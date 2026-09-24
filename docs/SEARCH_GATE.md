# Search Gate v0.1

Date: 2026-09-24
Status: functional MVP

## Goal

Decide whether an agent should use external/current information before answering a task.

This is intentionally a hybrid policy rather than a pure model prediction.

## Why hybrid

A false negative can make an agent answer a current or externally grounded question from stale internal knowledge. That failure is more costly than one unnecessary search.

Search Gate therefore uses:

1. deterministic hard gates for obvious cases;
2. Local System One Noul for ambiguous cases;
3. conservative fallback when the model is uncertain.

## Endpoint

POST /v1/workflows/search-gate

Example request:

~~~json
{
  "task": "OpenAI 的 CEO 是谁？",
  "freshness": "auto",
  "source_scope": "auto",
  "external_lookup_required": false,
  "provided_context_sufficient": false,
  "request_id": "example-1"
}
~~~

Example response:

~~~json
{
  "workflow": "search_gate",
  "should_search": true,
  "decision": "search",
  "decision_source": "rule",
  "reason": "volatile_public_fact",
  "probability_search": 1.0,
  "confidence": 1.0,
  "backend": "rule",
  "route_reason": "search_gate:volatile_public_fact",
  "token_count": 0
}
~~~

## Hard-search conditions

Current implementation searches without model inference when:

- external lookup is explicitly required;
- freshness is current or recent;
- the task contains clear current/live language;
- the task asks for volatile public facts such as current leadership roles, price, availability, opening hours or service status.

Examples:

- 今天北京天气怎么样？
- OpenAI 的 CEO 是谁？
- What is the current exchange rate?
- Is this store open now?

## Hard-no-search conditions

Current implementation suppresses search when:

- source_scope is provided_only;
- source_scope is local_private;
- the caller explicitly says the provided context is sufficient;
- a static transformation request clearly targets supplied content.

Examples:

- rewrite this supplied paragraph;
- summarize this local meeting note;
- translate the following text.

## Model fallback

Ambiguous requests are converted to a Noul decision:

> Does answering this task correctly require looking up information outside the provided state, such as current public facts, recent events, live data, an external page, or information not supplied here?

The default policy only returns no_search when P(search) <= 0.40.

This is deliberately conservative. The threshold is a product baseline, not a trained optimum.

## Real smoke findings

Initial real 421M MLX smoke exposed an important failure:

- task: OpenAI 的 CEO 是谁？
- model-only P(search): 0.181
- model-only decision: no_search

That is unacceptable for a volatile public role.

The product policy was therefore changed so volatile public facts are hard-search cases.

After the fix:

- OpenAI 的 CEO 是谁？ -> search / volatile_public_fact
- 今天北京天气怎么样？ -> search / current_language
- 解释 Python 里 list 和 tuple 的区别。 -> no_search / model_confident_local_answer
- supplied local summary -> no_search / source_scope_provided_only

This is the intended development loop: real workflow failure -> explicit product policy -> regression test.

## Python client

~~~python
from local_system_one import LocalSystemOneClient

client = LocalSystemOneClient("http://127.0.0.1:8787")
decision = client.search_gate(
    "OpenAI 的 CEO 是谁？",
    request_id="agent-task-123",
)

if decision["should_search"]:
    # invoke the agent's web/search tool
    ...
~~~

## Privacy

The service does not persist raw task/context by default.

Metrics record backend, route reason and latency. Rule decisions are counted as backend=rule.

## Known limitations

- The 421M Typed Decisions checkpoint was not trained specifically for search gating.
- Volatile-fact rules are deliberately conservative and incomplete.
- Multilingual phrasing outside the current rule set may still reach the model.
- Search Gate does not decide which search tool to use yet.
- Search result quality is outside this workflow; this only decides whether lookup is needed.

## Next validation

Do not create a synthetic leaderboard.

Deploy Search Gate into real agent traffic, retain only privacy-safe decision metadata by default, sample disagreements for manual review, and build the future Agent Decision Blind Set from real use.
