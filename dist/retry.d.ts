/** Phase 8C: frozen upstream tool identity policy. Never inspect error text or arguments. */
import type { FailureContext, SessionEventLike } from './types.js';
type Operation = FailureContext['operation'];
export declare function operationFromToolName(name: string): Operation | null;
export declare function resultCallId(event: SessionEventLike): string | null;
/** Accept only structured DSH failure, never infer a failure from content text. */
export declare function failureFromToolResult(event: SessionEventLike, operation: Operation): FailureContext | null;
export {};
