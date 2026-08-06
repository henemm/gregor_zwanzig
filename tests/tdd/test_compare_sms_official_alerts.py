"""Compare-SMS: amtliche Warnungen als `!`-Kuerzel-Marker pro Ort (#1332).

SPEC: docs/specs/modules/compare_official_alert_channels.md — AC-1, AC-2
Ursprungs-Bug: `render_compare_sms()` las `LocationResult.official_alerts`
GAR NICHT -- keine Warnung erschien in der Compare-SMS, unabhaengig von der
Stufe.

Issue #1461 S3b-2b (AC-17): der Vorgabewert ist seither die Startschwelle
"gering" statt des vormals festen `MIN_SMS_LEVEL` (orange) -- eine gelbe
Warnung (Stufe 2) traegt jetzt ebenfalls den `!`-Kuerzel-Marker. Der
Stufenfilter wird wie in `test_telegram_official_alert_bubble.py:217`
AUS DEM GETEILTEN KATALOG abgeleitet (`min_official_level_for_threshold`),
nicht als Zahl wiederholt.

Verhaltenstests -- KEINE Mocks. Echte `SavedLocation`/`LocationResult`/
`OfficialAlert`-Objekte, echter Renderer-Aufruf (`render_compare_sms`).
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from app.user import ComparisonResult, LocationResult, SavedLocation
from output.renderers.comparison import render_compare_sms
from services.alert_urgency import min_official_level_for_threshold
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
# AC-1 (bis #1461 S3b-2b: AC-17) — nur der Ort mit Warnung >= Startschwelle
# ("gering") traegt den `!`-Marker; darunter bleibt er stumm.
# ---------------------------------------------------------------------------
def test_only_location_at_or_above_threshold_carries_marker():
    threshold = min_official_level_for_threshold("LOW")
    ort_a = _loc_result("Aachen", alerts=[_alert("thunderstorm", 4)])  # rot, weit ueber der Schwelle
    ort_b = _loc_result("Berg", alerts=[_alert("rain", threshold)])  # genau an der Startschwelle
    ort_c = _loc_result("Chur")  # keine Warnung
    ort_d = _loc_result("Dorf", alerts=[_alert("fog", threshold - 1)])  # unter der Startschwelle

    sms = render_compare_sms(_result([ort_a, ort_b, ort_c, ort_d]))

    part_a = _location_part(sms, "Aachen")
    part_b = _location_part(sms, "Berg")
    part_c = _location_part(sms, "Chur")
    part_d = _location_part(sms, "Dorf")

    assert "!TH:H" in part_a, (
        f"Ort mit roter amtlicher Warnung traegt keinen `!`-Kuerzel-Marker: "
        f"{sms!r} (Ortsteil: {part_a!r})"
    )
    assert "!" in part_b, (
        f"AC-17: eine Warnung GENAU an der Startschwelle ('gering', Stufe "
        f"{threshold}) muss seit #1461 S3b-2b einen Marker tragen -- vorher "
        f"war sie gefiltert: {sms!r} (Ortsteil: {part_b!r})"
    )
    assert "!" not in part_c, (
        f"Ort ohne Warnung darf keinen Marker tragen: "
        f"{sms!r} (Ortsteil: {part_c!r})"
    )
    assert "!" not in part_d, (
        f"Eine Warnung UNTER der Startschwelle (Stufe {threshold - 1}) darf "
        f"weiterhin keinen Marker tragen: {sms!r} (Ortsteil: {part_d!r})"
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
