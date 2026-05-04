---
entity_id: forgot_reset_rate_limit
type: bugfix
created: 2026-05-04
updated: 2026-05-04
status: draft
version: "1.0"
tags: [security, bugfix, go-api, rate-limit, auth, issue-123, follow-up-117-119]
---

# Forgot/Reset Password Rate-Limit (Issue #123)

## Approval

- [ ] Approved

## Purpose

Folge-Story zu #117 (Register, 5/h) und #119 (Login, 30/h). Die noch offenen Auth-Endpoints sind:

- `/api/auth/forgot-password` — startet den Reset-Flow, sendet Email mit Token
- `/api/auth/reset-password` — verifiziert Token, setzt neues Passwort

Ohne Limit: Email-Bombing über forgot-password (User-Postfach füllen, Mail-Provider blockiert Domain) und theoretisches Token-Brute-Force über reset-password.

## Source

- **File:** `cmd/server/main.go`
- **Identifier:** Zeilen mit `r.Post("/api/auth/forgot-password", ...)` und `r.Post("/api/auth/reset-password", ...)`

## Dependencies

| Komponente | Typ | Zweck |
|---|---|---|
| `internal/middleware.IPRateLimiter` | bestehend | wiederverwendet, kein neuer Code |
| `golang.org/x/time/rate` | bestehende Dep | indirect |

## Implementation Strategy

### `cmd/server/main.go`

Vorher:
```go
r.Post("/api/auth/forgot-password", handler.ForgotPasswordHandler(s, bcrypt.DefaultCost))
r.Post("/api/auth/reset-password", handler.ResetPasswordHandler(s, bcrypt.DefaultCost))
```

Nachher:
```go
forgotLimiter := authmw.NewIPRateLimiter(5, time.Hour)
r.Post("/api/auth/forgot-password",
    forgotLimiter.Middleware(handler.ForgotPasswordHandler(s, bcrypt.DefaultCost)).ServeHTTP,
)
resetLimiter := authmw.NewIPRateLimiter(10, time.Hour)
r.Post("/api/auth/reset-password",
    resetLimiter.Middleware(handler.ResetPasswordHandler(s, bcrypt.DefaultCost)).ServeHTTP,
)
```

### Limit-Begründung

| Endpoint | Limit | Begründung |
|---|---|---|
| forgot-password | 5/h/IP | wie Register — Spam-Schutz, normaler User triggert max 1× pro Vergessen |
| reset-password | 10/h/IP | mittelmäßig — legitimer User probiert ggf. 2-3× (Token im Spam? Browser-Sessions?) |

### Tests

Keine neuen Unit-Tests nötig — `IPRateLimiter`-Logik ist in `internal/middleware/ratelimit_test.go` schon abgedeckt. Live-Verifikation auf Staging via Black-Box.

## Expected Behavior

### forgot-password

- **1.–5. Versuch (gleiche IP, < 1h):** HTTP 200 oder 4xx je nach Existenz des Users
- **6. Versuch:** HTTP 429 + Retry-After
- **andere IP:** weiter erlaubt

### reset-password

- **1.–10. Versuch (gleiche IP, < 1h):** Standard-Reset-Antworten
- **11. Versuch:** HTTP 429 + Retry-After

## Acceptance Criteria

- [ ] Forgot: 5 OK / 6 → 429 (gleiche IP)
- [ ] Reset: 10 OK / 11 → 429 (gleiche IP)
- [ ] Andere IP: weiter erlaubt
- [ ] Register (5/h), Login (30/h) unverändert
- [ ] `go build`, `go vet`, `go test ./...` clean

## Files to Modify

| Datei | Δ LoC |
|---|---|
| `cmd/server/main.go` | +8 / -2 |

## Bewusst NICHT im Scope

- Pro-Username-Limits (Account-Lockout-Risiko)
- Captcha
- E-Mail-Throttling im Mailer (separate Schicht)

## Risk Analysis

- Service-Restart resettet Limiter — gleicher Trade-off wie #117/#119
- Reset-Token sind UUIDv4 → 122 Bit Entropie, brute-force ohne Limit nicht praktikabel; Limit ist defense-in-depth

## Bezug

- GitHub Issue #123
- Folge zu #117 (Register), #119 (Login)

## Changelog

- 2026-05-04: Initial spec
