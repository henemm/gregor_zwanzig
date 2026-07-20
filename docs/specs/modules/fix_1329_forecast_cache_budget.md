---
entity_id: fix_1329_forecast_cache_budget
type: module
created: 2026-07-20
updated: 2026-07-20
status: draft
version: "1.0"
tags: [forecast, cache, budget, quota, openmeteo, alert, briefing]
---

# Forecast-Cache teilen + Verbrauchsbudget (Issue #1329, Scheibe C+)

## Approval

- [ ] Approved

## Purpose

Prod schöpft das open-meteo-Tageskontingent (10.000 Anfragen/Tag, Free-Tier auf
der Server-IP) chronisch aus: Prod-Log 2026-07-20 zeigt HTTP 429 **durchgehend
von Stunde 00 bis 14** (Spitze 78 Anfragen/h um 08 Uhr) bei 14 Trips, 19
Compare-Presets und 31 Orten — das Kontingent ist **ganztägig**, nicht nur
morgens, erschöpft. Root Cause: der vorhandene `WeatherCacheService` cached
nichts, weil jeder Aufrufer sich pro Aufruf eine neue, leere Instanz baut
(`segment_weather.py:60-64`) und der Alert-Pfad den Cache zusätzlich explizit
leert (`trip_alert.py:833`). Dieses Modul macht den Cache **prozessweit
geteilt** (Teil 1) und führt einen **Verbrauchsbegriff mit Prioritätssteuerung**
ein (Teil 2), damit Kontingent-Erschöpfung nicht mehr mitten im
Nutzer-Versand als 429 sichtbar wird, sondern vorher gemessen und gedrosselt
wird — ohne je ein Nutzer-Briefing zu verwerfen.

## Source

- **File:** `src/services/weather_cache.py` (Cache-Umbau: Singleton +
  koordinatenbasierter Schlüssel + TTL)
- **File:** `src/services/segment_weather.py` (Default-Cache-Injektion auf
  Singleton umstellen)
- **File:** `src/services/trip_alert.py` (`_cache.clear()`-Entfernung,
  Prioritäts-Tag `alert_check`)
- **File:** `src/services/compare_location_weather_source.py`
  (Prioritäts-Tag `alert_check`)
- **File:** `src/services/trip_report_scheduler.py`,
  `src/services/stage_weather.py` (Prioritäts-Tag `user_briefing`)
- **File:** `src/services/forecast_budget.py` (NEU — Zähler + Prioritätsgate)
- **File:** `internal/scheduler/forecast_budget_status.go` (NEU — Aggregation
  für `/api/scheduler/status`, analog `briefing_health.go`)
- **Identifier:** `WeatherCacheService`, `SegmentWeatherService`,
  `ForecastBudgetGate` (neu)

> **Schicht-Hinweis:** Cache/Budget-Kern ist Python-Core (`src/services/`,
> Prozess `gregor-python`, Port 8000/8001). Die Sichtbarkeit im
> Status-Endpunkt ist Go-API (`internal/scheduler/`, `internal/handler/`,
> Port 8090) und liest ausschließlich eine von Python geschriebene
> Zustandsdatei — analog zu `briefing_health.go`, das
> `data/diagnostics/openmeteo_calls.jsonl` liest, ohne selbst Python-Code
> aufzurufen. Kein Doppel-Pfad.

## Estimated Scope

- **LoC:** ~220-250 (Cache-Umbau ~60, Budget-Modul ~90, Call-Site-Wiring
  ~30, Go-Aggregation ~40-50)
- **Files:** ~9 (5 Python geändert, 1 Python neu, 1 Go neu, 1 Go geändert
  [`scheduler_status.go` bzw. `Scheduler.Status()`], Tests kommen in
  Phase 4 dazu)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `providers.base.get_provider` / `WeatherProvider.fetch_forecast` | upstream | Aufrufkompatible Signatur bleibt unverändert |
| `providers.openmeteo.OpenMeteoProvider.select_model` | upstream | Modellwahl aus lat/lon — muss in den Cache-Schlüssel einfließen |
| `services.throttle_store.ThrottleStore` | Vorbild | Datei-basierter, sperren-geschützter Zustand pro Prozess/Nutzer — Muster für den Budget-Zähler |
| `providers.openmeteo.AVAILABILITY_CACHE_PATH`-Muster | Vorbild | Fail-soft, TTL-basierter Datei-Cache ohne Lock |
| `app.loader._data_root()` / `GZ_DATA_DIR` | upstream | Bestimmt automatisch prod/staging-getrennten Datenpfad für den Budget-Zähler |
| `services.trip_alert.TripAlertService`, `services.compare_location_weather_source.CompareLocationWeatherSource` | downstream | Rufen `SegmentWeatherService` mit Priorität `alert_check` |
| `services.stage_weather.compute_stage_weather`, `services.trip_report_scheduler.TripReportSchedulerService` | downstream | Rufen `SegmentWeatherService` mit Priorität `user_briefing` |
| `internal/scheduler/briefing_health.go` | Vorbild | Aggregations-Muster: Go liest eine von Python geschriebene JSON-Datei fail-soft, keine Nutzeridentifikatoren |

## Implementation Details

### Teil 1 — Geteilter Cache

**1.1 Prozessweiter Singleton (`weather_cache.py`)**

```python
# Modul-Ebene in weather_cache.py
_shared_cache: Optional["WeatherCacheService"] = None
_shared_cache_lock = Lock()

def get_shared_weather_cache(ttl_seconds: int = 600) -> "WeatherCacheService":
    """Prozessweite Singleton-Instanz. Thread-sicher (Double-Checked-Locking);
    der Cache selbst ist bereits intern lock-geschuetzt (WeatherCacheService),
    dieses Lock schuetzt nur die Erst-Erzeugung."""
    global _shared_cache
    if _shared_cache is None:
        with _shared_cache_lock:
            if _shared_cache is None:
                _shared_cache = WeatherCacheService(ttl_seconds=ttl_seconds)
    return _shared_cache

def reset_shared_weather_cache_for_tests() -> None:
    """Nur fuer Tests: setzt den Singleton zurueck (Test-Isolation)."""
    global _shared_cache
    with _shared_cache_lock:
        _shared_cache = None
```

`segment_weather.py:61-63` verwendet `get_shared_weather_cache()` statt
`WeatherCacheService()` als Default, wenn kein `cache` übergeben wird.
Explizite Injektion (`SegmentWeatherService(provider, cache=...)`, wie in
Tests genutzt) bleibt unverändert möglich und übersteuert den Singleton.

**1.2 Cache-Ebene: rohe Provider-Zeitreihe + Fenster-Abdeckungsregel
(korrigiert nach Adversary-Fund F001, siehe Changelog)**

**Ursprünglicher Entwurf (verworfen):** Der Cache sollte das ABGELEITETE
`SegmentWeatherData` unter einem Ort/Stunde-Schlüssel speichern. Der
Adversary fand dabei einen kritischen Fehler: ein Cache-Schlüssel, der nur
Ort + Stunde beschreibt, aber Segment-**Identität** (`segment_id`) und ein
fenstergebundenes **Aggregat** im Wert speichert, liefert bei
unterschiedlicher Fensterdauer (z. B. Trip 4h vs. Compare 1h an derselben
Koordinate/Stunde) die Identität UND das Aggregat des FALSCHEN Aufrufers
zurück. Da sowohl `trip_alert.py` als auch `deviation_alert_engine.py`
`cached` gegen `fresh` **per Identität** matchen, führt ein
Identitäts-Leck dort zu einem STILL VERSCHLUCKTEN Alarm-Ausfall (kein
Fehler, kein Log) — End-to-End reproduziert über
`CompareLocationWeatherSource().fetch("compare-point-99", …)`, das die
`segment_id` eines Trip-Segments zurücklieferte.

**Korrigierter Entwurf:** Der Cache speichert NUR die rohe
`NormalizedTimeseries` (die Provider-Antwort), NIEMALS ein abgeleitetes
`SegmentWeatherData`. Identität und Aggregat entstehen bei JEDEM Aufruf
neu, beim Aufrufer selbst (`SegmentWeatherService._aggregate_for_segment`),
egal ob die zugrundeliegende Zeitreihe aus dem Cache kam oder frisch
geholt wurde.

Der Cache-**Bucket**-Schlüssel (Ort/Modell/Enrich-Flags, OHNE Zeitfenster):

```python
def _bucket_key(
    self,
    segment: TripSegment,
    enrich_ensemble: bool,
    enrich_snow: bool,
    model_id: str,
) -> str:
    lat = round(segment.start_point.lat, 4)   # ~11 m Aufloesung
    lon = round(segment.start_point.lon, 4)
    return f"{lat}_{lon}_{model_id}_{enrich_ensemble}_{enrich_snow}"
```

Jeder Eintrag trägt zusätzlich sein tatsächlich abgedecktes Zeitfenster
(`window_start`, `window_end`, UTC) als Metadaten. `get()` durchsucht die
Einträge desselben Buckets und liefert den ersten FRISCHEN Treffer, dessen
Fenster das angeforderte Fenster **vollständig abdeckt**:

```python
if entry.window_start <= req_start and entry.window_end >= req_end:
    ...  # Treffer -- liefert die ROHE Zeitreihe + den Original-Fetch-
         # Zeitpunkt (`cached_at`) zurueck, NIE Identitaet/Aggregat
```

Ein Eintrag mit einem KLEINEREN Fenster als angefordert ist NIE ein
Treffer (kein stilles Kürzen). Das erlaubt weiterhin die Teilung aus AC-4
(ein breiteres Trip-Fenster bedient eine engere Compare-Anfrage), schließt
F001 aber strukturell aus: der Aufrufer schneidet sich sein Fenster IMMER
selbst aus der (ggf. breiteren) Zeitreihe heraus und aggregiert nur
darüber — nie wird ein fremdes Aggregat oder eine fremde Identität
zurückgegeben.

**Modellkennung ohne Wegwerf-Instanz:** `SegmentWeatherService.
_resolve_model_id(lat, lon)` fragt `getattr(self._provider, "select_model",
None)` auf dem BEREITS injizierten Provider ab (kein zusätzliches
`OpenMeteoProvider()` pro Cache-Zugriff) und ruft ihn bei Vorhandensein vor
dem Cache-Zugriff auf (reine Koordinatenfunktion, kein Netzzugriff).
Provider ohne diese Methode (GeoSphereProvider, FixtureProvider,
Test-Fakes) fallen auf `provider.name` zurück. Ersetzt die ursprüngliche
Spec-Vorgabe eines direkten Modul-Imports von `select_model` — das ist
tatsächlich eine Instanzmethode (`providers/openmeteo.py:411`), kein
Modul-Level-Funktion (Tech-Lead-Entscheidung 2026-07-20).

**1.3 TTL 10 Minuten**

`get_shared_weather_cache()` Default `ttl_seconds=600` (kürzer als der
15-Minuten-Alarmtakt der Go-Cron-Jobs, `internal/scheduler/scheduler.go:110`).
Jeder Ort wird pro 15-Minuten-Zyklus höchstens einmal geholt (Cache-Treffer
für den Rest des Zyklus), aber nie länger als 10 Minuten alt ausgeliefert.
Der bisherige `WeatherCacheService(ttl_seconds=3600)`-Default bleibt nur als
Klassen-Default für explizite Injektion (z. B. isolierte Tests) bestehen —
im produktiven Singleton-Pfad gilt ausschließlich 600 s.

**1.4 `trip_alert.py:833` `_cache.clear()` entfernen**

Der Aufruf erzwingt aktuell einen Upstream-Fetch bei jedem Alarm-Check
(„immer frische Daten"). Mit geteiltem Cache + 10-Minuten-TTL ist das nicht
mehr nötig: die maximale Datenalterung im Alarmpfad ist durch den TTL bereits
auf ≤ 10 Minuten begrenzt, unabhängig davon, ob ein anderer Aufrufer (z. B.
das letzte Briefing für denselben Ort) den Eintrag kurz zuvor gefüllt hat.
Das ist eine **bewusste Verhaltensänderung** — vorher „garantiert taufrisch
pro Check", nachher „garantiert ≤ 10 Min alt" — abgedeckt durch AC-6.

### Teil 2 — Verbrauch sichtbar + steuerbar

**2.1 `ForecastBudgetGate` (neu, `src/services/forecast_budget.py`)**

Datei-basierter Tageszähler pro Provider, Muster `ThrottleStore` /
`AVAILABILITY_CACHE_PATH`: Reload-Merge-Write unter `fcntl`-Sperre (mehrere
Job-Requests im selben Prozess/Tag), Pfad automatisch prod/staging-getrennt
über `app.loader._data_root()` (kein User-Namespace — der Zähler ist
prozess-/instanzweit, nicht pro Nutzer). Datei:
`<data_root>/diagnostics/forecast_budget.json`, Struktur:

```json
{
  "date": "2026-07-20",
  "calls": {"openmeteo": 4213},
  "cache_hits": 8877,
  "cache_misses": 4213
}
```

Tageswechsel: beim ersten Zugriff nach Datumswechsel wird die Datei
zurückgesetzt (Read-Modify-Write, kein Replace fremder Felder — Datenschema-
Pflicht gilt sinngemäß, auch wenn dies kein Nutzer-Datenschema ist).

```python
class ForecastBudgetGate:
    DAILY_BUDGET = 9000          # Sicherheitsmarge unter dem 10k-Limit
    POLLING_THRESHOLD = 0.80     # ab 80% Budget: polling abweisen
    BRIEFING_ONLY_THRESHOLD = 0.95  # ab 95%: nur noch user_briefing

    def allow(self, priority: str) -> bool:
        """Fail-open: jeder Lese-/Zaehlfehler -> True (nie blockieren)."""
        if priority == "user_briefing":
            return True
        try:
            ratio = self._read_usage_ratio()
        except Exception:
            return True  # kaputter/unlesbarer Zaehler blockiert nie
        if priority == "polling":
            return ratio < self.POLLING_THRESHOLD
        if priority == "alert_check":
            return ratio < self.BRIEFING_ONLY_THRESHOLD
        return True  # unbekannte Prioritaet -> nie drosseln (fail-open)

    def record_call(self) -> None: ...      # increments calls.openmeteo
    def record_cache_hit(self) -> None: ...
    def record_cache_miss(self) -> None: ...
    def snapshot(self) -> dict: ...          # fuer Observability-Export
```

Priorität wird vom Aufrufer als String übergeben:

| Priorität | Aufrufer | Schwelle |
|---|---|---|
| `user_briefing` | `trip_report_scheduler.py`, `stage_weather.py` (Briefing/Preview/Report-Versand) | nie gedrosselt |
| `alert_check` | `trip_alert.py:_fetch_fresh_weather`, `compare_location_weather_source.py:fetch` | gedrosselt ab 95 % Tagesbudget |
| `polling` | aktuell kein produktiver Aufrufer verdrahtet (siehe Known Limitations) — Mechanismus liegt für künftige Hintergrund-/Low-Priority-Aufrufer bereit | gedrosselt ab 80 % Tagesbudget |

`SegmentWeatherService.fetch_segment_weather()` bekommt einen neuen
optionalen Parameter `priority: str = "user_briefing"` (Default = nie
drosseln, rückwärtskompatibel für alle nicht angepassten Aufrufer). Vor dem
Upstream-Fetch (Schritt 4 im bestehenden Algorithmus,
`segment_weather.py:137-146`) prüft die Methode
`ForecastBudgetGate().allow(priority)`; bei `False` wird — analog zum
bestehenden `ProviderRequestError`-Pfad (`:147-158`) — ein
`SegmentWeatherData(has_error=True, error_message="budget_throttled")`
zurückgegeben statt eine Exception zu werfen (kein neuer Fehlerpfad für
Aufrufer nötig).

**2.2 Fail-open**

Jede Zähler-Lese-/Schreiboperation ist in `try/except Exception` gekapselt
und liefert im Fehlerfall den permissiven Wert (`allow()` → `True`,
`snapshot()` → Nullen mit `"status": "unavailable"`). Kein Zähler-Defekt
darf einen Versand verhindern — Muster `openmeteo.py:258-269`
(`_load_availability_cache` gibt bei Fehler `None` zurück, kein Crash).

**2.3 Observability im Status-Endpunkt**

`data/diagnostics/forecast_budget.json` wird analog zu
`data/diagnostics/openmeteo_calls.jsonl` von Go gelesen. Neue Funktion
`ForecastBudgetStatus(dataDir string) map[string]any` in
`internal/scheduler/forecast_budget_status.go` (Datei-Read fail-soft, exakt
das Muster aus `briefing_health.go:aggregateCorruptTrips`), eingehängt in
`Scheduler.Status()` (dieselbe Stelle, an der `BriefingHealth()` bereits
eingehängt ist) unter einem neuen Top-Level-Key `forecast_budget`:

```json
{
  "forecast_budget": {
    "date": "2026-07-20",
    "calls_today": 4213,
    "daily_budget": 9000,
    "usage_ratio": 0.468,
    "cache_hit_ratio": 0.678,
    "throttle_level": "none"
  }
}
```

`throttle_level` ∈ `{"none", "polling_throttled", "briefing_only"}`,
abgeleitet aus `usage_ratio` gegen dieselben zwei Schwellen wie
`ForecastBudgetGate` (Python bleibt Single Source of Truth für die
Schwellenwerte — Go berechnet nur zur Anzeige, keine eigene
Entscheidungslogik, um Drift zwischen den beiden Schichten zu vermeiden;
die Schwellen 80 %/95 % werden deshalb als Kommentar mit Verweis auf
`forecast_budget.py` dokumentiert, nicht als zweite Quelle).

## Expected Behavior

- **Input:** Zwei Aufrufer (z. B. Trip-Alert-Check und Briefing-Versand)
  fragen dieselbe Koordinate/Stunde ab; Budget-Zähler nähert sich dem
  Tageslimit.
- **Output:** Der zweite Aufruf liefert den gecachten Wert ohne
  Upstream-Call, solange der Cache-Eintrag ≤ 10 Minuten alt ist. Bei
  Budget-Druck werden `polling`- und dann `alert_check`-Aufrufe mit
  `has_error=True, error_message="budget_throttled"` abgewiesen;
  `user_briefing`-Aufrufe laufen immer durch. `/api/scheduler/status` zeigt
  Tagesverbrauch, Cache-Trefferquote und aktive Drosselstufe.
- **Side effects:** Neue Zustandsdatei `data/diagnostics/forecast_budget.json`
  (prod/staging getrennt über den Datenpfad); Wegfall des expliziten
  Cache-Clears im Alarmpfad; geteilter In-Memory-Cache-Zustand über alle
  Aufrufer im selben Prozess (Speicher-Footprint unverändert, LRU-Cap 100
  bleibt bestehen).

## Acceptance Criteria

- **AC-1:** Given zwei aufeinanderfolgende Aufrufe von `fetch_segment_weather` für **dieselbe Koordinate und Stunde** (unterschiedliche `segment_id`, z. B. zwei verschiedene Trips) innerhalb des TTL / When der zweite Aufruf läuft / Then geht genau **ein** Upstream-Call an den zählenden Fake-Provider (der zweite Aufruf ist ein Cache-Hit).
  - Test: Zählender Fake-Provider (kein `patch()`), zwei `SegmentWeatherService`-Instanzen mit dem geteilten Singleton-Cache, zwei Trip-Segmente mit identischer Koordinate/Stunde aber verschiedener `segment_id` — Provider-Call-Zähler bleibt bei 1.

- **AC-2:** Given zwei Aufrufe mit **unterschiedlicher** Koordinate (oder unterschiedlicher Stunde) / When beide laufen / Then gehen **zwei** Upstream-Calls raus (kein falscher Cache-Treffer).
  - Test: Gleicher Fake-Provider-Zähler, zwei Segmente mit abweichender Koordinate — Zähler steht bei 2.

- **AC-3:** Given ein Cache-Eintrag, dessen Alter den TTL (10 Min) überschritten hat / When ein weiterer Aufruf für dieselbe Koordinate/Stunde erfolgt / Then wird erneut vom Provider geholt (kein stiller Stale-Serve über den TTL hinaus).
  - Test: Injizierbare Uhr (kein `sleep`) im Cache/Gate — Zeit künstlich über 600 s vorstellen, dann zweiter Aufruf zählt als neuer Provider-Call.

- **AC-4:** Given zwei verschiedene Trips (oder ein Trip und ein Compare-Preset) am selben Ort / When beide im selben 15-Minuten-Zyklus ihr Wetter abrufen / Then teilen sie sich einen einzigen Upstream-Call (Beweis für die Koordinaten-basierte statt segment_id-basierte Schlüsselbildung).
  - Test: Zwei unabhängige `SegmentWeatherService`-Aufrufe wie in Prod (`trip_alert.py`-Aufrufmuster und `compare_location_weather_source.py`-Aufrufmuster) mit identischer Koordinate über den geteilten Singleton — ein Provider-Call.

- **AC-5:** Given das Tagesbudget ist zu ≥ 95 % ausgeschöpft (simuliert) / When ein `alert_check`- oder `polling`-Aufruf erfolgt / Then wird er abgewiesen (`has_error=True`, `error_message="budget_throttled"`), **aber** ein `user_briefing`-Aufruf im selben Zustand läuft unverändert durch und erreicht den Provider.
  - Test: `ForecastBudgetGate` mit vorpräpariertem Zählerstand (95 % simuliert) — `allow("alert_check")`/`allow("polling")` liefern `False`, `allow("user_briefing")` liefert `True`; End-to-End über `fetch_segment_weather(priority=...)` bestätigt denselben Effekt am Rückgabewert.

- **AC-6:** Given der Alarm-Check ruft `fetch_segment_weather` ohne expliziten `cache.clear()` auf (Verhaltensänderung aus `trip_alert.py:833`) / When die zurückgelieferten Daten geprüft werden / Then ist ihr Alter (`cached_at` bis Aufrufzeitpunkt) nie größer als der TTL (10 Min) — die Alarm-Frische bleibt trotz Wegfall des expliziten Clears erhalten.
  - Test: Cache mit einem frischen (< 10 Min) und einem künstlich gealterten (> 10 Min) Eintrag; Alarm-Fetch-Pfad ohne `clear()`-Aufruf liefert für den gealterten Eintrag einen neuen Provider-Call, für den frischen einen Cache-Hit — in beiden Fällen ist das Ergebnisalter ≤ TTL.

- **AC-7:** Given die Budget-Zählerdatei ist beschädigt (kaputtes JSON) oder nicht lesbar / When ein beliebiger Aufruf (`user_briefing`, `alert_check` oder `polling`) erfolgt / Then wird er **nicht** blockiert (fail-open) — der Versand läuft trotz kaputtem Zähler.
  - Test: `forecast_budget.json` mit ungültigem JSON vorab schreiben, `ForecastBudgetGate.allow(...)` für alle drei Prioritäten aufrufen — alle liefern `True`; kein geworfener Fehler.

- **AC-8:** Given normale Betriebslage (kein Budget-Druck) / When `/api/scheduler/status` abgefragt wird / Then enthält die Antwort einen `forecast_budget`-Block mit `calls_today`, `cache_hit_ratio` und `throttle_level`, dessen Werte mit dem zuvor geschriebenen Zählerstand übereinstimmen.
  - Test: Zählerdatei mit bekannten Werten vorschreiben, `ForecastBudgetStatus(dataDir)` (Go) aufrufen, Felder gegen die vorgeschriebenen Werte prüfen; fehlende Datei liefert einen Default-Block (`status: "unavailable"`), keinen Panic.

- **AC-9:** Given zwei Aufrufer mit **derselben Koordinate/Stunde**, aber **abweichender Fensterdauer** (z. B. ein 4h-Trip-Segment und ein 1h-Compare-Punkt) / When der zweite Aufrufer sein Wetter über den geteilten Cache abruft (Cache-Treffer gegen den breiteren, zuerst gecachten Eintrag) / Then erhält er seine **eigene** `segment_id`/`duration_hours` und ein **ausschließlich über sein eigenes Fenster** berechnetes Aggregat — niemals die Identität oder das Aggregat des ersten Aufrufers (Adversary-Fund F001).
  - Test: Zwei `SegmentWeatherService`-Aufrufe (4h zuerst, 1h danach) über einen Fake-Provider, der pro Stunde einen unterscheidbaren Wert liefert (`t2m_c == Stunde`) — der zweite Aufruf liefert `segment_id == "compare-point-99"` und ein Aggregat, das NUR die eigene Stunde abdeckt, nicht den 4h-Bereich des ersten Aufrufers. Zusätzlich End-to-End über die echten Produktionspfade (`TripAlertService._fetch_fresh_weather` → `CompareLocationWeatherSource.fetch()`) und ein Test, der belegt, dass ein zu KLEINES gecachtes Fenster eine größere Anfrage NIE bedient (kein stilles Kürzen).

## Known Limitations

- **Kein Neustart-Überstand:** Der geteilte Cache ist ein reiner
  In-Memory-Singleton. Ein Deploy-Neustart von `gregor-python`
  (Prod/Staging) leert ihn vollständig. Das ist bewusst in Kauf genommen —
  der TTL ist mit 10 Minuten ohnehin kurz, ein Cache-Verlust beim Neustart
  ist praktisch gleichwertig zu einem regulären TTL-Ablauf.
- **Nur prozessweit wirksam (Single-Worker-Annahme):** Der Singleton lebt im
  Adressraum eines Prozesses. `gregor-python` läuft ohne `--workers`-Flag
  (kein Treffer im Repo für `uvicorn.*--workers` oder Multi-Worker-Start) —
  Single-Worker ist der aktuelle Betriebszustand. Würde künftig auf mehrere
  Worker/Prozesse skaliert, wäre der In-Memory-Cache pro Worker getrennt und
  die Teilungswirkung entsprechend geringer (nicht falsch, nur schwächer) —
  eine prozessübergreifende Lösung (z. B. Datei- oder Redis-basiert wie
  `ThrottleStore`) wäre dann ein Folge-Ticket.
- **Identitätstrennung Prod/Staging beim Anbieter nicht Teil dieser
  Scheibe:** Diese Scheibe behebt die Kontingent-Erschöpfung durch
  Teilung/Drosselung auf Anwendungsseite. Die separate Frage, ob Prod und
  Staging überhaupt mit **derselben** open-meteo-Server-IP-Identität
  sprechen sollten (Punkt 3 der #1329-Architektur-Einordnung), ist
  ausdrücklich **nicht** Gegenstand dieser Spec — eigenes Ticket.
- **`polling`-Priorität aktuell ohne produktiven Aufrufer:** Der Mechanismus
  (`ForecastBudgetGate.allow("polling")`, Schwelle 80 %) ist implementiert
  und getestet (AC-5, AC-7), aber keiner der vier bestehenden
  Scheduler-Jobs ruft `fetch_segment_weather` aktuell mit `priority="polling"`
  auf — die identifizierten Aufrufer sind entweder `user_briefing`
  (Briefing/Preview-Report-Pfade) oder `alert_check` (Trip-/Compare-Alarm).
  Die Stufe steht für künftige Hintergrund-Aufrufer bereit, ohne dass diese
  Scheibe einen erfinden muss.
- **Radar-/Nowcast-Pfad bleibt unberührt:** `radar_service.py` nutzt einen
  eigenen Namensraum (BrightSky/RADOLAN, GeoSphere INCA, RadarDPC,
  AROME-FR-HD, teils open-meteo `minutely_15` als Fallback) und wird von
  dieser Scheibe nicht angefasst — auch der open-meteo-Fallback-Fall des
  Radar-Pfads bleibt außerhalb des hier eingeführten Cache/Budget-Gates
  (andere Auflösung, kein gemeinsamer Code-Pfad mit `fetch_forecast` über
  `SegmentWeatherService`).
- **`comparison_engine.py` (Compare-Report-Versand) profitiert nicht vom
  Cache:** Der Compare-Report-Pfad ruft `ForecastService.get_forecast()`
  direkt (`comparison_engine.py:348-357`), nicht über
  `SegmentWeatherService` — er nutzt daher weder den geteilten Cache noch
  das Prioritäts-Gate. Das ist ein bewusster Scope-Schnitt (Compare-Reports
  sind ohnehin `user_briefing`-äquivalent, also nie gedrosselt; der
  entgangene Cache-Vorteil ist ein Folge-Optimierungs-Ticket, kein
  Korrektheitsproblem dieser Scheibe).
- **Sicherheitsmarge statt Ist-Limit:** `DAILY_BUDGET = 9000` ist absichtlich
  unter dem tatsächlichen 10.000er-Limit gewählt, um Uhrzeiten-Drift
  zwischen dem lokalen Tageszähler und dem Reset-Zeitpunkt des
  open-meteo-Kontingents abzufedern; das exakte Reset-Verhalten von
  open-meteo ist nicht dokumentiert/verifiziert.
- **`forecast.py` und `trip_forecast.py` umgehen den Cache ebenfalls
  (Adversary-Fund F003, LOW):** Nicht nur `comparison_engine.py` (bereits
  oben dokumentiert) ruft Forecast-Daten außerhalb von
  `SegmentWeatherService`/`WeatherCacheService` ab — auch `forecast.py`
  und `trip_forecast.py` gehen an Cache und Budget-Gate vorbei. Bewusster
  Scope-Schnitt dieser Scheibe (kein Korrektheitsproblem, da diese Pfade
  ohnehin `user_briefing`-äquivalent sind, also nie gedrosselt würden);
  eine Konsolidierung aller Forecast-Abrufpfade auf `SegmentWeatherService`
  wäre ein Folge-Ticket.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0032
- **Rationale:** Zwei gekoppelte, aber trennbare Grundsatzentscheidungen:
  (1) Cache-Teilung über einen **prozessweiten In-Memory-Singleton** statt
  eines prozessübergreifenden/persistenten Caches (z. B. Redis oder
  datei-basiert wie `ThrottleStore`) — gerechtfertigt durch die verifizierte
  Single-Worker-Topologie (kein `--workers`) und den kurzen TTL, der einen
  Neustart-Verlust praktisch bedeutungslos macht; spart die
  Betriebskomplexität eines externen Cache-Dienstes. (2) Budget-Steuerung
  über **statische Prioritätsklassen mit festen Schwellen** statt eines
  dynamischen/adaptiven Rate-Limiters — einfacher zu verifizieren
  (`allow(priority)` ist eine reine, deterministische Funktion des
  Tageszählers) und passt zum Produktgrundsatz „kein Nutzer-Briefing wird je
  wegen Budget verworfen". Beide Entscheidungen sind an die aktuelle
  Ein-Prozess-Topologie gebunden und müssten bei einer Skalierung auf
  mehrere Worker überarbeitet werden (siehe Known Limitations).

## Test Plan

Kern-Schicht, netzfrei, kein Mock-Theater (Test-Politik siehe `CLAUDE.md`):

- **Zählender Fake-Provider** (kein `patch()`/`Mock()`): ein
  `WeatherProvider`, dessen `fetch_forecast()` echte, deterministische
  `NormalizedTimeseries`-Objekte liefert und dabei einen Aufruf-Zähler
  hochzählt — kein Test spiegelt die eigene Annahme, sondern beobachtet
  Verhalten (AC-1 bis AC-4).
- **Injizierbare Uhr statt `sleep`**: TTL-Ablauf (AC-3, AC-6) wird über eine
  im Test kontrollierte Zeitquelle simuliert (z. B. `cached_at` im
  `CacheEntry` direkt manipulierbar oder ein injizierbares `now()` in
  `WeatherCacheService`/`ForecastBudgetGate`), nicht über reale Wartezeit.
- **Budget-Simulation**: `ForecastBudgetGate` mit vorab geschriebenem
  Zählerstand (Datei direkt vorbereiten, kein Mock der Klasse) für AC-5;
  kaputte Datei (ungültiges JSON) für AC-7.
- **Go-Seite**: `internal/scheduler/forecast_budget_status_test.go` — Datei
  mit bekannten Werten schreiben, `ForecastBudgetStatus()` aufrufen, Felder
  vergleichen (AC-8); Fehlerfall (fehlende Datei) separat.
- **Alarm-Frische (AC-6)**: End-to-End über `_fetch_fresh_weather`
  (`trip_alert.py`) ohne den entfernten `_cache.clear()`-Aufruf — beweist,
  dass der Fix keine Regression bei der Alarm-Aktualität einführt.
- Live-E2E (Staging, nur `/e2e-verify`): `/api/scheduler/status` nach einem
  echten Alert-/Briefing-Zyklus abfragen und `forecast_budget`-Block auf
  Plausibilität prüfen (Zähler > 0 nach echtem Lauf).

## Changelog

- 2026-07-20: Initial spec created (Issue #1329, Scheibe C+)
- 2026-07-20: Adversary-Verdict BROKEN nach erster Implementierung —
  F001 (CRITICAL, behoben): Cache-Ebene auf rohe Provider-Zeitreihe +
  Fenster-Abdeckungsregel umgestellt (Abschnitt 1.2 korrigiert, AC-9
  ergänzt); F002 (MEDIUM, behoben): Tageszähler auf UTC-Datumsgrenze
  umgestellt (`allow(priority, now=...)`); F003 (LOW): Known Limitations um
  `forecast.py`/`trip_forecast.py` als weitere Cache-Umgeher ergänzt.
