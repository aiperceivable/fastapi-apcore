"""ApcoreSettings configuration system.

Reads configuration from environment variables with APCORE_ prefix
and produces a frozen dataclass with validated settings.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Environment helpers
# ---------------------------------------------------------------------------

_VALID_TRANSPORTS = {"stdio", "streamable-http", "sse"}
_VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


def _env(key: str, default: str) -> str:
    """Read APCORE_{key} from environment with a guaranteed default."""
    return os.environ.get(f"APCORE_{key}", default)


def _env_optional(key: str) -> str | None:
    """Read APCORE_{key} from environment, returning None if unset."""
    return os.environ.get(f"APCORE_{key}")


def _env_bool(key: str, default: bool) -> bool:
    """Read APCORE_{key} as a boolean."""
    val = os.environ.get(f"APCORE_{key}")
    if val is None:
        return default
    return val.lower() in ("1", "true", "yes")


def _env_int(key: str, default: int) -> int:
    """Read APCORE_{key} as an integer."""
    val = os.environ.get(f"APCORE_{key}")
    if val is None:
        return default
    try:
        return int(val)
    except ValueError:
        raise ValueError(f"APCORE_{key} must be an integer, got '{val}'") from None


def _env_list(key: str, default: list[str] | None = None) -> list[str]:
    """Read APCORE_{key} as a comma-separated list of strings."""
    val = os.environ.get(f"APCORE_{key}")
    if val is None:
        return default or []
    return [s.strip() for s in val.split(",") if s.strip()]


def _env_json(key: str) -> dict | None:
    """Read APCORE_{key} as a JSON object."""
    val = os.environ.get(f"APCORE_{key}")
    if val is None:
        return None
    try:
        return json.loads(val)  # type: ignore[no-any-return]
    except (json.JSONDecodeError, ValueError):
        raise ValueError(f"APCORE_{key} must be valid JSON, got '{val}'") from None


# ---------------------------------------------------------------------------
# Observability sub-validators
# ---------------------------------------------------------------------------


def _validate_observability_logging_dict(config: dict) -> None:
    """Validate the observability_logging dict structure."""
    allowed_keys = {"level", "format", "handler", "propagate"}
    unknown = set(config.keys()) - allowed_keys
    if unknown:
        raise ValueError(f"observability_logging contains unknown keys: {sorted(unknown)}")
    if "level" in config and config["level"] not in _VALID_LOG_LEVELS:
        raise ValueError(
            f"observability_logging.level must be one of {sorted(_VALID_LOG_LEVELS)}, " f"got '{config['level']}'"
        )


def _validate_tracing_dict(config: dict) -> None:
    """Validate the tracing dict structure."""
    allowed_keys = {"enabled", "exporter", "endpoint", "sampling_rate", "service_name"}
    unknown = set(config.keys()) - allowed_keys
    if unknown:
        raise ValueError(f"tracing contains unknown keys: {sorted(unknown)}")
    if "sampling_rate" in config:
        rate = config["sampling_rate"]
        if not isinstance(rate, (int, float)) or not (0.0 <= rate <= 1.0):
            raise ValueError(f"tracing.sampling_rate must be a number between 0.0 and 1.0, " f"got {rate!r}")


def _validate_metrics_dict(config: dict) -> None:
    """Validate the metrics dict structure."""
    allowed_keys = {"enabled", "exporter", "endpoint", "buckets", "prefix"}
    unknown = set(config.keys()) - allowed_keys
    if unknown:
        raise ValueError(f"metrics contains unknown keys: {sorted(unknown)}")
    if "buckets" in config:
        buckets = config["buckets"]
        if not isinstance(buckets, list) or not all(isinstance(b, (int, float)) for b in buckets):
            raise ValueError("metrics.buckets must be a list of numbers")


def _validate_embedded_server_dict(config: dict) -> None:
    """Validate the embedded_server dict structure."""
    allowed_keys = {"enabled", "host", "port", "workers"}
    unknown = set(config.keys()) - allowed_keys
    if unknown:
        raise ValueError(f"embedded_server contains unknown keys: {sorted(unknown)}")
    if "port" in config:
        port = config["port"]
        if not isinstance(port, int) or not (1 <= port <= 65535):
            raise ValueError(f"embedded_server.port must be an integer in range 1-65535, " f"got {port!r}")


# ---------------------------------------------------------------------------
# Settings dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ApcoreSettings:
    """Immutable apcore configuration populated from environment variables."""

    module_dir: str = "apcore_modules/"
    auto_discover: bool = True
    serve_transport: str = "stdio"
    serve_host: str = "127.0.0.1"
    serve_port: int = 9090
    server_name: str = "apcore-mcp"
    binding_pattern: str = "*.binding.yaml"
    middlewares: list[str] = field(default_factory=list)
    acl_path: str | None = None
    context_factory: str | None = None
    server_version: str | None = None
    executor_config: dict[str, Any] | None = None
    validate_inputs: bool = False
    observability_logging: bool | dict | None = None
    tracing: bool | dict | None = None
    metrics: bool | dict | None = None
    embedded_server: bool | dict | None = None
    extensions_dir: str | None = None
    module_validators: list[str] = field(default_factory=list)
    task_max_concurrent: int = 10
    task_max_tasks: int = 1000
    task_cleanup_age: int = 3600
    cancel_default_timeout: int | None = None
    serve_validate_inputs: bool = False
    serve_metrics: bool = False
    serve_log_level: str | None = None
    serve_tags: list[str] | None = None
    serve_prefix: str | None = None
    explorer_enabled: bool = False
    explorer_prefix: str = "/explorer"
    explorer_allow_execute: bool = False
    hot_reload: bool = False
    hot_reload_paths: list[str] = field(default_factory=list)
    jwt_secret: str | None = None
    jwt_algorithm: str = "HS256"
    jwt_audience: str | None = None
    jwt_issuer: str | None = None
    output_formatter: str | None = None
    ai_enhance: bool = False
    module_packages: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def _read_observability_field(key: str) -> bool | dict | None:
    """Read an observability-style env var that can be bool or JSON dict."""
    val = os.environ.get(f"APCORE_{key}")
    if val is None:
        return None
    low = val.lower()
    if low in ("1", "true", "yes"):
        return True
    if low in ("0", "false", "no"):
        return False
    try:
        return json.loads(val)
    except (json.JSONDecodeError, ValueError):
        raise ValueError(f"APCORE_{key} must be true/false or valid JSON, got '{val}'") from None


def get_apcore_settings() -> ApcoreSettings:
    """Create and validate an ApcoreSettings instance from the environment."""

    # --- read values -------------------------------------------------------
    serve_transport = _env("SERVE_TRANSPORT", "stdio")
    serve_port_raw = os.environ.get("APCORE_SERVE_PORT")
    if serve_port_raw is not None:
        try:
            serve_port = int(serve_port_raw)
        except (TypeError, ValueError):
            raise ValueError(f"APCORE_SERVE_PORT must be an integer, got '{serve_port_raw}'")
    else:
        serve_port = 9090

    server_name = _env("SERVER_NAME", "apcore-mcp")
    serve_log_level = _env_optional("SERVE_LOG_LEVEL")
    explorer_prefix = _env("EXPLORER_PREFIX", "/explorer")

    task_max_concurrent = _env_int("TASK_MAX_CONCURRENT", 10)
    task_max_tasks = _env_int("TASK_MAX_TASKS", 1000)
    task_cleanup_age = _env_int("TASK_CLEANUP_AGE", 3600)

    cancel_raw = os.environ.get("APCORE_CANCEL_DEFAULT_TIMEOUT")
    cancel_default_timeout: int | None = None
    if cancel_raw is not None:
        try:
            cancel_default_timeout = int(cancel_raw)
        except ValueError:
            raise ValueError(f"APCORE_CANCEL_DEFAULT_TIMEOUT must be an integer, got '{cancel_raw}'") from None

    serve_tags_raw = os.environ.get("APCORE_SERVE_TAGS")
    serve_tags: list[str] | None = None
    if serve_tags_raw is not None:
        serve_tags = [s.strip() for s in serve_tags_raw.split(",") if s.strip()]

    observability_logging = _read_observability_field("OBSERVABILITY_LOGGING")
    tracing = _read_observability_field("TRACING")
    metrics_cfg = _read_observability_field("METRICS")
    embedded_server = _read_observability_field("EMBEDDED_SERVER")

    settings = ApcoreSettings(
        module_dir=_env("MODULE_DIR", "apcore_modules/"),
        auto_discover=_env_bool("AUTO_DISCOVER", True),
        serve_transport=serve_transport,
        serve_host=_env("SERVE_HOST", "127.0.0.1"),
        serve_port=serve_port,
        server_name=server_name,
        binding_pattern=_env("BINDING_PATTERN", "*.binding.yaml"),
        middlewares=_env_list("MIDDLEWARES"),
        acl_path=_env_optional("ACL_PATH"),
        context_factory=_env_optional("CONTEXT_FACTORY"),
        server_version=_env_optional("SERVER_VERSION"),
        executor_config=_env_json("EXECUTOR_CONFIG"),
        validate_inputs=_env_bool("VALIDATE_INPUTS", False),
        observability_logging=observability_logging,
        tracing=tracing,
        metrics=metrics_cfg,
        embedded_server=embedded_server,
        extensions_dir=_env_optional("EXTENSIONS_DIR"),
        module_validators=_env_list("MODULE_VALIDATORS"),
        task_max_concurrent=task_max_concurrent,
        task_max_tasks=task_max_tasks,
        task_cleanup_age=task_cleanup_age,
        cancel_default_timeout=cancel_default_timeout,
        serve_validate_inputs=_env_bool("SERVE_VALIDATE_INPUTS", False),
        serve_metrics=_env_bool("SERVE_METRICS", False),
        serve_log_level=serve_log_level,
        serve_tags=serve_tags,
        serve_prefix=_env_optional("SERVE_PREFIX"),
        explorer_enabled=_env_bool("EXPLORER_ENABLED", False),
        explorer_prefix=explorer_prefix,
        explorer_allow_execute=_env_bool("EXPLORER_ALLOW_EXECUTE", False),
        hot_reload=_env_bool("HOT_RELOAD", False),
        hot_reload_paths=_env_list("HOT_RELOAD_PATHS"),
        jwt_secret=_env_optional("JWT_SECRET"),
        jwt_algorithm=_env("JWT_ALGORITHM", "HS256"),
        jwt_audience=_env_optional("JWT_AUDIENCE"),
        jwt_issuer=_env_optional("JWT_ISSUER"),
        output_formatter=_env_optional("OUTPUT_FORMATTER"),
        ai_enhance=_env_bool("AI_ENHANCE", False),
        module_packages=_env_list("MODULE_PACKAGES"),
    )

    # --- validate ----------------------------------------------------------
    if settings.serve_transport not in _VALID_TRANSPORTS:
        raise ValueError(
            f"serve_transport must be one of {sorted(_VALID_TRANSPORTS)}, " f"got '{settings.serve_transport}'"
        )

    if not (1 <= settings.serve_port <= 65535):
        raise ValueError(f"serve_port must be in range 1-65535, got {settings.serve_port}")

    if not settings.server_name:
        raise ValueError("server_name must not be empty")
    if len(settings.server_name) > 100:
        raise ValueError(f"server_name must be at most 100 characters, " f"got {len(settings.server_name)}")

    if settings.serve_log_level is not None:
        if settings.serve_log_level.upper() not in _VALID_LOG_LEVELS:
            raise ValueError(
                f"serve_log_level must be one of {sorted(_VALID_LOG_LEVELS)}, " f"got '{settings.serve_log_level}'"
            )

    if not settings.explorer_prefix.startswith("/"):
        raise ValueError(f"explorer_prefix must start with '/', got '{settings.explorer_prefix}'")

    if settings.task_max_concurrent <= 0:
        raise ValueError(f"task_max_concurrent must be positive, got {settings.task_max_concurrent}")
    if settings.task_max_tasks <= 0:
        raise ValueError(f"task_max_tasks must be positive, got {settings.task_max_tasks}")
    if settings.task_cleanup_age < 0:
        raise ValueError(f"task_cleanup_age must be non-negative, got {settings.task_cleanup_age}")

    if settings.cancel_default_timeout is not None and settings.cancel_default_timeout <= 0:
        raise ValueError(f"cancel_default_timeout must be positive if set, " f"got {settings.cancel_default_timeout}")

    # Observability dict validations
    if isinstance(settings.observability_logging, dict):
        _validate_observability_logging_dict(settings.observability_logging)
    if isinstance(settings.tracing, dict):
        _validate_tracing_dict(settings.tracing)
    if isinstance(settings.metrics, dict):
        _validate_metrics_dict(settings.metrics)
    if isinstance(settings.embedded_server, dict):
        _validate_embedded_server_dict(settings.embedded_server)

    return settings
