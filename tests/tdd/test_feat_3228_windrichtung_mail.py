"""Windrichtung in der Briefing-Mail faerben, Scheibe S2 von Epic #3222 (Issue #3228).

Spec: docs/specs/modules/feat_3228_windrichtung_mail.md (AC-1..AC-4, AC-6,
AC-7, AC-9..AC-11; AC-5/AC-8 Ortsvergleich in ``..._compare.py``).
Kontext: docs/context/feat-3228-windrichtung-mail.md (Analysis).

Kein Mock: echte ``TripReportFormatter().format_email``-Aufrufe mit echten
``SegmentWeatherData``/``ForecastDataPoint``-Objekten, echte Vorlage
``radtour`` (Windstaerke 20/30/45, Gegenwind 10/20/30 km/h), deterministisch,
ohne Netz.

WO WIRKT ES (Messstelle): in der Desktop-Stundentabelle der Etappe
(``<table data-table="resp">`` nach ``>SEG {n}</span>``):

* Zelltoenung = ``background:<tone_css(level)[0]>`` im oeffnenden ``<td>``
  der Wind-Zelle (``data-label="Wind"``) bzw. der eigenen WDir-Spalte
  (``data-label="WDir"``, Roh-Modus). Ungefaerbt = kein ``background:``.
* Ampelpunkt in der Wind-Zelle = ``border-radius:50%;background:<_AMPEL_DOT_COLORS[level][0]>``
  (``fmt_val``).
* Zeilenpunkt = Punkt in der letzten Zelle der Zeile (``_row_risk``).

Konvention: ``wind_direction_deg`` = Richtung, AUS der der Wind kommt
(0 = N); Etappe "nach Norden" = start_point suedlich von end_point (> 300 m).
"""
from __future__ import annotations

import copy
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app.ampel import hat_ampel, resolve_ampel
from app.metric_catalog import build_default_display_config
from app.models import (
    ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries, Provider,
    SegmentWeatherData, SegmentWeatherSummary, ThunderLevel, TripSegment,
)
from output.renderers.email.design_tokens import tone_css
from output.renderers.email.helpers import _AMPEL_DOT_COLORS
from output.renderers.trip_report import TripReportFormatter

_HERE = Path(__file__).resolve().parent
_UTC = ZoneInfo("UTC")

# Ampel-Stufe <- Hex (aus den Quellen abgeleitet, keine Hex-Kopien).
_BG_TO_LEVEL = {tone_css(lvl)[0].lower(): lvl for lvl in ("yellow", "orange", "red")}
_DOT_TO_LEVEL = {fill.lower(): lvl for lvl, (fill, _ring) in _AMPEL_DOT_COLORS.items()}

# Geometrie (Luftlinie): Nordkurs ~5,5 km, Suedkurs umgekehrt, Rundkurs ~110 m.
NORD = ((47.00, 11.00), (47.05, 11.00))
SUED = ((47.05, 11.00), (47.00, 11.00))
RUNDKURS = ((47.000, 11.00), (47.001, 11.00))

RADTOUR = {"template": "radtour"}
RADTOUR_AUS = {"template": "radtour", "metrics": {"wind_direction": {"modus": "aus"}}}


# ---------------------------------------------------------------------------
# Fixtures (echte Datenobjekte)
# ---------------------------------------------------------------------------

def _dp(hour: int, kmh: float, deg: float, gust: float = 10.0) -> ForecastDataPoint:
    """Stunde mit sonst ruhigem Wetter: Boeen niedrig (kein Paar-Eskalieren
    im Zeilenpunkt), kein Regen, 15 Grad, wenig Wolken."""
    return ForecastDataPoint(
        ts=datetime(2026, 7, 11, hour, 0, tzinfo=timezone.utc),
        t2m_c=15.0, wind10m_kmh=kmh, gust_kmh=gust, wind_direction_deg=deg,
        precip_1h_mm=0.0, pop_pct=0, cloud_total_pct=20,
        thunder_level=ThunderLevel.NONE, wind_chill_c=14.0,
    )


def _segment(seg_id: int, geo, dps: list[ForecastDataPoint],
             start_h: int = 8, end_h: int = 10) -> SegmentWeatherData:
    (slat, slon), (elat, elon) = geo
    seg = TripSegment(
        segment_id=seg_id,
        start_point=GPXPoint(lat=slat, lon=slon, elevation_m=400.0),
        end_point=GPXPoint(lat=elat, lon=elon, elevation_m=500.0),
        start_time=datetime(2026, 7, 11, start_h, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 11, end_h, 0, tzinfo=timezone.utc),
        duration_hours=float(end_h - start_h), distance_km=10.0,
        ascent_m=100.0, descent_m=0.0,
    )
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="icon_d2",
        run=datetime(2026, 7, 11, 0, 0, tzinfo=timezone.utc),
        grid_res_km=2.0, interp="point_grid",
    )
    winds = [d.wind10m_kmh for d in dps]
    agg = SegmentWeatherSummary(
        temp_min_c=15.0, temp_max_c=15.0, temp_avg_c=15.0,
        wind_max_kmh=max(winds), gust_max_kmh=10.0, precip_sum_mm=0.0,
        cloud_avg_pct=20, humidity_avg_pct=50,
        thunder_level_max=ThunderLevel.NONE, wind_chill_min_c=14.0,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=NormalizedTimeseries(meta=meta, data=dps),
        aggregated=agg, fetched_at=datetime(2026, 7, 11, 0, 0, tzinfo=timezone.utc),
        provider="openmeteo",
    )


def _etappe(geo, kmh: float, deg: float, seg_id: int = 1, start_h: int = 8):
    """Etappe mit drei gleichen Stunden (start_h .. start_h+2)."""
    return _segment(seg_id, geo, [_dp(start_h + i, kmh, deg) for i in range(3)],
                    start_h=start_h, end_h=start_h + 2)


def _dc(ampel, *, roh: bool = False):
    """Standard-Anzeige mit Wind + Windrichtung an. ``roh=False``: Kompass in der
    Wind-Zelle (Merge, ``format_mode`` scale = Katalog-Standard); ``roh=True``:
    eigene WDir-Spalte in Grad."""
    dc = build_default_display_config()
    dc.ampel = copy.deepcopy(ampel)
    for mc in dc.metrics:
        if mc.metric_id in ("wind", "wind_direction"):
            mc.enabled = True
        if roh and mc.metric_id == "wind_direction":
            mc.format_mode = "raw"
            mc.use_friendly_format = False
    return dc


def _report(segments, ampel, *, roh: bool = False, display_config=None, trip=None):
    dc = display_config if display_config is not None else _dc(ampel, roh=roh)
    return TripReportFormatter().format_email(
        segments, "Radtrip", "evening", display_config=dc, tz=_UTC, trip=trip,
    )


# ---------------------------------------------------------------------------
# HTML-Messstellen
# ---------------------------------------------------------------------------

def _seg_table(html: str, seg_id: int) -> str:
    """Desktop-Stundentabelle der Etappe ``seg_id`` (erste resp-Tabelle nach
    der Kopfzeile ``SEG n``)."""
    pos = html.find(f">SEG {seg_id}</span>")
    assert pos != -1, f"Testdaten-Fehler: Etappe SEG {seg_id} fehlt im HTML"
    start = html.find('<table data-table="resp"', pos)
    assert start != -1, f"Testdaten-Fehler: keine Stundentabelle nach SEG {seg_id}"
    return html[start:html.find("</table>", start)]


def _bg_level(td_open: str):
    m = re.search(r"background:(#[0-9a-fA-F]{6})", td_open)
    if not m:
        return None
    return _BG_TO_LEVEL.get(m.group(1).lower(), f"unbekannt:{m.group(1)}")


def _dot_level(inner: str):
    m = re.search(r"border-radius:50%;background:(#[0-9a-fA-F]{6})", inner)
    if not m:
        return None
    return _DOT_TO_LEVEL.get(m.group(1).lower(), f"unbekannt:{m.group(1)}")


def _zeilen(html: str, seg_id: int, label: str) -> list[dict]:
    """Je Stundenzeile: Zeit, Zelltoenung und Inhalt der Spalte ``label``,
    Ampelpunkt in der Zelle, Zeilenpunkt (letzte Zelle)."""
    table = _seg_table(html, seg_id)
    out = []
    for tr in re.findall(r"<tr>(.*?)</tr>", table, re.S):
        if "<th" in tr:
            continue
        zeit = re.search(r'data-label="Time">([^<]*)<', tr).group(1)
        m = re.search(rf'(<td[^>]*data-label="{label}"[^>]*>)(.*?)</td>', tr, re.S)
        assert m, f"Testdaten-Fehler: Spalte {label!r} fehlt in SEG {seg_id}: {tr[:300]}"
        letzte = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)[-1]
        out.append({
            "zeit": zeit, "bg": _bg_level(m.group(1)), "inhalt": m.group(2),
            "punkt": _dot_level(m.group(2)), "zeilenpunkt": _dot_level(letzte),
        })
    assert out, f"Testdaten-Fehler: keine Stundenzeilen in SEG {seg_id}"
    return out


def _wind(html: str, seg_id: int = 1) -> list[dict]:
    return _zeilen(html, seg_id, "Wind")


def _ohne_uhrzeit(html: str) -> str:
    """Sendezeit (``sent_at`` = jetzt) neutralisieren, damit zwei Renderings
    an einer Minutengrenze nicht zufaellig abweichen."""
    return re.sub(r"\d{2}:\d{2}", "HH:MM", html)


# ---------------------------------------------------------------------------
# AC-1: Nordwind 25 km/h bei Nordkurs -> orange
# ---------------------------------------------------------------------------

def test_ac1_nordwind_25_bei_nordkurs_wind_zelle_orange():
    """AC-1: Radtour, Etappe nach Norden, 25 km/h aus Norden.

    Datenwahl: Windstaerke 25 km/h ergibt nach Radtour-Ampel (20/30/45) allein
    GELB; die Gegenwindkomponente 25 km/h (Grenzen 10/20/30) ergibt ORANGE.
    Orange kann also nur aus der Windrichtung kommen. Gegenprobe: dieselbe
    Etappe mit ``modus: aus`` bleibt gelb (Messaufbau ist scharf)."""
    seg = _etappe(NORD, 25, 0)
    ohne = _wind(_report([seg], RADTOUR_AUS).email_html)
    assert {z["bg"] for z in ohne} == {"yellow"}, f"Messaufbau: Windstaerke allein gelb, war {ohne}"
    assert all(z["inhalt"].rstrip().endswith("N") for z in ohne), "Kompass N steht in der Wind-Zelle"

    mit = _wind(_report([seg], RADTOUR).email_html)
    assert [z["bg"] for z in mit] == ["orange"] * len(mit), (
        f"AC-1: Gegenwind 25 km/h muss die Wind-Zelle orange toenen, war {[z['bg'] for z in mit]}"
    )


def test_ac1_schwellen_der_windrichtung_aus_abgeleiteter_ampel():
    """Schnittstelle (Spec Implementation Details): ``wind_direction`` ist eine
    abgeleitete Ampelgroesse (``AMPEL_ABGELEITET``); ``schwellen_aus_ampel``
    liefert ihre km/h-Grenzen, ``hat_ampel`` bleibt False (AC-11)."""
    from app import ampel as ampel_mod

    assert "wind_direction" in getattr(ampel_mod, "AMPEL_ABGELEITET", frozenset()), (
        "AMPEL_ABGELEITET mit 'wind_direction' fehlt in app.ampel"
    )
    radtour = resolve_ampel({"display_config": {"ampel": RADTOUR}})
    assert ampel_mod.schwellen_aus_ampel(radtour, "wind_direction") == {
        "yellow": 10, "orange": 20, "red": 30,
    }
    assert hat_ampel("wind_direction") is False


def test_ac1_stundenzeilen_tragen_den_gegenwind_als_seitenkanal():
    """Seitenkanal ``row["_wind_unerwuenscht_kmh"]`` (analog ``_wind_dir_deg``):
    bei Radtour und Nordkurs/Nordwind 25 km/h je Stunde 25.0. Zeilenbau ueber
    ``_extract_hourly_rows(seg_data, dc, ampel=...)``, Ampel = aufgeloeste
    Abo-Ampel (Pflicht-Keyword, Ratsche test_profil_ampel_kette)."""
    seg = _etappe(NORD, 25, 0)
    dc = _dc(RADTOUR)
    rows = TripReportFormatter()._extract_hourly_rows(seg, dc, ampel=resolve_ampel(dc))
    assert rows, "Testdaten-Fehler: keine Zeilen"
    assert [r.get("_wind_unerwuenscht_kmh") for r in rows] == [25.0] * len(rows)


# ---------------------------------------------------------------------------
# AC-2: Rueckenwind / Seitenwind -> keine Richtungsfaerbung
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("deg, kompass", [(180, "S"), (90, "O")])
def test_ac2_rueckenwind_und_seitenwind_keine_richtungsfaerbung(deg, kompass):
    """AC-2: Sued (Rueckenwind) und Ost (reiner Seitenwind) bei Nordkurs:
    Zelle exakt wie ohne Feature (gelb aus Windstaerke 25 km/h), Anzeige gleich."""
    seg = _etappe(NORD, 25, deg)
    mit = _report([seg], RADTOUR).email_html
    ohne = _report([seg], RADTOUR_AUS).email_html
    assert _wind(mit) == _wind(ohne)
    assert {z["bg"] for z in _wind(mit)} == {"yellow"}


# ---------------------------------------------------------------------------
# AC-3: 5 km/h ungefaerbt, 10 km/h gelb
# ---------------------------------------------------------------------------

def test_ac3_schwacher_gegenwind_5_kmh_bleibt_ungefaerbt():
    """AC-3: 5 km/h Nordwind: Windstaerke gruen, Gegenwind 5 < 10 -> keine Toenung."""
    seg = _etappe(NORD, 5, 0)
    assert {z["bg"] for z in _wind(_report([seg], RADTOUR).email_html)} == {None}


def test_ac3_gegenwind_10_kmh_wird_gelb():
    """AC-3: 10 km/h Nordwind: Windstaerke allein gruen (< 20), Gegenwind
    10 km/h erreicht die gelbe Grenze -> gelb (nur aus der Richtung)."""
    seg = _etappe(NORD, 10, 0)
    assert {z["bg"] for z in _wind(_report([seg], RADTOUR_AUS).email_html)} == {None}, "Messaufbau"
    assert [z["bg"] for z in _wind(_report([seg], RADTOUR).email_html)] == ["yellow"] * 3


# ---------------------------------------------------------------------------
# AC-4: Rundkurs ohne Fahrtrichtung, Nachbarsegment gefaerbt
# ---------------------------------------------------------------------------

def _rundkurs_und_nachbar():
    return [
        _etappe(RUNDKURS, 40, 0, seg_id=1, start_h=8),
        _etappe(NORD, 40, 0, seg_id=2, start_h=11),
    ]


def test_ac4_rundkurs_unter_300_m_keine_richtungsfaerbung():
    """AC-4: Rundkurs (~110 m Luftlinie), 40 km/h Nordwind: Wind-Zelle genau wie
    mit ``modus: aus`` (orange aus der Windstaerke 40 km/h)."""
    segs = _rundkurs_und_nachbar()
    mit = _wind(_report(segs, RADTOUR).email_html, 1)
    ohne = _wind(_report(segs, RADTOUR_AUS).email_html, 1)
    assert {z["bg"] for z in ohne} == {"orange"}, "Messaufbau: 40 km/h allein orange"
    assert mit == ohne


def test_ac4_nachbarsegment_mit_gegenwind_wird_gefaerbt():
    """AC-4: das angrenzende Nordkurs-Segment mit 40 km/h Gegenwind wird ROT
    (Gegenwind 40 >= 30), waehrend die Windstaerke allein nur orange ergaebe."""
    segs = _rundkurs_und_nachbar()
    ohne = _wind(_report(segs, RADTOUR_AUS).email_html, 2)
    assert {z["bg"] for z in ohne} == {"orange"}, "Messaufbau"
    mit = _wind(_report(segs, RADTOUR).email_html, 2)
    assert [z["bg"] for z in mit] == ["red"] * len(mit), (
        f"AC-4: Nachbarsegment mit Gegenwind muss rot sein, war {[z['bg'] for z in mit]}"
    )


# ---------------------------------------------------------------------------
# AC-6: Alt-Trip ohne modus byte-gleich
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("vorlage", ["wandern", "allgemein", "alpen-trekking"])
def test_ac6_alt_trip_ohne_modus_mail_byte_gleich(vorlage):
    """AC-6: Vorlage ohne Windrichtungs-Modus (Bestand): HTML und Klartext
    identisch zum Rendern mit ausdruecklich ``modus: aus``; Nordkurs/Nordwind
    25 km/h, damit eine faelschliche Richtungsfaerbung sichtbar wuerde.
    Darf vor der Implementierung gruen sein (Regressionssicherung)."""
    seg = _etappe(NORD, 25, 0)
    alt = _report([seg], {"template": vorlage})
    aus = _report([seg], {"template": vorlage, "metrics": {"wind_direction": {"modus": "aus"}}})
    assert _ohne_uhrzeit(alt.email_html) == _ohne_uhrzeit(aus.email_html)
    assert _ohne_uhrzeit(alt.email_plain) == _ohne_uhrzeit(aus.email_plain)


def test_ac6_alt_trip_zeilen_ohne_seitenkanal():
    """AC-6: ohne Modus wird der Seitenkanal gar nicht gesetzt (Mail
    strukturell unveraendert). Darf vorher gruen sein."""
    seg = _etappe(NORD, 25, 0)
    for ampel in ({"template": "wandern"}, RADTOUR_AUS):
        dc = _dc(ampel)
        rows = TripReportFormatter()._extract_hourly_rows(seg, dc, ampel=resolve_ampel(dc))
        assert rows
        assert all("_wind_unerwuenscht_kmh" not in r for r in rows), ampel


# ---------------------------------------------------------------------------
# AC-7: Merge-Fall -> hoehere der beiden Stufen, konsistent
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("kmh, deg, erwartet, begruendung", [
    (25, 0, "orange", "Windstaerke gelb (25), Gegenwind orange (25)"),
    (50, 70, "red", "Windstaerke rot (50), Gegenwind gelb (50*cos70=17.1)"),
    (25, 60, "yellow", "Windstaerke gelb (25), Gegenwind gelb (12.5): nicht addiert"),
])
def test_ac7_merge_zelle_zeigt_maximum_konsistent_mit_punkt_und_zeilenpunkt(
    kmh, deg, erwartet, begruendung,
):
    """AC-7: Kompass in der Wind-Zelle; Zellfarbe, Ampelpunkt (fmt_val) und
    Zeilenpunkt (_row_risk) zeigen alle das Maximum beider Einzelstufen,
    nie eine hoehere (keine Addition). Boeen niedrig, sonst ruhiges Wetter."""
    seg = _etappe(NORD, kmh, deg)
    zeilen = _wind(_report([seg], RADTOUR).email_html)
    for z in zeilen:
        assert (z["bg"], z["punkt"], z["zeilenpunkt"]) == (erwartet, erwartet, erwartet), (
            f"AC-7 ({begruendung}): Zelle/Punkt/Zeilenpunkt = "
            f"{z['bg']}/{z['punkt']}/{z['zeilenpunkt']}, erwartet {erwartet}"
        )


# ---------------------------------------------------------------------------
# AC-9: zwei Nutzer, eigene Einstellung
# ---------------------------------------------------------------------------

def _speichere_trip(tmp_path: Path, user_id: str, ampel: dict) -> None:
    from app.loader import _metric_to_dict

    data = json.loads((_HERE.parent / "fixtures" / "trip_schema_full.json").read_text(encoding="utf-8"))
    dc = _dc(ampel)
    data["display_config"] = {
        "metrics": [_metric_to_dict(mc) for mc in dc.metrics],
        "ampel": ampel,
    }
    pfad = tmp_path / "users" / user_id / "briefings" / f"{data['id']}.json"
    pfad.parent.mkdir(parents=True)
    pfad.write_text(json.dumps(data), encoding="utf-8")


def test_ac9_zwei_nutzer_eigene_windrichtungs_einstellung(tmp_path):
    """AC-9: Nutzer ``anna`` (radtour, Gegenwind) und ``bert`` (radtour, modus aus)
    haben denselben Trip (gleiche ID) mit gleichen Winddaten. Die Einstellung
    wird je Nutzer aus ``data/users/<id>/briefings`` geladen (nie "default"):
    Anna orange, Bert nur Windstaerke (gelb)."""
    from app.loader import load_trip

    _speichere_trip(tmp_path, "anna", RADTOUR)
    _speichere_trip(tmp_path, "bert", RADTOUR_AUS)
    seg = _etappe(NORD, 25, 0)
    trip_id = json.loads((_HERE.parent / "fixtures" / "trip_schema_full.json")
                         .read_text(encoding="utf-8"))["id"]

    anna = load_trip(trip_id, data_dir=tmp_path, user_id="anna")
    bert = load_trip(trip_id, data_dir=tmp_path, user_id="bert")
    assert resolve_ampel(anna)["metrics"]["wind_direction"]["modus"] == "gegenwind"
    assert resolve_ampel(bert)["metrics"]["wind_direction"]["modus"] == "aus"

    html_b = _report([seg], None, display_config=bert.display_config).email_html
    html_a = _report([seg], None, display_config=anna.display_config).email_html
    assert {z["bg"] for z in _wind(html_b)} == {"yellow"}, "Bert: keine Richtungsfaerbung"
    assert [z["bg"] for z in _wind(html_a)] == ["orange"] * 3, "Anna: Gegenwind orange"
    # Reihenfolge umgekehrt: kein Zustand wandert zwischen den Renderings.
    assert {z["bg"] for z in _wind(_report([seg], None, display_config=bert.display_config).email_html)} == {"yellow"}


# ---------------------------------------------------------------------------
# AC-10: Roh-Modus, eigene WDir-Spalte nach km/h, nicht nach Grad
# ---------------------------------------------------------------------------

def test_ac10_roh_modus_wdir_zelle_nach_gegenwind_orange():
    """AC-10: eigene WDir-Spalte (Grad), Nordkurs, 25 km/h aus 0 Grad ->
    WDir-Zelle orange (Gegenwind 25 km/h), Inhalt bleibt die Gradzahl."""
    seg = _etappe(NORD, 25, 0)
    zeilen = _zeilen(_report([seg], RADTOUR, roh=True).email_html, 1, "WDir")
    assert all("0°" in z["inhalt"] for z in zeilen), "Testdaten: WDir zeigt Grad"
    assert [z["bg"] for z in zeilen] == ["orange"] * 3, (
        f"AC-10: WDir-Zelle muss nach Gegenwind-km/h orange sein, war {[z['bg'] for z in zeilen]}"
    )


@pytest.mark.parametrize("geo, deg", [(NORD, 180), (SUED, 350)])
def test_ac10_roh_modus_grad_ohne_gegenwind_bleibt_ungefaerbt(geo, deg):
    """AC-10: Gefaerbt wird nach km/h, nicht nach Grad: Suedwind (180 Grad) bei
    Nordkurs und 350 Grad bei Suedkurs (Rueckenwind) bleiben ungefaerbt,
    obwohl 180/350 ueber jeder km/h-Grenze laegen. Darf vorher gruen sein."""
    seg = _etappe(geo, 25, deg)
    zeilen = _zeilen(_report([seg], RADTOUR, roh=True).email_html, 1, "WDir")
    assert all(f"{deg}°" in z["inhalt"] for z in zeilen), "Testdaten: WDir zeigt Grad"
    assert {z["bg"] for z in zeilen} == {None}


# ---------------------------------------------------------------------------
# AC-11: Kurzkanaele unberuehrt
# ---------------------------------------------------------------------------

def test_ac11_hat_ampel_windrichtung_bleibt_false():
    """AC-11: ``hat_ampel`` meldet fuer die Windrichtung weiter keine Ampel.
    Regressionssicherung, darf vorher gruen sein."""
    assert hat_ampel("wind_direction") is False


def test_ac11_sms_premium_telegram_identisch_zu_modus_aus():
    """AC-11: Radtrip mit 25 km/h Gegenwind: SMS, Premium-SMS und Telegram sind
    identisch zur Ausgabe mit ``modus: aus`` (S3 zieht nach), waehrend die Mail
    sich unterscheiden darf. Regressionssicherung, darf vorher gruen sein."""
    segs = [_etappe(NORD, 25, 0, seg_id=1, start_h=8), _etappe(NORD, 40, 0, seg_id=2, start_h=11)]
    mit = _report(segs, RADTOUR)
    aus = _report(segs, RADTOUR_AUS)
    assert mit.sms_text == aus.sms_text
    assert mit.premium_sms_text == aus.premium_sms_text
    assert mit.telegram_bubbles == aus.telegram_bubbles


# ---------------------------------------------------------------------------
# Regression: 3-Tages-Ausblick faerbt die Windrichtung nie nach Grad
# ---------------------------------------------------------------------------

def test_ausblick_windrichtung_350_grad_bei_radtour_ohne_hintergrund():
    """Seit ``schwellen_aus_ampel`` die Windrichtung liest (AMPEL_ABGELEITET),
    haette der Ausblick den GRADWERT gegen die km/h-Grenzen geprueft (350 Grad
    >= 30 -> rot). Der Ausblick kennt den abgeleiteten Wert erst ab S3: die
    Windrichtungs-Spalte bleibt ohne Hintergrund. Gegenprobe: die Windspalte
    derselben Zeile (50 km/h, Radtour-Wind rot ab 45) ist gefaerbt,
    der Messaufbau also scharf. Echter Aufruf, kein Mock."""
    from output.renderers.email.outlook import build_outlook_row, render_outlook_table

    ampel = resolve_ampel({"display_config": {"ampel": RADTOUR}})
    wdir = {"metric_id": "wind_direction", "aggregation": "avg"}
    wind = {"metric_id": "wind", "aggregation": "max"}
    summary = SegmentWeatherSummary(wind_direction_avg_deg=350, wind_max_kmh=50.0)
    row = build_outlook_row(summary, [], "Mo", _UTC, metrics=[wdir, wind],
                            context="route", ampel=ampel)
    html = render_outlook_table([row], show_acc=False, metrics=[wdir, wind], ampel=ampel)

    styles = re.findall(r'<td style="([^"]*)"', html)
    assert len(styles) == 3, f"Testdaten: Wochentag + 2 Spalten erwartet: {styles!r}"
    assert "background:" not in styles[1], f"Windrichtung 350 Grad gefaerbt: {styles[1]!r}"
    assert styles[2].startswith(f"background:{tone_css('red')[0]};"), (
        f"Messaufbau: Windspalte 50 km/h muss rot sein, war {styles[2]!r}"
    )
