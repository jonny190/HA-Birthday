"""Sensor platform for Birthday Tracker - one entity per birthday."""
from __future__ import annotations

from datetime import date

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, EVENT_BIRTHDAYS_UPDATED


def _ordinal(n: int) -> str:
    """Convert an integer to an ordinal string."""
    if 11 <= (n % 100) <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _days_until(birthday_date_str: str, today: date) -> int:
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
    """Calculate the age they will be turning on their next birthday."""
    year = int(birthday_date_str.split("-")[0])
    if year == 0:
        return None
    month, day = int(birthday_date_str.split("-")[1]), int(birthday_date_str.split("-")[2])
    try:
        this_year_bday = date(today.year, month, day)
    except ValueError:
        this_year_bday = date(today.year, month, 28)
    if this_year_bday < today:
        return today.year + 1 - year
    return today.year - year


def _display_date(stored_date: str) -> str:
    """Convert internal YYYY-MM-DD to DD-MM-YYYY or DD-MM."""
    parts = stored_date.split("-")
    year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
    if year == 0:
        return f"{day:02d}-{month:02d}"
    return f"{day:02d}-{month:02d}-{year:04d}"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Birthday Tracker sensors from config entry."""
    store = hass.data[DOMAIN]["store"]

    # Track which birthday IDs have entities
    tracked: dict[str, BirthdaySensor] = {}

    @callback
    def _async_update_sensors(event=None) -> None:
        """Add/remove/update sensor entities when birthdays change."""
        current_ids = {b["id"] for b in store.birthdays}
        new_entities = []

        # Add sensors for new birthdays
        for birthday in store.birthdays:
            bid = birthday["id"]
            if bid not in tracked:
                sensor = BirthdaySensor(birthday, store)
                tracked[bid] = sensor
                new_entities.append(sensor)
            else:
                # Update existing sensor
                tracked[bid].async_write_ha_state()

        if new_entities:
            async_add_entities(new_entities)

        # Mark removed birthdays as unavailable
        removed_ids = set(tracked.keys()) - current_ids
        for rid in removed_ids:
            tracked[rid].set_removed()
            tracked[rid].async_write_ha_state()
            del tracked[rid]

    # Initial population
    _async_update_sensors()

    # Listen for changes
    entry.async_on_unload(
        hass.bus.async_listen(EVENT_BIRTHDAYS_UPDATED, _async_update_sensors)
    )


class BirthdaySensor(SensorEntity):
    """Sensor showing days until a person's next birthday."""

    _attr_icon = "mdi:cake-variant"
    _attr_native_unit_of_measurement = "days"
    _attr_has_entity_name = True

    def __init__(self, birthday: dict, store) -> None:
        """Initialize the sensor."""
        self._birthday_id = birthday["id"]
        self._store = store
        self._removed = False
        self._attr_unique_id = f"{DOMAIN}_{birthday['id']}"
        self._attr_name = birthday["name"]

    def set_removed(self) -> None:
        """Mark this sensor as removed."""
        self._removed = True

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return not self._removed

    @property
    def _birthday(self) -> dict | None:
        """Get current birthday data from store."""
        return self._store.get_by_id(self._birthday_id)

    @property
    def native_value(self) -> int | None:
        """Return days until next birthday."""
        birthday = self._birthday
        if birthday is None:
            return None
        return _days_until(birthday["date"], date.today())

    @property
    def extra_state_attributes(self) -> dict | None:
        """Return additional attributes."""
        birthday = self._birthday
        if birthday is None:
            return None

        today = date.today()
        age = _age_turning(birthday["date"], today)

        return {
            "birthday_id": birthday["id"],
            "date": _display_date(birthday["date"]),
            "age_turning": age,
            "age_turning_ordinal": _ordinal(age) if age else None,
            "reminder_days_before": birthday.get("reminder_days_before", []),
            "notes": birthday.get("notes", ""),
        }
