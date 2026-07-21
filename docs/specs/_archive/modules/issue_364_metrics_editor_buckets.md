---
entity_id: issue_364_metrics_editor_buckets
type: module
created: 2026-05-25
updated: 2026-05-25
status: draft
version: "1.0"
tags: [output, frontend, editor, epic-331, issue-361]
---

# Wetter-Metriken-Editor: Spalten/Detail/Aus + Reihenfolge + Roh/Skala

## Approval

- [x] Approved (User, 2026-05-25)

## Purpose

Schritt B von #361 (Epic #331). Der bestehende Kategorie-Checkbox-Editor
(`WeatherMetricsTab`) wird zum **Bucket-Editor** umgebaut: pro Metrik wählt der User
**eigene Spalte / Detail-Wert / aus**, legt die **Reihenfolge** fest und schaltet
**Roh/Skala** um. Gespeichert wird über den bestehenden Trip-Save. Rein **Frontend**:
`bucket`/`order` reisen als freie Felder in `display_config` durch die Go-API
(`Trip.DisplayConfig` ist `map[string]interface{}`) und werden vom Python-Loader (#360)
gelesen — kein Backend-Umbau.

Die 4-Kanal-Live-Vorschau ist **Schritt C (#365)**; B behält bis dahin eine schlanke
Spalten-Vorschau.

## Source

- **Design (verbindlich):** `docs/design/epic_331_output_layout/screen-metrics-editor.jsx`; Design-System `docs/design-system/` (Tokens/Components/Copy)
- **Geändert:** `frontend/src/lib/types.ts` — `WeatherConfigMetric` additiv +`bucket?: 'primary'|'secondary'` +`order?: number`
- **Geändert:** `frontend/src/lib/components/trip-detail/metricsEditor.ts` — Bucket-Modell, `autoAssign`, `move`, `reorder`, `channelOverflow`-Helfer
- **Umgebaut:** `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` — Bucket-Layout statt Kategorie-Checkboxen
- **Neu:** `BucketSection.svelte`, `ActiveMetricRow.svelte`, `ChannelLimitMarkers.svelte`, `BucketSectionOff.svelte`, `AboutOutputLayout.svelte` (unter `trip-detail/`)
- **Wiederverwendet/angepasst:** `PresetRow.svelte`, `SavePresetDialog.svelte`, `TablePreview.svelte` (zeigt vorerst nur die `primary`-Spalten); `MetricGroup`/`MetricCheckbox` wandern in die „Nicht im Briefing"-Ansicht oder werden abgelöst.

> Schicht: **Frontend / SvelteKit** (`frontend/src/`). KEIN Go/Python-Backend-Change. Save-Pfad `PUT /api/trips/{id}/weather-config` (Go `PutTripWeatherConfigHandler` ersetzt die `display_config`-Map durch den geposteten Body → Client-Merge wie heute).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `Trip.DisplayConfig` (Go, `map[string]interface{}`) | model | reicht bucket/order verbatim durch |
| `src/app/loader.py::_parse_display_config` (#360) | backend | liest bucket/order, Legacy-Migration |
| `INDICATOR_MAP` (metricsEditor.ts) | const | Roh/Skala-Fähigkeit pro Metrik (vorhanden) |
| `/api/metrics`, `/api/templates`, `/api/metric-presets` | API | Katalog/Presets (vorhanden) |
| `#365` (C) | follow-up | 4-Kanal-Live-Vorschau ersetzt die schlanke Vorschau |
| `#345` | separate | Konsolidierung EditWeatherSection/WeatherConfigDialog (4 Aufrufstellen — eigener Scope, NICHT in B) |

## Implementation Details

### Bucket-Modell (Frontend)

State ersetzt `enabledMap` durch geordnete Bucket-Listen (zusätzlich bleiben `friendlyMap` = Roh/Skala und `horizonsMap`):

```ts
// metricsEditor.ts
export interface Buckets { primary: string[]; secondary: string[]; off: string[]; }

// Konsistent mit Backend #360 auto_distribute: Top-5 nach Priorität → primary (order 0..4),
// Rest der aktiven → secondary. Inaktive → off. Signal-safe by default (Signal-Budget = 5
// wählbare Spalten + feste Uhrzeit = 6).
export function autoAssign(activeIds: string[], catalog: MetricCatalog): Buckets

export function move(b: Buckets, id: string, from: keyof Buckets, to: keyof Buckets): Buckets
export function reorder(b: Buckets, bucket: keyof Buckets, id: string, dir: -1 | 1): Buckets
```

`enabled` ↔ Bucket: `off` = `enabled:false`; `primary`/`secondary` = `enabled:true`. „Uhrzeit" ist KEIN Katalog-Metrik (immer implizit Spalte 0) und taucht im Editor nicht als Zeile auf.

### Kanal-Budgets (Anzeige, NICHT hartes Limit)

```ts
// wählbare Metrik-Spalten je Kanal (Uhrzeit nicht mitgezählt — deckt sich mit #360):
export const CHANNEL_COL_BUDGET = { email: Infinity, telegram: 7, signal: 5, sms: 0 };
```
`ChannelLimitMarkers` zeigt je Kanal `primary.length / budget`; bei Überschreitung Warn-Färbung (Brand-`--g-warn`). Der Renderer demotet überzählige Spalten kanalspezifisch (bereits in #360) — der Editor warnt nur.

### Save

`handleSave` postet je Metrik `{metric_id, enabled, use_friendly_format, horizons, bucket, order}` (order = Position im jeweiligen Bucket; off-Metriken `enabled:false`, bucket weggelassen oder "secondary"). Body = `{...trip.display_config, metrics, preset_name}` an `PUT /api/trips/{id}/weather-config`.

### Layout (design-getreu, `screen-metrics-editor.jsx`)

Breadcrumb + dirty-Pill + Verwerfen/Speichern · H1 + Intro + „Wie funktioniert das genau?"→`AboutOutputLayout` · 2-Spalten (Preset-Liste | Editor): `BucketSection` „Spalten" (mit `ChannelLimitMarkers` + Signal-Trenner ab der 6. Spalte) → `BucketSection` „Detail-Werte" → schlanke `TablePreview` (nur primary, Platzhalter bis #365) → `BucketSectionOff` „Nicht im Briefing" (nach Kategorie, +Spalte/+Detail). UI-Sprache: „Spalte / Detail / Aus / Reihenfolge / Roh / Skala".

### Preset-Wechsel

Wechsel eines Presets → `autoAssign(preset.metrics)` überschreibt die Buckets (Confirm-Dialog wenn dirty). `SavePresetDialog`-Zusammenfassung zeigt Spalten-/Detail-/Skala-Zähler (Anzeige; Preset persistiert weiterhin enabled/friendly, Buckets werden bei Anwendung neu via autoAssign abgeleitet — kein Preset-Schema-Change).

## Expected Behavior

- **Input:** `trip` (mit/ohne bucket/order in `display_config.metrics`), Katalog/Presets
- **Output:** Editierte Buckets+Reihenfolge+Mode; gespeicherte `display_config.metrics` mit bucket/order
- **Side effects:** PUT auf den Trip; keine Backend-Logik-Änderung

## Acceptance Criteria

- **AC-1:** Given ein Trip ohne `bucket`/`order` auf den Metriken / When `WeatherMetricsTab` lädt / Then werden aktive Metriken auto-verteilt (die 5 wichtigsten → „Spalten" in Prioritäts-Reihenfolge, Rest → „Detail"), inaktive erscheinen unter „Nicht im Briefing" — konsistent mit dem Backend-`auto_distribute` (#360).
  - Test: (populated after /tdd-red)

- **AC-2:** Given eine Metrik im Bucket „Spalten" / When der User „→ Detail" klickt / Then liegt sie danach in „Detail-Werte", ist aus „Spalten" entfernt, und die dirty-Pill „Ungespeicherte Änderungen" erscheint.
  - Test: (populated after /tdd-red)

- **AC-3:** Given mehrere Metriken in „Spalten" / When der User ↑/↓ auf einer Zeile betätigt / Then ändert sich die Reihenfolge entsprechend und wird beim Speichern als `order` (lückenlos 0..n-1) übernommen.
  - Test: (populated after /tdd-red)

- **AC-4:** Given eine Metrik mit `INDICATOR_MAP`-Eintrag / When der User „Roh/Skala" umschaltet / Then kippt `use_friendly_format`; Metriken ohne Indikator zeigen statt des Toggles „nur Rohwert".
  - Test: (populated after /tdd-red)

- **AC-5:** Given mehr als 5 Metriken im Bucket „Spalten" / When der Editor rendert / Then markiert `ChannelLimitMarkers` Signal als überschritten (z.B. „Signal 6/5", Warn-Färbung), Telegram (Budget 7) bleibt unmarkiert.
  - Test: (populated after /tdd-red)

- **AC-6:** Given eine Metrik unter „Nicht im Briefing" / When der User „+ Spalte" bzw. „+ Detail" klickt / Then wandert sie in den jeweiligen Bucket mit `enabled:true` und verschwindet aus „Nicht im Briefing".
  - Test: (populated after /tdd-red)

- **AC-7:** Given Bucket-/Reihenfolge-Änderungen / When der User „Speichern" klickt / Then enthält der `PUT /api/trips/{id}/weather-config`-Body je Metrik `bucket`+`order`+`enabled`+`use_friendly_format`+`horizons`, und nach Reload zeigt der Editor dieselbe Aufteilung (Round-Trip ohne Verlust).
  - Test: (populated after /tdd-red)

- **AC-8:** Given ein Preset wird gewählt / When es angewandt wird / Then werden die Buckets via `autoAssign` aus den Preset-Metriken neu gesetzt (überschreibt die aktuelle Auswahl; Confirm-Dialog wenn dirty).
  - Test: (populated after /tdd-red)

## Known Limitations

- Keine 4-Kanal-Live-Vorschau in B (Schritt C/#365) — B zeigt nur eine schlanke Spalten-Vorschau.
- Presets persistieren keine Buckets (Re-Anwendung via `autoAssign`) — Layout-Capture pro Preset wäre ein späterer additiver Schritt (Go `DisplayMetric` + Python-Preset-Modell).
- Mobile-Adaption in Schritt C.
- 2 offene LOW-Test-Nits aus #363 (Telegram-Proxy `user_id`-Assert; signal≠telegram-Assert) hier NICHT — gehören zu #365.

## Changelog

- 2026-05-25: Initial spec created (Schritt B von #361 / Epic #331, Issue #364)
