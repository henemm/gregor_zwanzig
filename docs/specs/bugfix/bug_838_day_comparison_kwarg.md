# Bug #838 — Regression: day_comparison-Kwarg in format_email entfernt

## Problem

Commit `945a824c` entfernte den Parameter `day_comparison` aus `TripReportFormatter.format_email()`,
aktualisierte aber `trip_report_scheduler.py` nicht. Jeder Briefing-Versand schlägt seitdem mit
`TypeError: TripReportFormatter.format_email() got an unexpected keyword argument 'day_comparison'`
fehl.

## Ursache

- `src/formatters/trip_report.py` — `format_email()` hat keinen `day_comparison`-Parameter mehr
- `src/services/trip_report_scheduler.py:556` — übergibt `day_comparison=day_comparison`
- `src/services/trip_report_scheduler.py:523-537` — berechnet `day_comparison`, das nirgends mehr verwendet wird (toter Code)

## Acceptance Criteria

**AC-1:** Given ein aktiver Trip mit gültigen Etappen, When der Scheduler `_send_trip_report()` aufruft, Then gibt es keinen `TypeError` für `day_comparison` und die Methode schließt ohne Exception ab.

**AC-2:** Given `trip_report_scheduler.py`, When der Code analysiert wird, Then existiert kein Aufruf von `format_email()` mit dem Keyword-Argument `day_comparison` und kein toter Berechnungsblock für `day_comparison`.

**AC-3:** Given ein Test-Briefing-Aufruf via `POST /api/scheduler/trips/{trip_id}/send`, When der Endpunkt aufgerufen wird, Then antwortet er mit HTTP 200 (nicht 422/500).

## Fix

Aus `src/services/trip_report_scheduler.py` entfernen:
1. Den toten Berechnungsblock (Zeilen 523–537: `day_comparison`-Berechnung)
2. Den Kwarg `day_comparison=day_comparison` im `format_email()`-Aufruf (Zeile 556)

## Aufwand: Small (1 Datei, ~16 Zeilen)
