"""Windrichtung in der Vergleichs-Mail faerben, Scheibe S2 von Epic #3222 (Issue #3228).

Spec: docs/specs/modules/feat_3228_windrichtung_mail.md (AC-5, AC-8).

Kein Mock: echte ``LocationResult``/``ForecastDataPoint``/``ComparisonResult``,
echter ``render_compare_html``-Aufruf (pure function, ohne Netz, ohne Engine).

Messstellen im HTML:
* Uebersicht: Zeile ``Windrichtung`` (``wind_direction_avg``), je Ort eine
  ``<td>``; Toenung = ``background:<tone_css(level)[0]>``, ungefaerbt =
  ``background:transparent``.
* Stundentabelle je Ort (Kopf ``Zeit``): Wind-Zelle mit angehaengtem Kompass
  (Merge, ``hourly_metrics`` enthaelt ``wind10m_kmh`` und ``wind_direction_deg``).

Ampel des Vergleichs: Vorlage ``allgemein`` (Wind 30/50/70 -> 30 km/h gelb)
plus Windrichtung ``sektoren`` = [N] mit Grenzen 10/20/40 (30 km/h -> ORANGE).
Orange kann damit nur aus dem Sektor kommen.
"""
from __future__ import annotations

import re
from datetime import date, datetime

from app.models import ForecastDataPoint
from app.user import ComparisonResult, LocationResult, SavedLocation
from output.renderers.email.compare_html import render_compare_html
from output.renderers.email.design_tokens import tone_css

_BG_TO_LEVEL = {tone_css(lvl)[0].lower(): lvl for lvl in ("yellow", "orange", "red")}

SEKTOR_N = {"display_config": {"ampel": {"template": "allgemein", "metrics": {"wind_direction": {
    "enabled": True, "modus": "sektoren", "sektoren": ["N"],
    "upper": {"yellow": 10, "orange": 20, "red": 40}}}}}}
SEKTOR_AUS = {"display_config": {"ampel": {"template": "allgemein", "metrics": {"wind_direction": {
    "enabled": True, "modus": "aus",
    "upper": {"yellow": 10, "orange": 20, "red": 40}}}}}}
RADTOUR = {"display_config": {"ampel": {"template": "radtour"}}}
RADTOUR_AUS = {"display_config": {"ampel": {"template": "radtour",
                                            "metrics": {"wind_direction": {"modus": "aus"}}}}}

ENABLED = ["wind_max", "wind_direction_avg"]
HOURLY = ["wind10m_kmh", "wind_direction_deg"]


def _ort(lid: str, name: str, deg: float, kmh: float = 30.0) -> LocationResult:
    dps = [
        ForecastDataPoint(ts=datetime(2026, 7, 23, h, 0), t2m_c=10.0, wind10m_kmh=kmh,
                          gust_kmh=kmh, wind_direction_deg=deg, precip_1h_mm=0.0)
        for h in (9, 10, 11)
    ]
    return LocationResult(
        location=SavedLocation(id=lid, name=name, lat=47.27, lon=11.39, elevation_m=574),
        official_alerts=[], hourly_data=dps, wind_max=kmh, wind_direction_avg=deg,
    )


def _ergebnis() -> ComparisonResult:
    return ComparisonResult(
        locations=[_ort("skiort", "Skiort", 0), _ort("suedort", "Suedort", 180)],
        time_window=(9, 12), target_date=date(2026, 7, 23),
        created_at=datetime(2026, 7, 23, 4, 0),
    )


def _render(preset: dict) -> str:
    return render_compare_html(
        _ergebnis(), enabled_metrics=ENABLED, hourly_metrics=HOURLY, preset=preset,
    )


def _bg(td_open: str):
    m = re.search(r"background:(#[0-9a-fA-F]{6}|transparent)", td_open)
    assert m, f"Testdaten-Fehler: Zelle ohne background-Angabe: {td_open[:200]}"
    v = m.group(1).lower()
    return None if v == "transparent" else _BG_TO_LEVEL.get(v, f"unbekannt:{v}")


def _uebersicht_windrichtung(html: str) -> list:
    """Toenung der Windrichtungs-Zelle je Ort (Reihenfolge der Orte)."""
    for tr in re.findall(r"<tr[^>]*>.*?</tr>", html, re.S):
        tds = re.findall(r"(<td[^>]*>)(.*?)</td>", tr, re.S)
        if tds and re.sub(r"<[^>]+>", "", tds[0][1]).strip() == "Windrichtung":
            return [_bg(o) for o, _ in tds[1:]]
    raise AssertionError("Testdaten-Fehler: Uebersichtszeile 'Windrichtung' fehlt")


def _stunden_wind(html: str) -> list[list]:
    """Je Ort (Reihenfolge im HTML) die Toenung der Wind-Zellen der Stundentabelle."""
    out = []
    for table in re.findall(r"<table[^>]*>.*?</table>", html, re.S):
        if ">Zeit<" not in table:
            continue
        orte = []
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", table, re.S):
            if "<th" in tr:
                continue
            tds = re.findall(r"(<td[^>]*>)(.*?)</td>", tr, re.S)
            orte.append((_bg(tds[1][0]), re.sub(r"<[^>]+>", "", tds[1][1]).strip()))
        out.append(orte)
    assert len(out) == 2, f"Testdaten-Fehler: erwartet 2 Stundentabellen, gefunden {len(out)}"
    return out


# ---------------------------------------------------------------------------
# AC-5: Sektor N, Skiort Nordwind gefaerbt, Suedort Suedwind ungefaerbt
# ---------------------------------------------------------------------------

def test_ac5_uebersicht_windrichtung_nordort_orange_suedort_ungefaerbt():
    """AC-5: Uebersichtszeile Windrichtung: Skiort (30 km/h aus N, Sektor N
    markiert) orange; Suedort (30 km/h aus S) ungefaerbt."""
    html = _render(SEKTOR_N)
    assert "Skiort" in html and "Suedort" in html
    assert _uebersicht_windrichtung(_render(SEKTOR_AUS)) == [None, None], "Messaufbau"
    assert _uebersicht_windrichtung(html) == ["orange", None], (
        f"AC-5: erwartet [orange, None], war {_uebersicht_windrichtung(html)}"
    )


def test_ac5_stundentabelle_wind_zelle_mit_sektor_maximum():
    """AC-5 (Stundentabelle, Merge): Skiort-Wind-Zelle orange (Sektor 30 km/h
    schlaegt Windstaerke gelb); Suedort bleibt gelb (nur Windstaerke), exakt
    wie mit ``modus: aus``."""
    ohne = _stunden_wind(_render(SEKTOR_AUS))
    assert [{bg for bg, _ in ort} for ort in ohne] == [{"yellow"}, {"yellow"}], "Messaufbau"
    assert all(text.endswith("N") for text in [t for _, t in ohne[0]]), "Kompass N in Wind-Zelle"

    mit = _stunden_wind(_render(SEKTOR_N))
    assert [bg for bg, _ in mit[0]] == ["orange"] * 3, (
        f"AC-5: Skiort-Wind-Zelle muss orange sein, war {mit[0]}"
    )
    assert mit[1] == ohne[1], "AC-5: Suedort unveraendert (nur Windstaerke)"


# ---------------------------------------------------------------------------
# AC-8: geerbter Modus gegenwind (Vorlage radtour) wirkungslos
# ---------------------------------------------------------------------------

def test_ac8_geerbter_gegenwind_im_ortsvergleich_keine_faerbung_kein_fehler():
    """AC-8: Vergleich mit Vorlage ``radtour`` (erbt ``modus: gegenwind``),
    30 km/h Nordwind: Orte haben keine Fahrtrichtung -> kein Wert, keine
    Faerbung, Mail vollstaendig. Vergleich gegen ``modus: aus`` (bis auf
    Uhrzeiten byte-gleich). Darf vor der Implementierung gruen sein."""
    html = _render(RADTOUR)
    assert "Skiort" in html and "Suedort" in html and "</html>" in html
    assert _uebersicht_windrichtung(html) == [None, None]
    norm = lambda s: re.sub(r"\d{2}:\d{2}", "HH:MM", s)  # noqa: E731
    assert norm(html) == norm(_render(RADTOUR_AUS))
