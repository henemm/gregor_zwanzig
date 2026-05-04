---
entity_id: wizard_step2_mobile_waypoint_row
type: bugfix
created: 2026-05-04
updated: 2026-05-04
status: draft
version: "1.0"
tags: [bugfix, frontend, mobile, responsive, svelte, tailwind, issue-106]
---

# Bug #106 — Wegpunkt-Zeile auf Mobile zu eng

## Approval

- [ ] Approved

## Purpose

Die Wegpunkt-Eingabezeile in `WizardStep2Stages.svelte` verwendet feste Pixel-Breiten (`w-32`, dreimal `w-24`) in einem `flex`-Container ohne Responsive-Breakpoints. Auf einem 375px-Viewport (iPhone SE) werden alle Eingabefelder abgeschnitten, da der Gesamt-Bedarf (~480px) den verfügbaren Platz (~335px) um ca. 145px übersteigt. Der Fix ersetzt das starre Flex-Layout durch ein Mobile-First-Grid-Layout, das auf Mobile zwei Zeilen verwendet (Name + Trash-Button oben, Lat/Lon/Höhe als 3-Spalten-Grid darunter) und auf Desktop (≥ 640px) das bisherige Aussehen beibehält.

## Source

- **File:** `frontend/src/lib/components/wizard/WizardStep2Stages.svelte`
- **Identifier:** Wegpunkt-Zeile, Zeilen 79–111 (innerer Block pro Waypoint im `{#each waypoints}`)

Der zweite betroffene Use-Case (`frontend/src/routes/trips/TripEditView.svelte`, Zeile 91) verwendet dieselbe Komponente und wird automatisch mitrepariert — keine Änderung dort nötig.

## Dependencies

| Komponente | Typ | Zweck |
|---|---|---|
| `WizardStep2Stages.svelte` | zu ändern | Enthält die fehlerhafte Wegpunkt-Zeile |
| `TripEditView.svelte` | read-only | Bindet `WizardStep2Stages` ein — wird implizit mitrepariert |
| `WizardStep4ReportConfig.svelte` | Referenz | Etabliertes Pattern `grid grid-cols-1 sm:grid-cols-3` |
| `WizardStep3Weather.svelte` | Referenz | Gleiches Grid-Pattern (Zeile 183) |
| `frontend/src/routes/locations/+page.svelte` | Referenz | Doppel-Button-Pattern `hidden sm:inline-flex` / `sm:hidden` |
| `frontend/src/routes/trips/+page.svelte` | Referenz | Doppel-Button-Pattern (Zeilen 261–262) |
| `frontend/e2e/trip-wizard.spec.ts` | zu ändern | Neue Mobile-Viewport-Tests (Bug #106) |

## Root Cause

Wegpunkt-Zeile mit `flex items-center gap-2` und festen Pixel-Breiten:

| Element | Breite |
|---------|--------|
| Input Name | `w-32` (128 px) |
| Input Lat | `w-24` (96 px) |
| Input Lon | `w-24` (96 px) |
| Input Höhe | `w-24` (96 px) |
| Trash-Button | ~32 px |
| 4× `gap-2` | 32 px |
| **Summe** | **~480 px** |

Verfügbarer Platz auf 375 px Viewport mit Card `p-4` (32 px) + `ml-2` (8 px): **~335 px**. Kein Breakpoint, kein `flex-wrap` → Werte werden abgeschnitten.

## Implementation Strategy

### Ziel-Layout

```
Mobile (< 640 px):
+---------------------------+
| Name              [🗑]    |   ← flex, justify-between
+------+--------+-----------+
| Lat  | Lon    | Höhe (m)  |   ← grid-cols-3, gap-2
+------+--------+-----------+

Desktop (≥ 640 px):
+----------+------+------+----------+----+
| Name     | Lat  | Lon  | Höhe (m) | 🗑 |   ← unverändert
+----------+------+------+----------+----+
```

### Änderungen in `WizardStep2Stages.svelte` (Zeilen 79–111)

Das bestehende `flex items-center gap-2`-Wrapper-Div wird ersetzt durch einen äußeren Container mit zwei Zuständen:

**Äußerer Container (ersetzt bisherigen Flex-Wrapper):**
```html
<div class="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-2">
```

**Mobile Zeile 1 — Name + Trash (nur Mobile sichtbar):**
```html
<div class="flex items-center justify-between gap-2 sm:contents">
  <input ... class="flex-1 sm:w-32 ..." />   <!-- Name -->
  <button ... class="h-11 w-11 sm:hidden ...">  <!-- Trash Mobile, 44×44 px -->
</div>
```

**Mobile Zeile 2 — Lat / Lon / Höhe:**
```html
<div class="grid grid-cols-3 gap-2 sm:contents">
  <input type="number" ... />   <!-- Lat  -->
  <input type="number" ... />   <!-- Lon  -->
  <input type="number" ... class="[appearance:textfield] ..." />  <!-- Höhe -->
</div>
```

**Desktop-Trash (nur Desktop sichtbar):**
```html
<button ... class="hidden sm:inline-flex ...">  <!-- Trash Desktop -->
```

**Wichtige Detailregeln:**
- Trash-Button Desktop: behält bestehende Größe und Klassen, ergänzt `hidden sm:inline-flex`
- Trash-Button Mobile: neu, `h-11 w-11` (44×44 px, Apple HIG Touch-Target), `sm:hidden`
- `[appearance:textfield]` auf Höhen-Input ergänzen, falls Playwright-Test `boundingBox().width > 40` fehlschlägt (Number-Spinner überschießen in engen Containern)
- `ml-2` auf dem Eltern-Div (Zeile 76) bleibt unangetastet — 327 px Restplatz reichen für 3 Spalten
- Etappen-Zeile (Zeilen 62–74) wird **nicht** angefasst — nicht im Scope

### Neue Tests in `frontend/e2e/trip-wizard.spec.ts`

Zwei neue `test()`-Blöcke unter einem gemeinsamen `describe('Bug #106 – Wegpunkt Mobile')`. Beide laufen mit `test.use({ viewport: { width: 375, height: 667 } })` (iPhone SE):

**Test 1 — Alle 4 Inputs sichtbar (Breite > 40 px):**
```ts
// selectors: [data-testid="wp-name"], [data-testid="wp-lat"], [data-testid="wp-lon"], [data-testid="wp-ele"]
for (const sel of inputSelectors) {
  const box = await page.locator(sel).boundingBox();
  expect(box?.width).toBeGreaterThan(40);
}
```

**Test 2 — Trash-Button Touch-Target ≥ 44×44 px:**
```ts
const trashBox = await page.locator('[data-testid="wp-trash-mobile"]').boundingBox();
expect(trashBox?.width).toBeGreaterThanOrEqual(44);
expect(trashBox?.height).toBeGreaterThanOrEqual(44);
```

**Hinweis:** Ein zunächst geplanter Test auf horizontales Page-Overflow (`document.documentElement.scrollWidth <= clientWidth`) wurde verworfen, weil das aktuelle defekte Layout die Inputs intern quetscht statt überzulaufen — der Test war auch im RED-Zustand grün und damit kein gültiger TDD-Beweis. Die beiden verbleibenden Tests prüfen das Symptom direkt (Eingabefelder zu schmal / Trash-Button zu klein für Touch).

## Expected Behavior

- **Mobile (< 640 px):** Name-Input nimmt volle verfügbare Breite ein (flex-1), darunter Lat/Lon/Höhe als gleichgroße 3-Spalten-Grid. Kein horizontaler Page-Overflow. Trash-Button 44×44 px, rechts neben Name-Input.
- **Desktop (≥ 640 px):** Einzeiliege Darstellung wie bisher — Name (`w-32`), Lat/Lon/Höhe je `w-24`, Trash-Button rechts.
- **TripEditView:** Identisches Verhalten, da dieselbe Komponente eingebunden wird.
- **Side effects:** Keine — nur Tailwind-Klassen und Wrapper-Divs, keine Logik-Änderungen.

## Acceptance Criteria

- [ ] Alle 4 Waypoint-Inputs haben `boundingBox().width > 40` auf 375×667-Viewport
- [ ] Trash-Button Mobile ≥ 44×44 px (Touch-Target)
- [ ] Desktop-Layout optisch unverändert (manuelle Sichtkontrolle)
- [ ] Trip-Edit-Akkordeon „Etappen" auf Safari Mobile korrekt (Hard-Reload Cmd+Shift+R)
- [ ] Etappen-Zeile (Name + Datum + Trash) unverändert
- [ ] `npm run build` ohne Fehler

## Files to Modify

| Datei | Δ LoC |
|---|---|
| `frontend/src/lib/components/wizard/WizardStep2Stages.svelte` | +15–18 / -5 |
| `frontend/e2e/trip-wizard.spec.ts` | +30 / 0 |

## Edge Cases

- **Number-Input-Spinner (< 320 px):** Browser-native Spinner können in engen Containern überschießen. Falls Test 2 fehlschlägt: `[appearance:textfield]` auf Höhen-Input ergänzen.
- **Viewports < 320 px:** Akzeptiert als Edge Case — „Höhe (m)"-Placeholder wird knapp, kein Fix geplant.
- **Safari Closure-Binding:** Trash-Button-Handler muss Factory-Pattern verwenden (`make_delete_waypoint_handler()`), falls Klick auf Mobile/Safari nicht reagiert (CLAUDE.md → NiceGUI Safari-Kompatibilität). Für Svelte-Event-Handler gilt das nicht — kein Handlungsbedarf.

## Bewusst NICHT im Scope

- Etappen-Zeile (Zeilen 62–74: Etappenname + Datum + Trash) — nicht im Issue
- Strukturelle Komponenten-Refaktorierung
- Visual-Regression-Tooling / Screenshot-Baseline
- Viewports < 320 px

## Risk Analysis

- Kein Risiko für bestehende Desktop-Funktionalität: `sm:`-Breakpoints greifen erst ab 640 px, darunter alles unverändert.
- Doppel-Button-Pattern ist im Projekt etabliert (`locations/+page.svelte`, `trips/+page.svelte`) — keine unbekannten Safari-Überraschungen zu erwarten.
- `sm:contents` (CSS `display: contents`) wird genutzt, um die Mobile-Wrapper-Divs auf Desktop transparent zu machen. Browser-Support seit Safari 11.1 / Chrome 65 / Firefox 37 (2018) — kein Risiko in 2026.

## Bezug

- GitHub Issue #106
- Konsistenz-Referenzen: `WizardStep4ReportConfig.svelte:174`, `WizardStep3Weather.svelte:183`, `locations/+page.svelte:157`, `trips/+page.svelte:261–262`

## Changelog

- 2026-05-04: Initial spec
- 2026-05-04: Risk-Analysis-Eintrag zu `sm:contents` korrigiert (Widerspruch zu Code-Beispielen aufgelöst; Browser-Support seit 2018, kein Risiko)
- 2026-05-04: Test-Plan auf 2 Tests reduziert (Page-Overflow-Test entfernt — war im RED-Zustand grün und damit kein gültiger TDD-Beweis; das aktuelle defekte Layout quetscht Inputs intern statt überzulaufen)
