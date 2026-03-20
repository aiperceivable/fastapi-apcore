# Changelog

All notable changes to this project will be documented in this file.

## [0.3.0] - 2026-03-20

### Added
- **`create_mcp_server()` method** -- standalone MCP server creation with two modes: full FastAPI route scan, or custom modules from an `extensions_dir`. Creates a fresh Registry/Executor (independent of the singleton), resolves serve defaults from settings, and supports `approval_handler` pass-through.
- **`create_cli()` method** -- generate an apcore-cli Click group from FastAPI routes. Scans routes, registers them as HTTP proxy modules via `HTTPProxyRegistryWriter`, and builds a Click group with `list`, `describe`, `completion`, and `man` subcommands. Supports `help_text_max_length` for configurable help text truncation.
- **`HTTPProxyRegistryWriter` re-export** -- available as a lazy import from `fastapi_apcore` via PEP 562 `__getattr__`. Does not break import when `apcore-toolkit` is not installed.
- **`get_writer("http-proxy")` format** -- `output.get_writer()` now supports `"http-proxy"` format, creating an `HTTPProxyRegistryWriter` with `base_url`, `auth_header_factory`, and `timeout` kwargs.
- **`simplify_ids` parameter on `init_app()` and `scan()`** -- consistent with `create_mcp_server()` and `create_cli()`, allowing simplified module IDs across all scanning entry points.
- **New apcore re-exports** -- `ExecutionCancelledError` and `ModuleDisabledError` from apcore 0.13.1.
- **10 new tests** -- covering `create_mcp_server` (ValueError guard, empty registry warning, scan+serve pipeline), `create_cli` (ImportError guard, Click group return), `scan(simplify_ids=)`, `get_writer("http-proxy")`, `get_writer` unknown format, lazy `__getattr__` import, and `__getattr__` error path.

### Fixed
- **`registry.watch(paths=...)` call in `init_app()`** -- removed invalid `paths` keyword argument. `Registry.watch()` takes no arguments; it watches the directories already configured via the constructor.
- **`create_mcp_server(scan=False)` silent misconfiguration** -- now logs a warning when called with `scan=False` and no `extensions_dir`, since the MCP server would have zero tools.
- **Top-level `HTTPProxyRegistryWriter` import** -- was an eager import that broke the entire package when `apcore-toolkit` lacked `http_proxy_writer`. Replaced with PEP 562 lazy `__getattr__`.

### Changed
- **Dependency versions bumped** -- `apcore>=0.13.1`, `apcore-toolkit>=0.3.0`, `apcore-cli>=0.2.1`.
- **`typer>=0.9` replaced with `click>=8.0`** in `[cli]` optional dependency -- apcore-cli uses click directly.
- **Package version bumped to 0.3.0**.

## [0.2.0] - 2026-03-18

### Added
- **`simplify_ids` option for `OpenAPIScanner`** -- when enabled, generates clean module IDs using only the function name instead of the full FastAPI operationId. For example, `product.get_product_product__product_id_.get` becomes `product.get_product.get`. Defaults to `False` for backward compatibility.
- **`_extract_func_name()` static method** -- reverses FastAPI's `generate_unique_id()` transformation to recover the original Python function name from an operationId. Handles path parameters, nested paths, and hyphens correctly.
- **`_strip_method_suffix()` static method** -- minimal default simplification that removes only the trailing `_{method}` from operationIds.
- **`get_scanner()` now accepts `**kwargs`** -- keyword arguments are forwarded to the scanner constructor, enabling `get_scanner("openapi", simplify_ids=True)`.
- **5 new tests** for `simplify_ids` behavior -- covers shortened IDs, function name extraction, no duplicates, default mode preserving path info, and factory kwarg passthrough.

### Changed
- `_generate_module_id()` refactored -- uses `_extract_func_name()` when `simplify_ids=True`, or `_strip_method_suffix()` when `False`. Extracted common prefix logic to reduce duplication.
- Module docstring in `openapi.py` updated to document both ID generation modes.

## [0.1.0] - 2026-03-18

### Added
- Initial release of `fastapi-apcore`.
- **`FastAPIApcore` unified entry point** -- single class consolidating Registry, Executor, ContextFactory, TaskManager, scanning, MCP serving, and OpenAI export. Thread-safe singleton via `get_instance()`.
- **`init_app(app)`** -- one-call initialization: auto-discovers YAML bindings, scans FastAPI routes, registers modules, enables hot-reload, and starts embedded MCP server.
- **`ApcoreSettings` configuration system** -- frozen dataclass with 40 settings, read from `APCORE_*` environment variables with full validation.
- **`FastAPIContextFactory`** -- maps FastAPI `Request` to apcore `Context` with `Identity` extraction from `request.state.user` (supports id/pk/sub fallback, roles/groups/scopes, W3C TraceContext).
- **Registry/Executor singleton management** -- thread-safe lazy singletons with double-checked locking for Registry, Executor, ExtensionManager, ContextFactory, MetricsCollector, and embedded MCP server.
- **Extension system** -- `FastAPIDiscoverer` (YAML bindings + module package scanning) and `FastAPIModuleValidator` (reserved words, length checks) implementing apcore protocols. `setup_extensions()` factory.
- **Observability auto-setup** -- `setup_observability()` creates TracingMiddleware, MetricsMiddleware, ObsLoggingMiddleware, ErrorHistoryMiddleware, UsageMiddleware, and PlatformNotifyMiddleware from settings.
- **Output writers** -- `FastAPIRegistryWriter` (direct registry registration with Pydantic flattening and schema-based FunctionModule creation) and `YAMLWriter` (YAML binding file generation).
- **Convenience shortcuts** -- `executor_call`, `executor_call_async`, `executor_stream`, `cancellable_call`, `cancellable_call_async`, `submit_task`, `get_task_status`, `cancel_task`, `report_progress`, `elicit`.
- **AsyncTaskManager integration** -- singleton task manager with configurable concurrency and cleanup.
- **Typer CLI** with four command groups:
  - `scan` -- scan FastAPI routes with `--source`, `--output`, `--include`, `--exclude`, `--ai-enhance`, `--verify`, `--dry-run`.
  - `serve` -- start MCP server with auto `init_app`, `--transport`, `--explorer`, `--jwt-secret`, `--approval`, `--tags`, `--output-formatter`.
  - `export` -- export modules as OpenAI-compatible tools with `--strict`, `--embed-annotations`.
  - `tasks` -- manage async tasks: `list`, `cancel`, `cleanup`.
- **Two scanner backends** -- `NativeFastAPIScanner` (direct route inspection) and `OpenAPIScanner` (OpenAPI spec-based).
- **Serialization helpers** -- `module_to_dict()` and `modules_to_dicts()` for ScannedModule conversion.
- **Complete `__init__.py` exports** -- `FastAPIApcore`, `ApcoreSettings`, `get_apcore_settings`, `FastAPIContextFactory`, scanners, and all apcore type re-exports.
- **PEP 561 `py.typed` marker** for type checker support.
- **Comprehensive test suite** -- 129 tests across 14 test files.
- **Project structure** -- public API (`__init__.py`, `client.py`, `cli.py`) at top level; internal engine files in `engine/` subdirectory; scanners in `scanners/`; output writers in `output/`.
