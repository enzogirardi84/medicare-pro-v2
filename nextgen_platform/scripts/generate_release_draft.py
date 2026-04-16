#!/usr/bin/env python3
"""Generate a release draft from docs/RELEASE_TEMPLATE.md plus git metadata and changelog."""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def _repo_root() -> Path:
    # scripts/ -> nextgen_platform/
    return Path(__file__).resolve().parent.parent


def _git_root(nextgen: Path) -> Path:
    return nextgen.parent


def _run_git(cwd: Path, *args: str) -> str:
    out = subprocess.check_output(["git", *args], cwd=cwd, stderr=subprocess.STDOUT)
    return out.decode("utf-8", errors="replace").strip()


def _fill_template(text: str, *, version: str, utc_now: str, git_sha: str) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.rstrip()
        if stripped == "- Version:":
            line = f"- Version: {version}"
        elif stripped == "- Fecha/hora (UTC):":
            line = f"- Fecha/hora (UTC): {utc_now}"
        elif stripped == "- `git_sha` esperado:":
            line = f"- `git_sha` esperado: {git_sha}"
        lines.append(line)
    return "\n".join(lines) + "\n"


def _changelog(repo: Path, compare_from: str | None, max_commits: int) -> str:
    paths = ["nextgen_platform", ".github/workflows", ".github/actions"]
    if compare_from:
        rng = f"{compare_from}..HEAD"
        cmd = ["git", "log", "--oneline", "--no-merges", rng, "--", *paths]
    else:
        cmd = ["git", "log", "--oneline", "--no-merges", f"-n{max_commits}", "--", *paths]
    try:
        return subprocess.check_output(cmd, cwd=repo, stderr=subprocess.STDOUT).decode(
            "utf-8", errors="replace"
        ).strip()
    except subprocess.CalledProcessError:
        cmd2 = ["git", "log", "--oneline", "--no-merges", f"-n{max_commits}"]
        return subprocess.check_output(cmd2, cwd=repo, stderr=subprocess.STDOUT).decode(
            "utf-8", errors="replace"
        ).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default="draft", help="Release label (e.g. 1.2.0)")
    parser.add_argument(
        "--compare-from",
        default="",
        help="Git ref for range (tag or commit). If empty, last N commits touching paths.",
    )
    parser.add_argument(
        "--max-commits",
        type=int,
        default=50,
        help="When --compare-from is empty, how many commits to include.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("release-draft.md"),
        help="Output markdown path.",
    )
    args = parser.parse_args()

    nextgen = _repo_root()
    repo = _git_root(nextgen)
    template = nextgen / "docs" / "RELEASE_TEMPLATE.md"
    if not template.is_file():
        print(f"Missing template: {template}", file=sys.stderr)
        return 1

    utc_now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        git_sha = _run_git(repo, "rev-parse", "HEAD")
    except subprocess.CalledProcessError as e:
        print(e, file=sys.stderr)
        return 1

    body = _fill_template(
        template.read_text(encoding="utf-8"),
        version=args.version,
        utc_now=utc_now,
        git_sha=git_sha,
    )
    compare_from = args.compare_from.strip() or None
    log_text = _changelog(repo, compare_from, args.max_commits)
    range_note = f"`{compare_from}..HEAD`" if compare_from else f"last {args.max_commits} commits (path-filtered)"

    out = body
    out += "\n## Changelog automatico\n\n"
    out += f"_Rango: {range_note}_\n\n"
    out += "```\n"
    out += log_text + ("\n" if log_text else "(sin commits en rango)\n")
    out += "```\n"

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(out, encoding="utf-8")
    print(f"Wrote {args.out.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
