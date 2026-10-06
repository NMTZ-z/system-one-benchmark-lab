export type AdapterMode = 'off' | 'shadow' | 'canary'

export interface AdapterConfig {
  mode?: AdapterMode
  service_url?: string
  timeout_ms?: number
  search_gate_enabled?: boolean
  model_tier_gate_enabled?: boolean
  notification_gate_enabled?: boolean
  canary_acknowledged?: boolean
  canary_web_filter_enabled?: boolean
  canary_reasoning_downgrade_enabled?: boolean
}

export interface ResolvedAdapterConfig {
  mode: AdapterMode
  effectiveMode: AdapterMode
  serviceUrl: string
  timeoutMs: number
  searchGateEnabled: boolean
  modelTierGateEnabled: boolean
  notificationGateEnabled: boolean
  canaryAcknowledged: boolean
  canaryWebFilterEnabled: boolean
  canaryReasoningDowngradeEnabled: boolean
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

export interface ModelTierDecision {
  tier: 'fast' | 'strong'
  decision_source: 'rule' | 'model'
  reason: string
  difficulty_score: number
  probability_strong: number
  confidence: number
  backend: string
  latency_ms: number
  request_id: string | null
}

export interface NotificationDecision {
  delivery: 'silent' | 'digest' | 'notify_now'
  notify_now: boolean
  decision_source: 'rule' | 'model'
  reason: string
  priority_score: number
  confidence: number
  backend: string
  latency_ms: number
  request_id: string | null
}

export interface StoredSearchDecision extends SearchDecision {
  observed_at_ms: number
}

export interface StoredModelTierDecision extends ModelTierDecision {
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

export interface AgentRequestInputLike {
  agent?: AgentLike
  turn?: unknown
  step?: unknown
}

export interface LlmCallConfigLike {
  provider?: unknown
  model?: unknown
  reasoningEffort?: unknown
  temperature?: unknown
  maxTokens?: unknown
  stop?: unknown
  [key: string]: unknown
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
