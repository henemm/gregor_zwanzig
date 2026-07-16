# Context: fix-1266-compare-edit-access

## Request Summary
Issue #1266 (Prod-Audit 2026-07-16, Befund 2, `[triage:po]`, Priorität 2 von 9): Auf dem Desktop soll es einen sichtbaren, funktionierenden Zugang zum Vergleichs-Editor (`/compare/<id>/edit`) geben. Laut Audit war der Link im DOM vorhanden aber unsichtbar (width 0), erreichbar nur über den mobilen Stift; die „Bearbeiten →"-Karten der Übersicht sprangen nur auf Hub-Tabs statt in den Editor. Explizit als INTERIMS-Fix gekennzeichnet — wird mittelfristig vom Epic „Eine Fläche wie Trip" (#1273) überholt.

## Kritischer Zeitstrahl-Fund (klärungsbedürftig in Analyse-Phase)
- Issue #1266 erstellt: **2026-07-16 04:53:41 UTC**
- Commit `addf58a3` (fix #1261 „Ortsvergleich — Bearbeiten auffindbar + Autospeichern"): erstellt 03:54:32 UTC, auf `origin/main` gemerged
- Prod-Frontend-Deploy von `9b3c4c2e` (enthält `addf58a3`): **04:58:35–04:58:40 UTC** — also **NACH** Issue-Erstellung
- Prod läuft aktuell (Stand jetzt) auf `9b3c4c2e`, d.h. **#1261 ist bereits live**

→ Die Audit-Screenshots (`docs/artifacts/audit-1256-prod/02-detail-uebersicht-desktop.png`, `02b-...`, nur in Worktree `intake-1194` vorhanden, nicht im Hauptrepo committed) wurden mit hoher Wahrscheinlichkeit gegen den **alten** Prod-Stand (vor #1261-Deploy) aufgenommen. Der Desktop-„Bearbeiten"-Button aus #1261 (`frontend/src/routes/compare/[id]/+page.svelte:180`, `Btn variant="outline" href="/compare/{id}/edit"`) ist im aktuellen Code vorhanden, keine `width:0`-verursachende CSS-Regel dazu gefunden (`app.css` durchsucht). Analyse-Phase MUSS zuerst live gegen aktuelles Prod verifizieren, ob Finding (a) überhaupt noch reproduziert.

## Zwei getrennte Teil-Befunde im Issue-Text
**(a) Desktop-Hub-Button unsichtbar** — vermutlich bereits durch #1261 behoben (s. Zeitstrahl oben). Bedingt: Button wird nur bei `status !== 'draft'` gerendert (`+page.svelte:172-181`); bei `status === 'draft'` gibt es nur „Setup abschließen", keinen Bearbeiten-Zugang — das ist aber vermutlich gewolltes Draft-Verhalten (Setup-Flow), kein Bug.

**(b) „Bearbeiten →"-Karten der Übersicht springen nur auf Hub-Tabs** — dieser Teil ist **weiterhin aktuell und unabhängig von #1261**. Fundort: `frontend/src/lib/components/compare/CompareTabs.svelte:888,898,908,918` — vier `<button onclick={() => handleValueChange('orte'|'idealwerte'|'layout'|'versand')}>Bearbeiten →</button>` in der Übersicht-Tab-SummaryCard. Diese wechseln nur den Hub-Tab (In-Page-Navigation), navigieren NICHT zu `/compare/{id}/edit`.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/routes/compare/[id]/+page.svelte` | Hub-Route: Desktop-„Bearbeiten"-Button (Zeile 180, aus #1261), Mobile-Stift (Zeile 214-220), `handleAction('edit')`-Zweig (Zeile 101-102) navigiert korrekt zu `/edit` |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | Enthält die vier „Bearbeiten →"-Buttons (Zeilen 888-918) in der Übersicht-SummaryCard, die auf Hub-Tabs statt `/edit` springen — das ist Teilbefund (b) |
| `frontend/src/routes/compare/+page.svelte` | Compare-Liste (Übersicht aller Vergleiche) — verlinkt auf `/compare/{id}` (Hub), kein direkter Editor-Zugang von hier, kein „Bearbeiten"-Text gefunden |
| `frontend/src/lib/components/ui/btn/Btn.svelte` + `frontend/src/lib/components/atoms/Btn.svelte` | Btn-Komponente (Re-Export-Wrapper #371); `href`-Prop rendert `<a>`, kein CSS-Bug mit width:0 gefunden |
| `frontend/src/lib/components/compare/subscriptionHelpers.ts` | `compareDetailActions()` liefert Kebab-Menü-Aktionen inkl. `{id:'edit', label:'Bearbeiten'}` für active/paused, NICHT für draft |
| `frontend/src/lib/components/compare/__tests__/compareDetailEditActions.test.ts` | Bestehende Tests aus #1261 zu `compareDetailActions()` — AC-2 (active/paused enthält edit), AC-4 (draft enthält KEIN edit) |
| `frontend/src/lib/components/compare/compare_detail.test.ts` | Bestehender Test AC-1 (#491): prüft nur String-Presence „Bearbeiten" im Source — kein Verhaltensnachweis, nicht ausreichend für #1266 |
| `frontend/src/routes/trips/[id]/edit/+page.svelte` | Trip-Pendant (Editor-Zugang) — Referenz für Trip/Compare-Code-Teilung (CLAUDE.md-Pflicht) |

## Existing Patterns
- Trip-Editor-Zugang (`/trips/[id]/edit`) ist das Referenzmuster für „wie soll Bearbeiten auf Desktop aussehen" — Pflicht-Prüfung: hätte dieser Fix ein geteilter Baustein sein müssen? (CLAUDE.md Trip/Compare-Teilung)
- Kebab-Menü-Aktion „Bearbeiten" (`compareDetailActions`) navigiert bereits korrekt über `handleAction` zu `/edit` — als Fallback-Pfad unabhängig vom Haupt-Button nutzbar.

## Dependencies
- Upstream: `data.preset.status` (draft/active/paused) steuert, welche Buttons überhaupt gerendert werden — Test-Szenario braucht alle drei Status.
- Downstream: keine — reine Frontend-Navigations-/Sichtbarkeitsfrage, kein Backend-Contract betroffen.

## Existing Specs
- Kein dediziertes Spec-Modul zu Compare-Hub-Navigation gefunden; verwandte Historie in Issues #1256 (Compare-UI Restliste), #1261 (Vorgänger-Fix), #1273 (Epic „Eine Fläche wie Trip", Grundsatzentscheidung PO 2026-07-16).

## Risks & Considerations
- **Doppelarbeit-Risiko:** Wenn Teilbefund (a) bereits durch #1261 gelöst ist, darf die Spec NICHT denselben Code nochmal ändern — Analyse-Phase muss das live verifizieren (Playwright/Screenshot gegen aktuelles Prod oder Staging), bevor ACs geschrieben werden.
- **Epic-Überschneidung:** #1273 (Epic „Eine Fläche wie Trip") wird `/edit` perspektivisch abschaffen und Hub-Tabs zum alleinigen Editor machen. Damit wäre das aktuelle Verhalten der „Bearbeiten →"-Buttons (Sprung zu Hub-Tab statt `/edit`) langfristig SOLL-Verhalten, nicht Bug. #1266 ist laut PO-Memo ausdrücklich nur „INTERIM" bis #1273 — die Spec muss den Fix bewusst minimal halten (nicht das Epic vorwegnehmen).
- **Trip/Compare-Teilungspflicht:** Jede neue Compare-only-Navigationskomponente ohne Trip-Pendant ist laut CLAUDE.md ein Default-Fehler — prüfen, ob der Fix stattdessen ein bestehendes geteiltes Muster nutzen sollte.
- Audit-Screenshots als Beleg sind aktuell nicht im Hauptrepo/Worktree verfügbar (nur in fremdem Worktree `intake-1194`, nicht committed) — für die Analyse-Phase ggf. neu erzeugen.
