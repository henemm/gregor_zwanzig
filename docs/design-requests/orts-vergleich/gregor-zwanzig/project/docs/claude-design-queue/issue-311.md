# #311 — Design: Compare-Screen — Detailspecs Sidebar + Matrix + Banner (Desktop)

**Labels:** `priority:medium` `frontend` `area:compare` `for:claude-design`
**URL:** https://github.com/henemm/gregor_zwanzig/issues/311
**Erstellt:** 2026-05-21

---

## Was fehlt

Der Compare-Screen (`/compare`) hat einen groben Soll-Mockup (`soll-flow3A-sidebar-overview.png`), aber **keine Detailspecs** für die einzelnen Komponenten. Ich muss aktuell Abstände, Breiten und Farben raten.

## Was ich brauche

Detaillierte Maßangaben und Token-Nutzung für Desktop (1680 px laut Screen-Kanon):

### LocationsRail (linke Sidebar)
- Breite: ? px (aktuell ~260 px hardcoded)
- Gruppen-Header: Welches Typografie-Muster? (Eyebrow? Fettschrift?)
- Ort-Zeile: Checkbox-Layout, aktiver Zustand (Accent-Left-Border?)
- „+ Gruppe" / „+ Ort" Buttons: Position und Stil

### PresetHeader (oberhalb Matrix)
- Welche Felder kompakt nebeneinander: Datum-Range, Zeitfenster, Forecast-Stunden, Aktivitätsprofil
- Wie werden Preset-Namen angezeigt?

### CompareMatrix (Hauptbereich)
- Zellen-Padding: ? px
- Gewinner-Hervorhebung: Farbe, Border oder Background?
- Score-Balken: Höhe, Farbe, Radius

### RecommendationBanner
- Hintergrundfarbe: `--g-surface-1` oder `--g-accent-tint`?
- Icon + Text-Layout
- Button-Stil

### HourlyMatrix (stündliche Detailansicht)
- Wann sichtbar (nach Klick auf Ort)?
- Wie ein-/ausblenden (Toggle, Accordion, Panel)?

## Betroffene Dateien

- `frontend/src/lib/components/compare/LocationsRail.svelte`
- `frontend/src/lib/components/compare/PresetHeader.svelte`
- `frontend/src/lib/components/compare/CompareMatrix.svelte`
- `frontend/src/lib/components/compare/RecommendationBanner.svelte`
- `frontend/src/lib/components/compare/HourlyMatrix.svelte`
