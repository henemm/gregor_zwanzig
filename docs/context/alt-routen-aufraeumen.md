# Context: Alt-Routen aufräumen

## Request Summary
Die 5 alten Routen (/locations, /subscriptions, /weather, /gpx-upload, /settings) entfernen oder redirecten. Die Funktionalität ist bereits in die neuen Bereiche (Startseite, Meine Touren, Orts-Vergleich, Account) integriert.

## Ist-Zustand
Alle 5 Routen existieren noch und sind per URL erreichbar, aber NICHT in der Sidebar-Navigation:
- /locations → SvelteKit + NiceGUI (Location CRUD)
- /subscriptions → SvelteKit + NiceGUI (Abo-Management)
- /weather → SvelteKit only (Wettervorhersage)
- /gpx-upload → SvelteKit + NiceGUI (GPX-Import)
- /settings → SvelteKit + NiceGUI (System-Status, im User-Menu verlinkt)

## Neue Bereiche wo die Funktionalität jetzt lebt
- /locations → in /compare Sidebar (Phase C1-C4, erledigt)
- /subscriptions → Auto-Reports in /compare Content (Phase C3, erledigt)
- /weather → Wetter-Drill-Down aus Sidebar (Phase F, erledigt)
- /gpx-upload → Trip-Wizard Schritt 1 (W1, erledigt)
- /settings → /account Seite (teilweise)

## Related Files

| File | Relevance |
|------|-----------|
| `src/web/main.py:32-71` | NiceGUI @ui.page() Registrierungen |
| `src/web/main.py:74-86` | Legacy Header mit alten Links (nicht mehr aufgerufen) |
| `frontend/src/routes/locations/` | SvelteKit /locations Page |
| `frontend/src/routes/subscriptions/` | SvelteKit /subscriptions Page |
| `frontend/src/routes/weather/` | SvelteKit /weather Page |
| `frontend/src/routes/gpx-upload/` | SvelteKit /gpx-upload Page |
| `frontend/src/routes/settings/` | SvelteKit /settings Page |
| `frontend/src/routes/+layout.svelte` | Sidebar Nav (nur 3 Einträge) |
| `frontend/e2e/locations.spec.ts` | E2E Tests für /locations |
| `frontend/e2e/weather.spec.ts` | E2E Tests für /weather |
| `frontend/e2e/system-status.spec.ts` | E2E Tests für /settings |

## Strategie
Redirect statt Löschen — alte URLs per 301 auf neue Bereiche umleiten:
- /locations → /compare
- /subscriptions → /compare
- /weather → /compare (oder /trips)
- /gpx-upload → /trips
- /settings → /account

## Risks & Considerations
- E2E Tests testen noch gegen alte Routen — müssen nach Redirect angepasst werden
- /settings ist noch im User-Menu verlinkt → auf /account umbiegen
- NiceGUI header mit alten Links wird nicht aufgerufen, kann entfernt werden
- Bookmarks von Usern könnten auf alte URLs zeigen → daher Redirect statt 404
