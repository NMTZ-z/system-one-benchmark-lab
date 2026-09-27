const DEFAULT_SERVICE_URL = 'http://127.0.0.1:8787';
const DEFAULT_TIMEOUT_MS = 500;
export const AUDITED_HARD_NO_WEB_REASONS = new Set([
    'bounded_transform_task',
    'local_file_or_repo',
    'connected_app_data',
]);
export const VERIFIED_PUBLIC_WEB_TOOLS = new Set([
    'web_search',
    'web_fetch',
    'mcp__tavily__tavily_search',
]);
function normalizeServiceUrl(value) {
    const url = new URL(value);
    if (url.protocol !== 'http:' && url.protocol !== 'https:') {
        throw new Error('service_url must use http or https');
    }
    return url.toString().replace(/\/$/, '');
}
export function resolveConfig(input = {}) {
    const mode = input.mode ?? 'off';
    if (!['off', 'shadow', 'canary'].includes(mode)) {
        throw new Error('mode must be off, shadow, or canary');
    }
    const timeoutMs = input.timeout_ms ?? DEFAULT_TIMEOUT_MS;
    if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) {
        throw new Error('timeout_ms must be a positive finite number');
    }
    const canaryAcknowledged = input.canary_acknowledged ?? false;
    const effectiveMode = mode === 'canary' && !canaryAcknowledged ? 'shadow' : mode;
    return {
        mode,
        effectiveMode,
        serviceUrl: normalizeServiceUrl(input.service_url ?? DEFAULT_SERVICE_URL),
        timeoutMs,
        searchGateEnabled: input.search_gate_enabled ?? true,
        canaryAcknowledged,
    };
}
export function isVerifiedPublicWebTool(name) {
    return VERIFIED_PUBLIC_WEB_TOOLS.has(name);
}
export function hasCanaryAuthority(decision) {
    return (decision.decision === 'no_search'
        && decision.decision_source === 'rule'
        && decision.backend === 'rule'
        && AUDITED_HARD_NO_WEB_REASONS.has(decision.reason));
}
//# sourceMappingURL=policy.js.map