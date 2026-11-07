"""Command-line entry point for the Local System One service."""

from __future__ import annotations

import argparse
import ipaddress
import os
from pathlib import Path
import sys

from .engine import DecisionEngine
from .health import ANEHealthGate
from .router import DecisionRouter, RouterConfig
from .runtime import ANERuntime, MLXRuntime
from .security import access_token_path, read_access_token
from .service import create_server


def _is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] in {
        "doctor", "start", "install", "shadow", "status", "off", "stop",
        "uninstall", "download-model",
    }:
        from .first_run import main as first_run_main
        return first_run_main(sys.argv[1:])
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=("First-run commands: doctor, download-model, install, start, shadow, "
                "status, off, stop, uninstall. For help: local-system-one doctor --help."),
    )
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
    parser.add_argument("--auth-token", help=argparse.SUPPRESS)
    args = parser.parse_args()
    owner_token = os.environ.pop("LOCAL_SYSTEM_ONE_OWNER_TOKEN", None)
    auth_token = os.environ.pop("LOCAL_SYSTEM_ONE_AUTH_TOKEN", None)

    if args.auth_token is not None:
        parser.error("do not put bearer credentials on the command line; use a private token file")

    if owner_token and (args.host != "127.0.0.1" or args.source != "laya-typed-decisions"):
        parser.error("owned first-run Runtime requires the pinned model and 127.0.0.1")

    if not _is_loopback(args.host):
        parser.error("Runtime only supports loopback binding")
    if not auth_token:
        try:
            path = Path(os.environ["LOCAL_SYSTEM_ONE_AUTH_TOKEN_FILE"]) if os.environ.get("LOCAL_SYSTEM_ONE_AUTH_TOKEN_FILE") else access_token_path()
            auth_token = read_access_token(path)
        except (OSError, ValueError):
            print("A private Runtime access token is required; use managed start or configure LOCAL_SYSTEM_ONE_AUTH_TOKEN_FILE.", file=sys.stderr)
            return 1

    from .runtime.sources import TYPED_DECISIONS_ALIAS, TYPED_DECISIONS_MODEL_ID
    model_source = args.source
    if args.source in {TYPED_DECISIONS_ALIAS, TYPED_DECISIONS_MODEL_ID}:
        os.environ["HF_HUB_OFFLINE"] = "1"
        from .first_run import _model_snapshot
        model_source = _model_snapshot()
        if model_source is None:
            print("Pinned model is missing or failed verification; run download-model explicitly.", file=sys.stderr)
            return 1

    mlx = MLXRuntime(model_source)
    ane = (
        ANERuntime(model_source, args.ane_package, length=args.ane_max_tokens)
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

    if owner_token:
        from .probes import PROBES
        from .runtime.sources import TYPED_DECISIONS_MODEL_ID, TYPED_DECISIONS_REVISION
        from .schemas import selected_label

        if not selected_label(mlx.predict(*PROBES[0])):
            raise RuntimeError("MLX startup inference did not return a decision")
        engine.runtime_identity = {
            "backend": "mlx", "model": TYPED_DECISIONS_MODEL_ID,
            "revision": TYPED_DECISIONS_REVISION, "inference_verified": True,
        }

    if ane is not None:
        print("ANE startup probe:", engine.startup_probe(), flush=True)
    else:
        print("ANE disabled; MLX fallback only.", flush=True)

    server = create_server(
        engine,
        host=args.host,
        port=args.port,
        auth_token=auth_token,
        owner_token=owner_token,
    )
    print(f"Local System One listening on http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0
