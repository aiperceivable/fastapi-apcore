"""Tests for fastapi_apcore.shortcuts -- convenience helpers."""

from __future__ import annotations

from unittest import mock

import pytest

from fastapi_apcore.engine import shortcuts


# ---------------------------------------------------------------------------
# executor_call
# ---------------------------------------------------------------------------


class TestExecutorCall:
    """Tests for executor_call (synchronous)."""

    @mock.patch("fastapi_apcore.engine.registry.get_executor")
    @mock.patch("fastapi_apcore.engine.registry.get_context_factory")
    def test_executor_call_delegates(self, mock_cf, mock_get_exec):
        """executor_call delegates to executor.call with the given inputs."""
        mock_executor = mock.MagicMock()
        mock_executor.call.return_value = {"result": 42}
        mock_get_exec.return_value = mock_executor

        result = shortcuts.executor_call("my.module", {"key": "value"})

        mock_executor.call.assert_called_once_with("my.module", {"key": "value"}, context=None)
        assert result == {"result": 42}

    @mock.patch("fastapi_apcore.engine.registry.get_executor")
    @mock.patch("fastapi_apcore.engine.registry.get_context_factory")
    def test_executor_call_with_request_builds_context(self, mock_cf, mock_get_exec):
        """When request is given but context is not, a context is built."""
        mock_executor = mock.MagicMock()
        mock_executor.call.return_value = {"ok": True}
        mock_get_exec.return_value = mock_executor

        fake_request = object()
        fake_context = mock.MagicMock()
        mock_cf.return_value.create_context.return_value = fake_context

        result = shortcuts.executor_call("my.module", {"a": 1}, request=fake_request)

        mock_cf.return_value.create_context.assert_called_once_with(fake_request)
        mock_executor.call.assert_called_once_with("my.module", {"a": 1}, context=fake_context)
        assert result == {"ok": True}

    @mock.patch("fastapi_apcore.engine.registry.get_executor")
    @mock.patch("fastapi_apcore.engine.registry.get_context_factory")
    def test_executor_call_defaults_inputs_to_empty_dict(self, mock_cf, mock_get_exec):
        """When inputs is None, an empty dict is passed."""
        mock_executor = mock.MagicMock()
        mock_executor.call.return_value = {}
        mock_get_exec.return_value = mock_executor

        shortcuts.executor_call("mod")

        mock_executor.call.assert_called_once_with("mod", {}, context=None)


# ---------------------------------------------------------------------------
# executor_call_async
# ---------------------------------------------------------------------------


class TestExecutorCallAsync:
    """Tests for executor_call_async."""

    @pytest.mark.asyncio
    @mock.patch("fastapi_apcore.engine.registry.get_executor")
    @mock.patch("fastapi_apcore.engine.registry.get_context_factory")
    async def test_executor_call_async_delegates(self, mock_cf, mock_get_exec):
        """executor_call_async delegates to executor.call_async."""
        mock_executor = mock.MagicMock()
        mock_executor.call_async = mock.AsyncMock(return_value={"async": True})
        mock_get_exec.return_value = mock_executor

        result = await shortcuts.executor_call_async("my.mod", {"x": 1})

        mock_executor.call_async.assert_called_once_with("my.mod", {"x": 1}, context=None)
        assert result == {"async": True}

    @pytest.mark.asyncio
    @mock.patch("fastapi_apcore.engine.registry.get_executor")
    @mock.patch("fastapi_apcore.engine.registry.get_context_factory")
    async def test_executor_call_async_with_request_builds_context(self, mock_cf, mock_get_exec):
        """When request is given but context is not, a context is built."""
        mock_executor = mock.MagicMock()
        mock_executor.call_async = mock.AsyncMock(return_value={"ok": True})
        mock_get_exec.return_value = mock_executor

        fake_request = object()
        fake_context = mock.MagicMock()
        mock_cf.return_value.create_context.return_value = fake_context

        await shortcuts.executor_call_async("m", request=fake_request)

        mock_cf.return_value.create_context.assert_called_once_with(fake_request)
        mock_executor.call_async.assert_called_once_with("m", {}, context=fake_context)


# ---------------------------------------------------------------------------
# report_progress / elicit -- graceful degradation without apcore_mcp
# ---------------------------------------------------------------------------


class TestMCPHelpers:
    """Tests for report_progress and elicit when apcore_mcp is not installed."""

    @pytest.mark.asyncio
    async def test_report_progress_noop_without_mcp(self):
        """report_progress silently does nothing when apcore_mcp is absent."""
        with mock.patch.dict("sys.modules", {"apcore_mcp": None}):
            # Should not raise
            await shortcuts.report_progress(None, 0.5, total=1.0, message="halfway")

    @pytest.mark.asyncio
    async def test_elicit_returns_none_without_mcp(self):
        """elicit returns None when apcore_mcp is absent."""
        with mock.patch.dict("sys.modules", {"apcore_mcp": None}):
            result = await shortcuts.elicit(None, "Pick one")
            assert result is None
