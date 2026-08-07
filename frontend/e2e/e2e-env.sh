#!/usr/bin/env bash
# Issue #1289: nur die Variablen extrahieren, die der Preview-Server
# tatsächlich liest (GZ_SESSION_SECRET, GZ_GOOGLE_CLIENT_ID) — kein
# Blanket-Source der kompletten .env mehr. GZ_API_BASE und NODE_ENV
# werden weiterhin separat in start-preview.sh gesetzt.
ENV_FILE="${GZ_REPO_ENV_FILE:-$(dirname "$0")/../../.env}"

_extract() {
  [ -f "$ENV_FILE" ] || return 0
  local val
  val="$(grep -m1 "^$1=" "$ENV_FILE" | cut -d= -f2-)"
  # Der frueher genutzte `source`-Pfad entfernt umschliessende Anfuehrungs-
  # zeichen, `grep | cut` nicht. In der Haupt-.env stehen die Werte in
  # doppelten Anfuehrungszeichen -- ohne dieses Abstreifen kaeme ein um zwei
  # Zeichen laengeres GZ_SESSION_SECRET an, das nicht zum Staging-Go-Server
  # passt und alle authentifizierten E2E-Tests STILL brechen liesse.
  case "$val" in
    '"'*'"') val="${val#\"}"; val="${val%\"}" ;;
    "'"*"'") val="${val#\'}"; val="${val%\'}" ;;
  esac
  printf '%s' "$val"
}

GZ_SESSION_SECRET_VAL="$(_extract GZ_SESSION_SECRET)"
GZ_GOOGLE_CLIENT_ID_VAL="$(_extract GZ_GOOGLE_CLIENT_ID)"
[ -n "$GZ_SESSION_SECRET_VAL" ] && export GZ_SESSION_SECRET="$GZ_SESSION_SECRET_VAL"
[ -n "$GZ_GOOGLE_CLIENT_ID_VAL" ] && export GZ_GOOGLE_CLIENT_ID="$GZ_GOOGLE_CLIENT_ID_VAL"
