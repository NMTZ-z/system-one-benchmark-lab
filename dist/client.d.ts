import type { ModelTierDecision, NotificationDecision, SearchDecision } from './types.js';
export declare function parseSearchDecision(value: unknown): SearchDecision;
export declare function parseModelTierDecision(value: unknown): ModelTierDecision;
export declare function parseNotificationDecision(value: unknown): NotificationDecision;
declare class GateClient<T> {
    private readonly serviceUrl;
    private readonly timeoutMs;
    private readonly path;
    private readonly parser;
    constructor(serviceUrl: string, timeoutMs: number, path: string, parser: (value: unknown) => T);
    protected post(payload: Record<string, unknown>): Promise<T>;
    decide(task: string, requestIdValue: string): Promise<T>;
}
export declare class SearchGateClient extends GateClient<SearchDecision> {
    constructor(serviceUrl: string, timeoutMs: number);
}
export declare class ModelTierGateClient extends GateClient<ModelTierDecision> {
    constructor(serviceUrl: string, timeoutMs: number);
}
export declare class NotificationGateClient extends GateClient<NotificationDecision> {
    constructor(serviceUrl: string, timeoutMs: number);
    decide(event: string, requestIdValue: string, context?: Record<string, unknown> | null, blockingFailure?: boolean): Promise<NotificationDecision>;
}
export {};
