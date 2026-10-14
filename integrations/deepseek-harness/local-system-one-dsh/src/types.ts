export type AdapterMode = 'off' | 'shadow' | 'canary'

export interface AdapterConfig {
  mode?: AdapterMode
  service_url?: string
  timeout_ms?: number
  search_gate_enabled?: boolean
  model_tier_gate_enabled?: boolean
  notification_gate_enabled?: boolean
  completion_gate_enabled?: boolean
  completion_loop_probe_enabled?: boolean
  retry_escalation_gate_enabled?: boolean
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
  completionGateEnabled: boolean
  completionLoopProbeEnabled: boolean
  retryEscalationGateEnabled: boolean
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

export interface CompletionDecision {
  decision: 'complete' | 'continue' | 'verify'
  decision_source: 'rule' | 'model'
  reason: string
  probability_complete: number
  probability_verify: number
  probability_continue: number
  confidence: number
  backend: string
  latency_ms: number
  request_id: string | null
}

export interface CompletionExecutionState {
  tools_used?: number
  tool_failures?: number
  tests_run?: number
  tests_passed?: number
  artifacts_created?: number
  required_checks_completed?: boolean
  required_artifact_missing?: boolean
  required_step_missing?: boolean
  blocking_failure?: boolean
  conflicting_evidence?: boolean
  verification_required?: boolean
  final_state_verified?: boolean
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

/** Structured trusted fields only. No raw tool arguments or errors. */
export interface FailureContext {
  failure: {
    category: 'timeout' | 'network' | 'rate_limit' | 'server_error' | 'auth' |
      'validation' | 'tool_error' | 'test_failure' | 'logic_failure' |
      'partial_success' | 'unknown'
    transience: 'transient' | 'permanent' | 'unknown'
    outcome_known: boolean
    http_status?: number
    retry_after_ms?: number
  }
  operation: {
    type: 'read' | 'write' | 'remote_api' | 'local_file' |
      'git_push' | 'pr_create' | 'test' | 'compute' | 'unknown'
    side_effect: 'none' | 'write' | 'external' | 'unknown'
    idempotency: 'verified' | 'non_idempotent' | 'unknown'
    side_effect_status: 'none' | 'applied' | 'not_applied' | 'partial' | 'unknown'
    verified_idempotency_key: boolean
    reversibility: 'yes' | 'no' | 'unknown'
    metadata_source: 'adapter_policy' | 'unknown'
  }
  history: {
    attempts: number
    max_attempts: number | null
    repeated_failures: number
    remaining_time_ms: number | null
    retry_budget_available: boolean
  }
  constraints: {
    requires_approval: boolean
    escalation_allowed: boolean
    escalation_budget_available: boolean
    alternative_available: boolean
  }
}
export type RetryDecisionValue =
  | 'retry_same' | 'try_alternative' | 'escalate_model'
  | 'verify_state' | 'ask_user' | 'abort'
export interface RetryEscalationDecision {
  workflow: 'retry_escalation_gate'
  decision: RetryDecisionValue
  guarded_decision: RetryDecisionValue
  raw_model_decision: RetryDecisionValue | null
  safety_override_reason: string | null
  decision_source: 'rule' | 'model'
  reason: string
  backend: string
  latency_ms: number
  confidence: number
  request_id: string | null
  advisory_only: true
}
