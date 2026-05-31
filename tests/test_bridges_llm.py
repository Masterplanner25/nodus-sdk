"""Tests for bridges/llm.py — LLMBridge."""

from __future__ import annotations

from unittest.mock import patch

import pytest


def test_llm_bridge_available_false_when_not_installed():
    from nodus_sdk.bridges import llm as llm_mod
    with patch.object(llm_mod, "_AVAILABLE", False):
        from nodus_sdk.bridges.llm import LLMBridge
        b = LLMBridge()
        assert b.available() is False


def test_llm_bridge_available_true_when_installed():
    try:
        import nodus_llm  # noqa: F401
    except ImportError:
        pytest.skip("nodus-llm not installed")
    from nodus_sdk.bridges.llm import LLMBridge
    b = LLMBridge()
    assert b.available() is True


def test_llm_bridge_failover_client_raises_when_not_installed():
    from nodus_sdk.bridges import llm as llm_mod
    with patch.object(llm_mod, "_AVAILABLE", False):
        from nodus_sdk.bridges.llm import LLMBridge
        b = LLMBridge()
        with pytest.raises(ImportError, match="nodus-llm"):
            b.failover_client()


def test_llm_bridge_credential_store_raises_when_not_installed():
    from nodus_sdk.bridges import llm as llm_mod
    with patch.object(llm_mod, "_AVAILABLE", False):
        from nodus_sdk.bridges.llm import LLMBridge
        b = LLMBridge()
        with pytest.raises(ImportError):
            b.credential_store()


def test_llm_bridge_failover_client_when_available():
    try:
        import nodus_llm  # noqa: F401
    except ImportError:
        pytest.skip("nodus-llm not installed")
    from nodus_sdk.bridges.llm import LLMBridge
    from unittest.mock import MagicMock
    b = LLMBridge(credentials=[])
    provider_fn = MagicMock(return_value=MagicMock())
    client = b.failover_client(provider_fn=provider_fn)
    assert client is not None


def test_llm_bridge_failover_client_raises_without_provider_fn():
    try:
        import nodus_llm  # noqa: F401
    except ImportError:
        pytest.skip("nodus-llm not installed")
    from nodus_sdk.bridges.llm import LLMBridge
    b = LLMBridge(credentials=[])
    with pytest.raises(ValueError, match="provider_fn"):
        b.failover_client()
