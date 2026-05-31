"""WebhookBridge — outbound webhook delivery with HMAC signing, retry, and circuit breaking."""

from __future__ import annotations

import hashlib
import hmac
import importlib.util
import json
import time
from typing import TYPE_CHECKING, Any

_HTTPX_AVAILABLE = importlib.util.find_spec("httpx") is not None

if TYPE_CHECKING:
    from nodus.runtime.embedding import NodusRuntime


def _sign_payload(secret: str, body: bytes) -> str:
    """Compute HMAC-SHA256 signature for webhook payload."""
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


class WebhookBridge:
    """Outbound webhook bridge with optional HMAC signing, retry, and circuit-breaking.

    Requires ``nodus-sdk[webhooks]`` (``httpx>=0.27``).

    Usage::

        bridge = WebhookBridge(secret="my-webhook-secret")
        rt.attach_webhook(bridge)
        # .nd: webhook_send("https://example.com/hook", {event: "order.placed"}, "order.placed")
    """

    def __init__(
        self,
        *,
        secret: str | None = None,
        retry_policy: Any = None,
        circuit_breaker: Any = None,
        timeout: float = 10.0,
    ) -> None:
        if not _HTTPX_AVAILABLE:
            raise ImportError("httpx not installed. pip install nodus-sdk[webhooks]")
        self._secret = secret
        self._retry_policy = retry_policy
        self._circuit_breaker = circuit_breaker
        self._timeout = timeout

    def send(
        self,
        url: str,
        payload: dict,
        *,
        event_type: str | None = None,
        headers: dict | None = None,
    ) -> dict:
        """POST payload to url. Returns {status, status_code, response}."""
        import httpx

        body = json.dumps(payload, separators=(",", ":")).encode()
        req_headers = {"Content-Type": "application/json"}
        if event_type:
            req_headers["X-Nodus-Event"] = event_type
        if self._secret:
            req_headers["X-Nodus-Signature"] = _sign_payload(self._secret, body)
        if headers:
            req_headers.update(headers)

        def _do_send() -> dict:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.post(url, content=body, headers=req_headers)
                try:
                    resp_body = resp.json()
                except Exception:
                    resp_body = resp.text
                return {
                    "status": "ok" if resp.is_success else "error",
                    "status_code": resp.status_code,
                    "response": resp_body,
                }

        if self._circuit_breaker is not None:
            try:
                return self._circuit_breaker.call(_do_send)
            except Exception as exc:
                return {"status": "error", "status_code": 0, "response": str(exc)}

        if self._retry_policy is not None:
            from nodus_retry import execute_with_retry
            try:
                return execute_with_retry(_do_send, policy=self._retry_policy)
            except Exception as exc:
                return {"status": "error", "status_code": 0, "response": str(exc)}

        try:
            return _do_send()
        except Exception as exc:
            return {"status": "error", "status_code": 0, "response": str(exc)}

    async def send_async(
        self,
        url: str,
        payload: dict,
        *,
        event_type: str | None = None,
        headers: dict | None = None,
    ) -> dict:
        """Async POST — same contract as send()."""
        import httpx

        body = json.dumps(payload, separators=(",", ":")).encode()
        req_headers = {"Content-Type": "application/json"}
        if event_type:
            req_headers["X-Nodus-Event"] = event_type
        if self._secret:
            req_headers["X-Nodus-Signature"] = _sign_payload(self._secret, body)
        if headers:
            req_headers.update(headers)

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(url, content=body, headers=req_headers)
                try:
                    resp_body = resp.json()
                except Exception:
                    resp_body = resp.text
                return {
                    "status": "ok" if resp.is_success else "error",
                    "status_code": resp.status_code,
                    "response": resp_body,
                }
        except Exception as exc:
            return {"status": "error", "status_code": 0, "response": str(exc)}

    def register_host_functions(self, runtime: "NodusRuntime") -> None:
        """Register webhook_send on the runtime."""
        bridge = self

        def webhook_send(url: Any, payload: Any, event_type: Any = None) -> dict:
            if not isinstance(url, str):
                return {"status": "error", "status_code": 0, "response": "url must be a string"}
            p = dict(payload.fields) if hasattr(payload, "fields") else (payload if isinstance(payload, dict) else {})
            ev = str(event_type) if event_type is not None else None
            return bridge.send(url, p, event_type=ev)

        runtime.register_function("webhook_send", webhook_send, arity=3)
