# Adversary Dialog — feat-3041-tabelle-beim-anlegen
Spec: docs/specs/modules/feat_3304_was_steht_wo_vorschau.md
Datum: 2026-11-23 19:16

## Checkliste
- [x] **Input:** `POST /api/briefings/placements/vorschau?kind=route|vergleich` mit angemeldetem Nutzer; Körper = Entwurf in der Form der Anlage-Nutzlast (`POST /api/trips` bzw. Orts-Vergleich-Anlage), mit oder ohne `display_config.placements.rows`.
- [x] **Output:** JSON mit denselben Schlüsseln wie `GET /api/briefings/{id}/placements` (`kind, lang, stored, placements, location_count, columns, fixed_rows, rows, sms_example, outlook_reports, blocks, legend, example_version`), `stored` immer `false`.
- [x] **Side effects:** keine. Es wird nichts gespeichert, kein Abo angelegt, kein Wetter abgerufen.
- [x] **AC-1:** Given ein Nutzer mit Trip-Entwurf im Körper und ein gespeicherter Trip mit gleicher Konfiguration / When die Vorschau mit `kind=route` und `GET /api/briefings/{id}/placements?kind=route` abgefragt werden / Then haben beide Antworten dieselben Schlüssel und denselben Inhalt in Spalten, Zeilen, SMS-Beispiel, Legende und Ausblick, nur `stored` ist bei der Vorschau `false`.
- [x] **AC-2:** Given ein Nutzer mit Orts-Vergleich-Entwurf (zwei eigene Orte) und ein gespeichertes Orts-Vergleich-Abo gleicher Konfiguration / When die Vorschau mit `kind=vergleich` und der GET-Weg abgefragt werden / Then stimmen Form und Inhalt überein (inklusive `location_count` und Beispielwerten der Orte), nur `stored` ist `false`.
- [x] **AC-3:** Given ein Entwurf ohne `placements.rows` und ein Entwurf mit eigenen Zeilen / When die Vorschau abgefragt wird / Then enthält die Antwort im ersten Fall die Zeilen aus der Grundauswahl, exakt wie sie die Erstanlage schreiben würde, im zweiten Fall genau die mitgeschickten Zeilen in dieser Reihenfolge, und `stored` bleibt in beiden Fällen `false`.
- [x] **AC-4:** Given ein Nutzer mit bekanntem Datenbaum / When er die Vorschau für Trip und Orts-Vergleich mehrfach abruft / Then bleibt der Datenbaum byte-gleich (keine neue Datei, kein neues Abo, keine geänderte Datei) und die Antwort trägt weder ETag noch eine Anlage-Kennung.
- [x] **AC-5:** Given zwei verschiedene Nutzer A und B, wobei der Entwurf von A eine Orts-ID von B und eine unbekannte ID nennt und im Körper `user_id` von B steht / When A die Vorschau abruft / Then erscheinen nur die eigenen Orte von A (`location_count` zählt nur sie, keine Namen oder Werte von B), und die `user_id` im Körper und in der Query bleiben ohne Wirkung, weil allein die Anmeldung gilt.
- [x] **AC-6:** Given eine Anfrage ohne Anmeldung / When die Vorschau aufgerufen wird / Then antwortet die API mit 401 und es erfolgt kein Aufruf des Python-Kerns.
- [x] **AC-7:** Given ein angemeldeter Nutzer / When `kind` fehlt oder unbekannt ist / Then antwortet die API mit 400 und dem Fehlercode `kind_required` im Text der Nutzersprache (Katalog, kein Freitext), auch direkt am Python-Kern.
- [x] **AC-8:** Given ein angemeldeter Nutzer / When der Körper größer als 256 KB oder kein gültiges JSON-Objekt ist / Then antwortet die API bei zu großem Körper mit 413 `payload_too_large` und bei kaputtem JSON mit 400 `bad_request`, jeweils ohne dass der Python-Kern aufgerufen wird; ein Entwurf, den der Kern nicht lesen kann, ergibt 422 `invalid_preset`.
- [x] **AC-9:** Given der bestehende Lese-, Schreib- und Anlegeweg / When nach der Änderung `GET` und `PUT /api/briefings/{id}/placements` sowie die Anlage eines Trips und Orts-Vergleichs (`anlageTabelle`) laufen / Then verhalten sie sich unverändert (gleiche Antworten, ETag und If-Match wie zuvor, Anlage schreibt weiterhin die volle Tabelle).
- [x] **AC-10:** Given ein Trip oder Orts-Vergleich mit der Kennung `placements` oder ein Aufruf des Pfads `/api/briefings/placements/vorschau` / When die Vorschau über Go und Python aufgerufen wird / Then wird der Pfad als Vorschau behandelt und nicht als Abo mit der Kennung `placements` gelesen (kein 404 `not_found` für ein Abo, kein Aufruf des GET-Handlers).

## Dialog

### Runde 1
**Adversary:** Angriff auf die Kernzusicherung: Entwurf ohne `id` ergibt keine Ausnahme mehr, und alle ACs bleiben erfuellt. Testlauf `tests/tdd/test_3304_placements_vorschau.py`, `test_3237_placements_aus_grundauswahl.py`, `test_placements_tabelle_endpoint.py` (-v): 131 passed (adversary-test-output-fix1.txt). Kollision: gespeichertes Abo mit Kennung `entwurf` (andere Konfiguration, beide Briefings) angelegt, danach Vorschau eines kennungslosen Entwurfs: Antwort identisch zur Vorschau mit Kennung `fremd` und zum GET des Quell-Trips, Datenbaum byte-gleich (Wegwerf-Test, danach entfernt).
Code reference: src/services/placements_view_service.py:116 — die Platzhalter-Kennung wird vor beiden Arten (route und vergleich) gesetzt, also am gemeinsamen Eingang, den der Nutzer erreicht.
Code reference: src/services/placements_view_service.py:140 — `load_trip(draft)` bekommt das Woerterbuch, nicht die Kennung als Pfad; der Platzhalter laedt also keine Datei. Lese-Pfad mit `data_dir` liegt nur in der GET-Funktion (Zeile 380-382), die die Vorschau nicht ruft.
Code reference: src/services/placements_view_service.py:394 — die Kennung fliesst nur in `UnifiedWeatherDisplayConfig(trip_id=...)`, ein internes Feld ohne Persistenz; die Antwort traegt keine Kennung (AC-4, Test tests/tdd/test_3304_placements_vorschau.py:438).
Code reference: src/services/placements_view_service.py:149 — Orts-Vergleich liest `id` im Entwurf gar nicht; Orte nur ueber `user_id` (Zeile 701), AC-5 unberuehrt.
**Implementierer:** Platzhalter ist rein intern, nichts wird gelesen oder geschrieben; Kollision mit echtem Abo `entwurf` ist wirkungslos.

### Runde 2
**Adversary:** Mutationen per String-Ersetzung, Sicherung im Scratchpad (orig.py), nach jeder Mutation byte-genau per diff wiederhergestellt (IDENT).
Code reference: src/services/placements_view_service.py:116 — M1 Aufruf entfernt: ROT (3 Tests: test_fix1_trip_entwurf_ohne_kennung_gleich_get_ansicht[standard-fehlt], [beide_briefings-fehlt], test_fix1_trip_entwurf_ohne_kennung_direkt_am_dienst_unveraendert). Der Aufruf wirkt und wird an der Nutzerstelle (HTTP-Router) geprueft.
Code reference: src/services/placements_view_service.py:137 — M2 Original statt Kopie mutieren: ROT nur durch test_fix1_trip_entwurf_ohne_kennung_direkt_am_dienst_unveraendert (Test Zeile 443). Die HTTP-Tests faengen es nicht (Entwurf wird serialisiert), der Dienst-Test schon; ausreichend.
Code reference: src/services/placements_view_service.py:135 — M3 nur bei fehlender id ersetzen (`"id" in draft`): bleibt GRUEN (33 passed). Grund: `load_trip` akzeptiert `id=""` ohne Fehler (auch ohne Fix laufen die `leer`-Varianten gruen, siehe M1). Aequivalente Mutation im Verhalten, aber die `leer`-Tests (Zeile 417, 456) bewachen die Leer-Zweig-Logik nicht; sie belegen nur Unkaputtheit.
Code reference: src/services/placements_view_service.py:129 — M4 Platzhalter auf "" gesetzt: bleibt GRUEN (33 passed), aus demselben Grund (leere Kennung wird gelesen). Der konkrete Wert `entwurf` ist unerheblich; Test prueft Abwesenheit einer Kennung in der Antwort, nicht den Wert.
**Implementierer:** M3/M4 sind verhaltensgleich; kein Nutzerschaden.

Findings:
F001 (LOW, anti_pattern) Code reference: src/services/placements_view_service.py:135 — Leer-Zweig (`id` leer) ist ohne Wirkung und ungeschuetzt; die Docstring-Behauptung "fehlt oder leer" wird von den `leer`-Tests nicht von der Alternative unterschieden. Kein Funktionsfehler; optional Zweig vereinfachen (`"id" in draft`) oder Test streichen.
Keine HIGH/CRITICAL Findings.

## Herkunft der Vorbedingungen

kein Sprachprofil konfiguriert (`precondition_origins.default_lang`)

## Verdict

VERDICT: VERIFIED

131 passed, 0 failed. Mutationen M1, M2 gefangen; M3, M4 verhaltensgleich (LOW F001). Platzhalter kollidiert nicht mit echtem Abo `entwurf` (keine Lese-/Schreibwirkung), Entwurf des Aufrufers bleibt unveraendert (Kopie, Test Zeile 443).

## Geprüfte Dateien

- sha256:0da7dc775d6e403b06d22ef3a180153d8fb3844ecf1c94466690d7389cf79d31  src/services/placements_view_service.py

## Prüfbasis

- base: 1000bfa37c3742c348cef9575623958b154bedaa
- blob:ba72becb1084bdcec827a15f914463aabdab8e11  src/services/placements_view_service.py

## Geprüfte Dateien

- sha256:0da7dc775d6e403b06d22ef3a180153d8fb3844ecf1c94466690d7389cf79d31  src/services/placements_view_service.py

## Prüfbasis

- base: 1000bfa37c3742c348cef9575623958b154bedaa
- blob:ba72becb1084bdcec827a15f914463aabdab8e11  src/services/placements_view_service.py
