"""TDD RED -- Entwarnung bei amtlichen Warnungen: Erkennung und Gedaechtnis
(Issue #1441 Scheibe S2).

SPEC: docs/specs/modules/feat_1441_s2_entwarnung.md
      AC-1, AC-2, AC-5 .. AC-11, AC-13 .. AC-15, AC-17
      (Versandpfade/Kanaele/Darstellung: test_official_alert_allclear_channels.py)

Alles laeuft durch die ECHTEN Einstiege (`TripAlertService.check_all_trips`,
`CompareOfficialAlertService.check_all_compare_presets`, Trip-Briefing
`_send_trip_report_outcome`). Ersetzt sind nur die Wetter-Snapshot-Naht, die
Quellen (echte Klassen in der echten Registry) und die vier Transport-Klassen
(Aufzeichner). Aufbau: `tests/tdd/_official_alert_allclear_fixtures.py`.

RED heute: es gibt keine Entwarnung -- weder Erkennung (gesenkt / vorzeitig
beendet) noch `absent_since`/`ended_at` im Gedaechtnis, noch `source`/
`scope`/`level` in den Eintraegen, noch GC abgelaufener Eintraege.

Negative ACs ("keine Entwarnung bei ...") sind unter dem heutigen Verhalten
trivial gruen (es gibt nie eine Entwarnung). Jeder solche Test traegt deshalb
im SELBEN Test eine Gegenprobe (eigener Nutzer bzw. Folgelauf), die eine
Entwarnung VERLANGT und heute rot ist -- markiert mit "Gegenprobe".
"""
from __future__ import annotations

import re
from datetime import timedelta

import pytest

from tests.helpers.transport_mitschrift import ALLE_KANAELE, aufzeichner_installieren
from tests.tdd._official_alert_allclear_fixtures import (
    AUSFALLARTEN, FLAECHEN, LAT, LAT_B, LON, LON_B, Szenario, Warnquelle,
    amtliche_eintraege, basis_jetzt, compare_lauf, compare_nutzer, entwarnungen_gesamt,
    entwarnungs_sendungen, fehlschlag_installieren, geometrie_zwei_segmente,
    lauf_erstwarnung, quellen, trip_briefing, warnung,
)

#: "Stufe 4 -> 2" -- alte und neue Stufe als Uebergang (Spec Abschnitt 7).
VIER_AUF_ZWEI = re.compile(r"4\s*(?:→|->|>)\s*2")


@pytest.fixture
def mit(monkeypatch):
    return aufzeichner_installieren(monkeypatch)


def _plain(sendung: dict) -> str:
    return str(sendung.get("plain_text_body") or "")


def _gesenkt_assert(snap, *, ac: str) -> None:
    """Genau EINE Entwarnung je Kanal, Mail-Klartext nennt Gefahr, Ort und 4 -> 2."""
    for kanal in ALLE_KANAELE:
        ew = entwarnungs_sendungen(snap, kanal)
        assert len(ew) == 1, f"{ac}: genau eine Entwarnung auf {kanal} erwartet, erhalten {len(ew)} -- {snap!r}"
    mail = entwarnungs_sendungen(snap, "email")[0]
    assert "Entwarnung" in mail["subject"], f"{ac}: Betreff ohne 'Entwarnung': {mail['subject']!r}"
    assert VIER_AUF_ZWEI.search(_plain(mail)), f"{ac}: Klartext ohne 'Stufe 4 -> 2': {_plain(mail)!r}"
    assert "Hitze" in _plain(mail), f"{ac}: Klartext ohne Gefahr: {_plain(mail)!r}"


# ═══════════════════════════ AC-1 ═══════════════════════════════════════════


@pytest.mark.parametrize("flaeche", FLAECHEN)
def test_ac1_gesenkte_warnung_ergibt_entwarnung_und_senkt_das_gedaechtnis(monkeypatch, mit, flaeche):
    """AC-1 [Gesenkt].
    GIVEN eine per Alarm gemeldete amtliche Warnung der Stufe 4 und die meldende
          Quelle antwortet im aktuellen Lauf erfolgreich mit Stufe 2 fuer dieselbe
          Gefahr, denselben Ort und denselben Zeitraum
    WHEN  der Alarm-Lauf laeuft (Trip bzw. Ortsvergleich)
    THEN  kommt genau EINE Entwarnung "Stufe 4 -> 2" mit Gefahr und Ort, und das
          Gedaechtnis steht danach auf Stufe 2 (`last_reported_value`/`level`).
    """
    sz = Szenario(flaeche, monkeypatch, mit, basis_jetzt())
    with quellen(sz.x):
        lauf_erstwarnung(sz)
        sz.x.alerts = [sz.warnung(2)]
        zwei = sz.lauf(15)

    _gesenkt_assert(zwei, ac="AC-1")
    mail_plain = _plain(entwarnungs_sendungen(zwei, "email")[0])
    ort = "Segment 1" if flaeche == "trip" else "Innsbruck"
    assert ort in mail_plain, f"AC-1: Ort/Etappe fehlt im Klartext: {mail_plain!r}"
    eintrag = sz.eintrag()
    assert eintrag.get("last_reported_value") == 2.0, f"AC-1: Gedaechtnis nicht gesenkt: {eintrag!r}"
    assert eintrag.get("level") == 2, f"AC-1: `level` nicht auf 2 gesenkt: {eintrag!r}"


# ═══════════════════════════ AC-2 ═══════════════════════════════════════════


@pytest.mark.parametrize("flaeche", FLAECHEN)
def test_ac2_vorzeitig_beendet_braucht_zwei_laeufe_bei_gesunder_quelle(monkeypatch, mit, flaeche):
    """AC-2 [Vorzeitig beendet, zwei Laeufe].
    GIVEN eine gemeldete Warnung mit `valid_to` in der Zukunft und die meldende
          Quelle antwortet erfolgreich, enthaelt sie aber nicht mehr
    WHEN  Lauf 1 stattfindet
    THEN  bleibt es still und `absent_since` ist gesetzt;
    WHEN  Lauf 2 die Abwesenheit bestaetigt
    THEN  kommt genau eine Entwarnung "beendet" und das Gedaechtnis traegt den
          Tombstone `ended_at`.
    """
    sz = Szenario(flaeche, monkeypatch, mit, basis_jetzt())
    with quellen(sz.x):
        lauf_erstwarnung(sz)
        sz.x.alerts = []
        eins = sz.lauf(15)
        nach_eins = sz.eintrag()
        zwei = sz.lauf(30)

    assert entwarnungen_gesamt(eins) == 0, f"AC-2: Lauf 1 muss still bleiben: {eins!r}"
    assert nach_eins.get("absent_since"), f"AC-2: `absent_since` nach Lauf 1 nicht gesetzt: {nach_eins!r}"
    assert not nach_eins.get("ended_at"), f"AC-2: Tombstone schon nach Lauf 1: {nach_eins!r}"
    for kanal in ALLE_KANAELE:
        ew = entwarnungs_sendungen(zwei, kanal)
        assert len(ew) == 1, f"AC-2: genau eine Entwarnung auf {kanal} nach Lauf 2: {zwei!r}"
    assert "beendet" in _plain(entwarnungs_sendungen(zwei, "email")[0]), "AC-2: Mail nennt nicht 'beendet'"
    assert sz.eintrag().get("ended_at"), f"AC-2: Tombstone fehlt: {sz.eintrag()!r}"


def test_ac2_wiederauftauchen_zwischen_den_laeufen_loescht_absent_since(monkeypatch, mit):
    """AC-2 (Wiederauftauchen).
    GIVEN Lauf A sieht die Warnung bei gesunder Quelle nicht (`absent_since` gesetzt)
    WHEN  sie in Lauf B unveraendert wieder auftaucht und in Lauf C erneut fehlt
    THEN  ist `absent_since` nach Lauf B geloescht und Lauf C bleibt still (C ist
          der ERSTE Lauf einer neuen Abwesenheit, keine Bestaetigung).
    """
    sz = Szenario("trip", monkeypatch, mit, basis_jetzt())
    with quellen(sz.x):
        lauf_erstwarnung(sz)
        warn = list(sz.x.alerts)
        sz.x.alerts = []
        a = sz.lauf(15)
        nach_a = sz.eintrag()
        sz.x.alerts = warn
        b = sz.lauf(30)
        nach_b = sz.eintrag()
        sz.x.alerts = []
        c = sz.lauf(45)
        nach_c = sz.eintrag()

    assert nach_a.get("absent_since"), f"AC-2: `absent_since` nach Lauf A nicht gesetzt: {nach_a!r}"
    assert not nach_b.get("absent_since"), f"AC-2: `absent_since` nach Wiederauftauchen nicht geloescht: {nach_b!r}"
    assert entwarnungen_gesamt(a) == entwarnungen_gesamt(b) == entwarnungen_gesamt(c) == 0, (
        f"AC-2: keine Entwarnung ohne zwei AUFEINANDERFOLGENDE Abwesenheiten: {a!r} {b!r} {c!r}")
    assert nach_c.get("absent_since") and not nach_c.get("ended_at"), f"AC-2: Lauf C: {nach_c!r}"


# ═══════════════════════════ AC-5 ═══════════════════════════════════════════


@pytest.mark.parametrize("flaeche", FLAECHEN)
def test_ac5_entwarnung_nur_beim_nutzer_dem_die_warnung_gemeldet_wurde(monkeypatch, mit, flaeche):
    """AC-5 [Zwei-Nutzer-Isolation] -- zwei echte Nutzerkennungen, getrennte
    Datenordner, nie "default".
    GIVEN Nutzer A und B mit je eigenem Gedaechtnis; NUR A bekam die Stufe-4-
          Warnung gemeldet. B hat alle Kanal-Schwellen auf "mittel" (eine neue
          Stufe-2-Warnung erreicht B also nicht; eine faelschlich zu B
          durchgereichte Entwarnung von "hoch" wuerde B dagegen erreichen)
    WHEN  die Quelle auf Stufe 2 senkt und beide Nutzer ihren Alarmlauf haben
    THEN  erhaelt nur A die Entwarnung, B bekommt nichts, und Bs Gedaechtnis
          bleibt unveraendert.
    """
    t0 = basis_jetzt()
    a = Szenario(flaeche, monkeypatch, mit, t0)
    mittel = {k: "MODERATE" for k in ALLE_KANAELE}
    b = Szenario(flaeche, monkeypatch, mit, t0, schwellen=mittel)
    assert a.uid != b.uid and "default" not in (a.uid, b.uid)
    b.x = a.x  # dieselbe amtliche Lage fuer beide Nutzer
    with quellen(a.x):
        lauf_erstwarnung(a)
        b_vorher = amtliche_eintraege(b.uid, b.entity)
        a.x.alerts = [a.warnung(2)]
        snap_a = a.lauf(15)
        snap_b = b.lauf(15)

    _gesenkt_assert(snap_a, ac="AC-5 (Nutzer A)")
    assert all(not snap_b.sendungen(k) for k in ALLE_KANAELE), f"AC-5: Nutzer B bekam etwas: {snap_b!r}"
    assert amtliche_eintraege(b.uid, b.entity) == b_vorher, "AC-5: Gedaechtnis von B veraendert"


# ═══════════════════════════ AC-6 ═══════════════════════════════════════════


@pytest.mark.parametrize("ausfall", AUSFALLARTEN)
def test_ac6_ausfall_der_meldenden_quelle_ist_keine_entwarnung(monkeypatch, mit, ausfall):
    """AC-6 [Teilausfall ist keine Entwarnung].
    GIVEN die meldende Quelle X faellt aus (Exception / fetch_failed /
          not_covered / fetch_incomplete), eine zweite zustaendige Quelle Y
          liefert gesund LEER -- das Aggregat-`unavailable` ist dabei False
    WHEN  zwei Alarmlaeufe stattfinden
    THEN  entsteht keine Entwarnung, das Gedaechtnis bleibt unveraendert.
    Gegenprobe (heute rot): antwortet X danach gesund leer, kommt nach zwei
    Laeufen die Entwarnung "beendet".
    """
    from freezegun import freeze_time
    from services.official_alerts import get_official_alerts_with_status

    sz = Szenario("trip", monkeypatch, mit, basis_jetzt())
    y = Warnquelle("quelle-y")
    with quellen(sz.x, y):
        lauf_erstwarnung(sz)
        vorher = sz.eintraege()
        sz.x.ausfall = ausfall
        with freeze_time(sz.zeit(15)):
            _alerts, unavailable = get_official_alerts_with_status(LAT, LON)
        assert unavailable is False, "Vorbedingung: Aggregat-`unavailable` muss False sein (Y kompensiert)"
        eins, zwei = sz.lauf(15), sz.lauf(30)
        nach_ausfall = sz.eintraege()
        # Gegenprobe: X wieder gesund, Warnung fehlt -> zwei Laeufe -> "beendet".
        sz.x.ausfall = None
        sz.x.alerts = []
        drei, vier = sz.lauf(45), sz.lauf(60)

    assert entwarnungen_gesamt(eins) + entwarnungen_gesamt(zwei) == 0, (
        f"AC-6 ({ausfall}): Ausfall der meldenden Quelle ergab eine Entwarnung: {eins!r} {zwei!r}")
    assert nach_ausfall == vorher, f"AC-6 ({ausfall}): Gedaechtnis veraendert: {vorher!r} -> {nach_ausfall!r}"
    assert entwarnungen_gesamt(drei) == 0
    assert entwarnungs_sendungen(vier, "email"), (
        f"AC-6 Gegenprobe ({ausfall}): gesunde, leere meldende Quelle muss nach zwei Laeufen "
        f"eine Entwarnung ergeben: {vier!r}")


# ═══════════════════════════ AC-7 ═══════════════════════════════════════════


def test_ac7_wechsel_der_besten_quelle_ist_keine_entwarnung(monkeypatch, mit):
    """AC-7 [Quellenwechsel der besten Quelle] -- verglichen wird auf dem
    Pre-Merge-Satz der MELDENDEN Quelle, nie auf dem zusammengefuehrten Satz.
    GIVEN X meldete Stufe 4; Y liefert dieselbe Identitaet+Gefahr mit Stufe 2
    WHEN  (i) X liefert weiter Stufe 4, (ii) X faellt aus und Y ist damit die
          "beste" Quelle (zusammengefuehrter Satz zeigt nur noch Stufe 2)
    THEN  entsteht in beiden Faellen keine Entwarnung.
    Gegenprobe (heute rot): liefert X selbst Stufe 2, kommt die Entwarnung 4 -> 2.
    """
    sz = Szenario("trip", monkeypatch, mit, basis_jetzt())
    y = Warnquelle("quelle-y")
    y.alerts = [warnung(2, quelle=y, von=sz.von, bis=sz.bis)]
    with quellen(sz.x, y):
        lauf_erstwarnung(sz)
        i = sz.lauf(15)
        sz.x.ausfall = "exception"
        ii_a, ii_b = sz.lauf(30), sz.lauf(45)
        sz.x.ausfall = None
        sz.x.alerts = [sz.warnung(2)]
        gegenprobe = sz.lauf(60)

    assert entwarnungen_gesamt(i) == 0, f"AC-7 (i): X liefert weiter 4 -- keine Entwarnung: {i!r}"
    assert entwarnungen_gesamt(ii_a) + entwarnungen_gesamt(ii_b) == 0, (
        f"AC-7 (ii): Y ist nur wegen X-Ausfall die beste Quelle -- keine Entwarnung: {ii_a!r} {ii_b!r}")
    assert entwarnungs_sendungen(gegenprobe, "email"), (
        f"AC-7 Gegenprobe: X selbst liefert 2 -> Entwarnung 4 -> 2 erwartet: {gegenprobe!r}")


# ═══════════════════════════ AC-8 ═══════════════════════════════════════════


def test_ac8a_neuausgabe_mit_neuem_zeitraum_ist_keine_entwarnung(monkeypatch, mit):
    """AC-8 (a) [Neuausgabe/Folgeperiode].
    GIVEN X meldete Stufe 4 fuer den Zeitraum A; die Behoerde gibt die Warnung
          neu heraus (Zeitraum B, ueberlappend, neuer Gedaechtnis-Schluessel),
          gleiche Stufe 4 -- A selbst liefert X nicht mehr
    WHEN  zwei Alarmlaeufe stattfinden
    THEN  keine Entwarnung (Abgleich ueber Identitaet+Gefahr, nicht ueber den
          vollen Schluessel).
    Gegenprobe (heute rot): sinkt die Neuausgabe B auf Stufe 2 -> Entwarnung.
    """
    t0 = basis_jetzt()
    sz = Szenario("trip", monkeypatch, mit, t0, bis_stunden=5)
    neu_von, neu_bis = t0 + timedelta(minutes=10), t0 + timedelta(hours=29)
    with quellen(sz.x):
        lauf_erstwarnung(sz)
        sz.x.alerts = [sz.warnung(4, von=neu_von, bis=neu_bis)]
        eins, zwei = sz.lauf(15), sz.lauf(30)
        sz.x.alerts = [sz.warnung(2, von=neu_von, bis=neu_bis)]
        gegenprobe = sz.lauf(45)

    assert entwarnungen_gesamt(eins) + entwarnungen_gesamt(zwei) == 0, (
        f"AC-8a: Neuausgabe mit gleicher Stufe ergab eine Entwarnung: {eins!r} {zwei!r}")
    assert entwarnungs_sendungen(gegenprobe, "email"), (
        f"AC-8a Gegenprobe: ueberlappende Neuausgabe mit Stufe 2 muss Entwarnung ergeben: {gegenprobe!r}")


def test_ac8b_vergangenes_trip_segment_ist_keine_entwarnung(monkeypatch, mit):
    """AC-8 (b) [vergangenes Segment].
    GIVEN die Warnung wurde fuer Segment 1 (Punkt A) gemeldet und gilt dort
          noch 20 h; Segment 1 ist inzwischen vorbei, der Lauf fragt nur noch
          Segment 2 (Punkt B) ab, wo dieselbe, gesunde Quelle leer antwortet
    WHEN  zwei Alarmlaeufe stattfinden
    THEN  keine Entwarnung -- der Eintrag wird nicht bewertet.
    Gegenprobe (heute rot, eigener Nutzer): bleibt Segment 1 aktiv und die
    Quelle antwortet DORT leer, kommt nach zwei Laeufen "beendet".
    """
    t0 = basis_jetzt()
    sz = Szenario("trip", monkeypatch, mit, t0, geometrie=geometrie_zwei_segmente(t0))
    sz.x.nur_bei = (round(LAT, 3), round(LON, 3))
    assert (round(LAT_B, 3), round(LON_B, 3)) != sz.x.nur_bei
    with quellen(sz.x):
        lauf_erstwarnung(sz)
        eins, zwei = sz.lauf(20), sz.lauf(35)  # Segment 1 endete t0+10 min

    assert sz.x.fetch_calls >= 3, "Vorbedingung: die Laeufe haben die Quelle befragt"
    assert entwarnungen_gesamt(eins) + entwarnungen_gesamt(zwei) == 0, (
        f"AC-8b: vergangenes Segment ergab eine Entwarnung: {eins!r} {zwei!r}")

    kontrolle = Szenario("trip", monkeypatch, mit, t0)
    with quellen(kontrolle.x):
        lauf_erstwarnung(kontrolle)
        kontrolle.x.alerts = []
        kontrolle.lauf(20)
        k2 = kontrolle.lauf(35)
    assert entwarnungs_sendungen(k2, "email"), (
        f"AC-8b Gegenprobe: aktives Segment, gesunde Quelle leer -> 'beendet' erwartet: {k2!r}")


def test_ac8c_tagesfenster_ende_im_ortsvergleich_ist_keine_entwarnung(monkeypatch, mit):
    """AC-8 (c) [Tagesfenster-Ende im Ortsvergleich].
    GIVEN ein Ortsvergleich meldete um 08:00 Ortszeit eine Stufe-4-Warnung, die
          erst ab 20:00 Ortszeit gilt (Tagesfenster bis 21 Uhr); danach endet das
          Tagesfenster um 12 Uhr -- die Warnung liegt ausserhalb des abgefragten
          Fensters, die Quelle liefert sie aber gesund weiter
    WHEN  zwei Alarmlaeufe stattfinden
    THEN  keine Entwarnung (nicht ueberlappende Eintraege werden nicht bewertet).
    Gegenprobe (heute rot): Fenster wieder bis 21 Uhr, Warnung auf Stufe 2
    -> Entwarnung 4 -> 2.
    """
    from datetime import datetime, timezone

    from tests.helpers.sms_empfaenger import profil_rueckadresse
    from tests.tdd._compare_kette_fixtures import preset_ablegen
    from tests.tdd._official_alert_allclear_fixtures import IBK, compare_entity

    t0 = datetime(2026, 7, 8, 6, 0, tzinfo=timezone.utc)  # 08:00 Europe/Vienna
    uid, preset = compare_nutzer(
        monkeypatch, morning_time="14:00:00", evening_time="20:00:00",
        day_window_start_hour=4, day_window_end_hour=21,
    )
    # Feste Uhr in der Vergangenheit: die Rueckadresse relativ zu t0 lernen,
    # sonst laege sie "in der Zukunft" und Premium-SMS waere gesperrt (#2231).
    profil_rueckadresse(uid, "+490000000008", gelernt_am=t0 - timedelta(minutes=5))
    x = Warnquelle("quelle-x", nur_bei=IBK)
    von, bis = t0 + timedelta(hours=12), t0 + timedelta(hours=17)  # 20:00-01:00 Ortszeit
    x.alerts = [warnung(4, quelle=x, von=von, bis=bis)]
    with quellen(x):
        compare_lauf(uid, t0)
        erst = _snap(mit)
        assert erst.sendungen("email"), f"Vorbedingung: Erstwarnung kam an: {erst!r}"
        assert erst.sendungen("premium_sms"), f"Vorbedingung: Premium-SMS offen: {erst!r}"
        preset_ablegen(uid, {**preset, "day_window_end_hour": 12})
        compare_lauf(uid, t0 + timedelta(minutes=15))
        eins = _snap(mit)
        compare_lauf(uid, t0 + timedelta(minutes=30))
        zwei = _snap(mit)
        vorher = amtliche_eintraege(uid, compare_entity(preset))
        preset_ablegen(uid, preset)
        x.alerts = [warnung(2, quelle=x, von=von, bis=bis)]
        compare_lauf(uid, t0 + timedelta(minutes=45))
        gegenprobe = _snap(mit)

    assert entwarnungen_gesamt(eins) + entwarnungen_gesamt(zwei) == 0, (
        f"AC-8c: Tagesfenster-Ende ergab eine Entwarnung: {eins!r} {zwei!r}")
    assert vorher and not any(e.get("ended_at") for e in vorher.values()), f"AC-8c: Tombstone: {vorher!r}"
    assert entwarnungs_sendungen(gegenprobe, "email"), (
        f"AC-8c Gegenprobe: ueberlappendes Fenster mit Stufe 2 -> Entwarnung erwartet: {gegenprobe!r}")


def _snap(mit):
    from tests.tdd._official_alert_allclear_fixtures import schnappschuss

    return schnappschuss(mit)


# ═══════════════════════════ AC-9 ═══════════════════════════════════════════


def test_ac9_planmaessiger_ablauf_ist_keine_entwarnung_und_der_eintrag_wird_aufgeraeumt(monkeypatch, mit):
    """AC-9 [Planmaessiger Ablauf ist keine Entwarnung -- Tech-Lead-Entscheid].
    GIVEN eine gemeldete Warnung, deren `valid_to` erreicht bzw. ueberschritten ist
    WHEN  sie in den naechsten Laeufen nicht mehr erscheint (Quelle gesund leer)
    THEN  keine Entwarnung, und der abgelaufene Gedaechtnis-Eintrag ist nach dem
          Lauf entfernt (GC).
    Gegenprobe (heute rot, eigener Nutzer): `valid_to` weit in der Zukunft ->
    nach zwei Laeufen "beendet".
    """
    t0 = basis_jetzt()
    sz = Szenario("trip", monkeypatch, mit, t0, bis_stunden=0.5)
    with quellen(sz.x):
        lauf_erstwarnung(sz)
        sz.x.alerts = []
        genau, danach = sz.lauf(30), sz.lauf(45)  # valid_to == jetzt, dann < jetzt

    assert entwarnungen_gesamt(genau) + entwarnungen_gesamt(danach) == 0, (
        f"AC-9: planmaessiger Ablauf ergab eine Entwarnung: {genau!r} {danach!r}")
    assert sz.eintraege() == {}, f"AC-9: abgelaufener Eintrag nicht aufgeraeumt (GC): {sz.eintraege()!r}"

    kontrolle = Szenario("trip", monkeypatch, mit, t0)
    with quellen(kontrolle.x):
        lauf_erstwarnung(kontrolle)
        kontrolle.x.alerts = []
        kontrolle.lauf(30)
        k2 = kontrolle.lauf(45)
    assert entwarnungs_sendungen(k2, "email"), f"AC-9 Gegenprobe: 'beendet' erwartet: {k2!r}"


def test_ac9_gc_raeumt_nur_abgelaufene_eintraege_und_reset_schont_die_uebrigen(monkeypatch, mit):
    """AC-9 [GC].
    GIVEN zwei vom Produkt geschriebene `official_alert:`-Eintraege desselben
          Trips -- Hitze (gilt bis t0+30 min) und Sturm (gilt bis t0+20 h)
    WHEN  ein Alarmlauf nach Ablauf der Hitzewarnung stattfindet
    THEN  ist der abgelaufene Eintrag entfernt, der zukuenftige bleibt -- auch
          nach `AlertStateService.reset()` (Briefing-Reset schont amtliche Eintraege).
    """
    from services.alert_state import AlertStateService

    t0 = basis_jetzt()
    sz = Szenario("trip", monkeypatch, mit, t0, bis_stunden=0.5)
    sturm = sz.warnung(3, hazard="wind_gust", bis=t0 + timedelta(hours=20))
    sz.x.alerts = sz.x.alerts + [sturm]
    with quellen(sz.x):
        lauf_erstwarnung(sz)
        assert sz.eintraege() and sz.eintraege(hazard="wind_gust"), "Vorbedingung: beide Eintraege geschrieben"
        sz.x.alerts = [sturm]
        sz.lauf(45)

    assert sz.eintraege() == {}, f"AC-9 GC: abgelaufene Hitzewarnung nicht entfernt: {sz.eintraege()!r}"
    assert sz.eintraege(hazard="wind_gust"), "AC-9 GC: zukuenftiger Eintrag darf nicht entfernt werden"
    AlertStateService(user_id=sz.uid).reset(sz.entity)
    assert sz.eintraege(hazard="wind_gust"), "AC-9: reset() muss zukuenftige amtliche Eintraege schonen"


# ═══════════════════════════ AC-10 ══════════════════════════════════════════


@pytest.mark.parametrize("flaeche", FLAECHEN)
def test_ac10_entwarnung_kommt_nur_einmal_und_wiederanstieg_ist_normale_warnung(monkeypatch, mit, flaeche):
    """AC-10 [Nur einmal].
    GIVEN eine zugestellte Entwarnung 4 -> 2
    WHEN  der naechste Lauf dieselbe Lage (Stufe 2) sieht
    THEN  kommt keine zweite Entwarnung;
    WHEN  die Stufe spaeter wieder auf 4 steigt
    THEN  ist das eine ganz normale neue Warnung (ohne Entwarnungs-Abschnitt).
    """
    sz = Szenario(flaeche, monkeypatch, mit, basis_jetzt())
    with quellen(sz.x):
        lauf_erstwarnung(sz)
        sz.x.alerts = [sz.warnung(2)]
        erste = sz.lauf(15)
        wieder = sz.lauf(30)
        sz.x.alerts = [sz.warnung(4)]
        anstieg = sz.lauf(45)

    assert entwarnungs_sendungen(erste, "email"), f"AC-10: erste Entwarnung fehlt: {erste!r}"
    assert entwarnungen_gesamt(wieder) == 0 and not wieder.sendungen("email"), (
        f"AC-10: zweite Entwarnung bei gleicher Lage: {wieder!r}")
    assert anstieg.sendungen("email") and anstieg.sendungen("sms"), (
        f"AC-10: Wiederanstieg auf 4 muss als normale Warnung kommen: {anstieg!r}")
    assert entwarnungen_gesamt(anstieg) == 0, f"AC-10: Wiederanstieg traegt Entwarnungs-Abschnitt: {anstieg!r}"


# ═══════════════════════════ AC-11 ══════════════════════════════════════════


@pytest.mark.parametrize("flaeche", FLAECHEN)
def test_ac11_fehlversand_schreibt_nichts_und_wird_wiederholt(monkeypatch, mit, flaeche):
    """AC-11 [Fehlversand wiederholt] (ADR-0086).
    GIVEN die Entwarnung 4 -> 2 entsteht, der Versand scheitert auf ALLEN Kanaelen
    WHEN  der naechste Lauf (nach Ablauf des Wiederholungs-Backoffs, 30 min) mit
          funktionierendem Transport stattfindet
    THEN  war das Gedaechtnis nach dem Fehlversand unveraendert (Stufe 4), und
          die Entwarnung wird jetzt zugestellt; danach steht das Gedaechtnis auf 2.
    """
    sz = Szenario(flaeche, monkeypatch, mit, basis_jetzt())
    with quellen(sz.x):
        lauf_erstwarnung(sz)
        sz.x.alerts = [sz.warnung(2)]
        versuche = fehlschlag_installieren(monkeypatch)
        sz.lauf(15)
        nach_fehlversand = sz.eintrag()
        neu = aufzeichner_installieren(monkeypatch)
        sz.mit = neu
        zweiter = sz.lauf(15 + 31)

    assert sum(versuche.values()) > 0, (
        f"AC-11: die Entwarnung muss ueberhaupt versucht worden sein: {versuche!r}")
    assert nach_fehlversand.get("last_reported_value") == 4.0, (
        f"AC-11: Fehlversand darf das Gedaechtnis nicht senken: {nach_fehlversand!r}")
    assert entwarnungs_sendungen(zweiter, "email"), f"AC-11: Wiederholung brachte keine Entwarnung: {zweiter!r}"
    assert sz.eintrag().get("last_reported_value") == 2.0, f"AC-11: nach Zustellung gesenkt: {sz.eintrag()!r}"


# ═══════════════════════════ AC-13 ══════════════════════════════════════════


def test_ac13_briefing_mit_gesunder_quelle_informiert_nicht_abrufbar_nicht(monkeypatch, mit):
    """AC-13 [Briefing informiert -- keine Entwarnung] (PO 15.10.).
    GIVEN nach einem Alarm Stufe 4 zeigt ein ZUGESTELLTES Briefing bei gesunder
          meldender Quelle bereits Stufe 2
    WHEN  der naechste Alarmlauf stattfindet
    THEN  keine Entwarnung (das Briefing hat das Gedaechtnis auf 2 gesenkt).
    Gegenprobe 1 (heute rot): das Briefing zeigte "nicht abrufbar" (meldende
    Quelle ausgefallen) -> der naechste Lauf bei gesunder Quelle (Stufe 2)
    sendet die Entwarnung.
    Gegenprobe 2 (heute rot): das Briefing wurde NICHT zugestellt -> Gedaechtnis
    unveraendert -> Entwarnung kommt.
    """
    t0 = basis_jetzt()
    # Hauptfall
    sz = Szenario("trip", monkeypatch, mit, t0, mit_morgen=True, bis_stunden=48)
    with quellen(sz.x):
        lauf_erstwarnung(sz)
        sz.x.alerts = [sz.warnung(2)]
        assert trip_briefing(sz, 5) == "sent", "Vorbedingung: Briefing zugestellt"
        sz.mit.leeren()
        nach_briefing = sz.lauf(15)
    assert sz.eintrag().get("last_reported_value") == 2.0, f"AC-13: Briefing senkt nicht: {sz.eintrag()!r}"
    assert entwarnungen_gesamt(nach_briefing) == 0, f"AC-13: Entwarnung trotz Briefing: {nach_briefing!r}"

    # Gegenprobe 1: Briefing mit ausgefallener meldender Quelle
    g1 = Szenario("trip", monkeypatch, mit, t0, mit_morgen=True, bis_stunden=48)
    with quellen(g1.x):
        lauf_erstwarnung(g1)
        g1.x.ausfall = "exception"
        assert trip_briefing(g1, 5) == "sent", "Vorbedingung: Briefing (nicht abrufbar) zugestellt"
        g1.mit.leeren()
        assert g1.eintrag().get("last_reported_value") == 4.0, "AC-13: 'nicht abrufbar' darf nicht senken"
        g1.x.ausfall = None
        g1.x.alerts = [g1.warnung(2)]
        g1_lauf = g1.lauf(15)
    assert entwarnungs_sendungen(g1_lauf, "email"), (
        f"AC-13 Gegenprobe 1: nach 'nicht abrufbar'-Briefing muss die Entwarnung kommen: {g1_lauf!r}")

    # Gegenprobe 2: Briefing nicht zugestellt
    g2 = Szenario("trip", monkeypatch, mit, t0, mit_morgen=True, bis_stunden=48)
    with quellen(g2.x):
        lauf_erstwarnung(g2)
        g2.x.alerts = [g2.warnung(2)]
        fehlschlag_installieren(monkeypatch)
        assert trip_briefing(g2, 5) != "sent", "Vorbedingung: Briefing NICHT zugestellt"
        g2.mit = aufzeichner_installieren(monkeypatch)
        g2_lauf = g2.lauf(15)
    assert entwarnungs_sendungen(g2_lauf, "email"), (
        f"AC-13 Gegenprobe 2: nicht zugestelltes Briefing -> Entwarnung erwartet: {g2_lauf!r}")


def test_ac13_ortsvergleich_briefing_informiert_nicht_abrufbar_nicht(monkeypatch, mit):
    """AC-13 [Ortsvergleich-Briefing] (Spec v1.1: Trip UND Ortsvergleich) --
    echte Aufrufstelle `scheduler_dispatch_service.send_one_compare_preset`.
    GIVEN nach einem Ortsvergleich-Alarm Stufe 4 zeigt ein ZUGESTELLTES
          Ortsvergleich-Briefing bei gesunder meldender Quelle bereits Stufe 2
    WHEN  der naechste Alarmlauf stattfindet
    THEN  keine Entwarnung (das Briefing hat das Gedaechtnis auf 2 gesenkt).
    Gegenprobe (heute rot): das Briefing zeigte "nicht abrufbar" (meldende Quelle
    ausgefallen) -> Gedaechtnis bleibt auf 4 -> der naechste Lauf bei gesunder
    Quelle (Stufe 2) sendet die Entwarnung.
    """
    from tests.tdd._official_alert_allclear_fixtures import compare_briefing

    t0 = basis_jetzt()
    sz = Szenario("vergleich", monkeypatch, mit, t0)
    with quellen(sz.x):
        lauf_erstwarnung(sz)
        sz.x.alerts = [sz.warnung(2)]
        compare_briefing(monkeypatch, sz, 5)
        briefing = _snap(mit)
        assert briefing.sendungen("email"), f"Vorbedingung: Ortsvergleich-Briefing zugestellt: {briefing!r}"
        nach_briefing = sz.eintrag()
        lauf = sz.lauf(15)
    assert nach_briefing.get("last_reported_value") == 2.0, f"AC-13: Briefing senkt nicht: {nach_briefing!r}"
    assert entwarnungen_gesamt(lauf) == 0, f"AC-13: Entwarnung trotz Briefing: {lauf!r}"

    g = Szenario("vergleich", monkeypatch, mit, t0)
    with quellen(g.x):
        lauf_erstwarnung(g)
        g.x.ausfall = "exception"
        compare_briefing(monkeypatch, g, 5)
        briefing_g = _snap(mit)
        assert briefing_g.sendungen("email"), f"Vorbedingung: Briefing (nicht abrufbar) zugestellt: {briefing_g!r}"
        assert g.eintrag().get("last_reported_value") == 4.0, "AC-13: 'nicht abrufbar' darf nicht senken"
        g.x.ausfall = None
        g.x.alerts = [g.warnung(2)]
        g_lauf = g.lauf(15)
    assert entwarnungs_sendungen(g_lauf, "email"), (
        f"AC-13 Gegenprobe: nach 'nicht abrufbar'-Ortsvergleich-Briefing muss die Entwarnung kommen: {g_lauf!r}")


# ═══════════════════════════ AC-14 ══════════════════════════════════════════


def test_ac14_briefing_tombstone_nach_absent_since_ergibt_keine_entwarnung(monkeypatch, mit):
    """AC-14 (Reihenfolge Alarm-Lauf, Briefing, Alarm-Lauf).
    GIVEN Alarm-Lauf 1 sieht die Warnung bei gesunder Quelle nicht (`absent_since`)
    WHEN  danach ein ZUGESTELLTES Briefing ohne die Warnung den Tombstone setzt
          und Alarm-Lauf 2 folgt
    THEN  kommt genau KEINE Entwarnung (das Briefing hat informiert); im
          Gedaechtnis steht `ended_at`, `absent_since` ist geloescht.
    """
    sz = Szenario("trip", monkeypatch, mit, basis_jetzt(), mit_morgen=True, bis_stunden=48)
    with quellen(sz.x):
        lauf_erstwarnung(sz)
        sz.x.alerts = []
        lauf1 = sz.lauf(15)
        nach_lauf1 = sz.eintrag()
        assert trip_briefing(sz, 20) == "sent", "Vorbedingung: Briefing zugestellt"
        sz.mit.leeren()
        nach_briefing = sz.eintrag()
        lauf2 = sz.lauf(30)

    assert nach_lauf1.get("absent_since"), f"AC-14: `absent_since` nach Alarm-Lauf 1 fehlt: {nach_lauf1!r}"
    assert nach_briefing.get("ended_at"), f"AC-14: Briefing setzte keinen Tombstone: {nach_briefing!r}"
    assert not nach_briefing.get("absent_since"), f"AC-14: `absent_since` nicht geloescht: {nach_briefing!r}"
    assert entwarnungen_gesamt(lauf1) + entwarnungen_gesamt(lauf2) == 0, (
        f"AC-14: Entwarnung trotz Briefing-Tombstone: {lauf1!r} {lauf2!r}")


def test_ac14_briefing_zeigt_warnung_noch_loescht_absent_since_und_verschiebt_beendet(monkeypatch, mit):
    """AC-14 (Umkehrung, Spec v1.1 Abschnitt 6 Spiegelstrich 2).
    GIVEN Alarm-Lauf 1 sieht die Warnung bei gesunder Quelle nicht (`absent_since`
          gesetzt), danach zeigt ein ZUGESTELLTES Briefing sie bei gesunder Quelle
          noch mit unveraenderter Stufe 4
    WHEN  Alarm-Lauf 2 und Alarm-Lauf 3 die Warnung weiter nicht sehen
    THEN  ist `absent_since` durch das Briefing geloescht (die Quelle hat die
          Warnung geliefert -- keine aufeinanderfolgende Abwesenheit), Alarm-Lauf 2
          bleibt still und setzt `absent_since` neu, und erst Alarm-Lauf 3 meldet
          genau EINE Entwarnung "beendet" je Kanal.
    """
    sz = Szenario("trip", monkeypatch, mit, basis_jetzt(), mit_morgen=True, bis_stunden=48)
    with quellen(sz.x):
        lauf_erstwarnung(sz)
        warn = list(sz.x.alerts)
        sz.x.alerts = []
        lauf1 = sz.lauf(15)
        nach_lauf1 = sz.eintrag()
        sz.x.alerts = warn  # das Briefing zeigt die Warnung unveraendert (Stufe 4)
        assert trip_briefing(sz, 20) == "sent", "Vorbedingung: Briefing zugestellt"
        sz.mit.leeren()
        nach_briefing = sz.eintrag()
        sz.x.alerts = []
        lauf2 = sz.lauf(30)
        nach_lauf2 = sz.eintrag()
        lauf3 = sz.lauf(45)

    assert nach_lauf1.get("absent_since"), f"AC-14: `absent_since` nach Alarm-Lauf 1 fehlt: {nach_lauf1!r}"
    assert not nach_briefing.get("absent_since"), (
        f"AC-14: Briefing mit sichtbarer Warnung muss `absent_since` loeschen: {nach_briefing!r}")
    assert not nach_briefing.get("ended_at"), f"AC-14: Tombstone trotz gezeigter Warnung: {nach_briefing!r}"
    assert entwarnungen_gesamt(lauf1) + entwarnungen_gesamt(lauf2) == 0, (
        f"AC-14: Alarm-Lauf 1/2 muessen still bleiben: {lauf1!r} {lauf2!r}")
    assert nach_lauf2.get("absent_since") and not nach_lauf2.get("ended_at"), (
        f"AC-14: Alarm-Lauf 2 setzt `absent_since` neu (erste Abwesenheit): {nach_lauf2!r}")
    for kanal in ALLE_KANAELE:
        ew = entwarnungs_sendungen(lauf3, kanal)
        assert len(ew) == 1, f"AC-14: Alarm-Lauf 3 -- genau eine 'beendet' auf {kanal}: {lauf3!r}"
    assert "beendet" in _plain(entwarnungs_sendungen(lauf3, "email")[0]), "AC-14: Mail nennt nicht 'beendet'"


# ═══════════════════════════ AC-15 ══════════════════════════════════════════


def test_ac15_briefing_erstmeldung_schreibt_source_scope_level(monkeypatch, mit):
    """AC-15 [Briefing schreibt die neuen Felder].
    GIVEN eine Warnung wird ZUERST per Briefing gemeldet (kein Alarm davor)
    WHEN  das Briefing zugestellt ist
    THEN  enthaelt der Gedaechtnis-Eintrag `source`, `scope` und `level`, und
          eine spaetere Absenkung erzeugt eine Entwarnung.
    """
    sz = Szenario("trip", monkeypatch, mit, basis_jetzt(), mit_morgen=True, bis_stunden=48)
    with quellen(sz.x):
        assert trip_briefing(sz, 0) == "sent", "Vorbedingung: Briefing zugestellt"
        sz.mit.leeren()
        eintrag = sz.eintrag()
        sz.x.alerts = [sz.warnung(2)]
        lauf = sz.lauf(15)

    assert eintrag.get("source") == "quelle-x", f"AC-15: `source` fehlt/falsch: {eintrag!r}"
    assert eintrag.get("scope"), f"AC-15: `scope` fehlt: {eintrag!r}"
    assert eintrag.get("level") == 4, f"AC-15: `level` fehlt/falsch: {eintrag!r}"
    assert entwarnungs_sendungen(lauf, "email"), f"AC-15: Absenkung nach Briefing-Erstmeldung: {lauf!r}"


def test_ac15_alt_eintrag_ohne_source_ergibt_nie_eine_entwarnung(monkeypatch, mit):
    """AC-15 [Alt-Eintraege, einmalige Luecke].
    GIVEN ein Gedaechtnis-Eintrag im ALTEN Format (ohne `source`, wie er vor S2
          geschrieben wurde: `official_alert_state_entry`)
    WHEN  die Lage sinkt (Stufe 2) bzw. endet (zwei Laeufe leer)
    THEN  entsteht nie eine Entwarnung.
    Gegenprobe (heute rot, eigener Nutzer): dasselbe mit einem vom Produkt
    geschriebenen Eintrag -> Entwarnung 4 -> 2.
    """
    from datetime import datetime, timezone

    from output.renderers.alert.official_alerts import official_alert_state_entry, official_alert_state_key
    from services.alert_state import AlertStateService

    t0 = basis_jetzt()
    sz = Szenario("trip", monkeypatch, mit, t0)
    alt = sz.warnung(4)
    eintrag = official_alert_state_entry(alt, datetime.now(timezone.utc).isoformat())
    eintrag.pop("source", None)
    AlertStateService(user_id=sz.uid).save(sz.entity, {official_alert_state_key(alt): eintrag})
    with quellen(sz.x):
        sz.x.alerts = [sz.warnung(2)]
        gesenkt = sz.lauf(15)
        sz.x.alerts = []
        e1, e2 = sz.lauf(30), sz.lauf(45)
    assert entwarnungen_gesamt(gesenkt) + entwarnungen_gesamt(e1) + entwarnungen_gesamt(e2) == 0, (
        f"AC-15: Alt-Eintrag ohne `source` ergab eine Entwarnung: {gesenkt!r} {e1!r} {e2!r}")

    kontrolle = Szenario("trip", monkeypatch, mit, t0)
    with quellen(kontrolle.x):
        lauf_erstwarnung(kontrolle)
        kontrolle.x.alerts = [kontrolle.warnung(2)]
        k = kontrolle.lauf(15)
    assert entwarnungs_sendungen(k, "email"), f"AC-15 Gegenprobe: Entwarnung erwartet: {k!r}"


# ═══════════════════════════ AC-17 ══════════════════════════════════════════


def test_ac17_meteoalarm_allclear_bleibt_verworfen_und_kuerzt_keine_bestaetigung_ab(monkeypatch, mit):
    """AC-17 [Scope-Grenze MeteoAlarm AllClear].
    GIVEN die aufgezeichnete DE-Aufhebung (`responseType: AllClear`, #216) und
          eine zuvor per Alarm gemeldete Warnung
    WHEN  die Quelle statt der Warnung nur noch die Umsetzung der Aufhebung
          liefert (der geteilte Umsetzer verwirft sie -> leer)
    THEN  loest die Aufhebung selbst keine Entwarnung aus (Lauf 1 still) -- nur
          das Verschwinden bei gesunder Quelle ueber ZWEI Laeufe (AC-2) traegt.
    Gegenprobe (heute rot): Lauf 2 bestaetigt -> "beendet".
    """
    from services.official_alerts.meteoalarm import _group_and_map_info_entries
    from services.official_alerts.meteoalarm_feed import _info_entries_from_alert
    from tests.tdd.test_meteoalarm_feed_deutschland import _alert_nach_identifier, _feed_de

    aufhebung = _alert_nach_identifier(_feed_de(), "031ad672-42fe-411f-b4d6-5b11785c051e.MUL")
    assert all(i.get("responseType") == ["AllClear"] for i in aufhebung["info"]), "Fixture-Vorbedingung"
    umgesetzt = _group_and_map_info_entries(_info_entries_from_alert(aufhebung))
    assert umgesetzt == [], f"AC-17: AllClear muss verworfen bleiben: {umgesetzt!r}"

    sz = Szenario("trip", monkeypatch, mit, basis_jetzt())
    with quellen(sz.x):
        lauf_erstwarnung(sz)
        sz.x.alerts = list(umgesetzt)
        eins = sz.lauf(15)
        zwei = sz.lauf(30)

    assert entwarnungen_gesamt(eins) == 0, f"AC-17: AllClear darf die Bestaetigung nicht abkuerzen: {eins!r}"
    assert entwarnungs_sendungen(zwei, "email"), f"AC-17 Gegenprobe: 'beendet' nach Lauf 2: {zwei!r}"
