"""External governance policy for scanned modules.

Behavioral annotations inferred from HTTP method (``GET`` -> readonly,
``DELETE`` -> destructive) never set ``requires_approval`` -- and a money-moving
``POST`` (e.g. ``/refund``) is not even flagged destructive. Deciding *what needs
human approval* is a governance choice, not something a heuristic can infer.

This module lets an operator declare that choice in an **external policy file**,
applied to scanned modules **without touching the target application's source**
(the outside-in governance model). A policy is a mapping::

    # governance.yaml
    require_approval:      # module_id glob patterns -> requires_approval=True
      - "*delete*"
      - "*refund*"
    mark_destructive:      # module_id glob patterns -> destructive=True (optional)
      - "*refund*"

Patterns are matched against each module's ``module_id`` with :func:`fnmatch.fnmatch`.
"""

from __future__ import annotations

import dataclasses
import logging
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from apcore import ModuleAnnotations

logger = logging.getLogger("fastapi_apcore")

# Modules are typed ``Any``: fastapi-apcore's local ``scanners.base.ScannedModule``
# and the canonical ``apcore_toolkit.types.ScannedModule`` have drifted into two
# distinct dataclasses. Policy application is duck-typed on the ``module_id`` and
# ``annotations`` fields, which both variants share.

_PATTERN_KEYS = ("require_approval", "mark_destructive")


def load_policy(path: str | Path) -> dict[str, Any]:
    """Load a governance policy from a YAML file.

    Returns an empty policy (no-op) if the path does not exist so callers can
    pass a conventional default path unconditionally.
    """
    p = Path(path)
    if not p.exists():
        logger.warning("Governance policy not found at %s; no rules applied.", p)
        return {}
    import yaml

    data = yaml.safe_load(p.read_text()) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Governance policy at {p} must be a mapping, got {type(data).__name__}.")
    return data


def _matches(module_id: str, patterns: Any) -> bool:
    if not isinstance(patterns, (list, tuple)):
        return False
    return any(isinstance(pat, str) and fnmatch(module_id, pat) for pat in patterns)


def apply_policy(modules: list[Any], policy: dict[str, Any]) -> list[Any]:
    """Return ``modules`` with annotations updated per ``policy``.

    Sets ``requires_approval=True`` on modules whose ``module_id`` matches any
    ``require_approval`` pattern, and ``destructive=True`` for ``mark_destructive``.
    Modules that match nothing are returned unchanged. Emits an INFO line per
    change so the governance decision is auditable at startup.
    """
    if not policy:
        return modules

    require_approval = policy.get("require_approval")
    mark_destructive = policy.get("mark_destructive")
    unknown = [k for k in policy if k not in _PATTERN_KEYS]
    if unknown:
        logger.warning("Governance policy: ignoring unknown keys %s", unknown)

    result: list[Any] = []
    for mod in modules:
        needs_approval = _matches(mod.module_id, require_approval)
        make_destructive = _matches(mod.module_id, mark_destructive)
        if not (needs_approval or make_destructive):
            result.append(mod)
            continue

        base = mod.annotations if isinstance(mod.annotations, ModuleAnnotations) else ModuleAnnotations()
        changes: dict[str, bool] = {}
        if needs_approval and not base.requires_approval:
            changes["requires_approval"] = True
        if make_destructive and not base.destructive:
            changes["destructive"] = True
        if not changes:
            result.append(mod)
            continue

        new_ann = dataclasses.replace(base, **changes)
        result.append(dataclasses.replace(mod, annotations=new_ann))
        logger.info("Governance: %s -> %s", mod.module_id, ", ".join(f"{k}=True" for k in changes))

    return result
