"""Run examples/01_basic.py end-to-end and assert it succeeds.

The example is offline (no Anthropic / Docker), so we execute its real
``main()`` and check behaviour rather than only parsing the file.
"""

import importlib.util
from pathlib import Path

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "01_basic.py"


def _load_main():
    spec = importlib.util.spec_from_file_location("ex01_basic", EXAMPLE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.main


def test_basic_example_returns_zero():
    # Arrange
    main = _load_main()
    # Act
    rc = main()
    # Assert
    assert rc == 0


def test_basic_example_prints_the_question_keys(capsys):
    # Arrange
    main = _load_main()
    # Act
    main()
    out = capsys.readouterr().out
    # Assert
    assert "what_for" in out
