"""TDD RED — Issue #2286 AC-4: Provider-Totalausfall im Cron-Vergleichsversand.

SPEC: docs/specs/modules/fix_2286_compare_betrieb_health.md (Implementierungsdetail 2, AC-4)

Heute wendet nur der Handversand (`weather_failure_as_outcome=True`) die Regel
"JEDER Ort ohne Daten ⇒ `no_weather`" an. Im Cron (Default `False`) geht eine
Mail aus lauter Fehlerzellen raus und zaehlt als "sent" -- damit kann die
Job-weite Totalausfall-Flanke im Hauptszenario (Provider-Stoerung) nie feuern.

Soll: auch im Cron ⇒ `SendOutcomeError("no_weather")`, KEINE Mail, der Preset
zaehlt als `failed`. Fehlen nur einzelne Orte, geht die Mail wie bisher raus.

Naehte (Kern-Schicht, netzfrei, kein Mock-Theater):
  * Wetter: `wetter_fehlt_je_ort` (echte Engine-Subklasse, liefert je Ort
    `LocationResult(error=...)` -- realistische Form, KEINE Ausnahme) aus
    `tests/tdd/_handversand_fixtures.py`; Teilausfall: eigene Engine-Subklasse,
    die nur fuer einen Ort einen Fehler liefert.
  * Transport: `mail_sink` (Einzelaufruf) bzw. smtplib-Boundary-Sink (Cron-Lauf).
  * Δ-Anker-Snapshot: neutralisiert (holt sonst Nowcast-Netz).
"""
from __future__ import annotations

import uuid
from datetime import date, datetime

import pytest

from app.config import Settings
from app.user import SavedLocation
from tests.tdd._handversand_fixtures import wetter_fehlt_je_ort
from tests.tdd.test_compare_dispatch_failed_tally import (
    _dp,
    _install_smtp_sink,
    _preset,
    _set_smtp_env,
    _write_location,
    _write_presets,
)

TARGET_DATE = date(2026, 7, 18)


class _Sink:
    """Aufzeichnungs-Naht (kein Mock): haelt jeden Zustellversuch fest."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def __call__(self, *args, **kwargs) -> None:
        self.calls.append(kwargs)

    def __len__(self) -> int:
        return len(self.calls)


@pytest.fixture
def env(tmp_path, monkeypatch):
    from app import loader as app_loader
    import services.dispatch_orchestrator as orch_mod
    import services.scheduler_dispatch_service as sds_mod

    data_root = tmp_path / "data"
    data_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(app_loader, "_DATA_ROOT", str(data_root))
    monkeypatch.setattr(orch_mod.CompareDispatchStrategy, "inter_mail_delay", 0.0)
    monkeypatch.setattr(sds_mod, "_write_compare_alert_snapshots", lambda *a, **k: None)
    # `tdd-`-Praefix: Settings leitet den Test-Nutzer auf den Stalwart-Test-Host.
    return data_root, f"tdd-2286-ac4-{uuid.uuid4().hex[:8]}"


def _settings_mail_only() -> Settings:
    return Settings(
        smtp_host="dummy.invalid", smtp_user="dummy", smtp_pass="dummy",
        mail_to="dummy@example.invalid",
    )


def _locations() -> list[SavedLocation]:
    return [
        SavedLocation(id="loc-ibk", name="Innsbruck", lat=47.27, lon=11.39, elevation_m=1000),
        SavedLocation(id="loc-bz", name="Bozen", lat=46.50, lon=11.35, elevation_m=260),
    ]


def _install_teilausfall_engine(monkeypatch, failing_loc_id: str) -> None:
    """Echte Engine-Subklasse: nur `failing_loc_id` ohne Daten, alle anderen
    mit vollstaendigen Werten (die Engine laeuft je Ort einmal)."""
    import services.comparison_engine as ce_mod
    from app.user import ComparisonResult, LocationResult

    original = ce_mod.ComparisonEngine

    class _TeilausfallEngine(original):  # echte Subklasse, kein Mock
        @staticmethod
        def run(*args, **kwargs):
            locations = list(kwargs.get("locations") or (args[0] if args else []))
            out = []
            for loc in locations:
                if loc.id == failing_loc_id:
                    out.append(LocationResult(location=loc, error="Open-Meteo: HTTP 503"))
                else:
                    out.append(LocationResult(
                        location=loc, score=80, temp_max=22.0, temp_min=12.0,
                        wind_max=11.0, gust_max=19.0, cloud_avg=35, sunny_hours=6,
                        official_alerts=[], hourly_data=[_dp(9), _dp(12), _dp(15)],
                    ))
            return ComparisonResult(
                locations=out,
                time_window=kwargs.get("time_window", (9, 16)),
                target_date=kwargs.get("target_date", TARGET_DATE),
                created_at=datetime(2026, 7, 18, 4, 0),
            )

    monkeypatch.setattr(ce_mod, "ComparisonEngine", _TeilausfallEngine)


def _vergleich(user_id: str) -> dict:
    return {
        "id": "vgl-ausfall", "name": "Ausfall", "user_id": user_id,
        "location_ids": ["loc-ibk", "loc-bz"], "schedule": "daily",
        "profil": "ALLGEMEIN", "created_at": "2026-07-01T00:00:00Z", "kind": "vergleich",
    }


# ---------------------------------------------------------------------------
# AC-4 — alle Orte ohne Daten ⇒ no_weather, keine Mail (Cron == Handversand)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "weather_failure_as_outcome",
    [
        pytest.param(False, id="cron-default"),
        pytest.param(True, id="handversand-paritaet"),
    ],
)
def test_all_locations_without_data_raise_no_weather_and_send_nothing(
    env, monkeypatch, weather_failure_as_outcome,
):
    """Given ein Vergleich mit zwei Orten, fuer BEIDE liefert der Provider
    keine Daten / When `send_one_compare_preset` laeuft (Cron-Default bzw.
    Handversand) / Then `SendOutcomeError` mit Code `no_weather`, und es wird
    KEINE Mail zugestellt.

    RED nur fuer `cron-default`: heute geht dort eine Fehlerzellen-Mail raus.
    `handversand-paritaet` ist der gruene Paritaets-Waechter."""
    from services.scheduler_dispatch_service import send_one_compare_preset
    from services.send_outcomes import SendOutcomeError

    data_root, user_id = env
    wetter_fehlt_je_ort(monkeypatch)
    mail_sink = _Sink()

    with pytest.raises(SendOutcomeError) as exc_info:
        send_one_compare_preset(
            _vergleich(user_id), _settings_mail_only(), user_id, str(data_root),
            all_locations_cache=_locations(), target_date=TARGET_DATE,
            tage_ab_ortstag=0, mail_sink=mail_sink,
            weather_failure_as_outcome=weather_failure_as_outcome,
        )

    assert exc_info.value.code == "no_weather", (
        f"AC-4: Grund muss 'no_weather' sein, kam {exc_info.value.code!r}"
    )
    assert len(mail_sink) == 0, (
        "AC-4: bei Totalausfall darf keine Mail aus lauter Fehlerzellen "
        f"zugestellt werden, zugestellt: {len(mail_sink)}"
    )


def test_one_location_missing_still_sends_mail(env, monkeypatch):
    """AC-4 (Gegenrichtung, gruener Waechter): fehlt nur EIN Ort, geht die
    Mail wie bisher raus -- die neue Regel darf den Teilausfall nicht
    verschlucken."""
    from services.scheduler_dispatch_service import send_one_compare_preset

    data_root, user_id = env
    _install_teilausfall_engine(monkeypatch, failing_loc_id="loc-bz")
    mail_sink = _Sink()

    send_one_compare_preset(
        _vergleich(user_id), _settings_mail_only(), user_id, str(data_root),
        all_locations_cache=_locations(), target_date=TARGET_DATE,
        tage_ab_ortstag=0, mail_sink=mail_sink,
    )

    assert len(mail_sink) == 1, (
        f"AC-4: Teilausfall muss die Mail versenden, zugestellt: {len(mail_sink)}"
    )


# ---------------------------------------------------------------------------
# AC-4 ueber den echten Cron-Lauf: failed=1, keine Mail
# ---------------------------------------------------------------------------

def test_cron_run_counts_total_outage_as_failed_without_mail(env, monkeypatch):
    """Given ein faelliger Vergleich, alle Orte ohne Daten / When der Cron-Lauf
    `run_compare_presets_daily(hour=6)` durchlaeuft / Then `(sent, failed) ==
    (0, 1)` und der smtplib-Boundary-Sink sah KEINE Mail.

    RED: heute `(1, 0)` mit einer Fehlerzellen-Mail."""
    from services.scheduler_dispatch_service import run_compare_presets_daily

    data_root, user_id = env
    wetter_fehlt_je_ort(monkeypatch)
    _set_smtp_env(monkeypatch)
    smtp_sent = _install_smtp_sink(monkeypatch)
    _write_location(data_root, user_id, "loc-ibk", "Innsbruck")
    _write_location(data_root, user_id, "loc-bz", "Bozen")
    _write_presets(data_root, user_id, [_preset("cp-ausfall", ["loc-ibk", "loc-bz"])])

    result = run_compare_presets_daily(user_id=user_id, data_root=str(data_root), hour=6)

    assert smtp_sent == [], (
        f"AC-4: der Cron darf keine Fehlerzellen-Mail versenden, gesendet: {smtp_sent!r}"
    )
    assert result == (0, 1), (
        f"AC-4: Totalausfall muss als (sent=0, failed=1) zaehlen, kam {result!r}"
    )


def test_cron_run_with_one_location_missing_counts_as_sent(env, monkeypatch):
    """AC-4 Gegenrichtung im Cron (gruener Waechter): ein Ort fehlt ⇒ Mail
    geht raus, `(1, 0)`."""
    from services.scheduler_dispatch_service import run_compare_presets_daily

    data_root, user_id = env
    _install_teilausfall_engine(monkeypatch, failing_loc_id="loc-bz")
    _set_smtp_env(monkeypatch)
    smtp_sent = _install_smtp_sink(monkeypatch)
    _write_location(data_root, user_id, "loc-ibk", "Innsbruck")
    _write_location(data_root, user_id, "loc-bz", "Bozen")
    _write_presets(data_root, user_id, [_preset("cp-teil", ["loc-ibk", "loc-bz"])])

    result = run_compare_presets_daily(user_id=user_id, data_root=str(data_root), hour=6)

    assert len(smtp_sent) == 1
    assert result == (1, 0), f"AC-4: Teilausfall bleibt 'sent', kam {result!r}"
