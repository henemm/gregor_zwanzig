---
entity_id: bug_469_subject_encoding
type: bugfix
created: 2026-05-30
updated: 2026-05-30
status: draft
version: "1.0"
tags: [bugfix, backend, go, mail, smtp, rfc-2047, issue-469]
---

<!-- Issue #469 — Subject-Header von Go-SMTP-Mails enthält rohes UTF-8 statt RFC-2047-Encoded-Word -->

# Issue #469 — Bug-Fix: Subject-Header ohne RFC-2047-Encoding

## Approval

- [ ] Approved

## Zweck

`internal/mail/sender.go` schreibt den `Subject:`-Header roh als UTF-8-Bytes in den
SMTP-Stream (`fmt.Sprintf("Subject: %s", msg.Subject)`). Subjects mit
Sonderzeichen wie dem Em-Dash `—` (z.B. `"Gregor 20 — Dein Einmalcode"` aus dem
Magic-Link-Flow, `"Gregor 20 — Passwort zuruecksetzen"` aus dem Reset-Flow)
verstossen damit gegen **RFC 5322 §2.2** (Header-Felder müssen US-ASCII sein) und
**RFC 2047** (Non-ASCII gehört in Encoded-Word-Form `=?charset?encoding?text?=`).
Stalwart markiert solche Subjects mit `charset="unknown-8bit"`; ältere oder
strenge Clients zeigen Mojibake (`â€"` statt `—`).

Der Fix führt einen Pure-Function-Helper `encodeMailHeader(s)` ein, der intern
`mime.QEncoding.Encode("UTF-8", s)` aufruft, und wendet ihn in `Send()` auf den
Subject an. ASCII-only-Inputs bleiben bitidentisch (stdlib-Garantie); Non-ASCII
wird als RFC-2047-Quoted-Printable Encoded-Word serialisiert. Dadurch sind
**alle** bestehenden und künftigen Subjects automatisch RFC-konform — kein
Anpassbedarf an den Mail-Buildern.

## Quelle / Source

- **Datei:** `internal/mail/sender.go`
- **Identifier:** `Send` (Zeile 57)
- **Schicht:** Go-API — Mail-Transport (`internal/mail/`)

```go
// Vorher (buggy):
headers := []string{
    fmt.Sprintf("From: %s", from),
    fmt.Sprintf("To: %s", to),
    fmt.Sprintf("Subject: %s", msg.Subject),   // ← UTF-8 roh, RFC-Verstoss
    ...
}

// Nachher (korrekt):
import "mime"

func encodeMailHeader(s string) string {
    return mime.QEncoding.Encode("UTF-8", s)
}

headers := []string{
    fmt.Sprintf("From: %s", from),
    fmt.Sprintf("To: %s", to),
    fmt.Sprintf("Subject: %s", encodeMailHeader(msg.Subject)),
    ...
}
```

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `mime.QEncoding.Encode` (Go stdlib) | Funktion | RFC-2047-Quoted-Printable Encoded-Word; ASCII-Identität garantiert |
| `mime.WordDecoder.DecodeHeader` (Go stdlib) | Funktion | Nur in Tests — Roundtrip-Assertion |
| `internal/mail/magic.go::BuildMagicLinkMail` | Caller | Produziert Subject `"Gregor 20 — Dein Einmalcode"` — unverändert, profitiert vom Fix |
| `internal/mail/reset.go::BuildResetMail` | Caller | Produziert Subject `"Gregor 20 — Passwort zuruecksetzen"` — unverändert, profitiert vom Fix |
| `internal/handler/auth.go::ForgotPasswordHandler` | Indirekter Caller | Ruft `BuildResetMail` + `Send` — keine API-Änderung |
| `internal/handler/auth_magic.go::MagicLinkRequestHandler` | Indirekter Caller | Ruft `BuildMagicLinkMail` + `Send` — keine API-Änderung |
| `internal/mail/sender_test.go` | Testdatei | Neue Unit-Tests für `encodeMailHeader` werden hier ergänzt |

## Implementation Details

```
1. internal/mail/sender.go:
   - Import "mime" ergänzen.
   - Pure Function `encodeMailHeader(s string) string` hinzufügen:
       return mime.QEncoding.Encode("UTF-8", s)
   - In Send() bei Header-Aufbau: Subject-Zeile auf encodeMailHeader(msg.Subject) umstellen.

2. internal/mail/sender_test.go:
   - Neue Tests (siehe Acceptance Criteria) — alle Pure-Function-Tests, kein SMTP.
   - Roundtrip via mime.WordDecoder mit CharsetReader-Fallback (utf-8 wird per Default unterstützt).

3. internal/mail/sender_integration_test.go (optional):
   - Bestehender Integration-Test bleibt unverändert.
   - Optional erweiterbar um decode_header(subject)-Assertion gegen Stalwart-IMAP — out of scope für diesen Bug, da Unit-Tests den Encoder vollständig abdecken.

4. NICHT betroffen:
   - From/To-Header: aktuell nur reine Adressen ohne Display-Name, kein RFC-2047-Bedarf.
   - Body-Parts: Content-Type: text/plain|html; charset=UTF-8 ist bereits korrekt deklariert (8BITMIME-OK).
   - src/outputs/email.py: Python email.mime.text setzt Subject automatisch RFC-konform.
   - internal/notify/mq.go: JSON-HTTP-Transport (Claude-MQ), kein SMTP.
```

## Expected Behavior

- **Input:** `msg.Subject` ist beliebiger UTF-8-String (z.B. `"Gregor 20 — Dein Einmalcode"`).
- **Output:** Der gesendete `Subject:`-Header ist RFC-5322-konform (reines US-ASCII). Bei ASCII-only-Input ist er bitidentisch zu vorher; bei Non-ASCII liefert er ein RFC-2047-Encoded-Word der Form `=?utf-8?q?...?=` (z.B. `=?utf-8?q?Gregor_20_=E2=80=94_Dein_Einmalcode?=`).
- **Side effects:** Keine. `Send()`-API unverändert, Mail-Builder unverändert, Caller unverändert. SMTP-Server interpretiert Encoded-Word automatisch; Empfänger-Clients zeigen den ursprünglichen Subject.

## Acceptance Criteria

- **AC-1:** Given ein ASCII-only Subject `"Hello World"` / When `encodeMailHeader("Hello World")` aufgerufen wird / Then ist die Rückgabe bitidentisch `"Hello World"` (kein Encoded-Word-Wrapping, kein Overhead).
  - Test: (populated after /tdd-red)

- **AC-2:** Given ein Subject mit Em-Dash `"Gregor 20 — Dein Einmalcode"` / When `encodeMailHeader` aufgerufen wird / Then enthält die Rückgabe ein RFC-2047-Encoded-Word mit Präfix `=?utf-8?q?` und der korrekten Quoted-Printable-Sequenz `=E2=80=94` für den Em-Dash.
  - Test: (populated after /tdd-red)

- **AC-3:** Given ein Subject mit deutschen Umlauten `"Gregor 20 — Passwortzurücksetzung"` / When `encodeMailHeader` aufgerufen wird / Then enthält die Rückgabe die Quoted-Printable-Sequenz `=C3=BC` für das `ü` und das Ergebnis ist insgesamt nur aus US-ASCII-Bytes (kein Byte ≥ 0x80).
  - Test: (populated after /tdd-red)

- **AC-4:** Given ein beliebiges Subject (ASCII oder Non-ASCII) / When die Ausgabe von `encodeMailHeader` durch `mime.WordDecoder{}.DecodeHeader` dekodiert wird / Then ist das Dekodierergebnis bitidentisch zum Original-Input (Roundtrip-Garantie für alle Mail-Clients, die RFC 2047 implementieren).
  - Test: (populated after /tdd-red)

- **AC-5:** Given ein Subject länger als 75 Zeichen mit Non-ASCII (RFC-2047-Folding-Grenze) / When `encodeMailHeader` aufgerufen wird / Then darf die Rückgabe mehrere Encoded-Word-Segmente enthalten (Header-Folding), und der Decoder-Roundtrip muss weiterhin den Original-Subject rekonstruieren (Folding-Guard für die Zukunft).
  - Test: (populated after /tdd-red)

- **AC-6:** Given die aktuellen Builder-Subjects aus `BuildMagicLinkMail("123456").Subject` und `BuildResetMail("https://example.com", "alice", "tok").Subject` / When diese durch `encodeMailHeader` geschickt werden / Then ist das Ergebnis (a) reines US-ASCII (kein Byte ≥ 0x80) und (b) durch `mime.WordDecoder.DecodeHeader` exakt zum Original-Subject dekodierbar.
  - Test: (populated after /tdd-red)

## Known Limitations

- **`From`/`To` mit Display-Namen** (z.B. `"Max Müller" <user@example.com>`) wären ebenfalls RFC-2047-pflichtig. Aktuell setzt der Code nur reine Adressen — out of scope für #469. Falls künftig Display-Namen eingeführt werden, ist `encodeMailHeader` bereits da; es muss nur auf den Display-Name-Teil angewendet werden, nicht auf die spitzklammern-eingerahmte Adresse selbst.
- **Body-Content-Transfer-Encoding** (8bit / quoted-printable / base64) wird **nicht** geändert. Bodies werden weiterhin als 8-Bit-UTF-8 nach `Content-Type: text/plain|html; charset=UTF-8` gesendet, was Resend und alle modernen MTAs (8BITMIME-Annonce) akzeptieren. Issue #469 beschränkt sich explizit auf den Subject-Header.
- **Q vs. B Encoding:** Wir wählen `mime.QEncoding` (Quoted-Printable), weil unsere Subjects 1-2 Non-ASCII-Zeichen enthalten und Q im Wire-Dump / Mail-Log lesbar bleibt. `mime.BEncoding` (Base64) wäre nur bei vielen Non-ASCII-Zeichen (CJK-Sprachen) effizienter — irrelevant für unseren deutschsprachigen Use-Case.

## Changelog

- 2026-05-30: Initial spec (Issue #469).
