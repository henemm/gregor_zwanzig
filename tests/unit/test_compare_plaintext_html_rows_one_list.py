"""Ortsvergleich-Mail: Klartext- und HTML-Uebersichtszeilen aus EINER
Zeilenliste (Issue #2991, #1986 NEU-10).

SPEC: docs/specs/modules/refactor_2991_compare_zeilenliste.md

Kern-Schicht, deterministisch: echte ``LocationResult``-Fixtures (aus
``tests/unit/test_compare_metric_order.py``), echte Renderer-Aufrufe, kein
Netz, kein ``Mock``/``patch``/``MagicMock``. Zeilenbeschriftungen werden aus
der fertig gerenderten Mail gelesen (``tests/helpers/compare_order.py``).

AC-Zuordnung (RED = schlaegt vor der Umsetzung fehl):
- AC-1: Klartext-Zeilen == HTML-Zeilen (6 Faelle)          -> RED nur [duplikat]
- AC-2: doppelt gespeicherte Metrik erscheint einmal        -> RED (HTML doppelt)
- AC-3: gleicher Auswahl-Luecken-Hinweis in beiden Fassungen -> Waechter
- AC-4: ``_PLAIN_FMT`` deckt CV2-Schluessel, Pruefung nennt Schluessel -> RED
- AC-5: abgeleitete Sichten unveraendert (Folge, Label-Key, Format) -> Waechter
"""
from __future__ import annotations

import pytest

from output.renderers.channel_layout import selection_gap_notice
from output.renderers.comparison import render_comparison_text
from output.renderers.email.compare_html import CV2_ZEILEN, render_compare_html
from tests.helpers.ampel_allgemein import PRESET_ALLGEMEIN
from tests.helpers.compare_order import (
    html_uebersicht_labels, klartext_uebersicht_labels,
)
from tests.unit.test_compare_metric_order import _result

_CV2_KEYS_OHNE_WARN = [m["key"] for m in CV2_ZEILEN if m["key"] != "warn"]


def _beide_fassungen(enabled_metrics):
    """HTML- und Klartext-Teil derselben Vergleichsmail mit identischen
    Optionen (Muster ``test_compare_metric_default_order_ssot.py``)."""
    ergebnis = _result()
    html = render_compare_html(
        ergebnis, enabled_metrics=enabled_metrics, preset=PRESET_ALLGEMEIN,
    )
    text = render_comparison_text(ergebnis, enabled_metrics=enabled_metrics, preset=None)
    return text, html


# ---------------------------------------------------------------------------
# AC-1: dieselben Zeilen in derselben Reihenfolge
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "enabled_metrics",
    [
        None,
        [],
        ["wind_max", "temp_max"],
        ["temp_max", "wind_max", "temp_max"],
        ["erfunden", "temp_max"],
        ["warn", "temp_max"],
    ],
    ids=["none", "leer", "teilmenge", "duplikat", "unbekannt", "mit_warn"],
)
def test_klartext_und_html_zeilen_gleich(enabled_metrics):
    text, html = _beide_fassungen(enabled_metrics)
    text_labels = klartext_uebersicht_labels(text)
    html_labels = html_uebersicht_labels(html)

    if enabled_metrics is None:
        assert len(html_labels) >= 20, f"Vakuum-Schutz: nur {len(html_labels)} Zeilen"
    elif enabled_metrics:
        assert html_labels, "Vakuum-Schutz: HTML-Uebersicht ohne Zeilen"
    assert text_labels == html_labels, (
        f"Klartext und HTML fuehren verschiedene Uebersichtszeilen "
        f"(enabled_metrics={enabled_metrics}).\n"
        f"HTML:     {html_labels}\nKlartext: {text_labels}"
    )


# ---------------------------------------------------------------------------
# AC-2: doppelt gespeicherte Metrik erscheint genau einmal
# ---------------------------------------------------------------------------

def test_duplikat_erscheint_einmal():
    text, html = _beide_fassungen(["temp_max", "wind_max", "temp_max"])
    text_labels = klartext_uebersicht_labels(text)
    html_labels = html_uebersicht_labels(html)

    assert len(text_labels) == 2, f"Klartext: {text_labels}"
    assert len(html_labels) == 2, (
        f"HTML zeigt die doppelt gespeicherte Metrik mehrfach: {html_labels}"
    )
    for label in text_labels:
        assert html_labels.count(label) == 1, (
            f"{label!r} erscheint {html_labels.count(label)}-mal im HTML: {html_labels}"
        )


# ---------------------------------------------------------------------------
# AC-3: gleicher Auswahl-Luecken-Hinweis mit gleicher Zahl
# ---------------------------------------------------------------------------

def test_auswahl_luecke_zaehlt_gleich():
    # Zwei verschiedene IDs ohne Zeilendefinition, eine davon doppelt:
    # gezaehlt wird je verschiedener ID -> 2.
    auswahl = ["erfunden", "temp_max", "nochwas", "erfunden", "warn"]
    text, html = _beide_fassungen(auswahl)

    erwartet = selection_gap_notice(2, scope="vergleich")
    assert erwartet, "Vakuum-Schutz: Hinweistext leer"
    assert erwartet in text, f"Klartext ohne Hinweis {erwartet!r}"
    assert erwartet in html, f"HTML ohne Hinweis {erwartet!r}"
    for falsch in (1, 3):
        anderer = selection_gap_notice(falsch, scope="vergleich")
        assert anderer not in text and anderer not in html, (
            f"Abweichende Zahl {falsch} in einer Fassung"
        )


# ---------------------------------------------------------------------------
# AC-4: Format-Zuordnung deckt exakt die CV2-Schluessel, Pruefung nennt Schluessel
# ---------------------------------------------------------------------------

def test_format_zuordnung_deckt_cv2_schluessel():
    from output.renderers.comparison import _PLAIN_FMT

    assert len(_CV2_KEYS_OHNE_WARN) >= 20
    assert set(_PLAIN_FMT) == set(_CV2_KEYS_OHNE_WARN), (
        f"nur in _PLAIN_FMT: {sorted(set(_PLAIN_FMT) - set(_CV2_KEYS_OHNE_WARN))}\n"
        f"nur in CV2:        {sorted(set(_CV2_KEYS_OHNE_WARN) - set(_PLAIN_FMT))}"
    )
    assert "warn" not in _PLAIN_FMT


def test_abweichung_nennt_schluessel():
    from output.renderers.comparison import _PLAIN_FMT, _pruefe_plain_fmt

    # Gueltige Zuordnung besteht die Pruefung.
    _pruefe_plain_fmt(dict(_PLAIN_FMT), CV2_ZEILEN)

    zuviel = {**_PLAIN_FMT, "erfundene_metrik_xyz": str}
    with pytest.raises(ValueError) as exc:
        _pruefe_plain_fmt(zuviel, CV2_ZEILEN)
    assert "erfundene_metrik_xyz" in str(exc.value)

    zuwenig = {k: f for k, f in _PLAIN_FMT.items() if k != "humidity_avg"}
    with pytest.raises(ValueError) as exc:
        _pruefe_plain_fmt(zuwenig, CV2_ZEILEN)
    assert "humidity_avg" in str(exc.value)


# ---------------------------------------------------------------------------
# AC-5: abgeleitete Sichten fuer Telegram/Compact/SMS/Placements unveraendert
# ---------------------------------------------------------------------------

# Gepinnt am 2026-11-26 aus dem Stand vor dem Umbau (Klartext-Formate
# byte-gleich halten; Format-Angleichung ist ausdruecklich nicht Teil, #3425).
_FORMAT_SNAPSHOT = {
    "temp_max": (12.3, "12°C"),
    "wind_max": (23.6, "24 km/h"),
    "precip_sum": (3.25, "3.2 mm"),
    "pop_max": (70.0, "70%"),
    "sunny_hours": (4, "4.0h"),
    "cloud_avg": (50, "50%"),
    "uv_max": (6.4, "6"),
    "visibility_min": (3000, "3.0 km"),
    "snow_depth_cm": (35.0, "35 cm"),
    "snow_new_cm": (12.4, "12 cm"),
    "temp_min": (-4.5, "-4°C"),
    "gust_max": (41.2, "41 km/h"),
    "freezing_level": (2850.4, "2850 m"),
    "wind_direction_avg": (213, "213°"),
    "wind_chill_min": (-8.4, "-8°C"),
    "wind_chill_max": (3.6, "4°C"),
    "cloud_low_avg": (40, "40%"),
    "cloud_mid_avg": (25, "25%"),
    "cloud_high_avg": (10, "10%"),
    "humidity_avg": (65.4, "65%"),
    "dewpoint_avg": (4.6, "5°C"),
    "pressure_avg": (1013.4, "1013 hPa"),
    "snowfall_limit": (1950.6, "1951 m"),
}


def test_abgeleitete_sichten_unveraendert():
    from output.renderers import comparison
    from output.renderers.email import compare_html

    keys = [row[0] for row in comparison._PLAIN_ROWS]
    assert keys == _CV2_KEYS_OHNE_WARN
    for key, label_key, _fmt in comparison._PLAIN_ROWS:
        assert label_key == f"vergleich.zeile.{key}"

    assert list(comparison._PLAIN_ROWS_BY_ID) == keys
    assert all(comparison._PLAIN_ROWS_BY_ID[r[0]] is r for r in comparison._PLAIN_ROWS)

    assert comparison._NIE_EINGESTELLT_IDS == tuple(_CV2_KEYS_OHNE_WARN)
    assert len(comparison._NIE_EINGESTELLT_IDS) >= 20

    fmt = {row[0]: row[2] for row in comparison._PLAIN_ROWS}
    assert fmt["thunder_max"] is compare_html._fmt_thunder
    assert fmt["precip_type"] is compare_html._fmt_precip_type
    assert set(_FORMAT_SNAPSHOT) | {"thunder_max", "precip_type"} == set(keys)
    for key, (wert, erwartet) in _FORMAT_SNAPSHOT.items():
        assert fmt[key](wert) == erwartet, f"{key}: {fmt[key](wert)!r} != {erwartet!r}"
