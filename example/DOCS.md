# Ville_qc_collecte

**Ville_qc_collecte** is a Home Assistant add-on that scrapes the [Ville de Québec Info-Collecte website](https://www.ville.quebec.qc.ca/services/info-collecte/) (using Selenium) to determine the next garbage (ordures/résidus alimentaires) and recycling (recyclage) collection dates. The add-on then publishes these dates as MQTT sensors, making them available in Home Assistant.

---

## How it works

1. **Headless browser (Selenium):**  
   The add-on launches a headless Chromium browser to load the Ville de Québec Info-Collecte page and automatically enters your address.
2. **HTML parsing (BeautifulSoup):**  
   Once the calendar is displayed, the add-on parses the HTML to find upcoming pickup dates for ordures/résidus alimentaires and recyclage.
3. **MQTT sensor publishing:**  
   Using **MQTT Discovery**, the add-on publishes states and attributes for two sensors: 
   - `sensor.collecte_ordures`  
   - `sensor.collecte_recyclage`  
   so Home Assistant can automatically detect and display them.

---

## Installation

1. **Add this repository** to Home Assistant as an Add-on repository:  
   - Go to **Settings** → **Add-ons** → **Add-on Store** → the three dots menu (**⋮**) → **Repositories** → enter this repo's URL.  
   - Or click the button below:

   [![Open your Home Assistant instance and show the add add-on repository dialog with a specific repository URL pre-filled.](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fhome-assistant%2Faddons-example)
2. **Install** the add-on named **Ville_qc_collecte** from your local add-ons list.
3. **Configure** the add-on (address to search, update interval, MQTT settings, etc.).
4. **Start** the add-on and check the logs. You should see it fetching the Info-Collecte calendar and publishing sensor data via MQTT.

---

## Configuration Options

| Key              | Description                                                    | Default                    |
|------------------|----------------------------------------------------------------|----------------------------|
| `address`        | The address to look up                                        | `"123 rue des tulippes"` |
| `update_interval`| How frequently (in seconds) to re-check the Info-Collecte site | `3600` (1 hour)            |
| `mqtt_host`      | The MQTT broker hostname                                      | `"core-mosquitto"`         |
| `mqtt_port`      | The MQTT broker port                                          | `1883`                     |
| `mqtt_username`  | Username for MQTT                                             | `""`                       |
| `mqtt_password`  | Password for MQTT                                             | `""`                       |

---

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
