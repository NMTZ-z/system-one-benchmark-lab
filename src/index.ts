import { randomUUID } from 'node:crypto'
import { SearchGateClient } from './client.js'
import { hasCanaryAuthority, isVerifiedPublicWebTool, resolveConfig } from './policy.js'
import { TurnDecisionState } from './state.js'
import type {
  AdapterConfig,
  DshContextLike,
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

function logDecision(
  ctx: DshContextLike,
  mode: string,
  decision: SearchDecision,
): void {
  ctx.logger?.info?.(
    `[local-system-one-dsh] ${JSON.stringify({
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

export function apply(ctx: DshContextLike, inputConfig: AdapterConfig = {}): void {
  const config = resolveConfig(inputConfig)
  const state = new TurnDecisionState()
  const client = new SearchGateClient(config.serviceUrl, config.timeoutMs)

  if (config.mode === 'canary' && config.effectiveMode === 'shadow') {
    ctx.logger?.warn?.(
      '[local-system-one-dsh] canary requested without canary_acknowledged=true; using shadow',
    )
  }

  ctx.on('session/event', (session: SessionLike, event: SessionEventLike) => {
    if (config.effectiveMode === 'off' || !config.searchGateEnabled) return

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
      if (config.effectiveMode === 'off' || !config.searchGateEnabled) {
        return next()
      }

      const step = asPositiveInteger(input.step)
      const turn = asPositiveInteger(input.turn)
      const sessionId = asSessionId(input.agent?.session)
      if (step !== 1 || turn === null || !sessionId) {
        return next()
      }

      state.beginTurn(sessionId, turn)
      const task = taskText(input.messages)
      if (!task) return next()

      try {
        const decision = await client.decide(task, randomUUID())
        state.setDecision(sessionId, turn, {
          ...decision,
          observed_at_ms: Date.now(),
        })
        logDecision(ctx, config.effectiveMode, decision)
      } catch (error) {
        ctx.logger?.warn?.(
          `[local-system-one-dsh] search gate unavailable; fail-open (${errorType(error)})`,
        )
      }

      return next()
    },
  )

  ctx.on(
    'tools/pre-execute',
    async (
      execution: ToolExecutionLike,
      next: () => Promise<unknown>,
    ): Promise<unknown> => {
      if (config.effectiveMode !== 'canary' || !config.searchGateEnabled) {
        return next()
      }

      const toolName = typeof execution.name === 'string' ? execution.name : ''
      if (!toolName || !isVerifiedPublicWebTool(toolName)) {
        return next()
      }

      const sessionId = asSessionId(execution.agent?.session)
      if (!sessionId) return next()

      const decision = state.getCurrentDecision(sessionId)
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

export { SearchGateClient, parseSearchDecision } from './client.js'
export {
  AUDITED_HARD_NO_WEB_REASONS,
  VERIFIED_PUBLIC_WEB_TOOLS,
  hasCanaryAuthority,
  isVerifiedPublicWebTool,
  resolveConfig,
} from './policy.js'
export { TurnDecisionState } from './state.js'
export type * from './types.js'