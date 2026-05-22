---
entity_id: bug_273_coordinate_inputmode
type: bugfix
created: 2026-05-22
updated: 2026-05-22
status: draft
version: "1.0"
tags: [bugfix, ios, safari, mobile, inputmode, coordinates, frontend, issue-273]
---

<!-- Issue #273 — Bug: Trip-Edit – Koordinaten-Eingabe ohne Mobile-Strategie -->

# Issue #273 — Bug-Fix: `inputmode="decimal"` für Koordinaten-Inputs im Trip-Editor

## Approval

- [ ] Approved

## Zweck

Auf iOS Safari öffnen `<input type="number">`-Felder ohne `inputmode`-Attribut das alphanumerische Standard-Keyboard statt des numerischen Dezimal-Pads. Im Trip-Bearbeiten-View gibt es drei solche Felder (Latitude, Longitude, Elevation), bei denen ausschließlich Dezimalzahlen sinnvoll sind. Das Hinzufügen von `inputmode="decimal"` erzwingt auf iOS das richtige Tastaturlayout und vermeidet fehleranfällige Eingaben.

Das responsive Layout (gestapelt auf Mobile <640 px, Grid auf Desktop) wurde bereits bei Bug #283 implementiert und ist nicht Gegenstand dieser Spec.

## Quelle / Source

**Geänderte Datei:**
- `frontend/src/lib/components/edit/EditStagesSection.svelte` — 3 `<Input>`-Elemente erhalten `inputmode="decimal"`

**NICHT ändern:**
- `frontend/src/lib/components/ui/input/input.svelte` — reicht `{...restProps}` durch, `inputmode` wird automatisch an das native `<input>` weitergereicht
- `frontend/src/lib/components/edit/TripEditView.svelte` — kein Änderungsbedarf
- Alle anderen Dateien

> **Schicht-Hinweis:** Ausschließlich Frontend-Layer (`frontend/src/`). Kein Go-API-Code, kein Python-Backend betroffen.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/components/ui/input/input.svelte` | Svelte-Komponente | Verteilt `{...restProps}` an natives `<input>` — `inputmode` wird ohne Änderung durchgereicht |

## Implementation Details

In `EditStagesSection.svelte` erhalten folgende drei `<Input>`-Elemente das Attribut `inputmode="decimal"`:

| data-testid | Feld | Zeile (ca.) |
|-------------|------|-------------|
| `wp-lat` | Latitude | 138 |
| `wp-lon` | Longitude | 147 |
| `wp-ele` | Elevation | 157 |

### Änderung je Input (Beispiel `wp-lat`)

```svelte
<!-- vorher -->
<Input
  data-testid="wp-lat"
  type="number"
  name="lat"
  placeholder="Lat"
  bind:value={wp.lat}
  step="0.0001"
  class="g-num-input text-right w-full ..."
/>

<!-- nachher -->
<Input
  data-testid="wp-lat"
  type="number"
  inputmode="decimal"
  name="lat"
  placeholder="Lat"
  bind:value={wp.lat}
  step="0.0001"
  class="g-num-input text-right w-full ..."
/>
```

Analoges gilt für `wp-lon` und `wp-ele`. Nur das Attribut `inputmode="decimal"` wird hinzugefügt — keine weiteren Änderungen an Logik, Layout oder Styles.

### LoC-Budget

| Datei | Δ LoC | Zählt |
|-------|--------|-------|
| `frontend/src/lib/components/edit/EditStagesSection.svelte` | +3 | nein (Frontend-Asset) |
| **Gesamt (zählend)** | **0** | **< 250 LoC-Limit** |

## Expected Behavior

- **Input:** Nutzer tippt auf ein Koordinatenfeld auf iOS
- **Output:** Dezimal-Tastatur erscheint (mit Komma/Punkt-Taste), kein alphanumerisches Keyboard
- **Side effects:** Keine — `inputmode` ist ein reines Hint-Attribut; Desktop-Browser ignorieren es oder verhalten sich äquivalent

## Acceptance Criteria

**AC-1:** Given iOS Safari auf einem 375 px-Viewport, When das Latitude-Feld (`wp-lat`) fokussiert wird, Then erscheint das numerische Dezimal-Keyboard (nicht das Standard-Keyboard)
  - Test: (populated after /tdd-red)

**AC-2:** Given iOS Safari auf einem 375 px-Viewport, When das Longitude-Feld (`wp-lon`) fokussiert wird, Then erscheint das numerische Dezimal-Keyboard
  - Test: (populated after /tdd-red)

**AC-3:** Given iOS Safari auf einem 375 px-Viewport, When das Elevation-Feld (`wp-ele`) fokussiert wird, Then erscheint das numerische Dezimal-Keyboard
  - Test: (populated after /tdd-red)

**AC-4:** Given ein beliebiger Desktop-Browser, When ein Koordinatenfeld fokussiert wird, Then ändert sich das Verhalten gegenüber dem Ist-Stand nicht (Desktop-Layouts und Eingabe unverändert)
  - Test: (populated after /tdd-red)

**AC-5:** Given die gerenderte HTML-Ausgabe von EditStagesSection, When die Koordinaten-Inputs geprüft werden, Then hat jedes der drei Felder das Attribut `inputmode="decimal"` im DOM
  - Test: (populated after /tdd-red)

## Known Limitations

- **Kein automatisierter iOS-Keyboard-Test möglich:** Das tatsächlich angezeigte Keyboard ist nur auf echtem iOS-Gerät oder Xcode-Simulator prüfbar. AC-1 bis AC-3 werden manuell verifiziert; AC-5 ist automatisiert testbar (DOM-Attribut-Check via Playwright).
- **`inputmode="decimal"` vs. `inputmode="numeric"`:** `decimal` erlaubt Komma/Punkt für Dezimalstellen; `numeric` zeigt nur Ziffern ohne Dezimaltrenner. Für Koordinaten (Lat/Lon mit 4 Dezimalstellen) ist `decimal` korrekt.

## Out of Scope

- Karten-Integration oder Vollbild-Karte auf Mobile (im Issue erwähnt, aber eigenes Feature)
- Responsive Layout-Änderungen (bereits in Bug #283 implementiert)
- Andere Formulare oder Seiten außer `EditStagesSection.svelte`

## Changelog

- 2026-05-22: Initial spec erstellt. 1 Datei, +3 LoC. Behebt fehlendes `inputmode="decimal"` auf Koordinaten-Inputs.
