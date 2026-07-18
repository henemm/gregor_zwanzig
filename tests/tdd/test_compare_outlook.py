"""TDD RED — Epic #1301 B4: 3-Tage-Ausblick je Ort im Ortsvergleich (Neubau).

Compare erzeugt seine Ausblick-Zeilen ueber dieselben geteilten Bausteine wie
der Trip-Renderer (render_outlook_table/render_outlook_plain/build_outlook_row,
s. test_shared_outlook_renderer.py) -- compare-eigen bleiben nur Tagesschleife
und Platzierung.

Kern-Schicht, deterministisch: KEINE Mocks/patch()/MagicMock. Echte
ForecastDataPoint-/LocationResult-/ComparisonResult-DTOs, echte Renderer
(render_compare_html/render_comparison_text/render_compare_email), echte
ComparisonEngine.run() gegen die autouse-Fixture-Provider-Umgebung (kein
Netz, s. tests/conftest.py + tests/tdd/test_issue_346_fixture_provider.py).
Wo eine teure Upstream-Abhaengigkeit rein zu Beobachtungszwecken beobachtet
werden muss (Provider-Aufrufzaehler, uebergebene Kwargs), wird eine echte
Aufzeichner-Funktion/-Subklasse eingehaengt, die vollstaendig an die reale
Implementierung delegiert (kein gefaelschtes Verhalten) -- etabliertes Muster
aus test_issue_764_compare_forecast_hours_consume.py /
test_compare_preview_service.py.

SPEC: docs/specs/modules/epic_1301_b4_compare_outlook.md AC-4..AC-9
KONTEXT: docs/context/epic-1301-b4-ausblick.md
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from bs4 import BeautifulSoup

TARGET_DATE = date(2026, 7, 20)


# ---------------------------------------------------------------------------
# Helpers — echte Domaenen-Objekte
# ---------------------------------------------------------------------------

def _day_points(day: date, temp_lo: float, temp_hi: float, *, wind=15.0, gust=25.0,
                 precip_total=1.0, thunder=None):
    from app.models import ForecastDataPoint, ThunderLevel

    tl = thunder or ThunderLevel.NONE
    temps = [temp_lo, (temp_lo + temp_hi) / 2, temp_hi, (temp_lo + temp_hi) / 2]
    pts = []
    for h, t in zip((2, 8, 14, 20), temps):
        pts.append(ForecastDataPoint(
            ts=datetime(day.year, day.month, day.day, h, 0, tzinfo=timezone.utc),
            t2m_c=t, wind10m_kmh=wind, gust_kmh=gust,
            precip_1h_mm=precip_total / 4, pop_pct=30, cloud_total_pct=50,
            thunder_level=tl, visibility_m=20000,
        ))
    return pts


def _location(name: str, target: date, day_temps: list[tuple[float, float]], *,
              timezone_str: str = "UTC"):
    """LocationResult mit outlook_hourly_data ueber len(day_temps) Kalendertage
    ab `target`; hourly_data = nur der heutige (erste) Tages-Slice -- exakt
    das AC-4-Verhaeltnis (Ein-Tages-Fenster vs. Mehrtages-Slice)."""
    from app.user import LocationResult, SavedLocation

    days = [target + timedelta(days=i) for i in range(len(day_temps))]
    all_points = []
    for day, (lo, hi) in zip(days, day_temps):
        all_points.extend(_day_points(day, lo, hi))
    today_points = [p for p in all_points if p.ts.date() == target]

    return LocationResult(
        location=SavedLocation(id=name.lower(), name=name, lat=47.0, lon=11.0,
                                elevation_m=500, timezone=timezone_str),
        score=50,
        hourly_data=today_points,
        outlook_hourly_data=all_points,  # RED: Feld existiert noch nicht (TypeError)
    )


# ---------------------------------------------------------------------------
# AC-4: Engine-Retention eines Mehrtages-Slice, kein Extra-Fetch
# ---------------------------------------------------------------------------

def test_engine_retains_multiday_slice_without_extra_fetch(monkeypatch):
    """AC-4: Given ein bereits erfolgter 96h-Fetch fuer einen Ort / When der
    Ort in comparison_engine.py verarbeitet wird / Then traegt
    LocationResult.outlook_hourly_data bis zu 3 Kalendertage aus raw_data;
    hourly_data bleibt unveraendert; kein zusaetzlicher API-Call entsteht.

    Zaehlung ueber eine echte Aufzeichner-Funktion, die vollstaendig an
    fetch_forecast_for_location delegiert (kein gefaelschtes Verhalten) --
    offline via GZ_TEST_FIXTURE_DIR-Autouse-Fixture (tests/conftest.py).
    official_alerts_enabled=False vermeidet den separaten Live-Netz-Pfad
    fuer amtliche Warnungen (Issue #1040), der mit dem hier geprueften
    Wetter-Fetch nichts zu tun hat.
    """
    import services.comparison_engine as ce_mod
    from app.user import SavedLocation

    calls = []
    orig_fetch = ce_mod.fetch_forecast_for_location

    def _counting_fetch(*args, **kwargs):
        calls.append((args, kwargs))
        return orig_fetch(*args, **kwargs)

    monkeypatch.setattr(ce_mod, "fetch_forecast_for_location", _counting_fetch)

    loc = SavedLocation(id="innsbruck", name="Innsbruck", lat=47.2692, lon=11.4041, elevation_m=574)
    result = ce_mod.ComparisonEngine.run(
        locations=[loc],
        time_window=(0, 23),
        target_date=date.today(),
        forecast_hours=ce_mod.COMPARE_FORECAST_HOURS,
        official_alerts_enabled=False,
    )

    assert len(calls) == 1, f"Erwartete genau 1 Fetch-Aufruf fuer den Ort, sah {len(calls)}"

    loc_result = result.locations[0]
    assert loc_result.error is None, f"Fixture-Fetch fehlgeschlagen: {loc_result.error}"
    assert loc_result.hourly_data, "hourly_data (Ein-Tages-Fenster) darf nicht leer sein"

    outlook_data = loc_result.outlook_hourly_data  # AttributeError vor B4-Feld
    assert len(outlook_data) > len(loc_result.hourly_data), (
        f"outlook_hourly_data ({len(outlook_data)}) soll laenger sein als "
        f"hourly_data ({len(loc_result.hourly_data)}) -- Mehrtages-Slice erwartet"
    )


# ---------------------------------------------------------------------------
# AC-5: HTML-Vergleichsmail zeigt je Ort einen eigenen Ausblick
# ---------------------------------------------------------------------------

def test_compare_html_shows_outlook_per_location():
    """AC-5: Given Innsbruck (Alpen) und Fréjus (Nicht-Alpen) im selben
    Vergleich / When die HTML-Vergleichsmail gerendert wird / Then zeigt
    JEDER Ort seinen eigenen 3-Tage-Ausblick mit ortsspezifischen
    Tageswerten (kein geteilter Platzhalter).
    """
    from output.renderers.email.compare_html import render_compare_html
    from app.user import ComparisonResult

    innsbruck = _location("Innsbruck", TARGET_DATE, [(6, 18), (9, 20), (11, 23)],
                           timezone_str="Europe/Vienna")
    frejus = _location("Fréjus", TARGET_DATE, [(20, 31), (21, 33), (19, 29)],
                        timezone_str="Europe/Paris")
    result = ComparisonResult(
        locations=[innsbruck, frejus], time_window=(0, 23),
        target_date=TARGET_DATE, created_at=datetime(2026, 7, 20, 4, 1),
    )

    html = render_compare_html(result, outlook_enabled=True)
    soup = BeautifulSoup(html, "html.parser")

    # Korrigierter Marker (Entwickler-Fix, s. Rueckmeldung an PO/QA): 'Böen'
    # allein ist NICHT exklusiv fuer die Ausblick-Tabelle -- die bestehende
    # Stundentabelle (HOUR_METRICS, compare_html.py) traegt dieselbe Spalte
    # bereits seit #1106. Eindeutiger Marker ist der Ausblick-Tabellen-Rahmen
    # (identisch zu test_shared_outlook_renderer.py::_OUTLOOK_TABLE_MARKER,
    # html.py Z.1258/outlook.py), der ausschliesslich auf der Ausblick-Tabelle
    # gesetzt ist.
    _OUTLOOK_TABLE_MARKER = "border-top:2px solid #1d1c1a"
    outlook_tables = [
        t for t in soup.find_all("table")
        if _OUTLOOK_TABLE_MARKER in str(t.get("style", ""))
    ]
    assert len(outlook_tables) == 2, (
        f"Erwartete je Ort eine eigene Ausblick-Tabelle (2 Orte), gefunden: "
        f"{len(outlook_tables)}"
    )

    def _nd_pairs(table):
        return {
            (tr.find_all("td")[1].get_text(strip=True), tr.find_all("td")[2].get_text(strip=True))
            for tr in table.find("tbody").find_all("tr")
        }

    temps_a, temps_b = (_nd_pairs(t) for t in outlook_tables)
    assert temps_a != temps_b, (
        "Beide Orte zeigen identische Ausblick-Tageswerte -- Verdacht auf "
        "geteilten Platzhalter statt ortsspezifischer Werte (AC-5)"
    )


# ---------------------------------------------------------------------------
# AC-6 (Neubau): Klartext-Vergleichsmail zeigt je Ort einen eigenen Ausblick
# ---------------------------------------------------------------------------

def test_compare_plain_shows_outlook_per_location():
    """AC-6 (Neubau): Given derselbe Mehr-Orte-Vergleich mit gueltigen
    Ausblick-Daten / When die Klartext-Fassung gerendert wird / Then enthaelt
    sie den Ausblick je Ort via render_outlook_plain(rows, show_acc=False).
    """
    from output.renderers.comparison import render_comparison_text
    from app.user import ComparisonResult

    innsbruck = _location("Innsbruck", TARGET_DATE, [(6, 18), (9, 20), (11, 23)])
    frejus = _location("Fréjus", TARGET_DATE, [(20, 31), (21, 33), (19, 29)])
    result = ComparisonResult(
        locations=[innsbruck, frejus], time_window=(0, 23),
        target_date=TARGET_DATE, created_at=datetime(2026, 7, 20, 4, 1),
    )

    text = render_comparison_text(result, outlook_enabled=True)

    assert "9–20°C" in text, "Innsbruck-Ausblick (Tag 2: 9-20°C) fehlt im Klartext"
    assert "21–33°C" in text, "Fréjus-Ausblick (Tag 2: 21-33°C) fehlt im Klartext"


# ---------------------------------------------------------------------------
# AC-7: outlook_enabled Default True, identisch fuer Versand- und Vorschau-Pfad
# ---------------------------------------------------------------------------

class _OutlookEnabledCaptured(Exception):
    """Sentinel: traegt die tatsaechlich an render_compare_email uebergebenen
    Kwargs, bricht VOR dem eigentlichen Rendern ab (kein Netz/SMTP beruehrt)."""

    def __init__(self, kwargs):
        self.kwargs = kwargs
        super().__init__(f"captured kwargs={sorted(kwargs)}")


def _capture_render_compare_email_kwargs(call):
    """Rebindet output.renderers.comparison.render_compare_email auf eine
    echte Aufzeichner-Funktion (kein Mock-Framework) -- `call` fuehrt den zu
    pruefenden Aufrufer (Dispatch ODER Preview) aus, restauriert in finally."""
    import output.renderers.comparison as comparison_mod

    original = comparison_mod.render_compare_email

    def _recording(*args, **kwargs):
        raise _OutlookEnabledCaptured(kwargs)

    comparison_mod.render_compare_email = _recording
    try:
        with pytest.raises(_OutlookEnabledCaptured) as exc:
            call()
        return exc.value.kwargs
    finally:
        comparison_mod.render_compare_email = original


def _resolvable_location(loc_id: str):
    from app.loader import SavedLocation
    return SavedLocation(id=loc_id, name="Innsbruck", lat=47.2692, lon=11.4041, elevation_m=574)


def _preset(preset_id: str, loc_id: str, **extra) -> dict:
    p = {
        "id": preset_id,
        "name": f"Vergleich {preset_id}",
        "location_ids": [loc_id],
        "schedule": "daily",
        "profil": "SUMMER_TREKKING",
        "empfaenger": ["gregor-test@henemm.com"],
        "created_at": "2026-01-01T00:00:00Z",
        # Vermeidet den separaten Live-Netz-Pfad fuer amtliche Warnungen
        # (Issue #1040) -- irrelevant fuer den hier geprueften Kwarg-Vertrag.
        "official_alerts_enabled": False,
    }
    p.update(extra)
    return p


@pytest.fixture
def compare_env(tmp_path, monkeypatch):
    """Isolierter Daten-Root fuer den Vorschau-Pfad (analog
    test_compare_preview_service.py::compare_env)."""
    from app import loader as app_loader

    data_root = tmp_path / "data"
    data_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(app_loader, "_DATA_ROOT", str(data_root))
    try:
        from src.app import loader as src_loader
        monkeypatch.setattr(src_loader, "_DATA_ROOT", str(data_root))
    except ImportError:  # pragma: no cover - Alias-Modul immer vorhanden
        pass
    return f"tdd-b4-{uuid.uuid4().hex[:8]}"


def _dispatch_kwargs(preset, location, user_id, tmp_path):
    from app.config import Settings
    from services.scheduler_dispatch_service import send_one_compare_preset

    settings = Settings().with_user_profile(user_id)
    return _capture_render_compare_email_kwargs(
        lambda: send_one_compare_preset(
            preset, settings, user_id, str(tmp_path), all_locations_cache=[location],
        )
    )


def _preview_kwargs(preset_id, user_id):
    from services.compare_preview_service import ComparePreviewService
    return _capture_render_compare_email_kwargs(
        lambda: ComparePreviewService().render_email_preview(preset_id, user_id=user_id)
    )


def test_outlook_enabled_default_true_end_to_end(compare_env, tmp_path):
    """AC-7: Given ein Preset ohne outlook_enabled-Schluessel / When eine
    Vergleichsmail gesendet bzw. vorgeschaut wird / Then ist der Ausblick
    sichtbar (Default True) -- Versand- und Vorschau-Pfad verhalten sich
    IDENTISCH (Divergenz-Schutz #1297).
    """
    from app.loader import get_data_dir, save_location
    from services.report_config_resolver import resolve_compare_render_options
    from tests.helpers.compare_briefings import write_compare_briefings

    user_id = compare_env
    loc = _resolvable_location("loc-b4-default")
    preset = _preset("cp-b4-default", loc.id)  # kein outlook_enabled-Key

    assert resolve_compare_render_options(preset).outlook_enabled is True, (
        "resolve_compare_render_options soll bei fehlendem Preset-Key Default "
        "True liefern (AC-7)"
    )

    dispatch_kwargs = _dispatch_kwargs(dict(preset), loc, user_id, tmp_path)
    assert dispatch_kwargs.get("outlook_enabled") is True, (
        f"Versandpfad: erwartet outlook_enabled=True (Default), Kwargs: {dispatch_kwargs}"
    )

    save_location(loc, user_id=user_id)
    write_compare_briefings(get_data_dir(user_id), [preset])
    preview_kwargs = _preview_kwargs(preset["id"], user_id)
    assert preview_kwargs.get("outlook_enabled") is True, (
        f"Vorschau-Pfad: erwartet outlook_enabled=True (Default), Kwargs: {preview_kwargs}"
    )


def test_outlook_enabled_false_suppresses_both_formats(compare_env, tmp_path):
    """AC-7: Given outlook_enabled=False im aufgeloesten Preset / Then fehlt
    der Ausblick sowohl in HTML als auch Klartext; Versand- und Vorschau-Pfad
    reichen denselben Wert durch (Divergenz-Schutz #1297).
    """
    from app.loader import get_data_dir, save_location
    from app.user import ComparisonResult
    from output.renderers.comparison import render_compare_email
    from services.report_config_resolver import resolve_compare_render_options
    from tests.helpers.compare_briefings import write_compare_briefings

    user_id = compare_env
    loc = _resolvable_location("loc-b4-off")
    preset = _preset("cp-b4-off", loc.id, outlook_enabled=False)

    assert resolve_compare_render_options(preset).outlook_enabled is False, (
        "resolve_compare_render_options soll outlook_enabled=False aus dem "
        "Preset uebernehmen (AC-7)"
    )

    dispatch_kwargs = _dispatch_kwargs(dict(preset), loc, user_id, tmp_path)
    assert dispatch_kwargs.get("outlook_enabled") is False, (
        f"Versandpfad: erwartet outlook_enabled=False, Kwargs: {dispatch_kwargs}"
    )

    save_location(loc, user_id=user_id)
    write_compare_briefings(get_data_dir(user_id), [preset])
    preview_kwargs = _preview_kwargs(preset["id"], user_id)
    assert preview_kwargs.get("outlook_enabled") is False, (
        f"Vorschau-Pfad: erwartet outlook_enabled=False, Kwargs: {preview_kwargs}"
    )

    # Inhaltlicher Nachweis: outlook_enabled steuert tatsaechlich Sichtbarkeit
    # in BEIDEN Formaten (HTML + Klartext) desselben render_compare_email-Aufrufs.
    healthy = _location("Innsbruck", TARGET_DATE, [(6, 18), (9, 20), (11, 23)])
    result = ComparisonResult(
        locations=[healthy], time_window=(0, 23),
        target_date=TARGET_DATE, created_at=datetime(2026, 7, 20, 4, 1),
    )

    html_off, text_off = render_compare_email(result, outlook_enabled=False)
    html_on, text_on = render_compare_email(result, outlook_enabled=True)

    # Korrigierter Marker (Entwickler-Fix, s. Rueckmeldung an PO/QA): 'Böen'
    # allein ist NICHT exklusiv fuer die Ausblick-Tabelle -- sowohl die
    # bestehende Uebersichtsmatrix (CV2_METRICS "gust_max", seit #1296) als
    # auch die Stundentabelle (HOUR_METRICS, seit #1106) tragen dieselbe
    # Spalte/Zeile unabhaengig von outlook_enabled. Eindeutiger Marker ist
    # der Ausblick-Tabellen-Rahmen (identisch zu
    # test_shared_outlook_renderer.py::_OUTLOOK_TABLE_MARKER).
    _OUTLOOK_TABLE_MARKER = "border-top:2px solid #1d1c1a"
    assert _OUTLOOK_TABLE_MARKER not in html_off, (
        "Ausblick-Tabelle sichtbar trotz outlook_enabled=False"
    )
    assert _OUTLOOK_TABLE_MARKER in html_on, "Ausblick-Tabelle fehlt trotz outlook_enabled=True"
    assert "9–20°C" not in text_off, "Klartext-Ausblick sichtbar trotz outlook_enabled=False"
    assert "9–20°C" in text_on, "Klartext-Ausblick fehlt trotz outlook_enabled=True"


# ---------------------------------------------------------------------------
# AC-8: Ausblick-Tageswert identisch zum #1285-Uebersichts-Tageswert
# ---------------------------------------------------------------------------

def test_outlook_daily_value_matches_1285_daily_summary():
    """AC-8: Given derselbe Stundensatz eines Ortes / When der
    Ausblick-Tageswert berechnet wird / Then geschieht das via
    summarize_points -- identisch zum #1285-Uebersichts-Tageswert desselben
    Tages (_daily_summary).
    """
    from output.renderers.email.compare_html import _daily_summary
    from output.renderers.email.outlook import build_outlook_row
    from services.weather_metrics import summarize_points

    loc = _location("Innsbruck", TARGET_DATE, [(6, 18), (9, 20), (11, 23)])

    expected = _daily_summary(loc)  # #1285-Pfad: summarize_points(loc.hourly_data)
    assert expected is not None

    day1_points = [p for p in loc.outlook_hourly_data if p.ts.date() == TARGET_DATE]
    day1_summary = summarize_points(day1_points)
    row = build_outlook_row(day1_summary, day1_points, "Mo", ZoneInfo("UTC"))

    assert row["precip_mm"] == pytest.approx(expected.precip_sum_mm)
    assert row["rain_probability_pct"] == expected.pop_max_pct
    assert row["temp_lo"] == int(expected.temp_min_c)
    assert row["temp_hi"] == int(expected.temp_max_c)


# ---------------------------------------------------------------------------
# AC-9: Fail-soft bei Fehlerzustand/leerem outlook_hourly_data
# ---------------------------------------------------------------------------

def test_outlook_fail_soft_on_missing_data():
    """AC-9: Given ein Ort mit Fehlerzustand (kein outlook_hourly_data) neben
    einem gesunden Ort / When die Mail gerendert wird / Then erscheint fuer
    den fehlerhaften Ort kein Ausblick, die restliche Mail bleibt
    unveraendert, kein Crash tritt auf.
    """
    from app.user import ComparisonResult, LocationResult, SavedLocation
    from output.renderers.comparison import render_comparison_text
    from output.renderers.email.compare_html import render_compare_html

    healthy = _location("Innsbruck", TARGET_DATE, [(6, 18), (9, 20), (11, 23)])
    broken = LocationResult(
        location=SavedLocation(id="fehlerort", name="Fehlerort", lat=1.0, lon=1.0, elevation_m=0),
        error="Fetch fehlgeschlagen",
    )
    result = ComparisonResult(
        locations=[healthy, broken], time_window=(0, 23),
        target_date=TARGET_DATE, created_at=datetime(2026, 7, 20, 4, 1),
    )

    html = render_compare_html(result, outlook_enabled=True)  # darf nicht crashen
    text = render_comparison_text(result, outlook_enabled=True)

    assert "Innsbruck" in html and "Fehlerort" in html, (
        "Beide Orte muessen trotz Fehlerzustand des zweiten Ortes in der HTML-Mail erscheinen"
    )
    assert "Innsbruck" in text and "Fehlerort" in text, (
        "Beide Orte muessen trotz Fehlerzustand des zweiten Ortes im Klartext erscheinen"
    )
