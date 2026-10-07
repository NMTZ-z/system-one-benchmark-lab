import { randomUUID } from 'node:crypto'
import { ModelTierGateClient, NotificationGateClient, SearchGateClient } from './client.js'
import {
  ADAPTER_CONTRACT_VERSION,
  actionOutcome,
  failureActionReason,
  telemetryRecord,
  toDecisionEnvelope,
} from './contract.js'
import {
  hasCanaryAuthority,
  hasModelTierCanaryAuthority,
  isVerifiedPublicWebTool,
  isVerifiedReasoningDowngradeRoute,
  resolveConfig,
} from './policy.js'
import { TurnDecisionState } from './state.js'
import type {
  AdapterConfig,
  AdapterMode,
  DshContextLike,
  AgentRequestInputLike,
  LlmCallConfigLike,
  ModelTierDecision,
  NotificationDecision,
  PreStepInputLike,
  SearchDecision,
  SessionEventLike,
  SessionLike,
  ToolExecutionLike,
  UserMessageLike,
} from './types.js'

export const name = 'local-system-one-dsh'
export const version = '0.4.0'
const MAX_NOTIFICATION_CHARS = 6000

function asSessionId(session: SessionLike | undefined): string | null {
  if (session?.id === undefined || session.id === null) return null
  const value = String(session.id)
  return value.length > 0 ? value : null
}

function asPositiveInteger(value: unknown): number | null {
  return typeof value === 'number' && Number.isInteger(value) && value > 0 ? value : null
}

function contentText(content: unknown): string {
  if (typeof content === 'string') return content.trim()
  if (!Array.isArray(content)) return ''
  const parts: string[] = []
  for (const block of content) {
    if (typeof block === 'string') {
      const text = block.trim()
      if (text) parts.push(text)
      continue
    }
    if (typeof block !== 'object' || block === null) continue
    const record = block as Record<string, unknown>
    if (record.type === 'text' && typeof record.text === 'string') {
      const text = record.text.trim()
      if (text) parts.push(text)
    }
  }
  return parts.join('\n').trim()
}

function taskText(messages: readonly UserMessageLike[] | undefined): string {
  if (!messages) return ''
  const parts: string[] = []
  for (const message of messages) {
    if (message.role !== undefined && message.role !== 'user') continue
    const text = contentText(message.content)
    if (text) parts.push(text)
  }
  return parts.join('\n').trim()
}

function assistantEventText(event: SessionEventLike): string {
  const message = event.data?.message
  if (typeof message !== 'object' || message === null) return ''
  const content = (message as Record<string, unknown>).content
  return contentText(content).slice(0, MAX_NOTIFICATION_CHARS)
}

function turnReasonKind(value: unknown): string | null {
  if (typeof value !== 'object' || value === null) return null
  const kind = (value as Record<string, unknown>).kind
  return typeof kind === 'string' && kind.length > 0 ? kind : null
}

function turnKey(sessionId: string, turn: number): string {
  return `${sessionId}:${turn}`
}

function errorType(error: unknown): string {
  if (error instanceof Error && error.name) return error.name
  return typeof error
}

function logSearchDecision(
  ctx: DshContextLike,
  mode: AdapterMode,
  decision: SearchDecision,
): void {
  ctx.logger?.info?.(
    `[local-system-one-dsh] ${JSON.stringify(telemetryRecord(
      version,
      mode,
      toDecisionEnvelope('search', decision),
      actionOutcome('observed', 'shadow_or_pre_action_observation'),
    ))}`,
  )
}

function logModelTierDecision(
  ctx: DshContextLike,
  mode: AdapterMode,
  decision: ModelTierDecision,
): void {
  ctx.logger?.info?.(
    `[local-system-one-dsh] ${JSON.stringify(telemetryRecord(
      version,
      mode,
      toDecisionEnvelope('model_tier', decision),
      actionOutcome('observed', 'shadow_or_pre_action_observation'),
    ))}`,
  )
}

function logNotificationDecision(
  ctx: DshContextLike,
  mode: AdapterMode,
  decision: NotificationDecision,
  eventChars: number,
): void {
  ctx.logger?.info?.(
    `[local-system-one-dsh] ${JSON.stringify(telemetryRecord(
      version,
      mode,
      toDecisionEnvelope('notification', decision),
      actionOutcome('observed', 'notification_shadow_only'),
      { event_chars: eventChars },
    ))}`,
  )
}

function logFailOpen(
  ctx: DshContextLike,
  mode: AdapterMode,
  gate: 'search' | 'model_tier' | 'notification',
  error: unknown,
): void {
  ctx.logger?.info?.(
    `[local-system-one-dsh] ${JSON.stringify({
      adapter_contract_version: ADAPTER_CONTRACT_VERSION,
      platform: 'deepseek_harness',
      adapter_version: version,
      gate,
      mode,
      decision: null,
      decision_source: null,
      reason: null,
      backend: null,
      latency_ms: null,
      action_status: 'failed_open',
      action_reason: failureActionReason(error),
      request_id: null,
    })}`,
  )
}

function logAction(
  ctx: DshContextLike,
  mode: AdapterMode,
  gate: 'search' | 'model_tier',
  decision: SearchDecision | ModelTierDecision,
  status: 'applied' | 'skipped' | 'failed_open' | 'unsupported',
  reason: string,
  extra: Record<string, unknown> = {},
): void {
  const envelope = gate === 'search'
    ? toDecisionEnvelope('search', decision as SearchDecision)
    : toDecisionEnvelope('model_tier', decision as ModelTierDecision)
  ctx.logger?.info?.(
    `[local-system-one-dsh] ${JSON.stringify(telemetryRecord(
      version,
      mode,
      envelope,
      actionOutcome(status, reason),
      extra,
    ))}`,
  )
}

export function apply(ctx: DshContextLike, inputConfig: AdapterConfig = {}): void {
  const config = resolveConfig(inputConfig)
  const state = new TurnDecisionState()
  const searchClient = new SearchGateClient(config.serviceUrl, config.timeoutMs)
  const modelTierClient = new ModelTierGateClient(config.serviceUrl, config.timeoutMs)
  const notificationClient = new NotificationGateClient(config.serviceUrl, config.timeoutMs)
  const notificationCandidates = new Map<string, string>()

  if (config.mode === 'canary' && config.effectiveMode === 'shadow') {
    ctx.logger?.warn?.(
      '[local-system-one-dsh] canary requested without canary_acknowledged=true; using shadow',
    )
  }

  ctx.on('session/event', (session: SessionLike, event: SessionEventLike) => {
    if (
      config.effectiveMode === 'off'
      || (!config.searchGateEnabled && !config.modelTierGateEnabled && !config.notificationGateEnabled)
    ) return

    const sessionId = asSessionId(session)
    if (!sessionId || typeof event?.type !== 'string') return

    const turn = asPositiveInteger(event.data?.turn)
    if (event.type === 'turn/start' && turn !== null) {
      state.beginTurn(sessionId, turn)
      return
    }

    if (
      config.notificationGateEnabled
      && event.type === 'assistant/message'
      && turn !== null
    ) {
      const text = assistantEventText(event)
      if (text) notificationCandidates.set(turnKey(sessionId, turn), text)
      return
    }

    if (event.type === 'turn/end' && turn !== null) {
      const candidateKey = turnKey(sessionId, turn)
      let eventText = notificationCandidates.get(candidateKey) ?? ''
      notificationCandidates.delete(candidateKey)
      const reasonKind = turnReasonKind(event.data?.reason)
      const blockingFailure = reasonKind === 'error' || reasonKind === 'failed'
      if (!eventText && blockingFailure) {
        eventText = 'Agent turn ended with a blocking failure before producing a final response.'
      }
      if (config.notificationGateEnabled && eventText) {
        const requestId = randomUUID()
        const context = { turn, reason_kind: reasonKind }
        void notificationClient
          .decide(eventText, requestId, context, blockingFailure)
          .then(decision => logNotificationDecision(
            ctx, config.effectiveMode, decision, eventText.length,
          ))
          .catch(error => {
            logFailOpen(ctx, config.effectiveMode, 'notification', error)
            ctx.logger?.warn?.(
              `[local-system-one-dsh] notification gate unavailable; fail-open (${errorType(error)})`,
            )
          })
      }
      state.clearTurn(sessionId, turn)
      return
    }

    if (event.type === 'session/end' || event.type === 'session/close') {
      state.clearSession(sessionId)
      for (const key of notificationCandidates.keys()) {
        if (key.startsWith(`${sessionId}:`)) notificationCandidates.delete(key)
      }
    }
  })

  ctx.on(
    'agent/pre-step',
    async (
      input: PreStepInputLike,
      next: () => Promise<unknown>,
    ): Promise<unknown> => {
      if (
        config.effectiveMode === 'off'
        || (!config.searchGateEnabled && !config.modelTierGateEnabled)
      ) return next()

      const step = asPositiveInteger(input.step)
      const turn = asPositiveInteger(input.turn)
      const sessionId = asSessionId(input.agent?.session)
      if (step !== 1 || turn === null || !sessionId) {
        return next()
      }

      state.beginTurn(sessionId, turn)
      const task = taskText(input.messages)
      if (!task) return next()
      const requestId = randomUUID()

      if (config.searchGateEnabled) {
        try {
          const decision = await searchClient.decide(task, requestId)
          state.setSearchDecision(sessionId, turn, {
            ...decision,
            observed_at_ms: Date.now(),
          })
          logSearchDecision(ctx, config.effectiveMode, decision)
        } catch (error) {
          logFailOpen(ctx, config.effectiveMode, 'search', error)
          ctx.logger?.warn?.(
            `[local-system-one-dsh] search gate unavailable; fail-open (${errorType(error)})`,
          )
        }
      }

      if (config.modelTierGateEnabled) {
        try {
          const decision = await modelTierClient.decide(task, requestId)
          state.setModelTierDecision(sessionId, turn, {
            ...decision,
            observed_at_ms: Date.now(),
          })
          logModelTierDecision(ctx, config.effectiveMode, decision)
        } catch (error) {
          logFailOpen(ctx, config.effectiveMode, 'model_tier', error)
          ctx.logger?.warn?.(
            `[local-system-one-dsh] model tier gate unavailable; fail-open (${errorType(error)})`,
          )
        }
      }

      return next()
    },
  )


  if (
    config.effectiveMode === 'canary'
    && config.modelTierGateEnabled
    && config.canaryReasoningDowngradeEnabled
  ) {
    ctx.on(
      'agent/request',
      async (
        input: AgentRequestInputLike,
        next: () => Promise<LlmCallConfigLike>,
      ): Promise<LlmCallConfigLike> => {
        const original = await next()
        try {
          const step = asPositiveInteger(input.step)
          const turn = asPositiveInteger(input.turn)
          const sessionId = asSessionId(input.agent?.session)
          if (step !== 1 || turn === null || !sessionId) return original

          const decision = state.getModelTierDecision(sessionId, turn)
          if (!decision || !hasModelTierCanaryAuthority(decision)) return original

          const provider = typeof original?.provider === 'string' ? original.provider : ''
          const model = typeof original?.model === 'string' ? original.model : ''
          if (!provider || !model || !isVerifiedReasoningDowngradeRoute(provider, model)) {
            logAction(
              ctx,
              config.effectiveMode,
              'model_tier',
              decision,
              'unsupported',
              'unsupported_provider_or_model',
              { provider, model },
            )
            return original
          }
          if (original.reasoningEffort !== 'high') {
            logAction(
              ctx,
              config.effectiveMode,
              'model_tier',
              decision,
              'skipped',
              'original_reasoning_not_high',
              { provider, model },
            )
            return original
          }

          const updated: LlmCallConfigLike = { ...original, reasoningEffort: 'low' }
          logAction(
            ctx,
            config.effectiveMode,
            'model_tier',
            decision,
            'applied',
            'verified_reasoning_mapping',
            { provider, model, reasoning_effort_before: 'high', reasoning_effort_after: 'low' },
          )
          return updated
        } catch (error) {
          const step = asPositiveInteger(input.step)
          const turn = asPositiveInteger(input.turn)
          const sessionId = asSessionId(input.agent?.session)
          const decision = turn !== null && sessionId
            ? state.getModelTierDecision(sessionId, turn)
            : undefined
          if (decision) {
            logAction(
              ctx,
              config.effectiveMode,
              'model_tier',
              decision,
              'failed_open',
              'mutation_exception',
            )
          }
          ctx.logger?.warn?.(
            `[local-system-one-dsh] model tier mutation unavailable; fail-open (${errorType(error)})`,
          )
          return original
        }
      },
    )
  }

  ctx.on(
    'tools/pre-execute',
    async (
      execution: ToolExecutionLike,
      next: () => Promise<unknown>,
    ): Promise<unknown> => {
      if (
        config.effectiveMode !== 'canary'
        || !config.searchGateEnabled
        || !config.canaryWebFilterEnabled
      ) return next()
      try {
        const toolName = typeof execution.name === 'string' ? execution.name : ''
        if (!toolName || !isVerifiedPublicWebTool(toolName)) {
          return next()
        }

        const sessionId = asSessionId(execution.agent?.session)
        if (!sessionId) return next()

        const decision = state.getCurrentSearchDecision(sessionId)
        if (!decision || !hasCanaryAuthority(decision)) {
          if (decision) {
            logAction(
              ctx,
              config.effectiveMode,
              'search',
              decision,
              'skipped',
              'no_active_authority',
              { tool: toolName },
            )
          }
          return next()
        }

        logAction(
          ctx,
          config.effectiveMode,
          'search',
          decision,
          'applied',
          'verified_public_web_tool_denied',
          { tool: toolName },
        )
        return {
          kind: 'deny',
          reason: `Local System One hard no-Web rule: ${decision.reason}`,
        }
      } catch (error) {
        const sessionId = asSessionId(execution.agent?.session)
        const decision = sessionId ? state.getCurrentSearchDecision(sessionId) : undefined
        if (decision) {
          logAction(
            ctx,
            config.effectiveMode,
            'search',
            decision,
            'failed_open',
            'mutation_exception',
          )
        }
        ctx.logger?.warn?.(
          `[local-system-one-dsh] search mutation unavailable; fail-open (${errorType(error)})`,
        )
        return next()
      }
    },
  )
}

export {
  ADAPTER_CONTRACT_VERSION,
  actionOutcome,
  failureActionReason,
  telemetryRecord,
  toDecisionEnvelope,
} from './contract.js'
export {
  ModelTierGateClient,
  NotificationGateClient,
  SearchGateClient,
  parseModelTierDecision,
  parseNotificationDecision,
  parseSearchDecision,
} from './client.js'
export {
  AUDITED_HARD_FAST_REASONS,
  AUDITED_HARD_NO_WEB_REASONS,
  VERIFIED_PUBLIC_WEB_TOOLS,
  VERIFIED_REASONING_DOWNGRADE_ROUTES,
  hasCanaryAuthority,
  hasModelTierCanaryAuthority,
  isVerifiedPublicWebTool,
  isVerifiedReasoningDowngradeRoute,
  resolveConfig,
} from './policy.js'
export { TurnDecisionState } from './state.js'
export type * from './types.js'
