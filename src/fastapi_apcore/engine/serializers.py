"""Serialization helpers for ScannedModule instances."""

from __future__ import annotations

from typing import Any

from apcore_toolkit.serializers import annotations_to_dict


def module_to_dict(module: Any) -> dict[str, Any]:
    """Convert a single ScannedModule to a dict.

    Args:
        module: A ScannedModule instance.

    Returns:
        Dictionary representation of the module.
    """
    data: dict[str, Any] = {
        "module_id": module.module_id,
        "description": module.description,
        "input_schema": module.input_schema,
        "output_schema": module.output_schema,
        "tags": module.tags,
        "target": module.target,
        "http_method": module.http_method,
        "url_path": module.url_path,
        "version": module.version,
        "metadata": module.metadata,
        "warnings": module.warnings,
    }
    if module.annotations is not None:
        data["annotations"] = annotations_to_dict(module.annotations)
    if module.documentation is not None:
        data["documentation"] = module.documentation
    return data


def modules_to_dicts(modules: list[Any]) -> list[dict[str, Any]]:
    """Convert a list of ScannedModule instances to dicts.

    Args:
        modules: List of ScannedModule instances.

    Returns:
        List of dictionary representations.
    """
    return [module_to_dict(m) for m in modules]


__all__ = ["module_to_dict", "modules_to_dicts"]
