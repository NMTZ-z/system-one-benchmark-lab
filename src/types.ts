export type AdapterMode = 'off' | 'shadow' | 'canary'

export interface AdapterConfig {
  mode?: AdapterMode
  service_url?: string
  timeout_ms?: number
  search_gate_enabled?: boolean
  canary_acknowledged?: boolean
}

export interface ResolvedAdapterConfig {
  mode: AdapterMode
  effectiveMode: AdapterMode
  serviceUrl: string
  timeoutMs: number
  searchGateEnabled: boolean
  canaryAcknowledged: boolean
}

export interface SearchDecision {
  decision: 'search' | 'no_search'
  decision_source: 'rule' | 'model'
  reason: string
  probability_search: number
  backend: string
  latency_ms: number
  request_id: string | null
}

export interface StoredSearchDecision extends SearchDecision {
  observed_at_ms: number
}

export interface ContentBlockLike {
  type?: unknown
  text?: unknown
}

export interface UserMessageLike {
  role?: unknown
  content?: readonly ContentBlockLike[]
}

export interface SessionLike {
  id?: unknown
}

export interface AgentLike {
  session?: SessionLike
}

export interface PreStepInputLike {
  agent?: AgentLike
  messages?: readonly UserMessageLike[]
  turn?: unknown
  step?: unknown
}

export interface ToolExecutionLike {
  name?: unknown
  agent?: AgentLike
}

export type PreToolDecisionLike =
  | { kind: 'allow' }
  | { kind: 'deny'; reason: string }
  | { kind: 'cancel' }
  | { kind: 'ask'; reason?: string }

export interface SessionEventLike {
  type?: unknown
  data?: {
    turn?: unknown
    [key: string]: unknown
  }
}

export interface LoggerLike {
  info?: (message: string) => unknown
  warn?: (message: string) => unknown
}

export interface DshContextLike {
  logger?: LoggerLike
  on: (event: string, handler: (...args: any[]) => unknown) => unknown
}