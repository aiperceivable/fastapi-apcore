"""Tests for FastAPIApcore unified entry point."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi_apcore.client import FastAPIApcore


class TestSingleton:
    def test_get_instance_returns_same(self) -> None:
        FastAPIApcore._reset_instance()
        a = FastAPIApcore.get_instance()
        b = FastAPIApcore.get_instance()
        assert a is b
        FastAPIApcore._reset_instance()

    def test_reset_instance(self) -> None:
        FastAPIApcore._reset_instance()
        a = FastAPIApcore.get_instance()
        FastAPIApcore._reset_instance()
        b = FastAPIApcore.get_instance()
        assert a is not b
        FastAPIApcore._reset_instance()


class TestResolveContext:
    def test_explicit_context_preferred(self) -> None:
        client = FastAPIApcore()
        ctx = MagicMock()
        result = client._resolve_context(request=MagicMock(), context=ctx)
        assert result is ctx

    def test_request_builds_context(self) -> None:
        client = FastAPIApcore()
        req = MagicMock()
        mock_factory = MagicMock()
        mock_factory.create_context.return_value = "built-ctx"
        with patch(
            "fastapi_apcore.engine.registry.get_context_factory",
            return_value=mock_factory,
        ):
            result = client._resolve_context(request=req)
        assert result == "built-ctx"
        mock_factory.create_context.assert_called_once_with(req)

    def test_no_request_no_context_returns_none(self) -> None:
        client = FastAPIApcore()
        assert client._resolve_context() is None


class TestModuleExecution:
    def test_call_delegates(self) -> None:
        client = FastAPIApcore()
        mock_executor = MagicMock()
        mock_executor.call.return_value = {"result": 42}
        with patch(
            "fastapi_apcore.engine.registry.get_executor",
            return_value=mock_executor,
        ):
            result = client.call("math.add", {"a": 1, "b": 2})
        assert result == {"result": 42}
        mock_executor.call.assert_called_once()

    def test_call_defaults_inputs_to_empty(self) -> None:
        client = FastAPIApcore()
        mock_executor = MagicMock()
        mock_executor.call.return_value = {}
        with patch(
            "fastapi_apcore.engine.registry.get_executor",
            return_value=mock_executor,
        ):
            client.call("my.module")
        mock_executor.call.assert_called_once_with("my.module", {}, context=None)


class TestModuleRegistration:
    def test_register_delegates(self) -> None:
        client = FastAPIApcore()
        mock_registry = MagicMock()
        mod_obj = MagicMock()
        with patch(
            "fastapi_apcore.engine.registry.get_registry",
            return_value=mock_registry,
        ):
            client.register("test.mod", mod_obj)
        mock_registry.register.assert_called_once_with("test.mod", mod_obj)

    def test_list_modules_delegates(self) -> None:
        client = FastAPIApcore()
        mock_registry = MagicMock()
        mock_registry.list.return_value = ["a", "b"]
        with patch(
            "fastapi_apcore.engine.registry.get_registry",
            return_value=mock_registry,
        ):
            result = client.list_modules(tags=["math"])
        assert result == ["a", "b"]
        mock_registry.list.assert_called_once_with(tags=["math"], prefix=None)

    def test_describe_delegates(self) -> None:
        client = FastAPIApcore()
        mock_registry = MagicMock()
        mock_registry.describe.return_value = "Adds two numbers"
        with patch(
            "fastapi_apcore.engine.registry.get_registry",
            return_value=mock_registry,
        ):
            result = client.describe("math.add")
        assert result == "Adds two numbers"


class TestScan:
    def test_scan_delegates(self) -> None:
        client = FastAPIApcore()
        mock_scanner = MagicMock()
        mock_scanner.scan.return_value = ["mod1", "mod2"]
        mock_app = MagicMock()
        with patch(
            "fastapi_apcore.scanners.get_scanner",
            return_value=mock_scanner,
        ):
            result = client.scan(mock_app, source="native")
        assert result == ["mod1", "mod2"]
        mock_scanner.scan.assert_called_once_with(mock_app, include=None, exclude=None)
