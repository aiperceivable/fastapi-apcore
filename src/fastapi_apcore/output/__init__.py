"""Output writers for fastapi-apcore."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastapi_apcore.output.registry_writer import FastAPIRegistryWriter as FastAPIRegistryWriter
    from fastapi_apcore.output.yaml_writer import YAMLWriter as YAMLWriter


def get_writer(output_format: str | None = None) -> Any:
    """Get a writer instance for the given format.

    Args:
        output_format: 'yaml' for file output, None for direct registry registration.

    Returns:
        A writer instance.
    """
    if output_format is None:
        from fastapi_apcore.output.registry_writer import FastAPIRegistryWriter

        return FastAPIRegistryWriter()
    if output_format == "yaml":
        from fastapi_apcore.output.yaml_writer import YAMLWriter

        return YAMLWriter()
    raise ValueError(f"Unknown output format '{output_format}'. Supported: 'yaml' or None (registry).")
