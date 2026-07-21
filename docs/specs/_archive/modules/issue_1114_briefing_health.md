---
entity_id: issue_1114_briefing_health
type: module
created: 2026-07-08
updated: 2026-07-08
status: draft
version: "1.0"
tags: [go, scheduler, monitoring, briefing, privacy]
---

<!-- Issue #1114 -->

# Issue 1114 — briefing_health Aggregat in /api/scheduler/status

## Approval

- [ ] Approved

## Purpose

`/api/scheduler/status` meldet aktuell `ok`, selbst wenn Briefings mit
fehlenden Wetter-Segmenten (`has_error`-Platzhalter durch Provider-Ausfall)
versendet wurden — Teil-Degradation zählt nicht als `failed`. Dieses Feature
fügt ein additives Aggregat `briefing_health` hinzu, das offene
Nachliefer-Marker (`pending_briefings.json`) über alle Nutzer zusammenfasst,
damit externes Monitoring (`check-gregor20.sh`, henemm-infra) unaufgelöste
Degradationen erkennen kann, ohne dass der Scheduler selbst Alarm auslöst.

## Source

- **File:** `internal/scheduler/scheduler.go` — `Status()` (Zeile 314–348), additive Erweiterung der Response-Map
- **Identifier:** `func (s *Scheduler) Status() map[string]any`

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `internal/store/pending_briefings.go` | CREATE | Fail-soft Reader für `data/users/<uid>/pending_briefings.json`, analog zu `LoadBriefingLog` in `internal/store/log.go` |
| `internal/scheduler/briefing_health.go` | CREATE | `func (s *Scheduler) BriefingHealth() map[string]any` — Verzeichnis-Scan über `data/users/*/pending_briefings.json`, Aggregation + optionaler Provider-Fehler-Zeitstempel |
| `internal/scheduler/scheduler.go` | MODIFY | `Status()` um `"briefing_health": s.BriefingHealth()` ergänzen (Zeile ~347), keine bestehenden Felder ändern |
| `internal/scheduler/briefing_health_test.go` | CREATE | Echter HTTP-Roundtrip (Muster: `internal/scheduler/scheduler_subscription_status_test.go:107-142`), echte Test-User-Dateien in `t.TempDir()`, ≥2 User |

## Estimated Scope

- **LoC:** ~90 (Go-Aggregation + Store-Reader + Wiring, exkl. Test)
- **Files:** 4 (3 neu, 1 geändert)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/store/log.go` (`LoadBriefingLog`-Pattern) | intern | Vorbild für fail-soften, dateibasierten Python→Go-Reader (leere Liste bei fehlender/korrupter Datei) |
| `data/users/<uid>/pending_briefings.json` | Datenquelle | Wird bereits von `src/services/trip_report_scheduler.py:279-329` geschrieben (Read-Modify-Write, kein neuer Schreibpfad nötig) |
| `data/diagnostics/openmeteo_calls.jsonl` | Datenquelle (optional) | Append-only JSONL, Format `{ts, endpoint, status, source, error}` — Feld `last_provider_error_at` filtert auf `source=="briefing"` und `error != null` |
| `internal/store.Store.DataDir` | intern | Basisverzeichnis für den Verzeichnis-Scan über alle User (`s.store.DataDir`) |
| `internal/handler/scheduler_status.go` | intern | Unverändert — ruft weiterhin nur `sched.Status()` auf, kein Handler-Code nötig |

## Implementation Details

### 1. `internal/store/pending_briefings.go` (NEU)

Struct und Reader analog zu `BriefingLogEntry`/`LoadBriefingLog` (`internal/store/log.go:9-40`):

```go
type PendingBriefingEntry struct {
    TripID           string   `json:"trip_id"`
    ReportType       string   `json:"report_type"`
    Date             string   `json:"date"`
    SlotHour         int      `json:"slot_hour"`
    FailedSegmentIDs []string `json:"failed_segment_ids"`
    Attempts         int      `json:"attempts"`
    CreatedAt        string   `json:"created_at"` // RFC3339
}
```

`LoadPendingBriefingsForUser(dataDir, userID string) ([]PendingBriefingEntry, error)`
liest `data/users/<uid>/pending_briefings.json`; fehlende/korrupte Datei →
leere Liste, kein Error (fail-soft, wie `LoadBriefingLog`).

### 2. `internal/scheduler/briefing_health.go` (NEU)

`func (s *Scheduler) BriefingHealth() map[string]any`:

1. `filepath.Glob(filepath.Join(s.store.DataDir, "users", "*", "pending_briefings.json"))`
   liefert alle User-Marker-Dateien (kein `user_id` wird in die Response
   übernommen — nur zum Auflisten der Dateien verwendet).
2. Für jede gefundene Datei: User-ID aus dem Pfad extrahieren, Datei via
   `store.LoadPendingBriefingsForUser` laden, alle Entries über alle User in
   eine flache Liste sammeln.
3. Aggregation:
   - `open_pending_briefings` = Anzahl aller Entries über alle User
   - `degraded_segments_total` = Summe `len(FailedSegmentIDs)` über alle Entries
   - `oldest_pending_age_hours` = `(now - min(CreatedAt))` in Stunden, `0` wenn keine Entries
   - `last_provider_error_at` = siehe Schritt 4, `nil` wenn keiner gefunden
4. `last_provider_error_at` (optional): `data/diagnostics/openmeteo_calls.jsonl`
   zeilenweise parsen (fail-soft, Datei fehlt → `nil`), Zeilen mit
   `source == "briefing"` und nicht-leerem `error`-Feld filtern, jüngsten
   `ts`-Wert (RFC3339) zurückgeben. Parse-Fehler einzelner Zeilen werden
   übersprungen (keine Kette bricht ab).

### 3. `internal/scheduler/scheduler.go` — `Status()` (Zeile 343-348)

Bestehende Return-Map bleibt unverändert, es wird nur ein Key ergänzt:

```go
return map[string]any{
    "running":         true,
    "jobs":            jobs,
    "timezone":        s.cron.Location().String(),
    "briefing_health": s.BriefingHealth(),
}
```

## Expected Behavior

- **Input:** `GET /api/scheduler/status` (public, no-auth), Dateisystem-Zustand unter `data/users/*/pending_briefings.json` und optional `data/diagnostics/openmeteo_calls.jsonl`
- **Output:** Bestehende Response-Felder (`running`, `jobs`, `timezone`, `jobs[].last_run`) unverändert + neues Feld `briefing_health: {open_pending_briefings: int, degraded_segments_total: int, oldest_pending_age_hours: number, last_provider_error_at: string|null}`
- **Side effects:** Keine — reiner Lesepfad, kein neuer Schreibvorgang, kein Eingriff in den Briefing-Sendepfad (`trip_report_scheduler.py` bleibt unverändert)

## Acceptance Criteria

- **AC-1:** Given keine `pending_briefings.json` existiert für irgendeinen User (Null-Zustand) / When `GET /api/scheduler/status` aufgerufen wird / Then enthält die Response `briefing_health: {open_pending_briefings: 0, degraded_segments_total: 0, oldest_pending_age_hours: 0, last_provider_error_at: null}`
  - Test: Echter HTTP-Call gegen den Handler mit leerem `t.TempDir()` als DataDir, keine Marker-Dateien angelegt, JSON-Response geparst und Nullwerte geprüft.

- **AC-2:** Given zwei Test-User (`tdd-1114-usera`, `tdd-1114-userb`) mit je einer echten `pending_briefings.json` (User A: 1 Entry mit 2 `failed_segment_ids`, User B: 1 Entry mit 1 `failed_segment_id`) / When `GET /api/scheduler/status` aufgerufen wird / Then ist `open_pending_briefings == 2` und `degraded_segments_total == 3` — die Summe über BEIDE User, nicht nur einen
  - Test: Echte Dateien für zwei User im `t.TempDir()`-DataDir anlegen (kein Mock), Handler real aufrufen (Muster `internal/scheduler/scheduler_subscription_status_test.go:107-142`), Zahlen gegen die angelegten Marker verifizieren.

- **AC-3:** Given ein offener Marker mit `created_at` vor genau 5 Stunden (kontrolliert gesetzt in der Test-Fixture) / When `GET /api/scheduler/status` aufgerufen wird / Then liegt `oldest_pending_age_hours` bei ungefähr 5 (Toleranz ±0.1h für Testlaufzeit) und entspricht dem ÄLTESTEN Marker, wenn mehrere existieren
  - Test: Zwei Marker mit unterschiedlichem `created_at` (5h und 1h alt) über zwei User anlegen, Response prüft, dass der ältere Wert (5h) gewinnt.

- **AC-4:** Given die Test-User-IDs (`tdd-1114-usera`, `tdd-1114-userb`) und deren Trip-IDs sind in den angelegten Marker-Dateien enthalten / When die rohe JSON-Response von `GET /api/scheduler/status` als String inspiziert wird / Then taucht KEINE der Test-User-IDs, Trip-IDs oder sonstiger identifizierender Strings in der Response auf — `briefing_health` enthält ausschließlich aggregierte Zahlen und einen ISO-Zeitstempel
  - Test: Response-Body als Rohstring gegen die verwendeten User-/Trip-ID-Literale prüfen (`strings.Contains` == false für jede ID), Privacy-Regression zu #252.

- **AC-5:** Given `data/diagnostics/openmeteo_calls.jsonl` fehlt komplett (kein Provider-Call-Log vorhanden) / When `GET /api/scheduler/status` aufgerufen wird / Then ist `last_provider_error_at == null` und der Handler antwortet trotzdem mit HTTP 200 (fail-soft, kein Absturz bei fehlender Diagnosedatei)
  - Test: `t.TempDir()` ohne `data/diagnostics/`-Verzeichnis, echter HTTP-Call, Statuscode und Feldwert geprüft.

- **AC-6:** Given die bestehenden Felder `running`, `jobs`, `timezone` und `jobs[].last_run` vor der Änderung / When der neue Key `briefing_health` additiv zur Response-Map ergänzt wird / Then bleiben alle bestehenden Feldwerte und -typen unverändert (Regressionstest gegen den bisherigen `Status()`-Vertrag)
  - Test: Bestehender Test `TestSchedulerStatusEndpointJSON` (`internal/scheduler/scheduler_subscription_status_test.go:107`) bleibt grün; zusätzlicher Assert, dass `running`, `jobs`, `timezone` weiterhin vorhanden und vom erwarteten Typ sind.

## Known Limitations

- `last_provider_error_at` ist optional und best-effort: bei sehr großem `openmeteo_calls.jsonl` wird die gesamte Datei zeilenweise durchlaufen (kein Tail-Limit in v1) — Performance-Optimierung (z. B. Zeilenlimit) ist ein möglicher Follow-up, falls die Datei relevant wächst.
- Das Aggregat zeigt nur **offene** (unaufgelöste) Degradationen; nach erfolgreichem Nachliefer-Catch-up verschwindet der Marker und damit auch die historische Spur — „letzte Degradation vor X Stunden, mittlerweile behoben" ist damit NICHT sichtbar (bewusste Tech-Lead-Entscheidung, siehe Kontext-Datei Option A vs. B).
- Auswertung durch `check-gregor20.sh` (henemm-infra) und optionaler Telegram/MQ-Hinweis bei Degradation sind explizit NICHT Teil dieses Workflows (siehe Out of Scope).
- Provider-Fallback-Mechanismus selbst (#1115) wird von diesem Feature nicht berührt — `briefing_health` ist ein reines Beobachtungs-Aggregat.

## Out of Scope

- `check-gregor20.sh`-Auswertung des neuen Felds → Schwester-Issue in `henemm/henemm-infra` (nicht hier).
- Proaktiver Telegram/MQ-Hinweis bei Degradation → optional, separates Issue falls gewünscht.
- Provider-Fallback-Implementierung selbst → Issue #1115.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Additive, rein lesende Erweiterung einer bestehenden Response-Map nach etabliertem Datei-Lese-Muster (`internal/store/log.go`). Kein neuer Schreibpfad, kein neuer Endpoint, keine Schema-Änderung an Bestandsdaten — keine architektonische Grundsatzentscheidung nötig.

## Test Coverage

Tests in `internal/scheduler/briefing_health_test.go` (Muster: `internal/scheduler/scheduler_subscription_status_test.go`, echter `httptest`-Roundtrip gegen realen Handler mit echten Dateien in `t.TempDir()`, kein Mock):

- `TestBriefingHealthNullStateWhenNoMarkers` — AC-1
- `TestBriefingHealthAggregatesAcrossTwoUsers` — AC-2
- `TestBriefingHealthOldestMarkerWins` — AC-3
- `TestBriefingHealthResponseContainsNoUserIdentifiers` — AC-4
- `TestBriefingHealthNullProviderErrorWhenLogMissing` — AC-5
- `TestBriefingHealthExistingFieldsUnchanged` — AC-6 (baut auf bestehendem `TestSchedulerStatusEndpointJSON` auf)

## Changelog

- 2026-07-08: Initial spec erstellt — Issue #1114
