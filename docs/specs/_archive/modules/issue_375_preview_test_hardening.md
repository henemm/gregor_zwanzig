---
entity_id: issue_375_preview_test_hardening
type: module
created: 2026-05-25
updated: 2026-05-25
status: draft
version: "1.0"
tags: [test, preview, signal, telegram, epic-331, issue-363, issue-375]
---

# Vorschau-Test-Hardening (vertagte #363-Nits)

## Approval

- [ ] Approved (User, ____-__-__)

## Purpose

Schließt die beiden vertagten Test-Lücken aus #363 (Epic #331). **Reines, additives
Test-Hardening — kein Produktionscode wird geändert.** Die zugrunde liegende
Implementierung (#363) ist nachweislich korrekt und live; die beiden bestehenden Tests
prüfen je eine Eigenschaft nur halb. Da kein Verhalten neu entsteht, gibt es **keinen
RED-Zustand** — die ergänzten Assertions sind sofort grün und sichern bestehend-korrektes
Verhalten gegen künftige Regression ab.

## Source

- **Geändert:** `internal/handler/preview_proxy_test.go` — der vorhandene
  `TestPreviewProxyHandlerForwardsTelegramChannel` erhält eine `user_id`-Injektions-Assertion
  (dispatcht mit Nicht-Default-User, prüft `user_id=<user>` in der Upstream-URL), analog zum
  bereits vorhandenen Signal-Test.
- **Geändert:** `tests/tdd/test_issue_363_signal_telegram_preview.py` —
  `test_ac3_signal_body_differs_from_sms_and_email` vergleicht zusätzlich explizit
  Signal-`body` ≠ Telegram-`body`.

> Schicht: ausschließlich Test-Dateien (Go-Handler-Test + Python-TDD-Test). Keine `src/`-,
> `api/`-, `cmd/`- oder `frontend/`-Änderung.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `issue_363_signal_telegram_preview.md` AC-5 | spec | Vertrag „`user_id` aus Auth-Context injiziert" — Go-Nit schließt die Telegram-Hälfte |
| `issue_363_signal_telegram_preview.md` AC-3 | spec | Vertrag „eigenständiges Kanal-Rendering" — Python-Nit ergänzt signal≠telegram |
| `internal/handler/preview_proxy.go` `PreviewProxyHandler` | handler | bereits korrekt (channel-parametrisiert) — nur Test-Abdeckung fehlt |

## Expected Behavior

- **Input:** keine Verhaltensänderung; nur erweiterte Test-Assertions.
- **Output:** beide ergänzten Assertions sind grün; die jeweils umgebenden Test-Funktionen
  bleiben funktional gleich.
- **Side effects:** keine.

## Acceptance Criteria

- **AC-1:** Given den Go-Test `TestPreviewProxyHandlerForwardsTelegramChannel` / When der
  Telegram-Proxy-Handler über einen Auth-Context mit einem Nicht-Default-User (z. B. `"bob"`)
  dispatcht wird / Then assertet der Test, dass die an Python weitergeleitete Upstream-URL
  `user_id=bob` enthält — wie der Signal-Test es bereits tut (schließt die #363-AC-5-Lücke für Telegram).
  - Test: `internal/handler/preview_proxy_test.go::TestPreviewProxyHandlerForwardsTelegramChannel`

- **AC-2:** Given den Python-Test `test_ac3_signal_body_differs_from_sms_and_email` / When
  Signal- und Telegram-Vorschau für denselben Trip abgerufen werden (beide 200) / Then assertet
  der Test zusätzlich explizit `signal_body != telegram_body`, über die bestehenden
  signal≠sms- und signal≠email-Vergleiche hinaus (eigenständiges Kanal-Rendering, #363-AC-3).
  - Test: `tests/tdd/test_issue_363_signal_telegram_preview.py::test_ac3_signal_body_differs_from_sms_and_email`

## Known Limitations

- Kein neuer Test-Fall, sondern Erweiterung bestehender Funktionen — bewusst minimal-invasiv.
- Beide Assertions bestätigen bereits live korrektes Verhalten; sie können nicht „RED" gemacht
  werden, ohne die korrekte #363-Implementierung künstlich zu brechen.

## Changelog

- 2026-05-25: Initial spec (Test-Hardening der vertagten #363-Nits, Issue #375)
