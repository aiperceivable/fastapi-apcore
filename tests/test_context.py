"""Tests for FastAPIContextFactory."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

from fastapi_apcore.engine.context import FastAPIContextFactory


# -- Helpers ----------------------------------------------------------------


def _make_request(
    *,
    user: Any = None,
    has_state: bool = True,
    headers: dict[str, str] | None = None,
    has_headers: bool = True,
) -> SimpleNamespace:
    """Build a minimal fake FastAPI request for testing."""
    request = SimpleNamespace()

    if has_state:
        state = SimpleNamespace()
        if user is not None:
            state.user = user
        request.state = state

    if has_headers and headers is not None:
        request.headers = headers
    elif has_headers:
        request.headers = {}

    if not has_headers:
        # Ensure no headers attribute at all
        if hasattr(request, "headers"):
            del request.headers

    return request


# -- Identity extraction tests ----------------------------------------------


class TestAnonymousIdentity:
    """Cases that should produce an anonymous identity."""

    def test_anonymous_no_state(self) -> None:
        """No request.state attribute produces anonymous identity."""
        factory = FastAPIContextFactory()
        request = SimpleNamespace()  # no .state at all

        with patch("apcore.Context"), patch("apcore.Identity") as mock_id:
            mock_id.return_value = "anon-identity"
            factory.create_context(request)

            mock_id.assert_called_once_with(id="anonymous", type="anonymous")

    def test_anonymous_no_user(self) -> None:
        """request.state exists but has no user attribute produces anonymous."""
        factory = FastAPIContextFactory()
        request = _make_request()  # state with no user

        with patch("apcore.Context"), patch("apcore.Identity") as mock_id:
            mock_id.return_value = "anon-identity"
            factory.create_context(request)

            mock_id.assert_called_once_with(id="anonymous", type="anonymous")

    def test_anonymous_not_authenticated(self) -> None:
        """user.is_authenticated = False produces anonymous."""
        user = SimpleNamespace(is_authenticated=False, id="42")
        factory = FastAPIContextFactory()
        request = _make_request(user=user)

        with patch("apcore.Context"), patch("apcore.Identity") as mock_id:
            mock_id.return_value = "anon-identity"
            factory.create_context(request)

            mock_id.assert_called_once_with(id="anonymous", type="anonymous")


class TestAuthenticatedIdentity:
    """Cases that should produce a real identity."""

    def test_authenticated_user(self) -> None:
        """User with id, roles, and is_staff maps correctly."""
        user = SimpleNamespace(
            id="42",
            roles=["admin", "editor"],
            is_staff=True,
            is_superuser=False,
        )
        factory = FastAPIContextFactory()
        request = _make_request(user=user)

        with patch("apcore.Context"), patch("apcore.Identity") as mock_id:
            mock_id.return_value = "real-identity"
            factory.create_context(request)

            mock_id.assert_called_once_with(
                id="42",
                type="user",
                roles=("admin", "editor"),
                attrs={"is_staff": True, "is_superuser": False},
            )

    def test_user_with_groups(self) -> None:
        """User with groups attribute instead of roles uses groups."""
        user = SimpleNamespace(id="7", groups=["staff", "viewers"])
        factory = FastAPIContextFactory()
        request = _make_request(user=user)

        with patch("apcore.Context"), patch("apcore.Identity") as mock_id:
            mock_id.return_value = "real-identity"
            factory.create_context(request)

            call_kwargs = mock_id.call_args[1]
            assert call_kwargs["roles"] == ("staff", "viewers")

    def test_user_with_scopes(self) -> None:
        """User with scopes attribute (OAuth pattern) uses scopes as roles."""
        user = SimpleNamespace(id="99", scopes=["read", "write"])
        factory = FastAPIContextFactory()
        request = _make_request(user=user)

        with patch("apcore.Context"), patch("apcore.Identity") as mock_id:
            mock_id.return_value = "real-identity"
            factory.create_context(request)

            call_kwargs = mock_id.call_args[1]
            assert call_kwargs["roles"] == ("read", "write")

    def test_roles_preferred_over_groups(self) -> None:
        """When both roles and groups exist, roles takes precedence."""
        user = SimpleNamespace(
            id="1",
            roles=["admin"],
            groups=["staff"],
        )
        factory = FastAPIContextFactory()
        request = _make_request(user=user)

        with patch("apcore.Context"), patch("apcore.Identity") as mock_id:
            mock_id.return_value = "real-identity"
            factory.create_context(request)

            call_kwargs = mock_id.call_args[1]
            assert call_kwargs["roles"] == ("admin",)

    def test_user_id_fallback_pk(self) -> None:
        """User with pk instead of id uses pk."""
        user = SimpleNamespace(pk="pk-123")
        factory = FastAPIContextFactory()
        request = _make_request(user=user)

        with patch("apcore.Context"), patch("apcore.Identity") as mock_id:
            mock_id.return_value = "real-identity"
            factory.create_context(request)

            call_kwargs = mock_id.call_args[1]
            assert call_kwargs["id"] == "pk-123"

    def test_user_id_fallback_sub(self) -> None:
        """User with sub (JWT claim) instead of id uses sub."""
        user = SimpleNamespace(sub="jwt-sub-456")
        factory = FastAPIContextFactory()
        request = _make_request(user=user)

        with patch("apcore.Context"), patch("apcore.Identity") as mock_id:
            mock_id.return_value = "real-identity"
            factory.create_context(request)

            call_kwargs = mock_id.call_args[1]
            assert call_kwargs["id"] == "jwt-sub-456"

    def test_user_no_id_yields_unknown(self) -> None:
        """User with no id/pk/sub yields 'unknown'."""
        user = SimpleNamespace(is_authenticated=True)
        factory = FastAPIContextFactory()
        request = _make_request(user=user)

        with patch("apcore.Context"), patch("apcore.Identity") as mock_id:
            mock_id.return_value = "real-identity"
            factory.create_context(request)

            call_kwargs = mock_id.call_args[1]
            assert call_kwargs["id"] == "unknown"

    def test_custom_user_type(self) -> None:
        """User with a type attribute uses that as identity type."""
        user = SimpleNamespace(id="10", type="service_account")
        factory = FastAPIContextFactory()
        request = _make_request(user=user)

        with patch("apcore.Context"), patch("apcore.Identity") as mock_id:
            mock_id.return_value = "real-identity"
            factory.create_context(request)

            call_kwargs = mock_id.call_args[1]
            assert call_kwargs["type"] == "service_account"

    def test_is_active_included_in_attrs(self) -> None:
        """is_active flag is included in attrs when present."""
        user = SimpleNamespace(id="5", is_active=True)
        factory = FastAPIContextFactory()
        request = _make_request(user=user)

        with patch("apcore.Context"), patch("apcore.Identity") as mock_id:
            mock_id.return_value = "real-identity"
            factory.create_context(request)

            call_kwargs = mock_id.call_args[1]
            assert call_kwargs["attrs"]["is_active"] is True


# -- TraceContext extraction tests ------------------------------------------


class TestTraceParent:
    def test_traceparent_extracted(self) -> None:
        """Valid traceparent header invokes TraceContext.extract."""
        tp_value = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"
        factory = FastAPIContextFactory()
        request = _make_request(headers={"traceparent": tp_value})

        with (
            patch("apcore.Context"),
            patch("apcore.Identity") as mock_id,
            patch("apcore.TraceContext") as mock_tc,
        ):
            mock_id.return_value = "anon-identity"
            mock_tc.extract.return_value = "trace-obj"
            factory.create_context(request)

            mock_tc.extract.assert_called_once_with({"traceparent": tp_value})

    def test_traceparent_missing(self) -> None:
        """No traceparent header yields None trace."""
        factory = FastAPIContextFactory()
        request = _make_request(headers={})

        with patch("apcore.Context") as mock_ctx, patch("apcore.Identity") as mock_id:
            mock_id.return_value = "anon-identity"
            factory.create_context(request)

            # trace_parent should be None
            mock_ctx.create.assert_called_once()
            call_kwargs = mock_ctx.create.call_args[1]
            assert call_kwargs["trace_parent"] is None

    def test_traceparent_invalid(self) -> None:
        """Invalid traceparent does not crash, returns None trace."""
        factory = FastAPIContextFactory()
        request = _make_request(headers={"traceparent": "bad-value"})

        with (
            patch("apcore.Context") as mock_ctx,
            patch("apcore.Identity") as mock_id,
            patch("apcore.TraceContext") as mock_tc,
        ):
            mock_id.return_value = "anon-identity"
            mock_tc.extract.side_effect = ValueError("invalid traceparent")
            factory.create_context(request)

            # Should not propagate the error
            mock_ctx.create.assert_called_once()
            call_kwargs = mock_ctx.create.call_args[1]
            assert call_kwargs["trace_parent"] is None

    def test_no_headers_attribute(self) -> None:
        """Request without headers attribute yields None trace."""
        factory = FastAPIContextFactory()
        request = _make_request(has_headers=False)

        with patch("apcore.Context") as mock_ctx, patch("apcore.Identity") as mock_id:
            mock_id.return_value = "anon-identity"
            factory.create_context(request)

            mock_ctx.create.assert_called_once()
            call_kwargs = mock_ctx.create.call_args[1]
            assert call_kwargs["trace_parent"] is None

    def test_traceparent_import_error(self) -> None:
        """ImportError from apcore.TraceContext yields None trace."""
        factory = FastAPIContextFactory()
        request = _make_request(headers={"traceparent": "00-abc-def-01"})

        # Force ImportError on TraceContext access via mock
        with patch.dict("sys.modules", {"apcore": MagicMock(spec=[])}):
            result = factory._extract_trace_parent(request)
            assert result is None


# -- Integration-style test -------------------------------------------------


class TestCreateContext:
    def test_create_context_wires_identity_and_trace(self) -> None:
        """create_context passes identity and trace_parent to Context.create."""
        user = SimpleNamespace(id="42", roles=["admin"])
        tp_value = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"
        factory = FastAPIContextFactory()
        request = _make_request(user=user, headers={"traceparent": tp_value})

        with (
            patch("apcore.Context") as mock_ctx,
            patch("apcore.Identity") as mock_id,
            patch("apcore.TraceContext") as mock_tc,
        ):
            mock_id.return_value = "the-identity"
            mock_tc.extract.return_value = "the-trace"
            mock_ctx.create.return_value = "the-context"

            result = factory.create_context(request)

            assert result == "the-context"
            mock_ctx.create.assert_called_once_with(
                identity="the-identity",
                trace_parent="the-trace",
            )
