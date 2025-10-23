import argparse
import json
import os
import time
from datetime import datetime, date, timedelta

import requests  # Pour effectuer des requêtes HTTP
import paho.mqtt.client as mqtt

# Selenium
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from bs4 import BeautifulSoup

# Fichier pour mémoriser l'état des événements créés
STATE_FILE = "/data/last_events.json"

def load_last_events():
    """Charge les dernières dates d'événements créés depuis le fichier d'état."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[SCRIPT] Erreur lors du chargement de l'état: {e}")
            return {}
    return {}

def save_last_events(state):
    """Enregistre l'état (dates des événements créés) dans le fichier."""
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f)
    except Exception as e:
        print(f"[SCRIPT] Erreur lors de l'enregistrement de l'état: {e}")

def publish_sensor(client, topic_base, sensor_name, state, attributes=None):
    """
    Publie un capteur via MQTT Discovery.
    """
    config_topic = f"{topic_base}/{sensor_name}/config"
    state_topic = f"{topic_base}/{sensor_name}/state"
    attr_topic = f"{topic_base}/{sensor_name}/attributes"

    device_name = "VilleQCCollecte"
    unique_id = f"ville_qc_{sensor_name}"

    config_payload = {
        "name": f"Collecte {sensor_name}",
        "state_topic": state_topic,
        "unique_id": unique_id,
        "device": {
            "identifiers": ["ville_qc_collecte_device"],
            "name": device_name,
            "manufacturer": "Ville de Québec"
        }
    }

    if attributes:
        config_payload["json_attributes_topic"] = attr_topic
        client.publish(attr_topic, json.dumps(attributes), retain=True)

    client.publish(config_topic, json.dumps(config_payload), retain=True)
    client.publish(state_topic, state, retain=True)

def create_event_in_ha(ha_url, ha_token, ha_calendar_entity, event_date, event_summary, event_description):
    """
    Appelle l'API Home Assistant pour créer un événement en appelant le script 'create_calendar_event'.
    Le script HA doit être configuré pour accepter les variables :
      - calendar_entity
      - start_date
      - end_date
      - summary
      - description
    Ici, nous utilisons le service script.turn_on.
    """
    url = f"{ha_url}/api/services/script/turn_on"
    headers = {
        "Authorization": f"Bearer {ha_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "entity_id": "script.create_calendar_event",
        "variables": {
            "calendar_entity": ha_calendar_entity,
            "start_date": event_date,
            "end_date": event_date,
            "summary": event_summary,
            "description": event_description,
        }
    }
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code != 200:
        raise Exception(f"Erreur lors de la création de l'événement : {response.status_code}: {response.text}")
    print(f"[SCRIPT] Événement créé dans HA: {event_summary} pour le {event_date}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--address", required=True)
    parser.add_argument("--mqtt_host", default="core-mosquitto")
    parser.add_argument("--mqtt_port", default="1883")
    parser.add_argument("--mqtt_user", default="")
    parser.add_argument("--mqtt_pass", default="")
    # Nouveaux arguments pour l'intégration HA
    parser.add_argument("--ha_url", default="")
    parser.add_argument("--ha_token", default="")
    parser.add_argument("--ha_calendar_entity", default="")

    args = parser.parse_args()
    ADDRESS = args.address
    MQTT_HOST = args.mqtt_host
    MQTT_PORT = int(args.mqtt_port)
    MQTT_USER = args.mqtt_user
    MQTT_PASS = args.mqtt_pass
    HA_URL = args.ha_url
    HA_TOKEN = args.ha_token
    HA_CALENDAR_ENTITY = args.ha_calendar_entity

    print(f"[SCRIPT] Démarrage avec adresse={ADDRESS}")

    # Connexion MQTT
    client = mqtt.Client()
    if MQTT_USER:
        client.username_pw_set(MQTT_USER, MQTT_PASS)

    try:
        client.connect(MQTT_HOST, MQTT_PORT, 60)
        client.loop_start()
        print("[SCRIPT] Connecté à MQTT.")
    except Exception as e:
        print(f"[ERREUR] Impossible de se connecter à MQTT: {e}")
        return

    status = "success"
    ordures_dates = []
    recyclage_dates = []
    today = date.today()

    try:
        # Selenium en mode headless
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--no-sandbox")
        service = Service("/usr/bin/chromedriver")

        driver = webdriver.Chrome(service=service, options=chrome_options)
        url_main = "https://www.ville.quebec.qc.ca/services/info-collecte/"
        print(f"[SCRIPT] Accès: {url_main}")
        driver.get(url_main)

        # Remplir le champ d'adresse
        field = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((
                By.NAME,
                "ctl00$ctl00$contenu$texte_page$ucInfoCollecteRechercheAdresse$RechercheAdresse$txtNomRue"
            ))
        )
        field.clear()
        field.send_keys(ADDRESS)

        # Cliquer sur le bouton de recherche
        search_button = driver.find_element(
            By.NAME,
            "ctl00$ctl00$contenu$texte_page$ucInfoCollecteRechercheAdresse$RechercheAdresse$BtnRue"
        )
        search_button.click()

        # Attendre le calendrier
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table.calendrier"))
        )
        print("[SCRIPT] Calendrier détecté.")

        soup = BeautifulSoup(driver.page_source, "html.parser")
        tables = soup.find_all("table", class_="calendrier")
        if not tables:
            raise RuntimeError("Aucune table 'calendrier' trouvée !")

        # Mapping de mois (en minuscule) -> numéro
        months_map = {
            "janvier": 1, "février": 2, "fevrier": 2, "mars": 3,
            "avril": 4, "mai": 5, "juin": 6, "juillet": 7,
            "aout": 8, "août": 8, "septembre": 9, "octobre": 10,
            "novembre": 11, "décembre": 12
        }

        for table in tables:
            caption = table.find("caption")
            caption_txt = caption.get_text(strip=True).lower() if caption else ""
            parts = caption_txt.split()
            if len(parts) >= 2:
                month_str = parts[0]
                year_str = parts[1]
                month_num = months_map.get(month_str, 0)
                year_num = int(year_str) if year_str.isdigit() else today.year
            else:
                month_num = 0
                year_num = today.year

            for td in table.find_all("td"):
                date_p = td.find("p", class_="date")
                if not date_p:
                    continue
                day_str = date_p.get_text(strip=True)
                if not day_str.isdigit():
                    continue
                day_num = int(day_str)
                try:
                    dt = datetime(year_num, month_num, day_num).date()
                except:
                    continue

                # Traitement de toutes les icônes présentes (ordures et/ou recyclage)
                for img in td.select("p.img img"):
                    alt = img.get("alt", "").lower()
                    if "ordures" in alt:
                        ordures_dates.append(dt)
                    if "recyclage" in alt:
                        recyclage_dates.append(dt)

        if not ordures_dates and not recyclage_dates:
            raise ValueError("Aucune collecte trouvée pour l'adresse donnée.")

        def next_future(dates):
            fut = [d for d in dates if d >= today]
            return min(fut) if fut else None

        next_ordures = next_future(ordures_dates)
        next_recyclage = next_future(recyclage_dates)
        str_ordures = next_ordures.isoformat() if next_ordures else "N/A"
        str_recyclage = next_recyclage.isoformat() if next_recyclage else "N/A"
        print(f"[SCRIPT] Prochaine ordures = {str_ordures}, recyclage = {str_recyclage}")
    except Exception as e:
        status = f"error: {e}"
        print(f"[SCRIPT] ÉRREUR: {e}")
    finally:
        try:
            driver.quit()
        except:
            pass

    # Gestion de l'état pour éviter les doublons
    last_events = load_last_events()

    if HA_URL and HA_TOKEN and HA_CALENDAR_ENTITY and status == "success":
        if next_ordures:
            if last_events.get("ordures") != next_ordures.isoformat():
                try:
                    create_event_in_ha(HA_URL, HA_TOKEN, HA_CALENDAR_ENTITY,
                                       next_ordures.isoformat(),
                                       "Collecte ordures",
                                       f"Prochaine collecte d'ordures prévue le {next_ordures.isoformat()}")
                    last_events["ordures"] = next_ordures.isoformat()
                except Exception as e:
                    print(f"Erreur lors de la création de l'événement d'ordures: {e}")
            else:
                print("[SCRIPT] L'événement d'ordures est déjà à jour.")
        if next_recyclage:
            if last_events.get("recyclage") != next_recyclage.isoformat():
                try:
                    create_event_in_ha(HA_URL, HA_TOKEN, HA_CALENDAR_ENTITY,
                                       next_recyclage.isoformat(),
                                       "Collecte recyclage",
                                       f"Prochaine collecte de recyclage prévue le {next_recyclage.isoformat()}")
                    last_events["recyclage"] = next_recyclage.isoformat()
                except Exception as e:
                    print(f"Erreur lors de la création de l'événement de recyclage: {e}")
            else:
                print("[SCRIPT] L'événement de recyclage est déjà à jour.")
        save_last_events(last_events)

    # Publication MQTT des capteurs
    topic_base = "homeassistant/sensor/ville_qc_collecte"
    publish_sensor(client, topic_base, "status", state=status, attributes={})
    if status.startswith("error"):
        publish_sensor(client, topic_base, "ordures", "error", attributes={})
    else:
        publish_sensor(client, topic_base, "ordures", str_ordures, attributes={
            "all_dates": [d.isoformat() for d in sorted(ordures_dates)]
        })
    if status.startswith("error"):
        publish_sensor(client, topic_base, "recyclage", "error", attributes={})
    else:
        publish_sensor(client, topic_base, "recyclage", str_recyclage, attributes={
            "all_dates": [d.isoformat() for d in sorted(recyclage_dates)]
        })

    client.loop_stop()
    client.disconnect()
    print("[SCRIPT] Terminé.")

if __name__ == "__main__":
    main()
