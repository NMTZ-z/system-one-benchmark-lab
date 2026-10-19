import { afterEach, describe, expect, it, vi } from 'vitest'
import { apply } from '../src/index.js'
import { correlationRefs, isolatedCorrelationKey, writePrivateCorrelation } from '../src/evidence.js'
import { mkdtempSync, mkdirSync, readFileSync, rmSync, statSync, symlinkSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { createHmac } from 'node:crypto'

const isolatedSetting = 'isolated-shadow-test-v1'
const fixedKey = '7e'.repeat(32)
const privateSid = 'SYNTHETIC_NATIVE_SESSION_NOT_TO_EXPORT'
const privateCall = 'SYNTHETIC_NATIVE_CALL_NOT_TO_EXPORT'

function expected(scope: string, raw: string): string {
  return createHmac('sha256', Buffer.from(fixedKey, 'hex'))
    .update(scope + '\0' + raw).digest('hex').slice(0, 32)
}

type Listener = (...args: any[]) => any
class FakeContext {
  handlers = new Map<string, Listener[]>()
  info: string[] = []
  logger = { info: (message: string) => { this.info.push(message) }, warn: (_: string) => {} }
  on(name: string, callback: Listener): void {
    const values = this.handlers.get(name) ?? []
    values.push(callback)
    this.handlers.set(name, values)
  }
  one(name: string): Listener {
    const callbacks = this.handlers.get(name) ?? []
    if (callbacks.length !== 1) throw new Error('unexpected callback count')
    return callbacks[0]!
  }
}
function isolatedEnv() {
  process.env.LOCAL_SYSTEM_ONE_EVIDENCE_ENABLE = isolatedSetting
  process.env.LOCAL_SYSTEM_ONE_EVIDENCE_KEY_HEX = fixedKey
}
afterEach(() => {
  delete process.env.LOCAL_SYSTEM_ONE_EVIDENCE_ENABLE
  delete process.env.LOCAL_SYSTEM_ONE_EVIDENCE_KEY_HEX
  delete process.env.LOCAL_SYSTEM_ONE_EVIDENCE_PRIVATE_ROOT
  delete process.env.DSH_HOME
  vi.unstubAllGlobals()
})

async function nativeOneTurn(mismatch = false, withCallId = true) {
  isolatedEnv()
  const ctx = new FakeContext()
  const wire: string[] = []
  const fetchMock = vi.fn(async (_url: string, options: RequestInit) => {
    const input = JSON.parse(String(options.body))
    wire.push(input.request_id)
    const content = {
      decision: 'verify', decision_source: 'rule', reason: 'pending_verification',
      probability_complete: 0, probability_verify: 1, probability_continue: 0,
      confidence: 1, backend: 'rule', latency_ms: 0,
      request_id: mismatch ? 'mismatched-response-id' : input.request_id,
    }
    return new Response(JSON.stringify(content), { status: 200,
      headers: { 'content-type': 'application/json' } })
  })
  vi.stubGlobal('fetch', fetchMock)
  apply(ctx, { mode: 'shadow', completion_gate_enabled: true,
    completion_loop_probe_enabled: true, notification_gate_enabled: false,
    search_gate_enabled: false, model_tier_gate_enabled: false })
  await ctx.one('session/event')({ id: privateSid }, { type: 'turn/start', data: { turn: 1 } })
  await ctx.one('agent/pre-step')({
    agent: { session: { id: privateSid } }, turn: 1, step: 1,
    messages: [{ role: 'user', content: [{ type: 'text', text: 'private task' }] }],
  }, async () => ({ kind: 'enter' }))
  const result = { type: 'tool/result', data: { turn: 1, step: 1, message: {
    isError: false,
    source: withCallId ? { callId: privateCall } : undefined,
  } } }
  await ctx.one('session/event')({ id: privateSid }, result)
  await ctx.one('session/event')({ id: privateSid }, {
    type: 'assistant/message', data: { turn: 1, message: {
      content: [{ type: 'text', text: 'result' }],
    } },
  })
  await ctx.one('session/event')({ id: privateSid }, {
    type: 'turn/end', data: { turn: 1, reason: { kind: 'completed' } },
  })
  await new Promise(resolve => setTimeout(resolve, 0))
  const rows = ctx.info.filter(x => x.startsWith('[local-system-one-dsh] {'))
    .map(x => JSON.parse(x.slice('[local-system-one-dsh] '.length)))
    .filter(x => x.gate === 'completion')
  return { rows, wire, fetchMock, info: ctx.info.join('\n') }
}

describe('8.2B isolated native correlation', () => {
  it('is disabled unless the isolated opt-in and full 256-bit key are both present', () => {
    expect(isolatedCorrelationKey()).toBeNull()
    process.env.LOCAL_SYSTEM_ONE_EVIDENCE_KEY_HEX = fixedKey
    expect(isolatedCorrelationKey()).toBeNull()
    process.env.LOCAL_SYSTEM_ONE_EVIDENCE_ENABLE = isolatedSetting
    expect(isolatedCorrelationKey()).toEqual(Buffer.from(fixedKey, 'hex'))
    expect(correlationRefs(isolatedCorrelationKey(), privateSid, 1,
      'request-id', 'tool_result', null)).toBeNull()
    expect(correlationRefs(isolatedCorrelationKey(), privateSid, 1,
      'request-id', 'tool_result', privateCall)?.native_event_ref)
      .toBe(expected('native_event', privateSid + '\0' + '1' + '\0tool_result\0' + privateCall))
  })

  it('links exact native tool/turn, adapter decision request and original runtime request', async () => {
    const { rows, wire, info } = await nativeOneTurn()
    expect(wire).toHaveLength(2)
    expect(rows).toHaveLength(2)
    for (const row of rows) {
      expect(row.session_ref).toBe(expected('session', privateSid))
      expect(row.turn_ref).toBe(expected('turn', privateSid + '\0' + '1'))
      expect(row.decision_request_ref).toBe(expected('decision_request', row.request_id))
      expect(row.action_status).toBe('observed')
    }
    expect(rows.find(x => x.native_stage === 'tool_result')?.native_event_ref)
      .toBe(expected('native_event', privateSid + '\0' + '1' + '\0tool_result\0' + privateCall))
    expect(rows.find(x => x.native_stage === 'turn_end')?.native_event_ref)
      .toBe(expected('native_event', privateSid + '\0' + '1' + '\0turn_end'))
    expect(info).not.toContain(privateSid)
    expect(info).not.toContain(privateCall)
    expect(info).not.toContain('private task')
  })

  it('declines fake exact tool identity when native callId missing', async () => {
    const { rows, wire } = await nativeOneTurn(false, false)
    expect(wire).toHaveLength(2)
    expect(rows.find(x => x.stage === 'tool_result')?.native_event_ref).toBeUndefined()
    expect(rows.find(x => x.stage === 'turn_end')?.native_event_ref).toBeDefined()
  })

  it('does not certify forged runtime request IDs', async () => {
    const { rows } = await nativeOneTurn(true)
    expect(rows).toHaveLength(2)
    expect(rows.every(row => row.action_status === 'failed_open')).toBe(true)
    expect(rows.every(row => row.evidence_status === 'ambiguous')).toBe(true)
  })

  it('writes only anonymized test metadata inside an isolated HOME', () => {
    isolatedEnv()
    const root = mkdtempSync(join(tmpdir(), 'local-system-one-isolated-'))
    try {
      const home = join(root, 'private-home')
      mkdirSync(home, { mode: 0o700 })
      process.env.DSH_HOME = home
      process.env.LOCAL_SYSTEM_ONE_EVIDENCE_PRIVATE_ROOT = root
      writePrivateCorrelation({
        gate: 'completion', native_stage: 'turn_end',
        native_event_ref: 'a'.repeat(32),
        decision_request_ref: 'b'.repeat(32),
        action_status: 'observed',
        task: 'DO_NOT_EXPORT_PRIVATE_TASK',
        api_key: 'DO_NOT_EXPORT_PRIVATE_KEY',
      })
      const path = join(home, 'phase8_2b_correlation.private.jsonl')
      const raw = readFileSync(path, 'utf8')
      const row = JSON.parse(raw.trim())
      expect(row.native_event_ref).toBe('a'.repeat(32))
      expect(row.decision_request_ref).toBe('b'.repeat(32))
      expect(row.task).toBeUndefined()
      expect(row.api_key).toBeUndefined()
      expect(raw).not.toContain('DO_NOT_EXPORT')
      expect(statSync(path).mode & 0o077).toBe(0)
    } finally {
      rmSync(root, { recursive: true, force: true })
    }
  })

  it('refuses a symlinked private evidence destination', () => {
    isolatedEnv()
    const root = mkdtempSync(join(tmpdir(), 'local-system-one-symlink-'))
    try {
      const home = join(root, 'private-home')
      mkdirSync(home)
      const victim = join(root, 'victim.txt')
      writeFileSync(victim, 'UNCHANGED')
      symlinkSync(victim, join(home, 'phase8_2b_correlation.private.jsonl'))
      process.env.DSH_HOME = home
      process.env.LOCAL_SYSTEM_ONE_EVIDENCE_PRIVATE_ROOT = root
      writePrivateCorrelation({
        gate: 'completion', native_stage: 'turn_end',
        native_event_ref: 'a'.repeat(32),
        decision_request_ref: 'b'.repeat(32),
      })
      expect(readFileSync(victim, 'utf8')).toBe('UNCHANGED')
    } finally {
      rmSync(root, { recursive: true, force: true })
    }
  })
})
