"""Zwei-Nutzer-Nachweis: der Python-Core baut Pfade unter users/<id>/ nur mit
gepruefter Kennung (Issue #2163 Scheibe 2).

SPEC: docs/specs/modules/auth_haertung_python_2163.md, AC-1 bis AC-8, AC-12.

Bauart ohne Mock: Alice und Bob bekommen echte Dateien in ``tmp_path``; die
Datenwurzel wird per dokumentiertem Override ``loader._DATA_ROOT`` umgebogen.
Angriffskennung ist ``../users/bob`` bzw. ``alice/../bob`` (NICHT ``../bob``:
``users/../bob`` zeigt auf ``root/bob``, das es nicht gibt, Test waere blind).
Dateizugriffe werden ueber einen Audit-Hook (``sys.addaudithook``, Ereignis
``open``) beobachtet, nicht ueber Patches. Kein Netz: Bobs Preset hat keine
Orte und keine Empfaenger, und der Handversand laeuft mit vorab gehaltener
Sende-Sperre, sodass er heute vor jedem Versand endet.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest

from app import loader

ANGRIFF = ["../users/bob", "alice/../bob"]

_OFFENE_PFADE: list | None = None


def _audit(event, args):
    if event == "open" and _OFFENE_PFADE is not None and args and isinstance(args[0], (str, bytes, os.PathLike)):
        _OFFENE_PFADE.append(os.fsdecode(args[0]))


sys.addaudithook(_audit)


@contextmanager
def _beobachte_oeffnungen():
    global _OFFENE_PFADE
    _OFFENE_PFADE = []
    try:
        yield _OFFENE_PFADE
    finally:
        _OFFENE_PFADE = None


def _bob_gelesen(pfade: list) -> list:
    return [p for p in pfade if "bob" in p.split(os.sep)]


def _fehlertyp():
    typ = getattr(loader, "InvalidUserIdError", None)
    assert typ is not None, "app.loader.InvalidUserIdError existiert nicht"
    return typ


def _rufe(fn, *a, **kw):
    try:
        return fn(*a, **kw), None
    except Exception as e:  # noqa: BLE001 -- Ergebnis wird danach geprueft
        return None, e


def _schnappschuss(root: Path) -> tuple:
    dateien, ordner = {}, set()
    for d, subdirs, files in os.walk(root):
        for s in subdirs:
            ordner.add(os.path.relpath(os.path.join(d, s), root))
        for f in files:
            p = os.path.join(d, f)
            dateien[os.path.relpath(p, root)] = hashlib.sha256(Path(p).read_bytes()).hexdigest()
    return dateien, ordner


def _schreibe(p: Path, data: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _trip(tid: str, name: str) -> dict:
    return {"id": tid, "name": name, "stages": []}


@pytest.fixture
def root(tmp_path, monkeypatch):
    """Alice und Bob mit je eigenen, unterschiedlichen Daten."""
    monkeypatch.setattr(loader, "_DATA_ROOT", str(tmp_path))
    users = tmp_path / "users"
    _schreibe(users / "alice" / "user.json", {"mail_to": "alice@example.org"})
    _schreibe(users / "alice" / "briefings" / "alice-vergleich.json",
              {"id": "alice-vergleich", "kind": "vergleich", "name": "Alice-Vergleich", "schedule": "daily"})
    _schreibe(users / "alice" / "briefings" / "alice-trip.json", _trip("alice-trip", "Alice-Trip"))
    _schreibe(users / "bob" / "user.json",
              {"mail_to": "bob@example.org", "is_test_user": True, "disabled": True})
    _schreibe(users / "bob" / "briefings" / "bob-aktiv.json",
              {"id": "bob-aktiv", "kind": "vergleich", "name": "Bob-Aktiv", "schedule": "daily",
               "location_ids": [], "empfaenger": []})
    _schreibe(users / "bob" / "briefings" / "bob-pausiert.json",
              {"id": "bob-pausiert", "kind": "vergleich", "name": "Bob-Pausiert", "schedule": "manual",
               "previous_schedule": "daily", "paused_at": "2026-10-01T00:00:00Z"})
    _schreibe(users / "bob" / "briefings" / "bob-trip.json", _trip("bob-trip", "Bob-Trip"))
    return tmp_path


def _lese_vergleiche(uid, r):
    return loader.load_compare_presets(uid, r)


def _lese_trip(uid, r):
    return loader.load_trip("bob-trip", data_dir=r, user_id=uid)


def _lese_dispatch(uid, r):
    from services.scheduler_dispatch_service import _load_presets_for_dispatch
    return _load_presets_for_dispatch(uid, str(r))


@pytest.mark.parametrize("kennung", ANGRIFF)
@pytest.mark.parametrize("leser", [_lese_vergleiche, _lese_trip, _lese_dispatch],
                         ids=["load_compare_presets", "load_trip", "load_presets_for_dispatch"])
def test_angriffskennung_liest_keine_daten_von_bob(root, kennung, leser):
    """AC-1. GIVEN Bob hat Preset und Trip WHEN ein Leser die Angriffskennung bekommt
    THEN kommt nichts von Bob zurueck und es fliegt InvalidUserIdError."""
    ergebnis, fehler = _rufe(leser, kennung, root)
    assert "bob-" not in repr(ergebnis), "Angriffskennung lieferte Bobs Daten"
    assert isinstance(fehler, _fehlertyp()), f"erwartet InvalidUserIdError, bekam {fehler!r}"


@pytest.mark.parametrize("pruefung", ["is_test_user_id", "is_user_disabled"])
def test_fail_soft_leser_sagen_false_und_oeffnen_bobs_profil_nicht(root, pruefung):
    """AC-2/AC-3. GIVEN Bobs user.json mit is_test_user/disabled true WHEN mit
    Angriffskennung gefragt wird THEN False, ohne Bobs Datei zu oeffnen."""
    from app.config import is_test_user_id
    fn = is_test_user_id if pruefung == "is_test_user_id" else loader.is_user_disabled
    assert fn("bob", str(root)) is True  # Gegenprobe: Bob selbst ist markiert
    with _beobachte_oeffnungen() as offen:
        ergebnis = fn("../users/bob", str(root))
    assert ergebnis is False, f"{pruefung}('../users/bob') lieferte {ergebnis!r} (Bobs Profil)"
    assert not _bob_gelesen(offen), f"Bobs Datei geoeffnet: {offen}"


def _status(uid, r):
    from services.scheduler_dispatch_service import save_compare_preset_status
    return save_compare_preset_status(uid, "bob-aktiv", "Ort", data_root=str(r))


def _pause(uid, r):
    from services.scheduler_dispatch_service import save_compare_preset_pause
    return save_compare_preset_pause(uid, "bob-aktiv", data_root=str(r))


def _resume(uid, r):
    from services.scheduler_dispatch_service import resume_compare_preset
    return resume_compare_preset(uid, "bob-pausiert", data_root=str(r))


@pytest.mark.parametrize("kennung", ANGRIFF)
@pytest.mark.parametrize("schreiber", [_status, _pause, _resume],
                         ids=["save_status", "save_pause", "resume"])
def test_preset_schreiber_lassen_bobs_dateien_byte_gleich(root, kennung, schreiber):
    """AC-4. GIVEN Bobs echte Presets WHEN ein Preset-Schreiber die Angriffskennung
    bekommt THEN bleibt jede Datei byte-gleich, kein Verzeichnis entsteht, und
    der Schreiber bleibt fail-soft (kein neuer Fehlerausgang)."""
    vorher = _schnappschuss(root)
    ergebnis = schreiber(kennung, root)
    assert _schnappschuss(root) == vorher, "Angriffskennung hat Bobs Daten veraendert"
    assert ergebnis not in (True, "resumed"), f"Schreiber meldet Erfolg: {ergebnis!r}"


@pytest.mark.parametrize("kennung", ["../users/bob", "../users/mallory", "alice/../mallory"])
def test_briefings_dir_for_legt_nichts_an_und_wirft(root, kennung):
    """AC-4. GIVEN Bob existiert, Mallory nicht WHEN _briefings_dir_for die
    Angriffskennung bekommt THEN entsteht kein Verzeichnis und es fliegt
    InvalidUserIdError."""
    vorher = _schnappschuss(root)
    _, fehler = _rufe(loader._briefings_dir_for, kennung, root)
    assert _schnappschuss(root) == vorher, "Verzeichnisbaum wurde veraendert"
    assert isinstance(fehler, _fehlertyp()), f"erwartet InvalidUserIdError, bekam {fehler!r}"


@pytest.mark.parametrize("kennung", ANGRIFF)
def test_with_user_profile_lehnt_ab_bevor_bobs_profil_gelesen_wird(root, kennung):
    """AC-5. GIVEN Bobs user.json mit is_test_user WHEN with_user_profile die
    Angriffskennung bekommt THEN InvalidUserIdError als erste Handlung, Bobs
    Datei wird nicht geoeffnet."""
    from app.config import Settings
    settings = Settings()
    with _beobachte_oeffnungen() as offen:
        _, fehler = _rufe(settings.with_user_profile, kennung)
    assert not _bob_gelesen(offen), f"Bobs Datei vor der Ablehnung gelesen: {offen}"
    assert isinstance(fehler, _fehlertyp()), f"erwartet InvalidUserIdError, bekam {fehler!r}"


@pytest.mark.parametrize("kennung", ANGRIFF)
def test_send_compare_preset_lehnt_ab_vor_dateizugriff_und_sperre(root, kennung):
    """AC-6. GIVEN Bobs Preset existiert und die Sende-Sperre fuer die Kennung ist
    schon belegt WHEN send_compare_preset die Angriffskennung bekommt THEN fliegt
    InvalidUserIdError, bevor Bobs Datei gelesen oder die Sperre befragt wird."""
    from services.scheduler_dispatch_service import send_compare_preset
    from services.send_lock import release_send_lock, try_acquire_send_lock
    assert try_acquire_send_lock("compare", kennung, "bob-aktiv")  # verhindert jeden Versand
    try:
        with _beobachte_oeffnungen() as offen:
            ergebnis, fehler = _rufe(send_compare_preset, kennung, "bob-aktiv", str(root))
    finally:
        release_send_lock("compare", kennung, "bob-aktiv")
    assert not _bob_gelesen(offen), f"Bobs Preset vor der Ablehnung gelesen: {offen}"
    assert ergebnis is None, f"Aufruf lief bis zur Sende-Sperre durch: {ergebnis!r}"
    assert isinstance(fehler, _fehlertyp()), f"erwartet InvalidUserIdError, bekam {fehler!r}"

def _fehler_with_user_profile(kennung, r):
    from app.config import Settings
    return _rufe(Settings().with_user_profile, kennung)[1]


def _fehler_send_compare(kennung, r):
    from services.scheduler_dispatch_service import send_compare_preset
    from services.send_lock import release_send_lock, try_acquire_send_lock
    assert try_acquire_send_lock("compare", kennung, "bob-aktiv")  # Netzsicherung
    try:
        return _rufe(send_compare_preset, kennung, "bob-aktiv", str(r))[1]
    finally:
        release_send_lock("compare", kennung, "bob-aktiv")


def _fehler_forecast_budget(kennung, r):
    from services.forecast_budget import ForecastBudgetGate
    return _rufe(ForecastBudgetGate, kennung, data_root=r)[1]


@pytest.mark.parametrize("kennung", ANGRIFF)
@pytest.mark.parametrize("ausloeser", [
    lambda k, r: _rufe(loader.user_dir, r, k)[1],
    _fehler_with_user_profile,
    _fehler_send_compare,
    _fehler_forecast_budget,
], ids=["user_dir", "with_user_profile", "send_compare_preset", "forecast_budget"])
def test_fehlertext_spiegelt_die_kennung_nie(root, kennung, ausloeser):
    """F001/F002 (#2163). GIVEN die Angriffskennung WHEN eine harte Pruefstelle
    ablehnt THEN ist es InvalidUserIdError, und str(exc) enthaelt weder die
    Kennung noch 'bob' noch 'users' (keine Spiegelung, auch nicht im Log)."""
    fehler = ausloeser(kennung, root)
    assert isinstance(fehler, _fehlertyp()), f"erwartet InvalidUserIdError, bekam {fehler!r}"
    text = str(fehler)
    for verraeter in (kennung, "bob", "users"):
        assert verraeter not in text, f"Kennung gespiegelt: {text!r}"


ZEILENUMBRUCH = "alice\n"


def test_zeilenumbruch_kennung_ist_ungueltig():
    """AC-7. GIVEN 'alice\\n' WHEN is_valid_user_id fragt THEN False, 'alice' True."""
    pruefer = getattr(loader, "is_valid_user_id", None)
    assert pruefer is not None, "app.loader.is_valid_user_id existiert nicht"
    assert pruefer(ZEILENUMBRUCH) is False
    assert pruefer("alice") is True
    assert pruefer(None) is False


def test_user_dir_lehnt_zeilenumbruch_und_angriff_ab(root):
    """AC-7. GIVEN user_dir WHEN 'alice\\n' oder '../users/bob' kommt THEN
    InvalidUserIdError; 'alice' liefert root/users/alice."""
    baue = getattr(loader, "user_dir", None)
    assert baue is not None, "app.loader.user_dir existiert nicht"
    assert baue(root, "alice") == root / "users" / "alice"
    for kennung in (ZEILENUMBRUCH, *ANGRIFF, ""):
        _, fehler = _rufe(baue, root, kennung)
        assert isinstance(fehler, _fehlertyp()), f"{kennung!r}: {fehler!r}"


def test_get_data_dir_lehnt_zeilenumbruch_ab(root):
    """AC-7. GIVEN 'alice\\n' WHEN get_data_dir THEN InvalidUserIdError statt Pfad."""
    ergebnis, fehler = _rufe(loader.get_data_dir, ZEILENUMBRUCH)
    assert ergebnis is None, f"get_data_dir nahm 'alice\\n' an: {ergebnis!r}"
    assert isinstance(fehler, _fehlertyp()), f"erwartet InvalidUserIdError, bekam {fehler!r}"


def test_forecast_budget_lehnt_zeilenumbruch_ab(root):
    """AC-7. GIVEN 'alice\\n' WHEN ForecastBudgetGate mit eigener Wurzel entsteht
    THEN ValueError (wie fuer jede ungueltige Kennung)."""
    from services.forecast_budget import ForecastBudgetGate
    gate, fehler = _rufe(ForecastBudgetGate, ZEILENUMBRUCH, data_root=root)
    assert gate is None and isinstance(fehler, ValueError), f"angenommen: {gate!r} / {fehler!r}"


def test_alert_input_capture_schreibt_nicht_fuer_zeilenumbruch(root):
    """AC-7. GIVEN 'alice\\n' WHEN capture_user_scoped schreibt THEN None und kein
    Verzeichnis 'alice\\n' unter users/."""
    from services.alert_input_capture import capture_user_scoped
    ergebnis = capture_user_scoped(ZEILENUMBRUCH, entity_type="trip", entity_id="t1", payload={"x": 1})
    assert ergebnis is None, f"Erfassung angenommen: {ergebnis!r}"
    assert not (root / "users" / ZEILENUMBRUCH).exists(), "Verzeichnis 'alice\\n' angelegt"


def test_alice_sieht_mit_gueltiger_kennung_nur_eigene_daten(root):
    """AC-8 (Regressionsschutz, darf heute gruen sein). GIVEN Alice und Bob mit
    eigenen Daten WHEN Alice gueltig liest THEN nur Alices Daten, nie Bobs."""
    from app.config import Settings, is_test_user_id
    assert [p.id for p in loader.load_compare_presets("alice", root)] == ["alice-vergleich"]
    assert sorted(p.id for p in loader.load_compare_presets("bob", root)) == ["bob-aktiv", "bob-pausiert"]
    assert loader.load_trip("alice-trip", data_dir=root, user_id="alice").name == "Alice-Trip"
    assert loader.load_trip("bob-trip", data_dir=root, user_id="alice") is None
    assert is_test_user_id("alice", str(root)) is False
    assert loader.is_user_disabled("alice", str(root)) is False
    assert Settings().with_user_profile("alice").mail_to == "alice@example.org"
    assert loader.get_data_dir("alice") == root / "users" / "alice"


def test_valid_user_id_re_match_wird_nirgends_mehr_benutzt():
    """AC-12. GIVEN src/ und api/ WHEN nach 'VALID_USER_ID_RE.match(' gesucht wird
    THEN kommt es nirgends mehr vor (Anwendung nur noch per fullmatch)."""
    # doc-compliance-test
    repo = Path(__file__).resolve().parents[2]
    treffer = [
        f"{p.relative_to(repo)}:{n}"
        for ordner in ("src", "api")
        for p in (repo / ordner).rglob("*.py")
        for n, zeile in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
        if "VALID_USER_ID_RE.match(" in zeile
    ]
    assert not treffer, f"VALID_USER_ID_RE.match( noch in: {treffer}"
