"""TDD RED — Issue #1288 (E2, Epic #1301 Scheibe E): Harter Telegram-Empfaenger-Guard.

SPEC: docs/specs/modules/compare_dispatch_observability_telegram_guard.md (AC-5..AC-8)

`TelegramOutput.send` postet `chat_id` heute ungeprueft an die Bot-API —
waehrend E-Mail seit #1147/#1219/#1235 eine bedingungslose Guard-Linie hat.
Konkretes Leck (config.py `for_testing()`/`with_user_profile()`): fehlt
`GZ_TELEGRAM_TEST_CHAT_ID`, bleibt `telegram_chat_id` im Test-Modus die
Prod-Chat-ID und ein Test-Versand geht klaglos an den Prod-Chat.

Boundary-Sink auf `httpx.post` (Vorbild test_bug599_telegram_persistent.py) —
KEIN Live-Telegram, kein echter Bot-API-Call. Der Sink beweist positiv wie
negativ, ob ein POST stattgefunden haette.

RED-Erwartung (vor Fix):
  - AC-5/AC-7/AC-8: kein Guard → `send()` postet ungeprueft (Sink faengt den
    Call), kein OutputConfigError → `pytest.raises` schlaegt fehl.
  - AC-6 ist bewusst schon heute gruen (Regressionsschutz gegen Ueberblocken:
    korrekt konfigurierte Test-Chat-ID muss weiter funktionieren).
  - AC-8 (Interlock mit E1/#1290): der Guard-Block wuerde heute zusaetzlich
    im fail-soften Telegram-Zweig von `send_compare_report` verschluckt und
    im (noch fehlenden) `failed`-Zaehler unsichtbar bleiben.
"""
from __future__ import annotations

import json
import smtplib
import uuid
from datetime import date, datetime
from pathlib import Path

import httpx
import pytest

from app.config import Settings
from app.models import ForecastDataPoint, ThunderLevel
from output.channels.base import OutputConfigError
from tests.helpers.compare_briefings import write_compare_briefings

PROD_CHAT_ID = "777000111"
TEST_CHAT_ID = "424242"
TARGET_DATE = date(2026, 7, 18)


# ---------------------------------------------------------------------------
# Boundary-Sink auf httpx.post (Bot-API-Grenze)
# ---------------------------------------------------------------------------

class _FakeBotApiResponse:
    status_code = 200
    text = '{"ok": true}'

    def json(self):
        return {"ok": True, "result": {"message_id": 4242}}


class _HttpxPostSink:
    """Zeichnet jeden httpx.post-Aufruf auf und antwortet wie eine
    wohlwollende Bot-API — so ist beweisbar, ob ein POST stattfand UND der
    Alt-Pfad (kein Guard) haette 'Erfolg' gemeldet."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def __call__(self, url, json=None, timeout=None, **kwargs):
        self.calls.append({"url": url, "payload": json})
        return _FakeBotApiResponse()

    def telegram_calls(self) -> list[dict]:
        return [c for c in self.calls if "api.telegram.org" in str(c["url"])]


@pytest.fixture
def httpx_sink(monkeypatch) -> _HttpxPostSink:
    sink = _HttpxPostSink()
    monkeypatch.setattr(httpx, "post", sink)
    return sink


def _guard_settings(**overrides) -> Settings:
    """Test-Modus-Settings mit der Fallback-Luecke aus config.py: Test-Chat-ID
    fehlt, chat_id zeigt auf die Prod-ID.

    telegram_test_bot_token wird identisch zu telegram_bot_token gesetzt
    (Issue #1363 Token-Guard, Faelle bleiben ausschliesslich Chat-ID-Faelle —
    der neue Token-Guard soll hier nicht zusaetzlich greifen)."""
    defaults = dict(
        telegram_bot_token="fake:token",
        telegram_test_bot_token="fake:token",
        telegram_chat_id=PROD_CHAT_ID,
        telegram_test_chat_id="",
        is_test_mode=True,
    )
    defaults.update(overrides)
    return Settings(**defaults)


# ---------------------------------------------------------------------------
# AC-5 — Test-Modus + Prod-Chat-ID: harter Block VOR jedem POST
# ---------------------------------------------------------------------------

class TestTestModeBlocksProdChatId:
    def test_missing_test_chat_id_blocks_send_without_any_post(self, httpx_sink):
        """AC-5: Given is_test_mode=True und telegram_test_chat_id fehlt
        (chat_id bleibt die Prod-ID) / When send() laeuft / Then
        OutputConfigError und KEIN POST an die Bot-API.

        RED: heute postet send() ungeprueft — der Sink faengt den Call, es
        gibt keinen Fehler."""
        from output.channels.telegram import TelegramOutput

        output = TelegramOutput(_guard_settings())

        with pytest.raises(OutputConfigError):
            output.send("Betreff", "Testnachricht")

        assert httpx_sink.telegram_calls() == [], (
            "AC-5: Im Test-Modus mit Prod-Chat-ID darf KEIN Bot-API-POST "
            f"passieren, gesehen: {httpx_sink.telegram_calls()!r}"
        )

    def test_diverging_test_chat_id_blocks_send_without_any_post(self, httpx_sink):
        """AC-5 (Variante 'abweichend'): telegram_test_chat_id ist zwar
        gesetzt, aber chat_id zeigt trotzdem auf die Prod-ID → Block."""
        from output.channels.telegram import TelegramOutput

        output = TelegramOutput(_guard_settings(telegram_test_chat_id=TEST_CHAT_ID))

        with pytest.raises(OutputConfigError):
            output.send("Betreff", "Testnachricht")

        assert httpx_sink.telegram_calls() == []


# ---------------------------------------------------------------------------
# AC-6 — Regressionsschutz: korrekte Test-Chat-ID sendet unveraendert
# ---------------------------------------------------------------------------

def test_matching_test_chat_id_still_sends(httpx_sink):
    """AC-6: Given Test-Modus UND chat_id == telegram_test_chat_id / When
    send() laeuft / Then normaler Versand (message_id), kein Guard-Block —
    Staging-/Live-Opt-in-Flows (GZ_TELEGRAM_LIVE=1, tg-live-e2e) bleiben
    lauffaehig.

    Bewusst schon heute GRUEN (Regressionsschutz gegen Ueberblocken)."""
    from output.channels.telegram import TelegramOutput

    output = TelegramOutput(_guard_settings(
        telegram_chat_id=TEST_CHAT_ID, telegram_test_chat_id=TEST_CHAT_ID,
    ))

    message_id = output.send("Betreff", "Testnachricht")

    assert message_id == 4242
    calls = httpx_sink.telegram_calls()
    assert len(calls) == 1
    assert calls[0]["payload"]["chat_id"] == TEST_CHAT_ID


def test_non_test_mode_send_stays_untouched(httpx_sink):
    """AC-6 (Flanke): is_test_mode=False (Prod-Normalbetrieb) bleibt vom
    Guard unberuehrt — identisch zum E-Mail-Guard-Prinzip (Guard prueft
    Zustand, nicht Herkunft). Bewusst schon heute GRUEN."""
    from output.channels.telegram import TelegramOutput

    output = TelegramOutput(Settings(
        telegram_bot_token="fake:token",
        telegram_chat_id=PROD_CHAT_ID,
    ))

    message_id = output.send("Betreff", "Prodnachricht")

    assert message_id == 4242
    assert len(httpx_sink.telegram_calls()) == 1


# ---------------------------------------------------------------------------
# AC-7 — Profil-Flag-Weg (is_test_user=True) fuehrt zur selben Sperre
# ---------------------------------------------------------------------------

def test_profile_flagged_test_user_is_blocked_via_with_user_profile(
    httpx_sink, tmp_path, monkeypatch,
):
    """AC-7: Given ein NEUTRAL benannter User, den nur das Profil-Flag
    `is_test_user=True` als Test-Konto ausweist, mit Prod-Chat-ID im Profil /
    When Settings().with_user_profile(user_id) gebildet und send() gerufen
    wird / Then greift dieselbe Sperre wie AC-5 — kein Sonderfall fuer den
    profilbasierten Erkennungsweg.

    RED: heute geht der POST an die Prod-Chat-ID raus."""
    from app import loader as app_loader
    from output.channels.telegram import TelegramOutput

    data_root = tmp_path / "data"
    monkeypatch.chdir(tmp_path)  # is_test_user_id liest data/ relativ zum cwd
    monkeypatch.setattr(app_loader, "_DATA_ROOT", str(data_root))

    user_id = f"e2guard-{uuid.uuid4().hex[:8]}"  # bewusst ohne 'test'/'tdd'
    user_json = data_root / "users" / user_id / "user.json"
    user_json.parent.mkdir(parents=True, exist_ok=True)
    user_json.write_text(
        json.dumps({"is_test_user": True, "telegram_chat_id": PROD_CHAT_ID}),
        encoding="utf-8",
    )

    base = Settings(
        telegram_bot_token="fake:token",
        telegram_test_bot_token="fake:token",
        telegram_chat_id=PROD_CHAT_ID,
        telegram_test_chat_id="",
    )
    settings = base.with_user_profile(user_id)

    # Vorbedingung (heute schon gruen): der Profil-Flag-Weg setzt is_test_mode,
    # laesst die chat_id aber auf der Prod-ID stehen — exakt die Luecke.
    assert settings.is_test_mode is True, (
        "Vorbedingung geplatzt: with_user_profile hat das Profil-Flag "
        "is_test_user=True nicht als Test-Modus erkannt"
    )
    assert settings.telegram_chat_id == PROD_CHAT_ID

    with pytest.raises(OutputConfigError):
        TelegramOutput(settings).send("Betreff", "Testnachricht")

    assert httpx_sink.telegram_calls() == [], (
        "AC-7: Auch der profilbasierte Test-User darf KEINEN Bot-API-POST "
        f"ausloesen, gesehen: {httpx_sink.telegram_calls()!r}"
    )


# ---------------------------------------------------------------------------
# AC-8 — Interlock E1×E2: Guard-Block wird im Compare-failed-Zaehler sichtbar
# ---------------------------------------------------------------------------

def _dp(hour: int) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(TARGET_DATE.year, TARGET_DATE.month, TARGET_DATE.day, hour, 0),
        t2m_c=22.0, wind_chill_c=21.0, wind10m_kmh=11.0, gust_kmh=19.0,
        precip_1h_mm=0.0, cloud_total_pct=35, uv_index=5.0,
        thunder_level=ThunderLevel.NONE, pop_pct=10, visibility_m=9000,
    )


def _install_engine_and_snapshot_seams(monkeypatch) -> None:
    """Haus-Muster test_compare_dispatch_channel_fanout.py: echte
    Engine-Subklasse (deterministisch, netzfrei) + Snapshot-Neutralisierung."""
    import services.comparison_engine as ce_mod
    import services.scheduler_dispatch_service as sds_mod
    from app.user import ComparisonResult, LocationResult

    original = ce_mod.ComparisonEngine

    class RecordingEngine(original):
        @staticmethod
        def run(*args, **kwargs):
            locations = kwargs.get("locations")
            if locations is None and args:
                locations = args[0]
            return ComparisonResult(
                locations=[
                    LocationResult(
                        location=loc, score=90, temp_max=22.0, temp_min=12.0,
                        wind_max=11.0, gust_max=19.0, cloud_avg=35,
                        sunny_hours=6, official_alerts=[],
                        hourly_data=[_dp(9), _dp(12), _dp(15)],
                    )
                    for loc in list(locations or [])
                ],
                time_window=kwargs.get("time_window", (9, 16)),
                target_date=kwargs.get("target_date", TARGET_DATE),
                created_at=datetime(2026, 7, 18, 4, 0),
            )

    monkeypatch.setattr(ce_mod, "ComparisonEngine", RecordingEngine)
    monkeypatch.setattr(sds_mod, "_write_compare_alert_snapshots", lambda *a, **k: None)


def _install_smtp_sink(monkeypatch):
    """Boundary-Sink auf smtplib.SMTP — die E-Mail (bei Compare immer aktiv)
    geht real durch EmailOutput inkl. Guards, nur der Draht ist ersetzt."""
    sent: list[tuple] = []

    class _FakeSMTP:
        def __init__(self, host, port, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def starttls(self):
            return None

        def login(self, user, password):
            return None

        def sendmail(self, from_addr, to_addrs, msg):
            sent.append((from_addr, tuple(to_addrs)))

    monkeypatch.setattr(smtplib, "SMTP", _FakeSMTP)
    return sent


class TestGuardBlockVisibleInCompareFailedTally:
    def test_send_compare_report_reraises_config_error_after_email(
        self, httpx_sink,
    ):
        """AC-8 (Kernstelle notification_service): Given Test-Modus mit
        Prod-Chat-ID und effective_channels={email, telegram} / When
        send_compare_report laeuft / Then wird die E-Mail zugestellt
        (mail_sink), der OutputConfigError aus dem Telegram-Guard aber
        RE-RAISED statt im Fail-Soft-Netz (#1270 AC-5) zu verschwinden.

        RED: heute schluckt der `except Exception`-Zweig jeden
        Telegram-Fehler — und ohne Guard gaebe es nicht einmal einen: der
        Sink faengt einen echten Bot-API-POST an die Prod-Chat-ID."""
        from services.notification_service import NotificationService

        settings = _guard_settings()
        mail_calls: list[str] = []

        with pytest.raises(OutputConfigError):
            NotificationService(settings, "tdd-e2-interlock").send_compare_report(
                subject="Wetter-Vergleich: Interlock (18.07.2026)",
                html_body="<p>Innsbruck</p>",
                text_body="Innsbruck",
                telegram_text="Innsbruck",
                sms_text="Innsbruck",
                recipients=["gregor-test@henemm.com"],
                effective_channels={"email", "telegram"},
                mail_sink=lambda **kw: mail_calls.append(kw.get("subject", "")),
            )

        assert len(mail_calls) == 1, (
            "AC-8: Die E-Mail (immer aktiver Compare-Kanal) muss VOR dem "
            f"Guard-Block zugestellt sein, waren {len(mail_calls)}"
        )
        assert httpx_sink.telegram_calls() == [], (
            "AC-8: Der Guard muss VOR jedem Bot-API-POST greifen, gesehen: "
            f"{httpx_sink.telegram_calls()!r}"
        )

    def test_daily_run_counts_guard_blocked_preset_as_failed(
        self, httpx_sink, tmp_path, monkeypatch,
    ):
        """AC-8 (ganze Kette): Given ein faelliges Compare-Preset mit
        send_telegram=True im Test-Modus, dessen chat_id auf die Prod-ID
        zeigt, waehrend die E-Mail erfolgreich rausgeht / When der
        Compare-Daily-Lauf es verarbeitet / Then zaehlt das Preset in E1s
        failed-Feld — der Guard-Block bleibt NICHT wie ein transienter
        Telegram-Fehler unsichtbar. Kein realer POST (Sink-Beweis).

        RED: heute (a) existiert kein Guard — der Sink faengt einen POST an
        die Prod-Chat-ID, (b) die Rueckgabe ist `int 1` (Preset zaehlt als
        Erfolg) statt (0, 1)."""
        from app import loader as app_loader
        from services.scheduler_dispatch_service import run_compare_presets_daily

        data_root = tmp_path / "data"
        data_root.mkdir(parents=True, exist_ok=True)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(app_loader, "_DATA_ROOT", str(data_root))
        import services.dispatch_orchestrator as orch_mod

        monkeypatch.setattr(orch_mod.CompareDispatchStrategy, "inter_mail_delay", 0.0)

        _install_engine_and_snapshot_seams(monkeypatch)
        smtp_sent = _install_smtp_sink(monkeypatch)

        # Env fuer den vom Lauf selbst geladenen Settings-Stack: SMTP
        # sendefaehig, Telegram konfiguriert — aber OHNE Test-Chat-ID
        # (genau die for_testing()-Fallback-Luecke aus config.py).
        monkeypatch.setenv("GZ_SMTP_HOST", "mail.henemm.com")
        monkeypatch.setenv("GZ_SMTP_USER", "dummy-user")
        monkeypatch.setenv("GZ_SMTP_PASS", "dummy-pass")
        monkeypatch.setenv("GZ_MAIL_TO", "gregor-test@henemm.com")
        monkeypatch.setenv("GZ_TELEGRAM_BOT_TOKEN", "fake:token")
        monkeypatch.setenv("GZ_TELEGRAM_CHAT_ID", PROD_CHAT_ID)
        monkeypatch.delenv("GZ_TELEGRAM_TEST_CHAT_ID", raising=False)

        user_id = f"tdd-e2lock-{uuid.uuid4().hex[:8]}"  # Test-User → is_test_mode
        loc_dir = data_root / "users" / user_id / "locations"
        loc_dir.mkdir(parents=True, exist_ok=True)
        (loc_dir / "loc-ibk.json").write_text(
            json.dumps({
                "id": "loc-ibk", "name": "Innsbruck", "lat": 47.27,
                "lon": 11.39, "elevation_m": 1000,
            }),
            encoding="utf-8",
        )
        user_dir = data_root / "users" / user_id
        write_compare_briefings(user_dir, [{
            "id": "cp-guarded",
            "name": "Vergleich cp-guarded",
            "location_ids": ["loc-ibk"],
            "schedule": "daily",
            "profil": "ALLGEMEIN",
            "empfaenger": ["gregor-test@henemm.com"],
            "send_telegram": True,
            "created_at": "2026-07-01T00:00:00Z",
        }])

        result = run_compare_presets_daily(
            user_id=user_id, data_root=str(data_root), hour=6,
        )

        assert httpx_sink.telegram_calls() == [], (
            "AC-8: Der Guard muss den Bot-API-POST an die Prod-Chat-ID "
            f"verhindern, gesehen: {httpx_sink.telegram_calls()!r}"
        )
        assert len(smtp_sent) == 1, (
            "AC-8-Szenario: die E-Mail des Presets muss erfolgreich raus "
            f"sein (immer aktiver Kanal), waren {len(smtp_sent)}"
        )
        assert result == (0, 1), (
            "AC-8: Das guard-blockierte Preset muss in E1s failed-Feld "
            f"zaehlen — (sent=0, failed=1), kam: {result!r}"
        )
