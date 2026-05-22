"""Tests for newb._install._workflow — gh surface injected, not mocked.

Each verb (``secret_exists``, ``workflow_exists``, ``set_secret``,
``scaffold_workflow``, ``install``) accepts a ``gh=`` kwarg; the
default is the real subprocess shim. We pass a hand-rolled
``FakeGh`` that records calls and returns canned output — exposing
only the call surface the production code actually touches.
"""

from __future__ import annotations

from typing import Optional

import pytest

from newb._install import _workflow as iw


class FakeGh:
    """Real callable substitute for ``_workflow._gh``.

    Recording fake: appends every call to ``self.calls``; resolves a
    response by matching the joined ``args`` against the registered
    ``responses`` prefixes. The sentinel ``"__ERROR__"`` raises
    ``iw.GhError`` so tests can exercise the exception path.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[tuple[str, ...], Optional[str]]] = []
        self.responses: dict[str, str] = {}

    def __call__(self, *args: str, input: Optional[str] = None) -> str:
        self.calls.append((args, input))
        for prefix, out in self.responses.items():
            if " ".join(args).startswith(prefix):
                if out == "__ERROR__":
                    raise iw.GhError(f"stubbed error for {prefix}")
                return out
        return ""


@pytest.fixture
def fake_gh() -> FakeGh:
    """Fresh FakeGh per test — call-log isolation."""
    return FakeGh()


def test_secret_exists_true(fake_gh):
    fake_gh.responses["secret list"] = (
        '[{"name": "NEWB_ANTHROPIC_API_KEY"}, {"name": "OTHER"}]'
    )
    assert iw.secret_exists("o/r", gh=fake_gh) is True


def test_secret_exists_false(fake_gh):
    fake_gh.responses["secret list"] = '[{"name": "OTHER"}]'
    assert iw.secret_exists("o/r", gh=fake_gh) is False


def test_secret_exists_handles_gh_error(fake_gh):
    fake_gh.responses["secret list"] = "__ERROR__"
    # Auth/access errors → treat as "doesn't exist".
    assert iw.secret_exists("o/r", gh=fake_gh) is False


def test_workflow_exists_true(fake_gh):
    fake_gh.responses["api /repos"] = "{...}"
    assert iw.workflow_exists("o/r", gh=fake_gh) is True


def test_workflow_exists_false(fake_gh):
    fake_gh.responses["api /repos"] = "__ERROR__"
    assert iw.workflow_exists("o/r", gh=fake_gh) is False


def test_set_secret_skip_when_existing(fake_gh):
    fake_gh.responses["secret list"] = '[{"name": "NEWB_ANTHROPIC_API_KEY"}]'
    assert iw.set_secret("o/r", "v", gh=fake_gh) == "skip-existing"
    # No `secret set` call should have been made.
    set_calls = [c for c in fake_gh.calls if c[0][:2] == ("secret", "set")]
    assert set_calls == []


def test_set_secret_writes_when_absent(fake_gh):
    fake_gh.responses["secret list"] = "[]"
    assert iw.set_secret("o/r", "v", gh=fake_gh) == "set"
    set_calls = [c for c in fake_gh.calls if c[0][:2] == ("secret", "set")]
    assert len(set_calls) == 1
    args = set_calls[0][0]
    assert "NEWB_ANTHROPIC_API_KEY" in args
    assert "--repo" in args and "o/r" in args
    assert "--body" in args and "v" in args


def test_set_secret_force_overwrites(fake_gh):
    fake_gh.responses["secret list"] = '[{"name": "NEWB_ANTHROPIC_API_KEY"}]'
    assert iw.set_secret("o/r", "v", force=True, gh=fake_gh) == "set"


def test_scaffold_workflow_skip_when_existing(fake_gh):
    fake_gh.responses["api /repos"] = "{...}"  # workflow_exists → True
    assert iw.scaffold_workflow("o/r", gh=fake_gh) == "skip-existing"


def test_scaffold_workflow_direct_push(fake_gh):
    fake_gh.responses["api /repos"] = "__ERROR__"  # workflow_exists → False
    # The PUT call should succeed.
    assert iw.scaffold_workflow("o/r", push=True, gh=fake_gh) == "pushed"
    put_calls = [
        c
        for c in fake_gh.calls
        if "PUT" in c[0] and ".github/workflows/newb.yml" in " ".join(c[0])
    ]
    assert len(put_calls) == 1


def test_install_combines_secret_and_workflow(fake_gh):
    fake_gh.responses["secret list"] = "[]"
    fake_gh.responses["api /repos"] = "__ERROR__"
    out = iw.install("o/r", secret_value="v", push=True, gh=fake_gh)
    assert out == {"secret": "set", "workflow": "pushed"}


def test_install_skip_secret_when_no_value(fake_gh):
    fake_gh.responses["api /repos"] = "__ERROR__"
    out = iw.install("o/r", secret_value=None, push=True, gh=fake_gh)
    assert out["secret"] == "skip-no-value"
    # No secret-set call.
    assert not any(c[0][:2] == ("secret", "set") for c in fake_gh.calls)


# EOF
