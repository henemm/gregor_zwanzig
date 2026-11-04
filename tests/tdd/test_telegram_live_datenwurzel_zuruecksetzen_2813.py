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
