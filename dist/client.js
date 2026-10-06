function isRecord(value) {
    return typeof value === 'object' && value !== null && !Array.isArray(value);
}
function requiredString(value, key, contract) {
    const field = value[key];
    if (typeof field !== 'string' || field.length === 0) {
        throw new Error(`invalid ${contract} response field: ${key}`);
    }
    return field;
}
function requiredNumber(value, key, contract) {
    const field = value[key];
    if (typeof field !== 'number' || !Number.isFinite(field)) {
        throw new Error(`invalid ${contract} response field: ${key}`);
    }
    return field;
}
function requestId(value, contract) {
    const field = value.request_id;
    if (field !== null && field !== undefined && typeof field !== 'string') {
        throw new Error(`invalid ${contract} response field: request_id`);
    }
    return field ?? null;
}
export function parseSearchDecision(value) {
    const contract = 'search-gate';
    if (!isRecord(value)) {
        throw new Error(`invalid ${contract} response`);
    }
    const decision = requiredString(value, 'decision', contract);
    if (decision !== 'search' && decision !== 'no_search') {
        throw new Error(`invalid ${contract} response field: decision`);
    }
    const decisionSource = requiredString(value, 'decision_source', contract);
    if (decisionSource !== 'rule' && decisionSource !== 'model') {
        throw new Error(`invalid ${contract} response field: decision_source`);
    }
    const probabilitySearch = requiredNumber(value, 'probability_search', contract);
    if (probabilitySearch < 0 || probabilitySearch > 1) {
        throw new Error('probability_search must be in [0, 1]');
    }
    return {
        decision,
        decision_source: decisionSource,
        reason: requiredString(value, 'reason', contract),
        probability_search: probabilitySearch,
        backend: requiredString(value, 'backend', contract),
        latency_ms: requiredNumber(value, 'latency_ms', contract),
        request_id: requestId(value, contract),
    };
}
export function parseModelTierDecision(value) {
    const contract = 'model-tier-gate';
    if (!isRecord(value)) {
        throw new Error(`invalid ${contract} response`);
    }
    const tier = requiredString(value, 'tier', contract);
    if (tier !== 'fast' && tier !== 'strong') {
        throw new Error(`invalid ${contract} response field: tier`);
    }
    const decisionSource = requiredString(value, 'decision_source', contract);
    if (decisionSource !== 'rule' && decisionSource !== 'model') {
        throw new Error(`invalid ${contract} response field: decision_source`);
    }
    const difficultyScore = requiredNumber(value, 'difficulty_score', contract);
    const probabilityStrong = requiredNumber(value, 'probability_strong', contract);
    const confidence = requiredNumber(value, 'confidence', contract);
    if (probabilityStrong < 0 || probabilityStrong > 1) {
        throw new Error('probability_strong must be in [0, 1]');
    }
    if (confidence < 0 || confidence > 1) {
        throw new Error('confidence must be in [0, 1]');
    }
    return {
        tier,
        decision_source: decisionSource,
        reason: requiredString(value, 'reason', contract),
        difficulty_score: difficultyScore,
        probability_strong: probabilityStrong,
        confidence,
        backend: requiredString(value, 'backend', contract),
        latency_ms: requiredNumber(value, 'latency_ms', contract),
        request_id: requestId(value, contract),
    };
}
export function parseNotificationDecision(value) {
    const contract = 'notification-gate';
    if (!isRecord(value)) {
        throw new Error(`invalid ${contract} response`);
    }
    const delivery = requiredString(value, 'delivery', contract);
    if (!['silent', 'digest', 'notify_now'].includes(delivery)) {
        throw new Error(`invalid ${contract} response field: delivery`);
    }
    const notifyNow = value.notify_now;
    if (typeof notifyNow !== 'boolean') {
        throw new Error(`invalid ${contract} response field: notify_now`);
    }
    const decisionSource = requiredString(value, 'decision_source', contract);
    if (decisionSource !== 'rule' && decisionSource !== 'model') {
        throw new Error(`invalid ${contract} response field: decision_source`);
    }
    const priorityScore = requiredNumber(value, 'priority_score', contract);
    if (priorityScore < 0 || priorityScore > 4) {
        throw new Error('priority_score must be in [0, 4]');
    }
    const confidence = requiredNumber(value, 'confidence', contract);
    if (confidence < 0 || confidence > 1) {
        throw new Error('confidence must be in [0, 1]');
    }
    return {
        delivery: delivery,
        notify_now: notifyNow,
        decision_source: decisionSource,
        reason: requiredString(value, 'reason', contract),
        priority_score: priorityScore,
        confidence,
        backend: requiredString(value, 'backend', contract),
        latency_ms: requiredNumber(value, 'latency_ms', contract),
        request_id: requestId(value, contract),
    };
}
class GateClient {
    serviceUrl;
    timeoutMs;
    path;
    parser;
    constructor(serviceUrl, timeoutMs, path, parser) {
        this.serviceUrl = serviceUrl;
        this.timeoutMs = timeoutMs;
        this.path = path;
        this.parser = parser;
    }
    async post(payload) {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), this.timeoutMs);
        try {
            const response = await fetch(`${this.serviceUrl}${this.path}`, {
                method: 'POST',
                headers: { 'content-type': 'application/json' },
                body: JSON.stringify(payload),
                signal: controller.signal,
            });
            if (!response.ok) {
                throw new Error(`${this.path} HTTP ${response.status}`);
            }
            return this.parser(await response.json());
        }
        finally {
            clearTimeout(timeout);
        }
    }
    async decide(task, requestIdValue) {
        return this.post({ task, request_id: requestIdValue });
    }
}
export class SearchGateClient extends GateClient {
    constructor(serviceUrl, timeoutMs) {
        super(serviceUrl, timeoutMs, '/v1/workflows/search-gate', parseSearchDecision);
    }
}
export class ModelTierGateClient extends GateClient {
    constructor(serviceUrl, timeoutMs) {
        super(serviceUrl, timeoutMs, '/v1/workflows/model-tier-gate', parseModelTierDecision);
    }
}
export class NotificationGateClient extends GateClient {
    constructor(serviceUrl, timeoutMs) {
        super(serviceUrl, timeoutMs, '/v1/workflows/notification-gate', parseNotificationDecision);
    }
    async decide(event, requestIdValue, context = null, blockingFailure = false) {
        return this.post({
            event,
            context,
            urgency: 'auto',
            user_action_required: false,
            blocking_failure: blockingFailure,
            routine_update: false,
            request_id: requestIdValue,
        });
    }
}
//# sourceMappingURL=client.js.map