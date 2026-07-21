"""Issue #1329, Scheibe C2: geteilter Radar-Nowcast-Frame-Cache (AC-1..AC-4, AC-9).

SPEC: docs/specs/modules/fix_1329_c2_radar_nowcast_cache.md
Ausfuehrung:
    uv run pytest tests/unit/test_radar_nowcast_cache_sharing.py -v

Kern-Schicht, netzfrei. Alle Tests nutzen den bestehenden DI-Seam
`RadarNowcastService(frame_source=callable(lat,lon)->list[RadarFrame])`
(`radar_service.py:79-81,86`) mit echten `RadarFrame`-Objekten -- KEINE
Mocks/patch/MagicMock (CLAUDE.md-Pflicht). Der zaehlende `frame_source`-Fake
implementiert nur eine normale Python-Callable, kein Mock-Objekt.

RED-Erwartung: `services.radar_cache` existiert noch nicht -> der Import
unten schlaegt fehl -> ALLE Tests in dieser Datei sind rot (Collection-
Error). Das ist die korrekte RED-Aussage fuer ein komplett neues Modul
(analog `test_forecast_cache_sharing.py` fuer den Forecast-Pfad in der
Vorgaenger-Scheibe C). Sobald `radar_cache.py` existiert, faellt dieser
Import weg vom Fehlerpfad und die einzelnen Assertions greifen.

Zusaetzlich pruefen mehrere Tests `RadarNowcastService(..., now_fn=...)`
(injizierbare Uhr) -- dieser Konstruktor-Parameter existiert heute ebenfalls
noch nicht; ein `TypeError: unexpected keyword argument 'now_fn'` ist dort
die erwartete RED-Aussage (Spec, Implementation Details Abschnitt 2).
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

import pytest

from providers.brightsky import RadarFrame
from services.radar_service import RadarNowcastService
from services.radar_cache import (  # noqa: E402  (RED: Modul existiert noch nicht)
    get_shared_radar_cache,
    reset_shared_radar_cache_for_tests,
)


@pytest.fixture(autouse=True)
def _reset_shared_radar_cache():
    """Isoliert den Prozess-Singleton zwischen Tests (Muster
    `reset_shared_weather_cache_for_tests()` aus der Vorgaenger-Scheibe)."""
    reset_shared_radar_cache_for_tests()
    yield
    reset_shared_radar_cache_for_tests()


# ---------------------------------------------------------------------------
# Helpers (echte Objekte, kein Mock-Theater)
# ---------------------------------------------------------------------------

def _dry_frames(now: datetime, count: int = 8, step_min: int = 5) -> list[RadarFrame]:
    return [
        RadarFrame(timestamp=now + timedelta(minutes=i * step_min), precip_mm_h=0.0)
        for i in range(count)
    ]


class CountingFrameSource:
    """Zaehlender Fake (KEIN Mock/patch) -- erfuellt den bestehenden DI-Seam
    `frame_source: Callable[[float, float], list[RadarFrame]]`
    (`radar_service.py:79-81,86`) mit einer normalen Python-Callable, die
    jeden Aufruf INSGESAMT und pro Koordinate zaehlt."""

    def __init__(self, frames_factory=None) -> None:
        self.call_count = 0
        self.calls: list[tuple[float, float]] = []
        self._frames_factory = frames_factory or (
            lambda lat, lon: _dry_frames(datetime.now(timezone.utc))
        )

    def __call__(self, lat: float, lon: float) -> list:
        self.call_count += 1
        self.calls.append((lat, lon))
        return self._frames_factory(lat, lon)


# ---------------------------------------------------------------------------
# AC-1: gleiche Koordinate, zwei Default-Instanzen -> EIN Fetch
# ---------------------------------------------------------------------------

def test_two_default_instances_same_coordinate_share_one_fetch():
    """AC-1: zwei unabhaengig konstruierte `RadarNowcastService()`-Instanzen
    (wie in `trip_alert.py:556-561`/`compare_radar_alert.py:172-176`
    tatsaechlich gebaut) an derselben Koordinate teilen sich EINEN Fetch
    ueber den geteilten Singleton-Cache."""
    source = CountingFrameSource()
    svc_a = RadarNowcastService(frame_source=source)
    svc_b = RadarNowcastService(frame_source=source)

    svc_a.get_nowcast(47.0, 11.0)
    svc_b.get_nowcast(47.0, 11.0)

    assert source.call_count == 1, (
        "AC-1: zwei get_nowcast-Aufrufe fuer dieselbe Koordinate innerhalb "
        f"des TTL muessen sich EINEN Fetch teilen (Cache-Hit beim zweiten "
        f"Aufruf), tatsaechliche Fetches: {source.call_count}"
    )


# ---------------------------------------------------------------------------
# AC-2: unterschiedliche Koordinate -> ZWEI Fetches
# ---------------------------------------------------------------------------

def test_different_coordinate_causes_two_fetches():
    source = CountingFrameSource()
    svc = RadarNowcastService(frame_source=source)

    svc.get_nowcast(47.0, 11.0)
    svc.get_nowcast(46.0, 10.0)

    assert source.call_count == 2, (
        "AC-2: unterschiedliche Koordinaten duerfen NICHT denselben "
        f"Cache-Eintrag treffen, tatsaechliche Fetches: {source.call_count}"
    )


# ---------------------------------------------------------------------------
# AC-3: TTL-Ablauf (300s) -> erneuter Fetch, kein stiller Stale-Serve
# ---------------------------------------------------------------------------

def test_ttl_expiry_after_300s_triggers_new_fetch_via_injected_clock():
    """AC-3: injizierbare Uhr (`now_fn`) statt `sleep` -- bei 300s TTL nicht
    praktikabel (Test Plan der Spec)."""
    source = CountingFrameSource()
    t0 = datetime.now(timezone.utc)
    clock = {"now": t0}
    svc = RadarNowcastService(frame_source=source, now_fn=lambda: clock["now"])

    svc.get_nowcast(48.0, 9.0)
    assert source.call_count == 1

    clock["now"] = t0 + timedelta(seconds=301)  # > 300s TTL
    svc.get_nowcast(48.0, 9.0)

    assert source.call_count == 2, (
        "AC-3: ein Cache-Eintrag aelter als der TTL (300s) muss verworfen "
        f"werden -> erneuter Fetch, tatsaechliche Fetches: {source.call_count}"
    )


def test_within_ttl_second_call_is_cache_hit_no_new_fetch():
    source = CountingFrameSource()
    t0 = datetime.now(timezone.utc)
    clock = {"now": t0}
    svc = RadarNowcastService(frame_source=source, now_fn=lambda: clock["now"])

    svc.get_nowcast(48.1, 9.1)
    clock["now"] = t0 + timedelta(seconds=120)  # < 300s TTL
    svc.get_nowcast(48.1, 9.1)

    assert source.call_count == 1, (
        "Ein <300s alter Cache-Eintrag darf keinen erneuten Fetch ausloesen, "
        f"tatsaechliche Fetches: {source.call_count}"
    )


# ---------------------------------------------------------------------------
# AC-4: Onset wird bei Cache-Hit IMMER frisch aus den rohen Frames berechnet
# (Lehre aus Adversary-Fund F001 der Vorgaenger-Scheibe C)
# ---------------------------------------------------------------------------

def test_onset_recomputed_fresh_on_cache_hit_from_same_raw_frames():
    """AC-4: der Cache speichert nur die ROHEN Frames, NIE ein fertiges
    `NowcastResult` -- ein Cache-Hit ein paar simulierte Minuten spaeter
    liefert einen entsprechend verschobenen `onset_minutes`, niemals
    denselben Wert wie beim ersten Aufruf."""
    t0 = datetime.now(timezone.utc)
    fixed_onset_dt = t0 + timedelta(minutes=20)

    def factory(lat, lon):
        return [RadarFrame(timestamp=fixed_onset_dt, precip_mm_h=3.0)]

    source = CountingFrameSource(frames_factory=factory)
    clock = {"now": t0}
    svc = RadarNowcastService(frame_source=source, now_fn=lambda: clock["now"])

    r1 = svc.get_nowcast(45.9, 8.9)
    clock["now"] = t0 + timedelta(minutes=3)  # innerhalb TTL -> Cache-Hit
    r2 = svc.get_nowcast(45.9, 8.9)

    assert source.call_count == 1, (
        "Cache-Hit erwartet: nur EIN Fetch fuer beide Aufrufe, tatsaechlich: "
        f"{source.call_count}"
    )
    assert r1.onset_minutes == 20
    assert r2.onset_minutes is not None
    assert abs(r2.onset_minutes - (r1.onset_minutes - 3)) <= 1, (
        f"AC-4: Onset muss bei Cache-Hit relativ zur AKTUELLEN Zeit neu "
        f"berechnet werden (r1.onset_minutes={r1.onset_minutes}, "
        f"r2.onset_minutes={r2.onset_minutes}) -- nicht aus einem "
        "gecachten fertigen Ergebnis uebernommen werden."
    )


# ---------------------------------------------------------------------------
# AC-5: leere Frame-Liste (Fehlschlag) wird NIE gecacht
# ---------------------------------------------------------------------------

def test_empty_fetch_result_is_never_cached():
    call_log: list[int] = []

    def factory(lat, lon):
        call_log.append(1)
        if len(call_log) == 1:
            return []
        return _dry_frames(datetime.now(timezone.utc))

    source = CountingFrameSource(frames_factory=factory)
    svc = RadarNowcastService(frame_source=source)

    r1 = svc.get_nowcast(30.0, 30.0)
    r2 = svc.get_nowcast(30.0, 30.0)

    assert r1.frames == []
    assert source.call_count == 2, (
        "AC-5: ein leerer Fetch (Fehlschlag/kein Signal) darf NICHT gecacht "
        f"werden -- der zweite Aufruf muss erneut fetchen (kein "
        f"Cache-Treffer auf einen leeren Eintrag), tatsaechliche Fetches: "
        f"{source.call_count}"
    )


# ---------------------------------------------------------------------------
# AC-9: Trip-Radar-Pfad und Compare-Radar-Pfad am selben Ort teilen sich
# einen Fetch ueber die ECHTEN Produktionskonstruktionspfade.
# ---------------------------------------------------------------------------

def test_two_default_instances_mimicking_trip_and_compare_construction_share_cache():
    """AC-9 (einfache Variante): zwei unabhaengig konstruierte
    `RadarNowcastService()`-Instanzen mit identischer Koordinate teilen
    sich EINEN Fetch -- direkter Nachweis der Singleton-Cache-Teilung
    (Test-Plan-Vorgabe, gleiche Konstruktion wie `trip_alert.py:556-561`
    und `compare_radar_alert.py:172-176`)."""
    source = CountingFrameSource()
    trip_side = RadarNowcastService(frame_source=source)
    compare_side = RadarNowcastService(frame_source=source)

    trip_side.get_nowcast(45.5, 9.2)
    compare_side.get_nowcast(45.5, 9.2)

    assert source.call_count == 1, (
        "AC-9: Trip-Radar- und Compare-Radar-Pfad am selben Ort im selben "
        f"Zyklus muessen sich EINEN Fetch teilen, tatsaechliche Fetches: "
        f"{source.call_count}"
    )

    cache = get_shared_radar_cache()
    assert len(cache._cache) == 1, (
        "AC-9: der geteilte Singleton-Cache muss genau EINEN Eintrag fuer "
        f"den gemeinsamen Ort enthalten, tatsaechlich: {len(cache._cache)}"
    )


def test_end_to_end_trip_and_compare_radar_paths_share_one_fetch(monkeypatch):
    """AC-9 (End-to-End): `TripAlertService.check_radar_alerts()` und
    `CompareRadarAlertService._detect_triggered_locations()` konstruieren
    JEWEILS ihre EIGENE `RadarNowcastService()` OHNE `frame_source`
    (echte Produktionspfade, `trip_alert.py:556-561`,
    `compare_radar_alert.py:172-176`). Monkeypatch ersetzt NUR, welche
    Klasse referenziert wird (echter Python-Klassenaustausch ueber
    Vererbung, kein Mock/patch von Verhalten) durch eine Variante mit
    voreingestelltem zaehlendem `frame_source` -- die eigentliche
    Cache-/Singleton-Logik der echten `RadarNowcastService` bleibt dabei
    unveraendert wirksam, weil die Ersatzklasse von ihr erbt."""
    from app.loader import save_trip
    from app.trip import Stage, Trip, Waypoint
    from app.user import SavedLocation
    from services.compare_radar_alert import CompareRadarAlertService
    from services.trip_alert import TripAlertService

    source = CountingFrameSource()

    class _PreWiredRadarNowcastService(RadarNowcastService):
        def __init__(self, *a, **kw):
            kw.setdefault("frame_source", source)
            super().__init__(*a, **kw)

    import services.radar_service as radar_service_module
    monkeypatch.setattr(radar_service_module, "RadarNowcastService", _PreWiredRadarNowcastService)

    lat, lon = 46.5, 12.0
    today = date.today()
    trip = Trip(
        id="ac9-e2e-trip",
        name="AC9 E2E Trip",
        stages=[
            Stage(
                id="T1",
                name="Heute",
                date=today,
                start_time=time(0, 0),
                waypoints=[
                    Waypoint(
                        id="W1", name="Start", lat=lat, lon=lon, elevation_m=1000,
                        arrival_override="00:00",
                    ),
                    Waypoint(
                        id="W2", name="Ziel", lat=lat + 0.02, lon=lon + 0.02,
                        elevation_m=1100, arrival_override="23:59",
                    ),
                ],
            )
        ],
    )
    save_trip(trip)

    trip_svc = TripAlertService(user_id="default")
    trip_svc.clear_radar_throttle(trip.id)
    trip_svc.check_radar_alerts()

    loc = SavedLocation(id="loc-ac9-e2e", name="Ort", lat=lat, lon=lon, elevation_m=1000)
    compare_svc = CompareRadarAlertService(user_id="default")
    compare_svc._detect_triggered_locations(
        "preset-ac9-e2e", ["loc-ac9-e2e"], {"loc-ac9-e2e": loc}
    )

    assert source.call_count == 1, (
        "AC-9 End-to-End: Trip-Radar-Check und Compare-Radar-Check am "
        f"selben Ort ueber die tatsaechlichen Produktionskonstruktionspfade "
        f"muessen sich EINEN Fetch teilen, tatsaechliche Fetches: "
        f"{source.call_count}"
    )


# ---------------------------------------------------------------------------
# Adversary-Fund F001 (Issue #1329 C2, BROKEN-Verdict): Region-Bucket MUSS
# Bestandteil des Cache-Schluessels sein. Zwei Koordinaten beidseits einer
# harten Routing-Grenze (RADOLAN-Suedrand lat=47.0) runden auf denselben
# Koordinaten-Schluessel, gehoeren aber zu VERSCHIEDENEN Regionen -- ohne
# Region im Schluessel wuerde der zweite Aufruf die Frames/Quelle des
# ersten erben, ohne die eigene Quellenkette zu durchlaufen.
# ---------------------------------------------------------------------------

def test_boundary_coordinates_do_not_share_cache_across_region_change(monkeypatch):
    """Regressionsschutz F001: `46.99999/10.0` liegt knapp AUSSERHALB
    RADOLAN (lat < 47.0, aber innerhalb INCA) -- `47.00001/10.0` liegt
    knapp INNERHALB RADOLAN. `round(46.99999, 4) == round(47.00001, 4) ==
    47.0` -- beide Koordinaten fallen auf denselben gerundeten
    Koordinaten-Schluessel, gehoeren aber zu verschiedenen Regionen. Jede
    Koordinate muss ihre EIGENE, regionsspezifische Fetch-Methode
    anstossen -- kein falscher Cache-Treffer ueber die Grenze hinweg.

    Netzfrei durch echten Methodenaustausch (Muster
    `test_issue_1161_inca_convective.py`/`test_issue_1162_radar_dpc.py`):
    `_fetch_brightsky`/`_fetch_geosphere_inca` werden durch echte,
    zaehlende Python-Funktionen ersetzt, die sofort nicht-leere Frames
    liefern -- die Kette bricht dadurch direkt nach dem ersten Treffer ab,
    kein weiterer (ungeschuetzter) Provider-Zweig wird erreicht.
    """
    calls: list[tuple[str, float, float]] = []

    def _fake_brightsky(self, lat, lon):
        calls.append(("brightsky", lat, lon))
        now = datetime.now(timezone.utc)
        return [RadarFrame(timestamp=now + timedelta(minutes=5), precip_mm_h=0.0)]

    def _fake_geosphere(self, lat, lon):
        calls.append(("geosphere", lat, lon))
        now = datetime.now(timezone.utc)
        return [RadarFrame(timestamp=now + timedelta(minutes=5), precip_mm_h=0.0)]

    monkeypatch.setattr(RadarNowcastService, "_fetch_brightsky", _fake_brightsky)
    monkeypatch.setattr(RadarNowcastService, "_fetch_geosphere_inca", _fake_geosphere)

    svc = RadarNowcastService()
    result_outside = svc.get_nowcast(46.99999, 10.0)  # knapp AUSSERHALB RADOLAN -> INCA
    result_inside = svc.get_nowcast(47.00001, 10.0)   # knapp INNERHALB RADOLAN

    assert [c[0] for c in calls] == ["geosphere", "brightsky"], (
        "F001-Regressionsschutz: beide Koordinaten runden auf denselben "
        "Koordinaten-Schluessel, liegen aber in verschiedenen Regionen -- "
        "jede muss ihre EIGENE Fetch-Methode anstossen (kein falscher "
        f"Cache-Treffer ueber die Grenze), tatsaechliche Aufrufreihenfolge: "
        f"{calls}"
    )
    assert result_outside.source == "INCA"
    assert result_inside.source == "radar"


def test_same_region_coordinates_rounding_to_identical_key_still_share_one_fetch(monkeypatch):
    """Gegenprobe zu F001: der ~11m-Dedup-Nutzen INNERHALB einer Region
    bleibt erhalten. Zwei Koordinaten weit im RADOLAN-Inneren (keine
    Grenznaehe), die auf denselben gerundeten Wert fallen, teilen sich
    weiterhin EINEN Fetch."""
    calls: list[tuple[float, float]] = []

    def _fake_brightsky(self, lat, lon):
        calls.append((lat, lon))
        now = datetime.now(timezone.utc)
        return [RadarFrame(timestamp=now + timedelta(minutes=5), precip_mm_h=0.0)]

    monkeypatch.setattr(RadarNowcastService, "_fetch_brightsky", _fake_brightsky)

    svc = RadarNowcastService()
    svc.get_nowcast(47.5, 10.0)        # tief im RADOLAN-Inneren
    svc.get_nowcast(47.50001, 10.00001)  # rundet auf denselben Schluessel, gleiche Region

    assert len(calls) == 1, (
        "Zwei Koordinaten, die auf denselben gerundeten Wert fallen UND in "
        "derselben Region liegen, muessen sich weiterhin EINEN Fetch "
        f"teilen (Dedup-Nutzen bleibt erhalten), tatsaechliche Fetches: "
        f"{len(calls)}"
    )
