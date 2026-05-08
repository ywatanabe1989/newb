"""Smoke test for `newb._env._loader`.

Mirror file for `src/newb/_env/_loader.py` per PS204/PS207. The real
loader is heavily exercised at CLI startup (`load_newb_env()` is the
first call in `cli_entrypoint`); this test just verifies the module
imports cleanly so PS207 is satisfied.
"""


def test_module_imports():
    import importlib

    importlib.import_module("newb._env._loader")
