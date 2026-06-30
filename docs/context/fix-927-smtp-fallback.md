# Context: fix-927-smtp-fallback

## Request Summary
Wenn Resend.com ausfällt, gehen Briefing- und Alert-Mails ersatzlos verloren. Nach erschöpften Resend-Retries soll automatisch ein Fallback-Versuch über Stalwart (mail.henemm.com:587) erfolgen.

## Related Files
| File | Relevance |
|------|-----------|
| `src/outputs/email.py` | Python-Mail-Pfad: EmailOutput mit Retry-Logik (4 Versuche, 5/15/30s Backoff). Hier Fallback nach letztem fehlgeschlagenem Retry einfügen. |
| `src/app/config.py` | Settings: `imap_host`, `imap_user`, `imap_pass` sind bereits befüllt (GZ_IMAP_*). Diese IMAP-Credentials können direkt als Fallback-SMTP-Credentials genutzt werden (PO-Entscheidung). |
| `internal/mail/sender.go` | Go-Mail-Pfad: einfaches `smtp.SendMail`, kein Retry. Neue Funktion `SendWithFallback` nötig. |
| `internal/config/config.go` | Go-Config: hat SMTP* und GoogleSMTP*, aber keine IMAP/Fallback-Felder. Braucht neue Felder für Stalwart-Credentials. |
| `internal/handler/auth.go` | Ruft `mail.Send` für Password-Reset-Mails auf. Muss auf `SendWithFallback` umgestellt werden. |
| `internal/handler/auth_magic.go` | Ruft `mail.Send` für Magic-Link-Mails auf. Ebenfalls umstellen. |

## Existing Patterns
- **Retry mit Backoff** (Python): `email.py` Zeile 192–268. 4 Versuche, Backoff-Multiplikatoren [1,3,6] × 5s = 5/15/30s. Permanente Fehler (SMTPAuthenticationError, SMTPResponseException 5xx, SMTPRecipientsRefused) brechen sofort ab.
- **Test-User-Routing** (Go): `auth.go` Zeile 222–246: je nach `IsTestUser()` → Google-SMTP oder Resend. Gleiches Dispatch-Pattern als Vorbild für Fallback.
- **Staging-Guard** (Python): `email.py` Zeile 112–118: wenn `env==staging` und `"resend"` im Host → sofortiger Config-Error. Dieser Guard bleibt unangetastet (Issue #924).
- **for_testing()** (Python): `config.py` Zeile 141+: lenkt SMTP auf Stalwart für Test-/Staging-Mails. Zeigt, dass Stalwart technisch als SMTP-Host funktioniert.
- **IMAP-Credentials in Produktion**: `GZ_IMAP_HOST=mail.henemm.com`, `GZ_IMAP_USER=gregor_zwanzig`, `GZ_IMAP_PASS=***` sind in `.env` hinterlegt und in `Settings.imap_*` gemappt.

## Dependencies
- **Upstream (Python):** `Settings.imap_host`, `Settings.imap_user`, `Settings.imap_pass` → Stalwart-Credentials
- **Upstream (Go):** Neue Config-Felder `FallbackSMTPHost/User/Pass` (env: `GZ_FALLBACK_SMTP_HOST/USER/PASS`) oder Wiederverwendung von IMAP-Feldern (werden aktuell nicht in Go verwendet)
- **Downstream:** Scheduler (Python-Scheduler ruft `EmailOutput.send()` auf), Go-API (ruft `mail.Send` in Goroutinen auf)

## Fallback-Logik (geplant)

### Python-Pfad
Fallback greift nur, wenn:
1. Alle Retries erschöpft sind
2. Fehler war transient (OSError oder 4xx `SMTPResponseException`)
3. Fallback-Credentials vorhanden sind (`imap_host`, `imap_user`, `imap_pass`)
4. Primary-Host ist Resend (Stalwart als Primary → kein Fallback auf sich selbst)

Kein Fallback bei:
- `SMTPAuthenticationError` (permanent)
- `SMTPResponseException` 5xx (permanent)
- `SMTPRecipientsRefused` (permanenter Empfänger-Fehler)

### Go-Pfad
Neue Funktion `SendWithFallback(cfg MailConfig, fallback MailConfig, to string, msg Mail) error`:
- Versucht primary `Send`
- Bei Fehler: prüft ob Netzwerk-/Verbindungsfehler (nicht Auth-Fehler)
- Falls ja + Fallback konfiguriert: versucht Fallback
- Loggt "sent via fallback SMTP"

## Test-Strategie (keine Mocks!)
- **Python:** Integration-Test: ungültiger Primary-Host (z.B. `127.0.0.1:1`) + echter Stalwart als Fallback → Mail tatsächlich an IMAP geliefert
- **Go:** Unit-Test mit ungültigem Primary-Port + konfigurierbarem Fallback; Integration-Test analog Python gegen echten Stalwart

## Analysis

### Type
Feature (neue Resilienz-Schicht für bestehende Mail-Versand-Pfade)

### Affected Files
| File | Change Type | Description |
|------|-------------|-------------|
| `src/outputs/email.py` | MODIFY | Fallback-Versuch nach letztem Retry (OSError/4xx), nutzt imap_host/user/pass |
| `internal/mail/sender.go` | MODIFY | Neue Funktion `SendWithFallback(primary, fallback MailConfig, ...)` |
| `internal/config/config.go` | MODIFY | 3 neue Felder: FallbackSMTPHost/User/Pass (GZ_FALLBACK_SMTP_*) |
| `internal/handler/auth.go` | MODIFY | mail.Send → SendWithFallback; Timeout 10s → 20s |
| `internal/handler/auth_magic.go` | MODIFY | mail.Send → SendWithFallback; Timeout 10s → 20s |
| `tests/tdd/test_927_smtp_fallback.py` | CREATE | Integration-Test Python: ungültiger Primary + echter Stalwart als Fallback |
| `internal/mail/sender_integration_test.go` | MODIFY | Go Integration-Test: SendWithFallback mit ungültigem Primary + Stalwart |

### Scope Assessment
- Files: 7
- Estimated LoC: +110 / -2
- Risk Level: MEDIUM — Kritischer Versandpfad, aber Änderung ist additiv (kein bestehender Code entfernt; Fallback greift nur nach vollem Retry-Erschöpfung)

### Technical Approach

**Python-Pfad (`email.py`):**
`EmailOutput.__init__` speichert zusätzlich `imap_host`, `imap_user`, `imap_pass` als `_fallback_*`.
In `send()`: Wenn der letzte Retry-Attempt mit OSError oder 4xx `SMTPResponseException` scheitert, wird einmal via Stalwart versucht. Fallback nur wenn:
- `_fallback_host` gesetzt UND
- `_fallback_host` ≠ Primary-Host (kein Stalwart-auf-Stalwart)
- Primary-Fehler war transient (OSError oder 4xx)
Keine Änderung an `src/app/config.py` — `imap_*`-Felder bereits vorhanden.

**Go-Pfad (`sender.go`):**
Neue Funktion `SendWithFallback(primary, fallback MailConfig, to string, msg Mail) error`:
- Versucht `Send(primary, ...)`.
- Bei Fehler: prüft ob Netzwerkfehler (kein String "535"/"534" = kein Auth-Fehler).
- Wenn Fallback konfiguriert (FallbackSMTPHost ≠ ""): versucht `Send(fallback, ...)`.
- Erfolg via Fallback → Log-Zeile `"[SMTP-FALLBACK] sent via fallback SMTP"`.
`internal/config/config.go`: 3 neue Felder `GZ_FALLBACK_SMTP_HOST/USER/PASS`.
`auth.go` + `auth_magic.go`: `mail.Send(cfg, ...)` → `mail.SendWithFallback(cfg, fallbackCfg, ...)`, Timeout 10s → 20s.

**Test-Strategie (keine Mocks!):**
- Python: Echter Stalwart als Fallback, Primary = ungültiger Host (`127.0.0.1:1`); Mail per IMAP verifizieren.
- Go: `SendWithFallback` mit ungültigem Primary-Port + echter Stalwart; `//go:build integration`.

### Dependencies
- `EmailOutput` wird direkt in `trip_report_scheduler.py`, `trip_alert.py`, `inbound_email_reader.py`, `api/routers/scheduler.py`, `notify.py`, `debug.py`, `cli.py` instanziiert. Fallback ist transparent — keine dieser Dateien braucht Änderungen.
- `mail.Send` nur in `auth.go:253` und `auth_magic.go:110` — beide umstellen.

### Open Questions
- [x] Stalwart-Credentials: IMAP-Credentials wiederverwenden (PO-Entscheidung ✓)
- [x] Go-Fallback-Config: neue Felder `GZ_FALLBACK_SMTP_*` in config.go; müssen in `.env` und Systemd eingetragen werden (nach Implementierung als Infra-MQ-Nachricht)

## Risks & Considerations
- **#924 nicht berühren:** Staging-Guard (`env==staging` + Resend → Error) liegt im `__init__`, nicht in der Send-Logik. Fallback-Code kommt nach dem Guard, kann den Guard also nicht umgehen.
- **Doppel-Versand verhindern:** Fallback nur wenn Primary nach allen Retries fehlschlug — nicht parallel. Kein Risiko doppelter Zustellung.
- **Stalwart-Reputation:** Ausgehende Mails via Hetzner-IP können im Spam landen. Bewusst akzeptiertes Risiko laut Issue (besser Spam-Ordner als kein Briefing).
- **Go-Goroutinen:** auth.go/auth_magic.go spawnen `mail.Send` in Goroutinen mit 10s Timeout. `SendWithFallback` kann mehr Zeit brauchen (Retry-Wartezeit entfällt im Fallback, aber Timeout sollte auf 20s erhöht werden).
- **Go-Config:** Neue Felder `GZ_FALLBACK_SMTP_HOST/USER/PASS` in `internal/config/config.go` nötig — müssen in `.env` und Systemd-Service-Files hinterlegt werden (Infra-Repo-Task).
