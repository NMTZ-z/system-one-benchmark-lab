#!/usr/bin/env python3
"""Capture a reproducible environment snapshot for SystemOne benchmarks."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

PACKAGES = (
    "torch",
    "mlx",
    "coremltools",
    "numpy",
    "transformers",
    "huggingface-hub",
    "laya-coreml",
)


def run_text(*argv: str) -> str | None:
    try:
        proc = subprocess.run(
            argv,
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    text = proc.stdout.strip()
    return text or None


def package_versions() -> dict[str, str | None]:
    versions: dict[str, str | None] = {}
    for name in PACKAGES:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    return versions


def hardware_snapshot() -> dict[str, Any]:
    data: dict[str, Any] = {
        "machine": platform.machine(),
        "processor": platform.processor() or None,
    }
    if sys.platform == "darwin":
        profile = run_text("system_profiler", "SPHardwareDataType", "-json")
        if profile:
            try:
                parsed = json.loads(profile)
                rows = parsed.get("SPHardwareDataType") or []
                hardware = rows[0] if rows else {}
                allowed = (
                    "chip_type",
                    "machine_model",
                    "machine_name",
                    "number_processors",
                    "physical_memory",
                )
                data["system_profiler"] = {
                    key: hardware.get(key) for key in allowed if hardware.get(key) is not None
                }
            except json.JSONDecodeError:
                data["system_profiler_parse_error"] = True
        data["sysctl_brand"] = run_text("sysctl", "-n", "machdep.cpu.brand_string")
        data["sysctl_memsize"] = run_text("sysctl", "-n", "hw.memsize")
    return data


def portable_path(path: str) -> str:
    resolved = Path(path).resolve()
    try:
        return str(resolved.relative_to(PROJECT_ROOT))
    except ValueError:
        return resolved.name


def collect() -> dict[str, Any]:
    return {
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "python": sys.version,
            "python_executable": portable_path(sys.executable),
            "sw_vers": run_text("sw_vers"),
            "xcodebuild": run_text("xcodebuild", "-version"),
        },
        "hardware": hardware_snapshot(),
        "packages": package_versions(),
        "git": {
            "repo_head": run_text("git", "rev-parse", "HEAD"),
            "upstream_laya_coreml_head": run_text(
                "git", "-C", "references/laya-coreml", "rev-parse", "HEAD"
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    payload = json.dumps(collect(), ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
