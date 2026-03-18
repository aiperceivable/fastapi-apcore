"""Convenience helpers for calling apcore modules from FastAPI routes.

Wraps the common pattern of wiring together get_executor(),
get_context_factory(), and Executor.call() into a single function call.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger("fastapi_apcore")


async def report_progress(
    context: Any,
    progress: float,
    total: float | None = None,
    message: str | None = None,
) -> None:
    """Report execution progress to the MCP client."""
    try:
        from apcore_mcp import report_progress as _report_progress

        await _report_progress(context, progress, total=total, message=message)
    except ImportError:
        logger.debug("apcore-mcp not installed; report_progress is a no-op")


async def elicit(
    context: Any,
    message: str,
    requested_schema: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Ask the MCP client for user input via elicitation."""
    try:
        from apcore_mcp import elicit as _elicit

        result = await _elicit(context, message, requested_schema=requested_schema)
        return result  # type: ignore[return-value]
    except ImportError:
        logger.debug("apcore-mcp not installed; elicit returns None")
        return None


def executor_call(
    module_id: str,
    inputs: dict[str, Any] | None = None,
    *,
    request: Any = None,
    context: Any = None,
) -> dict[str, Any]:
    """Execute an apcore module synchronously."""
    from fastapi_apcore.engine.registry import get_context_factory, get_executor

    executor = get_executor()
    if context is None and request is not None:
        context = get_context_factory().create_context(request)
    result: dict[str, Any] = executor.call(module_id, inputs or {}, context=context)
    return result


async def executor_call_async(
    module_id: str,
    inputs: dict[str, Any] | None = None,
    *,
    request: Any = None,
    context: Any = None,
) -> dict[str, Any]:
    """Execute an apcore module asynchronously."""
    from fastapi_apcore.engine.registry import get_context_factory, get_executor

    executor = get_executor()
    if context is None and request is not None:
        context = get_context_factory().create_context(request)
    result: dict[str, Any] = await executor.call_async(module_id, inputs or {}, context=context)
    return result


async def executor_stream(
    module_id: str,
    inputs: dict[str, Any] | None = None,
    *,
    request: Any = None,
    context: Any = None,
) -> AsyncIterator[dict[str, Any]]:
    """Stream an apcore module's output asynchronously."""
    from fastapi_apcore.engine.registry import get_context_factory, get_executor

    executor = get_executor()
    if context is None and request is not None:
        context = get_context_factory().create_context(request)
    async for chunk in executor.stream(module_id, inputs or {}, context=context):
        yield chunk


def cancellable_call(
    module_id: str,
    inputs: dict[str, Any] | None = None,
    *,
    request: Any = None,
    context: Any = None,
    timeout: float | None = None,
) -> dict[str, Any]:
    """Execute an apcore module with CancelToken."""
    from apcore import CancelToken, Context
    from fastapi_apcore.engine.registry import get_context_factory, get_executor
    from fastapi_apcore.engine.config import get_apcore_settings

    executor = get_executor()
    token = CancelToken()

    if context is None:
        if request is not None:
            context = get_context_factory().create_context(request)
        else:
            context = Context.create()
    context.cancel_token = token

    if timeout is None:
        timeout = get_apcore_settings().cancel_default_timeout

    if timeout is not None:
        import threading

        timer = threading.Timer(timeout, token.cancel)
        timer.start()
        try:
            result: dict[str, Any] = executor.call(module_id, inputs or {}, context=context)
            return result
        finally:
            timer.cancel()

    result = executor.call(module_id, inputs or {}, context=context)
    return result


async def cancellable_call_async(
    module_id: str,
    inputs: dict[str, Any] | None = None,
    *,
    request: Any = None,
    context: Any = None,
    timeout: float | None = None,
) -> dict[str, Any]:
    """Execute an apcore module asynchronously with CancelToken."""
    import asyncio
    from apcore import CancelToken, Context
    from fastapi_apcore.engine.registry import get_context_factory, get_executor
    from fastapi_apcore.engine.config import get_apcore_settings

    executor = get_executor()
    token = CancelToken()

    if context is None:
        if request is not None:
            context = get_context_factory().create_context(request)
        else:
            context = Context.create()
    context.cancel_token = token

    if timeout is None:
        timeout = get_apcore_settings().cancel_default_timeout

    if timeout is not None:

        async def _cancel_after_timeout() -> None:
            await asyncio.sleep(timeout)
            token.cancel()

        cancel_task = asyncio.create_task(_cancel_after_timeout())
        try:
            result: dict[str, Any] = await executor.call_async(module_id, inputs or {}, context=context)
            return result
        finally:
            cancel_task.cancel()

    result = await executor.call_async(module_id, inputs or {}, context=context)
    return result


async def submit_task(
    module_id: str,
    inputs: dict[str, Any] | None = None,
    *,
    context: Any = None,
) -> str:
    """Submit an async task to the AsyncTaskManager."""
    from fastapi_apcore.engine.tasks import get_task_manager

    tm = get_task_manager()
    task_id: str = await tm.submit(module_id, inputs or {}, context=context)
    return task_id


def get_task_status(task_id: str) -> Any:
    """Query task status from the AsyncTaskManager."""
    from fastapi_apcore.engine.tasks import get_task_manager

    return get_task_manager().get_status(task_id)


async def cancel_task(task_id: str) -> bool:
    """Cancel a running async task."""
    from fastapi_apcore.engine.tasks import get_task_manager

    cancelled: bool = await get_task_manager().cancel(task_id)
    return cancelled
