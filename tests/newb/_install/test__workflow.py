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


def test_secret_exists_true_when_name_in_list(fake_gh):
    # Arrange
    fake_gh.responses["secret list"] = (
        '[{"name": "NEWB_ANTHROPIC_API_KEY"}, {"name": "OTHER"}]'
    )
    # Act
    out = iw.secret_exists("o/r", gh=fake_gh)
    # Assert
    assert out is True


def test_secret_exists_false_when_name_absent(fake_gh):
    # Arrange
    fake_gh.responses["secret list"] = '[{"name": "OTHER"}]'
    # Act
    out = iw.secret_exists("o/r", gh=fake_gh)
    # Assert
    assert out is False


def test_secret_exists_handles_gh_error_as_false(fake_gh):
    # Arrange
    fake_gh.responses["secret list"] = "__ERROR__"
    # Act
    # Auth/access errors → treat as "doesn't exist".
    out = iw.secret_exists("o/r", gh=fake_gh)
    # Assert
    assert out is False


def test_workflow_exists_true_when_api_succeeds(fake_gh):
    # Arrange
    fake_gh.responses["api /repos"] = "{...}"
    # Act
    out = iw.workflow_exists("o/r", gh=fake_gh)
    # Assert
    assert out is True


def test_workflow_exists_false_when_api_errors(fake_gh):
    # Arrange
    fake_gh.responses["api /repos"] = "__ERROR__"
    # Act
    out = iw.workflow_exists("o/r", gh=fake_gh)
    # Assert
    assert out is False


# ---------------------------------------------------------------------------
# set_secret — split "returns skip-existing" + "made no secret-set call".
# ---------------------------------------------------------------------------


@pytest.fixture
def _set_secret_skip_existing(fake_gh) -> tuple[str, FakeGh]:
    fake_gh.responses["secret list"] = '[{"name": "NEWB_ANTHROPIC_API_KEY"}]'
    status = iw.set_secret("o/r", "v", gh=fake_gh)
    return status, fake_gh


def test_set_secret_skip_existing_returns_status(_set_secret_skip_existing):
    # Arrange
    status, _ = _set_secret_skip_existing
    # Act
    value = status
    # Assert
    assert value == "skip-existing"


def test_set_secret_skip_existing_makes_no_set_call(_set_secret_skip_existing):
    # Arrange
    _, fake = _set_secret_skip_existing
    # Act
    set_calls = [c for c in fake.calls if c[0][:2] == ("secret", "set")]
    # Assert
    assert set_calls == []


# ---------------------------------------------------------------------------
# set_secret writes when absent — multiple verifications.
# ---------------------------------------------------------------------------


@pytest.fixture
def _set_secret_absent_then_write(fake_gh) -> tuple[str, FakeGh]:
    fake_gh.responses["secret list"] = "[]"
    status = iw.set_secret("o/r", "v", gh=fake_gh)
    return status, fake_gh


def test_set_secret_absent_returns_set(_set_secret_absent_then_write):
    # Arrange
    status, _ = _set_secret_absent_then_write
    # Act
    value = status
    # Assert
    assert value == "set"


def test_set_secret_absent_makes_exactly_one_set_call(_set_secret_absent_then_write):
    # Arrange
    _, fake = _set_secret_absent_then_write
    # Act
    set_calls = [c for c in fake.calls if c[0][:2] == ("secret", "set")]
    # Assert
    assert len(set_calls) == 1


def test_set_secret_absent_set_call_includes_secret_name(
    _set_secret_absent_then_write,
):
    # Arrange
    _, fake = _set_secret_absent_then_write
    set_calls = [c for c in fake.calls if c[0][:2] == ("secret", "set")]
    args = set_calls[0][0]
    # Act
    present = "NEWB_ANTHROPIC_API_KEY" in args
    # Assert
    assert present


def test_set_secret_absent_set_call_includes_repo_flag(_set_secret_absent_then_write):
    # Arrange
    _, fake = _set_secret_absent_then_write
    set_calls = [c for c in fake.calls if c[0][:2] == ("secret", "set")]
    args = set_calls[0][0]
    # Act
    has_repo = "--repo" in args and "o/r" in args
    # Assert
    assert has_repo


def test_set_secret_absent_set_call_includes_body_value(_set_secret_absent_then_write):
    # Arrange
    _, fake = _set_secret_absent_then_write
    set_calls = [c for c in fake.calls if c[0][:2] == ("secret", "set")]
    args = set_calls[0][0]
    # Act
    has_body = "--body" in args and "v" in args
    # Assert
    assert has_body


def test_set_secret_force_overwrites_existing(fake_gh):
    # Arrange
    fake_gh.responses["secret list"] = '[{"name": "NEWB_ANTHROPIC_API_KEY"}]'
    # Act
    out = iw.set_secret("o/r", "v", force=True, gh=fake_gh)
    # Assert
    assert out == "set"


def test_scaffold_workflow_skip_when_existing(fake_gh):
    # Arrange
    fake_gh.responses["api /repos"] = "{...}"  # workflow_exists → True
    # Act
    out = iw.scaffold_workflow("o/r", gh=fake_gh)
    # Assert
    assert out == "skip-existing"


# ---------------------------------------------------------------------------
# scaffold_workflow direct-push: returns "pushed" + exactly one PUT call.
# ---------------------------------------------------------------------------


@pytest.fixture
def _scaffold_direct_push(fake_gh) -> tuple[str, FakeGh]:
    fake_gh.responses["api /repos"] = "__ERROR__"  # workflow_exists → False
    status = iw.scaffold_workflow("o/r", push=True, gh=fake_gh)
    return status, fake_gh


def test_scaffold_workflow_direct_push_returns_pushed(_scaffold_direct_push):
    # Arrange
    status, _ = _scaffold_direct_push
    # Act
    value = status
    # Assert
    assert value == "pushed"


def test_scaffold_workflow_direct_push_calls_put_exactly_once(_scaffold_direct_push):
    # Arrange
    _, fake = _scaffold_direct_push
    # Act
    put_calls = [
        c
        for c in fake.calls
        if "PUT" in c[0] and ".github/workflows/newb.yml" in " ".join(c[0])
    ]
    # Assert
    assert len(put_calls) == 1


def test_install_combines_secret_and_workflow(fake_gh):
    # Arrange
    fake_gh.responses["secret list"] = "[]"
    fake_gh.responses["api /repos"] = "__ERROR__"
    # Act
    out = iw.install("o/r", secret_value="v", push=True, gh=fake_gh)
    # Assert
    assert out == {"secret": "set", "workflow": "pushed"}


# ---------------------------------------------------------------------------
# install skip-secret path — returns "skip-no-value" + no secret-set call.
# ---------------------------------------------------------------------------


@pytest.fixture
def _install_no_secret_value(fake_gh) -> tuple[dict, FakeGh]:
    fake_gh.responses["api /repos"] = "__ERROR__"
    out = iw.install("o/r", secret_value=None, push=True, gh=fake_gh)
    return out, fake_gh


def test_install_skip_secret_returns_skip_no_value(_install_no_secret_value):
    # Arrange
    out, _ = _install_no_secret_value
    # Act
    value = out["secret"]
    # Assert
    assert value == "skip-no-value"


def test_install_skip_secret_makes_no_set_call(_install_no_secret_value):
    # Arrange
    _, fake = _install_no_secret_value
    # Act
    set_calls = [c for c in fake.calls if c[0][:2] == ("secret", "set")]
    # Assert
    assert set_calls == []


# EOF
