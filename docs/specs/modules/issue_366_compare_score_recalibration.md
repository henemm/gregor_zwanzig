---
entity_id: issue_366_compare_score_recalibration
type: module
created: 2026-05-25
updated: 2026-05-25
status: draft
version: "1.0"
tags: [compare, scoring, sunshine, weather, calibration]
---

# Compare-Score Sonnenstunden-Neukalibrierung (#366)

## Approval

- [x] Approved (2026-05-25)

## Purpose

Nach dem Sonnenstunden-Fix #347 liefert `calculate_sunny_hours()` reale Werte
(vorher de-facto konstant `0`). Die hartcodierten Sonnen-Schwellen im Compare-Scoring
sind dadurch entwertet: An jedem klaren Tag wird die oberste Bonus-Stufe erreicht, weil
`sunny_hours` faktisch gleich der Fensterlänge ist. Diese Neukalibrierung stellt die
Differenzierung wieder her, indem der Sonnen-Bonus auf den **Sonnen-Anteil am Zeitfenster**
umgestellt wird — robust gegen das pro Abo frei wählbare Zeitfenster.

## Scope

- **Betroffen:** Compare-E-Mail-Abos (Scheduler), Python-Engine.
- **NICHT betroffen:** Interaktiver Frontend-Vergleich (`/api/compare/run`, Go-Engine,
  relative DNI-Normalisierung) — eigene Logik, kein `sunny_hours`.

## Source

- **File:** `src/services/comparison_scoring.py`
- **Identifier:** `calculate_score`, `_score_wintersport`, `_score_wandern`, `_score_allgemein`
- **File:** `src/services/comparison_engine.py`
- **Identifier:** `ComparisonEngine.run` (Aufruf von `calculate_score`)

**Schicht:** Python-Backend (`src/services/`). Verifiziert per grep — die Go-Engine
(`internal/compare/scoring.go`) ist eine separate Code-Schicht und ausdrücklich out of scope.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `WeatherMetricsService.calculate_sunny_hours` | function | Liefert `sunny_hours` (Summe über Fenster, #347) |
| `ComparisonEngine.run` | method | Kennt `time_window`, leitet `window_hours` ab und übergibt es |
| `compare_subscription.run_comparison_for_subscription` | function | Konsument der Scores (Abo-Mails) |
| `app.profile.ActivityProfile` | enum | Profil-Dispatch (WINTERSPORT/WANDERN/ALLGEMEIN) |

## Implementation Details

### Signatur-Erweiterung (abwärtskompatibel)

```python
def calculate_score(
    metrics: Dict[str, Any],
    profile: Optional["ActivityProfile"] = None,
    window_hours: Optional[float] = None,   # NEU
) -> int:
```

`window_hours` wird an die drei privaten Scorer durchgereicht.

### Sonnen-Anteil

In jedem Scorer wird der Sonnen-Block umgestellt:

```
sunny_hours = metrics.get("sunny_hours")
if sunny_hours is not None:
    if window_hours and window_hours > 0:
        fraction = max(0.0, min(1.0, sunny_hours / window_hours))
        # anteilige Schwellen (siehe Tabelle)
    else:
        # window_hours None/<=0 -> bisherige Absolut-Schwellen (unverändert)
```

### Anteils-Schwellen (window_hours gesetzt)

| Profil | ≥ Stufe 1 → Bonus | ≥ Stufe 2 → Bonus | ≥ Stufe 3 → Bonus |
|--------|-------------------|-------------------|-------------------|
| WINTERSPORT | 0.70 → +15 | 0.50 → +10 | 0.25 → +5 |
| WANDERN     | 0.70 → +20 | 0.50 → +12 | 0.30 → +5 |
| ALLGEMEIN   | 0.65 → +15 | 0.45 → +8  | 0.25 → +4 |

Bonus-Beträge bleiben identisch zu vorher; nur die Bedingung (Stunden → Anteil) ändert sich.

### Absolut-Fallback (window_hours None/<=0)

Bisherige Schwellen bleiben byte-gleich erhalten (Legacy-Aufrufer
`comparison_engine.py:445`, `api/routers/compare.py`, Bestands-Tests ohne `window_hours`):
WINTERSPORT 6/4/2, WANDERN 7/5/3, ALLGEMEIN 6/4/2.

### Engine-Verkabelung

`comparison_engine.py` nach `start_hour, end_hour = time_window`:
```python
window_hours = end_hour - start_hour + 1
...
score = calculate_score(metrics, profile=effective_profile, window_hours=window_hours)
```
Der zweite Aufruf (`comparison_engine.py:445`, ohne Zeitfenster) bleibt ohne `window_hours`.

## Expected Behavior

- **Input:** `metrics` (inkl. `sunny_hours`), `profile`, optional `window_hours`.
- **Output:** Integer-Score 0–100 (Clamp unverändert).
- **Side effects:** Keine. Reine Pure-Function-Änderung. Keine Persistenz-/API-Änderung.

## Acceptance Criteria

- **AC-1:** Given ein vollständig sonniges Zeitfenster (`sunny_hours == window_hours`) und Profil WANDERN / When `calculate_score` mit `window_hours` aufgerufen wird / Then wird die oberste Sonnen-Stufe (+20) angewendet (Anteil ≥ 0.70).
  - Test: (populated after /tdd-red)

- **AC-2:** Given derselbe Sonnen-Anteil (z. B. 0.5) bei zwei verschiedenen Fensterlängen (8 h und 14 h) / When beide mit passendem `window_hours` gescort werden / Then ist der vergebene Sonnen-Bonus in beiden Fällen identisch (keine Fensterlängen-Abhängigkeit).
  - Test: (populated after /tdd-red)

- **AC-3:** Given ein teils sonniger Tag (Anteil 0.40) gegen einen sehr sonnigen Tag (Anteil 0.85) bei gleichem Fenster und Profil WANDERN / When beide gescort werden / Then erhält der sehr sonnige Tag einen strikt höheren Sonnen-Bonus (Differenzierung wiederhergestellt).
  - Test: (populated after /tdd-red)

- **AC-4:** Given `calculate_score` ohne `window_hours` (Legacy-Aufrufer + Bestands-Tests) / When mit denselben `metrics` wie bisher aufgerufen / Then ist das Ergebnis byte-gleich zum bisherigen Absolut-Schwellen-Verhalten (keine Regression).
  - Test: (populated after /tdd-red)

- **AC-5:** Given ein Compare-Lauf mit `time_window=(start, end)` / When `ComparisonEngine.run` die Scores berechnet / Then erhält `calculate_score` `window_hours = end - start + 1`.
  - Test: (populated after /tdd-red)

- **AC-6:** Given ein Ort ohne DNI (Geosphere-Cloud-Fallback) über ein Zeitfenster / When mit `window_hours` gescort wird / Then greifen dieselben Anteils-Schwellen wie im DNI-Fall (identische Normierung, da gleiche Einheit und Fensterlänge).
  - Test: (populated after /tdd-red)

- **AC-7:** Given alle drei Profile mit identischem Sonnen-Anteil 0.60 und `window_hours` / When gescort wird / Then liegt der Anteil bei WANDERN/WINTERSPORT in Stufe 2 (≥0.50) und bei ALLGEMEIN ebenfalls in Stufe 2 (≥0.45) — konsistente Stufung über die Profile.
  - Test: (populated after /tdd-red)

## Known Limitations

- Bei einem vollständig klaren Tag erreichen alle Orte (korrekt) die oberste Stufe — die Differenzierung wirkt erst bei teils bewölkten Tagen. Das ist gewolltes Verhalten.
- Der Absolut-Fallback (window_hours None) behält die alten, gegen `0` kalibrierten Schwellen — bewusst akzeptiert, da diese Pfade keine maßgeblichen Compare-Abo-Scores liefern.
- Die konkreten Anteils-Schwellen sind eine begründete Erst-Kalibrierung gegen reale DNI-Verteilungen (Open-Meteo, Mai 2026); Feinjustierung bei späteren Beobachtungen bleibt möglich.

## Changelog

- 2026-05-25: Initial spec created (#366)
