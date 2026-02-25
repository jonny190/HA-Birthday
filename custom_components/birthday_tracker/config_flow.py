"""Config flow for Birthday Tracker."""
from __future__ import annotations

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
    CONF_DEFAULT_REMINDER_DAYS,
    CONF_NOTIFICATION_TIME,
    DEFAULT_NOTIFICATION_TIME,
    DEFAULT_REMINDER_DAYS,
    DOMAIN,
)


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


class BirthdayTrackerOptionsFlow(OptionsFlow):
    """Handle options flow for Birthday Tracker."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate notification time format
            time_str = user_input.get(CONF_NOTIFICATION_TIME, "")
            try:
                parts = time_str.split(":")
                h, m = int(parts[0]), int(parts[1])
                if not (0 <= h <= 23 and 0 <= m <= 59):
                    raise ValueError
            except (ValueError, IndexError):
                errors[CONF_NOTIFICATION_TIME] = "invalid_time"

            # Validate reminder days format
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
            step_id="init",
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
