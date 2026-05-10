---
entity_id: no_resend_for_tests
type: tests
created: 2026-05-10
updated: 2026-05-10
status: approved
version: "1.0"
tags: [email, guardrail, resend, gmail]
---

# Wächter-Tests: Test-Mails niemals über Resend

## Approval

- [x] Approved

## Purpose

Mechanischer Wächter, der jede Regression bricht, bei der Test-/TDD-Mails versehentlich über
Resend (Produktiv-Versanddienst) statt über Gmail-SMTP gehen. Verhindert, dass Resend-Kontingent
durch Tests verbrannt wird und Zustellraten verfälscht werden.

## Source

- **File:** `tests/unit/test_no_resend_for_tests.py`
- **Implementation under test:** `src/app/config.py` (`Settings.is_test_mode`, `Settings.for_testing`,
  `Settings.with_user_profile`) und `src/outputs/email.py` (`EmailOutput.__init__`)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| Settings | module | Liefert `is_test_mode`-Flag und `for_testing()` |
| EmailOutput | module | Verweigert Versand, wenn Test-Modus + Resend-Host |

## Test Cases

| # | Test | Erwartetes Verhalten |
|---|------|---------------------|
| 1 | `for_testing_setzt_is_test_mode` | `Settings().for_testing()` setzt `is_test_mode=True` |
| 2 | `for_testing_swappt_auf_gmail` | `for_testing()` ersetzt SMTP-Host durch `google_smtp_host` |
| 3 | `for_testing_ohne_gmail_credentials_setzt_trotzdem_flag` | Wenn `google_smtp_*` leer, bleibt SMTP-Host unverändert, aber `is_test_mode=True` (damit Wächter greift) |
| 4 | `email_output_blockiert_resend_im_test_modus` | `EmailOutput(settings)` wirft `OutputConfigError`, wenn `is_test_mode=True` und Host `resend` enthält |
| 5 | `email_output_erlaubt_gmail_im_test_modus` | `EmailOutput(settings)` funktioniert mit Gmail-Host im Test-Modus |
| 6 | `email_output_erlaubt_resend_in_production` | `EmailOutput(settings)` erlaubt Resend, wenn `is_test_mode=False` (echter User-Versand) |
| 7 | `test_user_routing_aktiviert_test_modus` | `Settings().with_user_profile("test_alice")` setzt `is_test_mode=True`; bei normalem User bleibt es `False` |

## Expected Behavior

- **Input:** Settings-Instanzen in verschiedenen Konfigurationen (Resend, Gmail, Test-User-IDs)
- **Output:** Pytest grün → Wächter intakt; Pytest rot → Regression im Versand-Routing
- **Side effects:** Keine — Tests instanziieren nur Klassen, senden keine echten Mails

## Known Limitations

- Heuristik: Erkennung „Resend" über Substring im Hostnamen (`smtp.resend.com`). Falls Resend
  jemals einen anderen Host verwendet, müssen Test #4 und der Wächter in `EmailOutput.__init__`
  angepasst werden.
- `is_test_mode` ist ein Flag-basierter Schutz, kein DNS-Block. Wer das Flag bewusst umgeht,
  kommt durch — die Test-Suite würde das aber bei nächstem Lauf melden.

## Changelog

- 2026-05-10: Initial Spec (User-Anforderung „Test-Mails NIE über Resend")
