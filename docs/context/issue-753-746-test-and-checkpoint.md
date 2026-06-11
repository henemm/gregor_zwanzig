# Context: Issue #753 (verbotener Datei-Inhalt-Test) + #746 (user-story-planner Checkpoint)

## Request Summary
Zwei unabhängige Tooling-/Test-Hygiene-Bugs in einem Workflow:
- **#753:** `tests/tdd/test_issue_299_edit_report_config_polish.py` prüft Verhalten nicht aus Nutzersicht, sondern liest `.svelte`-Quelltext und assertet auf CSS-Klassen/Testids — Verstoß gegen die CLAUDE.md-Regel „Dateiinhalt-Checks sind VERBOTEN".
- **#746:** Der `user-story-planner`-Agent legt GitHub-Issues an (Phase 5), ohne dass der PO Story + ACs + Feature-Breakdown vorher bestätigt hat.

## Related Files
| File | Relevance |
|------|-----------|
| `tests/tdd/test_issue_299_edit_report_config_polish.py` | #753 Hauptziel — 16 Asserts auf `COMPONENT.read_text()`, prüft CSS-Klassen/Testids |
| `docs/specs/modules/issue_299_edit_report_config_section_polish.md` | Obsolete Spec zu #299 (Cosmetic-Polish) |
| `frontend/src/lib/components/edit/EditReportConfigSection.svelte` | Geprüfte Komponente — seit #299 zweimal reworked (#693 Gruppen, #723 Eindampfung) |
| `frontend/e2e/issue-88-report-config-dialog.spec.ts` | Echter E2E gegen Reports-Tab, nutzt die Testids unabhängig |
| `.claude/agents/user-story-planner.md` | #746 Hauptziel — Phase 5 läuft automatisch nach Phase 4 durch |

## Befund #753: Test ist aktuell ROT — und zwar falsch
`test_regression_all_required_testids_present` fordert `channel-signal` + `channel-signal-hint`. Signal wurde aber app-weit entfernt (#610, 2026-06-06). Der Test bricht also **nicht wegen geändertem Verhalten**, sondern weil er auf Quelltext-Artefakte eines entfernten Features assertet — exakt die Brüchigkeit, die #723-F002/#753 anprangern.

Die geprüften ACs (AC-1..AC-7) sind reine **Cosmetic-Polish**-Checks (Pill-Form, Accent-Farbe, Ghost-Btn, Card-Wrapper). Das sind Implementierungsdetails, kein nutzersichtbares Verhalten. CLAUDE.md (Design-Leitprinzipien) ordnet Kosmetik ausdrücklich unter — ein schwerer Playwright-Computed-Style-Suite wäre selbst brüchig und für obsolete Optik nicht gerechtfertigt.

## Anti-Pattern-Surface (#753 „weitere Dateien prüfen")
23 Dateien in `tests/tdd/` lesen `.svelte`/`.ts`-Quelltext via `read_text()` ohne `# doc-compliance-test`-Marker:
test_issue_299, _285, _323, _326, _278, _259, _315, _180, _456, _339, _bug_328, _bug_382, _bug_272, _bug_330, _bug_281_290, _bug_541_543_544, _bug590, _bug707, _alert_rules_model, _metric_entry_cleanup, _trips_naming u.a.
→ Vollständiger Sweep sprengt das 250-LoC-Limit und erfordert pro Datei Einzelurteil. **Empfehlung: Follow-up-Issue** für den systematischen Sweep + Regressions-Guard.

## #746: Fix laut Issue selbst spezifiziert
Harter Checkpoint zwischen Phase 4 und Phase 5 in `user-story-planner.md`: Story (Als/möchte/damit) + ACs + Feature-Liste dem PO präsentieren, auf explizite Bestätigung warten, sonst STOP (keine Issues, kein Dokument). Schadensfall: #737–#743 ohne PO-Bestätigung angelegt.

## Existing Patterns
- `# doc-compliance-test`-Marker = erlaubte Ausnahme für Workflow-Artefakt-Tests (z.B. `test_bug720_tripeditview_spread_fix.py` mit 9 Markern).
- STOP-Conditions im user-story-planner existieren bereits (Phase-übergreifend) — Checkpoint reiht sich konsistent ein.

## Dependencies
- Upstream: keine (Test-Löschung + Markdown-Edit).
- Downstream: `issue-88-report-config-dialog.spec.ts` nutzt Testids unabhängig → Löschung des Python-Tests verliert keine Abdeckung.

## Risks & Considerations
- **Scope #753:** delete vs. migrate. Empfehlung delete (obsolet, Komponente 2× reworked, Test aktuell falsch-rot, Kosmetik). Migrate zu Playwright = Aufwand für obsolete Optik.
- **Test-Coverage:** Löschen reduziert Test-Zahl — aber die gelöschten Asserts beweisen ohnehin kein Verhalten.
- **Scope-Klassifikation:** Beide Änderungen sind tooling/test/docs-only (kein `src/`) → Docs-/Tooling-Ausnahme, voraussichtlich kein Prod-Deploy.
