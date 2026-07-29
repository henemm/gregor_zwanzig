"""TDD RED -- Compare-Telegram bedient die volle Metrik-Auswahl (Scheibe S5a).

Spec: docs/specs/modules/compare_kanal_metriken.md (AC-1, AC-2, AC-4, AC-5,
AC-6, AC-7 -- jeweils nur der TELEGRAM-Teil dieser Kriterien; SMS/AC-3/AC-8
sind Scheibe S5b und NICHT Teil dieser Datei).
Analyse: docs/context/fix-1362-1399-compare-kurzformen.md

Ist-Zustand (comparison.py:380-436): `_CHANNEL_METRICS` ist eine feste
Sechserliste; `_channel_metric_cells()` bildet die SCHNITTMENGE aus
Nutzerauswahl und dieser Liste -- alles ausserhalb der sechs Groessen
verschwindet ersatzlos, ohne Hinweis (#1362). AC-6 ist ein reiner
NACHWEIS-Test fuer #1399 (mutmasslich bereits durch #1402 behoben) -- bleibt
er gruen, ist #1399 gegenstandslos; wird er rot, ist es doch ein Fehler und
wird an den Product Owner eskaliert statt stillschweigend gefixt.

Test-Politik (CLAUDE.md, Schicht "Kern"): rein deterministisch, KEINE Mocks
(kein Mock()/patch()/MagicMock), kein Netz, kein Versand. Alle Pruefungen
lesen den GERENDERTEN Telegram-Text (Nutzersicht), nicht den Code-Pfad.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timezone

from app.models import ForecastDataPoint, ThunderLevel
from app.user import ComparisonResult, LocationResult, SavedLocation
from output.metric_format import format_value
from output.renderers.comparison import render_compare_telegram
from services.official_alerts.models import OfficialAlert

# ---------------------------------------------------------------------------
# Bausteine -- echte Objekte, keine Mocks
# ---------------------------------------------------------------------------

TARGET_DATE = date(2026, 7, 27)
CREATED_AT = datetime(2026, 7, 27, 8, 0)


def _loc(
    loc_id: str, name: str, *, lat: float = 47.0, lon: float = 11.0,
    timezone_field: str | None = None,
) -> SavedLocation:
    return SavedLocation(
        id=loc_id, name=name, lat=lat, lon=lon, elevation_m=600,
        timezone=timezone_field,
    )


def _daily_points(
    *, dewpoint_c: float | None = None, pressure_msl_hpa: float | None = None,
    humidity_pct: int | None = None,
) -> list[ForecastDataPoint]:
    """24 Stundenpunkte mit neutralen Basiswerten -- Traeger fuer die drei
    Klasse-B-Aggregate (Taupunkt/Luftdruck/Luftfeuchtigkeit), die
    `_metric_value()` NUR live aus `hourly_data` ableitet
    (`_DAILY_AGGREGATE_FIELD`, `compare_html.py:440-455`; kein direktes
    `LocationResult`-Feld dafuer)."""
    points = []
    for hour in range(24):
        points.append(ForecastDataPoint(
            ts=datetime(TARGET_DATE.year, TARGET_DATE.month, TARGET_DATE.day, hour),
            t2m_c=15.0, wind10m_kmh=10.0, gust_kmh=15.0, precip_1h_mm=0.0,
            cloud_total_pct=50, thunder_level=ThunderLevel.NONE,
            visibility_m=10000, dewpoint_c=dewpoint_c,
            pressure_msl_hpa=pressure_msl_hpa, humidity_pct=humidity_pct,
        ))
    return points


def _result(locations: list[LocationResult]) -> ComparisonResult:
    return ComparisonResult(
        locations=locations, time_window=(0, 23), target_date=TARGET_DATE,
        created_at=CREATED_AT,
    )


def _location_cells(text: str, name: str) -> list[str]:
    """Zellen ("Label Wert"-Paare) des Ortsblocks `name` im Telegram-Text.

    Blockstruktur (`render_compare_telegram`): Ortsname-Zeile, danach genau
    eine Zeile "   Zelle1 · Zelle2 · ..." bzw. "   keine Werte"."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line == name:
            cell_line = lines[i + 1].strip()
            if cell_line == "keine Werte":
                return []
            return [c.strip() for c in cell_line.split(" · ")]
    raise AssertionError(f"Ortsblock {name!r} nicht gefunden in:\n{text}")


# ---------------------------------------------------------------------------
# AC-1 -- neue Groesse erscheint im Telegram
# ---------------------------------------------------------------------------

def test_metric_outside_old_six_appears_in_telegram_with_label_and_value():
    """AC-1: Taupunkt (ausserhalb von `_CHANNEL_METRICS`) muss mit Label und
    Wert im Ortsblock erscheinen -- heute verschwindet er ersatzlos, weil
    `_channel_metric_cells()` die Auswahl mit der festen Sechserliste
    schneidet (comparison.py:415-436)."""
    name = "Andermatt"
    loc = LocationResult(
        location=_loc("a", name), hourly_data=_daily_points(dewpoint_c=6.0),
    )
    text = render_compare_telegram(_result([loc]), enabled_metrics=["dewpoint_avg"])

    cells = _location_cells(text, name)
    expected_value = format_value("temperature", 6.0, style="plain")
    assert cells and any("Taupunkt" in c and expected_value in c for c in cells), (
        f"Ortsblock {name!r} zeigt Zellen {cells!r} (erwartet eine Zelle mit "
        f"'Taupunkt' und dem Wert {expected_value!r}). Taupunkt ('dewpoint_avg') liegt "
        "ausserhalb der heutigen Sechserliste (_CHANNEL_METRICS, comparison.py:380-387) "
        "und wird von der Schnittmenge in _channel_metric_cells() verworfen -- der "
        "Ortsblock zeigt stattdessen 'keine Werte'."
    )


# ---------------------------------------------------------------------------
# AC-2 -- Ueberlauf wird gezaehlt, nicht verschwiegen
# ---------------------------------------------------------------------------

def test_metric_overflow_shows_seven_cells_and_notice_naming_the_rest():
    """AC-2: 10 gewaehlte Groessen bei 7 Telegram-Zellen je Ort (max_table_cols
    = 8, ein Slot fuer die implizite Orts-Spalte) -> die 7 wichtigsten
    erscheinen, ein sichtbarer Hinweis nennt die Zahl der uebrigen (3).

    Ist-Zustand: die Schnittmenge mit der Sechserliste schneidet VOR jeder
    Prioritaets-Kappung ab -- von den 10 gewaehlten Groessen bleiben hoechstens
    die (bis zu sechs) alten uebrig, kein Ueberlauf-Hinweis existiert."""
    name = "Andermatt"
    loc = LocationResult(
        location=_loc("a", name),
        temp_max=10.0, wind_max=8.0, sunny_hours=3, cloud_avg=40,
        snow_depth_cm=20.0, snow_new_cm=5.0, wind_direction_avg=180,
        hourly_data=_daily_points(dewpoint_c=4.0, pressure_msl_hpa=1010.0, humidity_pct=70),
    )
    enabled = [
        "temp_max", "wind_max", "sunny_hours", "cloud_avg", "snow_depth_cm",
        "snow_new_cm", "dewpoint_avg", "pressure_avg", "humidity_avg",
        "wind_direction_avg",
    ]
    text = render_compare_telegram(_result([loc]), enabled_metrics=enabled)

    cells = _location_cells(text, name)
    assert len(cells) == 7, (
        f"Ortsblock {name!r} zeigt {len(cells)} Zellen ({cells!r}), erwartet 7 "
        "(Telegram-Limit max_table_cols=8, 1 Slot fuer die implizite Orts-Spalte). "
        "Heute schneidet die Schnittmenge mit der festen Sechserliste VOR jeder "
        "Prioritaets-Kappung ab, statt die vollen 10 zu priorisieren und erst bei 7 zu "
        "kappen (channel_layout.render_for_channel() wird gar nicht aufgerufen)."
    )
    assert "+3 weitere Wettergrößen" in text, (
        f"Telegram-Text enthaelt keinen Hinweis auf die 3 verdraengten Groessen "
        f"({text!r}) -- ein Ueberlauf darf nicht kommentarlos verschwinden (AC-2, "
        "analog dem bestehenden Orts-Ueberlauf-Hinweis `_telegram_notice`)."
    )


# ---------------------------------------------------------------------------
# AC-2 (Adversary-Fund, Gegenpruefung) -- eine gewaehlte Groesse OHNE Wert an
# diesem Ort darf keinen Zellen-Platz belegen UND muss getrennt gezaehlt
# werden. Invariante: sichtbare Zellen + Platzmangel-Zaehler +
# Ohne-Daten-Zaehler == Anzahl gewaehlter Groessen.
# ---------------------------------------------------------------------------

def test_metric_without_value_frees_its_slot_and_is_counted_separately():
    """Adversary-Fund (Gegenpruefung #1362): `gust_max`/`wind_chill_max` sind
    ausgewaehlt, haben an diesem Ort aber keinen Wert (auf `LocationResult`
    nicht gesetzt -- z.B. weil die Fallback-Kette dort ausgefallen ist).
    Vor dieser Korrektur belegte eine wertlose Groesse trotzdem einen der 7
    Telegram-Plaetze (weil die Prioritaetsliste VOR der Wert-Pruefung gebaut
    wurde) und verdraengte dabei eine andere, gueltige Groesse -- ohne dass
    der Ueberlauf-Zaehler (der nur Platzmangel kennt) das bemerkte. 5 der 10
    gewaehlten Groessen verschwanden dadurch spurlos.

    Aufbau: 10 gewaehlte Groessen, davon 8 mit Wert an diesem Ort (7 passen
    in die Zellen, 1 wird durch Platzmangel verdraengt) und 2 OHNE Wert
    (`gust_max`, `wind_chill_max` bleiben auf dem `LocationResult` ungesetzt,
    also `None` -- kein Aggregat-Feld, kein `hourly_data`-Ersatzwert)."""
    name = "Andermatt"
    loc = LocationResult(
        location=_loc("a", name),
        temp_max=10.0, wind_max=8.0, sunny_hours=3, cloud_avg=40,
        snow_depth_cm=20.0, snow_new_cm=5.0,
        # gust_max/wind_chill_max bleiben None -- kein Wert an diesem Ort.
        hourly_data=_daily_points(dewpoint_c=4.0, pressure_msl_hpa=1010.0),
    )
    enabled = [
        "temp_max", "wind_max", "sunny_hours", "cloud_avg", "snow_depth_cm",
        "snow_new_cm", "gust_max", "wind_chill_max", "dewpoint_avg",
        "pressure_avg",
    ]
    text = render_compare_telegram(_result([loc]), enabled_metrics=enabled)

    cells = _location_cells(text, name)
    visible = len(cells)
    overflow_match = re.search(r"\+(\d+) weitere Wettergrößen", text)
    no_data_match = re.search(r"\+(\d+) gewählte Wettergrößen ohne Wert", text)
    overflow = int(overflow_match.group(1)) if overflow_match else 0
    no_data = int(no_data_match.group(1)) if no_data_match else 0

    assert visible + overflow + no_data == len(enabled), (
        f"Invariante verletzt: sichtbare Zellen ({visible}) + Platzmangel-"
        f"Zaehler ({overflow}) + Ohne-Daten-Zaehler ({no_data}) = "
        f"{visible + overflow + no_data}, erwartet {len(enabled)} (Anzahl "
        f"gewaehlter Groessen). Text:\n{text!r}"
    )
    assert visible == 7, (
        f"Erwartet 7 sichtbare Zellen (die 8 Groessen MIT Wert werden auf "
        f"7 Plaetze gekappt), erhalten {visible} ({cells!r}). Wertlose "
        "Groessen (gust_max/wind_chill_max) duerfen keinen Platz belegen."
    )
    assert overflow == 1, (
        f"Erwartet genau 1 durch Platzmangel verdraengte Groesse (8 mit Wert "
        f"- 7 Plaetze), Regex fand {overflow}. Text:\n{text!r}"
    )
    assert no_data == 2, (
        f"Erwartet genau 2 Groessen ohne Wert an diesem Ort (gust_max, "
        f"wind_chill_max), Regex fand {no_data}. Text:\n{text!r}"
    )


# ---------------------------------------------------------------------------
# AC-4 (Telegram-Teil) -- Nutzer-Reihenfolge wirkt
# ---------------------------------------------------------------------------

def test_user_order_governs_telegram_cell_sequence_including_new_metric():
    """AC-4: zwei Auswahlen mit denselben zwei Groessen in umgekehrter
    Reihenfolge (eine davon ausserhalb der alten Sechserliste) -> die
    Zellfolge unterscheidet sich entsprechend.

    Ist-Zustand: Taupunkt wird komplett herausgefiltert -- beide Auswahlen
    liefern dieselbe (einzeilige) Zellfolge, unabhaengig von der Reihenfolge."""
    name = "Andermatt"
    loc = LocationResult(
        location=_loc("a", name), temp_max=10.0,
        hourly_data=_daily_points(dewpoint_c=5.0),
    )
    order_a = ["dewpoint_avg", "temp_max"]
    order_b = ["temp_max", "dewpoint_avg"]

    cells_a = _location_cells(
        render_compare_telegram(_result([loc]), enabled_metrics=order_a), name,
    )
    cells_b = _location_cells(
        render_compare_telegram(_result([loc]), enabled_metrics=order_b), name,
    )

    assert len(cells_a) == 2 and len(cells_b) == 2, (
        f"Erwartet je 2 Zellen (Taupunkt + Temp) fuer beide Reihenfolgen, erhalten "
        f"cells_a={cells_a!r} cells_b={cells_b!r} -- Taupunkt liegt ausserhalb der "
        "Sechserliste und wird unabhaengig von der Reihenfolge komplett verworfen."
    )
    assert cells_a[0].startswith("Taupunkt") and cells_a[1].startswith("Temp"), (
        f"Reihenfolge A (Taupunkt zuerst) liefert Zellen {cells_a!r} in falscher Folge."
    )
    assert cells_b[0].startswith("Temp") and cells_b[1].startswith("Taupunkt"), (
        f"Reihenfolge B (Temp zuerst) liefert Zellen {cells_b!r} in falscher Folge."
    )
    assert cells_a != cells_b, (
        f"Reihenfolge A {cells_a!r} und Reihenfolge B {cells_b!r} ergeben identische "
        "Zellfolgen -- die Nutzer-Reihenfolge wirkt sich nicht aus."
    )


# ---------------------------------------------------------------------------
# AC-5 (Telegram-Teil) -- reine Nicht-Sechser-Auswahl bleibt nicht leer
# ---------------------------------------------------------------------------

def test_selection_of_only_new_metrics_does_not_render_empty():
    """AC-5: Auswahl ausschliesslich aus Groessen ausserhalb der Sechserliste
    (Taupunkt, Luftdruck) -> beide Werte erscheinen -- heute liefert die
    Schnittmenge nichts, der Ortsblock zeigt faelschlich 'keine Werte'."""
    name = "Andermatt"
    loc = LocationResult(
        location=_loc("a", name),
        hourly_data=_daily_points(dewpoint_c=4.0, pressure_msl_hpa=1015.0),
    )
    text = render_compare_telegram(
        _result([loc]), enabled_metrics=["dewpoint_avg", "pressure_avg"],
    )

    assert "keine Werte" not in text, (
        f"Telegram-Text zeigt 'keine Werte', obwohl zwei Groessen mit gueltigen Werten "
        f"gewaehlt wurden: {text!r} -- die Schnittmenge mit der Sechserliste ist leer, "
        "weil weder Taupunkt noch Luftdruck darin vorkommen."
    )
    expected_dewpoint = format_value("temperature", 4.0, style="plain")
    expected_pressure = "1015 hPa"
    assert expected_dewpoint in text, (
        f"Telegram-Text enthaelt den Taupunkt-Wert {expected_dewpoint!r} nicht: {text!r}"
    )
    assert expected_pressure in text, (
        f"Telegram-Text enthaelt den Luftdruck-Wert {expected_pressure!r} nicht: {text!r}"
    )


# ---------------------------------------------------------------------------
# AC-6 -- Nachweis #1399: Telegram rechnet in Ortszeit (KEIN Bugfix-Test)
# ---------------------------------------------------------------------------

def test_telegram_alert_time_uses_location_timezone_not_utc():
    """AC-6: Ort OHNE gespeichertes `timezone`-Feld (nur Koordinaten,
    Europe/Vienna, UTC+2 im Juli) mit einer amtlichen Warnung 12:00-16:00 UTC.

    Erwartung: der Telegram-Warnblock zeigt die ORTSZEIT 14:00-18:00, nicht
    die Weltzeit 12:00-16:00 (`resolve_location_tz`/`location_tz`,
    comparison.py:504).

    NACHWEIS-Test (kein Bugfix): bleibt er GRUEN, ist #1399 bereits durch
    #1402 behoben und wird mit diesem Test geschlossen. Wird er ROT, ist es
    doch ein Fehler -- das Ergebnis geht an den Product Owner, OHNE
    stillschweigenden Fix in dieser Scheibe.
    """
    name = "Innsbruck"
    alert = OfficialAlert(
        source="meteoalarm", hazard="thunderstorm", level=3, label="Gewitter",
        valid_from=datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc),
        valid_to=datetime(2026, 7, 27, 16, 0, tzinfo=timezone.utc),
        region_label="Tirol",
    )
    loc = LocationResult(
        location=_loc("a", name, lat=47.27, lon=11.39, timezone_field=None),
        official_alerts=[alert],
    )
    text = render_compare_telegram(_result([loc]))

    assert "14:00" in text and "18:00" in text, (
        f"Telegram-Text = {text!r}; erwartet die ORTSZEIT-Stunden 14:00-18:00 (Warnung "
        "12:00-16:00 UTC, Europe/Vienna = UTC+2 im Juli, ueber Koordinaten aufgeloest -- "
        "kein gespeichertes `timezone`-Feld). Ist dieser Test ROT, ist #1399 NICHT durch "
        "#1402 behoben -- an den Product Owner eskalieren statt stillschweigend fixen."
    )
    assert "12:00" not in text and "16:00" not in text, (
        f"Telegram-Text = {text!r} zeigt weiterhin die Weltzeit-Stunden 12:00/16:00 UTC "
        "statt der Ortszeit 14:00/18:00."
    )


# ---------------------------------------------------------------------------
# AC-7 (Telegram-Teil) -- Regressionsschutz: die heutigen sechs Werte bleiben
# ---------------------------------------------------------------------------

def test_regression_original_six_metrics_values_unchanged():
    """AC-7: eine Auswahl exakt der heutigen sechs Groessen liefert
    unveraenderte WERTE (Labels duerfen sich aendern, s. Spec 'Sichtbare
    Wirkung'). Darf/soll bereits GRUEN sein -- Regressionsschutz, kein
    Bug-Nachweis."""
    name = "Andermatt"
    loc = LocationResult(
        location=_loc("a", name),
        temp_max=16.4, wind_max=12.0, sunny_hours=5, cloud_avg=42,
        snow_depth_cm=30.0, snow_new_cm=4.0,
    )
    enabled = [
        "temp_max", "wind_max", "sunny_hours", "cloud_avg", "snow_depth_cm",
        "snow_new_cm",
    ]
    text = render_compare_telegram(_result([loc]), enabled_metrics=enabled)

    expected_values = [
        format_value("temperature", 16.4, style="plain"),
        format_value("wind", 12.0, style="plain"),
        f"{format_value('sunshine', 5, style='bare')}h",
        format_value("cloud_total", 42, style="plain"),
        format_value("snow_depth", 30.0, style="plain"),
        "4 cm",
    ]
    for value in expected_values:
        assert value in text, (
            f"Telegram-Text {text!r} enthaelt den erwarteten Wert {value!r} nicht -- "
            "AC-7 verlangt unveraenderte WERTE fuer die heutigen sechs Groessen (Labels "
            "duerfen sich aendern)."
        )
