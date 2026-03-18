"""FastAPI integration for the apcore AI-Perceivable Core ecosystem.

Exposes FastAPI routes as apcore modules via automatic scanning,
with full execution, context mapping, and MCP serving support.
"""

from __future__ import annotations

try:
    from importlib.metadata import version as _get_version

    __version__ = _get_version("fastapi-apcore")
except Exception:
    __version__ = "unknown"

from fastapi_apcore.client import FastAPIApcore
from fastapi_apcore.engine.config import ApcoreSettings, get_apcore_settings
from fastapi_apcore.engine.context import FastAPIContextFactory
from fastapi_apcore.scanners import get_scanner
from fastapi_apcore.scanners.base import BaseScanner, ScannedModule

# Re-export apcore core types for convenience
from apcore import (
    ACL,
    Config,
    Context,
    Executor,
    Identity,
    Middleware,
    Registry,
    ModuleAnnotations,
    FunctionModule,
    ModuleExample,
    ApprovalHandler,
    AutoApproveHandler,
    AlwaysDenyHandler,
    EventEmitter,
    EventSubscriber,
    ApCoreEvent,
    CancelToken,
    PreflightResult,
    ModuleError,
    ModuleNotFoundError,
    ACLDeniedError,
    SchemaValidationError,
    InvalidInputError,
)

# Convenience re-exports
from apcore import module  # noqa: F401 — @module decorator

__all__ = [
    # Main entry point
    "FastAPIApcore",
    # Configuration
    "ApcoreSettings",
    "get_apcore_settings",
    # Context
    "FastAPIContextFactory",
    # Scanners
    "BaseScanner",
    "ScannedModule",
    "get_scanner",
    # apcore re-exports
    "ACL",
    "Config",
    "Context",
    "Executor",
    "Identity",
    "Middleware",
    "Registry",
    "ModuleAnnotations",
    "FunctionModule",
    "ModuleExample",
    "ApprovalHandler",
    "AutoApproveHandler",
    "AlwaysDenyHandler",
    "EventEmitter",
    "EventSubscriber",
    "ApCoreEvent",
    "CancelToken",
    "PreflightResult",
    "ModuleError",
    "ModuleNotFoundError",
    "ACLDeniedError",
    "SchemaValidationError",
    "InvalidInputError",
    "module",
]
