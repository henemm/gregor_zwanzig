# ADR-0031: Dateibasierte JSON-Persistenz unter `data/users/{user_id}/` (keine Datenbank)

- **Status:** Akzeptiert (rückwirkend dokumentiert 2026-07-22 — gelebte Praxis, Issue #1343)
- **Datum:** 2026-07-22
- **Bezug:** `internal/store/`, ADR-0003 (Mandantentrennung), ADR-0023 (briefings/-Persistenz), CLAUDE.md §Daten-Schema-Reworks

## Kontext

Kleines Multi-User-Produkt auf einem einzelnen VServer, Datenvolumen pro
Nutzer im Kilobyte-Bereich, kein konkurrierender Schreibzugriff über
Prozessgrenzen hinweg (Go-API ist der einzige Schreiber, Python liest).

## Entscheidung

Persistenz ist ein dateibasierter JSON-Store unter `data/users/{user_id}/`
(`user.json`, `trips/`, `briefings/` (kind=route|vergleich, ADR-0023), `gpx/`,
`locations.json`, `alert_state/`, Snapshot-/Throttle-Dateien). Der Go-Store
(`internal/store/`) ist die einzige Schreib-Autorität; Normalisierung beim
Load (`normalizeTrip`, `NormalizeComparePreset`). Es gibt keine Datenbank.

## Verworfene Alternativen

- **SQLite/Postgres** — Transaktions- und Query-Komfort, aber Migrations- und
  Betriebs-Overhead; bei den Datenmengen ohne messbaren Nutzen. Grep-barkeit
  und Backup per `tar` sind im Betrieb wertvoller.

## Konsequenzen

- **Positiv:** Trivialer Backup/Restore, menschenlesbar, pro-Nutzer isoliert
  (ADR-0003).
- **Negativ / Preis:** Kein Schema-Zwang — Schema-Disziplin muss die
  Anwendung leisten.
- **Folgepflichten:** Read-Modify-Write mit Merge, niemals Replace
  (BUG-DATALOSS-GR221/#102, CLAUDE.md §Daten-Schema-Reworks);
  Schema-Änderungen brauchen idempotente Migrations-Skripte als
  per-Host-Deploy-Schritt; nie-`null`-Invariante für Listen-Felder (#1244).
