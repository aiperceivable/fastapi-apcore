"""FastAPI + apcore ACL demo.

Shows how a FastAPI application enforces apcore Access Control Lists (ACL) on
apcore module calls made from within request handlers.

How it works
------------
1. ``APCORE_ACL_PATH`` points apcore at ``acl.yaml``. On first Executor access,
   fastapi-apcore's ``setup_extensions()`` calls ``ACL.load(path)`` and applies
   it to the Executor (``executor.set_acl(acl)``).
2. A (simulated) auth dependency attaches a user with ``roles`` to
   ``request.state.user``.
3. Each route calls an apcore module via ``apcore.call_async(module_id, ...,
   request=request)``. ``FastAPIContextFactory`` turns ``request.state.user``
   into an apcore ``Identity(roles=...)``.
4. The Executor checks the ACL before running the module. A denied call raises
   ``ACLDeniedError``, which the route maps to HTTP 403.

Run it::

    export APCORE_ACL_PATH=examples/acl_demo/acl.yaml   # optional; app sets a default
    uvicorn examples.acl_demo.app:app --reload

Then::

    curl -X DELETE localhost:8000/orders/1                       # 403 (anonymous)
    curl -X DELETE localhost:8000/orders/1 -H 'X-Roles: user'    # 403 (not admin)
    curl -X DELETE localhost:8000/orders/1 -H 'X-Roles: admin'   # 200
    curl localhost:8000/orders                                   # 200 (read is public)

NOTE: The ``X-Roles`` header is a demo shortcut standing in for real
authentication. In production, resolve the user from a JWT/session dependency
and set ``request.state.user`` there instead.
"""

from __future__ import annotations

import contextlib
import os
from pathlib import Path
from types import SimpleNamespace

from fastapi import Depends, FastAPI, Header, HTTPException, Request

from fastapi_apcore import ACLDeniedError, FastAPIApcore

# Point apcore at this demo's ACL file unless the caller already set one.
os.environ.setdefault("APCORE_ACL_PATH", str(Path(__file__).parent / "acl.yaml"))


def _fake_auth(request: Request, x_roles: str | None = Header(default=None)) -> None:
    """Stand-in for real authentication.

    Reads a comma-separated ``X-Roles`` header and attaches a user object to
    ``request.state.user``. Real apps should do this from a JWT/session
    dependency; the shape (``id`` + ``roles``) is what matters to apcore.
    """
    if x_roles:
        request.state.user = SimpleNamespace(
            id="u1",
            roles=[r.strip() for r in x_roles.split(",") if r.strip()],
            is_authenticated=True,
        )
    # No header -> no user -> FastAPIContextFactory yields an anonymous Identity.


def create_demo_app() -> FastAPI:
    """Build the demo FastAPI app with two ACL-protected apcore modules."""
    apcore = FastAPIApcore()

    # Modules are registered into a process-wide singleton registry. Drop any
    # previous registration so create_demo_app() is idempotent / re-runnable.
    for module_id in ("orders.delete", "orders.list"):
        with contextlib.suppress(Exception):
            apcore.registry.unregister(module_id)

    # Two apcore modules protected by acl.yaml:
    #   orders.delete -> admins only
    #   orders.list   -> public (read)
    @apcore.module(id="orders.delete")
    def delete_order(order_id: int) -> dict:
        return {"deleted": order_id}

    @apcore.module(id="orders.list")
    def list_orders() -> dict:
        return {"orders": [{"id": 1}, {"id": 2}]}

    app = FastAPI(title="fastapi-apcore ACL demo")

    @app.delete("/orders/{order_id}")
    async def delete_order_route(
        order_id: int,
        request: Request,
        _: None = Depends(_fake_auth),
    ) -> dict:
        try:
            return await apcore.call_async("orders.delete", {"order_id": order_id}, request=request)
        except ACLDeniedError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    @app.get("/orders")
    async def list_orders_route(
        request: Request,
        _: None = Depends(_fake_auth),
    ) -> dict:
        try:
            return await apcore.call_async("orders.list", {}, request=request)
        except ACLDeniedError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    return app


app = create_demo_app()
