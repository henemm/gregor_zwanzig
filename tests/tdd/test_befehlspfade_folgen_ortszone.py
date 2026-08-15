"""TDD RED — #1727 S5a: die Befehlspfade folgen dem ORTSTAG der Tour.

SPEC: docs/specs/modules/fix_1727_s5a_befehlspfade_ortstag.md (AC-1 bis AC-9)

Vier Fundstellen bestimmen "welcher Kalendertag ist gemeint" heute ueber die
Serveruhr bzw. den UTC-Tag der Nachricht statt ueber den Ortstag der Tour
(ADR-0044): ``_show_status``, ``_show_now``, ``command_date`` fuer
``### ruhetag`` und die vorgelagerte Tourauswahl ``_find_active_trip``.

RED-Gruende (gemessen, nicht vermutet):
* ``_show_status``/``_show_now`` rechnen mit ``date.today()`` — unter
  ``freeze_time`` ist das der UTC-Tag des eingefrorenen Zeitpunkts (nachgemessen,
  freezegun ignoriert die Prozess-Zone). Die Zusicherungen scheitern fachlich.
* ``_find_active_trip`` traegt die Signatur ``(user_id="default")``; der
  Pflichtparameter ``now_utc`` existiert noch nicht -> ``TypeError``.

Testpolitik (CLAUDE.md "Test-Politik: Zwei Schichten"): Kern-Schicht, kein Netz.
Echte ``Trip``/``Stage``/``Waypoint``-Objekte, echter Loader (die autouse-Fixtur
``_isolate_data_root`` haelt ``data/`` isoliert), echter
``TripCommandProcessor``. Der Radar-Nowcast laeuft ueber eine echte
``RadarNowcastService``-Subklasse (DI-Seam, Muster
``test_952_onset_alert_fidelity.py``) — sie zeichnet auf, WELCHE Koordinaten
der Pruefling waehlt, statt eine Annahme zurueckzuspiegeln.

Pfadregel #1409: diese Datei liest nichts von der Platte.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from freezegun import freeze_time

from app.loader import get_data_dir, load_all_trips, save_trip
from app.trip import Stage, Trip, Waypoint
from services.inbound_telegram_reader import InboundTelegramReader
from services.radar_service import NowcastResult, RadarNowcastService
from services.trip_command_processor import (
    CommandResult,
    InboundMessage,
    TripCommandProcessor,
)
from tests.tdd.conftest import WP_KORSIKA, WP_NZ, _anker, trip_two_zones

# Zonen, deren Ortstag sich zum selben Augenblick unterscheidet.
KORSIKA_ZONE = "Europe/Paris"          # im August UTC+2
WELLINGTON_ZONE = "Pacific/Auckland"   # im August UTC+12
LA = (34.05, -118.24)                  # America/Los_Angeles, im August UTC-7
LA_ZONE = "America/Los_Angeles"
# Die beiden Enden der bewohnten Zonenskala -- 25 Stunden auseinander. Nur mit
# ihnen tragen zwei Touren zum selben Augenblick DREI verschiedene Kalendertage
# (D19 / Weltzeit D20 / D21); mit zwei benachbarten Zonen ist der
# Zukunfts-Rueckfall nicht falsifizierbar (Begruendung am Test).
PAGO = (-14.28, -170.70)               # Pacific/Pago_Pago,  UTC-11
PAGO_ZONE = "Pacific/Pago_Pago"
KIRITIMATI = (1.87, -157.40)           # Pacific/Kiritimati, UTC+14
KIRITIMATI_ZONE = "Pacific/Kiritimati"

D19, D20, D21, D22, D23 = (date(2026, 8, d) for d in (19, 20, 21, 22, 23))

# 22:30 UTC am 20.08. = 00:30 Ortszeit am 21.08. auf Korsika: nach der ORTS-,
# vor der Weltzeit-Mitternacht. Das Mismatch-Fenster.
NACHTS_UTC = datetime(2026, 8, 20, 22, 30, tzinfo=timezone.utc)
# 14:00 UTC am 20.08. = 02:00 Ortszeit am 21.08. in Wellington (UTC+12),
# gleichzeitig 16:00 Ortszeit am 20.08. auf Korsika. Zwei Touren, zwei Ortstage.
MITTAGS_UTC = datetime(2026, 8, 20, 14, 0, tzinfo=timezone.utc)
# 10:30 UTC am 20.08.: 23:30 am 19.08. in Pago Pago, 00:30 am 21.08. auf
# Kiritimati, dazwischen der Weltzeit-Tag 20.08. Das einzige Zeitfenster, in dem
# zwei bewohnte Orte DREI Kalendertage aufspannen (taeglich ~1 h breit).
DREI_TAGE_UTC = datetime(2026, 8, 20, 10, 30, tzinfo=timezone.utc)


def _wp(idx: int, coords: tuple[float, float]) -> Waypoint:
    return Waypoint(id=f"W{idx}", name=f"WP{idx}", lat=coords[0], lon=coords[1],
                    elevation_m=500)


def _trip(trip_id: str, tage: list[date], coords: tuple[float, float]) -> Trip:
    return Trip(
        id=trip_id, name=trip_id,
        stages=[
            Stage(id=f"S{i}", name=f"Etappe {tag:%d.%m.}", date=tag,
                  waypoints=[_wp(i, coords)])
            for i, tag in enumerate(tage)
        ],
    )


def _befehl(trip: Trip, body: str, now_utc: datetime,
            user_id: str = "default") -> CommandResult:
    """Befehl ueber den ECHTEN Eintrittspunkt ``process()`` schicken."""
    return TripCommandProcessor().process(InboundMessage(
        channel="telegram", trip_name=trip.name, body=body, sender="4711",
        received_at=now_utc, user_id=user_id,
    ))


# ``_anker`` ist ab #1795 nach ``tests/tdd/conftest.py`` gehoben (geteilter
# Ort statt einer zweiten Kopie, s. dortiger Docstring) — hier nur noch
# importiert (s. Import-Block oben).


# ══════════════════════ AC-1/AC-2: /status filtert nach Ortstag ══════════════════════


def _rolle(tag: date, ortstag: date) -> str:
    """Benennt die Etappe aus Sicht des Ortstages — damit die Fehlermeldung
    sagt, WELCHE Etappe fehlt/zuviel ist, nicht nur welches Datum."""
    if tag == ortstag:
        return "die HEUTIGE Etappe"
    if tag == ortstag - timedelta(days=1):
        return "die lokal gerade abgeschlossene Etappe"
    return "die vergangene Etappe" if tag < ortstag else "eine kuenftige Etappe"


@pytest.mark.parametrize("now_utc, zone, coords, ortstag, etappen, sichtbar, fehlerbild", [
    pytest.param(
        datetime(2026, 8, 21, 3, 0, tzinfo=timezone.utc), LA_ZONE, LA,
        D20, [D19, D20, D21], [D20, D21],
        "der Weltzeit-Tag ist der Ortszeit VORAUS — vor dem Fix fiel die "
        "heutige Etappe durch den Filter (bis zu 7 h/Tag unsichtbar)",
        id="westkueste-utc-minus-7",
    ),
    pytest.param(
        MITTAGS_UTC, WELLINGTON_ZONE, WP_NZ,
        D21, [D19, D20, D21, D22], [D21, D22],
        "der Servertag hinkt der Ortszeit HINTERHER — vor dem Fix blieb die "
        "lokal abgeschlossene Etappe stehen (bis zu 12 h/Tag sichtbar)",
        id="neuseeland-utc-plus-12",
    ),
])
def test_ac1_ac2_status_filtert_gegen_den_ortstag(
    now_utc, zone, coords, ortstag, etappen, sichtbar, fehlerbild,
):
    """AC-1 (negativer Offset) und AC-2 (positiver Offset) — Spiegelfaelle
    DERSELBEN Regel, deshalb ein parametrisierter Test.

    GIVEN eine Tour in einer Zone, deren Ortstag zum Abfragezeitpunkt sowohl vom
          Weltzeit- als auch vom Servertag abweicht — einmal nach hinten
          (US-Westkueste, im August PDT/UTC-7, Abfrage 03:00 UTC), einmal nach
          vorne (Neuseeland, NZST/UTC+12, Abfrage 14:00 UTC),
    WHEN  ``/status`` abgefragt wird,
    THEN  enthaelt die Liste GENAU die Etappen ab dem Ortstag: die heutige
          bleibt sichtbar (AC-1; vor dem Fix fiel sie durch ``stage.date >=
          today``, weil ``today`` schon den UTC-Folgetag trug) und die lokal
          abgeschlossene verschwindet (AC-2; vor dem Fix stufte der Servertag
          sie noch als "heute oder spaeter" ein).

    Beide Faelle pruefen beide Richtungen — was fehlen MUSS und was stehen muss.
    ``unsichtbar`` ist bewusst das Komplement der literal aufgeschriebenen
    Erwartung, nicht ein zweites Mal die Filterregel des Prueflings: so faellt
    auch eine Etappe auf, die gar nicht erwartet war.
    """
    unsichtbar = [tag for tag in etappen if tag not in sichtbar]

    with freeze_time(now_utc):
        _anker(now_utc, zone, ortstag)
        # Tourname traegt die Zone: der ausgegebene Body identifiziert im
        # Fehlerfall selbst, welcher der beiden Faelle gebrochen ist.
        trip = _trip(f"status-{zone.split('/')[-1].lower()}", etappen, coords)
        save_trip(trip)
        servertag = date.today()

        body = _befehl(trip, "### status", now_utc).confirmation_body

    lage = (
        f"  Zone {zone}, Ortstag {ortstag:%d.%m.%Y}, Weltzeit-Tag "
        f"{now_utc.date():%d.%m.%Y}, Servertag {servertag:%d.%m.%Y}\n"
        f"  Fehlerbild: {fehlerbild}\n{body}"
    )
    for tag in sichtbar:
        assert f"{tag:%d.%m.%Y}" in body, (
            f"/status: {_rolle(tag, ortstag)} vom {tag:%d.%m.%Y} FEHLT in der "
            f"Liste, obwohl sie am Ortstag oder spaeter liegt.\n{lage}"
        )
    for tag in unsichtbar:
        assert f"{tag:%d.%m.%Y}" not in body, (
            f"/status: {_rolle(tag, ortstag)} vom {tag:%d.%m.%Y} STEHT noch in "
            f"der Liste, obwohl sie vor dem Ortstag liegt.\n{lage}"
        )


# ══════════════════════ AC-3: /jetzt waehlt den Wegpunkt des Ortstages ══════════════════════


def test_ac3_jetzt_nimmt_den_wegpunkt_der_ortstag_etappe(monkeypatch):
    """AC-3.

    GIVEN die Zwei-Zonen-Tour (Etappe 20.08. Wellington, ab 21.08. Korsika),
    WHEN  ``/jetzt`` um 22:30 UTC am 20.08. = 00:30 Ortszeit am 21.08. laeuft,
    THEN  holt der Nowcast die Koordinaten des Wegpunkts der ORTSTAG-Etappe
          (Korsika), nicht die der Servertag-Etappe (Wellington). #1402 hatte
          hier nur die Uhrzeit des Onset-Texts ortsrichtig gemacht.

    Geprueft werden die KOORDINATEN, nicht die Uhrzeit — die Tageswahl sitzt vor
    der Zonenwahl.
    """
    aufrufe: list[tuple[float, float]] = []

    class _AufzeichnenderNowcast(RadarNowcastService):
        """Echte Subklasse (DI-Seam) — merkt sich die Koordinaten, mit denen der
        Pruefling sie ruft. Kein Mock: die Zusicherung prueft die Entscheidung
        des Produktivcodes, nicht die eigene Annahme."""

        def get_nowcast(self, lat, lon, priority="user_briefing"):
            aufrufe.append((lat, lon))
            return NowcastResult(onset_minutes=None,
                                 intensity_label="Kein Niederschlag",
                                 source="radar")

    monkeypatch.setattr("services.radar_service.RadarNowcastService",
                        _AufzeichnenderNowcast)

    with freeze_time(NACHTS_UTC):
        _anker(NACHTS_UTC, KORSIKA_ZONE, D21)
        trip = trip_two_zones(D20, trip_id="zwei-zonen-jetzt")
        assert trip.get_stage_for_date(D20).waypoints[0].lat != \
            trip.get_stage_for_date(D21).waypoints[0].lat, (
            "Testaufbau nicht diskriminierend: Servertag- und Ortstag-Etappe "
            "muessen verschiedene Wegpunkte tragen"
        )
        save_trip(trip)

        ergebnis = _befehl(trip, "### now", NACHTS_UTC)

    erwartet = (pytest.approx(WP_KORSIKA[0]), pytest.approx(WP_KORSIKA[1]))
    assert len(aufrufe) == 1, (
        f"AC-3: erwartet genau EIN get_nowcast(), gesehen {len(aufrufe)} "
        f"({aufrufe}) — Antwort: {ergebnis.confirmation_body!r}"
    )
    assert aufrufe[0] == erwartet, (
        f"AC-3: der Nowcast lief auf {aufrufe[0]} statt auf dem Wegpunkt der "
        f"Ortstag-Etappe (21.08., Korsika {WP_KORSIKA}) — das sind die "
        f"Koordinaten der Servertag-Etappe (20.08., Wellington {WP_NZ})"
    )


# ══════════════════════ AC-4/AC-5/AC-6: ### ruhetag ══════════════════════


@pytest.mark.parametrize("now_utc, im_mismatch_fenster", [
    pytest.param(NACHTS_UTC, True, id="00-30-ortszeit"),
    pytest.param(datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc), False,
                 id="14-00-ortszeit"),
])
def test_ac4_ruhetag_verschiebt_im_ganzen_ortstag_dieselben_etappen(
    now_utc, im_mismatch_fenster,
):
    """AC-4.

    GIVEN eine Korsika-Tour mit Etappen 21./22./23.08., Ortstag D = 21.08.,
    WHEN  ``### ruhetag`` einmal um 00:30 und einmal um 14:00 Ortszeit
          DESSELBEN Ortstages gesendet wird,
    THEN  bleibt die Etappe von D in BEIDEN Faellen liegen und es wandern beide
          Male genau 22. und 23.08. Vor dem Fix wanderte D um 00:30 Ortszeit
          mit, weil ``command_date`` noch den Vortag trug.

    Der 14:00-Lauf ist der Kontrolllauf: dort fallen Orts- und Weltzeit-Tag
    zusammen, er belegt die GLEICHHEIT innerhalb des Ortstages.
    """
    with freeze_time(now_utc):
        if im_mismatch_fenster:
            _anker(now_utc, KORSIKA_ZONE, D21)
        else:
            assert now_utc.astimezone(ZoneInfo(KORSIKA_ZONE)).date() == D21 \
                == now_utc.date(), "Kontrolllauf: Orts- und Weltzeit-Tag gleich"
        trip = _trip("ruhetag-gleichheit", [D21, D22, D23], WP_KORSIKA)
        save_trip(trip)

        ergebnis = _befehl(trip, "### ruhetag", now_utc)

    verschoben = {s.old_date for s in (ergebnis.shifts or [])}
    assert ergebnis.success is True, (
        f"AC-4: ruhetag scheiterte — {ergebnis.confirmation_body!r}"
    )
    assert verschoben == {D22, D23}, (
        f"AC-4: verschoben wurden {sorted(verschoben)}, erwartet nur "
        f"{[D22, D23]} — die Etappe des Ortstages ({D21}) muss liegen bleiben"
    )


def test_ac5_ruhetag_ohne_zukuenftige_etappe_meldet_nichts_zu_verschieben():
    """AC-5.

    GIVEN eine Korsika-Tour mit NUR der heutigen Etappe (Ortstag 21.08.),
    WHEN  ``### ruhetag`` um 00:30 Ortszeit im Mismatch-Fenster kommt,
    THEN  meldet die Antwort "Keine zukuenftigen Etappen zum Verschieben"
          (success=False) und die Etappe bleibt auf dem 21.08. Vor dem Fix galt
          sie als verschiebbar und wanderte auf den 22.08.
    """
    with freeze_time(NACHTS_UTC):
        _anker(NACHTS_UTC, KORSIKA_ZONE, D21)
        trip = _trip("ein-etappen-tour", [D21], WP_KORSIKA)
        save_trip(trip)

        ergebnis = _befehl(trip, "### ruhetag", NACHTS_UTC)
        danach = load_all_trips()[0]

    assert ergebnis.success is False, (
        "AC-5: die heutige Etappe wurde als zukuenftig behandelt — "
        f"{ergebnis.confirmation_body!r}"
    )
    assert "Keine zukuenftigen Etappen zum Verschieben" in ergebnis.confirmation_body, (
        f"AC-5: unerwarteter Text — {ergebnis.confirmation_body!r}"
    )
    assert danach.stages[0].date == D21, (
        f"AC-5: die Etappe wurde auf {danach.stages[0].date} verschoben, "
        f"erwartet unveraendert {D21}"
    )


def test_ac6_command_log_traegt_den_ortstag_und_sperrt_die_zweitausfuehrung():
    """AC-6.

    GIVEN eine Korsika-Tour (Etappen 21./22.08.),
    WHEN  ``### ruhetag`` zweimal im SELBEN Ortstag kommt, aber an verschiedenen
          Weltzeit-Tagen (22:30 UTC am 20.08. = 00:30 Ortszeit, dann 06:00 UTC
          am 21.08. = 08:00 Ortszeit),
    THEN  traegt ``command_log.json`` den Ortstag 2026-08-21 und der zweite
          Versuch wird als Duplikat abgewiesen. Vor dem Fix trugen die beiden
          Eintraege verschiedene UTC-Tage — der Ruhetag wurde ZWEIMAL angewendet.
    """
    zweiter = datetime(2026, 8, 21, 6, 0, tzinfo=timezone.utc)
    assert zweiter.date() != NACHTS_UTC.date(), (
        "Testaufbau: die beiden Versuche muessen auf verschiedenen Weltzeit-"
        "Tagen liegen, sonst faellt der UTC-Tag nicht auf"
    )
    assert zweiter.astimezone(ZoneInfo(KORSIKA_ZONE)).date() == D21, (
        "Testaufbau: beide Versuche muessen im selben Ortstag liegen"
    )

    with freeze_time(NACHTS_UTC):
        _anker(NACHTS_UTC, KORSIKA_ZONE, D21)
        trip = _trip("ruhetag-log", [D21, D22], WP_KORSIKA)
        save_trip(trip)
        erster_lauf = _befehl(trip, "### ruhetag", NACHTS_UTC)
    with freeze_time(zweiter):
        zweiter_lauf = _befehl(trip, "### ruhetag", zweiter)
        danach = load_all_trips()[0]

    eintraege = json.loads((get_data_dir() / "command_log.json").read_text())
    assert erster_lauf.success is True, erster_lauf.confirmation_body
    assert [e["date"] for e in eintraege] == ["2026-08-21"], (
        f"AC-6: command_log traegt {[e['date'] for e in eintraege]}, erwartet "
        "['2026-08-21'] (Ortstag, nicht der UTC-Tag 2026-08-20)"
    )
    assert zweiter_lauf.success is False, (
        "AC-6: der zweite Versuch im selben Ortstag wurde nicht als Duplikat "
        f"erkannt — {zweiter_lauf.confirmation_body!r}"
    )
    assert sorted(s.date for s in danach.stages) == [D21, D23], (
        f"AC-6: Etappen stehen auf {sorted(s.date for s in danach.stages)}, "
        f"erwartet {[D21, D23]} (genau EINE Verschiebung)"
    )


# ══════════════════════ AC-7/AC-8: Tourauswahl ══════════════════════


def test_ac7_find_active_trip_rechnet_je_tour_in_deren_eigener_zone(monkeypatch):
    """AC-7 — die Pflicht-Probe gegen die gemessene Nachweis-Luecke.

    GIVEN zwei Touren mit identischen Etappendaten (19./20.08.), eine in
          Wellington (Ortstag 21.08., lokal also beendet), eine auf Korsika
          (Ortstag 20.08., lokal aktiv),
    WHEN  ``_find_active_trip(now_utc, user_id)`` um 14:00 UTC am 20.08. laeuft,
    THEN  liefert sie die Korsika-Tour.

    Der Aufbau ist so gewaehlt, dass JEDE Tagesbestimmung VOR der Schleife
    scheitert — genau die Regression, die #1724 in ``_get_active_trips`` behoben
    hat: mit einem einzigen Tag 20.08. gewinnt die zuerst gepruefte
    Wellington-Tour, mit einem einzigen Tag 21.08. passt keine Tour mehr und
    auch der Zukunfts-Rueckfall greift nicht (Ergebnis ``None``).

    ``load_all_trips`` wird durch eine feste Liste ECHTER Trips ersetzt, weil
    die Pruefreihenfolge Teil der Zusicherung ist — die Glob-Reihenfolge des
    Loaders waere dateisystemabhaengig.
    """
    wellington = _trip("wellington-tour", [D19, D20], WP_NZ)
    korsika = _trip("korsika-tour", [D19, D20], WP_KORSIKA)
    monkeypatch.setattr(
        "services.inbound_telegram_reader.load_all_trips",
        lambda user_id="default", include_archived=False: [wellington, korsika],
    )

    with freeze_time(MITTAGS_UTC):
        _anker(MITTAGS_UTC, WELLINGTON_ZONE, D21)
        assert MITTAGS_UTC.astimezone(ZoneInfo(KORSIKA_ZONE)).date() == D20, (
            "Testaufbau: die Korsika-Tour muss zum selben Augenblick einen "
            "ANDEREN Ortstag tragen als die Wellington-Tour"
        )
        reader = InboundTelegramReader.__new__(InboundTelegramReader)
        gewaehlt = reader._find_active_trip(MITTAGS_UTC, "default")

    assert gewaehlt is korsika, (
        "AC-7: _find_active_trip() lieferte "
        f"{getattr(gewaehlt, 'id', None)!r}, erwartet 'korsika-tour' — die "
        "Wellington-Tour ist an ihrem eigenen Ortstag (21.08.) bereits vorbei, "
        "die Korsika-Tour an ihrem (20.08.) aktiv"
    )


def test_ac7_zukunfts_rueckfall_rechnet_ebenfalls_je_tour(monkeypatch):
    """AC-7, zweite Haelfte — der Zukunfts-Rueckfall, nicht die Overlap-Schleife.

    GIVEN keine Tour ist an ihrem eigenen Ortstag aktiv, aber zwei Touren liegen
          in Zonen an den ENDEN der bewohnten Skala: Pago Pago (UTC-11, Ortstag
          19.08.) mit Etappen ab dem 21.08. -- aus ihrer Sicht zukuenftig -- und
          Kiritimati (UTC+14, Ortstag 21.08.) mit einer einzigen Etappe am
          20.08. -- aus ihrer Sicht bereits VORBEI,
    WHEN  ``_find_active_trip(now_utc, user_id)`` um 10:30 UTC am 20.08. laeuft,
    THEN  liefert sie die Pago-Pago-Tour. Die Kiritimati-Tour darf nicht in die
          Zukunfts-Auswahl geraten, obwohl ihr Startdatum (20.08.) das FRUEHERE
          ist -- ``min(...)`` wuerde sie sonst gewinnen lassen.

    Warum dieser Test zusaetzlich zu ``test_ac7_...je_tour_in_deren_eigener_zone``
    noetig ist: jener prueft die Overlap-SCHLEIFE. Der Rueckfall darunter ist ein
    zweiter, eigener Rechenweg -- eine Verfaelschung, die NUR dort den Ortstag
    hebt (klassisch: die Schleifenvariable ``today`` nach der Schleife
    weiterbenutzen, statt je Tour neu zu rechnen), liess jener Test gruen.

    Warum die exotischen Zonen: der Rueckfall ist nur falsifizierbar, wenn eine
    Tour existiert, die an IHREM Ortstag vergangen ist, an einem gehievten Tag
    aber als zukuenftig durchgeht -- und deren Start zugleich vor dem der echten
    Siegerin liegt. Zwischen zwei benachbarten Zonen (ein Tag Unterschied) ist
    das rechnerisch unmoeglich: das dafuer noetige Startdatum liegt in einem
    leeren Intervall. Erst drei Kalendertage zum selben Augenblick machen die
    Luecke sichtbar, und die gibt es nur zwischen UTC-11 und UTC+14.
    """
    pago = _trip("pago-tour", [D21, D22], PAGO)
    kiritimati = _trip("kiritimati-tour", [D20], KIRITIMATI)
    monkeypatch.setattr(
        "services.inbound_telegram_reader.load_all_trips",
        lambda user_id="default", include_archived=False: [pago, kiritimati],
    )

    with freeze_time(DREI_TAGE_UTC):
        _anker(DREI_TAGE_UTC, PAGO_ZONE, D19)
        _anker(DREI_TAGE_UTC, KIRITIMATI_ZONE, D21)
        # Vorbedingung 1: KEINE Tour ist an ihrem Ortstag aktiv -- sonst greift
        # die Overlap-Schleife und der Rueckfall wird nie erreicht.
        assert pago.stages[0].date > D19 and kiritimati.stages[-1].date < D21, (
            "Testaufbau: beide Touren muessen an ihrem eigenen Ortstag "
            "AUSSERHALB liegen, damit der Zukunfts-Rueckfall ueberhaupt laeuft"
        )
        # Vorbedingung 2: die falsche Tour startet FRUEHER -- ohne das koennte
        # `min(...)` sie auch bei fehlerhafter Filterung nie waehlen.
        assert kiritimati.stages[0].date < pago.stages[0].date, (
            "Testaufbau nicht diskriminierend: die vergangene Tour muss das "
            "fruehere Startdatum tragen, sonst gewinnt die richtige zufaellig"
        )
        reader = InboundTelegramReader.__new__(InboundTelegramReader)
        gewaehlt = reader._find_active_trip(DREI_TAGE_UTC, "default")

    assert gewaehlt is pago, (
        "AC-7 (Rueckfall): _find_active_trip() lieferte "
        f"{getattr(gewaehlt, 'id', None)!r}, erwartet 'pago-tour'. "
        "'kiritimati-tour' heisst: der Rueckfall hat den Ortstag EINER Tour "
        "(21.08.) fuer alle benutzt und die am 20.08. endende Tour faelschlich "
        "als zukuenftig gezaehlt. 'None' heisst dasselbe mit dem anderen "
        "Ortstag (19.08.) -- dann fiel die echte Siegerin aus der Auswahl."
    )


def test_ac8_find_active_trip_waehlt_an_der_tourgrenze_die_folgetour(monkeypatch):
    """AC-8 — der Blast-Radius-Grenzfall vor JEDEM Telegram-Befehl.

    GIVEN zwei aneinandergrenzende Touren in Mitteleuropa (UTC+2): A endet am
          Ortstag 20.08., B beginnt am 21.08.,
    WHEN  eine Nachricht um 22:30 UTC = 00:30 Ortszeit des 21.08. eintrifft,
    THEN  waehlt ``_find_active_trip`` bereits Tour B. Vor dem Fix haette der
          Servertag Tour A gewaehlt — eine abgelaufene Tour haette den Befehl
          beantwortet.
    """
    tour_a = _trip("tour-a-endet", [D19, D20], WP_KORSIKA)
    tour_b = _trip("tour-b-beginnt", [D21, D22], WP_KORSIKA)
    monkeypatch.setattr(
        "services.inbound_telegram_reader.load_all_trips",
        lambda user_id="default", include_archived=False: [tour_a, tour_b],
    )

    with freeze_time(NACHTS_UTC):
        _anker(NACHTS_UTC, KORSIKA_ZONE, D21)
        reader = InboundTelegramReader.__new__(InboundTelegramReader)
        gewaehlt = reader._find_active_trip(NACHTS_UTC, "default")

    assert gewaehlt is tour_b, (
        "AC-8: _find_active_trip() lieferte "
        f"{getattr(gewaehlt, 'id', None)!r}, erwartet 'tour-b-beginnt' — lokal "
        f"ist bereits {D21}, Tour A endete am {D20}"
    )


# ═════════ Adversary F001: der Parameter schlaegt die Umgebungsuhr ═════════
#
# Alle Tests oben frieren die Uhr auf DENSELBEN Zeitpunkt ein, den sie als
# ``now_utc`` hereinreichen. freezegun patcht ``datetime.now()`` global — damit
# sind Parameterwert und Systemuhr im Test IMMER identisch, und die Zusicherung
# "der Aufrufer bestimmt den Zeitpunkt, nicht die Umgebung" (ADR-0051 Regel 3,
# woertlich in allen vier Docstrings) ist strukturell nicht falsifizierbar. Eine
# Verfaelschung, die den Pflichtparameter STEHEN laesst und im Rumpf trotzdem
# ``datetime.now(tz=timezone.utc)`` benutzt, blieb an allen fuenf Stellen
# ungefangen. Die Tests unten ziehen die beiden Zeitpunkte auseinander.

FROST_UTC = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)   # die Uhr: Ortstag 20.08.
PARAM_UTC = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)   # der Parameter: Ortstag 22.08.
WP_KORSIKA_NORD = (42.5, 9.2)   # ebenfalls Europe/Paris, anderer Wegpunkt


def _trip_zwei_wegpunkte(trip_id: str) -> Trip:
    """Etappe am 20.08. und am 22.08., beide auf Korsika, aber an VERSCHIEDENEN
    Wegpunkten — damit die Standortwahl von ``/jetzt`` verraet, welchen Tag der
    Pruefling benutzt hat."""
    return Trip(
        id=trip_id, name=trip_id,
        stages=[
            Stage(id="S-frost", name="Etappe 20.08.", date=D20,
                  waypoints=[_wp(0, WP_KORSIKA)]),
            Stage(id="S-param", name="Etappe 22.08.", date=D22,
                  waypoints=[_wp(1, WP_KORSIKA_NORD)]),
        ],
    )


def _fall_status(monkeypatch):
    """`/status` — welche Etappen bleiben in der Liste?"""
    trip = _trip("param-status", [D20, D21, D22, D23], WP_KORSIKA)
    save_trip(trip)
    body = _befehl(trip, "### status", PARAM_UTC).confirmation_body
    return frozenset(t for t in (D20, D21, D22, D23) if f"{t:%d.%m.%Y}" in body)


def _fall_jetzt(monkeypatch):
    """`/jetzt` — von welchem Wegpunkt holt der Nowcast seine Koordinaten?"""
    aufrufe: list[tuple[float, float]] = []

    class _AufzeichnenderNowcast(RadarNowcastService):
        def get_nowcast(self, lat, lon, priority="user_briefing"):
            aufrufe.append((round(lat, 4), round(lon, 4)))
            return NowcastResult(onset_minutes=None,
                                 intensity_label="Kein Niederschlag",
                                 source="radar")

    monkeypatch.setattr("services.radar_service.RadarNowcastService",
                        _AufzeichnenderNowcast)
    trip = _trip_zwei_wegpunkte("param-jetzt")
    save_trip(trip)
    _befehl(trip, "### now", PARAM_UTC)
    return tuple(aufrufe)


def _fall_ruhetag(monkeypatch):
    """`### ruhetag` — ab welchem Tag gelten Etappen als verschiebbar?"""
    trip = _trip("param-ruhetag", [D20, D21, D22, D23], WP_KORSIKA)
    save_trip(trip)
    ergebnis = _befehl(trip, "### ruhetag", PARAM_UTC)
    return frozenset(s.old_date for s in (ergebnis.shifts or []))


def _tourauswahl(monkeypatch, trips: list[Trip]):
    monkeypatch.setattr(
        "services.inbound_telegram_reader.load_all_trips",
        lambda user_id="default", include_archived=False: trips,
    )
    reader = InboundTelegramReader.__new__(InboundTelegramReader)
    return getattr(reader._find_active_trip(PARAM_UTC, "default"), "id", None)


def _fall_tourauswahl_overlap(monkeypatch):
    """`_find_active_trip`, Overlap-Schleife — welche laufende Tour gewinnt?"""
    return _tourauswahl(monkeypatch, [
        _trip("laeuft-am-20-08", [D20], WP_KORSIKA),
        _trip("laeuft-am-22-08", [D22], WP_KORSIKA),
    ])


def _fall_tourauswahl_rueckfall(monkeypatch):
    """`_find_active_trip`, Zukunfts-Rueckfall — welche Tour gilt als kuenftig?

    Keine der beiden laeuft: am 20.08. liegen beide in der Zukunft, am 22.08.
    ist die erste bereits vorbei. Der Rueckfall entscheidet.
    """
    return _tourauswahl(monkeypatch, [
        _trip("startet-am-21-08", [D21], WP_KORSIKA),
        _trip("startet-am-23-08", [D23], WP_KORSIKA),
    ])


@pytest.mark.parametrize("fall, erwartet_parameter, erwartet_systemuhr", [
    pytest.param(_fall_status, frozenset({D22, D23}),
                 frozenset({D20, D21, D22, D23}), id="status"),
    pytest.param(_fall_jetzt, (WP_KORSIKA_NORD,), (WP_KORSIKA,), id="jetzt"),
    pytest.param(_fall_ruhetag, frozenset({D23}), frozenset({D21, D22, D23}),
                 id="ruhetag"),
    pytest.param(_fall_tourauswahl_overlap, "laeuft-am-22-08", "laeuft-am-20-08",
                 id="tourauswahl-overlap"),
    pytest.param(_fall_tourauswahl_rueckfall, "startet-am-23-08",
                 "startet-am-21-08", id="tourauswahl-rueckfall"),
])
def test_befehlspfade_folgen_dem_parameter_nicht_der_systemuhr(
    fall, erwartet_parameter, erwartet_systemuhr, monkeypatch,
):
    """Adversary F001 — die vier Fundstellen (fuenf Rechenwege) muessen dem
    UEBERGEBENEN Zeitpunkt folgen, nicht der Uhr des Rechners.

    GIVEN die Systemuhr steht auf dem 20.08. (Ortstag 20.08. auf Korsika),
    WHEN  derselbe Aufruf ``now_utc`` = 22.08. hereinreicht (Ortstag 22.08.),
    THEN  entspricht die Antwort dem 22.08. Ein Pruefling, der den
          Pflichtparameter zwar entgegennimmt, im Rumpf aber
          ``datetime.now(tz=timezone.utc)`` benutzt, liefert stattdessen die
          Antwort zum 20.08. — genau das war bis hierher ungefangen.

    Die beiden Erwartungswerte stehen literal nebeneinander und muessen
    verschieden sein: das ist die Selbstpruefung, dass der Fall ueberhaupt
    zwischen Parameter und Uhr unterscheiden KANN.
    """
    assert erwartet_parameter != erwartet_systemuhr, (
        f"Testaufbau nicht diskriminierend: Parameter- und Systemuhr-Erwartung "
        f"sind beide {erwartet_parameter!r} — der Fall kann nichts belegen"
    )

    with freeze_time(FROST_UTC):
        tag_uhr = FROST_UTC.astimezone(ZoneInfo(KORSIKA_ZONE)).date()
        tag_param = PARAM_UTC.astimezone(ZoneInfo(KORSIKA_ZONE)).date()
        assert tag_uhr != tag_param, (
            f"Testaufbau: Uhr ({tag_uhr}) und Parameter ({tag_param}) muessen "
            "auf verschiedene ORTSTAGE fallen, nicht nur auf verschiedene Uhrzeiten"
        )
        # Belegt, dass die eingefrorene Uhr im Pruefprozess wirklich greift —
        # sonst waere ein gruener Lauf kein Beweis, sondern ein Zufall.
        assert datetime.now(tz=timezone.utc) == FROST_UTC, (
            "Testaufbau: freeze_time greift nicht, die Systemuhr steht auf "
            f"{datetime.now(tz=timezone.utc).isoformat()}"
        )
        beobachtet = fall(monkeypatch)

    hinweis = ""
    if beobachtet == erwartet_systemuhr:
        hinweis = (
            f"\n  Das ist GENAU das Ergebnis zum {tag_uhr:%d.%m.%Y} — der "
            "Pruefling hat den uebergebenen Zeitpunkt ignoriert und die "
            "Systemuhr benutzt (ADR-0051 Regel 3)."
        )
    assert beobachtet == erwartet_parameter, (
        f"Der Befehlspfad folgte nicht dem uebergebenen Zeitpunkt.\n"
        f"  uebergeben:  {PARAM_UTC.isoformat()} (Ortstag {tag_param:%d.%m.%Y})\n"
        f"  Systemuhr:   {FROST_UTC.isoformat()} (Ortstag {tag_uhr:%d.%m.%Y})\n"
        f"  erwartet:    {erwartet_parameter!r}\n"
        f"  beobachtet:  {beobachtet!r}{hinweis}"
    )
