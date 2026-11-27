"""Vergleichsmail Klartext-Uebersicht: Zellformate wie im HTML-Teil
(Issue #3431, TDD RED).

SPEC: docs/specs/modules/feat_3431_klartext_zellformate.md (AC-1 bis AC-7).

Kern-Schicht, deterministisch, ohne Netz: echte ``LocationResult``-Objekte
aus der Golden-Fixture (``tests/helpers/vergleichs_mail_fixture.build_result``),
echte Renderer-Aufrufe (``render_compare_email`` liefert HTML UND Klartext
derselben Mail, ``render_compare_telegram``, ``render_compare_compact``).
Kein ``Mock``/``patch``/``MagicMock``.
"""
from __future__ import annotations

import html as _html
import re

import pytest

from output.metric_format import NO_VALUE
from output.renderers.comparison import (
    _plain_metric_cell, render_compare_email, render_compare_telegram,
)
from output.renderers.email.compact_compare import render_compare_compact
from tests.helpers.ampel_allgemein import PRESET_ALLGEMEIN
from tests.helpers.vergleichs_mail_fixture import build_result

LANGS = ["de", "en"]

# Die fuenf Zeilen, deren Klartext-Format bisher handgetippt war.
ZEILEN = ["wind_direction_avg", "sunny_hours", "cloud_low_avg",
          "cloud_mid_avg", "cloud_high_avg"]

# Testwerte mit Nachkommastellen und Soll-Zelle (= HTML-Zelle, Katalog).
WERTE = {
    "wind_direction_avg": (213.4, "213 °"),
    "sunny_hours": (4.0, "4.0 h"),
    "cloud_low_avg": (40.3, "40%"),
    "cloud_mid_avg": (25.4, "25%"),
    "cloud_high_avg": (10.2, "10%"),
}

_TAGS = re.compile(r"<[^>]+>")


def _plain_text(s: str) -> str:
    return _html.unescape(_TAGS.sub("", s)).strip()


def _result():
    """Golden-Fixture; erster Ort (Innsbruck) traegt die fuenf Testwerte,
    die uebrigen Orte haben fuer Windrichtung/Wolkenschichten keinen Wert."""
    result = build_result(mit_fehlerort=True)
    erster = result.locations[0]
    for key, (wert, _soll) in WERTE.items():
        setattr(erster, key, wert)
    return result


def _render_mail(lang: str, enabled_metrics=ZEILEN) -> tuple[str, str]:
    return render_compare_email(
        _result(), enabled_metrics=enabled_metrics, hourly_enabled=False,
        outlook_enabled=False, preset=PRESET_ALLGEMEIN, lang=lang,
    )


def _plain_block(plain: str, ortsname: str) -> dict[str, str]:
    """``{Beschriftung: Zelle}`` der Klartext-Uebersicht eines Ortes."""
    lines = plain.splitlines()
    idx = lines.index(ortsname)
    out: dict[str, str] = {}
    for line in lines[idx + 1:]:
        if not line.startswith("   ") or ": " not in line:
            break
        label, _, cell = line.strip().partition(": ")
        out[label] = cell
    return out


def _html_row(html: str, label: str) -> list[str]:
    """Zellen (ohne Kopfzelle) der HTML-Uebersichtszeile ``label``."""
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
        cells = [_plain_text(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        if cells and cells[0] == label:
            return cells[1:]
    raise AssertionError(f"HTML-Uebersichtszeile {label!r} nicht gefunden")


def _label_je_zeile(plain: str) -> dict[str, str]:
    """Beschriftung je Zeilenschluessel, in Auswahlfolge aus dem Klartext."""
    labels = list(_plain_block(plain, "Innsbruck"))
    assert len(labels) == len(ZEILEN), labels
    return dict(zip(ZEILEN, labels))


# ---------------------------------------------------------------------------
# AC-1/AC-2/AC-3 (+ AC-7 mit lang=en): Klartext-Zelle == HTML-Zelle
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("lang", LANGS)
@pytest.mark.parametrize("key", ZEILEN)
def test_klartext_uebersicht_zeigt_katalog_format(lang, key):
    """AC-1/AC-2/AC-3, AC-7: Given ein Orts-Vergleich mit Windrichtung 213.4,
    4.0 Sonnenstunden und Wolken tief/mittel/hoch 40.3/25.4/10.2 / When die
    Vergleichsmail (DE und EN) gerendert wird / Then zeigt die Klartext-
    Uebersicht ``213 °``, ``4.0 h``, ``40%``/``25%``/``10%`` -- dieselbe
    Zelle wie die HTML-Zeile derselben Mail."""
    html, plain = _render_mail(lang)
    soll = WERTE[key][1]
    label = _label_je_zeile(plain)[key]

    klartext = _plain_block(plain, "Innsbruck")[label]
    assert klartext == soll, f"{key} ({lang}): Klartext {klartext!r} != {soll!r}"
    assert soll in _html_row(html, label), (
        f"{key} ({lang}): HTML-Zeile {label!r} zeigt {_html_row(html, label)} "
        f"statt {soll!r}"
    )


# ---------------------------------------------------------------------------
# AC-4 (+ AC-7): Platzhalter "–" in Klartext und HTML
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("lang", LANGS)
def test_fehlender_wert_gleicher_platzhalter(lang):
    """AC-4, AC-7: Given ein Ort (Lienz) ohne Messwert fuer Windrichtung und
    Wolkenschichten / When Klartext- und HTML-Teil der Vergleichsmail
    gerendert werden / Then steht in beiden der Platzhalter ``–`` (U+2013,
    ``NO_VALUE``), nicht ``-``."""
    assert NO_VALUE == "–"
    html, plain = _render_mail(lang)
    labels = _label_je_zeile(plain)
    lienz = _plain_block(plain, "Lienz")
    for key in ("wind_direction_avg", "cloud_low_avg", "cloud_mid_avg", "cloud_high_avg"):
        label = labels[key]
        assert lienz[label] == NO_VALUE, (
            f"{key} ({lang}): Klartext-Platzhalter {lienz[label]!r} != {NO_VALUE!r}"
        )
        assert NO_VALUE in _html_row(html, label)
    zeilen = [l for l in plain.splitlines() if l.startswith("   ")]
    assert not any(l.endswith(": -") for l in zeilen), zeilen


# ---------------------------------------------------------------------------
# AC-1..AC-3 verallgemeinert: Paritaet je CV2-Zeile ohne eigenes ``fmt``
# ---------------------------------------------------------------------------

_PARITAETS_WERTE = [213.4, 4.0, 0.25, 40.3]


def _cv2_zeilen_ohne_fmt() -> list[dict]:
    from output.renderers.email import compare_html

    zeilen = [m for m in compare_html._visible_metrics(None, "de", ampel={})
              if m["key"] != "warn" and "fmt" not in m]
    assert len(zeilen) >= 18, f"Vakuum-Schutz: nur {len(zeilen)} Zeilen"
    return zeilen


@pytest.mark.parametrize("wert", _PARITAETS_WERTE)
def test_klartext_format_gleich_html_format_je_zeile(wert):
    """AC-1..AC-3 (Paritaet): Given jede CV2-Uebersichtszeile ohne eigenes
    Format und Testwerte mit Nachkommastellen / When Klartext-Zelle
    (``_PLAIN_FMT``) und HTML-Zelle (``_fmt_metric`` mit Register-
    ``decimals``/``unit``) gebildet werden / Then sind beide zeichengleich."""
    from output.renderers import comparison
    from output.renderers.email import compare_html

    abweichungen = {}
    for m in _cv2_zeilen_ohne_fmt():
        klartext = comparison._PLAIN_FMT[m["key"]](wert)
        html_zelle = compare_html._fmt_metric(wert, m.get("decimals"), m.get("unit", ""))
        if klartext != html_zelle:
            abweichungen[m["key"]] = (klartext, html_zelle)
    assert not abweichungen, f"Klartext != HTML bei {wert}: {abweichungen}"


# ---------------------------------------------------------------------------
# AC-5: Telegram-Vergleich und Kompakt-Vergleichsmail ziehen mit
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("lang", LANGS)
def test_telegram_vergleich_gleiches_format(lang):
    """AC-5: Given derselbe Orts-Vergleich / When der Telegram-Vergleich
    gerendert wird / Then zeigt er fuer Windrichtung, Sonnenstunden und
    Wolkenschichten dasselbe Format wie die Klartext-Mail."""
    from i18n import t

    loc = _result().locations[0]
    for key, (_wert, soll) in WERTE.items():
        zelle = _plain_metric_cell(loc, key, lang, ampel=None)
        assert zelle == f"{t(f'vergleich.zeile.{key}', lang)} {soll}", (key, zelle)

    text = render_compare_telegram(_result(), enabled_metrics=ZEILEN, lang=lang)
    for key, (_wert, soll) in WERTE.items():
        assert f"{t(f'vergleich.zeile.{key}', lang)} {soll}" in text, (key, text)


@pytest.mark.parametrize("lang", LANGS)
def test_kompakt_vergleichsmail_gleiches_format(lang):
    """AC-5: Given derselbe Orts-Vergleich / When die Kompakt-Vergleichsmail
    (ASCII) gerendert wird / Then zeigt sie die gerundeten Katalog-Werte
    (Windrichtung ``213`` ohne Nachkommastelle, ``4.0 h``, ``40%``/``25%``/
    ``10%``), wie die Klartext-Mail."""
    text = render_compare_compact(
        _result(), enabled_metrics=ZEILEN, preset=PRESET_ALLGEMEIN, lang=lang,
    )
    zeile = next(l for l in text.splitlines() if l.startswith("Innsbruck:"))
    assert "213.4" not in zeile, zeile
    assert re.search(r"WD 213(?![.\d])", zeile), zeile
    # Gefaltetes `213 °` darf kein Doppel-Leerzeichen hinterlassen.
    assert "WD 213 SU" in zeile, zeile
    assert "  " not in zeile and zeile == zeile.rstrip(), zeile
    for teil in ("SU 4.0 h", "CL 40%", "CM 25%", "CH 10%"):
        assert teil in zeile, (teil, zeile)


# ---------------------------------------------------------------------------
# AC-6: uebrige Zeilen unveraendert und weiterhin gleich zum HTML
# ---------------------------------------------------------------------------

# Bisheriger Stand der uebrigen Zeilen (aus `_FORMAT_SNAPSHOT`,
# tests/unit/test_compare_plaintext_html_rows_one_list.py, 2026-11-26).
_UNVERAENDERT = {
    "temp_max": (12.3, "12°C"),
    "wind_max": (23.6, "24 km/h"),
    "precip_sum": (3.25, "3.2 mm"),
    "pop_max": (70.0, "70%"),
    "cloud_avg": (50, "50%"),
    "uv_max": (6.4, "6"),
    "visibility_min": (3000, "3.0 km"),
    "snow_depth_cm": (35.0, "35 cm"),
    "snow_new_cm": (12.4, "12 cm"),
    "temp_min": (-4.5, "-4°C"),
    "gust_max": (41.2, "41 km/h"),
    "freezing_level": (2850.4, "2850 m"),
    "wind_chill_min": (-8.4, "-8°C"),
    "wind_chill_max": (3.6, "4°C"),
    "humidity_avg": (65.4, "65%"),
    "dewpoint_avg": (4.6, "5°C"),
    "pressure_avg": (1013.4, "1013 hPa"),
    "snowfall_limit": (1950.6, "1951 m"),
}


@pytest.mark.parametrize("key", sorted(_UNVERAENDERT))
def test_uebrige_zeilen_unveraendert(key):
    """AC-6: Given Testwerte fuer alle uebrigen Uebersichtszeilen / When die
    Klartext-Zelle gebildet wird / Then ist sie zeichengleich zum bisherigen
    Stand (``_FORMAT_SNAPSHOT``)."""
    from output.renderers import comparison

    wert, soll = _UNVERAENDERT[key]
    assert comparison._PLAIN_FMT[key](wert) == soll
