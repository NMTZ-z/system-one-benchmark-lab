import type { StoredModelTierDecision, StoredSearchDecision } from './types.js';
/** Injective, session-scoped prefix for untrusted opaque session IDs.
 *
 * Length-prefixing prevents a session ID such as "job" from matching
 * "job:child" during prefix-based map cleanup. Keep this shared between
 * Retry, Completion, Notification, Search and Model Tier state.
 */
export declare function sessionKeyPrefix(sessionId: string): string;
export declare function turnKey(sessionId: string, turn: number): string;
export declare class TurnDecisionState {
    private readonly activeTurns;
    private readonly searchDecisions;
    private readonly modelTierDecisions;
    beginTurn(sessionId: string, turn: number): void;
    setSearchDecision(sessionId: string, turn: number, decision: StoredSearchDecision): void;
    setModelTierDecision(sessionId: string, turn: number, decision: StoredModelTierDecision): void;
    getCurrentSearchDecision(sessionId: string): StoredSearchDecision | undefined;
    getCurrentModelTierDecision(sessionId: string): StoredModelTierDecision | undefined;
    getModelTierDecision(sessionId: string, turn: number): StoredModelTierDecision | undefined;
    setDecision(sessionId: string, turn: number, decision: StoredSearchDecision): void;
    getCurrentDecision(sessionId: string): StoredSearchDecision | undefined;
    clearTurn(sessionId: string, turn: number): void;
    clearSession(sessionId: string): void;
    decisionCount(): number;
}
