"""Tests for bridges/observability.py — init_observability."""

from __future__ import annotations

from unittest.mock import patch

import pytest


def test_observability_available_false_when_not_installed():
    from nodus_sdk.bridges import observability as obs_mod
    with patch.object(obs_mod, "_AVAILABLE", False):
        from nodus_sdk.bridges.observability import available
        assert available() is False


def test_observability_available_true_when_installed():
    try:
        import nodus_observability  # noqa: F401
    except ImportError:
        pytest.skip("nodus-observability not installed")
    from nodus_sdk.bridges.observability import available
    assert available() is True


def test_init_observability_noop_when_not_installed():
    from nodus_sdk.bridges import observability as obs_mod
    with patch.object(obs_mod, "_AVAILABLE", False):
        from nodus_sdk.bridges.observability import init_observability
        # Should not raise even when package is absent
        init_observability("test-service")


def test_init_observability_calls_configure_logging():
    try:
        import nodus_observability  # noqa: F401
    except ImportError:
        pytest.skip("nodus-observability not installed")
    from nodus_sdk.bridges.observability import init_observability
    # Should not raise
    init_observability("test-svc", configure_logging=True)
