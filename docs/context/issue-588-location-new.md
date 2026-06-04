# Context: Issue #588 — Location-New 1:1 nach screen-location-new.jsx

## Request Summary

Der „Neuer Ort"-Dialog soll 1:1 aus der JSX-Vorlage `screen-location-new.jsx` neu implementiert werden. Der alte 3-Schritt-Wizard (`NewLocationWizard.svelte`) wird durch ein neues, design-fidelity-konformes Modal ersetzt.

## Related Files

| Datei | Relevanz |
|-------|----------|
| `claude-code-handoff/current/jsx/screen-location-new.jsx` | **Bindendes SOLL** — 1:1 implementieren |
| `claude-code-handoff/current/jsx/atoms.jsx` | Atom-Referenz |
| `claude-code-handoff/current/jsx/molecules.jsx` | Molecule-Referenz |
| `claude-code-handoff/current/jsx/organisms.jsx` | Organism-Referenz |
| `claude-code-handoff/current/jsx/tokens.css` | Token-Referenz, nur `var(--g-*)` |
| `claude-code-handoff/current/soll/M-location-new.png` | Älterer SOLL-Screenshot (weicht vom JSX ab) |
| `frontend/src/lib/components/compare/NewLocationWizard.svelte` | Bisherige Implementierung (wird ersetzt) |
| `frontend/src/routes/locations/+page.svelte` | Verwendet NewLocationWizard im create-Dialog |
| `frontend/src/routes/locations/__tests__/issue_408_location_wizard.test.ts` | Tests, die `NewLocationWizard` prüfen |
| `frontend/src/lib/components/atoms/Eyebrow.svelte` | Atom: `<Eyebrow>` |
| `frontend/src/lib/components/atoms/TopoBg.svelte` | Atom: `<TopoBg>` |
| `frontend/src/lib/components/atoms/Pill.svelte` | Atom: `<Pill>` |
| `frontend/src/lib/components/atoms/KV.svelte` | Atom: `<KV>` |
| `frontend/src/lib/components/atoms/Card.svelte` | Atom: `<Card>` |
| `frontend/src/lib/components/atoms/Btn.svelte` | Atom: `<Btn>` |
| `frontend/src/lib/types.ts` | `ACTIVITY_PROFILE_OPTIONS`, `ActivityProfile` |
| `internal/handler/location_resolve.go` | Backend: `POST /api/locations/resolve` |
| `frontend/src/lib/components/compare/LocationPreviewMap.svelte` | Mini-Map (evtl. wiederverwendbar) |
| `frontend/src/lib/components/compare/locationHelpers.ts` | `toKebabCase`, `isCoordsValid` |

## SOLL-Design (aus JSX)

Das Modal ist eine **single-page Übersicht** (kein Wizard-Stepper) mit 3 nummerierten Sektionen:

1. **Verortung · Smart-Import** — URL/Koordinaten-Eingabe, erkannte Format-Chips, Vorschau-Card (KV-Grid + Mini-Map)
2. **Benennung** — Name + Gruppe (2-Spalten-Grid)
3. **Meteorologische Brille** — Activity-Profile-Cards (3er-Grid, auswählbar)

**Layout:**
- Äußeres Div: Volle Höhe, `var(--g-paper)` Hintergrund
- Hintergrundschicht: Abgedunkelter, verschwommener Compare-List-Kontext (opacity 0.35, blur 2px)
- Dunkle Overlay-Schicht: `rgba(26,26,24,0.45)`
- Modal-Card: 720px breit, `position: absolute, top: 60, left: 50%`, weiß, `var(--g-shadow-3)`

## Diskrepanz: SOLL-Screenshot vs. JSX

Der Screenshot `M-location-new.png` zeigt das **ältere Design** (Karte + Formular nebeneinander, Shadcn-Dialog-Shell). Die JSX-Vorlage ist die **bindende Quelle** laut Issue-Body.

## Existing Patterns

- Atoms: Alle benötigten Atoms (`Eyebrow`, `TopoBg`, `Pill`, `KV`, `Card`, `Btn`) existieren in `frontend/src/lib/components/atoms/`
- Helper-Komponenten (`LocSectionTag`, `LocFormatChip`, `LocPseudoInput`, `LocProfileCard`) sind im JSX als inline-Funktionen definiert → werden in Svelte als inline-Subkomponenten oder `{#snippet}`-Blöcke implementiert
- Smart-Import-API: `POST /api/locations/resolve` existiert (`internal/handler/location_resolve.go`)
- Activity Profiles: `ACTIVITY_PROFILE_OPTIONS` in `types.ts` hat 4 Einträge (allgemein, wintersport, wandern, summer_trekking) — JSX-Konstante `LOCATION_ACTIVITY_PROFILES` muss daraus abgeleitet werden

## Dependencies

- **Upstream:** `POST /api/locations/resolve` (Backend, live), `POST /api/locations` (Backend, live)
- **Downstream:** `locations/+page.svelte` ruft `NewLocationWizard` auf → nach Migration wird neues Modal gerufen
- **Tests:** `issue_408_location_wizard.test.ts` prüft `NewLocationWizard`-Import und -Usage → müssen auf neues Modal angepasst werden

## Risks & Considerations

1. **Discrepancy Screenshot/JSX**: JSX ist bindend, Screenshot ignorieren
2. **Groups-Prop**: `locations/+page.svelte` übergibt `groups={[]}` — im neuen Modal Gruppe als freies Texteingabe-Feld laut JSX (`LocPseudoInput label="Gruppe (optional)"`)
3. **Old wizard tests**: `issue_408_location_wizard.test.ts` prüft spezifisch `NewLocationWizard` — braucht Update auf neue Komponente
4. **Full-page overlay**: JSX-Design setzt `position: absolute` voraus — Integration in `locations/+page.svelte` muss den Container relativ positionieren (oder eigenes Portal)
5. **ScreenCompareList als Hintergrund**: Im JSX wird `<ScreenCompareList/>` als Hintergrundkontext eingeblendet — in Svelte entweder als Screenshot-Placeholder oder echter Compare-Content
