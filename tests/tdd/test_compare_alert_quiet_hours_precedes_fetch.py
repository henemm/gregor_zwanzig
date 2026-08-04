"""TDD RED — Issue #1467 Scheibe S2, Arbeitsgang AG2: Ruhezeiten vor die
Erkennung (Ortsvergleich-Änderungsalarm).

SPEC: docs/specs/modules/rework_1467_s2_aenderungsalarm.md, Abschnitt
"AG2 — Ruhezeiten vor die Erkennung", AC-4/AC-5/AC-6.

Ist-Stand (gemessen, `src/services/compare_alert.py`): `check_all_compare_presets()`
liest Sperrzeit (`:112`, `ThrottleStore.is_throttled("compare_preset", ...)`)
und Tages-Obergrenze (`:118`, `alert_daily_limit.is_allowed(...)`) bereits VOR
dem Wetterabruf. Die Ruhezeit-Prüfung (`DeviationAlertEngine.is_quiet_hours`,
`deviation_alert_engine.py:75-100`) sitzt bislang aber erst INNERHALB der
Engine (`deviation_alert_engine.py:243`), aufgerufen aus `evaluate()`, die
`_evaluate_one_location()` (`compare_alert.py:187-214`) erst NACH dem Fetch
(`:194`) aufruft — die Ruhezeit spart also heute keinen Wetterabruf, obwohl
der Trip-Pfad das schon so macht (`trip_alert.py:205`) und der amtliche
Compare-Pfad ebenfalls (`compare_official_alert.py:105-113`, Vorbild für den
vorzuziehenden Riegel).

AC-4 ist der einzige echte RED-Test dieser Datei: heute wird `fetch()`
während der Ruhezeit trotzdem aufgerufen. AC-5 und AC-6 sichern Verhalten ab,
das schon heute korrekt ist (Regressionsschutz vor UND nach dem AG2-Umbau,
s. Docstrings dort) — sie werden bewusst NICHT künstlich rot gehalten.

Mock-freie Test-Seams analog `test_issue_1170_compare_alert_config.py` und
`test_throttle_store.py`: `_ScriptedWeatherSource`/`_CountingWeatherSource`
sind echte `LocationWeatherSource`-Implementierungen (kein `Mock()`/`patch()`),
liefern feste `PointWeatherData` ohne Netzzugriff und zählen echte
Aufrufe. Presets liegen als echte Dateien unter `data/users/<user_id>/briefings/`
(`tests/helpers/compare_briefings.py`), Zähler-Snapshots kommen aus den
echten `ThrottleStore`-/`alert_daily_limit`-Dateien.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from app.config import Settings
from app.user import SavedLocation

from tests.helpers.compare_briefings import write_compare_briefings

# Pfadregel #1409: Prüfling relativ zur Testdatei auflösen, nie über einen
# festen Hauptrepo-Pfad — sonst würde ein Worktree gegen die unveränderte
# Hauptrepo-Kopie prüfen und faelschlich gruen melden.
DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "users"

VIENNA = ZoneInfo("Europe/Vienna")


# ───────────────────────── Helfer (1:1 aus test_issue_1170 übernommen) ──────

def _clean_user(user_id: str) -> None:
    import shutil

    d = DATA_ROOT / user_id
    if d.exists():
        shutil.rmtree(d)


def _settings_email_capable_dummy() -> Settings:
    """`can_send_email() == True` ohne echten Netzwerkzugriff — für
    `mail_sink`-Captures (kein SMTP-Dial, siehe `notification_service.py:475-489`)."""
    return Settings(
        smtp_host="dummy.invalid", smtp_user="dummy", smtp_pass="dummy",
        mail_to="dummy@example.com",
    )


def _location(loc_id: str, name: str, lat: float, lon: float, elevation_m: int = 1000) -> SavedLocation:
    return SavedLocation(id=loc_id, name=name, lat=lat, lon=lon, elevation_m=elevation_m)


def _point(point_id: str, name: str, lat: float, lon: float, precip_sum_mm: float = 0.0,
           provider: str = "test-scripted"):
    """Echtes `PointWeatherData`-DTO (kein Mock)."""
    from app.models import SegmentWeatherSummary
    from services.point_weather import PointWeatherData

    return PointWeatherData(
        id=point_id, name=name, lat=lat, lon=lon, timeseries=None,
        aggregated=SegmentWeatherSummary(precip_sum_mm=precip_sum_mm),
        fetched_at=datetime.now(timezone.utc), provider=provider,
    )


class _ScriptedWeatherSource:
    """Deterministischer `LocationWeatherSource`-Impl — 1:1 aus
    `test_issue_1169_compare_alert_consumer.py`/`test_issue_1170...`. Kein
    `Mock()`/`patch()`: ein Konfigurations-Seam, der echte `PointWeatherData`
    mit vorab festgelegten Werten liefert, ohne Netz."""

    def __init__(self, values: dict[str, float]) -> None:
        self._values = dict(values)

    def fetch(self, point_id: str, lat: float, lon: float):
        return _point(point_id, point_id, lat, lon, precip_sum_mm=self._values.get(point_id, 0.0))


class _CountingWeatherSource:
    """Zähl-Seam um `_ScriptedWeatherSource` — kein Mock, sondern eine echte
    kleine Klasse, die jeden `fetch()`-Aufruf mitzählt und an die
    Skript-Quelle weiterreicht. Beweist AC-4 (0 Aufrufe während der
    Ruhezeit) direkt über den Aufrufzähler, nicht über Seiteneffekte."""

    def __init__(self, values: dict[str, float]) -> None:
        self._inner = _ScriptedWeatherSource(values)
        self.call_count = 0

    def fetch(self, point_id: str, lat: float, lon: float):
        self.call_count += 1
        return self._inner.fetch(point_id, lat, lon)


def _quiet_window_covering_now() -> tuple[str, str]:
    """Baut ein Ruhezeitfenster (`"HH:MM"`/`"HH:MM"`), das die AKTUELLE
    Ortszeit (Europe/Vienna) garantiert einschließt — unabhängig davon, wann
    der Test läuft. `CompareAlertService` hat KEINEN `now`-Injection-Parameter
    für die Ruhezeit-Prüfung (sie hängt letztlich an der echten Uhr,
    `deviation_alert_engine.py:241` `now = now or datetime.now(timezone.utc)`
    bzw. nach dem AG2-Umbau am direkten Aufruf von `is_quiet_hours`); ein
    ±1h-Fenster um die reale Vienna-Zeit ist der kontrollierte Ersatz dafür,
    den der Auftrag vorsieht ("notfalls über einen kontrollierten Zeitpunkt
    statt der echten Uhr"). `is_quiet_hours()` unterstützt den
    Mitternachts-Wrap (`deviation_alert_engine.py:98-99`), das Fenster ist
    also auch über Tagesgrenzen hinweg korrekt."""
    now_local = datetime.now(timezone.utc).astimezone(VIENNA)
    quiet_from = (now_local - timedelta(hours=1)).strftime("%H:%M")
    quiet_to = (now_local + timedelta(hours=1)).strftime("%H:%M")
    return quiet_from, quiet_to


def _preset_multi(preset_id: str, location_ids: list[str], empfaenger: list[str]) -> dict:
    """Compare-Preset-Dict ohne Ruhezeit-Konfiguration — Kontrollgruppen-
    Fixture (aktiv, muss weiter feuern)."""
    return {
        "id": preset_id,
        "name": preset_id,
        "user_id": "default",
        "location_ids": location_ids,
        # Issue #1467 S2 AG6: `schedule="manual"` gilt seither als "pausiert"
        # und schweigt in allen Alarm-Pfaden. Diese Datei prueft die RUHEZEIT
        # (AG2) — ihre Presets muessen den Stilllegungs-Riegel passieren,
        # brauchen also einen aktiven Zeitplan.
        "schedule": "daily",
        "weekday": 4,
        "profil": "ALLGEMEIN",
        "hour_from": 9,
        "hour_to": 16,
        "empfaenger": empfaenger,
        "letzter_versand": None,
        "top_ort_letzter_versand": None,
        "created_at": "2026-07-09T00:00:00Z",
    }


def _preset_with_quiet_hours(
    preset_id: str, location_ids: list[str], empfaenger: list[str],
    quiet_from: str | None, quiet_to: str | None,
) -> dict:
    """Compare-Preset-Dict mit Ruhezeit-Feldern `alert_quiet_from`/
    `alert_quiet_to` — TOP-LEVEL (nicht unter `display_config`), so wie
    `compare_alert.py::_build_eval_config` sie liest
    (`preset.get("alert_quiet_from")`, `:240-241`). `None` lässt den
    jeweiligen Schlüssel bewusst GANZ WEG (nicht `null`), damit AC-5 den
    fehlenden Schlüssel prüft statt eines gesetzten `None`-Werts."""
    preset = _preset_multi(preset_id, location_ids, empfaenger)
    if quiet_from is not None:
        preset["alert_quiet_from"] = quiet_from
    if quiet_to is not None:
        preset["alert_quiet_to"] = quiet_to
    return preset


def _write_preset_file(user_id: str, presets: list[dict]) -> Path:
    # Issue #1250 S7b Cutover: per-Datei briefings/<id>.json (kind="vergleich").
    return write_compare_briefings(DATA_ROOT / user_id, presets)


# ═══════════════════════════════ AC-4 ════════════════════════════════════════

def test_ac4_quiet_hours_prevent_fetch_and_delivery_two_users():
    """AC-4 (RED heute) GIVEN zwei Compare-Presets zweier verschiedener,
    echter Nutzer — Nutzer A mit aktiver Ruhezeit, die die aktuelle Ortszeit
    einschließt (`_quiet_window_covering_now()`), Nutzer B ohne Ruhezeit
    (Kontrollgruppe, beweist zugleich Mandantentrennung: Nutzer Bs Preset ist
    von Nutzer As Ruhezeit unberührt).

    WHEN `CompareAlertService.check_all_compare_presets()` für beide Nutzer
    läuft (je ein deutlich auslösender Δ-Wert, 28 mm über dem Anker, weit
    über jeder Empfindlichkeitsstufe).

    THEN wird `CompareLocationWeatherSource.fetch()` für Nutzer A KEIN
    einziges Mal aufgerufen (0 Aufrufe) und es erfolgt KEINE Zustellung;
    für Nutzer B (keine Ruhezeit) wird weiterhin normal geholt und
    zugestellt — der Riegel greift nur, wo er soll.

    RED-Grund (heute): die Ruhezeit wird erst INNERHALB von
    `DeviationAlertEngine.evaluate()` geprüft (`deviation_alert_engine.py:243`),
    NACHDEM `_evaluate_one_location()` bereits `self._weather_source.fetch(...)`
    aufgerufen hat (`compare_alert.py:194`) — der Fetch-Zähler für Nutzer A
    steht heute auf 1 statt der geforderten 0. Nach dem AG2-Umbau (Ruhezeit
    VOR dem Preset-Loop-Body geprüft, Muster `compare_official_alert.py:105-113`)
    wird er 0.
    """
    from app.loader import save_location
    from services.compare_alert import CompareAlertService

    uid_quiet = f"tdd-ag2-quiet-{uuid.uuid4().hex[:6]}"
    uid_active = f"tdd-ag2-active-{uuid.uuid4().hex[:6]}"
    preset_id_quiet = f"cp-ag2-quiet-{uuid.uuid4().hex[:6]}"
    preset_id_active = f"cp-ag2-active-{uuid.uuid4().hex[:6]}"
    _clean_user(uid_quiet)
    _clean_user(uid_active)
    try:
        from services.compare_weather_snapshot import CompareWeatherSnapshotService

        # ── Nutzer A: aktive Ruhezeit, deckt die reale Ortszeit ab ──────────
        loc_q = _location("loc-q", "RuhezeitOrt", 47.0, 11.0)
        save_location(loc_q, user_id=uid_quiet)
        quiet_from, quiet_to = _quiet_window_covering_now()
        _write_preset_file(uid_quiet, [
            _preset_with_quiet_hours(
                preset_id_quiet, ["loc-q"], ["gregor-test@henemm.com"],
                quiet_from, quiet_to,
            )
        ])
        CompareWeatherSnapshotService(user_id=uid_quiet).save(
            preset_id_quiet, "loc-q", _point("loc-q", loc_q.name, loc_q.lat, loc_q.lon, precip_sum_mm=2.0)
        )

        settings_quiet = _settings_email_capable_dummy()
        sent_subjects_quiet: list[str] = []
        ws_quiet = _CountingWeatherSource({"loc-q": 30.0})  # Δ=28, weit über jeder Schwelle

        svc_quiet = CompareAlertService(
            settings=settings_quiet, user_id=uid_quiet, weather_source=ws_quiet,
            mail_sink=lambda subject, body: sent_subjects_quiet.append(subject),
        )
        sent_quiet = svc_quiet.check_all_compare_presets()

        assert ws_quiet.call_count == 0, (
            f"fetch() wurde {ws_quiet.call_count}-mal aufgerufen, erwartet 0 — "
            "die Ruhezeit muss den Wetterabruf verhindern, nicht erst die "
            "Zustellung (AC-4)."
        )
        assert sent_quiet == 0, f"Erwartet 0 Zustellungen waehrend der Ruhezeit, erhalten: {sent_quiet}"
        assert sent_subjects_quiet == [], "mail_sink wurde trotz aktiver Ruhezeit aufgerufen (AC-4)"

        # ── Nutzer B: KEINE Ruhezeit, echter zweiter Mandant ────────────────
        loc_a = _location("loc-a", "AktivOrt", 48.0, 12.0)
        save_location(loc_a, user_id=uid_active)
        _write_preset_file(uid_active, [
            _preset_multi(preset_id_active, ["loc-a"], ["gregor-test@henemm.com"])
        ])
        CompareWeatherSnapshotService(user_id=uid_active).save(
            preset_id_active, "loc-a", _point("loc-a", loc_a.name, loc_a.lat, loc_a.lon, precip_sum_mm=2.0)
        )

        settings_active = _settings_email_capable_dummy()
        sent_subjects_active: list[str] = []
        ws_active = _CountingWeatherSource({"loc-a": 30.0})

        svc_active = CompareAlertService(
            settings=settings_active, user_id=uid_active, weather_source=ws_active,
            mail_sink=lambda subject, body: sent_subjects_active.append(subject),
        )
        sent_active = svc_active.check_all_compare_presets()

        assert ws_active.call_count == 1, (
            "Kontrollgruppe (kein Ruhezeit-Preset, anderer Nutzer) muss weiterhin "
            f"fetchen — Nutzer As Ruhezeit darf Nutzer B nicht beeinflussen "
            f"(Mandantentrennung); erhalten: {ws_active.call_count} Aufrufe"
        )
        assert sent_active == 1, f"Erwartet 1 Zustellung fuer den aktiven Nutzer, erhalten: {sent_active}"
        assert len(sent_subjects_active) == 1
    finally:
        _clean_user(uid_quiet)
        _clean_user(uid_active)


# ═══════════════════════════════ AC-5 ════════════════════════════════════════

def test_ac5_half_filled_quiet_window_does_not_permanently_suppress():
    """AC-5 (Regressionsschutz, GRÜN vor UND nach AG2) GIVEN ein Compare-Preset,
    bei dem NUR `alert_quiet_from` gesetzt ist und der Schlüssel
    `alert_quiet_to` ganz FEHLT (R5 aus der Spec: ein halb ausgefülltes Feld
    darf nicht dauerhaft stummschalten).

    WHEN der Lauf zu einer beliebigen (der echten) Uhrzeit erfolgt und ein
    deutlich auslösender Δ-Wert vorliegt.

    THEN wird der Alarm trotzdem ausgelöst und zugestellt — `fetch()` wird
    aufgerufen, `check_all_compare_presets()` liefert `1`.

    Warum das schon HEUTE grün ist: `DeviationAlertEngine.is_quiet_hours()`
    prüft `if not quiet_from or not quiet_to: return False`
    (`deviation_alert_engine.py:91-92`) — ein fehlendes `alert_quiet_to`
    macht das Fenster grundsätzlich unwirksam, unabhängig davon, ob diese
    Prüfung (wie heute) erst in der Engine oder (nach AG2) davor läuft. Dieser
    Test nagelt fest, dass der AG2-Umbau (Vorziehen der Prüfung) daran NICHTS
    ändert — er ist Regressionsschutz, kein RED-Beweis.
    """
    from app.loader import save_location
    from services.compare_alert import CompareAlertService

    uid = f"tdd-ag2-halfquiet-{uuid.uuid4().hex[:6]}"
    preset_id = f"cp-ag2-halfquiet-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    try:
        from services.compare_weather_snapshot import CompareWeatherSnapshotService

        loc = _location("loc-h", "HalbRuhezeitOrt", 47.5, 11.5)
        save_location(loc, user_id=uid)
        _write_preset_file(uid, [
            _preset_with_quiet_hours(
                preset_id, ["loc-h"], ["gregor-test@henemm.com"],
                quiet_from="22:00", quiet_to=None,  # alert_quiet_to fehlt bewusst ganz
            )
        ])
        CompareWeatherSnapshotService(user_id=uid).save(
            preset_id, "loc-h", _point("loc-h", loc.name, loc.lat, loc.lon, precip_sum_mm=2.0)
        )

        settings = _settings_email_capable_dummy()
        sent_subjects: list[str] = []
        ws = _CountingWeatherSource({"loc-h": 30.0})  # Δ=28, weit über jeder Schwelle

        service = CompareAlertService(
            settings=settings, user_id=uid, weather_source=ws,
            mail_sink=lambda subject, body: sent_subjects.append(subject),
        )
        sent = service.check_all_compare_presets()

        assert ws.call_count == 1, (
            f"fetch() wurde {ws.call_count}-mal aufgerufen, erwartet 1 — ein halb "
            "ausgefülltes Ruhezeit-Feld darf den Wetterabruf nicht unterdrücken (AC-5)"
        )
        assert sent == 1, (
            f"Gespeicherte halb ausgefüllte Ruhezeit hat den Alarm faelschlich "
            f"unterdrueckt — erwartet 1 Zustellung, erhalten: {sent} (AC-5, R5)"
        )
        assert len(sent_subjects) == 1
    finally:
        _clean_user(uid)


# ═══════════════════════════════ AC-6 ════════════════════════════════════════

def test_ac6_suppressed_run_leaves_throttle_and_daily_limit_untouched():
    """AC-6 (Regressionsschutz, GRÜN vor UND nach AG2) GIVEN ein Compare-Preset
    mit aktiver Ruhezeit (deckt die reale Ortszeit ab) und einem deutlich
    auslösenden Δ-Wert.

    WHEN der durch die Ruhezeit unterdrückte Lauf beendet ist.

    THEN sind weder der Sperrzeit-Zähler (`ThrottleStore`, Scope
    `compare_preset`) noch die Tages-Obergrenze (`alert_daily_limit`) für
    dieses Preset verändert — beide Zähler-Snapshots vor/nach dem Lauf sind
    exakt gleich.

    Warum das schon HEUTE grün ist: Sperrzeit (`compare_alert.py:112`,
    `ThrottleStore.is_throttled`, ein reiner Lese-Zugriff) und
    Tages-Obergrenze (`:118`, `alert_daily_limit.is_allowed`, ebenfalls nur
    lesend) werden VOR jeder Ruhezeit-Prüfung nur GELESEN — geschrieben wird
    ausschließlich nach erfolgreichem Versand (`:158-159`,
    `self._throttle_store.record(...)` / `alert_daily_limit.increment(...)`).
    Das Vorziehen der Ruhezeit-Prüfung in AG2 verschiebt keine dieser
    Schreiboperationen, es spart nur den dazwischenliegenden Wetterabruf.
    Dieser Test nagelt das als Invariante fest.
    """
    from app.loader import save_location
    from services import alert_daily_limit
    from services.compare_alert import CompareAlertService
    from services.throttle_store import ThrottleStore

    uid = f"tdd-ag2-counters-{uuid.uuid4().hex[:6]}"
    preset_id = f"cp-ag2-counters-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    try:
        from services.compare_weather_snapshot import CompareWeatherSnapshotService

        loc = _location("loc-c", "ZaehlerOrt", 46.5, 10.5)
        save_location(loc, user_id=uid)
        quiet_from, quiet_to = _quiet_window_covering_now()
        _write_preset_file(uid, [
            _preset_with_quiet_hours(
                preset_id, ["loc-c"], ["gregor-test@henemm.com"],
                quiet_from, quiet_to,
            )
        ])
        CompareWeatherSnapshotService(user_id=uid).save(
            preset_id, "loc-c", _point("loc-c", loc.name, loc.lat, loc.lon, precip_sum_mm=2.0)
        )

        now = datetime.now(timezone.utc)
        # Zähler-Snapshot VOR dem Lauf — echte Stores, kein Mock.
        before_last_sent = ThrottleStore(uid).last_sent("compare_preset", preset_id)
        before_daily_count = alert_daily_limit.load(uid, now)

        settings = _settings_email_capable_dummy()
        sent_subjects: list[str] = []
        ws = _CountingWeatherSource({"loc-c": 30.0})  # Δ=28, weit über jeder Schwelle

        service = CompareAlertService(
            settings=settings, user_id=uid, weather_source=ws,
            mail_sink=lambda subject, body: sent_subjects.append(subject),
        )
        sent = service.check_all_compare_presets()

        assert sent == 0, f"Erwartet 0 Zustellungen waehrend der Ruhezeit, erhalten: {sent}"
        assert sent_subjects == []

        # Zähler-Snapshot NACH dem Lauf — frische Store-Instanz, kein
        # In-Memory-Zustand aus dem Lauf selbst.
        after_last_sent = ThrottleStore(uid).last_sent("compare_preset", preset_id)
        after_daily_count = alert_daily_limit.load(uid, now)

        assert after_last_sent == before_last_sent, (
            f"Sperrzeit-Zaehler wurde trotz durch Ruhezeit unterdruecktem Lauf "
            f"veraendert: vorher={before_last_sent!r}, nachher={after_last_sent!r} (AC-6)"
        )
        assert after_daily_count == before_daily_count, (
            f"Tages-Obergrenze wurde trotz durch Ruhezeit unterdruecktem Lauf "
            f"veraendert: vorher={before_daily_count}, nachher={after_daily_count} (AC-6)"
        )
    finally:
        _clean_user(uid)


# ═════════════════════════ Fix-Loop F001 (Adversary) ═════════════════════════
# Der in AG2 eingefuegte Ruhezeit-Riegel (`compare_alert.py::check_all_compare_
# presets`, um Zeile 131) stand ausserhalb jeder Fehlerbehandlung: ein kaputt
# formatierter Ruhezeit-Wert (z.B. "25:00") laesst `time.fromisoformat()`
# (`deviation_alert_engine.py:95-96`) einen `ValueError` werfen, der VOR dem
# AG2-Umbau vom Ort-try/except in `_detect_triggered_locations` (:189-191)
# abgefangen wurde, seither aber den GESAMTEN Lauf abbricht — auch fuer
# weitere, gesunde Presets desselben Nutzers. Fachliche Richtung (vorgegeben):
# ein unbrauchbarer Wert wird wie "keine Ruhezeit gesetzt" behandelt, nicht
# wie ein stummer Schalter.

def test_f001_broken_quiet_value_does_not_abort_other_presets_same_user():
    """F001 (RED vor dem Fix) GIVEN zwei Compare-Presets DESSELBEN Nutzers:
    Preset 1 hat einen kaputt formatierten Ruhezeit-Wert (`alert_quiet_from
    ="25:00"`), Preset 2 ist gesund (keine Ruhezeit) — BEIDE haben einen
    deutlich ausloesenden Δ-Wert.

    WHEN `check_all_compare_presets()` fuer diesen Nutzer laeuft.

    THEN darf der kaputte Wert in Preset 1 NICHT den ganzen Lauf abbrechen —
    Preset 2 MUSS seinen Alarm trotzdem zustellen. Zusaetzlich (fachliche
    Richtung, s. `test_f001_broken_quiet_value_alone_treated_as_no_quiet_hours`):
    ein kaputter Wert gilt als "keine Ruhezeit gesetzt", nicht als stummer
    Schalter — Preset 1 liefert deshalb SELBST auch, macht in Summe 2
    Zustellungen.

    RED-Grund (vor dem Fix): `DeviationAlertEngine.is_quiet_hours()` wirft
    beim Auswerten von Preset 1 einen unabgefangenen `ValueError`, der aus
    `check_all_compare_presets()` (einer einzigen Schleife ueber ALLE
    Presets) nach oben durchschlaegt — Preset 2 wird nie erreicht.
    """
    from app.loader import save_location
    from services.compare_alert import CompareAlertService

    uid = f"tdd-f001-multi-{uuid.uuid4().hex[:6]}"
    preset_id_broken = f"cp-f001-broken-{uuid.uuid4().hex[:6]}"
    preset_id_healthy = f"cp-f001-healthy-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    try:
        from services.compare_weather_snapshot import CompareWeatherSnapshotService

        loc_broken = _location("loc-broken", "KaputtRuhezeitOrt", 47.2, 11.2)
        loc_healthy = _location("loc-healthy", "GesundOrt", 47.3, 11.3)
        save_location(loc_broken, user_id=uid)
        save_location(loc_healthy, user_id=uid)

        _write_preset_file(uid, [
            _preset_with_quiet_hours(
                preset_id_broken, ["loc-broken"], ["gregor-test@henemm.com"],
                quiet_from="25:00", quiet_to="23:00",  # kaputt: Stunde 25 existiert nicht
            ),
            _preset_multi(preset_id_healthy, ["loc-healthy"], ["gregor-test@henemm.com"]),
        ])
        CompareWeatherSnapshotService(user_id=uid).save(
            preset_id_broken, "loc-broken",
            _point("loc-broken", loc_broken.name, loc_broken.lat, loc_broken.lon, precip_sum_mm=2.0),
        )
        CompareWeatherSnapshotService(user_id=uid).save(
            preset_id_healthy, "loc-healthy",
            _point("loc-healthy", loc_healthy.name, loc_healthy.lat, loc_healthy.lon, precip_sum_mm=2.0),
        )

        settings = _settings_email_capable_dummy()
        sent_subjects: list[str] = []
        ws = _CountingWeatherSource({"loc-broken": 30.0, "loc-healthy": 30.0})  # Δ=28 je Ort

        service = CompareAlertService(
            settings=settings, user_id=uid, weather_source=ws,
            mail_sink=lambda subject, body: sent_subjects.append(subject),
        )
        sent = service.check_all_compare_presets()

        assert sent == 2, (
            f"Beide Presets ({preset_id_broken}, {preset_id_healthy}) muessen "
            f"zustellen — der kaputte Ruhezeit-Wert darf weder den Lauf "
            f"abbrechen (Preset {preset_id_healthy}) noch das eigene Preset "
            f"stumm schalten (Preset {preset_id_broken}); erwartet 2 "
            f"Zustellungen, erhalten: {sent} (F001)"
        )
        assert ws.call_count == 2, (
            "fetch() haette fuer BEIDE Orte aufgerufen werden muessen "
            f"— erhalten: {ws.call_count} Aufrufe (F001)"
        )
        assert len(sent_subjects) == 2
    finally:
        _clean_user(uid)


def test_f001_broken_quiet_value_alone_treated_as_no_quiet_hours():
    """F001 (fachliche Richtung) GIVEN ein einzelnes Compare-Preset mit
    kaputt formatiertem Ruhezeit-Wert (`alert_quiet_from="abc"`) und einem
    deutlich ausloesenden Δ-Wert, sonst keine weiteren Presets.

    WHEN `check_all_compare_presets()` laeuft.

    THEN stuerzt der Lauf NICHT ab, `fetch()` wird aufgerufen und der Alarm
    wird zugestellt — ein unbrauchbarer Ruhezeit-Wert gilt als "keine
    Ruhezeit gesetzt" (lieber eine Meldung zu viel als eine verschluckte),
    nicht als stummer Schalter.
    """
    from app.loader import save_location
    from services.compare_alert import CompareAlertService

    uid = f"tdd-f001-solo-{uuid.uuid4().hex[:6]}"
    preset_id = f"cp-f001-solo-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    try:
        from services.compare_weather_snapshot import CompareWeatherSnapshotService

        loc = _location("loc-solo", "SoloKaputtOrt", 47.4, 11.4)
        save_location(loc, user_id=uid)
        _write_preset_file(uid, [
            _preset_with_quiet_hours(
                preset_id, ["loc-solo"], ["gregor-test@henemm.com"],
                quiet_from="abc", quiet_to="23:00",  # kaputt: kein gueltiges HH:MM
            )
        ])
        CompareWeatherSnapshotService(user_id=uid).save(
            preset_id, "loc-solo", _point("loc-solo", loc.name, loc.lat, loc.lon, precip_sum_mm=2.0)
        )

        settings = _settings_email_capable_dummy()
        sent_subjects: list[str] = []
        ws = _CountingWeatherSource({"loc-solo": 30.0})  # Δ=28, weit ueber jeder Schwelle

        service = CompareAlertService(
            settings=settings, user_id=uid, weather_source=ws,
            mail_sink=lambda subject, body: sent_subjects.append(subject),
        )
        sent = service.check_all_compare_presets()

        assert ws.call_count == 1, (
            f"fetch() wurde {ws.call_count}-mal aufgerufen, erwartet 1 — ein "
            "kaputter Ruhezeit-Wert darf den Wetterabruf nicht unterdruecken (F001)"
        )
        assert sent == 1, (
            f"Ein kaputter Ruhezeit-Wert muss wie 'keine Ruhezeit gesetzt' "
            f"behandelt werden — erwartet 1 Zustellung, erhalten: {sent} (F001)"
        )
        assert len(sent_subjects) == 1
    finally:
        _clean_user(uid)


# ═════════════════════════ Fix-Loop F003 (Adversary) ═════════════════════════
# F001 fing nur `except ValueError` ab. `time.fromisoformat()`
# (`deviation_alert_engine.py:95-96`) wirft aber `TypeError`, wenn
# `alert_quiet_from`/`alert_quiet_to` gar kein String ist (z.B. `int` 2200
# aus einer manipulierten `briefings/<id>.json` — weder Go
# `internal/model/compare_preset.go:78-79` noch Python
# `src/app/models.py:947-948` erzwingen zur Laufzeit einen String). Der
# F001-Absturz kam dadurch fuer diese Werte zurueck.

def test_f003_non_string_quiet_value_does_not_abort_other_presets_same_user():
    """F003 (RED vor dem Fix) GIVEN zwei Compare-Presets DESSELBEN Nutzers:
    Preset 1 hat einen NICHT-STRING Ruhezeit-Wert (`alert_quiet_from=2200`,
    ein `int` statt `"22:00"`), Preset 2 ist gesund (keine Ruhezeit) — BEIDE
    haben einen deutlich ausloesenden Δ-Wert.

    WHEN `check_all_compare_presets()` fuer diesen Nutzer laeuft.

    THEN darf der nicht-string Wert in Preset 1 NICHT den ganzen Lauf
    abbrechen — Preset 2 MUSS seinen Alarm trotzdem zustellen. Preset 1
    liefert (analog F001) selbst auch, macht in Summe 2 Zustellungen.

    RED-Grund (vor dem Fix): `except ValueError` faengt den `TypeError` aus
    `time.fromisoformat(2200)` nicht ab — er schlaegt aus
    `check_all_compare_presets()` nach oben durch, Preset 2 wird nie
    erreicht.
    """
    from app.loader import save_location
    from services.compare_alert import CompareAlertService

    uid = f"tdd-f003-multi-{uuid.uuid4().hex[:6]}"
    preset_id_broken = f"cp-f003-broken-{uuid.uuid4().hex[:6]}"
    preset_id_healthy = f"cp-f003-healthy-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    try:
        from services.compare_weather_snapshot import CompareWeatherSnapshotService

        loc_broken = _location("loc-broken3", "NichtStringRuhezeitOrt", 47.6, 11.6)
        loc_healthy = _location("loc-healthy3", "GesundOrt3", 47.7, 11.7)
        save_location(loc_broken, user_id=uid)
        save_location(loc_healthy, user_id=uid)

        preset_broken = _preset_multi(preset_id_broken, ["loc-broken3"], ["gregor-test@henemm.com"])
        preset_broken["alert_quiet_from"] = 2200  # int statt "HH:MM" — TypeError, nicht ValueError
        preset_broken["alert_quiet_to"] = "23:00"

        _write_preset_file(uid, [
            preset_broken,
            _preset_multi(preset_id_healthy, ["loc-healthy3"], ["gregor-test@henemm.com"]),
        ])
        CompareWeatherSnapshotService(user_id=uid).save(
            preset_id_broken, "loc-broken3",
            _point("loc-broken3", loc_broken.name, loc_broken.lat, loc_broken.lon, precip_sum_mm=2.0),
        )
        CompareWeatherSnapshotService(user_id=uid).save(
            preset_id_healthy, "loc-healthy3",
            _point("loc-healthy3", loc_healthy.name, loc_healthy.lat, loc_healthy.lon, precip_sum_mm=2.0),
        )

        settings = _settings_email_capable_dummy()
        sent_subjects: list[str] = []
        ws = _CountingWeatherSource({"loc-broken3": 30.0, "loc-healthy3": 30.0})  # Δ=28 je Ort

        service = CompareAlertService(
            settings=settings, user_id=uid, weather_source=ws,
            mail_sink=lambda subject, body: sent_subjects.append(subject),
        )
        sent = service.check_all_compare_presets()

        assert sent == 2, (
            f"Beide Presets ({preset_id_broken}, {preset_id_healthy}) muessen "
            f"zustellen — ein nicht-string Ruhezeit-Wert darf weder den Lauf "
            f"abbrechen (Preset {preset_id_healthy}) noch das eigene Preset "
            f"stumm schalten (Preset {preset_id_broken}); erwartet 2 "
            f"Zustellungen, erhalten: {sent} (F003)"
        )
        assert ws.call_count == 2, (
            "fetch() haette fuer BEIDE Orte aufgerufen werden muessen "
            f"— erhalten: {ws.call_count} Aufrufe (F003)"
        )
        assert len(sent_subjects) == 2
    finally:
        _clean_user(uid)


def test_f003_broken_quiet_value_logs_warning_with_preset_id_and_exception_type(caplog):
    """F003 Mutation D (Testluecke aus dem Adversary-Protokoll): kein
    bestehender Test prueft, dass bei einem kaputten Ruhezeit-Wert
    ueberhaupt eine Warnung geschrieben wird — entfernt man `logger.warning`
    in `compare_alert.py`, blieben alle Tests bis hierher gruen.

    GIVEN ein Compare-Preset mit nicht-string Ruhezeit-Wert
    (`alert_quiet_from=2200`).

    WHEN `check_all_compare_presets()` laeuft.

    THEN erscheint im Log (Logger "compare_alert", Level WARNING) eine
    Zeile, die sowohl die Preset-Kennung als auch den Ausnahmetyp
    ("TypeError") enthaelt — Beleg dafuer, dass ein echter Programmfehler
    dort auffindbar bliebe und nicht als bloss "kaputter Nutzerwert"
    durchgeht.
    """
    import logging

    from app.loader import save_location
    from services.compare_alert import CompareAlertService

    uid = f"tdd-f003-log-{uuid.uuid4().hex[:6]}"
    preset_id = f"cp-f003-log-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    try:
        from services.compare_weather_snapshot import CompareWeatherSnapshotService

        loc = _location("loc-log3", "LogRuhezeitOrt", 47.8, 11.8)
        save_location(loc, user_id=uid)

        preset = _preset_multi(preset_id, ["loc-log3"], ["gregor-test@henemm.com"])
        preset["alert_quiet_from"] = 2200  # int statt "HH:MM" — TypeError
        preset["alert_quiet_to"] = "23:00"
        _write_preset_file(uid, [preset])
        CompareWeatherSnapshotService(user_id=uid).save(
            preset_id, "loc-log3", _point("loc-log3", loc.name, loc.lat, loc.lon, precip_sum_mm=2.0)
        )

        settings = _settings_email_capable_dummy()
        sent_subjects: list[str] = []
        ws = _CountingWeatherSource({"loc-log3": 30.0})

        service = CompareAlertService(
            settings=settings, user_id=uid, weather_source=ws,
            mail_sink=lambda subject, body: sent_subjects.append(subject),
        )

        with caplog.at_level(logging.WARNING, logger="compare_alert"):
            service.check_all_compare_presets()

        warning_texts = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
        assert any(
            preset_id in text and "TypeError" in text for text in warning_texts
        ), (
            f"Erwartet eine WARNING-Zeile mit Preset-Kennung {preset_id!r} und "
            f"'TypeError' — erhalten: {warning_texts} (F003, Mutation D)"
        )
    finally:
        _clean_user(uid)
