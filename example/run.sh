#!/usr/bin/env bash
set -euo pipefail

OPTIONS_FILE="/data/options.json"

# --- Lecture des options depuis config.yaml (via /data/options.json) ---
TEAM_URL="$(jq -r '.team_url // empty' "$OPTIONS_FILE")"
UPDATE_INTERVAL="$(jq -r '.update_interval // empty' "$OPTIONS_FILE")"

MQTT_HOST="$(jq -r '.mqtt_host // empty' "$OPTIONS_FILE")"
MQTT_PORT="$(jq -r '.mqtt_port // empty' "$OPTIONS_FILE")"
MQTT_USER="$(jq -r '.mqtt_username // empty' "$OPTIONS_FILE")"
MQTT_PASS="$(jq -r '.mqtt_password // empty' "$OPTIONS_FILE")"
DISCOVERY_PREFIX="$(jq -r '.discovery_prefix // "homeassistant"' "$OPTIONS_FILE")"

# Optionnels si tu veux aussi créer des événements calendrier HA
HA_URL="$(jq -r '.ha_url // empty' "$OPTIONS_FILE")"
HA_TOKEN="$(jq -r '.ha_token // empty' "$OPTIONS_FILE")"
HA_CALENDAR_ENTITY="$(jq -r '.ha_calendar_entity // empty' "$OPTIONS_FILE")"

# --- Défauts raisonnables ---
: "${UPDATE_INTERVAL:=900}"         # 15 min si non défini
: "${MQTT_PORT:=1883}"
: "${DISCOVERY_PREFIX:=homeassistant}"

echo "[INFO] Démarrage de l'add-on RSEQ Team Calendar"
echo "[INFO] Team URL              = ${TEAM_URL:-<non défini>}"
echo "[INFO] Intervalle (sec)      = $UPDATE_INTERVAL"
echo "[INFO] MQTT                  = ${MQTT_HOST:-<non défini>}:$MQTT_PORT"
echo "[INFO] Discovery prefix      = $DISCOVERY_PREFIX"
echo "[INFO] Home Assistant URL    = ${HA_URL:-<non défini>}"
echo "[INFO] HA Calendar Entity    = ${HA_CALENDAR_ENTITY:-<non défini>}"

if [[ -z "${TEAM_URL:-}" ]]; then
  echo "[ERREUR] 'team_url' est obligatoire dans config.yaml"
  exit 1
fi

while true; do
  echo "[INFO] Exécution du script Python…"
  python3 /script.py \
    --team_url "$TEAM_URL" \
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
