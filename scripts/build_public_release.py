#!/usr/bin/env python3
"""Build a sanitized public Local System One source bundle from tracked files only."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ALLOWLIST = PROJECT_ROOT / "release" / "public-files.txt"
DEFAULT_OUTPUT = PROJECT_ROOT / "artifacts" / "public-release" / "local-system-one"

FORBIDDEN_PARTS = {
    ".env",
    "__pycache__",
    "private",
    "models",
    "artifacts",
}
FORBIDDEN_PREFIXES = (
    "results/raw/",
    "private/",
    "models/",
    "artifacts/",
)
TEXT_PATTERNS = (
    ("macOS user home", re.compile(r"/" r"Users/[^/\s]+/")),
    ("Windows user home", re.compile(r"[A-Za-z]:\\\\Users\\\\[^\\\\\s]+\\\\")),
    (
        "private key",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    ),
    (
        "credential token prefix",
        re.compile(r"\b(?:sk|tvly|gh[pousr]|xox[baprs])-[A-Za-z0-9_-]{12,}\b"),
    ),
    (
        "assigned secret",
        re.compile(
            r"(?i)\b(?:api[_-]?key|token|secret|password)\b\s*[:=]\s*"
            r"['\"]?(?!\$\{|<|your_|example|changeme|none|null)"
            r"[A-Za-z0-9_./+=-]{16,}"
        ),
    ),
)


def git(*args: str, root: Path = PROJECT_ROOT) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout


def load_allowlist(path: Path) -> list[str]:
    entries: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        value = raw.strip()
        if not value or value.startswith("#"):
            continue
        if value.startswith("/") or ".." in Path(value).parts:
            raise ValueError(f"unsafe allowlist entry: {value}")
        entries.append(value)
    if not entries:
        raise ValueError("public release allowlist is empty")
    return entries


def select_source_files(entries: list[str], root: Path = PROJECT_ROOT) -> list[str]:
    """Select tracked prefix contents plus explicitly named, non-ignored files.

    Prefix entries are intentionally Git-index-only, so an accidental untracked file
    under an exported directory can never hitch a ride. Exact entries may refer to a
    new review-stage file before it is committed; a dirty source tree is always marked
    non-publish-ready in PUBLIC-RELEASE.json.
    """
    tracked = {value for value in git("ls-files", "-z", root=root).split("\0") if value}
    files: set[str] = set()
    missing: list[str] = []

    for entry in entries:
        if entry.endswith("/"):
            files.update(path for path in tracked if path.startswith(entry))
            continue
        source = root / entry
        if entry in tracked:
            files.add(entry)
            continue
        ignored = subprocess.run(
            ["git", "check-ignore", "-q", "--", entry],
            cwd=root,
            check=False,
        ).returncode == 0
        if source.is_file() and not ignored:
            files.add(entry)
        else:
            missing.append(entry)

    if missing:
        raise ValueError("allowlist contains missing/ignored files: " + ", ".join(missing))
    return sorted(files)


def validate_export_paths(paths: list[str]) -> list[str]:
    findings: list[str] = []
    for value in paths:
        posix = Path(value).as_posix()
        parts = set(Path(value).parts)
        if parts & FORBIDDEN_PARTS:
            findings.append(f"forbidden path: {value}")
        if any(posix.startswith(prefix) for prefix in FORBIDDEN_PREFIXES):
            findings.append(f"forbidden prefix: {value}")
        if value.endswith((".pyc", ".pyo")):
            findings.append(f"bytecode path: {value}")
    return findings


def _text(path: Path) -> str | None:
    data = path.read_bytes()
    if b"\0" in data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def scan_tree(root: Path) -> list[str]:
    findings: list[str] = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        relative = path.relative_to(root).as_posix()
        if relative in {"PUBLIC-MANIFEST.sha256", "PUBLIC-RELEASE.json"}:
            continue
        text = _text(path)
        if text is None:
            continue
        for label, pattern in TEXT_PATTERNS:
            match = pattern.search(text)
            if match:
                line = text.count("\n", 0, match.start()) + 1
                findings.append(f"{relative}:{line}: {label}")
    return findings


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_release(
    output: Path,
    *,
    root: Path = PROJECT_ROOT,
    allowlist: Path = DEFAULT_ALLOWLIST,
    force: bool = False,
) -> dict[str, object]:
    entries = load_allowlist(allowlist)
    files = select_source_files(entries, root=root)

    path_findings = validate_export_paths(files)
    if path_findings:
        raise RuntimeError("\n".join(path_findings))

    if output.exists():
        if not force:
            raise FileExistsError(f"output exists: {output}; pass --force to replace it")
        shutil.rmtree(output)
    output.mkdir(parents=True)

    for relative in files:
        source = root / relative
        if source.is_symlink():
            raise RuntimeError(f"refusing symlink in public bundle: {relative}")
        if not source.is_file():
            raise RuntimeError(f"tracked selection is not a regular file: {relative}")
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    findings = scan_tree(output)
    if findings:
        raise RuntimeError(
            "public release scan failed:\n" + "\n".join(f"  - {item}" for item in findings)
        )

    manifest_lines = []
    for path in sorted(p for p in output.rglob("*") if p.is_file()):
        relative = path.relative_to(output).as_posix()
        if relative in {"PUBLIC-MANIFEST.sha256", "PUBLIC-RELEASE.json"}:
            continue
        manifest_lines.append(f"{sha256(path)}  {relative}")
    (output / "PUBLIC-MANIFEST.sha256").write_text(
        "\n".join(manifest_lines) + "\n", encoding="utf-8"
    )

    commit = git("rev-parse", "HEAD", root=root).strip()
    dirty = bool(git("status", "--porcelain", root=root).strip())
    license_present = (root / "LICENSE").is_file() and "LICENSE" in files
    metadata = {
        "schema": 1,
        "source_commit": commit,
        "source_dirty": dirty,
        "file_count": len(files),
        "license_status": "included" if license_present else "missing",
        "publish_ready": bool(license_present and not dirty),
        "notes": (
            []
            if license_present
            else ["A license must be selected and included before public publication."]
        ),
    }
    (output / "PUBLIC-RELEASE.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return metadata


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--allowlist", type=Path, default=DEFAULT_ALLOWLIST)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    try:
        metadata = build_release(
            args.output.resolve(),
            allowlist=args.allowlist.resolve(),
            force=args.force,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(f"Public release bundle: {args.output.resolve()}")
    print(f"Files: {metadata['file_count']}")
    print(f"Source commit: {metadata['source_commit']}")
    print(f"License: {metadata['license_status']}")
    if not metadata["publish_ready"]:
        print("Bundle built for review, but it is NOT publish-ready yet.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
