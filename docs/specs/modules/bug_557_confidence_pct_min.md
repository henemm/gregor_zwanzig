---
entity_id: bug_557_confidence_pct_min
type: bugfix
created: 2026-06-02
updated: 2026-06-02
status: draft
version: "1.0"
tags: [bugfix, ensemble, confidence, trip-report-scheduler, issue-557, issue-288]
---

<!-- Issue #557 — `_enrich_ensemble_for_trip()` setzt `confidence_pct_min` nicht — AC-3 von Bug #288 nicht erfüllt -->

# Issue #557 — Bug-Fix: `_apply_ensemble_spreads()` als testbare Pure Helper-Methode extrahieren

## Approval

- [ ] Approved

## Zweck

`_enrich_ensemble_for_trip()` in `trip_report_scheduler.py` ruft `get_provider("openmeteo")` auf, was in der CI-Umgebung (wenn `GZ_TEST_FIXTURE_DIR` gesetzt ist) einen `FixtureProvider` zurückgibt statt eines `OpenMeteoProvider`. Der `isinstance(provider, OpenMeteoProvider)`-Guard schlägt daraufhin sofort fehl und kehrt zurück, bevor der Berechnungscode (Zeilen 885–936) ausgeführt wird — `confidence_pct_min` wird damit nie gesetzt. Der Fix extrahiert den Berechnungsblock in eine neue, direkt aufrufbare Methode `_apply_ensemble_spreads()`, sodass der Test AC-3 aus Bug #288 ohne Netzwerkzugriff verifizieren kann und die Produktionslogik unverändert bleibt.

## Quelle / Source

**Geänderte Dateien:**

- `src/services/trip_report_scheduler.py` — Zeilen 885–936 aus `_enrich_ensemble_for_trip()` in neue Methode `_apply_ensemble_spreads(self, weather_data, spreads_naive, now_utc)` extrahieren; `_enrich_ensemble_for_trip()` ruft `_apply_ensemble_spreads()` intern auf
- `tests/tdd/test_bug_288_ensemble_api_limit.py` — `test_ac3_confidence_propagated_to_all_segments_after_enrichment` aktualisieren: direkt `_apply_ensemble_spreads()` aufrufen, `@pytest.mark.xfail`-Marker entfernen

> **Schicht-Hinweis:** Alle Änderungen liegen ausschließlich im Python-Backend-Layer (`src/services/`). Frontend, Go-API und andere Provider sind nicht betroffen.

## Estimated Scope

- **LoC:** ~15 net additions
- **Files:** 2
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/trip_report_scheduler.py` | Python-Service | Enthält `_enrich_ensemble_for_trip()` und die neue Methode `_apply_ensemble_spreads()` |
| `src/providers/openmeteo.py:67` | Python-Funktion | `compute_confidence_pct(spread_t2m_k, spread_precip_mm, lead_h)` — pure Funktion, die von `_apply_ensemble_spreads()` aufgerufen wird |
| `src/app/models.py:332` | Python-Dataclass | `SegmentWeatherSummary.confidence_pct_min: Optional[int]` — Feld, das nach Aufruf von `_apply_ensemble_spreads()` gesetzt sein muss |
| `tests/tdd/test_bug_288_ensemble_api_limit.py` | Test-Datei | Enthält `test_ac3`, der aktuell mit `@pytest.mark.xfail` markiert ist und nach dem Fix ohne Marker bestehen muss |

## Implementation Details

### 1. Neue Methode `_apply_ensemble_spreads()` extrahieren

Die Logik aus Zeilen 885–936 von `_enrich_ensemble_for_trip()` wird 1:1 in eine neue Methode verschoben:

```python
def _apply_ensemble_spreads(
    self,
    weather_data: dict,          # segment_key -> SegmentWeatherSummary
    spreads_naive: dict,         # naive datetime -> (spread_t2m_k, spread_precip_mm, lead_h)
    now_utc: datetime,
) -> None:
    """
    Propagiert vorberechnete Ensemble-Spreads auf alle DataPoints in weather_data
    und setzt anschließend confidence_pct_min auf jedem SegmentWeatherSummary.
    Kein API-Call — arbeitet ausschließlich auf übergebenen Daten.
    """
    for segment_summary in weather_data.values():
        for dp in segment_summary.data_points:
            ts_key = dp.timestamp.replace(tzinfo=None)  # Timestamp-Normalisierung wie bisher
            if ts_key in spreads_naive:
                spread_t2m_k, spread_precip_mm, lead_h = spreads_naive[ts_key]
                dp.confidence_pct = compute_confidence_pct(spread_t2m_k, spread_precip_mm, lead_h)
                dp.spread_t2m_k = spread_t2m_k
                dp.spread_precip_mm = spread_precip_mm

        valid = [dp.confidence_pct for dp in segment_summary.data_points
                 if dp.confidence_pct is not None]
        segment_summary.confidence_pct_min = min(valid) if valid else None
```

### 2. `_enrich_ensemble_for_trip()` anpassen

Nach dem Ensemble-API-Call und der Spread-Berechnung wird `_apply_ensemble_spreads()` aufgerufen statt den Block inline auszuführen:

```python
def _enrich_ensemble_for_trip(self, trip, weather_data, now_utc):
    provider = get_provider("openmeteo")
    if not isinstance(provider, OpenMeteoProvider):
        return

    # ... bestehender API-Call-Block (unverändert) ...
    spreads_naive = _compute_spreads_naive(ensemble_raw, now_utc)  # bisher inline

    self._apply_ensemble_spreads(weather_data, spreads_naive, now_utc)
```

Die Semantik des bisherigen Produktionspfads bleibt vollständig erhalten.

### 3. Test `test_ac3` aktualisieren

```python
# Vorher:
@pytest.mark.xfail(reason="FixtureProvider bypasses isinstance guard")
def test_ac3_confidence_propagated_to_all_segments_after_enrichment(...):
    ...

# Nachher (kein xfail-Marker):
def test_ac3_confidence_propagated_to_all_segments_after_enrichment(...):
    spreads_naive = {
        naive_dt_matching_segment: (spread_t2m_k=2.1, spread_precip_mm=0.8, lead_h=24),
    }
    scheduler._apply_ensemble_spreads(weather_data, spreads_naive, now_utc=datetime.utcnow())
    assert weather_data[segment_key].confidence_pct_min is not None
```

Der Test verwendet handgefertigte `spreads_naive`-Daten mit Zeitstempeln, die in das Segment-Zeitfenster fallen — kein API-Call erforderlich.

### 4. LoC-Budget

| Datei | Δ LoC | Zählt |
|-------|--------|-------|
| `src/services/trip_report_scheduler.py` | ~10 | ja |
| `tests/tdd/test_bug_288_ensemble_api_limit.py` | ~5 | ja |
| **Gesamt (zählend)** | **~15** | **< 250 LoC-Limit** |

## Expected Behavior

- **Input:** `weather_data` (dict mit SegmentWeatherSummary-Werten), `spreads_naive` (dict mit naive datetime-Keys und Spread-Tupeln), `now_utc` (datetime)
- **Output:** Kein Rückgabewert; mutiert `weather_data` in-place: `dp.confidence_pct`, `dp.spread_t2m_k`, `dp.spread_precip_mm` auf allen DataPoints mit übereinstimmenden Timestamps gesetzt; `segment_summary.confidence_pct_min` auf jedem SegmentWeatherSummary gesetzt (Minimum über alle DataPoints, oder `None` wenn keine Übereinstimmung)
- **Side effects:** Produktionspfad über `_enrich_ensemble_for_trip()` unverändert — ruft `_apply_ensemble_spreads()` intern auf, Verhalten identisch zu vor dem Fix

## Acceptance Criteria

- **AC-1:** Given ein SegmentWeatherSummary mit DataPoints, deren Timestamps mit den Keys in `spreads_naive` übereinstimmen, und `timeseries=None` / When `_apply_ensemble_spreads()` mit diesen Spread-Daten aufgerufen wird / Then ist `weather_item.aggregated.confidence_pct_min` danach nicht `None` und enthält einen Integer-Wert zwischen 0 und 100
  - Test: (populated after /tdd-red)

- **AC-2:** Given ein SegmentWeatherSummary mit mehreren DataPoints, von denen jeder einen übereinstimmenden Timestamp-Key in `spreads_naive` hat / When `_apply_ensemble_spreads()` aufgerufen wird / Then ist `weather_item.aggregated.confidence_pct_min` gleich dem Minimum der berechneten `confidence_pct`-Werte über alle DataPoints
  - Test: (populated after /tdd-red)

- **AC-3:** Given der bestehende Test `test_ac3_confidence_propagated_to_all_segments_after_enrichment` in `tests/tdd/test_bug_288_ensemble_api_limit.py` ohne `@pytest.mark.xfail`-Marker / When `pytest` die Test-Datei ausführt / Then besteht der Test ohne Fehler und ohne xfail-Skip
  - Test: (populated after /tdd-red)

- **AC-4:** Given ein laufender Report-Run in der Produktionsumgebung (echter `OpenMeteoProvider`, kein `FixtureProvider`) / When `_enrich_ensemble_for_trip()` aufgerufen wird / Then wird `_apply_ensemble_spreads()` intern aufgerufen und `confidence_pct_min` auf allen Segmenten korrekt gesetzt — kein Regression gegenüber den ACs AC-1, AC-2, AC-4 und AC-5 des ursprünglichen Bug-#288-Specs
  - Test: (populated after /tdd-red)

## Known Limitations

- **Timestamp-Normalisierung muss konsistent bleiben:** `_apply_ensemble_spreads()` normalisiert Timestamps auf naive datetime via `.replace(tzinfo=None)`. Wenn Segment-DataPoints tz-aware Timestamps mit Nicht-UTC-Offsets haben, kann das Matching fehlschlagen. Die bestehende Normalisierung aus `openmeteo.py:770-787` muss 1:1 übernommen werden.
- **Nur `OpenMeteoProvider` unterstützt Ensemble:** Der `isinstance`-Guard in `_enrich_ensemble_for_trip()` bleibt erhalten. `_apply_ensemble_spreads()` selbst ist provider-agnostisch, setzt aber voraus, dass `spreads_naive` korrekt befüllt ist — leere Spreads führen zu `confidence_pct_min=None`.

## Out of Scope

- Änderungen an der Ensemble-API-Aufruf-Logik selbst (bleibt in `_enrich_ensemble_for_trip()`)
- Caching oder Parallelisierung von Ensemble-Calls
- Änderungen am Frontend oder Go-API
- Refactoring weiterer Teile von `trip_report_scheduler.py`

## Changelog

- 2026-06-02: Initial spec erstellt. Extrahiert Zeilen 885–936 aus `_enrich_ensemble_for_trip()` in `_apply_ensemble_spreads()`, damit AC-3 von Bug #288 ohne Netzwerkzugriff testbar wird. ~15 LoC netto, 2 Dateien.
