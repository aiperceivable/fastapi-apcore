"""Tests for serializers."""

from __future__ import annotations

from types import SimpleNamespace

from fastapi_apcore.engine.serializers import module_to_dict, modules_to_dicts


def _make_scanned_module(**overrides):
    defaults = {
        "module_id": "items.list.get",
        "description": "List items",
        "input_schema": {"type": "object", "properties": {}},
        "output_schema": {"type": "object"},
        "tags": ["items"],
        "target": "myapp.views:list_items",
        "http_method": "GET",
        "url_path": "/items",
        "version": "1.0.0",
        "annotations": None,
        "documentation": None,
        "metadata": {},
        "warnings": [],
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class TestModuleToDict:
    def test_basic(self):
        mod = _make_scanned_module()
        d = module_to_dict(mod)
        assert d["module_id"] == "items.list.get"
        assert d["http_method"] == "GET"
        assert d["url_path"] == "/items"
        assert "annotations" not in d
        assert "documentation" not in d

    def test_with_documentation(self):
        mod = _make_scanned_module(documentation="Full docs here")
        d = module_to_dict(mod)
        assert d["documentation"] == "Full docs here"

    def test_with_annotations(self):
        from apcore import ModuleAnnotations

        ann = ModuleAnnotations(readonly=True, cacheable=True)
        mod = _make_scanned_module(annotations=ann)
        d = module_to_dict(mod)
        assert "annotations" in d
        assert d["annotations"]["readonly"] is True


class TestModulesToDicts:
    def test_batch(self):
        mods = [_make_scanned_module(module_id=f"m{i}") for i in range(3)]
        result = modules_to_dicts(mods)
        assert len(result) == 3
        assert [r["module_id"] for r in result] == ["m0", "m1", "m2"]
