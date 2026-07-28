"""TDD RED — Issue #1357 (Epic #1372 S4a), AC-3/AC-4/AC-8: der Nutzer schraenkt
je Wettergroesse ein, welche Auswertungen in der Kachelzeile erscheinen.

Spec: docs/specs/modules/trip_aggregation_selection.md (AC-3, AC-4, AC-8).
Kontext: docs/context/feat-1357-trip-auswertungswahl.md.

Kern-Schicht, deterministisch: kein Mock, kein Netz, kein ``patch()``. Echte
Datenmodell-Fixtures, echter Aufruf von ``build_metrics_summary_pills``
(src/output/renderers/email/helpers.py:1503).

RED heute in zwei Stufen:
 1. ``build_metrics_summary_pills`` nimmt ueberhaupt kein Auswahl-Signal
    entgegen — die Kette ``html.py:1163`` / ``plain.py:155`` / ``compact.py:146``
    reicht nur nackte Metrik-IDs durch (``_pill_metric_ids``), das gespeicherte
    Feld ``MetricConfig.aggregations`` hat bis heute NULL Leser in ``src/``.
 2. Selbst mit Signal baut ``_pill_for_metric`` fuer ``temperature`` und
    ``wind_chill`` je eine fest verdrahtete Form (helpers.py:1218-1251).

AC-9 (Ortsvergleich bleibt von der Trip-Wahl unberuehrt) bekommt bewusst KEINEN
neuen Test: der Vergleich laeuft ueber einen eigenen Renderer-Pfad
(``output/renderers/comparison.py`` bzw. ``email/compare_html.py``, gespeist aus
``compare_outlook_metric_ids.resolve_outlook_metrics``) und liest
``display_config.metrics[].aggregations`` nicht. Die Absicherung tragen die
Bestandssuiten ``tests/unit/test_compare_metric_parity.py``,
``tests/test_compare_top_n_render_invariance.py`` und
``tests/test_wind_chill_max_selectable.py`` (dort insbesondere
``test_compare_renderers_show_wind_chill_min_only_selection_unchanged``). Sie
sind heute gruen und werden nicht kuenstlich rot gemacht; sie muessen es nach
der Umsetzung unveraendert bleiben.
"""
from __future__ import annotations

import inspect

from tests.tdd._trip_aggregation_fixtures import (
    TZ, dp, first_hour, make_segment, shape,
)

# UTC 6,7,8 -> CEST 8,9,10.
#  gefuehlte Temperatur: 9.0 / 8.0 / 6.6  => min 6.6 @10:00, max 9.0 @08:00
#  gemessene Temperatur: 20.0 / 22.0 / 25.0 => min 20 @08:00, max 25 @10:00
_WC_MIN = "6.6"
_WC_MAX = "9.0"


def _segments():
    return [make_segment([
        dp(6, t2m_c=20.0, wind_chill_c=9.0),
        dp(7, t2m_c=22.0, wind_chill_c=8.0),
        dp(8, t2m_c=25.0, wind_chill_c=6.6),
    ])]


def _pills(metric_ids: list[str], selection: dict[str, list[str]]) -> list[str]:
    """Kachel-Texte fuer eine ausdrueckliche Auswertungs-Einschraenkung.

    ``selection`` bildet Metrik-ID -> gewaehlte Auswertungen ab (das, was der
    Nutzer im Trip-Editor einstellt und was als ``MetricConfig.aggregations``
    gespeichert wird).
    """
    from output.renderers.email.helpers import build_metrics_summary_pills

    params = inspect.signature(build_metrics_summary_pills).parameters
    assert "metric_aggregations" in params, (
        "build_metrics_summary_pills nimmt keine Auswertungs-Auswahl entgegen — "
        "die gespeicherte Nutzerwahl (MetricConfig.aggregations) erreicht den "
        "Renderer nicht (Spec Implementation Details §3: Schluesselwort-"
        f"Parameter `metric_aggregations`). Vorhandene Parameter: {list(params)}"
    )
    pills = build_metrics_summary_pills(
        _segments(), metric_ids, {}, tz=TZ, metric_aggregations=selection,
    )
    return [text for text, _tone in pills]


# ---------------------------------------------------------------------------
# AC-3 — „nur Hoechstwert" bei der gefuehlten Temperatur
# ---------------------------------------------------------------------------

def test_wind_chill_max_only_shows_max():
    """AC-3 (RED): schraenkt der Nutzer die gefuehlte Temperatur auf „nur
    Hoechstwert" ein, zeigt die Kachel ausschliesslich den Hoechstwert (9.0°C)
    — der Tiefstwert (6.6°C) darf nicht mehr auftauchen."""
    texts = _pills(["wind_chill"], {"wind_chill": ["max"]})

    assert texts, "AC-3: gar keine Kachel fuer die gefuehlte Temperatur erzeugt"
    assert any(_WC_MAX in t for t in texts), (
        f"AC-3: Hoechstwert {_WC_MAX}°C fehlt trotz Auswahl ['max'] — got: {texts}"
    )
    assert not any(_WC_MIN in t for t in texts), (
        f"AC-3: Tiefstwert {_WC_MIN}°C erscheint trotz Auswahl ['max'] — "
        f"got: {texts}"
    )


# ---------------------------------------------------------------------------
# AC-4 — gleiche Einschraenkung, gleiche Darstellungsform und gleicher Zeitraum
# ---------------------------------------------------------------------------

def test_temperature_and_wind_chill_same_selection_same_shape():
    """AC-4 (RED): gleiche Einschraenkung (jeweils „nur Hoechstwert") ergibt
    bei gemessener und gefuehlter Temperatur dieselbe Darstellungsform.

    Verglichen wird das Geruest (``_trip_aggregation_fixtures.shape``): das
    Praefix ``gef. `` wird entfernt, alle Zahlen durch ``#`` ersetzt. Werte und
    Nachkommastellen duerfen sich also unterscheiden, das Wert-plus-Uhrzeit-
    Muster nicht — genau die Spec-Zusage „dieselbe Fallunterscheidung, nur
    Label-Praefix und Nachkommastellen unterscheiden sich".
    """
    texts = _pills(["temperature", "wind_chill"],
                   {"temperature": ["max"], "wind_chill": ["max"]})

    assert len(texts) == 2, (
        f"AC-4: erwartet je eine Kachel fuer Temperatur und gefuehlte "
        f"Temperatur — got: {texts}"
    )
    temp_text, wc_text = texts[0], texts[1]
    assert wc_text.startswith("gef."), (
        f"AC-4: zweite Kachel ist nicht die gefuehlte Temperatur — got: {texts}"
    )
    assert shape(temp_text) == shape(wc_text), (
        "AC-4: unterschiedliche Darstellungsform bei identischer Auswahl — "
        f"Temperatur {temp_text!r} -> {shape(temp_text)!r}, gefuehlt "
        f"{wc_text!r} -> {shape(wc_text)!r}"
    )


def test_temperature_and_wind_chill_same_selection_same_time_window():
    """AC-4 (RED, zweite Haelfte): beide Werte beziehen sich nachweislich auf
    denselben Zeitraum der Wanderung.

    Nachweis ohne Rechenweg-Nachbau: beide Groessen bekommen in diesem Fixture
    denselben Werteverlauf (20/22/25 bzw. spiegelbildlich), zusaetzlich liegen
    DataPoints AUSSERHALB des Gehzeit-Fensters. Nennen beide Kacheln bei
    „nur Hoechstwert" dieselbe Uhrzeit, stammen sie aus demselben Fenster;
    wuerde eine der beiden ein anderes Fenster benutzen, zoege sie den
    ausserhalb liegenden Extremwert herein.
    """
    from output.renderers.email.helpers import build_metrics_summary_pills

    params = inspect.signature(build_metrics_summary_pills).parameters
    assert "metric_aggregations" in params, (
        "build_metrics_summary_pills nimmt keine Auswertungs-Auswahl entgegen "
        f"(Spec §3: `metric_aggregations`). Vorhandene Parameter: {list(params)}"
    )

    # Gehzeit-Fenster UTC 6..9; die Stunde UTC 10 (CEST 12) liegt ausserhalb
    # und traegt fuer beide Groessen einen extremen Wert.
    segs = [make_segment([
        dp(6, t2m_c=20.0, wind_chill_c=15.0),
        dp(7, t2m_c=22.0, wind_chill_c=17.0),
        dp(8, t2m_c=25.0, wind_chill_c=20.0),
        dp(10, t2m_c=40.0, wind_chill_c=35.0),
    ], start_h_utc=6, end_h_utc=9)]
    pills = build_metrics_summary_pills(
        segs, ["temperature", "wind_chill"], {}, tz=TZ,
        metric_aggregations={"temperature": ["max"], "wind_chill": ["max"]},
    )
    texts = [t for t, _tone in pills]

    assert len(texts) == 2, f"AC-4: zwei Kacheln erwartet — got: {texts}"
    assert first_hour(texts[0]) == first_hour(texts[1]), (
        "AC-4: Temperatur und gefuehlte Temperatur nennen verschiedene "
        f"Uhrzeiten, beziehen sich also nicht auf denselben Zeitraum — "
        f"got: {texts}"
    )
    assert not any("40" in t or "35" in t for t in texts), (
        "AC-4: ein Wert von ausserhalb des Gehzeit-Fensters (UTC 10) ist in "
        f"die Kachel geraten — got: {texts}"
    )


# ---------------------------------------------------------------------------
# AC-8 — bewusst leere Auswahl blendet die Kachel aus
# ---------------------------------------------------------------------------

def test_empty_selection_hides_pill():
    """AC-8 (RED): entfernt der Nutzer bei der gefuehlten Temperatur alle
    Haekchen (``aggregations=[]``), erscheint KEINE Kachel fuer diese Groesse —
    kein leeres, kaputtes oder auf den Vorgabewert zurueckfallendes Element.
    Die uebrigen Kacheln bleiben unberuehrt.
    """
    texts = _pills(["temperature", "wind_chill"], {"wind_chill": []})

    assert not any(t.startswith("gef.") for t in texts), (
        f"AC-8: Kachel der gefuehlten Temperatur erscheint trotz leerer "
        f"Auswahl — got: {texts}"
    )
    assert not any(_WC_MIN in t or _WC_MAX in t for t in texts), (
        f"AC-8: gefuehlte Werte tauchen trotz leerer Auswahl auf — got: {texts}"
    )
    assert len(texts) == 1 and "°C" in texts[0], (
        f"AC-8: die Temperatur-Kachel muss unveraendert bleiben — got: {texts}"
    )
