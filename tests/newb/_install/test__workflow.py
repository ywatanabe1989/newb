"""Tests for newb._install_workflow — gh surface mocked."""

from __future__ import annotations

import pytest

from newb._install import _workflow as iw


@pytest.fixture
def fake_gh(monkeypatch):
    """Replace _gh() with a stub that records calls and returns canned output."""
    calls: list[tuple[tuple[str, ...], str | None]] = []
    responses: dict[str, str] = {}

    def stub(*args: str, input: str | None = None) -> str:
        calls.append((args, input))
        # Match by first 2-3 args.
        for prefix, out in responses.items():
            if " ".join(args).startswith(prefix):
                if out == "__ERROR__":
                    raise iw.GhError(f"stubbed error for {prefix}")
                return out
        return ""

    monkeypatch.setattr(iw, "_gh", stub)
    return calls, responses


def test_secret_exists_true(fake_gh):
    calls, responses = fake_gh
    responses["secret list"] = '[{"name": "NEWB_ANTHROPIC_API_KEY"}, {"name": "OTHER"}]'
    assert iw.secret_exists("o/r") is True


def test_secret_exists_false(fake_gh):
    calls, responses = fake_gh
    responses["secret list"] = '[{"name": "OTHER"}]'
    assert iw.secret_exists("o/r") is False


def test_secret_exists_handles_gh_error(fake_gh):
    calls, responses = fake_gh
    responses["secret list"] = "__ERROR__"
    # Auth/access errors → treat as "doesn't exist".
    assert iw.secret_exists("o/r") is False


def test_workflow_exists_true(fake_gh):
    calls, responses = fake_gh
    responses["api /repos"] = "{...}"
    assert iw.workflow_exists("o/r") is True


def test_workflow_exists_false(fake_gh):
    calls, responses = fake_gh
    responses["api /repos"] = "__ERROR__"
    assert iw.workflow_exists("o/r") is False


def test_set_secret_skip_when_existing(fake_gh):
    calls, responses = fake_gh
    responses["secret list"] = '[{"name": "NEWB_ANTHROPIC_API_KEY"}]'
    assert iw.set_secret("o/r", "v") == "skip-existing"
    # No `secret set` call should have been made.
    set_calls = [c for c in calls if c[0][:2] == ("secret", "set")]
    assert set_calls == []


def test_set_secret_writes_when_absent(fake_gh):
    calls, responses = fake_gh
    responses["secret list"] = "[]"
    assert iw.set_secret("o/r", "v") == "set"
    set_calls = [c for c in calls if c[0][:2] == ("secret", "set")]
    assert len(set_calls) == 1
    args = set_calls[0][0]
    assert "NEWB_ANTHROPIC_API_KEY" in args
    assert "--repo" in args and "o/r" in args
    assert "--body" in args and "v" in args


def test_set_secret_force_overwrites(fake_gh):
    calls, responses = fake_gh
    responses["secret list"] = '[{"name": "NEWB_ANTHROPIC_API_KEY"}]'
    assert iw.set_secret("o/r", "v", force=True) == "set"


def test_scaffold_workflow_skip_when_existing(fake_gh):
    calls, responses = fake_gh
    responses["api /repos"] = "{...}"  # workflow_exists → True
    assert iw.scaffold_workflow("o/r") == "skip-existing"


def test_scaffold_workflow_direct_push(fake_gh):
    calls, responses = fake_gh
    responses["api /repos"] = "__ERROR__"  # workflow_exists → False
    # The PUT call should succeed.
    assert iw.scaffold_workflow("o/r", push=True) == "pushed"
    put_calls = [
        c
        for c in calls
        if "PUT" in c[0] and ".github/workflows/newb.yml" in " ".join(c[0])
    ]
    assert len(put_calls) == 1


def test_install_combines_secret_and_workflow(fake_gh):
    calls, responses = fake_gh
    responses["secret list"] = "[]"
    responses["api /repos"] = "__ERROR__"
    out = iw.install("o/r", secret_value="v", push=True)
    assert out == {"secret": "set", "workflow": "pushed"}


def test_install_skip_secret_when_no_value(fake_gh):
    calls, responses = fake_gh
    responses["api /repos"] = "__ERROR__"
    out = iw.install("o/r", secret_value=None, push=True)
    assert out["secret"] == "skip-no-value"
    # No secret-set call.
    assert not any(c[0][:2] == ("secret", "set") for c in calls)


# EOF
