"""TDD RED — Issue #1474 (S3 zu #1419), AC-3.

SPEC: docs/specs/modules/feat_1474_gewitter_befund_stufen.md v2.3 Abschnitt 2

`email/helpers.py::_pill_for_metric(metric_id="thunder", ...)` bindet den Satz
"Gewitter ab HH:00 · staerkste HH:00" heute an den Literal
`thunder_ordinal(lvl) >= 1`. Nach der Skalenerweiterung (Ordinal 1 = LOW statt
MED) muss dieser Literal an die benannte Stufe MED gebunden sein
(`thunder_ordinal(lvl) >= thunder_ordinal(ThunderLevel.MED)`), sonst loest
schon das schwaechste, unsicherste Signal ("leicht", nur ueber CAPE) einen
konkreten Uhrzeit-Anspruch aus.

RED-Ursache (heute): `ThunderLevel.LOW` existiert nicht -> AttributeError.

Keine Mocks: echte ForecastDataPoint-Reihe durch die echte Renderfunktion
`_pill_for_metric()` (SSoT fuer die Mail-Pille), kein Netz.
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.models import ForecastDataPoint, ThunderLevel

TZ = ZoneInfo("Europe/Berlin")


def _dps_only_low() -> list:
    """Stundenreihe, die NUR ThunderLevel.LOW traegt -- nie MED/HIGH."""
    base = datetime(2026, 8, 3, 6, 0, tzinfo=timezone.utc)
    return [
        ForecastDataPoint(ts=base, thunder_level=ThunderLevel.NONE),
        ForecastDataPoint(ts=base.replace(hour=10), thunder_level=ThunderLevel.LOW),
        ForecastDataPoint(ts=base.replace(hour=14), thunder_level=ThunderLevel.LOW),
        ForecastDataPoint(ts=base.replace(hour=18), thunder_level=ThunderLevel.NONE),
    ]


def _dps_reaching_med() -> list:
    """Dieselbe Reihe, aber MINDESTENS eine Stunde erreicht ThunderLevel.MED."""
    base = datetime(2026, 8, 3, 6, 0, tzinfo=timezone.utc)
    return [
        ForecastDataPoint(ts=base, thunder_level=ThunderLevel.NONE),
        ForecastDataPoint(ts=base.replace(hour=10), thunder_level=ThunderLevel.LOW),
        ForecastDataPoint(ts=base.replace(hour=14), thunder_level=ThunderLevel.MED),
        ForecastDataPoint(ts=base.replace(hour=18), thunder_level=ThunderLevel.NONE),
    ]


def test_ac3_nur_leicht_loest_den_uhrzeit_satz_nicht_aus():
    """AC-3 (Gegenprobe-kritischer Fall): eine Etappe, deren Stundenreihe NUR
    ThunderLevel.LOW traegt, darf den Satz "Gewitter ab HH:00 · staerkste
    HH:00" NICHT zeigen. Bleibt der Literal `>= 1` unveraendert statt auf
    `thunder_ordinal(ThunderLevel.MED)` gehaertet, loest bereits dieser reine
    LOW-Fall aus (Ordinal von LOW ist neu 1) -- dieser Test muss das fangen."""
    from output.renderers.email.helpers import _pill_for_metric

    result = _pill_for_metric("thunder", {}, _dps_only_low(), tz=TZ)
    assert result is not None, "Erwartet ein (text, tone)-Tupel, erhalten None"
    text, _tone = result
    assert "Gewitter ab" not in text, (
        "Der Uhrzeit-Satz darf bei reinem 'leicht' (LOW, nur ueber CAPE "
        f"gesetzt) nicht erscheinen. Erhalten: {text!r}"
    )


def test_ac3_mittel_loest_den_uhrzeit_satz_aus():
    """AC-3 (positiver Fall): sobald mindestens eine Stunde ThunderLevel.MED
    erreicht, erscheint der Satz weiterhin -- das heutige reale Verhalten
    bleibt fuer MED/HIGH unveraendert."""
    from output.renderers.email.helpers import _pill_for_metric

    result = _pill_for_metric("thunder", {}, _dps_reaching_med(), tz=TZ)
    assert result is not None, "Erwartet ein (text, tone)-Tupel, erhalten None"
    text, _tone = result
    assert "Gewitter ab" in text, (
        f"Der Uhrzeit-Satz muss bei erreichtem MED erscheinen. Erhalten: {text!r}"
    )
