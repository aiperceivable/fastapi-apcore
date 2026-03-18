"""Tests for observability auto-setup."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from types import SimpleNamespace

from fastapi_apcore.engine.observability import setup_observability


def _make_settings(**overrides):
    """Create a mock settings object."""
    defaults = {
        "tracing": None,
        "metrics": None,
        "observability_logging": None,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class TestSetupObservability:
    def test_all_disabled(self):
        settings = _make_settings()
        ext_data: dict = {}
        setup_observability(settings, ext_data)
        assert ext_data["observability_middlewares"] == []
        assert ext_data["metrics_collector"] is None

    def test_tracing_enabled_true(self):
        settings = _make_settings(tracing=True)
        ext_data: dict = {}
        with (
            patch("apcore.observability.tracing.TracingMiddleware"),
            patch("apcore.observability.tracing.StdoutExporter"),
            patch("apcore.observability.ErrorHistory"),
            patch("apcore.middleware.ErrorHistoryMiddleware"),
        ):
            setup_observability(settings, ext_data)
        assert len(ext_data["observability_middlewares"]) >= 1

    def test_metrics_enabled_true(self):
        settings = _make_settings(metrics=True)
        ext_data: dict = {}
        with (
            patch("apcore.observability.metrics.MetricsCollector") as mock_mc,
            patch("apcore.observability.metrics.MetricsMiddleware"),
            patch("apcore.observability.ErrorHistory"),
            patch("apcore.middleware.ErrorHistoryMiddleware"),
            patch("apcore.observability.UsageCollector"),
            patch("apcore.observability.UsageMiddleware"),
        ):
            mock_mc.return_value = MagicMock()
            setup_observability(settings, ext_data)
        assert ext_data["metrics_collector"] is not None

    def test_logging_enabled_true(self):
        settings = _make_settings(observability_logging=True)
        ext_data: dict = {}
        with (
            patch("apcore.observability.context_logger.ContextLogger"),
            patch("apcore.observability.context_logger.ObsLoggingMiddleware"),
            patch("apcore.observability.ErrorHistory"),
            patch("apcore.middleware.ErrorHistoryMiddleware"),
        ):
            setup_observability(settings, ext_data)
        assert len(ext_data["observability_middlewares"]) >= 1
