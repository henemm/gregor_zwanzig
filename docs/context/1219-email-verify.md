# Kontext: #1219 Scheibe 1 — Resend-Allowlist auf E-Mail-Verifikation umstellen

**Workflow:** `1219-email-verify` · **Issue:** #1219 · **Modus:** Änderung an live-System

## Problem / Root Cause
Die live #1219-Allowlist entscheidet „echter Nutzer?" per Substring-Heuristik `test`/`tdd` im Kontonamen. Ein Konto `e2e-758` entkommt → `e2e-758@example.com` gilt als echt → Resend-Versand erlaubt. (Die am 10.07. beobachtete Leak-Mail um 12:20 UTC war jedoch **pre-fix** — Deploy war 12:26 UTC.)

## Ist-Zustand (am Code verifiziert)
- **Allowlist-Loader:** `src/output/channels/email.py::_load_resend_allowlist` (+ Guard ~Z.371); `internal/mail/sender.go::loadResendAllowlist` / `recipientBlocked` / `Send` / `SendWithFallback`.
- **Test-Heuristik (Eignungskriterium):** `src/app/config.py::is_test_user_id`; `internal/mail/sender.go::isResendAllowlistTestUser` / `IsTestUser`.
- **Konto-Verwaltung = reines Go** (`internal/handler/auth.go`, `internal/store/user.go`, `internal/model/user.go`). Python liest `user.json` nur passiv.
- **Wiederverwendbar:** `model.PasswordResetToken` + `Store.SaveResetToken/LoadResetToken/DeleteResetToken` (Token-Hash + Ablauf) — Muster für Scheibe-2-Bestätigungslink.
- **Reale Bestandskonten:** nur `henning` + `steffi` haben echte `mail_to`; kein Verifikations-Feld → Migration nötig.
- **Zweite Lücke (Planner-Befund):** `UpdateProfileHandler` erlaubt freies Ändern von `mail_to`/`email` — ein einmal gesetzter Verifiziert-Zeitstempel würde eine danach eingetragene, ungeprüfte Adresse erlauben.

## PO-Entscheidungen (2026-07-10)
1. **Verfahren:** volle Selbst-Bestätigung (Double-Opt-In). `email_verified_at`-Zeitstempel; Allowlist speist sich NUR aus verifizierten Profilen; Namens-Heuristik als Eignungskriterium entfällt.
2. **Reservierte Test-Domains (RFC 2606: `example.com/.net/.org`, `.test`, `.invalid`, `.localhost`):** IMMER vom Resend-Versand ausgeschlossen — auch bei verifizierten Konten (dauerhaftes Sicherheitsnetz).
3. **Adressänderung setzt Verifikation zurück:** schon in Scheibe 1 (Riegel gegen die zweite Lücke).
4. **Ticket:** beide Scheiben unter #1219; Issue erst schließen, wenn beides fertig.

## Schnitt
- **Scheibe 1 (dieser Workflow):** Allowlist auf `email_verified_at` umstellen (Py+Go symmetrisch) · reservierte-Domain-Hard-Drop · Adressänderung → Reset · Migration `henning`/`steffi` (Read-Modify-Write, gleicher Deploy) · symmetrische Tests.
- **Scheibe 2 (später, eigener Workflow):** Self-Service-Bestätigungsflow (Token, Endpoint, Bestätigungsmail-Sonderpfad, Frontend).

## Bug-Nachweis (für RED)
- Rot: Profil ohne `email_verified_at`, Adresse `e2e-758@example.com`, Name ohne `test`/`tdd` → aktuell zugestellt.
- Grün: gleiches Profil ohne `email_verified_at` → über Resend blockiert.
- Regression: Profil MIT `email_verified_at` + echte Domain → erlaubt.
- Hard-Drop: reservierte Test-Domain → immer blockiert, selbst mit gesetztem Flag.
