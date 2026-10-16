"""Entwarnung amtlicher Warnungen -- Randfaelle an den Wirkstellen
(Issue #1441 Scheibe S2, Adversary F004, F005, F006, F007).

SPEC: docs/specs/modules/feat_1441_s2_entwarnung.md -- AC-8 (Zeitraum-
      Ueberlappung), AC-10 (nur einmal), AC-12 (SMS-Kuerzung, Ortsvergleich;
      Wetter-Alarm im selben Lauf), AC-15 (Alt-Eintrag ohne `source`).

Versandpfade laufen durch die ECHTEN Einstiege; ersetzt sind nur Wetter-Naht,
Quellen (echte Klassen in der echten Registry) und Transport-Klassen.
"""
from __future__ import annotations

from datetime import timedelta

import pytest

from output.tokens.hazard_symbols import sms_symbol_for
from tests.helpers.transport_mitschrift import aufzeichner_installieren
from tests.tdd._official_alert_allclear_fixtures import (
    Szenario, basis_jetzt, entwarnungen_gesamt, entwarnungs_sendungen,
    lauf_erstwarnung, quellen,
)

HT = sms_symbol_for("extreme_heat")


@pytest.fixture
def mit(monkeypatch):
    return aufzeichner_installieren(monkeypatch)


# ═══════════════ AC-12, Ortsvergleich: SMS-Kuerzung (F004) ═══════════════════


def test_ortsvergleich_von_der_sms_kuerzung_verdraengte_entwarnung_bleibt_offen(monkeypatch, mit):
    """AC-12 [SMS-Kuerzung] im Ortsvergleich.
    GIVEN NUR SMS ist Alarmkanal; im selben Lauf fuellen neue Warnungen das
          SMS-Budget, dazu die Entwarnung der Hitzewarnung 4 -> 2
    WHEN  die SMS erzeugt und zugestellt wird
    THEN  gilt die verdraengte Entwarnung als NICHT zugestellt (Gedaechtnis
          bleibt auf 4) und sie kommt im naechsten Lauf.
    """
    nur_sms = {"email": False, "telegram": False, "sms": True, "premium_sms": False}
    sz = Szenario("vergleich", monkeypatch, mit, basis_jetzt(), kanaele=nur_sms)
    gefahren = ("thunderstorm", "flood", "rain", "wind_gust", "snow", "black_ice",
                "extreme_cold", "wildfire_risk", "fog", "storm_surge")
    with quellen(sz.x):
        lauf_erstwarnung(sz, kanaele=("sms",))
        neue = [sz.warnung(3, hazard=h, region=f"Region-{h}") for h in gefahren]
        sz.x.alerts = [sz.warnung(2)] + neue
        voll = sz.lauf(15)
        nach_kuerzung = sz.eintrag()
        naechster = sz.lauf(30)

    sms = [s["body"] for s in voll.sendungen("sms")]
    assert len(sms) == 1 and "!" in sms[0], f"Vorbedingung: EINE SMS mit den Warnungen: {voll!r}"
    assert f"+{HT}" not in sms[0], f"Vorbedingung: Entwarnung durch Kuerzung verdraengt: {sms[0]!r}"
    assert nach_kuerzung.get("last_reported_value") == 4.0, (
        f"verdraengte Entwarnung darf das Gedaechtnis nicht senken: {nach_kuerzung!r}")
    assert any(f"+{HT}:H>L" in s["body"] for s in naechster.sendungen("sms")), (
        f"verdraengte Entwarnung muss im naechsten Lauf kommen: {naechster!r}")


# ═══════════════ AC-8: Ueberlappung, Positivrichtung (F005) ═══════════════════


def test_nicht_ueberlappende_folgeperiode_verdeckt_die_absenkung_nicht(monkeypatch, mit):
    """AC-8 / Spec Abschnitt 3: bewertet werden nur UEBERLAPPENDE Eintraege.
    GIVEN gemeldet Stufe 4 fuer Zeitraum A (bis t0+5h); jetzt liefert die
          meldende Quelle A mit Stufe 2 und zusaetzlich eine NICHT
          ueberlappende Folgeperiode B (t0+6h..t0+9h) mit Stufe 4
    WHEN  der Alarmlauf stattfindet
    THEN  kommt die Entwarnung 4 -> 2 fuer A -- B zaehlt fuer A nicht als
          "noch da" (B selbst ist eine eigene Warnung).
    """
    t0 = basis_jetzt()
    sz = Szenario("trip", monkeypatch, mit, t0, bis_stunden=5)
    with quellen(sz.x):
        lauf_erstwarnung(sz)
        folge = sz.warnung(4, von=t0 + timedelta(hours=6), bis=t0 + timedelta(hours=9))
        sz.x.alerts = [sz.warnung(2), folge]
        lauf = sz.lauf(15)
        eintraege = sz.eintraege()

    assert entwarnungs_sendungen(lauf, "email"), (
        f"Absenkung von A durch nicht ueberlappende Folgeperiode verdeckt: {lauf!r}")
    a_eintrag = [e for e in eintraege.values() if e.get("valid_to") == sz.bis.isoformat()]
    assert len(a_eintrag) == 1 and a_eintrag[0].get("last_reported_value") == 2.0, eintraege


# ═══════════════ AC-15: Alt-Eintrag direkt an der Erkennung (F007) ════════════


def test_alt_eintrag_ohne_source_wird_von_der_erkennung_nicht_bewertet():
    """AC-15 [Alt-Eintrag]: direkt an `detect_official_allclear` (ohne den
    Fail-soft des Alarmpfads, der einen Fehler verschlucken wuerde).
    GIVEN ein Alt-Eintrag OHNE `source` (mit `scope`) und ein Produkt-Eintrag
          mit `source`, beide Stufe 4; die gesunde Quelle liefert beide mit 2
    THEN  genau EINE Entwarnung (fuer den Produkt-Eintrag), der Alt-Eintrag
          bleibt unveraendert (kein `absent_since`, keine Senkung).
    """
    import copy
    from datetime import datetime, timezone

    from output.renderers.alert.official_alerts import (
        official_alert_state_entry, official_alert_state_key,
    )
    from services.official_alert_allclear import AllClearQuery, detect_official_allclear
    from services.official_alerts.models import OfficialAlert

    now = datetime.now(timezone.utc).replace(microsecond=0)
    von, bis = now - timedelta(hours=1), now + timedelta(hours=10)

    def _a(hazard, level):
        return OfficialAlert(source="quelle-x", hazard=hazard, level=level, label=hazard,
                             region_label="Innsbruck-Land", valid_from=von, valid_to=bis)

    alt, neu = _a("extreme_heat", 4), _a("thunderstorm", 4)
    alt_entry = official_alert_state_entry(alt, now.isoformat(), scope=["ort"])
    alt_entry.pop("source")
    state = {
        official_alert_state_key(alt): alt_entry,
        official_alert_state_key(neu): official_alert_state_entry(
            neu, now.isoformat(), source="quelle-x", scope=["ort"]),
    }
    vorher = copy.deepcopy(state[official_alert_state_key(alt)])
    query = AllClearQuery(scope="ort", scope_ids=("ort",), window_start=now, window_end=None,
                          sources={"quelle-x": (True, [_a("extreme_heat", 2), _a("thunderstorm", 2)])})

    found, _changed = detect_official_allclear(state, [query], now)

    assert [ac.key for ac in found] == [official_alert_state_key(neu)], found
    assert state[official_alert_state_key(alt)] == vorher, state


# ═══════════════ AC-12: Wetter-Alarm im selben Lauf (F006) ════════════════════


def test_entwarnung_kommt_auch_wenn_im_selben_lauf_ein_wetter_alarm_feuert(monkeypatch, mit):
    """AC-12 / Spec Abschnitt 8: im selben Lauf feuert der Wetter-Abweichungs-
    Alarm (Δ-Anker vorhanden) UND eine Entwarnung 4 -> 2 liegt vor.
    WHEN  `check_all_trips` laeuft
    THEN  geht die Entwarnung trotzdem hinaus und das Gedaechtnis steht auf 2.

    Naht: der Abweichungs-Alarm selbst (`check_and_send_alerts`, eigene
    Wetter-Abrufe) ist NICHT Pruefgegenstand und meldet hier "zugestellt";
    geprueft wird die Verzweigung in `check_all_trips` und der echte
    Entwarnungs-Versand danach.
    """
    from services.trip_alert import TripAlertService
    from tests.tdd._official_alert_allclear_fixtures import geometrie_ein_segment

    t0 = basis_jetzt()
    sz = Szenario("trip", monkeypatch, mit, t0)
    geometrie = geometrie_ein_segment(t0)
    delta_aufrufe: list = []

    def _mit_anker(self, trip, *, tagesgleicher_anker_noetig, now_utc=None):
        return list(geometrie)

    def _delta_alarm_zugestellt(self, trip, cached, fresh_weather=None, official_notices=None):
        delta_aufrufe.append(list(official_notices or []))
        return True

    with quellen(sz.x):
        lauf_erstwarnung(sz)
        monkeypatch.setattr(TripAlertService, "_get_cached_weather", _mit_anker)
        monkeypatch.setattr(TripAlertService, "check_and_send_alerts", _delta_alarm_zugestellt)
        sz.x.alerts = [sz.warnung(2)]
        lauf = sz.lauf(15)
        eintrag = sz.eintrag()

    assert delta_aufrufe == [[]], f"Vorbedingung: der Wetter-Alarm feuerte (ohne neue Warnung): {delta_aufrufe!r}"
    assert entwarnungs_sendungen(lauf, "email"), f"Entwarnung nach Wetter-Alarm fehlt: {lauf!r}"
    assert eintrag.get("last_reported_value") == 2.0, f"Gedaechtnis nicht gesenkt: {eintrag!r}"


# ═══════════════ AC-10: Neuausgabe gesenkt -- nur einmal (F007) ═══════════════


def test_gesenkte_neuausgabe_unter_neuem_schluessel_meldet_nur_einmal(monkeypatch, mit):
    """AC-10 [nur einmal] bei Absenkung ueber eine Neuausgabe.
    GIVEN gemeldet Stufe 4 (Zeitraum A); die Quelle liefert jetzt eine
          ueberlappende Neuausgabe B (neuer Schluessel) mit Stufe 2
    WHEN  zwei Alarmlaeufe mit gleicher Lage stattfinden
    THEN  kommt genau EINE Entwarnung, und kein Gedaechtnis-Eintrag dieser
          Identitaet steht danach noch ueber Stufe 2.

    Grenze (Adversary R2 F012/N6d): dieser Test bewacht NICHT, dass der
    Schreibweg `apply_official_allclears` die `current_keys` mitsenkt: senkt
    der Schreibweg nur den Alt-Schluessel (Mutation N6d), bleibt er gruen.
    Geprueft wird allein das Verhalten: eine Entwarnung ueber zwei Laeufe,
    danach nichts mehr ueber Stufe 2.
    """
    t0 = basis_jetzt()
    sz = Szenario("trip", monkeypatch, mit, t0, bis_stunden=5)
    with quellen(sz.x):
        lauf_erstwarnung(sz)
        sz.x.alerts = [sz.warnung(2, von=t0 + timedelta(minutes=10), bis=t0 + timedelta(hours=29))]
        eins, zwei = sz.lauf(15), sz.lauf(30)
        eintraege = sz.eintraege()

    assert entwarnungen_gesamt(eins) > 0, f"Vorbedingung: Entwarnung 4 -> 2: {eins!r}"
    assert entwarnungen_gesamt(zwei) == 0, f"zweite Entwarnung bei gleicher Lage: {zwei!r}"
    hoch = {k: e for k, e in eintraege.items()
            if not e.get("ended_at") and (e.get("last_reported_value") or 0) > 2}
    assert not hoch, f"Eintrag steht noch ueber der gemeldeten Stufe: {hoch!r}"
