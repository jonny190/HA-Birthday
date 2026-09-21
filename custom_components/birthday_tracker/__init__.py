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

from . import wording
from .const import (
    ATTR_AGE_TURNING,
    ATTR_AGE_TURNING_ORDINAL,
    ATTR_BIRTHDAY_ID,
    ATTR_DATE,
    ATTR_DAYS_UNTIL,
    ATTR_NAME,
    ATTR_NOTES,
    ATTR_REMINDER_DAYS,
    ATTR_TYPE,
    ATTR_YEARS,
    ATTR_YEARS_ORDINAL,
    CONF_DEFAULT_REMINDER_DAYS,
    CONF_NOTIFICATION_TIME,
    CONF_NOTIFY_SERVICES,
    DEFAULT_NOTIFICATION_TIME,
    DEFAULT_REMINDER_DAYS,
    DEFAULT_TYPE,
    DOMAIN,
    ENTRY_TYPES,
    EVENT_BIRTHDAY_REMINDER,
    EVENT_BIRTHDAYS_UPDATED,
    PLATFORMS,
    SERVICE_ADD_BIRTHDAY,
    SERVICE_EDIT_BIRTHDAY,
    SERVICE_LIST_BIRTHDAYS,
    SERVICE_REMOVE_BIRTHDAY,
    TYPE_MEMORIAL,
    TYPE_PERSONAL,
    TYPE_WEDDING,
)
from .dates import days_until, display_date, next_occurrence, ordinal, years_counting
from .store import BirthdayStore

_LOGGER = logging.getLogger(__name__)

# Friendly names accepted alongside the canonical types, so a service call can say
# "anniversary" or "reminder" without the caller having to know the internal words.
TYPE_ALIASES: dict[str, str] = {
    "anniversary": TYPE_WEDDING,
    "wedding_anniversary": TYPE_WEDDING,
    "reminder": TYPE_PERSONAL,
    "personal_reminder": TYPE_PERSONAL,
    "passing": TYPE_MEMORIAL,
    "in_memoriam": TYPE_MEMORIAL,
    "memorial_day": TYPE_MEMORIAL,
}


def _resolve_type(value: str | None) -> str:
    """Map an incoming type (or alias) to a canonical one."""
    if not value:
        return DEFAULT_TYPE
    cleaned = value.strip().lower().replace("-", "_").replace(" ", "_")
    return TYPE_ALIASES.get(cleaned, cleaned)


SERVICE_ADD_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_NAME): cv.string,
        vol.Required(ATTR_DATE): cv.string,
        vol.Optional(ATTR_REMINDER_DAYS): cv.string,
        vol.Optional(ATTR_NOTES, default=""): cv.string,
        vol.Optional(ATTR_TYPE): vol.In(list(ENTRY_TYPES) + list(TYPE_ALIASES)),
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
        vol.Optional(ATTR_TYPE): vol.In(list(ENTRY_TYPES) + list(TYPE_ALIASES)),
    }
)


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
      - "DD-MM"      -> stored as "0000-MM-DD" (year unknown)
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
        entry_type = _resolve_type(call.data.get(ATTR_TYPE))

        new_entry = await store.async_add(
            name, date_str, reminder_days, notes, entry_type
        )
        _LOGGER.info(
            "Added %s for %s on %s (id=%s)",
            entry_type,
            name,
            date_str,
            new_entry["id"],
        )
        hass.bus.async_fire(EVENT_BIRTHDAYS_UPDATED)
        return {
            "id": new_entry["id"],
            "name": new_entry["name"],
            "date": display_date(new_entry["date"]),
            ATTR_TYPE: new_entry[ATTR_TYPE],
        }

    async def handle_remove_birthday(call: ServiceCall) -> ServiceResponse:
        """Handle the remove_birthday service call."""
        entry_id = call.data[ATTR_BIRTHDAY_ID]
        removed = await store.async_remove(entry_id)
        if not removed:
            raise ValueError(f"Entry with id '{entry_id}' not found")
        _LOGGER.info("Removed entry id=%s", entry_id)
        hass.bus.async_fire(EVENT_BIRTHDAYS_UPDATED)
        return {"removed": entry_id}

    async def handle_edit_birthday(call: ServiceCall) -> ServiceResponse:
        """Handle the edit_birthday service call."""
        entry_id = call.data[ATTR_BIRTHDAY_ID]
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
        if ATTR_TYPE in call.data:
            kwargs[ATTR_TYPE] = _resolve_type(call.data[ATTR_TYPE])

        result = await store.async_edit(entry_id, **kwargs)
        if result is None:
            raise ValueError(f"Entry with id '{entry_id}' not found")
        _LOGGER.info("Edited entry id=%s", entry_id)
        hass.bus.async_fire(EVENT_BIRTHDAYS_UPDATED)
        return result

    async def handle_list_birthdays(call: ServiceCall) -> ServiceResponse:
        """Handle the list_birthdays service call."""
        today = date.today()
        result = []
        for b in store.birthdays:
            event_date = next_occurrence(b["date"], today)
            years = years_counting(b["date"], event_date)
            result.append(
                {
                    "id": b["id"],
                    "name": b["name"],
                    ATTR_TYPE: wording.entry_type(b),
                    "date": display_date(b["date"]),
                    "days_until": days_until(b["date"], today),
                    # age_turning is kept for anything already built on it; years is general.
                    "age_turning": years,
                    "age_turning_ordinal": ordinal(years) if years else None,
                    ATTR_YEARS: years,
                    ATTR_YEARS_ORDINAL: ordinal(years) if years else None,
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
        """Check every entry and fire reminder events + send notifications."""
        today = now.date()

        # Get configured notify services
        notify_services_str = entry.options.get(CONF_NOTIFY_SERVICES, "")
        notify_services = [
            s.strip() for s in notify_services_str.split(",") if s.strip()
        ] if notify_services_str else []

        for item in store.birthdays:
            days = days_until(item["date"], today)
            reminder_days = item.get("reminder_days_before", default_reminder_days)
            if days not in reminder_days:
                continue

            event_date = next_occurrence(item["date"], today)
            years = years_counting(item["date"], event_date)
            entry_type = wording.entry_type(item)
            event_data = {
                ATTR_NAME: item["name"],
                ATTR_TYPE: entry_type,
                ATTR_DATE: display_date(item["date"]),
                ATTR_DAYS_UNTIL: days,
                ATTR_AGE_TURNING: years,
                ATTR_AGE_TURNING_ORDINAL: ordinal(years) if years else None,
                ATTR_YEARS: years,
                ATTR_YEARS_ORDINAL: ordinal(years) if years else None,
                ATTR_NOTES: item.get("notes", ""),
                ATTR_BIRTHDAY_ID: item["id"],
            }
            _LOGGER.info(
                "Firing %s event for %s (%s, %d days away)",
                EVENT_BIRTHDAY_REMINDER,
                item["name"],
                entry_type,
                days,
            )
            hass.bus.async_fire(EVENT_BIRTHDAY_REMINDER, event_data)

            # Send to configured notify services
            if notify_services:
                message = wording.reminder_message(item, days, event_date)
                if item.get("notes"):
                    message += f"\nNotes: {item['notes']}"
                title = wording.notification_title(item)
                for service_name in notify_services:
                    hass.async_create_task(
                        hass.services.async_call(
                            "notify",
                            service_name,
                            {"title": title, "message": message},
                        )
                    )

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
        _LOGGER.info("Rescheduled the personal-dates check to %02d:%02d", new_hour, new_minute)

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
