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
from collections.abc import Iterable
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

from apcore import ModuleAnnotations
from apcore_toolkit import BaseScanner as _ToolkitBaseScanner
from apcore_toolkit.types import ScannedModule as _CanonicalScannedModule

if TYPE_CHECKING:
    from fastapi import FastAPI


@dataclass
class ScannedModule(_CanonicalScannedModule):
    """Result of scanning a single FastAPI endpoint.

    Extends the canonical :class:`apcore_toolkit.types.ScannedModule` — every
    shared field (``annotations``, ``examples``, ``display``,
    ``suggested_alias``, ``metadata``, ``warnings``, ...) is **inherited**, so
    this type can never drift from the canonical shape the way the previous
    standalone fork did. That drift dropped ``examples`` and crashed toolkit
    code reading ``mod.examples``; see apcore-toolkit-python#7 (item 3).

    ``http_method`` / ``url_path`` are FastAPI-specific extensions kept as
    top-level attributes for scanner ergonomics; the canonical type stores such
    route data in ``metadata``. They default to ``""`` (required-in-practice —
    every scanner sets them) because a dataclass subclass cannot add fields
    without defaults after the parent's defaulted fields.
    """

    http_method: str = ""
    url_path: str = ""


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

    def collect_api_routes(
        self,
        routes: Iterable[Any],
        prefix: str = "",
        extra_tags: tuple[str, ...] = (),
    ) -> list[tuple[Any, str, tuple[str, ...]]]:
        """Recursively collect APIRoute instances with their effective prefix and tags.

        FastAPI >=0.128 stopped flattening included routers into ``app.routes``;
        it inserts a lazy ``_IncludedRouter`` node that references the original
        ``APIRouter`` instead of copying its routes. Older versions expose
        ``APIRoute`` objects directly. This walk handles both shapes so routes
        are discovered regardless of the installed FastAPI version.

        Args:
            routes: Route objects to walk (typically ``app.routes``).
            prefix: URL prefix accumulated from enclosing routers/mounts.
            extra_tags: Tags accumulated from enclosing ``include_router`` calls.

        Returns:
            List of ``(route, prefix, extra_tags)`` tuples, one per APIRoute.
        """
        from fastapi.routing import APIRoute

        collected: list[tuple[Any, str, tuple[str, ...]]] = []
        for route in routes:
            if isinstance(route, APIRoute):
                collected.append((route, prefix, extra_tags))
                continue

            # FastAPI >=0.128 lazy include node: descend into the referenced router.
            original_router = getattr(route, "original_router", None)
            if original_router is not None:
                context = getattr(route, "include_context", None)
                include_prefix = getattr(context, "prefix", "") or ""
                include_tags = tuple(str(t) for t in (getattr(context, "tags", None) or ()))
                collected.extend(
                    self.collect_api_routes(
                        original_router.routes,
                        prefix + include_prefix,
                        extra_tags + include_tags,
                    )
                )
                continue

            # Starlette Mount / sub-router exposing nested routes directly.
            sub_routes = getattr(route, "routes", None)
            if sub_routes:
                mount_prefix = getattr(route, "path", "") or ""
                collected.extend(self.collect_api_routes(sub_routes, prefix + mount_prefix, extra_tags))
        return collected

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
