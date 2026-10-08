---
entity_id: fix_1981_alarm_abwahl_alt_vokabular
type: module
created: 2026-10-08
updated: 2026-10-08
status: draft
version: "1.0"
tags: [alarm, ortsvergleich, bug, metric_alert_levels, vokabular]
---

<!-- Issue #1981. Grundlage: docs/context/fix-1981-alarm-abwahl-vokabular.md
     (Ursache, Uebersetzungstabelle, Affected Files, Open Question). -->

# Alarm-Abwahl wirkt auch bei Alt-Vokabular in `metric_alert_levels` (#1981)

## Approval

- [ ] Approved

## Purpose

Im Ortsvergleich wirkt eine im Alarme-Reiter auf `off` gestellte Metrik nicht, wenn
ihre Stufe in `metric_alert_levels` unter einem Alt-Schlüssel im Summary-Vokabular
(`temp_max_c` statt `temperature_max`) gespeichert ist: Die Auswertung verwirft den
unbekannten Schlüssel, der Alarm feuert trotz Abwahl. Diese Spec führt einen geteilten
Normalisierer ein (Python und Go, Trip und Vergleich), der Alt-Schlüssel beim Laden in
das Alarm-Vokabular übersetzt, sodass die gespeicherte Stufe gilt und Editor-Anzeige
und Wirkung dasselbe zeigen. Mit diesem Fix wird auch Nebenbefund B2-33 aus #1199
geschlossen.

## Source

> **Schicht-Hinweis:** Python-Core UND Go-API. Python liest Vergleiche direkt von Platte
> (`compare_preset_access.py` → `load_compare_presets`), nicht über Go; deshalb braucht
> es beide Normalisierer. Kein Frontend-Anteil (das Frontend schreibt heute nur
> Alarm-Namen und liest über Go).

- **File:** `src/app/loader.py`
  - **Identifier:** neuer gemeinsamer Normalisierer für `metric_alert_levels`;
    Aufruf im Trip-Ladepfad (bestehende snow_line-Migration, ca. `:764`, `:1057`) und
    im Vergleichs-Ladepfad (`load_compare_presets`, ca. `:309`).
- **File:** `internal/store/trip.go`
  - **Identifier:** `migrateMetricAlertLevels` (ca. `:331`) — um dieselbe Tabelle erweitern.
- **File:** `internal/store/compare_preset.go`
  - **Identifier:** `normalizeLoadedComparePreset` (ca. `:88-114`), Aufruf neben
    `migrateComparePresetSlots`.
- **Wirkort (unverändert, nur Prüfort):** `src/services/compare_alert.py`
  `_build_eval_config` (`:680-720`) und `src/services/alert_preset.py`
  `expand_per_metric_levels`.

## Estimated Scope

- **LoC:** ca. +120/−20 produktiv, ca. +200 Testcode
- **Files:** 4 produktiv (optional 5: `src/services/alert_preset.py`, nur falls ohne Risiko
  auf den geteilten Baustein umstellbar) + 2 Testdateien
- **Effort:** medium (zentrale Alarm-Auswertung, aber Wirkung eng auf Alt-Schlüssel begrenzt)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `alert_metric_for`, `summary_field_for` (`src/app/metric_catalog.py:968,982`) | Funktion | Quelle der Übersetzung; Gegenstand des Paritätstests |
| `AlertMetric`-Enum, `_PRESET_TABLE` (`src/services/alert_preset.py`) | Register | Gültiges Ziel-Vokabular |
| `expand_per_metric_levels` (`src/services/alert_preset.py:178`) | Funktion | Verwirft heute unbekannte Schlüssel (`ValueError`); Wirkort |
| `_build_eval_config` (`src/services/compare_alert.py:680-720`) | Funktion | Einziger Python-Leser im Vergleichspfad; `or _STANDARD_METRIC_LEVELS` bleibt unverändert |
| `issue_1971_legacy_preset_alarm_fallback` | Spec | Known Limitation zu #1981 entfällt mit diesem Fix; AC-4/AC-6 dort (CAPE bleibt) bleiben gültig |
| #959 (snow_line → freezing_level) | Muster | Vorbild: Neu-Schlüssel gewinnt, Alt wird entfernt |

## Implementation Details

**Übersetzungstabelle (fest, in Python und Go deckungsgleich):**

| Alt-Schlüssel (Summary) | Neu-Schlüssel (Alarm-Name) |
|---|---|
| temp_max_c | temperature_max |
| temp_min_c | temperature_min |
| gust_max_kmh | wind_gust |
| precip_sum_mm | precipitation_sum |
| visibility_min_m | visibility |
| cape_max_jkg | cape |
| thunder_level_max | thunder_level |
| wind_max_kmh | wind_change |
| snow_line (bestehend) | freezing_level |
| wind_chill_min_c | — wird verworfen (keine Alarm-Identität) |

Die Tabelle hat 8 Summary-Einträge plus den bestehenden snow_line-Eintrag; `wind_chill_min_c`
wird ersatzlos entfernt. Nicht verwenden: die Umkehr von `_ALERT_METRIC_TO_SUMMARY_FIELD`
(mehrdeutig).

**Regeln des Normalisierers:**

1. Neu-Schlüssel gewinnt bei Doppelbelegung (Vorbild #959).
2. Der Alt-Schlüssel wird entfernt.
3. Alle anderen Schlüssel bleiben unverändert (Merge, kein Neuaufbau, #102).
4. Zweiter Lauf ist ein No-Op (idempotent).
5. Python normalisiert im Lade-Pfad nur im Speicher (Python schreibt Vergleichsdateien nur per
   eigenem Read-Modify-Write und liest dort die Datei neu); die Platte heilt über Go beim
   nächsten Speichern im Editor. Kein Python-Rückschreiben.
6. `or _STANDARD_METRIC_LEVELS` in `_build_eval_config` bleibt unverändert: Wird die Map nach
   Normalisierung leer (nur `wind_chill_min_c`), gilt der volle Standard-Satz wie heute.

**PO-Entscheid (Variante A):** Bei einem Alt-Eintrag gilt die damals gespeicherte Stufe.
Heute zeigt der Editor „Standard", gespeichert ist z. B. „off", ausgewertet wird „Standard".
Nach dem Fix zeigen Editor und Auswertung beide den gespeicherten Wert; das Ticket
verlangt genau das („Abwahl wirkt nicht").

**Zwei-Nutzer-Isolation:** Kein neuer Endpoint und kein neuer Datenpfad. Der Normalisierer
arbeitet auf dem bereits nutzerbezogen geladenen Objekt und kennt keine `user_id`; die
bestehende Isolation (`WithUser` / `user_id`-Parameter) bleibt unberührt.

## Expected Behavior

- **Input:** Ein Trip oder Ortsvergleich, dessen `metric_alert_levels` Alt-Schlüssel enthält.
- **Output:** Nach dem Laden stehen die Stufen unter den Alarm-Namen; die Auswertung
  erzeugt für `off` keine Regel mehr, der Editor zeigt denselben Wert.
- **Side effects:** Alarme, die heute trotz gespeichertem „off" feuern, verstummen.
  Go-Datei auf Platte wird erst beim nächsten Speichern im Editor bereinigt.

## Acceptance Criteria

- **AC-1:** Given ein Ortsvergleich, dessen `metric_alert_levels` `temp_max_c: "off"` enthält
  (Alt-Vokabular) / When der Vergleich geladen und die Alarm-Regelbildung
  (`_build_eval_config` → `expand_per_metric_levels`) ausgeführt wird / Then entsteht keine
  Regel für `temperature_max` und das Temperatur-Maximum löst keinen Alarm mehr aus.
  - Test: `tests/tdd/test_alarm_abwahl_alt_vokabular.py` — echte Kette ab Laden der
    Preset-Datei bis zur Regelmenge; vorher rot (Regel vorhanden), nachher grün.

- **AC-2:** Given ein Alt-Eintrag mit gespeicherter Stufe (z. B. `gust_max_kmh: "off"`) / When
  der Vergleich geladen wird (Python-Loader und Go-Ladepfad) / Then gilt die gespeicherte
  Stufe unter dem Alarm-Namen (`wind_gust: "off"`), und der Editor zeigt denselben Wert wie
  die Auswertung — Anzeige und Wirkung stimmen überein (PO-Entscheid Variante A).
  - Test: `tests/tdd/test_alarm_abwahl_alt_vokabular.py` (Python-Seite) und
    `internal/store/compare_preset_test.go` (Go-Ladepfad liefert den Neu-Schlüssel mit dem
    gespeicherten Wert).

- **AC-3:** Given ein Ortsvergleich mit Alt-Schlüssel UND Neu-Schlüssel für dieselbe Metrik
  (z. B. `temp_max_c: "off"` und `temperature_max: "standard"`) / When geladen wird / Then
  gewinnt der Neu-Schlüssel (`standard`), und der Alt-Schlüssel ist entfernt.
  - Test: `tests/tdd/test_alarm_abwahl_alt_vokabular.py::` Vorrang-Test und
    `internal/store/compare_preset_test.go` (Go).

- **AC-4:** Given `metric_alert_levels` mit Alt-Schlüsseln und fremden Schlüsseln (z. B.
  `thunder_level: "off"`, ein unbekannter Zusatzschlüssel) / When der Normalisierer läuft / Then
  bleiben alle nicht übersetzten Schlüssel mit Wert unverändert erhalten (Merge statt Neuaufbau).
  - Test: Python- und Go-Test vergleichen die Schlüsselmenge vor und nach dem Lauf.

- **AC-5:** Given bereits normalisierte `metric_alert_levels` / When der Normalisierer ein
  zweites Mal läuft / Then ist das Ergebnis identisch zum ersten Lauf (No-Op).
  - Test: Python und Go, je `normalize(normalize(x)) == normalize(x)`.

- **AC-6:** Given ein Ortsvergleich, dessen `metric_alert_levels` ausschließlich
  `wind_chill_min_c: "off"` enthält / When geladen und die Alarm-Regelbildung ausgeführt wird /
  Then ist der Schlüssel verworfen, die Map leer, und es gilt der volle Standard-Satz — exakt
  wie vor dem Fix (Grenzfall `or _STANDARD_METRIC_LEVELS`).
  - Test: `tests/tdd/test_alarm_abwahl_alt_vokabular.py` zählt die Regeln gegen die
    Regelmenge eines Presets ohne `metric_alert_levels`.

- **AC-7:** Given ein Trip mit `snow_line` und einem Summary-Alt-Schlüssel in
  `metric_alert_levels` / When der Trip geladen wird (Python und Go) / Then wird `snow_line`
  weiterhin zu `freezing_level` und der Summary-Schlüssel gemäß Tabelle übersetzt; ein Trip
  ohne Alt-Schlüssel bleibt byte-gleich.
  - Test: Python-Test für den Trip-Ladepfad und Go-Test in `internal/store/` (Trip).

- **AC-8:** Given die Übersetzungstabelle / When sie gegen `alert_metric_for` und
  `summary_field_for` (`metric_catalog.py`) geprüft wird / Then liefert jeder Tabelleneintrag
  denselben Neu-Schlüssel, den der Katalog für das Paar (metric_id, Aggregation) ergibt, und
  unter den Alt-Schlüsseln der Tabelle ist `wind_chill_min_c` der einzige ohne Alarm-Identität (wird verworfen).
  - Test: `tests/tdd/test_alarm_abwahl_alt_vokabular.py` (Paritätstest Tabelle ↔ Katalog).

- **AC-9:** Given die Go-Tabelle und die Python-Tabelle / When beide auf dieselbe Eingabe
  angewendet werden / Then ist die Ausgabe gleich für alle Einträge (Go ↔ Python-Parität).
  - Test: Go-Test liest die Tabelle und prüft sie gegen eine gemeinsame, versionierte Fixture
    (Eingabe/Erwartung); derselbe Fixture-Satz wird im Python-Test geprüft.

- **AC-10:** Given ein Ortsvergleich mit Alt-Schlüssel `cape_max_jkg: "off"` / When die Alarm-
  Regelbildung am Wirkort (`_build_eval_config`) ausgeführt wird / Then fehlt die `cape`-Regel,
  während Alt-Vergleiche ohne `metric_alert_levels` die CAPE-Regel weiterhin behalten (#1971
  AC-4/AC-6 bleiben unverändert grün).
  - Test: `tests/tdd/test_alarm_abwahl_alt_vokabular.py` plus bestehende
    `test_compare_alert_missing_active_metrics_with_levels.py` unverändert.

## Test Plan

| Datei | Schicht | Deckt ab |
|---|---|---|
| `tests/tdd/test_alarm_abwahl_alt_vokabular.py` | Kern (deterministisch, Fixtures auf Platte, kein Netz) | AC-1, AC-2 (Python), AC-3–AC-6, AC-7 (Python), AC-8, AC-9 (Python), AC-10 |
| `internal/store/compare_preset_test.go` | Kern (Go) | AC-2 (Go), AC-3–AC-5, AC-9 (Go) |
| Trip-Test in `internal/store/` (z. B. `trip_metric_alert_levels_test.go`) | Kern (Go) | AC-7 (Go) |
| `tests/tdd/test_compare_alert_missing_active_metrics_with_levels.py` (Bestand, unverändert) | Kern | AC-10 (#1971-Schutz) |

Bug-Nachweis: AC-1 ist vor dem Fix rot (Regel für `temperature_max` entsteht trotz `temp_max_c: "off"`)
und nach dem Fix grün — geprüft am Wirkort `_build_eval_config`, nicht am Normalisierer allein.

## Known Limitations

- **Datenbestand unbekannt:** `/var/lib/gregor/users` ist für `hem` nicht lesbar; die Zahl
  betroffener Vergleiche ist nicht gemessen. Bekannt ist `cp-eb6ba0b239d90e37` („Le Var",
  Nutzer henning), dort ändert sich praktisch nichts, weil `active_metrics` dieselben Metriken
  ohnehin abschaltet.
- **Trip-Daten vermutlich frei von Alt-Schlüsseln** (ungemessen); der Normalisierer ist dort
  ein No-Op.
- **Datei auf Platte** wird durch Go erst beim nächsten Speichern im Editor bereinigt;
  Python-Auswertung wirkt sofort über die Lade-Normalisierung.
- Die Known Limitation „Vokabular-Mischung" in `issue_1971_legacy_preset_alarm_fallback.md`
  entfällt mit diesem Fix von selbst.

## Out of Scope

- **Kein Migrationsskript** (Datenbestand für `hem` unlesbar, Selbstheilung über
  Lade-Normalisierung genügt).
- **Kein Mail-Inhalt betroffen:** `email_spec_validator.py` / `briefing_mail_validator.py`
  nicht im Umfang.
- **Nebenbefund B1-04 (CAPE im Rückfall `_STANDARD_METRIC_LEVELS`):** durch #1971 entschieden
  (dortige AC-4 und AC-6 verlangen, dass die CAPE-Regel erhalten bleibt) — kein
  Änderungsbedarf. **B2-33 ist dieser Bug** und wird hier behoben.
- `_SUMMARY_KEY_TO_CATALOG_ID` (`compare_alert.py:63-74`) bedient ein anderes Vokabular
  (Katalog-ID) und bleibt unangetastet.
- Keine Änderung am Frontend; ggf. Prüfung, ob die Test-Fixture
  `wertebereicheVergleichPruefstand.ts:56` (nutzt `wind_max_kmh` als Testdatum) angepasst
  werden muss, erfolgt in der Implementierung.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Datenbereinigung beim Laden im Bestands-Vokabular, nach dem Muster von #959.
  Kein neuer Kanal, Provider, Datenmodell-Entscheid, keine Auth- oder Editor-Änderung.

## Changelog

- 2026-10-08: Initial spec created
