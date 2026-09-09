"""
TDD RED — öffentliche Basis-URL (public_host) für den Python-Core.

Spec: docs/specs/modules/public_host.md (Issue #2272)

Deckt AC-1 bis AC-7: sechs Text-/Link-Ausgabestellen (Trip-Report-Mail,
Telegram-Befehle `### config`/`### columns`, drei Telegram-Fließtext-Stellen)
plus `GET /health` sollen bei gesetztem `GZ_PUBLIC_HOST` den konfigurierten
Host tragen und bei fehlendem Wert den Link-/Host-Anteil ERSATZLOS weglassen
(fail-closed) — niemals `gregor20.henemm.com` als eingebrannten Literal.

Nachweisform (CLAUDE.md, Mock-Verbot): KEIN Mock()/patch()/MagicMock. Gefakt
wird ausschließlich die äußere Netzgrenze der Telegram-Tests (`httpx.post`,
Muster aus `tests/tdd/test_telegram_chat_id_ownership.py`) — alles dazwischen
(Reader, TripCommandProcessor, NotificationService, TelegramOutput) läuft
produktiv. Die Mail-/Health-Tests rufen echte Renderer/Endpoints auf und
prüfen den tatsächlich erzeugten Text/JSON, keine Dateiinhalte.

RED-Erwartung gegen den unveränderten Ausgangscode: `Settings` kennt kein
`public_host`-Feld (wird über `extra="ignore"` still verschluckt), alle sechs
Stellen bleiben beim Literal `gregor20.henemm.com` fest verdrahtet, und
`GET /health` liefert kein `public_host`-Feld.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import httpx

from app.config import Settings
from app.trip import Stage, Trip, Waypoint

_STAGING_HOST = "https://staging.gregor20.henemm.com"


# ---------------------------------------------------------------------------
# Gemeinsame Bausteine (echte Objekte, kein Mock)
# ---------------------------------------------------------------------------

def _assert_no_bare_prod_host(text: str) -> None:
    """`gregor20.henemm.com` darf NUR als `staging.`-Suffix vorkommen (oder
    gar nicht) — nie als bloßer Produktions-Host."""
    match = re.search(r"(?<!staging\.)gregor20\.henemm\.com", text)
    assert match is None, (
        f"Produktions-Host 'gregor20.henemm.com' (nicht als staging.-Suffix) "
        f"im Text gefunden: {text!r}"
    )


def _minimal_trip(trip_id: str, name: str | None = None) -> Trip:
    """Kleinstmöglicher Trip für Aufrufe, die kein echtes Wetter brauchen
    (Rendering-/Link-Aufbau, kein Persistenz-Roundtrip)."""
    wp = Waypoint(id="G1", name="Start", lat=42.15, lon=9.15, elevation_m=800)
    stage = Stage(id="T1", name="Etappe 1", date=date(2026, 7, 10), waypoints=[wp])
    return Trip(id=trip_id, name=name or f"Trip {trip_id}", stages=[stage])


def _build_seg_data():
    """Minimales, aber echtes SegmentWeatherData für format_email() —
    identisches Muster wie tests/tdd/test_briefing_mail_inhalt.py."""
    from app.models import (
        ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries,
        Provider, SegmentWeatherData, SegmentWeatherSummary, ThunderLevel,
        TripSegment,
    )
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.13, lon=9.13, elevation_m=900.0),
        end_point=GPXPoint(lat=42.10, lon=9.18, elevation_m=1450.0),
        start_time=datetime(2026, 7, 10, 8, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc),
        duration_hours=4.0, distance_km=14.5, ascent_m=820.0, descent_m=440.0,
    )
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="demo", grid_res_km=1.3,
        run=datetime(2026, 7, 10, 0, 0, tzinfo=timezone.utc),
    )
    data = [
        ForecastDataPoint(
            ts=datetime(2026, 7, 10, h, 0, tzinfo=timezone.utc),
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
        fetched_at=datetime.now(timezone.utc), provider="demo",
    )


def _build_request_and_render(settings: Settings, trip_id: str = "abc"):
    """Baut das echte TripReportRequest-DTO über den Produktivpfad
    (_build_trip_report_request) UND rendert es über den echten
    HTML-Renderer — genau die zwei Ebenen, die AC-1/AC-5 verlangen."""
    from output.renderers.trip_report import TripReportFormatter
    from services.trip_report_scheduler import TripReportSchedulerService

    trip = _minimal_trip(trip_id)
    scheduler = TripReportSchedulerService(settings=settings, user_id="gz2272scheduler")
    request = scheduler._build_trip_report_request(
        trip=trip,
        report_type="evening",
        segment_weather=[],
        trip_tz=ZoneInfo("Europe/Vienna"),
        stage_name=None,
        stage_stats=None,
        night_weather=None,
        thunder_forecast=None,
        multi_day_trend=None,
        stability_result=None,
        day_comparison=None,
        exposed_sections=[],
        allow_test_fallback=False,
        on_demand=False,
        catchup_prefix=None,
    )
    report = TripReportFormatter().format_email(
        [_build_seg_data()],
        trip_name=trip.name,
        report_type="evening",
        trip_url=request.trip_url,
    )
    return request, report


class _WireRecorder:
    """Fake an der EINZIGEN echten Außengrenze: dem HTTP-POST an die
    Telegram-Bot-API (Muster aus test_telegram_chat_id_ownership.py). Jeder
    andere Host ist im deterministischen Kern ein Fehler."""

    def __init__(self) -> None:
        self.telegram: list[dict] = []

    def post(self, url, **kwargs):
        payload = kwargs.get("json") or {}
        if "api.telegram.org" in str(url):
            self.telegram.append({"url": str(url), "payload": payload})
            return httpx.Response(
                200, json={"ok": True, "result": {"message_id": len(self.telegram)}}
            )
        raise AssertionError(f"unerwarteter HTTP-POST im Kern-Test: {url}")

    def texts(self) -> list[str]:
        return [str(p["payload"].get("text", "")) for p in self.telegram]


def _telegram_settings(chat_id: str, *, public_host: str | None) -> Settings:
    """Telegram-Settings mit Herkunftssperre (#1476) neutralisiert:
    telegram_test_chat_id == chat_id, telegram_test_bot_token == Bot-Token."""
    return Settings(
        env="production",
        is_test_mode=False,
        telegram_bot_token="gz2272-bot-token",
        telegram_chat_id=chat_id,
        telegram_test_bot_token="gz2272-bot-token",
        telegram_test_chat_id=chat_id,
        public_host=public_host,
    )


def _register_user(user_id: str, chat_id: str) -> None:
    """Schreibt ein minimales user.json mit telegram_chat_id in die per
    Test isolierte data/users/-Wurzel (tests/conftest.py _isolate_data_root)."""
    from app.loader import get_data_dir

    d = get_data_dir(user_id)
    d.mkdir(parents=True, exist_ok=True)
    (d / "user.json").write_text(
        json.dumps({"id": user_id, "telegram_chat_id": chat_id}), encoding="utf-8",
    )


def _incoming_update(chat_id: str, text: str) -> dict:
    return {
        "update_id": 1,
        "message": {
            "message_id": 1,
            "from": {"id": int(chat_id), "is_bot": False, "first_name": "Test"},
            "chat": {"id": int(chat_id), "type": "private"},
            "date": int(datetime.now(tz=timezone.utc).timestamp()),
            "text": text,
        },
    }


def _incoming_callback(chat_id: str, message_id: int, data: str) -> dict:
    return {
        "update_id": 1,
        "callback_query": {
            "id": "cbq-2272",
            "from": {"id": int(chat_id), "is_bot": False, "first_name": "Test"},
            "data": data,
            "message": {
                "message_id": message_id,
                "from": {"id": 1, "is_bot": True, "first_name": "Gregor"},
                "chat": {"id": int(chat_id), "type": "private"},
                "date": int(datetime.now(tz=timezone.utc).timestamp()),
                "text": "vorherige Nachricht",
            },
        },
    }


# ---------------------------------------------------------------------------
# AC-1 — trip_report_scheduler.py:1830 (Mail-Deep-Link, gesetzt)
# ---------------------------------------------------------------------------

class TestAC1SchedulerUsesConfiguredHost:
    def test_trip_url_field_uses_configured_host(self):
        """
        GIVEN GZ_PUBLIC_HOST=staging-Host ist auf den Settings gesetzt
        WHEN ein TripReportRequest für Trip "abc" gebaut wird
        THEN ist trip_url exakt "{staging-host}/trips/abc"
        """
        settings = Settings(env="production", is_test_mode=False, public_host=_STAGING_HOST)
        request, _ = _build_request_and_render(settings, trip_id="abc")
        assert request.trip_url == f"{_STAGING_HOST}/trips/abc", (
            f"AC-1: trip_url sollte '{_STAGING_HOST}/trips/abc' sein, war "
            f"{request.trip_url!r} (RED: Feld ist noch fest verdrahtet)."
        )

    def test_rendered_html_contains_configured_host_not_prod(self):
        """
        GIVEN dieselbe Konfiguration
        WHEN der Mail-Body (HTML) gerendert wird
        THEN enthält er den Deep-Link mit dem Staging-Host, nicht mit gregor20.henemm.com
        """
        settings = Settings(env="production", is_test_mode=False, public_host=_STAGING_HOST)
        _, report = _build_request_and_render(settings, trip_id="abc")
        assert f"{_STAGING_HOST}/trips/abc" in report.email_html, (
            "AC-1: gerenderter Mail-Body enthält nicht den konfigurierten "
            "Staging-Deep-Link."
        )
        _assert_no_bare_prod_host(report.email_html)


# ---------------------------------------------------------------------------
# AC-2 — trip_command_processor.py:1863 (_show_config, gesetzt)
# ---------------------------------------------------------------------------

class TestAC2ShowConfigUsesConfiguredHost:
    def test_show_config_link_uses_configured_host(self, monkeypatch):
        """
        GIVEN GZ_PUBLIC_HOST=staging-Host ist gesetzt (Ad-hoc Settings()-Zugriff)
        WHEN TripCommandProcessor()._show_config(trip) aufgerufen wird
        THEN enthält confirmation_body die volle Staging-URL, nicht gregor20.henemm.com
        """
        from services.trip_command_processor import TripCommandProcessor

        monkeypatch.setenv("GZ_PUBLIC_HOST", _STAGING_HOST)
        trip = _minimal_trip("abc")
        result = TripCommandProcessor()._show_config(trip)
        assert f"{_STAGING_HOST}/trips/abc" in result.confirmation_body, (
            f"AC-2: confirmation_body enthält nicht die konfigurierte URL: "
            f"{result.confirmation_body!r}"
        )
        _assert_no_bare_prod_host(result.confirmation_body)


# ---------------------------------------------------------------------------
# AC-3 — trip_command_processor.py:1772 (_show_columns_info, gesetzt)
# ---------------------------------------------------------------------------

class TestAC3ColumnsInfoUsesConfiguredHost:
    def test_columns_info_uses_configured_host(self, monkeypatch):
        """
        GIVEN GZ_PUBLIC_HOST=staging-Host ist gesetzt
        WHEN TripCommandProcessor()._show_columns_info() aufgerufen wird
        THEN enthält confirmation_body die Staging-Basis-URL, nicht gregor20.henemm.com
        """
        from services.trip_command_processor import TripCommandProcessor

        monkeypatch.setenv("GZ_PUBLIC_HOST", _STAGING_HOST)
        result = TripCommandProcessor()._show_columns_info()
        assert _STAGING_HOST in result.confirmation_body, (
            f"AC-3: confirmation_body enthält nicht die konfigurierte "
            f"Basis-URL: {result.confirmation_body!r}"
        )
        _assert_no_bare_prod_host(result.confirmation_body)


# ---------------------------------------------------------------------------
# AC-4 — inbound_telegram_reader.py:188/208/315 (Fließtext, gesetzt)
# ---------------------------------------------------------------------------

class TestAC4TelegramProseUsesConfiguredHost:
    def test_line188_unregistered_chat_registration_hint(self, monkeypatch):
        """
        GIVEN eine unbekannte chat_id (kein user.json-Match) und gesetzter Host
        WHEN _process_update den Registrierungs-Hinweis baut (Zeile 188)
        THEN enthält der Text den bloßen Staging-Host, nicht gregor20.henemm.com
        """
        from services.inbound_telegram_reader import InboundTelegramReader

        rec = _WireRecorder()
        monkeypatch.setattr(httpx, "post", rec.post)
        settings = _telegram_settings("777000188", public_host=_STAGING_HOST)
        reader = InboundTelegramReader()
        reader._process_update(_incoming_update("777000188", "status"), settings)
        body = "\n".join(rec.texts())
        assert "staging.gregor20.henemm.com" in body, (
            f"AC-4 (Zeile 188): Registrierungs-Hinweis enthält nicht den "
            f"konfigurierten Host: {body!r}"
        )
        assert "https://staging.gregor20.henemm.com" not in body, (
            f"AC-4 (Zeile 188): Spec verlangt bloßen Host im Fließtext "
            f"(ohne Schema) — Text enthält die volle URL: {body!r}"
        )
        _assert_no_bare_prod_host(body)

    def test_line208_registered_chat_no_active_trip(self, monkeypatch):
        """
        GIVEN eine registrierte chat_id ohne aktiven Trip und gesetzter Host
        WHEN _process_update die "Kein aktiver Trip"-Meldung baut (Zeile 208)
        THEN enthält der Text den bloßen Staging-Host, nicht gregor20.henemm.com
        """
        from services.inbound_telegram_reader import InboundTelegramReader

        chat_id = "777000208"
        _register_user("gz2272regchat208", chat_id)
        rec = _WireRecorder()
        monkeypatch.setattr(httpx, "post", rec.post)
        settings = _telegram_settings(chat_id, public_host=_STAGING_HOST)
        reader = InboundTelegramReader()
        reader._process_update(_incoming_update(chat_id, "status"), settings)
        body = "\n".join(rec.texts())
        assert "staging.gregor20.henemm.com" in body, (
            f"AC-4 (Zeile 208): 'Kein aktiver Trip'-Meldung enthält nicht "
            f"den konfigurierten Host: {body!r}"
        )
        assert "https://staging.gregor20.henemm.com" not in body, (
            f"AC-4 (Zeile 208): Spec verlangt bloßen Host im Fließtext "
            f"(ohne Schema) — Text enthält die volle URL: {body!r}"
        )
        _assert_no_bare_prod_host(body)

    def test_line315_unregistered_chat_callback(self, monkeypatch):
        """
        GIVEN eine unbekannte chat_id klickt einen Inline-Button und gesetzter Host
        WHEN _process_callback_query die Nachricht in-place ersetzt (Zeile 315)
        THEN enthält der editierte Text den bloßen Staging-Host, nicht gregor20.henemm.com
        """
        from services.inbound_telegram_reader import InboundTelegramReader

        rec = _WireRecorder()
        monkeypatch.setattr(httpx, "post", rec.post)
        settings = _telegram_settings("777000315", public_host=_STAGING_HOST)
        reader = InboundTelegramReader()
        reader._process_update(_incoming_callback("777000315", 42, "glance"), settings)
        body = "\n".join(rec.texts())
        assert "staging.gregor20.henemm.com" in body, (
            f"AC-4 (Zeile 315): editierte Callback-Antwort enthält nicht "
            f"den konfigurierten Host: {body!r}"
        )
        assert "https://staging.gregor20.henemm.com" not in body, (
            f"AC-4 (Zeile 315): Spec verlangt bloßen Host im Fließtext "
            f"(ohne Schema) — Text enthält die volle URL: {body!r}"
        )
        _assert_no_bare_prod_host(body)


# ---------------------------------------------------------------------------
# AC-5 — Fail-closed an allen sechs Stellen, GZ_PUBLIC_HOST fehlt
# ---------------------------------------------------------------------------

class TestAC5FailClosedWithoutPublicHost:
    def test_scheduler_trip_url_is_none_and_deep_link_absent(self, monkeypatch):
        """Scheduler (trip_report_scheduler.py:1830): trip_url None, HTML ohne Deep-Link-Block."""
        monkeypatch.delenv("GZ_PUBLIC_HOST", raising=False)
        settings = Settings(env="production", is_test_mode=False, public_host=None)
        request, report = _build_request_and_render(settings, trip_id="abc")
        assert request.trip_url is None, (
            f"AC-5: trip_url sollte ohne GZ_PUBLIC_HOST None sein, war "
            f"{request.trip_url!r}."
        )
        assert "gregor20.henemm.com" not in report.email_html, (
            "AC-5: gerenderter Mail-Body enthält trotz fehlendem "
            "GZ_PUBLIC_HOST einen Host-Verweis."
        )

    def test_show_config_omits_link_entirely(self, monkeypatch):
        """trip_command_processor.py:1863: Link-Zeile entfällt exakt wie in der Spec spezifiziert."""
        from services.trip_command_processor import TripCommandProcessor

        monkeypatch.delenv("GZ_PUBLIC_HOST", raising=False)
        trip = _minimal_trip("abc")
        result = TripCommandProcessor()._show_config(trip)
        expected = (
            f"Einstellungen für '{trip.name}':\n\n"
            "Dort kannst du Zeitplan, Kanäle und Alarm-Schwellen anpassen."
        )
        assert result.confirmation_body == expected, (
            f"AC-5: confirmation_body ohne GZ_PUBLIC_HOST sollte exakt "
            f"{expected!r} sein, war {result.confirmation_body!r}."
        )

    def test_columns_info_omits_link_entirely(self, monkeypatch):
        """trip_command_processor.py:1772: URL-Zeile entfällt, Doppelpunkt wird zu Punkt."""
        from services.trip_command_processor import TripCommandProcessor

        monkeypatch.delenv("GZ_PUBLIC_HOST", raising=False)
        result = TripCommandProcessor()._show_columns_info()
        expected = "Spalten-Konfiguration ist nur im Trip-Editor möglich."
        assert result.confirmation_body == expected, (
            f"AC-5: confirmation_body ohne GZ_PUBLIC_HOST sollte exakt "
            f"{expected!r} sein, war {result.confirmation_body!r}."
        )

    def test_line188_omits_host_clause(self, monkeypatch):
        """inbound_telegram_reader.py:188: Klammerzusatz entfällt, Klammer bleibt geschlossen."""
        from services.inbound_telegram_reader import InboundTelegramReader

        rec = _WireRecorder()
        monkeypatch.setattr(httpx, "post", rec.post)
        settings = _telegram_settings("777100188", public_host=None)
        reader = InboundTelegramReader()
        reader._process_update(_incoming_update("777100188", "status"), settings)
        body = "\n".join(rec.texts())
        expected_tail = (
            "Sende /start gefolgt von deinem Token (zu finden im "
            "Account-Bereich)."
        )
        assert expected_tail in body, (
            f"AC-5 (Zeile 188): erwarteter Degradations-Text fehlt: {body!r}"
        )
        assert "gregor20.henemm.com" not in body

    def test_line208_omits_host_clause(self, monkeypatch):
        """inbound_telegram_reader.py:208: Adressteil entfällt."""
        from services.inbound_telegram_reader import InboundTelegramReader

        chat_id = "777100208"
        _register_user("gz2272regchat208b", chat_id)
        rec = _WireRecorder()
        monkeypatch.setattr(httpx, "post", rec.post)
        settings = _telegram_settings(chat_id, public_host=None)
        reader = InboundTelegramReader()
        reader._process_update(_incoming_update(chat_id, "status"), settings)
        body = "\n".join(rec.texts())
        assert "Kein aktiver Trip gefunden. Erstelle oder aktiviere einen Trip." in body, (
            f"AC-5 (Zeile 208): erwarteter Degradations-Text fehlt: {body!r}"
        )
        assert "gregor20.henemm.com" not in body

    def test_line315_omits_host_clause(self, monkeypatch):
        """inbound_telegram_reader.py:315: identischer Baustein wie Zeile 188."""
        from services.inbound_telegram_reader import InboundTelegramReader

        rec = _WireRecorder()
        monkeypatch.setattr(httpx, "post", rec.post)
        settings = _telegram_settings("777100315", public_host=None)
        reader = InboundTelegramReader()
        reader._process_update(_incoming_callback("777100315", 42, "glance"), settings)
        body = "\n".join(rec.texts())
        expected_tail = (
            "Sende /start gefolgt von deinem Token (zu finden im "
            "Account-Bereich)."
        )
        assert expected_tail in body, (
            f"AC-5 (Zeile 315): erwarteter Degradations-Text fehlt: {body!r}"
        )
        assert "gregor20.henemm.com" not in body


# ---------------------------------------------------------------------------
# AC-6 / AC-7 — GET /health
# ---------------------------------------------------------------------------

class TestAC6And7HealthReportsEffectiveConfig:
    def test_health_reports_configured_host_matching_rendered_mail(self, monkeypatch):
        """
        AC-6: GET /health liefert denselben (NORMALISIERTEN) Host wie der
        tatsächlich gerenderte Mail-Body — Quervergleich, keine zweite
        unabhängige Ableitung.

        GZ_PUBLIC_HOST wird bewusst MIT trailing Slash gesetzt: ein
        Health-Endpoint, der den Wert unabhängig vom gemeinsamen Helper
        selbst aus der Umgebung läse (Known Limitations, Mutation 8),
        würde den ROHEN Wert MIT Slash melden — die exakte
        Gleichheits-Assertion unten (`== _STAGING_HOST`, OHNE Slash) fällt
        dann durch. Ein reiner Teilstring-Vergleich würde das nicht fangen,
        eine exakte Gleichheit gegen den normalisierten Wert schon.

        (Korrektur nach Advisor-Review: eine ursprünglich geplante dritte
        Assertion — "der rohe Wert MIT Slash darf NICHT im Mail-Body
        vorkommen" — war in sich widersprüchlich zur zweiten Assertion:
        der normalisierte Host ist als Präfix des Deep-Links
        `{host}/trips/abc` zwangsläufig auch Präfix von `{host}/` selbst,
        jede AC-1-konforme Implementierung hätte sie also verletzt. Die
        exakte Gleichheits-Assertion unten allein diskriminiert die
        Mutation bereits vollständig — belegt: ein `os.environ.get()`-
        Bypass ohne Normalisierung liefert `.../`≠`_STAGING_HOST`.)
        """
        from fastapi.testclient import TestClient

        from api.main import app

        raw_host_with_slash = _STAGING_HOST + "/"
        monkeypatch.setenv("GZ_PUBLIC_HOST", raw_host_with_slash)
        client = TestClient(app)
        health_body = client.get("/health").json()

        settings = Settings(env="production", is_test_mode=False)
        _, report = _build_request_and_render(settings, trip_id="abc")

        assert health_body.get("public_host") == _STAGING_HOST, (
            f"AC-6: /health liefert public_host={health_body.get('public_host')!r}, "
            f"erwartet normalisiert (ohne Slash) {_STAGING_HOST!r}."
        )
        assert health_body["public_host"] in report.email_html, (
            "AC-6: der von /health gemeldete (normalisierte) Host taucht "
            "NICHT im tatsächlich gerenderten Mail-Body auf — zwei "
            "unabhängige Ableitungen statt eines gemeinsamen Helpers."
        )

    def test_health_public_host_null_when_unset(self, monkeypatch):
        """AC-7: ohne GZ_PUBLIC_HOST liefert /health public_host=null, kein Fallback."""
        from fastapi.testclient import TestClient

        from api.main import app

        monkeypatch.delenv("GZ_PUBLIC_HOST", raising=False)
        client = TestClient(app)
        body = client.get("/health").json()
        assert "public_host" in body, "AC-7: Feld public_host fehlt in der Health-Antwort."
        assert body["public_host"] is None, (
            f"AC-7: public_host sollte null sein ohne GZ_PUBLIC_HOST, war "
            f"{body['public_host']!r}."
        )
