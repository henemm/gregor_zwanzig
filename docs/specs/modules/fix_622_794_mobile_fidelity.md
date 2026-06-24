---
entity_id: fix_622_794_mobile_fidelity
type: bugfix
created: 2026-06-24
updated: 2026-06-24
status: draft
workflow: fix-622-794-mobile-fidelity
---

# Fix #794 Mobile Metric-Label + #622 Fidelity-Gate Trip-Wizard Abschluss

## Approval

- [ ] Approved

## Purpose

Behebt zwei gebündelte Frontend-Aufgaben: (1) Auf mobilen Viewports werden Metrik-Namen in der Wetter-Reihenfolge-Ansicht abgeschnitten statt umbrochen — das macht sie unleserlich (#794). (2) Das Pixel-Fidelity-Gate für den progressiven Trip-Editor (`/trips/new`) kann die Etappen- und Wegpunkte-Tabs bisher nicht per Playwright ansteuern; Pre-Actions fehlen, deshalb können die SOLL-PNGs nicht automatisch verifiziert werden (#622).

## Source

- **File:** `frontend/src/lib/components/trip-detail/WeatherV2Reihenfolge.svelte`
- **Identifier:** `.metric-label`, `.label-cell`, `.controls` (CSS-Klassen, Mobile-Override)
- **File:** `.claude/hooks/design_fidelity_diff.py`
- **Identifier:** `SCREEN_PRE_ACTIONS` (Dict, Einträge für `I-wizard-step2-etappen` und `I-wizard-step3-wegpunkte`)

## Estimated Scope

- **LoC:** ~25 (CSS-Block ~12 Zeilen + 2 Pre-Action-Einträge ~8 Zeilen + evtl. TripNewEditor.svelte-Korrekturen ~5 Zeilen)
- **Files:** 2 (Pflicht), 1 (bedingt bei Pixel-Diff > 10 %)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/components/trip-new/TripNewEditor.svelte` | Frontend-Komponente | Bedingt: Anpassung nur wenn Fidelity-Diff gegen SOLL-PNGs > 10 % |
| `.github/issue-assets/soll-trip-new-route-tab.png` | SOLL-PNG | Fidelity-Referenz Route-Tab (Step 1) |
| `.github/issue-assets/soll-trip-new-etappen-tab.png` | SOLL-PNG | Fidelity-Referenz Etappen-Tab (Step 2) |
| `.github/issue-assets/soll-trip-new-wegpunkte-tab.png` | SOLL-PNG | Fidelity-Referenz Wegpunkte-Tab (Step 3) |

## Implementation Details

### Fix #794 — Mobile Metric-Label

`WeatherV2Reihenfolge.svelte` enthält aktuell für `.metric-label` die Deklarationen `white-space: nowrap; overflow: hidden; text-overflow: ellipsis;` ohne mobilen Override. Ab 900 px Breite ist das korrekt (Desktop). Unterhalb dieser Schwelle schneidet es Metrik-Namen wie "Windgeschwindigkeit" auf wenige Zeichen ab.

Zu ergänzender CSS-Block:

```css
@media (max-width: 899px) {
  .metric-label {
    white-space: normal;
    overflow: visible;
    text-overflow: clip;
  }
  .label-cell {
    flex-wrap: wrap;
  }
  .controls {
    flex-direction: column;
    align-items: flex-end;
    gap: 4px;
  }
}
```

Der Breakpoint 899 px ist projekt-weit einheitlich (Mobile < 900 px). Kein Design-Token-Eingriff, keine Breaking Change.

### Fix #622 — Fidelity-Gate Pre-Actions

`design_fidelity_diff.py` enthält das Dict `SCREEN_PRE_ACTIONS`. Für die Screens `I-wizard-step2-etappen` und `I-wizard-step3-wegpunkte` fehlen Einträge: Playwright öffnet zwar `/trips/new`, klickt aber nicht den jeweiligen Tab an und screenshottet deshalb immer Step-1-Inhalt.

Zu ergänzende Einträge in `SCREEN_PRE_ACTIONS`:

```python
"I-wizard-step2-etappen": [
    ("click", '[role="tab"]:has-text("Etappen & GPX")'),
    ("wait_selector", '[role="tab"][aria-selected="true"]:has-text("Etappen & GPX")'),
],
"I-wizard-step3-wegpunkte": [
    ("click", '[role="tab"]:has-text("Wegpunkte prüfen")'),
    ("wait_selector", '[role="tab"][aria-selected="true"]:has-text("Wegpunkte prüfen")'),
],
```

Nach Eintrag: Pixel-Diffs gegen alle drei SOLL-PNGs laufen. Liegt ein Diff > 10 %, ist `TripNewEditor.svelte` entsprechend anzupassen (bedingte Datei).

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/trip-detail/WeatherV2Reihenfolge.svelte` | MODIFY | `@media (max-width: 899px)` Block für `.metric-label`, `.label-cell`, `.controls` |
| `.claude/hooks/design_fidelity_diff.py` | MODIFY | Pre-Actions für `I-wizard-step2-etappen` und `I-wizard-step3-wegpunkte` in `SCREEN_PRE_ACTIONS` |
| `frontend/src/lib/components/trip-new/TripNewEditor.svelte` | MODIFY (bedingt) | Nur bei Pixel-Diff > 10 % nach Fidelity-Lauf |

### Estimated Changes

- Files: 2 (Pflicht) + 1 (bedingt)
- LoC: +20/-0 (Pflicht), +5 (bedingt)

## Acceptance Criteria

**AC-1:** Given mobiler Viewport (<900 px) / When Wetter-Reihenfolge-Tab eines Trips geöffnet wird / Then sind alle Metrik-Namen vollständig sichtbar und umbrechen auf mehrere Zeilen statt abgeschnitten zu werden.

**AC-2:** Given mobiler Viewport (<900 px) / When die Controls-Zeile einer Metrik gerendert wird / Then sind Steuerelemente vertikal gestapelt und es gibt keinen horizontalen Overflow.

**AC-3:** Given Desktop-Viewport (≥900 px) / When der Wetter-Reihenfolge-Tab geöffnet wird / Then bleibt das Verhalten unverändert: Metrik-Namen werden einzeilig mit Ellipsis abgekürzt.

**AC-4:** Given `design_fidelity_diff.py` mit eingetragenen Pre-Actions / When Screen `I-wizard-step2-etappen` aufgerufen wird / Then klickt Playwright den Tab "Etappen & GPX" an und der Screenshot zeigt Etappen-Tab-Inhalt statt Route-Tab-Inhalt.

**AC-5:** Given `design_fidelity_diff.py` mit eingetragenen Pre-Actions / When Screen `I-wizard-step3-wegpunkte` aufgerufen wird / Then klickt Playwright den Tab "Wegpunkte prüfen" an und der Screenshot zeigt Wegpunkte-Tab-Inhalt mit maximal 10 % Pixel-Abweichung vom SOLL-PNG.

## Known Limitations

- Der bedingte Edit an `TripNewEditor.svelte` wird erst nach dem Fidelity-Lauf auf Staging bekannt — Scope und LoC können sich leicht erhöhen.
- SOLL-PNGs zeigen Desktop-Viewport; Mobile-Fidelity für den Trip-Wizard wird durch #794-Fix abgedeckt, nicht durch den Fidelity-Gate (der auf Desktop-Referenzbilder läuft).

## Changelog

- 2026-06-24: Initial spec created
