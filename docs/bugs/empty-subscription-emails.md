## Bug: Subscription E-Mails sind leer (Score=0, keine Daten)

**Datum:** 2026-02-03
**Entdeckt:** User-Report
**Status:** Analysiert - bereit zur Behebung

---

### 1. Symptome

**Was passiert:**
- Subscription E-Mails (18:00 daily_evening) werden versendet
- E-Mail enthält Template aber KEINE Wetterdaten
- Alle Locations zeigen: Score=0, Temp/Wind/Snow = "-"

**Wann:**
- Seit Commit `bce2991` (Feature 2.2b - Erweiterte Metriken)
- Tritt bei ALLEN Subscriptions auf
- API-Calls funktionieren korrekt (48 Datenpunkte)

**Erwartetes Verhalten:**
- E-Mail zeigt Vergleich von 4 Serfaus-Locations
- Mit Scores, Temperaturen, Wind, Schnee, etc.

---

### 2. Root Cause

**Location:** `src/services/weather_metrics.py` (Commit bce2991)

**Problem:**
Bei Refactoring von Feature 2.2b wurden **3 statische Methoden gelöscht**, die von `compare.py` verwendet werden:

1. ❌ `WeatherMetricsService.calculate_sunny_hours()` - GELÖSCHT
2. ❌ `WeatherMetricsService.calculate_effective_cloud()` - GELÖSCHT
3. ❌ `WeatherMetricsService.HIGH_ELEVATION_THRESHOLD_M` - GELÖSCHT

**Auswirkung:**
```python
# src/web/pages/compare.py:333
metrics["sunny_hours"] = WeatherMetricsService.calculate_sunny_hours(
    filtered_data, loc.elevation_m
)
# → AttributeError: 'WeatherMetricsService' has no attribute 'calculate_sunny_hours'
# → Exception wird in ComparisonEngine.run() gefangen
# → LocationResult.error gesetzt, Score bleibt 0
```

**Verwendungsstellen in compare.py:**
- Zeile 315: `calculate_effective_cloud()`
- Zeile 329: `HIGH_ELEVATION_THRESHOLD_M`
- Zeile 333: `calculate_sunny_hours()`
- Zeile 1299: `calculate_effective_cloud()` (UI path)
- Zeile 1313: `HIGH_ELEVATION_THRESHOLD_M` (UI path)
- Zeile 1317: `calculate_sunny_hours()` (UI path)

---

### 3. Warum ist das passiert?

**Refactoring-Fehler:**
- Feature 2.2b hat `WeatherMetricsService` umgebaut
- Von statischen Hilfsfunktionen zu instanz-basiertem Service
- Alte statische Methoden wurden entfernt
- **ABER:** `compare.py` verwendet sie noch (6x!)
- Keine Tests haben das gefangen (fehlende Integration-Tests)

**Git-History:**
```bash
bce2991 feat: implement Feature 2.2b - Erweiterte Metriken (Story 2)
# Entfernte:
# - @staticmethod calculate_sunny_hours()
# - @staticmethod calculate_effective_cloud()
# - HIGH_ELEVATION_THRESHOLD_M = 2500
```

---

### 4. Reproduktion

```bash
# 1. Manual test
uv run python3 << 'EOF'
import sys
sys.path.insert(0, 'src')
from web.pages.compare import ComparisonEngine, load_all_locations
from datetime import date, timedelta

locs = [l for l in load_all_locations() if 'serfaus' in l.id.lower()]
result = ComparisonEngine.run(
    locations=locs,
    time_window=(9, 16),
    target_date=date.today() + timedelta(days=1),
    forecast_hours=48
)

for r in result.locations:
    print(f"{r.location.name}: Score={r.score}, Error={r.error}")
EOF

# Erwartet: Error="'WeatherMetricsService' object has no attribute 'calculate_sunny_hours'"
```

---

### 5. Fix-Strategie

**Option 1: Restore Methods (EMPFOHLEN)**
- Stelle 3 statische Methoden in `WeatherMetricsService` wieder her
- Als `@staticmethod` für Backward Compatibility
- Mit Kommentar: "Legacy methods for compare.py compatibility"

**Option 2: Refactor compare.py**
- Ersetze alle 6 Aufrufe durch neue API
- Instanziiere `WeatherMetricsService`
- Höheres Risiko, mehr Änderungen

**Empfehlung: Option 1**
- Minimale Änderungen (1 Datei)
- Restore bekannter funktionierender Code
- Kein Breaking Change

---

### 6. Betroffene Dateien

**Zu ändern:**
- `src/services/weather_metrics.py` - 3 Methoden wiederherstellen

**Abhängig (keine Änderung nötig):**
- `src/web/pages/compare.py` - verwendet die Methoden (6x)
- `src/web/scheduler.py` - ruft Subscriptions auf

---

### 7. Test-Plan

**Nach Fix:**

1. **Unit-Test:** Methoden existieren und funktionieren
   ```python
   assert hasattr(WeatherMetricsService, 'calculate_sunny_hours')
   assert hasattr(WeatherMetricsService, 'calculate_effective_cloud')
   assert hasattr(WeatherMetricsService, 'HIGH_ELEVATION_THRESHOLD_M')
   ```

2. **Integration-Test:** ComparisonEngine liefert Daten
   ```python
   result = ComparisonEngine.run(...)
   assert all(r.score > 0 for r in result.locations if not r.error)
   assert result.locations[0].temp_min is not None
   ```

3. **E2E-Test:** Subscription E-Mail enthält Daten
   ```bash
   # Run subscription manually via UI
   # Check email via IMAP
   # Verify: Temperature/Wind/Snow values present
   ```

---

### 8. Effort

**Aufwand:** Small (1-2 Stunden)

- 1 Datei ändern
- 3 Methoden wiederherstellen (aus Git-History)
- Tests schreiben
- E2E-Validierung

---

### 9. Prevention

**Maßnahmen für Zukunft:**
1. Integration-Tests für `ComparisonEngine.run()`
2. Subscription E2E-Test als Teil der CI
3. Deprecation-Warnings statt direktes Löschen
4. Cross-reference Check vor Refactoring

---

**Erstellt von:** Claude (Bug Analysis)
**Git Blame:** Commit `bce2991` - Feature 2.2b Erweiterte Metriken
