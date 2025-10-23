import argparse
import json
import os
import time
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional

import requests
import paho.mqtt.client as mqtt
from bs4 import BeautifulSoup

# Selenium (site RSEQ rendu côté client)
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

STATE_FILE = "/data/last_events.json"

# ---------- Utils état (éviter doublons events HA) ----------

def load_last_events() -> Dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[SCRIPT] Erreur chargement état: {e}")
    return {}

def save_last_events(state: Dict) -> None:
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f)
    except Exception as e:
        print(f"[SCRIPT] Erreur sauvegarde état: {e}")

# ---------- Publication MQTT (MQTT Discovery) ----------

def mqtt_discovery_publish(client: mqtt.Client, discovery_prefix: str, sensor_id: str,
                           name: str, device_name: str, icon: str,
                           state: str, attributes: Optional[Dict] = None) -> None:
    base = f"{discovery_prefix}/sensor/{sensor_id}"
    config_topic = f"{base}/config"
    state_topic = f"{base}/state"
    attr_topic = f"{base}/attributes"

    config_payload = {
        "name": name,
        "uniq_id": sensor_id,
        "stat_t": state_topic,
        "json_attr_t": attr_topic,
        "dev": {"name": device_name, "ids": [device_name]},
        "icon": icon
    }
    client.publish(config_topic, json.dumps(config_payload), retain=True, qos=1)
    if attributes is not None:
        client.publish(attr_topic, json.dumps(attributes, ensure_ascii=False), retain=True, qos=0)
    client.publish(state_topic, state, retain=True, qos=0)

# ---------- Création d’événements HA (optionnelle) ----------

def create_event_in_ha(ha_url: str, ha_token: str, ha_calendar_entity: str,
                       start_iso: str, end_iso: str,
                       summary: str, description: str) -> None:
    """
    Appelle le service script.turn_on de HA, qui doit déclencher ton
    script `script.create_calendar_event` acceptant:
    - calendar_entity
    - start_date
    - end_date
    - summary
    - description
    """
    if not (ha_url and ha_token and ha_calendar_entity):
        return

    url = f"{ha_url}/api/services/script/turn_on"
    headers = {"Authorization": f"Bearer {ha_token}", "Content-Type": "application/json"}
    payload = {
        "entity_id": "script.create_calendar_event",
        "variables": {
            "calendar_entity": ha_calendar_entity,
            "start_date": start_iso,
            "end_date": end_iso,
            "summary": summary,
            "description": description,
        }
    }
    r = requests.post(url, headers=headers, json=payload, timeout=20)
    if r.status_code != 200:
        raise RuntimeError(f"HA event error {r.status_code}: {r.text}")

# ---------- Scraping RSEQ ----------

def build_driver() -> webdriver.Chrome:
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--window-size=1366,2400")
    chrome_options.add_argument("--lang=fr-CA")
    chrome_options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    )
    service = Service("/usr/bin/chromedriver")
    return webdriver.Chrome(service=service, options=chrome_options)

def parse_datetime_candidates(date_str: str, time_str: str) -> Optional[datetime]:
    """
    Accepte plusieurs formats vus sur les sites francophones.
    Remplace '19h30' -> '19:30' avant parsing.
    """
    ds = (date_str or "").strip()
    ts = (time_str or "").strip().replace("h", ":").replace("H", ":")
    dt_text = f"{ds} {ts}".strip() if ts else ds

    fmts = [
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%d-%m-%Y %H:%M",
        "%d-%m-%Y",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y",
        "%Y-%m-%d %H:%M:%S",
    ]
    for fmt in fmts:
        try:
            return datetime.strptime(dt_text, fmt)
        except ValueError:
            continue
    return None

def extract_calendar_rows(page_html: str) -> List[Dict]:
    """
    Cible la table #CalendarTable et lit chaque <tr> du <tbody data-bind="foreach: TeamGames">.
    Colonnes (indexées depuis 0) observées:
      0: (blank) | 1: # | 2: Jour | 3: Date | 4: Heure | 5: Visiteur | 6: Résultat
      7: Receveur | 8: (map link) | 9: Endroit
    """
    soup = BeautifulSoup(page_html, "html.parser")
    table = soup.find("table", {"id": "CalendarTable"})
    if not table:
        raise RuntimeError("Table #CalendarTable non trouvée")

    rows: List[Dict] = []
    for tr in table.select("tbody tr"):
        tds = [td.get_text(strip=True) for td in tr.find_all("td")]
        if len(tds) < 9:  # parfois pas de cellule 'mapLink' -> 9 cellules
            continue

        no = tds[1]
        jour = tds[2]
        date_str = tds[3]
        time_str = tds[4]
        visitor = tds[5]
        result  = tds[6]
        home    = tds[7]
        # Endroit peut être en index 9 (avec lien carte) ou 8 (sans lien)
        venue   = tds[9] if len(tds) >= 10 else tds[8]

        dt = parse_datetime_candidates(date_str, time_str) or parse_datetime_candidates(date_str, "")
        dt_iso = dt.isoformat() if dt else None

        rows.append({
            "no": no,
            "jour": jour,
            "date": date_str,
            "time": time_str,
            "datetime": dt_iso,
            "visitor": visitor,
            "result": result,
            "home": home,
            "venue": venue
        })

    return rows

def scrape_team_calendar(team_url: str) -> List[Dict]:
    driver = build_driver()
    try:
        print(f"[SCRIPT] Ouverture: {team_url}")
        driver.get(team_url)

        # Attendre la présence de la section puis scroller dessus (certaines liaisons JS se font au viewport)
        try:
            section = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "ScheduleSection"))
            )
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", section)
            time.sleep(0.4)
        except Exception:
            pass

        # Attendre explicitement la table et au moins 5 lignes
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, "CalendarTable")))
        # Boucle d'attente jusqu'à >= 5 lignes dans tbody (chargement KO/async)
        max_rows = 0
        for _ in range(30):  # ~15s
            rows_now = driver.find_elements(By.CSS_SELECTOR, "#CalendarTable tbody tr")
            max_rows = max(max_rows, len(rows_now))
            if len(rows_now) >= 5:
                break
            time.sleep(0.5)

        print(f"[SCRIPT] Debug: {max_rows} tr détectés dans #CalendarTable (au plus).")

        # Petite marge de sécurité
        time.sleep(0.3)
        html = driver.page_source
        rows = extract_calendar_rows(html)

        if not rows:
            # Dump HTML pour debug si jamais
            try:
                os.makedirs("/share", exist_ok=True)
                with open("/share/rseq_last.html", "w", encoding="utf-8") as f:
                    f.write(html)
                print("[SCRIPT] Aucune ligne parsée — snapshot /share/rseq_last.html écrit.")
            except Exception as e:
                print(f"[SCRIPT] Dump HTML impossible: {e}")

        print(f"[SCRIPT] {len(rows)} lignes de calendrier détectées.")
        return rows
    finally:
        try:
            driver.quit()
        except Exception:
            pass

def find_next_and_upcoming(rows: List[Dict]) -> (Optional[Dict], List[Dict]):
    now = datetime.now()
    future = []
    for r in rows:
        try:
            dt_iso = r.get("datetime")
            if not dt_iso:
                continue
            dt = datetime.fromisoformat(dt_iso)
            if dt >= now:
                future.append(r)
        except Exception:
            continue
    future.sort(key=lambda x: x["datetime"])
    return (future[0] if future else None), future[:5]

# ---------- Main ----------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--team_url", required=True)
    parser.add_argument("--mqtt_host", default="core-mosquitto")
    parser.add_argument("--mqtt_port", default="1883")
    parser.add_argument("--mqtt_user", default="")
    parser.add_argument("--mqtt_pass", default="")
    parser.add_argument("--discovery_prefix", default="homeassistant")
    # Optionnel: création d’événements dans HA
    parser.add_argument("--ha_url", default="")
    parser.add_argument("--ha_token", default="")
    parser.add_argument("--ha_calendar_entity", default="")
    args = parser.parse_args()

    TEAM_URL = args.team_url
    MQTT_HOST = args.mqtt_host
    MQTT_PORT = int(args.mqtt_port)
    MQTT_USER = args.mqtt_user
    MQTT_PASS = args.mqtt_pass
    DISCOVERY_PREFIX = args.discovery_prefix
    HA_URL = args.ha_url
    HA_TOKEN = args.ha_token
    HA_CALENDAR_ENTITY = args.ha_calendar_entity

    print(f"[SCRIPT] Démarrage RSEQ avec team_url={TEAM_URL}")

    # Connexion MQTT
    client = mqtt.Client(client_id="rseq_team_calendar")
    if MQTT_USER:
        client.username_pw_set(MQTT_USER, MQTT_PASS)

    try:
        client.connect(MQTT_HOST, MQTT_PORT, 60)
        client.loop_start()
        print("[SCRIPT] Connecté à MQTT.")
    except Exception as e:
        print(f"[ERREUR] MQTT: {e}")
        return

    status = "success"
    next_game = None
    upcoming: List[Dict] = []

    try:
        rows = scrape_team_calendar(TEAM_URL)
        ng, up = find_next_and_upcoming(rows)
        next_game = ng
        upcoming = up
        if not rows:
            status = "error: calendrier vide"
    except Exception as e:
        status = f"error: {e}"
        print(f"[SCRIPT] ERREUR: {e}")

    # Création éventuelle d’un event HA (si next_game)
    if next_game and HA_URL and HA_TOKEN and HA_CALENDAR_ENTITY:
        last = load_last_events()
        ng_key = next_game.get("datetime")
        try:
            if last.get("last_next_game") != ng_key:
                summary = f"{next_game['visitor']} @ {next_game['home']} (RSEQ)"
                start_iso = next_game["datetime"]
                try:
                    dt_start = datetime.fromisoformat(start_iso)
                    dt_end = (dt_start + timedelta(hours=2)).isoformat()
                except Exception:
                    dt_end = start_iso
                description = f"Endroit: {next_game.get('venue','-')} | Résultat: {next_game.get('result','')}"
                create_event_in_ha(HA_URL, HA_TOKEN, HA_CALENDAR_ENTITY, start_iso, dt_end, summary, description)
                last["last_next_game"] = ng_key
                save_last_events(last)
            else:
                print("[SCRIPT] Événement HA déjà créé pour ce prochain match.")
        except Exception as e:
            print(f"[SCRIPT] Erreur création événement HA: {e}")

    # Publication MQTT des sensors
    device_name = "RSEQ Team Calendar"
    # 1) status
    mqtt_discovery_publish(
        client, DISCOVERY_PREFIX, "rseq_team_status",
        "RSEQ – Status", device_name, "mdi:information",
        status, {}
    )
    # 2) prochain match
    if next_game:
        state_str = f"{next_game['date']} {next_game['time']} – {next_game['visitor']} @ {next_game['home']}"
    else:
        state_str = "Aucun match à venir"
    attributes = {
        "next_game": next_game,
        "upcoming": upcoming,
        "updated": datetime.now().isoformat()
    }
    mqtt_discovery_publish(
        client, DISCOVERY_PREFIX, "rseq_team_next_game",
        "RSEQ – Prochain match (équipe)", device_name, "mdi:calendar-account",
        state_str, attributes
    )

    client.loop_stop()
    client.disconnect()
    print("[SCRIPT] Terminé.")

if __name__ == "__main__":
    main()
