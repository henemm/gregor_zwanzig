# Context: Bug #271 — Trip-Wizard Stepper Mobile

## Request Summary

Der Trip-Wizard (`/trips/new`) zeigt auf Viewports ≤ 899 px alle 4 Stepper-Labels gleichzeitig in einem Flex-Container ohne Mobile-Alternative. Labels klippen bei 375 px, und die Weiter/Zurück-Buttons haben keinen Safe-Area-Abstand.

## Betroffene Dateien

| Datei | Relevanz |
|-------|----------|
| `frontend/src/lib/components/trip-wizard/Stepper.svelte` | Hauptursache: kein mobiler Zweig, alle 4 Labels nebeneinander |
| `frontend/src/lib/components/trip-wizard/TripWizardShell.svelte` | Shell: Footer-Buttons ohne sticky/safe-area; kein WizardCancelSheet |
| `frontend/src/routes/trips/new/+page.svelte` | Mount-Punkt (minimal, nur State-Factory) |
| `frontend/src/lib/components/trip-wizard/stepperState.ts` | Pure-Function-Logik (kein Change nötig) |
| `frontend/src/app.css` | Definiert `@custom-variant mobile` (≤899px) / `desktop` (≥900px), `mobile-scroll-pad`, Safe-Area |

## Bestehende Muster

### Breakpoints
- `mobile:` → `@media (max-width: 899px)` — in `app.css` via `@custom-variant` definiert
- `desktop:` → `@media (min-width: 900px)`
- `BottomNav.svelte` nutzt `desktop:hidden` (verschwindet auf Desktop)
- `main` in `+layout.svelte` nutzt `mobile-scroll-pad` für `padding-top: 56px` + `padding-bottom: calc(64px + env(safe-area-inset-bottom))`

### Safe-Area-Implementierung (Referenz: BottomNav.svelte)
```css
padding-bottom: env(safe-area-inset-bottom);
```

### Bottom-Sheet-Muster (Referenz: trips/+page.svelte, compare/+page.svelte)
- Backdrop + Panel mit Handle — aus Issues #268, #270

### Compact-Stepper-Idee (Issue-Spec)
Auf Mobile: nur `"02 / 04 · GPX-Import"` — Schritt-Nummer + Schritt-Titel, kein Label-Array sichtbar

## Abhängigkeiten

- **Upstream:** `WizardState` (wizardState.svelte.ts) — `currentStep`, `canAdvanceCurrent`, `save()`, `prevStep()`, `nextStep()`
- **Downstream:** `Step1Profile`, `Step2Stages`, `Step3Waypoints`, `Step4Briefings` — keine Änderungen nötig
- `BottomNav` (fix bottom-0 z-50) — Wizard-Footer-Bar muss z-Index unter BottomNav bleiben (BottomNav ist z-50)

## Risks & Considerations

1. **BottomNav-Überlagerung:** Die App-Shell-BottomNav ist `fixed bottom-0 z-50`. Eine neue sticky Wizard-Bottom-Bar muss sich darunter platzieren ODER die BottomNav muss auf `/trips/new` ausgeblendet werden. Option 2 ist sauberer (Wizard ist modal flow, keine Workspace-Navigation nötig).
2. **WizardCancelSheet:** Issue nennt einen `WizardCancelSheet` — existiert noch nicht. Für den ersten Fix kann `goto('/')` direkt bleiben (wie jetzt); Sheet ist Nice-to-Have.
3. **Desktop-Stepper unverändert lassen** — explizit in Issue-Spec genannt.
4. **Kein Backend-Change** — rein Frontend.

## Zusammenfassung der geplanten Änderungen

1. `Stepper.svelte`: Mobile-Zweig (`mobile:` Klasse) → kompakter Text `"N / 4 · [Label]"` statt 4 Kreise + Labels
2. `TripWizardShell.svelte`: 
   - Footer-Buttons → `sticky bottom-0` mit `padding-bottom: env(safe-area-inset-bottom)` + Padding für BottomNav (64px)
   - BottomNav auf `/trips/new` ausblenden (via Layout-Slot oder CSS) ODER Wizard-Footer höher z-index statt BottomNav
3. Kein WizardCancelSheet im ersten Fix (scope halten)
