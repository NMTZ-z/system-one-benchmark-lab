"""Small standard-library HTTP service for Local System One."""

from __future__ import annotations

import hmac
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .engine import DecisionEngine
from .schemas import DecisionRequest
from .workflows import (
    ModelTierGate,
    ModelTierRequest,
    NotificationGate,
    NotificationGateRequest,
    SearchGate,
    SearchGateRequest,
)

MAX_BODY_BYTES = 1_048_576


def create_server(
    engine: DecisionEngine,
    *,
    host: str = "127.0.0.1",
    port: int = 8787,
    auth_token: str | None = None,
) -> ThreadingHTTPServer:
    search_gate = SearchGate(engine)
    model_tier_gate = ModelTierGate(engine)
    notification_gate = NotificationGate(engine)

    class Handler(BaseHTTPRequestHandler):
        server_version = "LocalSystemOne/0.1"

        def log_message(self, format: str, *args: Any) -> None:
            # Avoid default request logging because URLs/metadata can become sensitive.
            return

        def _json(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _authorized(self) -> bool:
            if auth_token is None:
                return True
            supplied = self.headers.get("Authorization", "")
            expected = f"Bearer {auth_token}"
            return hmac.compare_digest(supplied, expected)

        def _read_payload(self) -> dict[str, Any]:
            raw_length = self.headers.get("Content-Length")
            if raw_length is None:
                raise ValueError("Content-Length is required")
            length = int(raw_length)
            if length < 0 or length > MAX_BODY_BYTES:
                raise ValueError("request body is too large")
            raw = self.rfile.read(length)
            payload = json.loads(raw.decode("utf-8"))
            if not isinstance(payload, dict):
                raise TypeError("request body must be a JSON object")
            return payload

        def do_GET(self) -> None:
            if not self._authorized():
                self._json(401, {"error": "unauthorized"})
                return
            if self.path == "/health":
                self._json(200, engine.health_snapshot())
                return
            if self.path == "/metrics":
                self._json(200, engine.metrics_snapshot())
                return
            self._json(404, {"error": "not_found"})

        def do_POST(self) -> None:
            if not self._authorized():
                self._json(401, {"error": "unauthorized"})
                return
            if self.path == "/v1/workflows/search-gate":
                try:
                    payload = self._read_payload()
                    request = SearchGateRequest.from_payload(payload)
                    response = search_gate.decide(request)
                except (ValueError, TypeError) as error:
                    self._json(400, {"error": "invalid_request", "detail": str(error)})
                    return
                except Exception as error:  # noqa: BLE001 - service boundary
                    engine.metrics.record_error()
                    self._json(
                        500,
                        {
                            "error": "decision_failed",
                            "detail": type(error).__name__,
                        },
                    )
                    return
                self._json(200, response)
                return

            if self.path == "/v1/workflows/model-tier-gate":
                try:
                    payload = self._read_payload()
                    request = ModelTierRequest.from_payload(payload)
                    response = model_tier_gate.decide(request)
                except (ValueError, TypeError) as error:
                    self._json(400, {"error": "invalid_request", "detail": str(error)})
                    return
                except Exception as error:  # noqa: BLE001 - service boundary
                    engine.metrics.record_error()
                    self._json(
                        500,
                        {
                            "error": "decision_failed",
                            "detail": type(error).__name__,
                        },
                    )
                    return
                self._json(200, response)
                return

            if self.path == "/v1/workflows/notification-gate":
                try:
                    payload = self._read_payload()
                    request = NotificationGateRequest.from_payload(payload)
                    response = notification_gate.decide(request)
                except (ValueError, TypeError) as error:
                    self._json(400, {"error": "invalid_request", "detail": str(error)})
                    return
                except Exception as error:  # noqa: BLE001 - service boundary
                    engine.metrics.record_error()
                    self._json(
                        500,
                        {
                            "error": "decision_failed",
                            "detail": type(error).__name__,
                        },
                    )
                    return
                self._json(200, response)
                return

            primitive_by_path = {
                "/v1/choice": "choice",
                "/v1/score": "score",
                "/v1/noul": "noul",
            }
            primitive = primitive_by_path.get(self.path)
            if primitive is None:
                self._json(404, {"error": "not_found"})
                return

            try:
                payload = self._read_payload()
                request = DecisionRequest.from_payload(primitive, payload)
                response = engine.decide(request)
            except (ValueError, TypeError) as error:
                self._json(400, {"error": "invalid_request", "detail": str(error)})
                return
            except Exception as error:  # noqa: BLE001 - service boundary
                engine.metrics.record_error()
                self._json(
                    500,
                    {
                        "error": "decision_failed",
                        "detail": type(error).__name__,
                    },
                )
                return

            self._json(200, response)

    return ThreadingHTTPServer((host, port), Handler)