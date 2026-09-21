"""Tests for the pure layers: dates.py and wording.py.

Runs under pytest, or with plain python3 when pytest is not installed:

    python3 tests/test_wording.py

The parent package cannot be imported normally, because
custom_components/birthday_tracker/__init__.py imports Home Assistant, which is not
present on a development box. Registering the package shells in sys.modules first means
Python resolves the submodules without executing that __init__.py.
"""
from __future__ import annotations

import sys
import types
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_DIR = REPO_ROOT / "custom_components" / "birthday_tracker"

if "custom_components" not in sys.modules:
    parent = types.ModuleType("custom_components")
    parent.__path__ = [str(REPO_ROOT / "custom_components")]
    sys.modules["custom_components"] = parent

if "custom_components.birthday_tracker" not in sys.modules:
    package = types.ModuleType("custom_components.birthday_tracker")
    package.__path__ = [str(PACKAGE_DIR)]
    sys.modules["custom_components.birthday_tracker"] = package

from custom_components.birthday_tracker import dates, wording  # noqa: E402
from custom_components.birthday_tracker.const import (  # noqa: E402
    TYPE_BIRTHDAY,
    TYPE_MEMORIAL,
    TYPE_PERSONAL,
    TYPE_WEDDING,
)

TODAY = date(2026, 9, 21)


def entry(name: str, stored: str, kind: str = TYPE_BIRTHDAY) -> dict:
    return {"id": "x", "name": name, "date": stored, "type": kind, "notes": ""}


# --- dates ---------------------------------------------------------------------------

def test_ordinal():
    assert dates.ordinal(1) == "1st"
    assert dates.ordinal(2) == "2nd"
    assert dates.ordinal(3) == "3rd"
    assert dates.ordinal(4) == "4th"
    assert dates.ordinal(11) == "11th"
    assert dates.ordinal(12) == "12th"
    assert dates.ordinal(13) == "13th"
    assert dates.ordinal(21) == "21st"
    assert dates.ordinal(111) == "111th"


def test_display_date():
    assert dates.display_date("1965-07-25") == "25-07-1965"
    assert dates.display_date("0000-11-12") == "12-11"


def test_days_until_this_year_and_next():
    assert dates.days_until("1994-09-30", TODAY) == 9
    # A date that has passed this year rolls to next year.
    assert dates.days_until("0000-09-20", TODAY) == 364
    assert dates.days_until("0000-09-21", TODAY) == 0


def test_leap_day_clamps_in_a_non_leap_year():
    assert dates.next_occurrence("1992-02-29", date(2026, 2, 1)) == date(2026, 2, 28)
    # 2028 is a leap year, so it lands on the 29th again.
    assert dates.next_occurrence("1992-02-29", date(2028, 2, 1)) == date(2028, 2, 29)


def test_years_counting():
    # Fran Pitman died in 2015; 2026 is the 11th anniversary.
    assert dates.years_counting("2015-08-13", date(2026, 8, 13)) == 11
    assert dates.years_counting("0000-08-13", date(2026, 8, 13)) is None
    # Nothing is "0 years" on the day itself, so nothing is displayed.
    assert dates.years_counting("2026-08-13", date(2026, 8, 13)) is None


# --- wording: calendar summaries -----------------------------------------------------

def test_summary_birthday_with_and_without_year():
    assert wording.summarise(entry("Halle Clews", "2015-11-29"), date(2026, 11, 29)) == (
        "Halle Clews' Birthday (11th)"
    )
    assert wording.summarise(entry("Anna-Liisa", "0000-01-11"), date(2027, 1, 11)) == (
        "Anna-Liisa's Birthday"
    )


def test_summary_memorial():
    fran = entry("Fran Pitman", "2015-08-13", TYPE_MEMORIAL)
    assert wording.summarise(fran, date(2026, 8, 13)) == "In memory of Fran Pitman (11 years)"
    assert wording.summarise(fran, date(2027, 8, 13)) == "In memory of Fran Pitman (12 years)"
    no_year = entry("Fran Pitman", "0000-08-13", TYPE_MEMORIAL)
    assert wording.summarise(no_year, date(2026, 8, 13)) == "In memory of Fran Pitman"
    one_year = entry("Fran Pitman", "2015-08-13", TYPE_MEMORIAL)
    assert wording.summarise(one_year, date(2016, 8, 13)) == "In memory of Fran Pitman (1 year)"


def test_summary_wedding():
    couple = entry("Jonny & Alex", "2026-07-12", TYPE_WEDDING)
    assert wording.summarise(couple, date(2031, 7, 12)) == (
        "Jonny & Alex's Wedding Anniversary (5th)"
    )
    no_year = entry("Jonny & Alex", "0000-07-12", TYPE_WEDDING)
    assert wording.summarise(no_year, date(2027, 7, 12)) == "Jonny & Alex's Wedding Anniversary"


def test_summary_personal_is_the_label():
    assert wording.summarise(entry("The day we met", "2024-06-18", TYPE_PERSONAL),
                             date(2027, 6, 18)) == "The day we met"


def test_possessive_handles_a_name_ending_in_s():
    assert wording.possessive("Halle Clews") == "Halle Clews'"
    assert wording.possessive("Alex") == "Alex's"


# --- wording: reminders --------------------------------------------------------------

def test_birthday_reminder_reads_naturally():
    halle = entry("Halle Clews", "2015-11-29")
    assert wording.reminder_message(halle, 0, date(2026, 11, 29)) == (
        "Today is Halle Clews' birthday. They are turning 11."
    )
    assert wording.reminder_message(halle, 1, date(2026, 11, 29)) == (
        "Halle Clews' birthday is tomorrow. They will be turning 11."
    )
    assert wording.reminder_message(halle, 7, date(2026, 11, 29)) == (
        "Halle Clews' birthday is in 7 days. They will be turning 11."
    )


def test_birthday_reminder_without_a_year():
    assert wording.reminder_message(entry("Anna-Liisa", "0000-01-11"), 0, date(2027, 1, 11)) == (
        "Today is Anna-Liisa's birthday."
    )


def test_memorial_reminder():
    fran = entry("Fran Pitman", "2015-08-13", TYPE_MEMORIAL)
    assert wording.reminder_message(fran, 0, date(2026, 8, 13)) == (
        "Today marks 11 years since Fran Pitman passed away."
    )
    assert wording.reminder_message(fran, 1, date(2026, 8, 13)) == (
        "Tomorrow marks 11 years since Fran Pitman passed away."
    )
    assert wording.reminder_message(fran, 7, date(2026, 8, 13)) == (
        "In 7 days it will be 11 years since Fran Pitman passed away."
    )
    no_year = entry("Fran Pitman", "0000-08-13", TYPE_MEMORIAL)
    assert wording.reminder_message(no_year, 0, date(2026, 8, 13)) == (
        "Remembering Fran Pitman today."
    )


def test_wedding_reminder():
    couple = entry("Jonny & Alex", "2026-07-12", TYPE_WEDDING)
    assert wording.reminder_message(couple, 0, date(2031, 7, 12)) == (
        "Today is Jonny & Alex's 5th wedding anniversary."
    )
    assert wording.reminder_message(couple, 1, date(2031, 7, 12)) == (
        "Jonny & Alex's 5th wedding anniversary is tomorrow."
    )
    assert wording.reminder_message(couple, 7, date(2031, 7, 12)) == (
        "Jonny & Alex's 5th wedding anniversary is in 7 days."
    )


def test_personal_reminder():
    day = entry("The day we met", "2024-06-18", TYPE_PERSONAL)
    assert wording.reminder_message(day, 0, date(2027, 6, 18)) == "Today: The day we met."
    assert wording.reminder_message(day, 3, date(2027, 6, 18)) == "In 3 days: The day we met."


def test_notification_titles():
    assert wording.notification_title(entry("A", "0000-01-01")) == "Birthday Reminder"
    assert wording.notification_title(entry("A", "0000-01-01", TYPE_MEMORIAL)) == "In Memory"
    assert wording.notification_title(entry("A", "0000-01-01", TYPE_WEDDING)) == (
        "Anniversary Reminder"
    )
    assert wording.notification_title(entry("A", "0000-01-01", TYPE_PERSONAL)) == "Reminder"


def test_missing_type_is_treated_as_a_birthday():
    legacy = {"id": "x", "name": "Nick Pitman", "date": "1965-07-25", "notes": ""}
    assert wording.entry_type(legacy) == TYPE_BIRTHDAY
    assert wording.summarise(legacy, date(2026, 7, 25)) == "Nick Pitman's Birthday (61st)"


def _run_all() -> int:
    """Minimal runner so the tests work without pytest."""
    failures = 0
    tests = [(name, fn) for name, fn in sorted(globals().items()) if name.startswith("test_")]
    for name, fn in tests:
        try:
            fn()
        except AssertionError as exc:
            failures += 1
            print(f"FAIL  {name}")
            if str(exc):
                print(f"      {exc}")
        else:
            print(f"ok    {name}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(_run_all())
