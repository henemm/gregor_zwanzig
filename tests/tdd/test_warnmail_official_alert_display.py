"""Warnmail — sechs gebündelte Darstellungsfehler amtlicher Warn-/Alarm-Mails.

SPEC: docs/specs/modules/warnmail_official_alert_display.md (AC-1..AC-6)
KONTEXT: docs/context/warnmail.md (Root Causes, file:line)

RED-Phase — jeder Test reproduziert GENAU einen der sechs Befunde aus
Nutzersicht am ECHTEN, unveränderten Ist-Code:

- AC-1 (#1326a): `build_official_alert_notices` befüllt `free_chips` heute mit
  ALLEN nicht-betroffenen Segmenten der Gesamtroute (63-Segment-Route-Gitter).
- AC-2 (#1326b): `_display_label`s else-Zweig konkateniert deutschen Typ +
  rohes Quell-Label ("Gewitter — Orange Thunderstorm Warning").
- AC-3 (#1248): `render_official_alert_subject` prüft `_uniform_scope` nur für
  `scope_kind=="locations"`, der Route-Pfad nimmt bedingungslos das Segment
  der führenden Warnung.
- AC-4 (#1251): `_official_source_label_for` liefert nur die Quelle der
  führenden (höchststufigen) Warnung, die zweite Quelle eines Bündels aus
  zwei Behörden geht verloren.
- AC-5 (#1338 Footer): `build_origin_footer` baut Zeile 2 immer als
  `renderer_name · Commit-Hash` -- kein fachlicher Wert, kein Bezug zur
  echten Datenquelle.
- AC-6 (#1338 Format): `_dispatch_alert_message` haengt amtliche Notices als
  HTML-escaped Plaintext in ein rohes `<p>`, statt den geteilten
  `render_warn_block(variant="embedded")` zu nutzen.

Test-Politik: Kern-Schicht, deterministisch, KEINE Mocks (kein `Mock()`/
`MagicMock`/`unittest.mock.patch`). Echte `OfficialAlert`/`OfficialAlertNotice`/
`AlertMessage`/`AlertEvent`/`OnsetEvent`-Objekte, echte Renderer-Aufrufe.
AC-6 nutzt `pytest`s `monkeypatch`-Fixture, um das produktiv genutzte
Transport-Objekt `EmailOutput` durch ein selbstgeschriebenes Test-Double (kein
Mocking-Framework) zu ersetzen -- siehe Docstring dort für die Begründung
(der einzige DI-Seam von `_dispatch_alert_message`, `mail_sink`, liefert nur
den Plain-Text-Body, nie den HTML-Body).
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from services.official_alerts.models import OfficialAlert

UTC = timezone.utc
FR_ALLDAY_FROM = datetime(2026, 7, 10, 0, 0, tzinfo=UTC)
FR_ALLDAY_TO = datetime(2026, 7, 10, 23, 59, tzinfo=UTC)
SA_FROM = datetime(2026, 7, 11, 15, 0, tzinfo=UTC)
SA_TO = datetime(2026, 7, 11, 21, 0, tzinfo=UTC)


def _alert(level, hazard, label, vf=None, vt=None, *, region=None,
           source="geosphere", dedup_id=None) -> OfficialAlert:
    return OfficialAlert(
        source=source, hazard=hazard, level=level, label=label,
        valid_from=vf, valid_to=vt, region_label=region, dedup_id=dedup_id,
    )


def _trip_with_n_segments(n_segments: int, *, trip_id="tdd-warnmail-trip"):
    """Baut einen Trip mit `n_segments` Segmenten (n_segments + 1 Waypoints),
    analog `test_official_alert_channel_scope.py::_trip_mixed_scope_notices`."""
    from app.trip import Stage, Trip, Waypoint

    waypoints = [
        Waypoint(
            id=f"w{i}", name=f"WP{i}",
            lat=47.0 + i * 0.001, lon=11.0 + i * 0.001, elevation_m=1000.0,
        )
        for i in range(n_segments + 1)
    ]
    stage = Stage(id="s1", name="Tag 1", date=date(2026, 7, 10), waypoints=waypoints)
    return Trip(id=trip_id, name="KHW 403", stages=[stage])


# ---------------------------------------------------------------------------
# AC-1 (#1326a) — 63-Segment-Route-Gitter statt "nur betroffene Segmente"
# ---------------------------------------------------------------------------
def test_ac1_builder_sets_no_free_chips_for_partial_route_warning():
    """`build_official_alert_notices` MUSS `free_chips=[]` liefern (Vorbild:
    `build_compare_official_alert_notices` setzt das bereits fest) -- eine
    Warnung, die 1 von 63 Segmenten betrifft, darf NICHT alle 62 übrigen
    Segmente als durchgestrichene Chips mitschleppen."""
    from output.renderers.alert.official_alerts import build_official_alert_notices

    trip = _trip_with_n_segments(63)
    tagged = [(_alert(3, "thunderstorm", "Gewitter", SA_FROM, SA_TO, region="Kärnten"), ["5"])]
    notices = build_official_alert_notices(trip, tagged)

    assert len(notices) == 1
    notice = notices[0]
    assert notice.affected_chips == ["Segment 5"]
    assert notice.free_chips == [], (
        "AC-1/#1326a: der Builder befüllt free_chips mit den 62 übrigen "
        f"Segmenten statt einer leeren Liste: {notice.free_chips!r}"
    )


def test_ac1_rendered_html_shows_no_strikethrough_grid_standalone_and_embedded():
    """Gerendertes HTML (Standalone UND embedded) darf keine 62 unbetroffenen
    Segment-Chips und kein `line-through` enthalten."""
    from output.renderers.alert.official_alerts import (
        build_official_alert_notices, render_official_alert_html, render_warn_block,
    )

    trip = _trip_with_n_segments(63)
    tagged = [(_alert(3, "thunderstorm", "Gewitter", SA_FROM, SA_TO, region="Kärnten"), ["5"])]
    notices = build_official_alert_notices(trip, tagged)

    standalone_html = render_official_alert_html(
        notices, source_label="GeoSphere Austria", stand_at="09:30", tz=UTC,
    )
    embedded_html = render_warn_block(
        notices, variant="embedded", source_label="GeoSphere Austria", tz=UTC,
    )

    for label, html in (("standalone", standalone_html), ("embedded", embedded_html)):
        assert "line-through" not in html, (
            f"AC-1/#1326a: {label}-HTML zeigt noch durchgestrichene "
            "Vollrouten-Chips (line-through)"
        )
        # Nur der EINE betroffene Segment-Chip ("Segment 5") darf erscheinen --
        # nicht die 62 unbetroffenen ("Segment 1", "Segment 2", ...).
        segment_mentions = html.count("Segment ")
        assert segment_mentions <= 1, (
            f"AC-1/#1326a: {label}-HTML nennt {segment_mentions}x 'Segment ' "
            "-- erwartet höchstens 1 (nur der betroffene Chip 'Segment 5'), "
            "nicht das 63-Segment-Route-Gitter"
        )


# ---------------------------------------------------------------------------
# AC-2 (#1326b) — doppelte Gefahren-Benennung ("Gewitter — Orange ...")
# ---------------------------------------------------------------------------
def test_ac2_display_label_shows_only_mapped_german_type():
    """`_display_label` darf für eine gemappte Gefahr mit abweichendem
    Roh-Label NUR den deutschen Typ zeigen, nicht die Verkettung."""
    from output.renderers.alert.official_alerts import _display_label

    alert = OfficialAlert(
        source="meteoalarm", hazard="thunderstorm",
        level=3, label="Orange Thunderstorm Warning",
        valid_from=SA_FROM, valid_to=SA_TO, region_label="Some Region",
    )
    display = _display_label(alert)
    assert display == "Gewitter", (
        f"AC-2/#1326b: _display_label konkateniert Typ+Roh-Label statt nur "
        f"'Gewitter' zu zeigen: {display!r}"
    )


def test_ac2_subject_html_telegram_show_no_raw_label_concatenation():
    from output.renderers.alert.official_alerts import (
        OfficialAlertNotice, render_official_alert_html,
        render_official_alert_subject, render_official_alert_telegram,
    )

    alert = OfficialAlert(
        source="meteoalarm", hazard="thunderstorm",
        level=3, label="Orange Thunderstorm Warning",
        valid_from=SA_FROM, valid_to=SA_TO, region_label="Some Region",
    )
    notice = OfficialAlertNotice(
        alert=alert, scope_label="gesamte Route", sms_scope="ges.Route",
        affected_chips=["gesamte Route"], free_chips=[],
    )

    subject = render_official_alert_subject([notice], prefix="KHW 403")
    assert "Orange Thunderstorm Warning" not in subject, (
        f"AC-2: Betreff enthält noch das rohe Quell-Label: {subject!r}"
    )
    assert "Gewitter" in subject

    html = render_official_alert_html(
        [notice], source_label="GeoSphere Austria", stand_at="09:30", tz=UTC,
    )
    assert "Orange Thunderstorm Warning" not in html, (
        "AC-2: HTML enthält noch das rohe Quell-Label"
    )
    assert "Gewitter" in html

    telegram = render_official_alert_telegram(
        [notice], prefix="KHW 403", source_label="GeoSphere Austria",
    )
    assert "Orange Thunderstorm Warning" not in telegram, (
        "AC-2: Telegram-Text enthält noch das rohe Quell-Label"
    )
    assert "Gewitter" in telegram
    # Adversary F002 (warnmail Runde 1): der eingebettete Deviation-Alert-Pfad
    # (`render_official_alert_notice_plain`, aufgerufen aus
    # `_dispatch_alert_message`) nutzte bislang `alert.label` DIREKT und
    # umging `_display_label` -- inzwischen behoben (s.
    # test_f002_dispatch_alert_message_embedded_plain_telegram_use_display_label
    # unten), AC-2 nennt Plain/Telegram explizit.


class _CapturingTelegramOutput:
    """Test-Double (KEIN Mock()/MagicMock/unittest.mock.patch), analog
    `_CapturingEmailOutput` (AC-6): sammelt den Telegram-Body ohne echten
    Bot-API-Call. `_dispatch_alert_message` ist der einzige Aufrufer, der
    hier relevant ist -- Signatur spiegelt `TelegramOutput.send`."""

    def __init__(self, settings):
        self.settings = settings

    def send(self, subject, body, parse_mode=None, suppress_subject_line=False,
              reply_markup=None):
        _TELEGRAM_CAPTURED.append({"subject": subject, "body": body})
        return 1


_TELEGRAM_CAPTURED: list[dict] = []


def test_f002_dispatch_alert_message_embedded_plain_telegram_use_display_label(monkeypatch):
    """F002 (Adversary Runde 1, AC-2): der eingebettete Deviation-Alert im
    Plain- UND Telegram-Body zeigte bislang `alert.label` DIREKT
    (`render_official_alert_notice_plain`, official_alerts.py:513) statt
    über `_display_label` zu gehen -- "ORANGE — Orange Thunderstorm Warning"
    statt "Gewitter". `_dispatch_alert_message` haengt denselben `extra_text`
    an Plain UND Telegram-Body an (notification_service.py:975-980), daher
    genuegt EIN Fix an der gemeinsamen Quelle fuer beide Kanaele."""
    import services.notification_service as ns
    from app.config import Settings
    from output.renderers.alert.model import AlertEvent, AlertMessage

    _CAPTURED.clear()
    _TELEGRAM_CAPTURED.clear()
    monkeypatch.setattr(ns, "EmailOutput", _CapturingEmailOutput)
    monkeypatch.setattr(ns, "TelegramOutput", _CapturingTelegramOutput)

    settings = Settings(
        smtp_host="smtp.test.invalid", smtp_user="t@test.invalid",
        smtp_pass="x", mail_to="to@test.invalid",
        telegram_bot_token="test-token", telegram_chat_id="12345",
    )
    svc = ns.NotificationService(settings, "tdd-warnmail-f002")

    ev = AlertEvent(
        metric_id="wind", value_from=20.0, value_to=48.0, threshold=15.0,
        cmp="über", occurred_at="14:00", km_from=5.0, km_to=12.0,
    )
    alert_msg = AlertMessage(trip_short="KHW 403", stand_at="09:30", events=(ev,))
    official_alert = _alert(
        3, "thunderstorm", "Orange Thunderstorm Warning", SA_FROM, SA_TO,
        region="Hermagor", source="meteoalarm",
    )
    official_notices = [(official_alert, [])]

    captured_plain: dict = {}

    def _mail_sink(*, subject, body):
        captured_plain["body"] = body

    result = svc._dispatch_alert_message(
        alert_msg=alert_msg, effective_channels={"email", "telegram"},
        official_notices=official_notices, alert_tz=UTC,
        mail_sink=_mail_sink,
    )

    assert result.sent
    assert "Orange Thunderstorm Warning" not in captured_plain["body"], (
        f"F002/AC-2: Plain-Body enthaelt noch das rohe Quell-Label: "
        f"{captured_plain['body']!r}"
    )
    assert "Gewitter" in captured_plain["body"], (
        "F002/AC-2: Plain-Body zeigt nicht das gemappte deutsche Typ-Wort "
        "'Gewitter'"
    )

    assert len(_TELEGRAM_CAPTURED) == 1, "TelegramOutput.send() wurde nicht (oder mehrfach) aufgerufen"
    telegram_body = _TELEGRAM_CAPTURED[0]["body"]
    assert "Orange Thunderstorm Warning" not in telegram_body, (
        f"F002/AC-2: Telegram-Body enthaelt noch das rohe Quell-Label: "
        f"{telegram_body!r}"
    )
    assert "Gewitter" in telegram_body, (
        "F002/AC-2: Telegram-Body zeigt nicht das gemappte deutsche Typ-Wort "
        "'Gewitter'"
    )


def test_f002_access_ban_label_stays_intact_in_embedded_plain_notice():
    """Kontrollfall (F002): ein access_ban-Label mit Detail-Separator ("—")
    MUSS unveraendert (voller Massiv-Name) erscheinen -- `_display_label`
    ersetzt nur voellig eigenstaendige Roh-Labels (Fall (d)), nicht Labels
    mit "—"-Detail-Trenner (Fall (a)/(b))."""
    from output.renderers.alert.official_alerts import render_official_alert_notice_plain

    alert = _alert(
        3, "access_ban", "Zugang gesperrt — Rotwand-Massiv", SA_FROM, SA_TO,
        region="Rotwand-Massiv", source="lwd_tirol",
    )
    lines = render_official_alert_notice_plain([(alert, [])], tz=UTC)
    joined = "\n".join(lines)
    assert "Zugang gesperrt — Rotwand-Massiv" in joined, (
        f"F002: access_ban-Kontrollfall verlor den Massiv-Namen: {joined!r}"
    )


# ---------------------------------------------------------------------------
# AC-3 (#1248) — Betreff nennt bei gemischtem Umfang nur das Segment der
# führenden Warnung, unabhängig von scope_kind (route ODER locations).
# ---------------------------------------------------------------------------
def test_ac3_route_scope_subject_names_no_single_leading_segment():
    """Route-Pfad (scope_kind='route', Trip-Default): zwei Warnungen mit
    unterschiedlichen betroffenen Segmenten -- der Betreff darf NICHT das
    Segment der führenden (höchststufigen) Warnung als Gesamt-Umfang
    behaupten (`_uniform_scope`-Prüfung muss auch für Route greifen)."""
    from output.renderers.alert.official_alerts import (
        build_official_alert_notices, render_official_alert_subject,
    )

    trip = _trip_with_n_segments(4)
    tagged = [
        (_alert(3, "thunderstorm", "Gewitter", SA_FROM, SA_TO, region="Kärnten"), ["1"]),
        (_alert(2, "extreme_heat", "Hitze", FR_ALLDAY_FROM, FR_ALLDAY_TO, region="Kärnten"), ["3"]),
    ]
    notices = build_official_alert_notices(trip, tagged)

    subject = render_official_alert_subject(notices, prefix="KHW 403")
    assert "mehrere Segmente" in subject, (
        f"AC-3/#1248: Betreff behauptet ein einzelnes führendes Segment als "
        f"Gesamt-Umfang statt einer ehrlichen Sammelangabe: {subject!r}"
    )
    assert "Segment 1" not in subject and "Segment 3" not in subject, (
        f"AC-3: Betreff nennt fälschlich nur das Segment der führenden Warnung: {subject!r}"
    )


# ---------------------------------------------------------------------------
# AC-4 (#1251) — Quelle global statt pro Warnung bei gebündelter Warn-Karte
# aus zwei verschiedenen Behörden.
# ---------------------------------------------------------------------------
def test_ac4_official_source_label_for_returns_only_leading_source():
    """`_official_source_label_for` (notification_service.py) wählt heute NUR
    die Quelle der höchststufigen Warnung -- bei einem Bündel aus GeoSphere
    Austria (Gewitter, ORANGE) + Météo-France (Hitze, GELB) geht die zweite
    Quelle verloren."""
    from output.renderers.alert.official_alerts import OfficialAlertNotice
    from services.notification_service import _official_source_label_for

    alert_at = OfficialAlert(
        source="geosphere_warn", hazard="thunderstorm", level=3, label="Gewitter",
        valid_from=SA_FROM, valid_to=SA_TO, region_label="Kärnten",
    )
    alert_fr = OfficialAlert(
        source="meteofrance_vigilance", hazard="extreme_heat", level=2, label="Hitze",
        valid_from=FR_ALLDAY_FROM, valid_to=FR_ALLDAY_TO, region_label="Haute-Corse",
    )
    notice_at = OfficialAlertNotice(
        alert=alert_at, scope_label="gesamte Route", sms_scope="ges.Route",
        affected_chips=["gesamte Route"], free_chips=[],
    )
    notice_fr = OfficialAlertNotice(
        alert=alert_fr, scope_label="gesamte Route", sms_scope="ges.Route",
        affected_chips=["gesamte Route"], free_chips=[],
    )

    source_label = _official_source_label_for([notice_at, notice_fr])
    assert "GeoSphere Austria" in source_label and "Météo-France" in source_label, (
        f"AC-4/#1251: nur EINE Quelle statt beider Behörden im Bündel: {source_label!r}"
    )


def test_ac4_rendered_html_names_both_bundled_sources():
    from output.renderers.alert.official_alerts import (
        OfficialAlertNotice, render_official_alert_html,
    )
    from services.notification_service import _official_source_label_for

    alert_at = OfficialAlert(
        source="geosphere_warn", hazard="thunderstorm", level=3, label="Gewitter",
        valid_from=SA_FROM, valid_to=SA_TO, region_label="Kärnten",
    )
    alert_fr = OfficialAlert(
        source="meteofrance_vigilance", hazard="extreme_heat", level=2, label="Hitze",
        valid_from=FR_ALLDAY_FROM, valid_to=FR_ALLDAY_TO, region_label="Haute-Corse",
    )
    notices = [
        OfficialAlertNotice(
            alert=alert_at, scope_label="gesamte Route", sms_scope="ges.Route",
            affected_chips=["gesamte Route"], free_chips=[],
        ),
        OfficialAlertNotice(
            alert=alert_fr, scope_label="gesamte Route", sms_scope="ges.Route",
            affected_chips=["gesamte Route"], free_chips=[],
        ),
    ]
    source_label = _official_source_label_for(notices)
    html = render_official_alert_html(
        notices, source_label=source_label, stand_at="09:30", tz=UTC,
    )
    assert "GeoSphere Austria" in html and "Météo-France" in html, (
        "AC-4/#1251: die Quelle-Box nennt nicht beide beteiligten Behörden"
    )


# ---------------------------------------------------------------------------
# AC-5 (#1338 Footer) — Herkunfts-Fußzeile Zeile 2 zeigt Renderer-Pfad +
# Commit statt der echten Datenquelle je Mail-Typ.
# ---------------------------------------------------------------------------
def _build_seg_data(provider="demo"):
    from app.models import (
        ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries,
        Provider, SegmentWeatherData, SegmentWeatherSummary, ThunderLevel,
        TripSegment,
    )
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.13, lon=9.13, elevation_m=900.0),
        end_point=GPXPoint(lat=42.10, lon=9.18, elevation_m=1450.0),
        start_time=datetime(2026, 7, 11, 8, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 11, 12, 0, tzinfo=timezone.utc),
        duration_hours=4.0, distance_km=14.5, ascent_m=820.0, descent_m=440.0,
    )
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="demo", grid_res_km=1.3,
        run=datetime(2026, 7, 11, 0, 0, tzinfo=timezone.utc),
    )
    data = [
        ForecastDataPoint(
            ts=datetime(2026, 7, 11, h, 0, tzinfo=timezone.utc),
            t2m_c=15.0 + h * 0.3, wind10m_kmh=15.0,
            precip_1h_mm=0.2, cloud_total_pct=50,
            thunder_level=ThunderLevel.NONE,
        )
        for h in range(8, 14)
    ]
    ts = NormalizedTimeseries(meta=meta, data=data)
    agg = SegmentWeatherSummary(
        temp_min_c=14.0, temp_max_c=22.0, temp_avg_c=18.0,
        wind_max_kmh=22.0, gust_max_kmh=35.0,
        precip_sum_mm=0.8, cloud_avg_pct=50, humidity_avg_pct=55,
        thunder_level_max=ThunderLevel.NONE,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=ts, aggregated=agg,
        fetched_at=datetime.now(timezone.utc), provider=provider,
    )


def _render_trip_html():
    from app.metric_catalog import build_default_display_config
    from output.renderers.email.html import render_html

    seg = _build_seg_data()
    return render_html(
        segments=[seg], seg_tables=[[]],
        trip_name="Warnmail-Testtrip", report_type="morning",
        dc=build_default_display_config(), night_rows=[],
        thunder_forecast=None, changes=None,
        stage_name="Etappe 2", stage_stats={"distance_km": 14.5, "ascent_m": 820},
        multi_day_trend=None, compact_summary="Guter Tag.",
        tz=ZoneInfo("Europe/Berlin"), friendly_keys=set(),
    )


def _render_trip_plain():
    from app.metric_catalog import build_default_display_config
    from output.renderers.email.plain import render_plain

    seg = _build_seg_data()
    return render_plain(
        segments=[seg], seg_tables=[[]],
        trip_name="Warnmail-Testtrip", report_type="morning",
        dc=build_default_display_config(), night_rows=[],
        thunder_forecast=None, changes=None,
        stage_name="Etappe 2", stage_stats={"distance_km": 14.5, "ascent_m": 820},
        multi_day_trend=None, compact_summary="Guter Tag.",
        tz=ZoneInfo("Europe/Berlin"), friendly_keys=set(),
    )


def test_ac5_trip_briefing_footer_shows_provider_not_renderer_path():
    """trip-briefing (full + plain): Zeile 2 MUSS `segments[0].provider`
    ("demo") zeigen statt `email/html.py`/`email/plain.py`. Die Zählprobe
    (count>=2) unterscheidet die neue Footer-Quelle von der bereits
    bestehenden "Data: demo (...)"-Zeile, die unabhängig vom Footer existiert."""
    html = _render_trip_html()
    plain = _render_trip_plain()

    assert "email/html.py" not in html, (
        "AC-5/Befund 4a: HTML-Footer zeigt noch den internen Renderer-Pfad"
    )
    assert "email/plain.py" not in plain, (
        "AC-5/Befund 4a: Plain-Footer zeigt noch den internen Renderer-Pfad"
    )
    assert html.count("demo") >= 2, (
        "AC-5: 'demo' (segments[0].provider) muss ZUSÄTZLICH in der "
        "Footer-Zeile 2 erscheinen (nicht nur in der bestehenden Data-Zeile)"
    )
    assert plain.count("demo") >= 2, (
        "AC-5: 'demo' muss ZUSÄTZLICH im Plain-Footer erscheinen"
    )


def test_ac5_deviation_alert_footer_shows_open_meteo_fallback_not_path():
    """deviation-alert (Trip, msg.source is None): Zeile 2 MUSS den festen
    Fallback 'Open-Meteo' (ADR-0029) zeigen -- kein per-Event-Provider
    verfügbar (Known Limitation der Spec), aber NIEMALS der interne
    Renderer-Pfad `alert/render.py` oder 'unknown'."""
    from output.renderers.alert.model import AlertEvent, AlertMessage
    from output.renderers.alert.render import render_email as render_alert_email

    ev = AlertEvent(
        metric_id="wind", value_from=20.0, value_to=48.0, threshold=15.0,
        cmp="über", occurred_at="14:00", km_from=5.0, km_to=12.0,
    )
    msg = AlertMessage(trip_short="KHW 403", stand_at="09:30", events=(ev,))
    html, plain = render_alert_email(msg)

    assert "alert/render.py" not in html, (
        "AC-5/Befund 4a: HTML-Footer zeigt noch den internen Renderer-Pfad"
    )
    assert "alert/render.py" not in plain
    assert "unknown" not in html and "unknown" not in plain, (
        "AC-5: Footer darf NIEMALS 'unknown' zeigen"
    )
    assert "Open-Meteo" in html, (
        "AC-5: deviation-alert-Footer fehlt der feste Quell-Fallback 'Open-Meteo'"
    )
    assert "Open-Meteo" in plain


def test_ac5_radar_alert_footer_shows_onset_source_label():
    """radar-alert (Onset): Zeile 2 MUSS `OnsetEvent.source_label` zeigen."""
    from output.renderers.alert.model import AlertMessage, OnsetEvent
    from output.renderers.alert.render import render_email as render_alert_email

    onset = OnsetEvent(
        onset_minutes=45, onset_time="14:30", km_from=5.0, km_to=12.0,
        is_convective=False, intensity_label="mäßig", source_label="Radar (DWD)",
    )
    msg = AlertMessage(
        trip_short="KHW 403", stand_at="09:30", events=(onset,),
        source="radar", cooldown_display="30 Min",
    )
    html, plain = render_alert_email(msg)

    assert "alert/render.py" not in html
    assert "Radar (DWD)" in html, (
        "AC-5: radar-alert-Footer zeigt nicht das echte OnsetEvent.source_label"
    )


# ---------------------------------------------------------------------------
# F001 (Adversary Runde 1, AC-5) — `segments[0].provider` kann legitim der
# WEATHER-04-Fehler-Platzhalter "unknown" sein (trip_report_scheduler.py:1204)
# -- die Fußzeile darf dann NIE "unknown" zeigen, sondern muss auf den festen
# Fallback "Open-Meteo" (ADR-0029) ausweichen.
# ---------------------------------------------------------------------------
def _build_error_seg_data():
    """WEATHER-04-Fehler-Platzhalter (trip_report_scheduler.py:1180-1207):
    `provider="unknown"`, `timeseries=None`, `has_error=True`."""
    from app.models import (
        GPXPoint, SegmentWeatherData, SegmentWeatherSummary, TripSegment,
    )
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.13, lon=9.13, elevation_m=900.0),
        end_point=GPXPoint(lat=42.10, lon=9.18, elevation_m=1450.0),
        start_time=datetime(2026, 7, 11, 8, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 11, 12, 0, tzinfo=timezone.utc),
        duration_hours=4.0, distance_km=14.5, ascent_m=820.0, descent_m=440.0,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=None, aggregated=SegmentWeatherSummary(),
        fetched_at=datetime.now(timezone.utc), provider="unknown",
        has_error=True, error_message="provider fetch failed",
    )


def test_f001_trip_briefing_html_footer_unknown_provider_falls_back_open_meteo():
    """F001/AC-5: HTML-Fußzeile-Zeile-2 zeigt bei `provider="unknown"`
    "Open-Meteo" statt des rohen Fehler-Platzhalters."""
    from app.metric_catalog import build_default_display_config
    from output.renderers.email.html import render_html

    seg = _build_error_seg_data()
    html = render_html(
        segments=[seg], seg_tables=[[]],
        trip_name="Warnmail-Testtrip", report_type="morning",
        dc=build_default_display_config(), night_rows=[],
        thunder_forecast=None, changes=None,
        stage_name="Etappe 2", stage_stats={"distance_km": 14.5, "ascent_m": 820},
        multi_day_trend=None, compact_summary="Guter Tag.",
        tz=ZoneInfo("Europe/Berlin"), friendly_keys=set(),
    )
    # Scope-Hinweis: die separate Brand-Zeile ("&middot; unknown &middot;
    # n/a") zeigt weiterhin den rohen `provider_str` -- das ist eine
    # bestehende, vom AC-5-Origin-Footer UNABHÄNGIGE Anzeige (html.py:414/431)
    # und nicht Teil von F001. F001 betrifft ausschließlich die
    # `build_origin_footer`-Zeile 2 (`render_origin_footer_html`, erkennbar
    # an der Farbe `#b5b1a6`).
    assert 'color:#b5b1a6;">unknown</div>' not in html, (
        "F001/AC-5: die AC-5-Origin-Footer-Zeile-2 zeigt noch 'unknown' "
        "statt des Open-Meteo-Fallbacks"
    )
    assert 'color:#b5b1a6;">Open-Meteo</div>' in html, (
        "F001/AC-5: die AC-5-Origin-Footer-Zeile-2 fehlt der "
        "Open-Meteo-Fallback bei provider='unknown'"
    )


def test_f001_trip_briefing_plain_footer_unknown_provider_falls_back_open_meteo():
    """F001/AC-5: Plain-Fußzeile-Zeile-2 zeigt bei `provider="unknown"`
    "Open-Meteo" statt des rohen Fehler-Platzhalters."""
    from app.metric_catalog import build_default_display_config
    from output.renderers.email.plain import render_plain

    seg = _build_error_seg_data()
    plain = render_plain(
        segments=[seg], seg_tables=[[]],
        trip_name="Warnmail-Testtrip", report_type="morning",
        dc=build_default_display_config(), night_rows=[],
        thunder_forecast=None, changes=None,
        stage_name="Etappe 2", stage_stats={"distance_km": 14.5, "ascent_m": 820},
        multi_day_trend=None, compact_summary="Guter Tag.",
        tz=ZoneInfo("Europe/Berlin"), friendly_keys=set(),
    )
    # Scope-Hinweis: die bestehende "Data: unknown (n/a)"-Zeile (plain.py:299)
    # zeigt weiterhin den rohen `provider`-Wert -- unabhängig vom AC-5-Origin-
    # Footer und nicht Teil von F001 (letzte Zeile des Bodys, s. build_origin_
    # footer-Aufruf plain.py:309-311).
    footer_line = plain.strip().splitlines()[-1]
    assert footer_line == "Etappen-Briefing · Vollversion · Open-Meteo", (
        f"F001/AC-5: Plain-Origin-Footer zeigt nicht den Open-Meteo-Fallback: "
        f"{footer_line!r}"
    )


def test_f001_trip_briefing_compact_footer_unknown_provider_falls_back_open_meteo():
    """F001/AC-5: Compact-Fußzeile-Zeile-2 zeigt bei `provider="unknown"`
    "Open-Meteo" statt des rohen Fehler-Platzhalters."""
    from app.metric_catalog import build_default_display_config
    from output.renderers.email.compact import render_compact

    seg = _build_error_seg_data()
    compact = render_compact(
        segments=[seg], dc=build_default_display_config(),
        multi_day_trend=None, stability_result=None,
        tz=ZoneInfo("Europe/Berlin"), report_type="morning",
        trip_name="Warnmail-Testtrip", stage_name="Etappe 2",
        stage_stats={"distance_km": 14.5, "ascent_m": 820},
    )
    # Scope-Hinweis: die bestehende "Data: unknown (n/a)"-Zeile (compact.py:218)
    # zeigt weiterhin den rohen `provider`-Wert -- unabhängig vom AC-5-Origin-
    # Footer und nicht Teil von F001 (letzte Zeile des Bodys, s. build_origin_
    # footer-Aufruf compact.py:224-226; "·" wird via `_ascii()` zu "-" gefaltet).
    footer_line = compact.strip().splitlines()[-1]
    assert footer_line == "Etappen-Briefing - Kompakt - Open-Meteo", (
        f"F001/AC-5: Compact-Origin-Footer zeigt nicht den Open-Meteo-Fallback: "
        f"{footer_line!r}"
    )


# ---------------------------------------------------------------------------
# AC-6 (#1338 Format) — eingebetteter Warn-Block bricht aus dem Format aus
# (rohes HTML-escaped <p> statt geteiltem render_warn_block(embedded)).
# ---------------------------------------------------------------------------
class _CapturingEmailOutput:
    """Test-Double (KEIN Mock()/MagicMock/unittest.mock.patch): sammelt den
    tatsächlich von `_dispatch_alert_message` gebauten HTML-Body ohne
    SMTP-Netzwerk. Ersetzt `notification_service.EmailOutput` NUR für diesen
    Test via `monkeypatch.setattr` (echte Klasse, kein Mocking-Framework,
    keine `.assert_called_with()`-Verhaltensverifikation)."""

    def __init__(self, settings):
        self.settings = settings

    def send(self, subject, body, html=True, plain_text_body=None, to=None,
              mail_type=None, mail_format=None, compare_hourly_enabled=None):
        _CAPTURED.append({"subject": subject, "body": body})


_CAPTURED: list[dict] = []


def test_ac6_dispatch_alert_message_embeds_wb_banner_not_raw_p(monkeypatch):
    """AC-6/#1338 Format: `_dispatch_alert_message` (notification_service.py
    :945-960) haengt den amtlichen Zusatzblock heute als HTML-escaped
    Plaintext in ein rohes `<p>` an, statt den geteilten, bereits von
    `send_official_alert` genutzten `render_warn_block(variant="embedded")`
    zu verwenden.

    Abweichung von der Spec-Skizze: `official_notices` ist laut den
    Bestandsaufrufern (`test_issue_1088_official_alert_triggers.py::
    TestAC7SmsWithoutParity`) eine Liste roher `(OfficialAlert, segment_ids)`-
    Tupel, KEINE `OfficialAlertNotice`-DTOs -- `_dispatch_alert_message`
    bekommt kein `trip`-Objekt, um die DTOs selbst zu bauen. Dieser Test nutzt
    daher das echte, bereits produktiv verwendete Tupel-Format.

    Zweite Abweichung: der einzige DI-Seam von `_dispatch_alert_message`
    (`mail_sink`) liefert NUR den Plain-Text-Body (`mail_sink(subject=subject,
    body=plain)`, notification_service.py:977) -- der HTML-Body ist über
    diesen Seam nicht beobachtbar. Dieser Test ersetzt daher das produktiv
    genutzte Transport-Objekt `EmailOutput` (echte Klasse, kein
    Mocking-Framework) via `monkeypatch.setattr`, um den tatsächlich gebauten
    HTML-Body zu inspizieren."""
    import services.notification_service as ns
    from app.config import Settings
    from output.renderers.alert.model import AlertEvent, AlertMessage

    _CAPTURED.clear()
    monkeypatch.setattr(ns, "EmailOutput", _CapturingEmailOutput)

    settings = Settings(
        smtp_host="smtp.test.invalid", smtp_user="t@test.invalid",
        smtp_pass="x", mail_to="to@test.invalid",
    )
    svc = ns.NotificationService(settings, "tdd-warnmail-ac6")

    ev = AlertEvent(
        metric_id="wind", value_from=20.0, value_to=48.0, threshold=15.0,
        cmp="über", occurred_at="14:00", km_from=5.0, km_to=12.0,
    )
    alert_msg = AlertMessage(trip_short="KHW 403", stand_at="09:30", events=(ev,))
    official_alert = OfficialAlert(
        source="geosphere_warn", hazard="thunderstorm", level=3, label="Gewitter",
        region_label="Hermagor", valid_from=SA_FROM, valid_to=SA_TO,
    )
    official_notices = [(official_alert, [])]

    result = svc._dispatch_alert_message(
        alert_msg=alert_msg, effective_channels={"email"},
        official_notices=official_notices, alert_tz=UTC,
    )

    assert result.sent, "E-Mail-Kanal wurde nicht als versendet gezählt"
    assert len(_CAPTURED) == 1, "EmailOutput.send() wurde nicht (oder mehrfach) aufgerufen"
    html = _CAPTURED[0]["body"]

    assert "wb-src" in html, (
        "AC-6/#1338: der eingebettete amtliche Warn-Block trägt nicht die "
        ".wb-Bannerform (wb-src fehlt) -- vermutlich noch das rohe "
        "<p>-HTML-Escaping statt render_warn_block(variant='embedded')"
    )
    assert "wb-count" in html, (
        "AC-6/#1338: der eingebettete amtliche Warn-Block trägt nicht die "
        ".wb-Bannerform (wb-count fehlt)"
    )
