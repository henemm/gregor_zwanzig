"""TDD RED — Issue #1290 (E1, Epic #1301 Scheibe E): Compare-Dispatch meldet `failed`.

SPEC: docs/specs/modules/compare_dispatch_observability_telegram_guard.md (AC-1..AC-4)

Der Compare-Daily-Endpoint (`/api/scheduler/compare-presets-daily`) meldet heute
`status:"ok"` selbst bei 100 % Fehlschlaegen (Prod-Journal 2026-07-16: 133/133),
weil `run_compare_presets_daily` nur den Erfolgs-Zaehler (`int`) liefert und die
Antwort kein `failed`-Feld traegt. Trip-Reports haben dasselbe Problem seit
#766/#1012 ueber `{status, count, failed}` geloest — E1 kopiert dieses Muster.

RED-Erwartung (vor Fix):
  - `run_compare_presets_daily` liefert `int` statt `tuple[int, int]`
    → alle Tupel-Assertions schlagen fehl.
  - Endpoint-Antwort hat kein `failed`-Feld und `status` bleibt "ok"
    → KeyError bzw. Status-Assertion schlaegt fehl.

Methodik (Kern-Schicht, netzfrei):
  - Fehlschlag-Pfad: Presets mit nicht aufloesbaren `location_ids` (Vorbild
    test_issue_649_compare_daily_dedup.py) — der Helper wirft ValueError, BEVOR
    Engine/Netz beruehrt werden.
  - Erfolgs-Pfad: echte Recording-Engine-Subklasse + Snapshot-Neutralisierung
    (Haus-Muster test_compare_dispatch_channel_fanout.py) und ein
    Boundary-Sink auf `smtplib.SMTP` (externe Bibliotheksgrenze, analog
    httpx.post-Sink) — die E-Mail geht real durch EmailOutput inkl. aller
    Guards (#1219/#1235), nur der Draht nach draussen ist ersetzt.
"""
from __future__ import annotations

import json
import smtplib
import uuid
from datetime import date, datetime
from pathlib import Path

import pytest

from app.models import ForecastDataPoint, ThunderLevel
from app.user import SavedLocation
from tests.helpers.compare_briefings import write_compare_briefings

TARGET_DATE = date(2026, 7, 18)


# ---------------------------------------------------------------------------
# Fixtures & Seams (Haus-Muster)
# ---------------------------------------------------------------------------

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


def _preset(preset_id: str, location_ids: list[str], **extra) -> dict:
    preset = {
        "id": preset_id,
        "name": f"Vergleich {preset_id}",
        "location_ids": location_ids,
        "schedule": "daily",
        "profil": "ALLGEMEIN",
        "empfaenger": ["gregor-test@henemm.com"],
        "created_at": "2026-07-01T00:00:00Z",
    }
    preset.update(extra)
    return preset


@pytest.fixture
def dispatch_env(tmp_path, monkeypatch):
    """Isolierter Daten-Root ueber BEIDE Zugriffsformen (loader._DATA_ROOT und
    relative "data"-Pfade wie im Endpoint-Default `data_root="data"`), damit
    kein Test am echten data/users/ vorbeischreibt (Muster
    test_compare_dispatch_channel_fanout.py::dispatch_env)."""
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

    # 2s-Pause zwischen Presets ist hier nicht Pruefgegenstand (eigener Test in
    # test_dispatch_orchestrator.py) — auf 0 gesetzt, sonst 2s je Zusatz-Preset.
    import services.dispatch_orchestrator as orch_mod

    monkeypatch.setattr(orch_mod.CompareDispatchStrategy, "inter_mail_delay", 0.0)

    user_id = f"tdd-e1-{uuid.uuid4().hex[:8]}"
    return data_root, user_id


def _write_presets(data_root: Path, user_id: str, presets: list[dict]) -> None:
    user_dir = data_root / "users" / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    write_compare_briefings(user_dir, presets)


def _write_location(data_root: Path, user_id: str, loc_id: str, name: str) -> None:
    loc_dir = data_root / "users" / user_id / "locations"
    loc_dir.mkdir(parents=True, exist_ok=True)
    (loc_dir / f"{loc_id}.json").write_text(
        json.dumps({
            "id": loc_id, "name": name, "lat": 47.27, "lon": 11.39,
            "elevation_m": 1000,
        }),
        encoding="utf-8",
    )


def _install_engine_and_snapshot_seams(monkeypatch) -> None:
    """Echte Engine-Subklasse mit deterministischem Ergebnis + Neutralisierung
    des Δ-Anker-Snapshot-Nachlaufs (holt sonst echtes Nowcast-Wetter) —
    Haus-Muster test_compare_dispatch_channel_fanout.py."""
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
                created_at=datetime(2026, 7, 18, 4, 0),
            )

    monkeypatch.setattr(ce_mod, "ComparisonEngine", RecordingEngine)
    monkeypatch.setattr(sds_mod, "_write_compare_alert_snapshots", lambda *a, **k: None)


def _install_smtp_sink(monkeypatch):
    """Boundary-Sink auf smtplib.SMTP (externe Bibliotheksgrenze): EmailOutput
    laeuft real inkl. Empfaenger-Guards, nur der Netz-Draht ist ersetzt."""
    sent: list[tuple] = []

    class _FakeSMTP:
        def __init__(self, host, port, *a, **k):
            self.host, self.port = host, port

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


def _set_smtp_env(monkeypatch) -> None:
    """Sendefaehige (Dummy-)SMTP-Konfiguration — der Test-User erzwingt via
    with_user_profile→for_testing() den Stalwart-Test-Host (nie Resend), der
    Boundary-Sink faengt den Dial ab."""
    monkeypatch.setenv("GZ_SMTP_HOST", "mail.henemm.com")
    monkeypatch.setenv("GZ_SMTP_USER", "dummy-user")
    monkeypatch.setenv("GZ_SMTP_PASS", "dummy-pass")
    monkeypatch.setenv("GZ_MAIL_TO", "gregor-test@henemm.com")


# ---------------------------------------------------------------------------
# AC-1 — 100%-Ausfall wird sichtbar: status="partial", failed=N, count=0
# ---------------------------------------------------------------------------

class TestTotalFailureVisible:
    def test_run_returns_sent_failed_tuple_on_total_failure(self, dispatch_env):
        """AC-1 (Funktionsebene): Given alle faelligen Presets scheitern /
        When run_compare_presets_daily laeuft / Then (sent, failed) == (0, 2).

        RED: Rueckgabe ist heute `int 0` — der 100%-Ausfall ist von einem
        leeren Lauf nicht unterscheidbar."""
        from services.scheduler_dispatch_service import run_compare_presets_daily

        data_root, user_id = dispatch_env
        _write_presets(data_root, user_id, [
            _preset("cp-fail-1", ["loc-missing-a"]),
            _preset("cp-fail-2", ["loc-missing-b"]),
        ])

        result = run_compare_presets_daily(
            user_id=user_id, data_root=str(data_root), hour=6,
        )

        assert result == (0, 2), (
            "AC-1: Zwei gescheiterte faellige Presets muessen als "
            f"(sent=0, failed=2) gemeldet werden, kam: {result!r}"
        )

    def test_endpoint_reports_partial_and_failed_on_total_failure(
        self, dispatch_env,
    ):
        """AC-1 (Endpoint): Given alle faelligen Presets scheitern / When der
        Scheduler POST /api/scheduler/compare-presets-daily aufruft / Then
        NICHT mehr status="ok", sondern status="partial" mit failed=2, count=0.

        RED: heute liefert der Endpoint {"status":"ok","count":0} ohne jeden
        Hinweis auf den Ausfall (Prod-Journal 2026-07-16: 133/133)."""
        from fastapi.testclient import TestClient

        from api.main import app

        data_root, user_id = dispatch_env
        _write_presets(data_root, user_id, [
            _preset("cp-fail-1", ["loc-missing-a"]),
            _preset("cp-fail-2", ["loc-missing-b"]),
        ])

        client = TestClient(app)
        resp = client.post(
            f"/api/scheduler/compare-presets-daily?user_id={user_id}&hour=6"
        )

        assert resp.status_code == 200
        data = resp.json()
        assert "failed" in data, (
            "AC-1: Die Antwort muss ein failed-Feld tragen (Schema-Paritaet "
            f"zu /trip-reports #766), kam: {data!r}"
        )
        assert data["failed"] == 2
        assert data["count"] == 0
        assert data["status"] == "partial", (
            "AC-1: Bei failed > 0 muss status='partial' sein (1:1 "
            f"Trip-Semantik), kam: {data['status']!r}"
        )


# ---------------------------------------------------------------------------
# AC-2 — Gemischter Lauf: count=Erfolge, failed=Fehlschlaege
# ---------------------------------------------------------------------------

def test_mixed_run_reports_exact_success_and_failure_counts(
    dispatch_env, monkeypatch,
):
    """AC-2: Given ein aufloesbares und ein nicht aufloesbares faelliges
    Preset / When der Lauf durchlaeuft / Then count=1, failed=1.

    Der Erfolg ist real belegt: der smtplib-Boundary-Sink hat genau eine
    Mail gesehen. RED: Rueckgabe ist heute `int 1` — der Fehlschlag ist
    unsichtbar."""
    from services.scheduler_dispatch_service import run_compare_presets_daily

    data_root, user_id = dispatch_env
    _install_engine_and_snapshot_seams(monkeypatch)
    _set_smtp_env(monkeypatch)
    smtp_sent = _install_smtp_sink(monkeypatch)

    _write_location(data_root, user_id, "loc-ibk", "Innsbruck")
    _write_presets(data_root, user_id, [
        _preset("cp-a-ok", ["loc-ibk"]),
        _preset("cp-b-bad", ["loc-missing"]),
    ])

    result = run_compare_presets_daily(
        user_id=user_id, data_root=str(data_root), hour=6,
    )

    assert len(smtp_sent) == 1, (
        f"Testvoraussetzung: das aufloesbare Preset muss real eine Mail "
        f"durch den Sink schicken, waren {len(smtp_sent)}"
    )
    assert result == (1, 1), (
        "AC-2: Gemischter Lauf muss (sent=1, failed=1) melden, "
        f"kam: {result!r}"
    )


# ---------------------------------------------------------------------------
# AC-3 — Regressionsschutz: fehlerfreier Lauf bleibt status="ok", failed=0
# ---------------------------------------------------------------------------

class TestZeroFailureStaysOk:
    def test_no_due_presets_returns_zero_zero(self, dispatch_env):
        """AC-3 (Funktionsebene): kein briefings/-Verzeichnis → (0, 0).

        RED: heute `int 0` statt Tupel."""
        from services.scheduler_dispatch_service import run_compare_presets_daily

        data_root, user_id = dispatch_env

        result = run_compare_presets_daily(
            user_id=user_id, data_root=str(data_root), hour=6,
        )

        assert result == (0, 0)

    def test_endpoint_keeps_status_ok_with_failed_zero(self, dispatch_env):
        """AC-3 (Endpoint): Lauf ohne Fehlschlag (keine faelligen Presets) →
        status="ok" wie bisher, failed=0 explizit.

        RED: das failed-Feld fehlt heute komplett."""
        from fastapi.testclient import TestClient

        from api.main import app

        data_root, user_id = dispatch_env
        _write_presets(data_root, user_id, [
            _preset("cp-manual", ["loc-x"], schedule="manual"),
        ])

        client = TestClient(app)
        resp = client.post(
            f"/api/scheduler/compare-presets-daily?user_id={user_id}&hour=6"
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["count"] == 0
        assert data.get("failed") == 0, (
            "AC-3: Auch der fehlerfreie Lauf muss failed=0 explizit melden, "
            f"kam: {data!r}"
        )


# ---------------------------------------------------------------------------
# AC-4 — Fehler-Isolation (#1207) bleibt: kaputtes Preset bricht den Lauf nicht ab
# ---------------------------------------------------------------------------

def test_broken_preset_only_increments_failed_others_still_dispatch(
    dispatch_env, monkeypatch,
):
    """AC-4: Given drei faellige Presets, das mittlere scheitert / When der
    Lauf durchlaeuft / Then werden beide intakten Presets trotzdem versendet
    (count=2), das kaputte erhoeht nur failed (=1), keine Exception nach
    aussen — Fehler-Isolation #1207 byte-fuer-byte unveraendert.

    RED: Rueckgabe ist heute `int 2` statt (2, 1)."""
    from services.scheduler_dispatch_service import run_compare_presets_daily

    data_root, user_id = dispatch_env
    _install_engine_and_snapshot_seams(monkeypatch)
    _set_smtp_env(monkeypatch)
    smtp_sent = _install_smtp_sink(monkeypatch)

    _write_location(data_root, user_id, "loc-ibk", "Innsbruck")
    # Alphabetische Dateinamen-Ordnung: das kaputte Preset liegt in der Mitte.
    _write_presets(data_root, user_id, [
        _preset("cp-a-ok", ["loc-ibk"]),
        _preset("cp-b-broken", ["loc-missing"]),
        _preset("cp-c-ok", ["loc-ibk"]),
    ])

    # Kein pytest.raises — Fehler muessen intern isoliert bleiben (#1207).
    result = run_compare_presets_daily(
        user_id=user_id, data_root=str(data_root), hour=6,
    )

    assert len(smtp_sent) == 2, (
        "AC-4: Beide intakten Presets muessen trotz kaputtem Mittel-Preset "
        f"real versendet werden, waren {len(smtp_sent)}"
    )
    assert result == (2, 1), (
        "AC-4: Drei Presets mit einem Fehlschlag muessen (sent=2, failed=1) "
        f"melden, kam: {result!r}"
    )
