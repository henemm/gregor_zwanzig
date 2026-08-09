"""#1651: die Nacht-Angabe stammt aus DERSELBEN Quelle wie die Nacht-Tabelle
-- und der Vorschau-Endpunkt sagt dasselbe wie die zugestellte Mail.

Spec: docs/specs/modules/fix_1651_vorschau_zeitfenster.md (AC-3, AC-9, AC-11)
Kontext: docs/context/fix-1651-vorschau-tagesentwarnung.md

Die zentrale Zusicherung dieser Scheibe ist NICHT "die Vorschau erwaehnt die
Nacht", sondern: fuer dieselbe Stunde derselben Mail darf es keine zwei
widersprechenden Quellen geben -- genau daran scheiterte #1498 in der
umgekehrten Richtung. Fuer 00:00-06:00 des Folgetags ist ``night_weather``
massgeblich, dieselbe Reihe, die direkt daneben als "Nacht am Ziel"-Tabelle
steht.

AC-9/AC-11 sind Paritaets-Aussagen und laufen deshalb ueber BEIDE echten
Pfade -- ``_send_trip_report_outcome()`` (Versand) UND
``PreviewService._build_report()`` (Vorschau) -- statt einen Pfad zweimal zu
fahren: ein Nachbau des Versandwegs wuerde die Uebergabe, um die es geht,
selbst mitliefern und nichts pruefen.

Die Falle aus Spec 5b: beide Pfade beschaffen Nachtdaten unter
VERSCHIEDENEN Bedingungen (Versand praktisch immer, Vorschau nur bei
``night_weather_needed()``). Ein Trip ohne Nacht-Tabelle faellt genau dort
auseinander -- und Fixtures MIT Nacht-Tabelle bleiben dabei gruen. AC-11
prueft deshalb ausdruecklich den Trip OHNE Nacht-Tabelle.

DETERMINISMUS (Kern-Schicht, KEIN Netz): die Wetterdaten kommen ueber den
projekteigenen Offline-Schalter ``GZ_TEST_FIXTURE_DIR``
(providers/base.py::get_provider, Issue #346) aus selbst geschriebenen
Fixture-Dateien -- der Produktivpfad bleibt unveraendert, getauscht ist nur
die Datenquelle. KEIN echter Versand: alle drei Kanaele sind abgeschaltet,
der Versandlauf endet mit "no_channels".
"""
from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.models import ThunderLevel

_UTC = ZoneInfo("UTC")
_TODAY = date.today()
_TOMORROW = _TODAY + timedelta(days=1)

# FixtureProvider verankert seine 72 Punkte am aktuellen UTC-Tag.
_IDX_TOMORROW_00 = 24

# Zwei WEIT auseinanderliegende Orte, damit der FixtureProvider fuer die
# Nachtquelle (Ankunft heute, Innsbruck) und die Folgeetappe (Zillertal)
# VERSCHIEDENE Dateien waehlt (providers/fixture.py::_nearest). Nur so ist
# unterscheidbar, aus welcher Quelle die Nacht-Angabe stammt.
_TODAY_COORDS = [(47.2692, 11.4041), (47.2700, 11.4100)]      # -> innsbruck.json
_TOMORROW_COORDS = [(47.2190, 11.8767), (47.2200, 11.8800)]   # -> zillertal.json

_EXPECTED_ADDENDUM = ", nachts starkes Gewitter ab 00:00"


def _fixture_points(thunder_by_index: dict) -> list[dict]:
    """72 Stundenpunkte im Go-Fixture-Format (Issue #263)."""
    return [
        {
            "t2m_c": 15.0, "wind10m_kmh": 10.0, "gust_kmh": 20.0,
            "precip_1h_mm": 0.0, "cloud_total_pct": 30, "pop_pct": 10,
            "thunder_level": thunder_by_index.get(i, "NONE"),
        }
        for i in range(72)
    ]


def _write_split_fixture_dir(tmp_path):
    """Nachtquelle mit Gewitter, Folgeetappe ohne.

    innsbruck  -- Ankunftsort von HEUTE, also die Quelle von
                  ``fetch_night_weather``: Stufe "hoch" um 00:00 morgen.
    zillertal  -- die Etappe von MORGEN: durchgehend gewitterfrei.

    Damit kann die Nacht-Angabe ausschliesslich aus der Nacht-Zeitreihe
    stammen. Holt ein Pfad sie nicht, fehlt sie ihm -- die Divergenz wird
    sichtbar, statt sich hinter einer zweiten, zufaellig gleichen Quelle zu
    verstecken.
    """
    fixture_dir = tmp_path / "openmeteo"
    fixture_dir.mkdir(parents=True, exist_ok=True)
    (fixture_dir / "innsbruck.json").write_text(
        json.dumps({"data": _fixture_points({_IDX_TOMORROW_00: "HIGH"})})
    )
    for name in ("zillertal.json", "stubai.json"):
        (fixture_dir / name).write_text(json.dumps({"data": _fixture_points({})}))
    return fixture_dir


def _trip(*, show_night_block: bool):
    """Trip mit heutiger Etappe (Innsbruck) + Folgeetappe (Zillertal), alle
    Kanaele abgeschaltet.

    Gewitter-Metrik aktiv, Nacht-Tiefsttemperatur NICHT gewaehlt: bei
    ``show_night_block=False`` liefert ``night_weather_needed()`` heute damit
    False -- genau die Bedingung aus Spec 5b.
    """
    from app.models import MetricConfig, TripReportConfig, UnifiedWeatherDisplayConfig
    from app.trip import Stage, TimeWindow, Trip, Waypoint

    def _stage(sid, name, day, coords):
        wps = [
            Waypoint(
                id=f"{sid}-{i}", name="Start" if i == 0 else "Ziel",
                lat=lat, lon=lon, elevation_m=600,
                time_window=TimeWindow(
                    start=time(9, 0) if i == 0 else time(15, 0),
                    end=time(9, 0) if i == 0 else time(15, 0),
                ),
            )
            for i, (lat, lon) in enumerate(coords)
        ]
        return Stage(id=sid, name=name, date=day, start_time=time(9, 0), waypoints=wps)

    display_config = UnifiedWeatherDisplayConfig(
        trip_id="tdd-1651-paritaet",
        metrics=[
            MetricConfig(metric_id="temperature", enabled=True, bucket="primary", order=0),
            MetricConfig(metric_id="thunder", enabled=True, bucket="primary", order=1),
        ],
        updated_at=datetime.now(timezone.utc),
        show_night_block=show_night_block,
    )
    trip = Trip(
        id="tdd-1651-paritaet",
        name="TDD 1651 Paritaet",
        stages=[
            _stage("S1", "Heute", _TODAY, _TODAY_COORDS),
            _stage("S2", "Morgen", _TOMORROW, _TOMORROW_COORDS),
        ],
        display_config=display_config,
        report_config=TripReportConfig(
            trip_id="tdd-1651-paritaet",
            multi_day_trend_reports=["evening"],
            send_email=False, send_sms=False, send_telegram=False,
        ),
    )
    # Kein Netzabruf fuer amtliche Warnungen im Versandlauf.
    trip.official_alerts_enabled = False
    return trip


class _ForecastRecorder:
    """Nimmt den Vorschau-Eintrag ab, den die GETEILTE Scheduler-Methode
    liefert -- die echte Methode laeuft dabei unveraendert durch (kein
    ersetzter Rueckgabewert, kein Mock)."""

    def __init__(self, monkeypatch):
        from services.trip_report_scheduler import TripReportSchedulerService

        self._cls = TripReportSchedulerService
        self._real = TripReportSchedulerService._build_thunder_forecast_from_trend_or_fetch
        self.captured: dict = {}
        recorder = self

        def _wrapped(inner_self, *args, **kwargs):
            result = recorder._real(inner_self, *args, **kwargs)
            recorder.captured[recorder.label] = result
            return result

        self.label = "?"
        monkeypatch.setattr(
            TripReportSchedulerService,
            "_build_thunder_forecast_from_trend_or_fetch",
            _wrapped,
        )

    def entry(self, label: str):
        fc = self.captured.get(label) or {}
        return fc.get("+1")


def _run_both_paths(monkeypatch, tmp_path, *, show_night_block: bool):
    """Faehrt Versand UND Vorschau fuer denselben Trip und Zieltag und gibt
    die beiden ``+1``-Eintraege zurueck."""
    from services.preview_service import PreviewService
    from services.trip_report_scheduler import TripReportSchedulerService
    from services.weather_cache import reset_shared_weather_cache_for_tests

    fixture_dir = _write_split_fixture_dir(tmp_path)
    monkeypatch.setenv("GZ_TEST_FIXTURE_DIR", str(fixture_dir))
    reset_shared_weather_cache_for_tests()

    recorder = _ForecastRecorder(monkeypatch)

    # "morning": Zieltag ist HEUTE, in beiden Pfaden identisch, und der
    # Mehrtages-Ausblick ist aus (multi_day_trend_reports=["evening"]) --
    # damit greift in beiden Pfaden derselbe Bauweg.
    scheduler = TripReportSchedulerService()
    assert scheduler._get_target_date("morning") == _TODAY, (
        "Fixture-Fehler: Versand und Vorschau muessen denselben Zieltag bauen"
    )

    recorder.label = "versand"
    outcome = scheduler._send_trip_report_outcome(_trip(show_night_block=show_night_block), "morning")
    assert outcome == "no_channels", (
        f"Der Versandlauf nahm einen anderen Ausgang als erwartet: {outcome!r} "
        "(alle Kanaele sind abgeschaltet, es darf nichts hinausgehen)"
    )

    recorder.label = "vorschau"
    PreviewService()._build_report(
        _trip(show_night_block=show_night_block), _TODAY, "morning",
    )

    return recorder.entry("versand"), recorder.entry("vorschau")


# ===========================================================================
# AC-3 — Konsistenz mit der Nacht-Tabelle in DERSELBEN Mail
# ===========================================================================


def _night_series_with_high_at_midnight():
    """``night_weather`` wie ``fetch_night_weather`` es liefert: Ankunft
    11.07. 12:00 bis 12.07. 06:00, Gewitter "hoch" um 00:00.

    Passend zu ``tests.unit.test_renderers_email._make_segment_weather()``
    (Ankunft 11.07.2026 12:00 UTC) -- dieselbe Fixture-Basis wie
    tests/tdd/test_briefing_parity_night_thunder.py.
    """
    from app.models import (
        ForecastDataPoint, ForecastMeta, NormalizedTimeseries, Provider,
    )

    def _dp(day: int, hour: int, thunder=ThunderLevel.NONE):
        return ForecastDataPoint(
            ts=datetime(2026, 7, day, hour, 0, tzinfo=timezone.utc),
            t2m_c=9.0, wind10m_kmh=8.0, gust_kmh=15.0, pop_pct=10,
            precip_1h_mm=0.0, cloud_total_pct=40, thunder_level=thunder,
            humidity_pct=60,
        )

    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="icon_d2",
        run=datetime(2026, 7, 11, 0, 0, tzinfo=timezone.utc),
        grid_res_km=2.0, interp="nearest",
    )
    data = [_dp(11, h) for h in range(12, 24)]
    data += [
        _dp(12, h, ThunderLevel.HIGH if h == 0 else ThunderLevel.NONE)
        for h in range(0, 7)
    ]
    return NormalizedTimeseries(meta=meta, data=data)


def test_ac3_nacht_angabe_und_nacht_tabelle_nennen_dieselbe_stunde():
    """AC-3: Given eine Mail, deren "Nacht am Ziel"-Tabelle fuer 00:00 des
    Folgetags "hoch" zeigt / When dieselbe Mail auch die Vorschau-Zeile
    enthaelt / Then nennen beide Stellen dieselbe Stunde und dieselbe Stufe.

    Das ist der gemessene #1651-Widerspruch in einem einzigen gerenderten
    Dokument: heute steht daneben "Kein Gewitter erwartet".

    Der Teilaspekt "Ausblick-Tabelle" von AC-3 ist mit dem Scheiben-Schnitt
    vom 2026-08-09 nach #1653 herausgeloest; geprueft wird hier ausschliesslich
    die Vorschau-Zeile gegen die Nacht-Tabelle.

    Kein Netz: ``night_weather`` ist ein konstruiertes, echtes
    ``NormalizedTimeseries``; der Vorschau-Eintrag wird ueber die ECHTE
    Scheduler-Methode aus GENAU DIESER Reihe abgeleitet -- also nicht
    unabhaengig behauptet, sondern aus derselben Quelle gezogen.
    """
    from output.renderers.trip_report import TripReportFormatter
    from services.trip_report_scheduler import TripReportSchedulerService
    from tests.unit.test_renderers_email import _make_segment_weather

    night = _night_series_with_high_at_midnight()
    target = date(2026, 7, 11)

    from app.models import ForecastDataPoint, SegmentWeatherSummary
    from output.renderers.email.outlook import build_outlook_row

    # Die Etappe von morgen ist tagsueber gewitterfrei -- der Hinweis kann
    # ausschliesslich aus der Nacht-Reihe kommen.
    quiet_points = [
        ForecastDataPoint(
            ts=datetime(2026, 7, 12, h, 0, tzinfo=timezone.utc),
            thunder_level=ThunderLevel.NONE,
        )
        for h in range(0, 24)
    ]
    summary = SegmentWeatherSummary(
        temp_min_c=10.0, temp_max_c=20.0, wind_max_kmh=10.0,
        precip_sum_mm=0.0, thunder_level_max=ThunderLevel.NONE,
    )
    row = build_outlook_row(summary, quiet_points, "So", _UTC)
    row["date"] = date(2026, 7, 12)

    forecast = TripReportSchedulerService()._build_thunder_forecast_from_trend_or_fetch(
        None, target, _UTC, multi_day_trend=[row], night_weather=night,
    )

    report = TripReportFormatter().format_email(
        segments=[_make_segment_weather()],
        trip_name="GR20",
        report_type="morning",
        night_weather=night,
        thunder_forecast=forecast,
        stage_name="GR20 E3",
        tz=_UTC,
    )
    plain = report.email_plain

    # Vorbedingung: die Nacht-Tabelle DIESER Mail nennt 00:00 als "hoch".
    night_rows = [
        ln for ln in plain.splitlines() if ln.strip().startswith("00 ")
    ]
    assert night_rows and "hoch" in night_rows[0], (
        "Fixture-Fehler: die Nacht-Tabelle muss fuer 00:00 'hoch' zeigen, "
        f"sonst prueft dieser Test nichts: {night_rows!r}"
    )

    # AC-3: die Vorschau derselben Mail nennt exakt dieselbe Stunde/Stufe.
    assert "Kein Gewitter erwartet, nachts starkes Gewitter ab 00:00" in plain, (
        "Vorschau und Nacht-Tabelle derselben Mail widersprechen sich fuer "
        "00:00 -- die Vorschau entwarnt, die Tabelle zeigt 'hoch'.\n"
        f"{plain}"
    )


# ===========================================================================
# AC-9 / AC-11 — Paritaet Vorschau-Endpunkt <-> zugestellte Mail
# ===========================================================================


def test_ac9_vorschau_und_versand_nennen_denselben_satz(monkeypatch, tmp_path):
    """AC-9: Given derselbe Trip und Zieltag, Nachtgewitter "hoch" um 00:00 /
    When der Vorschau-Satz einmal ueber den Vorschau-Endpunkt und einmal ueber
    den Versandpfad entsteht / Then ist er zeichengleich -- und beide nennen
    das Nachtgewitter.

    Beide Pfade laufen hier wirklich; die Nacht-Zeitreihe muss in beiden VOR
    dem Bau des Vorschau-Eintrags vorliegen (Spec 5a). Liegt sie in einem der
    beiden erst danach vor, fehlt dort der Halbsatz -- und die Gleichheit
    faellt.
    """
    versand, vorschau = _run_both_paths(monkeypatch, tmp_path, show_night_block=True)

    assert versand is not None and vorschau is not None, (
        f"Fixture-Fehler: kein '+1'-Eintrag gebaut ({versand!r} / {vorschau!r})"
    )
    assert _EXPECTED_ADDENDUM in versand["text"], (
        "Der VERSANDPFAD verschweigt das Nachtgewitter um 00:00: "
        f"{versand['text']!r}"
    )
    assert _EXPECTED_ADDENDUM in vorschau["text"], (
        "Der VORSCHAU-PFAD verschweigt das Nachtgewitter um 00:00: "
        f"{vorschau['text']!r}"
    )
    assert versand["text"] == vorschau["text"], (
        "Vorschau-Endpunkt und zugestellte Mail nennen verschiedene Saetze:\n"
        f"  Versand:  {versand['text']!r}\n"
        f"  Vorschau: {vorschau['text']!r}"
    )


def test_ac11_paritaet_auch_ohne_nacht_tabelle(monkeypatch, tmp_path):
    """AC-11 (die Falle aus Spec 5b): Given ein Trip mit aktiver
    Gewitter-Metrik, aber OHNE Nacht-Tabelle und ohne gewaehlte
    Nacht-Tiefsttemperatur / When derselbe Tag einmal ueber den
    Vorschau-Endpunkt und einmal ueber den Versand entsteht / Then nennen
    beide dieselbe Nachtstunde.

    Heute beschafft der Vorschau-Pfad hier ueberhaupt keine Nachtdaten
    (``night_weather_needed()`` prueft nur Nacht-Tabelle und
    Nacht-Tiefsttemperatur), waehrend der Versand sie immer holt. Eine
    Reihenfolge-Korrektur allein reicht deshalb nicht -- die geteilte
    Entscheidung selbst muss die Gewitter-Metrik kennen.
    """
    versand, vorschau = _run_both_paths(monkeypatch, tmp_path, show_night_block=False)

    assert versand is not None and vorschau is not None, (
        f"Fixture-Fehler: kein '+1'-Eintrag gebaut ({versand!r} / {vorschau!r})"
    )
    assert _EXPECTED_ADDENDUM in versand["text"], (
        f"Der VERSANDPFAD verschweigt das Nachtgewitter: {versand['text']!r}"
    )
    assert _EXPECTED_ADDENDUM in vorschau["text"], (
        "Der VORSCHAU-PFAD nennt das Nachtgewitter nicht -- er greift auf eine "
        "andere Quelle zu als der Versand (Spec 5b): "
        f"{vorschau['text']!r}"
    )
    assert versand["text"] == vorschau["text"], (
        "Ohne Nacht-Tabelle divergieren Vorschau und Versand:\n"
        f"  Versand:  {versand['text']!r}\n"
        f"  Vorschau: {vorschau['text']!r}"
    )


def test_ac11_geteilte_entscheidung_kennt_die_gewitter_metrik():
    """AC-11 an der geteilten Entscheidung selbst: ``night_weather_needed()``
    ist laut eigenem Docstring die EINE Entscheidung fuer beide Pfade. Ab
    dieser Scheibe speisen Nachtdaten auch die Nacht-Angabe -- eine aktive
    Gewitter-Metrik macht sie damit noetig, auch ohne Nacht-Tabelle.

    Gegenprobe im selben Test: ohne Gewitter-Metrik (und ohne die beiden
    bisherigen Gruende) bleibt die Antwort Nein -- es entsteht kein
    pauschaler Zusatz-Abruf fuer jeden Trip.
    """
    import dataclasses

    from app.metric_catalog import build_default_display_config
    from services.segment_weather import night_weather_needed

    base = build_default_display_config(trip_id="tdd-1651-needed")
    without_night = dataclasses.replace(
        base,
        show_night_block=False,
        metrics=[
            dataclasses.replace(mc, enabled=(mc.metric_id == "thunder"))
            for mc in base.metrics
        ],
    )
    assert without_night.is_metric_enabled("thunder"), "Fixture-Fehler"
    assert not without_night.is_metric_enabled("temperature_night"), "Fixture-Fehler"

    assert night_weather_needed(without_night) is True, (
        "Die geteilte Entscheidung haelt Nachtdaten fuer entbehrlich, obwohl "
        "die Gewitter-Metrik aktiv ist -- der Vorschau-Pfad bekaeme dann eine "
        "andere Quelle als der Versand (Spec 5b)"
    )

    nothing_enabled = dataclasses.replace(
        base,
        show_night_block=False,
        metrics=[dataclasses.replace(mc, enabled=False) for mc in base.metrics],
    )
    assert night_weather_needed(nothing_enabled) is False, (
        "Ohne Nacht-Tabelle, ohne Nacht-Tiefsttemperatur und ohne "
        "Gewitter-Metrik darf kein Nachtabruf entstehen"
    )
