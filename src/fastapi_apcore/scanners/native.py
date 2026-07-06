"""Native FastAPI route scanner.

Scans FastAPI routes via app.routes (APIRoute instances).
Extracts input schemas from Pydantic request models and path/query parameters.
Extracts output schemas from response_model or return type annotations.

Module ID format: {tag}.{function_name}.{method}
  e.g., task.create_task.post, product.get_products.get
"""

from __future__ import annotations

import inspect
import logging
import re
from typing import TYPE_CHECKING, Any, Callable, get_type_hints

from fastapi.routing import APIRoute

from fastapi_apcore.scanners.base import BaseScanner, ScannedModule

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger("fastapi_apcore")


class NativeFastAPIScanner(BaseScanner):
    """Scans FastAPI routes via app.routes for APIRoute instances.

    Extracts Pydantic model schemas from request bodies, path parameters,
    and query parameters. Uses FastAPI's built-in OpenAPI schema generation
    for accurate type information.
    """

    def scan(
        self,
        app: FastAPI,
        include: str | None = None,
        exclude: str | None = None,
    ) -> list[ScannedModule]:
        """Scan all FastAPI routes and generate module definitions.

        Args:
            app: FastAPI application instance.
            include: Regex pattern for module_id inclusion.
            exclude: Regex pattern for module_id exclusion.

        Returns:
            List of ScannedModule instances.
        """
        modules: list[ScannedModule] = []

        for route, prefix, extra_tags in self.collect_api_routes(app.routes):
            endpoint = route.endpoint
            if not callable(endpoint):
                continue

            full_path = prefix + route.path

            tags = self._extract_tags(route, extra_tags)

            for method in sorted(route.methods - {"HEAD", "OPTIONS"}):
                module_id = self._generate_module_id(route, tags, full_path, method)
                description = self._extract_description(
                    endpoint, route, full_path, method
                )
                documentation = self._extract_documentation(endpoint)
                annotations = self.infer_annotations_from_method(method)
                target = self._generate_target(endpoint)
                input_schema = self._extract_input_schema(full_path, endpoint)
                output_schema = self._extract_output_schema(route)

                warnings: list[str] = []
                if not input_schema.get("properties"):
                    warnings.append(
                        f"Route '{method} {full_path}' has no input parameters"
                    )

                modules.append(
                    ScannedModule(
                        module_id=module_id,
                        description=description,
                        input_schema=input_schema,
                        output_schema=output_schema,
                        tags=tags,
                        target=target,
                        http_method=method,
                        url_path=full_path,
                        annotations=annotations,
                        documentation=documentation,
                        metadata={"source": "native"},
                        warnings=warnings,
                    )
                )

        modules = self.deduplicate_ids(modules)
        return self.filter_modules(modules, include, exclude)

    def get_source_name(self) -> str:
        return "native-fastapi"

    def _generate_module_id(
        self, route: APIRoute, tags: list[str], path: str, method: str
    ) -> str:
        """Generate module_id from tags + function name + method.

        Format: {tag}.{function_name}.{method}
        Falls back to path-based ID if no tags or function name.
        """
        func_name = route.endpoint.__name__

        # Use first tag as prefix (most FastAPI apps tag by resource)
        tag = ""
        if tags:
            tag = str(tags[0]).lower().replace(" ", "_")

        if tag:
            module_id = f"{tag}.{func_name}.{method.lower()}"
        else:
            # Derive from URL path: /task/create → task.create
            path_parts = [
                p for p in path.strip("/").split("/") if not p.startswith("{")
            ]
            prefix = ".".join(path_parts) if path_parts else "root"
            module_id = f"{prefix}.{func_name}.{method.lower()}"

        return re.sub(r"[^a-zA-Z0-9._]", "_", module_id)

    def _extract_description(
        self, endpoint: Callable[..., Any], route: APIRoute, path: str, method: str
    ) -> str:
        """Extract description from route summary, docstring, or auto-generate."""
        if route.summary:
            return route.summary
        if route.description:
            return route.description.split("\n")[0].strip()
        doc = inspect.getdoc(endpoint)
        if doc:
            return doc.split("\n")[0].strip()
        return f"{method} {path}"

    def _extract_documentation(self, endpoint: Callable[..., Any]) -> str | None:
        """Extract full docstring as documentation."""
        doc = inspect.getdoc(endpoint)
        return doc.strip() if doc else None

    def _generate_target(self, endpoint: Callable[..., Any]) -> str:
        """Generate target in 'module.path:callable' format."""
        module = getattr(endpoint, "__module__", "__main__")
        name = getattr(endpoint, "__qualname__", endpoint.__name__)
        return f"{module}:{name}"

    def _extract_tags(
        self, route: APIRoute, extra_tags: tuple[str, ...] = ()
    ) -> list[str]:
        """Extract tags from route tags, merging any inherited from include_router."""
        merged: list[str] = list(extra_tags)
        for tag in route.tags or []:
            if str(tag) not in merged:
                merged.append(str(tag))
        return merged

    def _extract_input_schema(
        self, path: str, endpoint: Callable[..., Any]
    ) -> dict[str, Any]:
        """Extract input schema from path params, query params, and request body.

        Inspects the endpoint function signature to find:
        - Path parameters (from the route path)
        - Query parameters (simple typed params without Depends)
        - Request body (Pydantic BaseModel params)
        """

        schema: dict[str, Any] = {
            "type": "object",
            "properties": {},
            "required": [],
        }

        path_params = set(re.findall(r"\{(\w+)\}", path))
        sig = inspect.signature(endpoint)

        try:
            hints = get_type_hints(endpoint, include_extras=True)
        except Exception:
            hints = {}

        for param_name, param in sig.parameters.items():
            # Skip DI-injected params (Depends, Session, Request, etc.)
            if self._is_dependency(param, param_name):
                continue

            param_type = hints.get(param_name, param.annotation)

            # Pydantic body model → merge its fields
            if self._is_pydantic_model(param_type):
                try:
                    body_schema = param_type.model_json_schema()
                    for prop_name, prop_schema in body_schema.get(
                        "properties", {}
                    ).items():
                        schema["properties"][prop_name] = prop_schema
                        if prop_name in body_schema.get("required", []):
                            schema["required"].append(prop_name)
                except Exception:
                    logger.debug("Could not extract schema from %s", param_type)
                continue

            # Path or query parameter
            prop = self._python_type_to_json_schema(param_type)
            if param_name in path_params:
                prop["description"] = prop.get(
                    "description", f"Path parameter: {param_name}"
                )

            schema["properties"][param_name] = prop

            if param.default is inspect.Parameter.empty:
                schema["required"].append(param_name)

        if not schema["required"]:
            del schema["required"]

        return schema

    def _extract_output_schema(self, route: APIRoute) -> dict[str, Any]:
        """Extract output schema from response_model."""
        from pydantic import BaseModel

        if route.response_model is not None:
            try:
                if isinstance(route.response_model, type) and issubclass(
                    route.response_model, BaseModel
                ):
                    return route.response_model.model_json_schema()
            except Exception:
                pass
        return {"type": "object"}

    def _is_dependency(self, param: inspect.Parameter, name: str) -> bool:
        """Check if a parameter is a FastAPI dependency (Depends, Session, etc.)."""
        from fastapi.params import Depends as DependsClass

        # Skip well-known DI param names
        if name in ("db", "request", "response", "background_tasks", "session"):
            return True

        default = param.default
        if isinstance(default, DependsClass):
            return True

        # Check annotation for common DI types
        annotation = param.annotation
        if annotation is inspect.Parameter.empty:
            return False

        skip_type_names = {
            "Session",
            "Request",
            "Response",
            "BackgroundTasks",
            "WebSocket",
            "User",
            "UserResponse",
        }
        type_name = getattr(annotation, "__name__", "")
        if type_name in skip_type_names:
            return True

        return False

    @staticmethod
    def _is_pydantic_model(annotation: Any) -> bool:
        """Check if an annotation is a Pydantic BaseModel subclass."""
        from pydantic import BaseModel

        try:
            return isinstance(annotation, type) and issubclass(annotation, BaseModel)
        except TypeError:
            return False

    @staticmethod
    def _python_type_to_json_schema(annotation: Any) -> dict[str, Any]:
        """Convert a Python type annotation to a JSON Schema property."""
        type_map: dict[type, dict[str, str]] = {
            str: {"type": "string"},
            int: {"type": "integer"},
            float: {"type": "number"},
            bool: {"type": "boolean"},
        }

        if annotation in type_map:
            return dict(type_map[annotation])

        # Handle Optional[T]
        origin = getattr(annotation, "__origin__", None)
        args = getattr(annotation, "__args__", ())
        if origin is type(None):
            return {"type": "string"}

        # list[T]
        if origin is list and args:
            return {
                "type": "array",
                "items": NativeFastAPIScanner._python_type_to_json_schema(args[0]),
            }

        return {"type": "string"}
