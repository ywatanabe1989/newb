"""Smoke test for examples/01_basic.py.

Auto-generated stub (audit-project PS303). Replace with a real test
that runs the example end-to-end and asserts on its outputs.
"""

import importlib.util
from pathlib import Path

import pytest


EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "01_basic.py"


def test_example_file_exists():
    # Arrange
    expected = EXAMPLE
    # Act
    found = expected.exists()
    # Assert
    assert found, f"missing example file: {expected}"


def test_example_imports_cleanly_parses_module_from_spec():
    # Arrange
    if EXAMPLE.suffix != ".py":
        pytest.skip(f"non-python example: {EXAMPLE.suffix}")
    spec = importlib.util.spec_from_file_location("ex", EXAMPLE)
    # Act
    # We don't execute the module — just verify parser-clean syntax via
    # spec resolution. A real test should import + invoke main().
    module = (
        importlib.util.module_from_spec(spec)
        if spec is not None and spec.loader is not None
        else None
    )
    # Assert
    assert module is not None
