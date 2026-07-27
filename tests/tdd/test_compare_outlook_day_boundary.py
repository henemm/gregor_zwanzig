"""TDD RED — Der 3-Tages-Ausblick beginnt NACH dem im Detail gezeigten Tag.

Issue #1361 Befund 2 (PO-Vorgabe V1, woertlich: "Der Ausblick soll nie den Tag
angeben, der im Detail im Briefing angezeigt wird, sondern immer am darauf
folgenden Tag beginnen."), S3 Scheibe A von Epic #1372.
SPEC: docs/specs/modules/issue_1361_1368_ausblick_konfigurierbar.md AC-6, AC-7
KONTEXT: docs/context/fix-1361-1368-ausblick-konfigurierbar.md

Ist-Zustand (comparison_engine.py:149-151): `d >= target_date` schliesst den
Detailtag ein — die echte Staging-Mail vom 27.07. zeigt `Datum: Monday,
27.07.2026` und darunter einen Ausblick `Mo · Di · Mi`.

Zwei Faelle, weil "der im Detail gezeigte Tag" bei einem Tagesfenster ueber
Mitternacht ZWEI Kalendertage sind (ADR-0035/#1361 S1b,
comparison_engine.py:77-82).

Kern-Schicht, deterministisch: keine Mocks, kein Netz. Die Engine laeuft gegen
den Offline-Fixture-Provider (autouse-Fixture in tests/conftest.py, Issue #346).
"""
from __future__ import annotations

from datetime import date, timedelta

from bs4 import BeautifulSoup

_OUTLOOK_TABLE_MARKER = "border-top:2px solid #1d1c1a"
_WEEKDAYS_DE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


def _run_engine(time_window: tuple[int, int], target_date: date):
    """Echter Engine-Lauf fuer EINEN Ort, offline ueber den Fixture-Provider.

    `official_alerts_enabled=False` haelt den separaten Live-Netz-Pfad fuer
    amtliche Warnungen (#1040) aus dem Test heraus — mit der Tagesgrenze hat er
    nichts zu tun.
    """
    from app.user import SavedLocation
    from services.comparison_engine import COMPARE_FORECAST_HOURS, ComparisonEngine

    loc = SavedLocation(id="innsbruck", name="Innsbruck", lat=47.2692,
                        lon=11.4041, elevation_m=574, timezone="Europe/Vienna")
    result = ComparisonEngine.run(
        locations=[loc],
        time_window=time_window,
        target_date=target_date,
        forecast_hours=COMPARE_FORECAST_HOURS,
        official_alerts_enabled=False,
    )
    loc_result = result.locations[0]
    assert loc_result.error is None, f"Fixture-Fetch fehlgeschlagen: {loc_result.error}"
    return result, loc_result


def _days_of(loc_result, points) -> list[date]:
    from utils.timezone import local_dt, location_tz

    tz = location_tz(loc_result.location)
    return sorted({local_dt(p.ts, tz).date() for p in points})


def _outlook_weekday_labels(result) -> list[str]:
    """Wochentags-Beschriftungen der Ausblick-Zeilen aus der GERENDERTEN
    HTML-Mail — das ist, was der Empfaenger tatsaechlich liest."""
    from output.renderers.email.compare_html import render_compare_html

    html = render_compare_html(result, outlook_enabled=True)
    soup = BeautifulSoup(html, "html.parser")
    tables = [t for t in soup.find_all("table")
              if _OUTLOOK_TABLE_MARKER in str(t.get("style", ""))]
    assert tables, "Kein 3-Tages-Ausblick in der HTML-Mail gefunden"
    return [tr.find_all("td")[0].get_text(strip=True)
            for tr in tables[0].find("tbody").find_all("tr")]


# ---------------------------------------------------------------------------
# AC-6: normales Tagesfenster (9-16 Uhr)
# ---------------------------------------------------------------------------

def test_normal_window_outlook_skips_the_detail_day():
    """AC-6: Given ein Vergleichspreset mit normalem Tagesfenster (9-16 Uhr,
    start_hour <= end_hour) und Detailtag `target_date` / When die
    Vergleichs-Mail erzeugt wird / Then ist `target_date` in KEINER Zeile des
    3-Tages-Ausblicks vertreten — die erste Ausblick-Zeile gehoert dem
    Folgetag.
    """
    target = date.today()
    result, loc_result = _run_engine((9, 16), target)

    detail_days = _days_of(loc_result, loc_result.hourly_data)
    assert detail_days == [target], (
        f"Vorbedingung: bei normalem Fenster zeigt die Stundentabelle genau "
        f"{target}, gesehen: {detail_days}"
    )

    outlook_days = _days_of(loc_result, loc_result.outlook_hourly_data)
    assert target not in outlook_days, (
        f"Der Ausblick wiederholt den im Detail gezeigten Tag {target} "
        f"(Ausblick-Tage: {outlook_days}) — PO-Vorgabe V1 verletzt (AC-6)."
    )

    labels = _outlook_weekday_labels(result)
    assert labels, "Ausblick-Tabelle enthaelt keine Zeilen"
    assert labels[0] != _WEEKDAYS_DE[target.weekday()], (
        f"Die erste Ausblick-Zeile ist mit {labels[0]!r} beschriftet — das ist "
        f"der Wochentag des Detailtags {target}. Ausblick-Beschriftungen: {labels}"
    )
    assert _WEEKDAYS_DE[target.weekday()] not in labels, (
        f"Der Wochentag des Detailtags erscheint im Ausblick: {labels}"
    )


# ---------------------------------------------------------------------------
# AC-7: Mitternachts-Tagesfenster (22-04 Uhr)
# ---------------------------------------------------------------------------

def test_midnight_window_outlook_skips_both_detail_days():
    """AC-7: Given ein Vergleichspreset mit Mitternachts-Tagesfenster (22-04
    Uhr, start_hour > end_hour, ADR-0035) / When die Vergleichs-Mail erzeugt
    wird / Then ist WEDER `target_date` NOCH `target_date + 1 Tag` (der von der
    Stundentabelle ebenfalls beruehrte Folgetag) in einer Ausblick-Zeile
    vertreten — der Ausblick beginnt fruehestens bei `target_date + 2 Tagen`.
    """
    target = date.today()
    next_day = target + timedelta(days=1)
    result, loc_result = _run_engine((22, 4), target)

    detail_days = _days_of(loc_result, loc_result.hourly_data)
    assert detail_days == [target, next_day], (
        "Vorbedingung: bei Mitternachts-Fenster beruehrt die Stundentabelle "
        f"beide Kalendertage {[target, next_day]}, gesehen: {detail_days}"
    )

    outlook_days = _days_of(loc_result, loc_result.outlook_hourly_data)
    overlap = [d for d in detail_days if d in outlook_days]
    assert not overlap, (
        f"Der Ausblick wiederholt {overlap} — genau die Kalendertage, die die "
        f"Stundentabelle bereits im Detail zeigt (Ausblick-Tage: {outlook_days}). "
        "Bei einem Fenster ueber Mitternacht sind das ZWEI Tage, nicht einer "
        "(AC-7)."
    )
    assert outlook_days and outlook_days[0] >= target + timedelta(days=2), (
        f"Der Ausblick beginnt bei {outlook_days[0] if outlook_days else None} "
        f"statt fruehestens bei {target + timedelta(days=2)} (AC-7)."
    )

    labels = _outlook_weekday_labels(result)
    forbidden = {_WEEKDAYS_DE[d.weekday()] for d in detail_days}
    assert not (set(labels) & forbidden), (
        f"Ausblick-Beschriftungen {labels} enthalten die Wochentage der im "
        f"Detail gezeigten Tage {sorted(forbidden)} (AC-7)."
    )
