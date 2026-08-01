"""Vorschau zeigt dieselben Stundenspalten wie die zugestellte Mail.

Issue #1406 Scheibe B, AC-8.
SPEC: docs/specs/modules/feat_1406b_stundenverlauf_katalog.md

``render_compare_email_preview()`` (``src/services/validator_render_service.py``)
ruft ``render_compare_html()`` heute OHNE ``hourly_metrics`` auf. Die Vorschau
im Editor zeigt deshalb immer die volle Spaltenmenge, gleichgueltig was der
Nutzer gewaehlt hat — und ein Nachweis, der ueber diesen Endpunkt gefuehrt
wird, sieht die Wirkung der Auswahl nicht (Muster #1435 E3b:
``build_token_line()`` ohne ``profile=``).

Beobachtbar ist die Auswahl in der Vorschau ueber die Einheiten-Legende unter
der Stundentabelle: sie entsteht in ``_render_units_legend()`` aus genau
derselben Quelle wie die Spaltenkoepfe (``_visible_hour_metrics``). Die
Stub-Orte der Vorschau tragen keine Stundendaten, also gibt es dort keine
Tabelle — die Legende ist die einzige Stelle, an der die Auswahl sichtbar
wird, und damit der ehrliche Pruefpunkt.

Der Request wird ueber das ECHTE Pydantic-Modell des Endpunkts gebaut
(``CompareEmailPreviewBody``) — so muss die Auswahl auch wirklich durch den
API-Vertrag reisen und nicht nur durch eine testeigene Attrappe.

Kern-Schicht, deterministisch: kein Netz, kein SMTP, keine Mocks/``patch()``.
"""
from __future__ import annotations

import re

from api.routers.validator import CompareEmailPreviewBody
from app.metric_catalog import get_metric
from output.renderers.email.compare_html import render_compare_html
from services.validator_render_service import render_compare_email_preview

_TAGS = re.compile(r"<[^>]+>")

# Eine eingeschraenkte Auswahl: zwei bestehende Groessen, KEINE der uebrigen.
AUSWAHL = ["t2m_c", "wind10m_kmh"]


def _units_legend(html: str) -> str:
    """Text der Einheiten-Legende unterhalb der Stundentabelle."""
    treffer = re.findall(
        r'<div style="margin-top:8px;font-family:[^"]*font-size:10px;'
        r'color:[^"]*">(.*?)</div>', html, re.S,
    )
    return _TAGS.sub("", treffer[-1]).strip() if treffer else ""


def _body(**extra) -> CompareEmailPreviewBody:
    return CompareEmailPreviewBody(
        profile="wandern", time_window=[6, 20], target_date="2026-07-08",
        **extra,
    )


def test_preview_body_carries_the_hourly_selection():
    """AC-8 (Vertrag): Given die Vorschau soll die Auswahl abbilden koennen /
    When der Request-Body des Vorschau-Endpunkts gebaut wird / Then traegt er
    ein ``hourly_metrics``-Feld. Ohne dieses Feld kann die Vorschau die
    Auswahl gar nicht kennen — der Nachweis liefe am Endpunkt vorbei."""
    body = _body(hourly_metrics=AUSWAHL)

    assert getattr(body, "hourly_metrics", None) == AUSWAHL, (
        "CompareEmailPreviewBody kennt kein `hourly_metrics` — der "
        "Vorschau-Endpunkt kann die Stundenverlauf-Auswahl nicht entgegen"
        "nehmen (validator.py:304-310)."
    )


def test_preview_shows_the_selected_columns_not_all_of_them():
    """AC-8: Given eine eingeschraenkte Stundenverlauf-Auswahl / When die
    Vorschau gerendert wird / Then nennt sie genau die gewaehlten Groessen —
    nicht pauschal alle."""
    eingeschraenkt = render_compare_email_preview(_body(hourly_metrics=AUSWAHL))
    voll = render_compare_email_preview(_body())

    legende = _units_legend(eingeschraenkt)
    assert legende, (
        "Die Vorschau zeigt gar keine Einheiten-Legende — dieser Test kann "
        "die Spaltenmenge dann nicht beobachten (Pruefpunkt kaputt)."
    )
    assert legende != _units_legend(voll), (
        "Die Vorschau sieht mit und ohne Auswahl identisch aus — sie "
        "ignoriert `hourly_metrics` (validator_render_service.py:169-172)."
    )
    for weggelassen in ("gust", "uv_index", "visibility"):
        assert get_metric(weggelassen).col_label not in legende, (
            f"Die Vorschau zeigt '{get_metric(weggelassen).col_label}', obwohl "
            f"diese Groesse nicht gewaehlt ist: {legende!r}"
        )


def test_preview_and_delivered_mail_show_the_same_columns():
    """AC-8 (Paritaet): Given dieselbe Auswahl / When einmal die Vorschau und
    einmal der Versandweg rendert / Then nennen beide dieselbe Spaltenmenge in
    derselben Reihenfolge."""
    vorschau = _units_legend(
        render_compare_email_preview(_body(hourly_metrics=AUSWAHL))
    )
    versand = _units_legend(
        render_compare_html(_leerer_vergleich(), hourly_metrics=AUSWAHL)
    )

    assert vorschau == versand, (
        f"Vorschau ({vorschau!r}) und zugestellte Mail ({versand!r}) zeigen "
        "unterschiedliche Stundenspalten fuer dieselbe Auswahl."
    )


def _leerer_vergleich():
    """Derselbe daten-lose Vergleich, den die Vorschau intern baut
    (``validator_render_service.py:151-166``) — damit der Paritaetsvergleich
    wirklich nur den Auswahl-Durchgriff misst und nicht unterschiedliche
    Wetterdaten."""
    from datetime import date

    from app.user import ComparisonResult, LocationResult, SavedLocation

    loc = LocationResult(
        location=SavedLocation(id="preview-1", name="Vorschau-Ort", lat=47.0,
                               lon=11.0, elevation_m=2000),
        score=85, error=None,
    )
    return ComparisonResult(
        locations=[loc], time_window=(6, 20), target_date=date(2026, 7, 8),
    )
