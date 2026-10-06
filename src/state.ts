import type { StoredModelTierDecision, StoredSearchDecision } from './types.js'

function key(sessionId: string, turn: number): string {
  return `${sessionId}:${turn}`
}

export class TurnDecisionState {
  private readonly activeTurns = new Map<string, number>()
  private readonly searchDecisions = new Map<string, StoredSearchDecision>()
  private readonly modelTierDecisions = new Map<string, StoredModelTierDecision>()

  beginTurn(sessionId: string, turn: number): void {
    this.activeTurns.set(sessionId, turn)
  }

  setSearchDecision(sessionId: string, turn: number, decision: StoredSearchDecision): void {
    this.activeTurns.set(sessionId, turn)
    this.searchDecisions.set(key(sessionId, turn), decision)
  }

  setModelTierDecision(sessionId: string, turn: number, decision: StoredModelTierDecision): void {
    this.activeTurns.set(sessionId, turn)
    this.modelTierDecisions.set(key(sessionId, turn), decision)
  }

  getCurrentSearchDecision(sessionId: string): StoredSearchDecision | undefined {
    const turn = this.activeTurns.get(sessionId)
    return turn === undefined ? undefined : this.searchDecisions.get(key(sessionId, turn))
  }

  getCurrentModelTierDecision(sessionId: string): StoredModelTierDecision | undefined {
    const turn = this.activeTurns.get(sessionId)
    return turn === undefined ? undefined : this.modelTierDecisions.get(key(sessionId, turn))
  }

  getModelTierDecision(sessionId: string, turn: number): StoredModelTierDecision | undefined {
    return this.modelTierDecisions.get(key(sessionId, turn))
  }

  // Backward-compatible Search Gate aliases retained for Phase 1 consumers/tests.
  setDecision(sessionId: string, turn: number, decision: StoredSearchDecision): void {
    this.setSearchDecision(sessionId, turn, decision)
  }

  getCurrentDecision(sessionId: string): StoredSearchDecision | undefined {
    return this.getCurrentSearchDecision(sessionId)
  }

  clearTurn(sessionId: string, turn: number): void {
    const decisionKey = key(sessionId, turn)
    this.searchDecisions.delete(decisionKey)
    this.modelTierDecisions.delete(decisionKey)
    if (this.activeTurns.get(sessionId) === turn) {
      this.activeTurns.delete(sessionId)
    }
  }

  clearSession(sessionId: string): void {
    this.activeTurns.delete(sessionId)
    for (const decisionKey of this.searchDecisions.keys()) {
      if (decisionKey.startsWith(`${sessionId}:`)) {
        this.searchDecisions.delete(decisionKey)
      }
    }
    for (const decisionKey of this.modelTierDecisions.keys()) {
      if (decisionKey.startsWith(`${sessionId}:`)) {
        this.modelTierDecisions.delete(decisionKey)
      }
    }
  }

  decisionCount(): number {
    return this.searchDecisions.size + this.modelTierDecisions.size
  }
}
