"""Run examples/02_verdict_workflow.py end-to-end and assert it succeeds.

The example is offline — it parses the committed ``tests_newb.yaml``
with newb's own loader and prints the expected verdict JSON. No agent
run, so we execute its real ``main()``.
"""

import importlib.util
from pathlib import Path

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "02_verdict_workflow.py"


def _load_main():
    spec = importlib.util.spec_from_file_location("ex02_verdict", EXAMPLE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.main


def test_verdict_example_returns_zero():
    # Arrange
    main = _load_main()
    # Act
    rc = main()
    # Assert
    assert rc == 0


def test_verdict_example_parses_both_author_tests(capsys):
    # Arrange
    main = _load_main()
    # Act
    main()
    out = capsys.readouterr().out
    # Assert
    assert "parsed 2 author test(s):" in out
