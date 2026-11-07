export const ADAPTER_CONTRACT_VERSION = '1.0';
export function toDecisionEnvelope(gate, decision) {
    const common = {
        adapter_contract_version: ADAPTER_CONTRACT_VERSION,
        request_id: decision.request_id,
        gate,
        decision_source: decision.decision_source,
        reason: decision.reason,
        backend: decision.backend,
        latency_ms: decision.latency_ms,
    };
    if (gate === 'search') {
        const value = decision;
        return {
            ...common,
            gate,
            decision: {
                value: value.decision,
                probability_search: value.probability_search,
            },
        };
    }
    if (gate === 'model_tier') {
        const value = decision;
        return {
            ...common,
            gate,
            decision: {
                value: value.tier,
                difficulty_score: value.difficulty_score,
                probability_strong: value.probability_strong,
            },
            confidence: value.confidence,
        };
    }
    if (gate === 'notification') {
        const value = decision;
        return {
            ...common,
            gate,
            decision: {
                value: value.delivery,
                notify_now: value.notify_now,
                priority_score: value.priority_score,
            },
            confidence: value.confidence,
        };
    }
    if (gate === 'retry_escalation') {
        const value = decision;
        return {
            ...common,
            gate,
            decision: {
                value: value.guarded_decision,
                raw_model_decision: value.raw_model_decision,
                safety_override_reason: value.safety_override_reason,
            },
            confidence: value.confidence,
        };
    }
    const value = decision;
    return {
        ...common,
        gate: 'completion',
        decision: {
            value: value.decision,
            probability_complete: value.probability_complete,
            probability_verify: value.probability_verify,
            probability_continue: value.probability_continue,
        },
        confidence: value.confidence,
    };
}
export function actionOutcome(status, reason) {
    return { status, reason };
}
export function telemetryRecord(adapterVersion, mode, envelope, outcome, extra = {}) {
    return {
        adapter_contract_version: ADAPTER_CONTRACT_VERSION,
        platform: 'deepseek_harness',
        adapter_version: adapterVersion,
        gate: envelope.gate,
        mode,
        decision: envelope.decision,
        decision_source: envelope.decision_source,
        reason: envelope.reason,
        backend: envelope.backend,
        latency_ms: envelope.latency_ms,
        action_status: outcome.status,
        action_reason: outcome.reason,
        request_id: envelope.request_id,
        ...extra,
    };
}
export function failureActionReason(error) {
    if (error instanceof DOMException && error.name === 'AbortError')
        return 'runtime_timeout';
    if (error instanceof Error) {
        if (/\bHTTP\s+\d{3}\b/.test(error.message))
            return 'runtime_http_error';
        if (/^invalid\s|must be in \[|response field/i.test(error.message))
            return 'malformed_response';
    }
    return 'runtime_error';
}
//# sourceMappingURL=contract.js.map