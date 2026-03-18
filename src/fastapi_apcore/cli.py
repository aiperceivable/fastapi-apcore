"""Typer CLI commands for fastapi-apcore.

Provides 'fastapi-apcore' command group with 'scan', 'serve', and 'export' subcommands.
"""

from __future__ import annotations

import importlib
import re
from typing import Any

import typer


def create_cli() -> Any:
    """Create the Typer CLI application."""
    cli = typer.Typer(name="fastapi-apcore", help="apcore AI-Perceivable Core CLI for FastAPI.")

    @cli.command()
    def scan(
        app_path: str = typer.Argument(..., help="Dotted path to FastAPI app (e.g., 'myapp.main:app')."),
        source: str = typer.Option("openapi", "--source", "-s", help="Scanner source: native or openapi."),
        output: str = typer.Option(None, "--output", "-o", help="Output format: yaml. Omit for direct registration."),
        output_dir: str = typer.Option(None, "--dir", "-d", help="Output directory."),
        dry_run: bool = typer.Option(False, "--dry-run", help="Preview without writing."),
        include: str = typer.Option(None, "--include", help="Regex: only include matching module IDs."),
        exclude: str = typer.Option(None, "--exclude", help="Regex: exclude matching module IDs."),
        ai_enhance: bool = typer.Option(False, "--ai-enhance", help="AI-enhance module metadata."),
        verify: bool = typer.Option(False, "--verify", help="Verify written output."),
    ) -> None:
        """Scan FastAPI routes and generate apcore module definitions."""
        app = _load_app(app_path)

        from fastapi_apcore.engine.config import get_apcore_settings

        settings = get_apcore_settings()

        if output_dir is None:
            output_dir = settings.module_dir

        # Validate regex patterns
        if include:
            try:
                re.compile(include)
            except re.error as e:
                typer.echo(f"Error: Invalid --include pattern: {e}", err=True)
                raise typer.Exit(code=1)
        if exclude:
            try:
                re.compile(exclude)
            except re.error as e:
                typer.echo(f"Error: Invalid --exclude pattern: {e}", err=True)
                raise typer.Exit(code=1)

        from fastapi_apcore.scanners import get_scanner

        try:
            scanner = get_scanner(source)
        except ValueError as e:
            typer.echo(f"Error: {e}", err=True)
            raise typer.Exit(code=1)

        typer.echo(f"[fastapi-apcore] Scanning {scanner.get_source_name()} routes...")
        modules = scanner.scan(app, include=include, exclude=exclude)
        typer.echo(f"[fastapi-apcore] Found {len(modules)} API routes.")

        if not modules:
            typer.echo(f"[fastapi-apcore] No routes found for source '{source}'.")
            raise typer.Exit(code=1)

        # AI Enhancement
        if ai_enhance or settings.ai_enhance:
            try:
                from apcore_toolkit import AIEnhancer

                if AIEnhancer.is_enabled():
                    enhancer = AIEnhancer()
                    typer.echo("[fastapi-apcore] Running AI enhancement...")
                    modules = enhancer.enhance(modules)
                else:
                    typer.echo("[fastapi-apcore] AI enhancement skipped (not enabled).")
            except ImportError:
                typer.echo("[fastapi-apcore] AI enhancement not available.")

        # Report warnings
        all_warnings = []
        for module in modules:
            all_warnings.extend(module.warnings)
        if all_warnings:
            typer.echo(f"[fastapi-apcore] Warnings: {len(all_warnings)}")
            for warning in all_warnings:
                typer.echo(f"[fastapi-apcore]   - {warning}")

        # Get writer and write output
        from fastapi_apcore.output import get_writer
        from fastapi_apcore.engine.registry import get_registry

        writer = get_writer(output)

        if output is None:
            registry = get_registry()
            if dry_run:
                typer.echo("[fastapi-apcore] Dry run -- no modules registered.")
                writer.write(modules, registry, dry_run=True)
            else:
                results = writer.write(modules, registry, verify=verify)
                typer.echo(f"[fastapi-apcore] Registered {len(results)} modules.")
        else:
            if dry_run:
                typer.echo("[fastapi-apcore] Dry run -- no files written.")
                writer.write(modules, output_dir, dry_run=True)
            else:
                results = writer.write(modules, output_dir)
                typer.echo(f"[fastapi-apcore] Generated {len(results)} module definitions.")
                typer.echo(f"[fastapi-apcore] Written to {output_dir}/")

    @cli.command()
    def serve(
        app_path: str = typer.Argument(..., help="Dotted path to FastAPI app (e.g., 'myapp.main:app')."),
        transport: str = typer.Option("stdio", "--transport", "-t", help="Transport: stdio, streamable-http, sse."),
        host: str = typer.Option(None, "--host", help="Host for HTTP transport."),
        port: int = typer.Option(None, "--port", "-p", help="Port for HTTP transport."),
        name: str = typer.Option(None, "--name", help="MCP server name."),
        explorer: bool = typer.Option(False, "--explorer", help="Enable MCP Tool Explorer UI."),
        explorer_prefix: str = typer.Option(None, "--explorer-prefix", help="Explorer URL prefix."),
        allow_execute: bool = typer.Option(False, "--allow-execute", help="Allow execution from explorer."),
        validate_inputs: bool = typer.Option(False, "--validate-inputs", help="Validate inputs before execution."),
        jwt_secret: str = typer.Option(None, "--jwt-secret", help="JWT secret key."),
        jwt_algorithm: str = typer.Option(None, "--jwt-algorithm", help="JWT algorithm."),
        jwt_audience: str = typer.Option(None, "--jwt-audience", help="JWT audience."),
        jwt_issuer: str = typer.Option(None, "--jwt-issuer", help="JWT issuer."),
        approval: str = typer.Option(
            "off", "--approval", help="Approval mode: off, elicit, auto-approve, always-deny."
        ),
        output_formatter: str = typer.Option(None, "--output-formatter", help="Dotted path to output formatter."),
        tags: str = typer.Option(None, "--tags", help="Comma-separated tags filter."),
        prefix: str = typer.Option(None, "--prefix", help="Module ID prefix filter."),
        log_level: str = typer.Option(None, "--log-level", help="Log level: DEBUG, INFO, WARNING, ERROR."),
    ) -> None:
        """Start an MCP server exposing registered apcore modules as tools."""
        app = _load_app(app_path)

        # Auto-scan and register routes before serving
        from fastapi_apcore.client import FastAPIApcore

        apcore = FastAPIApcore.get_instance()
        apcore.init_app(app)

        from fastapi_apcore.engine.config import get_apcore_settings
        from fastapi_apcore.engine.registry import get_executor, get_registry, get_metrics_collector

        settings = get_apcore_settings()

        # Resolve with config fallbacks
        transport = transport or settings.serve_transport
        host = host or settings.serve_host
        port = port if port is not None else settings.serve_port
        name = name or settings.server_name

        if not validate_inputs:
            validate_inputs = settings.serve_validate_inputs
        if log_level is None:
            log_level = settings.serve_log_level
        if not explorer:
            explorer = settings.explorer_enabled
        if explorer_prefix is None:
            explorer_prefix = settings.explorer_prefix
        if not allow_execute:
            allow_execute = settings.explorer_allow_execute

        # JWT fallbacks
        if jwt_secret is None:
            jwt_secret = settings.jwt_secret
        if jwt_algorithm is None:
            jwt_algorithm = settings.jwt_algorithm
        if jwt_audience is None:
            jwt_audience = settings.jwt_audience
        if jwt_issuer is None:
            jwt_issuer = settings.jwt_issuer

        # Tags/prefix
        tags_list = _parse_tags(tags)
        if tags_list is None and settings.serve_tags is not None:
            tags_list = settings.serve_tags
        if prefix is None:
            prefix = settings.serve_prefix

        # Build authenticator
        authenticator = None
        if jwt_secret is not None:
            try:
                from apcore_mcp import JWTAuthenticator

                authenticator = JWTAuthenticator(
                    jwt_secret,
                    algorithms=[jwt_algorithm],
                    audience=jwt_audience,
                    issuer=jwt_issuer,
                )
            except ImportError:
                typer.echo("Error: apcore-mcp >= 0.10.0 required for JWT.", err=True)
                raise typer.Exit(code=1)

        # Build approval handler
        approval_handler = _resolve_approval_handler(approval)

        # Resolve output formatter
        formatter_func = _resolve_output_formatter(output_formatter)

        # Check modules
        registry = get_registry()
        if registry.count == 0:
            typer.echo("Error: No apcore modules registered. Run 'scan' first.", err=True)
            raise typer.Exit(code=1)

        # Detect executor vs registry
        use_executor = bool(settings.middlewares or settings.acl_path or settings.executor_config)
        registry_or_executor = get_executor() if use_executor else registry

        typer.echo(f"[fastapi-apcore] Starting MCP server '{name}' via {transport}...")
        typer.echo(f"[fastapi-apcore] {registry.count} modules registered.")

        try:
            from apcore_mcp import serve as mcp_serve
        except ImportError:
            typer.echo("Error: apcore-mcp is required. Install with: pip install fastapi-apcore[mcp]", err=True)
            raise typer.Exit(code=1)

        kwargs: dict[str, Any] = dict(
            transport=transport,
            host=host,
            port=port,
            name=name,
            version=settings.server_version,
            validate_inputs=validate_inputs,
            log_level=log_level,
            metrics_collector=get_metrics_collector(),
        )
        if explorer:
            kwargs["explorer"] = explorer
            kwargs["explorer_prefix"] = explorer_prefix
            kwargs["allow_execute"] = allow_execute
        if authenticator is not None:
            kwargs["authenticator"] = authenticator
        if approval_handler is not None:
            kwargs["approval_handler"] = approval_handler
        if formatter_func is not None:
            kwargs["output_formatter"] = formatter_func
        if tags_list is not None:
            kwargs["tags"] = tags_list
        if prefix is not None:
            kwargs["prefix"] = prefix

        mcp_serve(registry_or_executor, **kwargs)

    @cli.command("export")
    def export_cmd(
        output_format: str = typer.Option("openai-tools", "--format", "-f", help="Export format."),
        strict: bool = typer.Option(False, "--strict", help="Add strict: true for Structured Outputs."),
        embed_annotations: bool = typer.Option(False, "--embed-annotations", help="Include annotation metadata."),
        tags: str = typer.Option(None, "--tags", help="Comma-separated tags filter."),
        prefix: str = typer.Option(None, "--prefix", help="Module ID prefix filter."),
    ) -> None:
        """Export registered modules to OpenAI-compatible tool format."""
        if output_format != "openai-tools":
            typer.echo(f"Error: Unsupported format '{output_format}'. Only 'openai-tools' is supported.", err=True)
            raise typer.Exit(code=1)

        import json
        from fastapi_apcore.engine.registry import get_registry

        try:
            from apcore_mcp import to_openai_tools
        except ImportError:
            typer.echo("Error: apcore-mcp is required. Install with: pip install fastapi-apcore[mcp]", err=True)
            raise typer.Exit(code=1)

        registry = get_registry()
        tags_list = _parse_tags(tags)

        tools = to_openai_tools(
            registry,
            tags=tags_list,
            prefix=prefix,
            embed_annotations=embed_annotations,
            strict=strict,
        )
        typer.echo(json.dumps(tools, indent=2))

    # -- tasks subcommand group ------------------------------------------------

    tasks_app = typer.Typer(name="tasks", help="Manage apcore async tasks.")
    cli.add_typer(tasks_app)

    @tasks_app.command("list")
    def tasks_list(
        status: str = typer.Option(
            None, "--status", help="Filter by status: pending, running, completed, failed, cancelled."
        ),
    ) -> None:
        """List async tasks."""
        from fastapi_apcore.engine.tasks import get_task_manager

        tm = get_task_manager()
        status_filter = None
        if status is not None:
            try:
                from apcore import TaskStatus

                status_filter = TaskStatus[status.upper()]
            except (ImportError, KeyError):
                status_filter = status

        tasks = tm.list_tasks(status=status_filter)
        if not tasks:
            typer.echo("No tasks found.")
            return
        for task in tasks:
            typer.echo(f"  {task.task_id}  {task.module_id}  {task.status.value}")

    @tasks_app.command("cancel")
    def tasks_cancel(
        task_id: str = typer.Argument(..., help="Task ID to cancel."),
    ) -> None:
        """Cancel a running async task."""
        import asyncio

        from fastapi_apcore.engine.tasks import get_task_manager

        tm = get_task_manager()
        result = asyncio.run(tm.cancel(task_id))
        if result:
            typer.echo(f"Task {task_id} cancelled.")
        else:
            typer.echo(f"Task {task_id} could not be cancelled.")

    @tasks_app.command("cleanup")
    def tasks_cleanup(
        max_age: int = typer.Option(None, "--max-age", help="Max age in seconds for completed tasks."),
    ) -> None:
        """Clean up old completed tasks."""
        from fastapi_apcore.engine.config import get_apcore_settings
        from fastapi_apcore.engine.tasks import get_task_manager

        if max_age is None:
            max_age = get_apcore_settings().task_cleanup_age

        tm = get_task_manager()
        count = tm.cleanup(max_age_seconds=max_age)
        typer.echo(f"Cleaned up {count} tasks.")

    return cli


def _parse_tags(tags: str | None) -> list[str] | None:
    """Parse a comma-separated tags string into a list."""
    if tags is None:
        return None
    return [t.strip() for t in tags.split(",") if t.strip()] or None


def _load_app(app_path: str) -> Any:
    """Load a FastAPI app from a dotted path like 'myapp.main:app'."""

    if ":" not in app_path:
        typer.echo(f"Error: app_path must be 'module:attribute' format. Got: '{app_path}'", err=True)
        raise typer.Exit(code=1)

    module_path, attr_name = app_path.rsplit(":", 1)
    try:
        mod = importlib.import_module(module_path)
    except ImportError as e:
        typer.echo(f"Error: Cannot import '{module_path}': {e}", err=True)
        raise typer.Exit(code=1)

    app = getattr(mod, attr_name, None)
    if app is None:
        typer.echo(f"Error: '{attr_name}' not found in '{module_path}'.", err=True)
        raise typer.Exit(code=1)

    return app


def _resolve_approval_handler(mode: str) -> Any:
    """Resolve an approval mode string to an ApprovalHandler instance."""

    if mode == "off":
        return None
    if mode == "elicit":
        try:
            from apcore_mcp import ElicitationApprovalHandler

            return ElicitationApprovalHandler()
        except ImportError:
            typer.echo(f"Error: apcore-mcp >= 0.10.0 required for approval '{mode}'.", err=True)
            raise typer.Exit(code=1)
    if mode == "auto-approve":
        from apcore import AutoApproveHandler

        return AutoApproveHandler()
    if mode == "always-deny":
        from apcore import AlwaysDenyHandler

        return AlwaysDenyHandler()
    typer.echo(f"Error: Unknown approval mode: '{mode}'.", err=True)
    raise typer.Exit(code=1)


def _resolve_output_formatter(path: str | None) -> Any:
    """Resolve a dotted path to an output formatter callable."""

    if path is None:
        return None
    module_path, _, attr_name = path.rpartition(".")
    if not module_path:
        typer.echo(f"Error: Invalid formatter path: '{path}'.", err=True)
        raise typer.Exit(code=1)
    try:
        mod = importlib.import_module(module_path)
        return getattr(mod, attr_name)
    except (ImportError, AttributeError) as e:
        typer.echo(f"Error: Cannot resolve formatter '{path}': {e}", err=True)
        raise typer.Exit(code=1)


def main() -> None:
    """Entry point for the CLI."""
    cli = create_cli()
    cli()


if __name__ == "__main__":
    main()
