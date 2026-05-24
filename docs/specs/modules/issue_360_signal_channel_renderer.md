---
entity_id: issue_360_signal_channel_renderer
type: module
created: 2026-05-24
updated: 2026-05-24
status: draft
version: "1.0"
tags: [output, signal, telegram, channel-renderer, epic-331]
---

# Kanal-bewusster Renderer für Signal/Telegram + Spalten-Datenmodell

## Approval

- [x] Approved (User, 2026-05-24)

## Purpose

Signal und Telegram bekommen heute `report.email_plain` — den Plaintext der E-Mail,
gebaut für unbegrenzte Tabellenbreite. In der schmalen Signal-Blase (~6 Spalten Platz)
bricht das hässlich um. Diese Spec führt einen **kanal-bewussten Renderer** ein, der pro
Kanal eine Spalten-Obergrenze anwendet: was nicht in die Tabelle passt, wandert in eine
kompakte Detail-Zeile. Damit erhalten Signal/Telegram einen eigenen, lesbaren
Monospace-Report statt des E-Mail-Texts.

Teil 1 von Epic #331 (Backend). Frontend-Editor + Multi-Kanal-Vorschau folgen in #361.

## Source

- **Neu:** `src/output/renderers/channel_layout.py` — `CHANNEL_LIMITS`, `render_for_channel()`, `auto_distribute()` (pure, Python-Backend)
- **Neu:** `src/output/renderers/narrow.py` — `render_narrow()` für Signal/Telegram (pure)
- **Geändert:** `src/app/models.py` — `MetricConfig` +`bucket`/`order`; `TripReport` +`signal_text`/`telegram_text`
- **Geändert:** `src/app/loader.py` — Persistenz der neuen Felder + Legacy-Migration
- **Geändert:** `src/formatters/trip_report.py` — `format_email()` befüllt zusätzlich `signal_text`/`telegram_text`
- **Geändert:** `src/services/trip_report_scheduler.py:444/457`, `src/services/trip_alert.py` — Versand nutzt `signal_text`/`telegram_text`
- **Geändert (optional, additiv):** `src/output/renderers/email/plain.py` — `_render_text_table()` akzeptiert explizite Spaltenliste

> Schicht: reines **Python-Backend** (`src/`). Keine Go-/Frontend-Änderung in diesem Issue.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `app.metric_catalog` | module | Metrik-IDs, `compact_label`, `col_key`, `friendly_label` |
| `UnifiedWeatherDisplayConfig` / `MetricConfig` | model | Spalten-Auswahl + neue Felder |
| `src/output/renderers/email/helpers.py` | module | `fmt_val`, `visible_cols` (Wert-Formatierung wiederverwenden) |
| `outputs.signal.SignalOutput` / `outputs.telegram.TelegramOutput` | output | Versand des fertigen Texts |

## Implementation Details

### 1. Datenmodell-Erweiterung (additiv, backward-compatible)

`MetricConfig` bekommt zwei neue Felder. **`mode` aus #331 wird NICHT eingeführt** — das
existiert bereits als `use_friendly_format`. **„aus" wird NICHT als drittes Bucket
eingeführt** — das ist bereits `enabled=False`.

```python
@dataclass
class MetricConfig:
    ...
    bucket: str = "primary"   # "primary" (eigene Spalte) | "secondary" (Detail-Zeile)
    order: int = 0            # Sortier-Reihenfolge innerhalb des Buckets
```

Semantik-Mapping zu #331:
- #331 `bucket="off"`  ⇔  `enabled=False` (unverändert genutzt)
- #331 `mode`          ⇔  `use_friendly_format` (vorhanden)
- Zeit-Spalte: implizit immer Spalte 0 (kein `hour`-Metrik nötig, s. `_render_text_table`)

### 2. Kanal-Constraints

```python
# src/output/renderers/channel_layout.py
CHANNEL_LIMITS = {
    "email":    {"max_table_cols": None, "max_chars": None},   # unbegrenzt
    "telegram": {"max_table_cols": 8,    "max_chars": 4096},
    "signal":   {"max_table_cols": 6,    "max_chars": 1800},
    "sms":      {"max_table_cols": 0,    "max_chars": 140},
}
```

`max_table_cols` zählt die **Gesamtspalten inkl. Zeit-Spalte** (Signal 6 = Zeit + 5 Metriken),
konsistent mit der #331-Auto-Verteilung.

### 3. Layout-Berechnung (pure function)

```python
@dataclass(frozen=True)
class ChannelLayout:
    table_columns: list[str]   # metric_ids in Spalten-Reihenfolge (ohne Zeit)
    detail_metrics: list[str]  # metric_ids für die Detail-Zeile
    demoted_count: int         # aus primary in Detail verschoben (Logging/Badge)

def render_for_channel(channel: str, dc, report_type: str) -> ChannelLayout:
    enabled = dc.get_metrics_for_report_type(report_type)   # respektiert per-Typ-Flags
    primary   = sorted([m for m in enabled if m.bucket == "primary"],   key=lambda m: m.order)
    secondary = sorted([m for m in enabled if m.bucket == "secondary"], key=lambda m: m.order)
    limit = CHANNEL_LIMITS[channel]["max_table_cols"]
    if limit is None:                       # Email
        table, overflow = primary, []
    elif limit == 0:                        # SMS
        table, overflow = [], primary
    else:                                   # Signal/Telegram: Slot 0 = Zeit
        metric_slots = limit - 1
        table, overflow = primary[:metric_slots], primary[metric_slots:]
    return ChannelLayout(
        table_columns=[m.metric_id for m in table],
        detail_metrics=[m.metric_id for m in (overflow + secondary)],
        demoted_count=len(overflow),
    )
```

### 4. Auto-Verteilung (Heuristik, Signal-safe)

Wird bei Legacy-Migration und (später, #361) bei Preset-Wechsel angewandt. Priorität als
Konstante in `channel_layout.py`, abgebildet auf **Katalog-IDs** (nicht die #331-JS-IDs):

```python
METRIC_PRIORITY = {
    "temperature": 95, "wind": 90, "gust": 88, "rain_probability": 85,
    "precipitation": 78, "wind_chill": 70, "cloud_total": 65, "thunder": 60,
    "fresh_snow": 55, "visibility": 55, "freezing_level": 50, "uv_index": 45,
    "wind_direction": 40, "snow_depth": 35, "precip_type": 35, "snowfall_limit": 35,
    "cloud_low": 30, "humidity": 25, "sunshine": 25, "dewpoint": 20,
    "pressure": 18, "cape": 15, "cloud_mid": 12, "cloud_high": 10, "confidence": 8,
}
```

`auto_distribute(enabled_ids)`: die 5 wichtigsten → `primary` (`order` 0..4), Rest →
`secondary` (`order` 0..n). 5 = Signal-Limit (6) minus Zeit-Spalte ⇒ Auto-Verteilung ist
Signal-safe.

### 5. Narrow-Renderer

`render_narrow(channel, segments, seg_tables, dc, report_type, ..., tz)` baut den kompakten
Signal/Telegram-Body: Header (Trip/Report/Datum), pro Segment eine schmale Monospace-Tabelle
mit `table_columns` (Zeit + gekappte Metrik-Spalten) und darunter — falls `detail_metrics`
nicht leer — eine `·`-getrennte Detail-Zeile. Wert-Formatierung über vorhandenes `fmt_val`.
Bei Überlänge auf `max_chars` kürzen (Log-Warnung, wie heute in `SignalOutput`).

### 6. Verkabelung

`TripReportFormatter.format_email()` berechnet `seg_tables` (wie heute) und befüllt
zusätzlich `report.signal_text = render_narrow("signal", ...)` und
`report.telegram_text = render_narrow("telegram", ...)`. Scheduler + Alert senden
`report.signal_text` bzw. `report.telegram_text` statt `report.email_plain`.

### 7. Migration (Schema-Rework-Pflicht)

Beim Laden eines Trips ohne `bucket`/`order` in der JSON (Legacy): `auto_distribute()` auf die
aktiven Metrik-IDs anwenden, Ergebnis in die `MetricConfig`-Liste schreiben, einmal
persistieren. Roundtrip-Test Pflicht (load alt → migrate → load neu → kein Daten-Diff).
Pre-Snapshot-Hook (`data_schema_backup.py`) greift bei Edit an `models.py`/`loader.py`.

## Expected Behavior

- **Input:** `SegmentWeatherData[]`, `UnifiedWeatherDisplayConfig`, `report_type`, `channel`
- **Output:** `ChannelLayout` (pure) bzw. fertiger Monospace-Body (`render_narrow`); `TripReport.signal_text`/`telegram_text` befüllt
- **Side effects:** Legacy-Trip wird einmalig migriert + persistiert; Versand an Signal/Telegram nutzt den neuen Text

## Acceptance Criteria

- **AC-1:** Given eine Tour mit ≤5 aktiven `primary`-Metriken / When `render_for_channel("signal", dc, "morning")` läuft / Then liegen alle Metriken in `table_columns` und `demoted_count == 0`.
  - Test: (populated after /tdd-red)

- **AC-2:** Given eine Tour mit 9 aktiven `primary`-Metriken / When `render_for_channel("signal", ...)` läuft / Then enthält `table_columns` genau 5 Einträge (Zeit + 5 = 6 Spalten), `detail_metrics` die übrigen 4 und `demoted_count == 4`.
  - Test: (populated after /tdd-red)

- **AC-3:** Given derselbe `dc` / When `render_for_channel("email", ...)` läuft / Then sind alle `primary`-Metriken in `table_columns` und `demoted_count == 0` (kein Limit).
  - Test: (populated after /tdd-red)

- **AC-4:** Given derselbe `dc` / When `render_for_channel("sms", ...)` läuft / Then ist `table_columns == []` und alle Werte liegen flach in `detail_metrics`.
  - Test: (populated after /tdd-red)

- **AC-5:** Given eine Tour mit 9 `primary`-Metriken / When `render_narrow("signal", ...)` läuft / Then ist jede Zeile des erzeugten Monospace-Bodys ≤26 Zeichen breit (Signal-Bubble-Constraint) und der Body endet mit einer Detail-Zeile.
  - Test: (populated after /tdd-red)

- **AC-6:** Given ein im Scheduler erzeugter `TripReport` mit `send_signal=True` / When der Report gebaut wird / Then ist `report.signal_text` gesetzt, ungleich `report.email_plain`, und der Versand nutzt `report.signal_text`.
  - Test: (populated after /tdd-red)

- **AC-7:** Given eine Legacy-Trip-JSON ohne `bucket`/`order` / When der Trip geladen und neu gespeichert wird / Then haben alle `MetricConfig` gültige `bucket`/`order`-Werte (via `auto_distribute`) und kein anderes Feld hat sich geändert (Roundtrip ohne Daten-Diff).
  - Test: (populated after /tdd-red)

- **AC-8:** Given eine Tour mit konfigurierter `order` / When ein Report für irgendeinen Kanal gerendert wird / Then erscheinen die Spalten in der durch `order` festgelegten Reihenfolge.
  - Test: (populated after /tdd-red)

## Known Limitations

- `mode`/Indikator-Darstellung nutzt das bestehende `use_friendly_format` — keine neue Indikator-Logik in diesem Issue.
- Kein Frontend, keine API-Änderung — die Bucket-Zuweisung erfolgt vorerst über `auto_distribute` (Default). Manuelle Konfiguration kommt mit #361.
- Telegram-Versand bleibt wie heute (reuse derselben Constraint-Mechanik, nur größeres Limit).

## Changelog

- 2026-05-24: Initial spec created (Teil 1 von Epic #331, Issue #360)
