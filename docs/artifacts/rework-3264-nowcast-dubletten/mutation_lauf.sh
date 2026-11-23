#!/bin/bash
# Mutationslauf #3264 (vorher/nachher). Aufruf: SCRATCH=<sicherungsordner> bash mutation_lauf.sh <label>
# Mutationen per String-Ersetzung mit externer Sicherungskopie, nie git checkout/stash/reset.
#
# Paare, die bewusst BLEIBEN (aehnlich, nicht doppelt; AC-5):
#  - ac4_*_convective_drives_intensity (734 vs 761): andere Quelle (AROME-FR vs ICON-D2), andere Raten (0.3/2.0 vs 0.4/3.0)
#  - within(_ATLANTIC) is False (734 vs 761): andere Funktion (_within_arome_france vs _within_icon_d2)
#  - 656 ac4_radar_alert_* vs 660 ac4_radar_alert_convective_marked_once_then_throttles: anderer (konvektiver) Fall
#  - 656 format_now_text_* vs 660 ac3_derive_result_convective_label_and_text: andere Eingaben
set -u
cd /home/hem/gregor_zwanzig/.claude/worktrees/wise-sauteeing-frost
SP="${SCRATCH:?SCRATCH muss gesetzt sein}"
F=src/services/radar_service.py
CORE="tests/tdd/test_feature_656_radar_nowcast.py tests/tdd/test_feature_660_convective_stage.py"
LIVE="tests/tdd/test_feature_734_arome_france_nowcast.py tests/tdd/test_feature_761_icon_d2_nowcast.py"
KCORE="intensity_to_text_levels or intensity_non_convective_unchanged"
KLIVE="chain_routing"
PT="uv run pytest -o addopts= -p no:warnings -q -rfxX"
cp "$F" "$SP/radar_service_backup.py"
mut() { python3 - "$1" "$2" <<'EOF'
import sys
p="src/services/radar_service.py"; old,new=sys.argv[1],sys.argv[2]; s=open(p).read()
n=s.count(old); assert n==1, f"Treffer {n} fuer {old!r}"; open(p,"w").write(s.replace(old,new)); print("Ersetzungen:",n)
EOF
}
restore() { cp "$SP/radar_service_backup.py" "$F"; }
echo "##### Lauf: $1 #####"
echo "=== Basislauf Kern (unverändert) ==="
$PT $CORE -m "not live" -k "$KCORE" 2>&1 | grep -E "^(FAILED|PASSED)|passed|failed"
echo "=== M1: Grenze leicht/mäßig 'if mm_per_h < 1.0:' -> 'if mm_per_h < 3.0:' ==="
mut "        if mm_per_h < 1.0:" "        if mm_per_h < 3.0:"
$PT $CORE -m "not live" -k "$KCORE" 2>&1 | grep -E "^FAILED|passed|failed"
restore
echo "=== M2: Default 'is_convective: bool = False' -> True ==="
mut "self, mm_per_h: float, is_convective: bool = False," "self, mm_per_h: float, is_convective: bool = True,"
$PT $CORE -m "not live" -k "$KCORE" 2>&1 | grep -E "^FAILED|passed|failed"
restore
echo "=== Basislauf Live (unverändert, -m live) ==="
$PT $LIVE -m live -k "$KLIVE" 2>&1 | grep -E "^(FAILED|XFAIL|XPASS)|passed|failed|xfail"
echo "=== M3a: RADOLAN-Box '_RADOLAN_LAT_MIN = 47.0' -> 53.0 (Berlin faellt aus der Box) ==="
mut "_RADOLAN_LAT_MIN = 47.0" "_RADOLAN_LAT_MIN = 53.0"
$PT $LIVE -m live -k "$KLIVE" 2>&1 | grep -E "^(FAILED|XFAIL|XPASS)|passed|failed|xfail"
restore
echo "=== M3b: Global-Fallback 'return frames, \"minutely_15\"' -> \"global\" ==="
mut '        return frames, "minutely_15"' '        return frames, "global"'
$PT $LIVE -m live -k "$KLIVE" 2>&1 | grep -E "^(FAILED|XFAIL|XPASS)|passed|failed|xfail"
restore
echo "=== Wiederhergestellt ==="
cmp "$F" "$SP/radar_service_backup.py" && echo "byte-identisch zur Sicherung"
git diff --quiet origin/main -- "$F" && echo "kein Diff gegen origin/main"
$PT $CORE $LIVE -m "not live" 2>&1 | grep -E "passed|failed"
echo "=== collect (vier Dateien) ==="
uv run pytest -o addopts= -p no:warnings --collect-only -q $CORE $LIVE 2>&1 | grep -E "intensity_to_text_levels|intensity_non_convective_unchanged|chain_routing|collected|error"
