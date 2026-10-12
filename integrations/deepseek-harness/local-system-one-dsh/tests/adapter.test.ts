import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  ModelTierGateClient,
  CompletionGateClient,
  NotificationGateClient,
  SearchGateClient,
  parseModelTierDecision,
  parseCompletionDecision,
  parseNotificationDecision,
  parseSearchDecision,
} from '../src/client.js'
import {
  ADAPTER_CONTRACT_VERSION,
  failureActionReason,
  toDecisionEnvelope,
} from '../src/contract.js'
import { apply } from '../src/index.js'
import {
  hasCanaryAuthority,
  hasModelTierCanaryAuthority,
  isVerifiedPublicWebTool,
  isVerifiedReasoningDowngradeRoute,
  resolveConfig,
} from '../src/policy.js'
import { TurnDecisionState } from '../src/state.js'
import type {
  CompletionDecision,
  ModelTierDecision,
  NotificationDecision,
  SearchDecision,
} from '../src/types.js'

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

const hardFastDecision: ModelTierDecision = {
  tier: 'fast',
  decision_source: 'rule',
  reason: 'bounded_transform',
  difficulty_score: 0,
  probability_strong: 0,
  confidence: 1,
  backend: 'rule',
  latency_ms: 0,
  request_id: 'req-fast',
}

const modelFastDecision: ModelTierDecision = {
  tier: 'fast',
  decision_source: 'model',
  reason: 'model_complexity_fast_sufficient',
  difficulty_score: 0.7,
  probability_strong: 0.06,
  confidence: 0.88,
  backend: 'ane',
  latency_ms: 33,
  request_id: 'req-model-fast',
}

const notificationDecision: NotificationDecision = {
  delivery: 'digest',
  notify_now: false,
  decision_source: 'model',
  reason: 'model_priority_digest',
  priority_score: 2,
  confidence: 0.8,
  backend: 'mlx',
  latency_ms: 12,
  request_id: 'req-notify',
}

const completionDecision: CompletionDecision = {
  decision: 'complete',
  decision_source: 'model',
  reason: 'model_complete',
  probability_complete: 0.9,
  probability_verify: 0.08,
  probability_continue: 0.02,
  confidence: 0.9,
  backend: 'mlx',
  latency_ms: 10,
  request_id: 'req-complete',
}

function jsonResponse(value: unknown, status = 200): Response {
  return new Response(JSON.stringify(value), {
    status,
    headers: { 'content-type': 'application/json' },
  })
}

function gateFetch(
  search: unknown = hardRuleDecision,
  modelTier: unknown = hardFastDecision,
  notification: unknown = notificationDecision,
  completion: unknown = completionDecision,
) {
  return vi.fn((url: string) => {
    if (url.endsWith('/v1/workflows/search-gate')) {
      return Promise.resolve(jsonResponse(search))
    }
    if (url.endsWith('/v1/workflows/model-tier-gate')) {
      return Promise.resolve(jsonResponse(modelTier))
    }
    if (url.endsWith('/v1/workflows/notification-gate')) {
      return Promise.resolve(jsonResponse(notification))
    }
    if (url.endsWith('/v1/workflows/completion-gate')) {
      return Promise.resolve(jsonResponse(completion))
    }
    return Promise.reject(new Error('unexpected URL'))
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

  count(event: string): number {
    return (this.handlers.get(event) ?? []).length
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

  it('defaults both gates on while keeping reasoning mutation off', () => {
    const config = resolveConfig({ mode: 'shadow' })
    expect(config.searchGateEnabled).toBe(true)
    expect(config.modelTierGateEnabled).toBe(true)
    expect(config.notificationGateEnabled).toBe(true)
    expect(config.completionGateEnabled).toBe(true)
    expect(config.canaryWebFilterEnabled).toBe(true)
    expect(config.canaryReasoningDowngradeEnabled).toBe(false)
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

  it('recognizes only audited deterministic hard-fast Model Tier decisions', () => {
    expect(hasModelTierCanaryAuthority(hardFastDecision)).toBe(true)
    expect(hasModelTierCanaryAuthority(modelFastDecision)).toBe(false)
    expect(
      hasModelTierCanaryAuthority({ ...hardFastDecision, reason: 'unreviewed_fast' }),
    ).toBe(false)
    expect(
      hasModelTierCanaryAuthority({ ...hardFastDecision, backend: 'ane' }),
    ).toBe(false)
  })

  it('uses exact provider/model allowlists for reasoning downgrade', () => {
    expect(isVerifiedReasoningDowngradeRoute('nova', 'deepseek-v4-flash')).toBe(true)
    expect(isVerifiedReasoningDowngradeRoute('stepfun', 'step-5-preview')).toBe(true)
    expect(isVerifiedReasoningDowngradeRoute('stepfun', 'step-5')).toBe(false)
    expect(isVerifiedReasoningDowngradeRoute('other', 'step-5-preview')).toBe(false)
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
  it('clears Search and Model Tier decisions at turn end', () => {
    const state = new TurnDecisionState()
    state.beginTurn('s1', 1)
    state.setSearchDecision('s1', 1, { ...hardRuleDecision, observed_at_ms: 1 })
    state.setModelTierDecision('s1', 1, { ...hardFastDecision, observed_at_ms: 1 })
    expect(state.getCurrentSearchDecision('s1')?.reason).toBe('local_file_or_repo')
    expect(state.getCurrentModelTierDecision('s1')?.tier).toBe('fast')
    expect(state.decisionCount()).toBe(2)
    state.clearTurn('s1', 1)
    expect(state.getCurrentSearchDecision('s1')).toBeUndefined()
    expect(state.getCurrentModelTierDecision('s1')).toBeUndefined()
    expect(state.decisionCount()).toBe(0)
  })
})

describe('HTTP clients', () => {
  it('normalizes Search and Model Tier into the same versioned adapter contract', () => {
    const search = toDecisionEnvelope('search', hardRuleDecision)
    const tier = toDecisionEnvelope('model_tier', hardFastDecision)
    expect(search.adapter_contract_version).toBe(ADAPTER_CONTRACT_VERSION)
    expect(tier.adapter_contract_version).toBe(ADAPTER_CONTRACT_VERSION)
    expect(search.decision).toEqual({ value: 'no_search', probability_search: 0 })
    expect(tier.decision).toEqual({
      value: 'fast',
      difficulty_score: 0,
      probability_strong: 0,
    })
  })

  it('classifies fail-open reasons without exposing error text', () => {
    expect(failureActionReason(new DOMException('aborted', 'AbortError'))).toBe('runtime_timeout')
    expect(failureActionReason(new Error('/search-gate HTTP 503'))).toBe('runtime_http_error')
    expect(failureActionReason(new Error('invalid search-gate response field: decision')))
      .toBe('malformed_response')
  })

  it('parses the Search Gate response contract', () => {
    expect(parseSearchDecision(hardRuleDecision)).toEqual(hardRuleDecision)
    expect(() => parseSearchDecision({ ...hardRuleDecision, decision_source: 'guess' }))
      .toThrow(/decision_source/)
  })

  it('parses the Model Tier response contract', () => {
    expect(parseModelTierDecision(hardFastDecision)).toEqual(hardFastDecision)
    expect(() => parseModelTierDecision({ ...hardFastDecision, tier: 'cheap' }))
      .toThrow(/tier/)
    expect(() => parseModelTierDecision({ ...hardFastDecision, probability_strong: 2 }))
      .toThrow(/probability_strong/)
  })

  it('parses the Notification Gate response contract', () => {
    expect(parseNotificationDecision(notificationDecision)).toEqual(notificationDecision)
    expect(() => parseNotificationDecision({ ...notificationDecision, delivery: 'later' }))
      .toThrow(/delivery/)
    expect(() => parseNotificationDecision({ ...notificationDecision, priority_score: 9 }))
      .toThrow(/priority_score/)
  })

  it('parses and normalizes the Completion Gate response contract', () => {
    expect(parseCompletionDecision(completionDecision)).toEqual(completionDecision)
    expect(toDecisionEnvelope('completion', completionDecision).decision).toEqual({
      value: 'complete',
      probability_complete: 0.9,
      probability_verify: 0.08,
      probability_continue: 0.02,
    })
    expect(() => parseCompletionDecision({ ...completionDecision, decision: 'stop' }))
      .toThrow(/decision/)
  })

  it('times out without returning Search or Model Tier decisions', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((_url: string, init?: RequestInit) => new Promise((_resolve, reject) => {
        init?.signal?.addEventListener('abort', () => {
          reject(new DOMException('aborted', 'AbortError'))
        })
      })),
    )

    const search = new SearchGateClient('http://127.0.0.1:9', 5)
    const tier = new ModelTierGateClient('http://127.0.0.1:9', 5)
    const notification = new NotificationGateClient('http://127.0.0.1:9', 5)
    const completion = new CompletionGateClient('http://127.0.0.1:9', 5)
    await expect(search.decide('synthetic task', 'req-timeout')).rejects.toThrow()
    await expect(tier.decide('synthetic task', 'req-timeout')).rejects.toThrow()
    await expect(notification.decide('event', 'req-timeout')).rejects.toThrow()
    await expect(completion.decide('task', 'result', {}, 'req-timeout')).rejects.toThrow()
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
    expect(ctx.count('agent/request')).toBe(0)
  })

  it('Shadow observes Search + Model Tier once on step 1 and never mutates tools', async () => {
    const fetchMock = gateFetch()
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

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(fetchMock.mock.calls.map(call => String(call[0]))).toEqual([
      'http://127.0.0.1:8787/v1/workflows/search-gate',
      'http://127.0.0.1:8787/v1/workflows/model-tier-gate',
    ])
    expect(toolResult).toBe('native-tool')
    expect(ctx.info.join('\n')).not.toContain('synthetic local task')
    expect(ctx.info.join('\n')).toContain('local_file_or_repo')
    expect(ctx.info.join('\n')).toContain('bounded_transform')
    expect(ctx.count('agent/request')).toBe(0)
  })

  it('Search Gate can be disabled without disabling Model Tier Gate', async () => {
    const fetchMock = gateFetch()
    vi.stubGlobal('fetch', fetchMock)
    const ctx = new FakeContext()
    apply(ctx, {
      mode: 'shadow',
      search_gate_enabled: false,
      model_tier_gate_enabled: true,
    })

    await enterTurn(ctx, 's-tier-only', 1, 'rewrite: hello')
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(String(fetchMock.mock.calls[0]![0])).toContain('/model-tier-gate')
    expect(ctx.info.join('\n')).toContain('"gate":"model_tier"')
  })

  it('Model Tier Gate can be disabled without disabling Search Gate', async () => {
    const fetchMock = gateFetch()
    vi.stubGlobal('fetch', fetchMock)
    const ctx = new FakeContext()
    apply(ctx, {
      mode: 'shadow',
      search_gate_enabled: true,
      model_tier_gate_enabled: false,
    })

    await enterTurn(ctx, 's-search-only', 1, 'local README task')
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(String(fetchMock.mock.calls[0]![0])).toContain('/search-gate')
    expect(ctx.info.join('\n')).toContain('"gate":"search"')
  })

  it('one gate failing does not suppress the other gate', async () => {
    const fetchMock = vi.fn((url: string) => {
      if (url.endsWith('/search-gate')) return Promise.reject(new Error('search unavailable'))
      return Promise.resolve(jsonResponse(hardFastDecision))
    })
    vi.stubGlobal('fetch', fetchMock)
    const ctx = new FakeContext()
    apply(ctx, { mode: 'shadow' })

    await enterTurn(ctx, 's-independent-failure', 1, 'rewrite: hello')
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(ctx.warnings.join('\n')).toContain('search gate unavailable')
    expect(ctx.info.join('\n')).toContain('bounded_transform')
  })

  it('Notification Shadow evaluates the final assistant event at turn end without logging raw text', async () => {
    const fetchMock = gateFetch()
    vi.stubGlobal('fetch', fetchMock)
    const ctx = new FakeContext()
    apply(ctx, { mode: 'shadow', completion_gate_enabled: false })
    const raw = 'Deployment finished; review the result when convenient.'

    await enterTurn(ctx, 's-notify', 1, 'deploy the service')
    ctx.one('session/event')(
      { id: 's-notify' },
      {
        type: 'assistant/message',
        data: { turn: 1, step: 1, message: { content: [{ type: 'text', text: raw }] } },
      },
    )
    ctx.one('session/event')(
      { id: 's-notify' },
      { type: 'turn/end', data: { turn: 1, reason: { kind: 'completed' } } },
    )
    await new Promise(resolve => setTimeout(resolve, 0))

    expect(fetchMock).toHaveBeenCalledTimes(3)
    const notifyCall = fetchMock.mock.calls.find(call => String(call[0]).endsWith('/notification-gate'))
    expect(notifyCall).toBeDefined()
    const body = JSON.parse(String((notifyCall![1] as RequestInit).body))
    expect(body.event).toBe(raw)
    expect(body.blocking_failure).toBe(false)
    expect(ctx.info.join('\n')).toContain('"gate":"notification"')
    expect(ctx.info.join('\n')).not.toContain(raw)
  })

  it('Notification Gate can be disabled independently', async () => {
    const fetchMock = gateFetch()
    vi.stubGlobal('fetch', fetchMock)
    const ctx = new FakeContext()
    apply(ctx, {
      mode: 'shadow',
      notification_gate_enabled: false,
      completion_gate_enabled: false,
    })
    await enterTurn(ctx, 's-notify-off', 1, 'task')
    ctx.one('session/event')(
      { id: 's-notify-off' },
      { type: 'assistant/message', data: { turn: 1, step: 1, message: { content: [{ type: 'text', text: 'done' }] } } },
    )
    ctx.one('session/event')(
      { id: 's-notify-off' },
      { type: 'turn/end', data: { turn: 1, reason: { kind: 'completed' } } },
    )
    await new Promise(resolve => setTimeout(resolve, 0))
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(fetchMock.mock.calls.every(call => !String(call[0]).endsWith('/notification-gate'))).toBe(true)
  })

  it('Notification Shadow fails open on service errors', async () => {
    const fetchMock = vi.fn((url: string) => {
      if (url.endsWith('/search-gate')) return Promise.resolve(jsonResponse(hardRuleDecision))
      if (url.endsWith('/model-tier-gate')) return Promise.resolve(jsonResponse(hardFastDecision))
      return Promise.reject(new Error('notification unavailable'))
    })
    vi.stubGlobal('fetch', fetchMock)
    const ctx = new FakeContext()
    apply(ctx, { mode: 'shadow', completion_gate_enabled: false })
    await enterTurn(ctx, 's-notify-fail', 1, 'task')
    ctx.one('session/event')(
      { id: 's-notify-fail' },
      { type: 'assistant/message', data: { turn: 1, step: 1, message: { content: [{ type: 'text', text: 'result' }] } } },
    )
    ctx.one('session/event')(
      { id: 's-notify-fail' },
      { type: 'turn/end', data: { turn: 1, reason: { kind: 'completed' } } },
    )
    await new Promise(resolve => setTimeout(resolve, 0))
    expect(ctx.warnings.join('\n')).toContain('notification gate unavailable')
    expect(ctx.warnings.join('\n')).not.toContain('notification unavailable')
  })

  it('Completion Shadow observes turn/end once, includes bounded state, and never mutates', async () => {
    const fetchMock = gateFetch()
    vi.stubGlobal('fetch', fetchMock)
    const ctx = new FakeContext()
    apply(ctx, {
      mode: 'shadow',
      search_gate_enabled: false,
      model_tier_gate_enabled: false,
      notification_gate_enabled: false,
      completion_gate_enabled: true,
    })
    const task = 'Create the artifact and validate it.'
    const result = 'Artifact created and checks passed.'
    await enterTurn(ctx, 's-completion', 1, task)
    await ctx.one('session/event')(
      { id: 's-completion' },
      { type: 'tool/result', data: { turn: 1, step: 1, message: { isError: false } } },
    )
    await ctx.one('session/event')(
      { id: 's-completion' },
      { type: 'assistant/message', data: { turn: 1, step: 1, message: { content: [{ type: 'text', text: result }] } } },
    )
    await ctx.one('session/event')(
      { id: 's-completion' },
      { type: 'turn/end', data: { turn: 1, reason: { kind: 'completed' } } },
    )
    await new Promise(resolve => setTimeout(resolve, 0))

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const call = fetchMock.mock.calls[0]!
    expect(String(call[0])).toContain('/completion-gate')
    const body = JSON.parse(String((call[1] as RequestInit).body))
    expect(body.task).toBe(task)
    expect(body.current_result).toBe(result)
    expect(body.execution_state).toEqual({
      tools_used: 1,
      tool_failures: 0,
      blocking_failure: false,
      required_step_missing: false,
    })
    expect(ctx.info.join('\n')).toContain('"gate":"completion"')
    expect(ctx.info.join('\n')).toContain('"action_status":"observed"')
    expect(ctx.info.join('\n')).not.toContain(task)
    expect(ctx.info.join('\n')).not.toContain(result)
    expect(ctx.count('agent/request')).toBe(0)
  })

  it('Completion Shadow fails open when the runtime is dead', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('dead completion runtime')))
    const ctx = new FakeContext()
    apply(ctx, {
      mode: 'shadow',
      search_gate_enabled: false,
      model_tier_gate_enabled: false,
      notification_gate_enabled: false,
      completion_gate_enabled: true,
    })
    await enterTurn(ctx, 's-completion-dead', 1, 'task')
    await ctx.one('session/event')(
      { id: 's-completion-dead' },
      { type: 'assistant/message', data: { turn: 1, step: 1, message: { content: [{ type: 'text', text: 'result' }] } } },
    )
    await ctx.one('session/event')(
      { id: 's-completion-dead' },
      { type: 'turn/end', data: { turn: 1, reason: { kind: 'completed' } } },
    )
    await new Promise(resolve => setTimeout(resolve, 0))
    expect(ctx.warnings.join('\n')).toContain('completion gate unavailable')
    expect(ctx.warnings.join('\n')).not.toContain('dead completion runtime')
    expect(ctx.info.join('\n')).toContain('"gate":"completion"')
    expect(ctx.info.join('\n')).toContain('"action_status":"failed_open"')
    expect(ctx.info.join('\n')).toContain('"stage":"turn_end"')
  })

  it('Phase 8B loop probe is off by default and independent of turn-end Completion', async () => {
    expect(resolveConfig({ mode: 'shadow' }).completionLoopProbeEnabled).toBe(false)
    const fetchMock = gateFetch()
    vi.stubGlobal('fetch', fetchMock)
    const ctx = new FakeContext()
    apply(ctx, {
      mode: 'shadow', search_gate_enabled: false, model_tier_gate_enabled: false,
      notification_gate_enabled: false, completion_gate_enabled: true,
    })
    await enterTurn(ctx, 's-phase8b-off', 1, 'task')
    await ctx.one('session/event')(
      { id: 's-phase8b-off' },
      { type: 'tool/result', data: { turn: 1, step: 1, message: { isError: false } } },
    )
    expect(fetchMock).toHaveBeenCalledTimes(0)
    await ctx.one('session/event')(
      { id: 's-phase8b-off' },
      { type: 'turn/end', data: { turn: 1, reason: { kind: 'completed' } } },
    )
    await new Promise(resolve => setTimeout(resolve, 0))
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('Phase 8B loop probe observes one tool-result event per turn without changing execution', async () => {
    const fetchMock = gateFetch()
    vi.stubGlobal('fetch', fetchMock)
    const ctx = new FakeContext()
    apply(ctx, {
      mode: 'shadow', search_gate_enabled: false, model_tier_gate_enabled: false,
      notification_gate_enabled: false, completion_gate_enabled: true,
      completion_loop_probe_enabled: true,
    })
    await enterTurn(ctx, 's-phase8b', 1, 'private task')
    for (const step of [1, 2]) {
      expect(await ctx.one('session/event')(
        { id: 's-phase8b' },
        { type: 'tool/result', data: { turn: 1, step,
          message: { isError: false, content: [{ type: 'text', text: 'private raw secret' }] } } },
      )).toBeUndefined()
    }
    await new Promise(resolve => setTimeout(resolve, 0))
    expect(fetchMock).toHaveBeenCalledTimes(1)
    const probe = JSON.parse(String((fetchMock.mock.calls[0]![1] as RequestInit).body))
    expect(probe.execution_state).toEqual({ tools_used: 1, tool_failures: 0 })
    expect(probe.current_result).not.toContain('private raw secret')
    expect(ctx.info.join('\\n')).toContain('"stage":"tool_result"')
    expect(ctx.info.join('\\n')).not.toContain('private task')
    expect(ctx.info.join('\\n')).not.toContain('private raw secret')
    await ctx.one('session/event')(
      { id: 's-phase8b' },
      { type: 'turn/end', data: { turn: 1, reason: { kind: 'completed' } } },
    )
    await new Promise(resolve => setTimeout(resolve, 0))
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(ctx.info.join('\\n')).toContain('"stage":"turn_end"')
    await enterTurn(ctx, 's-phase8b', 2, 'second task')
    await ctx.one('session/event')(
      { id: 's-phase8b' },
      { type: 'tool/result', data: { turn: 2, step: 1, message: { isError: true } } },
    )
    await new Promise(resolve => setTimeout(resolve, 0))
    expect(fetchMock).toHaveBeenCalledTimes(3)
    const second = JSON.parse(String((fetchMock.mock.calls[2]![1] as RequestInit).body))
    expect(second.execution_state).toEqual({ tools_used: 1, tool_failures: 1 })
    // No stop/deny mutation hook is registered for Completion.
    expect(ctx.count('agent/request')).toBe(0)
  })

  it('Phase 8B loop and turn-end failed_open telemetry identifies each stage', async () => {
    const failed = vi.fn().mockRejectedValue(new Error('private runtime failure'))
    vi.stubGlobal('fetch', failed)
    const ctx = new FakeContext()
    apply(ctx, {
      mode: 'shadow',
      search_gate_enabled: false, model_tier_gate_enabled: false,
      notification_gate_enabled: false, completion_gate_enabled: true,
      completion_loop_probe_enabled: true,
    })
    const session = { id: 's-both-completion-stages-fail' }
    await enterTurn(ctx, session.id, 1, 'private task body')
    expect(await ctx.one('session/event')(
      session, { type: 'tool/result', data: { turn: 1, step: 1,
        message: { isError: true, content: [{ type: 'text', text: 'secret tool output' }] } } },
    )).toBeUndefined()
    await ctx.one('session/event')(
      session, { type: 'assistant/message', data: { turn: 1, step: 1,
        message: { content: [{ type: 'text', text: 'candidate report' }] } } },
    )
    expect(await ctx.one('session/event')(
      session, { type: 'turn/end', data: { turn: 1, reason: { kind: 'completed' } } },
    )).toBeUndefined()
    await new Promise(resolve => setTimeout(resolve, 0))

    const completionRecords = ctx.info
      .filter(message => message.includes('"gate":"completion"'))
      .map(message => JSON.parse(message.slice(message.indexOf('{'))) as {
        stage?: string,
        action_status: string,
        action_reason: string,
      })
    expect(failed).toHaveBeenCalledTimes(2)
    expect(completionRecords).toHaveLength(2)
    expect(completionRecords.map(record => record.stage).sort())
      .toEqual(['tool_result', 'turn_end'])
    expect(completionRecords.every(record => record.action_status === 'failed_open')).toBe(true)
    expect(completionRecords.every(record => record.action_reason === 'runtime_error')).toBe(true)
    expect(ctx.info.join('\\n')).not.toContain('private task body')
    expect(ctx.info.join('\\n')).not.toContain('secret tool output')
    expect(ctx.warnings.join('\\n')).not.toContain('private runtime failure')
    expect(ctx.count('agent/request')).toBe(0)
  })

  it('Phase 8B probe fails open and is inert when Completion is disabled', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('private runtime failure')))
    const ctx = new FakeContext()
    apply(ctx, {
      mode: 'shadow', search_gate_enabled: false, model_tier_gate_enabled: false,
      notification_gate_enabled: false, completion_gate_enabled: true,
      completion_loop_probe_enabled: true,
    })
    await enterTurn(ctx, 's-dead-probe', 1, 'some task')
    expect(await ctx.one('session/event')(
      { id: 's-dead-probe' },
      { type: 'tool/result', data: { turn: 1, step: 1, message: { isError: false } } },
    )).toBeUndefined()
    await new Promise(resolve => setTimeout(resolve, 0))
    expect(ctx.info.join('\\n')).toContain('"action_status":"failed_open"')
    expect(ctx.info.join('\\n')).not.toContain('private runtime failure')
    const inert = new FakeContext()
    const fetchMock = gateFetch()
    vi.stubGlobal('fetch', fetchMock)
    apply(inert, {
      mode: 'shadow', search_gate_enabled: false, model_tier_gate_enabled: false,
      notification_gate_enabled: false, completion_gate_enabled: false,
      completion_loop_probe_enabled: true,
    })
    await enterTurn(inert, 's-inert-probe', 1, 'task')
    await inert.one('session/event')(
      { id: 's-inert-probe' },
      { type: 'tool/result', data: { turn: 1, step: 1, message: { isError: false } } },
    )
    expect(fetchMock).toHaveBeenCalledTimes(0)
  })

  it('unacknowledged Canary behaves as Shadow', async () => {
    vi.stubGlobal('fetch', gateFetch())
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
    vi.stubGlobal('fetch', gateFetch())
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
    expect(ctx.info.join('\n')).toContain('"action_status":"applied"')
    expect(ctx.info.join('\n')).toContain('"action_reason":"verified_public_web_tool_denied"')
  })

  it('Search Canary feature switch can disable mutation without disabling observation', async () => {
    const fetchMock = gateFetch()
    vi.stubGlobal('fetch', fetchMock)
    const ctx = new FakeContext()
    apply(ctx, {
      mode: 'canary',
      canary_acknowledged: true,
      canary_web_filter_enabled: false,
    })

    await enterTurn(ctx, 's-search-switch', 1, 'synthetic local task')
    const result = await ctx.one('tools/pre-execute')(
      { name: 'web_search', agent: { session: { id: 's-search-switch' } } },
      async () => 'native-tool',
    )
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(result).toBe('native-tool')
  })

  it('model probability never gains Search Canary authority', async () => {
    vi.stubGlobal(
      'fetch',
      gateFetch({ ...modelDecision, probability_search: 0 }, modelFastDecision),
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

  it('Local System One failure is fail-open for Search and Model Tier', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('service unavailable')))
    const ctx = new FakeContext()
    apply(ctx, { mode: 'canary', canary_acknowledged: true })

    await enterTurn(ctx, 's-fail', 1, 'synthetic task')
    const result = await ctx.one('tools/pre-execute')(
      { name: 'web_search', agent: { session: { id: 's-fail' } } },
      async () => 'web-allowed',
    )

    expect(result).toBe('web-allowed')
    expect(ctx.warnings.join('\n')).toContain('search gate unavailable')
    expect(ctx.warnings.join('\n')).toContain('model tier gate unavailable')
    expect(ctx.warnings.join('\n')).not.toContain('service unavailable')
    expect(ctx.info.join('\n')).toContain('"action_status":"failed_open"')
    expect(ctx.info.join('\n')).toContain('"action_reason":"runtime_error"')
  })

  it('malformed Model Tier response fails open without breaking Search Canary', async () => {
    vi.stubGlobal('fetch', gateFetch(hardRuleDecision, { ...hardFastDecision, tier: '???' }))
    const ctx = new FakeContext()
    apply(ctx, { mode: 'canary', canary_acknowledged: true })

    await enterTurn(ctx, 's-malformed-tier', 1, 'synthetic local task')
    const result = await ctx.one('tools/pre-execute')(
      { name: 'web_search', agent: { session: { id: 's-malformed-tier' } } },
      async () => 'web-allowed',
    )
    expect(result).toMatchObject({ kind: 'deny' })
    expect(ctx.warnings.join('\n')).toContain('model tier gate unavailable')
    expect(ctx.info.join('\n')).toContain('"action_reason":"malformed_response"')
  })

  it('Model Tier Canary downgrades only deterministic hard-fast on the verified route', async () => {
    vi.stubGlobal('fetch', gateFetch(hardRuleDecision, hardFastDecision))
    const ctx = new FakeContext()
    apply(ctx, {
      mode: 'canary',
      canary_acknowledged: true,
      canary_reasoning_downgrade_enabled: true,
    })

    await enterTurn(ctx, 's-tier-canary', 1, 'rewrite this bounded text')
    const original = {
      provider: 'nova',
      model: 'deepseek-v4-flash',
      reasoningEffort: 'high',
      maxTokens: 4096,
    }
    const result = await ctx.one('agent/request')(
      { agent: { session: { id: 's-tier-canary' } }, turn: 1, step: 1 },
      async () => original,
    )

    expect(result).toEqual({ ...original, reasoningEffort: 'low' })
    expect(original.reasoningEffort).toBe('high')
    expect(result).not.toBe(original)
    expect(ctx.info.join('\n')).toContain('"action_status":"applied"')
    expect(ctx.info.join('\n')).toContain('"action_reason":"verified_reasoning_mapping"')
  })

  it('Model Tier Canary also downgrades the verified StepFun Step 5 Preview route', async () => {
    vi.stubGlobal('fetch', gateFetch(hardRuleDecision, hardFastDecision))
    const ctx = new FakeContext()
    apply(ctx, {
      mode: 'canary',
      canary_acknowledged: true,
      canary_reasoning_downgrade_enabled: true,
    })

    await enterTurn(ctx, 's-tier-stepfun', 1, 'rewrite this bounded text')
    const original = {
      provider: 'stepfun',
      model: 'step-5-preview',
      reasoningEffort: 'high',
      maxTokens: 4096,
    }
    const result = await ctx.one('agent/request')(
      { agent: { session: { id: 's-tier-stepfun' } }, turn: 1, step: 1 },
      async () => original,
    )
    expect(result).toEqual({ ...original, reasoningEffort: 'low' })
    expect(original.reasoningEffort).toBe('high')
  })

  it('Model Tier probability-only fast never gains Active authority', async () => {
    vi.stubGlobal('fetch', gateFetch(hardRuleDecision, modelFastDecision))
    const ctx = new FakeContext()
    apply(ctx, {
      mode: 'canary',
      canary_acknowledged: true,
      canary_reasoning_downgrade_enabled: true,
    })

    await enterTurn(ctx, 's-tier-model', 1, 'ambiguous task')
    const original = { provider: 'nova', model: 'deepseek-v4-flash', reasoningEffort: 'high' }
    const result = await ctx.one('agent/request')(
      { agent: { session: { id: 's-tier-model' } }, turn: 1, step: 1 },
      async () => original,
    )
    expect(result).toBe(original)
  })

  it('Model Tier Canary refuses unsupported providers and models', async () => {
    vi.stubGlobal('fetch', gateFetch(hardRuleDecision, hardFastDecision))
    const ctx = new FakeContext()
    apply(ctx, {
      mode: 'canary',
      canary_acknowledged: true,
      canary_reasoning_downgrade_enabled: true,
    })
    await enterTurn(ctx, 's-tier-route', 1, 'rewrite bounded text')

    for (const original of [
      { provider: 'other', model: 'deepseek-v4-flash', reasoningEffort: 'high' },
      { provider: 'nova', model: 'unverified-model', reasoningEffort: 'high' },
    ]) {
      const result = await ctx.one('agent/request')(
        { agent: { session: { id: 's-tier-route' } }, turn: 1, step: 1 },
        async () => original,
      )
      expect(result).toBe(original)
    }
    expect(ctx.info.join('\n')).toContain('"action_status":"unsupported"')
    expect(ctx.info.join('\n')).toContain('"action_reason":"unsupported_provider_or_model"')
  })

  it('Model Tier Canary preserves non-high user reasoning settings', async () => {
    vi.stubGlobal('fetch', gateFetch(hardRuleDecision, hardFastDecision))
    const ctx = new FakeContext()
    apply(ctx, {
      mode: 'canary',
      canary_acknowledged: true,
      canary_reasoning_downgrade_enabled: true,
    })
    await enterTurn(ctx, 's-tier-preserve', 1, 'rewrite bounded text')

    for (const reasoningEffort of ['low', 'off', undefined]) {
      const original = { provider: 'nova', model: 'deepseek-v4-flash', reasoningEffort }
      const result = await ctx.one('agent/request')(
        { agent: { session: { id: 's-tier-preserve' } }, turn: 1, step: 1 },
        async () => original,
      )
      expect(result).toBe(original)
    }
  })

  it('Model Tier Canary runs only on the first provider call step', async () => {
    vi.stubGlobal('fetch', gateFetch(hardRuleDecision, hardFastDecision))
    const ctx = new FakeContext()
    apply(ctx, {
      mode: 'canary',
      canary_acknowledged: true,
      canary_reasoning_downgrade_enabled: true,
    })
    await enterTurn(ctx, 's-tier-step', 1, 'rewrite bounded text')
    const original = { provider: 'nova', model: 'deepseek-v4-flash', reasoningEffort: 'high' }
    const result = await ctx.one('agent/request')(
      { agent: { session: { id: 's-tier-step' } }, turn: 1, step: 2 },
      async () => original,
    )
    expect(result).toBe(original)
  })

  it('Model Tier Canary feature switch off and unacknowledged Canary register no mutation hook', async () => {
    const offSwitch = new FakeContext()
    apply(offSwitch, {
      mode: 'canary',
      canary_acknowledged: true,
      canary_reasoning_downgrade_enabled: false,
    })
    expect(offSwitch.count('agent/request')).toBe(0)

    const unacknowledged = new FakeContext()
    apply(unacknowledged, {
      mode: 'canary',
      canary_acknowledged: false,
      canary_reasoning_downgrade_enabled: true,
    })
    expect(unacknowledged.count('agent/request')).toBe(0)
  })

  it('dead or malformed Model Tier runtime response leaves provider request unchanged', async () => {
    const cases = [
      vi.fn((url: string) => url.endsWith('/search-gate')
        ? Promise.resolve(jsonResponse(hardRuleDecision))
        : Promise.reject(new Error('dead'))),
      gateFetch(hardRuleDecision, { ...hardFastDecision, tier: 'invalid' }),
    ]

    for (const fetchMock of cases) {
      vi.stubGlobal('fetch', fetchMock)
      const ctx = new FakeContext()
      apply(ctx, {
        mode: 'canary',
        canary_acknowledged: true,
        canary_reasoning_downgrade_enabled: true,
      })
      const sessionId = `s-tier-fail-${Math.random()}`
      await enterTurn(ctx, sessionId, 1, 'rewrite bounded text')
      const original = { provider: 'nova', model: 'deepseek-v4-flash', reasoningEffort: 'high' }
      const result = await ctx.one('agent/request')(
        { agent: { session: { id: sessionId } }, turn: 1, step: 1 },
        async () => original,
      )
      expect(result).toBe(original)
      vi.unstubAllGlobals()
    }
  })

  it('turn/end prevents cross-turn Search or Model Tier decision leakage', async () => {
    vi.stubGlobal('fetch', gateFetch())
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
