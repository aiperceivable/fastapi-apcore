"""Tests for output writers."""

from __future__ import annotations

import pytest

from fastapi_apcore.output import get_writer
from fastapi_apcore.output.registry_writer import FastAPIRegistryWriter, _schema_to_pydantic


class TestGetWriter:
    """Tests for the get_writer factory function."""

    def test_get_writer_default_returns_registry_writer(self) -> None:
        """Default writer (no format) should return FastAPIRegistryWriter."""
        writer = get_writer()
        assert isinstance(writer, FastAPIRegistryWriter)

    def test_get_writer_yaml_returns_yaml_writer(self) -> None:
        """Passing 'yaml' should return a YAMLWriter instance."""
        from apcore_toolkit.output.yaml_writer import YAMLWriter

        writer = get_writer("yaml")
        assert isinstance(writer, YAMLWriter)

    def test_get_writer_http_proxy_returns_http_proxy_writer(self) -> None:
        """Passing 'http-proxy' should return an HTTPProxyRegistryWriter."""
        from apcore_toolkit.output.http_proxy_writer import HTTPProxyRegistryWriter

        writer = get_writer("http-proxy", base_url="http://localhost:8000")
        assert isinstance(writer, HTTPProxyRegistryWriter)

    def test_get_writer_unknown_raises(self) -> None:
        """Unknown format should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown output format"):
            get_writer("nonexistent")


class TestSchemaTopydantic:
    """Tests for _schema_to_pydantic helper."""

    def test_schema_to_pydantic_empty(self) -> None:
        """An empty schema should produce a model with no fields."""
        model = _schema_to_pydantic("Empty", {})
        instance = model()
        assert instance is not None

    def test_schema_to_pydantic_with_properties(self) -> None:
        """Schema with properties should produce a model with matching fields."""
        schema = {
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
            },
            "required": ["name", "age"],
        }
        model = _schema_to_pydantic("Person", schema)
        instance = model(name="Alice", age=30)
        assert instance.name == "Alice"
        assert instance.age == 30

    def test_schema_to_pydantic_required_vs_optional(self) -> None:
        """Required fields must be provided; optional fields default to None."""
        schema = {
            "properties": {
                "title": {"type": "string"},
                "description": {"type": "string"},
            },
            "required": ["title"],
        }
        model = _schema_to_pydantic("Item", schema)

        # Optional field defaults to None
        instance = model(title="Hello")
        assert instance.title == "Hello"
        assert instance.description is None

        # Omitting required field should raise
        with pytest.raises(Exception):
            model()
