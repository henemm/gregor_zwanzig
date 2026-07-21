# Spec: Test-/Staging-Mail-Versand strikt von Resend isolieren (Issue #879)

- **Status:** Approved (PO 'go' 2026-06-28)
- **Created:** 2026-06-28
- **Issue:** #879
- **ADR:** [no-adr] — bestätigt bestehende Architektur (Resend = Produktion senden, Stalwart = lokal/Test), keine Richtungsänderung.

## Problem / Kontext

Resend ist der einzige Versanddienst für externe Produktiv-Briefings (`smtp.resend.com`).
Das monatliche Versandkontingent war ~70 % erschöpft, ohne dass Produktivnutzung das
erklärt. Ursache: Test-, E2E- und (potenziell) Staging-Mails liefen über denselben
Resend-Account und belasteten das Produktivkontingent.

Chronologie der bestehenden Teil-Schutzmaßnahmen:

1. **2026-05-10** (`f3683066`): Wächter in `EmailOutput.__init__` — wirft `OutputConfigError`,
   wenn `is_test_mode` gesetzt ist **und** `smtp_host` „resend" enthält.
2. **2026-05-17** (`6b3a9628`): `Settings.for_testing()` / `with_user_profile()` routen
   Test-User (`*test*`/`*tdd*`) auf Stalwart-Credentials — **ändern aber `smtp_host` NICHT**
   (Annahme damals: `smtp_host` = Stalwart).
3. **2026-06-24** (#876): `GZ_SMTP_HOST` von Stalwart **zurück auf `smtp.resend.com`** gestellt,
   weil Stalwart externe Zustellung (DNSSEC bei Resend-AAAA) nicht mehr leisten konnte.

**Folge des heutigen Zustands** (`smtp_host = smtp.resend.com`):

- Der Wächter (1) stoppt das akute Leck für test-getaggte User — Test-Versand über Resend
  wirft `OutputConfigError`. Gut, aber:
- `for_testing()` (2) lenkt `smtp_host` nicht um → Test-Mails landen im Wächter und
  **schlagen fehl** statt lokal über Stalwart zugestellt zu werden. Der Test-/E2E-Mail-Pfad
  ist faktisch kaputt.
- **Staging hat keine eigene Bremse:** Eine echte (nicht test-getaggte) Tour auf Staging
  würde ein echtes Briefing über Resend an einen echten Empfänger senden und still das
  Produktivkontingent belasten.

`gregor-test@henemm.com` ist ein **lokales** Stalwart-Postfach; Absender und Empfänger
liegen beide auf `@henemm.com`. Eine solche Zustellung braucht **kein** externes Relay und
ist vom DNSSEC-Problem aus #876 nicht betroffen.

## Scope

- **In Scope:** `Settings.for_testing()`, `Settings`-Felder (`test_smtp_host`/-`port`),
  Staging-Test-Modus-Erzwingung, Beibehaltung des Resend-Wächters.
- **Out of Scope:** Resend-Verbrauchs-Monitoring mit Alarm (an Infrastruktur-Instanz
  delegiert, gehört in `henemm-infra` — kein neuer BetterStack-Heartbeat, Integration in
  bestehenden Check; Kontingent bei 10 Heartbeats voll).

## Affected Files

- `src/app/config.py` — `Settings.for_testing()`, neue Felder `test_smtp_host`/`test_smtp_port`,
  Staging-Erzwingung in `with_user_profile()`.
- `src/outputs/email.py` — Resend-Wächter (unverändert, bleibt als zweite Sicherung).
- `.env` (Server/Staging) — `GZ_TEST_SMTP_HOST` setzen (Operations, nicht im Repo).
- `tests/tdd/test_issue_879_*.py` — neue Tests.

## Acceptance Criteria

**AC-1:** Given ein Test-Kontext (`is_test_mode=True` bzw. test-getaggter User) und
`GZ_SMTP_HOST=smtp.resend.com`, When eine Briefing-Mail an `gregor-test@henemm.com` versendet
wird, Then erfolgt der SMTP-Versand über den lokalen Stalwart-Host (`test_smtp_host`,
Default `mail.henemm.com`) und **nicht** über Resend; die Mail wird zugestellt und ist per
IMAP im `gregor-test`-Postfach nachweisbar.

**AC-2:** Given `GZ_ENV=staging`, When der Versandpfad Settings auflöst (`with_user_profile`
für beliebige `user_id`, auch nicht-test), Then ist `is_test_mode=True` und der Versand läuft
über den Stalwart-Test-Account — der Staging-Server kann strukturell **keine** Mail über Resend
an reale Empfänger senden.

**AC-3:** Given `is_test_mode=True` und ein `smtp_host`, der „resend" enthält, When `EmailOutput`
instanziiert wird, Then wirft es `OutputConfigError` (bestehender Wächter bleibt als
Defense-in-Depth erhalten und greift, falls `test_smtp_host` fehlkonfiguriert ist).

## Test Strategy

- **AC-1:** Echter SMTP-Versand über Stalwart an `gregor-test@henemm.com`, echter IMAP-Abruf,
  Inhalt geprüft (kein Mock — Projektregel). Zusätzlich Unit-Test: `for_testing()` setzt
  `smtp_host`/`smtp_port` auf `test_smtp_host`/-`port`.
- **AC-2:** Settings mit `env="staging"` → `with_user_profile("realuser")` liefert
  `is_test_mode=True` und Stalwart-Host.
- **AC-3:** `EmailOutput(Settings(is_test_mode=True, smtp_host="smtp.resend.com", ...))`
  wirft `OutputConfigError`.

## Open Questions

Keine — Verhalten durch ACs abgedeckt.
