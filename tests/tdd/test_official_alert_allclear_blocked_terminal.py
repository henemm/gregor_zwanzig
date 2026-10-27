"""Entwarnung amtlicher Warnungen: eine rein GESPERRTE Entwarnung ist terminal,
ein Transportfehler nicht (Issue #1441 Scheibe S2, ADR-0086/ADR-0090).

SPEC: docs/specs/modules/feat_1441_s2_entwarnung.md (Abschnitt 4: Schreibweg nach
Zustellung; ADR-0086: Sperre ist terminal, Transportfehler wird wiederholt)

Ohne die Sperr-Regel wuerde eine Entwarnung, deren einziger Kanal gesperrt ist
(SMS-Tageskontingent erschoepft), jeden Lauf erneut versucht, protokolliert und
auf das Alarm-Tageslimit gebucht -- bis zum Ende der Gueltigkeit.

Echter Pfad: `TripAlertService.check_all_trips()`, echte Registry-Quelle,
echtes SMS-Tageskontingent (`sms_daily_limit.seed_daily_usage`), Aufzeichner
an den Ausgangs-Klassen. Kein Mock.
"""
from __future__ import annotations

from datetime import datetime, timezone

from tests.helpers.transport_mitschrift import aufzeichner_installieren
from tests.tdd._official_alert_allclear_fixtures import (
    Szenario, basis_jetzt, entwarnungen_gesamt, fehlschlag_installieren,
    lauf_erstwarnung, quellen,
)

_NUR_SMS = {"email": False, "telegram": False, "sms": True, "premium_sms": False}


def test_rein_gesperrte_entwarnung_gilt_als_erledigt_und_wiederholt_sich_nicht(monkeypatch):
    """GIVEN eine per SMS gemeldete Warnung Stufe 4, SMS ist der einzige Alarmkanal,
          und das SMS-Tageskontingent des Nutzers ist danach erschoepft
    WHEN  die Quelle auf Stufe 2 senkt und zwei Alarmlaeufe stattfinden
    THEN  ist die Entwarnung nach dem ersten (gesperrten) Lauf erledigt -- das
          Gedaechtnis steht auf 2 -- und der zweite Lauf versucht sie nicht erneut.
    Mutation: Sperre nicht als terminal werten -> Gedaechtnis bleibt auf 4 -> rot."""
    from services import sms_daily_limit

    mit = aufzeichner_installieren(monkeypatch)
    sz = Szenario("trip", monkeypatch, mit, basis_jetzt(), kanaele=_NUR_SMS)
    with quellen(sz.x):
        lauf_erstwarnung(sz, kanaele=("sms",))
        sms_daily_limit.seed_daily_usage(sz.uid, sms=10_000, premium_sms=None,
                                         now=datetime.now(timezone.utc))
        sz.x.alerts = [sz.warnung(2)]
        gesperrt = sz.lauf(15)
        nach_sperre = sz.eintrag()
        zweiter = sz.lauf(30)

    assert entwarnungen_gesamt(gesperrt) == 0, f"Vorbedingung: SMS gesperrt, nichts zugestellt: {gesperrt!r}"
    assert nach_sperre.get("last_reported_value") == 2.0, (
        f"Gesperrte Entwarnung muss terminal sein (Gedaechtnis auf 2): {nach_sperre!r}")
    assert not zweiter.sendungen("sms"), f"Zweiter Lauf darf nichts erneut versuchen: {zweiter!r}"
    assert sz.eintrag().get("last_reported_value") == 2.0


def test_transportfehler_bei_entwarnung_bleibt_offen(monkeypatch):
    """Gegenfall: GIVEN dieselbe Lage, aber der SMS-Transport scheitert (kein
    Sperr-Code) WHEN der Alarmlauf die Entwarnung versucht THEN bleibt das
    Gedaechtnis auf 4 -- die Entwarnung wird spaeter wiederholt (ADR-0086).
    Mutation: jede Rueckmeldung als erledigt werten -> Gedaechtnis 2 -> rot."""
    mit = aufzeichner_installieren(monkeypatch)
    sz = Szenario("trip", monkeypatch, mit, basis_jetzt(), kanaele=_NUR_SMS)
    with quellen(sz.x):
        lauf_erstwarnung(sz, kanaele=("sms",))
        versuche = fehlschlag_installieren(monkeypatch)
        sz.x.alerts = [sz.warnung(2)]
        sz.lauf(15)

    assert versuche["sms"] > 0, f"Vorbedingung: Versand wurde versucht: {versuche!r}"
    assert sz.eintrag().get("last_reported_value") == 4.0, (
        f"Transportfehler darf die Entwarnung nicht erledigen: {sz.eintrag()!r}")
