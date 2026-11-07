import type { CompletionDecision, CompletionExecutionState, ModelTierDecision, NotificationDecision, SearchDecision, FailureContext, RetryEscalationDecision } from './types.js';
export declare function parseSearchDecision(value: unknown): SearchDecision;
export declare function parseModelTierDecision(value: unknown): ModelTierDecision;
export declare function parseNotificationDecision(value: unknown): NotificationDecision;
export declare function parseCompletionDecision(value: unknown): CompletionDecision;
declare class GateClient<T> {
    private readonly serviceUrl;
    private readonly timeoutMs;
    private readonly path;
    private readonly parser;
    constructor(serviceUrl: string, timeoutMs: number, path: string, parser: (value: unknown) => T);
    protected post(payload: Record<string, unknown>): Promise<T>;
    protected decideTask(task: string, requestIdValue: string): Promise<T>;
}
export declare class SearchGateClient extends GateClient<SearchDecision> {
    constructor(serviceUrl: string, timeoutMs: number);
    decide(task: string, requestIdValue: string): Promise<SearchDecision>;
}
export declare class ModelTierGateClient extends GateClient<ModelTierDecision> {
    constructor(serviceUrl: string, timeoutMs: number);
    decide(task: string, requestIdValue: string): Promise<ModelTierDecision>;
}
export declare class NotificationGateClient extends GateClient<NotificationDecision> {
    constructor(serviceUrl: string, timeoutMs: number);
    decide(event: string, requestIdValue: string, context?: Record<string, unknown> | null, blockingFailure?: boolean): Promise<NotificationDecision>;
}
export declare class CompletionGateClient extends GateClient<CompletionDecision> {
    constructor(serviceUrl: string, timeoutMs: number);
    decide(task: string, currentResult: string, executionState: CompletionExecutionState, requestIdValue: string): Promise<CompletionDecision>;
}
export declare function parseRetryEscalationDecision(value: unknown): RetryEscalationDecision;
export declare class RetryEscalationGateClient extends GateClient<RetryEscalationDecision> {
    constructor(serviceUrl: string, timeoutMs: number);
    decide(context: FailureContext, requestIdValue: string): Promise<RetryEscalationDecision>;
}
export {};
