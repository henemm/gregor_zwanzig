"""Issue #1357 — die Auswertungswahl ist eine EINZELWAHL (PO 2026-07-28:
„Es gibt kein zusaetzlich: entweder oder").

Adversary-Befund F001: bei einer gemischten Auswahl wie ``["min","avg"]`` gewann
die if/elif-Kaskade fuer ``min``/``max``, und ``avg`` verschwand ohne jede
Meldung — der Guard prueft nur Katalog-Zulaessigkeit, und ``avg`` ist bei der
Temperatur katalog-gueltig. Der Fix beseitigt die Kombination strukturell (die
Oberflaeche laesst sie nicht mehr entstehen) und macht sie im Renderer, wo sie
nur noch aus Altbestand kommen kann, sichtbar statt still.

Geprueft wird hier:
 1. die vier sich ausschliessenden Moeglichkeiten je Groesse — Spanne, nur
    Tiefstwert, nur Hoechstwert, nur Mittelwert — und dass „nur Mittelwert" bei
    der gefuehlten Temperatur gar nicht erst angeboten wird (Katalog fuehrt dort
    kein ``avg``-Feld), ohne Sonderpfad fuer diese Groesse;
 2. der Altbestands-Fall: ``["min","max","avg"]`` bedeutet Spanne (und loest
    keinen Fehlalarm aus — genau diese Liste schreibt der Katalog selbst),
    ``["min","avg"]`` wird auf den Tiefstwert abgebildet UND protokolliert.

Kern-Schicht, deterministisch: kein Mock, kein Netz, kein ``patch()``.
Spec: docs/specs/modules/trip_aggregation_selection.md (AC-3, AC-4, AC-7).
"""
from __future__ import annotations

import logging

from tests.tdd._trip_aggregation_fixtures import TZ, dp, make_segment, shape

# UTC 6,7,8 -> CEST 8,9,10.
#  gemessene Temperatur: 20.0 / 22.0 / 25.0 => min 20 @08:00, max 25 @10:00
#  gefuehlte Temperatur:  9.0 /  8.0 /  6.6 => min 6.6 @10:00, max 9.0 @08:00
def _segments():
    return [make_segment([
        dp(6, t2m_c=20.0, wind_chill_c=9.0),
        dp(7, t2m_c=22.0, wind_chill_c=8.0),
        dp(8, t2m_c=25.0, wind_chill_c=6.6),
    ])]


def _pill(metric_id: str, chosen: list[str]) -> str | None:
    """Kachel-Text einer Groesse fuer eine gespeicherte Auswahl (oder ``None``)."""
    from output.renderers.email.helpers import build_metrics_summary_pills
    pills = build_metrics_summary_pills(
        _segments(), [metric_id], {}, tz=TZ,
        metric_aggregations={metric_id: chosen},
    )
    return pills[0][0] if pills else None


# ---------------------------------------------------------------------------
# Die Moeglichkeiten kommen aus dem Katalog, nicht aus einer zweiten Tabelle
# ---------------------------------------------------------------------------

def test_choices_come_from_summary_fields():
    """Temperatur: vier Moeglichkeiten. Gefuehlte Temperatur: drei — „nur
    Mittelwert" entfaellt, weil ``summary_fields`` dort kein ``avg`` fuehrt."""
    from output.renderers.email.helpers import pill_aggregation_choices

    assert pill_aggregation_choices("temperature") == [
        ["min", "max"], ["min"], ["max"], ["avg"],
    ]
    assert pill_aggregation_choices("wind_chill") == [
        ["min", "max"], ["min"], ["max"],
    ], ("Mittelwert wird bei der gefuehlten Temperatur angeboten, obwohl der "
        "Katalog dort kein avg-Feld fuehrt")


# ---------------------------------------------------------------------------
# Jede Moeglichkeit hat ihre eigene Kachel-Form — beide Groessen gleich
# ---------------------------------------------------------------------------

def test_range_choice_shows_span_with_time_anchor():
    assert _pill("temperature", ["min", "max"]) == "20–25°C · Max 10:00"
    assert _pill("wind_chill", ["min", "max"]) == "gef. 6.6–9.0°C · Max 08:00"


def test_min_only_choice_shows_single_value():
    assert _pill("temperature", ["min"]) == "min 20°C · 08:00"
    assert _pill("wind_chill", ["min"]) == "gef. min 6.6°C · 10:00"


def test_max_only_choice_shows_single_value():
    assert _pill("temperature", ["max"]) == "max 25°C · 10:00"
    assert _pill("wind_chill", ["max"]) == "gef. max 9.0°C · 08:00"


def test_avg_only_choice_shows_mean_without_time():
    """Der Mittelwert ist kein Zeitpunkt-Ereignis — deshalb ohne Uhrzeit."""
    text = _pill("temperature", ["avg"])
    assert text == "Ø 22°C", f"Mittelwert-Form unerwartet — got: {text!r}"
    assert ":00" not in text


def test_every_choice_has_the_same_shape_for_both_metrics():
    """Dieselbe Fallunterscheidung fuer beide Groessen: nur Label-Praefix und
    Nachkommastellen duerfen sich unterscheiden, nicht die Form."""
    for choice in (["min", "max"], ["min"], ["max"]):
        temp, wc = _pill("temperature", choice), _pill("wind_chill", choice)
        assert shape(temp) == shape(wc), (
            f"Auswahl {choice}: unterschiedliche Form — {temp!r} vs. {wc!r}"
        )


# ---------------------------------------------------------------------------
# Altbestand: Listen ohne Entsprechung werden abgebildet, nicht verschluckt
# ---------------------------------------------------------------------------

def test_legacy_min_max_avg_means_range(caplog):
    """``["min","max","avg"]`` ist die Katalog-Vorgabe (``default_aggregations``,
    geschrieben von ``build_default_display_config()``) und bedeutet Spanne —
    identisch zu ``["min","max"]``. Genau diese Gleichheit haelt die zehn
    Golden-Fixtures unter ``tests/golden/email/`` unveraendert.
    """
    with caplog.at_level(logging.WARNING):
        text = _pill("temperature", ["min", "max", "avg"])

    assert text == _pill("temperature", ["min", "max"]) == "20–25°C · Max 10:00"
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING], (
        "die vom System selbst geschriebene Katalog-Vorgabe loest einen "
        f"Fehlalarm aus: {[r.getMessage() for r in caplog.records]}"
    )


def test_legacy_min_and_avg_is_mapped_and_logged(caplog):
    """F001: ``["min","avg"]`` liess ``avg`` frueher spurlos verschwinden.

    Jetzt wird die Liste auf die naechstliegende Moeglichkeit („nur
    Tiefstwert") abgebildet UND das Abbilden protokolliert — die Meldung nennt
    Groesse und die gespeicherte Liste.
    """
    with caplog.at_level(logging.WARNING):
        text = _pill("temperature", ["min", "avg"])

    assert text == "min 20°C · 08:00", f"unerwartete Abbildung — got: {text!r}"
    hits = [
        r.getMessage() for r in caplog.records
        if r.levelno >= logging.WARNING
        and "temperature" in r.getMessage() and "avg" in r.getMessage()
    ]
    assert hits, (
        "F001: die gemischte Auswahl wird weiterhin still auf den Tiefstwert "
        f"reduziert. Aufgezeichnet: {[r.getMessage() for r in caplog.records]}"
    )


def test_legacy_max_and_avg_prefers_the_extreme(caplog):
    """``["max","avg"]``: der Extremwert gewinnt (wie die Katalog-Vorgabe
    ``pill_default_aggregations()`` min/max bevorzugt), sichtbar protokolliert."""
    with caplog.at_level(logging.WARNING):
        text = _pill("temperature", ["max", "avg"])

    assert text == "max 25°C · 10:00"
    assert [r for r in caplog.records if r.levelno >= logging.WARNING]
