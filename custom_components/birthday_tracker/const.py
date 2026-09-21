"""Constants for the Birthday Tracker integration."""
from typing import Final

DOMAIN: Final = "birthday_tracker"
PLATFORMS: Final = ["calendar", "sensor"]

# Storage
STORAGE_KEY: Final = f"{DOMAIN}.birthdays"
STORAGE_VERSION: Final = 1

# Config / Options keys
CONF_NOTIFICATION_TIME: Final = "notification_time"
CONF_DEFAULT_REMINDER_DAYS: Final = "default_reminder_days"
CONF_NOTIFY_SERVICES: Final = "notify_services"

# Defaults
DEFAULT_NOTIFICATION_TIME: Final = "12:00"
DEFAULT_REMINDER_DAYS: Final = [7, 1, 0]

# Event
EVENT_BIRTHDAY_REMINDER: Final = f"{DOMAIN}_reminder"

# Internal event for calendar refresh
EVENT_BIRTHDAYS_UPDATED: Final = f"{DOMAIN}_updated"

# Service names
SERVICE_ADD_BIRTHDAY: Final = "add_birthday"
SERVICE_REMOVE_BIRTHDAY: Final = "remove_birthday"
SERVICE_EDIT_BIRTHDAY: Final = "edit_birthday"
SERVICE_LIST_BIRTHDAYS: Final = "list_birthdays"

# Birthday data keys
ATTR_BIRTHDAY_ID: Final = "id"
ATTR_NAME: Final = "name"
ATTR_DATE: Final = "date"
ATTR_REMINDER_DAYS: Final = "reminder_days_before"
ATTR_NOTES: Final = "notes"
ATTR_DAYS_UNTIL: Final = "days_until"
ATTR_AGE_TURNING: Final = "age_turning"
ATTR_AGE_TURNING_ORDINAL: Final = "age_turning_ordinal"

# --- Entry types -------------------------------------------------------------------
# Every entry carries a type. Entries that predate the field are read as birthdays, so
# existing data needs no migration and old code tolerates the extra key.
ATTR_TYPE: Final = "type"
TYPE_BIRTHDAY: Final = "birthday"
TYPE_MEMORIAL: Final = "memorial"
TYPE_WEDDING: Final = "wedding"
TYPE_PERSONAL: Final = "personal"
ENTRY_TYPES: Final = (TYPE_BIRTHDAY, TYPE_MEMORIAL, TYPE_WEDDING, TYPE_PERSONAL)
DEFAULT_TYPE: Final = TYPE_BIRTHDAY

# Icon per type, so a memorial does not wear a birthday cake.
TYPE_ICONS: Final = {
    TYPE_BIRTHDAY: "mdi:cake-variant",
    TYPE_MEMORIAL: "mdi:flower",
    TYPE_WEDDING: "mdi:ring",
    TYPE_PERSONAL: "mdi:calendar-star",
}

# Years counting: a birthday's age, a wedding's years married, or years since a passing.
ATTR_YEARS: Final = "years"
ATTR_YEARS_ORDINAL: Final = "years_ordinal"
