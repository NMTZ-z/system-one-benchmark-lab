export type NativeStage = 'tool_result' | 'turn_end';
export interface CorrelationRefs extends Record<string, unknown> {
    evidence_contract_version: '1.0';
    session_ref: string;
    turn_ref: string;
    native_event_ref: string;
    decision_request_ref: string;
    native_stage: NativeStage;
}
/** Null indicates unsupported or incomplete identity, never an inferred match.
 * The call ID is required for a tool-result event. These refs are purely
 * correlation claims; a separate native verifier must confirm the raw event.
 */
export declare function correlationRefs(key: Buffer | null, sessionId: string | null, turn: number | null, requestId: string | null, stage: NativeStage, callId?: string | null): CorrelationRefs | null;
/** Resolve once at isolated Adapter setup. No key bytes appear in telemetry. */
export declare function isolatedCorrelationKey(): Buffer | null;
/** Optional private test harness capture when the platform logger is not
 * exported by the native headless CLI. This is NOT production telemetry:
 * explicit opt-in, private-root confinement, metadata-only, bounded, fail-open.
 */
export declare function writePrivateCorrelation(value: Record<string, unknown>): void;
