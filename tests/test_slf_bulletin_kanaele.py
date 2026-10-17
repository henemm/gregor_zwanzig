"""Der SLF-Lagebericht in den vier Kanaelen und im Ortsvergleich (#1441 Scheibe S3).

SPEC: docs/specs/modules/feat_1441_s3_slf.md -- AC-3/AC-4 (gerenderter Text), AC-10 (Ausfall-
Hinweiszeile im Trip-Briefing), AC-18 bis AC-25.

Kein Mock-Theater: Die Warnungen kommen aus der ECHTEN ``SlfSource`` mit dem Fixture-Transport
(aufgezeichnete Antworten ``tests/fixtures/slf/``) ueber den echten Registry-Abruf
``get_official_alerts_with_status``. Gerendert wird mit den echten Renderern (``render_html``,
``render_plain``, ``render_compare_email``, ``render_official_alert_telegram``,
``SMSTripFormatter``); versendet ueber die echten Versandpfade ``send_official_alert`` und
``send_multi_location_official_alert`` -- ersetzt sind nur die vier Ausgangs-Klassen zum Netz
(``tests/helpers/transport_mitschrift.py``). Das Melde-Gedaechtnis (AC-25) schreibt das Produkt
selbst im echten Alarmlauf.

Stufe 4/5 sind ABGELEITET (die aufgezeichneten Bulletins enthalten hoechstens Stufe 3): nur
``mainValue``/``dangerRatingValue`` geaendert (``derive``), im Testnamen "abgeleitet". Die
Feinstufen neutral/plus fuer denselben Wortlaut sind ebenfalls abgeleitet (``level_modifier``
per ``dataclasses.replace`` an der echten Warnung); ein ECHTER Plus-Fall (CH-5112, Januar)
steht daneben.

Pruefling-Importe (``services.official_alerts.slf`` ueber den Helper, Feld ``level_modifier``)
stehen nur innerhalb der Tests.
"""
from __future__ import annotations

import dataclasses
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from tests.helpers.slf_support import (
    ABEND_FOLGETAG_FRUEH, APRIL, FEHLERARTEN, JANUAR, MORGEN_UPDATE, P_MUENCHEN, SLF_LABEL,
    SLF_MASSGEBLICH, SLF_URL, WINTER_ABEND, WINTER_MORGEN, FakeClock, SlfFixtureTransport,
    alerts_with_status, bulletin_of, derive, interior_point, make_slf_source, ok_doc, only_slf,
    slf_doc,
)

UTC = timezone.utc
T_WINTER = datetime(2026, 3, 1, 8, 0, tzinfo=UTC)
T_ABEND = datetime(2026, 3, 1, 17, 30, tzinfo=UTC)
T_MORGEN_UPDATE = datetime(2026, 3, 2, 8, 0, tzinfo=UTC)
T_JANUAR = datetime(2026, 1, 15, 8, 0, tzinfo=UTC)
T_APRIL = datetime(2026, 4, 10, 8, 0, tzinfo=UTC)
MELDUNG = "2026-03-01T07:00:00+00:00"

MUENSTERTAL = "CH-7231"   # Graubuenden, erheblich/minus, Altschnee ab 2000 m
DAVOS = "CH-5123"         # Graubuenden (dasselbe Bulletin wie CH-7231)
_ZEILE_MINUS = "Lawinenstufe 3- (erheblich) oberhalb 2000 m · Altschnee"
_ZEILE_NEUTRAL = "Lawinenstufe 3 (erheblich) oberhalb 2000 m · Altschnee"
_ZEILE_PLUS = "Lawinenstufe 3+ (erheblich) oberhalb 2000 m · Altschnee"
_SLF_MARKER = (SLF_LABEL, SLF_URL, SLF_MASSGEBLICH)
_FEINSTUFE_SMS = re.compile(r"AV\d[-+]")


# ====================================================================== Hilfen: Quelle
def _slf_abruf(monkeypatch, reply, punkt, now):
    """Echte ``SlfSource`` (Fixture-Transport, eigene Uhr/Cache) als einzige Registry-Quelle;
    Abruf wie im Trip-Briefing. Liefert (transport, alerts, unavailable)."""
    transport = SlfFixtureTransport(reply)
    only_slf(monkeypatch, transport, FakeClock(now))
    alerts, unavailable = alerts_with_status(*punkt, now)
    return transport, alerts, unavailable


def _slf_warnung(monkeypatch, reply, region: str, now: datetime, punkt=None):
    """Genau EINE Lagebericht-Warnung der SLF-Quelle fuer einen inneren Punkt der Region."""
    _t, alerts, unavailable = _slf_abruf(monkeypatch, reply, punkt or interior_point(region), now)
    lawine = [a for a in alerts if a.hazard == "avalanche_bulletin"]
    assert len(lawine) == 1 and unavailable is False, (
        f"Vorbedingung: die SLF-Quelle liefert fuer {region} genau eine Warnung: {alerts!r}")
    return lawine[0]


def _muenstertal_minus(monkeypatch):
    """CH-7231, 2026-03-01 Morgen: Stufe 3, Feinstufe minus, oberhalb 2000 m, Altschnee."""
    a = _slf_warnung(monkeypatch, WINTER_MORGEN, MUENSTERTAL, T_WINTER)
    assert (a.native_level, a.level_modifier, a.elevation_value) == (3, "-", "2000"), a
    return a


def _abgeleitet(stufe: int, region: str = MUENSTERTAL) -> dict:
    """Stufe 4/5 abgeleitet aus dem Morgen-Bulletin: Rating UND tragendes Problem auf ``stufe``
    (sonst traegt kein Problem mehr das Rating und die Hoehe entfiele, Spec Abschnitt 5)."""
    return derive(slf_doc(WINTER_MORGEN), region, main_value=stufe,
                  problem_values={"persistent_weak_layers": stufe})


def _muenstertal_abgeleitet(monkeypatch, stufe: int):
    a = _slf_warnung(monkeypatch, ok_doc(_abgeleitet(stufe)), MUENSTERTAL, T_WINTER)
    assert (a.native_level, a.level, a.elevation_value) == (stufe, 4, "2000"), a
    return a


# ====================================================================== Hilfen: Darstellung
def _segmente(alerts: list, *, lat: float, lon: float, unavailable: bool = False):
    """Echte Segment-Objekte wie ``tests/helpers/avalanche_report_support.render_trip_mail``."""
    from app.models import (
        ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries, Provider,
        SegmentWeatherData, SegmentWeatherSummary, ThunderLevel, TripSegment,
    )

    start = datetime(2026, 3, 1, 6, 0, tzinfo=UTC)

    def _dp(h: int):
        return ForecastDataPoint(
            ts=start.replace(hour=h), t2m_c=-4.0, wind10m_kmh=10.0, gust_kmh=20.0,
            precip_1h_mm=0.0, pop_pct=10, cloud_total_pct=40, thunder_level=ThunderLevel.NONE,
            visibility_m=20000, freezing_level_m=2000,
        )

    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=lat, lon=lon, elevation_m=1500.0, distance_from_start_km=0.0),
        end_point=GPXPoint(lat=lat, lon=lon, elevation_m=2300.0, distance_from_start_km=5.0),
        start_time=start, end_time=start + timedelta(hours=4),
        duration_hours=4.0, distance_km=5.0, ascent_m=800.0, descent_m=0.0,
    )
    meta = ForecastMeta(provider=Provider.OPENMETEO, model="demo", grid_res_km=1.3)
    agg = SegmentWeatherSummary(
        temp_min_c=-8.0, temp_max_c=0.0, temp_avg_c=-4.0, wind_max_kmh=20.0, gust_max_kmh=30.0,
        precip_sum_mm=0.0, cloud_avg_pct=40, humidity_avg_pct=55, thunder_level_max=ThunderLevel.NONE,
    )
    swd = SegmentWeatherData(
        segment=seg, timeseries=NormalizedTimeseries(meta=meta, data=[_dp(6), _dp(7), _dp(8)]),
        aggregated=agg, fetched_at=datetime.now(UTC), provider="demo",
        official_alerts=list(alerts),
    )
    swd.official_alerts_unavailable = unavailable
    return [swd]


def _trip_mail(alerts: list, *, punkt=None, unavailable: bool = False) -> tuple[str, str]:
    """Trip-Briefing-Mail: (HTML-Teil ``render_html``, Text-Teil ``render_plain``) aus denselben
    Segmenten."""
    from app.metric_catalog import build_default_display_config
    from output.renderers.email.html import render_html
    from output.renderers.email.plain import render_plain

    lat, lon = punkt or interior_point(MUENSTERTAL)
    segs = _segmente(alerts, lat=lat, lon=lon, unavailable=unavailable)
    gemeinsam = dict(
        segments=segs, seg_tables=[[{"time": "06", "temp": -4.0, "risk_color": "#2f8a3e"}]],
        trip_name="Graubuenden Test", report_type="morning", dc=build_default_display_config(),
        night_rows=[], thunder_forecast=None, changes=None, stage_name=None, stage_stats=None,
        multi_day_trend=None, compact_summary="Kalt und klar.", tz=ZoneInfo("Europe/Zurich"),
        friendly_keys=set(),
    )
    return render_html(**gemeinsam), render_plain(**gemeinsam)


def _compare_mail(alerts: list) -> tuple[str, str]:
    """Ortsvergleich-Mail (``render_compare_email``): ein Ort mit den Warnungen, ein Ort ohne."""
    from app.models import ForecastDataPoint
    from app.profile import ActivityProfile
    from app.user import ComparisonResult, LocationResult, SavedLocation
    from output.renderers.comparison import render_compare_email

    lat, lon = interior_point(MUENSTERTAL)

    def _loc(loc_id: str, name: str, dy: float, warns: list) -> LocationResult:
        saved = SavedLocation(id=loc_id, name=name, lat=lat + dy, lon=lon, elevation_m=1800)
        dp = ForecastDataPoint(ts=datetime(2026, 3, 1, 9, 0), t2m_c=-3.0)
        return LocationResult(location=saved, score=70, official_alerts=list(warns), hourly_data=[dp])

    result = ComparisonResult(
        locations=[_loc("loc-ch", "Muenstertal", 0.0, alerts), _loc("loc-frei", "Talort", 0.3, [])],
        time_window=(9, 16), target_date=date(2026, 3, 1),
    )
    return render_compare_email(result, profile=ActivityProfile.ALLGEMEIN)


def _notice(alert, *, sms_scope: str = "ges.Route"):
    from output.renderers.alert.official_alerts import OfficialAlertNotice

    return OfficialAlertNotice(alert=alert, scope_label="gesamte Route", sms_scope=sms_scope,
                               affected_chips=["gesamte Route"], free_chips=[])


def _telegram_direkt(alert) -> str:
    """Telegram-Langform direkt am Renderer (nur fuer Stufen-/Hoehentext, AC-3/AC-4)."""
    from output.renderers.alert.official_alerts import (
        official_alert_source_label, render_official_alert_telegram,
    )

    return render_official_alert_telegram([_notice(alert)], prefix="Etappe 1",
                                          source_label=official_alert_source_label(alert.source))


def _briefing_sms(alerts) -> str:
    """Echte Briefing-SMS (``SMSTripFormatter``), Muster ``test_avalanche_report_sms``."""
    from output.renderers.sms_trip import SMSTripFormatter
    from tests.tdd.test_sms_official_alert_tokens import _DISABLE_NEW_14, _segment

    return SMSTripFormatter().format_sms([_segment(alerts)], stage_name="Etappe 1",
                                         tz=ZoneInfo("UTC"), disabled_specs=list(_DISABLE_NEW_14))


def _av_token(text: str, ziffer: int) -> list[str]:
    return re.findall(rf"(?<![A-Za-z0-9])AV{ziffer}(?![0-9A-Za-z:@])", text)


def _warnzeilen_plain(alerts) -> list[str]:
    from output.renderers.alert.official_alerts import render_official_alerts_plain

    return render_official_alerts_plain([("Ort", list(alerts))])


# ====================================================================== Hilfen: Versand
def _nutzer(monkeypatch):
    """Frisches Premium-Profil (alle vier Kanaele), Aufzeichner an den Ausgangs-Klassen."""
    from services.notification_service import NotificationService
    from tests.helpers.transport_mitschrift import aufzeichner_installieren
    from tests.tdd._compare_kette_fixtures import settings_fuer
    from tests.tdd._einstellung_auslieferung_fixtures import TRANSPORT_ENV, frisches_profil

    for k, v in TRANSPORT_ENV.items():
        monkeypatch.setenv(k, v)
    mit = aufzeichner_installieren(monkeypatch)
    uid = frisches_profil(tier="premium")
    return mit, NotificationService(settings_fuer(uid), user_id=uid)


ALLE = {"email", "telegram", "sms", "premium_sms"}
TRIP_NAME = "Muenstertal-Trip"
ORT = "Davos"


def _trip_versand(monkeypatch, alert, *, telegram_style: str = "rich"):
    """Echter Trip-Alarm-Versand ``send_official_alert`` ueber alle vier Kanaele."""
    from app.trip import Stage, Trip, Waypoint

    mit, svc = _nutzer(monkeypatch)
    lat, lon = interior_point(MUENSTERTAL)
    waypoints = [Waypoint(id=f"w{i}", name=f"P{i}", lat=lat, lon=lon, elevation_m=2100.0)
                 for i in range(3)]
    trip = Trip(id=f"slf-{uuid.uuid4().hex[:6]}", name=TRIP_NAME,
                stages=[Stage(id="s1", name="Tag 1", date=date(2026, 3, 1), waypoints=waypoints)])
    svc.send_official_alert(trip=trip, notices=[(alert, ["1"])], effective_channels=set(ALLE),
                            telegram_style=telegram_style)
    return mit


def _vergleich_versand(monkeypatch, alert, *, telegram_style: str = "rich"):
    """Echter Ortsvergleich-Alarm-Versand ``send_multi_location_official_alert``; zwei Orte, die
    Warnung betrifft nur den Schweizer Ort (Ortsname erscheint dann im Umfang)."""
    from app.user import SavedLocation

    mit, svc = _nutzer(monkeypatch)
    lat, lon = interior_point(DAVOS)
    orte = [SavedLocation(id="loc-davos", name=ORT, lat=lat, lon=lon, elevation_m=1560),
            SavedLocation(id="loc-chur", name="Chur", lat=46.85, lon=9.53, elevation_m=590)]
    svc.send_multi_location_official_alert("Graubuenden-Vergleich", orte, [(alert, ["loc-davos"])],
                                           set(ALLE), telegram_style)
    return mit


#: Beide Alarm-Flaechen (Trip/Ortsvergleich) -- geteilte Pruefungen laufen ueber beide Versandpfade.
_FLAECHEN = {"trip": _trip_versand, "vergleich": _vergleich_versand}


def _einzige(mit, kanal: str) -> dict:
    sendungen = mit.sendungen(kanal)
    assert len(sendungen) == 1, f"{kanal}: genau eine Sendung erwartet: {mit!r}"
    return sendungen[0]


# ====================================================================== AC-3 / AC-4 (Text)
def test_ac3_gerenderter_mail_und_telegram_text_nennt_unterhalb_2400_m(monkeypatch):
    """AC-3. GIVEN Bulletin 2026-04-10, Region CH-1246 (erheblich, Nassschnee bis 2400 m)
    WHEN Trip-Briefing-Mail (HTML+Text) und Telegram-Langform gerendert werden
    THEN steht dort "unterhalb 2400 m"."""
    a = _slf_warnung(monkeypatch, APRIL, "CH-1246", T_APRIL)
    html, plain = _trip_mail([a], punkt=interior_point("CH-1246"))

    assert "unterhalb 2400 m" in html
    assert "unterhalb 2400 m" in plain
    assert "unterhalb 2400 m" in _telegram_direkt(a)


def test_ac4_mehrdeutige_grenzen_ergeben_im_gerenderten_text_keine_hoehe(monkeypatch):
    """AC-4. GIVEN Abend-Ausgabe 2026-03-01, Region CH-5112 (maessig; Altschnee ab 2000 m UND
    Nassschnee bis 2200 m, beide maessig) WHEN Warnblock, Warnzeilen und Telegram gerendert
    werden THEN Stufe 2 ohne "oberhalb"/"unterhalb"."""
    from tests.helpers.avalanche_report_support import embedded_block

    a = _slf_warnung(monkeypatch, WINTER_ABEND, "CH-5112", T_ABEND)
    assert a.native_level == 2 and a.elevation_value is None, a

    block = embedded_block([a])
    zeilen = " | ".join(_warnzeilen_plain([a]))
    telegram = _telegram_direkt(a)

    assert "Lawinenstufe 2 (mäßig)" in block and "Lawinenstufe 2 (mäßig)" in zeilen
    for text in (block, zeilen, telegram):
        assert "oberhalb" not in text and "unterhalb" not in text, text


# ====================================================================== AC-10 (Hinweis)
@pytest.mark.parametrize("fehlerart", sorted(FEHLERARTEN))
def test_ac10_slf_abruffehler_zeigt_die_ausfall_hinweiszeile_im_trip_briefing(monkeypatch, fehlerart):
    """AC-10. GIVEN SLF ist die einzige zustaendige Quelle und der Abruf scheitert (Netzfehler,
    503, kaputtes JSON, 200 ohne ``bulletins``) WHEN fuer einen Punkt in Graubuenden das
    Trip-Briefing gerendert wird THEN steht die Hinweiszeile "nicht abrufbar" in HTML und Text."""
    transport, alerts, unavailable = _slf_abruf(
        monkeypatch, FEHLERARTEN[fehlerart](), interior_point(DAVOS), T_WINTER)

    assert transport.count == 1, f"Vorbedingung: genau ein Abruf an aws.slf.ch ({transport.calls})"
    assert alerts == [] and unavailable is True
    html, plain = _trip_mail(alerts, punkt=interior_point(DAVOS), unavailable=unavailable)
    assert "Amtliche Warnungen aktuell nicht abrufbar" in html
    assert "nicht abrufbar" in plain


# ====================================================================== AC-18 Quelle/Link/Satz
def test_ac18_trip_briefing_mail_traegt_slf_quelle_link_und_massgeblichkeitssatz(monkeypatch):
    """AC-18. GIVEN SLF-Warnung CH-7231 (2026-03-01 Morgen) WHEN die Trip-Briefing-Mail gerendert
    wird THEN enthaelt sie Quellenname, Link zum Originalbericht und den Massgeblichkeitssatz."""
    html, _plain = _trip_mail([_muenstertal_minus(monkeypatch)])

    for element in _SLF_MARKER:
        assert element in html, f"{element!r} fehlt in der Trip-Briefing-Mail"


def test_ac18_ortsvergleichs_mail_traegt_slf_quelle_link_und_massgeblichkeitssatz(monkeypatch):
    """AC-18. GIVEN dieselbe Warnung an einem Ort WHEN die Ortsvergleichs-Mail gerendert wird
    THEN enthaelt sie Quellenname, Link und Massgeblichkeitssatz."""
    html, _plain = _compare_mail([_muenstertal_minus(monkeypatch)])

    for element in _SLF_MARKER:
        assert element in html, f"{element!r} fehlt in der Ortsvergleichs-Mail"


@pytest.mark.parametrize("flaeche", ["trip", "vergleich"])
def test_ac18_eigenstaendige_warnmail_und_telegram_langform_tragen_quelle_link_und_satz(monkeypatch, flaeche):
    """AC-18. GIVEN dieselbe Warnung WHEN der echte Trip- bzw. Ortsvergleich-Alarm
    (``send_official_alert`` / ``send_multi_location_official_alert``) versendet wird THEN tragen
    die zugestellte Warn-Mail (HTML- UND Text-Teil) und die Telegram-Langform Quellenname, Link
    und Massgeblichkeitssatz."""
    mit = _FLAECHEN[flaeche](monkeypatch, _muenstertal_minus(monkeypatch))
    mail, telegram = _einzige(mit, "email"), _einzige(mit, "telegram")

    for element in _SLF_MARKER:
        assert element in mail["body"], f"{element!r} fehlt im HTML-Teil der Warn-Mail"
        assert element in (mail["plain_text_body"] or ""), f"{element!r} fehlt im Text-Teil"
        assert element in telegram["body"], f"{element!r} fehlt in der Telegram-Langform"


def test_ac18_sms_premium_sms_und_telegram_kurzform_tragen_weder_quelle_noch_link_noch_satz(monkeypatch):
    """AC-18. GIVEN dieselbe Warnung (Positivkontrolle: die Mail desselben Versands nennt die
    Quelle) WHEN SMS, Premium-SMS und Telegram-Kurzform versendet werden THEN enthaelt keine der
    drei Nachrichten Quellenname, Link oder Massgeblichkeitssatz."""
    a = _muenstertal_minus(monkeypatch)
    mit = _trip_versand(monkeypatch, a, telegram_style="kurzform")

    assert SLF_LABEL in _einzige(mit, "email")["body"], "Positivkontrolle: Mail nennt die Quelle"
    for kanal in ("sms", "premium_sms", "telegram"):
        text = _einzige(mit, kanal)["body"]
        assert _av_token(text, 3), f"Positivkontrolle {kanal}: AV3 fehlt: {text!r}"
        for verboten in (*_SLF_MARKER, "SLF", "WSL", "slf.ch", "Maßgeblich"):
            assert verboten not in text, f"{kanal} traegt {verboten!r}: {text!r}"


@pytest.mark.parametrize("quelle", ["slf_bulletin", "slf_bulletin:CH-7231", "slf_bulletin:CH-5123"])
def test_ac18_quellenlabel_fuer_registry_name_und_region(quelle):
    """AC-18. GIVEN der Registry-Name ``slf_bulletin`` (Entwarnungs-Mail) bzw. eine Regions-Kennung
    WHEN das Quellenlabel aufgeloest wird THEN lautet es "WSL-Institut fuer Schnee- und
    Lawinenforschung SLF"."""
    from output.renderers.alert.official_alerts import official_alert_source_label

    assert official_alert_source_label(quelle) == SLF_LABEL


# ====================================================================== AC-19 Feinstufe Mail
_FEINSTUFEN = [("-", _ZEILE_MINUS), (None, _ZEILE_NEUTRAL), ("+", _ZEILE_PLUS)]
_FEINSTUFEN_IDS = ["minus-echt", "neutral-abgeleitet", "plus-abgeleitet"]


def _mit_feinstufe(monkeypatch, modifier):
    """Echte CH-7231-Warnung (minus); neutral/plus abgeleitet ueber ``level_modifier``."""
    a = _muenstertal_minus(monkeypatch)
    return a if modifier == "-" else dataclasses.replace(a, level_modifier=modifier)


def _assert_feinstufe(text: str, erwartet: str, modifier, wo: str) -> None:
    assert erwartet in text, f"{wo}: {erwartet!r} fehlt"
    if modifier is None:
        assert "Lawinenstufe 3-" not in text and "Lawinenstufe 3+" not in text, f"{wo}: Feinstufe bei neutral"


@pytest.mark.parametrize("modifier, erwartet", _FEINSTUFEN, ids=_FEINSTUFEN_IDS)
def test_ac19_trip_briefing_mail_zeigt_die_feinstufe_in_html_und_text(monkeypatch, modifier, erwartet):
    """AC-19. GIVEN SLF-Warnung Stufe 3 (minus/neutral/plus), oberhalb 2000 m, Altschnee
    WHEN die Trip-Briefing-Mail gerendert wird THEN lautet die Stufenzeile im HTML- und im
    Text-Teil "Lawinenstufe 3- / 3 / 3+ (erheblich) oberhalb 2000 m · Altschnee"."""
    html, plain = _trip_mail([_mit_feinstufe(monkeypatch, modifier)])

    _assert_feinstufe(html, erwartet, modifier, "Trip-Briefing HTML")
    _assert_feinstufe(plain, erwartet, modifier, "Trip-Briefing Text")


@pytest.mark.parametrize("modifier, erwartet", _FEINSTUFEN, ids=_FEINSTUFEN_IDS)
def test_ac19_ortsvergleichs_mail_zeigt_die_feinstufe_in_html_und_text(monkeypatch, modifier, erwartet):
    """AC-19. GIVEN dieselbe Warnung WHEN die Ortsvergleichs-Mail gerendert wird THEN steht die
    Stufenzeile mit Feinstufe im HTML- und im Text-Teil."""
    html, plain = _compare_mail([_mit_feinstufe(monkeypatch, modifier)])

    _assert_feinstufe(html, erwartet, modifier, "Ortsvergleich HTML")
    _assert_feinstufe(plain, erwartet, modifier, "Ortsvergleich Text")


@pytest.mark.parametrize("flaeche", ["trip", "vergleich"])
@pytest.mark.parametrize("modifier, erwartet", _FEINSTUFEN, ids=_FEINSTUFEN_IDS)
def test_ac19_eigenstaendige_warnmail_zeigt_die_feinstufe_in_html_und_text(monkeypatch, modifier, erwartet,
                                                                           flaeche):
    """AC-19. GIVEN dieselbe Warnung WHEN der echte Trip- bzw. Ortsvergleich-Alarm die Warn-Mail
    zustellt THEN steht die Stufenzeile mit Feinstufe im HTML- und im Text-Teil."""
    mail = _einzige(_FLAECHEN[flaeche](monkeypatch, _mit_feinstufe(monkeypatch, modifier)), "email")

    _assert_feinstufe(mail["body"], erwartet, modifier, "Warn-Mail HTML")
    _assert_feinstufe(mail["plain_text_body"] or "", erwartet, modifier, "Warn-Mail Text")


def test_ac19_echte_feinstufe_plus_aus_dem_januar_bulletin(monkeypatch):
    """AC-19 (echter Plus-Fall). GIVEN Bulletin 2026-01-15, Region CH-5112 (Feinstufe plus)
    WHEN die Trip-Briefing-Mail gerendert wird THEN beginnt die Stufenzeile mit
    "Lawinenstufe 3+ (erheblich)"."""
    a = _slf_warnung(monkeypatch, JANUAR, "CH-5112", T_JANUAR)
    assert (a.native_level, a.level_modifier) == (3, "+"), a
    html, plain = _trip_mail([a], punkt=interior_point("CH-5112"))

    assert "Lawinenstufe 3+ (erheblich)" in html
    assert "Lawinenstufe 3+ (erheblich)" in plain


# ====================================================================== AC-20 Telegram
@pytest.mark.parametrize("flaeche", ["trip", "vergleich"])
def test_ac20_telegram_langform_zeigt_feinstufe_in_zeile_und_kopfzeile(monkeypatch, flaeche):
    """AC-20. GIVEN SLF-Warnung Stufe 3 minus WHEN der echte Trip- bzw. Ortsvergleich-Alarm die
    Telegram-Langform zustellt THEN steht "Lawinenstufe 3- (erheblich)" in einer Zeile und
    "Lawinenstufe 3-" in der (fetten) Kopfzeile."""
    mit = _FLAECHEN[flaeche](monkeypatch, _muenstertal_minus(monkeypatch))
    text = _einzige(mit, "telegram")["body"]
    koepfe = [z for z in text.splitlines() if z.startswith("<b>")]

    assert "Lawinenstufe 3- (erheblich)" in text, text
    assert any("Lawinenstufe 3-" in k for k in koepfe), koepfe


def test_ac20_telegram_kurzform_ist_identisch_zum_sms_text_ohne_feinstufe(monkeypatch):
    """AC-20. GIVEN dieselbe Warnung (Positivkontrolle ``level_modifier == "-"``) WHEN der Trip-Alarm
    im Telegram-Kurzstil versendet wird THEN ist die Telegram-Nachricht identisch zur SMS und
    traegt ``AV3`` ohne Feinstufe."""
    mit = _trip_versand(monkeypatch, _muenstertal_minus(monkeypatch), telegram_style="kurzform")
    telegram, sms = _einzige(mit, "telegram")["body"], _einzige(mit, "sms")["body"]

    assert telegram == sms
    assert len(_av_token(telegram, 3)) == 1 and not _FEINSTUFE_SMS.search(telegram), telegram


# ====================================================================== AC-21 SMS-Wege
def test_ac21_briefing_sms_traegt_av3_im_warnblock_ohne_feinstufe(monkeypatch):
    """AC-21. GIVEN SLF-Warnung Stufe 3 minus WHEN die Briefing-SMS gebaut wird THEN steht genau
    ein ``AV``-Token, ``!AV3`` im Warnblock, kein ``AV3-``/"3-" und kein Quellenname."""
    sms = _briefing_sms([_muenstertal_minus(monkeypatch)])

    assert "!AV3" in sms and sms.count("AV") == 1, sms
    assert not _FEINSTUFE_SMS.search(sms) and "3-" not in sms, sms
    assert "SLF" not in sms and "WSL" not in sms, sms


def test_ac21_alarm_sms_und_premium_sms_tragen_av3_ohne_feinstufe(monkeypatch):
    """AC-21. GIVEN dieselbe Warnung WHEN der echte Trip-Alarm SMS und Premium-SMS zustellt
    THEN enthaelt jede genau ein ``AV``-Token ``AV3``, nie ``AV3-``/"3-" und keinen Quellennamen."""
    mit = _trip_versand(monkeypatch, _muenstertal_minus(monkeypatch))

    for kanal in ("sms", "premium_sms"):
        text = _einzige(mit, kanal)["body"]
        assert len(_av_token(text, 3)) == 1 and text.count("AV") == 1, f"{kanal}: {text!r}"
        assert not _FEINSTUFE_SMS.search(text) and "3-" not in text, f"{kanal}: {text!r}"
        assert "SLF" not in text and "WSL" not in text, f"{kanal}: {text!r}"


# ====================================================================== AC-22 Alarm-Matrix
@pytest.mark.parametrize("kanal", ["email", "telegram", "sms", "premium_sms"])
@pytest.mark.parametrize("flaeche", ["trip", "vergleich"])
def test_ac22_abgeleitet_stufe_4_kommt_in_beiden_flaechen_ueber_jeden_kanal_an(monkeypatch, flaeche, kanal):
    """AC-22. GIVEN Eskalation auf Stufe 4 in CH-7231 (abgeleitet aus 2026-03-01 Morgen)
    WHEN der Alarm im Trip- bzw. Ortsvergleich-Alarm versendet wird THEN kommt er ueber diesen
    Kanal an -- Premium-SMS ausdruecklich auch im Ortsvergleich -- mit Stufe, Ort (Ortsvergleich)
    und Hoehe (Langform) in kanalgerechter Form."""
    a = _muenstertal_abgeleitet(monkeypatch, 4)
    sendung = _einzige(_FLAECHEN[flaeche](monkeypatch, a), kanal)
    text = " ".join(str(sendung.get(f) or "") for f in ("subject", "body", "plain_text_body"))

    if kanal in ("email", "telegram"):
        assert "Lawinenstufe 4 (groß) oberhalb 2000 m" in text, text
        assert (TRIP_NAME if flaeche == "trip" else ORT) in text, text
    else:
        assert len(_av_token(sendung["body"], 4)) == 1, sendung["body"]
        if flaeche == "vergleich":
            assert ORT in sendung["body"], sendung["body"]


@pytest.mark.parametrize("flaeche", ["trip", "vergleich"])
def test_ac22_abgeleitet_stufe_5_nimmt_dieselben_wege_mit_originalziffer(monkeypatch, flaeche):
    """AC-22. GIVEN Stufe 5 (abgeleitet, ``level`` bleibt 4) WHEN der Alarm versendet wird
    THEN kommt er ueber alle vier Kanaele an, SMS/Premium-SMS mit ``AV5``, Mail mit
    "Lawinenstufe 5 (sehr groß)"."""
    mit = _FLAECHEN[flaeche](monkeypatch, _muenstertal_abgeleitet(monkeypatch, 5))

    assert set(mit.kanaele) == ALLE, mit
    assert "Lawinenstufe 5 (sehr groß)" in _einzige(mit, "email")["body"]
    for kanal in ("sms", "premium_sms"):
        assert len(_av_token(_einzige(mit, kanal)["body"], 5)) == 1, mit


# ====================================================================== AC-23 Quellenfilter
def _filter_ergebnis(monkeypatch, sources):
    """Echter ``CompareOfficialAlertService._detect`` (Quellenfilter #1258) mit der echten
    ``SlfSource``; die Wanduhr steht auf dem Fixture-Zeitpunkt (der Dienst fragt mit ihr ab)."""
    from freezegun import freeze_time

    from app.config import Settings
    from app.user import SavedLocation
    from services.compare_official_alert import CompareOfficialAlertService

    transport = SlfFixtureTransport(WINTER_MORGEN)
    only_slf(monkeypatch, transport, FakeClock(T_WINTER))
    lat, lon = interior_point(DAVOS)
    ort = SavedLocation(id="loc-davos", name=ORT, lat=lat, lon=lon, elevation_m=1560)
    service = CompareOfficialAlertService(
        settings=Settings(smtp_host="dummy.invalid", smtp_user="dummy", smtp_pass="dummy",
                          mail_to="d@example.invalid"),
        user_id=f"slf-filter-{uuid.uuid4().hex[:8]}", mail_sink=lambda subject, body: None,
    )
    with freeze_time(T_WINTER):
        tagged, _pro_ort = service._detect("p-slf", [ort], sources)
    return [(a.hazard, a.source) for a, _ids in tagged]


def test_ac23_ortsvergleich_ohne_filter_zeigt_die_slf_warnung(monkeypatch):
    """AC-23. GIVEN ein Ort in Graubuenden WHEN ohne ``sources``-Filter abgefragt wird THEN
    erscheint die SLF-Warnung."""
    assert _filter_ergebnis(monkeypatch, None) == [("avalanche_bulletin", "slf_bulletin:CH-5123")]


def test_ac23_ortsvergleich_mit_filter_slf_bulletin_zeigt_die_slf_warnung(monkeypatch):
    """AC-23. GIVEN derselbe Ort WHEN mit ``sources=["slf_bulletin"]`` abgefragt wird THEN
    erscheint die SLF-Warnung (Quellenname = Teil vor dem ersten ':')."""
    assert _filter_ergebnis(monkeypatch, ["slf_bulletin"]) == [("avalanche_bulletin", "slf_bulletin:CH-5123")]


def test_ac23_ortsvergleich_mit_filter_meteoalarm_blendet_die_slf_warnung_aus(monkeypatch):
    """AC-23. GIVEN derselbe Ort (Positivkontrolle: ohne Filter erscheint die Warnung) WHEN mit
    ``sources=["meteoalarm"]`` abgefragt wird THEN fehlt die SLF-Warnung."""
    assert _filter_ergebnis(monkeypatch, None), "Positivkontrolle: ohne Filter erscheint die Warnung"
    assert _filter_ergebnis(monkeypatch, ["meteoalarm"]) == []


# ====================================================================== AC-24 Eskalation
def _gedaechtnis(alert) -> dict:
    from output.renderers.alert.official_alerts import official_alert_state_entry, official_alert_state_key

    return {official_alert_state_key(alert): official_alert_state_entry(alert, MELDUNG)}


def _urteil(alert, state, now: datetime):
    from output.renderers.alert.official_alerts import official_alert_revision_verdict

    return official_alert_revision_verdict(alert, state, now=now)


def test_ac24_abgeleitet_eskalation_3_auf_4_wird_gemeldet(monkeypatch):
    """AC-24. GIVEN zuletzt gemeldet Stufe 3 (CH-7231, echt) und neue Stufe 4 (abgeleitet,
    gleiche Ausgabe) WHEN der Alarm-Lauf urteilt THEN wird eskaliert."""
    from output.renderers.alert.official_alerts import official_alert_state_key

    drei = _muenstertal_minus(monkeypatch)
    vier = _muenstertal_abgeleitet(monkeypatch, 4)
    assert official_alert_state_key(drei) == official_alert_state_key(vier), "Voraussetzung: derselbe Schluessel"

    melden, _stale, _merged = _urteil(vier, _gedaechtnis(drei), T_WINTER)

    assert melden is True


def test_ac24_abgeleitet_eskalation_4_auf_5_vergleicht_native_level(monkeypatch):
    """AC-24. GIVEN zuletzt gemeldet Stufe 4 und neue Stufe 5 (beide abgeleitet, ``level`` beidseitig
    4) WHEN der Alarm-Lauf urteilt THEN wird eskaliert (Vergleich ueber ``native_level``)."""
    vier = _muenstertal_abgeleitet(monkeypatch, 4)
    fuenf = _muenstertal_abgeleitet(monkeypatch, 5)
    assert vier.level == fuenf.level == 4, "Voraussetzung: Farblevel gleich -- nur native_level unterscheidet"

    melden, _stale, _merged = _urteil(fuenf, _gedaechtnis(vier), T_WINTER)

    assert melden is True


def test_ac24_abgeleitet_kette_3_4_5_mit_gedaechtnis_meldet_zweimal(monkeypatch):
    """AC-24 (Kette). GIVEN Gedaechtnis nach Stufe 3 WHEN nacheinander Stufe 4 und 5 (abgeleitet)
    beurteilt werden und das Gedaechtnis jeweils fortgeschrieben wird THEN eskalieren beide."""
    from output.renderers.alert.official_alerts import official_alert_state_entry, official_alert_state_key

    state = _gedaechtnis(_muenstertal_minus(monkeypatch))
    meldungen = []
    for stufe in (4, 5):
        neu = _muenstertal_abgeleitet(monkeypatch, stufe)
        melden, _stale, _merged = _urteil(neu, state, T_WINTER)
        meldungen.append(melden)
        if melden:
            state[official_alert_state_key(neu)] = official_alert_state_entry(neu, MELDUNG)

    assert meldungen == [True, True]


def test_ac24_folgeausgabe_gleiche_stufe_abend_auf_morgen_update_bleibt_still(monkeypatch):
    """AC-24. GIVEN gemeldet die Abend-Ausgabe 2026-03-01 (CH-7231, Stufe 3) WHEN das Morgen-Update
    2026-03-02 mit gleicher Stufe beurteilt wird THEN kein neuer Alarm (Identitaet = Mikroregion,
    nicht die wechselnde Bulletin-ID); das Gedaechtnis wird still fortgeschrieben."""
    from output.renderers.alert.official_alerts import official_alert_state_key

    abend = _slf_warnung(monkeypatch, WINTER_ABEND, MUENSTERTAL, T_ABEND)
    morgen = _slf_warnung(monkeypatch, MORGEN_UPDATE, MUENSTERTAL, T_MORGEN_UPDATE)
    id_abend = bulletin_of(slf_doc(WINTER_ABEND), MUENSTERTAL)["bulletinID"]
    id_morgen = bulletin_of(slf_doc(MORGEN_UPDATE), MUENSTERTAL)["bulletinID"]
    assert id_abend != id_morgen, "Voraussetzung: verschiedene Bulletin-IDs"
    assert abend.native_level == morgen.native_level == 3
    assert abend.dedup_id == morgen.dedup_id == "avalanche_bulletin:CH-7231"
    assert official_alert_state_key(abend) != official_alert_state_key(morgen), "Voraussetzung: neue Ausgabe"

    melden, stale, merged = _urteil(morgen, _gedaechtnis(abend), T_MORGEN_UPDATE)

    assert melden is False
    assert stale == official_alert_state_key(abend) and merged is not None
    assert merged["last_reported_value"] == 3.0


def test_ac24_abend_ausgabe_gilt_frueh_am_folgetag_noch_und_bleibt_still(monkeypatch):
    """AC-24 (dieselbe Abend-Ausgabe frueh am Folgetag). GIVEN gemeldet die Abend-Ausgabe
    (2026-03-01 17:30Z) WHEN sie um 2026-03-02 06:00Z erneut geliefert wird THEN kein Alarm."""
    abend = _slf_warnung(monkeypatch, WINTER_ABEND, MUENSTERTAL, T_ABEND)
    frueh = _slf_warnung(monkeypatch, ABEND_FOLGETAG_FRUEH, MUENSTERTAL,
                         datetime(2026, 3, 2, 6, 0, tzinfo=UTC))
    assert frueh.native_level == 3

    melden, _stale, _merged = _urteil(frueh, _gedaechtnis(abend), datetime(2026, 3, 2, 6, 0, tzinfo=UTC))

    assert melden is False


# ====================================================================== AC-25 Zwei Nutzer
def _briefing_fuer(punkt, now):
    alerts, unavailable = alerts_with_status(*punkt, now)
    html, _plain = _trip_mail(alerts, punkt=punkt, unavailable=unavailable)
    return alerts, unavailable, html, _briefing_sms(alerts)


def test_ac25_nur_der_graubuenden_nutzer_bekommt_den_slf_bericht_in_mail_und_sms(monkeypatch):
    """AC-25. GIVEN Nutzer A (Trip in Graubuenden, Winter-Fixture) und Nutzer B (Trip in Muenchen)
    WHEN fuer beide Trip-Briefing-Mail und -SMS erzeugt werden THEN enthaelt nur die von A den
    SLF-Bericht; die von B bleibt ohne Lagebericht und ohne Hinweis; A in umgekehrter Reihenfolge
    erneut liefert dasselbe."""
    transport = SlfFixtureTransport(WINTER_MORGEN)
    only_slf(monkeypatch, transport, FakeClock(T_WINTER))

    a_alerts, a_unav, a_html, a_sms = _briefing_fuer(interior_point(DAVOS), T_WINTER)
    b_alerts, b_unav, b_html, b_sms = _briefing_fuer(P_MUENCHEN, T_WINTER)
    a_alerts2, _u, _h, a_sms2 = _briefing_fuer(interior_point(DAVOS), T_WINTER)

    assert [a.source for a in a_alerts] == ["slf_bulletin:CH-5123"] and a_unav is False
    assert _ZEILE_MINUS in a_html and SLF_LABEL in a_html
    assert "!AV3" in a_sms, a_sms
    assert b_alerts == [] and b_unav is False
    assert "Lawinen" not in b_html and "nicht abrufbar" not in b_html and SLF_LABEL not in b_html
    assert "AV" not in b_sms and "!" not in b_sms, b_sms
    assert a_sms2 == a_sms and len(a_alerts2) == 1
    assert transport.count == 1, "Muenchen loest keinen Abruf aus, Graubuenden nur einen (Cache)"


def _lawinen_eintraege(uid: str, entity: str) -> dict:
    from tests.tdd._official_alert_allclear_fixtures import gedaechtnis

    return {k: v for k, v in gedaechtnis(uid, entity).items() if "avalanche_bulletin" in k}


def test_ac25_melde_gedaechtnisse_der_beiden_nutzer_bleiben_getrennt(monkeypatch):
    """AC-25 (Gedaechtnis). GIVEN Nutzer A (Graubuenden) und Nutzer B (Muenchen), je ein echter
    Trip-Alarmlauf mit der echten ``SlfSource`` in der Registry WHEN beide nacheinander laufen
    THEN hat A den SLF-Eintrag (Positivkontrolle: A wurde wirklich alarmiert), B keinen, und
    keiner liest einen Eintrag des anderen."""
    from freezegun import freeze_time

    from tests.helpers.transport_mitschrift import aufzeichner_installieren
    from tests.tdd._official_alert_allclear_fixtures import Szenario, _segment, quellen

    quelle = make_slf_source(SlfFixtureTransport(WINTER_MORGEN), FakeClock(T_WINTER))
    mit = aufzeichner_installieren(monkeypatch)

    def _geometrie(punkt):
        return [_segment(1, punkt[0], punkt[1], T_WINTER - timedelta(hours=2), T_WINTER + timedelta(hours=8))]

    with quellen(quelle):
        with freeze_time(T_WINTER):
            sz_a = Szenario("trip", monkeypatch, mit, T_WINTER, geometrie=_geometrie(interior_point(DAVOS)))
        lauf_a = sz_a.lauf(0)
        with freeze_time(T_WINTER):
            sz_b = Szenario("trip", monkeypatch, mit, T_WINTER, geometrie=_geometrie(P_MUENCHEN))
        lauf_b = sz_b.lauf(0)

    assert sz_a.uid != sz_b.uid
    mails_a = [s["body"] for s in lauf_a.sendungen("email")]
    assert any("Lawinenstufe 3" in (b or "") for b in mails_a), f"Vorbedingung: A wurde alarmiert: {lauf_a!r}"
    assert not lauf_b.kanaele, f"B (Muenchen) darf nichts erhalten: {lauf_b!r}"

    eintraege_a = _lawinen_eintraege(sz_a.uid, sz_a.entity)
    assert len(eintraege_a) == 1, eintraege_a
    assert _lawinen_eintraege(sz_b.uid, sz_b.entity) == {}
    assert _lawinen_eintraege(sz_b.uid, sz_a.entity) == {}, "B liest A's Gedaechtnis"
    assert _lawinen_eintraege(sz_a.uid, sz_b.entity) == {}, "A liest B's Gedaechtnis"
