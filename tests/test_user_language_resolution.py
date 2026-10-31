"""Issue #2646 (i18n S1) -- Python-Aufloesung der Nutzersprache.

Spec: docs/specs/modules/i18n_s1_sprachfeld_nutzer_2646.md (AC-6).

``resolve_user_lang`` ist die EINZIGE Stelle, ueber die der Python-Core die
Sprache eines Nutzers bezieht. Geprueft gegen echte Dateien in einem
Temp-``data_dir`` (kein Mock): Nutzer A mit ``en``, Nutzer B ohne Feld, ein
unbekannter Nutzer, eine kaputte Datei, die unsichere Kennung ``../bob``.
"""
import json
from pathlib import Path

import pytest

from i18n import resolve_user_lang


def _schreibe(root: Path, user_id: str, inhalt: str) -> Path:
    pfad = root / "users" / user_id / "user.json"
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(inhalt, encoding="utf-8")
    return pfad


@pytest.fixture
def datenwurzel(tmp_path: Path) -> Path:
    _schreibe(tmp_path, "anna", json.dumps({"id": "anna", "language": "en"}))
    _schreibe(tmp_path, "bert", json.dumps({"id": "bert", "display_name": "Bert"}))
    _schreibe(tmp_path, "kaputt", '{"id": "kaputt", "language": "en"')
    _schreibe(tmp_path, "franz", json.dumps({"id": "franz", "language": "fr"}))
    _schreibe(tmp_path, "gross", json.dumps({"id": "gross", "language": "EN"}))
    _schreibe(tmp_path, "liste", json.dumps(["en"]))
    # Ziel der unsicheren Kennung: laege hier "en", darf es trotzdem nie gelesen werden.
    _schreibe(tmp_path, "bob", json.dumps({"id": "bob", "language": "en"}))
    return tmp_path


def test_ac6_nutzer_mit_en_bekommt_en(datenwurzel: Path) -> None:
    assert resolve_user_lang("anna", data_dir=datenwurzel) == "en"
    assert resolve_user_lang("anna", data_dir=str(datenwurzel)) == "en"


@pytest.mark.parametrize(
    "user_id",
    ["bert", "unbekannt", "kaputt", "franz", "gross", "liste", "../bob", "users/../bob", ""],
)
def test_ac6_sonst_immer_deutsch_ohne_ausnahme(datenwurzel: Path, user_id: str) -> None:
    assert resolve_user_lang(user_id, data_dir=datenwurzel) == "de"


def test_ac6_unsichere_kennung_verlaesst_nie_das_nutzerverzeichnis(tmp_path: Path) -> None:
    # data_dir/users/../bob == data_dir/bob: dort liegt "en" -- muss "de" bleiben.
    (tmp_path / "users").mkdir()
    (tmp_path / "bob").mkdir()
    (tmp_path / "bob" / "user.json").write_text('{"language": "en"}', encoding="utf-8")
    assert resolve_user_lang("../bob", data_dir=tmp_path) == "de"


def test_ac6_zwei_nutzer_lesen_nur_die_eigene_datei(datenwurzel: Path) -> None:
    # B wird nach A abgefragt: kein Prozess-/Modulzustand traegt A's "en" zu B.
    assert resolve_user_lang("anna", data_dir=datenwurzel) == "en"
    assert resolve_user_lang("bert", data_dir=datenwurzel) == "de"
    # A's Datei verschwindet: B bleibt de, A faellt auf de (liest jedes Mal neu).
    (datenwurzel / "users" / "anna" / "user.json").unlink()
    assert resolve_user_lang("anna", data_dir=datenwurzel) == "de"
    _schreibe(datenwurzel, "bert", json.dumps({"id": "bert", "language": "en"}))
    assert resolve_user_lang("bert", data_dir=datenwurzel) == "en"


def test_ac6_ohne_data_dir_gilt_die_konfigurierte_datenwurzel(
    datenwurzel: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.loader as loader

    monkeypatch.setattr(loader, "_DATA_ROOT", str(datenwurzel))
    assert resolve_user_lang("anna") == "en"
    assert resolve_user_lang("bert") == "de"
    assert resolve_user_lang("../bob") == "de"


def test_ac6_kennung_mit_zeilenumbruch_bleibt_deutsch(tmp_path: Path) -> None:
    # F001: re.match mit "$" akzeptiert ein abschliessendes "\n" -- fullmatch nicht.
    _schreibe(tmp_path, "bob\n", json.dumps({"id": "bob", "language": "en"}))
    assert resolve_user_lang("bob\n", data_dir=tmp_path) == "de"
