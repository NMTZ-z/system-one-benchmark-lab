import type { ModelTierDecision, SearchDecision } from './types.js'

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

class GateClient<T> {
  constructor(
    private readonly serviceUrl: string,
    private readonly timeoutMs: number,
    private readonly path: string,
    private readonly parser: (value: unknown) => T,
  ) {}

  async decide(task: string, requestIdValue: string): Promise<T> {
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), this.timeoutMs)

    try {
      const response = await fetch(`${this.serviceUrl}${this.path}`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ task, request_id: requestIdValue }),
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
}

export class SearchGateClient extends GateClient<SearchDecision> {
  constructor(serviceUrl: string, timeoutMs: number) {
    super(serviceUrl, timeoutMs, '/v1/workflows/search-gate', parseSearchDecision)
  }
}

export class ModelTierGateClient extends GateClient<ModelTierDecision> {
  constructor(serviceUrl: string, timeoutMs: number) {
    super(serviceUrl, timeoutMs, '/v1/workflows/model-tier-gate', parseModelTierDecision)
  }
}
