# Spec: Home-Loader — kein Live-Wetter-Abruf (Issue #395)

**Status:** Approved (PO 2026-05-26) — Live auf Prod. Nachspiel: Parallel-Session ccbe84c führte den Fetch wieder ein → am 2026-05-26 erneut entfernt (Commit 9211546).
**Created:** 2026-05-26
**Issue:** #395 (Regression aus #386)
**Schweregrad:** hoch — Startseite ist meistbesucht, Bug live auf Prod.

## Problem & Produkt-Entscheidung

`frontend/src/routes/+page.server.ts` holt im SSR-Loader Live-Wetter für die Hero-Tour (`await fetch(.../stages/weather)`) — ohne Timeout → `/` hängt bis ~57 s, wenn der Wetter-Endpoint langsam ist.

**PO-Direktive (2026-05-26):** Live-Wetter auf der **Website** anzuzeigen ist **nicht der Zweck** der App — Wetter wird über Briefings (E-Mail/SMS) ausgeliefert. Website-Seiten zeigen standardmäßig **keine** teuer live geladenen Wetterdaten; aktuelle Daten nur **auf Anforderung**.

## Lösung

Den **Live-Wetter-Abruf aus dem Home-Loader entfernen** (nicht nur ein Timeout). Die Startseite rendert dann sofort aus den vorhandenen Tour-/Etappen-Daten.

- `+page.server.ts`: Wetter-Fetch entfernen; Loader liefert wieder nur `trips` + `subscriptions` (Stand vor #386, fail-soft `.catch` bleibt).
- `+page.svelte`: Der Hero zeigt Trip/Etappe/Route (Name, Region, Etappe, km/↑/↓, Höhenprofil, Etappen-Streifen) **ohne** Live-Wetter/Risk. Die Wetter-/Risk-Anzeige rendert bereits konditional (seit #386) → bei fehlenden Daten einfach nicht sichtbar. **Kein Fake-/Demo-Wetter** im Hero (irreführend). Markup bleibt dormant für eine spätere „aktuelles Wetter auf Anforderung"-Funktion.

**Folge-Option (separat, nicht jetzt):** Falls gewünscht, „Wetter jetzt laden"-Button im Hero, der client-seitig on-demand `stages/weather` holt.

## Acceptance Criteria

**AC-1:** Given der Home-Loader, When `/` serverseitig lädt, Then erfolgt **kein** Fetch auf `…/stages/weather` — der Loader hat keine Abhängigkeit vom Wetter-Endpoint. (Source-Inspection-Guard verhindert Wieder-Einführung.)

**AC-2:** Given ein (auch langsamer/hängender) Wetter-Endpoint, When `/` authentifiziert geladen wird, Then ist die Ladezeit schnell und unabhängig vom Wetterdienst (Ziel < 3 s; RED-Beleg = vorherige 57,3 s).

**AC-3:** Given die Hero-Tour, When `/` rendert, Then erscheinen Trip-/Etappen-/Routen-Infos (inkl. Höhenprofil + Etappen-Streifen) korrekt **ohne** Live-Wetter/Risk-Pill; kein Crash, kein irreführendes Fake-Wetter.

**AC-4:** Given `trips`/`subscriptions`, When der Loader läuft, Then unverändert geliefert (bestehendes fail-soft); Leerzustand/„Weitere Trips"/Archiv wie gehabt.

**AC-5 (keine Regression):** `svelte-check` + `contrast-audit` + `trip-terminology`-Guard grün, `vite build` grün; Cockpit-Layout sonst unverändert (#386).

## Tests (mock-frei)

- `home-loader-no-weather.test.ts` (node:test, Source-Inspection): `+page.server.ts` enthält keinen `stages/weather`-Fetch. RED vor dem Entfernen, GREEN danach. Lasting Guard.
- E2E (Staging, Post-Push): `/` authentifiziert-Ladezeit messen (< 3 s; RED = 57,3 s) + Hero zeigt Trip-Infos, keine Risk-Pill.

## Risiken

- Toter Wetter-Code in `+page.svelte` (heroWeather-Prop, Risk/Summary-Blöcke) bleibt dormant — bewusst, für spätere on-demand-Funktion. Kein Funktionsbruch (rendert konditional nichts).
- LoC: klein (Loader-Zeilen entfernen + 1 Guard-Test).
