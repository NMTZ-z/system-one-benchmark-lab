/** Phase 8C: frozen upstream tool identity policy. Never inspect error text or arguments. */
import type { FailureContext, SessionEventLike } from './types.js'

type Operation = FailureContext['operation']
type Category = FailureContext['failure']['category']

/** Only the exact tool names validated against DSH tool/call events. Unknown tools are unsupported. */
const READ_TOOLS = new Set(['read', 'web_fetch', 'web_search', 'mcp__tavily__tavily_search'])
const FILE_WRITE_TOOLS = new Set(['write', 'edit'])

export function operationFromToolName(name: string): Operation | null {
  if (READ_TOOLS.has(name)) return {
    type: 'read', side_effect: 'none', idempotency: 'verified',
    side_effect_status: 'none', verified_idempotency_key: false,
    reversibility: 'yes', metadata_source: 'adapter_policy',
  }
  if (FILE_WRITE_TOOLS.has(name)) return {
    type: 'local_file', side_effect: 'write', idempotency: 'unknown',
    side_effect_status: 'unknown', verified_idempotency_key: false,
    reversibility: 'unknown', metadata_source: 'adapter_policy',
  }
  return null
}

export function resultCallId(event: SessionEventLike): string | null {
  const message = event.data?.message
  if (typeof message !== 'object' || message === null) return null
  const source = (message as Record<string, unknown>).source
  if (typeof source !== 'object' || source === null) return null
  const id = (source as Record<string, unknown>).callId
  return typeof id === 'string' && id.length > 0 && id.length <= 128 ? id : null
}

function classifyErrorCode(value: unknown): { category: Category; transience: FailureContext['failure']['transience']; http_status?: number } {
  if (typeof value !== 'string' || value.length > 64) {
    return { category: 'unknown', transience: 'unknown' }
  }
  if (['ETIMEDOUT', 'ERR_TIMEOUT'].includes(value)) return {
    category: 'timeout', transience: 'transient',
  }
  if (['ECONNRESET', 'EAI_AGAIN', 'ENOTFOUND'].includes(value)) return {
    category: 'network', transience: 'transient',
  }
  if (['HTTP_401','HTTP_403'].includes(value)) return {
    category: 'auth', transience: 'permanent',
    http_status: Number(value.slice(5)),
  }
  if (value === 'HTTP_429') return {
    category: 'rate_limit', transience: 'transient', http_status: 429,
  }
  if (['HTTP_500','HTTP_502','HTTP_503','HTTP_504'].includes(value)) return {
    category: 'server_error', transience: 'transient', http_status: Number(value.slice(5)),
  }
  if (['INVALID_ARGUMENTS','VALIDATION_ERROR'].includes(value)) return {
    category: 'validation', transience: 'permanent',
  }
  return { category: 'tool_error', transience: 'unknown' }
}

/** Accept only structured DSH failure, never infer a failure from content text. */
export function failureFromToolResult(
  event: SessionEventLike,
  operation: Operation,
): FailureContext | null {
  const msg = event.data?.message
  if (typeof msg !== 'object' || msg === null ||
      (msg as Record<string, unknown>).isError !== true) return null
  const error = event.data?.error
  const code = typeof error === 'object' && error !== null
    ? (error as Record<string, unknown>).code
    : null
  const identified = classifyErrorCode(code)
  // No verified attempt ceiling, native retry budget or remaining time is passed
  // at this hook. Do not make one up to elicit an automatic retry recommendation.
  return {
    failure: {
      ...identified, outcome_known: false,
    },
    operation,
    history: {
      attempts: 0, max_attempts: null, repeated_failures: 0,
      remaining_time_ms: null, retry_budget_available: false,
    },
    constraints: {
      requires_approval: false, escalation_allowed: false,
      escalation_budget_available: false, alternative_available: false,
    },
  }
}
