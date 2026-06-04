# Spec: Issue #585 — Waypoint-Editor Design-Fidelity 1:1

**Status:** Draft  
**Issue:** #585  
**Quelle:** `claude-code-handoff/current/jsx/screen-waypoint-editor.jsx`  
**SOLL-Screenshot:** `claude-code-handoff/current/soll/J-waypoint-editor-etappen-tab.png`

---

## Kontext

Der Tab "Etappen & Wegpunkte" in TripEditView weicht visuell vom JSX-Design ab.
Ziel: 1:1-Umsetzung aus `screen-waypoint-editor.jsx` — kein eigenständiger Screen,
sondern der eingebettete Editor-Kern (`embedded = true`).

---

## Acceptance Criteria

**AC-1:** Given EtappenStrip wird gerendert / When User sieht den Strip / Then zeigt die Strip-Leiste oben links den Eyebrow-Text "ETAPPEN · DRAG ZUM SORTIEREN · + PAUSE ZWISCHEN" und rechts daneben eine mono Zähler-Zeile "N GPX · N Pause" (10px, ink-4).

**AC-2:** Given EtappenStrip enthält mehrere Stages / When User den Strip betrachtet / Then erscheinen zwischen je zwei StageCards dünne `PauseInsertGap`-Trennelemente — im Ruhezustand 8px breit mit 1px Separator-Linie, bei Hover expandieren sie auf 56px und zeigen ein "+ Pause"-Badge in accent-Farbe.

**AC-3:** Given EtappenStrip / When User den Strip betrachtet / Then gibt es am rechten Ende einen "+ Etappe"-Button (dashed border, ghost-style, minHeight 88px, mono 11px).

**AC-4:** Given StageCard / When eine normale Etappe angezeigt wird / Then hat die Karte: Breite 200px, minHeight 88px, oben links "⋮⋮ TNN · CODE" in mono (9px, ink-4 normal / accent-deep aktiv), oben rechts ein ×-Entfernen-Button.

**AC-5:** Given StageCard aktiv / When die Karte aktiv ist / Then hat sie `border: 2px solid var(--g-accent)` (kein CSS-outline), inaktive Karten haben 1px solid Rand.

**AC-6:** Given StageCard mit Profil / When eine normale Etappe Waypoints hat / Then zeigt die Karte unten eine SVG-Polyline-Sparkline (height 18px, Stroke accent aktiv / ink-4 inaktiv) — kein `<ElevSparkline>`-Atom.

**AC-7:** Given StageCard Pausetag / When eine Pause-Stage angezeigt wird / Then hat die Karte: dashed Border, card-alt-Hintergrund, kursiven Titel, unten "⌂ Pause · Standort"-Zeile (9px mono).

**AC-8:** Given aktive Stage-Inhaltsbereich / When eine normale Stage aktiv ist / Then zeigt der Header: Eyebrow "ETAPPE · {stage.code}", darunter der Stagename in 32px/600 fontWeight, daneben rechts das Datum-Feld. Unter dem Titel (max 680px Breite): Fließtext "Wegpunkte sind **Wetterscheiden** — Punkte, an denen sich Höhe, Exposition oder Geländekammer ändert. Aus der GPX sind N Wegpunkte entstanden — du kannst sie umbenennen, verschieben, löschen oder eigene ergänzen."

**AC-9:** Given Stage-Inhaltsbereich Padding / When der Editor gerendert wird / Then hat der Inhaltsbereich `padding: 20px 40px 60px` und `maxWidth: 1480px`.

**AC-10:** Given WaypointCard / When eine Waypoint-Zeile angezeigt wird / Then zeigt die Meta-Zeile neben Höhe und Ankunftszeit auch das Typ-Label: "Start", "Ziel", "Gipfel", "Pass", "Tal" oder "Hütte" (aus `waypoint.type`, Fallback "Wegpunkt"). Format: `TypeLabel · N m · HH:MM`.

**AC-11:** Given alle bestehenden Tests / When die Änderungen eingespielt sind / Then laufen alle bestehenden Tests grün (keine Regression).

---

## Technische Umsetzung

### Betroffene Dateien

| Datei | Änderung |
|---|---|
| `frontend/src/lib/components/trip-detail/waypoints/EtappenStrip.svelte` | Eyebrow-Header + PauseInsertGap + Etappe-Button |
| `frontend/src/lib/components/trip-detail/waypoints/StageCard.svelte` | 200px, ⋮⋮-Label, ×-Button, MiniSpark-SVG, Border-statt-Outline |
| `frontend/src/lib/components/edit/EditStagesPanelNew.svelte` | Padding + maxWidth + Etappe-Header-Text |
| `frontend/src/lib/components/trip-detail/waypoints/WaypointCard.svelte` | Typ-Label in Meta |
| `frontend/src/lib/types.ts` | `Waypoint.type?: string` (optional) |

### Nicht geändert

- Route-Struktur bleibt: Waypoint-Editor ist Tab in TripEditView, kein eigener Screen
- Leaflet/MapCanvas bleibt unverändert
- ProfileEditor bleibt unverändert
- PauseStageView bleibt unverändert
- Keine neuen Backend-Endpunkte

### StageCard — MiniSpark-SVG

```svelte
<!-- Inline SVG, height 18px, kein Atom -->
{#if elevData.length >= 2}
  {@const min = Math.min(...elevData)}
  {@const max = Math.max(...elevData)}
  {@const range = max - min || 1}
  {@const W = 174}
  {@const H = 18}
  {@const pts = elevData.map((v, i) =>
    `${((i / (elevData.length - 1)) * W).toFixed(1)},${(H - ((v - min) / range) * (H - 2) - 1).toFixed(1)}`
  ).join(' ')}
  <svg viewBox="0 0 {W} {H}" width="100%" height={H} preserveAspectRatio="none">
    <polyline points={pts} fill="none"
      stroke={active ? 'var(--g-accent)' : 'var(--g-ink-4)'}
      stroke-width="1.2"/>
  </svg>
{/if}
```

### PauseInsertGap-Komponente (neu)

Kleines Inline-Snippet in EtappenStrip — kein eigenes File nötig:
```svelte
<!-- hoverGap === i → Breite 56px + Badge; sonst 8px + 1px Linie -->
```

### Waypoint.type

`type` ist bereits in der Datenquelle vorhanden (Naismith-Backend-Suggestions: `start`, `end`, `summit`, `pass`, `valley`, `hut`). Das Interface bekommt `type?: string` als optionales Feld. Mapping in WaypointCard:
```ts
const typeLabel = { start: 'Start', end: 'Ziel', summit: 'Gipfel', pass: 'Pass', valley: 'Tal', hut: 'Hütte' }
const label = typeLabel[waypoint.type ?? ''] ?? 'Wegpunkt'
```
