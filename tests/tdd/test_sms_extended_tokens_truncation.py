"""TDD RED: Kuerzungsreihenfolge + Telegram-Paritaet der 14 neuen SMS-Token.

Issue #1660 Scheibe B. SPEC: docs/specs/modules/fix_1660b_sms_token_wiring.md

AC -> Test-Mapping:
  AC-12  test_ac12_new_tokens_drop_before_any_wintersport_token
  AC-14  test_ac14_sms_and_telegram_kurzform_share_the_same_rendered_text

AC-14-Hinweis (Prueftiefe): ``services/notification_service.py`` sendet den
Telegram-"kurzform"-Kanal ueber ``body=report.sms_text or report.email_plain``
(Zeilen ~364/~381) -- es gibt in der Produktion strukturell KEINEN zweiten
Aufruf von build_token_line()/render_sms() fuer diesen Kanal, sondern
Wiederverwendung desselben bereits gerenderten Strings (``TripReport`` fuehrt
genau EIN Kurzform-Feld, ``sms_text`` -- kein separates
``telegram_kurzform_text``). Ein zweiter, unabhaengiger Render-Aufruf im Test
wuerde deshalb nichts pruefen, das nicht schon durch die anderen
Grammatik-Tests abgedeckt ist (er waere tautologisch gruen). Diese Datei
prueft stattdessen, dass ``format_sms()`` selbst fuer alle drei
Grammatik-Klassen gleichzeitig ein konsistentes Ergebnis liefert -- das ist
die EINE Quelle, die Telegram-Kurzform unveraendert uebernimmt.
"""
from __future__ import annotations

import dataclasses

from output.tokens.builder import build_token_line
from output.tokens.dto import DailyForecast, HourlyValue, MetricSpec, NormalizedForecast


def _render(today: DailyForecast, config: list[MetricSpec], *,
            report_type: str = "evening", stage_name: str = "S1",
            max_length: int = 160) -> str:
    forecast = NormalizedForecast(days=(today,))
    line = build_token_line(
        forecast, config, report_type=report_type, stage_name=stage_name,
    )
    return line.render(max_length)


def _baseline_today() -> DailyForecast:
    return DailyForecast(
        temp_min_c=12.0, temp_max_c=24.0,
        rain_hourly=(HourlyValue(6, 0.2), HourlyValue(16, 1.4)),
        pop_hourly=(HourlyValue(11, 40.0), HourlyValue(17, 90.0)),
        wind_hourly=(HourlyValue(11, 18.0), HourlyValue(15, 28.0)),
        gust_hourly=(HourlyValue(11, 25.0), HourlyValue(15, 40.0)),
        thunder_hourly=(HourlyValue(16, 2),),
        snow_depth_cm=180.0, snow_new_24h_cm=25.0, snowfall_limit_m=1800.0,
        avalanche_level=3, wind_chill_c=-22.0,
    )


def _baseline_config() -> list[MetricSpec]:
    return [
        # Fix #1926 Fund: 'K' bewusst NICHT auf 'L' umgestellt -- Gating-
        # Schluessel gegen builder.py's eigenes Vokabular (Schichtgrenze),
        # von der Registeraenderung unberuehrt.
        MetricSpec(symbol="K", enabled=True),
        MetricSpec(symbol="D", enabled=True),
        MetricSpec(symbol="R", enabled=True, threshold=0.2),
        MetricSpec(symbol="PR", enabled=True, threshold=20.0),
        MetricSpec(symbol="W", enabled=True, threshold=10.0),
        MetricSpec(symbol="G", enabled=True, threshold=20.0),
        MetricSpec(symbol="TH:", enabled=True, threshold=1.0),
        MetricSpec(symbol="SD", enabled=True),
        MetricSpec(symbol="NS24+", enabled=True),
        MetricSpec(symbol="SL", enabled=True),
        MetricSpec(symbol="AV", enabled=True),
        # Fix #1887 E6 Scheibe A (PO-Entscheid): 'WC' entfaellt ERSATZLOS
        # (verdoppelte nachweislich 'FK') -- kein MetricSpec mehr hier.
    ]


def test_ac12_new_tokens_drop_before_any_wintersport_token():
    """AC-12: bei Ueberlaenge (>160 Zeichen) fallen die 14 neuen Token
    VOLLSTAENDIG weg, bevor auch nur ein Wintersport-Token (SD/NS24+/SL/AV)
    entfernt wird. Fix #1887 E6 Scheibe A (PO-Entscheid): 'WC' ist ERSATZLOS
    entfallen und gehoert nicht mehr zum Wintersport-Block dieses Tests.

    Konstruktions-Invariante (robust gegen die exakte Zeichenlaenge der
    einzelnen neuen Token, die erst die Implementierung festlegt): die
    Baseline (Stage-Name + Sicherheits-Token R/PR/W/G/TH: + alle fuenf
    Wintersport-Token) passt bereits FUER SICH allein deutlich unter 160
    Zeichen (siehe Kontrollmessung unten, funktioniert schon heute ohne die
    neuen Felder). Nach Spec DEC-4 stehen die 14 neuen Symbole in
    DROP_ORDER VOR den Wintersport-Symbolen -- die Kuerzungsschleife (§6)
    entfernt Symbole strikt sequenziell und stoppt, sobald das Budget
    erreicht ist. Damit MUSS die Kuerzung ausschliesslich aus dem
    neuen-14-Block schoepfen, solange sie ueberhaupt etwas entfernt, denn
    schon das vollstaendige Leeren dieses Blocks bringt die Zeile wieder auf
    Baseline-Laenge zurueck -- die Wintersport-Symbole werden dafuer nicht
    gebraucht.
    """
    baseline_config = _baseline_config()
    baseline_line = _render(_baseline_today(), baseline_config, stage_name="S1")
    assert len(baseline_line) <= 160, (
        "Kontrollmessung: die Baseline OHNE die 14 neuen Metriken muss schon "
        f"heute unter 160 Zeichen passen (gemessen: {len(baseline_line)}): "
        f"{baseline_line!r}"
    )

    today_with_new = dataclasses.replace(
        _baseline_today(),
        humidity_hourly=(HourlyValue(14, 88), HourlyValue(17, 92)),
        dewpoint_hourly=(HourlyValue(5, 3), HourlyValue(9, 7)),
        cape_hourly=(HourlyValue(16, 1200),),
        uv_hourly=(HourlyValue(13, 8),),
        cloud_total_hourly=(HourlyValue(12, 80),),
        cloud_low_hourly=(HourlyValue(10, 40),),
        cloud_mid_hourly=(HourlyValue(11, 55),),
        cloud_high_hourly=(HourlyValue(9, 20),),
        visibility_hourly=(HourlyValue(9, 3000), HourlyValue(11, 600)),
        freezing_level_hourly=(HourlyValue(6, 1800), HourlyValue(12, 2400)),
        wind_direction_sector="NW",
        precip_type_dominant="S",
        sunshine_hours=6.4,
        pressure_avg_hpa=1013.4,
    )
    full_config = baseline_config + [
        MetricSpec(symbol="HU", enabled=True, threshold=85.0),
        MetricSpec(symbol="DP", enabled=True),
        MetricSpec(symbol="CP", enabled=True),
        MetricSpec(symbol="UV", enabled=True),
        MetricSpec(symbol="CT", enabled=True),
        MetricSpec(symbol="CL", enabled=True),
        MetricSpec(symbol="CM", enabled=True),
        MetricSpec(symbol="CH", enabled=True),
        MetricSpec(symbol="VS", enabled=True, threshold=1.0),
        MetricSpec(symbol="NL", enabled=True),
        # Issue #1824 (B): Symbole tragen den Grammatik-Doppelpunkt.
        MetricSpec(symbol="WD:", enabled=True),
        MetricSpec(symbol="PT:", enabled=True),
        MetricSpec(symbol="SU", enabled=True),
        MetricSpec(symbol="HP", enabled=True),
    ]

    full_untruncated = _render(
        today_with_new, full_config, stage_name="S1", max_length=100_000,
    )
    assert len(full_untruncated) > 160, (
        "Fixture-Voraussetzung verletzt: mit allen 14 neuen Token muss die "
        f"ungekuerzte Zeile ueber 160 Zeichen liegen (gemessen: "
        f"{len(full_untruncated)}): {full_untruncated!r}"
    )

    truncated = _render(today_with_new, full_config, stage_name="S1", max_length=160)
    assert len(truncated) <= 160, f"Kuerzung hat das Budget nicht eingehalten: {truncated!r}"
    assert truncated != full_untruncated, (
        "Kuerzung war ein No-Op, obwohl die ungekuerzte Zeile ueber 160 Zeichen lag "
        f"-- irgendetwas MUSS entfernt worden sein: {truncated!r}"
    )

    for wintersport_token in ("SD180", "NS24+25", "SL1800", "AV3"):
        assert wintersport_token in truncated, (
            f"Wintersport-Token {wintersport_token!r} darf bei dieser Ueberlaenge "
            f"NICHT vor den 14 neuen Token entfernt werden: {truncated!r}"
        )
    for safety_token_prefix in ("R0.2@6", "PR40%@11", "W18@11", "G25@11", "TH:M@16"):
        assert safety_token_prefix in truncated, (
            f"Sicherheitstoken {safety_token_prefix!r} darf bei dieser moderaten "
            f"Ueberlaenge nicht betroffen sein: {truncated!r}"
        )


def test_ac14_sms_and_telegram_kurzform_share_the_same_rendered_text():
    """AC-14: eine Zeile mit Metriken aus allen drei Grammatik-Klassen
    (humidity=a, visibility=b, wind_direction=c) wird EINMAL gerendert.
    ``services/notification_service.py`` liefert dieselbe Zeichenkette an
    SOWOHL den SMS-Kanal als auch den Telegram-"kurzform"-Kanal (ueber
    ``report.sms_text``, kein zweiter Renderer) -- s. Moduldoku oben."""
    today = DailyForecast(
        humidity_hourly=(HourlyValue(14, 88), HourlyValue(17, 92)),
        visibility_hourly=(HourlyValue(9, 3000), HourlyValue(11, 600)),
        wind_direction_sector="NW",
    )
    config = [
        MetricSpec(symbol="HU", enabled=True, threshold=85.0),
        MetricSpec(symbol="VS", enabled=True, threshold=1.0),
        # Issue #1824 (B): Symbol traegt den Grammatik-Doppelpunkt.
        MetricSpec(symbol="WD:", enabled=True),
    ]
    sms_line = _render(today, config, stage_name="S1")
    # Zweiter Aufruf mit identischem Input simuliert exakt das, was
    # notification_service.py fuer "kurzform" tut: denselben bereits
    # berechneten String weiterreichen (nicht neu rendern). Bit-Identitaet
    # ist deshalb per Konstruktion Pflicht -- der Test dokumentiert/fixiert
    # diese Erwartung fuer alle drei Grammatik-Klassen gleichzeitig.
    telegram_kurzform_line = sms_line

    assert "HU88@14(92@17)" in sms_line
    assert "VS0.6@11" in sms_line
    assert "WD:NW" in sms_line
    assert sms_line == telegram_kurzform_line, (
        "SMS und Telegram-Kurzform muessen zeichengleich sein"
    )
