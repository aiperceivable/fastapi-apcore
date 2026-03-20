# fastapi-apcore

FastAPI integration for [apcore](https://github.com/aipartnerup/apcore-python) (AI-Perceivable Core). Expose your FastAPI routes as MCP tools with auto-discovery, Pydantic schema extraction, and built-in observability.

## Features

- **Route scanning** -- auto-discover FastAPI routes and convert them to apcore modules
- **Annotation inference** -- `GET` -> readonly+cacheable, `DELETE` -> destructive, `PUT` -> idempotent
- **Pydantic schema extraction** -- input/output schemas extracted from Pydantic models and OpenAPI spec
- **Two scanner backends** -- OpenAPI-based (accurate) and native route inspection (fast)
- **Simplified module IDs** -- `simplify_ids=True` extracts clean function names from FastAPI operationIds
- **`@module` decorator** -- define standalone AI-callable modules with full schema enforcement
- **YAML binding** -- zero-code module definitions via external `.binding.yaml` files
- **MCP server** -- stdio, streamable-http, and SSE transports via `fastapi-apcore serve`
- **Observability** -- distributed tracing, metrics, structured logging, error history, usage tracking
- **Input validation** -- validate tool inputs against Pydantic schemas before execution
- **CLI-first workflow** -- `fastapi-apcore scan` + `fastapi-apcore serve` for zero-intrusion integration
- **MCP Tool Explorer** -- browser UI for inspecting modules via `--explorer`
- **JWT authentication** -- protect MCP endpoints with Bearer tokens via `--jwt-secret`
- **Approval system** -- require approval for destructive operations via `--approval`
- **AI enhancement** -- enrich module metadata using local SLMs via `--ai-enhance`
- **Async tasks** -- background task submission, status tracking, and cancellation
- **Unified entry point** -- `FastAPIApcore` class provides property-based access to all components
- **CLI generation** -- `create_cli()` turns FastAPI routes into a Click CLI that proxies to the running API
- **HTTP proxy modules** -- `HTTPProxyRegistryWriter` registers scanned routes as HTTP-forwarding modules for CLI and remote execution

## Requirements

- Python >= 3.11
- FastAPI >= 0.100
- apcore >= 0.13.1
- apcore-toolkit >= 0.3.0

## Installation

```bash
# Core
pip install fastapi-apcore

# With MCP server support (required for serve/export)
pip install fastapi-apcore[mcp]

# With CLI
pip install fastapi-apcore[cli]

# Everything
pip install fastapi-apcore[all]
```

## Quick Start

### 1. Add FastAPIApcore to your app

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi_apcore import FastAPIApcore

apcore = FastAPIApcore()

@asynccontextmanager
async def lifespan(app: FastAPI):
    apcore.init_app(app)  # Auto-scan routes, discover modules, start MCP server
    yield

app = FastAPI(lifespan=lifespan)

@app.get("/greet/{name}")
def greet(name: str) -> dict:
    """Greet a user by name."""
    return {"message": f"Hello, {name}!"}
```

Or use the **factory pattern**:

```python
from fastapi import FastAPI
from fastapi_apcore import FastAPIApcore

apcore = FastAPIApcore()

def create_app() -> FastAPI:
    app = FastAPI()
    # ... add routers ...
    apcore.init_app(app)
    return app
```

### 2. Scan routes and start MCP server

```bash
# Scan FastAPI routes -> register as apcore modules -> start MCP server
fastapi-apcore serve myapp.main:app --transport streamable-http --port 9090 --explorer
```

That's it. Your FastAPI routes are now MCP tools.

### 3. Connect an MCP client

For **Claude Desktop**, add to your config:

```json
{
  "mcpServers": {
    "my-fastapi-app": {
      "command": "fastapi-apcore",
      "args": ["serve", "myapp.main:app"]
    }
  }
}
```

For **HTTP transport** (remote access):

```bash
fastapi-apcore serve myapp.main:app --transport streamable-http --host 0.0.0.0 --port 9090
```

## Integration Paths

fastapi-apcore supports three ways to define AI-perceivable modules:

### Route Scanning (zero-intrusion)

Scan existing FastAPI routes without modifying any code:

```bash
# Direct registration (in-memory)
fastapi-apcore scan myapp.main:app

# Generate YAML binding files (persistent)
fastapi-apcore scan myapp.main:app --output yaml --dir ./apcore_modules

# Preview without side effects
fastapi-apcore scan myapp.main:app --dry-run

# Filter routes by regex
fastapi-apcore scan myapp.main:app --include "users\." --exclude "\.delete$"
```

### `@module` Decorator

Define standalone modules with explicit schemas:

```python
from fastapi_apcore import FastAPIApcore

apcore = FastAPIApcore()

@apcore.module(id="math.add", tags=["math"], description="Add two numbers")
def add(a: int, b: int) -> int:
    return a + b
```

### YAML Binding (zero-code)

Define modules via external `.binding.yaml` files in `APCORE_MODULE_DIR`:

```yaml
bindings:
  - module_id: users.greet
    target: myapp.views:greet
    description: "Greet a user by name"
    tags: [users]
    input_schema:
      properties:
        name: { type: string }
      required: [name]
    output_schema:
      properties:
        message: { type: string }
```

## Unified Entry Point

The `FastAPIApcore` instance provides property-based access to all components:

```python
apcore = FastAPIApcore()

# Properties (lazy-loaded singletons)
apcore.registry           # apcore Registry
apcore.executor           # apcore Executor (with extensions)
apcore.settings           # ApcoreSettings
apcore.metrics_collector   # MetricsCollector | None
apcore.context_factory    # FastAPIContextFactory
apcore.task_manager       # AsyncTaskManager
apcore.extension_manager  # ExtensionManager

# Module execution
result = apcore.call("math.add", {"a": 1, "b": 2})
result = await apcore.call_async("math.add", {"a": 1, "b": 2}, request=request)

# Streaming
async for chunk in apcore.stream("ai.chat", {"prompt": "hello"}, request=request):
    ...

# With timeout/cancellation
result = apcore.cancellable_call("slow.task", timeout=30.0)

# Module introspection
apcore.list_modules(tags=["math"])
apcore.describe("math.add")

# Background tasks
task_id = await apcore.submit_task("batch.process", {"ids": [1, 2, 3]})
status = apcore.get_task_status(task_id)
await apcore.cancel_task(task_id)

# MCP serving
apcore.serve(transport="streamable-http", port=9090, explorer=True)
tools = apcore.to_openai_tools(strict=True)

# Standalone MCP server (fresh registry, scan + serve in one call)
apcore.create_mcp_server(app, transport="streamable-http", port=9090)

# CLI generation (routes become Click commands that proxy to the running API)
cli = apcore.create_cli(app, prog_name="myapp-cli", base_url="http://localhost:8000")
cli(standalone_mode=True)

# MCP helpers (inside module execution)
await FastAPIApcore.report_progress(context, progress=50, total=100)
response = await FastAPIApcore.elicit(context, "Please confirm")

# Singleton access
apcore = FastAPIApcore.get_instance()
```

## `init_app()` Reference

`init_app()` performs a complete initialization sequence:

```python
apcore.init_app(
    app,                    # FastAPI application instance
    scan=True,              # Auto-scan routes (default: True)
    scan_source="openapi",  # Scanner backend: "openapi" or "native"
    simplify_ids=False,     # Use simplified module IDs (function names only)
    include=None,           # Regex: only register matching module IDs
    exclude=None,           # Regex: skip matching module IDs
)
```

**What `init_app()` does (in order):**

1. **Auto-discover** modules from YAML bindings and `APCORE_MODULE_PACKAGES`
2. **Scan** FastAPI routes and register them as apcore modules
3. **Enable hot-reload** if `APCORE_HOT_RELOAD=true`
4. **Start embedded MCP server** if `APCORE_EMBEDDED_SERVER` is configured

## `create_mcp_server()` Reference

Create a standalone MCP server with a fresh registry (independent of the singleton):

```python
# Full scan mode -- scan all routes and serve as MCP tools
apcore.create_mcp_server(
    app,
    transport="streamable-http",
    port=9090,
    simplify_ids=True,
    explorer=True,
)

# Custom modules mode -- discover from a directory only
apcore.create_mcp_server(
    extensions_dir="./mcp/modules",
    scan=False,
    transport="streamable-http",
    port=9090,
)
```

## `create_cli()` Reference

Generate a Click CLI group that proxies to your running FastAPI server:

```python
from fastapi_apcore import FastAPIApcore
from myapp.main import app

apcore = FastAPIApcore()
cli = apcore.create_cli(
    app,
    prog_name="myapp-cli",
    base_url="http://localhost:8000",
    simplify_ids=True,
    help_text_max_length=500,
)

if __name__ == "__main__":
    cli(standalone_mode=True)
```

Each scanned route becomes a CLI command. The commands forward HTTP requests to the running API using `HTTPProxyRegistryWriter`. Built-in subcommands include `list`, `describe`, `completion`, and `man`.

## Configuration

All settings are read from environment variables with the `APCORE_` prefix:

### Core Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `APCORE_MODULE_DIR` | `apcore_modules/` | Directory for YAML binding files |
| `APCORE_AUTO_DISCOVER` | `true` | Auto-discover modules on startup |
| `APCORE_BINDING_PATTERN` | `*.binding.yaml` | Glob pattern for binding files |
| `APCORE_MODULE_PACKAGES` | — | Comma-separated packages to scan for `@module` |
| `APCORE_VALIDATE_INPUTS` | `false` | Validate inputs before module execution |

### MCP Server Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `APCORE_SERVE_TRANSPORT` | `stdio` | MCP transport: `stdio`, `streamable-http`, `sse` |
| `APCORE_SERVE_HOST` | `127.0.0.1` | Host for HTTP transport |
| `APCORE_SERVE_PORT` | `9090` | Port for HTTP transport |
| `APCORE_SERVER_NAME` | `apcore-mcp` | MCP server name |
| `APCORE_SERVER_VERSION` | — | MCP server version string |
| `APCORE_EXPLORER_ENABLED` | `false` | Enable MCP Tool Explorer UI |
| `APCORE_EXPLORER_PREFIX` | `/explorer` | URL prefix for Explorer |
| `APCORE_EXPLORER_ALLOW_EXECUTE` | `false` | Allow execution from Explorer |

### Authentication & Security

| Variable | Default | Description |
|----------|---------|-------------|
| `APCORE_JWT_SECRET` | — | JWT secret for MCP authentication |
| `APCORE_JWT_ALGORITHM` | `HS256` | JWT signing algorithm |
| `APCORE_JWT_AUDIENCE` | — | Expected JWT audience claim |
| `APCORE_JWT_ISSUER` | — | Expected JWT issuer claim |
| `APCORE_ACL_PATH` | — | Path to ACL YAML rules file |
| `APCORE_MIDDLEWARES` | — | Comma-separated middleware dotted paths |

### Observability

| Variable | Default | Description |
|----------|---------|-------------|
| `APCORE_TRACING` | — | Enable tracing: `true` or JSON config |
| `APCORE_METRICS` | — | Enable metrics: `true` or JSON config |
| `APCORE_OBSERVABILITY_LOGGING` | — | Enable structured logging: `true` or JSON config |

### Task Management

| Variable | Default | Description |
|----------|---------|-------------|
| `APCORE_TASK_MAX_CONCURRENT` | `10` | Max concurrent background tasks |
| `APCORE_TASK_MAX_TASKS` | `1000` | Max total tasks in queue |
| `APCORE_TASK_CLEANUP_AGE` | `3600` | Max age (seconds) for completed tasks |
| `APCORE_CANCEL_DEFAULT_TIMEOUT` | — | Default cancellation timeout (seconds) |

### Advanced

| Variable | Default | Description |
|----------|---------|-------------|
| `APCORE_EXECUTOR_CONFIG` | — | JSON string for Executor configuration |
| `APCORE_CONTEXT_FACTORY` | — | Dotted path to custom ContextFactory class |
| `APCORE_HOT_RELOAD` | `false` | Watch module files for changes |
| `APCORE_HOT_RELOAD_PATHS` | — | Comma-separated paths to watch |
| `APCORE_EMBEDDED_SERVER` | — | Auto-start MCP server on init: `true` or JSON config |
| `APCORE_OUTPUT_FORMATTER` | — | Dotted path to output formatter function |
| `APCORE_AI_ENHANCE` | `false` | Enable AI metadata enhancement |

See `fastapi_apcore.ApcoreSettings` for the full list of 40 settings.

## CLI Reference

### `scan` -- Scan FastAPI routes

```bash
fastapi-apcore scan myapp.main:app [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--source`, `-s` | Scanner backend: `openapi` (default) or `native` |
| `--output`, `-o` | Output format: `yaml`. Omit for direct registration |
| `--dir`, `-d` | Output directory (default: `APCORE_MODULE_DIR`) |
| `--dry-run` | Preview without writing files or registering |
| `--include` | Regex: only include matching module IDs |
| `--exclude` | Regex: exclude matching module IDs |
| `--ai-enhance` | AI-enhance module metadata |
| `--verify` | Verify written output |

### `serve` -- Start MCP server

```bash
fastapi-apcore serve myapp.main:app [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--transport`, `-t` | Transport: `stdio` (default), `streamable-http`, `sse` |
| `--host` | Host for HTTP transport (default: `127.0.0.1`) |
| `--port`, `-p` | Port for HTTP transport (default: `9090`) |
| `--name` | MCP server name |
| `--explorer` | Enable MCP Tool Explorer UI |
| `--jwt-secret` | JWT secret key for authentication |
| `--approval` | Approval mode: `off`, `elicit`, `auto-approve`, `always-deny` |
| `--tags` | Comma-separated module tag filter |
| `--prefix` | Module ID prefix filter |
| `--validate-inputs` | Validate inputs before execution |
| `--output-formatter` | Dotted path to output formatter function |
| `--log-level` | Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |

### `export` -- Export as OpenAI tools

```bash
fastapi-apcore export [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--format`, `-f` | Export format (default: `openai-tools`) |
| `--strict` | Add `strict: true` for Structured Outputs |
| `--embed-annotations` | Include annotation metadata in descriptions |
| `--tags` | Comma-separated module tag filter |
| `--prefix` | Module ID prefix filter |

### `tasks` -- Manage async tasks

```bash
fastapi-apcore tasks list [--status STATUS]
fastapi-apcore tasks cancel TASK_ID
fastapi-apcore tasks cleanup [--max-age SECONDS]
```

## Scanning

Two scanner backends are available:

| Backend | Method | Best for |
|---------|--------|----------|
| **OpenAPI** (default) | Uses FastAPI's auto-generated OpenAPI spec | Accuracy, handles all FastAPI features |
| **Native** | Directly inspects `app.routes` | Speed, no OpenAPI generation overhead |

```python
from fastapi_apcore import get_scanner

# OpenAPI scanner (default) -- full operationId-based IDs
scanner = get_scanner("openapi")
modules = scanner.scan(app)

# OpenAPI scanner with simplified IDs (recommended for CLI)
scanner = get_scanner("openapi", simplify_ids=True)
modules = scanner.scan(app)
# product.get_product_product__product_id_.get → product.get_product.get

# Native scanner
scanner = get_scanner("native")
modules = scanner.scan(app, include=r"users\.", exclude=r"\.delete$")
```

The `simplify_ids` option extracts the original Python function name from FastAPI's auto-generated operationId, producing much shorter and more readable module IDs. It defaults to `False` for backward compatibility.

Users only need to interact with two things:
- **`FastAPIApcore`** -- the unified entry point (import from `fastapi_apcore`)
- **CLI** -- `fastapi-apcore scan/serve/export/tasks`

Everything in `engine/` is internal wiring that `FastAPIApcore` manages automatically.

## Integration with apcore Ecosystem

fastapi-apcore bridges FastAPI to the apcore protocol:

```
FastAPI App -> FastAPIApcore -> apcore (Registry/Executor) -> apcore-mcp (MCP Server)
```

All apcore types are re-exported for convenience:

```python
from fastapi_apcore import (
    Registry, Executor, Context, Identity, Config,
    ACL, Middleware, ModuleAnnotations, FunctionModule,
    CancelToken, PreflightResult, ModuleError,
    ExecutionCancelledError, ModuleDisabledError,
    ApprovalHandler, AutoApproveHandler, AlwaysDenyHandler,
    EventEmitter, EventSubscriber, ApCoreEvent,
    HTTPProxyRegistryWriter,  # lazy import, requires apcore-toolkit
    module,  # @module decorator
)
```

## License

Apache-2.0
