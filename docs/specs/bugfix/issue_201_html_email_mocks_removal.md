---
entity_id: issue_201_html_email_mocks_removal
type: bugfix
created: 2026-05-12
updated: 2026-05-12
status: draft
version: "1.0"
tags: [bugfix, tests, mock-removal, memory-violation, prep-for-129a3]
---

<!-- GitHub Issue #201 — Mocks aus tests/tdd/test_html_email.py entfernen -->

# Issue #201 — SMTP-Mocks aus `test_html_email.py` entfernen

## Approval

- [ ] Approved

## Purpose

Die Memory-Regel **"KEINE MOCKED TESTS!"** (siehe `CLAUDE.md` Sektion „KEINE MOCKED TESTS! (KRITISCH!)") wird in `tests/tdd/test_html_email.py` an mehreren Stellen verletzt: `MockSMTP`-Klassen, `patch("smtplib.SMTP", …)` und `settings = Mock()` in 3 von 5 Test-Klassen. Im Adversary-Lauf von Workflow `epic-129a-1-compare-helpers` als pre-existing Verstoß identifiziert (LOW severity, aber sofort blockierend für Phase #129 A.3).

Bonus-Effekt: Die Datei importiert noch von `web.pages.compare` — nach dem Refactor zeigen die Imports auf die neuen Service-Module, was Phase #129 A.3 entlastet (sonst müsste A.3 die Imports zusätzlich umbauen).

## Source

- **File:** `tests/tdd/test_html_email.py` (638 LoC)
- **Identifier:** 5 Test-Klassen — 3 zu löschen, 2 zu behalten

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `tests/tdd/test_html_email.py::TestRealGmailE2E` | test class | Source of Truth für E-Mail-Verhalten — bleibt erhalten |
| `app.user.{SavedLocation, CompareSubscription, ComparisonResult, LocationResult}` | DTOs | Werden von verbleibenden Tests genutzt |
| `services.comparison_renderers.render_comparison_html` (NEU seit A.1) | Helper | Wird von `TestSubscriptionEmailGeneration` aufgerufen |
| `services.compare_subscription.run_comparison_for_subscription` | Service | Wird von `TestSubscriptionEmailGeneration` aufgerufen |
| `outputs.email.EmailOutput` | Service | Wird von `TestRealGmailE2E` aufgerufen |

## Implementation Details

### 5 Test-Klassen — Aktion pro Klasse

| Klasse | Tests | Aktion | Begründung |
|--------|-------|--------|------------|
| `TestHTMLEmailFormat` (Z. 17-104) | 6 | **LÖSCHEN** | Keine Mocks, aber Coverage 1:1 in `TestRealGmailE2E::test_real_gmail_e2e_html_email` (Z. 525-544): DOCTYPE, `<table>`, CSS-Styling, keine ASCII-Borders. Echte E2E > Unit-Test mit Fixtures. |
| `TestSubscriptionEmailGeneration` (Z. 106-168) | 1 | **BEHALTEN** | Keine Mocks. Testet Generierungs-Pipeline (`run_comparison_for_subscription`) ohne Versand → ergänzt `TestRealGmailE2E` (das den Versand testet). Schnell, ohne Netz. |
| `TestEndToEndEmailSending` (Z. 170-414) | 3 | **LÖSCHEN** | `MockSMTP` (Z. 206, 298, 364) + `patch("smtplib.SMTP", MockSMTP)` (Z. 241, 322, 388) + `settings = Mock()` (Z. 183). Coverage 1:1 in `TestRealGmailE2E`: multipart/alternative-Struktur, HTML-Part, Plain-Text ohne CSS — alles dort mit echtem Gmail. |
| `TestRealGmailE2E` (Z. 417-550) | 1 | **BEHALTEN (primär)** | Memory-Referenz, mock-frei. `@pytest.mark.email`-marker. Source of Truth. |
| `TestEmailRetryMechanism` (Z. 553-638) | 2 | **LÖSCHEN** | `MockSMTP` (Z. 587, 625) + `patch("smtplib.SMTP", MockSMTP)` (Z. 603, 629) + `patch("time.sleep")` (Z. 604, 630). Memory-Regel ist hier kompromisslos: "NIEMALS Mock(), patch(), oder MagicMock fuer E-Mail/API Tests verwenden!". Retry-Verhalten ist EmailOutput-Implementierungsdetail; bei kaputter Retry-Logic merken wir es in `TestRealGmailE2E` (Mail kommt nicht an) bzw. Production-Logs. |

### Imports umstellen (Vorbereitung für #129 A.3)

Aktuell (Z. 14):
```python
from web.pages.compare import render_comparison_html, run_comparison_for_subscription
```

Neu:
```python
from services.comparison_renderers import render_comparison_html
from services.compare_subscription import run_comparison_for_subscription
```

Weitere Imports anpassen:
- `from unittest.mock import patch, Mock` (Z. 10) — **vollständig entfernen** (keine Mocks mehr genutzt)

### Was BLEIBT in der Datei

Nach dem Refactor: ~200 LoC, **2 Test-Klassen mit insgesamt 2 Tests**:
- `TestSubscriptionEmailGeneration::test_subscription_generates_html_email_with_real_data` (1 Test, schnell, ohne Netz)
- `TestRealGmailE2E::test_real_gmail_e2e_html_email` (1 Test, `@pytest.mark.email`, braucht Gmail-Creds)

## Expected Behavior

- **Pre-Refactor:** 13 Tests in der Datei. 5 Tests nutzen `MockSMTP` oder `Mock()`. Imports zeigen auf `web.pages.compare`.
- **Post-Refactor:** 2 Tests. 0 Mocks. Imports zeigen auf `services.*`.
- **Side effects:** Datei schrumpft von 638 auf ~200 LoC. Keine funktionale Änderung am Production-Code.
- **CI-Verhalten:** `pytest tests/tdd/test_html_email.py -v` führt 1 Test aus (`TestSubscriptionEmailGeneration`), `TestRealGmailE2E` ist via Marker nur mit `pytest -m email` aktiv (unverändert).

## Acceptance Criteria

- **AC-1:** Given die Datei `tests/tdd/test_html_email.py` / When `grep -nE "^from unittest\.mock\|^import mock\|MockSMTP\|patch\(\"smtplib|patch\(\"time|settings = Mock\(\)\|= Mock\(\)" tests/tdd/test_html_email.py` läuft / Then **0 Treffer** — Mocks vollständig entfernt.
  - Test: (populated after /tdd-red)

- **AC-2:** Given die Datei nach dem Refactor / When `grep -c "^class Test" tests/tdd/test_html_email.py` läuft / Then Output **2** (genau zwei Test-Klassen: `TestSubscriptionEmailGeneration`, `TestRealGmailE2E`). Klassen `TestHTMLEmailFormat`, `TestEndToEndEmailSending`, `TestEmailRetryMechanism` sind weg.
  - Test: (populated after /tdd-red)

- **AC-3:** Given die Imports in `tests/tdd/test_html_email.py` / When grep nach `from web.pages.compare`, `from src.web.pages.compare` läuft / Then **0 Treffer**. Imports zeigen stattdessen auf `services.comparison_renderers` und `services.compare_subscription`.
  - Test: (populated after /tdd-red)

- **AC-4:** Given die übrig gebliebene Datei / When `uv run pytest tests/tdd/test_html_email.py -v --collect-only` läuft / Then es werden **genau 2 Tests** gesammelt: `TestSubscriptionEmailGeneration::test_subscription_generates_html_email_with_real_data` und `TestRealGmailE2E::test_real_gmail_e2e_html_email`.
  - Test: (populated after /tdd-red)

- **AC-5:** Given die übrig gebliebene Datei / When `uv run pytest tests/tdd/test_html_email.py -v` läuft (ohne `-m email`) / Then **1 Test PASS** (`TestSubscriptionEmailGeneration`), 1 Test SKIPPED (`TestRealGmailE2E` via marker). **0 FAIL**.
  - Test: (populated after /tdd-red)

## Out of Scope

- **Refactor-Hilfsmittel** wie `aiosmtpd` (lokaler SMTP-Test-Server) für eine eventuelle Retry-Test-Wiedereinführung → später, wenn jemand das echt braucht.
- **Andere Test-Files mit Mocks** → nicht Teil dieses Workflows. Falls es weitere gibt, separates Issue.
- **`/tmp/gregor_email_test/`-Cleanup in `TestRealGmailE2E`** (Adversary-Hinweis Z. 497-499) → eigenes Issue falls relevant.

## Verification

- **Unit (scoped):** `uv run pytest tests/tdd/test_html_email.py -v` muss grün laufen (1 PASS + 1 SKIP).
- **Optional E2E:** `uv run pytest tests/tdd/test_html_email.py -v -m email` (braucht Gmail-Creds) — sollte grün sein.
- **Full-Suite-Smoke:** `uv run pytest tests/ -q --tb=short` — vergleichen mit Baseline (vor #201): 11 Tests weniger gesammelt, sonst keine Regression.
- **Memory-Compliance:** `grep -rn "from unittest.mock\|MockSMTP" tests/tdd/test_html_email.py` → 0 Treffer.

## LoC-Estimate

- **`test_html_email.py`:** 638 → ~200 LoC (-438 LoC, alles Löschungen)
- **Keine neuen Files**
- **Imports:** 1-2 Zeilen geändert

**Erwartetes LoC-Delta:** netto -438 LoC. Liegt unter Default-Limit 250 — also kein Override nötig.

## Risks

| Risiko | Wahrscheinlichkeit | Mitigation |
|--------|-------------------|------------|
| `TestSubscriptionEmailGeneration` bricht nach Import-Update auf `services.*` | niedrig | AC-5 (Test läuft grün), Imports sind 1:1-Umstellung (Funktion gleich, nur Pfad) |
| Eine gelöschte Test-Klasse hat doch noch wertvolle Coverage, die `TestRealGmailE2E` nicht abdeckt | niedrig | Phase-2-Analyse hat 1:1-Coverage-Mapping nachgewiesen |
| Retry-Verhalten wird unbemerkt kaputt | mittel | Production-Logs zeigen es bei E-Mail-Versand-Fehler. Falls künftig kritisch: separates Issue für aiosmtpd-basierten Test |
| `@pytest.mark.email`-Marker nicht mehr unique → CI führt `TestRealGmailE2E` plötzlich aus | sehr niedrig | Marker bleibt unverändert |
