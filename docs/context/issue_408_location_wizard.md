# Context: Issue #408 — Location-Neu als 3-Schritt-Wizard

## Request Summary

Die `/locations`-Seite zeigt beim Erstellen einer neuen Location noch den alten `LocationForm`-Dialog (flaches Formular). SOLL ist der bereits fertig implementierte `NewLocationWizard` (3 Schritte: Verortung → Benennung → Aktivitätsprofil), der auf der `/compare`-Seite bereits funktioniert.

## Kernbefund: Wizard ist FERTIG, nur falsch verdrahtet

`NewLocationWizard.svelte` existiert vollständig in `frontend/src/lib/components/compare/NewLocationWizard.svelte`. Er wird auf `/compare` korrekt eingebunden. Auf `/locations` wird stattdessen `LocationForm.svelte` verwendet — das ist der einzige Fehler.

## Related Files

| Datei | Relevanz |
|-------|----------|
| `frontend/src/routes/locations/+page.svelte` | **Hauptänderung**: Create-Dialog auf `NewLocationWizard` umstellen |
| `frontend/src/lib/components/compare/NewLocationWizard.svelte` | Fertiger Wizard — wird nur importiert, KEIN Edit nötig |
| `frontend/src/lib/components/LocationForm.svelte` | Bleibt für Edit-Modus unverändert |
| `frontend/src/routes/locations/+page.server.ts` | Lädt nur `locations`, keine `groups` → `groups=[]` für Wizard |
| `frontend/src/routes/compare/+page.svelte` | Referenz-Implementierung: Wie Wizard korrekt eingebunden wird |

## Existing Patterns

- **Wizard-Einbindung auf /compare:** `<NewLocationWizard {locations} {groups} onsave={handleNewLocSave} oncancel={...} />`
- **handleNewLocSave auf /compare:** Fügt neue Location zur Liste hinzu, schließt Dialog — macht KEINEN weiteren API-Call (Wizard speichert intern via `api.post('/api/locations', loc)`)
- **Edit-Modus bleibt bei LocationForm** — Wizard ist nur für Create ausgelegt

## Dependencies

- **Upstream:** `NewLocationWizard` → `api.post('/api/locations', ...)` intern
- **Downstream:** Nach Wizard-Save wird `onsave(loc: Location)` aufgerufen — Page muss `refetchLocations()` aufrufen und Dialog schließen

## Risiken

- **Doppelter API-Call (KRITISCH):** `handleSave` in der locations-Page macht ebenfalls `api.post`. Wenn wir `NewLocationWizard` mit dem alten `handleSave` verbinden, wird zweimal gespeichert. Fix: Neuer `handleNewLocationSave`-Callback nur mit `refetchLocations()` + `dialogMode = null`.
- **Fehlende `groups`:** `/locations/+page.server.ts` lädt keine Gruppen. `NewLocationWizard` bekommt `groups={[]}` → Gruppe-Select zeigt nur "Keine Gruppe". Akzeptabel für diese Phase.
- **Edit-Modus:** `NewLocationWizard` ist nicht für Edit ausgelegt (kein `location`-Prop). Edit bleibt bei `LocationForm`.

## Scope

**Nur 1 Datei** muss geändert werden: `frontend/src/routes/locations/+page.svelte`

Änderungen:
1. Import `NewLocationWizard` hinzufügen
2. Import `LocationForm` behalten (für Edit)
3. Neue Funktion `handleNewLocationSave(loc: Location)`: nur `refetchLocations()` + `dialogMode = null`
4. Create-Dialog: `LocationForm` → `NewLocationWizard`
5. Edit-Dialog: `LocationForm` bleibt

## SOLL-Screenshot

`claude-code-handoff/soll-audit-2026-05-27/soll-screenshots/desktop-location-new.png` — zeigt den vollständigen 3-Schritt-Wizard (Schritt 1 mit Smart-Import-Input + Minimap-Preview bereits ausgefüllt sichtbar, darunter Schritt 2 "Benennung" mit Zeichenzähler, Schritt 3 mit visuellen Kacheln).

## Existing Specs

- `docs/specs/modules/issue_249_locations_rail.md` — Spezifiziert `NewLocationWizard` (approved, implementiert)
- `docs/specs/modules/issue_266_location_preview_map.md` — LocationPreviewMap-Komponente (bereits in Wizard eingebaut)
- `docs/specs/modules/issue_276_mobile_gmaps_link.md` — Smart-Import-Backend (bereits vorhanden)
