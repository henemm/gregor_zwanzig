# Context: test-email-routing-stalwart

## Request Summary
Test-E-Mails sollen an `gregor-test@henemm.com` (Stalwart) gehen statt an `henning.emmrich@gmail.com` (privates Postfach). Der User-JSON-Eintrag ist bereits geändert; die Code-Anpassungen in `config.py` und `test_html_email.py` sind blockiert (geschützte Dateien).

## Related Files

| Datei | Relevanz |
|-------|----------|
| `src/app/config.py` | Settings-Klasse: `for_testing()`, `_is_test_user()`, `google_smtp_*`-Felder — muss bereinigt werden |
| `src/outputs/email.py` | Resend-Guard (`is_test_mode` + Resend-Host-Check) — Kommentar veraltet, Guard bleibt korrekt |
| `tests/tdd/test_html_email.py` | E2E-Test: sendet via `Settings.for_testing()`, prüft IMAP auf `settings.imap_*` — muss auf `gregor-test`-Credentials umgestellt werden |
| `data/users/default/user.json` | `mail_to` bereits auf `gregor-test@henemm.com` geändert ✓ |
| `.env` | `GZ_GOOGLE_SMTP_*` entfernt, `GZ_TEST_SMTP_*`/`GZ_TEST_IMAP_*` ergänzt (noch ohne Mapping in config.py) |

## Existing Patterns
- `Settings`-Felder werden über Pydantic `Field(default=None)` mit Env-Var-Mapping via `GZ_`-Prefix definiert
- `for_testing()` gibt `model_copy(update={...})` zurück — immutable Settings
- IMAP-Fallback-Kette: `settings.imap_user or settings.smtp_user`
- `_is_test_user()` erkennt Test-User-IDs per String-Pattern (`"test"` oder `"tdd"` in user_id)

## Was bereits erledigt ist
- `data/users/default/user.json`: `mail_to = gregor-test@henemm.com` ✓
- `.env`: Gmail-Vars entfernt, neue `GZ_TEST_*`-Vars vorbereitet ✓
- Stalwart-Account `gregor-test@henemm.com` angelegt, Passwort `GregorTest-7xK9mQ2026!` ✓
- IMAP + SMTP Ende-zu-Ende verifiziert ✓

## Was noch fehlt

### 1. `src/app/config.py`
- `google_smtp_*`-Felder durch `test_smtp_user`, `test_smtp_pass`, `test_mail_from`, `test_imap_user`, `test_imap_pass` ersetzen
- `for_testing()`: nutzt jetzt Stalwart-SMTP (gleicher Host wie Produktion), überschreibt SMTP-User/Pass/From auf Test-Credentials und zusätzlich IMAP-User/Pass

### 2. `tests/tdd/test_html_email.py`
- Klasse `TestRealGmailE2E` umbenennen → `TestRealStalwartE2E` (oder ähnlich)
- IMAP-Check: nutzt bereits `settings.imap_user` — funktioniert automatisch wenn `for_testing()` IMAP überschreibt
- Kommentare: "Gmail SMTP" → "Stalwart SMTP"

## Dependencies
- **Upstream:** `.env` → `Settings` → `for_testing()` → `EmailOutput`
- **Downstream:** `test_html_email.py::TestRealGmailE2E`, `email.py` Resend-Guard

## Risks & Considerations
- `email.py` Resend-Guard prüft `"resend" in smtp_host` — bleibt korrekt (Stalwart-Host ist `mail.henemm.com`)
- `_is_test_user("default")` → False → `for_testing()` wird für default-User NICHT aufgerufen → `mail_to` kommt direkt aus user.json ✓
- Test-User (z.B. `test_*`) bekommen weiterhin `mail_to` aus globalem `GZ_MAIL_TO=gregor_zwanzig@henemm.com` — unverändert korrekt
- LoC-Delta: ~15 Zeilen Änderung → gut unter Limit
