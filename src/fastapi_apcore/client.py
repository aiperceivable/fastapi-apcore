"""FastAPIApcore: Unified entry point for fastapi-apcore.

Consolidates Registry, Executor, ContextFactory, TaskManager, and MCP
serving into a single class with a FastAPI-aware API.

Usage::

    from fastapi_apcore import FastAPIApcore

    app = FastAPIApcore()

    # Call a module
    result = app.call("users.list", {"page": 1}, request=request)

    # Async call
    result = await app.call_async("users.list", {"page": 1}, request=request)

    # Register a module
    @app.module(id="math.add")
    def add(a: int, b: int) -> int:
        return a + b

    # Scan endpoints
    modules = app.scan(fastapi_app)

    # Start MCP server
    app.serve(transport="streamable-http", port=9090, explorer=True)
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from fastapi import FastAPI

logger = logging.getLogger("fastapi_apcore")

_instance: FastAPIApcore | None = None
_instance_lock = threading.Lock()


class FastAPIApcore:
    """Unified entry point for fastapi-apcore.

    Provides a single object to access all fastapi-apcore functionality:
    Registry, Executor, context mapping, task management, scanning,
    MCP serving, and OpenAI export.

    All singletons are lazily accessed via properties, so this class
    integrates seamlessly with FastAPI's app lifecycle.
    """

    def __init__(self) -> None:
        """Create a FastAPIApcore instance."""

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def init_app(
        self,
        app: FastAPI,
        *,
        scan: bool = True,
        scan_source: str = "openapi",
        include: str | None = None,
        exclude: str | None = None,
    ) -> None:
        """Initialize fastapi-apcore with a FastAPI application.

        Performs route scanning, auto-discovery, and optionally starts
        the embedded MCP server.  Should be called during application
        startup (e.g., in a lifespan context manager).

        Args:
            app: The FastAPI application instance.
            scan: Whether to auto-scan FastAPI routes and register them
                as apcore modules.  Defaults to True.
            scan_source: Scanner backend to use ('openapi' or 'native').
            include: Regex pattern — only register matching module IDs.
            exclude: Regex pattern — skip matching module IDs.
        """
        from fastapi_apcore.engine.config import get_apcore_settings
        from fastapi_apcore.engine.registry import get_extension_manager, get_registry

        settings = get_apcore_settings()
        registry = get_registry()

        # 1. Auto-discover modules from YAML bindings / module_packages
        if settings.auto_discover:
            ext_mgr = get_extension_manager()
            discoverer = ext_mgr.get("discoverer")
            if discoverer is not None:
                discovered = discoverer.discover([settings.module_dir])
                for entry in discovered:
                    try:
                        registry.register(entry["module_id"], entry["module"])
                    except Exception:
                        logger.warning(
                            "Failed to register %s",
                            entry["module_id"],
                            exc_info=True,
                        )
                logger.info("Auto-discovered %d modules", len(discovered))

        # 2. Scan FastAPI routes and register as apcore modules
        if scan:
            from fastapi_apcore.output import get_writer

            scanned = self.scan(app, source=scan_source, include=include, exclude=exclude)
            if scanned:
                writer = get_writer(None)  # RegistryWriter
                writer.write(scanned, registry)
                logger.info("Scanned and registered %d FastAPI routes", len(scanned))

        # 3. Hot-reload
        if settings.hot_reload:
            watch_paths = settings.hot_reload_paths or [settings.module_dir]
            try:
                registry.watch(paths=watch_paths)
                logger.info("Hot-reload enabled for %s", watch_paths)
            except Exception:
                logger.warning("Hot-reload not available", exc_info=True)

        # 4. Start embedded server if configured
        if settings.embedded_server:
            from fastapi_apcore.engine.registry import start_embedded_server

            start_embedded_server()

    # ------------------------------------------------------------------
    # Properties -- lazy access to singletons
    # ------------------------------------------------------------------

    @property
    def registry(self) -> Any:
        """The apcore Registry singleton."""
        from fastapi_apcore.engine.registry import get_registry

        return get_registry()

    @property
    def executor(self) -> Any:
        """The apcore Executor singleton (with extensions applied)."""
        from fastapi_apcore.engine.registry import get_executor

        return get_executor()

    @property
    def extension_manager(self) -> Any:
        """The ExtensionManager singleton."""
        from fastapi_apcore.engine.registry import get_extension_manager

        return get_extension_manager()

    @property
    def context_factory(self) -> Any:
        """The ContextFactory singleton."""
        from fastapi_apcore.engine.registry import get_context_factory

        return get_context_factory()

    @property
    def metrics_collector(self) -> Any | None:
        """The MetricsCollector singleton, or None if disabled."""
        from fastapi_apcore.engine.registry import get_metrics_collector

        return get_metrics_collector()

    @property
    def task_manager(self) -> Any:
        """The AsyncTaskManager singleton."""
        from fastapi_apcore.engine.tasks import get_task_manager

        return get_task_manager()

    @property
    def settings(self) -> Any:
        """The validated ApcoreSettings dataclass."""
        from fastapi_apcore.engine.config import get_apcore_settings

        return get_apcore_settings()

    # ------------------------------------------------------------------
    # Context helpers
    # ------------------------------------------------------------------

    def _resolve_context(
        self,
        request: Any = None,
        context: Any = None,
    ) -> Any:
        """Build an apcore Context from a FastAPI request or explicit context."""
        if context is not None:
            return context
        if request is not None:
            return self.context_factory.create_context(request)
        return None

    # ------------------------------------------------------------------
    # Module execution
    # ------------------------------------------------------------------

    def call(
        self,
        module_id: str,
        inputs: dict[str, Any] | None = None,
        *,
        request: Any = None,
        context: Any = None,
    ) -> dict[str, Any]:
        """Execute a module synchronously."""
        ctx = self._resolve_context(request, context)
        return self.executor.call(module_id, inputs or {}, context=ctx)

    async def call_async(
        self,
        module_id: str,
        inputs: dict[str, Any] | None = None,
        *,
        request: Any = None,
        context: Any = None,
    ) -> dict[str, Any]:
        """Execute a module asynchronously."""
        ctx = self._resolve_context(request, context)
        return await self.executor.call_async(module_id, inputs or {}, context=ctx)

    async def stream(
        self,
        module_id: str,
        inputs: dict[str, Any] | None = None,
        *,
        request: Any = None,
        context: Any = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream a module's output asynchronously."""
        ctx = self._resolve_context(request, context)
        async for chunk in self.executor.stream(module_id, inputs or {}, context=ctx):
            yield chunk

    def cancellable_call(
        self,
        module_id: str,
        inputs: dict[str, Any] | None = None,
        *,
        request: Any = None,
        context: Any = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Execute a module with cooperative cancellation."""
        from fastapi_apcore.engine.shortcuts import cancellable_call

        return cancellable_call(
            module_id,
            inputs,
            request=request,
            context=context,
            timeout=timeout,
        )

    async def cancellable_call_async(
        self,
        module_id: str,
        inputs: dict[str, Any] | None = None,
        *,
        request: Any = None,
        context: Any = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Execute a module asynchronously with cooperative cancellation."""
        from fastapi_apcore.engine.shortcuts import cancellable_call_async

        return await cancellable_call_async(
            module_id,
            inputs,
            request=request,
            context=context,
            timeout=timeout,
        )

    # ------------------------------------------------------------------
    # Module registration
    # ------------------------------------------------------------------

    def module(
        self,
        id: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
        version: str = "1.0.0",
        **kwargs: Any,
    ) -> Callable:
        """Decorator to register a function as an apcore module."""
        from apcore import module as apcore_module

        def decorator(func: Callable) -> Callable:
            inner = apcore_module(
                id=id,
                description=description,
                tags=tags,
                version=version,
                registry=self.registry,
                **kwargs,
            )
            return inner(func)

        return decorator

    def register(self, module_id: str, module_obj: Any) -> None:
        """Register a module object directly."""
        self.registry.register(module_id, module_obj)

    def list_modules(
        self,
        tags: list[str] | None = None,
        prefix: str | None = None,
    ) -> list[str]:
        """List registered module IDs, optionally filtered."""
        return self.registry.list(tags=tags, prefix=prefix)

    def describe(self, module_id: str) -> str:
        """Get a module's description."""
        return self.registry.describe(module_id)

    # ------------------------------------------------------------------
    # Task management
    # ------------------------------------------------------------------

    async def submit_task(
        self,
        module_id: str,
        inputs: dict[str, Any] | None = None,
        *,
        context: Any = None,
    ) -> str:
        """Submit an async task."""
        return await self.task_manager.submit(module_id, inputs or {}, context=context)

    def get_task_status(self, task_id: str) -> Any:
        """Query task status."""
        return self.task_manager.get_status(task_id)

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task."""
        return await self.task_manager.cancel(task_id)

    # ------------------------------------------------------------------
    # Scanning
    # ------------------------------------------------------------------

    def scan(
        self,
        app: FastAPI,
        source: str = "openapi",
        *,
        include: str | None = None,
        exclude: str | None = None,
    ) -> list[Any]:
        """Scan FastAPI endpoints and return ScannedModule instances."""
        from fastapi_apcore.scanners import get_scanner

        scanner = get_scanner(source)
        return scanner.scan(app, include=include, exclude=exclude)

    # ------------------------------------------------------------------
    # MCP serving
    # ------------------------------------------------------------------

    def serve(
        self,
        *,
        transport: str | None = None,
        host: str | None = None,
        port: int | None = None,
        name: str | None = None,
        explorer: bool | None = None,
        explorer_prefix: str | None = None,
        allow_execute: bool | None = None,
        **kwargs: Any,
    ) -> None:
        """Start an MCP server with registered modules."""
        try:
            from apcore_mcp import serve
        except ImportError:
            raise ImportError(
                "apcore-mcp is required for serve(). " "Install with: pip install fastapi-apcore[mcp]"
            ) from None

        s = self.settings
        serve(
            self.executor,
            transport=transport or s.serve_transport,
            host=host or s.serve_host,
            port=port if port is not None else s.serve_port,
            name=name or s.server_name,
            explorer=explorer if explorer is not None else s.explorer_enabled,
            explorer_prefix=(explorer_prefix if explorer_prefix is not None else s.explorer_prefix),
            allow_execute=(allow_execute if allow_execute is not None else s.explorer_allow_execute),
            **kwargs,
        )

    def to_openai_tools(
        self,
        *,
        tags: list[str] | None = None,
        prefix: str | None = None,
        embed_annotations: bool = False,
        strict: bool = False,
    ) -> list[dict[str, Any]]:
        """Export modules as OpenAI-compatible tool definitions."""
        try:
            from apcore_mcp import to_openai_tools
        except ImportError:
            raise ImportError(
                "apcore-mcp is required for to_openai_tools(). " "Install with: pip install fastapi-apcore[mcp]"
            ) from None

        return to_openai_tools(
            self.registry,
            tags=tags,
            prefix=prefix,
            embed_annotations=embed_annotations,
            strict=strict,
        )

    # ------------------------------------------------------------------
    # MCP helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def report_progress(
        context: Any,
        progress: float,
        total: float | None = None,
        message: str | None = None,
    ) -> None:
        """Report execution progress to an MCP client."""
        from fastapi_apcore.engine.shortcuts import report_progress

        await report_progress(context, progress, total=total, message=message)

    @staticmethod
    async def elicit(
        context: Any,
        message: str,
        requested_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Ask the MCP client for user input via elicitation."""
        from fastapi_apcore.engine.shortcuts import elicit

        return await elicit(context, message, requested_schema=requested_schema)

    # ------------------------------------------------------------------
    # Singleton access
    # ------------------------------------------------------------------

    @classmethod
    def get_instance(cls) -> FastAPIApcore:
        """Return the process-wide singleton FastAPIApcore instance."""
        global _instance
        if _instance is None:
            with _instance_lock:
                if _instance is None:
                    _instance = cls()
        return _instance

    @classmethod
    def _reset_instance(cls) -> None:
        """Reset the singleton. For testing only."""
        global _instance
        with _instance_lock:
            _instance = None
