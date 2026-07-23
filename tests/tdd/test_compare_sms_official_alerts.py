"""Compare-SMS: amtliche Warnungen als `!`-Kuerzel-Marker pro Ort (#1332).

SPEC: docs/specs/modules/compare_official_alert_channels.md — AC-1, AC-2
Bug: `render_compare_sms()` liest `LocationResult.official_alerts` bislang
GAR NICHT -- keine Warnung erscheint in der Compare-SMS, unabhaengig von der
Stufe. Diese Tests MUESSEN vor dem Fix rot sein (kein `!`-Marker irgendwo).

Verhaltenstests -- KEINE Mocks. Echte `SavedLocation`/`LocationResult`/
`OfficialAlert`-Objekte, echter Renderer-Aufruf (`render_compare_sms`).
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from app.user import ComparisonResult, LocationResult, SavedLocation
from output.renderers.comparison import render_compare_sms
from services.official_alerts.models import OfficialAlert

UTC = timezone.utc
_TARGET_DATE = date(2026, 7, 23)
WARN_FROM = datetime(2026, 7, 23, 14, 0, tzinfo=UTC)
WARN_TO = datetime(2026, 7, 23, 18, 0, tzinfo=UTC)


def _alert(hazard: str, level: int, *, label: str | None = None) -> OfficialAlert:
    return OfficialAlert(
        source="meteoalarm", hazard=hazard, level=level,
        label=label or hazard, valid_from=WARN_FROM, valid_to=WARN_TO,
        region_label="Region-Test",
    )


def _location(name: str) -> SavedLocation:
    # id abgeleitet aus dem Namen -- fuer diese Tests ohne eigene Bedeutung.
    return SavedLocation(
        id=name.lower(), name=name, lat=45.9, lon=6.87, elevation_m=1035,
    )


def _loc_result(
    name: str, *, alerts: list[OfficialAlert] | None = None,
) -> LocationResult:
    return LocationResult(
        location=_location(name),
        temp_max=18.0, wind_max=8.0,
        official_alerts=list(alerts or []),
    )


def _result(locations: list[LocationResult]) -> ComparisonResult:
    return ComparisonResult(
        locations=locations, time_window=(0, 23), target_date=_TARGET_DATE,
        created_at=datetime(2026, 7, 23, 6, 0),
    )


def _location_part(sms: str, name: str) -> str:
    """Der Teiltext eines Ortes innerhalb der flachen Semikolon-getrennten
    Compare-SMS (bis zum naechsten '; ' bzw. Stringende)."""
    idx = sms.index(name)
    rest = sms[idx:]
    end = rest.find("; ")
    return rest if end == -1 else rest[:end]


# ---------------------------------------------------------------------------
# AC-1 — nur der Ort mit Warnung >= orange traegt den `!`-Marker
# ---------------------------------------------------------------------------
def test_only_location_with_orange_or_red_alert_carries_marker():
    ort_a = _loc_result("Aachen", alerts=[_alert("thunderstorm", 4)])  # rot
    ort_b = _loc_result("Berg", alerts=[_alert("rain", 2)])  # gelb
    ort_c = _loc_result("Chur")  # keine Warnung

    sms = render_compare_sms(_result([ort_a, ort_b, ort_c]))

    part_a = _location_part(sms, "Aachen")
    part_b = _location_part(sms, "Berg")
    part_c = _location_part(sms, "Chur")

    assert "!TH:H" in part_a, (
        f"Ort mit roter amtlicher Warnung traegt keinen `!`-Kuerzel-Marker: "
        f"{sms!r} (Ortsteil: {part_a!r})"
    )
    assert "!" not in part_b, (
        f"Ort mit nur gelber Warnung darf keinen Marker tragen: "
        f"{sms!r} (Ortsteil: {part_b!r})"
    )
    assert "!" not in part_c, (
        f"Ort ohne Warnung darf keinen Marker tragen: "
        f"{sms!r} (Ortsteil: {part_c!r})"
    )


# ---------------------------------------------------------------------------
# AC-2 — mehrere Hazards >= orange an einem Ort: beide Kuerzel, dedupliziert
# ---------------------------------------------------------------------------
def test_multiple_hazards_above_orange_appear_deduplicated():
    ort = _loc_result(
        "Aachen",
        alerts=[
            _alert("thunderstorm", 4),
            _alert("wind_gust", 3),
            # Exaktes Duplikat (gleiche Identitaet+Hazard+Zeitraum) -- muss
            # ueber `dedupe_official_alerts` kollabieren, nicht zweimal
            # erscheinen.
            _alert("thunderstorm", 4),
        ],
    )
    sms = render_compare_sms(_result([ort]))

    assert "!TH:H" in sms, f"Gewitter-Kuerzel fehlt: {sms!r}"
    assert "W:M" in sms, f"Wind-Kuerzel fehlt: {sms!r}"
    assert sms.count("TH:H") == 1, (
        f"Gewitterwarnung darf nach Dedup nur einmal erscheinen: {sms!r}"
    )
