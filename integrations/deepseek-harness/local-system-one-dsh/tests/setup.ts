import { afterAll, beforeAll, vi } from 'vitest'
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

let directory: string
let previous: string | undefined
beforeAll(() => {
  previous = process.env.LOCAL_SYSTEM_ONE_AUTH_TOKEN_FILE
  directory = mkdtempSync(join(tmpdir(), 'lso-dsh-test-'))
  const path = join(directory, 'access-token')
  writeFileSync(path, 'a'.repeat(43), { mode: 0o600 })
  process.env.LOCAL_SYSTEM_ONE_AUTH_TOKEN_FILE = path
})
afterAll(() => {
  if (previous === undefined) delete process.env.LOCAL_SYSTEM_ONE_AUTH_TOKEN_FILE
  else process.env.LOCAL_SYSTEM_ONE_AUTH_TOKEN_FILE = previous
  rmSync(directory, { recursive: true, force: true })
})

vi.mock('../src/transport.js', () => ({
  postJsonVerified: (url: string, token: string, body: string, signal: AbortSignal) => fetch(url, {
    method: 'POST', headers: { 'content-type': 'application/json', authorization: `Bearer ${token}` },
    body, signal, redirect: 'error',
  }),
}))
