# Context: feat-1115-openmeteo-model-fallback

Issue: [#1115](https://github.com/henemm/gregor_zwanzig/issues/1115) — `priority:critical`, `type:feature`, `area:trips`

## Request Summary

Beim Incident 07./08.07. (14 h, 203× HTTP 503 **ausschließlich** auf `/v1/dwd-icon`, alle anderen Open-Meteo-Endpoints lieferten parallel 200) fielen **alle** Trip-Briefings aus, weil der gewählte Modell-Endpoint hart ist und bei 5xx kein Ausweichen stattfindet. Ziel: Bei 5xx des regional gewählten Modell-Endpoints innerhalb Open-Meteo auf das nächste Modell der `REGIONAL_MODELS`-Prioritätskette (letztlich globales ECMWF) ausweichen. Anbieter-übergreifender Fallback ist zweite Stufe.

## Kern-Befund (verändert Issue-Framing)

- **`brightsky` ist KEIN tragfähiger Ersatz-Provider.** `src/providers/brightsky.py` bietet nur `fetch_radar(lat, lon) -> list[RadarFrame]` (Niederschlags-Radar-Nowcast, DE-Bounding-Box), **kein** `fetch_forecast`, **kein** `NormalizedTimeseries`. Der Issue-Vorschlag „openmeteo → brightsky" liefert damit kein vollständiges Briefing. → Cross-Provider-Fallback kann nur `geosphere` sein.
- **`geosphere` ist protokoll-kompatibel** (`fetch_forecast(location, start, end, enrich_ensemble) -> NormalizedTimeseries`, `geosphere.py:172`), aber Österreich/AROME-fokussiert, **kein** Coverage-Bounds-Check im Code, **kein** Ensemble/Confidence-Spread (`enrich_ensemble` wird ignoriert, Bug #288).
- **Der wirksamste Hebel ist die Intra-Open-Meteo-Modell-Fallback-Kette** — sie hätte den kompletten Incident verhindert und ist auf einen Provider begrenzt.

## Related Files

| Datei | Relevanz |
|------|-----------|
| `src/providers/openmeteo.py` | **Kern.** `select_model()` (372) wählt genau EIN Modell nach Koordinaten; `fetch_forecast()` (722) ruft `_request(endpoint, params)` (801) für genau diesen Endpoint. `REGIONAL_MODELS` (103) ist die Prioritätskette. Hier muss die Fallback-Schleife über die Kette rein. |
| `src/providers/base.py` | `get_provider(name)` (101), Registry `_load_providers` (140): registriert `geosphere`/`openmeteo`/`brightsky`. `WeatherProvider`-Protocol (18). |
| `src/providers/geosphere.py` | Einziger protokoll-kompatibler Alt-Provider (`fetch_forecast` :172). AT/AROME, kein Coverage-Check, kein Ensemble. |
| `src/providers/brightsky.py` | **Nicht** protokoll-kompatibel (nur `fetch_radar`). Als Vollersatz ausgeschlossen. |
| `src/services/trip_report_scheduler.py` | `_fetch_weather()` (960) — pro Segment ein Fetch (998–1006). Hat bereits `provider=`-Param (963, Default None) und eigene Retry-/`has_error`-Platzhalter-Logik (1001–1070). `_fetch_night_weather` (1115) + `_enrich_ensemble_for_trip` (1175) hardcodieren `openmeteo`. |
| `src/services/segment_weather.py` | `SegmentWeatherService` fängt `ProviderRequestError` intern ab → liefert `has_error`-Objekt statt Raise. |
| `src/app/models.py` | `SegmentWeatherData` (390) mit `has_error`/`error_message`; `NormalizedTimeseries`. |
| `docs/reference/decision_matrix.md` | Nur MET vs. MOSMIX (Distanz/Höhe/Land-See). **Kein** „wann welcher Provider"-Abschnitt für die real implementierten Provider. |

## Existing Patterns

- **Prioritätsketten-Iteration existiert bereits:** `select_model()` (openmeteo.py:393) und `_find_fallback_model()` (324) iterieren `REGIONAL_MODELS` `sorted(..., key=priority)`. Die Fallback-Schleife kann dieses Muster wiederverwenden.
- **Metrik-Fallback (WEATHER-05b)** existiert (`_find_fallback_model`/`_merge_fallback`, Block 857–893) — triggert aber **nur bei fehlenden Metriken laut Availability-Cache**, NICHT bei HTTP-5xx. Ein 5xx im Primär-Call (801) beendet `fetch_forecast` vor diesem Block.
- **Retry-Muster:** tenacity `@retry` auf `_request` (441). **Achtung:** 5xx werden faktisch **nicht** retried, weil `raise_for_status()` (477) den `httpx.HTTPStatusError` im except (479–483) in `ProviderRequestError` umwandelt, bevor der Retry-Decorator ihn sieht → `_is_retryable_error` greift nicht. Retry gegen transiente 503 passiert stattdessen auf **Scheduler-Ebene** (`_fetch_weather`, `FETCH_RETRY_ATTEMPTS`, #1113).
- **Diagnose-Logging:** `_log_api_call` (421) schreibt pro Call nach `openmeteo_calls.jsonl` (Grundlage der Incident-Analyse).

## Dependencies

- **Upstream (was Open-Meteo nutzt):** `httpx`-Client, `REGIONAL_MODELS`, `select_model`, `_parse_response`, `_log_api_call`.
- **Downstream (was den Provider nutzt):** `SegmentWeatherService.fetch_segment_weather` → `trip_report_scheduler._fetch_weather` (Briefings), `comparison_engine` (Ortsvergleich, `get_provider("openmeteo")` :300), `trip_alert` (:885), `cli` (:195), `_fetch_night_weather`/`_enrich_ensemble_for_trip`.

## Existing Specs

- `docs/reference/decision_matrix.md` — Provider-Auswahl (nur MET/MOSMIX-Ebene).
- Keine bestehende Spec zu Modell-Fallback bei HTTP-Fehler.

## Bestehende Tests (relevant)

- `tests/tdd/test_issue_1113_partial_outage_guard.py` — Teilausfall-Schwelle (>75 %), Scheduler-Retry/Backoff bei transientem 503, `partial_outage_hint`. Nutzt Offline-Fixtures `fixtures/openmeteo`.
- `tests/unit/test_provider_error_handling.py` — `has_error`/`error_message="[openmeteo] API error: 503"`.
- `tests/unit/test_model_metric_fallback.py`, `tests/integration/test_snapshot_plausibility.py` — WEATHER-05b Metrik-Fallback (nicht 503).
- **Keinen** Test für Modell-Fallback bei 503 und **keinen** für Provider-zu-Provider-Umschaltung → das ist die TDD-RED-Lücke.

## Risks & Considerations

- **Datenqualität/Metrik-Semantik:** Fallback auf gröberes Modell (z. B. ICON-D2 2 km → ICON-EU 7 km → ECMWF 40 km) darf Metrik-Semantik nicht brechen. Kette ist bereits nach Auflösung sortiert; ECMWF global garantiert Coverage.
- **Alpenraum:** AROME/ICON-D2 hochauflösend; bei Fallback auf ECMWF sinkt Auflösung deutlich — akzeptabel als „beste verfügbare" statt Totalausfall, aber im Briefing ggf. kenntlich machen (Provider/Modell-Meta).
- **Doppelte Modell-IDs:** `icon_d2` und `icon_eu` nutzen **denselben Endpoint** `/v1/dwd-icon` (openmeteo.py:115/131). Bei 503 auf `/v1/dwd-icon` bringt das Überspringen zum nächsten Endpoint (nicht nur nächster Modell-Eintrag) den eigentlichen Nutzen — Fallback muss auf **Endpoint-Ebene** ausweichen, nicht nur Modell-Eintrag.
- **Retry vs. Fallback-Reihenfolge:** Klären, ob erst Retry am selben Endpoint (Scheduler-Ebene) oder direkt Endpoint-Wechsel. Bei persistentem endpoint-spezifischem 503 (Incident-Muster) ist Endpoint-Wechsel der wirksame Hebel.
- **Kein Overfetch:** Fallback nur bei 5xx/Timeout auslösen, nicht bei 4xx (z. B. `start_date out of range`, Bug #353) — dort würde jedes Modell scheitern.
- **Cross-Provider (Stufe 2):** Nur `geosphere`, nur AT-Region, ohne Ensemble → begrenzter Nutzen, eigene Metrik-Lücken. Kandidat für separaten Scope/Folge-Issue statt in diesem Workflow zu erzwingen.
- **Beobachtbarkeit:** Fallback-Ereignisse müssen geloggt/diagnostizierbar sein (welches Modell übersprungen, welches lieferte) — sonst still-degradierte Briefings ohne Signal (vgl. #1114).

## Analysis

### Type
Feature (`priority:critical`) — strukturelle Redundanz im Datenpfad.

### Technischer Ansatz (Empfehlung, Tech-Lead-Entscheidung)

**Intra-Open-Meteo-Endpoint-Fallback-Schleife in `fetch_forecast`, strikt auf einen Provider begrenzt.**

1. **Neue private `_candidate_models(lat, lon) -> List[Tuple[id, grid_res_km, endpoint]]`** — reine Extraktion der bereits an drei Stellen vorhandenen Bounds-Filter-Logik (`select_model` Z.393-398, `_find_fallback_model` Z.332-338), sortiert nach `priority`. `select_model()` bleibt **unangetastet** (eigener Test-Contract `tests/unit/test_openmeteo_endpoint_routing.py`).
2. **Fallback-Loop in `fetch_forecast`** (ersetzt den Einzel-`select_model`+`_request`-Aufruf Z.750/801): iteriert über `_candidate_models`, **dedupliziert auf Endpoint-Ebene** via `seen_endpoints`-Set (icon_d2 und icon_eu teilen `/v1/dwd-icon` → zweiter Eintrag entfällt, da ein zweiter Call an denselben Endpoint bei endpoint-weitem 503 garantiert erneut scheitert). `params` sind modellunabhängig und bleiben über alle Versuche identisch.
3. **Fehler-Klassifikation im Loop:** 5xx (`{502,503,504}`) oder Timeout/ConnectError → **nächster Endpoint**; 4xx → **sofortiger Re-Raise** (kein Modell hilft, z. B. Bug #353 `start_date out of range`). Wiederverwendung von `_is_retryable_error` (Z.190) für die Unterscheidung.
4. **`ProviderRequestError.status_code`** (neu, optional in `base.py:82`) — strukturierte 5xx/4xx-Erkennung statt String-Matching. **Bonus:** `trip_report_scheduler._is_transient_fetch_error` (Z.66-68) liest `exc.status_code` bereits per `getattr`, bekommt es aber nie gesetzt → diese Erweiterung schließt eine latente Lücke und macht das dortige Text-Matching robust.
5. **Erfolgreiches Modell durchreichen:** `model_id`/`grid_res_km` werden lokale Variablen, die erst nach erfolgreichem Request feststehen — `_parse_response` (Z.804) UND der WEATHER-05b-Block (Z.857ff, nutzt `model_id` für Availability-Cache) müssen mit dem **tatsächlich erfolgreichen** Modell arbeiten, nicht dem ursprünglich gewählten. **Wichtigster Implementierungspunkt** (Variablen-Verwechslung vermeiden).
6. **Downgrade = komplette Übernahme** der Timeseries des Ersatzmodells (kein Merge — bei 5xx ist das Primärmodell komplett tot). Auflösung sinkt automatisch mit (`grid_res_km` aus erfolgreichem Modell). Ensemble/UV unabhängig vom Modell → kein Risiko.
7. **Beobachtbarkeit:** `meta.fallback_model` (existiert bereits, `models.py:83`) auf das Ersatzmodell setzen, wenn ≠ primär gewählt; `logger.warning("Model fallback: X (5xx) -> Y")`; `_log_api_call` protokolliert bereits jeden Versuch nach `openmeteo_calls.jsonl`. Optional `ForecastMeta.fallback_reason` zur Unterscheidung „Metrik-Fallback (05b)" vs. „5xx-Endpoint-Fallback".

**Fallback greift unabhängig vom (aktuell toten) `_request`-5xx-Retry** — sofortiger Endpoint-Wechsel bei 5xx. Das hätte den Incident sicher verhindert. Der latente Retry-Bug (`_request` retryt 5xx faktisch nie, weil `HTTPStatusError` vor dem tenacity-Decorator zu `ProviderRequestError` gewandelt wird) wird **NICHT** in diesem Workflow angefasst → **Folge-Issue** (Retry-Semantik auf kritischem Pfad nicht nebenbei ändern; Scheduler-Retry #1113 deckt kurze Flaps weiterhin ab).

### Affected Files (with changes)
| File | Change | Description |
|------|--------|-------------|
| `src/providers/openmeteo.py` | MODIFY | `_candidate_models` (neu), Fallback-Loop in `fetch_forecast`, `status_code` beim Error-Wrap setzen, `fallback_model`-Meta + Log |
| `src/providers/base.py` | MODIFY | `ProviderRequestError` um optionales `status_code` erweitern |
| `src/app/models.py` | MODIFY (optional) | `ForecastMeta.fallback_reason` (nur falls Unterscheidung nötig) |
| `tests/tdd/test_issue_1115_*.py` | CREATE | RED-Tests: 503-auf-Endpoint → Fallback greift, 4xx → kein Fallback, Endpoint-Dedup, `fallback_model`-Meta gesetzt |

### Scope Assessment
- Files: 2-3 Produktiv + 1 Test
- Estimated LoC: **+80-150** Produktivcode (ggf. LoC-Override nötig, 250-Limit; vorab User fragen)
- Risk Level: **HIGH** (Wetter-Datenpfad aller Briefings) — mitigiert durch strikte Scope-Begrenzung + 2 Adversary-Runden

### Out of Scope (→ Folge-Issues)
- **Cross-Provider-Fallback (geosphere):** AT-only, kein Coverage-Bounds-Check im Code, ignoriert `enrich_ensemble` (#288) — orthogonales Risiko, eigener Bounds-Check-Spike nötig. Separates Issue.
- **`_request`-5xx-Retry-Bugfix:** latenter Bug, eigenes Issue.

### Open Questions
- [ ] LoC-Override auf 500 nötig (Schätzung >250)? → User vor Implementierung fragen.
- [ ] `fallback_reason`-Feld einführen oder `fallback_model` allein genügt? → in Spec entscheiden.
