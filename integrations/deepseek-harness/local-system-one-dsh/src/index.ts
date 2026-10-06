import { randomUUID } from 'node:crypto'
import { ModelTierGateClient, SearchGateClient } from './client.js'
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
  DshContextLike,
  AgentRequestInputLike,
  LlmCallConfigLike,
  ModelTierDecision,
  PreStepInputLike,
  SearchDecision,
  SessionEventLike,
  SessionLike,
  ToolExecutionLike,
  UserMessageLike,
} from './types.js'

export const name = 'local-system-one-dsh'

function asSessionId(session: SessionLike | undefined): string | null {
  if (session?.id === undefined || session.id === null) return null
  const value = String(session.id)
  return value.length > 0 ? value : null
}

function asPositiveInteger(value: unknown): number | null {
  return typeof value === 'number' && Number.isInteger(value) && value > 0 ? value : null
}

function taskText(messages: readonly UserMessageLike[] | undefined): string {
  if (!messages) return ''
  const parts: string[] = []

  for (const message of messages) {
    if (message.role !== undefined && message.role !== 'user') continue
    for (const block of message.content ?? []) {
      if (block.type === 'text' && typeof block.text === 'string') {
        const text = block.text.trim()
        if (text) parts.push(text)
      }
    }
  }

  return parts.join('\n').trim()
}

function errorType(error: unknown): string {
  if (error instanceof Error && error.name) return error.name
  return typeof error
}

function logSearchDecision(
  ctx: DshContextLike,
  mode: string,
  decision: SearchDecision,
): void {
  ctx.logger?.info?.(
    `[local-system-one-dsh] ${JSON.stringify({
      gate: 'search',
      mode,
      request_id: decision.request_id,
      decision: decision.decision,
      decision_source: decision.decision_source,
      reason: decision.reason,
      probability_search: decision.probability_search,
      backend: decision.backend,
      latency_ms: decision.latency_ms,
    })}`,
  )
}

function logModelTierDecision(
  ctx: DshContextLike,
  mode: string,
  decision: ModelTierDecision,
): void {
  ctx.logger?.info?.(
    `[local-system-one-dsh] ${JSON.stringify({
      gate: 'model_tier',
      mode,
      request_id: decision.request_id,
      tier: decision.tier,
      decision_source: decision.decision_source,
      reason: decision.reason,
      difficulty_score: decision.difficulty_score,
      probability_strong: decision.probability_strong,
      confidence: decision.confidence,
      backend: decision.backend,
      latency_ms: decision.latency_ms,
    })}`,
  )
}

export function apply(ctx: DshContextLike, inputConfig: AdapterConfig = {}): void {
  const config = resolveConfig(inputConfig)
  const state = new TurnDecisionState()
  const searchClient = new SearchGateClient(config.serviceUrl, config.timeoutMs)
  const modelTierClient = new ModelTierGateClient(config.serviceUrl, config.timeoutMs)

  if (config.mode === 'canary' && config.effectiveMode === 'shadow') {
    ctx.logger?.warn?.(
      '[local-system-one-dsh] canary requested without canary_acknowledged=true; using shadow',
    )
  }

  ctx.on('session/event', (session: SessionLike, event: SessionEventLike) => {
    if (
      config.effectiveMode === 'off'
      || (!config.searchGateEnabled && !config.modelTierGateEnabled)
    ) return

    const sessionId = asSessionId(session)
    if (!sessionId || typeof event?.type !== 'string') return

    const turn = asPositiveInteger(event.data?.turn)
    if (event.type === 'turn/start' && turn !== null) {
      state.beginTurn(sessionId, turn)
      return
    }

    if (event.type === 'turn/end' && turn !== null) {
      state.clearTurn(sessionId, turn)
      return
    }

    if (event.type === 'session/end' || event.type === 'session/close') {
      state.clearSession(sessionId)
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
            return original
          }
          if (original.reasoningEffort !== 'high') return original

          const updated: LlmCallConfigLike = { ...original, reasoningEffort: 'low' }
          ctx.logger?.info?.(
            `[local-system-one-dsh] ${JSON.stringify({
              gate: 'model_tier',
              mode: 'canary',
              action: 'reasoning_effort_downgrade',
              provider,
              model,
              from: 'high',
              to: 'low',
              reason: decision.reason,
              request_id: decision.request_id,
            })}`,
          )
          return updated
        } catch (error) {
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

      const toolName = typeof execution.name === 'string' ? execution.name : ''
      if (!toolName || !isVerifiedPublicWebTool(toolName)) {
        return next()
      }

      const sessionId = asSessionId(execution.agent?.session)
      if (!sessionId) return next()

      const decision = state.getCurrentSearchDecision(sessionId)
      if (!decision || !hasCanaryAuthority(decision)) {
        return next()
      }

      return {
        kind: 'deny',
        reason: `Local System One hard no-Web rule: ${decision.reason}`,
      }
    },
  )
}

export {
  ModelTierGateClient,
  SearchGateClient,
  parseModelTierDecision,
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
