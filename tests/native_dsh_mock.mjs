// Run the installed bundle in a pinned, isolated DSH SDK with local mock services.
import { strict as assert } from 'node:assert'
import { createHmac, randomBytes } from 'node:crypto'
import { execFileSync, spawn } from 'node:child_process'
import { createServer } from 'node:http'
import { chmodSync, existsSync, realpathSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { createInterface } from 'node:readline'
import { setTimeout as delay } from 'node:timers/promises'
import { pathToFileURL } from 'node:url'

const root = realpathSync(process.env.LOCAL_SYSTEM_ONE_QUALIFICATION_ROOT)
const source = realpathSync(process.env.DSH_SOURCE_ROOT)
const home = realpathSync(process.env.DSH_HOME)
assert(existsSync(join(root, '.local-system-one-isolated-test')))
assert(source.startsWith(root + '/') && home.startsWith(root + '/'))
const revision = execFileSync('git', ['-C', source, 'rev-parse', 'HEAD'], { encoding: 'utf8' }).trim()
assert.equal(revision, process.env.DSH_EXPECTED_REVISION)
const { startMockLlmServer } = await import(pathToFileURL(join(source, 'packages/test-support/llm-mock-server/src/index.ts')).href)
const tokenPath = join(root, `dsh-access-token-${revision.slice(0, 8)}`)
const token = randomBytes(32).toString('base64url')
writeFileSync(tokenPath, token, { mode: 0o600, flag: 'wx' })
chmodSync(tokenPath, 0o600)
const paths = []
let sidecar

try {
  sidecar = createServer((req, res) => {
    if (req.url === '/_local_system_one/identity') {
      const proof = createHmac('sha256', token).update(`identity:${req.headers['x-local-system-one-challenge']}:${req.socket.localAddress}:${req.socket.localPort}`).digest('hex')
      res.writeHead(200, { 'content-type': 'application/json' }).end(JSON.stringify({ proof })); return
    }
    if (req.headers.authorization !== `Bearer ${token}`) { res.writeHead(401).end(); return }
    let body = ''
    req.on('data', chunk => { body += chunk })
    req.on('end', () => {
      const input = JSON.parse(body)
      paths.push(req.url)
      const common = { decision_source: 'rule', reason: 'local_file_or_repo', backend: 'rule', latency_ms: 0, request_id: input.request_id }
      const response = req.url.endsWith('/search-gate')
        ? { ...common, workflow: 'search_gate', decision: 'no_search', probability_search: 0 }
        : req.url.endsWith('/model-tier-gate')
          ? { ...common, workflow: 'model_tier_gate', tier: 'fast', difficulty_score: 0, probability_strong: 0, confidence: 1 }
          : req.url.endsWith('/notification-gate')
            ? { ...common, workflow: 'notification_gate', delivery: 'silent', notify_now: false, priority_score: 0, confidence: 1 }
            : req.url.endsWith('/completion-gate')
              ? { ...common, workflow: 'completion_gate', decision: 'complete', probability_complete: 1, probability_verify: 0, probability_continue: 0, confidence: 1, advisory_only: true }
              : { ...common, workflow: 'retry_escalation_gate', decision: 'verify_state', guarded_decision: 'verify_state', raw_model_decision: null, safety_override_reason: null, confidence: 1, advisory_only: true }
      res.writeHead(200, { 'content-type': 'application/json' }).end(JSON.stringify(response))
    })
  })
  await new Promise(resolve => sidecar.listen(0, '127.0.0.1', resolve))
  const sidecarPort = sidecar.address().port

  async function scenario(mode, sequence = ['success']) {
    const mock = await startMockLlmServer({ sequence, repeatLast: true, toolName: 'read', toolArguments: '{}', successText: 'MOCK_RESPONSE' })
    const before = paths.length
    const patch = join(root, `dsh-${mode}.yml`)
    const gates = mode === 'first' ? '' : '    search_gate_enabled: true\n    model_tier_gate_enabled: true\n    notification_gate_enabled: true\n    completion_gate_enabled: true\n    retry_escalation_gate_enabled: true\n'
    writeFileSync(patch, `- id: local-system-one-dsh\n  config:\n    mode: ${mode === 'off' ? 'off' : 'shadow'}\n    service_url: http://127.0.0.1:${sidecarPort}\n    timeout_ms: 3000\n${gates}    canary_acknowledged: false\n`)
    const policy = `(version 1)(allow default)(deny network-outbound)(allow network-outbound (remote ip "localhost:${mock.port}"))(allow network-outbound (remote ip "localhost:${sidecarPort}"))`
    const env = { ...process.env, DSH_TELEMETRY_MODE: 'DISABLED', DEEPSEEK_API_KEY: 'local-mock-key',
      DEEPSEEK_BASE_URL: mock.baseURL, LOCAL_SYSTEM_ONE_AUTH_TOKEN_FILE: tokenPath, NO_PROXY: '127.0.0.1,localhost' }
    const child = spawn('/usr/bin/sandbox-exec', ['-p', policy, process.execPath, '--import', 'tsx/esm', 'apps/cli/src/bin.ts', '--profile', 'sdk-minimal', '--patch', patch],
      { cwd: source, env, stdio: ['pipe', 'pipe', 'pipe'] })
    let errors = ''
    child.stderr.on('data', value => { errors = (errors + value).slice(-4000) })
    const lines = createInterface({ input: child.stdout })[Symbol.asyncIterator]()
    const messages = []
    const send = value => child.stdin.write(JSON.stringify(value) + '\n')
    async function waitFor(predicate) {
      const deadline = Date.now() + 35000
      while (Date.now() < deadline) {
        const existing = messages.find(predicate)
        if (existing) return existing
        const item = await Promise.race([lines.next(), delay(Math.max(1, deadline - Date.now()), undefined, { ref: false }).then(() => { throw Error('SDK timeout') })])
        if (item.done) throw Error(`SDK ended early: ${errors}`)
        try { messages.push(JSON.parse(item.value)) } catch { throw Error('SDK returned non-JSON output') }
      }
      throw Error('SDK timeout')
    }
    try {
      send({ jsonrpc: '2.0', id: 1, method: 'initialize', params: { cwd: root, provider: 'deepseek-official', model: 'deepseek-v4-flash' } })
      const initialized = await waitFor(value => value.id === 1)
      assert(initialized.result, JSON.stringify(initialized.error) + errors)
      send({ jsonrpc: '2.0', id: 2, method: 'session/prompt', params: { sessionId: `test-${mode}-${randomBytes(6).toString('hex')}`, contentBlocks: [{ type: 'text', text: 'Respond with the mock answer.' }] } })
      const prompted = await waitFor(value => value.id === 2)
      assert(prompted.result, JSON.stringify(prompted.error) + errors)
      const ended = await waitFor(value => value.method === 'session.event' && value.params?.event?.type === 'turn/end')
      assert.equal(ended.params.event.data?.reason?.kind, 'completed')
      const expected = mode === 'first' ? 1 : ['shadow', 'retry'].includes(mode) ? 4 : 0
      for (let i = 0; i < 40 && paths.length - before < expected; i++) await delay(50)
      if (mode === 'first') await delay(300)
      send({ jsonrpc: '2.0', id: 3, method: 'shutdown', params: {} })
      const stopped = await waitFor(value => value.id === 3)
      assert(stopped.result, JSON.stringify(stopped.error) + errors)
      if (child.exitCode === null) await Promise.race([new Promise(resolve => child.once('exit', resolve)), delay(5000, undefined, { ref: false }).then(() => { throw Error('SDK did not exit') })])
      assert(mock.requests.length > 0, 'mock provider was not called')
      return { paths: paths.slice(before), request: mock.requests[0].body,
        toolFailure: messages.some(value => value.method === 'session.event' && value.params?.event?.type === 'tool/result' && value.params.event.data?.message?.isError === true) }
    } finally {
      if (child.exitCode === null) {
        child.kill('SIGKILL')
        await new Promise(resolve => child.once('exit', resolve))
      }
      await mock.close()
    }
  }

  const off = await scenario('off')
  assert.equal(off.paths.length, 0)
  const first = await scenario('first')
  assert.deepEqual(first.paths, ['/v1/workflows/search-gate'])
  const shadow = await scenario('shadow')
  for (const gate of ['search', 'model-tier', 'notification', 'completion']) {
    assert(shadow.paths.some(path => path.endsWith(`/${gate}-gate`)), `missing ${gate} observation`)
  }
  for (const key of ['model', 'messages', 'tools', 'max_tokens']) {
    assert.deepEqual(shadow.request[key], off.request[key], `Shadow changed provider ${key}`)
  }
  const retry = await scenario('retry', ['tool_call_success', 'success'])
  const retryObserved = retry.paths.some(path => path.endsWith('/retry-escalation-gate'))
  sidecar.closeAllConnections()
  await new Promise(resolve => sidecar.close(resolve))
  sidecar = undefined
  const down = await scenario('down')
  assert(down.request, 'native DSH did not continue with the mock provider')
  console.log(JSON.stringify({ revision, install: 'PASS', default_off: 'PASS', first_shadow_search_only: 'PASS', shadow_four_gates: 'PASS',
    native_provider_request_unchanged: 'PASS', runtime_down_fail_open: 'PASS',
    retry_observed: retryObserved, retry_tool_failure_seen: retry.toolFailure, provider: 'local_mock' }))
} finally {
  if (sidecar) {
    sidecar.closeAllConnections()
    await new Promise(resolve => sidecar.close(resolve))
  }
  try { (await import('node:fs')).unlinkSync(tokenPath) } catch {}
}
