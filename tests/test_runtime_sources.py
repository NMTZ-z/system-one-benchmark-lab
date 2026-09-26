from pathlib import Path

import pytest

from local_system_one.runtime.sources import (
    TYPED_DECISIONS_MODEL_ID,
    TYPED_DECISIONS_REVISION,
    normalize_source,
    require_local_source,
)


def test_typed_decisions_alias_is_pinned():
    source, revision = normalize_source("laya-typed-decisions")
    assert source == TYPED_DECISIONS_MODEL_ID
    assert revision == TYPED_DECISIONS_REVISION


def test_full_typed_decisions_model_id_is_pinned():
    source, revision = normalize_source(TYPED_DECISIONS_MODEL_ID)
    assert source == TYPED_DECISIONS_MODEL_ID
    assert revision == TYPED_DECISIONS_REVISION


def test_existing_local_directory_stays_local(tmp_path):
    source, revision = normalize_source(tmp_path)
    assert source == tmp_path
    assert revision is None


def test_unknown_value_is_treated_as_local_path():
    source, revision = normalize_source("not-a-known-model-alias")
    assert source == Path("not-a-known-model-alias")
    assert revision is None


def test_missing_local_source_fails_before_remote_lookup(tmp_path):
    missing = tmp_path / "missing"
    with pytest.raises(FileNotFoundError):
        require_local_source(missing)
