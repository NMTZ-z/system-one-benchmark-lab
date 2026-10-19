"""Privacy-safe post-freeze native Mock summary integrity (no raw artifacts)."""
from __future__ import annotations

import json
from pathlib import Path

FILE = (Path(__file__).resolve().parents[1] / "results/processed" /
        "phase8_2b_native_mock_acceptance.json")


def test_frozen_mock_summary_is_bounded_and_explicit_about_provenance():
    source = FILE.read_text(encoding="utf-8")
    report = json.loads(source)
    assert report["schema"] == "local-system-one/phase8_2b_native_mock_acceptance_v1"
    assert report["source_commit"] == "9172e6dbed4b7c7f744480de9a95668685fe9b22"
    assert report["real_paid_provider_requests"] == 0
    assert report["active_permissions"] == "NOT_AUTHORIZED"
    assert report["evidence_scope"] == "native_agent_execution_with_local_mock_provider"
    assert report["runtime_healthy_path"] == "isolated_deterministic_mock_rule"
    assert len(report["cases"]) == 7
    assert sum(r["native_tool_calls"] for r in report["cases"]) == 9
    assert sum(r["model_budget"]["outbound_attempts"] for r in report["cases"]) == 21
    assert sum(r["native_http_links_verified"] or 0 for r in report["cases"]) == 14
    assert {r["platform"] for r in report["cases"]} == {"hermes", "deepseek_harness"}
    assert all(r["native_agent_finished"] and r["independent_task_oracle"]
               and r["native_process_exit"] == 0 for r in report["cases"])
    for record in report["cases"]:
        assert record["native_tool_calls"] == record["paired_native_results"]
        assert record["model_budget"]["ledger_status"] == "PARTIAL"
        assert record["model_budget"]["remote_bill"] == "unknown"
        assert record["model_budget"]["remote_usage_tokens"] == "unknown"
        assert record["model_budget"]["outbound_attempts"] == record["model_budget"]["reserved"]
        assert record["model_budget"]["outbound_attempts"] == record["model_budget"]["upstream_http_responses"]
        if record["mode"] == "off":
            assert record["runtime_http_statuses"] == []
            assert record["native_http_links_verified"] is None
        elif record["mode"] == "down":
            assert record["runtime_http_statuses"] == [503, 503]
            assert record["native_http_links_verified"] == 2
        elif record["mode"] == "shadow":
            assert record["runtime_http_statuses"] == [200, 200]
            assert record["native_http_links_verified"] == 2
    multi = next(x for x in report["cases"] if x["mode"] == "shadow_multiturn")
    assert multi["distinct_sessions"] == 2
    assert multi["distinct_turns"] == 3
    assert multi["native_http_links_verified"] == 6
    assert len(multi["runtime_http_statuses"]) == 6
    for private in (
        "/Users/", "\\Users\\", "P82B_MOCK_NATIVE_READ_PROOF",
        "P82B_NATIVE_DSH_READ_PROOF", "ISOLATED_DUMMY_ONLY",
        "STEPFUN_API_KEY", "api_key", "private-correlation.bin",
    ):
        assert private not in source
