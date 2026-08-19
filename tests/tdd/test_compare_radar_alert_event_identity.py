"""TDD RED — Issue #1917 (Scheibe S4b-2, Epic #1458 Teil 4b):
quellenuebergreifende Ereignis-Identitaets-Entdopplung auf der
ORTSVERGLEICH-Radar-Flaeche.

SPEC: docs/specs/modules/rework_1917_s4b2_compare_entdopplung.md

Abgedeckte Acceptance Criteria in DIESER Datei:
AC-0 (Radar-Haelfte, inkl. Mutations-Gegenprobe zu `segment_ids=[]`),
AC-1, AC-2, AC-3, AC-7, AC-9 (Radar-Haelfte), AC-10, AC-12,
AC-15 (Radar-Haelfte), AC-17.

RED-Grund (heute): `src/services/compare_radar_alert.py` importiert und ruft
`check_event_identity_gate`/`record_event_identity` NICHT — der Spion-Aufbau
scheitert mit AttributeError, und die Verhaltenstests finden weder
Unterdrueckung noch Registereintrag.

Keine Mocks (CLAUDE.md): echte Presets/Orte/Registerdateien unter dem von
`tests/conftest.py` isolierten Datenwurzel-Pfad, echte `RadarFrame`-Fixtures
ueber den `frame_source`-DI-Seam von `RadarNowcastService`, echter
`mail_sink`-Seam statt SMTP. Die Spione delegieren an die ECHTEN Funktionen
und geben deren echten Rueckgabewert zurueck (Vorbild
`test_issue_1088_official_alert_triggers.py::TestS4bEventIdentityWiring`) —
gepatcht wird auf den Modul-Namensraum des VERBRAUCHENDEN Moduls, weil
`compare_radar_alert.py` den Baustein benannt importiert.
"""
from __future__ import annotations

import inspect
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
from services.compare_radar_alert import CompareRadarAlertService

from tests.helpers.compare_briefings import write_compare_briefings

# Ein Ort in Oesterreich (Europe/Vienna) je Kennung — klar getrennte
# Koordinaten, damit `_CoordFrameSource` sie sicher auseinanderhaelt.
LAT_A, LON_A = 46.62, 13.68
LAT_B, LON_B = 46.20, 12.40


# ───────────────────────────── Fixtures & Builder ───────────────────────────


def _data_root_users() -> Path:
    """Funktion statt Konstante (#1595): die Datenwurzel loest erst zur
    Laufzeit auf die von der #1133-Fixture gesetzte Basis auf."""
    from app.loader import get_data_root

    return get_data_root() / "users"


def _uid(prefix: str) -> str:
    return f"tdd-1917r-{prefix}-{uuid.uuid4().hex[:6]}"


def _clean_user(user_id: str) -> None:
    d = _data_root_users() / user_id
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)


def _settings_email_capable_dummy() -> Settings:
    """`can_send_email() == True` ohne Netzwerk — der `mail_sink`-Zweig
    ersetzt den SMTP-Versand vollstaendig, die Dummy-Creds werden nie
    gewaehlt."""
    return Settings(
        smtp_host="dummy.invalid", smtp_user="dummy", smtp_pass="dummy",
        mail_to="dummy@example.com",
    )


def _location(loc_id: str, name: str, lat: float, lon: float) -> SavedLocation:
    return SavedLocation(id=loc_id, name=name, lat=lat, lon=lon, elevation_m=1000)


def _radar_preset(preset_id: str, location_ids: list[str], **extra) -> dict:
    preset: dict = {
        "id": preset_id, "name": preset_id, "user_id": "default",
        "location_ids": location_ids, "schedule": "daily", "weekday": 4,
        "profil": "ALLGEMEIN", "hour_from": 9, "hour_to": 16,
        "empfaenger": ["gregor-test@henemm.com"],
        "created_at": "2026-07-10T00:00:00Z",
        "radar_alert_enabled": True,
    }
    preset.update(extra)
    return preset


def _write_preset(user_id: str, presets: list[dict]) -> None:
    write_compare_briefings(_data_root_users() / user_id, presets)


def _wet_frame(onset_minutes: int, *, is_convective: bool = False, rate: float = 0.3) -> list:
    """Ein echter `RadarFrame` `onset_minutes` in der Zukunft. `rate=0.3`
    ergibt „Leichter Regen" -> Dringlichkeit LOW (`alert_urgency`), damit die
    Kanal-Schwelle in den Tests gezielt als Zustell-Sperre benutzt werden
    kann."""
    from providers.brightsky import RadarFrame

    ts = datetime.now(timezone.utc) + timedelta(minutes=onset_minutes)
    return [RadarFrame(timestamp=ts, precip_mm_h=rate, is_convective=is_convective)]


class _CoordFrameSource:
    """Echter, aufrufbarer `frame_source`-Doppelgaenger (kein Mock) fuer
    `RadarNowcastService(frame_source=...)` — liefert je Koordinate einen
    vorher festgelegten, echten Framesatz."""

    def __init__(self, by_coord: dict[tuple[float, float], list]) -> None:
        self._by_coord = by_coord
        self.calls: list[tuple[float, float]] = []

    def __call__(self, lat: float, lon: float) -> list:
        self.calls.append((lat, lon))
        return self._by_coord.get((round(lat, 4), round(lon, 4)), [])


class _RecordingCompareRadarAlertService(CompareRadarAlertService):
    """Echte Unterklasse (kein Mock, Vorbild `_RecordingTripAlertService` in
    `test_issue_1088_official_alert_triggers.py`): schreibt mit, WELCHE
    Ortsliste tatsaechlich in den gebuendelten Versand geht, und traegt
    optional die Versand-Marke in eine Reihenfolge-Liste ein. Alles andere
    delegiert unveraendert an den echten `NotificationService`."""

    def __init__(self, *args, order: list | None = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.sent_entities: list[list] = []
        self._order = order

    def _notification_service_for(self, preset: dict):
        real = super()._notification_service_for(preset)
        outer = self

        class _Durchreiche:
            def __getattr__(self, name):
                return getattr(real, name)

            def send_multi_location_radar_alert(self, *args, **kwargs):
                entities = kwargs.get("entities")
                if entities is None and args:
                    entities = args[0]
                outer.sent_entities.append(list(entities or []))
                if outer._order is not None:
                    outer._order.append("send_multi_location_radar_alert")
                return real.send_multi_location_radar_alert(*args, **kwargs)

        return _Durchreiche()


def _radar_service(by_coord: dict):
    from services.radar_service import RadarNowcastService

    return RadarNowcastService(frame_source=_CoordFrameSource(by_coord))


def _event_identity_keys(user_id: str, entity_id: str) -> list[str]:
    from services.alert_state import EVENT_IDENTITY_KEY_PREFIX, AlertStateService

    state = AlertStateService(user_id=user_id).load(entity_id)
    return [k for k in state if isinstance(k, str) and k.startswith(EVENT_IDENTITY_KEY_PREFIX)]


def _event_identity_entries(user_id: str, entity_id: str) -> list[dict]:
    from services.alert_state import AlertStateService

    state = AlertStateService(user_id=user_id).load(entity_id)
    return [state[k] for k in _event_identity_keys(user_id, entity_id)]


def _write_raw_state(user_id: str, entity_id: str, payload: dict) -> None:
    """Schreibt einen ROHEN Registereintrag (auch bewusst kaputte Formen, die
    `record_event_identity()` selbst nie erzeugen wuerde) — Read-Modify-Write
    ueber den echten `AlertStateService`."""
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


def _register_official_style_entry(
    user_id: str, entity_id: str, loc_id: str, *, severity: str = "HIGH",
    start_offset_min: int = -60, end_offset_min: int = 120,
) -> None:
    """Legt einen Registereintrag an, wie ihn eine bereits zugestellte
    AMTLICHE Warnung hinterlassen wuerde (Intervall statt Punkt) — ueber die
    ECHTE `record_event_identity()`, damit Schluesselform und Feldnamen nicht
    im Test nachgebaut werden."""
    from services.alert_gate import record_event_identity

    now = datetime.now(timezone.utc)
    record_event_identity(
        user_id=user_id, entity_id=entity_id, hazard_class="wet",
        segment_ids=[loc_id], severity=severity, now=now,
        window_start=now + timedelta(minutes=start_offset_min),
        window_end=now + timedelta(minutes=end_offset_min),
    )


# ═════════════════════════════ AC-1 — Wiring ════════════════════════════════


def test_ac1_radar_pfad_ruft_denselben_geteilten_baustein_auf(monkeypatch):
    """AC-1: Der Compare-Radar-Pfad ruft fuer JEDEN getriggerten Ort denselben
    `check_event_identity_gate` auf, der schon auf der Trip-Flaeche laeuft —
    kein eigener, zweiter Compare-Baustein.

    Spion auf dem Modul-Namensraum von `compare_radar_alert` (benannter
    Import), delegiert an die ECHTE Funktion und gibt deren echtes
    `GateResult` zurueck.

    RED heute: `compare_radar_alert` hat kein Attribut
    `check_event_identity_gate` -> AttributeError beim Patchen."""
    import services.compare_radar_alert as crm
    from services.alert_gate import GateResult
    from services.alert_gate import check_event_identity_gate as _echt

    ergebnisse: list = []

    def _spion(*args, **kwargs):
        ergebnis = _echt(*args, **kwargs)
        ergebnisse.append((kwargs, ergebnis))
        return ergebnis

    monkeypatch.setattr(crm, "check_event_identity_gate", _spion)

    uid = _uid("ac1")
    _clean_user(uid)
    try:
        save_location(_location("loc-a", "OrtA", LAT_A, LON_A), user_id=uid)
        save_location(_location("loc-b", "OrtB", LAT_B, LON_B), user_id=uid)
        _write_preset(uid, [_radar_preset("p-ac1", ["loc-a", "loc-b"])])

        svc = CompareRadarAlertService(
            settings=_settings_email_capable_dummy(), user_id=uid,
            radar_service=_radar_service({
                (LAT_A, LON_A): _wet_frame(8),
                (LAT_B, LON_B): _wet_frame(9),
            }),
            mail_sink=lambda subject, body: None,
        )
        raus = svc.check_all_compare_presets()

        assert raus == 1, f"Voraussetzung: der gebuendelte Radar-Alarm muss zustellen ({raus!r})"
        assert len(ergebnisse) >= 2, (
            f"check_event_identity_gate muss je getriggertem Ort (2) mindestens "
            f"einmal gerufen werden, gerufen: {len(ergebnisse)}"
        )
        assert all(isinstance(e, GateResult) for _kw, e in ergebnisse), (
            f"Rueckgabewert muss eine echte GateResult-Instanz sein: {ergebnisse!r}"
        )
        # AC-0-Design an der Aufrufstelle: NIE mit leerer Segment-Menge.
        for kwargs, _e in ergebnisse:
            segmente = [s for s in (kwargs.get("segment_ids") or []) if s]
            assert segmente, (
                f"AC-0: jeder Compare-Gate-Aufruf muss segment_ids=[loc.id] "
                f"tragen (leer = struktureller No-Op): {kwargs!r}"
            )
    finally:
        _clean_user(uid)


# ═══════════════════ AC-2/AC-3 — Registrierung nur nach Erfolg ══════════════


def test_ac2_erfolgreiche_zustellung_legt_genau_einen_registereintrag_an():
    """AC-2: Nach erfolgreicher Zustellung liegt in der ORT-Datei
    `f"{preset_id}:{loc.id}"` GENAU EIN neuer `event_identity:`-Schluessel mit
    allen Pflichtfeldern — und seine `segment_ids` sind NICHT leer (AC-0).

    RED heute: es entsteht kein einziger `event_identity:`-Schluessel."""
    uid = _uid("ac2")
    _clean_user(uid)
    try:
        save_location(_location("loc-a", "OrtA", LAT_A, LON_A), user_id=uid)
        _write_preset(uid, [_radar_preset("p-ac2", ["loc-a"])])

        svc = CompareRadarAlertService(
            settings=_settings_email_capable_dummy(), user_id=uid,
            radar_service=_radar_service({(LAT_A, LON_A): _wet_frame(8)}),
            mail_sink=lambda subject, body: None,
        )
        raus = svc.check_all_compare_presets()
        assert raus == 1, f"Voraussetzung: der Radar-Alarm muss zustellen ({raus!r})"

        eintraege = _event_identity_entries(uid, "p-ac2:loc-a")
        assert len(eintraege) == 1, (
            f"Genau EIN event_identity:-Eintrag in der Ort-Datei erwartet, "
            f"gefunden: {len(eintraege)} ({_event_identity_keys(uid, 'p-ac2:loc-a')!r})"
        )
        eintrag = eintraege[0]
        assert eintrag.get("hazard_class") == "wet", f"Gefahrenklasse fehlt/falsch: {eintrag!r}"
        assert eintrag.get("segment_ids") == ["loc-a"], (
            f"AC-0: segment_ids muss die Ortskennung tragen (leer = No-Op): {eintrag!r}"
        )
        assert eintrag.get("severity"), f"Dringlichkeit fehlt: {eintrag!r}"
        assert eintrag.get("point_at"), f"Zeitbezug (Onset) fehlt: {eintrag!r}"
        assert eintrag.get("reported_at"), f"Meldezeitpunkt fehlt: {eintrag!r}"
    finally:
        _clean_user(uid)


def test_ac3_ohne_zustellbaren_kanal_entsteht_kein_registereintrag():
    """AC-3 (F001-Symmetrie): Scheitert die Zustellung, entsteht KEIN
    Registereintrag.

    Mit Positivkontrolle im selben Test (sonst waere die Zusicherung heute
    trivial wahr, weil ueberhaupt nie registriert wird): derselbe Aufbau OHNE
    Kanal-Schwelle MUSS einen Eintrag erzeugen.

    Der Zustell-Fehlschlag wird ueber die Kanal-Schwelle erzeugt
    (`alert_channel_thresholds={"email": "HIGH"}` gegen eine LOW-Meldung) —
    damit bleibt kein Kanal uebrig, `notif_result.sent` ist False, und es
    entsteht kein Netzwerkverkehr.

    RED heute: die Positivkontrolle findet keinen Eintrag."""
    # ── Positivkontrolle: Zustellung gelingt -> Eintrag entsteht ──
    uid_ok = _uid("ac3-ok")
    _clean_user(uid_ok)
    try:
        save_location(_location("loc-a", "OrtA", LAT_A, LON_A), user_id=uid_ok)
        _write_preset(uid_ok, [_radar_preset("p-ac3", ["loc-a"])])
        raus = CompareRadarAlertService(
            settings=_settings_email_capable_dummy(), user_id=uid_ok,
            radar_service=_radar_service({(LAT_A, LON_A): _wet_frame(8)}),
            mail_sink=lambda subject, body: None,
        ).check_all_compare_presets()
        assert raus == 1, f"Positivkontrolle: der Alarm muss zustellen ({raus!r})"
        assert _event_identity_keys(uid_ok, "p-ac3:loc-a"), (
            "Positivkontrolle: nach erfolgreicher Zustellung MUSS ein "
            "event_identity:-Eintrag existieren — sonst bewacht der "
            "Negativfall unten nichts."
        )
    finally:
        _clean_user(uid_ok)

    # ── Eigentliche Zusicherung: kein zustellbarer Kanal -> kein Eintrag ──
    uid = _uid("ac3-fail")
    _clean_user(uid)
    try:
        save_location(_location("loc-a", "OrtA", LAT_A, LON_A), user_id=uid)
        _write_preset(uid, [_radar_preset(
            "p-ac3", ["loc-a"], alert_channel_thresholds={"email": "HIGH"},
        )])

        vorher = sorted(_event_identity_keys(uid, "p-ac3:loc-a"))
        raus = CompareRadarAlertService(
            settings=_settings_email_capable_dummy(), user_id=uid,
            radar_service=_radar_service({(LAT_A, LON_A): _wet_frame(8)}),
            mail_sink=lambda subject, body: None,
        ).check_all_compare_presets()
        nachher = sorted(_event_identity_keys(uid, "p-ac3:loc-a"))

        assert raus == 0, f"Voraussetzung: ohne zustellbaren Kanal darf nichts rausgehen ({raus!r})"
        assert vorher == nachher == [], (
            f"Ohne erfolgreiche Zustellung darf KEIN Registereintrag entstehen: "
            f"vorher={vorher!r} nachher={nachher!r}"
        )
    finally:
        _clean_user(uid)


# ═════════════ AC-0 (Radar-Haelfte) — segment_ids=[loc.id] wirkt ════════════


def test_ac0_radar_haelfte_der_registereintrag_wird_mit_ortskennung_gefunden():
    """AC-0 (Radar-Haelfte, inkl. Mutations-Gegenprobe): Der vom Compare-
    Radar-Pfad angelegte Registereintrag wird von einer NACHFOLGENDEN Pruefung
    mit `segment_ids=[loc.id]` tatsaechlich als Duplikat ERKANNT —
    `allowed=False` und `reason=REASON_EVENT_DUPLICATE`.

    Gegenprobe im selben Test: dieselbe Pruefung mit `segment_ids=[]` findet
    strukturell NIE ein Match (`alert_gate.py:508-510`, „AC-5 Bruchstelle").
    Das ist genau der stille No-Op-Bug, den AC-0 ausschliesst: wuerde die
    Verdrahtung `segment_ids=[]` verwenden, saehe sie verdrahtet aus, wuerde
    aber nie unterdruecken — der erste Teilbeweis (Eintrag traegt die
    Ortskennung) faellt dann um.

    RED heute: der Compare-Radar-Pfad legt gar keinen Eintrag an, also findet
    auch die Pruefung mit `segment_ids=[loc.id]` nichts."""
    from services.alert_gate import check_event_identity_gate

    uid = _uid("ac0")
    _clean_user(uid)
    try:
        save_location(_location("loc-a", "OrtA", LAT_A, LON_A), user_id=uid)
        _write_preset(uid, [_radar_preset("p-ac0", ["loc-a"])])

        raus = CompareRadarAlertService(
            settings=_settings_email_capable_dummy(), user_id=uid,
            radar_service=_radar_service({(LAT_A, LON_A): _wet_frame(8, is_convective=True)}),
            mail_sink=lambda subject, body: None,
        ).check_all_compare_presets()
        assert raus == 1, f"Voraussetzung: der Nowcast muss zustellen ({raus!r})"

        now = datetime.now(timezone.utc)
        mit_ortskennung = check_event_identity_gate(
            user_id=uid, entity_id="p-ac0:loc-a", hazard_class="wet",
            segment_ids=["loc-a"], severity="MODERATE", now=now,
            window_start=now - timedelta(minutes=5),
            window_end=now + timedelta(hours=2),
        )
        assert mit_ortskennung.allowed is False, (
            "AC-0: die zweite Meldung desselben Ortes/derselben Klasse mit "
            "ueberlappendem Fenster MUSS als Duplikat erkannt werden — "
            f"erhalten: {mit_ortskennung!r}"
        )
        assert mit_ortskennung.reason == alert_log.REASON_EVENT_DUPLICATE, (
            f"Falscher Unterdrueckungsgrund: {mit_ortskennung!r}"
        )

        ohne_ortskennung = check_event_identity_gate(
            user_id=uid, entity_id="p-ac0:loc-a", hazard_class="wet",
            segment_ids=[], severity="MODERATE", now=now,
            window_start=now - timedelta(minutes=5),
            window_end=now + timedelta(hours=2),
        )
        assert ohne_ortskennung.allowed is True, (
            "Gegenprobe: eine LEERE Segment-Menge findet strukturell nie ein "
            "Match — genau deshalb darf die Compare-Verdrahtung sie nie "
            f"verwenden. Erhalten: {ohne_ortskennung!r}"
        )
    finally:
        _clean_user(uid)


# ═══════════ AC-7 — Gegenrichtung: amtlich registriert, Nowcast raus ════════


def test_ac7_registrierte_amtliche_warnung_unterdrueckt_den_nowcast():
    """AC-7: Ist fuer einen Compare-Ort bereits ein amtlicher Eintrag
    derselben Gefahrenklasse registriert, wird ein danach ausgeloester
    Radar-Nowcast mit ueberlappendem Zeitbezug UNTERDRUECKT — die Entdopplung
    wirkt symmetrisch in beide Richtungen (dasselbe Register, wer zuerst
    zustellt, schreibt).

    RED heute: der Compare-Radar-Pfad kennt das Register nicht und stellt zu."""
    uid = _uid("ac7")
    _clean_user(uid)
    try:
        save_location(_location("loc-a", "OrtA", LAT_A, LON_A), user_id=uid)
        _write_preset(uid, [_radar_preset("p-ac7", ["loc-a"])])
        _register_official_style_entry(uid, "p-ac7:loc-a", "loc-a", severity="HIGH")

        mails: list = []
        svc = _RecordingCompareRadarAlertService(
            settings=_settings_email_capable_dummy(), user_id=uid,
            radar_service=_radar_service({(LAT_A, LON_A): _wet_frame(8)}),
            mail_sink=lambda subject, body: mails.append((subject, body)),
        )
        raus = svc.check_all_compare_presets()

        assert raus == 0, (
            f"Der Nowcast ist ein Duplikat der bereits gemeldeten amtlichen "
            f"Warnung und darf NICHT zustellen ({raus!r})"
        )
        assert mails == [], f"Es darf keine Radar-Alarm-Mail rausgehen: {mails!r}"
        assert svc.sent_entities == [], (
            f"Der gebuendelte Versand darf gar nicht erst aufgerufen werden: "
            f"{svc.sent_entities!r}"
        )
    finally:
        _clean_user(uid)


# ═══════════════ AC-9 (Radar-Haelfte) — fail-soft Richtung Zustellung ═══════


def test_ac9_radar_registereintrag_ohne_zeitbezug_unterdrueckt_nicht():
    """AC-9 (fail-soft, Radar): Ein Registereintrag OHNE vergleichbaren
    Zeitbezug erzeugt KEIN Match — der Nowcast wird zugestellt, kein Absturz.

    Positivkontrolle im selben Test (sonst waere die Zusicherung heute
    trivial wahr): derselbe Aufbau mit intaktem Zeitbezug MUSS unterdruecken.

    RED heute: die Positivkontrolle stellt zu, obwohl sie unterdruecken
    muesste."""
    # ── Positivkontrolle: intakter Eintrag unterdrueckt ──
    uid_ok = _uid("ac9a-ok")
    _clean_user(uid_ok)
    try:
        save_location(_location("loc-a", "OrtA", LAT_A, LON_A), user_id=uid_ok)
        _write_preset(uid_ok, [_radar_preset("p-ac9a", ["loc-a"])])
        _register_official_style_entry(uid_ok, "p-ac9a:loc-a", "loc-a", severity="HIGH")
        raus_ok = CompareRadarAlertService(
            settings=_settings_email_capable_dummy(), user_id=uid_ok,
            radar_service=_radar_service({(LAT_A, LON_A): _wet_frame(8)}),
            mail_sink=lambda subject, body: None,
        ).check_all_compare_presets()
        assert raus_ok == 0, (
            "Positivkontrolle: ein INTAKTER, passender Registereintrag MUSS "
            f"unterdruecken — sonst bewacht der fail-soft-Fall nichts ({raus_ok!r})"
        )
    finally:
        _clean_user(uid_ok)

    # ── fail-soft: Eintrag ohne jeden Zeitbezug ──
    uid = _uid("ac9a")
    _clean_user(uid)
    try:
        save_location(_location("loc-a", "OrtA", LAT_A, LON_A), user_id=uid)
        _write_preset(uid, [_radar_preset("p-ac9a", ["loc-a"])])
        _write_raw_state(uid, "p-ac9a:loc-a", {
            "event_identity:wet:loc-a:2026-08-18T10:00:00+00:00": {
                "hazard_class": "wet", "segment_ids": ["loc-a"], "severity": "HIGH",
                "point_at": None, "window_start": None, "window_end": None,
                "reported_at": "2026-08-18T10:00:00+00:00",
            },
        })

        raus = CompareRadarAlertService(
            settings=_settings_email_capable_dummy(), user_id=uid,
            radar_service=_radar_service({(LAT_A, LON_A): _wet_frame(8)}),
            mail_sink=lambda subject, body: None,
        ).check_all_compare_presets()

        assert raus == 1, (
            f"fail-soft: ohne vergleichbaren Zeitbezug entsteht KEIN Match, "
            f"der Nowcast muss zugestellt werden ({raus!r})"
        )
    finally:
        _clean_user(uid)


def test_ac9_radar_kaputter_registereintrag_unterdrueckt_nicht():
    """AC-9 (fail-soft, Radar): Ein kaputter Registereintrag (fehlendes
    `severity`-Feld) wird uebersprungen — der Nowcast wird zugestellt, kein
    Absturz (R-E: ein unbekanntes Format darf NIE als Match gelten).

    RED heute: nicht als Verhalten pruefbar, weil der Pfad das Register
    ueberhaupt nicht liest — der Test wird ueber die im ersten fail-soft-Test
    verankerte Positivkontrolle mitgetragen und bleibt hier bewusst als
    eigener Fall stehen (Spec AC-9: „ein Fall mit kaputtem Registereintrag")."""
    uid = _uid("ac9b")
    _clean_user(uid)
    try:
        save_location(_location("loc-a", "OrtA", LAT_A, LON_A), user_id=uid)
        _write_preset(uid, [_radar_preset("p-ac9b", ["loc-a"])])
        now = datetime.now(timezone.utc)
        _write_raw_state(uid, "p-ac9b:loc-a", {
            # Passender Ort, passende Klasse, ueberlappendes Fenster — es fehlt
            # AUSSCHLIESSLICH das Pflichtfeld `severity`.
            f"event_identity:wet:loc-a:{(now - timedelta(minutes=5)).isoformat()}": {
                "hazard_class": "wet", "segment_ids": ["loc-a"],
                "window_start": (now - timedelta(minutes=60)).isoformat(),
                "window_end": (now + timedelta(minutes=120)).isoformat(),
                "reported_at": now.isoformat(),
            },
        })

        raus = CompareRadarAlertService(
            settings=_settings_email_capable_dummy(), user_id=uid,
            radar_service=_radar_service({(LAT_A, LON_A): _wet_frame(8)}),
            mail_sink=lambda subject, body: None,
        ).check_all_compare_presets()

        assert raus == 1, (
            f"fail-soft: ein kaputter Registereintrag darf NIE unterdruecken "
            f"({raus!r})"
        )
        # Der Lauf muss trotzdem regulaer registriert haben (Beweis, dass der
        # Pfad das Register ueberhaupt anfasst — sonst waere die Zusicherung
        # oben trivial wahr).
        assert len(_event_identity_keys(uid, "p-ac9b:loc-a")) == 2, (
            f"Nach der Zustellung muss NEBEN dem kaputten Alt-Eintrag genau ein "
            f"neuer, intakter Eintrag stehen: "
            f"{_event_identity_keys(uid, 'p-ac9b:loc-a')!r}"
        )
    finally:
        _clean_user(uid)


# ═════════ AC-10 — Reihenfolge: Registrierung ERST NACH dem Versand ═════════


def test_ac10_record_event_identity_laeuft_erst_nach_dem_versand():
    """AC-10: `record_event_identity` wird ERST NACH
    `notification_service.send_multi_location_radar_alert(...)` gerufen — und
    NUR bei `notif_result.sent == True`.

    Beobachtet zur LAUFZEIT ueber eine echte Aufruf-Sequenz (Order-Spy); ein
    Quellcode-Grep genuegt laut Spec ausdruecklich nicht. Zweiter Lauf ohne
    zustellbaren Kanal zeigt, dass dann GAR NICHT registriert wird.

    RED heute: `compare_radar_alert` hat kein Attribut
    `check_event_identity_gate`/`record_event_identity` -> AttributeError."""
    import services.compare_radar_alert as crm
    from services.alert_gate import check_event_identity_gate as _echt_gate
    from services.alert_gate import record_event_identity as _echt_record

    # ── Lauf 1: Zustellung gelingt ──
    reihenfolge: list[str] = []

    def _spion_gate(*args, **kwargs):
        reihenfolge.append("check_event_identity_gate")
        return _echt_gate(*args, **kwargs)

    def _spion_record(*args, **kwargs):
        reihenfolge.append("record_event_identity")
        return _echt_record(*args, **kwargs)

    mp = pytest.MonkeyPatch()
    mp.setattr(crm, "check_event_identity_gate", _spion_gate)
    mp.setattr(crm, "record_event_identity", _spion_record)

    uid = _uid("ac10-ok")
    _clean_user(uid)
    try:
        save_location(_location("loc-a", "OrtA", LAT_A, LON_A), user_id=uid)
        _write_preset(uid, [_radar_preset("p-ac10", ["loc-a"])])
        svc = _RecordingCompareRadarAlertService(
            settings=_settings_email_capable_dummy(), user_id=uid,
            radar_service=_radar_service({(LAT_A, LON_A): _wet_frame(8)}),
            mail_sink=lambda subject, body: None, order=reihenfolge,
        )
        raus = svc.check_all_compare_presets()

        assert raus == 1, f"Voraussetzung: der Radar-Alarm muss zustellen ({raus!r})"
        assert "check_event_identity_gate" in reihenfolge, (
            f"Das Gate muss gerufen werden: {reihenfolge!r}"
        )
        assert "send_multi_location_radar_alert" in reihenfolge, (
            f"Der gebuendelte Versand muss gerufen werden: {reihenfolge!r}"
        )
        assert "record_event_identity" in reihenfolge, (
            f"Nach erfolgreicher Zustellung muss registriert werden: {reihenfolge!r}"
        )
        assert (
            reihenfolge.index("check_event_identity_gate")
            < reihenfolge.index("send_multi_location_radar_alert")
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

    def _spion_gate2(*args, **kwargs):
        reihenfolge2.append("check_event_identity_gate")
        return _echt_gate(*args, **kwargs)

    def _spion_record2(*args, **kwargs):
        reihenfolge2.append("record_event_identity")
        return _echt_record(*args, **kwargs)

    mp2 = pytest.MonkeyPatch()
    mp2.setattr(crm, "check_event_identity_gate", _spion_gate2)
    mp2.setattr(crm, "record_event_identity", _spion_record2)

    uid2 = _uid("ac10-fail")
    _clean_user(uid2)
    try:
        save_location(_location("loc-a", "OrtA", LAT_A, LON_A), user_id=uid2)
        _write_preset(uid2, [_radar_preset(
            "p-ac10", ["loc-a"], alert_channel_thresholds={"email": "HIGH"},
        )])
        raus2 = CompareRadarAlertService(
            settings=_settings_email_capable_dummy(), user_id=uid2,
            radar_service=_radar_service({(LAT_A, LON_A): _wet_frame(8)}),
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


# ══════════════════ AC-12 — Batch-Teilfilterung im Radar-Pfad ═══════════════


def test_ac12_nur_der_duplizierte_ort_faellt_aus_dem_buendel():
    """AC-12: Zwei getriggerte Orte in EINEM Preset-Lauf, einer davon Duplikat
    eines bereits registrierten amtlichen Ereignisses — NUR dieser Ort faellt
    aus der gebuendelten Radar-Alarm-Mail, der andere bleibt enthalten. Keine
    Alles-oder-nichts-Entscheidung ueber das ganze Preset (R-D).

    RED heute: beide Orte gehen raus."""
    uid = _uid("ac12")
    _clean_user(uid)
    try:
        save_location(_location("loc-a", "OrtDuplikat", LAT_A, LON_A), user_id=uid)
        save_location(_location("loc-b", "OrtEigenstaendig", LAT_B, LON_B), user_id=uid)
        _write_preset(uid, [_radar_preset("p-ac12", ["loc-a", "loc-b"])])
        _register_official_style_entry(uid, "p-ac12:loc-a", "loc-a", severity="HIGH")

        mails: list = []
        svc = _RecordingCompareRadarAlertService(
            settings=_settings_email_capable_dummy(), user_id=uid,
            radar_service=_radar_service({
                (LAT_A, LON_A): _wet_frame(8),
                (LAT_B, LON_B): _wet_frame(9),
            }),
            mail_sink=lambda subject, body: mails.append((subject, body)),
        )
        raus = svc.check_all_compare_presets()

        assert raus == 1, (
            f"Der eigenstaendige Ort muss weiterhin alarmieren ({raus!r})"
        )
        assert len(svc.sent_entities) == 1, (
            f"Genau EIN gebuendelter Versand erwartet: {svc.sent_entities!r}"
        )
        gesendete_orte = sorted(loc.id for _name, loc, _nc in svc.sent_entities[0])
        assert gesendete_orte == ["loc-b"], (
            f"Nur der nicht-duplizierte Ort darf im Buendel stehen: "
            f"{gesendete_orte!r}"
        )
        assert len(mails) == 1, f"Genau eine Mail erwartet: {len(mails)}"
        # Geprueft wird der BETREFF, nicht der Rumpf: bleibt nach dem Filtern
        # genau EIN Ort uebrig, faellt der Buendel-Renderer per Invariante aus
        # #1041 AC-5 auf den Single-Onset-Pfad zurueck
        # (`output/renderers/alert/project.py`, `location_label=None`) — der
        # Ortsname steht dann ausschliesslich im Betreff. Unabhaengig von
        # dieser Scheibe: ein Ortsvergleich mit nur einem Ort rendert heute
        # schon so.
        subject, _body = mails[0]
        assert "OrtEigenstaendig" in subject, (
            f"Der eigenstaendige Ort fehlt: {subject!r}"
        )
        assert "OrtDuplikat" not in subject, (
            f"Der duplizierte Ort darf nicht mehr in der Mail stehen: {subject!r}"
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
        assert any(
            str(e.get("entity_id", "")).startswith("p-ac12") for e in protokoll
        ), f"Der Protokolleintrag muss das Preset benennen: {protokoll!r}"
    finally:
        _clean_user(uid)


# ══════════════════ AC-15 (Radar-Haelfte) — Mandantentrennung ═══════════════


def test_ac15_radar_registereintrag_von_nutzer_a_wirkt_nicht_auf_nutzer_b():
    """AC-15 (Radar-Haelfte): Zwei Nutzer mit gleicher `preset_id` und
    gleicher `location_id` fuehren ihre Register UNABHAENGIG. A's Eintrag
    unterdrueckt A's Nowcast (Positivkontrolle im selben Test) — B bekommt
    seinen Nowcast trotzdem, ohne Rueckfall auf `"default"`.

    RED heute: die Positivkontrolle (A wird unterdrueckt) schlaegt fehl."""
    uid_a = _uid("ac15-a")
    uid_b = _uid("ac15-b")
    _clean_user(uid_a)
    _clean_user(uid_b)
    try:
        for uid in (uid_a, uid_b):
            save_location(_location("loc-a", "OrtA", LAT_A, LON_A), user_id=uid)
            _write_preset(uid, [_radar_preset("p-ac15", ["loc-a"])])

        # NUR Nutzer A registriert.
        _register_official_style_entry(uid_a, "p-ac15:loc-a", "loc-a", severity="HIGH")

        raus_a = CompareRadarAlertService(
            settings=_settings_email_capable_dummy(), user_id=uid_a,
            radar_service=_radar_service({(LAT_A, LON_A): _wet_frame(8)}),
            mail_sink=lambda subject, body: None,
        ).check_all_compare_presets()
        raus_b = CompareRadarAlertService(
            settings=_settings_email_capable_dummy(), user_id=uid_b,
            radar_service=_radar_service({(LAT_A, LON_A): _wet_frame(8)}),
            mail_sink=lambda subject, body: None,
        ).check_all_compare_presets()

        assert raus_a == 0, (
            "Positivkontrolle: A's eigener Registereintrag MUSS A's Nowcast "
            f"unterdruecken ({raus_a!r})"
        )
        assert raus_b == 1, (
            "Mandantentrennung: A's Registereintrag darf B NICHT betreffen — "
            f"B muss seinen Nowcast bekommen ({raus_b!r})"
        )
        assert _event_identity_keys(uid_b, "p-ac15:loc-a"), (
            "B muss seinen EIGENEN Registereintrag bekommen haben"
        )
    finally:
        _clean_user(uid_a)
        _clean_user(uid_b)


# ═══════════════ AC-17 — Signatur-Regression gegenueber S4b-1 ═══════════════


def _parameter_form(fn) -> list[tuple[str, str, bool]]:
    """(Name, Uebergabeart, hat-Default) je Parameter — vergleichbar ohne von
    der Text-Darstellung der Typannotationen abzuhaengen."""
    return [
        (p.name, p.kind.name, p.default is not inspect.Parameter.empty)
        for p in inspect.signature(fn).parameters.values()
    ]


def test_ac17_signaturen_des_geteilten_bausteins_bleiben_unveraendert():
    """AC-17: Diese Scheibe verdrahtet den bestehenden Baustein nur an zwei
    NEUEN Aufrufstellen — `check_event_identity_gate`, `record_event_identity`
    und `resolve_hazard_class` behalten ihre S4b-1-Signatur unveraendert (kein
    neuer Parameter, keine geaenderte Uebergabeart, kein neuer Default).

    Regressionstest — heute schon gruen; er faellt erst, wenn jemand den
    geteilten Baustein fuer Compare „passend macht" statt ihn zu benutzen."""
    from services.alert_gate import (
        check_event_identity_gate, record_event_identity, resolve_hazard_class,
    )

    assert _parameter_form(check_event_identity_gate) == [
        ("user_id", "KEYWORD_ONLY", False),
        ("entity_id", "KEYWORD_ONLY", False),
        ("hazard_class", "KEYWORD_ONLY", False),
        ("segment_ids", "KEYWORD_ONLY", False),
        ("severity", "KEYWORD_ONLY", False),
        ("now", "KEYWORD_ONLY", False),
        ("point_at", "KEYWORD_ONLY", True),
        ("window_start", "KEYWORD_ONLY", True),
        ("window_end", "KEYWORD_ONLY", True),
        ("cooldown_minutes", "KEYWORD_ONLY", True),
    ], f"check_event_identity_gate: {_parameter_form(check_event_identity_gate)!r}"

    assert _parameter_form(record_event_identity) == [
        ("user_id", "KEYWORD_ONLY", False),
        ("entity_id", "KEYWORD_ONLY", False),
        ("hazard_class", "KEYWORD_ONLY", False),
        ("segment_ids", "KEYWORD_ONLY", False),
        ("severity", "KEYWORD_ONLY", False),
        ("now", "KEYWORD_ONLY", False),
        ("point_at", "KEYWORD_ONLY", True),
        ("window_start", "KEYWORD_ONLY", True),
        ("window_end", "KEYWORD_ONLY", True),
    ], f"record_event_identity: {_parameter_form(record_event_identity)!r}"

    assert _parameter_form(resolve_hazard_class) == [
        ("is_convective", "KEYWORD_ONLY", True),
        ("hazard", "KEYWORD_ONLY", True),
    ], f"resolve_hazard_class: {_parameter_form(resolve_hazard_class)!r}"
