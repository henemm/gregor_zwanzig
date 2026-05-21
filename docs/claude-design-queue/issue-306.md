# #306 — Design: Login-Seite Desktop-Screen

**Labels:** `priority:high` `frontend` `area:sidebar` `for:claude-design`
**URL:** https://github.com/henemm/gregor_zwanzig/issues/306
**Erstellt:** 2026-05-21

---

## Was fehlt

Die Login-Seite (`/login`) hat **kein Desktop-Design**. Das Mobile-Mockup (`screen-login-mobile.jsx`) aus dem letzten Claude Design Handoff wurde explizit als *„NEU — Desktop hatte noch keinen Login-Screen"* markiert.

## Aktueller Zustand

Die Desktop-Seite ist ein einfaches zentriertes Formular ohne Design-Token-Konformität:
- Keine Wordmark-Integration (`<Wordmark size="lg">`)
- Kein Topo-Hintergrund (`<TopoBg>`)
- Formularfelder nutzen natives HTML statt `<Input>`-Komponente
- Submit-Button ist kein `<Btn variant="primary">`

## Was ich brauche

Ein Desktop-Screen für `/login` (1440 px Breite), der zeigt:
- Layout: Gesplittet (linke Seite mit Topo-BG + Wordmark, rechtes Formular-Panel) **oder** zentrierte Card
- Wordmark `gregor.zwanzig` in Größe `lg` oben
- Untertitel (z.B. „Wetter-Briefings für Weitwanderer")
- Formular: Username-Feld, Passwort-Feld, Submit-Button `<Btn variant="primary" size="lg">`
- Links: „Passwort vergessen" + „Noch kein Konto? Registrieren"
- Token-konform: `--g-surface-1`, `--g-paper`, `--g-accent`

## Mobile-Referenz

`gregor-zwanzig-mobile/project/screen-login-mobile.jsx` aus dem letzten Handoff ZIP.

## Betroffene Dateien

- `frontend/src/routes/login/+page.svelte`
