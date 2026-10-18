import { randomUUID } from 'node:crypto'
import {
  CompletionGateClient,
  ModelTierGateClient,
  NotificationGateClient,
  SearchGateClient,
  RetryEscalationGateClient,
} from './client.js'
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
import { TurnDecisionState, sessionKeyPrefix, turnKey } from './state.js'
import { operationFromToolName, resultCallId, failureFromToolResult } from './retry.js'
import type {
  AdapterConfig,
  AdapterMode,
  CompletionDecision,
  CompletionExecutionState,
  DshContextLike,
  AgentRequestInputLike,
  LlmCallConfigLike,
  ModelTierDecision,
  NotificationDecision,
  PreStepInputLike,
  SearchDecision,
  SessionEventLike,
  RetryEscalationDecision,
  SessionLike,
  ToolExecutionLike,
  UserMessageLike,
} from './types.js'

export const name = 'local-system-one-dsh'
export const version = '0.6.0'
const MAX_COMPLETION_TASK_CHARS = 4000
const MAX_NOTIFICATION_CHARS = 6000

interface CompletionCandidate {
  task?: string
  currentResult?: string
  toolsUsed: number
  toolFailures: number
  loopProbeSent?: boolean
}

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

function toolResultFailed(event: SessionEventLike): boolean {
  if (typeof event.data?.error === 'object' && event.data.error !== null) return true
  const message = event.data?.message
  if (typeof message !== 'object' || message === null) return false
  return (message as Record<string, unknown>).isError === true
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

function logCompletionDecision(
  ctx: DshContextLike,
  mode: AdapterMode,
  decision: CompletionDecision,
  taskChars: number,
  resultChars: number,
  stage: 'turn_end' | 'tool_result' = 'turn_end',
): void {
  ctx.logger?.info?.(
    `[local-system-one-dsh] ${JSON.stringify(telemetryRecord(
      version,
      mode,
      toDecisionEnvelope('completion', decision),
      actionOutcome('observed', 'completion_shadow_only'),
      { task_chars: taskChars, result_chars: resultChars, stage },
    ))}`,
  )
}

function logFailOpen(
  ctx: DshContextLike,
  mode: AdapterMode,
  gate: 'search' | 'model_tier' | 'notification' | 'completion',
  error: unknown,
  stage?: 'tool_result' | 'turn_end',
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
      ...(stage ? { stage } : {}),
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
  const completionClient = new CompletionGateClient(config.serviceUrl, config.timeoutMs)
  const retryClient = new RetryEscalationGateClient(config.serviceUrl, config.timeoutMs)
  const retryCallNames = new Map<string, string>()
  const retrySeen = new Set<string>()
  const retryCounts = new Map<string, number>()
  // Only a native turn/start can admit Retry events. Ended turns cannot be
  // resurrected by delayed tool/call or tool/result callbacks.
  const retryLiveTurns = new Set<string>()
  let retryInFlight = 0
  const RETRY_MAX_OBSERVATIONS = 2
  const RETRY_MAX_ACTIVE_TURNS = 96
  const RETRY_MAX_INFLIGHT = 4

  function retryStatus(status: 'unsupported' | 'failed_open', reason: string): void {
    ctx.logger?.info?.('[local-system-one-dsh] ' + JSON.stringify({
      adapter_contract_version: ADAPTER_CONTRACT_VERSION,
      platform: 'deepseek_harness', adapter_version: version,
      gate: 'retry_escalation', mode: config.effectiveMode,
      action_status: status, action_reason: reason, request_id: null,
    }))
  }
  function retryDecision(decision: RetryEscalationDecision): void {
    ctx.logger?.info?.('[local-system-one-dsh] ' + JSON.stringify(telemetryRecord(
      version, config.effectiveMode, toDecisionEnvelope('retry_escalation', decision),
      actionOutcome('observed', 'retry_shadow_advisory_only'),
    )))
  }

  const notificationCandidates = new Map<string, string>()
  const completionCandidates = new Map<string, CompletionCandidate>()

  if (config.mode === 'canary' && config.effectiveMode === 'shadow') {
    ctx.logger?.warn?.(
      '[local-system-one-dsh] canary requested without canary_acknowledged=true; using shadow',
    )
  }

  ctx.on('session/event', (session: SessionLike, event: SessionEventLike) => {
    if (
      config.effectiveMode === 'off'
      || (
        !config.searchGateEnabled
        && !config.modelTierGateEnabled
        && !config.notificationGateEnabled
        && !config.completionGateEnabled
        && !config.retryEscalationGateEnabled
      )
    ) return

    const sessionId = asSessionId(session)
    if (!sessionId || typeof event?.type !== 'string') return

    const turn = asPositiveInteger(event.data?.turn)
    if (event.type === 'turn/start' && turn !== null) {
      const key = turnKey(sessionId, turn)
      // A duplicated turn/start must not reset a live Retry observation
      // counter. Only turn/end or session/end may release its budget.
      if (!retryCounts.has(key)) {
        for (const k of retryCallNames.keys()) {
          if (k.startsWith(key + ':')) retryCallNames.delete(k)
        }
        for (const k of retrySeen) {
          if (k.startsWith(key + ':')) retrySeen.delete(k)
        }
      }
      if (config.retryEscalationGateEnabled && !retryLiveTurns.has(key)) {
        if (retryLiveTurns.size < RETRY_MAX_ACTIVE_TURNS) {
          retryLiveTurns.add(key)
        } else {
          retryStatus('failed_open', 'retry_turn_capacity_exhausted')
        }
      }
      state.beginTurn(sessionId, turn)
      return
    }

    if (config.retryEscalationGateEnabled && event.type === 'tool/call' && turn !== null) {
      // Late calls without a started turn cannot revive cleaned identity maps.
      if (!retryLiveTurns.has(turnKey(sessionId, turn))) return
      // Join exact upstream call id to a pinned tool policy; do not retain arguments.
      const callId = event.data?.callId
      const toolName = event.data?.name
      if (typeof callId === 'string' && callId.length > 0 && callId.length <= 128) {
        const key = turnKey(sessionId, turn)
        retryCallNames.set(key + ':' + callId,
          typeof toolName === 'string' && operationFromToolName(toolName) ? toolName : '')
        while (retryCallNames.size > 256) retryCallNames.delete(retryCallNames.keys().next().value!)
      }
      return
    }

    if (
      (config.notificationGateEnabled || config.completionGateEnabled)
      && event.type === 'assistant/message'
      && turn !== null
    ) {
      const text = assistantEventText(event)
      const key = turnKey(sessionId, turn)
      if (text && config.notificationGateEnabled) notificationCandidates.set(key, text)
      if (text && config.completionGateEnabled) {
        const candidate = completionCandidates.get(key) ?? { toolsUsed: 0, toolFailures: 0 }
        candidate.currentResult = text
        completionCandidates.set(key, candidate)
      }
      return
    }

    if (config.retryEscalationGateEnabled && event.type === 'tool/result' && turn !== null
        && retryLiveTurns.has(turnKey(sessionId, turn))) {
      const message = event.data?.message
      if (typeof message === 'object' && message !== null &&
          (message as Record<string, unknown>).isError === true) {
        const key = turnKey(sessionId, turn)
        const callId = resultCallId(event)
        const callKey = callId ? key + ':' + callId : ''
        // Never evict an active turn to make room for a new one: doing
        // so would reset its 2-observation safety limit. Reject new turn
        // observations at capacity and keep existing counts until end.
        if (!retryCounts.has(key) && retryCounts.size >= RETRY_MAX_ACTIVE_TURNS) {
          retryStatus('failed_open', 'retry_turn_capacity_exhausted')
        } else if ((retryCounts.get(key) ?? 0) < RETRY_MAX_OBSERVATIONS &&
            (!callKey || !retrySeen.has(callKey))) {
          retryCounts.set(key, (retryCounts.get(key) ?? 0) + 1)
          if (callKey) retrySeen.add(callKey)
          // At most 96 tracked turns x 2 observations = 192 seen IDs.
          // FIFO eviction is unsafe here because call IDs can reappear.
          const name = retryCallNames.get(callKey)
          const operation = name ? operationFromToolName(name) : null
          const failure = operation ? failureFromToolResult(event, operation) : null
          if (!callKey || !operation || !failure) {
            retryStatus('unsupported', 'failure_identity_or_operation_unverified')
          } else if (retryInFlight >= RETRY_MAX_INFLIGHT) {
            retryStatus('failed_open', 'retry_observer_capacity_exhausted')
          } else {
            retryInFlight += 1
            void retryClient.decide(failure, randomUUID())
              .then(value => retryDecision(value))
              .catch(_error => retryStatus('failed_open', 'retry_runtime_unavailable'))
              .finally(() => { retryInFlight -= 1 })
          }
        }
      }
      // Completion keeps its independent tool-result accounting.
    }

    if (config.completionGateEnabled && event.type === 'tool/result' && turn !== null) {
      const candidate = completionCandidates.get(turnKey(sessionId, turn))
      if (candidate) {
        candidate.toolsUsed += 1
        if (toolResultFailed(event)) candidate.toolFailures += 1
        // Experimental one-per-turn tool-result observer, explicitly OFF by default.
        // Never await inference in the event path or make Agent execution conditional.
        if (config.completionLoopProbeEnabled && candidate.task && !candidate.loopProbeSent) {
          candidate.loopProbeSent = true // suppress duplicate probes before I/O
          const resultText = (
            'A tool step finished during the Agent turn. '
            + 'The final requested deliverable has not been independently checked.'
          )
          const executionState: CompletionExecutionState = {
            tools_used: candidate.toolsUsed,
            tool_failures: candidate.toolFailures,
          }
          const task = candidate.task
          void completionClient
            .decide(task, resultText, executionState, randomUUID())
            .then(decision => logCompletionDecision(
              ctx, config.effectiveMode, decision, task.length, resultText.length, 'tool_result',
            ))
            .catch(error => {
              logFailOpen(ctx, config.effectiveMode, 'completion', error, 'tool_result')
              ctx.logger?.warn?.(
                `[local-system-one-dsh] completion loop probe unavailable; fail-open (${errorType(error)})`,
              )
            })
        }
      }
      return
    }

    if (event.type === 'turn/end' && turn !== null) {
      const candidateKey = turnKey(sessionId, turn)
      retryLiveTurns.delete(candidateKey)
      retryCounts.delete(candidateKey)
      for (const k of retryCallNames.keys()) {
        if (k.startsWith(candidateKey + ':')) retryCallNames.delete(k)
      }
      for (const k of retrySeen) {
        if (k.startsWith(candidateKey + ':')) retrySeen.delete(k)
      }
      let eventText = notificationCandidates.get(candidateKey) ?? ''
      notificationCandidates.delete(candidateKey)
      const completionCandidate = completionCandidates.get(candidateKey)
      completionCandidates.delete(candidateKey)
      const reasonKind = turnReasonKind(event.data?.reason)
      const blockingFailure = reasonKind !== null && reasonKind !== 'completed'
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
      if (config.completionGateEnabled) {
        if (completionCandidate?.task) {
          const currentResult = completionCandidate.currentResult
            ?? 'Agent turn ended before producing a final result.'
          const executionState: CompletionExecutionState = {
            tools_used: completionCandidate.toolsUsed,
            tool_failures: completionCandidate.toolFailures,
            blocking_failure: blockingFailure,
            required_step_missing: !completionCandidate.currentResult,
          }
          const requestId = randomUUID()
          void completionClient
            .decide(completionCandidate.task, currentResult, executionState, requestId)
            .then(decision => logCompletionDecision(
              ctx,
              config.effectiveMode,
              decision,
              completionCandidate.task?.length ?? 0,
              currentResult.length,
            ))
            .catch(error => {
              logFailOpen(ctx, config.effectiveMode, 'completion', error, 'turn_end')
              ctx.logger?.warn?.(
                `[local-system-one-dsh] completion gate unavailable; fail-open (${errorType(error)})`,
              )
            })
        } else {
          ctx.logger?.info?.(
            `[local-system-one-dsh] ${JSON.stringify({
              adapter_contract_version: ADAPTER_CONTRACT_VERSION,
              platform: 'deepseek_harness',
              adapter_version: version,
              gate: 'completion',
              mode: config.effectiveMode,
              decision: null,
              decision_source: null,
              reason: null,
              backend: null,
              latency_ms: null,
              action_status: 'unsupported',
              action_reason: 'task_unavailable_at_turn_boundary',
              request_id: null,
            })}`,
          )
        }
      }
      state.clearTurn(sessionId, turn)
      return
    }

    if (event.type === 'session/end' || event.type === 'session/close') {
      for (const k of retryLiveTurns) {
        if (k.startsWith(sessionKeyPrefix(sessionId))) retryLiveTurns.delete(k)
      }
      for (const k of retryCounts.keys()) {
        if (k.startsWith(sessionKeyPrefix(sessionId))) retryCounts.delete(k)
      }
      for (const k of retryCallNames.keys()) {
        if (k.startsWith(sessionKeyPrefix(sessionId))) retryCallNames.delete(k)
      }
      for (const k of retrySeen) {
        if (k.startsWith(sessionKeyPrefix(sessionId))) retrySeen.delete(k)
      }
      state.clearSession(sessionId)
      for (const key of notificationCandidates.keys()) {
        if (key.startsWith(sessionKeyPrefix(sessionId))) notificationCandidates.delete(key)
      }
      for (const key of completionCandidates.keys()) {
        if (key.startsWith(sessionKeyPrefix(sessionId))) completionCandidates.delete(key)
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
        || (!config.searchGateEnabled && !config.modelTierGateEnabled && !config.completionGateEnabled)
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
      if (config.completionGateEnabled) {
        completionCandidates.set(turnKey(sessionId, turn), {
          task: task.slice(0, MAX_COMPLETION_TASK_CHARS),
          toolsUsed: 0,
          toolFailures: 0,
        })
      }
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
  CompletionGateClient,
  NotificationGateClient,
  SearchGateClient,
  RetryEscalationGateClient,
  parseCompletionDecision,
  parseModelTierDecision,
  parseNotificationDecision,
  parseSearchDecision,
  parseRetryEscalationDecision,
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
