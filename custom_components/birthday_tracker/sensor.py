"""Sensor platform for Birthday Tracker - one entity per entry."""
from __future__ import annotations

from datetime import date

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import wording
from .const import (
    DOMAIN,
    EVENT_BIRTHDAYS_UPDATED,
    TYPE_BIRTHDAY,
    TYPE_ICONS,
)
from .dates import days_until, display_date, next_occurrence, ordinal, years_counting


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Birthday Tracker sensors from config entry."""
    store = hass.data[DOMAIN]["store"]

    # Track which entry IDs have entities
    tracked: dict[str, BirthdaySensor] = {}

    @callback
    def _async_update_sensors(event=None) -> None:
        """Add/remove/update sensor entities when entries change."""
        current_ids = {b["id"] for b in store.birthdays}
        new_entities = []

        # Add sensors for new entries
        for entity in store.birthdays:
            eid = entity["id"]
            if eid not in tracked:
                sensor = BirthdaySensor(entity, store)
                tracked[eid] = sensor
                new_entities.append(sensor)
            else:
                # Update existing sensor
                tracked[eid].async_write_ha_state()

        if new_entities:
            async_add_entities(new_entities)

        # Mark removed entries as unavailable
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
    """Sensor showing days until the next occurrence of an entry."""

    _attr_native_unit_of_measurement = "days"
    _attr_has_entity_name = True

    def __init__(self, entity: dict, store) -> None:
        """Initialize the sensor."""
        self._birthday_id = entity["id"]
        self._store = store
        self._removed = False
        self._attr_unique_id = f"{DOMAIN}_{entity['id']}"
        self._attr_name = entity["name"]

    def set_removed(self) -> None:
        """Mark this sensor as removed."""
        self._removed = True

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return not self._removed

    @property
    def _entry(self) -> dict | None:
        """Get current entry data from the store."""
        return self._store.get_by_id(self._birthday_id)

    @property
    def icon(self) -> str:
        """Icon follows the entry type, so a memorial does not wear a cake."""
        entity = self._entry
        if entity is None:
            return TYPE_ICONS[TYPE_BIRTHDAY]
        return TYPE_ICONS.get(wording.entry_type(entity), TYPE_ICONS[TYPE_BIRTHDAY])

    @property
    def native_value(self) -> int | None:
        """Return days until the next occurrence."""
        entity = self._entry
        if entity is None:
            return None
        return days_until(entity["date"], date.today())

    @property
    def extra_state_attributes(self) -> dict | None:
        """Return additional attributes."""
        entity = self._entry
        if entity is None:
            return None

        today = date.today()
        years = years_counting(entity["date"], next_occurrence(entity["date"], today))

        return {
            "birthday_id": entity["id"],
            "type": wording.entry_type(entity),
            "date": display_date(entity["date"]),
            # age_turning is kept for anything already built on it; years is the general form.
            "age_turning": years,
            "age_turning_ordinal": ordinal(years) if years else None,
            "years": years,
            "years_ordinal": ordinal(years) if years else None,
            "reminder_days_before": entity.get("reminder_days_before", []),
            "notes": entity.get("notes", ""),
        }
