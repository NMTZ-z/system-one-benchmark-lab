import type { StoredSearchDecision } from './types.js'

function key(sessionId: string, turn: number): string {
  return `${sessionId}:${turn}`
}

export class TurnDecisionState {
  private readonly activeTurns = new Map<string, number>()
  private readonly decisions = new Map<string, StoredSearchDecision>()

  beginTurn(sessionId: string, turn: number): void {
    this.activeTurns.set(sessionId, turn)
  }

  setDecision(sessionId: string, turn: number, decision: StoredSearchDecision): void {
    this.activeTurns.set(sessionId, turn)
    this.decisions.set(key(sessionId, turn), decision)
  }

  getCurrentDecision(sessionId: string): StoredSearchDecision | undefined {
    const turn = this.activeTurns.get(sessionId)
    return turn === undefined ? undefined : this.decisions.get(key(sessionId, turn))
  }

  clearTurn(sessionId: string, turn: number): void {
    this.decisions.delete(key(sessionId, turn))
    if (this.activeTurns.get(sessionId) === turn) {
      this.activeTurns.delete(sessionId)
    }
  }

  clearSession(sessionId: string): void {
    this.activeTurns.delete(sessionId)
    for (const decisionKey of this.decisions.keys()) {
      if (decisionKey.startsWith(`${sessionId}:`)) {
        this.decisions.delete(decisionKey)
      }
    }
  }

  decisionCount(): number {
    return this.decisions.size
  }
}