"""Daily green planner logic: idempotent, backfills missed days, never skips."""

from datetime import date

from scripts.daily_update import plan_days


def test_no_entries_means_today_only():
    assert plan_days(date(2026, 8, 23), set()) == [date(2026, 8, 23)]


def test_up_to_date_means_no_work():
    assert plan_days(date(2026, 8, 23), {date(2026, 8, 23)}) == []
    assert plan_days(date(2026, 8, 23), {date(2026, 8, 25)}) == []  # future entries: nothing


def test_gap_backfills_each_missed_day():
    plan = plan_days(date(2026, 8, 23), {date(2026, 8, 20)})
    assert plan == [date(2026, 8, 21), date(2026, 8, 22), date(2026, 8, 23)]


def test_backfill_is_capped():
    plan = plan_days(date(2026, 9, 1), {date(2026, 1, 1)})
    assert len(plan) == 14  # DAILY_GREEN_BACKFILL_DAYS default
    assert plan[-1] == date(2026, 9, 1)


def test_existing_dates_parses_log(tmp_path, monkeypatch):
    import scripts.daily_update as du

    log = tmp_path / "daily-tips.md"
    log.write_text(
        "# Whalewatch tips\n\n"
        "## 2026-08-21 — Whale tip of the day: X\nbody\n\n"
        "## 2026-08-22 — Whale tip of the day: Y\nbody\n\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(du, "LOG_PATH", log)
    assert du.existing_dates() == {date(2026, 8, 21), date(2026, 8, 22)}
    assert du.existing_dates() == {date(2026, 8, 21), date(2026, 8, 22)}  # idempotent parse