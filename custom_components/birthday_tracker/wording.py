"""Every human-readable string the integration produces.

Pure functions, no Home Assistant imports, so the wording rules can be tested directly
and there is exactly one place to change how a date is described. The calendar summary,
the sensor attributes and the reminder notification all come from here.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from .const import (
    DEFAULT_TYPE,
    TYPE_BIRTHDAY,
    TYPE_MEMORIAL,
    TYPE_PERSONAL,
    TYPE_WEDDING,
)
from .dates import ordinal, years_counting


def entry_type(entry: dict[str, Any]) -> str:
    """The entry's type, defaulting to birthday for entries stored before types existed."""
    return entry.get("type") or DEFAULT_TYPE


def possessive(name: str) -> str:
    """Alice's, or Chris' when the name already ends in s."""
    return f"{name}'" if name.endswith("s") else f"{name}'s"


def _years_phrase(years: int | None) -> str:
    """'11 years', '1 year', or '' when the year is unknown."""
    if years is None:
        return ""
    return "1 year" if years == 1 else f"{years} years"


def summarise(entry: dict[str, Any], event_date: date) -> str:
    """The calendar line for an entry on a given occurrence.

    Examples, using the house's own entries:
        "Halle Clews' Birthday (11th)"
        "In memory of Fran Pitman (11 years)"
        "Jonny & Alex's Wedding Anniversary (5th)"
        "The day we met"
    """
    name = entry["name"]
    kind = entry_type(entry)
    years = years_counting(entry["date"], event_date)

    if kind == TYPE_MEMORIAL:
        phrase = _years_phrase(years)
        return f"In memory of {name} ({phrase})" if phrase else f"In memory of {name}"

    if kind == TYPE_WEDDING:
        if years:
            return f"{possessive(name)} Wedding Anniversary ({ordinal(years)})"
        return f"{possessive(name)} Wedding Anniversary"

    if kind == TYPE_PERSONAL:
        return name

    if years:
        return f"{possessive(name)} Birthday ({ordinal(years)})"
    return f"{possessive(name)} Birthday"


def notification_title(entry: dict[str, Any]) -> str:
    """Title for a pushed notification, so it does not say Birthday for a memorial."""
    return {
        TYPE_MEMORIAL: "In Memory",
        TYPE_WEDDING: "Anniversary Reminder",
        TYPE_PERSONAL: "Reminder",
    }.get(entry_type(entry), "Birthday Reminder")


def reminder_message(entry: dict[str, Any], days: int, event_date: date) -> str:
    """The sentence that reaches a phone on a reminder day.

    days is days until the date, so 0 is the day itself. Notes are appended by the
    caller, not here.
    """
    name = entry["name"]
    kind = entry_type(entry)
    years = years_counting(entry["date"], event_date)

    if kind == TYPE_MEMORIAL:
        phrase = _years_phrase(years)
        if not phrase:
            if days == 0:
                return f"Remembering {name} today."
            if days == 1:
                return f"Remembering {name} tomorrow."
            return f"Remembering {name} in {days} days."
        if days == 0:
            return f"Today marks {phrase} since {name} passed away."
        if days == 1:
            return f"Tomorrow marks {phrase} since {name} passed away."
        return f"In {days} days it will be {phrase} since {name} passed away."

    if kind == TYPE_WEDDING:
        ordinal_years = f"{ordinal(years)} " if years else ""
        if days == 0:
            return f"Today is {possessive(name)} {ordinal_years}wedding anniversary."
        if days == 1:
            return f"{possessive(name)} {ordinal_years}wedding anniversary is tomorrow."
        return f"{possessive(name)} {ordinal_years}wedding anniversary is in {days} days."

    if kind == TYPE_PERSONAL:
        if days == 0:
            return f"Today: {name}."
        if days == 1:
            return f"Tomorrow: {name}."
        return f"In {days} days: {name}."

    # Birthday is the default.
    if days == 0:
        message = f"Today is {possessive(name)} birthday."
        if years:
            message += f" They are turning {years}."
        return message
    if days == 1:
        message = f"{possessive(name)} birthday is tomorrow."
        if years:
            message += f" They will be turning {years}."
        return message
    message = f"{possessive(name)} birthday is in {days} days."
    if years:
        message += f" They will be turning {years}."
    return message
