"""LLMBridge — thin bridge over nodus-llm's FailoverClient."""

from __future__ import annotations

import importlib.util
from typing import Any

_AVAILABLE = importlib.util.find_spec("nodus_llm") is not None


class LLMBridge:
    """Thin bridge wrapping nodus-llm for multi-provider LLM failover.

    Requires ``nodus-sdk[llm]`` (``nodus-llm``).
    """

    def __init__(self, credentials: list[Any] | None = None) -> None:
        self._credentials = credentials or []

    def available(self) -> bool:
        return _AVAILABLE

    def failover_client(self, provider_fn: Any = None) -> Any:
        """Return a FailoverClient configured with provided credentials.

        provider_fn maps CredentialProfile → LLMClient. Required by nodus-llm;
        pass a callable that constructs a provider-specific client.
        """
        if not _AVAILABLE:
            raise ImportError("nodus-llm not installed. pip install nodus-sdk[llm]")
        if provider_fn is None:
            raise ValueError(
                "provider_fn is required: pass a callable that maps CredentialProfile → LLMClient"
            )
        from nodus_llm import FailoverClient, CredentialStore
        store = CredentialStore(profiles=self._credentials)
        return FailoverClient(store, provider_fn)

    def credential_store(self) -> Any:
        """Return a CredentialStore from the provided credential profiles."""
        if not _AVAILABLE:
            raise ImportError("nodus-llm not installed. pip install nodus-sdk[llm]")
        from nodus_llm import CredentialStore
        return CredentialStore(profiles=self._credentials)
