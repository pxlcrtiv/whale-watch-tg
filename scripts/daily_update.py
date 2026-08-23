#!/usr/bin/env python3
"""
Daily Green — one meaningful, dated commit per day.

Appends a dated entry to this repo's daily log (content drawn from
scripts/tips_pool.json, rotated deterministically by the calendar day),
commits it, and pushes.  Never creates empty commits; idempotent per day;
backfills missed days; pause-able; CI-safe.

Scheduling / fallback (primary -> fallback):
  1. macOS launchd  -> ~/Library/LaunchAgents/com.pxlcrtiv.daily-green.plist
  2. GitHub Actions -> .github/workflows/daily.yml (runs this same script)
  3. Catch-up       -> if days were skipped, the next run emits one commit per
                       missed day (max DAILY_GREEN_BACKFILL_DAYS, default 14),
                       each dated the day it covers, so the contribution graph
                       stays green even after a laptop-off streak.

Customize / pause — see the "Daily Green automation" section in README.md:
  - content pool: add/remove entries in scripts/tips_pool.json
  - pause:        `touch .daily-pause` in the repo root (this repo only)
                  or unload the launchd job (all repos, see README)

Env overrides (testing / ops):
  DAILY_GREEN_SIM_DATE=YYYY-MM-DD   pretend "today" is this date
  DAILY_GREEN_NO_PUSH=1             commit locally, do not push
  DAILY_GREEN_PAUSE=1               skip this run (same as .daily-pause)
  DAILY_GREEN_BACKFILL_DAYS=N       max backfill window (default 14)
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Repo configuration — when copying into another repo, update this block only.
KIND = "tip"                            # log-specific noun ("tip" | "entry")
KIND_LABEL = "Whale tip of the day"
LOG_FILE = "docs/daily-tips.md"         # file entries are appended to
POOL_FILE = "scripts/tips_pool.json"    # content pool (title/body/command)
COMMIT_PREFIX = "docs: daily whale tip"
LOG_HEADER = [
    "# Whale-watching tips of the day",
    "",
    "> Maintained by `scripts/daily_update.py` (Daily Green automation) — one",
    "> dated, non-empty on-chain/whale tip per day, rotated from the pool in",
    "> `scripts/tips_pool.json`. Pause by creating a `.daily-pause` file in the",
    "> repo root, or unload the scheduler job (see README, Daily Green).",
    "",
]
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = REPO_ROOT / LOG_FILE
POOL_PATH = REPO_ROOT / POOL_FILE
BACKFILL_DAYS = int(os.environ.get("DAILY_GREEN_BACKFILL_DAYS", "14"))
EPOCH = dt.date(1970, 1, 1)


def log(msg: str) -> None:
    """Mirror every run line to both stdout and ~/.daily-green/daily-green.log."""
    stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{stamp} {REPO_ROOT.name}: {msg}"
    print(line, flush=True)
    try:
        log_dir = Path.home() / ".daily-green"
        log_dir.mkdir(parents=True, exist_ok=True)
        with open(log_dir / "daily-green.log", "a") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=check,
        capture_output=True,
        text=True,
    )


def today() -> dt.date:
    sim = os.environ.get("DAILY_GREEN_SIM_DATE")
    if sim:
        return dt.date.fromisoformat(sim)
    return dt.date.today()


def first_run_header() -> list[str]:
    return list(LOG_HEADER)


def pool_tip(day: dt.date, pool: list[dict]) -> dict:
    """Deterministic daily rotation: day index into the pool."""
    return pool[(day - EPOCH).days % len(pool)]


def render_entry(day: dt.date, tip: dict) -> list[str]:
    title = tip["title"].strip()
    body = tip["body"].strip().replace("\n", "\n\n")
    cmd = (tip.get("command") or "").strip()
    lines = [f"## {day.isoformat()} — {KIND_LABEL}: {title}", "", body, ""]
    if cmd:
        lines += [f"> `{cmd}`", ""]
    return lines


def existing_dates() -> set[dt.date]:
    if not LOG_PATH.exists():
        return set()
    txt = LOG_PATH.read_text(encoding="utf-8")
    return {dt.date.fromisoformat(m) for m in re.findall(r"^## (\d{4}-\d{2}-\d{2})", txt, re.MULTILINE)}


def plan_days(now: dt.date, have: set[dt.date]) -> list[dt.date]:
    """Days that still need an entry: gap between the newest entry and today,
    plus today itself. Never predates the oldest entry (no retroactive history
    before the automation was installed). Capped at BACKFILL_DAYS."""
    if not have:
        return [now]
    last = max(have)
    if now <= last:
        return []
    gap = [last + dt.timedelta(days=i) for i in range(1, (now - last).days + 1)]
    gap = [d for d in gap if d not in have]
    if len(gap) > BACKFILL_DAYS:
        gap = gap[-BACKFILL_DAYS:]
    return gap


def ensure_git_identity() -> None:
    if git("config", "user.email", check=False).stdout.strip():
        return
    git("config", "user.name", "pxlcrtiv")
    git("config", "user.email", "pxlcrtiv@users.noreply.github.com")


def has_upstream() -> bool:
    return git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}", check=False).returncode == 0


def sync_with_remote() -> None:
    """Rebase local onto the remote before planning so a CI-fallback commit
    from the same day is seen locally (append-only file -> clean rebase)."""
    if not has_upstream():
        return
    git("pull", "--rebase", "--autostash", check=False)


def push_with_retry() -> bool:
    if os.environ.get("DAILY_GREEN_NO_PUSH"):
        return True
    if not has_upstream():
        return True
    for attempt in range(3):
        res = git("push", check=False)
        if res.returncode == 0:
            return True
        if attempt < 2:
            git("pull", "--rebase", "--autostash", check=False)  # remote moved
    return False


def main() -> int:
    if os.environ.get("DAILY_GREEN_PAUSE") or (REPO_ROOT / ".daily-pause").exists():
        log("SKIP — paused (.daily-pause present or DAILY_GREEN_PAUSE=1)")
        return 0

    if not POOL_PATH.exists():
        log(f"ERROR — pool file missing: {POOL_PATH}")
        return 1
    pool = json.loads(POOL_PATH.read_text(encoding="utf-8"))
    if not pool:
        log("ERROR — pool file is empty")
        return 1

    ensure_git_identity()
    if has_upstream():
        sync_with_remote()

    now = today()
    days = plan_days(now, existing_dates())
    if not days:
        log("SKIP — already up to date")
        return 0

    # One commit per day (entry appended just before its commit, so every
    # commit is non-empty), dated that day, so the contribution graph gets a
    # square for every covered date (today's commit uses the real clock).
    if not LOG_PATH.exists():
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        LOG_PATH.write_text("\n".join(first_run_header()) + "\n", encoding="utf-8")
    committed = []
    for day in days:
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write("\n" + "\n".join(render_entry(day, pool_tip(day, pool))) + "\n")
        git("add", LOG_FILE)
        if day == now:
            stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        else:
            stamp = f"{day.isoformat()} 12:00:00"
        env = dict(os.environ, GIT_AUTHOR_DATE=stamp, GIT_COMMITTER_DATE=stamp)
        res = subprocess.run(
            ["git", "commit", "-m", f"{COMMIT_PREFIX} {day.isoformat()}"],
            cwd=REPO_ROOT, check=False, capture_output=True, text=True, env=env,
        )
        if res.returncode != 0:
            log(f"ERROR — commit for {day.isoformat()} failed: {res.stderr.strip()}")
            return 1
        committed.append(day.isoformat())

    if not push_with_retry():
        log(f"ERROR — push failed after retries; commits exist locally: {', '.join(committed)}")
        return 1

    log(f"OK — {len(committed)} commit(s): {', '.join(committed)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())