import { randomUUID } from 'node:crypto';
import { ModelTierGateClient, NotificationGateClient, SearchGateClient } from './client.js';
import { hasCanaryAuthority, hasModelTierCanaryAuthority, isVerifiedPublicWebTool, isVerifiedReasoningDowngradeRoute, resolveConfig, } from './policy.js';
import { TurnDecisionState } from './state.js';
export const name = 'local-system-one-dsh';
const MAX_NOTIFICATION_CHARS = 6000;
function asSessionId(session) {
    if (session?.id === undefined || session.id === null)
        return null;
    const value = String(session.id);
    return value.length > 0 ? value : null;
}
function asPositiveInteger(value) {
    return typeof value === 'number' && Number.isInteger(value) && value > 0 ? value : null;
}
function contentText(content) {
    if (typeof content === 'string')
        return content.trim();
    if (!Array.isArray(content))
        return '';
    const parts = [];
    for (const block of content) {
        if (typeof block === 'string') {
            const text = block.trim();
            if (text)
                parts.push(text);
            continue;
        }
        if (typeof block !== 'object' || block === null)
            continue;
        const record = block;
        if (record.type === 'text' && typeof record.text === 'string') {
            const text = record.text.trim();
            if (text)
                parts.push(text);
        }
    }
    return parts.join('\n').trim();
}
function taskText(messages) {
    if (!messages)
        return '';
    const parts = [];
    for (const message of messages) {
        if (message.role !== undefined && message.role !== 'user')
            continue;
        const text = contentText(message.content);
        if (text)
            parts.push(text);
    }
    return parts.join('\n').trim();
}
function assistantEventText(event) {
    const message = event.data?.message;
    if (typeof message !== 'object' || message === null)
        return '';
    const content = message.content;
    return contentText(content).slice(0, MAX_NOTIFICATION_CHARS);
}
function turnReasonKind(value) {
    if (typeof value !== 'object' || value === null)
        return null;
    const kind = value.kind;
    return typeof kind === 'string' && kind.length > 0 ? kind : null;
}
function turnKey(sessionId, turn) {
    return `${sessionId}:${turn}`;
}
function errorType(error) {
    if (error instanceof Error && error.name)
        return error.name;
    return typeof error;
}
function logSearchDecision(ctx, mode, decision) {
    ctx.logger?.info?.(`[local-system-one-dsh] ${JSON.stringify({
        gate: 'search',
        mode,
        request_id: decision.request_id,
        decision: decision.decision,
        decision_source: decision.decision_source,
        reason: decision.reason,
        probability_search: decision.probability_search,
        backend: decision.backend,
        latency_ms: decision.latency_ms,
    })}`);
}
function logModelTierDecision(ctx, mode, decision) {
    ctx.logger?.info?.(`[local-system-one-dsh] ${JSON.stringify({
        gate: 'model_tier',
        mode,
        request_id: decision.request_id,
        tier: decision.tier,
        decision_source: decision.decision_source,
        reason: decision.reason,
        difficulty_score: decision.difficulty_score,
        probability_strong: decision.probability_strong,
        confidence: decision.confidence,
        backend: decision.backend,
        latency_ms: decision.latency_ms,
    })}`);
}
function logNotificationDecision(ctx, mode, decision, eventChars) {
    ctx.logger?.info?.(`[local-system-one-dsh] ${JSON.stringify({
        gate: 'notification',
        mode,
        request_id: decision.request_id,
        delivery: decision.delivery,
        notify_now: decision.notify_now,
        decision_source: decision.decision_source,
        reason: decision.reason,
        priority_score: decision.priority_score,
        confidence: decision.confidence,
        backend: decision.backend,
        latency_ms: decision.latency_ms,
        event_chars: eventChars,
    })}`);
}
export function apply(ctx, inputConfig = {}) {
    const config = resolveConfig(inputConfig);
    const state = new TurnDecisionState();
    const searchClient = new SearchGateClient(config.serviceUrl, config.timeoutMs);
    const modelTierClient = new ModelTierGateClient(config.serviceUrl, config.timeoutMs);
    const notificationClient = new NotificationGateClient(config.serviceUrl, config.timeoutMs);
    const notificationCandidates = new Map();
    if (config.mode === 'canary' && config.effectiveMode === 'shadow') {
        ctx.logger?.warn?.('[local-system-one-dsh] canary requested without canary_acknowledged=true; using shadow');
    }
    ctx.on('session/event', (session, event) => {
        if (config.effectiveMode === 'off'
            || (!config.searchGateEnabled && !config.modelTierGateEnabled && !config.notificationGateEnabled))
            return;
        const sessionId = asSessionId(session);
        if (!sessionId || typeof event?.type !== 'string')
            return;
        const turn = asPositiveInteger(event.data?.turn);
        if (event.type === 'turn/start' && turn !== null) {
            state.beginTurn(sessionId, turn);
            return;
        }
        if (config.notificationGateEnabled
            && event.type === 'assistant/message'
            && turn !== null) {
            const text = assistantEventText(event);
            if (text)
                notificationCandidates.set(turnKey(sessionId, turn), text);
            return;
        }
        if (event.type === 'turn/end' && turn !== null) {
            const candidateKey = turnKey(sessionId, turn);
            let eventText = notificationCandidates.get(candidateKey) ?? '';
            notificationCandidates.delete(candidateKey);
            const reasonKind = turnReasonKind(event.data?.reason);
            const blockingFailure = reasonKind === 'error' || reasonKind === 'failed';
            if (!eventText && blockingFailure) {
                eventText = 'Agent turn ended with a blocking failure before producing a final response.';
            }
            if (config.notificationGateEnabled && eventText) {
                const requestId = randomUUID();
                const context = { turn, reason_kind: reasonKind };
                void notificationClient
                    .decide(eventText, requestId, context, blockingFailure)
                    .then(decision => logNotificationDecision(ctx, config.effectiveMode, decision, eventText.length))
                    .catch(error => {
                    ctx.logger?.warn?.(`[local-system-one-dsh] notification gate unavailable; fail-open (${errorType(error)})`);
                });
            }
            state.clearTurn(sessionId, turn);
            return;
        }
        if (event.type === 'session/end' || event.type === 'session/close') {
            state.clearSession(sessionId);
            for (const key of notificationCandidates.keys()) {
                if (key.startsWith(`${sessionId}:`))
                    notificationCandidates.delete(key);
            }
        }
    });
    ctx.on('agent/pre-step', async (input, next) => {
        if (config.effectiveMode === 'off'
            || (!config.searchGateEnabled && !config.modelTierGateEnabled))
            return next();
        const step = asPositiveInteger(input.step);
        const turn = asPositiveInteger(input.turn);
        const sessionId = asSessionId(input.agent?.session);
        if (step !== 1 || turn === null || !sessionId) {
            return next();
        }
        state.beginTurn(sessionId, turn);
        const task = taskText(input.messages);
        if (!task)
            return next();
        const requestId = randomUUID();
        if (config.searchGateEnabled) {
            try {
                const decision = await searchClient.decide(task, requestId);
                state.setSearchDecision(sessionId, turn, {
                    ...decision,
                    observed_at_ms: Date.now(),
                });
                logSearchDecision(ctx, config.effectiveMode, decision);
            }
            catch (error) {
                ctx.logger?.warn?.(`[local-system-one-dsh] search gate unavailable; fail-open (${errorType(error)})`);
            }
        }
        if (config.modelTierGateEnabled) {
            try {
                const decision = await modelTierClient.decide(task, requestId);
                state.setModelTierDecision(sessionId, turn, {
                    ...decision,
                    observed_at_ms: Date.now(),
                });
                logModelTierDecision(ctx, config.effectiveMode, decision);
            }
            catch (error) {
                ctx.logger?.warn?.(`[local-system-one-dsh] model tier gate unavailable; fail-open (${errorType(error)})`);
            }
        }
        return next();
    });
    if (config.effectiveMode === 'canary'
        && config.modelTierGateEnabled
        && config.canaryReasoningDowngradeEnabled) {
        ctx.on('agent/request', async (input, next) => {
            const original = await next();
            try {
                const step = asPositiveInteger(input.step);
                const turn = asPositiveInteger(input.turn);
                const sessionId = asSessionId(input.agent?.session);
                if (step !== 1 || turn === null || !sessionId)
                    return original;
                const decision = state.getModelTierDecision(sessionId, turn);
                if (!decision || !hasModelTierCanaryAuthority(decision))
                    return original;
                const provider = typeof original?.provider === 'string' ? original.provider : '';
                const model = typeof original?.model === 'string' ? original.model : '';
                if (!provider || !model || !isVerifiedReasoningDowngradeRoute(provider, model)) {
                    return original;
                }
                if (original.reasoningEffort !== 'high')
                    return original;
                const updated = { ...original, reasoningEffort: 'low' };
                ctx.logger?.info?.(`[local-system-one-dsh] ${JSON.stringify({
                    gate: 'model_tier',
                    mode: 'canary',
                    action: 'reasoning_effort_downgrade',
                    provider,
                    model,
                    from: 'high',
                    to: 'low',
                    reason: decision.reason,
                    request_id: decision.request_id,
                })}`);
                return updated;
            }
            catch (error) {
                ctx.logger?.warn?.(`[local-system-one-dsh] model tier mutation unavailable; fail-open (${errorType(error)})`);
                return original;
            }
        });
    }
    ctx.on('tools/pre-execute', async (execution, next) => {
        if (config.effectiveMode !== 'canary'
            || !config.searchGateEnabled
            || !config.canaryWebFilterEnabled)
            return next();
        const toolName = typeof execution.name === 'string' ? execution.name : '';
        if (!toolName || !isVerifiedPublicWebTool(toolName)) {
            return next();
        }
        const sessionId = asSessionId(execution.agent?.session);
        if (!sessionId)
            return next();
        const decision = state.getCurrentSearchDecision(sessionId);
        if (!decision || !hasCanaryAuthority(decision)) {
            return next();
        }
        return {
            kind: 'deny',
            reason: `Local System One hard no-Web rule: ${decision.reason}`,
        };
    });
}
export { ModelTierGateClient, NotificationGateClient, SearchGateClient, parseModelTierDecision, parseNotificationDecision, parseSearchDecision, } from './client.js';
export { AUDITED_HARD_FAST_REASONS, AUDITED_HARD_NO_WEB_REASONS, VERIFIED_PUBLIC_WEB_TOOLS, VERIFIED_REASONING_DOWNGRADE_ROUTES, hasCanaryAuthority, hasModelTierCanaryAuthority, isVerifiedPublicWebTool, isVerifiedReasoningDowngradeRoute, resolveConfig, } from './policy.js';
export { TurnDecisionState } from './state.js';
//# sourceMappingURL=index.js.map