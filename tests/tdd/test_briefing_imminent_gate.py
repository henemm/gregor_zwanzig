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


# ═════════════════════════ AC-5 — Nachlauf-Fenster ══════════════════════════


def test_ac5_kurz_nach_einem_briefing_wird_gesperrt(nutzer):
    """AC-5: Ist das letzte Briefing dieser Entitaet nachweislich vor wenigen
    Minuten rausgegangen, wird eine Meldung ebenfalls nicht mehr als eigene
    Nachricht verschickt — der gemessene 13.08.-Fall (Alarm zwei Minuten NACH
    dem Briefing).

    Der Nachlauf haengt an der TATSACHE „ein Briefing ist raus"
    (``alert_briefing_anchor.last_briefing_at``), nicht an einer
    Uhrzeit-Rechnung: scheitert der Versand, wird der Anker gar nicht erst
    fortgeschrieben und die Sperre greift zu Recht nicht.

    Das Faelligkeits-Praedikat sagt hier durchgehend „nein" — die Sperre darf
    also allein aus dem Nachlauf entstehen.

    ROT HEUTE: ``services.alert_gate.check_briefing_imminent`` existiert nicht
    (ImportError).
    """
    uid = nutzer("ac5")
    _anker(uid, vor_minuten=5)

    assert _sperre(uid, NIE_FAELLIG()) is True, (
        "Ein Briefing, das vor fuenf Minuten rausging, muss die nachfolgende "
        "Meldung im Nachlauf-Fenster sperren."
    )


def test_ac5_ohne_jedes_briefing_wird_nicht_gesperrt(nutzer):
    """AC-5 (Gegenprobe): Gab es fuer diese Entitaet noch nie ein Briefing
    (Bestandsnutzer, erster Lauf nach der Auslieferung), liefert
    ``last_briefing_at()`` ``None`` — und die Sperre darf daraus NICHT „gerade
    rausgegangen" machen.

    Ohne diese Haelfte waere eine Implementierung, die bei fehlendem Anker
    pauschal sperrt, formal AC-5-konform und legte jede Bestandstour still.

    ROT HEUTE: ImportError.
    """
    uid = nutzer("ac5-ohne")

    assert _sperre(uid, NIE_FAELLIG()) is False, (
        "Ohne jeden Briefing-Anker darf nichts gesperrt werden."
    )


# ═══════════════════ AC-6 — Fenstergrenzen in beide Richtungen ══════════════


def test_ac6_ausserhalb_beider_fenster_wird_regulaer_verschickt(nutzer):
    """AC-6: Naechstes Briefing weiter als 60 Minuten entfernt UND letztes
    laenger als 15 Minuten her — die Meldung geht wie bisher regulaer raus.

    ROT HEUTE: ImportError.
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


def test_ac6_vorlauf_grenze_60_minuten(nutzer):
    """AC-6 (Grenze des Vorlaufs): Ein Briefing 59 Minuten voraus sperrt, eines
    75 Minuten voraus nicht. Damit ist die PO-Entscheidung „60 Minuten" als
    Verhalten gemessen — nicht als Konstante abgelesen.

    Der gemessene Anlassfall lag genau hier: Alarme um 04:00 und 04:45 UTC
    gegen ein Briefing um 05:00. Ein 15-Minuten-Vorlauf haette die 04:00-Faelle
    nicht gefangen.

    ROT HEUTE: ImportError.
    """
    uid = nutzer("ac6-vorlauf")
    knapp_drin = Faelligkeit(
        FEST + timedelta(minutes=55), FEST + timedelta(minutes=59),
    )
    knapp_draussen = Faelligkeit(
        FEST + timedelta(minutes=70), FEST + timedelta(minutes=80),
    )

    assert _sperre(uid, knapp_drin) is True, (
        "Ein Briefing 55–59 Minuten voraus liegt im Vorlauf-Fenster und muss "
        "sperren."
    )
    assert _sperre(uid, knapp_draussen) is False, (
        "Ein Briefing 70–80 Minuten voraus liegt ausserhalb — hier darf nicht "
        "gesperrt werden, sonst schweigt der Alarm ohne zeitnahen Ersatz."
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


def test_ac6_nachlauf_grenze_15_minuten(nutzer):
    """AC-6 (Grenze des Nachlaufs, Risiko R6): Ein Briefing vor 14 Minuten
    sperrt, eines vor 25 Minuten nicht. Ohne diesen Deckel bliebe die Sperre
    wirksam, obwohl das Briefing laengst durch ist — ein Meldeloch ohne Grenze.

    Zwei getrennte Nutzer, damit der Anker des einen den anderen nicht faerbt
    (er wird pro Nutzerverzeichnis gefuehrt).

    ROT HEUTE: ImportError.
    """
    drin, draussen = nutzer("ac6-nach-drin"), nutzer("ac6-nach-draussen")
    _anker(drin, vor_minuten=14)
    _anker(draussen, vor_minuten=25)

    assert _sperre(drin, NIE_FAELLIG()) is True, (
        "Ein Briefing vor 14 Minuten liegt im Nachlauf-Fenster und muss sperren."
    )
    assert _sperre(draussen, NIE_FAELLIG()) is False, (
        "Ein Briefing vor 25 Minuten liegt ausserhalb — die Sperre muss enden, "
        "sonst schweigt der Alarm unbegrenzt weiter."
    )


def test_ac6_anker_eines_fremden_gegenstands_sperrt_nicht(nutzer):
    """AC-6 (Trennschaerfe): Der Anker liegt je ``(entity_id, entity_type)``.
    Ein frisches Briefing einer ANDEREN Entitaet desselben Nutzers darf die
    Meldung hier nicht sperren.

    Ohne diesen Fall waere eine Implementierung, die den Anker nur nach
    ``user_id`` nachschlaegt, formal AC-5-konform — und legte bei jedem
    Briefing irgendeiner Tour saemtliche Alarme des Nutzers fuer 15 Minuten
    still.

    ROT HEUTE: ImportError.
    """
    from services.alert_briefing_anchor import record_briefing_sent

    uid = nutzer("ac6-fremd")
    record_briefing_sent(
        user_id=uid, entity_id="eine-ganz-andere-entitaet", entity_type="route",
        at=FEST - timedelta(minutes=3),
    )

    assert _sperre(uid, NIE_FAELLIG()) is False, (
        "Das Briefing einer fremden Entitaet darf diese hier nicht sperren."
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
