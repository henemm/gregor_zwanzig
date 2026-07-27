"""TDD RED — Ortsvergleich rechnet und beschriftet in ORTSZEIT statt Serverzeit.

Spec: docs/specs/modules/issue_1378_compare_zeitbasis.md (AC-1 … AC-10)
Analyse/Nachweis: docs/context/fix-1378-compare-zeitbasis.md

Belegter Defekt (echte Staging-Mail 2026-07-27): das Preset-Tagesfenster
"9 bis 16 Uhr" liefert bei einem Ort in `Europe/Vienna` (Sommer = UTC+2) die
Datenpunkte der Ortszeit-Stunden 11-18, beschriftet als 9-16. `dp.ts` ist per
Hausnorm naive UTC (`app/models.py:146-157`, #1345) -- Auswahl (`comparison_
engine._filter_by_target_date_and_window`), HTML-Beschriftung
(`compare_html._render_hour_row`), Klartext-Beschriftung
(`comparison.render_comparison_text`), Ausblick (`_build_location_outlook_rows`
/ `_group_by_calendar_day`), "Erstellt"-Kopfzeile und der SMS-`@Stunde`-Marker
lesen diese Rohstunde direkt.

Test-Politik (CLAUDE.md, Schicht "Kern"): rein deterministisch, KEINE Mocks
(kein Mock()/patch()/MagicMock), kein Netz, kein Mail-/SMS-Versand. Die einzige
Netz-Grenze der Engine (`fetch_forecast_for_location`) wird -- wie in
`test_comparison_engine_midnight_window.py` etabliert -- durch eine ECHTE
Funktion per Attribut-Rebind ersetzt und in `finally` restauriert.

Alle Pruefungen sind Nutzersicht: was steht in der gerenderten Mail / SMS,
nicht welche Funktion aufgerufen wurde.
"""
from __future__ import annotations

import os
import re
import time
from datetime import date, datetime, timedelta, timezone

import pytest

from app.models import ForecastDataPoint, ThunderLevel
from app.user import ComparisonResult, LocationResult, SavedLocation
from output.renderers.comparison import render_compare_email, render_compare_sms
from services.official_alerts.models import OfficialAlert

# 2026-07-27 ist ein Montag; Europe/Vienna liegt dann auf UTC+2 (Sommerzeit),
# America/Denver auf UTC-6. Beide Versaetze sind != 0 -- ein UTC+0-Ort wuerde
# den Defekt nicht sichtbar machen.
TARGET_DATE = date(2026, 7, 27)
CREATED_AT_UTC = datetime(2026, 7, 27, 4, 58)  # naive UTC, wie im Staging-Nachweis
VIENNA_OFFSET_H = 2
DENVER_OFFSET_H = -6

WINDOW = (9, 16)  # Preset-Tagesfenster aus dem Staging-Nachweis

_WEEKDAY_ABBR = ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So")


@pytest.fixture(autouse=True)
def _server_clock_is_utc():
    """Der Server laeuft auf `Etc/UTC` (Nachweis-Umgebung). `local_hour()` ruft
    `astimezone()` auf einem NAIVEN `dp.ts` auf -- das interpretiert die
    Prozess-Zeitzone. Ohne diese Fixierung waere der Test auf einer Maschine mit
    anderer TZ nicht reproduzierbar."""
    old = os.environ.get("TZ")
    os.environ["TZ"] = "UTC"
    time.tzset()
    try:
        yield
    finally:
        if old is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = old
        time.tzset()


# ---------------------------------------------------------------------------
# Bausteine — echte Objekte, keine Mocks
# ---------------------------------------------------------------------------

def _vienna_location(loc_id: str = "loc-ibk", name: str = "Innsbruck") -> SavedLocation:
    """Innsbruck: Koordinaten ergeben `Europe/Vienna`. `timezone=None` --
    genau der Zustand der drei Staging-Referenzorte (Analyse-Dokument)."""
    return SavedLocation(
        id=loc_id, name=name, lat=47.27, lon=11.39, elevation_m=574, timezone=None,
    )


def _denver_location(loc_id: str = "loc-asp", name: str = "Aspen") -> SavedLocation:
    """Aspen: Koordinaten ergeben `America/Denver` (UTC-6 im Sommer)."""
    return SavedLocation(
        id=loc_id, name=name, lat=39.19, lon=-106.82, elevation_m=2438, timezone=None,
    )


def _unresolvable_location(loc_id: str = "loc-nowhere") -> SavedLocation:
    """Koordinaten ausserhalb des gueltigen Bereichs -- `tz_for_coords()` faengt
    den ValueError von TimezoneFinder und faellt auf UTC zurueck (AC-7)."""
    return SavedLocation(
        id=loc_id, name="Nirgendwo", lat=91.0, lon=200.0, elevation_m=0, timezone=None,
    )


def _dp(ts: datetime, **kw) -> ForecastDataPoint:
    return ForecastDataPoint(ts=ts, **kw)


def _hour_points_for_local_window(offset_h: int) -> list[ForecastDataPoint]:
    """Ein Datenpunkt je ORTSZEIT-Stunde 9..16 des `TARGET_DATE`, abgelegt als
    naive UTC (`ts = Ortszeit - offset`). `t2m_c` ist je Stunde eindeutig
    (20°..27°) und traegt bewusst KEINE Stundenzahl -- so ist die Zuordnung
    "Zeile mit Wert X" <-> "Beschriftung Y" nicht mit dem Wert verwechselbar."""
    points = []
    for local_hour in range(WINDOW[0], WINDOW[1] + 1):
        ts_utc = datetime(
            TARGET_DATE.year, TARGET_DATE.month, TARGET_DATE.day, local_hour,
        ) - timedelta(hours=offset_h)
        points.append(_dp(ts_utc, t2m_c=float(20 + local_hour - WINDOW[0])))
    return points


def _three_day_hourly_profile() -> list[ForecastDataPoint]:
    """72 Datenpunkte (TARGET_DATE-1 .. TARGET_DATE+1, je 00-23 UTC).
    `t2m_c` kodiert (Tagesversatz, UTC-Stunde) eindeutig, damit ein Punkt vom
    falschen Kalendertag am Wert erkennbar ist."""
    points = []
    for day_offset in (-1, 0, 1):
        day = TARGET_DATE + timedelta(days=day_offset)
        for hour in range(24):
            points.append(_dp(
                datetime(day.year, day.month, day.day, hour),
                t2m_c=float(day_offset * 100 + hour),
            ))
    return points


def _result(
    loc_results: list[LocationResult], *, created_at: datetime = CREATED_AT_UTC,
) -> ComparisonResult:
    return ComparisonResult(
        locations=loc_results, time_window=WINDOW, target_date=TARGET_DATE,
        created_at=created_at,
    )


def _run_engine(locations: list[SavedLocation], window: tuple[int, int]):
    """Echte `ComparisonEngine.run()` mit aufgezeichnetem 3-Tage-Profil.
    `official_alerts_enabled=False` -> strukturell kein MeteoAlarm-Fetch."""
    import services.comparison_engine as ce_mod

    original_fetch = ce_mod.fetch_forecast_for_location

    def recorded_fetch(location, hours=96, settings=None):  # echte Funktion
        return {
            "location": location, "error": None, "forecast_hours": hours,
            "snow_source": None, "raw_data": _three_day_hourly_profile(),
        }

    ce_mod.fetch_forecast_for_location = recorded_fetch
    try:
        return ce_mod.ComparisonEngine.run(
            locations=locations, time_window=window, target_date=TARGET_DATE,
            official_alerts_enabled=False,
        )
    finally:
        ce_mod.fetch_forecast_for_location = original_fetch


# ---------------------------------------------------------------------------
# Ableser — lesen die GERENDERTE Mail, nicht den Code
# ---------------------------------------------------------------------------

_HOUR_ROW_RE = re.compile(r'<tr style="border-bottom:1px solid #f0ece1;">(.*?)</tr>')
_CELL_RE = re.compile(r'<td[^>]*>(.*?)</td>')
_ORT_SPLIT = 'letter-spacing:0.1em;">ORT</span>'


def _html_hour_rows(html: str) -> list[tuple[str, str]]:
    """(Zeit-Beschriftung, erster Wert) je Zeile der HTML-Stundentabelle.
    Der Aufrufer rendert mit `hourly_metrics=["t2m_c"]`, deshalb genau 2 Zellen
    je Zeile -- die Uebersichts-Zeilen (Label + Wert) werden ueber die
    Stunden-Beschriftung `^\\d{2}$` ausgeschlossen."""
    rows = []
    for row in _HOUR_ROW_RE.findall(html):
        cells = _CELL_RE.findall(row)
        if len(cells) == 2 and re.fullmatch(r"\d{2}", cells[0]):
            rows.append((cells[0], cells[1]))
    return rows


def _html_hour_rows_by_location(html: str) -> dict[str, list[tuple[str, str]]]:
    """Stundenzeilen je Ortsblock der STUNDEN-Sektion (Reihenfolge = Mail)."""
    tail = html.split(">STUNDEN</span>", 1)
    if len(tail) < 2:
        return {}
    out: dict[str, list[tuple[str, str]]] = {}
    for chunk in tail[1].split(_ORT_SPLIT)[1:]:
        m = re.search(r'color:#1a1a18;">(.*?)</span>', chunk)
        if m:
            out[m.group(1)] = _html_hour_rows(chunk)
    return out


def _plain_hour_rows(text: str) -> list[tuple[str, str]]:
    """(Zeit-Beschriftung, Wert) je Zeile der KLARTEXT-Stundentabelle."""
    rows = []
    for line in text.splitlines():
        m = re.match(r"^\s{3}(\d{2}:\d{2})\s+Temp\s+(\S+)\s*$", line)
        if m:
            rows.append((m.group(1), m.group(2)))
    return rows


def _html_created_value(html: str) -> str:
    """Wert der 'Erstellt'-Kachel der HTML-Kopfzeile (Desktop-Variante)."""
    hits = re.findall(r"Erstellt</div><div[^>]*>(.*?)</div>", html)
    assert hits, "HTML-Kopfzeile enthaelt keine 'Erstellt'-Kachel"
    return hits[0]


def _plain_created_value(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("Erstellt:"):
            return line[len("Erstellt:"):].strip()
    raise AssertionError("Klartext-Teil enthaelt keine 'Erstellt:'-Zeile")


def _html_outlook_rows(html: str) -> list[list[str]]:
    """Die Tageszeilen der HTML-Ausblick-Tabelle (8 Zellen, erste = Wochentag)."""
    rows = []
    for row in re.findall(r"<tr>(.*?)</tr>", html):
        cells = _CELL_RE.findall(row)
        if len(cells) == 8 and cells[0] in _WEEKDAY_ABBR:
            rows.append(cells)
    return rows


def _html_location_headings(html: str) -> dict[str, str]:
    """Ortsname -> vollstaendige Ueberschrift des Ortsblocks der STUNDEN-Sektion.

    Gelesen wird der Text zwischen dem `ORT`-Eyebrow und dem Beginn der
    Stundentabelle -- also genau das, was ueber der Tabelle steht und ihre
    Zeitbasis anschreiben muss."""
    tail = html.split(">STUNDEN</span>", 1)
    if len(tail) < 2:
        return {}
    out: dict[str, str] = {}
    for chunk in tail[1].split(_ORT_SPLIT)[1:]:
        heading_html = chunk.split("<table", 1)[0]
        name_m = re.search(r'color:#1a1a18;">(.*?)</span>', heading_html)
        if name_m:
            out[name_m.group(1)] = re.sub(r"<[^>]+>", " ", heading_html)
    return out


def _plain_location_headings(text: str) -> dict[str, str]:
    """Ortsname -> Ueberschriftszeile des Ortsblocks im KLARTEXT-Stundenverlauf."""
    if "STUNDENVERLAUF" not in text:
        return {}
    section = text.split("STUNDENVERLAUF", 1)[1]
    out: dict[str, str] = {}
    for line in section.splitlines():
        # Ortsueberschriften stehen ohne Einrueckung, Datenzeilen mit drei Leerzeichen.
        if line and not line.startswith(" ") and not line.startswith("-"):
            name = line.split("(")[0].strip()
            if name:
                out[name] = line
    return out


_TZ_MARKER_RE = re.compile(
    r"MESZ|MEZ|CEST|CET|UTC\s*\+\s*0?2|GMT\s*\+\s*0?2|\+\s*02:?0?0?|\(\s*\+2\s*\)",
    re.IGNORECASE,
)
_UTC_MARKER_RE = re.compile(r"UTC|GMT|Z\b|\+00:?00", re.IGNORECASE)


# ---------------------------------------------------------------------------
# AC-1 — Stundenauswahl folgt der Ortszeit
# ---------------------------------------------------------------------------

def test_engine_window_selects_local_hours_not_server_hours():
    """AC-1: Fenster 9-16 Uhr, Ort in Europe/Vienna (UTC+2).

    Erwartet: die gewaehlten Datenpunkte sind die ORTSZEIT-Stunden 9..16 des
    Zieltages -- das sind die UTC-Stunden 7..14 (unabhaengig hergeleitet, nicht
    ueber dieselbe Umrechnungsfunktion). Ist-Zustand: UTC-Stunden 9..16 (das
    waeren Ortszeit 11..18, der belegte +2h-Versatz).
    """
    result = _run_engine([_vienna_location()], WINDOW)
    loc_result = result.locations[0]

    utc_hours = sorted(dp.ts.hour for dp in loc_result.hourly_data)
    utc_dates = {dp.ts.date() for dp in loc_result.hourly_data}
    expected_utc_hours = list(range(WINDOW[0] - VIENNA_OFFSET_H, WINDOW[1] - VIENNA_OFFSET_H + 1))

    assert utc_hours == expected_utc_hours, (
        f"Fenster {WINDOW[0]}-{WINDOW[1]} Uhr ORTSZEIT (Europe/Vienna, UTC+2) muss die "
        f"UTC-Stunden {expected_utc_hours} auswaehlen, ausgewaehlt wurden aber {utc_hours}. "
        "Die Auswahl laeuft auf der rohen Serverzeit (dp.ts.hour) statt auf der Ortszeit."
    )
    assert utc_dates == {TARGET_DATE}, (
        f"Alle gewaehlten Punkte muessen zum Ortstag {TARGET_DATE} gehoeren, "
        f"erhalten wurden Kalendertage {sorted(utc_dates)}."
    )
    # t2m_c kodiert (Tagesversatz*100 + UTC-Stunde): Zieltag -> 7.0 .. 14.0
    temps = sorted(dp.t2m_c for dp in loc_result.hourly_data)
    assert temps == [float(h) for h in expected_utc_hours], (
        f"Werte der gewaehlten Punkte: {temps} -- erwartet "
        f"{[float(h) for h in expected_utc_hours]} (Werte kodieren Tag+UTC-Stunde)."
    )


# ---------------------------------------------------------------------------
# AC-2 — HTML-Stundenbeschriftung
# ---------------------------------------------------------------------------

def test_html_hour_labels_show_local_hour_of_the_datapoint():
    """AC-2: die Zeile, die den Wert des Datenpunkts 07:00 UTC zeigt, traegt bei
    einem Ort in Europe/Vienna die Beschriftung '09' (= 09:00 Ortszeit).

    Wertkodierung: Ortszeit 9 Uhr -> 20°, 10 Uhr -> 21°, ... 16 Uhr -> 27°.
    """
    loc_result = LocationResult(
        location=_vienna_location(),
        hourly_data=_hour_points_for_local_window(VIENNA_OFFSET_H),
    )
    html, _text = render_compare_email(
        _result([loc_result]), hourly_metrics=["t2m_c"], outlook_enabled=False,
    )

    rows = _html_hour_rows(html)
    expected = [
        (f"{h:02d}", f"{20 + h - WINDOW[0]}°") for h in range(WINDOW[0], WINDOW[1] + 1)
    ]
    assert rows == expected, (
        f"HTML-Stundenzeilen (Beschriftung, Wert) = {rows}\nerwartet = {expected}\n"
        "Die Beschriftung kommt aus der Serverzeit (dp.ts.strftime('%H')) statt aus der "
        "Ortszeit des Ortes (Europe/Vienna, UTC+2)."
    )


# ---------------------------------------------------------------------------
# AC-3 — Klartext-Stundenbeschriftung (blinder Fleck des Pflicht-Validators)
# ---------------------------------------------------------------------------

def test_plaintext_hour_labels_show_local_hour_of_the_datapoint():
    """AC-3: derselbe Nachweis eigenstaendig im KLARTEXT-Teil.

    `email_spec_validator.py` liest laut docs/reference/mail_validators.md nur
    den HTML-Teil -- in Scheibe B (#1366) ist genau hier ein Defekt
    durchgerutscht. Deshalb ein eigener Test, kein Anhaengsel an AC-2.
    """
    loc_result = LocationResult(
        location=_vienna_location(),
        hourly_data=_hour_points_for_local_window(VIENNA_OFFSET_H),
    )
    _html, text = render_compare_email(
        _result([loc_result]), hourly_metrics=["t2m_c"], outlook_enabled=False,
    )

    rows = _plain_hour_rows(text)
    expected = [
        (f"{h:02d}:00", f"{20 + h - WINDOW[0]}°") for h in range(WINDOW[0], WINDOW[1] + 1)
    ]
    assert rows == expected, (
        f"Klartext-Stundenzeilen (Beschriftung, Wert) = {rows}\nerwartet = {expected}\n"
        "Der Klartext-Teil beschriftet weiterhin mit der Serverzeit "
        "(dp.ts.strftime('%H:%M'))."
    )


def test_plaintext_and_html_hour_labels_are_identical_in_the_same_mail():
    """AC-3 (Paritaet): beide Teile DERSELBEN Mail zeigen Zeile fuer Zeile
    dieselbe Beschriftung zum selben Wert."""
    loc_result = LocationResult(
        location=_vienna_location(),
        hourly_data=_hour_points_for_local_window(VIENNA_OFFSET_H),
    )
    html, text = render_compare_email(
        _result([loc_result]), hourly_metrics=["t2m_c"], outlook_enabled=False,
    )

    html_rows = [(hh, val) for hh, val in _html_hour_rows(html)]
    plain_rows = [(hhmm.split(":")[0], val) for hhmm, val in _plain_hour_rows(text)]
    assert html_rows == plain_rows, (
        f"HTML-Zeilen {html_rows} != Klartext-Zeilen {plain_rows} -- beide Teile "
        "derselben Mail muessen dieselbe Zeitbasis zeigen."
    )
    assert html_rows and html_rows[0][0] == f"{WINDOW[0]:02d}", (
        f"Erste Stundenzeile traegt die Beschriftung {html_rows[0][0] if html_rows else None!r}, "
        f"erwartet {WINDOW[0]:02d} (Ortszeit-Fensterbeginn)."
    )


# ---------------------------------------------------------------------------
# AC-4 — "Erstellt"-Kopfzeile in beiden Mail-Teilen
# ---------------------------------------------------------------------------

def test_created_header_shows_local_time_of_first_configured_location():
    """AC-4: 'Erstellt' zeigt in HTML UND Klartext die Ortszeit des
    ERSTGENANNTEN Ortes (konfigurierte Reihenfolge, NICHT alphabetisch, #1359)
    plus erkennbares Zeitzonen-Kuerzel/-Offset.

    Erzeugungszeit 04:58 UTC -> 06:58 in Europe/Vienna (erster Ort) bzw.
    22:58 des Vortages in America/Denver (zweiter Ort, alphabetisch VOR dem
    ersten -- eine alphabetische Sortierung waere daran erkennbar).
    """
    first = LocationResult(
        location=_vienna_location(name="Zillertal"),
        hourly_data=_hour_points_for_local_window(VIENNA_OFFSET_H),
    )
    second = LocationResult(
        location=_denver_location(name="Aspen"),
        hourly_data=_hour_points_for_local_window(DENVER_OFFSET_H),
    )
    html, text = render_compare_email(
        _result([first, second]), hourly_metrics=["t2m_c"], outlook_enabled=False,
    )

    html_created = _html_created_value(html)
    plain_created = _plain_created_value(text)

    for part, value in (("HTML", html_created), ("Klartext", plain_created)):
        assert "06:58" in value, (
            f"{part}-Kopfzeile 'Erstellt' = {value!r}; erwartet 06:58 (04:58 UTC in "
            "Europe/Vienna, Ortszeit des erstgenannten Ortes 'Zillertal')."
        )
        assert "04:58" not in value, (
            f"{part}-Kopfzeile 'Erstellt' = {value!r} zeigt weiterhin die Serverzeit 04:58."
        )
        assert "22:58" not in value, (
            f"{part}-Kopfzeile 'Erstellt' = {value!r} nutzt die Zeitzone des alphabetisch "
            "ersten Ortes 'Aspen' statt des erstgenannten Ortes der konfigurierten "
            "Reihenfolge (#1359)."
        )
        assert _TZ_MARKER_RE.search(value), (
            f"{part}-Kopfzeile 'Erstellt' = {value!r} nennt keine erkennbare Zeitbasis "
            "(Kuerzel wie MESZ/CEST oder Offset wie UTC+2) -- eine nackte Uhrzeit laesst "
            "den Empfaenger im Unklaren, welche Zeit gemeint ist."
        )


# ---------------------------------------------------------------------------
# AC-5 — 3-Tage-Ausblick ohne gespeicherte Zeitzone
# ---------------------------------------------------------------------------

def test_outlook_resolves_timezone_from_coordinates_without_stored_field():
    """AC-5: Ort ohne `SavedLocation.timezone`, aber mit aufloesbaren
    Koordinaten -> der Ausblick nutzt die koordinaten-aufgeloeste Ortszeit,
    kein stiller UTC-Rueckfall.

    Sichtbare Stelle im Ausblick ist die Gewitter-Zelle ('mittel @h', vgl.
    email/outlook.py). Das Gewitter liegt auf 09:00 UTC = 11:00 Ortszeit.
    """
    points = []
    for hour in range(24):
        points.append(_dp(
            datetime(TARGET_DATE.year, TARGET_DATE.month, TARGET_DATE.day, hour),
            t2m_c=15.0, precip_1h_mm=0.0, wind10m_kmh=5.0, gust_kmh=6.0,
            thunder_level=ThunderLevel.MED if hour == 9 else ThunderLevel.NONE,
        ))
    loc_result = LocationResult(
        location=_vienna_location(), hourly_data=[], outlook_hourly_data=points,
    )
    html, _text = render_compare_email(
        _result([loc_result]), hourly_metrics=["t2m_c"],
        hourly_enabled=False, outlook_enabled=True,
    )

    rows = _html_outlook_rows(html)
    assert rows, f"Kein Ausblick gerendert: {html[:400]!r}"
    gew_cell = rows[0][7]
    assert gew_cell == "mittel @11", (
        f"Ausblick-Gewitterzelle = {gew_cell!r}, erwartet 'mittel @11' -- der Datenpunkt "
        "liegt auf 09:00 UTC, das sind 11:00 Ortszeit (Europe/Vienna). Ohne gespeichertes "
        "`timezone`-Feld faellt der Ausblick still auf UTC zurueck, statt die Koordinaten "
        "aufzuloesen."
    )


# ---------------------------------------------------------------------------
# AC-9 — Tagesgrenze des Ausblicks liegt auf Orts-Mitternacht
# ---------------------------------------------------------------------------

def test_outlook_day_grouping_uses_local_midnight_not_utc_midnight():
    """AC-9: ein Datenpunkt zwischen 22:00 und 23:59 UTC gehoert bei UTC+2
    bereits zum FOLGENDEN Ortstag.

    Aufbau (Werte je Ortstag klar getrennt):
      Mo (Ortstag 27.07.): 20:00/21:00 UTC -> 22:00/23:00 Ortszeit, 10°/11°
      Di (Ortstag 28.07.): 22:00/23:00 UTC (=00:00/01:00 Ortszeit) 30°/31°
                           plus 00:00-02:00 UTC des 28. -> 32°/33°/34°
    Bei UTC-Gruppierung erhaelt die Mo-Zeile faelschlich 10°..31°.
    """
    spec = [
        (datetime(2026, 7, 27, 20), 10.0), (datetime(2026, 7, 27, 21), 11.0),
        (datetime(2026, 7, 27, 22), 30.0), (datetime(2026, 7, 27, 23), 31.0),
        (datetime(2026, 7, 28, 0), 32.0), (datetime(2026, 7, 28, 1), 33.0),
        (datetime(2026, 7, 28, 2), 34.0),
    ]
    points = [
        _dp(ts, t2m_c=t, precip_1h_mm=0.0, wind10m_kmh=5.0, gust_kmh=6.0,
            thunder_level=ThunderLevel.NONE)
        for ts, t in spec
    ]
    loc_result = LocationResult(
        location=_vienna_location(), hourly_data=[], outlook_hourly_data=points,
    )
    html, _text = render_compare_email(
        _result([loc_result]), hourly_metrics=["t2m_c"],
        hourly_enabled=False, outlook_enabled=True,
    )

    rows = _html_outlook_rows(html)
    assert rows, f"Kein Ausblick gerendert: {html[:400]!r}"
    by_weekday = {r[0]: r for r in rows}
    assert "Mo" in by_weekday, f"Ausblick-Zeilen {rows} enthalten keinen Montag."

    mo_min, mo_max = by_weekday["Mo"][1], by_weekday["Mo"][2]
    assert (mo_min, mo_max) == ("10°", "11°"), (
        f"Ausblick-Zeile 'Mo' zeigt {mo_min}/{mo_max}, erwartet 10°/11°. Die Punkte "
        "22:00 und 23:00 UTC liegen bereits am ORTSTAG Dienstag (00:00/01:00 Ortszeit) "
        "und duerfen den Montag nicht mehr beeinflussen -- die Tagesgrenze laeuft noch "
        "auf UTC-Mitternacht."
    )
    assert "Di" in by_weekday, f"Ausblick-Zeilen {rows} enthalten keinen Dienstag."
    di_min, di_max = by_weekday["Di"][1], by_weekday["Di"][2]
    assert (di_min, di_max) == ("30°", "34°"), (
        f"Ausblick-Zeile 'Di' zeigt {di_min}/{di_max}, erwartet 30°/34° (alle fuenf "
        "Punkte des Ortstages Dienstag)."
    )


# ---------------------------------------------------------------------------
# AC-6 — zwei Orte, zwei Zeitzonen, ein Fenster
# ---------------------------------------------------------------------------

def test_two_locations_in_different_timezones_each_use_their_own_local_hours():
    """AC-6: dasselbe Fenster 9-16 Uhr an einem UTC+2- und einem UTC-6-Ort.

    Jeder Ortsblock zeigt seine EIGENEN Ortszeit-Stunden -- die absoluten
    (UTC-)Zeitpunkte der beiden Bloecke unterscheiden sich dadurch bewusst.
    """
    vienna = _vienna_location(name="Innsbruck")
    denver = _denver_location(name="Aspen")
    result = _run_engine([vienna, denver], WINDOW)

    by_name = {lr.location.name: lr for lr in result.locations}
    vienna_utc = sorted(dp.ts.hour for dp in by_name["Innsbruck"].hourly_data)
    denver_utc = sorted(dp.ts.hour for dp in by_name["Aspen"].hourly_data)

    assert vienna_utc == list(range(7, 15)), (
        f"Innsbruck (UTC+2): Ortszeit 9-16 Uhr entspricht UTC 7-14, ausgewaehlt wurden "
        f"UTC-Stunden {vienna_utc}."
    )
    assert denver_utc == list(range(15, 23)), (
        f"Aspen (UTC-6): Ortszeit 9-16 Uhr entspricht UTC 15-22, ausgewaehlt wurden "
        f"UTC-Stunden {denver_utc}."
    )

    html, _text = render_compare_email(
        result, hourly_metrics=["t2m_c"], outlook_enabled=False,
    )
    blocks = _html_hour_rows_by_location(html)
    expected_labels = [f"{h:02d}" for h in range(WINDOW[0], WINDOW[1] + 1)]
    for name in ("Innsbruck", "Aspen"):
        labels = [hh for hh, _v in blocks.get(name, [])]
        assert labels == expected_labels, (
            f"Ortsblock {name!r} zeigt die Stundenbeschriftungen {labels}, erwartet "
            f"{expected_labels} (eigenes Ortszeit-Fenster je Ort)."
        )


# ---------------------------------------------------------------------------
# AC-7 — nicht aufloesbare Zeitzone bleibt erkennbar UTC
# ---------------------------------------------------------------------------

def test_unresolvable_coordinates_are_marked_as_utc_in_both_mail_parts():
    """AC-7: laesst sich die Zeitzone weder aus `SavedLocation.timezone` noch
    aus den Koordinaten bestimmen, muss die Anzeige ERKENNBAR auf UTC
    zurueckfallen -- statt unmarkiert eine falsche Ortszeit vorzutaeuschen.
    """
    loc_result = LocationResult(
        location=_unresolvable_location(),
        hourly_data=_hour_points_for_local_window(0),
    )
    html, text = render_compare_email(
        _result([loc_result]), hourly_metrics=["t2m_c"], outlook_enabled=False,
    )

    html_created = _html_created_value(html)
    plain_created = _plain_created_value(text)
    for part, value in (("HTML", html_created), ("Klartext", plain_created)):
        assert "04:58" in value, (
            f"{part}-Kopfzeile 'Erstellt' = {value!r}; ohne aufloesbare Zeitzone bleibt "
            "die Erzeugungszeit 04:58 (UTC)."
        )
        assert _UTC_MARKER_RE.search(value), (
            f"{part}-Kopfzeile 'Erstellt' = {value!r} traegt kein erkennbares "
            "UTC-Kennzeichen -- der Rueckfall auf Serverzeit bleibt fuer den Empfaenger "
            "unsichtbar und sieht wie eine Ortszeit aus."
        )


def test_each_location_block_names_its_own_time_basis():
    """AC-7 (Adversary F002): zwei Orte, EINER davon nicht aufloesbar.

    Der Ein-Ort-Test oben kann diese Luecke bauartbedingt nicht sehen: dort
    faellt die ganze Mail auf UTC zurueck, und die 'Erstellt'-Kopfzeile (die
    ausschliesslich die Zeitzone des ERSTgenannten Ortes nennt) trifft damit
    zufaellig auch fuer den einzigen Ort zu. Bei zwei Orten sagt sie ueber den
    zweiten nichts mehr aus -- beide Stundentabellen zeigen '09'..'16', ohne
    dass der Leser erkennen kann, dass die eine Ortszeit und die andere
    Serverzeit meint.

    Hergeleitet:
      Zillertal   lat 47.27 / lon 11.39 -> Europe/Vienna, Juli -> Kuerzel CEST
      Nirgendwo   lat 91.0 / lon 200.0  -> nicht aufloesbar -> Kuerzel UTC
    """
    resolvable = LocationResult(
        location=_vienna_location(name="Zillertal"),
        hourly_data=_hour_points_for_local_window(VIENNA_OFFSET_H),
    )
    unresolvable = LocationResult(
        location=_unresolvable_location(),
        hourly_data=_hour_points_for_local_window(0),
    )
    html, text = render_compare_email(
        _result([resolvable, unresolvable]), hourly_metrics=["t2m_c"],
        outlook_enabled=False,
    )

    for part, headings in (
        ("HTML", _html_location_headings(html)),
        ("Klartext", _plain_location_headings(text)),
    ):
        assert "Zillertal" in headings and "Nirgendwo" in headings, (
            f"{part}: Ortsblock-Ueberschriften nicht gefunden: {sorted(headings)}"
        )
        assert "CEST" in headings["Zillertal"], (
            f"{part}-Ueberschrift des Ortsblocks 'Zillertal' = {headings['Zillertal']!r} "
            "nennt seine Zeitbasis nicht (erwartet das Kuerzel CEST)."
        )
        assert _UTC_MARKER_RE.search(headings["Nirgendwo"]), (
            f"{part}-Ueberschrift des Ortsblocks 'Nirgendwo' = {headings['Nirgendwo']!r} "
            "traegt kein erkennbares UTC-Kennzeichen. Beide Stundentabellen zeigen "
            "'09'..'16' -- ohne Anschrift haelt der Empfaenger die Serverzeit-Tabelle "
            "fuer eine Ortszeit-Tabelle (AC-7 gilt je Ort, nicht nur fuer den "
            "erstgenannten)."
        )
        assert "CEST" not in headings["Nirgendwo"], (
            f"{part}-Ueberschrift {headings['Nirgendwo']!r} uebernimmt die Zeitzone des "
            "ERSTgenannten Ortes statt der eigenen."
        )


def test_two_resolvable_zones_each_block_is_labelled_with_its_own_zone():
    """AC-6 (Adversary F002): zwei Orte in VERSCHIEDENEN, beide aufloesbaren
    Zonen. Beide Bloecke zeigen dieselben Stunden-Beschriftungen 09..16, meinen
    damit aber verschiedene absolute Zeitpunkte -- ohne Anschrift je Block ist
    die Mail an dieser Stelle irrefuehrend.

    Hergeleitet:
      Innsbruck lat 47.27 / lon 11.39   -> Europe/Vienna,  Juli -> CEST
      Aspen     lat 39.19 / lon -106.82 -> America/Denver, Juli -> MDT
    """
    vienna = LocationResult(
        location=_vienna_location(name="Innsbruck"),
        hourly_data=_hour_points_for_local_window(VIENNA_OFFSET_H),
    )
    denver = LocationResult(
        location=_denver_location(name="Aspen"),
        hourly_data=_hour_points_for_local_window(DENVER_OFFSET_H),
    )
    html, text = render_compare_email(
        _result([vienna, denver]), hourly_metrics=["t2m_c"], outlook_enabled=False,
    )

    # Vorbedingung: beide Bloecke zeigen wirklich dieselben Beschriftungen.
    blocks = _html_hour_rows_by_location(html)
    expected_labels = [f"{h:02d}" for h in range(WINDOW[0], WINDOW[1] + 1)]
    for name in ("Innsbruck", "Aspen"):
        assert [hh for hh, _v in blocks.get(name, [])] == expected_labels, (
            f"Vorbedingung: Ortsblock {name!r} muss die Stunden {expected_labels} zeigen."
        )

    for part, headings in (
        ("HTML", _html_location_headings(html)),
        ("Klartext", _plain_location_headings(text)),
    ):
        assert "CEST" in headings.get("Innsbruck", ""), (
            f"{part}-Ueberschrift 'Innsbruck' = {headings.get('Innsbruck')!r} nennt die "
            "Zeitzone Europe/Vienna (CEST) nicht."
        )
        assert "MDT" in headings.get("Aspen", ""), (
            f"{part}-Ueberschrift 'Aspen' = {headings.get('Aspen')!r} nennt die Zeitzone "
            "America/Denver (MDT) nicht -- beide Bloecke zeigen 09..16, ohne Anschrift "
            "haelt der Empfaenger sie faelschlich fuer zeitgleich (AC-6)."
        )
        assert "CEST" not in headings.get("Aspen", ""), (
            f"{part}-Ueberschrift 'Aspen' = {headings.get('Aspen')!r} traegt die Zone des "
            "erstgenannten Ortes."
        )


# ---------------------------------------------------------------------------
# AC-8 — Gegenprobe: EINE Zeitbasis in EINER Mail
# ---------------------------------------------------------------------------

def test_single_mail_uses_one_time_basis_across_hours_outlook_and_header():
    """AC-8: Stundenzeile, 3-Tage-Ausblick und 'Erstellt'-Kopfzeile derselben
    Mail nennen dieselbe Zeitbasis (Europe/Vienna). Keine Stelle darf noch
    Serverzeit zeigen, waehrend eine andere schon Ortszeit zeigt."""
    outlook_points = []
    for hour in range(24):
        outlook_points.append(_dp(
            datetime(TARGET_DATE.year, TARGET_DATE.month, TARGET_DATE.day, hour),
            t2m_c=15.0, precip_1h_mm=0.0, wind10m_kmh=5.0, gust_kmh=6.0,
            thunder_level=ThunderLevel.MED if hour == 9 else ThunderLevel.NONE,
        ))
    loc_result = LocationResult(
        location=_vienna_location(),
        hourly_data=_hour_points_for_local_window(VIENNA_OFFSET_H),
        outlook_hourly_data=outlook_points,
    )
    html, text = render_compare_email(
        _result([loc_result]), hourly_metrics=["t2m_c"], outlook_enabled=True,
    )

    findings: list[str] = []

    html_labels = [hh for hh, _v in _html_hour_rows(html)]
    if html_labels != [f"{h:02d}" for h in range(WINDOW[0], WINDOW[1] + 1)]:
        findings.append(f"HTML-Stundenzeilen: {html_labels} (erwartet 09..16 Ortszeit)")

    plain_labels = [hh.split(":")[0] for hh, _v in _plain_hour_rows(text)]
    if plain_labels != [f"{h:02d}" for h in range(WINDOW[0], WINDOW[1] + 1)]:
        findings.append(f"Klartext-Stundenzeilen: {plain_labels} (erwartet 09..16 Ortszeit)")

    outlook_rows = _html_outlook_rows(html)
    gew = outlook_rows[0][7] if outlook_rows else "<keine Ausblick-Zeile>"
    if gew != "mittel @11":
        findings.append(f"Ausblick-Gewitterzelle: {gew!r} (erwartet 'mittel @11' Ortszeit)")

    html_created = _html_created_value(html)
    if "06:58" not in html_created:
        findings.append(f"HTML-Kopfzeile 'Erstellt': {html_created!r} (erwartet 06:58 Ortszeit)")
    plain_created = _plain_created_value(text)
    if "06:58" not in plain_created:
        findings.append(
            f"Klartext-Kopfzeile 'Erstellt': {plain_created!r} (erwartet 06:58 Ortszeit)"
        )

    assert not findings, (
        "Dieselbe Mail nennt verschiedene Zeitbasen -- folgende Stellen zeigen nicht die "
        "Ortszeit (Europe/Vienna, UTC+2):\n  - " + "\n  - ".join(findings)
    )


# ---------------------------------------------------------------------------
# AC-10 — Compare-SMS `@Stunde` (deterministisch, KEIN Versand)
# ---------------------------------------------------------------------------

def test_compare_sms_warn_marker_hour_uses_coordinate_resolved_timezone():
    """AC-10: Ort ohne `SavedLocation.timezone`, aber mit aufloesbaren
    Koordinaten und einer amtlichen Warnung ab orange.

    Warnbeginn 12:00 UTC = 14:00 Ortszeit -> der Marker muss '@14' tragen.
    Ist-Zustand: `tz=None` (kein `timezone`-Feld) -> der Stunden-Teil entfaellt
    ersatzlos, der Marker bleibt '!TH:M'.

    Rein deterministisch: `render_compare_sms()` ist eine reine Funktion, es
    wird KEINE SMS versendet (Kontingent, Spec-Risiko 7).
    """
    alert = OfficialAlert(
        source="meteoalarm", hazard="thunderstorm", level=3, label="Gewitter",
        valid_from=datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc),
        valid_to=datetime(2026, 7, 27, 16, 0, tzinfo=timezone.utc),
        region_label="Tirol",
    )
    loc_result = LocationResult(
        location=_vienna_location(), temp_max=24.0, wind_max=8.0,
        official_alerts=[alert],
    )
    sms = render_compare_sms(_result([loc_result]))

    assert "@14" in sms, (
        f"Compare-SMS = {sms!r}; erwartet den Warn-Marker mit Ortszeit-Stunde '@14' "
        "(Warnbeginn 12:00 UTC = 14:00 Ortszeit, Europe/Vienna). Ohne gespeichertes "
        "`timezone`-Feld wird die Zeitzone bisher gar nicht aufgeloest und der "
        "Stunden-Teil entfaellt."
    )
    assert "@12" not in sms, (
        f"Compare-SMS = {sms!r} zeigt die Serverzeit-Stunde '@12' statt der Ortszeit '@14'."
    )
    assert len(sms) <= 140, f"SMS-Budget verletzt ({len(sms)} Zeichen): {sms!r}"
