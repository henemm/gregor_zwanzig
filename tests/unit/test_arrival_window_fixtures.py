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
    past_window_offsets,
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

# Seit #1940 verweigert ``fenster_minuten`` die Auskunft, wenn ein NEGATIV
# gewuenschter Versatz an der gegebenen Ortsminute nicht mehr vor *jetzt*
# darstellbar ist. Die drei Zusicherungs-Schleifen unten pruefen deshalb zwei
# Aeste — geliefertes Fenster und Verweigerung — und zaehlen BEIDE mit: ohne
# feste Erwartung koennte ein Ast still auf null Faelle zusammenfallen und die
# Schleife waere trivial gruen (sie pruefte dann nichts mehr).
#
# Die Zahlen sind nachgemessen, nicht hergeleitet: 1440 Verweigerungen sind
# stets die negativen Ortsminuten (der lokale Etappentag hat noch nicht
# begonnen, dort ist ueberhaupt keine Vergangenheit darstellbar), dazu kommt
# die Randzone am Tagesanfang.
GEWORFEN_JE_FAMILIE: dict[tuple[int, ...], int] = {
    (60, 240): 0,                    # ohne negativen Versatz -> nie
    (120, 240): 0,                   # dito
    (-60, 120): 1440,                # nur die negativen Ortsminuten
    (-60, 180): 1440,                # dito
    (-240, -120, 120): 1440 + 120,   # + Randzone Ortsminute 0-119
    (-120, -30, 90): 1440 + 90,      # + Randzone Ortsminute 0-89
}
GEWORFEN_GESAMT = sum(GEWORFEN_JE_FAMILIE[versaetze] for versaetze in FAMILIEN)
GEPRUEFT_GESAMT = len(ALLE_MINUTEN) * len(FAMILIEN) - GEWORFEN_GESAMT


def _durchlauf(pruefung) -> list:
    """Laeuft ``ALLE_MINUTEN x FAMILIEN`` ab und ruft ``pruefung`` fuer jedes
    tatsaechlich gelieferte Fenster; Verweigerungen werden getrennt gezaehlt.

    Die beiden Zaehler sind hier verankert und nicht in den Aufrufern, damit
    jede der drei Zusicherungen unten dieselbe Grundgesamtheit prueft.
    """
    verletzt: list = []
    geprueft = geworfen = 0
    for m in ALLE_MINUTEN:
        for versaetze in FAMILIEN:
            try:
                werte = fenster_minuten(m, *versaetze)
            except ValueError:
                geworfen += 1
                continue
            geprueft += 1
            verletzt += pruefung(m, versaetze, werte)

    assert geprueft == GEPRUEFT_GESAMT, (
        f"{geprueft} statt {GEPRUEFT_GESAMT} gelieferte Fenster geprueft — die "
        "Zusicherung wird an einer anderen Grundgesamtheit gemessen als "
        "gemessen wurde (zu weit greifende Verweigerung?)"
    )
    assert geworfen == GEWORFEN_GESAMT, (
        f"{geworfen} statt {GEWORFEN_GESAMT} Verweigerungen — der Bereich, in "
        "dem fenster_minuten die Auskunft verweigert, hat sich verschoben"
    )
    return verletzt


# ══════════ Schicht 1: die reine Rechnung, ueber den ganzen Tag ══════════

def test_verweigerung_trifft_genau_den_gemessenen_bereich():
    """#1940: der laute Fehler greift GENAU so weit wie gemessen — je Familie.

    Die Summenzaehler in ``_durchlauf`` wuerden es nicht merken, wenn eine
    Familie mehr und eine andere weniger verweigert. Hier steht die Verteilung
    selbst unter Aufsicht: sie ist die Grenze zwischen "schliesst die
    Fehlerklasse" und "macht die 13 abhaengigen Testdateien unbenutzbar".
    """
    gemessen = {}
    for versaetze in FAMILIEN:
        anzahl = 0
        for m in ALLE_MINUTEN:
            try:
                fenster_minuten(m, *versaetze)
            except ValueError:
                anzahl += 1
        gemessen[versaetze] = anzahl

    erwartet = {versaetze: GEWORFEN_JE_FAMILIE[versaetze] for versaetze in FAMILIEN}
    assert gemessen == erwartet, (
        f"Verweigerungs-Bereich verschoben:\n  gemessen  {gemessen}\n"
        f"  erwartet  {erwartet}"
    )


def test_erster_wegpunkt_liegt_immer_auf_dem_etappentag():
    """Zusicherung 1: ``0 <= ergebnis[0] <= 1439``.

    ``wp_days[0]`` ist in ``convert_trip_to_segments`` strukturell immer 0.
    Faellt der erste Wegpunkt aus dem Etappentag, wird er beim Zusammensetzen
    trotzdem auf diesen Tag gelegt — das Segment landet einen ganzen Tag
    daneben.
    """
    def pruefung(m, versaetze, werte):
        if not 0 <= werte[0] <= MINUTEN_PRO_TAG - 1:
            return [(m, versaetze, werte[0])]
        return []

    verletzt = _durchlauf(pruefung)
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
    def pruefung(m, versaetze, werte):
        if any(werte[i] >= werte[i + 1] for i in range(len(werte) - 1)):
            return [(m, versaetze, werte)]
        return []

    verletzt = _durchlauf(pruefung)
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
    def pruefung(m, versaetze, werte):
        return [
            (m, versaetze, werte[i], werte[i + 1])
            for i in range(len(werte) - 1)
            if werte[i + 1] - werte[i] > MINUTEN_PRO_TAG - 1
        ]

    verletzt = _durchlauf(pruefung)
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


# Seit #1940 verweigert der Helfer an der Ortszeit-Mitternacht die Auskunft
# (s. GEWORFEN_JE_FAMILIE). An den Kippkanten unten trifft das 20 der 270
# Kombinationen aus Kippkante x Ort x Familie — nachgemessen, nicht geschaetzt.
# Die Tabelle haelt genau diese Faelle fest: sie sind KEIN Segmentfehler,
# sondern die neue, erwartete Verweigerung. Wer sie nur mit einem stillen
# ``except ValueError: continue`` uebergeht, prueft an den interessantesten
# Zeitpunkten unbemerkt nichts mehr.
NICHT_DARSTELLBAR: dict[tuple[str, str], int] = {
    ("Island UTC+0", "2026-08-11T00:00:01+00:00"): 2,
    ("Korsika UTC+2", "2026-08-10T22:00:00+00:00"): 2,
    ("Korsika UTC+2", "2026-08-10T22:59:59+00:00"): 2,
    ("Korsika UTC+2", "2026-08-10T23:00:00+00:00"): 2,
    ("Korsika UTC+2", "2026-08-10T23:30:00+00:00"): 1,
    ("Korsika UTC+2", "2026-08-10T23:59:59+00:00"): 1,
    ("London UTC+1", "2026-08-10T23:00:00+00:00"): 2,
    ("London UTC+1", "2026-08-10T23:30:00+00:00"): 2,
    ("London UTC+1", "2026-08-10T23:59:59+00:00"): 2,
    ("London UTC+1", "2026-08-11T00:00:01+00:00"): 2,
    ("Neuseeland UTC+12", "2026-08-10T12:00:00+00:00"): 2,
}


def _trip_aus_helfer(
    lat: float,
    lon: float,
    versaetze: tuple[int, ...],
    helfer=active_window_offsets,
    tagesfenster: dict | None = None,
) -> Trip:
    """Echter Trip, dessen Ankunftszeiten aus dem Helfer stammen — genau so,
    wie es die umgestellten Fixturen tun.

    ``helfer`` waehlt zwischen aktivem und vergangenem Fenster; ``tagesfenster``
    reicht die Vorkehrung durch, die eine Vergangenheits-Fixture seit #1584
    braucht (s. ``past_window_offsets``-Docstring). Ein zweiter Bauer waere
    dieselbe Funktion mit einer anderen Zeile gewesen.
    """
    zeiten = helfer(lat, lon, *versaetze)
    waypoints = [
        Waypoint(id=f"WP{i}", name=f"WP{i}", lat=lat + i * 0.05,
                 lon=lon + i * 0.05, elevation_m=1000.0, arrival_calculated=z)
        for i, z in enumerate(zeiten)
    ]
    stage = Stage(id="S1", name="Tag 1", date=stage_date(lat, lon), waypoints=waypoints)
    trip = Trip(id="wanduhr-probe", name="Wanduhr-Probe", stages=[stage])
    trip.report_config = TripReportConfig(
        trip_id="wanduhr-probe", send_email=False, **(tagesfenster or {})
    )
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
        verweigert = 0
        for versaetze in FAMILIEN:
            try:
                trip = _trip_aus_helfer(lat, lon, versaetze)
            except ValueError:
                # #1940: an dieser Ortszeit ist die verlangte Vergangenheit
                # nicht darstellbar — erwartet, unten stueckgenau gezaehlt.
                verweigert += 1
                continue
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

    erwartet = NICHT_DARSTELLBAR.get((ortsname, zeitpunkt), 0)
    assert verweigert == erwartet, (
        f"{ortsname} @ {zeitpunkt}: {verweigert} statt {erwartet} Familien "
        f"verweigert — es wurden {len(FAMILIEN) - verweigert} von "
        f"{len(FAMILIEN) - erwartet} vorgesehenen Faellen wirklich am Segment "
        "geprueft"
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
        verweigert = 0
        for ortsname, lat, lon in ORTE:
            for versaetze in FAMILIEN:
                try:
                    trip = _trip_aus_helfer(lat, lon, versaetze)
                except ValueError:
                    verweigert += 1  # #1940, s. NICHT_DARSTELLBAR
                    continue
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

    erwartet = sum(
        NICHT_DARSTELLBAR.get((name, zeitpunkt), 0) for name, _, _ in ORTE
    )
    assert verweigert == erwartet, (
        f"@ {zeitpunkt}: {verweigert} statt {erwartet} Verweigerungen ueber "
        f"alle Orte — {len(ORTE) * len(FAMILIEN) - verweigert} von "
        f"{len(ORTE) * len(FAMILIEN) - erwartet} vorgesehenen Faellen wurden "
        "wirklich am Segmentbau geprueft"
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


# ══════════ #1940: das Vorzeichen eines Versatzes ist eine Zusicherung ══════════

# Je Offset-Familie der Bereich der Ortsminuten, in dem die
# Vorwaertsverschiebung (``verschiebung = max(0, -roh[0])``) einen NEGATIV
# gewuenschten Wegpunkt hinter *jetzt* legt. Nachgemessen ueber alle 1440
# Ortsminuten, nicht hergeleitet (docs/context/fix-1940-fixture-zeitkippkante.md).
KAPUTTE_BEREICHE: list[tuple[tuple[int, ...], range]] = [
    ((-120, -30, 90), range(0, 90)),     # 822 AC-3, Neuseeland -> 12:00-13:30 UTC
    ((-120, -60, 60), range(0, 60)),     # 822 AC-2, London     -> 23:00-00:00 UTC
    ((-240, -120, 120), range(0, 120)),  # 822 AC-1, Tirol      -> 22:00-00:00 UTC
]

# Die Familien der uebrigen 13 Testdateien: sie brauchen nur "ein Segment ist
# jetzt aktiv" und sind von der Verschiebung nachweislich nicht betroffen.
HARMLOSE_FAMILIEN: list[tuple[int, ...]] = [(-60, 120), (-60, 180), (-60, 60)]


@pytest.mark.parametrize(
    "versaetze,minute",
    [
        (versaetze, minute)
        for versaetze, bereich in KAPUTTE_BEREICHE
        for minute in (
            bereich.start,
            (bereich.start + bereich.stop) // 2,
            bereich.stop - 1,
        )
    ],
)
def test_nicht_darstellbarer_vergangenheits_wegpunkt_scheitert_laut(versaetze, minute):
    """AC-1 (#1940): ein bewusst in die VERGANGENHEIT gelegter Wegpunkt darf
    nicht still in der Zukunft landen.

    Nahe der Ortszeit-Mitternacht schiebt ``fenster_minuten`` das ganze Fenster
    nach vorne. Die Abstaende bleiben dabei erhalten — das Vorzeichen eines
    Versatzes nicht. Ein Aufrufer, der "zwei Stunden vor jetzt" verlangt hat,
    bekommt ein Fenster, dessen erstes Segment noch AKTIV ist, und prueft danach
    eine Konstellation, die er gar nicht hergestellt hat (Issue #1940: CI-Job
    ``test`` taeglich 12:00-13:30 UTC rot, ohne Bezug zum PR-Inhalt).

    Der Helfer muss das sagen, statt es zu verschweigen — genau so, wie
    ``past_window_offsets`` es bereits tut (``ValueError``, wenn der Platz auf
    dem Etappentag nicht reicht). Die Fehlermeldung muss die verletzte
    Zusicherung benennen; ``match`` prueft deshalb den Begriff, nicht eine
    zufaellige Formulierung.

    RED heute: ``fenster_minuten`` liefert klaglos ein Fenster.
    """
    with pytest.raises(ValueError, match=r"(?i)vergangenheit"):
        werte = fenster_minuten(minute, *versaetze)
        verletzt = [(v, w) for v, w in zip(versaetze, werte) if v < 0 and w > minute]
        raise AssertionError(
            f"fenster_minuten({minute}, *{versaetze}) lieferte still {werte}; "
            f"diese negativ gewuenschten Versaetze liegen NACH jetzt={minute}: "
            f"{verletzt}"
        )


@pytest.mark.parametrize("versaetze,kaputt", KAPUTTE_BEREICHE)
def test_negative_versaetze_liegen_ausserhalb_der_randzone_in_der_vergangenheit(
    versaetze, kaputt
):
    """AC-2 (#1940), Positivkontrolle — HEUTE SCHON GRUEN, mit Absicht.

    Dieser Test beweist NICHT den Fix; er sichert das Bestandsverhalten ab, das
    der Fix nicht antasten darf: ausserhalb der Randzone liefert der Helfer
    tatsaechlich ein Fenster, in dem jeder negativ gewuenschte Wegpunkt bei oder
    vor *jetzt* liegt. Ohne ihn koennte der neue laute Fehler aus AC-1 beliebig
    weit greifen (im Grenzfall: immer werfen) und AC-1 bliebe gruen, waehrend
    die 14 abhaengigen Testdateien reihenweise ausfielen — AC-1 bewachte dann
    die leere Menge.

    Geprueft wird ueber alle 1440 Ortsminuten eines Tages, nicht an einem
    Stichzeitpunkt; die Zahl der tatsaechlich geprueften Minuten wird
    mitgezaehlt, damit ein zu grosszuegiger Ausschluss auffaellt.
    """
    geprueft = 0
    verletzt: list[tuple[int, int, int]] = []
    for m in range(MINUTEN_PRO_TAG):
        if m in kaputt:
            continue
        geprueft += 1
        werte = fenster_minuten(m, *versaetze)
        verletzt += [(m, v, w) for v, w in zip(versaetze, werte) if v < 0 and w > m]

    assert geprueft == MINUTEN_PRO_TAG - len(kaputt), (
        f"nur {geprueft} von {MINUTEN_PRO_TAG - len(kaputt)} erwarteten "
        f"Ortsminuten geprueft — der Ausschluss {kaputt} passt nicht zur "
        "gemessenen Randzone"
    )
    assert not verletzt, (
        f"{len(verletzt)} Faelle ausserhalb der Randzone legen einen negativ "
        f"gewuenschten Wegpunkt hinter jetzt, z.B. {verletzt[:3]} "
        "(Format: minuten_jetzt, Versatz, Wegpunkt)"
    )


@pytest.mark.parametrize("versaetze", HARMLOSE_FAMILIEN)
def test_harmlose_familien_loesen_den_lauten_fehler_nie_aus(versaetze):
    """AC-5 (#1940): keine Kollateralschaeden.

    Die uebrigen 13 Testdateien verlangen nur "ein Segment ist jetzt aktiv" und
    duerfen vom neuen lauten Fehler an keiner einzigen Ortsminute getroffen
    werden — auch nicht ueber die Fan-out-Helfer (``_trip()`` in
    ``test_briefing_anchor_survives_dispatch_failure.py``: 37 Aufrufe aus 25
    Testfunktionen). Heute gruen, weil es den Fehler noch nicht gibt; nach dem
    Fix traegt der Test die Zusicherung, dass er eng gefasst blieb.
    """
    ausloesungen: list[tuple[int, str]] = []
    for m in range(MINUTEN_PRO_TAG):
        try:
            fenster_minuten(m, *versaetze)
        except ValueError as fehler:
            ausloesungen.append((m, str(fehler)))

    assert not ausloesungen, (
        f"Versaetze {versaetze} loesen an {len(ausloesungen)} von "
        f"{MINUTEN_PRO_TAG} Ortsminuten einen Fehler aus, z.B. "
        f"{ausloesungen[:3]} — der neue Waechter greift zu weit"
    )


# ══════════ #1940 AC-7: past_window_offsets staucht nicht mehr still ══════════

# Beide Aufrufstellen des Vergangenheits-Helfers benutzen dieselbe Familie.
AC7_VERSAETZE = (-240, -120)
# Pacific/Auckland, UTC+12 im August: Ortszeit-Mitternacht liegt bei 12:00 UTC.
AC7_LAT, AC7_LON = -41.29, 174.78
AC7_MITTERNACHT_UTC = datetime(2026, 8, 18, 12, 0, tzinfo=timezone.utc)

# Ortsminuten des Sweeps: dicht um die gemessene Kante bei 240, grob ueber den
# Rest des Tages. Der volle 1440-Minuten-Sweep wurde einmal gefahren (Kante
# scharf bei 240, Spanne durchgehend 120, jeder Wegpunkt vor jetzt) und dauert
# 4,5 s — jede Ortsminute braucht einen eigenen ``freeze_time``-Kontext, weil
# ``past_window_offsets`` seine Uhr selbst liest. Diese Auswahl kostet 0,2 s
# und traegt dieselbe Aussage.
AC7_PUNKTE = [*range(230, 250), 0, 60, 120, 180, 300, 600, 900, 1200, 1439]
AC7_VERWEIGERT_ERWARTET = 14   # 230-239 plus 0, 60, 120, 180
AC7_GELIEFERT_ERWARTET = 15    # 240-249 plus 300, 600, 900, 1200, 1439
AC7_SPANNE = 120               # -240 -> -120


def _minute_aus_hhmm(hhmm: str) -> int:
    return int(hhmm[:2]) * MINUTEN_PRO_TAG // 24 + int(hhmm[3:])


def _ac7_sweep() -> tuple[list, list]:
    """Ruft ``past_window_offsets`` an jeder Ortsminute aus ``AC7_PUNKTE`` und
    trennt Verweigerungen von gelieferten Fenstern."""
    verweigert: list = []
    geliefert: list = []
    for m in AC7_PUNKTE:
        with freeze_time(AC7_MITTERNACHT_UTC + timedelta(minutes=m)):
            try:
                erster, letzter = past_window_offsets(
                    AC7_LAT, AC7_LON, *AC7_VERSAETZE
                )
            except ValueError as fehler:
                verweigert.append((m, str(fehler)))
                continue
        geliefert.append((m, _minute_aus_hhmm(erster), _minute_aus_hhmm(letzter)))
    return verweigert, geliefert


def test_past_window_verweigert_wenn_der_ortstag_zu_frueh_ist():
    """AC-7: der Vergangenheits-Helfer staucht nicht mehr still.

    Bis 2026-08-17 wurde ein Fenster, das nicht mehr auf den vergangenen Teil
    des Etappentags passte, gleichmaessig auf ``[0, obergrenze]`` gestaucht.
    Der letzte Wegpunkt landete dann eine Minute vor *jetzt* — und das
    Ziel-Segment blieb nach dem Randfall-Guard noch eine Stunde offen. Der
    Trip war damit gerade NICHT "vorbei", also das Gegenteil dessen, wofuer
    diese Funktion existiert. Sichtbar wurde das als taeglicher CI-Ausfall
    12:00-16:00 UTC in
    ``test_issue_818_radar_briefing_integration.py::test_ac5_...``.
    """
    verweigert, geliefert = _ac7_sweep()

    assert len(verweigert) == AC7_VERWEIGERT_ERWARTET, (
        f"{len(verweigert)} statt {AC7_VERWEIGERT_ERWARTET} Verweigerungen an "
        f"den Ortsminuten {AC7_PUNKTE} — die Kante hat sich verschoben "
        f"(verweigert wurde bei {[m for m, _ in verweigert]})"
    )
    assert len(geliefert) == AC7_GELIEFERT_ERWARTET, (
        f"{len(geliefert)} statt {AC7_GELIEFERT_ERWARTET} gelieferte Fenster — "
        "ohne diesen Gegenzaehler waere der Test auch dann gruen, wenn die "
        "Funktion ueberhaupt nichts mehr liefert"
    )
    ohne_hinweis = [
        (m, meldung) for m, meldung in verweigert
        if "vergangenes Fenster" not in meldung
    ]
    assert not ohne_hinweis, (
        f"{len(ohne_hinweis)} Meldungen benennen die verletzte Zusicherung "
        f"nicht, z.B. {ohne_hinweis[:1]}"
    )


def test_past_window_haelt_die_spanne_ausserhalb_der_randzone():
    """AC-7, Positivkontrolle: die Verweigerung ersetzt die Stauchung, sie
    ersetzt nicht die Funktion.

    Ohne diesen Test waere ein Waechter, der IMMER wirft, oben trivial gruen —
    und die beiden Aufrufstellen haetten gar kein Fenster mehr. Geprueft wird
    deshalb nicht nur, DASS ein Fenster kommt, sondern dass es die verlangte
    Spanne traegt und vollstaendig vor *jetzt* liegt.
    """
    _, geliefert = _ac7_sweep()

    assert len(geliefert) == AC7_GELIEFERT_ERWARTET, (
        f"nur {len(geliefert)} von {AC7_GELIEFERT_ERWARTET} Ortsminuten "
        "lieferten ueberhaupt ein Fenster"
    )
    gestaucht = [
        (m, erster, letzter) for m, erster, letzter in geliefert
        if letzter - erster != AC7_SPANNE
    ]
    assert not gestaucht, (
        f"{len(gestaucht)} Fenster tragen nicht die verlangten {AC7_SPANNE} "
        f"Minuten Spanne, z.B. {gestaucht[:3]} (Format: Ortsminute, erster, "
        "letzter Wegpunkt) — genau die stille Stauchung, die AC-7 abschafft"
    )
    nicht_vorbei = [
        (m, letzter) for m, _, letzter in geliefert if letzter >= m
    ]
    assert not nicht_vorbei, (
        f"{len(nicht_vorbei)} Fenster enden nicht vor jetzt, z.B. "
        f"{nicht_vorbei[:3]} — der Trip waere dort nicht 'vorbei'"
    )


def test_vergangenes_fenster_ist_am_echten_segmentbau_wirklich_vorbei():
    """AC-7 am WIRKORT — die Luecke aus Adversary-Finding F001.

    Die beiden Tests oben pruefen die Rechnung des Helfers isoliert. Das reicht
    hier nicht: beide echten Aufrufstellen stellen seit AC-7 ihre Uhr und
    erreichen die Randzone nie mehr — eine Rueckabwicklung des Prueflings
    (Stauchung statt Verweigerung) bliebe an ihnen unsichtbar. Ein Waechter,
    der die Klasse, der er angehoert, nicht sieht, ist genau der Fund, wegen
    dem es #1940 gibt.

    Geprueft wird deshalb die ZUSICHERUNG der Funktion am echten
    ``convert_trip_to_segments``: dass das letzte Segment tatsaechlich
    abgelaufen ist. Dieselbe Vorkehrung wie an der echten Aufrufstelle
    (Tagesfenster 0-1 Uhr) — ohne sie haelt das Ziel-Segment seit #1584 bis
    19:00 Ortszeit offen und der Test pruefte etwas anderes, als er behauptet.
    """
    fenster = {"day_window_start_hour": 0, "day_window_end_hour": 1}
    vorbei = verweigert = 0
    for m in (0, 120, 239, 240, 300, 720, 1439):
        with freeze_time(AC7_MITTERNACHT_UTC + timedelta(minutes=m)):
            try:
                trip = _trip_aus_helfer(
                    AC7_LAT, AC7_LON, AC7_VERSAETZE,
                    helfer=past_window_offsets, tagesfenster=fenster,
                )
            except ValueError:
                verweigert += 1
                continue
            segmente = convert_trip_to_segments(trip, stage_date(AC7_LAT, AC7_LON))
            assert segmente, f"Ortsminute {m}: leere Segmentliste"
            letztes_ende = max(s.end_time for s in segmente)
            assert letztes_ende < datetime.now(timezone.utc), (
                f"Ortsminute {m}: das letzte Segment endet erst "
                f"{letztes_ende.isoformat()} und ist damit NICHT vorbei — "
                "genau der Zustand, den eine stille Stauchung erzeugt "
                "(letzter Wegpunkt eine Minute vor jetzt, Ziel-Segment noch "
                "eine Stunde offen)"
            )
            vorbei += 1

    assert (verweigert, vorbei) == (3, 4), (
        f"{verweigert} Verweigerungen / {vorbei} vorbeigelaufene Trips statt "
        "3 / 4 — die Kante bei Ortsminute 240 hat sich verschoben, oder der "
        "Test prueft gar nichts mehr"
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
