"""Tests for the external governance policy (fastapi_apcore.governance)."""

from __future__ import annotations

import logging

import pytest
from apcore import ModuleAnnotations

from fastapi_apcore.governance import apply_policy, load_policy
from fastapi_apcore.scanners.base import ScannedModule


def _module(module_id: str, annotations: ModuleAnnotations | None = None) -> ScannedModule:
    return ScannedModule(
        module_id=module_id,
        description="",
        input_schema={},
        output_schema={},
        tags=[],
        target="pkg.mod:fn",
        http_method="POST",
        url_path="/x",
        annotations=annotations,
    )


class TestLoadPolicy:
    def test_missing_file_returns_empty_policy(self, tmp_path) -> None:
        assert load_policy(tmp_path / "nope.yaml") == {}

    def test_loads_yaml_mapping(self, tmp_path) -> None:
        p = tmp_path / "governance.yaml"
        p.write_text("require_approval:\n  - '*delete*'\n")
        assert load_policy(p) == {"require_approval": ["*delete*"]}

    def test_non_mapping_raises(self, tmp_path) -> None:
        p = tmp_path / "bad.yaml"
        p.write_text("- just\n- a\n- list\n")
        with pytest.raises(ValueError, match="must be a mapping"):
            load_policy(p)


class TestApplyPolicy:
    def test_empty_policy_is_noop(self) -> None:
        mods = [_module("orders.delete.delete")]
        assert apply_policy(mods, {}) is mods

    def test_sets_requires_approval_on_match(self) -> None:
        mods = [_module("orders.delete_order.delete", ModuleAnnotations(destructive=True))]
        out = apply_policy(mods, {"require_approval": ["*delete*"]})
        assert out[0].annotations.requires_approval is True
        # unrelated annotation preserved
        assert out[0].annotations.destructive is True

    def test_mark_destructive_on_money_moving_post(self) -> None:
        # A POST /refund is not destructive by inference; policy flags it.
        mods = [_module("orders.refund.post", ModuleAnnotations(destructive=False))]
        out = apply_policy(
            mods,
            {"require_approval": ["*refund*"], "mark_destructive": ["*refund*"]},
        )
        assert out[0].annotations.requires_approval is True
        assert out[0].annotations.destructive is True

    def test_non_matching_module_unchanged(self) -> None:
        original = _module("orders.list.get", ModuleAnnotations(readonly=True))
        out = apply_policy([original], {"require_approval": ["*delete*"]})
        assert out[0] is original

    def test_handles_none_annotations(self) -> None:
        out = apply_policy([_module("orders.delete.delete", None)], {"require_approval": ["*delete*"]})
        assert out[0].annotations.requires_approval is True

    def test_no_double_apply_when_already_set(self) -> None:
        already = _module("orders.delete.delete", ModuleAnnotations(requires_approval=True))
        out = apply_policy([already], {"require_approval": ["*delete*"]})
        # Nothing to change -> same object returned (no needless copy).
        assert out[0] is already

    def test_unknown_keys_warned_and_ignored(self, caplog) -> None:
        with caplog.at_level(logging.WARNING, logger="fastapi_apcore"):
            out = apply_policy([_module("a.b.get")], {"bogus": ["*"]})
        assert out[0].annotations is None
        assert any("unknown keys" in r.message.lower() for r in caplog.records)
