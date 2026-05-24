---
issue: 343
parent_epic: 304
predecessor: 342
workflow: issue_343_horizon_chip_ui
created: 2026-05-23
status: phase1_context
---

# Context: Issue #343 — HorizonChip-UI im Wetter-Editor

> Sub-Issue 2 von Klammer-Epic #304. Backend-Voraussetzung (#342) ist live deployed.

## Request Summary

Frontend-Erweiterung des `WeatherMetricsTab` (Trip-Detail-Wetter-Tab): pro Metrik-Zeile drei togglebare Tag-Chips `heute / morgen / übermorgen` ergänzen, die unabhängig von Aus-Schalter und Roh/Indikator-Modus funktionieren. Speichern via existierender `PUT /api/trips/{id}/weather-config` (Server liest `display_config.metrics[].horizons` schon, Backend-Filter ist live).

## Related Files

| Datei | Relevanz |
|---|---|
| `frontend/src/lib/components/trip-detail/MetricCheckbox.svelte` | Eine Metrik-Zeile (Checkbox + ggf. Roh/Indikator-Pills). **Drei HorizonChips nach den Pills einfügen.** |
| `frontend/src/lib/components/ui/horizon-chip/HorizonChip.svelte` | **NEU** — `[data-slot="horizon-chip"]`-Komponente mit `[data-active]`-Attribut (Vorbild: Pill, Segmented). |
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` | Bringt Daten + Save-Flow. **Neue `horizonsMap: Record<string,{today,tomorrow,day_after}>`** parallel zu `enabledMap`/`friendlyMap`. Dirty-State + Save-Payload erweitern. |
| `frontend/src/lib/components/trip-detail/SavePresetDialog.svelte` | Übergibt heute nur Metric-IDs + Friendly-IDs an `POST /api/metric-presets`. **Muss `horizons` mitschicken.** |
| `frontend/src/lib/components/trip-detail/TablePreview.svelte` | Vorschau-Tabelle pro Metrik-Spalte. **Visualisieren welche Horizonte aktiv sind** (siehe Klärungs-Frage unten). |
| `frontend/src/lib/types.ts` | TypeScript-Type `WeatherConfigMetric` und `MetricPreset` um `horizons?: { today, tomorrow, day_after }` ergänzen — Typ `Horizons` einführen. |
| `frontend/src/lib/components/ui/pill/Pill.svelte` | Vorbild für `[data-slot]`-Pattern. |
| `frontend/src/lib/components/ui/segmented/Segmented.svelte` | Vorbild für `[data-active]`-Attribut + Klick-Handler. |
| `frontend/e2e/weather.spec.ts` | Bestehende Renderer-Tests — eigenständig, betreffen WeatherMetricsTab nicht direkt. Regression beobachten. |

## Existing Patterns

- **`[data-slot]`-Komponenten** mit `[data-active]`-Attribut für Toggle-State; keine Props für Styling, alles via CSS-Attribut-Selektoren in `app.css` oder Scoped-Style.
- **State-Maps in WeatherMetricsTab**: parallele `Record<metric_id, value>`-Maps; `isDirty` ist `JSON.stringify({enabledMap, friendlyMap}) !== savedSnapshot`. Erweiterung um `horizonsMap` analog.
- **Save-Flow**: `PUT /api/trips/{id}/weather-config` mit kompletter `metrics`-Liste (jede mit `metric_id`, `enabled`, `use_friendly_format`, neu `horizons`).
- **Preset-Flow**: `POST /api/metric-presets` legt User-Preset an — Body bekommt jetzt strukturierte `[]DisplayMetric` statt `[]string` + `[]friendly_ids` (Backend hat Compat-Layer für beide).

## Backend-API (live aus #342)

```
GET   /api/metric-presets              → [MetricPreset]
POST  /api/metric-presets              → MetricPreset (akzeptiert Legacy + Neu-Schema)
PATCH /api/metric-presets/{id}         → MetricPreset (Read-Modify-Write)
DELETE /api/metric-presets/{id}        → 204

MetricPreset {
  id, name, description, is_default, created_at,
  metrics: [
    { metric_id, enabled, use_friendly_format,
      horizons: { today, tomorrow, day_after } }
  ]
}
```

`Trip.display_config.metrics[]` analog (additiv erweitert, optional `horizons`).

## Dependencies

- **Upstream:** Backend-Felder aus #342 (`horizons`-Objekt im JSON, Filter im Renderer).
- **Downstream:** 
  - #344 (Account-Karte) wird die HorizonChip-Komponente in der Preset-Verwaltung wiederverwenden.
  - #345 (Konsolidierung) ersetzt den alten `EditWeatherSection`-Pfad durch denselben WeatherMetricsTab-Komponenten-Stack — bekommt HorizonChips dadurch automatisch.

## Existing Specs

- `docs/specs/modules/issue_342_pro_metrik_horizon_backend.md` — Backend (live).
- `docs/specs/modules/epic_138_174_178_metriken_ui.md` — Phase 2 des Metric-Editors (heutiger Stand des WeatherMetricsTab).
- `docs/specs/modules/issue_285_weather_section_restyle.md` — Brand-Token-Restyle, `[data-slot]`-Pattern.
- `docs/specs/ux_redesign_navigation.md` (§ Wetter-Template) — Soll-Vision der Spec.

## Risks & Considerations

1. **TablePreview-Darstellung offen.** Issue bietet zwei Optionen: (a) ein Tag-Hinweis pro Spalte (z.B. kleines Pill-Trio im Header), (b) drei separate Mini-Tabellen für heute/morgen/übermorgen. → Klärung mit User.
2. **`MetricPreset`-Type-Schnitt im Frontend.** Backend hat das Schema umgestellt (kein `friendly_ids` mehr; Compat-Layer im POST). Frontend-Type muss synchron — ggf. existieren noch lesende Stellen, die `MetricPreset.metrics: string[]` erwarten.
3. **Default-Wert beim Anlegen einer neuen Metrik.** Wenn der User eine vorher deaktivierte Metrik aktiviert, sollen alle drei Horizonte default `true` sein (= heutiges Verhalten).
4. **Mobile-Touch-Target.** Brand-Tokens fordern 44×44px Touch-Target. Drei kleine Chips à 9px-Font (laut Issue-CSS-Skizze) werden auf Mobile schwer treffbar — Mindest-Größe sicherstellen oder Layout anpassen.
5. **Speicher-Schema in `display_config.metrics[]`.** Aktuell schickt das Frontend ein altes Format (ohne `horizons`). Wenn `horizons` fehlt, sieht der Renderer Default `{true,true,true}` — also keine Regression für ungeänderte Trips. Save mit horizons funktioniert ab sofort.
6. **Tests:** Sub-Issue erwartet vermutlich UI-Tests via Playwright (E2E) — die `tests/`-Suite ist Python-zentriert, Frontend-Tests laufen über `frontend/e2e/`. Wir brauchen vermutlich `frontend/e2e/issue-343-horizon-chips.spec.ts`. Außerdem Unit-Tests für die HorizonChip-Komponente.

## Geklärt via Soll-Mockups (2026-05-23)

Drei Mockups in `claude-code-handoff/screenshots/`:
- `soll-issue343-table-preview.png`
- `soll-issue343-mobile-metric-row.png`
- `soll-issue343-save-preset-dialog.png`

Plus weiterhin gültig: `soll-flow1D-wizard-step3-wetter.png` (Metrik-Zeile + Chip-Optik).

### TablePreview — Drei Mini-Tabellen nebeneinander

- Sektion-Header (Eyebrow + H2): `SCHRITT 3 VON 4 · NEUE TOUR · VORSCHAU` / „Vorschau — so kommt das Briefing pro Tag an"
- Sub-Text: „Pro Tag erscheinen nur die Metriken, die du oben für diesen Horizont aktiviert hast. Sample-Stunden 09/12/15/18 für die Vorschau — im echten Briefing entscheidet das pro-Etappe-Profil."
- Strip mit Aktivitätsprofil + Zähler (`5 METRIKEN · 3 HORIZONT-KONFIGS`)
- **Drei Tabellen nebeneinander**: `HEUTE — N METRIKEN`, `MORGEN — N METRIKEN`, `ÜBERMORGEN — N METRIKEN` (Eyebrow + Zähler)
- Spalten pro Tabelle variieren je nach aktivierten Horizonten
- Sample-Zeilen: vier Slots `09:00 / 12:00 / 15:00 / 18:00`, identisch pro Tag
- **Responsive-Hinweis im Mockup:** < 1100 px Editor-Breite → Tabellen stapeln vertikal (separates Mockup folgt aus Design); in dieser Iteration nur Desktop-Layout (nebeneinander) implementieren, Mobile-Stapeln per CSS-Grid auto-fit
- **Empty-State**: wenn ein Tag 0 Metriken hat, zeigt die Tabelle ein dezentes „Keine Metriken für diesen Horizont" (im Mockup ungezeigt, Design-Entscheidung Wording während Implementierung)

### Mobile-Metrik-Zeile — Chips unter Namen, eingerückt

- Im Mockup-Phone (393×852, iOS-Style): jeder Metrik-Eintrag ist eine **zweiwellige Zeile**:
  - Zeile 1: Checkbox + Metrik-Name (+ optional Untertitel wie `AM WICHTIGSTEN`) … `Roh + Indikator` + `…`-Menü rechts
  - Zeile 2: HorizonChips `[HEUTE] [MORGEN] [ÜBERMORGEN]`, **eingerückt auf Höhe des Metrik-Namens** (Indent = Checkbox-Breite + Gap)
- Chip-Höhe 32 px, mit Padding entsteht das geforderte 44 px Touch-Target
- Roh/Indikator und `…` bleiben in Zeile 1 (kein Umbruch, kein Bottom-Sheet)
- Breakpoint: < 600 px

### SavePresetDialog — „WIRD GESPEICHERT"-Box mit ZEITHORIZONTE-Zusammenfassung

- Dialog-Header: Eyebrow `EIGENES PRESET` + H2 „Auswahl als Preset speichern" + `×`-Close
- `NAME` (required), `BESCHREIBUNG · OPTIONAL`
- **Neue Box „WIRD GESPEICHERT"** zwischen Beschreibung und Default-Checkbox:
  - Statuszeile: `8 Metriken aktiv · 3 Rohwert · 5 Indikator` (heutiger Stand, unverändert)
  - Trenn-Hairline
  - Eyebrow `ZEITHORIZONTE`
  - Zusammenfassungs-Zeile: `5 alle drei Tage · 2 nur heute + morgen · 1 nur heute` (dynamisch)
  - Metrik-Liste in zwei Spalten mit `●●●` / `●●○` / `●○○`-Indikatoren pro Metrik (Filled = Tag aktiv, Outline = Tag inaktiv). Reihenfolge: heute / morgen / übermorgen
- Footer: `Abbrechen` / `Preset speichern` (Primary)

### Wording-Heuristik für Zusammenfassungs-Zeile

Gruppiere Metriken nach Horizont-Pattern und kondensiere:
- `{n} alle drei Tage` (heute=true, morgen=true, day_after=true)
- `{n} nur heute + morgen` (heute=true, morgen=true, day_after=false)
- `{n} nur heute` (heute=true, morgen=false, day_after=false)
- `{n} nur morgen + übermorgen` (heute=false, morgen=true, day_after=true) — falls vorhanden
- `{n} sonstige Kombinationen` (Sammelpunkt für alles andere)
- Bei n=0 wird der Eintrag weggelassen

