#!/usr/bin/env python3
"""Replay real Hermes turns through Local System One without modifying Hermes.

Raw user content is written only under a caller-specified private output path and
must remain git-ignored. The processed summary contains aggregate metrics only.

Observed public/external tool use is a WEAK behavior label, not ground truth:
Hermes can search unnecessarily, fail to search when it should, or access the
network through a generic terminal command that this detector cannot see.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
import sqlite3
import statistics
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

DEFAULT_PROFILES = ("default", "sisi", "lili", "susu", "vivi", "xixi", "yaoyao")
PUBLIC_TOOL_EXACT = {
    "web_search",
    "web_extract",
    "browser_exec",
    "mcp__xiaohongshu_mcp__search_feeds",
    "mcp__xiaohongshu_mcp__get_feed_detail",
    "mcp__xiaohongshu_mcp__list_feeds",
}
PUBLIC_TOOL_PREFIXES = (
    "browser_",
    "mcp__amap",
    "mcp__baidu",
    "mcp__12306",
)
CRON_MARKER = "[IMPORTANT: You are running as a scheduled cron job."
SYNTHETIC_USER_PREFIXES = (
    "[CONTEXT COMPACTION",
    "[IMPORTANT: Background process",
    "↪ Redirected current run",
)
KANBAN_TRIGGER = re.compile(r"^work kanban task\s+(\S+)\s*$", re.IGNORECASE)


@dataclass
class Turn:
    profile: str
    source: str
    session_id: str
    message_id: int
    timestamp: float
    content: str
    context: str
    task_source: str
    tool_names: list[str]
    tool_count: int
    span_messages: int
    observed_public_lookup: bool

    @property
    def private_id(self) -> str:
        raw = f"{self.profile}:{self.session_id}:{self.message_id}".encode()
        return hashlib.sha256(raw).hexdigest()[:16]


def profile_db(profile: str) -> Path:
    home = Path.home() / ".hermes"
    return (
        home / "state.db"
        if profile == "default"
        else home / "profiles" / profile / "state.db"
    )


def visible_text(value: Any) -> str:
    if isinstance(value, str):
        raw = value.strip()
        if raw[:1] in "[{":
            try:
                parsed = json.loads(raw)
            except (ValueError, TypeError):
                return raw
            nested = visible_text(parsed)
            return nested or raw
        return raw
    if isinstance(value, list):
        return "\n".join(part for item in value if (part := visible_text(item)))
    if isinstance(value, dict):
        preferred = []
        for key in ("text", "content", "message", "prompt", "query"):
            if key in value and (part := visible_text(value[key])):
                preferred.append(part)
        return "\n".join(preferred)
    return ""


def _kanban_tasks() -> dict[str, tuple[str, str]]:
    result: dict[str, tuple[str, str]] = {}
    home = Path.home() / ".hermes"
    candidates = [home / "kanban.db"] + sorted(
        (home / "kanban" / "boards").glob("*/kanban.db")
    )
    for path in candidates:
        if not path.exists() or path.stat().st_size == 0:
            continue
        try:
            con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            if not con.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='tasks'"
            ).fetchone():
                con.close()
                continue
            for task_id, title, body in con.execute(
                "SELECT id, title, body FROM tasks"
            ):
                result[str(task_id)] = (str(title or ""), str(body or ""))
            con.close()
        except sqlite3.Error:
            continue
    return result


KANBAN_TASKS = _kanban_tasks()


def strip_cron_wrapper(text: str) -> str:
    clean = text.strip()
    start = clean.find(CRON_MARKER)
    if start >= 0:
        end = clean.find("]\n\n", start)
        if end >= 0:
            clean = clean[end + 3 :].strip()

    if clean.startswith("## Your previous run's output"):
        # Hermes may recursively embed the previous cron report, which itself contains
        # older prompts. The actual current task follows the OUTERMOST closing fence.
        fence_end = clean.rfind("\n```\n")
        if fence_end >= 0:
            tail = clean[fence_end + len("\n```\n") :].strip()
            if tail:
                clean = tail
    return clean or text


def normalize_task(content: str, source: str, max_chars: int) -> tuple[str, str]:
    clean = content.strip()
    if source == "kanban":
        match = KANBAN_TRIGGER.fullmatch(" ".join(clean.split()))
        if match:
            task = KANBAN_TASKS.get(match.group(1))
            if task:
                title, body = task
                resolved = "\n\n".join(
                    part.strip() for part in (title, body) if part.strip()
                )
                if resolved:
                    return resolved[:max_chars], "kanban_task"
            return clean[:max_chars], "kanban_opaque_trigger"
    if source == "cron":
        return strip_cron_wrapper(clean)[:max_chars], "cron_prompt"
    return clean[:max_chars], "user_message"


def recent_context(rows: list[sqlite3.Row], start: int, max_chars: int = 2000) -> str:
    parts: list[str] = []
    remaining = max_chars
    for item in reversed(rows[:start]):
        if item["role"] not in {"user", "assistant"}:
            continue
        text = visible_text(item["content"]).strip()
        if not text or text.startswith("[System:"):
            continue
        piece = text[-remaining:]
        parts.append(f"{item['role']}: {piece}")
        remaining -= len(piece)
        if remaining <= 0 or len(parts) >= 4:
            break
    return "\n".join(reversed(parts))


def is_public_lookup_tool(name: str) -> bool:
    clean = (name or "").strip().lower()
    if clean in PUBLIC_TOOL_EXACT:
        return True
    return any(clean.startswith(prefix) for prefix in PUBLIC_TOOL_PREFIXES)


def load_turns(profile: str, max_chars: int) -> list[Turn]:
    path = profile_db(profile)
    if not path.exists():
        return []
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    sessions = {
        row["id"]: (row["source"] or "unknown")
        for row in con.execute(
            "SELECT id, source FROM sessions WHERE COALESCE(hidden,0)=0"
        )
    }
    turns: list[Turn] = []
    for session_id, source in sessions.items():
        rows = list(
            con.execute(
                """
                SELECT id, role, content, tool_name, timestamp
                FROM messages
                WHERE session_id=? AND active=1
                ORDER BY id
                """,
                (session_id,),
            )
        )
        user_positions = [i for i, row in enumerate(rows) if row["role"] == "user"]
        for pos_index, start in enumerate(user_positions):
            row = rows[start]
            raw_content = visible_text(row["content"])
            if len(raw_content.strip()) < 4:
                continue
            stripped = raw_content.lstrip()
            if source != "cron" and stripped.startswith("[System:"):
                continue
            if stripped.startswith(SYNTHETIC_USER_PREFIXES):
                continue
            content, task_source = normalize_task(raw_content, str(source), max_chars)
            if len(content.strip()) < 4:
                continue
            context = recent_context(rows, start)
            end = (
                user_positions[pos_index + 1]
                if pos_index + 1 < len(user_positions)
                else len(rows)
            )
            span = rows[start + 1 : end]
            tool_names = [
                str(item["tool_name"] or "") for item in span if item["role"] == "tool"
            ]
            turns.append(
                Turn(
                    profile=profile,
                    source=str(source),
                    session_id=str(session_id),
                    message_id=int(row["id"]),
                    timestamp=float(row["timestamp"] or 0.0),
                    content=content[:max_chars],
                    context=context,
                    task_source=task_source,
                    tool_names=tool_names,
                    tool_count=len(tool_names),
                    span_messages=len(span),
                    observed_public_lookup=any(
                        is_public_lookup_tool(name) for name in tool_names
                    ),
                )
            )
    con.close()
    return turns


def proportional_take(
    groups: dict[str, list[Turn]], n: int, rng: random.Random
) -> list[Turn]:
    """Take approximately proportional samples while preserving profile diversity."""
    if n <= 0:
        return []
    total = sum(len(v) for v in groups.values())
    if total <= n:
        out = [x for values in groups.values() for x in values]
        rng.shuffle(out)
        return out

    quotas: dict[str, int] = {}
    fractions: list[tuple[float, str]] = []
    used = 0
    for key, values in groups.items():
        exact = n * len(values) / total
        base = min(len(values), math.floor(exact))
        if values and base == 0:
            base = 1
        quotas[key] = base
        used += base
        fractions.append((exact - math.floor(exact), key))

    while used > n:
        for _, key in sorted(fractions):
            if used <= n:
                break
            if quotas[key] > 1:
                quotas[key] -= 1
                used -= 1
    while used < n:
        progressed = False
        for _, key in sorted(fractions, reverse=True):
            if used >= n:
                break
            if quotas[key] < len(groups[key]):
                quotas[key] += 1
                used += 1
                progressed = True
        if not progressed:
            break

    out: list[Turn] = []
    for key, values in groups.items():
        local = list(values)
        rng.shuffle(local)
        out.extend(local[: quotas[key]])
    rng.shuffle(out)
    return out[:n]


def stratified_sample(
    turns: list[Turn], n: int, positive_fraction: float, seed: int
) -> list[Turn]:
    rng = random.Random(seed)
    n_pos = round(n * positive_fraction)
    n_neg = n - n_pos
    positives: dict[str, list[Turn]] = defaultdict(list)
    negatives: dict[str, list[Turn]] = defaultdict(list)
    for turn in turns:
        (positives if turn.observed_public_lookup else negatives)[turn.profile].append(
            turn
        )
    selected = proportional_take(positives, n_pos, rng) + proportional_take(
        negatives, n_neg, rng
    )
    rng.shuffle(selected)
    return selected


def post_json(
    base_url: str, path: str, payload: dict[str, Any], timeout: float
) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode()
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        value = json.loads(response.read().decode())
    if not isinstance(value, dict):
        raise TypeError("response must be a JSON object")
    return value


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * q
    lo = math.floor(index)
    hi = math.ceil(index)
    if lo == hi:
        return ordered[lo]
    return ordered[lo] * (hi - index) + ordered[hi] * (index - lo)


def median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profiles", default=",".join(DEFAULT_PROFILES))
    parser.add_argument("--sample-size", type=int, default=200)
    parser.add_argument("--positive-fraction", type=float, default=0.5)
    parser.add_argument("--seed", type=int, default=20260925)
    parser.add_argument("--max-chars", type=int, default=4000)
    parser.add_argument("--base-url", default="http://127.0.0.1:8787")
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument(
        "--private-output",
        type=Path,
        default=Path("private/hermes-system-one-replay/replay-200.json"),
    )
    parser.add_argument(
        "--summary-output",
        type=Path,
        default=Path("results/processed/hermes-system-one-history-replay-summary.json"),
    )
    args = parser.parse_args()

    if not 0 <= args.positive_fraction <= 1:
        raise SystemExit("--positive-fraction must be in [0,1]")

    profiles = [item.strip() for item in args.profiles.split(",") if item.strip()]
    all_turns: list[Turn] = []
    for profile in profiles:
        all_turns.extend(load_turns(profile, args.max_chars))

    population_by_profile = Counter(turn.profile for turn in all_turns)
    population_lookup_by_profile = Counter(
        turn.profile for turn in all_turns if turn.observed_public_lookup
    )
    population_by_source = Counter(turn.source for turn in all_turns)
    population_task_source = Counter(turn.task_source for turn in all_turns)
    population_lookup_by_source = Counter(
        turn.source for turn in all_turns if turn.observed_public_lookup
    )

    sample = stratified_sample(
        all_turns, args.sample_size, args.positive_fraction, args.seed
    )
    private_rows: list[dict[str, Any]] = []
    errors = 0
    started_all = time.perf_counter()

    for index, turn in enumerate(sample, 1):
        row = {
            "private_id": turn.private_id,
            **asdict(turn),
            "search": None,
            "model_tier": None,
            "roundtrip_ms": None,
            "error": None,
        }
        started = time.perf_counter()
        try:
            search = post_json(
                args.base_url,
                "/v1/workflows/search-gate",
                {
                    "task": turn.content,
                    "context": turn.context or None,
                    "request_id": turn.private_id,
                },
                args.timeout,
            )
            tier = post_json(
                args.base_url,
                "/v1/workflows/model-tier-gate",
                {
                    "task": turn.content,
                    "context": turn.context or None,
                    "request_id": turn.private_id,
                },
                args.timeout,
            )
            row["search"] = search
            row["model_tier"] = tier
        except (
            urllib.error.URLError,
            TimeoutError,
            ValueError,
            TypeError,
            OSError,
        ) as exc:
            errors += 1
            row["error"] = type(exc).__name__
        row["roundtrip_ms"] = (time.perf_counter() - started) * 1000.0
        private_rows.append(row)
        if index % 25 == 0:
            print(f"replayed {index}/{len(sample)} errors={errors}", flush=True)

    args.private_output.parent.mkdir(parents=True, exist_ok=True)
    args.private_output.write_text(
        json.dumps(private_rows, ensure_ascii=False, indent=2)
    )

    valid = [row for row in private_rows if row["search"] and row["model_tier"]]
    confusion = Counter()
    search_reasons = Counter()
    search_backends = Counter()
    tier_counts = Counter()
    tier_backends = Counter()
    per_profile = defaultdict(Counter)
    per_source = defaultdict(Counter)
    roundtrips = []
    gate_latencies = []
    tool_counts_by_tier = defaultdict(list)
    span_by_tier = defaultdict(list)

    for row in valid:
        observed = bool(row["observed_public_lookup"])
        predicted = bool(row["search"].get("should_search"))
        key = (
            "tp"
            if observed and predicted
            else "fn_candidate"
            if observed and not predicted
            else "fp_candidate"
            if not observed and predicted
            else "tn"
        )
        confusion[key] += 1
        search_reasons[str(row["search"].get("reason"))] += 1
        search_backends[str(row["search"].get("backend"))] += 1
        tier = str(row["model_tier"].get("tier"))
        tier_counts[tier] += 1
        tier_backends[str(row["model_tier"].get("backend"))] += 1
        per_profile[row["profile"]][key] += 1
        per_profile[row["profile"]][f"tier_{tier}"] += 1
        per_source[row["source"]][key] += 1
        per_source[row["source"]][f"tier_{tier}"] += 1
        roundtrips.append(float(row["roundtrip_ms"]))
        gate_latencies.extend(
            float(value)
            for value in (
                row["search"].get("latency_ms"),
                row["model_tier"].get("latency_ms"),
            )
            if isinstance(value, (int, float))
        )
        tool_counts_by_tier[tier].append(int(row["tool_count"]))
        span_by_tier[tier].append(int(row["span_messages"]))

    tp = confusion["tp"]
    fn = confusion["fn_candidate"]
    fp = confusion["fp_candidate"]
    tn = confusion["tn"]

    def ratio(a: int, b: int) -> float | None:
        return a / b if b else None

    summary = {
        "generated_at": time.time(),
        "method": {
            "profiles": profiles,
            "sample_size_requested": args.sample_size,
            "sample_size_actual": len(sample),
            "positive_fraction_target": args.positive_fraction,
            "seed": args.seed,
            "max_task_chars": args.max_chars,
            "raw_content_committed": False,
            "private_output": str(args.private_output),
            "observed_public_lookup_is_weak_label": True,
            "limitations": [
                "Observed tool use is not ground truth; Hermes can search unnecessarily or omit needed search.",
                "Generic terminal/network access is not detectable from tool_name alone.",
                "The balanced sample is not prevalence-representative.",
                "Cron wrappers and Kanban opaque triggers are normalized before replay.",
                "Recent conversation context is provided to the local gates but raw context stays private.",
            ],
        },
        "population": {
            "turns": len(all_turns),
            "observed_public_lookup_turns": sum(
                t.observed_public_lookup for t in all_turns
            ),
            "by_profile": {
                p: {
                    "turns": population_by_profile[p],
                    "observed_public_lookup_turns": population_lookup_by_profile[p],
                }
                for p in profiles
            },
            "task_normalization": dict(population_task_source),
            "by_source": {
                source: {
                    "turns": count,
                    "observed_public_lookup_turns": population_lookup_by_source[source],
                }
                for source, count in sorted(population_by_source.items())
            },
        },
        "replay": {
            "valid": len(valid),
            "errors": errors,
            "elapsed_seconds": time.perf_counter() - started_all,
            "roundtrip_pair_ms": {
                "mean": statistics.fmean(roundtrips) if roundtrips else None,
                "p50": percentile(roundtrips, 0.50),
                "p95": percentile(roundtrips, 0.95),
                "max": max(roundtrips) if roundtrips else None,
            },
            "gate_model_latency_ms": {
                "p50": percentile(gate_latencies, 0.50),
                "p95": percentile(gate_latencies, 0.95),
            },
        },
        "search_behavior_alignment": {
            "confusion_vs_observed_tool_use": dict(confusion),
            "observed_lookup_recall": ratio(tp, tp + fn),
            "observed_no_lookup_specificity": ratio(tn, tn + fp),
            "precision_vs_observed_lookup": ratio(tp, tp + fp),
            "reasons": dict(search_reasons),
            "backends": dict(search_backends),
            "note": "These are behavioral-alignment metrics against weak labels, not correctness accuracy.",
        },
        "model_tier": {
            "counts": dict(tier_counts),
            "backends": dict(tier_backends),
            "execution_complexity_proxy": {
                tier: {
                    "median_tool_calls": median([float(x) for x in values]),
                    "median_span_messages": median(
                        [float(x) for x in span_by_tier[tier]]
                    ),
                    "n": len(values),
                }
                for tier, values in tool_counts_by_tier.items()
            },
            "note": "Tool/message counts are complexity proxies only and are not tier-quality labels.",
        },
        "by_profile": {key: dict(value) for key, value in sorted(per_profile.items())},
        "by_source": {key: dict(value) for key, value in sorted(per_source.items())},
        "private_review_candidates": {
            "false_no_search_candidates": fn,
            "false_search_candidates": fp,
            "stored_only_in_private_output": True,
        },
    }
    args.summary_output.parent.mkdir(parents=True, exist_ok=True)
    args.summary_output.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
