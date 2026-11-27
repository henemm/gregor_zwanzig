"""TDD RED — Issue #3186: ein pausierter Trip schweigt in ALLEN Trip-Alarmpfaden.

SPEC: docs/specs/modules/fix_3186_trip_pause_alarme.md (AC-1..AC-7; AC-8 in
``tests/tdd/test_issue_995_scheduler_pause.py::TestAC9AlertDispatchUnaffected``).

Heute ist die Trip-Pause (``paused_at`` bzw. ``report_config.paused_until``)
nur im Briefing-Filter verdrahtet. ``TripAlertService.check_all_trips``
(Abweichung + amtliche Warnungen) und ``_check_radar_trips`` (Radar) kennen sie
nicht: ein pausierter Trip alarmiert weiter auf allen Kanaelen.

Wo die Zusicherung WIRKT: die beiden echten Laeufe ``check_all_trips()`` und
``check_radar_alerts_run()`` lesen die Trips von der Platte
(``load_all_trips``). Die Pause wird deshalb per Read-Modify-Write in die
gespeicherte Trip-Datei geschrieben, so wie die Go-API sie persistiert.

Kein Mock-Theater: Versand wird an der Netz-Naht abgegriffen
(``transport_mitschrift`` fuer E-Mail/Telegram/SMS/Premium-SMS bzw.
``AlarmPruefstrecke`` mit lokalen Telegram-/seven.io-Stubs). Wetter-Snapshot,
Frisch-Abruf und amtliche Quelle sind deterministische, ZAEHLENDE
Ersatzfunktionen an benannten DI-Seams (Vorbild ``_alarm_amtlich_fixtures``);
der Radar-Nowcast eine zaehlende ``RadarNowcastService``-Unterklasse.

RED-Gruende (heute): pausierter Trip -> Wetter-/Warnungs-/Nowcast-Abruf findet
statt und der Alarm geht raus. Gegenproben ohne Pause sind bereits gruen.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

from freezegun import freeze_time

from app.loader import get_briefings_dir, get_data_dir, load_all_trips, save_trip
from app.models import (
    ForecastMeta, GPXPoint, MetricConfig, NormalizedTimeseries, Provider,
    SegmentWeatherData, SegmentWeatherSummary, TripSegment,
    UnifiedWeatherDisplayConfig,
)
from services import official_alerts as official_alerts_mod
from services.trip_alert import TripAlertService

from tests.helpers.alarm_pruefstrecke import AlarmPruefstrecke
from tests.helpers.nowcast_gate_fixtures import entries_for
from tests.helpers.transport_mitschrift import ALLE_KANAELE, aufzeichner_installieren
from tests.tdd._alarm_amtlich_fixtures import amtliche_warnung
from tests.tdd._einstellung_auslieferung_fixtures import TRANSPORT_ENV
from tests.tdd.test_952_onset_alert_fidelity import _clean_user, _GuaranteedWetRadar
from tests.tdd.test_alarm_pruefstrecke_selbstschutz import (
    _radar_trip, _settings_all_channels, _write_premium_profile,
)

# Gestellte Uhr wie die Pruefstrecken-Tests (#2050): 10:00 UTC = 12:00 Ortszeit
# Korsika (Koordinaten aus `_trip_with_active_segment`).
_AT = datetime(2026, 4, 5, 10, 0, tzinfo=timezone.utc)

_ZUKUNFT = (_AT + timedelta(days=2)).isoformat()
_VERGANGEN = (_AT - timedelta(hours=1)).isoformat()


def _uid(tag: str) -> str:
    return f"tdd-3186-{tag}-{uuid.uuid4().hex[:6]}"


# ═══════════════════════════════ Bausteine ═══════════════════════════════════


def _pause_auf_platte(uid: str, trip_id: str, *, paused_at=None, paused_until=None,
                      entfernen: bool = False) -> None:
    """Read-Modify-Write auf die gespeicherte Trip-Datei: setzt ``paused_at``
    bzw. ``report_config.paused_until`` (oder entfernt beides), alles andere
    bleibt unveraendert."""
    path = get_briefings_dir(uid) / f"{trip_id}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if entfernen:
        data.pop("paused_at", None)
        (data.get("report_config") or {}).pop("paused_until", None)
    if paused_at is not None:
        data["paused_at"] = paused_at
    if paused_until is not None:
        data.setdefault("report_config", {})["paused_until"] = paused_until
    path.write_text(json.dumps(data), encoding="utf-8")


def _profil_mit_allen_kanaelen(uid: str) -> None:
    """Premium-Profil (Garmin-Rueckadresse, kein Tageslimit) plus bestaetigte
    SMS-Nummer — sonst wischt ``with_user_profile()`` SMS strukturell weg."""
    _write_premium_profile(uid, _AT)
    path = get_data_dir(uid) / "user.json"
    profil = json.loads(path.read_text(encoding="utf-8"))
    profil["sms_verified_number"] = profil["sms_to"]
    path.write_text(json.dumps(profil), encoding="utf-8")


def _alle_kanaele_trip(uid: str, trip_id: str):
    """Trip mit aktivem Segment zur gestellten Uhr, alle vier Alarm-Kanaele an,
    aktive Niederschlags-Abweichungsregel, amtliche Warnungen Default an.
    Auf der Platte gespeichert (``load_all_trips`` liest ihn)."""
    _profil_mit_allen_kanaelen(uid)
    trip = _radar_trip(
        uid, trip_id, send_email=True, send_telegram=True,
        send_sms=True, send_premium_sms=True,
    )
    trip.display_config = UnifiedWeatherDisplayConfig(
        trip_id=trip_id,
        metrics=[MetricConfig(metric_id="precipitation", enabled=True)],
        metric_alert_levels={"precipitation_sum": "standard"},
    )
    trip.alert_cooldown_minutes = 0
    with freeze_time(_AT):
        save_trip(trip, user_id=uid)
    return trip


def _wetter(precip_mm: float) -> SegmentWeatherData:
    """Ein Segment, dessen Zeitfenster `_AT` umschliesst — dient als Δ-Anker
    bzw. Frisch-Wert (Niederschlagssumme) UND als Routen-Geometrie fuer die
    amtliche Pruefung."""
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.20, lon=9.10, elevation_m=1000, distance_from_start_km=0.0),
        end_point=GPXPoint(lat=42.25, lon=9.15, elevation_m=1200, distance_from_start_km=8.0),
        start_time=_AT - timedelta(hours=2), end_time=_AT + timedelta(hours=6),
        duration_hours=8.0, distance_km=8.0, ascent_m=200, descent_m=0,
    )
    return SegmentWeatherData(
        segment=seg,
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=1.0), data=[],
        ),
        aggregated=SegmentWeatherSummary(precip_sum_mm=precip_mm),
        fetched_at=_AT, provider="openmeteo",
    )


def _abruf_naehte(monkeypatch, *, abweichung: bool, warnungen: list) -> dict:
    """Zaehlende Ersatzfunktionen fuer Wetter-Snapshot, Frisch-Abruf und
    amtliche Quelle (kein Netz). ``abweichung=True``: Anker 2 mm, frisch 18 mm
    (signifikant); ``False``: kein tagesgleicher Anker (nur amtlicher Zweig)."""
    zaehler = {"wetter": 0, "frisch": 0, "amtlich": 0}

    def _snapshot(self, trip, *, tagesgleicher_anker_noetig, now_utc=None, nur_lesen=False):
        zaehler["wetter"] += 1
        if tagesgleicher_anker_noetig and not abweichung:
            return []
        return [_wetter(2.0)]

    def _frisch(self, cached_weather):
        zaehler["frisch"] += 1
        return [_wetter(18.0)]

    def _quelle(lat, lon, *, window_start, window_end, now):
        zaehler["amtlich"] += 1
        return list(warnungen)

    monkeypatch.setattr(TripAlertService, "_get_cached_weather", _snapshot)
    monkeypatch.setattr(TripAlertService, "_fetch_fresh_weather", _frisch)
    monkeypatch.setattr(official_alerts_mod, "get_official_alerts_for_location", _quelle)
    return zaehler


def _sammellauf(monkeypatch, uid: str):
    """EIN echter Lauf ``check_all_trips()`` zur gestellten Uhr; Versand an der
    Netz-Naht abgegriffen (alle vier Kanaele)."""
    for k, v in TRANSPORT_ENV.items():
        monkeypatch.setenv(k, v)
    mit = aufzeichner_installieren(monkeypatch)
    with freeze_time(_AT):
        settings = _settings_all_channels().with_user_profile(uid)
        ergebnis = TripAlertService(settings=settings, user_id=uid).check_all_trips()
    return ergebnis, mit


def _warn_state(uid: str) -> dict:
    d = get_data_dir(uid) / "alert_state"
    if not d.exists():
        return {}
    return {p.name: p.read_text(encoding="utf-8") for p in sorted(d.glob("*.json"))}


def _protokoll(uid: str, trip_id: str) -> list[dict]:
    return entries_for(uid, trip_id, bucket="entries") + entries_for(uid, trip_id, bucket="not_delivered")


class _ZaehlendesNassRadar(_GuaranteedWetRadar):
    """Echte ``RadarNowcastService``-Unterklasse: Regen-Beginn in 12 Minuten,
    zaehlt jeden Abruf. Ein Abruf bei pausiertem Trip ist der Budget-Verstoss
    (ADR-0082), den AC-3 verbietet."""

    def __init__(self) -> None:
        super().__init__(onset_minutes=12)
        self.calls: list[tuple[float, float]] = []

    def get_nowcast(self, lat, lon, elevation_m=None, priority="user_briefing", user_id=None, deadline_at=None):
        self.calls.append((lat, lon))
        return super().get_nowcast(
            lat, lon, elevation_m=elevation_m, priority=priority,
            user_id=user_id, deadline_at=deadline_at,
        )


def _radarlauf(uid: str, trip):
    radar = _ZaehlendesNassRadar()
    lauf = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels()).lauf(
        at=_AT, zweig="radar", trip=trip, radar_service=radar,
    )
    return lauf, radar


def _radar_kanaele(lauf) -> dict:
    return {"email": lauf.mail, "telegram": lauf.telegram, "sms": lauf.sms, "premium_sms": lauf.premium_sms}


def _radar_kurz(lauf) -> dict:
    return {k: len(v) for k, v in _radar_kanaele(lauf).items()}


def _gesendet(mit) -> dict:
    """Je bedientem Kanal die Betreffzeilen (kurz genug fuer Fehlermeldungen)."""
    return {k: [s["subject"] for s in mit.sendungen(k)] for k in ALLE_KANAELE if mit.sendungen(k)}


# ═══════════════════════════════ AC-1 ════════════════════════════════════════


def test_ac1_pausierter_trip_abweichung_kein_versand_kein_wetterabruf(monkeypatch):
    """AC-1: Trip mit ``paused_at`` auf der Platte und signifikanter
    Niederschlags-Abweichung -> ``check_all_trips`` versendet auf keinem der
    vier Kanaele und ruft kein Wetter ab (weder Snapshot noch frisch)."""
    uid = _uid("ac1")
    _clean_user(uid)
    try:
        _alle_kanaele_trip(uid, "trip-3186-ac1")
        _pause_auf_platte(uid, "trip-3186-ac1", paused_at=_AT.isoformat())
        zaehler = _abruf_naehte(monkeypatch, abweichung=True, warnungen=[])

        ergebnis, mit = _sammellauf(monkeypatch, uid)

        assert _gesendet(mit) == {}, f"AC-1: pausierter Trip, trotzdem Versand: {_gesendet(mit)!r}"
        assert ergebnis.alerts_sent == 0, f"AC-1: pausiert, trotzdem alerts_sent={ergebnis.alerts_sent}"
        assert zaehler["wetter"] == 0 and zaehler["frisch"] == 0, (
            f"AC-1: pausierter Trip, trotzdem Wetter abgerufen: {zaehler!r}"
        )
    finally:
        _clean_user(uid)


# ═══════════════════════════════ AC-2 ════════════════════════════════════════


def test_ac2_pausierter_trip_amtliche_warnung_kein_versand_kein_abruf_state_unveraendert(monkeypatch):
    """AC-2: pausierter Trip, aktive amtliche Warnung -> kein Versand, die
    Warnungs-Quelle wird nicht befragt, der Warn-State bleibt unveraendert."""
    uid = _uid("ac2")
    _clean_user(uid)
    try:
        _alle_kanaele_trip(uid, "trip-3186-ac2")
        _pause_auf_platte(uid, "trip-3186-ac2", paused_at=_AT.isoformat())
        warnung = amtliche_warnung(3, von=_AT - timedelta(hours=1), bis=_AT + timedelta(hours=6))
        zaehler = _abruf_naehte(monkeypatch, abweichung=False, warnungen=[warnung])
        vorher = _warn_state(uid)

        ergebnis, mit = _sammellauf(monkeypatch, uid)

        assert _gesendet(mit) == {}, f"AC-2: pausierter Trip, trotzdem Warn-Versand: {_gesendet(mit)!r}"
        assert ergebnis.alerts_sent == 0, f"AC-2: pausiert, trotzdem alerts_sent={ergebnis.alerts_sent}"
        assert zaehler["amtlich"] == 0, (
            f"AC-2: pausierter Trip, trotzdem {zaehler['amtlich']} Warnungs-Abruf(e)"
        )
        assert _warn_state(uid) == vorher, (
            f"AC-2: Warn-State durch pausierten Lauf veraendert: vorher={vorher!r} "
            f"nachher={_warn_state(uid)!r}"
        )
    finally:
        _clean_user(uid)


# ═══════════════════════════════ AC-3 ════════════════════════════════════════


def test_ac3_pausierter_trip_radar_kein_nowcast_kein_versand(monkeypatch):
    """AC-3: pausierter Trip, Regen im Anflug -> der Radar-Lauf ruft keinen
    Nowcast ab und versendet auf keinem der vier Kanaele."""
    uid = _uid("ac3")
    _clean_user(uid)
    try:
        trip = _alle_kanaele_trip(uid, "trip-3186-ac3")
        _pause_auf_platte(uid, "trip-3186-ac3", paused_at=_AT.isoformat())

        lauf, radar = _radarlauf(uid, trip)

        assert radar.calls == [], (
            f"AC-3: pausierter Trip, trotzdem {len(radar.calls)} Nowcast-Abruf(e) (ADR-0082)"
        )
        assert lauf.triggered_count == 0, f"AC-3: pausiert, trotzdem {lauf.triggered_count} Radar-Alarm"
        assert not any(_radar_kanaele(lauf).values()), (
            f"AC-3: pausiert, trotzdem Versand je Kanal: {_radar_kurz(lauf)!r}"
        )
    finally:
        _clean_user(uid)


def test_ac3_pausierter_trip_gilt_im_radarlauf_trotzdem_als_erreicht():
    """AC-3 / #3085: der Riegel sitzt NACH dem „zuletzt erreicht"-Stempel. Der
    pausierte Trip zaehlt als geprueft, nicht als uebersprungen, und bekommt
    seinen Stempel — dabei kein einziger Nowcast-Abruf, kein Versand."""
    from tests.helpers.nowcast_gate_fixtures import settings_email_only

    uid = _uid("ac3-stempel")
    _clean_user(uid)
    try:
        # Nur E-Mail (ueber mail_sink): ohne Pruefstrecken-Stubs darf kein
        # anderer Kanal konfiguriert sein (heutiger roter Lauf ginge sonst an
        # echte Gateways).
        _radar_trip(uid, "trip-3186-stempel", send_email=True)
        _pause_auf_platte(uid, "trip-3186-stempel", paused_at=_AT.isoformat())
        radar = _ZaehlendesNassRadar()
        mails: list = []
        with freeze_time(_AT):
            result = TripAlertService(
                settings=settings_email_only(), user_id=uid, radar_service=radar,
                mail_sink=lambda subject, body: mails.append((subject, body)),
            ).check_radar_alerts_run()

        assert radar.calls == [], f"pausiert, trotzdem {len(radar.calls)} Nowcast-Abruf(e)"
        assert result.alerts_sent == 0 and mails == [], f"pausiert, trotzdem Versand: {mails!r}"
        assert result.checked == 1 and result.skipped == 0, (
            f"pausierter Trip muss als erreicht zaehlen: checked={result.checked} skipped={result.skipped}"
        )
        stempel = json.loads(
            (get_data_dir(uid) / "alert_last_checked_radar.json").read_text(encoding="utf-8")
        )
        assert "trip-3186-stempel" in stempel, f"Stempel erreicht fehlt: {stempel!r}"
    finally:
        _clean_user(uid)


# ═══════════════════════════════ AC-4 ════════════════════════════════════════


def test_ac4_paused_until_zukunft_schweigt_in_allen_drei_alarmarten(monkeypatch):
    """AC-4: ``report_config.paused_until`` in der Zukunft (Inbound „pause 2d")
    -> Abweichung, amtliche Warnung und Radar schweigen wie bei ``paused_at``."""
    uid = _uid("ac4-zukunft")
    _clean_user(uid)
    try:
        trip = _alle_kanaele_trip(uid, "trip-3186-ac4")
        _pause_auf_platte(uid, "trip-3186-ac4", paused_until=_ZUKUNFT)
        warnung = amtliche_warnung(3, von=_AT - timedelta(hours=1), bis=_AT + timedelta(hours=6))
        zaehler = _abruf_naehte(monkeypatch, abweichung=True, warnungen=[warnung])

        ergebnis, mit = _sammellauf(monkeypatch, uid)
        assert _gesendet(mit) == {} and ergebnis.alerts_sent == 0, (
            f"AC-4: paused_until in der Zukunft, trotzdem Abweichungs-/Warn-Versand: {_gesendet(mit)!r}"
        )
        assert zaehler == {"wetter": 0, "frisch": 0, "amtlich": 0}, (
            f"AC-4: paused_until in der Zukunft, trotzdem Abruf: {zaehler!r}"
        )

        lauf, radar = _radarlauf(uid, trip)
        assert radar.calls == [] and lauf.triggered_count == 0, (
            f"AC-4: paused_until in der Zukunft, trotzdem Radar (Abrufe={len(radar.calls)}, "
            f"Alarme={lauf.triggered_count})"
        )
    finally:
        _clean_user(uid)


def test_ac4_paused_until_vergangen_alarmiert_wieder(monkeypatch):
    """AC-4 (Gegenseite): ``paused_until`` liegt in der Vergangenheit -> die
    Pause ist abgelaufen, Abweichung (mit gebuendelter Warnung) und Radar
    alarmieren normal. Ein zweiter Nutzer (Isolation) mit eigener Pause bleibt
    davon unberuehrt still."""
    uid, anderer = _uid("ac4-vergangen"), _uid("ac4-anderer")
    _clean_user(uid)
    _clean_user(anderer)
    try:
        trip = _alle_kanaele_trip(uid, "trip-3186-ac4")
        _pause_auf_platte(uid, "trip-3186-ac4", paused_until=_VERGANGEN)
        _alle_kanaele_trip(anderer, "trip-3186-ac4")
        _pause_auf_platte(anderer, "trip-3186-ac4", paused_until=_ZUKUNFT)
        warnung = amtliche_warnung(3, von=_AT - timedelta(hours=1), bis=_AT + timedelta(hours=6))
        zaehler = _abruf_naehte(monkeypatch, abweichung=True, warnungen=[warnung])

        # Radar zuerst: ein vorausgehender Abweichungs-Alarm saesse sonst in
        # der Radar-Sperrzeit (Vorbedingung, keine Zusicherung).
        lauf, radar = _radarlauf(uid, trip)
        assert radar.calls and lauf.triggered_count == 1, (
            f"AC-4: paused_until vergangen -> Radar-Alarm erwartet (Alarme={lauf.triggered_count})"
        )

        ergebnis, mit = _sammellauf(monkeypatch, uid)
        assert ergebnis.alerts_sent == 1 and mit.sendungen("email"), (
            f"AC-4: paused_until vergangen -> Alarm erwartet, alerts_sent={ergebnis.alerts_sent} "
            f"{_gesendet(mit)!r}"
        )
        assert zaehler["wetter"] >= 1 and zaehler["amtlich"] >= 1, f"Abrufe erwartet: {zaehler!r}"

        ergebnis_b, mit_b = _sammellauf(monkeypatch, anderer)
        assert ergebnis_b.alerts_sent == 0 and _gesendet(mit_b) == {}, (
            f"Isolation: der andere Nutzer ist noch pausiert, trotzdem Versand: {_gesendet(mit_b)!r}"
        )
    finally:
        _clean_user(uid)
        _clean_user(anderer)


# ═══════════════════════════════ AC-5 ════════════════════════════════════════


def test_ac5_pause_aufgehoben_aktive_warnung_kommt_genau_einmal(monkeypatch):
    """AC-5: Lauf 1 pausiert -> nichts. ``paused_at`` von der Platte entfernt ->
    Lauf 2 liefert die noch aktive amtliche Warnung genau einmal, Lauf 3 keine
    mehr (Melde-Gedaechtnis wurde erst beim Versand geschrieben)."""
    uid = _uid("ac5")
    _clean_user(uid)
    try:
        _alle_kanaele_trip(uid, "trip-3186-ac5")
        _pause_auf_platte(uid, "trip-3186-ac5", paused_at=_AT.isoformat())
        warnung = amtliche_warnung(3, von=_AT - timedelta(hours=1), bis=_AT + timedelta(hours=6))
        _abruf_naehte(monkeypatch, abweichung=False, warnungen=[warnung])

        lauf1, mit1 = _sammellauf(monkeypatch, uid)
        assert lauf1.alerts_sent == 0 and _gesendet(mit1) == {}, (
            f"AC-5 Lauf 1: pausiert, trotzdem Versand: {_gesendet(mit1)!r}"
        )

        _pause_auf_platte(uid, "trip-3186-ac5", entfernen=True)
        lauf2, mit2 = _sammellauf(monkeypatch, uid)
        assert lauf2.alerts_sent == 1 and len(mit2.sendungen("email")) == 1, (
            f"AC-5 Lauf 2: nach dem Fortsetzen genau ein Warn-Alarm erwartet, "
            f"alerts_sent={lauf2.alerts_sent} {_gesendet(mit2)!r}"
        )

        lauf3, mit3 = _sammellauf(monkeypatch, uid)
        assert lauf3.alerts_sent == 0 and _gesendet(mit3) == {}, (
            f"AC-5 Lauf 3: dieselbe Warnung darf nicht erneut kommen: {_gesendet(mit3)!r}"
        )
    finally:
        _clean_user(uid)


# ═══════════════════════════════ AC-6 ════════════════════════════════════════


def test_ac6_nicht_pausiert_abweichung_auf_allen_vier_kanaelen(monkeypatch):
    """AC-6 (Gegenprobe zu AC-1): derselbe Aufbau ohne Pause -> der Abweichungs-
    Alarm geht auf E-Mail, Telegram, SMS und Premium-SMS je genau einmal raus."""
    uid = _uid("ac6-abw")
    _clean_user(uid)
    try:
        _alle_kanaele_trip(uid, "trip-3186-ac6")
        zaehler = _abruf_naehte(monkeypatch, abweichung=True, warnungen=[])

        ergebnis, mit = _sammellauf(monkeypatch, uid)

        assert ergebnis.alerts_sent == 1, f"AC-6: ohne Pause ein Alarm erwartet, war {ergebnis.alerts_sent}"
        for kanal in ALLE_KANAELE:
            assert len(mit.sendungen(kanal)) == 1, (
                f"AC-6: Kanal {kanal} muss genau einen Abweichungs-Alarm erhalten: {_gesendet(mit)!r}"
            )
        assert zaehler["wetter"] >= 1 and zaehler["frisch"] >= 1, f"Wetter-Abruf erwartet: {zaehler!r}"
    finally:
        _clean_user(uid)


def test_ac6_nicht_pausiert_amtliche_warnung_wird_zugestellt(monkeypatch):
    """AC-6 (Gegenprobe zu AC-2): ohne Pause wird die aktive amtliche Warnung
    abgerufen und zugestellt, der Warn-State fortgeschrieben."""
    uid = _uid("ac6-amtlich")
    _clean_user(uid)
    try:
        _alle_kanaele_trip(uid, "trip-3186-ac6")
        warnung = amtliche_warnung(3, von=_AT - timedelta(hours=1), bis=_AT + timedelta(hours=6))
        zaehler = _abruf_naehte(monkeypatch, abweichung=False, warnungen=[warnung])

        ergebnis, mit = _sammellauf(monkeypatch, uid)

        assert ergebnis.alerts_sent == 1 and mit.sendungen("email") and mit.sendungen("telegram"), (
            f"AC-6: ohne Pause muss die Warnung zugestellt werden: alerts_sent={ergebnis.alerts_sent} {_gesendet(mit)!r}"
        )
        assert zaehler["amtlich"] >= 1, f"Warnungs-Abruf erwartet: {zaehler!r}"
        assert _warn_state(uid), "AC-6: nach Versand muss das Melde-Gedaechtnis geschrieben sein"
    finally:
        _clean_user(uid)


def test_ac6_nicht_pausiert_radar_auf_allen_vier_kanaelen():
    """AC-6 (Gegenprobe zu AC-3): ohne Pause -> Nowcast abgerufen, je Kanal
    genau ein Radar-Alarm (ADR-0095)."""
    uid = _uid("ac6-radar")
    _clean_user(uid)
    try:
        trip = _alle_kanaele_trip(uid, "trip-3186-ac6")
        lauf, radar = _radarlauf(uid, trip)
        assert radar.calls and lauf.triggered_count == 1
        for kanal, nachrichten in _radar_kanaele(lauf).items():
            assert len(nachrichten) == 1, f"AC-6: Kanal {kanal} genau ein Radar-Alarm: {_radar_kurz(lauf)!r}"
    finally:
        _clean_user(uid)


# ═══════════════════════════════ AC-7 ════════════════════════════════════════


def test_ac7_riegel_nutzt_trip_pausiert_still_und_ohne_loader_filter(monkeypatch):
    """AC-7: der pausierte Trip bleibt ueber ``load_all_trips`` ladbar (kein
    Filter dort), ``trip_pausiert`` meldet ihn als pausiert, und alle drei
    Laeufe schweigen still — kein Alarmprotokoll-Eintrag (#1459/#2800)."""
    from services.trip_report_scheduler import trip_pausiert

    uid = _uid("ac7")
    trip_id = "trip-3186-ac7"
    _clean_user(uid)
    try:
        trip = _alle_kanaele_trip(uid, trip_id)
        _pause_auf_platte(uid, trip_id, paused_at=_AT.isoformat())

        geladen = {t.id: t for t in load_all_trips(user_id=uid)}
        assert trip_id in geladen, "AC-7: load_all_trips darf pausierte Trips nicht filtern"
        assert trip_pausiert(geladen[trip_id], _AT), "Vorbedingung: trip_pausiert meldet pausiert"

        warnung = amtliche_warnung(3, von=_AT - timedelta(hours=1), bis=_AT + timedelta(hours=6))
        _abruf_naehte(monkeypatch, abweichung=True, warnungen=[warnung])
        ergebnis, mit = _sammellauf(monkeypatch, uid)
        lauf, radar = _radarlauf(uid, trip)

        assert ergebnis.alerts_sent == 0 and _gesendet(mit) == {}, (
            f"AC-7: pausiert, trotzdem Abweichungs-/Warn-Versand: {_gesendet(mit)!r}"
        )
        assert lauf.triggered_count == 0 and not radar.calls, (
            f"AC-7: pausiert, trotzdem Radar (Abrufe={len(radar.calls)}, Alarme={lauf.triggered_count})"
        )
        assert _protokoll(uid, trip_id) == [], (
            f"AC-7: Riegel muss still sein, Alarmprotokoll hat: {_protokoll(uid, trip_id)!r}"
        )
    finally:
        _clean_user(uid)


def test_ac7_debug_trigger_liefert_fuer_pausierten_trip_weiter(monkeypatch):
    """AC-7: der Testversand (``POST /api/debug/trigger-radar-alert``, Staging)
    umgeht den Riegel bewusst — fuer einen pausierten Trip wird weiter
    zugestellt (Versand am SMTP-Transportrand abgegriffen)."""
    import smtplib
    import time
    from datetime import date as date_type

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from api.routers import debug as debug_router
    from tests.helpers.nowcast_gate_fixtures import frozen_active_window, make_trip
    from tests.tdd.test_debug_radar_segmentwahl import _RecordingSMTP

    smtp_calls: list = []
    monkeypatch.setattr(smtplib, "SMTP", _RecordingSMTP(smtp_calls))
    monkeypatch.setattr(time, "sleep", lambda *a, **k: None)
    monkeypatch.setenv("GZ_ENV", "staging")
    monkeypatch.setenv("GZ_SMTP_HOST", "smtp.example.invalid")
    monkeypatch.setenv("GZ_SMTP_USER", "test-user")
    monkeypatch.setenv("GZ_SMTP_PASS", "test-pass")

    app = FastAPI()
    app.include_router(debug_router.router)

    uid = _uid("debug")
    trip_id = "trip-3186-debug"
    _clean_user(uid)
    try:
        with frozen_active_window():
            trip = make_trip(trip_id, stage_date=date_type(2026, 8, 1), lat=64.1466, lon=-21.9426,
                             arrival_start="08:00", arrival_end="16:00")
            save_trip(trip, user_id=uid)
            _pause_auf_platte(uid, trip_id, paused_at=_AT.isoformat())
        resp = TestClient(app).post("/api/debug/trigger-radar-alert", params={"user_id": uid})
        assert resp.status_code == 200, f"Status {resp.status_code}: {resp.text}"
        body = resp.json()
    finally:
        _clean_user(uid)

    assert body.get("status") == "sent", f"AC-7: Testversand fuer pausierten Trip erwartet 'sent', war {body!r}"
    assert smtp_calls, "AC-7: Testversand muss den Transport erreichen"
