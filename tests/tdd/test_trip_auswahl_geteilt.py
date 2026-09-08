"""TDD RED — geteilte Trip-Auswahlregel (Issue #2184, Epic #2133 Scheibe S4).

SPEC: docs/specs/modules/feat_2184_s4_premium_sms_kommandoverarbeiter.md
      (Implementation Details 1, Dependencies `pick_active_trip`)

Zielverhalten: Die Auswahl "welche Tour meint eine Nachricht ohne Trip-Namen"
liegt als ``services.trip_selection.pick_active_trip(trips, now_utc)`` an EINER
Stelle. Der Premium-SMS-Reader braucht sie genauso wie der Telegram-Reader —
eine zweite Kopie derselben Regel waere genau der Fehler, den ADR-0044 fuer die
Ortstag-Aufloesung verbietet.

RED heute: ``src/services/trip_selection.py`` existiert nicht — jeder Test, der
``pick_active_trip`` braucht, scheitert mit ImportError. Der Import steht
deshalb IN den Testfunktionen, nicht am Modulkopf: sonst risse er die
Regressionswaechter unten mit in einen Collection-Error, und genau die muessen
heute GRUEN sein.

GRUEN heute (Regressionswaechter, bewusst): die vier
``test_bestand_find_active_trip_*``-Tests halten das HEUTIGE Verhalten von
``InboundTelegramReader._find_active_trip`` fest. Sie sind das Netz unter dem
Umbau zur Delegations-Huelle — ohne sie koennte ``pick_active_trip`` eine
andere Regel implementieren und die Huelle das unbemerkt uebernehmen.

Kein Mock-Theater: es gibt keinen Ersatz fuer irgendetwas. Die Touren liegen
als echte Dateien auf der isolierten Datenwurzel (autouse-Fixture aus
tests/conftest.py, #1133), ``load_all_trips`` liest sie echt, die Ortszonen
kommen aus den echten Koordinaten.

Die Verhaltensgleichheit wird an ERGEBNISSEN geprueft, nicht an Aufrufen: ein
Test, der bloss nachsieht, ob ``_find_active_trip`` die neue Funktion aufruft,
bewachte die Regel nicht, sondern nur die Verdrahtung.
"""
from __future__ import annotations

import sys
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from app.loader import load_all_trips, save_trip  # noqa: E402
from app.trip import Stage, Trip, Waypoint  # noqa: E402
from services.inbound_telegram_reader import InboundTelegramReader  # noqa: E402

#: Zwei Orte, zwoelf Stunden auseinander — nur so wird sichtbar, dass der
#: Vergleichstag JE TOUR am eigenen Ort gemessen wird (ADR-0044) und nicht
#: einmal an der Serveruhr.
AUCKLAND = (-36.8485, 174.7633)     # Pacific/Auckland, UTC+12
KORSIKA = (42.1333, 9.1333)         # Europe/Paris, UTC+2

#: 2026-08-20 13:00 UTC = 21.08. 01:00 in Auckland, aber 20.08. 15:00 auf
#: Korsika. Genau das Fenster, in dem ein gemeinsamer Vergleichstag die
#: falsche Tour waehlt.
JETZT = datetime(2026, 8, 20, 13, 0, tzinfo=timezone.utc)


def _kennung() -> str:
    """Mandantenkennung OHNE "tdd"/"test" (sonst greift die Test-Umleitung
    in ``Settings.with_user_profile``)."""
    return f"tripauswahl-{uuid.uuid4().hex[:8]}"


def _trip(user_id: str, *, name: str, ort: tuple[float, float],
          tage: list[date]) -> Trip:
    """Echte Tour auf der isolierten Datenwurzel, eine Etappe je Tag."""
    trip_id = f"auswahl-{uuid.uuid4().hex[:8]}"
    stages = [
        Stage(
            id=f"S{i}", name=f"Etappe {i}", date=tag,
            waypoints=[
                Waypoint(id=f"W{i}a", name="Start",
                         lat=ort[0], lon=ort[1], elevation_m=100),
                Waypoint(id=f"W{i}b", name="Ziel",
                         lat=ort[0] + 0.02, lon=ort[1] + 0.02, elevation_m=200),
            ],
        )
        for i, tag in enumerate(tage)
    ]
    trip = Trip(id=trip_id, name=name, stages=stages)
    save_trip(trip, user_id)
    return trip


def _trip_ohne_etappen(user_id: str, *, name: str) -> Trip:
    trip = Trip(id=f"leer-{uuid.uuid4().hex[:8]}", name=name, stages=[])
    save_trip(trip, user_id)
    return trip


def _id_oder_none(trip: Trip | None) -> str | None:
    return trip.id if trip is not None else None


# ---------------------------------------------------------------------------
# Szenarien — je Szenario ein Aufbau, von beiden Wegen befragt
# ---------------------------------------------------------------------------

def _szenario_overlap_am_ortstag(user_id: str) -> str:
    """Die Auckland-Tour liegt auf dem 21.08. — an IHREM Ortstag (21.08.)
    ueberlappt sie, am UTC-Tag der Nachricht (20.08.) nicht. Die zweite Tour
    liegt in der Zukunft und waere der Rueckfall, wenn die Regel den Ortstag
    ignorierte."""
    aktiv = _trip(user_id, name="Auckland Tour", ort=AUCKLAND,
                  tage=[date(2026, 8, 21)])
    _trip(user_id, name="Korsika Spaeter", ort=KORSIKA, tage=[date(2026, 8, 25)])
    return aktiv.id


def _szenario_zukunfts_rueckfall(user_id: str) -> str:
    """Keine Tour ueberlappt; die FRUEHESTE zukuenftige gewinnt — nicht die
    zuerst geladene."""
    _trip(user_id, name="Korsika Sehr Spaet", ort=KORSIKA,
          tage=[date(2026, 9, 20)])
    frueh = _trip(user_id, name="Korsika Bald", ort=KORSIKA,
                  tage=[date(2026, 8, 28)])
    _trip(user_id, name="Korsika Vorbei", ort=KORSIKA, tage=[date(2026, 8, 1)])
    return frueh.id


def _szenario_nur_vergangenheit(user_id: str) -> None:
    """Alles vorbei, nichts in der Zukunft -> keine Tour."""
    _trip(user_id, name="Korsika Vorbei A", ort=KORSIKA, tage=[date(2026, 7, 1)])
    _trip(user_id, name="Korsika Vorbei B", ort=KORSIKA, tage=[date(2026, 8, 2)])
    return None


def _szenario_etappenlose_tour_wird_uebersprungen(user_id: str) -> str:
    """Eine Tour ohne Etappen darf weder ueberlappen noch den Rueckfall
    besetzen — sie wird uebersprungen."""
    _trip_ohne_etappen(user_id, name="Leere Tour")
    aktiv = _trip(user_id, name="Korsika Heute", ort=KORSIKA,
                  tage=[date(2026, 8, 20)])
    return aktiv.id


def _szenario_ohne_touren(user_id: str) -> None:
    return None


SZENARIEN = {
    "overlap_am_ortstag": _szenario_overlap_am_ortstag,
    "zukunfts_rueckfall": _szenario_zukunfts_rueckfall,
    "nur_vergangenheit": _szenario_nur_vergangenheit,
    "etappenlose_tour": _szenario_etappenlose_tour_wird_uebersprungen,
    "ohne_touren": _szenario_ohne_touren,
}


# ═════════════════════ Die neue, geteilte Regel ═══════════════════════════


def test_pick_active_trip_waehlt_die_tour_mit_overlap_am_eigenen_ortstag():
    """GIVEN eine Auckland-Tour, deren einzige Etappe auf dem 21.08. liegt,
    und ein Anfragezeitpunkt, der in Auckland bereits der 21.08. ist, in UTC
    aber noch der 20.08.
    WHEN  ``pick_active_trip(trips, now_utc)`` gefragt wird
    THEN  liefert sie genau diese Tour — der Vergleichstag wird am Ort DIESER
          Tour gemessen (ADR-0044), nicht an der Serveruhr.

    RED heute: ``services.trip_selection`` existiert nicht (ImportError).
    Die zweite, spaetere Tour ist die Gegenprobe: eine Regel, die den Ortstag
    ignoriert, faellt auf sie zurueck und liefert die falsche Kennung statt
    schlicht ``None``.
    """
    from services.trip_selection import pick_active_trip

    uid = _kennung()
    erwartet = _szenario_overlap_am_ortstag(uid)

    gewaehlt = pick_active_trip(load_all_trips(uid), JETZT)

    assert _id_oder_none(gewaehlt) == erwartet, (
        f"pick_active_trip muss die am eigenen Ortstag ueberlappende Tour "
        f"waehlen, gewaehlt wurde {_id_oder_none(gewaehlt)!r}, erwartet "
        f"{erwartet!r}"
    )


def test_pick_active_trip_faellt_auf_die_frueheste_zukuenftige_tour_zurueck():
    """GIVEN keine Tour ueberlappt den heutigen Ortstag, es gibt aber zwei
    zukuenftige und eine vergangene.
    WHEN  ``pick_active_trip`` gefragt wird
    THEN  liefert sie die FRUEHESTE zukuenftige — nicht die zuerst geladene
          und nicht die vergangene.

    RED heute: ImportError.
    """
    from services.trip_selection import pick_active_trip

    uid = _kennung()
    erwartet = _szenario_zukunfts_rueckfall(uid)

    gewaehlt = pick_active_trip(load_all_trips(uid), JETZT)

    assert _id_oder_none(gewaehlt) == erwartet, (
        f"Der Rueckfall muss die frueheste ZUKUENFTIGE Tour liefern, gewaehlt "
        f"wurde {_id_oder_none(gewaehlt)!r}, erwartet {erwartet!r}"
    )


@pytest.mark.parametrize("szenario", ["nur_vergangenheit", "ohne_touren"])
def test_pick_active_trip_liefert_none_wenn_es_nichts_zu_waehlen_gibt(szenario):
    """GIVEN entweder gar keine Touren oder ausschliesslich vergangene.
    WHEN  ``pick_active_trip`` gefragt wird
    THEN  liefert sie ``None`` — kein Rueckfall auf irgendeine Tour.

    RED heute: ImportError.
    """
    from services.trip_selection import pick_active_trip

    uid = _kennung()
    SZENARIEN[szenario](uid)

    gewaehlt = pick_active_trip(load_all_trips(uid), JETZT)

    assert gewaehlt is None, (
        f"Ohne waehlbare Tour muss None herauskommen, geliefert wurde "
        f"{_id_oder_none(gewaehlt)!r} (Szenario {szenario!r})"
    )


def test_pick_active_trip_ueberspringt_touren_ohne_etappen():
    """GIVEN eine Tour ohne jede Etappe steht vor einer heute laufenden Tour.
    WHEN  ``pick_active_trip`` gefragt wird
    THEN  liefert sie die laufende Tour — die etappenlose wird uebersprungen
          statt mit einem IndexError zu enden.

    RED heute: ImportError.
    """
    from services.trip_selection import pick_active_trip

    uid = _kennung()
    erwartet = _szenario_etappenlose_tour_wird_uebersprungen(uid)

    gewaehlt = pick_active_trip(load_all_trips(uid), JETZT)

    assert _id_oder_none(gewaehlt) == erwartet, (
        f"Die etappenlose Tour muss uebersprungen werden, gewaehlt wurde "
        f"{_id_oder_none(gewaehlt)!r}, erwartet {erwartet!r}"
    )


# ═════════════════ Verhaltensgleichheit beider Wege ═══════════════════════


@pytest.mark.parametrize("szenario", sorted(SZENARIEN))
def test_beide_wege_waehlen_dieselbe_tour(szenario):
    """GIVEN dieselbe Tourenlage auf derselben Datenwurzel.
    WHEN  einmal ``InboundTelegramReader._find_active_trip(now_utc, user_id)``
          und einmal ``pick_active_trip(load_all_trips(user_id), now_utc)``
          gefragt wird
    THEN  liefern beide DIESELBE Tour (bzw. beide ``None``).

    Gemessen wird das ERGEBNIS, nicht der Aufruf: ein Test, der bloss
    nachsaehe, ob die Huelle die neue Funktion ruft, bewachte die Regel nicht.
    Damit ist "bit-identisch" (Spec, Implementation Details 1) ueber alle fuenf
    Zweige der Regel geprueft, nicht nur ueber den Normalfall.

    RED heute: ImportError.
    """
    from services.trip_selection import pick_active_trip

    uid = _kennung()
    SZENARIEN[szenario](uid)

    ueber_huelle = InboundTelegramReader()._find_active_trip(JETZT, uid)
    ueber_regel = pick_active_trip(load_all_trips(uid), JETZT)

    assert _id_oder_none(ueber_huelle) == _id_oder_none(ueber_regel), (
        f"Szenario {szenario!r}: beide Wege muessen dieselbe Tour waehlen — "
        f"_find_active_trip liefert {_id_oder_none(ueber_huelle)!r}, "
        f"pick_active_trip liefert {_id_oder_none(ueber_regel)!r}"
    )


# ═══════════ Regressionswaechter: heutiges Verhalten der Huelle ════════════
# Heute GRUEN. Sie halten fest, was ``_find_active_trip`` VOR dem Umbau tut —
# ohne sie koennte die Delegations-Huelle eine abweichende Regel uebernehmen,
# ohne dass irgendetwas rot wird.


def test_bestand_find_active_trip_waehlt_overlap_am_ortstag():
    """GIVEN die Auckland-Lage aus dem ersten Test.
    WHEN  ``_find_active_trip`` gefragt wird
    THEN  liefert es die Auckland-Tour. Heutiges Verhalten, festgehalten.
    """
    uid = _kennung()
    erwartet = _szenario_overlap_am_ortstag(uid)

    gewaehlt = InboundTelegramReader()._find_active_trip(JETZT, uid)

    assert _id_oder_none(gewaehlt) == erwartet, (
        f"Bestandsverhalten: _find_active_trip waehlt die am eigenen Ortstag "
        f"ueberlappende Tour, geliefert wurde {_id_oder_none(gewaehlt)!r}"
    )


def test_bestand_find_active_trip_faellt_auf_frueheste_zukunft_zurueck():
    """GIVEN keine ueberlappende, zwei zukuenftige Touren.
    WHEN  ``_find_active_trip`` gefragt wird
    THEN  liefert es die frueheste zukuenftige. Heutiges Verhalten.
    """
    uid = _kennung()
    erwartet = _szenario_zukunfts_rueckfall(uid)

    gewaehlt = InboundTelegramReader()._find_active_trip(JETZT, uid)

    assert _id_oder_none(gewaehlt) == erwartet, (
        f"Bestandsverhalten: Rueckfall auf die frueheste zukuenftige Tour, "
        f"geliefert wurde {_id_oder_none(gewaehlt)!r}"
    )


def test_bestand_find_active_trip_ohne_touren_liefert_none():
    """GIVEN der Mandant hat keine einzige Tour.
    WHEN  ``_find_active_trip`` gefragt wird
    THEN  liefert es ``None``. Heutiges Verhalten.
    """
    uid = _kennung()

    assert InboundTelegramReader()._find_active_trip(JETZT, uid) is None, (
        "Bestandsverhalten: ohne Touren liefert _find_active_trip None"
    )


def test_bestand_find_active_trip_ueberspringt_touren_ohne_etappen():
    """GIVEN eine etappenlose Tour vor einer laufenden.
    WHEN  ``_find_active_trip`` gefragt wird
    THEN  liefert es die laufende. Heutiges Verhalten.
    """
    uid = _kennung()
    erwartet = _szenario_etappenlose_tour_wird_uebersprungen(uid)

    gewaehlt = InboundTelegramReader()._find_active_trip(JETZT, uid)

    assert _id_oder_none(gewaehlt) == erwartet, (
        f"Bestandsverhalten: etappenlose Touren werden uebersprungen, "
        f"geliefert wurde {_id_oder_none(gewaehlt)!r}"
    )
