"""TDD RED — #2124: Lauf-Lock fuer den Ortsvergleich-Versand (Paritaet zu #1756).

Spec: docs/specs/modules/fix_2124_versand_nginx_timeout.md (AC-5, AC-8)
Vorbild: tests/tdd/test_send_idempotenz_lock.py (#1756)

Zielverhalten (vom Developer exakt so umzusetzen):
- Neues Modul `services.send_lock` mit `try_acquire_send_lock(*key_parts) -> bool`
  und `release_send_lock(*key_parts) -> None` (modulweites Register + Guard).
- `services.trip_report_scheduler._try_acquire_send_lock(user_id, trip_id,
  report_type)` / `_release_send_lock(...)` bleiben als duenne Huellen und
  delegieren an `send_lock` mit dem UNVERAENDERTEN Schluessel
  `(user_id, trip_id, report_type)`.
- `services.scheduler_dispatch_service.send_compare_preset(user_id, preset_id)`
  klammert den Versand mit dem Schluessel `("compare", user_id, preset_id)`
  (wie in Spec §3 woertlich genannt), Freigabe in `finally`. Kollision ->
  Rueckgabe `{"status": "already_in_progress"}` OHNE Versand.
- `api.routers.scheduler.manual_send_compare_preset` mappt diesen Outcome auf
  HTTP 409 mit nicht-leerem `detail`, das "läuft bereits" enthaelt.

Test-Politik: Kern-Schicht, kein Netz. Ersetzt wird ausschliesslich die Naht
zum Netz (`send_one_compare_preset`, modulglobal in
`services.scheduler_dispatch_service` aufgerufen) durch eine ECHTE Funktion,
die Aufrufe mitschreibt und — nur fuer den designierten ersten Aufruf — auf
einem echten `threading.Event` blockiert. Kein `sleep`-Raten: der erste
Aufruf meldet per Event, dass er die Naht betreten hat (und damit — nach dem
Fix — den Lock haelt), bevor der zweite Aufruf startet.

`services.send_lock` wird NICHT auf Modulebene importiert (existiert heute
nicht) — nur innerhalb der Tests, die den geteilten Helfer belegen.

RED heute: kein Lock um `send_compare_preset` -> der zweite Aufruf betritt
die Naht ein zweites Mal (Doppelversand), `services.send_lock` existiert nicht.
"""
from __future__ import annotations

import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from app.loader import get_data_root  # noqa: E402
from tests.helpers.compare_briefings import write_compare_briefings  # noqa: E402

DISPATCH = "services.scheduler_dispatch_service"


# ---------------------------------------------------------------------------
# Aufbau-Helfer
# ---------------------------------------------------------------------------


def _schreibe_preset(user_id: str, preset_id: str) -> None:
    """Echtes Preset im (per conftest isolierten) Daten-Root des Nutzers."""
    user_dir = Path(get_data_root()) / "users" / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    write_compare_briefings(user_dir, [{
        "id": preset_id,
        "name": f"Vergleich {preset_id}",
        "user_id": user_id,
        "location_ids": ["loc-a", "loc-b"],
        "schedule": "manual",
        "profil": "SUMMER_TREKKING",
        "hour_from": 9,
        "hour_to": 16,
        "empfaenger": ["urlauber@example.com"],
        "created_at": "2026-01-01T00:00:00Z",
    }])


class _Versandnaht:
    """Echter Ersatz der Netz-Naht `send_one_compare_preset`.

    Schreibt jeden Aufruf als `(user_id, preset_id)` mit. Nur der ERSTE
    Aufruf fuer `blockiere_user` betritt die Barriere: er setzt `betreten`
    und wartet auf `weiter`. Optional wirft dieser erste Aufruf danach
    `ausnahme`. Alle uebrigen Aufrufe kehren sofort zurueck — so haengt der
    heutige (lock-lose) zweite Aufruf nicht, sondern faellt schnell auf.
    """

    def __init__(self, blockiere_user: str | None = None,
                 ausnahme: BaseException | None = None) -> None:
        self.aufrufe: list[tuple[str, str]] = []
        self.betreten = threading.Event()
        self.weiter = threading.Event()
        self._blockiere_user = blockiere_user
        self._ausnahme = ausnahme
        self._blockiert_schon = False
        self._guard = threading.Lock()

    def __call__(self, preset, settings, user_id, data_root, **kwargs):
        with self._guard:
            self.aufrufe.append((user_id, preset["id"]))
            blockieren = (user_id == self._blockiere_user and not self._blockiert_schon)
            if blockieren:
                self._blockiert_schon = True
        if blockieren:
            self.betreten.set()
            self.weiter.wait(timeout=5)
            if self._ausnahme is not None:
                raise self._ausnahme
        return ("Zermatt", ["urlauber@example.com"])


def _naht_einsetzen(monkeypatch, naht: _Versandnaht) -> None:
    monkeypatch.setattr(f"{DISPATCH}.send_one_compare_preset", naht)


def _starte_ersten_versand(user_id: str, preset_id: str, naht: _Versandnaht,
                           ergebnisse: list, fehler: list) -> threading.Thread:
    from services.scheduler_dispatch_service import send_compare_preset

    def _lauf() -> None:
        try:
            ergebnisse.append(send_compare_preset(user_id, preset_id))
        except BaseException as exc:  # noqa: BLE001 — Test sammelt jede Ausnahme
            fehler.append(exc)

    thread = threading.Thread(target=_lauf)
    thread.start()
    assert naht.betreten.wait(timeout=5), "Erster Versand hat die Netz-Naht nicht betreten"
    return thread


# ---------------------------------------------------------------------------
# AC-5 — zweiter gleichzeitiger Compare-Versand wird abgewiesen (Service)
# ---------------------------------------------------------------------------


def test_ac5_zweiter_gleichzeitiger_compare_versand_liefert_already_in_progress(monkeypatch):
    """Given ein Ortsvergleich-Versand fuer Nutzer X und Preset P laeuft /
    When ein zweiter `send_compare_preset(X, P)` eintrifft / Then liefert er
    `{"status": "already_in_progress"}` und die Versand-Naht wird nur EINMAL
    betreten (kein Doppelversand). RED: heute laeuft der zweite durch."""
    from services.scheduler_dispatch_service import send_compare_preset

    user_id, preset_id = "cmp-lock-ac5-svc", "cp-2124-a"
    _schreibe_preset(user_id, preset_id)
    naht = _Versandnaht(blockiere_user=user_id)
    _naht_einsetzen(monkeypatch, naht)

    ergebnisse: list = []
    fehler: list = []
    thread = _starte_ersten_versand(user_id, preset_id, naht, ergebnisse, fehler)
    try:
        zweiter = send_compare_preset(user_id, preset_id)
    finally:
        naht.weiter.set()
        thread.join(timeout=5)

    assert not fehler, f"Erster Versand darf nicht scheitern: {fehler}"
    assert zweiter.get("status") == "already_in_progress", (
        f"Erwartet status 'already_in_progress' waehrend ein Versand fuer denselben "
        f"Nutzer+Preset laeuft, bekommen {zweiter!r}"
    )
    assert ergebnisse and ergebnisse[0].get("status") == "ok", (
        f"Erster Versand muss unveraendert durchlaufen: {ergebnisse}"
    )
    assert naht.aufrufe == [(user_id, preset_id)], (
        f"Versand-Naht darf nur EINMAL betreten werden (Zaehler == 1): {naht.aufrufe}"
    )


# ---------------------------------------------------------------------------
# AC-5 — Router mappt die Kollision auf HTTP 409 (echter ASGI-Aufruf)
# ---------------------------------------------------------------------------


def test_ac5_router_liefert_409_waehrend_compare_versand_laeuft(monkeypatch):
    """Given ein Ortsvergleich-Versand fuer X/P laeuft (Service im Thread) /
    When `POST /api/scheduler/compare-presets/P/send?user_id=X` eintrifft /
    Then antwortet der Python-Core mit 409 und sprechendem `detail`, ohne einen
    zweiten Versand auszuloesen. RED: heute 200 und zweiter Versand."""
    from fastapi.testclient import TestClient
    from api.main import app

    user_id, preset_id = "cmp-lock-ac5-router", "cp-2124-b"
    _schreibe_preset(user_id, preset_id)
    naht = _Versandnaht(blockiere_user=user_id)
    _naht_einsetzen(monkeypatch, naht)

    ergebnisse: list = []
    fehler: list = []
    thread = _starte_ersten_versand(user_id, preset_id, naht, ergebnisse, fehler)
    try:
        resp = TestClient(app).post(
            f"/api/scheduler/compare-presets/{preset_id}/send",
            params={"user_id": user_id},
        )
    finally:
        naht.weiter.set()
        thread.join(timeout=5)

    assert resp.status_code == 409, (
        f"Erwartet 409 waehrend ein Compare-Versand fuer denselben Nutzer+Preset "
        f"laeuft, bekommen {resp.status_code}. Body: {resp.text}"
    )
    detail = resp.json().get("detail")
    assert isinstance(detail, str) and "läuft bereits" in detail, (
        f"409-detail muss sprechend sein ('läuft bereits'), bekommen {detail!r}"
    )
    assert naht.aufrufe == [(user_id, preset_id)], (
        f"Der abgewiesene Router-Aufruf darf die Versand-Naht nicht betreten: {naht.aufrufe}"
    )


# ---------------------------------------------------------------------------
# AC-5 — Lock nach Exception wieder frei (finally)
# ---------------------------------------------------------------------------


def test_ac5_lock_nach_exception_wieder_frei(monkeypatch):
    """Given der erste Versand wirft eine Exception, waehrend er den Lock
    haelt / When waehrenddessen ein zweiter, danach ein dritter Aufruf
    eintrifft / Then wird der zweite abgewiesen, der dritte darf wieder
    senden (Freigabe per finally). Teil 1 ist der Fehlernachweis (RED heute);
    Teil 2 allein waere vakuum-gruen."""
    from services.scheduler_dispatch_service import send_compare_preset

    user_id, preset_id = "cmp-lock-ac5-exc", "cp-2124-c"
    _schreibe_preset(user_id, preset_id)
    naht = _Versandnaht(blockiere_user=user_id,
                        ausnahme=RuntimeError("Versandpfad wirft (simuliert)"))
    _naht_einsetzen(monkeypatch, naht)

    ergebnisse: list = []
    fehler: list = []
    thread = _starte_ersten_versand(user_id, preset_id, naht, ergebnisse, fehler)
    try:
        zweiter = send_compare_preset(user_id, preset_id)
    finally:
        naht.weiter.set()
        thread.join(timeout=5)

    assert zweiter.get("status") == "already_in_progress", (
        f"Waehrend der erste Versand (kurz vor seiner Exception) laeuft, muss der "
        f"zweite abgewiesen werden, bekommen {zweiter!r}"
    )
    assert fehler and isinstance(fehler[0], RuntimeError), (
        f"Erster Versand muss die Exception unveraendert weiterreichen: {fehler}"
    )

    dritter = send_compare_preset(user_id, preset_id)
    assert dritter.get("status") == "ok", (
        f"Nach der Exception muss der Lock frei sein (finally), bekommen {dritter!r}"
    )
    assert len(naht.aufrufe) == 2, (
        f"Nur 1. und 3. Aufruf duerfen die Naht betreten: {naht.aufrufe}"
    )


# ---------------------------------------------------------------------------
# AC-5 — Trip- und Compare-Lock nutzen dasselbe Modul `send_lock`
# ---------------------------------------------------------------------------


def test_ac5_trip_und_compare_lock_nutzen_dasselbe_modul_send_lock(monkeypatch):
    """Given das geteilte Modul `services.send_lock` / When ein Schluessel
    dort direkt belegt wird / Then sehen ihn sowohl die Trip-Huellen aus #1756
    als auch der Compare-Versand — EIN Register, keine Kopie der Logik.
    Getrennte Schluesselraeume: ein laufender Compare-Versand fuer Preset-ID X
    blockiert keinen Trip-Lock fuer dieselbe ID X desselben Nutzers.
    RED heute: `services.send_lock` existiert nicht (ImportError)."""
    from services import send_lock
    from services import trip_report_scheduler as trs
    from services.scheduler_dispatch_service import send_compare_preset

    user_id = "cmp-lock-ac5-modul"
    gleiche_id = "gleiche-id-2124"

    # (a) Trip: im geteilten Modul belegt -> Trip-Huelle sieht ihn als belegt.
    assert send_lock.try_acquire_send_lock(user_id, gleiche_id, "evening") is True
    try:
        assert trs._try_acquire_send_lock(user_id, gleiche_id, "evening") is False, (
            "Trip-Huelle muss das Register von services.send_lock nutzen"
        )
    finally:
        send_lock.release_send_lock(user_id, gleiche_id, "evening")
    assert trs._try_acquire_send_lock(user_id, gleiche_id, "evening") is True
    trs._release_send_lock(user_id, gleiche_id, "evening")

    # (b) Compare: im geteilten Modul belegt -> Compare-Versand weist ab.
    _schreibe_preset(user_id, gleiche_id)
    naht = _Versandnaht()
    _naht_einsetzen(monkeypatch, naht)
    assert send_lock.try_acquire_send_lock("compare", user_id, gleiche_id) is True
    try:
        belegt = send_compare_preset(user_id, gleiche_id)
    finally:
        send_lock.release_send_lock("compare", user_id, gleiche_id)
    assert belegt.get("status") == "already_in_progress", (
        f"Compare-Versand muss den Schluessel ('compare', user_id, preset_id) in "
        f"services.send_lock pruefen, bekommen {belegt!r}"
    )
    assert naht.aufrufe == [], f"Abgewiesener Versand darf nicht senden: {naht.aufrufe}"

    # (c) Getrennte Schluesselraeume: laufender Compare-Versand fuer X
    #     blockiert den Trip-Lock fuer Trip-ID X nicht.
    naht_c = _Versandnaht(blockiere_user=user_id)
    _naht_einsetzen(monkeypatch, naht_c)
    ergebnisse: list = []
    fehler: list = []
    thread = _starte_ersten_versand(user_id, gleiche_id, naht_c, ergebnisse, fehler)
    try:
        trip_frei = trs._try_acquire_send_lock(user_id, gleiche_id, "evening")
        if trip_frei:
            trs._release_send_lock(user_id, gleiche_id, "evening")
    finally:
        naht_c.weiter.set()
        thread.join(timeout=5)
    assert trip_frei is True, (
        "Compare- und Trip-Schluessel muessen getrennt sein: ein laufender "
        "Compare-Versand darf den Trip-Lock fuer dieselbe ID nicht belegen"
    )


# ---------------------------------------------------------------------------
# AC-8 — Mandantentrennung: zwei Nutzer, gleiche Preset-ID
# ---------------------------------------------------------------------------


def test_ac8_zwei_nutzer_gleiche_preset_id_blockieren_sich_nicht(monkeypatch):
    """Given `user_x` und `user_y` senden gleichzeitig ein Preset mit
    identischer `preset_id` / When beide Versaende verschraenkt laufen /
    Then bekommt keiner `already_in_progress`, beide werden zugestellt.

    Kontroll-Bein im selben Test: ein zweiter Versand von `user_x` fuer
    DASSELBE Preset waehrend dessen Lauf MUSS abgewiesen werden — sonst waere
    dieser Test schon ohne jeden Lock gruen (vakuum). Damit ist er heute rot
    (Kontroll-Bein) und rot bei der Mutation „Lock-Schluessel ohne user_id"
    (dann wuerde `user_y` blockiert)."""
    from services.scheduler_dispatch_service import send_compare_preset

    preset_id = "cp-2124-gleich"
    user_x, user_y = "user_x", "user_y"
    _schreibe_preset(user_x, preset_id)
    _schreibe_preset(user_y, preset_id)
    naht = _Versandnaht(blockiere_user=user_x)
    _naht_einsetzen(monkeypatch, naht)

    ergebnisse_x: list = []
    fehler_x: list = []
    thread = _starte_ersten_versand(user_x, preset_id, naht, ergebnisse_x, fehler_x)
    try:
        ergebnis_y = send_compare_preset(user_y, preset_id)
        kontrolle_x = send_compare_preset(user_x, preset_id)
    finally:
        naht.weiter.set()
        thread.join(timeout=5)

    assert not fehler_x, f"Versand von user_x darf nicht scheitern: {fehler_x}"
    assert ergebnis_y.get("status") == "ok", (
        f"user_y darf durch den laufenden Versand von user_x (gleiche preset_id) "
        f"nicht blockiert werden, bekommen {ergebnis_y!r}"
    )
    assert ergebnisse_x and ergebnisse_x[0].get("status") == "ok", (
        f"Versand von user_x muss zugestellt werden: {ergebnisse_x}"
    )
    assert kontrolle_x.get("status") == "already_in_progress", (
        f"Kontroll-Bein: zweiter Versand von user_x fuer dasselbe Preset waehrend "
        f"des Laufs muss abgewiesen werden, bekommen {kontrolle_x!r}"
    )
    assert sorted(naht.aufrufe) == [(user_x, preset_id), (user_y, preset_id)], (
        f"Genau ein Versand je Nutzer erwartet: {naht.aufrufe}"
    )
