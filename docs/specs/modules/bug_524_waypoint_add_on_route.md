---
entity_id: bug_524_waypoint_add_on_route
type: bugfix
created: 2026-06-02
updated: 2026-06-02
status: draft
version: "1.0"
tags: [frontend, svelte, waypoints, bugfix, edit-panel]
---

# Bug #524: WaypointSidebar — '+ auf Route' Button entsperren

## Approval

- [ ] Approved

## Purpose

Der Button „+ auf Route" in `EditStagesPanelNew.svelte` ist durch ein hartkodiertes `disabled`-Attribut dauerhaft gesperrt und besitzt keinen `onclick`-Handler. Dieser Fix entsperrt den Button, führt einen `addModeHint`-State ein und zeigt dem Nutzer einen schließbaren Info-Strip oberhalb des Höhenprofils, der erklärt, wie ein Wegpunkt via Profil-Klick eingefügt wird — so wird die bereits vollständig vorhandene `handleProfileAdd`-Infrastruktur erstmals nutzbar gemacht.

## Source

- **File:** `frontend/src/lib/components/edit/EditStagesPanelNew.svelte`
- **Identifier:** Button `data-testid="waypoint-add-on-route-btn"` + `handleProfileAdd` + `addModeHint`

## Estimated Scope

- **LoC:** ~30
- **Files:** 2
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `EditStagesPanelNew.svelte` Z.138 `handleProfileAdd(fraction)` | Funktion (existierend) | Fügt interpolierten Wegpunkt an gegebener Profil-Position ein; wird nach Fix auch `addModeHint` zurücksetzen |
| `frontend/src/lib/components/trip-detail/waypoints/ProfileEditor.svelte` `data-testid="profile-add-area"` | Komponente (existierend) | Transparente Klickfläche über dem Höhenprofil; ruft `onProfileAdd` auf, das auf `handleProfileAdd` gemappt ist |
| `.cascade-prompt`-Pattern Z.226–252 | CSS/HTML-Pattern (existierend) | Vorlage für den Info-Strip (Struktur und Stil analog übernehmen) |
| `frontend/src/lib/components/edit/issue_503_etappen_waypoints.test.ts` | Testdatei (existierend) | Erhält 3 neue Source-Inspection-Tests für den Button-Fix |

## Implementation Details

```
1. State hinzufügen (Z. nach bestehenden $state-Deklarationen):
     let addModeHint = $state(false);

2. Button entsperren (Z.292):
   Vorher:  <button disabled data-testid="waypoint-add-on-route-btn">+ auf Route</button>
   Nachher: <button
               data-testid="waypoint-add-on-route-btn"
               onclick={() => { addModeHint = true; }}
             >+ auf Route</button>
   → kein disabled-Attribut, kein disabled-Prop

3. handleProfileAdd (Z.138) um Reset erweitern:
   Am Ende der Funktion (nach Waypoint-Einfügen):
     addModeHint = false;

4. Info-Strip einfügen — direkt oberhalb der Profil-Card,
   analog zum .cascade-prompt-Pattern (Z.226–252):
   {#if addModeHint}
     <div class="add-mode-hint" role="status">
       <span>Klicke im Höhenprofil, um einen Wegpunkt einzufügen</span>
       <button
         class="add-mode-hint-close"
         aria-label="Hinweis schließen"
         onclick={() => { addModeHint = false; }}
       >×</button>
     </div>
   {/if}

   CSS im <style>-Block (kein Tailwind, konsistent mit bestehendem Muster):
     .add-mode-hint {
       display: flex;
       align-items: center;
       justify-content: space-between;
       padding: 6px 12px;
       background: var(--g-surface-2, #f0ede8);
       border-left: 3px solid var(--g-accent);
       font-size: 13px;
       color: var(--g-ink-2);
       margin-bottom: 4px;
     }
     .add-mode-hint-close {
       background: none;
       border: none;
       cursor: pointer;
       font-size: 16px;
       line-height: 1;
       color: var(--g-ink-3);
       padding: 0 4px;
     }

5. Tests (issue_503_etappen_waypoints.test.ts) — Source-Inspection:
   T1: Datei enthält kein disabled-Attribut am waypoint-add-on-route-btn
   T2: Datei enthält addModeHint als $state(false)
   T3: Datei enthält den Text "Klicke im Höhenprofil" als Info-Strip-Inhalt
```

## Expected Behavior

- **Input:** Nutzer klickt den Button „+ auf Route" in der Wegpunkt-Sidebar
- **Output:** Info-Strip erscheint unmittelbar oberhalb des Höhenprofils mit dem Text „Klicke im Höhenprofil, um einen Wegpunkt einzufügen" und einem „×"-Schließ-Button
- **Side effects:**
  - Klick auf „×" setzt `addModeHint = false` → Strip verschwindet
  - Klick auf die `profile-add-area` (Höhenprofil) ruft `handleProfileAdd` auf → Wegpunkt wird eingefügt → `addModeHint = false` → Strip verschwindet automatisch
  - Map-Klick bleibt out of scope (MapCanvas unterstützt kein Klick-Add)

## Acceptance Criteria

- **AC-1:** Given die WaypointSidebar ist geöffnet / When der Button „+ auf Route" gerendert wird / Then besitzt er kein `disabled`-Attribut und hat einen funktionsfähigen `onclick`-Handler
  - Test: Source-Inspection — `EditStagesPanelNew.svelte` enthält KEIN Muster `waypoint-add-on-route-btn[^>]*disabled` und enthält `onclick` im Kontext des Buttons

- **AC-2:** Given der Button „+ auf Route" ist klickbar / When der Nutzer ihn klickt / Then erscheint ein Info-Strip oberhalb des Höhenprofils mit dem Text „Klicke im Höhenprofil, um einen Wegpunkt einzufügen"
  - Test: Source-Inspection — `EditStagesPanelNew.svelte` enthält den String `Klicke im Höhenprofil` und die State-Variable `addModeHint`

- **AC-3:** Given der Button existiert / When der DOM gerendert ist / Then trägt er `data-testid="waypoint-add-on-route-btn"` (unverändert)
  - Test: Source-Inspection — `EditStagesPanelNew.svelte` enthält `data-testid="waypoint-add-on-route-btn"`

- **AC-4:** Given der Info-Strip ist sichtbar / When der Nutzer einen Klick im Höhenprofil auslöst und `handleProfileAdd` ausgeführt wird / Then verschwindet der Info-Strip automatisch
  - Test: Source-Inspection — `handleProfileAdd` in `EditStagesPanelNew.svelte` setzt `addModeHint = false` nach dem Einfügen

## Known Limitations

- Map-Klick-Add ist nicht Teil dieses Fixes — `MapCanvas.svelte` unterstützt ausschließlich `onWaypointActivate`, kein positionsbasiertes Einfügen per Kartenklick (separates Feature).
- Der Info-Strip informiert den Nutzer nur; er aktiviert keinen gesonderten Interaktionsmodus — das Höhenprofil nimmt Klicks bereits im Normalzustand entgegen.

## Changelog

- 2026-06-02: Initial spec created
