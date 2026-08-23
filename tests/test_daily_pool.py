"""Daily Green content pool: >= 20 curated tips, deterministic rotation."""

import json
from datetime import date
from pathlib import Path

from scripts.daily_update import pool_tip, render_entry

POOL = json.loads(Path("scripts/tips_pool.json").read_text(encoding="utf-8"))


def test_pool_has_at_least_20_tips():
    assert len(POOL) >= 20


def test_pool_entries_are_unique_and_complete():
    titles = [t["title"].strip() for t in POOL]
    assert len(set(titles)) == len(titles), "duplicate titles"
    for tip in POOL:
        assert tip["title"], "title required"
        assert tip["body"], "body required"
        assert len(tip["body"]) > 60, "tips should carry substance"
        assert "command" in tip


def test_rotation_is_deterministic():
    d = date(2026, 8, 23)
    a = pool_tip(d, POOL)
    b = pool_tip(d, POOL)
    assert a["title"] == b["title"]


def test_adjacent_days_rotate():
    d1 = pool_tip(date(2026, 8, 23), POOL)
    d2 = pool_tip(date(2026, 8, 24), POOL)
    d3 = pool_tip(date(2026, 8, 25), POOL)
    assert len({d1["title"], d2["title"], d3["title"]}) == 3


def test_render_entry_is_dated_markdown():
    lines = render_entry(date(2026, 8, 23), POOL[0])
    assert lines[0] == "## 2026-08-23 — Whale tip of the day: " + POOL[0]["title"]