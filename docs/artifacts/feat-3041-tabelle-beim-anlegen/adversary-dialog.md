# Adversary Dialog — feat-3041-tabelle-beim-anlegen
Spec: docs/specs/modules/feat_3304_was_steht_wo_vorschau.md
Datum: 2026-11-23 18:13

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
**Adversary:** Tests ausgefuehrt (Python 79 passed, Go handler und router alle PASS; Ausgabe in docs/artifacts/feat-3041-tabelle-beim-anlegen/adversary-test-output.txt). Mutationen je per String-Ersetzung mit Sicherung im Scratchpad, danach per diff identisch wiederhergestellt:
- (a) Orte-Aufloesung mit festem fremdem Nutzer, user_id aus Koerper, Orte beider Nutzer (src/services/placements_view_service.py:687): GEFANGEN (test_ac5 beide, test_ac2). Der ersetzte AC-5-Test ist wirksam: location_count (3 oder 0 statt 2) und Gleichheit mit der GET-Ansicht des eigenen Abos schlagen an, obwohl Namen in keiner Antwort stehen.
- (b) Go: user_id aus der Query statt der Anmeldung (internal/handler/preview_proxy.go, appendUserID): GEFANGEN (Zwei-Nutzer-Test Go). Das Weglassen der Query-Neuschreibung im Handler (internal/handler/placements.go:263) ist aequivalent (appendUserID ueberschreibt user_id immer): kein Test faengt es (F003).
- (c) MaxBytesReader entfernt (internal/handler/placements.go:248): GEFANGEN (KoerperGrenzeUndKaputtesJSON, Router-Test).
- (d) stored=True bzw. Ueberschreibung entfernt (src/services/placements_view_service.py:123): GEFANGEN (AC-1, AC-2, AC-3).
- (e) Vorschau schreibt eine Datei: GEFANGEN (test_ac4 Baumvergleich).
- (f) Zeilen des Entwurfs ignoriert oder geleert: GEFANGEN (AC-3 mit Zeilen, AC-1 mit Tabelle).
- Weitere: Anmeldepruefung aus (401-Test), Route entfernt (internal/router/router.go:392, Routing-Test), kind-Pruefung im Kern aus (api/routers/placements.py:51, AC-7), invalid_preset durchgereicht (AC-8), GET-Pfad stored geaendert (Regression): alle GEFANGEN.
**Implementierer:** keine Rueckmeldung.

### Runde 2
**Adversary:** Randfaelle direkt am Kern: leerer Koerper, null, Liste, stages als Text, location_ids als Text oder mit Nicht-Strings, display_config als Text, Pfadzeichen in id und location_ids. Nie 500, nie ein Schreibzugriff; 422 invalid_preset oder 200. Befund F001: der 422-Text lautet woertlich "Orte-Abo nicht versendbar: {reason}" (Platzhalter nicht ersetzt, Versandtext, auch fuer Trips). Befund F002: Formatierungsfehler in src/services/placements_view_service.py:380. Regression: bestehende 3237, 3154 und Placements-Tests gruen; GET, PUT, Anlage unveraendert.
**Implementierer:** offen.

### Runde 3
**Adversary:** Fixes F001-F003 geprueft, Mutationen je per String-Ersetzung mit Sicherung im Scratchpad, danach per diff byte-genau wiederhergestellt.
- F001 behoben: api/routers/placements.py:72 reicht text_key="versand.vorschau.entwurf_unlesbar" durch (Code Reference: api/routers/placements.py:72); src/services/send_outcomes.py:82 nutzt `t(text_key or key, ...)`, Status und Code bleiben aus SEND_OUTCOMES (Code Reference: src/services/send_outcomes.py:82). Ohne text_key unveraendert: test_versand_zweisprachig, test_briefings_send_endpoint, 3237, i18n-Paritaet gruen.
- F002 behoben: Code Reference: src/services/placements_view_service.py:380 (Formatierung sauber).
- F003 behoben: Code Reference: internal/handler/placements.go:261 schreibt die Query auf kind neu; neuer Go-Test prueft mit doppelten kind/user_id-Parametern, dass der Kern genau {kind: route, user_id: nutzer-a} erhaelt. Route weiter registriert: Code Reference: internal/router/router.go:392.
- Mutationen: M1 text_key in error_body ignorieren -> 4 Tests rot (route/vergleich x de/en). M2 Router ohne text_key -> 4 rot. M2b Katalogtext DE zurueck auf Platzhalter-Text "Orte-Abo nicht versendbar: {reason}" -> 2 rot (route-de, vergleich-de). M3 Go-Query nicht mehr neu geschrieben (Zeile 261 neutralisiert) -> TestPlacementsVorschau3304KernErhaeltNurKindUndUserID rot. Alle zurueckgenommen, diff identisch (Go-Datei gegen Index leer).
- Hinweis zum Ablauf: ein erster Mutationsversuch wurde vom Werkzeug vor Ausfuehrung abgewiesen; bei M3 fehlte deshalb zunaechst die Sicherung, die Zeile wurde aus dem vorher gelesenen Wortlaut wiederhergestellt und per git diff gegen den Index als identisch bestaetigt.
- Tests: Python-Zieldateien (3304, 3237, versand_zweisprachig, briefings_send_endpoint, i18n-Paritaet/Hartkodierung/Doku) alle gruen, 0 rot; Go internal/handler und internal/router ok. Ausgabe: docs/artifacts/feat-3041-tabelle-beim-anlegen/adversary-test-output.txt.
**Implementierer:** keine Rueckmeldung.

Code reference: api/routers/placements.py:72
Code reference: src/services/send_outcomes.py:82
Code reference: src/services/placements_view_service.py:123
Code reference: src/services/placements_view_service.py:687
Code reference: internal/handler/placements.go:248
Code reference: internal/router/router.go:392

## Herkunft der Vorbedingungen

kein Sprachprofil konfiguriert (`precondition_origins.default_lang`)


## Verdict

VERDICT: VERIFIED

Confirmation: AC-1, AC-2, AC-3 | Code reference: src/services/placements_view_service.py:123 | Status: CONFIRMED
Confirmation: AC-4 | Code reference: api/routers/placements.py:51 | Status: CONFIRMED
Confirmation: AC-5 | Code reference: src/services/placements_view_service.py:687 | Status: CONFIRMED
Confirmation: AC-6, AC-7, AC-8 | Code reference: internal/handler/placements.go:248 | Evidence: F001 behoben (api/routers/placements.py:72, src/services/send_outcomes.py:82), Mutationen M1-M3 gefangen | Status: CONFIRMED
Confirmation: AC-9 | Code reference: src/services/placements_view_service.py:380 | Status: CONFIRMED
Confirmation: AC-10 | Code reference: internal/router/router.go:392 | Status: CONFIRMED

F001, F002, F003: behoben und bewacht (siehe Runde 3). Keine offenen Findings.

## Geprüfte Dateien

- sha256:fc98d435dfdd3c25a41af4129ce20a625a865377a143b4708ebe70f7fb9953fd  api/routers/placements.py
- sha256:bdd7ac4e833a1d2d3123278097f2ac89731035307cd68c233cd75a0a87b07eeb  internal/handler/placements.go
- sha256:fa016a6743d6195ab312572784e70c13d861a986f66fa534e9e6d0117b5370f4  internal/router/router.go
- sha256:32878bac9959d25c4017572ae50e758d668738815d5165e5c2511ccbda03f3fb  src/services/placements_view_service.py
- sha256:bd8e994aa08cc976d2773b470e527355c963d6bbb3a86213c482fd514c6cd59c  src/services/send_outcomes.py

## Prüfbasis

- base: b9282aa0a449d1458ab52300207013bbe2ffe551
- blob:d74781ca5d325c34c2f7e727d5b0dda75c9f00f1  api/routers/placements.py
- blob:a013b79095254cd4c514b31f2223d6e7e6b162e0  internal/handler/placements.go
- blob:06050035ab9242d57545adca738eb923450e7b74  internal/router/router.go
- blob:c774487fc06d81d5d41f8cc2b9f2ce311fb0d99f  src/services/placements_view_service.py
- blob:0ebc739e2aa7c09b3f22fc585be6360a25020497  src/services/send_outcomes.py
