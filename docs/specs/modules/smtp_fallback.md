---
entity_id: smtp_fallback
type: bugfix
created: 2026-06-30
updated: 2026-06-30
status: draft
workflow: fix-927-smtp-fallback
---

# SMTP-Fallback via Stalwart (Issue #927)

## Approval

- [ ] Approved

## Purpose

Wenn Resend.com nicht erreichbar ist, gehen Briefing- und Alert-Mails ersatzlos verloren — der bestehende Retry-Mechanismus (3 Wiederholungen, bis zu 30 s Backoff) fängt nur kurzfristige Netzwerkzuckungen ab, nicht aber einen anhaltenden Resend-Ausfall. Dieses Modul ergänzt Stalwart (mail.henemm.com:587) als Fallback-SMTP, der nach Erschöpfung aller Resend-Versuche greift: Python-Pfad in `EmailOutput.send()`, Go-Pfad als neue Funktion `SendWithFallback()`.

## Source

- **File (Python):** `src/outputs/email.py`
- **Identifier:** `class EmailOutput` / `def send()`
- **File (Go):** `internal/mail/sender.go`
- **Identifier:** `func SendWithFallback()`
- **File (Go Config):** `internal/config/config.go`
- **Identifier:** `type Config struct`

## Estimated Scope

- **LoC:** ~120
- **Files:** 7
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/outputs/email.py::EmailOutput` | module | Python-Hauptpfad, wird erweitert |
| `internal/mail/sender.go::Send` | function | Go-Basisfunktion, bleibt erhalten; neue Wrapper-Funktion daneben |
| `internal/config/config.go::Config` | module | Aufnahme neuer Fallback-SMTP-Felder |
| `internal/handler/auth.go` | handler | Ruft `mail.Send` auf — wird auf `SendWithFallback` umgestellt |
| `internal/handler/auth_magic.go` | handler | Ruft `mail.Send` auf — wird auf `SendWithFallback` umgestellt |
| `GZ_IMAP_HOST / GZ_IMAP_USER / GZ_IMAP_PASS` | config | Python-Fallback bezieht Stalwart-Zugangsdaten daraus |
| `GZ_FALLBACK_SMTP_HOST / _USER / _PASS` | config | Go-Fallback-Felder (neu) |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/outputs/email.py` | MODIFY | Fallback-Block nach letztem Retry-Versuch (OSError / 4xx erschöpft) |
| `internal/mail/sender.go` | MODIFY | Neue Funktion `SendWithFallback()` neben unverändertem `Send()` |
| `internal/config/config.go` | MODIFY | Neue Felder `FallbackSMTPHost`, `FallbackSMTPUser`, `FallbackSMTPPass` |
| `internal/handler/auth.go` | MODIFY | `mail.Send` → `mail.SendWithFallback`, Timeout 10 s → 20 s |
| `internal/handler/auth_magic.go` | MODIFY | `mail.Send` → `mail.SendWithFallback`, Timeout 10 s → 20 s |
| `tests/tdd/test_927_smtp_fallback.py` | CREATE | Python-Integration-Test (kein Mock, echter Stalwart-Fallback) |
| `internal/mail/sender_integration_test.go` | MODIFY | Go-Integration-Test mit `SendWithFallback` |

### Estimated Changes

- Files: 7
- LoC: +110/-10

## Implementation Details

### Python-Pfad (`src/outputs/email.py`)

Nach dem letzten fehlgeschlagenen Retry-Versuch in `EmailOutput.send()` prüft der Code, ob Fallback-Credentials vorhanden sind. Auslöser für den Fallback: nur `OSError` (Netzwerkfehler) und SMTP 4xx-Temporärfehler nach Retry-Erschöpfung. Kein Fallback bei `SMTPAuthenticationError` (535) oder `SMTPResponseException` mit Code >= 500 — diese sind permanent.

Fallback-Logik greift ausschließlich nach dem letzten (vierten) Retry-Versuch:

- Primary erschöpft (OSError oder 4xx nach 4 Versuchen)
- Fallback-Credentials aus `settings.imap_host` / `settings.imap_user` / `settings.imap_pass` (GZ_IMAP_*) prüfen
- Wenn vorhanden: Verbindungsversuch gegen Stalwart-SMTP (Port 587, STARTTLS)
- Log-Eintrag `[SMTP-FALLBACK] sent via fallback SMTP` bei Erfolg
- Kein neues Settings-Feld nötig: GZ_IMAP_* bereits vorhanden, Stalwart akzeptiert SMTP mit denselben Credentials

Der Staging-Guard (Issue #924) liegt in `__init__` und greift vor jeder Fallback-Logik — er bleibt unverändert.

### Go-Pfad (`internal/mail/sender.go`)

Neue Funktion `SendWithFallback(primaryCfg, fallbackCfg MailConfig, to string, msg Mail) error`:

1. Versucht `Send(primaryCfg, to, msg)`
2. Bei Fehler: prüft `fallbackCfg.Host != ""`
3. Wenn Fallback konfiguriert: loggt `[SMTP-FALLBACK] Primary failed: <err>`, ruft `Send(fallbackCfg, to, msg)`
4. Wenn Fallback ebenfalls fehlschlägt: gibt kombinierten Fehler zurück
5. Bei Auth-Fehler (535-String im Fehler): sofortiger Abbruch ohne Fallback

Bestehende `Send()`-Funktion bleibt unverändert (keine Breaking Change).

### Config-Erweiterung (`internal/config/config.go`)

Drei neue Felder im Config-Struct mit GZ_-Prefix durch envconfig: `GZ_FALLBACK_SMTP_HOST`, `GZ_FALLBACK_SMTP_USER`, `GZ_FALLBACK_SMTP_PASS` (alle default leer).

### Handler-Anpassungen

In `auth.go` und `auth_magic.go` wird `mail.Send(c, to, msg)` ersetzt durch `mail.SendWithFallback(c, fallbackCfg, to, msg)`, wobei `fallbackCfg` aus den neuen Config-Feldern gebaut wird. Goroutine-Timeout: 10 s → 20 s, um dem Fallback-Versuch ausreichend Zeit zu lassen.

## Expected Behavior

- **Input:** SMTP-Sendeanfrage (subject, body, recipients) bei nicht erreichbarem Primary-SMTP
- **Output:** Mail wird trotzdem zugestellt (via Stalwart); Log-Eintrag `[SMTP-FALLBACK] sent via fallback SMTP`
- **Side effects:** Bei permanenten Fehlern (Auth 535, 5xx) kein Fallback-Versuch — Fehler wird sofort geworfen

## Acceptance Criteria

- **AC-1:** Given GZ_SMTP_HOST=smtp.resend.com (nicht erreichbar) und GZ_IMAP_HOST=mail.henemm.com (erreichbar) / When EmailOutput.send() aufgerufen wird und alle 4 Resend-Versuche mit OSError fehlschlagen / Then wird die Mail trotzdem via Stalwart zugestellt und das Log enthält den Eintrag "[SMTP-FALLBACK]"
  - Test: `tests/tdd/test_927_smtp_fallback.py` — echter SMTP-Verbindungsversuch auf ungültigem Primary-Host, echter Stalwart als Fallback, IMAP-Abholung beweist Zustellung

- **AC-2:** Given GZ_SMTP_HOST=smtp.resend.com mit falschem SMTP-Passwort / When EmailOutput.send() aufgerufen wird und Resend mit SMTPAuthenticationError (535) antwortet / Then wird sofort OutputError geworfen, kein Fallback-Versuch findet statt
  - Test: `tests/tdd/test_927_smtp_fallback.py` — Auth-Fehler-Szenario, Log darf keinen "[SMTP-FALLBACK]"-Eintrag enthalten

- **AC-3:** Given GZ_SMTP_HOST=smtp.resend.com (nicht erreichbar) und GZ_FALLBACK_SMTP_HOST=mail.henemm.com (erreichbar) / When mail.SendWithFallback() für Password-Reset aufgerufen wird / Then wird die Mail via Stalwart zugestellt und das Log enthält "[SMTP-FALLBACK]"
  - Test: `internal/mail/sender_integration_test.go` — ungültiger Primary-Host, echter Stalwart-Fallback, Response-Code 250 als Nachweis

- **AC-4:** Given GZ_SMTP_HOST zeigt auf Resend und Fehler ist Auth-Fehler (535) / When mail.SendWithFallback() aufgerufen wird / Then wird ein Fehler zurückgegeben und kein Fallback-Versuch unternommen
  - Test: `internal/mail/sender_integration_test.go` — Auth-Fehler-Szenario, Fehler-String enthält "535"

- **AC-5:** Given GZ_ENV=staging und GZ_SMTP_HOST enthält "resend" / When EmailOutput() instanziiert wird / Then wird sofort OutputConfigError geworfen — Staging-Guard (#924) greift unverändert, der Fallback-Pfad wird nie erreicht
  - Test: `tests/tdd/test_927_smtp_fallback.py` — Staging-Guard-Szenario, Exception-Type und Message prüfen

- **AC-6:** Given Fallback erfolgreich via Stalwart / When Mail zugestellt wurde / Then enthält der Log-Eintrag exakt "[SMTP-FALLBACK] sent via fallback SMTP"
  - Test: Teil der Tests AC-1 und AC-3 — Log-Capture und String-Assertion

## Known Limitations

- Go-Pfad erkennt Auth-Fehler nur via Fehler-String-Matching ("535"), da `net/smtp` keinen strukturierten Error-Typ für SMTP-Antwortcodes zurückgibt.
- Der Python-Fallback erhöht die maximale Gesamtwartezeit einer Send-Operation: 4 Retries (5 + 15 + 30 s Backoff) + Fallback-Verbindungsversuch. Bei komplettem Ausfall beider SMTP-Server verlängert sich der Timeout entsprechend.
- Kein Fallback-Retry: Der Fallback-Versuch läuft einmalig ohne eigene Retry-Logik.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Kein Architektur-Paradigmenwechsel — der Fallback ist eine lokale Erweiterung bestehender Send-Funktionen. Die bestehende Stalwart-Infrastruktur (GZ_IMAP_*) wird für Python wiederverwendet; für Go werden drei neue ENV-Variablen eingeführt (GZ_FALLBACK_SMTP_*). Keine neue externe Abhängigkeit.

## Changelog

- 2026-06-30: Initial spec created
