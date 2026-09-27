import { afterEach, describe, expect, it, vi } from 'vitest'
import { SearchGateClient, parseSearchDecision } from '../src/client.js'
import { apply } from '../src/index.js'
import {
  hasCanaryAuthority,
  isVerifiedPublicWebTool,
  resolveConfig,
} from '../src/policy.js'
import { TurnDecisionState } from '../src/state.js'
import type { SearchDecision } from '../src/types.js'

const hardRuleDecision: SearchDecision = {
  decision: 'no_search',
  decision_source: 'rule',
  reason: 'local_file_or_repo',
  probability_search: 0,
  backend: 'rule',
  latency_ms: 0,
  request_id: 'req-hard',
}

const modelDecision: SearchDecision = {
  decision: 'no_search',
  decision_source: 'model',
  reason: 'model_confident_local_answer',
  probability_search: 0.01,
  backend: 'ane',
  latency_ms: 42,
  request_id: 'req-model',
}

function jsonResponse(value: unknown, status = 200): Response {
  return new Response(JSON.stringify(value), {
    status,
    headers: { 'content-type': 'application/json' },
  })
}

type Handler = (...args: any[]) => unknown

class FakeContext {
  readonly handlers = new Map<string, Handler[]>()
  readonly info: string[] = []
  readonly warnings: string[] = []
  readonly logger = {
    info: (message: string) => this.info.push(message),
    warn: (message: string) => this.warnings.push(message),
  }

  on(event: string, handler: Handler): void {
    const handlers = this.handlers.get(event) ?? []
    handlers.push(handler)
    this.handlers.set(event, handlers)
  }

  one(event: string): Handler {
    const handlers = this.handlers.get(event) ?? []
    if (handlers.length !== 1) {
      throw new Error(`expected one handler for ${event}, got ${handlers.length}`)
    }
    return handlers[0]!
  }
}

function userInput(sessionId: string, turn: number, step: number, text: string) {
  return {
    agent: { session: { id: sessionId } },
    turn,
    step,
    messages: [
      {
        role: 'user',
        content: [{ type: 'text', text }],
      },
    ],
  }
}

async function enterTurn(
  ctx: FakeContext,
  sessionId: string,
  turn: number,
  text: string,
): Promise<void> {
  await ctx.one('session/event')(
    { id: sessionId },
    { type: 'turn/start', data: { turn } },
  )
  await ctx.one('agent/pre-step')(
    userInput(sessionId, turn, 1, text),
    async () => ({ kind: 'enter' }),
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('configuration and policy', () => {
  it('degrades unacknowledged canary to shadow', () => {
    const config = resolveConfig({ mode: 'canary', canary_acknowledged: false })
    expect(config.mode).toBe('canary')
    expect(config.effectiveMode).toBe('shadow')
  })

  it('activates canary only after explicit acknowledgement', () => {
    const config = resolveConfig({ mode: 'canary', canary_acknowledged: true })
    expect(config.effectiveMode).toBe('canary')
  })

  it('recognizes only audited deterministic hard no-Web decisions', () => {
    expect(hasCanaryAuthority(hardRuleDecision)).toBe(true)
    expect(hasCanaryAuthority(modelDecision)).toBe(false)
    expect(
      hasCanaryAuthority({
        ...hardRuleDecision,
        reason: 'unreviewed_reason',
      }),
    ).toBe(false)
    expect(
      hasCanaryAuthority({
        ...hardRuleDecision,
        backend: 'ane',
      }),
    ).toBe(false)
  })

  it('uses an exact verified public-Web tool allowlist', () => {
    expect(isVerifiedPublicWebTool('web_search')).toBe(true)
    expect(isVerifiedPublicWebTool('web_fetch')).toBe(true)
    expect(isVerifiedPublicWebTool('mcp__tavily__tavily_search')).toBe(true)
    expect(isVerifiedPublicWebTool('read')).toBe(false)
    expect(isVerifiedPublicWebTool('bash')).toBe(false)
    expect(isVerifiedPublicWebTool('mcp__private__search')).toBe(false)
  })
})

describe('turn-scoped state', () => {
  it('clears a decision at turn end', () => {
    const state = new TurnDecisionState()
    state.beginTurn('s1', 1)
    state.setDecision('s1', 1, { ...hardRuleDecision, observed_at_ms: 1 })
    expect(state.getCurrentDecision('s1')?.reason).toBe('local_file_or_repo')
    state.clearTurn('s1', 1)
    expect(state.getCurrentDecision('s1')).toBeUndefined()
    expect(state.decisionCount()).toBe(0)
  })
})

describe('HTTP client', () => {
  it('parses the Search Gate response contract', () => {
    expect(parseSearchDecision(hardRuleDecision)).toEqual(hardRuleDecision)
    expect(() => parseSearchDecision({ ...hardRuleDecision, decision_source: 'guess' }))
      .toThrow(/decision_source/)
  })

  it('times out without returning a decision', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((_url: string, init?: RequestInit) => new Promise((_resolve, reject) => {
        init?.signal?.addEventListener('abort', () => {
          reject(new DOMException('aborted', 'AbortError'))
        })
      })),
    )

    const client = new SearchGateClient('http://127.0.0.1:9', 5)
    await expect(client.decide('synthetic task', 'req-timeout')).rejects.toThrow()
  })
})

describe('DeepSeek Harness lifecycle integration', () => {
  it('OFF performs zero Local System One calls and zero tool mutation', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    const ctx = new FakeContext()
    apply(ctx, { mode: 'off' })

    await ctx.one('agent/pre-step')(
      userInput('s-off', 1, 1, 'synthetic'),
      async () => 'native-pre-step',
    )
    const toolResult = await ctx.one('tools/pre-execute')(
      { name: 'web_search', agent: { session: { id: 's-off' } } },
      async () => 'native-tool',
    )

    expect(fetchMock).not.toHaveBeenCalled()
    expect(toolResult).toBe('native-tool')
  })

  it('Shadow calls Search Gate once on step 1 and never mutates tools', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(hardRuleDecision))
    vi.stubGlobal('fetch', fetchMock)
    const ctx = new FakeContext()
    apply(ctx, { mode: 'shadow' })

    await enterTurn(ctx, 's-shadow', 1, 'synthetic local task')
    await ctx.one('agent/pre-step')(
      { ...userInput('s-shadow', 1, 2, ''), messages: [] },
      async () => 'continuation',
    )
    const toolResult = await ctx.one('tools/pre-execute')(
      { name: 'web_search', agent: { session: { id: 's-shadow' } } },
      async () => 'native-tool',
    )

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(toolResult).toBe('native-tool')
    expect(ctx.info.join('\n')).not.toContain('synthetic local task')
    expect(ctx.info.join('\n')).toContain('local_file_or_repo')
  })

  it('unacknowledged Canary behaves as Shadow', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(hardRuleDecision)))
    const ctx = new FakeContext()
    apply(ctx, { mode: 'canary', canary_acknowledged: false })

    await enterTurn(ctx, 's-no-ack', 1, 'synthetic local task')
    const result = await ctx.one('tools/pre-execute')(
      { name: 'web_search', agent: { session: { id: 's-no-ack' } } },
      async () => 'native-tool',
    )

    expect(result).toBe('native-tool')
    expect(ctx.warnings.join('\n')).toContain('using shadow')
  })

  it('Canary denies only verified Web/Search tools for audited hard rules', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(hardRuleDecision)))
    const ctx = new FakeContext()
    apply(ctx, { mode: 'canary', canary_acknowledged: true })

    await enterTurn(ctx, 's-canary', 1, 'synthetic local task')

    for (const name of ['web_search', 'web_fetch', 'mcp__tavily__tavily_search']) {
      const result = await ctx.one('tools/pre-execute')(
        { name, agent: { session: { id: 's-canary' } } },
        async () => 'native-tool',
      )
      expect(result).toEqual({
        kind: 'deny',
        reason: 'Local System One hard no-Web rule: local_file_or_repo',
      })
    }

    const localResult = await ctx.one('tools/pre-execute')(
      { name: 'read', agent: { session: { id: 's-canary' } } },
      async () => 'local-ok',
    )
    expect(localResult).toBe('local-ok')
  })

  it('model probability never gains Canary authority', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse({ ...modelDecision, probability_search: 0 })),
    )
    const ctx = new FakeContext()
    apply(ctx, { mode: 'canary', canary_acknowledged: true })

    await enterTurn(ctx, 's-model', 1, 'synthetic ambiguous task')
    const result = await ctx.one('tools/pre-execute')(
      { name: 'web_search', agent: { session: { id: 's-model' } } },
      async () => 'web-allowed',
    )

    expect(result).toBe('web-allowed')
  })

  it('Local System One failure is fail-open', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('service unavailable')))
    const ctx = new FakeContext()
    apply(ctx, { mode: 'canary', canary_acknowledged: true })

    await enterTurn(ctx, 's-fail', 1, 'synthetic task')
    const result = await ctx.one('tools/pre-execute')(
      { name: 'web_search', agent: { session: { id: 's-fail' } } },
      async () => 'web-allowed',
    )

    expect(result).toBe('web-allowed')
    expect(ctx.warnings.join('\n')).toContain('fail-open')
    expect(ctx.warnings.join('\n')).not.toContain('service unavailable')
  })

  it('turn/end prevents cross-turn decision leakage', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(hardRuleDecision)))
    const ctx = new FakeContext()
    apply(ctx, { mode: 'canary', canary_acknowledged: true })

    await enterTurn(ctx, 's-multi', 1, 'synthetic turn one')
    const denied = await ctx.one('tools/pre-execute')(
      { name: 'web_search', agent: { session: { id: 's-multi' } } },
      async () => 'web-allowed',
    )
    expect(denied).toMatchObject({ kind: 'deny' })

    await ctx.one('session/event')(
      { id: 's-multi' },
      { type: 'turn/end', data: { turn: 1 } },
    )
    await ctx.one('session/event')(
      { id: 's-multi' },
      { type: 'turn/start', data: { turn: 2 } },
    )

    const turnTwo = await ctx.one('tools/pre-execute')(
      { name: 'web_search', agent: { session: { id: 's-multi' } } },
      async () => 'web-allowed',
    )
    expect(turnTwo).toBe('web-allowed')
  })
})