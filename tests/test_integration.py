"""Integration tests for fastapi-apcore end-to-end workflows."""

from __future__ import annotations

from unittest.mock import patch

from fastapi import FastAPI, APIRouter
from pydantic import BaseModel

from fastapi_apcore import FastAPIApcore, get_scanner


class ItemCreate(BaseModel):
    name: str
    price: float


class ItemResponse(BaseModel):
    id: int
    name: str
    price: float


def _build_test_app() -> FastAPI:
    app = FastAPI(title="Test API")
    router = APIRouter(prefix="/items", tags=["items"])

    @router.get("", response_model=list[ItemResponse], summary="List items")
    async def list_items():
        return []

    @router.post("", response_model=ItemResponse, summary="Create item")
    async def create_item(item: ItemCreate):
        return {"id": 1, **item.model_dump()}

    app.include_router(router)
    return app


class TestScanAndRegister:
    def test_scan_via_client(self):
        """FastAPIApcore.scan() delegates to get_scanner correctly."""
        app = _build_test_app()
        client = FastAPIApcore()
        modules = client.scan(app, source="openapi")
        assert len(modules) >= 2
        ids = [m.module_id for m in modules]
        assert any("items" in mid for mid in ids)

    def test_scan_native(self):
        """Native scanner discovers routes directly."""
        app = _build_test_app()
        scanner = get_scanner("native")
        modules = scanner.scan(app)
        assert len(modules) >= 2

    def test_scan_openapi(self):
        """OpenAPI scanner discovers routes via OpenAPI spec."""
        app = _build_test_app()
        scanner = get_scanner("openapi")
        modules = scanner.scan(app)
        assert len(modules) >= 2

    def test_scan_with_include_filter(self):
        """Include filter narrows results."""
        app = _build_test_app()
        scanner = get_scanner("openapi")
        modules = scanner.scan(app, include=r"\.post$")
        assert len(modules) == 1
        assert "post" in modules[0].module_id

    def test_scan_with_exclude_filter(self):
        """Exclude filter removes matches."""
        app = _build_test_app()
        scanner = get_scanner("openapi")
        all_modules = scanner.scan(app)
        filtered = scanner.scan(app, exclude=r"\.post$")
        assert len(filtered) < len(all_modules)


class TestClientSingleton:
    def test_singleton_pattern(self):
        """get_instance returns same object."""
        FastAPIApcore._reset_instance()
        try:
            a = FastAPIApcore.get_instance()
            b = FastAPIApcore.get_instance()
            assert a is b
        finally:
            FastAPIApcore._reset_instance()


class TestContextFactory:
    def test_fastapi_context_factory_integration(self):
        """FastAPIContextFactory creates context from mock request."""
        from fastapi_apcore.engine.context import FastAPIContextFactory
        from types import SimpleNamespace

        user = SimpleNamespace(id="42", roles=["admin"], is_staff=True)
        state = SimpleNamespace(user=user)
        request = SimpleNamespace(state=state, headers={})

        factory = FastAPIContextFactory()
        with patch("apcore.Context") as mock_ctx, patch("apcore.Identity") as mock_id:
            mock_id.return_value = "identity"
            mock_ctx.create.return_value = "context"
            result = factory.create_context(request)
            assert result == "context"
            mock_id.assert_called_once()
            call_kwargs = mock_id.call_args[1]
            assert call_kwargs["id"] == "42"
            assert call_kwargs["roles"] == ("admin",)
