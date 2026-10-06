import type { StoredModelTierDecision, StoredSearchDecision } from './types.js';
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
