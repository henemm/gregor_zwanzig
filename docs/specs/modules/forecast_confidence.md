---
entity_id: forecast_confidence
type: module
created: 2026-05-15
updated: 2026-05-15
status: draft
version: "1.0"
tags: [forecast, ensemble, openmeteo, risk, sms, email, dto]
---

<!-- Issue #121 — F11: Prognose-Konfidenz im Report -->

# F11: Prognose-Konfidenz (Master-Spec)

## Approval

- [ ] Approved

## Purpose

Macht für Empfänger eines Reports sichtbar, **wie sicher** eine Prognose ist — pro Stunde und pro Tag. Datenquelle ist die OpenMeteo Ensemble API (200+ Member aus 7 Modellen). Drei neue Optional-Felder im DTO, Lead-Time-gecapte Konfidenz-Berechnung, neuer Risk-Typ `LOW_CONFIDENCE`, Sicht-Anzeige als 1-Zeichen-Symbol pro Tag in SMS (`+`/`~`/`?`) und als eigene Spalte „Sicherheit" plus Klartext-Hinweis in E-Mail.

Diese **Master-Spec** umfasst das vollständige Feature. Die Umsetzung erfolgt in zwei Sub-Workflows:
- **Workflow 1 (Backend):** ACs **AC-1 bis AC-8** — Datenfelder, Provider, Aggregation, Risk-Engine
- **Workflow 2 (Output):** ACs **AC-9 bis AC-14** — Token-Builder, MetricCatalog, E-Mail-Renderer

## Source

### Workflow 1 — Backend

- **Änderung:** `src/app/models.py` — `ForecastDataPoint` (Z. 80–122): drei neue Optional-Felder
- **Änderung:** `internal/model/forecast.go` — `ForecastDataPoint` (Z. 44–75): drei Pointer-Felder mit `json:omitempty`
- **Änderung:** `src/providers/openmeteo.py` — neue Funktion `_fetch_ensemble_spread()`, Merge in `_parse_response()`, Konfidenz-Berechnung mit Lead-Time-Cap
- **Änderung:** `src/services/aggregation.py` + `src/services/trip_forecast.py` — `confidence_pct_min` in `SegmentWeatherSummary`
- **Änderung:** `src/services/risk_engine.py` — neuer `RiskType.LOW_CONFIDENCE`, `_check_confidence()`
- **Änderung:** `internal/risk/engine.go` + `internal/model/risk.go` — Go-Pendant
- **Änderung:** `docs/reference/api_contract.md` — drei neue Felder dokumentieren

### Workflow 2 — Output

- **Änderung:** `src/output/tokens/builder.py` — Symbol `"C"` zu `PRIORITY` + `POSITIONAL`, Confidence-Token im Builder-Loop
- **Änderung:** `src/app/metric_catalog.py` — neue `MetricDefinition(id="confidence", ...)` für E-Mail-Spalte
- **Änderung:** `src/output/renderers/email/html.py` + `plain.py` — Klartext-Hinweis bei `<60 %` in T+0-72h
- **Änderung:** `docs/reference/sms_format.md` — v2.0 → v2.1
- **Änderung:** `docs/reference/renderer_email_spec.md` — Spalte „Sicherheit" + Hinweis-Regel
- **Neu:** `docs/specs/modules/issue_121_confidence_output.md` — Sub-Spec, referenziert diese Master-Spec

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| OpenMeteo Ensemble API (`/v1/ensemble`) | external | Datenquelle für Ensemble-Spread |
| `ForecastDataPoint` | DTO | Trägt die drei neuen Optional-Felder |
| `SegmentWeatherSummary` | DTO | Aggregiert `confidence_pct_min` über Segment-Stunden |
| `RiskEngine` | Service | Konsumiert `confidence_pct_min`, generiert `LOW_CONFIDENCE`-Risk |
| `RiskType` Enum | Enum | Neuer Wert `LOW_CONFIDENCE` |
| `MetricCatalog` | Registry | Neue Metrik-Definition `confidence` für E-Mail-Spalten |
| Token-Builder `PRIORITY` + `POSITIONAL` | Konstanten | Confidence-Symbol einreihen |
| `sms_format.md` v2.1 | Reference | Authority für Token-Reihenfolge und Symbole |
| `httpx` | External | HTTP-Client für Ensemble-Call (bereits in Provider) |

## Implementation Details

### 1) Drei neue Optional-Felder in `ForecastDataPoint`

**Python (`src/app/models.py`, nach Z. 121):**

```python
# Forecast confidence (from ensemble spread, Issue #121)
confidence_pct: Optional[int] = None       # 0–100, lead-time-capped
spread_t2m_k: Optional[float] = None       # Ensemble σ Temperatur, in K
spread_precip_mm: Optional[float] = None   # Ensemble σ Niederschlag, in mm
```

**Go (`internal/model/forecast.go`, nach Z. 75):**

```go
ConfidencePct     *int     `json:"confidence_pct,omitempty"`
SpreadT2mK        *float64 `json:"spread_t2m_k,omitempty"`
SpreadPrecipMm    *float64 `json:"spread_precip_mm,omitempty"`
```

Alle drei Felder sind Optional/Pointer. Loader/Saver verwenden `.get(key, None)` bzw. JSON-`omitempty`. Bestehende Snapshots laden ohne Migration.

### 2) Konfidenz-Berechnung mit Lead-Time-Cap

```
raw_confidence = clamp(100 − (spread_t2m_k × 15) − (spread_precip_mm × 10), 0, 100)
confidence_pct = min(raw_confidence, lead_time_cap)
```

| Vorhersage-Horizont (Stunden ab Request-Zeit) | Cap |
|---|---|
| T+0–24 h | 95 % |
| T+24–48 h | 80 % |
| T+48–72 h | 60 % |
| T+72 h+ | 40 % |

**Berechnungsort:** im Provider (`src/providers/openmeteo.py`), nicht in der Aggregation. Der Provider kennt sowohl den Spread-Rohwert als auch die Lead-Time des Datenpunkts (Differenz zwischen `ts` und Request-Zeit). Aggregation und Risk-Engine konsumieren den fertigen `confidence_pct`-Wert.

**Cap-Erzwingung:** Der Cap wirkt auch bei Spread = 0. Test: `spread_t2m_k=0, spread_precip_mm=0` für einen T+96h-Datenpunkt ⇒ `confidence_pct == 40`, nicht 100.

### 3) OpenMeteo Ensemble-Call

**Endpoint:** `https://ensemble-api.open-meteo.com/v1/ensemble` (separater Host vom Haupt-Forecast)

**Parameter:**
- `latitude`, `longitude`
- `hourly=temperature_2m,precipitation`
- `models=icon_seamless,gfs_seamless,ecmwf_ifs04` (oder regional ausgewählte Familie)
- `forecast_days=7`

**Response-Verarbeitung:**
- Pro Stunde liefert die API ein Array von Member-Werten (z.B. 51 Member bei ECMWF IFS).
- `spread_t2m_k = stdev([m.temp for m in members if m is not None])`
- `spread_precip_mm = stdev([m.precip for m in members if m is not None])`
- Bei < 5 verwertbaren Membern: Felder bleiben `None` (Fallback ohne Fehler).

**Integration in `_parse_response()`:** Nach dem regulären Forecast-Parse wird der Ensemble-Call ausgeführt, die Werte werden per `ts`-Match in die bereits gebauten `ForecastDataPoint`-Objekte einsortiert. Bei Ensemble-Call-Fehler (HTTP 5xx, Timeout): Forecast wird trotzdem zurückgegeben, alle drei Felder bleiben `None`.

### 4) Aggregation in `SegmentWeatherSummary`

**Neues Feld in `SegmentWeatherSummary` (`src/services/trip_forecast.py` Z. 311+):**

```python
confidence_pct_min: Optional[int] = None  # Min. Konfidenz über alle Stunden im Segment
```

**Aggregations-Logik in `aggregate()` (`src/services/aggregation.py`):**

```python
confidences = [dp.confidence_pct for dp in all_points if dp.confidence_pct is not None]
summary.confidence_pct_min = min(confidences) if confidences else None
```

Worst-Case-Aggregation: Wenn auch nur eine Stunde im Segment unsicher ist, ist das Segment unsicher.

### 5) Neuer Risk-Typ `LOW_CONFIDENCE`

**Erweiterung von `RiskType` (`src/app/models.py` Z. 186):**

```python
LOW_CONFIDENCE = "low_confidence"
```

**Erweiterung von `RiskEngine.assess_segment()` (`src/services/risk_engine.py`):**

```python
def _check_confidence(self, agg: SegmentWeatherSummary, risks: list[Risk]) -> None:
    """
    Fires LOW_CONFIDENCE risk if confidence < 40% AND segment already has
    a high-risk weather event (THUNDERSTORM, WIND, RAIN with level HIGH).
    """
    if agg.confidence_pct_min is None or agg.confidence_pct_min >= 40:
        return
    high_risk_present = any(
        r.type in (RiskType.THUNDERSTORM, RiskType.WIND, RiskType.RAIN)
        and r.level == RiskLevel.HIGH
        for r in risks
    )
    if high_risk_present:
        risks.append(Risk(type=RiskType.LOW_CONFIDENCE, level=RiskLevel.MODERATE))
```

**Trigger-Definition:** `LOW_CONFIDENCE` feuert **nur**, wenn (a) `confidence_pct_min < 40` UND (b) im selben Segment bereits ein `Risk` mit `RiskType ∈ {THUNDERSTORM, WIND, RAIN}` und `Level == HIGH` existiert. Sonst entsteht Doppel-Alarm bei stabilem schlechtem Wetter.

**Go-Pendant in `internal/risk/engine.go` + `internal/model/risk.go`:** Analoge `RiskLowConfidence` Konstante + `checkConfidence()` Funktion.

### 6) SMS-Symbol pro Tag (Workflow 2)

**Symbol-Mapping:**

| `confidence_pct_min` (Tag) | Symbol |
|---|---|
| ≥ 75 | `+` |
| 50–74 | `~` |
| < 50 | `?` |
| `None` | (kein Symbol) |

**Builder-Integration (`src/output/tokens/builder.py`):**

- `PRIORITY["C"] = 4` (höhere Priorität als Temperatur/Regen, niedriger als Gewitter/Vigilance)
- `POSITIONAL`-Liste um `("C", "confidence")` ergänzt — Position nach Wind/Gust, vor Gewitter-Tokens
- Im Builder-Loop pro Tag: `if day.confidence_pct_min is not None: tokens.append(Token(symbol="C", value=_symbol_for(day.confidence_pct_min)))`

**SMS-Format-Spec (`docs/reference/sms_format.md` → v2.1):** Symbole `+`, `~`, `?` werden formal als Konfidenz-Indikatoren reserviert. Kollisions-Check mit bestehenden Tokens: keine.

### 7) E-Mail-Spalte „Sicherheit" + Klartext-Hinweis (Workflow 2)

**MetricCatalog-Eintrag (`src/app/metric_catalog.py`):**

```python
MetricDefinition(
    id="confidence",
    label_de="Sicherheit",
    col_key="confidence",
    col_label="Sicherheit",
    dp_field="confidence_pct",
    unit="%",
    visible_default=True,
)
```

→ HTML- und Plain-Renderer ziehen die Spalte automatisch über `visible_cols()` (bestehender Mechanismus).

**Klartext-Hinweis:**

Im E-Mail-Body wird ein Klartext-Hinweis eingefügt, wenn `confidence_pct_min < 60` für mindestens einen Tag innerhalb der ersten 72 Stunden ab `now`. Bei Konfidenz ≥ 60 in T+0-72h: kein Hinweis.

Beispiel-Wortlaut:
> Bis morgen ist die Prognose verlässlich. Ab Mittwoch nimmt die Unsicherheit zu (Temperatur-Spreizung 8 °C).

Das Datum („Mittwoch") wird aus dem ersten unsicheren Tag berechnet, der Wert `8 °C` aus dem höchsten `spread_t2m_k`-Wert dieses Tages.

### 8) OpenMeteo Attribution

OpenMeteo Ensemble-Daten sind CC-BY 4.0. Im E-Mail-Footer und in den Debug-Buffer-Logs wird die Attribution `Daten: Open-Meteo.com (CC-BY 4.0)` hinzugefügt, falls noch nicht vorhanden.

## Acceptance Criteria

### Workflow 1 — Backend

- **AC-1:** Given `ForecastDataPoint` (Python) / When ein bestehender JSON-Snapshot ohne `confidence_pct`, `spread_t2m_k`, `spread_precip_mm` geladen wird / Then lädt das DTO ohne Fehler, alle drei Felder sind `None`, keine Schema-Migration nötig
  - Test: (populated after /tdd-red)

- **AC-2:** Given `ForecastDataPoint` (Go) / When ein JSON ohne die drei Felder unmarshalled wird / Then sind `ConfidencePct`, `SpreadT2mK`, `SpreadPrecipMm` `nil`, kein Marshal-Fehler
  - Test: (populated after /tdd-red)

- **AC-3:** Given OpenMeteo Ensemble-Call für Salzburg (lat=47.8, lon=13.0) für T+0-168h / When `_fetch_ensemble_spread()` läuft / Then liefern mindestens 90 % der stündlichen Datenpunkte ein `spread_t2m_k`, und `confidence_pct` ist für jeden Punkt mit Spread-Wert berechnet
  - Test: (populated after /tdd-red)

- **AC-4:** Given ein Datenpunkt mit `spread_t2m_k=0, spread_precip_mm=0` bei T+96h / When `confidence_pct` berechnet wird / Then ist das Ergebnis genau `40` (Lead-Time-Cap), nicht `100`
  - Test: (populated after /tdd-red)

- **AC-5:** Given ein Datenpunkt mit `spread_t2m_k=2.0, spread_precip_mm=1.0` bei T+12h / When `confidence_pct` berechnet wird / Then ist das Ergebnis `min(100 - 30 - 10, 95) = 60`
  - Test: (populated after /tdd-red)

- **AC-6:** Given OpenMeteo Ensemble-API antwortet mit HTTP 503 / When `fetch_forecast()` läuft / Then wird der reguläre Forecast trotzdem geliefert, alle drei Konfidenz-Felder sind `None`, kein Exception nach außen
  - Test: (populated after /tdd-red)

- **AC-7:** Given ein Segment mit 5 Stunden, `confidence_pct = [90, 80, 30, 75, 80]` / When `aggregate()` läuft / Then ist `summary.confidence_pct_min == 30`
  - Test: (populated after /tdd-red)

- **AC-8:** Given ein Segment mit `confidence_pct_min=25` UND einem bereits gefeuerten `Risk(THUNDERSTORM, HIGH)` / When `RiskEngine.assess_segment()` läuft / Then enthält das Result ein zusätzliches `Risk(LOW_CONFIDENCE, MODERATE)`. Given dasselbe Segment ohne High-Risk-Event / When dieselbe Assessment läuft / Then **kein** `LOW_CONFIDENCE`-Risk
  - Test: (populated after /tdd-red)

### Workflow 2 — Output

- **AC-9:** Given ein `DailyForecast` mit `confidence_pct_min=80` / When der Token-Builder läuft / Then enthält die SMS-Token-Liste einen Token `(symbol="C", value="+")`. Bei `confidence_pct_min=60` → `"~"`. Bei `confidence_pct_min=35` → `"?"`. Bei `confidence_pct_min=None` → kein C-Token
  - Test: (populated after /tdd-red)

- **AC-10:** Given eine SMS mit Konfidenz-Tokens für einen 7-Tage-Trip / When die finale SMS-Zeichenkette gebildet wird / Then bleibt die Länge ≤ 160 Zeichen (GSM-7), Tokens werden nach `PRIORITY` getrunkt falls nötig
  - Test: (populated after /tdd-red)

- **AC-11:** Given ein E-Mail-Report mit Tabelle / When HTML- und Plain-Renderer laufen / Then enthält die Tabelle eine Spalte `Sicherheit` mit `%`-Werten je Stunde, automatisch durch `visible_cols(MetricCatalog)` eingefügt
  - Test: (populated after /tdd-red)

- **AC-12:** Given ein 5-Tage-Trip mit `confidence_pct_min` an Tag 3 (Mittwoch) = `45` (alle anderen Tage ≥ 80) / When die E-Mail gebaut wird / Then enthält der Body den Klartext-Hinweis mit Wochentagsbezug („Mittwoch") und einer Spread-Angabe in °C
  - Test: (populated after /tdd-red)

- **AC-13:** Given ein Trip mit `confidence_pct_min ≥ 60` für alle Tage in T+0-72h / When die E-Mail gebaut wird / Then enthält der Body **keinen** Klartext-Hinweis (Visual Noise vermeiden)
  - Test: (populated after /tdd-red)

- **AC-14:** Given ein echtes Gmail-E2E-Setup (`TestRealGmailE2E`) / When eine E-Mail mit Konfidenz-Daten gesendet wird / Then bestätigt der IMAP-Roundtrip den Empfang, das HTML enthält die Spalte „Sicherheit" und (bei niedriger Konfidenz) den Klartext-Hinweis, und `email_spec_validator.py` liefert Exit 0
  - Test: (populated after /tdd-red)

## Expected Behavior

- **Input:** OpenMeteo Forecast-Request (Location, Datum, Lead-Time)
- **Output:**
  - `NormalizedTimeseries` mit `ForecastDataPoint`-Liste, jedes mit optional gesetzten Konfidenz-Feldern
  - `SegmentWeatherSummary` mit `confidence_pct_min`
  - `RiskAssessment` ggf. mit `Risk(LOW_CONFIDENCE)`
  - SMS-Zeile mit `+`/`~`/`?`-Symbol pro Tag (Workflow 2)
  - HTML-/Plain-E-Mail mit Spalte „Sicherheit" + Klartext-Hinweis bei Unsicherheit in T+0-72h (Workflow 2)
- **Side effects:** Ein zusätzlicher HTTP-Call an OpenMeteo Ensemble-API pro Forecast-Request. Bei API-Fehler: kein Crash, Konfidenz-Felder `None`.

## Known Limitations

- **Regionale Ensemble-Coverage:** OpenMeteo Ensemble deckt nicht alle Regionen mit allen Modellen ab. Für Pollença (Mittelmeer) ggf. nur ECMWF-IFS verfügbar. Bei < 5 Membern Fallback auf `None`.
- **Lead-Time-Cap statisch:** Die Cap-Werte (95/80/60/40 %) sind aus ECMWF-Skill-Score-Literatur abgeleitet, nicht dynamisch aus aktuellen Verifikations-Daten. Bei stark verbesserten Modellen müssten sie manuell angepasst werden.
- **Klartext-Hinweis nur T+0-72h:** Ein unsicherer Tag in T+96h löst keinen Hinweis aus. Begründung: ab T+72h ist Unsicherheit normal — Hinweis würde bei jedem Report erscheinen.
- **Risk-Trigger eng:** `LOW_CONFIDENCE` feuert nur in Kombination mit High-Risk-Event. Eine unsichere Sonnentag-Prognose erzeugt kein Risk — Konfidenz-Information bleibt aber in SMS-Symbol und E-Mail-Spalte sichtbar.
- **Symbol-Schwellen fix:** 75/50 als Grenzen sind heuristisch gewählt (ECMWF CRPSS-Bänder). Keine A/B-Optimierung mit echten Empfängern möglich (keine produktiven Nutzer).

## Changelog

- 2026-05-15: Initial Master-Spec für Issue #121, Workflow 1 (Backend) + Workflow 2 (Output) als getrennte Sub-Workflows mit gemeinsamer Spec
