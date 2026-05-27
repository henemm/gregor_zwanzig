---
entity_id: issue_396_archive_stats
type: module
created: 2026-05-27
updated: 2026-05-27
status: draft
version: "1.0"
tags: [archive, stats, briefing-log, alert-log, go-api, frontend, issue-396]
---

<!-- Issue #396 — Archiv-Statistiken: Briefings + Alarme pro Tour zählen -->

# Issue #396 — Archiv-Statistiken: Briefings + Alarme pro Tour

## Approval

- [x] Approved

## Zweck

Der Archiv-Screen zeigt pro vergangener Tour `—` für "Briefings gesendet" und "Alarme
ausgelöst". Beide Zahlen liegen bereits in JSON-Logs vor (`briefing_log.json`,
`alert_log.json`). Diese Spec beschreibt die Verkabelung: Python-Seitig die 48h-Bereinigung
entfernen, Go-seitig Aggregation per trip_id, Frontend die Platzhalter anbinden.

**Kein Scope:** Forecast-Accuracy (%), retrospektive Schlagzeilen, Ist-Wetter-Vergleich.

## Source

- **Layer:** Python-Backend + Go-API + Frontend (SvelteKit)

| Datei | Änderungstyp |
|-------|-------------|
| `src/services/trip_alert.py` | 48h-Retention entfernen (~3 Zeilen) |
| `internal/store/store.go` | `BriefingCountByTrip()` + `AlertCountByTrip()` |
| `internal/handler/archive_stats.go` (neu) | `GET /api/archive/stats` Handler |
| `cmd/server/main.go` | Route registrieren |
| `frontend/src/routes/archiv/+page.server.ts` | Endpoint-Call beim Laden |
| `frontend/src/routes/archiv/+page.svelte` | Platzhalter mit echten Daten verbinden |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/trip_alert.py` — `_append_alert_log()` | Upstream | Schreibt `alert_log.json`; Retention-Entfernung macht Log dauerhaft |
| `internal/store/store.go` — `LoadBriefingLog()` | Upstream | Liest `briefing_log.json`; neue Aggregationsfunktion drauf |
| `internal/store/store.go` — `LoadAlertLog()` | Upstream | Liest `alert_log.json`; neue Aggregationsfunktion drauf |
| `GET /api/cockpit/status` | Nicht-Abhängigkeit | Filtert Go-seitig auf 24h — unverändert nach Python-Change |

## Implementation Details

### Fix 1 — `trip_alert.py`: 48h-Retention entfernen

```python
# Vorher:
cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=48)
data["entries"] = [e for e in data["entries"] if _aware(e["sent_at"]) > cutoff]

# Nachher: entfernt — Log wächst dauerhaft.
# Go filtert 24h für /api/cockpit/status clientseitig (kein Python-Change nötig).
```

### Fix 2 — `store.go`: Aggregation per trip_id

```go
// BriefingCountByTrip gibt einen map[tripID]count zurück.
func (s *Store) BriefingCountByTrip(userID string) (map[string]int, error)

// AlertCountByTrip gibt einen map[tripID]count zurück.
func (s *Store) AlertCountByTrip(userID string) (map[string]int, error)
```

Beide lesen die vorhandenen JSON-Dateien und aggregieren nach `trip_id`.

### Fix 3 — `GET /api/archive/stats`

Response:
```json
{
  "briefings": { "trip-abc": 12, "trip-xyz": 6 },
  "alerts":    { "trip-abc": 1,  "trip-xyz": 0 }
}
```

Auth: gleiche Session-Auth wie alle anderen `/api/`-Endpoints.

### Fix 4 — Frontend

`+page.server.ts`: `fetch('/api/archive/stats')` beim Laden der Archiv-Seite.

`+page.svelte`:
- `alertCount(trip)`: bisher `alert_rules.length` → `archiveStats.alerts[trip.id] ?? 0`
- Stats-Strip "Briefings gesendet": Summe aller Werte aus `archiveStats.briefings`
- Stats-Strip "Alarme ausgelöst": Summe aller Werte aus `archiveStats.alerts`
- `{@render accuracyBar()}`: bleibt Platzhalter (`—`)

## Expected Behavior

- **Input:** Archiv-Seite wird geladen; User hat vergangene Touren mit gesendeten Briefings/Alarmen
- **Output:** Listenzeilen zeigen echte Zahlen ("12 Briefings · 1 Alarm"); Stats-Strip summiert korrekt
- **Side effects:** `alert_log.json` wächst dauerhaft. Größe: ~200 Bytes pro Alert-Eintrag, realistisch <100 Einträge/Jahr pro User → vernachlässigbar.

## Acceptance Criteria

- **AC-1:** Given eine vergangene Tour mit 12 gesendeten Briefings / When der Archiv-Screen geladen wird / Then zeigt die Listenzeile "12" statt "—" im Briefings-Feld
  - Test: `tests/tdd/test_issue_396_archive_stats.py::test_briefing_count_per_trip`
  - Test: `tests/tdd/test_issue_396_archive_stats.py::test_store_go_has_briefing_count_by_trip`

- **AC-2:** Given eine vergangene Tour mit 2 ausgelösten Alarmen (älter als 48h) / When der Archiv-Screen geladen wird / Then zeigt die Listenzeile "2" statt "—" (Retention-Entfernung wirkt)
  - Test: `tests/tdd/test_issue_396_archive_stats.py::test_alert_count_includes_old_entries`
  - Test: `tests/tdd/test_issue_396_archive_stats.py::test_alert_retention_code_removed`

- **AC-3:** Given `GET /api/cockpit/status` / When der Endpoint nach dem Python-Fix aufgerufen wird / Then zeigt er weiterhin nur Alerts der letzten 24h (Go-seitige Filterung unverändert)
  - Test: `tests/tdd/test_issue_396_archive_stats.py::test_cockpit_still_filters_24h`

- **AC-4:** Given kein einziger Alert jemals ausgelöst / When der Archiv-Screen geladen wird / Then zeigt die Listenzeile "0" (kein Crash, kein `—`)
  - Test: `tests/tdd/test_issue_396_archive_stats.py::test_zero_counts_handled`
  - Test: `tests/tdd/test_issue_396_archive_stats.py::test_store_go_has_alert_count_by_trip`
  - Test: `tests/tdd/test_issue_396_archive_stats.py::test_archive_stats_handler_exists`

## Known Limitations

- Rückwirkend: Alerts die vor diesem Deploy ausgelöst wurden und älter als 48h sind, fehlen
  im Log (wurden bereinigt). Zähler startet ab Deploy-Datum bei 0 für alte Einträge.
- `accuracy`-Feld und Schlagzeile: bewusst außerhalb Scope.

## Changelog

- 2026-05-27: Spec erstellt. Scope bewusst auf Zähler beschränkt — Accuracy/Schlagzeilen
  ausgeschlossen (Claude Design hatte Kreativitätsüberschuss in der ursprünglichen Issue-Beschreibung).
