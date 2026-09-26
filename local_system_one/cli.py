"""Command-line entry point for the Local System One service."""

from __future__ import annotations

import argparse
import ipaddress
import os
from pathlib import Path

from .engine import DecisionEngine
from .health import ANEHealthGate
from .router import DecisionRouter, RouterConfig
from .runtime import ANERuntime, MLXRuntime
from .service import create_server


def _is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        default="laya-typed-decisions",
        help=(
            "Local model directory or the pinned 'laya-typed-decisions' alias "
            "(default: laya-typed-decisions)"
        ),
    )
    parser.add_argument("--ane-package", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--ane-min-tokens", type=int, default=192)
    parser.add_argument("--ane-max-tokens", type=int, default=512)
    parser.add_argument("--ane-max-p50-ms", type=float, default=125.0)
    parser.add_argument(
        "--auth-token",
        default=os.environ.get("LOCAL_SYSTEM_ONE_AUTH_TOKEN"),
    )
    args = parser.parse_args()

    if not _is_loopback(args.host) and not args.auth_token:
        parser.error(
            "non-loopback binding requires --auth-token or LOCAL_SYSTEM_ONE_AUTH_TOKEN"
        )

    mlx = MLXRuntime(args.source)
    ane = (
        ANERuntime(args.source, args.ane_package, length=args.ane_max_tokens)
        if args.ane_package
        else None
    )
    health = ANEHealthGate(
        available=ane is not None,
        max_p50_ms=args.ane_max_p50_ms,
    )
    router = DecisionRouter(
        RouterConfig(
            ane_min_tokens=args.ane_min_tokens,
            ane_max_tokens=args.ane_max_tokens,
        )
    )
    engine = DecisionEngine(mlx=mlx, ane=ane, router=router, health=health)

    if ane is not None:
        print("ANE startup probe:", engine.startup_probe(), flush=True)
    else:
        print("ANE disabled; MLX fallback only.", flush=True)

    server = create_server(
        engine,
        host=args.host,
        port=args.port,
        auth_token=args.auth_token,
    )
    print(f"Local System One listening on http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0
