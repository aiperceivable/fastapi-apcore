"""FastAPI context factory for apcore.

Creates apcore Context objects from FastAPI/Starlette requests,
extracting identity and W3C TraceContext (traceparent header).
"""

from __future__ import annotations

from typing import Any


class FastAPIContextFactory:
    """Creates apcore Context from FastAPI/Starlette requests.

    Implements the apcore ContextFactory protocol.
    Supports W3C TraceContext (traceparent header) extraction.
    """

    def create_context(self, request: Any) -> Any:
        """Build an apcore Context from a FastAPI request.

        Args:
            request: A FastAPI/Starlette Request object.

        Returns:
            An apcore Context populated with identity and trace information.
        """
        from apcore import Context

        identity = self._extract_identity(request)
        trace_parent = self._extract_trace_parent(request)
        return Context.create(identity=identity, trace_parent=trace_parent)

    def _extract_identity(self, request: Any) -> Any:
        """Extract an apcore Identity from the request.

        FastAPI convention: authentication middleware or dependencies set
        ``request.state.user``.  This method reads that attribute and maps
        it to an apcore Identity with id, type, roles, and attrs.

        Args:
            request: A FastAPI/Starlette Request object.

        Returns:
            An apcore Identity (anonymous when no authenticated user is found).
        """
        from apcore import Identity

        # FastAPI common pattern: user set on request.state by auth middleware/dependency
        state = getattr(request, "state", None)
        user = getattr(state, "user", None) if state else None

        if user is None:
            return Identity(id="anonymous", type="anonymous")

        # Check if authenticated (default True when attr missing — presence implies auth)
        if not getattr(user, "is_authenticated", True):
            return Identity(id="anonymous", type="anonymous")

        # Extract user ID with fallback chain: id -> pk -> sub
        user_id = str(getattr(user, "id", None) or getattr(user, "pk", None) or getattr(user, "sub", None) or "unknown")

        # Extract roles from first available attribute
        roles: tuple[str, ...] = ()
        for attr in ("roles", "groups", "scopes"):
            val = getattr(user, attr, None)
            if val is not None:
                if isinstance(val, (list, tuple, set, frozenset)):
                    roles = tuple(str(r) for r in val)
                    break

        # Extract boolean/flag attrs
        attrs: dict[str, Any] = {}
        for attr_name in ("is_staff", "is_superuser", "is_active"):
            val = getattr(user, attr_name, None)
            if val is not None:
                attrs[attr_name] = val

        # Determine user type
        user_type = str(getattr(user, "type", "user"))

        return Identity(id=user_id, type=user_type, roles=roles, attrs=attrs)

    def _extract_trace_parent(self, request: Any) -> Any:
        """Extract W3C traceparent from request headers.

        Args:
            request: A FastAPI/Starlette Request object.

        Returns:
            An apcore TraceContext or None if header is absent or invalid.
        """
        headers = getattr(request, "headers", None)
        if headers is None:
            return None

        traceparent = headers.get("traceparent", "")
        if not traceparent:
            return None

        try:
            from apcore import TraceContext

            return TraceContext.extract({"traceparent": traceparent})
        except (ImportError, ValueError):
            return None
