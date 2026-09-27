import type { AdapterConfig, ResolvedAdapterConfig, SearchDecision } from './types.js';
export declare const AUDITED_HARD_NO_WEB_REASONS: Set<string>;
export declare const VERIFIED_PUBLIC_WEB_TOOLS: Set<string>;
export declare function resolveConfig(input?: AdapterConfig): ResolvedAdapterConfig;
export declare function isVerifiedPublicWebTool(name: string): boolean;
export declare function hasCanaryAuthority(decision: SearchDecision): boolean;