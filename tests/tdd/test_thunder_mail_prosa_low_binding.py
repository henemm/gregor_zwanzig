"""Issue #1474 (S3 zu #1419), AC-3 -- angepasst durch Issue #1474b.

SPEC: docs/specs/modules/feat_1474_gewitter_befund_stufen.md v2.3 Abschnitt 2
(urspruengliche Bindung an MED), abgeloest durch
docs/specs/modules/fix_1474b_gewitterschwelle_cockpit.md (PO-Entscheidung
2026-08-03: die Prosa-Pille meldet am Standard-Trip jetzt schon ab "leicht").

`email/helpers.py::_pill_for_metric(metric_id="thunder", ...)` band den Satz
"Gewitter ab HH:00 · staerkste HH:00" zunaechst an die benannte Stufe MED
(`thunder_ordinal(lvl) >= thunder_ordinal(ThunderLevel.MED)`). Issue #1474b
ersetzt das durch die konfigurierbare Erwaehnungsschwelle
(`_sms_mention_threshold("thunder", configured)`), Standardwert weiterhin
1.0 ("ab leicht") -- SMS-identisch. `test_ac3_mittel_loest_den_uhrzeit_satz_aus`
bleibt unveraendert gruen (MED loest weiterhin aus).

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


def test_ac5_1474b_nur_leicht_loest_den_uhrzeit_satz_am_standard_trip_aus():
    """Issue #1474b AC-5 (PO-Entscheidung 2026-08-03, ersetzt die alte
    #1474-S3-Erwartung): ein Trip OHNE eigene Gewitter-Schwellen-Einstellung
    zeigt den Satz "Gewitter ab HH:00 · staerkste HH:00" schon bei reinem
    ThunderLevel.LOW ("leicht") -- die Pille liest die konfigurierbare
    Erwaehnungsschwelle (Standard 1.0, SMS-identisch), nicht mehr fest MED."""
    from output.renderers.email.helpers import _pill_for_metric

    result = _pill_for_metric("thunder", {}, _dps_only_low(), tz=TZ)
    assert result is not None, "Erwartet ein (text, tone)-Tupel, erhalten None"
    text, _tone = result
    # #1493: der Satz traegt jetzt das Stufenwort ("Gewitter leicht ab
    # HH:00") -- die Aussage dieses Tests (Satz erscheint bei reinem LOW)
    # bleibt, das erwartete Zeichenmuster zieht mit.
    assert "Gewitter leicht ab" in text, (
        "Der Uhrzeit-Satz muss am Standard-Trip schon bei reinem 'leicht' "
        f"(LOW) erscheinen. Erhalten: {text!r}"
    )


def test_ac3_mittel_loest_den_uhrzeit_satz_aus():
    """AC-3 (positiver Fall): sobald mindestens eine Stunde ThunderLevel.MED
    erreicht, erscheint der Satz weiterhin -- das heutige reale Verhalten
    bleibt fuer MED/HIGH unveraendert."""
    from output.renderers.email.helpers import _pill_for_metric

    result = _pill_for_metric("thunder", {}, _dps_reaching_med(), tz=TZ)
    assert result is not None, "Erwartet ein (text, tone)-Tupel, erhalten None"
    text, _tone = result
    # #1493: Stufenwort im Satz (siehe oben).
    assert "Gewitter mittel ab" in text, (
        f"Der Uhrzeit-Satz muss bei erreichtem MED erscheinen. Erhalten: {text!r}"
    )
