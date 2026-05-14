---
entity_id: issue_131_alert_email_klarheit
type: module
created: 2026-05-13
updated: 2026-05-13
status: draft
version: "1.0"
tags: [bug, email, alert, formatter, change-detection]
---

<!-- Issue #131 — Alert-E-Mail Wetteränderungen: Segment-Bezug, Format, Scope -->

# Issue 131 — Alert-E-Mail Wetteränderungen klarer formatieren

## Approval

- [ ] Approved

## Purpose

Die Alert-E-Mail bei Wetteränderungen ist unverständlich: Es fehlt der
Segment- und Zeit-Bezug, mehrere Zeilen derselben Metrik wirken zufällig,
unabonnierte Metriken werden gemeldet, und das Zahlenformat
(`12240.0m`, `63.0%`) ist nicht lesbar. Diese Spec macht die
Alert-Zeilen eindeutig zuordenbar (Segment + Zeit), beschränkt den
Alert-Scope auf die im Report-Profil aktivierten Metriken und führt
einheits-spezifische Zahlenformatierung mit DE-Locale ein.

## Source

- **File:** `src/app/models.py` (Z. 372-394) — `WeatherChange` Dataclass erhält Feld `segment_id`
- **File:** `src/services/weather_change_detection.py` (Z. 125-188, Z. 95-123) — `detect_changes()` übergibt `segment_id` an `WeatherChange`; `from_display_config()` ändert Auswahl-Logik
- **File:** `src/app/metric_catalog.py` (neue Funktion `format_metric_value()` unterhalb Z. 526) — einheits-spezifische Formatierung mit DE-Tausender-Trenner
- **File:** `src/output/renderers/email/helpers.py` (neue SSoT-Funktion `format_change_line()` am Ende) — eine Renderfunktion für HTML und Plain
- **File:** `src/output/renderers/email/html.py` (Z. 226-244) — nutzt `format_change_line()`
- **File:** `src/output/renderers/email/plain.py` (Z. 143-152) — nutzt `format_change_line()`
- **File:** `src/formatters/trip_report.py` (Z. 966-984 + Z. 1095-1104) — toter Renderer-Code entfernen

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `WeatherChange` Dataclass | intern | Datenmodell für eine erkannte Änderung — bekommt Pflichtfeld `segment_id` |
| `MetricDefinition` / `MetricCatalog` | intern | Quelle für Label, Aggregation, Unit und neuen Formatter |
| `UnifiedWeatherDisplayConfig.get_enabled_metrics()` | intern | Liefert die Metriken, die im Report-Profil aktiviert sind — wird neuer Scope für Alert-Detection |
| `SegmentWeatherData.segment.segment_id` + `start_time` / `end_time` | intern | Quelle für Segment-Label `Segment N (HH:MM–HH:MM)` in Change-Zeilen |
| `TripAlertService._detect_all_changes()` | intern | Bestehende Aggregation — bleibt strukturell, nutzt aber neue `segment_id`-Information |

## Implementation Details

### 1. `WeatherChange.segment_id` einführen

```python
# src/app/models.py
@dataclass
class WeatherChange:
    metric: str
    old_value: float
    new_value: float
    delta: float
    threshold: float
    severity: ChangeSeverity
    direction: str
    segment_id: str = ""  # NEU: 1, 2, "Ziel", … — gefüllt vom Detector
```

Default `""` für Rückwärtskompatibilität in bestehenden Tests; der
Detector setzt das Feld immer.

### 2. Detector liefert `segment_id`

```python
# src/services/weather_change_detection.py – innerhalb detect_changes()
change = WeatherChange(
    metric=metric,
    old_value=float(old_value),
    new_value=float(new_value),
    delta=float(delta),
    threshold=float(threshold),
    severity=severity,
    direction=direction,
    segment_id=str(new_data.segment.segment_id),  # NEU
)
```

### 3. Alert-Scope: sichtbare Metriken im Report-Profil

```python
# src/services/weather_change_detection.py
@classmethod
def from_display_config(cls, display_config):
    """Schwellwerte für alle ENABLED Metriken (nicht nur alert_enabled)."""
    from app.metric_catalog import get_metric
    thresholds: dict[str, float] = {}
    for mc in display_config.metrics:
        if not mc.enabled:          # ehemals: not mc.alert_enabled
            continue
        try:
            metric_def = get_metric(mc.metric_id)
        except KeyError:
            continue
        if metric_def.default_change_threshold is None:
            continue
        threshold = (
            mc.alert_threshold
            if mc.alert_threshold is not None
            else metric_def.default_change_threshold
        )
        for field in metric_def.summary_fields.values():
            thresholds[field] = threshold
    return cls(thresholds=thresholds)
```

`TripAlertService.check_and_send_alerts()` ruft `from_display_config()`
nun immer auf, wenn `trip.display_config` vorhanden ist — Bedingung
`get_alert_enabled_metrics()` entfällt. Fallback auf
`from_trip_config()` bleibt für Trips ohne `display_config`.

### 4. Einheits-Formatter im `MetricCatalog`

```python
# src/app/metric_catalog.py
def _format_de_thousand(value: float) -> str:
    """12240 → '12.240', 12240.7 → '12.241' (gerundet, integer-Display)."""
    return f"{int(round(value)):,}".replace(",", ".")


def format_metric_value(unit: str, value: float, *, signed: bool = False) -> str:
    """
    Einheits-spezifische DE-Formatierung mit Tausender-Trenner.

    - m, km, hPa            → integer, Tausender-Trenner DE (Punkt)
    - %                     → integer
    - km/h                  → integer
    - °C, mm                → 1 NK, Dezimaltrenner Komma
    - sonst                 → str(value)

    signed=True präfixt '+' bei positiven Werten (Delta-Darstellung).
    """
    abs_v = abs(value)
    if unit in ("m", "km", "hPa"):
        formatted = _format_de_thousand(abs_v)
    elif unit in ("%", "km/h"):
        formatted = f"{int(round(abs_v))}"
    elif unit in ("°C", "mm"):
        formatted = f"{abs_v:.1f}".replace(".", ",")
    else:
        formatted = str(value)

    sign = ""
    if signed:
        if value > 0:
            sign = "+"
        elif value < 0:
            sign = "−"  # U+2212, schöner als ASCII-Minus
    elif value < 0 and unit in ("m", "km", "hPa", "%", "km/h"):
        sign = "−"

    return f"{sign}{formatted} {unit}".strip()
```

### 5. Single-Source-of-Truth-Renderfunktion

```python
# src/output/renderers/email/helpers.py
def format_change_line(change, segment_label: str) -> str:
    """
    Eine Zeile für eine erkannte Wetteränderung.

    Beispiel-Output:
        'Segment 2 (14:00–16:00) — Sichtweite (min): 12.240 m → 38.440 m (+26.200 m)'
    """
    from app.metric_catalog import get_label_for_field, format_metric_value
    label_info = get_label_for_field(change.metric)
    if label_info:
        name, agg, unit = label_info
        old_fmt = format_metric_value(unit, change.old_value)
        new_fmt = format_metric_value(unit, change.new_value)
        delta_fmt = format_metric_value(unit, change.delta, signed=True)
        return f"{segment_label} — {name} ({agg}): {old_fmt} → {new_fmt} ({delta_fmt})"
    return (
        f"{segment_label} — {change.metric}: "
        f"{change.old_value:.1f} → {change.new_value:.1f} "
        f"(Δ {abs(change.delta):.1f})"
    )


def build_segment_label(change, segments) -> str:
    """
    Liefert 'Segment N (HH:MM–HH:MM)' oder '🏁 Ziel' aus segment_id +
    segments-Liste.

    Fallback ohne Match: 'Segment N'.
    """
    for s in segments:
        if str(s.segment.segment_id) == change.segment_id:
            start = s.segment.start_time.strftime("%H:%M")
            end = s.segment.end_time.strftime("%H:%M")
            if str(s.segment.segment_id) == "Ziel":
                return f"🏁 Ziel ({start})"
            return f"Segment {s.segment.segment_id} ({start}–{end})"
    return f"Segment {change.segment_id}" if change.segment_id else "Unbekannt"
```

### 6. Renderer-Konsolidierung

HTML:
```python
# src/output/renderers/email/html.py – Change-Block
ch_items = []
for c in changes:
    label = build_segment_label(c, segments)
    ch_items.append(f"<li>{format_change_line(c, label)}</li>")
changes_html = f"<div class=\"section\"><h3>⚠️ Wetteränderungen</h3><ul>{''.join(ch_items)}</ul></div>"
```

Plain:
```python
# src/output/renderers/email/plain.py – Change-Block
if changes:
    lines.append("━━ Wetteränderungen ━━")
    for c in changes:
        label = build_segment_label(c, segments)
        lines.append(f"  {format_change_line(c, label)}")
    lines.append("")
```

### 7. Toter Code

`src/formatters/trip_report.py` Z. 966-984 (HTML-Change-Block) und
Z. 1095-1104 (Plain-Change-Block) werden ersatzlos entfernt — die
Methode `format_email()` delegiert seit dem Renderer-Refactor auf
`output/renderers/email/*` und erreicht diesen Code nicht mehr.

## Expected Behavior

- **Input:** `WeatherChange`-Liste vom Detector + `segments: List[SegmentWeatherData]`
- **Output:** Pro Change eine Zeile mit Segment-Bezug, Zeitfenster und einheits-korrekt formatierten Zahlen — identisch in HTML- und Plain-Text-Mail.
- **Side effects:** Keine. Throttle (2h) und MINOR-Filter (Severity ≥ MODERATE) bleiben unverändert.

## Acceptance Criteria

- **AC-1:** Given ein Trip mit zwei Segmenten, beide reißen die
  Sichtweite-Schwelle / When `WeatherChangeDetectionService.detect_changes()`
  läuft / Then enthält jede zurückgegebene `WeatherChange` das Feld
  `segment_id` mit dem Wert des Segments aus `new_data.segment.segment_id`
  (z. B. `"1"` und `"2"`), das Feld ist niemals leer.

- **AC-2:** Given ein Trip mit `display_config`, bei dem `Sichtweite.enabled=True`
  und `Sichtweite.alert_enabled=False` / When der Alert-Detector mit
  `WeatherChangeDetectionService.from_display_config(display_config)` gebaut
  wird / Then steht `visibility_min` in `self._thresholds` (Schwellwert
  = `MetricCatalog.default_change_threshold` für `visibility`) und die
  Sichtweite-Änderung wird gemeldet.

- **AC-3:** Given ein Trip ohne `display_config` aber mit `report_config` /
  When `TripAlertService.check_and_send_alerts()` ausgeführt wird / Then
  fällt der Detector auf `from_trip_config()` zurück (3-Slider-Pfad) und
  meldet nur Änderungen für Metriken, die `default_change_threshold`
  besitzen — identisches Verhalten wie vor diesem Fix.

- **AC-4:** Given `format_metric_value("m", 12240.0)` /
  When der Aufruf ausgeführt wird /
  Then ist der Rückgabewert exakt der String `"12.240 m"` (DE-Tausender-Trenner,
  keine Dezimalstellen).

- **AC-5:** Given `format_metric_value("%", 63.0)` und
  `format_metric_value("%", 33.5, signed=True)` /
  When die Aufrufe ausgeführt werden /
  Then sind die Rückgaben `"63 %"` bzw. `"+34 %"` (Integer, kaufmännische
  Rundung) — kein `63.0%` mehr.

- **AC-6:** Given `format_metric_value("°C", 12.5)` und
  `format_metric_value("mm", -2.3, signed=True)` /
  When die Aufrufe ausgeführt werden /
  Then sind die Rückgaben `"12,5 °C"` bzw. `"−2,3 mm"` (Komma als
  Dezimaltrenner, Unicode-Minus bei signed).

- **AC-7:** Given eine `WeatherChange(metric="visibility_min", old_value=12240,
  new_value=38440, delta=26200, segment_id="2", …)` und ein passendes
  Segment mit `start_time=14:00`, `end_time=16:00` /
  When `format_change_line(change, build_segment_label(change, segments))`
  läuft /
  Then ergibt sich der String
  `"Segment 2 (14:00–16:00) — Sichtweite (min): 12.240 m → 38.440 m (+26.200 m)"`.

- **AC-8:** Given die generierte Alert-E-Mail (HTML + Plain) zu einem Trip
  mit zwei Sichtweite-Änderungen in unterschiedlichen Segmenten /
  When der Renderer läuft /
  Then erscheinen genau zwei Change-Zeilen — eine pro Segment,
  jede mit eigenem `Segment N (HH:MM–HH:MM)` Präfix, und HTML- und Plain-Variante
  rendern dieselbe Information über `format_change_line()` (keine
  Format-Drift).

- **AC-9:** Given die Datei `src/formatters/trip_report.py` /
  When nach dem Refactor gegrept wird (`grep -n "Wetteränderungen" src/formatters/trip_report.py`) /
  Then findet sich kein Match mehr — der tote Change-Renderer-Block
  Z. 966-984 + Z. 1095-1104 ist entfernt.

## Known Limitations

- **Throttle bleibt pro Trip**, nicht pro Segment. Ein Trip mit vielen
  gleichzeitigen Segment-Änderungen liefert weiterhin eine Mail mit
  allen Changes — gewollt, kein Spam pro Segment.
- **Locale-Trick `replace(",", ".")`** statt `locale.setlocale()`, weil
  letzteres process-global wirkt und in einem Web-App-Kontext
  Nebeneffekte haben kann.
- **Sichtweite ohne `display_config`**: Trips, die nie das neue Profil
  bekommen haben, fallen auf den 3-Slider-Pfad zurück und melden
  weiterhin Sichtweite (Metric hat einen `default_change_threshold`).
  Das ist konsistent mit dem heutigen Verhalten — Änderung nur, wenn
  ein User-Trip aktiv ein `display_config` hat.

## Changelog

- 2026-05-13: Initial spec für Issue #131 erstellt.
