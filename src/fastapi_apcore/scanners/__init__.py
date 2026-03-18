"""Scanner registry and factory for FastAPI route scanners."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi_apcore.scanners.native import NativeFastAPIScanner
from fastapi_apcore.scanners.openapi import OpenAPIScanner

if TYPE_CHECKING:
    from fastapi_apcore.scanners.base import BaseScanner

_SCANNER_REGISTRY: dict[str, type[BaseScanner]] = {
    "native": NativeFastAPIScanner,
    "openapi": OpenAPIScanner,
}


def get_scanner(source: str = "openapi") -> BaseScanner:
    """Instantiate a scanner by source name.

    Args:
        source: Scanner type — 'native' for route inspection,
                'openapi' for OpenAPI schema-based scanning (default).

    Returns:
        A BaseScanner subclass instance.

    Raises:
        ValueError: If the source is not recognized.
    """
    scanner_cls = _SCANNER_REGISTRY.get(source)
    if scanner_cls is None:
        valid = ", ".join(sorted(_SCANNER_REGISTRY))
        raise ValueError(f"Unknown scanner source '{source}'. Valid sources: {valid}")
    return scanner_cls()
