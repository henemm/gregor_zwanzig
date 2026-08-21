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


# ═══════ AC-10 / AC-11 im Ortsvergleich — der stille Totalausfall ═══════════

def test_ac10_vs_ac11_ortsvergleich_totalschnitt_faellt_auf_die_grundauswahl_zurueck_bewusst_geleert_bleibt_verschieden(
    caplog,
):
    """AC-10 + AC-11 fuer den ORTSVERGLEICH, beide Faelle im selben Test
    gegenuebergestellt (Spec-Vorgabe: "sonst beweist keiner die
    Unterscheidbarkeit").

    🔴 Warum dieser Test ZUSAETZLICH zu
    ``test_ausblick_erbt_grundauswahl.py::test_ac10_vs_ac11_...`` existiert:
    jener beweist AC-10 am gerenderten TRIP-Block. Fuer den Ortsvergleich lag
    bis hierher nur das Argument vor, ``_build_location_outlook_rows``
    (``compare_html.py``) benutze "dieselbe ``[]``-Gate-Logik". Genau diese
    Argumentation ist kein Nachweis: die Aufloesung laeuft ueber einen
    ANDEREN Einstieg (``resolve_compare_outlook_metrics()`` statt
    ``resolve_trip_outlook_metrics()``, verdrahtet in
    ``report_config_resolver.py``), gegen eine ANDERE Grundauswahl-Quelle
    (``active_metrics`` statt ``display_config.metrics``) und mit einem
    eigenen ``outlook_enabled``-Schalter davor. Jede dieser drei Stellen
    koennte den Rueckfall verschlucken, ohne dass der Trip-Test rot wuerde.
    AC-6 sagt ausdruecklich, die Kopplung gelte in BEIDEN Flaechen -- dann
    braucht die zweite auch ihren eigenen Beleg.

    AC-10: eine NICHT-LEERE, aber nach dem Schnitt gegen ``active_metrics``
    VOLLSTAENDIG verworfene Auswahl (beide Eintraege liegen ausserhalb) muss
    den Ausblick mit der VOLLEN Grundauswahl zeigen, plus Protokoll-Warnung.

    AC-11: eine ausdruecklich leere Auswahl (``outlook_metrics=[]``) laesst
    den Block dagegen vollstaendig entfallen.

    Prueforts-Regel wie im Rest der Datei: gegen die GERENDERTE
    Vergleichsmail, nicht gegen den Rueckgabewert von
    ``resolve_compare_render_options()``.
    """
    import logging

    grundauswahl = [
        {"metric_id": "temperature", "aggregation": "max"},
        {"metric_id": "precipitation", "aggregation": "sum"},
    ]

    # --- AC-10: "humidity"/"uv_index" liegen BEIDE ausserhalb der Grundauswahl.
    preset_ac10 = _preset(
        active_metrics=list(grundauswahl),
        outlook_metrics=["humidity", "uv_index"],
    )
    with caplog.at_level(logging.WARNING):
        opts_ac10 = _render_options(preset_ac10)
        html_ac10, _text_ac10 = _render_mail(opts_ac10)

    tabellen_ac10 = _outlook_tables(html_ac10)
    assert tabellen_ac10, (
        "AC-10 FAIL: der Ausblick der Vergleichsmail ist komplett "
        "verschwunden, obwohl die gespeicherte Auswahl nicht ausdruecklich "
        "leer war -- 'unaufloesbar nach dem Grundauswahl-Schnitt' und "
        "'bewusst geleert' duerfen nie denselben Zustand erzeugen (M3-Bug)."
    )
    kopf_ac10 = _headers(tabellen_ac10[0])
    assert kopf_ac10[1:] == ["Temperatur", "Niederschlag"], (
        f"AC-10: nach dem Totalschnitt zeigt der Ausblick {kopf_ac10[1:]!r} "
        "statt der VOLLEN Grundauswahl ['Temperatur', 'Niederschlag']."
    )
    warnungen = "\n".join(
        r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING
    )
    assert "humidity" in warnungen or "uv_index" in warnungen, (
        f"AC-10: der Rueckfall auf die Grundauswahl wurde nicht protokolliert "
        f"(logger.warning erwartet). Gesehene Warnungen:\n{warnungen}"
    )

    # --- AC-11: ausdruecklich LEERE Auswahl -- Gegenprobe.
    preset_ac11 = _preset(active_metrics=list(grundauswahl), outlook_metrics=[])
    opts_ac11 = _render_options(preset_ac11)
    html_ac11, _text_ac11 = _render_mail(opts_ac11)

    assert _outlook_tables(html_ac11) == [], (
        "AC-11 FAIL: eine ausdruecklich leere Ausblick-Auswahl zeigt in der "
        "Vergleichsmail weiterhin eine Tabelle -- 'bewusst geleert' muss den "
        f"Block vollstaendig entfallen lassen: "
        f"{[_headers(t) for t in _outlook_tables(html_ac11)]!r}"
    )

    # --- Unterscheidbarkeit: die beiden Faelle duerfen NICHT dasselbe liefern.
    assert bool(tabellen_ac10) != bool(_outlook_tables(html_ac11)), (
        "AC-10 und AC-11 sind im Ortsvergleich nicht unterscheidbar -- genau "
        "der Fehler, den A2 an der Nachbarstelle bereits beseitigt hat."
    )
