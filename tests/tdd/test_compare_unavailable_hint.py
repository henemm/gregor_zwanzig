"""TDD RED — Scheibe 3 (Compare) von Issue #1349: Banner "amtliche Warnungen
nicht abrufbar" in der Orts-Vergleich-Mail.

SPEC: docs/specs/modules/feat_1349_compare_unavailable.md (AC-1 … AC-5)

Diese Tests schlagen JETZT absichtlich fehl:
- `LocationResult` hat noch kein `official_alerts_unavailable`-Feld,
- `render_compare_html` rendert keinen Nicht-abrufbar-Banner,
- `comparison_engine` reicht kein Ausfall-Flag durch.

KEIN Mock-Theater: echte `LocationResult`/`ComparisonResult`-DTOs, echter
`render_compare_html`. AC-3 fährt den echten `ComparisonEngine.run()` (Wetter
über den autouse Offline-Fixture-Provider) mit der echten, im Egress-Waechter
geblockten `GeoSphereWarnSource` — realer Fail-soft-Pfad, KEIN werfendes Double.

Fixture-Muster: tests/tdd/test_compare_outlook_placement.py (LocationResult/
ComparisonResult) + tests/tdd/test_issue_1034_official_alerts_foundation.py
(ComparisonEngine.run + _REGISTERED_SOURCES-Isolation).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

_HINT = "nicht abrufbar"


def _loc(name: str, *, unavailable: bool = False, alerts=None,
         lat: float = 47.0, lon: float = 11.0):
    """Ein echtes LocationResult. `official_alerts_unavailable` als Instanz-
    Attribut (im RED-Stand kein Dataclass-Feld — der Renderer liest per getattr;
    nach der Implementierung additives Feld mit Default False)."""
    from app.user import LocationResult, SavedLocation
    lr = LocationResult(
        location=SavedLocation(id=name.lower(), name=name, lat=lat, lon=lon,
                               elevation_m=500, timezone="UTC"),
        score=50,
        official_alerts=list(alerts or []),
    )
    lr.official_alerts_unavailable = unavailable
    return lr


def _result(locs):
    from app.user import ComparisonResult
    return ComparisonResult(
        locations=locs, time_window=(0, 23),
        target_date=date(2026, 7, 20), created_at=datetime(2026, 7, 20, 4, 1),
    )


def _real_alert():
    from services.official_alerts import OfficialAlert
    return OfficialAlert(
        source="meteoalarm", hazard="thunderstorm", level=3,
        label="Gewitterwarnung Stufe Orange",
    )


def _render(locs):
    from output.renderers.email.compare_html import render_compare_html
    return render_compare_html(_result(locs))


def test_ac1_flag_gesetzt_zeigt_banner():
    """AC-1: ≥1 Ort mit official_alerts_unavailable=True -> HTML enthält den
    Nicht-abrufbar-Hinweis."""
    html = _render([_loc("Nizza", unavailable=True), _loc("Cannes")])
    assert _HINT in html.lower(), (
        f"AC-1: Bei ≥1 Ort mit Ausfall MUSS die Compare-Mail den Nicht-abrufbar-"
        f"Hinweis zeigen (gerendertes HTML)."
    )


def test_ac2_flag_false_byte_identisch_ohne_banner():
    """AC-2: kein Ort mit Flag -> HTML byte-identisch zur Baseline und ohne Banner."""
    html = _render([_loc("Nizza"), _loc("Cannes")])
    baseline = _render([_loc("Nizza"), _loc("Cannes")])
    assert html == baseline, "AC-2: Ohne Ausfall MUSS die Compare-Mail deterministisch identisch sein."
    assert _HINT not in html.lower(), "AC-2: Ohne Flag darf kein Nicht-abrufbar-Banner erscheinen."


def test_ac4_banner_aus_geteiltem_baustein_hochkontrast():
    """AC-4: der Banner stammt aus dem geteilten Baustein
    render_official_alerts_unavailable_html (G_DANGER, kein G_INK_FAINT)."""
    from output.renderers.email.unavailable_hint import (
        render_official_alerts_unavailable_html,
    )
    from output.renderers.email.design_tokens import G_DANGER, G_INK_FAINT

    baustein = render_official_alerts_unavailable_html()
    assert _HINT in baustein.lower()
    html = _render([_loc("Nizza", unavailable=True)])
    assert G_DANGER in html, "AC-4: Der Banner MUSS die Gefahr-Farbe G_DANGER tragen."
    # Der geteilte Baustein steht im gerenderten HTML (Kern-Text).
    assert "Amtliche Warnungen aktuell nicht abrufbar" in html, (
        "AC-4: Der Compare-Banner MUSS den geteilten Baustein-Text tragen (kein Neubau)."
    )
    # Der Baustein selbst nutzt kein schwaches Grau — im Banner-Fragment nicht enthalten.
    assert G_INK_FAINT not in baustein, (
        "AC-4: Der geteilte Baustein darf nicht im schwachen Grau G_INK_FAINT stehen."
    )


def test_ac5_mischfall_echte_warnung_und_ausfall_beide_sichtbar():
    """AC-5: ein Ort mit echter Warnung, ein anderer mit Ausfall-Flag -> BEIDE
    Banner erscheinen (orthogonal)."""
    html = _render([
        _loc("Marseille", alerts=[_real_alert()]),
        _loc("Nizza", unavailable=True),
    ])
    assert _HINT in html.lower(), "AC-5: Der Nicht-abrufbar-Hinweis MUSS erscheinen."
    assert "Gewitter" in html, (
        "AC-5: Die echte amtliche Warnung des anderen Orts MUSS ebenfalls erscheinen."
    )


def test_ac3_comparison_engine_echter_failsoft_pfad_setzt_flag():
    """AC-3 REAL-PFAD-REGRESSIONSWAECHTER: ComparisonEngine.run() mit einem Ort
    innerhalb der GeoSphere-Bbox und registrierter echter GeoSphereWarnSource
    (Host warnungen.zamg.at ist im Egress-Waechter BLOCKED) -> die Quelle liefert
    intern fail-soft [] OHNE zu werfen -> das resultierende LocationResult trägt
    official_alerts_unavailable=True. KEIN werfendes Double; Wetter über den
    autouse Offline-Fixture-Provider (kein Netz)."""
    import services.official_alerts.base as oa_base
    from services.comparison_engine import ComparisonEngine
    from services.official_alerts.geosphere_warn import GeoSphereWarnSource, _cache
    from app.profile import ActivityProfile
    from app.user import SavedLocation

    innsbruck = SavedLocation(id="innsbruck", name="Innsbruck",
                              lat=47.26, lon=11.39, elevation_m=574, timezone="UTC")

    backup = list(oa_base._REGISTERED_SOURCES)
    oa_base._REGISTERED_SOURCES.clear()
    _cache.clear()
    try:
        source = GeoSphereWarnSource()
        assert source.covers(47.26, 11.39) is True, "Testkoordinate muss GeoSphere-abdeckend sein."
        oa_base._REGISTERED_SOURCES.append(source)

        result = ComparisonEngine.run(
            [innsbruck],
            time_window=(9, 16),
            target_date=date.today() + timedelta(days=1),
            profile=ActivityProfile.ALLGEMEIN,
        )
        loc = result.locations[0]
        assert loc.official_alerts == [], (
            f"Die geblockte Quelle darf keine Alerts liefern, war {loc.official_alerts!r}"
        )
        assert getattr(loc, "official_alerts_unavailable", False) is True, (
            "AC-3: Der echte Fail-soft-Ausfall der abdeckenden Quelle MUSS "
            "LocationResult.official_alerts_unavailable=True setzen (Regressionswächter "
            "gegen den #1348-Stillschweig-Bug im Compare-Pfad)."
        )
    finally:
        oa_base._REGISTERED_SOURCES.clear()
        oa_base._REGISTERED_SOURCES.extend(backup)
        _cache.clear()
