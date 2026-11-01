"""Modus-Matrix der Trip-Briefing-Mail ``full`` in beiden Sprachen (Issue #2664, AC-4).

SPEC: docs/specs/modules/i18n_p2_briefing_mail_html_2664.md

Neben ``test_issue_811_mode_matrix.py`` (unveraendert): Modus (Einfach/Roh)
x Profil x Metrikauswahl x Sprache, jeweils ECHT ueber
``TripReportFormatter.format_email`` gerendert (kein Mock). Pro Fall gilt der
Vertrag der Matrix (Stundentabelle mit festen Kuerzeln, Ampel nur im
Einfach-Modus) in BEIDEN Sprachen, und die englische Ausgabe traegt in keinem
Modus „Nacht" oder „Ausblick" als Ueberschrift.
"""
from __future__ import annotations

import re

import pytest

from app.metric_catalog import build_default_display_config
from app.profile import ActivityProfile
from tests.helpers.briefing_html_sprache_fixture import render_reich

_AMPEL_DOT = "border-radius:50%"
_NUR_KERN = {"temperature", "wind", "gust", "precipitation", "thunder"}


def _dc(*, roh: bool, auswahl: str):
    dc = build_default_display_config()
    for mc in dc.metrics:
        if auswahl == "kern":
            mc.enabled = mc.metric_id in _NUR_KERN
        if roh:
            mc.format_mode, mc.use_friendly_format = "raw", False
    return dc


def _ueberschriften(html: str) -> list[str]:
    """Texte aller Ueberschriften: <h1>-<h3>, Eyebrows, Abschnittskoepfe."""
    koepfe = re.findall(r"<h[1-3][^>]*>(.*?)</h[1-3]>", html, flags=re.S)
    koepfe += re.findall(r'class="eyebrow"[^>]*>(.*?)</div>', html, flags=re.S)
    koepfe += re.findall(r"letter-spacing:0\.1\d?em;[^>]*>([^<]+)<", html)
    koepfe += re.findall(r"font-size:12px;font-weight:600;[^>]*>([^<]+)<", html)
    return [re.sub(r"<[^>]+>", "", k).strip() for k in koepfe]


def _gewitter_zellen(html: str) -> list[str]:
    return re.findall(r'data-label="Thdr">(.*?)</td>', html, flags=re.S)


@pytest.mark.parametrize("lang", ["de", "en"])
@pytest.mark.parametrize("auswahl", ["standard", "kern"])
@pytest.mark.parametrize("profil", [None, ActivityProfile.WINTERSPORT,
                                    ActivityProfile.WANDERN])
@pytest.mark.parametrize("roh", [False, True], ids=["einfach", "roh"])
def test_matrix_bleibt_in_beiden_sprachen_gruen(roh, profil, auswahl, lang):
    html = render_reich(lang, dc=_dc(roh=roh, auswahl=auswahl), profile=profil).email_html

    # Vertrag der Matrix (#811): Stundentabelle mit festen Kuerzeln.
    assert '<th style="background:#fff;' in html and ">Time</th>" in html
    assert ">Temp</th>" in html and ">Gust</th>" in html and ">Thdr</th>" in html
    zellen = _gewitter_zellen(html)
    assert zellen, "keine Gewitter-Zelle"
    if roh:
        assert not any(_AMPEL_DOT in z for z in zellen)
        stufe = "medium" if lang == "en" else "mittel"
        assert any(z.strip().startswith(stufe) for z in zellen), zellen
    else:
        assert any(_AMPEL_DOT in z for z in zellen)

    koepfe = " | ".join(_ueberschriften(html))
    if lang == "en":
        assert "Nacht" not in koepfe and "Ausblick" not in koepfe, koepfe
        assert "Night at destination" in koepfe and "Outlook · next 3 days" in koepfe
    else:
        assert "Nacht am Ziel" in koepfe and "Ausblick · nächste 3 Tage" in koepfe
