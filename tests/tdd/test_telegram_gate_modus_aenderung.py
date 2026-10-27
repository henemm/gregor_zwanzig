"""
Telegram-Live-Gate: eine reine Dateimodus-Änderung ist kein Telegram-Verhalten (#2630).

`_telegram_live_gate()` darf den Test-Chat nur verlangen, wenn sich Telegram-VERHALTEN
ändert. Eine Telegram-namige Datei, die nur den `fsmode`-Import und einen
`os.Chmod(…, fsmode.FileMode)`-Block bekommt (#2624), ist neutral.

KEINE Mocks: echte temporäre git-Repos, echte `git diff`-Ausgabe, echtes Gate
(`staging_gate._telegram_live_gate`). monkeypatch nur für ENV + REPO_DIR.

Spec: docs/specs/modules/fix_2630_telegram_gate_modus_aenderung.md
"""
from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO / ".claude" / "hooks"

GO_FILE = "internal/handler/telegram_connect.go"
PY_FILE = "src/channels/telegram_x.py"

GO_BEFORE = """package handler

import (
\t"os"
)

func writeToken(tmpName string, data []byte) error {
\twerr := os.WriteFile(tmpName, data, 0o600)
\tif werr != nil {
\t\treturn werr
\t}
\treturn nil
}
"""

# Der Diff aus Commit 04b8e0472: Import + Chmod-Block.
GO_MODE_ONLY = """package handler

import (
\t"os"

\t"gregor/internal/fsmode"
)

func writeToken(tmpName string, data []byte) error {
\twerr := os.WriteFile(tmpName, data, 0o600)
\tif werr == nil {
\t\twerr = os.Chmod(tmpName, fsmode.FileMode)
\t}
\tif werr != nil {
\t\treturn werr
\t}
\treturn nil
}
"""

PY_BEFORE = """import os


def save(pfad, daten):
    with open(pfad, "w") as f:
        f.write(daten)
    return True
"""

PY_MODE_ONLY = """import os
from src.app import fsmode


def save(pfad, daten):
    with open(pfad, "w") as f:
        f.write(daten)
    os.chmod(pfad, fsmode.FILE_MODE)
    return True
"""


def _load_staging_gate():
    path = HOOKS_DIR / "staging_gate.py"
    spec = importlib.util.spec_from_file_location("staging_gate_2630", str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _git(repo: Path, *args):
    subprocess.run(["git", *args], cwd=str(repo), check=True,
                   capture_output=True, text=True)


def _make_repo(tmp_path: Path, before: dict[str, str], after: dict[str, str]) -> Path:
    """Repo mit Basis-Commit (`before`) und Änderungs-Commit (`after`).

    Ein Wert `None` in `after` löscht die Datei.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "AAA.txt").write_text("seed\n")
    for rel, text in before.items():
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "base")
    for rel, text in after.items():
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "change")
    return repo


def _gate_rc(repo: Path, monkeypatch) -> int:
    gate_mod = _load_staging_gate()
    monkeypatch.setattr(gate_mod, "REPO_DIR", repo)
    monkeypatch.delenv("GZ_TELEGRAM_TEST_CHAT_ID", raising=False)
    return gate_mod._telegram_live_gate()


# AC-1 --------------------------------------------------------------------

def test_ac1_go_modus_aenderung_blockt_nicht(tmp_path, monkeypatch):
    """GIVEN nur fsmode-Import + Chmod-Block in telegram_connect.go, ohne Chat-ID
    WHEN das Gate läuft THEN 0."""
    repo = _make_repo(tmp_path, {GO_FILE: GO_BEFORE}, {GO_FILE: GO_MODE_ONLY})
    assert _gate_rc(repo, monkeypatch) == 0


# AC-2 --------------------------------------------------------------------

def test_ac2_modus_plus_logikzeile_bleibt_telegram_scope(tmp_path, monkeypatch):
    """GIVEN Modus-Block + geänderter Rückgabewert THEN 1."""
    mixed = GO_MODE_ONLY.replace("\treturn nil\n}\n", "\treturn errors.New(\"x\")\n}\n")
    assert mixed != GO_MODE_ONLY
    repo = _make_repo(tmp_path, {GO_FILE: GO_BEFORE}, {GO_FILE: mixed})
    assert _gate_rc(repo, monkeypatch) == 1


# AC-3 --------------------------------------------------------------------

def test_ac3_entfernte_logikzeile_bleibt_telegram_scope(tmp_path, monkeypatch):
    """GIVEN Modus-Block + GELÖSCHTE Logikzeile THEN 1."""
    ohne_fehlerpfad = GO_MODE_ONLY.replace(
        "\tif werr != nil {\n\t\treturn werr\n\t}\n", "")
    assert ohne_fehlerpfad != GO_MODE_ONLY
    repo = _make_repo(tmp_path, {GO_FILE: GO_BEFORE}, {GO_FILE: ohne_fehlerpfad})
    assert _gate_rc(repo, monkeypatch) == 1


# AC-4 --------------------------------------------------------------------

def test_ac4_diff_nicht_lesbar_ist_fail_closed(tmp_path, monkeypatch):
    """GIVEN Repo mit nur EINEM Commit (HEAD~1 fehlt) THEN 1."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "internal/handler").mkdir(parents=True)
    (repo / GO_FILE).write_text(GO_MODE_ONLY)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "only")
    assert _gate_rc(repo, monkeypatch) == 1


def test_ac4_hunk_lesen_scheitert_ist_fail_closed(tmp_path, monkeypatch):
    """GIVEN der Namens-Diff klappt, aber der Zeilen-Diff liefert None
    (Helfer wird im Gate-Modul auf Fehler gestellt) THEN 1 — Datei zählt als Telegram."""
    repo = _make_repo(tmp_path, {GO_FILE: GO_BEFORE}, {GO_FILE: GO_MODE_ONLY})
    gate_mod = _load_staging_gate()
    monkeypatch.setattr(gate_mod, "REPO_DIR", repo)
    monkeypatch.delenv("GZ_TELEGRAM_TEST_CHAT_ID", raising=False)
    monkeypatch.setattr(gate_mod._e2e_paths, "_git_diff_lines",
                        lambda *a, **k: None)
    assert gate_mod._telegram_live_gate() == 1


# AC-5 --------------------------------------------------------------------

OTHER_GO = "internal/handler/telegram_webhook.go"


def test_ac5_eine_modusdatei_eine_logikdatei_blockt(tmp_path, monkeypatch):
    other_before = GO_BEFORE.replace("writeToken", "hook")
    other_after = other_before.replace("return nil", "return nil // geändert\n\tpanic(1)")
    repo = _make_repo(
        tmp_path,
        {GO_FILE: GO_BEFORE, OTHER_GO: other_before},
        {GO_FILE: GO_MODE_ONLY, OTHER_GO: other_after},
    )
    assert _gate_rc(repo, monkeypatch) == 1


def test_ac5_beide_rein_modusbedingt_blockt_nicht(tmp_path, monkeypatch):
    other_before = GO_BEFORE.replace("writeToken", "hook")
    other_after = GO_MODE_ONLY.replace("writeToken", "hook")
    repo = _make_repo(
        tmp_path,
        {GO_FILE: GO_BEFORE, OTHER_GO: other_before},
        {GO_FILE: GO_MODE_ONLY, OTHER_GO: other_after},
    )
    assert _gate_rc(repo, monkeypatch) == 0


# AC-6 --------------------------------------------------------------------

def test_ac6_klammerumbau_ohne_fsmode_bleibt_telegram_scope(tmp_path, monkeypatch):
    """Nur Leer-/Klammerzeilen geändert, keine Zeile nennt fsmode THEN 1."""
    umbau = GO_BEFORE.replace("\treturn nil\n}\n", "\treturn nil\n\n}\n")
    assert umbau != GO_BEFORE
    repo = _make_repo(tmp_path, {GO_FILE: GO_BEFORE}, {GO_FILE: umbau})
    assert _gate_rc(repo, monkeypatch) == 1


def test_ac6_neuanlage_telegram_datei_bleibt_telegram_scope(tmp_path, monkeypatch):
    """Neu angelegte Telegram-Datei (auch mit fsmode-Inhalt) THEN 1."""
    repo = _make_repo(tmp_path, {}, {"internal/handler/telegram_x.go": GO_MODE_ONLY})
    assert _gate_rc(repo, monkeypatch) == 1


# AC-7 --------------------------------------------------------------------

def test_ac7_datei_ohne_telegram_im_pfad_blockt_nicht(tmp_path, monkeypatch):
    repo = _make_repo(tmp_path, {"internal/store/store.go": GO_BEFORE},
                      {"internal/store/store.go": GO_BEFORE + "// x\n"})
    assert _gate_rc(repo, monkeypatch) == 0


# AC-8 --------------------------------------------------------------------

def test_ac8_python_modus_aenderung_blockt_nicht(tmp_path, monkeypatch):
    repo = _make_repo(tmp_path, {PY_FILE: PY_BEFORE}, {PY_FILE: PY_MODE_ONLY})
    assert _gate_rc(repo, monkeypatch) == 0


def test_ac8_python_modus_plus_logikzeile_blockt(tmp_path, monkeypatch):
    mixed = PY_MODE_ONLY.replace("    return True\n", "    return False\n")
    repo = _make_repo(tmp_path, {PY_FILE: PY_BEFORE}, {PY_FILE: mixed})
    assert _gate_rc(repo, monkeypatch) == 1


# F001: Logikzeilen, die `fsmode.` bloß ENTHALTEN, sind nicht neutral -------

def _go_variant(old: str, new: str) -> str:
    out = GO_MODE_ONLY.replace(old, new)
    assert out != GO_MODE_ONLY
    return out


def test_f001_go_rueckgabe_mit_fsmode_blockt(tmp_path, monkeypatch):
    mixed = _go_variant("\treturn nil\n}\n", "\treturn fsmode.FileMode\n}\n")
    repo = _make_repo(tmp_path, {GO_FILE: GO_BEFORE}, {GO_FILE: mixed})
    assert _gate_rc(repo, monkeypatch) == 1


def test_f001_go_zuweisung_aufruf_mit_fsmode_blockt(tmp_path, monkeypatch):
    mixed = _go_variant("\treturn nil\n}\n",
                        "\tx := fsmode.Foo() // evil\n\t_ = x\n\treturn nil\n}\n")
    repo = _make_repo(tmp_path, {GO_FILE: GO_BEFORE}, {GO_FILE: mixed})
    assert _gate_rc(repo, monkeypatch) == 1


def test_f001_go_chmod_mit_aufruf_als_ziel_blockt(tmp_path, monkeypatch):
    mixed = _go_variant("os.Chmod(tmpName, fsmode.FileMode)",
                        "os.Chmod(evil(), fsmode.FileMode)")
    repo = _make_repo(tmp_path, {GO_FILE: GO_BEFORE}, {GO_FILE: mixed})
    assert _gate_rc(repo, monkeypatch) == 1


def test_f001_python_chmod_mit_angehaengter_logik_blockt(tmp_path, monkeypatch):
    mixed = PY_MODE_ONLY.replace("os.chmod(pfad, fsmode.FILE_MODE)",
                                 "os.chmod(pfad, fsmode.FILE_MODE); do_evil()")
    assert mixed != PY_MODE_ONLY
    repo = _make_repo(tmp_path, {PY_FILE: PY_BEFORE}, {PY_FILE: mixed})
    assert _gate_rc(repo, monkeypatch) == 1


def test_f001_go_alias_import_und_chmod_deklaration_blockt_nicht(tmp_path, monkeypatch):
    """Positiv: Alias-Import + `werr := os.Chmod(…)` THEN 0."""
    variant = _go_variant('\t"gregor/internal/fsmode"\n',
                          '\tfsmode "gregor/internal/fsmode"\n')
    variant = variant.replace("\t\twerr = os.Chmod(tmpName, fsmode.FileMode)\n",
                              "\t\twerr := os.Chmod(tmpName, fsmode.FileMode)\n")
    assert "werr := os.Chmod" in variant
    repo = _make_repo(tmp_path, {GO_FILE: GO_BEFORE}, {GO_FILE: variant})
    assert _gate_rc(repo, monkeypatch) == 0


# F002: Header-Prüfung in _git_diff_lines ----------------------------------

# Besteht AUSSCHLIESSLICH aus Whitelist-Zeilen — ohne Header-Prüfung wäre
# der Diff „neutral“; nur der Neuanlage-/Lösch-/Rename-Header macht ihn rot.
WHITELIST_ONLY = """// nur Modus
"gregor/internal/fsmode"
werr = os.Chmod(tmpName, fsmode.FileMode)
"""
ONLY_MODE_GO = "internal/handler/telegram_only_mode.go"


def test_f002_neue_whitelist_datei_blockt(tmp_path, monkeypatch):
    repo = _make_repo(tmp_path, {}, {ONLY_MODE_GO: WHITELIST_ONLY})
    assert _gate_rc(repo, monkeypatch) == 1


def test_f002_geloeschte_whitelist_datei_blockt(tmp_path, monkeypatch):
    repo = _make_repo(tmp_path, {ONLY_MODE_GO: WHITELIST_ONLY}, {"AAA.txt": "x\n"})
    (repo / ONLY_MODE_GO).unlink()
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "delete")
    assert _gate_rc(repo, monkeypatch) == 1


def test_f002_umbenannte_whitelist_datei_blockt(tmp_path, monkeypatch):
    old = "internal/handler/telegram_a.go"
    repo = _make_repo(tmp_path, {old: WHITELIST_ONLY}, {"AAA.txt": "x\n"})
    _git(repo, "mv", old, "internal/handler/telegram_b.go")
    _git(repo, "commit", "-m", "rename")
    assert _gate_rc(repo, monkeypatch) == 1


# F-R2-1: if-Guard nur werr/err und nur mit Chmod; entfernte Klammern zählen --

GO_IMPORT_ONLY = GO_BEFORE.replace('\t"os"\n', '\t"os"\n\n\t"gregor/internal/fsmode"\n')


def test_fr2_import_plus_fremder_if_guard_ohne_chmod_blockt(tmp_path, monkeypatch):
    """Import + `if disabled == nil {` + `}` ändert den Kontrollfluss THEN 1."""
    mixed = GO_IMPORT_ONLY.replace(
        "\treturn nil\n}\n", "\tif disabled == nil {\n\t}\n\treturn nil\n}\n")
    assert mixed != GO_IMPORT_ONLY
    repo = _make_repo(tmp_path, {GO_FILE: GO_BEFORE}, {GO_FILE: mixed})
    assert _gate_rc(repo, monkeypatch) == 1


def test_fr2_werr_guard_ohne_chmod_blockt(tmp_path, monkeypatch):
    """Import + `if werr == nil {` + `}` ohne Chmod-Zeile THEN 1."""
    mixed = GO_IMPORT_ONLY.replace(
        "\treturn nil\n}\n", "\tif werr == nil {\n\t}\n\treturn nil\n}\n")
    assert mixed != GO_IMPORT_ONLY
    repo = _make_repo(tmp_path, {GO_FILE: GO_BEFORE}, {GO_FILE: mixed})
    assert _gate_rc(repo, monkeypatch) == 1


def test_fr2_if_guard_mit_aufruf_blockt(tmp_path, monkeypatch):
    mixed = _go_variant("\tif werr == nil {\n", "\tif send() == nil {\n")
    repo = _make_repo(tmp_path, {GO_FILE: GO_BEFORE}, {GO_FILE: mixed})
    assert _gate_rc(repo, monkeypatch) == 1


def test_fr2_if_guard_mit_init_statement_blockt(tmp_path, monkeypatch):
    mixed = _go_variant("\tif werr == nil {\n", "\tif x := f(); x == nil {\n")
    repo = _make_repo(tmp_path, {GO_FILE: GO_BEFORE}, {GO_FILE: mixed})
    assert _gate_rc(repo, monkeypatch) == 1


GO_WITH_BLOCK = """package handler

import (
\t"os"
)

func writeToken(tmpName string, data []byte) error {
\tif len(data) == 0 {
\t\treturn nil
\t}
\treturn os.WriteFile(tmpName, data, 0o600)
}
"""


def test_fr2_import_plus_entfernte_klammer_blockt(tmp_path, monkeypatch):
    """Import + GELÖSCHTE `}`-Zeile verschiebt den Kontrollfluss THEN 1."""
    after = GO_WITH_BLOCK.replace(
        '\t"os"\n', '\t"os"\n\n\t"gregor/internal/fsmode"\n').replace(
        "\t\treturn nil\n\t}\n", "\t\treturn nil\n")
    assert "\t}\n" not in after
    repo = _make_repo(tmp_path, {GO_FILE: GO_WITH_BLOCK}, {GO_FILE: after})
    assert _gate_rc(repo, monkeypatch) == 1


def test_fr2_python_import_mit_angehaengtem_aufruf_blockt(tmp_path, monkeypatch):
    mixed = PY_MODE_ONLY.replace("from src.app import fsmode",
                                 "import fsmode; send()")
    assert mixed != PY_MODE_ONLY
    repo = _make_repo(tmp_path, {PY_FILE: PY_BEFORE}, {PY_FILE: mixed})
    assert _gate_rc(repo, monkeypatch) == 1


def test_fr2_go_string_mit_fsmode_und_aufruf_blockt(tmp_path, monkeypatch):
    mixed = _go_variant("\t\"gregor/internal/fsmode\"\n",
                        "\t\"gregor/internal/fsmode\"\n\t\"fsmode: \"+send()\n")
    repo = _make_repo(tmp_path, {GO_FILE: GO_BEFORE}, {GO_FILE: mixed})
    assert _gate_rc(repo, monkeypatch) == 1


def test_fr2_kommentar_plus_modus_blockt_nicht(tmp_path, monkeypatch):
    """Geänderte Kommentarzeile (entfernt + hinzugefügt) + Import + Chmod THEN 0."""
    before = GO_BEFORE.replace("\treturn nil\n}\n", "\t// alt\n\treturn nil\n}\n")
    after = GO_MODE_ONLY.replace("\treturn nil\n}\n",
                                 "\t// Modus gesetzt (#2624)\n\treturn nil\n}\n")
    assert before != GO_BEFORE and after != GO_MODE_ONLY
    repo = _make_repo(tmp_path, {GO_FILE: before}, {GO_FILE: after})
    assert _gate_rc(repo, monkeypatch) == 0


def _added_diff_lines(repo: Path) -> list[str]:
    out = subprocess.run(["git", "diff", "HEAD~1", "HEAD", "--", GO_FILE],
                         cwd=str(repo), check=True, capture_output=True, text=True)
    return [line[1:].strip() for line in out.stdout.splitlines()
            if line.startswith("+") and not line.startswith("+++")]


# F-R3-2: der if-Guard ist nur mit werr/err neutral — auch MIT Chmod-Zeile ---

def test_fr3_fremder_if_guard_mit_chmod_blockt(tmp_path, monkeypatch):
    """Import + `if disabled == nil {` + Chmod + `}` THEN 1 — die vorhandene
    Chmod-Zeile darf einen Guard mit fremdem Bezeichner nicht neutral machen."""
    mixed = _go_variant("\tif werr == nil {\n", "\tif disabled == nil {\n")
    repo = _make_repo(tmp_path, {GO_FILE: GO_BEFORE}, {GO_FILE: mixed})
    added = _added_diff_lines(repo)
    assert "werr = os.Chmod(tmpName, fsmode.FileMode)" in added
    assert "if disabled == nil {" in added
    assert _gate_rc(repo, monkeypatch) == 1


def test_fr3_err_guard_mit_chmod_blockt_nicht(tmp_path, monkeypatch):
    """Import + `if err == nil {` + Chmod + `}` (alles Whitelist) THEN 0."""
    variant = _go_variant("\tif werr == nil {\n", "\tif err == nil {\n")
    repo = _make_repo(tmp_path, {GO_FILE: GO_BEFORE}, {GO_FILE: variant})
    added = _added_diff_lines(repo)
    assert "werr = os.Chmod(tmpName, fsmode.FileMode)" in added
    assert "if err == nil {" in added
    assert _gate_rc(repo, monkeypatch) == 0


def test_fr2_nur_kommentar_ohne_fsmode_blockt(tmp_path, monkeypatch):
    after = GO_BEFORE.replace("\treturn nil\n}\n", "\t// nur Kommentar\n\treturn nil\n}\n")
    assert after != GO_BEFORE
    repo = _make_repo(tmp_path, {GO_FILE: GO_BEFORE}, {GO_FILE: after})
    assert _gate_rc(repo, monkeypatch) == 1
