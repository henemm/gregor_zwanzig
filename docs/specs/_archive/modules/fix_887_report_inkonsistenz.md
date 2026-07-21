# Spec: Fix #887 — Inkonsistenz zwischen Reports (SMS/Telegram)

**Issue:** https://github.com/henemm/gregor_zwanzig/issues/887  
**Workflow:** `fix-887-report-inkonsistenz`  
**ADR:** [no-adr] — lokale Bugfixes ohne Architekturentscheidung

## Problem

Konfigurierte Metriken erscheinen korrekt in der E-Mail, aber:
- **SMS**: `pop_hourly` (Regenwahrscheinlichkeit) nie befüllt → Token-Builder zeigt `PR–`
- **Telegram**: `_tg_segment_line()` hat hard-coded Format, ignoriert display_config komplett —
  nur Temp, Wind und grobe Regen-Kategorie; PR und alle anderen konfigurierten Metriken fehlen

## Root Cause

### SMS
`_segments_to_normalized_forecast()` (`sms_trip.py:92–104`) befüllt `rain_hourly`, `wind_hourly`,
`gust_hourly` — aber nie `pop_hourly`. Fix: synthetisches `HourlyValue(hour, pop_max_pct)`
pro Segment einbauen, wenn `agg.pop_max_pct is not None`.

### Telegram
`render_narrow()` (`narrow.py`) ruft für Telegram `_tg_segment_line()` auf und ignoriert
`layout.table_columns` + `layout.detail_metrics`, die `render_for_channel("telegram", dc, ...)`
bereits korrekt aus der display_config berechnet.

Fix: nach `_tg_segment_line()` eine config-gesteuerte Detail-Zeile einfügen, die alle
aktivierten Metriken zeigt, die nicht bereits in der Kopfzeile stehen
(d.h. alle außer `temperature`, `wind`, `wind_direction`).

### Nicht in diesem Issue
- Geosphere liefert kein `pop_pct` → `pop_max_pct` bleibt `None` für Geosphere-Nutzer.
  Separates Issue anlegen.

## Betroffene Dateien

| Datei | Änderung |
|---|---|
| `src/formatters/sms_trip.py` | `_segments_to_normalized_forecast()`: `pop_hourly` aus `agg.pop_max_pct` befüllen |
| `src/output/renderers/narrow.py` | Nach `_tg_segment_line()`: config-gesteuerte Detail-Zeile einfügen |

## Format-Design

Telegram-Segment nach dem Fix (Beispiel mit rain_probability + gust konfiguriert):

```
🌧️ 10–14h  15→18°C · Wind 20 NW · Regen
Rain% 60% · Gust 35 km/h
```

- Kopfzeile: unverändert (`_tg_segment_line()`)
- Detail-Zeile: metric_ids aus `layout.table_columns + layout.detail_metrics`,
  gefiltert um `temperature`, `wind`, `wind_direction`
- Labels in der Detail-Zeile: `MetricDefinition.col_label` (identisch mit E-Mail-Spaltenköpfen,
  z.B. `Rain%`, `Gust`, `Visib`, `0°Line`) — **nicht** `compact_label`
- Detail-Zeile entfällt komplett, wenn keine zusätzlichen Metriken konfiguriert

## Acceptance Criteria

**AC-1:** Given ein Segment mit `agg.pop_max_pct = 40` /
When SMS formatiert wird /
Then erscheint `PR40` im SMS-Text (nicht `PR–`).

**AC-2:** Given ein Segment mit `agg.pop_max_pct = 60` und `rain_probability` in der
display_config des Trips aktiviert /
When Telegram-Text generiert wird /
Then enthält die Ausgabe unterhalb der Segment-Kopfzeile `Rain% 60%` (col_label-Format,
identisch mit E-Mail-Spaltenkopf).

**AC-3:** Given eine display_config mit aktivierter `rain_probability` UND `gust` /
When Telegram-Text generiert wird /
Then enthält die Detail-Zeile beide Metriken mit col_label-Kürzeln (`Rain% …% · Gust … km/h`).

**AC-4:** Given ein Segment mit `agg.pop_max_pct = None` oder `= 0` /
When SMS oder Telegram formatiert wird /
Then kein Absturz; SMS zeigt `PR–` oder lässt PR weg; Telegram zeigt keine Detail-Zeile
(bzw. nur Metriken mit Wert).

**AC-5:** Given eine display_config ohne zusätzliche Metriken (nur Temp + Wind konfiguriert) /
When Telegram-Text generiert wird /
Then erscheint keine Detail-Zeile — Format identisch zu heute.

**AC-6:** Given ein Segment mit `agg.pop_max_pct = 0` aber `agg.precip_sum_mm = 3.0` /
When Telegram-Text generiert wird /
Then zeigt die Kopfzeile weiterhin den Regen-Kategorie-Text ("Regen") — AC-6 stellt
sicher dass die Kopfzeile sich nicht ändert wenn PR nicht konfiguriert ist.

## Manuelle Verifikation (Post-Deploy)

1. Trip mit Regenwahrscheinlichkeit > 20% und aktivierter `rain_probability`-Metrik
2. SMS-Vorschau: `PR{N}` (z.B. `PR40`) sichtbar
3. Telegram-Vorschau: Detail-Zeile unter Segment-Kopfzeile mit `PR …%`
