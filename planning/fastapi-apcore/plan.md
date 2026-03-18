# fastapi-apcore Full Implementation Plan

## Overview

Complete fastapi-apcore to feature parity with flask-apcore and django-apcore.
Current state: Scanner layer only (~637 LOC, 4 files).
Target state: Full integration with config, context, registry, execution, CLI, MCP, observability, extensions, tasks.

## Architecture

```
FastAPI App
    ↓
FastAPIApcore (unified entry point)
    ├─ ApcoreSettings (env-based config)
    ├─ FastAPIContextFactory (Request → Identity + TraceContext)
    ├─ Scanners (native, openapi) [EXISTING]
    ├─ Output Writers (registry, yaml)
    ├─ Extensions (FastAPIDiscoverer, FastAPIModuleValidator)
    ├─ Observability (auto-setup tracing/metrics/logging)
    ├─ CLI (Typer: scan, serve, export)
    └─ Shortcuts (convenience functions)
    ↓
apcore Core (Registry, Executor, Context, ACL, Middleware)
    ↓
apcore-mcp (MCP Server, OpenAI export)
```

## Tasks

### Task 001: ApcoreSettings — Configuration System
- **File**: `src/fastapi_apcore/config.py`
- **Pattern**: Frozen dataclass with env var resolution (APCORE_ prefix)
- **Reference**: django-apcore/settings.py, flask-apcore/config.py
- **Details**: ~30 settings, validation, defaults. Unlike Django/Flask which read from framework config, FastAPI reads from os.environ with APCORE_ prefix or from app.state if available.
- **TDD**: Test defaults, env override, validation errors, type checking

### Task 002: FastAPIContextFactory — Context Mapping
- **File**: `src/fastapi_apcore/context.py`
- **Pattern**: Maps FastAPI Request → apcore Context + Identity
- **Reference**: django-apcore/context.py, flask-apcore/context.py
- **Details**: Extract user from request.state.user (common FastAPI pattern). W3C traceparent header extraction. Anonymous fallback.
- **TDD**: Test authenticated user, anonymous, traceparent, missing attrs

### Task 003: Registry/Executor Singleton Management
- **File**: `src/fastapi_apcore/registry.py`
- **Pattern**: Thread-safe lazy singletons with locks
- **Reference**: django-apcore/registry.py
- **Details**: get_registry(), get_executor(), get_extension_manager(), get_context_factory(), get_metrics_collector(), _reset_* for testing
- **TDD**: Test lazy creation, thread safety, reset functions

### Task 004: Extension System
- **File**: `src/fastapi_apcore/extensions.py`
- **Pattern**: Implements apcore Discoverer + ModuleValidator protocols
- **Reference**: django-apcore/extensions.py
- **Details**: FastAPIDiscoverer (YAML bindings + module scanning), FastAPIModuleValidator (reserved words, length), setup_extensions() factory
- **TDD**: Test discovery from yaml dir, module validation, extension wiring

### Task 005: Observability Auto-Setup
- **File**: `src/fastapi_apcore/observability.py`
- **Pattern**: Factory function creating middleware from settings
- **Reference**: flask-apcore/observability.py
- **Details**: setup_observability(settings) → middlewares list. Tracing (stdout/memory/otlp), Metrics, Logging, ErrorHistory, Usage, PlatformNotify
- **TDD**: Test each middleware type creation, disabled state

### Task 006: Output Writers
- **Files**: `src/fastapi_apcore/output/__init__.py`, `registry_writer.py`, `yaml_writer.py`
- **Pattern**: Convert ScannedModule → Registry or YAML
- **Reference**: django-apcore/output/registry_writer.py, yaml_writer.py
- **Details**: FastAPIRegistryWriter extends toolkit RegistryWriter. Handles FastAPI endpoint functions (no request param stripping needed unlike Django). YAMLWriter re-exports toolkit.
- **TDD**: Test registration, dry-run, verify, yaml generation

### Task 007: Shortcuts — Convenience Functions
- **File**: `src/fastapi_apcore/shortcuts.py`
- **Pattern**: Module-level functions wrapping singleton access
- **Reference**: django-apcore/shortcuts.py
- **Details**: executor_call, executor_call_async, executor_stream, cancellable_call, cancellable_call_async, submit_task, get_task_status, cancel_task, report_progress, elicit
- **TDD**: Test each shortcut delegates correctly

### Task 008: Task Management
- **File**: `src/fastapi_apcore/tasks.py`
- **Pattern**: AsyncTaskManager singleton wrapper
- **Reference**: django-apcore/tasks.py
- **Details**: get_task_manager() singleton, configured from settings (max_concurrent, max_tasks)
- **TDD**: Test singleton creation, config from settings

### Task 009: FastAPIApcore — Unified Entry Point
- **File**: `src/fastapi_apcore/client.py`
- **Pattern**: Single class consolidating all functionality
- **Reference**: django-apcore/client.py
- **Details**: Properties for lazy singletons. Methods: init_app(), call(), call_async(), stream(), cancellable_call(), module(), register(), list_modules(), describe(), scan(), serve(), to_openai_tools(), submit_task(), report_progress(), elicit(). Singleton via get_instance(). init_app() uses FastAPI lifespan.
- **TDD**: Test all methods delegate correctly, singleton pattern

### Task 010: CLI Commands (Typer)
- **File**: `src/fastapi_apcore/cli.py`
- **Pattern**: Typer CLI with scan, serve, export commands
- **Reference**: flask-apcore/cli.py, django-apcore/management/commands/
- **Details**: Uses Typer (FastAPI ecosystem). scan: --source, --output, --dir, --dry-run, --include, --exclude, --verify, --ai-enhance. serve: --transport, --host, --port, --explorer, --jwt-secret, --tags, --prefix, --approval. export: --format, --strict, --tags. Entry point in pyproject.toml.
- **TDD**: Test command invocation, option parsing, error cases

### Task 011: Serializers
- **File**: `src/fastapi_apcore/serializers.py`
- **Pattern**: ScannedModule → dict conversion
- **Reference**: flask-apcore/serializers.py
- **Details**: module_to_dict(), modules_to_dicts(). Re-export annotations_to_dict from toolkit.
- **TDD**: Test serialization roundtrip

### Task 012: Complete __init__.py Exports
- **File**: `src/fastapi_apcore/__init__.py`
- **Pattern**: Comprehensive public API
- **Reference**: django-apcore/__init__.py, flask-apcore/__init__.py
- **Details**: Export FastAPIApcore, all apcore re-exports, settings, context, shortcuts, writers
- **TDD**: Test all exports exist and are correct types

### Task 013: pyproject.toml Updates
- **File**: `pyproject.toml`
- **Details**: Add typer dependency, cli entry point, bump version to 0.2.0
- **TDD**: Verify entry point resolves

### Task 014: Integration Tests
- **Files**: `tests/test_config.py`, `test_context.py`, `test_registry.py`, `test_extensions.py`, `test_writers.py`, `test_cli.py`, `test_client.py`, `test_shortcuts.py`, `test_tasks.py`, `test_observability.py`, `test_serializers.py`, `test_public_api.py`, `test_integration.py`
- **Details**: Comprehensive test suite matching django-apcore coverage
- **TDD**: Each task includes its own tests; this task adds integration/e2e tests

## Execution Order

```
001 (config) → 002 (context) → 003 (registry) → 004 (extensions)
    → 005 (observability) → 006 (writers) → 007 (shortcuts)
    → 008 (tasks) → 009 (client) → 010 (cli) → 011 (serializers)
    → 012 (exports) → 013 (pyproject) → 014 (integration tests)
```

## Critical Files

| File | Purpose |
|------|---------|
| `src/fastapi_apcore/config.py` | Settings resolution from env |
| `src/fastapi_apcore/context.py` | Request → Identity mapping |
| `src/fastapi_apcore/registry.py` | Singleton management |
| `src/fastapi_apcore/extensions.py` | Discovery + validation |
| `src/fastapi_apcore/observability.py` | Auto-setup middleware |
| `src/fastapi_apcore/output/` | Writers (registry, yaml) |
| `src/fastapi_apcore/shortcuts.py` | Convenience functions |
| `src/fastapi_apcore/tasks.py` | Task management |
| `src/fastapi_apcore/client.py` | Unified entry point |
| `src/fastapi_apcore/cli.py` | CLI commands |
| `src/fastapi_apcore/serializers.py` | Serialization |
| `src/fastapi_apcore/__init__.py` | Public API |
