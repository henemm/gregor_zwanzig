"""TDD RED — #1848 A3 AC-6: der Ortsvergleich-Ausblick erbt ``active_metrics``.

SPEC: docs/specs/modules/feat_1848_a3_ausblick_erbt_grundauswahl.md AC-6
KONTEXT: docs/context/feat-1848-a3-outlook-kanal-modul.md
  "Ortsvergleich, Teil (a): eine echte Verhaltensaenderung" --
  ``report_config_resolver.py:291`` ruft ``resolve_outlook_metrics()`` heute
  UNGEKLEMMT auf; ADR-0053 Punkt 1 (bewusst kein Maximum) wird durch diese
  Scheibe abgeloest.

Prueforts-Regel: gegen die GERENDERTE Vergleichsmail (``render_compare_email()``),
nicht gegen den blossen Rueckgabewert von ``resolve_compare_render_options()``
-- ein Test auf den Resolver allein faengt eine fehlende Verdrahtung im
Renderer/Aufrufer nicht (Spec-Vorgabe zu AC-6, CLAUDE.md "Pruefort == Wirkort").

Kein Mock-Framework, kein Netz. Vorbild/geteilte Bausteine:
``tests/tdd/test_compare_outlook_metric_selection.py``.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from bs4 import BeautifulSoup

TARGET_DATE = date(2026, 7, 20)
TZ_NAME = "Europe/Vienna"
_OUTLOOK_TABLE_MARKER = "border-top:2px solid #1d1c1a"


def _day_points(day: date, temp_lo: float, temp_hi: float, precip_total: float):
    from app.models import ForecastDataPoint, ThunderLevel

    temps = [temp_lo, (temp_lo + temp_hi) / 2, temp_hi, (temp_lo + temp_hi) / 2]
    return [
        ForecastDataPoint(
            ts=datetime(day.year, day.month, day.day, h, 0, tzinfo=timezone.utc),
            t2m_c=t, wind10m_kmh=15.0, gust_kmh=25.0,
            precip_1h_mm=precip_total / 4, pop_pct=55, cloud_total_pct=50,
            humidity_pct=60.0,
            thunder_level=ThunderLevel.NONE, visibility_m=20000,
        )
        for h, t in zip((2, 8, 14, 20), temps)
    ]


def _location(name: str = "Innsbruck"):
    from app.user import LocationResult, SavedLocation

    day_specs = [
        (TARGET_DATE, 6.0, 18.0, 0.4),
        (TARGET_DATE + timedelta(days=1), 9.0, 27.0, 4.4),
        (TARGET_DATE + timedelta(days=2), 11.0, 23.0, 0.0),
    ]
    all_points: list = []
    for day, lo, hi, precip in day_specs:
        all_points.extend(_day_points(day, lo, hi, precip))
    today_points = [p for p in all_points if p.ts.date() == TARGET_DATE]

    return LocationResult(
        location=SavedLocation(id=name.lower(), name=name, lat=47.27, lon=11.40,
                               elevation_m=574, timezone=TZ_NAME),
        score=50,
        hourly_data=today_points,
        outlook_hourly_data=all_points,
    )


def _result():
    from app.user import ComparisonResult

    return ComparisonResult(
        locations=[_location()], time_window=(9, 16),
        target_date=TARGET_DATE, created_at=datetime(2026, 7, 20, 4, 1),
    )


def _preset(**display_config) -> dict:
    return {
        "id": "cp-a3-ausblick-grundauswahl",
        "name": "A3 Ausblick Grundauswahl",
        "location_ids": ["innsbruck"],
        "schedule": "daily",
        "profil": "SUMMER_TREKKING",
        "empfaenger": ["gregor-test@henemm.com"],
        "created_at": "2026-01-01T00:00:00Z",
        "display_config": dict(display_config),
    }


def _render_options(preset: dict):
    from services.report_config_resolver import resolve_compare_render_options

    return resolve_compare_render_options(preset)


def _render_mail(opts):
    """Der ECHTE Aufrufpfad, wie ihn der Versand/die Vorschau nutzt --
    ``CompareRenderOptions.outlook_metrics`` reist unveraendert bis in den
    Renderer (kein zweiter, im Test nachgebauter Schnitt)."""
    from output.renderers.comparison import render_compare_email

    return render_compare_email(
        _result(),
        outlook_enabled=opts.outlook_enabled,
        outlook_metrics=opts.outlook_metrics,
    )


def _outlook_tables(html: str):
    soup = BeautifulSoup(html, "html.parser")
    return [t for t in soup.find_all("table")
            if _OUTLOOK_TABLE_MARKER in str(t.get("style", ""))]


def _headers(table) -> list[str]:
    return [th.get_text(strip=True) for th in table.find_all("th")]


def test_ac6_ortsvergleich_ausblick_zeigt_keine_spalte_ausserhalb_von_active_metrics():
    """AC-6: Given der Ortsvergleich mit ``active_metrics`` OHNE "humidity" /
    When sein Ausblick gerendert wird / Then erscheint keine
    Luftfeuchtigkeits-Spalte -- die Kopplung an die Grundauswahl gilt im
    Ortsvergleich genauso wie im Trip.

    Heute (vor A3) klemmt ``report_config_resolver.py:291`` NICHT gegen
    ``active_metrics`` -- die "humidity"-Spalte erscheint trotzdem (RED).
    """
    # active_metrics nutzt das Legacy-Paar-Vokabular des Uebersichts-Resolvers
    # (``compare_metric_ids.resolve_enabled_metrics``, #1373 Scheibe B) --
    # ANDERS als ``outlook_metrics``, das seit #1848 A2 reine Kennungen
    # speichert. Ein Kennungs-String wie 'temperature' waere hier NICHT
    # aufloesbar (kein Katalog-Schluessel) und wuerde defensiv verworfen.
    preset = _preset(
        active_metrics=[
            {"metric_id": "temperature", "aggregation": "max"},
            {"metric_id": "precipitation", "aggregation": "sum"},
        ],
        outlook_metrics=["temperature", "humidity"],
    )
    opts = _render_options(preset)
    html, _text = _render_mail(opts)

    tabellen = _outlook_tables(html)
    assert tabellen, "Kein 3-Tages-Ausblick in der Vergleichsmail gefunden."
    kopf = _headers(tabellen[0])

    assert "Luftfeuchtigkeit" not in kopf, (
        f"Kopfzeile {kopf!r}: 'Luftfeuchtigkeit' erscheint, obwohl 'humidity' "
        "in der Grundauswahl (active_metrics) NICHT aktiv ist (AC-6). Der "
        "Ortsvergleich-Ausblick klemmt die Auswahl noch nicht gegen "
        "active_metrics (report_config_resolver.py:291)."
    )
    assert kopf[1:] == ["Temperatur"], (
        f"Erwartet nur die grundauswahl-gedeckte Spalte 'Temperatur': {kopf!r}"
    )


def test_ac6_ortsvergleich_ohne_active_metrics_bleibt_ungeklemmt_regressionsschutz():
    """Gegenprobe zu AC-6 (Regressionsschutz, muss GRUEN bleiben): ohne
    gesetzte ``active_metrics`` (Altbestand, kein Maximum definiert) darf der
    Ausblick NICHT geschnitten werden -- sonst Totalausfall fuer jeden
    Ortsvergleich ohne konfigurierte Grundauswahl (ADR-0050 D4, analog
    ``test_ausblick_erbt_grundauswahl.py::test_ac16``-Vorbild auf der
    Trip-Seite).
    """
    preset = _preset(outlook_metrics=["temperature", "humidity"])
    opts = _render_options(preset)
    html, _text = _render_mail(opts)

    kopf = _headers(_outlook_tables(html)[0])
    assert set(kopf[1:]) == {"Temperatur", "Luftfeuchtigkeit"}, (
        f"Kopfzeile {kopf!r}: ohne konfigurierte active_metrics darf die "
        "Ausblick-Auswahl nicht geschnitten werden (kein Maximum definiert)."
    )
