---
entity_id: issue_772_archive_stats_test
type: module
created: 2026-06-12
updated: 2026-06-12
status: draft
version: "1.0"
tags: [test, go, archive-stats, coverage, multi-tenant]
---

# Archiv-Statistiken — Echter Verhaltenstest (Issue #772)

## Approval

- [ ] Approved

## Purpose

Echte Verhaltenstests (Go, keine Mocks, kein Source-Grep) für die live laufenden
Archiv-Statistik-Features ergänzen, deren einziger "Test" beim #765-Sweep als
reiner Source-Grep gelöscht wurde. Abgedeckt werden Store-Zählung pro Trip,
Handler-Verhalten und Mandantentrennung.

## Source

- **File:** `internal/store/store.go` (`BriefingCountByTrip` :781, `AlertCountByTrip` :797)
- **File:** `internal/handler/archive_stats.go` (`ArchiveStatsHandler`)
- **Identifier:** neue Tests `internal/store/archive_stats_test.go`, `internal/handler/archive_stats_test.go`

## Estimated Scope

- **LoC:** ~140 (nur Test-Code)
- **Files:** 2 neue Test-Dateien (kein Produktivcode)
- **Effort:** low

## Dependencies

- `Store.LoadBriefingLog`/`LoadAlertLog`, `Store.WithUser`
- `middleware.ContextWithUserID` / `UserIDFromContext`
- Test-Helfer-Muster aus `internal/handler/cockpit_test.go` (`seedBriefingLog`/`seedAlertLog`, `withUserCtx`)

## Scope-Abgrenzung

- **NICHT im Scope:** Cockpit-24h-Filter (`cockpit.go`) — bereits durch `cockpit_test.go`
  (`FiltersAlertsByLast24h`, `FiltersBriefingsByToday`) mit echten Verhaltenstests
  abgedeckt. Das Issue nannte ihn als Lücke; das ist veraltet.
- **Kein Produktivcode-Eingriff.** Reine Test-Ergänzung. Bestehende Features bleiben
  byte-identisch.

## Acceptance Criteria

**AC-1:** Given eine Store-Instanz mit einem `briefing_log.json`, das mehrere
Einträge für zwei verschiedene Trips enthält, When `BriefingCountByTrip()`
aufgerufen wird, Then liefert es eine Map mit der korrekten Anzahl Briefings
pro `trip_id` (z.B. trip-A=3, trip-B=1) und keinen Fehler.

**AC-2:** Given eine Store-Instanz mit einem `alert_log.json`, das mehrere
Einträge für zwei verschiedene Trips enthält, When `AlertCountByTrip()`
aufgerufen wird, Then liefert es eine Map mit der korrekten Anzahl Alarme
pro `trip_id` und keinen Fehler.

**AC-3:** Given eine Store-Instanz ohne jegliche Log-Dateien (fehlende Dateien),
When `BriefingCountByTrip()` bzw. `AlertCountByTrip()` aufgerufen werden, Then
liefern beide eine leere (nicht-nil oder nil, aber leere) Map und keinen Fehler
(Fail-soft, niemals Panik/Fehler).

**AC-4:** Given zwei Nutzer (userA, userB) mit jeweils eigenen Log-Dateien
unterschiedlichen Inhalts, When über `WithUser(userA)` bzw. `WithUser(userB)`
gezählt wird, Then sieht jeder Nutzer ausschließlich seine eigenen Counts —
userAs Einträge tauchen nie in userBs Ergebnis auf (Mandantentrennung).

**AC-5:** Given ein über `ContextWithUserID` mit einer User-ID versehener
HTTP-Request und geseedete Briefing- und Alert-Logs für diesen Nutzer, When
`ArchiveStatsHandler` den Request bedient, Then antwortet er mit HTTP 200,
Content-Type `application/json` und einem Body, der die Felder `briefings`
und `alerts` mit den korrekten Counts pro Trip enthält.

**AC-6:** Given ein HTTP-Request für einen Nutzer ganz ohne Log-Dateien, When
`ArchiveStatsHandler` den Request bedient, Then antwortet er mit HTTP 200 und
liefert für `briefings` und `alerts` jeweils ein leeres JSON-Objekt `{}`
(kein 500, kein `null`).

**AC-7:** Given zwei Nutzer mit unterschiedlich geseedeten Logs, When der
Handler nacheinander mit dem Kontext von userA und userB aufgerufen wird, Then
liefert er pro Nutzer ausschließlich dessen eigene Counts (Handler-Pfad
mandantengetrennt über `WithUser(UserIDFromContext(...))`).

## Test Strategy

- **Keine Mocks, kein Source-Grep.** Echte `store.New(t.TempDir(), ...)`-Instanzen,
  echte JSON-Log-Dateien auf Platte, echte Handler-Aufrufe via `httptest`.
- Log-Dateien werden mit dem realen Schema geschrieben
  (`{"entries":[{trip_id,kind,sent_at,channels}|{trip_id,sent_at,changes_count,severity}]}`).
- Mindestens ein Test je Ebene (Store + Handler) beweist Mandantentrennung mit
  **zwei** verschiedenen Nutzern.

## Out of Scope

- Änderungen an Produktivcode (`store.go`, `archive_stats.go`, `cockpit.go`).
- Cockpit-Endpoint-Tests (bereits vorhanden).
