"""Calendar platform for Birthday Tracker."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import wording
from .const import DOMAIN, EVENT_BIRTHDAYS_UPDATED
from .dates import days_until, next_occurrence


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Birthday Tracker calendar from config entry."""
    store = hass.data[DOMAIN]["store"]
    async_add_entities([BirthdayCalendar(hass, store)])


class BirthdayCalendar(CalendarEntity):
    """A calendar entity that displays every entry as a yearly recurring all-day event.

    One calendar holds all four types. How each one reads is decided by wording.summarise,
    so a birthday, a memorial, a wedding anniversary and a personal date each get their own
    phrasing from the same list.
    """

    _attr_has_entity_name = True
    _attr_name = "Birthdays"
    _attr_icon = "mdi:cake-variant"

    def __init__(self, hass: HomeAssistant, store) -> None:
        """Initialize the calendar entity."""
        self._store = store
        self._attr_unique_id = f"{DOMAIN}_calendar"
        self._unsub_update = hass.bus.async_listen(
            EVENT_BIRTHDAYS_UPDATED, self._handle_update
        )

    @callback
    def _handle_update(self, event) -> None:
        """Handle entry data update."""
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        """Clean up event listener."""
        if self._unsub_update:
            self._unsub_update()

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        today = date.today()
        entries = self._store.birthdays
        if not entries:
            return None

        closest = None
        closest_days = 999999

        for entry in entries:
            entry_days = days_until(entry["date"], today)
            if entry_days < closest_days:
                closest_days = entry_days
                closest = entry

        if closest is None:
            return None

        event_date = next_occurrence(closest["date"], today)

        return CalendarEvent(
            start=event_date,
            end=event_date + timedelta(days=1),
            summary=wording.summarise(closest, event_date),
            description=closest.get("notes", ""),
            uid=closest["id"],
        )

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return every entry falling within the requested date range."""
        events: list[CalendarEvent] = []
        start_d = start_date.date() if isinstance(start_date, datetime) else start_date
        end_d = end_date.date() if isinstance(end_date, datetime) else end_date

        for entry in self._store.birthdays:
            parts = entry["date"].split("-")
            month = int(parts[1])
            day = int(parts[2])

            for year in range(start_d.year, end_d.year + 1):
                try:
                    event_date = date(year, month, day)
                except ValueError:
                    event_date = date(year, month, 28)

                if start_d <= event_date < end_d:
                    events.append(
                        CalendarEvent(
                            start=event_date,
                            end=event_date + timedelta(days=1),
                            summary=wording.summarise(entry, event_date),
                            description=entry.get("notes", ""),
                            uid=f"{entry['id']}_{year}",
                        )
                    )

        events.sort(key=lambda e: e.start)
        return events
