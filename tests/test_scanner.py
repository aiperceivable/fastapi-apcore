"""Tests for FastAPI scanners (native and openapi)."""

from __future__ import annotations

from typing import Optional

import pytest
from fastapi import APIRouter, Depends, FastAPI
from pydantic import BaseModel, Field

from fastapi_apcore.scanners.native import NativeFastAPIScanner
from fastapi_apcore.scanners.openapi import OpenAPIScanner


# -- Test app ---------------------------------------------------------------


class ItemCreate(BaseModel):
    name: str = Field(..., description="Item name")
    price: float = Field(..., description="Item price")
    description: Optional[str] = Field(None, description="Item description")


class ItemResponse(BaseModel):
    id: str
    name: str
    price: float


def fake_db():
    return None


def build_test_app() -> FastAPI:
    """Build a minimal FastAPI app for testing."""
    app = FastAPI(title="Test API")
    router = APIRouter(prefix="/items", tags=["items"])

    @router.get("", summary="List all items")
    async def list_items(skip: int = 0, limit: int = 10, db=Depends(fake_db)):
        """List items with pagination."""
        return []

    @router.post("", response_model=ItemResponse, summary="Create item")
    async def create_item(item: ItemCreate, db=Depends(fake_db)):
        """Create a new item."""
        return {"id": "1", **item.model_dump()}

    @router.get("/{item_id}", response_model=ItemResponse, summary="Get item")
    async def get_item(item_id: str, db=Depends(fake_db)):
        """Get a single item by ID."""
        return {"id": item_id, "name": "Test", "price": 9.99}

    @router.delete("/{item_id}", summary="Delete item")
    async def delete_item(item_id: str, db=Depends(fake_db)):
        """Delete an item."""
        return {"ok": True}

    app.include_router(router)
    return app


@pytest.fixture()
def app() -> FastAPI:
    return build_test_app()


# -- NativeFastAPIScanner ---------------------------------------------------


class TestNativeScanner:
    def test_scan_discovers_all_routes(self, app: FastAPI) -> None:
        scanner = NativeFastAPIScanner()
        modules = scanner.scan(app)

        # 4 endpoints: GET /, POST /, GET /{item_id}, DELETE /{item_id}
        assert len(modules) == 4

    def test_module_ids_include_tag(self, app: FastAPI) -> None:
        scanner = NativeFastAPIScanner()
        modules = scanner.scan(app)
        ids = {m.module_id for m in modules}

        # All should be prefixed with "items" tag
        assert all("items." in mid for mid in ids)

    def test_http_methods_correct(self, app: FastAPI) -> None:
        scanner = NativeFastAPIScanner()
        modules = scanner.scan(app)

        get_modules = [m for m in modules if m.http_method == "GET"]
        post_modules = [m for m in modules if m.http_method == "POST"]
        delete_modules = [m for m in modules if m.http_method == "DELETE"]

        assert len(get_modules) == 2
        assert len(post_modules) == 1
        assert len(delete_modules) == 1

    def test_annotations_inferred(self, app: FastAPI) -> None:
        scanner = NativeFastAPIScanner()
        modules = scanner.scan(app)

        for m in modules:
            assert m.annotations is not None
            if m.http_method == "GET":
                assert m.annotations.readonly is True
            elif m.http_method == "DELETE":
                assert m.annotations.destructive is True

    def test_post_has_body_schema(self, app: FastAPI) -> None:
        scanner = NativeFastAPIScanner()
        modules = scanner.scan(app)

        post_module = next(m for m in modules if m.http_method == "POST")
        props = post_module.input_schema.get("properties", {})

        assert "name" in props
        assert "price" in props
        assert "description" in props

    def test_get_has_output_schema(self, app: FastAPI) -> None:
        scanner = NativeFastAPIScanner()
        modules = scanner.scan(app)

        get_detail = next(m for m in modules if m.http_method == "GET" and "{item_id}" in m.url_path)
        assert get_detail.output_schema.get("properties") is not None

    def test_description_from_summary(self, app: FastAPI) -> None:
        scanner = NativeFastAPIScanner()
        modules = scanner.scan(app)

        post_module = next(m for m in modules if m.http_method == "POST")
        assert post_module.description == "Create item"

    def test_include_filter(self, app: FastAPI) -> None:
        scanner = NativeFastAPIScanner()
        modules = scanner.scan(app, include=r"\.get$")

        assert all(m.module_id.endswith(".get") for m in modules)

    def test_exclude_filter(self, app: FastAPI) -> None:
        scanner = NativeFastAPIScanner()
        modules = scanner.scan(app, exclude=r"\.delete$")

        assert not any(m.module_id.endswith(".delete") for m in modules)

    def test_target_format(self, app: FastAPI) -> None:
        scanner = NativeFastAPIScanner()
        modules = scanner.scan(app)

        for m in modules:
            assert ":" in m.target
            module_path, func = m.target.split(":", 1)
            assert module_path
            assert func

    def test_dependencies_excluded_from_schema(self, app: FastAPI) -> None:
        """Depends() params should NOT appear in input_schema."""
        scanner = NativeFastAPIScanner()
        modules = scanner.scan(app)

        for m in modules:
            props = m.input_schema.get("properties", {})
            assert "db" not in props, f"'db' Depends leaked into {m.module_id}"


# -- OpenAPIScanner ---------------------------------------------------------


class TestOpenAPIScanner:
    def test_scan_discovers_all_routes(self, app: FastAPI) -> None:
        scanner = OpenAPIScanner()
        modules = scanner.scan(app)

        assert len(modules) == 4

    def test_module_ids_include_tag(self, app: FastAPI) -> None:
        scanner = OpenAPIScanner()
        modules = scanner.scan(app)
        ids = {m.module_id for m in modules}

        assert all("items." in mid for mid in ids)

    def test_input_schema_from_openapi(self, app: FastAPI) -> None:
        scanner = OpenAPIScanner()
        modules = scanner.scan(app)

        post_module = next(m for m in modules if m.http_method == "POST")
        props = post_module.input_schema.get("properties", {})

        assert "name" in props
        assert "price" in props

    def test_output_schema_from_openapi(self, app: FastAPI) -> None:
        scanner = OpenAPIScanner()
        modules = scanner.scan(app)

        get_detail = next(m for m in modules if m.http_method == "GET" and "{item_id}" in m.url_path)
        # OpenAPI scanner should extract resolved output schema
        assert get_detail.output_schema != {"type": "object"} or get_detail.output_schema.get("properties") is not None

    def test_include_filter(self, app: FastAPI) -> None:
        scanner = OpenAPIScanner()
        modules = scanner.scan(app, include=r"\.post$")

        assert len(modules) == 1
        assert modules[0].http_method == "POST"

    def test_metadata_has_source(self, app: FastAPI) -> None:
        scanner = OpenAPIScanner()
        modules = scanner.scan(app)

        for m in modules:
            assert m.metadata.get("source") == "openapi"
            assert "operation_id" in m.metadata


# -- OpenAPIScanner simplify_ids --------------------------------------------


class TestOpenAPIScannerSimplifyIds:
    def test_simplified_ids_are_shorter(self, app: FastAPI) -> None:
        default = OpenAPIScanner()
        simplified = OpenAPIScanner(simplify_ids=True)

        default_modules = default.scan(app)
        simplified_modules = simplified.scan(app)

        assert len(default_modules) == len(simplified_modules)
        for d, s in zip(default_modules, simplified_modules):
            assert len(s.module_id) <= len(d.module_id)

    def test_simplified_ids_use_func_name(self, app: FastAPI) -> None:
        scanner = OpenAPIScanner(simplify_ids=True)
        modules = scanner.scan(app)
        ids = {m.module_id for m in modules}

        # Should contain clean function-name based IDs
        assert "items.list_items.get" in ids
        assert "items.create_item.post" in ids
        assert "items.get_item.get" in ids
        assert "items.delete_item.delete" in ids

    def test_default_ids_contain_path_info(self, app: FastAPI) -> None:
        scanner = OpenAPIScanner(simplify_ids=False)
        modules = scanner.scan(app)
        ids = {m.module_id for m in modules}

        # Default IDs should contain path fragments (longer)
        get_detail = next(mid for mid in ids if "get_item" in mid and mid.endswith(".get"))
        assert "item_id" in get_detail  # path param info preserved

    def test_simplify_ids_no_duplicates(self, app: FastAPI) -> None:
        scanner = OpenAPIScanner(simplify_ids=True)
        modules = scanner.scan(app)
        ids = [m.module_id for m in modules]

        assert len(ids) == len(set(ids)), f"Duplicate IDs found: {ids}"

    def test_factory_passes_simplify_ids(self, app: FastAPI) -> None:
        import warnings

        from fastapi_apcore.scanners import get_scanner

        with warnings.catch_warnings(record=True):
            scanner = get_scanner("openapi", simplify_ids=True)
        modules = scanner.scan(app)

        # Verify simplified IDs (no path fragments like __item_id__)
        for m in modules:
            assert "__" not in m.module_id, f"Unsimplified ID: {m.module_id}"

    def test_simplify_ids_emits_deprecation_warning(self) -> None:
        """OpenAPIScanner(simplify_ids=True) must emit a DeprecationWarning."""
        import warnings

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            OpenAPIScanner(simplify_ids=True)

        dep_warnings = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        assert len(dep_warnings) == 1
        assert "simplify_ids" in str(dep_warnings[0].message).lower()
        assert "deprecated" in str(dep_warnings[0].message).lower()

    def test_simplify_ids_sets_suggested_alias_in_metadata(self, app: FastAPI) -> None:
        """simplify_ids=True writes suggested_alias to module metadata."""
        import warnings

        with warnings.catch_warnings(record=True):
            scanner = OpenAPIScanner(simplify_ids=True)
        modules = scanner.scan(app)
        for m in modules:
            assert "suggested_alias" in m.metadata, f"Missing suggested_alias for {m.module_id}"


# -- get_scanner factory -----------------------------------------------------


class TestScannerFactory:
    def test_get_native_scanner(self) -> None:
        from fastapi_apcore.scanners import get_scanner

        scanner = get_scanner("native")
        assert isinstance(scanner, NativeFastAPIScanner)

    def test_get_openapi_scanner(self) -> None:
        from fastapi_apcore.scanners import get_scanner

        scanner = get_scanner("openapi")
        assert isinstance(scanner, OpenAPIScanner)

    def test_default_is_openapi(self) -> None:
        from fastapi_apcore.scanners import get_scanner

        scanner = get_scanner()
        assert isinstance(scanner, OpenAPIScanner)

    def test_unknown_source_raises(self) -> None:
        from fastapi_apcore.scanners import get_scanner

        with pytest.raises(ValueError, match="Unknown scanner"):
            get_scanner("nonexistent")
