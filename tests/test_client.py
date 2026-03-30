"""Tests for FastAPIApcore unified entry point."""

from __future__ import annotations

import logging

from typing import Any

import pytest
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

    def test_scan_forwards_simplify_ids(self) -> None:
        client = FastAPIApcore()
        mock_scanner = MagicMock()
        mock_scanner.scan.return_value = []
        mock_app = MagicMock()
        with patch(
            "fastapi_apcore.scanners.get_scanner",
            return_value=mock_scanner,
        ) as mock_get:
            client.scan(mock_app, simplify_ids=True)
        mock_get.assert_called_once_with("openapi", simplify_ids=True)


class TestCreateMcpServer:
    def test_raises_value_error_when_scan_true_and_app_none(self) -> None:
        client = FastAPIApcore()
        with patch(
            "fastapi_apcore.client.FastAPIApcore.settings", new_callable=lambda: property(lambda s: MagicMock())
        ):
            with patch.dict("sys.modules", {"apcore_mcp": MagicMock()}):
                with pytest.raises(ValueError, match="app is required when scan=True"):
                    client.create_mcp_server(app=None, scan=True)

    def test_warns_when_no_scan_and_no_extensions_dir(self, caplog: pytest.LogCaptureFixture) -> None:
        client = FastAPIApcore()
        mock_mcp_module = MagicMock()
        with (
            patch("fastapi_apcore.client.FastAPIApcore.settings", new_callable=lambda: property(lambda s: MagicMock())),
            patch.dict("sys.modules", {"apcore_mcp": mock_mcp_module}),
            patch("apcore.Registry"),
            patch("apcore.Executor"),
            caplog.at_level(logging.WARNING, logger="fastapi_apcore"),
        ):
            try:
                client.create_mcp_server(scan=False)
            except Exception:
                pass
            assert "no tools registered" in caplog.text

    def test_scans_and_serves(self) -> None:
        client = FastAPIApcore()
        mock_app = MagicMock()
        mock_scanner = MagicMock()
        mock_scanned = [MagicMock()]
        mock_scanner.scan.return_value = mock_scanned
        mock_writer = MagicMock()
        mock_mcp_serve = MagicMock()

        with (
            patch("fastapi_apcore.client.FastAPIApcore.settings", new_callable=lambda: property(lambda s: MagicMock())),
            patch("fastapi_apcore.scanners.get_scanner", return_value=mock_scanner),
            patch("fastapi_apcore.output.get_writer", return_value=mock_writer),
            patch("apcore.Registry") as MockRegistry,
            patch("apcore.Executor") as MockExecutor,
        ):
            mock_registry = MockRegistry.return_value
            MockExecutor.return_value
            # Patch the import of apcore_mcp.serve
            import sys

            mock_mcp_module = MagicMock()
            mock_mcp_module.serve = mock_mcp_serve
            with patch.dict(sys.modules, {"apcore_mcp": mock_mcp_module}):
                client.create_mcp_server(mock_app, simplify_ids=True)

        mock_scanner.scan.assert_called_once_with(mock_app, include=None, exclude=None)
        mock_writer.write.assert_called_once_with(mock_scanned, mock_registry)
        mock_mcp_serve.assert_called_once()


class TestCreateCli:
    def test_raises_import_error_without_apcore_cli(self) -> None:
        client = FastAPIApcore()
        mock_app = MagicMock()
        with patch.dict("sys.modules", {"click": None, "apcore_cli": None, "apcore_cli.cli": None}):
            with pytest.raises(ImportError, match="apcore-cli is required"):
                client.create_cli(mock_app)

    def test_returns_click_group(self) -> None:
        client = FastAPIApcore()
        mock_app = MagicMock()
        mock_app.title = "TestApp"
        mock_app.version = "1.0.0"

        mock_scanner = MagicMock()
        mock_scanner.scan.return_value = []

        mock_writer = MagicMock()
        mock_writer.write.return_value = []

        with (
            patch("fastapi_apcore.scanners.get_scanner", return_value=mock_scanner),
            patch(
                "apcore_toolkit.output.http_proxy_writer.HTTPProxyRegistryWriter",
                return_value=mock_writer,
            ),
            patch("apcore.Registry"),
            patch("apcore.Executor"),
        ):
            cli = client.create_cli(
                mock_app,
                prog_name="test-cli",
                base_url="http://localhost:9000",
                help_text_max_length=500,
            )

        import click

        assert isinstance(cli, click.BaseCommand)


class TestDisplayOverlayIntegration:
    """Tests for binding_path / DisplayResolver wiring in create_cli and create_mcp_server."""

    def test_create_cli_calls_display_resolver_when_binding_path_given(self, tmp_path) -> None:
        """When binding_path is provided, DisplayResolver.resolve is called before write."""
        client = FastAPIApcore()
        mock_app = MagicMock()
        mock_app.title = "TestApp"
        mock_app.version = "1.0.0"

        mock_scanner = MagicMock()
        scanned = [MagicMock()]
        resolved = [MagicMock()]
        mock_scanner.scan.return_value = scanned

        mock_writer = MagicMock()
        mock_writer.write.return_value = []

        with (
            patch("fastapi_apcore.scanners.get_scanner", return_value=mock_scanner),
            patch("apcore_toolkit.output.http_proxy_writer.HTTPProxyRegistryWriter", return_value=mock_writer),
            patch("apcore.Registry"),
            patch("apcore.Executor"),
            patch("apcore_toolkit.display.DisplayResolver") as MockResolver,
        ):
            MockResolver.return_value.resolve.return_value = resolved
            client.create_cli(mock_app, binding_path=str(tmp_path))

        MockResolver.return_value.resolve.assert_called_once_with(scanned, binding_path=str(tmp_path))
        mock_writer.write.assert_called_once_with(resolved, mock_writer.write.call_args[0][1])

    def test_create_cli_skips_display_resolver_when_no_binding_path(self) -> None:
        """When binding_path is None, DisplayResolver is never called."""
        client = FastAPIApcore()
        mock_app = MagicMock()
        mock_app.title = "TestApp"
        mock_app.version = "1.0.0"

        mock_scanner = MagicMock()
        mock_scanner.scan.return_value = []

        mock_writer = MagicMock()
        mock_writer.write.return_value = []

        with (
            patch("fastapi_apcore.scanners.get_scanner", return_value=mock_scanner),
            patch("apcore_toolkit.output.http_proxy_writer.HTTPProxyRegistryWriter", return_value=mock_writer),
            patch("apcore.Registry"),
            patch("apcore.Executor"),
            patch("apcore_toolkit.display.DisplayResolver") as MockResolver,
        ):
            client.create_cli(mock_app)

        MockResolver.assert_not_called()

    def test_create_mcp_server_calls_display_resolver_when_binding_path_given(self, tmp_path) -> None:
        """When binding_path is provided, DisplayResolver.resolve is called before RegistryWriter.write."""
        client = FastAPIApcore()
        mock_app = MagicMock()
        mock_scanner = MagicMock()
        scanned = [MagicMock()]
        resolved = [MagicMock()]
        mock_scanner.scan.return_value = scanned
        mock_writer = MagicMock()
        mock_mcp_serve = MagicMock()

        import sys

        mock_mcp_module = MagicMock()
        mock_mcp_module.serve = mock_mcp_serve

        with (
            patch("fastapi_apcore.client.FastAPIApcore.settings", new_callable=lambda: property(lambda s: MagicMock())),
            patch("fastapi_apcore.scanners.get_scanner", return_value=mock_scanner),
            patch("fastapi_apcore.output.get_writer", return_value=mock_writer),
            patch("apcore.Registry"),
            patch("apcore.Executor"),
            patch("apcore_toolkit.display.DisplayResolver") as MockResolver,
            patch.dict(sys.modules, {"apcore_mcp": mock_mcp_module}),
        ):
            MockResolver.return_value.resolve.return_value = resolved
            client.create_mcp_server(mock_app, binding_path=str(tmp_path))

        MockResolver.return_value.resolve.assert_called_once_with(scanned, binding_path=str(tmp_path))
        mock_writer.write.assert_called_once_with(resolved, mock_writer.write.call_args[0][1])

    def test_create_mcp_server_skips_display_resolver_when_no_binding_path(self) -> None:
        """When binding_path is None, DisplayResolver is never called."""
        client = FastAPIApcore()
        mock_app = MagicMock()
        mock_scanner = MagicMock()
        mock_scanner.scan.return_value = []
        mock_writer = MagicMock()
        mock_mcp_serve = MagicMock()

        import sys

        mock_mcp_module = MagicMock()
        mock_mcp_module.serve = mock_mcp_serve

        with (
            patch("fastapi_apcore.client.FastAPIApcore.settings", new_callable=lambda: property(lambda s: MagicMock())),
            patch("fastapi_apcore.scanners.get_scanner", return_value=mock_scanner),
            patch("fastapi_apcore.output.get_writer", return_value=mock_writer),
            patch("apcore.Registry"),
            patch("apcore.Executor"),
            patch("apcore_toolkit.display.DisplayResolver") as MockResolver,
            patch.dict(sys.modules, {"apcore_mcp": mock_mcp_module}),
        ):
            client.create_mcp_server(mock_app)

        MockResolver.assert_not_called()


class TestConventionScannerIntegration:
    """Tests for commands_dir / ConventionScanner wiring."""

    def test_create_cli_with_commands_dir(self) -> None:
        """When commands_dir is provided, ConventionScanner is called."""
        client = FastAPIApcore()
        mock_app = MagicMock()
        mock_app.title = "TestApp"
        mock_app.version = "1.0.0"

        mock_scanner = MagicMock()
        mock_scanner.scan.return_value = []

        mock_writer = MagicMock()
        mock_writer.write.return_value = []

        mock_conv_scanner = MagicMock()
        mock_conv_scanner.scan.return_value = []

        with (
            patch("fastapi_apcore.scanners.get_scanner", return_value=mock_scanner),
            patch("apcore_toolkit.output.http_proxy_writer.HTTPProxyRegistryWriter", return_value=mock_writer),
            patch("apcore.Registry"),
            patch("apcore.Executor"),
            patch("apcore_toolkit.convention_scanner.ConventionScanner", return_value=mock_conv_scanner),
        ):
            client.create_cli(mock_app, commands_dir="/tmp/commands")

        mock_conv_scanner.scan.assert_called_once_with("/tmp/commands")

    def test_create_cli_without_commands_dir_skips_convention(self) -> None:
        """When commands_dir is None, ConventionScanner is not called."""
        client = FastAPIApcore()
        mock_app = MagicMock()
        mock_app.title = "TestApp"
        mock_app.version = "1.0.0"

        mock_scanner = MagicMock()
        mock_scanner.scan.return_value = []
        mock_writer = MagicMock()
        mock_writer.write.return_value = []

        with (
            patch("fastapi_apcore.scanners.get_scanner", return_value=mock_scanner),
            patch("apcore_toolkit.output.http_proxy_writer.HTTPProxyRegistryWriter", return_value=mock_writer),
            patch("apcore.Registry"),
            patch("apcore.Executor"),
            patch("apcore_toolkit.convention_scanner.ConventionScanner") as MockConv,
        ):
            client.create_cli(mock_app)

        MockConv.return_value.scan.assert_not_called()

    def test_create_mcp_server_with_commands_dir(self) -> None:
        """When commands_dir is provided in create_mcp_server, ConventionScanner is called."""
        client = FastAPIApcore()
        mock_app = MagicMock()
        mock_app.title = "TestApp"

        mock_scanner = MagicMock()
        mock_scanner.scan.return_value = []

        mock_conv_scanner = MagicMock()
        mock_conv_scanner.scan.return_value = []

        with (
            patch("fastapi_apcore.scanners.get_scanner", return_value=mock_scanner),
            patch("fastapi_apcore.output.get_writer"),
            patch("apcore.Registry"),
            patch("apcore.Executor"),
            patch("apcore_mcp.serve"),
            patch("apcore_toolkit.convention_scanner.ConventionScanner", return_value=mock_conv_scanner),
        ):
            client.create_mcp_server(mock_app, commands_dir="/tmp/commands", transport="stdio")

        mock_conv_scanner.scan.assert_called_once_with("/tmp/commands")

    def test_create_cli_grouped_module_group(self) -> None:
        """create_cli now uses GroupedModuleGroup instead of LazyModuleGroup."""
        client = FastAPIApcore()
        mock_app = MagicMock()
        mock_app.title = "TestApp"
        mock_app.version = "1.0.0"

        mock_scanner = MagicMock()
        mock_scanner.scan.return_value = []
        mock_writer = MagicMock()
        mock_writer.write.return_value = []

        with (
            patch("fastapi_apcore.scanners.get_scanner", return_value=mock_scanner),
            patch("apcore_toolkit.output.http_proxy_writer.HTTPProxyRegistryWriter", return_value=mock_writer),
            patch("apcore.Registry"),
            patch("apcore.Executor"),
        ):
            cli = client.create_cli(mock_app, prog_name="test-cli")

        from apcore_cli.cli import GroupedModuleGroup

        assert isinstance(cli, GroupedModuleGroup)

    def test_create_mcp_server_without_commands_dir_skips_convention(self) -> None:
        """When commands_dir is None in create_mcp_server, ConventionScanner is not called."""
        client = FastAPIApcore()
        mock_app = MagicMock()

        mock_scanner = MagicMock()
        mock_scanner.scan.return_value = []

        with (
            patch("fastapi_apcore.scanners.get_scanner", return_value=mock_scanner),
            patch("fastapi_apcore.output.get_writer"),
            patch("apcore.Registry"),
            patch("apcore.Executor"),
            patch("apcore_mcp.serve"),
            patch("apcore_toolkit.convention_scanner.ConventionScanner") as MockConv,
        ):
            client.create_mcp_server(mock_app, transport="stdio")

        MockConv.return_value.scan.assert_not_called()

    def test_create_mcp_server_commands_dir_only_no_false_warning(self, caplog) -> None:
        """When scan=False + commands_dir set, the 'no tools' warning should NOT fire."""
        client = FastAPIApcore()

        mock_conv = MagicMock()
        mock_conv.scan.return_value = [MagicMock()]

        with (
            patch("apcore.Registry"),
            patch("apcore.Executor"),
            patch("apcore_mcp.serve"),
            patch(
                "fastapi_apcore.client.FastAPIApcore._apply_convention_modules",
            ),
        ):
            with caplog.at_level(logging.WARNING):
                client.create_mcp_server(
                    scan=False,
                    commands_dir="/tmp/commands",
                    transport="stdio",
                )

        assert "no tools registered" not in caplog.text.lower()


class TestCreateCliApCoreCliFeatures:
    """Tests for apcore-cli 0.4.0 features: verbose_help, docs_url, man page support."""

    def _make_cli(self, mock_app: MagicMock, **kwargs: Any) -> Any:
        mock_scanner = MagicMock()
        mock_scanner.scan.return_value = []
        mock_writer = MagicMock()
        mock_writer.write.return_value = []
        with (
            patch("fastapi_apcore.scanners.get_scanner", return_value=mock_scanner),
            patch("apcore_toolkit.output.http_proxy_writer.HTTPProxyRegistryWriter", return_value=mock_writer),
            patch("apcore.Registry"),
            patch("apcore.Executor"),
        ):
            return FastAPIApcore().create_cli(mock_app, **kwargs)

    def _make_app(self) -> MagicMock:
        app = MagicMock()
        app.title = "TestApp"
        app.version = "1.2.3"
        return app

    def test_set_verbose_help_called_with_default_false(self, monkeypatch: Any) -> None:
        """set_verbose_help(False) is called when verbose_help is not passed.

        sys.argv is isolated so a pytest --verbose invocation does not bleed in.
        """
        monkeypatch.setattr("sys.argv", ["pytest"])
        with patch("apcore_cli.cli.set_verbose_help") as mock_svh:
            self._make_cli(self._make_app())
        mock_svh.assert_called_once_with(False)

    def test_set_verbose_help_called_with_true(self, monkeypatch: Any) -> None:
        """set_verbose_help(True) is called when verbose_help=True."""
        monkeypatch.setattr("sys.argv", ["pytest"])
        with patch("apcore_cli.cli.set_verbose_help") as mock_svh:
            self._make_cli(self._make_app(), verbose_help=True)
        mock_svh.assert_called_once_with(True)

    def test_set_verbose_help_from_argv(self, monkeypatch: Any) -> None:
        """--verbose in sys.argv triggers set_verbose_help(True) even without verbose_help=True."""
        monkeypatch.setattr("sys.argv", ["mycli", "--verbose"])
        with patch("apcore_cli.cli.set_verbose_help") as mock_svh:
            self._make_cli(self._make_app())
        mock_svh.assert_called_once_with(True)

    def test_set_docs_url_called_when_provided(self) -> None:
        """set_docs_url is called with the provided URL."""
        with patch("apcore_cli.cli.set_docs_url") as mock_sdu:
            self._make_cli(self._make_app(), docs_url="https://docs.example.com/cli")
        mock_sdu.assert_called_once_with("https://docs.example.com/cli")

    def test_set_docs_url_called_with_none_to_clear(self) -> None:
        """set_docs_url(None) is always called to clear stale state from a prior create_cli() call."""
        with patch("apcore_cli.cli.set_docs_url") as mock_sdu:
            self._make_cli(self._make_app())
        mock_sdu.assert_called_once_with(None)

    def test_configure_man_help_called(self) -> None:
        """configure_man_help is called after all commands are registered."""
        with patch("apcore_cli.shell.configure_man_help") as mock_cmh:
            self._make_cli(self._make_app(), prog_name="myapp", docs_url="https://docs.example.com")
        mock_cmh.assert_called_once()
        _, kwargs = mock_cmh.call_args
        assert kwargs["prog_name"] == "myapp"
        assert kwargs["version"] == "1.2.3"
        assert kwargs["docs_url"] == "https://docs.example.com"

    def test_configure_man_help_called_without_docs_url(self) -> None:
        """configure_man_help is still called even without docs_url."""
        with patch("apcore_cli.shell.configure_man_help") as mock_cmh:
            self._make_cli(self._make_app(), prog_name="myapp")
        mock_cmh.assert_called_once()
        _, kwargs = mock_cmh.call_args
        assert kwargs["docs_url"] is None

    def test_cli_has_verbose_flag(self) -> None:
        """The returned CLI group exposes a --verbose flag (checks user-facing option name)."""
        cli = self._make_cli(self._make_app())
        all_opts = [opt for p in cli.params for opt in getattr(p, "opts", [])]
        assert "--verbose" in all_opts

    def test_cli_has_man_option(self) -> None:
        """configure_man_help adds a --man option to the CLI group (integration check)."""
        # Use the real configure_man_help (not mocked) so we verify it actually
        # mutates cli.params.  The other tests already verify it is called correctly.
        cli = self._make_cli(self._make_app())
        param_names = [p.name for p in cli.params]
        assert "man" in param_names

    def test_configure_man_help_receives_cli_group(self) -> None:
        """configure_man_help is called with the constructed CLI group as first arg."""
        with patch("apcore_cli.shell.configure_man_help") as mock_cmh:
            cli = self._make_cli(self._make_app(), prog_name="myapp")
        args, _ = mock_cmh.call_args
        assert args[0] is cli
