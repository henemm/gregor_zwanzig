"""Stundentabellen-Gewitterspalte wird eine reguläre Ampel-Spalte (Issue #1491).

SPEC: docs/specs/modules/fix_1491_gewitter_ampelkreis.md

Bisher: `fmt_val()` (`src/output/renderers/email/helpers.py`, Zweig `thunder`)
kennt nur `MED`/`HIGH`, behandelt `LOW` wie `NONE` (Strich) und benutzt
Blitzsymbole + das Wort `mögl.` -- Widerspruch zur Kurzfassung/Prosa-Pille,
die für dieselbe Stunde bereits "Gewitter" melden (Issue #1491).

Diese Datei prüft ausschließlich an der ECHT gerenderten Mail (Trip-Briefing
via `TripReportFormatter`/`render_email`, Ortsvergleich via
`render_compare_html`) -- kein isolierter `fmt_val()`-Aufruf allein. Genau
ein solcher isolierter Test (`test_issue_811_mode_matrix.py`) stand bereits
neben dem ursprünglichen Bug und hat ihn nicht gefangen (Spec AC-6, Lehre aus
#1457: an der Stelle prüfen, wo die Zusicherung WIRKT).

Keine Mocks/patch/MagicMock -- echte `ForecastDataPoint`-/`SegmentWeatherData`-
/`LocationResult`-Objekte, echte Renderer, kein Netz.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from app.models import ThunderLevel

TZ = ZoneInfo("Europe/Berlin")

# Ampel-Kreis-Palette (helpers._AMPEL_DOT_COLORS) -- fill-Farbe je Stufe.
# Fest verdrahtet: die Spec schreibt ausdrücklich vor, den bestehenden
# Baustein `_ampel_dot_css`/`_AMPEL_DOT_COLORS` wiederzuverwenden, nicht eine
# neue Palette zu erfinden.
_GREEN_FILL = "#15803d"
_YELLOW_FILL = "#ca8a04"
_ORANGE_FILL = "#c2410c"
_RED_FILL = "#b91c1c"

_LEVEL_FILL = {
    ThunderLevel.NONE: _GREEN_FILL,
    ThunderLevel.LOW: _YELLOW_FILL,
    ThunderLevel.MED: _ORANGE_FILL,
    ThunderLevel.HIGH: _RED_FILL,
}
_LEVEL_WORD = {
    ThunderLevel.NONE: "kein",
    ThunderLevel.LOW: "leicht",
    ThunderLevel.MED: "mittel",
    ThunderLevel.HIGH: "hoch",
}


# ---------------------------------------------------------------------------
# Render-Bausteine (Trip) -- Vorbild tests/tdd/test_issue_811_mode_matrix.py
# ---------------------------------------------------------------------------

def _dp(thunder_level, *, hour: int = 10):
    from app.models import ForecastDataPoint
    return ForecastDataPoint(
        ts=datetime(2026, 7, 11, hour, 0, tzinfo=timezone.utc),
        t2m_c=20.0, wind10m_kmh=10.0, gust_kmh=20.0, precip_1h_mm=0.5,
        pop_pct=20, cloud_total_pct=50, thunder_level=thunder_level,
        wind_chill_c=18.0,
    )


def _seg_data(dp, *, start_hour: int = 8, end_hour: int = 12):
    from app.models import (
        ForecastMeta, GPXPoint, NormalizedTimeseries, Provider,
        SegmentWeatherData, SegmentWeatherSummary, TripSegment,
    )
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.20, lon=9.05, elevation_m=400.0),
        end_point=GPXPoint(lat=42.25, lon=9.09, elevation_m=1200.0),
        start_time=datetime(2026, 7, 11, start_hour, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 11, end_hour, 0, tzinfo=timezone.utc),
        duration_hours=float(end_hour - start_hour), distance_km=8.0,
        ascent_m=800.0, descent_m=0.0,
    )
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="arome_france",
        run=datetime(2026, 7, 11, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.3, interp="point_grid",
    )
    ts = NormalizedTimeseries(meta=meta, data=[dp])
    agg = SegmentWeatherSummary(
        temp_min_c=14.0, temp_max_c=24.0, temp_avg_c=19.0,
        wind_max_kmh=10.0, gust_max_kmh=20.0, precip_sum_mm=0.5,
        cloud_avg_pct=50, humidity_avg_pct=55,
        thunder_level_max=dp.thunder_level, wind_chill_min_c=18.0,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=ts, aggregated=agg,
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )


def _dc(*, raw: bool):
    """Nur die Metrik 'thunder' aktiv, Modus Roh oder Einfach (Symbol)."""
    from app.metric_catalog import build_default_display_config
    dc = build_default_display_config()
    for mc in dc.metrics:
        mc.enabled = mc.metric_id == "thunder"
        mc.format_mode = "raw" if raw else None
        mc.use_friendly_format = not raw
    return dc


def _render_thunder(thunder_level, *, raw: bool):
    """Rendert eine Ein-Stunden-Etappe über den echten render_email-Pfad,
    NUR die Gewitter-Spalte aktiv. Gibt (html, plain) zurück."""
    from output.renderers.email import render_email
    from output.renderers.email.helpers import dp_to_row
    from output.tokens.dto import TokenLine

    dp = _dp(thunder_level)
    dc = _dc(raw=raw)
    row = dp_to_row(dp, dc, tz=TZ)
    tl = TokenLine(trip_name="Ampel-Test", report_type="evening", stage_name="Etappe 1")
    return render_email(
        tl, segments=[_seg_data(dp)], seg_tables=[[row]],
        display_config=dc, tz=TZ, friendly_keys=set(),
        email_format="full",
    )


def _thunder_td_html(html: str) -> str:
    """Volles `<td ...>...</td>` der Gewitter-Zelle (data-label='Thdr') aus
    der Desktop-Stundentabelle (class-Marker `data-table="resp"`)."""
    m = re.search(r'<table[^>]*data-table="resp"[^>]*>.*?</table>', html, re.S)
    assert m, f"Stundentabelle nicht gefunden. HTML-Ausschnitt: {html[:1500]!r}"
    tds = re.findall(r'<td[^>]*data-label="Thdr"[^>]*>.*?</td>', m.group(0), re.S)
    assert len(tds) == 1, f"Erwartete genau eine Gewitter-Zelle, gefunden: {tds!r}"
    return tds[0]


def _thunder_cell_content(html: str) -> str:
    """Nur der Zellinhalt (ohne das umschließende <td ...>...</td>)."""
    td = _thunder_td_html(html)
    return re.sub(r"^<td[^>]*>|</td>$", "", td, flags=re.S)


def _td_open_tag(td_html: str) -> str:
    """Nur das öffnende `<td ...>` (Attribute), ohne Zellinhalt -- für die
    Zell-TÖNUNG (nicht die innere Ampel-Kreis-Farbe im Span)."""
    end = td_html.index(">")
    return td_html[: end + 1]


def _plain_thunder_row(plain: str) -> str:
    """Isoliert die einzige Stundentabellen-Datenzeile im Klartext-Teil
    (beginnt mit einer Ziffer, direkt nach der '-----'-Trennzeile)."""
    lines = plain.splitlines()
    in_table = False
    rows: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("-----"):
            in_table = True
            continue
        if in_table:
            if not stripped:
                break
            if stripped[0].isdigit():
                rows.append(stripped)
    assert len(rows) == 1, (
        f"Erwartete genau eine Stundenzeile im Klartext-Teil, gefunden: "
        f"{rows!r}\nVoller Klartext: {plain!r}"
    )
    return rows[0]


# ---------------------------------------------------------------------------
# Adversary-Finding F002 (Sonnet-Adversary, Issue #1491): die Sicherheits-
# invariante "keine Aussage != keine Gefahr" hielt bislang nur, weil zwei
# VORGELAGERTE Mechanismen sie zufaellig schuetzen (`fmt_val()` faengt
# `val is None` bereits vor dem `thunder`-Zweig ab; `html.py` uebergibt in der
# Praxis nie ein rohes `None` an `thunder_ampel_band()`). Ein kuenftiger
# DRITTER Aufrufer der reinen Funktion waere ungeschuetzt. Direkter Test der
# Funktion selbst, unabhaengig vom Renderer-Umweg.
# ---------------------------------------------------------------------------

def test_f002_thunder_ampel_band_of_none_is_none():
    """GIVEN kein ThunderLevel (None, keine Gewitteraussage)
    WHEN thunder_ampel_band() direkt aufgerufen wird
    THEN liefert sie None -- niemals ein Ampelband (insbesondere nicht
    'green'). Direkte Absicherung der Quelle, nicht nur ueber den Renderer.
    """
    from output.metric_format import thunder_ampel_band

    assert thunder_ampel_band(None) is None, (
        "F002: thunder_ampel_band(None) muss None liefern -- 'keine Aussage' "
        "darf an der Quelle selbst nie zu einem Ampelband werden."
    )


# ---------------------------------------------------------------------------
# AC-1 (wichtigstes AC) -- fehlender Wert bleibt Strich, NIE grüner Kreis
# ---------------------------------------------------------------------------

def test_ac1_fehlender_wert_bleibt_strich_kein_gruener_kreis():
    """GIVEN eine Stunde ohne jede Gewitteraussage (thunder_level=None)
    WHEN die Briefing-Mail (einfache HTML-Ansicht) gerendert wird
    THEN zeigt die Gewitter-Zelle einen Strich (–) -- NIEMALS einen grünen
    Ampel-Kreis. 'Keine Aussage' darf nirgends wie 'keine Gefahr' aussehen.
    """
    html, _plain = _render_thunder(None, raw=False)
    cell = _thunder_cell_content(html)
    assert "–" in cell, f"AC-1: fehlender Wert muss ein Strich sein: {cell!r}"
    assert _GREEN_FILL not in cell, (
        f"AC-1: fehlender Wert darf NIEMALS als grüner Ampel-Kreis erscheinen "
        f"('keine Aussage' != 'keine Gefahr'). Zelle: {cell!r}"
    )
    assert "border-radius:50%" not in cell, (
        f"AC-1: fehlender Wert darf keinerlei Ampel-Kreis zeigen: {cell!r}"
    )


# ---------------------------------------------------------------------------
# AC-2 -- ruhige Stunde (NONE) zeigt grünen Kreis, Gegenprobe gegen AC-1
# ---------------------------------------------------------------------------

def test_ac2_ruhige_stunde_zeigt_gruenen_kreis_unterscheidbar_von_strich():
    """GIVEN eine Stunde mit geprüfter Entwarnung (thunder_level=NONE)
    WHEN dieselbe Mail gerendert wird
    THEN zeigt die Gewitter-Spalte einen grünen Ampel-Kreis -- und dieser
    unterscheidet sich von der Strich-Zelle bei fehlendem Wert (AC-1).
    Beide Ergebnisse dürfen NIE gleich werden (Gegenprobe).
    """
    html_none_value, _ = _render_thunder(ThunderLevel.NONE, raw=False)
    cell_none_value = _thunder_cell_content(html_none_value)

    html_missing, _ = _render_thunder(None, raw=False)
    cell_missing = _thunder_cell_content(html_missing)

    assert _GREEN_FILL in cell_none_value, (
        f"AC-2: ThunderLevel.NONE (geprüft, ruhig) muss einen grünen "
        f"Ampel-Kreis zeigen, nicht mehr den Strich. Zelle: {cell_none_value!r}"
    )
    assert cell_none_value != cell_missing, (
        f"AC-2 Gegenprobe: 'ruhig' (grüner Kreis) und 'keine Aussage' "
        f"(Strich) dürfen NIE dasselbe Ergebnis liefern. "
        f"NONE={cell_none_value!r} fehlend={cell_missing!r}"
    )


# ---------------------------------------------------------------------------
# AC-3 -- alle vier Stufen als Ampel-Kreis, kein Blitzsymbol, kein 'mögl.'
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "level", [ThunderLevel.NONE, ThunderLevel.LOW, ThunderLevel.MED, ThunderLevel.HIGH],
    ids=["none", "low", "med", "high"],
)
def test_ac3_alle_vier_stufen_als_ampel_kreis_kein_blitzsymbol(level):
    """GIVEN eine Stunde je Stufe kein/leicht/mittel/hoch
    WHEN die Mail gerendert wird
    THEN zeigt jede Stunde den zugehörigen Ampel-Kreis (grün/gelb/orange/rot),
    und keine Zelle enthält ein Blitzsymbol (⚡) oder das Wort 'mögl.'.
    """
    html, _plain = _render_thunder(level, raw=False)
    cell = _thunder_cell_content(html)
    expected_fill = _LEVEL_FILL[level]
    assert expected_fill in cell, (
        f"AC-3: Stufe {level!r} muss den Ampel-Kreis (fill {expected_fill!r}) "
        f"zeigen. Zelle: {cell!r}"
    )
    assert "⚡" not in cell, f"AC-3: kein Blitzsymbol mehr erlaubt. Zelle: {cell!r}"
    assert "mögl" not in cell, f"AC-3: kein 'mögl.' mehr erlaubt. Zelle: {cell!r}"


# ---------------------------------------------------------------------------
# AC-4 -- Text-Fassung zeigt die vier Wörter, kein Blitzsymbol, kein 'mögl.'
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw", [True, False], ids=["roh", "symbol"])
@pytest.mark.parametrize(
    "level", [ThunderLevel.NONE, ThunderLevel.LOW, ThunderLevel.MED, ThunderLevel.HIGH],
    ids=["none", "low", "med", "high"],
)
def test_ac4_text_fassung_zeigt_wort_kein_blitz_kein_moegl(level, raw):
    """GIVEN dieselben vier Stufen
    WHEN der Klartext-Teil der Mail gerendert wird (Roh- UND Symbol-Modus --
    Klartext kann keinen CSS-Kreis darstellen, muss also in BEIDEN Modi das
    Wort zeigen)
    THEN steht in der Gewitter-Spalte das jeweilige Wort kein/leicht/mittel/
    hoch, nirgends ein Blitzsymbol oder 'mögl.'.
    """
    _html, plain = _render_thunder(level, raw=raw)
    row = _plain_thunder_row(plain)
    expected_word = _LEVEL_WORD[level]
    assert expected_word in row, (
        f"AC-4: Text-Fassung (Klartext, raw={raw}) muss bei Stufe {level!r} "
        f"das Wort {expected_word!r} zeigen. Zeile: {row!r}"
    )
    assert "⚡" not in row, f"AC-4: kein Blitzsymbol im Klartext erlaubt: {row!r}"
    assert "mögl" not in row, f"AC-4: kein 'mögl.' im Klartext erlaubt: {row!r}"


# ---------------------------------------------------------------------------
# AC-5 -- Zell-Tönung von LOW und MED unterscheiden sich (nicht mehr beide
# orange)
# ---------------------------------------------------------------------------

def test_ac5_low_und_med_zell_toenung_unterscheiden_sich():
    """GIVEN eine Stunde mit Stufe LOW und eine mit Stufe MED
    WHEN die HTML-Mail gerendert wird
    THEN hat die LOW-Zelle eine andere Hintergrundfarbe als die MED-Zelle
    (gelb-Ton vs. orange-Ton) -- bisher waren beide identisch orange gefärbt.
    """
    html_low, _ = _render_thunder(ThunderLevel.LOW, raw=False)
    html_med, _ = _render_thunder(ThunderLevel.MED, raw=False)
    td_low = _td_open_tag(_thunder_td_html(html_low))
    td_med = _td_open_tag(_thunder_td_html(html_med))

    bg_low = re.search(r"background:(#[0-9a-fA-F]{6})", td_low)
    bg_med = re.search(r"background:(#[0-9a-fA-F]{6})", td_med)
    assert bg_low, f"AC-5: LOW-Zelle hat keine Hintergrund-Tönung: {td_low!r}"
    assert bg_med, f"AC-5: MED-Zelle hat keine Hintergrund-Tönung: {td_med!r}"
    assert bg_low.group(1) != bg_med.group(1), (
        f"AC-5: LOW- und MED-Zelle dürfen keine identische Tönung mehr haben "
        f"(bisher beide {bg_low.group(1)!r}). LOW={bg_low.group(1)!r} "
        f"MED={bg_med.group(1)!r}"
    )


# ---------------------------------------------------------------------------
# AC-6 (der eigentliche Bug) -- Widerspruchsfreiheit an der GANZEN Mail
# ---------------------------------------------------------------------------

def _seg_data_low_at_hour(target_hour_utc: int) -> tuple:
    """Etappe 08-16 UTC, alle Stunden NONE außer `target_hour_utc` (LOW).
    Gibt (SegmentWeatherData, ForecastDataPoint der Zielstunde) zurück."""
    from app.models import (
        ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries,
        Provider, SegmentWeatherData, SegmentWeatherSummary, TripSegment,
    )
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.20, lon=9.05, elevation_m=400.0),
        end_point=GPXPoint(lat=42.25, lon=9.09, elevation_m=1200.0),
        start_time=datetime(2026, 7, 11, 8, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 11, 16, 0, tzinfo=timezone.utc),
        duration_hours=8.0, distance_km=14.0, ascent_m=900.0, descent_m=100.0,
    )
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="arome_france",
        run=datetime(2026, 7, 11, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.3, interp="point_grid",
    )
    data = []
    target_dp = None
    for h in range(8, 17):
        level = ThunderLevel.LOW if h == target_hour_utc else ThunderLevel.NONE
        dp = ForecastDataPoint(
            ts=datetime(2026, 7, 11, h, 0, tzinfo=timezone.utc),
            t2m_c=20.0, wind10m_kmh=10.0, gust_kmh=20.0, precip_1h_mm=0.0,
            pop_pct=10, cloud_total_pct=40, thunder_level=level,
            wind_chill_c=18.0,
        )
        data.append(dp)
        if h == target_hour_utc:
            target_dp = dp
    ts = NormalizedTimeseries(meta=meta, data=data)
    agg = SegmentWeatherSummary(
        temp_min_c=15.0, temp_max_c=25.0, temp_avg_c=20.0,
        wind_max_kmh=10.0, gust_max_kmh=20.0, precip_sum_mm=0.0,
        cloud_avg_pct=40, humidity_avg_pct=50,
        thunder_level_max=ThunderLevel.LOW, wind_chill_min_c=18.0,
    )
    seg_data = SegmentWeatherData(
        segment=seg, timeseries=ts, aggregated=agg,
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )
    return seg_data, target_dp


def _hour_row_html(html: str, hour_label: str) -> str:
    """Die `<tr>`-Zeile der Stundentabelle, deren Time-Zelle `hour_label`
    trägt (z.B. '15')."""
    m = re.search(r'<table[^>]*data-table="resp"[^>]*>.*?</table>', html, re.S)
    assert m, f"Stundentabelle nicht gefunden. HTML-Ausschnitt: {html[:1500]!r}"
    rows = re.findall(r"<tr>(.*?)</tr>", m.group(0), re.S)
    for row in rows:
        if re.search(rf'data-label="Time">{re.escape(hour_label)}<', row):
            return row
    raise AssertionError(
        f"Keine Zeile für Stunde {hour_label!r} gefunden. Zeilen: {rows!r}"
    )


def test_ac6_widerspruchsfreiheit_kurzfassung_und_stundentabelle():
    """GIVEN eine Etappe, deren einzige Gewitterstunde LOW trägt (Kurzfassung
    meldet dadurch ein Gewitter für diese Stunde)
    WHEN die VOLLSTÄNDIGE Briefing-Mail gerendert wird (echter
    TripReportFormatter-Pfad, kein Renderer-Ausschnitt)
    THEN meldet die Stundentabelle für exakt dieselbe Stunde NICHT '–'/'kein'
    -- sie zeigt den gelben Ampel-Kreis, konsistent mit der Kurzfassung.

    Genau dieser kombinierte Test hätte den ursprünglichen Bug gefangen: ein
    isolierter Aufruf des Zellformatierers allein (test_issue_811) stand
    bereits daneben und hat ihn nicht gefunden.
    """
    from output.renderers.trip_report import TripReportFormatter
    from utils.timezone import local_hour

    target_hour_utc = 13  # 15:00 Europe/Berlin (Sommerzeit, UTC+2)
    seg_data, target_dp = _seg_data_low_at_hour(target_hour_utc)
    # dp.ts ist naive UTC (Hausnorm #1345) -- dieselbe Aufloesung wie der
    # Renderer (dp_to_row/local_hour) verwenden, NICHT rohes .astimezone()
    # auf einem naiven Wert (das interpretiert ihn als Prozess-Systemzeit,
    # hier bewusst auf America/St_Johns fixiert, root conftest.py). Vorher
    # traf der Test dadurch eine falsche, gewitterfreie Stunde.
    local_hour_str = f"{local_hour(target_dp.ts, TZ):02d}"

    report = TripReportFormatter().format_email(
        [seg_data],
        trip_name="Ampel-Widerspruch-Test",
        report_type="evening",
        stage_name="Etappe 1",
        tz=TZ,
    )

    # Kurzfassung/Prosa meldet ein Gewitter für diese Stunde (unverändertes
    # Verhalten, s. Spec 'Known Limitations' -- die Erwähnungsschwelle wird
    # hier NICHT angefasst).
    assert "möglich" in report.email_html or "möglich" in report.email_plain, (
        f"Voraussetzung des Tests nicht erfüllt: die Kurzfassung erwähnt kein "
        f"Gewitter. HTML-Ausschnitt: {report.email_html[:800]!r}"
    )

    row = _hour_row_html(report.email_html, local_hour_str)
    thunder_cell = re.search(
        r'<td[^>]*data-label="Thdr"[^>]*>(.*?)</td>', row, re.S,
    )
    assert thunder_cell, (
        f"Keine Gewitter-Zelle in der Zeile für Stunde {local_hour_str!r} "
        f"gefunden: {row!r}"
    )
    cell_text = thunder_cell.group(1)
    assert "–" not in cell_text, (
        f"AC-6 (der eigentliche Bug): die Stundentabelle zeigt für Stunde "
        f"{local_hour_str} einen Strich, obwohl die Kurzfassung für "
        f"dieselbe Stunde ein Gewitter meldet. Zelle: {cell_text!r}"
    )
    assert "kein" not in cell_text, (
        f"AC-6: die Stundentabelle darf für Stunde {local_hour_str} nicht "
        f"'kein' zeigen, obwohl die Kurzfassung ein Gewitter meldet. "
        f"Zelle: {cell_text!r}"
    )
    assert _YELLOW_FILL in cell_text, (
        f"AC-6: die Stundentabelle muss für Stunde {local_hour_str} den "
        f"gelben Ampel-Kreis (LOW) zeigen, konsistent mit der Kurzfassung. "
        f"Zelle: {cell_text!r}"
    )


# ---------------------------------------------------------------------------
# AC-7 -- Ortsvergleich: unverändertes Aussehen, geteilte Herkunft
# ---------------------------------------------------------------------------

def _compare_location(level: ThunderLevel):
    from app.models import ForecastDataPoint
    from app.user import ComparisonResult, LocationResult, SavedLocation

    dp = ForecastDataPoint(
        ts=datetime(2026, 7, 8, 10, 0, tzinfo=timezone.utc),
        t2m_c=18.0, wind10m_kmh=10.0, gust_kmh=15.0, precip_1h_mm=0.0,
        cloud_total_pct=30, thunder_level=level, pop_pct=10,
        wind_chill_c=17.0,
    )
    loc = LocationResult(
        location=SavedLocation(
            id="testort", name="Testort", lat=42.0, lon=9.0, elevation_m=800,
        ),
        score=50, hourly_data=[dp],
    )
    return ComparisonResult(
        locations=[loc], time_window=(0, 23), target_date=date(2026, 7, 8),
        created_at=datetime(2026, 7, 8, 4, 1),
    )


def _compare_thunder_cell(html: str) -> str:
    """Zelle der 'Gewitter'-Spalte in der ersten Stundenzeile der
    PER-ORT-Stundentabelle (nicht die Übersichtsmatrix -- diese hat eine
    eigene erste Tabelle mit Kopf 'Metrik'/Ortsname, deshalb wird gezielt
    die Tabelle mit Kopf 'Zeit' gesucht)."""
    for table_match in re.finditer(r"<table[^>]*>.*?</table>", html, re.S):
        table_html = table_match.group(0)
        header_match = re.search(r"<thead>(.*?)</thead>", table_html, re.S)
        body_match = re.search(r"<tbody>(.*?)</tbody>", table_html, re.S)
        if not (header_match and body_match):
            continue
        headers = re.findall(r"<th[^>]*>(.*?)</th>", header_match.group(1), re.S)
        clean_headers = [re.sub(r"<[^>]+>", "", h).strip() for h in headers]
        if not clean_headers or clean_headers[0] != "Zeit":
            continue
        assert "Thdr" in clean_headers, f"Keine Gewitter-Spalte ('Thdr'): {clean_headers!r}"
        idx = clean_headers.index("Thdr")
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", body_match.group(1), re.S)
        assert rows, "Keine Stundenzeile im Ortsvergleich gefunden"
        # Volle <td ...>...</td>-Tags (nicht nur der Inhalt) -- die Ampel-
        # Tönung steckt im style-Attribut des <td>, nicht im Text.
        cells = re.findall(r"<td[^>]*>.*?</td>", rows[0], re.S)
        assert len(cells) > idx, f"Zu wenige Zellen ({len(cells)}) für Index {idx}: {cells!r}"
        return cells[idx]
    raise AssertionError(f"Keine Stundentabelle (Kopf 'Zeit') gefunden: {html[:1500]!r}")


@pytest.mark.parametrize(
    "level,expected_word,expected_bg",
    [
        (ThunderLevel.LOW, "leicht", "#fbeeb8"),
        (ThunderLevel.MED, "mittel", "#fad6b8"),
        (ThunderLevel.HIGH, "hoch", "#f6c5bf"),
    ],
    ids=["low", "med", "high"],
)
def test_ac7_ortsvergleich_unveraendertes_label_und_ampel(level, expected_word, expected_bg):
    """GIVEN eine Ortsvergleich-Mail mit den Stufen leicht/mittel/hoch
    WHEN sie gerendert wird
    THEN zeigt sie exakt dieselben Wörter und dieselbe Ampel-Einstufung wie
    vor dieser Änderung -- kein sichtbarer Unterschied zum bisherigen
    Ortsvergleich (Spec: 'im Ortsvergleich gibt es keinen Fehler', diese
    Prüfung ist ein Regressionsschutz, kein Bugreproduktions-Test).
    """
    from output.renderers.email.compare_html import render_compare_html

    result = _compare_location(level)
    html = render_compare_html(result)
    cell = _compare_thunder_cell(html)
    assert expected_word in cell, (
        f"AC-7: Stufe {level!r} muss weiterhin das Wort {expected_word!r} "
        f"zeigen. Zelle: {cell!r}"
    )
    assert expected_bg in cell, (
        f"AC-7: Stufe {level!r} muss weiterhin mit {expected_bg!r} getönt "
        f"sein. Zelle: {cell!r}"
    )
