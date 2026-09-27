function key(sessionId, turn) {
    return `${sessionId}:${turn}`;
}
export class TurnDecisionState {
    activeTurns = new Map();
    decisions = new Map();
    beginTurn(sessionId, turn) {
        this.activeTurns.set(sessionId, turn);
    }
    setDecision(sessionId, turn, decision) {
        this.activeTurns.set(sessionId, turn);
        this.decisions.set(key(sessionId, turn), decision);
    }
    getCurrentDecision(sessionId) {
        const turn = this.activeTurns.get(sessionId);
        return turn === undefined ? undefined : this.decisions.get(key(sessionId, turn));
    }
    clearTurn(sessionId, turn) {
        this.decisions.delete(key(sessionId, turn));
        if (this.activeTurns.get(sessionId) === turn) {
            this.activeTurns.delete(sessionId);
        }
    }
    clearSession(sessionId) {
        this.activeTurns.delete(sessionId);
        for (const decisionKey of this.decisions.keys()) {
            if (decisionKey.startsWith(`${sessionId}:`)) {
                this.decisions.delete(decisionKey);
            }
        }
    }
    decisionCount() {
        return this.decisions.size;
    }
}
//# sourceMappingURL=state.js.map