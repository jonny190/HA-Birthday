<p align="center">
  <img src="images/logo.png" alt="Birthday Tracker for Home Assistant" width="480">
</p>

<p align="center">
  A custom Home Assistant integration that tracks friends' and family birthdays, displays them on the HA calendar, and fires configurable reminder events for your automations.
</p>

## Features

- **Calendar integration** - Birthdays appear as recurring yearly events in the HA calendar dashboard with age display (e.g. "Alice's Birthday (40th)")
- **Configurable reminders** - Set how many days before each birthday to get reminded (default: 7, 1, and 0 days before)
- **Flexible notifications** - Fires `birthday_tracker_reminder` events that you wire up to any notification service via automations
- **Per-person settings** - Each birthday can have its own reminder schedule
- **Age tracking** - Automatically calculates and displays the age they're turning (when birth year is provided)
- **Midday notifications** - Reminders fire at 12:00 by default, configurable in integration options

## Installation

### HACS (Recommended)

1. Open HACS in your Home Assistant instance
2. Click the three dots menu in the top right and select **Custom repositories**
3. Add this repository URL and select **Integration** as the category
4. Click **Download** on the Birthday Tracker card
5. Restart Home Assistant

### Manual

1. Copy the `custom_components/birthday_tracker` folder into your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant

## Setup

1. Go to **Settings > Devices & Services > Add Integration**
2. Search for **Birthday Tracker** and click it
3. Click **Submit** to complete setup

### Options

After setup, click **Configure** on the Birthday Tracker integration card to adjust:

- **Notification time** - When daily reminder checks run (default: `12:00`, 24-hour format)
- **Default reminder days** - Comma-separated days before birthday to remind (default: `7,1,0`)

## Usage

### Adding Birthdays

Use the **Developer Tools > Services** panel or call from automations/scripts:

```yaml
service: birthday_tracker.add_birthday
data:
  name: "Alice Smith"
  date: "1990-03-15"          # YYYY-MM-DD (with birth year for age tracking)
  notes: "Likes chocolate cake"
  reminder_days_before: "7,1,0"  # Optional, uses global default if omitted
```

If you don't know the birth year, use `MM-DD` format:

```yaml
service: birthday_tracker.add_birthday
data:
  name: "Bob Jones"
  date: "03-15"               # MM-DD (no age tracking)
```

### Listing Birthdays

```yaml
service: birthday_tracker.list_birthdays
```

Returns all birthdays sorted by days until next occurrence, including `id`, `days_until`, `age_turning`, and `age_turning_ordinal` fields.

### Editing Birthdays

```yaml
service: birthday_tracker.edit_birthday
data:
  id: "a1b2c3d4"             # Get IDs from list_birthdays
  name: "Alice Johnson"       # Only include fields you want to change
  notes: "Now prefers vanilla"
```

### Removing Birthdays

```yaml
service: birthday_tracker.remove_birthday
data:
  id: "a1b2c3d4"
```

## Automation Example

The integration fires `birthday_tracker_reminder` events that you can use to trigger any notification:

```yaml
automation:
  - alias: "Birthday Reminder Notification"
    trigger:
      - platform: event
        event_type: birthday_tracker_reminder
    action:
      - service: notify.mobile_app_my_phone
        data:
          title: "Birthday Reminder"
          message: >-
            {% if trigger.event.data.days_until == 0 %}
              Today is {{ trigger.event.data.name }}'s birthday!
              {% if trigger.event.data.age_turning %}
              They are turning {{ trigger.event.data.age_turning_ordinal }}.
              {% endif %}
            {% else %}
              {{ trigger.event.data.name }}'s birthday is in
              {{ trigger.event.data.days_until }} day(s).
              {% if trigger.event.data.age_turning %}
              They will be turning {{ trigger.event.data.age_turning_ordinal }}.
              {% endif %}
            {% endif %}
            {% if trigger.event.data.notes %}
            Notes: {{ trigger.event.data.notes }}
            {% endif %}
```

### Event Data

The `birthday_tracker_reminder` event includes:

| Field | Type | Example | Description |
|-------|------|---------|-------------|
| `name` | string | `"Alice Smith"` | Person's name |
| `date` | string | `"1990-03-15"` | Stored birthday date |
| `days_until` | int | `7` | Days until next birthday |
| `age_turning` | int/null | `40` | Age they're turning (null if no birth year) |
| `age_turning_ordinal` | string/null | `"40th"` | Ordinal age string (null if no birth year) |
| `notes` | string | `"Likes cake"` | Notes for this person |
| `id` | string | `"a1b2c3d4"` | Birthday record ID |

## License

MIT
