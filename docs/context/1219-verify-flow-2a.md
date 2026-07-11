# Kontext: #1219 Scheibe 2a-i — Versand des Bestätigungslinks (Double-Opt-In Backend)

**Workflow:** `1219-verify-flow-2a` · **Issue:** #1219 (bleibt offen) · **Modus:** Änderung/Erweiterung

## Ausgangslage (Scheibe 1 live)
`email_verified_at` (in `internal/model/user.go`) ist Eignungskriterium der Resend-Allowlist. Gesetzt wird es heute NUR per Migrationsscript. Scheibe 2 schafft den Self-Service-Weg. `UpdateProfileHandler` (`internal/handler/auth.go:445-514`) nullt `email_verified_at` bereits bei Adressänderung — natürlicher Auslösepunkt.

## PO-Entscheidungen (2026-07-10)
1. **Bestätigt wird nur `mail_to`** (Rückfall auf `email`, wenn `mail_to` leer) — die tatsächlich für den Versand genutzte Empfänger-Adresse.
2. **Link-Gültigkeit: 24 Stunden.**
3. **Bestätigungsseite mit Knopf** (kein Ein-Klick-Auto-Confirm) → Verify-Endpoint (2a-ii) ist **POST**, nicht GET-Auto-Confirm; der Mail-Link zeigt auf die Frontend-Seite (2b).

## Wiederverwendung (am Code geprüft)
- Token-Muster 1:1 von `model.PasswordResetToken` + `store.SaveResetToken/LoadResetToken/DeleteResetToken` (`internal/store/user.go:92-127`, Datei `data/users/<id>/password_reset.json`) → neue `email_verification.json`. Neuer Link überschreibt alten automatisch (macht alten Link bei zweiter Adressänderung wertlos).
- Mail-Versand-Muster: `ForgotPasswordHandler` (`auth.go:167-270`): Token → Test-User→Gmail / echte User→Resend → Goroutine+20s-Timeout → `SendWithFallback`. `BuildResetMail` (`internal/mail/reset.go`) → neue `BuildVerificationMail`.

## Schnitt (2a in zwei Slices, LoC-Limit)
- **2a-i (dieser Workflow, Versand-Pfad):** Token-Typ+Store; `internal/mail/verify.go` `BuildVerificationMail`; `sender.go` Refactor (Low-Level-Send auslagern) + `recipientBlockedForVerification` + `SendVerificationMail`; `UpdateProfileHandler` erweitert (Token erzeugen + Versand-Goroutine); Router-Signatur (`cfg config.Config`).
- **2a-ii (folgt, Bestätigungs-Pfad):** `VerifyEmailHandler` (POST, setzt `email_verified_at` per RMW + entwertet Token); Public-Allowlist-Eintrag (`internal/middleware/auth.go:34-46`); Route + Rate-Limiter.

## Sicherheits-Sonderpfad (kritisch, 2a-i)
Die Bestätigungsmail ist die EINZIGE an eine unverifizierte Adresse erlaubte Mail. `recipientBlockedForVerification(host, to)`: wie `recipientBlocked` (`sender.go:312-348`), aber OHNE Allowlist-Lookup — dafür (a) rohes Test-Postfach-Fangnetz (`rawContainsTestMailbox`), (b) genau EIN Empfänger (kein Adresslisten-Trick), (c) `isReservedTestDomain` (reservierte Domains bekommen NICHT einmal die Bestätigungsmail), plus `resendBlocked` (#1122). `SendVerificationMail` hat GENAU EINEN Aufrufer (Versand-Pfad in `UpdateProfileHandler`, `to` = die vom eingeloggten Nutzer selbst gesetzte Adresse). Kein generischer „beliebige Adresse senden"-Pfad. Test-User (`IsTestUser`) laufen über Gmail, nie über den Resend-Sonderpfad.

## Multi-User
`userId` aus `middleware.UserIDFromContext` (authentifizierter Endpoint), kein `"default"`-Fallback. RMW bei allen `user.json`/Token-Schreibpfaden.

## Bug-/Verhaltens-Nachweis (RED, 2a-i)
- Adressänderung (`mail_to`) → Token erzeugt + Bestätigungsmail an die NEUE (unverifizierte) Adresse.
- No-Op-Update → kein Token, kein Versand (Anschluss AC-6 Scheibe 1).
- Reservierte Test-Domain → bekommt NICHT einmal die Bestätigungsmail (Bootstrap-Sicherung).
- `resendBlocked` (#1122) + Test-Postfach-Fangnetz greifen auch auf dem Sonderpfad.
- Test-User → Gmail, nie Resend-Sonderpfad.
- Genau ein Empfänger (kein Listen-/Trennzeichen-Trick).
