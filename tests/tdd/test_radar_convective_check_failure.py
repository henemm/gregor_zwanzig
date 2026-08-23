"""TDD RED — eine AUSGEFALLENE Gewitterpruefung traegt die
Briefing-Unterdrueckung nicht mehr (Issue #2050 Scheibe S4a, Teil B: AC-7 bis
AC-9).

SPEC:    docs/specs/modules/feat_2050_s4a_radar_teilausfall.md
KONTEXT: docs/context/feat-2050-s4a-radar-teilausfall.md

Der schwerwiegende Fall aus Anforderung B-4: `RadarFrame.is_convective` ist
per Vorgabe `False` und wird ohne Gewitter-Beiabruf nie gesetzt — aus „nicht
geprueft" wird still „kein Gewitter". Der Sicherheits-Override aus #883
(„konvektive Gefahr durchbricht die Briefing-Unterdrueckung") feuert dann
nicht, weil die Pruefung ausfiel: ein Gewitteralarm wird auf Grundlage einer
NIE STATTGEFUNDENEN Pruefung unterdrueckt (`trip_alert.py:1815`). Das Feld
`convective_checked` haelt den Unterschied fest, wird aber ausserhalb von
`format_now_text` (dem `/jetzt`-Pull-Pfad) in keiner Zeile Produktivcode
gelesen — im Alarmpfad null Treffer.

RED-Stand (gemessen, s. `docs/artifacts/.../test-red-output.txt`):

* AC-7 ist ROT: der Lauf bleibt trotz ausgefallener Gewitterpruefung an der
  Briefing-Unterdrueckung haengen (`triggered_count == 0`).
* AC-8 ist die GEGENPROBE gegen Uebersteuerung und heute wie nachher GRUEN —
  sie muss rot werden, wenn die neue Regel die Briefing-Unterdrueckung auch
  fuer eine DURCHGEFUEHRTE, negative Gewitterpruefung aushebelt.
* AC-9 ist ROT: der Ausfall der Gewitterpruefung steht in keinem
  Protokolleintrag.

AC-7 und AC-8 unterscheiden sich in GENAU EINEM Bit (`gewitterpruefung_lief`)
— derselbe Aufbau, dieselbe Lage, dieselbe Ankuendigung. Ohne diese
Deckungsgleichheit koennte ein gruenes AC-7 auch von einer ganz anderen
Abweichung im Aufbau stammen.

Mock-frei: der Ausfall der Beiabfrage wird an DERSELBEN Stelle nachgestellt,
an der `_fetch_inca` ihn im Betrieb quittiert (`radar_service.py:762-764`:
`self._convective_checked = False`) — der Marker entsteht damit an seiner
Bildungsstelle (`:1129`), nicht im Test. Jeder Lauf faehrt ueber die echte
Ausloeseentscheidung `TripAlertService.check_radar_alerts()` ueber die
`AlarmPruefstrecke` (#2050 S1); gelesen wird ueber `alert_log.read_undelivered()`.

Keine Wanduhr: alle Zeitpunkte haengen an `_AT` (gestellte Uhr), Trip UND
Briefing-Anker entstehen unter derselben gestellten Uhr.

Pfadregel #1409: alles relativ zu DIESER Datei, nie ueber einen festen
Hauptrepo-Pfad.
"""
from __future__ import annotations

import sys
import uuid
from dataclasses import fields
from datetime import datetime, timedelta, timezone
from pathlib import Path

from freezegun import freeze_time

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from services import alert_log  # noqa: E402
from services.radar_cache import reset_shared_radar_cache_for_tests  # noqa: E402
from services.radar_service import RadarNowcastService  # noqa: E402

from tests.helpers.alarm_pruefstrecke import AlarmPruefstrecke  # noqa: E402
from tests.tdd.test_952_onset_alert_fidelity import _clean_user  # noqa: E402
from tests.tdd.test_alarm_pruefstrecke_selbstschutz import (  # noqa: E402
    _AT, _radar_trip, _settings_all_channels, _write_premium_profile,
)
from tests.tdd.test_alarm_szenario_briefing_ueberholung_zeitreihe import (  # noqa: E402
    _briefing_anker, _dauerregen, _gelesene_briefing_werte, _kurze_spitze,
)

# Die Ankuendigung des Briefings. 1,0 mm heisst: die Ueberholungspruefung
# verlangt >= 2,0 mm (Faktor) UND >= 2,0 mm (absolute Untergrenze).
_BRIEFING_MM = 1.0

# 11 mm/h ueber 10 Minuten ~ 1,83 mm im 60-Min-Vergleichsfenster: die
# Ankuendigung wird NICHT ueberholt (`_overtaking` False), der Beginn liegt
# aber bei ~5 Minuten und damit weit innerhalb der Ausloeseschwelle. Genau die
# Lage, in der heute allein `is_convective` ueber Alarm oder Stille
# entscheidet — und in der eine ausgefallene Pruefung wie ein geprueftes
# „kein Gewitter" wirkt.
_LAGE_RATE_MM_H = 11.0


def _uid(tag: str) -> str:
    return f"tdd-2050-s4a-b-{tag}-{uuid.uuid4().hex[:6]}"


class _RadarMitGewitterpruefung(RadarNowcastService):
    """Echter Dienst mit ECHTER Ergebnis-Ableitung; nachgestellt wird
    ausschliesslich die Abrufkette.

    `gewitterpruefung_lief=False` setzt `self._convective_checked = False` —
    exakt das, was `_fetch_inca` tut, wenn der Gewitter-Beiabruf leer
    zurueckkommt (`radar_service.py:762-764`, ADR-0018: „einen
    fehlgeschlagenen Check nicht still als ‚kein Gewitter' durchgehen
    lassen"). Der Marker `convective_checked` entsteht danach an SEINER
    Bildungsstelle (`:1129`) — ein im Test fertig gebautes `NowcastResult`
    pruefte dagegen nur die eigene Annahme.

    🔴 Falle: bei einem CACHE-TREFFER wird `_fetch_frames_with_fallback` gar
    nicht betreten und `_convective_checked` bleibt auf dem im Aufruf
    gesetzten Vorgabewert `True` — der Ausfall waere dann still weg. Der
    Frame-Cache ist ein Prozess-Singleton mit Koordinaten-Schluessel;
    `AlarmPruefstrecke.lauf()` leert ihn vor JEDEM Lauf
    (`alarm_pruefstrecke.py:149`), und `_gemessenes_ergebnis()` unten leert
    ihn vor und nach der Messung. Wer hier einen zweiten Abruf ohne Reset
    einbaut, misst den ersten.
    """

    def __init__(self, frames_fn, *, gewitterpruefung_lief: bool) -> None:
        super().__init__()
        self._frames_fn = frames_fn
        self._gewitterpruefung_lief = gewitterpruefung_lief

    def _fetch_frames_with_fallback(self, lat, lon, elevation_m=None):
        frames = self._frames_fn(lat, lon)
        if not self._gewitterpruefung_lief:
            self._convective_checked = False
        return frames, "INCA"


def _radar(frames_fn, *, gewitterpruefung_lief: bool):
    return _RadarMitGewitterpruefung(
        frames_fn, gewitterpruefung_lief=gewitterpruefung_lief,
    )


def _gemessenes_ergebnis(trip, dienst, at: datetime):
    """Das ECHTE `NowcastResult` dieses Dienstes an den Koordinaten des Trips —
    die Zahlen und Merker, mit denen der Prueflauf spaeter entscheidet, nicht
    im Testkopf behauptete."""
    lat, lon = trip.stages[0].waypoints[0].lat, trip.stages[0].waypoints[0].lon
    with freeze_time(at):
        reset_shared_radar_cache_for_tests()
        ergebnis = dienst.get_nowcast(lat, lon)
        reset_shared_radar_cache_for_tests()
    return ergebnis


def _aufbau(uid: str, tag: str, *, briefing_mm: float | None = _BRIEFING_MM):
    """Nutzer (Premium-Profil fuer den vierten Kanal) + Trip mit allen vier
    Kanaelen, wahlweise mit Briefing-Anker.

    `briefing_mm=None` laesst den Anker WEG: `_briefing_announced` ist dann
    False und die Briefing-Unterdrueckung faellt als Entscheidungsgrund
    komplett aus (fuer AC-9, wo eine NACHGELAGERTE Stufe unterdruecken soll).
    """
    _clean_user(uid)
    _write_premium_profile(uid, _AT)
    with freeze_time(_AT):
        trip = _radar_trip(
            uid, f"trip-2050-s4a-b-{tag}", send_email=True, send_telegram=True,
            send_sms=True, send_premium_sms=True,
        )
        if briefing_mm is not None:
            _briefing_anker(uid, trip, briefing_mm)
    return trip


def _vorfaelle(uid: str, trip, seit: datetime) -> list:
    return alert_log.read_undelivered(
        uid, entity_id=trip.id, entity_type="trip", since=seit,
    )


def _gruende(uid: str, trip, seit: datetime) -> set:
    return {g for v in _vorfaelle(uid, trip, seit) for g in v.reasons}


def _lage_pruefen(trip, dienst, *, gewitterpruefung_lief: bool) -> None:
    """Die Testkonstruktion am ECHTEN Ergebnis nachmessen: der Lauf muss
    ausloesefaehig sein, darf die Ankuendigung aber NICHT ueberholen und darf
    nicht konvektiv sein — sonst entschiede eine andere Bedingung als die
    geprueften und der Test bewachte nichts."""
    from services import radar_service as radar_service_mod
    from services import trip_alert as trip_alert_mod

    ergebnis = _gemessenes_ergebnis(trip, dienst, _AT)
    assert ergebnis.convective_checked is gewitterpruefung_lief, (
        f"Testkonstruktion: `convective_checked` muss "
        f"{gewitterpruefung_lief!r} sein, gemessen "
        f"{ergebnis.convective_checked!r} — nur dieses eine Bit unterscheidet "
        f"AC-7 von AC-8."
    )
    assert ergebnis.is_convective is False, (
        f"Testkonstruktion: die Lage darf NICHT konvektiv sein, sonst greift "
        f"der bestehende Sicherheits-Override aus #883 und der Test misst ihn "
        f"statt der ausgefallenen Pruefung (gemessen "
        f"{ergebnis.is_convective!r})."
    )
    assert (
        ergebnis.onset_minutes is not None
        and ergebnis.onset_minutes <= radar_service_mod.RADAR_ONSET_THRESHOLD_MIN
    ), (
        f"Testkonstruktion: der Beginn muss innerhalb der Ausloeseschwelle "
        f"({radar_service_mod.RADAR_ONSET_THRESHOLD_MIN} Min) liegen, gemessen "
        f"{ergebnis.onset_minutes!r} — sonst haengt der Lauf schon am "
        f"Ausloese-Guard."
    )
    # Modul-Referenzen statt gebundener Kopien: eine Aenderung der Schwellen
    # soll hier auffallen, nicht stillschweigend mitwandern.
    faktor_schwelle = _BRIEFING_MM * trip_alert_mod._BRIEFING_OVERTAKE_FACTOR
    absolut_schwelle = trip_alert_mod._OVERTAKE_MIN_ABSOLUTE_MM
    assert ergebnis.window_precip_mm < max(faktor_schwelle, absolut_schwelle), (
        f"Testkonstruktion: die Lage darf die Ankuendigung von "
        f"{_BRIEFING_MM} mm NICHT ueberholen (gemessen "
        f"{ergebnis.window_precip_mm} mm gegen Faktor-Schwelle "
        f"{faktor_schwelle} mm / absolute Untergrenze {absolut_schwelle} mm) — "
        f"sonst waere der Alarm schon durch die Ueberholung erklaert und der "
        f"Test saehe die Gewitterpruefung nie."
    )


# ─────────────── AC-7: ausgefallene Pruefung traegt nicht mehr ──────────────


def test_ac7_ausgefallene_gewitterpruefung_traegt_die_briefing_unterdrueckung_nicht():
    """AC-7. GIVEN die Gewitterpruefung eines Radar-Abrufs ist nachweislich
    ausgefallen (`convective_checked=False`), WHEN derselbe Abruf OHNE den
    Ausfall die Briefing-Unterdrueckung ausgeloest haette
    (`is_convective=False` wuerde greifen, `_overtaking=False`), THEN traegt
    die Pruefung die Unterdrueckung nicht mehr und der Radar-Alarm wird nicht
    allein aus diesem Grund unterdrueckt.

    Nachgewiesen am TATSAECHLICHEN Versand ueber die vier Kanal-Abgriffe der
    Pruefstrecke, nicht nur am Zaehler: `triggered_count` zaehlt bereits den
    VERSUCH (Anti-Muster #656).

    Die Gegenprobe zu diesem Test ist AC-8 — dieselbe Lage mit
    DURCHGEFUEHRTER Pruefung muss weiterhin schweigen. Beide zusammen
    verhindern, dass aus „Ausfall zaehlt nicht als Entwarnung" ein „die
    Briefing-Unterdrueckung ist tot" wird.

    ROT heute: `trip_alert.py:1815` liest `result.convective_checked` nicht —
    der Lauf schweigt mit Grund `briefing_announced:1.0mm`."""
    uid = _uid("ac7")
    try:
        trip = _aufbau(uid, "ac7")
        dienst_kw = dict(gewitterpruefung_lief=False)
        _lage_pruefen(
            trip, _radar(_kurze_spitze(_LAGE_RATE_MM_H), **dienst_kw), **dienst_kw,
        )

        seit = _AT - timedelta(minutes=1)
        strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())
        lauf = strecke.lauf(
            at=_AT, zweig="radar", trip=trip,
            radar_service=_radar(_kurze_spitze(_LAGE_RATE_MM_H), **dienst_kw),
        )
        assert lauf.triggered_count == 1, (
            f"AC-7: eine NIE STATTGEFUNDENE Gewitterpruefung darf die "
            f"Briefing-Unterdrueckung nicht tragen — der Alarm muss raus. War "
            f"triggered_count={lauf.triggered_count}, protokollierte Gruende: "
            f"{_gruende(uid, trip, seit)!r}"
        )
        assert lauf.mail and lauf.telegram and lauf.sms and lauf.premium_sms, (
            f"AC-7: alle vier Kanaele muessen Inhalt tragen: mail={lauf.mail!r} "
            f"telegram={lauf.telegram!r} sms={lauf.sms!r} "
            f"premium_sms={lauf.premium_sms!r}"
        )
        assert not any(
            str(g).startswith("briefing_announced:") for g in _gruende(uid, trip, seit)
        ), (
            f"AC-7: der Lauf darf nicht an der Briefing-Ankuendigung haengen "
            f"bleiben. Protokolliert wurde: {_gruende(uid, trip, seit)!r}"
        )
    finally:
        _clean_user(uid)


# ──────────── AC-8: durchgefuehrte Pruefung unterdrueckt weiterhin ──────────


def test_ac8_durchgefuehrte_gewitterpruefung_ohne_gewitter_unterdrueckt_unveraendert():
    """AC-8 (GEGENPROBE, sichert AC-7 gegen Uebersteuerung; heute wie nachher
    GRUEN). GIVEN die Gewitterpruefung wurde DURCHGEFUEHRT und ergab kein
    Gewitter (`convective_checked=True, is_convective=False`), WHEN derselbe
    Radar-Alarmpfad geprueft wird, THEN greift die Briefing-Unterdrueckung
    unveraendert wie heute.

    Der reine Δ-Modell-Charakter bleibt erhalten: angekuendigter Regen, der
    die Ankuendigung nicht ueberholt, wird nicht noch einmal gemeldet. Wuerde
    die Umsetzung von AC-7 die Bedingung pauschal aufweichen, muss dieser Test
    rot werden.

    Die Stille wird nicht nur behauptet, sondern auf ihren GRUND festgenagelt:
    der Eintrag muss die Briefing-Ankuendigung nennen UND die
    ANGEKUENDIGTEN Millimeter tragen, die der Prueflauf selbst gelesen hat.
    Ohne diese Haelfte waere der Test auch dann gruen, wenn der Lauf aus einem
    ganz anderen Grund (Sperrzeit, fehlendes Segment) nie bis zur
    Briefing-Stufe kaeme."""
    uid = _uid("ac8")
    try:
        trip = _aufbau(uid, "ac8")
        dienst_kw = dict(gewitterpruefung_lief=True)
        _lage_pruefen(
            trip, _radar(_kurze_spitze(_LAGE_RATE_MM_H), **dienst_kw), **dienst_kw,
        )

        seit = _AT - timedelta(minutes=1)
        strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())
        lauf = strecke.lauf(
            at=_AT, zweig="radar", trip=trip,
            radar_service=_radar(_kurze_spitze(_LAGE_RATE_MM_H), **dienst_kw),
        )
        assert lauf.triggered_count == 0, (
            f"AC-8: eine DURCHGEFUEHRTE, negative Gewitterpruefung laesst die "
            f"Briefing-Unterdrueckung unveraendert greifen (war "
            f"{lauf.triggered_count})."
        )
        assert not (lauf.mail or lauf.telegram or lauf.sms or lauf.premium_sms), (
            f"AC-8: kein Kanal darf etwas ausliefern: mail={lauf.mail!r} "
            f"telegram={lauf.telegram!r} sms={lauf.sms!r} "
            f"premium_sms={lauf.premium_sms!r}"
        )
        gruende = _gruende(uid, trip, seit)
        assert any(str(g).startswith("briefing_announced:") for g in gruende), (
            f"AC-8: die Stille muss von der BRIEFING-Unterdrueckung kommen, "
            f"nicht von einer anderen Stufe. Protokolliert wurde: {gruende!r}"
        )
        assert _gelesene_briefing_werte(uid, trip, seit) == [_BRIEFING_MM], (
            f"AC-8: der Prueflauf muss GENAU die angekuendigten {_BRIEFING_MM} "
            f"mm gelesen haben, protokolliert wurde "
            f"{_gelesene_briefing_werte(uid, trip, seit)!r}"
        )
    finally:
        _clean_user(uid)


# ──────────── AC-9: der Ausfall steht im Protokolleintrag ───────────────────


def _aktives_segment_id(uid: str, trip):
    """Kennung des Segments, das `check_radar_alerts()` fuer diesen Trip
    waehlt — ueber DENSELBEN Aufloeser, nicht als Literal.

    Als `"1"` hingeschrieben bliebe die Bildungsstelle unbewacht: ein
    veraenderter Segment-Zuschnitt liesse den Guard-Eintrag ins Leere zeigen,
    der Guard griffe nicht — und der Test waere gruen, weil dann eben gar kein
    Eintrag entstuende (Muster aus #2050 S3b)."""
    from services.trip_alert import TripAlertService
    from services.trip_day import trip_local_today

    with freeze_time(_AT):
        jetzt = datetime.now(timezone.utc)
        dienst = TripAlertService(
            settings=_settings_all_channels(), throttle_hours=2, user_id=uid,
        )
        aufgeloest = dienst._resolve_alert_segment(
            trip, jetzt, trip_local_today(trip, jetzt),
        )
    assert aufgeloest is not None, (
        f"Vorbedingung: {trip.id!r} muss zur gestellten Uhr ein aktives "
        f"Segment haben."
    )
    return aufgeloest[0].segment_id


def _doppel_alarm_gedaechtnis_setzen(uid: str, trip) -> None:
    """Melde-Gedaechtnis so hinterlassen, wie ein soeben zugestellter Alarm es
    hinterlaesst — ueber den produktiven Speicher `AlertStateService.save()`,
    nicht per Handschrift in die Datei."""
    from services.alert_state import AlertStateService

    AlertStateService(uid).save(trip.id, {
        f"precip:{_aktives_segment_id(uid, trip)}": {
            "last_reported_value": 1.0,
            "reported_at": (_AT - timedelta(minutes=5)).isoformat(),
        },
    })


def _kennzeichen(vorfall) -> set:
    """Alle textlichen Merkmale, die die LESESEITE ueber diesen Vorfall
    ausgibt — ohne den Zeitstempel.

    BEWUSST breit ueber die Felder des DTOs gelesen (inklusive kuenftiger):
    WELCHES Feld den Ausfall traegt, ist laut Spec eine
    Implementierungsentscheidung der GREEN-Phase (neues optionales Feld an
    `append_suppressed_entry` vs. Suffix an einem bestehenden Feld, Vorbild
    `gate_reason=f"briefing_announced:{mm}mm"`). DASS er auf der Leseseite
    auftaucht, ist die Zusicherung — ein Merkmal, das nur in der rohen
    JSON-Datei stuende, erreichte weder Briefing noch Auswertung."""
    merkmale: set = set()
    for feld in fields(vorfall):
        if feld.name == "at":
            continue
        wert = getattr(vorfall, feld.name)
        if isinstance(wert, str):
            merkmale.add(wert)
        elif isinstance(wert, (tuple, list, set)):
            merkmale.update(str(teil) for teil in wert)
        elif wert is not None:
            merkmale.add(str(wert))
    return merkmale


def _guard_lauf(uid: str, trip, *, gewitterpruefung_lief: bool):
    """Ein Lauf, der am Doppel-Alarm-Guard unterdrueckt wird — einziger
    Unterschied zwischen den beiden Aufrufen ist `gewitterpruefung_lief`."""
    strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())
    return strecke.lauf(
        at=_AT, zweig="radar", trip=trip,
        radar_service=_radar(
            _dauerregen(_LAGE_RATE_MM_H),
            gewitterpruefung_lief=gewitterpruefung_lief,
        ),
    )


def test_ac9_der_ausfall_der_gewitterpruefung_steht_im_protokolleintrag():
    """AC-9. GIVEN ein Radar-Lauf mit ausgefallener Gewitterpruefung
    (`convective_checked=False`), WHEN dieser Lauf einen Protokolleintrag
    erzeugt, THEN ist der Ausfall der Gewitterpruefung IN DIESEM Eintrag
    festgehalten (Anforderung D-2: benannter Grund samt der Werte).

    Aufbau: KEIN Briefing-Anker (die Briefing-Stufe faellt als
    Entscheidungsgrund aus), dafuer ein scharf gestellter Doppel-Alarm-Guard —
    eine NACHGELAGERTE Stufe, die den Lauf anhaelt und dabei protokolliert.
    Nur so entsteht ueberhaupt ein Eintrag, in dem der Ausfall stehen kann.

    Gemessen wird als KONTRAST zweier Nutzer, deren Laeufe sich in GENAU EINEM
    Bit unterscheiden: beide werden am selben Guard unterdrueckt, beide
    bekommen einen Eintrag mit demselben Sperrgrund — der Eintrag des
    ausgefallenen Laufs muss auf der Leseseite ein Merkmal tragen, das der
    andere NICHT hat. Ein blosses „irgendetwas ist anders" reicht nicht: der
    Zeitstempel ist ausgenommen, und der bestehende Sperrgrund muss in BEIDEN
    Eintraegen unveraendert stehen bleiben (er darf nicht vom neuen Merkmal
    verdraengt werden).

    POSITIVKONTROLLE (dritter Nutzer): DIESELBE Lage OHNE scharfen Guard loest
    aus. Ohne sie bewiese der Eintrag nur, dass irgendetwas den Lauf anhielt —
    nicht, dass es der Guard war. Sie steht VOR der Kontrast-Zusicherung,
    damit sie in der RED-Phase tatsaechlich mitlaeuft.

    ROT heute: der Alarmpfad liest `convective_checked` nicht, beide Eintraege
    sind ununterscheidbar."""
    ohne, mit, frei = _uid("ac9-ohne"), _uid("ac9-mit"), _uid("ac9-frei")
    try:
        seit = _AT - timedelta(minutes=1)
        trip_ohne = _aufbau(ohne, "ac9-ohne", briefing_mm=None)
        trip_mit = _aufbau(mit, "ac9-mit", briefing_mm=None)
        _doppel_alarm_gedaechtnis_setzen(ohne, trip_ohne)
        _doppel_alarm_gedaechtnis_setzen(mit, trip_mit)

        lauf_ohne = _guard_lauf(ohne, trip_ohne, gewitterpruefung_lief=False)
        lauf_mit = _guard_lauf(mit, trip_mit, gewitterpruefung_lief=True)
        assert (lauf_ohne.triggered_count, lauf_mit.triggered_count) == (0, 0), (
            f"AC-9 Vorbedingung: beide Laeufe muessen am Doppel-Alarm-Guard "
            f"haengen bleiben (war {lauf_ohne.triggered_count} bzw. "
            f"{lauf_mit.triggered_count})."
        )

        # Positivkontrolle VOR der eigentlichen Zusicherung: sonst liefe sie
        # in der RED-Phase nie mit, und der Nachweis „der Guard ist es, der
        # anhaelt" faellt genau dann aus, wenn er gebraucht wird.
        trip_frei = _aufbau(frei, "ac9-frei", briefing_mm=None)
        lauf_frei = _guard_lauf(frei, trip_frei, gewitterpruefung_lief=False)
        assert lauf_frei.triggered_count == 1, (
            f"AC-9 Positivkontrolle: dieselbe Lage OHNE scharfen "
            f"Doppel-Alarm-Guard MUSS ausloesen — sonst sagt die Stille oben "
            f"nichts ueber den Guard aus (war {lauf_frei.triggered_count}, "
            f"Gruende: {_gruende(frei, trip_frei, seit)!r})."
        )

        vorfaelle_ohne = _vorfaelle(ohne, trip_ohne, seit)
        vorfaelle_mit = _vorfaelle(mit, trip_mit, seit)
        assert len(vorfaelle_ohne) == 1 and len(vorfaelle_mit) == 1, (
            f"AC-9 Vorbedingung: jeder Lauf muss GENAU EINEN Eintrag erzeugen, "
            f"gefunden {len(vorfaelle_ohne)} bzw. {len(vorfaelle_mit)}: "
            f"{vorfaelle_ohne!r} / {vorfaelle_mit!r}"
        )
        vorfall_ohne, vorfall_mit = vorfaelle_ohne[0], vorfaelle_mit[0]
        for vorfall in (vorfall_ohne, vorfall_mit):
            assert alert_log.REASON_DOUBLE_ALERT_GUARD in vorfall.reasons, (
                f"AC-9 Vorbedingung: der Eintrag muss weiterhin den Sperrgrund "
                f"{alert_log.REASON_DOUBLE_ALERT_GUARD!r} tragen — der Ausfall "
                f"der Gewitterpruefung kommt HINZU, er ersetzt den Grund "
                f"nicht. Gefunden: {sorted(vorfall.reasons)!r}"
            )

        zusatz = _kennzeichen(vorfall_ohne) - _kennzeichen(vorfall_mit)
        assert zusatz, (
            f"AC-9: der Eintrag des Laufs mit AUSGEFALLENER Gewitterpruefung "
            f"muss sich auf der Leseseite von dem mit durchgefuehrter Pruefung "
            f"unterscheiden — nachtraeglich muss belegbar sein, dass die "
            f"Entscheidung OHNE Gewitterinformation fiel. Beide Eintraege sind "
            f"heute ununterscheidbar:\nohne Pruefung: {vorfall_ohne!r}\nmit "
            f"Pruefung:  {vorfall_mit!r}"
        )
    finally:
        _clean_user(ohne)
        _clean_user(mit)
        _clean_user(frei)
