---
entity_id: test_hygiene_754_755_756
type: module
created: 2026-06-11
updated: 2026-06-11
status: draft
version: "1.0"
tags: [tests, hygiene, telegram, e2e, cleanup]
---

<!-- Issues #754, #755, #756 — Test-Hygiene-Sweep (Nebenbefunde aus #753/#744) -->

# Test-Hygiene-Sweep #754 + #755 + #756

## Approval

- [ ] Approved

## Purpose

Drei Nebenbefunde abräumen, die die Test-Suite verlogen oder dauerrot machen und damit
echte Regressionen maskieren:

1. **#754** — 19 `tests/tdd`-Dateien prüfen Quelltext (`assert 'xyz' in file.read_text()`
   auf `.svelte`/`.ts`: CSS-Klassen, Tokens, `data-testid`) statt nutzersichtbares
   Verhalten. Verstößt gegen CLAUDE.md "Dateiinhalt-Checks sind VERBOTEN". 6 davon sind
   bereits falsch-rot.
2. **#755** — `frontend/e2e/issue-88-report-config-dialog.spec.ts` testet den entfernten
   Signal-Kanal (`channel-signal`, #610). Toter Test, der gegen einen echten Browser nie
   grün wird.
3. **#756** — 4 stale Telegram-E2E-Tests erwarten das alte "eine Nachricht"-Verhalten,
   obwohl der On-demand-Flow (#697/#704) Loading + In-place-Edit macht.

**Scope: test-/tooling-only.** Keine Produkt-Code-Änderung in `src/`, `api/`, `internal/`,
`frontend/src/`. Kein Prod-Deploy. Verifikation läuft lokal über `uv run pytest` (Python)
bzw. statische Locator-Konsistenz für die Playwright-Specs.

## Source

- **Files (#754):** 19 Dateien in `tests/tdd/` — siehe Issue #754. Pro Datei Einzelurteil:
  Struktur-Asserts löschen (durch echtes E2E gedeckt) / auf Playwright-E2E umstellen /
  obsolete Datei löschen. **Sonderfall** `test_issue_456_auto_briefings.py`: gemischt —
  echte Verhaltenstests (`run_comparison_for_subscription`, `top_ort_letzter_versand`)
  behalten/reparieren, nur die `read_text`-Asserts entfernen.
- **File (#755):** `frontend/e2e/issue-88-report-config-dialog.spec.ts` — Signal-AC-4-Test
  (Z.190–219) + Header-Kommentare (Z.14–15) entfernen.
- **File (#755):** `frontend/e2e/trip-wizard-step4.spec.ts` — verbleibende
  `channel-signal`-Referenz bereinigen.
- **File (#756):** `tests/tdd/test_e2e_telegram_pipeline.py` — capture-Fixture (Z.160)
  liefert `message_id`; AC-1/AC-2/AC-4-Asserts auf Loading-`send` + `editMessageText`
  umstellen.
- **File (#756):** `tests/tdd/test_inbound_telegram_reader.py` — `test_hilfe_command_in_processor`
  Hilfetext-Assert auf den konsolidierten #731-Befehlssatz aktualisieren.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/e2e/*.spec.ts` | E2E-Suite | Bestehende Coverage als Ersatz für gelöschte Struktur-Asserts |
| `src/services/inbound_telegram_reader.py` | Prod (read-only) | Referenz Loading+Edit-Verhalten — wird NICHT geändert |
| `pytest` / Playwright | Tooling | Verifikation grün vs. rot |

## Acceptance Criteria

**AC-1:** Given die 19 in #754 gelisteten `tests/tdd`-Dateien;
When der Sweep abgeschlossen ist;
Then enthält keine dieser Dateien mehr einen `read_text()`/`.exists()`-basierten Assert
auf den Inhalt einer `.svelte`- oder `.ts`-Quelldatei (CSS-Klasse, Token, `data-testid`),
es sei denn die Datei ist mit `# doc-compliance-test` markiert und prüft ein
Workflow-Artefakt (kein Produkt-Quelltext).

**AC-2:** Given jeder in #754 gelöschte Struktur-Assert;
When er entfernt wird, weil das Verhalten "bereits durch E2E gedeckt" gilt;
Then existiert ein konkret benennbarer grüner E2E-Test (`frontend/e2e/*.spec.ts`), der das
gleiche nutzersichtbare Verhalten prüft — die Zuordnung ist im Execution-Log dokumentiert.
Wo keine Deckung existiert und das Verhalten relevant ist, wird stattdessen auf einen
echten Playwright-E2E-Test umgestellt; nur obsolete (Design überholt) Dateien werden
ersatzlos gelöscht.

**AC-3:** Given `tests/tdd/test_issue_456_auto_briefings.py`;
When der Sweep abgeschlossen ist;
Then bleiben die echten Verhaltenstests (`run_comparison_for_subscription` gibt 4-Tupel,
`top_ort_letzter_versand`-Persistenz) erhalten und sind grün (Test-Setup repariert), während
nur die `read_text`-Asserts entfernt sind.

**AC-4:** Given die Telegram-Inbound-On-demand-Pfade (glance/timeline/heute/morgen);
When ein Text-Befehl durch die Pipeline läuft und die capture-Fixture eine `message_id`
liefert (wie echtes Telegram);
Then beweisen `test_e2e_telegram_pipeline.py` AC-1/AC-2/AC-4 das reale Verhalten — genau
eine Loading-`sendMessage` (⏳) gefolgt von einem `editMessageText` mit Inhalt und
`reply_markup` — und sind grün. Kein Test erwartet mehr fälschlich genau einen
`sendMessage`.

**AC-5:** Given `tests/tdd/test_inbound_telegram_reader.py::test_hilfe_command_in_processor`;
When er ausgeführt wird;
Then asserted er gegen den konsolidierten #731-Befehlssatz (heute/morgen/jetzt/gewitter/
ruhetag/status/stop/weiter/hilfe) und nicht mehr gegen entfernte Befehle (`startdatum`),
und ist grün.

**AC-6:** Given die gesamte betroffene Python-Test-Menge (#754-Dateien + #756-Telegram-Tests);
When `uv run pytest` über diese Dateien läuft;
Then ist sie vollständig grün (kein falsch-rot mehr), und ein projektweiter Grep findet
keine `channel-signal`-Referenz mehr in `frontend/e2e/` oder `tests/`.

## Out of Scope

- Jede Änderung an Produkt-Code (`src/`, `api/`, `internal/`, `frontend/src/`).
- Neue Features oder Verhaltensänderungen am Telegram-Flow.
- Prod-Deploy (Scope ist test-/tooling-only).

## Changelog

- 2026-06-11: Initiale Spec aus Issues #754/#755/#756 (Nebenbefunde #753/#744).
