# Context: Compare-Editor Slice 1 (Issue #678, Epic #677)

## Request Summary
Orts-Vergleich vom 5-Schritt-Wizard auf einen Tab-Editor umstellen (wie Trips). Slice 1: Editor-Gerüst
+ reine Progressive-Lock-Logik + Tab „Vergleich" (Desktop/Create) unter `/compare/new`.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/compare/CompareWizard.svelte` | Abzulösende Stepper-Shell (Vorbild für State-Verdrahtung, Edit-Header, Save) |
| `frontend/src/lib/components/compare/compareWizardState.svelte.ts` | State-Container (Name/Region/activityProfile/pickedIds/idealRanges/channelLayouts/schedule…) — wird vom Editor weitergenutzt |
| `frontend/src/lib/components/compare/steps/Step1Vergleich.svelte` | Bestehender Tab-1-Inhalt (Name/Region/Profil-Tiles) — Logik wiederverwenden |
| `frontend/src/lib/components/compare/steps/Step2..5*.svelte` | Tabs 2–5 als gesperrte Panels mounten (kein Funktionsverlust) |
| `frontend/src/routes/compare/new/+page.svelte` | Mount-Punkt → auf CompareEditor umstellen |
| `frontend/src/lib/components/trip-new/TripNewEditor.svelte` | Muster (Progressive Tab Editor #622) |
| `claude-code-handoff/current/jsx/screen-compare-editor.jsx` | Design-Quelle (CE_TabBar/CE_Progress/CE_unlocked/CE_doneSet/CE_VergleichTab) |

## Existing Patterns
- **Factory-State im +page.svelte** (`new CompareWizardState()` + `setContext`) wegen Safari-Runes-Reaktivität — beibehalten.
- **Trip-Editor (#622):** ein Editor, progressive Tab-Freischaltung, Floating/Footer-CTA. Direkte Vorlage.
- **Atoms/Molecules** (`Btn/Eyebrow/TopoBg/Field`) + `var(--g-*)`-Tokens (keine rohen Hex/px).
- **Profil-Tiles:** `ACTIVITY_PROFILE_OPTIONS` aus `$lib/types` (4 Bestandsprofile) — Design hat 5 (Divergenz, siehe Risiken).

## Dependencies
- **Upstream:** `CompareWizardState`, atoms/molecules, `ACTIVITY_PROFILE_OPTIONS`, `data.locations` aus `+page.server.ts`.
- **Downstream:** `/compare/new` (Create). `/compare/[id]/edit` bleibt in diesem Slice am Wizard (erst Slice 2).

## Existing Specs
- `docs/specs/modules/issue_440_compare_wizard_shell_step1_step2.md` — Wizard-Shell + Step1/2 (abzulösen)
- `docs/specs/modules/issue_678_compare_editor_shell.md` — diese Spec (Slice 1)

## Risks & Considerations
- **Profil-Divergenz:** Design = 5 Profile (wintersport/-glacier/alpine-touring/hiking/trail-running), App = 4. Slice 1 hält Bestandsprofile (kein Backend-Bruch); Adoption separat.
- **Kein Funktionsverlust:** Tabs 2–5 müssen die bestehenden Step-Komponenten weiter zeigen; nur die Hülle wechselt.
- **Keine Persistenz-Änderung** in Slice 1 → kein Mandantentrennungs-Risiko hier (kommt in Slice 2/4).
- **LoC-Budget 250** — Shell + Logik + Tab1 + Route, knapp; Tab-Inhalte 2–5 bleiben Bestandskomponenten.
- **Desktop-only** in Slice 1; Mobile-Media-Queries nicht anfassen (Slice 5).
