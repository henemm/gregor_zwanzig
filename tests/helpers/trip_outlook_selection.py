"""Gemeinsame Bausteine fuer die Trip-Ausblick-Spaltenauswahl (#1720 S1).

SPEC: docs/specs/modules/feat_1720_s1_trip_ausblick_metriken.md

Ein Helfer statt je Testdatei eigener Fixture-Bauer: die AC-1-Referenz
(aufgezeichnet VOR der Lieferung) und die Wirkort-Tests muessen DIESELBEN
Eingabedaten verwenden, sonst vergleicht der Bestandsschutz zwei Welten.

🔴 Prueforts-Regel: ``render_trip_mail()`` treibt ``render_email()`` -- den
echten Aufrufpfad inkl. ``email/html.py:1357`` und ``email/plain.py:338``.
``tests/tdd/test_trip_outlook_parity.py`` ruft ``render_outlook_table()``
direkt auf und durchlaeuft diese Stellen nie.

Kein Mock-Framework, kein Netz.
"""
from __future__ import annotations

import contextlib
import dataclasses
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

# Pfadregel #1409: Pruefling relativ zur eigenen Datei aufloesen -- sonst
# pruefte ein Worktree-Lauf die unveraenderte Hauptrepo-Kopie.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "src") not in sys.path:  # erlaubt `python -m tests.helpers...`
    sys.path.insert(0, str(REPO_ROOT / "src"))

REFERENCE_DIR = REPO_ROOT / "tests" / "fixtures" / "trip_outlook_reference"
REFERENCE_TABLE = REFERENCE_DIR / "outlook_table.html"
REFERENCE_LEGEND = REFERENCE_DIR / "outlook_legend.html"
REFERENCE_PLAIN = REFERENCE_DIR / "outlook_block.txt"

TZ = ZoneInfo("Europe/Berlin")
OUTLOOK_EYEBROW = "Ausblick · nächste 3 Tage"
PLAIN_OUTLOOK_HEADING = "Nächste Etappen"

# Legende des Legacy-Zweigs (html.py:1360-1366); #9a978d ist ihr Anker.
_LEGEND_RE = re.compile(
    r'<div style="font-family:[^"]*font-size:9px;color:#9a978d;[^"]*">(.*?)</div>',
    re.DOTALL,
)
_UNSET = object()


@contextlib.contextmanager
def utc_process_tz():
    """Der Zeilenbau (``local_hour``) haengt an der Prozess-Zeitzone; ohne
    Fixierung waere die Referenz von der Shell-TZ abhaengig (vgl.
    test_trip_renderer_characterization.py, Punkt 2)."""
    vorher = os.environ.get("TZ")
    os.environ["TZ"] = "UTC"
    time.tzset()
    try:
        yield
    finally:
        if vorher is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = vorher
        time.tzset()


# Drei Tage mit unterscheidbaren Werten -- bei zwei Elementen kann ein
# Vertauschungs-Fang Zufall sein.
_TAGE = (
    # Wochentag, t_min, t_max, precip, wind, gust, pop, thunder, schnee,
    # confidence, Etappenname, Notiz
    ("Mo", 9.0, 21.0, 2.5, 25.0, 44.0, 55, "MED", 12.0, 82.0,
     "Obstanserseehütte", "Hütte geschlossen"),
    ("Di", 11.0, 19.0, 0.0, 31.0, 52.0, 15, "NONE", 4.0, 61.0,
     "Filmoor-Standschützenhütte", None),
    ("Mi", 6.0, 24.0, 7.1, 18.0, 33.0, 80, "HIGH", 27.0, 44.0,
     "Sillianer Hütte", None),
)


def _points(tag_index: int):
    from app.models import ForecastDataPoint, ThunderLevel

    (_, _, temp_max, precip, wind, gust, pop, thunder, *_) = _TAGE[tag_index]
    return [
        ForecastDataPoint(
            ts=datetime(2026, 7, 12 + tag_index, stunde, 0, tzinfo=timezone.utc),
            t2m_c=temp_max - (14 - stunde) * 0.5, wind10m_kmh=wind,
            wind_direction_deg=270, gust_kmh=gust, precip_1h_mm=precip / 6.0,
            pop_pct=pop, cloud_total_pct=60,
            thunder_level=getattr(ThunderLevel, thunder), visibility_m=9000.0,
        )
        for stunde in range(8, 17)
    ]


def _summary(tag_index: int):
    from app.models import SegmentWeatherSummary, ThunderLevel

    (_, temp_min, temp_max, precip, wind, gust, pop, thunder, schnee,
     confidence, _, _) = _TAGE[tag_index]
    return SegmentWeatherSummary(
        temp_min_c=temp_min, temp_max_c=temp_max,
        temp_avg_c=(temp_min + temp_max) / 2, wind_max_kmh=wind,
        gust_max_kmh=gust, precip_sum_mm=precip, cloud_avg_pct=60,
        humidity_avg_pct=55, thunder_level_max=getattr(ThunderLevel, thunder),
        pop_max_pct=pop, snow_depth_cm=schnee, snow_new_sum_cm=schnee / 4,
        confidence_pct_min=int(confidence), visibility_min_m=9000,
        sunny_hours=4.0, uv_index_max=5.0,
        # RED-Korrektur (#1720 S1, GREEN-Phase): ohne diese Regeln liefert
        # ``aggregate_stage()`` eine Summary aus lauter ``None`` -- es
        # iteriert ausschliesslich ueber ``summaries[0].aggregation_config``
        # (weather_metrics.py:1204). Der Ketten-Test saehe dann in JEDER Zelle
        # "–" und koennte einen Spaltenversatz strukturell nicht mehr sehen.
        # Regeln 1:1 aus dem Erzeuger (weather_metrics.py:468,854), nur fuer
        # die hier gesetzten Felder.
        aggregation_config={
            "temp_min_c": "min", "temp_max_c": "max", "temp_avg_c": "avg",
            "wind_max_kmh": "max", "gust_max_kmh": "max",
            "precip_sum_mm": "sum", "cloud_avg_pct": "avg",
            "humidity_avg_pct": "avg", "thunder_level_max": "max",
            "pop_max_pct": "max", "snow_depth_cm": "max",
            "snow_new_sum_cm": "sum", "confidence_pct_min": "min",
            "visibility_min_m": "min", "uv_index_max": "max",
        },
    )


def tages_summary(index: int, anteile: int = 1):
    """Oeffentlicher Zugriff fuer den Ketten-Test (drei unterscheidbare Tage).

    ``anteile``: auf wie viele Segmente sich die Etappe aufteilt. Die
    SUM-Felder werden entsprechend geteilt -- ``aggregate_stage()`` summiert
    sie ueber die Segmente wieder zusammen (Regel "sum",
    weather_metrics.py:1204ff). Ohne diese Teilung stuende in der Mail der
    doppelte Tageswert, sobald eine Etappe mehr als ein Segment hat (RED-
    Korrektur #1720 S1, GREEN-Phase: gemessen 2 Segmente je Etappe).
    """
    summary = _summary(index % len(_TAGE))
    if anteile <= 1:
        return summary
    return dataclasses.replace(
        summary,
        precip_sum_mm=summary.precip_sum_mm / anteile,
        snow_new_sum_cm=summary.snow_new_sum_cm / anteile,
    )


def outlook_rows(
    metrics: Optional[list[dict]] = None,
    *,
    trip_display_config: object = None,
    report_type: str = "evening",
    day_window_start_hour: Optional[int] = None,
    day_window_end_hour: Optional[int] = None,
    points_override: Optional[dict[int, list]] = None,
    summary_override: Optional[dict[int, object]] = None,
) -> list[dict]:
    """Die drei Ausblick-Zeilen, gebaut wie der Scheduler sie baut.

    RED-Korrektur (#1841, AC-8): ``metrics`` ist NICHT der Parameter, den
    ``trip_report_scheduler.py:2282`` fuellt -- das ist die COMPARE-
    Konvention. Der bisherige Docstring behauptete das Gegenteil. Der
    Zeitplaner reicht stattdessen die UNGEKOLLABIERTE
    ``trip_display_config``/``report_type``/das Tagesfenster durch und
    ueberlaesst ``build_outlook_row`` die Aufloesung (s. dortiger
    Docstring). Ist ``trip_display_config`` gesetzt, geht dieser Helfer
    denselben Weg; ``metrics`` bleibt dann unbenutzt (Vorrangregel in
    ``build_outlook_row``). ``points_override``/``summary_override``
    (Tagesindex -> Wert) spielen Tests eigene Punktreihen/Aggregate ein --
    noetig fuer Geometrien, in denen Gehzeit-Aggregat und Tagesfenster
    auseinanderfallen (#1841 Spec "Fixtur-Geometrie").
    """
    from output.renderers.email.outlook import build_outlook_row

    with utc_process_tz():
        zeilen = [
            build_outlook_row(
                (summary_override or {}).get(i, _summary(i)),
                (points_override or {}).get(i, _points(i)),
                _TAGE[i][0], TZ,
                metrics=metrics if trip_display_config is None else None,
                trip_display_config=trip_display_config,
                report_type=report_type,
                day_window_start_hour=day_window_start_hour,
                day_window_end_hour=day_window_end_hour,
            )
            for i in range(len(_TAGE))
        ]
    for i, zeile in enumerate(zeilen):
        zeile["name"] = _TAGE[i][10]
        if _TAGE[i][11] is not None:
            zeile["note"] = _TAGE[i][11]
    return zeilen


def display_config(*, enabled_ids: Optional[set[str]] = None,
                   leere_grundauswahl: bool = False,
                   report_overrides: Optional[dict[str, dict]] = None,
                   outlook_metrics=_UNSET):
    """``enabled_ids``: Grundauswahl zuschneiden (AC-14/15).
    ``leere_grundauswahl``: ``metrics = []`` (AC-16).
    ``report_overrides``: z.B. ``{"gust": {"evening_enabled": False}}``.
    ``outlook_metrics`` nicht uebergeben = Feld unberuehrt (Altbestand).
    """
    from app.metric_catalog import build_default_display_config

    dc = build_default_display_config()
    if enabled_ids is not None:
        for mc in dc.metrics:
            mc.enabled = mc.metric_id in enabled_ids
    for metric_id, felder in (report_overrides or {}).items():
        for mc in dc.metrics:
            if mc.metric_id == metric_id:
                for name, wert in felder.items():
                    setattr(mc, name, wert)
    if leere_grundauswahl:
        dc.metrics = []
    if outlook_metrics is _UNSET:
        return dc
    return mit_outlook_metrics(dc, outlook_metrics)


def mit_outlook_metrics(dc, outlook_metrics):
    """Setzt die Vorschau-Auswahl -- mit sprechendem RED-Fehler, solange das
    Feld in ``UnifiedWeatherDisplayConfig`` fehlt."""
    try:
        return dataclasses.replace(dc, outlook_metrics=outlook_metrics)
    except TypeError as exc:
        raise AssertionError(
            "UnifiedWeatherDisplayConfig kennt das Feld 'outlook_metrics' noch "
            "nicht (#1720 S1, Spec Source: src/app/models.py:774-807). Ohne "
            "dieses Feld kann eine Vorschau-Auswahl weder gespeichert noch "
            f"gerendert werden.\nUrsprungsfehler: {exc}"
        ) from exc


def _segment_weather():
    from app.models import (
        ForecastMeta, GPXPoint, NormalizedTimeseries, Provider,
        SegmentWeatherData, TripSegment,
    )

    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=46.65, lon=12.85, elevation_m=1400.0),
        end_point=GPXPoint(lat=46.70, lon=12.95, elevation_m=2100.0),
        start_time=datetime(2026, 7, 11, 8, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 11, 14, 0, tzinfo=timezone.utc),
        duration_hours=6.0, distance_km=12.0, ascent_m=700.0, descent_m=120.0,
    )
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="icon_d2",
        run=datetime(2026, 7, 11, 0, 0, tzinfo=timezone.utc),
        grid_res_km=2.2, interp="point_grid",
    )
    return SegmentWeatherData(
        segment=seg, timeseries=NormalizedTimeseries(meta=meta, data=_points(0)),
        aggregated=_summary(0),
        fetched_at=datetime(2026, 7, 11, 6, 0, tzinfo=timezone.utc),
        provider="openmeteo",
    )


def render_trip_mail(dc, rows, *, report_type: str = "evening"):
    """Echter Aufrufpfad: ``TripReportFormatter.format_email()`` -> HTML/
    Klartext-Ausblick.

    🔴 Seit der F001-Nachbesserung MUSS es der Formatter sein, nicht
    ``render_email()`` direkt: die Ausblick-Spalten werden genau dort EINMAL
    aus dem ungekollabierten ``display_config`` aufgeloest (trip_report.py)
    und dem Renderer als Parameter uebergeben. Ein Test, der ``render_email()``
    direkt riefe, muesste die Aufloesung selbst nachbauen -- und pruefte dann
    seine eigene Nachbildung statt des Prueflings.

    Byte-Gleichheit zum bisherigen Weg fuer die drei Ausblick-Teile
    (Tabelle/Legende/Klartext-Block) wurde gemessen, bevor umgestellt wurde --
    die AC-1-Aufzeichnung bleibt unangetastet gueltig.
    """
    from output.renderers.trip_report import TripReportFormatter

    with utc_process_tz():
        report = TripReportFormatter().format_email(
            segments=[_segment_weather()], trip_name="Karnischer Höhenweg",
            report_type=report_type, display_config=dc, tz=TZ,
            multi_day_trend=rows, stage_name="Etappe 3",
        )
    return report.email_html, report.email_plain


# --- Extraktion der Ausblick-Teile aus der fertigen Mail --------------------

def html_outlook_table(html: str) -> Optional[str]:
    anker = html.find(OUTLOOK_EYEBROW)
    if anker == -1:
        return None
    start = html.find("<table", anker)
    ende = html.find("</table>", start) if start != -1 else -1
    return html[start:ende + len("</table>")] if ende != -1 else None


def html_outlook_legend(html: str) -> Optional[str]:
    treffer = _LEGEND_RE.search(html)
    return treffer.group(0) if treffer else None


def _entkerne(zellen: list[str]) -> list[str]:
    return [re.sub(r"<[^>]+>", "", z).strip() for z in zellen]


def html_outlook_headers(html: str) -> list[str]:
    """Spaltenueberschriften der Ausblick-Tabelle, in Reihenfolge."""
    tabelle = html_outlook_table(html)
    kopf = re.search(r"<thead>(.*?)</thead>", tabelle, re.DOTALL) if tabelle else None
    if kopf is None:
        return []
    return _entkerne(re.findall(r"<th[^>]*>(.*?)</th>", kopf.group(1), re.DOTALL))


def html_outlook_body_rows(html: str) -> list[list[str]]:
    """Datenzeilen der Ausblick-Tabelle als Textzellen."""
    tabelle = html_outlook_table(html)
    koerper = re.search(r"<tbody>(.*?)</tbody>", tabelle, re.DOTALL) if tabelle else None
    if koerper is None:
        return []
    return [
        _entkerne(re.findall(r"<td[^>]*>(.*?)</td>", zeile, re.DOTALL))
        for zeile in re.findall(r"<tr>(.*?)</tr>", koerper.group(1), re.DOTALL)
    ]


def plain_outlook_block(plain: str) -> Optional[str]:
    """Klartext-Ausblick-Block (Ueberschrift + Zeilen) oder ``None``."""
    zeilen = plain.splitlines()
    try:
        start = zeilen.index(PLAIN_OUTLOOK_HEADING)
    except ValueError:
        return None
    block = [zeilen[start]]
    for zeile in zeilen[start + 1:]:
        if zeile.strip() == "":
            break
        block.append(zeile)
    return "\n".join(block)


# --- Referenz-Aufzeichnung (AC-1), einmalig VOR der Lieferung ---------------

def record_reference(force: bool = False) -> list[Path]:
    """Zeichnet die AC-1-Referenz aus dem AKTUELLEN Code auf.

    Schreibt ohne ``force`` NICHT ueber eine vorhandene Aufzeichnung: eine
    Referenz, die man bei rotem Test neu erzeugen kann, bewacht nichts.

    #1848 A3: aufgezeichnet wird der FESTE Sieben-Spalten-Zweig -- er gilt
    seither nur noch fuer Touren ganz ohne Grundauswahl (ADR-0050 D4). Der
    Aufruf muss dieselbe Vorbedingung setzen wie die AC-1-Tests
    (``test_trip_outlook_metric_selection._dc_altpfad()``), sonst zeichnete
    er den konfigurierbaren Zweig auf und die Referenz bewachte etwas
    anderes als der Test.
    """
    html, plain = render_trip_mail(display_config(leere_grundauswahl=True),
                                   outlook_rows())
    inhalte = {
        REFERENCE_TABLE: html_outlook_table(html),
        REFERENCE_LEGEND: html_outlook_legend(html),
        REFERENCE_PLAIN: plain_outlook_block(plain),
    }
    # 🔴 ``outlook_legend.html`` traegt bewusst den ALTEN Wortlaut
    # ("N Nacht-Tief"): ``test_ac1_bestandstrip_legende_...`` rechnet daraus
    # das Soll ("N Tagestief") und prueft die AC-8-Korrektur damit gegen eine
    # unabhaengige Quelle. Wer die Legende mit-aufzeichnet, laesst den Test
    # die Korrektur gegen sich selbst pruefen -- er waere danach immer gruen.
    inhalte.pop(REFERENCE_LEGEND, None)
    fehlend = [p.name for p, t in inhalte.items() if not t]
    if fehlend:
        raise RuntimeError(f"Kein Ausblick gerendert fuer: {fehlend} -- "
                           "die Aufzeichnung waere leer und wertlos.")
    REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
    geschrieben = []
    for pfad, text in inhalte.items():
        if pfad.exists() and not force:
            continue
        pfad.write_text(text, encoding="utf-8")
        geschrieben.append(pfad)
    return geschrieben


if __name__ == "__main__":  # pragma: no cover - Aufzeichnungs-Werkzeug
    for pfad in record_reference(force="--force" in sys.argv):
        print(f"aufgezeichnet: {pfad}")
