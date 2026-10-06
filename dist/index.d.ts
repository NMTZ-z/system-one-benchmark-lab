import type { AdapterConfig, DshContextLike } from './types.js';
export declare const name = "local-system-one-dsh";
export declare function apply(ctx: DshContextLike, inputConfig?: AdapterConfig): void;
export { ModelTierGateClient, NotificationGateClient, SearchGateClient, parseModelTierDecision, parseNotificationDecision, parseSearchDecision, } from './client.js';
export { AUDITED_HARD_FAST_REASONS, AUDITED_HARD_NO_WEB_REASONS, VERIFIED_PUBLIC_WEB_TOOLS, VERIFIED_REASONING_DOWNGRADE_ROUTES, hasCanaryAuthority, hasModelTierCanaryAuthority, isVerifiedPublicWebTool, isVerifiedReasoningDowngradeRoute, resolveConfig, } from './policy.js';
export { TurnDecisionState } from './state.js';
export type * from './types.js';
