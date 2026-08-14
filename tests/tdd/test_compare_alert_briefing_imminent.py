"""TDD RED — Ortsvergleich (Aenderungsalarm): keine Doppel-Meldung kurz vor
einem geplanten Briefing (Issue #1594, AC-3, AC-7, AC-10, AC-13, AC-15).

SPEC:    docs/specs/modules/fix_1594_alarm_vorlauf_sperre.md
KONTEXT: docs/context/fix-1594-alarm-vorlauf-sperre.md

Einhaengepunkt: ``src/services/compare_alert.py:183`` (direkt nach der
Ruhezeit-Pruefung, VOR dem Wetterabruf). Gemessen wird an der Netz-Naht
``_detect_triggered_locations`` — sie liegt unmittelbar dahinter, „0 Aufrufe"
heisst also „vor dem Abruf gesperrt".

RED heute: es gibt keine Vorlauf-Sperre; jeder Lauf im Vorlauf-Fenster ruft ab.

═══════════════════════════════════════════════════════════════════════════
🔴 EIN BEFUND AUS DER RED-PHASE, DER AC-7 EINSCHRAENKT
═══════════════════════════════════════════════════════════════════════════

AC-7 nennt fuenf Gruende, aus denen ein Ortsvergleich „kein geplantes
Briefing" hat: ``schedule: "manual"``, ``paused_at``, ``archived_at``,
abgelaufenes ``end_date`` und abgeschalteter Slot.

Die ersten DREI davon sind ``compare_alert_guard.is_silenced()`` — und der
Riegel sitzt in BEIDEN Vergleichs-Alarmpfaden GANZ VORNE, vor Sperrzeit,
Tageslimit und Ruhezeit (``compare_alert.py:131``,
``compare_official_alert.py:96``). Gemessen am Ist-Code: ein solches Preset
loest heute schon NULL Alarme aus. Die neue Sperre kann dort gar keinen
Schaden anrichten, und ein Test kann „nicht durch die neue Sperre
unterdrueckt" nicht von „schon vorher stillgelegt" unterscheiden — beide
Ergebnisse sind null.

Echt gefaehrdet (und hier scharf geprueft) sind deshalb die beiden Gruende,
bei denen der Alarm HEUTE durchgeht: abgelaufenes ``end_date`` und
abgeschaltete Slots. Fuer die stillgelegten drei bleibt ein ausdruecklich
markierter Bestands-Anker: ihr Verhalten (null Alarme) darf sich nicht
aendern.

Mock-frei: echte Presets/Orte auf Platte, echter Dienst, echte
Zustandsdateien. Nur die Netz-Naht ist durch eine echte, zaehlende Unterklasse
ersetzt.

Pfadregel #1409: alle Pfade relativ zu DIESER Datei bzw. ueber
``app.loader.get_data_dir()``.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from tests.helpers.briefing_imminent_fixtures import (  # noqa: E402
    LOCATION_ZONE,
    briefing_anker_setzen,
    briefing_versand_gescheitert,
    clean_uid,
    compare_change_alert_run,
    compare_preset,
    fresh_uid,
    ortstag,
    protokoll_eintraege,
    ruhezeit_woanders,
    stunde_versetzt,
    write_location,
    write_presets,
    write_user_tier,
    zustand_schnappschuss,
)

PRESET = "cp-1594"


# NAH: Slot-Stunde = die Stunde, die in einer Stunde gilt — jetzt nicht
# faellig, in 60 Minuten schon. FERN: fuenf Stunden voraus.
def NAH() -> int:
    return stunde_versetzt(1, zone=LOCATION_ZONE)


def FERN() -> int:
    return stunde_versetzt(5, zone=LOCATION_ZONE)


@pytest.fixture
def nutzer():
    vergeben: list[str] = []

    def _neu(kennung: str, tier: str = "premium") -> str:
        user_id = fresh_uid(kennung)
        clean_uid(user_id)
        write_user_tier(user_id, tier)
        write_location(user_id)
        vergeben.append(user_id)
        return user_id

    yield _neu
    for user_id in vergeben:
        clean_uid(user_id)


def _lauf(user_id: str, **preset_kwargs) -> int:
    """Ein echter Vergleichs-Aenderungsalarm-Lauf; liefert die Zahl der
    Wetterabrufe (0 = vor dem Abruf gesperrt)."""
    preset_kwargs.setdefault("quiet", ruhezeit_woanders())
    write_presets(user_id, [compare_preset(PRESET, **preset_kwargs)])
    return compare_change_alert_run(user_id)


# ═══════════ AC-3 — Vergleichs-Aenderungsalarm im Vorlauf-Fenster ═══════════


def test_ac3_aenderungsalarm_schweigt_wenn_das_briefing_unmittelbar_bevorsteht(nutzer):
    """AC-3: Steht das naechste geplante Briefing des Ortsvergleichs in Kuerze
    an, geht der Wetter-Aenderungsalarm NICHT mehr als eigene Zusatz-Meldung
    raus.

    Der Gegen-Lauf mit fernem Slot schuetzt vor falschem Gruen: ohne ihn waere
    die erste Zusicherung auch dann erfuellt, wenn der Pfad aus einem ganz
    anderen Grund gar nicht erst losliefe (z.B. kein aufloesbarer Ort).

    ROT HEUTE: es gibt keine Vorlauf-Pruefung — beide Laeufe rufen ab.
    """
    abrufe_nah = _lauf(nutzer("ac3-nah"), morgen_stunde=NAH())
    abrufe_fern = _lauf(nutzer("ac3-fern"), morgen_stunde=FERN())

    assert abrufe_nah == 0, (
        f"Briefing steht in unter 60 Minuten an — der Vergleichs-Alarm muss "
        f"schweigen und darf kein Wetter abrufen, es waren {abrufe_nah} Abrufe."
    )
    assert abrufe_fern >= 1, (
        f"Ein Briefing in fuenf Stunden darf den Vergleichs-Alarm NICHT sperren "
        f"— es waren {abrufe_fern} Abrufe."
    )


def test_ac3_abend_slot_wirkt_wie_der_morgen_slot(nutzer):
    """AC-3 (Symmetrie innerhalb des Vergleichs): dieselbe Sperre greift, wenn
    der ABEND-Slot in Kuerze faellig ist und der Morgen-Slot abgeschaltet ist.

    Ohne diesen Fall waere eine Implementierung, die nur ``morning_time`` liest,
    formal AC-3-konform — und die Abend-Sperre existierte nur auf dem Papier.

    ROT HEUTE: keine Sperre, der Abruf laeuft an.
    """
    abrufe_abend = _lauf(
        nutzer("ac3-abend"), morgen_stunde=None, abend_stunde=NAH(),
    )
    abrufe_abend_fern = _lauf(
        nutzer("ac3-abend-fern"), morgen_stunde=None, abend_stunde=FERN(),
    )

    assert abrufe_abend == 0, (
        f"Faelliger Abend-Slot in unter 60 Minuten muss ebenso sperren wie der "
        f"Morgen-Slot ({abrufe_abend} Abrufe)."
    )
    assert abrufe_abend_fern >= 1, (
        f"Ferner Abend-Slot darf nicht sperren ({abrufe_abend_fern} Abrufe)."
    )


# ═══════════ AC-7 — kein Schweigen ohne Ersatz (Preset ohne Briefing) ═══════


def test_ac7_abgelaufenes_end_date_wird_nie_gesperrt(nutzer):
    """AC-7 (Risiko R1), Grund 1 von 2, die heute ueberhaupt Alarme ausloesen:
    Ein Preset, dessen ``end_date`` in der Vergangenheit liegt, bekommt kein
    geplantes Briefing mehr (``presets_due_for_hour`` stoppt es ab dem
    Folgetag) — sein Alarm muss trotzdem unveraendert durchgehen.

    ROT HEUTE ueber den Kontroll-Lauf: das gleich getaktete Preset OHNE
    ``end_date`` muesste gesperrt sein, ist es aber nicht.
    """
    abrufe_abgelaufen = _lauf(
        nutzer("ac7-enddate"), morgen_stunde=NAH(),
        end_date=ortstag(LOCATION_ZONE, -3).isoformat(),
    )
    abrufe_kontrolle = _lauf(nutzer("ac7-enddate-kontrolle"), morgen_stunde=NAH())

    assert abrufe_abgelaufen >= 1, (
        f"Preset mit abgelaufenem end_date hat kein Briefing mehr — sein Alarm "
        f"darf NIEMALS von der Vorlauf-Sperre verschluckt werden "
        f"({abrufe_abgelaufen} Abrufe)."
    )
    assert abrufe_kontrolle == 0, (
        f"Kontroll-Lauf: dasselbe Preset mit gueltigem Zeitraum muss gesperrt "
        f"sein — sonst misst dieser Test die Sperre gar nicht "
        f"({abrufe_kontrolle} Abrufe)."
    )


def test_ac7_abgeschaltete_slots_werden_nie_gesperrt(nutzer):
    """AC-7 (Risiko R1), Grund 2 von 2: Ein Preset mit abgeschaltetem
    Morgen- UND Abend-Slot hat kein geplantes Briefing — sein Alarm muss
    durchgehen. Zusaetzlich der schaerfere Halbfall: NUR der Morgen-Slot ist
    abgeschaltet, der Abend-Slot liegt fern — auch dann darf nichts gesperrt
    werden.

    ROT HEUTE ueber den Kontroll-Lauf.
    """
    abrufe_kein_slot = _lauf(
        nutzer("ac7-noslot"), morgen_stunde=None, abend_stunde=None,
    )
    abrufe_nur_abend_fern = _lauf(
        nutzer("ac7-halb"), morgen_stunde=None, abend_stunde=FERN(),
    )
    abrufe_kontrolle = _lauf(nutzer("ac7-noslot-kontrolle"), morgen_stunde=NAH())

    assert abrufe_kein_slot >= 1, (
        f"Preset ohne aktiven Slot hat kein Briefing — sein Alarm darf nicht "
        f"gesperrt werden ({abrufe_kein_slot} Abrufe)."
    )
    assert abrufe_nur_abend_fern >= 1, (
        f"Abgeschalteter Morgen-Slot zur NAH-Stunde darf nicht als faellig "
        f"gelten ({abrufe_nur_abend_fern} Abrufe)."
    )
    assert abrufe_kontrolle == 0, (
        f"Kontroll-Lauf: dasselbe Preset mit aktivem Morgen-Slot muss gesperrt "
        f"sein ({abrufe_kontrolle} Abrufe)."
    )


@pytest.mark.parametrize(
    "grund,kwargs",
    [
        ("schedule_manual", {"schedule": "manual"}),
        ("paused_at", {"paused_at": "2026-08-01T00:00:00Z"}),
        ("archived_at", {"archived_at": "2026-08-01T00:00:00Z"}),
    ],
)
def test_ac7_stillgelegte_presets_bleiben_wie_bisher_stumm(nutzer, grund, kwargs):
    """AC-7, die drei stillgelegten Gruende — BESTANDS-ANKER, kein Sperr-Test.

    🔴 Ausdruecklich markiert: dieser Test ist HEUTE gruen und bleibt es. Er
    kann die neue Sperre nicht messen, weil ``is_silenced()`` vor jeder
    Alarm-Stufe abbricht (``compare_alert.py:131``) — „nicht durch die neue
    Sperre unterdrueckt" und „schon vorher stillgelegt" sind beide null Abrufe.

    Sein Wert liegt woanders: er haelt fest, dass die neue Stufe die
    Reihenfolge NICHT umbaut. Wuerde sie vor ``is_silenced()`` einsortiert und
    dabei ein stillgelegtes Preset faelschlich als faellig lesen, entstuende
    genau hier ein Abruf, der heute nicht existiert.
    """
    abrufe = _lauf(nutzer(f"ac7-{grund}"), morgen_stunde=NAH(), **kwargs)

    assert abrufe == 0, (
        f"Stillgelegtes Preset ({grund}): der Stilllegungs-Riegel muss weiter "
        f"ganz vorne greifen, es waren {abrufe} Abrufe."
    )


# ═══════ AC-10 + AC-13 — kein State-Verbrauch, keine Protokollzeile ═════════


def test_ac10_und_ac13_gesperrter_lauf_hinterlaesst_keine_spur(nutzer):
    """AC-10 + AC-13: Ein durch die neue Sperre unterdrueckter
    Vergleichs-Aenderungsalarm veraendert weder Melde-Gedaechtnis noch
    Sperrzeit-Ablage noch Tageszaehler — und erzeugt keine Protokollzeile.

    Beide ACs zusammen, weil sie denselben Schnappschuss brauchen und dieselbe
    Zusicherung tragen: die Stufe LIEST nur.

    ROT HEUTE ueber die Voraussetzung (der Lauf ist heute nicht gesperrt).
    """
    uid = nutzer("ac10-13")
    write_presets(uid, [compare_preset(
        PRESET, morgen_stunde=NAH(), quiet=ruhezeit_woanders(),
    )])

    vorher = zustand_schnappschuss(uid, f"{PRESET}:loc-1594")
    protokoll_vorher = protokoll_eintraege(uid)
    abrufe = compare_change_alert_run(uid)
    nachher = zustand_schnappschuss(uid, f"{PRESET}:loc-1594")
    protokoll_nachher = protokoll_eintraege(uid)

    assert abrufe == 0, (
        f"Voraussetzung: der Lauf muss durch die Vorlauf-Sperre unterdrueckt "
        f"sein ({abrufe} Abrufe)."
    )
    assert nachher["melde_gedaechtnis"] == vorher["melde_gedaechtnis"], (
        f"Melde-Gedaechtnis veraendert: {vorher['melde_gedaechtnis']!r} -> "
        f"{nachher['melde_gedaechtnis']!r}"
    )
    assert nachher["sperrzeit"] == vorher["sperrzeit"], (
        f"Sperrzeit-Ablage veraendert: {vorher['sperrzeit']!r} -> "
        f"{nachher['sperrzeit']!r}"
    )
    assert nachher["tageszaehler"] == vorher["tageszaehler"], (
        f"Tageszaehler veraendert: {vorher['tageszaehler']!r} -> "
        f"{nachher['tageszaehler']!r}"
    )
    assert protokoll_nachher == protokoll_vorher, (
        f"Die Vorlauf-Sperre darf keine Protokollzeile erzeugen — "
        f"{len(protokoll_vorher)} -> {len(protokoll_nachher)} Eintraege."
    )


# ═════════════════════════ AC-15 — Mandantentrennung ════════════════════════


def test_ac15_sperre_wirkt_nur_auf_die_eigenen_daten_des_nutzers(nutzer):
    """AC-15: Zwei Nutzer, DIESELBE Preset-Kennung, verschiedene Slot-Zeiten.
    A steht im Vorlauf-Fenster SEINES Briefings und muss schweigen, B nicht.

    Eine Implementierung, die auf ``"default"`` zurueckfaellt oder die Kennung
    ohne Nutzer-Bezug nachschlaegt, faellt hier durch.

    ROT HEUTE: A meldet ebenfalls (keine Sperre).
    """
    abrufe_a = _lauf(nutzer("ac15-a"), morgen_stunde=NAH())
    abrufe_b = _lauf(nutzer("ac15-b"), morgen_stunde=FERN())

    assert abrufe_a == 0, (
        f"Nutzer A steht im Vorlauf-Fenster SEINES Briefings — sein Alarm muss "
        f"schweigen ({abrufe_a} Abrufe)."
    )
    assert abrufe_b >= 1, (
        f"Nutzer B hat sein Briefing erst in fuenf Stunden — die Sperre von A "
        f"darf ihn nicht mitnehmen ({abrufe_b} Abrufe)."
    )


# ════════ AC-5 — der VERSUCH beendet die Sperre, auch ohne Vermerk ══════════
#
# 🔴 Der Ortsvergleich hat KEINEN Idempotenz-Vermerk: ``presets_due_for_hour``
# prueft reine Stundengleichheit. Ein Preset bleibt seine ganze Slot-Stunde
# ueber „faellig" — auch nach dem gelungenen Versand. Beim Trip nimmt der
# Vermerk die Faelligkeit; hier traegt die Sperr-Beendigung ALLEIN der
# Briefing-Anker. Faellt sie aus, schweigt der Alarm bis zum Ende der
# Slot-Stunde, obwohl das Briefing schon durch ist.
#
# Uhr GESTELLT statt geerbt (dasselbe wie im Trip-Teil): der Slot muss
# bereits LAUFEN, und die uebrigen Tests dieser Datei koennen nur Slots in der
# Zukunft legen. `check_all_compare_presets()` holt sich den Zeitpunkt selbst,
# er ist kein Parameter — Einfrieren ist hier also zulaessig.
# Europe/Vienna liegt Mitte Maerz auf UTC+1: 08:20 UTC = 09:20 Ortszeit.
_JETZT_UTC = datetime(2026, 3, 15, 8, 20, tzinfo=timezone.utc)
_SLOT_STUNDE_ORTSZEIT = 9


@pytest.mark.parametrize(
    "ausgang, erwartet_abrufe",
    [("erfolgreich", True), ("gescheitert", True), ("ohne_versuch", False)],
)
def test_ac5_der_briefing_versuch_beendet_die_sperre(
    nutzer, ausgang, erwartet_abrufe,
):
    """AC-5 (Ortsvergleich): Die Sperre endet mit dem Versandversuch — ob er
    gelang oder scheiterte.

    Der Alarm-Lauf liegt 20 Minuten hinter dem Slot-Beginn, das Preset ist
    also weiterhin faellig (Stundengleichheit, kein Vermerk). Beide
    Versandausgaenge schreiben den Briefing-Anker: der gelungene ueber
    ``_anchor_and_reset()``, der gescheiterte ueber denselben Aufruf im
    Fehler-Zweig (#1629, ``scheduler_dispatch_service.py:561-566``). Genau
    deshalb darf der Anker die Sperre nicht AUSLOESEN, sondern muss sie
    BEENDEN.

    Der Kontrollfall ``ohne_versuch`` haelt die Grenze: ohne Anker steht das
    Briefing noch aus und die Meldung bleibt gesperrt.
    """
    from freezegun import freeze_time

    with freeze_time(_JETZT_UTC):
        user_id = nutzer(f"ac5-{ausgang}")
        if ausgang == "erfolgreich":
            briefing_anker_setzen(user_id, PRESET, "compare", vor_minuten=20)
        elif ausgang == "gescheitert":
            briefing_versand_gescheitert(
                user_id, PRESET, entity_type="compare", kind="vergleich",
                vor_minuten=20,
            )
        abrufe = _lauf(user_id, morgen_stunde=_SLOT_STUNDE_ORTSZEIT)

    if erwartet_abrufe:
        assert abrufe >= 1, (
            f"Das Briefing wurde vor 20 Minuten versucht ({ausgang}) — die "
            f"Sperre muss enden, es waren {abrufe} Abrufe. Ohne den Anker "
            f"schwiege der Alarm bis zum Ende der Slot-Stunde."
        )
    else:
        assert abrufe == 0, (
            f"Ohne Versandversuch steht das Briefing der laufenden Slot-Stunde "
            f"noch aus — der Alarm muss schweigen, es waren {abrufe} Abrufe."
        )
