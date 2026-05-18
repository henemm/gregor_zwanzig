# Context: Epic #138 Phase 2 — Metriken-Editor Komponenten (Issues #174–178)

## Request Summary

Aufbauend auf dem bereits implementierten `WeatherMetricsTab.svelte` (Epic #138 Phase 1, VERIFIED) werden 5 neue Sub-Features für den Wetter-Metriken-Editor gebaut: MetricGroup/MetricCheckbox-Komponenten (#174), ModeBtn-Pill mit INDICATOR_MAP (#175), live TablePreview (#176), SavePresetDialog (#177) und dirty-State-Warnung (#178).

## Überblick der Issues

| Issue | Titel | Kernaufgabe |
|-------|-------|-------------|
| #174 | Metriken-Editor: Metriken-Gruppen + Checkbox-Grid | MetricGroup (Eyebrow + Zähler) + MetricCheckbox (Custom-CB, Label, Unit, Short) |
| #175 | Metriken-Editor: Roh/Indikator-Toggle | ModeBtn-Pill pro Metrik mit INDICATOR_MAP (12 Metriken) |
| #176 | Metriken-Editor: Tabellen-Vorschau live | TablePreview mit aktiven Spalten, 4 Beispiel-Zeilen |
| #177 | Metriken-Editor: 'Als Preset speichern' Dialog | SavePresetDialog-Modal mit Name, Beschreibung, Zusammenfassung |
| #178 | Metriken-Editor: Ungespeichert-Warnung + State | dirty-State, Pill 'Ungespeicherte Änderungen', Verwerfen/Speichern |

## Related Files

| File | Relevanz |
|------|---------|
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` | Haupt-Komponente — wird refaktoriert/erweitert |
| `frontend/src/lib/components/trip-detail/PresetRow.svelte` | Bestehende Preset-Zeilen (von #173) — bleibt unverändert |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | Rendert WeatherMetricsTab im "Wetter-Metriken"-Tab |
| `frontend/src/lib/types.ts` | TypeScript-Interfaces (Trip, WeatherConfigMetric, DisplayConfig) |
| `frontend/src/lib/components/ui/eyebrow/Eyebrow.svelte` | Eyebrow-Komponente für MetricGroup-Header |
| `frontend/src/lib/components/ui/pill/Pill.svelte` | Pill-Komponente für dirty-State + ModeBtn |
| `frontend/src/lib/components/ui/dialog/` | Dialog-Komponenten für SavePresetDialog |
| `frontend/src/lib/components/ui/table/` | Tabellen-Komponenten für TablePreview |
| `src/app/metric_catalog.py` | Single Source of Truth: alle 25 Metriken in 5 Kategorien |
| `api/routers/config.py` | Backend: /api/metrics + /api/templates Endpoints |
| `docs/specs/modules/epic_138_metriken_editor.md` | Bestehende Spec (Phase 1) — als Basis-Referenz |

## Bestehende Implementation (Phase 1 — VERIFIED)

`WeatherMetricsTab.svelte` ist voll funktionsfähig mit:
- Preset-Liste (PresetRow-Komponenten, 7 Templates)
- 25 Metrik-Checkboxen in 5 Kategorien (einfache HTML-Checkboxen)
- Roh/Indikator-Toggle (zwei Buttons) für 9 Metriken mit `has_friendly_format`
- Speichern-Button mit Full-Replace PUT

Die Issues #174–178 bauen ÜBER dieser Basis eine poliertere UI-Schicht auf.

## Analyseergebnisse (Phase 2)

### Geklärt

| Frage | Befund |
|-------|--------|
| 25 vs. 26 Metriken | **25 Metriken** im Backend (metric_catalog.py) — Spec-Angabe "26" ist ungenau |
| INDICATOR_MAP 12 vs. 9 | 9 backend-seitige (`has_friendly_format=True`) + 3 frontend-erweiterte: `wind`, `gust`, `rain_probability` |
| TablePreview Daten | **Statische Beispieldaten** (keine API-Calls) — rein client-seitig |
| dirty-State vorhanden? | **Nein** — kein `isDirty`/`dirty` im Frontend implementiert |
| INDICATOR_MAP vorhanden? | **Nein** — nur lokale `friendlyMap: Record<string, boolean>` |
| User-Preset-Backend | **Nein** — kein Endpoint; Templates sind code-seitig hardcodiert |
| Kategorie-Namen | Bleiben wie in Phase 1: Temperatur/Wind/Niederschlag/Atmosphäre/Winter/Schnee |

### Implementierungsstrategie

**Neue Dateien (4 Stück):**
- `MetricCheckbox.svelte` — Custom-Checkbox mit Label, Unit, Short-Key, ModeBtn-Pills
- `MetricGroup.svelte` — Eyebrow + aktiver Zähler (Wrapper für eine Kategorie)
- `TablePreview.svelte` — Vorschau-Tabelle mit statischen Beispieldaten
- `SavePresetDialog.svelte` — Modal, speichert in localStorage

**Geänderte Datei (1 Stück):**
- `WeatherMetricsTab.svelte` — Umbau auf Subkomponenten + dirty-State + INDICATOR_MAP

**Reihenfolge:** #178 (dirty-State) → #174 (MetricGroup/MetricCheckbox) → #175 (ModeBtn-Pill) → #176 (TablePreview) → #177 (SavePresetDialog)

**LoC-Schätzung:** ~380 netto — LoC-Override auf 450 nötig

### SavePresetDialog: localStorage (keine Backend-Änderung)

User-definierte Presets werden in `localStorage['gz-metric-presets']` gespeichert (JSON-Array). Kein neuer Go-Endpoint nötig. Begründung: alle 5 Issues sind rein frontend-seitig; Backend-Erweiterung wäre separates Epic.

## Existing Patterns

- **Eyebrow-Header-Pattern:** `WeatherMetricsPreviewCard.svelte` und `TripHero.svelte` nutzen `<Eyebrow>` als Kategorie-Label
- **dirty-State-Pattern:** Kein direktes Vorbild im Projekt; `AlertRulesEditor` emittiert Changes über Binding, kein internes dirty-Flag
- **Dialog-Pattern:** `bits-ui` Dialog-Komponenten liegen bereits vor (`frontend/src/lib/components/ui/dialog/`)
- **Table-Pattern:** `bits-ui` Table-Komponenten liegen vor (`frontend/src/lib/components/ui/table/`)
- **Pill-Pattern:** `<Pill tone="...">` aus `frontend/src/lib/components/ui/pill/`

## Dependencies

- **Upstream:** `/api/metrics` (Backend), `/api/templates` (Backend), `trip.display_config` (Trip-State)
- **Downstream:** Trip-Report-Formatter konsumiert persistierte Metriken-Config
- **Neu ggf.:** `POST /api/user-presets` für SavePresetDialog (falls User-Presets serverseitig gespeichert werden)

## Design-System Tokens (relevant)

- `--g-accent` (#c45a2a) — aktive Checkboxen, aktive ModeBtn-Pill
- `--g-ink-faint` (#9c9a90) — inaktive Labels, Unit-Text, Eyebrow
- `--g-surface-1` (#edeae1) — MetricGroup-Hintergrund
- `--g-border` — Trennlinien zwischen Gruppen

## Risks & Considerations

1. **Refactoring-Risiko:** WeatherMetricsTab.svelte ist bereits funktionsfähig und in Produktion. Komponenten-Extraktion darf Verhalten nicht ändern.
2. **SavePresetDialog Backend-Scope:** Falls User-Presets serverseitig gespeichert werden müssen, entsteht ein neuer Go-Endpoint. Scope zu klären.
3. **TablePreview-Performance:** Live-Update bei jeder Checkbox-Änderung darf keinen API-Call triggern (rein client-seitig mit Mockdaten).
4. **dirty-State-Verlust:** Tab-Wechsel ohne Speichern soll warnen — ggf. `beforeunload`-Handler oder eingebettete Warnung nötig.
5. **LoC-Budget:** 5 Issues × ca. 100-150 LoC = ~600 LoC gesamt. LoC-Override notwendig.
