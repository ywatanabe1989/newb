"""Behaviour tests for `newb._env._loader`.

Mirror file for `src/newb/_env/_loader.py` (PS204/PS207). Exercises the
real parsing path against a real ``.src`` file on disk (`tmp_path`) —
no mocks, no import-only theater.
"""

from __future__ import annotations

from newb._env._loader import load_env_from_path, parse_src_file


def test_parse_src_file_reads_a_declared_var(tmp_path):
    # Arrange
    src = tmp_path / "vars.src"
    src.write_text("export NEWB_FOO=bar\n")
    # Act
    parsed = parse_src_file(src)
    # Assert
    assert parsed["NEWB_FOO"] == "bar"


def test_parse_src_file_skips_comments_and_blanks(tmp_path):
    # Arrange
    src = tmp_path / "vars.src"
    src.write_text("# a comment\n\nexport NEWB_ONLY=1\n")
    # Act
    parsed = parse_src_file(src)
    # Assert
    assert parsed == {"NEWB_ONLY": "1"}


def test_load_env_from_path_merges_all_src_files_in_dir(tmp_path):
    # Arrange
    (tmp_path / "01.src").write_text("export A=1\n")
    (tmp_path / "02.src").write_text("export B=2\n")
    # Act
    loaded = load_env_from_path(str(tmp_path))
    # Assert
    assert loaded == {"A": "1", "B": "2"}
