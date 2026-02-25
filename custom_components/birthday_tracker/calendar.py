"""Calendar platform for Birthday Tracker."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, EVENT_BIRTHDAYS_UPDATED


def _ordinal(n: int) -> str:
    """Convert an integer to an ordinal string (1st, 2nd, 3rd, 11th, etc.)."""
    if 11 <= (n % 100) <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Birthday Tracker calendar from config entry."""
    store = hass.data[DOMAIN]["store"]
    async_add_entities([BirthdayCalendar(hass, store)])


class BirthdayCalendar(CalendarEntity):
    """A calendar entity that displays birthdays as yearly recurring all-day events."""

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
        """Handle birthday data update."""
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        """Clean up event listener."""
        if self._unsub_update:
            self._unsub_update()

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming birthday event."""
        today = date.today()
        birthdays = self._store.birthdays
        if not birthdays:
            return None

        closest = None
        closest_days = 999999

        for b in birthdays:
            days = self._days_until(b["date"], today)
            if days < closest_days:
                closest_days = days
                closest = b

        if closest is None:
            return None

        event_date = self._next_occurrence(closest["date"], today)
        summary = self._build_summary(closest, event_date)

        return CalendarEvent(
            start=event_date,
            end=event_date + timedelta(days=1),
            summary=summary,
            description=closest.get("notes", ""),
            uid=closest["id"],
        )

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return all birthday events within the requested date range."""
        events: list[CalendarEvent] = []
        start_d = start_date.date() if isinstance(start_date, datetime) else start_date
        end_d = end_date.date() if isinstance(end_date, datetime) else end_date

        for birthday in self._store.birthdays:
            parts = birthday["date"].split("-")
            month = int(parts[1])
            day = int(parts[2])

            for year in range(start_d.year, end_d.year + 1):
                try:
                    event_date = date(year, month, day)
                except ValueError:
                    event_date = date(year, month, 28)

                if start_d <= event_date < end_d:
                    summary = self._build_summary(birthday, event_date)
                    events.append(
                        CalendarEvent(
                            start=event_date,
                            end=event_date + timedelta(days=1),
                            summary=summary,
                            description=birthday.get("notes", ""),
                            uid=f"{birthday['id']}_{year}",
                        )
                    )

        events.sort(key=lambda e: e.start)
        return events

    @staticmethod
    def _build_summary(birthday: dict, event_date: date) -> str:
        """Build the event summary with age ordinal if birth year is known.

        Examples:
            "Alice's Birthday (40th)"
            "Bob Jones' Birthday"
        """
        name = birthday["name"]
        possessive = f"{name}'" if name.endswith("s") else f"{name}'s"

        birth_year = int(birthday["date"].split("-")[0])
        if birth_year and birth_year != 0:
            age = event_date.year - birth_year
            if age > 0:
                return f"{possessive} Birthday ({_ordinal(age)})"

        return f"{possessive} Birthday"

    @staticmethod
    def _next_occurrence(birthday_date_str: str, today: date) -> date:
        """Get the next occurrence date of a birthday."""
        parts = birthday_date_str.split("-")
        month, day = int(parts[1]), int(parts[2])

        try:
            this_year = date(today.year, month, day)
        except ValueError:
            this_year = date(today.year, month, 28)

        if this_year < today:
            try:
                return date(today.year + 1, month, day)
            except ValueError:
                return date(today.year + 1, month, 28)
        return this_year

    @staticmethod
    def _days_until(birthday_date_str: str, today: date) -> int:
        """Calculate days until the next occurrence."""
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
