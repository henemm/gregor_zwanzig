# Context: Issue #879 — Test-/Staging-Mail-Versand von Resend isolieren

## Request

Verhindern, dass Test-/E2E-/Staging-Mails das Resend-Produktivkontingent belasten.
PO-Frage: nicht „ob", sondern „wie zukünftig verhindern".

## Findings (Codebase-Recherche 2026-06-28)

- `src/outputs/email.py:110-117` — Wächter: `is_test_mode` + `smtp_host` enthält „resend" → `OutputConfigError`.
- `src/app/config.py:139-155` — `for_testing()` schaltet User/From auf Stalwart-Test-Creds,
  **lässt `smtp_host` aber unverändert**.
- `src/app/config.py:163-197` — `with_user_profile()` ruft `for_testing()` nur für test-getaggte User.
- `.env` — `GZ_SMTP_HOST=smtp.resend.com` (seit #876, 2026-06-24). Kein `GZ_TEST_SMTP_HOST`.
- Sendepfade: `trip_alert.py`, `trip_report_scheduler.py`, `inbound_email_reader.py`,
  `inbound_telegram_reader.py`, `cli.py` — reguläre Pfade nutzen `with_user_profile`.
- Kein `GZ_ENV=staging`-spezifischer Versand-Schutz im Scheduler.

## Affected Files

- `src/app/config.py`, `src/outputs/email.py`
- `tests/tdd/test_issue_879_*.py`

## Dependencies

- Maßnahme „Resend-Verbrauchs-Monitoring" an Infrastruktur-Instanz delegiert (MQ #41383),
  gehört in `henemm-infra` (kein neuer BetterStack-Heartbeat — Kontingent voll).

Spec: `docs/specs/modules/issue_879_test_mail_resend_isolation.md`
