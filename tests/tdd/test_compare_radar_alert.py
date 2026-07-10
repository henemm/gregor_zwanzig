"""TDD RED — Issue #1041 Slice 1b: Compare-Radar-Alarm-Service &
Scheduler-Verdrahtung (Epic #1095).

Nutzt den in Slice 1a (LIVE) gelieferten Bündel-Versand-Baustein
(`NotificationService.send_multi_location_radar_alert`,
`output.renderers.alert.project.to_multi_location_onset_alert_message`) und
verdrahtet ihn zu einem echten Compare-Radar-Alarm-Pfad: neuer
`CompareRadarAlertService` (Struktur-Vorbild `CompareAlertService`,
`src/services/compare_alert.py`), DI-Seam `radar_service` (Vorbild
`TripAlertService.__init__`, `trip_alert.py:59`), `mail_sink`-DI (Vorbild
`CompareAlertService`).

Alle Tests folgen der Projektregel „keine Mocks" (CLAUDE.md): echte
Preset-/Throttle-/Locations-Dateien unter `data/users/<user_id>/` (eindeutige
tdd-1041b-* IDs, Cleanup per try/finally — Vorbild
`test_issue_1169_compare_alert_consumer.py`), echte `RadarFrame`-Fixtures
über den `frame_source`-DI-Seam von `RadarNowcastService`
(`radar_service.py:84-89`) statt eines Mocks der Provider-Kette. Der
`mail_sink`-Seam ersetzt den SMTP-Versand vollständig (Vorbild
`send_multi_location_radar_alert`-Tests in `test_multi_location_onset_alert.py`),
kein echter Netzwerkzugriff nötig.

RED-Grund: Das Modul `services.compare_radar_alert` / die Klasse
`CompareRadarAlertService` existieren noch nicht → ImportError/AttributeError
in jedem Test.

SPEC: docs/specs/modules/issue_1041b_compare_radar_alert_service.md
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.config import Settings
from app.loader import save_location
from app.user import SavedLocation

DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "users"


# ───────────────────────── Fixtures & Builder ───────────────────────────────


def _clean_user(user_id: str) -> None:
    d = DATA_ROOT / user_id
    if d.exists():
        shutil.rmtree(d)


def _settings_email_capable_dummy() -> Settings:
    """`can_send_email() == True` ohne echten Netzwerkzugriff — der
    `mail_sink`-Zweig in `NotificationService._dispatch_alert_message`
    (`notification_service.py:585-598`) ersetzt den SMTP-Versand vollständig;
    die Dummy-Creds werden nie dial't. Vorbild
    `test_issue_1169_compare_alert_consumer.py::_settings_email_capable_dummy`."""
    return Settings(
        smtp_host="dummy.invalid", smtp_user="dummy", smtp_pass="dummy",
        mail_to="dummy@example.com",
    )


def _location(loc_id: str, name: str, lat: float, lon: float) -> SavedLocation:
    return SavedLocation(id=loc_id, name=name, lat=lat, lon=lon, elevation_m=1000)


def _radar_preset(
    preset_id: str,
    location_ids: list[str],
    empfaenger: list[str],
    *,
    radar_alert_enabled: bool | None = True,
    quiet_from: str | None = None,
    quiet_to: str | None = None,
    name: str | None = None,
) -> dict:
    """Direktes Compare-Preset-Dict (Vorbild
    `test_issue_1169_compare_alert_consumer.py::_preset`).
    `radar_alert_enabled=None` lässt das Feld komplett weg (Default-Test, AC-6)."""
    preset: dict = {
        "id": preset_id,
        "name": name or preset_id,
        "user_id": "default",
        "location_ids": location_ids,
        "schedule": "manual",
        "weekday": 4,
        "profil": "ALLGEMEIN",
        "hour_from": 9,
        "hour_to": 16,
        "empfaenger": empfaenger,
        "letzter_versand": None,
        "top_ort_letzter_versand": None,
        "created_at": "2026-07-10T00:00:00Z",
    }
    if radar_alert_enabled is not None:
        preset["radar_alert_enabled"] = radar_alert_enabled
    if quiet_from is not None:
        preset["alert_quiet_from"] = quiet_from
    if quiet_to is not None:
        preset["alert_quiet_to"] = quiet_to
    return preset


def _write_preset_file(user_id: str, presets: list[dict]) -> Path:
    path = DATA_ROOT / user_id / "compare_presets.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(presets, ensure_ascii=False), encoding="utf-8")
    return path


class _CoordFrameSource:
    """Echter (kein `Mock()`/`patch()`), aufrufbarer `frame_source`-Doppelgänger
    für `RadarNowcastService(frame_source=...)` (`radar_service.py:84-89`) —
    liefert je nach (lat, lon) einen vorab festgelegten, echten
    `RadarFrame`-Satz. Konfigurations-Seam analog `_ScriptedWeatherSource` in
    `test_issue_1169_compare_alert_consumer.py`. Zählt echte Aufrufe
    (`call_count`) für AC-6 — kein Mock-Theater, ein reales Objekt mit realen
    Rückgabewerten."""

    def __init__(self, by_coord: dict[tuple[float, float], list]) -> None:
        self._by_coord = by_coord
        self.call_count = 0
        self.calls: list[tuple[float, float]] = []

    def __call__(self, lat: float, lon: float) -> list:
        self.call_count += 1
        self.calls.append((lat, lon))
        return self._by_coord.get((round(lat, 4), round(lon, 4)), [])


def _wet_frame(onset_minutes: int, *, is_convective: bool = False, rate: float = 0.6) -> list:
    """Ein einzelner nasser `RadarFrame` `onset_minutes` in der Zukunft —
    echtes DTO (kein Mock), Vorbild `providers/brightsky.py::RadarFrame`."""
    from providers.brightsky import RadarFrame

    ts = datetime.now(timezone.utc) + timedelta(minutes=onset_minutes)
    return [RadarFrame(timestamp=ts, precip_mm_h=rate, is_convective=is_convective)]


def _dry_frames() -> list:
    """Kein auslösender Frame im Nowcast-Fenster."""
    return []


def _quiet_hours_window_now(buffer_minutes: int = 3) -> tuple[str, str]:
    """`(quiet_from, quiet_to)` als `HH:MM`-UTC-Strings, die den aktuellen
    Zeitpunkt umschließen — garantiert, dass der Check-Lauf während der
    Ruhezeit stattfindet, unabhängig von der tatsächlichen Tageszeit
    (Vorbild-Idee: Test Plan AC-5 „gesetzte Systemzeit innerhalb des
    konfigurierten Ruhezeit-Fensters" — hier über ein dynamisch um „jetzt"
    gelegtes Fenster realisiert, da `DeviationAlertEngine.is_quiet_hours`
    keinen `now`-Injektions-Seam anbietet)."""
    now = datetime.now(timezone.utc)
    start = (now - timedelta(minutes=buffer_minutes)).strftime("%H:%M")
    end = (now + timedelta(minutes=buffer_minutes)).strftime("%H:%M")
    return start, end


# ═══════════════════════════════ AC-1 ════════════════════════════════════════


def test_single_location_onset_triggers_bundled_alert():
    """AC-1: EIN Ort in einem Preset mit `radar_alert_enabled=true`, Onset
    ≤ 20 Min → EINE E-Mail (Einzel-Onset-Format) mit Ortsname + Onset-Zeit.

    RED: `services.compare_radar_alert` existiert noch nicht (ImportError).
    """
    from services.compare_radar_alert import CompareRadarAlertService
    from services.radar_service import RadarNowcastService

    uid = "tdd-1041b-ac1"
    _clean_user(uid)
    try:
        loc = _location("loc-a", "Zermatt-Alarm", 46.0207, 7.7491)
        save_location(loc, user_id=uid)
        preset_id = "cp-1041b-ac1"
        _write_preset_file(uid, [_radar_preset(preset_id, ["loc-a"], ["gregor-test@henemm.com"])])

        frame_source = _CoordFrameSource({(46.0207, 7.7491): _wet_frame(8)})
        radar_service = RadarNowcastService(frame_source=frame_source)
        mail_calls: list[tuple[str, str]] = []

        service = CompareRadarAlertService(
            settings=_settings_email_capable_dummy(), user_id=uid,
            radar_service=radar_service,
            mail_sink=lambda subject, body: mail_calls.append((subject, body)),
        )
        sent = service.check_all_compare_presets()

        assert sent == 1, f"Erwartete genau 1 Bündel-Mail, erhalten: {sent}"
        assert len(mail_calls) == 1, f"Erwartete genau 1 mail_sink-Aufruf, erhalten: {len(mail_calls)}"
        subject, body = mail_calls[0]
        assert "Zermatt-Alarm" in subject, f"Ortsname fehlt im Betreff: {subject!r}"
        assert "8" in subject, f"Onset-Zeitangabe fehlt im Betreff: {subject!r}"
    finally:
        _clean_user(uid)


# ═══════════════════════════════ AC-2 ════════════════════════════════════════


def test_no_alert_when_all_locations_dry_or_late_onset():
    """AC-2: ein Preset mit `radar_alert_enabled=true`, dessen Orte alle
    trocken sind oder deren Onset > 20 Min liegt → kein Alarm, kein Versand.

    RED: `services.compare_radar_alert` existiert noch nicht (ImportError).
    """
    from services.compare_radar_alert import CompareRadarAlertService
    from services.radar_service import RadarNowcastService

    uid = "tdd-1041b-ac2"
    _clean_user(uid)
    try:
        loc_dry = _location("loc-dry", "Trockenhausen", 47.0, 11.0)
        loc_late = _location("loc-late", "Spaetregen", 47.2, 11.2)
        save_location(loc_dry, user_id=uid)
        save_location(loc_late, user_id=uid)
        preset_id = "cp-1041b-ac2"
        _write_preset_file(
            uid, [_radar_preset(preset_id, ["loc-dry", "loc-late"], ["gregor-test@henemm.com"])],
        )

        frame_source = _CoordFrameSource({
            (47.0, 11.0): _dry_frames(),
            (47.2, 11.2): _wet_frame(45),
        })
        radar_service = RadarNowcastService(frame_source=frame_source)
        mail_calls: list[tuple[str, str]] = []

        service = CompareRadarAlertService(
            settings=_settings_email_capable_dummy(), user_id=uid,
            radar_service=radar_service,
            mail_sink=lambda subject, body: mail_calls.append((subject, body)),
        )
        sent = service.check_all_compare_presets()

        assert sent == 0, f"Trocken/spät darf keinen Alarm auslösen, erhalten: {sent}"
        assert mail_calls == [], "Kein mail_sink-Aufruf bei Trocken/Spät-Onset erwartet"
    finally:
        _clean_user(uid)


# ═══════════════════════════════ AC-3 ════════════════════════════════════════


def test_two_simultaneous_locations_bundled_into_one_mail():
    """AC-3: ZWEI Orte EINES Presets lösen gleichzeitig aus (beide Onset
    ≤ 20 Min) → GENAU EINE gebündelte Mail, die BEIDE Orte mit Namen und
    Onset-Zeit listet.

    RED: `services.compare_radar_alert` existiert noch nicht (ImportError).
    """
    from services.compare_radar_alert import CompareRadarAlertService
    from services.radar_service import RadarNowcastService

    uid = "tdd-1041b-ac3"
    _clean_user(uid)
    try:
        loc_a = _location("loc-a", "Zermatt-Bündel", 46.0207, 7.7491)
        loc_b = _location("loc-b", "Chamonix-Bündel", 45.9237, 6.8694)
        save_location(loc_a, user_id=uid)
        save_location(loc_b, user_id=uid)
        preset_id = "cp-1041b-ac3"
        _write_preset_file(
            uid, [_radar_preset(preset_id, ["loc-a", "loc-b"], ["gregor-test@henemm.com"])],
        )

        frame_source = _CoordFrameSource({
            (46.0207, 7.7491): _wet_frame(5),
            (45.9237, 6.8694): _wet_frame(18),
        })
        radar_service = RadarNowcastService(frame_source=frame_source)
        mail_calls: list[tuple[str, str]] = []

        service = CompareRadarAlertService(
            settings=_settings_email_capable_dummy(), user_id=uid,
            radar_service=radar_service,
            mail_sink=lambda subject, body: mail_calls.append((subject, body)),
        )
        sent = service.check_all_compare_presets()

        assert sent == 1, f"Erwartete GENAU EINE gebündelte Mail, erhalten: {sent}"
        assert len(mail_calls) == 1
        _subject, body = mail_calls[0]
        assert "Zermatt-Bündel" in body, f"Ort A fehlt in der Bündel-Mail: {body!r}"
        assert "Chamonix-Bündel" in body, f"Ort B fehlt in der Bündel-Mail: {body!r}"
    finally:
        _clean_user(uid)


# ═══════════════════════════════ AC-4 ════════════════════════════════════════


def test_cooldown_suppresses_repeat_alert_within_window():
    """AC-4: nach einem versendeten Alarm unterdrückt ein zweiter Lauf
    innerhalb des Cooldown-Fensters (echter Throttle-Store auf Platte, zwei
    zeitlich versetzte, echte Läufe) den erneuten Versand.

    RED: `services.compare_radar_alert` existiert noch nicht (ImportError).
    """
    from services.compare_radar_alert import CompareRadarAlertService
    from services.radar_service import RadarNowcastService

    uid = "tdd-1041b-ac4"
    _clean_user(uid)
    try:
        loc = _location("loc-cd", "Cooldown-Ort", 47.0, 11.0)
        save_location(loc, user_id=uid)
        preset_id = "cp-1041b-ac4"
        _write_preset_file(uid, [_radar_preset(preset_id, ["loc-cd"], ["gregor-test@henemm.com"])])

        frame_source = _CoordFrameSource({(47.0, 11.0): _wet_frame(10)})
        settings = _settings_email_capable_dummy()
        mail_calls: list[tuple[str, str]] = []

        svc1 = CompareRadarAlertService(
            settings=settings, user_id=uid,
            radar_service=RadarNowcastService(frame_source=frame_source),
            mail_sink=lambda subject, body: mail_calls.append((subject, body)),
        )
        first = svc1.check_all_compare_presets()
        assert first == 1, "Erster Lauf (kein Cooldown aktiv) muss alarmieren"
        assert len(mail_calls) == 1

        # Zweiter Lauf mit frischer Service-Instanz (lädt Throttle-Store von
        # Platte) direkt danach — liegt real innerhalb jedes plausiblen
        # Cooldown-Fensters (Minuten/Stunden).
        svc2 = CompareRadarAlertService(
            settings=settings, user_id=uid,
            radar_service=RadarNowcastService(frame_source=frame_source),
            mail_sink=lambda subject, body: mail_calls.append((subject, body)),
        )
        second = svc2.check_all_compare_presets()
        assert second == 0, "Zweiter Lauf innerhalb des Cooldown-Fensters darf nicht erneut versenden"
        assert len(mail_calls) == 1, "Cooldown hätte den zweiten Versand unterdrücken müssen"
    finally:
        _clean_user(uid)


# ═══════════════════════════════ AC-5 ════════════════════════════════════════


def test_quiet_hours_suppress_alert_despite_detected_onset():
    """AC-5: Ruhezeiten aktiv (Fenster um „jetzt" gelegt) UND ein Ort zeigt
    einen auslösenden Onset → der Alarm wird unterdrückt, kein Versand, kein
    stiller Fehler.

    RED: `services.compare_radar_alert` existiert noch nicht (ImportError).
    """
    from services.compare_radar_alert import CompareRadarAlertService
    from services.radar_service import RadarNowcastService

    uid = "tdd-1041b-ac5"
    _clean_user(uid)
    try:
        loc = _location("loc-qh", "Ruhezeit-Ort", 47.0, 11.0)
        save_location(loc, user_id=uid)
        quiet_from, quiet_to = _quiet_hours_window_now()
        preset_id = "cp-1041b-ac5"
        _write_preset_file(uid, [
            _radar_preset(
                preset_id, ["loc-qh"], ["gregor-test@henemm.com"],
                quiet_from=quiet_from, quiet_to=quiet_to,
            ),
        ])

        frame_source = _CoordFrameSource({(47.0, 11.0): _wet_frame(9)})
        mail_calls: list[tuple[str, str]] = []

        service = CompareRadarAlertService(
            settings=_settings_email_capable_dummy(), user_id=uid,
            radar_service=RadarNowcastService(frame_source=frame_source),
            mail_sink=lambda subject, body: mail_calls.append((subject, body)),
        )
        sent = service.check_all_compare_presets()

        assert sent == 0, f"Ruhezeit muss den Versand unterdrücken, erhalten: {sent}"
        assert mail_calls == [], "Kein mail_sink-Aufruf während der Ruhezeit erwartet"
    finally:
        _clean_user(uid)


# ═══════════════════════════════ AC-6 ════════════════════════════════════════


def test_disabled_or_missing_flag_skips_nowcast_fetch_entirely():
    """AC-6: ein Preset OHNE `radar_alert_enabled` (fehlendes Feld) und ein
    zweites mit `radar_alert_enabled=false` → `get_nowcast()`/`frame_source`
    wird für KEINEN Ort dieser Presets aufgerufen (echter zählender
    `frame_source`-Doppelgänger, `call_count == 0`), kein Alarm.

    RED: `services.compare_radar_alert` existiert noch nicht (ImportError).
    """
    from services.compare_radar_alert import CompareRadarAlertService
    from services.radar_service import RadarNowcastService

    uid = "tdd-1041b-ac6"
    _clean_user(uid)
    try:
        loc_missing = _location("loc-missing", "Fehlendes-Flag", 47.0, 11.0)
        loc_false = _location("loc-false", "Falsches-Flag", 47.2, 11.2)
        save_location(loc_missing, user_id=uid)
        save_location(loc_false, user_id=uid)
        _write_preset_file(uid, [
            _radar_preset(
                "cp-1041b-ac6-missing", ["loc-missing"], ["gregor-test@henemm.com"],
                radar_alert_enabled=None,
            ),
            _radar_preset(
                "cp-1041b-ac6-false", ["loc-false"], ["gregor-test@henemm.com"],
                radar_alert_enabled=False,
            ),
        ])

        # Würde AUSLÖSEN, wenn tatsächlich aufgerufen — Beweis, dass der Guard
        # den Fetch verhindert, nicht dass zufällig kein Onset erkannt wurde.
        frame_source = _CoordFrameSource({
            (47.0, 11.0): _wet_frame(5),
            (47.2, 11.2): _wet_frame(5),
        })
        radar_service = RadarNowcastService(frame_source=frame_source)
        mail_calls: list[tuple[str, str]] = []

        service = CompareRadarAlertService(
            settings=_settings_email_capable_dummy(), user_id=uid,
            radar_service=radar_service,
            mail_sink=lambda subject, body: mail_calls.append((subject, body)),
        )
        sent = service.check_all_compare_presets()

        assert sent == 0, f"Deaktivierte/fehlende Presets dürfen nicht alarmieren, erhalten: {sent}"
        assert mail_calls == []
        assert frame_source.call_count == 0, (
            f"get_nowcast() wurde trotz deaktiviertem/fehlendem Flag {frame_source.call_count}x "
            "aufgerufen — Netzwerkkosten-Guard fehlt"
        )
    finally:
        _clean_user(uid)


# ═══════════════════════════════ AC-7 ════════════════════════════════════════


def test_two_users_isolated_locations_and_recipients():
    """AC-7 (Mandantenfähigkeit): zwei Nutzer mit je eigenem Preset/Ort/
    Empfänger → Nutzer A's Alarm nutzt ausschließlich A's Ort/Empfänger,
    Nutzer B (dry) löst nichts aus; Throttle-/State-Dateien liegen
    ausschließlich unter `data/users/A/...` bzw. `data/users/B/...`; keine
    Datei referenziert das jeweils andere Preset (kein `"default"`-Fallback).

    RED: `services.compare_radar_alert` existiert noch nicht (ImportError).
    """
    from services.compare_radar_alert import CompareRadarAlertService
    from services.radar_service import RadarNowcastService

    user_a, user_b = "tdd-1041b-ac7-a", "tdd-1041b-ac7-b"
    _clean_user(user_a)
    _clean_user(user_b)
    preset_a_id, preset_b_id = "cp-1041b-ac7-a", "cp-1041b-ac7-b"
    try:
        loc_a = _location("loc-a", "OrtA-Alarm", 46.0207, 7.7491)
        loc_b = _location("loc-b", "OrtB-Ruhig", 45.9237, 6.8694)
        save_location(loc_a, user_id=user_a)
        save_location(loc_b, user_id=user_b)

        _write_preset_file(user_a, [_radar_preset(preset_a_id, ["loc-a"], ["userA@testinvalid.example"])])
        _write_preset_file(user_b, [_radar_preset(preset_b_id, ["loc-b"], ["userB@testinvalid.example"])])

        frame_source_a = _CoordFrameSource({(46.0207, 7.7491): _wet_frame(7)})
        frame_source_b = _CoordFrameSource({(45.9237, 6.8694): _dry_frames()})

        mail_calls_a: list[tuple[str, str]] = []
        mail_calls_b: list[tuple[str, str]] = []

        svc_a = CompareRadarAlertService(
            settings=_settings_email_capable_dummy(), user_id=user_a,
            radar_service=RadarNowcastService(frame_source=frame_source_a),
            mail_sink=lambda subject, body: mail_calls_a.append((subject, body)),
        )
        svc_b = CompareRadarAlertService(
            settings=_settings_email_capable_dummy(), user_id=user_b,
            radar_service=RadarNowcastService(frame_source=frame_source_b),
            mail_sink=lambda subject, body: mail_calls_b.append((subject, body)),
        )
        sent_a = svc_a.check_all_compare_presets()
        sent_b = svc_b.check_all_compare_presets()

        assert sent_a == 1, "Nutzer A muss einen Alarm auslösen (Onset ≤ 20 Min)"
        assert sent_b == 0, "Nutzer B darf keinen Alarm auslösen (trocken)"
        assert len(mail_calls_a) == 1
        assert mail_calls_b == []

        _subject_a, body_a = mail_calls_a[0]
        assert "OrtA-Alarm" in body_a or "OrtA-Alarm" in _subject_a
        assert "OrtB-Ruhig" not in body_a and "OrtB-Ruhig" not in _subject_a, (
            "Cross-User-Datenleck B→A in der Alarm-Mail von Nutzer A"
        )

        # Datei-Isolation: nur A hat einen Throttle-Store, B (nie ausgelöst) nicht.
        a_throttle = DATA_ROOT / user_a / "compare_radar_alert_throttle.json"
        b_throttle = DATA_ROOT / user_b / "compare_radar_alert_throttle.json"
        assert a_throttle.exists(), "Throttle-Store für Nutzer A fehlt nach erfolgtem Alarm"
        assert not b_throttle.exists(), "Nutzer B hat einen Throttle-Eintrag trotz Δ=trocken"

        b_dir = DATA_ROOT / user_b
        if b_dir.exists():
            for p in b_dir.rglob("*"):
                if p.is_file():
                    assert preset_a_id not in p.name, f"Cross-User-Datenleck A→B in {p}"
        a_dir = DATA_ROOT / user_a
        for p in a_dir.rglob("*"):
            if p.is_file():
                assert preset_b_id not in p.name, f"Cross-User-Datenleck B→A in {p}"
    finally:
        _clean_user(user_a)
        _clean_user(user_b)


# ═══════════════════════════════ AC-8 ════════════════════════════════════════


def test_convective_event_labeled_when_triggering():
    """AC-8: ein Ort mit konvektiver Gefahr (`is_convective=True`, WMO
    95/96/99) UND Onset ≤ 20 Min → der Alarm löst aus UND die versendete
    Nachricht kennzeichnet das Ereignis als konvektiv (Gewitter/Hagel-Label
    statt reinem Regen-Label).

    RED: `services.compare_radar_alert` existiert noch nicht (ImportError).
    """
    from services.compare_radar_alert import CompareRadarAlertService
    from services.radar_service import RadarNowcastService

    uid = "tdd-1041b-ac8"
    _clean_user(uid)
    try:
        loc = _location("loc-conv", "Sturmdorf", 47.0, 11.0)
        save_location(loc, user_id=uid)
        preset_id = "cp-1041b-ac8"
        _write_preset_file(uid, [_radar_preset(preset_id, ["loc-conv"], ["gregor-test@henemm.com"])])

        frame_source = _CoordFrameSource({
            (47.0, 11.0): _wet_frame(6, is_convective=True, rate=5.0),
        })
        mail_calls: list[tuple[str, str]] = []

        service = CompareRadarAlertService(
            settings=_settings_email_capable_dummy(), user_id=uid,
            radar_service=RadarNowcastService(frame_source=frame_source),
            mail_sink=lambda subject, body: mail_calls.append((subject, body)),
        )
        sent = service.check_all_compare_presets()

        assert sent == 1, f"Konvektiver Onset ≤ 20 Min muss auslösen, erhalten: {sent}"
        assert len(mail_calls) == 1
        subject, body = mail_calls[0]
        text = subject + "\n" + body
        assert "Gewitter" in text or "Hagel" in text, (
            f"Konvektives Ereignis trägt kein Gewitter/Hagel-Label: {text!r}"
        )
        assert "leichter Regen" not in text, (
            f"Konvektives Ereignis darf nicht als reiner Regen gelabelt werden: {text!r}"
        )
    finally:
        _clean_user(uid)
