"""PR #6 third Codex review: Laya identity and hard-link integrity regressions.

This suite uses an isolated fake MLX runtime and saved public synthetic reports.
No model downloads or TypeSafe network requests are performed.
"""

from __future__ import annotations

import os
import shutil
from argparse import Namespace
from pathlib import Path

import pytest

from benchmarks.model_backend_pilot.__main__ import _load_provider, compare
from local_system_one.runtime.sources import (
    TYPED_DECISIONS_MODEL_ID,
    TYPED_DECISIONS_REVISION,
)


@pytest.fixture
def fake_mlx(monkeypatch):
    calls = []

    class StubRuntime:
        def __init__(self, source):
            self.source = source
            calls.append(source)

    monkeypatch.setattr("local_system_one.runtime.mlx.MLXRuntime", StubRuntime)
    return calls


def _laya_args(source: str, identity: str | None = None) -> Namespace:
    return Namespace(
        provider="laya", laya_source=source, laya_model_identity=identity,
        ane_package=None,
    )


@pytest.mark.parametrize("alias", [
    "laya-typed-decisions",
    "convaiinnovations/laya-typed-decisions",
])
def test_local_directory_shadowing_pinned_alias_requires_explicit_identity(
    monkeypatch, tmp_path, fake_mlx, alias,
):
    monkeypatch.chdir(tmp_path)
    Path(alias).mkdir(parents=True)
    with pytest.raises(ValueError, match="local checkpoint requires explicit"):
        _load_provider(_laya_args(alias))
    assert fake_mlx == []  # Reject BEFORE loading any unpinned checkpoint.

    explicit = "my-local-checkpoint@synthetic-revision"
    model = _load_provider(_laya_args(alias, explicit))
    assert model.model_identity == explicit
    assert fake_mlx == [alias]


def test_unshadowed_alias_is_recorded_as_official_pinned_revision(
    monkeypatch, tmp_path, fake_mlx,
):
    monkeypatch.chdir(tmp_path)
    provider = _load_provider(_laya_args("laya-typed-decisions"))
    assert provider.model_identity == (
        f"{TYPED_DECISIONS_MODEL_ID}@{TYPED_DECISIONS_REVISION}"
    )
    assert fake_mlx == ["laya-typed-decisions"]


def test_ordinary_local_checkpoint_needs_explicit_identity(tmp_path, fake_mlx):
    local = tmp_path / "local-checkpoint"
    local.mkdir()
    with pytest.raises(ValueError, match="local checkpoint requires explicit"):
        _load_provider(_laya_args(str(local)))
    assert fake_mlx == []
    provider = _load_provider(_laya_args(str(local), "checkpoint-custom@verified"))
    assert provider.model_identity == "checkpoint-custom@verified"


def test_hardlinked_comparison_output_rejected_without_mutating_input(tmp_path):
    project = Path(__file__).resolve().parents[1]
    sources = [
        project / "results" / "processed" / f"model-backend-pilot-20261016-{model}.json"
        for model in ("rule", "laya", "jev")
    ]
    inputs = [tmp_path / source.name for source in sources]
    for source, target in zip(sources, inputs):
        shutil.copyfile(source, target)

    # The control case must be genuinely comparable, not a malformed fixture.
    safe_output = tmp_path / "independent-comparison.json"
    assert compare(Namespace(reports=inputs, output=safe_output)) == 0
    assert safe_output.is_file()

    original = inputs[-1].read_bytes()
    hard_link = tmp_path / "hardlink-out.json"
    os.link(inputs[-1], hard_link)
    assert hard_link.samefile(inputs[-1])
    assert hard_link.resolve() != inputs[-1].resolve()

    with pytest.raises(ValueError, match="overwrite an input"):
        compare(Namespace(reports=inputs, output=hard_link))
    assert hard_link.read_bytes() == original
    assert inputs[-1].read_bytes() == original
