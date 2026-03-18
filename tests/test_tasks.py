"""Tests for fastapi_apcore.tasks -- AsyncTaskManager singleton."""

from __future__ import annotations

import sys
from typing import Any
from unittest import mock

import pytest

from fastapi_apcore.engine import tasks


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Ensure every test starts with a clean task manager."""
    tasks._reset_task_manager()
    yield
    tasks._reset_task_manager()


def _make_mock_settings(**overrides: Any) -> Any:
    """Return a mock ApcoreSettings with task defaults."""
    settings = mock.MagicMock()
    settings.task_max_concurrent = overrides.get("task_max_concurrent", 10)
    settings.task_max_tasks = overrides.get("task_max_tasks", 1000)
    return settings


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGetTaskManager:
    """Tests for get_task_manager singleton creation."""

    def test_get_task_manager_creates_singleton(self):
        """get_task_manager creates an AsyncTaskManager on first call and reuses it."""
        mock_atm_cls = mock.MagicMock()
        sentinel = mock.MagicMock()
        mock_atm_cls.return_value = sentinel

        mock_executor = mock.MagicMock()
        mock_settings = _make_mock_settings()

        mock_apcore = mock.MagicMock()
        mock_apcore.AsyncTaskManager = mock_atm_cls

        with (
            mock.patch.dict(sys.modules, {"apcore": mock_apcore}),
            mock.patch("fastapi_apcore.engine.registry.get_executor", return_value=mock_executor),
            mock.patch("fastapi_apcore.engine.config.get_apcore_settings", return_value=mock_settings),
        ):
            tm1 = tasks.get_task_manager()
            tm2 = tasks.get_task_manager()

        assert tm1 is sentinel
        assert tm1 is tm2
        mock_atm_cls.assert_called_once_with(
            executor=mock_executor,
            max_concurrent=10,
            max_tasks=1000,
        )

    def test_reset_task_manager(self):
        """_reset_task_manager clears the cached singleton."""
        tasks._task_manager = mock.MagicMock()
        assert tasks._task_manager is not None

        tasks._reset_task_manager()

        assert tasks._task_manager is None
