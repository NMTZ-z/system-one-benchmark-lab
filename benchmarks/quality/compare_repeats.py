"""Compare two typed-decisions runs over their common case ids."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def selected_label(answer: dict[str, Any]) -> str:
    if answer["type"] == "choice":
        return str(answer["choice"])
    if answer["type"] == "noul":
        return "true" if float(answer["noul"]) >= 0.5 else "false"
    probabilities = answer["probabilities"]
    return str(max(probabilities, key=probabilities.get))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("left", type=Path)
    parser.add_argument("right", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    left = json.loads(args.left.read_text())
    right = json.loads(args.right.read_text())

    left_cases = {case["id"]: case for case in left["cases"]}
    right_cases = {case["id"]: case for case in right["cases"]}
    common_ids = [case["id"] for case in right["cases"] if case["id"] in left_cases]
    if not common_ids:
        raise RuntimeError("runs have no common case ids")

    decisions = 0
    exact_objects = 0
    selected_flips = []
    max_probability_delta = 0.0
    max_confidence_delta = 0.0

    for case_id in common_ids:
        left_case = left_cases[case_id]
        right_case = right_cases[case_id]
        if left_case.get("status") != "ok" or right_case.get("status") != "ok":
            raise RuntimeError(f"non-ok common case: {case_id}")
        left_answers = left_case["response"]["answers"]
        right_answers = right_case["response"]["answers"]
        if set(left_answers) != set(right_answers):
            raise RuntimeError(f"question sets differ: {case_id}")

        for question, left_answer in left_answers.items():
            right_answer = right_answers[question]
            decisions += 1
            exact_objects += left_answer == right_answer

            left_selected = selected_label(left_answer)
            right_selected = selected_label(right_answer)
            if left_selected != right_selected:
                selected_flips.append(
                    {
                        "case_id": case_id,
                        "question": question,
                        "type": left_answer["type"],
                        "left": left_selected,
                        "right": right_selected,
                    }
                )

            if left_answer["type"] in ("choice", "score"):
                for key, value in left_answer["probabilities"].items():
                    max_probability_delta = max(
                        max_probability_delta,
                        abs(float(value) - float(right_answer["probabilities"][key])),
                    )
            else:
                max_probability_delta = max(
                    max_probability_delta,
                    abs(float(left_answer["noul"]) - float(right_answer["noul"])),
                )

            max_confidence_delta = max(
                max_confidence_delta,
                abs(
                    float(left_answer.get("confidence", 0.0))
                    - float(right_answer.get("confidence", 0.0))
                ),
            )

    payload = {
        "left": str(args.left),
        "right": str(args.right),
        "common_cases": len(common_ids),
        "decisions": decisions,
        "exact_answer_objects": exact_objects,
        "selected_flips": len(selected_flips),
        "selected_flip_rate": len(selected_flips) / decisions,
        "max_probability_abs_delta": max_probability_delta,
        "max_confidence_abs_delta": max_confidence_delta,
        "flip_examples": selected_flips[:50],
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
