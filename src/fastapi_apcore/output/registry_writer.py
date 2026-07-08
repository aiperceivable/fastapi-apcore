"""FastAPI-aware registry writer.

Extends apcore-toolkit's RegistryWriter. Unlike Django, FastAPI endpoints
don't have a request parameter that needs stripping.
"""

from __future__ import annotations

import contextlib
import logging
from typing import TYPE_CHECKING, Any

from apcore_toolkit.output.registry_writer import RegistryWriter

if TYPE_CHECKING:
    from apcore_toolkit.types import ScannedModule

logger = logging.getLogger("fastapi_apcore")


class FastAPIRegistryWriter(RegistryWriter):
    """Registry writer for FastAPI scanned modules.

    Handles module registration with:
    - Auto-replacement of existing modules (from auto-discovery)
    - Pydantic parameter flattening
    - Schema-based FunctionModule creation
    """

    def write(
        self,
        modules: list[ScannedModule],
        registry: Any,
        *,
        dry_run: bool = False,
        verify: bool = False,
        verifiers: Any = None,
        allowed_prefixes: list[str] | None = None,
    ) -> list[Any]:
        from apcore_toolkit.output.types import WriteResult
        from apcore_toolkit.output.verifiers import RegistryVerifier, run_verifier_chain

        results: list[WriteResult] = []
        for mod in modules:
            if dry_run:
                results.append(WriteResult(module_id=mod.module_id))
                continue

            fm = self._to_function_module(mod, allowed_prefixes=allowed_prefixes)
            with contextlib.suppress(KeyError, ValueError):
                registry.unregister(mod.module_id)
            registry.register(mod.module_id, fm)
            logger.debug("Registered module: %s", mod.module_id)

            result = WriteResult(module_id=mod.module_id)
            if verify:
                vr = RegistryVerifier(registry).verify("", mod.module_id)
                if not vr.ok:
                    result = WriteResult(
                        module_id=mod.module_id,
                        verified=False,
                        verification_error=vr.error,
                    )
            if result.verified and verifiers:
                chain_result = run_verifier_chain(verifiers, "", mod.module_id)
                if not chain_result.ok:
                    result = WriteResult(
                        module_id=result.module_id,
                        path=result.path,
                        verified=False,
                        verification_error=chain_result.error,
                    )
            results.append(result)
        return results

    # NOTE: this writer no longer overrides ``_to_function_module``. Doing so
    # previously dropped ``annotations``, silently disabling approval/ACL gating
    # (that keys on ``requires_approval``) for scanned routes. Field mapping —
    # including annotations — is now centralized in the toolkit base writer's
    # ``_build_function_module``; here we override only the narrow schema hooks.

    def _build_input_schema(self, mod: ScannedModule) -> Any:
        """Build an explicit input model from the scanned OpenAPI/Pydantic schema
        so ``FunctionModule`` skips function introspection."""
        return _schema_to_pydantic(f"{mod.module_id}_Input", mod.input_schema)

    def _build_output_schema(self, mod: ScannedModule) -> Any:
        """Build an explicit output model from the scanned schema. See
        :meth:`_build_input_schema`."""
        return _schema_to_pydantic(f"{mod.module_id}_Output", mod.output_schema)


_JSON_TYPE_MAP: dict[str, type] = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "array": list,
    "object": dict,
}


def _schema_to_pydantic(name: str, schema: dict[str, Any]) -> Any:
    """Create a dynamic Pydantic model from a JSON Schema dict."""
    from pydantic import create_model

    properties = schema.get("properties", {})
    if not properties:
        return create_model(name)

    required = set(schema.get("required", []))
    fields: dict[str, Any] = {}

    for field_name, field_schema in properties.items():
        py_type = _JSON_TYPE_MAP.get(field_schema.get("type", ""), Any)
        if field_name in required:
            fields[field_name] = (py_type, ...)
        else:
            fields[field_name] = (py_type | None, None)

    return create_model(name, **fields)
