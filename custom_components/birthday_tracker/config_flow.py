"""Config flow for Birthday Tracker."""
from __future__ import annotations

import logging
from datetime import date
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback

from .const import (
    ATTR_BIRTHDAY_ID,
    ATTR_DATE,
    ATTR_NAME,
    ATTR_NOTES,
    ATTR_REMINDER_DAYS,
    CONF_DEFAULT_REMINDER_DAYS,
    CONF_NOTIFICATION_TIME,
    DEFAULT_NOTIFICATION_TIME,
    DEFAULT_REMINDER_DAYS,
    DOMAIN,
    EVENT_BIRTHDAYS_UPDATED,
)

_LOGGER = logging.getLogger(__name__)


class BirthdayTrackerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Birthday Tracker."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step - simple confirmation."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(
                title="Birthday Tracker",
                data={},
                options={
                    CONF_NOTIFICATION_TIME: DEFAULT_NOTIFICATION_TIME,
                    CONF_DEFAULT_REMINDER_DAYS: ",".join(
                        str(d) for d in DEFAULT_REMINDER_DAYS
                    ),
                },
            )

        return self.async_show_form(step_id="user")

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> BirthdayTrackerOptionsFlow:
        """Get the options flow handler."""
        return BirthdayTrackerOptionsFlow()


def _normalize_date(date_str: str) -> str:
    """Normalize date input to YYYY-MM-DD format."""
    parts = date_str.strip().split("-")
    if len(parts) == 2:
        month, day = int(parts[0]), int(parts[1])
        date(2000, month, day)
        return f"0000-{month:02d}-{day:02d}"
    if len(parts) == 3:
        year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
        if year != 0:
            date(year, month, day)
        else:
            date(2000, month, day)
        return f"{year:04d}-{month:02d}-{day:02d}"
    raise vol.Invalid(f"Invalid date format: {date_str}. Use YYYY-MM-DD or MM-DD.")


def _parse_reminder_days(value: str) -> list[int]:
    """Parse '7,1,0' into [7, 1, 0] sorted descending."""
    return sorted(
        [int(x.strip()) for x in value.split(",") if x.strip()],
        reverse=True,
    )


class BirthdayTrackerOptionsFlow(OptionsFlow):
    """Handle options flow for Birthday Tracker."""

    def __init__(self) -> None:
        """Initialize options flow."""
        self._selected_birthday_id: str | None = None

    def _get_store(self):
        """Get the birthday store."""
        return self.hass.data[DOMAIN]["store"]

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the main menu."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["add_birthday", "manage_birthdays", "settings"],
        )

    # ── Add Birthday ─────────────────────────────────────────────

    async def async_step_add_birthday(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle adding a new birthday."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate date
            try:
                date_str = _normalize_date(user_input[ATTR_DATE])
            except (ValueError, vol.Invalid):
                errors[ATTR_DATE] = "invalid_date"

            if not errors:
                store = self._get_store()
                default_days = self.hass.data[DOMAIN].get(
                    "default_reminder_days", DEFAULT_REMINDER_DAYS
                )
                reminder_str = user_input.get(ATTR_REMINDER_DAYS, "")
                reminder_days = (
                    _parse_reminder_days(reminder_str)
                    if reminder_str
                    else list(default_days)
                )

                await store.async_add(
                    name=user_input[ATTR_NAME],
                    date_str=date_str,
                    reminder_days_before=reminder_days,
                    notes=user_input.get(ATTR_NOTES, ""),
                )

                self.hass.bus.async_fire(EVENT_BIRTHDAYS_UPDATED)
                _LOGGER.info("Added birthday for %s via config flow", user_input[ATTR_NAME])

                # Return unchanged options to close the flow
                return self.async_create_entry(data=self.config_entry.options)

        default_reminder_str = ",".join(
            str(d) for d in self.hass.data[DOMAIN].get(
                "default_reminder_days", DEFAULT_REMINDER_DAYS
            )
        )

        return self.async_show_form(
            step_id="add_birthday",
            data_schema=vol.Schema(
                {
                    vol.Required(ATTR_NAME): str,
                    vol.Required(ATTR_DATE): str,
                    vol.Optional(
                        ATTR_REMINDER_DAYS, default=default_reminder_str
                    ): str,
                    vol.Optional(ATTR_NOTES, default=""): str,
                }
            ),
            errors=errors,
        )

    # ── Manage Birthdays ─────────────────────────────────────────

    async def async_step_manage_birthdays(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show a list of birthdays to select from."""
        store = self._get_store()
        birthdays = store.birthdays

        if not birthdays:
            return self.async_abort(reason="no_birthdays")

        if user_input is not None:
            self._selected_birthday_id = user_input["birthday"]
            return await self.async_step_birthday_action()

        # Build selection list: "Name (YYYY-MM-DD)"
        birthday_options = {
            b["id"]: f"{b['name']} ({b['date']})" for b in birthdays
        }

        return self.async_show_form(
            step_id="manage_birthdays",
            data_schema=vol.Schema(
                {
                    vol.Required("birthday"): vol.In(birthday_options),
                }
            ),
        )

    async def async_step_birthday_action(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show edit/remove menu for selected birthday."""
        return self.async_show_menu(
            step_id="birthday_action",
            menu_options=["edit_birthday", "remove_birthday"],
        )

    # ── Edit Birthday ────────────────────────────────────────────

    async def async_step_edit_birthday(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle editing a birthday."""
        store = self._get_store()
        birthday = store.get_by_id(self._selected_birthday_id)
        if birthday is None:
            return self.async_abort(reason="birthday_not_found")

        errors: dict[str, str] = {}

        if user_input is not None:
            kwargs: dict[str, Any] = {}

            if user_input.get(ATTR_NAME):
                kwargs[ATTR_NAME] = user_input[ATTR_NAME]

            if user_input.get(ATTR_DATE):
                try:
                    kwargs[ATTR_DATE] = _normalize_date(user_input[ATTR_DATE])
                except (ValueError, vol.Invalid):
                    errors[ATTR_DATE] = "invalid_date"

            if user_input.get(ATTR_REMINDER_DAYS):
                try:
                    kwargs[ATTR_REMINDER_DAYS] = _parse_reminder_days(
                        user_input[ATTR_REMINDER_DAYS]
                    )
                except ValueError:
                    errors[ATTR_REMINDER_DAYS] = "invalid_days"

            if ATTR_NOTES in user_input:
                kwargs[ATTR_NOTES] = user_input[ATTR_NOTES]

            if not errors:
                await store.async_edit(self._selected_birthday_id, **kwargs)
                self.hass.bus.async_fire(EVENT_BIRTHDAYS_UPDATED)
                _LOGGER.info("Edited birthday %s via config flow", self._selected_birthday_id)
                return self.async_create_entry(data=self.config_entry.options)

        reminder_str = ",".join(str(d) for d in birthday.get("reminder_days_before", []))

        return self.async_show_form(
            step_id="edit_birthday",
            data_schema=vol.Schema(
                {
                    vol.Required(ATTR_NAME, default=birthday["name"]): str,
                    vol.Required(ATTR_DATE, default=birthday["date"]): str,
                    vol.Required(
                        ATTR_REMINDER_DAYS, default=reminder_str
                    ): str,
                    vol.Optional(
                        ATTR_NOTES, default=birthday.get("notes", "")
                    ): str,
                }
            ),
            errors=errors,
        )

    # ── Remove Birthday ──────────────────────────────────────────

    async def async_step_remove_birthday(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm and remove a birthday."""
        store = self._get_store()
        birthday = store.get_by_id(self._selected_birthday_id)
        if birthday is None:
            return self.async_abort(reason="birthday_not_found")

        if user_input is not None:
            await store.async_remove(self._selected_birthday_id)
            self.hass.bus.async_fire(EVENT_BIRTHDAYS_UPDATED)
            _LOGGER.info("Removed birthday %s via config flow", self._selected_birthday_id)
            return self.async_create_entry(data=self.config_entry.options)

        return self.async_show_form(
            step_id="remove_birthday",
            description_placeholders={"name": birthday["name"]},
        )

    # ── Settings ─────────────────────────────────────────────────

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle global settings."""
        errors: dict[str, str] = {}

        if user_input is not None:
            time_str = user_input.get(CONF_NOTIFICATION_TIME, "")
            try:
                parts = time_str.split(":")
                h, m = int(parts[0]), int(parts[1])
                if not (0 <= h <= 23 and 0 <= m <= 59):
                    raise ValueError
            except (ValueError, IndexError):
                errors[CONF_NOTIFICATION_TIME] = "invalid_time"

            days_str = user_input.get(CONF_DEFAULT_REMINDER_DAYS, "")
            try:
                days = [int(x.strip()) for x in days_str.split(",") if x.strip()]
                if not days or any(d < 0 for d in days):
                    raise ValueError
            except ValueError:
                errors[CONF_DEFAULT_REMINDER_DAYS] = "invalid_days"

            if not errors:
                return self.async_create_entry(data=user_input)

        options = self.config_entry.options

        return self.async_show_form(
            step_id="settings",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NOTIFICATION_TIME,
                        default=options.get(
                            CONF_NOTIFICATION_TIME, DEFAULT_NOTIFICATION_TIME
                        ),
                    ): str,
                    vol.Required(
                        CONF_DEFAULT_REMINDER_DAYS,
                        default=options.get(
                            CONF_DEFAULT_REMINDER_DAYS,
                            ",".join(str(d) for d in DEFAULT_REMINDER_DAYS),
                        ),
                    ): str,
                }
            ),
            errors=errors,
        )
