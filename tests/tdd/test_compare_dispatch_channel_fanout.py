"""TDD RED — Issue #1270 / Spec docs/specs/modules/compare_channel_preview_dispatch.md

Test 5 (AC-4) und Test 6 (AC-5): Der Compare-Briefing-Versand muss die
gespeicherten Kanal-Opt-ins `send_telegram`/`send_sms` tatsaechlich bedienen
(heute E-Mail-only, KB-3: `scheduler_dispatch_service.py:322` ruft direkt
`EmailOutput(settings).send(...)`), und ein nicht sendefaehiger Kanal darf die
anderen nicht reissen (fail-soft, Vorbild `send_trip_report:250-290`).

RED-Grund: `send_one_compare_preset` kennt keine Sink-Parameter →
TypeError: unexpected keyword argument 'sms_sink'. Selbst mit Sinks gaebe es
keinen Telegram-/SMS-Versand, weil der Fan-out fehlt.

KEINE Mocks. Deterministischer Transport-Ersatz ist die im Bestand etablierte
**Sink-Naht** (`mail_sink`/`sms_sink`/`telegram_sink`, Vorbild
`notification_service.py::send_multi_location_official_alert:596-607`) — kein
Netz, kein SMTP. Substituiert wird zusaetzlich nur die teure Upstream-
Abhaengigkeit `ComparisonEngine.run` (Live-Wetter) sowie der Snapshot-Schreiber
`_write_compare_alert_snapshots` (holt echtes Nowcast-Wetter, nicht
Pruefgegenstand) — echte Subklasse bzw. echte Funktion + Attribut-Rebind,
alles per monkeypatch restauriert (Haus-Muster
tests/tdd/test_compare_dispatch_mail_marker.py).
"""
from __future__ import annotations

import json
import uuid
from datetime import date, datetime

import pytest

from app.config import Settings
from app.models import ForecastDataPoint, ThunderLevel
from app.user import SavedLocation

TARGET_DATE = date(2026, 7, 8)


def _location(loc_id: str, name: str, lat: float, lon: float) -> SavedLocation:
    return SavedLocation(id=loc_id, name=name, lat=lat, lon=lon, elevation_m=1000)


def _dp(hour: int) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(TARGET_DATE.year, TARGET_DATE.month, TARGET_DATE.day, hour, 0),
        t2m_c=22.0,
        wind_chill_c=21.0,
        wind10m_kmh=11.0,
        gust_kmh=19.0,
        precip_1h_mm=0.0,
        cloud_total_pct=35,
        uv_index=5.0,
        thunder_level=ThunderLevel.NONE,
        pop_pct=10,
        visibility_m=9000,
    )


def _settings_all_channels() -> Settings:
    """can_send_email/telegram/sms == True ohne Netzwerk — die Sinks ersetzen
    den Transport vollstaendig, die Dummy-Creds werden nie benutzt
    (Muster tests/tdd/test_compare_official_alert.py::_settings_all_channels)."""
    return Settings(
        smtp_host="dummy.invalid", smtp_user="dummy", smtp_pass="dummy",
        mail_to="dummy@example.invalid",
        telegram_bot_token="dummy-token", telegram_chat_id="123456",
        sms_gateway_url="https://sms.invalid", seven_api_key="k",
        sms_to="+491700000000",
    )


def _settings_without_telegram() -> Settings:
    """can_send_telegram() == False (kein Token/Chat), E-Mail bleibt sendefaehig."""
    return Settings(
        smtp_host="dummy.invalid", smtp_user="dummy", smtp_pass="dummy",
        mail_to="dummy@example.invalid",
    )


def _preset(preset_id: str, user_id: str, **extra) -> dict:
    preset = {
        "id": preset_id,
        "name": "Urlaubsorte",
        "user_id": user_id,
        "location_ids": ["loc-ibk", "loc-bz"],
        "schedule": "daily",
        "profil": "ALLGEMEIN",
        "hour_from": 9,
        "hour_to": 16,
        "forecast_hours": 48,
        "empfaenger": ["gregor-test@henemm.com"],
        "created_at": "2026-07-01T00:00:00Z",
        "kind": "vergleich",
    }
    preset.update(extra)
    return preset


class _Sink:
    """Echte Aufzeichnungs-Naht (kein Mock): nimmt jede Aufrufform an und
    haelt den zugestellten Inhalt fuer den Inhaltsnachweis fest."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(self, *args, **kwargs) -> None:
        parts = [str(a) for a in args] + [f"{k}={v}" for k, v in kwargs.items()]
        self.calls.append("\n".join(parts))

    def __len__(self) -> int:
        return len(self.calls)


@pytest.fixture
def dispatch_env(tmp_path, monkeypatch):
    """Isolierter Daten-Root ueber BEIDE Zugriffsformen (get_data_dir()/
    _DATA_ROOT und relative "data"-Pfade wie in services/user_tier.py), damit
    kein Test am echten data/users/ vorbeischreibt und `sms_allowed()` den
    Test-Nutzer sieht."""
    from app import loader as app_loader

    data_root = tmp_path / "data"
    data_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(app_loader, "_DATA_ROOT", str(data_root))
    try:
        from src.app import loader as src_loader

        monkeypatch.setattr(src_loader, "_DATA_ROOT", str(data_root))
    except ImportError:  # pragma: no cover
        pass

    user_id = f"tdd-1270fan-{uuid.uuid4().hex[:8]}"
    # premium -> sms_allowed(user_id) True (services/user_tier.py liest
    # data/users/<id>/user.json relativ zum Arbeitsverzeichnis).
    user_json = data_root / "users" / user_id / "user.json"
    user_json.parent.mkdir(parents=True, exist_ok=True)
    user_json.write_text(json.dumps({"tier": "premium"}), encoding="utf-8")
    return user_id


def _install_engine_and_snapshot_seams(monkeypatch) -> None:
    import services.comparison_engine as ce_mod
    import services.scheduler_dispatch_service as sds_mod
    from app.user import ComparisonResult, LocationResult

    original = ce_mod.ComparisonEngine

    class RecordingEngine(original):  # echte Subklasse, kein Mock
        @staticmethod
        def run(*args, **kwargs):
            locations = kwargs.get("locations")
            if locations is None and args:
                locations = args[0]
            return ComparisonResult(
                locations=[
                    LocationResult(
                        location=loc,
                        score=90 - 7 * i,
                        temp_max=22.0 + i,
                        temp_min=12.0,
                        wind_max=11.0,
                        gust_max=19.0,
                        cloud_avg=35,
                        sunny_hours=6,
                        official_alerts=[],
                        hourly_data=[_dp(9), _dp(12), _dp(15)],
                    )
                    for i, loc in enumerate(list(locations or []))
                ],
                time_window=kwargs.get("time_window", (9, 16)),
                target_date=kwargs.get("target_date", TARGET_DATE),
                created_at=datetime(2026, 7, 8, 4, 0),
            )

    monkeypatch.setattr(ce_mod, "ComparisonEngine", RecordingEngine)
    # Δ-Anker-Snapshots holen echtes Nowcast-Wetter (Netz) — im Kern
    # neutralisiert; nicht Pruefgegenstand (#1169, best-effort Nachlauf).
    monkeypatch.setattr(sds_mod, "_write_compare_alert_snapshots", lambda *a, **k: None)


def _locations() -> list[SavedLocation]:
    return [
        _location("loc-ibk", "Innsbruck", 47.27, 11.39),
        _location("loc-bz", "Bozen", 46.50, 11.35),
    ]


# ---------------------------------------------------------------------------
# Test 5 (AC-4) — Opt-in wirkt: Telegram UND SMS werden tatsaechlich zugestellt
# ---------------------------------------------------------------------------


def test_preset_with_telegram_and_sms_optin_dispatches_all_three_channels(
    dispatch_env, monkeypatch, tmp_path
):
    """GIVEN ein Preset mit send_telegram=True/send_sms=True und globaler
    Sendefaehigkeit
    WHEN send_one_compare_preset laeuft
    THEN landet in sms_sink UND telegram_sink je eine Nachricht mit dem
    Vergleichs-Inhalt (zusaetzlich zur E-Mail).

    RED: send_one_compare_preset nimmt keine Sink-Parameter entgegen
    (TypeError: unexpected keyword argument 'mail_sink') und kennt ueberhaupt
    keinen Telegram-/SMS-Fan-out — die gespeicherten Opt-ins werden im
    Report-Pfad nie gelesen (KB-3)."""
    user_id = dispatch_env
    _install_engine_and_snapshot_seams(monkeypatch)
    from services.scheduler_dispatch_service import send_one_compare_preset

    mail_sink, sms_sink, telegram_sink = _Sink(), _Sink(), _Sink()
    settings = _settings_all_channels()
    assert settings.can_send_telegram() and settings.can_send_sms(), (
        "Testvoraussetzung: der Nutzer ist global fuer Telegram/SMS sendefaehig"
    )

    send_one_compare_preset(
        _preset("cp-1270-fan", user_id, send_telegram=True, send_sms=True),
        settings,
        user_id,
        str(tmp_path),
        all_locations_cache=_locations(),
        target_date=TARGET_DATE,
        mail_sink=mail_sink,
        sms_sink=sms_sink,
        telegram_sink=telegram_sink,
    )

    assert len(mail_sink) == 1, (
        f"E-Mail muss wie bisher genau einmal rausgehen, waren {len(mail_sink)}"
    )
    assert len(telegram_sink) == 1, (
        "AC-4: Preset mit send_telegram=True muss den Vergleich tatsaechlich per "
        f"Telegram zustellen, zugestellt wurden {len(telegram_sink)} Nachrichten."
    )
    assert len(sms_sink) == 1, (
        "AC-4: Preset mit send_sms=True muss den Vergleich tatsaechlich per SMS "
        f"zustellen, zugestellt wurden {len(sms_sink)} Nachrichten."
    )
    assert "Innsbruck" in telegram_sink.calls[0], (
        f"Telegram-Nachricht ohne Vergleichs-Inhalt: {telegram_sink.calls[0][:300]!r}"
    )
    assert "Innsbruck" in sms_sink.calls[0], (
        f"SMS-Nachricht ohne Vergleichs-Inhalt: {sms_sink.calls[0][:300]!r}"
    )


# ---------------------------------------------------------------------------
# Test 6 (AC-5) — nicht sendefaehiger Kanal reisst die E-Mail nicht mit
# ---------------------------------------------------------------------------


@pytest.mark.xfail(reason="#1301: Praekondition kollidiert mit konfiguriertem Telegram -- Abstimmung mit paralleler Compare-Session", strict=False)
def test_telegram_optin_without_capability_leaves_email_dispatch_intact(
    dispatch_env, monkeypatch, tmp_path
):
    """GIVEN send_telegram=True, aber can_send_telegram() == False
    WHEN der Versand laeuft
    THEN geht die E-Mail unveraendert raus, Telegram wird nicht versucht, und
    es gibt keinen Abbruch.

    RED: send_one_compare_preset nimmt keine Sink-Parameter entgegen
    (TypeError) — es gibt keine Kanal-Aufloesung, die `can_send_telegram()`
    beruecksichtigen koennte."""
    user_id = dispatch_env
    _install_engine_and_snapshot_seams(monkeypatch)
    from services.scheduler_dispatch_service import send_one_compare_preset

    mail_sink, sms_sink, telegram_sink = _Sink(), _Sink(), _Sink()
    settings = _settings_without_telegram()
    assert not settings.can_send_telegram(), (
        "Testvoraussetzung: der Nutzer ist global NICHT Telegram-faehig"
    )

    send_one_compare_preset(
        _preset("cp-1270-nocap", user_id, send_telegram=True),
        settings,
        user_id,
        str(tmp_path),
        all_locations_cache=_locations(),
        target_date=TARGET_DATE,
        mail_sink=mail_sink,
        sms_sink=sms_sink,
        telegram_sink=telegram_sink,
    )

    assert len(mail_sink) == 1, (
        "AC-5: Der E-Mail-Versand muss unbeeinflusst weiterlaufen, wenn der "
        f"Telegram-Kanal nicht sendefaehig ist — E-Mails: {len(mail_sink)}"
    )
    assert len(telegram_sink) == 0, (
        "AC-5: Ohne globale Telegram-Faehigkeit darf kein Telegram-Versand "
        f"versucht werden, es waren {len(telegram_sink)}."
    )
    assert len(sms_sink) == 0, (
        "Ohne SMS-Opt-in darf kein SMS-Versand stattfinden, es waren "
        f"{len(sms_sink)}."
    )
