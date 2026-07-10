---
entity_id: stage_weather_python_endpoint
type: module
created: 2026-07-10
updated: 2026-07-10
status: draft
version: "1.0"
tags: [risk, weather, cockpit, adr-0015, issue-1212]
---

# Stage-Weather Python-Endpoint (Slice R1, #1212)

## Approval

- [x] Approved — PO „go" 2026-07-10

## Purpose

Ein interner Python-Endpoint liefert pro Wander-Etappe eine Wetter-Zusammenfassung und eine
Risiko-Stufe (green/yellow/red), die **exakt** der Bewertung des E-Mail-Briefings entspricht.
Er ist die künftige Single Source of Truth der Cockpit-Risiko-Kacheln (ADR-0015) und ersetzt in
Slice R2 die eigene Go-Risk-Logik durch einen Proxy. R1 baut nur den Python-Endpoint; Go/Frontend bleiben unberührt.

## Source

- **File:** `src/services/stage_weather.py` (NEU) · `api/routers/internal.py` (MODIFY)
- **Identifier:** `compute_stage_weather(trip, provider)` · `GET /api/_internal/trips/{id}/stages-weather`

## Estimated Scope

- **LoC:** ~200–250 (Code, ohne Tests) — grenzwertig unter dem 250-Limit
- **Files:** 2 Code-Dateien (+ Tests)
- **Effort:** high (Paritäts-Genauigkeit ist das Risiko, nicht die Mechanik)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `convert_trip_to_segments` (`src/services/trip_segments.py:106`) | reuse | Segmente pro Stage bilden (N-1 Leg + 1 Ziel) |
| `SegmentWeatherService.fetch_segment_weather` (`src/services/segment_weather.py:71`) | reuse | Wetter je Segment (`enrich_ensemble=False`) |
| `WindExpositionService.detect_exposed_from_segments` (`src/services/wind_exposition.py:59`) | reuse | Exposition (Regel 9) aus Segment-Höhen |
| `RiskEngine.assess_segment` + `get_max_risk_level` (`src/services/risk_engine.py:39,113`) | reuse | Risiko-Bewertung |
| `aggregate_stage` (`src/services/weather_metrics.py:1228`) | reuse | Stage-Summary (temp/wind/precip/wmo) |
| `load_all_trips` (`src/app/loader.py:1020`) | reuse | Trip für `user_id` laden |
| `api/routers/internal.py` | pattern | `/api/_internal/`-Endpoint, `user_id` als Query-Param |

## Implementation Details

### Service `compute_stage_weather(trip, provider) -> dict[str, StageResult | None]`
Pro Stage in `trip.stages`:
1. `stage.id == ""` → Stage komplett überspringen (kein Ergebnis-Eintrag).
2. Fail-soft → `None`, wenn: `stage.date` fehlt · `len(stage.waypoints) == 0` · keine Segmente ·
   alle Segment-Fetches scheitern · leere Aggregation.
3. Segmente: `convert_trip_to_segments(trip, stage.date)`.
4. Exposition: `detect_exposed_from_segments(segments, min_elevation_m = trip.report_config.wind_exposition_min_elevation_m or 1500)`.
5. Wetter je Segment: `SegmentWeatherService(provider).fetch_segment_weather(seg, enrich_ensemble=False)` —
   **parallel** via `ThreadPoolExecutor` (flach über alle (Stage,Segment)-Paare; I/O-bound, threadsicher).
6. Risiko: je Segment `assess_segment(sw, exposed_sections)` → `get_max_risk_level`; **Stage-Risiko = max** über die Segmente.
7. `weather_summary`: `aggregate_stage(seg_weather)` → `temp_min_c`, `temp_max_c`, `wind_max_kmh`, `precip_mm` (aus precip_sum), `wmo_code` (dominant).
8. `is_day`: aus den Timeseries der Stage — `1`, wenn ≥1 Punkt am Stage-Tag `is_day==1`; `0`, wenn Punkte aber keiner ==1; `null`, wenn kein Punkt am Tag ein is_day trägt (analog Go `computeIsDay`).
9. RiskLevel → `"red"` (HIGH) / `"yellow"` (MODERATE) / `"green"` (sonst).

**Ensemble/Confidence (Regel 10) wird NICHT gefetcht** — siehe Known Limitations (farbneutral).

### Endpoint `GET /api/_internal/trips/{id}/stages-weather`
- `user_id: str = Query(...)` (Muster `internal.py:16`); kein Auth-Kontext in Python (Go-API ist Auth-Schicht).
- `trip = next((t for t in load_all_trips(user_id) if t.id == id), None)`.
- `trip is None` → HTTP 404, Body **exakt** `{"error":"not_found"}`.
- Interner Fehler (Store/Load-Exception) → HTTP 500, Body **exakt** `{"error":"store_error"}`.
- Erfolg → HTTP 200, Body `{"results": {"<stage_id>": <StageResult|null>, …}}`.

## Expected Behavior

- **Input:** `trip_id` (Path), `user_id` (Query).
- **Output (Erfolg):**
  ```json
  {"results": {"<stage_id>": {
    "weather_summary": {"temp_min_c": <float|null>, "temp_max_c": <float|null>,
      "wind_max_kmh": <float|null>, "precip_mm": <float|null>,
      "wmo_code": <int|null>, "is_day": <int|null>},
    "risk": "green"|"yellow"|"red"} | null}}
  ```
  Nullbare Felder werden **explizit als `null`** ausgegeben (nicht weggelassen). Ein Stage-Result ist
  entweder komplett `null` oder hat sowohl `weather_summary` (non-null) als auch `risk` (non-null).
- **Side effects:** keine (Read-only; kein Mailversand, kein Marker-Schreiben).

## Acceptance Criteria

- **AC-1 (Response-Vertrag 1:1):** Given ein Trip mit gültigen Etappen und Wetterdaten / When der Endpoint mit korrektem `user_id` aufgerufen wird / Then liefert er HTTP 200 mit `{"results": {...}}`, wobei jedes Stage-Result die Felder `weather_summary` (`temp_min_c, temp_max_c, wind_max_kmh, precip_mm, wmo_code, is_day`) und `risk` trägt, und nullbare Felder explizit als `null` serialisiert sind.
  - Test: Kern-Test gegen Fixture-Provider prüft, dass die JSON-Struktur und alle Feldnamen exakt dem Go-Schema entsprechen (inkl. `null`-Serialisierung eines fehlenden Werts).

- **AC-2 (Risiko = max über Segmente, Briefing-Parität):** Given eine Etappe, in der genau ein Segment ein HIGH-Risiko hat und die übrigen green sind / When der Endpoint die Etappe bewertet / Then ist `risk` der Etappe `"red"` (das Maximum), identisch zur Briefing-Bewertung derselben Segmente.
  - Test: Kern-Test mit aufgezeichneten Segment-Wetterdaten, in denen ein Segment HIGH auslöst; Ergebnis-Risk == `"red"`.

- **AC-3 (Grenzwert 70,0 → gelb):** Given eine Etappe mit maximalem Wind/Böe von exakt 70,0 km/h und sonst harmlosen Werten / When der Endpoint sie bewertet / Then ist `risk` `"yellow"` (nicht `"red"`), weil die Python-Semantik `> high` verlangt.
  - Test: Kern-Test mit Wind-Fixture exakt 70,0 km/h → Ergebnis `"yellow"`.

- **AC-4 (Exposition greift, Regel 9):** Given eine Etappe mit einem exponierten Segment (Segment-Höhe ≥ Schwelle) und Wind zwischen der Expositions- und der Normal-Schwelle / When der Endpoint sie bewertet / Then wird das exponierte Segment höher eingestuft als es die alte Whole-Stage-Logik täte, und die Etappen-Kachel spiegelt das (z.B. `"yellow"`/`"red"` statt `"green"`).
  - Test: Kern-Test mit exponiertem Segment + Wind im Expositions-Band; Ergebnis-Risk ist erhöht ggü. einem identischen nicht-exponierten Segment.

- **AC-5 (Fail-soft pro Etappe):** Given ein Trip, bei dem eine Etappe kein Datum/keine Waypoints hat oder deren Wetter-Fetch scheitert / When der Endpoint läuft / Then ist deren Ergebnis `null`, ohne dass der gesamte Request scheitert (kein 5xx), und die übrigen Etappen liefern normale Ergebnisse.
  - Test: Kern-Test mit einer defekten und einer gültigen Etappe → `results[defekt]==null`, `results[gültig]!=null`, HTTP 200.

- **AC-6 (Leere Stage-ID übersprungen):** Given ein Trip mit einer Etappe ohne ID / When der Endpoint läuft / Then erscheint für diese Etappe **kein** Schlüssel in `results`.
  - Test: Kern-Test mit einer leeren Stage-ID → Schlüssel fehlt im Ergebnis.

- **AC-7 (Fehlerfälle):** Given eine unbekannte `trip_id` bzw. ein interner Ladefehler / When der Endpoint aufgerufen wird / Then antwortet er mit HTTP 404 Body `{"error":"not_found"}` bzw. HTTP 500 Body `{"error":"store_error"}`.
  - Test: Kern-Test für unbekannte ID (404) und für einen simulierten Ladefehler (500) prüft Status + exakten Body.

- **AC-8 (Nutzer-Isolation):** Given zwei verschiedene Nutzer A und B, jeder mit einem eigenen Trip gleicher ID-Kollision oder unterschiedlicher Trips / When der Endpoint mit `user_id=A` bzw. `user_id=B` aufgerufen wird / Then sieht A nur A's Trip-Daten und B nur B's — nie fällt der Endpoint auf `"default"` zurück.
  - Test: Kern-Test mit zwei Nutzern und je eigenem Trip; Cross-Zugriff liefert 404 bzw. die jeweils eigenen Daten, nie fremde.

## Known Limitations

- **Regel 10 / LOW_CONFIDENCE wird bewusst NICHT berechnet.** `_check_confidence` (`risk_engine.py:170-189`)
  fügt nur ein MODERATE hinzu und **nur**, wenn bereits ein HIGH-Risiko vorliegt → das Maximum ist dann ohnehin HIGH (rot).
  Der Confidence-Wert ändert die grün/gelb/rot-Farbe also nie. Der teure trip-weite Ensemble-Call entfällt daher in R1.
  (Falls Regel 10 künftig farbwirksam würde, muss der Endpoint nachziehen.)
- **WMO-Tie-Break bei unbekannten Codes:** Pythons `compute_dominant_wmo` wählt bei Severity-Gleichstand den
  „zuerst gesehenen" Code, Go den „numerisch höchsten". Betrifft nur *unbekannte* WMO-Codes (Severity 0) und ist
  farbneutral; für `wmo_code` im Anzeigefeld theoretisch minimal abweichend, praktisch irrelevant.
- **Latenz:** Der Endpoint fetcht pro Segment (mehr Einzel-Fetches als der alte Go-Handler pro Stage), gleicht das
  aber per `ThreadPoolExecutor` aus. Die spürbare Cockpit-Latenz-Parität wird erst in Slice R2 (Proxy live, Playwright
  vor/nach) endgültig verifiziert; in R1 wird die Endpoint-Antwortzeit gemessen und dokumentiert.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0015 (bestehend — Python ist Owner der Wetter-Domäne). Kein neuer ADR nötig; R1 setzt ADR-0015 um.
- **Rationale:** Die Konsolidierung folgt der bereits getroffenen Entscheidung; keine neue architektonische Weiche.

## Changelog

- 2026-07-10: Initial spec created (Slice R1 von #1212)
