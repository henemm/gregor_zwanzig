"""TDD RED — Trip: keine Doppel-Meldung kurz vor einem geplanten Briefing
(Issue #1594, AC-1, AC-2, AC-8, AC-10, AC-11, AC-13, AC-15, AC-16).

SPEC:    docs/specs/modules/fix_1594_alarm_vorlauf_sperre.md
KONTEXT: docs/context/fix-1594-alarm-vorlauf-sperre.md

Beide Trip-Aufrufstellen laufen ueber DEN EINEN Adapter
``TripAlertService._is_quiet_hours`` (``trip_alert.py:680``): der
Aenderungsalarm bei ``:231``, die amtliche Warnung bei ``:1447``. Trotzdem
bekommt jede Aufrufstelle einen EIGENEN Nachweis — geteilter Code hat in
#1697 dreimal in Folge nichts ueber den jeweiligen Aufrufer bewiesen.

RED heute: es gibt keine Vorlauf-Sperre. Jeder Lauf im Vorlauf-Fenster
beschafft Wetter bzw. verschickt die amtliche Warnung, statt zu schweigen.

═══════════════════════════════════════════════════════════════════════════
GEKREUZTE PROBE — warum jeder Test ZWEI Laeufe fahrt
═══════════════════════════════════════════════════════════════════════════

Die Haelfte der ACs dieser Scheibe sind BEWAHRUNGS-Kriterien (AC-8, AC-10,
AC-11, AC-13, AC-16): sie beschreiben, was sich NICHT aendern darf. Solche
Zusicherungen sind ohne Gate trivial erfuellt und waeren als Einzel-Assertion
heute gruen — ein gruener TDD-RED-Test beweist nichts.

Deshalb faehrt jeder Test hier zusaetzlich einen KONTROLL-Lauf mit einer
Entitaet, deren Briefing im Vorlauf-Fenster liegt, und behauptet dessen
Unterdrueckung. Diese Haelfte ist heute rot. Nach der Umsetzung bewachen
beide Haelften gemeinsam die Grenze: gesperrt wird nur, wo ein Briefing
tatsaechlich folgt.

Mock-frei: echte Trips auf Platte, echte Dienste, echte Zustandsdateien. Nur
die NETZ-Naehte (``_fetch_fresh_weather``, Warnquellen-Registry) sind durch
echte Unterklassen bzw. echte Quellen ersetzt.

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
    TRIP_ZONE,
    briefing_anker_setzen,
    briefing_versand_gescheitert,
    clean_uid,
    fresh_uid,
    official_alert,
    protokoll_eintraege,
    read_trip_raw,
    render_trip_briefing_html,
    stunde_versetzt,
    trip_briefing_vermerk_setzen,
    trip_change_alert_run,
    trip_official_alert_run,
    write_trip,
    write_user_tier,
    zustand_schnappschuss,
)

# Ortsstunden des Trips (Atlantic/Reykjavik, ganzjaehrig UTC+0 — Ortstag und
# Weltzeittag fallen nie auseinander).
#
# NAH: Briefing-Stunde = die Stunde, die in einer Stunde gilt. JETZT ist der
# Trip damit NICHT faellig, in 60 Minuten schon — genau der Vorlauf-Fall.
# FERN: fuenf Stunden voraus; auch bei ``now + 60 min`` nicht faellig, und
# ausserhalb des 3-Stunden-Nachholfensters des Trip-Schedulers.
def NAH() -> int:
    return stunde_versetzt(1, zone=TRIP_ZONE)


def FERN() -> int:
    return stunde_versetzt(5, zone=TRIP_ZONE)


def ABEND_WEG() -> int:
    """Abend-Slot weit genug weg, dass er in keinem Fall mit hineinspielt."""
    return stunde_versetzt(9, zone=TRIP_ZONE)


@pytest.fixture
def nutzer():
    """Vergibt Nutzer-Kennungen und raeumt sie hinterher weg."""
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


# ═══════════════ AC-1 — Trip-Aenderungsalarm im Vorlauf-Fenster ═════════════


def test_ac1_aenderungsalarm_schweigt_wenn_das_briefing_unmittelbar_bevorsteht(nutzer):
    """AC-1: Steht das naechste geplante Briefing des Trips in Kuerze an, geht
    der Wetter-Aenderungsalarm NICHT mehr als eigene Zusatz-Meldung raus.

    Gemessen an der Netz-Naht ``_fetch_fresh_weather`` — die Sperre sitzt VOR
    dem Abruf, ein gesperrter Lauf kostet also kein Abruf-Kontingent. Der
    Gegen-Lauf mit fernem Briefing schuetzt vor falschem Gruen: ohne ihn waere
    die erste Zusicherung auch dann erfuellt, wenn der Pfad aus einem ganz
    anderen Grund gar nicht erst losliefe.

    ROT HEUTE: es gibt keine Vorlauf-Pruefung — beide Laeufe rufen ab.
    """
    nah = nutzer("ac1-nah")
    write_trip(nah, "t-ac1", morgen_stunde=NAH(), abend_stunde=ABEND_WEG())
    abrufe_nah = trip_change_alert_run(nah, "t-ac1")

    fern = nutzer("ac1-fern")
    write_trip(fern, "t-ac1", morgen_stunde=FERN(), abend_stunde=ABEND_WEG())
    abrufe_fern = trip_change_alert_run(fern, "t-ac1")

    assert abrufe_nah == 0, (
        f"Briefing steht in unter 60 Minuten an — der Aenderungsalarm muss "
        f"schweigen und darf kein Wetter abrufen, es waren {abrufe_nah} Abrufe."
    )
    assert abrufe_fern >= 1, (
        f"Ein Briefing in fuenf Stunden darf den Aenderungsalarm NICHT sperren "
        f"(sonst Schweigen ohne Ersatz) — es waren {abrufe_fern} Abrufe."
    )


# ══════════ AC-2 — amtliche Trip-Warnung im Vorlauf-Fenster (:1447) ═════════


def test_ac2_amtliche_warnung_schweigt_wenn_das_briefing_unmittelbar_bevorsteht(nutzer):
    """AC-2: Dieselbe Sperre wirkt auf die amtliche Warnung des Trips —
    ``_send_official_alert_only()`` meldet „nicht versendet" und der Mail-Weg
    bleibt unberuehrt.

    Eigenstaendiger Nachweis fuer DIESE Aufrufstelle, obwohl sie sich den
    Ruhezeit-Adapter mit AC-1 teilt.

    ROT HEUTE: die Warnung geht raus (Rueckgabe True, eine Mail).
    """
    nah = nutzer("ac2-nah")
    write_trip(nah, "t-ac2", morgen_stunde=NAH(), abend_stunde=ABEND_WEG())
    versendet_nah, mails_nah = trip_official_alert_run(nah, "t-ac2")

    fern = nutzer("ac2-fern")
    write_trip(fern, "t-ac2", morgen_stunde=FERN(), abend_stunde=ABEND_WEG())
    versendet_fern, mails_fern = trip_official_alert_run(fern, "t-ac2")

    assert (versendet_nah, mails_nah) == (False, []), (
        f"Briefing steht unmittelbar bevor — die amtliche Warnung darf nicht "
        f"als eigene Meldung rausgehen: versendet={versendet_nah}, "
        f"Mails={len(mails_nah)}"
    )
    assert versendet_fern is True and len(mails_fern) >= 1, (
        f"Ohne anstehendes Briefing muss die amtliche Warnung unveraendert "
        f"zugestellt werden: versendet={versendet_fern}, Mails={len(mails_fern)}"
    )


# ═══════════ AC-8 — kein Schweigen ohne Ersatz (Trip ohne Briefing) ═════════


def _trip_ohne_briefing(user_id: str, trip_id: str, grund: str) -> None:
    """Ein Trip, der zur NAH-Stunde faellig WAERE, es aber aus genau einem
    Grund nicht ist. Die Briefing-Stunde bleibt in allen Faellen NAH — nur so
    misst der Test den jeweiligen Aktiv-Filter und nicht die Uhrzeit."""
    gemeinsam = dict(morgen_stunde=NAH(), abend_stunde=ABEND_WEG())
    if grund == "paused_at":
        write_trip(user_id, trip_id, paused_at="2026-08-01T00:00:00Z", **gemeinsam)
    elif grund == "enabled_false":
        write_trip(user_id, trip_id, enabled=False, **gemeinsam)
    elif grund == "paused_until":
        write_trip(
            user_id, trip_id,
            paused_until=datetime.now(timezone.utc) + timedelta(hours=6), **gemeinsam,
        )
    elif grund == "keine_etappe":
        # Etappen erst in fuenf bzw. sechs Tagen -> am Zieltag keine Etappe.
        write_trip(user_id, trip_id, etappen_tage=(5, 6), **gemeinsam)
    else:  # pragma: no cover - Schutz gegen Tippfehler im Parameter
        raise AssertionError(f"unbekannter Grund: {grund!r}")


@pytest.mark.parametrize(
    "grund", ["paused_at", "enabled_false", "paused_until", "keine_etappe"],
)
def test_ac8_trip_ohne_geplantes_briefing_wird_nie_gesperrt(nutzer, grund):
    """AC-8 (Risiko R2): Ein Trip, fuer den gar kein Briefing geplant ist,
    darf NIEMALS durch die neue Sperre stillgelegt werden — es gaebe keinen
    Ersatz, die Meldung waere verschluckt statt ersetzt (Fehlerklasse
    #1555/#1584).

    Vier Gruende, vier Faelle — jeder einzeln, weil sie in
    ``_get_active_trips()`` an vier verschiedenen Stellen stehen und ein
    herausgeloestes Praedikat jeden davon einzeln vergessen kann.

    Beide Alarmarten werden geprueft: Aenderungsalarm UND amtliche Warnung.

    ROT HEUTE ueber den Kontroll-Lauf: der aktive Trip mit demselben
    Briefing-Zeitpunkt muesste gesperrt sein, ist es aber nicht.
    """
    ohne = nutzer(f"ac8-{grund}")
    _trip_ohne_briefing(ohne, "t-ac8", grund)
    abrufe_ohne = trip_change_alert_run(ohne, "t-ac8")
    versendet_ohne, mails_ohne = trip_official_alert_run(ohne, "t-ac8")

    kontrolle = nutzer(f"ac8-{grund}-kontrolle")
    write_trip(kontrolle, "t-ac8", morgen_stunde=NAH(), abend_stunde=ABEND_WEG())
    abrufe_kontrolle = trip_change_alert_run(kontrolle, "t-ac8")

    assert abrufe_ohne >= 1, (
        f"Trip ohne geplantes Briefing ({grund}): der Aenderungsalarm muss "
        f"unveraendert durchgehen, es waren {abrufe_ohne} Abrufe."
    )
    assert versendet_ohne is True and len(mails_ohne) >= 1, (
        f"Trip ohne geplantes Briefing ({grund}): die amtliche Warnung muss "
        f"unveraendert zugestellt werden: versendet={versendet_ohne}, "
        f"Mails={len(mails_ohne)}"
    )
    assert abrufe_kontrolle == 0, (
        "Kontroll-Lauf: derselbe Trip MIT geplantem Briefing zur selben Stunde "
        f"muss gesperrt sein — sonst misst dieser Test die Sperre gar nicht "
        f"(Abrufe={abrufe_kontrolle})."
    )


# ═══════ AC-10 + AC-13 — kein State-Verbrauch, keine Protokollzeile ═════════


def test_ac10_gesperrte_meldung_veraendert_keinen_zustand(nutzer):
    """AC-10 (Risiko R4, #1233-Analogie): Eine durch die neue Sperre
    unterdrueckte Meldung darf weder Melde-Gedaechtnis noch Sperrzeit-Ablage
    noch Tageszaehler beruehren.

    Gemessen am amtlichen Trip-Pfad, weil dort HEUTE tatsaechlich alle drei
    Buchungen entstehen (``trip_alert.py:1494-1499``) — ein Pfad, der heute
    ohnehin nichts schreibt, koennte die Zusicherung gar nicht pruefen.

    ROT HEUTE: der Lauf stellt zu und bucht alle drei.
    """
    uid = nutzer("ac10")
    write_trip(uid, "t-ac10", morgen_stunde=NAH(), abend_stunde=ABEND_WEG())

    vorher = zustand_schnappschuss(uid, "t-ac10")
    versendet, mails = trip_official_alert_run(uid, "t-ac10")
    nachher = zustand_schnappschuss(uid, "t-ac10")

    assert (versendet, mails) == (False, []), (
        f"Voraussetzung: der Lauf muss durch die Vorlauf-Sperre unterdrueckt "
        f"werden: versendet={versendet}, Mails={len(mails)}"
    )
    assert nachher["melde_gedaechtnis"] == vorher["melde_gedaechtnis"], (
        f"Melde-Gedaechtnis nach gesperrter Meldung veraendert: "
        f"{vorher['melde_gedaechtnis']!r} -> {nachher['melde_gedaechtnis']!r}"
    )
    assert nachher["sperrzeit"] == vorher["sperrzeit"], (
        f"Sperrzeit-Ablage nach gesperrter Meldung veraendert: "
        f"{vorher['sperrzeit']!r} -> {nachher['sperrzeit']!r}"
    )
    assert nachher["tageszaehler"] == vorher["tageszaehler"], (
        f"Tageszaehler nach gesperrter Meldung veraendert: "
        f"{vorher['tageszaehler']!r} -> {nachher['tageszaehler']!r}"
    )


def test_ac13_gesperrte_meldung_erzeugt_keinen_protokolleintrag(nutzer):
    """AC-13: Fuer eine durch die neue Sperre unterdrueckte Meldung entsteht
    KEIN neuer Eintrag im Alarm-Protokoll — weder in ``entries`` noch in
    ``not_delivered``. Der Delta-Wetter- und der amtliche Pfad bekommen
    ausdruecklich keine Unterdrueckungs-Protokollierung
    (``rework_1467_s3_nowcast.md`` AC-9), und die Meldung wird hier ohnehin
    ERSETZT, nicht verschluckt.

    ROT HEUTE: der Lauf stellt zu und schreibt eine ``entries``-Zeile.
    """
    uid = nutzer("ac13")
    write_trip(uid, "t-ac13", morgen_stunde=NAH(), abend_stunde=ABEND_WEG())

    vorher = protokoll_eintraege(uid)
    versendet, mails = trip_official_alert_run(uid, "t-ac13")
    nachher = protokoll_eintraege(uid)

    assert (versendet, mails) == (False, []), (
        f"Voraussetzung: der Lauf muss gesperrt sein: versendet={versendet}, "
        f"Mails={len(mails)}"
    )
    assert nachher == vorher, (
        f"Die Vorlauf-Sperre darf keine Protokollzeile erzeugen — "
        f"{len(vorher)} -> {len(nachher)} Eintraege, neu: "
        f"{nachher[len(vorher):]!r}"
    )


# ══════════════════ AC-11 — `skip_next` bleibt unverbraucht ════════════════


def test_ac11_sperrpruefung_verbraucht_skip_next_nicht(nutzer):
    """AC-11 (Risiko R3, der gefaehrlichste Fund der Analyse):
    ``_get_active_trips()`` konsumiert ``report_config.skip_next`` per
    Read-Modify-Write MIT ``save_trip()`` bei JEDEM Aufruf
    (``trip_report_scheduler.py:783-788``). Benutzt die neue Sperre diese
    Methode mit, verbraucht sie im 15-Minuten-Alarmtakt den Nutzerwunsch
    „naechstes Briefing ueberspringen", bevor der Briefing-Scheduler ihn je
    sieht — das Briefing kaeme trotzdem.

    Gelesen wird die PERSISTIERTE Datei, nicht das Objekt im Speicher: der
    Verbrauch passiert genau als Schreibvorgang, ein Speicher-Vergleich saehe
    ihn nicht.

    ROT HEUTE ueber die erste Zusicherung (kein Sperr-Lauf ohne Sperre).
    """
    uid = nutzer("ac11")
    write_trip(
        uid, "t-ac11", morgen_stunde=NAH(), abend_stunde=ABEND_WEG(), skip_next=True,
    )
    assert read_trip_raw(uid, "t-ac11")["report_config"]["skip_next"] is True, (
        "Aufbau-Nachweis: der Ausgangszustand muss skip_next=True tragen"
    )

    abrufe = trip_change_alert_run(uid, "t-ac11")
    versendet, _mails = trip_official_alert_run(uid, "t-ac11")

    assert (abrufe, versendet) == (0, False), (
        f"Voraussetzung: beide Trip-Alarmarten muessen im Vorlauf-Fenster "
        f"gesperrt sein (Abrufe={abrufe}, amtlich versendet={versendet})"
    )
    assert read_trip_raw(uid, "t-ac11")["report_config"]["skip_next"] is True, (
        "Die Vorlauf-Sperre hat den Nutzerwunsch 'naechstes Briefing "
        "ueberspringen' verbraucht — er steht nach dem Alarm-Lauf nicht mehr "
        "auf True. Ursache waere die Wiederverwendung von `_get_active_trips()` "
        "statt eines seiteneffektfreien Praedikats."
    )


# ═════════════════════════ AC-15 — Mandantentrennung ════════════════════════


def test_ac15_sperre_wirkt_nur_auf_die_eigenen_daten_des_nutzers(nutzer):
    """AC-15: Zwei Nutzer, DIESELBE Trip-Kennung, verschiedene Briefing-Zeiten.
    Die Sperre des einen darf den anderen nicht beruehren.

    Beide Richtungen in EINEM Test: A (Briefing in Kuerze) muss schweigen, B
    (Briefing in fuenf Stunden) muss melden. Eine Implementierung, die auf
    ``"default"`` zurueckfaellt oder die Kennung ohne Nutzer-Bezug nachschlaegt,
    faellt hier durch.

    ROT HEUTE: A meldet ebenfalls (keine Sperre).
    """
    a, b = nutzer("ac15-a"), nutzer("ac15-b")
    geteilte_kennung = "t-1594-geteilt"
    write_trip(a, geteilte_kennung, morgen_stunde=NAH(), abend_stunde=ABEND_WEG())
    write_trip(b, geteilte_kennung, morgen_stunde=FERN(), abend_stunde=ABEND_WEG())

    abrufe_a = trip_change_alert_run(a, geteilte_kennung)
    abrufe_b = trip_change_alert_run(b, geteilte_kennung)

    assert abrufe_a == 0, (
        f"Nutzer A steht im Vorlauf-Fenster SEINES Briefings — sein Alarm muss "
        f"schweigen ({abrufe_a} Abrufe)."
    )
    assert abrufe_b >= 1, (
        f"Nutzer B hat sein Briefing erst in fuenf Stunden — die Sperre von A "
        f"darf ihn nicht mitnehmen ({abrufe_b} Abrufe)."
    )


# ═══════ AC-16 — die tragende Rechtfertigung: ERSETZT, nicht verschluckt ════


def test_ac16_unterdrueckte_warnung_erscheint_im_folgenden_briefing(nutzer):
    """AC-16: Dieselbe amtliche Warnung, die als eigene Meldung unterdrueckt
    wurde, MUSS im unmittelbar folgenden Briefing erscheinen. Ohne diesen
    Nachweis waere die gesamte Scheibe auf einer ungeprueften Annahme gebaut —
    „die Meldung wird ersetzt" waere eine Behauptung, kein Befund.

    Zwei Schritte, EIN Test, damit die Ersetzung als Kette nachgewiesen ist:
    1. Der Standalone-Versand derselben Warnung wird im Vorlauf-Fenster
       unterdrueckt (rot heute).
    2. Dieselbe Warnung, dem Briefing-Renderer als ``seg.official_alerts``
       uebergeben, taucht im gerenderten Ergebnis auf — nachgewiesen gegen ein
       Briefing OHNE Warnung, damit die Zusicherung nicht durch einen
       beliebigen Textbaustein erfuellbar ist.

    Fuer den Wetter-Aenderungsalarm ist die Ersetzung baulich gegeben (das
    Briefing zeigt den vollstaendigen aktuellen Wetterstand) und wird nicht
    separat geprueft.
    """
    uid = nutzer("ac16")
    write_trip(uid, "t-ac16", morgen_stunde=NAH(), abend_stunde=ABEND_WEG())

    versendet, mails = trip_official_alert_run(uid, "t-ac16")
    assert (versendet, mails) == (False, []), (
        f"Schritt 1: die amtliche Warnung muss im Vorlauf-Fenster unterdrueckt "
        f"werden: versendet={versendet}, Mails={len(mails)}"
    )

    warnung = official_alert(level=3, hazard="wind", label="Sturmwarnung")
    mit_warnung = render_trip_briefing_html([warnung])
    ohne_warnung = render_trip_briefing_html([])

    assert warnung.label in mit_warnung, (
        "Schritt 2: die unterdrueckte Warnung muss im folgenden Briefing "
        f"erscheinen — {warnung.label!r} fehlt im gerenderten Briefing."
    )
    assert warnung.region_label in mit_warnung, (
        "Die Warnung muss mit ihrer Region erscheinen, nicht nur als nackter "
        f"Text — {warnung.region_label!r} fehlt."
    )
    assert warnung.label not in ohne_warnung, (
        "Gegenprobe: ohne Warnung darf der Text nicht im Briefing stehen — "
        "sonst waere die Zusicherung durch einen festen Textbaustein erfuellt "
        "und wuerde nichts ueber die Ersetzung aussagen."
    )


# ════════ AC-5 + R6 — der VERSUCH beendet die Sperre, nicht der Erfolg ══════
#
# 🔴 HIER wird die Uhr GESTELLT, nicht geerbt. Die uebrigen Tests dieser Datei
# legen die Briefing-Stunde relativ zur echten Uhr; das geht nur fuer Slots in
# der ZUKUNFT. Diese Faelle brauchen einen Slot, der bereits laeuft, und das
# Nachholfenster des Trip-Schedulers rechnet ohne Mitternachts-Umbruch
# (`stunde <= vor_ort.hour < stunde + 3`) — ein Lauf um 01:00 Ortszeit haette
# sonst still am fehlenden Fenster gemessen statt an der Sperre.
#
# Einfrieren ist hier erlaubt und noetig: `check_and_send_alerts()` holt sich
# den Zeitpunkt SELBST (`datetime.now(timezone.utc)`), er ist kein Parameter.
# Die Warnung aus
# `reference_freeze_time_macht_parameter_vs_systemuhr_unfalsifizierbar` gilt
# fuer die reine Gate-Funktion — dort wird deshalb NICHT eingefroren, sondern
# ein Zeitpunkt weit weg von der Systemuhr uebergeben
# (`test_briefing_imminent_gate.py`).
#
# Ortszone des Trips ist Atlantic/Reykjavik (ganzjaehrig UTC+0), Ortsstunde ist
# damit gleich der UTC-Stunde.
SLOT_STUNDE = 7


def _lauf_nach_briefing(user_id: str, *, ausgang: str, jetzt: datetime) -> int:
    """Ein Alarm-Lauf zum Zeitpunkt ``jetzt``, nachdem das Morgen-Briefing um
    ``SLOT_STUNDE`` den Ausgang ``ausgang`` genommen hat.

    ``"erfolgreich"``  Anker UND Idempotenz-Vermerk — der Trip ist damit nicht
                       mehr faellig.
    ``"gescheitert"``  Anker, ABER kein Vermerk (reserve-then-release) — der
                       Trip bleibt das ganze Nachholfenster ueber faellig.
    ``"ohne_versuch"`` weder noch — die Ausgangslage des gemeldeten
                       13.08.-Falls.

    Returns: Anzahl der Wetterabrufe (0 = gesperrt).
    """
    write_trip(
        user_id, "t-ac5", morgen_stunde=SLOT_STUNDE, abend_stunde=ABEND_WEG(),
    )
    slot_zeitpunkt = jetzt.replace(hour=SLOT_STUNDE, minute=0, second=30)
    vor_minuten = (jetzt - slot_zeitpunkt).total_seconds() / 60.0

    if ausgang == "erfolgreich":
        briefing_anker_setzen(user_id, "t-ac5", "trip", vor_minuten=vor_minuten)
        trip_briefing_vermerk_setzen(user_id, "t-ac5", slot="morning")
    elif ausgang == "gescheitert":
        briefing_versand_gescheitert(
            user_id, "t-ac5", entity_type="trip", kind="route",
            vor_minuten=vor_minuten,
        )
    elif ausgang != "ohne_versuch":  # pragma: no cover - Tippfehler-Schutz
        raise AssertionError(f"unbekannter Ausgang: {ausgang!r}")

    return trip_change_alert_run(user_id, "t-ac5")


@pytest.mark.parametrize(
    "ausgang, erwartet_abrufe",
    [("erfolgreich", True), ("gescheitert", True), ("ohne_versuch", False)],
)
def test_ac5_der_briefing_versuch_beendet_die_sperre(
    nutzer, ausgang, erwartet_abrufe,
):
    """AC-5: Die Sperre endet mit dem VERSUCH, nicht mit dem Erfolg.

    Der Alarm-Lauf liegt fuenf Minuten hinter der Briefing-Stunde — im
    Vorlauf-Fenster, das Briefing steht dort noch „an". Trotzdem muss die
    Meldung regulaer rausgehen, sobald ein Versandversuch stattgefunden hat:

    * ``erfolgreich`` — der Idempotenz-Vermerk nimmt dem Trip die Faelligkeit.
    * ``gescheitert``  — der Vermerk wurde zurueckgenommen, der Trip ist noch
      faellig; hier MUSS der Briefing-Anker die Sperre beenden. Genau das
      konnte die erste Fassung nicht: dort loeste der Anker die Sperre aus,
      statt sie zu beenden, und der Alarm schwieg fuer ein Briefing, das nie
      angekommen ist.
    * ``ohne_versuch`` — Kontrolle: ohne jeden Versuch muss gesperrt werden,
      sonst waere die ganze Scheibe wirkungslos und die beiden anderen Faelle
      trivial gruen.
    """
    from freezegun import freeze_time

    jetzt = datetime(2026, 3, 15, SLOT_STUNDE, 5, tzinfo=timezone.utc)
    with freeze_time(jetzt):
        uid = nutzer(f"ac5-{ausgang}")
        abrufe = _lauf_nach_briefing(uid, ausgang=ausgang, jetzt=jetzt)

    if erwartet_abrufe:
        assert abrufe >= 1, (
            f"Das Briefing wurde um {SLOT_STUNDE}:00 bereits versucht "
            f"({ausgang}) — die Sperre muss enden und der Alarm regulaer "
            f"pruefen, es waren {abrufe} Abrufe."
        )
    else:
        assert abrufe == 0, (
            f"Ohne Versandversuch steht das Briefing noch aus — der Alarm muss "
            f"schweigen, es waren {abrufe} Abrufe."
        )


@pytest.mark.parametrize(
    "ausgang, erwartet_abrufe", [("gescheitert", True), ("ohne_versuch", False)],
)
def test_r6_gescheitertes_briefing_sperrt_nicht_das_ganze_nachholfenster(
    nutzer, ausgang, erwartet_abrufe,
):
    """R6: Kein 4-Stunden-Schweif nach einem gescheiterten Briefing.

    Anker und Idempotenz-Vermerk laufen bei einem Fehlschlag auseinander: der
    Anker wird geschrieben (#1629), der Vermerk zurueckgenommen
    (reserve-then-release). Der Trip bleibt dadurch das volle
    ``NACHHOL_FENSTER_STUNDEN = 3`` ueber „faellig" — zusammen mit den 60
    Minuten Vorlauf waeren das bis zu VIER Stunden Alarmstille fuer ein
    Briefing, das nie ankam. In der GREEN-Phase real gemessen: Sperre von
    06:00 bis 09:59 Ortszeit am 07:00-Slot.

    Der Lauf liegt hier ZWEIEINHALB Stunden hinter der Briefing-Stunde, also
    tief im Nachholfenster. Der Kontrollfall ``ohne_versuch`` zeigt, dass die
    Sperre dort tatsaechlich noch greifen WUERDE — ohne ihn bewiese der erste
    Fall nur, dass irgendetwas anderes den Lauf durchlaesst.
    """
    from freezegun import freeze_time

    jetzt = datetime(2026, 3, 15, SLOT_STUNDE + 2, 30, tzinfo=timezone.utc)
    with freeze_time(jetzt):
        uid = nutzer(f"r6-{ausgang}")
        abrufe = _lauf_nach_briefing(uid, ausgang=ausgang, jetzt=jetzt)

    if erwartet_abrufe:
        assert abrufe >= 1, (
            f"Der Versand um {SLOT_STUNDE}:00 ist gescheitert und wurde damit "
            f"versucht — zweieinhalb Stunden spaeter darf der Alarm nicht mehr "
            f"gesperrt sein, es waren {abrufe} Abrufe (R6)."
        )
    else:
        assert abrufe == 0, (
            f"Kontrolle: ohne Versandversuch ist der Trip im Nachholfenster "
            f"weiterhin faellig und der Alarm gesperrt, es waren {abrufe} "
            f"Abrufe — ohne diese Haelfte misst der Schweif-Nachweis nichts."
        )
