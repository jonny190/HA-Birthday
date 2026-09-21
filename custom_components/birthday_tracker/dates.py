"""Pure date arithmetic for Birthday Tracker.

No Home Assistant imports live here on purpose: these rules can be tested on their own,
and the same function is used by the calendar, the sensors and the reminder scheduler
rather than being written out three times.
"""
from __future__ import annotations

from datetime import date

# A stored year of 0000 means "the year is not known", e.g. a birthday recorded as 12-11.
NO_YEAR: int = 0


def parse_stored(stored: str) -> tuple[int, int, int]:
    """Split an internal YYYY-MM-DD (or 0000-MM-DD) into year, month, day."""
    year, month, day = (int(part) for part in stored.split("-"))
    return year, month, day


def _safe_date(year: int, month: int, day: int) -> date:
    """Build a date, clamping 29 February to the 28th in a non-leap year."""
    try:
        return date(year, month, day)
    except ValueError:
        return date(year, month, 28)


def next_occurrence(stored: str, today: date) -> date:
    """Return the next time this date comes round, today included."""
    _, month, day = parse_stored(stored)
    this_year = _safe_date(today.year, month, day)
    if this_year < today:
        return _safe_date(today.year + 1, month, day)
    return this_year


def days_until(stored: str, today: date) -> int:
    """Days from today until the next occurrence."""
    return (next_occurrence(stored, today) - today).days


def years_counting(stored: str, event_date: date) -> int | None:
    """Years being counted on event_date.

    An age on a birthday, years married on a wedding anniversary, or years since a
    passing on a memorial. Returns None when the stored year is unknown, and None rather
    than 0 when the counted number would be zero.
    """
    year, _, _ = parse_stored(stored)
    if year == NO_YEAR:
        return None
    years = event_date.year - year
    return years if years > 0 else None


def ordinal(n: int) -> str:
    """1 -> 1st, 2 -> 2nd, 11 -> 11th, 111 -> 111th."""
    if 11 <= (n % 100) <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def display_date(stored: str) -> str:
    """Internal YYYY-MM-DD to DD-MM-YYYY, or DD-MM when the year is unknown."""
    year, month, day = parse_stored(stored)
    if year == NO_YEAR:
        return f"{day:02d}-{month:02d}"
    return f"{day:02d}-{month:02d}-{year:04d}"
