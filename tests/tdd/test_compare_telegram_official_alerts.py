"""Compare-Telegram: amtliche Warnungen gefiltert ab Kanal-Schwelle,
ausgeschrieben wie das Trip-Telegram, OHNE SMS-Kuerzel (#1332).

SPEC: docs/specs/modules/compare_official_alert_channels.md — AC-2
Ursprungs-Bug: `render_compare_telegram()` renderte `LocationResult.
official_alerts` UNGEFILTERT (auch gelb/gruen) ueber
`render_official_alerts_plain()` -- kein Sicherheits-Filter.

Issue #1461 S3b-2b (AC-17): der Vorgabewert ist seither die Startschwelle
"gering" statt des vormals festen `MIN_SMS_LEVEL` (orange) -- eine gelbe
Warnung (Stufe 2) zeigt jetzt ebenfalls einen ausgeschriebenen Warn-Block.
Der Stufenfilter wird wie in `test_telegram_official_alert_bubble.py:217`
AUS DEM GETEILTEN KATALOG abgeleitet (`min_official_level_for_threshold`),
nicht als Zahl wiederholt.

PO-Entscheidung (2026-07-23, final): Compare-Telegram sieht GENAU wie das
Trip-Telegram aus (ausgeschrieben, `render_official_alert_telegram()`),
KEIN SMS-Kuerzel (`!TH:H`) -- das bleibt exklusiv im SMS-Pfad.

Verhaltenstests -- KEINE Mocks. Echte `SavedLocation`/`LocationResult`/
`OfficialAlert`-Objekte, echter Renderer-Aufruf (`render_compare_telegram`).
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from app.user import ComparisonResult, LocationResult, SavedLocation
from output.renderers.comparison import render_compare_telegram
from services.alert_urgency import min_official_level_for_threshold
from services.official_alerts.models import OfficialAlert

UTC = timezone.utc
_TARGET_DATE = date(2026, 7, 23)
WARN_FROM = datetime(2026, 7, 23, 14, 0, tzinfo=UTC)
WARN_TO = datetime(2026, 7, 23, 18, 0, tzinfo=UTC)


def _alert(hazard: str, level: int, *, label: str) -> OfficialAlert:
    return OfficialAlert(
        source="meteoalarm", hazard=hazard, level=level, label=label,
        valid_from=WARN_FROM, valid_to=WARN_TO, region_label="Region-Test",
    )


def _location(name: str) -> SavedLocation:
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


_LOCATION_NAMES = ("Aachen", "Berg", "Chur", "Dorf")


def _location_block(text: str, name: str) -> str:
    """Der Ort-Block innerhalb der zeilenbasierten Compare-Telegram-Nachricht,
    ab der Zeile mit dem Ortsnamen bis (exklusiv) zur naechsten Ort-Zeile
    bzw. Textende."""
    lines = text.split("\n")
    start = next(i for i, line in enumerate(lines) if line == name)
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if lines[i] in _LOCATION_NAMES and lines[i] != name:
            end = i
            break
    return "\n".join(lines[start:end])


# ---------------------------------------------------------------------------
# AC-2 (bis #1461 S3b-2b: AC-17) — nur der Ort mit Stufe >= Startschwelle
# ("gering") zeigt einen ausgeschriebenen Warn-Block (wie das Trip-Telegram),
# NIE das SMS-Kuerzel; darunter bleibt der Ort stumm.
# ---------------------------------------------------------------------------
def test_only_location_at_or_above_threshold_shows_narrative_warn_block_no_sms_shortcode():
    threshold = min_official_level_for_threshold("LOW")
    ort_a = _loc_result(
        "Aachen", alerts=[_alert("thunderstorm", 4, label="Unwetter Gewitter")],
    )  # rot, weit ueber der Schwelle
    ort_b = _loc_result(
        "Berg", alerts=[_alert("rain", threshold, label="Starkregen")],
    )  # genau an der Startschwelle
    ort_c = _loc_result("Chur")  # keine Warnung
    ort_d = _loc_result(
        "Dorf", alerts=[_alert("fog", threshold - 1, label="Nebel")],
    )  # unter der Startschwelle

    text = render_compare_telegram(_result([ort_a, ort_b, ort_c, ort_d]))

    block_a = _location_block(text, "Aachen")
    block_b = _location_block(text, "Berg")
    block_c = _location_block(text, "Chur")
    block_d = _location_block(text, "Dorf")

    assert "Warnstufe ROT" in block_a and "Unwetter Gewitter" in block_a, (
        f"Roter Ort zeigt keinen ausgeschriebenen Warn-Block (Trip-Format "
        f"via render_official_alert_telegram): {text!r} (Block: {block_a!r})"
    )
    assert "!TH" not in block_a and "!TH:H" not in text, (
        f"Compare-Telegram darf KEIN SMS-Kuerzel zeigen (PO-Entscheidung "
        f"2026-07-23, Konsistenz mit Trip-Telegram): {text!r}"
    )
    assert "unbekannt" not in block_a, (
        f"Warn-Header darf kein irrefuehrendes 'unbekannt'-Scope-Segment "
        f"zeigen (#1332 F001, Ortsname steht bereits als Block-Ueberschrift): "
        f"{text!r} (Block: {block_a!r})"
    )
    assert "Warnstufe" in block_b, (
        f"AC-17: eine Warnung GENAU an der Startschwelle ('gering', Stufe "
        f"{threshold}) muss seit #1461 S3b-2b einen ausgeschriebenen "
        f"Warn-Block zeigen -- vorher war sie gefiltert: {text!r} (Block: {block_b!r})"
    )
    assert "Warnstufe" not in block_c and "⚠️" not in block_c, (
        f"Ort ohne Warnung darf keinen Warn-Block zeigen: {text!r} (Block: {block_c!r})"
    )
    assert "Warnstufe" not in block_d and "⚠️" not in block_d, (
        f"Eine Warnung UNTER der Startschwelle (Stufe {threshold - 1}) darf "
        f"weiterhin keinen Warn-Block zeigen: {text!r} (Block: {block_d!r})"
    )
