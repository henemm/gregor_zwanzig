# Context: Issue #469 — Subject-Header ohne RFC-2047-Encoding

## Request Summary

Go-SMTP-Sender schreibt UTF-8-Sonderzeichen (z.B. Em-Dash `—`) **roh** in den `Subject:`-Header. Das verstösst gegen RFC 5322 (Header = ASCII) und RFC 2047 (Encoded-Word für Non-ASCII). Folge: Stalwart markiert den Subject mit `charset="unknown-8bit"`; ältere/strenge Clients zeigen Mojibake (`â€"` statt `—`). Fix: `mime.QEncoding.Encode("UTF-8", subject)` in `internal/mail/sender.go` zentralisieren — wirkt automatisch für **alle** aktuellen und künftigen Subjects.

## Related Files

| Datei | Relevanz |
|------|-----------|
| `internal/mail/sender.go:57` | **ROOT CAUSE** — `fmt.Sprintf("Subject: %s", msg.Subject)` ohne Encoding. Einzige Änderung im Produktivcode. |
| `internal/mail/magic.go:24` | Subject `"Gregor 20 — Dein Einmalcode"` enthält `—` (betroffen). Read-only — keine Änderung nötig. |
| `internal/mail/reset.go:34` | Subject `"Gregor 20 — Passwort zuruecksetzen"` enthält `—` (betroffen). Read-only — keine Änderung nötig. |
| `internal/mail/sender_test.go` | Unit-Tests für `IsTestUser` + `BuildResetMail`. **Hier neue RED-Tests für Subject-Encoding ergänzen.** |
| `internal/mail/sender_integration_test.go` | `//go:build integration` — IMAP-Roundtrip via Stalwart. Optional erweitern um `decode_header(subject)`-Assertion. |
| `internal/handler/auth.go:239,244` | Ruft `BuildResetMail` + `Send` — bleibt unverändert. |
| `internal/handler/auth_magic.go:107,110` | Ruft `BuildMagicLinkMail` + `Send` — bleibt unverändert. |

**Nicht betroffen:**

- `internal/notify/mq.go` — HTTP-Claude-MQ, kein SMTP. `Subject` ist JSON-Feld, keine RFC-Header-Encoding.
- `src/outputs/email.py` — Python verwendet `email.mime.text.MIMEText`; `msg["Subject"] = subject` enkodiert automatisch korrekt (stdlib-Header-Policy).

## Existing Patterns

- **Zentrale Mail-Builder** (`Build*Mail` → `Mail{Subject, PlainBody, HTMLBody}`) trennen Inhalt von Transport. `Send` ist die einzige Stelle, wo Header gerendert werden — **deshalb ist Subject-Encoding genau dort richtig aufgehoben** (DRY, künftige Subjects automatisch sicher).
- **stdlib-first** im Mail-Subsystem (`net/smtp`, `mime`) — kein externes Encoding-Package nötig. `mime.QEncoding.Encode` liefert RFC-2047-Encoded-Words; bei reinem ASCII bleibt der Input unverändert (kein Overhead).
- **Mock-freie Tests:** Unit-Tests testen Pure Functions ohne Netzwerk; Integration-Tests (`//go:build integration`) machen echten Gmail-SMTP-Roundtrip + Stalwart-IMAP-Verifikation. Folgt der projektweiten "KEINE MOCKED TESTS!"-Regel.

## Dependencies

- **Upstream (was wir nutzen):** Go stdlib `mime` (Quoted-Printable Encoded-Word, RFC 2047).
- **Downstream (was uns nutzt):** `internal/handler/auth.go::ForgotPasswordHandler`, `internal/handler/auth_magic.go::MagicLinkRequestHandler` — beide rufen `mail.Send`. Signatur ändert sich nicht, kein Anpassbedarf.
- **Tests:** `sender_test.go` (Unit), `sender_integration_test.go` (Gmail-Roundtrip) — keine API-Änderung der getesteten Funktionen.

## Existing Specs

- `docs/specs/modules/password_reset_mail.md` — definiert den Sender (`internal/mail/sender.go`) und den Reset-Mail-Builder. Status `approved`, version 1.0. Diese Bugfix-Spec ist **additiv** dazu (kein Re-Approval nötig, eigene Spec unter `docs/specs/modules/bug_469_subject_encoding.md`).
- `docs/specs/modules/issue_449_magic_link.md` — definiert den Magic-Link-Builder, der den ersten betroffenen Em-Dash-Subject eingeführt hat. Wird durch den Fix sauberer, ohne dass die Spec ändert (Subject-Inhalt bleibt identisch, nur On-Wire-Encoding wird korrekt).
- `docs/specs/modules/smtp_mailer.md` — älterer SMTP-Mailer-Kontext (Python-Seite, nicht direkt betroffen).

## Risks & Considerations

- **Regression auf reine ASCII-Subjects:** `mime.QEncoding.Encode` lässt ASCII-only-Input bitidentisch durch (Go-Doku-Garantie). Trotzdem Unit-Test: ASCII-Subject → unverändert.
- **Header-Faltung (Folding) bei langen Subjects:** Encoded-Words sind auf 75 Zeichen pro Zeile limitiert (RFC 2047 §2). `mime.QEncoding.Encode` fügt bei Bedarf `\r\n ` ein. Unsere Subjects sind <50 Zeichen, also kein praktisches Problem — aber Test sollte trotzdem mit einem >75-Zeichen-Subject prüfen, dass `Send` nicht crasht.
- **Content-Type-Header der Body-Parts** ist **nicht** betroffen — Bodies sind als `Content-Type: text/plain; charset=UTF-8` korrekt deklariert; UTF-8 im Body ist RFC-konform (8BITMIME). Issue beschränkt sich auf den Subject-Header.
- **`From`/`To`-Header** mit Display-Namen (Beispiel: `"Max Müller" <user@example.com>`) wären theoretisch ebenfalls 2047-pflichtig. Aktuell schreibt der Code nur reine Adressen → out of scope für #469, aber bei künftigem Display-Name-Support gleicher Fix-Punkt.
- **Integration-Test-Assertion:** Issue empfiehlt `decode_header(subject) == original`. In Go gibt es `mime.WordDecoder.DecodeHeader` — ideal für IMAP-Roundtrip-Assertion. Optional, da Unit-Test des Encoders bereits ausreicht.
- **LoC-Budget:** Issue schätzt 10 LoC Produktivcode + 30 LoC Tests = ~40 LoC, weit unter 250-Limit.

## Next Step

Phase 2 (`/2-analyse`) — RFC-2047 / `mime.QEncoding` evaluieren, Test-Plan (ASCII / Em-Dash / Umlaute / Long-Subject) festlegen, Aufwand bestätigen.
