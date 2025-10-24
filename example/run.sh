#!/usr/bin/env bash
set -euo pipefail

OPTIONS_FILE="/data/options.json"

# --- Lecture des options (avec valeurs par défaut raisonnables) ---
ENTITY_PREFIX="$(jq -r '.entity_prefix // "rseq"' "$OPTIONS_FILE")"
UPDATE_INTERVAL="$(jq -r '.update_interval // 900' "$OPTIONS_FILE")"

MQTT_HOST="$(jq -r '.mqtt_host // empty' "$OPTIONS_FILE")"
MQTT_PORT="$(jq -r '.mqtt_port // 1883' "$OPTIONS_FILE")"
MQTT_USER="$(jq -r '.mqtt_username // empty' "$OPTIONS_FILE")"
MQTT_PASS="$(jq -r '.mqtt_password // empty' "$OPTIONS_FILE")"
DISCOVERY_PREFIX="$(jq -r '.discovery_prefix // "homeassistant"' "$OPTIONS_FILE")"

HA_URL="$(jq -r '.ha_url // empty' "$OPTIONS_FILE")"
HA_TOKEN="$(jq -r '.ha_token // empty' "$OPTIONS_FILE")"
HA_CALENDAR_ENTITY="$(jq -r '.ha_calendar_entity // empty' "$OPTIONS_FILE")"

# --- Multi-équipes (nouveau) + compat legacy ---
# Préfère .teams ; si absent/vide, bascule sur .team_url (legacy).
TEAMS_JSON="$(jq -c '
  if (.teams // []) | length > 0 then
    .teams
  elif (.team_url // "") != "" then
    [ { "name": "default", "team_url": .team_url } ]
  else
    []
  end
' "$OPTIONS_FILE")"

# --- Validation de base ---
if [[ "$TEAMS_JSON" == "[]" ]]; then
  echo "[ERREUR] Aucune équipe configurée. Définis soit:
  - options.teams: [ {name, team_url}, ... ]
  - ou (legacy) options.team_url: \"https://diffusion.rseq.ca/Default?Type=Team&TeamId=...\""
  exit 1
fi

echo "[INFO] Démarrage de l'add-on RSEQ Team Calendar (multi-équipes)"
echo "[INFO] Discovery prefix      = $DISCOVERY_PREFIX"
echo "[INFO] MQTT                  = ${MQTT_HOST:-<non défini>}:$MQTT_PORT"
echo "[INFO] Intervalle (sec)      = $UPDATE_INTERVAL"
echo "[INFO] HA URL                = ${HA_URL:-<non défini>}"
echo "[INFO] HA Calendar Entity    = ${HA_CALENDAR_ENTITY:-<non défini>}"
echo "[INFO] Entity prefix         = $ENTITY_PREFIX"

# Liste lisible des équipes dans les logs
echo "[INFO] Équipes configurées :"
echo "$TEAMS_JSON" | jq -r '.[] | "- \(.name) -> \(.team_url)"'

# Facultatif : Flags Chromium headless (si tu veux les injecter au script)
export CHROMIUM_FLAGS="${CHROMIUM_FLAGS:---headless=new --no-sandbox --disable-dev-shm-usage --disable-gpu --window-size=1920,1080}"

while true; do
  echo "[INFO] Exécution du script Python…"
  python3 /script.py \
    --teams-json "$TEAMS_JSON" \
    --entity_prefix "$ENTITY_PREFIX" \
    --mqtt_host "$MQTT_HOST" \
    --mqtt_port "$MQTT_PORT" \
    --mqtt_user "$MQTT_USER" \
    --mqtt_pass "$MQTT_PASS" \
    --discovery_prefix "$DISCOVERY_PREFIX" \
    --ha_url "$HA_URL" \
    --ha_token "$HA_TOKEN" \
    --ha_calendar_entity "$HA_CALENDAR_ENTITY"

  echo "[INFO] Attente ${UPDATE_INTERVAL}s…"
  sleep "$UPDATE_INTERVAL"
done
