"""Load fixed-shape research ANE packages for the upstream energy harness."""

from pathlib import Path

from laya_coreml.ane import ANEAgent


def load_research_ane_l512(source: Path, package: Path):
    """Load the Phase 4A 421M L512 research ANE graph."""
    return ANEAgent(
        source,
        package=package,
        length=512,
        compute_units="cpu_ne",
    )
