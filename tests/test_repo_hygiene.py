from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_gitignore_is_text_without_nul_bytes():
    data = (ROOT / ".gitignore").read_bytes()

    assert b"\x00" not in data
    data.decode("utf-8")


def test_sensitive_local_data_files_are_not_tracked():
    result = subprocess.run(
        ["git", "ls-files", "backups/*.json", ".streamlit/data_store/*", ".streamlit/local_data.json"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    assert result.stdout.strip() == ""
