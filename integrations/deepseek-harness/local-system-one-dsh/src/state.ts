import type { StoredModelTierDecision, StoredSearchDecision } from './types.js'

/** Injective, session-scoped prefix for untrusted opaque session IDs.
 *
 * Length-prefixing prevents a session ID such as "job" from matching
 * "job:child" during prefix-based map cleanup. Keep this shared between
 * Retry, Completion, Notification, Search and Model Tier state.
 */
export function sessionKeyPrefix(sessionId: string): string {
  return `${sessionId.length}:${sessionId}:`
}

export function turnKey(sessionId: string, turn: number): string {
  return `${sessionKeyPrefix(sessionId)}${turn}`
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
    this.searchDecisions.set(turnKey(sessionId, turn), decision)
  }

  setModelTierDecision(sessionId: string, turn: number, decision: StoredModelTierDecision): void {
    this.activeTurns.set(sessionId, turn)
    this.modelTierDecisions.set(turnKey(sessionId, turn), decision)
  }

  getCurrentSearchDecision(sessionId: string): StoredSearchDecision | undefined {
    const turn = this.activeTurns.get(sessionId)
    return turn === undefined ? undefined : this.searchDecisions.get(turnKey(sessionId, turn))
  }

  getCurrentModelTierDecision(sessionId: string): StoredModelTierDecision | undefined {
    const turn = this.activeTurns.get(sessionId)
    return turn === undefined ? undefined : this.modelTierDecisions.get(turnKey(sessionId, turn))
  }

  getModelTierDecision(sessionId: string, turn: number): StoredModelTierDecision | undefined {
    return this.modelTierDecisions.get(turnKey(sessionId, turn))
  }

  // Backward-compatible Search Gate aliases retained for Phase 1 consumers/tests.
  setDecision(sessionId: string, turn: number, decision: StoredSearchDecision): void {
    this.setSearchDecision(sessionId, turn, decision)
  }

  getCurrentDecision(sessionId: string): StoredSearchDecision | undefined {
    return this.getCurrentSearchDecision(sessionId)
  }

  clearTurn(sessionId: string, turn: number): void {
    const decisionKey = turnKey(sessionId, turn)
    this.searchDecisions.delete(decisionKey)
    this.modelTierDecisions.delete(decisionKey)
    if (this.activeTurns.get(sessionId) === turn) {
      this.activeTurns.delete(sessionId)
    }
  }

  clearSession(sessionId: string): void {
    this.activeTurns.delete(sessionId)
    for (const decisionKey of this.searchDecisions.keys()) {
      if (decisionKey.startsWith(sessionKeyPrefix(sessionId))) {
        this.searchDecisions.delete(decisionKey)
      }
    }
    for (const decisionKey of this.modelTierDecisions.keys()) {
      if (decisionKey.startsWith(sessionKeyPrefix(sessionId))) {
        this.modelTierDecisions.delete(decisionKey)
      }
    }
  }

  decisionCount(): number {
    return this.searchDecisions.size + this.modelTierDecisions.size
  }
}
