"""OpenAPI-based FastAPI scanner.

Scans FastAPI routes via the auto-generated OpenAPI schema.
This is the most accurate scanner since FastAPI's OpenAPI generation
handles all edge cases (Depends, File, Form, etc.).

Module ID format: {tag}.{operation_id}.{method}
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
        """Generate module_id from tags + operation_id + method.

        Format: {tag}.{operation_id}.{method}
        Falls back to path-based ID if no tags.
        """
        operation_id: str = operation.get("operationId", "unknown")
        tags = operation.get("tags", [])

        # Clean operation_id: FastAPI generates e.g. "create_task_task_create_post"
        # We use the simpler function name portion
        func_name = self._simplify_operation_id(operation_id)

        if tags:
            prefix = str(tags[0]).lower().replace(" ", "_")
            module_id = f"{prefix}.{func_name}.{method.lower()}"
        else:
            path_parts = [p for p in path.strip("/").split("/") if not p.startswith("{")]
            prefix = ".".join(path_parts) if path_parts else "root"
            module_id = f"{prefix}.{func_name}.{method.lower()}"

        return re.sub(r"[^a-zA-Z0-9._]", "_", module_id)

    def _simplify_operation_id(self, operation_id: str) -> str:
        """Simplify FastAPI's auto-generated operation IDs.

        FastAPI generates IDs like 'create_task_task_create_post'.
        We strip the trailing path+method suffix to get the function name.
        """
        # FastAPI pattern: {func_name}_{path_part}_{path_part}_{method}
        # Try to extract just the function name by removing the suffix
        parts = operation_id.rsplit("_", 1)
        if len(parts) == 2 and parts[1] in ("get", "post", "put", "delete", "patch"):
            return parts[0]
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
