---
entity_id: issue_347_sunshine_hours
type: bugfix
created: 2026-05-24
updated: 2026-05-24
status: draft
version: "1.0"
tags: [bugfix, weather-metrics, sunshine-hours, dni, open-meteo, geosphere, trip-report, compare, issue-347]
---

<!-- Issue #347 — Sonnenstunden-Berechnung: toter DNI-Pfad + binärer Cloud-Schnitt → DNI-Interpolation + proportionaler Fallback -->

# Issue #347 — Bug-Fix: Sonnenstunden-Berechnung per DNI-Interpolation (WMO-konform)

## Approval

- [ ] Approved

## Zweck

`WeatherMetricsService.calculate_sunny_hours()` hat zwei strukturelle Defekte: der primäre
Berechnungspfad ist toter Code (Feld `sunshine_duration_s` existiert nicht im Datenmodell),
und der einzig aktive Fallback greift nur ab 2500 m Höhe mit einem binären 30 %-Cloud-Cutoff.
Folge: Lagen unter 2500 m liefern immer 0 Sonnenstunden, Lagen ab 2500 m ignorieren
anteilige Bewölkung (45 % Wolken → 0 h, obwohl real Sonne scheint). Der Fix nutzt das
bereits befüllte Feld `dp.dni_wm2` für eine WMO-konforme lineare Interpolation, ergänzt
einen proportionalen Cloud-Fallback für Provider ohne DNI (Geosphere), und vereinheitlicht
die angezeigte Größe in Trip-Summary und Ortsvergleich auf Sonnenstunden (h) statt DNI (W/m²).

## Quelle / Source

- **Datei:** `src/services/weather_metrics.py` — Klasse `WeatherMetricsService`, Methode `calculate_sunny_hours()` (Z. 245–295); Konstanten Z. 208–209
- **Datei:** `src/app/config.py` — Pydantic-`Settings`-Klasse (neue Felder)
- **Datei:** `src/services/comparison_engine.py` — Aufrufe von `calculate_sunny_hours()` (Z. 141, 429)
- **Datei:** `src/app/metric_catalog.py` — Metrik-Definition `sunshine` (Z. 268–276)
- **Datei:** `src/formatters/trip_report.py` — Summary-Rendering Sonnenschein (Z. 686–696)
- **Datei:** `tests/unit/test_weather_metrics_legacy.py` — bestehende Tests mit veralteter 0-h-Erwartung

> **Schicht-Hinweis:** Alle Änderungen liegen ausschließlich im Python-Backend-Layer
> (`src/services/`, `src/app/`, `src/formatters/`). Go-API und Frontend sind nicht betroffen.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `ForecastDataPoint.dni_wm2` | Python-Dataclass-Feld | Primärquelle; Direct Normal Irradiance in W/m²; wird von Open-Meteo-Provider befüllt |
| `ForecastDataPoint.cloud_total_pct` | Python-Dataclass-Feld | Cloud-Fallback-Quelle für Provider ohne DNI (Geosphere) |
| `calculate_effective_cloud()` | interne Methode | Höhenlogik „über tiefen Wolken" (≥ 2500 m nur mid/high-Clouds); bleibt unverändert; liefert effektive Bewölkung für Cloud-Fallback |
| `src/app/config.py` — Pydantic `Settings` | Python-Modul | Konfigurationsquelle für DNI-Schwellen und Cloud-Threshold; GZ_-Prefix, Env-Override möglich |
| `src/services/comparison_engine.py` | Python-Service | Ruft `calculate_sunny_hours()` auf; erhält `settings`-Parameter weitergereicht |
| `src/services/comparison_scoring.py` | Python-Service | Score-Boni für Sonnenstunden (≥7/≥5/≥3 h); Schwellen nach Fix auf Plausibilität zu prüfen |
| `src/app/metric_catalog.py` | Python-Modul | Definiert Metrik `sunshine`; muss von DNI-Mittelwert auf Sonnenstunden-Float umgestellt werden |
| `src/formatters/trip_report.py` | Python-Modul | Rendert Trip-Summary-Zeile „Sonnenschein"; muss `sunny_hours`-Float statt DNI-W/m² anzeigen |
| `tests/unit/test_weather_metrics_legacy.py` | Test-Datei | Bestehende Tests mit 0-h-Erwartung; müssen an neues Verhalten angepasst werden |

## Implementation Details

### 1. `calculate_sunny_hours()` — neue Logik

**Signatur:**
```python
def calculate_sunny_hours(
    self,
    data: list[ForecastDataPoint],
    elevation_m: float | None = None,
    settings: Settings | None = None,
) -> float:
```

`settings=None` bedeutet: Defaults aus `Settings()`-Konstruktor verwenden.

**DNI-Hauptweg (Open-Meteo und alle Provider mit befülltem `dni_wm2`):**
```
für jede Stunde dp:
    wenn dp.dni_wm2 is None → 0,0 h Beitrag (→ Cloud-Fallback, s. u.)
    wenn dp.dni_wm2 >= max (Default 180) → +1,0 h
    wenn dp.dni_wm2 <= min (Default 60)  → +0,0 h
    sonst → +(dp.dni_wm2 - min) / (max - min) h  [lineare Interpolation]
```

**Cloud-Fallback (nur wenn `dp.dni_wm2 is None` für diese Stunde):**
```
eff_cloud = calculate_effective_cloud(dp, elevation_m)  # existierende Methode
beitrag = (100 - eff_cloud) / 100  # proportional, kein binärer Cutoff
```

`calculate_effective_cloud()` (Höhenlogik, ≥ 2500 m → nur mid/high) bleibt byte-gleich.

**Rückgabe:**
```python
return round(total_hours, 1)  # Float, 1 Dezimalstelle
```

Der bisherige `max(api_hours, spec_hours)`-Hack entfällt ersatzlos — er war ausschließlich
Workaround für den toten `sunshine_duration_s`-Pfad.

### 2. `src/app/config.py` — neue Settings-Felder

```python
class Settings(BaseSettings):
    # ... bestehende Felder ...
    sunny_dni_min_wm2: int = Field(default=60, ge=0, le=500)
    sunny_dni_max_wm2: int = Field(default=180, ge=0, le=1000)
    sunny_cloud_threshold_pct: int = Field(default=30, ge=0, le=100)
    # GZ_SUNNY_DNI_MIN_WM2, GZ_SUNNY_DNI_MAX_WM2, GZ_SUNNY_CLOUD_THRESHOLD_PCT
```

`sunny_cloud_threshold_pct` wird vorerst als Konfigurationsfeld angelegt (Binär-Cutoff ist
entfernt), bleibt aber für spätere Nutzung (z. B. Cloud-Methode-Switch) im Modell erhalten.

### 3. `src/services/comparison_engine.py` — `settings` weiterreichen

An beiden Aufrufstellen (Z. 141, 429):
```python
sunny = metrics_service.calculate_sunny_hours(
    data, elevation_m=location.elevation_m, settings=self.settings
)
```

`self.settings` wird aus dem bestehenden Dependency-Injection-Pattern entnommen
(analog zu anderen Service-Instanzen in comparison_engine.py).

### 4. `src/app/metric_catalog.py` — Metrik `sunshine` umstellen

Metrik-Definition von `dp_field="dni_wm2"` (W/m²-Aggregation) auf Sonnenstunden-Float
(`sunny_hours`-Schlüssel aus dem Metrics-Dict). Einheit im Katalog: `"h"` statt `"W/m²"`.
`default_aggregations` auf `("sum",)` statt `("avg",)` (Stundensumme ist sinnvoller als
DNI-Mittelwert). DNI-W/m² bleibt intern als separates Feld erhalten (Emoji-Logik nutzt es).

### 5. `src/formatters/trip_report.py` — Rendering Z. 686–696

Summary-Zeile liest künftig `sunny_hours` (Float, h) statt `dni_wm2` (W/m²).
Formatierung: `f"{val:.1f} h"` (z. B. `"3.5 h"`). Bestehende Emoji-Logik (DNI-basiert)
bleibt unverändert — sie zieht weiterhin aus `dp.dni_wm2` direkt.

### 6. `tests/unit/test_weather_metrics_legacy.py` — Anpassung

Alle Tests, die aktuell `0` Sonnenstunden erwarten (Lagen unter 2500 m mit befülltem
`dni_wm2`), werden auf realistische Werte basierend auf Fixture-Daten umgestellt.
Keine neuen Mocks — echte `ForecastDataPoint`-Instanzen mit gesetztem `dni_wm2` verwenden.
Neue Test-Fälle: DNI-Interpolation bei 45 % Bewölkung, Geosphere-Fallback, Konfigurierbarkeit.

### LoC-Budget

| Datei | Δ LoC | Zählt |
|-------|--------|-------|
| `src/services/weather_metrics.py` | ~30 | ja |
| `src/app/config.py` | ~10 | ja |
| `src/services/comparison_engine.py` | ~5 | ja |
| `src/app/metric_catalog.py` | ~15 | ja |
| `src/formatters/trip_report.py` | ~15 | ja |
| `tests/unit/test_weather_metrics_legacy.py` | ~40 | ja |
| **Gesamt (zählend)** | **~115** | **< 250 LoC-Limit** |

## Expected Behavior

- **Input:** Liste von `ForecastDataPoint`-Objekten mit `dni_wm2` (befüllt bei Open-Meteo)
  oder `cloud_total_pct` (Geosphere), optionale Höhenangabe `elevation_m`, optionales
  `Settings`-Objekt
- **Output:** `float` (≥ 0,0), gerundet auf 1 Dezimalstelle — Anzahl Sonnenstunden im
  übergebenen Datenfenster
- **Nebeneffekte:**
  - Trip-Summary zeigt Sonnenstunden (h) statt DNI-Mittelwert (W/m²)
  - Ortsvergleich (Compare) und Trip-Summary verwenden dieselbe Größe und Einheit
  - `comparison_scoring.py`-Schwellen (≥7/≥5/≥3 h) werden mit realistischen Werten
    konfrontiert; Plausibilisierung erfolgt im selben Workflow (kein Umbau, nur Prüfung)
  - Kein neuer Open-Meteo-API-Parameter (Daten-Governance #338 unberührt)

## Acceptance Criteria

- **AC-1:** Given ein `ForecastDataPoint` mit `dni_wm2 = 90` (zwischen 60 und 180 W/m²) und 45 % Bewölkung / When `calculate_sunny_hours([dp])` aufgerufen wird / Then ist der Rückgabewert `> 0,0` und `< 1,0` — die Stunde trägt einen Bruchwert bei, nicht 0 (Kern-Bug behoben)
  - Test: (populated after /tdd-red)

- **AC-2:** Given ein `ForecastDataPoint` mit `dni_wm2 >= 180` (Default-Maximum) / When `calculate_sunny_hours([dp])` aufgerufen wird / Then ist der Rückgabewert `1,0` (volle Sonnenstunde)
  - Test: (populated after /tdd-red)

- **AC-3:** Given ein `ForecastDataPoint` mit `dni_wm2 <= 60` (Default-Minimum) oder `dni_wm2 = None` ohne Cloud-Fallback / When `calculate_sunny_hours([dp])` aufgerufen wird / Then ist der Rückgabewert `0,0`
  - Test: (populated after /tdd-red)

- **AC-4:** Given eine Lage unter 2500 m Höhe mit `ForecastDataPoint.dni_wm2 = 150` (sonnige Stunde) / When `calculate_sunny_hours([dp], elevation_m=800)` aufgerufen wird / Then ist der Rückgabewert `> 0,0` (vorher war das Ergebnis konstant `0` — Regression ausgeschlossen)
  - Test: (populated after /tdd-red)

- **AC-5:** Given ein `ForecastDataPoint` mit `dni_wm2 = None` (Geosphere-Datenpunkt ohne DNI) und `cloud_total_pct = 40` / When `calculate_sunny_hours([dp])` aufgerufen wird / Then ist der Rückgabewert `round((100 - 40) / 100, 1) = 0,6` — proportionaler Fallback, kein binärer 30 %-Cutoff
  - Test: (populated after /tdd-red)

- **AC-6:** Given ein `Settings`-Objekt mit `sunny_dni_min_wm2=100, sunny_dni_max_wm2=200` und ein Datenpunkt mit `dni_wm2=150` / When `calculate_sunny_hours([dp], settings=custom_settings)` aufgerufen wird / Then ist der Rückgabewert `0,5` (lineare Mitte des angepassten Bandes) — Konfigurierbarkeit nachweisbar
  - Test: (populated after /tdd-red)

- **AC-7:** Given `calculate_sunny_hours([dp])` ohne `settings`-Argument / When aufgerufen / Then gelten die Defaults `60/180 W/m²` ohne Fehler (kein `AttributeError`, kein `TypeError`)
  - Test: (populated after /tdd-red)

- **AC-8:** Given ein Trip mit mehreren Etappen / When die Trip-Summary gerendert wird / Then zeigt die „Sonnenschein"-Zeile einen Wert in `h` (z. B. `3.5 h`) — identische Einheit wie im Ortsvergleich (kein W/m²-Wert mehr in der Summary)
  - Test: (populated after /tdd-red)

- **AC-9:** Given dieselbe Lage wird in `compare` (Ortsvergleich) und in der Trip-Summary ausgewertet / When `sunny_hours` in beiden Pfaden berechnet wird / Then stammt der Wert in beiden Fällen aus `calculate_sunny_hours()` mit denselben Eingangsparametern und derselben Einheit (keine Größen-Inkongruenz mehr)
  - Test: (populated after /tdd-red)

## Test-Strategie

**Keine Mocks** (Projekt-Regel). Tests verwenden:

- **Echte `ForecastDataPoint`-Instanzen** mit gesetzten Feldern (`dni_wm2`,
  `cloud_total_pct`) für Unit-Tests der Berechnungslogik.
- **Fixture-Provider (#263)** für Integrations-Tests gegen gespeicherte Open-Meteo-
  und Geosphere-Datensätze (Innsbruck, Stubai, Zillertal).

**Bestehende Tests** in `tests/unit/test_weather_metrics_legacy.py`, die aktuell
`0` Sonnenstunden erwarten, müssen auf realistische Werte umgestellt werden —
die Erwartung `0` war durch den Defekt erzwungen, nicht korrekt.

**Neue Test-Schwerpunkte:**
1. DNI-Interpolation: Bruchwerte zwischen 0 und 1 (Kern-Bug AC-1)
2. Grenzwerte: `dni >= max`, `dni <= min`, `dni = None`
3. Höhenunabhängigkeit: Lagen unter 2500 m liefern jetzt > 0 bei Sonne (AC-4)
4. Provider-Asymmetrie: Geosphere-Pfad (Cloud-Proportional, AC-5)
5. Konfigurierbarkeit: anderes DNI-Band, nachweisbare Ergebnisänderung (AC-6, AC-7)
6. Konsistenz-Prüfung: Trip-Summary vs. Compare-Ausgabe (AC-8, AC-9)

## Risiken

- **Score-Drift im Ortsvergleich (Priorität: hoch):** `comparison_scoring.py`-Schwellen
  (`≥7/≥5/≥3 h` → +20/+12/+5 Punkte) wurden kalibriert als `sunny_hours` de facto immer
  0 war. Echte, positive Werte verschieben Rankings aller Standorte im Vergleich. Im selben
  Workflow wird geprüft, ob Schwellen plausibel bleiben — eine Neukalibrierung ist
  `Out of Scope` dieses Bugfix, wird aber als Folgemaßnahme dokumentiert.

- **Provider-Asymmetrie:** Open-Meteo (DNI-Methode) liefert systematisch etwas andere
  Werte als Geosphere (Cloud-Methode) bei derselben Lage. Kein Blocker; im Rendering
  transparent machen ist optional (ggf. Folge-Issue).

- **Float statt Int an Anzeige-Stellen:** `comparison_renderers.py:226` und weitere
  Format-Stellen erwarten möglicherweise `int`. Alle `int()`-Casts auf `sunny_hours`
  müssen gesucht und auf `f"{val:.1f}"` umgestellt werden.

- **Daten-Governance #338:** Kein neuer Open-Meteo-Parameter wird abgerufen
  (`dni_wm2` ist bereits in der Parameterliste). Unkritisch.

## Out of Scope

- Neukalibrierung der Compare-Score-Schwellen in `comparison_scoring.py`: Die Schwellen
  werden im selben Workflow auf Plausibilität geprüft, aber nicht als eigenes Feature
  umgebaut. Falls Anpassungsbedarf besteht, wird ein separates GitHub-Issue eröffnet.
- Abruf von `sunshine_duration` (Sekunden) als neuer Open-Meteo-Parameter.
- Ensemble-Methoden oder probabilistische Sonnenstunden-Prognosen.
- Geosphere-seitiger DNI-Abruf (Geosphere stellt DNI nicht bereit).
- Frontend-Darstellungsänderungen über das reine Einheitslabel (h) hinaus.

## Changelog

- 2026-05-24: Initial Spec erstellt. Behebt toten `sunshine_duration_s`-Pfad und binären
  30 %-Cloud-Cutoff in `calculate_sunny_hours()`. DNI-Interpolation (60–180 W/m²,
  WMO-konform) als Hauptweg; proportionaler Cloud-Fallback für Geosphere. Float-Rückgabe.
  3 neue Settings-Felder in `config.py`. Trip-Summary auf Sonnenstunden (h) umgestellt,
  konsistent mit Ortsvergleich. 6 Dateien, ~115 LoC.
