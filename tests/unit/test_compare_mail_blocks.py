"""
Ortsvergleichs-Mail (HTML + Klartext + Kanaele) nach dem Rueckbau des
Ort-Zusammenfassungsblocks (#1300, Rueckbau von #1278).

Kern-Schicht, deterministisch: keine Mocks, kein Netz, kein patch(). Alle
Wetterdaten sind echte ``ForecastDataPoint``-Objekte; Tages-Aggregate kommen
vom echten ``services.weather_metrics.summarize_points`` (kein selbst
ausgedachter Erwartungswert).

SPEC: docs/specs/modules/rework_1300_compare_summary_block_removal.md

Diese Datei ist der verhaltensbenannte Nachfolger der Teile von
``test_compare_location_summary.py``, die NICHT das entfernte Verhalten
pruefen:

- AC-1/AC-2/AC-6: der Zusammenfassungsblock (HTML+Klartext) ist weg
  (RED bis zur Implementierung).
- AC-3: Regressionsschutz -- ``_daily_summary``/``summaries`` speisen weiter
  die MATRIX (5 Metriken aus #1285). Ein Rueckbau, der diese Live-Ableitung
  mitreisst, MUSS an diesem Test scheitern (bleibt GRUEN vor und nach #1300).
- AC-5: Telegram/SMS riefen ``render_comparison_text`` nie auf -- ihre
  Ausgabe ist vom Rueckbau unberuehrt (bleibt GRUEN).

``test_trip_summary_text_unchanged_byte_identical`` (AC-4) zieht in eine
eigene Datei um: ``tests/unit/test_trip_summary_text.py`` (Begruendung dort).
"""
from __future__ import annotations

import re
from datetime import date, datetime, timezone

from app.models import (
    ForecastDataPoint, ForecastMeta, NormalizedTimeseries, Provider,
    ThunderLevel,
)
from app.user import ComparisonResult, LocationResult, SavedLocation
from output.renderers.compare_metric_ids import resolve_enabled_metrics
from output.renderers.comparison import (
    render_compare_email, render_comparison_text, render_compare_sms,
    render_compare_telegram,
)
from output.renderers.email.compare_html import render_compare_html
from services.report_config_resolver import resolve_compare_render_options
from services.weather_metrics import WeatherMetricsService, summarize_points

TARGET_DATE = date(2026, 7, 8)

# Sentence-Muster des entfernten Blocks: "<Ortsname>: <min>–<max>°C" (en-dash
# Temperaturspanne, wortgleich zum PO-beanstandeten Beispiel in der Spec).
_SUMMARY_SENTENCE_RE = r"{name}: \d+–\d+°C"


# ---------------------------------------------------------------------------
# Fixtures (echte Objekte, deterministisch -- Wetterlage 1:1 aus
# test_compare_location_summary.py uebernommen: erzeugt fuer jede geprueften
# Groesse ein unterscheidbares, per Hand nachvollziehbares Ergebnis).
# ---------------------------------------------------------------------------

def _dp(hour: int, **overrides) -> ForecastDataPoint:
    rain = 1.0 if 13 <= hour <= 15 else 0.0
    defaults = dict(
        ts=datetime(2026, 7, 8, hour, 0, tzinfo=timezone.utc),
        t2m_c=float(8 + (hour - 9)),
        wind10m_kmh=20.0,
        wind_direction_deg=270,
        gust_kmh=25.0,
        precip_1h_mm=rain,
        cloud_total_pct=50,
        thunder_level=ThunderLevel.MED if hour in (13, 14) else ThunderLevel.NONE,
        pop_pct=70 if 13 <= hour <= 15 else 20,
        humidity_pct=65,
        uv_index=6.0 if hour == 12 else 3.0,
        visibility_m=3000 if 13 <= hour <= 15 else 20000,
        wind_chill_c=float(6 + (hour - 9)),
    )
    defaults.update(overrides)
    return ForecastDataPoint(**defaults)


def _hourly() -> list[ForecastDataPoint]:
    return [_dp(h) for h in range(9, 18)]


def _timeseries(hourly: list[ForecastDataPoint]) -> NormalizedTimeseries:
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="test",
        run=datetime(2026, 7, 8, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.0, interp="point_grid",
    )
    return NormalizedTimeseries(meta=meta, data=hourly)


def _saved_location(name: str) -> SavedLocation:
    return SavedLocation(
        id=re.sub(r"\W+", "_", name.lower()), name=name,
        lat=39.76, lon=2.71, elevation_m=200,
    )


def _location_result(name: str, hourly: list[ForecastDataPoint]) -> LocationResult:
    """LocationResult nur mit den Feldern, die es VOR #1285 schon gab
    (temp_min/temp_max/wind_max/gust_max/cloud_avg/sunny_hours). Die fuenf
    #1285-Felder (precip_sum_mm/pop_max_pct/thunder_level_max/uv_index_max/
    visibility_min_m) bleiben bewusst ungesetzt (None) -- genau das ist das
    ``Given`` von AC-3: die Matrix muss sie LIVE aus ``hourly_data``
    ableiten, kein Engine-Lauf hat sie vorberechnet."""
    s = WeatherMetricsService().compute_basis_metrics(_timeseries(hourly))
    return LocationResult(
        location=_saved_location(name),
        score=50,
        temp_min=s.temp_min_c, temp_max=s.temp_max_c,
        wind_max=s.wind_max_kmh, gust_max=s.gust_max_kmh,
        cloud_avg=s.cloud_avg_pct, sunny_hours=4,
        hourly_data=hourly,
    )


def _comparison_result(locations: list[LocationResult]) -> ComparisonResult:
    return ComparisonResult(
        locations=locations, time_window=(0, 23), target_date=TARGET_DATE,
        created_at=datetime(2026, 7, 8, 4, 1),
    )


# ---------------------------------------------------------------------------
# Matrix-Region-Helfer (fuer AC-3): isoliert die UEBERSICHTS-Tabelle
# (min-width:760px) von der/den Stundentabelle(n) darunter -- letztere tragen
# diese CSS-Angabe nicht (compare_html.py:472 vs. :621).
# ---------------------------------------------------------------------------

def _matrix_region(html: str) -> str:
    start = html.index("min-width:760px")
    marker = "</tbody></table>"
    end = html.index(marker, start) + len(marker)
    return html[start:end]


def _cell_value_for_label(region: str, label: str) -> str:
    """Text der (einzigen) Werte-Zelle in der Matrix-Zeile mit ``label`` --
    sucht nur nach dem Label-Text gefolgt vom naechsten ``<td>``, robust
    gegen Style-Details (kein Snapshot der HTML-Struktur)."""
    row_match = re.search(rf">{re.escape(label)}<", region)
    assert row_match, f"Matrix-Zeile {label!r} nicht gefunden. Region: {region!r}"
    tail = region[row_match.end():]
    row_tail = tail[: tail.index("</tr>")]
    cell_match = re.search(r"<td[^>]*>([^<]*)</td>", row_tail)
    assert cell_match, f"Keine Werte-Zelle fuer {label!r} gefunden: {row_tail!r}"
    return cell_match.group(1)


# ===========================================================================
# AC-1 -- HTML: kein Zusammenfassungssatz mehr im ganzen Dokument
# ===========================================================================

def test_html_no_location_summary_sentence_anywhere_in_document():
    """AC-1: Vergleichs-Mail (HTML) mit mehreren Orten mit Wetterdaten --
    kein "Ortsname: 22-31C, ..."-Muster mehr im gesamten Dokument.

    RED bis zur Implementierung: heute (#1278/cb9918b0) rendert
    ``_render_summary_block`` genau diesen Satz zwischen Matrix und
    Stundenverlauf.
    """
    hourly = _hourly()
    result = _comparison_result([
        _location_result("Andermatt", hourly),
        _location_result("Zermatt", hourly),
    ])
    enabled = resolve_enabled_metrics(["temp_max_c", "precip_sum_mm"])

    html = render_compare_html(result, enabled_metrics=enabled)

    for name in ("Andermatt", "Zermatt"):
        assert not re.search(_SUMMARY_SENTENCE_RE.format(name=re.escape(name)), html), (
            f"Zusammenfassungssatz fuer {name!r} noch im HTML-Dokument -- "
            "der Block haette mit #1300 (PO-Entscheid 2026-07-17, "
            "'kein Mehrwert') vollstaendig entfernt sein muessen."
        )


# ===========================================================================
# AC-2 -- Klartext: kein Zusammenfassungssatz + keine doppelte Leerzeile
# ===========================================================================

def test_plaintext_no_summary_sentence_and_no_double_blank_line_before_hourly():
    """AC-2: Klartext-Fassung (``text_body`` derselben multipart-Mail) --
    zwischen Orts-Uebersicht und "STUNDENVERLAUF" weder Zusammenfassungssatz
    noch doppelte Leerzeile als Rueckstand.

    Der geloeschte Block (comparison.py:165-172) endete auf
    ``lines.append("")``; davor steht bereits eines aus der Orts-Schleife
    (:162). Wird beim Rueckbau nur der Bloecktext, aber nicht das zweite
    ``lines.append("")`` entfernt, bleibt eine Leerzeile zuviel stehen
    (RISIKO 4 im Kontext-Dokument). RED bis zur Implementierung wegen des
    Satz-Musters; die Leerzeilen-Assertion ist der Regressionsschutz fuer
    genau diese Falle.
    """
    hourly = _hourly()
    result = _comparison_result([
        _location_result("Andermatt", hourly),
        _location_result("Zermatt", hourly),
    ])
    enabled = resolve_enabled_metrics(["temp_max_c", "precip_sum_mm"])

    text = render_comparison_text(result, enabled_metrics=enabled)

    assert "STUNDENVERLAUF" in text, (
        "Vorbedingung verletzt: kein Stundenverlauf-Abschnitt im Klartext, "
        "der Test wuerde nichts pruefen."
    )
    before = text[: text.index("STUNDENVERLAUF")]

    for name in ("Andermatt", "Zermatt"):
        assert not re.search(_SUMMARY_SENTENCE_RE.format(name=re.escape(name)), before), (
            f"Zusammenfassungssatz fuer {name!r} noch im Klartext vor "
            "STUNDENVERLAUF -- der Block haette entfernt sein muessen."
        )
    assert not before.endswith("\n\n\n"), (
        "Doppelte Leerzeile zwischen Orts-Uebersicht und STUNDENVERLAUF -- "
        "Rueckstand des entfernten lines.append(\"\")-Musters (RISIKO 4)."
    )


# ===========================================================================
# AC-6 -- Vorschau und Versand bleiben deckungsgleich (Fehlerklasse #1297)
# ===========================================================================

def test_dispatch_and_preview_share_render_path_without_summary_block():
    """AC-6: Vorschau (``compare_preview_service._render_email``,
    compare_preview_service.py:165-181) und Versand
    (``scheduler_dispatch_service.dispatch_compare_preset``,
    scheduler_dispatch_service.py:360-376) reichen fuer denselben Preset
    beide 1:1 ``resolve_compare_render_options(preset)`` -> die opts-Felder
    an ``render_compare_email()`` durch -- KEIN Import-Check, sondern derselbe
    Aufruf, den beide Aufrufstellen tatsaechlich machen (Wortlaut/Reihenfolge
    der Keyword-Argumente identisch zu beiden Fundstellen).

    ``resolve_compare_render_options`` ist eine reine Funktion (kein I/O) --
    der Vergleich ist ohne Netz/DB moeglich. Beide Pfade duerfen den
    Zusammenfassungsblock nicht zeigen (Fehlerklasse #1297: Vorschau zeigte
    einen anderen Wert als der Versand). RED bis zur Implementierung.
    """
    hourly = _hourly()
    result = _comparison_result([
        _location_result("Andermatt", hourly),
        _location_result("Zermatt", hourly),
    ])
    preset = {
        "id": "vorschau-versand-preset",
        "display_config": {"active_metrics": ["temp_max_c", "precip_sum_mm"]},
    }
    opts = resolve_compare_render_options(preset)

    html_body, text_body = render_compare_email(
        result,
        top_n_details=opts.top_n_details,
        enabled_metrics=opts.enabled_metrics,
        hourly_metrics=opts.hourly_metrics,
        hourly_enabled=opts.hourly_enabled,
        corridors=opts.corridors,
    )

    for name in ("Andermatt", "Zermatt"):
        pattern = _SUMMARY_SENTENCE_RE.format(name=re.escape(name))
        assert not re.search(pattern, html_body), (
            f"Vorschau/Versand-HTML enthaelt noch den Zusammenfassungssatz "
            f"fuer {name!r}."
        )
        assert not re.search(pattern, text_body), (
            f"Vorschau/Versand-Klartext enthaelt noch den Zusammenfassungssatz "
            f"fuer {name!r}."
        )


# ===========================================================================
# AC-3 -- Matrix-Regressionsschutz: 5 #1285-Metriken bleiben live abgeleitet
# ===========================================================================

def test_matrix_five_1285_metrics_stay_live_derived_from_daily_summary():
    """AC-3: die fuenf mit #1285 reparierten Matrix-Zeilen (Regen,
    Regenwahrscheinlichkeit, Gewitter, UV max, Sicht min) beziehen ihren Wert
    weiterhin aus der Live-Ableitung ``_daily_summary``/``summaries``
    (compare_html.py:349/464-469), NICHT aus dem entfernten
    Zusammenfassungsblock.

    Muss VOR UND NACH #1300 gruen bleiben. Wer beim Rueckbau
    ``_daily_summary`` oder die ``summaries``-Vorberechnung mitentfernt (weil
    es "wie Teil des Summary-Blocks aussieht", s. Kontext-Dokument RISIKO 1),
    scheitert an diesem Test -- die Matrix wuerde dann '-' statt echter Werte
    zeigen.

    ``LocationResult`` traegt fuer diese fuenf Felder in diesem Test bewusst
    KEINEN Engine-Wert (s. ``_location_result``) -- die Matrix MUSS also live
    aus ``hourly_data`` ableiten, kein Vorrang-Zweig kann sie umgehen.
    """
    hourly = _hourly()
    result = _comparison_result([_location_result("Sóller", hourly)])
    enabled = resolve_enabled_metrics([
        "precip_sum_mm", "pop_max_pct", "thunder_level_max",
        "uv_index_max", "visibility_min_m",
    ])

    summary = summarize_points(hourly)
    # Vorbedingungen: die Wetterlage muss tatsaechlich unterscheidbare Werte
    # fuer alle fuenf Groessen liefern, sonst prueft der Test nichts.
    assert summary.precip_sum_mm == 3.0
    assert summary.pop_max_pct == 70
    assert summary.thunder_level_max is ThunderLevel.MED
    assert summary.uv_index_max == 6.0
    assert summary.visibility_min_m == 3000

    html = render_compare_html(result, enabled_metrics=enabled)
    region = _matrix_region(html)

    assert _cell_value_for_label(region, "Regen") == f"{summary.precip_sum_mm:.1f} mm", (
        "Regen-Matrixzelle weicht von der Live-Ableitung ab -- #1285-"
        "Regression."
    )
    assert _cell_value_for_label(region, "Regenwahrscheinlichkeit") == f"{summary.pop_max_pct:.0f}%", (
        "Regenwahrscheinlichkeit-Matrixzelle weicht von der Live-Ableitung "
        "ab -- #1285-Regression."
    )
    assert _cell_value_for_label(region, "Gewitter") == "mittel", (
        "Gewitter-Matrixzelle weicht von der Live-Ableitung ab -- "
        "#1285-Regression."
    )
    assert _cell_value_for_label(region, "UV max") == f"{summary.uv_index_max:.0f}", (
        "UV-max-Matrixzelle weicht von der Live-Ableitung ab -- "
        "#1285-Regression."
    )
    assert _cell_value_for_label(region, "Sicht min") == f"{summary.visibility_min_m / 1000:.1f} km", (
        "Sicht-min-Matrixzelle weicht von der Live-Ableitung ab -- "
        "#1285-Regression."
    )


# ===========================================================================
# AC-5 -- Telegram/SMS unberuehrt (riefen render_comparison_text nie auf)
# ===========================================================================

def test_telegram_and_sms_output_unchanged_by_summary_block_removal():
    """AC-5: ``render_compare_telegram`` und ``render_compare_sms`` bauen
    ihre Ausgabe eigenstaendig auf (comparison.py:320/428) und rufen
    ``render_comparison_text`` NICHT auf -- der Zusammenfassungssatz erschien
    dort nie, der Rueckbau darf sie nicht beruehren.

    Erwartungswerte sind eine VORHER (vor Beginn dieser Arbeit, Commit
    6910853b) aufgezeichnete echte Ausgabe -- kein ausgedachter Wert. Dieser
    Test ist absichtlich schon jetzt gruen und muss gruen bleiben.
    """
    hourly = _hourly()
    result = _comparison_result([
        _location_result("Andermatt", hourly),
        _location_result("Zermatt", hourly),
    ])
    enabled = resolve_enabled_metrics(["temp_max_c", "precip_sum_mm"])

    telegram = render_compare_telegram(result, enabled_metrics=enabled, preset_name="Test-Preset")
    sms = render_compare_sms(result, enabled_metrics=enabled)

    recorded_telegram = (
        "ORTS-VERGLEICH — Test-Preset\nDatum: 08.07.2026\n\n"
        "Andermatt\n   Temp 16°C\nZermatt\n   Temp 16°C"
    )
    recorded_sms = "Vergleich 08.07.: Andermatt Temp 16°C; Zermatt Temp 16°C"

    assert telegram == recorded_telegram, (
        "Telegram-Ausgabe hat sich veraendert (Regression). "
        f"vorher: {recorded_telegram!r} / jetzt: {telegram!r}"
    )
    assert sms == recorded_sms, (
        "SMS-Ausgabe hat sich veraendert (Regression). "
        f"vorher: {recorded_sms!r} / jetzt: {sms!r}"
    )
    for name in ("Andermatt", "Zermatt"):
        pattern = _SUMMARY_SENTENCE_RE.format(name=re.escape(name))
        assert not re.search(pattern, telegram)
        assert not re.search(pattern, sms)


# ===========================================================================
# Kein totes Zeitfenster im STUNDEN-Kopf (#1278-Nebenbefund AC-12, aus
# test_compare_location_summary.py uebergesiedelt -- unabhaengig vom
# Summary-Block, gehoert aber thematisch zu den Bloecken der Vergleichs-Mail).
# ===========================================================================

def test_hourly_head_no_dead_time_window_string():
    """AC-12 (#1278-Nebenbefund): Der STUNDEN-Kopf zeigt keine feste
    Uhrzeitangabe '09–16 Uhr' mehr (toter Rest des mit #1268 abgeschafften
    Zeitfensters)."""
    result = _comparison_result([_location_result("Sóller", _hourly())])

    html = render_compare_html(result)

    assert "09–16 Uhr" not in html, (
        "STUNDEN-Kopf behauptet weiterhin ein Zeitfenster 09–16 Uhr, obwohl "
        "die Bewertung seit #1268 ueber den ganzen Tag laeuft."
    )
