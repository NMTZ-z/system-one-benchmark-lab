import type { SearchDecision } from './types.js';
export declare function parseSearchDecision(value: unknown): SearchDecision;
export declare class SearchGateClient {
    private readonly serviceUrl;
    private readonly timeoutMs;
    constructor(serviceUrl: string, timeoutMs: number);
    decide(task: string, requestId: string): Promise<SearchDecision>;
}