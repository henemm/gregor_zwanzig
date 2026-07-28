"""TDD RED — Issue #1357 (Epic #1372 S4a), AC-1: die gefuehlte Temperatur zeigt
in der Kachelzeile („Metriken-Ueberblick") kuenftig die SPANNE aus Tiefst- und
Hoechstwert, ohne dass der Nutzer irgendetwas einstellt.

Spec: docs/specs/modules/trip_aggregation_selection.md (AC-1).
Kontext: docs/context/feat-1357-trip-auswertungswahl.md.

Kern-Schicht, deterministisch: kein Mock, kein Netz, kein ``patch()``. Echte
``ForecastDataPoint``/``SegmentWeatherData``-Fixtures, echter Aufruf von
``build_metrics_summary_pills`` (src/output/renderers/email/helpers.py:1503).
Fixture-Vorbild: tests/tdd/test_issue_912_pill_textformat.py.

RED heute: ``_pill_for_metric`` (helpers.py:1233-1252) baut fuer ``wind_chill``
ausschliesslich die Tiefstwert-Form „gef. min X.X°C · HH:00" — der bereits
berechnete Hoechstwert (``wind_chill_max_c``, gleicher Rechenweg wie die
gemessene Temperatur, s. services/segment_weather.py:254-281) erscheint nie.

AC-2 (alle uebrigen Kacheln bleiben unveraendert) bekommt bewusst KEINEN neuen
Test: diese Absicherung tragen bereits die Bestands-Golden-Suiten
``tests/golden/email/test_email_html_golden.py`` und
``tests/golden/email/test_email_plain_golden.py`` gegen die Fixtures
``tests/golden/email/*-html.txt`` / ``*-plain.txt`` (Abschnitt
„Metriken-Ueberblick"). Sie sind heute gruen und werden nicht kuenstlich rot
gemacht. Achtung fuer die Umsetzungsphase: dieselben fuenf Fixture-Paare
enthalten je eine ``gef. min ...``-Zeile und muessen als GEWOLLTE Folge von
AC-1 neu erzeugt werden (Spec-Abschnitt „Bewusste Golden-Fixture-
Neuerzeugung", Werkzeug ``tests/golden/email/regenerate.py``).
"""
from __future__ import annotations

from tests.tdd._trip_aggregation_fixtures import TZ, dp, make_segment

# UTC 6,7,8 -> CEST 8,9,10. Gefuehlte Temperatur: 9.0 / 8.0 / 6.6
#  => Tiefstwert 6.6 um 10:00, Hoechstwert 9.0 um 08:00 (deutlich auseinander).
_WIND_CHILL_MIN = "6.6"
_WIND_CHILL_MAX = "9.0"
_ALT_MIN_ONLY_FORM = "gef. min 6.6°C · 10:00"


def _wind_chill_pill_texts() -> list[str]:
    """Kachel-Texte fuer einen Trip mit aktivierter gefuehlter Temperatur und
    OHNE jede Nutzer-Einschraenkung (Aufruf ohne Auswahl-Signal)."""
    from output.renderers.email.helpers import build_metrics_summary_pills
    segs = [make_segment([
        dp(6, wind_chill_c=9.0),
        dp(7, wind_chill_c=8.0),
        dp(8, wind_chill_c=6.6),
    ])]
    pills = build_metrics_summary_pills(segs, ["wind_chill"], {}, tz=TZ)
    return [text for text, _tone in pills]


# ---------------------------------------------------------------------------
# AC-1 — Hoechstwert erscheint ohne jede Nutzeraktion
# ---------------------------------------------------------------------------

def test_wind_chill_default_pill_shows_max_value():
    """AC-1 (RED): der gefuehlte Hoechstwert (9.0°C um 08:00) muss ohne jede
    Nutzereinstellung in der Kachel stehen.

    Heute nicht der Fall: helpers.py:1244-1250 wertet ausschliesslich das
    Minimum der ``wind_chill_c``-Reihe aus.
    """
    texts = _wind_chill_pill_texts()

    assert any(_WIND_CHILL_MAX in t for t in texts), (
        f"AC-1: gefuehlter Hoechstwert {_WIND_CHILL_MAX}°C fehlt in der "
        f"Kachelzeile — got: {texts}"
    )


def test_wind_chill_default_pill_is_no_longer_min_only_form():
    """AC-1 (RED): die bisherige Nur-Tiefstwert-Form darf nach der Umstellung
    nicht mehr die vollstaendige Kachel sein.

    Bewusste Verhaltensaenderung: bislang lieferte der Renderer exakt
    ``gef. min 6.6°C · 10:00``; kuenftig traegt derselbe Datensatz beide
    Auswertungen. Der Bestandstest
    ``test_issue_912_pill_textformat.py::TestAC2WindChill::test_wind_chill_format_exact``
    nagelt genau diese alte Form fest und wird durch die Umsetzung brechen —
    in der Spec als gewollte Fixture-Neuerzeugung dokumentiert.
    """
    texts = _wind_chill_pill_texts()

    assert texts != [_ALT_MIN_ONLY_FORM], (
        f"AC-1: Kachel zeigt weiterhin nur den Tiefstwert — got: {texts}"
    )


def test_wind_chill_default_pill_keeps_min_value():
    """AC-1 (Gegenprobe): der Tiefstwert darf durch die Umstellung NICHT
    verschwinden — die Spanne ergaenzt, sie ersetzt nicht.

    Heute bereits gruen; sichert ab, dass die Umsetzung nicht einfach von
    „nur min" auf „nur max" umschwenkt.
    """
    texts = _wind_chill_pill_texts()

    assert any(_WIND_CHILL_MIN in t for t in texts), (
        f"AC-1: gefuehlter Tiefstwert {_WIND_CHILL_MIN}°C fehlt in der "
        f"Kachelzeile — got: {texts}"
    )


def test_wind_chill_default_pill_keeps_time_anchor():
    """AC-1 (Gegenprobe): die Spannen-Form behaelt einen Uhrzeit-Anker, wie ihn
    die gemessene Temperatur fuehrt (``8–11°C · Max 10:00``).

    Heute bereits gruen; verhindert, dass die Umstellung den Zeitbezug
    ersatzlos herauswirft.
    """
    texts = _wind_chill_pill_texts()

    assert any(":00" in t for t in texts), (
        f"AC-1: Uhrzeit-Anker fehlt in der Kachelzeile — got: {texts}"
    )
