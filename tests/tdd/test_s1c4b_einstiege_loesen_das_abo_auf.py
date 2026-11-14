"""Issue #2792 S1c-4b — jeder Einstieg löst das ABO auf, nie still „allgemein".

SPEC: docs/specs/modules/feat_2792_s1_profil_ampel.md v1.5, §5 Nachtrag
S1c-4 Punkt 1 und Nachtrag S1c-4b Punkte 1–6, AC-1, AC-7, AC-15, AC-21,
AC-25; Testplan „Wirkungstest je Einstieg", „Vier Kanäle aus einer dc",
F001 (Scheduler-Ausblick), F002 (Ein-Ort-Alarm).

Jeder Test ruft den EINSTIEG selbst (Formatter, Scheduler, Dienst) mit einem
Abo, das seine Vorlage trägt (``display_config.preset_name`` bzw. Preset mit
``profil``/``display_config.ampel``), und misst die Bewertung dort, wo sie
ankommt: Farbe, Erwähnung, Hervorhebung. Eine innere Ampel wird nie direkt
übergeben — sonst bliebe ein Einstieg, der weiter ``resolve_ampel(None)``
ruft, unsichtbar (die S1c-1-Kettentests decken die Zwischenglieder ab).

Unterscheidende Werte (aus ``app/ampel_templates.py`` gemessen):
  Temp +9 °C     Skitouren orange (ab 8)   / Allgemein grün (gelb ab 28)
  Böen 35 km/h   Skitouren grün (gelb 40)  / Allgemein gelb (gelb ab 30)
  Böen 52 km/h   Skitouren gelb (orange 55)/ Allgemein orange (ab 45)

Beide Reihenfolgen laufen im selben Prozess (keine Zustandsübernahme). In
S1c-4a lösen alle Einstiege fest „allgemein" auf: die Allgemein-Seite jedes
Tests ist deshalb schon grün, die Skitouren-Seite rot.

Kern-Schicht: echte Domänenobjekte, Transport-Mitschrift statt Sockets,
keine Mocks, kein Netz.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from bs4 import BeautifulSoup

UTC = timezone.utc
TZ = ZoneInfo("UTC")
REIHENFOLGEN = [("skitouren", "allgemein"), ("allgemein", "skitouren")]
IDS = ["ski_dann_allg", "allg_dann_ski"]


def _tone_bg(level: str) -> str:
    from output.renderers.email.design_tokens import tone_css
    return tone_css(level)[0]


def _dot_fill(level: str) -> str:
    from output.renderers.email.helpers import _AMPEL_DOT_COLORS
    return _AMPEL_DOT_COLORS[level][0]


def _punkte_farben(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    return [s["style"].split("background:", 1)[1].split(";", 1)[0]
            for s in soup.find_all("span")
            if "border-radius:50%" in (s.get("style") or "") and "width:10px" in s["style"]]


# ---------------------------------------------------------------------------
# Trip: ein Tag, Gehzeit 08–14 UTC
# ---------------------------------------------------------------------------

def _tagesreihe(tag: date, *, nacht_gewitter: bool = False):
    from app.models import ForecastDataPoint, ForecastMeta, NormalizedTimeseries, Provider, ThunderLevel
    punkte = [ForecastDataPoint(
        ts=datetime(tag.year, tag.month, tag.day, h, tzinfo=UTC),
        t2m_c=9.0 if h == 11 else 2.0, wind_chill_c=0.0, wind10m_kmh=12.0,
        gust_kmh=35.0 if 9 <= h <= 11 else 15.0, precip_1h_mm=0.0, pop_pct=0,
        thunder_level=ThunderLevel.HIGH if (nacht_gewitter and h == 21) else ThunderLevel.NONE,
        humidity_pct=50, visibility_m=20000, cloud_total_pct=20,
    ) for h in range(24)]
    meta = ForecastMeta(provider=Provider.OPENMETEO, model="test",
                        run=datetime(tag.year, tag.month, tag.day, tzinfo=UTC),
                        grid_res_km=1.0, interp="point_grid")
    return NormalizedTimeseries(meta=meta, data=punkte)


def _segmente(tag: date = date(2026, 7, 20), *, bis: int = 14, nacht_gewitter: bool = False):
    """Echtes Aggregat aus dem Produktivpfad (``_aggregate_for_segment``)."""
    from app.models import GPXPoint, TripSegment
    from providers.openmeteo import OpenMeteoProvider
    from services.segment_weather import SegmentWeatherService
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=47.0, lon=11.0, elevation_m=1000, distance_from_start_km=0.0),
        end_point=GPXPoint(lat=47.05, lon=11.05, elevation_m=1500, distance_from_start_km=6.0),
        start_time=datetime(tag.year, tag.month, tag.day, 8, tzinfo=UTC),
        end_time=datetime(tag.year, tag.month, tag.day, bis, tzinfo=UTC),
        duration_hours=float(bis - 8), distance_km=6.0, ascent_m=500, descent_m=0,
    )
    return [SegmentWeatherService(OpenMeteoProvider())._aggregate_for_segment(
        seg, _tagesreihe(tag, nacht_gewitter=nacht_gewitter),
        fetched_at=datetime(tag.year, tag.month, tag.day, 4, tzinfo=UTC))]


_METRIKEN = ("temperature", "temperature_day_low", "temperature_day_high", "gust", "wind")


def _dc(vorlage: str | None, *metriken: str):
    """Abo-Konfiguration; die Böen tragen eine alte ``sms_threshold`` 20,
    die nach E1 nicht mehr wirken darf (AC-7)."""
    from app.models import MetricConfig, UnifiedWeatherDisplayConfig
    return UnifiedWeatherDisplayConfig(
        trip_id="s1c4b", preset_name=vorlage,
        metrics=[MetricConfig(metric_id=m, enabled=True,
                              sms_threshold=20.0 if m == "gust" else None)
                 for m in (metriken or _METRIKEN)],
    )


def _bericht(vorlage: str, email_format: str = "full"):
    from app.models import TripReportConfig
    from output.renderers.trip_report import TripReportFormatter
    return TripReportFormatter().format_email(
        _segmente(), trip_name="S1c4b", report_type="morning",
        display_config=_dc(vorlage), stage_name="E1", tz=TZ,
        report_config=TripReportConfig(trip_id="s1c4b", email_format=email_format),
    )


def _boeen_pille(text: str) -> str:
    """Kachel-Zeile der Böen im Metriken-Überblick (eingerückt, nicht die
    Kurzzusammenfassung)."""
    zeilen = [z for z in text.splitlines()
              if z.startswith("  ") and "35" in z and any(w in z for w in ("Böen", "Boeen", "Gust"))]
    assert zeilen, f"Vorbedingung: Böen-Kachel fehlt\n{text[:3000]}"
    return zeilen[0]


@pytest.mark.parametrize("reihenfolge", REIHENFOLGEN, ids=IDS)
def test_trip_mail_html_bewertet_nach_der_vorlage_des_abos(reihenfolge):
    """``render_html`` über ``format_email``: +9 °C ist nur bei Skitouren
    orange (Kachel und Stundentabelle), bei Allgemein kommt kein Orange vor."""
    html = {v: _bericht(v).email_html for v in reihenfolge}
    orange = (_tone_bg("orange"), _dot_fill("orange"))
    assert any(o in html["skitouren"] for o in orange), "Skitouren: +9 °C muss orange sein"
    assert not any(o in html["allgemein"] for o in orange)
    assert html["skitouren"] != html["allgemein"]


@pytest.mark.parametrize("reihenfolge", REIHENFOLGEN, ids=IDS)
def test_trip_mail_klartext_erwaehnt_nach_der_vorlage_des_abos(reihenfolge):
    """``render_plain``: Böen 35 km/h sind bei Allgemein gelb (Erwähnung in
    Ereignis-Form „ab 09:00"), bei Skitouren grün (nur Höchstwert). Die alte
    ``sms_threshold`` 20 wirkt nicht mehr (AC-19 e, E1, AC-27)."""
    plain = {v: _bericht(v).email_plain for v in reihenfolge}
    assert "ab 09:00" not in _boeen_pille(plain["skitouren"])
    assert "ab 09:00" in _boeen_pille(plain["allgemein"])


@pytest.mark.parametrize("reihenfolge", REIHENFOLGEN, ids=IDS)
def test_trip_mail_kompakt_bewertet_nach_der_vorlage_des_abos(reihenfolge):
    """``render_compact``: Schwerezeichen der Kacheln aus der Abo-Ampel
    (orange = „!!"): Temperatur +9 °C nur bei Skitouren „!!"."""
    kompakt = {v: _bericht(v, "compact").email_plain for v in reihenfolge}
    temp_ski = [z for z in kompakt["skitouren"].splitlines() if "9" in z and "!!" in z]
    assert temp_ski, f"Skitouren: +9 °C-Kachel muss „!!“ tragen\n{kompakt['skitouren']}"
    assert not [z for z in kompakt["allgemein"].splitlines() if z.strip().startswith("!!")]
    assert "ab 09:00" not in _boeen_pille(kompakt["skitouren"])
    assert "ab 09:00" in _boeen_pille(kompakt["allgemein"])


def _temp_zeile(bubbles: list[str]) -> str:
    """Kurzübersicht-Zeile der Temperatur (``T 2.0-9.0…``)."""
    for b in bubbles:
        for z in b.splitlines():
            if z.startswith("T ") and "9.0" in z:
                return z
    raise AssertionError(f"Vorbedingung: Temperatur-Zeile fehlt\n{bubbles}")


@pytest.mark.parametrize("reihenfolge", REIHENFOLGEN, ids=IDS)
def test_telegram_briefing_hebt_temperatur_nach_der_vorlage_hervor(reihenfolge):
    """AC-1, ``render_telegram_bubbles``: +9 °C ist bei Skitouren gelb oder
    schlechter und als Spitzenwert mit Stunde hervorgehoben (``9.0@11``),
    bei Allgemein (grün) nicht — die beiden Zeilen unterscheiden sich."""
    blasen = {v: _bericht(v).telegram_bubbles for v in reihenfolge}
    assert "9.0@11" in _temp_zeile(blasen["skitouren"])
    assert _temp_zeile(blasen["skitouren"]) != _temp_zeile(blasen["allgemein"])


def _sms_token(sms: str, kuerzel: str) -> str:
    for tok in sms.split():
        if tok.startswith(kuerzel) and not tok[len(kuerzel):][:1].isalpha():
            return tok
    raise AssertionError(f"Token {kuerzel} fehlt in {sms!r}")


@pytest.mark.parametrize("reihenfolge", REIHENFOLGEN, ids=IDS)
def test_trip_sms_hebt_nach_der_ampel_derselben_dc_hervor(reihenfolge):
    """AC-1/AC-7, ``format_sms`` aus derselben ``dc`` wie die Mail
    (Premium-SMS sendet denselben Text): Skitouren ``D2/9@11`` (Bereichs-
    Token, nur die gelbe Hälfte trägt ihre Stunde, §5) und Böen ``G-`` (35
    unter Gelb 40, die alte Schwelle 20 wirkt nicht); Allgemein ``D2/9``
    ohne Stunde und Böen ab 09 Uhr hervorgehoben."""
    sms = {v: _bericht(v).sms_text for v in reihenfolge}
    assert _sms_token(sms["skitouren"], "D") == "D2/9@11"
    assert _sms_token(sms["skitouren"], "G") == "G-"
    assert _sms_token(sms["allgemein"], "D") == "D2/9"
    assert _sms_token(sms["allgemein"], "G").startswith("G35@9")


def test_abgeleitete_kanal_kopien_behalten_die_vorlage():
    """Nachtrag v1.5 Punkt 2: ``dataclasses.replace(dc, metrics=…)`` (Mail-
    Kollabierung, ``_dc_telegram``) darf ``preset_name`` nicht verlieren —
    die vier Kanäle einer ``dc`` bewerten gemeinsam nach Skitouren."""
    ski, allg = _bericht("skitouren"), _bericht("allgemein")
    assert ski.email_html != allg.email_html
    assert ski.email_plain != allg.email_plain
    assert ski.telegram_bubbles != allg.telegram_bubbles
    assert ski.sms_text != allg.sms_text


# ---------------------------------------------------------------------------
# F001: Ausblick über den echten Scheduler-Weg (``_build_stage_trend``)
# ---------------------------------------------------------------------------

def _scheduler(segmente):
    from services.trip_report_scheduler import TripReportSchedulerService

    class _FesteDaten(TripReportSchedulerService):
        def _convert_trip_to_segments(self, trip, target_date):
            return ["ein-segment"]

        def _fetch_weather(self, seg, provider=None):
            return segmente

        def _enrich_ensemble_for_trip(self, trip, weather_data):
            return None

    return _FesteDaten(user_id="default")


def _ausblick_zeile(dc):
    from app.trip import Stage, Trip, Waypoint
    morgen = date.today() + timedelta(days=1)
    trip = Trip(id="s1c4b-ausblick", name="Ausblick", display_config=dc, stages=[Stage(
        id="S1", name="E1", date=morgen,
        waypoints=[Waypoint(id="W1", name="Ort", lat=47.0, lon=11.0, elevation_m=1000)])])
    ergebnis = _scheduler(_segmente(morgen, bis=22, nacht_gewitter=True))._build_stage_trend(
        trip, date.today(), now_utc=datetime.now(UTC), tz=TZ)
    assert ergebnis.rows, f"Vorbedingung: Ausblick gebaut ({ergebnis.state})"
    return ergebnis.rows[0]


@pytest.mark.parametrize("reihenfolge", REIHENFOLGEN, ids=IDS)
def test_scheduler_ausblick_faerbt_nach_dem_trip_und_bleibt_im_trip_zweig(reihenfolge):
    """F001 + Nachtrag v1.5 Punkt 3: der Scheduler löst je ``stage_trip``
    die Ampel auf. Tageshoch +9 °C ist bei Skitouren orange, bei Allgemein
    ungefärbt. Die Gewitterstunde 21 Uhr liegt im Etappenaggregat, aber
    nachts (Tagesfenster #1841): der Trip-Zweig zeigt „–" — ein
    vertauschtes ``context`` zeigte das Aggregat „hoch"."""
    zeilen = {v: _ausblick_zeile(_dc(v, "temperature", "thunder")) for v in reihenfolge}
    for v, erwartet in (("skitouren", f"background:{_tone_bg('orange')};"), ("allgemein", "")):
        assert zeilen[v]["cell_bg"][0] == erwartet, (v, zeilen[v])
        assert zeilen[v]["cells"][1] == "–", (v, zeilen[v]["cells"])


def test_scheduler_ausblick_trip_ohne_display_config_bleibt_allgemein_im_trip_zweig():
    """Korrektur v1.5: ein Trip ohne ``display_config`` hat keine Vorlage —
    Ausblick ohne Auswahl (Altbestand), kein Absturz, Gewitter nur aus dem
    Tagesfenster (Nacht-Gewitter erscheint nicht als Tageswert)."""
    from output.renderers.email.helpers import format_trend_tokens
    zeile = _ausblick_zeile(None)
    assert "cells" not in zeile and zeile["temp_hi"] == 9
    from tests.helpers.ampel_allgemein import AMPEL_ALLGEMEIN
    assert format_trend_tokens(zeile, ampel=AMPEL_ALLGEMEIN)["thunder_day_token"] == "-"


# ---------------------------------------------------------------------------
# Vergleich: Mail, Klartext, Kopfzelle „Profil"
# ---------------------------------------------------------------------------

def _ergebnis():
    from app.models import ForecastDataPoint, ThunderLevel
    from app.user import ComparisonResult, LocationResult, SavedLocation
    tag = date(2026, 7, 11)
    stunden = [ForecastDataPoint(
        ts=datetime(2026, 7, 11, h, tzinfo=UTC), t2m_c=9.0, wind10m_kmh=10.0, gust_kmh=15.0,
        precip_1h_mm=0.0, pop_pct=10, cloud_total_pct=30, thunder_level=ThunderLevel.NONE,
        visibility_m=20000) for h in (9, 10, 11, 12, 13, 14)]
    orte = [LocationResult(
        location=SavedLocation(id=f"o{i}", name=n, lat=47.27, lon=11.39, elevation_m=574, timezone="UTC"),
        temp_max=9.0, temp_min=9.0, hourly_data=stunden) for i, n in enumerate(("Alpe", "Joch", "Tal"))]
    return ComparisonResult(locations=orte, time_window=(9, 15), target_date=tag,
                            created_at=datetime(2026, 7, 11, 6, tzinfo=UTC))


def _preset(vorlage: str) -> dict:
    return {"id": f"cp-{vorlage}", "profil": "allgemein",
            "display_config": {"ampel": {"template": vorlage}}}


@pytest.mark.parametrize("reihenfolge", REIHENFOLGEN, ids=IDS)
def test_vergleichs_mail_faerbt_nach_dem_preset(reihenfolge):
    """AC-20/AC-25, ``render_compare_html``: +9 °C in Übersicht und
    Stundenverlauf bei Skitouren orange, bei Allgemein ungetönt."""
    from output.renderers.email.compare_html import render_compare_html
    html = {v: render_compare_html(_ergebnis(), preset=_preset(v), hourly_metrics=["t2m_c"])
            for v in reihenfolge}
    orange = f"background:{_tone_bg('orange')};"
    assert orange in html["skitouren"]
    assert orange not in html["allgemein"]


def test_vergleichs_mail_verlangt_das_preset():
    """§5 Nachtrag Punkt 3: ``render_compare_html(preset=None)`` ist
    abgeschafft — ohne Preset scheitert der Aufruf laut."""
    import inspect

    from output.renderers.email.compare_html import render_compare_html
    p = inspect.signature(render_compare_html).parameters["preset"]
    assert p.kind is inspect.Parameter.KEYWORD_ONLY and p.default is inspect.Parameter.empty
    with pytest.raises(TypeError):
        render_compare_html(_ergebnis())  # type: ignore[call-arg]


def _profil_zelle(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    td = soup.select_one("table.header-stats-desktop td")
    assert td is not None, "Vorbedingung: Kopfzeile mit Kennzahlen"
    return td.find_all("div")[1].get_text(strip=True)


@pytest.mark.parametrize("profil,lang,label", [
    ("summer_trekking", "de", "Alpen-Trekking"), ("summer_trekking", "en", "Alpine trekking"),
    ("WANDERN", "de", "Wandern"), ("WANDERN", "en", "Hiking"),
    ("unbekannt-xyz", "de", "Allgemein"), ("unbekannt-xyz", "en", "General"),
])
def test_vergleichs_kopfzelle_profil_zeigt_das_vorlagen_label(profil, lang, label):
    """AC-15 (Nachtrag v1.4) / AC-19 f: die Zelle „Profil" zeigt das Label
    der aufgelösten Vorlage in der Nutzersprache (``mail.vorlage.*``)."""
    from output.renderers.email.compare_html import render_compare_html
    html = render_compare_html(_ergebnis(), preset={"id": "cp", "profil": profil}, lang=lang)
    assert _profil_zelle(html) == label


# ---------------------------------------------------------------------------
# Alarme: Trip, Vergleich (mehrere Orte und Ein-Ort-Wrapper), Radar
# ---------------------------------------------------------------------------

_BOEEN = ((10, 10.0), (11, 35.0), (12, 35.0), (13, 52.0), (14, 10.0))


def _punkt(name: str):
    from app.models import SegmentWeatherSummary
    from services.point_weather import PointWeatherData
    from services.weather_snapshot import _deserialize_timeseries
    rows = [{"ts": datetime(2026, 5, 1, h, tzinfo=UTC).isoformat(), "t2m_c": 10.0,
             "wind10m_kmh": 10.0, "gust_kmh": g} for h, g in _BOEEN]
    return PointWeatherData(
        id=name.lower(), name=name, lat=47.0, lon=11.0,
        timeseries=_deserialize_timeseries({"hourly": rows}, "openmeteo"),
        aggregated=SegmentWeatherSummary(), fetched_at=datetime(2026, 5, 1, 6, tzinfo=UTC),
        provider="openmeteo")


def _aenderung():
    from app.models import ChangeSeverity, WeatherChange
    return WeatherChange(
        metric="gust_max_kmh", old_value=10.0, new_value=52.0, delta=42.0, threshold=20.0,
        severity=ChangeSeverity.MAJOR, direction="increase", segment_id="1",
        occurred_at=datetime(2026, 5, 1, 13, tzinfo=UTC))


def _dienst(monkeypatch, name: str):
    from services.notification_service import NotificationService
    from tests.helpers.sms_empfaenger import mit_profil_kanaele
    from tests.tdd.test_alert_hour_rows import _settings, _user
    settings = _settings()
    return NotificationService(settings, mit_profil_kanaele(_user(f"s1c4b-{name}"), settings))


def _stundenpunkte(mail: str) -> list[str]:
    farben = _punkte_farben(mail)
    assert farben or "13" in mail, "Vorbedingung: Stundenzeilen in der Alarm-Mail"
    return farben


@pytest.mark.parametrize("weg", ["mehrere_orte", "ein_ort"])
@pytest.mark.parametrize("reihenfolge", REIHENFOLGEN, ids=IDS)
def test_vergleichs_abweichungsalarm_waehlt_stunden_nach_dem_preset(monkeypatch, reihenfolge, weg):
    """AC-21/AC-25, ``send_multi_location_deviation_alert`` und (F002) der
    Durchreiche-Wrapper ``send_location_deviation_alert``: ohne Anker zählen
    die Stunden ab Gelb. Skitouren: nur 13 Uhr UTC (52 gelb); Allgemein:
    11–13 Uhr (35 gelb, 52 orange). Zwei Nutzer, je eigenes Preset. Feste
    Uhr (Stand 06:07 Ortszeit), damit keine Stand-Zeile „13:00" trifft."""
    from freezegun import freeze_time

    from tests.helpers.transport_mitschrift import aufzeichner_installieren
    aufzeichner_installieren(monkeypatch)
    mails: dict[str, list[str]] = {}
    for v in reihenfolge:
        mails[v] = []
        dienst = _dienst(monkeypatch, v)
        senke = (lambda subject, body, _m=mails[v]: _m.append(body))
        with freeze_time("2026-05-01 04:07:00"):
            if weg == "ein_ort":
                dienst.send_location_deviation_alert(
                    "Alpe", [_punkt("Alpe")], [_aenderung()], {"email"}, mail_sink=senke, preset=_preset(v))
            else:
                dienst.send_multi_location_deviation_alert(
                    entities=[("Alpe", [_punkt("Alpe")], [_aenderung()])], effective_channels={"email"},
                    mail_sink=senke, preset=_preset(v))
    assert len(mails["skitouren"]) == 1 and len(mails["allgemein"]) == 1
    ski, allg = mails["skitouren"][0], mails["allgemein"][0]
    assert ski.count("15:00") >= 1 and "13:00" not in ski, "Skitouren: nur die 52-km/h-Stunde"
    assert "13:00" in allg and "14:00" in allg


def _trip_alarm(vorlage: str):
    from app.models import MetricConfig, UnifiedWeatherDisplayConfig
    from app.trip import Stage, Trip, Waypoint
    tid = f"trip-s1c4b-{vorlage}"
    return Trip(
        id=tid, name="Ampel-Trip", official_warnings=None, corridors=[],
        # Issue #2069: zwei Wegpunkte = ein echtes Segment "1" -- die
        # Abweichungs-Vorschau rendert echte Segmente statt Platzhaltern.
        stages=[Stage(id="T1", name="Tag 1", date=date(2026, 5, 1), waypoints=[
            Waypoint(id="G1", name="Start", lat=47.0, lon=11.0, elevation_m=1000.0),
            Waypoint(id="G2", name="Ziel", lat=47.05, lon=11.05, elevation_m=1400.0)])],
        display_config=UnifiedWeatherDisplayConfig(
            trip_id=tid, preset_name=vorlage,
            metrics=[MetricConfig(metric_id="gust", enabled=True)],
            per_channel_layouts={"email": [
                MetricConfig(metric_id="gust", enabled=True, format_mode="simplified")]}))


@pytest.mark.parametrize("reihenfolge", REIHENFOLGEN, ids=IDS)
def test_trip_abweichungsalarm_faerbt_ueber_den_versandweg_nach_dem_trip(monkeypatch, reihenfolge):
    """AC-21, ``send_deviation_alert`` (echter Versandweg, zwei Nutzer):
    Böen 31 km/h um 12 Uhr UTC — Allgemein gelb, Skitouren grün."""
    from tests.helpers.transport_mitschrift import aufzeichner_installieren
    from tests.tdd.test_alert_hour_rows import _load, _segment_data, _wc
    fx = _load("boeen_stufe_statt_schwelle.json")
    mit = aufzeichner_installieren(monkeypatch)
    punkte = {}
    for v in reihenfolge:
        vorher = len(mit.sendungen("email"))
        _dienst(monkeypatch, v).send_deviation_alert(
            trip=_trip_alarm(v), weather=[_segment_data(fx, fx["fresh"])], changes=[_wc(fx["change"])],
            effective_channels={"email"}, anchor_weather=[_segment_data(fx, fx["anchor"])])
        mails = mit.sendungen("email")
        assert len(mails) == vorher + 1
        punkte[v] = _stundenpunkte(mails[-1]["body"])
    assert _dot_fill("yellow") in punkte["allgemein"]
    assert _dot_fill("yellow") not in punkte["skitouren"]


def test_radar_alarm_nachricht_traegt_die_vorlage_des_trips():
    """``build_onset_alert_message``: die gebaute Nachricht trägt die Ampel
    des Trips (Vorlage aus ``display_config.preset_name``)."""
    from types import SimpleNamespace

    from services.radar_alert_service import build_onset_alert_message
    aktiv = SimpleNamespace(start_point=SimpleNamespace(lat=42.2, lon=9.0), distance_km=8.0)
    for v in ("skitouren", "allgemein", "skitouren"):
        trip = SimpleNamespace(name="GR20", alert_cooldown_minutes=120,
                               display_config=SimpleNamespace(preset_name=v, ampel=None))
        msg = build_onset_alert_message(trip, aktiv, 25, "06:25", "Leichter Regen", "Radar (DWD)")
        assert msg.ampel["template"] == v


# ---------------------------------------------------------------------------
# Einstiege ohne sichtbare Farbe: die gebaute Nachricht trägt die Abo-Ampel
# ---------------------------------------------------------------------------

def _mitschreiben(monkeypatch, modul, name: str) -> list:
    """Die echte Funktion bleibt wirksam; nur ihr Ergebnis wird mitgeschrieben."""
    echt, seen = getattr(modul, name), []

    def aufzeichnen(*a, **k):
        seen.append(echt(*a, **k))
        return seen[-1]
    monkeypatch.setattr(modul, name, aufzeichnen)
    return seen


def _vorlagen(nachrichten) -> list[str]:
    return [m.ampel["template"] for m in nachrichten]


def _ort():
    from app.user import SavedLocation
    return SavedLocation(id="o0", name="Ort0", lat=47.27, lon=11.39, elevation_m=574, timezone="UTC")


@pytest.mark.parametrize("reihenfolge", REIHENFOLGEN, ids=IDS)
def test_radar_alarme_versenden_mit_der_ampel_des_abos(monkeypatch, reihenfolge):
    """``send_radar_alert`` (Trip) und ``send_multi_location_radar_alert``
    (Vergleich): die an den echten Versand (Transport-Mitschrift) gereichte
    Nachricht trägt die Vorlage des Abos."""
    from services.notification_service import NotificationService, RadarAlertRequest
    from services.radar_service import NowcastResult
    from tests.helpers.transport_mitschrift import aufzeichner_installieren
    aufzeichner_installieren(monkeypatch)
    gesendet = []
    echt = NotificationService.__dict__["_dispatch_alert_message"]
    monkeypatch.setattr(NotificationService, "_dispatch_alert_message",
                        lambda self, alert_msg, **k: gesendet.append(alert_msg) or echt(self, alert_msg, **k))
    nc = NowcastResult(onset_minutes=15, intensity_label="Regen", source="radar", is_convective=False)
    for v in reihenfolge:
        dienst = _dienst(monkeypatch, v)
        dienst.send_radar_alert(_trip_alarm(v), request=RadarAlertRequest(
            onset_minutes=15, onset_time="14:15", km_from=0.0, km_to=4.0, is_convective=False,
            intensity_label="Regen", source_label="Radar", tz=TZ), source="Radar",
            cooldown_display="2 h", effective_channels={"email"}, mail_sink=lambda subject, body: None)
        dienst.send_multi_location_radar_alert([("Ort0", _ort(), nc)], {"email"},
                                               mail_sink=lambda subject, body: None, preset=_preset(v))
    assert _vorlagen(gesendet) == [v for v in reihenfolge for _ in (1, 2)]


@pytest.mark.parametrize("reihenfolge", REIHENFOLGEN, ids=IDS)
def test_alarm_vorschauen_bauen_die_nachricht_mit_der_ampel_des_abos(monkeypatch, reihenfolge):
    """``render_alert_preview`` (Onset-Zweig), ``_deviation_preview_message``
    (Rückgabewert, ohne Nutzerreihen) und ``compare_alert_preview_service``
    ``_onset``/``_deviation`` (frischer Nutzer ohne Anker: kein Abruf)."""
    from types import SimpleNamespace

    from output.renderers.alert import project
    from services import compare_alert_preview_service as cap
    from services import validator_render_service as vrs
    gebaut = _mitschreiben(monkeypatch, vrs, "AlertMessage")
    onset_vgl = _mitschreiben(monkeypatch, project, "to_multi_location_onset_alert_message")
    abw_vgl = _mitschreiben(monkeypatch, project, "to_multi_point_alert_message")
    onset = SimpleNamespace(onset_minutes=15, onset_time="14:15", km_from=0.0, km_to=4.0,
                            is_convective=False, intensity_label="Regen", source_label="Radar",
                            cooldown_display="2 h")
    rueckgabe, orte = [], {"o0": _ort()}
    for v in reihenfolge:
        vrs.render_alert_preview(_trip_alarm(v), SimpleNamespace(onset=onset, official=None, nowcast_frames=None))
        rueckgabe.append(vrs._deviation_preview_message(
            _trip_alarm(v), [_aenderung()], [SimpleNamespace(segment_id="1", start="08:00", end="14:00")],
            user_id=None, tz=TZ, stand_at="08:00", now_utc=datetime(2026, 5, 1, 6, tzinfo=UTC)))
        preset = {**_preset(v), "location_ids": ["o0"]}
        cap._onset(preset, [{"location_id": "o0", "onset_minutes": 15, "intensity_label": "Regen",
                             "source": "radar"}], orte, "rich", lang="de")
        cap._deviation(preset, [{"location_id": "o0", "metric": "gust_max_kmh", "old_value": 10.0,
                                 "new_value": 52.0, "delta": 42.0, "threshold": 20.0, "severity": "major",
                                 "direction": "increase"}], orte, "rich", preset_id=preset["id"],
                       user_id=_dienst(monkeypatch, v)._user_id, lang="de")
    ist = {"vorschau": gebaut, "rueckgabe": rueckgabe, "vgl_onset": onset_vgl, "vgl_abw": abw_vgl}
    # vgl_abw: eine Nachricht für Mail/SMS plus eine je Ort für Telegram
    soll = {k: [v for v in reihenfolge for _ in range(2 if k == "vgl_abw" else 1)] for k in ist}
    assert {k: _vorlagen(n) for k, n in ist.items()} == soll


@pytest.mark.parametrize("reihenfolge", REIHENFOLGEN, ids=IDS)
def test_vergleichs_klartext_baut_den_ausblick_mit_der_ampel_des_presets(monkeypatch, reihenfolge):
    """``render_comparison_text``: der Klartext zeigt keine Farben, für +9 °C
    gibt es dort kein Zeichen. Geprüft wird die von der Ampel abhängige
    Ausgabe, die der Klartext selbst baut: die Ausblick-Zeilen (``cell_bg``
    Skitouren orange, Allgemein leer)."""
    from app.models import ForecastDataPoint
    from output.renderers import comparison
    zeilen = _mitschreiben(monkeypatch, comparison, "_build_location_outlook_rows")
    erg = _ergebnis()
    for loc in erg.locations:
        loc.outlook_hourly_data = [ForecastDataPoint(ts=datetime(2026, 7, 12, h, tzinfo=UTC), t2m_c=9.0)
                                   for h in (10, 11, 12)]
    for v in reihenfolge:
        comparison.render_comparison_text(erg, preset=_preset(v), outlook_enabled=True,
                                          outlook_metrics=[{"metric_id": "temperature", "aggregation": "max"}])
    orange = f"background:{_tone_bg('orange')};"
    assert [r[0]["cell_bg"][0] for r in zeilen[::3]] == [orange if v == "skitouren" else "" for v in reihenfolge]
