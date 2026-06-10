# Spec: On-demand Wetter-Fetch für Telegram-Abfragebefehle (Issue #697)

## Problem

Telegram-Befehle (`/heute`, `/morgen`, `/glance`, `/timeline_heute`, `/timeline_morgen`)
liefern "Kein Wetter-Snapshot verfügbar" wenn kein gecachter Snapshot existiert.
Das betrifft alle User ohne vorherigen Scheduler-Lauf.

## Lösung

**Kein Snapshot → on-demand Fetch**, statt Fehlermeldung.

### UX-Flow

1. User sendet `/heute`
2. Bot antwortet sofort mit `⏳ Wetter wird geladen...`
3. On-demand Fetch (heute + morgen Segmente)
4. `editMessageText` mit echten Wetterdaten

### Fetch-Logik (AC-5: Cache nutzen wenn frisch)

- Snapshot vorhanden **und** `target_date == heute` → direkt zeigen, kein Re-Fetch
- Snapshot fehlt **oder** `target_date != heute` → on-demand Fetch, dann zeigen

## Architektur

**Wo:** `trip_command_processor.py::_handle_query` — on-demand Fetch wenn `not timeline.available` oder Snapshot veraltet.

**Loading-Message:** `inbound_telegram_reader.py::_process_update` — bei Query-Befehlen zuerst `send("⏳ Wetter wird geladen...")`, dann `editMessageText` nach Prozessierung.

**Fetch-Implementierung:** `TripReportSchedulerService._convert_trip_to_segments(heute) + _convert_trip_to_segments(morgen)` kombiniert, dann `_fetch_weather` + `WeatherSnapshotService.save`.

## Acceptance Criteria

**AC-1:** Given ein User mit aktivem Trip aber ohne Wetter-Snapshot, When er `/heute` sendet, Then antwortet der Bot mit echten Wetterdaten (enthält `°C` oder `km/h` oder `mm`).

**AC-2:** Given ein User mit aktivem Trip aber ohne Wetter-Snapshot, When er `/morgen` sendet, Then antwortet der Bot mit echten Wetterdaten für morgen.

**AC-3:** Given ein User mit aktivem Trip aber ohne Wetter-Snapshot, When er `/glance` sendet, Then antwortet der Bot mit Wetterdaten für heute UND morgen.

**AC-4:** Given ein User sendet `/heute` ohne Snapshot, When der Bot antwortet, Then erscheint zunächst eine Zwischennachricht (enthält `⏳`) die danach durch echte Daten ersetzt wird.

**AC-5:** Given ein User hat bereits einen frischen Snapshot (target_date == heute), When er `/heute` sendet, Then werden die gecachten Daten direkt gezeigt (kein Re-Fetch, Antwort <1s).

**AC-6:** Given der E2E-Test löscht keinen Snapshot vorab, When alle 7 Befehle durch die Pipeline laufen, Then enthalten alle Antworten echte Wetterdaten (kein "Kein Wetter-Snapshot").

## Betroffene Dateien

| Datei | Änderung |
|-------|----------|
| `src/services/trip_command_processor.py` | `_handle_query`: on-demand Fetch wenn Snapshot fehlt/veraltet |
| `src/services/inbound_telegram_reader.py` | Query-Pfad: Loading-Message + editMessageText |
| `tests/tdd/_telegram_live_fixture.py` | `_ensure_weather_snapshot`-Vorseedung aus `ensure_test_user_with_active_trip` entfernen |
| `tests/tdd/test_issue_686_telegram_functional_live.py` | AC-3/AC-4: kein Snapshot vorab, echter no-snapshot→Fetch-Flow |

## LoC-Schätzung

~70 LOC netto

## Changelog

- 2026-06-10: Spec erstellt
