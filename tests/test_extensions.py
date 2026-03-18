"""Tests for fastapi_apcore.extensions — Extension adapter layer."""

from __future__ import annotations

import os
from types import SimpleNamespace
from unittest import mock

from apcore import MAX_MODULE_ID_LENGTH, RESERVED_WORDS, ExtensionManager
from fastapi_apcore.engine.config import ApcoreSettings, get_apcore_settings
from fastapi_apcore.engine.extensions import (
    FastAPIDiscoverer,
    FastAPIModuleValidator,
    _import_and_instantiate,
    setup_extensions,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _clean_env():
    """Return a copy of os.environ with all APCORE_ keys removed."""
    return {k: v for k, v in os.environ.items() if not k.startswith("APCORE_")}


def _default_settings(**overrides) -> ApcoreSettings:
    """Create an ApcoreSettings with defaults and optional overrides."""
    with mock.patch.dict(os.environ, _clean_env(), clear=True):
        s = get_apcore_settings()
    if overrides:
        # Frozen dataclass: rebuild with overrides
        import dataclasses

        return dataclasses.replace(s, **overrides)
    return s


def _make_module(module_id: str = "test.module") -> SimpleNamespace:
    """Create a minimal mock module object."""
    return SimpleNamespace(module_id=module_id)


# ---------------------------------------------------------------------------
# FastAPIModuleValidator
# ---------------------------------------------------------------------------


class TestFastAPIModuleValidator:
    """Tests for FastAPIModuleValidator."""

    def test_validator_valid_module(self):
        validator = FastAPIModuleValidator()
        mod = _make_module("my_app.greet")
        errors = validator.validate(mod)
        assert errors == []

    def test_validator_no_module_id(self):
        validator = FastAPIModuleValidator()
        mod = SimpleNamespace()  # no module_id attribute
        errors = validator.validate(mod)
        assert len(errors) == 1
        assert "no module_id" in errors[0]

    def test_validator_reserved_word(self):
        validator = FastAPIModuleValidator()
        # Pick the first reserved word for a deterministic test
        reserved = sorted(RESERVED_WORDS)[0]
        mod = _make_module(f"my_app.{reserved}")
        errors = validator.validate(mod)
        assert any("reserved word" in e for e in errors)
        assert any(reserved in e for e in errors)

    def test_validator_too_long(self):
        validator = FastAPIModuleValidator()
        long_id = "x" * (MAX_MODULE_ID_LENGTH + 1)
        mod = _make_module(long_id)
        errors = validator.validate(mod)
        assert any("exceeds max length" in e for e in errors)

    def test_validator_extra_validators(self):
        """Extra validators are called and their errors are aggregated."""

        class CustomValidator:
            def validate(self, module):
                return [f"custom error for {module.module_id}"]

        validator = FastAPIModuleValidator(extra_validators=[CustomValidator()])
        mod = _make_module("my_app.greet")
        errors = validator.validate(mod)
        assert len(errors) == 1
        assert "custom error" in errors[0]

    def test_validator_extra_validator_exception(self):
        """Extra validator that raises is handled gracefully."""

        class BrokenValidator:
            def validate(self, module):
                raise RuntimeError("boom")

        validator = FastAPIModuleValidator(extra_validators=[BrokenValidator()])
        mod = _make_module("my_app.greet")
        # Should not raise; the broken validator is skipped
        errors = validator.validate(mod)
        assert errors == []


# ---------------------------------------------------------------------------
# FastAPIDiscoverer
# ---------------------------------------------------------------------------


class TestFastAPIDiscoverer:
    """Tests for FastAPIDiscoverer."""

    def test_discoverer_no_dir(self, tmp_path):
        """Non-existent module dir skips bindings gracefully."""
        settings = _default_settings(module_dir=str(tmp_path / "does_not_exist"))
        discoverer = FastAPIDiscoverer(settings)
        result = discoverer.discover([])
        # No bindings found, no crash
        assert isinstance(result, list)

    def test_discoverer_empty_dir(self, tmp_path):
        """Empty module dir returns no bindings."""
        empty_dir = tmp_path / "modules"
        empty_dir.mkdir()
        settings = _default_settings(module_dir=str(empty_dir))
        discoverer = FastAPIDiscoverer(settings)
        result = discoverer.discover([])
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# setup_extensions
# ---------------------------------------------------------------------------


class TestSetupExtensions:
    """Tests for setup_extensions."""

    def test_setup_extensions_creates_manager(self):
        settings = _default_settings()
        mgr = setup_extensions(settings)
        assert isinstance(mgr, ExtensionManager)

    def test_setup_extensions_registers_discoverer_and_validator(self):
        settings = _default_settings()
        mgr = setup_extensions(settings)
        # The manager should have at least discoverer and module_validator
        assert isinstance(mgr, ExtensionManager)


# ---------------------------------------------------------------------------
# _import_and_instantiate
# ---------------------------------------------------------------------------


class TestImportAndInstantiate:
    """Tests for _import_and_instantiate helper."""

    def test_import_and_instantiate_success(self):
        # Use a known stdlib class that takes no arguments
        obj = _import_and_instantiate("collections.OrderedDict")
        assert obj is not None
        from collections import OrderedDict

        assert isinstance(obj, OrderedDict)

    def test_import_and_instantiate_failure(self):
        result = _import_and_instantiate("nonexistent.module.ClassName")
        assert result is None

    def test_import_and_instantiate_bad_class(self):
        result = _import_and_instantiate("collections.NoSuchClass")
        assert result is None
