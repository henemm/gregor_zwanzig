# Context: Issue #396 — Archiv-Statistiken (Briefings + Alarme zählen)

## Request Summary

Archiv-Screen zeigt `—` für "Briefings gesendet" und "Alarme ausgelöst" pro Tour.
Ziel: echte Zähler aus vorhandenen Logs. Kein Accuracy-%, keine Schlagzeilen.

## Was #393 bereits gebaut hat

| Was | Datei | Retention |
|-----|-------|-----------|
| Briefing-Log | `data/users/{uid}/briefing_log.json` | **unbegrenzt** (kein Cleanup) |
| Alert-Log | `data/users/{uid}/alert_log.json` | **48h** — Python bereinigt beim Schreiben |
| Go-Leser | `internal/store/store.go` — `LoadBriefingLog()` / `LoadAlertLog()` | — |
| Cockpit-Endpoint | `GET /api/cockpit/status` | filtert heute / letzte 24h |

## Kritische Erkenntnis

`briefing_log.json` → sofort nutzbar (kein Python-Change nötig).
`alert_log.json` → 48h-Bereinigung **entfernen**: Go filtert schon clientseitig für Cockpit auf 24h.
Log wächst danach dauerhaft — korrekt für Archiv.

## Multi-User

`data/users/{uid}/` ist bereits user-scoped. Go-Store arbeitet per UserStore. Kein Änderungsbedarf.

## Frontend-Status (archiv/+page.svelte)

- `alertCount(trip)` zählt `alert_rules.length` (falsch — konfigurierte Regeln, nicht Auslösungen)
- Stats-Strip: alle drei Felder `—` (expliziter TODO-Kommentar)
- `{@render accuracyBar()}` — Platzhalter, bleibt `—`

## Betroffene Dateien

| Datei | Änderung |
|-------|----------|
| `src/services/trip_alert.py` | 48h-Bereinigung entfernen (~3 Zeilen) |
| `internal/store/store.go` | `BriefingCountByTrip()` + `AlertCountByTrip()` |
| `internal/handler/` oder `cmd/server/main.go` | Neuer Endpoint `GET /api/archive/stats` |
| `frontend/src/routes/archiv/+page.svelte` | Platzhalter an echte Daten anbinden |
| `frontend/src/routes/archiv/+page.server.ts` | Endpoint-Call beim Laden der Seite |
