"""Base scanner interface and ScannedModule dataclass for FastAPI.

All scanners (NativeFastAPIScanner, OpenAPIScanner) extend BaseScanner
and produce lists of ScannedModule instances.

ScannedModule keeps FastAPI-specific fields (http_method, url_path) as
top-level attributes. The toolkit's domain-agnostic ScannedModule stores
these in metadata instead.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any

from apcore import ModuleAnnotations
from apcore_toolkit import BaseScanner as _ToolkitBaseScanner

if TYPE_CHECKING:
    from fastapi import FastAPI


@dataclass
class ScannedModule:
    """Result of scanning a single FastAPI endpoint.

    Attributes:
        module_id: Unique module identifier (e.g., 'task.create_task.post').
        description: Human-readable description for tool listing.
        input_schema: JSON Schema dict for module input.
        output_schema: JSON Schema dict for module output.
        tags: Categorization tags (derived from FastAPI router tags).
        target: Callable reference in 'module.path:callable' format.
        http_method: HTTP method (GET, POST, PUT, DELETE).
        url_path: The FastAPI URL path string (e.g., '/task/create').
        version: Module version string.
        annotations: Behavioral annotations inferred from HTTP method.
        documentation: Full docstring text for rich descriptions.
        metadata: Arbitrary key-value data (e.g., scanner source info).
        warnings: Non-fatal issues encountered during scanning.
    """

    module_id: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    tags: list[str]
    target: str
    http_method: str
    url_path: str
    version: str = "1.0.0"
    annotations: ModuleAnnotations | None = None
    documentation: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


class BaseScanner(ABC):
    """Abstract base class for all FastAPI scanners.

    Subclasses must implement scan() and get_source_name().
    """

    @abstractmethod
    def scan(
        self,
        app: FastAPI,
        include: str | None = None,
        exclude: str | None = None,
    ) -> list[ScannedModule]:
        """Scan FastAPI app endpoints and return module definitions."""
        ...

    @abstractmethod
    def get_source_name(self) -> str:
        """Return human-readable scanner name."""
        ...

    def filter_modules(
        self,
        modules: list[ScannedModule],
        include: str | None = None,
        exclude: str | None = None,
    ) -> list[ScannedModule]:
        """Apply include/exclude regex filters to scanned modules."""
        result = modules
        if include is not None:
            pattern = re.compile(include)
            result = [m for m in result if pattern.search(m.module_id)]
        if exclude is not None:
            pattern = re.compile(exclude)
            result = [m for m in result if not pattern.search(m.module_id)]
        return result

    @staticmethod
    def infer_annotations_from_method(method: str) -> ModuleAnnotations:
        """Infer behavioral annotations from an HTTP method."""
        return _ToolkitBaseScanner.infer_annotations_from_method(method)

    def deduplicate_ids(self, modules: list[ScannedModule]) -> list[ScannedModule]:
        """Resolve duplicate module IDs by appending _2, _3, etc."""
        seen: dict[str, int] = {}
        result: list[ScannedModule] = []
        for module in modules:
            mid = module.module_id
            if mid in seen:
                seen[mid] += 1
                result.append(replace(module, module_id=f"{mid}_{seen[mid]}"))
            else:
                seen[mid] = 1
                result.append(module)
        return result
