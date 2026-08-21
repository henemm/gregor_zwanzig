"""TDD RED -- #1841: 3-Tages-Vorschau liest die Gewitterspalte aus dem
falschen Zeitfenster, sobald der Nutzer eine Ausblick-Spaltenauswahl
gesetzt hat.

SPEC: docs/specs/modules/fix_1841_vorschau_metrik_tagesfenster.md (AC-1..9)
KONTEXT: docs/context/fix-1841-ausblick-metrik-tagesfenster.md

RED-Ursache (heute gemessen): ``build_outlook_row()``
(``src/output/renderers/email/outlook.py:581-587``) baut die Gewitterzelle
des Metrik-Zweigs im TRIP-Fall ueber ``getattr(summary, "thunder_level_max")``
-- das auf die Gehzeit geklemmte Aggregat -- statt ueber das konfigurierte
Tagesfenster (denselben geteilten Helfer ``resolve_thunder_day_branch()``,
den #1671 fuer Kompaktmail/Klartext-Altpfad/Telegram liefert).

Fixtur-Geometrie (Spec "Fixtur-Geometrie", PFLICHT): AC-1 und AC-2 brauchen
ENTGEGENGESETZTE Zuschnitte, sonst liefern Aggregat und Tagesfenster
denselben Wert und der jeweilige AC-Test prueft nichts. Beide Fixturen
haben deshalb einen eigenen, vorangestellten Vorbedingungs-Test.

PRUEFORT = WIRKORT: AC-1/AC-2/AC-3 rendern ueber
``tests.helpers.trip_outlook_selection.render_trip_mail()`` --
``TripReportFormatter.format_email()``, den echten Aufrufpfad inkl.
``html.py:1364``/``plain.py:344``.

KEIN MOCK-THEATER. Echte ``ForecastDataPoint``/``SegmentWeatherSummary``,
echter Renderer-Aufruf. Kein Netz.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

# Pfadregel #1409: Pruefling relativ zur eigenen Testdatei aufloesen -- sonst
# pruefte ein Worktree-Lauf die unveraenderte Hauptrepo-Kopie.
REPO_ROOT = Path(__file__).resolve().parents[2]
for _pfad in (REPO_ROOT, REPO_ROOT / "src"):
    if str(_pfad) not in sys.path:
        sys.path.insert(0, str(_pfad))

from app.models import ForecastDataPoint, SegmentWeatherSummary, ThunderLevel  # noqa: E402
from output.renderers.email.compare_html import _fmt_thunder  # noqa: E402
from output.renderers.email.helpers import format_trend_tokens  # noqa: E402
from output.renderers.email.outlook import build_outlook_row  # noqa: E402
from output.tokens.dto import HourlyValue  # noqa: E402
from tests.helpers.trip_outlook_selection import (  # noqa: E402
    display_config, html_outlook_body_rows, html_outlook_headers,
    outlook_rows, plain_outlook_block, render_trip_mail,
)

_UTC = ZoneInfo("UTC")
GEWITTER = "thunder"   # #1848 A2: reine Kennung statt Paar
DAY_START, DAY_END = 4, 19


def _point(hour: int, level: ThunderLevel, signals=None) -> ForecastDataPoint:
    """Ein Stundenpunkt (UTC) fuer den 20.7.2026 (Sommerzeit) -- Stunden 14
    (Mitte) bzw. 0 (Mitternacht) bleiben unter BEIDEN moeglichen
    Ortszeit-Verschiebungen (UTC direkt oder Europe/Berlin +1/+2) sicher
    innerhalb bzw. ausserhalb des Tagesfensters 4-19."""
    return ForecastDataPoint(
        ts=datetime(2026, 7, 20, hour, 0, tzinfo=timezone.utc),
        thunder_level=level, thunder_level_signals=signals,
    )


def _summary(level: ThunderLevel, signals=None) -> SegmentWeatherSummary:
    return SegmentWeatherSummary(
        temp_min_c=9.0, temp_max_c=18.0, wind_max_kmh=20.0, precip_sum_mm=0.0,
        thunder_level_max=level, thunder_level_max_signals=signals,
    )


# AC-1: Gewitter um 14 Uhr (im Tagesfenster), Gehzeit-Aggregat sah es NICHT
# (die Gehzeit war enger als das Fenster) -> Aggregat meldet NONE.
AC1_POINTS = [_point(14, ThunderLevel.HIGH, signals=["cape"])]
AC1_SUMMARY = _summary(ThunderLevel.NONE)
# Variante ohne Traegerliste (AC-6 Zusatzfall).
AC1_POINTS_OHNE_SIGNALE = [_point(14, ThunderLevel.HIGH)]

# AC-2: Gewitter um 0 Uhr (ausserhalb des Tagesfensters), Gehzeit-Aggregat
# sah es SEHR WOHL (die Gehzeit reichte in die Nacht hinein) -> HIGH.
AC2_POINTS = [_point(0, ThunderLevel.HIGH, signals=["cape"])]
AC2_SUMMARY = _summary(ThunderLevel.HIGH, signals=["cape"])

# M6-Gegenprobe (Adversary-Finding F001, HIGH): AC-1/AC-2 tragen je NUR EINEN
# Stundenpunkt -- Tagesfenster- und 24h-Menge sind dort IDENTISCH, eine
# Verwechslung der beiden Fenster kann darin nicht auffallen. Diese Fixture
# hat ZWEI Punkte mit unterschiedlichen Stufen auf beiden Seiten der
# Fenstergrenze: MED um 14 Uhr (im Tagesfenster), HIGH um 0 Uhr (ausserhalb)
# -- Tagesfenster-Maximum (MED) und 24h-Maximum (HIGH) muessen sich
# unterscheiden, sonst pruefte der Test wieder nichts (dieselbe Falle wie
# bei AC-1/AC-2, nur auf der zweiten, unabhaengigen Achse).
M6_POINTS = [_point(14, ThunderLevel.MED), _point(0, ThunderLevel.HIGH)]
M6_SUMMARY = _summary(ThunderLevel.NONE)


# ═══════════════════ Fixtur-Vorbedingungen (KEIN AC) ═════════════════════
# Zeigen, dass Aggregat und Tagesfenster-Stufe je Fixture verschiedene Werte
# liefern -- sonst pruefte der zugehoerige AC-Test nichts (Spec
# "Fixtur-Geometrie"). Beide muessen schon HEUTE gruen sein, unabhaengig
# vom Fix: sie beschreiben nur die Testdaten.

def test_vorbedingung_ac1_aggregat_und_tagesfenster_liefern_verschiedene_werte():
    """Given die AC-1-Fixture / When Aggregat und der (bereits bestehende)
    Tagesfenster-Token verglichen werden / Then unterscheiden sie sich:
    das Aggregat meldet NONE, das Tagesfenster traegt ein Gewitter."""
    row = build_outlook_row(
        AC1_SUMMARY, AC1_POINTS, "Mo", _UTC,
        day_window_start_hour=DAY_START, day_window_end_hour=DAY_END,
    )
    tok = format_trend_tokens(row)
    assert AC1_SUMMARY.thunder_level_max == ThunderLevel.NONE
    assert tok["thunder_day_token"] != "-", (
        "Vorbedingung verletzt: die AC-1-Fixture zeigt im Tagesfenster kein "
        "Gewitter -- Aggregat und Tagesfenster liefern denselben Wert, der "
        "AC-1-Test koennte nichts pruefen."
    )


def test_vorbedingung_ac2_aggregat_und_tagesfenster_liefern_verschiedene_werte():
    """Given die AC-2-Fixture (Gegenrichtung) / When Aggregat und
    Tagesfenster-Token verglichen werden / Then unterscheiden sie sich:
    das Aggregat traegt eine Stufe, das Tagesfenster ist leer."""
    row = build_outlook_row(
        AC2_SUMMARY, AC2_POINTS, "Mo", _UTC,
        day_window_start_hour=DAY_START, day_window_end_hour=DAY_END,
    )
    tok = format_trend_tokens(row)
    assert AC2_SUMMARY.thunder_level_max == ThunderLevel.HIGH
    assert tok["thunder_day_token"] == "-", (
        "Vorbedingung verletzt: die AC-2-Fixture zeigt im Tagesfenster ein "
        "Gewitter -- Aggregat und Tagesfenster liefern denselben Wert, der "
        "AC-2-Test koennte nichts pruefen."
    )


# ══════════════════════════════ AC-1, AC-2 ═══════════════════════════════

def test_ac1_tagesgewitter_sichtbar_trotz_none_im_aggregat():
    """AC-1: Given ein Trip mit gesetzter Spaltenauswahl (Gewitter), dessen
    Stundenreihe im Tagesfenster ein Gewitter (14 Uhr, HIGH) zeigt, waehrend
    das gehzeit-geklemmte Aggregat NONE meldet / When die Trip-Mail erzeugt
    wird / Then nennt die Gewitterspalte die Stufe aus dem Tagesfenster --
    nicht NONE. Nachweis in HTML UND Klartext, ueber den echten
    Renderpfad (``render_trip_mail`` -> ``TripReportFormatter.format_email``).
    """
    dc = display_config(outlook_metrics=[GEWITTER])
    row = build_outlook_row(
        AC1_SUMMARY, AC1_POINTS, "Mo", _UTC,
        trip_display_config=dc, report_type="evening",
        day_window_start_hour=DAY_START, day_window_end_hour=DAY_END,
    )
    html, plain = render_trip_mail(dc, [row])
    # #1848 A3: der Metrik-Zweig ruft denselben Zellenbau wie der feste Zweig
    # (`thunder_branch.thunder_cell_html`/`…_plain`) -- die Stufe kommt
    # weiterhin aus dem TAGESFENSTER, traegt jetzt aber ihre Onset-Uhrzeit
    # (#1493) und die ausgabeort-eigene Schreibweise. Die hier bewachte
    # Zusicherung ist unveraendert: das gehzeit-geklemmte Aggregat meldet
    # NONE, jede Zelle mit "hoch" beweist das Tagesfenster als Quelle.
    stufe_mit_herkunft = _fmt_thunder(ThunderLevel.HIGH, None, ["cape"])
    erwartet_html = stufe_mit_herkunft.replace("hoch", "hoch @14", 1)
    erwartet_plain = "⚡" + stufe_mit_herkunft.replace("hoch", "hoch@14", 1)

    assert html_outlook_headers(html) == ["Tag", "Gewitter"], (
        f"Testaufbau: unerwartete Kopfzeile {html_outlook_headers(html)!r}."
    )
    zeilen = html_outlook_body_rows(html)
    zelle = zeilen[0][1] if zeilen else None
    assert zelle == erwartet_html, (
        f"HTML-Gewitterzelle {zelle!r} statt {erwartet_html!r} -- die Spalte "
        "zeigt weiterhin das gehzeit-geklemmte Aggregat (NONE) statt der "
        "Tagesfenster-Stufe (AC-1)."
    )

    block = plain_outlook_block(plain)
    assert block is not None and f"Gewitter {erwartet_plain}" in block, (
        f"Klartext-Ausblick:\n{block}\nenthaelt nicht "
        f"'Gewitter {erwartet_plain}' -- dieselbe Ursache wie im HTML-Zweig "
        "(AC-1)."
    )


def test_ac2_kein_gewitter_statt_nachtstufe_bei_leerem_tagesfenster():
    """AC-2: Given denselben Trip, dessen Aggregat eine Stufe traegt (HIGH),
    waehrend die Stundenreihe im Tagesfenster leer ist (das Gewitter liegt
    um 0 Uhr nachts) / When die Trip-Mail erzeugt wird / Then zeigt die
    Gewitterspalte ausdruecklich 'kein Gewitter' (ThunderLevel.NONE) und
    behauptet keine Tagesstufe."""
    dc = display_config(outlook_metrics=[GEWITTER])
    row = build_outlook_row(
        AC2_SUMMARY, AC2_POINTS, "Mo", _UTC,
        trip_display_config=dc, report_type="evening",
        day_window_start_hour=DAY_START, day_window_end_hour=DAY_END,
    )
    html, _ = render_trip_mail(dc, [row])
    erwartet = _fmt_thunder(ThunderLevel.NONE)

    zeilen = html_outlook_body_rows(html)
    zelle = zeilen[0][1] if zeilen else None
    assert zelle == erwartet, (
        f"HTML-Gewitterzelle {zelle!r} statt {erwartet!r} -- die Spalte "
        "behauptet ein Tagesgewitter, das nur im Nachtfenster lag (AC-2)."
    )


def test_ac3_keine_nachtangabe_im_metrik_zweig():
    """AC-3: Given denselben Trip aus AC-2 (Gewitter ausschliesslich im
    Nachtfenster) / When die Trip-Mail erzeugt wird / Then enthaelt die
    3-Tages-Vorschau KEINE Nachtangabe -- weder als eigene Spalte noch als
    Zusatz in der Gewitterzelle (PO-Entscheid 2026-08-14, bewusste
    Abweichung von #1653/#1671).

    #1848 A3: dieser Entscheid gilt seither fuer ALLE Touren, nicht mehr nur
    fuer den Metrik-Zweig -- der feste Zweig entfaellt als Normalfall, und die
    Nachtangabe ist aus allen VIER Ausblick-Darstellungen entfernt. DREIFACH
    bestaetigt (2026-08-14 · 2026-08-21 mit Kenntnis von Verwechslungsluecke
    und Testumfang · 2026-08-21 Mittelweg ausdruecklich abgelehnt); Begruendung
    und Tragweite stehen an der zentralen Fundstelle
    ``output/renderers/email/thunder_branch.py`` (Kopfkommentar). Der
    Geltungsbereich bleibt strikt die 3-Tages-Vorschau; Tages-Briefing,
    Stundenverlauf und Alarme fuehren den Tag/Nacht-Split unveraendert."""
    dc = display_config(outlook_metrics=[GEWITTER])
    row = build_outlook_row(
        AC2_SUMMARY, AC2_POINTS, "Mo", _UTC,
        trip_display_config=dc, report_type="evening",
        day_window_start_hour=DAY_START, day_window_end_hour=DAY_END,
    )
    html, plain = render_trip_mail(dc, [row])

    zeilen = html_outlook_body_rows(html)
    zelle = (zeilen[0][1] if zeilen else "").lower()
    assert "nachts" not in zelle, (
        f"HTML-Gewitterzelle {zelle!r} enthaelt eine Nachtangabe (AC-3)."
    )
    block = (plain_outlook_block(plain) or "").lower()
    assert "nachts" not in block, (
        f"Klartext-Ausblick enthaelt eine Nachtangabe:\n{block}\n(AC-3)"
    )


def test_ac4_ohne_stundenreihe_bleibt_die_zelle_zeichengleich():
    """AC-4: Given einen Trip mit gesetzter Spaltenauswahl, dessen Punkte
    ueberhaupt keine Gewitterstufen tragen (keine Stundenreihe) / When eine
    Zeile gebaut wird / Then bleibt die Zelle zeichengleich zum Stand vor
    dieser Aenderung (Zweig 'plain', Rueckfall auf das Aggregat).

    Regressionsschutz: bleibt gruen, unabhaengig davon ob der Fix schon
    implementiert ist -- der Nullfall ohne Stundenreihe ist gerade NICHT
    von #1841 betroffen."""
    dc = display_config(outlook_metrics=[GEWITTER])
    summary = _summary(ThunderLevel.MED, signals=["blitzdichte"])
    row = build_outlook_row(
        summary, [], "Mo", _UTC,
        trip_display_config=dc, report_type="evening",
        day_window_start_hour=DAY_START, day_window_end_hour=DAY_END,
    )
    erwartet = [_fmt_thunder(ThunderLevel.MED, None, ["blitzdichte"])]
    assert row.get("cells") == erwartet, (
        f"Zelle {row.get('cells')!r} statt {erwartet!r} -- der Nullfall "
        "ohne Stundenreihe muss unveraendert auf das Aggregat zurueckfallen "
        "(AC-4)."
    )


def test_ac5_ortsvergleich_bleibt_byte_identisch():
    """AC-5: Given einen Ortsvergleich (metrics=..., KEIN
    trip_display_config) mit gesetzter Metrik-Auswahl und denselben
    asymmetrischen Punkten wie AC-1 / When dessen Zeile gebaut wird / Then
    zeigt die Zelle weiterhin ``summary.thunder_level_max`` -- unveraendert
    (#1653 AC-6 bleibt in Kraft).

    Regressionsschutz -- ist heute bereits gruen (der Metrik-Zweig kennt
    noch gar keine Tagesfenster-Verzweigung) und MUSS es nach dem Fix
    bleiben (Mutations-Gegenprobe M1: Diskriminator faelschlich auf
    ``True``)."""
    row = build_outlook_row(
        AC1_SUMMARY, AC1_POINTS, "Mo", _UTC, metrics=[GEWITTER],
        day_window_start_hour=DAY_START, day_window_end_hour=DAY_END,
    )
    erwartet = [_fmt_thunder(ThunderLevel.NONE)]
    assert row["cells"] == erwartet, (
        f"Compare-Zelle {row['cells']!r} statt {erwartet!r} -- der "
        "Ortsvergleich darf sich durch diese Scheibe nicht aendern (AC-5)."
    )


def test_ac6_herkunft_stammt_aus_demselben_fenster_wie_die_stufe():
    """AC-6: Given denselben Trip aus AC-1 (das Aggregat traegt KEINE
    Herkunft) / When die Gewitterzelle eine Herkunft nennt / Then stammt
    diese aus dem Tagesfenster -- nicht aus dem (hier leeren) Aggregat."""
    dc = display_config(outlook_metrics=[GEWITTER])
    assert AC1_SUMMARY.thunder_level_max_signals is None, (
        "Testaufbau: das Aggregat darf keine Herkunft tragen, sonst "
        "unterscheidet dieser Test die beiden Quellen nicht."
    )
    row = build_outlook_row(
        AC1_SUMMARY, AC1_POINTS, "Mo", _UTC,
        trip_display_config=dc, report_type="evening",
        day_window_start_hour=DAY_START, day_window_end_hour=DAY_END,
    )
    erwartet = [_fmt_thunder(ThunderLevel.HIGH, None, ["cape"])]
    assert row.get("cells") == erwartet, (
        f"Zelle {row.get('cells')!r} statt {erwartet!r} -- sie muss die "
        "Herkunft aus dem Tagesfenster nennen (AC-6)."
    )


def test_ac6_ohne_traegerliste_erscheint_die_stufe_ohne_herkunft():
    """AC-6 Zusatzfall: traegt KEIN Datenpunkt im Tagesfenster eine
    Traegerliste, erscheint die (korrekte) Tagesfenster-Stufe OHNE Herkunft
    -- nie eine Herkunft aus einer anderen Rechnung (AC-10-Regel aus
    #1680 S5a)."""
    dc = display_config(outlook_metrics=[GEWITTER])
    row = build_outlook_row(
        AC1_SUMMARY, AC1_POINTS_OHNE_SIGNALE, "Mo", _UTC,
        trip_display_config=dc, report_type="evening",
        day_window_start_hour=DAY_START, day_window_end_hour=DAY_END,
    )
    erwartet = [_fmt_thunder(ThunderLevel.HIGH, None, None)]
    assert row.get("cells") == erwartet, (
        f"Zelle {row.get('cells')!r} statt {erwartet!r} -- ohne "
        "Traegerliste darf keine Herkunft erscheinen (AC-6)."
    )


def test_ac7_trip_ohne_grundauswahl_bleibt_altpfad_unberuehrt():
    """⚠️ AC-7 NACHGEZOGEN durch #1848 A3.

    Bis dahin lautete die Bedingung "OHNE gesetzte SPALTENAUSWAHL": ein
    fehlendes ``outlook_metrics`` liess den Metrik-Zweig ruhen und der feste
    Zweig blieb in Kraft. Genau das kehrt A3 um -- "nie eingestellt" heisst
    seither "nichts abgewaehlt", der Ausblick erbt die Grundauswahl (AC-3
    der A3-Spec). Der feste Zweig bleibt fuer den verbliebenen Fall
    zustaendig: KEINE Grundauswahl, also kein Maximum (ADR-0050 D4).

    Given einen Trip ohne Grundauswahl / When eine Zeile gebaut wird / Then
    bleibt der Row-Dict OHNE 'cells' -- der Altpfad (feste sieben Spalten
    inkl. Nachtangabe/Ampelfarben) bleibt in Kraft.
    """
    dc = display_config(leere_grundauswahl=True)  # kein Maximum (D4)
    row = build_outlook_row(
        AC2_SUMMARY, AC2_POINTS, "Mo", _UTC,
        trip_display_config=dc, report_type="evening",
        day_window_start_hour=DAY_START, day_window_end_hour=DAY_END,
    )
    assert "cells" not in row, (
        f"Row {row!r} traegt 'cells', obwohl keine Grundauswahl gesetzt "
        "ist -- ohne Maximum darf der Metrik-Zweig nicht greifen (AC-7, D4)."
    )

    # Gegenprobe: MIT Grundauswahl greift er sehr wohl -- sonst waere die
    # Zusicherung oben auch dann gruen, wenn der Metrik-Zweig gar nicht mehr
    # erreichbar ist.
    row_mit = build_outlook_row(
        AC2_SUMMARY, AC2_POINTS, "Mo", _UTC,
        trip_display_config=display_config(), report_type="evening",
        day_window_start_hour=DAY_START, day_window_end_hour=DAY_END,
    )
    assert row_mit.get("cells"), (
        "Gegenprobe gescheitert: mit Grundauswahl muss der Metrik-Zweig "
        "greifen (#1848 A3, AC-3) -- sonst bewacht der Test oben nichts."
    )


def test_ac8_helfer_baut_trip_zeilen_ueber_die_trip_konvention():
    """AC-8: Given der Testhelfer ``outlook_rows()`` mit eigens
    eingespeisten Punkten/Aggregat (AC-1-Geometrie) / When er ueber
    ``trip_display_config``/``report_type``/Tagesfenster (NICHT ``metrics=``)
    eine Zeile baut / Then zeigt die gebaute Zeile die Tagesfenster-Stufe --
    derselbe Aufrufweg wie ``trip_report_scheduler.py:2282``.

    Nachweis (Mutations-Gegenprobe M7): faellt der Helfer zurueck auf
    ``metrics=``, zeigt die Zelle das (hier NONE-)Aggregat statt der
    Tagesfenster-Stufe -- dieser Test wird rot."""
    dc = display_config(outlook_metrics=[GEWITTER])
    row = outlook_rows(
        trip_display_config=dc, report_type="evening",
        day_window_start_hour=DAY_START, day_window_end_hour=DAY_END,
        points_override={0: AC1_POINTS}, summary_override={0: AC1_SUMMARY},
    )[0]
    erwartet = [_fmt_thunder(ThunderLevel.HIGH, None, ["cape"])]
    assert row.get("cells") == erwartet, (
        f"Zelle {row.get('cells')!r} statt {erwartet!r} -- der Helfer "
        "liefert weiterhin die Compare-Zellen (Aggregat) statt der "
        "Trip-Zellen (Tagesfenster); outlook_rows() nutzt noch nicht die "
        "Trip-Konvention (AC-8)."
    )


def test_ac9_format_trend_tokens_liefert_zusaetzlich_thunder_day_level():
    """AC-9: Given ein Stundenfenster mit einem Gewitter um 14 Uhr (HIGH) im
    Tagesfenster (4-19) / When ``format_trend_tokens()`` aufgerufen wird /
    Then traegt die Rueckgabe zusaetzlich ``thunder_day_level`` ==
    ``ThunderLevel.HIGH`` -- additiv, ohne den bestehenden Schluessel
    ``thunder_day_token`` ('hoch@14') zu veraendern (Bestandsschutz fuer
    Telegram/Kompaktmail/Altpfad-Aufrufer)."""
    stage = dict(
        weekday="Mo", temp_lo=10, temp_hi=18, precip_mm=0.0, wind_dir="W",
        wind_kmh=20, thunder="NONE",
        hourly_precip=(), hourly_wind=(), hourly_gust=(),
        hourly_thunder=(HourlyValue(hour=14, value=3.0),),
        day_window_start_hour=DAY_START, day_window_end_hour=DAY_END,
    )
    tok = format_trend_tokens(stage)
    assert tok["thunder_day_token"] == "hoch@14", (
        "Testaufbau: Bestandsverhalten nicht wie erwartet, tatsaechlich "
        f"{tok['thunder_day_token']!r}."
    )
    assert tok.get("thunder_day_level") == ThunderLevel.HIGH, (
        "format_trend_tokens() liefert noch keinen (korrekten) "
        "Rueckgabeschluessel 'thunder_day_level' -- AC-9 verlangt eine "
        "zusaetzliche, additive Tagesfenster-STUFE neben dem bestehenden "
        "String-Token 'thunder_day_token'."
    )


# ═══════════ Mutations-Gegenprobe M6 (Adversary-Finding F001, HIGH) ══════════
# AC-1/AC-2 tragen je nur EINEN Stundenpunkt -- Tagesfenster- und 24h-Menge
# sind dort identisch, eine Verwechslung der beiden Fenster (M6: "aus dem
# 24h-Fenster statt dem Tagesfenster") kann darin nicht auffallen. Diese
# zweite, unabhaengige Fixtur-Achse braucht mindestens zwei Punkte auf
# beiden Seiten der Fenstergrenze mit UNTERSCHIEDLICHEN Stufen.

def test_vorbedingung_m6_tagesfenster_max_und_24h_max_liefern_verschiedene_werte():
    """Fixtur-Vorbedingung (KEIN AC): zeigt, dass fuer die M6-Fixture das
    Tagesfenster-Maximum (MED, aus dem Punkt um 14 Uhr) und das 24h-Maximum
    (HIGH, aus dem Punkt um 0 Uhr ausserhalb) verschieden sind -- sonst
    pruefte der M6-Test nichts. Muss schon HEUTE gruen sein."""
    from app.thunder_scale import thunder_ordinal

    row = build_outlook_row(
        M6_SUMMARY, M6_POINTS, "Mo", _UTC,
        day_window_start_hour=DAY_START, day_window_end_hour=DAY_END,
    )
    tok = format_trend_tokens(row)
    _24h_max = max(
        (p.thunder_level for p in M6_POINTS if p.thunder_level is not None),
        key=thunder_ordinal,
    )
    assert _24h_max == ThunderLevel.HIGH, (
        "Testaufbau: das 24h-Maximum der M6-Fixture ist nicht HIGH."
    )
    assert tok["thunder_day_token"] == "mittel@14", (
        "Vorbedingung verletzt: das Tagesfenster-Maximum der M6-Fixture "
        f"({tok['thunder_day_token']!r}) muss MED ('mittel@14') sein, nicht "
        "das 24h-Maximum HIGH -- sonst unterscheiden Tagesfenster und 24h-"
        "Fenster nichts, und der M6-Test koennte die Verwechslung nicht "
        "fangen."
    )


def test_m6_tagesfenster_stufe_kommt_aus_dem_tagesfenster_nicht_aus_24h():
    """Mutations-Gegenprobe M6 (Spec-Tabelle): Given eine Stundenreihe mit
    zwei Punkten -- MED um 14 Uhr (im Tagesfenster 4-19), HIGH um 0 Uhr
    (ausserhalb) / When die Trip-Mail mit gesetzter Gewitterspalte erzeugt
    wird / Then zeigt die Zelle die Stufe DES TAGESFENSTERS (MED) -- nicht
    das 24-Stunden-Maximum (HIGH).

    Eine Ein-Punkt-Fixtur (wie AC-1/AC-2) kann diese Verwechslung nicht
    fangen, weil Tagesfenster- und 24h-Menge dort identisch sind
    (Adversary-Finding F001, HIGH)."""
    dc = display_config(outlook_metrics=[GEWITTER])
    row = build_outlook_row(
        M6_SUMMARY, M6_POINTS, "Mo", _UTC,
        trip_display_config=dc, report_type="evening",
        day_window_start_hour=DAY_START, day_window_end_hour=DAY_END,
    )
    html, _ = render_trip_mail(dc, [row])
    # #1848 A3: die Zelle traegt jetzt die Onset-Uhrzeit (#1493). Die
    # Mutations-Gegenprobe bleibt scharf: das 24h-Maximum HIGH liegt
    # ausserhalb des Tagesfensters und darf nirgends erscheinen.
    erwartet = f"{_fmt_thunder(ThunderLevel.MED)} @14"

    zeilen = html_outlook_body_rows(html)
    zelle = zeilen[0][1] if zeilen else None
    assert zelle == erwartet, (
        f"HTML-Gewitterzelle {zelle!r} statt {erwartet!r} -- zeigt "
        "vermutlich das 24h-Maximum (HIGH) statt der Tagesfenster-Stufe "
        "(MED) (Mutations-Gegenprobe M6)."
    )
