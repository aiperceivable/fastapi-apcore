"""OpenAPI-based FastAPI scanner.

Scans FastAPI routes via the auto-generated OpenAPI schema.
This is the most accurate scanner since FastAPI's OpenAPI generation
handles all edge cases (Depends, File, Form, etc.).

Module ID format:
  Default:        {tag}.{operationId_without_method}.{method}
  simplify_ids:   {tag}.{func_name}.{method}
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

from apcore_toolkit.openapi import extract_input_schema, extract_output_schema

from fastapi_apcore.scanners.base import BaseScanner, ScannedModule

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger("fastapi_apcore")


class OpenAPIScanner(BaseScanner):
    """Scans FastAPI routes via the auto-generated OpenAPI schema.

    This scanner produces the most accurate schemas since it uses
    FastAPI's own OpenAPI generation, which correctly handles:
    - Depends() injection (excluded from schema)
    - File/Form parameters
    - Complex Pydantic model nesting
    - Response models with $ref
    """

    def __init__(self, *, simplify_ids: bool = False) -> None:
        """Initialize the OpenAPI scanner.

        Args:
            simplify_ids: When True, generate simplified module IDs using only
                the function name (e.g. ``product.get_product.get``).
                When False (default), use the full FastAPI operationId
                (e.g. ``product.get_product_product__product_id_.get``).
        """
        self._simplify_ids = simplify_ids

    def scan(
        self,
        app: FastAPI,
        include: str | None = None,
        exclude: str | None = None,
    ) -> list[ScannedModule]:
        """Scan all FastAPI routes via OpenAPI schema.

        Args:
            app: FastAPI application instance.
            include: Regex pattern for module_id inclusion.
            exclude: Regex pattern for module_id exclusion.

        Returns:
            List of ScannedModule instances.
        """
        openapi_schema = app.openapi()
        paths: dict[str, Any] = openapi_schema.get("paths", {})
        modules: list[ScannedModule] = []

        # Build operationId → view function map for target resolution
        view_map = self._build_view_map(app)

        for path, path_item in paths.items():
            for method, operation in path_item.items():
                if method in ("parameters", "summary", "description"):
                    continue  # Skip path-level metadata

                method_upper = method.upper()
                if method_upper in ("HEAD", "OPTIONS"):
                    continue

                operation_id: str = operation.get("operationId", "")
                if not operation_id:
                    continue

                module_id = self._generate_module_id(operation, path, method_upper)
                description = (
                    operation.get("summary")
                    or operation.get("description", "").split("\n")[0].strip()
                    or f"{method_upper} {path}"
                )
                documentation = operation.get("description")
                annotations = self.infer_annotations_from_method(method_upper)
                tags = operation.get("tags", [])
                target = view_map.get(operation_id, f"__unknown__:{operation_id}")

                input_schema = extract_input_schema(operation, openapi_schema)
                output_schema = extract_output_schema(operation, openapi_schema)

                modules.append(
                    ScannedModule(
                        module_id=module_id,
                        description=description,
                        input_schema=input_schema,
                        output_schema=output_schema,
                        tags=tags,
                        target=target,
                        http_method=method_upper,
                        url_path=path,
                        annotations=annotations,
                        documentation=documentation,
                        metadata={"source": "openapi", "operation_id": operation_id},
                        warnings=[],
                    )
                )

        modules = self.deduplicate_ids(modules)
        return self.filter_modules(modules, include, exclude)

    def get_source_name(self) -> str:
        return "openapi-fastapi"

    def _generate_module_id(self, operation: dict[str, Any], path: str, method: str) -> str:
        """Generate module_id from prefix + function_name + method.

        When ``simplify_ids=True`` (set in constructor), extracts the clean
        function name and uses only the first path segment as prefix::

            GET  /product/{product_id}                      → product.get_product.get
            POST /task/create                               → task.create_task.post
            GET  /virtual-purchase/purchase/status/{id}     → virtual_purchase.get_purchase_status_by_payment_intent.get

        When ``simplify_ids=False`` (default), uses the raw operationId
        with only the trailing method stripped, and all path segments as prefix::

            GET /product/{product_id}  → product.get_product_product__product_id_.get
        """
        operation_id: str = operation.get("operationId", "unknown")
        tags = operation.get("tags", [])

        if self._simplify_ids:
            func_name = self._extract_func_name(operation_id, path, method)
        else:
            func_name = self._strip_method_suffix(operation_id, method)

        if tags:
            prefix = str(tags[0]).lower().replace(" ", "_")
        elif self._simplify_ids:
            # Only first path segment as prefix — shorter, still unique
            path_parts = [p for p in path.strip("/").split("/") if not p.startswith("{")]
            prefix = path_parts[0] if path_parts else "root"
        else:
            # All path segments as prefix (default, backward compatible)
            path_parts = [p for p in path.strip("/").split("/") if not p.startswith("{")]
            prefix = ".".join(path_parts) if path_parts else "root"

        module_id = f"{prefix}.{func_name}.{method.lower()}"
        return re.sub(r"[^a-zA-Z0-9._]", "_", module_id)

    @staticmethod
    def _strip_method_suffix(operation_id: str, method: str) -> str:
        """Strip the trailing ``_{method}`` from an operationId.

        This is the default (non-short) simplification — removes only the
        HTTP method suffix while preserving the full path information.
        """
        suffix = f"_{method.lower()}"
        if operation_id.endswith(suffix):
            return operation_id[: -len(suffix)]
        return operation_id

    @staticmethod
    def _extract_func_name(operation_id: str, path: str, method: str) -> str:
        """Extract the original function name from a FastAPI operationId.

        FastAPI generates operationId as::

            re.sub(r"\\W", "_", f"{func_name}{path}") + "_{method}"

        This method reverses that transformation to recover ``func_name``.
        """
        method_lower = method.lower()

        # Reconstruct the path suffix exactly as FastAPI generates it:
        # every non-word character (\W) in the path becomes "_"
        path_suffix = re.sub(r"\W", "_", path)
        expected_suffix = f"{path_suffix}_{method_lower}"

        if operation_id.endswith(expected_suffix):
            return operation_id[: -len(expected_suffix)].rstrip("_")

        # Fallback: strip trailing _{method}
        if operation_id.endswith(f"_{method_lower}"):
            return operation_id[: -(len(method_lower) + 1)]

        return operation_id

    def _build_view_map(self, app: FastAPI) -> dict[str, str]:
        """Build a map of operationId → target string.

        Iterates FastAPI routes to extract endpoint function references.
        """
        from fastapi.routing import APIRoute

        view_map: dict[str, str] = {}
        for route in app.routes:
            if not isinstance(route, APIRoute):
                continue
            endpoint = route.endpoint
            if not callable(endpoint):
                continue
            # FastAPI auto-generates operationId from function name + path + method
            # We map all possible operation IDs for this endpoint
            op_id = route.operation_id or route.unique_id
            module = getattr(endpoint, "__module__", "__main__")
            name = getattr(endpoint, "__qualname__", endpoint.__name__)
            target = f"{module}:{name}"

            if op_id:
                view_map[op_id] = target

            # Also map by function name (fallback)
            view_map[endpoint.__name__] = target

        return view_map
