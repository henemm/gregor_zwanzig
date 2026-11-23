#!/bin/bash
# Mutationslauf #3266 (vorher/nachher). Aufruf: SCRATCH=<sicherungsordner> bash mutation_lauf.sh <label>
# Mutationen per String-Ersetzung mit externer Sicherungskopie, nie git checkout/stash/reset.
#
# Entfernt (G7a): r8py test_f1_altbestand_leer_jeder_kanal_folgt_editor, Z. 117-118
#   (SMS-Praefixe == _SMS_KUERZEL, premium_sms == sms_roh) = echte Teilmenge von
#   test_f1_altbestand_leer_sms_folgt_register_wie_editor_gespeichert Z. 51-53
#   (exakter SMS-String, Premium == Premium gespeichert == SMS), gleiche Eingabe.
#
# Paare, die bewusst BLEIBEN (aehnlich, nicht doppelt; AC-5):
#  - Premium-Ausgang vs Trip-Versand (fixloop3): Premium-Test strenger (exakt R-, genau eine Sendung)
#  - Versand vs Vorschau (fixloop3, 3039 ac13, orte_kanaele Renderer/Kette/Vorschau): andere Wege
#  - r8py t4 (Fenster 10,10) vs tagesfenster "nie eingestellt": andere Eingabe, eigener Rueckfallzweig
#  - r7 roh_gleich_mail_roh vs roh_zeigt_grad: zusaetzliche Mail-Liste, anderes Pruefziel
#  - orte_luecken bl2 (sms vs marker): preset() vs nie eingestellt, "irgendwo" vs "am Ende"
#  - orte_luecken bl4 vs sms_kuerzung "nie eingestellt": andere Wetter-Naht, andere Soll-Listen
#  - 3039 ac1/ac7/f001/f005: bewusst verschiedene Eingaben (False, Feld fehlt, Dublette)
#  - s1c4b Klammer-Tests (fixloop1/2/3): verschiedene Reihen, je eine eigene Regel
#  - fixloop1 leere Ampel vs fixloop2 Gewitter-Leser: andere Produktfunktionen
#  - Tabelle, Kachel, Telegram-Kurzuebersicht: andere Ebenen
#  - r8py t2 vs r9: eigene outlook_metrics vs Altbestand ohne Liste
#  - doppelter Helfercode (_sms_ort, zwei_nutzer, _ergebnis, mit, preset) ist keine doppelte Zusicherung
# Ertrag ehrlich: eine Teilmenge (zwei Zeilen) in 101 Testfunktionen aus 14 Dateien.
set -u
cd /home/hem/gregor_zwanzig/.claude/worktrees/wise-sauteeing-frost
SP="${SCRATCH:?SCRATCH muss gesetzt sein}"
B=src/output/tokens/builder.py
R=src/output/renderers/trip_report.py
T=tests/tdd/test_3047_r8py_luecken.py
F1="$T::test_f1_altbestand_leer_sms_folgt_register_wie_editor_gespeichert $T::test_f1_altbestand_leer_jeder_kanal_folgt_editor"
ALL="tests/tdd/test_compare_channel_layouts_3039.py tests/tdd/test_compare_channel_layouts_3039_fixloop.py
 tests/tdd/test_s1c4b_fixloop1_findings.py tests/tdd/test_s1c4b_fixloop2_findings.py tests/tdd/test_s1c4b_fixloop3_versandweg.py
 tests/tdd/test_3047_runde7_orte_kanaele.py tests/tdd/test_3047_runde7_orte_luecken.py tests/tdd/test_3047_runde7_orte_mail.py
 tests/tdd/test_3047_runde7_orte_sms_kuerzung.py tests/tdd/test_3047_runde7_sonnenstunden_settings.py
 tests/tdd/test_3047_runde7_telegram_tagesfenster.py tests/tdd/test_3047_r7_kanaele_trip.py $T
 tests/tdd/test_3047_r9_orte_altbestand_ausblick.py tests/tdd/test_einstellung_gleich_mail_fallliste.py"
PT="uv run pytest -o addopts= -p no:warnings -q -rfxX"
cp "$B" "$SP/builder_backup.py"; cp "$R" "$SP/trip_report_backup.py"
mut() { python3 - "$1" "$2" "$3" <<'PY'
import sys
p,old,new=sys.argv[1:4]; s=open(p).read()
n=s.count(old); assert n==1, f"Treffer {n} fuer {old!r}"; open(p,"w").write(s.replace(old,new)); print("Ersetzungen:",n)
PY
}
restore() { cp "$SP/builder_backup.py" "$B"; cp "$SP/trip_report_backup.py" "$R"; }
echo "##### Lauf: $1 #####"
echo "=== Basislauf f1-Tests (unveraendert, -m 'not live') ==="
$PT $F1 -m "not live" 2>&1 | grep -E "^FAILED|passed|failed"
echo "=== M1: FORECAST_THP \"TH+:\" -> \"TX+:\" ($B) ==="
mut "$B" 'FORECAST_THP = "TH+:"' 'FORECAST_THP = "TX+:"'
$PT $F1 -m "not live" 2>&1 | grep -E "^FAILED|passed|failed"
restore
echo "=== M2: Premium-SMS weicht von der SMS ab ($R, premium_sms_text: sms_text + \" X\") ==="
mut "$R" '            sms_text if len(sms_text) <= _premium_max' '            sms_text + " X" if len(sms_text) <= _premium_max'
$PT $F1 -m "not live" 2>&1 | grep -E "^FAILED|passed|failed"
restore
echo "=== Wiederhergestellt ==="
cmp "$B" "$SP/builder_backup.py" && cmp "$R" "$SP/trip_report_backup.py" && echo "byte-identisch zur Sicherung"
git diff --quiet origin/main -- src/ && echo "kein Diff gegen origin/main unter src/"
$PT $ALL -m "not live" 2>&1 | grep -E "^FAILED|^ERROR|passed|failed"
echo "=== collect (14 Dateien + Fallliste) ==="
uv run pytest -o addopts= -p no:warnings --collect-only -q $ALL 2>&1 | grep -E "test_f1_|collected|rror"
echo "=== Vorkommen _SMS_KUERZEL / sms_roh in r8py ==="
grep -cE "_SMS_KUERZEL|sms_roh" $T || true
