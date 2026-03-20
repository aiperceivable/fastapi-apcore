"""Output writers for fastapi-apcore."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastapi_apcore.output.registry_writer import FastAPIRegistryWriter as FastAPIRegistryWriter
    from fastapi_apcore.output.yaml_writer import YAMLWriter as YAMLWriter


def get_writer(output_format: str | None = None, **kwargs: Any) -> Any:
    """Get a writer instance for the given format.

    Args:
        output_format: 'yaml' for file output, 'http-proxy' for HTTP proxy
            registration, or None for direct registry registration.
        **kwargs: Passed to the writer constructor. For 'http-proxy':
            ``base_url``, ``auth_header_factory``, ``timeout``.

    Returns:
        A writer instance.
    """
    if output_format is None:
        from fastapi_apcore.output.registry_writer import FastAPIRegistryWriter

        return FastAPIRegistryWriter()
    if output_format == "yaml":
        from fastapi_apcore.output.yaml_writer import YAMLWriter

        return YAMLWriter()
    if output_format == "http-proxy":
        from apcore_toolkit.output.http_proxy_writer import HTTPProxyRegistryWriter

        return HTTPProxyRegistryWriter(**kwargs)
    raise ValueError(
        f"Unknown output format '{output_format}'. " "Supported: 'yaml', 'http-proxy', or None (registry)."
    )
