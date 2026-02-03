# Context: Bugfix - Empty Subscription Emails

**Workflow:** Bugfix: Empty Subscription Emails
**Phase:** Analysis (Phase 2)
**Date:** 2026-02-03

---

## Problem Statement

Subscription E-Mails (z.B. "Serfaus 18:00" daily_evening) werden versendet, enthalten aber **keine Wetterdaten**:
- Score: 0 (statt 50-80)
- Temp/Wind/Snow: "-" (statt echte Werte)
- E-Mail zeigt nur leeres Template

**User Impact:** HIGH - Subscriptions sind unbrauchbar

---

## Analysis

### Root Cause

**Commit:** `bce2991` - Feature 2.2b (Erweiterte Metriken)

Bei Refactoring von `WeatherMetricsService` wurden **3 statische Methoden gelöscht**, die noch von `compare.py` verwendet werden:

1. ❌ `HIGH_ELEVATION_THRESHOLD_M = 2500` (Konstante)
2. ❌ `calculate_effective_cloud()` (static method)
3. ❌ `calculate_sunny_hours()` (static method)

**Fehler-Kette:**
```
ComparisonEngine.run() (compare.py:333)
  → WeatherMetricsService.calculate_sunny_hours(filtered_data, elevation)
  → AttributeError: 'WeatherMetricsService' has no attribute 'calculate_sunny_hours'
  → Exception wird gefangen (compare.py:377)
  → LocationResult.error gesetzt
  → Score bleibt 0, alle Metriken None
  → E-Mail zeigt leere Werte
```

---

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/weather_metrics.py` | MODIFY | Restore 3 static methods + constant |
| `tests/unit/test_weather_metrics.py` | CREATE | Unit tests for restored methods |

**Dependencies (no changes needed):**
- `src/web/pages/compare.py` - verwendet die Methoden (12 Stellen!)
- `src/web/scheduler.py` - ruft Subscriptions auf

---

### Usage Analysis: compare.py

**12 Verwendungsstellen:**

**ComparisonEngine.run() (Subscription path):**
- Zeile 315: `calculate_effective_cloud()` - Cloud-Berechnung für hohe Lagen
- Zeile 329: `HIGH_ELEVATION_THRESHOLD_M` - Check für "above_low_clouds" Flag
- Zeile 333: `calculate_sunny_hours()` - Sonnenstunden-Berechnung

**fetch_forecast_for_location() (UI path):**
- Zeile 974: `calculate_sunny_hours()` - Sonnenstunden für UI

**run_comparison() (UI path):**
- Zeile 1299: `calculate_effective_cloud()` - Cloud-Berechnung
- Zeile 1313: `HIGH_ELEVATION_THRESHOLD_M` - Above-clouds Check
- Zeile 1317: `calculate_sunny_hours()` - Sonnenstunden

**render_comparison_text() (Email plain-text):**
- Zeile 756: `degrees_to_compass()` - Wind-Richtung (existiert noch!)
- Zeile 772-778: `calculate_cloud_status()` + helpers (existieren noch!)

**render_comparison_ui() (Web UI):**
- Zeile 644, 665: `format_hourly_cell()`, `hourly_cell_to_compact()` (existieren noch!)
- Zeile 1495-1496: `format_hourly_cell()`, `hourly_cell_to_compact()` (existieren noch!)

**Status:**
- ✅ 9 Methoden existieren noch (werden nicht gebraucht für den Fix)
- ❌ 3 Methoden fehlen (müssen restored werden)

---

### Scope Assessment

- **Files:** 2 (weather_metrics.py + neue Tests)
- **Estimated LoC:** +120 (Restore) / +50 (Tests)
- **Risk Level:** LOW
  - Restore bekannten, funktionierenden Code aus Git
  - Keine Breaking Changes
  - Isoliert in einem Service

---

### Technical Approach

**1. Restore Static Methods**

Aus Commit `575cd6c` (letzter bekannt-funktionierender Stand):

```python
class WeatherMetricsService:
    # Konstante
    HIGH_ELEVATION_THRESHOLD_M = 2500
    SUNNY_HOUR_CLOUD_THRESHOLD_PCT = 30

    @staticmethod
    def calculate_effective_cloud(
        elevation_m: Optional[int],
        cloud_total_pct: Optional[int],
        cloud_mid_pct: Optional[int] = None,
        cloud_high_pct: Optional[int] = None,
    ) -> Optional[int]:
        """Calculate effective cloud cover based on elevation."""
        # Hohe Lagen (>= 2500m): ignoriere Low-Clouds, nutze nur Mid+High
        if (elevation_m is not None
            and elevation_m >= WeatherMetricsService.HIGH_ELEVATION_THRESHOLD_M
            and cloud_mid_pct is not None
            and cloud_high_pct is not None):
            return (cloud_mid_pct + cloud_high_pct) // 2
        return cloud_total_pct

    @staticmethod
    def calculate_sunny_hours(
        data: List["ForecastDataPoint"],
        elevation_m: Optional[int] = None,
    ) -> int:
        """Calculate sunny hours from forecast data."""
        if not data:
            return 0

        # Method 1: API sunshine_duration_s (preferred)
        sunshine_secs = [dp.sunshine_duration_s for dp in data
                        if hasattr(dp, 'sunshine_duration_s')
                        and dp.sunshine_duration_s is not None]
        api_hours = round(sum(sunshine_secs) / 3600) if sunshine_secs else 0

        # Method 2: Cloud-based fallback für hohe Lagen
        spec_hours = 0
        if elevation_m and elevation_m >= WeatherMetricsService.HIGH_ELEVATION_THRESHOLD_M:
            for dp in data:
                eff_cloud = WeatherMetricsService.calculate_effective_cloud(
                    elevation_m, dp.cloud_total_pct,
                    getattr(dp, 'cloud_mid_pct', None),
                    getattr(dp, 'cloud_high_pct', None)
                )
                if eff_cloud and eff_cloud < WeatherMetricsService.SUNNY_HOUR_CLOUD_THRESHOLD_PCT:
                    spec_hours += 1

        return max(api_hours, spec_hours)
```

**2. Platzierung im Code**

Nach Zeile 70 (nach `degrees_to_compass()`, vor `calculate_cloud_status()`):
- Passt zur bestehenden Struktur (statische Methoden am Anfang)
- Vor den anderen Cloud-Status-Methoden
- Mit Kommentar: "Legacy static methods for compare.py compatibility"

**3. Tests**

```python
# tests/unit/test_weather_metrics_legacy.py

def test_calculate_effective_cloud_high_elevation():
    """High elevations ignore low clouds."""
    eff = WeatherMetricsService.calculate_effective_cloud(
        elevation_m=2600,
        cloud_total_pct=80,
        cloud_mid_pct=40,
        cloud_high_pct=20,
    )
    assert eff == 30  # (40 + 20) // 2

def test_calculate_effective_cloud_low_elevation():
    """Low elevations use total clouds."""
    eff = WeatherMetricsService.calculate_effective_cloud(
        elevation_m=1500,
        cloud_total_pct=80,
        cloud_mid_pct=40,
        cloud_high_pct=20,
    )
    assert eff == 80

def test_calculate_sunny_hours_api_based():
    """Primary method: API sunshine duration."""
    dp1 = ForecastDataPoint(ts=datetime.now(), sunshine_duration_s=3600)
    dp2 = ForecastDataPoint(ts=datetime.now(), sunshine_duration_s=1800)
    hours = WeatherMetricsService.calculate_sunny_hours([dp1, dp2])
    assert hours == 2  # (3600 + 1800) / 3600 = 1.5 → round(1.5) = 2

def test_calculate_sunny_hours_high_elevation_fallback():
    """High elevation fallback uses effective cloud."""
    dp = ForecastDataPoint(
        ts=datetime.now(),
        cloud_total_pct=60,  # Would be cloudy
        cloud_mid_pct=20,    # But mid+high are clear
        cloud_high_pct=10,
    )
    hours = WeatherMetricsService.calculate_sunny_hours([dp], elevation_m=2600)
    assert hours == 1  # effective_cloud=15 < 30 → sunny
```

---

### Open Questions

- [x] Welche Methoden fehlen? → 3 identifiziert
- [x] Wo werden sie verwendet? → 12 Stellen in compare.py
- [x] Aus welchem Commit restoren? → 575cd6c (original implementation)
- [x] Welche Tests brauchen wir? → 4 Unit-Tests für static methods

**Keine offenen Fragen!** Alle Informationen vorhanden.

---

## Next Steps

1. `/write-spec` - Spec mit exaktem Code aus Git erstellen
2. User approval
3. `/tdd-red` - Tests schreiben (sollten fehlschlagen)
4. `/implement` - Methods restoren
5. `/validate` - E2E-Test: Subscription E-Mail mit Daten

---

**Analysis Status:** ✅ Complete
**Ready for:** Spec Phase
