"""TDD RED — Issue #2152, AC-5 (Python): ``is_test_user_id`` entscheidet ueber das
Profilfeld ``is_test_user`` ODER die feste Fixture-Konstante ``tg-live-e2e`` —
KEINE "test"/"tdd"-Namens-Heuristik mehr.

Spec: docs/specs/modules/testkonto_profilfeld.md

Erwartete GREEN-Signatur (src/app/config.py):

    def is_test_user_id(user_id: str, data_dir: str | None = None) -> bool
        # data_dir=None → get_data_root() (loader, respektiert _DATA_ROOT/GZ_DATA_DIR)

RED-Stand (vor GREEN):
- ROT: ``is_test_user_id("protester", data_dir=tmp)`` liefert heute True (Substring).
- ROT: Aufruf OHNE ``data_dir`` fuer ein geflaggtes Konto unter der konfigurierten
  Wurzel liefert heute False (Default ist der literale String "data").
- GRUEN (Regressions-Pin, sichert gegen Mitreissen in GREEN): ``tg-live-e2e``
  bleibt Testkonto; ``mitarbeiter42`` mit Flag und explizitem ``data_dir`` ist eins.
"""
from __future__ import annotations

import json
from pathlib import Path

from app import loader
from app.config import is_test_user_id
from app.loader import get_data_dir


def _write_profile_under(root: Path, user_id: str, profile: dict) -> None:
    d = root / "users" / user_id
    d.mkdir(parents=True, exist_ok=True)
    (d / "user.json").write_text(json.dumps(profile), encoding="utf-8")


def test_tg_live_e2e_bleibt_testkonto_ohne_flag_ac5(tmp_path):
    """AC-5 GIVEN die feste Fixture-ID ohne Profil / THEN True (unveraendert,
    auch case-insensitive). Regressions-Pin — heute bereits gruen."""
    assert is_test_user_id("tg-live-e2e", data_dir=str(tmp_path)) is True
    assert is_test_user_id("TG-LIVE-E2E", data_dir=str(tmp_path)) is True
    assert is_test_user_id("tg-live-e2e") is True


def test_protester_ohne_flag_ist_kein_testkonto_ac5(tmp_path):
    """AC-5/AC-2 GIVEN Konto "protester" ohne Flag (und ohne Profil) / THEN False
    — der "test"-Substring entscheidet nicht mehr."""
    _write_profile_under(tmp_path, "protester", {"id": "protester"})

    assert is_test_user_id("protester", data_dir=str(tmp_path)) is False, (
        "BUG #2152: Namens-Heuristik klassifiziert protester als Testkonto"
    )
    assert is_test_user_id("mattdd", data_dir=str(tmp_path)) is False
    assert is_test_user_id("testarossa", data_dir=str(tmp_path)) is False


def test_neutraler_name_mit_flag_ist_testkonto_ac5(tmp_path):
    """AC-5 GIVEN "mitarbeiter42" mit ``is_test_user: true`` / THEN True.
    Regressions-Pin mit explizitem ``data_dir`` — heute bereits gruen."""
    _write_profile_under(tmp_path, "mitarbeiter42", {"id": "mitarbeiter42", "is_test_user": True})

    assert is_test_user_id("mitarbeiter42", data_dir=str(tmp_path)) is True
    # false/fehlend bleibt kein Testkonto
    _write_profile_under(tmp_path, "henning", {"id": "henning", "is_test_user": False})
    assert is_test_user_id("henning", data_dir=str(tmp_path)) is False


def test_ohne_data_dir_wird_konfigurierte_wurzel_gelesen():
    """AC-5/AC-4 GIVEN ein geflaggtes Profil unter ``get_data_dir()`` (isolierte
    ``_DATA_ROOT``-Wurzel, tests/conftest.py #1133) / WHEN ``is_test_user_id``
    OHNE ``data_dir`` aufgerufen wird / THEN True — der Default ist die
    konfigurierte Datenwurzel, nicht der literale Pfad "data"."""
    p = get_data_dir("mitarbeiter42")
    p.mkdir(parents=True, exist_ok=True)
    (p / "user.json").write_text(
        json.dumps({"id": "mitarbeiter42", "is_test_user": True}), encoding="utf-8"
    )

    assert is_test_user_id("mitarbeiter42") is True, (
        "BUG #2152: Profilfeld unter der konfigurierten Datenwurzel wird ohne "
        "data_dir-Argument nicht gelesen (Default 'data' statt get_data_root())"
    )


def test_ohne_data_dir_respektiert_gz_data_dir(tmp_path, monkeypatch):
    """Dieselbe Zusicherung ueber die zweite Quelle der Wurzel: ``_DATA_ROOT``
    unbesetzt, ``GZ_DATA_DIR`` zeigt auf tmp_path."""
    _write_profile_under(tmp_path, "mitarbeiter42", {"id": "mitarbeiter42", "is_test_user": True})
    monkeypatch.setattr(loader, "_DATA_ROOT", None)
    monkeypatch.setenv("GZ_DATA_DIR", str(tmp_path))

    assert is_test_user_id("mitarbeiter42") is True
    assert is_test_user_id("protester") is False
