# Ville_qc_collecte

**Ville_qc_collecte** is a Home Assistant add-on that scrapes the [Ville de Québec Info-Collecte website](https://www.ville.quebec.qc.ca/services/info-collecte/) (using Selenium) to determine the next garbage (ordures/résidus alimentaires) and recycling (recyclage) collection dates. The add-on then publishes these dates as MQTT sensors, making them available in Home Assistant.  
**New features:**  
- Automatic creation of calendar events in Home Assistant via the API REST.  
- Prevention of duplicate events using persistent state storage.  
- Updated MQTT client initialization using the new callback API (ensure paho-mqtt is up-to-date).

---

## How it works

1. **Headless browser (Selenium):**  
   The add-on launches a headless Chromium browser to load the Ville de Québec Info-Collecte page and automatically enter your address.

2. **HTML parsing (BeautifulSoup):**  
   Once the calendar is displayed, the add-on parses the HTML to find upcoming pickup dates for garbage (ordures/résidus alimentaires) and recycling (recyclage).

3. **MQTT sensor publishing:**  
   Using **MQTT Discovery**, the add-on publishes states and attributes for two sensors:
   - `sensor.collecte_ordures`
   - `sensor.collecte_recyclage`  
   so that Home Assistant can automatically detect and display them.

4. **Calendar Event Creation:**  
   If Home Assistant integration is configured, the add-on calls a HA script (via the API REST using `script.turn_on`) to create calendar events for the upcoming collection dates.  
   To avoid duplicates, the add-on saves the last event dates in a persistent file (`/data/last_events.json`).

5. **Updated MQTT Client Initialization:**  
   The MQTT client is now initialized with the new callback API (CallbackAPIVersion) to suppress deprecation warnings. (Make sure your Dockerfile installs a recent version of paho-mqtt.)

---

## Installation

1. **Add this repository** to Home Assistant as an Add-on repository:  
   - Go to **Settings** → **Add-ons** → **Add-on Store** → the three dots menu (**⋮**) → **Repositories** → enter this repo's URL.  
   - Or click the button below:

   [![Open your Home Assistant instance and show the add add-on repository dialog with a specific repository URL pre-filled.](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fhome-assistant%2Faddons-example)

2. **Install** the add-on named **Ville_qc_collecte** from your local add-ons list.
3. **Configure** the add-on with the following options:
   - **Address to search:** The address used for lookup.
   - **Update interval:** How frequently (in seconds) the site is re-checked.
   - **MQTT settings:** MQTT host, port, username, and password.
   - **Home Assistant Calendar integration:**  
     - `ha_url` (e.g., `"http://homeassistant.local:8123"`)
     - `ha_token` (your long-lived access token)
     - `ha_calendar_entity` (e.g., `"calendar.mon_calendrier"`)
4. **Start** the add-on and check the logs. You should see it fetching the Info-Collecte calendar, publishing MQTT sensor data, and (if configured) creating calendar events in HA.

---

## Configuration Options

| Key                  | Description                                                                                      | Default                         |
|----------------------|--------------------------------------------------------------------------------------------------|---------------------------------|
| `address`            | The address to look up                                                                           | `"123 street"`                  |
| `update_interval`    | How frequently (in seconds) to re-check the Info-Collecte site                                   | `3600` (1 hour)                 |
| `mqtt_host`          | The MQTT broker hostname                                                                         | `"core-mosquitto"`              |
| `mqtt_port`          | The MQTT broker port                                                                             | `1883`                          |
| `mqtt_username`      | Username for MQTT                                                                                | `""`                            |
| `mqtt_password`      | Password for MQTT                                                                                | `""`                            |
| `ha_url`             | URL of your Home Assistant instance (for creating calendar events)                               | `"http://homeassistant.local:8123"` |
| `ha_token`           | Long-lived access token for the Home Assistant API                                               | `""`                            |
| `ha_calendar_entity` | The calendar entity ID in Home Assistant where events will be created                             | `"calendar.mon_calendrier"`     |

---

## Automation Example

```yaml
alias: Alerte collecte en erreur
trigger:
  - platform: state
    entity_id: sensor.collecte_status
    to: "error"
action:
  - service: notify.persistent_notification
    data:
      title: "Ville QC Collecte"
      message: "Le scraping has failed."
```

## Script to create and call create_calendar_event

Creating Calendar Events
When HA integration options are provided, the add-on calls an HA script to create calendar events for garbage and recycling collections. To enable this feature, you must define a script in Home Assistant (e.g. script.create_calendar_event) that accepts the following variables:

-calendar_entity

-start_date

-end_date

-summary

-description

```
  alias: "Create Calendar Event"
  mode: restart
  fields:
    calendar_entity:
      description: "The calendar entity"
      example: "calendar.mon_calendrier"
    start_date:
      description: "Event start date (YYYY-MM-DD)"
      example: "2025-01-01"
    end_date:
      description: "Event end date (YYYY-MM-DD)"
      example: "2025-01-01"
    summary:
      description: "Event summary"
      example: "Collecte ordures"
    description:
      description: "Event description"
      example: "Next garbage collection on 2025-01-01"
  sequence:
    - service: calendar.create_event
      data_template:
        entity_id: "{{ calendar_entity }}"
        start_date_time: "{{ start_date }}T07:00:00"
        end_date_time: "{{ end_date }}T07:05:59"
        summary: "{{ summary }}"
        description: "{{ description }}"
```

## Architectures

![Supports aarch64 Architecture][aarch64-shield]
![Supports amd64 Architecture][amd64-shield]
![Supports armhf Architecture][armhf-shield]
![Supports armv7 Architecture][armv7-shield]
![Supports i386 Architecture][i386-shield]

---

## Community & Support

- [Home Assistant Community](https://community.home-assistant.io/) – For questions, setup tips, or to share configurations.
- [Ville de Québec Info-Collecte](https://www.ville.quebec.qc.ca/services/info-collecte/) – Official site with waste collection schedules.

---

<!--
Notes for developers or advanced instructions can remain hidden here as comments if desired.
-->

[aarch64-shield]: https://img.shields.io/badge/aarch64-yes-green.svg
[amd64-shield]: https://img.shields.io/badge/amd64-yes-green.svg
[armhf-shield]: https://img.shields.io/badge/armhf-yes-green.svg
[armv7-shield]: https://img.shields.io/badge/armv7-yes-green.svg
[i386-shield]: https://img.shields.io/badge/i386-yes-green.svg
