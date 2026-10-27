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


# --- AC-11 (/60-validate F1): Stufen nie ueber Gefahrenarten/Skalen hinweg vergleichen -----------

def _zwei_orte_kopfzeile(erst: tuple[str, list], zweit: tuple[str, list]) -> list[str]:
    """Echte Ortsvergleich-Mail mit ZWEI gewarnten Orten in der gegebenen Reihenfolge."""
    from datetime import date, datetime

    from app.models import ForecastDataPoint
    from app.profile import ActivityProfile
    from app.user import ComparisonResult, LocationResult, SavedLocation
    from output.renderers.email.compare_html import render_compare_html

    def _loc(idx: int, name: str, warns: list) -> LocationResult:
        saved = SavedLocation(id=f"loc-{idx}", name=name, lat=46.94 + idx * 0.3, lon=12.68,
                              elevation_m=1800)
        dp = ForecastDataPoint(ts=datetime(2026, 2, 20, 9, 0), t2m_c=-3.0)
        return LocationResult(location=saved, score=70, official_alerts=list(warns), hourly_data=[dp])

    result = ComparisonResult(
        locations=[_loc(0, *erst), _loc(1, *zweit)],
        time_window=(9, 16), target_date=date(2026, 2, 20),
    )
    return wb_count_texts(render_compare_html(result, profile=ActivityProfile.ALLGEMEIN))


def _sturm_rot():
    from services.official_alerts.models import OfficialAlert

    return OfficialAlert(source="meteoalarm", hazard="wind", level=4, label="Sturm",
                         region_label="Osttirol")


def test_ac11_kopfzeile_sturm_zuerst_wird_nicht_von_lawinenstufe_5_verdraengt():
    """Gleiches Farblevel 4, verschiedene Gefahrenarten: die EAWS-Originalstufe 5 darf
    nicht gegen die Awareness-Stufe des Sturms antreten -- es fuehrt der zuerst gefundene."""
    fuenf = _stufe("derived/2026-02-20_AT-07_de_CAAMLv6_DERIVED_very_high.json", "AT-07-25")
    assert (fuenf.native_level, fuenf.level) == (5, 4), "Voraussetzung: Farblevel 4, Originalstufe 5"

    kopf = _zwei_orte_kopfzeile(("Sturm-Pass", [_sturm_rot()]), ("Tirol-Hütte", [fuenf]))

    assert kopf == ["höchste Stufe ROT · Sturm-Pass"], kopf


def test_ac11_kopfzeile_lagebericht_zuerst_fuehrt_auch_in_umgekehrter_reihenfolge():
    fuenf = _stufe("derived/2026-02-20_AT-07_de_CAAMLv6_DERIVED_very_high.json", "AT-07-25")

    kopf = _zwei_orte_kopfzeile(("Tirol-Hütte", [fuenf]), ("Sturm-Pass", [_sturm_rot()]))

    assert kopf == ["Lawinenstufe 5 · Tirol-Hütte"], kopf


def test_ac11_innerhalb_des_lageberichts_fuehrt_stufe_5_vor_stufe_4():
    """Positivfall: gleiche Gefahrenart, gleiches Farblevel -> die Originalstufe entscheidet."""
    from dataclasses import replace

    fuenf = _stufe("derived/2026-02-20_AT-07_de_CAAMLv6_DERIVED_very_high.json", "AT-07-25")
    vier = replace(fuenf, native_level=4)
    assert (vier.native_level, vier.level) == (4, 4)

    kopf = _zwei_orte_kopfzeile(("Vier-Hütte", [vier]), ("Fünf-Hütte", [fuenf]))

    assert kopf == ["Lawinenstufe 5 · Fünf-Hütte"], kopf
