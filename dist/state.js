function key(sessionId, turn) {
    return `${sessionId}:${turn}`;
}
export class TurnDecisionState {
    activeTurns = new Map();
    searchDecisions = new Map();
    modelTierDecisions = new Map();
    beginTurn(sessionId, turn) {
        this.activeTurns.set(sessionId, turn);
    }
    setSearchDecision(sessionId, turn, decision) {
        this.activeTurns.set(sessionId, turn);
        this.searchDecisions.set(key(sessionId, turn), decision);
    }
    setModelTierDecision(sessionId, turn, decision) {
        this.activeTurns.set(sessionId, turn);
        this.modelTierDecisions.set(key(sessionId, turn), decision);
    }
    getCurrentSearchDecision(sessionId) {
        const turn = this.activeTurns.get(sessionId);
        return turn === undefined ? undefined : this.searchDecisions.get(key(sessionId, turn));
    }
    getCurrentModelTierDecision(sessionId) {
        const turn = this.activeTurns.get(sessionId);
        return turn === undefined ? undefined : this.modelTierDecisions.get(key(sessionId, turn));
    }
    getModelTierDecision(sessionId, turn) {
        return this.modelTierDecisions.get(key(sessionId, turn));
    }
    // Backward-compatible Search Gate aliases retained for Phase 1 consumers/tests.
    setDecision(sessionId, turn, decision) {
        this.setSearchDecision(sessionId, turn, decision);
    }
    getCurrentDecision(sessionId) {
        return this.getCurrentSearchDecision(sessionId);
    }
    clearTurn(sessionId, turn) {
        const decisionKey = key(sessionId, turn);
        this.searchDecisions.delete(decisionKey);
        this.modelTierDecisions.delete(decisionKey);
        if (this.activeTurns.get(sessionId) === turn) {
            this.activeTurns.delete(sessionId);
        }
    }
    clearSession(sessionId) {
        this.activeTurns.delete(sessionId);
        for (const decisionKey of this.searchDecisions.keys()) {
            if (decisionKey.startsWith(`${sessionId}:`)) {
                this.searchDecisions.delete(decisionKey);
            }
        }
        for (const decisionKey of this.modelTierDecisions.keys()) {
            if (decisionKey.startsWith(`${sessionId}:`)) {
                this.modelTierDecisions.delete(decisionKey);
            }
        }
    }
    decisionCount() {
        return this.searchDecisions.size + this.modelTierDecisions.size;
    }
}
//# sourceMappingURL=state.js.map