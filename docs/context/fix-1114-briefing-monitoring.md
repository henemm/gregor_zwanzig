# Context: fix-1114-briefing-monitoring

## Request Summary
`/api/scheduler/status` ist blind für **degradierte** Briefings: Fällt der Wetter-Provider aus und werden Briefings mit fehlenden Segmenten (`has_error`-Platzhalter) versendet, meldet der Scheduler `ok` — kein Alarm. Issue #1114 will ein Aggregat `briefing_health` einführen, das offene Degradationen sichtbar macht.

## Architektur des Scheduler-Pfads (Ist-Zustand)

```
Go-Cron-Tick  →  POST Python /api/scheduler/trigger (pro User)
                    → send_reports_for_hour() → {status, count:sent, failed}
                 Go parst failed>0 → error, sonst ok
                 Go speichert IN-MEMORY lastRuns[jobID]{time,status,error}
GET /api/scheduler/status (Go, PUBLIC/no-auth)
                 → jobs[].last_run{time, status ∈ {ok,error}, error}
```

**Der blinde Fleck:** Teil-Degradation (einige Segmente `has_error`, Briefing trotzdem versendet) → Outcome `"sent"` → `failed=0` → Python `status:ok` → Go `ok`. Der Go-Status kennt nur `ok`/`error`, **kein `partial`** (der `partial`-Wert aus #766 lebt nur im Python-Trigger-Response-Body und wird von Go zu `error` kollabiert, wenn `failed>0`).

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/trip_report_scheduler.py:186-211` | `send_reports_for_hour` — zählt nur Komplettausfall/Exception als `failed`; Teil-Degradation = `sent` |
| `src/services/trip_report_scheduler.py:839,782-786` | Teilausfall-Segmente (`errors`) → `_write_pending_marker` |
| `src/services/trip_report_scheduler.py:639-656` | Komplettausfall-Guard → Pending-Marker + `no_weather` |
| `src/services/trip_report_scheduler.py:72-84,279-329` | `pending_briefings.json` lesen/schreiben (pro User) |
| `src/services/segment_weather.py:142-153` | `has_error`-Platzhalter bei `ProviderRequestError` |
| `api/routers/scheduler.py:31-47` | Python-Trigger-Response `{status, count, failed}`, `partial` bei `failed>0` |
| `internal/scheduler/scheduler.go:183-241,314-348` | Go: `recordRun` (ok/error), `Status()` baut `jobs[].last_run` |
| `internal/handler/scheduler_status.go:12` | Go-Handler für `/api/scheduler/status` |
| `internal/router/router.go:193` + `internal/middleware/auth.go:34` | Route **public/no-auth** |
| `internal/store/log.go:23-40` | Bestehendes Datei-basiertes Python→Go-Muster (`briefing_log.json`-Reader) |
| `src/providers/call_log.py:56-79` | `openmeteo_calls.jsonl` — Call-Level Provider-Fehler (ts, status, source="briefing") |

## Existing Patterns
- **Dateibasierte Python→Go-Schnittstelle:** Python schreibt pro-User-JSON (`briefing_log.json`, `pending_briefings.json`), Go liest read-only über `internal/store/*`. Das ist das etablierte Muster für „Python-Fakt → Go-Response".
- **Additive Status-Erweiterung:** `Status()` (scheduler.go:314-348) baut eine `map[string]any` — ein `briefing_health`-Feld ist additiv einbaubar, ohne bestehende Felder zu brechen.
- **Pending-Marker als Degradations-Spur:** Jede Degradation (Teil **und** Komplett) schreibt einen Pending-Marker mit `failed_segment_ids`, `attempts`, `created_at`. Erfolgreicher Catch-up entfernt ihn (`_remove_pending_marker`).

## Design-Optionen (für Analyse-Phase)

**Kernfrage: Woher bezieht `briefing_health` seine Daten?**

| Option | Ansatz | Pro | Contra |
|--------|--------|-----|--------|
| **A (empfohlen): Go-seitige Aggregation offener Pending-Marker** | Go scannt alle `data/users/*/pending_briefings.json` und aggregiert: Anzahl offener Marker, ältester `created_at`, Summe `failed_segment_ids` | Reuse bestehendes Datei-Muster; **kein neuer Write im heißen Briefing-Pfad** (geringer Blast Radius auf kritischen Sendepfad); Pending-Marker erfassen jede Degradation zuverlässig | „Segmente beim letzten Lauf" wird zu „offene unaufgelöste Degradationen" umgedeutet (Marker verschwinden nach Catch-up) |
| **B: Neue Python-Health-Datei** | Python persistiert pro Lauf `briefing_health.json` (degraded/total Segmente, letzter Provider-Fehler-ts) | Erfasst exakt „letzter Lauf" auch nach Catch-up | Neuer Schreibpfad im kritischen Sendepfad; Schema-Rework-Risiko (Read-Modify-Write-Pflicht) |
| **C: Provider-Call-Log auswerten** | Go/Skript wertet `openmeteo_calls.jsonl` (source="briefing") aus | Exakter Fehler-Zeitstempel + Rate | Kein Bezug „Segment X im Briefing Y fehlte"; separate Datei Go/Python |

**Tech-Lead-Neigung:** **Option A** als Basis für Feld „offene Pending-Marker" (Kern-Alarm-Signal, deckt sich mit Issue-Vorschlag „offene Marker älter als N Stunden") + **Option C** nur für den optionalen Zeitstempel „letzter Provider-Fehler". Damit kein neuer Write im Sendepfad. Feld „Segmente mit Provider-Fehler beim letzten Lauf" wird als „Segment-Summe über offene Marker" realisiert — der monitoring-relevante Zustand ist „gibt es unaufgelöste Lücken", nicht die historische Zahl.

## Dependencies
- **Upstream:** Pending-Marker-Struktur (`trip_report_scheduler.py`), `internal/store` Datei-Reader, `Status()`-Response-Map.
- **Downstream:** `check-gregor20.sh` in **henemm-infra** (Schwester-Issue!) wertet `briefing_health` aus → BetterStack-Alarm über bestehenden Heartbeat (Quota beachten — kein neuer Heartbeat).

## Existing Specs
- `docs/reference/api_contract.md` — DTOs/Datenformate (falls Response-Vertrag dokumentiert).
- #766 (`partial`-Status) — verwandt, deckt diesen Fall aber nicht ab.

## Risks & Considerations
- **Privacy (#252):** `/api/scheduler/status` ist **public/no-auth**. `briefing_health` darf **nur aggregierte Zahlen** enthalten — niemals User-IDs, Trip-Namen oder Empfänger. Muss im Test abgesichert werden.
- **Multi-User-Pflicht:** Aggregat „über alle User" muss mit **≥2 Usern** getestet werden (CLAUDE.md).
- **KEINE Mocks:** TDD-RED braucht echten HTTP-Call gegen laufende App mit echtem degradiertem Zustand (echter Pending-Marker für Test-User), dann `/api/scheduler/status` prüfen.
- **Schema-Rework (falls Option B):** Read-Modify-Write-Merge Pflicht, `data_schema_backup.py`-Hook feuert bei Edits an Schema-Dateien.
- **Scope-Abgrenzung:** Punkt 2 (`check-gregor20.sh`) + Punkt 3 (MQ/Telegram-Hinweis, optional) sind **henemm-infra** bzw. optional — **nicht** Teil dieses Workflows. Nur der `briefing_health`-Datenlieferant im gregor-Repo.
- **Go/Python-Cross-Language:** Änderung berührt beide Sprachen → Deploy ist full-stack (Go-Binary + evtl. Python).
