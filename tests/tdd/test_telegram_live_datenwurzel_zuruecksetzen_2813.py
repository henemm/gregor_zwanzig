"""Issue #2813 Teil 4: Telegram-Live-Tests hinterlassen keine Spur in ``data/users``.

Spec: docs/specs/bugfix/e2e_verify_en_mailweg_2813.md (AC-8, AC-9, AC-10)

Kern-Schicht, kein Netz: die Fixture ``tg_live_datenwurzel_zuruecksetzen`` wird in
einer tmp-Datenwurzel gegen echte Dateien geprueft. Der Waechter #2226 in
``tests/conftest.py`` bleibt unveraendert -- die Spur wird wirklich entfernt.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from tests.tdd import _telegram_live_fixture as fx

ROOT = Path(__file__).resolve().parents[2]


def _fingerprint(wurzel: Path) -> dict:
    """Pfad -> Inhalts-Hash aller Dateien UNTER ``users`` (Verzeichnisse als None)."""
    users = wurzel / "users"
    if not users.exists():
        return {}
    return {
        str(p.relative_to(wurzel)): (None if p.is_dir() else hashlib.sha256(p.read_bytes()).hexdigest())
        for p in sorted(users.rglob("*"))
    }


def test_ohne_vorbestand_wird_das_verzeichnis_vollstaendig_entfernt(tmp_path):
    """AC-8: nicht vorhanden -> Test legt an -> danach Fingerprint gleich, Verzeichnis weg."""
    (tmp_path / "users" / "anderer-nutzer").mkdir(parents=True)
    (tmp_path / "users" / "anderer-nutzer" / "user.json").write_text("{}", encoding="utf-8")
    vorher = _fingerprint(tmp_path)

    with fx.tg_live_datenwurzel_zuruecksetzen(str(tmp_path)):
        spur = tmp_path / "users" / fx.TEST_USER_ID
        (spur / "trips").mkdir(parents=True)
        (spur / "user.json").write_text('{"id": "tg-live-e2e"}', encoding="utf-8")
        (spur / "trips" / "tg-live-e2e-trip.json").write_text("{}", encoding="utf-8")
        assert _fingerprint(tmp_path) != vorher

    assert _fingerprint(tmp_path) == vorher
    assert not (tmp_path / "users" / fx.TEST_USER_ID).exists()


def test_ohne_vorbestand_auch_wenn_der_test_fehlschlaegt(tmp_path):
    vorher = _fingerprint(tmp_path)
    try:
        with fx.tg_live_datenwurzel_zuruecksetzen(str(tmp_path)):
            (tmp_path / "users" / fx.TEST_USER_ID).mkdir(parents=True)
            raise RuntimeError("Live-Test bricht ab")
    except RuntimeError:
        pass
    assert _fingerprint(tmp_path) == vorher
    assert not (tmp_path / "users" / fx.TEST_USER_ID).exists()


def test_ohne_users_vorher_bleibt_kein_leeres_users_zurueck(tmp_path):
    """Kein ``users/`` vorher => keines nachher (kein leerer Rest im echten Baum)."""
    assert not (tmp_path / "users").exists()
    with fx.tg_live_datenwurzel_zuruecksetzen(str(tmp_path)):
        (tmp_path / "users" / fx.TEST_USER_ID).mkdir(parents=True)
        (tmp_path / "users" / fx.TEST_USER_ID / "user.json").write_text("{}", encoding="utf-8")
    assert not (tmp_path / "users").exists()


_DUMMY_LIVE_TESTS = '''
import pytest
from pathlib import Path

from tests.tdd._telegram_live_fixture import (  # noqa: F401
    tg_live_datenwurzel_zuruecksetzen_autouse,
)

SPUR = Path("data") / "users" / "tg-live-e2e"


@pytest.mark.real_data_root
def test_a_live_test_legt_spur_an():
    (SPUR / "trips").mkdir(parents=True)
    (SPUR / "user.json").write_text("{}", encoding="utf-8")
    assert SPUR.exists()


def test_b_danach_ist_die_spur_weg():
    assert not SPUR.exists(), "real_data_root-Spur wurde nicht zurueckgesetzt"
'''


def test_autouse_fixture_raeumt_nach_real_data_root_test_wirklich_auf(tmp_path):
    """F001: die GEMEINSAME autouse-Fixture in einem echten pytest-Lauf (Subprozess,
    CWD = tmp_path, also ``data`` = tmp-Wurzel): ein ``real_data_root``-Test legt
    ``data/users/tg-live-e2e`` an, der naechste Test und der Aufrufer sehen keine Spur."""
    import subprocess
    import sys

    (tmp_path / "pytest.ini").write_text(
        "[pytest]\nmarkers =\n    real_data_root: Test\n", encoding="utf-8")
    (tmp_path / "test_dummy_live.py").write_text(_DUMMY_LIVE_TESTS, encoding="utf-8")
    env = {**__import__("os").environ, "PYTHONPATH": str(ROOT)}
    lauf = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q",
         "test_dummy_live.py"],
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=120,
    )
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr
    assert "2 passed" in lauf.stdout, lauf.stdout
    assert not (tmp_path / "data" / "users" / fx.TEST_USER_ID).exists()


def test_beide_live_testdateien_registrieren_die_gemeinsame_fixture():
    """F001 (Verdrahtung): pytest registriert Fixtures aus dem Modul-Namensraum --
    fehlt der Import, laeuft der Live-Test ohne Zuruecksetzen."""
    import importlib

    for name in ("test_issue_686_telegram_functional_live", "test_telegram_live_zweisprachig"):
        mod = importlib.import_module(f"tests.tdd.{name}")
        assert getattr(mod, "tg_live_datenwurzel_zuruecksetzen_autouse", None) \
            is fx.tg_live_datenwurzel_zuruecksetzen_autouse, name


def test_mit_vorbestand_wird_der_urspruengliche_inhalt_wiederhergestellt(tmp_path):
    """AC-9: Datei veraendert, Neues angelegt, Vorbestand geloescht -> alles wie vorher."""
    spur = tmp_path / "users" / fx.TEST_USER_ID
    (spur / "trips").mkdir(parents=True)
    (spur / "user.json").write_text('{"id": "tg-live-e2e", "telegram_chat_id": "42"}', encoding="utf-8")
    (spur / "trips" / "alt.json").write_text('{"alt": true}', encoding="utf-8")
    vorher = _fingerprint(tmp_path)

    with fx.tg_live_datenwurzel_zuruecksetzen(str(tmp_path)):
        (spur / "user.json").write_text('{"id": "tg-live-e2e", "language": "en"}', encoding="utf-8")
        (spur / "trips" / "neu.json").write_text("{}", encoding="utf-8")
        (spur / "trips" / "alt.json").unlink()
        (spur / "snapshots").mkdir()
        assert _fingerprint(tmp_path) != vorher

    assert _fingerprint(tmp_path) == vorher
    assert (spur / "user.json").read_text(encoding="utf-8") == \
        '{"id": "tg-live-e2e", "telegram_chat_id": "42"}'
    assert not (spur / "trips" / "neu.json").exists()
    assert not (spur / "snapshots").exists()


def test_fremde_nutzer_bleiben_unberuehrt(tmp_path):
    """Nur ``tg-live-e2e`` wird zurueckgesetzt, nie ein anderer Nutzer (Mandantentrennung)."""
    fremd = tmp_path / "users" / "echter-nutzer"
    fremd.mkdir(parents=True)
    (fremd / "user.json").write_text('{"id": "echter-nutzer"}', encoding="utf-8")
    with fx.tg_live_datenwurzel_zuruecksetzen(str(tmp_path)):
        (fremd / "user.json").write_text('{"id": "echter-nutzer", "neu": 1}', encoding="utf-8")
    assert "neu" in (fremd / "user.json").read_text(encoding="utf-8")


def test_beide_live_testdateien_binden_die_fixture_ein():
    """AC-8 (Verdrahtung): ohne Einbindung nuetzt die Fixture dem Live-Lauf nichts."""
    # doc-compliance-test
    for name in ("test_issue_686_telegram_functional_live.py", "test_telegram_live_zweisprachig.py"):
        quelle = (ROOT / "tests" / "tdd" / name).read_text(encoding="utf-8")  # doc-compliance-test
        assert "tg_live_datenwurzel_zuruecksetzen" in quelle, name


def test_e2e_verify_doku_nennt_live_marker_und_subject_contains():
    """AC-10: reine Doku, kein Verhaltensnachweis."""
    # doc-compliance-test
    doku = (ROOT / ".claude" / "commands" / "e2e-verify.md").read_text(encoding="utf-8")  # doc-compliance-test
    assert "-m live" in doku
    assert "0 selected" in doku
    for validator in ("official_alert_mail_validator", "radar_alert_mail_validator"):
        zeilen = [z for z in doku.splitlines() if validator in z]
        assert any("--subject-contains" in z for z in zeilen), validator
