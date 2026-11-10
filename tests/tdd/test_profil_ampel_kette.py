"""Issue #2792 S1c-1 — die Ampel wirkt durch die GANZE Renderkette.

SPEC: docs/specs/modules/feat_2792_s1_profil_ampel.md §5 „Träger", Test Plan
„Mutationsgegenprobe"; Adversary-Findings F001–F003
(docs/artifacts/feat-2792-s1c-leser/adversary-dialog.md).

``test_profil_ampel_durchreichen.py`` prüft die ENDPUNKTE (``severity_for``,
``ampel_level``, ``_stage``, ``_metric_column_bg``, ``build_*_metrics``). Diese
Datei prüft die ZWISCHENGLIEDER: jede Funktion zwischen Einstieg und
Farbentscheidung wird mit einer NICHT-allgemeinen Ampel (Skitouren,
Wassersport, Radtour) aufgerufen, und die Farbe wird dort gemessen, wo sie
ankommt — im HTML/Text der Ausgabe bzw. auf der Nachricht. Bei „allgemein"
wäre ein vergessenes Durchreichen unsichtbar; darum hat jeder Fall einen
Wert, bei dem die gewählte Vorlage eine andere Farbe ergibt als „allgemein"
(beides wird geprüft, damit der Test nicht zufällig grün ist).

Unterscheidende Werte (gemessen aus den Vorlagen):
  Böen 52 km/h   Skitouren gelb   / Allgemein orange
  Wind 47 km/h   Skitouren orange / Allgemein gelb
  Regen 6 mm     Skitouren gelb   / Allgemein orange
  Temp +9 °C     Skitouren orange / Allgemein grün
  Sicht 800 m    Skitouren gelb   / Allgemein orange
  UV 5           Wassersport grün / Allgemein gelb
  Regenw. 55 %   Radtour orange   / Allgemein gelb

Text-Kanäle (Alarm-Klartext, Alarm-Telegram, Briefing-Klartext, Telegram-
Tabelle) färben nicht: ``fmt_val(html=False)`` liest die Ampel dort nicht,
ein vergessenes Durchreichen ist in S1c-1 an der Ausgabe nicht messbar. Für
diese Stellen und für die Einstiege wacht die Ratsche am Ende (Zählung der
``resolve_ampel(``-Aufrufe je Funktion).

Kern-Schicht: echte Domänenobjekte, keine Mocks, kein Netz.
"""
from __future__ import annotations

import ast
import dataclasses
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from bs4 import BeautifulSoup

from app.ampel import resolve_ampel

SKI = resolve_ampel({"display_config": {"preset_name": "skitouren"}})
WASSER = resolve_ampel({"display_config": {"preset_name": "wassersport"}})
RAD = resolve_ampel({"display_config": {"preset_name": "radtour"}})
ALLG = resolve_ampel(None)

UTC = timezone.utc
TZ = ZoneInfo("UTC")


def _dot_fill(level: str) -> str:
    from output.renderers.email.helpers import _AMPEL_DOT_COLORS
    return _AMPEL_DOT_COLORS[level][0]


def _tone_bg(level: str) -> str:
    from output.renderers.email.design_tokens import tone_css
    return tone_css(level)[0]


def test_unterscheidende_werte_stimmen():
    """Vorbedingung: jede Testzeile unterscheidet die Vorlage von „allgemein"."""
    from output.metric_format import severity_for
    faelle = [
        ("gust", 52.0, SKI, "yellow", "orange"),
        ("wind", 47.0, SKI, "orange", "yellow"),
        ("precipitation", 6.0, SKI, "yellow", "orange"),
        ("temperature", 9.0, SKI, "orange", "green"),
        ("visibility", 800.0, SKI, "yellow", "orange"),
        ("uv_index", 5.0, WASSER, "green", "yellow"),
        ("rain_probability", 55.0, RAD, "orange", "yellow"),
    ]
    for mid, wert, ampel, vorlage, allgemein in faelle:
        assert severity_for(mid, wert, ampel=ampel) == vorlage, mid
        assert severity_for(mid, wert, ampel=ALLG) == allgemein, mid


# ---------------------------------------------------------------------------
# 1. Alarm: Nachricht -> render_email -> _hours_html -> row_parts -> format_cell
# ---------------------------------------------------------------------------

def _gust_event(*, value_from=None, value_to=52.0):
    from output.renderers.alert.model import AlertEvent, AlertHourRow
    return AlertEvent(
        metric_id="gust", value_from=40.0, value_to=value_to, threshold=10.0,
        cmp="über", occurred_at="12:00", km_from=0.0, km_to=4.0,
        hours=(AlertHourRow("12:00", value_from, value_to),),
    )


def _wind_event():
    from output.renderers.alert.model import AlertEvent, AlertHourRow
    return AlertEvent(
        metric_id="wind", value_from=20.0, value_to=47.0, threshold=10.0,
        cmp="über", occurred_at="13:00", km_from=0.0, km_to=4.0,
        hours=(AlertHourRow("13:00", None, 47.0),),
    )


def _alarm(events, ampel):
    from output.renderers.alert.model import AlertMessage
    return AlertMessage(
        trip_short="Kette", stand_at="06:00", events=tuple(events),
        indicator_keys={"email": frozenset({"gust", "wind"})}, ampel=ampel,
    )


def _stundenzellen(html: str) -> list[str]:
    """Hintergrundfarben der Ampel-Punkte in den Stundenzeilen-Tabellen."""
    soup = BeautifulSoup(html, "html.parser")
    farben = []
    for span in soup.find_all("span"):
        style = span.get("style") or ""
        if "border-radius:50%" in style and "width:10px" in style:
            farben.append(style.split("background:", 1)[1].split(";", 1)[0])
    return farben


@pytest.mark.parametrize("ampel,erwartet", [(SKI, "yellow"), (ALLG, "orange")],
                         ids=["skitouren", "allgemein"])
def test_alarm_mail_einzelereignis_faerbt_stundenzeile_nach_nachrichten_ampel(ampel, erwartet):
    """AC-21 (Kette): Böen 52 km/h in der Alarm-Mail (ein Ereignis) —
    Skitouren gelb, Allgemein orange; die Farbe kommt von ``msg.ampel``."""
    from output.renderers.alert.render import render_email
    html, _plain = render_email(_alarm([_gust_event()], ampel))
    assert _stundenzellen(html) == [_dot_fill(erwartet)]


@pytest.mark.parametrize("ampel,erwartet", [
    (SKI, ["yellow", "orange"]), (ALLG, ["orange", "yellow"]),
], ids=["skitouren", "allgemein"])
def test_alarm_mail_mehrere_ereignisse_faerbt_jede_stundenzeile_nach_nachrichten_ampel(
        ampel, erwartet):
    """Mehr-Ereignis-Zweig von ``render_email``: Böen 52 und Wind 47 —
    Skitouren gelb/orange, Allgemein orange/gelb."""
    from output.renderers.alert.render import render_email
    html, _plain = render_email(_alarm([_gust_event(), _wind_event()], ampel))
    assert _stundenzellen(html) == [_dot_fill(e) for e in erwartet]


def test_alarm_zeilenzellen_alt_und_neu_folgen_der_ampel():
    """``row_parts`` (alt → neu): alt 52 und neu 36 Böen — bei Skitouren
    gelb → grün, bei Allgemein orange → gelb. Beide Zellen einzeln."""
    from output.renderers.alert.hours import row_parts
    from output.renderers.alert.model import AlertHourRow
    e = _gust_event(value_from=52.0, value_to=36.0)
    row = AlertHourRow("12:00", 52.0, 36.0)
    for ampel, erwartet in ((SKI, ["yellow", "green"]), (ALLG, ["orange", "yellow"])):
        teile = row_parts(e, row, {"gust": "raw"}, html=True,
                          indicators=frozenset({"gust"}), ampel=ampel)
        assert [_stundenzellen(p) for p in teile] == [[_dot_fill(x)] for x in erwartet]


def test_alarm_zelle_folgt_der_ampel():
    from output.renderers.alert.hours import format_cell
    for ampel, erwartet in ((SKI, "yellow"), (ALLG, "orange")):
        zelle = format_cell("gust", 52.0, "simplified", html=True, ampel=ampel)
        assert _stundenzellen(zelle) == [_dot_fill(erwartet)]


# ---------------------------------------------------------------------------
# 2. Alarm-Projektion: Ampel landet auf der Nachricht und wählt die Stunden
# ---------------------------------------------------------------------------

_STUNDEN = ((10, 10.0), (11, 35.0), (12, 35.0), (13, 52.0), (14, 10.0))


def _reihe(boeen):
    from services.weather_snapshot import _deserialize_timeseries
    rows = [{"ts": datetime(2026, 5, 1, h, 0, tzinfo=UTC).isoformat(),
             "t2m_c": 10.0, "wind10m_kmh": 10.0, "gust_kmh": g} for h, g in boeen]
    ts = _deserialize_timeseries({"hourly": rows}, "openmeteo")
    assert ts is not None and len(ts.data) == len(rows)
    return ts


def _punkt(name, boeen):
    from app.models import SegmentWeatherSummary
    from services.point_weather import PointWeatherData
    return PointWeatherData(
        id=name.lower(), name=name, lat=47.0, lon=11.0, timeseries=_reihe(boeen),
        aggregated=SegmentWeatherSummary(),
        fetched_at=datetime(2026, 5, 1, 6, 0, tzinfo=UTC), provider="openmeteo",
    )


def _aenderung():
    from app.models import ChangeSeverity, WeatherChange
    return WeatherChange(
        metric="gust_max_kmh", old_value=10.0, new_value=52.0, delta=42.0,
        threshold=20.0, severity=ChangeSeverity.MAJOR, direction="increase",
        segment_id="1", occurred_at=datetime(2026, 5, 1, 13, 0, tzinfo=UTC),
    )


def _anker():
    """Anker 10 (grün) außer 11 Uhr UTC: 35 — dieselbe 35 wie frisch, bei
    Allgemein beidseitig gelb, bei Skitouren beidseitig grün. Liest nur EINE
    Seite des Stufenvergleichs die falsche Ampel, wird 11 Uhr betroffen."""
    return [(h, 35.0 if h == 11 else 10.0) for h, _ in _STUNDEN]


# Angezeigt in Ortszeit der Koordinaten (47/11 = Europe/Vienna, UTC+2).
# Ohne Anker zählt jede Stunde ab Gelb: Skitouren nur 13 Uhr UTC (52 gelb),
# Allgemein 11-13 Uhr UTC (35 gelb, 52 orange).
_STUNDEN_OHNE_ANKER = {"skitouren": ["15:00"], "allgemein": ["13:00", "14:00", "15:00"]}
# Mit Anker zählt der Stufenwechsel: Skitouren nur 13 Uhr UTC; Allgemein
# 12 Uhr (10 grün -> 35 gelb) und 13 Uhr (10 -> 52 orange), nicht 11 Uhr.
_ERWARTETE_STUNDEN = {"skitouren": ["15:00"], "allgemein": ["14:00", "15:00"]}


@pytest.mark.parametrize("name,ampel", [("skitouren", SKI), ("allgemein", ALLG)])
def test_ortsvergleich_alarm_traegt_ampel_und_waehlt_stunden_danach(name, ampel):
    """``to_multi_point_alert_message``: die Ampel reist auf der Nachricht
    mit UND entscheidet (über ``_hour_fields``), welche Stunden ihre Stufe
    gewechselt haben."""
    from output.renderers.alert.project import to_multi_point_alert_message
    msg = to_multi_point_alert_message(
        [("Alpe", [_aenderung()], _punkt("Alpe", _STUNDEN))], tz=TZ, stand_at="06:00",
        anchor_points={"Alpe": _punkt("Alpe", _anker())}, ampel=ampel,
    )
    assert msg.ampel is ampel
    assert [h.time for h in msg.events[0].hours] == _ERWARTETE_STUNDEN[name]


@pytest.mark.parametrize("name,ampel", [("skitouren", SKI), ("allgemein", ALLG)])
def test_einzelort_alarm_traegt_ampel_und_waehlt_stunden_danach(name, ampel):
    """``to_point_alert_message`` delegiert und muss die Ampel mitgeben."""
    from output.renderers.alert.project import to_point_alert_message
    msg = to_point_alert_message(
        [_aenderung()], [_punkt("Alpe", _STUNDEN)], "Alpe", tz=TZ, stand_at="06:00",
        ampel=ampel,
    )
    assert msg.ampel is ampel
    assert [h.time for h in msg.events[0].hours] == _STUNDEN_OHNE_ANKER[name]


def _segment(boeen):
    from app.models import (
        GPXPoint, SegmentWeatherData, SegmentWeatherSummary, TripSegment,
    )
    seg = TripSegment(
        segment_id="1",
        start_point=GPXPoint(lat=47.0, lon=11.0, elevation_m=1000, distance_from_start_km=0.0),
        end_point=GPXPoint(lat=47.05, lon=11.05, elevation_m=1500, distance_from_start_km=6.0),
        start_time=datetime(2026, 5, 1, 10, 0, tzinfo=UTC),
        end_time=datetime(2026, 5, 1, 14, 0, tzinfo=UTC),
        duration_hours=4.0, distance_km=6.0, ascent_m=500, descent_m=0,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=_reihe(boeen), aggregated=SegmentWeatherSummary(),
        fetched_at=datetime(2026, 5, 1, 6, 0, tzinfo=UTC), provider="openmeteo",
    )


@pytest.mark.parametrize("name,ampel", [("skitouren", SKI), ("allgemein", ALLG)])
def test_trip_alarm_traegt_ampel_und_waehlt_stunden_danach(name, ampel):
    """``to_alert_message`` (Trip): dieselbe Kette wie der Ortsvergleich."""
    from output.renderers.alert.project import to_alert_message
    msg = to_alert_message(
        [_aenderung()], [_segment(_STUNDEN)], "Trip", tz=TZ, stand_at="06:00",
        anchor_segments=[_segment(_anker())], ampel=ampel,
    )
    assert msg.ampel is ampel
    assert [h.time for h in msg.events[0].hours] == _ERWARTETE_STUNDEN[name]


def test_radar_buendel_alarm_traegt_die_ampel():
    """``to_multi_location_onset_alert_message``: die Ampel landet auf der
    Nachricht (Onset-Ereignisse haben keine Stundenzeilen — gemessen wird
    das Feld, das die Renderer lesen)."""
    from output.renderers.alert.project import to_multi_location_onset_alert_message
    from services.radar_service import NowcastResult
    nc = NowcastResult(onset_minutes=10, intensity_label="Regen", source="radar",
                       is_convective=False)
    msg = to_multi_location_onset_alert_message(
        [("A", nc), ("B", nc)], tz=UTC, stand_at="06:00", ampel=SKI)
    assert msg.ampel is SKI


# ---------------------------------------------------------------------------
# 3. Briefing-Mail: Tabellenzellen, Risiko-Punkt, Handy-Tabelle
# ---------------------------------------------------------------------------

def _tds(html: str):
    soup = BeautifulSoup(html, "html.parser")
    zeilen = [tr for tr in soup.find_all("tr") if tr.find("td")]
    assert zeilen, "Vorbedingung: Tabelle hat Datenzeilen"
    return zeilen[0].find_all("td")


def _td_bg(td) -> str | None:
    style = td.get("style") or ""
    return style.split("background:", 1)[1].split(";", 1)[0] if "background:" in style else None


def _zelle(html: str, label_teil: str):
    for td in _tds(html):
        if label_teil.lower() in (td.get("data-label") or "").lower():
            return td
    raise AssertionError(f"keine Zelle {label_teil!r}")


def _ampel_cell_bg(level):
    from output.renderers.email.html import _ampel_cell_bg
    return _ampel_cell_bg(level)


@pytest.mark.parametrize("ampel,erwartet", [(SKI, "yellow"), (ALLG, "orange")],
                         ids=["skitouren", "allgemein"])
def test_briefing_tabelle_einfach_punkt_und_toenung_folgen_der_ampel(ampel, erwartet):
    """``_render_html_table`` (Einfach-Modus): Punkt (fmt_val) UND Zell-
    Tönung (ampel_level) der Böen-Zelle 52 km/h."""
    from output.renderers.email.html import _render_html_table
    html = _render_html_table([{"time": "08", "gust": 52.0}], friendly_keys=set(),
                              indicator_keys={"gust"}, ampel=ampel)
    td = _zelle(html, "Gust")
    assert _stundenzellen(str(td)) == [_dot_fill(erwartet)]
    assert _td_bg(td) == _ampel_cell_bg(erwartet)


@pytest.mark.parametrize("ampel,erwartet", [(SKI, "yellow"), (ALLG, "orange")],
                         ids=["skitouren", "allgemein"])
def test_briefing_tabelle_roh_toenung_folgt_der_ampel(ampel, erwartet):
    """``_render_html_table`` (Roh-Modus, Rückfall ``severity_for``)."""
    from output.renderers.email.html import _render_html_table
    html = _render_html_table([{"time": "08", "gust": 52.0}], friendly_keys=set(),
                              indicator_keys=set(), ampel=ampel)
    td = _zelle(html, "Gust")
    assert _stundenzellen(str(td)) == []
    assert _td_bg(td) == _ampel_cell_bg(erwartet)


@pytest.mark.parametrize("ampel,erwartet", [(SKI, "yellow"), (ALLG, "orange")],
                         ids=["skitouren", "allgemein"])
def test_briefing_tabelle_risikopunkt_folgt_der_ampel(ampel, erwartet):
    """Risiko-Punkt am Zeilenende (``_row_risk``): Böen 52 → gelb bzw. orange."""
    from output.renderers.email.html import _render_html_table
    html = _render_html_table([{"time": "08", "gust": 52.0}], friendly_keys=set(),
                              indicator_keys=set(), ampel=ampel)
    letzte = _tds(html)[-1]
    assert _dot_fill(erwartet) in str(letzte)
    andere = "orange" if erwartet == "yellow" else "yellow"
    assert _dot_fill(andere) not in str(letzte)


@pytest.mark.parametrize("ampel,erwartet", [(SKI, "yellow"), (ALLG, "orange")],
                         ids=["skitouren", "allgemein"])
def test_briefing_handy_tabelle_folgt_der_ampel(ampel, erwartet):
    """``_render_mobile_compact_rows`` reicht die Ampel an die Tabelle weiter."""
    from output.renderers.email.html import _render_mobile_compact_rows
    html = _render_mobile_compact_rows([{"time": "08", "gust": 52.0}], friendly_keys=set(),
                                       indicator_keys={"gust"}, ampel=ampel)
    td = _zelle(html, "Gust")
    assert _td_bg(td) == _ampel_cell_bg(erwartet)


# Je Zeile die einzige Metrik, die über die gewählte Vorlage entscheidet.
_ROW_RISK = [
    ("boeen", {"gust": 52.0}, SKI, "yellow", "watch"),
    ("wind", {"wind": 47.0}, SKI, "watch", "yellow"),
    ("regen", {"precip": 6.0}, SKI, "yellow", "watch"),
    ("regenw", {"pop": 55.0}, RAD, "watch", "yellow"),
    ("sicht", {"visibility": 800.0}, SKI, "yellow", "watch"),
    # Paar Regen+Temperatur: Regen 3 ist in beiden gelb, Temperatur 4 °C nur
    # bei Skitouren gelb -> Eskalation auf watch.
    ("temperatur", {"precip": 3.0, "temp": 4.0}, SKI, "watch", "yellow"),
    # Paar Sicht+Neuschnee: Sicht 800 bei Skitouren gelb, Neuschnee 25 bei
    # Skitouren gelb (Allgemein orange) -> Eskalation nur bei Skitouren-Neuschnee.
    ("neuschnee", {"visibility": 800.0, "fresh_snow": 25.0}, SKI, "watch", None),
]


@pytest.mark.parametrize("name,row,ampel,erwartet,allgemein", _ROW_RISK,
                         ids=[r[0] for r in _ROW_RISK])
def test_risiko_stufe_je_metrik_folgt_der_ampel(name, row, ampel, erwartet, allgemein):
    """``_row_risk``: jede der sieben Bewertungen liest die übergebene Ampel."""
    from output.renderers.email.html import _row_risk
    assert _row_risk(row, ampel=ampel) == erwartet
    if allgemein is not None:
        assert _row_risk(row, ampel=ALLG) == allgemein


# ---------------------------------------------------------------------------
# 4. Briefing-Mail: Ampel-Punkte (fmt_val) und Kacheln (Pillen)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key,wert,ampel,erwartet,allgemein", [
    ("gust", 52.0, SKI, "yellow", "orange"),
    ("wind", 47.0, SKI, "orange", "yellow"),
    ("precip", 6.0, SKI, "yellow", "orange"),
    ("pop", 55.0, RAD, "orange", "yellow"),
])
def test_ampel_punkt_folgt_der_ampel(key, wert, ampel, erwartet, allgemein):
    from output.renderers.email.helpers import fmt_val
    for a, e in ((ampel, erwartet), (ALLG, allgemein)):
        zelle = fmt_val(key, wert, html=True, indicator_keys={key}, ampel=a)
        assert _stundenzellen(zelle) == [_dot_fill(e)], (key, e)


def _dp(hour: int, **felder):
    from app.models import ForecastDataPoint
    return ForecastDataPoint(ts=datetime(2026, 7, 11, hour, 0, tzinfo=UTC), **felder)


@pytest.mark.parametrize("metric_id,felder,ampel,erwartet,allgemein", [
    ("temperature", {"t2m_c": 9.0}, SKI, "ampel_orange", "ampel_green"),
    ("uv_index", {"uv_index": 5.0}, WASSER, "ampel_green", "ampel_yellow"),
    ("gust", {"gust_kmh": 52.0}, SKI, "ampel_yellow", "ampel_orange"),
    ("wind", {"wind10m_kmh": 47.0}, SKI, "ampel_orange", "ampel_yellow"),
    ("precipitation", {"precip_1h_mm": 6.0}, SKI, "ampel_yellow", "ampel_orange"),
    ("rain_probability", {"pop_pct": 55}, RAD, "ampel_orange", "ampel_yellow"),
    ("visibility", {"visibility_m": 800}, SKI, "ampel_yellow", "ampel_orange"),
])
def test_kachel_toenung_folgt_der_ampel(metric_id, felder, ampel, erwartet, allgemein):
    """``_pill_for_metric``: Temperatur (``_extreme_ampel_tone``), UV,
    Wind/Böen, Regen, Regenwahrscheinlichkeit, Sicht."""
    from output.renderers.email.helpers import _pill_for_metric
    dps = [_dp(10, **felder), _dp(11, **felder)]
    assert _pill_for_metric(metric_id, {}, dps, tz=TZ, ampel=ampel)[1] == erwartet
    assert _pill_for_metric(metric_id, {}, dps, tz=TZ, ampel=ALLG)[1] == allgemein


def _briefing_segment():
    from app.models import GPXPoint, SegmentWeatherData, SegmentWeatherSummary, TripSegment
    from services.weather_snapshot import _deserialize_timeseries
    seg = TripSegment(
        segment_id="1",
        start_point=GPXPoint(lat=47.0, lon=11.0, elevation_m=1000, distance_from_start_km=0.0),
        end_point=GPXPoint(lat=47.05, lon=11.05, elevation_m=1500, distance_from_start_km=6.0),
        start_time=datetime(2026, 7, 11, 8, 0, tzinfo=UTC),
        end_time=datetime(2026, 7, 11, 12, 0, tzinfo=UTC),
        duration_hours=4.0, distance_km=6.0, ascent_m=500, descent_m=0,
    )
    rows = [{"ts": datetime(2026, 7, 11, h, 0, tzinfo=UTC).isoformat(),
             "t2m_c": 9.0, "wind10m_kmh": 10.0, "gust_kmh": 52.0} for h in (8, 9, 10, 11, 12)]
    ts = _deserialize_timeseries({"hourly": rows}, "openmeteo")
    assert ts is not None and len(ts.data) == len(rows)
    return SegmentWeatherData(
        segment=seg, timeseries=ts, aggregated=SegmentWeatherSummary(),
        fetched_at=datetime(2026, 7, 11, 6, 0, tzinfo=UTC), provider="openmeteo",
    )


@pytest.mark.parametrize("ampel,erwartet", [
    (SKI, ["ampel_orange", "ampel_yellow"]), (ALLG, ["ampel_green", "ampel_orange"]),
], ids=["skitouren", "allgemein"])
def test_kachelreihe_reicht_die_ampel_an_jede_kachel(ampel, erwartet):
    """``build_metrics_summary_pills`` -> ``_pill_for_metric``: Temperatur 9
    und Böen 52 aus echten Segmentdaten."""
    from output.renderers.email.helpers import build_metrics_summary_pills
    pills = build_metrics_summary_pills(
        [_briefing_segment()], ["temperature", "gust"], {}, tz=TZ, ampel=ampel)
    assert [tone for _t, tone in pills] == erwartet


# ---------------------------------------------------------------------------
# 5. 3-Tages-Ausblick (geteilt Trip/Vergleich)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("feld,wert,ampel,erwartet,allgemein", [
    ("wind_kmh", 47.0, SKI, "orange", "yellow"),
    ("precip_mm", 6.0, SKI, "yellow", "orange"),
])
def test_ausblick_tabelle_feste_spalten_folgen_der_ampel(feld, wert, ampel, erwartet, allgemein):
    """``render_outlook_table`` (fester Zweig, ``_catalog_thresholds``)."""
    from output.renderers.email.outlook import render_outlook_table
    for a, e in ((ampel, erwartet), (ALLG, allgemein)):
        html = render_outlook_table([{"weekday": "Mo", feld: wert}], ampel=a)
        assert f"background:{_tone_bg(e)};" in html, (feld, e)


def test_ausblick_tabelle_boeen_folgen_der_ampel():
    from output.renderers.email.outlook import render_outlook_table
    from output.tokens.dto import HourlyValue
    row = {"weekday": "Mo", "hourly_gust": (HourlyValue(hour=13, value=52.0),)}
    assert f"background:{_tone_bg('yellow')};" in render_outlook_table([row], ampel=SKI)
    assert f"background:{_tone_bg('orange')};" in render_outlook_table([row], ampel=ALLG)


# ---------------------------------------------------------------------------
# 6. Vergleichs-Mail: Übersicht, Stundentabelle, Ort-Abschnitt, Ausblick
# ---------------------------------------------------------------------------

def _ort(*, stunden_temp=9.0, ausblick=False):
    from datetime import date, timedelta

    from app.models import ForecastDataPoint, ThunderLevel
    from app.user import LocationResult, SavedLocation

    def tag(d, temp, wind):
        return [ForecastDataPoint(
            ts=datetime(d.year, d.month, d.day, h, 0, tzinfo=UTC),
            t2m_c=temp, wind10m_kmh=wind, gust_kmh=15.0, precip_1h_mm=0.0, pop_pct=10,
            cloud_total_pct=30, thunder_level=ThunderLevel.NONE, visibility_m=20000,
        ) for h in (9, 10, 11, 12, 13, 14)]

    heute = date(2026, 7, 11)  # fest: Kern-Schicht ohne „jetzt"
    return LocationResult(
        location=SavedLocation(id="alpe", name="Alpe", lat=47.27, lon=11.39,
                               elevation_m=574, timezone="UTC"),
        temp_max=stunden_temp,
        hourly_data=tag(heute, stunden_temp, 10.0),
        outlook_hourly_data=tag(heute + timedelta(days=1), 10.0, 47.0) if ausblick else [],
    )


@pytest.mark.parametrize("ampel,getoent", [(SKI, True), (ALLG, False)],
                         ids=["skitouren", "allgemein"])
def test_vergleich_stundentabelle_folgt_der_ampel(ampel, getoent):
    """``_render_hour_table`` und ``_render_location_section``: +9 °C ist
    bei Skitouren orange getönt, bei Allgemein ungetönt (AC-20, Kette)."""
    from output.renderers.email.compare_html import (
        _render_hour_table, _render_location_section,
    )
    orange = f"background:{_tone_bg('orange')};"
    for html in (_render_hour_table(_ort(), ["t2m_c"], ampel=ampel),
                 _render_location_section(_ort(), 0, ["t2m_c"], ampel=ampel)):
        assert (orange in html) is getoent


@pytest.mark.parametrize("ampel,getoent", [(SKI, True), (ALLG, False)],
                         ids=["skitouren", "allgemein"])
def test_vergleich_uebersicht_folgt_der_ampel(ampel, getoent):
    """``_render_overview_table`` -> ``_visible_metrics``: Tageshoch +9 °C."""
    from output.renderers.email.compare_html import _render_overview_table, _visible_metrics
    zeile = next(m for m in _visible_metrics(["temp_max"], ampel=ampel) if m["key"] == "temp_max")
    assert zeile["sev"](9.0) == ("warn" if getoent else "ok")
    html = _render_overview_table([_ort()], ["temp_max"], ampel=ampel)
    assert (f"background:{_tone_bg('orange')};" in html) is getoent


def test_vergleich_uebersicht_ohne_auswahl_folgt_der_ampel():
    from output.renderers.email.compare_html import _visible_metrics
    zeile = next(m for m in _visible_metrics(None, ampel=SKI) if m["key"] == "temp_max")
    assert zeile["sev"](9.0) == "warn"


@pytest.mark.parametrize("ampel,erwartet", [(SKI, "orange"), (ALLG, "yellow")],
                         ids=["skitouren", "allgemein"])
def test_vergleich_ausblick_folgt_der_ampel(ampel, erwartet):
    """``_render_location_outlook`` -> ``render_outlook_table``: Wind 47 km/h."""
    from output.renderers.email.compare_html import _render_location_outlook
    html = _render_location_outlook(_ort(ausblick=True), 0, ampel=ampel)
    assert f"background:{_tone_bg(erwartet)};" in html
    andere = "yellow" if erwartet == "orange" else "orange"
    assert f"background:{_tone_bg(andere)};" not in html


@pytest.mark.parametrize("ampel,erwartet", [(SKI, "orange"), (ALLG, "yellow")],
                         ids=["skitouren", "allgemein"])
def test_vergleich_ausblick_mit_metrikauswahl_folgt_der_ampel(ampel, erwartet):
    """Konfigurierte Ausblick-Metriken: die Zell-Hintergründe entstehen im
    Zeilenbau (``_build_location_outlook_rows`` -> ``_outlook_row``), nicht
    im festen Zweig von ``render_outlook_table``. Wind 47 km/h: Skitouren
    orange, Allgemein gelb (Adversary-Nachbefund, AC-20 Kette)."""
    from output.renderers.email.compare_html import _render_location_outlook
    html = _render_location_outlook(_ort(ausblick=True), 0, ["wind"], ampel=ampel)
    assert f"background:{_tone_bg(erwartet)};" in html
    andere = "yellow" if erwartet == "orange" else "orange"
    assert f"background:{_tone_bg(andere)};" not in html


def test_vergleich_ausblick_mit_metrikauswahl_unterscheidet_die_ampeln():
    from output.renderers.email.compare_html import _render_location_outlook
    ski = _render_location_outlook(_ort(ausblick=True), 0, ["wind"], ampel=SKI)
    allg = _render_location_outlook(_ort(ausblick=True), 0, ["wind"], ampel=ALLG)
    assert ski != allg


# Fix-Loop 2 (Adversary Iteration 2, F001): jede Übersichtszeile mit eigener
# ``_sev_*``-Funktion. Werte vorab aus den Vorlagen nachgerechnet:
#   wind_max 47       Skitouren orange (45) / Allgemein gelb (30, orange 50)
#   gust_max 52       Skitouren gelb (40, orange 55) / Allgemein orange (45)
#   precip_sum 6      Skitouren gelb (2, orange 10) / Allgemein orange (5)
#   uv_max 5          Wassersport grün (gelb 6) / Allgemein gelb (3)
#   pop_max 55        Radtour orange (50) / Allgemein gelb (30, orange 60)
#   visibility_min 800 Skitouren gelb (<1000) / Allgemein orange (<1000; gelb <2000)
#   temp_min -10      Skitouren grün (gelb unter -15) / Allgemein orange (unter -5)
_UEBERSICHT = [
    ("wind_max", {"wind_max": 47.0}, SKI, "orange", "yellow"),
    ("gust_max", {"gust_max": 52.0}, SKI, "yellow", "orange"),
    ("precip_sum", {"precip_sum_mm": 6.0}, SKI, "yellow", "orange"),
    ("uv_max", {"uv_index_max": 5.0}, WASSER, "green", "yellow"),
    ("pop_max", {"pop_max_pct": 55}, RAD, "orange", "yellow"),
    ("visibility_min", {"visibility_min_m": 800}, SKI, "yellow", "orange"),
    ("temp_min", {"temp_min": -10.0}, SKI, "green", "orange"),
]


def _uebersicht_zelle_bg(key, felder, ampel):
    import dataclasses as dc

    from output.renderers.email.compare_html import _render_overview_table
    ort = dc.replace(_ort(), **felder)
    html = _render_overview_table([ort], [key], ampel=ampel)
    zeilen = BeautifulSoup(html, "html.parser").find("tbody").find_all("tr")
    assert len(zeilen) == 2, "Vorbedingung: Warn-Zeile + genau die gewählte Zeile"
    style = zeilen[1].find_all("td")[1].get("style")
    return style.split("background:", 1)[1].split(";", 1)[0]


def _bg_erwartet(level):
    return "transparent" if level == "green" else _tone_bg(level)


@pytest.mark.parametrize("key,felder,ampel,erwartet,allgemein", _UEBERSICHT,
                         ids=[u[0] for u in _UEBERSICHT])
def test_vergleich_uebersicht_jede_zeile_folgt_der_ampel(key, felder, ampel, erwartet, allgemein):
    """Compare-Übersicht: die Zellfarbe jeder ``_sev_*``-Zeile kommt aus der
    übergebenen Ampel (gemessen im HTML der Zelle)."""
    assert _uebersicht_zelle_bg(key, felder, ampel) == _bg_erwartet(erwartet)
    assert _uebersicht_zelle_bg(key, felder, ALLG) == _bg_erwartet(allgemein)


@pytest.mark.parametrize("ampel,erwartet", [(SKI, "yellow"), (ALLG, "orange")],
                         ids=["skitouren", "allgemein"])
def test_vergleich_stundentabelle_regen_folgt_der_ampel(ampel, erwartet):
    """Stundenspalte Regen (``_sev_rain_safe``): 6 mm/h Skitouren gelb,
    Allgemein orange."""
    import dataclasses as dc

    from output.renderers.email.compare_html import _render_hour_table
    ort = _ort()
    ort = dc.replace(ort, hourly_data=[dc.replace(p, precip_1h_mm=6.0) for p in ort.hourly_data])
    html = _render_hour_table(ort, ["precip_1h_mm"], ampel=ampel)
    assert f"background:{_tone_bg(erwartet)};" in html
    andere = "orange" if erwartet == "yellow" else "yellow"
    assert f"background:{_tone_bg(andere)};" not in html


# F003a / F004: Ausblick-Zeilenbau mit Metrik-Auswahl (Spannen- und Einzelspalte)
def _tageswerte():
    from app.models import SegmentWeatherSummary
    return SegmentWeatherSummary(temp_min_c=2.0, temp_max_c=9.0, gust_max_kmh=52.0)


@pytest.mark.parametrize("metrik,ampel,erwartet", [
    ("temperature", SKI, "orange"), ("temperature", ALLG, "green"),
    ("gust", SKI, "yellow"), ("gust", ALLG, "orange"),
])
def test_ausblick_zeilenbau_spannen_und_einzelspalte_folgen_der_ampel(metrik, ampel, erwartet):
    """``_outlook_row``: Spannen-Spalte Temperatur (Tageshoch +9 °C) und
    Einzelspalte Böen 52 km/h tragen den Hintergrund der übergebenen Ampel."""
    from output.renderers.email.outlook import _outlook_row
    row = _outlook_row(_tageswerte(), [], "Mo", UTC, metrics=[metrik], ampel=ampel, context="vergleich")
    bg = "" if erwartet == "green" else f"background:{_tone_bg(erwartet)};"
    assert row["cell_bg"] == [bg]


def test_ausblick_einstieg_verlangt_die_ampel_des_abos():
    """S1c-4b (umgekehrt aus dem S1c-1-Übergangstest): ``build_outlook_row``
    löst nicht mehr selbst „allgemein" auf, sondern verlangt ``ampel=`` ohne
    Default — ein Aufruf ohne Ampel scheitert laut (AC-27)."""
    from output.renderers.email.outlook import build_outlook_row
    with pytest.raises(TypeError):
        build_outlook_row(_tageswerte(), [], "Mo", UTC, metrics=["temperature"], context="vergleich")


@pytest.mark.parametrize("metrik,ampel,erwartet", [
    ("temperature", SKI, "orange"), ("temperature", ALLG, "green"),
    ("gust", SKI, "yellow"), ("gust", ALLG, "orange"),
])
def test_ausblick_einstieg_faerbt_nach_der_uebergebenen_abo_ampel(metrik, ampel, erwartet):
    """S1c-4b: der Einstieg färbt nach der übergebenen Abo-Ampel — +9 °C bei
    Skitouren orange, bei Allgemein ohne Farbe; Böen 52 km/h Skitouren gelb,
    Allgemein orange (AC-25)."""
    from output.renderers.email.outlook import build_outlook_row
    row = build_outlook_row(_tageswerte(), [], "Mo", UTC, metrics=[metrik], context="vergleich", ampel=ampel)
    bg = "" if erwartet == "green" else f"background:{_tone_bg(erwartet)};"
    assert row["cell_bg"] == [bg]


# F003b: Kappung auf MAX_ROWS — welche Stunden die stärksten sind, hängt an der
# Stufenstärke (``_strength``) und damit an der Ampel.
#   S (10 -> 60): Stufenwechsel in beiden Ampeln, großer Abstand (stark)
#   C (28 -> 31): Allgemein grün->gelb (Stufe 1), Skitouren grün->grün (0)
#   D (38 -> 41): Allgemein gelb->gelb (0), Skitouren grün->gelb (1)
#   E (10 -> 12): nirgends Stufenwechsel (schwächste)
_KAPPUNG = [(6, 10.0, 60.0), (7, 10.0, 60.0), (8, 28.0, 31.0), (9, 38.0, 41.0),
            (10, 10.0, 12.0), (11, 10.0, 60.0), (12, 10.0, 60.0), (13, 10.0, 60.0)]


@pytest.mark.parametrize("name,ampel,erwartet", [
    ("skitouren", SKI, ["08:00", "09:00", "11:00", "13:00", "14:00", "15:00"]),
    ("allgemein", ALLG, ["08:00", "09:00", "10:00", "13:00", "14:00", "15:00"]),
])
def test_alarm_kappung_waehlt_staerkste_stunden_nach_ampel(name, ampel, erwartet):
    from output.renderers.alert.hours import MAX_ROWS
    from output.renderers.alert.project import to_multi_point_alert_message
    frisch = _punkt("Alpe", [(h, neu) for h, _alt, neu in _KAPPUNG])
    anker = _punkt("Alpe", [(h, alt) for h, alt, _neu in _KAPPUNG])
    msg = to_multi_point_alert_message(
        [("Alpe", [_aenderung()], frisch)], tz=TZ, stand_at="06:00",
        anchor_points={"Alpe": anker}, ampel=ampel)
    ev = msg.events[0]
    assert len(_KAPPUNG) > MAX_ROWS and ev.hours_capped
    assert [h.time for h in ev.hours] == erwartet


# ---------------------------------------------------------------------------
# 7. Kein stiller Fallback (F002)
# ---------------------------------------------------------------------------

def _ampel_parameter_in_src_output():
    for py in sorted(_OUTPUT_SIG.rglob("*.py")):
        baum = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        for node in ast.walk(baum):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                continue
            a = node.args
            ort = f"{py.relative_to(_OUTPUT_SIG).as_posix()}:{getattr(node, 'name', 'lambda')}"
            if any(p.arg == "ampel" for p in a.posonlyargs + a.args):
                yield ort, "positional"
            if a.vararg and a.vararg.arg == "ampel" or a.kwarg and a.kwarg.arg == "ampel":
                yield ort, "*args/**kwargs"
            for p, default in zip(a.kwonlyargs, a.kw_defaults):
                if p.arg == "ampel":
                    yield ort, "ok" if default is None else "mit Default"


_OUTPUT_SIG = Path(__file__).resolve().parents[2] / "src" / "output"


def test_jeder_ampel_parameter_in_src_output_ist_pflicht_und_keyword_only():
    """F002: statt einer Liste ein Scan — jede Funktion in src/output mit
    einem Parameter ``ampel`` hat ihn keyword-only und ohne Default."""
    funde = list(_ampel_parameter_in_src_output())
    assert len([f for f in funde if f[1] == "ok"]) > 40, "Selbsttest: Scan sieht die Kette"
    assert [f for f in funde if f[1] != "ok"] == []

def test_alarm_nachricht_ampel_ist_pflichtfeld_ohne_default():
    from output.renderers.alert.model import AlertMessage
    feld = {f.name: f for f in dataclasses.fields(AlertMessage)}["ampel"]
    assert feld.default is dataclasses.MISSING
    assert feld.default_factory is dataclasses.MISSING
    assert feld.kw_only is True
    with pytest.raises(TypeError):
        AlertMessage(trip_short="x", stand_at="06:00", events=())  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# 8. Spitzenwert-Gleichstand und CAPE-Brücke (F003)
# ---------------------------------------------------------------------------

def _schaerfe(ampel, metric_id, v):
    """Fix-Loop 2 (F003): ``ampel_schaerfe`` ist neben ``ampel_stufe`` Pflicht
    (Klammer = schlimmster Wert je Seite); mechanisch ergaenzt."""
    from app.ampel import ampel_schaerfe
    return ampel_schaerfe(ampel, metric_id, v)


def test_spitzenwert_bei_gleicher_stufe_zeigt_das_maximum():
    """31 @12 und 35 @15 sind bei Allgemein-Wind beide gelb. Issue #2792
    S1c-4b Fix-Loop 1 (F008, Koordinator-Entscheid) -- umgekehrt: die Klammer
    zeigt weiter den Hoechstwert mit Stunde (bisherige Token-Semantik, kein
    Informationsverlust) ⇒ „31@12(35@15)"; frueher (S1c-4a) „31@12"."""
    from output.metric_format import severity_for
    from output.tokens.dto import HourlyValue
    from output.tokens.metrics import render_threshold_peak_value
    samples = (HourlyValue(hour=12, value=31.0), HourlyValue(hour=15, value=35.0))
    assert render_threshold_peak_value(
        "W", samples, None,
        ampel_stufe=lambda v: severity_for("wind", v, ampel=ALLG),
        ampel_schaerfe=lambda v: _schaerfe(ALLG, "wind", v)) == "31@12(35@15)"


def test_spitzenwert_rot_schlaegt_orange_und_reihenfolge_egal():
    """F006: unsortierte Stunden, Wind 70 (rot) @16, 31 (gelb) @10, 50
    (orange) @13 — erste Stunde ab Gelb ist 10, Spitze die rote 70 @16."""
    from output.metric_format import severity_for
    from output.tokens.dto import HourlyValue
    from output.tokens.metrics import render_threshold_peak_value
    samples = (HourlyValue(hour=16, value=70.0), HourlyValue(hour=10, value=31.0),
               HourlyValue(hour=13, value=50.0))
    assert render_threshold_peak_value(
        "W", samples, None,
        ampel_stufe=lambda v: severity_for("wind", v, ampel=ALLG),
        ampel_schaerfe=lambda v: _schaerfe(ALLG, "wind", v)) == "31@10(70@16)"


def test_spitzenwert_ampelstufe_hat_vorrang_vor_gespeicherter_schwelle():
    """Fix-Loop 3 F002: mit ``ampel_stufe`` UND ``threshold=30`` entscheidet
    die Ampel (AC-7: die alte ``sms_threshold`` wird nicht mehr gelesen).
    Wassersport-Wind 3 km/h @14 ist orange ⇒ „3@14"; die Schwellen-Logik
    sähe nur die 15 unter 30 ⇒ „-"."""
    from output.metric_format import severity_for
    from output.tokens.dto import HourlyValue
    from output.tokens.metrics import render_threshold_peak_value
    samples = (HourlyValue(hour=10, value=15.0), HourlyValue(hour=14, value=3.0),
               HourlyValue(hour=16, value=12.0))
    assert render_threshold_peak_value("W", samples, 30.0) == "-"
    assert render_threshold_peak_value(
        "W", samples, 30.0,
        ampel_stufe=lambda v: severity_for("wind", v, ampel=WASSER),
        ampel_schaerfe=lambda v: _schaerfe(WASSER, "wind", v)) == "3@14"


def test_cape_traegt_keine_eigene_farbe():
    """S1c-4b, AC-6/P1 (umgekehrt aus dem S1c-1-Übergangstest): die
    CAPE-Brücke ist entfernt, CAPE hat keinen Ampel-Leser mehr."""
    from app.ampel import hat_ampel
    assert hat_ampel("cape") is False
    assert hat_ampel("gust") is True
    assert hat_ampel("dewpoint") is False


# ---------------------------------------------------------------------------
# 9. Ratsche: resolve_ampel( nur an den Einstiegen, je genau einmal
# ---------------------------------------------------------------------------

_SRC = Path(__file__).resolve().parents[2] / "src"
_OUTPUT = _SRC / "output"
_SERVICES = _SRC / "services"

# (Datei relativ zu src/output, Funktion) -> Anzahl Auflöser-Treffer.
# Darf nur schrumpfen bzw. in S1c-4 auf das Abo umgestellt werden.
EINSTIEGE = {
    ("renderers/email/html.py", "render_html"): 1,
    ("renderers/email/plain.py", "render_plain"): 1,
    ("renderers/email/compact.py", "render_compact"): 1,
    ("renderers/email/compare_html.py", "render_compare_html"): 1,
    ("renderers/comparison.py", "render_comparison_text"): 1,
    ("renderers/narrow.py", "render_telegram_bubbles"): 1,
    # S1c-4b (Spec v1.5 Punkt 4): die SMS bekommt die Ampel aus derselben dc
    # wie die Mail; aufgeloest im Formatter, der format_sms ruft.
    ("renderers/trip_report.py", "format_email"): 1,
}

# S1c-4b: ``build_outlook_row`` löst nicht mehr selbst auf (er war Einstieg in
# S1c-1), sondern nimmt die Ampel als keyword-only Pflichtparameter ohne
# Default; aufgelöst wird beim Aufrufer im Scheduler (DIENST_EINSTIEGE).
# Darf nur wachsen.
AMPEL_PFLICHT_OHNE_DEFAULT = {
    ("renderers/email/outlook.py", "build_outlook_row"),
}

# Alles aus src/app/ampel.py, womit sich eine Ampel bzw. Vorlage beschaffen
# lässt (Adversary F005): jede Nennung (Aufruf, Referenz, getattr-String,
# Alias-Import) zählt, nicht nur ``resolve_ampel``.
_AUFLOESER = {
    "resolve_ampel", "ampel_for", "_verschmelzen", "_aufloesen", "template_id_for",
    "template_for_profil", "_bekannte_vorlage", "_vorlage_der_ampel", "_abo_ampel",
    "AMPEL_TEMPLATES", "DEFAULT_TEMPLATE", "ampel_templates",
}


def _aufrufe_je_funktion(wurzel: Path = _OUTPUT) -> dict:
    gefunden: dict = {}

    def zaehle(rel, funktion):
        schluessel = (rel, funktion or "<modul>")
        gefunden[schluessel] = gefunden.get(schluessel, 0) + 1

    def besuche(node, rel, funktion):
        for kind in ast.iter_child_nodes(node):
            if isinstance(kind, (ast.FunctionDef, ast.AsyncFunctionDef)):
                besuche(kind, rel, kind.name)
                continue
            name = (kind.id if isinstance(kind, ast.Name)
                    else kind.attr if isinstance(kind, ast.Attribute)
                    else kind.value if isinstance(kind, ast.Constant)
                    and isinstance(kind.value, str) else None)
            if name in _AUFLOESER:
                zaehle(rel, funktion)
            if isinstance(kind, (ast.ImportFrom, ast.Import)):
                modul = getattr(kind, "module", None) or ""
                if modul.endswith("ampel_templates"):
                    zaehle(rel, f"<import {modul}>")
                for alias in kind.names:
                    if alias.name.endswith("ampel_templates"):
                        zaehle(rel, f"<import {alias.name}>")
                    if alias.name in _AUFLOESER and alias.asname:
                        zaehle(rel, f"<alias {alias.asname}>")
            besuche(kind, rel, funktion)

    for py in sorted(wurzel.rglob("*.py")):
        rel = py.relative_to(wurzel).as_posix()
        besuche(ast.parse(py.read_text(encoding="utf-8"), filename=str(py)), rel, None)
    return gefunden


# Dienste, die eine Alarm-/Vorschau-Nachricht bauen, sind legitime Einstiege
# (AlertMessage braucht die Ampel). Explizite Liste, darf nur schrumpfen.
DIENST_EINSTIEGE = {
    ("compare_alert_preview_service.py", "_deviation"): 1,
    ("compare_alert_preview_service.py", "_onset"): 1,
    ("notification_service.py", "send_deviation_alert"): 1,
    ("notification_service.py", "send_multi_location_deviation_alert"): 1,
    ("notification_service.py", "send_multi_location_radar_alert"): 1,
    ("notification_service.py", "send_radar_alert"): 1,
    ("radar_alert_service.py", "build_onset_alert_message"): 1,
    ("validator_render_service.py", "_deviation_preview_message"): 1,
    ("validator_render_service.py", "render_alert_preview"): 1,
    # S1c-4b: der Ausblick wird je stage_trip mit dessen Ampel gebaut.
    ("trip_report_scheduler.py", "_build_stage_trend"): 1,
    # S1c-4b (Spec v1.4 Punkt 7): die Telegram-Drilldowns loesen die Trip-
    # Ampel fuer das Gewitter-Emoji (thunder_color) auf.
    ("trip_command_processor.py", "_handle_drilldown"): 1,
    ("trip_command_processor.py", "_handle_hours_drilldown"): 1,
    ("trip_command_processor.py", "_handle_metric_drilldown"): 1,
    # S1c-4b (Koordinator-Freigabe): zustandslose SMS-Editor-Vorschau, Body nur
    # metric_ids, kein Trip/keine dc -- bewusst Vorlage „allgemein".
    ("validator_render_service.py", "render_sms_fidelity_preview"): 1,
    # #2793 S2b (Spec §2): die Alarm-Ausloesung liest die Abo-Ampel -- die
    # beiden Adapter der geteilten DeviationAlertEngine loesen sie je Abo auf
    # und reichen sie per AlertEvaluationConfig.ampel durch (Engine selbst loest
    # nicht auf, fehlt sie, scheitert sie laut).
    ("trip_alert.py", "check_and_send_alerts"): 1,
    ("compare_alert.py", "_build_eval_config"): 1,
    # #2794 Teil 3 (AC-29): das Alarmquellen-Gate loest die Abo-Ampel des Trips
    # auf (nur bei gesetztem display_config.ampel), um alarm_ab zu erkennen.
    ("trip_alert.py", "ampel_alarmquelle_aktiv"): 1,
}


def _funktion(datei: Path, name: str):
    for node in ast.walk(ast.parse(datei.read_text(encoding="utf-8"), filename=str(datei))):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError(f"{datei}:{name} nicht gefunden")


@pytest.mark.parametrize("rel,name", sorted(AMPEL_PFLICHT_OHNE_DEFAULT))
def test_ausblick_nimmt_die_ampel_als_pflichtparameter_ohne_default(rel, name):
    """S1c-4b, AC-27: wer nicht mehr selbst auflöst, verlangt die Ampel —
    keyword-only, ohne Default (kein stilles „allgemein")."""
    a = _funktion(_OUTPUT / rel, name).args
    kw = {p.arg: d for p, d in zip(a.kwonlyargs, a.kw_defaults)}
    assert "ampel" in kw, f"{rel}:{name} hat keinen keyword-only Parameter ampel"
    assert kw["ampel"] is None, f"{rel}:{name}: ampel hat einen Default"


def test_ausblick_ist_kein_aufloeser_mehr():
    """S1c-4b: im Ausblick-Einstieg steht kein Auflöser mehr (sonst würde er
    die übergebene Ampel still überschreiben)."""
    for schluessel in AMPEL_PFLICHT_OHNE_DEFAULT:
        assert schluessel not in _aufrufe_je_funktion()


def test_ratsche_scan_sieht_die_einstiege():
    """Selbsttest: der Scan findet die bekannten Einstiege überhaupt."""
    assert ("renderers/email/html.py", "render_html") in _aufrufe_je_funktion()
    assert _aufrufe_je_funktion(_SERVICES), "Scan über src/services leer"


def test_dienste_loesen_die_ampel_nur_an_den_benannten_stellen_auf():
    assert _aufrufe_je_funktion(_SERVICES) == DIENST_EINSTIEGE


def test_ampel_wird_nur_an_den_einstiegen_aufgeloest():
    """Jede Zwischenstelle bekommt die Ampel durchgereicht; ein
    ``resolve_ampel(``/``ampel_for(`` außerhalb der Einstiege (oder ein
    zweiter Aufruf in einem Einstieg) setzt eine Zwischenstelle still auf
    „allgemein" — auch dort, wo die Text-Kanäle es nicht sichtbar machen."""
    assert _aufrufe_je_funktion() == EINSTIEGE


def _aufloesungen(wurzel: Path) -> list:
    """Jeder ``resolve_ampel(...)``-Aufruf unter ``wurzel`` mit seiner Form."""
    funde = []
    for py in sorted(wurzel.rglob("*.py")):
        rel = py.relative_to(wurzel).as_posix()
        for node in ast.walk(ast.parse(py.read_text(encoding="utf-8"), filename=str(py))):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            name = fn.id if isinstance(fn, ast.Name) else fn.attr if isinstance(fn, ast.Attribute) else None
            if name != "resolve_ampel":
                continue
            literal_none = (len(node.args) == 1 and not node.keywords
                            and isinstance(node.args[0], ast.Constant)
                            and node.args[0].value is None)
            funde.append((rel, node.lineno, literal_none))
    return funde


@pytest.mark.parametrize("wurzel,anzahl", [(_OUTPUT, len(EINSTIEGE)), (_SERVICES, len(DIENST_EINSTIEGE))],
                         ids=["src_output", "src_services"])
def test_kein_einstieg_loest_still_none_auf(wurzel, anzahl):
    """S1c-4b, AC-25 (umgekehrt aus dem S1c-1-Übergangstest
    ``…loest_in_s1c1_genau_allgemein_auf``): jeder Einstieg (Renderer UND
    Dienste) ruft ``resolve_ampel`` genau einmal auf und übergibt das ABO
    seines Kontexts (Trip, ``display_config``, Compare-Preset) — nie das
    Literal ``None``. Ein Einstieg, der still „allgemein" auflöst, verlöre
    bei Skitouren- und Wassersport-Abos die Bewertung."""
    funde = _aufloesungen(wurzel)
    assert len(funde) == anzahl
    assert [f for f in funde if f[2]] == []


# ---------------------------------------------------------------------------
# 10. Dienst-Einstiege: die gebaute Alarm-Nachricht trägt „allgemein" (S1c-1)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("display_config,erwartet,andere", [
    ({"preset_name": "skitouren"}, SKI, ALLG),
    (None, ALLG, SKI),
], ids=["skitouren", "ohne_vorlage"])
def test_radar_alarm_nachricht_traegt_die_ampel_des_trips(display_config, erwartet, andere):
    """S1c-4b (umgekehrt aus ``…traegt_in_s1c1_die_allgemein_ampel``):
    ``build_onset_alert_message`` (Radar-Alarm, Trip) trägt die Ampel des
    Trips — Skitouren-Trip ⇒ Skitouren, Trip ohne Vorlage ⇒ „allgemein"."""
    from types import SimpleNamespace

    from services.radar_alert_service import build_onset_alert_message
    trip = SimpleNamespace(name="GR20", alert_cooldown_minutes=120, display_config=display_config)
    active = SimpleNamespace(start_point=SimpleNamespace(lat=42.2, lon=9.0), distance_km=8.0)
    msg = build_onset_alert_message(trip, active, 25, "06:25", "Leichter Regen", "Radar (DWD)")
    assert msg.ampel == erwartet
    assert msg.ampel != andere


@pytest.mark.parametrize("preset_name,gelb_erwartet", [("skitouren", False), (None, True)],
                         ids=["skitouren", "allgemein"])
def test_trip_abweichungsalarm_faerbt_ueber_den_versandweg_nach_der_trip_ampel(
        monkeypatch, preset_name, gelb_erwartet):
    """``NotificationService.send_deviation_alert`` (Trip-Alarm-Pfad) über den
    echten Versandweg (Transport-Mitschrift, keine Sockets): Böen 31 km/h um
    12 Uhr UTC sind bei Allgemein gelb, bei Skitouren grün (gelb ab 40).
    S1c-4b (umgekehrt aus ``…versandweg_nach_allgemein``): der Dienst-Einstieg
    löst die Ampel des Trips auf — der Skitouren-Trip trägt keinen gelben
    Punkt, der Trip ohne Vorlage den gelben „allgemein"-Punkt."""
    from app.models import MetricConfig, UnifiedWeatherDisplayConfig
    from app.trip import Stage, Trip, Waypoint
    from services.notification_service import NotificationService
    from tests.helpers.sms_empfaenger import mit_profil_kanaele
    from tests.helpers.transport_mitschrift import aufzeichner_installieren
    from tests.tdd.test_alert_hour_rows import _load, _segment_data, _settings, _user, _wc

    fx = _load("boeen_stufe_statt_schwelle.json")
    mit = aufzeichner_installieren(monkeypatch)
    settings = _settings()
    uid = mit_profil_kanaele(_user("ampel"), settings)
    tid = "trip-2792-ampel"
    trip = Trip(
        id=tid, name="Ampel-Trip", official_warnings=None, corridors=[],
        stages=[Stage(id="T1", name="Tag 1", date=datetime(2026, 5, 1).date(),
                      waypoints=[Waypoint(id="G1", name="Start", lat=47.0, lon=11.0,
                                          elevation_m=1000.0)])],
        display_config=UnifiedWeatherDisplayConfig(
            trip_id=tid, preset_name=preset_name,
            metrics=[MetricConfig(metric_id="gust", enabled=True)],
            per_channel_layouts={"email": [
                MetricConfig(metric_id="gust", enabled=True, format_mode="simplified")]},
        ),
    )
    NotificationService(settings, uid).send_deviation_alert(
        trip=trip, weather=[_segment_data(fx, fx["fresh"])], changes=[_wc(fx["change"])],
        effective_channels={"email"}, anchor_weather=[_segment_data(fx, fx["anchor"])],
    )
    mails = mit.sendungen("email")
    assert len(mails) == 1, f"Vorbedingung: eine Mail ({mit!r})"
    punkte = _stundenzellen(mails[0]["body"])
    assert punkte, "Vorbedingung: Stundenzeilen mit Ampel-Punkten"
    assert (_dot_fill("yellow") in punkte) is gelb_erwartet
