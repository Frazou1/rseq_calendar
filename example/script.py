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
        return dt.isoformat()

def now_local() -> datetime:
    try:
        import pytz
        tz = pytz.timezone(LOCAL_TZ)
        return datetime.now(tz)
    except Exception:
        return datetime.now()

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
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36")
    service = Service("/usr/bin/chromedriver")
    return webdriver.Chrome(service=service, options=chrome_options)

def parse_datetime_candidates(date_str: str, time_str: str) -> Optional[datetime]:
    ds = (date_str or "").strip()
    ts = (time_str or "").strip().replace("h", ":").replace("H", ":")
    if ts and re.fullmatch(r"^\d{1,2}$", ts):
        ts = f"{ts}:00"
    dt_text = f"{ds} {ts}".strip() if ts else ds
    fmts = ["%Y-%m-%d %H:%M", "%Y-%m-%d", "%d-%m-%Y %H:%M", "%d-%m-%Y",
            "%d/%m/%Y %H:%M", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S"]
    for fmt in fmts:
        try:
            return datetime.strptime(dt_text, fmt)
        except ValueError:
            continue
    return None

def extract_calendar_rows(page_html: str) -> List[Dict]:
    soup = BeautifulSoup(page_html, "html.parser")
    table = soup.find("table", {"id": "CalendarTable"})
    if not table:
        raise RuntimeError("Table #CalendarTable non trouvée")
    rows = []
    for tr in table.select("tbody tr"):
        tds = [td.get_text(strip=True) for td in tr.find_all("td")]
        if len(tds) < 9:
            continue
        no, jour, date_str, time_str, visitor, result, home = tds[1:8]
        venue = tds[9] if len(tds) >= 10 else tds[8]
        dt = parse_datetime_candidates(date_str, time_str) or parse_datetime_candidates(date_str, "")
        dt_iso = to_local_iso(dt) if dt else None
        rows.append({
            "no": no, "jour": jour, "date": date_str, "time": time_str,
            "datetime": dt_iso, "visitor": visitor, "result": result,
            "home": home, "venue": venue
        })
    return rows

def extract_standings_rows(page_html: str) -> List[Dict]:
    soup = BeautifulSoup(page_html, "html.parser")
    table = soup.find("table", {"id": "standingsTable"})
    if not table:
        return []
    headers = [h.get_text(strip=True) for h in table.select("thead tr th")]
    def find_idx(names):
        for i, h in enumerate(headers):
            h_norm = h.lower()
            for n in names:
                if n in h_norm:
                    return i
        return None
    idx_pos = find_idx(["pos"])
    idx_team = find_idx(["équipe", "equipe", "team"])
    idx_mj = find_idx(["mj"])
    idx_v = find_idx([" v", "wins"])
    idx_d = find_idx([" d", "losses"])
    idx_n = find_idx([" n", "draws"])
    idx_pp = find_idx(["pp", "points for"])
    idx_pc = find_idx(["pc", "points against"])
    idx_moy = find_idx(["moy"])
    idx_pes = find_idx(["pts eth", "pes"])
    idx_pts = find_idx(["pts tot", "pts", "total points"])
    rows = []
    for tr in table.select("tbody tr"):
        tds = [td.get_text(strip=True) for td in tr.find_all("td")]
        if not tds:
            continue
        def at(i): return tds[i] if i is not None and i < len(tds) else None
        entry = {
            "pos": at(idx_pos), "team": at(idx_team), "MJ": at(idx_mj),
            "V": at(idx_v), "D": at(idx_d), "N": at(idx_n),
            "PP": at(idx_pp), "PC": at(idx_pc), "MOY": at(idx_moy),
            "PES": at(idx_pes), "PTS": at(idx_pts),
        }
        if entry["pos"] and entry["team"]:
            rows.append(entry)
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
    WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, "CalendarTable")))
    html = driver.page_source
    rows = extract_calendar_rows(html)
    try:
        standings = extract_standings_rows(html)
    except Exception:
        standings = []
    print(f"[SCRIPT] {len(rows)} matchs, {len(standings)} standings.")
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
            if dt.tzinfo is None:
                import pytz
                tz = pytz.timezone(LOCAL_TZ)
                dt = tz.localize(dt)
            if dt >= now:
                future.append(r)
        except Exception:
            continue
    future.sort(key=lambda x: x["datetime"])
    return (future[0] if future else None), future[:5]

# ---------- Main ----------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--teams-json", default="")
    parser.add_argument("--entity_prefix", default="rseq")
    parser.add_argument("--team_url", default="")
    parser.add_argument("--mqtt_host", default="core-mosquitto")
    parser.add_argument("--mqtt_port", default="1883")
    parser.add_argument("--mqtt_user", default="")
    parser.add_argument("--mqtt_pass", default="")
    parser.add_argument("--discovery_prefix", default="homeassistant")
    parser.add_argument("--ha_url", default="")
    parser.add_argument("--ha_token", default="")
    parser.add_argument("--ha_calendar_entity", default="")
    args = parser.parse_args()

    teams = []
    if args.teams_json:
        try:
            teams = json.loads(args.teams_json)
        except Exception as e:
            print(f"[ERREUR] teams-json invalide: {e}")
    elif args.team_url:
        teams = [{"name": "default", "team_url": args.team_url}]
    else:
        print("[ERREUR] Aucune équipe fournie.")
        return

    client = mqtt.Client(client_id=f"rseq_team_calendar_{int(time.time())}")
    if args.mqtt_user:
        client.username_pw_set(args.mqtt_user, args.mqtt_pass)
    client.connect(args.mqtt_host, int(args.mqtt_port), 60)
    client.loop_start()
    driver = build_driver()
    last = load_last_events()

    try:
        for team in teams:
            name = team.get("name") or "default"
            url = team.get("team_url") or ""
            slug = slugify(name)
            device_name = f"RSEQ – {name}"
            print(f"[SCRIPT] Traitement équipe: {name}")

            status = "success"
            try:
                rows, standings = scrape_team_calendar(url, driver)
            except Exception as e:
                print(f"[ERREUR scrape]: {e}")
                standings, rows, status = [], [], f"error: {e}"
            next_game, upcoming = find_next_and_upcoming(rows)

            # ---- Classement format SportStandingsScores ----
            sport_standings = {
                "league": "RSEQ",
                "season": f"{now_local().year}-{now_local().year + 1}",
                "standings": [
                    {
                        "position": int(r.get("pos") or 0),
                        "team": r.get("team") or "",
                        "played": int(r.get("MJ") or 0),
                        "wins": int(r.get("V") or 0),
                        "losses": int(r.get("D") or 0),
                        "pct": float(r.get("MOY") or 0),
                        "points": int(r.get("PTS") or r.get("PES") or 0)
                    }
                    for r in standings
                ],
                "updated": now_local().isoformat()
            }

            # ---- MQTT publication du classement ----
            top = " | ".join(f"{r['pos']}) {r['team']} ({r.get('PTS') or r.get('PES')} pts)" for r in standings[:3]) if standings else "Classement indisponible"
            sensor_id_stand = f"{args.entity_prefix}_{slug}_classement"
            mqtt_discovery_publish(
                client, args.discovery_prefix, sensor_id_stand,
                f"RSEQ – Classement ({name})", device_name, "mdi:trophy",
                top,
                {
                    "team": name,
                    "team_url": url,
                    "sport_standings": sport_standings,
                    "sport_standings_version": 1,
                    "updated": now_local().isoformat()
                }
            )
        print("[SCRIPT] Tous les teams traités.")
    finally:
        driver.quit()
        client.loop_stop()
        client.disconnect()
        print("[SCRIPT] Terminé.")

if __name__ == "__main__":
    main()
