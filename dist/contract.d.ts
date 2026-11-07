import type { AdapterMode, CompletionDecision, ModelTierDecision, NotificationDecision, SearchDecision, RetryEscalationDecision } from './types.js';
export declare const ADAPTER_CONTRACT_VERSION = "1.0";
export type GateName = 'search' | 'model_tier' | 'notification' | 'completion' | 'retry_escalation';
export type ActionStatus = 'observed' | 'applied' | 'skipped' | 'failed_open' | 'unsupported';
export interface ActionOutcome {
    status: ActionStatus;
    reason: string;
}
export interface DecisionEnvelope {
    adapter_contract_version: typeof ADAPTER_CONTRACT_VERSION;
    request_id: string | null;
    gate: GateName;
    decision: Record<string, unknown>;
    decision_source: 'rule' | 'model';
    reason: string;
    backend: string;
    latency_ms: number;
    confidence?: number;
}
export type RuntimeDecision = SearchDecision | ModelTierDecision | NotificationDecision | CompletionDecision | RetryEscalationDecision;
export declare function toDecisionEnvelope(gate: 'search', decision: SearchDecision): DecisionEnvelope;
export declare function toDecisionEnvelope(gate: 'model_tier', decision: ModelTierDecision): DecisionEnvelope;
export declare function toDecisionEnvelope(gate: 'notification', decision: NotificationDecision): DecisionEnvelope;
export declare function toDecisionEnvelope(gate: 'completion', decision: CompletionDecision): DecisionEnvelope;
export declare function toDecisionEnvelope(gate: 'retry_escalation', decision: RetryEscalationDecision): DecisionEnvelope;
export declare function actionOutcome(status: ActionStatus, reason: string): ActionOutcome;
export declare function telemetryRecord(adapterVersion: string, mode: AdapterMode, envelope: DecisionEnvelope, outcome: ActionOutcome, extra?: Record<string, unknown>): Record<string, unknown>;
export declare function failureActionReason(error: unknown): string;
