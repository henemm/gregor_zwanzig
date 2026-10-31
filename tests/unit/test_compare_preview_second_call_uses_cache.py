"""Issue #2234 — Grundvorhersage-Cache im Ortsvergleich-Pfad (TDD RED).

SPEC: docs/specs/modules/fix_2234_compare_forecast_cache.md
Ausfuehrung:
    uv run pytest tests/unit/test_compare_preview_second_call_uses_cache.py -v

Kern-Schicht, netzfrei, OHNE Mock-Theater: der ``CountingFakeProvider`` unten
erfuellt das ``WeatherProvider``-Protokoll echt (deterministische
``NormalizedTimeseries``) und zaehlt nur seine eigenen Aufrufe. Er wird ueber
die echte Provider-Registry eingehaengt (``providers.base._PROVIDER_FACTORIES``),
derselbe Weg, den ``get_provider("openmeteo")`` in Produktion geht -- der Test
haengt also NICHT an der Frage, ob die Engine den Provider ueber
``ForecastService`` oder ``SegmentWeatherService`` anspricht.

Beobachtungspunkte (dort, wo die Zusicherung WIRKT):
- Anbieter-Abrufe: Zaehler des Fake-Providers.
- Budget-Buchung beim ausloesenden Nutzer: ``ForecastBudgetGate(uid).snapshot()
  ["user_calls_today"]`` -- die einzige oeffentliche Lesequelle fuer den
  Nutzer-Topf. Damit wird ohne ``patch()`` nachgewiesen, dass die echte
  ``user_id`` des Aufrufers am Segment-Weg ankommt.
- Abruf-Fenster: die vom Provider empfangenen ``start``/``end``.

Vertrag fuer die Implementierung (Spec, Implementation Details Punkt 2):
    services.comparison_engine.compare_fetch_window(
        now: datetime, hours: int = COMPARE_FORECAST_HOURS
    ) -> tuple[datetime, datetime]
    start = now (UTC) auf die volle Stunde abgerundet
    end   = 23:59:59 UTC des Kalendertags von (now + hours)
    beide mit ``tzinfo is timezone.utc``.

RED-Ursachen heute: ``fetch_forecast_for_location`` ruft
``ForecastService.get_forecast`` am geteilten Cache vorbei, mit einem
sekundengenauen Fenster ``now .. now+96h``, ohne Budget-Gate. Jeder zweite
Aufruf geht deshalb erneut an den Anbieter, kein Nutzer-Topf wird gebucht, und
``compare_fetch_window`` existiert nicht.
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from app.models import ForecastDataPoint, ForecastMeta, NormalizedTimeseries, Provider

VIENNA = ZoneInfo("Europe/Vienna")
TIME_WINDOW = (9, 16)

# Drei Alpen-Orte (Koordinate + Hoehe sind seit #1991 Teil des Cache-Schluessels).
ORTE = [
    ("loc-innsbruck", "Innsbruck", 47.2692, 11.4041, 574),
    ("loc-seefeld", "Seefeld", 47.3297, 11.1880, 1180),
    ("loc-obergurgl", "Obergurgl", 46.8700, 11.0270, 1930),
]


# ---------------------------------------------------------------------------
# Fake-Provider (kein Mock)
# ---------------------------------------------------------------------------

def _series_anchor() -> datetime:
    return datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)


def _wert(ts: datetime, lat: float) -> float:
    """Deterministisch je Zeitstempel und Ort -- unabhaengig vom Abruf-Fenster."""
    return round(2.0 + ts.hour * 0.5 + ts.day * 0.1 + lat * 0.01, 3)


class CountingFakeProvider:
    """Wie der reale OpenMeteo-Provider tageweise: liefert IMMER dieselbe
    Stundenreihe ab heute 00:00 UTC ueber 6 Tage, egal welches ``start``/``end``
    angefragt wird. Zaehlt threadsicher jeden Aufruf und merkt sich das
    angefragte Fenster. Kein ``select_model`` -> Modell-Schluessel faellt auf
    den Provider-Namen zurueck."""

    def __init__(self, delay_s: float = 0.0) -> None:
        self._lock = threading.Lock()
        self.call_count = 0
        self.windows: list[tuple[datetime, datetime]] = []
        self.delay_s = delay_s

    @property
    def name(self) -> str:
        return "openmeteo"

    def _antwort(self, location) -> NormalizedTimeseries:
        anchor = _series_anchor()
        meta = ForecastMeta(
            provider=Provider.OPENMETEO,
            model="icon_d2",
            grid_res_km=2.2,
            run=anchor,
            interp="grid_point",
        )
        data = []
        for i in range(24 * 6):
            ts = anchor + timedelta(hours=i)
            v = _wert(ts, location.latitude)
            data.append(ForecastDataPoint(
                ts=ts,
                t2m_c=v,
                wind10m_kmh=10.0 + ts.hour,
                gust_kmh=20.0 + ts.hour,
                cloud_total_pct=(ts.hour * 4) % 100,
                precip_1h_mm=0.1 if ts.hour % 6 == 0 else 0.0,
                pop_pct=(ts.hour * 3) % 100,
            ))
        return NormalizedTimeseries(meta=meta, data=data)

    def fetch_forecast(self, location, start=None, end=None,
                       enrich_ensemble: bool = True, enrich_snow: bool = True):
        with self._lock:
            self.call_count += 1
            self.windows.append((start, end))
        if self.delay_s:
            time.sleep(self.delay_s)
        return self._antwort(location)


class FailFirstProvider(CountingFakeProvider):
    """Erster Aufruf fuer ``fail_lat`` scheitert (Fehler bzw. leere Reihe),
    jeder weitere liefert gueltige Daten."""

    def __init__(self, fail_lat: float, mode: str) -> None:
        super().__init__()
        self.fail_lat = fail_lat
        self.mode = mode
        self._failed = False

    def fetch_forecast(self, location, start=None, end=None,
                       enrich_ensemble: bool = True, enrich_snow: bool = True):
        from providers.base import ProviderRequestError

        with self._lock:
            self.call_count += 1
            self.windows.append((start, end))
            fail_now = (not self._failed
                        and abs(location.latitude - self.fail_lat) < 1e-6)
            if fail_now:
                self._failed = True
        if fail_now and self.mode == "error":
            raise ProviderRequestError("openmeteo", "anbieter-stoerung-2234")
        if fail_now and self.mode == "empty":
            ts = self._antwort(location)
            return NormalizedTimeseries(meta=ts.meta, data=[])
        return self._antwort(location)


@pytest.fixture
def install_provider(monkeypatch):
    """Haengt einen Fake unter ``openmeteo`` in die echte Registry. Die
    autouse-Fixture ``_use_fixture_provider`` (tests/conftest.py) setzt
    ``GZ_TEST_FIXTURE_DIR``, das in ``get_provider()`` Vorrang haette."""
    import providers.base as registry

    monkeypatch.delenv("GZ_TEST_FIXTURE_DIR", raising=False)
    if not registry._PROVIDER_FACTORIES:
        registry._load_providers()

    def _install(provider):
        monkeypatch.setitem(registry._PROVIDER_FACTORIES, "openmeteo", lambda: provider)
        return provider

    return _install


# ---------------------------------------------------------------------------
# Hilfen
# ---------------------------------------------------------------------------

def _orte(namen_suffix: str = ""):
    from app.user import SavedLocation

    return [
        SavedLocation(id=i, name=n + namen_suffix, lat=lat, lon=lon,
                      elevation_m=elev, timezone="Europe/Vienna")
        for i, n, lat, lon, elev in ORTE
    ]


def _target_date() -> date:
    return datetime.now(VIENNA).date() + timedelta(days=1)


def _run_engine(locations):
    from services.comparison_engine import ComparisonEngine

    return ComparisonEngine.run(
        locations=locations,
        time_window=TIME_WINDOW,
        target_date=_target_date(),
        official_alerts_enabled=False,
    )


def _projection(result):
    """Vergleichbare Sicht auf ein ComparisonResult (Rohdaten + Aggregate)."""
    out = []
    for lr in result.locations:
        out.append({
            "id": lr.location.id,
            "error": lr.error,
            "score": lr.score,
            "temp_min": lr.temp_min,
            "temp_max": lr.temp_max,
            "wind_max": lr.wind_max,
            "gust_max": lr.gust_max,
            "cloud_avg": lr.cloud_avg,
            "precip_sum_mm": lr.precip_sum_mm,
            "pop_max_pct": lr.pop_max_pct,
            "sunny_hours": lr.sunny_hours,
            "hourly": [(dp.ts, dp.t2m_c) for dp in (lr.hourly_data or [])],
            "outlook": [(dp.ts, dp.t2m_c) for dp in (lr.outlook_hourly_data or [])],
        })
    return out


def _as_utc(ts: datetime) -> datetime:
    """Zeitstempel vergleichbar machen: naive Werte gelten als UTC."""
    return ts.replace(tzinfo=timezone.utc) if ts.tzinfo is None else ts.astimezone(timezone.utc)


def _user_calls(uid: str) -> int:
    from services.forecast_budget import ForecastBudgetGate

    return ForecastBudgetGate(uid).snapshot()["user_calls_today"]


def _uid(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _lege_vergleich_an(uid: str, locations, preset_id: str = "cp-2234") -> dict:
    from app.loader import get_data_root, save_location
    from tests.helpers.compare_briefings import write_compare_briefings

    for loc in locations:
        save_location(loc, user_id=uid)
    preset = {
        "id": preset_id,
        "name": "Cache-Vergleich",
        "user_id": uid,
        "location_ids": [loc.id for loc in locations],
        "schedule": "daily",
        "weekday": 4,
        "profil": "ALLGEMEIN",
        "empfaenger": ["gregor-test@henemm.com"],
        "official_alerts_enabled": False,
        "day_window_start_hour": TIME_WINDOW[0],
        "day_window_end_hour": TIME_WINDOW[1],
        "created_at": "2026-10-31T00:00:00Z",
    }
    write_compare_briefings(get_data_root() / "users" / uid, [preset])
    return preset


def _vorschau(uid: str, preset_id: str = "cp-2234"):
    from services.compare_preview_service import ComparePreviewService

    return ComparePreviewService()._prepare(preset_id, user_id=uid, target_date=None)["result"]


def _versand(uid: str, preset: dict, locations):
    from app.config import Settings
    from app.loader import get_data_root
    from services.scheduler_dispatch_service import send_one_compare_preset

    return send_one_compare_preset(
        dict(preset),
        Settings(mail_to="empfaenger@example.com"),
        uid,
        str(get_data_root()),
        all_locations_cache=list(locations),
        mail_sink=lambda *a, **kw: None,
        sms_sink=lambda *a, **kw: None,
        telegram_sink=lambda *a, **kw: None,
        premium_sms_sink=lambda *a, **kw: None,
        on_demand=True,
    )


# ---------------------------------------------------------------------------
# AC-1: zweite Vorschau innerhalb von 10 Minuten -> 0 Anbieter-Abrufe
# ---------------------------------------------------------------------------

def test_ac1_second_comparison_run_makes_no_provider_call_and_is_identical(install_provider):
    provider = install_provider(CountingFakeProvider())
    locations = _orte()

    first = _run_engine(locations)
    nach_erstem = provider.call_count
    assert nach_erstem == 3, f"Erster Lauf: je Ort ein Abruf erwartet, tatsaechlich {nach_erstem}"

    second = _run_engine(locations)

    assert provider.call_count == nach_erstem, (
        "AC-1: die zweite Vorschau desselben Vergleichs innerhalb von 10 Minuten "
        "darf KEINEN Anbieter-Abruf machen (geteilter Cache), tatsaechlich "
        f"{provider.call_count - nach_erstem} zusaetzliche Abrufe"
    )
    assert _projection(second) == _projection(first), (
        "AC-1: Rohdaten und Aggregate der zweiten Vorschau muessen identisch sein"
    )


# ---------------------------------------------------------------------------
# AC-2: Vorschau -> Versand innerhalb von 10 Minuten -> 0 Anbieter-Abrufe
# ---------------------------------------------------------------------------

def test_ac2_dispatch_after_preview_makes_no_provider_call(install_provider):
    provider = install_provider(CountingFakeProvider())
    uid = _uid("tdd-2234-ac2")
    locations = _orte()
    preset = _lege_vergleich_an(uid, locations)

    _vorschau(uid)
    nach_vorschau = provider.call_count
    assert nach_vorschau == 3

    _versand(uid, preset, locations)

    assert provider.call_count == nach_vorschau, (
        "AC-2: der Versand (scheduler_dispatch_service) direkt nach der Vorschau "
        "darf keinen Anbieter-Abruf machen, tatsaechlich "
        f"{provider.call_count - nach_vorschau} zusaetzliche Abrufe"
    )


# ---------------------------------------------------------------------------
# AC-3: Doppelklick -> je Ort genau 1 Abruf (Single-Flight)
# ---------------------------------------------------------------------------

def test_ac3_concurrent_double_click_fetches_each_location_once(install_provider):
    from services.comparison_parallel import run_comparison_parallel

    provider = install_provider(CountingFakeProvider(delay_s=0.4))
    locations = _orte()
    barrier = threading.Barrier(2)
    ergebnisse: dict[int, object] = {}
    fehler: list[BaseException] = []

    def _klick(idx: int) -> None:
        try:
            barrier.wait(timeout=5)
            ergebnisse[idx] = run_comparison_parallel(
                locations=locations,
                time_window=TIME_WINDOW,
                target_date=_target_date(),
                official_alerts_enabled=False,
            )
        except BaseException as exc:  # pragma: no cover - nur Diagnose
            fehler.append(exc)

    threads = [threading.Thread(target=_klick, args=(i,)) for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert not fehler, f"Vorschau-Threads scheiterten: {fehler!r}"
    assert provider.call_count == len(locations), (
        "AC-3: zwei gleichzeitige Vorschauen desselben Vergleichs (leerer Cache) "
        f"duerfen je Ort genau EINEN Abruf machen ({len(locations)} gesamt), "
        f"tatsaechlich {provider.call_count}"
    )
    assert _projection(ergebnisse[0]) == _projection(ergebnisse[1])


# ---------------------------------------------------------------------------
# AC-4: angeglichenes Fenster
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("now, erwarteter_start, erwartetes_ende", [
    (datetime(2026, 10, 31, 14, 37, 12, tzinfo=timezone.utc),
     datetime(2026, 10, 31, 14, 0, tzinfo=timezone.utc),
     datetime(2026, 11, 4, 23, 59, 59, tzinfo=timezone.utc)),
    (datetime(2026, 10, 31, 23, 59, 30, tzinfo=timezone.utc),
     datetime(2026, 10, 31, 23, 0, tzinfo=timezone.utc),
     datetime(2026, 11, 4, 23, 59, 59, tzinfo=timezone.utc)),
    (datetime(2026, 11, 1, 0, 0, 0, tzinfo=timezone.utc),
     datetime(2026, 11, 1, 0, 0, tzinfo=timezone.utc),
     datetime(2026, 11, 5, 23, 59, 59, tzinfo=timezone.utc)),
    (datetime(2026, 10, 31, 10, 59, 59, tzinfo=timezone.utc),
     datetime(2026, 10, 31, 10, 0, tzinfo=timezone.utc),
     datetime(2026, 11, 4, 23, 59, 59, tzinfo=timezone.utc)),
])
def test_ac4_fetch_window_rounds_start_to_hour_and_ends_at_last_second_of_target_day(
    now, erwarteter_start, erwartetes_ende,
):
    from services.comparison_engine import COMPARE_FORECAST_HOURS, compare_fetch_window

    start, end = compare_fetch_window(now, COMPARE_FORECAST_HOURS)

    assert start == erwarteter_start
    assert end == erwartetes_ende
    # _validate_segment verlangt exakt timezone.utc (nicht ZoneInfo("UTC")).
    assert start.tzinfo is timezone.utc and end.tzinfo is timezone.utc
    # Kein Datenverlust gegenueber dem alten Fenster, aber KEIN Extra-Tag.
    soll_ende = now + timedelta(hours=COMPARE_FORECAST_HOURS)
    assert end >= soll_ende
    naechste_mitternacht = datetime.combine(
        soll_ende.date() + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc,
    )
    assert end < naechste_mitternacht
    assert start <= now


def test_ac4_fetch_window_is_stable_within_hour_and_end_stable_across_hours():
    from services.comparison_engine import compare_fetch_window

    a = compare_fetch_window(datetime(2026, 10, 31, 9, 0, 5, tzinfo=timezone.utc), 96)
    b = compare_fetch_window(datetime(2026, 10, 31, 9, 59, 50, tzinfo=timezone.utc), 96)
    c = compare_fetch_window(datetime(2026, 10, 31, 11, 20, 0, tzinfo=timezone.utc), 96)
    assert a == b, "Innerhalb derselben Stunde muss das Fenster identisch sein"
    assert a[1] == c[1], "Ueber die Stunde hinweg bleibt das Ende gleich (Covers-Treffer)"


def test_ac4_provider_receives_aligned_window(install_provider):
    """Die Zusicherung dort, wo sie WIRKT: das Fenster, das beim Anbieter ankommt."""
    provider = install_provider(CountingFakeProvider())
    vorher = datetime.now(timezone.utc)
    _run_engine(_orte()[:1])

    assert provider.windows, "Der Anbieter wurde gar nicht abgefragt"
    start, end = provider.windows[0]
    assert (start.minute, start.second, start.microsecond) == (0, 0, 0), (
        f"AC-4: Start muss auf einer vollen Stunde liegen, tatsaechlich {start.isoformat()}"
    )
    assert (end.hour, end.minute, end.second) == (23, 59, 59), (
        f"AC-4: Ende muss 23:59:59 UTC sein, tatsaechlich {end.isoformat()}"
    )
    assert end.date() == (vorher + timedelta(hours=96)).date(), (
        "AC-4: Ende liegt auf dem Kalendertag von now+96h (kein Extra-Tag)"
    )


def test_ac4_guard_aggregates_and_outlook_unchanged(install_provider):
    """Guard (muss gruen bleiben): Aggregate des Zieltags und der Ausblick
    entstehen aus der VOLLEN Zeitreihe -- der Umbau darf nicht auf das
    Segment-Fenster zuschneiden."""
    install_provider(CountingFakeProvider())
    loc = _orte()[0]
    result = _run_engine([loc])
    lr = result.locations[0]
    assert lr.error is None, lr.error

    target = _target_date()
    anchor = _series_anchor()
    fenster = [
        anchor + timedelta(hours=i) for i in range(24 * 6)
        if (anchor + timedelta(hours=i)).astimezone(VIENNA).date() == target
        and TIME_WINDOW[0] <= (anchor + timedelta(hours=i)).astimezone(VIENNA).hour <= TIME_WINDOW[1]
    ]
    werte = [_wert(ts, loc.lat) for ts in fenster]
    assert lr.temp_min == pytest.approx(min(werte))
    assert lr.temp_max == pytest.approx(max(werte))
    assert [_as_utc(dp.ts) for dp in lr.hourly_data] == fenster

    ausblick_tage = {_as_utc(dp.ts).astimezone(VIENNA).date() for dp in lr.outlook_hourly_data}
    assert len(ausblick_tage) == 3, (
        f"Ausblick braucht drei Folgetage aus raw_data, tatsaechlich {sorted(ausblick_tage)}"
    )


# ---------------------------------------------------------------------------
# AC-5: Vergleich bedient Trip-Etappe (True/True), Compare-Alarm (False/False)
#       holt eigenen Abruf
# ---------------------------------------------------------------------------

def test_ac5_comparison_entry_serves_trip_stage_but_not_compare_alert(install_provider):
    from app.models import GPXPoint, TripSegment
    from services.compare_location_weather_source import CompareLocationWeatherSource
    from services.segment_weather import SegmentWeatherService

    provider = install_provider(CountingFakeProvider())
    loc = _orte()[0]
    _run_engine([loc])
    nach_vergleich = provider.call_count
    assert nach_vergleich == 1

    # Trip-Etappe am selben Ort (Koordinate + Hoehe), innerhalb des Vergleichsfensters.
    start = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0) + timedelta(hours=26)
    point = GPXPoint(lat=loc.lat, lon=loc.lon, elevation_m=float(loc.elevation_m))
    etappe = TripSegment(
        segment_id="trip-2234-etappe-1", start_point=point, end_point=point,
        start_time=start, end_time=start + timedelta(hours=4), duration_hours=4.0,
        distance_km=0.0, ascent_m=0, descent_m=0,
    )
    trip_result = SegmentWeatherService(provider).fetch_segment_weather(
        etappe, enrich_ensemble=True, enrich_snow=True,
    )
    assert not trip_result.has_error
    assert provider.call_count == nach_vergleich, (
        "AC-5: die Trip-Etappe am selben Ort (Bucket Ensemble+Schnee) muss aus dem "
        "Vergleichs-Eintrag bedient werden, tatsaechlich "
        f"{provider.call_count - nach_vergleich} zusaetzliche Abrufe"
    )
    assert trip_result.segment.segment_id == "trip-2234-etappe-1"

    CompareLocationWeatherSource().fetch(
        "cmp-alarm-2234", loc.lat, loc.lon, elevation_m=loc.elevation_m,
        user_id=_uid("tdd-2234-ac5"),
    )
    assert provider.call_count == nach_vergleich + 1, (
        "AC-5: der Compare-Alarm (eigener Bucket ohne Ensemble/Schnee) macht "
        f"einen eigenen Abruf, tatsaechlich {provider.call_count - nach_vergleich}"
    )


# ---------------------------------------------------------------------------
# AC-6: Fehler / leere Reihe werden nicht gecacht, Fehlerform unveraendert
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("mode", ["error", "empty"])
def test_ac6_failed_or_empty_fetch_is_not_cached_and_good_one_is(install_provider, mode):
    locations = _orte()[:2]
    provider = install_provider(FailFirstProvider(fail_lat=locations[0].lat, mode=mode))

    erster = _run_engine(locations)
    assert provider.call_count == 2
    kaputt, gut = erster.locations
    if mode == "error":
        assert isinstance(kaputt.error, str) and "anbieter-stoerung-2234" in kaputt.error, (
            f"Fehlerform muss wie bisher result['error'] (Text) sein, tatsaechlich {kaputt.error!r}"
        )
    else:
        assert not kaputt.hourly_data, "Leere Reihe darf keine Stundenwerte erzeugen"
    assert gut.error is None and gut.hourly_data, "Die uebrigen Orte werden weiter ausgewertet"

    zweiter = _run_engine(locations)
    assert provider.call_count == 3, (
        "AC-6: Fehler bzw. leere Reihe darf NICHT gecacht werden -> der gestoerte "
        "Ort holt neu, der gute kommt aus dem Cache (3 Abrufe gesamt), tatsaechlich "
        f"{provider.call_count}"
    )
    assert zweiter.locations[0].error is None and zweiter.locations[0].hourly_data

    _run_engine(locations)
    assert provider.call_count == 3, (
        "AC-6: nach dem erfolgreichen Abruf sind beide Orte gecacht, "
        f"tatsaechlich {provider.call_count} Abrufe"
    )


# ---------------------------------------------------------------------------
# AC-7: zwei Nutzer teilen den Abruf, Budget nur beim Ausloeser, kein Leck;
#       alle drei Aufrufer reichen die echte user_id durch
# ---------------------------------------------------------------------------

def test_ac7_two_users_share_fetch_budget_only_at_trigger_and_no_leak(install_provider):
    provider = install_provider(CountingFakeProvider())
    uid_a, uid_b = _uid("tdd-2234-alice"), _uid("tdd-2234-bob")
    orte_a = _orte()[:1]
    orte_b = [replace(_orte()[0], id="bob-ort", name="Bobs Huette")]
    _lege_vergleich_an(uid_a, orte_a)
    _lege_vergleich_an(uid_b, orte_b)

    _vorschau(uid_a)
    result_b = _vorschau(uid_b)

    assert provider.call_count == 1, (
        f"AC-7: derselbe Ort bei zwei Nutzern teilt EINEN Abruf, tatsaechlich {provider.call_count}"
    )
    assert _user_calls(uid_a) == 1, (
        "AC-7: der ausloesende Nutzer A bucht den Abruf in seinem Tagesbudget, "
        f"tatsaechlich {_user_calls(uid_a)}"
    )
    assert _user_calls(uid_b) == 0, (
        f"AC-7: Nutzer B (Cache-Treffer) bucht nichts, tatsaechlich {_user_calls(uid_b)}"
    )
    lr_b = result_b.locations[0]
    assert lr_b.location.id == "bob-ort" and lr_b.location.name == "Bobs Huette"
    assert "Innsbruck" not in repr(_projection(result_b)) + lr_b.location.name


def test_ac7_preview_passes_real_user_id(install_provider):
    install_provider(CountingFakeProvider())
    uid = _uid("tdd-2234-vorschau")
    _lege_vergleich_an(uid, _orte())
    _vorschau(uid)
    assert _user_calls(uid) == 3, (
        "AC-7: die Vorschau muss die echte user_id bis zum Segment-Weg reichen "
        f"(3 Buchungen im Topf des Nutzers), tatsaechlich {_user_calls(uid)}"
    )
    assert _user_calls("default") == 0, "Nie ein Rueckfall auf 'default'"


def test_ac7_dispatch_passes_real_user_id(install_provider):
    install_provider(CountingFakeProvider())
    uid = _uid("tdd-2234-versand")
    locations = _orte()
    preset = _lege_vergleich_an(uid, locations)
    _versand(uid, preset, locations)
    assert _user_calls(uid) == 3, (
        "AC-7: der Versand muss die echte user_id bis zum Segment-Weg reichen, "
        f"tatsaechlich {_user_calls(uid)}"
    )
    assert _user_calls("default") == 0, "Nie ein Rueckfall auf 'default'"


def test_ac7_instant_compare_endpoint_passes_real_user_id(install_provider):
    from fastapi.testclient import TestClient

    from api.main import app
    from app.loader import save_location

    install_provider(CountingFakeProvider())
    uid = _uid("tdd-2234-sofort")
    for loc in _orte():
        save_location(loc, user_id=uid)

    resp = TestClient(app).get(
        f"/api/compare?location_ids=*&user_id={uid}&forecast_hours=96"
        f"&time_window_start={TIME_WINDOW[0]}&time_window_end={TIME_WINDOW[1]}"
        f"&target_date={_target_date().isoformat()}"
    )
    assert resp.status_code == 200, resp.text
    assert _user_calls(uid) == 3, (
        "AC-7: der Sofortvergleich muss die echte user_id bis zum Segment-Weg "
        f"reichen, tatsaechlich {_user_calls(uid)}"
    )
    assert _user_calls("default") == 0, "Nie ein Rueckfall auf 'default'"


# ---------------------------------------------------------------------------
# AC-8: >95 % Tagesbudget -> Vorschau/Versand nie gedrosselt, aber gebucht
# ---------------------------------------------------------------------------

def test_ac8_preview_and_dispatch_never_throttled_above_95_percent(install_provider):
    from services.forecast_budget import ForecastBudgetGate

    provider = install_provider(CountingFakeProvider())
    # Fix-Loop F002: das Tagesbudget ist VOLL (Stufe 2, >= 100 %). Dort wird
    # JEDE Prioritaet ausser ``user_briefing`` gedrosselt, unabhaengig vom
    # fairen Anteil -- ein Abruf mit "alert_check"/"polling" kaeme fuer genau
    # diesen Nutzer nicht mehr durch. Erst damit ist die Prioritaet dort
    # geprueft, wo sie WIRKT (bei 96 % liesse Stufe 1 einen Nutzer unter
    # seinem fairen Anteil auch mit "alert_check" durch).
    seed = ForecastBudgetGate(None)
    assert seed.reserve("user_briefing", units=ForecastBudgetGate.DAILY_BUDGET)
    assert seed.snapshot()["usage_ratio"] >= 1.0

    uid = _uid("tdd-2234-budget")
    vorab = ForecastBudgetGate(uid)
    assert not vorab.allow("alert_check"), "Vorbedingung: alert_check waere gedrosselt"
    assert not vorab.allow("polling"), "Vorbedingung: polling waere gedrosselt"
    assert vorab.allow("user_briefing")
    locations = _orte()
    preset = _lege_vergleich_an(uid, locations)

    result = _vorschau(uid)
    for lr in result.locations:
        assert lr.error is None, f"AC-8: Vorschau gedrosselt? error={lr.error!r}"
        assert lr.hourly_data
    assert provider.call_count == 3, "AC-8: die Vorschau erreicht den Anbieter"
    assert _user_calls(uid) == 3, (
        "AC-8: die Vorschau laeuft ueber das Budget-Gate (Prioritaet user_briefing) "
        f"und bucht beim Nutzer, tatsaechlich {_user_calls(uid)}"
    )

    from services.weather_cache import reset_shared_weather_cache_for_tests

    reset_shared_weather_cache_for_tests()  # Versand muss selbst abrufen
    _versand(uid, preset, locations)
    assert provider.call_count == 6, "AC-8: der Versand erreicht den Anbieter"
    assert _user_calls(uid) == 6, (
        f"AC-8: der Versand bucht ebenfalls ungedrosselt, tatsaechlich {_user_calls(uid)}"
    )


# ---------------------------------------------------------------------------
# Fix-Loop F001: segment_id am geteilten Segment-Weg ist nutzerneutral
# ---------------------------------------------------------------------------

def _mitschnitt_zeilen(lat: float) -> list[dict]:
    """Zeilen des Vorhersage-Mitschnitts (#2030) fuer eine Koordinate -- die
    Stelle, an der die ``segment_id`` des geteilten Segment-Wegs dauerhaft
    landet."""
    import json

    from app.loader import get_data_root
    from services.forecast_capture import DATEI_PRAEFIX, UNTERORDNER

    zeilen = []
    for pfad in sorted((get_data_root() / UNTERORDNER).glob(f"{DATEI_PRAEFIX}*.jsonl")):
        for roh in pfad.read_text(encoding="utf-8").splitlines():
            zeile = json.loads(roh)
            if abs(zeile["lat"] - lat) < 1e-6:
                zeilen.append(zeile)
    return zeilen


def test_f001_segment_id_is_user_neutral_and_same_for_two_users(install_provider, monkeypatch):
    from services.forecast_capture import reset_capture_state

    monkeypatch.setenv("GZ_FORECAST_CAPTURE", "1")
    reset_capture_state()
    provider = install_provider(CountingFakeProvider())
    uid_a, uid_b = _uid("tdd-2234-anna"), _uid("tdd-2234-ben")
    ort_a = replace(_orte()[0], id="anna-ort-17", name="Annas Basislager")
    ort_b = replace(_orte()[0], id="ben-ort-42", name="Bens Huettenziel")
    _lege_vergleich_an(uid_a, [ort_a])
    _lege_vergleich_an(uid_b, [ort_b])

    _vorschau(uid_a)
    reset_capture_state()  # Dedup leeren, damit auch der Treffer von B mitgeschnitten wird
    _vorschau(uid_b)

    assert provider.call_count == 1, (
        "F001: derselbe Ort unter zwei Namen/IDs trifft denselben Cache-Eintrag, "
        f"tatsaechlich {provider.call_count} Abrufe"
    )
    zeilen = _mitschnitt_zeilen(ort_a.lat)
    assert len(zeilen) == 2, f"Je Vorschau eine Mitschnitt-Zeile erwartet, tatsaechlich {len(zeilen)}"
    ids = {z["segment_id"] for z in zeilen}
    assert len(ids) == 1, (
        f"F001: beide Nutzer muessen dieselbe segment_id erzeugen, tatsaechlich {sorted(ids)}"
    )
    segment_id = ids.pop()
    for fremd in (ort_a.name, ort_b.name, ort_a.id, ort_b.id, uid_a, uid_b, "Innsbruck"):
        assert fremd not in segment_id, (
            f"F001: segment_id {segment_id!r} enthaelt Nutzerbezogenes ({fremd!r})"
        )


# ---------------------------------------------------------------------------
# Fix-Loop F003: die uebergebenen hours bilden das Fenster (Sofortvergleich 48)
# ---------------------------------------------------------------------------

def test_f003_instant_compare_window_follows_requested_hours(install_provider):
    from fastapi.testclient import TestClient

    from api.main import app
    from app.loader import save_location

    provider = install_provider(CountingFakeProvider())
    uid = _uid("tdd-2234-48h")
    save_location(_orte()[0], user_id=uid)

    vorher = datetime.now(timezone.utc)
    resp = TestClient(app).get(
        f"/api/compare?location_ids=*&user_id={uid}&forecast_hours=48"
        f"&time_window_start={TIME_WINDOW[0]}&time_window_end={TIME_WINDOW[1]}"
        f"&target_date={_target_date().isoformat()}"
    )
    assert resp.status_code == 200, resp.text
    assert provider.windows, "Der Anbieter wurde gar nicht abgefragt"
    _start, end = provider.windows[0]
    assert end.date() == (vorher + timedelta(hours=48)).date(), (
        "F003: das Fenster beim Anbieter muss aus den angeforderten 48 h gebildet "
        f"werden, Ende tatsaechlich {end.isoformat()}"
    )


# ---------------------------------------------------------------------------
# Fix-Loop F004: ohne user_id wird nie auf "default" gebucht
# ---------------------------------------------------------------------------

def test_f004_engine_without_user_id_never_books_default(install_provider):
    from services.forecast_budget import ForecastBudgetGate

    provider = install_provider(CountingFakeProvider())
    global_vorher = ForecastBudgetGate(None).snapshot()["calls_today"]

    _run_engine(_orte()[:1])

    assert provider.call_count == 1
    assert ForecastBudgetGate(None).snapshot()["calls_today"] == global_vorher + 1, (
        "Der Abruf laeuft ueber das Budget-Gate (globaler Topf gebucht)"
    )
    assert _user_calls("default") == 0, (
        "F004: ohne user_id darf der Abruf nie im Topf des Nutzers 'default' "
        f"landen, tatsaechlich {_user_calls('default')}"
    )
