---
entity_id: password_reset_mail
type: bugfix
created: 2026-05-12
updated: 2026-05-12
status: approved
version: "1.0"
tags: [backend, go, bugfix, auth, password-reset, email, smtp, issue-124]
---

# Password Reset Mail

## Approval

- [x] Approved (2026-05-12)

## Purpose

Fix `ForgotPasswordHandler` so it actually sends a reset e-mail instead of only logging the link to stdout. The handler has all the prerequisite logic (token generation, hashing, storage) but line 199 of `internal/handler/auth.go` contains a bare `log.Printf` stub — no SMTP code exists anywhere in the Go backend. This spec adds a minimal SMTP sender (`internal/mail/sender.go`) and a reset-mail builder (`internal/mail/reset.go`), wires them into the handler, and extends the config for the required credentials, while preserving the existing no-enumeration contract (`200 {"status":"ok"}` in all cases).

## Source

- **File:** `internal/handler/auth.go`
- **Identifier:** `ForgotPasswordHandler` (lines 155-203)
- **Specific Issue:** Line 199 (`log.Printf("Password reset link: ...")`) is a stub — the token is generated and stored but never delivered to the user.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `model.User` | Struct | Provides `MailTo` and `Email` fields for recipient resolution |
| `model.PasswordResetToken` | Struct | Generated and persisted before mail dispatch (unchanged) |
| `store.Store` | Type | `LoadUser`, `SaveResetToken` — both unchanged |
| `internal/config.Config` | Struct | Extended with `SMTPHost/Port/User/Pass`, `GoogleSMTPHost/Port/User/Pass`, `PublicHost` |
| `internal/mail.Send` | Function | New — SMTP helper (multipart/alternative, Resend or Gmail) |
| `internal/mail.BuildResetMail` | Function | New — constructs HTML + plaintext body for the reset link |
| `context.WithTimeout` | stdlib | Goroutine timeout (10 s) for SMTP dispatch |
| `strings` | stdlib | `isTestUser` case-insensitive substring check |

## Root Cause Analysis

### Current Implementation (BROKEN)

```go
// internal/handler/auth.go:155-203 (condensed)
func ForgotPasswordHandler(s *store.Store, bcryptCost int) http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        // ... decode req, load user, generate token, hash, SaveResetToken ...

        // STUB — token stored but never sent
        log.Printf("Password reset link: /reset-password?user=%s&token=%s", req.Username, token)

        w.Write([]byte(`{"status":"ok"}`))
    }
}
```

The entire Go backend (`internal/`, `cmd/`) contains zero SMTP code. The stub was presumably a placeholder during initial development that was never replaced.

### Fixed Implementation (EXPECTED)

```go
// internal/handler/auth.go — ForgotPasswordHandler, post-fix
func ForgotPasswordHandler(s *store.Store, bcryptCost int, cfg config.Config) http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        // ... decode req, load user, generate token, hash, SaveResetToken (all unchanged) ...

        // --- Mail dispatch ---
        // 1. Resolve recipient address: MailTo preferred, Email as fallback
        recipient := user.MailTo
        if recipient == "" {
            recipient = user.Email
        }
        if recipient == "" {
            log.Printf("password reset: no email address for user %s", req.Username)
            w.Write([]byte(`{"status":"ok"}`))
            return
        }

        // 2. Select SMTP config: test users -> Gmail, all others -> Resend
        var mailCfg mail.MailConfig
        if mail.IsTestUser(req.Username) {
            if cfg.GoogleSMTPHost == "" {
                log.Printf("password reset: Google SMTP not configured, mail not sent for test user %s", req.Username)
                w.Write([]byte(`{"status":"ok"}`))
                return
            }
            mailCfg = mail.MailConfig{
                Host: cfg.GoogleSMTPHost, Port: cfg.GoogleSMTPPort,
                User: cfg.GoogleSMTPUser, Pass: cfg.GoogleSMTPPass,
            }
        } else {
            if cfg.SMTPHost == "" {
                log.Printf("password reset: SMTP not configured, mail not sent")
                w.Write([]byte(`{"status":"ok"}`))
                return
            }
            mailCfg = mail.MailConfig{
                Host: cfg.SMTPHost, Port: cfg.SMTPPort,
                User: cfg.SMTPUser, Pass: cfg.SMTPPass,
            }
        }

        // 3. Build reset link using configured public host
        publicHost := cfg.PublicHost
        if publicHost == "" {
            publicHost = "https://gregor20.henemm.com"
        }
        resetLink := fmt.Sprintf("%s/reset-password?user=%s&token=%s", publicHost, req.Username, token)

        subject, html, plain := mail.BuildResetMail(req.Username, resetLink)

        // 4. Dispatch in goroutine with timeout — config validated before launch
        go func() {
            ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
            defer cancel()
            if err := mail.Send(ctx, mailCfg, recipient, subject, html, plain); err != nil {
                log.Printf("password reset: mail send failed for user %s: %v", req.Username, err)
            }
        }()

        w.Write([]byte(`{"status":"ok"}`))
    }
}
```

## Implementation Details

### New file: `internal/mail/sender.go` (~80 LoC)

```
MailConfig struct {
    Host string
    Port int
    User string
    Pass string
}

IsTestUser(userID string) bool
    → strings.Contains(strings.ToLower(userID), "test") || strings.Contains(strings.ToLower(userID), "tdd")

Send(ctx context.Context, cfg MailConfig, to, subject, html, plain string) error
    → Dial cfg.Host:cfg.Port via net/smtp with STARTTLS
    → Build multipart/alternative MIME message (text/plain first, text/html second)
    → smtp.SendMail with cfg.User/Pass credentials
    → Respect ctx deadline; return error on timeout or SMTP failure
```

### New file: `internal/mail/reset.go` (~25 LoC)

```
BuildResetMail(username, resetLink string) (subject, html, plain string)
    → subject: "Dein Passwort-Reset für Gregor Zwanzig"
    → html:  minimal HTML with <a href="{resetLink}">Reset-Link</a>
    → plain: "Klicke auf folgenden Link, um dein Passwort zurückzusetzen: {resetLink}"
```

### Edit: `internal/config/config.go` (~20 new LoC)

New ENV-backed fields appended to `Config` struct and `Load()`:

| Field | ENV variable | Default |
|-------|-------------|---------|
| `SMTPHost` | `GZ_SMTP_HOST` | `""` |
| `SMTPPort` | `GZ_SMTP_PORT` | `587` |
| `SMTPUser` | `GZ_SMTP_USER` | `""` |
| `SMTPPass` | `GZ_SMTP_PASS` | `""` |
| `GoogleSMTPHost` | `GZ_GOOGLE_SMTP_HOST` | `""` |
| `GoogleSMTPPort` | `GZ_GOOGLE_SMTP_PORT` | `587` |
| `GoogleSMTPUser` | `GZ_GOOGLE_SMTP_USER` | `""` |
| `GoogleSMTPPass` | `GZ_GOOGLE_SMTP_PASS` | `""` |
| `PublicHost` | `GZ_PUBLIC_HOST` | `"https://gregor20.henemm.com"` |

### Edit: `internal/handler/auth.go`

- Signature change: `ForgotPasswordHandler(s *store.Store, bcryptCost int, cfg config.Config)`
- Replace line 199 stub with dispatch logic (see Fixed Implementation above)

### Edit: `cmd/server/main.go` (~3 LoC)

- Pass `cfg` to `ForgotPasswordHandler(s, bcrypt.DefaultCost, cfg)` at line 66

### New file: `internal/mail/sender_integration_test.go` (~50 LoC)

```
//go:build integration

TestSendPasswordResetMail_Gmail
    → Load Gmail creds from ENV (GZ_GOOGLE_SMTP_*)
    → Call mail.Send() with a real reset link to henemm.gmbh@gmail.com
    → Wait 30 s
    → Connect via IMAP to Stalwart (mail.henemm.com:993)
    → Search UNSEEN subject matching "Passwort-Reset"
    → Assert mail found AND body contains "/reset-password?user=" substring
    → Mark as SEEN / delete test mail
```

Run with: `go test -tags=integration ./internal/mail/...`

## Expected Behavior

### Before Fix (broken)

- Action: `POST /api/auth/forgot-password` with a valid username
- Observed: HTTP 200 `{"status":"ok"}`, token stored in DB, reset link printed only to server stdout — user receives nothing

### After Fix (green)

- Action: same POST for a user with `MailTo` set and valid SMTP config
- Expected: HTTP 200 `{"status":"ok"}`, goroutine dispatches SMTP mail to `user.MailTo`, body contains `{PublicHost}/reset-password?user=<u>&token=<t>`

- Action: same POST, `GZ_SMTP_HOST=""` (SMTP not configured)
- Expected: HTTP 200 `{"status":"ok"}`, warning logged, no goroutine launched, no mail sent

- Action: same POST for user where both `MailTo` and `Email` are empty
- Expected: HTTP 200 `{"status":"ok"}`, warning logged, no mail sent

- **Side effects:** Token generation, hashing, and `SaveResetToken` are unchanged in all paths. No user-enumerable response code change. Rate-limit middleware at `cmd/server/main.go:64-66` is untouched.

## Acceptance Criteria

- **AC-1:** Given a user with `MailTo` set AND valid SMTP config (`GZ_SMTP_HOST` non-empty), When `POST /api/auth/forgot-password` is called with that username, Then the endpoint responds `200 {"status":"ok"}` AND an e-mail is sent to `user.MailTo` containing the reset link `{PublicHost}/reset-password?user={username}&token={token}`. (Normal user -> Resend config.)
  - Test: (populated after /tdd-red)

- **AC-2:** Given a user with `MailTo == ""` but `Email` non-empty AND valid SMTP config, When the forgot-password endpoint is called, Then the endpoint responds `200 {"status":"ok"}` AND the e-mail is sent to `user.Email` (fallback).
  - Test: (populated after /tdd-red)

- **AC-3:** Given a user with `MailTo == ""` AND `Email == ""`, When the endpoint is called, Then the endpoint responds `200 {"status":"ok"}` AND no e-mail is sent AND the server log contains `"password reset: no email address for user <username>"`.
  - Test: (populated after /tdd-red)

- **AC-4:** Given a user ID containing the substring `"test"` OR `"tdd"` (case-insensitive), When `mail.IsTestUser(userID)` is called, Then it returns `true`; all other IDs return `false`. When such a user triggers a reset, the mail is dispatched via `GZ_GOOGLE_SMTP_*` config, never via `GZ_SMTP_*`.
  - Test: (populated after /tdd-red)

- **AC-5:** Given `GZ_PUBLIC_HOST=https://example.com` in the environment, When a reset mail is built via `mail.BuildResetMail`, Then the resulting body contains exactly `https://example.com/reset-password?user=<u>&token=<t>` with no hardcoded host.
  - Test: (populated after /tdd-red)

- **AC-6:** Given `GZ_SMTP_HOST=""` (SMTP not configured), When the forgot-password endpoint is called for a user with a valid e-mail address, Then the endpoint responds `200 {"status":"ok"}`, no goroutine is started, and the server log contains `"password reset: SMTP not configured, mail not sent"`.
  - Test: (populated after /tdd-red)

- **AC-7:** Given the integration test (`go test -tags=integration ./internal/mail/...`) with valid `GZ_GOOGLE_SMTP_*` and IMAP credentials set, When the test sends a real reset mail via Gmail and waits 30 s, Then the mail is retrievable via IMAP AND contains the expected `/reset-password?user=` substring in the body.
  - Test: (populated after /tdd-red)

## Known Limitations

- **Existing users without e-mail address:** At current data state the majority of existing users have neither `MailTo` nor `Email` set. Reset mails will be silently skipped (AC-3) until a follow-up UI for user e-mail management is built (not in scope of Issue #124).
- **Token cleanup:** Expired reset tokens are not garbage-collected. A separate hygiene issue is needed.
- **Integration test vs. Stalwart-Staging:** Staging Stalwart has open IMAP auth issues (MQ #18394 to infra). The integration test must target the production Stalwart inbox (`mail.henemm.com:993`) or a local mail server with valid credentials. This is documented; the test is gated behind `//go:build integration` to avoid blocking CI.
- **Single SMTP path:** There is deliberately no interface/mock abstraction for the mailer. If Go-side weather-report mails are added later, `mail.Send` can be reused directly — no refactor needed at that point.
- **`IsTestUser` substring match:** `IsTestUser("contest") == true`, `IsTestUser("tdd-prod-user") == true` (false-positive for strings that contain "test" or "tdd"). Deliberate decision — mirrors the Python behaviour (`src/app/config.py:_is_test_user`). If a prod-user with "test"/"tdd" in their name is ever registered, their reset mail goes through Gmail instead of Resend. Acceptable risk: only a few characters, trivial to avoid in setup. Guarded by `TestIsTestUser_Boundary` in `internal/mail/sender_test.go`.

## Files to Modify

| Path | Change type | Approx. LoC delta |
|------|-------------|-------------------|
| `internal/handler/auth.go` | Edit (lines 155-203) | +30 |
| `internal/config/config.go` | Edit (append fields + Load) | +20 |
| `internal/mail/sender.go` | New | +80 |
| `internal/mail/reset.go` | New | +25 |
| `cmd/server/main.go` | Edit (line 66) | +3 |
| `internal/mail/sender_integration_test.go` | New | +50 |

## Files NOT to Modify

- `internal/store/store.go` — `SaveResetToken`, `LoadUser` unchanged
- `internal/model/` — `User`, `PasswordResetToken` structs unchanged
- `cmd/server/main.go:64-65` — Rate-limit middleware untouched

## Changelog

- 2026-05-12: Initial spec created for Issue #124 (password reset stub → real SMTP dispatch)
