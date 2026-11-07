/** Injective, session-scoped prefix for untrusted opaque session IDs.
 *
 * Length-prefixing prevents a session ID such as "job" from matching
 * "job:child" during prefix-based map cleanup. Keep this shared between
 * Retry, Completion, Notification, Search and Model Tier state.
 */
export function sessionKeyPrefix(sessionId) {
    return `${sessionId.length}:${sessionId}:`;
}
export function turnKey(sessionId, turn) {
    return `${sessionKeyPrefix(sessionId)}${turn}`;
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
        this.searchDecisions.set(turnKey(sessionId, turn), decision);
    }
    setModelTierDecision(sessionId, turn, decision) {
        this.activeTurns.set(sessionId, turn);
        this.modelTierDecisions.set(turnKey(sessionId, turn), decision);
    }
    getCurrentSearchDecision(sessionId) {
        const turn = this.activeTurns.get(sessionId);
        return turn === undefined ? undefined : this.searchDecisions.get(turnKey(sessionId, turn));
    }
    getCurrentModelTierDecision(sessionId) {
        const turn = this.activeTurns.get(sessionId);
        return turn === undefined ? undefined : this.modelTierDecisions.get(turnKey(sessionId, turn));
    }
    getModelTierDecision(sessionId, turn) {
        return this.modelTierDecisions.get(turnKey(sessionId, turn));
    }
    // Backward-compatible Search Gate aliases retained for Phase 1 consumers/tests.
    setDecision(sessionId, turn, decision) {
        this.setSearchDecision(sessionId, turn, decision);
    }
    getCurrentDecision(sessionId) {
        return this.getCurrentSearchDecision(sessionId);
    }
    clearTurn(sessionId, turn) {
        const decisionKey = turnKey(sessionId, turn);
        this.searchDecisions.delete(decisionKey);
        this.modelTierDecisions.delete(decisionKey);
        if (this.activeTurns.get(sessionId) === turn) {
            this.activeTurns.delete(sessionId);
        }
    }
    clearSession(sessionId) {
        this.activeTurns.delete(sessionId);
        for (const decisionKey of this.searchDecisions.keys()) {
            if (decisionKey.startsWith(sessionKeyPrefix(sessionId))) {
                this.searchDecisions.delete(decisionKey);
            }
        }
        for (const decisionKey of this.modelTierDecisions.keys()) {
            if (decisionKey.startsWith(sessionKeyPrefix(sessionId))) {
                this.modelTierDecisions.delete(decisionKey);
            }
        }
    }
    decisionCount() {
        return this.searchDecisions.size + this.modelTierDecisions.size;
    }
}
//# sourceMappingURL=state.js.map