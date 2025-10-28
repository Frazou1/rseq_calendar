import argparse
import json
import os
import time
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple

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
LOCAL_TZ = "America/Toronto"

# ---------- Utils ----------

def slugify(name: str) -> str:
    import unicodedata
    value = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
    return value or "rseq"

def to_local_iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    try:
        import pytz
        tz = pytz.timezone(LOCAL_TZ)
        if dt.tzinfo is None:
            dt = tz.localize(dt)
        else:
            dt = dt.astimezone(tz)
        return dt.isoformat()
    except Exception:
        # Fallback: ISO naive
        return dt.isoformat()

def now_local() -> datetime:
    try:
        import pytz
        tz = pytz.timezone(LOCAL_TZ)
        return datetime.now(tz)
    except Exception:
        return datetime.now()

# ---------- Persistance anti-doublons (événements HA) ----------

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

# ---------- MQTT (Discovery) ----------

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
    # Flags depuis l'env (Dockerfile exporte CHROMIUM_FLAGS)
    env_flags = os.getenv("CHROMIUM_FLAGS", "")
    if env_flags:
        for flag in env_flags.split():
            chrome_options.add_argument(flag)
    else:
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
    ds = (date_str or "").strip()
    ts = (time_str or "").strip().replace("h", ":").replace("H", ":")

    # Normaliser cas "19h" => "19:00"
    if ts and re.fullmatch(r"^\d{1,2}$", ts):
        ts = f"{ts}:00"

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
    Table #CalendarTable ; colonnes typiques:
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
        if len(tds) < 9:
            continue

        no = tds[1]
        jour = tds[2]
        date_str = tds[3]
        time_str = tds[4]
        visitor = tds[5]
        result  = tds[6]
        home    = tds[7]
        venue   = tds[9] if len(tds) >= 10 else tds[8]

        dt = parse_datetime_candidates(date_str, time_str) or parse_datetime_candidates(date_str, "")
        dt_iso = to_local_iso(dt) if dt else None

        rows.append({
            "no": no,
            "jour": jour,
            "date": date_str,
            "time": time_str,
            "datetime": dt_iso,   # ISO local avec offset si possible
            "visitor": visitor,
            "result": result,
            "home": home,
            "venue": venue
        })

    return rows

def extract_standings_rows(page_html: str) -> List[Dict]:
    """
    Parse le tableau #standingsTable. On lit l'en-tête pour détecter
    dynamiquement les colonnes disponibles (certaines peuvent être cachées).
    On tente de récupérer au minimum:
      Pos, Équipe, MJ, V, D, N, PP, PC, MOY, PTS Eth (PES), PTS tot (PTS)
    Retourne une liste de dicts triée par 'pos' asc si possible.
    """
    soup = BeautifulSoup(page_html, "html.parser")
    table = soup.find("table", {"id": "standingsTable"})
    if not table:
        return []

    # Récupérer les headers (même si certains ont display:none)
    header_cells = table.select("thead tr th")
    headers = [h.get_text(strip=True) for h in header_cells]

    # Helper pour trouver l'index d'une colonne par libellé (tolérant)
    def find_idx(names: List[str]) -> Optional[int]:
        for i, h in enumerate(headers):
            h_norm = h.lower()
            for n in names:
                if n in h_norm:
                    return i
        return None

    idx_pos   = find_idx(["pos"])
    idx_team  = find_idx(["équipe", "equipe", "team"])
    idx_mj    = find_idx(["mj"])
    idx_v     = find_idx([" v", "wins"])  # espace avant v évite match 'visiteur'
    idx_d     = find_idx([" d", "losses"])
    idx_n     = find_idx([" n", "draws"])
    idx_pp    = find_idx(["pp", "points for"])
    idx_pc    = find_idx(["pc", "points againts", "points against", "points againsts"])
    idx_moy   = find_idx(["moy"])
    idx_pes   = find_idx(["pts eth", "pes"])
    idx_pts   = find_idx(["pts tot", "pts", "total points"])

    rows: List[Dict] = []
    for tr in table.select("tbody tr"):
        tds = [td.get_text(strip=True) for td in tr.find_all("td")]
        if not tds:
            continue

        def at(i: Optional[int]) -> Optional[str]:
            return tds[i] if i is not None and i < len(tds) else None

        entry = {
            "pos":   at(idx_pos),
            "team":  at(idx_team),
            "MJ":    at(idx_mj),
            "V":     at(idx_v),
            "D":     at(idx_d),
            "N":     at(idx_n),
            "PP":    at(idx_pp),
            "PC":    at(idx_pc),
            "MOY":   at(idx_moy),
            "PES":   at(idx_pes),
            "PTS":   at(idx_pts),
        }

        # Filtre minimal: on garde les lignes qui ont au moins pos + team
        if entry["pos"] and entry["team"]:
            rows.append(entry)

    # Try tri par position numérique si possible
    def pos_key(e):
        try:
            return int(e["pos"])
        except Exception:
            return 999999

    rows.sort(key=pos_key)
    return rows

def scrape_team_calendar(team_url: str, driver: webdriver.Chrome) -> Tuple[List[Dict], List[Dict]]:
    print(f"[SCRIPT] Ouverture: {team_url}")
    driver.get(team_url)

    # Attente section / table du calendrier
    try:
        section = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "ScheduleSection"))
        )
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", section)
        time.sleep(0.4)
    except Exception:
        pass

    WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, "CalendarTable")))

    max_rows = 0
    for _ in range(30):
        rows_now = driver.find_elements(By.CSS_SELECTOR, "#CalendarTable tbody tr")
        max_rows = max(max_rows, len(rows_now))
        if len(rows_now) >= 5:
            break
        time.sleep(0.5)

    print(f"[SCRIPT] Debug: {max_rows} tr détectés dans #CalendarTable (au plus).")
    time.sleep(0.3)
    html = driver.page_source
    rows = extract_calendar_rows(html)

    # === Standings ===
    try:
        standings_sec = driver.find_element(By.ID, "StandingsSection")
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", standings_sec)
        time.sleep(0.2)
    except Exception:
        pass

    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.ID, "standingsTable"))
        )
        html = driver.page_source  # refresh après éventuelle maj DOM
        standings = extract_standings_rows(html)
    except Exception:
        standings = []

    if not rows:
        try:
            os.makedirs("/share", exist_ok=True)
            with open("/share/rseq_last.html", "w", encoding="utf-8") as f:
                f.write(html)
            print("[SCRIPT] Aucune ligne parsée — snapshot /share/rseq_last.html écrit.")
        except Exception as e:
            print(f"[SCRIPT] Dump HTML impossible: {e}")

    print(f"[SCRIPT] {len(rows)} lignes de calendrier détectées.")
    print(f"[SCRIPT] {len(standings)} lignes de standings détectées.")
    return rows, standings

def find_next_and_upcoming(rows: List[Dict]) -> Tuple[Optional[Dict], List[Dict]]:
    now = now_local()
    future = []
    for r in rows:
        try:
            dt_iso = r.get("datetime")
            if not dt_iso:
                continue
            dt = datetime.fromisoformat(dt_iso)
            # Si ISO sans tz : considérer local
            if dt.tzinfo is None:
                # best effort: on colle l'offset du now local
                try:
                    import pytz
                    tz = pytz.timezone(LOCAL_TZ)
                    dt = tz.localize(dt)
                except Exception:
                    pass
            if dt >= now:
                future.append(r)
        except Exception:
            continue
    future.sort(key=lambda x: x["datetime"])
    return (future[0] if future else None), future[:5]

# ---------- Main (multi-équipes) ----------

def main():
    parser = argparse.ArgumentParser()
    # Nouveau: multi-équipes via JSON compact
    parser.add_argument("--teams-json", default="")
    parser.add_argument("--entity_prefix", default="rseq")

    # Compat legacy
    parser.add_argument("--team_url", default="")

    # MQTT / HA
    parser.add_argument("--mqtt_host", default="core-mosquitto")
    parser.add_argument("--mqtt_port", default="1883")
    parser.add_argument("--mqtt_user", default="")
    parser.add_argument("--mqtt_pass", default="")
    parser.add_argument("--discovery_prefix", default="homeassistant")
    parser.add_argument("--ha_url", default="")
    parser.add_argument("--ha_token", default="")
    parser.add_argument("--ha_calendar_entity", default="")
    args = parser.parse_args()

    # Teams à traiter
    teams: List[Dict[str, str]] = []
    if args.teams_json:
        try:
            teams = json.loads(args.teams_json)
        except Exception as e:
            print(f"[ERREUR] teams-json invalide: {e}")
            teams = []
    elif args.team_url:
        teams = [{"name": "default", "team_url": args.team_url}]
    else:
        print("[ERREUR] Aucune équipe fournie (teams-json ou team_url).")
        return

    entity_prefix = args.entity_prefix.strip() or "rseq"

    MQTT_HOST = args.mqtt_host
    MQTT_PORT = int(args.mqtt_port)
    MQTT_USER = args.mqtt_user
    MQTT_PASS = args.mqtt_pass
    DISCOVERY_PREFIX = args.discovery_prefix
    HA_URL = args.ha_url
    HA_TOKEN = args.ha_token
    HA_CALENDAR_ENTITY = args.ha_calendar_entity

    # Connexion MQTT
    client = mqtt.Client(client_id=f"rseq_team_calendar_{int(time.time())}")
    if MQTT_USER:
        client.username_pw_set(MQTT_USER, MQTT_PASS)
    try:
        client.connect(MQTT_HOST, MQTT_PORT, 60)
        client.loop_start()
        print("[SCRIPT] Connecté à MQTT.")
    except Exception as e:
        print(f"[ERREUR] MQTT: {e}")
        return

    # Driver Selenium unique pour toutes les équipes (dans ce run)
    driver = build_driver()

    # Persistance événements
    last = load_last_events()

    try:
        for team in teams:
            name = team.get("name") or "default"
            url = team.get("team_url") or ""
            if not url:
                print(f"[WARN] Équipe '{name}' sans team_url — ignorée.")
                continue

            slug = slugify(name)
            device_name = f"RSEQ – {name}"

            print(f"[SCRIPT] Traitement équipe: {name} ({url})")
            status = "success"
            next_game = None
            upcoming: List[Dict] = []
            standings: List[Dict] = []

            try:
                rows, standings = scrape_team_calendar(url, driver)
                ng, up = find_next_and_upcoming(rows)
                next_game = ng
                upcoming = up
                if not rows:
                    status = "error: calendrier vide"
            except Exception as e:
                status = f"error: {e}"
                print(f"[SCRIPT] ERREUR[{name}]: {e}")

            # Event HA optionnel (anti-doublon par équipe)
            if next_game and HA_URL and HA_TOKEN and HA_CALENDAR_ENTITY:
                try:
                    ng_key = f"{slug}:{next_game.get('datetime')}"
                    if last.get(slug) != ng_key:
                        summary = f"{next_game['visitor']} @ {next_game['home']} (RSEQ)"
                        start_iso = next_game["datetime"]
                        try:
                            dt_start = datetime.fromisoformat(start_iso)
                            if dt_start.tzinfo is None:
                                # local par défaut
                                end_iso = to_local_iso(dt_start + timedelta(hours=2))
                                start_iso = to_local_iso(dt_start)
                            else:
                                end_iso = (dt_start + timedelta(hours=2)).isoformat()
                        except Exception:
                            end_iso = start_iso
                        description = f"Endroit: {next_game.get('venue','-')} | Résultat: {next_game.get('result','')}"
                        create_event_in_ha(HA_URL, HA_TOKEN, HA_CALENDAR_ENTITY, start_iso, end_iso, summary, description)
                        last[slug] = ng_key
                        save_last_events(last)
                    else:
                        print(f"[SCRIPT] Événement HA déjà créé pour '{name}'.")
                except Exception as e:
                    print(f"[SCRIPT] Erreur création événement HA [{name}]: {e}")

            # Publication MQTT des sensors (1 équipe = 3 sensors)
            # 1) status
            sensor_id_status = f"{entity_prefix}_{slug}_status"
            mqtt_discovery_publish(
                client, DISCOVERY_PREFIX, sensor_id_status,
                f"RSEQ – Statut ({name})", device_name, "mdi:information",
                status, {"team_url": url, "last_updated": now_local().isoformat()}
            )

            # 2) prochain match
            if next_game:
                state_str = f"{next_game['date']} {next_game['time']} – {next_game['visitor']} @ {next_game['home']}"
            else:
                state_str = "Aucun match à venir"

            attributes = {
                "team": name,
                "team_url": url,
                "next_game": next_game,
                "upcoming": upcoming,
                "updated": now_local().isoformat()
            }
            sensor_id_next = f"{entity_prefix}_{slug}_next_game"
            mqtt_discovery_publish(
                client, DISCOVERY_PREFIX, sensor_id_next,
                f"RSEQ – Prochain match ({name})", device_name, "mdi:calendar-account",
                state_str, attributes
            )

            # 3) standings (classement)
            def fmt_team_row(r):
                pts = r.get("PTS") or r.get("PES") or "-"
                return f"{r.get('pos','?')}) {r.get('team','?')} ({pts} pts)"

            if standings:
                top = " | ".join(fmt_team_row(r) for r in standings[:3])
                standings_state = top if top else "Classement disponible"
            else:
                standings_state = "Classement indisponible"

            sensor_id_stand = f"{entity_prefix}_{slug}_standings"
            mqtt_discovery_publish(
                client, DISCOVERY_PREFIX, sensor_id_stand,
                f"RSEQ – Classement ({name})", device_name, "mdi:trophy",
                standings_state,
                {
                    "team": name,
                    "team_url": url,
                    "standings": standings,
                    "updated": now_local().isoformat()
                }
            )

        print("[SCRIPT] Tous les teams traités.")
    finally:
        try:
            driver.quit()
        except Exception:
            pass
        client.loop_stop()
        client.disconnect()
        print("[SCRIPT] Terminé.")

if __name__ == "__main__":
    main()
