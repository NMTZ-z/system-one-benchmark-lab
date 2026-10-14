import type {
  CompletionDecision,
  CompletionExecutionState,
  ModelTierDecision,
  NotificationDecision,
  SearchDecision,
  FailureContext,
  RetryEscalationDecision,
  RetryDecisionValue,
} from './types.js'

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function requiredString(
  value: Record<string, unknown>,
  key: string,
  contract: string,
): string {
  const field = value[key]
  if (typeof field !== 'string' || field.length === 0) {
    throw new Error(`invalid ${contract} response field: ${key}`)
  }
  return field
}

function requiredNumber(
  value: Record<string, unknown>,
  key: string,
  contract: string,
): number {
  const field = value[key]
  if (typeof field !== 'number' || !Number.isFinite(field)) {
    throw new Error(`invalid ${contract} response field: ${key}`)
  }
  return field
}

function requestId(value: Record<string, unknown>, contract: string): string | null {
  const field = value.request_id
  if (field !== null && field !== undefined && typeof field !== 'string') {
    throw new Error(`invalid ${contract} response field: request_id`)
  }
  return field ?? null
}

export function parseSearchDecision(value: unknown): SearchDecision {
  const contract = 'search-gate'
  if (!isRecord(value)) {
    throw new Error(`invalid ${contract} response`)
  }

  const decision = requiredString(value, 'decision', contract)
  if (decision !== 'search' && decision !== 'no_search') {
    throw new Error(`invalid ${contract} response field: decision`)
  }

  const decisionSource = requiredString(value, 'decision_source', contract)
  if (decisionSource !== 'rule' && decisionSource !== 'model') {
    throw new Error(`invalid ${contract} response field: decision_source`)
  }

  const probabilitySearch = requiredNumber(value, 'probability_search', contract)
  if (probabilitySearch < 0 || probabilitySearch > 1) {
    throw new Error('probability_search must be in [0, 1]')
  }

  return {
    decision,
    decision_source: decisionSource,
    reason: requiredString(value, 'reason', contract),
    probability_search: probabilitySearch,
    backend: requiredString(value, 'backend', contract),
    latency_ms: requiredNumber(value, 'latency_ms', contract),
    request_id: requestId(value, contract),
  }
}

export function parseModelTierDecision(value: unknown): ModelTierDecision {
  const contract = 'model-tier-gate'
  if (!isRecord(value)) {
    throw new Error(`invalid ${contract} response`)
  }

  const tier = requiredString(value, 'tier', contract)
  if (tier !== 'fast' && tier !== 'strong') {
    throw new Error(`invalid ${contract} response field: tier`)
  }

  const decisionSource = requiredString(value, 'decision_source', contract)
  if (decisionSource !== 'rule' && decisionSource !== 'model') {
    throw new Error(`invalid ${contract} response field: decision_source`)
  }

  const difficultyScore = requiredNumber(value, 'difficulty_score', contract)
  const probabilityStrong = requiredNumber(value, 'probability_strong', contract)
  const confidence = requiredNumber(value, 'confidence', contract)
  if (probabilityStrong < 0 || probabilityStrong > 1) {
    throw new Error('probability_strong must be in [0, 1]')
  }
  if (confidence < 0 || confidence > 1) {
    throw new Error('confidence must be in [0, 1]')
  }

  return {
    tier,
    decision_source: decisionSource,
    reason: requiredString(value, 'reason', contract),
    difficulty_score: difficultyScore,
    probability_strong: probabilityStrong,
    confidence,
    backend: requiredString(value, 'backend', contract),
    latency_ms: requiredNumber(value, 'latency_ms', contract),
    request_id: requestId(value, contract),
  }
}

export function parseNotificationDecision(value: unknown): NotificationDecision {
  const contract = 'notification-gate'
  if (!isRecord(value)) {
    throw new Error(`invalid ${contract} response`)
  }

  const delivery = requiredString(value, 'delivery', contract)
  if (!['silent', 'digest', 'notify_now'].includes(delivery)) {
    throw new Error(`invalid ${contract} response field: delivery`)
  }
  const notifyNow = value.notify_now
  if (typeof notifyNow !== 'boolean') {
    throw new Error(`invalid ${contract} response field: notify_now`)
  }
  const decisionSource = requiredString(value, 'decision_source', contract)
  if (decisionSource !== 'rule' && decisionSource !== 'model') {
    throw new Error(`invalid ${contract} response field: decision_source`)
  }
  const priorityScore = requiredNumber(value, 'priority_score', contract)
  if (priorityScore < 0 || priorityScore > 4) {
    throw new Error('priority_score must be in [0, 4]')
  }
  const confidence = requiredNumber(value, 'confidence', contract)
  if (confidence < 0 || confidence > 1) {
    throw new Error('confidence must be in [0, 1]')
  }

  return {
    delivery: delivery as NotificationDecision['delivery'],
    notify_now: notifyNow,
    decision_source: decisionSource,
    reason: requiredString(value, 'reason', contract),
    priority_score: priorityScore,
    confidence,
    backend: requiredString(value, 'backend', contract),
    latency_ms: requiredNumber(value, 'latency_ms', contract),
    request_id: requestId(value, contract),
  }
}

export function parseCompletionDecision(value: unknown): CompletionDecision {
  const contract = 'completion-gate'
  if (!isRecord(value)) {
    throw new Error(`invalid ${contract} response`)
  }
  const decision = requiredString(value, 'decision', contract)
  if (!['complete', 'continue', 'verify'].includes(decision)) {
    throw new Error(`invalid ${contract} response field: decision`)
  }
  const decisionSource = requiredString(value, 'decision_source', contract)
  if (decisionSource !== 'rule' && decisionSource !== 'model') {
    throw new Error(`invalid ${contract} response field: decision_source`)
  }
  const probabilityComplete = requiredNumber(value, 'probability_complete', contract)
  const probabilityVerify = requiredNumber(value, 'probability_verify', contract)
  const probabilityContinue = requiredNumber(value, 'probability_continue', contract)
  const confidence = requiredNumber(value, 'confidence', contract)
  for (const [key, probability] of [
    ['probability_complete', probabilityComplete],
    ['probability_verify', probabilityVerify],
    ['probability_continue', probabilityContinue],
    ['confidence', confidence],
  ] as const) {
    if (probability < 0 || probability > 1) throw new Error(`${key} must be in [0, 1]`)
  }
  return {
    decision: decision as CompletionDecision['decision'],
    decision_source: decisionSource,
    reason: requiredString(value, 'reason', contract),
    probability_complete: probabilityComplete,
    probability_verify: probabilityVerify,
    probability_continue: probabilityContinue,
    confidence,
    backend: requiredString(value, 'backend', contract),
    latency_ms: requiredNumber(value, 'latency_ms', contract),
    request_id: requestId(value, contract),
  }
}

class GateClient<T> {
  constructor(
    private readonly serviceUrl: string,
    private readonly timeoutMs: number,
    private readonly path: string,
    private readonly parser: (value: unknown) => T,
  ) {}

  protected async post(payload: Record<string, unknown>): Promise<T> {
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), this.timeoutMs)

    try {
      const response = await fetch(`${this.serviceUrl}${this.path}`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(payload),
        signal: controller.signal,
      })

      if (!response.ok) {
        throw new Error(`${this.path} HTTP ${response.status}`)
      }
      return this.parser(await response.json())
    } finally {
      clearTimeout(timeout)
    }
  }

  protected async decideTask(task: string, requestIdValue: string): Promise<T> {
    return this.post({ task, request_id: requestIdValue })
  }
}

export class SearchGateClient extends GateClient<SearchDecision> {
  constructor(serviceUrl: string, timeoutMs: number) {
    super(serviceUrl, timeoutMs, '/v1/workflows/search-gate', parseSearchDecision)
  }

  async decide(task: string, requestIdValue: string): Promise<SearchDecision> {
    return this.decideTask(task, requestIdValue)
  }
}

export class ModelTierGateClient extends GateClient<ModelTierDecision> {
  constructor(serviceUrl: string, timeoutMs: number) {
    super(serviceUrl, timeoutMs, '/v1/workflows/model-tier-gate', parseModelTierDecision)
  }

  async decide(task: string, requestIdValue: string): Promise<ModelTierDecision> {
    return this.decideTask(task, requestIdValue)
  }
}

export class NotificationGateClient extends GateClient<NotificationDecision> {
  constructor(serviceUrl: string, timeoutMs: number) {
    super(serviceUrl, timeoutMs, '/v1/workflows/notification-gate', parseNotificationDecision)
  }

  async decide(
    event: string,
    requestIdValue: string,
    context: Record<string, unknown> | null = null,
    blockingFailure = false,
  ): Promise<NotificationDecision> {
    return this.post({
      event,
      context,
      urgency: 'auto',
      user_action_required: false,
      blocking_failure: blockingFailure,
      routine_update: false,
      request_id: requestIdValue,
    })
  }
}

export class CompletionGateClient extends GateClient<CompletionDecision> {
  constructor(serviceUrl: string, timeoutMs: number) {
    super(serviceUrl, timeoutMs, '/v1/workflows/completion-gate', parseCompletionDecision)
  }

  async decide(
    task: string,
    currentResult: string,
    executionState: CompletionExecutionState,
    requestIdValue: string,
  ): Promise<CompletionDecision> {
    return this.post({
      task,
      current_result: currentResult,
      execution_state: executionState,
      request_id: requestIdValue,
    })
  }
}

const RETRY_DECISIONS = new Set<RetryDecisionValue>([
  'retry_same', 'try_alternative', 'escalate_model',
  'verify_state', 'ask_user', 'abort',
])

export function parseRetryEscalationDecision(value: unknown): RetryEscalationDecision {
  const contract = 'retry-escalation-gate'
  if (!isRecord(value) || value.workflow !== 'retry_escalation_gate'
      || value.advisory_only !== true) {
    throw new Error('invalid retry-escalation-gate response')
  }
  const decision = requiredString(value, 'decision', contract) as RetryDecisionValue
  if (!RETRY_DECISIONS.has(decision) || value.guarded_decision !== decision) {
    throw new Error('invalid retry decision or guarded decision')
  }
  const raw = value.raw_model_decision
  if (raw !== null && (typeof raw !== 'string' || !RETRY_DECISIONS.has(raw as RetryDecisionValue))) {
    throw new Error('invalid raw_model_decision')
  }
  if (value.safety_override_reason !== null &&
      (typeof value.safety_override_reason !== 'string' || !value.safety_override_reason)) {
    throw new Error('invalid safety_override_reason')
  }
  if (value.decision_source !== 'rule' && value.decision_source !== 'model') {
    throw new Error('invalid retry decision_source')
  }
  const reason = requiredString(value, 'reason', contract)
  if (!/^[a-z][a-z0-9_]{0,79}$/.test(reason)) {
    throw new Error('invalid retry telemetry reason')
  }
  if (value.safety_override_reason !== null &&
      !/^[a-z][a-z0-9_]{0,79}$/.test(value.safety_override_reason as string)) {
    throw new Error('invalid retry safety override')
  }
  const latency = requiredNumber(value, 'latency_ms', contract)
  const confidence = requiredNumber(value, 'confidence', contract)
  if (latency < 0 || confidence < 0 || confidence > 1) {
    throw new Error('invalid retry latency/confidence')
  }
  return {
    workflow: 'retry_escalation_gate',
    decision, guarded_decision: decision,
    raw_model_decision: raw as RetryDecisionValue | null,
    safety_override_reason: value.safety_override_reason as string | null,
    decision_source: value.decision_source,
    reason,
    backend: requiredString(value, 'backend', contract),
    latency_ms: latency, confidence,
    request_id: requestId(value, contract), advisory_only: true,
  }
}

export class RetryEscalationGateClient extends GateClient<RetryEscalationDecision> {
  constructor(serviceUrl: string, timeoutMs: number) {
    super(serviceUrl, timeoutMs, '/v1/workflows/retry-escalation-gate', parseRetryEscalationDecision)
  }

  async decide(context: FailureContext, requestIdValue: string): Promise<RetryEscalationDecision> {
    const result = await this.post({ ...context, request_id: requestIdValue })
    if (result.request_id !== requestIdValue) {
      throw new Error('retry gate request_id mismatch')
    }
    return result
  }
}
