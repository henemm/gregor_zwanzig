"""TDD RED — Issue #1697: geteilter Baustein ``services.trip_day``.

SPEC: docs/specs/modules/fix_1697_ortstag_statt_servertag.md (AC-6, AC-7, AC-8)

RED-Grund heute (gemessen): ``src/services/trip_day.py`` existiert noch
nicht — jeder Import in dieser Datei scheitert mit ``ModuleNotFoundError``.
``TripCommandProcessor`` traegt die drei Methoden (``_trip_tz``/
``_display_tz``/``_anchor_tz``) noch selbst (#1470), AC-8 ist also ebenfalls
rot.

Testpolitik (CLAUDE.md "Test-Politik: Zwei Schichten"): Kern-Schicht, kein
Netz, kein Mock — reine Funktionstests gegen echte ``Trip``/``Stage``/
``Waypoint``-Objekte und echte Zeitzonenaufloesung (``utils.timezone``).
Uhr: ``freeze_time`` (freezegun) fuer AC-7.

Pfadregel #1409: keine Pfadaufloesung noetig — diese Datei liest nichts von
der Platte, sie ruft nur echten Produktivcode gegen In-Memory-Objekte auf.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from freezegun import freeze_time

from app.trip import Stage, Trip, Waypoint

AUCKLAND_LAT, AUCKLAND_LON = -36.8485, 174.7633
LOS_ANGELES_LAT, LOS_ANGELES_LON = 34.0522, -118.2437
VIENNA_LAT, VIENNA_LON = 48.2082, 16.3738


def _wp(id_: str, lat: float, lon: float) -> Waypoint:
    return Waypoint(id=id_, name=id_, lat=lat, lon=lon, elevation_m=500.0,
                     arrival_calculated="12:00")


# ══════════════════════════════ AC-6: Rueckfallkette ══════════════════════════════


def test_ac6_direkter_treffer_nutzt_die_etappe_des_weltzeit_tages():
    """Treffer-Fall: die Etappe des Weltzeit-Tages tragt Wegpunkte -> ihre
    Zone bestimmt den Ortstag direkt, ohne Rueckfall.

    Nachgemessen (nicht angenommen): Auckland (UTC+12 im August) und der
    Weltzeit-Tag als Stage-Datum liefern einen ANDEREN Ortstag als das
    UTC-Datum — das beweist, dass die Berechnung wirklich die Zone des
    Wegpunkts benutzt, nicht bloss ``now_utc.date()`` durchreicht.
    """
    from services.trip_day import trip_local_today

    with freeze_time("2026-08-10T23:00:00+00:00"):
        now_utc = datetime.now(timezone.utc)
        weltzeit_tag = now_utc.date()  # 2026-08-10
        trip = Trip(
            id="ac6-treffer", name="Treffer",
            stages=[Stage(id="S1", name="S1", date=weltzeit_tag,
                          waypoints=[_wp("W0", AUCKLAND_LAT, AUCKLAND_LON)])],
        )
        erwartet = now_utc.astimezone(ZoneInfo("Pacific/Auckland")).date()
        assert erwartet != weltzeit_tag, (
            "Testvoraussetzung: Auckland-Ortstag muss vom Weltzeit-Tag abweichen"
        )
        result = trip_local_today(trip, now_utc)

    assert result == erwartet, (
        f"AC-6 (Treffer): trip_local_today() lieferte {result}, erwartet "
        f"{erwartet} (Auckland-Ortstag zum Zeitpunkt {now_utc.isoformat()})"
    )


def test_ac6_rueckfall_1_erste_etappe_mit_wegpunkten():
    """Rueckfall 1: keine Etappe traegt das Datum des Weltzeit-Tages, aber
    eine SPAETERE Etappe im ``stages``-Array hat Wegpunkte -> deren Zone
    wird benutzt (die ERSTE mit Wegpunkten, nicht irgendeine).

    Zwei Kandidatenzonen (Auckland zuerst, Los Angeles danach) stellen
    sicher, dass wirklich die ERSTE mit Wegpunkten gewinnt — beide Zonen
    liefern am selben ``now_utc`` unterschiedliche Kalendertage.
    """
    from services.trip_day import trip_local_today

    with freeze_time("2026-08-10T23:00:00+00:00"):
        now_utc = datetime.now(timezone.utc)
        trip = Trip(
            id="ac6-rueckfall1", name="Rueckfall1",
            stages=[
                Stage(id="S0", name="S0", date=date(2026, 1, 1), waypoints=[]),
                Stage(id="S1", name="S1", date=date(2026, 2, 1),
                      waypoints=[_wp("W1", AUCKLAND_LAT, AUCKLAND_LON)]),
                Stage(id="S2", name="S2", date=date(2026, 3, 1),
                      waypoints=[_wp("W2", LOS_ANGELES_LAT, LOS_ANGELES_LON)]),
            ],
        )
        assert trip.get_stage_for_date(now_utc.date()) is None, (
            "Testvoraussetzung: keine Etappe darf auf den Weltzeit-Tag treffen"
        )
        erwartet_auckland = now_utc.astimezone(ZoneInfo("Pacific/Auckland")).date()
        erwartet_la = now_utc.astimezone(ZoneInfo("America/Los_Angeles")).date()
        assert erwartet_auckland != erwartet_la, (
            "Testvoraussetzung: Auckland- und LA-Ortstag muessen sich "
            "unterscheiden, sonst ist der Test nicht diskriminierend"
        )
        result = trip_local_today(trip, now_utc)

    assert result == erwartet_auckland, (
        f"AC-6 (Rueckfall 1): trip_local_today() lieferte {result}, erwartet "
        f"{erwartet_auckland} (Zone der ERSTEN Etappe mit Wegpunkten = "
        "Auckland, S1 — nicht S2/Los Angeles)"
    )


def test_ac6_rueckfall_2_utc_konstante_ohne_wegpunkte():
    """Rueckfall 2: KEINE Etappe der Tour hat Wegpunkte -> die aus
    ``utils.timezone`` importierte UTC-Konstante greift, nicht ein
    hartverdrahtetes ``ZoneInfo("UTC")``."""
    from services.trip_day import anchor_tz, trip_local_today
    from utils.timezone import UTC

    with freeze_time("2026-08-10T23:00:00+00:00"):
        now_utc = datetime.now(timezone.utc)
        trip = Trip(
            id="ac6-rueckfall2", name="Rueckfall2",
            stages=[
                Stage(id="S0", name="S0", date=date(2026, 1, 1), waypoints=[]),
                Stage(id="S1", name="S1", date=date(2026, 2, 1), waypoints=[]),
            ],
        )
        result = trip_local_today(trip, now_utc)
        used_tz = anchor_tz(trip, now_utc)

    assert used_tz == UTC, (
        f"AC-6 (Rueckfall 2): anchor_tz() lieferte {used_tz!r}, erwartet die "
        "importierte UTC-Konstante aus utils.timezone"
    )
    assert result == now_utc.date(), (
        f"AC-6 (Rueckfall 2): trip_local_today() lieferte {result}, erwartet "
        f"{now_utc.date()} (UTC-Datum, da keine Etappe Wegpunkte traegt)"
    )


# ══════════════════════════════ AC-7: Sommerzeit ══════════════════════════════


def test_ac7_sommerzeit_fruehjahrs_umstellung_2026():
    """Europe/Vienna, Fruehjahrs-Umstellung 2026-03-29 (02:00 -> 03:00
    Ortszeit, nachgemessen: UTC-Sprung bei 01:00 UTC, Offset +1 -> +2).
    Der Ortstag muss kurz vor UND kurz nach der Umstellungsstunde korrekt
    2026-03-29 lauten — keine Rechenfalle "24,0 Stunden an jedem Tag"."""
    from services.trip_day import trip_local_today

    tag = date(2026, 3, 29)
    trip = Trip(
        id="ac7-fruehjahr", name="Fruehjahr",
        stages=[Stage(id="S1", name="S1", date=tag,
                      waypoints=[_wp("W0", VIENNA_LAT, VIENNA_LON)])],
    )

    with freeze_time("2026-03-29T00:59:00+00:00"):
        vor = trip_local_today(trip, datetime.now(timezone.utc))
    with freeze_time("2026-03-29T01:01:00+00:00"):
        nach = trip_local_today(trip, datetime.now(timezone.utc))

    assert vor == tag, (
        f"AC-7 (Fruehjahr, kurz vor Umstellung): trip_local_today() lieferte "
        f"{vor}, erwartet {tag}"
    )
    assert nach == tag, (
        f"AC-7 (Fruehjahr, kurz nach Umstellung): trip_local_today() lieferte "
        f"{nach}, erwartet {tag}"
    )


def test_ac7_sommerzeit_herbst_umstellung_2026():
    """Europe/Vienna, Herbst-Umstellung 2026-10-25 (03:00 -> 02:00
    Ortszeit, nachgemessen: UTC-Sprung bei 01:00 UTC, Offset +2 -> +1).
    Derselbe Ortstag muss vor UND nach der Umstellungsstunde stehen."""
    from services.trip_day import trip_local_today

    tag = date(2026, 10, 25)
    trip = Trip(
        id="ac7-herbst", name="Herbst",
        stages=[Stage(id="S1", name="S1", date=tag,
                      waypoints=[_wp("W0", VIENNA_LAT, VIENNA_LON)])],
    )

    with freeze_time("2026-10-25T00:59:00+00:00"):
        vor = trip_local_today(trip, datetime.now(timezone.utc))
    with freeze_time("2026-10-25T01:01:00+00:00"):
        nach = trip_local_today(trip, datetime.now(timezone.utc))

    assert vor == tag, (
        f"AC-7 (Herbst, kurz vor Umstellung): trip_local_today() lieferte "
        f"{vor}, erwartet {tag}"
    )
    assert nach == tag, (
        f"AC-7 (Herbst, kurz nach Umstellung): trip_local_today() lieferte "
        f"{nach}, erwartet {tag}"
    )


# ══════════════════════════════ AC-8: keine vierte Kopie ══════════════════════════════


def test_ac8_trip_command_processor_verliert_die_privaten_methoden():
    """Nach dem Umbau traegt ``TripCommandProcessor`` ``_trip_tz``/
    ``_display_tz``/``_anchor_tz`` NICHT mehr als eigene Implementierung —
    die Aufloesung existiert im Repo genau einmal, in ``trip_day.py``."""
    from services.trip_command_processor import TripCommandProcessor

    for methodenname in ("_trip_tz", "_display_tz", "_anchor_tz"):
        assert not hasattr(TripCommandProcessor, methodenname), (
            f"AC-8: TripCommandProcessor traegt noch '{methodenname}' als "
            "eigene Implementierung — sie muss nach services/trip_day.py "
            "verschoben sein (keine vierte Kopie)"
        )


def test_ac8_anchor_folgt_der_heutigen_etappe_nicht_der_ersten_der_tour():
    """Adversary-Hinweis (kein CRITICAL-Finding, Bestandsschutz): eine Tour
    ueber ZWEI Zonen — erste Etappe Auckland, die Etappe des HEUTIGEN
    Weltzeit-Tages Wien — muss ``anchor_tz()`` aus der Zone der HEUTIGEN
    Etappe ziehen (``display_tz(trip, weltzeit_tag)``), NICHT aus der
    ERSTEN Etappe der Tour (``trip_tz``) — genau das war die von #1470 mit
    der Neuseeland->Korsika-Tour als "zehn Stunden daneben" VERWORFENE
    Alternative. AC-8 verlangt diesen Bestandsschutz; die geerbte
    #1470-Suite (``test_drilldown_day_window_local_date.py``) deckt ihn nur
    indirekt ueber ``TripCommandProcessor`` ab — hier direkt gegen
    ``services.trip_day``."""
    from services.trip_day import anchor_tz, trip_tz
    from utils.timezone import tz_for_coords

    with freeze_time("2026-08-10T12:00:00+00:00"):
        now_utc = datetime.now(timezone.utc)
        heute = now_utc.date()
        trip = Trip(
            id="ac8-zwei-zonen", name="ZweiZonen",
            stages=[
                Stage(id="S0", name="S0", date=date(2026, 1, 1),
                      waypoints=[_wp("W0", AUCKLAND_LAT, AUCKLAND_LON)]),
                Stage(id="S1", name="S1", date=heute,
                      waypoints=[_wp("W1", VIENNA_LAT, VIENNA_LON)]),
            ],
        )
        auckland_zone = tz_for_coords(AUCKLAND_LAT, AUCKLAND_LON)
        vienna_zone = tz_for_coords(VIENNA_LAT, VIENNA_LON)
        assert auckland_zone != vienna_zone, (
            "Testvoraussetzung: Auckland- und Wien-Zone muessen sich "
            "unterscheiden, sonst ist der Test nicht diskriminierend"
        )
        assert trip_tz(trip) == auckland_zone, (
            "Testvoraussetzung: trip_tz() (erste Etappe MIT Wegpunkten) "
            "muss Auckland liefern"
        )

        result = anchor_tz(trip, now_utc)

    assert result == vienna_zone, (
        f"AC-8: anchor_tz() lieferte {result!r}, erwartet die Zone der "
        f"HEUTIGEN Etappe (Wien) {vienna_zone!r} — nicht die der ERSTEN "
        "Etappe der Tour (Auckland, #1470 verworfene Alternative)"
    )
