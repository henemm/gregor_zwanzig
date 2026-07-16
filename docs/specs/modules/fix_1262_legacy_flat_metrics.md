---
entity_id: fix_1262_legacy_flat_metrics
type: module
created: 2026-07-16
updated: 2026-07-16
status: draft
version: "1.0"
tags: [bugfix, trip-loader, metrics, scheduler, observability, migration]
---

<!-- Issue #1262 — Legacy-Flach-String-Metrics brechen den Trip-Loader -->

# Legacy-Flach-String-Metrics brechen den Trip-Loader (Issue #1262)

## Approval

- [ ] Approved

## Purpose

Ein Trip, dessen `display_config.metrics` als Legacy-Flach-String-Liste
(`["temperature", "wind_speed"]`) statt als Liste von `MetricConfig`-Dicts
gespeichert ist, crasht beim Laden in `_parse_display_config`
(`AttributeError`/`TypeError`, weil ein `str` kein `.get()`/`["metric_id"]`
kennt). `load_all_trips` fängt diesen Fehler pro Trip nur mit `logger.error`
+ `continue` ab — der Trip verschwindet dadurch **komplett und still** aus
der geladenen Trip-Liste. Diese Liste speist sowohl den Briefing-Scheduler
als auch die Alarm-Engine: der Nutzer bekommt weder Briefings noch Alarme,
ohne dass irgendwo eine Fehlermeldung sichtbar wird. Dieser Fix schließt die
Lücke dreifach: Leseseite (Loader heilt Flach-Strings fail-soft), Beobacht-
barkeit (übersprungene Trips werden sichtbar statt nur geloggt) und Bestands-
daten (Migrationsskript für bereits betroffene Trip-Dateien).

## Source

- **File:** `src/app/loader.py` — `_parse_display_config`, :693-826 (Crash-Stelle, Kern-Fix)
- **File:** `src/app/loader.py` — `load_all_trips`, :1249-1295 (Swallow-Punkt: `logger.error` + `continue`)
- **File:** `src/services/trip_report_scheduler.py` — `_get_active_trips`/`send_reports*` (Observability-Anschlusspunkt)
- **File:** `scripts/migrate_1262_flat_metrics.py` (NEU) — Migration der Bestandsdaten unter `data/users/*/briefings/`

> **Schicht-Hinweis:** `src/app/loader.py`, `src/services/`, `scripts/` = Python-Core
> (`src/app/`, `src/services/`). Kein Frontend-Code, keine Go-API-Schreibpfade
> betroffen — der Fehler entsteht ausschließlich beim Lesen bestehender
> JSON-Dateien im Python-Core.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/app/loader.py::_normalize_legacy_mode` | Python-Funktion | Präzedenz für pro-Metrik-Legacy-Normalisierung (bereits etablierter Vor-Schleifen-Normalisierungs-Stil) |
| `src/app/loader.py::_migrate_weather_config` (:846-885) | Python-Funktion | Migriert `TripWeatherConfig.enabled_metrics` — genau dieselbe Flach-String-Form, die hier direkt in `display_config.metrics` auftauchen kann |
| `scripts/migrate_1244_null_lists.py` | Python-Skript | Vorbild-Muster für das neue Migrationsskript (Dry-Run-Default, `--execute`, `--root`, tar.gz-Backup, zweiphasig `_collect_plan`/`_apply`, Idempotenz) |
| `src/app/models.py::MetricConfig` (:496-521) | Python-Dataclass | Zielstruktur der Normalisierung — nur `metric_id` ist Pflichtfeld, alle anderen Felder haben Defaults |
| `src/services/trip_alert.py` (:204, :271) | Python-Modul | Liest denselben geladenen `trip.display_config` — downstream durch den Loader-Fix mitgeheilt, kein eigener Code-Eingriff nötig |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `src/app/loader.py` | MODIFY | Neuer Helper `_coerce_metric_entry(entry)` normalisiert einen Flach-String zu `{"metric_id": entry, "enabled": True}` vor jeder der drei Metrik-Verarbeitungsschleifen (`metrics`, `channel_layouts`, `channel_layouts_per_report`) in `_parse_display_config` |
| `src/services/trip_report_scheduler.py` | MODIFY | Erfasst pro Scheduler-Lauf die Anzahl beim Laden übersprungener/kaputter Trips und macht sie sichtbar (Status + einmalige deduplizierte MQ-Meldung) |
| `scripts/migrate_1262_flat_metrics.py` | CREATE | Bestandsdaten in `data/users/*/briefings/*.json` (nur `kind` ≠ `vergleich`): Flach-String-`display_config.metrics` → dict-Liste umschreiben |
| `tests/tdd/test_legacy_flat_metrics_load.py` | CREATE | Nutzersicht-Repro-Test: Flach-String-Trip fehlt vor Fix in `load_all_trips` (rot), ist nach Fix enthalten (grün); Roundtrip-Test für bestehenden dict-Pfad |
| `tests/tdd/test_migrate_1262_flat_metrics.py` | CREATE | Kern-Test für das Migrationsskript (Dry-Run, Idempotenz, Feld-Erhalt, Backup) |

### Estimated Changes

- Files: 5 (2 geändert, 3 neu)
- LoC: +150/-5

## Implementation Details

### 1. Loader-Selbstheilung (Kern-Fix)

`_parse_display_config` bekommt einen Helper, der auf jeden rohen
Metrik-Eintrag angewendet wird, bevor auf `.get()`/`["metric_id"]`
zugegriffen wird:

```python
def _coerce_metric_entry(entry):
    """Legacy-Flach-String -> minimales MetricConfig-Dict, dict bleibt
    unveraendert. Analog _migrate_weather_config (enabled_metrics)."""
    if isinstance(entry, str):
        return {"metric_id": entry, "enabled": True}
    return entry
```

Der Helper wird auf `raw_metrics` (:698, vor Zeile 707) sowie in den
`channel_layouts`- (:758) und `channel_layouts_per_report`-Schleifen (:790)
angewendet — an allen drei Stellen, die heute direkt `mc_data["metric_id"]`
lesen. Ein dict-Eintrag durchläuft den Helper unverändert (`entry`
zurückgegeben as-is), damit der bestehende, voll ausgeprägte Pfad
(`aggregations`, `bucket`/`order`, `alert_threshold`, …) bit-identisch
bleibt (Regressionsschutz, AC-3).

### 2. Beobachtbarkeit im Scheduler

`load_all_trips` bleibt der einzige Swallow-Punkt (:1293
`logger.error("Skipping corrupt trip %s: %s", ...)`). Der
Briefing-Scheduler zählt pro Lauf, wie viele Trips beim Laden übersprungen
wurden (Differenz zwischen vorhandenen Briefing-Dateien und geladener
Trip-Liste, bzw. ein von `load_all_trips` optional zurückgegebener
Skip-Zähler) und macht das Ergebnis auf zwei Wegen sichtbar:

- **Status:** die Anzahl kaputter/übersprungener Trips wird analog zum
  bestehenden `last_run`/Diagnostics-Muster (`data/diagnostics/*.jsonl`,
  das der Go-Aggregator `internal/scheduler/briefing_health.go` bereits
  cross-language für `/api/scheduler/status` liest) als Zähler abgelegt.
- **MQ:** genau **eine** deduplizierte Meldung (Priorität `high`) an
  Instanz `infra` pro kaputter Trip-Datei — Dedup-Schlüssel ist der
  Dateiname, damit nicht bei jedem stündlichen Tick erneut gepingt wird.

### 3. Migration der Bestandsdaten

`scripts/migrate_1262_flat_metrics.py`, strukturell identisch zu
`scripts/migrate_1244_null_lists.py`:

- Iteriert über `data/users/*/briefings/*.json`, überspringt Dateien mit
  `"kind": "vergleich"` (Compare-Presets kennen kein `metrics`-Feld in
  derselben Bedeutung)
- Zweiphasig: `_collect_plan(root)` findet Dateien mit Flach-String-Einträgen
  in `display_config.metrics`, `_apply(plan)` schreibt
- Dry-Run per Default, `--execute` zum tatsächlichen Schreiben, `--root`
  für alternativen Datenwurzelpfad (Tests)
- tar.gz-Pre-Snapshot nach `.backups/` vor jedem `--execute`-Lauf
- Read-Modify-Write (BUG-DATALOSS-GR221-Prinzip): nur String-Einträge in
  `display_config.metrics` werden zu `{"metric_id": s, "enabled": true}`
  umgeschrieben, alle anderen Keys — auch unbekannte — bleiben unverändert
- Idempotent: zweiter Lauf über bereits migrierte Dateien erzeugt einen
  leeren Plan und schreibt nichts (Exit 0, kein Fehler)

## Expected Behavior

- **Input:** Eine `briefings/<trip_id>.json`-Datei, deren
  `display_config.metrics` eine Liste roher Strings ist statt einer Liste
  von Objekten
- **Output:** `load_trip`/`load_all_trips` liefern ein valides `Trip`-Objekt
  mit `MetricConfig(metric_id=<string>, enabled=True)` je Eintrag, ohne
  Exception; der Trip erscheint in der Ergebnisliste von `load_all_trips`
  und ist damit für Briefing-Scheduler und Alarm-Engine wieder erreichbar
- **Side effects:** Scheduler-Lauf mit mindestens einem übersprungenen Trip
  erzeugt einen sichtbaren Zähler-Eintrag und genau eine deduplizierte
  MQ-Meldung an `infra`; Migrationsskript räumt Bestandsdateien beim
  `--execute`-Lauf physisch auf (Backup vorher)

## Acceptance Criteria

- **AC-1:** Given ein Trip-JSON, dessen `display_config.metrics` eine
  Flach-String-Liste ist (z.B. `["temperature", "wind_speed"]`) / When der
  Trip via `load_trip` geladen wird / Then wird er ohne Exception geladen
  und jeder String-Eintrag erscheint als `MetricConfig(metric_id=<string>,
  enabled=True)`
  - Test: `tests/tdd/test_legacy_flat_metrics_load.py` erzeugt eine
    Trip-Datei mit Flach-String-`metrics`, ruft `load_trip()` auf und prüft
    die resultierende `MetricConfig`-Liste auf `metric_id`/`enabled`.

- **AC-2:** Given ein Nutzer, dessen einziger aktiver Trip eine
  Flach-String-`metrics`-Config hat / When `load_all_trips` für den
  Briefing-Scheduler bzw. die Alarm-Engine läuft / Then wird der Trip NICHT
  übersprungen und ist in der Ergebnisliste enthalten (vor Fix: Trip fehlt
  in der Liste, 0 Briefings/Alarme zugestellt)
  - Test: `tests/tdd/test_legacy_flat_metrics_load.py` legt genau einen
    Trip mit Flach-String-`metrics` in einem temporären `briefings/`-Ordner
    an, ruft `load_all_trips()` auf und prüft `len(result) == 1` (vor dem
    Fix rot: `len(result) == 0`, weil der Trip beim Laden crasht und der
    `except Exception`-Block ihn verwirft).

- **AC-3:** Given ein Trip mit korrekt strukturierter dict-`metrics`-Config
  / When er geladen und wieder serialisiert wird (`_parse_display_config` →
  `_trip_to_dict`) / Then bleibt die `metrics`-Config semantisch
  bit-identisch — der bestehende dict-Pfad wird durch die Normalisierung
  NICHT verändert
  - Test: `tests/tdd/test_legacy_flat_metrics_load.py` lädt einen Trip mit
    voll ausgeprägten `MetricConfig`-Dicts (inkl. `bucket`, `order`,
    `alert_threshold`, `aggregations`), serialisiert ihn erneut und
    vergleicht beide `metrics`-Listen feldweise auf Gleichheit.

- **AC-4:** Given ein geplanter Scheduler-Lauf, bei dem mindestens ein Trip
  beim Laden als kaputt übersprungen wird / When der Lauf abschließt / Then
  ist die Anzahl übersprungener/kaputter Trips über den bestehenden
  Status-Mechanismus sichtbar, UND es wird genau EINE deduplizierte
  MQ-Meldung (Priorität `high`) an Instanz `infra` gesendet — dedupliziert
  pro kaputter Trip-Datei, kein Ping bei jedem Tick
  - Test: `tests/tdd/test_scheduler_corrupt_trip_observability.py` legt
    eine strukturell defekte Trip-Datei an (z.B. fehlendes Pflichtfeld
    `id`), ruft den Scheduler-Beobachtbarkeits-Pfad zweimal hintereinander
    auf und prüft: Zähler > 0 nach Lauf 1, und der MQ-Versand-Aufruf
    (gestubbt über das Skript-Interface, nicht mit `Mock()` auf
    Geschäftslogik) erfolgt beim zweiten Lauf für dieselbe Datei NICHT
    erneut.

- **AC-5:** Given Bestandsdateien in `briefings/*.json` (nur `kind` ≠
  `vergleich`) mit Flach-String-`display_config.metrics` / When
  `scripts/migrate_1262_flat_metrics.py --root <dir> --execute` läuft /
  Then werden die String-Einträge zu dict-Form (`{"metric_id": s,
  "enabled": true}`) umgeschrieben (Read-Modify-Write, tar.gz-Backup VOR
  dem Schreiben); ohne `--execute` ist es ein Dry-Run ohne Dateiänderung;
  ein zweiter Lauf ist idempotent (Exit 0, keine Änderung)
  - Test: `tests/tdd/test_migrate_1262_flat_metrics.py` führt
    `_collect_plan`/`_apply` gegen ein temporäres Verzeichnis mit einer
    Flach-String-Datei und einer bereits korrekten Datei aus, prüft
    Dry-Run-Unveränderlichkeit, `--execute`-Umschreibung, Backup-Existenz
    und einen leeren Plan beim zweiten Lauf.

## Known Limitations

- Die Loader-Selbstheilung repariert NICHT die on-disk-Datei — sie bleibt
  Flach-String, bis sie via Save neu geschrieben ODER das Migrationsskript
  ausgeführt wird (AC-5 deckt das ab).
- Observability (AC-4) macht künftige *andere* Lade-Crashes sichtbar,
  verhindert sie aber nicht.
- Es gibt aktuell KEINE aktiven Produktiv-User; die Migration ist Hygiene,
  kein Notfall.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** — (kein neuer ADR; folgt Fail-soft-Loader-Muster #1244)
- **Rationale:** Bugfix innerhalb eines bereits etablierten, dokumentierten
  Musters (Vor-Schleifen-Normalisierung analog `_normalize_legacy_mode`,
  Fail-soft-Loader + Migrationsskript-Vorbild aus Issue #1244). Keine neue
  Architektur-Entscheidung, keine neue Abhängigkeit, keine strukturelle
  Weichenstellung.

## Changelog

- 2026-07-16: Initial spec created — Issue #1262
