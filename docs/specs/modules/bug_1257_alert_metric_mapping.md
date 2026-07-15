---
entity_id: bug_1257_alert_metric_mapping
type: bugfix
created: 2026-07-15
updated: 2026-07-15
status: draft
version: "1.0"
tags: [go, alerts, persistence, data-loss, migration]
workflow: fix-1257-alert-metric-mapping
---

<!-- Issue #1257 -->

# Bug #1257 — Alert-Metric-Mapping (Katalog-Vokabular ↔ AlertMetric-Vokabular)

## Approval

- [x] Approved (PO „Go", 2026-07-15 — inkl. wörtlich freigegebener Known Limitation: Fix stellt Regeln wieder her, schaltet KEINE neuen Alarme ein)

## Purpose

Alarm-Regeln (`trip.alert_rules`) werden bei jedem Speichern und Laden eines
Trips gelöscht, weil `ActiveAlertableMetricIDs()` Katalog-IDs (`gust`,
`precipitation`, `temperature`, `snowfall_limit`, `thunder`,
`freezing_level`) roh gegen das `AlertableMetrics`-Vokabular
(`wind_gust`, `precipitation_sum`, `temperature_min/max`, `snow_line`,
`thunder_level`) matcht — die Schnittmenge dieser beiden Vokabulare ist
leer, daher matcht nie eine Metrik und `SyncAlertRules()` liefert
konsequent `[]`. Der Fix führt eine Vorwärts-Abbildung Katalog-ID →
AlertMetric(s) ein (exakte Inverse der bereits existierenden Python-Bridge
`_ALERT_METRIC_TO_CATALOG_ID`), konsolidiert die zwei parallelen
Go-Persistenzpfade auf diese eine Abbildung und materialisiert die
dadurch entstehenden Default-Regeln einmalig rückwirkend in alle
Bestands-Trips.

## Source

- **File:** `internal/model/trip.go`
- **Identifier:** `func ActiveAlertableMetricIDs`, `func SyncAlertRules`, neue Map `catalogIDToAlertMetrics`

## Estimated Scope

- **LoC:** ~+130 / -20
- **Files:** 4 Code/Test + 1 Migrationsskript
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/model/trip.go: AlertableMetrics` | Go-Map | Alarm-Vokabular (Filter, welche AlertMetric überhaupt Regeln bekommen darf) |
| `internal/model/trip.go: DefaultDeltaThreshold` | Go-Map | Default-Schwellenwerte für neu materialisierte Delta-Regeln |
| `internal/model/trip.go: SyncAlertRules` | Go-Funktion | Konsument der neuen Abbildung — baut/erhält Regeln aus `activeMetricIDs` |
| `internal/store/trip.go: LoadTrip/SaveTrip` | Go-Store | Ruft `ActiveAlertableMetricIDs` + `SyncAlertRules` bei jedem Laden/Speichern auf |
| `internal/handler/weather_config.go: extractActiveMetricIDs` | Go-Handler | Zweiter, bisher divergenter Pfad mit demselben Mismatch — wird entfernt und durch `model.ActiveAlertableMetricIDs` ersetzt |
| `src/services/weather_change_detection.py: _ALERT_METRIC_TO_CATALOG_ID` | Python-Bridge | Bereits existierende Rückwärts-Abbildung AlertMetric → Katalog-IDs; die neue Go-Map ist ihre exakte Inverse und wird per Paritätstest gegen sie abgesichert |
| `src/app/metric_catalog.py` | Python-Katalog | Quelle der Katalog-IDs (`gust`, `precipitation`, `temperature`, `temperature_cold`, `snowfall_limit`, `thunder`, `freezing_level`) |
| `src/services/trip_alert.py: has_active_rules, _effective_alert_channels` | Python | Einzige Python-Konsumenten von `trip.alert_rules` (Enable-Gating + Kanalwahl) — NICHT der Delta-Detektor |

## Scope

### Affected Files
| File | Change Type | Description |
|------|-------------|--------------|
| `internal/model/trip.go` | MODIFY | Neue Map `catalogIDToAlertMetrics` (Katalog-ID → []AlertMetric, exakte Inverse von `_ALERT_METRIC_TO_CATALOG_ID`, gefiltert auf `AlertableMetrics`); `ActiveAlertableMetricIDs` übersetzt Katalog-IDs vor dem Alertable-Filter und dedupliziert das Ergebnis |
| `internal/handler/weather_config.go` | MODIFY | `extractActiveMetricIDs` (Zeilen ~145-170) entfernen, Aufrufstelle nutzt `model.ActiveAlertableMetricIDs` |
| `internal/model/*_test.go` (CREATE/MODIFY, z.B. `alert_sync_test.go` oder neue Datei) | CREATE/MODIFY | Golden-Mapping-Test (jede Katalog-ID → erwartete AlertMetric-Menge, inkl. `temperature`→{min,max} und `snowfall_limit`+`freezing_level`→einzige `snow_line`-Regel); Naht-Test mit ECHTEN Katalog-IDs durch `ActiveAlertableMetricIDs` statt Alarm-Vokabular |
| `tests/tdd/test_alert_metric_mapping_parity.py` | CREATE | Python-Paritätstest: berechnet die Inverse von `_ALERT_METRIC_TO_CATALOG_ID` und vergleicht sie wertebasiert gegen die in Go erwartete Zuordnung (kein Dateiinhalt-Grep, sondern Werte-/Strukturvergleich) |
| Migrationsskript (Pfad gemäß `operations_playbook.md`, z.B. `scripts/migrate_1257_alert_rules.sh` oder Go-Migrationsbinary) | CREATE | Einmaliger Batch-`SaveTrip`-Lauf über alle Bestands-Trips: Pre-Snapshot/Backup, danach für jeden Trip laden+speichern (löst den lazy Sync aus), idempotent bei erneutem Lauf |

### Estimated Changes
- Files: 5
- LoC: +130/-20

## Implementation Details

**1. Vorwärts-Abbildung (Kern des Fixes).** In `internal/model/trip.go` wird
eine Map `catalogIDToAlertMetrics map[string][]AlertMetric` ergänzt, definiert
als exakte Inverse der Python-Bridge `_ALERT_METRIC_TO_CATALOG_ID`
(`src/services/weather_change_detection.py:78-97`), aber nur für Katalog-IDs,
deren Ziel-AlertMetric(s) auch tatsächlich in `AlertableMetrics` enthalten sind:

- `gust` → `{AlertMetricWindGust}`
- `precipitation` → `{AlertMetricPrecipitationSum}`
- `thunder` → `{AlertMetricThunderLevel}`
- `temperature` → `{AlertMetricTemperatureMin, AlertMetricTemperatureMax}` (beide — `temperature_cold` ist im Katalog `selectable=False` und nie eigenständig im `display_config`, `temperature` ist der einzige User-Toggle für warm UND kalt)
- `snowfall_limit` → `{AlertMetricSnowLine}`
- `freezing_level` → `{AlertMetricSnowLine}` (dedupliziert zur gleichen Regel wie `snowfall_limit`, da Go kein eigenes `AlertMetricFreezingLevel` kennt)

**2. `ActiveAlertableMetricIDs` übersetzt vor dem Filter.** Bisher wird die
rohe Katalog-`metric_id` direkt gegen `AlertableMetrics` geprüft (Zeile 210,
matcht nie). Neu: pro aktiver Katalog-`metric_id` wird zuerst über
`catalogIDToAlertMetrics` in eine oder mehrere AlertMetric-IDs übersetzt,
diese werden gegen `AlertableMetrics` gefiltert (bleibt als Sicherheitsnetz
bestehen) und dedupliziert in die Ergebnisliste aufgenommen. Katalog-IDs
ohne Eintrag in `catalogIDToAlertMetrics` werden wie bisher ignoriert
(kein Fehler).

**3. Zwei Go-Pfade zusammenlegen.** `extractActiveMetricIDs`
(`internal/handler/weather_config.go:145-170`) implementiert dieselbe
(kaputte) Logik ein zweites Mal für den PUT-Handler. Sie wird entfernt;
der Handler ruft stattdessen `model.ActiveAlertableMetricIDs` auf. Damit
gibt es nur noch eine Stelle, die das Mapping kennt.

**4. Drift-Schutz.** Ein Go-Golden-Test in `internal/model` pinnt die
erwartete `catalogIDToAlertMetrics`-Zuordnung explizit (Tabelle
Katalog-ID → erwartete AlertMetric-Menge). Ein Python-Test
(`tests/tdd/test_alert_metric_mapping_parity.py`) berechnet die Inverse
von `_ALERT_METRIC_TO_CATALOG_ID` und vergleicht sie strukturell gegen
dieselbe erwartete Zuordnung. `_ALERT_METRIC_TO_CATALOG_ID` bleibt damit
die benannte Autorität — die Go-Map ist ihre geprüfte Inverse, kein
drittes, drift-anfälliges Vokabular.

**5. Rückwirkende Materialisierung.** `LoadTrip` synchronisiert bereits
in-memory, `SaveTrip` persistiert (`internal/store/trip.go:113-116,
139-141`) — nach dem Fix reicht technisch ein nächster Save pro Trip, um
die Regeln on-disk zu materialisieren. Da das PO-Ziel ein sofortiger,
verifizierbarer Zustand für alle 15 Bestands-Trips ist (0/15 → 15/15),
läuft beim Deploy zusätzlich ein einmaliger Batch-Migrationslauf: für
jeden Trip in `data/users/*/trips/*.json` wird `LoadTrip` + `SaveTrip`
ausgeführt. Pflicht dabei: vorheriges Backup (Persistenz-Änderung, siehe
`docs/reference/operations_playbook.md`), Idempotenz (ein zweiter Lauf
ändert nichts mehr an bereits materialisierten Regeln, da `SyncAlertRules`
existierende Regeln read-modify-write behandelt statt sie zu duplizieren),
Ausführung als `claude-gregor` pro Host (Staging + Prod getrennt).

## Expected Behavior

- **Input:** Ein Trip mit `display_config.metrics[]`, in dem eine oder
  mehrere Katalog-Metriken (`gust`, `precipitation`, `temperature`,
  `snowfall_limit`, `thunder`, `freezing_level`) `enabled: true` gesetzt
  haben.
- **Output:** Nach Laden+Speichern enthält `trip.alert_rules` für jede
  aktive, alarmfähige Katalog-Metrik genau eine `kind="delta"`-Regel mit
  Default-Schwelle (`DefaultDeltaThreshold`); bereits existierende
  Regeln bleiben unverändert erhalten (read-modify-write); Regeln für
  inaktive Metriken werden entfernt.
- **Side effects:** Einmaliger Migrationslauf schreibt alle Bestands-Trip-
  Dateien neu (mit vorherigem Backup). Der Live-Delta-Detektor
  (`DeviationAlertEngine`) ändert sein Verhalten NICHT — er liest
  `metric_alert_levels`/`display_config`, nie `trip.alert_rules`.

## Test Plan

Alle Tests laufen in der **Kern-Schicht** (deterministisch, ohne Netz/Live-Dienste). Kein Mock-Theater, keine Dateiinhalt-Greps als Verhaltensnachweis.

| # | Test | Schicht | Deckt AC | Art |
|---|------|---------|----------|-----|
| T1 | Trip mit `gust: enabled=true` + manuell angelegter Regel: speichern → neu laden → `alert_rules` enthält die Böen-Regel weiterhin (vor Fix rot: Regel weg) | Go (Store) | AC-1 | Bug-Repro (Round-Trip) |
| T2 | Trip mit allen sechs Katalog-Metriken (`gust`, `precipitation`, `thunder`, `temperature`, `snowfall_limit`, `freezing_level`) aktiv: speichern → jede Größe hat ≥1 passende Regel, keine geht verloren | Go (Store) | AC-2 | Verhalten |
| T3 | Trip mit ausschließlich `temperature` aktiv: speichern → genau zwei distincte Regeln (min UND max) | Go (Model) | AC-3 | Verhalten |
| T4 | Trip mit `snowfall_limit` UND `freezing_level` aktiv: speichern → exakt EINE schneefallgrenzen-bezogene Regel (Dedup) | Go (Model) | AC-4 | Verhalten |
| T5 | Denselben Metrik-Satz einmal via Store-`SaveTrip`, einmal via PUT-weather-config-Handler setzen → resultierende `alert_rules` identisch | Go (Handler+Store) | AC-5 | Pfad-Parität |
| T6 | Migrationsskript zweimal hintereinander gegen denselben Datenbestand: `alert_rules` nach Lauf 1 == nach Lauf 2 (Idempotenz); alle Trips mit aktiven alarmfähigen Metriken sind on-disk materialisiert | Go/Skript | AC-6 | Migration + Idempotenz |
| T7 | `test_alert_metric_mapping_parity.py`: Inverse von `_ALERT_METRIC_TO_CATALOG_ID` wertebasiert gegen die in Go erwartete Zuordnungstabelle — strukturelle Übereinstimmung für alle sechs Katalog-IDs | Python | AC-7 | Drift-Guard |

## Acceptance Criteria

- **AC-1:** Given ein Trip mit einer aktivierten Katalog-Metrik `gust` im `display_config` und einer manuell angelegten Alarm-Regel / When der Trip gespeichert und anschließend neu geladen wird / Then ist die Alarm-Regel weiterhin vorhanden (Round-Trip-Integrität) — vor dem Fix verschwindet sie, nach dem Fix bleibt sie erhalten.
  - Test: Trip mit `gust: enabled=true` speichern, neu laden, `alert_rules` ist nicht leer und enthält eine Regel für die Böen-Metrik.

- **AC-2:** Given ein Trip mit `display_config.metrics` für alle sechs betroffenen Katalog-Metriken (`gust`, `precipitation`, `thunder`, `temperature`, `snowfall_limit`, `freezing_level`) aktiviert / When der Trip gespeichert wird / Then enthält `trip.alert_rules` für jede dieser Metriken mindestens eine passende Alarm-Regel, keine geht verloren.
  - Test: Trip mit allen sechs aktivierten Metriken laden+speichern, Anzahl und Zuordnung der resultierenden Regeln prüfen.

- **AC-3:** Given ein Trip mit ausschließlich `temperature` als aktivierte Katalog-Metrik / When der Trip gespeichert wird / Then enthält `alert_rules` sowohl eine Regel für die minimale als auch für die maximale Temperatur (beide, nicht nur eine).
  - Test: Nur `temperature: enabled=true` setzen, speichern, prüfen dass zwei distincte Temperatur-Regeln (min UND max) entstehen.

- **AC-4:** Given ein Trip mit sowohl `snowfall_limit` als auch `freezing_level` aktiviert / When der Trip gespeichert wird / Then entsteht dafür genau EINE Alarm-Regel (keine Duplikate für dieselbe zugrundeliegende Größe).
  - Test: Beide Metriken aktivieren, speichern, Anzahl der Schneefallgrenzen-bezogenen Regeln muss exakt 1 sein.

- **AC-5:** Given ein Trip wird über den PUT-weather-config-Endpunkt geändert statt über den direkten Store-Save-Pfad / When dieselbe Katalog-Metrik-Kombination gesetzt wird / Then entstehen dieselben Alarm-Regeln wie beim direkten Speichern über den Store — beide Pfade verhalten sich identisch.
  - Test: Denselben Metrik-Satz einmal via Store-`SaveTrip` und einmal via PUT-Handler setzen, resultierende `alert_rules` vergleichen — identisch.

- **AC-6:** Given alle Bestands-Trips vor dem Fix haben ein leeres oder fehlendes `alert_rules`-Feld / When der Migrationslauf beim Deploy einmalig ausgeführt wird / Then haben danach alle Trips mit aktiven alarmfähigen Katalog-Metriken materialisierte Regeln on-disk, und ein zweiter Lauf der Migration ändert an diesem Zustand nichts mehr (Idempotenz).
  - Test: Migrationsskript zweimal hintereinander gegen denselben Datenbestand laufen lassen, `alert_rules`-Inhalt nach Lauf 1 und Lauf 2 vergleichen — identisch.

- **AC-7:** Given die Go-Abbildung Katalog-ID → AlertMetric(s) und die Python-Bridge `_ALERT_METRIC_TO_CATALOG_ID` / When ein Paritätstest die Inverse beider Richtungen vergleicht / Then stimmen sie für alle sechs betroffenen Katalog-IDs strukturell überein — kein Vokabular-Drift zwischen Go und Python.
  - Test: `tests/tdd/test_alert_metric_mapping_parity.py` berechnet die Inverse von `_ALERT_METRIC_TO_CATALOG_ID` und vergleicht sie wertebasiert gegen die in Go erwartete Zuordnungstabelle.

## Known Limitations

Dieser Fix stellt die Alarm-Regeln über Save/Load wieder her
(Round-Trip-Integrität) und behebt fälschliches Gate-Ausschließen von
Trips, deren einzige aktive Alarmquelle `alert_rules` ist. Er schaltet
KEINE neuen Alarme ein und ändert NICHT, welche Metrik mit welcher
Schwelle feuert — das eigentliche Alarm-Feuern läuft über den
`metric_alert_levels`-Pfad (#809/#817) und bleibt unangetastet.

Weitere Grenzen:
- Materialisierte Default-Regeln haben keine expliziten `Channels` —
  Kanalwahl fällt weiterhin auf den Legacy-Briefing-Kanal-Pfad zurück
  (unverändertes Bestandsverhalten von `_effective_alert_channels`).
- Der Delta-Detektor (`DeviationAlertEngine`) wird NICHT an `alert_rules`
  gehängt — das ist explizit außerhalb des Scopes dieses Fixes (PO-
  Entscheidung, Q3).
- Migrationsskript läuft manuell/deploy-gesteuert pro Host (Staging,
  Prod getrennt), kein automatischer Cron-Trigger.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Bugfix innerhalb bestehender Architektur (Go-Persistenzschicht, bereits etabliertes Cross-Lang-Wertekontrakt-Muster analog `trip.go:146-147`). Keine neue Systemgrenze, kein neuer Dienst, keine Technologieentscheidung — die Inverse-Map folgt einem im Code bereits vorhandenen Muster.

## Changelog

- 2026-07-15: Initial spec erstellt — Issue #1257
