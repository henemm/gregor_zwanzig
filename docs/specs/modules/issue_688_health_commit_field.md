---
entity_id: issue_688_health_commit_field
type: module
created: 2026-06-09
updated: 2026-06-09
status: draft
version: "1.0"
tags: [health-endpoint, deploy-gate, go-api, ldflags, staging, bugfix]
---

# /api/health: commit-Feld ergänzen (Issue #688)

## Approval

- [ ] Approved

## Purpose

**#688 — `/api/health` liefert kein `commit`-Feld, daher ist der Staging-Commit-Abgleich
in `/e2e-verify` wirkungslos** (das Feld fehlt im JSON → der Poll vergleicht `undefined`
mit dem erwarteten SHA → Timeout oder fälschliches „Match").

Fix: Das Go-Binary kennt seinen Git-Commit dank Build-Zeit-Injektion via
`-ldflags "-X main.gitCommit=<sha>"`. Der `HealthHandler` gibt das injizierte Feld als
`"commit"` im JSON-Response zurück. Beide Deploy-Scripts (Prod + Staging) werden um den
`-ldflags`-Aufruf ergänzt, sodass Prod- und Staging-Binary den zugehörigen SHA kennen und
das `/e2e-verify`-Gate zuverlässig entscheiden kann, ob der erwartete Commit läuft.

## Source

- **File:** `internal/handler/proxy.go` — `HealthHandler`: zweiter Parameter `gitCommit string`;
  Response-JSON um `"commit": gitCommit` erweitert.
- **File:** `cmd/server/main.go` — `var gitCommit = "dev"` deklarieren (Build-Default);
  `gitCommit` an `HealthHandler(...)` übergeben.
- **File:** `/home/hem/henemm-infra/scripts/deploy-gregor-prod.sh` — `go build`-Zeile um
  `-ldflags "-X main.gitCommit=$(git rev-parse HEAD)"` ergänzen.
- **File:** `/home/hem/henemm-infra/scripts/auto-deploy-gregor-staging.sh` — `go build`-Zeile
  um `-ldflags "-X main.gitCommit=$(git rev-parse HEAD)"` ergänzen.
- **File:** `internal/handler/handler_test.go` — bestehende HealthHandler-Tests anpassen
  (zweiter Parameter `gitCommit` einfügen).

## Estimated Scope

- **LoC:** ~20 (Go) + ~4 (Shell-Einzeiler in 2 Scripts) + ~5 (Test-Anpassung) = ~30
- **Files:** 5
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `HealthHandler` in `internal/handler/proxy.go` | Go-Handler | Bestehender Health-Endpoint; wird um `gitCommit`-Parameter erweitert |
| `cmd/server/main.go` | Go-Entry | Deklariert `var gitCommit`; übergibt SHA an HealthHandler |
| `go build -ldflags` | Go-Build-Toolchain | Injiziert SHA zur Compile-Zeit via `-X main.gitCommit=<sha>` |
| `deploy-gregor-prod.sh` | Deploy-Script (infra) | Prod-Deploy; go build muss SHA-ldflags übergeben |
| `auto-deploy-gregor-staging.sh` | Deploy-Script (infra) | Staging-Auto-Deploy; go build muss SHA-ldflags übergeben |
| `internal/handler/handler_test.go` | Go-Test | Bestehende HealthHandler-Unit-Tests; Signatur-Anpassung nötig |

## Implementation Details

### 1) `cmd/server/main.go` — Build-Variable deklarieren

```go
// Wird bei go build mit -ldflags "-X main.gitCommit=<sha>" überschrieben.
// Default "dev" greift bei lokalem Build ohne ldflags.
var gitCommit = "dev"
```

Den `gitCommit`-Wert beim HealthHandler-Aufruf übergeben:

```go
handler.HealthHandler(w, r, gitCommit)
```

### 2) `internal/handler/proxy.go` — HealthHandler-Signatur erweitern

```go
func HealthHandler(w http.ResponseWriter, r *http.Request, gitCommit string) {
    w.Header().Set("Content-Type", "application/json")
    json.NewEncoder(w).Encode(map[string]string{
        "status": "ok",
        "commit": gitCommit,
    })
}
```

Kein bedingtes Weglassen: Das Feld ist immer vorhanden. Bei lokalem Build ohne
ldflags steht `"commit": "dev"`.

### 3) Deploy-Scripts — `-ldflags` ergänzen

In `deploy-gregor-prod.sh` (Zeile ~103) und `auto-deploy-gregor-staging.sh`
(Zeile ~27) die bestehende `go build`-Zeile jeweils um den ldflags-Parameter
erweitern:

```bash
# Vorher (Beispiel):
go build -o gregor-api ./cmd/server

# Nachher:
go build -ldflags "-X main.gitCommit=$(git rev-parse HEAD)" -o gregor-api ./cmd/server
```

`git rev-parse HEAD` läuft zur Deploy-Zeit im geklonten Repo-Verzeichnis
(beide Scripts operieren bereits auf einem `git`-geklonten Arbeitsbaum).

### 4) `internal/handler/handler_test.go` — Tests anpassen

Alle direkten `HealthHandler(w, r)`-Aufrufe in den bestehenden Tests auf
`HealthHandler(w, r, "test-sha")` ändern (zweiter Parameter wird als
Fixture-SHA mitgegeben). Keine neuen Testfälle notwendig; der neue Parameter
ist durch die bestehende Signaturänderung erzwungen.

## Expected Behavior

- **Input:** `GET /api/health`
- **Output:** HTTP 200, JSON `{"status": "ok", "commit": "<sha>"}`, wobei `<sha>`
  dem zur Build-Zeit injizierten `git rev-parse HEAD`-Wert entspricht; bei lokalem
  Build ohne ldflags ist der Wert `"dev"`.
- **Side effects:** Keine — reiner Read-Pfad; bestehende `status`-Semantik unverändert.

## Acceptance Criteria

- **AC-1:** Given ein frisch deploytes Staging- oder Prod-Binary, das via
  `deploy-gregor-prod.sh` bzw. `auto-deploy-gregor-staging.sh` gebaut wurde /
  When `GET /api/health` aufgerufen wird /
  Then enthält der JSON-Response ein `commit`-Feld mit einem nicht-leeren, nicht-`"dev"`
  Wert (kurzer oder voller Git-SHA des deployten Stands).

- **AC-2:** Given das deployete Staging-Binary und der bekannte `HEAD`-Commit des
  gepushten Stands /
  When `health.commit` mit `git rev-parse --short HEAD` (des deployten Commits) verglichen
  wird /
  Then stimmen die ersten 8 Zeichen überein — `health.commit[:8] == git rev-parse --short HEAD`
  (echter HTTP-GET gegen `https://staging.gregor20.henemm.com/api/health` nach Deploy).

- **AC-3:** Given der `/e2e-verify`-Poll in Schritt 1 liest `health.commit` /
  When der Staging-Deploy den erwarteten Commit trägt /
  Then terminiert der Poll ohne Timeout und ohne `?`-Platzhalter im Staging-Commit-Log
  (kein dauerhafter Fallback auf „unbekannt").

## Known Limitations

- Wird das Binary ohne `-ldflags` gebaut (z.B. lokaler Entwicklungs-Build), steht
  `"commit": "dev"` in der Response. Das ist beabsichtigt und kein Fehlerfall.
- Die Variable `gitCommit` liegt in `package main` — sie ist nur über `-X main.gitCommit`
  überschreibbar, nicht über ein anderes Package. Beide Deploy-Scripts müssen daher
  explizit `main.gitCommit` referenzieren.
- Werden die Deploy-Scripts außerhalb eines git-Repos ausgeführt (kein `.git`-Verzeichnis),
  schlägt `git rev-parse HEAD` fehl. Beide Scripts laufen aktuell immer im geklonten
  Arbeitsbaum; dieser Fall tritt in der Praxis nicht auf.

## Changelog

- 2026-06-09: Initial spec (Issue #688 — commit-Feld in /api/health).
