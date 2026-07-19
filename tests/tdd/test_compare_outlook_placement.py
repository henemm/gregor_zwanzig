"""TDD RED — Issue #1323: 3-Tage-Ausblick je Ort *direkt unter dessen
Stundentabelle* platzieren statt gesammelt am Mail-Ende.

Kern-Schicht, deterministisch: KEINE Mocks/patch()/MagicMock. Echte
ForecastDataPoint-/LocationResult-/ComparisonResult-DTOs, echte Renderer
(render_compare_html / render_comparison_text). Geprueft wird die
beobachtbare Reihenfolge der Bausteine im gerenderten Mail-Body, nicht
Dateiinhalt.

Ist-Zustand (Bug): compare_html.py baut `hourly_sections_html` (alle Orte)
und `outlook_sections_html` (alle Orte) als zwei getrennte Bloecke; der
Ausblick landet als Sammelblock hinter allen Stundentabellen. comparison.py
(Klartext) hat dieselbe Trennung (Sektion "STUNDENVERLAUF" dann Sektion
"AUSBLICK").

Soll-Zustand (Fix): je Ort folgt der Ausblick unmittelbar auf dessen
Stundentabelle; kein gesammelter Ausblick-Sammel-Head mehr.

SPEC: docs/specs/modules/fix_1323_compare_outlook_placement.md AC-1..AC-6
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone


TARGET_DATE = date(2026, 7, 20)

# Eindeutige Marker (aus dem Renderer):
# ">Zeit</th>" steht NUR im Stundentabellen-Kopf (je Ort genau 1x); der
# ">ORT</span>"-Kopf taugt NICHT, weil Stunden- UND Ausblick-Sektion ihn teilen.
_HOURLY_TABLE_MARKER = ">Zeit</th>"                     # Stundentabelle je Ort
_OUTLOOK_TABLE_MARKER = "border-top:2px solid #1d1c1a"  # Ausblick-Tabelle je Ort
_BUNDLE_HEAD_MARKER = "· alle Orte"                      # Sammel-Section-Head (Stunden/Ausblick)
_PLAIN_OUTLOOK_MARKER = "Nächste Etappen"               # render_outlook_plain je Ort


# ---------------------------------------------------------------------------
# Helpers — echte Domaenen-Objekte (Muster aus test_compare_outlook.py)
# ---------------------------------------------------------------------------

def _day_points(day: date, temp_lo: float, temp_hi: float):
    from app.models import ForecastDataPoint, ThunderLevel

    temps = [temp_lo, (temp_lo + temp_hi) / 2, temp_hi, (temp_lo + temp_hi) / 2]
    pts = []
    for h, t in zip((2, 8, 14, 20), temps):
        pts.append(ForecastDataPoint(
            ts=datetime(day.year, day.month, day.day, h, 0, tzinfo=timezone.utc),
            t2m_c=t, wind10m_kmh=15.0, gust_kmh=25.0,
            precip_1h_mm=0.25, pop_pct=30, cloud_total_pct=50,
            thunder_level=ThunderLevel.NONE, visibility_m=20000,
        ))
    return pts


def _loc(name: str, day_temps: list[tuple[float, float]], *,
         tz: str = "UTC", with_outlook: bool = True):
    """LocationResult: hourly_data = Tag 0, outlook_hourly_data = alle Tage
    (bzw. leer, wenn with_outlook=False -> fail-soft-Fall)."""
    from app.user import LocationResult, SavedLocation

    days = [TARGET_DATE + timedelta(days=i) for i in range(len(day_temps))]
    all_points: list = []
    for day, (lo, hi) in zip(days, day_temps):
        all_points.extend(_day_points(day, lo, hi))
    today_points = [p for p in all_points if p.ts.date() == TARGET_DATE]

    return LocationResult(
        location=SavedLocation(id=name.lower(), name=name, lat=47.0, lon=11.0,
                               elevation_m=500, timezone=tz),
        score=50,
        hourly_data=today_points,
        outlook_hourly_data=all_points if with_outlook else [],
    )


def _result(locs):
    from app.user import ComparisonResult
    return ComparisonResult(
        locations=locs, time_window=(0, 23),
        target_date=TARGET_DATE, created_at=datetime(2026, 7, 20, 4, 1),
    )


def _positions(haystack: str, needle: str) -> list[int]:
    return [m.start() for m in re.finditer(re.escape(needle), haystack)]


# ---------------------------------------------------------------------------
# AC-1: HTML — Ausblick jedes Orts direkt unter dessen Stundentabelle
# ---------------------------------------------------------------------------

def test_html_outlook_sits_under_each_location_hourly_table():
    """AC-1: Given zwei Orte mit Stundenverlauf und Ausblick / When die
    HTML-Vergleichsmail gerendert wird / Then folgt auf die Stundentabelle
    des ERSTEN Orts unmittelbar dessen Ausblick, BEVOR die Stundentabelle
    des zweiten Orts beginnt.
    """
    from output.renderers.email.compare_html import render_compare_html

    result = _result([
        _loc("Innsbruck", [(6, 18), (9, 20), (11, 23)], tz="Europe/Vienna"),
        _loc("Fréjus", [(20, 31), (21, 33), (19, 29)], tz="Europe/Paris"),
    ])
    html = render_compare_html(result, outlook_enabled=True)

    ort_pos = _positions(html, _HOURLY_TABLE_MARKER)
    outlook_pos = _positions(html, _OUTLOOK_TABLE_MARKER)
    assert len(ort_pos) == 2, f"Erwartete 2 Ort-Stundensektionen, sah {len(ort_pos)}"
    assert len(outlook_pos) == 2, f"Erwartete 2 Ausblick-Tabellen, sah {len(outlook_pos)}"

    # Verschachtelt: Ausblick des ersten Orts VOR der Stundensektion des zweiten.
    assert outlook_pos[0] < ort_pos[1], (
        "Ausblick des ersten Orts steht NICHT unter dessen Stundentabelle — "
        f"outlook[0]={outlook_pos[0]} liegt hinter ort[1]={ort_pos[1]} "
        "(gesammelter Ausblick-Block am Ende)."
    )


# ---------------------------------------------------------------------------
# AC-2: HTML — kein gesammelter Ausblick-Sammel-Head mehr
# ---------------------------------------------------------------------------

def test_html_has_no_bundled_outlook_section_head():
    """AC-2: Given dieselbe Mail / When gerendert / Then existiert kein
    zweiter '· alle Orte'-Sammel-Head (der bisherige Ausblick-Sammelblock
    'AUSBLICK · 3-Tage-Ausblick · alle Orte' entfaellt; nur der
    Stundenverlauf-Head bleibt).
    """
    from output.renderers.email.compare_html import render_compare_html

    result = _result([
        _loc("Innsbruck", [(6, 18), (9, 20), (11, 23)]),
        _loc("Fréjus", [(20, 31), (21, 33), (19, 29)]),
    ])
    html = render_compare_html(result, outlook_enabled=True)

    n = html.count(_BUNDLE_HEAD_MARKER)
    assert n <= 1, (
        f"Erwartete hoechstens EINEN Sammel-Head ('· alle Orte', Stundenverlauf), "
        f"fand {n} — der Ausblick-Sammelblock ist noch vorhanden."
    )


# ---------------------------------------------------------------------------
# AC-3: Klartext — Ausblick je Ort direkt nach dessen Stundenblock
# ---------------------------------------------------------------------------

def test_plain_outlook_nested_per_location():
    """AC-3: Given die Klartext-Fassung mit zwei Orten / When gerendert /
    Then steht der Ausblick des ersten Orts vor dem Stundenblock des zweiten
    Orts (verschachtelt), nicht gesammelt am Textende.
    """
    from output.renderers.comparison import render_comparison_text

    result = _result([
        _loc("Alphaville", [(6, 18), (9, 20), (11, 23)]),
        _loc("Betatown", [(20, 31), (21, 33), (19, 29)]),
    ])
    text = render_comparison_text(result, outlook_enabled=True)

    sv = text.index("STUNDENVERLAUF")
    pos_alpha_hours = text.index("Alphaville", sv)
    pos_first_outlook = text.index(_PLAIN_OUTLOOK_MARKER, sv)
    pos_beta_hours = text.index("Betatown", sv)

    assert pos_alpha_hours < pos_first_outlook < pos_beta_hours, (
        "Klartext-Ausblick des ersten Orts steht NICHT zwischen dessen "
        "Stundenblock und dem zweiten Ort — Reihenfolge "
        f"(alpha_hours={pos_alpha_hours}, outlook={pos_first_outlook}, "
        f"beta_hours={pos_beta_hours})."
    )


# ---------------------------------------------------------------------------
# AC-4: Edge — Ausblick an, Stundenverlauf aus: je Ort, kein Sammel-Head
# ---------------------------------------------------------------------------

def test_outlook_enabled_hourly_disabled_no_bundle_no_crash():
    """AC-4: Given outlook_enabled=True und hourly_enabled=False / When
    gerendert / Then erscheint je Ort eine Ausblick-Tabelle, ohne
    gesammelten Sammel-Head, ohne Crash.
    """
    from output.renderers.email.compare_html import render_compare_html

    result = _result([
        _loc("Innsbruck", [(6, 18), (9, 20), (11, 23)]),
        _loc("Fréjus", [(20, 31), (21, 33), (19, 29)]),
    ])
    html = render_compare_html(result, outlook_enabled=True, hourly_enabled=False)

    assert len(_positions(html, _OUTLOOK_TABLE_MARKER)) == 2, \
        "Bei hourly aus / outlook an muss je Ort eine Ausblick-Tabelle erscheinen."
    assert _BUNDLE_HEAD_MARKER not in html, \
        "Kein gesammelter Ausblick-Sammel-Head, auch wenn der Stundenverlauf aus ist."


# ---------------------------------------------------------------------------
# AC-5: fail-soft + Verschachtelung bei drei Orten, einer ohne Ausblick-Daten
# ---------------------------------------------------------------------------

def test_missing_outlook_data_failsoft_keeps_nesting_and_order():
    """AC-5: Given drei Orte, der mittlere ohne outlook_hourly_data / When
    gerendert / Then hat nur der Ort ohne Daten keinen Ausblick, die beiden
    anderen zeigen ihn direkt unter ihrer Stundensektion, Reihenfolge stabil.
    """
    from output.renderers.email.compare_html import render_compare_html

    result = _result([
        _loc("Aaa", [(6, 18), (9, 20), (11, 23)]),
        _loc("Bbb", [(5, 15), (7, 17), (8, 18)], with_outlook=False),
        _loc("Ccc", [(20, 31), (21, 33), (19, 29)]),
    ])
    html = render_compare_html(result, outlook_enabled=True)

    ort_pos = _positions(html, _HOURLY_TABLE_MARKER)      # 3 Ort-Sektionen
    outlook_pos = _positions(html, _OUTLOOK_TABLE_MARKER)  # nur 2 Ausblicke
    assert len(ort_pos) == 3, f"Erwartete 3 Ort-Stundensektionen, sah {len(ort_pos)}"
    assert len(outlook_pos) == 2, (
        f"Erwartete 2 Ausblick-Tabellen (mittlerer Ort fail-soft ohne Daten), "
        f"sah {len(outlook_pos)}"
    )
    # 1. Ausblick (Aaa) zwischen Ort-1 und Ort-2; 2. Ausblick (Ccc) nach Ort-3.
    assert ort_pos[0] < outlook_pos[0] < ort_pos[1], \
        "Ausblick des ersten Orts steht nicht direkt unter dessen Stundensektion."
    assert outlook_pos[1] > ort_pos[2], \
        "Ausblick des dritten Orts steht nicht unter dessen Stundensektion."
