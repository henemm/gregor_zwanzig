"""TDD RED — Ortsvergleich (amtliche Warnung): keine Doppel-Meldung kurz vor
einem geplanten Briefing (Issue #1594, AC-4, AC-9, AC-10, AC-13).

SPEC:    docs/specs/modules/fix_1594_alarm_vorlauf_sperre.md
KONTEXT: docs/context/fix-1594-alarm-vorlauf-sperre.md

Einhaengepunkt: ``src/services/compare_official_alert.py:126`` (direkt nach der
Ruhezeit-Pruefung, VOR ``_detect()``).

Diese Datei faehrt bewusst den ECHTEN Versandpfad mit einer echten, lokalen
Warnquelle (``FakeOfficialAlertSource`` — strukturelles Subtyping, kein Mock,
kein Netz) statt mit abgeklemmter Erkennung. Nur so entstehen heute
tatsaechlich Melde-Gedaechtnis, Sperrzeit, Tageszaehler und Protokoll-Eintrag —
und nur so lassen sich AC-10/AC-13 ueberhaupt messen. Ein Lauf mit
abgeklemmtem ``_detect()`` haette gar nichts zu buchen und waere fuer diese
beiden ACs strukturell blind.

═══════════════════════════════════════════════════════════════════════════
DIE #1233-ZUSICHERUNG, DIE HIER NICHT BRECHEN DARF
═══════════════════════════════════════════════════════════════════════════

``compare_official_alert.py:124-125`` sichert woertlich zu: eine waehrend der
Ruhezeit unterdrueckte Warnung schreibt KEINEN State, damit sie nach Ende der
Ruhezeit noch als „neu" zugestellt wird. Bewacht von
``tests/tdd/test_compare_official_alert.py:610``, das unveraendert gruen
bleiben MUSS.

Die neue Sperre haelt dieselbe Eigenschaft ein: sie liest nur. Fuer eine
Entitaet OHNE anstehendes Briefing greift sie gar nicht — die Sammel-
Zustellung nach Ruhezeit-Ende bleibt dort unveraendert (AC-9). Fuer eine
Entitaet MIT anstehendem Briefing verzoegert sie bis zum Briefing, das den
Anker setzt und das Melde-Gedaechtnis zuruecksetzt.

Zur Minutengenauigkeit: AC-4 spricht von „in 10 Minuten". Versandzeiten
existieren im Produktivsystem nur stundengenau (Go kappt sie beim Schreiben
UND beim Laden, ``internal/store/slot_hour_normalization.go``) — der
Vorlauf wirkt deshalb stundenbezogen. Die Tests stellen den Slot auf die
Stunde, die in einer Stunde gilt: jetzt nicht faellig, im Vorlauf-Fenster
schon.

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
    clean_uid,
    compare_official_alert_run,
    compare_official_versand_lauf,
    compare_preset,
    fresh_uid,
    protokoll_eintraege,
    ruhezeit_woanders,
    stunde_versetzt,
    write_location,
    write_presets,
    write_user_tier,
    zustand_schnappschuss,
)

PRESET = "cp-1594-amtlich"
ORT = "loc-1594"


def NAH() -> int:
    return stunde_versetzt(1, zone=LOCATION_ZONE)


def FERN() -> int:
    return stunde_versetzt(5, zone=LOCATION_ZONE)


def ruhezeit_jetzt(puffer_minuten: int = 20) -> tuple[str, str]:
    """Ruhezeit-Fenster in der ORTSZONE, das den jetzigen Zeitpunkt umschliesst
    — seit #1726 wertet ``is_quiet_hours()`` in der Zone des Gegenstands aus,
    das Fenster muss also in DERSELBEN Zone gebildet werden."""
    jetzt = datetime.now(timezone.utc).astimezone(LOCATION_ZONE)
    return (
        (jetzt - timedelta(minutes=puffer_minuten)).strftime("%H:%M"),
        (jetzt + timedelta(minutes=puffer_minuten)).strftime("%H:%M"),
    )


@pytest.fixture
def nutzer():
    vergeben: list[str] = []

    def _neu(kennung: str, tier: str = "premium") -> str:
        user_id = fresh_uid(kennung)
        clean_uid(user_id)
        write_user_tier(user_id, tier)
        write_location(user_id, ORT)
        vergeben.append(user_id)
        return user_id

    yield _neu
    for user_id in vergeben:
        clean_uid(user_id)


def _preset_schreiben(user_id: str, **kwargs) -> None:
    kwargs.setdefault("quiet", ruhezeit_woanders())
    write_presets(user_id, [compare_preset(PRESET, **kwargs)])


# ═════════════ AC-4 — amtliche Vergleichs-Warnung im Vorlauf-Fenster ════════


def test_ac4_amtliche_warnung_schweigt_wenn_das_briefing_unmittelbar_bevorsteht(nutzer):
    """AC-4: Steht das naechste geplante Briefing des Ortsvergleichs in Kuerze
    an, geht die amtliche Warnung NICHT mehr als eigene Zusatz-Meldung raus.

    Gemessen am echten Versandpfad (Rueckgabe des Dienstes UND Mail-Weg), nicht
    an einem Zaehler — hier interessiert die ZUSTELLUNG, nicht der Abruf.

    ROT HEUTE: es gibt keine Vorlauf-Pruefung, die Warnung geht raus.
    """
    nah = nutzer("ac4-nah")
    _preset_schreiben(nah, morgen_stunde=NAH())
    sent_nah, mails_nah = compare_official_versand_lauf(nah)

    fern = nutzer("ac4-fern")
    _preset_schreiben(fern, morgen_stunde=FERN())
    sent_fern, mails_fern = compare_official_versand_lauf(fern)

    assert (sent_nah, mails_nah) == (0, []), (
        f"Briefing steht in unter 60 Minuten an — die amtliche Warnung darf "
        f"nicht als eigene Meldung rausgehen: sent={sent_nah}, "
        f"Mails={len(mails_nah)}"
    )
    assert sent_fern >= 1 and len(mails_fern) >= 1, (
        f"Ein Briefing in fuenf Stunden darf die amtliche Warnung NICHT sperren "
        f"— sonst Schweigen ohne Ersatz: sent={sent_fern}, "
        f"Mails={len(mails_fern)}"
    )


def test_ac4_sperre_greift_vor_dem_warnungs_abruf(nutzer):
    """AC-4 (Ergaenzung, Invariante „vor jedem Abruf"): Ein gesperrter Lauf
    darf die Warnungs-Erkennung gar nicht erst erreichen — die neue Stufe sitzt
    laut Spec VOR ``_detect()``.

    Gemessen an der Netz-Naht selbst, nicht am Versand: eine Sperre, die erst
    NACH dem Abruf greift, waere fuer den Nutzer gleich, kostete aber weiter
    Laufzeit und Kontingent.

    ROT HEUTE: ``_detect`` wird gerufen.
    """
    nah = nutzer("ac4-abruf-nah")
    _preset_schreiben(nah, morgen_stunde=NAH())
    abrufe_nah = compare_official_alert_run(nah)

    fern = nutzer("ac4-abruf-fern")
    _preset_schreiben(fern, morgen_stunde=FERN())
    abrufe_fern = compare_official_alert_run(fern)

    assert abrufe_nah == 0, (
        f"Die Sperre muss VOR der Warnungs-Erkennung greifen, es waren "
        f"{abrufe_nah} Aufrufe."
    )
    assert abrufe_fern >= 1, (
        f"Ohne anstehendes Briefing muss die Erkennung unveraendert laufen "
        f"({abrufe_fern} Aufrufe)."
    )


# ═══════ AC-9 — die #1233-Sammel-Zustellung bleibt fuer Entitaeten OHNE ═════
# ═══════        anstehendes Briefing vollstaendig erhalten                ═══


def test_ac9_ruhezeit_ende_stellt_ohne_anstehendes_briefing_weiter_zu(nutzer):
    """AC-9: Die bewusst gebaute #1233-Eigenschaft — waehrend der Ruhezeit
    unterdrueckte Warnungen brechen nach deren Ende gesammelt los — bleibt fuer
    Entitaeten OHNE anstehendes Briefing UNVERAENDERT.

    Zwei Runden mit demselben Preset und derselben Warnung:
      Runde 1 — Ruhezeit umschliesst jetzt  -> keine Zustellung, KEIN State.
      Runde 2 — Ruhezeit liegt woanders     -> Zustellung (die Warnung gilt
                                               weiterhin als „neu").

    Und die Gegenprobe im selben Test: dasselbe Preset MIT Briefing im
    Vorlauf-Fenster bleibt in Runde 2 still — dort wird die Warnung nicht
    verschluckt, sondern vom Briefing Minuten spaeter mitgetragen.

    Ohne die Gegenprobe waere dieser Test heute gruen und bewiese nichts.

    ROT HEUTE: die zweite Haelfte (Preset mit Briefing) stellt zu.
    """
    ohne = nutzer("ac9-ohne")
    _preset_schreiben(
        ohne, morgen_stunde=None, abend_stunde=None, quiet=ruhezeit_jetzt(),
    )
    sent_ruhe, mails_ruhe = compare_official_versand_lauf(ohne)
    zustand_ruhe = zustand_schnappschuss(ohne, f"{PRESET}:{ORT}")

    _preset_schreiben(ohne, morgen_stunde=None, abend_stunde=None)
    sent_wach, mails_wach = compare_official_versand_lauf(ohne)

    mit = nutzer("ac9-mit")
    _preset_schreiben(mit, morgen_stunde=NAH(), quiet=ruhezeit_jetzt())
    compare_official_versand_lauf(mit)
    _preset_schreiben(mit, morgen_stunde=NAH())
    sent_mit, mails_mit = compare_official_versand_lauf(mit)

    assert (sent_ruhe, mails_ruhe) == (0, []), (
        f"Runde 1: die Ruhezeit muss die Warnung unterdruecken: "
        f"sent={sent_ruhe}, Mails={len(mails_ruhe)}"
    )
    assert not any(
        k.startswith("official_alert:") for k in zustand_ruhe["melde_gedaechtnis"]
    ), (
        f"#1233: eine waehrend der Ruhezeit unterdrueckte Warnung darf KEINEN "
        f"State schreiben, sonst wird sie nach Ende der Ruhezeit als 'schon "
        f"gemeldet' verschluckt: {zustand_ruhe['melde_gedaechtnis']!r}"
    )
    assert sent_wach >= 1 and len(mails_wach) >= 1, (
        f"Runde 2 ohne anstehendes Briefing: die Warnung MUSS nach Ende der "
        f"Ruhezeit gesammelt zugestellt werden — die neue Sperre darf hier gar "
        f"nicht greifen: sent={sent_wach}, Mails={len(mails_wach)}"
    )
    assert (sent_mit, mails_mit) == (0, []), (
        f"Gegenprobe: dasselbe Preset MIT Briefing im Vorlauf-Fenster muss "
        f"still bleiben — die Warnung kommt Minuten spaeter im Briefing an: "
        f"sent={sent_mit}, Mails={len(mails_mit)}"
    )


# ═══════ AC-10 + AC-13 — kein State-Verbrauch, keine Protokollzeile ════════


def test_ac10_und_ac13_gesperrter_lauf_hinterlaesst_keine_spur(nutzer):
    """AC-10 (Risiko R4) + AC-13: Eine durch die neue Sperre unterdrueckte
    amtliche Vergleichs-Warnung veraendert weder Melde-Gedaechtnis noch
    Sperrzeit-Ablage noch Tageszaehler — und erzeugt keine Protokollzeile.

    Der Lauf ist bewusst der ECHTE Versandpfad: heute schreibt er alle vier
    Spuren (``compare_official_alert.py`` bucht State, Sperrzeit, Tageszaehler
    und Protokoll nach dem Versand). Damit ist dieser Test heute aus dem
    RICHTIGEN Grund rot — nicht bloss mangels Gelegenheit zu buchen.
    """
    uid = nutzer("ac10-13")
    _preset_schreiben(uid, morgen_stunde=NAH())

    vorher = zustand_schnappschuss(uid, f"{PRESET}:{ORT}")
    protokoll_vorher = protokoll_eintraege(uid)
    sent, mails = compare_official_versand_lauf(uid)
    nachher = zustand_schnappschuss(uid, f"{PRESET}:{ORT}")
    protokoll_nachher = protokoll_eintraege(uid)

    assert (sent, mails) == (0, []), (
        f"Voraussetzung: der Lauf muss durch die Vorlauf-Sperre unterdrueckt "
        f"sein: sent={sent}, Mails={len(mails)}"
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
        f"{len(protokoll_vorher)} -> {len(protokoll_nachher)} Eintraege, neu: "
        f"{protokoll_nachher[len(protokoll_vorher):]!r}"
    )
