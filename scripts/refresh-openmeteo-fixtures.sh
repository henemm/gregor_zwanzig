#!/usr/bin/env bash
# Refresh-Script für OpenMeteo-Fixtures (Issue #263).
#
# Ruft /api/forecast gegen einen LOKALEN Server (ohne GZ_TEST_FIXTURE_DIR!) auf
# und überschreibt die 3 Fixture-Dateien in fixtures/openmeteo/.
#
# Voraussetzungen:
#   - Lokaler Go-Server läuft auf $BASE_URL (default: http://localhost:8090)
#   - GZ_TEST_FIXTURE_DIR ist NICHT gesetzt (sonst kämen Fixture-Daten zurück)
#   - Auth-Cookie ggf. mit -u oder COOKIE-Env (hier nicht implementiert — local dev)
#
# Usage:
#   ./scripts/refresh-openmeteo-fixtures.sh [BASE_URL]
set -euo pipefail

BASE_URL="${1:-http://localhost:8090}"
OUT_DIR="fixtures/openmeteo"

declare -A LOCATIONS=(
  ["innsbruck"]="47.2692,11.4041"
  ["stubai"]="47.1015,11.2958"
  ["zillertal"]="47.2190,11.8767"
)

mkdir -p "$OUT_DIR"

for name in "${!LOCATIONS[@]}"; do
  IFS=',' read -r lat lon <<< "${LOCATIONS[$name]}"
  echo "Fetching $name (lat=$lat, lon=$lon)..."
  curl -fsSL "${BASE_URL}/api/forecast?lat=${lat}&lon=${lon}&hours=72" \
    -o "${OUT_DIR}/${name}.json"
  echo "  -> ${OUT_DIR}/${name}.json aktualisiert"
done

echo "Alle 3 Fixture-Dateien aktualisiert."
