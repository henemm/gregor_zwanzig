"""Ortsvergleich-Standalone-Alarm für amtliche Warnungen (#1216 Slice 2a).

SPEC: docs/specs/modules/issue_1216_slice2_compare_official_alert.md (AC-1..AC-8)

RED-Phase: `CompareOfficialAlertService`, `build_compare_official_alert_notices`
und `NotificationService.send_multi_location_official_alert` existieren noch
nicht → ImportError/AttributeError bei jedem Test.

Verhaltenstests — KEINE Mocks. Echte Fake-`OfficialAlertSource` (strukturelles
Subtyping, register_official_alert_source, Muster #1088), echte Presets/Orte auf
Platte, echte alert_state-Persistenz, mail_sink/sms_sink/telegram_sink-DI-Seams
(Muster CompareAlertService/test_compare_radar_alert). Der echte Zustellnachweis
folgt in der Validate-Phase.
"""
from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.config import Settings
from app.loader import get_data_dir, save_location
from app.user import SavedLocation
from services.official_alerts.models import OfficialAlert

from tests.helpers.compare_briefings import write_compare_briefings

DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "users"

# Zwei Orte mit klar getrennten Koordinaten (Toleranz der Fake-Quelle 0.05).
LAT_A, LON_A = 46.62, 13.68   # Hermagor
LAT_B, LON_B = 46.60, 13.20   # St. Stefan im Gailtal

# Issue #1316 (AC-8): einmal beim Modul-Import berechnet, damit mehrere
# _alert()-Aufrufe mit Default-Werten exakt identische Zeitraeume liefern
# (Dedup-Vergleiche in build_compare_official_alert_notices vergleichen
# (valid_from, valid_to)) -- analog zu den vorher fest verdrahteten Konstanten
# (2026-07-11 00:00-23:59), jetzt relativ zur echten Ausfuehrungszeit, damit
# der neue Default-Zeitfenster-Filter [now, +inf) sie nicht ausfiltert.
_NOW = datetime.now(timezone.utc)
_DEFAULT_VALID_FROM = _NOW - timedelta(hours=1)
_DEFAULT_VALID_TO = _NOW + timedelta(hours=23, minutes=59)


def _clean_user(user_id: str) -> None:
    d = DATA_ROOT / user_id
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)


def _uid(prefix: str) -> str:
    return f"tdd-1216s2-{prefix}-{uuid.uuid4().hex[:6]}"


def _settings_all_channels() -> Settings:
    """can_send_email/telegram/sms == True ohne Netzwerk — die Sinks ersetzen
    den Versand vollständig; Dummy-Creds werden nie gewählt."""
    return Settings(
        smtp_host="dummy.invalid", smtp_user="dummy", smtp_pass="dummy",
        mail_to="dummy@example.com",
        telegram_bot_token="dummy-token", telegram_chat_id="123456",
        sms_gateway_url="https://sms.invalid", seven_api_key="k", sms_to="+491700000000",
    )


def _write_user_tier(user_id: str, tier: str = "premium") -> None:
    # user_tier.sms_allowed() liest seit #1265 über get_data_dir() (isolierter
    # Root, #1133) — die user.json muss demselben Pfad folgen, sonst greift das
    # Tier-Gate nicht und SMS/Telegram werden fälschlich unterdrückt.
    p = get_data_dir(user_id) / "user.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"tier": tier}), encoding="utf-8")


def _location(loc_id: str, name: str, lat: float, lon: float) -> SavedLocation:
    return SavedLocation(id=loc_id, name=name, lat=lat, lon=lon, elevation_m=1000)


def _preset(preset_id, location_ids, empfaenger, *, triggers_enabled=None,
            send_telegram=None, send_sms=None, name=None, schedule="daily",
            archived_at=None, alert_quiet_from=None, alert_quiet_to=None) -> dict:
    # Issue #1233: der Default war frueher "manual" (beliebig gewaehlt, bevor
    # "manual" eine Gating-Bedeutung hatte). Seit #1233 heisst schedule=="manual"
    # "Ortsvergleich deaktiviert" -> Default hier auf "daily" (aktiv) umgestellt,
    # damit die bestehenden (nicht schedule-bezogenen) Tests dieser Datei nach
    # dem Fix weiterhin einen aktiven Versand erwarten duerfen. Tests, die den
    # Deaktivierungs-Pfad pruefen, setzen `schedule="manual"` explizit.
    p: dict = {
        "id": preset_id, "name": name or preset_id, "user_id": "default",
        "location_ids": location_ids, "schedule": schedule, "weekday": 4,
        "profil": "ALLGEMEIN", "hour_from": 9, "hour_to": 16,
        "empfaenger": empfaenger, "created_at": "2026-07-11T00:00:00Z",
    }
    if triggers_enabled is not None:
        p["official_alert_triggers_enabled"] = triggers_enabled
    if send_telegram is not None:
        p["send_telegram"] = send_telegram
    if send_sms is not None:
        p["send_sms"] = send_sms
    if archived_at is not None:
        p["archived_at"] = archived_at
    if alert_quiet_from is not None:
        p["alert_quiet_from"] = alert_quiet_from
    if alert_quiet_to is not None:
        p["alert_quiet_to"] = alert_quiet_to
    return p


def _write_presets(user_id: str, presets: list[dict]) -> None:
    # Issue #1250 S7b Cutover: per-Datei briefings/<id>.json (kind="vergleich").
    write_compare_briefings(DATA_ROOT / user_id, presets)


def _alert(level=2, hazard="extreme_heat", label="Hitze", region="Hermagor",
           vf=None, vt=None) -> OfficialAlert:
    return OfficialAlert(
        source="test-1216s2", hazard=hazard, level=level, label=label,
        valid_from=vf or _DEFAULT_VALID_FROM,
        valid_to=vt or _DEFAULT_VALID_TO,
        region_label=region,
    )


class _FakeOfficialAlertSource:
    """Echte Quelle (kein Mock): zuständig für einen Punkt (0.05-Toleranz),
    liefert steuerbare Alerts, zählt fetch()-Aufrufe (AC-6)."""

    def __init__(self, lat, lon, alerts):
        self._lat, self._lon, self._alerts = lat, lon, alerts
        self.fetch_calls = 0

    @property
    def name(self) -> str:
        return "test-1216s2-source"

    def covers(self, lat, lon) -> bool:
        return abs(lat - self._lat) < 0.05 and abs(lon - self._lon) < 0.05

    def fetch(self, lat, lon):
        self.fetch_calls += 1
        return list(self._alerts)


def _sources_backup():
    import services.official_alerts.base as b
    return b, list(b._REGISTERED_SOURCES)


# ═══════════════════════════ AC-1 — Trigger + State ═══════════════════════════
def test_ac1_new_warning_triggers_one_bundled_alert_and_state():
    from services.alert_state import AlertStateService
    from services.compare_official_alert import CompareOfficialAlertService
    from services.official_alerts import register_official_alert_source

    uid = _uid("ac1")
    _clean_user(uid)
    b, backup = _sources_backup()
    b._REGISTERED_SOURCES.clear()
    try:
        save_location(_location("loc-a", "Hermagor", LAT_A, LON_A), user_id=uid)
        save_location(_location("loc-b", "St. Stefan", LAT_B, LON_B), user_id=uid)
        _write_presets(uid, [_preset("p1", ["loc-a", "loc-b"], ["e@x.invalid"])])
        register_official_alert_source(_FakeOfficialAlertSource(LAT_A, LON_A, [_alert()]))

        mail_calls: list = []
        svc = CompareOfficialAlertService(
            settings=_settings_all_channels(), user_id=uid,
            mail_sink=lambda subject, body: mail_calls.append((subject, body)),
        )
        sent = svc.check_all_compare_presets()

        assert sent == 1, f"Erwartet genau 1 gebündelter Alarm, erhalten: {sent}"
        assert len(mail_calls) == 1
        state = AlertStateService(user_id=uid).load("p1:loc-a")
        assert any(k.startswith("official_alert:") for k in state), (
            f"State-Key official_alert:* fehlt: {list(state)!r}"
        )
    finally:
        b._REGISTERED_SOURCES.clear()
        b._REGISTERED_SOURCES.extend(backup)
        _clean_user(uid)


# ═══════════════════════ AC-2 — Orts-Scope + Dedup (rein) ═════════════════════
def test_ac2_location_scope_dedup_and_free_chip():
    from output.renderers.alert.official_alerts import (
        build_compare_official_alert_notices, render_official_alert_html,
        render_official_alert_subject,
    )
    # Zwei getrennte Orte (keine Namensduplikate) -> ID == Name genuegt hier.
    id_to_name = {"Hermagor": "Hermagor", "St. Stefan": "St. Stefan"}

    # Fall 1: dieselbe Warnung an BEIDEN Orten -> 1 Notice, "alle Orte".
    tagged_all = [(_alert(region="Gailtal"), ["Hermagor"]),
                  (_alert(region="Gailtal"), ["St. Stefan"])]
    notices = build_compare_official_alert_notices(
        ["Hermagor", "St. Stefan"], id_to_name, tagged_all,
    )
    assert len(notices) == 1, f"Dedup fehlgeschlagen: {len(notices)} Notices"
    subj = render_official_alert_subject(notices, prefix="Vergleich")
    assert "alle Orte" in subj, f"Erwartet 'alle Orte' im Betreff: {subj!r}"

    # Fall 2: nur Ort B betroffen -> "nur St. Stefan"; seit #1238 (AC-12) zeigt der
    # Ortsvergleich AUSSCHLIESSLICH die betroffenen Orte als Chips — der unbetroffene
    # Ort erscheint NICHT mehr als durchgestrichener freier Chip (das Chip-Muster
    # "übrige Strecke frei" gehoert zur Trip-Route, nicht zu einer Ortsliste).
    tagged_b = [(_alert(region="Gailtal"), ["St. Stefan"])]
    notices_b = build_compare_official_alert_notices(
        ["Hermagor", "St. Stefan"], id_to_name, tagged_b,
    )
    subj_b = render_official_alert_subject(notices_b, prefix="Vergleich")
    assert "St. Stefan" in subj_b and "alle Orte" not in subj_b
    html_b = render_official_alert_html(
        notices_b, source_label="GeoSphere Austria", stand_at="09:30", tz=timezone.utc,
    )
    assert "St. Stefan" in html_b, "Betroffener Ort fehlt als Chip"
    assert "line-through" not in html_b, "Durchgestrichener freier Orts-Chip (AC-12)"
    assert "Hermagor" not in html_b, "Unbetroffener Ort erscheint weiterhin als Chip"


# ═══════════════ AC-3 — alle drei Kanäle gebündelt bei Opt-in ═════════════════
def test_ac3_all_three_channels_dispatched_when_opted_in():
    from services.compare_official_alert import CompareOfficialAlertService
    from services.official_alerts import register_official_alert_source

    uid = _uid("ac3")
    _clean_user(uid)
    b, backup = _sources_backup()
    b._REGISTERED_SOURCES.clear()
    try:
        _write_user_tier(uid, "premium")  # sms_allowed True
        save_location(_location("loc-a", "Hermagor", LAT_A, LON_A), user_id=uid)
        _write_presets(uid, [_preset(
            "p1", ["loc-a"], ["e@x.invalid"], send_telegram=True, send_sms=True,
        )])
        register_official_alert_source(_FakeOfficialAlertSource(LAT_A, LON_A, [_alert()]))

        mail_calls, sms_calls, tg_calls = [], [], []
        svc = CompareOfficialAlertService(
            settings=_settings_all_channels(), user_id=uid,
            mail_sink=lambda subject, body: mail_calls.append(body),
            sms_sink=lambda text: sms_calls.append(text),
            telegram_sink=lambda text: tg_calls.append(text),
        )
        svc.check_all_compare_presets()

        assert len(mail_calls) == 1, f"E-Mail: {len(mail_calls)}"
        assert len(tg_calls) == 1, f"Telegram: {len(tg_calls)}"
        assert len(sms_calls) == 1, f"SMS: {len(sms_calls)}"
        assert len(sms_calls[0]) <= 140 and sms_calls[0].isascii()
    finally:
        b._REGISTERED_SOURCES.clear()
        b._REGISTERED_SOURCES.extend(backup)
        _clean_user(uid)


# ═════════ F006 — gleichnamige Orte: Scope/Betreff NICHT fälschlich "alle Orte" ═
def test_f006_duplicate_names_partial_scope_not_all_locations():
    """F006 (HIGH, Adversary): Zwei gleichnamige Orte, Warnung nur am ersten →
    der Betreff darf NICHT „alle Orte" behaupten (nur einer ist betroffen).
    Die Scope-Rechnung muss über Orts-IDs laufen, nicht über Namen.

    #1238 AC-12 (angepasst): der unbetroffene Ort erscheint NICHT mehr als
    durchgestrichener freier Chip — der Ortsvergleich zeigt nur die betroffenen
    Orte. Die F006-Invariante selbst (ID-basierter Scope statt Namens-Scope)
    wird jetzt an der Chip-ANZAHL geprüft: genau ein betroffener Ort, obwohl
    beide Orte denselben Namen tragen."""
    from bs4 import BeautifulSoup

    from services.compare_official_alert import CompareOfficialAlertService
    from services.official_alerts import register_official_alert_source

    uid = _uid("f006")
    _clean_user(uid)
    b, backup = _sources_backup()
    b._REGISTERED_SOURCES.clear()
    try:
        save_location(_location("loc-a", "Hütte", LAT_A, LON_A), user_id=uid)
        save_location(_location("loc-b", "Hütte", LAT_B, LON_B), user_id=uid)
        _write_presets(uid, [_preset("p1", ["loc-a", "loc-b"], ["e@x.invalid"])])
        register_official_alert_source(
            _FakeOfficialAlertSource(LAT_A, LON_A, [_alert(region="RegionA")])
        )
        mail_calls: list = []
        subjects: list = []
        CompareOfficialAlertService(
            settings=_settings_all_channels(), user_id=uid,
            mail_sink=lambda subject, body: (subjects.append(subject), mail_calls.append(body)),
        ).check_all_compare_presets()

        assert len(mail_calls) == 1
        assert "alle Orte" not in subjects[0], (
            f"Nur ein Ort betroffen — Betreff darf nicht 'alle Orte' sagen: {subjects[0]!r}"
        )
        assert "line-through" not in mail_calls[0], (
            "Durchgestrichener freier Orts-Chip im Ortsvergleich (AC-12)"
        )
        chips = BeautifulSoup(mail_calls[0], "html.parser").select("div.warn span.seg")
        assert [c.get_text(strip=True) for c in chips] == ["Hütte"], (
            "Genau EIN betroffener Ort erwartet (ID-basierter Scope trotz gleicher "
            f"Namen): {[c.get_text(strip=True) for c in chips]!r}"
        )
    finally:
        b._REGISTERED_SOURCES.clear()
        b._REGISTERED_SOURCES.extend(backup)
        _clean_user(uid)


# ═════════ F005 — gleichnamige Orte: State an den RICHTIGEN Ort ═══════════════
def test_f005_duplicate_location_names_state_attributed_to_correct_id():
    """F005 (HIGH, Adversary): Zwei Orte mit gleichem Namen, Warnung nur am
    ERSTEN (loc-a). Der alert_state muss unter `{preset}:loc-a` landen, NICHT
    unter loc-b — sonst Dauer-Spam (loc-a nie 'gemerkt') und stille
    Unterdrückung einer echten neuen Warnung an loc-b (sicherheitsrelevant)."""
    from services.alert_state import AlertStateService
    from services.compare_official_alert import CompareOfficialAlertService
    from services.official_alerts import register_official_alert_source

    uid = _uid("f005")
    _clean_user(uid)
    b, backup = _sources_backup()
    b._REGISTERED_SOURCES.clear()
    try:
        # Gleicher NAME, verschiedene id + Koordinaten.
        save_location(_location("loc-a", "Hütte", LAT_A, LON_A), user_id=uid)
        save_location(_location("loc-b", "Hütte", LAT_B, LON_B), user_id=uid)
        _write_presets(uid, [_preset("p1", ["loc-a", "loc-b"], ["e@x.invalid"])])
        # Quelle deckt NUR loc-a ab.
        register_official_alert_source(
            _FakeOfficialAlertSource(LAT_A, LON_A, [_alert(region="RegionA")])
        )
        CompareOfficialAlertService(
            settings=_settings_all_channels(), user_id=uid,
            mail_sink=lambda subject, body: None,
        ).check_all_compare_presets()

        st_a = AlertStateService(user_id=uid).load("p1:loc-a")
        st_b = AlertStateService(user_id=uid).load("p1:loc-b")
        assert any(k.startswith("official_alert:") for k in st_a), (
            f"Warnung an loc-a muss im State von loc-a stehen, ist aber leer: {st_a!r}"
        )
        assert not any(k.startswith("official_alert:") for k in st_b), (
            f"loc-b (keine Warnung) darf keinen Warn-State tragen: {st_b!r}"
        )
    finally:
        b._REGISTERED_SOURCES.clear()
        b._REGISTERED_SOURCES.extend(backup)
        _clean_user(uid)


# ═══════════ F001 — Zeitzone: Compare-Alarm lokalisiert (kein UTC-Bug) ═════════
def test_f001_compare_alert_localizes_validity_to_location_timezone():
    """F001 (CRITICAL, Adversary): `send_multi_location_official_alert` darf die
    Gültigkeitszeiten NICHT roh in UTC rendern. Hermagor (46.62,13.68) →
    Europe/Vienna (+2 im Sommer): 12:00 UTC → 14:00 lokal."""
    from services.compare_official_alert import CompareOfficialAlertService
    from services.official_alerts import register_official_alert_source

    uid = _uid("f001")
    _clean_user(uid)
    b, backup = _sources_backup()
    b._REGISTERED_SOURCES.clear()
    try:
        save_location(_location("loc-a", "Hermagor", LAT_A, LON_A), user_id=uid)
        _write_presets(uid, [_preset("p1", ["loc-a"], ["e@x.invalid"])])
        # Issue #1316 (AC-8): relativer statt fixer Tag (der neue Default-
        # Zeitfenster-Filter wuerde ein Vergangenheitsdatum ausfiltern) -- Stunde
        # bleibt exakt 12:00/18:00 UTC, damit die 14:00/20:00-Lokalisierungs-
        # Assertion (Europe/Vienna, +2 im Sommer) unveraendert gilt.
        tomorrow = datetime.now(timezone.utc).date() + timedelta(days=1)
        vf = datetime(tomorrow.year, tomorrow.month, tomorrow.day, 12, 0, tzinfo=timezone.utc)
        vt = datetime(tomorrow.year, tomorrow.month, tomorrow.day, 18, 0, tzinfo=timezone.utc)
        register_official_alert_source(
            _FakeOfficialAlertSource(LAT_A, LON_A, [_alert(vf=vf, vt=vt)])
        )
        mail_calls: list = []
        CompareOfficialAlertService(
            settings=_settings_all_channels(), user_id=uid,
            mail_sink=lambda subject, body: mail_calls.append(body),
        ).check_all_compare_presets()

        assert len(mail_calls) == 1
        body = mail_calls[0]
        assert "14:00" in body and "20:00" in body, (
            f"Gültigkeit muss auf Europe/Vienna lokalisiert sein (14:00–20:00): {body!r}"
        )
        assert "12:00" not in body, "Rohe UTC-Zeit (12:00) im Body — F001-Regress"
    finally:
        b._REGISTERED_SOURCES.clear()
        b._REGISTERED_SOURCES.extend(backup)
        _clean_user(uid)


# ═══════════════════ AC-4 — Dedup über Runden + Eskalation ════════════════════
def test_ac4_dedup_then_escalation_refires():
    from services.compare_official_alert import CompareOfficialAlertService
    from services.official_alerts import register_official_alert_source

    uid = _uid("ac4")
    _clean_user(uid)
    b, backup = _sources_backup()
    b._REGISTERED_SOURCES.clear()
    try:
        save_location(_location("loc-a", "Hermagor", LAT_A, LON_A), user_id=uid)
        _write_presets(uid, [_preset("p1", ["loc-a"], ["e@x.invalid"])])
        src = _FakeOfficialAlertSource(LAT_A, LON_A, [_alert(level=2)])
        register_official_alert_source(src)

        def _svc():
            return CompareOfficialAlertService(
                settings=_settings_all_channels(), user_id=uid,
                mail_sink=lambda subject, body: None,
            )
        # Cooldown umgehen: je Runde neue Instanz + ThrottleStore ist preset-weit;
        # Test setzt cooldown effektiv 0 über fehlendes alert_cooldown_minutes? Nein —
        # Default 120. Darum prüfen wir die DETECT-Ebene über den State-Effekt:
        r1 = _svc().check_all_compare_presets()
        assert r1 == 1, f"Runde 1 (neu) muss feuern: {r1}"
        # Runde 2: unveränderte Stufe → Dedup (kein neuer Trigger).
        r2 = _svc().check_all_compare_presets()
        assert r2 == 0, f"Runde 2 (unverändert) darf nicht feuern (Dedup): {r2}"
        # Runde 3: Eskalation auf ORANGE.
        src._alerts = [_alert(level=3, label="Hitze")]
        r3 = _svc().check_all_compare_presets()
        assert r3 == 1, f"Runde 3 (Eskalation) muss erneut feuern: {r3}"
    finally:
        b._REGISTERED_SOURCES.clear()
        b._REGISTERED_SOURCES.extend(backup)
        _clean_user(uid)


# ═══════════════════ AC-5 — Default = nur E-Mail (kein Opt-in) ════════════════
def test_ac5_default_email_only():
    from services.compare_official_alert import CompareOfficialAlertService
    from services.official_alerts import register_official_alert_source

    uid = _uid("ac5")
    _clean_user(uid)
    b, backup = _sources_backup()
    b._REGISTERED_SOURCES.clear()
    try:
        _write_user_tier(uid, "premium")
        save_location(_location("loc-a", "Hermagor", LAT_A, LON_A), user_id=uid)
        # KEIN send_telegram/send_sms → Default aus.
        _write_presets(uid, [_preset("p1", ["loc-a"], ["e@x.invalid"])])
        register_official_alert_source(_FakeOfficialAlertSource(LAT_A, LON_A, [_alert()]))

        mail_calls, sms_calls, tg_calls = [], [], []
        svc = CompareOfficialAlertService(
            settings=_settings_all_channels(), user_id=uid,
            mail_sink=lambda subject, body: mail_calls.append(body),
            sms_sink=lambda text: sms_calls.append(text),
            telegram_sink=lambda text: tg_calls.append(text),
        )
        svc.check_all_compare_presets()

        assert len(mail_calls) == 1
        assert tg_calls == [] and sms_calls == [], (
            f"Ohne Opt-in nur E-Mail; tg={tg_calls!r} sms={sms_calls!r}"
        )
    finally:
        b._REGISTERED_SOURCES.clear()
        b._REGISTERED_SOURCES.extend(backup)
        _clean_user(uid)


# ═══════════════════ AC-6 — Toggle aus → kein Fetch ═══════════════════════════
def test_ac6_trigger_toggle_disabled_no_fetch():
    from services.compare_official_alert import CompareOfficialAlertService
    from services.official_alerts import register_official_alert_source

    uid = _uid("ac6")
    _clean_user(uid)
    b, backup = _sources_backup()
    b._REGISTERED_SOURCES.clear()
    try:
        save_location(_location("loc-a", "Hermagor", LAT_A, LON_A), user_id=uid)
        _write_presets(uid, [_preset(
            "p1", ["loc-a"], ["e@x.invalid"], triggers_enabled=False,
        )])
        src = _FakeOfficialAlertSource(LAT_A, LON_A, [_alert()])
        register_official_alert_source(src)

        svc = CompareOfficialAlertService(
            settings=_settings_all_channels(), user_id=uid,
            mail_sink=lambda subject, body: None,
        )
        sent = svc.check_all_compare_presets()

        assert src.fetch_calls == 0, (
            f"official_alert_triggers_enabled=False muss den Fetch verhindern, "
            f"fetch_calls={src.fetch_calls}"
        )
        assert sent == 0
    finally:
        b._REGISTERED_SOURCES.clear()
        b._REGISTERED_SOURCES.extend(backup)
        _clean_user(uid)


# ═══════════════════ AC-7 — Multi-User-Isolation ═════════════════════════════
def test_ac7_two_users_isolated():
    from services.alert_state import AlertStateService
    from services.compare_official_alert import CompareOfficialAlertService
    from services.official_alerts import register_official_alert_source

    u1, u2 = _uid("ac7a"), _uid("ac7b")
    _clean_user(u1)
    _clean_user(u2)
    b, backup = _sources_backup()
    b._REGISTERED_SOURCES.clear()
    try:
        for uid in (u1, u2):
            save_location(_location("loc-a", "Hermagor", LAT_A, LON_A), user_id=uid)
            _write_presets(uid, [_preset("p1", ["loc-a"], [f"{uid}@x.invalid"])])
        register_official_alert_source(_FakeOfficialAlertSource(LAT_A, LON_A, [_alert()]))

        m1, m2 = [], []
        CompareOfficialAlertService(
            settings=_settings_all_channels(), user_id=u1,
            mail_sink=lambda subject, body: m1.append(body),
        ).check_all_compare_presets()
        CompareOfficialAlertService(
            settings=_settings_all_channels(), user_id=u2,
            mail_sink=lambda subject, body: m2.append(body),
        ).check_all_compare_presets()

        assert len(m1) == 1 and len(m2) == 1
        # State pro Nutzer getrennt (kein Cross-User-Leck).
        assert AlertStateService(user_id=u1).load("p1:loc-a")
        assert AlertStateService(user_id=u2).load("p1:loc-a")
    finally:
        b._REGISTERED_SOURCES.clear()
        b._REGISTERED_SOURCES.extend(backup)
        _clean_user(u1)
        _clean_user(u2)


# ═══════════════════ AC-8 — Scheduler-Endpoint ══════════════════════════════
def test_ac8_scheduler_endpoint_delegates():
    from fastapi.testclient import TestClient

    from api.main import app
    from services.official_alerts import register_official_alert_source

    uid = _uid("ac8")
    _clean_user(uid)
    b, backup = _sources_backup()
    b._REGISTERED_SOURCES.clear()
    try:
        save_location(_location("loc-a", "Hermagor", LAT_A, LON_A), user_id=uid)
        _write_presets(uid, [_preset("p1", ["loc-a"], ["e@x.invalid"])])
        register_official_alert_source(_FakeOfficialAlertSource(LAT_A, LON_A, [_alert()]))

        client = TestClient(app)
        resp = client.post(f"/api/scheduler/compare-official-alert-checks?user_id={uid}")
        assert resp.status_code == 200, f"Endpoint fehlt/Fehler: {resp.status_code} {resp.text[:200]}"
        data = resp.json()
        # Delegation an den Service → numerische Alarm-Anzahl (hier 1).
        count = data if isinstance(data, int) else data.get("sent", data.get("count"))
        assert count == 1, f"Erwartet 1 versendeter Alarm über Endpoint, erhalten: {data!r}"
    finally:
        b._REGISTERED_SOURCES.clear()
        b._REGISTERED_SOURCES.extend(backup)
        _clean_user(uid)


# ═══════════════════════════════════════════════════════════════════════════
# #1233 AC-1..AC-5 — Versand-Gating: Ruhezeiten + Deaktivierung (Bug-Repro)
#
# Symptom (docs/context/fix-1233-compare-official-alert.md): ein deaktivierter
# Ortsvergleich (schedule="manual") sandte um 00:00 Uhr (Ruhezeit) trotzdem
# eine amtliche-Warnung-Mail. `_check_one_preset` prueft heute weder Ruhezeiten
# noch schedule/archived_at -> alle Tests unten sind RED bis zur Implementierung.
# ═══════════════════════════════════════════════════════════════════════════

def _freeze_compare_official_alert_now(monkeypatch, frozen: datetime) -> None:
    """Friert `datetime.now()` im Gating-Pfad ein (Muster: `_FrozenDatetime` aus
    `tests/golden/email/conftest.py`). `_check_one_preset` importiert `datetime`
    modul-lokal (`from datetime import datetime, timezone`) und ruft
    `datetime.now(timezone.utc)` fuer Quiet-Hours-Pruefung + Tageslimit +
    State-Zeitstempel auf -- fuer AC-1/AC-2 muss dieser Zeitpunkt deterministisch
    steuerbar sein. Kein Mock des zu pruefenden Verhaltens selbst (der Service
    bleibt echt), nur ein Uhrzeit-Seam."""
    import services.compare_official_alert as coa_mod

    class _Frozen(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return frozen.replace(tzinfo=None)
            return frozen.astimezone(tz)

    monkeypatch.setattr(coa_mod, "datetime", _Frozen)


def test_ac1_quiet_hours_suppresses_send_state_and_limit(monkeypatch):
    """AC-1 (#1233 Bug-Repro): Ruhezeit 22:00–06:00 (Mitternachts-Wrap) umschliesst
    now=00:00 UTC -> KEINE Mail, KEIN AlertState-Eintrag, KEIN Tageslimit-Increment.
    RED: `_check_one_preset` prueft aktuell KEINE Ruhezeiten -> sendet trotzdem
    (genau der 00:00-Uhr-Bug aus der Symptom-Beschreibung)."""
    from services import alert_daily_limit
    from services.alert_state import AlertStateService
    from services.compare_official_alert import CompareOfficialAlertService
    from services.official_alerts import register_official_alert_source

    uid = _uid("1233ac1")
    _clean_user(uid)
    b, backup = _sources_backup()
    b._REGISTERED_SOURCES.clear()
    try:
        save_location(_location("loc-a", "Hermagor", LAT_A, LON_A), user_id=uid)
        _write_presets(uid, [_preset(
            "p1", ["loc-a"], ["e@x.invalid"],
            alert_quiet_from="22:00", alert_quiet_to="06:00",
        )])
        register_official_alert_source(_FakeOfficialAlertSource(LAT_A, LON_A, [_alert()]))
        frozen_midnight = datetime(2026, 7, 12, 0, 0, tzinfo=timezone.utc)
        _freeze_compare_official_alert_now(monkeypatch, frozen_midnight)

        mail_calls: list = []
        sent = CompareOfficialAlertService(
            settings=_settings_all_channels(), user_id=uid,
            mail_sink=lambda subject, body: mail_calls.append(body),
        ).check_all_compare_presets()

        assert sent == 0, f"Ruhezeit 22–06 umschliesst 00:00 -> darf nicht senden: sent={sent}"
        assert mail_calls == [], f"mail_sink darf bei Ruhezeit leer bleiben: {mail_calls!r}"
        state = AlertStateService(user_id=uid).load("p1:loc-a")
        assert not any(k.startswith("official_alert:") for k in state), (
            f"Waehrend Ruhezeit unterdrueckte Warnung darf KEINEN State schreiben "
            f"(sonst wird sie nach Ende der Ruhezeit als 'schon gemeldet' verschluckt): {state!r}"
        )
        assert alert_daily_limit.load(uid, frozen_midnight) == 0, (
            "Tageslimit darf bei unterdruecktem Versand NICHT erhoeht werden"
        )
    finally:
        b._REGISTERED_SOURCES.clear()
        b._REGISTERED_SOURCES.extend(backup)
        _clean_user(uid)


def test_ac2_quiet_hour_suppression_does_not_permanently_swallow_warning(monkeypatch):
    """AC-2: Runde 1 (now=00:00, Ruhezeit) unterdrueckt -> Runde 2 (now=09:00,
    dieselbe noch-neue Warnung) MUSS zustellen. Belegt end-to-end, dass die
    Nacht-Unterdrueckung die Warnung nicht dauerhaft verschluckt (setzt voraus,
    dass Runde 1 keinen State schreibt, s. AC-1)."""
    from services.compare_official_alert import CompareOfficialAlertService
    from services.official_alerts import register_official_alert_source

    uid = _uid("1233ac2")
    _clean_user(uid)
    b, backup = _sources_backup()
    b._REGISTERED_SOURCES.clear()
    try:
        save_location(_location("loc-a", "Hermagor", LAT_A, LON_A), user_id=uid)
        _write_presets(uid, [_preset(
            "p1", ["loc-a"], ["e@x.invalid"],
            alert_quiet_from="22:00", alert_quiet_to="06:00",
        )])
        register_official_alert_source(_FakeOfficialAlertSource(LAT_A, LON_A, [_alert()]))

        def _svc(mail_calls):
            return CompareOfficialAlertService(
                settings=_settings_all_channels(), user_id=uid,
                mail_sink=lambda subject, body: mail_calls.append(body),
            )

        night_calls: list = []
        _freeze_compare_official_alert_now(
            monkeypatch, datetime(2026, 7, 12, 0, 0, tzinfo=timezone.utc)
        )
        sent_night = _svc(night_calls).check_all_compare_presets()
        assert sent_night == 0 and night_calls == [], (
            f"Runde 1 (00:00, Ruhezeit) darf nicht senden: sent={sent_night}, calls={night_calls!r}"
        )

        morning_calls: list = []
        _freeze_compare_official_alert_now(
            monkeypatch, datetime(2026, 7, 12, 9, 0, tzinfo=timezone.utc)
        )
        sent_morning = _svc(morning_calls).check_all_compare_presets()
        assert sent_morning == 1, (
            f"Runde 2 (09:00, ausserhalb Ruhezeit) muss die weiterhin neue Warnung "
            f"zustellen: sent={sent_morning}"
        )
        assert len(morning_calls) == 1
    finally:
        b._REGISTERED_SOURCES.clear()
        b._REGISTERED_SOURCES.extend(backup)
        _clean_user(uid)


def test_ac3_manual_schedule_disabled_compare_suppresses_send():
    """AC-3 (#1233 Bug-Repro): Preset `schedule=="manual"` (= deaktivierter
    Ortsvergleich, PO-Entscheidung) + neue amtliche Warnung, ausserhalb jeder
    Ruhezeit -> KEINE Mail. RED: `_check_one_preset` prueft `schedule` bisher
    gar nicht -> sendet trotz Deaktivierung (Symptom: Preset 'zillertal' mit
    schedule='manual' sandte trotzdem)."""
    from services.compare_official_alert import CompareOfficialAlertService
    from services.official_alerts import register_official_alert_source

    uid = _uid("1233ac3")
    _clean_user(uid)
    b, backup = _sources_backup()
    b._REGISTERED_SOURCES.clear()
    try:
        save_location(_location("loc-a", "Hermagor", LAT_A, LON_A), user_id=uid)
        _write_presets(uid, [_preset(
            "p1", ["loc-a"], ["e@x.invalid"], schedule="manual",
        )])
        register_official_alert_source(_FakeOfficialAlertSource(LAT_A, LON_A, [_alert()]))

        mail_calls: list = []
        sent = CompareOfficialAlertService(
            settings=_settings_all_channels(), user_id=uid,
            mail_sink=lambda subject, body: mail_calls.append(body),
        ).check_all_compare_presets()

        assert sent == 0, f"Deaktiviertes Preset (schedule=manual) darf nicht senden: sent={sent}"
        assert mail_calls == []
    finally:
        b._REGISTERED_SOURCES.clear()
        b._REGISTERED_SOURCES.extend(backup)
        _clean_user(uid)


def test_ac4_archived_preset_suppresses_send():
    """AC-4 (#1233): ein archivierter Ortsvergleich (`archived_at` gesetzt)
    sendet keine amtliche-Warnung-Mail mehr. RED: `_check_one_preset` prueft
    `archived_at` bisher gar nicht."""
    from services.compare_official_alert import CompareOfficialAlertService
    from services.official_alerts import register_official_alert_source

    uid = _uid("1233ac4")
    _clean_user(uid)
    b, backup = _sources_backup()
    b._REGISTERED_SOURCES.clear()
    try:
        save_location(_location("loc-a", "Hermagor", LAT_A, LON_A), user_id=uid)
        _write_presets(uid, [_preset(
            "p1", ["loc-a"], ["e@x.invalid"], archived_at="2026-07-01T00:00:00Z",
        )])
        register_official_alert_source(_FakeOfficialAlertSource(LAT_A, LON_A, [_alert()]))

        mail_calls: list = []
        sent = CompareOfficialAlertService(
            settings=_settings_all_channels(), user_id=uid,
            mail_sink=lambda subject, body: mail_calls.append(body),
        ).check_all_compare_presets()

        assert sent == 0, f"Archiviertes Preset darf nicht senden: sent={sent}"
        assert mail_calls == []
    finally:
        b._REGISTERED_SOURCES.clear()
        b._REGISTERED_SOURCES.extend(backup)
        _clean_user(uid)


def test_ac5_active_daily_preset_still_sends_no_regression():
    """AC-5 (Regressionsschutz #1233): aktives Preset (`schedule='daily'`),
    ausserhalb jeder Ruhezeit, neue Warnung -> Mail wird weiterhin versendet.
    Dieser Test sollte bereits GRUEN sein (kein neues Gate greift hier) -- er
    belegt, dass #1/#2 aktive Presets nicht kollateral blockieren."""
    from services.compare_official_alert import CompareOfficialAlertService
    from services.official_alerts import register_official_alert_source

    uid = _uid("1233ac5")
    _clean_user(uid)
    b, backup = _sources_backup()
    b._REGISTERED_SOURCES.clear()
    try:
        save_location(_location("loc-a", "Hermagor", LAT_A, LON_A), user_id=uid)
        _write_presets(uid, [_preset("p1", ["loc-a"], ["e@x.invalid"], schedule="daily")])
        register_official_alert_source(_FakeOfficialAlertSource(LAT_A, LON_A, [_alert()]))

        mail_calls: list = []
        sent = CompareOfficialAlertService(
            settings=_settings_all_channels(), user_id=uid,
            mail_sink=lambda subject, body: mail_calls.append(body),
        ).check_all_compare_presets()

        assert sent == 1, f"Aktives Preset ausserhalb der Ruhezeit muss senden: sent={sent}"
        assert len(mail_calls) == 1
    finally:
        b._REGISTERED_SOURCES.clear()
        b._REGISTERED_SOURCES.extend(backup)
        _clean_user(uid)
