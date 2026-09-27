import { performance } from 'node:perf_hooks'
import type { SearchDecision } from './types.js'

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function requiredString(
  value: Record<string, unknown>,
  key: string,
): string {
  const field = value[key]
  if (typeof field !== 'string' || field.length === 0) {
    throw new Error(`invalid search-gate response field: ${key}`)
  }
  return field
}

function requiredNumber(
  value: Record<string, unknown>,
  key: string,
): number {
  const field = value[key]
  if (typeof field !== 'number' || !Number.isFinite(field)) {
    throw new Error(`invalid search-gate response field: ${key}`)
  }
  return field
}

export function parseSearchDecision(value: unknown): SearchDecision {
  if (!isRecord(value)) {
    throw new Error('invalid search-gate response')
  }

  const decision = requiredString(value, 'decision')
  if (decision !== 'search' && decision !== 'no_search') {
    throw new Error('invalid search-gate response field: decision')
  }

  const decisionSource = requiredString(value, 'decision_source')
  if (decisionSource !== 'rule' && decisionSource !== 'model') {
    throw new Error('invalid search-gate response field: decision_source')
  }

  const probabilitySearch = requiredNumber(value, 'probability_search')
  if (probabilitySearch < 0 || probabilitySearch > 1) {
    throw new Error('probability_search must be in [0, 1]')
  }

  const requestId = value.request_id
  if (requestId !== null && requestId !== undefined && typeof requestId !== 'string') {
    throw new Error('invalid search-gate response field: request_id')
  }

  return {
    decision,
    decision_source: decisionSource,
    reason: requiredString(value, 'reason'),
    probability_search: probabilitySearch,
    backend: requiredString(value, 'backend'),
    latency_ms: requiredNumber(value, 'latency_ms'),
    request_id: requestId ?? null,
  }
}

export class SearchGateClient {
  constructor(
    private readonly serviceUrl: string,
    private readonly timeoutMs: number,
  ) {}

  async decide(task: string, requestId: string): Promise<SearchDecision> {
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), this.timeoutMs)
    const started = performance.now()

    try {
      const response = await fetch(`${this.serviceUrl}/v1/workflows/search-gate`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ task, request_id: requestId }),
        signal: controller.signal,
      })

      if (!response.ok) {
        throw new Error(`search-gate HTTP ${response.status}`)
      }

      const parsed = parseSearchDecision(await response.json())
      if (!Number.isFinite(parsed.latency_ms)) {
        parsed.latency_ms = performance.now() - started
      }
      return parsed
    } finally {
      clearTimeout(timeout)
    }
  }
}