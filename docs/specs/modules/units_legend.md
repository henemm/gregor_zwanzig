---
entity_id: units_legend
type: module
created: 2026-02-17
updated: 2026-02-17
status: draft
version: "1.0"
tags: [formatter, email, units]
---

# Units Legend (Einheiten-Legende im E-Mail-Footer)

## Approval

- [ ] Approved

## Purpose

Kompakte Einheiten-Legende im E-Mail-Footer, damit der Leser weiss was die Spalten bedeuten. Gleichzeitig wird die Visibility-Darstellung vereinfacht: statt `15k` steht `15`, die Einheit "km" steht in der Legende.

## Source

- **File:** `src/formatters/trip_report.py`
- **Identifier:** `TripReportFormatter._render_html`, `_render_plain`, `_fmt_val`
- **File:** `src/app/metric_catalog.py`
- **Identifier:** `MetricDefinition` (neues Feld `display_unit`)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `metric_catalog.py` | module | Metrik-Definitionen mit `unit` und neuem `display_unit` |
| `trip_report.py` | module | E-Mail-Formatter (HTML + Plaintext) |
| `models.py` | DTO | `UnifiedWeatherDisplayConfig` fuer enabled-Metriken |

## Implementation Details

### 1. Neues Feld `display_unit` im MetricCatalog

`MetricDefinition` erhaelt ein optionales Feld:

```python
display_unit: str = ""  # Einheit fuer Legende, falls abweichend von `unit`
```

Nur bei Visibility relevant: `unit="m"` (intern), `display_unit="km"` (Legende).
Alle anderen Metriken: `display_unit` bleibt leer → Legende nutzt `unit`.

### 2. Visibility-Format aendern (`_fmt_val`)

**Vorher:**
- `>= 10000m` → `"15k"` (mit "k" Suffix)
- `>= 1000m` → `"5.0k"`
- `< 1000m` → `"800"` (Meter, nackt)

**Nachher:**
- `>= 10000m` → `"15"` (km, ohne Suffix)
- `>= 1000m` → `"5.0"` (km, ohne Suffix)
- `< 1000m` → `"0.8"` (km, 1 Dezimalstelle)

Die Einheit steht jetzt ausschliesslich in der Footer-Legende.

### 3. Legende im Footer

Neue Hilfsfunktion in `trip_report.py`:

```python
def _build_units_legend(self, rows: list[dict], dc: UnifiedWeatherDisplayConfig) -> str:
```

Logik:
1. Ermittle sichtbare Spalten via `_visible_cols(rows)` (col_key, col_label)
2. Fuer jede Spalte: lookup MetricDefinition via `get_metric_by_col_key(col_key)`
3. Einheit: `display_unit` falls gesetzt, sonst `unit`
4. Ueberspringe Metriken ohne Einheit (thunder, precip_type, uv_index)
5. Gruppiere gleiche Einheiten: `Temp, Feels °C · Wind, Gust km/h · Rain mm · Visib km`

Format-String (Plaintext):
```
Einheiten: Temp, Feels °C · Wind, Gust km/h · Rain mm · Visib km
```

Format-String (HTML):
```html
<div style="color:#888;font-size:10px;margin-top:4px">
  Temp, Feels °C · Wind, Gust km/h · Rain mm · Visib km
</div>
```

### 4. Footer-Integration

**HTML** (nach Generated-Zeile in `.footer`):
```html
<div class="footer">
  Generated: ... | Data: ...
  <br>{units_legend_html}
</div>
```

**Plaintext** (vor Generated-Zeile):
```
Einheiten: Temp, Feels °C · Wind, Gust km/h · Rain mm · Visib km
------------------------------------------------------------
Generated: ...
```

### 5. Gruppierung der Einheiten

Metriken mit gleicher Einheit werden zusammengefasst:

| Einheit | Metriken (col_label) |
|---------|---------------------|
| °C | Temp, Feels, Cond° |
| km/h | Wind, Gust |
| mm | Rain |
| % | Humid, Rain%, Cloud, CldLow, CldMid, CldHi |
| km | Visib |
| hPa | hPa |
| m | SnowL, 0°Line |
| cm | SnowH, NewSn |
| J/kg | Thndr% |

Reihenfolge: Katalog-Reihenfolge der ersten Metrik pro Gruppe.

## Expected Behavior

- **Input:** Segment-Tabellen-Rows + DisplayConfig
- **Output:** Einheiten-Legende als String (HTML oder Plain)
- **Sichtbarkeit:** Nur Metriken die tatsaechlich in der Tabelle erscheinen
- **Side effects:** Visibility-Werte in der Tabelle aendern sich von `15k` auf `15`

## Edge Cases

- Keine sichtbaren Metriken mit Einheit → keine Legende anzeigen
- Friendly-Format aktiv (z.B. Cloud als Emoji) → trotzdem in Legende (User koennte umschalten)
- Night-Block und Segment-Tabellen koennen unterschiedliche Spalten haben → Legende basiert auf Union aller sichtbaren Spalten

## Known Limitations

- Legende zeigt col_label (englisch: "Temp", "Wind") — konsistent mit Tabellen-Header
- Friendly-Format-Metriken (good/fog, Emoji) haben keine numerische Einheit — werden in Legende mit ihrer Basis-Einheit gezeigt

## Test Plan

1. **test_legend_contains_active_units** — Legende enthaelt nur Einheiten der aktivierten Metriken
2. **test_legend_groups_same_units** — Metriken mit gleicher Einheit sind gruppiert
3. **test_visibility_format_km** — Visibility-Werte ohne "k" Suffix, in km
4. **test_visibility_sub_1km** — Werte unter 1 km als Dezimal-km (0.8)
5. **test_legend_in_html_footer** — HTML-Footer enthaelt Legende
6. **test_legend_in_plain_footer** — Plaintext-Footer enthaelt Legende
7. **test_no_legend_when_no_units** — Keine Legende wenn nur unitless Metriken

## Changelog

- 2026-02-17: Initial spec created
