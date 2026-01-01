---
entity_id: weather_metrics
type: module
created: 2025-12-31
updated: 2025-12-31
status: approved
version: "1.0"
tags: [refactoring, architecture, single-source-of-truth]
entities: [WeatherMetrics, CloudStatus, SunnyHours, WeatherSymbol]
---

# Weather Metrics Service (Single Source of Truth)

## Approval

- [x] Approved (2025-12-31)

## Problem Statement

Aktuell gibt es **3+ separate Implementierungen** fuer dieselben Berechnungen:

| Metrik | Stellen im Code | Resultat |
|--------|-----------------|----------|
| Sonnenstunden | `ComparisonEngine.run()`, `fetch_forecast_for_location()`, `run_comparison()` | Inkonsistente Werte |
| Wolkenlage | `render_comparison_html()`, `render_results_table()` | E-Mail zeigt "klar", Web-UI zeigt "in Wolken" |
| Wetter-Symbol | `get_weather_symbol()` (nur 1x, aber nicht von allen genutzt) | - |

**Konsequenz:** Spec und Code driften auseinander, weil Aenderungen an einer Stelle die anderen nicht betreffen.

## Purpose

Zentraler Service fuer alle Wetter-Metrik-Berechnungen. Garantiert identische Ergebnisse in Web-UI, E-Mail und CLI.

**Architektur-Prinzip:** Eine Berechnung = Eine Funktion. Keine Duplikate.

## Source

- **File:** `src/services/weather_metrics.py` (NEU)
- **Identifier:** `WeatherMetricsService` class

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `app.models.ForecastDataPoint` | dataclass | Input-Daten mit Wolken, Temperatur, etc. |
| `app.user.SavedLocation` | dataclass | Location mit elevation_m |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    WeatherMetricsService                     │
│  (Single Source of Truth fuer alle Wetter-Berechnungen)     │
├─────────────────────────────────────────────────────────────┤
│  calculate_sunny_hours(data, elevation) -> int              │
│  calculate_cloud_status(sunny_hours, time_window, ...) -> CloudStatus │
│  calculate_effective_cloud(elevation, clouds) -> int        │
│  get_weather_symbol(cloud, precip, temp, elevation) -> str  │
│  calculate_score(metrics) -> int                            │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
     ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
     │ E-Mail HTML │  │   Web-UI    │  │     CLI     │
     │  Renderer   │  │  Renderer   │  │   Output    │
     └─────────────┘  └─────────────┘  └─────────────┘
```

## Implementation Details

### 1. CloudStatus Enum

```python
class CloudStatus(str, Enum):
    """Wolkenlage-Klassifikation."""
    ABOVE_CLOUDS = "above_clouds"  # "ueber Wolken"
    CLEAR = "clear"                # "klar"
    LIGHT = "light"                # "leicht bewoelkt"
    IN_CLOUDS = "in_clouds"        # "in Wolken"
```

### 2. WeatherMetricsService

```python
class WeatherMetricsService:
    """
    Single Source of Truth fuer Wetter-Metriken.

    WICHTIG: Alle Renderer (E-Mail, Web-UI, CLI) MUESSEN
    diese Klasse verwenden. Keine lokalen Berechnungen!
    """

    @staticmethod
    def calculate_effective_cloud(
        elevation_m: int | None,
        cloud_total_pct: int | None,
        cloud_mid_pct: int | None = None,
        cloud_high_pct: int | None = None,
    ) -> int | None:
        """
        Berechnet effektive Bewoelkung basierend auf Hoehe.

        Hochlagen (>= 2500m) ignorieren tiefe Wolken.

        Returns:
            Effektive Bewoelkung in % (0-100) oder None
        """
        if elevation_m and elevation_m >= 2500:
            if cloud_mid_pct is not None and cloud_high_pct is not None:
                return (cloud_mid_pct + cloud_high_pct) // 2
        return cloud_total_pct

    @staticmethod
    def calculate_sunny_hours(
        data: List[ForecastDataPoint],
        elevation_m: int | None = None,
    ) -> int:
        """
        Berechnet Sonnenstunden aus Wolkendecke.

        DATENQUELLE: BERECHNET (nicht API!)
        Siehe: docs/specs/data_sources.md (sunshine_duration = REJECTED)

        Formel:
            sunshine_pct = 100 - effective_cloud_pct
            Summe aller Stunden / 100 = Sonnenstunden

        Hochlagen (>= 2500m) ignorieren tiefe Wolken via calculate_effective_cloud().

        Returns:
            Anzahl Sonnenstunden (gerundet auf ganze Stunden)
        """
        if not data:
            return 0

        total_sunshine_pct = 0.0

        for dp in data:
            # Effektive Wolkendecke (elevation-aware)
            eff_cloud = WeatherMetricsService.calculate_effective_cloud(
                elevation_m, dp.cloud_total_pct,
                dp.cloud_mid_pct, dp.cloud_high_pct
            )

            if eff_cloud is not None:
                # Sonnenschein = Inverse der Bewoelkung
                sunshine_pct = max(0, 100 - eff_cloud)
                total_sunshine_pct += sunshine_pct

        # Prozent -> Stunden (100% = 1h), gerundet
        return round(total_sunshine_pct / 100.0)

    @staticmethod
    def calculate_cloud_status(
        sunny_hours: int | None,
        time_window_hours: int,
        elevation_m: int | None = None,
        cloud_low_avg: int | None = None,
    ) -> CloudStatus:
        """
        Bestimmt Wolkenlage basierend auf Sonnenstunden.

        Regeln (SPEC: docs/specs/compare_email.md):
        1. Hochlage (>= 2500m) + cloud_low > 30% + sunny >= 5h -> ABOVE_CLOUDS
        2. sunny >= 75% der Stunden -> CLEAR
        3. sunny >= 25% der Stunden -> LIGHT
        4. sonst -> IN_CLOUDS

        Returns:
            CloudStatus enum
        """
        if sunny_hours is None:
            return CloudStatus.IN_CLOUDS

        # Regel 1: Hochlage ueber den Wolken
        if (elevation_m and elevation_m >= 2500
            and cloud_low_avg is not None
            and cloud_low_avg > 30
            and sunny_hours >= 5):
            return CloudStatus.ABOVE_CLOUDS

        # Regel 2-4: Basierend auf Sonnenstunden-Anteil
        if sunny_hours >= time_window_hours * 0.75:
            return CloudStatus.CLEAR
        elif sunny_hours >= time_window_hours * 0.25:
            return CloudStatus.LIGHT
        else:
            return CloudStatus.IN_CLOUDS

    @staticmethod
    def format_cloud_status(status: CloudStatus) -> tuple[str, str]:
        """
        Formatiert CloudStatus fuer Anzeige.

        Returns:
            Tuple von (display_text, css_style)
        """
        mapping = {
            CloudStatus.ABOVE_CLOUDS: ("ueber Wolken", "color: #2e7d32; font-weight: 600;"),
            CloudStatus.CLEAR: ("klar", "color: #2e7d32;"),
            CloudStatus.LIGHT: ("leicht", ""),
            CloudStatus.IN_CLOUDS: ("in Wolken", "color: #888;"),
        }
        return mapping.get(status, ("-", ""))

    @staticmethod
    def get_weather_symbol(
        cloud_total_pct: int | None,
        precip_mm: float | None,
        temp_c: float | None,
        elevation_m: int | None = None,
        cloud_mid_pct: int | None = None,
        cloud_high_pct: int | None = None,
    ) -> str:
        """
        Bestimmt Wetter-Symbol basierend auf Bedingungen.

        Beruecksichtigt Hoehe fuer effektive Bewoelkung.

        Returns:
            Emoji-Symbol (str)
        """
        # Niederschlag hat Prioritaet
        if precip_mm and precip_mm > 0.5:
            if temp_c is not None and temp_c < 0:
                return "snow"  # Schnee
            return "rain"  # Regen

        # Bewoelkung
        eff_cloud = WeatherMetricsService.calculate_effective_cloud(
            elevation_m, cloud_total_pct, cloud_mid_pct, cloud_high_pct
        )

        if eff_cloud is None:
            return "?"
        if eff_cloud < 20:
            return "sunny"
        if eff_cloud < 50:
            return "partly_cloudy"
        if eff_cloud < 80:
            return "mostly_cloudy"
        return "cloudy"
```

### 3. Migration der bestehenden Stellen

| Datei | Funktion | Aktion |
|-------|----------|--------|
| `compare.py` | `_calc_effective_cloud()` | LOESCHEN, durch `WeatherMetricsService.calculate_effective_cloud()` ersetzen |
| `compare.py` | `get_weather_symbol()` | LOESCHEN, durch `WeatherMetricsService.get_weather_symbol()` ersetzen |
| `compare.py` | Sonnenstunden in `ComparisonEngine.run()` | Durch `WeatherMetricsService.calculate_sunny_hours()` ersetzen |
| `compare.py` | Sonnenstunden in `fetch_forecast_for_location()` | Durch `WeatherMetricsService.calculate_sunny_hours()` ersetzen |
| `compare.py` | Wolkenlage in `render_comparison_html()` | Durch `WeatherMetricsService.calculate_cloud_status()` ersetzen |
| `compare.py` | Wolkenlage in `render_results_table()` | Durch `WeatherMetricsService.calculate_cloud_status()` ersetzen |

### 4. Wetter-Symbol Legende

Alle Renderer (E-Mail, Web-UI) zeigen eine Legende:

| Symbol | Bedeutung | Bewoelkung |
|--------|-----------|------------|
| ☀️ | Sonnig | < 20% |
| ⛅ | Teilweise bewoelkt | 20-50% |
| 🌥️ | Ueberwiegend bewoelkt | 50-80% |
| ☁️ | Bedeckt | > 80% |
| 🌧️ | Regen | (Niederschlag > 0.5mm, Temp >= 0) |
| ❄️ | Schnee | (Niederschlag > 0.5mm, Temp < 0) |

### 5. Spec-Tests (Pflicht)

```python
# tests/spec/test_weather_metrics_spec.py

class TestSunnyHoursSpec:
    """Tests fuer Sonnenstunden-Berechnung aus Wolkendecke."""

    def test_clear_sky_full_sunshine(self):
        """0% Wolken = 1h Sonnenschein pro Stunde."""
        data = [
            ForecastDataPoint(ts=datetime(2025,1,1,9), cloud_total_pct=0),
            ForecastDataPoint(ts=datetime(2025,1,1,10), cloud_total_pct=0),
        ]
        assert WeatherMetricsService.calculate_sunny_hours(data) == 2

    def test_partial_clouds(self):
        """30% Wolken = 70% Sonnenschein = 0.7h pro Stunde."""
        data = [
            ForecastDataPoint(ts=datetime(2025,1,1,9), cloud_total_pct=30),
            ForecastDataPoint(ts=datetime(2025,1,1,10), cloud_total_pct=30),
            ForecastDataPoint(ts=datetime(2025,1,1,11), cloud_total_pct=30),
        ]
        # 3 * 70% = 210% = 2.1h -> gerundet = 2h
        assert WeatherMetricsService.calculate_sunny_hours(data) == 2

    def test_high_elevation_ignores_low_clouds(self):
        """Hochlage ignoriert tiefe Wolken."""
        data = [
            ForecastDataPoint(
                ts=datetime(2025,1,1,9),
                cloud_total_pct=80,
                cloud_mid_pct=10,
                cloud_high_pct=10,
            ),
        ]
        # Effektiv: (10+10)/2 = 10% -> 90% Sonnenschein -> 1h
        assert WeatherMetricsService.calculate_sunny_hours(data, elevation_m=3000) == 1


class TestCloudStatusSpec:
    """Tests gegen docs/specs/compare_email.md Zeile 212-216"""

    def test_above_clouds_high_elevation(self):
        status = WeatherMetricsService.calculate_cloud_status(
            sunny_hours=6, time_window_hours=8,
            elevation_m=3000, cloud_low_avg=50
        )
        assert status == CloudStatus.ABOVE_CLOUDS

    def test_clear_75_percent_sunshine(self):
        status = WeatherMetricsService.calculate_cloud_status(
            sunny_hours=6, time_window_hours=8,
            elevation_m=2000, cloud_low_avg=10
        )
        assert status == CloudStatus.CLEAR

    def test_light_25_percent_sunshine(self):
        status = WeatherMetricsService.calculate_cloud_status(
            sunny_hours=3, time_window_hours=8,
            elevation_m=2000, cloud_low_avg=30
        )
        assert status == CloudStatus.LIGHT

    def test_in_clouds_low_sunshine(self):
        status = WeatherMetricsService.calculate_cloud_status(
            sunny_hours=1, time_window_hours=8,
            elevation_m=2000, cloud_low_avg=60
        )
        assert status == CloudStatus.IN_CLOUDS
```

## Expected Behavior

- **Input:** ForecastDataPoint-Listen, Location-Daten
- **Output:** Konsistente Metriken (Sonnenstunden, Wolkenlage, Symbole)
- **Side effects:** Keine

## Validation

Nach Implementation MUSS gelten:

1. `grep -r "sunny_hours\s*=" src/` zeigt NUR `WeatherMetricsService`
2. `grep -r "cloud_status" src/` zeigt NUR `WeatherMetricsService`
3. `grep -r "_calc_effective_cloud" src/` zeigt 0 Treffer (geloescht)
4. Alle Spec-Tests gruen

## Scope

**Dateien:** 4
- `src/services/weather_metrics.py` (NEU, ~150 LoC)
- `src/web/pages/compare.py` (AENDERN, ~-100 LoC durch Entfernen von Duplikaten)
- `tests/spec/test_weather_metrics_spec.py` (NEU, ~50 LoC)
- `docs/specs/compare_email.md` (UPDATE, Verweis auf weather_metrics)

**LoC:** ~+100 netto (mehr Tests, weniger Duplikate)

## Known Limitations

- Erfordert Update aller bestehenden Renderer
- Spec-Tests muessen bei Spec-Aenderungen manuell aktualisiert werden

## Changelog

- 2026-01-01: Sonnenstunden-Berechnung auf wolkenbasierte Formel umgestellt (sunshine_duration_s war REJECTED)
- 2026-01-01: Wetter-Symbol Legende fuer E-Mail und WebUI hinzugefuegt
- 2025-12-31: Initial spec created nach Inkonsistenz-Bug zwischen E-Mail und Web-UI
