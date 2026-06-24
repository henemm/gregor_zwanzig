# Context: fix-622-794-mobile-fidelity

## Request Summary
Zwei Frontend-Aufgaben: (1) Pixel-Fidelity-Gate für #622 (Progressive Trip-Editor) abschließen — die SOLL-vs-IST-Bilder für Route/Etappen/Wegpunkte-Tab prüfen und eventuelle Abweichungen beheben. (2) #794 beheben — auf mobilen Viewports ist der Metrik-Name im Wetter-Metriken-Editor nicht lesbar (Text wird abgeschnitten oder ist zu klein).

## Related Files

| Datei | Relevanz |
|-------|----------|
| `frontend/src/lib/components/trip-new/TripNewEditor.svelte` | Haupt-Komponente des Progressive Editors (6 Tabs inline, 1026 Zeilen) |
| `frontend/src/lib/components/trip-detail/WeatherV2Reihenfolge.svelte` | `.metric-label` mit `nowrap+ellipsis`, kein Mobile-Media-Query — Hauptverdächtiger für #794 |
| `frontend/src/lib/components/trip-detail/TripHeader.svelte` | Mobile-Metriken-Kacheln mit Stat-Komponente, 9px Font |
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` | Outer Layout des Wetter-Tabs (Mobile Single-Column, @899px) |
| `frontend/src/lib/components/atoms/Stat.svelte` | Atom: 9px Label-Font bei `size="sm"` |
| `.claude/hooks/design_fidelity_diff.py` | Pixel-Diff-Tooling für SOLL-IST-Vergleich |
| `.github/issue-assets/soll-trip-new-route-tab.png` | SOLL-Bild Route-Tab |
| `.github/issue-assets/soll-trip-new-etappen-tab.png` | SOLL-Bild Etappen-Tab |
| `.github/issue-assets/soll-trip-new-wegpunkte-tab.png` | SOLL-Bild Wegpunkte-Tab |
| `docs/design-requests/trip-anlegen-2026-06-06/screen-trip-new-v2.jsx` | Verbindliche Design-Quelle Desktop |

## Existing Patterns
- Responsive Breakpoint: `@media (max-width: 899px)` durchgehend im Projekt
- Design-Token: `var(--g-*)` für alle Farben, Abstände, Fonts
- Fidelity-Gate: `python3 .claude/hooks/design_fidelity_diff.py --screen <id>` (Exit 0 = PASS < 10% Diff)
- TripNewEditor hat `tn-desktop`/`tn-mobile` CSS-Klassen für responsives Hiding

## Dependencies
- Upstream #622: Slices 1+2+3 LIVE (Desktop + Wegpunkte-Tab + Mobile-Parität alle CLOSED)
- Upstream #794: `WeatherV2Reihenfolge.svelte` → eingebettet in `WeatherMetricsTab.svelte`
- SOLL-Bilder liegen in `.github/issue-assets/soll-trip-new-*.png` (3 Desktop-Tabs vorhanden)

## Root Cause #794
`WeatherV2Reihenfolge.svelte`: `.metric-label` hat `white-space: nowrap; overflow: hidden; text-overflow: ellipsis;` ohne `@media`-Override für Mobile. Auf engen Viewports werden Metrik-Namen wie "Temperatur", "Windgeschwindigkeit" etc. auf wenige Zeichen abgeschnitten. Zusätzlich: `TripHeader.svelte` Mobile-Kacheln mit `Stat size="sm"` (9px Font) für längere Labels.

## Risks & Considerations
- Fidelity-Gate für #622: Tooling läuft gegen gerendertes Staging-Screenshot — braucht laufenden Playwright
- #794-Fix darf Desktop-Darstellung nicht verändern (`@media`-scoped)
- `TripNewEditor.svelte` ist groß (1026 Zeilen) — Änderungen chirurgisch halten
- Keine neuen Komponenten-Dateien nötig (CSS-Fix in bestehenden Dateien)

## Analysis

### Type
Bug (#794) + Feature-Abschluss / Fidelity-Gate (#622)

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/trip-detail/WeatherV2Reihenfolge.svelte` | MODIFY | `@media (max-width: 899px)` Block: `.metric-label` white-space:normal + `.label-cell` flex-wrap:wrap + `.controls` flex-direction:column |
| `.claude/hooks/design_fidelity_diff.py` | MODIFY | Pre-Actions für Etappen- und Wegpunkte-Tab eintragen (Tab-Klick via Textinhalt-Selektor) |
| `frontend/src/lib/components/trip-new/TripNewEditor.svelte` | MODIFY (bedingt) | Nur wenn Pixel-Diff >10% — CSS-Nacharbeit nach Diff-Auswertung |
| `frontend/src/lib/components/trip-detail/TripHeader.svelte` | kein Fix | Labels bereits kurze Kürzel (max 7 Zeichen), 9px-Font designintentional |

### Scope Assessment
- Dateien fix: 2 (sicher) + 1 (bedingt nach Diff)
- Estimated LoC: +12–18 (CSS) + ~6 (Python Pre-Actions) + X (Diff-Korrekturen)
- Risk Level: NIEDRIG — alle Änderungen `@media`-scoped, kein Desktop-Impact, kein Backend

### Technical Approach

**Reihenfolge: #794 zuerst, dann #622**

**#794 Fix (WeatherV2Reihenfolge.svelte):**
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
Warum Option A (Umbruch) statt B (max-width) oder C (kleinerer Font): Grid-Spalte ist bereits `1fr min-width:0` — feste Breite wäre fragil, Font-Reduktion löst das Problem nicht für lange Namen wie "Windgeschwindigkeit".

**#622 Fidelity-Gate:**
1. `design_fidelity_diff.py` Pre-Actions für Step 2 (Etappen) und Step 3 (Wegpunkte) — Playwright-Klick via `[role="tab"]:has-text("Etappen & GPX")` usw.
2. Diff-Läufe gegen 3 SOLL-PNGs (Route / Etappen / Wegpunkte)
3. Abweichungen > 10%: CSS-Fix in TripNewEditor.svelte, sonst direkt schließen

### Open Questions
- [x] Wo sucht design_fidelity_diff.py die SOLL-PNGs? → .github/issue-assets/ (Tooling-Map muss gecheckt werden)
- [x] TripHeader.svelte braucht keinen Fix — Labels bewusst kurz gehalten
