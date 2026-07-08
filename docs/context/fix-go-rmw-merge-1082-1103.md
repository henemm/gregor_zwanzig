# Context: fix-go-rmw-merge-1082-1103 (#1082 + #1103)

## Aufgabe

Zwei vorbestehende Go-Datenverlust-Bugs derselben Klasse ("Blind-Replace statt
feldweisem Read-Modify-Write") beheben. Bündel aus Intake #991/#1082/#1103 →
hier nur die zwei Go-Bugs (#991 Python separat, Workflow B).

## Root Cause (recherchiert)

- **#1082** — `CreateLocationHandler` (`internal/handler/location.go:55-95`) leitet ID
  via `toKebab` ab und ruft `SaveLocation` (`internal/store/location.go:80-92`,
  `os.WriteFile` ohne Existenzcheck) → still überschriebene Location bei ID-Kollision.
- **#1103** — `UpdateTripHandler` (`internal/handler/trip.go:203-204`):
  `existing.ReportConfig = *req.ReportConfig` ersetzt die ganze Map statt Feld-Merge.
  Live-Beweis auf Staging 2026-07-08 (`enabled`/`send_email` verschwanden).

## Affected Files

- `internal/handler/location.go` — Existenzprüfung + 409 in `CreateLocationHandler`
- `internal/handler/trip.go` — Feld-Level-Merge für `report_config`
- `internal/store/location.go` — `LoadLocation` (Existenzprüfung, keine Änderung nötig)
- `internal/model/trip.go` — `ReportConfig map[string]interface{}` (Typ, keine Änderung)

## Design-Entscheidungen (Tech Lead)

- #1082: **409 Conflict** (POST = anlegen; sichtbar ablehnen statt still mergen; PUT existiert für Updates). User-scoped Prüfung → kein Cross-User-Leck.
- #1103: **Feld-Level-Merge** (nur vorhandene Keys überschreiben).

## Nicht im Scope

`aggregation`/`weather_config`/`display_config` (gleiche Blind-Replace-Mechanik,
aber kein Live-Bug) — ggf. Folge-Issue.

## Tests

Go-Handler-Tests gegen echten Store (Tempdir, keine Mocks), Muster:
`internal/handler/location_write_test.go`, `internal/handler/trip_write_test.go`.
