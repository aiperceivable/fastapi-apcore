"""AsyncTaskManager singleton for fastapi-apcore.

Provides a process-level singleton AsyncTaskManager configured from settings.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

logger = logging.getLogger("fastapi_apcore")

_task_manager: Any = None
_task_manager_lock = threading.Lock()


def get_task_manager() -> Any:
    """Return the singleton AsyncTaskManager for this process.

    Lazily created on first call, configured from APCORE_TASK_* settings.

    Returns:
        The shared apcore.AsyncTaskManager instance.
    """
    global _task_manager
    if _task_manager is None:
        with _task_manager_lock:
            if _task_manager is None:
                from apcore import AsyncTaskManager
                from fastapi_apcore.engine.config import get_apcore_settings
                from fastapi_apcore.engine.registry import get_executor

                settings = get_apcore_settings()
                executor = get_executor()
                _task_manager = AsyncTaskManager(
                    executor=executor,
                    max_concurrent=settings.task_max_concurrent,
                    max_tasks=settings.task_max_tasks,
                )
                logger.debug(
                    "Created AsyncTaskManager (max_concurrent=%d, max_tasks=%d)",
                    settings.task_max_concurrent,
                    settings.task_max_tasks,
                )
    return _task_manager


def _reset_task_manager() -> None:
    """Reset the singleton task manager. For testing only."""
    global _task_manager
    with _task_manager_lock:
        _task_manager = None
