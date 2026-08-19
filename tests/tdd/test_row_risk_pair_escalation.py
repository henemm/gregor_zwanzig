"""TDD RED — Issue #1927 Wiedereroeffnung, Spec fix_1927_risk_dot_kombi_regel
(AC-2, AC-6 Integrationsteil).

`_row_risk()` (`src/output/renderers/email/html.py`) ruft nach der bestehenden
Maximalwert-Logik `metric_format.escalate_pair_watch()` auf, um Paar 1
(Niederschlag+Temperatur) zu pruefen.

**v1.1-Stand:** In v1.0 war Paar 1 das EINZIGE der (damals vier) Spec-Paare,
das ueber echte Rohwerte durch `_row_risk(raw_row)` beobachtbar war -- die
anderen drei scheiterten strukturell am Aufrufpfad (Adversary-Verdict BROKEN,
`docs/artifacts/fix-1927-risk-dot-kombi-regel/adversary-dialog.md`). v1.1
behebt das fuer zwei der drei verbleibenden Paare: Gewitter+Wind/Boeen ist
jetzt per Verdrahtungskorrektur ueber `_row_risk(raw_row)` erreichbar
(Integrationsnachweis in tests/tdd/test_row_risk_thunder_pair_escalation.py),
Sicht+Neuschnee ebenso ueber eine neue Katalog-Schwelle fuer `fresh_snow`
(Integrationsnachweis in
tests/tdd/test_row_risk_visibility_fresh_snow_pair_escalation.py). Diese
Datei bleibt bei Paar 1 (Niederschlag+Temperatur), unveraendert seit v1.0.

Kern-Schicht, deterministisch: keine Mocks/patch()/MagicMock, kein Netz. Echter
Renderer-Aufruf (`_row_risk`) mit echten Zeilen-Dicts. Kein Dateiinhalt-Check.

SPEC: docs/specs/modules/fix_1927_risk_dot_kombi_regel.md AC-2, AC-6
KONTEXT: docs/context/fix-1927-risk-dot-kombi-regel.md
"""
from __future__ import annotations

from output.metric_format import severity_for
from src.output.renderers.email.html import _row_risk


def test_ac2_precip_and_temp_both_yellow_escalates_to_orange():
    """AC-2 (Paar 1): precip UND temp beide exakt auf Gelb-Schwelle ->
    Zeile eskaliert auf Orange (Vereisungsgefahr).

    HINWEIS RED-Phase: dieser Test ist VOR der Implementierung bereits gruen
    -- der heutige 3-stufige Kollaps liefert 'watch' fuer JEDE gelbe
    Einzelmetrik, unabhaengig von temp (das heutige `_row_risk` liest `temp`
    gar nicht). Der eigentliche RED-Nachweis fuer AC-2 steht in
    test_escalate_pair_watch.py::test_ac2_precipitation_and_temperature_both_yellow_escalates
    (ImportError vor Implementierung). Dieser Test bleibt als
    Integrations-/Regressionsschutz erhalten -- er wird rot, sobald S1 (echte
    4-Stufigkeit) implementiert ist, S2 (Paar-Eskalation) aber fehlt."""
    assert severity_for("precipitation", 1.0) == "yellow", (
        "Erwartungs-Grundlage: 1.0mm erreicht die Katalog-Gelbschwelle"
    )
    assert severity_for("temperature", 28.0) == "yellow", (
        "Erwartungs-Grundlage: 28.0°C erreicht die Katalog-Gelbschwelle"
    )
    result = _row_risk({"precip": 1.0, "temp": 28.0})
    assert result == "watch", (
        f"_row_risk({{'precip': 1.0, 'temp': 28.0}}) liefert {result!r}, "
        f"erwartet 'watch' (=Orange, Paar-Eskalation Vereisungsgefahr, "
        f"Spec AC-2)."
    )


def test_ac6_precip_yellow_alone_stays_yellow_no_partner():
    """AC-6: nur precip gelb, kein temp-Wert in der Zeile (kein Partner) ->
    keine Eskalation, Ergebnis bleibt Gelb."""
    result = _row_risk({"precip": 1.0})
    assert result == "yellow", (
        f"_row_risk({{'precip': 1.0}}) liefert {result!r}, erwartet 'yellow' "
        f"-- kein temp-Partner vorhanden, keine Eskalation (Spec AC-6)."
    )


def test_ac6_precip_yellow_with_green_temp_stays_yellow():
    """AC-6: precip gelb, temp gruen (Partner vorhanden, aber nicht gelb) ->
    keine Eskalation."""
    assert severity_for("temperature", 10.0) == "green", (
        "Erwartungs-Grundlage: 10.0°C liegt unter jeder Temp-Schwelle"
    )
    result = _row_risk({"precip": 1.0, "temp": 10.0})
    assert result == "yellow", (
        f"_row_risk({{'precip': 1.0, 'temp': 10.0}}) liefert {result!r}, "
        f"erwartet 'yellow' -- Partner temp ist gruen, keine Eskalation "
        f"(Spec AC-6)."
    )


def test_ac8_red_gust_with_yellow_pair_stays_risk_not_downgraded():
    """Regressionsschutz (Adversary-Finding F001, v1.1): Eine rote Einzelmetrik
    (gust=100, > Rotschwelle 60) UND gleichzeitig ein gelbes Paar (precip=1.0 +
    temp=28.0, beide auf Gelb-Schwelle) darf NICHT auf 'watch' heruntergestuft
    werden -- der Guard `if worst == "yellow":` um die Paar-Eskalation muss
    das verhindern."""
    result = _row_risk({"gust": 100, "precip": 1.0, "temp": 28.0})
    assert result == "risk", (
        f"_row_risk mit rotem gust + gelbem Paar (precip+temp) liefert "
        f"{result!r}, erwartet 'risk' -- eine rote Zeile darf durch ein "
        f"gleichzeitig gelbes Paar nicht heruntergestuft werden (Adversary "
        f"Finding F001)."
    )
