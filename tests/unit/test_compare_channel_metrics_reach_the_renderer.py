"""Kanal-eigene Uebersichts-Metriken erreichen die GERENDERTE Ausgabe (#1703 S8).

Waechter fuer Mutation M2 (Spec `feat_1703_s8_compare_kanal_tabs.md`): werden die
acht kanalweisen Aufrufstellen in `scheduler_dispatch_service.py` (3) und
`compare_preview_service.py` (5) wieder mit der GEMEINSAMEN `opts.enabled_metrics`
gefuettert, zeigen alle drei Kanaele dasselbe — genau die Attrappe, die
2026-07-18 (#1287/#1291) zum Rueckbau gefuehrt hat. Ein Nachweis auf
`CompareRenderOptions` faengt das NICHT: dort ist die Mechanik korrekt, die
Wirkung haengt an der Aufrufstelle. Geprueft wird deshalb die fertige
Zeichenkette je Kanal — Pruefort == Wirkort. Deterministisch, ohne Netz/SMTP:
Transport sind die Bestands-Sinks, `ComparisonEngine.run` eine echte Subklasse,
die ihr Ergebnis AUS den uebergebenen Orten baut (Haus-Muster
`tests/tdd/test_compare_dispatch_channel_fanout.py`). Kein Mock/patch/MagicMock;
die Renderer laufen echt.
"""
from __future__ import annotations

import json
import uuid
from datetime import date, datetime

import pytest

from app.config import Settings
from app.models import ForecastDataPoint, ThunderLevel
from app.user import ComparisonResult, LocationResult, SavedLocation
from tests.helpers.compare_briefings import write_compare_briefings

TARGET_DATE = date(2026, 7, 8)
LOCATION = SavedLocation(id="loc-ibk", name="Innsbruck", lat=47.27, lon=11.39, elevation_m=574)
# Grundauswahl = MAXIMUM (ADR-0050 Regel 1); jeder Kanal waehlt eine ANDERE
# Groesse ab — so faellt jede Aufrufstelle EINZELN auf, nicht nur alle zusammen.
DISPLAY_CONFIG = {
    "active_metrics": ["temp_max_c", "sunny_hours_h", "uv_index_max"],
    "channel_active_metrics": {
        "email": ["temp_max_c", "sunny_hours_h"],
        "telegram": ["temp_max_c", "uv_index_max"],
        "sms": ["temp_max_c"],
    },
}
# Je Kanal (muss sichtbar sein, darf NICHT sichtbar sein), in der Schreibweise
# des jeweiligen Renderers: HTML-Zeilenlabel, Telegram-Klartextlabel, SMS-Kuerzel.
VISIBLE_HIDDEN: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "email": (("Temperatur", "Sonnenstunden"), ("UV-Index",)),
    "telegram": (("Temp max", "UV max"), ("Sonne",)),
    "sms": ((" D+ ",), (" SU ", " UV ")),
}


def _preset(preset_id: str, user_id: str) -> dict:
    return {
        "id": preset_id, "name": "Kanal-Probe", "user_id": user_id, "kind": "vergleich",
        "location_ids": [LOCATION.id], "schedule": "daily", "profil": "ALLGEMEIN",
        "created_at": "2026-07-01T00:00:00Z", "send_telegram": True, "send_sms": True,
        # Stundenverlauf/Ausblick aus: diese Scheibe betrifft NUR die
        # Uebersichtstabelle — beide Bloecke wuerden die Kuerzel-Suche stoeren.
        "hourly_enabled": False, "outlook_enabled": False,
        "display_config": dict(DISPLAY_CONFIG),
    }


@pytest.fixture
def env(tmp_path, monkeypatch) -> str:
    """Isolierter Daten-Root ueber BEIDE Zugriffsformen (`app.loader._DATA_ROOT`
    und relative "data"-Pfade wie in `services/user_tier.py`) + Offline-Naehte."""
    from app import loader as app_loader
    import services.comparison_engine as ce_mod
    import services.scheduler_dispatch_service as sds_mod

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(app_loader, "_DATA_ROOT", str(tmp_path / "data"))
    user_id = f"s8-kanal-{uuid.uuid4().hex[:8]}"
    user_json = tmp_path / "data" / "users" / user_id / "user.json"
    user_json.parent.mkdir(parents=True, exist_ok=True)
    user_json.write_text(json.dumps({"tier": "premium"}), encoding="utf-8")  # sms_allowed()

    def _dp(hour: int) -> ForecastDataPoint:
        return ForecastDataPoint(
            ts=datetime(2026, 7, 8, hour, 0), t2m_c=22.0, wind_chill_c=21.0,
            wind10m_kmh=11.0, gust_kmh=19.0, precip_1h_mm=0.0, cloud_total_pct=35,
            uv_index=5.0, thunder_level=ThunderLevel.NONE, pop_pct=10, visibility_m=9000,
        )

    class RecordingEngine(ce_mod.ComparisonEngine):  # echte Subklasse, kein Mock
        @staticmethod
        def run(*args, **kwargs):
            return ComparisonResult(
                locations=[
                    LocationResult(
                        location=loc, score=90, temp_max=22.0, temp_min=12.0,
                        wind_max=11.0, gust_max=19.0, cloud_avg=35, sunny_hours=6,
                        official_alerts=[], hourly_data=[_dp(9), _dp(12), _dp(15)],
                    )
                    for loc in (kwargs.get("locations") or (args[0] if args else []))
                ],
                time_window=kwargs.get("time_window", (9, 16)),
                target_date=kwargs.get("target_date", TARGET_DATE),
                created_at=datetime(2026, 7, 8, 4, 0),
            )

    monkeypatch.setattr(ce_mod, "ComparisonEngine", RecordingEngine)
    # Δ-Anker-Snapshots holen echtes Nowcast-Wetter (Netz) — nicht Pruefgegenstand.
    monkeypatch.setattr(sds_mod, "_write_compare_alert_snapshots", lambda *a, **k: None)
    return user_id


def _assert_channel(channel: str, text: str, where: str) -> None:
    visible, hidden = VISIBLE_HIDDEN[channel]
    for token in visible:
        assert token in text, (
            f"{where}: '{token}' fehlt in der {channel}-Ausgabe, obwohl der Kanal "
            f"diese Groesse gewaehlt hat.\n{text[:400]!r}"
        )
    for token in hidden:
        assert token not in text, (
            f"{where}: die {channel}-Ausgabe zeigt '{token}', obwohl der Kanal diese "
            "Groesse abgewaehlt hat — die Aufrufstelle liest vermutlich wieder die "
            f"gemeinsame `opts.enabled_metrics` (Mutation M2).\n{text[:400]!r}"
        )


def test_dispatch_delivers_a_different_metric_set_per_channel(env, tmp_path):
    """AC-S8-7/AC-S8-8: GIVEN ein Vergleich mit je Kanal anderer Uebersichts-
    Auswahl / WHEN der echte Versandpfad laeuft / THEN traegt jede zugestellte
    Nachricht genau die Groessen ihres Kanals."""
    from services.scheduler_dispatch_service import send_one_compare_preset

    sent: dict[str, list[str]] = {"email": [], "telegram": [], "sms": []}
    send_one_compare_preset(
        _preset("cp-s8-dispatch", env),
        Settings(
            smtp_host="dummy.invalid", smtp_user="dummy", smtp_pass="dummy",
            mail_to="dummy@example.invalid", telegram_bot_token="dummy-token",
            telegram_chat_id="123456", sms_gateway_url="https://sms.invalid",
            seven_api_key="k", sms_to="+491700000000",
        ),
        env, str(tmp_path), all_locations_cache=[LOCATION],
        target_date=TARGET_DATE, tage_ab_ortstag=0,
        mail_sink=lambda subject, body: sent["email"].append(body),
        telegram_sink=sent["telegram"].append,
        sms_sink=sent["sms"].append,
    )

    for channel, delivered in sent.items():
        assert len(delivered) == 1, f"{channel}: eine Zustellung erwartet, waren {len(delivered)}"
        _assert_channel(channel, delivered[0], "Versandpfad send_one_compare_preset")


def test_preview_shows_the_same_per_channel_selection_as_the_dispatch(env):
    """Zweiter Leser derselben Optionen: die Vorschau MUSS je Kanal dasselbe
    zeigen wie der Versand — sonst verspricht der Editor etwas anderes, als
    ankommt. Deckt die uebrigen fuenf Aufrufstellen (Spec Abschnitt 2)."""
    from app.loader import get_data_dir, save_location
    from services.compare_preview_service import ComparePreviewService

    save_location(LOCATION, user_id=env)
    write_compare_briefings(get_data_dir(env), [_preset("cp-s8-preview", env)])

    service = ComparePreviewService()
    args = dict(user_id=env, target_date=TARGET_DATE.isoformat())
    payload = service.render_all_channels("cp-s8-preview", **args)
    for channel, key in (("email", "email_html"), ("telegram", "telegram"), ("sms", "sms")):
        _assert_channel(channel, payload[key], f"Vorschau render_all_channels[{key}]")
    _assert_channel("telegram", service.render_telegram_preview("cp-s8-preview", **args),
                    "Vorschau render_telegram_preview")
    _assert_channel("sms", service.render_sms_preview("cp-s8-preview", **args),
                    "Vorschau render_sms_preview")
