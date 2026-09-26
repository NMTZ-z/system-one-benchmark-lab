# Notification Gate v0.1

Date: 2026-09-24
Status: functional MVP

## Goal

Decide whether an agent event should remain silent, be included in a digest, or interrupt the user now.

Output delivery levels:

- silent
- digest
- notify_now

This is more useful than a binary notify/no-notify flag for 24/7 agents.

## Endpoint

POST /v1/workflows/notification-gate

Request fields:

- event
- optional context
- urgency: auto / low / medium / high / critical
- user_action_required
- blocking_failure
- routine_update
- optional deadline_minutes
- request_id

## Policy

### Hard notify_now

Immediate notification bypasses model inference when:

- urgency is critical;
- the event is a blocking failure;
- a deadline is within 30 minutes;
- high/critical urgency also requires user action.

### Hard digest

A routine low-urgency update with no required user action goes directly to digest.

### Model fallback

Other events become a 0–4 priority Score:

0. no user value; silent
1. low value; log/later digest
2. useful but not urgent; digest
3. important; notify soon
4. urgent/blocking; interrupt now

Initial thresholds:

- below 1.25 -> silent
- 1.25 to below 2.75 -> digest
- 2.75 and above -> notify_now

These are initial product thresholds, not calibrated optima.

## Real 421M smoke

| Event | Result | Source | Priority |
|---|---|---|---:|
| nightly NAS backup completed | digest | rule | 1.0 |
| agent blocked waiting for user approval | notify_now | rule | 4.0 |
| background indexing completed; no action required | digest | model | 1.8512 |
| long-running migration finished with reviewable result | digest | model | 2.3052 |
| deployment decision due within 20 minutes | notify_now | rule | 4.0 |

The behavior is intentionally conservative about interruption: useful progress can wait for a digest unless urgency/action requirements justify immediate interruption.

## Product role

~~~text
agent event
    |
    v
Notification Gate
  /      |       \
silent  digest  notify_now
~~~

A caller can map these to:

- silent -> store only;
- digest -> batch into scheduled summary;
- notify_now -> send immediate message/push.

## Privacy

Raw event/context is not persisted by default. Service metrics record backend, route reason and latency.

## Known limitations

- The current checkpoint is not specifically trained on personal notification preferences.
- User preference learning is not implemented yet.
- Duplicate-event suppression belongs in a higher event layer.
- Quiet hours are not implemented here; the caller can combine delivery with schedule policy.
- Digest scheduling itself is outside this gate.

## Next validation

Deploy against real agent events and collect privacy-safe outcome signals:

- user opened/acted on notification;
- user dismissed it;
- event was later escalated;
- digest item was useful;
- immediate notification was unnecessary;
- important event was missed.

Those outcomes should drive future threshold tuning and any personalized training.