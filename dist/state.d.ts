import type { StoredSearchDecision } from './types.js';
export declare class TurnDecisionState {
    private readonly activeTurns;
    private readonly decisions;
    beginTurn(sessionId: string, turn: number): void;
    setDecision(sessionId: string, turn: number, decision: StoredSearchDecision): void;
    getCurrentDecision(sessionId: string): StoredSearchDecision | undefined;
    clearTurn(sessionId: string, turn: number): void;
    clearSession(sessionId: string): void;
    decisionCount(): number;
}