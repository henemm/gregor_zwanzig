"""Telegram-Trip-Nachricht: Kappungshinweis in der Kurzuebersicht (#1741).

SPEC: docs/specs/modules/fix_1741_telegram_kappungshinweis.md — AC-1, AC-2,
AC-3, AC-6 (AC-4/AC-5 sind Regressionsschutz ueber bestehende Testdateien,
brauchen keine neue Datei).

Bug: Ueberzaehlige Telegram-Metriken (>7 aktive ``primary``) verlieren ihre
stuendliche Aufloesung in der Segment-Tabelle, aber die Telegram-Nachricht
selbst sagt nirgends, dass gekappt wurde. KEIN bestehender Test prueft die
GERENDERTE Ausgabe darauf -- ``test_channel_metric_matrix.py:800-806`` haelt
das schriftlich fest und weicht dem Problem bewusst aus (dort wird nur
``ChannelLayout`` gegengeprueft, nie der Bubble-Text). Diese Datei rendert
deshalb echte Bubbles ueber den Produktivpfad
(``TripReportFormatter().format_email()`` -> ``report.telegram_bubbles``),
Vorbild ``test_channel_metric_matrix.py::_kaskade_report``/
``_s4_telegram_bubbles`` (Zeilen 851/3251).
"""
from __future__ import annotations

import dataclasses

from app.models import MetricConfig, UnifiedWeatherDisplayConfig
from output.renderers import narrow
from output.renderers.channel_layout import ChannelLayout, telegram_metric_notice
from output.renderers.trip_report import TripReportFormatter

from tests.tdd import _min_temp_felt_fixtures as F

# Wortlaut-Fragment aus der Spec (Implementation Details §2), OHNE das
# fuehrende "… +N " -- das wird je Test mit dem erwarteten N zusammengesetzt.
_NOTICE_FRAGMENT = "weitere Wettergrößen nur als Tageswert (Telegram-Limit)"

# 9 reale, katalogisierte primary-Metriken, winterfrei -- F.segment() liefert
# fuer alle neun einen echten Wert ohne Zusatz-Aggregation (anders als
# snow_depth/snowfall_limit/fresh_snow, die eine praeparierte Aggregation
# brauchen, s. test_channel_metric_matrix.py::_matrix_segment). Reihenfolge
# nach METRIC_PRIORITY (channel_layout.py), sodass die ersten 7 in die
# Tabelle rutschen und die letzten 2 ueberzaehlig sind (demoted_count == 2).
_NINE_PRIMARY_METRIC_IDS = [
    "temperature", "wind", "gust", "rain_probability", "precipitation",
    "wind_chill", "cloud_total", "thunder", "visibility",
]
assert len(_NINE_PRIMARY_METRIC_IDS) == 9


def _dc_with_primary_metrics(metric_ids: list[str]) -> UnifiedWeatherDisplayConfig:
    """Globale Auswahl, KEINE Kanal-Ebene -- Telegram faellt auf die
    Grundauswahl zurueck (ADR-0050 Regel 1), alle Metriken im
    ``primary``-Bucket, Reihenfolge == Eingabe-Reihenfolge."""
    return UnifiedWeatherDisplayConfig(
        trip_id="1741-kappungshinweis",
        metrics=[
            MetricConfig(metric_id=mid, enabled=True, bucket="primary", order=i)
            for i, mid in enumerate(metric_ids)
        ],
    )


def _telegram_bubbles(
    dc: UnifiedWeatherDisplayConfig, segments: list | None = None,
) -> list[str]:
    """Echter Renderpfad (Vorbild ``_kaskade_report``/``_s4_telegram_bubbles``,
    test_channel_metric_matrix.py:851/3251) -- NICHT ``render_for_channel()``
    direkt, das den Kollabierungsschritt umgeht und keine Bubble-Texte
    erzeugt (Konstruktionshinweis der Spec, AC-1)."""
    segs = segments if segments is not None else [F.segment()]
    report = TripReportFormatter().format_email(
        segs, trip_name="Kappungshinweis1741", report_type="evening",
        night_weather=F.night_weather(), display_config=dc,
        stage_name=F.STAGE_NAME, tz=F.TZ,
    )
    return report.telegram_bubbles


def _kurzuebersicht_bubble(bubbles: list[str]) -> str:
    """Findet die Kurzuebersicht-Bubble am PRAEFIX ihres Textes, nicht per
    festem Index -- die Bubble-Reihenfolge darf sich aendern, ohne dass der
    Test aus dem falschen Grund bricht (AC-1-Vorgabe)."""
    for text in bubbles:
        if text.startswith("Kurzübersicht"):
            return text
    raise AssertionError(f"keine Kurzuebersicht-Bubble gefunden: {bubbles!r}")


# --- AC-1: >7 aktive primary-Metriken -> Hinweis mit korrektem N ----------


def test_overview_bubble_shows_notice_with_correct_count_when_over_seven_metrics():
    dc = _dc_with_primary_metrics(_NINE_PRIMARY_METRIC_IDS)
    bubbles = _telegram_bubbles(dc)
    kb = _kurzuebersicht_bubble(bubbles)
    # Zeilenumbruch-tolerant: die Zeile ist 60 Zeichen lang und damit breiter
    # als _TG_PROSE_WIDTH (56) -- _wrap() darf sie auf zwei Zeilen verteilen.
    normalized = " ".join(kb.split())
    assert f"+2 {_NOTICE_FRAGMENT}" in normalized, (
        f"AC-1: Kappungshinweis mit N=2 fehlt in der Kurzuebersicht "
        f"(9 primary-Metriken, 7 Tabellen-Slots): {kb!r}"
    )


# --- AC-2: <=7 aktive primary-Metriken -> Hinweiszeile fehlt vollstaendig -


def test_overview_bubble_has_no_notice_when_seven_or_fewer_metrics():
    dc = _dc_with_primary_metrics(_NINE_PRIMARY_METRIC_IDS[:7])
    bubbles = _telegram_bubbles(dc)
    kb = _kurzuebersicht_bubble(bubbles)
    assert _NOTICE_FRAGMENT not in " ".join(kb.split()), (
        f"AC-2: Kappungshinweis erscheint trotz demoted_count==0: {kb!r}"
    )
    assert "+0" not in kb, f"AC-2: '+0' im Bubble-Text: {kb!r}"
    assert "\n\n\n" not in kb, (
        f"AC-2: ueberzaehlige Leerzeile im Bubble-Text: {kb!r}"
    )


# --- AC-3: Ueberlauf + >=2 Segmente -> Hinweis GENAU EINMAL, nur in der ---
# --- Kurzuebersicht, nie in einer Segment-Tabellen-Bubble -----------------


def test_notice_appears_exactly_once_across_bubbles_with_multiple_segments():
    seg1 = F.segment()
    seg2_raw = F.segment(day=F.DAY + 1)
    seg2 = dataclasses.replace(
        seg2_raw, segment=dataclasses.replace(seg2_raw.segment, segment_id=2),
    )
    dc = _dc_with_primary_metrics(_NINE_PRIMARY_METRIC_IDS)
    bubbles = _telegram_bubbles(dc, segments=[seg1, seg2])

    fragment = f"+2 {_NOTICE_FRAGMENT}"
    hits = [b for b in bubbles if fragment in " ".join(b.split())]
    assert len(hits) == 1, (
        f"AC-3: Hinweistext soll GENAU EINMAL ueber alle Bubbles vorkommen, "
        f"gefunden in {len(hits)} Bubbles: {bubbles!r}"
    )
    assert hits[0].startswith("Kurzübersicht"), (
        f"AC-3: Hinweistext steht nicht in der Kurzuebersicht-Bubble: {hits[0]!r}"
    )
    for b in bubbles:
        if "<pre>" in b:
            assert fragment not in " ".join(b.split()), (
                f"AC-3: Hinweistext in einer Segment-Tabellen-Bubble gefunden: {b!r}"
            )


# --- F001 (Adversary-Fund, Gegenpruefung) -- die beiden Wortlaute sind ---
# --- BEWUSST verschieden (kein Kanal ersetzt einen anderen) und muessen --
# --- deshalb je Kontext WOERTLICH gepinnt werden, nicht nur am Fragment --
# --- "+N weitere Wettergrößen", das in beiden Wortlauten identisch ist. --
# --- Erwartung ist ein Literal in diesem Test, NICHT aus channel_layout.py
# --- importiert/abgeleitet -- sonst bewacht der Test die Quelle nicht. ---


def test_vergleich_notice_full_wording_is_pinned_and_route_wording_absent():
    text = telegram_metric_notice(2, context="vergleich")
    assert text == (
        "… +2 weitere Wettergrößen je Ort (Telegram-Limit) "
        "— vollständig per E-Mail"
    ), f"F001: Vergleichs-Wortlaut weicht ab: {text!r}"
    assert "nur als Tageswert" not in text, (
        f"F001: Trip-Wortlaut-Fragment im Vergleichs-Text gefunden: {text!r}"
    )


def test_route_notice_full_wording_is_pinned_and_vergleich_wording_absent():
    text = telegram_metric_notice(2, context="route")
    assert text == (
        "… +2 weitere Wettergrößen nur als Tageswert (Telegram-Limit)"
    ), f"F001: Trip-Wortlaut weicht ab: {text!r}"
    assert "je Ort" not in text, (
        f"F001: Vergleichs-Wortlaut-Fragment 'je Ort' im Trip-Text gefunden: {text!r}"
    )
    assert "vollständig per E-Mail" not in text, (
        f"F001: Vergleichs-Wortlaut-Fragment 'vollständig per E-Mail' im "
        f"Trip-Text gefunden: {text!r}"
    )


def test_notice_is_empty_string_for_zero_demoted_in_both_contexts():
    assert telegram_metric_notice(0, context="vergleich") == ""
    assert telegram_metric_notice(0, context="route") == ""


# --- AC-6: toter Pfad entfernt --------------------------------------------


def test_channel_layout_and_narrow_have_no_dead_detail_path():
    field_names = {f.name for f in dataclasses.fields(ChannelLayout)}
    assert "detail_metrics" not in field_names, (
        f"AC-6: ChannelLayout traegt noch das tote Feld 'detail_metrics': {field_names}"
    )
    assert not hasattr(narrow, "_detail_lines"), (
        "AC-6: narrow-Modul hat noch das tote Attribut '_detail_lines'"
    )
