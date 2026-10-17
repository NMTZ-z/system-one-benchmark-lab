"""PR #6 ninth review: raw Gate safety evidence, Laya backend and ANE artifact identity.

Only synthetic/frozen public observations and stubbed model constructors.
No TypeSafe API calls, Keychain reads, MLX model loads or Core ML imports.
"""
from __future__ import annotations

import json
import shutil
from argparse import Namespace
from pathlib import Path

import pytest

from benchmarks.model_backend_pilot import __main__ as pilot
from benchmarks.model_backend_pilot.integrity import ane_artifact_sha256

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "results/processed"


def _reports(tmp_path):
    result = {}
    for provider in ("rule", "laya", "jev"):
        target = tmp_path / f"{provider}.json"
        shutil.copyfile(
            PROCESSED / f"model-backend-pilot-20261016-{provider}.json", target,
        )
        result[provider] = target
    return result


def _corrupt(report_path, case_id, edit):
    report = json.loads(report_path.read_text())
    case = next(x for x in report["cases"] if x["id"] == case_id)
    edit(case)
    report["summary"] = pilot._summary(report["cases"])
    report_path.write_text(json.dumps(report))


def _compare(reports, output, capsys):
    exit_code = pilot.main([
        "compare", "--reports", *(str(reports[p]) for p in ("rule", "laya", "jev")),
        "--output", str(output),
    ])
    return exit_code, capsys.readouterr().err


def test_frozen_evidence_still_compares_exactly(tmp_path, capsys):
    reports = _reports(tmp_path)
    output = tmp_path / "compared.json"
    code, err = _compare(reports, output, capsys)
    assert code == 0 and err == ""
    assert output.read_bytes() == (
        PROCESSED / "model-backend-pilot-20261016-comparison.json"
    ).read_bytes()


@pytest.mark.parametrize("raw", ["verify", None, "continue"])
def test_laya_c04_unsafe_raw_event_cannot_be_erased(tmp_path, capsys, raw):
    reports = _reports(tmp_path)
    _corrupt(
        reports["laya"], "C04",
        lambda case: case.update(raw_model_decision=raw),
    )
    output = tmp_path / "forged.json"
    code, err = _compare(reports, output, capsys)
    assert code == 3 and "raw model decision" in err
    assert not output.exists()


@pytest.mark.parametrize("field,value", [
    ("decision_source_note", "model_verify"),
    ("decision", "complete"),
    ("decision_source_note", "model_complete"),
])
def test_completion_threshold_override_must_correspond_to_original_advice(
    tmp_path, capsys, field, value,
):
    reports = _reports(tmp_path)

    def update(case):
        case[field] = value
        case["correct"] = pilot._expected_correct(case)

    _corrupt(reports["laya"], "C04", update)
    out = tmp_path / "invalid.json"
    code, err = _compare(reports, out, capsys)
    assert code == 3 and "raw model decision" in err
    assert not out.exists()


@pytest.mark.parametrize("case_id,new_raw", [
    ("P01", "verify"),
    ("P03", 1),
    ("R04", "abort"),
])
def test_primitive_and_retry_raw_evidence_must_agree_with_decision_and_reason(
    tmp_path, capsys, case_id, new_raw,
):
    reports = _reports(tmp_path)
    _corrupt(
        reports["jev"], case_id,
        lambda case: case.update(raw_model_decision=new_raw),
    )
    out = tmp_path / "recomputed.json"
    code, err = _compare(reports, out, capsys)
    assert code == 3
    if case_id == "P01":
        assert "Choice raw decision outside frozen options" in err
    else:
        assert "raw model decision" in err
    assert not out.exists()


@pytest.mark.parametrize("backend", [
    "remote_http", "ane_l512", "cpu", "gpu", "", None,
])
def test_laya_cannot_claim_unrecognized_backend(tmp_path, capsys, backend):
    reports = _reports(tmp_path)
    _corrupt(
        reports["laya"], "P01",
        lambda case: case.update(execution_backend=backend),
    )
    out = tmp_path / "forged-backend.json"
    code, err = _compare(reports, out, capsys)
    assert code == 3 and ("backend" in err or "execution" in err)
    assert not out.exists()


def test_laya_ane_claim_requires_package_digest(tmp_path, capsys):
    reports = _reports(tmp_path)
    _corrupt(
        reports["laya"], "P03",
        lambda case: case.update(execution_backend="ane"),
    )
    out = tmp_path / "unbound-ane.json"
    code, err = _compare(reports, out, capsys)
    assert code == 3 and "ANE execution lacks package digest" in err
    assert not out.exists()


def _package(path, *, weight=b"ane-model-weights-v1"):
    path.mkdir(parents=True)
    (path / "Manifest.json").write_text('{"version": 1}', encoding="utf-8")
    data = path / "Data" / "com.apple.CoreML"
    data.mkdir(parents=True)
    (data / "weights.bin").write_bytes(weight)
    return path


def test_ane_digest_binds_all_file_contents_and_names(tmp_path):
    one = _package(tmp_path / "one.mlpackage")
    two = _package(tmp_path / "two.mlpackage")
    reference = ane_artifact_sha256(one)
    assert len(reference) == 64
    assert ane_artifact_sha256(two) == reference  # Path-independent same bytes.
    (two / "Data/com.apple.CoreML/weights.bin").write_bytes(b"different")
    assert ane_artifact_sha256(two) != reference
    (two / "Data/com.apple.CoreML/weights.bin").write_bytes(b"ane-model-weights-v1")
    assert ane_artifact_sha256(two) == reference
    (two / "Data/com.apple.CoreML/weights.bin").rename(
        two / "Data/com.apple.CoreML/renamed.bin"
    )
    assert ane_artifact_sha256(two) != reference


def test_ane_digest_supports_single_compiled_file(tmp_path):
    one = tmp_path / "model.mlmodel"
    one.write_bytes(b"compiled-model")
    digest = ane_artifact_sha256(one)
    assert len(digest) == 64
    one.write_bytes(b"compiled-model-modified")
    assert ane_artifact_sha256(one) != digest


@pytest.mark.parametrize("kind", ["top_link", "nested_link", "missing", "empty"])
def test_ane_digest_rejects_nonportable_or_unsafe_package(tmp_path, kind):
    real = _package(tmp_path / "real.mlpackage")
    if kind == "top_link":
        path = tmp_path / "shortcut.mlpackage"
        path.symlink_to(real, target_is_directory=True)
    elif kind == "nested_link":
        path = real
        (real / "Data/weights-link").symlink_to(real / "Data/com.apple.CoreML/weights.bin")
    elif kind == "missing":
        path = tmp_path / "not-found.mlpackage"
    else:
        path = tmp_path / "empty.mlpackage"
        path.mkdir()
    with pytest.raises(ValueError, match="ANE package"):
        ane_artifact_sha256(path)


def test_distinct_ane_packages_produce_distinct_laya_model_identities(
    monkeypatch, tmp_path,
):
    from local_system_one.engine import DecisionEngine
    import local_system_one.runtime.mlx as mlx_module
    import local_system_one.runtime.ane as ane_module

    class FakeRuntime:
        def __init__(self, *args, **kwargs):
            pass

    monkeypatch.setattr(mlx_module, "MLXRuntime", FakeRuntime)
    monkeypatch.setattr(ane_module, "ANERuntime", FakeRuntime)
    monkeypatch.setattr(DecisionEngine, "startup_probe", lambda self: {})

    one = _package(tmp_path / "one.mlpackage", weight=b"weights-A")
    two = _package(tmp_path / "two.mlpackage", weight=b"weights-B")

    def provider(package):
        return pilot._load_provider(Namespace(
            provider="laya", laya_source="laya-typed-decisions",
            laya_model_identity=None, ane_package=package,
        ))

    first = provider(one)
    second = provider(two)
    assert first.model_identity != second.model_identity
    assert first.model_identity.endswith(
        "|ane-package-sha256:" + ane_artifact_sha256(one)
    )
    assert second.model_identity.endswith(
        "|ane-package-sha256:" + ane_artifact_sha256(two)
    )
    assert first.engine.ane is not None and second.engine.ane is not None
    assert first.model_identity.startswith("convaiinnovations/laya-typed-decisions@")


def test_run_refuses_ane_package_changed_after_model_load(
    tmp_path, monkeypatch, capsys,
):
    from benchmarks.model_backend_pilot.integrity import Provenance

    artifact = _package(tmp_path / "pilot.mlpackage")
    old_digest = ane_artifact_sha256(artifact)
    identity = "synthetic-local@revision|ane-package-sha256:" + old_digest

    class SyntheticProvider:
        provider_id = "laya"
        model_identity = identity
        def evaluate(self, request):
            # Pretend the model's compiled package changed during a run.
            (artifact / "Data/com.apple.CoreML/weights.bin").write_bytes(
                b"changed-during-synthetic-run"
            )
            raise ValueError("intentional synthetic inference failure")

    monkeypatch.setattr(pilot, "_load_provider", lambda args: SyntheticProvider())
    monkeypatch.setattr(
        pilot, "preflight_provenance",
        lambda _: Provenance(git_sha="a" * 40, clean_at_start=True),
    )
    output = tmp_path / "should-not-exist.json"
    code = pilot.main([
        "run", "--provider", "laya",
        "--dataset", str(ROOT / "benchmarks/model_backend_pilot/public_synthetic_v1.jsonl"),
        "--output", str(output), "--ane-package", str(artifact),
    ])
    assert code == 3
    assert "ANE package changed during model backend pilot run" in capsys.readouterr().err
    assert not output.exists()


def test_non_ane_laya_identity_is_unchanged(monkeypatch):
    import local_system_one.runtime.mlx as mlx_module
    monkeypatch.setattr(mlx_module, "MLXRuntime", lambda source: object())
    provider = pilot._load_provider(Namespace(
        provider="laya", laya_source="laya-typed-decisions",
        laya_model_identity=None, ane_package=None,
    ))
    assert provider.model_identity == (
        "convaiinnovations/laya-typed-decisions"
        "@f9ab0b228f0fc0f14d873dbc99038f135c2da1b2"
    )
