---
entity_id: rework_3263_doppelte_zusicherungen_2795
type: refactor
created: 2026-11-23
updated: 2026-11-23
status: draft
version: "1.0"
issue: 3263
epic: 1196
workflow: rework-3263-doppelte-tests-2795
tags: [tests, aufraeumen, doppelte-zusicherungen]
---

# Doppelte Zusicherungen in den #2795/#2792-Testdateien entfernen (#3263)

## Approval

- [ ] Approved

## Purpose

Dieselbe Regel soll an genau einer Stelle geprueft werden. Diese Scheibe (Gruppe G4 aus #3208) prueft die Fix-Runden- und Migrations-Testdateien zu #2795/#2792 auf doppelte Zusicherungen. Ehrlicher Befund vorab: Es gibt genau eine echte Teilmenge, der Rest ist trotz der Fix-Runden-Namen inhaltlich disjunkt. Entfernt wird deshalb ein einziger Test; die Hauptleistung ist der Nachweis per Mutation, dass dadurch kein Schutz verloren geht, und die dokumentierte Begruendung, warum die sechs 2795-Dateien unveraendert bleiben.

## Source

- **File:** `docs/context/rework-3263-doppelte-tests-2795.md` (Abschnitt "Analysis": Befund, Mutationsplan)
- **Identifier:** `tests/tdd/test_migration_2792_profil_ampel.py`; Vorbild fuer Methode und Aufbau: `docs/specs/modules/rework_3208_doppelte_zusicherungen.md` (#3208)

Schicht: reine Testsuite-Sanierung. Kein Produktcode in `src/`, `api/`, `internal/`, `scripts/` oder `frontend/src/` wird veraendert (die Mutationen am Migrationsskript sind temporaer und werden aus externer Sicherung wiederhergestellt). Keine Nutzerdaten bewegt, kein Briefing-/Alarm-Inhalt veraendert, alle vier Kanaele bleiben durch ihre bleibenden Tests bewacht. Kein Trip/Vergleich-Pendant betroffen.

## Estimated Scope

- **LoC:** ca. -10 / +2 (Testcode), dazu Protokoll in der Kontext-Doku
- **Files:** 2 (1 Testdatei, 1 Kontext-Dokument)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| #3208 / `rework_3208_doppelte_zusicherungen` | spec | Vorgaenger; Kriterium (identisch oder echte Teilmenge) und Mutationsmethode |
| `scripts/migrate_2792_profil_ampel.py` | module | geprueftes Verhalten; Mutationsziel M1 (Berichtstext, Z. 119) und M2 (`_NICHT_ZUORDENBAR`, Z. 56-62); bleibt unveraendert |
| `tests/tdd/test_migration_2792_profil_ampel.py` | test | enthaelt beide AC-23-Tests, Aenderungsort |
| `tests/test_2795_fixrunde1.py`, `test_2795_fixrunde2.py`, `test_2795_fixrunde3.py`, `test_2795_alert_metric_channels_ignoriert.py`, `test_2795_alte_regel_kanaele_ignoriert.py`, `test_2795_migration_alert_metric_channels.py` | test | geprueft, bleiben unveraendert; teilen Helfer per Import untereinander |
| `docs/specs/modules/feat_2792_s1_profil_ampel.md` (AC-23) | spec | fachliche Grundlage der bleibenden Zusicherung |
| ADR-0094, ADR-0095 | decision | Test-Schichten; Kanal-Paritaet (kein Kanal verliert Abdeckung) |

## Implementation Details

### Kriterium

Entfernt wird nur, was identisch ist (gleiche Funktion, gleiche Eingabe, gleiche Erwartung) oder echte Teilmenge einer bleibenden Zusicherung. "Aehnlich" (andere Schicht, andere Werte, anderer Eingangsweg) bleibt.

### Entscheidung 1: Teilmengen-Test entfernen

`test_ac23_neu_erkannte_nicht_zuordenbare_schluessel_stehen_im_bericht` (5 Faelle: wind_direction_deg, cloud_mid_avg_pct, cloud_high_avg_pct, pressure_avg_hpa, precip_type_dominant) ist echte Teilmenge von `test_ac23_nicht_zuordenbar_mit_begruendung_und_bereich_bleibt_erhalten` (7 Faelle, enthaelt alle 5). Beide rufen `_vgl_ampel(tmp_path, [_band(key, 1, 9)])` auf. Der bleibende Test prueft den vollen Berichtstext (`nicht zuordenbar: {key} [1, 9] (corridors): {grund}, erhalten, nicht migriert` enthaelt `nicht zuordenbar: {key}`), `not ampel.get("metrics")` und zusaetzlich den Erhalt der `corridors`. Es ist keine Zusatz-Zusicherung zu uebernehmen. Der entfallende Test wird samt Parametrisierung entfernt; am bleibenden Test steht der Kommentar, dass er auch die bei #2792 neu erkannten Schluessel abdeckt (ehemals eigener Test, #3263).

### Entscheidung 2: Die sechs 2795-Dateien bleiben unveraendert

Keine Datei enthaelt eine identische Zusicherung oder echte Teilmenge. Aehnliche Paare und der Grund, warum sie bleiben (Details je Paar in der Kontext-Doku):

- alte_regel hoch/gering gegen ac29_trip hoch/gering: anderer Eingangsweg (alte Regel-Kanaele gegen Altschluessel).
- ac29_trip_altschluessel_aendert_nichts gegen ac29_trip_hoch: der erste faehrt zusaetzlich den Fall "ohne Altschluessel".
- ac29_vergleich_kette gegen dispatcher: kette prueft zusaetzlich `split_by_threshold`; der Versandweg ist eine andere Schicht.
- f005_loader gegen Trip-Roundtrip-Test: andere Werte.
- f001 gegen f010, f002_vergleich gegen f011 gegen f013, f011_bestandsvermerk gegen f015, f003 gegen f012 gegen ac28 gegen 10a0: jeweils andere Zweige, Eingaben oder Dateiinhalte.
- 2792 `ratsche` (Band 5,50, alle Schluessel) und `gewitter_und_cape` (andere Baender) bleiben.

Keine ganze Datei entfaellt: jede traegt eigene Zusicherungen, und fixrunde1 sowie alert_metric_channels_ignoriert liefern Helfer an Nachbardateien. Fachliches Umbenennen oder Zusammenlegen waere Umbau, nicht Gegenstand von #3263.

### Mutationsnachweis (vorher UND nachher)

Jede Mutation per String-Ersetzung im Produktcode mit externer Sicherungskopie im Scratchpad, danach Wiederherstellung aus der Sicherung, nie `git checkout/stash/reset`. Es laufen nur benannte Testdateien. Das Protokoll (Mutation, rot vorher, rot nachher, wiederhergestellt gruen) steht in `docs/context/rework-3263-doppelte-tests-2795.md`.

| Mutation | Ziel | Vorher | Nachher |
|---|---|---|---|
| M1 | `scripts/migrate_2792_profil_ampel.py` Z. 119: `"    nicht zuordenbar: {key}` wird zu `"    nicht-zuordenbar: {key}` | `neu_erkannte` UND `begruendung` rot | `begruendung` allein rot |
| M2 (Gegenprobe) | Eintrag `"wind_direction_deg": ...` aus `_NICHT_ZUORDENBAR` entfernen (Schluessel faellt in den allgemeinen Text Z. 125) | `neu_erkannte[wind_direction_deg]` gruen, `begruendung[wind_direction_deg]` rot | `begruendung[wind_direction_deg]` rot |

M2 belegt, dass der bleibende Test strenger ist als der entfernte: der entfernte haette diese Mutation nicht gefangen. Ist eine Mutation nachher gruen, wird nicht ausgeliefert.

### Nicht im Umfang

- Fachliche Umbenennung oder Zusammenlegung der 2795-Dateien (eigenes Thema, nicht Teil von #1196/#3263).
- Aenderung an Gate-Konfiguration: keine.
- Die Messprotokolle `docs/artifacts/perf-3209-pytest-laufzeit/collect-*.txt` nennen den entfallenden Testnamen, werden aber von nichts gelesen (historisches Protokoll) und bleiben.

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `tests/tdd/test_migration_2792_profil_ampel.py` | MODIFY | `test_ac23_neu_erkannte_...` samt Parametrisierung entfernen (ca. -10 LoC); Kommentar am bleibenden Test (ca. +2 LoC) |
| `docs/context/rework-3263-doppelte-tests-2795.md` | MODIFY | Mutationsprotokoll M1/M2 vorher/nachher, Begruendung je Paar fuer die unveraenderten 2795-Dateien |

Nicht geaendert (geprueft): die sechs `tests/test_2795_*.py`-Dateien, `scripts/migrate_2792_profil_ampel.py` und aller sonstige Produktionscode.

## Expected Behavior

- **Input:** Testbestand mit einer belegten Teilmengen-Dopplung in der 2792-Migrationstestdatei.
- **Output:** gleiche geprueften Zusicherungen, an einer Stelle; Testanzahl sinkt netto um 5 (die fuenf Faelle des entfallenden Tests); die sechs 2795-Dateien sind unveraendert; Kern-Schicht weiter 100 % gruen.
- **Side effects:** keine Auswirkung auf Produktverhalten oder Deploy-Inhalt.

## Test Plan

Es entsteht kein neuer Produktionscode. Der RED-Schritt ist der Mutationsnachweis "vorher", der Nachweis "nachher" der GREEN-Beleg. Keine Mock-Tests, keine Dateiinhalt-Checks als Verhaltensnachweis.

### Automated Tests (TDD RED)

- [ ] Test 1: GIVEN der Stand vor dem Umbau WHEN M1 angewendet wird THEN sind `test_ac23_neu_erkannte_...` und `test_ac23_nicht_zuordenbar_mit_begruendung_...` rot (Ausgangsprotokoll in der Kontext-Doku).
- [ ] Test 2: GIVEN der Stand nach dem Umbau WHEN M1 angewendet wird THEN ist `test_ac23_nicht_zuordenbar_mit_begruendung_...` rot und nach Wiederherstellung wieder gruen.
- [ ] Test 3: GIVEN M2 vorher und nachher WHEN die AC-23-Tests laufen THEN faengt nur der bleibende Test den Fall `wind_direction_deg`.
- [ ] Test 4: GIVEN `pytest --collect-only -q` auf `test_migration_2792_profil_ampel.py` vorher und nachher THEN fehlen genau die fuenf Faelle des entfernten Tests und es gibt keine Collect-Fehler.
- [ ] Test 5: GIVEN die berührten Testdateien (2792-Migration und die sechs 2795-Dateien) WHEN sie namentlich laufen THEN sind alle gruen (`uv run pytest` nie ohne benannte Dateien, #1477).

## Definition of Done

- [ ] Teilmengen-Test entfernt, bleibender Test unveraendert mit allen 7 Faellen und Kommentar (AC-1)
- [ ] M1 vorher beide rot, nachher der bleibende rot (AC-2)
- [ ] M2 Gegenprobe dokumentiert (AC-3)
- [ ] Sechs 2795-Dateien unveraendert, Begruendung je Paar in der Kontext-Doku (AC-4)
- [ ] Betroffene Dateien namentlich gruen, alle 6 CI-Checks gruen, Adversary-Verdict VERIFIED (AC-5)
- [ ] Diff nur unter tests/ und docs/, Produktionscode unveraendert (AC-6)
- [ ] Mutationsprotokoll in der Kontext-Doku, Skript nach Mutation wiederhergestellt (AC-7)

## Acceptance Criteria

- **AC-1:** Given der Test `test_ac23_neu_erkannte_nicht_zuordenbare_schluessel_stehen_im_bericht` ist echte Teilmenge des Tests `test_ac23_nicht_zuordenbar_mit_begruendung_und_bereich_bleibt_erhalten` / When der Umbau fertig ist / Then ist der Teilmengen-Test samt Parametrisierung entfernt, der bleibende Test unveraendert mit allen 7 Faellen (inklusive der fuenf neu erkannten Schluessel) vorhanden und mit einem Kommentar versehen, dass er die bei #2792 neu erkannten Schluessel mit abdeckt.
  - Test: `pytest --collect-only -q` auf die Datei zeigt die fuenf Faelle des entfernten Tests nicht mehr und alle 7 Faelle des bleibenden Tests; der bleibende Test laeuft gruen.

- **AC-2:** Given die Mutation M1 (Berichtstext "nicht zuordenbar" im Migrationsskript wird per String-Ersetzung veraendert) / When sie vor und nach dem Umbau angewendet wird / Then sind vorher beide AC-23-Tests rot und nachher der bleibende Test `test_ac23_nicht_zuordenbar_mit_begruendung_...` rot, und nach Wiederherstellung aus der externen Sicherung ist er wieder gruen.
  - Test: Mutationsprotokoll M1 (vorher, nachher, wiederhergestellt) in der Kontext-Doku.

- **AC-3:** Given die Gegenprobe M2 (Eintrag `wind_direction_deg` wird aus `_NICHT_ZUORDENBAR` entfernt) / When die AC-23-Tests vor dem Umbau laufen / Then bleibt der entfernte Test fuer diesen Schluessel gruen, waehrend der bleibende Test rot wird, und nach dem Umbau faengt der bleibende Test die Mutation weiterhin; damit ist belegt, dass der bleibende Test strenger ist und kein Schutz verloren geht.
  - Test: Mutationsprotokoll M2 in der Kontext-Doku, Wiederherstellung aus der Sicherung gruen.

- **AC-4:** Given die sechs Testdateien `test_2795_fixrunde1/2/3`, `test_2795_alert_metric_channels_ignoriert`, `test_2795_alte_regel_kanaele_ignoriert`, `test_2795_migration_alert_metric_channels` enthalten nur aehnliche, aber keine identischen oder echt enthaltenen Zusicherungen / When der Umbau fertig ist / Then sind diese Dateien unveraendert, und die Kontext-Doku nennt je aehnlichem Paar die Begruendung, warum es bleibt.
  - Test: `git diff --name-only origin/main` enthaelt keine dieser Dateien; Pruefung der Paar-Begruendungen in der Kontext-Doku im Review.

- **AC-5:** Given die berührten Testdateien (`tests/tdd/test_migration_2792_profil_ampel.py` und die sechs 2795-Dateien) / When sie namentlich ausgefuehrt werden (nie `uv run pytest` ohne Dateien) / Then sind alle gruen, die Kern-Schicht ist zu 100 % gruen und alle 6 CI-Checks des PR sind gruen.
  - Test: lokaler Lauf der benannten Dateien; CI-Lauf des PR mit allen 6 Checks gruen.

- **AC-6:** Given der Umbau betrifft nur Testsammlung und Dokumentation / When der Diff gegen `origin/main` geprueft wird / Then liegen alle geaenderten Dateien unter `tests/` oder `docs/`, Produktionscode (`src/`, `api/`, `internal/`, `scripts/`, `frontend/src/`, `cmd/`) ist unveraendert, und es gibt keine Aenderung an Gate-Konfiguration.
  - Test: `git diff --name-only origin/main` enthaelt keinen Pfad ausserhalb von `tests/` und `docs/`.

- **AC-7:** Given das Mutationsprotokoll fuer M1 und M2 / When der Umbau abgeschlossen ist / Then steht es vollstaendig (Mutation, vorher, nachher, wiederhergestellt gruen) in `docs/context/rework-3263-doppelte-tests-2795.md`, und `scripts/migrate_2792_profil_ampel.py` ist byte-identisch zur externen Sicherung wiederhergestellt (kein Diff gegen `origin/main`).
  - Test: Protokoll im Kontext-Dokument; `git diff origin/main -- scripts/migrate_2792_profil_ampel.py` ist leer.

## Known Limitations

- Die Ausbeute ist bewusst klein (ein Test). "Fast nichts doppelt" ist selbst ein Befund fuer #1196: die 2795-Dateien sind inhaltlich disjunkt.
- Die Methode erfasst nur Dopplung per Funktion, Eingabe und Erwartung; semantische Aehnlichkeit mit anderen Fixtures wird nicht zusammengelegt.
- Mutationen werden von Hand gesetzt; ein automatischer Mutationslauf ist nicht Teil dieser Scheibe.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Aufraeumen nach bestehender Test-Politik (ADR-0094) und der in #3207/#3208 verankerten Regel; keine neue Architekturentscheidung, kein neues Gate, keine Aenderung an wirksamer Gate-Konfiguration.

## Changelog

- 2026-11-23: Initial spec created
