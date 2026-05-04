# Context: Orts-Vergleich C1 — Master-Detail Layout

## Request Summary
Die /compare Seite bekommt ein Master-Detail Layout: Links eine Sidebar mit der Locations-Liste (aus /locations), rechts der bestehende Compare-Content. Phase C1 baut nur das Layout — keine Gruppen, keine Subscriptions, keine neue Logik.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/routes/compare/+page.svelte` | **Hauptdatei** — bekommt Sidebar + Content-Split (379 LOC) |
| `frontend/src/routes/compare/+page.server.ts` | Laedt bereits Locations — bleibt unveraendert |
| `frontend/src/routes/locations/+page.svelte` | **Referenz** — Locations-Tabelle, CRUD, Dialoge (215 LOC) |
| `frontend/src/routes/locations/+page.server.ts` | Laedt Locations — identisch zum Compare-Loader |
| `frontend/src/lib/components/LocationForm.svelte` | Wird in Sidebar fuer "Ort hinzufuegen" wiederverwendet |
| `frontend/src/lib/components/WeatherConfigDialog.svelte` | Optional — Wetter-Config pro Location |
| `frontend/src/routes/+layout.svelte` | Nav zeigt bereits "Orts-Vergleich" auf /compare |

## Ist-Zustand: /compare
- Volle Seitenbreite, keine Sidebar
- Oben: "Einstellungen" Card mit Location-Checkboxen, Datum, Zeitfenster, Profil, Button
- Darunter: Ergebnis-Tabelle mit Winner-Highlight
- Location-Auswahl: Flache Checkbox-Liste aller Locations
- Daten: locations kommen aus +page.server.ts (GET /api/locations)

## Soll-Zustand: /compare (Phase C1)
- **Sidebar (links, ~240px):** Locations-Liste mit Checkboxen fuer Vergleichs-Auswahl
  - "Neue Location" Button → oeffnet LocationForm Dialog
  - Einfache Liste (keine Gruppen in C1)
- **Content (rechts):** Bestehende Compare-Logik
  - Einstellungen-Card (ohne Location-Checkboxen — die sind jetzt in der Sidebar)
  - Ergebnis-Tabelle

## Was sich NICHT aendert
- API-Endpunkte bleiben identisch
- Compare-Logik (runComparison, result rendering) bleibt identisch
- +page.server.ts bleibt identisch (laedt bereits locations)
- /locations Seite bleibt erreichbar (wird erst in C3/C4 ueberarbeitet)
- /subscriptions Seite bleibt erreichbar

## Existing Patterns
- Master-Detail Layout existiert im Projekt nicht — das waere neu
- Sidebar-Pattern: Haupt-Layout hat eine globale Sidebar (nav), hier ist eine Page-Level Sidebar
- Checkbox-Pattern: Compare hat bereits toggleAll/toggleLocation Logik

## Dependencies
- **Upstream:** LocationForm.svelte, $lib/types.js (Location type), shadcn-svelte Komponenten
- **Downstream:** Phase C2 (Sidebar-Checkboxen steuern Compare), C3 (Auto-Reports), C4 (Gruppen)

## Scoping
- **1 Datei** hauptsaechlich: compare/+page.svelte
- **~100-150 LOC** Aenderung (Layout-Split, Location-Liste in Sidebar verschieben)
- Location-CRUD in Sidebar: Optional fuer C1 — koennte auch C2 sein
- Komplexitaet: **Mittel** — CSS-Layout + State-Refactoring

## Risks
- CSS: Page-Level Sidebar neben der globalen Nav-Sidebar koennte Layout-Probleme verursachen
- Mobile: Sidebar muss auf kleinen Screens kollapsen oder ausgeblendet werden
- Location-Checkboxen muessen synchron bleiben zwischen Sidebar und Compare-State
