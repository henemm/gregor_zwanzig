"""Issue #2792 S1c-4b — Gewitter zentral, ein Prädikat, Altlasten ohne Wirkung.

SPEC: docs/specs/modules/feat_2792_s1_profil_ampel.md v1.5, §5 Nachtrag
S1c-4 Punkte 4–9, Nachtrag S1c-4b Punkt 7; AC-5, AC-6, AC-19 (c)/(d)/(e),
AC-24, AC-27.

Hier sind die Farbentscheider selbst der Prüfling (Einheit „Abbildung"):
ihnen wird die aufgelöste Ampel übergeben. Ob die Einstiege das Abo
auflösen, prüft ``test_s1c4b_einstiege_loesen_das_abo_auf.py``.

Kern-Schicht: echte Domänenobjekte, keine Mocks, kein Netz.
"""
from __future__ import annotations

import inspect
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from app.ampel import AMPEL_TEMPLATES, resolve_ampel, thunder_color
from app.models import ThunderLevel

UTC = timezone.utc
VORLAGEN = sorted(AMPEL_TEMPLATES)
STUFEN = [ThunderLevel.NONE, ThunderLevel.LOW, ThunderLevel.MED, ThunderLevel.HIGH]


def _ampel(vorlage: str) -> dict:
    return resolve_ampel({"display_config": {"preset_name": vorlage}})


def _tone_bg(level: str) -> str:
    from output.renderers.email.design_tokens import tone_css
    return tone_css(level)[0]


# ---------------------------------------------------------------------------
# AC-5: eine Gewitterfarbe an allen früheren Dubletten
# ---------------------------------------------------------------------------

def test_gewitterfarbe_der_vorlagen_stimmt_mit_der_spec():
    """Vorbedingung: keins grün, leicht fest gelb (P2), mittel Wassersport
    rot und Allgemein orange."""
    for v in VORLAGEN:
        assert thunder_color(ThunderLevel.NONE, _ampel(v)) == "green"
        assert thunder_color(ThunderLevel.LOW, _ampel(v)) == "yellow"
    assert thunder_color(ThunderLevel.MED, _ampel("wassersport")) == "red"
    assert thunder_color(ThunderLevel.MED, _ampel("allgemein")) == "orange"


@pytest.mark.parametrize("vorlage", VORLAGEN)
@pytest.mark.parametrize("stufe", STUFEN, ids=lambda s: s.name)
def test_ausblick_gewitterzelle_folgt_der_zentralen_abbildung(vorlage, stufe):
    """``outlook._metric_column_bg`` (Ordinal-Zweig): Hintergrund aus
    ``thunder_color``; „leicht" ohne eigenes Hellgelb (AC-19 c), grün färbt
    wie bisher nicht."""
    from output.renderers.email.outlook import _metric_column_bg
    farbe = thunder_color(stufe, _ampel(vorlage))
    erwartet = "" if farbe == "green" else f"background:{_tone_bg(farbe)};"
    col = {"metric_id": "thunder", "kind": "ordinal"}
    assert _metric_column_bg(col, stufe, ampel=_ampel(vorlage)) == erwartet


@pytest.mark.parametrize("vorlage", VORLAGEN)
@pytest.mark.parametrize("stufe", STUFEN, ids=lambda s: s.name)
def test_vergleich_gewitterstufe_folgt_der_zentralen_abbildung(vorlage, stufe):
    """``compare_html._sev_thunder``: dieselbe Farbe wie ``thunder_color``,
    „keins" jetzt grün statt unmarkiert (AC-19 c)."""
    from output.renderers.email.compare_html import _sev_thunder, _to_compare
    a = _ampel(vorlage)
    assert _sev_thunder(stufe, ampel=a) == _to_compare(thunder_color(stufe, a))


@pytest.mark.parametrize("vorlage", VORLAGEN)
def test_telegram_gewitter_emoji_folgt_der_zentralen_abbildung(vorlage):
    """``trip_command_processor``: das Kreis-Emoji je Stufe kommt aus
    ``thunder_color`` mit der Trip-Ampel (Wassersport „mittel" = 🔴)."""
    from services.trip_command_processor import _BAND_EMOJI, _thunder_symbols
    a = _ampel(vorlage)
    symbole = _thunder_symbols(ampel=a)
    for stufe in STUFEN:
        assert symbole[stufe.name] == _BAND_EMOJI[thunder_color(stufe, a)], stufe


# ---------------------------------------------------------------------------
# AC-6 und AC-27: CAPE ohne Farbe, leere Ampel und fehlende Ampel scheitern laut
# ---------------------------------------------------------------------------

def test_cape_traegt_keine_eigene_farbe():
    from app.ampel import hat_ampel, schwellen_aus_ampel
    from output.metric_format import severity_for
    assert hat_ampel("cape") is False
    assert schwellen_aus_ampel(_ampel("allgemein"), "cape") == {}
    assert severity_for("cape", 1600.0, ampel=_ampel("allgemein")) is None


def test_leere_ampel_scheitert_laut():
    from app.ampel import schwellen_aus_ampel
    with pytest.raises(Exception):
        schwellen_aus_ampel({}, "gust")


def test_ausblick_einstieg_verlangt_die_ampel():
    from app.models import SegmentWeatherSummary
    from output.renderers.email.outlook import build_outlook_row
    p = inspect.signature(build_outlook_row).parameters.get("ampel")
    assert p is not None and p.kind is inspect.Parameter.KEYWORD_ONLY
    assert p.default is inspect.Parameter.empty
    with pytest.raises(TypeError):
        build_outlook_row(SegmentWeatherSummary(temp_max_c=9.0), [], "Mo", UTC,
                          metrics=["temperature"], context="route")


# ---------------------------------------------------------------------------
# AC-27 / AC-19 e: Mail-Erwähnung nach demselben Prädikat wie die Kurzkanäle
# ---------------------------------------------------------------------------

def _dps(feld: str, wert: float):
    from app.models import ForecastDataPoint
    return [ForecastDataPoint(ts=datetime(2026, 7, 11, h, tzinfo=UTC), **{feld: wert})
            for h in (10, 11)]


@pytest.mark.parametrize("vorlage,metrik,feld,wert", [
    ("allgemein", "wind", "wind10m_kmh", 29.0), ("allgemein", "wind", "wind10m_kmh", 31.0),
    ("wassersport", "wind", "wind10m_kmh", 7.0), ("wassersport", "wind", "wind10m_kmh", 9.0),
    ("allgemein", "visibility", "visibility_m", 1500.0),
    ("skitouren", "visibility", "visibility_m", 1500.0),
])
def test_mail_erwaehnung_folgt_gelb_oder_schlechter(vorlage, metrik, feld, wert):
    """Die Kachel nennt eine Metrik in Ereignis-Form („ab HH:00") genau dann,
    wenn der Wert gelb oder schlechter ist — beidseitig (Wassersport-Wind
    unter 8) und für die Sicht aus der Ampel (Allgemein gelb unter 2000 m,
    Skitouren unter 1000 m). ``DEFAULTS``/2-km-Literal wirken nicht mehr."""
    from app.ampel import gelb_oder_schlechter
    from output.renderers.email.helpers import _pill_for_metric
    a = _ampel(vorlage)
    text, _ton = _pill_for_metric(metrik, {}, _dps(feld, wert), tz=ZoneInfo("UTC"), ampel=a)
    assert (" ab " in text) is gelb_oder_schlechter(a, metrik, wert), text


@pytest.mark.parametrize("vorlage", ["allgemein", "skitouren"])
def test_luftfeuchte_bleibt_fest_bei_90(vorlage):
    """§5 Punkt 5: Luftfeuchte hat keinen Ampel-Leser, die Erwähnung bleibt
    fest ab 90 % (Wache, schon heute so)."""
    from output.renderers.email.helpers import _pill_for_metric
    for wert, erwaehnt in ((89.0, False), (92.0, True)):
        text, _ = _pill_for_metric("humidity", {}, _dps("humidity_pct", wert),
                                   tz=ZoneInfo("UTC"), ampel=_ampel(vorlage))
        assert (" ab " in text) is erwaehnt, text


# ---------------------------------------------------------------------------
# AC-19 d / AC-24: Wertebereich-Markierung ohne Wirkung
# ---------------------------------------------------------------------------

def test_gespeicherte_wertebereiche_markieren_die_vergleichs_mail_nicht_mehr():
    from app.models import Corridor
    from output.renderers.email.compare_html import render_compare_html
    from tests.tdd.test_s1c4b_einstiege_loesen_das_abo_auf import _ergebnis
    preset = {"id": "cp", "profil": "allgemein"}
    ohne = render_compare_html(_ergebnis(), preset=preset)
    mit = render_compare_html(_ergebnis(), preset=preset, corridors=[
        Corridor(metric="temp_max_c", range=[0.0, 5.0], mark=True)])
    assert mit == ohne


# ---------------------------------------------------------------------------
# Nachtrag v1.5 Punkt 7: Gleichstand im Minimum
# ---------------------------------------------------------------------------

def test_gleichstand_im_minimum_liefert_die_frueheste_stunde_auch_unsortiert():
    """/60-Hinweis a aus 4a: der 4a-Gleichstand hängt an der Eingabe-
    reihenfolge (``min(..., key=)`` nimmt das erste Vorkommen). Unsortierte
    Punkte mit gleichem Minimum müssen trotzdem die früheste Stunde liefern
    (sichtbar ab ``L-17@6``)."""
    from app.models import ForecastDataPoint
    from output.renderers.day_window import hiking_field_min_max_ts
    pts = [ForecastDataPoint(ts=datetime(2026, 7, 20, h, tzinfo=UTC), t2m_c=v)
           for h, v in ((8, -2.0), (14, 9.0), (6, -2.0))]
    _mn, _mx, min_ts, _max_ts = hiking_field_min_max_ts(pts, "t2m_c")
    assert min_ts.hour == 6
    assert date(2026, 7, 20) == min_ts.date()
