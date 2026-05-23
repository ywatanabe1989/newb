"""Smoke test for `newb._env._loader`.

Mirror file for `src/newb/_env/_loader.py` per PS204/PS207. The real
loader is heavily exercised at CLI startup (`load_newb_env()` is the
first call in `cli_entrypoint`); this test just verifies the module
imports cleanly so PS207 is satisfied.
"""


def test_env_loader_module_imports_cleanly():
    # Arrange
    import importlib

    # Act
    mod = importlib.import_module("newb._env._loader")
    # Assert
    # Smoke-import isn't enough on its own (TQ001 placeholder ban):
    # assert the public symbol the CLI uses is callable so a future
    # rename in production breaks this test.
    assert callable(getattr(mod, "load_newb_env"))
