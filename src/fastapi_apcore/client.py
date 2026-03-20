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
        simplify_ids: bool = False,
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
            simplify_ids: Use simplified module IDs (function names only).
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

            scanned = self.scan(app, source=scan_source, simplify_ids=simplify_ids, include=include, exclude=exclude)
            if scanned:
                writer = get_writer(None)  # RegistryWriter
                writer.write(scanned, registry)
                logger.info("Scanned and registered %d FastAPI routes", len(scanned))

        # 3. Hot-reload
        if settings.hot_reload:
            try:
                registry.watch()
                logger.info("Hot-reload enabled")
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
        simplify_ids: bool = False,
        include: str | None = None,
        exclude: str | None = None,
    ) -> list[Any]:
        """Scan FastAPI endpoints and return ScannedModule instances."""
        from fastapi_apcore.scanners import get_scanner

        scanner = get_scanner(source, simplify_ids=simplify_ids)
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

    def create_mcp_server(
        self,
        app: FastAPI | None = None,
        *,
        extensions_dir: str | None = None,
        scan: bool = True,
        scan_source: str = "openapi",
        simplify_ids: bool = False,
        include: str | None = None,
        exclude: str | None = None,
        **serve_kwargs: Any,
    ) -> None:
        """Scan routes or discover modules, then start an MCP server.

        Supports two modes:

        **Full scan** (default): scan all FastAPI routes and expose as MCP tools::

            apcore.create_mcp_server(app, transport="streamable-http", port=9090)

        **Custom modules**: discover from a specific directory only::

            apcore.create_mcp_server(
                extensions_dir="./mcp/modules",
                scan=False,
                transport="streamable-http",
                port=9090,
                authenticator=my_authenticator,
            )

        Args:
            app: FastAPI application instance (required when ``scan=True``).
            extensions_dir: Directory containing hand-written apcore modules.
                When set, modules are auto-discovered from this directory.
            scan: Whether to scan FastAPI routes. Defaults to True.
                Set to False when using ``extensions_dir`` for custom modules.
            scan_source: Scanner backend ('openapi' or 'native').
            simplify_ids: Use simplified module IDs (function names only).
            include: Regex pattern — only include matching module IDs.
            exclude: Regex pattern — skip matching module IDs.
            **serve_kwargs: Passed directly to ``apcore_mcp.serve()``.
                Common options: ``transport``, ``host``, ``port``, ``name``,
                ``authenticator``, ``require_auth``, ``approval_handler``,
                ``explorer``, ``allow_execute``, ``output_formatter``.
        """
        try:
            from apcore_mcp import serve as mcp_serve
        except ImportError:
            raise ImportError(
                "apcore-mcp is required for create_mcp_server(). " "Install with: pip install fastapi-apcore[mcp]"
            ) from None

        from apcore import Executor, Registry

        registry = Registry(extensions_dir=extensions_dir) if extensions_dir else Registry()

        # Discover modules from extensions_dir
        if extensions_dir:
            count = registry.discover()
            logger.info("Discovered %d module(s) from %s", count, extensions_dir)

        # Scan FastAPI routes
        if scan:
            if app is None:
                raise ValueError("app is required when scan=True")
            from fastapi_apcore.output import get_writer
            from fastapi_apcore.scanners import get_scanner

            scanner = get_scanner(scan_source, simplify_ids=simplify_ids)
            scanned = scanner.scan(app, include=include, exclude=exclude)
            if scanned:
                writer = get_writer(None)  # FastAPIRegistryWriter
                writer.write(scanned, registry)
                logger.info("Scanned and registered %d routes as MCP tools", len(scanned))

        if not scan and not extensions_dir:
            logger.warning(
                "create_mcp_server called with scan=False and no extensions_dir — "
                "MCP server will have no tools registered"
            )

        # Resolve serve defaults from settings
        s = self.settings
        serve_defaults: dict[str, Any] = {
            "transport": s.serve_transport,
            "host": s.serve_host,
            "port": s.serve_port,
            "name": s.server_name,
            "explorer": s.explorer_enabled,
            "explorer_prefix": s.explorer_prefix,
            "allow_execute": s.explorer_allow_execute,
        }
        # User kwargs override defaults
        for key, default in serve_defaults.items():
            serve_kwargs.setdefault(key, default)

        approval_handler = serve_kwargs.pop("approval_handler", None)
        executor = (
            Executor(registry, approval_handler=approval_handler)
            if approval_handler is not None
            else Executor(registry)
        )

        logger.info(
            "Starting MCP server on %s:%s",
            serve_kwargs.get("host"),
            serve_kwargs.get("port"),
        )
        mcp_serve(executor, **serve_kwargs)

    # ------------------------------------------------------------------
    # CLI generation
    # ------------------------------------------------------------------

    def create_cli(
        self,
        app: FastAPI,
        *,
        prog_name: str = "apcore-cli",
        base_url: str = "http://localhost:8000",
        auth_header_factory: Callable[[], dict[str, str]] | None = None,
        timeout: float = 60.0,
        simplify_ids: bool = False,
        scan_source: str = "openapi",
        include: str | None = None,
        exclude: str | None = None,
        help_text_max_length: int = 1000,
        max_content_width: int | None = None,
    ) -> Any:
        """Create an apcore-cli Click group with all API routes as commands.

        Scans FastAPI routes, registers them as HTTP proxy modules, and
        returns a Click group ready to be invoked. Each CLI command
        forwards requests to the running REST API.

        Args:
            app: The FastAPI application instance.
            prog_name: CLI program name shown in help text.
            base_url: Base URL of the running API server.
            auth_header_factory: Optional callable returning auth headers
                (e.g. ``{"Authorization": "Bearer xxx"}``).
            timeout: HTTP request timeout in seconds.
            simplify_ids: Use simplified module IDs (function names only).
            scan_source: Scanner backend ('openapi' or 'native').
            include: Regex pattern — only include matching module IDs.
            exclude: Regex pattern — skip matching module IDs.
            help_text_max_length: Max characters for CLI help text per
                command. Defaults to 1000.
            max_content_width: Maximum width for CLI help output. When set,
                overrides Click's default (terminal width, max 80). Useful
                when command names are long and truncate descriptions.

        Returns:
            A Click Group that can be invoked with ``cli(standalone_mode=True)``.

        Example::

            from fastapi_apcore import FastAPIApcore
            from myapp.main import app

            apcore = FastAPIApcore()
            cli = apcore.create_cli(
                app,
                prog_name="myapp-cli",
                base_url="http://localhost:8000",
                simplify_ids=True,
            )
            cli(standalone_mode=True)
        """
        try:
            import click
            from apcore_cli.cli import LazyModuleGroup
            from apcore_cli.discovery import register_discovery_commands
            from apcore_cli.shell import register_shell_commands
        except ImportError:
            raise ImportError(
                "apcore-cli is required for create_cli(). " "Install with: pip install fastapi-apcore[cli]"
            ) from None

        from apcore import Executor, Registry
        from apcore_toolkit.output.http_proxy_writer import HTTPProxyRegistryWriter
        from fastapi_apcore.scanners import get_scanner

        # 1. Scan routes
        scanner = get_scanner(scan_source, simplify_ids=simplify_ids)
        modules = scanner.scan(app, include=include, exclude=exclude)
        logger.info("Scanned %d API routes", len(modules))

        # 2. Register as HTTP proxy modules
        registry = Registry()
        writer = HTTPProxyRegistryWriter(
            base_url=base_url,
            auth_header_factory=auth_header_factory,
            timeout=timeout,
        )
        results = writer.write(modules, registry)

        registered = sum(1 for r in results if r.verified)
        skipped = sum(1 for r in results if not r.verified)
        if skipped:
            logger.info("Registered %d modules (%d skipped)", registered, skipped)
        else:
            logger.info("Registered %d modules", registered)

        executor = Executor(registry)

        # 3. Build Click group
        ctx_settings: dict[str, Any] = {}
        if max_content_width is not None:
            ctx_settings["max_content_width"] = max_content_width

        # Compute the effective help width for the command list.
        # Click uses min(terminal_width, max_content_width), so when the
        # terminal is narrow, long command names push the description column
        # to zero and everything shows "...".  We override format_commands
        # to use the configured max_content_width directly.
        effective_width = max_content_width

        @click.group(
            cls=LazyModuleGroup,
            registry=registry,
            executor=executor,
            help_text_max_length=help_text_max_length,
            name=prog_name,
            help=f"{prog_name} — CLI for {app.title or 'FastAPI'} API.",
            context_settings=ctx_settings,
        )
        @click.version_option(
            version=app.version or "0.0.0",
            prog_name=prog_name,
        )
        @click.option(
            "--log-level",
            default=None,
            type=click.Choice(
                ["DEBUG", "INFO", "WARNING", "ERROR"],
                case_sensitive=False,
            ),
            help="Log verbosity.",
        )
        def cli(log_level: str | None = None) -> None:
            if log_level is not None:
                level = getattr(logging, log_level.upper(), logging.WARNING)
                logging.getLogger().setLevel(level)

        register_discovery_commands(cli, registry)
        register_shell_commands(cli, prog_name=prog_name)

        # Override format_commands to use effective_width so descriptions
        # are not truncated when the terminal is narrower than the content.
        if effective_width is not None:
            _original_format_commands = cli.format_commands

            def _wide_format_commands(ctx: Any, formatter: Any) -> None:
                original_width = formatter.width
                formatter.width = max(formatter.width, effective_width)
                _original_format_commands(ctx, formatter)
                formatter.width = original_width

            cli.format_commands = _wide_format_commands  # type: ignore[method-assign]

        return cli

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
