"""Research-only source and report-file integrity boundary.

A paid remote call is never permitted to *precede* Git provenance and
output writability checks. All writes use a temporary file in the target
directory followed by an atomic replacement.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def ane_artifact_sha256(path: Path) -> str:
    """Fingerprint an actual ANE model package by its entire file contents.

    Path-independent and directory-order-independent. Reject symbolic links,
    special files and concurrent mutation; a free-form human version label
    does not establish that two compiled Core ML packages are identical.
    """
    package = Path(path).expanduser()
    if package.is_symlink() or not (package.is_dir() or package.is_file()):
        raise ValueError("ANE package must be an existing regular file or directory")
    digest = hashlib.sha256()
    if package.is_file():
        files = [(package, ".")]
        digest.update(b"ane-artifact-file-v1\x00")
    else:
        digest.update(b"ane-artifact-directory-v1\x00")
        files = []
        for root, dirs, filenames in os.walk(package, followlinks=False):
            dirs.sort()
            filenames.sort()
            for name in dirs:
                directory = Path(root) / name
                if directory.is_symlink() or not directory.is_dir():
                    raise ValueError("ANE package contains unsafe directory entry")
                rel = directory.relative_to(package).as_posix()
                digest.update(b"dir\x00" + rel.encode("utf-8") + b"\x00")
            for name in filenames:
                file = Path(root) / name
                if file.is_symlink() or not file.is_file():
                    raise ValueError("ANE package contains unsafe file entry")
                files.append((file, file.relative_to(package).as_posix()))
        if not files:
            raise ValueError("ANE package contains no regular files")

    for file, relative in files:
        before = file.stat(follow_symlinks=False)
        name = relative.encode("utf-8")
        digest.update(b"file\x00" + len(name).to_bytes(4, "big") + name)
        digest.update(before.st_size.to_bytes(8, "big"))
        with file.open("rb") as stream:
            while block := stream.read(1024 * 1024):
                digest.update(block)
        after = file.stat(follow_symlinks=False)
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns
        ):
            raise ValueError("ANE package was modified during fingerprinting")
    return digest.hexdigest()


def unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Reject conflicting JSON keys at any nesting depth, without echoing data."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key in research evidence")
        result[key] = value
    return result


@dataclass(frozen=True)
class Provenance:
    git_sha: str
    clean_at_start: bool


def preflight_provenance(source_root: Path) -> Provenance:
    """Fail closed on non-Git export bundles, nested repos or missing Git.

    A sanitized public release has PUBLIC-RELEASE.json but no authenticated
    source checkout. Until archive verification is implemented, running paid
    research from an export bundle must fail before even loading the provider.
    """
    root = source_root.resolve()
    try:
        kwargs = {"cwd": root, "capture_output": True, "text": True, "check": True}
        top = subprocess.run(["git", "rev-parse", "--show-toplevel"], **kwargs).stdout.strip()
        if Path(top).resolve() != root:
            raise ValueError("research run requires its own Git checkout root")
        sha = subprocess.run(["git", "rev-parse", "HEAD"], **kwargs).stdout.strip()
        if re.fullmatch(r"[0-9a-fA-F]{40,64}", sha) is None:
            raise ValueError("research run cannot verify a committed Git revision")
        clean = not subprocess.run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"], **kwargs
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        raise ValueError(
            "research run requires an accessible Git checkout and commit before "
            "provider initialization; standalone public release archives cannot "
            "be used for paid research without verified provenance"
        ) from None
    return Provenance(git_sha=sha, clean_at_start=clean)


def preflight_report_output(output: Path, *, inputs: list[Path], kind: str) -> None:
    """Reject aliases and verify the output is writable *before* inference."""
    if output.resolve() in {p.resolve() for p in inputs} or (
        output.exists() and any(output.samefile(path) for path in inputs)
    ):
        raise ValueError(
            "output may not overwrite input dataset" if kind == "run"
            else "comparison output must not overwrite an input report"
        )
    if output.is_dir():
        raise ValueError("output must be a file, not a directory")
    output.parent.mkdir(parents=True, exist_ok=True)
    # A temp file proves that an atomic report write can at least be initiated.
    # This is deliberately done before any authorized API calls and leaves no
    # tracked artefacts or private task content behind.
    with tempfile.TemporaryFile(dir=output.parent):
        pass


def write_report(output: Path, report: dict[str, Any], *, ensure_ascii: bool) -> None:
    """Atomic JSON write: a failed write cannot truncate an existing report."""
    payload = json.dumps(report, indent=2, ensure_ascii=ensure_ascii, allow_nan=False) + "\n"
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=output.parent,
            prefix=".model-backend-report-", suffix=".tmp", delete=False,
        ) as f:
            temp_path = Path(f.name)
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, output)
        temp_path = None
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
