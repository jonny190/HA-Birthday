"""Persistent storage manager for birthday, memorial, wedding and personal entries."""
from __future__ import annotations

import uuid
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import (
    ATTR_BIRTHDAY_ID,
    ATTR_DATE,
    ATTR_NAME,
    ATTR_NOTES,
    ATTR_REMINDER_DAYS,
    ATTR_TYPE,
    DEFAULT_REMINDER_DAYS,
    DEFAULT_TYPE,
    STORAGE_KEY,
    STORAGE_VERSION,
)


class BirthdayStore:
    """Manage entry persistence.

    Storage stays at version 1 and the list key stays ``birthdays``. The only change is an
    extra ``type`` key on each entry, which older code ignores, so rolling back to the
    previous release still reads the file. Entries written before types existed are
    backfilled as birthdays on load rather than through a migration step.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the store."""
        self._store: Store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._birthdays: list[dict[str, Any]] = []

    async def async_load(self) -> None:
        """Load entries from disk, backfilling a missing type."""
        data = await self._store.async_load()
        entries = data.get("birthdays") if data else None
        self._birthdays = entries if entries is not None else []

        backfilled = False
        for entry in self._birthdays:
            if not entry.get(ATTR_TYPE):
                entry[ATTR_TYPE] = DEFAULT_TYPE
                backfilled = True
        if backfilled:
            await self._async_save()

    async def _async_save(self) -> None:
        """Save entries to disk."""
        await self._store.async_save({"birthdays": self._birthdays})

    @property
    def birthdays(self) -> list[dict[str, Any]]:
        """Return all entries."""
        return list(self._birthdays)

    async def async_add(
        self,
        name: str,
        date_str: str,
        reminder_days_before: list[int] | None = None,
        notes: str = "",
        entry_type: str | None = None,
    ) -> dict[str, Any]:
        """Add an entry. Returns the new entry dict."""
        entry: dict[str, Any] = {
            ATTR_BIRTHDAY_ID: uuid.uuid4().hex[:8],
            ATTR_NAME: name,
            ATTR_DATE: date_str,
            ATTR_REMINDER_DAYS: reminder_days_before if reminder_days_before is not None else list(DEFAULT_REMINDER_DAYS),
            ATTR_NOTES: notes,
            ATTR_TYPE: entry_type or DEFAULT_TYPE,
        }
        self._birthdays.append(entry)
        await self._async_save()
        return entry

    async def async_remove(self, birthday_id: str) -> bool:
        """Remove an entry by ID. Returns True if found and removed."""
        for i, entry in enumerate(self._birthdays):
            if entry[ATTR_BIRTHDAY_ID] == birthday_id:
                self._birthdays.pop(i)
                await self._async_save()
                return True
        return False

    async def async_edit(
        self, birthday_id: str, **kwargs: Any
    ) -> dict[str, Any] | None:
        """Edit an entry. Returns the updated dict, or None if not found."""
        for entry in self._birthdays:
            if entry[ATTR_BIRTHDAY_ID] == birthday_id:
                for key in (ATTR_NAME, ATTR_DATE, ATTR_REMINDER_DAYS, ATTR_NOTES, ATTR_TYPE):
                    if key in kwargs and kwargs[key] is not None:
                        entry[key] = kwargs[key]
                await self._async_save()
                return dict(entry)
        return None

    def get_by_id(self, birthday_id: str) -> dict[str, Any] | None:
        """Get an entry by ID."""
        for entry in self._birthdays:
            if entry[ATTR_BIRTHDAY_ID] == birthday_id:
                return dict(entry)
        return None
