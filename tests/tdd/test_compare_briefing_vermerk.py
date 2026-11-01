"""TDD RED — Ortsvergleich-Briefing: Idempotenz-Vermerk je (preset_id, slot, ortstag).

SPEC: docs/specs/modules/fix_1777_compare_faelligkeit_und_idempotenz.md
      (Commit 1: AC-4, AC-6 .. AC-17, AC-21, AC-22, AC-23)
Vorbild Trip (#1725): tests/tdd/test_briefing_slot_idempotenz.py
Aufbau/Naehte: tests/tdd/_compare_slot_vermerk_fixtures.py (Begruendung dort)

🔴 Commit-Schnitt: Diese Datei muss schon nach COMMIT 1 gruen sein, in dem die
Faelligkeit noch Stundengleichheit (``==``) ist. Kein Test hier verlaesst sich
darauf, dass Ortsstunde H+1 regulaer faellig ist. „Erneut verarbeitet" wird
deshalb durch einen ZWEITEN Lauf in DERSELBEN Ortsstunde H gemessen (doppelter
Tick, Neustart, manueller Ausloeser) -- das liefert unter beiden Commits
dieselbe Antwort. Das Fenster selbst steht in
``test_compare_faelligkeit_fenster.py``.

────────────────────────────────────────────────────────────────────────────
Schnittstellen-Annahmen fuer GREEN (der Developer richtet sich danach)
────────────────────────────────────────────────────────────────────────────
1. Speicher: ``BriefingSlotStore(user_id, data_dir=None, *, filename=...,
   entity_type=..., id_key=...)``; Defaults = Trip (``briefing_slots.json``,
   ``"trip"``, ``"trip_id"``) byte-gleich. Compare-Instanz:
   ``filename="briefing_slots_compare.json", entity_type="compare",
   id_key="preset_id"``. Schema der Datei:
   ``{"entries": [{"preset_id", "slot", "local_day", "recorded_at", "outcome"}]}``
   -- ``slot`` ist ``"morning"``/``"evening"``, ``local_day`` der ORTSTAG DES
   LAUFS in der Preset-Zone (auch beim Abend-Slot, dessen Zieltag morgen ist).
   Sperr-Sidecar: ``briefing_slots_compare.json.lock``;
   ``briefing_slots.LOCK_TIMEOUT_SECONDS`` wird zur LAUFZEIT gelesen.
2. Rollout-Ableitung fuer Compare: Log-Eintraege mit
   ``entity_type == "compare"``, ``entity_id == preset_id``, ``kind == slot``,
   ``on_demand`` nicht ``True``, ``sent_at`` im Ortstag der PRESET-Zone; nur
   solange ``briefing_slots_compare.json`` fehlt. Trip-Eintraege (Typ
   ``"trip"`` oder ohne Typ) zaehlen fuer Compare NIE.
3. ``CompareDispatchStrategy.collect_due`` filtert mit
   ``is_recorded_or_claimed(..., moment=now_utc)`` (Pruefort = Wirkort);
   ``dispatch_one`` reicht ``now_utc`` an
   ``_dispatch_due_preset(..., tage_ab_ortstag=..., now_utc=...)`` durch.
   Beide Parameter sind OPTIONAL: ``now_utc: datetime | None = None``
   (Default = jetzt) -- Bestandsaufrufer ohne ``now_utc`` bleiben gueltig.
4. ``_dispatch_due_preset`` liefert den AUSGANG als String (``"sent"``,
   ``"no_channels"``, ``"no_weather"``, ``"channels_unreachable"``, ein
   unbekannter Code unveraendert) bzw. ``None``, wenn mangels Reservierung kein
   Versandversuch stattfand; eine sonstige Ausnahme fuehrt zu ``release`` und
   zaehlt als ``failed``. Zaehlung in ``dispatch_one``: ``sent`` -> sent,
   ``no_channels`` -> neutral, alles andere -> failed (Trip-Paritaet #2218).
5. ``no_weather`` im Cron: ``record_outcome`` UND Nachhol-Vermerk (#2587).
6. ``_catchup_verdict`` liest den Compare-Speicher: Ausgang ``sent`` -> drop;
   ``no_weather``/``no_channels`` -> NICHT drop.
7. Direktaufrufe von ``_dispatch_due_preset`` bzw. ``dispatch_one`` ohne
   ``now_utc`` (``test_compare_preset_send.py::_cron``,
   ``test_compare_briefing_nachholen.py`` test_ac11/test_f004,
   ``test_compare_anchor_target_date.py``) bleiben dank Default gueltig; dort
   wird nur der Rueckgabewert ``"sent"`` statt ``True`` erwartet.
8. ``DuePreset`` bleibt das Tripel ``(preset, target_date, tage_ab_ortstag)``
   (Bestandstests vergleichen gegen 3-Tupel); der Slot folgt aus dem Versatz
   (0 = ``morning``, 1 = ``evening``), der Ortstag des Schluessels aus
   ``now_utc`` in der Preset-Zone (EIN Schluessel-Helfer).
9. Der Compare-Speicher liegt im Nutzerordner (``get_data_dir(user_id)``
   wie beim Trip und bei ``pending_briefings.json``). Diese Tests laufen mit
   ``data_root == get_data_root()``; Bestandstests mit eigenem ``data_root``
   (test_issue_461/509/511/649) duerfen dadurch nicht kippen.

RED-Charakter je Test steht im Docstring:
``Fehlernachweis`` = misst den gemeldeten Defekt (heute rot);
``Mutations-Waechter`` = heute nur ueber eine Zusatz-Zusicherung rot, sein
Wert liegt in der Verfaelschung, die er nach GREEN faengt.
"""
from __future__ import annotations

import fcntl
import os
from datetime import date, datetime, timedelta, timezone

import pytest

from app.loader import get_data_dir, get_data_root
from services import briefing_slots
from tests.tdd._compare_slot_vermerk_fixtures import (  # noqa: F401  (Fixtures)
    COMPARE_SLOTS,
    INNSBRUCK,
    KORSIKA,
    NACHHOL_HINWEIS,
    PARIS,
    TRIP_SLOTS,
    WIEN,
    abgeschlossene_vermerke,
    briefing_log_schreiben,
    compare_log_eintrag,
    compare_vermerk,
    compare_vermerk_schluessel,
    compare_vermerk_schreiben,
    compare_vermerke,
    kette,
    kette_nutzer,
    lauf,
    nachhol_vermerk_schreiben,
    nachhol_vermerke,
    naht,
    nutzer,
    ohne_mail_to,
    ort_anlegen,
    utc_zu,
    vergleich_ablegen,
)

#: Ortstag ohne Zeitumstellung (Do 20.08.2026).
D = date(2026, 8, 20)
H = 7


def _paris_vergleich(uid: str, pid: str, **kw) -> str:
    ort_anlegen(uid, f"ort-{pid}", KORSIKA)
    return vergleich_ablegen(uid, pid, orte=[f"ort-{pid}"], **kw)


# ═══════════════════════════════ AC-4 ════════════════════════════════════════


def test_ac4_morgen_und_abend_auf_derselben_stunde_werden_beide_vermerkt(naht):
    """AC-4: Given Morgen- UND Abend-Slot auf 07:00 / When Ortsstunde 07
    erreicht wird / Then beide Slots werden unabhaengig versendet UND
    vermerkt; ein zweiter Lauf derselben Stunde sendet keinen der beiden.

    Gezaehlt werden VERSANDVERSUCHE: beide Slots fallen in DERSELBEN Sammlung
    an, der Vermerk des ersten entsteht erst beim Versand danach.

    RED-Charakter: Fehlernachweis — heute kein Vermerk, der zweite Lauf sendet
    beide Slots erneut. Nach GREEN rot bei: ``slot`` aus dem Schluessel
    entfernt (dann scheitert die Reservierung des zweiten Slots).
    """
    uid = nutzer()
    pid = _paris_vergleich(uid, "vgl-ac4", morgen="07:00:00", abend="07:00:00")

    lauf(uid, utc_zu(PARIS, D, H))

    assert sorted(naht.regulaer()) == [(pid, "evening"), (pid, "morning")], (
        f"Beide Slots muessen im ersten Lauf versendet werden: {naht.versuche}"
    )
    assert abgeschlossene_vermerke(uid) == {
        (pid, "morning", D.isoformat(), "sent"),
        (pid, "evening", D.isoformat(), "sent"),
    }, (
        "Beide Slots muessen getrennt vermerkt sein, Schluessel-Ortstag ist der "
        f"Tag des LAUFS (auch beim Abend-Slot): {compare_vermerke(uid)!r}"
    )

    lauf(uid, utc_zu(PARIS, D, H, 30))

    assert len(naht.regulaer()) == 2, (
        "Ein zweiter Lauf in derselben Ortsstunde darf keinen Slot erneut "
        f"versenden: {naht.versuche}"
    )


# ═══════════════════════════════ AC-6 ════════════════════════════════════════


def test_ac6_vermerk_des_vortags_blockiert_den_folgetag_nicht(naht):
    """AC-6: Given der Morgen-Slot ist an D vermerkt / When der Lauf an D+1
    zur Slot-Stunde stattfindet / Then ist der Vergleich erneut faellig.

    RED-Charakter: Fehlernachweis — heute sendet der Wiederholungslauf an D
    erneut und es gibt keinen Vermerk. Nach GREEN rot bei: ``ortstag`` aus dem
    Schluessel entfernt (dann verstummt D+1).
    """
    uid = nutzer()
    pid = _paris_vergleich(uid, "vgl-ac6")

    lauf(uid, utc_zu(PARIS, D, H))
    lauf(uid, utc_zu(PARIS, D, H, 30))
    lauf(uid, utc_zu(PARIS, D + timedelta(days=1), H))

    assert naht.regulaer() == [(pid, "morning"), (pid, "morning")], (
        "Erwartet je Ortstag genau einen Versand (D, D+1), der Wiederholungslauf "
        f"an D sendet nicht: {naht.versuche}"
    )
    assert abgeschlossene_vermerke(uid) == {
        (pid, "morning", D.isoformat(), "sent"),
        (pid, "morning", (D + timedelta(days=1)).isoformat(), "sent"),
    }, compare_vermerke(uid)


# ═══════════════════════════════ AC-7 ════════════════════════════════════════


def test_ac7_zwei_vergleiche_gleicher_zone_blockieren_einander_nicht(naht):
    """AC-7: Given zwei Vergleiche, gleiche Zone, gleiche Slot-Stunde / When
    die Ortsstunde erreicht wird / Then beide werden versendet und vermerkt;
    ein Wiederholungslauf sendet keinen.

    RED-Charakter: Fehlernachweis — heute kein Vermerk, Wiederholung sendet.
    Nach GREEN rot bei: ``preset_id`` aus dem Schluessel entfernt.
    """
    uid = nutzer()
    ort_anlegen(uid, "ort-paris", KORSIKA)
    vergleich_ablegen(uid, "vgl-ac7-a", orte=["ort-paris"])
    vergleich_ablegen(uid, "vgl-ac7-b", orte=["ort-paris"])

    lauf(uid, utc_zu(PARIS, D, H))
    lauf(uid, utc_zu(PARIS, D, H, 30))

    assert sorted(naht.regulaer()) == [("vgl-ac7-a", "morning"), ("vgl-ac7-b", "morning")], (
        f"Je Vergleich genau ein Versand: {naht.versuche}"
    )
    assert abgeschlossene_vermerke(uid) == {
        ("vgl-ac7-a", "morning", D.isoformat(), "sent"),
        ("vgl-ac7-b", "morning", D.isoformat(), "sent"),
    }, compare_vermerke(uid)


# ═══════════════════════════════ AC-8 ════════════════════════════════════════


def test_ac8_zwei_nutzer_gleiche_preset_id_fuehren_getrennte_vermerke(naht):
    """AC-8: Given zwei Nutzer mit je einem Vergleich GLEICHER Kennung / When
    der Lauf fuer beide laeuft / Then jeder fuehrt seinen Vermerk unter
    ``data/users/<uid>/briefing_slots_compare.json``; der eine blockiert den
    anderen nicht, und keiner liest den Vermerk des anderen.

    RED-Charakter: Fehlernachweis — heute keine Datei, Wiederholung sendet.
    Nach GREEN rot bei: Speicher unter festem Nutzer (``default``) oder
    Datei ausserhalb des Nutzerordners.
    """
    a, b = nutzer(), nutzer()
    for uid in (a, b):
        _paris_vergleich(uid, "vgl-geteilt")

    lauf(a, utc_zu(PARIS, D, H))
    assert not (get_data_dir(b) / COMPARE_SLOTS).exists(), (
        "Der Lauf von A darf keine Vermerk-Datei bei B anlegen"
    )
    lauf(b, utc_zu(PARIS, D, H))
    lauf(a, utc_zu(PARIS, D, H, 30))
    lauf(b, utc_zu(PARIS, D, H, 30))

    assert naht.regulaer(uid=a) == [("vgl-geteilt", "morning")], naht.versuche
    assert naht.regulaer(uid=b) == [("vgl-geteilt", "morning")], (
        f"Der Vermerk von A darf B nicht blockieren (und umgekehrt): {naht.versuche}"
    )
    for uid in (a, b):
        assert abgeschlossene_vermerke(uid) == {
            ("vgl-geteilt", "morning", D.isoformat(), "sent"),
        }, f"{uid}: {compare_vermerke(uid)!r}"
        assert len(compare_vermerke(uid)) == 1, (
            f"{uid}: genau der eigene Vermerk, kein fremder: {compare_vermerke(uid)!r}"
        )


# ═══════════════════════════════ AC-9 ════════════════════════════════════════


def test_ac9_rollout_log_eintrag_vom_ortstag_gilt_als_erledigt(naht):
    """AC-9: Given ``briefing_slots_compare.json`` fehlt (Rollout), aber
    ``briefing_log.json`` traegt fuer den Vergleich einen regulaeren
    Versand mit ``entity_type="compare"``, passender ``entity_id`` und
    Slot-Art, dessen ``sent_at`` im AKTUELLEN Ortstag der Preset-Zone liegt /
    When die Faelligkeit geprueft wird / Then wird nicht erneut versendet;
    ein Eintrag vom VORTAG zaehlt nicht.

    ``sent_at`` liegt bewusst um 01:30 Ortszeit (Paris, CEST) — das ist
    23:30 UTC des VORTAGS. Nur die Auswertung in der Preset-Zone erkennt den
    Eintrag als „heute".

    RED-Charakter: Fehlernachweis — heute gibt es keine Ableitung, es wird
    trotz Log-Eintrag erneut versendet. Nach GREEN rot bei: Ableitung
    entfernt, Ortstag aus UTC (``zone=None``), ``kind``/``entity_id``-Pruefung
    entfernt.
    """
    heute = nutzer()
    pid = _paris_vergleich(heute, "vgl-ac9")
    briefing_log_schreiben(heute, [compare_log_eintrag(pid, "morning", utc_zu(PARIS, D, 1, 30))])
    assert not (get_data_dir(heute) / COMPARE_SLOTS).exists(), "Vorbedingung: Rollout"

    lauf(heute, utc_zu(PARIS, D, H))

    assert naht.regulaer(uid=heute) == [], (
        "Das Protokoll bezeugt einen regulaeren Versand am heutigen Ortstag — "
        f"der Slot gilt als erledigt: {naht.versuche}"
    )

    vortag = nutzer()
    pid2 = _paris_vergleich(vortag, "vgl-ac9")
    briefing_log_schreiben(vortag, [
        compare_log_eintrag(pid2, "morning", utc_zu(PARIS, D - timedelta(days=1), H, 5)),
    ])

    lauf(vortag, utc_zu(PARIS, D, H))

    assert naht.regulaer(uid=vortag) == [(pid2, "morning")], (
        f"Ein Eintrag vom Vortag darf den heutigen Slot nicht blockieren: {naht.versuche}"
    )


# ═══════════════════════════════ AC-10 ═══════════════════════════════════════


@pytest.mark.parametrize("fall", ["on_demand", "trip_gleiche_id", "altbestand_ohne_typ"])
def test_ac10_handversand_und_trip_eintraege_blockieren_den_slot_nicht(naht, fall):
    """AC-10: Given Rollout-Lage (keine Compare-Datei), der Log-Eintrag des
    heutigen Ortstags stammt aber von einem Handversand (``on_demand=true``)
    bzw. von einem TRIP mit gleicher ID (Typ ``trip`` oder Altbestand ohne
    Typ) / When die Faelligkeit geprueft wird / Then ist der Vergleich faellig,
    wird versendet und danach vermerkt.

    RED-Charakter: Mutations-Waechter — heute nur ueber die Vermerk-
    Zusicherung rot (die Ableitung existiert noch nicht, der Versand findet
    also ohnehin statt). Nach GREEN rot bei: ``on_demand``-Filter entfernt,
    Typ-Filter entfernt bzw. auf ``(None, "compare")`` erweitert.
    """
    uid = nutzer()
    pid = _paris_vergleich(uid, "vgl-ac10")
    sent_at = utc_zu(PARIS, D, 6, 10)
    eintrag = {
        "on_demand": compare_log_eintrag(pid, "morning", sent_at, on_demand=True),
        "trip_gleiche_id": compare_log_eintrag(pid, "morning", sent_at, entity_type="trip"),
        "altbestand_ohne_typ": compare_log_eintrag(pid, "morning", sent_at, entity_type=None),
    }[fall]
    briefing_log_schreiben(uid, [eintrag])

    lauf(uid, utc_zu(PARIS, D, H))

    assert naht.regulaer() == [(pid, "morning")], (
        f"Ein {fall}-Eintrag darf dem Vergleich sein regulaeres Briefing nicht "
        f"nehmen: {naht.versuche}"
    )
    assert abgeschlossene_vermerke(uid) == {(pid, "morning", D.isoformat(), "sent")}, (
        f"Nach dem Versand muss der Slot vermerkt sein: {compare_vermerke(uid)!r}"
    )


# ═══════════════════════════════ AC-11 ═══════════════════════════════════════


@pytest.mark.parametrize(
    ("ausgang", "zaehlung"),
    [("sent", (1, 0)), ("no_channels", (0, 0)), ("no_weather", (0, 1))],
)
def test_ac11_ausgang_setzt_den_vermerk_und_sperrt_die_wiederholung(naht, ausgang, zaehlung):
    """AC-11: Given ein Versandversuch endet mit ``sent``, ``no_channels``
    oder ``no_weather`` / When er abgeschlossen ist / Then ist der Slot fuer
    diesen Ortstag mit genau diesem Ausgang vermerkt und wird in derselben
    Stunde nicht erneut regulaer verarbeitet; ``no_channels`` zaehlt NEUTRAL
    (weder sent noch failed), ``no_weather`` als failed (Trip-Paritaet #2218).

    Nachholversuche (#2587) zaehlen hier nicht mit: bei ``no_weather`` ist der
    Nachhol-Vermerk der vorgesehene Retry (AC-12).

    RED-Charakter: Fehlernachweis — heute kein Vermerk, ``no_channels`` zaehlt
    als failed, der Wiederholungslauf sendet erneut. Nach GREEN rot bei:
    ``release`` statt ``record_outcome`` fuer einen dieser Ausgaenge.
    """
    uid = nutzer()
    pid = _paris_vergleich(uid, f"vgl-ac11-{ausgang}")
    naht.standard = ausgang

    ergebnis = lauf(uid, utc_zu(PARIS, D, H))

    assert tuple(ergebnis) == zaehlung, (
        f"Ausgang {ausgang}: Zaehlung (sent, failed) erwartet {zaehlung}, gefunden {ergebnis}"
    )
    assert abgeschlossene_vermerke(uid) == {(pid, "morning", D.isoformat(), ausgang)}, (
        f"Ausgang {ausgang} muss den Slot vermerken: {compare_vermerke(uid)!r}"
    )

    naht.standard = "sent"
    lauf(uid, utc_zu(PARIS, D, H, 30))

    assert naht.regulaer() == [(pid, "morning")], (
        f"Nach Ausgang {ausgang} darf der Slot in derselben Stunde nicht erneut "
        f"regulaer versendet werden: {naht.versuche}"
    )


def test_ac11_kein_kanal_erreichbar_haelt_den_slot_offen(naht):
    """AC-11/AC-13 (Ausgangs-Abbildung): Given ``channels_unreachable`` /
    When der Lauf endet / Then KEIN abgeschlossener Vermerk (release), Zaehlung
    failed, und ein Wiederholungslauf derselben Stunde versucht es regulaer
    erneut und vermerkt dann ``sent``.

    RED-Charakter: Mutations-Waechter — heute nur ueber den abschliessenden
    ``sent``-Vermerk rot. Nach GREEN rot bei: ``record_outcome`` statt
    ``release`` bei ``channels_unreachable`` (dann sendet der zweite Lauf nicht).
    """
    uid = nutzer()
    pid = _paris_vergleich(uid, "vgl-ac11-unerreichbar")
    naht.standard = "channels_unreachable"

    ergebnis = lauf(uid, utc_zu(PARIS, D, H))

    assert tuple(ergebnis) == (0, 1), ergebnis
    assert abgeschlossene_vermerke(uid) == set(), (
        f"channels_unreachable darf keinen Vermerk hinterlassen: {compare_vermerke(uid)!r}"
    )

    naht.standard = "sent"
    lauf(uid, utc_zu(PARIS, D, H, 30))

    assert naht.regulaer() == [(pid, "morning"), (pid, "morning")], (
        f"Der Slot ist offen geblieben und muss erneut versucht werden: {naht.versuche}"
    )
    assert abgeschlossene_vermerke(uid) == {(pid, "morning", D.isoformat(), "sent")}, (
        compare_vermerke(uid)
    )


# ═══════════════════════════════ AC-12 ═══════════════════════════════════════


def test_ac12_kein_wetter_im_cron_vermerkt_und_holt_ueber_den_marker_nach(kette):
    """AC-12: Given der Zeitplan-Versand scheitert an fehlenden Wetterdaten
    (``no_weather``) / When der Cron-Lauf endet / Then ist der Slot mit
    ``no_weather`` vermerkt UND ein Nachhol-Vermerk (#2587) geschrieben; in
    der Folgestunde (Wetter wieder da) kommt das Briefing genau EINMAL an —
    ueber den Nachholer, mit Nachhol-Hinweis — und danach nicht noch einmal.

    Volle Kette (echter ``send_one_compare_preset``), weil der Nachhol-
    Vermerk aus dem echten Versandweg stammen muss.

    RED-Charakter: Fehlernachweis — heute schreibt der Cron bei ``no_weather``
    weder Vermerk noch Nachhol-Vermerk, der Vergleich faellt ersatzlos aus.
    Nach GREEN rot bei: ``release`` statt ``record_outcome`` bei
    ``no_weather`` (Vermerk-Zusicherung), Nachholer droppt bei ``no_weather``.
    """
    from tests.tdd._compare_kette_fixtures import TARGET_DATE

    tag = TARGET_DATE
    uid = kette_nutzer()
    pid = vergleich_ablegen(uid, "vgl-ac12", orte=["loc-ibk", "loc-bz"])
    kette.wetter_aus = True

    lauf(uid, utc_zu(WIEN, tag, H))

    assert kette.mails() == [], kette.mit
    assert abgeschlossene_vermerke(uid) == {(pid, "morning", tag.isoformat(), "no_weather")}, (
        f"no_weather muss den Slot vermerken: {compare_vermerke(uid)!r}"
    )
    marker = [(m.get("preset_id"), m.get("report_type"), m.get("date"), m.get("slot_hour"))
              for m in nachhol_vermerke(uid)]
    assert marker == [(pid, "morning", tag.isoformat(), H)], (
        f"no_weather im Cron muss einen Nachhol-Vermerk schreiben: {nachhol_vermerke(uid)!r}"
    )

    kette.wetter_aus = False
    lauf(uid, utc_zu(WIEN, tag, H + 1))
    lauf(uid, utc_zu(WIEN, tag, H + 2))

    mails = kette.mails()
    assert len(mails) == 1, f"Genau eine Nachlieferung, kein Doppel: {kette.mit!r}"
    assert NACHHOL_HINWEIS in (mails[0]["plain_text_body"] or ""), (
        "Die Zustellung kommt ueber den Nachhol-Vermerk (mit Hinweis), nicht als "
        f"zweiter regulaerer Versand: {(mails[0]['plain_text_body'] or '')[:200]!r}"
    )


# ═══════════════════════════════ AC-13 ═══════════════════════════════════════


def test_ac13_kein_kanal_erreichbar_ergibt_mit_nachhol_vermerk_kein_doppel(kette):
    """AC-13: Given der einzige wirksame Kanal (Telegram, keine ``mail_to``)
    scheitert beim Senden (``channels_unreachable``) / When der Lauf endet /
    Then bleibt der Vermerk aus, der Nachhol-Vermerk liegt vor, ein Lauf
    derselben Stunde mit wieder erreichbarem Kanal sendet REGULAER (ohne
    Nachhol-Hinweis) genau einmal, und ein weiterer Lauf sendet nichts mehr.

    RED-Charakter: Mutations-Waechter — heute nur ueber den abschliessenden
    ``sent``-Vermerk rot. Nach GREEN rot bei: ``record_outcome`` statt
    ``release`` (dann geht die Zustellung ueber den Nachholer MIT Hinweis),
    Nachholer ohne „wait" (dann zwei Zustellungen).
    """
    from tests.tdd._compare_kette_fixtures import TARGET_DATE

    tag = TARGET_DATE
    uid = kette_nutzer()
    pid = vergleich_ablegen(uid, "vgl-ac13", orte=["loc-ibk", "loc-bz"], telegram=True)
    ohne_mail_to(uid)
    kette.telegram_aus = True

    lauf(uid, utc_zu(WIEN, tag, H))

    assert kette.telegram_versuche == 1, "Vorbedingung: Telegram-Ausgang betreten"
    assert kette.telegramme() == [], kette.mit
    assert abgeschlossene_vermerke(uid) == set(), (
        f"channels_unreachable darf keinen Vermerk hinterlassen: {compare_vermerke(uid)!r}"
    )
    assert [m.get("preset_id") for m in nachhol_vermerke(uid)] == [pid], (
        f"Vorbedingung (#2587): Nachhol-Vermerk liegt vor: {nachhol_vermerke(uid)!r}"
    )

    kette.telegram_aus = False
    lauf(uid, utc_zu(WIEN, tag, H, 30))
    lauf(uid, utc_zu(WIEN, tag, H, 45))

    tg = kette.telegramme()
    assert len(tg) == 1, f"Genau eine Zustellung aus regulaerem Lauf und Nachholer: {kette.mit!r}"
    assert NACHHOL_HINWEIS not in (tg[0]["body"] or ""), (
        "Der regulaere Lauf muss senden (Slot war per release offen), nicht der "
        f"Nachholer: {(tg[0]['body'] or '')[:200]!r}"
    )
    assert abgeschlossene_vermerke(uid) == {(pid, "morning", tag.isoformat(), "sent")}, (
        compare_vermerke(uid)
    )


# ═══════════════════════════════ AC-14 ═══════════════════════════════════════


def test_ac14_ungeraeumter_marker_nach_zugestelltem_slot_sendet_nicht_doppelt(naht):
    """AC-14: Given ein Nachhol-Marker ist ungeraeumt, obwohl der Slot am
    Ortstag bereits mit ``sent`` vermerkt ist / When der Nachholer bewertet /
    Then verwirft er ihn ohne Versand. Bei Ausgang ``no_weather`` bzw.
    ``no_channels`` verwirft er ihn NICHT — dort ist der Marker der Retry.

    RED-Charakter: Fehlernachweis — heute kennt der Vergleich keinen Vermerk:
    der Slot gilt in der Slot-Stunde als faellig und geht trotz ``sent``
    erneut regulaer raus. Nach GREEN rot bei: ``_catchup_verdict`` ohne
    Store-Pruefung (dann sendet der Nachholer das Doppel), Drop auch bei
    ``no_weather``/``no_channels`` (dann faellt die Nachlieferung aus).
    """
    faelle = {}
    for ausgang in ("sent", "no_weather", "no_channels"):
        uid = nutzer()
        pid = _paris_vergleich(uid, f"vgl-ac14-{ausgang}")
        compare_vermerk_schreiben(uid, [compare_vermerk(pid, "morning", D, ausgang)])
        nachhol_vermerk_schreiben(uid, pid, "morning", D, H)
        faelle[ausgang] = (uid, pid)

    for uid, _ in faelle.values():
        lauf(uid, utc_zu(PARIS, D, H))

    uid, pid = faelle["sent"]
    assert naht.regulaer(pid) == [] and naht.nachgeholt(pid) == [], (
        "Slot bereits zugestellt: weder regulaerer Versand noch Nachholversand "
        f"duerfen stattfinden: {naht.versuche}"
    )
    assert nachhol_vermerke(uid) == [], (
        f"Der ungeraeumte Marker wird verworfen: {nachhol_vermerke(uid)!r}"
    )
    for ausgang in ("no_weather", "no_channels"):
        _, pid = faelle[ausgang]
        assert naht.regulaer(pid) == [], (
            f"{ausgang}: der Slot ist vermerkt, kein regulaerer Versand: {naht.versuche}"
        )
        assert naht.nachgeholt(pid) == [(pid, "morning")], (
            f"{ausgang}: der Marker ist der Retry und muss nachliefern: {naht.versuche}"
        )


# ═══════════════════════════════ AC-15 ═══════════════════════════════════════


def test_ac15_marker_und_faelliger_slot_ergeben_genau_einen_versand(naht):
    """AC-15: Given der regulaere Slot ist faellig und ein Nachhol-Marker liegt
    vor / When Nachholer und Sammellauf laufen — auch wiederholt in derselben
    Stunde / Then wartet der Nachholer, der REGULAERE Versand sendet, und es
    entsteht kein zweites Briefing fuer Slot und Ortstag.

    RED-Charakter: Fehlernachweis — heute sendet der Wiederholungslauf
    regulaer erneut (kein Vermerk). Nach GREEN rot bei: Nachholer ohne „wait"
    (zwei Versuche im ersten Lauf), ``_catchup_verdict`` ohne Store-Pruefung
    (der ungeraeumte Marker sendet im zweiten Lauf).
    """
    uid = nutzer()
    pid = _paris_vergleich(uid, "vgl-ac15")
    nachhol_vermerk_schreiben(uid, pid, "morning", D, H)

    lauf(uid, utc_zu(PARIS, D, H))

    assert naht.regulaer() == [(pid, "morning")] and naht.nachgeholt() == [], (
        f"Der Nachholer wartet, der regulaere Versand sendet: {naht.versuche}"
    )

    lauf(uid, utc_zu(PARIS, D, H, 30))

    assert len(naht.versuche) == 1, (
        f"Kein zweites Briefing fuer denselben Slot und Ortstag: {naht.versuche}"
    )
    assert abgeschlossene_vermerke(uid) == {(pid, "morning", D.isoformat(), "sent")}, (
        compare_vermerke(uid)
    )


# ═══════════════════════════════ AC-16 ═══════════════════════════════════════


def test_ac16_ohne_schreibsperre_wird_nicht_gesendet(naht, monkeypatch):
    """AC-16: Given die Schreibsperre auf ``briefing_slots_compare.json`` ist
    innerhalb der Frist nicht zu bekommen / When ein Vergleich zum Versand
    ansteht / Then wird NICHT gesendet (fail-closed).

    Die Sperre haelt ein ECHTER ``flock`` im selben Prozess auf der Sidecar-
    Datei (Open-File-Description, kollidiert real). Die Frist wird ueber das
    Modul-Attribut gekuerzt.

    RED-Charakter: Fehlernachweis — heute gibt es keine Reservierung, der
    Versand laeuft. Nach GREEN rot bei: fail-open (Warnung loggen und senden).
    """
    uid = nutzer()
    pid = _paris_vergleich(uid, "vgl-ac16")
    monkeypatch.setattr(briefing_slots, "LOCK_TIMEOUT_SECONDS", 0.05, raising=False)

    ordner = get_data_dir(uid)
    ordner.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(ordner / f"{COMPARE_SLOTS}.lock"), os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        lauf(uid, utc_zu(PARIS, D, H))
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)

    assert naht.versuche == [], (
        "Ohne Sperre kein wirksamer Vermerk — dann darf NICHT gesendet werden, "
        f"sonst droht der Doppelversand (Premium-SMS): {naht.versuche}"
    )

    lauf(uid, utc_zu(PARIS, D, H, 30))
    assert naht.regulaer() == [(pid, "morning")], (
        f"Sperre wieder frei: der Slot ist weiter offen und wird versendet: {naht.versuche}"
    )


# ═══════════════════════════════ AC-17 ═══════════════════════════════════════


@pytest.mark.parametrize(
    "ausnahme",
    [ValueError("kein Empfaenger (Skip-Pfad)"), RuntimeError("Renderer kaputt")],
    ids=["ValueError", "RuntimeError"],
)
def test_ac17_ausnahme_nimmt_die_reservierung_zurueck_und_isoliert(naht, ausnahme):
    """AC-17: Given zwei Vergleiche, einer wirft beim Versand eine Ausnahme /
    When der Lauf endet / Then ist dessen Reservierung zurueckgenommen, er
    zaehlt als failed, der andere kommt an (Fehlerisolation #2217); ein
    Wiederholungslauf versucht NUR den gescheiterten erneut.

    RED-Charakter: Fehlernachweis — heute sendet der Wiederholungslauf auch
    den zugestellten Vergleich erneut. Nach GREEN rot bei: Ausnahme ohne
    ``release`` (Slot bliebe als lebendiger Claim gesperrt), Ausnahme bricht
    die Schleife ab.
    """
    uid = nutzer()
    ort_anlegen(uid, "ort-paris", KORSIKA)
    vergleich_ablegen(uid, "vgl-ac17-kaputt", orte=["ort-paris"])
    vergleich_ablegen(uid, "vgl-ac17-ok", orte=["ort-paris"])
    naht.ausgang["vgl-ac17-kaputt"] = ausnahme

    erster = lauf(uid, utc_zu(PARIS, D, H))
    zweiter = lauf(uid, utc_zu(PARIS, D, H, 30))

    assert tuple(erster) == (1, 1), f"Erster Lauf (sent, failed): {erster}"
    assert sorted(naht.regulaer()) == [
        ("vgl-ac17-kaputt", "morning"), ("vgl-ac17-kaputt", "morning"),
        ("vgl-ac17-ok", "morning"),
    ], f"Nur der gescheiterte Vergleich wird wiederholt: {naht.versuche}"
    assert tuple(zweiter) == (0, 1), f"Zweiter Lauf (sent, failed): {zweiter}"
    assert abgeschlossene_vermerke(uid) == {("vgl-ac17-ok", "morning", D.isoformat(), "sent")}, (
        compare_vermerke(uid)
    )
    assert ("vgl-ac17-kaputt", "morning", D.isoformat(), None) not in compare_vermerk_schluessel(uid), (
        f"Die Reservierung des gescheiterten Vergleichs ist zurueckzunehmen: {compare_vermerke(uid)!r}"
    )


# ═══════════════════════════════ AC-21 ═══════════════════════════════════════


def test_ac21_manueller_ausloeser_zweimal_dieselbe_stunde_sendet_einmal(naht):
    """AC-21: Given ein Vergleich wird ueber ``run_compare_presets_daily(hour=)``
    angestossen / When dieselbe Stunde ein zweites Mal ausgeloest wird / Then
    laeuft der Aufruf ueber denselben Sammelpfad inklusive Vermerk und sendet
    nicht doppelt.

    Der Ausloeser verankert ``hour`` in ``Europe/Vienna`` am heutigen Tag; der
    Vergleich liegt deshalb in Wien (Innsbruck), Slot 07:00.

    RED-Charakter: Fehlernachweis — heute sendet der zweite Aufruf erneut.
    Nach GREEN rot bei: Sonderpfad am Vermerk vorbei.
    """
    from services.scheduler_dispatch_service import run_compare_presets_daily

    uid = nutzer()
    ort_anlegen(uid, "ort-wien", INNSBRUCK)
    pid = vergleich_ablegen(uid, "vgl-ac21", orte=["ort-wien"])

    run_compare_presets_daily(uid, data_root=str(get_data_root()), hour=H)
    run_compare_presets_daily(uid, data_root=str(get_data_root()), hour=H)

    assert naht.regulaer() == [(pid, "morning")], (
        f"Zwei Ausloesungen derselben Stunde, genau ein Versand: {naht.versuche}"
    )
    assert [k[:2] + (k[3],) for k in abgeschlossene_vermerke(uid)] == [(pid, "morning", "sent")], (
        compare_vermerke(uid)
    )


# ═══════════════════════════════ AC-22 ═══════════════════════════════════════


def test_ac22_handversand_schreibt_keinen_vermerk_und_wird_nicht_blockiert(kette):
    """AC-22: Given ein Handversand (``send_compare_preset``, ``on_demand=True``)
    / When er VOR und NACH dem regulaeren Slot laeuft / Then schreibt er
    keinen Vermerk, wird von keinem blockiert, und der regulaere Slot bleibt
    trotz des vorherigen Handversands faellig.

    Echter heutiger Ortstag (Wien), weil ``send_compare_preset`` seine Uhr
    selbst liest und die Rollout-Ableitung ``sent_at`` mit dem Ortstag des
    Laufs vergleicht.

    RED-Charakter: Mutations-Waechter — heute nur ueber den Vermerk des
    regulaeren Laufs rot. Nach GREEN rot bei: Vermerk im Handversand gesetzt
    (Datei aendert sich bzw. regulaerer Slot blockiert), ``on_demand``-Filter
    der Rollout-Ableitung entfernt (regulaerer Slot nach Handversand stumm),
    Handversand vom Vermerk blockiert.
    """
    from services.scheduler_dispatch_service import send_compare_preset
    from tests.helpers.briefing_imminent_fixtures import ortstag

    uid = kette_nutzer()
    pid = vergleich_ablegen(uid, "vgl-ac22", orte=["loc-ibk", "loc-bz"])
    heute = ortstag(WIEN)
    vermerk_pfad = get_data_dir(uid) / COMPARE_SLOTS

    vorher = send_compare_preset(uid, pid, str(get_data_root()))
    assert vorher.get("status") == "ok", vorher
    assert len(kette.mails()) == 1, kette.mit
    assert not vermerk_pfad.exists(), "Der Handversand darf keinen Vermerk schreiben"

    lauf(uid, utc_zu(WIEN, heute, H))

    assert len(kette.mails()) == 2, (
        f"Der regulaere Slot bleibt trotz Handversand faellig: {kette.mit!r}"
    )
    assert abgeschlossene_vermerke(uid) == {(pid, "morning", heute.isoformat(), "sent")}, (
        compare_vermerke(uid)
    )
    stand = vermerk_pfad.read_bytes()

    nachher = send_compare_preset(uid, pid, str(get_data_root()))
    lauf(uid, utc_zu(WIEN, heute, H, 30))

    assert nachher.get("status") == "ok", nachher
    assert len(kette.mails()) == 3, (
        "Handversand nach dem regulaeren Slot funktioniert, der Wiederholungslauf "
        f"sendet nichts: {kette.mit!r}"
    )
    assert vermerk_pfad.read_bytes() == stand, "Der Handversand darf den Vermerk nicht aendern"


# ═══════════════════════════════ AC-23 ═══════════════════════════════════════


def test_ac23_trip_standard_schreibt_nur_in_die_trip_datei():
    """AC-23 (Regressionsschutz, HEUTE GRUEN): Given der parametrierte
    ``BriefingSlotStore`` mit Trip-Defaults / When ein Trip-Vermerk reserviert
    und abgeschlossen wird / Then landet er in ``briefing_slots.json`` unter
    ``trip_id`` — ``briefing_slots_compare.json`` entsteht nicht.

    RED-Charakter: Mutations-Waechter — rot bei: Standardwerte der
    parametrierten Klasse veraendert (Trip schreibt in die Compare-Datei bzw.
    unter ``preset_id``).
    """
    from services.briefing_slots import BriefingSlotStore

    uid = nutzer()
    moment = utc_zu(PARIS, D, H)
    store = BriefingSlotStore(uid)

    assert store.reserve("trip-x", "morning", D, PARIS, moment=moment) is True
    store.record_outcome("trip-x", "morning", D, "sent")

    import json

    trip_daten = json.loads((get_data_dir(uid) / TRIP_SLOTS).read_text(encoding="utf-8"))
    assert [(e.get("trip_id"), e.get("slot"), e.get("local_day"), e.get("outcome"))
            for e in trip_daten["entries"]] == [("trip-x", "morning", D.isoformat(), "sent")]
    assert not any("preset_id" in e for e in trip_daten["entries"]), trip_daten
    assert not (get_data_dir(uid) / COMPARE_SLOTS).exists(), (
        "Der Trip-Pfad darf nie in die Compare-Datei schreiben"
    )
    assert BriefingSlotStore(uid).is_recorded("trip-x", "morning", D, PARIS) is True


def test_ac23_trip_und_vergleich_gleicher_kennung_beruehren_einander_nicht(naht):
    """AC-23/Teilungs-Gate: Given ein Trip-Vermerk ``sent`` fuer die Kennung X
    und ein Vergleich mit derselben Kennung X / When der Compare-Lauf laeuft /
    Then wird der Vergleich versendet und in ``briefing_slots_compare.json``
    vermerkt; ``briefing_slots.json`` bleibt byte-gleich und der Trip-Speicher
    sieht keinen neuen Vermerk.

    RED-Charakter: Fehlernachweis — heute entsteht kein Compare-Vermerk.
    Nach GREEN rot bei: Compare und Trip in derselben Datei, ``id_key``
    ignoriert (Trip-Vermerk X blockiert den Vergleich X).
    """
    from services.briefing_slots import BriefingSlotStore

    uid = nutzer()
    pid = _paris_vergleich(uid, "geteilte-kennung")
    BriefingSlotStore(uid).record_outcome(pid, "morning", D, "sent")
    trip_pfad = get_data_dir(uid) / TRIP_SLOTS
    trip_stand = trip_pfad.read_bytes()

    lauf(uid, utc_zu(PARIS, D, H))

    assert naht.regulaer() == [(pid, "morning")], (
        f"Ein Trip-Vermerk gleicher Kennung darf den Vergleich nicht blockieren: {naht.versuche}"
    )
    assert abgeschlossene_vermerke(uid) == {(pid, "morning", D.isoformat(), "sent")}, (
        compare_vermerke(uid)
    )
    assert trip_pfad.read_bytes() == trip_stand, "briefing_slots.json muss byte-gleich bleiben"
