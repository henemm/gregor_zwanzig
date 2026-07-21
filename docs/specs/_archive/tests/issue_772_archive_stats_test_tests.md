---
entity_id: issue_772_archive_stats_test_tests
type: tests
created: 2026-06-12
updated: 2026-06-12
status: draft
version: "1.0"
tags: [tests, go, archive-stats, coverage, multi-tenant, issue-772]
parent: issue_772_archive_stats_test
phase: phase5_tdd_red
---

# Issue #772 — Archiv-Statistiken Verhaltenstest (Tests)

## Approval

- [x] Approved

## Purpose

Test-Manifest für die echten Verhaltenstests aus
`docs/specs/modules/issue_772_archive_stats_test.md`. Jeder Go-Test mappt 1:1 auf
ein Acceptance Criterion der Parent-Spec. Keine Mocks, kein Source-Grep — echte
`store.Store`-Instanzen, echte JSON-Log-Dateien, echte Handler-Aufrufe.

Parent-Spec: `docs/specs/modules/issue_772_archive_stats_test.md` v1.0

## Source

- **File:** `internal/store/archive_stats_test.go` (NEU — Store-Zählung pro Trip,
  Fail-soft, Mandantentrennung)
- **File:** `internal/handler/archive_stats_test.go` (NEU — Handler-Verhalten,
  JSON-Response, leere Logs, Mandantentrennung)

## Test Inventory

### Go Store (`internal/store/archive_stats_test.go`)

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `TestBriefingCountByTrip_CountsPerTrip` | AC-1 | Echte `briefing_log.json` mit mehreren Einträgen für zwei Trips → korrekte Map (trip-A=3, trip-B=1). |
| `TestAlertCountByTrip_CountsPerTrip` | AC-2 | Echte `alert_log.json` mit mehreren Einträgen für zwei Trips → korrekte Map. |
| `TestCountByTrip_FailSoftWhenNoLogs` | AC-3 | Store ohne Log-Dateien → beide Count-Methoden liefern leere Map und keinen Fehler. |
| `TestCountByTrip_IsolatedPerUser` | AC-4 | Zwei Nutzer (userA/userB) mit eigenen Logs → `WithUser` zählt strikt getrennt, keine Vermischung. |

### Go Handler (`internal/handler/archive_stats_test.go`)

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `TestArchiveStatsHandler_ReturnsCountsJson` | AC-5 | Geseedete Logs + Auth-Kontext → HTTP 200, `application/json`, `briefings`/`alerts` mit korrekten Counts pro Trip. |
| `TestArchiveStatsHandler_EmptyWhenNoLogs` | AC-6 | Nutzer ohne Logs → HTTP 200, `briefings` und `alerts` jeweils leeres Objekt `{}` (kein 500, kein null). |
| `TestArchiveStatsHandler_IsolatedPerUser` | AC-7 | Handler nacheinander mit userA- und userB-Kontext → jeder erhält nur seine eigenen Counts. |

## Implementation Details

Tests folgen dem No-Mocks-Pattern des Projekts (Vorbild: `cockpit_test.go`):
- Echte `store.New(t.TempDir(), userID)`-Instanzen.
- Log-Dateien werden mit dem realen Schema auf Platte geschrieben.
- Handler via `httptest.NewRequest` + `ContextWithUserID` + `ServeHTTP`.
- RED-Nachweis bei Coverage-Fill von funktionierendem Code: temporäre Mutation des
  Produktivcodes lässt die jeweiligen Asserts fehlschlagen (Tests haben Zähne);
  ohne Mutation sind sie grün (= Live-Code korrekt + jetzt beobachtet).
