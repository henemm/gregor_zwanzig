"""TDD RED — Issue #1357 (Epic #1372 S4a), AC-7: eine gespeicherte Auswertung,
die es fuer diese Wettergroesse gar nicht gibt, wird nicht still geschluckt.

Spec: docs/specs/modules/trip_aggregation_selection.md (AC-7).
Kontext: docs/context/feat-1357-trip-auswertungswahl.md.

Bezugsfall: ``wind_chill`` kennt laut Katalog nur ``{"min": "wind_chill_min_c",
"max": "wind_chill_max_c"}`` (src/app/metric_catalog.py:107) — ein gespeichertes
``aggregations=["avg"]`` ist dort unaufloesbar. Vorbild fuer das erwartete
Verhalten ist ``compare_outlook_metric_ids.resolve_outlook_metrics()``
(src/output/renderers/compare_outlook_metric_ids.py:49-80): unaufloesbare
Eintraege werden verworfen UND per ``logger.warning`` sichtbar gemacht, gueltige
Teile der Auswahl bleiben in ihrer Reihenfolge erhalten.

Kern-Schicht, deterministisch: kein Mock, kein Netz, kein ``patch()``.

RED heute: der Renderer liest die Auswahl ueberhaupt nicht (0 Leser von
``MetricConfig.aggregations`` in ``src/``) und faellt damit unbemerkt auf die
fest verdrahtete Tiefstwert-Form zurueck — der ungueltige Eintrag verschwindet
spurlos.
"""
from __future__ import annotations

import inspect
import logging

from tests.tdd._trip_aggregation_fixtures import TZ, dp, make_segment

_WC_MIN = "6.6"
_WC_MAX = "9.0"


def _segments():
    # UTC 6,7,8 -> CEST 8,9,10; gefuehlt 9.0 / 8.0 / 6.6
    return [make_segment([
        dp(6, wind_chill_c=9.0),
        dp(7, wind_chill_c=8.0),
        dp(8, wind_chill_c=6.6),
    ])]


def _pills(selection: dict[str, list[str]]) -> list[str]:
    from output.renderers.email.helpers import build_metrics_summary_pills

    params = inspect.signature(build_metrics_summary_pills).parameters
    assert "metric_aggregations" in params, (
        "build_metrics_summary_pills nimmt keine Auswertungs-Auswahl entgegen — "
        "eine ungueltige gespeicherte Auswahl kann gar nicht erst geprueft "
        "werden (Spec Implementation Details §3: Schluesselwort-Parameter "
        f"`metric_aggregations`). Vorhandene Parameter: {list(params)}"
    )
    pills = build_metrics_summary_pills(
        _segments(), ["wind_chill"], {}, tz=TZ, metric_aggregations=selection,
    )
    return [text for text, _tone in pills]


# ---------------------------------------------------------------------------
# AC-7 — unaufloesbare Auswertung wird verworfen ...
# ---------------------------------------------------------------------------

def test_unresolvable_aggregation_does_not_fall_back_to_default():
    """AC-7 (RED): ``aggregations=["avg"]`` bei der gefuehlten Temperatur darf
    NICHT stillschweigend die Vorgabe-Darstellung erzeugen.

    Genau das passiert heute: die Auswahl wird ignoriert, die Kachel zeigt
    unveraendert ``gef. min 6.6°C · 10:00``. Der Nutzer sieht nirgends, dass
    seine gespeicherte Wahl unmoeglich ist.
    """
    texts = _pills({"wind_chill": ["avg"]})

    assert not any(_WC_MIN in t or _WC_MAX in t for t in texts), (
        "AC-7: unaufloesbare Auswertung 'avg' erzeugt trotzdem eine Kachel mit "
        f"Werten — got: {texts}"
    )
    assert texts == [], (
        f"AC-7: erwartet keine Kachel fuer eine restlos unaufloesbare "
        f"Auswahl — got: {texts}"
    )


# ---------------------------------------------------------------------------
# ... und sichtbar protokolliert
# ---------------------------------------------------------------------------

def test_unresolvable_aggregation_is_logged(caplog):
    """AC-7 (RED): das Verwerfen wird nachvollziehbar protokolliert (Warnung
    nennt Groesse und die unmoegliche Auswertung), analog
    ``resolve_outlook_metrics()`` (#1361 Befund 3)."""
    with caplog.at_level(logging.WARNING):
        _pills({"wind_chill": ["avg"]})

    hits = [
        r.getMessage() for r in caplog.records
        if r.levelno >= logging.WARNING
        and "wind_chill" in r.getMessage() and "avg" in r.getMessage()
    ]
    assert hits, (
        "AC-7: keine Warnung, die Groesse ('wind_chill') und unaufloesbare "
        "Auswertung ('avg') benennt — der ungueltige Eintrag verschwindet "
        f"still. Aufgezeichnet: {[r.getMessage() for r in caplog.records]}"
    )


# ---------------------------------------------------------------------------
# AC-7 — gueltige Teile einer gemischten Auswahl bleiben erhalten
# ---------------------------------------------------------------------------

def test_valid_part_of_mixed_selection_survives(caplog):
    """AC-7 (RED): bei ``["avg", "max"]`` wird nur der unmoegliche Teil
    verworfen — der Hoechstwert erscheint weiter, und die Verwerfung wird
    protokolliert („gueltige Teile bleiben", Spec AC-7)."""
    with caplog.at_level(logging.WARNING):
        texts = _pills({"wind_chill": ["avg", "max"]})

    assert any(_WC_MAX in t for t in texts), (
        f"AC-7: gueltiger Teil der Auswahl ('max' -> {_WC_MAX}°C) fehlt — "
        f"got: {texts}"
    )
    assert not any(_WC_MIN in t for t in texts), (
        f"AC-7: nicht gewaehlter Tiefstwert erscheint — got: {texts}"
    )
    hits = [
        r.getMessage() for r in caplog.records
        if r.levelno >= logging.WARNING and "avg" in r.getMessage()
    ]
    assert hits, (
        "AC-7: der verworfene Teil 'avg' wird nicht protokolliert. "
        f"Aufgezeichnet: {[r.getMessage() for r in caplog.records]}"
    )
