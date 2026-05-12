# Context: Bug #124 — Passwort-Reset verschickt keine E-Mail

## Request Summary

`ForgotPasswordHandler` legt den Reset-Token korrekt ab, schreibt den Reset-Link aber nur ins Server-Log — keinerlei E-Mail-Versand. User mit vergessenem Passwort bleibt ausgesperrt. Es gibt im Go-Backend gar keinen SMTP-Code; wir brauchen einen Mailer.

## Related Files

| File | Relevance |
|------|-----------|
| `internal/handler/auth.go:155-203` | **Bug-Ort.** `ForgotPasswordHandler` — Zeile 199 ist der `log.Printf`-Stub, hier MUSS der Mail-Versand rein. |
| `internal/handler/auth.go:205-...` | `ResetPasswordHandler` — bleibt unverändert, validiert nur den eingehenden Token. |
| `internal/model/user.go:7-10` | User-Modell hat `Email string` (Z.7) und `MailTo string` (Z.10), beide `omitempty`. Empfänger-Quelle für die Reset-Mail. |
| `internal/config/config.go` | `Config`-Struct hat aktuell **keine SMTP/Public-Host-Felder** — müssen ergänzt werden (`SMTPHost/Port/User/Pass`, `PublicHost`, `MailFrom`). |
| `.env` | Bestehend: `GZ_SMTP_HOST/PORT/USER/PASS` (Python nutzt sie). Werden vom Go-Backend mit-übernommen. |
| `src/outputs/email.py:1-100` | **Python-Vorbild für SMTP-Pattern.** Zeigt: STARTTLS gegen `smtp.resend.com:587`, Test-Schutz „Test-User dürfen NICHT über Resend senden". |
| `src/app/config.py:95-171` | Test-Schutz-Pattern: `is_test_mode`, `_is_test_user(user_id)` (Z.154), `for_testing()` (Z.136). Memory-Regel: Test-Mails über Gmail, nicht Resend. |
| `frontend/src/routes/forgot-password/+page.server.ts` | UI-Endpoint, ruft `/api/auth/forgot-password` auf — unverändert. |
| `frontend/src/routes/reset-password/+page.server.ts` | Validiert `?user=&token=` aus dem Mail-Link — unverändert. |

## Existing Patterns

- **Python-SMTP (`src/outputs/email.py`):** `smtplib.SMTP` mit STARTTLS, `MIMEMultipart('alternative')` für HTML+Plaintext, Settings-Validierung via `can_send_email()`. Vorlage für Go-Mailer.
- **Test-User-Schutz:** `_is_test_user(user_id)` erkennt User-IDs, die `'test'` oder `'tdd'` enthalten. Diese **MÜSSEN** Gmail-SMTP statt Resend nutzen (Memory-Regel + `src/outputs/email.py:34-41` Hard-Block).
- **Rate-Limit:** Forgot-Endpoint hat seit Issue #123 ein Rate-Limit-Middleware-Wrapping davor — Code bleibt unangetastet.
- **No-Enumeration:** Endpoint antwortet IMMER `200 {"status":"ok"}` — auch wenn User nicht existiert oder keine E-Mail hat. Diese Eigenschaft MUSS beim Mail-Versand erhalten bleiben (Mail nur abschicken wenn Empfänger vorhanden; ansonsten still loggen).

## Dependencies

- **Upstream (das wir nutzen):**
  - Go-Standard-Lib `net/smtp` für STARTTLS-SMTP (kein externer Lib nötig).
  - `Config` (erweitert um SMTP-Felder + `PublicHost`).
  - `model.User` (`Email`, `MailTo`).
- **Downstream (was uns nutzt):** Nur der Forgot-Endpoint. Kein anderer Code ruft den Mailer.

## Existing Specs

- **Neu zu schreiben:** `docs/specs/modules/password_reset_mail.md` (Issue nennt diesen Pfad explizit).
- Keine bestehende Mail-Spec für Go — Python-`email.py` ist nur Pattern-Vorbild, nicht normativ.

## Risks & Considerations

1. **Public-Host-Drift:** Reset-Link in der Mail MUSS auf den richtigen Host zeigen (`https://gregor20.henemm.com/reset-password?user=&token=`). Hardcoden ist fragil — als ENV `GZ_PUBLIC_HOST` mit Default `https://gregor20.henemm.com` einbauen.
2. **Test-User-Schutz (Memory):** Reset-Mails für Test-User (User-ID enthält `test`/`tdd`) **MÜSSEN** über Gmail-SMTP gehen, nicht Resend. Die Logik aus `src/app/config.py:_is_test_user` 1:1 in Go nachbauen — sonst frisst Resend Test-Mails (Anti-Spam) und der Test ist nicht reproduzierbar.
3. **No-Enumeration:** Wenn `user.Email == ""` UND `user.MailTo == ""` → 200 zurück geben, Mail nicht versenden, aber **Warnung loggen**. Genau wie heute, plus Warnung.
4. **Mail-Versand synchron oder Goroutine?** SMTP-Send kann 2-5s dauern. Wenn synchron, hängt der HTTP-Request. Goroutine sicherer, aber Fehler-Handling versteckt. Empfehlung: synchron + Timeout 10s — Forgot-Endpoint ist nicht performance-kritisch und User soll wissen ob's geklappt hat. (Streng genommen: no-enumeration heißt User erfährt es eh nicht; trotzdem: ein Timeout-Fehler im Server-Log ist hilfreich.)
5. **Test-Strategie:** Memory + CLAUDE.md: **KEINE Mocks.** Test schickt eine echte Mail via Gmail-SMTP und holt sie via IMAP wieder ab (Stalwart `mail.henemm.com:993`). Pattern existiert bereits — siehe Python-Tests `tests/tdd/test_html_email.py::TestRealGmailE2E`. Im Go-Bereich gibt's noch keinen IMAP-Helper; entweder Go-IMAP-Lib (`github.com/emersion/go-imap`) oder pragmatisch: das Python-IMAP-Lese-Script über `exec.Command` aufrufen.
6. **HTML- oder Plaintext-Mail?** Reset-Mails sind meist Plaintext + einfacher Link. Empfehlung: einfache **HTML mit Plaintext-Fallback** (`multipart/alternative`), damit der Link klickbar ist UND in Klartext-Clients funktioniert.
7. **Staging-IMAP-Sache offen:** Aus heutiger Session: Staging-IMAP-Pass falsch. Wenn IMAP-Verifikation im Test gegen Staging laufen soll, könnte das hinken. Lokaler Test (mit Stalwart-Postfach) ist stabil — der Mail-Verifikations-Loop dort.
8. **Spoofing nach #199-Fix:** Issue #199 hat appendUserID-Spoofing gefixt. Forgot-Endpoint nimmt aber `req.Username` aus dem Body — das ist legitim (User nicht eingeloggt). No-Enumeration sorgt dafür, dass kein Info-Leak entsteht. **Unverändert lassen.**

## Analyse-Ergebnisse (Phase 2)

### Verifiziert (bug-intake)

- `auth.go:199` ist exakt `log.Printf("Password reset link: ...")` — kein Mail-Versand.
- Komplettes `internal/`-Tree hat null Treffer für `net/smtp`, `gomail`, `SendMail`, `Resend`. Go-Backend hat kein Mail-Subsystem.
- `model/user.go:7` (`Email`) und `:10` (`MailTo`) bestätigt.
- Rate-Limit-Middleware vor `ForgotPasswordHandler` in `cmd/server/main.go:65-66` vorhanden — unangetastet lassen.

### Strategie (Plan-Agent)

1. **Mailer-Architektur:** Helper-Funktion `internal/mail/sender.go::Send(cfg, to, subject, html, plain)`. **Kein Interface** — nur 1 Versandpfad heute, kein Bedarf für Indirektion. Wenn Wetterreport-E-Mails irgendwann von Go aus gehen, lässt sich's später heben.
2. **Body-Format:** `multipart/alternative` HTML + Plaintext (analog zu `src/outputs/email.py`).
3. **Test-User-Routing:** `isTestUser(userID)` prüft `strings.Contains(strings.ToLower(userID), "test"/"tdd")`. Bei Test-User → zweite Config-Gruppe `GZ_GOOGLE_SMTP_HOST/PORT/USER/PASS`. Bei fehlender Google-Config → Versand still abbrechen + Warnung loggen.
4. **Synchron vs. Goroutine:** Goroutine mit `context.WithTimeout(10s)`. Begründung: SMTP kann 2–5s dauern, würde HTTP-Response unnötig blockieren. Rückkanal zum HTTP-Response gibt's bei No-Enumeration eh nicht. Vorher Config-Vollständigkeit prüfen, um Goroutine-Leak bei leerer ENV zu vermeiden.
5. **Reihenfolge:** Config-Erweiterung → `internal/mail/sender.go` (~80 LoC) → `internal/mail/reset.go` (~25 LoC, baut Subject/HTML/Plaintext) → Handler-Hook in `auth.go` (~15 LoC) → `main.go`-Aufruf anpassen (~3 LoC) → Integration-Test (~40 LoC, Build-Tag `integration`).

### Scope-Schätzung

- **5 Dateien** geändert/neu (`config.go`, `internal/mail/sender.go` NEU, `internal/mail/reset.go` NEU, `auth.go`, `main.go`) + 1 Test-Datei
- **~220–240 LoC** (knapp unter 250-Limit, im grünen Bereich)

### Risiken (relevant für Spec)

1. **Resend-STARTTLS-Kompatibilität:** Resend könnte auf 587 nur Implicit-TLS akzeptieren statt STARTTLS. Python's `smtplib.SMTP` funktioniert in Prod gegen `smtp.resend.com:587` → STARTTLS geht. Go's `net/smtp` ebenfalls STARTTLS-fähig → sollte 1:1 funktionieren. **Vor Implementation kurz verifizieren** mit `openssl s_client -starttls smtp -connect smtp.resend.com:587`.
2. **Bestehende User ohne `Email`/`MailTo`:** ~100% der heutigen User. Versand wird still abgebrochen — MUSS klar geloggt werden, damit Resets nicht im Produktivbetrieb verschwinden: `log.Printf("password reset: no email for user %s — token written but not sent", username)`.
3. **Goroutine-Leak bei Config-Lücke:** Wenn Prod-ENV `GZ_SMTP_HOST` fehlt, jede Forgot-Request → Goroutine, die nach 10s mit Verbindungsfehler abbricht. Lösung: Config-Vollständigkeits-Check VOR Goroutine-Start.
