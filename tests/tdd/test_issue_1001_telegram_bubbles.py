"""TDD RED — Feature #1001: Telegram-Ausgabe neu bauen (Multi-Bubble-Format).

SPEC: docs/specs/modules/feat_1001_telegram_redesign.md (AC-1..AC-10).

`render_telegram_bubbles()`, `TelegramBubble`, `TripReport.telegram_bubbles`,
`TripReport.telegram_actions_markup` und die `act_*`-Callback-Dispatch-Zweige
existieren noch NICHT — jeder Test hier ist im RED-Zustand rot, entweder per
ImportError/AttributeError (Funktion/Feld fehlt) oder per AssertionError
(Verhalten weicht vom Spec ab).

KEINE Mocks, KEIN Dateiinhalt-Check. Reale Fixtures + reale Funktionsaufrufe.
Live-Tests (AC-1, AC-8, AC-9-Ergänzung) senden real gegen den Staging-Bot
(`GregorZwanzigStaging_bot`, Chat 8346977700) und räumen per `delete_message`
sofort wieder auf. Die Staging-Zugangsdaten werden — falls im Environment noch
nicht gesetzt — lediglich aus `/home/hem/gregor_zwanzig_staging/.env` gesourct
(nicht kopiert), damit die Live-Tests in der RED-Phase nicht mangels Creds
stumm überspringen, sondern echt am fehlenden Feature scheitern.
"""
from __future__ import annotations

import os
import re
import shutil
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.tdd._telegram_live_fixture import live_telegram_enabled

# ---------------------------------------------------------------------------
# Live-Opt-in-Gate (Issue #1014) — kein Import-Autoload mehr, Sourcing erfolgt
# ausschließlich innerhalb von live_telegram_enabled() bei GZ_TELEGRAM_LIVE=1.
# ---------------------------------------------------------------------------

_LIVE_CREDS_AVAILABLE = live_telegram_enabled()
_TEST_CHAT_ID = os.environ.get("GZ_TELEGRAM_TEST_CHAT_ID", "")
_LIVE_SKIP_REASON = (
    "GZ_TELEGRAM_LIVE=1 nicht gesetzt — Live-Sends nur opt-in (#1014)"
)

_TZ = ZoneInfo("Europe/Vienna")


# ---------------------------------------------------------------------------
# Fixture-Helper — echte Trip-/Segment-/DisplayConfig-Objekte (kein Mock).
# Muster übernommen aus tests/tdd/test_issue_635_telegram_weather.py.
# ---------------------------------------------------------------------------


def _make_segment(
    seg_id=1, start_hour=8, end_hour=10, start_km=0.0, end_km=6.0,
    ascent=500.0, descent=0.0, thunder=None,
):
    from app.models import (
        ForecastMeta, GPXPoint, NormalizedTimeseries, Provider,
        SegmentWeatherData, SegmentWeatherSummary, ThunderLevel, TripSegment,
    )
    seg = TripSegment(
        segment_id=seg_id,
        start_point=GPXPoint(lat=42.2, lon=9.05, elevation_m=400.0, distance_from_start_km=start_km),
        end_point=GPXPoint(lat=42.25, lon=9.09, elevation_m=900.0, distance_from_start_km=end_km),
        start_time=datetime(2026, 7, 3, start_hour, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 3, end_hour, 0, tzinfo=timezone.utc),
        duration_hours=float(max(end_hour - start_hour, 0)) or 0.5,
        distance_km=max(end_km - start_km, 0.1),
        ascent_m=ascent,
        descent_m=descent,
    )
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="arome_france",
        run=datetime(2026, 7, 3, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.3, interp="point_grid",
    )
    ts = NormalizedTimeseries(meta=meta, data=[])
    agg = SegmentWeatherSummary(
        temp_min_c=12.0, temp_max_c=14.0, wind_max_kmh=8.0,
        precip_sum_mm=0.0, cloud_avg_pct=20,
        thunder_level_max=thunder if thunder is not None else ThunderLevel.NONE,
        visibility_min_m=15000,
        freezing_level_m=3200, wind_direction_avg_deg=90,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=ts, aggregated=agg,
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )


def _make_dc(metric_specs: list[tuple[str, str]], telegram_kurzform: bool = False):
    """metric_specs: Liste von (metric_id, bucket). Reihenfolge = order."""
    from app.models import MetricConfig, UnifiedWeatherDisplayConfig
    metrics = [
        MetricConfig(metric_id=mid, enabled=True, bucket=bucket, order=idx)
        for idx, (mid, bucket) in enumerate(metric_specs)
    ]
    return UnifiedWeatherDisplayConfig(
        trip_id="test-1001", metrics=metrics, telegram_kurzform=telegram_kurzform,
        updated_at=datetime.now(timezone.utc),
    )


_SUNNY_ROW = {
    "time": "08", "temp": 12, "wind": 5, "wind_dir": 90, "precip": 0.0,
    "cloud": 20, "thunder": "NONE", "visibility": 15000, "freeze_lvl": 3200,
}


# ===========================================================================
# AC-2 (strukturell, kein Netzwerk): Segment-Bubble = echte Monospace-Tabelle,
# keine _tg_segment_line-Prosa mehr, max 8 Spalten (Zeit + 7 Metriken).
# ===========================================================================


class TestAC2SegmentBubbleTable:
    def test_segment_bubble_has_real_table_with_matching_header(self):
        """AC-2: Segment-Bubble enthält eine per _narrow_table gebaute Tabelle
        mit Header 'Zt <Kürzel...>' — exakt die konfigurierten Spalten."""
        from output.renderers.narrow import _compact_label, render_telegram_bubbles

        seg = _make_segment(seg_id=1, start_hour=8, end_hour=10, start_km=0.0, end_km=6.0)
        rows = [dict(_SUNNY_ROW), {**_SUNNY_ROW, "time": "09", "temp": 14}]
        metric_ids = ["temperature", "wind", "wind_direction", "precipitation", "cloud_total"]
        dc = _make_dc([(m, "primary") for m in metric_ids])

        bubbles = render_telegram_bubbles(
            segments=[seg], seg_tables=[rows], dc=dc, report_type="morning",
            tz=_TZ, trip_name="AC2 Test",
        )
        assert isinstance(bubbles, list) and bubbles, "render_telegram_bubbles() muss eine nicht-leere Liste liefern"

        joined = "\n".join(b.text for b in bubbles)
        header_match = re.search(r"(?m)^Zt\s+(.+)$", joined)
        assert header_match, f"Tabellen-Header 'Zt ...' nicht gefunden (AC-2):\n{joined}"
        header_cols = header_match.group(1).split()
        expected_labels = [_compact_label(m) for m in metric_ids]
        assert header_cols == expected_labels, (
            f"Tabellen-Spalten stimmen nicht mit konfigurierten Metriken überein: "
            f"{header_cols} != {expected_labels}"
        )
        assert "· Wind" not in joined, (
            f"Alte _tg_segment_line-Prosa ('· Wind ...') noch vorhanden:\n{joined}"
        )

    def test_segment_table_never_exceeds_eight_columns(self):
        """AC-2: Mehr als 7 konfigurierte Primary-Metriken → Tabelle kappt bei
        7 Metrik-Spalten (+ Zeit-Spalte = 8 Gesamt-Spalten)."""
        from output.renderers.narrow import render_telegram_bubbles

        seg = _make_segment(seg_id=1)
        rows = [dict(_SUNNY_ROW)]
        metric_ids = [
            "temperature", "wind", "wind_direction", "precipitation",
            "thunder", "cloud_total", "visibility", "freezing_level", "gust",
        ]
        dc = _make_dc([(m, "primary") for m in metric_ids])

        bubbles = render_telegram_bubbles(
            segments=[seg], seg_tables=[rows], dc=dc, report_type="morning",
            tz=_TZ, trip_name="AC2 Overflow",
        )
        joined = "\n".join(b.text for b in bubbles)
        header_match = re.search(r"(?m)^Zt\s+(.+)$", joined)
        assert header_match, f"Tabellen-Header nicht gefunden:\n{joined}"
        header_cols = header_match.group(1).split()
        assert len(header_cols) <= 7, (
            f"Segment-Tabelle darf max. 7 Metrik-Spalten (+Zeit=8) haben, waren {len(header_cols)}: {header_cols}"
        )


# ===========================================================================
# AC-3 (strukturell, kein Netzwerk): Kurzübersicht-Bubble = ALLE konfigurierten
# Metriken, unabhängig vom 8-Spalten-Limit und unabhängig von telegram_kurzform.
# ===========================================================================


class TestAC3KurzuebersichtAlleMetriken:
    def test_all_ten_metrics_in_overview_bubble_regardless_of_kurzform_flag(self):
        from output.renderers.narrow import _compact_label, render_telegram_bubbles

        seg = _make_segment(seg_id=1)
        rows = [dict(_SUNNY_ROW)]
        metric_ids = [
            "temperature", "wind", "wind_direction", "precipitation", "thunder",
            "cloud_total", "visibility", "freezing_level", "gust", "uv_index",
        ]
        assert len(metric_ids) > 8, "Testvoraussetzung: mehr als 8 Metriken"

        for kurzform_flag in (False, True):
            dc = _make_dc([(m, "primary") for m in metric_ids], telegram_kurzform=kurzform_flag)
            bubbles = render_telegram_bubbles(
                segments=[seg], seg_tables=[rows], dc=dc, report_type="morning",
                tz=_TZ, trip_name="AC3 Test",
            )
            assert len(bubbles) >= 2, (
                f"Erwarte mindestens Kopf+Kurzübersicht-Bubble (kurzform={kurzform_flag}), "
                f"waren {len(bubbles)}"
            )
            # Bubble-Reihenfolge lt. Spec: [0]=Kopf, [1]=Kurzübersicht.
            overview_text = bubbles[1].text
            missing = [
                m for m in metric_ids if _compact_label(m) not in overview_text
            ]
            assert not missing, (
                f"Kurzübersicht-Bubble (kurzform={kurzform_flag}) fehlt Kürzel für: "
                f"{[_compact_label(m) for m in missing]}\n{overview_text}"
            )


# ===========================================================================
# AC-6 (Regression, strukturell): Kopf-Bubble erhält Trip-Name/Report-Typ/Datum
# — dieselbe Information, die 'report morning'/'report evening' bisher über den
# Header transportierten, bleibt erhalten (kein Bruch für nachgelagerte
# Text-Befehls-Konsumenten).
# ===========================================================================


class TestAC6RegressionHeaderPreserved:
    def test_kopf_bubble_contains_tripname_reporttype_and_date(self):
        from output.renderers.narrow import render_telegram_bubbles

        seg = _make_segment(seg_id=1, start_hour=8, end_hour=10)
        rows = [dict(_SUNNY_ROW)]
        dc = _make_dc([("temperature", "primary")])

        bubbles = render_telegram_bubbles(
            segments=[seg], seg_tables=[rows], dc=dc, report_type="morning",
            tz=_TZ, trip_name="KHW Regression 403",
        )
        assert bubbles, "render_telegram_bubbles() lieferte keine Bubbles"
        kopf = bubbles[0].text
        assert "KHW Regression 403" in kopf, f"Trip-Name fehlt im Kopf-Bubble: {kopf!r}"
        assert "Morning" in kopf, f"Report-Typ fehlt im Kopf-Bubble: {kopf!r}"
        assert "03.07.2026" in kopf, f"Datum fehlt im Kopf-Bubble: {kopf!r}"


# ===========================================================================
# AC-10 (strukturell, kein Netzwerk): telegram_kurzform beeinflusst die
# Bubble-Liste NICHT mehr — Feld ist wirkungslos (Altdaten-Kompatibilität).
# ===========================================================================


class TestAC10KurzformFlagWirkungslos:
    def test_bubble_lists_identical_for_both_flag_values(self):
        from output.renderers.narrow import render_telegram_bubbles

        seg = _make_segment(seg_id=1)
        rows = [dict(_SUNNY_ROW)]
        dc_false = _make_dc([("temperature", "primary"), ("wind", "primary")], telegram_kurzform=False)
        dc_true = _make_dc([("temperature", "primary"), ("wind", "primary")], telegram_kurzform=True)

        bubbles_false = render_telegram_bubbles(
            segments=[seg], seg_tables=[rows], dc=dc_false, report_type="morning",
            tz=_TZ, trip_name="AC10 Test",
        )
        bubbles_true = render_telegram_bubbles(
            segments=[seg], seg_tables=[rows], dc=dc_true, report_type="morning",
            tz=_TZ, trip_name="AC10 Test",
        )
        texts_false = [b.text for b in bubbles_false]
        texts_true = [b.text for b in bubbles_true]
        assert texts_false == texts_true, (
            f"telegram_kurzform darf das Rendering-Ergebnis nicht beeinflussen "
            f"(AC-10):\nfalse={texts_false}\ntrue={texts_true}"
        )


# ===========================================================================
# AC-9 (strukturell, kein Netzwerk): _TG_TABLE_WIDTH begrenzt jede
# Tabellenzeile hart.
# ===========================================================================


class TestAC9TableWidthLimitStructural:
    def test_segment_table_lines_respect_tg_table_width(self):
        from output.renderers import narrow

        seg = _make_segment(seg_id=1, start_hour=14, end_hour=16)
        # Extremwerte + 7 Metriken (max. Spaltenanzahl) provozieren die breitest
        # mögliche Tabellenzeile.
        row = {
            "time": "14", "temp": -12, "wind": 95, "wind_dir": 225,
            "precip": 23.7, "thunder": "HIGH", "cloud": 100, "visibility": 200,
        }
        metric_ids = ["temperature", "wind", "wind_direction", "precipitation", "thunder", "cloud_total", "visibility"]
        dc = _make_dc([(m, "primary") for m in metric_ids])

        bubbles = narrow.render_telegram_bubbles(
            segments=[seg], seg_tables=[[row]], dc=dc, report_type="morning",
            tz=_TZ, trip_name="AC9 Test",
        )
        all_lines = [ln for b in bubbles for ln in b.text.splitlines()]
        table_lines = [ln for ln in all_lines if ln.startswith("Zt") or re.match(r"^\d{2}\s", ln)]
        assert table_lines, f"Keine Tabellenzeilen im Rendering gefunden:\n{all_lines}"

        assert hasattr(narrow, "_TG_TABLE_WIDTH"), "narrow._TG_TABLE_WIDTH (AC-9-Konstante) fehlt"
        overlong = [ln for ln in table_lines if len(ln) > narrow._TG_TABLE_WIDTH]
        assert not overlong, (
            f"Zeile(n) über _TG_TABLE_WIDTH={getattr(narrow, '_TG_TABLE_WIDTH', '?')}:\n"
            + "\n".join(f"  [{len(l)}] {l!r}" for l in overlong)
        )


# ===========================================================================
# AC-5 (Vorstufe, strukturell): TripReport-DTO muss telegram_bubbles /
# telegram_actions_markup tragen, damit der Scheduler pro Bubble senden und
# bei Fehlschlag abbrechen kann.
# ===========================================================================


class TestAC5ReportCarriesBubbleFields:
    def test_tripreport_accepts_telegram_bubbles_and_actions_markup(self):
        """AC-5 (Vorstufe): TripReport MUSS telegram_bubbles/telegram_actions_markup
        als Konstruktor-Felder akzeptieren. Heute (RED) existieren beide Felder
        nicht auf der Dataclass -> TypeError beim Konstruieren mit diesen Keywords."""
        from app.models import TripReport

        report = TripReport(
            trip_id="t", trip_name="T", report_type="morning",
            generated_at=datetime.now(timezone.utc), segments=[],
            email_subject="s", email_html="h", email_plain="p",
            telegram_bubbles=["a", "b", "c"],
            telegram_actions_markup=None,
        )
        assert report.telegram_bubbles == ["a", "b", "c"]
        assert report.telegram_actions_markup is None


@pytest.mark.skipif(not _LIVE_CREDS_AVAILABLE, reason=_LIVE_SKIP_REASON)
class TestAC5LiveAbortAfterFirstFailure:
    def test_break_after_first_failed_bubble_no_partial_retry(self):
        """AC-5: Sobald render_telegram_bubbles() existiert, muss ein
        Fehlschlag beim Senden einer Bubble den Rest der Sequenz stoppen.
        Diese Testversion treibt render_telegram_bubbles() echt und simuliert
        den in der Spec dokumentierten Scheduler-Loop 1:1 gegen echte
        TelegramOutput.send()-Aufrufe (echter Erfolg + echter Fehlschlag via
        kaputtem Bot-Token) — bis render_telegram_bubbles() existiert,
        schlägt bereits der Aufbau (ImportError) fehl."""
        from app.config import Settings
        from output.renderers.narrow import render_telegram_bubbles
        from outputs.base import OutputError
        from outputs.telegram import TelegramOutput

        seg1 = _make_segment(seg_id=1, start_hour=8, end_hour=10, start_km=0.0, end_km=6.0)
        seg2 = _make_segment(seg_id=2, start_hour=10, end_hour=12, start_km=6.0, end_km=11.0)
        rows = [dict(_SUNNY_ROW)]
        dc = _make_dc([("temperature", "primary"), ("wind", "primary")])

        bubbles = render_telegram_bubbles(
            segments=[seg1, seg2], seg_tables=[rows, rows], dc=dc,
            report_type="morning", tz=_TZ, trip_name="AC5 Live Abort Test",
        )
        assert len(bubbles) >= 3, f"Erwarte mindestens 3 Bubbles, waren {len(bubbles)}"

        good_settings = Settings(
            telegram_bot_token=os.environ["GZ_TELEGRAM_BOT_TOKEN"],
            telegram_chat_id=_TEST_CHAT_ID,
        )
        bad_settings = Settings(
            telegram_bot_token="000000000:AAInvalidTokenXXXXXXXXXXXXXXXXXXXXX",
            telegram_chat_id=_TEST_CHAT_ID,
        )

        sent_ids: list[int] = []
        failed_at = None
        try:
            for i, b in enumerate(bubbles):
                settings = good_settings if i == 0 else bad_settings
                out = TelegramOutput(settings)
                try:
                    mid = out.send(
                        subject="AC5", body=b.text, reply_markup=b.reply_markup,
                        parse_mode="HTML", suppress_subject_line=True,
                    )
                    sent_ids.append(mid)
                except OutputError:
                    failed_at = i
                    break
        finally:
            cleanup_out = TelegramOutput(good_settings)
            for mid in sent_ids:
                if mid:
                    cleanup_out.delete_message(chat_id=_TEST_CHAT_ID, message_id=mid)

        assert failed_at == 1, f"Erwartete Abbruch bei Bubble-Index 1 (2. Bubble), war: {failed_at}"
        assert len(sent_ids) == 1, f"Nur die erste Bubble sollte zugestellt worden sein, waren {len(sent_ids)}"


# ===========================================================================
# AC-4: act_*-Callback (Aktionen-Bubble) muss auf denselben Processor-Body
# mappen wie der bestehende Text-Befehl — realer Roundtrip über
# InboundTelegramReader._callback_to_body() + TripCommandProcessor (kein Mock,
# lokale Trip-Persistenz statt Netzwerk-Zustellung).
# ===========================================================================

_AC4_USER = "tdd-1001-act4"
_AC4_TRIP_ID = "act4-trip-1001"
_AC4_TRIP_NAME = "AC4 Trip 1001"


def _make_ac4_trip():
    from app.models import TripReportConfig
    from app.trip import Stage, Trip, Waypoint

    wp = Waypoint(id="W1", name="A", lat=47.0, lon=11.0, elevation_m=800)
    stage = Stage(id="S1", name="Tag 1", date=date(2026, 7, 10), waypoints=[wp])
    rc = TripReportConfig(trip_id=_AC4_TRIP_ID)
    return Trip(id=_AC4_TRIP_ID, name=_AC4_TRIP_NAME, stages=[stage], report_config=rc)


@pytest.fixture
def _clean_ac4_user():
    from app.loader import get_trips_dir
    d = get_trips_dir(_AC4_USER)
    shutil.rmtree(d, ignore_errors=True)
    yield
    shutil.rmtree(d, ignore_errors=True)


class TestAC4CallbackPauseRoundtrip:
    def test_act_pause_callback_body_matches_text_pause_result(self, _clean_ac4_user):
        from app.loader import save_trip
        from services.inbound_telegram_reader import InboundTelegramReader
        from services.trip_command_processor import InboundMessage, TripCommandProcessor

        save_trip(_make_ac4_trip(), _AC4_USER)

        reader = InboundTelegramReader()
        body = reader._callback_to_body("act_pause")
        assert body is not None, (
            "AC-4: 'act_pause' muss über _callback_to_body() auf einen "
            "Processor-Body gemappt werden (analog zum bestehenden "
            "_CALLBACK_QUERY_MAP-Dispatch) — heute liefert "
            "_callback_to_body('act_pause') None (unbekannter Callback)."
        )

        msg_callback = InboundMessage(
            channel="telegram", trip_name=_AC4_TRIP_NAME, body=body,
            sender="8346977700", received_at=datetime(2026, 7, 10, 8, 0, tzinfo=timezone.utc),
            user_id=_AC4_USER,
        )
        result_callback = TripCommandProcessor().process(msg_callback)

        # Referenzverhalten: derselbe Trip-Zustand, bare Text-Befehl "pause".
        save_trip(_make_ac4_trip(), _AC4_USER)
        msg_text = InboundMessage(
            channel="telegram", trip_name=_AC4_TRIP_NAME, body="### pause",
            sender="8346977700", received_at=datetime(2026, 7, 10, 8, 0, tzinfo=timezone.utc),
            user_id=_AC4_USER,
        )
        result_text = TripCommandProcessor().process(msg_text)

        assert result_callback.success == result_text.success, (
            f"'act_pause'-Callback-Ergebnis weicht vom Text-Befehl 'pause' ab "
            f"(AC-4): callback.success={result_callback.success} != "
            f"text.success={result_text.success}"
        )


# ===========================================================================
# AC-7: GET /api/preview/{trip}/telegram liefert zusätzlich bubbles: list[str]
# neben dem bestehenden body-Feld (additiv, rückwärtskompatibel).
# ===========================================================================

_AC7_TRIP_ID = "gr221-mallorca"


@pytest.fixture
def _ac7_client():
    from api.routers import preview
    app = FastAPI()
    app.include_router(preview.router)
    return TestClient(app)


class TestAC7PreviewEndpointBubbles:
    def test_telegram_preview_endpoint_returns_bubbles_alongside_body(self, _ac7_client):
        resp = _ac7_client.get(
            f"/api/preview/{_AC7_TRIP_ID}/telegram",
            params={"type": "evening", "user_id": "default"},
        )
        assert resp.status_code in (200, 503), (
            f"Erwarte 200 oder 503, bekam {resp.status_code}: {resp.text[:200]}"
        )
        if resp.status_code != 200:
            pytest.skip("Wetter-API nicht erreichbar (503)")

        data = resp.json()
        assert "body" in data and isinstance(data["body"], str) and data["body"], (
            "Rückwärtskompatibles 'body'-Feld fehlt oder ist leer"
        )
        assert "bubbles" in data, (
            "AC-7: Antwort muss zusätzlich 'bubbles': list[str] enthalten"
        )
        bubbles = data["bubbles"]
        assert isinstance(bubbles, list) and bubbles, f"'bubbles' muss eine nicht-leere Liste sein: {bubbles!r}"
        for b in bubbles:
            assert isinstance(b, str) and b
        for b in bubbles:
            assert b in data["body"], (
                f"'body' muss die getrennt verbundenen Bubbles enthalten — "
                f"Bubble fehlt im body: {b[:60]!r}"
            )

    def test_preview_service_render_telegram_preview_returns_bubbles(self):
        from app.config import Settings
        from services.preview_service import PreviewService

        service = PreviewService(Settings())
        try:
            subject, body, bubbles = service.render_telegram_preview(
                _AC7_TRIP_ID, user_id="default", report_type="evening",
            )
        except RuntimeError:
            pytest.skip("Wetter-API nicht erreichbar")
        assert isinstance(subject, str)
        assert isinstance(body, str) and body
        assert isinstance(bubbles, list) and bubbles


# ===========================================================================
# AC-1 (Live): Scheduler-Multi-Send — mehrere sendMessage-Aufrufe mit eigener
# message_id statt einer einzigen Nachricht.
# ===========================================================================


@pytest.mark.skipif(not _LIVE_CREDS_AVAILABLE, reason=_LIVE_SKIP_REASON)
class TestAC1LiveMultiBubbleDelivery:
    def test_real_send_produces_at_least_five_distinct_message_ids(self):
        from app.config import Settings
        from output.renderers.narrow import render_telegram_bubbles
        from outputs.telegram import TelegramOutput

        seg1 = _make_segment(seg_id=1, start_hour=8, end_hour=10, start_km=0.0, end_km=6.0)
        seg2 = _make_segment(seg_id=2, start_hour=10, end_hour=12, start_km=6.0, end_km=11.0)
        ziel = _make_segment(seg_id="Ziel", start_hour=12, end_hour=12, start_km=11.0, end_km=11.0)
        rows = [dict(_SUNNY_ROW)]
        dc = _make_dc([("temperature", "primary"), ("wind", "primary")])

        bubbles = render_telegram_bubbles(
            segments=[seg1, seg2, ziel], seg_tables=[rows, rows, rows],
            dc=dc, report_type="morning", tz=_TZ, trip_name="AC1 Live E2E 1001",
        )
        assert len(bubbles) >= 5, f"AC-1 verlangt mindestens 5 Bubbles, waren {len(bubbles)}"

        settings = Settings(
            telegram_bot_token=os.environ["GZ_TELEGRAM_BOT_TOKEN"],
            telegram_chat_id=_TEST_CHAT_ID,
        )
        out = TelegramOutput(settings)
        sent_ids: list[int] = []
        try:
            for b in bubbles:
                mid = out.send(
                    subject="AC1 Live", body=b.text, reply_markup=b.reply_markup,
                    parse_mode="HTML", suppress_subject_line=True,
                )
                assert mid is not None, f"Bubble ohne message_id (Zustellung fehlgeschlagen): {b.text[:80]!r}"
                sent_ids.append(mid)
            assert len(sent_ids) == len(bubbles)
            assert len(set(sent_ids)) == len(sent_ids), "message_ids müssen eindeutig sein (separate Nachrichten)"
        finally:
            for mid in sent_ids:
                out.delete_message(chat_id=_TEST_CHAT_ID, message_id=mid)


# ===========================================================================
# AC-8 (Live): Sonderzeichen (&, <, >) im Segment-Mini-Header überleben den
# echten HTML-Versand (kein 400-Parse-Fehler, korrekt escaped).
# ===========================================================================


@pytest.mark.skipif(not _LIVE_CREDS_AVAILABLE, reason=_LIVE_SKIP_REASON)
class TestAC8LiveHtmlEscaping:
    def test_special_chars_survive_real_html_send(self):
        from app.config import Settings
        from output.renderers.narrow import render_telegram_bubbles
        from outputs.telegram import TelegramOutput

        seg = _make_segment(seg_id=1, start_hour=8, end_hour=10)
        rows = [dict(_SUNNY_ROW)]
        dc = _make_dc([("temperature", "primary"), ("wind", "primary")])

        bubbles = render_telegram_bubbles(
            segments=[seg], seg_tables=[rows], dc=dc, report_type="morning",
            tz=_TZ, trip_name="A & B <Test>",
        )
        assert bubbles, "render_telegram_bubbles() lieferte keine Bubbles"
        kopf = bubbles[0].text
        assert "&lt;Test&gt;" in kopf, f"'<Test>' nicht als &lt;/&gt; escaped (AC-8): {kopf!r}"
        assert "&amp;" in kopf, f"'&' nicht als &amp; escaped (AC-8): {kopf!r}"

        settings = Settings(
            telegram_bot_token=os.environ["GZ_TELEGRAM_BOT_TOKEN"],
            telegram_chat_id=_TEST_CHAT_ID,
        )
        out = TelegramOutput(settings)
        mid = out.send(
            subject="AC8", body=kopf, parse_mode="HTML", suppress_subject_line=True,
        )
        try:
            assert mid is not None, "HTML-Parse-Fehler oder Zustellung fehlgeschlagen (AC-8)"
        finally:
            if mid:
                out.delete_message(chat_id=_TEST_CHAT_ID, message_id=mid)


# ===========================================================================
# AC-9 (Live-Ergänzung): Segment-Tabelle mit max. 8 Spalten real verschickt.
# ===========================================================================


@pytest.mark.skipif(not _LIVE_CREDS_AVAILABLE, reason=_LIVE_SKIP_REASON)
class TestAC9LiveTableSend:
    def test_max_column_table_real_send_succeeds(self):
        from app.config import Settings
        from output.renderers.narrow import render_telegram_bubbles
        from outputs.telegram import TelegramOutput

        seg = _make_segment(seg_id=1, start_hour=14, end_hour=16)
        row = {
            "time": "14", "temp": -12, "wind": 95, "wind_dir": 225,
            "precip": 23.7, "thunder": "HIGH", "cloud": 100, "visibility": 200,
        }
        metric_ids = ["temperature", "wind", "wind_direction", "precipitation", "thunder", "cloud_total", "visibility"]
        dc = _make_dc([(m, "primary") for m in metric_ids])

        bubbles = render_telegram_bubbles(
            segments=[seg], seg_tables=[[row]], dc=dc, report_type="morning",
            tz=_TZ, trip_name="AC9 Live Test",
        )
        segment_bubble = next(
            (b for b in bubbles if re.search(r"(?m)^Zt\s", b.text)), None,
        )
        assert segment_bubble is not None, "Keine Tabellen-Bubble gefunden (AC-9)"

        settings = Settings(
            telegram_bot_token=os.environ["GZ_TELEGRAM_BOT_TOKEN"],
            telegram_chat_id=_TEST_CHAT_ID,
        )
        out = TelegramOutput(settings)
        mid = out.send(
            subject="AC9", body=segment_bubble.text, parse_mode="HTML",
            suppress_subject_line=True,
        )
        try:
            assert mid is not None, "Zustellung der Max-Spalten-Tabelle fehlgeschlagen (AC-9)"
        finally:
            if mid:
                out.delete_message(chat_id=_TEST_CHAT_ID, message_id=mid)


# ===========================================================================
# F001-Regression (Adversary Fix-Runde 1): Kurzübersicht-Gewitterzeile muss
# den Tages-Schlimmstwert zeigen (analog _tg_day_footer()), nicht den zuletzt
# beobachteten Wert — sonst widersprechen sich Kurzübersicht und Fußzeile in
# derselben Bubble.
# ===========================================================================


class TestF001OverviewThunderMatchesFooterWorstValue:
    def test_overview_thunder_line_shows_worst_not_last_segment(self):
        """Reproduziert die Adversary-Fundstelle 1:1: Vormittag HIGH, Nachmittag
        NONE (letztes Segment) → Kurzübersicht muss trotzdem HIGH zeigen, wie
        die Fußzeile es bereits (korrekt) tut."""
        from app.models import ThunderLevel
        from output.renderers.narrow import render_telegram_bubbles

        seg_morning = _make_segment(
            seg_id=1, start_hour=8, end_hour=10, start_km=0.0, end_km=6.0,
            thunder=ThunderLevel.HIGH,
        )
        seg_afternoon = _make_segment(
            seg_id=2, start_hour=14, end_hour=16, start_km=6.0, end_km=12.0,
            thunder=ThunderLevel.NONE,
        )
        rows_morning = [{**_SUNNY_ROW, "time": "08", "thunder": "HIGH"}]
        rows_afternoon = [{**_SUNNY_ROW, "time": "14", "thunder": "NONE"}]
        dc = _make_dc([("temperature", "primary"), ("thunder", "primary")])

        bubbles = render_telegram_bubbles(
            segments=[seg_morning, seg_afternoon],
            seg_tables=[rows_morning, rows_afternoon],
            dc=dc, report_type="morning", tz=_TZ, trip_name="F001 Regression",
        )
        assert len(bubbles) >= 2, f"Erwarte mindestens Kopf+Kurzübersicht, waren {len(bubbles)}"
        overview_text = bubbles[1].text

        thunder_lines = [ln for ln in overview_text.splitlines() if ln.startswith("⚡")]
        assert thunder_lines, f"Keine Gewitter-Zeile (⚡) in der Kurzübersicht-Bubble:\n{overview_text}"

        # Die ERSTE ⚡-Zeile ist die _overview_line("thunder", ...)-Zeile — genau
        # die Stelle des F001-Bugs (`hits[-1]` statt Tages-Schlimmstwert). Bei
        # Symbol-Modus (Default, kein format_mode="raw") rendert HIGH als "⚡⚡"
        # (siehe email/helpers.py fmt_val key=="thunder"), NONE als "–".
        overview_thunder_line = thunder_lines[0]
        assert "⚡⚡" in overview_thunder_line, (
            f"F001-Regression: Kurzübersicht-Gewitterzeile zeigt nicht das "
            f"HIGH-Symbol '⚡⚡' (Tages-Schlimmstwert), sondern {overview_thunder_line!r} "
            f"(vermutlich den zuletzt beobachteten Wert 'NONE'/'–' des letzten "
            f"Segments statt des Tages-Schlimmstwerts). Ganze Bubble:\n{overview_text}"
        )
        assert overview_thunder_line.strip() != "⚡ –", (
            f"Widerspruch (F001): Kurzübersicht zeigt 'kein Gewitter' (–), "
            f"obwohl ein Segment HIGH meldete: {overview_thunder_line!r}"
        )

        # Widerspruchsfreiheit: Fußzeile (dritte ⚡-Zeile, _tg_day_footer) UND
        # Kurzübersicht-Zeile müssen dieselbe Tagesaussage treffen — beide
        # "etwas" (nicht "kein Gewitter") melden, nicht eine "kein" und die
        # andere "HIGH" (die ursprüngliche Adversary-Klage).
        footer_thunder_line = next((ln for ln in thunder_lines if "Sicht" in ln), None)
        assert footer_thunder_line is not None, f"Keine Fußzeile mit ⚡ gefunden: {thunder_lines}"
        assert "HIGH" in footer_thunder_line, f"Fußzeile zeigt nicht HIGH: {footer_thunder_line!r}"
        overview_says_none = overview_thunder_line.strip() == "⚡ –"
        footer_says_none = "kein" in footer_thunder_line
        assert not (overview_says_none and not footer_says_none), (
            f"Widersprüchliche Gewitter-Aussagen in derselben Bubble: "
            f"overview={overview_thunder_line!r} footer={footer_thunder_line!r}"
        )


# ===========================================================================
# F002-Regression (Adversary Fix-Runde 1): "📊 Spalten"-Button (act_columns)
# darf kein toter Button mehr sein — echter Callback-Roundtrip muss einen
# informativen Antworttext liefern statt eines stillen No-Ops.
# ===========================================================================


class TestF002ActColumnsCallbackNoLongerDead:
    def test_act_columns_callback_maps_to_body_and_returns_informative_result(self):
        from services.inbound_telegram_reader import InboundTelegramReader
        from services.trip_command_processor import InboundMessage, TripCommandProcessor

        reader = InboundTelegramReader()
        body = reader._callback_to_body("act_columns")
        assert body is not None, (
            "F002-Regression: 'act_columns' muss über _callback_to_body() auf "
            "einen Processor-Body gemappt werden — vorher lieferte es None "
            "(unbekannter Callback), wodurch der Button beim Klick sichtbar "
            "nichts tat."
        )

        msg = InboundMessage(
            channel="telegram", trip_name="F002 Test", body=body,
            sender="8346977700", received_at=datetime(2026, 7, 3, 8, 0, tzinfo=timezone.utc),
            user_id="tdd-1001-f002",
        )
        result = TripCommandProcessor().process(msg)
        assert result.success is True, (
            f"'act_columns'-Callback muss eine erfolgreiche, informative Antwort "
            f"liefern (kein stiller Fehlschlag): {result}"
        )
        assert result.confirmation_body, "Antworttext für 'act_columns' darf nicht leer sein"
        assert "Trip-Editor" in result.confirmation_body or "Spalten" in result.confirmation_body, (
            f"Antworttext sollte auf die Spalten-Konfiguration im Trip-Editor "
            f"hinweisen: {result.confirmation_body!r}"
        )


# ===========================================================================
# F003-Regression (Adversary Fix-Runde 1): Briefing-Log darf "telegram" nicht
# als vollständig gesendet verzeichnen, wenn die Bubble-Sendeschleife wegen
# eines echten Fehlschlags (ungültiger Bot-Token) abgebrochen wurde.
# ===========================================================================

_F003_USER = "tdd-1001-f003"
_F003_TRIP_ID = "f003-trip-1001"


def _f003_waypoints():
    return [
        {"id": "wp1", "name": "Calenzana", "lat": 42.508, "lon": 8.857, "elevation_m": 275},
        {"id": "wp2", "name": "Ortu di u Piobbu", "lat": 42.406, "lon": 8.877, "elevation_m": 1530},
    ]


@pytest.fixture
def _f003_trip_and_log():
    import json as _json
    from datetime import timedelta

    from app.loader import get_trips_dir

    trips_dir = get_trips_dir(_F003_USER)
    trips_dir.mkdir(parents=True, exist_ok=True)
    future = (date.today() + timedelta(days=5)).isoformat()
    trip_path = trips_dir / f"{_F003_TRIP_ID}.json"
    trip_path.write_text(_json.dumps({
        "id": _F003_TRIP_ID,
        "name": "F003 Regression Trip",
        "stages": [
            {"id": "st1", "name": "Etappe 1", "date": future, "waypoints": _f003_waypoints()},
        ],
        "report_config": {
            "trip_id": _F003_TRIP_ID,
            "send_email": False, "send_sms": False, "send_telegram": True,
        },
        "alert_rules": [],
    }))
    log_path = Path(f"data/users/{_F003_USER}/briefing_log.json")
    log_path.unlink(missing_ok=True)
    yield trip_path, log_path
    trip_path.unlink(missing_ok=True)
    log_path.unlink(missing_ok=True)


@pytest.mark.skipif(not _LIVE_CREDS_AVAILABLE, reason=_LIVE_SKIP_REASON)
class TestF003BriefingLogOmitsTelegramOnLoopAbort:
    def test_broken_token_aborts_send_loop_and_log_omits_telegram(self, _f003_trip_and_log):
        """F003-Regression: Ein echter Sendefehlschlag (ungültiger Bot-Token)
        bricht die Bubble-Schleife bereits bei der ersten Nachricht ab (AC-5)
        — das Briefing-Log darf 'telegram' dann NICHT als gesendeten Kanal
        verzeichnen (vorher: unbedingtes Anhängen, unabhängig vom
        Schleifenerfolg)."""
        import json as _json

        from app.config import Settings
        from app.loader import load_trip
        from services.trip_report_scheduler import TripReportSchedulerService

        trip_path, log_path = _f003_trip_and_log
        trip = load_trip(trip_path)
        assert trip is not None, "F003-Fixture-Trip konnte nicht geladen werden"

        bad_settings = Settings(
            telegram_bot_token="000000000:AAInvalidTokenXXXXXXXXXXXXXXXXXXXXX",
            telegram_chat_id=_TEST_CHAT_ID,
        )
        service = TripReportSchedulerService(settings=bad_settings, user_id=_F003_USER)
        sent = service.send_test_report(trip, "morning")
        assert sent is True, (
            f"send_test_report() soll True liefern (Report wurde generiert, "
            f"Telegram-Fehlschlag wird intern abgefangen), war {sent}"
        )

        assert log_path.exists(), "briefing_log.json wurde nicht geschrieben"
        entries = _json.loads(log_path.read_text())["entries"]
        assert entries, "Kein Briefing-Log-Eintrag geschrieben"
        last = entries[-1]
        assert last["trip_id"] == _F003_TRIP_ID
        assert "telegram" not in last["channels"], (
            f"F003-Regression: Briefing-Log verzeichnet 'telegram' als "
            f"vollständig gesendet, obwohl die Sendeschleife beim ersten "
            f"Fehlschlag (ungültiger Bot-Token) abgebrochen wurde: "
            f"{last['channels']}"
        )
