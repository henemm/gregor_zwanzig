---
entity_id: bug_201_html_email_mocks_tests
type: tests
created: 2026-05-12
updated: 2026-05-12
status: draft
version: "1.0"
tags: [tests, refactor, bugfix, mock-removal, issue-201]
parent: issue_201_html_email_mocks_removal
phase: phase5_tdd_red
---

# Issue #201 — Mocks aus `tests/tdd/test_html_email.py` entfernen (Tests)

## Approval

- [x] Approved

## Purpose

Test-Manifest fuer den Mock-Removal-Refactor in `tests/tdd/test_html_email.py`.
Jeder Eintrag mappt einen pytest-Funktionsnamen auf das in der Parent-Spec
definierte Acceptance-Criterion (AC-1 bis AC-5).

Parent-Spec: `docs/specs/bugfix/issue_201_html_email_mocks_removal.md`.

## Source

- **Files:**
  - `tests/refactor/test_issue_201_mocks_removed.py` (NEU — Refactor-Strukturpruefung)
- **Spec:** `docs/specs/bugfix/issue_201_html_email_mocks_removal.md` v1.0

## Test Inventory

Die Test-Funktionsnamen verwenden Bezeichner aus der Parent-Spec, damit der
Spec-Enforcement-Hook sie aufloesen kann. Die Mapping-Tabelle dokumentiert,
welcher Test welches Acceptance-Criterion abdeckt.

### Refactor-Strukturpruefung (`tests/refactor/test_issue_201_mocks_removed.py`)

| Test-Funktion | AC | Was geprueft wird |
|---------------|----|------------------|
| `ac1_no_mock_imports_or_calls` | AC-1 | grep auf `from unittest.mock`, `MockSMTP`, `patch("smtplib`, `patch("time`, `settings = Mock()`, `= Mock()` in der Zieldatei — 0 Treffer. |
| `ac2_only_two_test_classes` | AC-2 | Regex-Suche nach `^class Test...` — genau 2 Treffer: `TestSubscriptionEmailGeneration`, `TestRealGmailE2E`. Klassen `TestHTMLEmailFormat`, `TestEndToEndEmailSending`, `TestEmailRetryMechanism` sind weg. |
| `ac3_imports_point_to_services` | AC-3 | grep auf `from web.pages.compare`, `from src.web.pages.compare` — 0 Treffer. Statt dessen muss `services.comparison_renderers` oder `services.compare_subscription` importiert werden. |
| `ac4_collect_only_returns_two_tests` | AC-4 | `pytest --collect-only` sammelt genau 2 Tests in der Zieldatei. |
| `ac5_scoped_run_one_pass_one_skip` | AC-5 | `pytest -v` auf der Zieldatei ergibt 0 FAIL (1 PASS + 1 SKIP via `@pytest.mark.email`). |

## Expected RED-State (vor GREEN-Phase)

| Test | Erwartung in Phase 5 (RED) | Begruendung |
|------|----------------------------|-------------|
| `ac1_no_mock_imports_or_calls` | FAIL | Mocks sind heute in 3 von 5 Klassen drin. |
| `ac2_only_two_test_classes` | FAIL | Heute 5 Test-Klassen, nicht 2. |
| `ac3_imports_point_to_services` | FAIL | Heute Import aus `web.pages.compare`. |
| `ac4_collect_only_returns_two_tests` | FAIL | Heute 13 Tests gesammelt, nicht 2. |
| `ac5_scoped_run_one_pass_one_skip` | kann GREEN sein | Heute laufen alle 13 Tests, evtl. ohne FAIL — der Test pruefe nur "0 failed", was aktuell schon stimmen koennte. |

Mindestens AC-1 bis AC-4 muessen FAIL liefern — das ist der RED-Beweis.

## Verification

- **Scoped Run:** `uv run pytest tests/refactor/test_issue_201_mocks_removed.py -v`
- **Phase 5 RED:** Mindestens 4 von 5 Tests rot.
- **Phase 6 GREEN:** Alle 5 Tests gruen — nach Loeschung der 3 Mock-Klassen + Import-Update.

## Out of Scope

- Funktionale Pruefung des bestehenden `TestSubscriptionEmailGeneration::test_subscription_generates_html_email_with_real_data` — der Test bleibt unveraendert und prueft sich selbst beim regulaeren pytest-Lauf.
- E2E-Mail-Pruefung in `TestRealGmailE2E` — wird durch den `@pytest.mark.email`-Marker im scoped Run uebersprungen, kein Teil dieses Refactors.

## Changelog

- 2026-05-12: Initial test manifest fuer issue-201 mocks-removal.
