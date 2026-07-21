---
entity_id: issue_1147_resend_recipient_invariant
type: module
created: 2026-07-08
updated: 2026-07-08
status: draft
version: "1.0"
tags: [mail, guard, resend, invariant, issue-1147]
issue: 1147
---

<!-- Issue #1147 — Strukturell: Fix-Verifikation versendet selbst Test-Mails über Resend (11. Vorfall) -->

# Issue 1147 — Resend-Empfänger-Invariante (dritte Guard-Linie)

## Approval

- [ ] Approved

## Purpose

Eine dritte, **empfängerseitige** Guard-Linie einführen, die einen Mail-Versand
über einen Resend-Host hart abbricht, sobald die finale Empfängerliste ein
Test-Postfach (`gregor-test@henemm.com`, `gregor-staging@henemm.com`) enthält —
unabhängig davon, ob `user_id`, `GZ_ENV`, `is_test_mode`, `pytest`-Kontext oder
`GZ_RESEND_ALLOWED` etwas anderes signalisieren. Alle bisherigen Guards
(#1122, #924, #879) klassifizieren „Test" **absender-/prozessseitig** — sie
lassen sich mit einem Kunst-User + internem Prod-Port umgehen (genau das war
der 11. Vorfall am 2026-07-08). Diese Invariante prüft stattdessen das, was
am Ende tatsächlich zählt: **wer die Mail bekommt**.

## Source

- **File:** `src/output/channels/email.py` — `EmailOutput.send()`, Guard nach Z.180 (Empfängerliste `recipients` final aufgelöst, VOR MIME-Bau/Dial); neue Modul-Konstante `TEST_MAILBOXES`
- **File:** `internal/mail/sender.go` — `Send()`, Guard am Eintritt (Z.72-75), analog zu `resendBlocked()`; neue Funktion `recipientBlocked(host, to string) error`
- **Identifier:** Python `EmailOutput.send`; Go `mail.Send`, `mail.recipientBlocked`

> **Schicht-Hinweis:** Beide betroffenen Dateien sind Server-seitige Sendepfade
> (Python-Core `src/output/channels/`, Go-API `internal/mail/`). Kein
> Frontend-Code betroffen. `src/app/core.py::send_mail` (toter smtplib-Pfad,
> kein Produktions-Aufrufer) ist NICHT Teil dieser Spec — Cleanup-Kandidat,
> siehe Known Limitations.

## Estimated Scope

- **LoC:** Produktivcode ~35-55, Tests ~160-240
- **Files:** 5 (2 Produktiv, 2 Test, 1 Doku)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `output.channels.base.OutputConfigError` | intern (Python) | Fehlertyp für den harten Abbruch, konsistent mit bestehenden Guards (#1122, #924, #879) |
| `internal/mail.resendBlocked` (#1122) | intern (Go) | Bestehende erste Linie, bleibt unverändert — neue Linie ergänzt, ersetzt nicht |
| `internal/mail.SendWithFallback` | intern (Go) | Lenkt Nicht-535-Fehler automatisch auf `fallbackCfg` (Stalwart) um — die neue Invariante profitiert davon ohne eigene Umlenk-Logik |
| `docs/reference/operations_playbook.md` | Doku | Ziel für Baustein B (passives Prüfrezept) |

## Implementation Details

### Python (`src/output/channels/email.py`)

Neue Modul-Konstante, direkt nach den Imports:

```python
TEST_MAILBOXES = frozenset({"gregor-test@henemm.com", "gregor-staging@henemm.com"})
```

Guard in `send()`, unmittelbar nach Zeile 180 (`recipients` ist final
aufgelöst — deckt sowohl `settings.mail_to` als auch den `to=`-Parameter-
Override ab, der die Init-Guards umgeht), VOR `build_mime_message()` und vor
jedem `smtplib`-Dial:

```python
if "resend" in (self._host or "").lower():
    hit = [r for r in recipients if _extract_addr(r).lower() in TEST_MAILBOXES]
    if hit:
        raise OutputConfigError(
            "email",
            f"Test-Postfach {hit!r} in Empfängerliste bei Resend-Host "
            f"{self._host!r} — Versand blockiert (Issue #1147). "
            "Test-Postfächer dürfen NIEMALS über Resend erreicht werden, "
            "auch nicht als Teil einer gemischten Empfängerliste.",
        )
```

`_extract_addr()` — kleiner Helfer, der `"Name <addr>"`-Form auf die reine
Adresse reduziert (z.B. via `email.utils.parseaddr`), damit
`"Gregor Test" <gregor-test@henemm.com>` erkannt wird.

### Go (`internal/mail/sender.go`)

Neue Funktion, analog `resendBlocked`:

```go
var testMailboxes = map[string]bool{
    "gregor-test@henemm.com":    true,
    "gregor-staging@henemm.com": true,
}

// recipientBlocked enforces the recipient-side Resend invariant (Issue #1147):
// a Resend host must never deliver to a GZ test mailbox, regardless of
// user/env/token signals. Third guard line, complements resendBlocked (#1122).
func recipientBlocked(host, to string) error {
    if !strings.Contains(strings.ToLower(host), "resend") {
        return nil
    }
    _, addr, _ := mail.ParseAddress(to) // strips "Name <addr>" form
    lower := strings.ToLower(addr)
    if lower == "" {
        lower = strings.ToLower(to)
    }
    if testMailboxes[lower] {
        return fmt.Errorf(
            "mail.Send: Test-Postfach %q bei Resend-Host %q blockiert (#1147) — "+
                "Test-Postfächer dürfen nie über Resend versendet werden", to, host)
    }
    return nil
}
```

Aufruf am Eintritt von `Send()`, vor `resendBlocked` oder direkt danach
(Reihenfolge irrelevant, beide müssen grün sein):

```go
func Send(cfg MailConfig, to string, msg Mail) error {
    if err := resendBlocked(cfg.Host); err != nil {
        return err
    }
    if err := recipientBlocked(cfg.Host, to); err != nil {
        return err
    }
    ...
}
```

`SendWithFallback` braucht keine Änderung: Ein Fehler aus `recipientBlocked`
enthält keinen `"535"`-String, wird also automatisch als Netzwerk-/Temp-
Fehler behandelt und lenkt auf `fallbackCfg` (Stalwart) um.

### Doku (`docs/reference/operations_playbook.md`)

Neues Kapitel **„Prod-Mail-Pfad-Nachweis: nur passiv"**, gleiche Ebene wie
die bestehenden `## `-Kapitel (E2E-Verifikation, Post-Deploy-Selftest,
Post-Push-Workflow, Parallele Sessions, Daten-Schema-Reworks). Inhalt:

1. **Verbot:** Kein synthetischer Send / Kunst-User auf Prod zur Verifikation
   des Resend-Pfads (das war der 11. Vorfall, Issue #1147).
2. **Passives Prüfrezept** an einer echten, ohnehin versendeten User-Mail:
   - Header-Forensik: `DKIM header.s=resend` + `amazonses`-Received-Header
   - Unit-Env-Attestation: `GZ_RESEND_ALLOWED=1` gesetzt, Settings-Auflösung
     zeigt Resend-Host (ohne Send)
   - Guard-Log-Grep: kein `#1122`/`#1147`-Fehlerlog im relevanten Zeitfenster

## Expected Behavior

- **Input:** Aufgelöste Empfängerliste + SMTP-Host zum Sendezeitpunkt (Python:
  `recipients` in `EmailOutput.send()`; Go: `to`-Parameter in `mail.Send()`)
- **Output:** Bei Resend-Host + Test-Postfach in der Liste → harter Fehler
  (`OutputConfigError` / Go `error`), kein SMTP-Dial. Sonst unverändertes
  Verhalten.
- **Side effects:** Go: `SendWithFallback` versucht bei Fehler automatisch
  die Fallback-Config (Stalwart) — die eigentliche Mail kommt trotzdem an,
  nur nicht über Resend.

## Acceptance Criteria

- **AC-1:** Given `EmailOutput` ist mit einem Resend-Host konstruiert (z.B.
  `smtp.resend.com`) / When `send(..., to=["gregor-test@henemm.com"])`
  aufgerufen wird (Empfänger-Override, umgeht die Init-Guards) / Then wirft
  `send()` eine `OutputConfigError` mit Verweis auf Issue #1147, und es
  erfolgt kein SMTP-Dial (kein `smtplib.SMTP(...)`-Verbindungsaufbau).
  - Test: `EmailOutput(settings_mit_resend_host).send(to=["gregor-test@henemm.com"])` löst die Exception aus; Test prüft reales Verhalten (Exception + kein offener Socket), kein Datei-Grep.

- **AC-2:** Given eine Resend-`EmailOutput`-Instanz / When `send()` mit einer
  gemischten Empfängerliste aufgerufen wird, die sowohl einen echten
  Empfänger als auch `gregor-test@henemm.com` enthält / Then schlägt der
  komplette Sendevorgang hart fehl — keine Teil-Zustellung an den echten
  Empfänger, keine stille Umlenkung nur des Test-Postfachs.
  - Test: `send(to=["real-user@example.com", "gregor-test@henemm.com"])` wirft; kein Mail geht raus (verifiziert über Exception vor dem Dial-Block).

- **AC-3:** Given eine `EmailOutput`-Instanz mit Stalwart-Host
  (`mail.henemm.com`) / When `send(to=["gregor-test@henemm.com"])`
  aufgerufen wird / Then läuft der Versand unverändert durch — der neue
  Guard greift ausschließlich bei Resend-Hosts, Test-Postfächer über
  Stalwart bleiben funktionsfähig.
  - Test: gegen echten Stalwart-Test-SMTP (`GZ_TEST_SMTP_*`) senden, per IMAP im Test-Postfach abrufen (kein Mock).

- **AC-4:** Given eine `EmailOutput`-Instanz mit Resend-Host / When
  `send(to=[...])` ausschließlich Nicht-Test-Empfänger enthält / Then greift
  diese neue Empfänger-Invariante nicht — bestehende Guards (#1122, #924,
  #879, erste/zweite Linie) bleiben die alleinigen Torwächter für diesen Fall
  und sind durch diese Änderung unverändert.
  - Test: bestehende Testsuite `test_issue_1122_resend_default_deny.py` bleibt vollständig grün nach dieser Änderung.

- **AC-5:** Given Go `mail.Send()` wird mit einer `MailConfig` aufgerufen,
  deren `Host` „resend" enthält, und `to` ist `gregor-test@henemm.com` /
  When `Send()` läuft / Then gibt es einen `error`, der das GZ-Test-Postfach
  und Issue #1147 benennt, und es erfolgt kein Netzwerk-Dial
  (`smtp.SendMail` wird nicht erreicht); wird derselbe Aufruf über
  `SendWithFallback(primaryCfg=Resend, fallbackCfg=Stalwart, ...)` getätigt,
  läuft der Versand automatisch über die Fallback-Config weiter (kein
  `"535"` im Fehlertext, also kein Abbruch ohne Fallback-Versuch).
  - Test: `internal/mail/recipient_guard_test.go`, echter `Send()`-Aufruf gegen eine Resend-artige Host-Config (kein echter Netzwerk-Request nötig, da der Guard vor dem Dial greift — Fehler wird direkt geprüft).

- **AC-6:** Given Host- und Adress-Schreibweisen variieren
  (`SMTP.RESEND.COM` groß, `GREGOR-TEST@HENEMM.COM` groß,
  `"Gregor Test" <gregor-test@henemm.com>` Name-Form) / When die Guards
  (Python und Go) mit diesen Varianten aufgerufen werden / Then werden alle
  drei korrekt als Resend-Host bzw. Test-Postfach erkannt und blockiert —
  der Vergleich ist case-insensitiv und Name-Form-robust.
  - Test: parametrisierte Testfälle in beiden Testdateien für alle drei Schreibweisen.

- **AC-7:** Given `docs/reference/operations_playbook.md` nach dieser
  Änderung / When das Kapitel „Prod-Mail-Pfad-Nachweis: nur passiv" gelesen
  wird / Then enthält es das passive Prüfrezept (Header-Forensik + Unit-Env-
  Attestation + Guard-Log-Grep) UND ein explizites Verbot synthetischer
  Sends/Kunst-User auf Prod zur Pfad-Verifikation.
  - Test: `# doc-compliance-test` — prüft Vorhandensein des Kapitels und beider Kernaussagen als Artefakt-Check (zulässige Ausnahme vom Mock-Verbot, da Dokuinhalt selbst der Prüfgegenstand ist).

## Known Limitations

- Gemischte Empfängerlisten (echter Empfänger + Test-Postfach) schlagen bei
  Resend-Host **komplett** fehl statt teilweise zuzustellen — bewusste
  PO-Entscheidung: laut und sichtbar statt still falsch geroutet. Wird in der
  Spec-Freigabe explizit bestätigt.
- `src/app/core.py::send_mail` ist ein toter, guard-loser `smtplib`-Pfad ohne
  Produktions-Aufrufer. Diese Spec deckt ihn NICHT ab — Cleanup/Löschung ist
  ein separater Nebenpunkt, kein Teil der Kern-Invariante.
- Der Guard schützt NICHT gegen Sends an echte Adressen, die aus einem
  Testkontext ausgelöst werden (z.B. versehentlicher Versand an einen realen
  Nutzer während eines Tests). Dafür sind die bestehenden absender-/prozess-
  seitigen Linien zuständig (#1122 Default-Deny, `is_test_mode`, Staging-
  `.env`-Trennung) sowie das separate Bash-Gate aus Issue #1148.
- Die Test-Postfach-Liste (`TEST_MAILBOXES` / `testMailboxes`) ist eine feste
  Konstante mit zwei Adressen. Neue Test-Postfächer erfordern eine
  Code-Änderung an beiden Stellen (Python + Go) — kein zentrales Config-Item.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Additive dritte Guard-Linie auf bestehendem Send-Pfad,
  keine strukturelle Architektur-Änderung. Konsistent mit dem bereits
  etablierten Guard-Muster aus #1122/#924/#879 (Raise statt stiller
  Umlenkung), keine neue Entscheidung, die ein ADR rechtfertigt.

## Test Coverage

- `tests/tdd/test_issue_1147_resend_recipient_invariant.py` (Vorbild:
  `tests/tdd/test_issue_1122_resend_default_deny.py`) — KEINE Mocks; der
  Guard wirft VOR jedem Netzwerk-Dial, daher ohne Mock testbar (Exception
  statt offener SMTP-Verbindung ist das beobachtbare Verhalten). Deckt AC-1
  bis AC-4 und AC-6 (Python-Teil) ab. AC-3 nutzt echten Stalwart-Test-SMTP +
  IMAP-Abruf.
- `internal/mail/recipient_guard_test.go` (Vorbild:
  `internal/mail/resend_guard_test.go`) — deckt AC-5 und AC-6 (Go-Teil) ab.
- Doku-Compliance-Test für AC-7 (`# doc-compliance-test`-Marker), prüft
  `operations_playbook.md` als Artefakt.

## Changelog

- 2026-07-08: Initial spec erstellt — Issue #1147
