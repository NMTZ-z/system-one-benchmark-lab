/** Phase 8.2B opt-in private test correlation. Never logs native identifiers or keys.
 * Test-only private metadata can be written under isolated DSH_HOME, never elsewhere.
 * No network calls, native execution changes, or Active permissions.
 */
import { createHmac } from 'node:crypto'
import { closeSync, constants, fstatSync, openSync, realpathSync, writeSync } from 'node:fs'
import { join, sep } from 'node:path'

const SCOPE = 'isolated-shadow-test-v1'
const HEX_KEY = /^[a-f0-9]{64}$/
const MAX_ID = 256

function keyFromEnvironment(): Buffer | null {
  if (process.env.LOCAL_SYSTEM_ONE_EVIDENCE_ENABLE !== SCOPE) return null
  const raw = process.env.LOCAL_SYSTEM_ONE_EVIDENCE_KEY_HEX
  if (!raw || !HEX_KEY.test(raw)) return null
  return Buffer.from(raw, 'hex')
}

function digest(key: Buffer, scope: string, raw: string): string {
  return createHmac('sha256', key).update(scope + '\0' + raw).digest('hex').slice(0, 32)
}

export type NativeStage = 'tool_result' | 'turn_end'

export interface CorrelationRefs extends Record<string, unknown> {
  evidence_contract_version: '1.0'
  session_ref: string
  turn_ref: string
  native_event_ref: string
  decision_request_ref: string
  native_stage: NativeStage
}

/** Null indicates unsupported or incomplete identity, never an inferred match.
 * The call ID is required for a tool-result event. These refs are purely
 * correlation claims; a separate native verifier must confirm the raw event.
 */
export function correlationRefs(
  key: Buffer | null,
  sessionId: string | null,
  turn: number | null,
  requestId: string | null,
  stage: NativeStage,
  callId: string | null = null,
): CorrelationRefs | null {
  if (!key || key.length !== 32 || !sessionId || sessionId.length > MAX_ID ||
      !Number.isSafeInteger(turn) || turn === null || turn < 1 ||
      !requestId || requestId.length > MAX_ID ||
      (stage === 'tool_result' && (!callId || callId.length > MAX_ID))) return null
  const scopedTurn = sessionId + '\0' + turn
  const nativeId = scopedTurn + '\0' + stage + (callId ? '\0' + callId : '')
  return {
    evidence_contract_version: '1.0',
    session_ref: digest(key, 'session', sessionId),
    turn_ref: digest(key, 'turn', scopedTurn),
    native_event_ref: digest(key, 'native_event', nativeId),
    decision_request_ref: digest(key, 'decision_request', requestId),
    native_stage: stage,
  }
}

/** Resolve once at isolated Adapter setup. No key bytes appear in telemetry. */
export function isolatedCorrelationKey(): Buffer | null {
  return keyFromEnvironment()
}

/** Optional private test harness capture when the platform logger is not
 * exported by the native headless CLI. This is NOT production telemetry:
 * explicit opt-in, private-root confinement, metadata-only, bounded, fail-open.
 */
export function writePrivateCorrelation(value: Record<string, unknown>): void {
  if (!keyFromEnvironment()) return
  const home = process.env.DSH_HOME
  const root = process.env.LOCAL_SYSTEM_ONE_EVIDENCE_PRIVATE_ROOT
  if (!home || !root) return
  try {
    const physicalRoot = realpathSync(root)
    const physicalHome = realpathSync(home)
    if (!physicalHome.startsWith(physicalRoot + sep)) return
    const filename = join(physicalHome, 'phase8_2b_correlation.private.jsonl')
    // Strong allowlist. Never include user prompts, raw request ids, native
    // Session/Tool IDs, credentials or arbitrary Adapter metadata.
    const fields = [
      'gate', 'native_stage', 'session_ref', 'turn_ref', 'native_event_ref',
      'decision_request_ref', 'action_status', 'evidence_status',
      'response_request_id_matches',
    ] as const
    const safe: Record<string, unknown> = {}
    for (const field of fields) {
      if (Object.prototype.hasOwnProperty.call(value, field)) safe[field] = value[field]
    }
    if (safe.gate !== 'completion' ||
        typeof safe.decision_request_ref !== 'string' ||
        typeof safe.native_event_ref !== 'string') return
    const fd = openSync(
      filename, constants.O_WRONLY | constants.O_APPEND | constants.O_CREAT |
      (constants.O_NOFOLLOW ?? 0), 0o600,
    )
    try {
      const stats = fstatSync(fd)
      if (!stats.isFile() || stats.size >= 256 * 1024 || (stats.mode & 0o077) !== 0) return
      writeSync(fd, JSON.stringify(safe) + '\n')
    } finally {
      closeSync(fd)
    }
  } catch {
    // Private test instrumentation must never delay or crash the native Agent.
  }
}
