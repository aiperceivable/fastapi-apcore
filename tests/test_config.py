"""Tests for fastapi_apcore.config — ApcoreSettings configuration system."""

from __future__ import annotations

import dataclasses
import json
import os
from unittest import mock

import pytest

from fastapi_apcore.engine.config import get_apcore_settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _clean_env():
    """Return a copy of os.environ with all APCORE_ keys removed."""
    return {k: v for k, v in os.environ.items() if not k.startswith("APCORE_")}


# ---------------------------------------------------------------------------
# Default values
# ---------------------------------------------------------------------------


class TestDefaults:
    """All defaults are correct when no APCORE_ env vars are set."""

    def test_defaults(self):
        with mock.patch.dict(os.environ, _clean_env(), clear=True):
            s = get_apcore_settings()

        assert s.module_dir == "apcore_modules/"
        assert s.auto_discover is True
        assert s.serve_transport == "stdio"
        assert s.serve_host == "127.0.0.1"
        assert s.serve_port == 9090
        assert s.server_name == "apcore-mcp"
        assert s.binding_pattern == "*.binding.yaml"
        assert s.middlewares == []
        assert s.acl_path is None
        assert s.context_factory is None
        assert s.server_version is None
        assert s.executor_config is None
        assert s.validate_inputs is False
        assert s.observability_logging is None
        assert s.tracing is None
        assert s.metrics is None
        assert s.embedded_server is None
        assert s.extensions_dir is None
        assert s.module_validators == []
        assert s.task_max_concurrent == 10
        assert s.task_max_tasks == 1000
        assert s.task_cleanup_age == 3600
        assert s.cancel_default_timeout is None
        assert s.serve_validate_inputs is False
        assert s.serve_metrics is False
        assert s.serve_log_level is None
        assert s.serve_tags is None
        assert s.serve_prefix is None
        assert s.explorer_enabled is False
        assert s.explorer_prefix == "/explorer"
        assert s.explorer_allow_execute is False
        assert s.hot_reload is False
        assert s.hot_reload_paths == []
        assert s.jwt_secret is None
        assert s.jwt_algorithm == "HS256"
        assert s.jwt_audience is None
        assert s.jwt_issuer is None
        assert s.output_formatter is None
        assert s.ai_enhance is False
        assert s.module_packages == []


# ---------------------------------------------------------------------------
# Environment overrides
# ---------------------------------------------------------------------------


class TestEnvOverrides:
    """Environment variables properly override defaults."""

    def test_env_override_string(self):
        env = {**_clean_env(), "APCORE_MODULE_DIR": "custom_modules/"}
        with mock.patch.dict(os.environ, env, clear=True):
            s = get_apcore_settings()
        assert s.module_dir == "custom_modules/"

    def test_env_override_bool(self):
        env = {**_clean_env(), "APCORE_AUTO_DISCOVER": "false"}
        with mock.patch.dict(os.environ, env, clear=True):
            s = get_apcore_settings()
        assert s.auto_discover is False

    def test_env_override_int(self):
        env = {**_clean_env(), "APCORE_SERVE_PORT": "8080"}
        with mock.patch.dict(os.environ, env, clear=True):
            s = get_apcore_settings()
        assert s.serve_port == 8080

    def test_env_override_list(self):
        env = {**_clean_env(), "APCORE_MIDDLEWARES": "a.B,c.D"}
        with mock.patch.dict(os.environ, env, clear=True):
            s = get_apcore_settings()
        assert s.middlewares == ["a.B", "c.D"]

    def test_env_json_executor_config(self):
        config = {"max_workers": 4, "timeout": 30}
        env = {**_clean_env(), "APCORE_EXECUTOR_CONFIG": json.dumps(config)}
        with mock.patch.dict(os.environ, env, clear=True):
            s = get_apcore_settings()
        assert s.executor_config == config


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------


class TestValidationErrors:
    """Invalid values raise ValueError."""

    def test_invalid_transport(self):
        env = {**_clean_env(), "APCORE_SERVE_TRANSPORT": "grpc"}
        with mock.patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="serve_transport"):
                get_apcore_settings()

    def test_invalid_port_range(self):
        env = {**_clean_env(), "APCORE_SERVE_PORT": "0"}
        with mock.patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="serve_port"):
                get_apcore_settings()

    def test_invalid_port_type(self):
        env = {**_clean_env(), "APCORE_SERVE_PORT": "abc"}
        with mock.patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="APCORE_SERVE_PORT"):
                get_apcore_settings()

    def test_server_name_empty(self):
        env = {**_clean_env(), "APCORE_SERVER_NAME": ""}
        with mock.patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="server_name"):
                get_apcore_settings()

    def test_server_name_too_long(self):
        env = {**_clean_env(), "APCORE_SERVER_NAME": "x" * 101}
        with mock.patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="server_name"):
                get_apcore_settings()

    def test_invalid_log_level(self):
        env = {**_clean_env(), "APCORE_SERVE_LOG_LEVEL": "VERBOSE"}
        with mock.patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="serve_log_level"):
                get_apcore_settings()

    def test_explorer_prefix_no_slash(self):
        env = {**_clean_env(), "APCORE_EXPLORER_PREFIX": "explorer"}
        with mock.patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="explorer_prefix"):
                get_apcore_settings()

    def test_task_max_concurrent_zero(self):
        env = {**_clean_env(), "APCORE_TASK_MAX_CONCURRENT": "0"}
        with mock.patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="task_max_concurrent"):
                get_apcore_settings()


# ---------------------------------------------------------------------------
# Frozen dataclass
# ---------------------------------------------------------------------------


class TestFrozen:
    """Settings object is immutable."""

    def test_frozen(self):
        with mock.patch.dict(os.environ, _clean_env(), clear=True):
            s = get_apcore_settings()
        with pytest.raises(dataclasses.FrozenInstanceError):
            s.module_dir = "changed/"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Observability dict validations
# ---------------------------------------------------------------------------


class TestObservabilityDictValidation:
    """Dict-style observability configs are validated."""

    def test_tracing_dict_validation(self):
        bad = json.dumps({"sampling_rate": 2.0})
        env = {**_clean_env(), "APCORE_TRACING": bad}
        with mock.patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="sampling_rate"):
                get_apcore_settings()

    def test_metrics_dict_validation(self):
        bad = json.dumps({"buckets": "not-a-list"})
        env = {**_clean_env(), "APCORE_METRICS": bad}
        with mock.patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="buckets"):
                get_apcore_settings()
