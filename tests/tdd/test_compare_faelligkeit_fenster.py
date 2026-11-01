"""TDD RED — Ortsvergleich-Briefing: Faelligkeitsfenster statt Stundengleichheit.

SPEC: docs/specs/modules/fix_1777_compare_faelligkeit_und_idempotenz.md
      (Commit 2: AC-1, AC-2, AC-3, AC-5, AC-13 Fensterfall, AC-18, AC-19, AC-20)
Vorbild Trip (#1725): tests/tdd/test_briefing_slot_idempotenz.py T1-T4, T15;
Alarm-Sperre: tests/tdd/test_briefing_slot_faelligkeit_und_alarmsperre.py;
Anzeige: tests/tdd/test_next_briefing_endpoint_nutzerdaten.py.
Aufbau/Naehte: tests/tdd/_compare_slot_vermerk_fixtures.py (Begruendung dort).

Zielverhalten::

    faellig ⟺ slot_stunde <= ortsstunde < slot_stunde + 3      (Ortszone des Presets)
             UND kein Vermerk fuer (preset_id, slot, ortstag)
             UND Wochentag-Gate (weekly) trifft den ORTSTAG des Laufs
    kein Fenster ueber Ortsmitternacht (Slot 23 gilt nur 23:00-23:59)

RED-Ursache heute: ``compare_slot_scheduler.py:211/213`` vergleicht Stunden
auf GLEICHHEIT; es gibt weder Fenster noch Vermerk.

🔴 Fensterbreite ist nur an einem AUSGEFALLENEN Takt messbar (bei wirksamem
Vermerk liefert jede Breite am Normaltag genau einen Treffer). AC-3 prueft
deshalb H+1 UND H+2 (faellig) gegen H+3 (nicht faellig) an Nutzern, deren
Lauf zur Stunde H nie stattfand.

────────────────────────────────────────────────────────────────────────────
Schnittstellen-Annahmen fuer GREEN (zusaetzlich zu test_compare_briefing_vermerk.py)
────────────────────────────────────────────────────────────────────────────
1. Geteiltes reines Fensterpraedikat + ``NACHHOL_FENSTER_STUNDEN = 3`` in
   ``services/briefing_slots.py``; ``trip_report_scheduler`` re-exportiert.
2. ``presets_due_for_hour(presets, all_locations, now_utc, store=None)``:
   Fenster statt ``==``; mit ``store`` (read-only) faellt ein Slot mit
   ABGESCHLOSSENEM Vermerk (``is_recorded``) heraus. Alarm-Sperre
   (``compare_alert``, ``compare_official_alert``) und Anzeige uebergeben den
   Compare-Speicher des Nutzers; der Sammellauf filtert separat mit
   ``is_recorded_or_claimed``.
3. ``next_briefing.next_compare_briefing(preset, locations, now_utc,
   strict_after=False, slot_store=None)`` — ``slot_store`` read-only wie beim
   Trip; ``api/routers/internal.py`` uebergibt den Compare-Speicher des
   anfragenden Nutzers.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

import pytest

from app.loader import get_data_dir
from services import briefing_slots
from tests.tdd._compare_slot_vermerk_fixtures import (  # noqa: F401  (Fixtures)
    KORSIKA,
    NACHHOL_HINWEIS,
    NEW_YORK,
    NY,
    PARIS,
    WIEN,
    abgeschlossene_vermerke,
    compare_vermerk,
    compare_vermerk_schreiben,
    compare_vermerke,
    kette,
    kette_nutzer,
    lauf,
    nachhol_vermerke,
    naht,
    nutzer,
    ohne_mail_to,
    ort_anlegen,
    ortsstunde,
    ortstag_schritte,
    utc_zu,
    vergleich_ablegen,
)

D = date(2026, 8, 20)  # Do, kein Umstellungstag


def _paris_vergleich(uid: str, pid: str, **kw) -> str:
    ort_anlegen(uid, f"ort-{pid}", KORSIKA)
    return vergleich_ablegen(uid, pid, orte=[f"ort-{pid}"], **kw)


def _stunden_mit_versand(naht, uid: str, pid: str, zone, tag: date) -> list[int]:
    """Schreitet den Ortstag ab; liefert die Ortsstunden, in denen der Lauf
    einen REGULAEREN Versandversuch fuer ``pid`` ausloeste."""
    stunden = []
    for now in ortstag_schritte(zone, tag):
        vorher = len(naht.regulaer(pid))
        lauf(uid, now)
        if len(naht.regulaer(pid)) > vorher:
            stunden.append(ortsstunde(now, zone))
    return stunden


# ═══════════════════════════════ AC-1 ════════════════════════════════════════


def test_ac1_fruehjahr_slot_0200_kommt_genau_einmal_um_0300(naht):
    """AC-1: Given Morgen-Briefing 02:00 in Europe/Paris am 29.03.2026 (die
    Ortsstunde 02 existiert nicht) / When der Lauf den Ortstag stuendlich
    durchlaeuft / Then wird der Vergleich genau einmal versendet, bei
    Ortsstunde 03.

    RED-Charakter: Fehlernachweis — heute 0 Versaende (Stundengleichheit).
    """
    uid = nutzer()
    pid = _paris_vergleich(uid, "vgl-f-ac1", morgen="02:00:00")

    stunden = _stunden_mit_versand(naht, uid, pid, PARIS, date(2026, 3, 29))

    assert stunden == [3], (
        "Fruehjahrs-Umstellung: das 02:00-Briefing muss genau einmal, um 03:00 "
        f"Ortszeit, kommen — gefunden Ortsstunden {stunden}"
    )


# ═══════════════════════════════ AC-2 ════════════════════════════════════════


def test_ac2_herbst_doppelstunde_sendet_nur_einmal(naht):
    """AC-2: Given derselbe Vergleich am 25.10.2026 (Ortsstunde 02 kommt zweimal
    vor) / When beide Vorkommen durchlaufen werden / Then geht das Briefing
    genau einmal raus; das zweite Vorkommen filtert der Vermerk.

    RED-Charakter: Fehlernachweis — heute 2 Versaende. Nach GREEN rot bei:
    ``is_recorded_or_claimed`` im Sammellauf entfernt.
    """
    uid = nutzer()
    pid = _paris_vergleich(uid, "vgl-f-ac2", morgen="02:00:00")

    stunden = _stunden_mit_versand(naht, uid, pid, PARIS, date(2026, 10, 25))

    assert stunden == [2], (
        "Herbst-Umstellung: die Ortsstunde 02 kommt zweimal vor, das Briefing "
        f"darf trotzdem nur einmal raus — gefunden Ortsstunden {stunden}"
    )
    assert naht.regulaer(pid) == [(pid, "morning")], naht.versuche


# ═══════════════════════════════ AC-3 ════════════════════════════════════════


def test_ac3_ausgefallener_takt_wird_bis_h_plus_2_nachgeholt_und_nicht_mehr_ab_h_plus_3(naht):
    """AC-3: Given Slot-Stunde H=07, der Takt zur Stunde H ist ausgefallen /
    When der erste Lauf in H+1 bzw. H+2 stattfindet / Then ist der Vergleich
    faellig; findet er erst in H+3 statt, nicht mehr. Am Normaltag ohne
    Ausfall trifft genau die Ortsstunde 07.

    Je Nachbarwert ein eigener Nutzer (kein Vermerk, kein frueherer Lauf).

    RED-Charakter: Fehlernachweis — heute ist H+1/H+2 nicht faellig. Nach
    GREEN rot bei: Fenster 3 -> 1 oder 2 (H+1 bzw. H+2 stumm), 3 -> 4 oder
    „bis Tagesende" (H+3 faellig), Faelligkeit auf ``<=`` gedreht (Normaltag
    trifft 00 statt 07).
    """
    H = 7
    ergebnisse = {}
    for versatz in (1, 2, 3):
        uid = nutzer()
        pid = _paris_vergleich(uid, f"vgl-f-ac3-h{versatz}")
        lauf(uid, utc_zu(PARIS, D, H + versatz))
        ergebnisse[versatz] = naht.regulaer(pid)

    assert ergebnisse[1] == [("vgl-f-ac3-h1", "morning")], (
        f"Takt 07 ausgefallen — in Ortsstunde 08 muss nachgeholt werden: {naht.versuche}"
    )
    assert ergebnisse[2] == [("vgl-f-ac3-h2", "morning")], (
        "Takte 07 und 08 ausgefallen — in Ortsstunde 09 muss noch nachgeholt "
        f"werden (Fenster 3 h, nicht 2): {naht.versuche}"
    )
    assert ergebnisse[3] == [], (
        "Ortsstunde 10 liegt drei Stunden hinter 07 und ausserhalb des Fensters: "
        f"{naht.versuche}"
    )

    uid = nutzer()
    pid = _paris_vergleich(uid, "vgl-f-ac3-normal")
    assert _stunden_mit_versand(naht, uid, pid, PARIS, D) == [7], naht.versuche


# ═══════════════════════════════ AC-5 ════════════════════════════════════════


def test_ac5_zwei_zonen_jeder_vergleich_nach_seiner_ortszeit_und_seinem_ortstag(naht):
    """AC-5: Given ein Nutzer mit zwei Vergleichen in Europe/Paris und
    America/New_York, beide Slot 19:00 / When der Lauf zu verschiedenen
    UTC-Zeitpunkten laeuft / Then wird jeder nach SEINER Ortsstunde und SEINEM
    Ortstag beurteilt und hoechstens einmal je Ortstag versendet.

    New York 19:00 EDT = 23:00 UTC; das Fenster reicht ueber die UTC-
    Tagesgrenze (20:00 EDT = 00:00 UTC des Folgetags). Nur ein Schluessel mit
    dem ORTSTAG erkennt den Lauf um 00:00 UTC als denselben Tag.

    RED-Charakter: Fehlernachweis — heute kein Vermerk. Nach GREEN rot bei:
    Schluessel-Ortstag aus UTC (dann zweiter New-York-Versand um 00:00 UTC),
    eine Zone fuer alle Vergleiche.
    """
    uid = nutzer()
    ort_anlegen(uid, "ort-paris", KORSIKA)
    ort_anlegen(uid, "ort-ny", NEW_YORK)
    vergleich_ablegen(uid, "vgl-paris", orte=["ort-paris"], morgen="19:00:00")
    vergleich_ablegen(uid, "vgl-ny", orte=["ort-ny"], morgen="19:00:00")

    paris_19 = utc_zu(PARIS, D, 19)
    lauf(uid, paris_19)
    assert naht.regulaer() == [("vgl-paris", "morning")], (
        f"17:00 UTC: nur Paris (19:00) ist faellig, New York (13:00) nicht: {naht.versuche}"
    )

    ny_19 = utc_zu(NY, D, 19)
    assert ny_19.date() == D and ny_19.hour == 23, ny_19
    lauf(uid, ny_19)
    lauf(uid, utc_zu(NY, D, 20))  # 00:00 UTC des Folgetags
    lauf(uid, utc_zu(NY, D, 21))

    assert sorted(naht.regulaer()) == [("vgl-ny", "morning"), ("vgl-paris", "morning")], (
        "Je Vergleich genau ein Versand am Ortstag; Paris ist um 01:00 Ortszeit "
        f"nicht faellig, New York nach 19:00 vermerkt: {naht.versuche}"
    )
    assert abgeschlossene_vermerke(uid) == {
        ("vgl-paris", "morning", D.isoformat(), "sent"),
        ("vgl-ny", "morning", D.isoformat(), "sent"),
    }, f"Schluessel-Ortstag ist der Ortstag der Preset-Zone: {compare_vermerke(uid)!r}"


# ═══════════════════════════════ AC-13 (Fensterfall) ═════════════════════════


def test_ac13_kein_kanal_erreichbar_wird_in_h_plus_1_regulaer_nachgeholt(kette):
    """AC-13 (Fensterfall): Given ``channels_unreachable`` um 07:00 (Telegram,
    keine ``mail_to``) / When der naechste Lauf um 08:00 Ortszeit stattfindet
    (Kanal wieder erreichbar) / Then sendet der REGULAERE Fensterversand genau
    einmal (ohne Nachhol-Hinweis), der Nachhol-Vermerk fuehrt zu keinem
    zweiten Briefing, und um 09:00 kommt nichts mehr.

    RED-Charakter: Fehlernachweis — heute ist 08:00 nicht faellig, die
    Zustellung kommt ueber den Nachholer (mit Hinweis). Nach GREEN rot bei:
    ``record_outcome`` statt ``release`` bei ``channels_unreachable``.
    """
    from tests.tdd._compare_kette_fixtures import TARGET_DATE

    tag = TARGET_DATE
    uid = kette_nutzer()
    pid = vergleich_ablegen(uid, "vgl-f-ac13", orte=["loc-ibk", "loc-bz"], telegram=True)
    ohne_mail_to(uid)
    kette.telegram_aus = True

    lauf(uid, utc_zu(WIEN, tag, 7))
    assert kette.telegram_versuche == 1 and kette.telegramme() == [], kette.mit
    assert [m.get("preset_id") for m in nachhol_vermerke(uid)] == [pid], nachhol_vermerke(uid)

    kette.telegram_aus = False
    lauf(uid, utc_zu(WIEN, tag, 8))
    lauf(uid, utc_zu(WIEN, tag, 9))

    tg = kette.telegramme()
    assert len(tg) == 1, f"Genau eine Zustellung: {kette.mit!r}"
    assert NACHHOL_HINWEIS not in (tg[0]["body"] or ""), (
        "Um 08:00 liegt der Slot im Fenster und war per release offen — der "
        f"regulaere Versand sendet, nicht der Nachholer: {(tg[0]['body'] or '')[:200]!r}"
    )
    assert abgeschlossene_vermerke(uid) == {(pid, "morning", tag.isoformat(), "sent")}, (
        compare_vermerke(uid)
    )


# ═══════════════════════════════ AC-18 ═══════════════════════════════════════


def test_ac18_weekly_gate_und_kein_fenster_ueber_ortsmitternacht(naht):
    """AC-18: Given ein Weekly-Vergleich, dessen Wochentag am Ortstag NICHT
    zutrifft / When in einer Stunde des Fensters gelaufen wird / Then ist er
    nicht faellig. Das Fenster laeuft nicht ueber Ortsmitternacht: Slot 23:00
    ist um 00:30 des Folgetags nicht faellig.

    Positiv-Kontrollen (heute rot, sonst waere der Test vakuum): Weekly mit
    PASSENDEM Wochentag ist um 08:00 faellig, Slot 22:00 um 23:30.

    RED-Charakter: Fehlernachweis an den Kontrollen; Mutations-Waechter an den
    Negativfaellen — rot bei: Weekly-Gate ueber den UTC-Tag oder den
    Slot-Tag statt den Ortstag des Laufs, Fenster ueber Mitternacht
    (Modulo-Rechnung).
    """
    passend = nutzer()
    pid_passend = _paris_vergleich(passend, "vgl-f-wk-ja", schedule="weekly", weekday=D.weekday())
    lauf(passend, utc_zu(PARIS, D, 8))

    falsch = nutzer()
    pid_falsch = _paris_vergleich(
        falsch, "vgl-f-wk-nein", schedule="weekly", weekday=(D + timedelta(days=1)).weekday(),
    )
    for stunde in (7, 8, 9):
        lauf(falsch, utc_zu(PARIS, D, stunde))

    spaet = nutzer()
    pid_22 = _paris_vergleich(spaet, "vgl-f-22", morgen="22:00:00")
    lauf(spaet, utc_zu(PARIS, D, 23, 30))

    mitternacht = nutzer()
    pid_23 = _paris_vergleich(mitternacht, "vgl-f-23", morgen="23:00:00")
    lauf(mitternacht, utc_zu(PARIS, D + timedelta(days=1), 0, 30))
    lauf(mitternacht, utc_zu(PARIS, D + timedelta(days=1), 1, 30))

    assert naht.regulaer(pid_passend) == [(pid_passend, "morning")], (
        f"Weekly am richtigen Ortstag, Ortsstunde 08 im Fenster: {naht.versuche}"
    )
    assert naht.regulaer(pid_22) == [(pid_22, "morning")], (
        f"Slot 22:00 ist um 23:30 desselben Ortstags im Fenster: {naht.versuche}"
    )
    assert naht.regulaer(pid_falsch) == [], (
        f"Weekly am falschen Ortstag darf im ganzen Fenster nicht senden: {naht.versuche}"
    )
    assert naht.regulaer(pid_23) == [], (
        "Slot 23:00 gilt nur 23:00-23:59 — kein Fenster ueber Ortsmitternacht: "
        f"{naht.versuche}"
    )


# ═══════════════════════════════ AC-19 ═══════════════════════════════════════

#: 08:05 Ortszeit Wien (CEST) — der 07:00-Slot liegt im Fenster.
_ALARM_JETZT = datetime(2026, 8, 20, 6, 5, tzinfo=timezone.utc)
_ALARM_PRESET = "cp-1777-alarm"


def _alarm_nutzer(kennung: str, vermerk: str | None) -> str:
    """Nutzer mit Vergleich (Ort Wien, Slot 07:00) und optional einem ROH
    geschriebenen Compare-Vermerk fuer den heutigen Morgen-Slot. KEIN
    Briefing-Anker: die Sperre haengt hier allein am Vermerk."""
    from tests.helpers.briefing_imminent_fixtures import (
        clean_uid, compare_preset, fresh_uid, ruhezeit_woanders, write_location,
        write_presets, write_user_tier,
    )

    uid = fresh_uid(kennung)
    clean_uid(uid)
    write_user_tier(uid)
    write_location(uid)
    write_presets(uid, [compare_preset(_ALARM_PRESET, morgen_stunde=7, quiet=ruhezeit_woanders())])
    tag = _ALARM_JETZT.astimezone(WIEN).date()
    if vermerk == "zugestellt":
        compare_vermerk_schreiben(uid, [compare_vermerk(_ALARM_PRESET, "morning", tag, "sent")])
    elif vermerk == "claim_lebendig":
        compare_vermerk_schreiben(uid, [compare_vermerk(
            _ALARM_PRESET, "morning", tag, None, recorded_at=_ALARM_JETZT - timedelta(minutes=1),
        )])
    return uid


@pytest.mark.parametrize("pfad", ["aenderungsalarm", "amtliche_warnung"])
def test_ac19_alarm_sperre_folgt_fenster_und_abgeschlossenem_vermerk(pfad, monkeypatch):
    """AC-19: Given ein Vergleich mit Briefing 07:00, es ist 08:05 Ortszeit /
    When ein Wetter- bzw. amtlicher Alarm ansteht / Then
      * ohne Vermerk (Briefing im Fenster noch nicht zugestellt) haelt die
        Sperre „Briefing steht bevor" (#1594) den Alarm zurueck (0 Abrufe);
      * mit abgeschlossenem Vermerk (``sent``) geht der Alarm raus (>=1 Abruf);
      * mit LEBENDIGEM Claim (Versand laeuft, ``outcome: null``) haelt die
        Sperre weiter — es kam noch nichts beim Nutzer an.

    Gemessen an der Netz-Naht hinter der Sperre (``_detect_triggered_locations``
    bzw. ``_detect``), echter Dienstlauf mit eingefrorener Uhr (die Dienste
    holen ihren Zeitpunkt selbst).

    RED-Charakter: Fehlernachweis (ohne Vermerk / Claim: heute ist 08:05 nicht
    faellig, der Alarm geht raus); Mutations-Waechter (zugestellt) — rot bei:
    Alarm-Sperre ohne Vermerk-Blick (Alarm schweigt bis 10:00 nach
    zugestelltem Briefing), ``is_recorded_or_claimed`` statt ``is_recorded``
    (Claim-Fall).
    """
    from freezegun import freeze_time

    from tests.helpers.briefing_imminent_fixtures import (
        compare_change_alert_run, compare_official_alert_run,
    )

    monkeypatch.setattr(briefing_slots, "CLAIM_TTL", 2 * 60 * 60)
    lauf_alarm = compare_change_alert_run if pfad == "aenderungsalarm" else compare_official_alert_run

    abrufe = {}
    with freeze_time(_ALARM_JETZT):
        for fall in ("ohne_vermerk", "zugestellt", "claim_lebendig"):
            uid = _alarm_nutzer(f"1777-{pfad[:6]}-{fall[:6]}", None if fall == "ohne_vermerk" else fall)
            abrufe[fall] = lauf_alarm(uid)

    assert abrufe["ohne_vermerk"] == 0, (
        f"{pfad}: Briefing 07:00 liegt um 08:05 im Fenster und ist nicht "
        f"zugestellt — die Sperre muss halten, Abrufe: {abrufe}"
    )
    assert abrufe["zugestellt"] >= 1, (
        f"{pfad}: Briefing ist zugestellt (Vermerk sent) — der Alarm muss "
        f"regulaer pruefen, Abrufe: {abrufe}"
    )
    assert abrufe["claim_lebendig"] == 0, (
        f"{pfad}: ein laufender Versand (Claim ohne Ausgang) ist noch nicht "
        f"zugestellt — die Sperre muss halten, Abrufe: {abrufe}"
    )


# ═══════════════════════════════ AC-20 ═══════════════════════════════════════

_ANZEIGE_JETZT = datetime(2026, 10, 23, 8, 30, tzinfo=PARIS).astimezone(timezone.utc)
_ANZEIGE_PRESET = "vgl-anzeige"


def test_ac20_anzeige_naechstes_briefing_folgt_fenster_und_vermerk_des_nutzers():
    """AC-20: Given ``GET /api/_internal/next-briefings`` fuer einen Vergleich
    mit Morgen 07:00 / Abend 18:00 (Paris), es ist 08:30 Ortszeit / When der
    Slot im Fenster liegt und noch nicht vermerkt ist (Nutzer B) / Then zeigt
    die Anzeige 07:00 als ueberfaellig; ist er vermerkt (Nutzer A, gleiche
    Preset-ID) / Then den Abend-Slot 18:00.

    Gemessen am echten Endpoint (Wirkort ``api/routers/internal.py``): reicht
    er den Compare-Speicher des anfragenden Nutzers nicht durch, kippt eine
    Seite. Die fruehere Festlegung „exakte Slot-Stunde, kein Nachholfenster"
    ist abgeloest.

    RED-Charakter: Fehlernachweis — heute zeigt B 18:00 statt 07:00
    ueberfaellig. Nach GREEN rot bei: Endpoint ohne Store, fremder Store.
    """
    from fastapi.testclient import TestClient
    from freezegun import freeze_time

    from api.main import app
    from app.loader import get_briefings_dir

    a, b = "nb1777-a", "nb1777-b"
    for uid in (a, b):
        ort_anlegen(uid, "ort-paris", KORSIKA)
        ordner = get_briefings_dir(uid)
        ordner.mkdir(parents=True, exist_ok=True)
        (ordner / f"{_ANZEIGE_PRESET}.json").write_text(json.dumps({
            "id": _ANZEIGE_PRESET, "kind": "vergleich", "name": "Anzeige",
            "schedule": "daily", "weekday": None, "location_ids": ["ort-paris"],
            "morning_enabled": True, "morning_time": "07:00:00",
            "evening_enabled": True, "evening_time": "18:00:00",
        }), encoding="utf-8")
    compare_vermerk_schreiben(a, [compare_vermerk(_ANZEIGE_PRESET, "morning", date(2026, 10, 23), "sent")])

    def _hole(uid: str) -> dict:
        with freeze_time(_ANZEIGE_JETZT):
            resp = TestClient(app).get("/api/_internal/next-briefings", params={"user_id": uid})
        assert resp.status_code == 200, f"{resp.status_code}: {resp.text[:300]}"
        return resp.json()["compare"][_ANZEIGE_PRESET]

    ra, rb = _hole(a), _hole(b)

    assert (rb.get("local_date"), rb.get("local_time"), rb.get("slot"), rb.get("overdue")) == (
        "2026-10-23", "07:00", "morning", True,
    ), f"B (ohne Vermerk): 07:00 liegt um 08:30 im Fenster und ist ueberfaellig: {rb!r}"
    assert (ra.get("local_date"), ra.get("local_time"), ra.get("slot"), ra.get("overdue")) == (
        "2026-10-23", "18:00", "evening", None,
    ), f"A (Morgen-Slot vermerkt): naechster Termin ist der Abend-Slot: {ra!r}"
