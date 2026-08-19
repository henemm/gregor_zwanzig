"""TDD RED — Issue #1927 Wiedereroeffnung, Spec fix_1927_risk_dot_kombi_regel
Revision v1.1 (AC-2, AC-4, AC-5, AC-6, AC-7, AC-9).

`escalate_pair_watch()` (`src/output/metric_format.py`) prueft die in
`_PAIR_WATCH_ESCALATIONS` gelisteten Metrik-Paare: eskaliert eine Zeile von
'yellow' auf 'orange', wenn BEIDE Partner-Metriken eines Paares gleichzeitig
'yellow' sind.

**v1.1-Aenderung:** Der Adversary-Dialog gegen v1.0 (`docs/artifacts/
fix-1927-risk-dot-kombi-regel/adversary-dialog.md`) ergab VERDICT: BROKEN --
3 von 4 urspruenglich geplanten Paaren waren ueber den echten Aufrufpfad
`_row_risk()` strukturell nie erreichbar. Nach PO-Scope-Entscheid enthaelt
`_PAIR_WATCH_ESCALATIONS` jetzt nur noch DREI Paare:

1. `precipitation` + `temperature` -- unveraendert seit v1.0, echte
   Katalog-Schwellen auf beiden Seiten, zusaetzlich per Rohwert-Integration
   in tests/tdd/test_row_risk_pair_escalation.py abgedeckt.
2. `thunder` + (`wind`/`gust`) -- v1.1: `_thunder_risk_level()` wird auf die
   bestehende `_THUNDER_AMPEL_BAND`-Zuordnung ausgerichtet (LOW->eigenes
   'yellow' statt mit MED auf 'watch' verschmolzen) UND `_row_risk` uebergibt
   kuenftig einen `"thunder"`-Key im `severities`-Dict (fehlte in v1.0
   komplett). Dieser Verdrahtungs-Nachweis steht als echter
   `_row_risk(raw_row)`-Integrationstest in
   tests/tdd/test_row_risk_thunder_pair_escalation.py -- HIER wird die
   Paar-Logik weiterhin nur isoliert mit vorgegebenem Severity-Dict geprueft.
3. `visibility` + `fresh_snow` -- v1.1: `fresh_snow` erhaelt erstmals
   `display_thresholds` (SLF/EAWS-Schwellen gelb=10/orange=20/rot=30 cm/24h),
   Nachweis in tests/tdd/test_fresh_snow_catalog_thresholds.py und
   tests/tdd/test_row_risk_visibility_fresh_snow_pair_escalation.py.
   `snow_depth` ist in v1.1 KEIN Partner mehr (keine belegbare
   Ampel-Absolutschwelle gefunden, siehe Spec Known Limitations).

**Entfallen in v1.1:** Das v1.0-Paar `(precipitation|rain_probability)` +
`freezing_level` (AC-3) ist ersatzlos gestrichen -- `freezing_level` bleibt
ohne `display_thresholds` (strukturell trip-relatives Problem, siehe Spec
Known Limitations). Kein Ersatztest.

Kern-Schicht, deterministisch: keine Mocks/patch()/MagicMock, kein Netz. Reiner
Funktionsaufruf mit Severity-Dicts. Kein Dateiinhalt-Check.

SPEC: docs/specs/modules/fix_1927_risk_dot_kombi_regel.md (v1.1) AC-2, AC-4,
AC-5, AC-6, AC-7, AC-9
KONTEXT: docs/context/fix-1927-risk-dot-kombi-regel.md
"""
from __future__ import annotations

from output.metric_format import _PAIR_WATCH_ESCALATIONS, escalate_pair_watch


def test_v1_1_exactly_three_pairs_defined():
    """v1.1 (PO-Scope-Entscheid nach Adversary-Verdict BROKEN): genau drei
    Metrik-Paare, nicht mehr vier -- das Nullgradgrenze-Paar (v1.0-AC-3)
    entfaellt ersatzlos, das Schneehoehe-Paar (v1.0-AC-5-Alternative
    `snow_depth`) entfaellt ebenso (Spec Non-Goals v1.1)."""
    assert len(_PAIR_WATCH_ESCALATIONS) == 3, (
        f"_PAIR_WATCH_ESCALATIONS hat {len(_PAIR_WATCH_ESCALATIONS)} Eintraege, "
        f"erwartet 3 (v1.1: Nullgradgrenze- und Schneehoehe-Paar entfallen)."
    )


def test_ac2_precipitation_and_temperature_both_yellow_escalates():
    """AC-2 (Paar 1) direkt an der Funktion: der Rohwert-Test in
    tests/tdd/test_row_risk_pair_escalation.py kann diesen Fall NICHT vom
    alten 3-stufigen Kollaps unterscheiden (Alt-Code liefert 'watch' fuer
    JEDE gelbe Einzelmetrik, unabhaengig von temp) -- diese Funktionsebene
    ist der eigentliche RED-Nachweis fuer AC-2 (ImportError vor Implementierung)."""
    result = escalate_pair_watch({"precipitation": "yellow", "temperature": "yellow"})
    assert result == "orange", (
        f"escalate_pair_watch mit precipitation+temperature beide gelb "
        f"liefert {result!r}, erwartet 'orange' (Vereisungsgefahr, Spec AC-2)."
    )


def test_ac4_thunder_and_wind_both_yellow_escalates():
    result = escalate_pair_watch({"thunder": "yellow", "wind": "yellow"})
    assert result == "orange", (
        f"escalate_pair_watch mit thunder+wind beide gelb liefert {result!r}, "
        f"erwartet 'orange' (Blitzschlag + Boeenfront-Sturzgefahr, Spec AC-4)."
    )


def test_ac4_thunder_and_gust_both_yellow_escalates():
    result = escalate_pair_watch({"thunder": "yellow", "gust": "yellow"})
    assert result == "orange", (
        f"escalate_pair_watch mit thunder+gust beide gelb liefert {result!r}, "
        f"erwartet 'orange' (Spec AC-4, Alternativ-Partner Boeen statt Wind)."
    )


def test_ac5_visibility_and_fresh_snow_both_yellow_escalates():
    """v1.1: `fresh_snow` ist der EINZIGE Partner dieses Paares (`snow_depth`
    entfaellt ersatzlos, siehe Modul-Docstring)."""
    result = escalate_pair_watch({"visibility": "yellow", "fresh_snow": "yellow"})
    assert result == "orange", (
        f"escalate_pair_watch mit visibility+fresh_snow beide gelb liefert "
        f"{result!r}, erwartet 'orange' (Weg unter Neuschnee, keine "
        f"Fernsicht, Spec v1.1 AC-5)."
    )


def test_ac6_only_one_partner_yellow_no_escalation():
    result = escalate_pair_watch({"precipitation": "yellow", "temperature": "green"})
    assert result is None, (
        f"escalate_pair_watch mit nur precipitation gelb (temperature gruen) "
        f"liefert {result!r}, erwartet None -- kein Partner, keine Eskalation "
        f"(Spec AC-6)."
    )


def test_ac6_missing_partner_value_no_escalation():
    result = escalate_pair_watch({"precipitation": "yellow"})
    assert result is None, (
        f"escalate_pair_watch mit nur precipitation gelb (temperature fehlt "
        f"im Dict) liefert {result!r}, erwartet None (Spec AC-6)."
    )


def test_ac7_unrelated_yellow_combination_no_escalation():
    result = escalate_pair_watch({"uv_index": "yellow", "temperature": "yellow"})
    assert result is None, (
        f"escalate_pair_watch mit uv_index+temperature beide gelb (kein "
        f"definiertes Paar) liefert {result!r}, erwartet None -- unabhaengige "
        f"Gelb-Kombination eskaliert nicht (Spec AC-7, PO-Beispiel)."
    )


def test_ac9_wind_and_temperature_yellow_no_escalation():
    """Windchill/Hitzeindex (`felt`) deckt Wind+Temp bereits als eigene
    Metrik ab -- keine zusaetzliche Paar-Regel fuer wind+temperature."""
    result = escalate_pair_watch({"wind": "yellow", "temperature": "yellow"})
    assert result is None, (
        f"escalate_pair_watch mit wind+temperature beide gelb liefert "
        f"{result!r}, erwartet None -- kein Wind+Temp-Paar in der "
        f"Drei-Paar-Liste (Spec AC-9, 'felt' deckt das bereits ab)."
    )


def test_yellow_plus_orange_does_not_double_escalate():
    """Non-Goal: keine Eskalation ueber eine Stufe hinaus -- ein Paar mit
    einem Partner bereits auf Orange loest die Regel nicht zusaetzlich aus."""
    result = escalate_pair_watch({"precipitation": "yellow", "temperature": "orange"})
    assert result is None, (
        f"escalate_pair_watch mit precipitation=gelb + temperature=orange "
        f"liefert {result!r}, erwartet None -- nur beide-gelb-Faelle sind in "
        f"Scope (Spec Implementation Details)."
    )


def test_empty_severities_no_escalation():
    assert escalate_pair_watch({}) is None
