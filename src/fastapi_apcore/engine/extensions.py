"""Extension adapter layer for apcore.

Implements apcore protocols (Discoverer, ModuleValidator) with FastAPI-specific
logic, and provides setup_extensions() to build a configured ExtensionManager.
"""

from __future__ import annotations

import importlib
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from apcore import (
    MAX_MODULE_ID_LENGTH,
    RESERVED_WORDS,
    ExtensionManager,
)

if TYPE_CHECKING:
    from fastapi_apcore.engine.config import ApcoreSettings

logger = logging.getLogger("fastapi_apcore")


class FastAPIDiscoverer:
    """Discovers apcore modules from FastAPI project structure.

    Implements the apcore Discoverer protocol.

    Discovery sources:
    1. YAML binding files from APCORE_MODULE_DIR matching APCORE_BINDING_PATTERN
    2. @module-decorated functions from module_packages
    """

    def __init__(self, settings: ApcoreSettings) -> None:
        self._settings = settings

    def discover(self, roots: list[str]) -> list[dict[str, Any]]:  # noqa: ARG002
        discovered: list[dict[str, Any]] = []
        module_dir = Path(self._settings.module_dir)
        if module_dir.exists() and module_dir.is_dir():
            discovered.extend(self._load_bindings(module_dir))
        discovered.extend(self._scan_module_packages())
        return discovered

    def _load_bindings(self, module_dir: Path) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        try:
            from apcore import BindingLoader, FunctionModule, Registry

            temp_registry = Registry()
            loader = BindingLoader()
            modules = loader.load_binding_dir(
                str(module_dir),
                temp_registry,
                pattern=self._settings.binding_pattern,
            )
            if modules:
                for fm in modules:
                    fm = self._adapt_module(fm, FunctionModule)
                    results.append({"module_id": fm.module_id, "module": fm})
            logger.info("Discovered %d binding modules from %s", len(results), module_dir)
        except ImportError:
            logger.warning("apcore.BindingLoader not available; skipping binding files")
        except Exception:
            logger.exception("Error loading binding files from %s", module_dir)
        return results

    @staticmethod
    def _adapt_module(fm: Any, function_module_cls: type) -> Any:
        """Apply Pydantic flattening to discovered modules."""
        try:
            from apcore_toolkit import flatten_pydantic_params

            func = fm._func
            flattened = flatten_pydantic_params(func)
            if flattened is not func:
                return function_module_cls(
                    func=flattened,
                    module_id=fm.module_id,
                    description=fm.description,
                    tags=fm.tags,
                    version=fm.version,
                    input_schema=fm.input_schema,
                    output_schema=fm.output_schema,
                )
        except (ImportError, AttributeError):
            pass
        return fm

    def _scan_module_packages(self) -> list[dict[str, Any]]:
        """Scan configured module packages for @module-decorated functions."""
        results: list[dict[str, Any]] = []
        for pkg_path in self._settings.module_packages:
            try:
                module = importlib.import_module(pkg_path)
                for attr_name in dir(module):
                    obj = getattr(module, attr_name)
                    if callable(obj) and hasattr(obj, "apcore_module"):
                        fm = obj.apcore_module  # type: ignore[union-attr]
                        results.append({"module_id": fm.module_id, "module": fm})
            except ImportError:
                continue
            except Exception:
                logger.warning("Error scanning %s", pkg_path, exc_info=True)
        return results


class FastAPIModuleValidator:
    """Validates modules against FastAPI-specific rules.

    Implements the apcore ModuleValidator protocol.
    """

    def __init__(self, extra_validators: list[Any] | None = None) -> None:
        self._extra = extra_validators or []

    def validate(self, module: Any) -> list[str]:
        errors: list[str] = []
        module_id = getattr(module, "module_id", None)
        if module_id is None:
            errors.append("Module has no module_id attribute")
            return errors
        parts = module_id.split(".")
        for part in parts:
            if part in RESERVED_WORDS:
                errors.append(f"Module ID '{module_id}' contains reserved word '{part}'")
        if len(module_id) > MAX_MODULE_ID_LENGTH:
            errors.append(f"Module ID '{module_id}' exceeds max length " f"({len(module_id)} > {MAX_MODULE_ID_LENGTH})")
        for validator in self._extra:
            try:
                extra_errors = validator.validate(module)
                errors.extend(extra_errors)
            except Exception:
                logger.warning("Extra validator %s raised an error", type(validator).__name__, exc_info=True)
        return errors


def setup_extensions(settings: ApcoreSettings) -> ExtensionManager:
    """Build and configure an ExtensionManager from settings."""
    ext_mgr = ExtensionManager()
    ext_mgr.register("discoverer", FastAPIDiscoverer(settings))
    extra_validators = _resolve_extra_validators(settings.module_validators)
    ext_mgr.register("module_validator", FastAPIModuleValidator(extra_validators))
    for mw_path in settings.middlewares:
        mw = _import_and_instantiate(mw_path)
        if mw is not None:
            ext_mgr.register("middleware", mw)
    if settings.acl_path:
        try:
            from apcore import ACL

            acl = ACL.load(settings.acl_path)
            ext_mgr.register("acl", acl)
        except Exception:
            logger.exception("Failed to load ACL from %s", settings.acl_path)
    if settings.tracing:
        exporter = _build_span_exporter(settings.tracing)
        if exporter is not None:
            ext_mgr.register("span_exporter", exporter)
    return ext_mgr


def _resolve_extra_validators(paths: list[str]) -> list[Any]:
    validators = []
    for path in paths:
        v = _import_and_instantiate(path)
        if v is not None:
            validators.append(v)
    return validators


def _import_and_instantiate(dotted_path: str) -> Any | None:
    try:
        module_path, class_name = dotted_path.rsplit(".", 1)
        mod = importlib.import_module(module_path)
        cls = getattr(mod, class_name)
        return cls()
    except Exception:
        logger.warning("Failed to import %s", dotted_path, exc_info=True)
        return None


def _build_span_exporter(config: bool | dict[str, Any]) -> Any | None:
    try:
        if config is True:
            from apcore import StdoutExporter

            return StdoutExporter()
        if isinstance(config, dict):
            exporter_name = config.get("exporter", "stdout")
            if exporter_name == "stdout":
                from apcore import StdoutExporter

                return StdoutExporter()
            if exporter_name == "in_memory":
                from apcore import InMemoryExporter

                return InMemoryExporter()
            if exporter_name == "otlp":
                from apcore import OTLPExporter

                kwargs: dict[str, Any] = {}
                if "otlp_endpoint" in config:
                    kwargs["endpoint"] = config["otlp_endpoint"]
                if "otlp_service_name" in config:
                    kwargs["service_name"] = config["otlp_service_name"]
                return OTLPExporter(**kwargs)
    except ImportError:
        logger.warning("Tracing exporter not available; skipping")
    except Exception:
        logger.exception("Failed to build span exporter")
    return None
