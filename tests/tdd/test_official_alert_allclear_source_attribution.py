"""Entwarnung amtlicher Warnungen -- Zuordnung der MELDENDEN Quelle im
Melde-Gedaechtnis (Issue #1441 Scheibe S2, Adversary F001).

SPEC: docs/specs/modules/feat_1441_s2_entwarnung.md -- AC-7 (Quellenwechsel der
      besten Quelle), Abschnitte 2 und 3 (Pre-Merge-Satz der meldenden Quelle).

Zwei Quellen liefern dieselbe Identitaet+Gefahr+Zeitraum (gleicher
Gedaechtnis-Schluessel), X mit Stufe 4 (gezeigt, weil hoechste Stufe), Y mit
Stufe 2. Die Registrier-Reihenfolge ist Y VOR X -- die Zuordnung darf nicht an
der Reihenfolge haengen, sondern an der tatsaechlich gezeigten Warnung.
Solange X weiter Stufe 4 liefert, darf keine Entwarnung entstehen -- weder
nach einer Alarm-Erstmeldung noch nach einer Briefing-Erstmeldung.
"""
from __future__ import annotations

import pytest

from tests.helpers.transport_mitschrift import aufzeichner_installieren
from tests.tdd._official_alert_allclear_fixtures import (
    FLAECHEN, Szenario, Warnquelle, basis_jetzt, entwarnungen_gesamt,
    entwarnungs_sendungen, lauf_erstwarnung, quellen, trip_briefing, warnung,
)


@pytest.fixture
def mit(monkeypatch):
    return aufzeichner_installieren(monkeypatch)


@pytest.mark.parametrize("flaeche", FLAECHEN)
def test_gleicher_schluessel_bei_zwei_quellen_ordnet_die_gezeigte_warnung_ihrer_quelle_zu(
        monkeypatch, mit, flaeche):
    """GIVEN Y (Stufe 2) ist VOR X (Stufe 4) registriert, beide mit demselben
          Gedaechtnis-Schluessel; der Alarm meldet die gezeigte Stufe 4 von X
    WHEN  der Folgelauf stattfindet und X weiter Stufe 4 liefert
    THEN  traegt das Gedaechtnis `source == quelle-x` und es entsteht keine
          Entwarnung. Gegenprobe: liefert X selbst Stufe 2 -> Entwarnung 4 -> 2.
    """
    sz = Szenario(flaeche, monkeypatch, mit, basis_jetzt())
    y = Warnquelle("quelle-y", nur_bei=sz.x.nur_bei)
    y.alerts = [warnung(2, quelle=y, von=sz.von, bis=sz.bis)]
    with quellen(y, sz.x):
        lauf_erstwarnung(sz)
        eintrag = sz.eintrag()
        folge = sz.lauf(15)
        sz.x.alerts = [sz.warnung(2)]
        gegenprobe = sz.lauf(30)

    assert eintrag.get("source") == "quelle-x", (
        f"[{flaeche}] meldende Quelle falsch zugeordnet (Registrier-Reihenfolge): {eintrag!r}")
    assert eintrag.get("last_reported_value") == 4.0, f"Vorbedingung: Stufe 4 gemeldet: {eintrag!r}"
    assert entwarnungen_gesamt(folge) == 0, (
        f"[{flaeche}] Schein-Entwarnung: X liefert weiter Stufe 4: {folge!r}")
    assert entwarnungs_sendungen(gegenprobe, "email"), (
        f"[{flaeche}] Gegenprobe: X selbst liefert 2 -> Entwarnung erwartet: {gegenprobe!r}")


def _query(sources: dict, shown):
    from services.official_alert_allclear import AllClearQuery

    return AllClearQuery(scope="ort", scope_ids=("ort",), window_start=basis_jetzt(),
                         window_end=None, sources=sources, shown=(shown,))


def _alert(source: str, level: int):
    from datetime import timedelta

    from services.official_alerts.models import OfficialAlert

    t0 = basis_jetzt()
    return OfficialAlert(source=source, hazard="extreme_heat", level=level, label="Hitzewarnung",
                         region_label="Innsbruck-Land", valid_from=t0, valid_to=t0 + timedelta(hours=8))


def test_zuordnung_folgt_stufe_und_quelle_der_gezeigten_warnung_nicht_dem_schluessel():
    """Gleicher Gedaechtnis-Schluessel bei Y (Stufe 2, zuerst) und X (Stufe 4,
    gezeigt): `reported_meta` ordnet die gezeigte Warnung X zu."""
    from output.renderers.alert.official_alerts import official_alert_state_key
    from services.official_alert_allclear import reported_meta

    x4, y2 = _alert("quelle-x", 4), _alert("quelle-y", 2)
    assert official_alert_state_key(x4) == official_alert_state_key(y2), "Vorbedingung: gleicher Schluessel"
    meta = reported_meta([_query({"quelle-y": (True, [y2]), "quelle-x": (True, [x4])}, x4)])
    assert meta[official_alert_state_key(x4)]["source"] == "quelle-x", meta


def test_mehrdeutige_zuordnung_ergibt_keine_quelle():
    """Liefern ZWEI Registry-Namen genau dieselbe gezeigte Warnung, ist die
    meldende Quelle nicht eindeutig: `source` bleibt leer (im Zweifel still)."""
    from output.renderers.alert.official_alerts import official_alert_state_key
    from services.official_alert_allclear import reported_meta

    x4 = _alert("quelle-x", 4)
    meta = reported_meta([_query({"quelle-x": (True, [x4]), "quelle-x-spiegel": (True, [x4])}, x4)])
    assert meta[official_alert_state_key(x4)]["source"] is None, meta


def test_briefing_erstmeldung_bei_gleichem_schluessel_ordnet_die_gezeigte_warnung_ihrer_quelle_zu(
        monkeypatch, mit):
    """GIVEN Y (Stufe 2) ist VOR X (Stufe 4) registriert; die Warnung wird
          ZUERST per Trip-Briefing gemeldet (Stufe 4 von X gezeigt)
    WHEN  der Folgelauf stattfindet und X weiter Stufe 4 liefert
    THEN  bleibt das Gedaechtnis bei `source == quelle-x` und Stufe 4, und es
          entsteht weder eine Entwarnung noch eine erneute Warnung.
    """
    sz = Szenario("trip", monkeypatch, mit, basis_jetzt(), mit_morgen=True, bis_stunden=48)
    y = Warnquelle("quelle-y")
    y.alerts = [warnung(2, quelle=y, von=sz.von, bis=sz.bis)]
    with quellen(y, sz.x):
        assert trip_briefing(sz, 0) == "sent", "Vorbedingung: Briefing zugestellt"
        sz.mit.leeren()
        eintrag = sz.eintrag()
        folge = sz.lauf(15)

    assert eintrag.get("source") == "quelle-x", f"Briefing ordnete die falsche Quelle zu: {eintrag!r}"
    assert eintrag.get("last_reported_value") == 4.0, f"Briefing senkte still: {eintrag!r}"
    assert entwarnungen_gesamt(folge) == 0, f"Schein-Entwarnung nach Briefing-Erstmeldung: {folge!r}"
    assert not folge.sendungen("email"), f"Keine erneute Warnung erwartet: {folge!r}"
