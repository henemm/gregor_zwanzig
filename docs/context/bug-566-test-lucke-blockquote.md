# Context: Bug #566 — Test-Lücke: Blockquote-Regression in 5-implement.md und 7-deploy.md

## Request Summary
Issue #566 erweitert den Test `test_bug_548_workflow_output_readability.py` um zwei fehlende Testfälle, die Blockquote-Regressionen in `5-implement.md` (Validator-Ergebnis-Ausgabe) und `7-deploy.md` (Fertig-und-live-Abschluss) abfangen. Der eigentliche Fix (Commit `97a4807c`) ist bereits deployed; die Tests fehlen noch.

## Related Files
| File | Relevance |
|------|-----------|
| `tests/tdd/test_bug_548_workflow_output_readability.py` | Bestehende Testdatei — hier werden die zwei neuen Tests ergänzt |
| `.claude/commands/5-implement.md` | Enthält `**Validator-Ergebnis:**` (Z.197) und `Implementation complete. Adversary verified.` (Z.243) |
| `.claude/commands/7-deploy.md` | Enthält `**Fertig und live.**` (Z.101) |

## Existing Patterns
- Alle bestehenden Tests (`test_analyse_...`, `test_write_spec_...`, `test_tdd_red_...`, `test_deploy_...`) folgen demselben Muster:
  1. Datei lesen
  2. Ankerpunkt-String suchen (`content.find(...)`)
  3. Einen Textausschnitt ab dem Ankerpunkt nehmen (~200–800 Zeichen)
  4. Zeilen mit `>` Prefix UND spezifischen Keywords aus dem Ausschnitt filtern
  5. `assert blockquote_lines == []`
- Bestehende Klasse: `TestNoBlockquoteInPOSummaries` in derselben Datei

## Neues Verhalten (nach Commit `97a4807c`)
- `7-deploy.md` Z.101: `**Fertig und live.** Issue #N — [Titel] ist abgeschlossen.` — kein `>`
- `5-implement.md` Z.197: `**Validator-Ergebnis:** [VERIFIED / BROKEN / AMBIGUOUS]` — kein `>`
- `5-implement.md` Z.243: `Implementation complete. Adversary verified. Ready for `/validate`.` — kein `>`

## Neue Tests
1. **`test_deploy_no_blockquote_in_fertig_und_live`** — prüft `7-deploy.md` ab Ankerpunkt `"Fertig und live"`:
   - Keywords: `"Fertig und live"`, `"abgeschlossen"`, `"geliefert"`
2. **`test_implement_no_blockquote_in_validator_result`** — prüft `5-implement.md` ab Ankerpunkt `"Validator-Ergebnis"`:
   - Keywords: `"Validator-Ergebnis"`, `"VERIFIED"`, `"BROKEN"`, `"AMBIGUOUS"`, `"Implementation complete"`, `"Adversary verified"`

## Dependencies
- Upstream: `tests/tdd/test_bug_548_workflow_output_readability.py` (wird erweitert)
- Downstream: keine

## Existing Specs
- Kein eigener Spec nötig — reine Testergänzung mit klarer Issue-Diagnose

## Risks & Considerations
- Sehr geringes Risiko: Nur neue Tests werden ergänzt, kein Produktionscode
- Tests müssen GREEN sein (Fix ist bereits deployed)
- Ankerpunkt-Suche muss eindeutig sein (kein Fehler wenn String mehrfach vorkommt)
