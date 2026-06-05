# Context: bug-567-stale-deploy-refs

## Request Summary
Veraltete `/7-deploy`- und `"approved"`-Referenzen in `.claude/commands/README.md` und `5-implement.md` korrigieren — Adversary-Finding F002 aus #563.

## Related Files
| File | Relevance |
|------|-----------|
| `.claude/commands/README.md` | Phase-Tabelle (Z. 17, 22) + Beispiele (Z. 67, 91) + State-Liste (Z. 192) |
| `.claude/commands/5-implement.md` | Verweis auf `/7-deploy` in Abschluss-Brief (Z. 237) |

## Existing Patterns
- #563 hat in `CLAUDE.md` die analogen Stellen schon korrigiert: `"approved"` → `"go"`, `/7-deploy` → `—` / `/6-validate` Step 5.

## Dependencies
- Upstream: keine
- Downstream: keine (reine Doku, keine Hook/Code-Ausführung)

## Existing Specs
- keine — Doku-Bereinigung ohne Verhalten

## Risks & Considerations
- Z. 13 `phase4_approved` ist ein State-Name (kein Keyword) — NICHT ändern
- Z. 67 "Read the approved spec" = "freigegebene Spec", kein Keyword — NICHT ändern
- Reine Doku-Änderung → Post-Push-Workflow Doku-Only-Ausnahme greift (kein Prod-Deploy)
