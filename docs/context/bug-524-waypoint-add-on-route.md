# Context: Bug #524 — WaypointSidebar „+ auf Route" Button ist disabled

## Request Summary

Der Button „+ auf Route" in der Wegpunkt-Sidebar (`EditStagesPanelNew.svelte:292`) ist explizit `disabled` und nicht klickbar. Er muss aktiviert werden und beim Klick einen nutzbaren Flow öffnen (mindestens: Hinweis-Banner oder Add-Modus-Aktivierung).

## Related Files

| Datei | Relevanz |
|-------|----------|
| `frontend/src/lib/components/edit/EditStagesPanelNew.svelte` | Enthält den disabled Button (Z. 292) und `handleProfileAdd` (Z. 138) |
| `frontend/src/lib/components/trip-detail/waypoints/ProfileEditor.svelte` | Transparente Klick-Fläche via `onProfileAdd`-Prop (Z. 93–131) |
| `frontend/src/lib/components/trip-detail/waypoints/MapCanvas.svelte` | Leaflet-Karte — unterstützt NUR `onWaypointActivate`, KEIN Map-Klick-Add |
| `frontend/src/lib/components/edit/issue_503_etappen_waypoints.test.ts` | Source-Inspection-Tests (node:test + readFileSync) — Muster für neue Tests |
| `docs/specs/modules/issue_503_wegpunkt_editor_fix.md` | AC-7: Sidebar-Header mit `[+ auf Route]`-Button war bereits Spec-Ziel |

## Existing Patterns

- **Waypoint hinzufügen via Höhenprofil:** `handleProfileAdd(fraction)` in `EditStagesPanelNew:138` — fügt interpolierten Wegpunkt ein, wird von `ProfileEditor` via transparente `<rect>` aufgerufen. Funktioniert bereits.
- **Waypoint aktivieren via Karte:** `handleWaypointActivate(waypointId)` — nur für bestehende Marker, kein Map-Klick-Add.
- **Test-Methodik:** Source-Inspection mit `node:test` + `readFileSync`, keine DOM-Mocks, keine Playwright. Prüft Code-Invarianten (Attribute, Imports, Muster).

## Abhängigkeiten

- **Upstream:** `ProfileEditor.svelte` muss `onProfileAdd` erhalten (bereits der Fall)
- **Downstream:** `WaypointCard` + Sidebar-Liste reagieren automatisch auf `stages`-State-Änderungen

## Bestehende Specs

- `docs/specs/modules/issue_503_wegpunkt_editor_fix.md` — AC-7 beschreibt den Button als Muss-Feature, Implementierung wurde aber als `disabled` ausgeliefert

## Technische Analyse

### Was fehlt

Der Button (`Z.292`) hat `disabled` ohne Handler. Die Infrastruktur für das Hinzufügen existiert bereits vollständig in `handleProfileAdd`. Es fehlt nur:
1. `disabled` entfernen
2. Klick-Handler, der dem User zeigt, wie er einen Wegpunkt einfügen soll

### Empfohlener Ansatz: Add-Modus-Banner

State-Variable `addModeHint = $state(false)` in `EditStagesPanelNew`:
- Button-Klick → `addModeHint = true`
- Über dem Höhenprofil: Info-Banner „Klicke im Höhenprofil, um einen Wegpunkt einzufügen" (nur sichtbar wenn `addModeHint`)
- `handleProfileAdd` → setzt `addModeHint = false` nach erfolgreichem Einfügen

Kein neuer Component nötig — reines State-Management im bestehenden Panel.

### Alternativer Ansatz: direkt Profil-Click auslösen (nicht empfohlen)

Button ruft `handleProfileAdd(0.5)` auf — fügt Wegpunkt in der Mitte ein. Nicht nutzerfreundlich, da Position nicht gewählt werden kann.

## Risks & Considerations

- **Kein Scope-Creep:** MapCanvas erhält KEIN Map-Klick-Add — das wäre ein eigenes Feature
- **testid erhalten:** `data-testid="waypoint-add-on-route-btn"` muss bestehen bleiben (AC-3 aus Issue)
- **Kein Modus-Persist:** `addModeHint` ist lokaler State, kein Backend-Call nötig
- **LoC-Schätzung:** ~15 LoC im Panel + ~10 LoC Tests — weit unter 250er Limit
