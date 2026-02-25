"""The Birthday Tracker integration."""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_AGE_TURNING,
    ATTR_AGE_TURNING_ORDINAL,
    ATTR_BIRTHDAY_ID,
    ATTR_DATE,
    ATTR_DAYS_UNTIL,
    ATTR_NAME,
    ATTR_NOTES,
    ATTR_REMINDER_DAYS,
    CONF_DEFAULT_REMINDER_DAYS,
    CONF_NOTIFICATION_TIME,
    DEFAULT_NOTIFICATION_TIME,
    DEFAULT_REMINDER_DAYS,
    DOMAIN,
    EVENT_BIRTHDAY_REMINDER,
    EVENT_BIRTHDAYS_UPDATED,
    PLATFORMS,
    SERVICE_ADD_BIRTHDAY,
    SERVICE_EDIT_BIRTHDAY,
    SERVICE_LIST_BIRTHDAYS,
    SERVICE_REMOVE_BIRTHDAY,
)
from .store import BirthdayStore

_LOGGER = logging.getLogger(__name__)

SERVICE_ADD_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_NAME): cv.string,
        vol.Required(ATTR_DATE): cv.string,
        vol.Optional(ATTR_REMINDER_DAYS): cv.string,
        vol.Optional(ATTR_NOTES, default=""): cv.string,
    }
)

SERVICE_REMOVE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_BIRTHDAY_ID): cv.string,
    }
)

SERVICE_EDIT_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_BIRTHDAY_ID): cv.string,
        vol.Optional(ATTR_NAME): cv.string,
        vol.Optional(ATTR_DATE): cv.string,
        vol.Optional(ATTR_REMINDER_DAYS): cv.string,
        vol.Optional(ATTR_NOTES): cv.string,
    }
)


def _ordinal(n: int) -> str:
    """Convert an integer to an ordinal string (1st, 2nd, 3rd, 11th, etc.)."""
    if 11 <= (n % 100) <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _parse_reminder_days(value: str) -> list[int]:
    """Parse '7,1,0' into [7, 1, 0] sorted descending."""
    return sorted(
        [int(x.strip()) for x in value.split(",") if x.strip()],
        reverse=True,
    )


def _normalize_date(date_str: str) -> str:
    """Normalize date input to YYYY-MM-DD internal format.

    Accepts:
      - "DD-MM-YYYY" -> stored as "YYYY-MM-DD"
      - "DD-MM"      -> stored as "0000-MM-DD" (no birth year)
    """
    parts = date_str.strip().split("-")
    if len(parts) == 2:
        day, month = int(parts[0]), int(parts[1])
        date(2000, month, day)  # Validate with a leap year
        return f"0000-{month:02d}-{day:02d}"
    if len(parts) == 3:
        day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
        if year != 0:
            date(year, month, day)
        else:
            date(2000, month, day)
        return f"{year:04d}-{month:02d}-{day:02d}"
    raise vol.Invalid(f"Invalid date format: {date_str}. Use DD-MM-YYYY or DD-MM.")


def _display_date(stored_date: str) -> str:
    """Convert internal YYYY-MM-DD to display format DD-MM-YYYY or DD-MM."""
    parts = stored_date.split("-")
    year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
    if year == 0:
        return f"{day:02d}-{month:02d}"
    return f"{day:02d}-{month:02d}-{year:04d}"


def _days_until_birthday(birthday_date_str: str, today: date) -> int:
    """Calculate days until the next occurrence of this birthday."""
    parts = birthday_date_str.split("-")
    month, day = int(parts[1]), int(parts[2])

    try:
        this_year = date(today.year, month, day)
    except ValueError:
        this_year = date(today.year, month, 28)

    if this_year < today:
        try:
            next_year = date(today.year + 1, month, day)
        except ValueError:
            next_year = date(today.year + 1, month, 28)
        return (next_year - today).days
    return (this_year - today).days


def _age_turning(birthday_date_str: str, today: date) -> int | None:
    """Calculate the age they will be turning on their next birthday.

    Returns None if birth year is not known (year == 0).
    """
    parts = birthday_date_str.split("-")
    year = int(parts[0])
    if year == 0:
        return None

    month, day = int(parts[1]), int(parts[2])
    try:
        this_year_bday = date(today.year, month, day)
    except ValueError:
        this_year_bday = date(today.year, month, 28)

    if this_year_bday < today:
        return today.year + 1 - year
    return today.year - year


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Birthday Tracker integration."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Birthday Tracker from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    store = BirthdayStore(hass)
    await store.async_load()
    hass.data[DOMAIN]["store"] = store

    # Parse options
    options = entry.options
    notification_time_str = options.get(
        CONF_NOTIFICATION_TIME, DEFAULT_NOTIFICATION_TIME
    )
    hour, minute = (int(x) for x in notification_time_str.split(":"))

    default_reminder_days_str = options.get(CONF_DEFAULT_REMINDER_DAYS, "")
    if default_reminder_days_str:
        default_reminder_days = _parse_reminder_days(default_reminder_days_str)
    else:
        default_reminder_days = list(DEFAULT_REMINDER_DAYS)

    hass.data[DOMAIN]["default_reminder_days"] = default_reminder_days

    # --- Services ---

    async def handle_add_birthday(call: ServiceCall) -> ServiceResponse:
        """Handle the add_birthday service call."""
        name = call.data[ATTR_NAME]
        date_str = _normalize_date(call.data[ATTR_DATE])
        reminder_str = call.data.get(ATTR_REMINDER_DAYS)
        reminder_days = (
            _parse_reminder_days(reminder_str)
            if reminder_str
            else list(default_reminder_days)
        )
        notes = call.data.get(ATTR_NOTES, "")

        birthday = await store.async_add(name, date_str, reminder_days, notes)
        _LOGGER.info(
            "Added birthday for %s on %s (id=%s)", name, date_str, birthday["id"]
        )
        hass.bus.async_fire(EVENT_BIRTHDAYS_UPDATED)
        return {
            "id": birthday["id"],
            "name": birthday["name"],
            "date": _display_date(birthday["date"]),
        }

    async def handle_remove_birthday(call: ServiceCall) -> ServiceResponse:
        """Handle the remove_birthday service call."""
        birthday_id = call.data[ATTR_BIRTHDAY_ID]
        removed = await store.async_remove(birthday_id)
        if not removed:
            raise ValueError(f"Birthday with id '{birthday_id}' not found")
        _LOGGER.info("Removed birthday id=%s", birthday_id)
        hass.bus.async_fire(EVENT_BIRTHDAYS_UPDATED)
        return {"removed": birthday_id}

    async def handle_edit_birthday(call: ServiceCall) -> ServiceResponse:
        """Handle the edit_birthday service call."""
        birthday_id = call.data[ATTR_BIRTHDAY_ID]
        kwargs: dict[str, Any] = {}

        if ATTR_NAME in call.data:
            kwargs[ATTR_NAME] = call.data[ATTR_NAME]
        if ATTR_DATE in call.data:
            kwargs[ATTR_DATE] = _normalize_date(call.data[ATTR_DATE])
        if ATTR_REMINDER_DAYS in call.data:
            kwargs[ATTR_REMINDER_DAYS] = _parse_reminder_days(
                call.data[ATTR_REMINDER_DAYS]
            )
        if ATTR_NOTES in call.data:
            kwargs[ATTR_NOTES] = call.data[ATTR_NOTES]

        result = await store.async_edit(birthday_id, **kwargs)
        if result is None:
            raise ValueError(f"Birthday with id '{birthday_id}' not found")
        _LOGGER.info("Edited birthday id=%s", birthday_id)
        hass.bus.async_fire(EVENT_BIRTHDAYS_UPDATED)
        return result

    async def handle_list_birthdays(call: ServiceCall) -> ServiceResponse:
        """Handle the list_birthdays service call."""
        today = date.today()
        result = []
        for b in store.birthdays:
            age = _age_turning(b["date"], today)
            result.append(
                {
                    "id": b["id"],
                    "name": b["name"],
                    "date": _display_date(b["date"]),
                    "days_until": _days_until_birthday(b["date"], today),
                    "age_turning": age,
                    "age_turning_ordinal": _ordinal(age) if age else None,
                    "reminder_days_before": b["reminder_days_before"],
                    "notes": b.get("notes", ""),
                }
            )
        result.sort(key=lambda x: x["days_until"])
        return {"birthdays": result}

    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_BIRTHDAY,
        handle_add_birthday,
        schema=SERVICE_ADD_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE_BIRTHDAY,
        handle_remove_birthday,
        schema=SERVICE_REMOVE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_EDIT_BIRTHDAY,
        handle_edit_birthday,
        schema=SERVICE_EDIT_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_LIST_BIRTHDAYS,
        handle_list_birthdays,
        schema=vol.Schema({}),
        supports_response=SupportsResponse.ONLY,
    )

    # --- Daily reminder scheduler ---

    @callback
    def _async_check_birthdays(now: datetime) -> None:
        """Check all birthdays and fire reminder events."""
        today = now.date()
        for birthday in store.birthdays:
            days = _days_until_birthday(birthday["date"], today)
            reminder_days = birthday.get(
                "reminder_days_before", default_reminder_days
            )
            if days in reminder_days:
                age = _age_turning(birthday["date"], today)
                event_data = {
                    ATTR_NAME: birthday["name"],
                    ATTR_DATE: _display_date(birthday["date"]),
                    ATTR_DAYS_UNTIL: days,
                    ATTR_AGE_TURNING: age,
                    ATTR_AGE_TURNING_ORDINAL: _ordinal(age) if age else None,
                    ATTR_NOTES: birthday.get("notes", ""),
                    ATTR_BIRTHDAY_ID: birthday["id"],
                }
                _LOGGER.info(
                    "Firing %s event for %s (%d days until birthday)",
                    EVENT_BIRTHDAY_REMINDER,
                    birthday["name"],
                    days,
                )
                hass.bus.async_fire(EVENT_BIRTHDAY_REMINDER, event_data)

    unsub_time_listener = async_track_time_change(
        hass, _async_check_birthdays, hour=hour, minute=minute, second=0
    )
    hass.data[DOMAIN]["unsub_time_listener"] = unsub_time_listener

    # --- Options update listener ---

    async def _async_options_updated(
        hass_ref: HomeAssistant, entry_ref: ConfigEntry
    ) -> None:
        """Handle options update - reschedule reminder time."""
        old_unsub = hass_ref.data[DOMAIN].get("unsub_time_listener")
        if old_unsub:
            old_unsub()

        new_time_str = entry_ref.options.get(
            CONF_NOTIFICATION_TIME, DEFAULT_NOTIFICATION_TIME
        )
        new_hour, new_minute = (int(x) for x in new_time_str.split(":"))

        new_reminder_str = entry_ref.options.get(CONF_DEFAULT_REMINDER_DAYS, "")
        if new_reminder_str:
            hass_ref.data[DOMAIN]["default_reminder_days"] = _parse_reminder_days(
                new_reminder_str
            )

        hass_ref.data[DOMAIN]["unsub_time_listener"] = async_track_time_change(
            hass_ref, _async_check_birthdays, hour=new_hour, minute=new_minute, second=0
        )
        _LOGGER.info(
            "Rescheduled birthday check to %02d:%02d", new_hour, new_minute
        )

    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    # --- Forward platform setup ---
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Birthday Tracker config entry."""
    unsub = hass.data[DOMAIN].get("unsub_time_listener")
    if unsub:
        unsub()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    for service_name in (
        SERVICE_ADD_BIRTHDAY,
        SERVICE_REMOVE_BIRTHDAY,
        SERVICE_EDIT_BIRTHDAY,
        SERVICE_LIST_BIRTHDAYS,
    ):
        hass.services.async_remove(DOMAIN, service_name)

    if unload_ok:
        hass.data.pop(DOMAIN, None)

    return unload_ok
