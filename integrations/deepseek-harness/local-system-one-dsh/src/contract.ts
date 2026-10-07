import type {
  AdapterMode,
  ModelTierDecision,
  NotificationDecision,
  SearchDecision,
} from './types.js'

export const ADAPTER_CONTRACT_VERSION = '1.0'
export type GateName = 'search' | 'model_tier' | 'notification'
export type ActionStatus = 'observed' | 'applied' | 'skipped' | 'failed_open' | 'unsupported'

export interface ActionOutcome {
  status: ActionStatus
  reason: string
}

export interface DecisionEnvelope {
  adapter_contract_version: typeof ADAPTER_CONTRACT_VERSION
  request_id: string | null
  gate: GateName
  decision: Record<string, unknown>
  decision_source: 'rule' | 'model'
  reason: string
  backend: string
  latency_ms: number
  confidence?: number
}

export type RuntimeDecision = SearchDecision | ModelTierDecision | NotificationDecision

export function toDecisionEnvelope(gate: 'search', decision: SearchDecision): DecisionEnvelope
export function toDecisionEnvelope(gate: 'model_tier', decision: ModelTierDecision): DecisionEnvelope
export function toDecisionEnvelope(gate: 'notification', decision: NotificationDecision): DecisionEnvelope
export function toDecisionEnvelope(gate: GateName, decision: RuntimeDecision): DecisionEnvelope {
  const common = {
    adapter_contract_version: ADAPTER_CONTRACT_VERSION,
    request_id: decision.request_id,
    gate,
    decision_source: decision.decision_source,
    reason: decision.reason,
    backend: decision.backend,
    latency_ms: decision.latency_ms,
  } as const

  if (gate === 'search') {
    const value = decision as SearchDecision
    return {
      ...common,
      gate,
      decision: {
        value: value.decision,
        probability_search: value.probability_search,
      },
    }
  }
  if (gate === 'model_tier') {
    const value = decision as ModelTierDecision
    return {
      ...common,
      gate,
      decision: {
        value: value.tier,
        difficulty_score: value.difficulty_score,
        probability_strong: value.probability_strong,
      },
      confidence: value.confidence,
    }
  }
  const value = decision as NotificationDecision
  return {
    ...common,
    gate: 'notification',
    decision: {
      value: value.delivery,
      notify_now: value.notify_now,
      priority_score: value.priority_score,
    },
    confidence: value.confidence,
  }
}

export function actionOutcome(status: ActionStatus, reason: string): ActionOutcome {
  return { status, reason }
}

export function telemetryRecord(
  adapterVersion: string,
  mode: AdapterMode,
  envelope: DecisionEnvelope,
  outcome: ActionOutcome,
  extra: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    adapter_contract_version: ADAPTER_CONTRACT_VERSION,
    platform: 'deepseek_harness',
    adapter_version: adapterVersion,
    gate: envelope.gate,
    mode,
    decision: envelope.decision,
    decision_source: envelope.decision_source,
    reason: envelope.reason,
    backend: envelope.backend,
    latency_ms: envelope.latency_ms,
    action_status: outcome.status,
    action_reason: outcome.reason,
    request_id: envelope.request_id,
    ...extra,
  }
}

export function failureActionReason(error: unknown): string {
  if (error instanceof DOMException && error.name === 'AbortError') return 'runtime_timeout'
  if (error instanceof Error) {
    if (/\bHTTP\s+\d{3}\b/.test(error.message)) return 'runtime_http_error'
    if (/^invalid\s|must be in \[|response field/i.test(error.message)) return 'malformed_response'
  }
  return 'runtime_error'
}
