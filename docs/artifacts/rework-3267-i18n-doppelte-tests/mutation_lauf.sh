#!/bin/bash
# Mutationslauf #3267 (vorher/nachher). Aufruf: SCRATCH=<sicherungsordner> bash mutation_lauf.sh <label>
# Mutationen per String-Ersetzung mit externer Sicherungskopie, nie git checkout/stash/reset.
#
# Entfernt (Spec rework_3267_i18n_dubletten):
#  F1  api_katalog_paritaet::test_api_schluessel_und_platzhalter_paritaet        (Teilmenge von A)
#  F2  inbound_katalog_paritaet::test_inbound_schluessel... Z. set(de)==set(en) + parity-Filter (A)
#  F3  telegram_briefing_zweisprachig::test_ac9... Z. set(de)==set(en) + Praefix telegram. (A)
#  F10 radar_verschaerfung...::test_ac6_katalog_paritaet_de_en                    (identisch mit A)
#  F4  keine_hartkodierten...::test_allowlist_hat_keine_toten_eintraege           (Teilmenge von B)
#  F5  ratsche_narrow_telegram::test_kein_allowlist_eintrag_fuer_narrow_py        (B)
#  F6  inbound_katalog_paritaet::test_allowlist_traegt_keine_paket_datei          (B)
#  F7  alarm_zweisprachig::test_ac4_sms_gekuerzt_unabhaengig_von_der_sprache[140] (byte_gleich)
#  F8  vergleichs_mail_zweisprachig::test_zwei_nutzer_zwei_sprachen SMS-Zeile     (ac4 byte_gleich :244)
#  F9  vergleichs_mail_zweisprachig::test_ac6_reihenfolge... treffer-Zeile        (ac1 kein_deutscher)
#  A = tests/unit/test_i18n_katalog_paritaet.py::test_echte_kataloge_paritaetisch
#  B = tests/test_i18n_keine_hartkodierten_nutzertexte_python.py::test_allowlist_ist_leer
#
# Paare, die bewusst BLEIBEN (aehnlich, nicht doppelt; AC-4):
#  - G1 unit:37-42 (zehn Bereichsdateien gueltiges JSON): erst :33 + :45 zusammen implizieren es
#  - G2 telegram_briefing:88-95: :93 anderswo nur lueckenhaft belegt
#  - Golden-Vergleiche vs Katalog-Teilstring-Tests: Schnappschuss vs Katalogquelle
#  - Zwei-Nutzer-Tests: Eingang ueber resolve_user_lang (falsch aufgeloeste Sprache)
#  - alarm byte_gleich vs ac7: lang=None und de-Golden nur in byte_gleich
#  - Validator Funktion vs Prozess: anderer Eingangsweg
#  - gate_testmails de-Basispostfach vs byte_gleich: nur 3 von 4 Pfaden ueberlappen
#  - versand ac5 vs jeder_code / ac2 vs berichtsart: andere kwargs bzw. Werte
#  - tagesvergleich aehnlich[de] vs deutsch_wie_vorher: lang="de" vs ohne lang
#  - format_datum Locale-Test: andere Prozess-Locale als Eingabe
#  - inbound test_restbefund_p11_...: verlangt Existenz der Allowlist-Datei
set -u
cd /home/hem/gregor_zwanzig/.claude/worktrees/wise-sauteeing-frost
SP="${SCRATCH:?SCRATCH muss gesetzt sein}"
M=src/i18n/messages
ZIELE="$M/de/api.json $M/en/api.json $M/de/inbound.json $M/de/telegram.json $M/en/telegram.json
 tests/fixtures/i18n_python_allowlist.json src/output/renderers/alert/render.py
 tests/helpers/vergleichs_mail_fixture.py src/output/renderers/email/compare_html.py"
KAT="tests/unit/test_i18n_katalog_paritaet.py tests/test_i18n_api_katalog_paritaet.py
 tests/test_i18n_inbound_katalog_paritaet.py tests/test_telegram_briefing_zweisprachig.py
 tests/tdd/test_radar_verschaerfung_kennzeichnung_renderer.py"
ALW="tests/test_i18n_keine_hartkodierten_nutzertexte_python.py tests/test_i18n_ratsche_narrow_telegram.py
 tests/test_i18n_inbound_katalog_paritaet.py"
ALARM="tests/test_alarm_zweisprachig.py"
VGL="tests/test_vergleichs_mail_zweisprachig.py"
REF="tests/unit/test_paritaet_begruendung_marker.py tests/test_i18n_doku_vollstaendig.py
 tests/tdd/test_765_backend_hygiene_compliance.py tests/tdd/test_telegram_live_datenwurzel_zuruecksetzen_2813.py"
ALL="$KAT tests/test_i18n_keine_hartkodierten_nutzertexte_python.py tests/test_i18n_ratsche_narrow_telegram.py $ALARM $VGL"
PT="uv run pytest -o addopts= -p no:warnings -q -rfxX"
bk() { echo "$SP/$(echo "$1" | tr / _)"; }
for f in $ZIELE; do cp "$f" "$(bk "$f")"; done
restore() { for f in $ZIELE; do cp "$(bk "$f")" "$f"; done; }
mut() { python3 - "$1" "$2" "$3" <<'PY'
import sys
p,old,new=sys.argv[1:4]; s=open(p).read()
n=s.count(old); assert n==1, f"Treffer {n} fuer {old!r}"; open(p,"w").write(s.replace(old,new)); print("Ersetzungen:",n)
PY
}
lauf() { $PT $* -m "not live" 2>&1 | grep -E "^FAILED|^ERROR|passed|failed"; }
echo "##### Lauf: $1 #####"
echo "=== Basislauf alle betroffenen Dateien (unveraendert, -m 'not live') ==="
lauf $ALL

echo "=== M1a: api-Katalog: einseitiger Schluessel nur in de ($M/de/api.json) ==="
mut $M/de/api.json '{
  "api.fehler.trip_nicht_gefunden"' '{
  "api.zz_mutation": "x",
  "api.fehler.trip_nicht_gefunden"'
lauf $KAT; restore
echo "=== M1b: api-Katalog: Platzhalter {user_id} -> {nutzer} nur in en ($M/en/api.json) ==="
mut $M/en/api.json '"Trip {trip_id} not found for user {user_id}"' '"Trip {trip_id} not found for user {nutzer}"'
lauf $KAT; restore
echo "=== M1c: inbound-Katalog: einseitiger Schluessel nur in de ($M/de/inbound.json) ==="
mut $M/de/inbound.json '{
  "inbound.antwort.fehler.betreff"' '{
  "inbound.zz_mutation": "x",
  "inbound.antwort.fehler.betreff"'
lauf $KAT; restore
echo "=== M1d: telegram-Katalog: einseitiger Schluessel nur in de ($M/de/telegram.json) ==="
mut $M/de/telegram.json '{
  "telegram.kopf.zusammenfassung"' '{
  "telegram.zz_mutation": "x",
  "telegram.kopf.zusammenfassung"'
lauf $KAT; restore
echo "=== M1e: telegram-Katalog: fremdes Praefix in beiden Sprachen (allgemein.zz_mutation in telegram.json) ==="
mut $M/de/telegram.json '{
  "telegram.kopf.zusammenfassung"' '{
  "allgemein.zz_mutation": "x",
  "telegram.kopf.zusammenfassung"'
mut $M/en/telegram.json '{
  "telegram.kopf.zusammenfassung"' '{
  "allgemein.zz_mutation": "x",
  "telegram.kopf.zusammenfassung"'
lauf $KAT; restore

echo "=== M2: Allowlist mit Eintraegen (narrow.py + Paket-Datei trip_command_processor.py) ==="
mut tests/fixtures/i18n_python_allowlist.json '{}' '{"src/output/renderers/narrow.py": 1, "src/services/trip_command_processor.py": 1}'
lauf $ALW; restore

echo "=== M3a: Alarm-SMS haengt von der Sprache ab (render_sms haengt bei englischem cooldown_display ' x' an) ==="
mut src/output/renderers/alert/render.py '    return _render_sms_body(msg, limit, location_positions)' '    return _render_sms_body(msg, limit, location_positions) + (" x" if any(w in str(msg.cooldown_display) for w in ("hour", "minute")) else "")'
lauf $ALARM; restore
echo "=== M3b: Alarm-SMS ueberschreitet die Grenze (render_sms rendert mit limit + 200) ==="
mut src/output/renderers/alert/render.py '    return _render_sms_body(msg, limit, location_positions)' '    return _render_sms_body(msg, limit + 200, location_positions)'
lauf $ALARM; restore

echo "=== M4: Vergleichs-SMS haengt vom Nutzer/der Sprache ab (Aufrufpfad tests/helpers/vergleichs_mail_fixture.py:143 haengt lang an) ==="
mut tests/helpers/vergleichs_mail_fixture.py 'render_compare_sms(result, enabled_metrics=KANAL_METRIKEN, unresolved_count=1),' 'render_compare_sms(result, enabled_metrics=KANAL_METRIKEN, unresolved_count=1) + str(lang),'
lauf $VGL; restore

echo "=== M5: englische Vergleichs-Mail mit deutschem Katalogtext (compare_html.py: app_oeffnen mit \"de\") ==="
mut src/output/renderers/email/compare_html.py 't("vergleich.fuss.app_oeffnen", lang)' 't("vergleich.fuss.app_oeffnen", "de")'
lauf $VGL; restore

echo "=== Wiederhergestellt ==="
ok=1; for f in $ZIELE; do cmp -s "$f" "$(bk "$f")" || { ok=0; echo "ABWEICHUNG $f"; }; done
[ $ok = 1 ] && echo "byte-identisch zur Sicherung"
git diff --quiet origin/main -- src/ tests/fixtures/ tests/helpers/ && echo "kein Diff gegen origin/main unter src/, tests/fixtures/, tests/helpers/"
lauf $ALL $REF
echo "=== collect (betroffene Dateien) ==="
uv run pytest -o addopts= -p no:warnings --collect-only -q $ALL 2>&1 | grep -E "allowlist_hat_keine_toten|kein_allowlist_eintrag_fuer_narrow|allowlist_traegt_keine_paket|api_schluessel_und_platzhalter|ac6_katalog_paritaet_de_en|gekuerzt_unabhaengig|collected|rror"
