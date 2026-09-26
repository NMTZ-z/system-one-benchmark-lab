"""Pinned source aliases shared by MLX and ANE runtimes."""

from __future__ import annotations

from pathlib import Path

TYPED_DECISIONS_ALIAS = "laya-typed-decisions"
TYPED_DECISIONS_MODEL_ID = "convaiinnovations/laya-typed-decisions"
TYPED_DECISIONS_REVISION = "f9ab0b228f0fc0f14d873dbc99038f135c2da1b2"

_TYPED_ALIASES = {
    TYPED_DECISIONS_ALIAS,
    TYPED_DECISIONS_MODEL_ID,
}


def normalize_source(source: str | Path) -> tuple[str | Path, str | None]:
    """Return a local path or a pinned remote model reference.

    Only the validated Typed Decisions alias is treated as a remote identifier.
    Other values remain filesystem paths so typos do not silently turn into
    unrelated Hugging Face repository lookups.
    """
    text = str(source)
    expanded = Path(text).expanduser()
    if expanded.is_dir():
        return expanded, None
    if text in _TYPED_ALIASES:
        return TYPED_DECISIONS_MODEL_ID, TYPED_DECISIONS_REVISION
    return expanded, None


def require_local_source(source: str | Path) -> Path:
    """Resolve the validated remote alias to a pinned local snapshot for ANE."""
    normalized, revision = normalize_source(source)
    if isinstance(normalized, Path):
        if not normalized.is_dir():
            raise FileNotFoundError(f"model source directory not found: {normalized}")
        return normalized

    from laya_coreml.convert import resolve_source

    return Path(resolve_source(normalized, revision))
