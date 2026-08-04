"""Spalten-Legende: jedes sichtbare Kuerzel wird in der Mail aufgeloest.

SPEC: docs/specs/modules/fix_1472_spaltenkuerzel_legende.md (AC-1 .. AC-7)
KONTEXT: docs/context/fix-1472-spaltenkuerzel-legende.md (#1472)

ADR-0042 erlaubt englische Kurzformen ("Thdr", "Visib", "Feels") in den
Spaltenkoepfen NUR unter der Bedingung, dass ihre Aufloesung auffindbar ist.
In der Mail — der Stelle, an der unterwegs gelesen wird — ist diese Bedingung
heute unerfuellt: unter der Stundentabelle steht ausschliesslich die
Einheiten-Zeile ("Einheiten: Temp, Feels °C · Wind km/h").

RED-Phase: eine zweite Legenden-Zeile "Spalten: Temp = Temperatur · ..."
existiert in KEINER der vier Ausgaben (Trip HTML, Trip Klartext, Vergleich
HTML, Vergleich Klartext). Der Vergleichs-Klartext hat ueberdies bis heute gar
keine Legende — dort entstehen BEIDE Zeilen neu. Alle Tests dieser Datei sind
deshalb rot; sie scheitern mit "keine 'Spalten:'-Legendenzeile gefunden".

Test-Politik (CLAUDE.md, Kern-Schicht): kein Netz, kein Versand, kein Mock,
kein Dateiinhalt-Check am Quelltext. Geprueft wird ausschliesslich die
GERENDERTE Ausgabe der echten Renderer, gespeist aus echten DTOs
(ForecastDataPoint / ComparisonResult / SegmentWeatherData) und dem echten
Metrik-Register.
"""
from __future__ import annotations

import dataclasses
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from app.metric_catalog import _METRICS_BY_COL_KEY, _METRICS_BY_ID, get_metric
from app.models import (
    ForecastDataPoint, ForecastMeta, GPXPoint, MetricConfig,
    NormalizedTimeseries, Provider, SegmentWeatherData,
    SegmentWeatherSummary, ThunderLevel, TripSegment,
    UnifiedWeatherDisplayConfig,
)
from app.user import ComparisonResult, LocationResult, SavedLocation
from output.renderers.comparison import render_compare_email
from output.renderers.email.helpers import dp_to_row

TZ = ZoneInfo("Europe/Berlin")

COLUMN_PREFIX = "Spalten:"
UNITS_PREFIX = "Einheiten:"

# Dieselbe Groessen-Auswahl auf beiden Seiten, in derselben sichtbaren
# Reihenfolge (AC-7). "wind10m_kmh"/"wind" ist bewusst dabei: Kuerzel und Name
# sind identisch ("Wind"), das Paar muss daher aus der Spalten-Zeile fallen,
# waehrend es in der Einheiten-Zeile stehen bleibt (AC-4).
COMPARE_SELECTION = [
    "t2m_c", "wind_chill_c", "dewpoint_c",
    "wind10m_kmh", "thunder_level", "visibility_m",
]
TRIP_SELECTION = [
    "temperature", "wind_chill", "dewpoint",
    "wind", "thunder", "visibility",
]

# Erwartete Paare fuer die gemeinsame Auswahl oben — "Wind" fehlt bewusst.
EXPECTED_PAIRS = [
    ("Temp", "Temperatur"),
    ("Feels", "Gefühlte Temperatur"),
    ("Dew", "Taupunkt"),
    ("Thdr", "Gewitter"),
    ("Visib", "Sichtweite"),
]


# ---------------------------------------------------------------------------
# Auswertung der gerenderten Ausgabe (kein Quelltext-Grep)
# ---------------------------------------------------------------------------

def _as_text(rendered: str, *, is_html: bool) -> str:
    if not is_html:
        return rendered
    return BeautifulSoup(rendered, "html.parser").get_text("\n")


def _legend_line(rendered: str, prefix: str, *, is_html: bool, where: str) -> str:
    """Text hinter `prefix` aus der gerenderten Ausgabe. Fehlt die Zeile,
    scheitert der Test mit dem tatsaechlich vorhandenen Legenden-Umfeld."""
    text = _as_text(rendered, is_html=is_html)
    for raw in text.splitlines():
        line = raw.strip()
        if prefix in line:
            return line.split(prefix, 1)[1].strip()
    vorhanden = [
        raw.strip() for raw in text.splitlines()
        if UNITS_PREFIX in raw or COLUMN_PREFIX in raw
    ]
    raise AssertionError(
        f"{where}: keine {prefix!r}-Legendenzeile in der gerenderten Ausgabe. "
        f"Gefundene Legendenzeilen: {vorhanden!r}"
    )


def _column_pairs(rendered: str, *, is_html: bool, where: str) -> list[tuple[str, str]]:
    """(Kuerzel, Name)-Paare aus der 'Spalten:'-Zeile der gerenderten Ausgabe."""
    body = _legend_line(rendered, COLUMN_PREFIX, is_html=is_html, where=where)
    pairs: list[tuple[str, str]] = []
    for chunk in body.split("·"):
        chunk = chunk.strip()
        if not chunk:
            continue
        assert "=" in chunk, (
            f"{where}: Legenden-Eintrag {chunk!r} hat nicht die Form "
            f"'<Kuerzel> = <ausgeschriebener Name>'"
        )
        short, long = chunk.split("=", 1)
        pairs.append((short.strip(), long.strip()))
    assert pairs, (
        f"{where}: die {COLUMN_PREFIX!r}-Zeile nennt kein einziges Paar: {body!r}"
    )
    return pairs


def _shorts(pairs: list[tuple[str, str]]) -> list[str]:
    return [short for short, _ in pairs]


# ---------------------------------------------------------------------------
# Fixtures Ortsvergleich (echte DTOs, drei Orte)
# ---------------------------------------------------------------------------

def _compare_dp(hour: int) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(2026, 7, 13, hour, 0),
        t2m_c=22.0 + hour, wind_chill_c=20.0 + hour, dewpoint_c=12.0,
        wind10m_kmh=8.0, thunder_level=ThunderLevel.MED, visibility_m=8000,
    )


def _comparison_result() -> ComparisonResult:
    def _loc(idx: int, name: str) -> LocationResult:
        return LocationResult(
            location=SavedLocation(
                id=name.lower(), name=name,
                lat=43.1 + idx * 0.1, lon=5.9, elevation_m=20,
            ),
            score=70 - idx, temp_max=31.0, wind_max=18.0,
            sunny_hours=7.0, cloud_avg=30, official_alerts=[],
            hourly_data=[_compare_dp(7), _compare_dp(12), _compare_dp(16)],
        )

    return ComparisonResult(
        locations=[_loc(0, "Toulon"), _loc(1, "Hyeres"), _loc(2, "Nizza")],
        time_window=(7, 16),
        target_date=date(2026, 7, 13),
        created_at=datetime(2026, 7, 13, 4, 1),
    )


def _render_compare(hourly_metrics: list[str]) -> tuple[str, str]:
    """(html_body, text_body) — beide Teile derselben Vergleichs-Mail."""
    return render_compare_email(_comparison_result(), hourly_metrics=hourly_metrics)


# ---------------------------------------------------------------------------
# Fixtures Trip-Briefing (echte Segmente, Zeilen ueber den echten dp_to_row)
# ---------------------------------------------------------------------------

def _trip_dp(hour: int) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(2026, 7, 11, hour, 0, tzinfo=timezone.utc),
        t2m_c=20.0, wind_chill_c=18.0, dewpoint_c=12.0,
        wind10m_kmh=11.0, thunder_level=ThunderLevel.MED, visibility_m=8000,
    )


def _trip_segments() -> list[SegmentWeatherData]:
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.13, lon=9.13, elevation_m=400.0),
        end_point=GPXPoint(lat=42.10, lon=9.18, elevation_m=1200.0),
        start_time=datetime(2026, 7, 11, 6, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 11, 10, 0, tzinfo=timezone.utc),
        duration_hours=4.0, distance_km=9.3, ascent_m=800.0, descent_m=0.0,
    )
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="demo", grid_res_km=1.3,
        run=datetime(2026, 7, 11, 0, 0, tzinfo=timezone.utc),
    )
    ts = NormalizedTimeseries(meta=meta, data=[_trip_dp(6), _trip_dp(7), _trip_dp(8)])
    agg = SegmentWeatherSummary(
        temp_min_c=18.0, temp_max_c=20.0, temp_avg_c=19.0,
        wind_max_kmh=11.0, gust_max_kmh=20.0, precip_sum_mm=0.0,
        cloud_avg_pct=60, humidity_avg_pct=55,
        thunder_level_max=ThunderLevel.MED,
    )
    return [SegmentWeatherData(
        segment=seg, timeseries=ts, aggregated=agg,
        fetched_at=datetime.now(timezone.utc), provider="demo",
    )]


def _trip_dc(metric_ids: list[str]) -> UnifiedWeatherDisplayConfig:
    return UnifiedWeatherDisplayConfig(
        trip_id="tdd-1472",
        metrics=[MetricConfig(metric_id=m, enabled=True) for m in metric_ids],
    )


def _trip_params(metric_ids: list[str]) -> dict:
    dc = _trip_dc(metric_ids)
    rows = [dp_to_row(dp, dc, tz=TZ) for dp in _trip_dp_series()]
    return dict(
        segments=_trip_segments(), seg_tables=[rows], trip_name="GR20 Test",
        report_type="morning", dc=dc, night_rows=[], thunder_forecast=None,
        changes=None, stage_name=None, stage_stats=None, multi_day_trend=None,
        compact_summary=None, tz=TZ, friendly_keys=set(),
    )


def _trip_dp_series() -> list[ForecastDataPoint]:
    return [_trip_dp(6), _trip_dp(7), _trip_dp(8)]


def _render_trip_html(metric_ids: list[str]) -> str:
    from output.renderers.email.html import render_html
    return render_html(**_trip_params(metric_ids))


def _render_trip_plain(metric_ids: list[str]) -> str:
    from output.renderers.email.plain import render_plain
    return render_plain(**_trip_params(metric_ids))


# ===========================================================================
# AC-1 — Vergleich HTML: die sichtbaren Kuerzel werden aufgeloest
# ===========================================================================

def test_ac1_compare_html_resolves_visible_abbreviations():
    """AC-1: Given ein Ortsvergleich mit sichtbaren Stunden-Spalten Thdr und
    Visib / When die HTML-Vergleichsmail gerendert wird / Then enthaelt sie die
    Zeile 'Spalten: Thdr = Gewitter · Visib = Sichtweite' unter der
    Einheiten-Zeile."""
    html, _plain = _render_compare(["thunder_level", "visibility_m"])
    pairs = _column_pairs(html, is_html=True, where="Vergleich HTML")
    assert pairs == [("Thdr", "Gewitter"), ("Visib", "Sichtweite")], (
        f"AC-1: erwartete Aufloesung Thdr/Visib, gerendert wurde: {pairs!r}"
    )


def test_ac1_compare_html_column_legend_stands_below_units_legend():
    """AC-1 (Platzierung): die Spalten-Zeile steht UNTER der Einheiten-Zeile,
    nicht davor und nicht an einer anderen Stelle der Mail."""
    html, _plain = _render_compare(["thunder_level", "visibility_m"])
    lines = [ln.strip() for ln in _as_text(html, is_html=True).splitlines()]
    units_idx = [i for i, ln in enumerate(lines) if UNITS_PREFIX in ln]
    column_idx = [i for i, ln in enumerate(lines) if COLUMN_PREFIX in ln]
    assert units_idx, f"AC-1: keine Einheiten-Zeile im Vergleichs-HTML: {lines[-20:]!r}"
    assert column_idx, (
        f"AC-1: keine Spalten-Zeile im Vergleichs-HTML — die Einheiten-Zeile "
        f"steht allein da: {[lines[i] for i in units_idx]!r}"
    )
    assert min(column_idx) > min(units_idx), (
        f"AC-1: die Spalten-Zeile (Zeile {min(column_idx)}) steht nicht unter "
        f"der Einheiten-Zeile (Zeile {min(units_idx)})"
    )


# ===========================================================================
# AC-2 — Vergleich Klartext: beide Zeilen, deckungsgleich mit dem HTML-Teil
# ===========================================================================

def test_ac2_compare_plaintext_carries_both_legend_lines():
    """AC-2: Given dieselbe Konstellation wie AC-1 / When der Klartext-Teil
    derselben Mail gerendert wird / Then enthaelt er dieselben zwei Zeilen
    (Einheiten und Spalten) — heute existiert dort noch gar keine Legende."""
    html, plain = _render_compare(["thunder_level", "visibility_m"])

    units_plain = _legend_line(plain, UNITS_PREFIX, is_html=False,
                               where="Vergleich Klartext")
    units_html = _legend_line(html, UNITS_PREFIX, is_html=True,
                              where="Vergleich HTML")
    assert units_plain == units_html, (
        f"AC-2: Einheiten-Zeile laeuft zwischen den Mail-Teilen auseinander — "
        f"Klartext {units_plain!r} vs. HTML {units_html!r}"
    )

    pairs_plain = _column_pairs(plain, is_html=False, where="Vergleich Klartext")
    pairs_html = _column_pairs(html, is_html=True, where="Vergleich HTML")
    assert pairs_plain == pairs_html, (
        f"AC-2: Spalten-Zeile laeuft zwischen den Mail-Teilen auseinander — "
        f"Klartext {pairs_plain!r} vs. HTML {pairs_html!r}"
    )
    assert pairs_plain == [("Thdr", "Gewitter"), ("Visib", "Sichtweite")], (
        f"AC-2: unerwartete Paare im Klartext-Teil: {pairs_plain!r}"
    )


# ===========================================================================
# AC-3 — Trip-Briefing: HTML und Klartext nennen dieselbe Aufloesung
# ===========================================================================

def test_ac3_trip_html_and_plain_resolve_feels_and_dew():
    """AC-3: Given ein Trip-Briefing mit sichtbaren Spalten Feels und Dew /
    When HTML und Klartext gerendert werden / Then enthalten beide dieselbe
    Zeile 'Spalten: Feels = Gefühlte Temperatur · Dew = Taupunkt'."""
    selection = ["wind_chill", "dewpoint"]
    erwartet = [("Feels", "Gefühlte Temperatur"), ("Dew", "Taupunkt")]

    pairs_html = _column_pairs(_render_trip_html(selection), is_html=True,
                               where="Trip HTML")
    pairs_plain = _column_pairs(_render_trip_plain(selection), is_html=False,
                                where="Trip Klartext")
    assert pairs_html == erwartet, f"AC-3 (HTML): {pairs_html!r}"
    assert pairs_plain == erwartet, f"AC-3 (Klartext): {pairs_plain!r}"


# ===========================================================================
# AC-4 — identisches Paar faellt weg (Wind), bleibt aber bei den Einheiten
# ===========================================================================

def test_ac4_identical_pair_wind_absent_from_column_legend_trip():
    """AC-4 (Trip): Given eine Auswahl, in der Wind sichtbar ist (Kuerzel Wind,
    Name Wind) / When die Legende gerendert wird / Then erscheint Wind NICHT im
    Spalten-Teil — waehrend die Einheiten-Zeile ihn unveraendert nennt."""
    selection = ["temperature", "wind"]
    for pfad, rendered, is_html in (
        ("Trip HTML", _render_trip_html(selection), True),
        ("Trip Klartext", _render_trip_plain(selection), False),
    ):
        pairs = _column_pairs(rendered, is_html=is_html, where=pfad)
        assert ("Temp", "Temperatur") in pairs, (
            f"AC-4 ({pfad}): Temp wird nicht aufgeloest: {pairs!r}"
        )
        assert "Wind" not in _shorts(pairs), (
            f"AC-4 ({pfad}): Wind steht in der Spalten-Zeile, obwohl Kuerzel "
            f"und Name identisch sind: {pairs!r}"
        )
        units = _legend_line(rendered, UNITS_PREFIX, is_html=is_html, where=pfad)
        assert "Wind" in units, (
            f"AC-4 ({pfad}): die Einheiten-Zeile darf sich nicht aendern, "
            f"nennt Wind aber nicht mehr: {units!r}"
        )


def test_ac4_identical_pair_wind_absent_from_column_legend_compare():
    """AC-4 (Ortsvergleich): dieselbe Regel auf dem zweiten Weg
    (derive_row_labels statt visible_cols)."""
    html, plain = _render_compare(["t2m_c", "wind10m_kmh"])
    for pfad, rendered, is_html in (
        ("Vergleich HTML", html, True),
        ("Vergleich Klartext", plain, False),
    ):
        pairs = _column_pairs(rendered, is_html=is_html, where=pfad)
        assert ("Temp", "Temperatur") in pairs, (
            f"AC-4 ({pfad}): Temp wird nicht aufgeloest: {pairs!r}"
        )
        assert "Wind" not in _shorts(pairs), (
            f"AC-4 ({pfad}): Wind steht in der Spalten-Zeile: {pairs!r}"
        )
        units = _legend_line(rendered, UNITS_PREFIX, is_html=is_html, where=pfad)
        assert "Wind" in units, (
            f"AC-4 ({pfad}): Einheiten-Zeile nennt Wind nicht mehr: {units!r}"
        )


# ===========================================================================
# AC-5 — Wirkungsnachweis: die Legende folgt der Auswahl, nicht dem Katalog
# ===========================================================================

def test_ac5_compare_legend_follows_metric_selection():
    """AC-5: Given zwei Renderlaeufe derselben Mail mit unterschiedlicher
    Metrik-Auswahl (A: Thdr sichtbar, B: Thdr abgewaehlt) / When beide
    gerendert werden / Then enthaelt nur Lauf A die Aufloesung
    'Thdr = Gewitter'; in Lauf B fehlt sie vollstaendig, obwohl Thdr weiterhin
    im zentralen Katalog steht."""
    html_a, plain_a = _render_compare(["t2m_c", "thunder_level", "visibility_m"])
    html_b, plain_b = _render_compare(["t2m_c", "visibility_m"])

    assert get_metric("thunder").col_label == "Thdr", (
        "AC-5-Voraussetzung: Thdr muss im Katalog stehen — sonst beweist der "
        "Vergleich nichts ueber die Auswahl."
    )

    for pfad, a, b, is_html in (
        ("Vergleich HTML", html_a, html_b, True),
        ("Vergleich Klartext", plain_a, plain_b, False),
    ):
        pairs_a = _column_pairs(a, is_html=is_html, where=f"{pfad} Lauf A")
        pairs_b = _column_pairs(b, is_html=is_html, where=f"{pfad} Lauf B")
        assert ("Thdr", "Gewitter") in pairs_a, (
            f"AC-5 ({pfad}): Lauf A hat Thdr sichtbar, loest es aber nicht "
            f"auf: {pairs_a!r}"
        )
        assert "Thdr" not in _shorts(pairs_b), (
            f"AC-5 ({pfad}): Lauf B hat Thdr abgewaehlt, die Legende nennt es "
            f"trotzdem: {pairs_b!r}"
        )
        assert pairs_a != pairs_b, (
            f"AC-5 ({pfad}): beide Laeufe liefern dieselbe Legende {pairs_a!r} "
            f"— die Auswahl wirkt nicht."
        )


def test_ac5_trip_legend_follows_metric_selection():
    """AC-5 (Trip-Weg): dieselbe Wirkung auf dem zweiten Pfad."""
    a = _render_trip_plain(["temperature", "thunder", "visibility"])
    b = _render_trip_plain(["temperature", "visibility"])
    pairs_a = _column_pairs(a, is_html=False, where="Trip Klartext Lauf A")
    pairs_b = _column_pairs(b, is_html=False, where="Trip Klartext Lauf B")
    assert ("Thdr", "Gewitter") in pairs_a, f"AC-5 (Trip) Lauf A: {pairs_a!r}"
    assert "Thdr" not in _shorts(pairs_b), f"AC-5 (Trip) Lauf B: {pairs_b!r}"
    assert pairs_a != pairs_b, (
        f"AC-5 (Trip): beide Laeufe liefern dieselbe Legende {pairs_a!r}"
    )


# ===========================================================================
# AC-6 — keine zweite Namensquelle: das Register regiert die Legende
# ===========================================================================

def _patch_label_de(monkeypatch, metric_id: str, neuer_name: str) -> None:
    """Einen echten Register-Eintrag zur Laufzeit ersetzen (reale
    MetricDefinition via dataclasses.replace, kein Mock). Beide Register-
    Indizes bekommen DASSELBE Objekt — es bleibt eine Quelle."""
    original = _METRICS_BY_ID[metric_id]
    ersetzt = dataclasses.replace(original, label_de=neuer_name)
    monkeypatch.setitem(_METRICS_BY_ID, metric_id, ersetzt)
    monkeypatch.setitem(_METRICS_BY_COL_KEY, original.col_key, ersetzt)


def test_ac6_column_legend_follows_catalog_label_change(monkeypatch):
    """AC-6: Given ein Register-Eintrag mit geaendertem label_de
    ('Gewitter' -> 'Gewittergefahr') / When dieselbe Mail erneut gerendert wird
    / Then aendert sich die Spalten-Zeile entsprechend — ohne dass eine zweite,
    separat gepflegte Namensliste angefasst wird."""
    # Ausgangslage vor dem Eingriff — beweist, dass sich der Wert bewegt.
    html_vorher, plain_vorher = _render_compare(COMPARE_SELECTION)
    vorher = dict(_column_pairs(html_vorher, is_html=True, where="Vergleich HTML (vorher)"))
    assert vorher.get("Thdr") == "Gewitter", (
        f"AC-6-Ausgangslage: Thdr wird nicht als 'Gewitter' aufgeloest: {vorher!r}"
    )
    assert dict(_column_pairs(plain_vorher, is_html=False,
                              where="Vergleich Klartext (vorher)")).get("Thdr") == "Gewitter"

    _patch_label_de(monkeypatch, "thunder", "Gewittergefahr")

    html_nachher, plain_nachher = _render_compare(COMPARE_SELECTION)
    ausgaben = (
        ("Vergleich HTML", html_nachher, True),
        ("Vergleich Klartext", plain_nachher, False),
        ("Trip HTML", _render_trip_html(TRIP_SELECTION), True),
        ("Trip Klartext", _render_trip_plain(TRIP_SELECTION), False),
    )
    geprueft = 0
    for pfad, rendered, is_html in ausgaben:
        pairs = dict(_column_pairs(rendered, is_html=is_html, where=pfad))
        assert pairs.get("Thdr") == "Gewittergefahr", (
            f"AC-6 ({pfad}): der geaenderte Registername schlaegt nicht durch — "
            f"Thdr wird als {pairs.get('Thdr')!r} aufgeloest. Das deutet auf "
            f"eine zweite, separat gepflegte Namensquelle hin."
        )
        geprueft += 1
    assert geprueft == 4, f"AC-6: nur {geprueft} von 4 Ausgaben geprueft"


# ===========================================================================
# AC-7 — keine Drift: alle vier Ausgaben nennen dieselben Paare
# ===========================================================================

def test_ac7_all_four_outputs_name_identical_pairs():
    """AC-7: Given dieselbe Metrik-Auswahl in allen vier Ausgabestellen /
    When alle vier gerendert werden / Then nennen alle vier exakt dieselben
    Kuerzel-Name-Paare in derselben Reihenfolge."""
    compare_html, compare_plain = _render_compare(COMPARE_SELECTION)
    ausgaben = {
        "Trip HTML": _column_pairs(_render_trip_html(TRIP_SELECTION),
                                   is_html=True, where="Trip HTML"),
        "Trip Klartext": _column_pairs(_render_trip_plain(TRIP_SELECTION),
                                       is_html=False, where="Trip Klartext"),
        "Vergleich HTML": _column_pairs(compare_html, is_html=True,
                                        where="Vergleich HTML"),
        "Vergleich Klartext": _column_pairs(compare_plain, is_html=False,
                                            where="Vergleich Klartext"),
    }
    assert len(ausgaben) == 4, "AC-7 prueft vier Ausgabestellen"

    namen = list(ausgaben)
    for i, links in enumerate(namen):
        for rechts in namen[i + 1:]:
            assert ausgaben[links] == ausgaben[rechts], (
                f"AC-7: {links} und {rechts} driften auseinander — "
                f"{ausgaben[links]!r} vs. {ausgaben[rechts]!r}"
            )

    assert ausgaben["Trip HTML"] == EXPECTED_PAIRS, (
        f"AC-7: die gemeinsame Legende weicht von der erwarteten Aufloesung "
        f"ab (Wind faellt als identisches Paar weg): {ausgaben['Trip HTML']!r}"
    )
