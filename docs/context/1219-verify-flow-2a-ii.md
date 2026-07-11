# Context: #1219 Scheibe 2a-ii — Einlösung des Bestätigungslinks (Double-Opt-In Backend)

**Workflow:** `1219-verify-flow-2a-ii` · **Issue:** #1219 (bleibt offen) · **Modus:** Änderung/Erweiterung

## Request Summary
Scheibe 2a-i (live, `e677b23e`) baut den **Versand-Pfad**: Adressänderung erzeugt einen 24h-Verifikations-Token (`data/users/<id>/email_verification.json`) und schickt eine Bestätigungsmail mit Link auf `{publicHost}/verify-email?user=<id>&token=<t>`. Diese Scheibe baut den **Einlöse-Pfad**: einen `VerifyEmailHandler` (POST), der den Token prüft, `email_verified_at` per Read-Modify-Write setzt und den Token entwertet — plus Public-Route-Freischaltung und Rate-Limiter. Erst damit ist der Self-Service-Double-Opt-In end-to-end nutzbar.

## Ausgangslage (2a-i live)
- `model.EmailVerificationToken{TokenHash, ExpiresAt}` existiert (`internal/model/user.go:42`).
- Token-Store existiert: `SaveVerificationToken`/`LoadVerificationToken`/`DeleteVerificationToken` (`internal/store/user.go:145,161`).
- `model.User.EmailVerifiedAt *time.Time` (`internal/model/user.go:32`) — Eignungskriterium der Resend-Allowlist (Scheibe 1).
- Der Mail-Link zeigt bereits auf `/verify-email?user=…&token=…` — bis jetzt läuft ein Klick ins Leere (kein Endpoint).

## Related Files
| File | Relevance |
|------|-----------|
| `internal/handler/auth.go:272-339` | `ResetPasswordHandler` — strukturelles Vorbild: Token laden → Ablauf prüfen → `bcrypt.CompareHashAndPassword` → User-RMW → Token löschen. Public, `userId` aus Request-Body (`req.Username`), NICHT aus Auth-Kontext. |
| `internal/store/user.go:145-170` | `LoadVerificationToken`/`DeleteVerificationToken` — bereits vorhanden, hier konsumiert. |
| `internal/model/user.go:32,42` | `EmailVerifiedAt`, `EmailVerificationToken`. |
| `internal/middleware/auth.go:34-46` | Public-Route-Allowlist — `/api/auth/verify-email` muss ergänzt werden (analog `reset-password`). |
| `internal/router/router.go:56-59` | Reset-Route + `NewIPRateLimiter(10, time.Hour)` — Vorbild für die neue Route + Limiter. |
| `internal/middleware/ratelimit.go` | `IPRateLimiter` / `NewIPRateLimiter(burst, window)` / `.Middleware()`. |

## Existing Patterns
- **Einlöse-Handler (Reset):** Body dekodieren → `LoadResetToken(username)` (nil → `400 invalid token`) → `time.Now().After(ExpiresAt)` (→ `400 token expired`) → `bcrypt.CompareHashAndPassword(hash, klartext)` (→ `400 invalid token`) → `LoadUser` → Feld setzen → `SaveUser` → `DeleteResetToken`. JSON-Antwort `{"status":"ok"}`.
- **RMW (Pflicht, CLAUDE.md):** `LoadUser` liefert das vollständige Objekt, nur `EmailVerifiedAt` wird gesetzt, `SaveUser(*user)` schreibt zurück — keine client-unbekannten Felder gehen verloren.
- **Public-Route:** exakte Pfad-Gleichheit in `AuthMiddleware` freischalten (wie `reset-password`), sonst 401 vor dem Handler.
- **Rate-Limit:** eigener `IPRateLimiter` pro Endpoint, per `.Middleware(handler).ServeHTTP` verdrahtet.

## Design-Entscheidungen (aus 2a-i PO-Vorgaben + Analyse)
1. **POST, kein GET-Auto-Confirm** (PO 2026-07-10): Der Handler ist `POST /api/auth/verify-email`, Body `{user, token}`. Der Mail-Link zeigt auf die Frontend-Seite (Scheibe 2b), die den POST auslöst — kein Prefetch/Scanner-Klick verifiziert versehentlich.
2. **Public + tokenbasiert:** `userId` kommt aus dem Request (der Klicker ist evtl. nicht eingeloggt), Sicherheit trägt allein der bcrypt-Token-Vergleich gegen den gehashten Store-Wert — identisch zu Reset.
3. **`email_verified_at` = Zeitpunkt der Einlösung** (`time.Now()` UTC), per RMW.
4. **Token einmalig:** nach Erfolg `DeleteVerificationToken` → derselbe Link ist nicht wiederverwendbar.
5. **Idempotenz-/Fehlerprofil wie Reset:** abgelaufener/fehlender/falscher Token → `400`, keine Preisgabe, ob User existiert.

## Dependencies
- **Upstream (konsumiert):** `store.LoadVerificationToken/DeleteVerificationToken`, `store.LoadUser/SaveUser`, `bcrypt`, `middleware`-Allowlist, `IPRateLimiter`.
- **Downstream (nutzt uns):** Scheibe 2b (Frontend-Bestätigungsseite ruft diesen POST). Resend-Allowlist (Scheibe 1) profitiert automatisch, sobald `email_verified_at` gesetzt ist.

## Existing Specs
- `docs/specs/modules/fix_1219_verify_flow_2a.md` — Spec 2a-i, Sektion „Schnitt": 2a-ii = `VerifyEmailHandler` (POST, RMW + Token-Entwertung) + Public-Allowlist + Route/Rate-Limiter.
- `docs/specs/modules/fix_1219_email_verify.md` — Scheibe 1 (Allowlist-Eignungskriterium).

## Risks & Considerations
- **Public-Endpoint-Missbrauch:** Rate-Limiter zwingend (Token-Rateversuche drosseln). Reset nutzt `(10, time.Hour)` — übernehmen.
- **Kein Cross-User-Leak:** `userId` streng aus Request, Token-Datei liegt pro Nutzerverzeichnis; ein Token für User A darf User B nie verifizieren (bcrypt-Vergleich gegen As Store).
- **RMW-Pflicht:** niemals ein frisch konstruiertes `User`-Objekt speichern — immer `LoadUser` → mutieren → `SaveUser`.
- **Timing:** `ExpiresAt`-Ablaufprüfung vor bcrypt (billiger Reject) — wie Reset.
- **Frontend-Seite (2b) fehlt noch:** der POST ist per `curl`/Test triggerbar, aber die klickbare Seite kommt separat — Known Limitation, kein Blocker für den Backend-Slice.
