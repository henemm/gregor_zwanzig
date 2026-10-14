"""Ortsvergleich: Kopfzeile des Warn-Banners und Chip-Schwere des Lageberichts (#1441,
Adversary-Fix-Loop 1: F002).

SPEC: docs/specs/modules/avalanche_report_bulletin.md -- AC-14, AC-15
VERTRAG: docs/artifacts/feat-1441-s1-lawinenlagebericht/red-contract.md Abschnitt 4

Geprueft wird an der Stelle, an der die Zusicherung WIRKT: der Text der Banner-Kopfzeile
(`wb-count`) der echten Ortsvergleich-Mail, nicht irgendein Vorkommen im HTML (der Pro-Ort-
Streifen nennt "Lawinenstufe 5 (sehr groß)" ohnehin).
"""
from __future__ import annotations

from tests.helpers.avalanche_report_support import parse_alert, render_compare_mail, wb_count_texts


def _stufe(datei: str, region: str):
    return parse_alert(datei, region, source="avalanche_report:AT-07")


def test_banner_kopfzeile_nennt_die_originalstufe_5_und_den_ort():
    """Mutation N10 (`native_level or level` -> `level`) zeigt hier "Lawinenstufe 4"."""
    fuenf = _stufe("derived/2026-02-20_AT-07_de_CAAMLv6_DERIVED_very_high.json", "AT-07-25")
    assert (fuenf.native_level, fuenf.level) == (5, 4), "Voraussetzung: Farblevel 4, Originalstufe 5"

    kopf = wb_count_texts(render_compare_mail([fuenf]))

    assert kopf == ["Lawinenstufe 5 · Tirol-Hütte"], kopf


def test_banner_kopfzeile_bei_stufe_1_ohne_ampelwort():
    eins = parse_alert("2026-03-01_AT-02_de_CAAMLv6.json", "AT-02-05-02", source="avalanche_report:AT-02")

    kopf = wb_count_texts(render_compare_mail([eins]))

    assert kopf == ["Lawinenstufe 1 · Tirol-Hütte"], kopf


def test_chip_schwere_der_stufe_1_ist_info():
    """Mutation N9 (Stufe 1 info -> caution) macht diesen Test rot."""
    from output.renderers.email.compare_html import _warn_short

    eins = parse_alert("2026-03-01_AT-02_de_CAAMLv6.json", "AT-02-05-02", source="avalanche_report:AT-02")

    assert _warn_short(eins) == ("Lawine 1", "info")
