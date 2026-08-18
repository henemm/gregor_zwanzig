"""TDD -- Adversary-Befund F002 (Nachbesserung zu Issue #1474b, PO-Freigabe
2026-08-04).

SPEC: docs/specs/modules/fix_1474b_gewitterschwelle_cockpit.md

``helpers.py:1576-1583`` (``_pill_for_metric``) mit
``metric_format.py:239-241`` (``thunder_ordinal``): bei ``sms_threshold=0.0``
ist ``thunder_ordinal(ThunderLevel.NONE) == 0 >= 0.0`` wahr -- eine
gewitterfreie Etappe erzeugt faelschlich den Satz "Gewitter ab HH:00 ·
staerkste HH:00", obwohl gar kein Gewitter vorliegt.

Fix: zusaetzlich zur Schwellenbedingung wird verlangt, dass die Stufe
mindestens ``ThunderLevel.LOW`` erreicht -- unabhaengig von der
eingestellten Schwelle darf der Satz fuer ``ThunderLevel.NONE`` niemals
erscheinen.

Keine Mocks -- echte ForecastDataPoint-Stundenreihe, echter Aufruf von
``_pill_for_metric()`` (SSoT fuer die Mail-Prosa-Pille).
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.models import ForecastDataPoint, ThunderLevel

TZ = ZoneInfo("Europe/Berlin")

# #1493: der Uhrzeit-Satz der Gewitter-Pille traegt seit Issue #1493 das
# Stufenwort ("Gewitter mittel ab 14:00 · staerkste 18:00"). Abwesenheit
# wird deshalb gegen dieses MUSTER geprueft -- die alte Zeichenkette
# "Gewitter ab" ist heute auch im Positivfall abwesend und als
# Negativ-Assertion damit blind.
_UHRZEIT_SATZ_RE = re.compile(r"Gewitter (?:leicht|mittel|hoch) ab \d{2}:00")


def _dps_all_none() -> list:
    """Stundenreihe ausschliesslich ThunderLevel.NONE -- kein Gewitter."""
    base = datetime(2026, 8, 3, 6, 0, tzinfo=timezone.utc)
    return [
        ForecastDataPoint(ts=base, thunder_level=ThunderLevel.NONE),
        ForecastDataPoint(ts=base.replace(hour=10), thunder_level=ThunderLevel.NONE),
        ForecastDataPoint(ts=base.replace(hour=14), thunder_level=ThunderLevel.NONE),
        ForecastDataPoint(ts=base.replace(hour=18), thunder_level=ThunderLevel.NONE),
    ]


def test_zero_threshold_does_not_trigger_gewitter_ab_for_thunder_free_stage():
    """F002: Schwelle 0.0 ('ab kein') + ausschliesslich ThunderLevel.NONE
    darf den Satz 'Gewitter ab' NICHT ausloesen. Vor dem Fix: NONE hat
    Ordinal 0, ``0 >= 0.0`` ist wahr -- falscher Alarm."""
    from output.renderers.email.helpers import _pill_for_metric

    result = _pill_for_metric("thunder", {"thunder": 0.0}, _dps_all_none(), tz=TZ)
    assert result is not None, "Erwartet ein (text, tone)-Tupel, erhalten None"
    text, _tone = result
    # #1493: gegen das MUSTER pruefen ("Gewitter <stufe> ab HH:00"), sonst
    # waere die Abwesenheit von "Gewitter ab" nach #1493 trivial wahr.
    assert _UHRZEIT_SATZ_RE.search(text) is None, (
        "F002: bei Schwelle 0.0 und einer gewitterfreien Etappe (nur "
        f"ThunderLevel.NONE) darf 'Gewitter ab' nicht erscheinen. Erhalten: "
        f"{text!r}"
    )
    assert text == "kein Gewitter", (
        f"Erwartet die Entwarnung 'kein Gewitter', erhalten: {text!r}"
    )
