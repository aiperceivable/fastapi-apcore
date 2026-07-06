"""Integration test for the FastAPI + apcore ACL demo (examples/acl_demo).

Exercises the full path: request -> FastAPIContextFactory identity ->
Executor ACL check -> allow/deny, proving that apcore ACL rules govern module
calls made from FastAPI routes.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# examples/ lives at the repo root, outside the installed `src` package path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """Build a fresh demo app with the demo ACL applied to a clean registry."""
    from fastapi_apcore.engine.registry import _reset_registry

    acl_path = Path(__file__).resolve().parent.parent / "examples" / "acl_demo" / "acl.yaml"
    monkeypatch.setenv("APCORE_ACL_PATH", str(acl_path))
    _reset_registry()  # drop any singleton Executor built without the ACL

    from examples.acl_demo.app import create_demo_app

    app = create_demo_app()
    try:
        yield TestClient(app)
    finally:
        _reset_registry()


def test_admin_can_delete(client: TestClient) -> None:
    resp = client.delete("/orders/1", headers={"X-Roles": "admin"})
    assert resp.status_code == 200
    assert resp.json() == {"deleted": True}


def test_anonymous_delete_is_denied(client: TestClient) -> None:
    resp = client.delete("/orders/1")
    assert resp.status_code == 403


def test_non_admin_delete_is_denied(client: TestClient) -> None:
    resp = client.delete("/orders/1", headers={"X-Roles": "user"})
    assert resp.status_code == 403


def test_anyone_can_read_orders(client: TestClient) -> None:
    # orders.list is allowed for any caller, including anonymous.
    assert client.get("/orders").status_code == 200
    assert client.get("/orders", headers={"X-Roles": "user"}).status_code == 200
