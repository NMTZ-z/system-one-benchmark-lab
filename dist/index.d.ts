import type { AdapterConfig, DshContextLike } from './types.js';
export declare const name = "local-system-one-dsh";
export declare const version = "0.7.0";
export declare function apply(ctx: DshContextLike, inputConfig?: AdapterConfig): void;
export { ADAPTER_CONTRACT_VERSION, actionOutcome, failureActionReason, telemetryRecord, toDecisionEnvelope, } from './contract.js';
export { ModelTierGateClient, CompletionGateClient, NotificationGateClient, SearchGateClient, RetryEscalationGateClient, parseCompletionDecision, parseModelTierDecision, parseNotificationDecision, parseSearchDecision, parseRetryEscalationDecision, } from './client.js';
export { AUDITED_HARD_FAST_REASONS, AUDITED_HARD_NO_WEB_REASONS, VERIFIED_PUBLIC_WEB_TOOLS, VERIFIED_REASONING_DOWNGRADE_ROUTES, hasCanaryAuthority, hasModelTierCanaryAuthority, isVerifiedPublicWebTool, isVerifiedReasoningDowngradeRoute, resolveConfig, } from './policy.js';
export { TurnDecisionState } from './state.js';
export type * from './types.js';
