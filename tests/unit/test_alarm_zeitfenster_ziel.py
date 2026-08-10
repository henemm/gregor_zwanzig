"""TDD RED — Issue #1584: Ziel-Segment endet am Tagesfenster, nicht nach 2 h.

SPEC: docs/specs/modules/fix_1584_alarm_zeitfenster.md (AC-1, AC-2a, AC-2b,
AC-3, AC-4, AC-5).

Abgenommen wird die ZUGESTELLTE WIRKUNG: geht ein Alarm ueber den echten
``TripAlertService``-Sendepfad raus (``mail_sink`` gefuellt) oder nicht.
Kein Assert auf ``segment.end_time`` oder ``aggregated.thunder_level_max``
— einzige Ausnahme ist AC-5, das die Spec ausdruecklich als
Struktur-Zusicherung ohne eigene Wirkungsdimension ausweist.

Netz- und versandfrei: Der Provider unten ist ein echter Fake (kein
``Mock``/``patch``/``MagicMock``), E-Mail laeuft ueber die vorhandene
``mail_sink``-DI-Naht, Telegram/SMS sind auf Trip-Ebene aus und in den
Settings leer. Persistenz liegt in der pytest-isolierten
``app.loader.get_data_dir()``-Basis (#1133).

Ausfuehrung:
    uv run pytest tests/unit/test_alarm_zeitfenster_ziel.py -v \
        --disable-socket --allow-hosts=127.0.0.1
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta, timezone

import pytest

from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    MetricConfig,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripReportConfig,
    UnifiedWeatherDisplayConfig,
)
from app.trip import Stage, Trip, Waypoint
from services.segment_weather import SegmentWeatherService
from services.trip_alert import TripAlertService
from services.trip_segments import convert_trip_to_segments
from services.weather_cache import reset_shared_weather_cache_for_tests
from utils.timezone import tz_for_coords

from tests.helpers.alert_log_fixtures import settings_email_only

# Mitteleuropa (Europe/Vienna) — AC-1/AC-2a/AC-2b/AC-3.
ALPEN_LAT, ALPEN_LON = 47.0500, 11.5500
# Deutlicher UTC-Versatz WESTLICH von Wien (America/Los_Angeles, UTC-7/-8) —
# AC-4. Westlich ist Pflicht: bei fest verdrahtetem Europe/Vienna liegt das
# dort berechnete Fensterende VOR der Ankunft am Ziel, das Gewitter faellt
# heraus und der Alarm bleibt aus. Eine oestliche Zone (z.B. Neuseeland)
# wuerde die Mutation NICHT sehen, weil das Wiener Fenster dort zu weit ist.
SIERRA_LAT, SIERRA_LON = 39.1900, -120.2400


@pytest.fixture(autouse=True)
def _reset_cache():
    reset_shared_weather_cache_for_tests()
    yield
    reset_shared_weather_cache_for_tests()


def _utc(tz, day: date, hour: int, minute: int = 0) -> datetime:
    """Ortszeit -> UTC, exakt nach dem Muster aus trip_segments.py:182-191."""
    return (
        datetime.combine(day, time(hour, minute))
        .replace(tzinfo=tz)
        .astimezone(timezone.utc)
    )


class ThunderAtHourProvider:
    """Fake-Provider (KEIN Mock): liefert wie Open-Meteo eine volle,
    stuendliche Zeitreihe unabhaengig vom angefragten Fenster — 72 h ab
    ``anchor``. Genau die uebergebenen UTC-Stunden tragen
    ``thunder_level=HIGH``, alle anderen ``NONE``."""

    def __init__(self, anchor: datetime, thunder_hours: set[datetime]) -> None:
        self._anchor = anchor
        self._thunder = set(thunder_hours)

    @property
    def name(self) -> str:
        return "openmeteo"

    def fetch_forecast(
        self, location, start=None, end=None,
        enrich_ensemble: bool = True, enrich_snow: bool = True,
    ) -> NormalizedTimeseries:
        meta = ForecastMeta(
            provider=Provider.OPENMETEO, model="icon_d2", grid_res_km=2.2,
            run=self._anchor, interp="grid_point",
        )
        data = [
            ForecastDataPoint(
                ts=self._anchor + timedelta(hours=h),
                t2m_c=15.0,
                thunder_level=(
                    ThunderLevel.HIGH
                    if self._anchor + timedelta(hours=h) in self._thunder
                    else ThunderLevel.NONE
                ),
            )
            for h in range(72)
        ]
        return NormalizedTimeseries(meta=meta, data=data)


def _trip(
    trip_id: str, lat: float, lon: float, day: date, arrival_local: str,
    day_window: tuple[int, int] | None = None,
) -> Trip:
    """Tour mit scharfer Gewitter-Empfindlichkeit, E-Mail als einzigem Kanal.

    ``day_window=None`` -> keine ``day_window_*``-Felder gesetzt, also Default
    4/19 (AC-1..AC-5). ``day_window=(start, end)`` setzt die Felder dort, wo
    sie tatsaechlich wohnen: auf ``TripReportConfig`` (``models.py:885-886``),
    erreichbar ueber ``trip.report_config`` — NICHT direkt auf ``Trip`` (AC-6).
    """
    stage = Stage(
        id="T1", name="Tag 1", date=day,
        waypoints=[
            Waypoint(id="G1", name="Start", lat=lat - 0.05, lon=lon - 0.05,
                     elevation_m=1000, arrival_calculated="08:00"),
            Waypoint(id="G2", name="Tagesziel", lat=lat, lon=lon,
                     elevation_m=1400, arrival_calculated=arrival_local),
        ],
    )
    trip = Trip(
        id=trip_id, name="Zielsegment-Trip", stages=[stage], official_warnings=None,
        display_config=UnifiedWeatherDisplayConfig(
            trip_id=trip_id,
            metrics=[MetricConfig(metric_id="thunder", enabled=True)],
            metric_alert_levels={"thunder_level": "standard"},
        ),
    )
    trip.report_config = TripReportConfig(
        trip_id=trip_id, send_email=True, alert_on_changes=True,
    )
    if day_window is not None:
        trip.report_config.day_window_start_hour = day_window[0]
        trip.report_config.day_window_end_hour = day_window[1]
    trip.alert_cooldown_minutes = 0
    trip.official_alert_triggers_enabled = False
    trip.alert_channels = {"email": True, "telegram": False, "sms": False}
    return trip


def _calm(segment) -> SegmentWeatherData:
    """Briefing-Schnappschuss ohne Gewitter (= ``cached``-Seite)."""
    return SegmentWeatherData(
        segment=segment,
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.OPENMETEO, model="icon_d2",
                              grid_res_km=2.2),
            data=[],
        ),
        aggregated=SegmentWeatherSummary(thunder_level_max=ThunderLevel.NONE),
        fetched_at=datetime.now(timezone.utc),
        provider="openmeteo",
    )


def _alarm_mails(
    lat: float, lon: float, arrival_local: str, thunder_hour: int,
    day_window: tuple[int, int] | None = None,
) -> list:
    """Ein vollstaendiger Alarm-Lauf; gibt die tatsaechlich zugestellten
    Mails zurueck.

    Die frischen Daten entstehen ueber denselben Produktionsweg wie in
    ``TripAlertService._fetch_fresh_weather`` (``SegmentWeatherService.
    fetch_segment_weather(..., priority="alert_check")``, Fehler pro Segment
    verschluckt) — nur die dortigen ``datetime.now()``-Filter entfallen,
    damit der Test nicht von der realen Uhrzeit abhaengt.
    """
    tz = tz_for_coords(lat, lon)
    day = date.today()
    trip = _trip(f"t-{uuid.uuid4().hex[:8]}", lat, lon, day, arrival_local, day_window)

    segments = convert_trip_to_segments(trip, day)
    anchor = datetime.combine(day - timedelta(days=1), time(0, 0), tzinfo=timezone.utc)
    provider = ThunderAtHourProvider(anchor, {_utc(tz, day, thunder_hour)})

    fresh = []
    for seg in segments:
        try:
            fresh.append(
                SegmentWeatherService(provider).fetch_segment_weather(
                    seg, enrich_ensemble=False, enrich_snow=False,
                    priority="alert_check",
                )
            )
        except Exception:  # noqa: BLE001 — 1:1 wie _fetch_fresh_weather
            continue

    mails: list = []
    TripAlertService(
        settings=settings_email_only(),
        user_id=f"tdd-1584-{uuid.uuid4().hex[:6]}",
        throttle_hours=0,
        mail_sink=lambda subject, body: mails.append((subject, body)),
    ).check_and_send_alerts(trip, [_calm(s) for s in segments], fresh_weather=fresh)
    return mails


# ---------------------------------------------------------------------------
# Radar-/NowCast-Pfad (F003). Alle ACs oben laufen ueber
# ``check_and_send_alerts()`` — den Deviations-Pfad. Der Radar-Pfad
# (``check_radar_alerts()``, Produktionsaufruf api/routers/scheduler.py:86)
# hat eine EIGENE Segment-Auswahl mit einem eigenen „alle Segmente vorbei"-
# Abbruch (trip_alert.py:737-745) und wird davon nicht beruehrt. Genau dieser
# Pfad lieferte im Belegfall von #1584 systemweit nie einen Alarm.
# ---------------------------------------------------------------------------

# Reykjavik: Atlantic/Reykjavik ist ganzjaehrig UTC+0 OHNE Sommerzeit. Damit
# sind Ortszeit und UTC identisch und die Fixture kommt ohne Offset-Rechnung
# aus — der Radar-Pfad haengt an der echten Wanduhr (``datetime.now()``),
# die Zeiten muessen also zur Laufzeit gebildet werden.
ISLAND_LAT, ISLAND_LON = 64.1466, -21.9426
# Ausweichort fuer die UTC-Stunde 0 (Pacific/Auckland, UTC+12/+13) — s.
# ``radar_fixture_ort()``.
AUCKLAND_LAT, AUCKLAND_LON = -36.8485, 174.7633


def _radar_wet_frames(lat: float, lon: float) -> list:
    """Echte ``RadarFrame``-Objekte (kein Mock) ueber den dokumentierten
    DI-Seam ``frame_source``; kraeftiger Regen ab +5 Minuten, damit
    ``radar_alert_due(..., threshold_min=20)`` anschlaegt."""
    from providers.brightsky import RadarFrame

    now = datetime.now(timezone.utc)
    return [
        RadarFrame(timestamp=now + timedelta(minutes=5), precip_mm_h=12.0),
        RadarFrame(timestamp=now + timedelta(minutes=15), precip_mm_h=20.0),
    ]


def _persist_trip(trip, user_id: str) -> None:
    """Trip-JSON in die pytest-isolierte Nutzerablage schreiben.

    ``check_radar_alerts()`` liest die Trips selbst ueber ``load_all_trips()``
    — der Trip muss also auf Platte liegen. ``save_trip()`` scheidet aus, weil
    es Naismith-Compute-on-Save ausloest (#802) und die exakt gesetzten
    ``arrival_calculated`` ueberschreibt; genau darauf steht dieser Test.
    Muster aus ``tests/tdd/test_issue_822_radar_nowcast_segment.py``, hier
    zusaetzlich mit den Tagesfenster-Feldern.
    """
    import json

    from app.loader import get_briefings_dir

    rc = trip.report_config
    briefings = get_briefings_dir(user_id)
    briefings.mkdir(parents=True, exist_ok=True)
    payload = {
        "id": trip.id,
        "name": trip.name,
        "alert_cooldown_minutes": 0,
        "stages": [
            {
                "id": s.id, "name": s.name, "date": s.date.isoformat(),
                "waypoints": [
                    {"id": w.id, "name": w.name, "lat": w.lat, "lon": w.lon,
                     "elevation_m": w.elevation_m,
                     "arrival_calculated": w.arrival_calculated}
                    for w in s.waypoints
                ],
            }
            for s in trip.stages
        ],
        "report_config": {
            "trip_id": rc.trip_id, "send_email": True,
            "send_telegram": False, "send_sms": False,
            "day_window_start_hour": rc.day_window_start_hour,
            "day_window_end_hour": rc.day_window_end_hour,
        },
    }
    (briefings / f"{trip.id}.json").write_text(json.dumps(payload, indent=2))


def radar_fixture_window(arrival_utc: datetime, heute: date | None = None) -> tuple[int, int]:
    """Tagesfenster-Grenzen fuer die Radar-Fixture — REINE Funktion, damit die
    Tageszeit-Unabhaengigkeit deterministisch pruefbar ist (s.
    ``test_radar_fixture_ist_zu_jeder_tageszeit_kein_mitternachtsfenster``).

    Anforderung an die Fixture: ``end_hour`` muss <= der ORTS-Stunde der
    Ankunft sein, damit das Fensterende (HH:00) vor der Ankunft (HH:MM) liegt
    und der Randfall-Guard greift — das ist der Zweig, den der Test beweisen
    soll. Gleichzeitig MUSS ``start_hour < end_hour`` gelten: bei
    ``start_hour > end_hour`` entsteht ein Mitternachts-Fenster, und der Test
    liefe versehentlich durch einen anderen Zweig (F004).

    Die erste Fassung bildete ``start_hour = (end_hour - 6) % 24`` und wrappte
    dadurch fuer jede Ankunftsstunde < 6 auf einen groesseren Wert — zwischen
    00:00 und 05:59 UTC bewachte der Test nichts. ``start_hour = 0`` kann
    nicht wrappen; noetig ist dann nur noch ``end_hour >= 1``, worum sich
    ``radar_fixture_ort()`` kuemmert.
    """
    return 0, arrival_utc.astimezone(radar_fixture_tz(arrival_utc, heute)).hour


def _island_taugt(arrival_utc: datetime, heute: date) -> bool:
    """Traegt Reykjavik diese Ankunft — oder muss die Fixture ausweichen?

    Zwei Bedingungen, beide zwingend (s. ``radar_fixture_ort``):
    Ortsstunde >= 1 und Ortsdatum == ``heute``.
    """
    from zoneinfo import ZoneInfo

    lokal = arrival_utc.astimezone(ZoneInfo("Atlantic/Reykjavik"))
    return lokal.hour >= 1 and lokal.date() == heute


def radar_fixture_tz(arrival_utc: datetime, heute: date | None = None):
    """Zeitzone des Zielorts fuer die Radar-Fixture — s. ``radar_fixture_ort``."""
    from zoneinfo import ZoneInfo

    heute = heute if heute is not None else date.today()
    if _island_taugt(arrival_utc, heute):
        return ZoneInfo("Atlantic/Reykjavik")
    return ZoneInfo("Pacific/Auckland")


def radar_fixture_ort(arrival_utc: datetime, heute: date | None = None) -> tuple[float, float]:
    """Zielkoordinate der Radar-Fixture — REINE Funktion (s. Invarianten-Test).

    Standard ist Reykjavik (``Atlantic/Reykjavik``, ganzjaehrig UTC+0 OHNE
    Sommerzeit): Ortszeit == UTC, keine Offset-Rechnung, kein DST-Flattern.
    Die Ortsstunde ist dort gleich der UTC-Stunde — und muss >= 1 sein, damit
    ``start_hour = 0`` echt kleiner als ``end_hour`` ist.

    Ausgewichen wird nach Auckland (UTC+12/+13), wenn eine der beiden
    Bedingungen verletzt ist:

    * **Ortsstunde 0** — dann waere ``end_hour == 0`` und ``start_hour = 0``
      nicht mehr echt kleiner.
    * **Ortsdatum != ``heute``** — ``check_radar_alerts()`` sucht die Etappe
      ueber ``date.today()``; liegt die Ankunft (``jetzt`` minus drei Minuten)
      noch vor UTC-Mitternacht, waehrend ``date.today()`` schon auf dem neuen
      Tag steht, faende es die Etappe nicht. #1667 S1: genau dafuer stand hier
      bis 2026-08-10 ein ``pytest.skip`` fuer die ersten drei Minuten des
      UTC-Tages. In Auckland faellt dieselbe absolute Zeit auf 11:5x bzw.
      12:5x Ortszeit DES NEUEN TAGES — Datum und Stunde stimmen also beide.
    """
    heute = heute if heute is not None else date.today()
    if _island_taugt(arrival_utc, heute):
        return ISLAND_LAT, ISLAND_LON
    return AUCKLAND_LAT, AUCKLAND_LON


def _radar_mails_fuer_spaetankunft() -> list:
    """Baut einen Trip mit Spaetankunft RELATIV ZUM TAGESFENSTER und laesst den
    echten ``check_radar_alerts()`` darueber laufen. Gibt die zugestellten
    Mails zurueck (``mail_sink``, kein echter Versand).

    Der Radar-Pfad liest ``datetime.now()`` und ``date.today()`` direkt, es
    gibt keine Einspeise-Naht fuer die Zeit. Die Fixture wird deshalb um die
    aktuelle Uhr herum gebaut: Ankunft drei Minuten in der Vergangenheit,
    ``day_window_end_hour`` auf die ORTS-Stunde der Ankunft — damit liegt das
    Fensterende (HH:00) zwangslaeufig VOR der Ankunft (HH:MM) und der
    Randfall-Guard greift, unabhaengig davon, wie spaet es gerade ist.
    """
    from services.radar_service import RadarNowcastService

    now = datetime.now(timezone.utc)
    arrival = now - timedelta(minutes=3)
    # #1667 S1: Der frueher hier stehende ``pytest.skip`` fuer die ersten drei
    # Minuten des UTC-Tages ist entfallen. Die Ortswahl bekommt jetzt
    # ``date.today()`` uebergeben und weicht selbst nach Auckland aus, wenn die
    # Ankunft noch vor UTC-Mitternacht liegt — dann stimmt das ORTSdatum
    # wieder mit dem Etappendatum ueberein (s. ``radar_fixture_ort``).
    heute = date.today()
    dest_lat, dest_lon = radar_fixture_ort(arrival, heute)
    dest_tz = radar_fixture_tz(arrival, heute)
    start_hour, end_hour = radar_fixture_window(arrival, heute)
    arrival_local = arrival.astimezone(dest_tz)
    start_local = (arrival - timedelta(hours=4)).astimezone(dest_tz)

    trip_id = f"radar-{uuid.uuid4().hex[:8]}"
    stage = Stage(
        id="S1", name="Tag 1", date=date.today(),
        waypoints=[
            Waypoint(id="W1", name="Start",
                     lat=dest_lat - 0.05, lon=dest_lon - 0.05,
                     elevation_m=100,
                     arrival_calculated=start_local.strftime("%H:%M")),
            Waypoint(id="W2", name="Tagesziel",
                     lat=dest_lat, lon=dest_lon, elevation_m=200,
                     arrival_calculated=arrival_local.strftime("%H:%M")),
        ],
    )
    trip = Trip(id=trip_id, name="Radar-Zielsegment-Trip", stages=[stage])
    trip.report_config = TripReportConfig(
        trip_id=trip_id, send_email=True,
        day_window_start_hour=start_hour,
        day_window_end_hour=end_hour,
    )

    user_id = f"tdd-1584-radar-{uuid.uuid4().hex[:6]}"
    _persist_trip(trip, user_id)

    mails: list = []
    svc = TripAlertService(
        settings=settings_email_only(),
        user_id=user_id,
        throttle_hours=0,
        mail_sink=lambda subject, body: mails.append((subject, body)),
        radar_service=RadarNowcastService(frame_source=_radar_wet_frames),
    )
    svc.clear_radar_throttle(trip_id)
    svc.check_radar_alerts()
    return mails


def test_ac1_gewitter_17_uhr_am_tagesziel_wird_zugestellt():
    """AC-1: Ankunft 13:18 Ortszeit, Gewitter 17:00 Ortszeit -> Alarm geht raus."""
    mails = _alarm_mails(ALPEN_LAT, ALPEN_LON, "13:18", 17)
    assert mails, (
        "AC-1: Ein Gewitter (HIGH) um 17:00 Ortszeit am Tagesziel muss einen "
        "zugestellten Alarm ausloesen. Es wurde KEINE Mail zugestellt — das "
        "Ziel-Segment endet bei arrival_time + 2 h (15:18 Ortszeit), 17:00 "
        "liegt ausserhalb und wird nie aggregiert (trip_segments.py:258)."
    )


def test_ac2a_gewitter_1845_knapp_vor_fensterende_wird_zugestellt():
    """AC-2a: Gewitter 18:45 Ortszeit — innerhalb 19:00, weit ausserhalb der
    alten 2-h-Grenze (15:18). Die diskriminierende Haelfte des Grenzwertpaars."""
    mails = _alarm_mails(ALPEN_LAT, ALPEN_LON, "13:18", 18)
    assert mails, (
        "AC-2a: Ein Gewitter (HIGH) um 18:45 Ortszeit liegt knapp INNERHALB "
        "der Fenster-Obergrenze 19:00 und muss zugestellt werden. Es wurde "
        "keine Mail zugestellt — mit dem festen 2-h-Fenster (bis 15:18) faellt "
        "18:45 heraus."
    )


def test_ac2b_gewitter_1915_knapp_nach_fensterende_bleibt_aus():
    """AC-2b: Gewitter 19:15 Ortszeit — knapp ausserhalb 19:00. Bewacht die
    PO-Vorgabe „kein naechtlicher Alarm" an der tatsaechlichen Grenze."""
    mails = _alarm_mails(ALPEN_LAT, ALPEN_LON, "13:18", 19)
    assert not mails, (
        "AC-2b: Ein Gewitter um 19:15 Ortszeit liegt ausserhalb der "
        "Fenster-Obergrenze 19:00 — es darf KEIN Alarm zugestellt werden. "
        f"Tatsaechlich zugestellt: {[s for s, _ in mails]} (das Ziel-Segment "
        "reicht zu weit, z.B. bis Mitternacht oder unbegrenzt)."
    )


def test_ac3_spaetankunft_2030_faellt_nicht_aus_der_ueberwachung():
    """AC-3: Ankunft 20:30 Ortszeit (NACH day_window_end_hour), Gewitter
    20:45 -> Alarm geht trotzdem raus; der Randfall-Guard haelt ein
    minimales, gueltiges Fenster statt eines kollabierten Segments."""
    mails = _alarm_mails(ALPEN_LAT, ALPEN_LON, "20:30", 20)
    assert mails, (
        "AC-3: Bei Ankunft 20:30 Ortszeit (nach dem Tagesfenster-Ende 19:00) "
        "muss ein Gewitter um 20:45 weiterhin einen zugestellten Alarm "
        "ausloesen. Es kam keine Mail an — das Ziel-Segment ist kollabiert "
        "oder laeuft rueckwaerts, der Trip faellt still aus der Ueberwachung."
    )


def test_radar_fixture_ist_zu_jeder_tageszeit_kein_mitternachtsfenster():
    """F004: Beweist die Tageszeit-Unabhaengigkeit der Radar-Fixture.

    Der Radar-Test haengt an der echten Wanduhr — er laeuft immer nur zu
    genau einer Tageszeit, und dort, wo er gerade laeuft, sieht man den Fehler
    nicht. Die erste Fassung bildete ``start_hour = (end_hour - 6) % 24`` und
    erzeugte fuer jede Ankunftsstunde < 6 ein MITTERNACHTS-Fenster
    (``start_hour > end_hour``). Zwischen 00:00 und 05:59 UTC pruefte der Test
    damit einen anderen Zweig als den, den er beweisen soll — und blieb selbst
    dann gruen, wenn der Randfall-Guard komplett entfernt war.

    Weil die Uhr im Test nicht gestellt werden kann, ist die Fixture-Rechnung
    in reine Funktionen ausgelagert. Hier werden sie fuer JEDE Minute eines
    vollen Tages (1440 Faelle) gegen die beiden Invarianten geprueft:

      1. ``start_hour < end_hour``  -> niemals ein Mitternachts-Fenster
      2. ``end_hour`` == Ortsstunde der Ankunft -> das Fensterende (HH:00)
         liegt vor der Ankunft (HH:MM), der Randfall-Guard greift

    Zusaetzlich wird geprueft, dass das Ortsdatum dem ETAPPENdatum entspricht —
    ``check_radar_alerts()`` sucht die Etappe ueber ``date.today()``.

    #1667 S1: Der Durchlauf deckt jetzt auch die drei Minuten VOR
    UTC-Mitternacht ab, in denen die Ankunft (``jetzt`` minus drei Minuten)
    noch auf dem Vortag liegt, waehrend ``date.today()`` schon auf dem neuen
    Tag steht. Fuer sie stand hier bis 2026-08-10 ein ``pytest.skip``; sie sind
    der Grund, warum das Etappendatum als Parameter hereinkommt statt aus
    ``arrival.date()`` abgeleitet zu werden.
    """
    basis = datetime(2026, 8, 8, tzinfo=timezone.utc)
    faelle = [(basis + timedelta(minutes=m), (basis + timedelta(minutes=m)).date())
              for m in range(24 * 60)]
    # Ankunft kurz vor UTC-Mitternacht, Etappendatum bereits der Folgetag.
    faelle += [(basis - timedelta(minutes=m), basis.date()) for m in (1, 2, 3)]

    for arrival, heute in faelle:
        tz = radar_fixture_tz(arrival, heute)
        start_hour, end_hour = radar_fixture_window(arrival, heute)
        lokal = arrival.astimezone(tz)

        assert start_hour < end_hour, (
            f"F004: Bei Ankunft {arrival.isoformat()} ({lokal.strftime('%H:%M')} "
            f"Ortszeit, {tz}) ergibt die Fixture start_hour={start_hour} >= "
            f"end_hour={end_hour} — das ist ein Mitternachts-Fenster. Der "
            "Radar-Test pruefte dann einen anderen Zweig als den "
            "Randfall-Guard und bewachte nichts."
        )
        assert end_hour == lokal.hour, (
            f"F004: end_hour={end_hour} passt nicht zur Ortsstunde "
            f"{lokal.hour} bei {arrival.isoformat()} — das Fensterende laege "
            "nicht vor der Ankunft und der Randfall-Guard griefe nicht."
        )
        assert lokal.date() == heute, (
            f"F004: Ortsdatum {lokal.date()} != Etappendatum {heute} bei "
            f"{arrival.isoformat()} ({tz}) — check_radar_alerts() sucht die "
            "Etappe ueber date.today() und faende sie nicht."
        )


def test_radarpfad_spaetankunft_faellt_nicht_in_alle_segmente_vorbei():
    """F003: Derselbe Fall wie AC-3 — aber ueber den RADAR-Pfad.

    AC-3 behauptet in seinem Docstring, er beweise, dass der Trip nicht ueber
    den „alle Segmente vorbei"-Abbruch in ``trip_alert.py:737-745`` aus der
    Ueberwachung faellt. Das tut er NICHT: er laeuft ausschliesslich ueber
    ``check_and_send_alerts()`` (Deviations-Pfad) und beruehrt diesen Code
    nie. Der Radar-/NowCast-Pfad hat eine eigene Segment-Auswahl — und genau
    er lieferte im Belegfall von #1584 systemweit keinen Alarm.

    Aufbau (die Zeiten entstehen zur Laufzeit, weil der Radar-Pfad an der
    echten Wanduhr haengt; Ortszeit == UTC durch Atlantic/Reykjavik):

        Ankunft am Tagesziel   = jetzt - 3 Minuten
        day_window_end_hour    = Stunde der Ankunft
        -> Fensterende HH:00 liegt VOR der Ankunft HH:MM
           => Randfall-Guard greift => Zielsegment [Ankunft, Ankunft + 1 h]
        -> „jetzt" liegt in diesem Fenster, das Zielsegment ist das aktive

    Ohne den Randfall-Guard kollabiert das Zielsegment (Ende <= Start). Dann
    ist kein Segment aktiv, ``now`` liegt hinter dem Start des ersten
    Segments, und der Radar-Pfad nimmt den Zweig „alle Segmente vorbei" —
    der Trip verschwindet stumm aus der Ueberwachung, obwohl es regnet.

    Geprueft wird die WIRKUNG (zugestellte Mail ueber ``mail_sink``), nicht
    dass die Funktion durchlaeuft.
    """
    mails = _radar_mails_fuer_spaetankunft()
    assert mails, (
        "F003: Bei Spaetankunft muss der Radar-Pfad einen Alarm zustellen. Es "
        "kam keine Mail an — das Zielsegment ist kollabiert, kein Segment gilt "
        "als aktiv und check_radar_alerts() nimmt den Zweig 'alle Segmente "
        "vorbei' (trip_alert.py:737-745). Genau so faellt ein Trip stumm aus "
        "der Ueberwachung."
    )


def test_ac3b_spaetankunft_mindestfenster_reicht_nicht_in_die_nacht():
    """AC-3 Ergaenzung (Waechter): Das Randfall-Mindestfenster bei Spaetankunft
    darf NICHT in die Nacht hineinreichen.

    Warum AC-3 diese Aufweichung allein NICHT faengt: dort liegt das Gewitter
    um 20:45 Ortszeit, also 15 Minuten nach der Ankunft um 20:30 — das ist in
    JEDEM Mindestfenster ab einer Stunde enthalten. AC-3 beweist, DASS der
    Guard greift, aber nichts ueber die LAENGE des Fensters; es koennte still
    auf sechs Stunden wachsen und AC-3 bliebe gruen.

    Nachgerechnet fuer den 08.08. (CEST = UTC+2):

        Ankunft 20:30 Ortszeit         = 18:30 UTC
        Fensterende 19:00 Ortszeit     = 17:00 UTC  -> <= Ankunft,
                                         also greift der Randfall-Guard
        Mindestfenster RICHTIG (1 h)   = 19:30 UTC = 21:30 Ortszeit
        Mindestfenster AUFGEWEICHT(6h) = 00:30 UTC = 02:30 Ortszeit (Folgetag)

    Das Gewitter liegt um 22:00 Ortszeit (= 20:00 UTC): eine halbe Stunde NACH
    dem richtigen Mindestfenster-Ende (21:30) und damit ausserhalb — aber
    mitten in einem aufgeweichten Fenster, das bis in die Nacht reicht.

    Was NICHT funktioniert haette: jeder Zeitpunkt innerhalb der ersten Stunde
    nach der Ankunft (20:30-21:30 Ortszeit) liegt in BEIDEN Varianten
    innerhalb — gemessen fuer 21:00 Ortszeit: richtig drin, aufgeweicht drin.
    Genau das ist der blinde Fleck von AC-3.

    Fachlich ist das die Spaetankunfts-Haelfte derselben PO-Vorgabe, die
    AC-2b fuer den Normalfall bewacht: nachts geht kein teurer Alarm raus.
    """
    mails = _alarm_mails(ALPEN_LAT, ALPEN_LON, "20:30", 22)
    assert not mails, (
        "AC-3b: Das Mindestfenster bei Spaetankunft (20:30 Ortszeit) darf nur "
        "eine Stunde umfassen — ein Gewitter um 22:00 Ortszeit liegt danach "
        "und darf KEINEN Alarm ausloesen. Tatsaechlich zugestellt: "
        f"{[s for s, _ in mails]} — das Randfall-Fenster reicht weiter als "
        "arrival_time + 1 h und ueberwacht damit in die Nacht hinein, obwohl "
        "AC-2b genau das fuer den Normalfall ausschliesst."
    )


def test_mitternachtsfenster_22_2_klemmt_auf_mindestfenster():
    """F005 (Waechter): Ein Tagesfenster ueber Mitternacht (``start > end``,
    hier 22-2 Uhr) fuehrt am Zielsegment zum MINDESTFENSTER — und darf kein
    ueberweites Fenster erzeugen.

    Ein solches Fenster ist seit #1361/#1372 S1b gueltig, hat aber ein LOCH
    (hier 2:00-22:00). Das Zielsegment ist ein einzelnes zusammenhaengendes
    Intervall und kann ein Loch nicht abbilden. PO-Entscheidung 2026-08-08:
    Mitternachts-Fenster werden am Zielsegment bewusst NICHT unterstuetzt; es
    greift der Randfall-Guard (Mindestfenster 1 h).

    Dieser Test bewacht die Regression, die beim ersten Loesungsversuch
    entstanden war: „Fensterende = naechstes Auftreten von ``end_hour`` ab
    der Ankunft" schuettet das Loch still zu und liefert je nach Ankunftszeit
    1 h bis fast 24 h Fenster — fuer die meisten Tagesankuenfte (02:01-21:59)
    sogar 16-24 Stunden. Das widerspricht direkt AC-2b und AC-3b („kein
    ueberweites Fenster, nachts kein teurer Alarm").

    Nachgerechnet (CEST = UTC+2, Fenster 22-2 Uhr, Ankunft 14:00 Ortszeit):

        Fensterende 02:00 Ortszeit am Ankunftstag liegt VOR der Ankunft
        -> Randfall-Guard -> Zielsegment 14:00-15:00 Ortszeit
        (verworfene Wrap-Variante haette bis 02:00 des Folgetags gereicht
         = 12 Stunden, bei Ankunft 02:30 sogar 23,5 Stunden)

    Das Gewitter liegt um 23:00 Ortszeit: ausserhalb des Mindestfensters,
    aber mitten in der verworfenen Wrap-Variante. Was NICHT funktioniert
    haette: jeder Zeitpunkt zwischen 14:00 und 15:00 Ortszeit laege in
    BEIDEN Varianten innerhalb und bewiese nichts.
    """
    mails = _alarm_mails(ALPEN_LAT, ALPEN_LON, "14:00", 23, day_window=(22, 2))
    assert not mails, (
        "F005: Bei einem Mitternachts-Tagesfenster (22-2 Uhr) greift am "
        "Zielsegment das Mindestfenster (14:00-15:00 Ortszeit) — ein Gewitter "
        "um 23:00 Ortszeit liegt ausserhalb und darf KEINEN Alarm ausloesen. "
        f"Tatsaechlich zugestellt: {[s for s, _ in mails]} — das Fensterende "
        "wurde offenbar auf den Folgetag geschoben (Wrap-Behandlung). Damit "
        "entsteht ein 12- bis 24-stuendiges Alarmfenster, das AC-2b und AC-3b "
        "aushebelt."
    )


def test_ac4_ziel_ausserhalb_mitteleuropas_nutzt_ortszeit_am_ziel():
    """AC-4: Ziel in America/Los_Angeles (UTC-7/-8). Gewitter 17:00 ORTSZEIT
    am Ziel. Bei fest verdrahtetem Europe/Vienna laege das Fensterende vor
    der Ankunft und der Alarm bliebe aus."""
    mails = _alarm_mails(SIERRA_LAT, SIERRA_LON, "13:18", 17)
    assert mails, (
        "AC-4: Die Fenstergrenze muss nach der Ortszeit am ZIEL aufgeloest "
        "werden (tz_for_coords der letzten Wegpunkt-Koordinate). Es kam keine "
        "Mail an — entweder gilt weiterhin arrival_time + 2 h oder das Fenster "
        "wurde in Europe/Vienna statt in America/Los_Angeles berechnet."
    )


def test_ac4b_westzone_spaete_ankunft_fenster_endet_am_ortstag():
    """AC-4 Ergaenzung (Waechter): Der Kalendertag des Fensterendes ist der
    LOKALE Ankunftstag am Ziel — nicht der UTC-Tag.

    Warum AC-4 diese Verwechslung allein NICHT faengt: dort kommt der Trip um
    13:18 Ortszeit an; in America/Los_Angeles (UTC-7) ist das 20:18 UTC am
    SELBEN Datum. UTC-Tag und Ortstag stimmen ueberein, ein Vertauschen der
    beiden bleibt folgenlos und AC-4 bleibt gruen.

    Hier kommt der Trip um 18:00 Ortszeit an — damit faellt die Ankunft in UTC
    bereits auf den Folgetag und die beiden Tagesbegriffe trennen sich
    (nachgerechnet fuer den 08.08., PDT = UTC-7):

        Ankunft 18:00 Ortszeit      = 09.08. 01:00 UTC  (UTC-Datum 09.08.,
                                                         Ortsdatum 08.08.)
        Fensterende RICHTIG (Ortstag) = 08.08. 19:00 Ortszeit
                                      = 09.08. 02:00 UTC
        Fensterende FALSCH  (UTC-Tag) = 09.08. 19:00 Ortszeit
                                      = 10.08. 02:00 UTC   -> 24 h zu lang

    Das Gewitter liegt um 22:00 Ortszeit am Ankunftstag (= 09.08. 05:00 UTC):
    drei Stunden NACH dem richtigen Fensterende und damit klar ausserhalb —
    aber mitten im 24 h zu langen Fenster der UTC-Tag-Variante. Genau diese
    Differenz trennt die Faelle. 18:30 Ortszeit laege in BEIDEN Varianten
    innerhalb, 20:00 Ortszeit des Folgetages in BEIDEN ausserhalb; beide
    bewiesen nichts (derselbe Fehler wie beim urspruenglichen AC-2).

    Fachlich bewacht der Test dieselbe PO-Vorgabe wie AC-2b: nachts geht kein
    Alarm raus. Ein um einen ganzen Tag verschobenes Fenster wuerde das
    Tagesziel die komplette Nacht und den Folgetag hindurch ueberwachen.
    """
    mails = _alarm_mails(SIERRA_LAT, SIERRA_LON, "18:00", 22)
    assert not mails, (
        "AC-4b: Das Fensterende muss am LOKALEN Ankunftstag am Ziel gebildet "
        "werden. Ein Gewitter um 22:00 Ortszeit liegt nach dem Fensterende "
        "19:00 desselben Tages und darf KEINEN Alarm ausloesen. Tatsaechlich "
        f"zugestellt: {[s for s, _ in mails]} — der Kalendertag stammt "
        "offenbar aus dem UTC-Zeitstempel der Ankunft (arrival_time.date()) "
        "statt aus arrival_time.astimezone(dest_tz).date(); westlich von "
        "Greenwich ist das der Folgetag und das Fenster 24 h zu lang."
    )


def test_ac5_alt_trip_ohne_tagesfenster_nutzt_default_4_19():
    """AC-5 (strukturell, von der Spec ausdruecklich als Ausnahme von der
    Wirkungs-Regel ausgewiesen): Alt-Trip ohne ``day_window_*`` -> Default
    4/19, Fensterende 19:00 Ortszeit am Ankunftstag."""
    tz = tz_for_coords(ALPEN_LAT, ALPEN_LON)
    day = date.today()
    trip = _trip("t-ac5-alttrip", ALPEN_LAT, ALPEN_LON, day, "13:18")
    assert trip.report_config.day_window_start_hour is None
    assert trip.report_config.day_window_end_hour is None

    dest = convert_trip_to_segments(trip, day)[-1]
    expected = _utc(tz, day, 19)
    assert dest.segment_id == "Ziel"
    assert dest.end_time == expected, (
        "AC-5: Ein Trip ohne konfiguriertes Tagesfenster muss den Default "
        f"4/19 verwenden — das Ziel-Segment muss um {expected.isoformat()} "
        f"(19:00 Ortszeit) enden, tatsaechlich: {dest.end_time.isoformat()} "
        "(= Ankunft + 2 h)."
    )


def test_ac6_konfiguriertes_fenster_6_16_schliesst_gewitter_1630_aus():
    """AC-6 (Waechter, kein RED-Test — s. Spec): Tagesfenster abweichend auf
    6-16 Uhr konfiguriert, Ankunft 13:18, Gewitter 16:30 Ortszeit.

    16:30 liegt ZWISCHEN der konfigurierten Obergrenze (16:00) und der
    Default-Obergrenze (19:00) — genau deshalb trennt dieser Zeitpunkt die
    Faelle: bei hartcodiertem ``(4, 19)`` laege er innerhalb, der Alarm ginge
    faelschlich raus. 15:30 laege in beiden Varianten innerhalb, 19:30 in
    beiden ausserhalb; beide bewiesen nichts (derselbe Fehler wie beim
    urspruenglichen AC-2).
    """
    mails = _alarm_mails(ALPEN_LAT, ALPEN_LON, "13:18", 16, day_window=(6, 16))
    assert not mails, (
        "AC-6: Bei konfiguriertem Tagesfenster 6-16 Uhr liegt ein Gewitter um "
        "16:30 Ortszeit AUSSERHALB — es darf kein Alarm zugestellt werden. "
        f"Tatsaechlich zugestellt: {[s for s, _ in mails]}. Das Ziel-Segment "
        "reicht bis zur Default-Obergrenze 19:00 statt bis zur konfigurierten "
        "16:00 — resolve_configured_window() wird nicht (oder mit einem "
        "hartcodierten (4, 19)) aufgerufen, die Einstellbarkeit ist ausgehebelt."
    )
