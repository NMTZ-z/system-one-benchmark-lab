from __future__ import annotations

import argparse
import json
import random
import sqlite3
import statistics
import subprocess
import time
from pathlib import Path
from typing import Any


def build_tasks() -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []

    json_specs = [
        (
            "json_01",
            "status=ready; retries=2; enabled=true",
            {"status": "ready", "retries": 2, "enabled": True},
        ),
        (
            "json_02",
            "service=Hermes; mode=shadow; active=false",
            {"service": "Hermes", "mode": "shadow", "active": False},
        ),
        (
            "json_03",
            "name=router; port=8787; healthy=true",
            {"name": "router", "port": 8787, "healthy": True},
        ),
        (
            "json_04",
            "device=Mac mini M4; memory_gb=24; online=true",
            {"device": "Mac mini M4", "memory_gb": 24, "online": True},
        ),
    ]
    for tid, src, expected in json_specs:
        tasks.append(
            {
                "id": tid,
                "category": "json",
                "prompt": f"把下面字段转换成一个 JSON 对象，只输出 JSON，不要解释：{src}",
                "validator": {"type": "json_equal", "expected": expected},
            }
        )

    sort_specs = [
        ("sort_01", "7,1,7,2,5", "1,2,5,7"),
        ("sort_02", "9,3,3,-1,8,0,-1", "-1,0,3,8,9"),
        ("sort_03", "42,11,5,42,11,19", "5,11,19,42"),
        ("sort_04", "100,2,10,2,1,100,20", "1,2,10,20,100"),
    ]
    for tid, src, expected in sort_specs:
        tasks.append(
            {
                "id": tid,
                "category": "sort_unique",
                "prompt": f"把下面整数去重并按升序排列，只输出英文逗号分隔结果：{src}",
                "validator": {"type": "exact", "expected": expected},
            }
        )

    date_specs = [
        (
            "date_01",
            "25 Sep 2026；2025/01/03；Dec 7 2024",
            "2026-09-25|2025-01-03|2024-12-07",
        ),
        (
            "date_02",
            "1 Feb 2026；2024/11/09；Mar 30 2025",
            "2026-02-01|2024-11-09|2025-03-30",
        ),
        (
            "date_03",
            "Jun 5 2023；2026/12/31；14 Aug 2025",
            "2023-06-05|2026-12-31|2025-08-14",
        ),
        (
            "date_04",
            "9 Jan 2024；Oct 21 2026；2025/04/02",
            "2024-01-09|2026-10-21|2025-04-02",
        ),
    ]
    for tid, src, expected in date_specs:
        tasks.append(
            {
                "id": tid,
                "category": "date_normalize",
                "prompt": f"把以下日期统一转换为 YYYY-MM-DD，用 | 连接，只输出结果：{src}",
                "validator": {"type": "exact", "expected": expected},
            }
        )

    extract_specs = [
        (
            "extract_01",
            "林舟使用 Mac mini M4，内存 24GB，状态 healthy。字段必须是 name、device、memory、status。",
            {
                "name": "林舟",
                "device": "Mac mini M4",
                "memory": "24GB",
                "status": "healthy",
            },
        ),
        (
            "extract_02",
            "服务 local-system-one 监听 127.0.0.1:8787，模式 shadow。字段必须是 service、host、port、mode。",
            {
                "service": "local-system-one",
                "host": "127.0.0.1",
                "port": 8787,
                "mode": "shadow",
            },
        ),
        (
            "extract_03",
            "任务编号 R03，结果 PASS，耗时 83.4ms。字段必须是 task、result、latency_ms。",
            {"task": "R03", "result": "PASS", "latency_ms": 83.4},
        ),
        (
            "extract_04",
            "模型 Laya-421M，后端 ANE，准确率 0.767。字段必须是 model、backend、accuracy。",
            {"model": "Laya-421M", "backend": "ANE", "accuracy": 0.767},
        ),
    ]
    for tid, src, expected in extract_specs:
        tasks.append(
            {
                "id": tid,
                "category": "field_extract",
                "prompt": f"从这句话提取字段，只输出 JSON：{src}",
                "validator": {"type": "json_equal", "expected": expected},
            }
        )

    csv_specs = [
        (
            "csv_01",
            "name,score\nA,3\nB,5",
            [{"name": "A", "score": 3}, {"name": "B", "score": 5}],
        ),
        (
            "csv_02",
            "service,port\nHermes,8080\nSystemOne,8787",
            [
                {"service": "Hermes", "port": 8080},
                {"service": "SystemOne", "port": 8787},
            ],
        ),
        (
            "csv_03",
            "item,enabled\nsearch,true\nnotify,false",
            [{"item": "search", "enabled": True}, {"item": "notify", "enabled": False}],
        ),
        (
            "csv_04",
            "profile,count\nagent_a,12\nagent_b,8",
            [{"profile": "agent_a", "count": 12}, {"profile": "agent_b", "count": 8}],
        ),
    ]
    for tid, src, expected in csv_specs:
        tasks.append(
            {
                "id": tid,
                "category": "csv_json",
                "prompt": f"把下面 CSV 转成 JSON 数组，只输出 JSON：\n{src}",
                "validator": {"type": "json_equal", "expected": expected},
            }
        )

    format_specs = [
        ("format_01", "alpha=1;beta=2;gamma=3", ["alpha:1", "beta:2", "gamma:3"]),
        (
            "format_02",
            "mode=shadow;health=ok;port=8787",
            ["mode:shadow", "health:ok", "port:8787"],
        ),
        (
            "format_03",
            "low=4.2;high=5.1;winner=low",
            ["low:4.2", "high:5.1", "winner:low"],
        ),
        ("format_04", "a=true;b=false;c=true", ["a:true", "b:false", "c:true"]),
    ]
    for tid, src, expected in format_specs:
        tasks.append(
            {
                "id": tid,
                "category": "format",
                "prompt": f"把下面键值对改成每行 key:value，只输出结果，保持原顺序：{src}",
                "validator": {"type": "exact_lines", "expected": expected},
            }
        )

    summary_specs = [
        (
            "summary_01",
            40,
            ["Shadow", "fail-open", "Web"],
            "Shadow 模式不改变 Hermes 请求；Local System One 故障时 fail-open；Canary 只对确定性 no-Web 任务减少直接 Web 工具暴露。",
        ),
        (
            "summary_02",
            38,
            ["ANE", "MLX", "Router"],
            "长输入优先 ANE，短输入可走 MLX，Router 根据长度和健康状态选择后端。",
        ),
        (
            "summary_03",
            40,
            ["Search", "Model Tier", "Notification"],
            "Local System One 当前包含 Search Gate、Model Tier Gate 和 Notification Gate 三类决策工作流。",
        ),
        (
            "summary_04",
            42,
            ["421M", "L512", "98.3%"],
            "421M Typed Decisions 的 L512 ANE 包覆盖 2000 条评测中的 1966 条，对应 98.3%。",
        ),
    ]
    for tid, max_chars, required, src in summary_specs:
        tasks.append(
            {
                "id": tid,
                "category": "bounded_summary",
                "prompt": f"把下面内容压缩成一句中文，{max_chars}字以内，必须保留“{'”“'.join(required)}”：{src}",
                "validator": {
                    "type": "bounded_contains",
                    "max_chars": max_chars,
                    "required": required,
                },
            }
        )

    rewrite_specs = [
        ("rewrite_01", 25, ["第一阶段", "部署"], "第一阶段已经完成，后续准备部署。"),
        (
            "rewrite_02",
            30,
            ["Hermes", "Shadow"],
            "Hermes 已经接入 Shadow 模式进行测试。",
        ),
        ("rewrite_03", 32, ["ANE", "健康"], "目前 ANE 的健康状态是正常的。"),
        ("rewrite_04", 35, ["回滚", "插件"], "如果不想继续使用插件，可以执行回滚。"),
    ]
    for tid, max_chars, required, src in rewrite_specs:
        tasks.append(
            {
                "id": tid,
                "category": "constraint_rewrite",
                "prompt": f"把这句话改写得更自然，{max_chars}字以内，必须保留“{'”“'.join(required)}”，不要新增事实。只输出改写后的句子，不要解释、不要备选：{src}",
                "validator": {
                    "type": "bounded_contains",
                    "max_chars": max_chars,
                    "required": required,
                },
            }
        )

    assert len(tasks) == 32
    return tasks


def strip_fence(text: str) -> str:
    value = text.strip()
    if value.startswith("```") and value.endswith("```"):
        lines = value.splitlines()
        if len(lines) >= 3:
            value = "\n".join(lines[1:-1]).strip()
    return value


def validate(text: str, spec: dict[str, Any]) -> tuple[bool, str]:
    value = strip_fence(text)
    kind = spec["type"]
    if kind == "exact":
        actual = value.replace(" ", "")
        expected = str(spec["expected"]).replace(" ", "")
        return actual == expected, f"actual={actual!r}"
    if kind == "exact_lines":
        actual = [
            line.strip().replace(" ", "") for line in value.splitlines() if line.strip()
        ]
        expected = [line.replace(" ", "") for line in spec["expected"]]
        return actual == expected, f"actual={actual!r}"
    if kind == "json_equal":
        try:
            actual = json.loads(value)
        except Exception as exc:  # noqa: BLE001
            return False, f"json_error={type(exc).__name__}"
        return actual == spec["expected"], f"actual={actual!r}"
    if kind == "bounded_contains":
        required = list(spec["required"])
        missing = [term for term in required if term not in value]
        char_count = len("".join(value.split()))
        ok = not missing and char_count <= int(spec["max_chars"])
        return ok, f"chars={char_count},missing={missing}"
    raise ValueError(f"unknown validator: {kind}")


def turn_seconds(db_path: Path, session_id: str) -> float | None:
    if not db_path.exists():
        return None
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT
              MIN(CASE WHEN role='user' THEN timestamp END),
              MAX(CASE WHEN role='assistant' THEN timestamp END)
            FROM messages
            WHERE session_id=? AND active=1
            """,
            (session_id,),
        ).fetchone()
    if not row or row[0] is None or row[1] is None:
        return None
    return float(row[1]) - float(row[0])


def run_one(
    args: argparse.Namespace, task: dict[str, Any], effort: str, raw_dir: Path
) -> dict[str, Any]:
    stem = f"{task['id']}-{effort}"
    usage_path = raw_dir / f"{stem}-usage.json"
    response_path = raw_dir / f"{stem}.txt"
    cmd = [
        "hermes",
        "-p",
        args.profile,
        "--provider",
        args.provider,
        "--model",
        args.model,
        "--reasoning",
        effort,
        "-t",
        args.toolsets,
        "-z",
        task["prompt"],
        "--usage-file",
        str(usage_path),
    ]
    started = time.perf_counter()
    proc = subprocess.run(
        cmd, capture_output=True, text=True, timeout=args.timeout, check=False
    )
    wall = time.perf_counter() - started
    response_path.write_text(proc.stdout, encoding="utf-8")
    usage: dict[str, Any] = {}
    if usage_path.exists():
        usage = json.loads(usage_path.read_text(encoding="utf-8"))
    passed, validation = validate(proc.stdout, task["validator"])
    session_id = str(usage.get("session_id") or "")
    return {
        "task": task["id"],
        "category": task["category"],
        "effort": effort,
        "passed": bool(
            passed and proc.returncode == 0 and usage.get("completed", False)
        ),
        "validator_passed": passed,
        "validation": validation,
        "returncode": proc.returncode,
        "completed": usage.get("completed"),
        "wall_seconds": wall,
        "turn_seconds": turn_seconds(
            Path.home() / f".hermes/profiles/{args.profile}/state.db", session_id
        ),
        "session_id": session_id,
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "total_tokens": usage.get("total_tokens"),
        "response_preview": proc.stdout.strip()[:240],
    }


def summarize(
    rows: list[dict[str, Any]], tasks: list[dict[str, Any]]
) -> dict[str, Any]:
    pairs = []
    by: dict[str, dict[str, dict[str, Any]]] = {}
    for row in rows:
        by.setdefault(row["task"], {})[row["effort"]] = row
    for task in tasks:
        pair = by.get(task["id"], {})
        low, high = pair.get("low"), pair.get("high")
        if not low or not high:
            continue
        lt = low.get("turn_seconds")
        ht = high.get("turn_seconds")
        ratio = (
            (ht / lt)
            if isinstance(lt, (int, float)) and lt > 0 and isinstance(ht, (int, float))
            else None
        )
        pairs.append(
            {
                "task": task["id"],
                "category": task["category"],
                "low_passed": low["passed"],
                "high_passed": high["passed"],
                "low_turn_seconds": lt,
                "high_turn_seconds": ht,
                "high_over_low_turn_ratio": ratio,
                "low_wall_seconds": low["wall_seconds"],
                "high_wall_seconds": high["wall_seconds"],
            }
        )
    turn_low = [
        p["low_turn_seconds"]
        for p in pairs
        if isinstance(p["low_turn_seconds"], (int, float))
    ]
    turn_high = [
        p["high_turn_seconds"]
        for p in pairs
        if isinstance(p["high_turn_seconds"], (int, float))
    ]
    comparable = [
        p for p in pairs if isinstance(p["high_over_low_turn_ratio"], (int, float))
    ]
    categories: dict[str, dict[str, Any]] = {}
    for category in sorted({p["category"] for p in pairs}):
        cp = [p for p in pairs if p["category"] == category]
        categories[category] = {
            "pairs": len(cp),
            "low_pass": sum(bool(p["low_passed"]) for p in cp),
            "high_pass": sum(bool(p["high_passed"]) for p in cp),
            "low_faster": sum((p["high_over_low_turn_ratio"] or 0) > 1 for p in cp),
        }
    return {
        "benchmark": "hermes-model-tier-hard-fast-v1",
        "pairs": len(pairs),
        "low_pass": sum(bool(p["low_passed"]) for p in pairs),
        "high_pass": sum(bool(p["high_passed"]) for p in pairs),
        "both_pass": sum(bool(p["low_passed"] and p["high_passed"]) for p in pairs),
        "low_only_fail": sum(
            bool((not p["low_passed"]) and p["high_passed"]) for p in pairs
        ),
        "high_only_fail": sum(
            bool(p["low_passed"] and (not p["high_passed"])) for p in pairs
        ),
        "both_fail": sum(
            bool((not p["low_passed"]) and (not p["high_passed"])) for p in pairs
        ),
        "low_mean_turn_seconds": statistics.mean(turn_low) if turn_low else None,
        "high_mean_turn_seconds": statistics.mean(turn_high) if turn_high else None,
        "low_median_turn_seconds": statistics.median(turn_low) if turn_low else None,
        "high_median_turn_seconds": statistics.median(turn_high) if turn_high else None,
        "median_high_over_low_ratio": (
            statistics.median([p["high_over_low_turn_ratio"] for p in comparable])
            if comparable
            else None
        ),
        "low_faster_pairs": sum(
            (p["high_over_low_turn_ratio"] or 0) > 1 for p in comparable
        ),
        "high_faster_pairs": sum(
            (p["high_over_low_turn_ratio"] or 0) < 1 for p in comparable
        ),
        "categories": categories,
        "pairs_detail": pairs,
        "method": {
            "model": "gemini-3.8-flash-tiered",
            "provider": "local-gemini",
            "efforts": ["low", "high"],
            "toolsets": "clarify",
            "quality_grading": "deterministic programmatic validators; no LLM judge",
            "pair_order": "seeded counterbalanced random order",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="systemoneeval")
    parser.add_argument("--provider", default="local-gemini")
    parser.add_argument("--model", default="gemini-3.8-flash-tiered")
    parser.add_argument("--toolsets", default="clarify")
    parser.add_argument("--seed", type=int, default=20260925)
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--limit", type=int, default=32)
    parser.add_argument("--category", default=None)
    parser.add_argument("--task-id", default=None)
    parser.add_argument("--raw-dir", default="private/hermes-model-tier-hard-fast-v1")
    parser.add_argument(
        "--task-output",
        default="results/processed/hermes-model-tier-hard-fast-v1-tasks.json",
    )
    parser.add_argument(
        "--summary-output",
        default="results/processed/hermes-model-tier-hard-fast-v1-summary.json",
    )
    args = parser.parse_args()

    tasks = build_tasks()
    if args.category:
        tasks = [task for task in tasks if task["category"] == args.category]
    if args.task_id:
        tasks = [task for task in tasks if task["id"] == args.task_id]
    tasks = tasks[: args.limit]
    raw_dir = Path(args.raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    Path(args.task_output).write_text(
        json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    rng = random.Random(args.seed)
    rows: list[dict[str, Any]] = []
    for idx, task in enumerate(tasks, 1):
        order = ["low", "high"]
        if rng.random() < 0.5:
            order.reverse()
        for effort in order:
            print(f"[{idx:02d}/{len(tasks)}] {task['id']} {effort}", flush=True)
            row = run_one(args, task, effort, raw_dir)
            rows.append(row)
            (raw_dir / "rows.json").write_text(
                json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(
                f"  pass={row['passed']} turn={row['turn_seconds']} wall={row['wall_seconds']:.3f}",
                flush=True,
            )

    summary = summarize(rows, tasks)
    Path(args.summary_output).write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                k: summary[k]
                for k in [
                    "pairs",
                    "low_pass",
                    "high_pass",
                    "both_pass",
                    "low_only_fail",
                    "high_only_fail",
                    "low_mean_turn_seconds",
                    "high_mean_turn_seconds",
                    "low_median_turn_seconds",
                    "high_median_turn_seconds",
                    "median_high_over_low_ratio",
                    "low_faster_pairs",
                    "high_faster_pairs",
                ]
            },
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
