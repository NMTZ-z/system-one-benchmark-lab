"""Load a published Laya ANE bundle through the upstream energy-harness factory API."""

from pathlib import Path

import laya_coreml


def load_published_ane(_source: Path, bundle: Path):
    """Return the pinned public ANE runtime expected by benchmarks.energy."""
    return laya_coreml.load(
        bundle,
        local_files_only=True,
        compute_units="cpu_ne",
    )
