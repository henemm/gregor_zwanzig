# Context: rework-1212-risk-r1-python-endpoint (Slice R1)

## Request Summary
Neuer Python-FastAPI-Endpoint `GET /api/_internal/trips/{id}/stages-weather`, der den heutigen
Go-Handler `StagesWeatherHandler` (GET `/api/trips/{id}/stages/weather`) fachlich nachbildet.
Ziel: Die Risiko-Bewertung der Cockpit-Kacheln kommt künftig aus dem **Python-Kern** (RiskEngine),
damit Cockpit und Briefing für identische Wetterdaten dieselbe Stufe zeigen (ADR-0015).
R1 baut nur den Python-Endpoint; R2 (separater Workflow) ersetzt den Go-Handler durch einen Proxy
und löscht `internal/risk/`.

## Related Files
| Datei | Relevanz |
|------|-----------|
| `internal/handler/stage_weather.go` | **Zu spiegelnder Vertrag** — Handler-Logik, Fail-soft, Aggregation, WMO-Dominanz, is_day, Risk-Mapping |
| `internal/model/stage_weather.go` | **Exaktes Response-Schema** (JSON-Feldnamen, Nullability) |
| `internal/router/router.go:140` | Go-Route + Auth-Middleware (Kontext für R2-Proxy) |
| `internal/risk/engine.go`, `thresholds.go` | Go-Risk-Logik (wird in R2 gelöscht) — Divergenz-Quelle |
| `internal/provider/openmeteo/models.go:50-58` | Thunder-Ableitung WMO {95,96,99}→HIGH |
| `api/routers/internal.py` | **Vorbild** für neuen `/api/_internal/`-Endpoint (user_id via Query, load_all_trips) |
| `api/main.py:44-59` | FastAPI-App, Router-Registrierung, Port 8000 |
| `src/services/risk_engine.py` | **Kern-Baustein** — `RiskEngine.assess_segment` liefert die Stufe |
| `src/services/weather_metrics.py:630` | `compute_metrics` → `SegmentWeatherSummary` aus Timeseries |
| `src/providers/openmeteo.py:757` | `fetch_forecast(location, start, end, ...)` pro Koordinate |
| `src/app/metric_catalog.py:111-347` | Schwellwerte (identisch zu Go thresholds.go) |
| `src/app/trip.py`, `src/app/loader.py` | Trip→Stage→Waypoint-Modell; `load_all_trips(user_id)` |
| `frontend/.../StageList.svelte:31` | Konsument — Schema darf sich (auch in R2) NICHT ändern |

## Der exakt zu spiegelnde Go-Vertrag (verifiziert am Code)

### Response-Schema (`internal/model/stage_weather.go`, KEINE omitempty)
```json
{ "results": { "<stage_id>": {
  "weather_summary": {
    "temp_min_c": <float|null>, "temp_max_c": <float|null>,
    "wind_max_kmh": <float|null>, "precip_mm": <float|null>,
    "wmo_code": <int|null>, "is_day": <int|null> },
  "risk": "green"|"yellow"|"red" }, ... } }
```
- Nullbare Felder werden **explizit als `null`** serialisiert (nicht weggelassen).
- Ein Stage-Result ist **entweder komplett `null`** (`"<id>": null`) **oder** hat sowohl
  `weather_summary` (non-null) als auch `risk` (non-null). „Result vorhanden, risk=null" kann nie auftreten.
- Feldnamen weichen von der internen Summary ab: `precip_mm` (aus PrecipSum), `wmo_code` (aus DominantWmo).

### Fehlerfälle / HTTP
- Content-Type **immer** `application/json`.
- Store-Fehler → 500 Body exakt `{"error":"store_error"}`.
- Trip nil/unbekannt → 404 Body exakt `{"error":"not_found"}`.
- Erfolg → 200.
- (Python-Pendant nutzt `user_id` als Query-Param statt Auth-Kontext, s.u.)

### Fail-soft pro Stage (→ `results[id] = null`)
- Stage-ID leer → Stage komplett übersprungen (**kein** Map-Eintrag).
- `date==""` ODER 0 Waypoints ODER provider nil → null.
- Fetch-Fehler ODER leere Timeseries → null.
- Leere Aggregation (kein Punkt am Stage-Datum) → null.

### Aggregation (`aggregateForecasts`, Filter: `Time.UTC()==stageDate`)
- Min/Max ignorieren nil; alle nil → Feld bleibt null.
- `precip_mm` = Summe aller nicht-nil Precip1h; nur gesetzt wenn ≥1 Punkt Precip hat.
- `is_day` = null wenn kein Punkt am Tag ein is_day gesetzt hat; sonst 1 falls irgendein Punkt is_day==1, sonst 0.
- Koordinate = **arithmetisches Mittel aller Waypoints** der Stage; Fetch-Fenster 168h.

### WMO-Dominanz (`selectDominantWmoCode` + `wmoSeverityTier`) — NICHT frequenzbasiert
- Auswahl: **höchster Severity-Tier gewinnt; bei Gleichstand höchster WMO-Code**. Häufigkeit wird ignoriert.
- Tier-Tabelle (top-down, Lücken beachten):
  `>=95`→5 · `80-82`→4 · `71-77`→3 · `51-67`→4 · `45-48`→2 · `2-3`→1 · sonst (inkl. 0-1, 68-70, 49-50, 78-79, 83-94)→0.
- Leere Codemenge → null.

## Existing Patterns
- **`/api/_internal/`-Endpoint:** `api/routers/internal.py` — `@router.get(..., user_id: str = Query(...))`,
  `trip = next((t for t in load_all_trips(user_id) if t.id == trip_id), None)`; 404 via `HTTPException`.
  **Kein Auth-Kontext in Python** — user_id ist Query-Param (Go-API ist die Auth-Schicht, injiziert per `appendUserID`).
- **Risk-Pfad Briefing:** `RiskEngine().assess_segment(SegmentWeatherData, exposed_sections)` →
  `RiskAssessment` → `get_max_risk_level()` → `RiskLevel.{LOW,MODERATE,HIGH}`.
- **Aggregation:** `WeatherMetricsService.compute_metrics(timeseries)` → `SegmentWeatherSummary`
  (`wind_max_kmh`, `gust_max_kmh`, `precip_sum_mm`, `cape_max_jkg`, `thunder_level_max`, `confidence_pct_min`, …).

## Dependencies
- **Upstream (nutzen wir):** `load_all_trips`, `OpenMeteoProvider.fetch_forecast`, `WeatherMetricsService`,
  `RiskEngine`, `metric_catalog` (Schwellwerte).
- **Downstream (nutzt uns):** In R1 nur direkt aufrufbar (interner Port 8000). In R2 der Go-Proxy → `StageList.svelte`.

## Bewusste Divergenz = der eigentliche Zweck (Python gewinnt)
Die Cockpit-Stufe soll dem **Briefing** (Python-RiskEngine) folgen, NICHT der alten Go-Logik. Konsequenzen:
1. **Grenzwert 70,0:** Python `> high` → nicht HIGH (Go war `>= high` → HIGH). Kachel bei exakt 70,0 wird gelb statt rot — **so gewollt** (AC des Issues).
2. **Wind-Exposition (Regel 9):** Python wendet sie an, wenn `exposed_sections` übergeben werden → Analyse-Frage: Woher kommen exposed_sections im Endpoint?
3. **LOW_CONFIDENCE (Regel 10):** Feuert nur bei `confidence_pct_min < 40` UND vorhandenem HIGH-Risiko → braucht Ensemble-Anreicherung im Fetch → Analyse-Frage (Latenz).

## Risks & Considerations (→ in Phase 2 zu klären)
- **Parallel-Fetch existiert NICHT in Python** (verifiziert: kein ThreadPool/asyncio.gather). Go nutzt eine Goroutine/Stage.
  → Wir müssen `ThreadPoolExecutor` selbst bauen, um die Cockpit-Latenz zu halten. Latenz vorher/nachher messen (Pflicht-AC).
- **WMO-Dominanz:** Muss die Go-Severity-Tier-Logik 1:1 in Python nachgebildet werden (für `wmo_code`), da `compute_metrics`
  evtl. anders aggregiert. Klären: welchen dominanten Code liefert Python heute?
- **Exposition & Confidence:** Die Cockpit-Parität zum Briefing verlangt beide Regeln. Klären, ob der Endpoint
  `exposed_sections` aus der Trip-Config zieht und ob `enrich_ensemble` (Confidence) angeschaltet wird — beides mit Latenzkosten.
- **is_day-Quelle:** Prüfen, ob `ForecastDataPoint` in Python ein `is_day`-Feld trägt (Go hat `IsDay *int`).
- **Datum-/Zeitzonen-Parität:** Go filtert per `Time.UTC().Format("2006-01-02")` == stageDate. Python-Filter muss identisch (UTC-Tag) sein.
- **Korrektur ggü. Issue:** Die im Issue behauptete „CAPE→Gewitter-MED in weather_metrics:817" existiert nicht;
  die CAPE→THUNDERSTORM-Logik liegt in `risk_engine.py:57-60` (Schwelle medium=1000).

## Slicing
- **R1 (dieser Workflow):** Python-Endpoint bauen + Tests. Kein Go-Change, kein Frontend-Change.
- **R2 (Folge-Workflow):** Go `StagesWeatherHandler` → Proxy (`appendUserID`-Muster), `internal/risk/` löschen,
  Playwright-Farbvergleich Cockpit vor/nach auf Staging.

---

## Analysis

### Type
Feature / Rework (Refactoring + Konsolidierung, ADR-0015).

### Entscheidender Befund: Regel 10 ist farbneutral → Ensemble entfällt
`_check_confidence` (`risk_engine.py:170-189`) hängt nur ein **MODERATE** an — und **nur** wenn bereits ein
HIGH-Risiko (THUNDERSTORM/WIND/RAIN) vorliegt. Wenn sie feuert, ist `get_max_risk_level` also schon HIGH (rot).
→ Der trip-weite Ensemble-Call ist für grün/gelb/rot **irrelevant** und wird in R1 **weggelassen** (spart HTTP-Call
+ Anchoring-Komplexität, ist zugleich korrekter, da ein Multi-Stage-Anchor am letzten Waypoint der letzten Etappe
ohnehin nicht sauber abbildbar wäre). Regeln 1–9 allein liefern exakte Farb-Parität zum Briefing.

### Granularität (verifiziert)
`convert_trip_to_segments` (`src/services/trip_segments.py:106`) erzeugt pro Stage **N-1 Leg-Segmente + 1 Ziel-Segment**
(N = Waypoints). Das Briefing bewertet Risiko **pro Segment** (`trip_report.py:660-673`), inkl. km-Overlap für die
Exposition (Regel 9). **Konsequenz:** Die Cockpit-Stage-Kachel = **max(Risiko über alle Segmente der Stage)**.
Der Whole-Stage-Weg (alter Go-Handler) kann das strukturell nicht → entfällt.

### Technical Approach (Ansatz B, ohne Ensemble)
Neuer SSoT-Service, der die vorhandenen **public** Bausteine wiederverwendet (nicht reimplementiert):
1. Pro Stage: `convert_trip_to_segments(trip, stage.date)`.
2. `detect_exposed_from_segments(segments, min_elevation_m = trip.report_config.wind_exposition_min_elevation_m or 1500)`.
3. Wetter je Segment: `SegmentWeatherService(provider).fetch_segment_weather(segment, enrich_ensemble=False)` —
   **parallel** über einen flachen `ThreadPoolExecutor` über alle (Stage,Segment)-Paare (I/O-bound; threadsicher, eigener Request/Call).
4. Pro Segment: `RiskEngine().assess_segment(sw, exposed_sections)` → `get_max_risk_level`; **Stage-Risiko = max** über Segmente.
5. `weather_summary`: `aggregate_stage(seg_weather)` (`weather_metrics.py:1228`) für temp/wind/precip/wmo; `is_day`
   analog Go (`stage_weather.go:122`) aus der Timeseries (≥1 Punkt am Stage-Tag mit is_day==1, sonst 0, kein Punkt→null).
6. RiskLevel → `"red"/"yellow"/"green"`.

**Fail-soft (→ `results[id]=null`):** date=="" · 0 Waypoints · keine Segmente · Fetch-Fehler · leere Aggregation.
Leere Stage-ID → Stage komplett übersprungen (kein Map-Eintrag). Response-Vertrag (Feldnamen, null-Serialisierung,
404 `not_found` / 500 `store_error`) bleibt **1:1** zum Go-Handler. `user_id` als Query-Param (Muster `internal.py`).

### Affected Files (with changes)
| Datei | Change | Beschreibung | LoC (Schätzung) |
|------|--------|--------------|-----------------|
| `src/services/stage_weather.py` | CREATE | SSoT `compute_stage_weather(trip, provider) -> dict[str, StageResult|None]` (Schritte 1–6) | ~150–190 |
| `api/routers/internal.py` | MODIFY | Endpoint `GET /api/_internal/trips/{id}/stages-weather`, user_id Query, load_all_trips, 404/500, results-Wrapper | ~45–60 |
| `tests/…` | CREATE | Kern-Tests gegen aufgezeichnete/Fixture-Provider-Daten (Farb-Parität, Fail-soft, Grenzwert 70,0, Exposition) | (zählt nicht ins LoC-Limit) |
| `api/main.py` | — | keine Änderung (`internal.router` bereits eingebunden) | 0 |

### Scope Assessment
- Files: 2 Code-Dateien (+ Tests)
- Estimated LoC: **~200–250** (Code, ohne Tests) → **grenzwertig unter 250**
- Risk Level: **MEDIUM-HIGH** (Paritäts-Genauigkeit ist das Risiko, nicht die Mechanik)

### Consequence for the product (Heads-up, kein offener Punkt)
Für reale Trips **verschieben sich Cockpit-Farben** ggü. heute: exponierte Etappen können rot/gelb werden (Go ignorierte
Exposition), und exakt 70,0 km/h wird gelb statt rot. Das ist der **beabsichtigte** Effekt von #1212 (Cockpit == Briefing).

### Dependencies / Reihenfolge
- R1 hat keine Vorbedingung. R2 (Go→Proxy + Löschung) hängt hart von diesem Endpoint ab.
- Wiederverwendete public Funktionen: `convert_trip_to_segments`, `SegmentWeatherService.fetch_segment_weather`,
  `detect_exposed_from_segments`, `RiskEngine.assess_segment`, `aggregate_stage`.

### Open Questions (für Spec/Implementierung)
- [ ] **LoC-Grenze:** Falls Provider-Injection (Tests) + saubere Parallelität >250 LoC treiben → Split R1a (Service) / R1b (Router).
  **Kein LoC-Override ohne PO-Freigabe** — bei Überschreitung zurück zum PO.
- [ ] **WMO-Tie-Break:** Pythons `compute_dominant_wmo` nutzt `max(key=severity)` → bei Severity-Gleichstand „first-seen"
  statt „höchster Code" (Go). Betrifft nur *unbekannte* Codes (Severity 0); für Farb-Parität irrelevant. Als Known Limitation dokumentieren.
- [ ] **Provider-Auswahl im Endpoint:** Welcher Provider wird instanziiert (OpenMeteo default vs. Trip-Provider-Config)? In Spec fixieren.
