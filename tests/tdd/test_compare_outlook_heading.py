"""TDD RED — 3-Tages-Ausblick der Vergleichs-Mail: eigene Ueberschrift.

Issue #1368 (Punkt 1), S3 Scheibe A von Epic #1372.
SPEC: docs/specs/modules/issue_1361_1368_ausblick_konfigurierbar.md AC-3, AC-4
KONTEXT: docs/context/fix-1361-1368-ausblick-konfigurierbar.md

Beleg-Lage (echte Staging-Mail, 27.07.2026): die Woerter "Ausblick" und
"3-Tages" kommen im HTML-Teil 0x vor — der Block traegt GAR KEINE eigene
Ueberschrift, nur den ein zweites Mal wiederholten Ortsnamen. Im Klartext
steht die Trip-Formulierung "Nächste Etappen"; im Ortsvergleich gibt es keine
Etappen.

Kern-Schicht, deterministisch: keine Mocks, kein Netz, echte DTOs, echter
Renderpfad ``render_compare_email()`` (HTML UND Klartext desselben Aufrufs).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

TARGET_DATE = date(2026, 7, 20)
TZ_NAME = "Europe/Vienna"

_OUTLOOK_TABLE_MARKER = "border-top:2px solid #1d1c1a"
_HEADING = "3-Tages-Ausblick"
_TRIP_HEADING = "Nächste Etappen"


def _day_points(day: date, temp_lo: float, temp_hi: float):
    from app.models import ForecastDataPoint, ThunderLevel

    temps = [temp_lo, (temp_lo + temp_hi) / 2, temp_hi, (temp_lo + temp_hi) / 2]
    return [
        ForecastDataPoint(
            ts=datetime(day.year, day.month, day.day, h, 0, tzinfo=timezone.utc),
            t2m_c=t, wind10m_kmh=15.0, gust_kmh=25.0, precip_1h_mm=0.25,
            pop_pct=40, cloud_total_pct=50, thunder_level=ThunderLevel.NONE,
            visibility_m=20000,
        )
        for h, t in zip((2, 8, 14, 20), temps)
    ]


def _location(name: str, tz_name: str):
    from app.user import LocationResult, SavedLocation

    points: list = []
    for offset, (lo, hi) in enumerate([(6.0, 18.0), (9.0, 27.0), (11.0, 23.0)]):
        points.extend(_day_points(TARGET_DATE + timedelta(days=offset), lo, hi))
    today = [p for p in points if p.ts.date() == TARGET_DATE]
    return LocationResult(
        location=SavedLocation(id=name.lower(), name=name, lat=47.27, lon=11.40,
                               elevation_m=574, timezone=tz_name),
        score=50, hourly_data=today, outlook_hourly_data=points,
    )


def _render():
    from app.user import ComparisonResult
    from output.renderers.comparison import render_compare_email

    result = ComparisonResult(
        locations=[_location("Innsbruck", TZ_NAME)],
        time_window=(9, 16), target_date=TARGET_DATE,
        created_at=datetime(2026, 7, 20, 4, 1),
    )
    return render_compare_email(result, outlook_enabled=True)


# ---------------------------------------------------------------------------
# AC-3: HTML-Ausblick-Block traegt "3-Tages-Ausblick" DIREKT ueber der Tabelle
# ---------------------------------------------------------------------------

def test_html_outlook_block_carries_its_own_heading():
    """AC-3: Given eine Vergleichs-Mail mit aktivem 3-Tages-Ausblick / When der
    HTML-Teil betrachtet wird / Then traegt der Ausblick-Block eine eigene, fuer
    den Empfaenger erkennbare Ueberschrift "3-Tages-Ausblick" direkt ueber der
    Tabelle (kein blosser String-Sucher irgendwo im Dokument) — nicht nur den
    wiederholten Ortsnamen ohne Bezeichnung des Blocks.
    """
    html, _text = _render()

    soup = BeautifulSoup(html, "html.parser")
    tables = [t for t in soup.find_all("table")
              if _OUTLOOK_TABLE_MARKER in str(t.get("style", ""))]
    assert tables, "Kein 3-Tages-Ausblick in der HTML-Mail gefunden"

    block = tables[0].find_parent("div")
    assert block is not None, "Ausblick-Tabelle steht in keinem umschliessenden Block"
    block_html = block.decode()

    assert _HEADING in block_html, (
        f"Der Ausblick-Block traegt keine Bezeichnung {_HEADING!r}. Ohne sie "
        "steht ueber der Tagestabelle nur der ein zweites Mal wiederholte "
        "Ortsname, und der Empfaenger sieht nicht, dass es sich um die "
        f"Folgetage handelt (AC-3). Block-Anfang:\n{block_html[:400]}"
    )
    assert block_html.index(_HEADING) < block_html.index(_OUTLOOK_TABLE_MARKER), (
        "Die Bezeichnung '3-Tages-Ausblick' steht nicht ueber, sondern unter/in "
        "der Ausblick-Tabelle (AC-3)."
    )


def test_html_outlook_heading_keeps_the_timezone_label():
    """AC-3 (Zusatz, Regressionsschutz #1378): Given derselbe Ausblick-Block /
    When die neue Ueberschrift den bisher dort stehenden Ort-Kopf ersetzt / Then
    bleibt die angeschriebene Zeitbasis (Zeitzonen-Kuerzel) erhalten — die
    Tageszeilen und ihre @-Stunden-Tokens stehen in Ortszeit.
    """
    html, _text = _render()

    expected_abbrev = datetime(
        TARGET_DATE.year, TARGET_DATE.month, TARGET_DATE.day, 12, 0,
        tzinfo=ZoneInfo(TZ_NAME),
    ).tzname()

    soup = BeautifulSoup(html, "html.parser")
    tables = [t for t in soup.find_all("table")
              if _OUTLOOK_TABLE_MARKER in str(t.get("style", ""))]
    assert tables, "Kein 3-Tages-Ausblick in der HTML-Mail gefunden"
    block_html = tables[0].find_parent("div").decode()
    heading_region = block_html[:block_html.index(_OUTLOOK_TABLE_MARKER)]

    assert _HEADING in heading_region, (
        f"Ueberschrift {_HEADING!r} fehlt ueber der Ausblick-Tabelle (AC-3)"
    )
    assert expected_abbrev in heading_region, (
        f"Zeitzonen-Kuerzel {expected_abbrev!r} fehlt an der Ausblick-Ueberschrift "
        f"— die Zeitbasis-Anschrift aus #1378 darf nicht verloren gehen. "
        f"Kopfbereich:\n{heading_region[-400:]}"
    )


# ---------------------------------------------------------------------------
# AC-4: Klartext-Ausblick heisst "3-Tages-Ausblick", nicht "Nächste Etappen"
# ---------------------------------------------------------------------------

def test_plain_outlook_block_is_not_labelled_as_trip_stages():
    """AC-4: Given dieselbe Mail / When der KLARTEXT-Teil betrachtet wird /
    Then traegt der Ausblick-Block die Bezeichnung "3-Tages-Ausblick" statt der
    Trip-Formulierung "Nächste Etappen" — im Ortsvergleich gibt es keine
    Etappen. Der Pflicht-Validator liest nur HTML und faengt das nicht (#1366).
    """
    _html, text = _render()

    assert _TRIP_HEADING not in text, (
        "Der Klartext-Ausblick des Ortsvergleichs ist mit der Trip-Formulierung "
        f"{_TRIP_HEADING!r} ueberschrieben — im Ortsvergleich gibt es keine "
        f"Etappen (AC-4).\n{text}"
    )
    assert _HEADING in text, (
        f"Der Klartext-Ausblick traegt keine Bezeichnung {_HEADING!r} (AC-4).\n{text}"
    )

    lines = [line.strip() for line in text.split("\n")]
    assert _HEADING in lines, (
        f"{_HEADING!r} steht nicht als eigene Ueberschriftszeile ueber dem "
        f"Klartext-Ausblick, sondern nur irgendwo im Text.\n{text}"
    )
    heading_idx = lines.index(_HEADING)
    following = [line for line in lines[heading_idx + 1:heading_idx + 5] if line]
    assert following, (
        f"Nach der Ueberschrift {_HEADING!r} folgen keine Tageszeilen.\n{text}"
    )
