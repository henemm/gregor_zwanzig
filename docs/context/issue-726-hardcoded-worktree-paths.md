# Context: Issue #726 — hartkodierte Fremd-Worktree-Pfade im Test

## Request Summary
`test_format_trend_tokens_is_sole_threshold_evaluator` (Z.685-688) öffnet Renderer-Dateien über absolute Pfade auf einen fremden Worktree (`idempotent-strolling-cray`) → `FileNotFoundError` in jedem anderen Worktree und im Hauptrepo. Pfade sollen relativ zum Repo-Root aufgelöst werden.

## Related Files
| File | Relevance |
|------|-----------|
| `tests/tdd/test_issue_623_trend_channels.py` (Z.685-715) | Enthält den `# doc-compliance-test` mit den hartkodierten Pfaden — einzige zu ändernde Datei |
| `src/output/renderers/email/html.py` | Zielobjekt 1 des Compliance-Checks (existiert relativ zum Repo-Root) |
| `src/output/renderers/email/plain.py` | Zielobjekt 2 |
| `src/output/renderers/narrow.py` | Zielobjekt 3 |

## Existing Patterns
- Repo-Root-Auflösung in Tests: `Path(__file__).resolve().parents[2]` (von `tests/tdd/<file>.py` → Repo-Root). Verifiziert: liefert den aktuellen Worktree-Root.
- Der Test ist als `# doc-compliance-test` markiert (Ausnahme von der „keine Dateiinhalt-Checks"-Regel laut CLAUDE.md) — diese Markierung bleibt erhalten.

## Dependencies
- Upstream: `pathlib.Path`, `__file__`
- Downstream: Nichts — reiner Struktur-/Compliance-Test, kein Produktionscode betroffen.

## Existing Specs
- Keine Entity-Spec betroffen (reiner Test-Fix). AC-N-Spec wird in Phase 3 angelegt.

## Risks & Considerations
- **Kein Produktionsbug** — pre-existing rot, verschmutzt jeden Validierungslauf.
- Trivialer Fix (+wenige LoC): Liste der absoluten Pfade durch `REPO_ROOT / "src/output/renderers/..."` ersetzen.
- **Begleit-Fund (OUT OF SCOPE):** `test_issue_613_email_redesign.py::TestAC6SectionsPreserved` ist ebenfalls vorbestehend rot (Footer `report morning` durch #670 geändert) — laut Issue-Body in #723 (Slice 3) mitbereinigt, nicht hier.
- Nach Fix muss der Test grün sein **und** weiterhin echte Threshold-Verstöße in den Renderern erkennen (Bad-Patterns unverändert).
