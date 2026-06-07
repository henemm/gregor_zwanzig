# Context: #582 Compare-Screen Design-Fidelity (v2 / Drift-Korrektur)

## Request Summary
Compare-Screens (Liste, Hub/Übersicht, Detail, Edit) 1:1 nach JSX-Vorlage neu angleichen, bis der Pixel-Diff gegen die SOLL-Bilder < 10 % liegt. Das Issue wurde am 2026-06-04 **wieder geöffnet**, weil die als "fertig" gemeldete Arbeit (e880d04e) bei der #603-Pilotmessung **51,5 % Drift** zeigte.

## Status-Korrektur
- Mein Gedächtnis (`project_issue_582_done.md`) sagte "LIVE & zu" — **veraltet**. Issue ist OPEN.
- Alter Workflow `issue-582-compare-design-fidelity` = Complete (gehört zur fälschlich geschlossenen Arbeit). Neuer Workflow: `issue-582-compare-fidelity-v2`.

## Bindende Quellen
| Datei | Rolle |
|------|------|
| `claude-code-handoff/current/jsx/screen-compare-list.jsx` | SOLL Liste (12 Inline-Styles, 2 Texte) |
| `claude-code-handoff/current/jsx/screen-compare-detail.jsx` | SOLL Hub + Detail + Edit |
| `claude-code-handoff/current/jsx/screen-compare-wizard.jsx` | SOLL Neu/Wizard |
| `claude-code-handoff/current/jsx/{atoms,molecules,organisms}.jsx` | Komponenten-Vorlagen |
| `claude-code-handoff/current/jsx/tokens.css` | Nur `var(--g-*)` Tokens, kein rohes Hex/px |
| `claude-code-handoff/current/soll/G-compare-*.png` | 8 SOLL-Bilder |

## Diff-Gate (PFLICHT vor Issue-Close, je < 10 %)
```
design_fidelity_diff.py --screen G-compare-uebersicht-kacheln   → /compare
design_fidelity_diff.py --screen G-compare-detail               → /compare
design_fidelity_diff.py --screen G-compare-edit                 → /compare
design_fidelity_diff.py --screen G-compare-edit-locations       → /compare
```
Artefakt `docs/artifacts/<workflow>/design-diff-<screen>.json` muss `"passed": true` haben. `pre_issue_close_design_gate.py` blockt Close ohne PASS.

## Related Files
| Datei | Relevanz |
|------|----------|
| `frontend/src/routes/compare/+page.svelte` | Liste/Hub-Route |
| `frontend/src/routes/compare/[id]/+page.svelte` | Detail |
| `frontend/src/routes/compare/[id]/edit/+page.svelte` | Edit |
| `frontend/src/routes/compare/new/+page.svelte` | Neu/Wizard |
| `frontend/src/lib/components/compare/*.svelte` | CompareTabs, CompareDetail, CompareMatrix, CompareGrid, CompareTile, CompareWizard … |
| `frontend/src/lib/components/molecules/Compare*.svelte` | Row/Preview-Molecules |
| `.claude/hooks/design_fidelity_diff.py` | Diff-Gate-Tool (NICHT umbauen — [[feedback-shared-fidelity-tool]]) |
| `.claude/tools/jsx_style_inventory.py` | Inventory-Checkliste |

## Kritischer Befund (Tooling-Lücke)
Alle 4 Gate-Screens mappen in `SCREEN_URL_MAP` auf `/compare` und haben **keine** Einträge in `SCREEN_PRE_ACTIONS`. → Das Tool würde 4× denselben Screenshot (die `/compare`-Liste) gegen 4 verschiedene SOLL-Bilder messen. Für `detail`/`edit`/`edit-locations` müssen Pre-Actions (Tab-/Detail-/Edit-Navigation) ergänzt werden, sonst kann das Gate niemals für alle grün werden. Muster: `M-location-new` mit `click`/`wait_selector`.

## Übernahme-Regeln (aus Reopen-Protokoll)
- Inline-Styles 1:1, sichtbarer Text wortgleich
- Kein Tailwind-Übersetzen, kein Sub-Komponenten-Refactoring während Übernahme
- Keine erfundenen Loading/Empty/Fallback-States
- Backend-Pre-Check: Mock-Felder gegen TS-Modell prüfen, fehlende Felder Backend-first ergänzen (nicht UI weglassen)

## Etablierte Vorgehensweise (aus jüngsten Fidelity-Reworks)
- #587/#632: SOLL-aus-JSX-Render-Technik, geteiltes Diff-Tool NICHT umbauen, Pixel-Diff als Hard-Gate
- #583: Viewport-/Threshold-Tuning ist entscheidend; Diff-Tool rendert SOLL bei ~1024px Desktop
- #577/#578: Foundation-First (Tokens→Atoms→Molecules) zahlt sich aus; diese liegen bereits live vor

## Dependencies
- Upstream: Tokens (#576), Atoms (#577), Molecules/Organisms (#578) — alle live
- Downstream: Epic #575 Screen-Redo (Schwester-Issues #579–#588)

## Risks & Considerations
- Diff-Tool-Pre-Actions-Lücke (s.o.) — blockiert Gate, muss Teil der Spec sein
- Daten-Divergenz: SOLL zeigt Mock-Daten, Staging-Testkonto zeigt echte Compare-Presets → ggf. erhöhter Threshold mit Begründung (wie #486 30 %), nur wenn Layout 1:1
- 51,5 % Alt-Drift war vor Foundation-Landung (#576–#578) — aktueller Ist-Wert evtl. niedriger; Baseline in Analyse/Spec messen
- LoC-Limit 250 — breiter Rework über 4 Routes + Komponenten könnte überschreiten → ggf. User um Override-Erlaubnis fragen oder splitten
