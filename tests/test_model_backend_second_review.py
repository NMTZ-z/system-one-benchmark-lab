"""PR #6 second Codex review: strict JSON and clean-code comparison invariants.

No remote requests; all fixtures are publicly synthetic.
"""
from __future__ import annotations

import json
from argparse import Namespace

import pytest

from benchmarks.model_backend_pilot.__main__ import _records, compare
from local_system_one.model_backends.contract import ModelContractError


@pytest.mark.parametrize("bad_constant", ["NaN", "Infinity", "-Infinity"])
@pytest.mark.parametrize("field", ["gold", "payload", "unsafe"])
def test_dataset_refuses_nonfinite_json(tmp_path, bad_constant, field):
    case = {
        "id": "synthetic", "family": "completion", "gold": "continue",
        "payload": {
            "task": "Synthetic review task", "current_result": "Incomplete",
            "execution_state": {},
        },
    }
    item = json.dumps(case)
    if field == "gold":
        item = item.replace('"gold": "continue"', f'"gold": {bad_constant}')
    elif field == "payload":
        item = item.replace('"execution_state": {}', f'"execution_state": {{"unexpected": {bad_constant}}}')
    else:
        item = item[:-1] + f', "unsafe": [{bad_constant}]' + "}"
    source = tmp_path / "bad.jsonl"
    source.write_text(item + "\n", encoding="utf-8")
    with pytest.raises((ValueError, ModelContractError)):
        _records(source)


@pytest.mark.parametrize("clean_state", [False, None, "true"])
def test_compare_rejects_dirty_missing_or_nonstrict_clean_flag(tmp_path, clean_state):
    inputs = []
    base = {
        "provider": "rule", "dataset_sha256": "dataset", "strategy": "policy",
        "git_sha": "same_sha_but_may_be_uncommitted",
        "schema_version": "model-backend-pilot-v1",
        "code_checkout_clean_at_run": True,
        "cases": [{"id": "synthetic", "model_resolved": None}],
        "remote_attempts": 0,
        "summary": {"total": 1},
    }
    for provider in ("rule", "laya", "jev"):
        record = dict(base, provider=provider)
        if provider == "jev":
            record["code_checkout_clean_at_run"] = clean_state
            if clean_state is None:
                del record["code_checkout_clean_at_run"]
        file = tmp_path / f"{provider}.json"
        file.write_text(json.dumps(record), encoding="utf-8")
        inputs.append(file)
    out = tmp_path / "comparison.json"
    with pytest.raises(ValueError, match="requires clean committed code"):
        compare(Namespace(reports=inputs, output=out))
    assert not out.exists()


def test_compare_rejects_nonfinite_report_even_with_clean_git(tmp_path):
    paths = []
    for provider in ("rule", "laya", "jev"):
        content = {
            "provider": provider, "dataset_sha256": "hash",
            "git_sha": "sha", "strategy": "v1",
            "schema_version": "model-backend-pilot-v1",
            "code_checkout_clean_at_run": True,
            "cases": [{"id": "s1"}], "remote_attempts": 1, "summary": {},
        }
        file = tmp_path / f"{provider}.json"
        file.write_text(json.dumps(content).replace('"summary": {}', '"summary": {"mae": NaN}')
                        if provider == "jev" else json.dumps(content), encoding="utf-8")
        paths.append(file)
    out = tmp_path / "result.json"
    with pytest.raises(ValueError, match="non-finite"):
        compare(Namespace(reports=paths, output=out))
    assert not out.exists()
