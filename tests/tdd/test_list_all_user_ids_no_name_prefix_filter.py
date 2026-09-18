"""TDD RED — Issue #2152, AC-9: ``list_all_user_ids()`` blendet Konten nicht mehr
ueber den ``startswith("test")``-Vorfilter aus (src/app/loader.py:1209-1211).

Spec: docs/specs/modules/testkonto_profilfeld.md

RED-Stand: "testarossa" (ohne Flag) fehlt heute in der Rueckgabe — der
Verzeichnis-Vorfilter greift, bevor das Praedikat ueberhaupt laeuft. Der
``_``-Praefix-Ausschluss (technische Verzeichnisse) bleibt bestehen.
"""
from __future__ import annotations

import json
from pathlib import Path

from app.loader import get_data_dir, list_all_user_ids


def _write_profile_under(root: Path, user_id: str, profile: dict) -> None:
    d = root / "users" / user_id
    d.mkdir(parents=True, exist_ok=True)
    (d / "user.json").write_text(json.dumps(profile), encoding="utf-8")


def test_testarossa_ohne_flag_erscheint_in_liste_ac9(tmp_path):
    """AC-9 GIVEN Verzeichnis mit "testarossa" (Name beginnt mit "test", kein
    Flag) / WHEN ``list_all_user_ids()`` / THEN ist "testarossa" enthalten."""
    _write_profile_under(tmp_path, "testarossa", {"id": "testarossa"})
    _write_profile_under(tmp_path, "henning", {"id": "henning"})

    ids = list_all_user_ids(data_dir=str(tmp_path))

    assert "testarossa" in ids, (
        f"BUG #2152: startswith('test')-Vorfilter blendet testarossa aus: {ids}"
    )
    assert "henning" in ids


def test_reale_nutzer_vor_geflaggten_testkonten_ac9(tmp_path):
    """AC-9 (Sortierung bleibt) GIVEN "testarossa" ohne Flag, "mitarbeiter42" mit
    Flag, "tg-live-e2e" / THEN reale Nutzer zuerst, Testkonten (Flag ODER
    Konstante) danach — "testarossa" zaehlt als real."""
    _write_profile_under(tmp_path, "testarossa", {"id": "testarossa"})
    _write_profile_under(tmp_path, "henning", {"id": "henning"})
    _write_profile_under(tmp_path, "mitarbeiter42", {"id": "mitarbeiter42", "is_test_user": True})
    _write_profile_under(tmp_path, "tg-live-e2e", {"id": "tg-live-e2e"})

    ids = list_all_user_ids(data_dir=str(tmp_path))

    assert ids == ["henning", "testarossa", "mitarbeiter42", "tg-live-e2e"], ids


def test_unterstrich_verzeichnisse_bleiben_ausgeschlossen_ac9(tmp_path):
    """Der technische ``_``-Praefix-Ausschluss ist NICHT Teil der Aenderung."""
    _write_profile_under(tmp_path, "_archive", {"id": "_archive"})
    _write_profile_under(tmp_path, "testarossa", {"id": "testarossa"})

    ids = list_all_user_ids(data_dir=str(tmp_path))

    assert ids == ["testarossa"], ids


def test_ohne_data_dir_wird_konfigurierte_wurzel_gelesen_ac9():
    """AC-9 ueber die konfigurierte Wurzel (``get_data_root()``, isoliert per
    tests/conftest.py #1133): "testarossa" erscheint auch ohne ``data_dir``."""
    p = get_data_dir("testarossa")
    p.mkdir(parents=True, exist_ok=True)
    (p / "user.json").write_text(json.dumps({"id": "testarossa"}), encoding="utf-8")

    assert "testarossa" in list_all_user_ids()
