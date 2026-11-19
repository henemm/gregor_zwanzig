"""TDD RED — Issue #2800 (Epic #2791, Scheibe S8): Trip-Radar-Alarm-Schalter.

SPEC: docs/specs/modules/feat_2800_trip_radar_alarm.md (AC-1, AC-3, AC-4, AC-5,
AC-7 Python-Loader-Teil).

Der Trip-Radarlauf (#822, ``TripAlertService.check_radar_alerts_run`` ->
``_check_radar_trips``) laeuft heute fuer JEDEN Trip. Neu: Feld
``radar_alert_enabled`` am Trip, Default ``None`` = AN (Vorbild
``official_alerts_enabled``), ``False`` = kein Nowcast-Abruf und kein Versand.
Die Pruefung sitzt VOR Segmentwahl, Kanal-Aufloesung und Nowcast-Abruf
(ADR-0082-Budget); der „zuletzt erreicht"-Stempel bleibt gesetzt.

Wo die Zusicherung WIRKT: der Lauf liest die Trips von der Platte
(``load_all_trips``). Deshalb wird der Schalter in die gespeicherte Trip-Datei
geschrieben (Read-Modify-Write auf das, was ``save_trip`` erzeugt hat — so wie
die Go-API ihn spaeter persistiert), nicht nur am Objekt gesetzt.

Kein Mock-Theater: ``AlarmPruefstrecke`` (#2050) gegen die echte
Ausloeseentscheidung, echte ``RadarNowcastService``-Unterklasse als DI-Seam
(zaehlt die Abrufe), lokale HTTP-Stubs fuer Telegram/seven.io, ``mail_sink``
fuer E-Mail. Vergleichs-Gegenprobe mit echtem ``CompareRadarAlertService``.

RED-Gruende (heute):
* AC-3: Schalter ``false`` wird ignoriert -> Nowcast wird abgerufen, Alarm geht
  auf allen Kanaelen raus.
* Loader: ``radar_alert_enabled`` ist kein Trip-Feld -> ``save_trip`` schreibt
  es nicht, ``load_all_trips`` liefert kein Attribut.
Bereits gruen (Absicherung, nicht kuenstlich rot): AC-1 (true/None -> alle vier
Kanaele), AC-4 (Bestandstrip ohne Feld alarmiert, Vergleich ohne Feld bleibt
aus), AC-5 (Stille Stunden halten zurueck).
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from freezegun import freeze_time

from app.loader import get_briefings_dir, get_data_dir, load_all_trips, save_location, save_trip
from services import alert_log

from tests.helpers.alarm_pruefstrecke import AlarmPruefstrecke
from tests.helpers.nowcast_gate_fixtures import (
    entries_for, settings_email_only, suppression_reasons,
)
from tests.tdd.test_952_onset_alert_fidelity import _clean_user, _GuaranteedWetRadar
from tests.tdd.test_alarm_pruefstrecke_selbstschutz import (
    _radar_trip, _settings_all_channels, _write_premium_profile,
)

# Gestellte Uhr wie die Pruefstrecken-Tests (#2050): 10:00 UTC = 12:00 Ortszeit
# Korsika (Trip-Koordinaten aus `_trip_with_active_segment`).
_AT = datetime(2026, 4, 5, 10, 0, tzinfo=timezone.utc)

_KEIN_WERT = object()


def _uid(tag: str) -> str:
    return f"tdd-2800-{tag}-{uuid.uuid4().hex[:6]}"


class _ZaehlendesNassRadar(_GuaranteedWetRadar):
    """Echte ``RadarNowcastService``-Unterklasse: liefert garantiert Regen-
    Beginn in 12 Minuten und zaehlt jeden Abruf. Ein Abruf bei Schalter aus
    ist genau der Budget-Verstoss, den AC-3 verbietet."""

    def __init__(self) -> None:
        super().__init__(onset_minutes=12)
        self.calls: list[tuple[float, float]] = []

    def get_nowcast(self, lat, lon, elevation_m=None, priority="user_briefing", user_id=None, deadline_at=None):
        self.calls.append((lat, lon))
        return super().get_nowcast(
            lat, lon, elevation_m=elevation_m, priority=priority,
            user_id=user_id, deadline_at=deadline_at,
        )


def _schalter_auf_platte(uid: str, trip_id: str, wert) -> None:
    """Read-Modify-Write auf die gespeicherte Trip-Datei: setzt (oder entfernt
    bei ``_KEIN_WERT``) ``radar_alert_enabled``, alles andere bleibt."""
    path = get_briefings_dir(uid) / f"{trip_id}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if wert is _KEIN_WERT:
        data.pop("radar_alert_enabled", None)
    else:
        data["radar_alert_enabled"] = wert
    path.write_text(json.dumps(data), encoding="utf-8")


def _alle_kanaele_trip(uid: str, trip_id: str, schalter, **extra):
    """Trip mit aktivem Segment zur gestellten Uhr, alle vier Alarm-Kanaele
    an, Premium-Profil mit frischer Garmin-Rueckadresse."""
    _write_premium_profile(uid, _AT)
    trip = _radar_trip(
        uid, trip_id, send_email=True, send_telegram=True,
        send_sms=True, send_premium_sms=True,
    )
    for feld, wert in extra.items():
        setattr(trip, feld, wert)
    if extra:
        save_trip(trip, user_id=uid)
    _schalter_auf_platte(uid, trip_id, schalter)
    return trip


def _kanal_texte(lauf) -> dict[str, list]:
    return {
        "email": lauf.mail, "telegram": lauf.telegram,
        "sms": lauf.sms, "premium_sms": lauf.premium_sms,
    }


# ═══════════════════════════════ AC-3 ════════════════════════════════════════


def test_ac3_schalter_aus_kein_nowcast_abruf_und_kein_versand():
    """AC-3: Trip mit ``radar_alert_enabled=false`` und Regen-Beginn auf der
    Etappe -> der Nowcast-Dienst wird NIE aufgerufen, auf keinem der vier
    Kanaele geht etwas raus. Gegenprobe: derselbe Aufbau mit Schalter an
    alarmiert (der Regen ist echt, die Stille kommt vom Schalter)."""
    uid, ctrl = _uid("ac3"), _uid("ac3-ctrl")
    _clean_user(uid)
    _clean_user(ctrl)
    try:
        trip = _alle_kanaele_trip(uid, "trip-2800-ac3", False)
        radar = _ZaehlendesNassRadar()
        strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())
        lauf = strecke.lauf(at=_AT, zweig="radar", trip=trip, radar_service=radar)

        assert radar.calls == [], (
            f"AC-3: Schalter aus, trotzdem {len(radar.calls)} Nowcast-Abruf(e) "
            "— die Schalter-Pruefung fehlt oder sitzt hinter dem Abruf (ADR-0082)"
        )
        assert lauf.triggered_count == 0, f"AC-3: Schalter aus, trotzdem {lauf.triggered_count} Alarm"
        assert not any(_kanal_texte(lauf).values()), (
            f"AC-3: Schalter aus, trotzdem Versand: {_kanal_texte(lauf)!r}"
        )

        trip_k = _alle_kanaele_trip(ctrl, "trip-2800-ac3", True)
        radar_k = _ZaehlendesNassRadar()
        lauf_k = AlarmPruefstrecke(user_id=ctrl, settings=_settings_all_channels()).lauf(
            at=_AT, zweig="radar", trip=trip_k, radar_service=radar_k,
        )
        assert radar_k.calls and lauf_k.triggered_count == 1, (
            "Gegenprobe: derselbe Trip mit Schalter an muss den Nowcast abrufen und alarmieren"
        )
    finally:
        _clean_user(uid)
        _clean_user(ctrl)


def test_ac3_schalter_aus_trip_gilt_trotzdem_als_erreicht():
    """Spec Implementation Details Punkt 3: die Pruefung sitzt NACH dem
    „zuletzt erreicht"-Stempel. Ein ausgeschalteter Trip zaehlt als geprueft
    (``checked``), wird nicht als uebersprungen gemeldet und bekommt seinen
    Stempel — sonst stuende er in der fairen Reihenfolge ewig vorne. Dabei
    kein einziger Nowcast-Abruf."""
    from services.trip_alert import TripAlertService

    uid = _uid("ac3-stempel")
    _clean_user(uid)
    try:
        # Nur E-Mail (ueber mail_sink): ohne Pruefstrecken-Stubs darf kein
        # anderer Kanal konfiguriert sein, sonst ginge der heutige (rote) Lauf
        # an echte Gateways.
        _radar_trip(uid, "trip-2800-stempel", send_email=True)
        _schalter_auf_platte(uid, "trip-2800-stempel", False)
        radar = _ZaehlendesNassRadar()
        mails: list = []
        with freeze_time(_AT):
            svc = TripAlertService(
                settings=settings_email_only(), user_id=uid, radar_service=radar,
                mail_sink=lambda subject, body: mails.append((subject, body)),
            )
            result = svc.check_radar_alerts_run()

        assert radar.calls == [], f"Schalter aus, trotzdem {len(radar.calls)} Nowcast-Abruf(e)"
        assert result.alerts_sent == 0 and mails == []
        assert result.checked == 1 and result.skipped == 0, (
            f"Ausgeschalteter Trip muss als erreicht zaehlen: checked={result.checked} "
            f"skipped={result.skipped}"
        )
        stempel = json.loads(
            (get_data_dir(uid) / "alert_last_checked_radar.json").read_text(encoding="utf-8")
        )
        assert "trip-2800-stempel" in stempel, f"Stempel fehlt: {stempel!r}"
    finally:
        _clean_user(uid)


# ═══════════════════════════ AC-1 / AC-4 ═════════════════════════════════════


def _assert_alarm_auf_allen_vier_kanaelen(lauf, radar) -> None:
    assert radar.calls, "Nowcast muss abgerufen werden"
    assert lauf.triggered_count == 1, f"genau ein Alarm erwartet, war {lauf.triggered_count}"
    texte = _kanal_texte(lauf)
    for kanal, nachrichten in texte.items():
        assert len(nachrichten) == 1, (
            f"AC-1: Kanal {kanal} muss genau einen Radar-Alarm erhalten, erhielt "
            f"{len(nachrichten)}: {texte!r}"
        )


def test_ac1_schalter_an_alarm_auf_allen_vier_kanaelen():
    """AC-1: ``radar_alert_enabled=true`` + Regen-Beginn -> je Kanal (E-Mail,
    Telegram, SMS, Premium-SMS) genau ein Alarm (ADR-0095)."""
    uid = _uid("ac1")
    _clean_user(uid)
    try:
        trip = _alle_kanaele_trip(uid, "trip-2800-ac1", True)
        radar = _ZaehlendesNassRadar()
        lauf = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels()).lauf(
            at=_AT, zweig="radar", trip=trip, radar_service=radar,
        )
        _assert_alarm_auf_allen_vier_kanaelen(lauf, radar)
    finally:
        _clean_user(uid)


def test_ac4_bestandstrip_ohne_feld_alarmiert_weiter():
    """AC-4: ein Bestandstrip, bei dem der Schalter nie gesetzt wurde (Feld
    fehlt in der Datei) verstummt NICHT still: None = an."""
    uid = _uid("ac4")
    _clean_user(uid)
    try:
        trip = _alle_kanaele_trip(uid, "trip-2800-ac4", _KEIN_WERT)
        raw = json.loads((get_briefings_dir(uid) / "trip-2800-ac4.json").read_text(encoding="utf-8"))
        assert "radar_alert_enabled" not in raw, "Vorbedingung: Bestandstrip ohne Feld"
        radar = _ZaehlendesNassRadar()
        lauf = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels()).lauf(
            at=_AT, zweig="radar", trip=trip, radar_service=radar,
        )
        _assert_alarm_auf_allen_vier_kanaelen(lauf, radar)
    finally:
        _clean_user(uid)


def test_ac4_direkt_konstruierter_trip_ohne_feld_alarmiert():
    """AC-4 (Fix-Loop 1, F002): der Default des Trip-Modells selbst ist „an".
    Ein direkt per ``Trip(...)`` gebauter Trip ohne ``radar_alert_enabled``
    (keine Loader-Runde, die ``None`` explizit setzt) geht durch die echte
    Trip-Schleife des Radarlaufs: Nowcast wird abgerufen, der Alarm geht per
    E-Mail raus. Wuerde der Modell-Default auf ``False`` kippen, verstummten
    alle intern gebauten Trips still."""
    import time

    from services.trip_alert import RADAR_RUN_DEADLINE_SECONDS, TripAlertService

    uid = _uid("ac4-direkt")
    _clean_user(uid)
    try:
        # `_radar_trip` baut den Trip per `Trip(id=..., name=..., stages=[...])`
        # ohne das Feld; das Objekt selbst (nicht die geladene Datei) laeuft durch.
        trip = _radar_trip(uid, "trip-2800-direkt", send_email=True)
        default = trip.radar_alert_enabled
        radar = _ZaehlendesNassRadar()
        mails: list = []
        with freeze_time(_AT):
            svc = TripAlertService(
                settings=settings_email_only(), user_id=uid, radar_service=radar,
                mail_sink=lambda subject, body: mails.append((subject, body)),
            )
            reached: dict = {}
            progress = {"checked": 0, "hit_deadline": False}
            sent, failed = svc._check_radar_trips(
                [trip], datetime.now(timezone.utc),
                time.monotonic() + RADAR_RUN_DEADLINE_SECONDS, reached, progress,
            )

        assert radar.calls, (
            "AC-4: direkt gebauter Trip ohne Feld muss den Nowcast abrufen (Default = an), "
            f"Modell-Default war {default!r}"
        )
        assert sent == 1 and failed == 0 and len(mails) == 1, (
            f"AC-4: direkt gebauter Trip ohne Feld muss alarmieren: sent={sent} "
            f"failed={failed} mails={len(mails)}, Modell-Default war {default!r}"
        )
        assert default is None, f"Modell-Default muss None sein, war {default!r}"
    finally:
        _clean_user(uid)


def test_ac4_gegenprobe_ortsvergleich_ohne_feld_bleibt_aus():
    """AC-4 (dokumentierte Default-Asymmetrie): beim Ortsvergleich bedeutet
    „nicht gesetzt" weiterhin AUS (``compare_radar_alert.py``) — kein Abruf,
    kein Alarm. Positivkontrolle: ein zweites Preset mit ``true`` am selben
    Lauf alarmiert, der Regen ist also echt."""
    from services.compare_radar_alert import CompareRadarAlertService
    from services.radar_service import RadarNowcastService
    from tests.tdd.test_compare_radar_alert import (
        _CoordFrameSource, _clean_user as _clean_compare_user, _location,
        _radar_preset, _settings_email_capable_dummy, _wet_frame, _write_preset_file,
    )

    uid = _uid("ac4-vergleich")
    _clean_compare_user(uid)
    try:
        save_location(_location("loc-2800-ohne", "Ohne-Feld", 47.0, 11.0), user_id=uid)
        save_location(_location("loc-2800-an", "Feld-an", 47.2, 11.2), user_id=uid)
        _write_preset_file(uid, [
            _radar_preset("cp-2800-ohne", ["loc-2800-ohne"], ["gregor-test@henemm.com"],
                          radar_alert_enabled=None),
            _radar_preset("cp-2800-an", ["loc-2800-an"], ["gregor-test@henemm.com"],
                          radar_alert_enabled=True),
        ])
        frames = _CoordFrameSource({(47.0, 11.0): _wet_frame(5), (47.2, 11.2): _wet_frame(5)})
        mails: list = []
        svc = CompareRadarAlertService(
            settings=_settings_email_capable_dummy(), user_id=uid,
            radar_service=RadarNowcastService(frame_source=frames),
            mail_sink=lambda subject, body: mails.append((subject, body)),
        )
        sent = svc.check_all_compare_presets()

        assert (47.0, 11.0) not in [(round(a, 4), round(b, 4)) for a, b in frames.calls], (
            "AC-4: Ortsvergleich ohne radar_alert_enabled darf keinen Nowcast abrufen (None = aus)"
        )
        assert sent == 1 and len(mails) == 1, (
            f"Positivkontrolle: nur das Preset mit true alarmiert (sent={sent}, mails={len(mails)})"
        )
        assert "Ohne-Feld" not in mails[0][1]
    finally:
        _clean_compare_user(uid)


# ═══════════════════════════════ AC-5 ════════════════════════════════════════


def test_ac5_stille_stunden_halten_radar_alarm_zurueck():
    """AC-5: Schalter an, Stille Stunden des Trips umschliessen die gestellte
    Uhr (12:00 Ortszeit) -> kein Versand auf irgendeinem Kanal, das Gate
    protokolliert „Stille Stunden". Gegenprobe ausserhalb der Stillen Stunden
    (gleicher Aufbau, Fenster nachts) -> zugestellt."""
    uid, ctrl = _uid("ac5"), _uid("ac5-ctrl")
    _clean_user(uid)
    _clean_user(ctrl)
    try:
        trip = _alle_kanaele_trip(
            uid, "trip-2800-ac5", True,
            alert_quiet_from="11:00", alert_quiet_to="13:00",
        )
        lauf = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels()).lauf(
            at=_AT, zweig="radar", trip=trip, radar_service=_ZaehlendesNassRadar(),
        )
        assert lauf.triggered_count == 0, "AC-5: in den Stillen Stunden kein Radar-Alarm"
        assert not any(_kanal_texte(lauf).values()), f"AC-5: Versand trotz Stiller Stunden: {_kanal_texte(lauf)!r}"
        gruende = set()
        for bucket in ("entries", "not_delivered"):
            for eintrag in entries_for(uid, "trip-2800-ac5", bucket=bucket):
                gruende |= suppression_reasons(eintrag)
        assert alert_log.REASON_QUIET_HOURS in gruende, (
            f"AC-5: Gate muss 'zurueckgehalten (Stille Stunden)' protokollieren, Gruende: {gruende!r}"
        )

        trip_k = _alle_kanaele_trip(
            ctrl, "trip-2800-ac5", True,
            alert_quiet_from="01:00", alert_quiet_to="03:00",
        )
        lauf_k = AlarmPruefstrecke(user_id=ctrl, settings=_settings_all_channels()).lauf(
            at=_AT, zweig="radar", trip=trip_k, radar_service=_ZaehlendesNassRadar(),
        )
        assert lauf_k.triggered_count == 1, "Gegenprobe: ausserhalb der Stillen Stunden zugestellt"
    finally:
        _clean_user(uid)
        _clean_user(ctrl)


def _protokoll_eintraege(uid: str, trip_id: str) -> list[dict]:
    """Alle Alarm-Protokolleintraege dieses Trips, gleich in welchem Fach."""
    eintraege: list[dict] = []
    for bucket in ("entries", "not_delivered"):
        eintraege += entries_for(uid, trip_id, bucket=bucket)
    return eintraege


def test_ac3_schalter_aus_in_stillen_stunden_kein_protokolleintrag():
    """AC-3 + Spec Implementation Details (Fix-Loop 2, F004): die Schalter-
    Pruefung sitzt VOR dem Gate. Ein abgeschalteter Trip in seinen Stillen
    Stunden erzeugt deshalb weder Nowcast-Abruf noch Versand NOCH einen
    Alarm-Protokolleintrag „zurueckgehalten (Stille Stunden)" — der Nutzer hat
    den Radar-Alarm abgeschaltet, im Protokoll darf er nicht als zurueck-
    gehaltener Alarm auftauchen. Gegenprobe: derselbe Aufbau mit Schalter an
    erzeugt den Unterdrueckungs-Eintrag (der Eintrag ist also beobachtbar)."""
    uid, ctrl = _uid("ac3-still"), _uid("ac3-still-ctrl")
    trip_id = "trip-2800-ac3-still"
    _clean_user(uid)
    _clean_user(ctrl)
    try:
        trip = _alle_kanaele_trip(
            uid, trip_id, False,
            alert_quiet_from="11:00", alert_quiet_to="13:00",
        )
        radar = _ZaehlendesNassRadar()
        lauf = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels()).lauf(
            at=_AT, zweig="radar", trip=trip, radar_service=radar,
        )
        assert radar.calls == [], f"Schalter aus, trotzdem {len(radar.calls)} Nowcast-Abruf(e)"
        assert lauf.triggered_count == 0 and not any(_kanal_texte(lauf).values()), (
            f"Schalter aus, trotzdem Versand: {_kanal_texte(lauf)!r}"
        )
        eintraege = _protokoll_eintraege(uid, trip_id)
        assert eintraege == [], (
            "F004: Schalter aus, trotzdem Alarm-Protokolleintrag — die Schalter-"
            f"Pruefung sitzt hinter dem Gate: {eintraege!r}"
        )

        trip_k = _alle_kanaele_trip(
            ctrl, trip_id, True,
            alert_quiet_from="11:00", alert_quiet_to="13:00",
        )
        radar_k = _ZaehlendesNassRadar()
        lauf_k = AlarmPruefstrecke(user_id=ctrl, settings=_settings_all_channels()).lauf(
            at=_AT, zweig="radar", trip=trip_k, radar_service=radar_k,
        )
        assert lauf_k.triggered_count == 0, "Gegenprobe: Stille Stunden halten zurueck"
        gruende = set()
        for eintrag in _protokoll_eintraege(ctrl, trip_id):
            gruende |= suppression_reasons(eintrag)
        assert alert_log.REASON_QUIET_HOURS in gruende, (
            "Gegenprobe: Schalter an in den Stillen Stunden muss einen "
            f"Unterdrueckungs-Eintrag erzeugen, Gruende: {gruende!r}"
        )
    finally:
        _clean_user(uid)
        _clean_user(ctrl)


# ════════════ Staging-Debug-Trigger respektiert den Schalter (Test 8) ═════════


def _debug_trigger(monkeypatch, smtp_calls: list, schalter) -> tuple[dict, list]:
    """Ruft die ECHTE Route ``POST /api/debug/trigger-radar-alert`` (Staging-
    Guard aktiv) fuer einen Nutzer-Trip auf Platte auf; der Schalter steht in
    der gespeicherten Datei. Versand faengt der SMTP-Transportrand ab (Muster
    aus ``test_debug_radar_segmentwahl.py``)."""
    import smtplib
    import time
    from datetime import date as date_type

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from api.routers import debug as debug_router
    from tests.helpers.nowcast_gate_fixtures import make_trip
    from tests.tdd.test_debug_radar_segmentwahl import _RecordingSMTP

    monkeypatch.setattr(smtplib, "SMTP", _RecordingSMTP(smtp_calls))
    monkeypatch.setattr(time, "sleep", lambda *a, **k: None)
    monkeypatch.setenv("GZ_ENV", "staging")
    monkeypatch.setenv("GZ_SMTP_HOST", "smtp.example.invalid")
    monkeypatch.setenv("GZ_SMTP_USER", "test-user")
    monkeypatch.setenv("GZ_SMTP_PASS", "test-pass")

    app = FastAPI()
    app.include_router(debug_router.router)

    uid = _uid("debug")
    _clean_user(uid)
    trip_id = "trip-2800-debug"
    try:
        # Vergangene Etappe: die Route faellt per Test-Seam auf das erste Segment.
        trip = make_trip(trip_id, stage_date=date_type(2026, 8, 1), lat=64.1466, lon=-21.9426,
                         arrival_start="08:00", arrival_end="16:00")
        save_trip(trip, user_id=uid)
        _schalter_auf_platte(uid, trip_id, schalter)
        resp = TestClient(app).post("/api/debug/trigger-radar-alert", params={"user_id": uid})
        assert resp.status_code == 200, f"Status {resp.status_code}: {resp.text}"
        return resp.json(), smtp_calls
    finally:
        _clean_user(uid)


def test_debug_trigger_schalter_aus_meldet_disabled_ohne_versand(monkeypatch):
    """Test 8 / AC-3 (Staging-Gegenprobe): Trip mit ``radar_alert_enabled=false``
    -> der Debug-Trigger antwortet ``disabled`` und versucht keinen Versand."""
    body, calls = _debug_trigger(monkeypatch, [], False)

    assert body == {"status": "disabled", "trip_id": "trip-2800-debug"}, (
        f"Debug-Trigger ignoriert den Schalter: {body!r}"
    )
    assert calls == [], f"Schalter aus, trotzdem Versandversuch: {calls!r}"


def test_debug_trigger_ohne_feld_versendet_wie_bisher(monkeypatch):
    """Gegenprobe: Bestandstrip ohne Feld (None = an) -> der Debug-Trigger
    versendet unveraendert an das Test-Postfach."""
    body, calls = _debug_trigger(monkeypatch, [], _KEIN_WERT)

    assert body.get("status") == "sent", f"erwartet 'sent', war {body!r}"
    assert calls and all(c["to"] == ("gregor-test@henemm.com",) for c in calls), calls


# ═════════════════════ Loader-Roundtrip (AC-7, Python) ═══════════════════════


def test_loader_roundtrip_schalter_true_und_false():
    """AC-7 (Python-Seite): ein Trip mit ``radar_alert_enabled`` true bzw.
    false uebersteht ``save_trip`` + ``load_all_trips`` mit demselben Wert und
    steht als Feld in der Datei."""
    from tests.helpers.nowcast_gate_fixtures import make_trip

    uid = _uid("loader")
    _clean_user(uid)
    try:
        for wert in (True, False):
            trip_id = f"trip-2800-loader-{str(wert).lower()}"
            trip = make_trip(trip_id)
            trip.radar_alert_enabled = wert
            save_trip(trip, user_id=uid)

            raw = json.loads((get_briefings_dir(uid) / f"{trip_id}.json").read_text(encoding="utf-8"))
            assert raw.get("radar_alert_enabled", "FEHLT") is wert, (
                f"save_trip muss radar_alert_enabled={wert} schreiben, Datei hat "
                f"{raw.get('radar_alert_enabled', 'FEHLT')!r}"
            )
            geladen = {t.id: t for t in load_all_trips(user_id=uid)}[trip_id]
            assert getattr(geladen, "radar_alert_enabled", "FEHLT") is wert, (
                f"load_all_trips muss radar_alert_enabled={wert} liefern, "
                f"war {getattr(geladen, 'radar_alert_enabled', 'FEHLT')!r}"
            )
            assert "radar_alert_enabled" not in getattr(geladen, "extra", {}), (
                "radar_alert_enabled darf nicht im extra-Auffangnetz landen"
            )
    finally:
        _clean_user(uid)


def test_loader_none_wird_nicht_geschrieben():
    """Ein Trip ohne Schalter (None = an) bekommt beim Speichern kein Feld —
    sonst entstuende still ein expliziter Wert; geladen ist er None."""
    from tests.helpers.nowcast_gate_fixtures import make_trip

    uid = _uid("loader-none")
    _clean_user(uid)
    try:
        trip = make_trip("trip-2800-loader-none")
        save_trip(trip, user_id=uid)
        raw = json.loads(
            (get_briefings_dir(uid) / "trip-2800-loader-none.json").read_text(encoding="utf-8")
        )
        assert "radar_alert_enabled" not in raw
        geladen = {t.id: t for t in load_all_trips(user_id=uid)}["trip-2800-loader-none"]
        assert getattr(geladen, "radar_alert_enabled", "FEHLT") is None, (
            "Trip-Modell muss radar_alert_enabled mit Default None fuehren"
        )
    finally:
        _clean_user(uid)
