"""TDD RED — Issue #1917 (Scheibe S4b-2, Epic #1458 Teil 4b):
quellenuebergreifende Ereignis-Identitaets-Entdopplung auf der
ORTSVERGLEICH-Flaeche fuer AMTLICHE Warnungen.

SPEC: docs/specs/modules/rework_1917_s4b2_compare_entdopplung.md

Abgedeckte Acceptance Criteria in DIESER Datei:
AC-0 (amtlich-Haelfte), AC-4, AC-5, AC-6, AC-8 (inkl. Gegenprobe-Begruendung),
AC-9 (amtlich-Haelfte), AC-11, AC-13, AC-14, AC-15 (amtlich-Haelfte).

RED-Grund (heute): `src/services/compare_official_alert.py` importiert und
ruft `check_event_identity_gate`/`record_event_identity` NICHT — der
Spion-Aufbau scheitert mit AttributeError, und die Verhaltenstests finden
weder Unterdrueckung noch Registereintrag.

Keine Mocks (CLAUDE.md): echte `OfficialAlertSource`-Doppelgaenger ueber
`register_official_alert_source` (strukturelles Subtyping, Muster #1088),
echte Presets/Orte/Registerdateien auf Platte, echter `mail_sink`-Seam. Die
Spione delegieren an die ECHTEN Funktionen; gepatcht wird auf den
Modul-Namensraum des VERBRAUCHENDEN Moduls, weil
`compare_official_alert.py` den Baustein benannt importiert.
"""
from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.config import Settings
from app.loader import get_data_dir, save_location
from app.user import SavedLocation
from services import alert_log
from services.compare_official_alert import CompareOfficialAlertService
from services.official_alerts.models import OfficialAlert

from tests.helpers.compare_briefings import write_compare_briefings

# Zwei Orte mit klar getrennten Koordinaten (Toleranz der Fake-Quelle 0.05).
LAT_A, LON_A = 46.62, 13.68   # Hermagor
LAT_B, LON_B = 46.60, 13.20   # St. Stefan im Gailtal


# ───────────────────────────── Fixtures & Builder ───────────────────────────


def _data_root_users() -> Path:
    from app.loader import get_data_root

    return get_data_root() / "users"


def _uid(prefix: str) -> str:
    return f"tdd-1917o-{prefix}-{uuid.uuid4().hex[:6]}"


def _clean_user(user_id: str) -> None:
    d = _data_root_users() / user_id
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)


def _settings_email_capable_dummy() -> Settings:
    return Settings(
        smtp_host="dummy.invalid", smtp_user="dummy", smtp_pass="dummy",
        mail_to="dummy@example.com",
    )


def _location(loc_id: str, name: str, lat: float, lon: float) -> SavedLocation:
    return SavedLocation(id=loc_id, name=name, lat=lat, lon=lon, elevation_m=1000)


def _preset(preset_id: str, location_ids: list[str], **extra) -> dict:
    """Ortsvergleich-Preset mit AUSDRUECKLICHEM Tagesfenster 0-23 Uhr: der
    amtliche Compare-Pfad fragt Warnungen nur bis zum Ende des heutigen
    Tagesfensters ab (`_day_window_end`). Mit dem ADR-0035-Default 4-19 Uhr
    waere derselbe Test abends taub — die Kippkante haengt an der Uhrzeit des
    Testlaufs, nicht am geprueften Verhalten."""
    preset: dict = {
        "id": preset_id, "name": preset_id, "user_id": "default",
        "location_ids": location_ids, "schedule": "daily", "weekday": 4,
        "profil": "ALLGEMEIN", "hour_from": 9, "hour_to": 16,
        "empfaenger": ["gregor-test@henemm.com"],
        "created_at": "2026-07-11T00:00:00Z",
        "day_window_start_hour": 0, "day_window_end_hour": 23,
    }
    preset.update(extra)
    return preset


def _write_preset(user_id: str, presets: list[dict]) -> None:
    write_compare_briefings(_data_root_users() / user_id, presets)


def _alert(
    *, level: int = 3, hazard: str = "thunderstorm", label: str = "Gewitter",
    region: str = "Gailtal", von_min: int = -5, bis_min: int = 120,
) -> OfficialAlert:
    now = datetime.now(timezone.utc)
    return OfficialAlert(
        source="tdd-1917", hazard=hazard, level=level, label=label,
        valid_from=now + timedelta(minutes=von_min),
        valid_to=now + timedelta(minutes=bis_min),
        region_label=region,
    )


class _PunktQuelle:
    """Echte Quelle (kein Mock): zustaendig fuer EINEN Punkt (0.05-Toleranz),
    liefert steuerbare Alerts."""

    def __init__(self, lat: float, lon: float, alerts: list) -> None:
        self._lat, self._lon, self._alerts = lat, lon, alerts
        self.fetch_calls = 0

    @property
    def name(self) -> str:
        return "tdd-1917-punkt"

    def covers(self, lat: float, lon: float) -> bool:
        return abs(lat - self._lat) < 0.05 and abs(lon - self._lon) < 0.05

    def fetch(self, lat: float, lon: float) -> list:
        self.fetch_calls += 1
        return list(self._alerts)


class _FlaechenQuelle:
    """Echte Quelle, die JEDEN Punkt abdeckt und ueberall DENSELBEN Alert
    liefert — dadurch kollabiert `dedupe_official_alerts()` die Rohtreffer zu
    EINEM `(alert, [loc_a, loc_b])`-Paar (Mehrfach-Ort-pro-Alert, AC-14)."""

    def __init__(self, alerts: list) -> None:
        self._alerts = alerts
        self.fetch_calls = 0

    @property
    def name(self) -> str:
        return "tdd-1917-flaeche"

    def covers(self, lat: float, lon: float) -> bool:
        return True

    def fetch(self, lat: float, lon: float) -> list:
        self.fetch_calls += 1
        return list(self._alerts)


class _RecordingCompareOfficialAlertService(CompareOfficialAlertService):
    """Echte Unterklasse (kein Mock): schreibt die tatsaechlich versendete
    `tagged_alerts`-Struktur mit und traegt optional die Versand-Marke in eine
    Reihenfolge-Liste ein. Alles andere delegiert unveraendert an den echten
    `NotificationService`."""

    def __init__(self, *args, order: list | None = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.sent_tagged: list[list] = []
        self._order = order

    def _notification_service_for(self, preset: dict):
        real = super()._notification_service_for(preset)
        outer = self

        class _Durchreiche:
            def __getattr__(self, name):
                return getattr(real, name)

            def send_multi_location_official_alert(self, *args, **kwargs):
                # Signatur: (preset_name, locs, tagged_alerts, channels, style, ...)
                tagged = kwargs.get("tagged_alerts")
                if tagged is None and len(args) >= 3:
                    tagged = args[2]
                outer.sent_tagged.append(list(tagged or []))
                if outer._order is not None:
                    outer._order.append("send_multi_location_official_alert")
                return real.send_multi_location_official_alert(*args, **kwargs)

        return _Durchreiche()


@pytest.fixture()
def saubere_quellen():
    """Leert die globale Quellen-Registrierung fuer die Dauer eines Tests und
    stellt den Bestand danach exakt wieder her."""
    import services.official_alerts.base as base

    sicherung = list(base._REGISTERED_SOURCES)
    base._REGISTERED_SOURCES.clear()
    try:
        yield base
    finally:
        base._REGISTERED_SOURCES.clear()
        base._REGISTERED_SOURCES.extend(sicherung)


def _event_identity_keys(user_id: str, entity_id: str) -> list[str]:
    from services.alert_state import EVENT_IDENTITY_KEY_PREFIX, AlertStateService

    state = AlertStateService(user_id=user_id).load(entity_id)
    return [k for k in state if isinstance(k, str) and k.startswith(EVENT_IDENTITY_KEY_PREFIX)]


def _event_identity_entries(user_id: str, entity_id: str) -> list[dict]:
    from services.alert_state import AlertStateService

    state = AlertStateService(user_id=user_id).load(entity_id)
    return [state[k] for k in _event_identity_keys(user_id, entity_id)]


def _write_raw_state(user_id: str, entity_id: str, payload: dict) -> None:
    from services.alert_state import AlertStateService

    svc = AlertStateService(user_id=user_id)
    state = svc.load(entity_id)
    state.update(payload)
    svc.save(entity_id, state)


def _not_delivered(user_id: str) -> list[dict]:
    path = get_data_dir(user_id) / "alert_log.json"
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("not_delivered", [])
    except (OSError, ValueError):
        return []


def _event_duplicate_log_entries(user_id: str) -> list[dict]:
    return [
        e for e in _not_delivered(user_id)
        if any(
            c.get("reason") == alert_log.REASON_EVENT_DUPLICATE
            for c in (e.get("channels_not_sent") or [])
        )
    ]


def _register_nowcast_style_entry(
    user_id: str, entity_id: str, loc_id: str, *, severity: str = "HIGH",
    onset_min: int = 8,
) -> None:
    """Legt einen Registereintrag an, wie ihn ein bereits zugestellter
    Radar-Nowcast hinterlaesst (PUNKT-Zeitbezug) — ueber die ECHTE
    `record_event_identity()`, damit Schluesselform und Feldnamen nicht im
    Test nachgebaut werden."""
    from services.alert_gate import record_event_identity

    now = datetime.now(timezone.utc)
    record_event_identity(
        user_id=user_id, entity_id=entity_id, hazard_class="wet",
        segment_ids=[loc_id], severity=severity, now=now,
        point_at=now + timedelta(minutes=onset_min),
    )


# ═════════════════════════════ AC-4 — Wiring ════════════════════════════════


def test_ac4_amtlicher_pfad_ruft_denselben_geteilten_baustein_auf(
    monkeypatch, saubere_quellen,
):
    """AC-4: Der amtliche Compare-Pfad ruft fuer JEDEN betroffenen Ort
    denselben `check_event_identity_gate` auf wie der Radar-Pfad und der
    Trip-Pfad — kein eigener, dritter Baustein.

    RED heute: `compare_official_alert` hat kein Attribut
    `check_event_identity_gate` -> AttributeError beim Patchen."""
    import services.compare_official_alert as com
    from services.alert_gate import GateResult
    from services.alert_gate import check_event_identity_gate as _echt
    from services.official_alerts import register_official_alert_source

    ergebnisse: list = []

    def _spion(*args, **kwargs):
        ergebnis = _echt(*args, **kwargs)
        ergebnisse.append((kwargs, ergebnis))
        return ergebnis

    monkeypatch.setattr(com, "check_event_identity_gate", _spion)

    uid = _uid("ac4")
    _clean_user(uid)
    try:
        save_location(_location("loc-a", "OrtA", LAT_A, LON_A), user_id=uid)
        save_location(_location("loc-b", "OrtB", LAT_B, LON_B), user_id=uid)
        _write_preset(uid, [_preset("p-ac4", ["loc-a", "loc-b"])])
        register_official_alert_source(_PunktQuelle(LAT_A, LON_A, [_alert(region="RegionA")]))
        register_official_alert_source(_PunktQuelle(LAT_B, LON_B, [_alert(region="RegionB")]))

        raus = CompareOfficialAlertService(
            settings=_settings_email_capable_dummy(), user_id=uid,
            mail_sink=lambda subject, body: None,
        ).check_all_compare_presets()

        assert raus == 1, f"Voraussetzung: die amtlichen Warnungen muessen zustellen ({raus!r})"
        assert len(ergebnisse) >= 2, (
            f"check_event_identity_gate muss je betroffenem Ort (2) mindestens "
            f"einmal gerufen werden, gerufen: {len(ergebnisse)}"
        )
        assert all(isinstance(e, GateResult) for _kw, e in ergebnisse), (
            f"Rueckgabewert muss eine echte GateResult-Instanz sein: {ergebnisse!r}"
        )
        for kwargs, _e in ergebnisse:
            segmente = [s for s in (kwargs.get("segment_ids") or []) if s]
            assert segmente, (
                f"AC-0: jeder Compare-Gate-Aufruf muss segment_ids=[loc_id] "
                f"tragen (leer = struktureller No-Op): {kwargs!r}"
            )
    finally:
        _clean_user(uid)


# ═════════════════════ AC-5 — Registrierung nach Erfolg ═════════════════════


def test_ac5_erfolgreiche_zustellung_legt_genau_einen_registereintrag_an(saubere_quellen):
    """AC-5: Nach erfolgreicher Zustellung liegt in der ORT-Datei
    `f"{preset_id}:{loc_id}"` GENAU EIN neuer `event_identity:`-Schluessel mit
    Segment-Kennung, Dringlichkeit und Zeitfenster.

    RED heute: es entsteht kein einziger `event_identity:`-Schluessel."""
    from services.official_alerts import register_official_alert_source

    uid = _uid("ac5")
    _clean_user(uid)
    try:
        save_location(_location("loc-a", "OrtA", LAT_A, LON_A), user_id=uid)
        _write_preset(uid, [_preset("p-ac5", ["loc-a"])])
        register_official_alert_source(_PunktQuelle(LAT_A, LON_A, [_alert()]))

        raus = CompareOfficialAlertService(
            settings=_settings_email_capable_dummy(), user_id=uid,
            mail_sink=lambda subject, body: None,
        ).check_all_compare_presets()
        assert raus == 1, f"Voraussetzung: die amtliche Warnung muss zustellen ({raus!r})"

        eintraege = _event_identity_entries(uid, "p-ac5:loc-a")
        assert len(eintraege) == 1, (
            f"Genau EIN event_identity:-Eintrag erwartet, gefunden: "
            f"{len(eintraege)} ({_event_identity_keys(uid, 'p-ac5:loc-a')!r})"
        )
        eintrag = eintraege[0]
        assert eintrag.get("hazard_class") == "wet", f"Gefahrenklasse fehlt/falsch: {eintrag!r}"
        assert eintrag.get("segment_ids") == ["loc-a"], (
            f"AC-0: segment_ids muss die Ortskennung tragen (leer = No-Op): {eintrag!r}"
        )
        assert eintrag.get("severity"), f"Dringlichkeit fehlt: {eintrag!r}"
        assert eintrag.get("window_start"), f"Fensteranfang fehlt: {eintrag!r}"
        assert eintrag.get("window_end"), f"Fensterende fehlt: {eintrag!r}"
    finally:
        _clean_user(uid)


# ═══════════════ AC-0 (amtlich-Haelfte) + AC-6 — Kernfall ═══════════════════


def test_ac0_amtliche_haelfte_nowcast_zuerst_dann_amtliche_warnung_unterdrueckt(
    saubere_quellen,
):
    """AC-0 (amtlich-Haelfte, End-to-End): Erst stellt ein Compare-Radar-
    Nowcast fuer einen Ort erfolgreich zu (Registereintrag entsteht), danach
    trifft eine amtliche Warnung derselben Klasse fuer DENSELBEN Ort mit
    ueberlappendem Fenster ein — sie wird unterdrueckt.

    Das ist der Beweis, dass die Verdrahtung `segment_ids=[loc.id]` an BEIDEN
    Aufrufstellen (Record im Radar-Pfad UND Check im amtlichen Pfad) wirksam
    ein Duplikat ERKENNT. Mutations-Gegenprobe (PFLICHT laut Spec R-A): wird
    an einer der beiden Stellen `segment_ids=[]` verdrahtet, liefert
    `_find_matching_entry()` (alert_gate.py:508-510) strukturell „kein Match"
    — dieser Test wird dann rot, obwohl der Gate-Aufruf sichtbar stattfindet.

    RED heute: die amtliche Warnung geht raus."""
    from services.compare_radar_alert import CompareRadarAlertService
    from services.official_alerts import register_official_alert_source
    from services.radar_service import RadarNowcastService
    from providers.brightsky import RadarFrame

    uid = _uid("ac0")
    _clean_user(uid)
    try:
        save_location(_location("loc-a", "OrtA", LAT_A, LON_A), user_id=uid)
        _write_preset(uid, [_preset("p-ac0", ["loc-a"], radar_alert_enabled=True)])

        # ── 1. Radar-Nowcast stellt zu (konvektiv -> Dringlichkeit HIGH) ──
        onset = datetime.now(timezone.utc) + timedelta(minutes=8)

        class _Frames:
            def __call__(self, lat, lon):
                return [RadarFrame(timestamp=onset, precip_mm_h=0.6, is_convective=True)]

        raus_radar = CompareRadarAlertService(
            settings=_settings_email_capable_dummy(), user_id=uid,
            radar_service=RadarNowcastService(frame_source=_Frames()),
            mail_sink=lambda subject, body: None,
        ).check_all_compare_presets()
        assert raus_radar == 1, (
            f"Voraussetzung: der Nowcast muss zustellen ({raus_radar!r})"
        )
        assert _event_identity_keys(uid, "p-ac0:loc-a"), (
            "Voraussetzung: der Nowcast muss einen Registereintrag hinterlassen "
            f"— gefunden: {_event_identity_keys(uid, 'p-ac0:loc-a')!r}"
        )

        # ── 2. Amtliche Warnung derselben Klasse, ueberlappendes Fenster ──
        register_official_alert_source(
            _PunktQuelle(LAT_A, LON_A, [_alert(level=3, von_min=-5, bis_min=120)])
        )
        mails: list = []
        svc = _RecordingCompareOfficialAlertService(
            settings=_settings_email_capable_dummy(), user_id=uid,
            mail_sink=lambda subject, body: mails.append((subject, body)),
        )
        raus_amtlich = svc.check_all_compare_presets()

        assert raus_amtlich == 0, (
            f"Die amtliche Warnung ist ein Duplikat des Nowcasts und darf "
            f"NICHT zustellen ({raus_amtlich!r})"
        )
        assert svc.sent_tagged == [], (
            f"Der gebuendelte Versand darf gar nicht erst aufgerufen werden: "
            f"{svc.sent_tagged!r}"
        )
        assert mails == [], f"Es darf keine amtliche Alarm-Mail rausgehen: {mails!r}"
    finally:
        _clean_user(uid)


def test_ac6_registrierter_nowcast_unterdrueckt_die_amtliche_warnung(saubere_quellen):
    """AC-6 (Kernfall): Ein bereits registrierter Nowcast-Eintrag (Klasse
    `wet`, Ort A, Onset T) unterdrueckt eine kurz danach eintreffende amtliche
    Warnung derselben Klasse fuer denselben Ort, deren Gueltigkeitsfenster den
    Onset-Punkt (mit dem bestehenden Puffer) ueberlappt. Der Ort faellt aus der
    zu versendenden `tagged_alerts`-Teilmenge; das Protokoll traegt einen
    `not_delivered`-Eintrag mit `gate_reason=REASON_EVENT_DUPLICATE`.

    RED heute: die amtliche Warnung geht raus, kein Protokolleintrag."""
    from services.official_alerts import register_official_alert_source

    uid = _uid("ac6")
    _clean_user(uid)
    try:
        save_location(_location("loc-a", "OrtA", LAT_A, LON_A), user_id=uid)
        _write_preset(uid, [_preset("p-ac6", ["loc-a"])])
        _register_nowcast_style_entry(uid, "p-ac6:loc-a", "loc-a", severity="HIGH")
        register_official_alert_source(_PunktQuelle(LAT_A, LON_A, [_alert(level=3)]))

        svc = _RecordingCompareOfficialAlertService(
            settings=_settings_email_capable_dummy(), user_id=uid,
            mail_sink=lambda subject, body: None,
        )
        raus = svc.check_all_compare_presets()

        assert raus == 0, (
            f"Die amtliche Warnung ist ein Duplikat des registrierten Nowcasts "
            f"({raus!r})"
        )
        assert svc.sent_tagged == [], (
            f"Kein Versand erwartet: {svc.sent_tagged!r}"
        )
        protokoll = _event_duplicate_log_entries(uid)
        assert protokoll, (
            f"Es muss ein not_delivered-Protokolleintrag mit gate_reason="
            f"{alert_log.REASON_EVENT_DUPLICATE!r} entstehen: "
            f"{_not_delivered(uid)!r}"
        )
        assert any(e.get("entity_type") == "compare" for e in protokoll), (
            f"Der Protokolleintrag gehoert zur Ortsvergleich-Flaeche: {protokoll!r}"
        )
    finally:
        _clean_user(uid)


# ══════════════════ AC-8 — Eskalation durchbricht immer (V2) ════════════════


def test_ac8_hoehere_dringlichkeit_bricht_die_unterdrueckung_durch(saubere_quellen):
    """AC-8 (V2): Eine zweite Meldung derselben Klasse/desselben Orts mit
    HOEHERER Dringlichkeit wird zugestellt — auch wenn ihr Zeitfenster das
    bereits abgedeckte NICHT wesentlich erweitert.

    Beide Faelle im selben Test, damit die Zusicherung nicht trivial wahr ist:
    (a) gleiche/niedrigere Dringlichkeit -> unterdrueckt,
    (b) hoehere Dringlichkeit, Fenster INNERHALB des abgedeckten -> zugestellt.

    Mutations-Gegenprobe (PFLICHT laut Spec): Wer in den Compare-Services eine
    EIGENE Vergleichsfunktion statt `check_event_identity_gate` einbaut, hat
    die Eskalations-Reihenfolge (V2 als struktureller ERSTER Zweig,
    alert_gate.py:605-606) nicht — Fall (b) faellt dann um.

    RED heute: Fall (a) stellt zu, obwohl er unterdruecken muesste."""
    from services.official_alerts import register_official_alert_source

    # ── (a) keine Eskalation -> unterdrueckt ──
    uid_a = _uid("ac8-a")
    _clean_user(uid_a)
    try:
        save_location(_location("loc-a", "OrtA", LAT_A, LON_A), user_id=uid_a)
        _write_preset(uid_a, [_preset("p-ac8", ["loc-a"])])
        # Nowcast-Eintrag HIGH; Warnung Stufe 3 -> MODERATE (keine Eskalation).
        _register_nowcast_style_entry(uid_a, "p-ac8:loc-a", "loc-a", severity="HIGH")
        register_official_alert_source(
            _PunktQuelle(LAT_A, LON_A, [_alert(level=3, von_min=-5, bis_min=60)])
        )
        raus_a = CompareOfficialAlertService(
            settings=_settings_email_capable_dummy(), user_id=uid_a,
            mail_sink=lambda subject, body: None,
        ).check_all_compare_presets()
        assert raus_a == 0, (
            f"Ohne Eskalation muss die Dublette unterdrueckt werden ({raus_a!r})"
        )
    finally:
        _clean_user(uid_a)

    # ── (b) echte Eskalation -> zugestellt ──
    uid_b = _uid("ac8-b")
    _clean_user(uid_b)
    try:
        save_location(_location("loc-a", "OrtA", LAT_A, LON_A), user_id=uid_b)
        _write_preset(uid_b, [_preset("p-ac8", ["loc-a"])])
        # Nowcast-Eintrag LOW; Warnung Stufe 4 -> HIGH (echte Verschaerfung).
        _register_nowcast_style_entry(uid_b, "p-ac8:loc-a", "loc-a", severity="LOW")
        register_official_alert_source(
            _PunktQuelle(LAT_A, LON_A, [_alert(level=4, von_min=-5, bis_min=60)])
        )
        raus_b = CompareOfficialAlertService(
            settings=_settings_email_capable_dummy(), user_id=uid_b,
            mail_sink=lambda subject, body: None,
        ).check_all_compare_presets()
        assert raus_b == 1, (
            f"Eine echte Verschaerfung MUSS durchkommen, auch bei Fenster "
            f"innerhalb des abgedeckten ({raus_b!r})"
        )
    finally:
        _clean_user(uid_b)


# ═════════════ AC-9 (amtlich-Haelfte) — fail-soft Richtung Zustellung ═══════


def test_ac9_amtlich_registereintrag_ohne_zeitbezug_unterdrueckt_nicht(saubere_quellen):
    """AC-9 (fail-soft, amtlich): Ein Registereintrag ohne vergleichbaren
    Zeitbezug erzeugt KEIN Match — die amtliche Warnung wird zugestellt, kein
    Absturz.

    Die Positivkontrolle (intakter Eintrag unterdrueckt) steht in
    `test_ac6_...` derselben Datei.

    RED heute: nicht negativ pruefbar, solange gar nicht gelesen wird — der
    Fall bleibt laut Spec AC-9 als eigener Nachweis stehen; rot wird die Datei
    ueber AC-6."""
    from services.official_alerts import register_official_alert_source

    uid = _uid("ac9a")
    _clean_user(uid)
    try:
        save_location(_location("loc-a", "OrtA", LAT_A, LON_A), user_id=uid)
        _write_preset(uid, [_preset("p-ac9a", ["loc-a"])])
        _write_raw_state(uid, "p-ac9a:loc-a", {
            "event_identity:wet:loc-a:2026-08-18T10:00:00+00:00": {
                "hazard_class": "wet", "segment_ids": ["loc-a"], "severity": "HIGH",
                "point_at": None, "window_start": None, "window_end": None,
                "reported_at": "2026-08-18T10:00:00+00:00",
            },
        })
        register_official_alert_source(_PunktQuelle(LAT_A, LON_A, [_alert(level=3)]))

        raus = CompareOfficialAlertService(
            settings=_settings_email_capable_dummy(), user_id=uid,
            mail_sink=lambda subject, body: None,
        ).check_all_compare_presets()

        assert raus == 1, (
            f"fail-soft: ohne vergleichbaren Zeitbezug entsteht KEIN Match, die "
            f"Warnung muss zugestellt werden ({raus!r})"
        )
        assert len(_event_identity_keys(uid, "p-ac9a:loc-a")) == 2, (
            f"Nach der Zustellung muss NEBEN dem zeitlosen Alt-Eintrag genau ein "
            f"neuer Eintrag stehen: {_event_identity_keys(uid, 'p-ac9a:loc-a')!r}"
        )
    finally:
        _clean_user(uid)


def test_ac9_amtlich_kaputter_registereintrag_unterdrueckt_nicht(saubere_quellen):
    """AC-9 (fail-soft, amtlich): Ein kaputter Registereintrag (fehlendes
    Pflichtfeld `severity`) wird uebersprungen — die amtliche Warnung wird
    zugestellt, kein Absturz (R-E).

    RED heute: der neue, regulaere Registereintrag entsteht nicht."""
    from services.official_alerts import register_official_alert_source

    uid = _uid("ac9b")
    _clean_user(uid)
    try:
        now = datetime.now(timezone.utc)
        save_location(_location("loc-a", "OrtA", LAT_A, LON_A), user_id=uid)
        _write_preset(uid, [_preset("p-ac9b", ["loc-a"])])
        _write_raw_state(uid, "p-ac9b:loc-a", {
            # Passender Ort, passende Klasse, ueberlappendes Fenster — es fehlt
            # AUSSCHLIESSLICH das Pflichtfeld `severity`.
            f"event_identity:wet:loc-a:{(now - timedelta(minutes=5)).isoformat()}": {
                "hazard_class": "wet", "segment_ids": ["loc-a"],
                "point_at": (now + timedelta(minutes=8)).isoformat(),
                "reported_at": now.isoformat(),
            },
        })
        register_official_alert_source(_PunktQuelle(LAT_A, LON_A, [_alert(level=3)]))

        raus = CompareOfficialAlertService(
            settings=_settings_email_capable_dummy(), user_id=uid,
            mail_sink=lambda subject, body: None,
        ).check_all_compare_presets()

        assert raus == 1, (
            f"fail-soft: ein kaputter Registereintrag darf NIE unterdruecken "
            f"({raus!r})"
        )
        assert len(_event_identity_keys(uid, "p-ac9b:loc-a")) == 2, (
            f"Nach der Zustellung muss NEBEN dem kaputten Alt-Eintrag genau ein "
            f"neuer, intakter Eintrag stehen: "
            f"{_event_identity_keys(uid, 'p-ac9b:loc-a')!r}"
        )
    finally:
        _clean_user(uid)


# ═════════ AC-11 — Reihenfolge: Registrierung ERST NACH dem Versand ═════════


def test_ac11_record_event_identity_laeuft_erst_nach_dem_versand(saubere_quellen):
    """AC-11: `record_event_identity` wird ERST NACH
    `notification_service.send_multi_location_official_alert(...)` gerufen —
    und NUR bei `result.sent == True`. Laufzeit-Beobachtung ueber einen echten
    Order-Spy; zweiter Lauf ohne zustellbaren Kanal zeigt, dass dann GAR NICHT
    registriert wird.

    RED heute: `compare_official_alert` hat kein Attribut
    `check_event_identity_gate`/`record_event_identity` -> AttributeError."""
    import services.compare_official_alert as com
    from services.alert_gate import check_event_identity_gate as _echt_gate
    from services.alert_gate import record_event_identity as _echt_record
    from services.official_alerts import register_official_alert_source

    # ── Lauf 1: Zustellung gelingt ──
    reihenfolge: list[str] = []

    mp = pytest.MonkeyPatch()
    mp.setattr(com, "check_event_identity_gate",
               lambda *a, **k: (reihenfolge.append("check_event_identity_gate"),
                                _echt_gate(*a, **k))[1])
    mp.setattr(com, "record_event_identity",
               lambda *a, **k: (reihenfolge.append("record_event_identity"),
                                _echt_record(*a, **k))[1])

    uid = _uid("ac11-ok")
    _clean_user(uid)
    try:
        save_location(_location("loc-a", "OrtA", LAT_A, LON_A), user_id=uid)
        _write_preset(uid, [_preset("p-ac11", ["loc-a"])])
        register_official_alert_source(_PunktQuelle(LAT_A, LON_A, [_alert(level=3)]))

        svc = _RecordingCompareOfficialAlertService(
            settings=_settings_email_capable_dummy(), user_id=uid,
            mail_sink=lambda subject, body: None, order=reihenfolge,
        )
        raus = svc.check_all_compare_presets()

        assert raus == 1, f"Voraussetzung: die Warnung muss zustellen ({raus!r})"
        assert "check_event_identity_gate" in reihenfolge, (
            f"Das Gate muss gerufen werden: {reihenfolge!r}"
        )
        assert "send_multi_location_official_alert" in reihenfolge, (
            f"Der gebuendelte Versand muss gerufen werden: {reihenfolge!r}"
        )
        assert "record_event_identity" in reihenfolge, (
            f"Nach erfolgreicher Zustellung muss registriert werden: {reihenfolge!r}"
        )
        assert (
            reihenfolge.index("check_event_identity_gate")
            < reihenfolge.index("send_multi_location_official_alert")
            < reihenfolge.index("record_event_identity")
        ), (
            f"Falsche Laufzeit-Reihenfolge (Gate -> Versand -> Registrierung): "
            f"{reihenfolge!r}"
        )
    finally:
        mp.undo()
        _clean_user(uid)

    # ── Lauf 2: kein zustellbarer Kanal -> gar keine Registrierung ──
    reihenfolge2: list[str] = []

    mp2 = pytest.MonkeyPatch()
    mp2.setattr(com, "check_event_identity_gate",
                lambda *a, **k: (reihenfolge2.append("check_event_identity_gate"),
                                 _echt_gate(*a, **k))[1])
    mp2.setattr(com, "record_event_identity",
                lambda *a, **k: (reihenfolge2.append("record_event_identity"),
                                 _echt_record(*a, **k))[1])

    uid2 = _uid("ac11-fail")
    _clean_user(uid2)
    try:
        save_location(_location("loc-a", "OrtA", LAT_A, LON_A), user_id=uid2)
        # Warnstufe 2 -> Dringlichkeit LOW, Kanal-Schwelle HIGH -> kein Kanal.
        _write_preset(uid2, [_preset(
            "p-ac11", ["loc-a"], alert_channel_thresholds={"email": "HIGH"},
        )])
        register_official_alert_source(_PunktQuelle(LAT_A, LON_A, [_alert(level=2)]))

        raus2 = CompareOfficialAlertService(
            settings=_settings_email_capable_dummy(), user_id=uid2,
            mail_sink=lambda subject, body: None,
        ).check_all_compare_presets()

        assert raus2 == 0, f"Voraussetzung: ohne Kanal darf nichts rausgehen ({raus2!r})"
        assert "record_event_identity" not in reihenfolge2, (
            f"Ohne erfolgreiche Zustellung darf record_event_identity GAR NICHT "
            f"gerufen werden: {reihenfolge2!r}"
        )
    finally:
        mp2.undo()
        _clean_user(uid2)


# ═══════════════ AC-13 — Batch-Teilfilterung ueber zwei Warnungen ═══════════


def test_ac13_nur_die_duplizierte_warnung_faellt_weg(saubere_quellen):
    """AC-13: Zwei amtliche Warnungen unterschiedlicher Hazards fuer
    unterschiedliche Orte in EINEM Lauf — eine davon Duplikat eines bereits
    registrierten Nowcast-Ereignisses. NUR die duplizierte wird unterdrueckt,
    die andere geht raus (keine Alles-oder-nichts-Entscheidung).

    RED heute: beide gehen raus."""
    from services.official_alerts import register_official_alert_source

    uid = _uid("ac13")
    _clean_user(uid)
    try:
        save_location(_location("loc-a", "OrtDuplikat", LAT_A, LON_A), user_id=uid)
        save_location(_location("loc-b", "OrtEigenstaendig", LAT_B, LON_B), user_id=uid)
        _write_preset(uid, [_preset("p-ac13", ["loc-a", "loc-b"])])
        _register_nowcast_style_entry(uid, "p-ac13:loc-a", "loc-a", severity="HIGH")
        register_official_alert_source(_PunktQuelle(
            LAT_A, LON_A,
            [_alert(level=3, hazard="thunderstorm", label="Gewitter A", region="RegionA")],
        ))
        register_official_alert_source(_PunktQuelle(
            LAT_B, LON_B,
            [_alert(level=3, hazard="flood", label="Hochwasser B", region="RegionB")],
        ))

        svc = _RecordingCompareOfficialAlertService(
            settings=_settings_email_capable_dummy(), user_id=uid,
            mail_sink=lambda subject, body: None,
        )
        raus = svc.check_all_compare_presets()

        assert raus == 1, (
            f"Die eigenstaendige Warnung muss weiterhin zustellen ({raus!r})"
        )
        assert len(svc.sent_tagged) == 1, (
            f"Genau EIN gebuendelter Versand erwartet: {svc.sent_tagged!r}"
        )
        versendet = svc.sent_tagged[0]
        gesendete_orte = sorted({lid for _a, loc_ids in versendet for lid in loc_ids})
        assert gesendete_orte == ["loc-b"], (
            f"Nur die eigenstaendige Warnung fuer loc-b darf uebrig bleiben: "
            f"{versendet!r}"
        )
        assert all(a.hazard == "flood" for a, _ in versendet), (
            f"Die duplizierte Gewitter-Warnung darf nicht mehr dabei sein: "
            f"{versendet!r}"
        )
        assert _event_duplicate_log_entries(uid), (
            f"Protokolleintrag fuer die unterdrueckte Warnung fehlt: "
            f"{_not_delivered(uid)!r}"
        )
    finally:
        _clean_user(uid)


# ═════════ AC-14 — Mehrfach-Ort pro Alert: Paar auf Teilmenge kuerzen ═══════


def test_ac14_ein_alert_zwei_orte_wird_nur_am_duplizierten_ort_unterdrueckt(
    saubere_quellen,
):
    """AC-14 (Mehrfach-Ort-pro-Alert, R-B): EIN amtlicher Alert betrifft ZWEI
    Compare-Orte `(alert, [loc_a, loc_b])`. Fuer `loc_a` existiert bereits ein
    passender Registereintrag, fuer `loc_b` nicht. Das Paar wird auf
    `(alert, [loc_b])` REDUZIERT — nicht komplett verworfen und nicht
    ungefiltert an beide Orte zugestellt.

    RED heute: der Alert geht ungefiltert an beide Orte."""
    from services.official_alerts import register_official_alert_source

    uid = _uid("ac14")
    _clean_user(uid)
    try:
        save_location(_location("loc-a", "OrtA", LAT_A, LON_A), user_id=uid)
        save_location(_location("loc-b", "OrtB", LAT_B, LON_B), user_id=uid)
        _write_preset(uid, [_preset("p-ac14", ["loc-a", "loc-b"])])
        # NUR loc-a hat einen passenden Registereintrag.
        _register_nowcast_style_entry(uid, "p-ac14:loc-a", "loc-a", severity="HIGH")
        # EINE Quelle, die beide Orte abdeckt und ueberall DENSELBEN Alert
        # liefert -> dedupe_official_alerts() kollabiert zu (alert, [a, b]).
        register_official_alert_source(_FlaechenQuelle([_alert(level=3, region="GemeinsameRegion")]))

        svc = _RecordingCompareOfficialAlertService(
            settings=_settings_email_capable_dummy(), user_id=uid,
            mail_sink=lambda subject, body: None,
        )
        raus = svc.check_all_compare_presets()

        assert raus == 1, (
            f"Der nicht-duplizierte Ort muss die Warnung weiterhin bekommen ({raus!r})"
        )
        assert len(svc.sent_tagged) == 1, (
            f"Genau EIN gebuendelter Versand erwartet: {svc.sent_tagged!r}"
        )
        versendet = svc.sent_tagged[0]
        assert len(versendet) == 1, (
            f"Das Paar darf nicht komplett verworfen werden: {versendet!r}"
        )
        _alert_obj, loc_ids = versendet[0]
        assert sorted(loc_ids) == ["loc-b"], (
            f"Das Paar muss auf die verbleibende Orts-Teilmenge [loc-b] "
            f"reduziert werden: {loc_ids!r}"
        )
        assert _event_duplicate_log_entries(uid), (
            f"Protokolleintrag fuer (alert, loc-a) fehlt: {_not_delivered(uid)!r}"
        )
    finally:
        _clean_user(uid)


# ═════════════ AC-15 (amtlich-Haelfte) — Mandantentrennung ══════════════════


def test_ac15_amtlich_registereintrag_von_nutzer_a_wirkt_nicht_auf_nutzer_b(
    saubere_quellen,
):
    """AC-15 (amtlich-Haelfte): Zwei Nutzer mit gleicher `preset_id` und
    gleicher `location_id` fuehren ihre Register UNABHAENGIG. A's Eintrag
    unterdrueckt A's amtliche Warnung (Positivkontrolle im selben Test) — B
    bekommt seine Warnung trotzdem, ohne Rueckfall auf `"default"`.

    RED heute: die Positivkontrolle (A wird unterdrueckt) schlaegt fehl."""
    from services.official_alerts import register_official_alert_source

    uid_a = _uid("ac15-a")
    uid_b = _uid("ac15-b")
    _clean_user(uid_a)
    _clean_user(uid_b)
    try:
        for uid in (uid_a, uid_b):
            save_location(_location("loc-a", "OrtA", LAT_A, LON_A), user_id=uid)
            _write_preset(uid, [_preset("p-ac15", ["loc-a"])])
        register_official_alert_source(_PunktQuelle(LAT_A, LON_A, [_alert(level=3)]))

        # NUR Nutzer A registriert.
        _register_nowcast_style_entry(uid_a, "p-ac15:loc-a", "loc-a", severity="HIGH")

        raus_a = CompareOfficialAlertService(
            settings=_settings_email_capable_dummy(), user_id=uid_a,
            mail_sink=lambda subject, body: None,
        ).check_all_compare_presets()
        raus_b = CompareOfficialAlertService(
            settings=_settings_email_capable_dummy(), user_id=uid_b,
            mail_sink=lambda subject, body: None,
        ).check_all_compare_presets()

        assert raus_a == 0, (
            "Positivkontrolle: A's eigener Registereintrag MUSS A's amtliche "
            f"Warnung unterdruecken ({raus_a!r})"
        )
        assert raus_b == 1, (
            "Mandantentrennung: A's Registereintrag darf B NICHT betreffen — "
            f"B muss seine Warnung bekommen ({raus_b!r})"
        )
        assert _event_identity_keys(uid_b, "p-ac15:loc-a"), (
            "B muss seinen EIGENEN Registereintrag bekommen haben"
        )
    finally:
        _clean_user(uid_a)
        _clean_user(uid_b)
