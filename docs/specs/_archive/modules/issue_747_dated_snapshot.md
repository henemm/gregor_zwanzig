---
entity_id: issue_747_dated_snapshot
type: module
created: 2026-06-11
updated: 2026-06-11
implemented: 2026-06-11
status: implemented
version: "1.0"
tags: [snapshot, vortag-vergleich, weather]
---

# Datierter Forecast-Snapshot-Speicher (Issue #747)

## Approval

- [x] Approved (2026-06-11)

## Purpose

Erweitert den bestehenden `WeatherSnapshotService` um datiertes Speichern und Laden von Wetter-Snapshots. Ermöglicht den Abruf der gestrigen Vorhersage für den Vortag-Vergleich im Trip-Briefing (Story: Vergleich zum Vortag).

## Source

- **File:** `src/services/weather_snapshot.py`
- **Identifier:** `WeatherSnapshotService`
- **Scheduler:** `src/services/trip_report_scheduler.py`

## Estimated Scope

- **LoC:** ~50
- **Files:** 2
- **Effort:** low

## Dependencies

- `src/services/weather_snapshot.py` — bestehende Klasse wird erweitert
- `src/services/trip_report_scheduler.py` — ruft `save_dated` nach bestehendem `save` auf
- `app/loader.get_snapshots_dir` — bestehender Pfad-Helper

## Affected Files

| File | Change |
|------|--------|
| `src/services/weather_snapshot.py` | +`save_dated()`, +`load_dated()`, +`_prune_dated_snapshots()` |
| `src/services/trip_report_scheduler.py` | `save_dated` nach bestehendem `save` aufrufen |

## Behaviour

### Datei-Benennung

- Bestehend (Alert-Nutzung, unverändert): `data/users/<user_id>/snapshots/{trip_id}.json`
- Neu (datiert): `data/users/<user_id>/snapshots/{trip_id}_{YYYY-MM-DD}.json`

### save_dated(trip_id, target_date, segments)

Schreibt zusätzlich zum bestehenden `save()` eine datierte Kopie. Dateiformat identisch mit der bestehenden JSON-Struktur. Wird aus `trip_report_scheduler.py` nach dem bestehenden `save`-Aufruf aufgerufen.

### load_dated(trip_id, target_date) → Optional[List[SegmentWeatherData]]

Lädt die datierte Snapshot-Datei für den angegebenen Tag. Gibt `None` zurück wenn keine Datei vorhanden (kein Absturz, stille Rückgabe).

### Retention

Nach jedem `save_dated`-Aufruf werden datierte Snapshots für diesen Trip bereinigt: maximal 7 Dateien behalten (nach `mtime` sortiert, älteste zuerst löschen). Fehler beim Löschen werden geloggt, aber nicht geworfen.

## Acceptance Criteria

**AC-1:** Given ein Trip-Briefing wird heute versendet / When `save_dated(trip_id, date.today(), segments)` aufgerufen wird / Then existiert `{trip_id}_{YYYY-MM-DD}.json` im Snapshots-Verzeichnis des Nutzers mit dem korrekten Datum im Dateinamen.

**AC-2:** Given eine datierte Snapshot-Datei für gestern existiert / When `load_dated(trip_id, date.today() - timedelta(1))` aufgerufen wird / Then werden die `SegmentWeatherData` korrekt deserialisiert zurückgegeben (gleiche Werte wie beim Speichern).

**AC-3:** Given noch keine datierte Snapshot-Datei existiert (erster Tag) / When `load_dated(trip_id, yesterday)` aufgerufen wird / Then gibt die Methode `None` zurück ohne Exception.

**AC-4:** Given mehr als 7 datierte Snapshot-Dateien für einen Trip existieren / When ein neuer `save_dated`-Aufruf erfolgt / Then werden die ältesten Dateien gelöscht sodass maximal 7 übrig bleiben.

**AC-5:** Given der bestehende Alert-Pfad nutzt `save()` und `load()` / When `save_dated` hinzugefügt wird / Then bleiben `save()` und `load()` byte-identisch — keine Verhaltensänderung für Alert-Nutzung.

## Changelog

- 2026-06-11: Implemented — `save_dated()`, `load_dated()`, `_prune_dated_snapshots()` auf WeatherSnapshotService, Scheduler ruft save_dated() auf, Retention max. 7 dated Files pro Trip. Spec v1.0 approved. Issue #747.
