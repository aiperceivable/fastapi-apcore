"""Observability auto-setup for fastapi-apcore.

Reads ApcoreSettings and creates tracing, metrics, and logging middleware
instances. Called during init to populate observability middleware.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastapi_apcore.engine.config import ApcoreSettings

logger = logging.getLogger("fastapi_apcore")


def setup_observability(settings: ApcoreSettings, ext_data: dict[str, Any]) -> None:
    """Configure observability middleware from settings.

    Inspects settings.tracing, settings.metrics, and
    settings.observability_logging to create appropriate middleware.

    Results stored in ext_data:
    - ext_data["observability_middlewares"]: list of middleware instances
    - ext_data["metrics_collector"]: MetricsCollector instance (or None)
    """
    middlewares: list[Any] = []
    metrics_collector = None

    # Tracing
    tracing = settings.tracing
    if tracing:
        from apcore.observability.tracing import TracingMiddleware

        from fastapi_apcore.engine.extensions import _build_span_exporter

        exporter = _build_span_exporter(tracing)
        if exporter is not None:
            tracing_mw = TracingMiddleware(exporter=exporter)
            middlewares.append(tracing_mw)
            logger.debug("Observability: tracing enabled")

    # Metrics
    metrics = settings.metrics
    if metrics:
        from apcore.observability.metrics import MetricsCollector, MetricsMiddleware

        if isinstance(metrics, dict) and "buckets" in metrics:
            metrics_collector = MetricsCollector(buckets=metrics["buckets"])
        else:
            metrics_collector = MetricsCollector()

        metrics_mw = MetricsMiddleware(collector=metrics_collector)
        middlewares.append(metrics_mw)
        logger.debug("Observability: metrics enabled")

    # Logging
    obs_logging = settings.observability_logging
    if obs_logging:
        from apcore.observability.context_logger import ContextLogger, ObsLoggingMiddleware

        log_kwargs: dict[str, Any] = {"name": "apcore.obs_logging"}
        if isinstance(obs_logging, dict):
            if "format" in obs_logging:
                log_kwargs["output_format"] = obs_logging["format"]
            if "level" in obs_logging:
                log_kwargs["level"] = obs_logging["level"]

        obs_logger = ContextLogger(**log_kwargs)
        logging_mw = ObsLoggingMiddleware(logger=obs_logger)
        middlewares.append(logging_mw)
        logger.debug("Observability: logging enabled")

    # Error History (if any observability is enabled)
    if tracing or metrics or obs_logging:
        from apcore.observability import ErrorHistory
        from apcore.middleware import ErrorHistoryMiddleware

        error_history = ErrorHistory()
        error_history_mw = ErrorHistoryMiddleware(error_history=error_history)
        middlewares.append(error_history_mw)
        ext_data["error_history"] = error_history
        logger.debug("Observability: error history enabled")

    # Usage Tracking
    if metrics:
        from apcore.observability import UsageCollector, UsageMiddleware

        usage_collector = UsageCollector()
        usage_mw = UsageMiddleware(collector=usage_collector)
        middlewares.append(usage_mw)
        ext_data["usage_collector"] = usage_collector
        logger.debug("Observability: usage tracking enabled")

    ext_data["observability_middlewares"] = middlewares
    ext_data["metrics_collector"] = metrics_collector
