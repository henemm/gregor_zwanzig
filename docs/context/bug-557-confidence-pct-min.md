# Context: Bug #557 — _enrich_ensemble_for_trip() setzt confidence_pct_min nicht

## Request Summary
`_enrich_ensemble_for_trip()` setzt `confidence_pct_min` auf `SegmentWeatherSummary`-Objekten nicht, wenn `timeseries=None` ist. Der zugehörige Test `test_ac3_confidence_propagated_to_all_segments_after_enrichment` ist mit `@pytest.mark.xfail` markiert und schlägt regulär fehl.

## Wurzelproblem
Der Test setzt `timeseries=None` und testet damit den Fallback-Pfad (5b/6b) in `_enrich_ensemble_for_trip`. Dieser Pfad benötigt echte Ensemble-Spread-Daten aus der HTTP-API (`provider._fetch_ensemble_spread()`). Da der Test kein Live-Setup hat, scheitert der HTTP-Call → frühes `return` → `confidence_pct_min` bleibt `None`.

**Zeitachse:**
- `f683be7` (#288): Methode eingeführt, Test als `@pytest.mark.live` markiert (ran nie in CI)
- `bug-537/539`: Marker-Aufräumen — `pytest.mark.live` auf Modul-Ebene entfernt → Test sichtbar
- Bug #557 dokumentiert das Problem, `@pytest.mark.xfail(strict=False)` hinzugefügt

## Related Files
| Datei | Relevanz |
|-------|---------|
| `src/services/trip_report_scheduler.py` L824–936 | `_enrich_ensemble_for_trip()` — Bug-Location |
| `tests/tdd/test_bug_288_ensemble_api_limit.py` L196–268 | Failing test mit xfail-Marker |
| `src/providers/openmeteo.py` L508–548 | `_fetch_ensemble_spread()` — Live-HTTP-Call |
| `src/providers/fixture.py` | FixtureProvider — fehlt `_fetch_ensemble_spread` |
| `src/providers/base.py` L120–125 | `get_provider("openmeteo")` → FixtureProvider wenn `GZ_TEST_FIXTURE_DIR` gesetzt |
| `src/app/models.py` L332–376 | `SegmentWeatherSummary.confidence_pct_min: Optional[int]` |

## Bestehende Patterns

### Fixture-Provider-Muster (Issue #263/#346)
```python
# In get_provider():
fixture_dir = os.environ.get("GZ_TEST_FIXTURE_DIR", "").strip()
if fixture_dir and name == "openmeteo":
    return FixtureProvider(fixture_dir)
```
`FixtureProvider` implementiert `fetch_forecast()` offline, aber NICHT `_fetch_ensemble_spread()`.

### isinstance-Guard in `_enrich_ensemble_for_trip`
```python
provider = get_provider("openmeteo")
if not isinstance(provider, OpenMeteoProvider):
    return  # ← FixtureProvider kommt hier raus → kein Ensemble
```

### Existierender Berechnungspfad (Zeilen 906–936)
Der Code setzt `confidence_pct_min` bereits korrekt — aber nur wenn:
- (Pfad 6a) `timeseries` nicht None ist UND spreads zeitlich auf DataPoints matchen
- (Pfad 6b) `timeseries` None ist und spreads in das Segment-Zeitfenster fallen

Beide Pfade setzen voraus, dass `_fetch_ensemble_spread()` erfolgreich antwortet.

## Fix-Optionen

### Option A — Computation extrahieren (empfohlen)
Pure Hilfsfunktion `_apply_ensemble_spreads(weather_data, spreads_naive, now_utc)` extrahieren. Test ruft diese direkt mit kontrollierten Spread-Daten auf. Kein API-Call nötig.

```python
# Test erstellt:
spreads = {naive_ts: (2.5, 1.2)}  # s_t, s_p
_apply_ensemble_spreads([weather_item], spreads, now_utc)
assert weather_item.aggregated.confidence_pct_min is not None
```

- Vorteile: kein Mock, kein HTTP, klar testbar, folgt "pure function test"-Muster
- Nachteile: kleines Refactoring nötig

### Option B — FixtureProvider erweitern
`_fetch_ensemble_spread()` zu `FixtureProvider` hinzufügen + `isinstance`-Check ersetzen durch Duck-Typing/Protocol. FixtureProvider gibt deterministischen Spread zurück.

- Vorteile: gesamter Flow getestet
- Nachteile: größere Änderung, Fixture-JSON erweitern, isinstance-Check anfassen

### Option C — @pytest.mark.live belassen
Test als `@pytest.mark.live` markieren — nur in CI mit echtem Netz.

- Nachteile: schlechte Testabdeckung, kein reguläres Grün

## Dependencies
- Upstream: `providers.openmeteo.compute_confidence_pct` (reine Funktion, importierbar)
- Downstream: F12 Stabilitätslabel (`confidence_pct_min`-Werte der Folge-Etappen)
  - `src/services/trip_report_scheduler.py` L357–363 liest `confidence_pct_min` nach dem Aufruf

## Existing Specs
- `docs/specs/modules/bug_288_ensemble_api_limit.md` — Original-Spec (AC-3 betroffen)

## Risks & Considerations
- `SegmentWeatherSummary` ist kein frozen dataclass → `confidence_pct_min` direkt schreibbar ✓
- `compute_confidence_pct` ist eine reine Funktion in `openmeteo.py:67` → importierbar ohne HTTP
- Kein Schema-Rework nötig — Feldname `confidence_pct_min` bleibt unverändert
- Gefahr: xfail-Test wird nach Fix nicht automatisch grün ohne Anpassung des Testcodes
