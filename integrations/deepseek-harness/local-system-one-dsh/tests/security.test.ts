import './setup.js'
import { afterEach, expect, it, vi } from 'vitest'
import { chmodSync } from 'node:fs'
import { SearchGateClient } from '../src/client.js'

afterEach(() => vi.unstubAllGlobals())

it('uses a private bearer token without following redirects', async () => {
  const fetchMock = vi.fn(async (_url: string, _options: RequestInit) => new Response(JSON.stringify({
    workflow: 'search_gate', decision: 'no_search', decision_source: 'rule', reason: 'local_file_or_repo',
    probability_search: 0, backend: 'rule', latency_ms: 1, request_id: 'test',
  })))
  vi.stubGlobal('fetch', fetchMock)
  await new SearchGateClient('http://127.0.0.1:8787', 1000).decide('task', 'test')
  const options = fetchMock.mock.calls[0]![1]
  expect(options.redirect).toBe('error')
  expect((options.headers as Record<string, string>).authorization).toBe(`Bearer ${'a'.repeat(43)}`)
})

it('rejects unsafe token files and remote sidecars before sending data', async () => {
  const fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  const path = process.env.LOCAL_SYSTEM_ONE_AUTH_TOKEN_FILE!
  chmodSync(path, 0o644)
  try {
    await expect(new SearchGateClient('http://127.0.0.1:8787', 1000).decide('task', 'test')).rejects.toThrow()
  } finally {
    chmodSync(path, 0o600)
  }
  await expect(new SearchGateClient('http://example.org', 1000).decide('task', 'test')).rejects.toThrow()
  expect(fetchMock).not.toHaveBeenCalled()
})

it('verifies listener identity on the same connection before sending task and token', async () => {
  const { createHmac } = await import('node:crypto')
  const { createServer } = await import('node:http')
  const { postJsonVerified } = await vi.importActual<typeof import('../src/transport.js')>('../src/transport.js')
  const token = 'a'.repeat(43)
  const seen: Array<{ path: string | undefined, authorization: string | undefined, socket: unknown }> = []
  let trusted = false
  const server = createServer((req, res) => {
    seen.push({ path: req.url, authorization: req.headers.authorization, socket: req.socket })
    if (req.url === '/_local_system_one/identity') {
      const port = (req.socket.localPort ?? 0) + (trusted ? 0 : 1)
      const proof = createHmac('sha256', token).update(`identity:${req.headers['x-local-system-one-challenge']}:${req.socket.localAddress}:${port}`).digest('hex')
      res.writeHead(200, { 'content-type': 'application/json' }).end(JSON.stringify({ proof }))
    } else {
      req.resume()
      req.on('end', () => res.writeHead(200, { 'content-type': 'application/json' }).end('{"ok":true}'))
    }
  })
  await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve))
  const address = server.address()
  if (!address || typeof address === 'string') throw Error('missing test address')
  const url = `http://127.0.0.1:${address.port}/v1/test`
  try {
    await expect(postJsonVerified(url, token, '{"task":"private"}', AbortSignal.timeout(2000))).rejects.toThrow('identity')
    expect(seen.map(row => [row.path, row.authorization])).toEqual([['/_local_system_one/identity', undefined]])
    seen.length = 0
    trusted = true
    const result = await postJsonVerified(url, token, '{"task":"private"}', AbortSignal.timeout(2000))
    expect(await result.json()).toEqual({ ok: true })
    expect(seen.map(row => row.path)).toEqual(['/_local_system_one/identity', '/v1/test'])
    expect(seen[0]!.socket).toBe(seen[1]!.socket)
    expect(seen[1]!.authorization).toBe(`Bearer ${token}`)
  } finally {
    server.closeAllConnections()
    await new Promise<void>(resolve => server.close(() => resolve()))
  }
})
