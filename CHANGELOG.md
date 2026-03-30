# Changelog

All notable changes to this project will be documented in this file.

## [0.4.0] - 2026-03-30

### Added

- **`docs_url` parameter on `create_cli()`** — base URL for online documentation (e.g. `"https://docs.example.com/cli"`). When set, the URL is embedded in man pages generated via `--help --man` and passed to `set_docs_url()` from apcore-cli so it appears in per-command help footers.
- **`verbose_help` parameter on `create_cli()`** — when `True`, built-in apcore options (`--input`, `--yes`, `--large-input`, `--format`) are shown in `--help` output. Defaults to `False` (hidden). Calls `set_verbose_help()` from apcore-cli 0.4.0; also pre-parses `sys.argv` so `--verbose` on the command line takes effect before Click renders `--help`.
- **`--verbose` flag on the generated CLI group** — runtime toggle for the verbose help behaviour. Equivalent to passing `verbose_help=True` to `create_cli()`, but can be used by end-users without changing application code.
- **Man page support via `configure_man_help()`** — after all commands are registered, `configure_man_help()` from apcore-cli 0.4.0 is called automatically. Users can run `mycli --help --man | man -` to view a full roff man page covering all registered commands.
- **`commands_dir` parameter on `create_cli()` and `create_mcp_server()`** — path to a directory of plain Python function files. When set, `ConventionScanner` from `apcore-toolkit` scans for public functions and registers them as additional modules alongside scanned API routes (§5.14).
- **`GroupedModuleGroup` in `create_cli()`** — CLI commands are now auto-grouped by namespace prefix (e.g., `myapp-cli product list` instead of `myapp-cli product.list`). Uses `GroupedModuleGroup` from `apcore-cli >= 0.3.0`.
- **`binding_path` parameter on `create_cli()` and `create_mcp_server()`** — wires `DisplayResolver` (§5.13) into the scan pipeline. Accepts a path to a single `.binding.yaml` file or a directory of `*.binding.yaml` files. When provided, `DisplayResolver().resolve(modules, binding_path=binding_path)` is called between scan and write, populating `metadata["display"]` on all scanned modules before they are registered.
  ```python
  cli = apcore.create_cli(app, binding_path="bindings/")
  mcp = apcore.create_mcp_server(app, binding_path="bindings/")
  ```
- **`DeprecationWarning` for `simplify_ids=True`** — emitted in `create_cli()` and `create_mcp_server()` when `simplify_ids=True`. Migrate to `binding_path` with `display.cli.alias` / `display.mcp.alias` in `binding.yaml` (§5.13).


### Changed

- Dependency floor raised: `apcore-cli >= 0.4.0` (for `set_verbose_help`, `set_docs_url`, `configure_man_help`).
- Dependency floor raised: `apcore-toolkit >= 0.4.1` (latest patch at time of release; 0.4.1 is already installed as a runtime dep of apcore-toolkit-python).
- Dependency bumps: `apcore-toolkit >= 0.4.0` (for `DisplayResolver`), `apcore-cli >= 0.3.0`, `apcore-mcp >= 0.11.0`.
- `create_cli()` now uses `GroupedModuleGroup` instead of `LazyModuleGroup` as the Click group class.

### Fixed

- **False-positive "no tools registered" warning** — `create_mcp_server(scan=False, commands_dir="./cmds/")` no longer emits a misleading warning when modules are provided via `commands_dir` only.
- **Convention scanner code duplication** — extracted `_apply_convention_modules()` helper shared by both `create_cli()` and `create_mcp_server()`.
- **Security docstring** — `commands_dir` docstrings now note that the path must be trusted and developer-controlled, as files are imported and executed during scanning.

### Tests

- `TestCreateCliApCoreCliFeatures` (10 tests): verifies `set_verbose_help` and `set_docs_url` are called with correct values (including `None` to clear stale state); confirms `sys.argv` pre-parse elevates `--verbose` before Click renders `--help`; confirms `--verbose` and `--man` options are present on the generated CLI group; integration check that the real `configure_man_help` mutates `cli.params`; `test_configure_man_help_receives_cli_group` verifies the CLI group is passed as the first positional argument. Tests use `monkeypatch` to isolate `sys.argv` so a pytest `--verbose` invocation does not bleed into assertions.
- `TestDisplayOverlayIntegration` (4 tests): `DisplayResolver` called when `binding_path` is set, skipped when not set, called in both `create_cli` and `create_mcp_server`, `DeprecationWarning` emitted for `simplify_ids=True`.
- `test_simplify_ids_emits_deprecation_warning`: verifies `DeprecationWarning` in `OpenAPIScanner.__init__`.
- `test_simplify_ids_sets_suggested_alias_in_metadata`: verifies scanner sets `metadata["suggested_alias"]` used by `DisplayResolver`.

---

## [0.3.1] - 2026-03-20

### Added
- **`max_content_width` parameter on `create_cli()`** -- overrides Click's default terminal-width-based help formatting. When the terminal is narrow, Click calculates description column width from the longest command name, often leaving zero space for descriptions (shown as `...`). This parameter forces a wider layout so descriptions are always visible.

### Improved
- **`simplify_ids` prefix optimization** -- when `simplify_ids=True`, module ID prefix now uses only the first path segment instead of all segments. This produces shorter, cleaner command names while maintaining uniqueness via function name differentiation and `deduplicate_ids()` safety net.
  - Before: `credit_purchase.purchase.status.get_purchase_status_by_payment_intent.get` (73 chars)
  - After: `credit_purchase.get_purchase_status_by_payment_intent.get` (57 chars)
- Default (`simplify_ids=False`) behavior unchanged -- all path segments preserved for backward compatibility.

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
