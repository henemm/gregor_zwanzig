"""TDD RED — Issue #1467 Scheibe S2, Arbeitsgang AG6: ein pausierter oder
archivierter Ortsvergleich schweigt in ALLEN Alarm-Pfaden.

SPEC: docs/specs/modules/rework_1467_s2_aenderungsalarm.md, Abschnitt
"AG6 — pausiert/archiviert schweigt", AC-20/AC-20b/AC-21/AC-22/AC-23/AC-28.

Ist-Stand (gemessen):
- `compare_official_alert.py:85-90` prueft `schedule == "manual"` und
  `archived_at` (#1233) — aber NICHT `paused_at`, und die Regel steht dort als
  Inline-Kopie.
- `compare_alert.py::check_all_compare_presets` (Aenderungsalarm) und
  `compare_radar_alert.py::_check_one_preset` (Nowcast) pruefen WEDER
  `paused_at` NOCH `schedule=="manual"` NOCH `archived_at` — sie senden
  weiter, obwohl der Ortsvergleich stillgelegt ist. Genau das ist der belegte
  Produktivfall: der einzige Ortsvergleich-Alarm der Historie ging vier Tage
  NACH dem Pausieren raus.

Verbindliche Vorlage fuer die Stilllegungs-Regel ist die Oberflaechen-Logik
`frontend/src/lib/components/compare/subscriptionHelpers.ts:83-88`
(`deriveStatusFromPreset`): `paused_at` gesetzt ODER `schedule === 'manual'`
ergibt "paused"; `archived_at` kommt aus dem Bestands-Riegel #1233 hinzu.

Kuenftige API (existiert noch NICHT -> ImportError = RED):

    from services.compare_alert_guard import is_silenced   # (preset: dict) -> bool

RED-Gruende je Testgruppe:
- AC-28 Direkttests: `services.compare_alert_guard` existiert nicht -> ImportError.
- AC-20/AC-20b/AC-21/AC-22: die beiden Pfade senden heute trotz Stilllegung
  (bzw. holen sogar Wetterdaten dafuer) -> Zustellzaehler/Abrufzaehler stehen
  auf 1 statt 0.
- AC-28 Verdrahtungstests: das Symbol `is_silenced` ist in den drei
  verbrauchenden Modulen noch nicht importiert; der Patch am VERBRAUCHENDEN
  Modul bleibt deshalb wirkungslos, die gemessene Wirkung weicht ab.
- AC-23 (Gegenprobe) ist bewusst schon HEUTE gruen: aktive Presets senden ja.
  Der Test haelt fest, dass der neue Riegel nicht zu breit greift ("gar nichts
  mehr senden" waere sonst eine bestehende Loesung").

Testpolitik (CLAUDE.md): kein Mock-Theater. Presets/Orte liegen als echte
Dateien unter `data/users/<user_id>/briefings/`, die Wetter-/Radar-/Warn-
Quellen sind echte, zaehlende Konfigurations-Seams (`_CountingWeatherSource`,
`_CoordFrameSource`, `_CountingOfficialAlertSource` — Vorbilder
`test_compare_alert_quiet_hours_precedes_fetch.py`, `test_compare_radar_alert.py`,
`test_compare_official_alert.py`), der Versand laeuft ausschliesslich in
`mail_sink`-Senken. Kein SMTP, kein Telegram, kein IMAP, kein Netz.
`monkeypatch` wird AUSSCHLIESSLICH fuer die Verdrahtungsnachweise (AC-28,
Muster AG1 `test_compare_alert_channels.py`) benutzt und setzt am
VERBRAUCHENDEN Modul an, nie am Definitionsort.

Pfadregel #1409: `DATA_ROOT` wird relativ zur eigenen Testdatei aufgeloest,
nie ueber einen festen Hauptrepo-Pfad.
"""
from __future__ import annotations

import shutil
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from app.config import Settings
from app.user import SavedLocation

from tests.helpers.compare_briefings import write_compare_briefings

DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "users"

PAUSED_AT = "2026-07-30T08:00:00Z"
ARCHIVED_AT = "2026-07-01T00:00:00Z"


# ───────────────────────────── Helfer & Fixturen ────────────────────────────

def _uid(prefix: str) -> str:
    return f"tdd-ag6-{prefix}-{uuid.uuid4().hex[:6]}"


def _clean_user(user_id: str) -> None:
    d = DATA_ROOT / user_id
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)


def _settings_email_capable_dummy() -> Settings:
    """`can_send_email() == True` ohne echten Netzwerkzugriff — der
    `mail_sink`-Zweig ersetzt den SMTP-Versand vollstaendig, die Dummy-Creds
    werden nie gewaehlt (Vorbild `test_compare_alert_quiet_hours_precedes_fetch.py`)."""
    return Settings(
        smtp_host="dummy.invalid", smtp_user="dummy", smtp_pass="dummy",
        mail_to="dummy@example.com",
    )


def _location(loc_id: str, name: str, lat: float, lon: float) -> SavedLocation:
    return SavedLocation(id=loc_id, name=name, lat=lat, lon=lon, elevation_m=1000)


def _point(point_id: str, name: str, lat: float, lon: float, precip_sum_mm: float = 0.0):
    """Echtes `PointWeatherData`-DTO (kein Mock)."""
    from app.models import SegmentWeatherSummary
    from services.point_weather import PointWeatherData

    return PointWeatherData(
        id=point_id, name=name, lat=lat, lon=lon, timeseries=None,
        aggregated=SegmentWeatherSummary(precip_sum_mm=precip_sum_mm),
        fetched_at=datetime.now(timezone.utc), provider="test-scripted",
    )


class _CountingWeatherSource:
    """Echter `LocationWeatherSource`-Impl mit Aufrufzaehler (kein Mock) —
    liefert feste `PointWeatherData` ohne Netz und zaehlt jeden `fetch()`.
    1:1 uebernommen aus `test_compare_alert_quiet_hours_precedes_fetch.py`
    (dort AG2-Nachweis "Riegel vor dem Abruf") — keine zweite Technik."""

    def __init__(self, values: dict[str, float]) -> None:
        self._values = dict(values)
        self.call_count = 0

    def fetch(self, point_id: str, lat: float, lon: float):
        self.call_count += 1
        return _point(point_id, point_id, lat, lon,
                      precip_sum_mm=self._values.get(point_id, 0.0))


class _CoordFrameSource:
    """Echter, aufrufbarer `frame_source`-Seam fuer `RadarNowcastService`
    (`radar_service.py:84-89`) mit Aufrufzaehler — 1:1 aus
    `test_compare_radar_alert.py`."""

    def __init__(self, by_coord: dict[tuple[float, float], list]) -> None:
        self._by_coord = by_coord
        self.call_count = 0

    def __call__(self, lat: float, lon: float) -> list:
        self.call_count += 1
        return self._by_coord.get((round(lat, 4), round(lon, 4)), [])


class _CountingOfficialAlertSource:
    """Echte `OfficialAlertSource` (strukturelles Subtyping, Vorbild
    `test_compare_official_alert.py::_FakeOfficialAlertSource`) OHNE Warnungen
    — sie dient hier nur als Abruf-Zaehler hinter dem Riegel: `fetch_calls`
    bleibt 0, solange das Preset stillgelegt ist, und wird 1, sobald der Lauf
    den Riegel passiert."""

    def __init__(self, lat: float, lon: float) -> None:
        self._lat, self._lon = lat, lon
        self.fetch_calls = 0

    @property
    def name(self) -> str:
        return "test-ag6-source"

    def covers(self, lat, lon) -> bool:
        return abs(lat - self._lat) < 0.05 and abs(lon - self._lon) < 0.05

    def fetch(self, lat, lon):
        self.fetch_calls += 1
        return []


def _preset(
    preset_id: str,
    location_ids: list[str],
    *,
    schedule: str = "daily",
    paused_at: str | None = None,
    archived_at: str | None = None,
    radar_alert_enabled: bool | None = None,
) -> dict:
    """Compare-Preset-Dict. `schedule="daily"` ist der AKTIVE Default (analog
    `test_compare_official_alert.py::_preset` seit #1233). `paused_at`/
    `archived_at` werden nur gesetzt, wenn ausdruecklich uebergeben — ein
    fehlender Schluessel darf nie als "stillgelegt" gelten."""
    preset: dict = {
        "id": preset_id,
        "name": preset_id,
        "user_id": "default",
        "location_ids": location_ids,
        "schedule": schedule,
        "weekday": 4,
        "profil": "ALLGEMEIN",
        "hour_from": 9,
        "hour_to": 16,
        "empfaenger": ["gregor-test@henemm.com"],
        "letzter_versand": None,
        "top_ort_letzter_versand": None,
        "created_at": "2026-07-09T00:00:00Z",
    }
    if paused_at is not None:
        preset["paused_at"] = paused_at
    if archived_at is not None:
        preset["archived_at"] = archived_at
    if radar_alert_enabled is not None:
        preset["radar_alert_enabled"] = radar_alert_enabled
    return preset


def _write_preset_file(user_id: str, presets: list[dict]) -> Path:
    # Issue #1250 S7b Cutover: per-Datei briefings/<id>.json (kind="vergleich").
    return write_compare_briefings(DATA_ROOT / user_id, presets)


def _setup_deviation_case(uid: str, preset: dict) -> _CountingWeatherSource:
    """Legt Ort, Preset und den Anker-Schnappschuss (2.0 mm) auf Platte an und
    liefert die zaehlende Wetterquelle mit einem klar ausloesenden Frischwert
    (30.0 mm -> Δ=28, weit ueber jeder Empfindlichkeitsstufe)."""
    from app.loader import save_location
    from services.compare_weather_snapshot import CompareWeatherSnapshotService

    loc = _location("loc-1", "AG6-Ort", 47.0, 11.0)
    save_location(loc, user_id=uid)
    _write_preset_file(uid, [preset])
    CompareWeatherSnapshotService(user_id=uid).save(
        preset["id"], "loc-1", _point("loc-1", loc.name, loc.lat, loc.lon, precip_sum_mm=2.0)
    )
    return _CountingWeatherSource({"loc-1": 30.0})


def _run_deviation(uid: str, weather_source) -> tuple[int, list[str]]:
    from services.compare_alert import CompareAlertService

    subjects: list[str] = []
    sent = CompareAlertService(
        settings=_settings_email_capable_dummy(), user_id=uid,
        weather_source=weather_source,
        mail_sink=lambda subject, body: subjects.append(subject),
    ).check_all_compare_presets()
    return sent, subjects


def _wet_frame(onset_minutes: int = 8) -> list:
    """Ein einzelner nasser `RadarFrame` in der Zukunft — echtes DTO, Vorbild
    `test_compare_radar_alert.py::_wet_frame`. Onset ≤ 20 Min = Ausloese-Bedingung."""
    from providers.brightsky import RadarFrame

    ts = datetime.now(timezone.utc) + timedelta(minutes=onset_minutes)
    return [RadarFrame(timestamp=ts, precip_mm_h=0.6, is_convective=False)]


def _setup_radar_case(uid: str, preset: dict) -> _CoordFrameSource:
    """Ort + Preset auf Platte, dazu eine Radar-Quelle, die GARANTIERT
    ausloesen wuerde (Onset 8 Min) — bleibt der Zaehler 0, hat der Riegel vor
    dem Abruf gegriffen."""
    from app.loader import save_location

    loc = _location("loc-r", "AG6-Radar-Ort", 46.0207, 7.7491)
    save_location(loc, user_id=uid)
    _write_preset_file(uid, [preset])
    return _CoordFrameSource({(46.0207, 7.7491): _wet_frame(8)})


def _run_radar(uid: str, frame_source) -> tuple[int, list]:
    from services.compare_radar_alert import CompareRadarAlertService
    from services.radar_service import RadarNowcastService

    mail_calls: list = []
    sent = CompareRadarAlertService(
        settings=_settings_email_capable_dummy(), user_id=uid,
        radar_service=RadarNowcastService(frame_source=frame_source),
        mail_sink=lambda subject, body: mail_calls.append((subject, body)),
    ).check_all_compare_presets()
    return sent, mail_calls


# ═════════════════ AC-20 — pausierter Vergleich: kein Aenderungsalarm ════════

def test_ac20_manual_schedule_preset_sends_no_deviation_alert():
    """AC-20 Fall (a) GIVEN ein Ortsvergleich, der NUR ueber
    `schedule="manual"` stillgelegt ist (kein `paused_at`), mit einem klar
    ausloesenden Δ-Wert (2.0 mm Anker -> 30.0 mm frisch).

    WHEN `CompareAlertService.check_all_compare_presets()` laeuft.

    THEN erfolgt keine Zustellung auf keinem Kanal, Rueckgabe 0.

    RED-Grund heute: `compare_alert.py::check_all_compare_presets` liest
    `schedule` ueberhaupt nicht — der Alarm geht raus (Rueckgabe 1, ein
    `mail_sink`-Aufruf).
    """
    uid = _uid("ac20a")
    _clean_user(uid)
    try:
        ws = _setup_deviation_case(uid, _preset("cp-ac20a", ["loc-1"], schedule="manual"))
        sent, subjects = _run_deviation(uid, ws)

        assert sent == 0, (
            f"Stillgelegter Ortsvergleich (schedule='manual') hat {sent} "
            "Aenderungsalarm(e) versendet, erwartet 0 (AC-20a)"
        )
        assert subjects == [], (
            f"mail_sink wurde trotz schedule='manual' aufgerufen: {subjects!r} (AC-20a)"
        )
    finally:
        _clean_user(uid)


def test_ac20_paused_at_alone_sends_no_deviation_alert():
    """AC-20 Fall (b) — DER PRUEFSTEIN. GIVEN ein Ortsvergleich, bei dem NUR
    `paused_at` gesetzt ist, waehrend `schedule` aktiv bleibt (`"daily"`);
    klar ausloesender Δ-Wert.

    WHEN `CompareAlertService.check_all_compare_presets()` laeuft.

    THEN erfolgt keine Zustellung, Rueckgabe 0.

    Warum dieser Fall der Pruefstein ist: Ein Riegel, der nur auf `schedule`
    schaut, faellt hier durch — genau so entstand der belegte Produktivfall
    (Alarm vier Tage nach dem Pausieren). Die Oberflaeche wertet
    `paused_at` als eigenstaendiges, VORRANGIGES Merkmal
    (`subscriptionHelpers.ts:85`), der Alarm-Pfad muss dem folgen.

    RED-Grund heute: `compare_alert.py` kennt weder `paused_at` noch
    `schedule` — der Alarm geht raus.
    """
    uid = _uid("ac20b")
    _clean_user(uid)
    try:
        ws = _setup_deviation_case(
            uid, _preset("cp-ac20b", ["loc-1"], schedule="daily", paused_at=PAUSED_AT)
        )
        sent, subjects = _run_deviation(uid, ws)

        assert sent == 0, (
            f"Pausierter Ortsvergleich (paused_at gesetzt, schedule='daily') hat "
            f"{sent} Aenderungsalarm(e) versendet, erwartet 0 — ein Riegel, der "
            "nur auf `schedule` liest, faellt genau hier durch (AC-20b)"
        )
        assert subjects == [], (
            f"mail_sink wurde trotz gesetztem paused_at aufgerufen: {subjects!r} (AC-20b)"
        )
    finally:
        _clean_user(uid)


def test_ac20_paused_and_manual_sends_no_deviation_alert():
    """AC-20 Fall (c) GIVEN ein Ortsvergleich mit BEIDEN Merkmalen
    (`paused_at` gesetzt UND `schedule="manual"`), klar ausloesender Δ-Wert.

    WHEN `CompareAlertService.check_all_compare_presets()` laeuft.

    THEN keine Zustellung, Rueckgabe 0.

    RED-Grund heute: wie (a)/(b) — der Aenderungsalarm-Pfad wertet keines der
    beiden Merkmale aus.
    """
    uid = _uid("ac20c")
    _clean_user(uid)
    try:
        ws = _setup_deviation_case(
            uid, _preset("cp-ac20c", ["loc-1"], schedule="manual", paused_at=PAUSED_AT)
        )
        sent, subjects = _run_deviation(uid, ws)

        assert sent == 0, (
            f"Ortsvergleich mit paused_at UND schedule='manual' hat {sent} "
            "Aenderungsalarm(e) versendet, erwartet 0 (AC-20c)"
        )
        assert subjects == [], f"mail_sink wurde aufgerufen: {subjects!r} (AC-20c)"
    finally:
        _clean_user(uid)


# ═══════════ AC-20b — kein Wetterabruf fuer ein stillgelegtes Preset ═════════

def test_ac20b_silenced_preset_triggers_no_weather_fetch():
    """AC-20b GIVEN ein pausierter Ortsvergleich (`paused_at` gesetzt,
    `schedule="daily"`) und eine zaehlende Wetterquelle, deren Werte den Alarm
    ausloesen WUERDEN (Δ=28).

    WHEN `CompareAlertService.check_all_compare_presets()` laeuft.

    THEN wird `fetch()` KEIN einziges Mal aufgerufen (Zaehler 0) — der Riegel
    muss VOR der Datenbeschaffung greifen, nicht erst vor dem Versand.
    Ein stillgelegter Ortsvergleich darf weder Kontingent noch Laufzeit kosten.

    Spion-Technik uebernommen aus
    `test_compare_alert_quiet_hours_precedes_fetch.py` (AG2) — dort ist
    derselbe Nachweis fuer die Ruhezeit gebaut, es gibt keine zweite Technik.

    RED-Grund heute: es gibt gar keinen Riegel; `_detect_triggered_locations`
    ruft `fetch()` auf (`compare_alert.py:194`), der Zaehler steht auf 1.
    """
    uid = _uid("ac20fetch")
    _clean_user(uid)
    try:
        ws = _setup_deviation_case(
            uid, _preset("cp-ac20fetch", ["loc-1"], schedule="daily", paused_at=PAUSED_AT)
        )
        sent, subjects = _run_deviation(uid, ws)

        assert ws.call_count == 0, (
            f"fetch() wurde {ws.call_count}-mal fuer einen stillgelegten "
            "Ortsvergleich aufgerufen, erwartet 0 — der Riegel muss VOR der "
            "Datenbeschaffung greifen (AC-20b)"
        )
        assert sent == 0 and subjects == []
    finally:
        _clean_user(uid)


# ═══════════════ AC-21 — pausierter Vergleich: kein Nowcast-Alarm ════════════

def test_ac21_paused_preset_sends_no_nowcast_alert():
    """AC-21 GIVEN ein pausierter Ortsvergleich (`paused_at` gesetzt,
    `schedule="daily"`) mit `radar_alert_enabled: true` und einer
    Radar-Quelle, deren Onset (8 Min) die Ausloese-Bedingung klar erfuellt.

    WHEN `CompareRadarAlertService.check_all_compare_presets()` laeuft.

    THEN erfolgt keine Zustellung, Rueckgabe 0 — und der Nowcast wird gar
    nicht erst geholt (`frame_source`-Zaehler 0, AC-20b-Wirkung im zweiten
    Pfad).

    RED-Grund heute: `compare_radar_alert.py::_check_one_preset` prueft nur
    `radar_alert_enabled` und den Cooldown, kein Stilllegungs-Merkmal — der
    Onset-Alarm geht raus (Rueckgabe 1).
    """
    uid = _uid("ac21")
    _clean_user(uid)
    try:
        fs = _setup_radar_case(uid, _preset(
            "cp-ac21", ["loc-r"], schedule="daily", paused_at=PAUSED_AT,
            radar_alert_enabled=True,
        ))
        sent, mail_calls = _run_radar(uid, fs)

        assert sent == 0, (
            f"Pausierter Ortsvergleich hat {sent} Nowcast-Alarm(e) versendet, "
            "erwartet 0 (AC-21)"
        )
        assert mail_calls == [], f"mail_sink wurde aufgerufen: {mail_calls!r} (AC-21)"
        assert fs.call_count == 0, (
            f"Nowcast wurde {fs.call_count}-mal fuer einen pausierten "
            "Ortsvergleich geholt, erwartet 0 (AC-21/AC-20b)"
        )
    finally:
        _clean_user(uid)


# ════════════ AC-22 — archivierter Vergleich schweigt in BEIDEN Pfaden ═══════

def test_ac22_archived_preset_silent_in_both_paths():
    """AC-22 GIVEN EIN archivierter Ortsvergleich (`archived_at` gesetzt,
    `schedule="daily"`, nicht pausiert) mit `radar_alert_enabled: true` — eine
    Fixture, beide Checker nacheinander.

    WHEN erst `CompareAlertService.check_all_compare_presets()` (Δ=28) und
    danach `CompareRadarAlertService.check_all_compare_presets()` (Onset 8 Min)
    laufen.

    THEN schweigen BEIDE Pfade: je 0 Zustellungen, keine `mail_sink`-Aufrufe,
    und beide Abrufzaehler (Wetter, Nowcast) bleiben auf 0.

    RED-Grund heute: `archived_at` wird nur im amtlichen Pfad ausgewertet
    (`compare_official_alert.py:89-90`, #1233); Aenderungsalarm und Nowcast
    kennen das Feld nicht und senden beide.
    """
    from app.loader import save_location
    from services.compare_weather_snapshot import CompareWeatherSnapshotService

    uid = _uid("ac22")
    _clean_user(uid)
    try:
        preset = _preset(
            "cp-ac22", ["loc-1"], schedule="daily", archived_at=ARCHIVED_AT,
            radar_alert_enabled=True,
        )
        loc = _location("loc-1", "AG6-Archiv-Ort", 46.0207, 7.7491)
        save_location(loc, user_id=uid)
        _write_preset_file(uid, [preset])
        CompareWeatherSnapshotService(user_id=uid).save(
            "cp-ac22", "loc-1", _point("loc-1", loc.name, loc.lat, loc.lon, precip_sum_mm=2.0)
        )

        ws = _CountingWeatherSource({"loc-1": 30.0})
        sent_dev, subjects = _run_deviation(uid, ws)

        fs = _CoordFrameSource({(46.0207, 7.7491): _wet_frame(8)})
        sent_radar, mail_calls = _run_radar(uid, fs)

        assert sent_dev == 0, (
            f"Archivierter Ortsvergleich hat {sent_dev} Aenderungsalarm(e) "
            "versendet, erwartet 0 (AC-22)"
        )
        assert subjects == [], f"Aenderungsalarm-mail_sink aufgerufen: {subjects!r} (AC-22)"
        assert ws.call_count == 0, (
            f"Wetterabruf fuer archivierten Ortsvergleich: {ws.call_count} statt 0 (AC-22)"
        )
        assert sent_radar == 0, (
            f"Archivierter Ortsvergleich hat {sent_radar} Nowcast-Alarm(e) "
            "versendet, erwartet 0 (AC-22)"
        )
        assert mail_calls == [], f"Nowcast-mail_sink aufgerufen: {mail_calls!r} (AC-22)"
        assert fs.call_count == 0, (
            f"Nowcast-Abruf fuer archivierten Ortsvergleich: {fs.call_count} statt 0 (AC-22)"
        )
    finally:
        _clean_user(uid)


# ═══════════════ AC-23 — GEGENPROBE: aktiver Vergleich meldet weiter ═════════

def test_ac23_active_preset_still_sends_deviation_alert():
    """AC-23 (Gegenprobe, heute bereits GRUEN — erwartet) GIVEN ein AKTIVER
    Ortsvergleich: nicht pausiert, nicht archiviert, `schedule="daily"`,
    dieselbe ausloesende Bedingung wie in AC-20 (Δ=28).

    WHEN `CompareAlertService.check_all_compare_presets()` laeuft.

    THEN wird zugestellt (Rueckgabe 1, genau ein `mail_sink`-Aufruf) und der
    Wetterabruf findet statt (Zaehler 1).

    Bedeutung: ohne diesen Test waere "gar nichts mehr senden" eine bestehende
    Loesung fuer AC-20..AC-22. Er beweist, dass der Riegel nicht zu breit
    greift — insbesondere darf ein FEHLENDES `paused_at`/`archived_at` nie als
    stillgelegt gelten.
    """
    uid = _uid("ac23dev")
    _clean_user(uid)
    try:
        ws = _setup_deviation_case(uid, _preset("cp-ac23dev", ["loc-1"], schedule="daily"))
        sent, subjects = _run_deviation(uid, ws)

        assert ws.call_count == 1, (
            f"Aktiver Ortsvergleich muss Wetterdaten holen — fetch()-Aufrufe: "
            f"{ws.call_count}, erwartet 1 (AC-23)"
        )
        assert sent == 1, (
            f"Aktiver Ortsvergleich muss weiter melden — erhalten: {sent} "
            "Zustellungen, erwartet 1. Ein zu breiter Riegel wuerde hier "
            "faelschlich schweigen (AC-23)"
        )
        assert len(subjects) == 1
    finally:
        _clean_user(uid)


def test_ac23_active_preset_still_sends_nowcast_alert():
    """AC-23 (Gegenprobe, zweiter Pfad, heute bereits GRUEN — erwartet) GIVEN
    ein AKTIVER Ortsvergleich mit `radar_alert_enabled: true` und erfuellter
    Onset-Bedingung (8 Min).

    WHEN `CompareRadarAlertService.check_all_compare_presets()` laeuft.

    THEN wird zugestellt (Rueckgabe 1, genau ein `mail_sink`-Aufruf).
    """
    uid = _uid("ac23radar")
    _clean_user(uid)
    try:
        fs = _setup_radar_case(uid, _preset(
            "cp-ac23radar", ["loc-r"], schedule="daily", radar_alert_enabled=True,
        ))
        sent, mail_calls = _run_radar(uid, fs)

        assert sent == 1, (
            f"Aktiver Ortsvergleich muss den Nowcast-Alarm weiter melden — "
            f"erhalten: {sent}, erwartet 1 (AC-23)"
        )
        assert len(mail_calls) == 1
    finally:
        _clean_user(uid)


# ═════════════════════════ Mandantentrennung (zwei Nutzer) ═══════════════════

def test_silenced_preset_of_user_a_does_not_affect_active_preset_of_user_b():
    """Mandantentrennung GIVEN zwei verschiedene, echte Nutzer: Nutzer A hat
    einen pausierten Ortsvergleich (`paused_at`), Nutzer B einen aktiven
    (`schedule="daily"`, kein Stilllegungs-Merkmal) — beide mit demselben
    ausloesenden Δ-Wert.

    WHEN beide Laeufe nacheinander erfolgen (je eigener Service mit echter
    `user_id`, nie `"default"`).

    THEN schweigt A (0 Zustellungen, 0 Wetterabrufe) und B meldet (1
    Zustellung, 1 Abruf) — beide Richtungen in einem Fall: As Stilllegung
    darf B nicht stummschalten, und Bs aktiver Zustand darf A nicht
    reaktivieren.

    RED-Grund heute: A sendet ebenfalls (kein Riegel im Aenderungsalarm).
    """
    uid_a, uid_b = _uid("mandant-a"), _uid("mandant-b")
    _clean_user(uid_a)
    _clean_user(uid_b)
    try:
        assert uid_a != "default" and uid_b != "default" and uid_a != uid_b

        ws_a = _setup_deviation_case(
            uid_a, _preset("cp-mandant-a", ["loc-1"], schedule="daily", paused_at=PAUSED_AT)
        )
        ws_b = _setup_deviation_case(
            uid_b, _preset("cp-mandant-b", ["loc-1"], schedule="daily")
        )

        sent_a, subjects_a = _run_deviation(uid_a, ws_a)
        sent_b, subjects_b = _run_deviation(uid_b, ws_b)

        assert sent_a == 0 and subjects_a == [], (
            f"Pausierter Ortsvergleich von Nutzer {uid_a} hat gesendet: "
            f"sent={sent_a}, subjects={subjects_a!r}"
        )
        assert ws_a.call_count == 0, (
            f"Wetterabruf fuer pausierten Ortsvergleich von {uid_a}: "
            f"{ws_a.call_count} statt 0"
        )
        assert sent_b == 1 and len(subjects_b) == 1, (
            f"Aktiver Ortsvergleich von Nutzer {uid_b} wurde faelschlich "
            f"stummgeschaltet: sent={sent_b}, subjects={subjects_b!r} — Nutzer "
            f"{uid_a}s Stilllegung darf nicht auf {uid_b} durchschlagen"
        )
        assert ws_b.call_count == 1
    finally:
        _clean_user(uid_a)
        _clean_user(uid_b)


# ═══════ AC-28 Teil 1 — die Stilllegungs-Regel als EIN reiner Baustein ═══════

def test_ac28_is_silenced_true_for_each_single_marker():
    """AC-28/1 Jedes der drei Merkmale schaltet EINZELN still (ODER-Verknuepfung,
    Vorlage `subscriptionHelpers.ts:83-88`): nur `paused_at`, nur
    `schedule="manual"`, nur `archived_at`.

    RED-Grund: `services.compare_alert_guard` existiert noch nicht (ImportError).
    """
    from services.compare_alert_guard import is_silenced

    only_paused = {"id": "p", "schedule": "daily", "paused_at": PAUSED_AT}
    only_manual = {"id": "p", "schedule": "manual"}
    only_archived = {"id": "p", "schedule": "daily", "archived_at": ARCHIVED_AT}

    assert is_silenced(only_paused) is True, (
        f"paused_at allein muss stilllegen: {only_paused!r}"
    )
    assert is_silenced(only_manual) is True, (
        f"schedule='manual' allein muss stilllegen: {only_manual!r}"
    )
    assert is_silenced(only_archived) is True, (
        f"archived_at allein muss stilllegen: {only_archived!r}"
    )


def test_ac28_is_silenced_true_for_combinations():
    """AC-28/1 Kombinationen der Merkmale bleiben stillgelegt (kein Merkmal
    hebt ein anderes auf)."""
    from services.compare_alert_guard import is_silenced

    combos = [
        {"id": "p", "schedule": "manual", "paused_at": PAUSED_AT},
        {"id": "p", "schedule": "manual", "archived_at": ARCHIVED_AT},
        {"id": "p", "schedule": "daily", "paused_at": PAUSED_AT, "archived_at": ARCHIVED_AT},
        {"id": "p", "schedule": "manual", "paused_at": PAUSED_AT, "archived_at": ARCHIVED_AT},
    ]
    for preset in combos:
        assert is_silenced(preset) is True, f"Kombination muss stilllegen: {preset!r}"


def test_ac28_is_silenced_false_for_active_preset():
    """AC-28/1 Ein aktives Preset (`schedule="daily"`, keine Stilllegungs-
    Felder) ist NICHT stillgelegt — die Gegenprobe auf Funktionsebene."""
    from services.compare_alert_guard import is_silenced

    active = {"id": "p", "schedule": "daily", "location_ids": ["loc-1"]}
    assert is_silenced(active) is False, f"Aktives Preset darf nicht stilllegen: {active!r}"


def test_ac28_is_silenced_robust_for_empty_none_and_missing_keys():
    """AC-28/1 Robustheit: die Funktion ist rein und darf strukturell nicht
    werfen. Leeres Dict, `paused_at=None`, `paused_at=""` (leerer String zaehlt
    NICHT als pausiert), `archived_at=None`/`""`, fehlende Schluessel — alles
    ergibt `False`, weil kein Merkmal tatsaechlich gesetzt ist.

    Warum der leere String wichtig ist: ein leeres Feld aus einem
    Formular-Roundtrip wuerde bei einer naiven `"paused_at" in preset`-Pruefung
    einen aktiven Ortsvergleich dauerhaft stummschalten."""
    from services.compare_alert_guard import is_silenced

    harmless = [
        {},
        {"id": "p"},
        {"id": "p", "paused_at": None},
        {"id": "p", "paused_at": ""},
        {"id": "p", "archived_at": None},
        {"id": "p", "archived_at": ""},
        {"id": "p", "schedule": None},
        {"id": "p", "schedule": "", "paused_at": "", "archived_at": ""},
        {"id": "p", "schedule": "weekly"},
    ]
    for preset in harmless:
        assert is_silenced(preset) is False, (
            f"Kein gesetztes Stilllegungs-Merkmal -> False erwartet: {preset!r}"
        )


# ═══════ AC-28 Teil 2 — Verdrahtung: jeder Aufrufer nutzt DIESE Regel ════════

def test_ac28_compare_alert_delegates_to_shared_is_silenced(monkeypatch):
    """AC-28/2 Verdrahtungsnachweis `compare_alert.py` (Muster AG1,
    `test_compare_alert_channels.py`): das Symbol `is_silenced` wird im
    VERBRAUCHENDEN Modul (`services.compare_alert`) durch eine Fassung ersetzt,
    die IMMER `True` liefert. Ein AKTIVES Preset (das ohne Patch senden wuerde)
    muss dadurch schweigen — sonst laeuft die Entscheidung nicht ueber den
    geteilten Baustein.

    Baut diese Stelle spaeter wieder eigene Logik, wird der Test rot.

    RED-Grund heute: `compare_alert` importiert kein `is_silenced`; der Patch
    bleibt wirkungslos und der Alarm geht raus (sent=1 statt 0).
    """
    import services.compare_alert as ca

    monkeypatch.setattr(ca, "is_silenced", lambda preset: True)

    uid = _uid("ac28-ca")
    _clean_user(uid)
    try:
        ws = _setup_deviation_case(uid, _preset("cp-ac28-ca", ["loc-1"], schedule="daily"))
        sent, subjects = _run_deviation(uid, ws)

        assert sent == 0, (
            f"compare_alert muss ueber das importierte Symbol `is_silenced` "
            f"entscheiden — mit einer immer-True-Fassung darf nichts rausgehen, "
            f"erhalten: sent={sent} (AC-28)"
        )
        assert subjects == []
        assert ws.call_count == 0, (
            f"Der Riegel muss vor dem Wetterabruf sitzen — fetch()-Aufrufe: "
            f"{ws.call_count}, erwartet 0 (AC-28/AC-20b)"
        )
    finally:
        _clean_user(uid)


def test_ac28_compare_radar_alert_delegates_to_shared_is_silenced(monkeypatch):
    """AC-28/2 Verdrahtungsnachweis `compare_radar_alert.py` — gleiches Muster:
    `is_silenced` im verbrauchenden Modul auf immer-`True` gesetzt, ein
    aktives Preset mit ausloesendem Onset muss schweigen.

    RED-Grund heute: `compare_radar_alert` importiert kein `is_silenced`; der
    Nowcast-Alarm geht raus (sent=1 statt 0).
    """
    import services.compare_radar_alert as cra

    monkeypatch.setattr(cra, "is_silenced", lambda preset: True)

    uid = _uid("ac28-cra")
    _clean_user(uid)
    try:
        fs = _setup_radar_case(uid, _preset(
            "cp-ac28-cra", ["loc-r"], schedule="daily", radar_alert_enabled=True,
        ))
        sent, mail_calls = _run_radar(uid, fs)

        assert sent == 0, (
            f"compare_radar_alert muss ueber das importierte Symbol "
            f"`is_silenced` entscheiden — erhalten: sent={sent}, erwartet 0 (AC-28)"
        )
        assert mail_calls == []
        assert fs.call_count == 0, (
            f"Der Riegel muss vor dem Nowcast-Abruf sitzen — Abrufe: "
            f"{fs.call_count}, erwartet 0 (AC-28/AC-20b)"
        )
    finally:
        _clean_user(uid)


def test_ac28_compare_official_alert_delegates_to_shared_is_silenced(monkeypatch):
    """AC-28/2 Verdrahtungsnachweis `compare_official_alert.py`: `is_silenced`
    im verbrauchenden Modul auf immer-`True` gesetzt -> ein AKTIVES Preset
    darf die registrierte amtliche Quelle nicht mehr abfragen
    (`fetch_calls == 0`).

    Der Abrufzaehler ist hier der praezisere Nachweis als der Sendezaehler:
    die Quelle liefert bewusst KEINE Warnungen, es wuerde also ohnehin nichts
    versendet — nur der Abruf zeigt, ob der Lauf den Riegel passiert hat.

    RED-Grund heute: `compare_official_alert` hat die Regel als Inline-Kopie
    (`:85-90`) und importiert kein `is_silenced` — der Patch bleibt
    wirkungslos, die Quelle wird abgefragt (fetch_calls=1 statt 0).
    """
    import services.compare_official_alert as coa
    import services.official_alerts.base as base
    from app.loader import save_location
    from services.official_alerts import register_official_alert_source

    monkeypatch.setattr(coa, "is_silenced", lambda preset: True)

    uid = _uid("ac28-coa")
    _clean_user(uid)
    backup = list(base._REGISTERED_SOURCES)
    base._REGISTERED_SOURCES.clear()
    try:
        lat, lon = 46.62, 13.68
        save_location(_location("loc-o", "AG6-Amtlich", lat, lon), user_id=uid)
        _write_preset_file(uid, [_preset("cp-ac28-coa", ["loc-o"], schedule="daily")])
        source = _CountingOfficialAlertSource(lat, lon)
        register_official_alert_source(source)

        mail_calls: list = []
        sent = coa.CompareOfficialAlertService(
            settings=_settings_email_capable_dummy(), user_id=uid,
            mail_sink=lambda subject, body: mail_calls.append(body),
        ).check_all_compare_presets()

        assert source.fetch_calls == 0, (
            f"compare_official_alert muss ueber das importierte Symbol "
            f"`is_silenced` entscheiden — mit einer immer-True-Fassung darf die "
            f"amtliche Quelle nicht abgefragt werden, erhalten: "
            f"{source.fetch_calls} Abrufe (AC-28)"
        )
        assert sent == 0 and mail_calls == []
    finally:
        base._REGISTERED_SOURCES.clear()
        base._REGISTERED_SOURCES.extend(backup)
        _clean_user(uid)


def test_ac28_compare_official_alert_keeps_no_own_silencing_copy(monkeypatch):
    """AC-28/2 Gegenrichtung — der eigentliche "genau EINMAL"-Beweis fuer den
    amtlichen Pfad. `is_silenced` wird im verbrauchenden Modul auf immer-`False`
    gesetzt und ein Preset uebergeben, das nach heutiger INLINE-Logik
    (`compare_official_alert.py:85-90`) blockiert wuerde:
    `schedule="manual"` UND `archived_at` gesetzt.

    Bleibt irgendwo eine zweite Fassung der Regel stehen, blockt sie weiterhin
    und die amtliche Quelle wird nie abgefragt. Existiert die Regel nur noch
    EINMAL (im geteilten Baustein), passiert der Lauf den Riegel und fragt die
    Quelle ab (`fetch_calls == 1`).

    RED-Grund heute: die Inline-Kopie blockiert -> `fetch_calls == 0`.
    """
    import services.compare_official_alert as coa
    import services.official_alerts.base as base
    from app.loader import save_location
    from services.official_alerts import register_official_alert_source

    monkeypatch.setattr(coa, "is_silenced", lambda preset: False)

    uid = _uid("ac28-coa-once")
    _clean_user(uid)
    backup = list(base._REGISTERED_SOURCES)
    base._REGISTERED_SOURCES.clear()
    try:
        lat, lon = 46.62, 13.68
        save_location(_location("loc-o", "AG6-Amtlich-Once", lat, lon), user_id=uid)
        _write_preset_file(uid, [_preset(
            "cp-ac28-once", ["loc-o"], schedule="manual", archived_at=ARCHIVED_AT,
        )])
        source = _CountingOfficialAlertSource(lat, lon)
        register_official_alert_source(source)

        coa.CompareOfficialAlertService(
            settings=_settings_email_capable_dummy(), user_id=uid,
            mail_sink=lambda subject, body: None,
        ).check_all_compare_presets()

        assert source.fetch_calls == 1, (
            "Die Stilllegungs-Regel darf NUR im geteilten Baustein stehen: mit "
            "einer immer-False-Fassung muss der Lauf den Riegel passieren und "
            f"die Quelle abfragen — erhalten: {source.fetch_calls} Abrufe. 0 "
            "bedeutet, dass `compare_official_alert.py` weiterhin eine eigene "
            "Kopie der Regel besitzt (AC-28)"
        )
    finally:
        base._REGISTERED_SOURCES.clear()
        base._REGISTERED_SOURCES.extend(backup)
        _clean_user(uid)


# ═══ AG6-Nebenwirkung im BRIEFING-Weg (Adversary F001, Runde 1) ══════════════
#
# `compare_slot_scheduler.py::presets_due_for_hour` ruft seit AG6 denselben
# geteilten Riegel. Damit ist `paused_at` DORT neu: ein pausiertes Preset mit
# aktivem Zeitplan bekommt jetzt auch kein regulaeres Ortsvergleich-Briefing
# mehr. Der Adversary hat genau diesen Anteil gezielt neutralisiert
# (`is_silenced({**preset, "paused_at": None})`) — alle 42 einschlaegigen Tests
# blieben gruen. Die Tests hier schliessen diese Luecke: die Wirkung wird an
# der Stelle geprueft, an der sie WIRKT, nicht nur dort, wo der Code steht.
# Fixtur-Vorbild: `test_compare_preset_slot_dispatch.py::_preset`.
#
# Nachtrag Runde 3 (Adversary-Fund F003): `presets_due_for_hour` prueft Morgen-
# und Abend-Slot UNABHAENGIG voneinander (KL-5 — beide koennen in derselben
# Stunde faellig sein). Ein Testpaar, das nur den Morgen-Slot verdrahtet, laesst
# eine Verfaelschung durch, die den Riegel ausschliesslich im Abend-Zweig
# neutralisiert. Deshalb ist der Slot an der Fixture WAEHLBAR (eine Fixture,
# ein Parameter — keine halb kopierte Zweitfassung) und beide Slots haben ihr
# eigenes Paar aus Nachweis und Gegenprobe.

BRIEFING_TODAY = date(2026, 8, 4)

#: Slot-Name -> (Slot-Stunde, Zieldatum-Versatz in Tagen). Der Morgen-Slot
#: zielt auf HEUTE, der Abend-Slot auf MORGEN (`compare_slot_scheduler.py`
#: `:101-104`).
BRIEFING_SLOTS = {"morning": (7, 0), "evening": (18, 1)}


def _briefing_preset(
    preset_id: str, *, slot: str = "morning", paused_at: str | None = None
) -> dict:
    """Preset-Dict fuer die Briefing-Faelligkeit: aktiver Zeitplan
    (`schedule="daily"`), nicht archiviert, `end_date` 30 Tage in der ZUKUNFT
    und GENAU EIN aktiver Slot — Morgen um 07:00 oder Abend um 18:00, gesteuert
    ueber `slot`. Damit ist jeder ANDERE Guard aus `presets_due_for_hour`
    (end_date, archived_at, schedule, Slot-Stunde) nachweislich erfuellt —
    faellt das Preset trotzdem raus, kann es nur an `paused_at` liegen.

    Der jeweils andere Slot ist bewusst AUS: so faellt eine Verfaelschung, die
    nur einen der beiden Zweige betrifft, im zugehoerigen Testpaar auf und kann
    nicht vom anderen Zweig verdeckt werden (F003)."""
    if slot not in BRIEFING_SLOTS:
        raise ValueError(f"unbekannter Slot: {slot!r}")
    preset: dict = {
        "id": preset_id,
        "name": preset_id,
        "schedule": "daily",
        "weekday": None,
        "hour_from": 9,
        "hour_to": 16,
        "location_ids": ["ort-a", "ort-b"],
        "empfaenger": ["gregor-test@henemm.com"],
        "archived_at": None,
        "letzter_versand": None,
        "end_date": (BRIEFING_TODAY + timedelta(days=30)).isoformat(),
        "morning_enabled": slot == "morning",
        "morning_time": "07:00:00",
        "evening_enabled": slot == "evening",
        "evening_time": "18:00:00",
    }
    if paused_at is not None:
        preset["paused_at"] = paused_at
    return preset


def test_paused_preset_is_not_due_for_regular_compare_briefing():
    """F001 GIVEN ein Ortsvergleich, bei dem NUR `paused_at` gesetzt ist —
    Zeitplan aktiv (`schedule="daily"`), nicht archiviert, `end_date` 30 Tage
    in der Zukunft, Morgen-Slot 07:00 aktiv.

    WHEN `presets_due_for_hour(..., hour=7, today=...)` fuer genau diese
    Stunde laeuft.

    THEN ist das Preset NICHT faellig — ein pausierter Ortsvergleich bekommt
    auch kein regulaeres Briefing, nicht nur keine Alarme.

    Warum die Fixture so gebaut ist: jeder andere Guard der Funktion ist
    bewusst erfuellt (end_date gueltig, kein `archived_at`, `schedule` aktiv,
    Slot-Stunde trifft). Ein leeres Ergebnis kann deshalb NUR aus `paused_at`
    kommen — sonst waere der Test auch ohne die AG6-Wirkung gruen.
    """
    from services.compare_slot_scheduler import presets_due_for_hour

    paused = _briefing_preset("cp-briefing-paused", paused_at=PAUSED_AT)

    due = presets_due_for_hour([paused], hour=7, today=BRIEFING_TODAY)

    assert due == [], (
        "Pausierter Ortsvergleich (paused_at gesetzt, schedule='daily', "
        f"end_date in der Zukunft, Morgen-Slot) ist faellig gemeldet worden: "
        f"{due!r} — erwartet [] (F001)"
    )


def test_active_preset_with_same_fixture_is_due_for_regular_compare_briefing():
    """F001 GEGENPROBE — dieselbe Fixture OHNE `paused_at`.

    GIVEN denselben Ortsvergleich, nur ohne gesetztes `paused_at`.
    WHEN `presets_due_for_hour(..., hour=7, today=...)` laeuft.
    THEN ist er faellig mit Zieldatum heute.

    Ohne diese Gegenprobe waere „nie faellig" eine bestehende Loesung fuer den
    Test darueber; erst das Paar beweist, dass genau `paused_at` den
    Unterschied macht.
    """
    from services.compare_slot_scheduler import presets_due_for_hour

    active = _briefing_preset("cp-briefing-active")

    due = presets_due_for_hour([active], hour=7, today=BRIEFING_TODAY)

    assert due == [(active, BRIEFING_TODAY)], (
        "Aktiver Ortsvergleich (identische Fixture, nur ohne paused_at) muss "
        f"sein regulaeres Briefing bekommen — erhalten: {due!r}, erwartet "
        f"[(preset, {BRIEFING_TODAY})]. Ein zu breiter Riegel wuerde hier "
        "faelschlich schweigen (F001)"
    )


def test_paused_preset_is_not_due_for_evening_compare_briefing():
    """F003 (Runde 3) GIVEN denselben pausierten Ortsvergleich wie oben, nur
    mit AKTIVEM ABEND-SLOT (18:00) statt Morgen-Slot — `paused_at` gesetzt,
    `schedule="daily"`, nicht archiviert, `end_date` 30 Tage in der Zukunft.

    WHEN `presets_due_for_hour(..., hour=18, today=...)` laeuft.

    THEN ist das Preset NICHT faellig.

    Warum dieser Test noetig ist: `presets_due_for_hour` entscheidet fuer
    Morgen- und Abend-Slot in ZWEI getrennten Zweigen (`:101-104`). Der
    Morgen-Nachweis oben deckt den Abend-Zweig NICHT ab — eine Verfaelschung,
    die den Riegel ausschliesslich dort neutralisiert, rutschte durch alle 44
    Tests des Bestands. Geprueft wird die Zusicherung damit an BEIDEN Stellen,
    an denen sie wirkt.
    """
    from services.compare_slot_scheduler import presets_due_for_hour

    paused = _briefing_preset(
        "cp-briefing-evening-paused", slot="evening", paused_at=PAUSED_AT
    )

    due = presets_due_for_hour([paused], hour=18, today=BRIEFING_TODAY)

    assert due == [], (
        "Pausierter Ortsvergleich (paused_at gesetzt, schedule='daily', "
        f"end_date in der Zukunft, ABEND-Slot 18:00) ist faellig gemeldet "
        f"worden: {due!r} — erwartet []. Der Riegel muss auch im Abend-Zweig "
        "greifen, nicht nur im Morgen-Zweig (F003)"
    )


def test_active_preset_is_due_for_evening_compare_briefing():
    """F003 GEGENPROBE zum Abend-Slot — dieselbe Fixture OHNE `paused_at`.

    GIVEN denselben Ortsvergleich mit aktivem Abend-Slot, nur ohne gesetztes
    `paused_at`.
    WHEN `presets_due_for_hour(..., hour=18, today=...)` laeuft.
    THEN ist er faellig, Zieldatum MORGEN (der Abend-Slot briefed den Folgetag).

    Ohne diese Gegenprobe waere „der Abend-Slot ist nie faellig" eine
    bestehende Loesung fuer den Test darueber.
    """
    from services.compare_slot_scheduler import presets_due_for_hour

    active = _briefing_preset("cp-briefing-evening-active", slot="evening")

    due = presets_due_for_hour([active], hour=18, today=BRIEFING_TODAY)

    expected_date = BRIEFING_TODAY + timedelta(days=1)
    assert due == [(active, expected_date)], (
        "Aktiver Ortsvergleich mit Abend-Slot (identische Fixture, nur ohne "
        f"paused_at) muss sein regulaeres Briefing bekommen — erhalten: {due!r}, "
        f"erwartet [(preset, {expected_date})]. Ein zu breiter Riegel wuerde "
        "hier faelschlich schweigen (F003)"
    )
