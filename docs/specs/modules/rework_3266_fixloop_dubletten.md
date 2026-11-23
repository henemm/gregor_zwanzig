---
entity_id: rework_3266_fixloop_dubletten
type: refactor
created: 2026-11-23
updated: 2026-11-23
status: draft
version: "1.0"
issue: 3266
epic: 1196
workflow: rework-3266-fixloop-doppelte-tests
tags: [tests, aufraeumen, doppelte-zusicherungen, fixloop, runden]
---

# Doppelte Zusicherungen in den Fixloop-/Runden-Tests entfernen (#3266)

## Approval

- [ ] Approved

## Purpose

Dieselbe Regel soll an genau einer Stelle geprueft werden. Diese Scheibe (Gruppe G7 aus #3208) prueft die Fixloop- und Runden-Testdateien zu 3039, s1c4b und 3047 (tatsaechlich 14 Dateien mit 101 Testfunktionen) auf doppelte Zusicherungen. Es gibt genau eine belegte Teilmenge: zwei Zeilen in `test_f1_altbestand_leer_jeder_kanal_folgt_editor` (`tests/tdd/test_3047_r8py_luecken.py`) sind in `test_f1_altbestand_leer_sms_folgt_register_wie_editor_gespeichert` derselben Datei bereits enthalten. Alles andere ist nur aehnlich und bleibt. Der Ertrag ist bewusst klein und wird ehrlich so benannt; die Hauptleistung ist der Mutationsnachweis, dass kein Schutz verloren geht.

## Source

- **File:** `docs/context/rework-3266-fixloop-doppelte-tests.md` (Abschnitte "Analysis", G7a, "Geprueft, bleibt")
- **Identifier:** `tests/tdd/test_3047_r8py_luecken.py::test_f1_altbestand_leer_jeder_kanal_folgt_editor`; Vorbild fuer Methode und Aufbau: `docs/specs/modules/rework_3265_fallback_dubletten.md` (#3265), `rework_3264_nowcast_dubletten.md`, `rework_3263_doppelte_zusicherungen_2795.md`, `rework_3208_doppelte_zusicherungen.md`

Schicht: reine Testsuite-Sanierung. Kein Produktcode in `src/`, `api/`, `internal/`, `scripts/`, `cmd/` oder `frontend/src/` wird veraendert (die Mutationen an `src/` sind temporaer und werden aus externer Sicherung wiederhergestellt). Kanaele (E-Mail, Telegram, SMS, Premium-SMS), Mandantentrennung und Trip/Vergleich-Teilung sind nicht betroffen: keine Nutzerdaten bewegt, kein Briefing- oder Alarm-Inhalt veraendert.

## Estimated Scope

- **LoC:** ca. -8 / +2 (Testcode)
- **Files:** 1 Aenderung plus 1 Protokoll-Artefakt
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| #3208, #3263, #3264, #3265, `rework_3265_fallback_dubletten` | spec | Vorgaenger; Kriterium (identisch oder echte Teilmenge) und Mutationsmethode |
| `tests/tdd/test_3047_r8py_luecken.py` | test | Aenderungsort; enthaelt den Waechter `test_f1_altbestand_leer_sms_folgt_register_wie_editor_gespeichert` (Z. 51-53) und den Test mit den Zeilen 117-118 |
| `src/output/tokens/builder.py` (`FORECAST_THP`) | module | Mutationsziel M1 (`"TH+:"` zu `"TX+:"`); bleibt unveraendert |
| Premium-SMS-Textaufbau (wird beim Mutieren im Quelltext festgelegt und im Protokoll benannt) | module | Mutationsziel M2; bleibt unveraendert |
| `tests/tdd/_einstellung_gleich_mail_trip_fixtures.py` (`trip_json`, Vorgabe `email_format: "full"`) | test-helper | belegt gleiche Eingabe beider Tests; bleibt unveraendert |
| `tests/tdd/test_einstellung_gleich_mail_fallliste.py` | test | Gate `pruefe_testverweise`; der betroffene Test steht in keiner Fallliste, sein Name bleibt ohnehin |
| 13 weitere Dateien (3039, 3039_fixloop, s1c4b fixloop1/2/3, 3047 runde7 orte_kanaele/luecken/mail/sms_kuerzung/sonnenstunden/telegram, r7 kanaele_trip, r9) | test | geprueft, unveraendert; viele Helfer/Fixtures werden dateiuebergreifend importiert |
| ADR-0094, ADR-0095 | decision | Test-Schichten; Kanal-Paritaet (kein Kanal verliert Abdeckung) |

## Implementation Details

### Kriterium

Entfernt wird nur, was identisch ist (gleiche Funktion, gleiche Eingabe, gleiche Erwartung) oder echte Teilmenge einer bleibenden Zusicherung. "Aehnlich" (andere Ebene, andere Werte, anderer Eingangsweg, anderer Kanal) bleibt.

### G7a: r8py, Z. 117-118 gegen Z. 51-53

Bleibende Seite: `test_f1_altbestand_leer_sms_folgt_register_wie_editor_gespeichert` prueft die SMS exakt als `E1 W- G45@4 R2.0@4 TH:M@4 TH+:- FZ2500@4 VS- D15/15`, dass die gespeicherte Liste dieselbe SMS ergibt und dass Premium-SMS beider Laeufe gleich der SMS ist. Die Eingabe ist identisch (`trip_json(["wind"], report_config=_SMS_KANAELE)` gegen `{**_SMS_KANAELE, "email_format": "full"}`, wobei `full` die Vorgabe von `trip_json` ist; beide Male `render_trip_mit_ausblick`, `metrics` leer beziehungsweise gleich aufgebaut gespeichert).

Zu entfernen im anderen Test:
- Z. 117 (`sms`-Praefixe gleich `_SMS_KUERZEL`): folgt zwingend aus dem exakten String des Waechters.
- Z. 118 (`premium_sms` gleich `sms_roh`): im Waechter durch `premium == premium_gesp == sms` enthalten, echte Teilmenge.

Mit den Zeilen fallen die dann ungenutzten Dict-Schluessel `sms`, `premium_sms`, `sms_roh` in `_alle_kanaele` und die nur dort benutzte Konstante `_SMS_KUERZEL` weg. Der Docstring nennt den SMS-Test als Waechter fuer SMS und Premium-SMS. Der Testname bleibt.

### Ausdruecklich bleibt (aehnlich, aber nicht doppelt)

- Premium-Ausgang gegen Trip-Versand (fixloop3): Premium-Test strenger (exakt `R-`, genau eine Sendung).
- Versand gegen Vorschau (fixloop3, 3039 ac13, orte_kanaele Renderer/Kette/Vorschau): andere Wege.
- r8py t4 (Fenster 10,10) gegen tagesfenster "nie eingestellt": andere Eingabe, eigener Rueckfallzweig.
- r7 `roh_gleich_mail_roh` gegen `roh_zeigt_grad`: zusaetzliche Mail-Liste, anderes Pruefziel.
- orte_luecken bl2 (sms gegen marker): `preset()` gegen nie eingestellt, "irgendwo" gegen "am Ende".
- orte_luecken bl4 gegen sms_kuerzung "nie eingestellt": andere Wetter-Naht, andere Soll-Listen.
- 3039 ac1/ac7/f001/f005: bewusst verschiedene Eingaben (`False`, Feld fehlt, Dublette).
- s1c4b Klammer-Tests (fixloop1/2/3): verschiedene Reihen, je eine eigene Regel.
- fixloop1 leere Ampel gegen fixloop2 Gewitter-Leser: andere Produktfunktionen.
- Tabelle, Kachel, Telegram-Kurzuebersicht: andere Ebenen.
- r8py t2 gegen r9: eigene `outlook_metrics` gegen Altbestand ohne Liste.
- Doppelter Helfercode (`_sms_ort`, `zwei_nutzer`, `_ergebnis`, `mit`, `preset` in den Orte-Dateien) ist keine doppelte Zusicherung und nicht Gegenstand dieses Tickets.

### Mutationsnachweis (vorher UND nachher)

Jede Mutation per String-Ersetzung im Produktcode mit externer Sicherungskopie im Scratchpad, danach Wiederherstellung aus der Sicherung, nie `git checkout/stash/reset`. Es laufen nur benannte Testdateien, Kern-Schicht mit `-m "not live"`. Das Protokoll (Mutation, rot vorher, rot nachher, wiederhergestellt gruen, Begruendung je bleibendem Paar) steht unter `docs/artifacts/rework-3266-fixloop-doppelte-tests/`.

| Mutation | Ziel | Vorher | Nachher |
|---|---|---|---|
| M1 | `FORECAST_THP` in `src/output/tokens/builder.py`: `"TH+:"` zu `"TX+:"` | beide f1-Tests rot (Jeder-Kanal-Test ueber Z. 117) | `test_f1_altbestand_leer_sms_folgt_register_wie_editor_gespeichert` rot |
| M2 | Premium-SMS-Text weicht von der SMS ab (Stelle im Premium-Textaufbau, im Protokoll benannt) | Waechter (Z. 53) und ggf. Z. 118 rot | Waechter (Z. 53) rot |

Ist eine Mutation nachher gruen, wird nicht ausgeliefert.

### Nicht im Umfang

- Aenderungen an den 13 anderen Dateien, Loeschen von Testdateien, Tests oder Helfern.
- Zusammenlegen des doppelten Helfercodes.
- Aenderung an Gate-Konfiguration: keine; kein Schritt braucht eine menschliche Gate-Sperre oder einen Override.

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `tests/tdd/test_3047_r8py_luecken.py` | MODIFY | Z. 117-118, ungenutzte Schluessel `sms`/`premium_sms`/`sms_roh` und `_SMS_KUERZEL` entfernen, Docstring anpassen (ca. -8/+2 LoC) |
| `docs/artifacts/rework-3266-fixloop-doppelte-tests/` | CREATE | Mutationsprotokoll M1/M2 vorher/nachher inkl. Paar-Begruendungen |

Nicht geaendert (geprueft): die 13 uebrigen Dateien der Gruppe, `tests/tdd/test_einstellung_gleich_mail_fallliste.py`, `src/output/tokens/builder.py` und aller sonstige Produktionscode.

## Expected Behavior

- **Input:** Testbestand mit einer Teilmengen-Dopplung (zwei Zeilen im Jeder-Kanal-Test gegen den SMS-Waechter).
- **Output:** gleiche geprueften Zusicherungen, je an einer wirksamen Stelle; zwei Zeilen weniger; Kern-Schicht der 14 Dateien weiter 100 % gruen.
- **Side effects:** keine Auswirkung auf Produktverhalten oder Deploy-Inhalt.

## Test Plan

Es entsteht kein neuer Produktionscode. Der RED-Schritt ist der Mutationsnachweis "vorher", der Nachweis "nachher" der GREEN-Beleg. Keine Mock-Tests, keine Dateiinhalt-Checks als Verhaltensnachweis.

### Automated Tests (TDD RED)

- [ ] Test 1: GIVEN der Stand vor dem Umbau WHEN M1 angewendet wird THEN sind beide f1-Tests in `test_3047_r8py_luecken.py` rot (Ausgangsprotokoll).
- [ ] Test 2: GIVEN der Stand nach dem Umbau WHEN M1 angewendet wird THEN ist `test_f1_altbestand_leer_sms_folgt_register_wie_editor_gespeichert` rot und nach Wiederherstellung wieder gruen.
- [ ] Test 3: GIVEN der Stand nach dem Umbau WHEN M2 angewendet wird THEN ist der SMS-Waechter rot und nach Wiederherstellung wieder gruen.
- [ ] Test 4: GIVEN `pytest --collect-only -q` auf die 14 Dateien vorher und nachher THEN ist die Testanzahl gleich und es gibt keine Collect-Fehler.
- [ ] Test 5: GIVEN die 14 Dateien und `test_einstellung_gleich_mail_fallliste.py` WHEN sie namentlich mit `-m "not live"` laufen THEN sind alle gruen (`uv run pytest` nie ohne benannte Dateien, #1477).

## Definition of Done

- [ ] Zeilen und ungenutzte Hilfsdaten entfernt, Testname bleibt (AC-1)
- [ ] Mutationsnachweis M1 vorher/nachher (AC-2)
- [ ] Mutationsnachweis M2 nachher (AC-3)
- [ ] 14 Dateien und Fallliste-Gate gruen, alle 6 CI-Checks gruen, Adversary-Verdict VERIFIED (AC-4)
- [ ] Nichts anderes geloescht, Diff nur unter tests/ und docs/, Ertrag ehrlich benannt (AC-5)

## Acceptance Criteria

- **AC-1:** Given die Zeilen 117-118 in `test_f1_altbestand_leer_jeder_kanal_folgt_editor` sind echte Teilmenge von Z. 51-53 des SMS-Waechters / When der Umbau fertig ist / Then sind diese beiden Zeilen sowie die dann ungenutzten Dict-Schluessel `sms`, `premium_sms`, `sms_roh` in `_alle_kanaele` und die Konstante `_SMS_KUERZEL` entfernt, der Docstring nennt den SMS-Test als Waechter fuer SMS und Premium-SMS, und der Testname bleibt unveraendert.
  - Test: `pytest --collect-only -q` auf `tests/tdd/test_3047_r8py_luecken.py` zeigt beide f1-Tests ohne Collect-Fehler; beide laufen gruen; `_SMS_KUERZEL` und `sms_roh` kommen in der Datei nicht mehr vor.

- **AC-2:** Given die Mutation M1 (`FORECAST_THP` in `src/output/tokens/builder.py` von `"TH+:"` auf `"TX+:"`) per String-Ersetzung mit externer Sicherungskopie / When sie vor und nach dem Umbau in der Kern-Schicht auf `test_3047_r8py_luecken.py` angewendet wird / Then wird sie vorher von beiden f1-Tests gefangen, nachher weiterhin von `test_f1_altbestand_leer_sms_folgt_register_wie_editor_gespeichert`, und nach Wiederherstellung aus der Sicherung ist die Datei wieder gruen.
  - Test: Mutationsprotokoll M1 (vorher, nachher, wiederhergestellt) unter `docs/artifacts/rework-3266-fixloop-doppelte-tests/`.

- **AC-3:** Given die Mutation M2, bei der der Premium-SMS-Text von der SMS abweicht, per String-Ersetzung mit externer Sicherungskopie / When sie nach dem Umbau auf `test_3047_r8py_luecken.py` angewendet wird / Then faengt weiterhin der SMS-Waechter (Premium gleich SMS) die Mutation, und nach Wiederherstellung aus der Sicherung ist die Datei wieder gruen.
  - Test: Mutationsprotokoll M2 unter `docs/artifacts/rework-3266-fixloop-doppelte-tests/`, mit benannter Mutationsstelle.

- **AC-4:** Given die 14 Testdateien der Gruppe und das Gate `tests/tdd/test_einstellung_gleich_mail_fallliste.py` / When sie namentlich mit `-m "not live"` ausgefuehrt werden (nie `uv run pytest` ohne Dateien) / Then sind alle gruen, die Kern-Schicht ist zu 100 % gruen und alle 6 CI-Checks des PR sind gruen.
  - Test: lokaler Lauf der benannten Dateien; CI-Lauf des PR mit allen 6 Checks gruen.

- **AC-5:** Given die uebrigen Paare sind nur aehnlich, nicht doppelt / When der Umbau fertig ist / Then ist ausser den in AC-1 genannten Zeilen und Hilfsdaten kein Test, kein Helfer und keine Datei geloescht, alle geaenderten Dateien liegen unter `tests/` oder `docs/`, der Produktionscode ist byte-identisch zur Sicherung wiederhergestellt, und das Protokoll nennt ehrlich, dass der Ertrag klein ist (eine Teilmenge in 101 Testfunktionen) und begruendet je bleibendem Paar, warum es bleibt.
  - Test: `git diff --name-only origin/main` enthaelt keinen Pfad ausserhalb von `tests/` und `docs/`; `git diff origin/main -- src/` ist leer; die Testanzahl per `--collect-only` ist vorher und nachher gleich.

## Known Limitations

- Die Ausbeute ist bewusst klein (zwei Zeilen in einem Test); "fast nichts doppelt" ist selbst ein Befund fuer #1196.
- Doppelter Helfercode in den Orte-Dateien bleibt; er ist keine doppelte Zusicherung.
- Mutationen werden von Hand gesetzt; ein automatischer Mutationslauf ist nicht Teil dieser Scheibe.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** reine Testbereinigung nach bestehender Test-Politik (ADR-0094) und der in #3207/#3208 verankerten Regel; keine neue Architekturentscheidung, kein neues Gate.

## Changelog

- 2026-11-23: Initial spec created
