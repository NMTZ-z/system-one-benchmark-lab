"""Audit whether a fixed-shape Laya ANE bundle can represent a benchmark unchanged."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from laya_coreml.prompt import PromptMixin
from laya_coreml.tokenizer import Tokenizer


class PromptOnly(PromptMixin):
    """Prompt builder without loading a Core ML model."""


def percentile(values: list[int], q: float) -> float:
    if not values:
        raise ValueError("cannot compute percentile of an empty list")
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    position = (len(ordered) - 1) * q
    lo = int(position)
    hi = min(lo + 1, len(ordered) - 1)
    weight = position - lo
    return float(ordered[lo] * (1 - weight) + ordered[hi] * weight)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=PROJECT_ROOT
        / "datasets/typed-decisions/all/test-00000-of-00001.parquet",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--candidate-lengths",
        type=int,
        nargs="+",
        default=[96, 128, 160, 192, 256, 384, 512, 640],
    )
    args = parser.parse_args()

    manifest = json.loads((args.bundle / "coreml_config.json").read_text())
    cfg = json.loads((args.bundle / "rl_agent_config.json").read_text())
    shape = manifest["shape"]

    prompt = PromptOnly()
    prompt.cfg = cfg
    prompt.tok = Tokenizer(args.bundle / "tokenizer")

    rows = pq.read_table(args.dataset).to_pylist()
    lengths: list[int] = []
    option_counts: list[int] = []
    by_workflow: dict[str, Counter[str]] = defaultdict(Counter)
    by_type: dict[str, Counter[str]] = defaultdict(Counter)
    supported = 0

    for row in rows:
        state = json.loads(row["state"])
        questions = json.loads(row["questions"])
        for question_id, question in questions.items():
            items, _ = prompt.prepare(state, {question_id: question})
            item = items[0]
            token_length = len(item["ids"])
            option_count = len(item["markers"])
            lengths.append(token_length)
            option_counts.append(option_count)
            status = (
                "supported"
                if token_length <= shape["max_length"]
                and option_count <= shape["max_options"]
                else "over_capacity"
            )
            supported += status == "supported"
            by_workflow[row["workflow"]][status] += 1
            by_type[question["type"]][status] += 1

    total = len(lengths)
    payload: dict[str, Any] = {
        "bundle": str(args.bundle),
        "source": manifest.get("source"),
        "source_revision": manifest.get("source_revision"),
        "repository": manifest.get("repository"),
        "precision": manifest.get("precision"),
        "compression": manifest.get("compression"),
        "shape": shape,
        "dataset": {
            "repo": "LocalLLaMA/typed-decisions",
            "revision": "c76749ec58bd8c3d2ea706b31c333a9059c38f90",
            "split": "all/test",
            "cases": len(rows),
            "decisions": total,
        },
        "capacity": {
            "supported": supported,
            "over_capacity": total - supported,
            "coverage": supported / total if total else 0.0,
            "token_length": {
                "min": min(lengths),
                "max": max(lengths),
                "mean": statistics.fmean(lengths),
                "p01": percentile(lengths, 0.01),
                "p05": percentile(lengths, 0.05),
                "p10": percentile(lengths, 0.10),
                "p25": percentile(lengths, 0.25),
                "p50": percentile(lengths, 0.50),
                "p75": percentile(lengths, 0.75),
                "p90": percentile(lengths, 0.90),
                "p95": percentile(lengths, 0.95),
                "p99": percentile(lengths, 0.99),
            },
            "option_count": {"min": min(option_counts), "max": max(option_counts)},
            "candidate_lengths": {
                str(length): {
                    "supported": sum(value <= length for value in lengths),
                    "coverage": sum(value <= length for value in lengths) / total,
                }
                for length in args.candidate_lengths
            },
            "by_workflow": {
                key: dict(value) for key, value in sorted(by_workflow.items())
            },
            "by_question_type": {
                key: dict(value) for key, value in sorted(by_type.items())
            },
        },
        "interpretation": (
            "Capacity only. A decision is supported when the unmodified prompt fits the "
            "bundle max_length and max_options. Over-capacity decisions are not scored as wrong."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(payload["capacity"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
