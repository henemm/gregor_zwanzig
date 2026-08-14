"""TDD RED — Die Vorlauf-Sperre selbst: Fenstergrenzen, NowCast-Ausnahme und
Symmetrie (Issue #1594, AC-5, AC-6, AC-12, AC-13, AC-14).

SPEC:    docs/specs/modules/fix_1594_alarm_vorlauf_sperre.md
KONTEXT: docs/context/fix-1594-alarm-vorlauf-sperre.md

Heimat der neuen Funktion ist ``src/services/alert_gate.py``, klar getrennt von
``check_nowcast_gate()``. RED-Grund fuer AC-5/AC-6: ``check_briefing_imminent``
existiert dort nicht (ImportError).

═══════════════════════════════════════════════════════════════════════════
WARUM HIER KEINE UHR EINGEFROREN WIRD
═══════════════════════════════════════════════════════════════════════════

``check_briefing_imminent()`` bekommt seinen Zeitpunkt als PARAMETER. Wer in so
einem Fall zusaetzlich die Systemuhr anhaelt, macht genau die Frage
unfalsifizierbar, um die es geht: benutzt der Pruefling den uebergebenen
Zeitpunkt oder heimlich die Uhr des Servers?

Die Tests uebergeben deshalb einen FESTEN Zeitpunkt, der Monate von der echten
Uhr entfernt liegt, und legen Anker und Faelligkeits-Fenster relativ zu DIESEM
Zeitpunkt. Ein Rueckfall auf die Systemuhr laesst jede positive Zusicherung
umkippen — der Anker waere Monate alt, das Faelligkeits-Fenster laege in der
Vergangenheit.

Das Faelligkeits-Praedikat ist eine echte, aufzeichnende Funktion des Tests
(DI-Naht, wie ``frame_source`` beim Radar) — kein ``Mock()``: es rechnet ein
echtes Ergebnis aus dem uebergebenen Zeitpunkt.

Die beiden Verhaltens-Abschnitte (AC-12, AC-14) fahren dagegen die ECHTEN
Dienstpfade mit der echten Uhr und legen stattdessen die Briefing-Zeiten
relativ dazu — dort ist der Zeitpunkt kein Parameter, sondern wird intern
geholt.

Pfadregel #1409: alle Pfade relativ zu DIESER Datei bzw. ueber
``app.loader.get_data_dir()``.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from tests.helpers.briefing_imminent_fixtures import (  # noqa: E402
    LOCATION_ZONE,
    TRIP_ZONE,
    clean_uid,
    compare_change_alert_run,
    compare_preset,
    fresh_uid,
    protokoll_eintraege,
    ruhezeit_woanders,
    settings_email_only,
    stunde_versetzt,
    trip_change_alert_run,
    write_location,
    write_presets,
    write_trip,
    write_user_tier,
)
from tests.helpers.nowcast_gate_fixtures import (  # noqa: E402
    CountingFrameSource,
    reset_radar_cache,
)

# Weit weg von der echten Uhr: ein Rueckfall auf `datetime.now()` faellt damit
# in JEDER positiven Zusicherung dieser Datei auf.
FEST = datetime(2026, 3, 15, 10, 0, tzinfo=timezone.utc)

ENTITY = "e-1594-gate"


class Faelligkeit:
    """Echtes Faelligkeits-Praedikat (kein Mock): liefert True genau dann, wenn
    der uebergebene Zeitpunkt in einem festen Fenster liegt, und zeichnet alle
    Abfragen auf.

    Ein FENSTER statt einer Schwelle ist Absicht: bei einer Schwelle
    („faellig ab X") waere ein Pruefling, der heimlich die Systemuhr benutzt,
    trotzdem True — die Systemzeit liegt ja weit hinter X. Mit einem Fenster
    um den uebergebenen Zeitpunkt herum faellt genau dieser Fehler auf.
    """

    def __init__(self, von: datetime, bis: datetime) -> None:
        self.von, self.bis = von, bis
        self.gefragt: list[datetime] = []

    def __call__(self, moment: datetime) -> bool:
        self.gefragt.append(moment)
        return self.von <= moment <= self.bis


def NIE_FAELLIG() -> Faelligkeit:
    """Ein Fenster, das garantiert nie getroffen wird — weder vom uebergebenen
    Zeitpunkt noch von der Systemuhr."""
    return Faelligkeit(
        datetime(1999, 1, 1, tzinfo=timezone.utc),
        datetime(1999, 1, 2, tzinfo=timezone.utc),
    )


@pytest.fixture
def nutzer():
    vergeben: list[str] = []

    def _neu(kennung: str, tier: str = "premium") -> str:
        user_id = fresh_uid(kennung)
        clean_uid(user_id)
        write_user_tier(user_id, tier)
        vergeben.append(user_id)
        return user_id

    yield _neu
    for user_id in vergeben:
        clean_uid(user_id)


def _sperre(user_id: str, faelligkeit, **kwargs) -> bool:
    from services.alert_gate import check_briefing_imminent

    return check_briefing_imminent(
        user_id=user_id, entity_id=ENTITY, entity_type="route",
        now=FEST, zone=TRIP_ZONE, briefing_due_at=faelligkeit, **kwargs,
    )


def _anker(user_id: str, vor_minuten: float) -> None:
    """Briefing-Anker relativ zum FESTEN Zeitpunkt — nicht zur Systemuhr."""
    from services.alert_briefing_anchor import record_briefing_sent

    record_briefing_sent(
        user_id=user_id, entity_id=ENTITY, entity_type="route",
        at=FEST - timedelta(minutes=vor_minuten),
    )


# ══════════ AC-5 — der VERSUCH beendet die Sperre, nicht der Erfolg ═════════
#
# 🔴 Die erste Fassung hatte hier ein Nachlauf-Fenster: „letztes Briefing
# weniger als 15 Minuten her" SPERRTE. Das war falsch begruendet — der Anker
# wird auch bei gescheitertem Versand geschrieben (#1629), der Nachlauf
# schwieg also gerade dann, wenn nichts ankam, und machte sieben
# Bestandstests rot. Der Anker hat jetzt das UMGEKEHRTE Vorzeichen: er
# BEENDET die Sperre.

# Ein Faelligkeits-Fenster, das JETZT offen ist — der Zustand nach einem
# gescheiterten Versand: der Slot bleibt faellig (der Vermerk wurde
# zurueckgenommen), obwohl der Versuch stattgefunden hat.
def OFFENES_FENSTER() -> Faelligkeit:
    return Faelligkeit(
        FEST - timedelta(minutes=30), FEST + timedelta(minutes=30),
    )


def test_ac5_versuch_im_offenen_fenster_beendet_die_sperre(nutzer):
    """AC-5: Wurde das anstehende Briefing bereits versucht — ob zugestellt
    oder beim Versand gescheitert —, wird die Meldung regulaer verschickt.

    Das Faelligkeits-Fenster ist hier durchgehend offen, sagt also „das
    Briefing steht immer noch an". Genau so sieht ein GESCHEITERTER Versand
    aus: der Anker ist gesetzt (er steht in beiden Versandpfaden im
    Fehler-Zweig, #1629), der Idempotenz-Vermerk wurde zurueckgenommen.
    Allein daraus entsteht sonst der gemessene 4-Stunden-Schweif (R6).

    ROT vor der Korrektur: der Vorlauf-Zweig sperrt, der Anker konnte die
    Sperre nicht beenden — er loeste sie aus.
    """
    uid = nutzer("ac5-versucht")
    _anker(uid, vor_minuten=10)

    assert _sperre(uid, OFFENES_FENSTER()) is False, (
        "Das anstehende Briefing wurde vor zehn Minuten versucht — die Sperre "
        "muss damit enden, sonst schweigt der Alarm bis zu vier Stunden lang "
        "fuer ein Briefing, das nie angekommen ist."
    )


def test_ac5_ohne_versuch_bleibt_die_sperre_bestehen(nutzer):
    """AC-5 (Gegenprobe): Dieselbe Lage, aber ohne jeden Briefing-Anker — der
    gemeldete 13.08.-Fall (Alarm-Lauf zur Briefing-Minute selbst, noch kein
    Versuch). Hier MUSS gesperrt werden.

    Ohne diese Haelfte waere eine Implementierung, die nach Bedingung 1 immer
    durchlaesst, formal AC-5-konform — und der ganze Fix wirkungslos.
    """
    uid = nutzer("ac5-ohne")

    assert _sperre(uid, OFFENES_FENSTER()) is True, (
        "Ohne Briefing-Anker gab es noch keinen Versuch — die Meldung muss "
        "gesperrt bleiben, das Briefing ersetzt sie Minuten spaeter."
    )


def test_ac5_anker_vom_vortag_beendet_die_heutige_sperre_nicht(nutzer):
    """AC-5 (Zuordnung zum Slot): Ein Briefing-Versuch von GESTERN darf die
    heutige Sperre nicht beenden — sonst waere die Sperre ab dem zweiten
    Betriebstag jeder Tour dauerhaft wirkungslos, ohne dass irgendein Test
    umkippt.

    Eine Implementierung, die nur „gibt es ueberhaupt einen Anker?" fragt,
    faellt hier durch.
    """
    uid = nutzer("ac5-vortag")
    _anker(uid, vor_minuten=24 * 60)

    assert _sperre(uid, OFFENES_FENSTER()) is True, (
        "Der Anker liegt 24 Stunden zurueck und gehoert damit zum Briefing von "
        "gestern — er darf die heutige Sperre nicht beenden."
    )


def test_ac5_versuch_am_morgen_beendet_die_sperre_des_abends_nicht(nutzer):
    """AC-5 (Zuordnung zum SLOT, nicht zum Ortstag): Zwei Faelligkeits-Fenster
    am selben Tag — das Morgen-Fenster liegt zwei Stunden zurueck und ist
    abgearbeitet, das Abend-Fenster steht in 30 Minuten an. Der Anker des
    Morgen-Briefings darf die Sperre des ABEND-Briefings nicht beenden.

    Ohne diesen Fall waere eine Implementierung, die den Versuch nur gegen
    Mitternacht Ortszeit abgleicht („heute schon ein Briefing gehabt"),
    formal AC-5-konform — und liesse jeden Abend-Alarm durch, obwohl das
    Abend-Briefing Minuten spaeter dasselbe erzaehlt.
    """
    uid = nutzer("ac5-zwei-slots")
    _anker(uid, vor_minuten=120)

    class ZweiFenster:
        def __init__(self) -> None:
            self.gefragt: list[datetime] = []

        def __call__(self, moment: datetime) -> bool:
            self.gefragt.append(moment)
            morgens = (
                FEST - timedelta(minutes=125) <= moment
                <= FEST - timedelta(minutes=115)
            )
            abends = (
                FEST + timedelta(minutes=30) <= moment
                <= FEST + timedelta(minutes=90)
            )
            return morgens or abends

    assert _sperre(uid, ZweiFenster()) is True, (
        "Der Anker gehoert zum Morgen-Briefing von vor zwei Stunden — das "
        "Abend-Briefing in 30 Minuten wurde noch nicht versucht und muss "
        "gesperrt bleiben."
    )


# ═══════════════════ AC-6 — Fenstergrenzen in beide Richtungen ══════════════


def test_ac6_ausserhalb_des_vorlaufs_wird_regulaer_verschickt(nutzer):
    """AC-6: Naechstes Briefing weiter als 60 Minuten entfernt — die Meldung
    geht wie bisher regulaer raus.

    Der Anker vor 30 Minuten ist bewusst gesetzt: er darf hier weder sperren
    (das war der gestrichene Nachlauf) noch sonst etwas bewirken.
    """
    uid = nutzer("ac6")
    _anker(uid, vor_minuten=30)
    fern = Faelligkeit(FEST + timedelta(minutes=90), FEST + timedelta(minutes=120))

    assert _sperre(uid, fern) is False, (
        "Briefing in 90 Minuten, letztes vor 30 Minuten — hier darf die neue "
        "Sperre nicht greifen."
    )
    assert fern.gefragt, (
        "Das Faelligkeits-Praedikat wurde gar nicht befragt — die Sperre "
        "rechnet die Faelligkeit dann selbst nach, statt sie zu FRAGEN (das "
        "waere die vierte Fassung derselben Regel, s. Spec)."
    )


def test_ac6_vorlauf_grenze_genau_60_und_61_minuten(nutzer):
    """AC-6 (Grenze des Vorlaufs, auf die Minute): Ein Briefing GENAU 60
    Minuten voraus sperrt, eines GENAU 61 Minuten voraus nicht. Damit ist die
    PO-Entscheidung „60 Minuten" als Verhalten gemessen — nicht als Konstante
    abgelesen.

    Der gemessene Anlassfall lag genau hier: Alarme um 04:00 und 04:45 UTC
    gegen ein Briefing um 05:00. Ein 15-Minuten-Vorlauf haette die 04:00-Faelle
    nicht gefangen.

    Die Fenster beginnen exakt auf der Grenze und reichen nach HINTEN weg:
    ein Fenster, das die Grenze umschliesst, waere in beiden Faellen getroffen
    und wuerde nichts unterscheiden.
    """
    uid = nutzer("ac6-vorlauf")
    genau_60 = Faelligkeit(
        FEST + timedelta(minutes=60), FEST + timedelta(minutes=120),
    )
    genau_61 = Faelligkeit(
        FEST + timedelta(minutes=61), FEST + timedelta(minutes=121),
    )

    assert _sperre(uid, genau_60) is True, (
        "Ein Briefing genau 60 Minuten voraus liegt im Vorlauf-Fenster und "
        "muss sperren."
    )
    assert _sperre(uid, genau_61) is False, (
        "Ein Briefing genau 61 Minuten voraus liegt ausserhalb — hier darf "
        "nicht gesperrt werden, sonst schweigt der Alarm ohne zeitnahen Ersatz."
    )


def test_ac6_faelligkeit_genau_jetzt_sperrt_ebenfalls(nutzer):
    """AC-6 (untere Grenze): Ist das Briefing GENAU JETZT faellig, muss
    ebenfalls gesperrt werden.

    Eine Implementierung, die das Praedikat nur gegen ``now + Vorlauf``
    auswertet und nicht auch gegen ``now``, faellt hier durch — und liesse
    genau den Fall durch, in dem Alarm und Briefing in derselben Minute
    kollidieren.

    ROT HEUTE: ImportError.
    """
    uid = nutzer("ac6-jetzt")
    genau_jetzt = Faelligkeit(
        FEST - timedelta(minutes=5), FEST + timedelta(minutes=5),
    )

    assert _sperre(uid, genau_jetzt) is True, (
        "Ein zum Pruefzeitpunkt faelliges Briefing muss die Meldung sperren."
    )


def test_ac6_ohne_jede_faelligkeit_wird_nie_gesperrt(nutzer):
    """AC-6 (Gegenprobe zur gestrichenen Nachlauf-Haelfte): Steht ueberhaupt
    kein Briefing an, wird NIE gesperrt — auch nicht kurz nach einem gerade
    verschickten.

    Genau hier stand bis zur Spec-Korrektur das Gegenteil („letztes Briefing
    vor 5 Minuten ⇒ sperren"). Der Anker vor drei Minuten ist deshalb bewusst
    gesetzt: er ist der Ausloeser, der NICHT mehr ausloesen darf.
    """
    uid = nutzer("ac6-ohne-faelligkeit")
    _anker(uid, vor_minuten=3)

    assert _sperre(uid, NIE_FAELLIG()) is False, (
        "Ohne anstehendes Briefing gibt es keinen Ersatz fuer die Meldung — "
        "ein gerade verschicktes Briefing darf sie nicht sperren."
    )


def test_ac6_anker_eines_fremden_gegenstands_beendet_die_sperre_nicht(nutzer):
    """AC-6 (Trennschaerfe): Der Anker liegt je ``(entity_id, entity_type)``.
    Ein frisches Briefing einer ANDEREN Entitaet desselben Nutzers darf die
    Sperre hier nicht beenden — fuer DIESE Entitaet gab es noch keinen
    Versuch.

    Ohne diesen Fall waere eine Implementierung, die den Anker nur nach
    ``user_id`` nachschlaegt, formal AC-5-konform — und liesse bei jedem
    Briefing irgendeiner Tour saemtliche Doppel-Meldungen des Nutzers durch.
    """
    from services.alert_briefing_anchor import record_briefing_sent

    uid = nutzer("ac6-fremd")
    record_briefing_sent(
        user_id=uid, entity_id="eine-ganz-andere-entitaet", entity_type="route",
        at=FEST - timedelta(minutes=3),
    )

    assert _sperre(uid, OFFENES_FENSTER()) is True, (
        "Das Briefing einer fremden Entitaet sagt nichts darueber, ob DIESES "
        "Briefing schon versucht wurde — die Sperre muss bestehen bleiben."
    )


# ═════════ AC-12 + AC-13 — NowCast bleibt aussen vor, kein Protokoll ════════


def test_ac12_nowcast_kommt_durch_waehrend_der_aenderungsalarm_schweigt(nutzer):
    """AC-12 (Risiko R5): Steht ein Briefing unmittelbar bevor UND loest
    gleichzeitig der Regenradar aus UND liegt eine Wetteraenderung vor, dann
    wird der NowCast trotzdem zugestellt — nur der Aenderungsalarm schweigt.
    Die neue Sperre wirkt ausschliesslich auf Aenderungsalarme und amtliche
    Warnungen.

    Bewusst ein VERHALTENStest, kein Struktur-/Importtest: Wirkort ist „kommt
    der NowCast trotzdem durch?", nicht „welche Datei importiert was". Ein
    Strukturtest wuerde bei der Zusammenlegung der Alarmpfade (#1467 S4) selbst
    zum Kollateralschaden.

    AC-13 gleich mit gemessen: der gesperrte Aenderungsalarm darf keine
    Protokollzeile erzeugen. Der Radar-Lauf laeuft deshalb NACH dem
    Protokoll-Vergleich — er schreibt bei Zustellung selbst eine.

    ROT HEUTE: der Aenderungsalarm ruft Wetter ab (keine Sperre).
    """
    from services.radar_service import RadarNowcastService
    from services.trip_alert import TripAlertService

    uid = nutzer("ac12")
    write_trip(
        uid, "t-ac12",
        morgen_stunde=stunde_versetzt(1, zone=TRIP_ZONE),
        abend_stunde=stunde_versetzt(9, zone=TRIP_ZONE),
    )

    protokoll_vorher = protokoll_eintraege(uid)
    abrufe_aenderung = trip_change_alert_run(uid, "t-ac12")
    protokoll_nachher = protokoll_eintraege(uid)

    reset_radar_cache()
    quelle = CountingFrameSource(onset_minutes=8)
    nowcast_mails: list = []
    nowcast_sent = TripAlertService(
        settings=settings_email_only(), throttle_hours=2, user_id=uid,
        radar_service=RadarNowcastService(frame_source=quelle),
        mail_sink=lambda *a, **kw: nowcast_mails.append((a, kw)),
    ).check_radar_alerts()

    assert abrufe_aenderung == 0, (
        f"Der Aenderungsalarm muss im Vorlauf-Fenster schweigen "
        f"({abrufe_aenderung} Wetterabrufe)."
    )
    assert protokoll_nachher == protokoll_vorher, (
        f"AC-13: der gesperrte Aenderungsalarm darf keine Protokollzeile "
        f"erzeugen — {len(protokoll_vorher)} -> {len(protokoll_nachher)}."
    )
    assert nowcast_sent >= 1 and len(nowcast_mails) >= 1, (
        f"Der NowCast ist ausdruecklich von der Sperre ausgenommen und muss "
        f"trotz anstehendem Briefing zugestellt werden: sent={nowcast_sent}, "
        f"Mails={len(nowcast_mails)}"
    )
    assert quelle.call_count >= 1, (
        f"Voraussetzung: der Radar-Abruf muss ueberhaupt stattgefunden haben "
        f"({quelle.call_count} Abrufe) — sonst misst der NowCast-Nachweis "
        f"einen Pfad, der aus einem anderen Grund gar nicht erst losläuft."
    )


# ═════════════ AC-14 — Symmetrie: morgens wie abends, Trip wie ══════════════
# ═════════════          Ortsvergleich, in allen vier Kombinationen ══════════


def _trip_lauf(user_id: str, *, slot: str, nah: bool) -> int:
    """Ein Trip, dessen ``slot`` in Kuerze (``nah``) bzw. in fuenf Stunden
    faellig ist; der jeweils andere Slot liegt weit weg."""
    stunde = stunde_versetzt(1 if nah else 5, zone=TRIP_ZONE)
    weit = stunde_versetzt(9, zone=TRIP_ZONE)
    if slot == "morgen":
        write_trip(user_id, "t-ac14", morgen_stunde=stunde, abend_stunde=weit)
    else:
        write_trip(user_id, "t-ac14", morgen_stunde=weit, abend_stunde=stunde)
    return trip_change_alert_run(user_id, "t-ac14")


def _compare_lauf(user_id: str, *, slot: str, nah: bool) -> int:
    """Dasselbe fuer den Ortsvergleich; der jeweils andere Slot ist
    ABGESCHALTET (dort sind Morgen und Abend einzeln schaltbar)."""
    write_location(user_id)
    stunde = stunde_versetzt(1 if nah else 5, zone=LOCATION_ZONE)
    if slot == "morgen":
        preset = compare_preset(
            "cp-ac14", morgen_stunde=stunde, abend_stunde=None,
            quiet=ruhezeit_woanders(),
        )
    else:
        preset = compare_preset(
            "cp-ac14", morgen_stunde=None, abend_stunde=stunde,
            quiet=ruhezeit_woanders(),
        )
    write_presets(user_id, [preset])
    return compare_change_alert_run(user_id)


@pytest.mark.parametrize("art", ["trip", "vergleich"])
@pytest.mark.parametrize("slot", ["morgen", "abend"])
def test_ac14_sperre_wirkt_in_allen_vier_kombinationen_gleich(nutzer, art, slot):
    """AC-14: Dieselbe Fenster-Logik, vier Kombinationen — (Morgen, Abend) ×
    (Trip, Ortsvergleich). In allen vieren dasselbe Unterdrueckungsverhalten,
    keine versteckte Bevorzugung des Morgen- oder des Trip-Pfads.

    Die Abend-Redundanz tritt heute faktisch kaum auf (gemessen: 1 von 15
    Faellen seit 25.07.), weil vor dem Abend-Briefing keine Ruhezeit endet. Der
    symmetrische Zuschnitt bleibt trotzdem richtig: Ruhezeiten und
    Briefing-Zeiten sind pro Nutzer frei konfigurierbar, und genau ihre
    Verschiebung hat den Effekt binnen einer Woche entstehen lassen.

    Jede Kombination faehrt beide Richtungen: nahes Briefing muss sperren,
    fernes darf nicht. Ein Pfad, der aus einem ganz anderen Grund still ist,
    faellt an der zweiten Zusicherung auf.

    ROT HEUTE: keine Sperre in keiner der vier Kombinationen.
    """
    lauf = _trip_lauf if art == "trip" else _compare_lauf

    abrufe_nah = lauf(nutzer(f"ac14-{art}-{slot}-nah"), slot=slot, nah=True)
    abrufe_fern = lauf(nutzer(f"ac14-{art}-{slot}-fern"), slot=slot, nah=False)

    assert abrufe_nah == 0, (
        f"{art}/{slot}: ein Briefing in unter 60 Minuten muss den Alarm sperren "
        f"({abrufe_nah} Abrufe) — sonst wirkt die Sperre nicht in allen vier "
        f"Kombinationen gleich."
    )
    assert abrufe_fern >= 1, (
        f"{art}/{slot}: ein Briefing in fuenf Stunden darf NICHT sperren "
        f"({abrufe_fern} Abrufe)."
    )
