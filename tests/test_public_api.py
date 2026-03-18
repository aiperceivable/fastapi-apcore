"""Tests for public API exports."""

from __future__ import annotations


class TestPublicAPI:
    def test_version(self) -> None:
        import fastapi_apcore

        assert isinstance(fastapi_apcore.__version__, str)
        assert len(fastapi_apcore.__version__) > 0

    def test_fastapi_apcore_exported(self) -> None:
        from fastapi_apcore import FastAPIApcore

        assert FastAPIApcore is not None

    def test_settings_exported(self) -> None:
        from fastapi_apcore import ApcoreSettings, get_apcore_settings

        assert ApcoreSettings is not None
        assert callable(get_apcore_settings)

    def test_context_factory_exported(self) -> None:
        from fastapi_apcore import FastAPIContextFactory

        assert FastAPIContextFactory is not None

    def test_scanner_exports(self) -> None:
        from fastapi_apcore import BaseScanner, ScannedModule, get_scanner

        assert BaseScanner is not None
        assert ScannedModule is not None
        assert callable(get_scanner)

    def test_apcore_re_exports(self) -> None:
        from fastapi_apcore import (
            ACL,
            Config,
            Context,
            Executor,
            Identity,
            Middleware,
            Registry,
            ModuleAnnotations,
            FunctionModule,
            ModuleExample,
            CancelToken,
            PreflightResult,
            ModuleError,
            ModuleNotFoundError,
        )

        # All should be importable
        assert all(
            [
                ACL,
                Config,
                Context,
                Executor,
                Identity,
                Middleware,
                Registry,
                ModuleAnnotations,
                FunctionModule,
                ModuleExample,
                CancelToken,
                PreflightResult,
                ModuleError,
                ModuleNotFoundError,
            ]
        )

    def test_module_decorator_exported(self) -> None:
        from fastapi_apcore import module

        assert callable(module)
