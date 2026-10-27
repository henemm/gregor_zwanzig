---
entity_id: compare_email
type: feature
created: 2025-12-28
updated: 2026-01-02
status: implemented
version: "4.3"
tags: [ui, nicegui, compare, email, scheduler]
entities: [comparesubscription, comparisonengine, comparisonresult, locationresult, hourlycell]
---

# Compare Subscription Scheduler

## Approval

- [x] Approved (2025-12-28)
- [x] Updated v3.0 (2025-12-29): HTML Email, Single Processor Architecture

## Purpose

Automatischer E-Mail-Versand von Skigebiet-Vergleichen nach konfigurierbarem Schedule.

Use Case: "Jeden Freitag um 18:00 bekomme ich eine E-Mail mit dem Ranking meiner Skigebiete fuer das Wochenende (9-16 Uhr)."

**Kernprinzip:** Ein Prozessor generiert die Daten, verschiedene Renderer stellen sie dar.
Website und E-Mail zeigen IDENTISCHE Inhalte, nur in unterschiedlichem Format/Layout.

## Architecture

```
ComparisonEngine.run(locations, time_window, target_date)
    → ComparisonResult (Dataclass mit allen Metriken)
        ↓
        ├─ WebRenderer.render(result) → NiceGUI UI
        └─ EmailRenderer.render(result) → HTML Email
```

**Keine Code-Duplizierung!** Änderungen am Prozessor wirken sich auf beide Outputs aus.

## Source

- **File:** `src/app/user.py` - CompareSubscription Dataclass
- **File:** `src/app/loader.py` - Load/Save Funktionen
- **File:** `src/web/pages/compare.py` - ComparisonEngine + Renderer
- **File:** `src/app/cli.py` - --run-subscriptions Command
- **File:** `src/web/pages/subscriptions.py` - Verwaltungs-UI

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `app.models.ForecastDataPoint` | dataclass | Forecast-Datenpunkte mit Timestamp |
| `outputs.email.EmailOutput` | class | E-Mail-Versand via SMTP |
| `app.config.Settings` | class | SMTP-Konfiguration |
| `nicegui` | external | UI-Framework |

## Scope: Ticket 1 (MVP)

**Enthalten:**
- Zeit-Filter Funktion
- E-Mail-Format Funktion
- UI: Zeitfenster-Dropdowns (Start/End Stunde)
- UI: Stunden-Tabelle pro Location
- UI: Sofort-E-Mail Button

**NICHT enthalten (Ticket 2):**
- Subscription-System
- Scheduled E-Mail-Versand
- Persistente Konfiguration

## Implementation Details

### 1. Zeit-Filter Funktion

```python
def filter_data_by_hours(
    data: List[ForecastDataPoint],
    start_hour: int,  # z.B. 9
    end_hour: int,    # z.B. 16
) -> List[ForecastDataPoint]:
    """Filtert Forecast auf bestimmte Tagesstunden."""
    return [dp for dp in data if start_hour <= dp.ts.hour < end_hour]
```

### 2. ComparisonResult Dataclass

```python
@dataclass
class ComparisonResult:
    """Ergebnis eines Skigebiet-Vergleichs."""
    locations: List[LocationResult]  # Sortiert nach Score
    time_window: Tuple[int, int]     # (start_hour, end_hour)
    target_date: date                # Forecast-Datum
    created_at: datetime             # Erstellungszeitpunkt

@dataclass
class LocationResult:
    """Ergebnis einer einzelnen Location."""
    location: SavedLocation
    score: int
    snow_depth_cm: Optional[float]
    snow_new_cm: Optional[float]
    temp_min: Optional[float]
    temp_max: Optional[float]
    wind_max: Optional[float]
    wind_chill_min: Optional[float]
    cloud_avg: Optional[int]
    sunny_hours: Optional[int]
    hourly_data: List[ForecastDataPoint]  # Gefilterte Stunden
    # v3.2: Neue Felder
    wind_direction_avg: Optional[int]     # Durchschnittliche Windrichtung (Grad)
    gust_max_kmh: Optional[float]         # Maximale Boeengeschwindigkeit
    cloud_low_avg: Optional[int]          # Durchschn. tiefe Bewoelkung (fuer Wolkenlage)
```

### 3. Renderer Interface

```python
def render_comparison_html(result: ComparisonResult) -> str:
    """Rendert ComparisonResult als HTML (fuer Email)."""

def render_comparison_ui(result: ComparisonResult, container: ui.element) -> None:
    """Rendert ComparisonResult in NiceGUI UI."""
```

Beide Renderer verwenden DASSELBE ComparisonResult - garantiert identische Inhalte.

### 4. UI-Erweiterungen

- Zwei Dropdowns fuer Start-/End-Stunde (6:00-20:00)
- Stunden-Tabelle pro Location (expandierbar)
- "Per E-Mail senden" Button (nur wenn SMTP konfiguriert)

### 5. Effektive Bewoelkung (Hoehenkorrektur)

Hochlagen (>2500m) sind oft UEBER den tiefen Wolken.
Das Wetter-Symbol muss dies beruecksichtigen.

**Regel:**
```
Wenn elevation >= 2500m:
  effektive_bewoelkung = (cloud_mid + cloud_high) / 2
  (tiefe Wolken sind unter der Location → ignorieren)

Sonst:
  effektive_bewoelkung = cloud_total
  (alle Wolkenschichten betreffen die Location)

Wetter-Symbol = basiert auf effektive_bewoelkung
```

**Wolkenschicht-Hoehen:**
- Low clouds: 0 - 2km → unter Hochlagen (>2500m)
- Mid clouds: 2 - 6km → betrifft alle Bergstationen
- High clouds: >6km → betrifft alle

**Beispiel Hintertuxer Gletscher (3000m):**
- cloud_total = 80% (hoch, weil viele tiefe Wolken)
- cloud_low = 100% (Nebel im Tal)
- cloud_mid = 0%, cloud_high = 0%
- → effektive_bewoelkung = 0% → ☀️ Sonne

### 6. Sonnenstunden und Wolkenlage (Single Source of Truth)

**ALLE Berechnungen erfolgen ueber `WeatherMetricsService`!**

Siehe: `docs/specs/modules/weather_metrics.md`

```python
from services.weather_metrics import WeatherMetricsService, CloudStatus

# Sonnenstunden berechnen
sunny_hours = WeatherMetricsService.calculate_sunny_hours(data, elevation_m)

# Wolkenlage bestimmen
cloud_status = WeatherMetricsService.calculate_cloud_status(
    sunny_hours, time_window_hours, elevation_m, cloud_low_avg
)
```

**WICHTIG:** Sonnenstunden und Wolkenlage sind KONSISTENT, weil beide
aus demselben Service kommen. Keine lokalen Berechnungen erlaubt!

### 7. HourlyCell - Single Source of Truth fuer Stunden-Zellen

**KRITISCH:** WebUI und E-Mail muessen IDENTISCHE Stunden-Daten anzeigen!

Eine gemeinsame Dataclass und Formatter-Funktion garantieren Konsistenz:

```python
@dataclass
class HourlyCell:
    """Eine Stunden-Zelle - identisch fuer UI und Email."""
    hour: int                    # 9, 10, 11, ...
    symbol: str                  # "☀️", "🌤️", "⛅", "☁️"
    temp_c: int                  # Gefuehlte Temperatur (Wind Chill), Fallback: Lufttemp
    precip_symbol: str           # "🌨️", "🌧️", ""
    precip_amount: Optional[float]  # 2.5, None wenn kein Niederschlag
    precip_unit: str             # "cm", "mm"
    wind_kmh: int                # 15
    gust_kmh: int                # 25
    wind_dir: str                # "SW", "N", "NE"

def format_hourly_cell(dp: ForecastDataPoint, elevation_m: int) -> HourlyCell:
    """
    Single Source of Truth fuer Stunden-Formatierung.

    Wird von BEIDEN Renderern verwendet:
    - render_comparison_html() fuer E-Mail
    - render_hourly_table() fuer WebUI
    """
    # Effektive Bewoelkung berechnen (Hoehenkorrektur)
    effective_cloud = WeatherMetricsService.calculate_effective_cloud(
        dp.cloud_total, dp.cloud_low, dp.cloud_mid, dp.cloud_high, elevation_m
    )
    symbol = WeatherMetricsService.get_weather_symbol(effective_cloud, dp.precip)

    # Niederschlagsart basierend auf Temperatur
    if dp.precip and dp.precip > 0:
        if dp.temp_c < 2:
            precip_symbol = "🌨️"
            precip_unit = "cm"
            # mm Wasser -> cm Schnee (Faktor ~10)
            precip_amount = round(dp.precip / 10, 1)
        else:
            precip_symbol = "🌧️"
            precip_unit = "mm"
            precip_amount = round(dp.precip, 1)
    else:
        precip_symbol = ""
        precip_amount = None
        precip_unit = ""

    # v4.3: Wind Chill fuer konsistente gefuehlte Temperatur
    # Vergleichs-Header zeigt auch Wind Chill - stundlich muss identisch sein
    felt_temp = dp.wind_chill_c if dp.wind_chill_c is not None else dp.temp_c

    return HourlyCell(
        hour=dp.ts.hour,
        symbol=symbol,
        temp_c=round(felt_temp),
        precip_symbol=precip_symbol,
        precip_amount=precip_amount,
        precip_unit=precip_unit,
        wind_kmh=round(dp.wind_kmh or 0),
        gust_kmh=round(dp.gust_kmh or 0),
        wind_dir=degrees_to_compass(dp.wind_direction or 0),
    )

def hourly_cell_to_compact(cell: HourlyCell) -> str:
    """Kompakte String-Darstellung fuer Tabellen-Zelle."""
    # Format: ☀️-5° 🌨️2cm 15/25SW
    precip = f"{cell.precip_symbol}{cell.precip_amount}{cell.precip_unit}" if cell.precip_amount else "-"
    return f"{cell.symbol}{cell.temp_c}° {precip} {cell.wind_kmh}/{cell.gust_kmh}{cell.wind_dir}"
```

**Location:** `src/services/weather_metrics.py`

**Verwendung in beiden Renderern:**
```python
# In render_comparison_html() UND render_hourly_table():
cell = format_hourly_cell(dp, location.elevation_m)
cell_text = hourly_cell_to_compact(cell)
```

## E-Mail Format - Multipart (HTML + Plain-Text)

E-Mails werden als **Multipart** versendet (HTML + Plain-Text Fallback).

### MIME-Struktur

```
Content-Type: multipart/alternative
├── text/plain (Fallback fuer alte Clients)
└── text/html (Primaere Darstellung)
```

## E-Mail Format (Plain-Text) - EXAKTE SPEZIFIKATION

Fuer E-Mail-Clients ohne HTML-Support.

### Header-Bereich

```
⛷️ SKIGEBIETE-VERGLEICH
========================
📅 Forecast: [Wochentag, DD.MM.YYYY]
🕐 Zeitfenster: [HH]:00 - [HH]:00
📝 Erstellt: [DD.MM.YYYY HH:MM]
```

### Winner-Box

```
🏆 EMPFEHLUNG: [Location Name]
   Score: [N] | ❄️ [N]cm Schnee | ☀️ ~[N]h Sonne
```

### Vergleichstabelle (Plain-Text)

```
#1 [Location Name]          #2 [Location Name]
Score: [N]                  Score: [N]
Schnee: [N]cm               Schnee: [N]cm
Neuschnee: +[N]cm           Neuschnee: -
Wind: 10/41 SW              Wind: 15/30 NE
Temp: [N]°C                 Temp: [N]°C
Sonne: ~[N]h                Sonne: ~[N]h
Wolken: [N]%                Wolken: [N]%
Lage: ☀️ ueber Wolken       Lage: ☁️ in Wolken
```

### Stunden-Tabelle (Plain-Text)

```
STUNDEN-DETAILS
---------------
Zeit  | #1 Location    | #2 Location    | #3 Location
09:00 | ☀️-5° -  15/25SW | 🌤️-3° - 10/18N | ⛅-2° 🌨️1cm 8/12E
10:00 | ☀️-4° -  12/20SW | 🌤️-2° - 8/15N  | ☁️-1° 🌨️2cm 10/15E
...
```

**Spaltenbreite:** Max 16 Zeichen pro Location (inkl. Padding)

### Footer

```
---
Generiert von Gregor Zwanzig ⛷️
```

## E-Mail Format (HTML) - EXAKTE SPEZIFIKATION

**KRITISCH:** Es darf nur EINEN HTML-Renderer geben (`render_comparison_html`).
Die UI-Button-Funktion muss diesen Renderer verwenden, KEINE separate Implementierung!

### Header-Bereich

```
H1: "⛷️ Skigebiete-Vergleich"
P:  "📅 Forecast für: [Wochentag, DD.MM.YYYY]"
P:  "🕐 Zeitfenster: [HH]:00 - [HH]:00"
P:  "📝 Erstellt: [DD.MM.YYYY HH:MM]"
```

### Winner-Box

```
H2: "🏆 Empfehlung: [Location Name]"
P:  "Score: [N] | ❄️ [N]cm Schnee | ☀️ ~[N]h Sonne"
```

### Vergleichstabelle - EXAKTE ZEILEN

| Zeile | Label | Format | Grün-Markierung |
|-------|-------|--------|-----------------|
| 1 | Header | "#[N] [Location Name]" | - |
| 2 | Score | "[N]" | Höchster Wert |
| 3 | Schneehöhe | "[N]cm" oder "-" | Höchster Wert |
| 4 | Neuschnee | "+[N]cm" oder "-" | Höchster Wert |
| 5 | Wind/Böen | "[W]/[B] [Richtung]" z.B. "10/41 SW" | Niedrigster Wind |
| 6 | Temperatur (gefühlt) | "[N]°C" | Höchster Wert (wärmer) |
| 7 | Sonnenstunden | "~[N]h" oder "0h" (NICHT "-" bei 0!) | Höchster Wert |
| 8 | Bewölkung | "[N]%" | Niedrigster Wert |
| 9 | Wolkenlage | Siehe unten | - |

**Wolkenlage-Werte (Zeile 9):**
- `elevation >= 2500m AND cloud_low > 30%`: "☀️ über Wolken" (grün)
- `cloud_low > 50%`: "☁️ in Wolken" (grau)
- `cloud_low < 20%`: "✨ klar" (grün)
- Sonst: "🌤️ leicht"

### Stunden-Tabelle

Für Top-N Locations (default: 3):

| Zeit | #1 [Name] | #2 [Name] | #3 [Name] |
|------|-----------|-----------|-----------|
| 09:00 | ☀️-5° 🌨️2cm 15/25SW | ... | ... |
| 10:00 | 🌤️-3° - 10/18SW | ... | ... |
| ... | ... | ... | ... |

**Pro Stunde werden angezeigt (kompakt, ohne Leerzeichen):**

| Element | Format | Beispiele |
|---------|--------|-----------|
| Wetter-Symbol | Emoji | ☀️ 🌤️ ⛅ ☁️ 🌧️ 🌨️ |
| Temperatur | `[N]°` | `-5°`, `12°` |
| Niederschlag | `[Symbol][N]cm/mm` oder `-` | `🌨️2cm`, `🌧️3mm`, `-` |
| Wind/Böen+Richtung | `[W]/[B][Dir]` | `15/25SW`, `8/12N` |

**Niederschlagsregeln:**
- Schnee (temp < 2°C): `🌨️[N]cm` - Menge als Schneehöhe
- Regen (temp >= 2°C): `🌧️[N]mm` - Menge in mm
- Kein Niederschlag: `-`

**Beispiel-Zeile:** `☀️-5° 🌨️2cm 15/25SW` (ca. 18 Zeichen)

**Wetter-Symbol basiert auf effektiver Bewölkung** (siehe Effektive Bewölkung).

### Footer

```
"Generiert von Gregor Zwanzig ⛷️"
```

### Formatierungsregeln

1. **Sonnenstunden:** `0` zeigt "0h" an, NICHT "-"
2. **Wind kombiniert:** Eine Zeile für Wind/Böen/Richtung: "10/41 SW"
3. **Keine Gradangabe:** Windrichtung nur als Himmelsrichtung (N, NE, E, SE, S, SW, W, NW)
4. **Grün-Markierung:** Bester Wert bekommt grünen Hintergrund + fette Schrift

## Expected Behavior

- **Input:** Klick auf "Per E-Mail senden" nach Vergleich
- **Output:** HTML E-Mail mit Ranking und Stunden-Details (identisch zur Web-UI)
- **Side effects:**
  - E-Mail wird via SMTP versendet
  - UI zeigt Erfolgs-/Fehlermeldung

## Validation

- SMTP muss konfiguriert sein (`settings.can_send_email()`)
- Mindestens eine Location muss verglichen worden sein
- Zeitfenster: start_hour < end_hour

## Known Limitations

- Nur Sofort-Versand (kein Scheduling in MVP)
- Zeitfenster nicht persistent (nur UI-State)

## Follow-up: Ticket 2 (Backlog)

Fuer spaetere Erweiterung:
- `CompareSubscription` Datenmodell
- Persistenz in `data/users/default/compare_subscriptions.json`
- Settings-UI fuer Subscription-Verwaltung
- Scheduler-Integration (CLI/Cron)

## Changelog

- 2026-01-02: v4.3 - Konsistente gefuehlte Temperatur
  - HourlyCell zeigt jetzt Wind Chill statt Lufttemperatur
  - Konsistent mit Vergleichs-Header (der bereits Wind Chill zeigte)
  - Fallback auf Lufttemperatur wenn Wind Chill nicht verfuegbar
- 2025-12-31: v4.2 - HourlyCell + Multipart E-Mail
  - NEU: `HourlyCell` Dataclass als Single Source of Truth
  - NEU: `format_hourly_cell()` fuer konsistente Stunden-Formatierung
  - NEU: Multipart E-Mail (HTML + Plain-Text Fallback)
  - NEU: Plain-Text E-Mail Format spezifiziert
  - WebUI und E-Mail verwenden dieselbe Formatter-Funktion
- 2025-12-31: v4.1 - Erweiterte Stunden-Tabelle
  - Stunden-Tabelle zeigt jetzt: Symbol, Temp, Niederschlag, Wind/Böen+Richtung
  - Kompaktes Format ohne Leerzeichen: `☀️-5° 🌨️2cm 15/25SW`
  - Niederschlag als Schneehöhe (cm) bei <2°C, sonst mm
- 2025-12-31: v4.0 - Exakte E-Mail Spezifikation
  - BREAKING: Nur noch EIN Renderer (`render_comparison_html`)
  - `format_compare_email` muss entfernt werden (Code-Duplizierung)
  - Wind/Böen/Richtung in EINER Zeile: "10/41 SW"
  - Keine Gradangabe bei Windrichtung
  - Sonnenstunden: 0 zeigt "0h" (nicht "-")
  - Wolkenlage-Zeile ist PFLICHT
  - Exakte Tabellen-Struktur definiert (9 Zeilen)
- 2025-12-30: v3.2 - Windrichtung, Boeen, Neuschnee
  - Neue Felder: wind_direction_avg, gust_max_kmh, snow_new_cm
  - Windrichtung als Durchschnitt im Zeitfenster (Gradangabe + Himmelsrichtung)
  - Boeengeschwindigkeit als Maximum im Zeitfenster
  - Neuschnee in cm (aus AROME snow_acc, bereits in cm konvertiert)
- 2025-12-29: v3.1 - Effektive Bewoelkung fuer Hochlagen
  - Wetter-Symbol beruecksichtigt Hoehe der Location
  - Hochlagen (>2500m) ignorieren tiefe Wolken (cloud_low)
  - Zeigt korrekt Sonne wenn Location ueber den Wolken liegt
- 2025-12-29: v3.0 - Single Processor Architecture, HTML Email
  - Refactoring: Ein ComparisonEngine, zwei Renderer (Web + Email)
  - HTML statt Plain-Text E-Mail
  - Garantiert identische Inhalte in Web und Email
- 2025-12-28: Initial spec created
