"""Tests for fastapi_apcore.registry -- singleton management."""

from __future__ import annotations

import threading
from unittest import mock

import pytest

from fastapi_apcore.engine import registry as reg


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_all_singletons():
    """Ensure every test starts with a clean slate."""
    reg._reset_registry()
    yield
    reg._reset_registry()


def _make_mock_settings(**overrides):
    """Return a mock ApcoreSettings with sensible defaults."""
    defaults = {
        "context_factory": None,
        "executor_config": None,
        "metrics": None,
        "middlewares": [],
        "acl_path": None,
        "observability_logging": None,
        "tracing": None,
        "embedded_server": None,
        "serve_transport": "stdio",
        "serve_host": "127.0.0.1",
        "serve_port": 9090,
        "server_name": "apcore-mcp",
        "server_version": None,
        "serve_validate_inputs": False,
        "serve_tags": None,
        "serve_prefix": None,
        "jwt_secret": None,
        "jwt_algorithm": "HS256",
        "jwt_audience": None,
        "jwt_issuer": None,
        "output_formatter": None,
    }
    defaults.update(overrides)
    return mock.MagicMock(**defaults)


# ---------------------------------------------------------------------------
# get_registry
# ---------------------------------------------------------------------------


class TestGetRegistry:
    """Tests for get_registry singleton."""

    def test_creates_singleton(self):
        """Two calls return the exact same Registry object."""
        r1 = reg.get_registry()
        r2 = reg.get_registry()
        assert r1 is r2

    def test_thread_safe(self):
        """Concurrent calls from multiple threads don't create duplicates."""
        results: list[object] = []
        barrier = threading.Barrier(8)

        def worker():
            barrier.wait()
            results.append(reg.get_registry())

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 8
        first = results[0]
        assert all(r is first for r in results)


# ---------------------------------------------------------------------------
# get_executor
# ---------------------------------------------------------------------------


class TestGetExecutor:
    """Tests for get_executor singleton."""

    @mock.patch("fastapi_apcore.engine.registry.get_extension_manager")
    @mock.patch("fastapi_apcore.engine.config.get_apcore_settings", return_value=_make_mock_settings())
    @mock.patch("apcore.Executor")
    def test_creates_singleton(self, mock_executor_cls, mock_settings, mock_ext_mgr):
        """Executor is lazily created on first call and reused."""
        sentinel = mock.MagicMock(name="executor-instance")
        mock_executor_cls.return_value = sentinel
        mock_ext_mgr.return_value = mock.MagicMock()

        e1 = reg.get_executor()
        e2 = reg.get_executor()

        assert e1 is e2
        mock_executor_cls.assert_called_once()


# ---------------------------------------------------------------------------
# get_context_factory
# ---------------------------------------------------------------------------


class TestGetContextFactory:
    """Tests for get_context_factory singleton."""

    @mock.patch(
        "fastapi_apcore.engine.config.get_apcore_settings",
        return_value=_make_mock_settings(context_factory=None),
    )
    def test_default(self, _mock_settings):
        """When context_factory setting is None, returns FastAPIContextFactory."""
        from fastapi_apcore.engine.context import FastAPIContextFactory

        factory = reg.get_context_factory()
        assert isinstance(factory, FastAPIContextFactory)

    @mock.patch(
        "fastapi_apcore.engine.config.get_apcore_settings",
        return_value=_make_mock_settings(context_factory="fastapi_apcore.engine.context.FastAPIContextFactory"),
    )
    def test_custom(self, _mock_settings):
        """When a dotted path is configured, the class is loaded dynamically."""
        from fastapi_apcore.engine.context import FastAPIContextFactory

        factory = reg.get_context_factory()
        assert isinstance(factory, FastAPIContextFactory)


# ---------------------------------------------------------------------------
# get_metrics_collector
# ---------------------------------------------------------------------------


class TestGetMetricsCollector:
    """Tests for get_metrics_collector singleton."""

    @mock.patch(
        "fastapi_apcore.engine.config.get_apcore_settings",
        return_value=_make_mock_settings(metrics=None),
    )
    def test_disabled_returns_none(self, _mock_settings):
        """Returns None when metrics is falsy."""
        result = reg.get_metrics_collector()
        assert result is None

    @mock.patch(
        "fastapi_apcore.engine.config.get_apcore_settings",
        return_value=_make_mock_settings(metrics=False),
    )
    def test_false_returns_none(self, _mock_settings):
        """Returns None when metrics is explicitly False."""
        result = reg.get_metrics_collector()
        assert result is None


# ---------------------------------------------------------------------------
# _reset_registry cascading
# ---------------------------------------------------------------------------


class TestResetRegistryCascades:
    """_reset_registry clears all dependent singletons."""

    def test_cascades(self):
        """After reset, get_registry returns a fresh instance."""
        r1 = reg.get_registry()
        reg._reset_registry()
        r2 = reg.get_registry()

        assert r1 is not r2

    def test_clears_all_dependents(self):
        """_reset_registry also clears executor, ext_manager, context_factory, etc."""
        reg._registry = mock.sentinel.registry
        reg._ext_manager = mock.sentinel.ext
        reg._executor = mock.sentinel.exec
        reg._context_factory = mock.sentinel.ctx
        reg._metrics_collector = mock.sentinel.metrics

        reg._reset_registry()

        assert reg._registry is None
        assert reg._ext_manager is None
        assert reg._executor is None
        assert reg._context_factory is None
        assert reg._metrics_collector is None


# ---------------------------------------------------------------------------
# _resolve_dotted_callable
# ---------------------------------------------------------------------------


class TestResolveDottedCallable:
    """Tests for _resolve_dotted_callable helper."""

    def test_resolves_existing(self):
        """Resolves a known stdlib callable."""
        result = reg._resolve_dotted_callable("json.loads")
        import json

        assert result is json.loads

    def test_missing_returns_none(self):
        """Returns None for a non-existent dotted path."""
        result = reg._resolve_dotted_callable("nonexistent.module.func")
        assert result is None

    def test_no_dot_returns_none(self):
        """Returns None when path has no module component."""
        result = reg._resolve_dotted_callable("nodot")
        assert result is None

    def test_missing_attr_returns_none(self):
        """Returns None when module exists but attr does not."""
        result = reg._resolve_dotted_callable("json.nonexistent_function_xyz")
        assert result is None
