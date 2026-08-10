"""Waechter fuer die tragenden Zusicherungen von ``arrival_window_fixtures``.

Warum es diese Datei gibt
-------------------------
Der Fixture-Helfer aus #1667 S1 traegt drei Zusicherungen, ohne die die zwoelf
umgestellten Alarm-/Radar-Testdateien zwischen ~22:00 und 00:00 UTC wieder rot
werden. Bis 2026-08-10 waren sie NUR durch einmalige, von Hand gestartete
``freeze_time``-Laeufe belegt, deren Ausgabe als Text in einem Artefakt lag.

Die Adversary-Gegenprobe hat gezeigt, was das wert war: zwei Verfaelschungen
von Zusicherungen, die der Helfer-Docstring selbst „tragend" nennt, blieben im
gesamten committeten Testbestand unbemerkt —

* Monotonie-Untergrenze entfernt (``max(r, vorher + 1)`` -> ``r``): voller
  Suitenlauf gruen, auch an allen vier Kippkanten unter gestellter Uhr (F002).
* Obere Klemme ``1439`` -> ``1440``: voller Suitenlauf gruen, nur ein gezielter
  Handlauf fing es (F003).

Das ist derselbe Fehler, den S1 beheben sollte, eine Ebene hoeher: der Schutz
existierte als Bericht, nicht als Mechanismus. Diese Datei macht ihn zum
Mechanismus.

Zwei Schichten, mit Absicht
---------------------------
1. ``fenster_minuten()`` ist eine REINE Funktion (Minute seit
   Ortszeit-Mitternacht rein, Wegpunkt-Minuten raus). Sie wird hier ueber ALLE
   1440 Minuten eines Tages plus die Raender davor und danach geprueft —
   deterministisch, ohne Uhr, ohne Zeitzonendaten, in jedem CI-Lauf.
2. Der Wirkort ist aber nicht die Rechnung, sondern das fertige Segment. Die
   Wirkungs-Tests unten stellen deshalb die Uhr auf die Kippkanten und lassen
   den ECHTEN ``convert_trip_to_segments`` ueber einen ECHTEN Trip laufen —
   „ist die Zusicherung dort geprueft, wo sie WIRKT?" Damit wird ``freezegun``
   auch tatsaechlich benutzt statt nur in ``pyproject.toml`` zu stehen (F001).

Kein Netz, kein Mock: Schicht 1 ist Arithmetik, Schicht 2 baut echte
Trip-/Waypoint-Objekte und ruft den echten Produktivcode.

Pfadregel #1409: der Pruefling wird ueber den Paketpfad importiert, den
``tests/conftest.py`` relativ zu DIESER Datei aufsetzt — kein fester
Hauptrepo-Pfad.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

import pytest
from freezegun import freeze_time

from app.models import TripReportConfig
from app.trip import Stage, Trip, Waypoint
from services.trip_segments import convert_trip_to_segments
from utils.timezone import tz_for_coords

from tests.helpers.arrival_window_fixtures import (
    MINUTEN_PRO_TAG,
    active_window_offsets,
    fenster_minuten,
    stage_date,
)

# Die Versatz-Familien, die in den zwoelf umgestellten Dateien wirklich
# vorkommen, plus zwei Grenzfaelle (gleiche Versaetze, Abstand ueber einen
# ganzen Tag), die die Zusicherungen 2 und 3 ueberhaupt erst ansprechen.
FAMILIEN: list[tuple[int, ...]] = [
    (60, 240),          # test_alert_log_metrics, test_alert_urgency
    (120, 240),         # test_issue_827, test_issue_1070, test_alert_channel_threshold
    (-60, 120),         # test_issue_883, test_alert_quiet_hours_robustness, #995
    (-60, 180),         # test_bundle_791_847_844
    (-240, -120, 120),  # test_issue_822 AC-1
    (-120, -30, 90),    # test_issue_822 AC-3
]

# Nord/Sued und weit oestlich/westlich von Greenwich, plus die Zonen, die in
# den Fixturen wirklich benutzt werden.
ORTE: list[tuple[str, float, float]] = [
    ("Korsika UTC+2", 42.20, 9.10),
    ("Island UTC+0", 64.00, -22.00),
    ("London UTC+1", 51.50, 0.00),
    ("Neuseeland UTC+12", -41.29, 174.78),
    ("Denver UTC-6", 39.74, -104.99),
]

# Ein voller lokaler Tag plus die Raender: minuten_jetzt darf negativ sein (der
# lokale Etappentag hat noch nicht begonnen) und ueber 1439 liegen (er ist
# schon vorbei) — beides kommt bei realen Zeitzonen vor.
ALLE_MINUTEN = range(-MINUTEN_PRO_TAG, 2 * MINUTEN_PRO_TAG)


# ══════════ Schicht 1: die reine Rechnung, ueber den ganzen Tag ══════════

def test_erster_wegpunkt_liegt_immer_auf_dem_etappentag():
    """Zusicherung 1: ``0 <= ergebnis[0] <= 1439``.

    ``wp_days[0]`` ist in ``convert_trip_to_segments`` strukturell immer 0.
    Faellt der erste Wegpunkt aus dem Etappentag, wird er beim Zusammensetzen
    trotzdem auf diesen Tag gelegt — das Segment landet einen ganzen Tag
    daneben.
    """
    verletzt = [
        (m, versaetze, fenster_minuten(m, *versaetze)[0])
        for m in ALLE_MINUTEN
        for versaetze in FAMILIEN
        if not 0 <= fenster_minuten(m, *versaetze)[0] <= MINUTEN_PRO_TAG - 1
    ]
    assert not verletzt, (
        f"{len(verletzt)} Faelle legen den ersten Wegpunkt neben den "
        f"Etappentag, z.B. {verletzt[:3]}"
    )


def test_wegpunkte_sind_immer_streng_monoton():
    """Zusicherung 2: streng steigend.

    Zwei gleiche Zeiten lassen das Segment am ``end_dt <= start_dt``-Guard in
    ``convert_trip_to_segments`` kollabieren; es wird dann geloggt
    uebersprungen und die Etappe verliert stillschweigend ein Segment.
    """
    verletzt = []
    for m in ALLE_MINUTEN:
        for versaetze in FAMILIEN:
            werte = fenster_minuten(m, *versaetze)
            if any(werte[i] >= werte[i + 1] for i in range(len(werte) - 1)):
                verletzt.append((m, versaetze, werte))
    assert not verletzt, (
        f"{len(verletzt)} Faelle sind nicht streng monoton, z.B. {verletzt[:3]}"
    )


def test_abstand_bleibt_unter_einem_ganzen_tag():
    """Zusicherung 3: jeder Abstand hoechstens 1439 Minuten.

    Bei genau 1440 waere die Uhrzeit des Folgepunkts IDENTISCH mit der seines
    Vorgaengers. Die Rollover-Erkennung in ``convert_trip_to_segments`` greift
    nur bei STRIKT fallender Uhrzeit — der Tageswechsel wuerde verschluckt und
    das Segment kollabierte.
    """
    verletzt = []
    for m in ALLE_MINUTEN:
        for versaetze in FAMILIEN:
            werte = fenster_minuten(m, *versaetze)
            for i in range(len(werte) - 1):
                if werte[i + 1] - werte[i] > MINUTEN_PRO_TAG - 1:
                    verletzt.append((m, versaetze, werte[i], werte[i + 1]))
    assert not verletzt, (
        f"{len(verletzt)} Abstaende erreichen oder ueberschreiten einen ganzen "
        f"Tag, z.B. {verletzt[:3]}"
    )


@pytest.mark.parametrize("versaetze", [(60, 60), (120, 120, 120), (240, 0)])
def test_gleiche_oder_fallende_versaetze_bleiben_streng_monoton(versaetze):
    """Die Untergrenze ``vorher + 1`` ist die einzige Zusicherung, die diesen
    Fall traegt — bei streng steigenden Versaetzen greift sie nie.

    Genau deshalb blieb ihre Entfernung in der Adversary-Gegenprobe unbemerkt:
    alle zwoelf Aufrufstellen uebergeben steigende Versaetze. Der Helfer sagt
    aber „streng monoton" ohne Vorbehalt zu — hier wird diese Zusage geprueft,
    nicht die zufaellige Aufrufpraxis.
    """
    for m in (0, 1, 719, 1438, 1439, -1, 1440, 2000):
        werte = fenster_minuten(m, *versaetze)
        assert all(werte[i] < werte[i + 1] for i in range(len(werte) - 1)), (
            f"minuten_jetzt={m}, Versaetze={versaetze} -> {werte} ist nicht "
            "streng monoton; die Untergrenze vorher+1 fehlt oder greift nicht"
        )


@pytest.mark.parametrize("abstand", [MINUTEN_PRO_TAG, MINUTEN_PRO_TAG + 1, 5000])
def test_grosser_abstand_wird_unter_einen_tag_geklemmt(abstand):
    """Ein Versatz-Paar, das ueber einen ganzen Tag auseinanderliegt, MUSS auf
    hoechstens 1439 Minuten zusammengezogen werden.

    Das ist der Fall, den die obere Klemme allein traegt. Waere sie 1440,
    kaeme beim Abstand 1440 dieselbe Uhrzeit heraus — hier direkt geprueft:
    die Minuten modulo Tag muessen sich unterscheiden.
    """
    for m in (0, 300, 900, 1439):
        a, b = fenster_minuten(m, 0, abstand)
        assert b - a <= MINUTEN_PRO_TAG - 1, (
            f"minuten_jetzt={m}, Abstand={abstand} -> {a}/{b}: Abstand "
            f"{b - a} erreicht einen ganzen Tag"
        )
        assert a % MINUTEN_PRO_TAG != b % MINUTEN_PRO_TAG, (
            f"minuten_jetzt={m}, Abstand={abstand} -> {a}/{b}: beide Wegpunkte "
            "tragen dieselbe Uhrzeit; der Tageswechsel waere fuer "
            "convert_trip_to_segments unsichtbar"
        )


def test_versaetze_in_der_tagesmitte_bleiben_unveraendert():
    """Gegenprobe zur Klemmung: mitten am Tag darf der Helfer NICHTS tun.

    Ohne diesen Test koennte die Klemmung beliebig scharf werden (z.B. alles
    auf eine Minute stauchen) und die drei Tests oben blieben gruen.
    """
    mitte = 12 * 60
    for versaetze in FAMILIEN:
        assert fenster_minuten(mitte, *versaetze) == tuple(
            mitte + v for v in versaetze
        ), f"Versaetze {versaetze} wurden in der Tagesmitte veraendert"


def test_zu_wenige_wegpunkte_scheitern_laut():
    """Ein Segment braucht zwei Wegpunkte — ein einzelner ist ein Programm-
    fehler des Aufrufers und darf nicht still ein Ein-Punkt-Fenster liefern."""
    with pytest.raises(ValueError):
        fenster_minuten(600, 60)


# ══════════ Schicht 2: die Wirkung am echten Segmentbau ══════════

# Die Kippkanten aus AC-3 der Spec, plus die Mitternachtssekunden. Bis
# 2026-08-10 wurden genau diese Zeitpunkte NUR von Hand geprueft.
KIPPKANTEN = [
    "2026-08-10T12:00:00+00:00",
    "2026-08-10T21:59:59+00:00",
    "2026-08-10T22:00:00+00:00",
    "2026-08-10T22:59:59+00:00",
    "2026-08-10T23:00:00+00:00",
    "2026-08-10T23:30:00+00:00",
    "2026-08-10T23:59:59+00:00",
    "2026-08-11T00:00:01+00:00",
    "2026-08-11T02:00:00+00:00",
]


def _trip_aus_helfer(lat: float, lon: float, versaetze: tuple[int, ...]) -> Trip:
    """Echter Trip, dessen Ankunftszeiten aus dem Helfer stammen — genau so,
    wie es die zwoelf umgestellten Fixturen tun."""
    zeiten = active_window_offsets(lat, lon, *versaetze)
    waypoints = [
        Waypoint(id=f"WP{i}", name=f"WP{i}", lat=lat + i * 0.05,
                 lon=lon + i * 0.05, elevation_m=1000.0, arrival_calculated=z)
        for i, z in enumerate(zeiten)
    ]
    stage = Stage(id="S1", name="Tag 1", date=stage_date(lat, lon), waypoints=waypoints)
    trip = Trip(id="wanduhr-probe", name="Wanduhr-Probe", stages=[stage])
    trip.report_config = TripReportConfig(trip_id="wanduhr-probe", send_email=False)
    return trip


@pytest.mark.parametrize("zeitpunkt", KIPPKANTEN)
@pytest.mark.parametrize("ortsname,lat,lon", ORTE)
def test_segment_liegt_nie_vollstaendig_in_der_vergangenheit(
    zeitpunkt, ortsname, lat, lon
):
    """DIE Wirkung, um die es in #1667 S1 geht — am Wirkort geprueft.

    ``check_radar_alerts()`` bricht mit „alle Segmente vorbei" ab, sobald
    ``now_utc`` hinter dem Ende des letzten Segments liegt; genau das liess die
    Fixturen ab 22:00/23:00 UTC 0 statt 1 Alarm liefern. Geprueft wird hier
    nicht die Rechnung des Helfers, sondern das Ergebnis des ECHTEN
    ``convert_trip_to_segments`` — inklusive Rollover-Erkennung und
    Ziel-Segment.
    """
    with freeze_time(zeitpunkt):
        jetzt = datetime.now(timezone.utc)
        for versaetze in FAMILIEN:
            trip = _trip_aus_helfer(lat, lon, versaetze)
            segmente = convert_trip_to_segments(trip, stage_date(lat, lon))
            assert segmente, (
                f"{ortsname} @ {zeitpunkt}, Versaetze {versaetze}: leere "
                "Segmentliste — die Etappe wurde gar nicht gefunden oder alle "
                "Segmente sind am end_dt<=start_dt-Guard kollabiert"
            )
            letztes_ende = max(s.end_time for s in segmente)
            assert letztes_ende >= jetzt, (
                f"{ortsname} @ {zeitpunkt}, Versaetze {versaetze}: alle "
                f"Segmente vorbei (letztes Ende {letztes_ende.isoformat()} < "
                f"jetzt {jetzt.isoformat()}) — check_radar_alerts() liefert "
                "hier 0 statt 1, genau der Fund aus #1667 S1"
            )


@pytest.mark.parametrize("zeitpunkt", KIPPKANTEN)
def test_wegpunktzeiten_ergeben_echt_wachsende_segmentgrenzen(zeitpunkt):
    """Kein Segment darf still verschwinden.

    ``convert_trip_to_segments`` ueberspringt ein Segment mit
    ``end_dt <= start_dt`` und loggt nur eine Warnung. Ein solcher Verlust
    faellt in den Fixturen sonst nicht auf: der Test bekommt einfach ein
    Segment weniger und laeuft weiter.
    """
    with freeze_time(zeitpunkt):
        for ortsname, lat, lon in ORTE:
            for versaetze in FAMILIEN:
                trip = _trip_aus_helfer(lat, lon, versaetze)
                segmente = convert_trip_to_segments(trip, stage_date(lat, lon))
                # Wegpunkte minus 1 Verbindungssegmente, plus das Ziel-Segment.
                erwartet = len(versaetze)
                assert len(segmente) == erwartet, (
                    f"{ortsname} @ {zeitpunkt}, Versaetze {versaetze}: "
                    f"{len(segmente)} statt {erwartet} Segmenten — mindestens "
                    "eines ist am end_dt<=start_dt-Guard kollabiert"
                )
                for s in segmente:
                    assert s.end_time > s.start_time, (
                        f"{ortsname} @ {zeitpunkt}: Segment {s.segment_id} "
                        "endet nicht nach seinem Anfang"
                    )


# ══════════ AC-9 (#1697): stage_date() folgt der Ortszeit, nicht dem Serverdatum ══════════

# Atlantic/Reykjavik: UTC+0 ganzjaehrig — "UTC-neutrale" Koordinate, deren
# Ortsdatum in der Randzeit 22:00-00:00 UTC NIE vom Serverdatum abweicht.
ISLAND_STAGE_DATE_LAT, ISLAND_STAGE_DATE_LON = 64.1466, -21.9426
# Korsika (Europe/Paris, UTC+2 im Sommer) — weicht in genau diesem Fenster ab.
KORSIKA_STAGE_DATE_LAT, KORSIKA_STAGE_DATE_LON = 42.20, 9.10


def test_ac9_stage_date_folgt_der_ortszeit_in_der_randzeit():
    """#1697 AC-9 ("Zweiter Fund"): ``stage_date()`` ist heute NILADISCH und
    liefert wörtlich ``date.today()`` (Serverdatum) — unabhängig von jeder
    Koordinate. Nach der Umstellung auf ``stage_date(lat, lon)`` MUSS eine
    Korsika-Koordinate um 22:30 UTC den FOLGETAG liefern (Ortszeit 00:30),
    waehrend eine UTC-neutrale Koordinate beim Serverdatum bleibt — dieselbe
    Formel, die ``trip_alert.py`` nach #1697 fuer die Etappenauswahl benutzt.

    RED heute: ``stage_date()`` nimmt keine Argumente entgegen ->
    ``TypeError`` bei ``stage_date(lat, lon)``.
    """
    with freeze_time("2026-08-10T22:30:00+00:00"):
        serverdatum = date(2026, 8, 10)
        folgetag = date(2026, 8, 11)

        korsika_datum = stage_date(KORSIKA_STAGE_DATE_LAT, KORSIKA_STAGE_DATE_LON)
        island_datum = stage_date(ISLAND_STAGE_DATE_LAT, ISLAND_STAGE_DATE_LON)

    assert korsika_datum == folgetag, (
        f"AC-9: stage_date(Korsika) lieferte {korsika_datum}, erwartet "
        f"{folgetag} (00:30 Ortszeit des Folgetags um 22:30 UTC)"
    )
    assert island_datum == serverdatum, (
        f"AC-9: stage_date(Island) lieferte {island_datum}, erwartet "
        f"{serverdatum} (UTC-neutrale Koordinate — Ortsdatum == Serverdatum)"
    )
    assert korsika_datum != island_datum, (
        "AC-9: Korsika- und Island-Ortsdatum muessen in dieser Randzeit "
        "auseinanderlaufen, sonst ist der Test nicht diskriminierend"
    )


def test_freeze_time_stellt_die_uhr_wirklich():
    """Selbstbeleg: wenn ``freeze_time`` hier nicht wirkte, waeren alle
    Wirkungs-Tests oben stumm — sie liefen dann immer zur realen Wanduhrzeit
    und pruefen die Kippkanten nie.

    Genau diese Frage („prueft der Test, was er behauptet?") war der Kern des
    Adversary-Findings F001.
    """
    with freeze_time("2026-08-10T23:30:00+00:00"):
        assert datetime.now(timezone.utc) == datetime(
            2026, 8, 10, 23, 30, tzinfo=timezone.utc
        )
        assert date.today() == date(2026, 8, 10)
        tz = tz_for_coords(42.20, 9.10)
        tagesbeginn = datetime.combine(date(2026, 8, 10), time(0, 0)).replace(tzinfo=tz)
        # Korsika liegt im Sommer auf UTC+2: der Etappentag begann um 22:00 UTC
        # des Vortages, "jetzt" ist also Minute 1530 dieses lokalen Tages.
        assert (datetime.now(timezone.utc) - tagesbeginn) == timedelta(minutes=1530)
