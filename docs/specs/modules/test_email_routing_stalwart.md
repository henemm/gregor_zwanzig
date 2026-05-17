---
entity_id: test_email_routing_stalwart
type: module
created: 2026-05-17
updated: 2026-05-17
status: draft
version: "1.0"
tags: [backend, config, testing, email, stalwart]
---

# Test-E-Mail-Routing auf Stalwart

## Approval

- [ ] Approved

## Purpose

Test-E-Mails gehen künftig an `gregor-test@henemm.com` (lokales Stalwart-Postfach) statt an `henning.emmrich@gmail.com` (privates Postfach). `Settings.for_testing()` nutzt dafür ein dediziertes Test-Konto auf dem bestehenden Stalwart-Server — kein Gmail-Relay mehr. `test_html_email.py` prüft den Posteingang über Stalwart-IMAP.

## Source

- **File:** `src/app/config.py`
- **Identifier:** `Settings.for_testing()`, `Settings.google_smtp_*`-Felder (ersetzen)
- **Zusätzlich:** `tests/tdd/test_html_email.py` — Klassen-/Kommentar-Anpassung

> **Schicht-Hinweis:** Reines Python-Backend. Kein Go-API-Touch, kein SvelteKit-Touch.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/outputs/email.py` | bestehend | Resend-Guard: prüft `is_test_mode` + `"resend" in smtp_host` — bleibt unverändert korrekt |
| `data/users/default/user.json` | bestehend | `mail_to = gregor-test@henemm.com` — bereits geändert |
| `.env` | bestehend | `GZ_TEST_SMTP_*` / `GZ_TEST_IMAP_*` bereits vorbereitet |
| Stalwart `gregor-test@henemm.com` | Infrastruktur | Postfach existiert, IMAP + SMTP verifiziert |

## Implementation Details

### config.py — Felder ersetzen

`google_smtp_host/port/user/pass` und `google_mail_from` werden entfernt (ENV-Vars bereits aus `.env` gelöscht). Ersatz:

```python
# Test-Account-Credentials (gregor-test@henemm.com auf Stalwart)
test_smtp_user: Optional[str] = Field(default=None, ...)
test_smtp_pass: Optional[str] = Field(default=None, ...)
test_mail_from: Optional[str] = Field(default=None, ...)
test_imap_user: Optional[str] = Field(default=None, ...)
test_imap_pass: Optional[str] = Field(default=None, ...)
```

ENV-Mapping (automatisch via Pydantic `GZ_`-Prefix):
`GZ_TEST_SMTP_USER`, `GZ_TEST_SMTP_PASS`, `GZ_TEST_MAIL_FROM`, `GZ_TEST_IMAP_USER`, `GZ_TEST_IMAP_PASS`

### config.py — for_testing() umschreiben

```python
def for_testing(self) -> "Settings":
    if not self.test_smtp_user or not self.test_smtp_pass:
        return self.model_copy(update={"is_test_mode": True})
    return self.model_copy(update={
        "smtp_user": self.test_smtp_user,
        "smtp_pass": self.test_smtp_pass,
        "mail_from": self.test_mail_from or f"{self.test_smtp_user}@henemm.com",
        "imap_user": self.test_imap_user or self.test_smtp_user,
        "imap_pass": self.test_imap_pass or self.test_smtp_pass,
        "is_test_mode": True,
    })
```

`smtp_host`/`smtp_port`/`imap_host`/`imap_port` bleiben unverändert — Test läuft auf demselben Stalwart-Server wie Produktion.

### test_html_email.py — Klasse umbenennen

`TestRealGmailE2E` → `TestRealStalwartE2E`. Docstring-Kommentare "Gmail SMTP" → "Stalwart SMTP". Kein Logik-Change nötig: IMAP-Check nutzt bereits `settings.imap_user` / `settings.imap_pass`, die `for_testing()` ab sofort auf `gregor-test`-Credentials setzt.

## Expected Behavior

- **Input:** `Settings().for_testing()` mit gesetzten `GZ_TEST_*`-Vars
- **Output:** Settings-Kopie mit SMTP-User/Pass = `gregor-test`, IMAP-User/Pass = `gregor-test`, `is_test_mode=True`
- **Side effect:** E-Mail landet in `gregor-test@henemm.com`-INBOX statt privatem Gmail

## Acceptance Criteria

**AC-1:** Given `GZ_TEST_SMTP_USER=gregor-test` und `GZ_TEST_SMTP_PASS` gesetzt / When `Settings().for_testing()` aufgerufen / Then gibt Settings zurück mit `smtp_user="gregor-test"`, `imap_user="gregor-test"` und `is_test_mode=True`
- Test: (nach /tdd-red)

**AC-2:** Given `GZ_TEST_SMTP_USER` nicht gesetzt / When `Settings().for_testing()` aufgerufen / Then gibt Settings zurück mit nur `is_test_mode=True` (Fallback, kein Absturz)
- Test: (nach /tdd-red)

**AC-3:** Given Test-Mail gesendet via `for_testing()`-Settings / When IMAP-Check auf `mail.henemm.com:993` mit `gregor-test`-Credentials / Then E-Mail in INBOX gefunden
- Test: (nach /tdd-red — E2E)

## Changelog

| Version | Datum | Änderung |
|---------|-------|----------|
| 1.0 | 2026-05-17 | Initial — Gmail-Relay durch Stalwart-Test-Account ersetzt |

## Known Limitations

- `test_html_email.py::TestRealStalwartE2E` erfordert laufenden Server + Netzwerkzugang zu `mail.henemm.com` — wird nicht in normalen `pytest`-Läufen ausgeführt
- Test-User (`test_*`-IDs) senden weiterhin an `GZ_MAIL_TO=gregor_zwanzig@henemm.com` — unverändert
