---
entity_id: fix_1329_c2_radar_nowcast_cache
type: module
created: 2026-07-20
updated: 2026-07-20
status: draft
version: "1.0"
tags: [radar, nowcast, cache, budget, quota, openmeteo, alert]
---

# Radar-Nowcast-Cache + Budget-Anbindung (Issue #1329, Scheibe C2)

## Approval

- [ ] Approved

## Purpose

Nach Auslieferung von Scheibe C (`31e807e4`, geteilter Forecast-Cache +
`ForecastBudgetGate`) zeigt die Messung vom 2026-07-20: **555 von 557**
fehlgeschlagenen open-meteo-Aufrufen stammen aus
`radar_service.get_nowcast()`, nur 2 aus dem Forecast-Pfad. `radar_service.py`
hat weder Cache noch Budget-Anbindung — jeder Aufruf löst mindestens einen
HTTP-Request aus, und zwei unabhängige Scheduler-Jobs (Trip-Radar,
Compare-Radar) holen denselben Ort unabhängig voneinander. Dieses Modul zieht
den Nowcast-Pfad in dieselbe geteilte Schicht wie den Forecast-Pfad: ein
neuer, radar-eigener Frame-Cache (TTL 300s) plus Anbindung an den
**bestehenden** `ForecastBudgetGate` (derselbe Tages-Topf, keine zweite
Zählung). Zusätzlich behebt es einen bei der Analyse gefundenen
Doppelverbrauch: ein fehlgeschlagener open-meteo-Call (429) löste bisher
einen ZWEITEN open-meteo-Call auf denselben Endpunkt aus (AROME-FR-Fehlschlag
→ Fallback `minutely_15`, derselbe Provider).

**Nachtrag (PO-Direktive „Tests dürfen Prod nie belasten"):** Bei der
Umsetzung dieser Scheibe wird zusätzlich ein bestehender Prod-Schutz-Lücke im
Radar-Pfad geschlossen: der Offline-Schalter `GZ_TEST_FIXTURE_DIR`
(`providers/base.py:144`, aktiviert automatisch für JEDEN nicht
`@pytest.mark.live`-markierten Testlauf über `tests/conftest.py:19-32`) wirkt
bisher NUR auf `get_provider("openmeteo")` (Forecast-Pfad). Der Radar-Pfad
umgeht ihn vollständig, weil `_fetch_openmeteo_15`
(`radar_service.py:317-363`) `httpx` direkt aufruft, ebenso wie die
BrightSky-/GeoSphere-/RadarDPC-Provider-Konstruktionen in `_fetch_brightsky`,
`_fetch_geosphere_inca`, `_fetch_radar_dpc`. Verifiziert: mehrere bestehende
Kern-Tests (u. a. `test_feature_761_icon_d2_nowcast.py:40-54,75-93` — Docstring
„echte API-Calls, kein Mock", NICHT `live`-markiert) konstruieren
`RadarNowcastService()` ohne `frame_source` und lösen dadurch heute bei
JEDEM `pytest`-Lauf reale HTTP-Requests an open-meteo/DWD aus — exakt der
Mechanismus, der laut Root-Cause-Analyse das Tageskontingent leert. Diese
Scheibe schließt die Lücke am selben Funnel, der ohnehin für Cache/Budget
angefasst wird (siehe Implementation Details Abschnitt 8).

## Source

- **File:** `src/services/radar_cache.py` (NEU — Frame-Cache + Singleton,
  analog `weather_cache.py::get_shared_weather_cache`)
- **File:** `src/services/radar_service.py` (Cache- und Budget-Einbindung in
  `RadarNowcastService`; zusätzlich Offline-Fixture-Guards in
  `_fetch_openmeteo_15`, `_fetch_brightsky`, `_fetch_geosphere_inca`,
  `_fetch_radar_dpc`)
- **File:** `fixtures/radar/minutely_15.json` (NEU — deterministische,
  trockene Offline-Frames, Muster `fixtures/openmeteo/*.json`)
- **File:** `src/services/trip_alert.py` (`get_nowcast(..., priority="polling")`)
- **File:** `src/services/compare_radar_alert.py` (`get_nowcast(..., priority="polling")`)
- **File:** `src/services/trip_command_processor.py` (`/jetzt`-Befehl,
  `priority="user_briefing"` — Default, explizit dokumentiert)
- **Identifier:** `RadarNowcastCacheService`, `get_shared_radar_cache`,
  `RadarNowcastService.get_nowcast` (erweitert), `ForecastBudgetGate`
  (wiederverwendet, unverändert), `_offline_fixture_active`,
  `_load_radar_fixture_frames` (neu, radar_service.py)

> **Schicht-Hinweis:** Python-Core (`src/services/`, Prozess `gregor-python`,
> Port 8000/8001). Kein Go-Anteil — die Radar-Aufrufe zahlen in denselben
> Zähler ein, den `internal/scheduler/forecast_budget_status.go` (Scheibe C)
> bereits über `/api/scheduler/status` sichtbar macht; kein neuer
> Observability-Endpunkt nötig.

## Estimated Scope

- **LoC:** ~190-230 (neues Cache-Modul ~70, `radar_service.py`-Änderungen
  ~60-70, drei Call-Site-Anpassungen ~10-15, Offline-Fixture-Guards +
  Fixture-Loader ~40-60; `fixtures/radar/minutely_15.json` als Datendatei
  nicht LoC-relevant)
- **Files:** 7 (2 Python/Daten neu [`radar_cache.py`,
  `fixtures/radar/minutely_15.json`], 4 Python geändert; Tests kommen in
  Phase 4 dazu)
- **Effort:** medium (LoC-Zuwachs durch Punkt 8 gegenüber der ursprünglichen
  Schätzung — falls das 250-LoC-Workflow-Limit dadurch überschritten wird,
  ist ein `loc_limit_override` mit PO-Erlaubnis einzuholen, nicht eigenmächtig
  zu setzen)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `services.weather_cache.get_shared_weather_cache` | Vorbild | Muster: prozessweiter Singleton, Double-Checked-Locking, Test-Reset-Funktion |
| `services.forecast_budget.ForecastBudgetGate` | reused | **Keine neue Klasse** — Radar zahlt in denselben Tages-Zähler (`PROVIDER="openmeteo"`) wie der Forecast-Pfad ein; `allow(priority)`/`record_call()`/`record_cache_hit()`/`record_cache_miss()` unverändert übernommen |
| `services.segment_weather.SegmentWeatherService.fetch_segment_weather` | Vorbild | Budget-Anbindungs-Reihenfolge: Cache-Hit → `record_cache_hit()`; Miss → `record_cache_miss()` → `allow(priority)` → bei Ablehnung kein HTTP-Call; `record_call()` unmittelbar vor dem echten Fetch |
| `services.radar_service.RadarNowcastService` | downstream/Source | Einbaupunkt für Cache + Budget-Gate + Doppelverbrauch-Fix |
| `services.trip_alert.TripAlertService.check_radar_alerts`, `services.compare_radar_alert.CompareRadarAlertService.check_all_compare_presets` | downstream | Rufen `get_nowcast(..., priority="polling")` |
| `services.trip_command_processor._show_now` (`/jetzt`) | downstream | Ruft `get_nowcast(..., priority="user_briefing")` — Nutzeraktion, nie gedrosselt |
| `providers.brightsky.RadarFrame` | upstream | Cache-Wert-Typ (rohe Frame-Liste, unverändert) |
| `providers.base.get_provider` (`GZ_TEST_FIXTURE_DIR`-Aktivierung, `:144`) | Vorbild | Identische Aktivierungsregel (`os.environ.get(...).strip()`-Wahrheitswert) für den neuen Radar-Offline-Schalter — EIN Signal, kein neuer Env-Var-Name |
| `providers.fixture.FixtureProvider` | Vorbild | Muster: Re-Stempelung der Fixture-Zeitstempel relativ zu „jetzt" (`fetch_forecast`, Zeile 110-117), fail-soft bei fehlender/kaputter Fixture-Datei |
| `tests/conftest.py::_use_fixture_provider` (Zeile 19-32) | upstream | Setzt `GZ_TEST_FIXTURE_DIR` automatisch für JEDEN nicht `@pytest.mark.live`-Test — der Radar-Offline-Pfad greift dadurch für den kompletten Bestand ohne Test-Datei-Änderungen |

## Implementation Details

### 1. Neuer Frame-Cache (`radar_cache.py`)

Analog zu `get_shared_weather_cache()`, aber bewusst **eigenständig und
einfacher** (kein „Covers"-Fenster-Konzept wie bei `WeatherCacheService` —
ein Nowcast-Frame-Satz ist keine feste Zeitspanne, sondern eine rollierende
Serie; ein reiner Koordinaten-Schlüssel mit TTL genügt). Gecacht wird
**ausschließlich** `list[RadarFrame]` + `source`-Label + `cached_at` —
**NIEMALS** ein `NowcastResult`, weil `onset_minutes` in `_derive_result`
(`radar_service.py:365-401`, insb. Zeile 367 `now = datetime.now(tz=...)`)
relativ zu `now` berechnet wird (Lehre aus F001 der Vorgänger-Scheibe C).

```python
@dataclass
class RadarCacheEntry:
    frames: list        # rohe RadarFrame-Liste
    source: str          # "radar" | "INCA" | "DPC" | "AROME-FR" | "ICON-D2" | "ARPAE-2I" | "minutely_15"
    cached_at: datetime  # UTC, Original-Abrufzeitpunkt

class RadarNowcastCacheService:
    def __init__(self, ttl_seconds: int = 300) -> None: ...

    def _key(self, lat: float, lon: float, region: str) -> str:
        # gerundete Koordinaten (~11m Aufloesung) + Region-Bucket
        return f"{round(lat, 4)}_{round(lon, 4)}_{region}"

    def get(self, lat: float, lon: float, region: str, now: datetime) -> Optional[RadarCacheEntry]:
        # Treffer nur wenn (now - entry.cached_at).total_seconds() <= ttl_seconds
        # UND dieselbe Region
        ...

    def put(self, lat: float, lon: float, region: str, frames: list, source: str, now: datetime) -> None:
        if not frames:
            return  # Negativ-Ergebnisse werden NIE gecacht (Alarm-Blindheit vermeiden)
        ...
```

**Schlüssel = Koordinate + Region-Bucket** (Adversary-Fund F001, Runde 1
GREEN-Verifikation, Verdict BROKEN → behoben). Der ursprüngliche Entwurf
verwendete die Koordinate allein — das war **unvollständig**: zwei
Koordinaten beidseits einer harten Routing-Grenze (z. B. der RADOLAN-Rand
bei `lat=47.0`, nur ~1 m auseinander: `46.99999` außerhalb, `47.00001`
innerhalb) runden bei 4 Nachkommastellen auf **denselben** Schlüssel
(`"47.0_10.0"`), gehören aber zu **verschiedenen** Regionen. Der zweite
Aufruf hätte fälschlich die Frames/Quelle des ersten geerbt, ohne die
eigene Quellenkette zu durchlaufen — direkter Treffer auf das Kernrisiko
„falsche Regen-in-X-Minuten-Aussage". Reproduziert über den echten
`get_nowcast`-Pfad; Regressionstest:
`tests/unit/test_radar_nowcast_cache_sharing.py::test_boundary_coordinates_do_not_share_cache_across_region_change`.

Der Region-Bucket (`_region_bucket(lat, lon)`, `radar_service.py`) ist eine
reine, deterministische Funktion der Koordinate — **dieselbe Reihenfolge**
wie die tatsächliche Quellenkette in `_fetch_frames_with_fallback`
(`radar_service.py:404-436`: RADOLAN → INCA → DPC → AROME-FR → ICON-D2 →
`"global"`) — und steht **vor** dem Fetch fest, weil der Cache-Lookup vor
jedem Fetch passiert:

```python
def _region_bucket(lat: float, lon: float) -> str:
    if _within_radolan(lat, lon):
        return "radolan"
    if _within_inca(lat, lon):
        return "inca"
    if _within_dpc(lat, lon):
        return "dpc"
    if _within_arome_france(lat, lon):
        return "arome_france"
    if _within_icon_d2(lat, lon):
        return "icon_d2"
    return "global"
```

Die Signatur bildet bewusst die **primär gewählte** Region ab (den ersten
Bounding-Box-Treffer), **nicht** die nach evtl. Fallback tatsächlich
resolvte Quelle (z. B. AROME-FR-Fehlschlag → `minutely_15`) — das ist
konsistent, weil der Cache-Lookup vor dem Fetch passiert und den finalen
resolvten Wert prinzipiell noch nicht kennen kann. Der tatsächlich
resolvte Wert wird unverändert als `source`-**Metadatum** im Cache-Eintrag
mitgeführt (nicht als weiterer Schlüsselbestandteil), damit
`_derive_result(frames, source)` bei einem Cache-Hit mit dem korrekten
Label arbeitet, statt die Quelle neu zu erraten. Der ~11 m-Dedup-Nutzen
**innerhalb** einer Region bleibt erhalten (Gegentest:
`test_same_region_coordinates_rounding_to_identical_key_still_share_one_fetch`).

Prozessweiter Singleton (identisches Muster wie `weather_cache.py`):

```python
_shared_radar_cache: Optional["RadarNowcastCacheService"] = None
_shared_radar_cache_lock = Lock()

def get_shared_radar_cache(ttl_seconds: int = 300) -> RadarNowcastCacheService: ...
def reset_shared_radar_cache_for_tests() -> None: ...
```

TTL **300s** (unter der feinsten Quell-Auflösung RADOLAN 5 Min, weit unter
dem 15-Minuten-Alarmtakt) — anders als der Forecast-Cache-Default (600s), weil
der Radar-Pfad der zeitkritischste Alarm-Pfad ist (Gewitter-Anzug).

### 2. Injizierbare Uhr in `RadarNowcastService` (Voraussetzung für
deterministische Onset-Recompute-Tests ohne `sleep`)

```python
def __init__(
    self,
    frame_source: Optional[Callable[[float, float], list]] = None,
    cache: Optional["RadarNowcastCacheService"] = None,
    now_fn: Optional[Callable[[], datetime]] = None,
) -> None:
    self._frame_source = frame_source
    self._convective_checked = True
    self._now_fn = now_fn or (lambda: datetime.now(timezone.utc))
    if cache is None:
        from services.radar_cache import get_shared_radar_cache
        cache = get_shared_radar_cache()
    self._cache = cache
    self._openmeteo_unavailable_this_call = False
    self._priority = "user_briefing"
    self._budget_gate = None
```

`_derive_result` verwendet `self._now_fn()` statt direkt
`datetime.now(tz=timezone.utc)` — Default-Verhalten unverändert
(Produktionscode ruft weiterhin die echte Uhr), Tests können eine
kontrollierte Zeitquelle injizieren.

### 3. `get_nowcast` — Cache- und Budget-Einbindung

```python
def get_nowcast(self, lat: float, lon: float, priority: str = "user_briefing") -> NowcastResult:
    self._convective_checked = True
    self._openmeteo_unavailable_this_call = False
    self._priority = priority
    from services.forecast_budget import ForecastBudgetGate
    self._budget_gate = ForecastBudgetGate()
    now = self._now_fn()
    region = _region_bucket(lat, lon)  # Adversary-Fund F001: Teil des Cache-Schluessels

    cached = self._cache.get(lat, lon, region, now=now)
    if cached is not None:
        self._budget_gate.record_cache_hit()
        return self._derive_result(cached.frames, cached.source, now=now)

    self._budget_gate.record_cache_miss()

    if self._frame_source is not None:
        frames = self._frame_source(lat, lon)
        source = "radar"
    else:
        frames, source = self._fetch_frames_with_fallback(lat, lon)

    if frames:
        self._cache.put(lat, lon, region, frames, source, now=now)

    return self._derive_result(frames, source, now=now)
```

`_derive_result(self, frames, source, now=None)`: `now = now or self._now_fn()`
statt `datetime.now(tz=timezone.utc)` — sonst unverändert. Wichtig: Die
Ableitung läuft **bei jedem Aufruf neu**, unabhängig davon, ob `frames` aus
dem Cache oder frisch geholt wurden — der Cache liefert nie ein fertiges
Ergebnis.

`priority="user_briefing"` bleibt rückwärtskompatibler Default — bestehende
Aufrufer, die `priority` nicht kennen, verhalten sich unverändert
(nie gedrosselt).

### 4. Budget-Gate auf den open-meteo-Funnel (`_fetch_openmeteo_15`) — NICHT
auf die nicht-quotierten Quellen (RADOLAN/INCA/DPC)

`ForecastBudgetGate.PROVIDER == "openmeteo"` (unverändert) — nur
open-meteo-Aufrufe zählen gegen das Tageskontingent. RADOLAN/INCA/DPC sind
eigene, nicht quotierte Endpunkte und werden **nicht** gegated. Da laut
Analyse `_fetch_openmeteo_15` (`radar_service.py:317-363`) der **einzige**
Funnel ist, durch den JEDER open-meteo-Zweig läuft (AROME-FR, ICON-D2,
ARPAE, der finale `minutely_15`-Fallback UND beide Sidecar-Aufrufe aus
`_fetch_geosphere_inca`/`_fetch_radar_dpc`, Zeilen 262/291), genügt EIN
Gate-Einbau an dieser Stelle, um Punkt 7 (Sidecars mitzählen) automatisch
mitabzudecken:

```python
def _fetch_openmeteo_15(self, lat, lon, models=None) -> list:
    if self._openmeteo_unavailable_this_call:
        return []  # Issue #1329 C2: kein zweiter Versuch nach vorherigem
                    # Fehlschlag/Drosselung in DIESEM get_nowcast()-Aufruf
    if not self._budget_gate.allow(self._priority):
        self._budget_throttled_this_call = True
        self._openmeteo_unavailable_this_call = True
        return []  # KEIN HTTP-Call
    try:
        ...
        self._budget_gate.record_call()  # unmittelbar vor dem echten Fetch
        with httpx.Client(timeout=HTTPX_TIMEOUT) as client:
            resp = client.get(url)
            resp.raise_for_status()
            ...
    except Exception as e:
        logger.warning(...)
        self._openmeteo_unavailable_this_call = True
        return []
```

`self._budget_gate`/`self._priority`/`self._openmeteo_unavailable_this_call`
werden bei jedem `get_nowcast()`-Aufruf frisch gesetzt (Instanz-Zustand,
Muster `self._convective_checked`) — `_fetch_openmeteo_15` ist nur über
`get_nowcast()` erreichbar, kein anderer Aufrufpfad existiert.

### 5. Doppelverbrauch-Fix (Root Cause 3)

Der Guard `_openmeteo_unavailable_this_call` (Schritt 4) verhindert
strukturell, dass nach einem ECHTEN Fehlschlag (Exception/429, catch-Block)
ein weiterer open-meteo-Zweig in **demselben** `get_nowcast()`-Aufruf
versucht wird — betrifft AROME-FR → ICON-D2 → ARPAE → `minutely_15`
gleichermaßen, da alle durch denselben Funnel laufen. **Nicht** betroffen ist
der bestehende „All-None-Guard" (`radar_service.py:340-346`, Zeile
345-346): eine leere-aber-valide Antwort außerhalb eines Modellgitters ist
KEIN Fehlschlag und darf weiterhin zum nächsten (anderen, potenziell
erfolgreichen) Modell durchfallen — dieser Fall setzt den Guard nicht.

### 6. Beobachtbarkeit bei Drosselung (kein Alarm-Fehlverhalten)

`NowcastResult` bekommt ein neues Feld `throttled: bool = False`
(rückwärtskompatibler Default). Wird auf `True` gesetzt, wenn
`get_nowcast()` am Ende KEINE Frames liefert UND
`self._budget_throttled_this_call` gesetzt wurde (Budget-Drosselung war die
Ursache, nicht „echt kein Regen"). `radar_alert_due()`
(`trip_alert.py:34-37`, `onset is not None and onset <= threshold`)
verhält sich bei `onset_minutes=None` unverändert — **kein Alarm** wird bei
Drosselung ausgelöst (sicheres Verhalten: lieber ein verpasster
Alarm-Poll-Zyklus als ein Kontingent-Ausfall über den ganzen Tag). Der
nächste erfolgreiche Poll (oder ein manueller `/jetzt`-Aufruf, nie
gedrosselt) holt die Information nach.

### 7. Call-Site-Anpassungen (Priorität explizit)

| Aufrufer | Datei:Zeile | Priorität |
|---|---|---|
| `TripAlertService.check_radar_alerts` | `trip_alert.py:677` | `priority="polling"` |
| `CompareRadarAlertService._detect_triggered_locations` | `compare_radar_alert.py:140` | `priority="polling"` |
| `/jetzt`-Befehl, `_show_now` | `trip_command_processor.py:1111` | `priority="user_briefing"` (Default, explizit gesetzt zur Dokumentation der Absicht — Nutzeraktion, nie gedrosselt) |

### 8. Offline-Fixture-Anbindung (PO-Direktive „Tests dürfen Prod nie belasten")

**Aktivierungssignal** — identisch zu `providers/base.py:144`, kein neuer
Env-Var-Name:

```python
def _offline_fixture_active() -> bool:
    """True wenn GZ_TEST_FIXTURE_DIR gesetzt ist (Issue #1329 C2) --
    identische Aktivierungsregel wie providers/base.py:144. EIN Schalter
    fuer den gesamten Radar-Pfad, kein separater Radar-Env-Var."""
    import os
    return bool(os.environ.get("GZ_TEST_FIXTURE_DIR", "").strip())
```

**Open-meteo-Funnel bekommt echte Offline-Frames** — `_fetch_openmeteo_15`
ist der EINZIGE Ort, durch den jeder open-meteo-Zweig läuft (AROME-FR,
ICON-D2, ARPAE, finaler `minutely_15`-Fallback, UND beide Sidecar-Aufrufe),
deshalb genügt EIN Einbau hier für den kompletten open-meteo-Anteil:

```python
def _fetch_openmeteo_15(self, lat, lon, models=None) -> list:
    if self._openmeteo_unavailable_this_call:
        return []
    if _offline_fixture_active():
        return self._load_radar_fixture_frames()  # kein Netzcall, kein Budget-Verbrauch
    if not self._budget_gate.allow(self._priority):
        ...
```

`_load_radar_fixture_frames(self)` lädt `fixtures/radar/minutely_15.json`
(Pfad hergeleitet als Geschwister-Verzeichnis von `GZ_TEST_FIXTURE_DIR`,
analog `FixtureProvider`: `Path(fixture_dir).resolve().parent / "radar" /
"minutely_15.json"` — kein neuer Env-Var, derselbe Wurzelpfad wie der
Forecast-Fixture-Ordner) und stempelt die Einträge relativ zu
`self._now_fn()` um (Muster `FixtureProvider.fetch_forecast`, Zeile
110-117). **Fail-soft:** fehlende/kaputte Fixture-Datei → `[]` (setzt
`_openmeteo_unavailable_this_call = True`, kein Absturz — degradiert zum
in Known Limitations (a) explizit erlaubten „keine Frames → kein Alarm").
Weder `record_call()` noch `budget_gate.allow()` werden im Offline-Zweig
aufgerufen — eine Fixture-Antwort ist kein realer Verbrauch und darf den
Tageszähler nicht verfälschen. Die äußere Radar-Frame-Cache-Buchführung
(Abschnitt 3, `record_cache_hit`/`record_cache_miss`) bleibt davon
unberührt — sie testet den Cache-Mechanismus selbst, nicht den
open-meteo-Verbrauch.

**Fixture-Inhalt (`fixtures/radar/minutely_15.json`):** bewusst
**trocken** (`precip_mm_h: 0.0` über den gesamten Nowcast-Horizont) —
verhindert, dass ein späterer Staging-Betrieb mit `GZ_TEST_FIXTURE_DIR`
gesetzt (Infra-Ticket #1333) bei jedem Poll-Zyklus einen Schein-Alarm
auslöst. Beispielstruktur:

```json
{
  "frames": [
    {"offset_min": 0, "precip_mm_h": 0.0, "weather_code": 0},
    {"offset_min": 15, "precip_mm_h": 0.0, "weather_code": 0},
    {"offset_min": 30, "precip_mm_h": 0.0, "weather_code": 0},
    {"offset_min": 45, "precip_mm_h": 0.0, "weather_code": 0},
    {"offset_min": 60, "precip_mm_h": 0.0, "weather_code": 0}
  ]
}
```

**Nicht-open-meteo-Quellen: sauberes Leerergebnis (gewählte Option statt
eigener Fixture, PO gab beide Optionen frei — einfacher, weniger LoC, keine
neue Fixture-Pflege für drei zusätzliche Formate):**

```python
def _fetch_brightsky(self, lat, lon) -> list:
    if _offline_fixture_active():
        return []  # Issue #1329 C2 Punkt 8: kein Netz zu BrightSky im Offline-Modus
    try:
        ...
```

Identischer Guard (vor der Provider-Instanziierung, kein Netzzugriff auch
nicht ansatzweise) in `_fetch_geosphere_inca` und `_fetch_radar_dpc` — beide
Methoden geben `[]` zurück, BEVOR `GeoSphereProvider()`/`RadarDPCProvider()`
je konstruiert wird (auch der jeweilige Sidecar-Aufruf an open-meteo
innerhalb dieser Methoden wird dadurch nie erreicht — kein doppelter
Guard nötig). Die Fallback-Kette läuft dadurch im Offline-Modus für JEDE
Koordinate deterministisch bis zum open-meteo-Funnel durch (RADOLAN/INCA/DPC
liefern leer → weiter in der Kette) und landet dort auf den
Fixture-Frames — ein wohldefiniertes Ergebnis für jede Koordinate, nie ein
Absturz, nie ein echter Netzzugriff.

**Selbstheilender Nebeneffekt (kein Test-Datei-Migrationsaufwand
nötig):** `tests/conftest.py:19-32` setzt `GZ_TEST_FIXTURE_DIR` bereits
heute automatisch für JEDEN nicht `@pytest.mark.live`-markierten Testlauf.
Sobald dieser Abschnitt ausgeliefert ist, greift der Offline-Pfad für ALLE
bestehenden Radar-Tests automatisch — ohne dass ein einziger bestehender
Testfile angefasst werden muss. `@pytest.mark.live`-markierte Tests
(z. B. `test_feature_1186_arpae_it_fallback.py`, `test_issue_1162_radar_dpc.py`)
bleiben unverändert gegen die echte API laufend, weil `conftest.py` für sie
`GZ_TEST_FIXTURE_DIR` explizit NICHT setzt.

## Expected Behavior

- **Input:** Zwei Scheduler-Jobs (Trip-Radar, Compare-Radar) fragen im
  selben 15-Minuten-Zyklus denselben Ort ab; das Tagesbudget nähert sich dem
  Limit.
- **Output:** Der zweite Aufruf liefert die gecachten rohen Frames ohne
  Upstream-Call (Onset dabei stets frisch relativ zur aktuellen Zeit
  berechnet, nie aus einem gecachten fertigen Ergebnis). Bei Budget-Druck
  werden `polling`-Aufrufe ab 80%, weitere ab 95% (bestehende
  `ForecastBudgetGate`-Schwellen) mit `onset_minutes=None,
  throttled=True` beantwortet — kein Alarm wird ausgelöst, kein
  Nutzer-Briefing betroffen. `/jetzt` (`priority="user_briefing"`) läuft
  immer durch.
- **Side effects:** Neuer prozessweiter In-Memory-Cache
  (`get_shared_radar_cache()`, TTL 300s, kein Neustart-Überstand — analog
  Scheibe C); `data/diagnostics/forecast_budget.json` erhält zusätzliche
  Einträge aus dem Radar-Pfad (derselbe Zähler wie der Forecast-Pfad, keine
  neue Datei); `_fetch_openmeteo_15` macht nach einem echten Fehlschlag
  innerhalb desselben Aufrufs keinen zweiten Versuch mehr. Neu:
  `fixtures/radar/minutely_15.json` (deterministische, trockene
  Offline-Frames); mit gesetztem `GZ_TEST_FIXTURE_DIR` macht der gesamte
  Radar-Pfad KEINEN Netzzugriff mehr (BrightSky/GeoSphere/RadarDPC/
  open-meteo) — inklusive aller bestehenden Kern-Tests, die bisher
  unbeabsichtigt echtes Netz nutzten (siehe Implementation Details
  Abschnitt 8).

## Acceptance Criteria

- **AC-1:** Given zwei aufeinanderfolgende `get_nowcast(lat, lon)`-Aufrufe für **dieselbe Koordinate** innerhalb des TTL (300s) — z. B. Trip-Radar-Check und Compare-Radar-Check am selben Ort über zwei unabhängige `RadarNowcastService`-Instanzen / When der zweite Aufruf läuft / Then geht genau **ein** Fetch an die zählende `frame_source`-Callable (der zweite Aufruf ist ein Cache-Hit).
  - Test: zählende Callable (kein `patch()`), zwei `RadarNowcastService()`-Default-Instanzen (wie in `trip_alert.py`/`compare_radar_alert.py` konstruiert) teilen sich den geteilten Singleton-Cache — Fetch-Zähler bleibt bei 1.

- **AC-2:** Given zwei Aufrufe mit **unterschiedlicher** Koordinate / When beide laufen / Then gehen **zwei** Fetches raus (kein falscher Cache-Treffer).
  - Test: gleiche zählende Callable, zwei `get_nowcast()`-Aufrufe mit abweichender lat/lon — Zähler steht bei 2.

- **AC-3:** Given ein Cache-Eintrag, dessen Alter den TTL (300s) überschritten hat — simuliert über den injizierbaren `now_fn` (kein `sleep`) / When ein weiterer Aufruf für dieselbe Koordinate erfolgt / Then wird erneut gefetcht (kein stiller Stale-Serve über den TTL hinaus).
  - Test: `now_fn` liefert beim zweiten Aufruf einen um >300s späteren Zeitpunkt — Fetch-Zähler steht danach bei 2.

- **AC-4:** Given ein Cache-Treffer auf Frames, die beim ersten Aufruf geholt wurden / When ein zweiter Aufruf für dieselbe Koordinate wenige simulierte Minuten später (innerhalb TTL) erfolgt / Then unterscheidet sich `onset_minutes` im zweiten Ergebnis vom ersten um ungefähr die simulierte Zeitspanne — der Onset wird bei JEDEM Aufruf relativ zur aktuellen Zeit aus denselben rohen Frames neu berechnet, NIE aus einem gecachten fertigen `NowcastResult` (Lehre aus Adversary-Fund F001 der Vorgänger-Scheibe C).
  - Test: zählende `frame_source` liefert feste, deterministische Frames mit fixem Regen-Einsatz-Zeitpunkt; zwei `get_nowcast()`-Aufrufe mit `now_fn` T0 und T0+3min (Cache-Hit beim zweiten) liefern `onset_minutes`-Werte, die sich um ~3 (±1) Minuten unterscheiden, bei konstant 1 Fetch.

- **AC-5:** Given ein Fetch liefert eine **leere** Frame-Liste (kein Signal/Ausfall) / When derselbe Ort erneut innerhalb des TTL abgefragt wird / Then wird NICHT der leere Zustand aus dem Cache bedient — es wird erneut gefetcht (Negativ-Ergebnisse werden nie gecacht, verhindert Alarm-Blindheit über den TTL bei vorübergehendem Ausfall).
  - Test: zählende Callable liefert beim ersten Aufruf `[]`, beim zweiten echte Frames — der zweite Aufruf ist ein erneuter Fetch (Zähler 2), kein Cache-Hit auf einen leeren Eintrag.

- **AC-6:** Given das Tagesbudget ist zu ≥ 80% ausgeschöpft (vorpräparierter `ForecastBudgetGate`-Zählerstand, `polling`-Schwelle) / When ein Scheduler-Radar-Check (`priority="polling"`) einen Cache-Miss hat und die Quellenkette bei einer Koordinate außerhalb aller RADOLAN/INCA/DPC/AROME-FR/ICON-D2-Bounding-Boxen direkt beim open-meteo-Funnel (`minutely_15`) landet / Then wird der HTTP-Fetch **abgewiesen ohne Netzzugriff** (`allow()` liefert `False`, bevor `httpx.Client` aufgerufen wird), das Ergebnis zeigt `onset_minutes=None, throttled=True` — **kein Alarm** wird ausgelöst (`radar_alert_due()` liefert `False`), **aber** derselbe Aufruf mit `priority="user_briefing"` im selben Budget-Zustand liefert weiterhin einen echten Fetch-Versuch (nie gedrosselt).
  - Test: `ForecastBudgetGate` mit vorpräpariertem Zählerstand (80%, kein Netzzugriff nötig — der Test beweist die Abwesenheit des HTTP-Calls über den fehlenden Fetch-Zähler-Increment einer zählenden Wrapper-Funktion um `_fetch_openmeteo_15`, kein `patch()`); `allow("polling")` bzw. der End-to-End-Pfad über `get_nowcast(priority="polling")` vs. `get_nowcast(priority="user_briefing")` im selben Budget-Zustand.

- **AC-7:** Given ein open-meteo-Zweig innerhalb eines `get_nowcast()`-Aufrufs schlägt fehl (Exception/simuliertes 429, z. B. AROME-FR-Branch) / When die Quellenkette zum nächsten open-meteo-Zweig weiterläuft (z. B. finaler `minutely_15`-Fallback) / Then wird **kein zweiter** open-meteo-HTTP-Versuch in demselben Aufruf unternommen (Doppelverbrauch-Fix, Root Cause 3) — der Aufruf endet mit leeren Frames statt einem zweiten fehlgeschlagenen Call.
  - Test: injizierter Fehler-Trigger im ersten open-meteo-Touchpoint (z. B. über eine Koordinate/Konstellation, die zwei Zweige durchläuft, mit einer zählenden Fehler-Simulation statt echtem Netzzugriff) — Zähler für tatsächlich unternommene HTTP-Versuche bleibt bei 1, nicht 2. Nicht betroffen: der bestehende All-None-Guard-Übergang zwischen validen, nicht-fehlerhaften Modell-Antworten (Regressionstest gegen `test_feature_734_arome_france_nowcast.py`-Bestand bleibt grün).

- **AC-8:** Given Sidecar-Aufrufe für den Gewitter-Check (INCA `radar_service.py:262`, DPC `radar_service.py:291`) laufen im selben `get_nowcast()`-Aufruf / When sie open-meteo erreichen / Then zählen sie ebenfalls gegen dasselbe Tagesbudget (`record_call()` wird auch für Sidecar-Aufrufe ausgeführt) — kein separater, ungezählter Verbrauchspfad.
  - Test: INCA-Pfad (Koordinate innerhalb der INCA-Bounding-Box) mit zählendem open-meteo-Funnel — nach einem `get_nowcast()`-Aufruf mit erfolgreichem INCA-Fetch UND erfolgreichem Sidecar-Call steht der Budget-Zähler (`record_call`-Aufrufe) bei mindestens 1 (dem Sidecar), obwohl INCA selbst nicht über open-meteo läuft.

- **AC-9:** Given ein Trip mit aktivem Radar-Alarm-Check und ein Compare-Preset mit demselben Ort im selben 15-Minuten-Zyklus (Prod-Log-Muster: getrennte Endpunkte, getrennte `RadarNowcastService`-Instanzen) / When beide Checks laufen / Then teilen sie sich einen einzigen Fetch über den geteilten Singleton-Cache — Beweis, dass die Cache-Teilung end-to-end über die tatsächlichen Produktionspfade wirkt, nicht nur bei manuell injiziertem geteiltem Cache-Objekt.
  - Test: zwei unabhängig konstruierte `RadarNowcastService()`-Instanzen (Default-Konstruktion wie in `trip_alert.py:556-561` und `compare_radar_alert.py:172-176`) mit identischer Koordinate, zählende `frame_source` — ein Fetch für beide zusammen.

- **AC-10:** Given `GZ_TEST_FIXTURE_DIR` ist gesetzt (Standard-Testzustand über `tests/conftest.py`-Autouse-Fixture) / When `get_nowcast(lat, lon)` **ohne** `frame_source`-Injection an einer Koordinate außerhalb aller RADOLAN/INCA/DPC-Bounding-Boxen aufgerufen wird (reiner open-meteo-Pfad, `minutely_15`- oder AROME-FR/ICON-D2-Zweig) / Then macht der Aufruf **keinen** echten `httpx`-Call und liefert dennoch ein wohldefiniertes `NowcastResult` (Frames aus `fixtures/radar/minutely_15.json`, `source` gesetzt, kein Absturz, `onset_minutes=None` wegen der trockenen Fixture).
  - Test: `httpx.Client` wird für die Testdauer per `monkeypatch` durch einen Tripwire-Stub ersetzt, dessen `__enter__`/`get` bei Aufruf `AssertionError("Netzcall trotz GZ_TEST_FIXTURE_DIR")` wirft — Beweis der ABWESENHEIT eines Calls, kein Rückgabewert wird vorgetäuscht (kein Mock-Theater im Sinne von CLAUDE.md: die Tripwire beweist etwas, sie spiegelt keine Annahme). `get_nowcast()` läuft durch, ohne die Tripwire auszulösen; `result.frames` entspricht der Fixture.

- **AC-11:** Given `GZ_TEST_FIXTURE_DIR` ist gesetzt / When eine Koordinate innerhalb der RADOLAN- ODER INCA- ODER DPC-Bounding-Box abgefragt wird (Quellen, die normalerweise BrightSky/GeoSphere/RadarDPC real kontaktieren würden) / Then wird die jeweilige Quelle **nicht einmal konstruiert** — sofortiger Rückfall auf die nächste Kettenstufe; der Aufruf landet deterministisch beim Fixture-gestützten open-meteo-Funnel (`result.source` ∈ `{"AROME-FR", "ICON-D2", "ARPAE-2I", "minutely_15"}`), niemals bei `"radar"`/`"INCA"`/`"DPC"`.
  - Test: Tripwire-Stubs für `BrightSkyProvider`/`GeoSphereProvider`/`RadarDPCProvider` (per `monkeypatch`, wirft bei Instanziierung) beweisen die Nicht-Kontaktierung für je eine Koordinate aus jeder Bounding-Box; `result.source` entspricht der Fixture-Kette, nicht der eigentlich zuständigen Primärquelle.

## Known Limitations

- **Quellenwechsel/Umleitung für Frankreich NICHT im Scope (geprüft und
  verworfen):** RADOLAN endet bei lat ≥ 47.0, DPC bei lon ≥ 6.5; für
  43.118/6.359 (Prod-Log-Beispiel) greift keine der beiden, eine
  Météo-France-Anbindung existiert nicht. Für diese Region bleibt
  `minutely_15`/AROME-FR über open-meteo die einzige Quelle — der Hebel
  dieser Scheibe ist Cache + Drosselung, nicht Quellenwechsel. Umleiten wäre
  ohne neue Provider-Integration unmöglich (eigenes Folge-Ticket, falls
  gewünscht).
- **Prozessweiter In-Memory-Cache, kein Neustart-Überstand
  (Single-Worker-Annahme):** identische Einschränkung wie Scheibe C
  (`gregor-python` läuft ohne `--workers`). Ein Deploy-Neustart leert den
  Cache vollständig — bei 300s TTL praktisch gleichwertig zu einem
  regulären Ablauf.
- **#1333 (Identitätstrennung Prod/Staging beim Anbieter) und #1334
  (Mitternachts-Filter) sind ausdrücklich NICHT Teil dieser Scheibe** —
  eigene Tickets, unverändert offen.
- **Kein neuer Go-Observability-Block:** Radar-Verbrauch erscheint bereits
  automatisch im bestehenden `forecast_budget`-Block von
  `/api/scheduler/status` (Scheibe C), weil derselbe Zähler
  (`PROVIDER="openmeteo"`) verwendet wird — keine Unterscheidung zwischen
  „Forecast-" und „Radar-Verbrauch" im Status-Endpunkt möglich. Eine
  Aufschlüsselung nach Quelle wäre ein Folge-Ticket, falls operativ
  gewünscht.
- **`throttled`-Flag ist ein reines Beobachtbarkeits-Signal, kein
  Alarm-Verhalten:** `radar_alert_due()` unterscheidet nicht zwischen „echt
  kein Regen" und „gedrosselt" (beide liefern `onset_minutes=None`) — das
  ist bewusst sicher (nie ein falscher Alarm durch Drosselung), bedeutet
  aber auch: eine Drosselungs-Serie ist im Alarm-Pfad selbst nicht sichtbar,
  nur im Log/Debug-Buffer.
- **RADOLAN/INCA/DPC-Primärfetches bleiben ungegatet:** Diese Quellen
  konsumieren kein open-meteo-Kontingent und werden daher bewusst nicht
  gedrosselt, auch nicht bei knappem Budget — nur tatsächliche
  open-meteo-Touchpoints (Fallback-Kette + Sidecars) zählen.
- **(a) Offline-Verhalten explizit definiert:** Der open-meteo-Funnel MUSS im
  Offline-Modus eine echte, mit dieser Scheibe ausgelieferte Radar-Fixture
  (`fixtures/radar/minutely_15.json`) verwenden — das ist kein optionaler
  Bestandteil. Fehlt die Datei zur Laufzeit dennoch (gelöscht, korrumpiert),
  degradiert `_load_radar_fixture_frames` fail-soft zu `[]`, was sich
  strukturell identisch zu „keine Frames → kein Alarm" verhält (derselbe
  Pfad wie eine reguläre Provider-Fehlmeldung) — kein Absturz, aber auch
  keine Onset-Beweisführung mehr möglich in diesem Degradationsfall. Diese
  Zwei-Stufen-Definition (Happy Path: echte Fixture-Frames; Fail-Soft:
  leer/kein Alarm) ist hiermit die verbindliche Spezifikation, keine offene
  Frage.
- **(b) Staging-Aktivierung ist NICHT Teil dieser Code-Scheibe:** Damit
  Staging tatsächlich offline läuft, muss `GZ_TEST_FIXTURE_DIR` zusätzlich
  auf der Staging-`systemd`-Unit (`gregor-python-staging`) als Env-Zeile
  gesetzt werden — das ist eine reine Betriebs-/Infra-Änderung
  (`henemm-infra`), verfolgt unter #1333, ausdrücklich nicht Gegenstand
  dieser Spec. Ohne diesen Infra-Schritt bleibt Staging bei Radar-Aufrufen
  weiterhin gegen die echte API laufen (unverändertes Verhalten bis #1333
  umgesetzt ist).
- **Vorgefundene, mit dieser Scheibe automatisch mitbehobene
  Altlast (kein zusätzlicher Migrationsaufwand, aber dokumentationswürdig):**
  mehrere bestehende Radar-Tests (z. B.
  `test_feature_761_icon_d2_nowcast.py:40-54,75-93`,
  `test_issue_822_radar_nowcast_segment.py:569`) konstruieren
  `RadarNowcastService()` ohne `frame_source` UND ohne
  `@pytest.mark.live`-Markierung, obwohl ihre Docstrings „echte API-Calls,
  kein Mock" behaupten — sie liefen bislang bei jedem `pytest`-Lauf
  unbeabsichtigt gegen echtes Netz. Nach dieser Scheibe laufen sie
  automatisch offline (Fixture statt Live-Antwort), OHNE dass ihr Code
  geändert werden muss (Abschnitt 8, „Selbstheilender Nebeneffekt") — ihre
  Docstring-Aussage „echte API-Calls" wird dadurch jedoch unzutreffend.
  Eine Nachschärfung dieser Docstrings/Marker (`@pytest.mark.live`
  ergänzen, wo tatsächlich Live-Verhalten geprüft werden soll) ist
  **nicht** Teil dieser Scheibe — Sammel-Eintrag in #1199 statt eigenem
  Ticket (kosmetisch/Doku-Diskrepanz, kein blockierendes Fehlverhalten).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0033
- **Rationale:** Zwei Entscheidungen, beide im Geiste von ADR-0032 (Scheibe
  C), aber bewusst NICHT identisch umgesetzt: (1) **Eigener, einfacherer
  Cache statt Wiederverwendung von `WeatherCacheService`** — Radar-Frames
  sind eine rollierende Zeitserie ohne Segment-Fensterbindung, das
  „Covers"-Konzept aus C (Fenster deckt Fenster ab) hat hier kein
  fachliches Gegenstück; ein reiner koordinatenbasierter TTL-Cache ist
  einfacher zu verifizieren und vermeidet, ein Konzept zu erzwingen, das
  nicht passt. (2) **Wiederverwendung des bestehenden
  `ForecastBudgetGate`-Zählers statt eines radar-eigenen Budgets** — die
  physische Ressource (open-meteo-Tageskontingent) ist identisch mit der
  aus Scheibe C; ein zweiter, unabhängiger Zähler für dieselbe Ressource
  würde Drift-Risiko erzeugen (zwei Zähler könnten unterschiedliche
  Ansichten des tatsächlichen Verbrauchs zeigen) ohne fachlichen Nutzen —
  ein Kontingent, ein Zähler. Beide Entscheidungen sind an dieselbe
  Ein-Prozess-Topologie gebunden wie ADR-0032 und müssten bei einer
  Skalierung auf mehrere Worker gemeinsam überarbeitet werden. (3)
  **Wiederverwendung von `GZ_TEST_FIXTURE_DIR` als alleiniges
  Offline-Signal statt eines radar-eigenen Schalters** — der Forecast-Pfad
  hat diese Konvention bereits etabliert (`providers/base.py:144`,
  `tests/conftest.py`-Autouse); ein zweiter, radar-spezifischer Env-Var
  würde denselben Zustand („wir sind im Offline-Test-/Staging-Modus")
  redundant und potenziell widersprüchlich abbilden (z. B. ein Lauf, in dem
  Forecast offline, Radar aber live liefe, ohne fachlichen Grund für diese
  Asymmetrie). Ein Signal, zwei Pfade, konsistent geschaltet.

## Test Plan

Kern-Schicht, netzfrei, kein Mock-Theater (Test-Politik siehe `CLAUDE.md`):

- **Zählende `frame_source`-Callable** (kein `patch()`/`Mock()`): der
  bestehende DI-Seam `RadarNowcastService(frame_source=callable(lat,lon)->list[RadarFrame])`
  (`radar_service.py:79-81`) mit echten `RadarFrame`-Objekten wie im
  Bestand (`test_feature_656_radar_nowcast.py`,
  `test_feature_734_arome_france_nowcast.py`) — deckt AC-1, AC-2, AC-5,
  AC-9.
- **Injizierbare Uhr (`now_fn`) statt `sleep`:** TTL-Ablauf (AC-3) und
  Onset-Neuberechnung bei Cache-Hit (AC-4) werden über eine im Test
  kontrollierte Zeitquelle simuliert — bei 300s TTL ist ein realer `sleep`
  nicht praktikabel (anders als bei C's kurzen Test-TTLs).
  `RadarNowcastCacheService.get/put` nehmen `now` als expliziten Parameter;
  `RadarNowcastService(now_fn=...)` steuert beide (Cache-TTL-Prüfung UND
  Onset-Berechnung) konsistent aus einer Quelle.
  - **Adversary-Wachsamkeit:** ein Test, der `now_fn` für die
    Onset-Berechnung, aber nicht konsistent für die Cache-TTL-Prüfung
    vorspiegelt, würde eine falsche Korrektheit demonstrieren — beide
    müssen aus demselben injizierten `now` gespeist werden (siehe
    Implementation Details Abschnitt 3).
- **Budget-Simulation ohne Netzzugriff (AC-6, AC-7, AC-8):** Da die
  Drosselung/der Doppelverbrauch-Guard VOR dem `httpx.Client`-Aufruf
  greifen, sind diese Tests netzfrei durch Konstruktion (kein Fixture/Mock
  nötig) — die Abwesenheit eines HTTP-Calls wird über einen echten
  Zähler-Wrapper um den Fetch-Einstiegspunkt bewiesen, nicht über
  `patch()`-Assertions.
- **Bestandsregression:** `test_feature_656_radar_nowcast.py` (8 Tests),
  `test_feature_734_arome_france_nowcast.py` (6 Tests) bleiben grün — der
  All-None-Guard-Übergang zwischen Modellen (kein echter Fehlschlag) darf
  vom neuen `_openmeteo_unavailable_this_call`-Guard NICHT betroffen sein.
- **End-to-End Prod-Pfad (AC-9):** Zwei unabhängig konstruierte
  `RadarNowcastService()`-Default-Instanzen (wie in
  `trip_alert.py:556-561` bzw. `compare_radar_alert.py:172-176`
  tatsächlich instanziiert) statt eines manuell injizierten geteilten
  Cache-Objekts — beweist, dass die Singleton-Teilung über die
  tatsächlichen Produktionskonstruktionspfade wirkt.
- Live-E2E (Staging, nur `/e2e-verify`): `/api/scheduler/status` nach einem
  echten Radar-Alert-Zyklus abfragen — `forecast_budget.calls_today`
  sollte nach der Fix-Auslieferung langsamer wachsen als vorher (relativ,
  nicht absolut prüfbar in einem einzelnen Lauf).
- **Offline-Fixture-Nachweis, netzfrei durch Tripwire (AC-10, AC-11):**
  `monkeypatch` (pytest-Bordmittel, NICHT `unittest.mock.patch`) ersetzt
  `httpx.Client` bzw. `BrightSkyProvider`/`GeoSphereProvider`/
  `RadarDPCProvider` für die Testdauer durch einen Stub, der bei
  tatsächlichem Aufruf/Instanziierung hart mit `AssertionError` fehlschlägt
  — das beweist die ABWESENHEIT eines Netzzugriffs (Tripwire), es täuscht
  keinen Rückgabewert vor und fällt damit NICHT unter das
  Mock-Theater-Verbot aus `CLAUDE.md` (dort verboten: Mocks, die „nur die
  eigene Annahme zurückspiegeln, beweisen nichts" — eine Tripwire beweist
  aktiv etwas Falsifizierbares). `GZ_TEST_FIXTURE_DIR` wird im Test explizit
  gesetzt (nicht nur über die `conftest.py`-Autouse-Fixture verlassen), um
  die Bedingung sichtbar zu machen.
- **Regressionsschutz Selbstheilungs-Nebeneffekt:** ein Kern-Test bestätigt,
  dass `test_feature_761_icon_d2_nowcast.py`-artige Aufrufmuster
  (`RadarNowcastService()` ohne `frame_source`, kein `live`-Marker) nach
  dieser Scheibe tatsächlich über den Fixture-Pfad laufen und nicht mehr
  versuchen, echtes Netz zu erreichen — stellvertretend über dieselbe
  Tripwire-Technik.

## Changelog

- 2026-07-20: Initial spec created (Issue #1329, Scheibe C2)
- 2026-07-20: Ergänzung (PO-Direktive „Tests dürfen Prod nie belasten"):
  Punkt 8 — Offline-Fixture-Anbindung für den kompletten Radar-Pfad über
  das bestehende `GZ_TEST_FIXTURE_DIR`-Signal (open-meteo-Funnel: echte
  Radar-Fixture `fixtures/radar/minutely_15.json`; BrightSky/INCA/DPC:
  sauberes Leerergebnis). AC-10/AC-11 ergänzt, Known Limitations (a)/(b)
  sowie ein vorgefundener Altlast-Befund (bestehende, fälschlich nicht
  `live`-markierte Radar-Tests mit echtem Netzzugriff) dokumentiert,
  ADR-0033 um Rationale-Punkt (3) erweitert, Estimated Scope angepasst.
- 2026-07-21: Adversary-Fund F001 (Runde 1 GREEN-Verifikation, Verdict
  BROKEN → behoben): Cache-Schlüssel um einen Region-Bucket
  (`_region_bucket(lat, lon)`, dieselbe Reihenfolge wie
  `_fetch_frames_with_fallback`) erweitert — reine Koordinatenrundung
  allein ließ zwei Koordinaten beidseits einer harten Routing-Grenze (z. B.
  RADOLAN-Rand, ~1 m Abstand) auf denselben Schlüssel fallen und dadurch
  fälschlich Frames/Quelle der jeweils anderen Region teilen. Implementation
  Details §1 nachgezogen (Codebeispiel `_key`/`get`/`put`/`_region_bucket`),
  zwei Regressionstests ergänzt (`test_boundary_coordinates_do_not_share_cache_across_region_change`,
  `test_same_region_coordinates_rounding_to_identical_key_still_share_one_fetch`).
