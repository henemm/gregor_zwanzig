"""Ortsvergleich: Aggregat-WarnBlock-Banner + Matrix-Zeile + Pro-Ort-Streifen
gleichzeitig (#1216, embedded, AC-4).

SPEC: docs/specs/modules/issue_1216_embedded_warnblock.md (AC-4)

RED-Phase: Heute rendert `render_compare_html` als Aggregat-Lead
`_render_warn_lead` (Satz + Tint-Tags), das WEDER die höchste amtliche Stufe
(GELB/ORANGE/ROT) noch den führenden Ortsnamen im Banner nennt. Die Spec
verlangt den geteilten WarnBlock als Aggregat-Banner mit „höchste Stufe {WORT}
· {Ort}"; die Matrix-Warn-Zeile (`Amtliche Warnungen`) UND der Pro-Ort-Streifen
(`border-left:4px`-Badge) bleiben additiv zusätzlich erhalten.

Verhaltenstests — KEINE Mocks. Echte `ComparisonResult`/`LocationResult`/
`SavedLocation`/`OfficialAlert`-Objekte durch die echte `render_compare_html`.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from app.profile import ActivityProfile
from app.user import ComparisonResult, LocationResult, SavedLocation
from services.official_alerts.models import OfficialAlert

UTC = timezone.utc
WINNER_NAME = "Marseille"


def _alert(level: int, hazard: str, label: str, region: str):
    return OfficialAlert(
        source="meteofrance_vigilance", hazard=hazard, level=level, label=label,
        valid_from=datetime(2026, 7, 11, 15, 0, tzinfo=UTC),
        valid_to=datetime(2026, 7, 11, 21, 0, tzinfo=UTC),
        region_label=region,
    )


def _loc_result(loc_id: str, name: str, lat: float, *, alert):
    from app.models import ForecastDataPoint
    loc = SavedLocation(id=loc_id, name=name, lat=lat, lon=5.0, elevation_m=100)
    dp = ForecastDataPoint(ts=datetime(2026, 7, 11, 9, 0), t2m_c=28.0)
    return LocationResult(
        location=loc, score=70,
        official_alerts=[alert] if alert else [],
        hourly_data=[dp],
    )


def _seven_locations_six_alerts():
    """7 Orte, 6 mit Warnung: 5x GELB Hitze + 1x ROT (Marseille) — höchste
    Stufe ROT am Ort Marseille, ein Ort (Avignon) ohne Warnung."""
    results = []
    # 5 GELB-Hitze-Orte.
    for i, nm in enumerate(["Nice", "Cannes", "Toulon", "Aix", "Nimes"]):
        results.append(_loc_result(
            f"loc-{i}", nm, 43.0 + i * 0.1,
            alert=_alert(2, "extreme_heat", "Hitze", nm),
        ))
    # 1 ROT-Ort (Marseille) — höchste Stufe.
    results.append(_loc_result(
        "loc-marseille", WINNER_NAME, 43.3,
        alert=_alert(4, "extreme_heat", "Extreme Hitze", WINNER_NAME),
    ))
    # 1 Ort ohne Warnung.
    results.append(_loc_result("loc-avignon", "Avignon", 43.9, alert=None))
    return ComparisonResult(
        locations=results, time_window=(9, 16), target_date=date(2026, 7, 11),
    )


# ---------------------------------------------------------------------------
# AC-4 — Aggregat-Banner (höchste Stufe ROT · Marseille) UND Matrix-Zeile UND
#         Pro-Ort-Streifen sind ALLE DREI gleichzeitig im HTML.
# ---------------------------------------------------------------------------
def test_ac4_banner_and_matrix_and_per_location_strip_all_present():
    from output.renderers.email.compare_html import render_compare_html
    html = render_compare_html(
        _seven_locations_six_alerts(), profile=ActivityProfile.ALLGEMEIN,
    )

    # (1) Aggregat-Banner: höchste amtliche Stufe ROT + führender Ort Marseille.
    #     Heute nennt _render_warn_lead weder Stufen-Wort noch Ortsnamen -> RED.
    assert "höchste Stufe ROT" in html, (
        "Aggregat-Banner nennt die höchste amtliche Stufe (ROT) nicht — "
        f"neuer WarnBlock fehlt. HTML: {html[:400]!r}"
    )
    assert WINNER_NAME in html, "Führender Ort (Marseille) fehlt im Banner-Scope"

    # (2) Matrix-Warn-Zeile bleibt (CV2_METRICS 'Amtliche Warnungen').
    assert "Amtliche Warnungen" in html, "Matrix-Warn-Zeile darf zusätzlich bleiben"

    # (3) Pro-Ort-Streifen bleibt additiv (Badge mit border-left:4px aus dem
    #     Shared-Renderer render_official_alerts_html).
    assert "border-left:4px solid" in html, (
        "Pro-Ort-Warn-Streifen (border-left:4px-Badge) muss additiv erhalten bleiben"
    )


# ---------------------------------------------------------------------------
# AC-4 — Banner zählt die betroffenen Orte („6 von 7").
# ---------------------------------------------------------------------------
def test_ac4_banner_counts_affected_locations():
    from output.renderers.email.compare_html import render_compare_html
    html = render_compare_html(
        _seven_locations_six_alerts(), profile=ActivityProfile.ALLGEMEIN,
    )
    assert "6 von 7" in html, (
        f"Aggregat-Banner muss die betroffenen Orte zählen (6 von 7): {html[:400]!r}"
    )
