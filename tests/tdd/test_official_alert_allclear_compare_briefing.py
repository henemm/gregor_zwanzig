"""Entwarnung amtlicher Warnungen -- Senk-/Tombstone-Pfad des ORTSVERGLEICH-
Briefings (Issue #1441 Scheibe S2, Adversary F002/F003).

SPEC: docs/specs/modules/feat_1441_s2_entwarnung.md -- Abschnitte 5 und 6,
      AC-13, AC-14, AC-15 (Ortsvergleich), AC-5 (Zwei-Nutzer-Isolation).

Alles laeuft durch den ECHTEN Briefing-Versand
(`scheduler_dispatch_service.send_one_compare_preset`) und den ECHTEN
Alarm-Einstieg (`CompareOfficialAlertService.check_all_compare_presets`).
Ersetzt sind nur das Wetter der Vergleichs-Engine, die Quellen (echte Klassen
in der echten Registry) und die Transport-Klassen (Aufzeichner). Die amtlichen
Warnungen holt die Engine-Naht ueber denselben Produkt-Baustein wie die
Engine (`fetch_location_official_alerts`), inklusive Pro-Quelle-Mitschnitt.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from tests.helpers.transport_mitschrift import ALLE_KANAELE, aufzeichner_installieren
from tests.tdd._official_alert_allclear_fixtures import (
    IBK, Szenario, Warnquelle, basis_jetzt, compare_briefing, entwarnungen_gesamt,
    entwarnungs_sendungen, lauf_erstwarnung, quellen, schnappschuss, warnung,
)


@pytest.fixture
def mit(monkeypatch):
    return aufzeichner_installieren(monkeypatch)


def _briefing(monkeypatch, sz: Szenario, minuten: float) -> None:
    """Ortsvergleich-Briefing; Vorbedingung: wirklich zugestellt."""
    compare_briefing(monkeypatch, sz, minuten)
    snap = schnappschuss(sz.mit)
    assert snap.sendungen("email"), f"Vorbedingung: Ortsvergleich-Briefing zugestellt: {snap!r}"


def test_briefing_ohne_warnung_setzt_den_tombstone_und_der_alarm_bleibt_still(monkeypatch, mit):
    """Spec Abschnitt 6, Spiegelstrich 1 (Ortsvergleich).
    GIVEN ein Ortsvergleich-Alarm meldete Stufe 4; die gesunde meldende Quelle
          liefert die Warnung nicht mehr
    WHEN  ein ZUGESTELLTES Ortsvergleich-Briefing ohne die Warnung laeuft
    THEN  steht sofort der Tombstone (`ended_at`, ohne Zwei-Lauf-Bestaetigung,
          ohne `absent_since`) und die folgenden Alarmlaeufe bleiben still.
    """
    sz = Szenario("vergleich", monkeypatch, mit, basis_jetzt())
    with quellen(sz.x):
        lauf_erstwarnung(sz)
        sz.x.alerts = []
        _briefing(monkeypatch, sz, 5)
        nach_briefing = sz.eintrag()
        eins, zwei = sz.lauf(15), sz.lauf(30)

    assert nach_briefing.get("ended_at"), f"Briefing setzte keinen Tombstone: {nach_briefing!r}"
    assert nach_briefing.get("last_reported_value") == 0.0, f"Tombstone ohne Rang 0: {nach_briefing!r}"
    assert not nach_briefing.get("absent_since"), f"Briefing braucht keine Zwei-Lauf-Bestaetigung: {nach_briefing!r}"
    assert entwarnungen_gesamt(eins) + entwarnungen_gesamt(zwei) == 0, (
        f"Entwarnung trotz Briefing-Tombstone: {eins!r} {zwei!r}")


def test_briefing_mit_sichtbarer_warnung_loescht_absent_since(monkeypatch, mit):
    """Spec Abschnitt 6, Spiegelstrich 2 / AC-14 Umkehrung (Ortsvergleich).
    GIVEN Alarm-Lauf 1 sah die Warnung bei gesunder Quelle nicht (`absent_since`)
    WHEN  das zugestellte Briefing sie bei gesunder Quelle noch mit Stufe 4 zeigt
    THEN  ist `absent_since` geloescht, kein Tombstone; Alarm-Lauf 2 bleibt still,
          erst Alarm-Lauf 3 meldet genau EINE Entwarnung "beendet" je Kanal.
    """
    sz = Szenario("vergleich", monkeypatch, mit, basis_jetzt())
    with quellen(sz.x):
        lauf_erstwarnung(sz)
        warn = list(sz.x.alerts)
        sz.x.alerts = []
        lauf1 = sz.lauf(10)
        nach_lauf1 = sz.eintrag()
        sz.x.alerts = warn
        _briefing(monkeypatch, sz, 15)
        nach_briefing = sz.eintrag()
        sz.x.alerts = []
        lauf2, lauf3 = sz.lauf(20), sz.lauf(30)

    assert nach_lauf1.get("absent_since"), f"Vorbedingung: `absent_since` nach Lauf 1: {nach_lauf1!r}"
    assert not nach_briefing.get("absent_since"), f"`absent_since` nicht geloescht: {nach_briefing!r}"
    assert not nach_briefing.get("ended_at"), f"Tombstone trotz gezeigter Warnung: {nach_briefing!r}"
    assert entwarnungen_gesamt(lauf1) + entwarnungen_gesamt(lauf2) == 0, f"{lauf1!r} {lauf2!r}"
    for kanal in ALLE_KANAELE:
        assert len(entwarnungs_sendungen(lauf3, kanal)) == 1, f"Lauf 3: 'beendet' auf {kanal}: {lauf3!r}"


def test_briefing_senkt_nur_das_gedaechtnis_des_eigenen_nutzers(monkeypatch, mit):
    """AC-5 / CLAUDE.md Multi-User: zwei Nutzer, dieselbe Lage, nur Nutzer A
    bekommt ein Briefing ohne die Warnung.
    THEN  A traegt den Tombstone, Bs Gedaechtnis ist unveraendert, und B (nicht
          informiert) erhaelt nach zwei Laeufen die Entwarnung "beendet".
    """
    t0 = basis_jetzt()
    a = Szenario("vergleich", monkeypatch, mit, t0)
    b = Szenario("vergleich", monkeypatch, mit, t0)
    b.x = a.x
    with quellen(a.x):
        lauf_erstwarnung(a)
        lauf_erstwarnung(b)
        b_vorher = b.eintrag()
        a.x.alerts = []
        _briefing(monkeypatch, a, 5)
        a_nach, b_nach = a.eintrag(), b.eintrag()
        b.lauf(15)
        b_zwei = b.lauf(30)

    assert a.uid != b.uid
    assert a_nach.get("ended_at"), f"Nutzer A: Briefing setzte keinen Tombstone: {a_nach!r}"
    assert b_nach == b_vorher, f"Nutzer B: Gedaechtnis durch As Briefing veraendert: {b_vorher!r} -> {b_nach!r}"
    assert entwarnungs_sendungen(b_zwei, "email"), f"Nutzer B: 'beendet' erwartet: {b_zwei!r}"


def test_teilausfall_der_meldenden_quelle_im_briefing_senkt_nicht(monkeypatch, mit):
    """Adversary F002 / AC-13 Gegenprobe mit TEILAUSFALL.
    GIVEN gemeldet Stufe 4 von X; im Briefing faellt NUR X aus, Y antwortet
          gesund und leer (Aggregat "nicht abrufbar" ist dabei False)
    WHEN  das Briefing zugestellt ist und X danach gesund Stufe 2 liefert
    THEN  hat das Briefing nichts gesenkt (kein Tombstone, Stufe 4) und der
          naechste Alarmlauf sendet die Entwarnung 4 -> 2.
    """
    from services.official_alerts import get_official_alerts_with_status

    sz = Szenario("vergleich", monkeypatch, mit, basis_jetzt())
    y = Warnquelle("quelle-y", nur_bei=sz.x.nur_bei)
    with quellen(sz.x, y):
        lauf_erstwarnung(sz)
        sz.x.ausfall = "exception"
        _alerts, aggregat = get_official_alerts_with_status(*IBK)
        _briefing(monkeypatch, sz, 5)
        nach_briefing = sz.eintrag()
        sz.x.ausfall = None
        sz.x.alerts = [sz.warnung(2)]
        lauf = sz.lauf(15)

    assert aggregat is False, "Vorbedingung: Teilausfall setzt das Aggregat NICHT"
    assert not nach_briefing.get("ended_at"), f"Teilausfall setzte einen Tombstone: {nach_briefing!r}"
    assert nach_briefing.get("last_reported_value") == 4.0, f"Teilausfall senkte: {nach_briefing!r}"
    assert entwarnungs_sendungen(lauf, "email"), f"Entwarnung 4 -> 2 erwartet: {lauf!r}"


def test_briefing_erstmeldung_im_ortsvergleich_ermoeglicht_die_spaetere_entwarnung(monkeypatch, mit):
    """AC-15 (Ortsvergleich): eine ZUERST per Ortsvergleich-Briefing gemeldete
    Warnung traegt danach `source` und `scope`; die spaetere Absenkung ergibt
    eine Entwarnung.
    """
    sz = Szenario("vergleich", monkeypatch, mit, basis_jetzt())
    with quellen(sz.x):
        _briefing(monkeypatch, sz, 0)
        eintrag = sz.eintrag()
        sz.x.alerts = [sz.warnung(2)]
        lauf = sz.lauf(15)

    assert eintrag.get("source") == "quelle-x", f"`source` fehlt/falsch: {eintrag!r}"
    assert eintrag.get("scope") == ["loc-ibk"], f"`scope` fehlt/falsch: {eintrag!r}"
    assert entwarnungs_sendungen(lauf, "email"), f"Absenkung nach Briefing-Erstmeldung: {lauf!r}"


def test_vergleichs_engine_schneidet_die_quellen_gesundheit_ihres_abrufs_mit():
    """Adversary F002: die echte `ComparisonEngine.run` legt das Pro-Quelle-
    Ergebnis DESSELBEN Abrufs am Ortsergebnis ab (Grundlage des Briefing-
    Senkpfads) -- nicht erst eine Nachfrage nach der Zustellung."""
    from app.profile import ActivityProfile
    from app.user import SavedLocation
    from services.comparison_engine import ComparisonEngine

    t0 = basis_jetzt()
    x = Warnquelle("quelle-x")
    x.alerts = [warnung(4, quelle=x, von=t0 - timedelta(hours=1), bis=t0 + timedelta(hours=20))]
    y = Warnquelle("quelle-y")
    y.ausfall = "fetch_failed"
    ort = SavedLocation(id="loc-ibk", name="Innsbruck", lat=IBK[0], lon=IBK[1],
                        elevation_m=574, timezone="Europe/Vienna")
    with quellen(x, y):
        result = ComparisonEngine.run(
            [ort], time_window=(9, 16), target_date=date.today() + timedelta(days=1),
            profile=ActivityProfile.ALLGEMEIN,
        )
    query = result.locations[0].official_alert_query
    assert query is not None, "Kein Pro-Quelle-Mitschnitt am Ortsergebnis"
    assert query.sources["quelle-x"][0] is True and len(query.sources["quelle-x"][1]) == 1, query.sources
    assert query.sources["quelle-y"][0] is False, query.sources
