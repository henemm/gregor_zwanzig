# Context: Issue #772 — Archiv-Statistiken ohne echten Verhaltenstest

## Request Summary
Beim #765-Test-Hygiene-Sweep wurde `test_issue_396_archive_stats.py` gelöscht, weil es die Archiv-Statistik-Features nur über Source-Greps "testete". Dadurch ist echte Coverage für die archive-stats-Features verloren. Ziel: echten Verhaltenstest ergänzen (keine Mocks, kein Source-Grep).

## Related Files
| File | Relevance |
|------|-----------|
| `internal/store/store.go:781` (`BriefingCountByTrip`), `:797` (`AlertCountByTrip`) | Zu testende Store-Methoden — zählen Log-Einträge pro Trip, fail-soft. **Kein Test.** |
| `internal/handler/archive_stats.go` (`ArchiveStatsHandler`) | Handler, der die zwei Counts mandantengetrennt als JSON liefert. **Kein Test.** |
| `cmd/server/main.go:231` | Route `r.Get("/api/archive/stats", handler.ArchiveStatsHandler(s))`. |
| `internal/handler/cockpit.go` (24h-Filter) | Issue behauptet "kein Test" — **falsch**: `cockpit_test.go` deckt 24h-/Heute-Filter bereits ab (grün verifiziert). Nicht im Scope. |
| `internal/handler/cockpit_test.go` | Liefert wiederverwendbare Helfer: `seedBriefingLog`, `seedAlertLog`, `withUserCtx`. |
| `internal/handler/trip_write_test.go:15` | `newTestStore(t)` → `store.New(t.TempDir(), "test")`. |
| `internal/middleware/auth.go:68,85` | `UserIDFromContext` / `ContextWithUserID` für Auth-Kontext im Test. |

## Existing Patterns
- **Go-Handler-Test:** `httptest.NewRequest` + `withUserCtx(req, userID)` + `httptest.NewRecorder()` + `h.ServeHTTP`. JSON-Response prüfen. (Vorbild: `cockpit_test.go`)
- **Store-Test:** `newTestStore` mit `t.TempDir()`; Log-Files via `seedBriefingLog`/`seedAlertLog` schreiben; `s.WithUser(id)` für Mandantentrennung.
- **Log-Schema:** `BriefingLogEntry{TripID,Kind,SentAt,Channels}`, `AlertLogEntry{TripID,SentAt,ChangesCount,Severity}` — Datei `briefing_log.json`/`alert_log.json` mit `{"entries":[...]}`.

## Dependencies
- Upstream: `LoadBriefingLog`/`LoadAlertLog` (lesen JSON-Logs, fail-soft).
- Downstream: Frontend Archiv-View konsumiert `/api/archive/stats`.

## Existing Specs
- Issue #396 (archive-stats, Feature live) — kein offenes Spec-Dokument; Bug-Fix-Workflow (Test-Nachzug).

## Risks & Considerations
- **Scope-Korrektur:** Cockpit-24h-Filter ist bereits getestet → nur Store-Counts + Handler + Endpoint sind echte Lücken.
- **Mandantentrennung:** Test muss mit **zwei** Nutzern beweisen, dass Counts pro `user_id` isoliert sind (CLAUDE.md-Pflicht).
- **Fail-soft:** Counts liefern leere Map (kein 500) bei fehlenden Logs — Test muss das mit abdecken.
- **Keine Mocks / kein Source-Grep** (CLAUDE.md). Echte Store-Instanz, echte JSON-Records, echter HTTP-Handler-Aufruf.
