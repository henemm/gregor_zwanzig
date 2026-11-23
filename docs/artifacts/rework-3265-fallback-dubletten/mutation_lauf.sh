#!/bin/bash
# Mutationslauf #3265 (vorher/nachher). Aufruf: SCRATCH=<sicherungsordner> bash mutation_lauf.sh <label>
# Mutationen per String-Ersetzung mit externer Sicherungskopie, nie git checkout/stash/reset.
#
# Entfernt (G6a): 1142 test_seam_catches_provider_request_and_not_found_error, Fall (a)
#   = echte Teilmenge von test_geosphere_5xx_preserves_original_error_and_retry (ac3):
#   gleicher Aufbau, gleicher Aufruf, gleiche Erwartung; ac3 prueft zusaetzlich die Retry-Zahl.
#
# Paare, die bewusst BLEIBEN (aehnlich, nicht doppelt; AC-4):
#  - 1115 ac2 (Berlin, 400, Retry gekappt) vs 1155 ac3 (Lappland, 404, echter Retry): andere Werte, andere Ebene
#  - 1115 ac3 vs 1155 ac4/ac2: andere Orte, andere Wege zum Erfolg, andere Erwartung (fallback_reason)
#  - 1115 ac1 vs 1115 ac3 (Fallback-Haelfte): gleiche Eingabe, andere Erwartung
#  - 1155 ac7 isinstance(NormalizedTimeseries): Setup-Assert, ohne ihn ist die Zeitmessung bedeutungslos
#  - 1141 ac2 vs 1155 ac1: 1141 traegt "keine Region", 1155 misst Retry-Zahlen
#  - 1141 ac5 vs 1142 ac3: anderer Direktprovider (DWD vs GeoSphere), andere Region; 1141 ac5 vs ac6: andere Erwartung
#  - 1141 ac1 (live) vs ac3: gleiche Eingabe, andere Erwartung
set -u
cd /home/hem/gregor_zwanzig/.claude/worktrees/wise-sauteeing-frost
SP="${SCRATCH:?SCRATCH muss gesetzt sein}"
F=src/providers/openmeteo.py
T1142=tests/tdd/test_issue_1142_geosphere_direct_fallback.py
ALL="tests/tdd/test_issue_1115_model_fallback.py tests/tdd/test_issue_1141_cross_provider_fallback.py $T1142 tests/tdd/test_issue_1155_retry_tuning.py"
PT="uv run pytest -o addopts= -p no:warnings -q -rfxX"
SEAM="                except (ProviderNotImplementedError, ProviderRequestError, ProviderNotFoundError):"
cp "$F" "$SP/openmeteo_backup.py"
mut() { python3 - "$1" "$2" <<'PY'
import sys
p="src/providers/openmeteo.py"; old,new=sys.argv[1],sys.argv[2]; s=open(p).read()
n=s.count(old); assert n==1, f"Treffer {n} fuer {old!r}"; open(p,"w").write(s.replace(old,new)); print("Ersetzungen:",n)
PY
}
restore() { cp "$SP/openmeteo_backup.py" "$F"; }
echo "##### Lauf: $1 #####"
echo "=== Basislauf 1142 (unverändert, -m 'not live') ==="
$PT $T1142 -m "not live" 2>&1 | grep -E "^FAILED|passed|failed"
echo "=== M1: Seam faengt ProviderRequestError nicht mehr ==="
mut "$SEAM" "                except (ProviderNotImplementedError, ProviderNotFoundError):"
$PT $T1142 -m "not live" 2>&1 | grep -E "^FAILED|passed|failed"
restore
echo "=== M2: Seam faengt ProviderNotFoundError nicht mehr ==="
mut "$SEAM" "                except (ProviderNotImplementedError, ProviderRequestError):"
$PT $T1142 -m "not live" 2>&1 | grep -E "^FAILED|passed|failed"
restore
echo "=== Wiederhergestellt ==="
cmp "$F" "$SP/openmeteo_backup.py" && echo "byte-identisch zur Sicherung"
git diff --quiet origin/main -- "$F" && echo "kein Diff gegen origin/main"
$PT $ALL -m "not live" 2>&1 | grep -E "^FAILED|passed|failed"
echo "=== collect (vier Dateien) ==="
uv run pytest -o addopts= -p no:warnings --collect-only -q $ALL 2>&1 | grep -E "seam_catches|5xx_preserves|collected|error"
echo "=== exc_a in 1142 ==="
grep -c "exc_a" $T1142 || true
