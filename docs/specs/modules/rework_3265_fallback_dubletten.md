---
entity_id: rework_3265_fallback_dubletten
type: refactor
created: 2026-11-23
updated: 2026-11-23
status: draft
version: "1.0"
issue: 3265
epic: 1196
workflow: rework-3265-fallback-dubletten
tags: [tests, aufraeumen, doppelte-zusicherungen, provider-fallback]
---

# Doppelte Zusicherungen in den Provider-Fallback-Tests entfernen (#3265)

## Approval

- [ ] Approved

## Purpose

Dieselbe Regel soll an genau einer Stelle geprueft werden. Diese Scheibe (Gruppe G6 aus #3208) prueft die Provider-Fallback-Testdateien 1115, 1141, 1142 und 1155 auf doppelte Zusicherungen. Es gibt genau eine belegte Dopplung: Fall (a) in `test_seam_catches_provider_request_and_not_found_error` (1142) ist identisch mit einem Teil von `test_geosphere_5xx_preserves_original_error_and_retry` (ac3) derselben Datei. Alle anderen Paare sind nur aehnlich und bleiben. Die Hauptleistung ist der Nachweis per Mutation, dass durch das Entfernen kein Schutz verloren geht.

## Source

- **File:** `docs/context/rework-3265-fallback-dubletten.md` (Abschnitte "Analysis", G6a, "Geprueft, bleibt")
- **Identifier:** `tests/tdd/test_issue_1142_geosphere_direct_fallback.py::test_seam_catches_provider_request_and_not_found_error`; Vorbild fuer Methode und Aufbau: `docs/specs/modules/rework_3264_nowcast_dubletten.md` (#3264), `rework_3263_doppelte_zusicherungen_2795.md` (#3263) und `rework_3208_doppelte_zusicherungen.md` (#3208)

Schicht: reine Testsuite-Sanierung. Kein Produktcode in `src/`, `api/`, `internal/`, `scripts/`, `cmd/` oder `frontend/src/` wird veraendert (die Mutationen an `src/providers/openmeteo.py` sind temporaer und werden aus externer Sicherung wiederhergestellt). Kanaele (E-Mail, Telegram, SMS, Premium-SMS), Mandantentrennung und Trip/Vergleich-Teilung sind nicht betroffen: keine Nutzerdaten bewegt, kein Briefing-/Alarm-Inhalt veraendert.

## Estimated Scope

- **LoC:** ca. -15 / +3 (Testcode)
- **Files:** 1 Aenderung plus 1 Protokoll-Artefakt
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| #3208, #3263 / #3264, `rework_3264_nowcast_dubletten` | spec | Vorgaenger; Kriterium (identisch oder echte Teilmenge) und Mutationsmethode |
| `src/providers/openmeteo.py` (`fetch_forecast`, Cross-Provider-Seam mit `except`-Block) | module | geprueftes Verhalten; Mutationsziel; bleibt unveraendert |
| `tests/tdd/test_issue_1142_geosphere_direct_fallback.py` | test | Aenderungsort; enthaelt `test_geosphere_5xx_preserves_original_error_and_retry` (ac3) (Wächter fuer Fall a) und den Test mit Fall (a)/(b) |
| `tests/tdd/test_issue_1115_model_fallback.py` | test | bleibt unveraendert; `_provider_seam` und `_BERLIN` werden von 1155 importiert |
| `tests/tdd/test_issue_1141_cross_provider_fallback.py` | test | bleibt unveraendert (nur aehnliche Paare) |
| `tests/tdd/test_issue_1155_retry_tuning.py` | test | bleibt unveraendert; importiert `_provider_seam`/`_BERLIN` aus 1115 per importlib |
| `docs/specs/modules/provider_dwd.md` (Z. 109), `provider_meteofrance.md` (Z. 106) | spec | verweisen "analog" auf den Testnamen; Name bleibt, keine Aenderung |
| ADR-0094, ADR-0095 | decision | Test-Schichten; Kanal-Paritaet (kein Kanal verliert Abdeckung) |

## Implementation Details

### Kriterium

Entfernt wird nur, was identisch ist (gleiche Funktion, gleiche Eingabe, gleiche Erwartung) oder echte Teilmenge einer bleibenden Zusicherung. "Aehnlich" (andere Schicht, andere Werte, anderer Eingangsweg, anderer Provider) bleibt.

### G6a: 1142, Fall (a) gegen `test_geosphere_5xx_preserves_original_error_and_retry` (ac3)

`test_geosphere_5xx_preserves_original_error_and_retry` (ac3) und Fall (a) in `test_seam_catches_provider_request_and_not_found_error` haben identischen Aufbau (`_geosphere_fault_server`, `_FutureAtDirectAdapter` als `at_direct`, `_total_outage_seam`, `_INNSBRUCK`), identischen Aufruf `fetch_forecast(_INNSBRUCK, enrich_ensemble=False)` und identische Erwartung (`pytest.raises(ProviderRequestError)`, `exc.value.provider == "openmeteo"`). ac3 prueft zusaetzlich die Retry-Zahl. Fall (a) ist damit echte Teilmenge von ac3 und wird entfernt (Block samt `exc_a`-Assert). Fall (b) (`ProviderNotFoundError`, `at_direct` nicht registriert) steht nur hier und bleibt. Der Testname bleibt (Spec-Verweise); der Docstring nennt ac3 als Waechter fuer den frueheren Fall (a).

### Ausdruecklich bleibt (aehnlich, aber nicht doppelt)

- 1115 ac2 (Berlin, 400, Retry gekappt) gegen 1155 ac3 (Lappland, 404, echter Retry): andere Werte, andere Ebene (1155 misst "kein Retry").
- 1115 ac3 gegen 1155 ac4 und ac2: andere Orte, andere Wege zum Erfolg, andere Erwartung (`fallback_reason`).
- 1115 ac1 gegen 1115 ac3 (Fallback-Haelfte): gleiche Eingabe, andere Erwartung.
- 1155 ac7 `isinstance(NormalizedTimeseries)`: Setup-Assert des Laufzeittests, ohne ihn ist die Zeitmessung bedeutungslos.
- 1141 ac2 gegen 1155 ac1: 1141 traegt die Zusicherung "keine Region", 1155 misst Retry-Zahlen.
- 1141 ac5 gegen 1142 ac3: anderer Direktprovider (DWD gegen GeoSphere), andere Region; 1141 ac5 gegen ac6: andere Erwartung.
- 1141 ac1 (live) gegen ac3: gleiche Eingabe, andere Erwartung.
- `docs/specs/_archive/...` bleibt unveraendert.

### Mutationsnachweis (vorher UND nachher)

Jede Mutation per String-Ersetzung im Produktcode mit externer Sicherungskopie im Scratchpad, danach Wiederherstellung aus der Sicherung, nie `git checkout/stash/reset`. Es laufen nur benannte Testdateien, Kern-Schicht mit `-m "not live"`. Das Protokoll (Mutation, rot vorher, rot nachher, wiederhergestellt gruen, Begruendung je bleibendem Paar) steht unter `docs/artifacts/rework-3265-fallback-dubletten/`.

| Mutation | Ziel | Vorher | Nachher |
|---|---|---|---|
| M1 | Cross-Provider-Seam in `openmeteo.py`: Fang von `ProviderRequestError` aus dem `except` entfernen (GeoSphere-Fehler schlaegt durch) | 1142 ac3 UND ac4 rot | 1142 ac3 rot |
| M2 | Cross-Provider-Seam: Fang von `ProviderNotFoundError` entfernen | 1142 ac4 (Fall b) rot | 1142 ac4 (Fall b) rot |

Ist eine Mutation nachher gruen, wird nicht ausgeliefert.

### Nicht im Umfang

- Aenderungen an 1115, 1141, 1155 (keine weiteren Loeschungen).
- Fachliche Umbenennung oder Zusammenlegung von Testdateien.
- Aenderung an Gate-Konfiguration: keine; kein Schritt braucht eine menschliche Gate-Sperre oder einen Override.
- Nebenbefund 1141 ac1: laut Kommentar offline rot (Ursache offen, #1196 Klasse A) und nur deshalb `live` markiert; wird nicht umgesetzt.

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `tests/tdd/test_issue_1142_geosphere_direct_fallback.py` | MODIFY | Fall (a) in `test_seam_catches_provider_request_and_not_found_error` entfernen, Docstring auf ac3 verweisen (ca. -15/+3 LoC) |
| `docs/artifacts/rework-3265-fallback-dubletten/` | CREATE | Mutationsprotokoll M1/M2 vorher/nachher inkl. Paar-Begruendungen |

Nicht geaendert (geprueft): `tests/tdd/test_issue_1115_model_fallback.py`, `tests/tdd/test_issue_1141_cross_provider_fallback.py`, `tests/tdd/test_issue_1155_retry_tuning.py`, `src/providers/openmeteo.py` und aller sonstige Produktionscode.

## Expected Behavior

- **Input:** Testbestand mit einer Teilmengen-Dopplung (Fall a gegen ac3 in 1142).
- **Output:** gleiche geprueften Zusicherungen, je an einer wirksamen Stelle; ein Fall weniger; Kern-Schicht der vier Dateien weiter 100 % gruen.
- **Side effects:** keine Auswirkung auf Produktverhalten oder Deploy-Inhalt.

## Test Plan

Es entsteht kein neuer Produktionscode. Der RED-Schritt ist der Mutationsnachweis "vorher", der Nachweis "nachher" der GREEN-Beleg. Keine Mock-Tests, keine Dateiinhalt-Checks als Verhaltensnachweis.

### Automated Tests (TDD RED)

- [ ] Test 1: GIVEN der Stand vor dem Umbau WHEN M1 angewendet wird THEN sind 1142 ac3 und `test_seam_catches_provider_request_and_not_found_error` rot (Ausgangsprotokoll).
- [ ] Test 2: GIVEN der Stand nach dem Umbau WHEN M1 angewendet wird THEN ist 1142 ac3 rot und nach Wiederherstellung wieder gruen.
- [ ] Test 3: GIVEN der Stand nach dem Umbau WHEN M2 angewendet wird THEN ist `test_seam_catches_provider_request_and_not_found_error` (Fall b) rot und nach Wiederherstellung wieder gruen.
- [ ] Test 4: GIVEN `pytest --collect-only -q` auf die vier Dateien vorher und nachher THEN ist die Testanzahl gleich (nur ein Fall innerhalb eines Tests entfaellt) und es gibt keine Collect-Fehler.
- [ ] Test 5: GIVEN die vier Dateien 1115, 1141, 1142, 1155 WHEN sie namentlich mit `-m "not live"` laufen THEN sind alle gruen (`uv run pytest` nie ohne benannte Dateien, #1477).

## Definition of Done

- [ ] Fall (a) entfernt, Fall (b) und Testname bleiben, Docstring verweist auf ac3 (AC-1)
- [ ] Mutationsnachweis M1 vorher/nachher (AC-2)
- [ ] Mutationsnachweis M2 nachher (AC-3)
- [ ] Bleibende, nur aehnliche Paare unveraendert, Begruendungen im Protokoll (AC-4)
- [ ] Kern-Schicht der vier Dateien 100 % gruen, alle 6 CI-Checks gruen, Adversary-Verdict VERIFIED (AC-5)
- [ ] Diff nur unter tests/ und docs/, Produktionscode wiederhergestellt, keine weiteren Loeschungen in 1115/1141/1155 (AC-6)

## Acceptance Criteria

- **AC-1:** Given Fall (a) in `test_seam_catches_provider_request_and_not_found_error` (1142) ist identisch mit einem Teil von `test_geosphere_5xx_preserves_original_error_and_retry` (ac3) / When der Umbau fertig ist / Then ist Fall (a) samt `exc_a`-Assert entfernt, Fall (b) (`ProviderNotFoundError`, `at_direct` nicht registriert) mit beiden Asserts und der Testname unveraendert vorhanden, und der Docstring verweist fuer den frueheren Fall (a) auf ac3.
  - Test: `pytest --collect-only -q` auf 1142 zeigt den Test weiterhin ohne Collect-Fehler; der Test laeuft gruen; `exc_a` kommt in der Datei nicht mehr vor.

- **AC-2:** Given die Mutation M1 (Fang von `ProviderRequestError` im Cross-Provider-Seam von `src/providers/openmeteo.py` entfernt) per String-Ersetzung mit externer Sicherungskopie / When sie vor und nach dem Umbau in der Kern-Schicht (`-m "not live"`) auf 1142 angewendet wird / Then wird sie vorher von ac3 und ac4 gefangen, nachher weiterhin von ac3 (Teilmenge verliert keinen Schutz), und nach Wiederherstellung aus der Sicherung ist 1142 wieder gruen.
  - Test: Mutationsprotokoll M1 (vorher, nachher, wiederhergestellt) unter `docs/artifacts/rework-3265-fallback-dubletten/`.

- **AC-3:** Given die Mutation M2 (Fang von `ProviderNotFoundError` im Cross-Provider-Seam entfernt) per String-Ersetzung mit externer Sicherungskopie / When sie nach dem Umbau auf 1142 angewendet wird / Then faengt weiterhin Fall (b) in `test_seam_catches_provider_request_and_not_found_error` die Mutation, und nach Wiederherstellung aus der Sicherung ist die Datei wieder gruen.
  - Test: Mutationsprotokoll M2 unter `docs/artifacts/rework-3265-fallback-dubletten/`.

- **AC-4:** Given es gibt aehnliche, aber nicht doppelte Paare (1115 ac2 gegen 1155 ac3, 1115 ac3 gegen 1155 ac4/ac2, 1155 ac7-Setup-Assert, 1141 ac2 gegen 1155 ac1, 1141 ac5 gegen 1142 ac3, 1141 ac1 gegen ac3) / When der Umbau fertig ist / Then sind 1115, 1141 und 1155 unveraendert, es gibt keine weiteren Loeschungen in 1142, und das Protokoll nennt je Paar die Begruendung (anderer Wert, andere Ebene, anderer Ort, anderer Provider, andere Erwartung), warum es bleibt.
  - Test: Diff der Testdateien zeigt nur die in AC-1 genannte Entfernung; Paar-Begruendungen im Protokoll im Review geprueft.

- **AC-5:** Given die vier Testdateien 1115, 1141, 1142 und 1155 / When sie namentlich mit `-m "not live"` ausgefuehrt werden (nie `uv run pytest` ohne Dateien) / Then sind alle gruen, die Kern-Schicht ist zu 100 % gruen und alle 6 CI-Checks des PR sind gruen.
  - Test: lokaler Lauf der benannten Dateien; CI-Lauf des PR mit allen 6 Checks gruen.

- **AC-6:** Given der Umbau betrifft nur Testsammlung und Dokumentation / When der Diff gegen `origin/main` geprueft wird / Then liegen alle geaenderten Dateien unter `tests/` oder `docs/`, `src/providers/openmeteo.py` ist byte-identisch zur externen Sicherung wiederhergestellt (kein Diff gegen `origin/main`), und es gibt keine Aenderung an Gate-Konfiguration.
  - Test: `git diff --name-only origin/main` enthaelt keinen Pfad ausserhalb von `tests/` und `docs/`; `git diff origin/main -- src/providers/openmeteo.py` ist leer.

## Known Limitations

- Die Ausbeute ist bewusst klein (ein Fall in einem Test); "fast nichts doppelt" ist selbst ein Befund fuer #1196.
- Nebenbefund, nicht Teil dieser Scheibe (Sammel-Issue #1199): 1141 ac1 ist laut Kommentar offline rot (Ursache offen) und nur deshalb `live` markiert.
- Mutationen werden von Hand gesetzt; ein automatischer Mutationslauf ist nicht Teil dieser Scheibe.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** reine Testbereinigung nach bestehender Test-Politik (ADR-0094) und der in #3207/#3208 verankerten Regel; keine neue Architekturentscheidung, kein neues Gate.

## Changelog

- 2026-11-23: Initial spec created
