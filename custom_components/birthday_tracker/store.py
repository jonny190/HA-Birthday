"""Persistent storage manager for birthday data."""
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
    DEFAULT_REMINDER_DAYS,
    STORAGE_KEY,
    STORAGE_VERSION,
)


class BirthdayStore:
    """Manage birthday data persistence."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the store."""
        self._store: Store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._birthdays: list[dict[str, Any]] = []

    async def async_load(self) -> None:
        """Load birthdays from disk."""
        data = await self._store.async_load()
        if data and "birthdays" in data:
            self._birthdays = data["birthdays"]
        else:
            self._birthdays = []

    async def _async_save(self) -> None:
        """Save birthdays to disk."""
        await self._store.async_save({"birthdays": self._birthdays})

    @property
    def birthdays(self) -> list[dict[str, Any]]:
        """Return all birthdays."""
        return list(self._birthdays)

    async def async_add(
        self,
        name: str,
        date_str: str,
        reminder_days_before: list[int] | None = None,
        notes: str = "",
    ) -> dict[str, Any]:
        """Add a birthday. Returns the new birthday dict."""
        birthday: dict[str, Any] = {
            ATTR_BIRTHDAY_ID: uuid.uuid4().hex[:8],
            ATTR_NAME: name,
            ATTR_DATE: date_str,
            ATTR_REMINDER_DAYS: reminder_days_before if reminder_days_before is not None else list(DEFAULT_REMINDER_DAYS),
            ATTR_NOTES: notes,
        }
        self._birthdays.append(birthday)
        await self._async_save()
        return birthday

    async def async_remove(self, birthday_id: str) -> bool:
        """Remove a birthday by ID. Returns True if found and removed."""
        for i, b in enumerate(self._birthdays):
            if b[ATTR_BIRTHDAY_ID] == birthday_id:
                self._birthdays.pop(i)
                await self._async_save()
                return True
        return False

    async def async_edit(
        self, birthday_id: str, **kwargs: Any
    ) -> dict[str, Any] | None:
        """Edit a birthday. Returns updated dict or None if not found."""
        for birthday in self._birthdays:
            if birthday[ATTR_BIRTHDAY_ID] == birthday_id:
                for key in (ATTR_NAME, ATTR_DATE, ATTR_REMINDER_DAYS, ATTR_NOTES):
                    if key in kwargs:
                        birthday[key] = kwargs[key]
                await self._async_save()
                return dict(birthday)
        return None

    def get_by_id(self, birthday_id: str) -> dict[str, Any] | None:
        """Get a birthday by ID."""
        for birthday in self._birthdays:
            if birthday[ATTR_BIRTHDAY_ID] == birthday_id:
                return dict(birthday)
        return None
