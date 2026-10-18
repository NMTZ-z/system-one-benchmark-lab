import { describe, it, expect, vi, afterEach } from 'vitest'
import { apply } from '../src/index.js'
import { parseRetryEscalationDecision } from '../src/client.js'
import { failureFromToolResult, operationFromToolName } from '../src/retry.js'
import type { FailureContext } from '../src/types.js'

type Handler = (...args: any[]) => unknown
class Context {
  handlers = new Map<string, Handler>()
  events: string[] = []
  logger = { info: (msg: string) => this.events.push(msg) }
  on(name: string, h: Handler) { this.handlers.set(name, h) }
  fire(name: string, session: string, type: string, data: Record<string, unknown>) {
    return this.handlers.get(name)?.({ id: session }, { type, data })
  }
}

function makeResponse(req: string) {
  return {
    workflow: 'retry_escalation_gate',
    decision: 'verify_state', guarded_decision: 'verify_state',
    raw_model_decision: null, safety_override_reason: null,
    decision_source: 'rule', reason: 'unconfirmed_side_effect_verify_first',
    backend: 'rule', latency_ms: 1.23, confidence: 1, request_id: req,
    advisory_only: true,
  }
}
function stubRemote() {
  const fetchMock = vi.fn(async (_url: string, opt: RequestInit) => {
    const request = JSON.parse(String(opt.body))
    return new Response(JSON.stringify(makeResponse(request.request_id)), {
      status: 200, headers: { 'content-type': 'application/json' },
    })
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}
function call(ctx: Context, tool: string, id: string, session = 's', turn = 1) {
  // Native Harness guarantees turn/start before the first tool call.
  ctx.fire('session/event', session, 'turn/start', { turn })
  ctx.fire('session/event', session, 'tool/call', {
    turn, step: 1, name: tool, callId: id,
    arguments: '{"secret":"never log me"}',
  })
}
function result(ctx: Context, id: string, failed: boolean, session = 's', turn = 1) {
  ctx.fire('session/event', session, 'tool/result', {
    turn, step: 1,
    message: { role: 'tool', isError: failed,
      source: { callId: id },
      content: [{ type: 'text', text: 'very private ERROR content' }],
    },
    error: failed ? { name: 'Error', code: 'ETIMEDOUT', reason: 'private stack trace' } : undefined,
  })
}
function configure(ctx: Context, enabled = true) {
  apply(ctx, {
    mode: 'shadow',
    search_gate_enabled: false, model_tier_gate_enabled: false,
    notification_gate_enabled: false, completion_gate_enabled: false,
    retry_escalation_gate_enabled: enabled,
  })
}
const settle = () => new Promise(resolve => setTimeout(resolve, 0))
afterEach(() => vi.unstubAllGlobals())

describe('Phase 8C DSH Retry Shadow', () => {
  it('defaults to OFF independently', async () => {
    const ctx = new Context()
    const fetchMock = stubRemote()
    configure(ctx, false)
    call(ctx, 'write', '1')
    result(ctx, '1', true)
    await settle()
    expect(fetchMock).not.toHaveBeenCalled()
  })
  it('requires exact upstream tool/call identity and only explicit failures', async () => {
    const ctx = new Context()
    const fetchMock = stubRemote()
    configure(ctx)
    call(ctx, 'write', 'a')
    result(ctx, 'a', false)
    expect(fetchMock).not.toHaveBeenCalled()
    result(ctx, 'a', true)
    result(ctx, 'a', true) // duplicate terminal event must not repeat inference
    await settle()
    expect(fetchMock).toHaveBeenCalledTimes(1)
    const request = JSON.parse(String(fetchMock.mock.calls[0]![1].body))
    expect(request.operation.type).toBe('local_file')
    expect(request.operation.side_effect_status).toBe('unknown')
    expect(request.history.retry_budget_available).toBe(false)
    expect(JSON.stringify(request)).not.toContain('secret')
    expect(JSON.stringify(ctx.events)).not.toContain('private')
    expect(ctx.events.some(s => s.includes('"decision":{"value":"verify_state"'))).toBe(true)
  })
  it('never invents known tool semantics or a failed action from result content', async () => {
    const ctx = new Context()
    const fetchMock = stubRemote()
    configure(ctx)
    call(ctx, 'bash', 'bad')
    result(ctx, 'bad', true)
    result(ctx, 'unpaired', true)
    await settle()
    expect(fetchMock).not.toHaveBeenCalled()
    expect(ctx.events.filter(e => e.includes('"action_status":"unsupported"'))).toHaveLength(2)
  })
  it('limits two observations per turn and cleans turn state', async () => {
    const ctx = new Context()
    const fetchMock = stubRemote()
    configure(ctx)
    for (const id of ['1', '2', '3']) {
      call(ctx, 'write', id)
      result(ctx, id, true)
    }
    await settle()
    expect(fetchMock).toHaveBeenCalledTimes(2)
    ctx.fire('session/event', 's', 'turn/end', { turn: 1, reason: { kind: 'completed' } })
    call(ctx, 'write', '1', 's', 2)
    result(ctx, '1', true, 's', 2)
    await settle()
    expect(fetchMock).toHaveBeenCalledTimes(3)
  })
  it('preserves oldest live-turn counts at 96 concurrent turns and frees capacity at end', async () => {
    const ctx = new Context()
    const fetchMock = stubRemote()
    configure(ctx)

    // 96 simultaneous tracked turns. Await only the observer network work,
    // not a turn/end, so all 96 counters stay live in the Map.
    for (let i = 0; i < 96; i += 1) {
      const session = `busy-${i}`
      call(ctx, 'write', 'first', session, 1)
      result(ctx, 'first', true, session, 1)
      if (i % 4 === 3) await settle()
    }
    await settle()
    expect(fetchMock).toHaveBeenCalledTimes(96)

    // The 97th turn is denied instead of silently evicting busy-0's count.
    call(ctx, 'write', 'overflow-call', 'overflow', 1)
    result(ctx, 'overflow-call', true, 'overflow', 1)
    await settle()
    expect(fetchMock).toHaveBeenCalledTimes(96)
    expect(ctx.events.some(e => e.includes('retry_turn_capacity_exhausted'))).toBe(true)

    // A previously admitted turn still gets its *second* observation, never
    // a third, even after many new turn events tried to exhaust the Map.
    call(ctx, 'write', 'second', 'busy-0', 1)
    result(ctx, 'second', true, 'busy-0', 1)
    await settle()
    expect(fetchMock).toHaveBeenCalledTimes(97)
    call(ctx, 'write', 'third', 'busy-0', 1)
    result(ctx, 'third', true, 'busy-0', 1)
    await settle()
    expect(fetchMock).toHaveBeenCalledTimes(97)

    // Once the original turn ends, capacity can be reused.
    ctx.fire('session/event', 'busy-0', 'turn/end', {
      turn: 1, reason: { kind: 'completed' },
    })
    call(ctx, 'write', 'accepted-after-end', 'overflow', 1)
    result(ctx, 'accepted-after-end', true, 'overflow', 1)
    await settle()
    expect(fetchMock).toHaveBeenCalledTimes(98)
  })

  it('does not reset an active observation budget on a duplicate turn/start', async () => {
    const ctx = new Context()
    const fetchMock = stubRemote()
    configure(ctx)
    call(ctx, 'write', 'first')
    result(ctx, 'first', true)
    await settle()
    ctx.fire('session/event', 's', 'turn/start', { turn: 1 })
    call(ctx, 'write', 'second')
    result(ctx, 'second', true)
    await settle()
    call(ctx, 'write', 'third')
    result(ctx, 'third', true)
    await settle()
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('closing a parent session never resets a colon-delimited child retry budget', async () => {
    const ctx = new Context()
    const fetchMock = stubRemote()
    configure(ctx)

    for (const id of ['child-first', 'child-second']) {
      call(ctx, 'write', id, 'job:child', 1)
      result(ctx, id, true, 'job:child', 1)
      await settle()
    }
    expect(fetchMock).toHaveBeenCalledTimes(2)

    // A distinct parent session may use an identical turn and call ID.
    call(ctx, 'write', 'child-first', 'job', 1)
    result(ctx, 'child-first', true, 'job', 1)
    await settle()
    expect(fetchMock).toHaveBeenCalledTimes(3)

    ctx.fire('session/event', 'job', 'session/end', {})
    // Parent cleanup must not erase the child's 2-observation counter.
    call(ctx, 'write', 'child-third', 'job:child', 1)
    result(ctx, 'child-third', true, 'job:child', 1)
    result(ctx, 'child-first', true, 'job:child', 1)
    await settle()
    expect(fetchMock).toHaveBeenCalledTimes(3)

    // A new parent session may use its own budget.
    call(ctx, 'write', 'parent-new', 'job', 2)
    result(ctx, 'parent-new', true, 'job', 2)
    await settle()
    expect(fetchMock).toHaveBeenCalledTimes(4)

    // Child lifecycle cleanup is independent as well.
    ctx.fire('session/event', 'job:child', 'session/close', {})
    call(ctx, 'write', 'child-new', 'job:child', 2)
    result(ctx, 'child-new', true, 'job:child', 2)
    await settle()
    expect(fetchMock).toHaveBeenCalledTimes(5)
    expect(JSON.stringify(ctx.events)).not.toContain('very private ERROR')
  })

  it('drops late tool events after turn/end and session/end without reviving Retry budgets', async () => {
    const ctx = new Context()
    const fetchMock = stubRemote()
    configure(ctx)
    call(ctx, 'read', 'first', 's', 1)
    result(ctx, 'first', true, 's', 1)
    await settle()
    expect(fetchMock).toHaveBeenCalledTimes(1)
    ctx.fire('session/event', 's', 'turn/end', { turn: 1, reason: { kind: 'completed' } })
    const logged = ctx.events.length
    ctx.fire('session/event', 's', 'tool/call', { turn: 1, name: 'read', callId: 'late' })
    result(ctx, 'late', true, 's', 1)
    result(ctx, 'first', true, 's', 1)
    await settle()
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(ctx.events).toHaveLength(logged)
    call(ctx, 'read', 'fresh', 's', 2)
    result(ctx, 'fresh', true, 's', 2)
    await settle()
    expect(fetchMock).toHaveBeenCalledTimes(2)
    ctx.fire('session/event', 's', 'session/end', {})
    const afterClose = ctx.events.length
    ctx.fire('session/event', 's', 'tool/call', { turn: 2, name: 'read', callId: 'very-late' })
    result(ctx, 'very-late', true, 's', 2)
    await settle()
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(ctx.events).toHaveLength(afterClose)
  })

  it('malformed runtime responses fail-open and preserve Agent events', async () => {
    const ctx = new Context()
    vi.stubGlobal('fetch', vi.fn(async () => new Response('{"decision":"retry_same"}')))
    configure(ctx)
    call(ctx, 'write', 'a')
    expect(result(ctx, 'a', true)).toBeUndefined()
    await settle()
    expect(ctx.events.some(e => e.includes('"action_status":"failed_open"'))).toBe(true)
  })
  it('requires positive evidence, refuses unsafe model schema', () => {
    const value = makeResponse('abc')
    expect(parseRetryEscalationDecision(value).decision).toBe('verify_state')
    const withoutRaw = { ...value } as Record<string, unknown>
    delete withoutRaw.raw_model_decision
    expect(() => parseRetryEscalationDecision(withoutRaw)).toThrow(/invalid/)
    const withoutOverride = { ...value } as Record<string, unknown>
    delete withoutOverride.safety_override_reason
    expect(() => parseRetryEscalationDecision(withoutOverride)).toThrow(/invalid/)
    expect(() => parseRetryEscalationDecision({ ...value, advisory_only: false }))
      .toThrow(/invalid/)
    expect(() => parseRetryEscalationDecision({ ...value, guarded_decision: 'retry_same' }))
      .toThrow(/invalid/)
    expect(operationFromToolName('bash')).toBeNull()
    expect(operationFromToolName('write')?.idempotency).toBe('unknown')
    const sample = { type: 'tool/result', data: {
      message: { isError: false, content: [{ text: 'Error: false positive' }] },
    } }
    expect(failureFromToolResult(sample, operationFromToolName('write')!)).toBeNull()
  })
})
