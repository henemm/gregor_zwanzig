---
entity_id: issue_200_inbound_polling_global
type: bugfix
created: 2026-05-12
updated: 2026-05-12
status: draft
version: "1.0"
tags: [bugfix, scheduler, imap, performance]
---

<!-- GitHub Issue #200 — Inbound Email Polling triggert N IMAP-Logins pro Tick (sollte 1 sein) -->

# Issue #200 — Inbound Email Polling: ein Tick = ein IMAP-Login

## Approval

- [ ] Approved

## Purpose

Der Cron-Job `inbound_command_poll` (5-Min-Tick) ruft `/api/scheduler/inbound-commands` über `runForAllUsers` einmal pro registriertem User auf. Der Endpoint ist aber global (ein gemeinsames Postfach `gregor_zwanzig@henemm.com`, ignoriert `user_id`). Folge: N redundante IMAP-Logins pro Tick. Bei falschem Pass: N Auth-Fails pro Tick → Stalwart-Rate-Limiting/IP-Sperre (siehe MQ #18397).

Fix: `inboundCommands()` ruft den Endpoint genau einmal pro Tick auf, unabhängig von der User-Anzahl. Bestehende `triggerEndpointForUser`-Methode bleibt für die echten per-User-Jobs unverändert.

## Source

- **File:** `internal/scheduler/scheduler.go`
- **Identifier:** `Scheduler.inboundCommands()` (Z. 182-186), neuer Helper `Scheduler.triggerGlobalEndpoint(path string) error`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/scheduler/scheduler.go` | go file | Cron-Scheduler |
| `api/routers/scheduler.py` | python file | `/inbound-commands`-Endpoint (bleibt unverändert, ist bereits global) |
| `docs/specs/modules/go_scheduler.md` | spec | Übergeordnete Spec — definiert `*/5 → POST /inbound-commands` (1 Call) |

## Implementation Details

### Neuer Helper

```go
// triggerGlobalEndpoint sends a single POST to the Python trigger endpoint
// without iterating over users. Use for global jobs (e.g. inbound polling)
// where the endpoint operates on shared resources.
func (s *Scheduler) triggerGlobalEndpoint(path string) error {
    url := s.pythonURL + path
    resp, err := s.client.Post(url, "application/json", nil)
    if err != nil {
        return fmt.Errorf("HTTP error: %w", err)
    }
    defer resp.Body.Close()
    body, _ := io.ReadAll(resp.Body)
    if resp.StatusCode >= 400 {
        return fmt.Errorf("HTTP %d: %s", resp.StatusCode, string(body))
    }
    log.Printf("[scheduler] %s → %d", path, resp.StatusCode)
    return nil
}
```

### Geänderter Job-Wrapper

```go
func (s *Scheduler) inboundCommands() {
    s.recordRun("inbound_command_poll", func() error {
        return s.triggerGlobalEndpoint("/api/scheduler/inbound-commands")
    })
}
```

Andere Job-Wrapper (`morningSubscriptions`, `eveningSubscriptions`, `tripReports`, `alertChecks`) bleiben unverändert — sie sind echt per-User.

## Expected Behavior

- **Input:** Cron-Tick alle 5 Minuten
- **Output:** Genau **ein** HTTP-POST auf `/api/scheduler/inbound-commands` pro Tick (kein `user_id`-Query-Parameter)
- **Side effects:** Genau ein IMAP-Login auf Stalwart pro Tick (auf Staging vorher: 14 Logins/Tick)

## Acceptance Criteria

- **AC-1:** Given der Scheduler läuft mit ≥2 registrierten Usern im Store / When `inboundCommands()` einmal getriggert wird / Then geht **genau ein** POST-Request an `/api/scheduler/inbound-commands` raus (verifiziert via Test-HTTP-Server, der Requests zählt).
  - Test: (populated after /tdd-red)

- **AC-2:** Given Test-HTTP-Server antwortet mit Status 200 / When `inboundCommands()` läuft / Then wird `lastRuns["inbound_command_poll"]` mit `Status="ok"` gesetzt.
  - Test: (populated after /tdd-red)

- **AC-3:** Given Test-HTTP-Server antwortet mit Status 500 / When `inboundCommands()` läuft / Then wird `lastRuns["inbound_command_poll"]` mit `Status="error"` gesetzt und Error-Message enthält `HTTP 500`.
  - Test: (populated after /tdd-red)

## Out of Scope

- **Cleanup der 14 Test-User in Staging-DB** — separates Aufräum-Thema, nicht Bug-Voraussetzung.
- **Parallel-Polling Go + Python** — beide Scheduler triggern dasselbe Inbound-Polling. Aktuell akzeptiert (2 Logins/5min nach Fix), Konsolidierung ggf. später.
- **Backoff bei Auth-Fehlern** — der vermutete „Backoff-Bug" aus MQ #18397 existiert nicht; Symptom kam ausschließlich aus N×Burst.

## Verification

- **Unit:** `TestInboundCommandsCallsEndpointOnce` (Go-Test, neuer Test, mit `httptest.Server`).
- **Live nach Deploy auf Staging:**
  ```bash
  journalctl -u gregor-api-staging --since "10 min ago" | grep "inbound-commands" | wc -l
  ```
  Erwartet: ~2 (zwei 5-Min-Ticks), nicht 28.
