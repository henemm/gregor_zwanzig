"""TDD RED — Ortsvergleich-Versand: Empfaenger kommen IMMER aus den
Konto-Settings, nie aus `preset.empfaenger`.

Spec: docs/specs/modules/fix_1452_compare_empfaenger_settings.md (AC-1..AC-6)

Ist-Zustand (RED-Grund): Alle vier Versandpfade lesen heute ein preset-eigenes
Empfaenger-Override:
  - `compare_alert.py::_notification_service_for` (Z. 294-303)
  - `compare_official_alert.py::_notification_service_for` (Z. 208-217)
  - `compare_radar_alert.py::_notification_service_for` (Z. 169-179)
  - `scheduler_dispatch_service.py::send_one_compare_preset` (Z. 332-339)
jeweils als `preset.get("empfaenger") or settings.mail_to`. Ein Preset mit
gefuelltem `empfaenger` schickt die Mail damit an eine Adresse, die der Nutzer
in seinem Konto nie hinterlegt hat. Soll (analog `trip_alert.py:125`):
ausschliesslich `settings.mail_to`.

KEINE Mocks (CLAUDE.md, Kern-Schicht):
  - Echte Presets/Orte/Snapshots auf Platte unter `data/users/tdd-1452-*`
    (Cleanup per try/finally, Haus-Muster test_compare_alert_metric_gating.py).
  - Deterministische Wetter-/Radar-/Warnungs-Quellen als echte Objekte
    (`_ScriptedSource`, `_CoordFrameSource`, `_FakeOfficialAlertSource`).
  - Der Empfaenger-Nachweis laeuft ueber eine ECHTE Subklasse von
    `NotificationService`, die die tatsaechlich verwendeten Settings bzw. die
    tatsaechlich uebergebene `recipients`-Liste aufzeichnet und danach das
    echte Verhalten der Basisklasse ausfuehrt (Spy auf echtem Code, kein
    `Mock()`/`patch()`/`MagicMock`). Der Transport selbst bleibt ueber die
    etablierte Sink-Naht (`mail_sink`/`sms_sink`/`telegram_sink`) ausgehaengt —
    kein Netz, kein SMTP.
"""
from __future__ import annotations

import json
import logging
import shutil
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.config import Settings
from app.loader import get_data_dir, save_location
from app.models import ForecastDataPoint, ThunderLevel
from app.user import SavedLocation

from tests.helpers.compare_briefings import write_compare_briefings

# Issue #1409: Pruefling relativ zur Testdatei aufloesen, nie ueber den
# festen Hauptrepo-Pfad (sonst falsches Gruen aus einem Worktree heraus).
def _data_root_users() -> Path:
    """Nutzer-Wurzel der Compare-Preset-Ablage — Funktion statt Konstante
    (#1595): ``get_data_root()`` liefert erst zur Laufzeit die von der
    #1133-Fixture gesetzte Basis, eine Konstante waere beim Import gebunden."""
    from app.loader import get_data_root

    return get_data_root() / "users"

SETTINGS_MAIL = "konto-settings@example.invalid"
PRESET_MAIL = "fremde-adresse@example.com"
TARGET_DATE = date(2026, 7, 8)


# ───────────────────────────── Fixtures & Helfer ────────────────────────────

def _uid(suffix: str) -> str:
    return f"tdd-1452-{suffix}-{uuid.uuid4().hex[:6]}"


def _clean_user(user_id: str) -> None:
    d = _data_root_users() / user_id
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)


def _settings(mail_to: str | None = SETTINGS_MAIL, *, all_channels: bool = False) -> Settings:
    """`can_send_email()` == True ohne Netzzugriff (Dummy-Creds werden nie
    gewaehlt, der Sink ersetzt den Transport). `mail_to=None` erzeugt ein
    Konto OHNE hinterlegte Empfaengeradresse."""
    extra = (
        dict(
            telegram_bot_token="dummy-token", telegram_chat_id="123456",
            sms_gateway_url="https://sms.invalid", seven_api_key="k",
            sms_to="+491700000000",
        )
        if all_channels else {}
    )
    return Settings(
        smtp_host="dummy.invalid", smtp_user="dummy", smtp_pass="dummy",
        mail_to=mail_to, **extra,
    )


def _location(loc_id: str, name: str, lat: float, lon: float) -> SavedLocation:
    return SavedLocation(id=loc_id, name=name, lat=lat, lon=lon, elevation_m=1000)


def _preset(preset_id: str, location_ids: list[str], **extra) -> dict:
    """Compare-Preset mit gefuelltem `empfaenger`-Override (der Kern des Bugs)."""
    preset = {
        "id": preset_id, "name": preset_id, "location_ids": list(location_ids),
        "schedule": "daily", "weekday": 4, "profil": "ALLGEMEIN",
        "hour_from": 9, "hour_to": 16,
        "empfaenger": [PRESET_MAIL],
        "created_at": "2026-08-02T00:00:00Z",
        "display_config": {"active_metrics": ["temp_max_c"]},
    }
    preset.update(extra)
    return preset


@contextmanager
def _recorded_settings(module):
    """Zeichnet die Settings auf, mit denen der Dienst seinen
    `NotificationService` tatsaechlich baut — echte Subklasse, die das echte
    Verhalten weiterfuehrt (kein Mock)."""
    from services.notification_service import NotificationService as _Real

    recorded: list[dict] = []

    class _Recording(_Real):
        def __init__(self, settings=None, user_id="default"):
            recorded.append({
                "mail_to": getattr(settings, "mail_to", None),
                "telegram_chat_id": getattr(settings, "telegram_chat_id", None),
                "sms_to": getattr(settings, "sms_to", None),
                "user_id": user_id,
            })
            super().__init__(settings, user_id)

    original = module.NotificationService
    module.NotificationService = _Recording
    try:
        yield recorded
    finally:
        module.NotificationService = original


def _assert_settings_recipient(recorded: list[dict], expected: str, label: str) -> None:
    assert recorded, f"{label}: es wurde ueberhaupt kein Versandobjekt gebaut"
    for entry in recorded:
        assert entry["mail_to"] == expected, (
            f"{label}: Versand-Ziel war {entry['mail_to']!r}, erwartet {expected!r} "
            f"aus den Konto-Settings. `preset.empfaenger` ({PRESET_MAIL!r}) darf "
            "die Empfaengerwahl nicht mehr beeinflussen (Spec AC-1/AC-2)."
        )
        assert PRESET_MAIL not in (entry["mail_to"] or ""), (
            f"{label}: die Preset-Fremdadresse {PRESET_MAIL!r} wurde als Empfaenger benutzt."
        )


# ─────────────────── AC-1: Gewitter-/Δ-Alarm (compare_alert.py) ─────────────

def _point(point_id: str, name: str, lat: float, lon: float, **summary):
    from app.models import SegmentWeatherSummary
    from services.point_weather import PointWeatherData

    return PointWeatherData(
        id=point_id, name=name, lat=lat, lon=lon, timeseries=None,
        aggregated=SegmentWeatherSummary(**summary),
        fetched_at=datetime.now(timezone.utc), provider="test-scripted",
    )


class _ScriptedSource:
    """Deterministischer `LocationWeatherSource` — echtes DTO, kein Mock."""

    def __init__(self, values: dict) -> None:
        self._values = {k: dict(v) for k, v in values.items()}

    def fetch(
        self, point_id: str, lat: float, lon: float,
        start_hour: int | None = None, end_hour: int | None = None,
    ):
        return _point(point_id, point_id, lat, lon, **self._values.get(point_id, {}))


def _run_deviation_alert(uid: str, presets: list[dict], settings: Settings):
    """Fuehrt `CompareAlertService.check_all_compare_presets()` mit verankertem
    Δ-Anker (temp_max_c 10 → 30, Δ=20 > Standardschwelle 10) aus."""
    import services.compare_alert as ca_mod
    from services.compare_alert import CompareAlertService
    from services.compare_weather_snapshot import CompareWeatherSnapshotService

    loc = _location("loc-x", "Vergleichsort", 47.0, 11.0)
    save_location(loc, user_id=uid)
    write_compare_briefings(_data_root_users() / uid, presets)
    for preset in presets:
        CompareWeatherSnapshotService(user_id=uid).save(
            preset["id"], "loc-x",
            _point("loc-x", loc.name, loc.lat, loc.lon, temp_max_c=10.0),
        )
    mails: list = []
    with _recorded_settings(ca_mod) as recorded:
        sent = CompareAlertService(
            settings=settings, user_id=uid,
            weather_source=_ScriptedSource({"loc-x": {"temp_max_c": 30.0}}),
            mail_sink=lambda subject, body: mails.append(subject),
        ).check_all_compare_presets()
    return sent, recorded, mails


def test_ac1_deviation_alert_mail_goes_to_settings_not_preset_empfaenger():
    """AC-1 GIVEN ein Compare-Preset von Nutzer A mit
    `empfaenger=["fremde-adresse@example.com"]` und einem davon abweichenden
    `mail_to` in den Settings von A / WHEN der Δ-/Gewitter-Alarm-Dienst
    (`CompareAlertService`) fuer dieses Preset ausloest / THEN geht die Mail
    ausschliesslich an `settings.mail_to`.

    RED heute: `_notification_service_for` kopiert `preset.empfaenger` in
    `mail_to` → Versand an die Fremdadresse."""
    uid = _uid("ac1")
    _clean_user(uid)
    try:
        sent, recorded, mails = _run_deviation_alert(
            uid, [_preset("cp-1452-ac1", ["loc-x"])], _settings(),
        )
        assert sent == 1 and len(mails) == 1, (
            f"Testvoraussetzung: genau ein Alarm musste ausloesen (sent={sent}, mails={len(mails)})"
        )
        _assert_settings_recipient(recorded, SETTINGS_MAIL, "Δ-Alarm (compare_alert)")
    finally:
        _clean_user(uid)


# ─────────── AC-2: amtliche Warnungen + Radar-Alarm (je ein Dienst) ─────────

class _FakeOfficialAlertSource:
    """Echte Quelle (kein Mock), zustaendig fuer einen Punkt (0.05-Toleranz)."""

    def __init__(self, lat, lon, alerts):
        self._lat, self._lon, self._alerts = lat, lon, alerts

    @property
    def name(self) -> str:
        return "test-1452-source"

    def covers(self, lat, lon) -> bool:
        return abs(lat - self._lat) < 0.05 and abs(lon - self._lon) < 0.05

    def fetch(self, lat, lon):
        return list(self._alerts)


def _official_alert():
    from services.official_alerts.models import OfficialAlert

    now = datetime.now(timezone.utc)
    return OfficialAlert(
        source="test-1452", hazard="extreme_heat", level=2, label="Hitze",
        valid_from=now - timedelta(hours=1), valid_to=now + timedelta(hours=12),
        region_label="Hermagor",
    )


@contextmanager
def _isolated_official_sources():
    import services.official_alerts.base as b

    backup = list(b._REGISTERED_SOURCES)
    b._REGISTERED_SOURCES.clear()
    try:
        yield
    finally:
        b._REGISTERED_SOURCES.clear()
        b._REGISTERED_SOURCES.extend(backup)


def _run_official_alert(uid: str, preset: dict, settings: Settings, **sinks):
    import services.compare_official_alert as co_mod
    from services.compare_official_alert import CompareOfficialAlertService
    from services.official_alerts import register_official_alert_source

    save_location(_location("loc-a", "Hermagor", 46.62, 13.68), user_id=uid)
    write_compare_briefings(_data_root_users() / uid, [preset])
    register_official_alert_source(_FakeOfficialAlertSource(46.62, 13.68, [_official_alert()]))
    with _recorded_settings(co_mod) as recorded:
        sent = CompareOfficialAlertService(
            settings=settings, user_id=uid,
            mail_sink=lambda subject, body: None, **sinks,
        ).check_all_compare_presets()
    return sent, recorded


def test_ac2_official_alert_mail_goes_to_settings_not_preset_empfaenger():
    """AC-2 (amtliche Warnungen) GIVEN dasselbe Szenario wie AC-1 / WHEN
    `CompareOfficialAlertService` einen Alarm ausloest / THEN geht die Mail
    ausschliesslich an `settings.mail_to`.

    RED heute: eigenes `_notification_service_for` mit demselben Override."""
    uid = _uid("ac2-official")
    _clean_user(uid)
    with _isolated_official_sources():
        try:
            sent, recorded = _run_official_alert(uid, _preset("cp-1452-ac2o", ["loc-a"]), _settings())
            assert sent == 1, f"Testvoraussetzung: genau ein amtlicher Alarm (sent={sent})"
            _assert_settings_recipient(recorded, SETTINGS_MAIL, "Amtliche Warnung")
        finally:
            _clean_user(uid)


class _CoordFrameSource:
    """Echter `frame_source`-Doppelgaenger fuer `RadarNowcastService`."""

    def __init__(self, by_coord: dict) -> None:
        self._by_coord = by_coord

    def __call__(self, lat: float, lon: float) -> list:
        return self._by_coord.get((round(lat, 4), round(lon, 4)), [])


def test_ac2_radar_alert_mail_goes_to_settings_not_preset_empfaenger():
    """AC-2 (Radar) GIVEN dasselbe Szenario wie AC-1 / WHEN
    `CompareRadarAlertService` einen Onset-Alarm ausloest / THEN geht die Mail
    ausschliesslich an `settings.mail_to`.

    RED heute: dritte Kopie desselben Overrides."""
    import services.compare_radar_alert as cr_mod
    from providers.brightsky import RadarFrame
    from services.compare_radar_alert import CompareRadarAlertService
    from services.radar_service import RadarNowcastService

    uid = _uid("ac2-radar")
    _clean_user(uid)
    try:
        save_location(_location("loc-r", "Zermatt", 46.0207, 7.7491), user_id=uid)
        write_compare_briefings(_data_root_users() / uid, [
            _preset("cp-1452-ac2r", ["loc-r"], radar_alert_enabled=True),
        ])
        frames = [RadarFrame(
            timestamp=datetime.now(timezone.utc) + timedelta(minutes=8),
            precip_mm_h=0.6, is_convective=False,
        )]
        mails: list = []
        with _recorded_settings(cr_mod) as recorded:
            sent = CompareRadarAlertService(
                settings=_settings(), user_id=uid,
                radar_service=RadarNowcastService(
                    frame_source=_CoordFrameSource({(46.0207, 7.7491): frames}),
                ),
                mail_sink=lambda subject, body: mails.append(subject),
            ).check_all_compare_presets()
        assert sent == 1 and len(mails) == 1, (
            f"Testvoraussetzung: genau ein Radar-Alarm (sent={sent}, mails={len(mails)})"
        )
        _assert_settings_recipient(recorded, SETTINGS_MAIL, "Radar-Alarm")
    finally:
        _clean_user(uid)


# ───────── AC-3: regulaerer Compare-Versand (scheduler_dispatch_service) ─────

def _dp(hour: int) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(TARGET_DATE.year, TARGET_DATE.month, TARGET_DATE.day, hour, 0),
        t2m_c=22.0, wind_chill_c=21.0, wind10m_kmh=11.0, gust_kmh=19.0,
        precip_1h_mm=0.0, cloud_total_pct=35, uv_index=5.0,
        thunder_level=ThunderLevel.NONE, pop_pct=10, visibility_m=9000,
    )


@pytest.fixture
def dispatch_env(tmp_path, monkeypatch):
    """Isolierter Daten-Root (Haus-Muster test_compare_dispatch_channel_fanout.py):
    kein Schreibzugriff auf das echte data/users/, kein Netz (Engine + Snapshot-
    Nachlauf sind echte Ersatz-Implementierungen)."""
    from app import loader as app_loader
    from app.user import ComparisonResult, LocationResult
    import services.comparison_engine as ce_mod
    import services.scheduler_dispatch_service as sds_mod

    data_root = tmp_path / "data"
    data_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(app_loader, "_DATA_ROOT", str(data_root))

    original = ce_mod.ComparisonEngine

    class RecordingEngine(original):  # echte Subklasse, kein Mock
        @staticmethod
        def run(*args, **kwargs):
            locations = kwargs.get("locations") or (args[0] if args else [])
            return ComparisonResult(
                locations=[
                    LocationResult(
                        location=loc, score=90 - 7 * i, temp_max=22.0 + i, temp_min=12.0,
                        wind_max=11.0, gust_max=19.0, cloud_avg=35, sunny_hours=6,
                        official_alerts=[], hourly_data=[_dp(9), _dp(12), _dp(15)],
                    )
                    for i, loc in enumerate(list(locations))
                ],
                time_window=kwargs.get("time_window", (9, 16)),
                target_date=kwargs.get("target_date", TARGET_DATE),
                created_at=datetime(2026, 7, 8, 4, 0),
            )

    monkeypatch.setattr(ce_mod, "ComparisonEngine", RecordingEngine)
    monkeypatch.setattr(sds_mod, "_write_compare_alert_snapshots", lambda *a, **k: None)
    return _uid("ac3"), tmp_path


@contextmanager
def _recorded_recipients():
    """Zeichnet die an `send_compare_report` uebergebene `recipients`-Liste auf —
    das ist die echte Versand-Entscheidung des Dispatch-Pfades."""
    import services.notification_service as ns_mod

    recorded: list[list[str]] = []
    original = ns_mod.NotificationService

    class _Recording(original):
        def send_compare_report(self, **kwargs):
            recorded.append(list(kwargs.get("recipients") or []))
            return super().send_compare_report(**kwargs)

    ns_mod.NotificationService = _Recording
    try:
        yield recorded
    finally:
        ns_mod.NotificationService = original


def test_ac3_dispatch_sends_to_settings_mail_to_not_preset_empfaenger(dispatch_env):
    """AC-3 (Fall 1) GIVEN ein Compare-Preset mit gesetztem `empfaenger` und
    einem abweichenden `mail_to` / WHEN `send_one_compare_preset()` laeuft /
    THEN geht die Mail ausschliesslich an `settings.mail_to`.

    RED heute: `empfaenger = preset.get("empfaenger") or []` gewinnt und wird
    1:1 als `recipients` durchgereicht."""
    from services.scheduler_dispatch_service import send_one_compare_preset

    user_id, tmp_path = dispatch_env
    with _recorded_recipients() as recorded:
        send_one_compare_preset(
            _preset("cp-1452-ac3", ["loc-d"]), _settings(), user_id, str(tmp_path),
            all_locations_cache=[_location("loc-d", "Innsbruck", 47.27, 11.39)],
            target_date=TARGET_DATE, mail_sink=lambda **kw: None,
        )

    assert recorded, "send_compare_report wurde nie aufgerufen"
    assert recorded[0] == [SETTINGS_MAIL], (
        f"Compare-Versand ging an {recorded[0]!r}, erwartet [{SETTINGS_MAIL!r}] aus "
        f"den Konto-Settings. `preset.empfaenger` ({PRESET_MAIL!r}) darf den "
        "Empfaenger nicht mehr bestimmen (Spec AC-3)."
    )


def test_ac3_dispatch_raises_valueerror_when_mail_to_missing(dispatch_env):
    """AC-3 (Fall 2) GIVEN ein Konto OHNE `mail_to` / WHEN
    `send_one_compare_preset()` laeuft / THEN wirft der Dienst weiterhin
    `ValueError` — kein stiller Erfolg, auch nicht mit gefuelltem
    `preset.empfaenger` (das Feld ist nach dem Fix inert)."""
    from services.scheduler_dispatch_service import send_one_compare_preset

    user_id, tmp_path = dispatch_env
    with pytest.raises(ValueError):
        send_one_compare_preset(
            _preset("cp-1452-ac3b", ["loc-d"]), _settings(mail_to=None), user_id,
            str(tmp_path),
            all_locations_cache=[_location("loc-d", "Innsbruck", 47.27, 11.39)],
            target_date=TARGET_DATE, mail_sink=lambda **kw: None,
        )


# ───────── AC-4: fehlendes mail_to → Warnung statt stillem Skip, kein Abbruch ─

def test_ac4_missing_mail_to_logs_warning_per_preset_and_run_continues(caplog):
    """AC-4 GIVEN ein Konto OHNE `mail_to` und ZWEI ausloesende Compare-Presets /
    WHEN der Δ-Alarm-Lauf beide verarbeitet / THEN bricht der Lauf nicht ab
    (kein Crash, beide Presets werden angefasst) und fuer JEDES betroffene
    Preset steht eine `logger.warning`-Zeile mit User- und Preset-Bezug im Log.

    RED heute: `preset.empfaenger` macht das Konto faelschlich sendefaehig —
    es gehen zwei Mails an die Fremdadresse raus statt gar keiner, und es gibt
    keine einzige WARNING-Zeile (stiller Skip war der Ist-Zustand, sobald auch
    `empfaenger` leer ist)."""
    uid = _uid("ac4")
    _clean_user(uid)
    try:
        presets = [_preset("cp-1452-ac4-a", ["loc-x"]), _preset("cp-1452-ac4-b", ["loc-x"])]
        with caplog.at_level(logging.WARNING, logger="compare_alert"):
            sent, _recorded, mails = _run_deviation_alert(uid, presets, _settings(mail_to=None))

        assert sent == 0 and mails == [], (
            "Ohne mail_to darf keine Mail rausgehen — der Lauf darf aber auch "
            f"nicht crashen (sent={sent}, mails={len(mails)})."
        )
        # Die Warnung fuer BEIDE Presets belegt zugleich, dass der Lauf nach dem
        # ersten fehlerhaften Preset weitergelaufen ist (kein Abbruch, AC-4).
        warnings = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
        for preset_id in ("cp-1452-ac4-a", "cp-1452-ac4-b"):
            assert any(preset_id in m and uid in m for m in warnings), (
                f"Keine WARNING mit User- ({uid}) und Preset-Bezug ({preset_id}) "
                f"bei fehlendem mail_to. Geloggt wurde: {warnings!r}. "
                "Der stille Skip ist laut Spec AC-4 nicht mehr zulaessig."
            )
    finally:
        _clean_user(uid)


# ───────────────────────── AC-5: Mandantentrennung ──────────────────────────

def test_ac5_two_users_each_receive_only_their_own_settings_mail_to():
    """AC-5 GIVEN zwei Compare-Presets von zwei VERSCHIEDENEN Nutzern (je
    eigenes `mail_to`, beide mit derselben Fremdadresse in `empfaenger`) /
    WHEN derselbe Alarm-Typ beide verarbeitet / THEN geht die Mail von Nutzer A
    ausschliesslich an `mail_to` von A und die von B ausschliesslich an das von
    B — kein Cross-User-Leck, kein `"default"`-Rueckfall (CLAUDE.md-Pflicht:
    jeder datenbewegende Pfad wird mit zwei echten user_ids geprueft).

    RED heute: beide Laeufe landen bei der IDENTISCHEN Preset-Fremdadresse."""
    mail_a, mail_b = "user-a@example.invalid", "user-b@example.invalid"
    uid_a, uid_b = _uid("ac5-a"), _uid("ac5-b")
    _clean_user(uid_a)
    _clean_user(uid_b)
    try:
        sent_a, rec_a, _ = _run_deviation_alert(
            uid_a, [_preset("cp-1452-ac5-a", ["loc-x"])], _settings(mail_to=mail_a),
        )
        sent_b, rec_b, _ = _run_deviation_alert(
            uid_b, [_preset("cp-1452-ac5-b", ["loc-x"])], _settings(mail_to=mail_b),
        )
        assert sent_a == 1 and sent_b == 1, (
            f"Testvoraussetzung: beide Nutzer loesen aus (A={sent_a}, B={sent_b})"
        )
        _assert_settings_recipient(rec_a, mail_a, "Nutzer A")
        _assert_settings_recipient(rec_b, mail_b, "Nutzer B")
        assert rec_a[0]["user_id"] == uid_a and rec_b[0]["user_id"] == uid_b, (
            f"user_id-Durchreichung verletzt: A={rec_a[0]['user_id']!r}, B={rec_b[0]['user_id']!r}"
        )
        assert mail_b not in (rec_a[0]["mail_to"] or "") and mail_a not in (rec_b[0]["mail_to"] or ""), (
            "Cross-User-Leck: die Adresse des anderen Nutzers wurde beliefert."
        )
    finally:
        _clean_user(uid_a)
        _clean_user(uid_b)


# ───────── AC-6: Telegram/SMS bleiben unveraendert (Nicht-Regression) ────────

def test_ac6_telegram_and_sms_still_use_settings_channels_unchanged():
    """AC-6 GIVEN ein Preset mit `send_telegram`/`send_sms`-Opt-in und
    gefuelltem `empfaenger` / WHEN ein amtlicher Alarm ausloest / THEN gehen
    Telegram und SMS unveraendert an `settings.telegram_chat_id` bzw.
    `settings.sms_to` — das E-Mail-Override hat diese Kanaele nie beruehrt und
    darf es auch nach dem Fix nicht.

    Schutz-Test: schon HEUTE gruen, sichert die Implementierungsphase ab."""
    uid = _uid("ac6")
    _clean_user(uid)
    with _isolated_official_sources():
        try:
            user_json = get_data_dir(uid) / "user.json"
            user_json.parent.mkdir(parents=True, exist_ok=True)
            user_json.write_text(json.dumps({"tier": "premium"}), encoding="utf-8")

            tg_calls, sms_calls = [], []
            settings = _settings(all_channels=True)
            sent, recorded = _run_official_alert(
                uid,
                _preset("cp-1452-ac6", ["loc-a"], send_telegram=True, send_sms=True),
                settings,
                telegram_sink=lambda text: tg_calls.append(text),
                sms_sink=lambda text: sms_calls.append(text),
            )
            assert sent == 1, f"Testvoraussetzung: ein amtlicher Alarm (sent={sent})"
            assert len(tg_calls) == 1, f"Telegram-Zustellungen: {len(tg_calls)}, erwartet 1"
            assert len(sms_calls) == 1, f"SMS-Zustellungen: {len(sms_calls)}, erwartet 1"
            assert recorded[0]["telegram_chat_id"] == settings.telegram_chat_id, (
                f"Telegram-Ziel verbogen: {recorded[0]['telegram_chat_id']!r}"
            )
            assert recorded[0]["sms_to"] == settings.sms_to, (
                f"SMS-Ziel verbogen: {recorded[0]['sms_to']!r}"
            )
        finally:
            _clean_user(uid)
