---
entity_id: segment_aggregation_timewindow
type: bugfix
created: 2026-02-14
status: draft
severity: HIGH
tags: [aggregation, formatter, highlights, night-block]
---

# Bugfix: Segment-Aggregation auf falsches Zeitfenster + Nacht-Luecken

## Approval

- [ ] Approved for implementation

## Symptom

Die E-Mail-Zusammenfassung zeigt dramatisch andere Werte als die Tabellen:

```
Tabelle Segment 2 (10:00-12:00):  max Boee 76 km/h, Regen 0.0 mm
Zusammenfassung:                  "Boeen bis 126 km/h", "Regen gesamt: 10.9 mm"
```

Die 126 km/h Boee war um 03:00 nachts, der Regen fiel ueber den ganzen Tag verteilt.

Zusaetzlich: Nacht-Tabelle (2h-Raster) ueberspringt ungerade Stunden komplett.
Extremwerte um 21:00, 23:00, 01:00 etc. sind unsichtbar.

## Root Cause

### Problem 1: Aggregation ueber vollen Tag

```
OpenMeteo API (hourly)
  → liefert 24h Daten (00:00-23:00) fuer jeden Tag
  → Segment-Zeitfenster (z.B. 10:00-12:00) wird ignoriert

segment_weather.py:126-130
  → fetch_forecast(start=10:00, end=12:00)
  → OpenMeteo nutzt nur das DATUM, liefert ganzen Tag

segment_weather.py:140
  → compute_basis_metrics(timeseries)  ← ALLE 24 Stunden
  → gust_max_kmh = max(alle 24 Werte) = 126 km/h (von 03:00!)

trip_report.py:98-108  _extract_hourly_rows()
  → filtert korrekt auf start_h..end_h → zeigt nur 3 Stunden
  → max Gust sichtbar = 76 km/h
```

### Problem 2: Nacht-Tabelle ohne Aggregation

```
trip_report.py:126
  → if h % interval == 0:  ← nimmt nur gerade Stunden
  → Stunden 21, 23, 01, 03, 05 werden WEGGEWORFEN
  → Keine Aggregation der Zwischenstunden
```

## Design

### Loesung Problem 1: Zwei Aggregations-Ebenen

Die Ganztags-Daten sind **wertvoll** (naechtliche Extremwerte sind fuer Wanderer
relevant). Aber die Zusammenfassung muss **unterscheiden** zwischen:

**a) Segment-Aggregation** (nur Segment-Zeitfenster):
- Fuer die Segment-spezifischen Werte in `SegmentWeatherSummary`
- Wird von Change-Detection und Risk-Bewertung verwendet
- Fix in `segment_weather.py`: Timeseries filtern VOR Aggregation

**b) Highlights/Zusammenfassung** (ganzer Tag, MIT Uhrzeit):
- Extremwerte ueber den gesamten Tag, aber mit Zeitangabe
- Format: "Boeen bis 126 km/h (03:00, nachts)" oder
          "Starkregen 8.2 mm/h (04:00, nachts)"
- Naechtliche Werte als Kontext, nicht als Segment-Eigenschaft

#### Umsetzung

**segment_weather.py** — Timeseries filtern vor Aggregation:

```python
# Nach fetch_forecast(), vor compute_basis_metrics():
filtered_data = [
    dp for dp in timeseries.data
    if segment.start_time <= dp.ts <= segment.end_time
]
filtered_ts = NormalizedTimeseries(
    meta=timeseries.meta,
    data=filtered_data,
)
basis_summary = metrics_service.compute_basis_metrics(filtered_ts)
```

`SegmentWeatherData.timeseries` behaelt das **ungefilterte** Original
(wird von Formatter fuer Tabellen-Anzeige und Thunder-Forecast benoetigt).

**trip_report.py** `_compute_highlights()` — Ganztags-Extremwerte MIT Uhrzeit:

```python
# Statt seg_data.aggregated.gust_max_kmh:
# Direkt aus timeseries.data den Max suchen, MIT Timestamp

for seg_data in segments:
    all_gusts = [
        (dp.gust_kmh, dp.ts) for dp in seg_data.timeseries.data
        if dp.gust_kmh is not None
    ]
    if all_gusts:
        max_gust_val, max_gust_ts = max(all_gusts, key=lambda x: x[0])
        in_segment = seg_data.segment.start_time <= max_gust_ts <= seg_data.segment.end_time
        time_label = max_gust_ts.strftime('%H:%M')
        if not in_segment:
            time_label += ", nachts"
        ...
```

Beispiel-Output:
```
Zusammenfassung:
  💨 Böen bis 126 km/h (03:00, nachts)
  💨 Böen bis 76 km/h (Segment 2, 10:00)   ← nur wenn > Schwelle
  🌧 Regen gesamt: 10.9 mm (davon 10.7 mm nachts)
```

### Loesung Problem 2: Nacht-Tabelle aggregiert Zwischenstunden

Statt ungerade Stunden wegzuwerfen, Zweistunden-Bloecke aggregieren:

```python
def _extract_night_rows(self, night_weather, arrival_hour, interval, dc):
    """Aggregate night data into 2h blocks."""
    # Gruppiere: [20:00+21:00], [22:00+23:00], [00:00+01:00], ...
    blocks = {}
    for dp in night_weather.data:
        block_hour = dp.ts.hour - (dp.ts.hour % interval)
        blocks.setdefault(block_hour, []).append(dp)

    for block_hour, dps in sorted(blocks.items()):
        # Aggregiere: max(gust), max(wind), min(temp), sum(precip), ...
        row = self._aggregate_block(dps, dc)
        rows.append(row)
```

Aggregationsregeln pro Metrik im 2h-Block:

| Metrik | Aggregation |
|--------|-------------|
| Temperatur | min |
| Gefuehlte Temp | min |
| Wind | max |
| Boeen | max |
| Niederschlag | sum |
| Gewitter | max (Enum) |
| Bewoelkung | avg |
| Sichtweite | min |

## Affected Files

| Datei | Aenderung | LOC |
|-------|-----------|-----|
| `src/services/segment_weather.py` | Timeseries filtern vor Aggregation | ~8 |
| `src/formatters/trip_report.py` | Highlights mit Uhrzeit + Nacht-Aggregation | ~40 |
| `src/app/models.py` | Optional: NormalizedTimeseries.filter_range() Methode | ~10 |
| **Gesamt** | | **~58 LOC** |

## Test Plan

### Automatisiert

- [ ] Segment-Aggregation: gust_max nur aus Segment-Stunden, nicht 24h
- [ ] Highlights: Boeen-Uhrzeit wird angezeigt
- [ ] Highlights: Naechtliche Werte mit "nachts" markiert
- [ ] Nacht-Tabelle: Zwischenstunden in 2h-Block aggregiert
- [ ] Nacht-Tabelle: Starker Regen um 23:00 taucht im 22:00-Block auf
- [ ] Change-Detection: Schwellwerte gegen Segment-Fenster, nicht 24h
- [ ] Risk-Bewertung: basiert auf Segment-Fenster

### Manuell

- [ ] Morning Report: Zusammenfassung passt zu Tabellenwerten
- [ ] Evening Report: Nacht-Tabelle zeigt aggregierte 2h-Werte
- [ ] Alert-E-Mail: Aenderungen basieren auf Segment-Werten

## Acceptance Criteria

- [ ] SegmentWeatherSummary aggregiert NUR ueber Segment-Zeitfenster
- [ ] Highlights zeigen Extremwerte mit Uhrzeit
- [ ] Naechtliche Extremwerte als "nachts" markiert
- [ ] Nacht-Tabelle aggregiert 2h-Bloecke (kein Datenverlust)
- [ ] Change-Detection und Risk nutzen gefilterte Werte
- [ ] Bestehende Tests bleiben gruen
