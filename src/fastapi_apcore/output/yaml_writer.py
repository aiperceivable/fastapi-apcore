"""YAML writer for fastapi-apcore.

Re-exports apcore-toolkit's YAMLWriter for backwards compatibility.
"""

from apcore_toolkit.output.yaml_writer import YAMLWriter

__all__ = ["YAMLWriter"]
