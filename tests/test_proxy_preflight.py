"""Tests for create_cli() HTTP proxy preflight (apcore-toolkit 0.15.0)."""

from __future__ import annotations

import pytest
from apcore_toolkit import validate_effective_proxy_modules
from pydantic import BaseModel

from fastapi_apcore import FastAPIApcore
from fastapi_apcore.scanners.base import ScannedModule
from fastapi_apcore.scanners.openapi import apply_effective_proxy_inputs


class _Item(BaseModel):
    name: str


def _spec_with_path_item_parameters() -> dict:
    return {
        "openapi": "3.0.0",
        "info": {"title": "Test", "version": "1.0.0"},
        "paths": {
            "/items/{item_id}": {
                "parameters": [
                    {
                        "name": "item_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                ],
                "get": {
                    "operationId": "get_item",
                    "parameters": [
                        {
                            "name": "expand",
                            "in": "query",
                            "schema": {"type": "boolean"},
                        }
                    ],
                    "responses": {"200": {"description": "ok"}},
                },
            }
        },
    }


def _module(method: str = "GET", path: str = "/items/{item_id}") -> ScannedModule:
    return ScannedModule(
        module_id="items.get_item.get",
        description="Get an item",
        input_schema={"type": "object", "properties": {}, "required": []},
        output_schema={"type": "object", "properties": {}},
        tags=["items"],
        target="tests:get_item",
        http_method=method,
        url_path=path,
        metadata={"source": "openapi"},
    )


class TestApplyEffectiveProxyInputs:
    """The sidecar effective scan enriches only the proxy-facing fields."""

    def test_inherits_path_item_parameters(self):
        [module] = apply_effective_proxy_inputs([_module()], _spec_with_path_item_parameters())

        assert set(module.input_schema["properties"]) == {"item_id", "expand"}
        openapi_meta = module.metadata["openapi"]
        assert openapi_meta["proxy_inputs"]["path"] == ["item_id"]
        assert openapi_meta["proxy_inputs"]["query"] == ["expand"]
        # Adapter-owned fields are preserved.
        assert module.module_id == "items.get_item.get"
        assert module.target == "tests:get_item"
        assert module.metadata["source"] == "openapi"

    def test_enriched_module_passes_preflight(self):
        [module] = apply_effective_proxy_inputs([_module()], _spec_with_path_item_parameters())

        validate_effective_proxy_modules([module])


class TestCreateCliProxyPreflight:
    """create_cli() refuses operations the HTTP proxy cannot forward."""

    def test_rejects_query_parameter_on_json_body_method(self):
        from fastapi import FastAPI

        app = FastAPI()

        @app.post("/items")
        def create_item(item: _Item, dry_run: bool = False) -> dict:
            return {"name": item.name, "dry_run": dry_run}

        client = FastAPIApcore()
        with pytest.raises(ValueError, match="proxy preflight failed"):
            client.create_cli(app, prog_name="test-cli", base_url="http://localhost:8000")

    def test_validate_proxy_false_keeps_legacy_behaviour(self):
        from fastapi import FastAPI

        app = FastAPI()

        @app.post("/items")
        def create_item(item: _Item, dry_run: bool = False) -> dict:
            return {"name": item.name, "dry_run": dry_run}

        client = FastAPIApcore()
        cli = client.create_cli(
            app,
            prog_name="test-cli",
            base_url="http://localhost:8000",
            validate_proxy=False,
        )

        import click

        assert isinstance(cli, click.Group)
