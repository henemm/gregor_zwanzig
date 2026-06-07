# Context: Issue #634 — Cleanup Forecast-Treffer-Quote

## Request Summary
Letzte zwei Code-Reste der von Claude Design erfundenen Forecast-Treffer-Quote
(`accuracy_pct` / „Treffer Ø") entfernen. PO-Frage: evtl. liegt schon Arbeit herum
oder ist fertig.

## Befund (Stand 2026-06-07)
- **NICHT auf `main`** (HEAD 3ab06251). AC-1 noch offen.
- **Geister-Arbeit** liegt uncommittet im Nachbar-Worktree `pure-honking-horizon`
  (Basis 09df8ddb, hinter main, vermischt mit dem bereits gemergten #616).
  Beim #616-Harvest wurde #634 bewusst ausgelassen (Memory `project_issue_616_done`).
- Bestehender Workflow `issue-634-treffer-quote-cleanup` steht in `phase6b_adversary`
  mit Verdict `BROKEN:Could not determine test result.` — klassischer Stale-Base-Fehlalarm.
- Spec + Context + e2e-Test wurden bereits geschrieben (in pure-honking-horizon).

## Die 3 ACs — IST-Stand auf main
| AC | Beschreibung | Stand main | Geister-Arbeit |
|----|--------------|-----------|----------------|
| AC-1 | Demo-`Stat` „Treffer Ø"/„87%" in `_design-system/+page.svelte:619` ersetzen | OFFEN | `Etappen`/`8`, `tone="accent"` bleibt |
| AC-2 | Obsoleten e2e `issue-583-archiv-design-fidelity.spec.ts` löschen | OFFEN (Datei existiert) | gelöscht |
| AC-3 | Repo-Grep Prod-Code 0 Treffer (außer Test/seed-Kommentar) | nur AC-1-Zeile übrig | erfüllt nach AC-1 |

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/routes/_design-system/+page.svelte` (Z.619) | AC-1: eine Zeile ersetzen |
| `frontend/e2e/issue-583-archiv-design-fidelity.spec.ts` | AC-2: löschen (testet seit #611 entfernte AccuracyBar/headline) |
| `frontend/e2e/issue-634-treffer-quote-cleanup.spec.ts` | neuer Behavior-Test (RED→GREEN) |
| `frontend/src/lib/components/atoms/Stat.svelte` | generisches Atom — **bleibt unverändert** |

## AC-3 Restbestand nach Fix
Nur noch in **Test-Dateien** (von AC-3 ausgenommen): `trip_archive_fields_roundtrip_test.go`
(bewusster #611-Rückwärtskompat-Roundtrip), `issue_480_archiv_suchfeld_breite.test.ts`
(Kommentar). Kein funktionaler Prod-Treffer.

## Risks & Considerations
- Stale-Base-Worktree NICHT direkt committen (#616 schon anders auf main gemergt) →
  die 3 winzigen #634-Änderungen sauber im aktuellen Worktree neu anwenden.
- `Stat.svelte` ist geteiltes Atom (Compare/TripHeader/Trips-Liste) — nicht anfassen.
- Reine Frontend-Showcase-Änderung, kein Backend, keine Persistenz.
