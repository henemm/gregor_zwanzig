"""TDD RED — Premium-SMS im Ortsvergleich-Briefing (Issue #2275).

SPEC: docs/specs/modules/fix_2275_compare_premium_sms_versand.md (AC-1..AC-8)

RED heute, warum: ``NotificationService.send_compare_report`` hat keinen
``premium_sms``-Zweig und kein ``premium_sms_sink``; ``send_one_compare_preset``
reicht keinen Sink durch. Ein aufgeloester Kanal ``premium_sms`` wird still
uebergangen.

Mock-frei: ``PremiumSmsOutput`` wird (wie in ``test_sms_tageslimit.py``) durch
eine echte Aufzeichner-Klasse ersetzt — im Modul ``notification_service`` UND im
Quellmodul. Tageslimit-Zaehler und Reservierung laufen ECHT (Dateien unter
einem tmp-Datenwurzel). Kein Netz.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from app.config import Settings
from app.models import ForecastDataPoint, ThunderLevel
from app.user import SavedLocation
from services.notification_service import NotificationService

TARGET_DATE = date(2026, 7, 8)

_ENV = {
    "GZ_ENV": "development",
    "GZ_SMTP_HOST": "smtp.invalid",
    "GZ_SMTP_USER": "unbrauchbar",
    "GZ_SMTP_PASS": "unbrauchbar",
    "GZ_MAIL_FROM": "gregor@example.invalid",
    "GZ_MAIL_TO": "unbrauchbar-fallback@example.invalid",
    "GZ_TELEGRAM_BOT_TOKEN": "0000000:unbrauchbar",
    "GZ_TELEGRAM_CHAT_ID": "unbrauchbar-chat",
    "GZ_SMS_GATEWAY_URL": "https://gateway.invalid/api/sms",
    "GZ_SEVEN_API_KEY": "unbrauchbar",
    "GZ_SMS_TO": "+490000000000",
}

SMS_TEXT = "Vergleich: Innsbruck 22C top"


class Mitschrift:
    def __init__(self) -> None:
        self.je_kanal: dict[str, list] = {
            k: [] for k in ("email", "sms", "premium_sms", "telegram")
        }
        self.fehler: dict[str, BaseException] = {}

    def anzahl(self, kanal: str) -> int:
        return len(self.je_kanal[kanal])


def _aufzeichner_installieren(monkeypatch) -> Mitschrift:
    from services import notification_service as ns
    import output.channels.email as _email_mod
    import output.channels.premium_sms as _premium_mod
    import output.channels.sms as _sms_mod
    import output.channels.telegram as _telegram_mod

    mit = Mitschrift()

    def _buchen(kanal: str, inhalt) -> None:
        if kanal in mit.fehler:
            raise mit.fehler[kanal]
        mit.je_kanal[kanal].append(inhalt)

    class _Email:
        def __init__(self, settings) -> None: ...

        def send(self, subject, body, html=True, plain_text_body=None, to=None,
                 mail_type=None, mail_format=None, compare_hourly_enabled=None):
            _buchen("email", subject)

    class _Sms:
        def __init__(self, settings) -> None: ...

        def send(self, subject, body) -> None:
            _buchen("sms", body)

    class _Premium:
        def __init__(self, settings) -> None: ...

        def send(self, subject, body) -> None:
            _buchen("premium_sms", body)

    class _Telegram:
        def __init__(self, settings) -> None: ...

        def send(self, subject, body, reply_markup=None, *, parse_mode=None,
                 suppress_subject_line=False) -> int:
            _buchen("telegram", body)
            return 1

    for modul in (ns, _email_mod):
        monkeypatch.setattr(modul, "EmailOutput", _Email)
    for modul in (ns, _sms_mod):
        monkeypatch.setattr(modul, "SMSOutput", _Sms)
    for modul in (ns, _premium_mod):
        monkeypatch.setattr(modul, "PremiumSmsOutput", _Premium)
    for modul in (ns, _telegram_mod):
        monkeypatch.setattr(modul, "TelegramOutput", _Telegram)
    return mit


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Isolierte Datenwurzel + Dummy-ENV + Aufzeichner."""
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
    for name, wert in _ENV.items():
        monkeypatch.setenv(name, wert)
    return _aufzeichner_installieren(monkeypatch)


def _kennung() -> str:
    # ohne "tdd"/"test", sonst erzwingt is_test_user_id Settings.for_testing()
    return f"pcmp-{uuid.uuid4().hex[:8]}"


def _nutzer(uid: str, tier: str = "premium") -> str:
    from app.loader import get_data_dir

    d = get_data_dir(uid)
    d.mkdir(parents=True, exist_ok=True)
    (d / "user.json").write_text(json.dumps({"id": uid, "tier": tier}))
    return uid


def _zaehler(uid: str) -> int:
    from app.loader import get_data_dir

    pfad = Path(get_data_dir(uid)) / "sms_daily_count.json"
    if not pfad.exists():
        return 0
    return int(json.loads(pfad.read_text()).get("premium_sms", 0))


def _zaehler_schreiben(uid: str, premium_sms: int) -> None:
    from app.loader import get_data_dir

    d = Path(get_data_dir(uid))
    d.mkdir(parents=True, exist_ok=True)
    (d / "sms_daily_count.json").write_text(json.dumps({
        "date": datetime.now(timezone.utc).date().isoformat(),
        "sms": 0, "premium_sms": premium_sms,
    }))


def _senden(uid: str, kanaele: set[str], **extra):
    svc = NotificationService(settings=Settings(), user_id=uid)
    return svc.send_compare_report(
        subject="Ortsvergleich", html_body="<p>H</p>", text_body="T",
        telegram_text="TG", sms_text=SMS_TEXT, recipients=["to@example.invalid"],
        effective_channels=kanaele, **extra,
    )


# ---------------------------------------------------------------------------
# AC-1 — Erfolg
# ---------------------------------------------------------------------------


def test_ac1_kurzform_geht_ueber_premium_sms_und_zaehler_steigt_um_eins(env):
    uid = _nutzer(_kennung())
    vorher = _zaehler(uid)

    ergebnis = _senden(uid, {"email", "premium_sms"})

    assert "premium_sms" in ergebnis.sent_channels, ergebnis
    assert env.je_kanal["premium_sms"] == [SMS_TEXT], (
        f"Transport muss genau die Vergleichs-Kurzform erhalten: {env.je_kanal['premium_sms']!r}"
    )
    assert _zaehler(uid) == vorher + 1


def test_ac1_sink_wird_statt_transport_gerufen(env):
    uid = _nutzer(_kennung())
    gesehen: list[str] = []

    ergebnis = _senden(uid, {"email", "premium_sms"}, premium_sms_sink=gesehen.append)

    assert gesehen == [SMS_TEXT]
    assert env.anzahl("premium_sms") == 0
    assert "premium_sms" in ergebnis.sent_channels


# ---------------------------------------------------------------------------
# AC-2 — Transportfehler: sichtbar, Reservierung frei, E-Mail unberuehrt
# ---------------------------------------------------------------------------


def test_ac2_transportfehler_ist_sichtbar_gibt_reservierung_frei_und_laesst_email_ganz(
    env, caplog,
):
    uid = _nutzer(_kennung())
    env.fehler["premium_sms"] = RuntimeError("seven.io kaputt")
    vorher = _zaehler(uid)

    with caplog.at_level(logging.ERROR):
        ergebnis = _senden(uid, {"email", "premium_sms"})

    assert "premium_sms" in ergebnis.failed_channels, ergebnis
    assert "premium_sms" in ergebnis.blocked_channels
    assert "premium_sms" in ergebnis.blocked_reason_codes
    assert "premium_sms" not in ergebnis.sent_channels
    assert _zaehler(uid) == vorher, "Reservierung muss freigegeben sein"
    assert "email" in ergebnis.sent_channels and env.anzahl("email") == 1
    assert any("premium" in r.getMessage().lower() for r in caplog.records), (
        "Fehlschlag muss geloggt werden"
    )


# ---------------------------------------------------------------------------
# AC-3 — Sperrgruende (Rueckadresse) und Tageslimit maschinenlesbar
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("grund", ["BLOCK_REASON_NO_REPLY_ADDRESS",
                                   "BLOCK_REASON_REPLY_ADDRESS_STALE"])
def test_ac3_rueckadresse_sperre_wird_als_grund_gebucht_nicht_verschluckt(env, grund):
    import output.channels.premium_sms as pm
    from output.channels.base import ChannelBlockedError

    uid = _nutzer(_kennung())
    code = getattr(pm, grund)
    env.fehler["premium_sms"] = ChannelBlockedError(
        "premium_sms", "Sperre", reason_code=code,
    )

    ergebnis = _senden(uid, {"email", "premium_sms"})  # darf NICHT werfen

    assert ergebnis.blocked_reason_codes.get("premium_sms") == code, ergebnis
    assert "premium_sms" in ergebnis.blocked_channels
    assert "premium_sms" in ergebnis.failed_channels
    assert "premium_sms" not in ergebnis.sent_channels
    assert env.anzahl("premium_sms") == 0
    assert _zaehler(uid) == 0


def test_ac3_tageslimit_sperre_steht_nur_in_blocked_und_sendet_nichts(env):
    uid = _nutzer(_kennung())
    _zaehler_schreiben(uid, premium_sms=10_000)

    ergebnis = _senden(uid, {"email", "premium_sms"})

    assert "premium_sms" in ergebnis.blocked_channels, ergebnis
    assert "premium_sms" in ergebnis.blocked_reason_codes
    assert "premium_sms" not in ergebnis.failed_channels
    assert env.anzahl("premium_sms") == 0
    assert "email" in ergebnis.sent_channels


# ---------------------------------------------------------------------------
# AC-4 — Vollstaendigkeits-Waechter ueber ALLE aufloesbaren Kanaele
# ---------------------------------------------------------------------------


def _alle_kanaele():
    from services.alert_channels import _ALL_CHANNELS

    return list(_ALL_CHANNELS)


@pytest.mark.parametrize("kanal", _alle_kanaele())
def test_ac4_compare_briefing_bedient_jeden_aufloesbaren_kanal_oder_bucht_grund(env, kanal):
    uid = _nutzer(_kennung())

    ergebnis = _senden(uid, {kanal})

    bedient = kanal in ergebnis.sent_channels and env.anzahl(kanal) >= 1
    gebucht = kanal in ergebnis.blocked_channels or kanal in ergebnis.failed_channels
    assert bedient or gebucht, (
        f"Kanal {kanal!r} wurde aufgeloest, aber weder bedient noch als Sperre "
        f"gebucht — still verschluckt: {ergebnis}, Mitschrift={env.je_kanal}"
    )


@pytest.mark.parametrize("kanal", _alle_kanaele())
def test_ac4_trip_briefing_bedient_jeden_aufloesbaren_kanal_oder_bucht_grund(env, kanal):
    from tests.tdd.test_sms_tageslimit import _report_request, _trip
    from services.notification_service import NotificationService as NS

    uid = _nutzer(_kennung())
    request = _report_request(
        _trip(f"trip-{uid}"),
        send_email=(kanal == "email"), send_telegram=(kanal == "telegram"),
        send_sms=(kanal == "sms"), send_premium_sms=(kanal == "premium_sms"),
    )
    ergebnis = NS(settings=Settings(), user_id=uid).send_trip_report(request)

    bedient = env.anzahl(kanal) >= 1
    gebucht = kanal in ergebnis.blocked_channels or kanal in ergebnis.failed_channels
    assert bedient or gebucht, (
        f"Trip-Briefing: Kanal {kanal!r} still verschluckt: {ergebnis}, {env.je_kanal}"
    )


# ---------------------------------------------------------------------------
# AC-5 — send_one_compare_preset reicht den Sink durch und warnt
# ---------------------------------------------------------------------------


def _preset(uid: str, **extra) -> dict:
    p = {
        "id": "cp-2275", "name": "Urlaubsorte", "user_id": uid,
        "location_ids": ["loc-ibk", "loc-bz"], "schedule": "daily",
        "profil": "ALLGEMEIN", "hour_from": 9, "hour_to": 16,
        "forecast_hours": 48, "empfaenger": ["gregor-test@henemm.com"],
        "created_at": "2026-07-01T00:00:00Z", "kind": "vergleich",
    }
    p.update(extra)
    return p


def _dp(hour: int) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(2026, 7, 8, hour, 0), t2m_c=22.0, wind_chill_c=21.0,
        wind10m_kmh=11.0, gust_kmh=19.0, precip_1h_mm=0.0, cloud_total_pct=35,
        uv_index=5.0, thunder_level=ThunderLevel.NONE, pop_pct=10, visibility_m=9000,
    )


def _engine_und_anker_naht(monkeypatch) -> None:
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
                        location=loc, score=90 - 7 * i, temp_max=22.0 + i,
                        temp_min=12.0, wind_max=11.0, gust_max=19.0, cloud_avg=35,
                        sunny_hours=6, official_alerts=[],
                        hourly_data=[_dp(9), _dp(12), _dp(15)],
                    )
                    for i, loc in enumerate(list(locations or []))
                ],
                time_window=kwargs.get("time_window", (9, 16)),
                target_date=kwargs.get("target_date", TARGET_DATE),
                created_at=datetime(2026, 7, 8, 4, 0),
            )

    monkeypatch.setattr(ce_mod, "ComparisonEngine", RecordingEngine)
    monkeypatch.setattr(sds_mod, "_write_compare_alert_snapshots", lambda *a, **k: None)


def _orte() -> list[SavedLocation]:
    return [
        SavedLocation(id="loc-ibk", name="Innsbruck", lat=47.27, lon=11.39, elevation_m=1000),
        SavedLocation(id="loc-bz", name="Bozen", lat=46.50, lon=11.35, elevation_m=1000),
    ]


def _preset_senden(uid, tmp_path, **kw):
    from services.scheduler_dispatch_service import send_one_compare_preset

    mails: list = []
    return send_one_compare_preset(
        _preset(uid, send_premium_sms=True), Settings(), uid, str(tmp_path),
        all_locations_cache=_orte(), target_date=TARGET_DATE, tage_ab_ortstag=0,
        mail_sink=lambda **k: mails.append(k), **kw,
    ), mails


def test_ac5_preset_versand_reicht_premium_sms_sink_bis_zum_zweig_durch(
    env, monkeypatch, tmp_path,
):
    _engine_und_anker_naht(monkeypatch)
    uid = _nutzer(_kennung())
    gesehen: list[str] = []

    _preset_senden(uid, tmp_path, premium_sms_sink=gesehen.append)

    assert len(gesehen) == 1 and "Innsbruck" in gesehen[0], gesehen


def test_ac5_gescheiterter_transport_warnt_und_preset_versand_gilt_als_erfolg(
    env, monkeypatch, tmp_path, caplog,
):
    _engine_und_anker_naht(monkeypatch)
    uid = _nutzer(_kennung())
    env.fehler["premium_sms"] = RuntimeError("seven.io kaputt")

    with caplog.at_level(logging.WARNING):
        (top_ort, empfaenger), mails = _preset_senden(uid, tmp_path)  # kein Raise

    assert len(mails) == 1 and empfaenger
    warnungen = [r for r in caplog.records
                 if r.levelno == logging.WARNING and "premium_sms" in r.getMessage()
                 and "cp-2275" in r.getMessage()]
    assert warnungen, "Aufrufer muss mit Preset-ID und Kanal warnen"


# ---------------------------------------------------------------------------
# AC-6 — Mandantentrennung
# ---------------------------------------------------------------------------


def test_ac6_zwei_nutzer_zaehler_und_reservierung_beeinflussen_sich_nicht(env):
    a, b = _nutzer(_kennung()), _nutzer(_kennung())
    _zaehler_schreiben(a, premium_sms=10_000)

    res_a = _senden(a, {"email", "premium_sms"})
    res_b = _senden(b, {"email", "premium_sms"})

    assert "premium_sms" in res_a.blocked_channels
    assert "premium_sms" in res_b.sent_channels
    assert _zaehler(b) == 1
    assert _zaehler(a) == 10_000
    assert _zaehler("default") == 0, "kein Zaehlereintrag unter 'default'"


# ---------------------------------------------------------------------------
# AC-7 — ohne Opt-in bzw. ohne Tier-Freigabe wird nichts gesendet
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("opt_in,tier", [(False, "premium"), (True, "standard")])
def test_ac7_ohne_optin_oder_freigabe_kein_premium_sms_versand(env, opt_in, tier):
    from services.compare_alert_channels import effective_compare_briefing_channels

    uid = _nutzer(_kennung(), tier=tier)
    settings = Settings()
    kanaele = effective_compare_briefing_channels(
        {"send_premium_sms": opt_in}, settings, uid,
    )

    ergebnis = _senden(uid, kanaele)

    assert "premium_sms" not in kanaele
    assert env.anzahl("premium_sms") == 0
    assert "premium_sms" not in ergebnis.sent_channels
    assert _zaehler(uid) == 0


# ---------------------------------------------------------------------------
# AC-8 — Doku
# ---------------------------------------------------------------------------


def test_ac8_claude_md_nennt_premium_sms_als_versandkanal_im_ortsvergleich():  # doc-compliance-test
    zeile = next(
        z for z in (Path(__file__).resolve().parents[2] / "CLAUDE.md")
        .read_text(encoding="utf-8").splitlines()
        if "Premium-SMS-Reichweite" in z
    )
    assert "nur im **Trip-Briefing**" not in zeile
    assert "Ortsvergleich-Briefing" in zeile
