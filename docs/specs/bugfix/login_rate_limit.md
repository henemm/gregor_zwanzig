---
entity_id: login_rate_limit
type: bugfix
created: 2026-05-04
updated: 2026-05-04
status: draft
version: "1.0"
tags: [security, bugfix, go-api, rate-limit, auth, issue-119, follow-up-117]
---

# Login Rate-Limit (Issue #119)

## Approval

- [ ] Approved

## Purpose

Folge-Story zu Issue #117. `/api/auth/register` ist seit gestern rate-limitiert (5/h/IP). `/api/auth/login` aber nicht — ein Brute-Force-Angreifer kann beliebig viele Versuche pro IP unternehmen. bcrypt-Cost (10) bremst nur passiv.

Diese Spec ergänzt einen App-Layer Rate-Limiter auf `/api/auth/login` durch Wiederverwendung der bereits vorhandenen `IPRateLimiter`-Middleware aus Issue #117. Defense-in-Depth zur Nginx-Seite (`limit_req` + fail2ban) die infra eingerichtet hat.

## Source

- **File:** `cmd/server/main.go`
- **Identifier:** `r.Post("/api/auth/login", ...)` Zeile 56 (aktueller Stand nach Issue #116/#117)

## Dependencies

| Komponente | Typ | Zweck |
|---|---|---|
| `internal/middleware.IPRateLimiter` | bestehend | wiederverwendet, kein neuer Code |
| `golang.org/x/time/rate` | bestehende Dep | indirect über IPRateLimiter |
| `chi.Router.Post` | external | Routing |

## Implementation Strategy

### `cmd/server/main.go`

Vorher:
```go
r.Post("/api/auth/login", handler.LoginHandler(s, cfg.SessionSecret))
```

Nachher:
```go
loginLimiter := authmw.NewIPRateLimiter(30, time.Hour)
r.Post("/api/auth/login",
    loginLimiter.Middleware(handler.LoginHandler(s, cfg.SessionSecret)).ServeHTTP,
)
```

Limit-Begründung: 30 Versuche/h ist großzügig genug, dass normale User (1–3 Logins pro Tag) nie betroffen sind. Brute-Force-Angreifer ist nach 30 Versuchen 12 Min gesperrt (Refill-Rate 1 Token / 120s aus Bucket=30 in 3600s) — bei 100k passwords/h theoretisch ohne Limiter geht das nicht mehr.

Pro-IP statt Pro-Username: schützt vor Account-Lockout-Attacks (Angreifer kann nicht gezielt einen User aussperren).

### Tests

Neu in `internal/scheduler/scheduler_test.go` — Moment, ist Wrong File. Korrekt: Da der Limiter im Handler-Layer hängt, werden Integration-Tests via main.go-Setup gemacht.

Kein neuer Test nötig: Die `IPRateLimiter`-Tests aus Issue #117 (`TestIPRateLimiter_AllowsBurst`, `_BlocksSixth`, `_DifferentIPsIndependent`, `_PrefersXRealIP`) decken die Logik ab. Live-Verifikation auf Production prüft die Wiring.

Optional: Ein Smoke-Test in Hauptrepo `cmd/server/main_test.go`, der prüft dass `/api/auth/login` mit gleichem IP nach 30 Calls 429 zurückgibt. Nice-to-have, nicht zwingend.

## Expected Behavior

### Vor Fix

- **Input:** `for i in {1..1000}; do curl -X POST .../api/auth/login -d '{...}'; done`
- **Output:** Bis 1000 HTTP 401 (oder 200), kein Limit
- **Side effects:** bcrypt-Cost bremst, aber kein hartes Stop

### Nach Fix

- **Input (1.–30. Versuch, gleiche IP):** Standard-Login-Antworten (200 OK / 401 Unauthorized)
- **Input (31. Versuch, gleiche IP):** HTTP 429 + Header `Retry-After: 120`, Body `{"error":"rate_limit_exceeded"}`
- **Input (Versuch aus anderer IP):** weiter normal

## Acceptance Criteria

- [ ] 30 sequentielle Login-Versuche aus gleicher IP innerhalb 1h: alle 200 oder 401
- [ ] 31. Versuch aus gleicher IP: HTTP 429
- [ ] Andere IP: weiter erlaubt
- [ ] `/api/auth/register` weiter mit 5/h-Limit (unverändert)
- [ ] `go build`, `go vet`, `go test ./...` clean

## Files to Modify

| Datei | Δ LoC |
|---|---|
| `cmd/server/main.go` | +4 / -1 |

Effort: trivial.

## Bewusst NICHT im Scope

- Forgot-Password / Reset-Password Limiter (eigene Stories falls gewünscht)
- Pro-Username Account-Lockout (Architektur-Diskussion: Ist nicht im Scope dieser Story)
- Failed-only-Counter (aktuell: alle Versuche zählen, hohes Limit kompensiert)

## Risk Analysis

- **Service-Restart resettet Limiter** → akzeptiert, gleicher Risk-Trade-off wie Issue #117
- **Header-Spoofing nicht möglich** → Nginx schreibt X-Real-IP, bestätigt durch Issue #117 Validator
- **Limit zu eng?** → 30/h ist ~1/2min. Auch ein paranoider User mit Mehrgeräte-Setup trifft das nicht.

## Bezug

- GitHub Issue #119
- Folge zu Issue #117 (Register Rate-Limit)
- MQ #14469 von infra (Nginx-Layer schon erledigt)

## Changelog

- 2026-05-04: Initial spec basierend auf Issue #119
