"""Backend routing policy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

RouteBackend = Literal["mlx", "ane"]


@dataclass(frozen=True)
class RouterConfig:
    ane_min_tokens: int = 192
    ane_max_tokens: int = 512

    def __post_init__(self) -> None:
        if self.ane_min_tokens < 1:
            raise ValueError("ane_min_tokens must be positive")
        if self.ane_max_tokens < self.ane_min_tokens:
            raise ValueError("ane_max_tokens must be >= ane_min_tokens")


@dataclass(frozen=True)
class RouteDecision:
    backend: RouteBackend
    reason: str


class DecisionRouter:
    def __init__(self, config: RouterConfig | None = None):
        self.config = config or RouterConfig()

    def route(
        self,
        token_count: int,
        *,
        ane_healthy: bool,
        ane_available: bool,
        override: str = "auto",
    ) -> RouteDecision:
        if override == "mlx":
            return RouteDecision("mlx", "forced_mlx")
        if override == "ane":
            if not ane_available:
                raise ValueError("ANE backend is unavailable")
            if not ane_healthy:
                raise ValueError("ANE backend is not healthy")
            if token_count > self.config.ane_max_tokens:
                raise ValueError("request exceeds ANE fixed-shape capacity")
            return RouteDecision("ane", "forced_ane")

        if token_count < self.config.ane_min_tokens:
            return RouteDecision("mlx", "short_input")
        if token_count > self.config.ane_max_tokens:
            return RouteDecision("mlx", "over_ane_capacity")
        if not ane_available:
            return RouteDecision("mlx", "ane_unavailable")
        if not ane_healthy:
            return RouteDecision("mlx", "ane_unhealthy")
        return RouteDecision("ane", "ane_suitable")
