---
entity_id: daylight_service
type: module
created: 2026-02-19
updated: 2026-02-19
status: approved
version: "1.0"
tags: [f11, daylight, astral, hiking]
---

# Daylight Service (F11)

## Approval

- [x] Approved

## Purpose

Berechnet das effektive Tageslichfenster ("Ohne Stirnlampe") fuer Weitwanderer.
Kombiniert astronomische Daemmerung (astral), Tal-Heuristik (GPX-Elevation) und
Wetter-Korrekturen (Bewoelkung/Niederschlag) zu einem praxistauglichen Zeitfenster.

## Source

- **File:** `src/services/daylight_service.py`
- **Identifier:** `compute_usable_daylight()`, `DaylightWindow`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `astral` | External lib (v3.2) | Astronomische Berechnungen (dawn/dusk/sunrise/sunset) |
| `ForecastDataPoint` | Model | Wetterdaten fuer cloud_total_pct, precip_1h_mm |

## Implementation Details

### DaylightWindow (dataclass)

```python
@dataclass
class DaylightWindow:
    civil_dawn: datetime       # Buergerliche Daemmerung (astral)
    civil_dusk: datetime       # Buergerliche Abenddaemmerung
    sunrise: datetime          # Astronomischer Sonnenaufgang
    sunset: datetime           # Astronomischer Sonnenuntergang
    usable_start: datetime     # Effektiv: ab wann ohne Stirnlampe
    usable_end: datetime       # Effektiv: ab wann Stirnlampe noetig
    duration_minutes: int      # usable_end - usable_start
    terrain_dawn_penalty_min: int   # 0 wenn kein Tal
    terrain_dusk_penalty_min: int
    weather_dawn_penalty_min: int   # 0 wenn klar
    weather_dusk_penalty_min: int
    notes: list[str]           # z.B. ["Tal-Lage +20min", "Wolken +15min"]
```

### compute_usable_daylight()

**Schicht 1 — Astronomisch (astral):**
- `Observer(lat, lon, elevation=elevation_m)` mit `Depression.CIVIL` (6 Grad)
- Berechnet civil_dawn, civil_dusk, sunrise, sunset

**Schicht 2 — Tal-Heuristik:**
- Vergleicht segment elevation mit route_max_elevation
- Wenn elevation < route_max - 300m: Tal-Penalty
- `penalty_min = min(25, int(elevation_diff / 50))` (10-25 Minuten)
- Dawn: penalty addieren (spaeter hell)
- Dusk: penalty subtrahieren (frueher dunkel)

**Schicht 3 — Wetter-Korrektur:**
- Sucht ForecastDataPoint um dawn/dusk-Stunde (+/- 1h)
- `cloud_total_pct > 80%`: Dawn verschoben bis sunrise (Daemmerung nutzlos)
- `precip_1h_mm > 2mm`: zusaetzlich 15min Penalty (Sichtbehinderung)
- Analog fuer dusk

### Formatter-Integration

**HTML:** Gelber Banner-Block (`background:#fffde7; border-left:4px solid #f9a825`)
zwischen summary_html und segments_html.

**Headline:** `Ohne Stirnlampe: HH:MM - HH:MM (XXh XXm)`

**Erklaerungszeile (nur wenn Korrekturen):**
`Daemmerung HH:MM + XXmin (Tal) + XXmin (Wolken) = HH:MM`

**Plain-Text:** Zwei Zeilen nach Compact Summary, Herleitung eingerueckt mit 3 Spaces.

## Expected Behavior

- **Input:** lat, lon, date, elevation_m, route_max_elevation_m, forecast_data
- **Output:** Optional[DaylightWindow] (None bei polaren Extremfaellen)
- **Side effects:** Keine

## Configuration

- **Toggle:** `TripReportConfig.show_daylight` (default: `True`)
- **UI:** Checkbox "Tageslicht-Fenster (Ohne Stirnlampe)" in Report-Einstellungen
- Wenn deaktiviert: Scheduler ueberspringt die Berechnung, kein Block in der E-Mail

## Known Limitations

- Keine echte Horizon-Berechnung mit DEM/Ray-Tracing
- Tal-Heuristik ist eine Schaetzung, nicht exakt
- Polargebiete (Mitternachtssonne/Polarnacht) geben None zurueck
- Nur aktueller Tag, kein Multi-Day Trend

## Changelog

- 2026-02-19: Initial spec v1.0
