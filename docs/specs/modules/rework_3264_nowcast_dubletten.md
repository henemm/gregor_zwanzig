---
entity_id: rework_3264_nowcast_dubletten
type: refactor
created: 2026-11-23
updated: 2026-11-23
status: draft
version: "1.0"
issue: 3264
epic: 1196
workflow: rework-3264-nowcast-dubletten
tags: [tests, aufraeumen, doppelte-zusicherungen, nowcast, radar]
---

# Doppelte Zusicherungen in den Nowcast/Radar-Tests entfernen (#3264)

## Approval

- [ ] Approved

## Purpose

Dieselbe Regel soll an genau einer Stelle geprueft werden. Diese Scheibe (Gruppe G5 aus #3208) prueft die Nowcast/Radar-Testdateien 656, 660, 734 und 761 auf doppelte Zusicherungen. Es gibt zwei belegte Dopplungen: einen Test, der eine echte Teilmenge eines anderen ist (G5a), und zwei wortgleiche Asserts in einem Test, der ohnehin unter xfail laeuft (G5b). Alles andere in diesen Dateien ist nur aehnlich und bleibt. Die Hauptleistung ist der Nachweis per Mutation, dass durch das Entfernen kein Schutz verloren geht.

## Source

- **File:** `docs/context/rework-3264-nowcast-dubletten.md` (Abschnitte "Analysis", G5a, G5b, "bleibt")
- **Identifier:** `tests/tdd/test_feature_656_radar_nowcast.py::test_ac2_intensity_to_text_levels` und `tests/tdd/test_feature_761_icon_d2_nowcast.py::test_ac2_chain_routing_precedence`; Vorbild fuer Methode und Aufbau: `docs/specs/modules/rework_3263_doppelte_zusicherungen_2795.md` (#3263) und `rework_3208_doppelte_zusicherungen.md` (#3208)

Schicht: reine Testsuite-Sanierung. Kein Produktcode in `src/`, `api/`, `internal/`, `scripts/`, `cmd/` oder `frontend/src/` wird veraendert (die Mutationen an `src/services/radar_service.py` sind temporaer und werden aus externer Sicherung wiederhergestellt). Kanaele (E-Mail, Telegram, SMS, Premium-SMS), Mandantentrennung und Trip/Vergleich-Teilung sind nicht betroffen: keine Nutzerdaten bewegt, kein Briefing-/Alarm-Inhalt veraendert.

## Estimated Scope

- **LoC:** ca. -20 / +5 (Testcode und Spec-Verweis)
- **Files:** 3 Aenderungen plus 1 Protokoll-Artefakt
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| #3208 / `rework_3208_doppelte_zusicherungen`, #3263 / `rework_3263_doppelte_zusicherungen_2795` | spec | Vorgaenger; Kriterium (identisch oder echte Teilmenge) und Mutationsmethode |
| `src/services/radar_service.py` (`intensity_to_text` Z. 627-647, `get_nowcast`) | module | geprueftes Verhalten; Mutationsziele; bleibt unveraendert |
| `tests/tdd/test_feature_656_radar_nowcast.py` | test | enthaelt den entfallenden Teilmengen-Test (G5a) |
| `tests/tdd/test_feature_660_convective_stage.py` | test | enthaelt den bleibenden Obermengen-Test `test_ac1_intensity_non_convective_unchanged` |
| `tests/tdd/test_feature_734_arome_france_nowcast.py` | test | enthaelt den bleibenden, live wirksamen Kettentest (G5b) |
| `tests/tdd/test_feature_761_icon_d2_nowcast.py` | test | Aenderungsort G5b (Test steht unter xfail strict=False, #1144) |
| `docs/specs/modules/radar_nowcast.md` (Z. 102) | spec | Testverweis AC-2 wird umgestellt |
| `docs/specs/modules/radar_nowcast_icon_d2.md` (Z. 121) | spec | nennt `test_ac2_chain_routing_precedence`; Test bleibt bestehen, Spec unveraendert |
| ADR-0094, ADR-0095 | decision | Test-Schichten; Kanal-Paritaet (kein Kanal verliert Abdeckung) |

## Implementation Details

### Kriterium

Entfernt wird nur, was identisch ist (gleiche Funktion, gleiche Eingabe, gleiche Erwartung) oder echte Teilmenge einer bleibenden Zusicherung. "Aehnlich" (andere Schicht, andere Werte, anderer Eingangsweg, andere Quelle) bleibt.

### G5a: 656 gegen 660, `intensity_to_text`

`test_ac2_intensity_to_text_levels` (656) ruft `intensity_to_text(r)` fuer die Raten 0.0, 0.3, 2.5 und 8.0 auf. `test_ac1_intensity_non_convective_unchanged` (660) ruft dieselben vier Raten mit `is_convective=False` mit denselben Erwartungen auf und zusaetzlich `intensity_to_text(8.0)` ueber das Default-Argument. Der Default ist `is_convective=False` (`radar_service.py` Z. 628), der Aufruf ohne Argument ist also gleichwertig. Der 656-Test ist damit echte Teilmenge und wird entfernt. Der Default-Pfad bleibt durch die Default-Zeile im 660-Test bewacht. Der Testverweis in `docs/specs/modules/radar_nowcast.md` Z. 102 (AC-2) wird auf `test_feature_660_convective_stage.py::test_ac1_intensity_non_convective_unchanged` umgestellt; die beiden `format_now_text`-Tests in derselben Zeile bleiben.

### G5b: 734 gegen 761, Routing-Kette

Die Asserts `get_nowcast(_BERLIN) == "radar"` und `get_nowcast(_ATLANTIC) == "minutely_15"` stehen wortgleich (gleiche Koordinaten 52.52/13.40 und 35.0/-40.0) in `test_ac2_chain_routing_berlin_radar_atlantic_global` (734, live, wirksam) und in `test_ac2_chain_routing_precedence` (761, xfail strict=False, #1144). In 761 werden der Berlin- und der Atlantik-Assert entfernt, der Docstring wird angepasst. Die Konstanten `_BERLIN_LAT, _BERLIN_LON` (Z. 30) werden danach nicht mehr benutzt und mit entfernt. `_ATLANTIC_LAT/_ATLANTIC_LON` bleiben, weil `within(_ATLANTIC)` weiter genutzt wird. Die Asserts zu Slowenien und Schweiz-West (AROME-Vorrang vor ICON-D2) bleiben, sie stehen nur in 761.

### Ausdruecklich bleibt (aehnlich, aber nicht doppelt)

- `ac4_*_convective_drives_intensity` (734 und 761): andere Quelle ("AROME-FR" gegen "ICON-D2") und andere Raten (0.3/2.0 gegen 0.4/3.0).
- `within(_ATLANTIC) is False` in 761: andere Funktion (`_within_icon_d2` gegen `_within_arome_france`).
- 656 `ac4_radar_alert_*` gegen 660 `ac4_radar_alert_convective_marked_once_then_throttles`: anderer (konvektiver) Fall.
- 656 `format_now_text_*` gegen 660 `ac3_derive_result_convective_label_and_text`: andere Eingaben.
- `docs/specs/_archive/...` bleibt unveraendert.

### Mutationsnachweis (vorher UND nachher)

Jede Mutation per String-Ersetzung im Produktcode mit externer Sicherungskopie im Scratchpad, danach Wiederherstellung aus der Sicherung, nie `git checkout/stash/reset`. Es laufen nur benannte Testdateien. Das Protokoll (Mutation, rot vorher, rot nachher, wiederhergestellt gruen) steht unter `docs/artifacts/rework-3264-nowcast-dubletten/`.

| Mutation | Ziel | Vorher | Nachher |
|---|---|---|---|
| M1 (G5a, Kern-Schicht) | `intensity_to_text`: Grenze leicht/maessig `mm_per_h < 1.0` wird zu `< 3.0` (2.5 mm/h ergibt dann "Leichter Regen") | 656 UND 660 rot | 660 allein rot |
| M2 (G5a, Default) | `intensity_to_text`: Default `is_convective=False` wird zu `True` | 656 und 660 rot | 660 rot (Default-Zeile) |
| M3 (G5b, Live-Schicht, `-m live`) | `get_nowcast`: Berlin faellt nicht mehr auf "radar" bzw. Atlantik nicht mehr auf "minutely_15" (Box bzw. Global-Fallback per String-Ersetzung veraendert) | 734 rot (761 faengt wegen xfail nichts) | 734 rot |

M3 ist nur in der Live-Schicht beobachtbar, weil der wirksame 734-Test `live` markiert ist; die Messung laeuft mit `-m live`. Ist eine Mutation nachher gruen, wird nicht ausgeliefert.

### Nicht im Umfang

- Fachliche Umbenennung oder Zusammenlegung von Testdateien.
- Aenderung an Gate-Konfiguration: keine.
- Die Nebenbefunde unter Known Limitations werden nicht umgesetzt.

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `tests/tdd/test_feature_656_radar_nowcast.py` | MODIFY | `test_ac2_intensity_to_text_levels` entfernen (ca. -9 LoC) |
| `tests/tdd/test_feature_761_icon_d2_nowcast.py` | MODIFY | Berlin- und Atlantik-Assert in `test_ac2_chain_routing_precedence` entfernen, Docstring anpassen, `_BERLIN_LAT/_BERLIN_LON` entfernen (ca. -8/+3 LoC) |
| `docs/specs/modules/radar_nowcast.md` | MODIFY | AC-2-Testverweis Z. 102 auf den 660-Test umstellen (ca. -1/+1 LoC) |
| `docs/artifacts/rework-3264-nowcast-dubletten/` | CREATE | Mutationsprotokoll M1-M3 vorher/nachher |

Nicht geaendert (geprueft): `tests/tdd/test_feature_660_convective_stage.py`, `tests/tdd/test_feature_734_arome_france_nowcast.py`, `docs/specs/modules/radar_nowcast_icon_d2.md`, `src/services/radar_service.py` und aller sonstige Produktionscode.

## Expected Behavior

- **Input:** Testbestand mit einer Teilmengen-Dopplung (G5a) und zwei wortgleichen Asserts (G5b).
- **Output:** gleiche geprueften Zusicherungen, je an einer wirksamen Stelle; ein Test (4 Stufen) und zwei Asserts weniger; Kern-Schicht der vier Dateien weiter 100 % gruen.
- **Side effects:** keine Auswirkung auf Produktverhalten oder Deploy-Inhalt.

## Test Plan

Es entsteht kein neuer Produktionscode. Der RED-Schritt ist der Mutationsnachweis "vorher", der Nachweis "nachher" der GREEN-Beleg. Keine Mock-Tests, keine Dateiinhalt-Checks als Verhaltensnachweis.

### Automated Tests (TDD RED)

- [ ] Test 1: GIVEN der Stand vor dem Umbau WHEN M1 und M2 angewendet werden THEN sind 656 `test_ac2_intensity_to_text_levels` und 660 `test_ac1_intensity_non_convective_unchanged` rot (Ausgangsprotokoll).
- [ ] Test 2: GIVEN der Stand nach dem Umbau WHEN M1 und M2 angewendet werden THEN ist 660 `test_ac1_intensity_non_convective_unchanged` rot und nach Wiederherstellung wieder gruen.
- [ ] Test 3: GIVEN M3 vorher und nachher WHEN 734 und 761 mit `-m live` laufen THEN faengt 734 `test_ac2_chain_routing_berlin_radar_atlantic_global` die Mutation in beiden Staenden.
- [ ] Test 4: GIVEN `pytest --collect-only -q` auf die vier Dateien vorher und nachher THEN fehlt genau `test_ac2_intensity_to_text_levels` und es gibt keine Collect-Fehler.
- [ ] Test 5: GIVEN die vier Dateien 656, 660, 734, 761 WHEN sie namentlich mit `-m "not live"` laufen THEN sind alle gruen (`uv run pytest` nie ohne benannte Dateien, #1477).

## Definition of Done

- [ ] 656-Teilmengen-Test entfernt, Spec-Verweis umgestellt (AC-1)
- [ ] 761: Berlin-/Atlantik-Assert und `_BERLIN_LAT/_BERLIN_LON` entfernt, Docstring angepasst, Rest unveraendert (AC-2)
- [ ] Mutationsnachweis G5a vorher/nachher in der Kern-Schicht (AC-3)
- [ ] Mutationsnachweis G5b vorher/nachher in der Live-Schicht (AC-4)
- [ ] Bleibende, nur aehnliche Tests unveraendert (AC-5)
- [ ] Kern-Schicht der vier Dateien 100 % gruen, alle 6 CI-Checks gruen, Adversary-Verdict VERIFIED (AC-6)
- [ ] Diff nur unter tests/ und docs/, Produktionscode unveraendert, Protokoll und Wiederherstellung belegt (AC-7)

## Acceptance Criteria

- **AC-1:** Given der Test `test_ac2_intensity_to_text_levels` in 656 ist echte Teilmenge von `test_ac1_intensity_non_convective_unchanged` in 660 / When der Umbau fertig ist / Then ist der 656-Test entfernt, der 660-Test unveraendert vorhanden, und der Testverweis bei AC-2 in `docs/specs/modules/radar_nowcast.md` nennt statt des entfernten Tests den 660-Test (die beiden `format_now_text`-Verweise bleiben).
  - Test: `pytest --collect-only -q` auf 656 zeigt den entfernten Test nicht mehr, auf 660 weiterhin; der 660-Test laeuft gruen; kein Verweis auf den entfernten Testnamen in `docs/specs/modules/`.

- **AC-2:** Given `test_ac2_chain_routing_precedence` in 761 enthaelt Berlin- und Atlantik-Assert, die wortgleich im wirksamen Test `test_ac2_chain_routing_berlin_radar_atlantic_global` in 734 stehen / When der Umbau fertig ist / Then fehlen beide Asserts samt der unbenutzten Konstanten `_BERLIN_LAT/_BERLIN_LON` in 761, der Docstring beschreibt nur noch den AROME-Vorrang vor ICON-D2 (Slowenien, Schweiz-West), `_ATLANTIC` und der `within`-Assert bleiben, und der Test ist weiter unter xfail strict=False markiert.
  - Test: `pytest --collect-only -q` auf 761 ohne Collect-Fehler; Test `test_ac2_chain_routing_berlin_radar_atlantic_global` in 734 unveraendert vorhanden.

- **AC-3:** Given die Mutationen M1 (Grenze leicht/maessig in `intensity_to_text` von 1.0 auf 3.0 verschoben) und M2 (Default `is_convective` von False auf True) per String-Ersetzung mit externer Sicherungskopie / When sie vor und nach dem Umbau in der Kern-Schicht angewendet werden / Then sind vorher 656 und 660 rot, nachher 660 rot (Teilmenge verliert keinen Schutz), und nach Wiederherstellung aus der Sicherung sind beide Dateien wieder gruen.
  - Test: Mutationsprotokoll M1/M2 (vorher, nachher, wiederhergestellt) unter `docs/artifacts/rework-3264-nowcast-dubletten/`.

- **AC-4:** Given die Mutation M3 an der Routing-Kette in `get_nowcast` (Berlin bzw. Atlantik wird falsch geroutet) / When sie vor und nach dem Umbau mit `-m live` gegen 734 und 761 angewendet wird / Then faengt der Test in 734 die Mutation in beiden Staenden, waehrend 761 dort wegen xfail nichts faengt, und nach Wiederherstellung aus der Sicherung ist 734 wieder gruen.
  - Test: Mutationsprotokoll M3 (nur Live-Schicht beobachtbar) unter `docs/artifacts/rework-3264-nowcast-dubletten/`.

- **AC-5:** Given es gibt aehnliche, aber nicht doppelte Tests (`ac4_*_convective_drives_intensity` in 734 und 761, `within(_ATLANTIC)`, 656 `ac4_radar_alert_*` und `format_now_text_*` gegen 660) / When der Umbau fertig ist / Then sind diese Tests und Asserts unveraendert, und das Mutationsprotokoll nennt je Paar die Begruendung (andere Quelle, andere Werte, andere Funktion, anderer Fall), warum es bleibt.
  - Test: Diff der Testdateien zeigt nur die in AC-1 und AC-2 genannten Entfernungen; Paar-Begruendungen im Protokoll im Review geprueft.

- **AC-6:** Given die vier Testdateien 656, 660, 734 und 761 / When sie namentlich mit `-m "not live"` ausgefuehrt werden (nie `uv run pytest` ohne Dateien) / Then sind alle gruen, die Kern-Schicht ist zu 100 % gruen und alle 6 CI-Checks des PR sind gruen.
  - Test: lokaler Lauf der benannten Dateien; CI-Lauf des PR mit allen 6 Checks gruen.

- **AC-7:** Given der Umbau betrifft nur Testsammlung und Dokumentation / When der Diff gegen `origin/main` geprueft wird / Then liegen alle geaenderten Dateien unter `tests/` oder `docs/`, `src/services/radar_service.py` ist byte-identisch zur externen Sicherung wiederhergestellt (kein Diff gegen `origin/main`), und es gibt keine Aenderung an Gate-Konfiguration.
  - Test: `git diff --name-only origin/main` enthaelt keinen Pfad ausserhalb von `tests/` und `docs/`; `git diff origin/main -- src/services/radar_service.py` ist leer.

## Known Limitations

- Die Ausbeute ist bewusst klein (ein Test, zwei Asserts); "fast nichts doppelt" ist selbst ein Befund fuer #1196.
- G5b ist nur in der Live-Schicht messbar, weil der wirksame 734-Test `live` markiert ist; die Kern-Schicht kann diese Gruppe nicht bewachen.
- Nebenbefund, nicht Teil dieser Scheibe (Sammel-Issue #1199): `761::test_ac4_icon_d2_convective_drives_intensity` ist `live` markiert, obwohl deterministisch (`_derive_result` mit festen Frames), und laeuft daher nur in der Live-Schicht statt im Kern.
- Nebenbefund, nicht Teil dieser Scheibe (Sammel-Issue #1199): `761::test_ac2_chain_routing_precedence` macht echte Netzaufrufe ohne `live`-Marker; xfail strict=False verdeckt das.
- Mutationen werden von Hand gesetzt; ein automatischer Mutationslauf ist nicht Teil dieser Scheibe.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** reine Testbereinigung nach bestehender Test-Politik (ADR-0094) und der in #3207/#3208 verankerten Regel; keine neue Architekturentscheidung, kein neues Gate.

## Changelog

- 2026-11-23: Initial spec created
