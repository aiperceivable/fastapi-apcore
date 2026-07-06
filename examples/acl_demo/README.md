# FastAPI + apcore ACL demo

Shows how a FastAPI application enforces **apcore Access Control Lists (ACL)**
on apcore module calls made from within request handlers.

## What it demonstrates

- Loading an ACL from YAML via `APCORE_ACL_PATH`.
- Mapping a FastAPI request's authenticated user (`request.state.user`) to an
  apcore `Identity(roles=...)` through `FastAPIContextFactory`.
- Role-based `allow`/`deny` enforced by the Executor before a module runs, with
  denied calls surfacing as `ACLDeniedError` → HTTP 403.

## Files

| File | Purpose |
|------|---------|
| `acl.yaml` | ACL rules: admins may call anything; `orders.list` is public; everything else is denied by `default_effect: deny`. |
| `app.py` | FastAPI app with two ACL-protected modules (`orders.delete`, `orders.list`) and a demo auth dependency. |

## Run it

```bash
# From the repo root. app.py sets APCORE_ACL_PATH to acl.yaml by default.
uvicorn examples.acl_demo.app:app --reload
```

```bash
curl -X DELETE localhost:8000/orders/1                     # 403  (anonymous)
curl -X DELETE localhost:8000/orders/1 -H 'X-Roles: user'  # 403  (authenticated, not admin)
curl -X DELETE localhost:8000/orders/1 -H 'X-Roles: admin' # 200  {"deleted": 1}
curl localhost:8000/orders                                 # 200  (read is public)
```

> The `X-Roles` header is a demo shortcut standing in for real authentication.
> In production, resolve the user from a JWT/session dependency and set
> `request.state.user` there — apcore only needs an object exposing `id` and
> `roles` (or `groups` / `scopes`).

## How the pieces connect

```
HTTP request
  └─ auth dependency sets request.state.user (id, roles)
       └─ route calls apcore.call_async(module_id, inputs, request=request)
            └─ FastAPIContextFactory → Identity(roles=...)
                 └─ Executor checks ACL (first-match-wins on callers/targets/conditions.roles)
                      ├─ allow → module runs
                      └─ deny  → ACLDeniedError → HTTP 403
```

ACL guards **apcore module calls** (the Executor), not raw FastAPI routes — so
the same rules apply whether a module is invoked from a FastAPI handler (as
here), from an MCP client via `serve()`, or from the generated CLI.

## ACL rule format

```yaml
default_effect: deny          # fallback when no rule matches
rules:
  - description: Admins may call any module
    callers: ["*"]            # caller-id glob patterns
    targets: ["*"]            # module-id glob patterns
    effect: allow             # allow | deny
    conditions:               # optional: roles | identity_types | max_call_depth
      roles: ["admin"]
```

See `src/fastapi_apcore/engine/context.py` for how `request.state.user` is
mapped to the `Identity` that `conditions.roles` matches against.

## Test

The end-to-end behavior is covered by `tests/test_acl_demo.py`.
