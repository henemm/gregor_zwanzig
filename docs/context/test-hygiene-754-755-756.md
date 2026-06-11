# Context: Test-Hygiene-Sweep #754 + #755 + #756

## Request Summary
Drei Nebenbefunde aus #753/#744 abräumen: verbotene Datei-Inhalt-Tests (19 Dateien),
ein toter Signal-E2E-Test und 4 stale Telegram-E2E-Tests. Ziel: ehrliche, grüne
Test-Suite ohne Code-Analyse-Asserts, die echte Regressionen maskieren.

## Drei Issues im Detail

### #754 — 19 `tests/tdd`-Dateien mit Datei-Inhalt-Anti-Pattern
`assert 'xyz' in file.read_text()` auf `.svelte`/`.ts`-Quelltext (CSS-Klassen, Tokens,
`data-testid`). Verstößt gegen CLAUDE.md "Dateiinhalt-Checks sind VERBOTEN". Keine als
`# doc-compliance-test` markiert. **5 bereits falsch-rot** (brechen an überholtem
Quelltext): `test_bug_281_290_stagestrip`, `test_bug_328_savepreset_tokens`,
`test_bug_541_543_544`, `test_issue_278_form_controls`, `test_issue_456_auto_briefings`
(letzteres ist evtl. ein echter Verhaltenstest — gesondert prüfen!), `test_trips_naming`.
Pro Datei Einzelurteil: (1) durch echtes E2E abgedeckt → Struktur-Asserts löschen,
(2) relevant aber ungedeckt → auf Playwright-E2E umstellen, (3) obsolet → löschen.

### #755 — toter E2E `issue-88-report-config-dialog.spec.ts`
AC-4-Test (Z.190–219) prüft `channel-signal`/`channel-signal-hint`. Signal ist seit #610
(2026-06-06) app-weit entfernt → Testids existieren nicht mehr → Locator timeoutet.
Header-Kommentare (Z.14–15) listen die Testids noch. Test entfernen + Kommentare bereinigen
+ weitere Specs auf `channel-signal` prüfen.

### #756 — 4 stale Telegram-E2E-Tests
`test_e2e_telegram_pipeline.py` AC-1/AC-2/AC-4 + `test_inbound_telegram_reader.py::test_hilfe_command_in_processor`.
**Punkt 2 geklärt: KEIN Produkt-Bug.** Prod-Code (`inbound_telegram_reader.py:196-217`)
macht korrekt `send`(Loading ⏳) + `edit_message_text`(Ergebnis in-place). Der Fake-Capture-Server
im Test (`test_e2e_telegram_pipeline.py:160`) liefert `{"ok":true,"result":{}}` **ohne
`message_id`** → `loading_mid is None` → Fallback-`else` (Z.210) feuert einen zweiten `send`
→ Test sieht 2× `sendMessage`. Fix: Fixture liefert `message_id` → echter Edit-Pfad wird
ausgeübt → Asserts auf Loading-`send` + `editMessageText` umstellen.
`test_hilfe_command_in_processor` ist separat stale: asserted `"startdatum"`, aber der
Hilfetext wurde in #731 konsolidiert (CONFIG/startdatum entfernt).

## Related Files
| File | Relevance |
|------|-----------|
| `tests/tdd/test_*` (19 Dateien aus #754) | Datei-Inhalt-Asserts entfernen/umstellen |
| `frontend/e2e/issue-88-report-config-dialog.spec.ts` | toten Signal-Test (Z.190–219) + Header (Z.14–15) entfernen |
| `tests/tdd/test_e2e_telegram_pipeline.py` | capture-Fixture (Z.160) message_id liefern; AC-1/2/4 Asserts |
| `tests/tdd/test_inbound_telegram_reader.py` | `test_hilfe_command_in_processor` Hilfetext-Assert |
| `frontend/e2e/*.spec.ts` | bestehende E2E-Coverage als Ersatz für gelöschte Struktur-Asserts |
| `src/services/inbound_telegram_reader.py:196-217` | Prod-Referenz (Loading+Edit) — wird NICHT geändert |

## Existing Patterns
- Verhaltensnachweis statt Code-Analyse: Playwright-E2E gegen Staging als eingeloggter Nutzer (CLAUDE.md).
- `# doc-compliance-test`-Marker nur für echte Workflow-Artefakt-Prüfungen.
- Boundary-Capture via lokalem HTTP-Server (kein Mock) — etabliertes Telegram-E2E-Muster.
- Vorbild #753: gelöschten Datei-Inhalt-Test durch vorhandenes echtes E2E ersetzt.

## Dependencies
- Upstream: keine Produkt-Code-Änderung (nur Tests + 1 Test-Fixture).
- Downstream: Test-Gates / Telegram-E2E-Gate werden ehrlicher (weniger Dauerrot).

## Existing Specs
- Bezug #610 (Signal entfernt), #731 (Antwort-Kommandos konsolidiert), #697/#704 (On-demand-Loading-Flow).
- `docs/specs/modules/issue_672_telegram_e2e_pipeline.md` (Telegram-E2E-Pipeline).

## Risks & Considerations
- **`test_issue_456_auto_briefings`** ist evtl. ein echter Verhaltenstest (run_comparison-Tuple),
  KEIN Datei-Inhalt-Anti-Pattern — nicht blind löschen, gesondert beurteilen.
- LoC-Guard zählt Löschungen → Override nötig (wie #753).
- Scope ist **test/tooling-only** (keine `src/`-, `api/`-, `internal/`-, `frontend/src/`-Änderung)
  → kein Prod-Deploy (CLAUDE.md Tooling-Ausnahme; `tests/` = neutraler Pfad).
- Pro gelöschtem Struktur-Assert sicherstellen, dass das Verhalten wirklich durch ein
  grünes E2E gedeckt ist (sonst Coverage-Loch) — Vorbild #753-Adversary.
- #755: auch andere Specs auf `channel-signal` greppen (Issue fordert das explizit).
