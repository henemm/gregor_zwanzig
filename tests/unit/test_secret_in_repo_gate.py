"""Verhaltensnachweis fuer das Commit-Gate „Secret-in-Repo-Sperre" (#1537 Scheibe 1).

Eine zum Commit vorgemerkte Datei, die den ausgeschriebenen Wert eines Geheimnisses aus
der lokalen `.env` enthaelt (Schluessel endet auf `_PASS`/`_TOKEN`/`_KEY`/`_SECRET`, Wert
mind. 10 Zeichen), blockiert den Commit. Der Wert selbst darf NIE in der Blockade-Meldung
auftauchen — nur Dateiname und Schluesselname.

Kern-Schicht, deterministisch: jeder Fall baut ein eigenes Wegwerf-Repository mit einer
SYNTHETISCHEN `.env` (nie die echte Projekt-`.env`) und ruft den Waechter als echten
Unterprozess auf — kein Mock, kein patch(). Damit ist die Suite hermetisch: sie liest nie
die reale `.env` des Ausfuehrungsortes (genau das machte PR #1534 auf CI rot).

Pfadregel #1409: Der Pruefling wird relativ zu DIESER Datei aufgeloest, damit der Test aus
einem Worktree den Worktree-Stand prueft und nicht die Hauptrepo-Kopie.
"""
from __future__ import annotations

import importlib.util as _gz_ilu
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
HOOKS = REPO / ".claude" / "hooks"
# Ueberschreibbar fuer die Mutationsprobe (#1537 Runde 3): der Adversary mutiert
# eine EXTERNE Kopie im Scratchpad statt der geschuetzten Originaldatei — dafuer
# muss der Pruefling-Pfad umstellbar sein. Ohne die Variable unveraendertes
# Verhalten: der echte Hook im Repo.
GATE = Path(os.environ.get("GZ_SECRET_GATE_PATH", "")) if os.environ.get("GZ_SECRET_GATE_PATH") \
    else HOOKS / "secret_in_repo_gate.py"

# Plugin-Sonde (Muster aus tests/tdd/test_pendant_gate.py): der Waechter laeuft ueber
# hook_utils, einen Shim auf das installierte agent-os-openspec-Plugin. Ohne Plugin
# (CI-Runner ohne Plugin-Installation) meldet das Gate fail-open "gestoert ... UNGEPRUEFT
# durchgelassen" fuer JEDEN Commit — die Block-Tests waeren dann strukturell rot. Sauber
# ueberspringen statt rot; auf dem Server (Plugin vorhanden) laeuft die Suite vollstaendig.
_gz_hook_utils = HOOKS / "hook_utils.py"
try:
    _gz_spec = _gz_ilu.spec_from_file_location("_gz_hook_utils_probe", _gz_hook_utils)
    _gz_mod = _gz_ilu.module_from_spec(_gz_spec)
    _gz_spec.loader.exec_module(_gz_mod)
except ImportError as _gz_exc:
    pytest.skip(
        f"agent-os-openspec-Plugin fehlt ({_gz_exc}) — Hook-Suite braucht die "
        "installierten Server-Hooks (#1196)",
        allow_module_level=True,
    )

# Synthetische Geheimnisse — bewusst NICHT aus der echten Projekt-.env. Frei erfunden,
# Kollision mit einem echten Zugangsdatum ist praktisch ausgeschlossen.
GEHEIM_SCHLUESSEL = "GZ_TEST_DUMMY_TOKEN"
GEHEIM_WERT = "unit-test-fixture-secret-9f8e7d6c"  # > 10 Zeichen
KURZER_SCHLUESSEL = "GZ_SHORT_KEY"
KURZER_WERT = "1234567"  # < 10 Zeichen -> darf NIE als Geheimnis gelten
HARMLOSER_SCHLUESSEL = "GZ_SMTP_HOST"
HARMLOSER_WERT = "smtp.example.invalid"  # Suffix passt zu keiner der vier Endungen


def _env_text() -> str:
    return (
        f"{GEHEIM_SCHLUESSEL}={GEHEIM_WERT}\n"
        f"{KURZER_SCHLUESSEL}={KURZER_WERT}\n"
        f"{HARMLOSER_SCHLUESSEL}={HARMLOSER_WERT}\n"
    )


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def _wegwerf_repo(tmp_path: Path, mit_env: bool = True) -> Path:
    """Repo mit committetem Ausgangsstand und (optional) lokaler `.env`.

    Die `.env` wird bewusst NICHT vorgemerkt/committet — genau wie im echten Projekt ist
    sie eine lokale, gitignorierte Datei, die der Waechter direkt von der Platte liest.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("Ausgangsstand\n")
    _git(repo.parent, "init", "-q", str(repo))
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "Ausgangsstand")
    if mit_env:
        (repo / ".env").write_text(_env_text())
    return repo


def _stage(repo: Path, pfad: str, inhalt: str) -> None:
    ziel = repo / pfad
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(inhalt)
    _git(repo, "add", "--", pfad)


def _hook(repo: Path, kommando: str = "git commit -m 'x'",
          cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Ruft den Waechter wie die Hook-Schicht auf: stdin-JSON, cwd = Wegwerf-Repo.

    `cwd` erlaubt, die Prozess-cwd des Hooks vom Repo zu ENTKOPPELN — genau der
    Fall, den F001 prueft: der Hook laeuft in `haupt`, das Kommando zielt per
    `-C <ziel>`/`--git-dir`/`--work-tree` auf ein ANDERES Repo.
    """
    eingabe = json.dumps({"tool_name": "Bash", "tool_input": {"command": kommando}})
    env = dict(os.environ)
    env.pop("GIT_DIR", None)
    env.pop("GIT_WORK_TREE", None)
    return subprocess.run(
        [sys.executable, str(GATE)], input=eingabe, cwd=str(cwd or repo),
        capture_output=True, text=True, timeout=60, env=env,
    )


def _text(r: subprocess.CompletedProcess) -> str:
    return r.stderr + r.stdout


# --------------------------------------------------------------------------------- Faelle


def test_gate_blocks_staged_file_with_env_secret(tmp_path):
    """(1) Vorgemerkte Datei mit echtem .env-Wert -> Gate blockiert.

    GIVEN eine .env mit einem Geheimnis (Schluessel endet auf _TOKEN, Wert >= 10 Zeichen)
    WHEN eine neue Datei mit genau diesem Wert vorgemerkt und committet wird
    THEN blockiert das Gate (Exit 2) und nennt die betroffene Datei.
    """
    repo = _wegwerf_repo(tmp_path)
    _stage(repo, "config/leaked.txt", f"token = {GEHEIM_WERT}\n")
    r = _hook(repo)
    ausgabe = _text(r)
    assert r.returncode == 2, f"Erwartete Blockade (Exit 2), bekam {r.returncode}: {ausgabe}"
    assert "leaked.txt" in ausgabe, f"Meldung nennt nicht die betroffene Datei: {ausgabe}"
    assert GEHEIM_SCHLUESSEL in ausgabe, f"Meldung nennt nicht den Schluesselnamen: {ausgabe}"


def test_gate_allows_harmless_staged_file(tmp_path):
    """(2) Harmlose Datei ohne Geheimnis -> Gate laesst durch.

    GIVEN eine .env mit einem Geheimnis
    WHEN eine neue Datei vorgemerkt wird, die diesen Wert NICHT enthaelt
    THEN laesst das Gate den Commit durch (Exit 0).
    """
    repo = _wegwerf_repo(tmp_path)
    _stage(repo, "docs/notes.md", "Nur ganz normaler Text, kein Geheimnis.\n")
    r = _hook(repo)
    assert r.returncode == 0, f"Harmlose Datei wurde blockiert: {_text(r)}"


def test_block_message_never_contains_the_secret_value(tmp_path):
    """(3) Blockade-Meldung enthaelt den Schluesselnamen, NIE den Wert.

    Wichtigste Einzelanforderung des Auftrags: der Wert selbst darf unter keinen
    Umstaenden in Log-/Fehlermeldungen erscheinen.
    """
    repo = _wegwerf_repo(tmp_path)
    _stage(repo, "config/leaked.txt", f"token = {GEHEIM_WERT}\n")
    r = _hook(repo)
    ausgabe = _text(r)
    assert r.returncode == 2, f"Erwartete Blockade, bekam {r.returncode}: {ausgabe}"
    assert GEHEIM_SCHLUESSEL in ausgabe
    assert GEHEIM_WERT not in ausgabe, (
        "Der Geheimniswert selbst ist in der Ausgabe aufgetaucht — das ist die "
        "wichtigste verbotene Wirkung dieses Gates."
    )


def test_gate_allows_when_env_missing(tmp_path):
    """(4a) Keine .env vorhanden -> Gate stoert sich selbst, laesst durch und sagt das.

    GIVEN kein .env im Repo-Wurzelverzeichnis
    WHEN eine Datei mit einem geheimnis-aehnlichen Text vorgemerkt wird
    THEN laesst das Gate durch (Exit 0) — es hat nichts, wogegen es pruefen koennte —
         und die Meldung erwaehnt die .env als Ursache der eigenen Stoerung.
    """
    repo = _wegwerf_repo(tmp_path, mit_env=False)
    _stage(repo, "config/leaked.txt", f"token = {GEHEIM_WERT}\n")
    r = _hook(repo)
    ausgabe = _text(r)
    assert r.returncode == 0, f"Fehlende .env haette NIE blockieren duerfen: {ausgabe}"
    assert ".env nicht lesbar" in ausgabe.lower(), (
        f"Eigene Stoerung wird nicht mit vollstaendiger Ursache gemeldet: {ausgabe}"
    )


def test_gate_allows_when_env_unreadable(tmp_path):
    """(4b) .env nicht als Datei lesbar (hier: ein Verzeichnis gleichen Namens)
    -> Gate laesst durch und meldet die Stoerung.

    Ein Verzeichnis statt einer Datei ist eine plattformunabhaengige, nicht von
    Dateirechten abhaengige Art, einen OSError beim Lesen zu erzwingen (root-Prozesse
    ignorieren `chmod 000`, ein IsADirectoryError trifft aber jeden).
    """
    repo = _wegwerf_repo(tmp_path, mit_env=False)
    (repo / ".env").mkdir()
    _stage(repo, "config/leaked.txt", f"token = {GEHEIM_WERT}\n")
    r = _hook(repo)
    ausgabe = _text(r)
    assert r.returncode == 0, f"Unlesbare .env haette NIE blockieren duerfen: {ausgabe}"
    assert ".env nicht lesbar" in ausgabe.lower()


def test_gate_ignores_short_values_and_non_matching_keys(tmp_path):
    """Laengen- und Schluessel-Filter greifen: kurze Werte und Schluessel ohne die
    gesuchten Endungen sind KEINE Geheimnisse — sonst traefe z.B. der Projektname
    ueberall.
    """
    repo = _wegwerf_repo(tmp_path)
    _stage(repo, "config/notes.txt", f"kurz={KURZER_WERT} host={HARMLOSER_WERT}\n")
    r = _hook(repo)
    assert r.returncode == 0, f"Kurzer/nicht passender Wert haette nicht blocken duerfen: {_text(r)}"


def test_gate_skips_binary_files(tmp_path):
    """Binaerdateien werden uebersprungen — auch wenn sie das Geheimnis als Bytes
    enthalten, kann/soll das Gate sie nicht sinnvoll als Text durchsuchen.
    """
    repo = _wegwerf_repo(tmp_path)
    ziel = repo / "assets/blob.bin"
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_bytes(b"\x00\x01\x02" + GEHEIM_WERT.encode() + b"\x00\x03")
    _git(repo, "add", "--", "assets/blob.bin")
    r = _hook(repo)
    assert r.returncode == 0, f"Binaerdatei haette uebersprungen werden muessen: {_text(r)}"


# --------------------------------------------------- F001 Runde 3: Sicherheitslage
#
# Drei Ausgaenge (Tech-Lead-Entscheid, siehe Kopf-Docstring des Prueflings):
#   sicher   -> geprueft (Exit 0 oder 2, je nach Fund)
#   unsicher -> BLOCKIERT (Exit 2, Marker UNSICHER_MARKER)
#   gestoert -> durchgelassen (Exit 0, eigene Stoerung)
#
# F007-Lehre (Runde 3 Adversary-Fund): Zusicherungen NIE gegen einen bloss
# zufaellig im temporaeren Pfad vorkommenden Teilstring pruefen (der von pytest
# erzeugte tmp_path-Name enthaelt den Testnamen, z.B. "..._on_cd0" — ein reiner
# `"cd" in ausgabe`-Test war dadurch unabhaengig vom tatsaechlichen Verhalten
# gruen). Jede Zusicherung hier prueft stattdessen einen FESTEN Marker aus dem
# Pruefling (SECRET_MARKER/UNSICHER_MARKER) UND einen vollstaendigen, nur vom
# Pruefling erzeugten Formulierungs-Ausschnitt.

SECRET_MARKER = "SECRET-IN-REPO-SPERRE"
UNSICHER_MARKER = "ZIEL-NICHT-SICHER-BESTIMMBAR"


def _zweitrepo(tmp_path: Path, name: str, mit_geheimnis: bool = True) -> Path:
    """Ein zweites, eigenstaendiges Wegwerf-Repo (eigener Ordnername noetig,
    `_wegwerf_repo` legt sein Repo fest unter `tmp_path/'repo'` an)."""
    repo = tmp_path / name
    repo.mkdir()
    (repo / "README.md").write_text("Ausgangsstand\n")
    _git(repo.parent, "init", "-q", str(repo))
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "Ausgangsstand")
    if mit_geheimnis:
        (repo / ".env").write_text(_env_text())
        _stage(repo, "config/leaked.txt", f"token = {GEHEIM_WERT}\n")
    return repo


def test_gate_checks_resolved_target_with_dash_c_flag(tmp_path):
    """(1/5 Umlenkungswege) `git -C <ziel> commit` loest SAUBER auf -> Zeile 1
    der Tabelle: dort wird geprueft (nicht blockiert, nicht lautlos durch).

    GIVEN `haupt` (Prozess-cwd, KEINE .env) und `ziel` (eigene .env mit
          Geheimnis, vorgemerkte Datei mit genau diesem Wert)
    WHEN  `git -C <ziel> commit` aus `haupt` heraus aufgerufen wird
    THEN  blockiert das Gate mit SECRET_MARKER und nennt die Datei aus `ziel`.
    """
    haupt = _wegwerf_repo(tmp_path, mit_env=False)
    ziel = _zweitrepo(tmp_path, "ziel_repo")
    r = _hook(haupt, kommando=f"git -C {ziel} commit -m 'x'", cwd=haupt)
    ausgabe = _text(r)
    assert r.returncode == 2, f"Sauber aufloesbares -C haette geprueft werden muessen: {ausgabe}"
    assert SECRET_MARKER in ausgabe, f"Kein Fund-Marker in der Meldung: {ausgabe}"
    assert "leaked.txt" in ausgabe and GEHEIM_SCHLUESSEL in ausgabe


def test_gate_checks_resolved_target_with_git_dir_and_work_tree_flags(tmp_path):
    """(2/5 Umlenkungswege) `git --git-dir=X --work-tree=Y commit` (getrennte
    Flags, sauber aufloesbar) -> ebenfalls Zeile 1: geprueft."""
    haupt = _wegwerf_repo(tmp_path, mit_env=False)
    ziel = _zweitrepo(tmp_path, "ziel_repo")
    kommando = f"git --git-dir={ziel}/.git --work-tree={ziel} commit -m 'x'"
    r = _hook(haupt, kommando=kommando, cwd=haupt)
    ausgabe = _text(r)
    assert r.returncode == 2, f"Sauber aufloesbares --git-dir/--work-tree haette geprueft werden muessen: {ausgabe}"
    assert SECRET_MARKER in ausgabe, f"Kein Fund-Marker in der Meldung: {ausgabe}"
    assert "leaked.txt" in ausgabe and GEHEIM_SCHLUESSEL in ausgabe


def test_gate_blocks_cd_redirect(tmp_path):
    """(3/5 Umlenkungswege) `cd <ziel> && git commit` traegt kein git-Vor-Options-
    Anzeichen -> Zeile 2: BLOCKIERT, nicht lautlos durchgelassen."""
    haupt = _wegwerf_repo(tmp_path, mit_env=False)
    ziel = _zweitrepo(tmp_path, "ziel_repo")
    r = _hook(haupt, kommando=f"cd {ziel} && git commit -m 'x'", cwd=haupt)
    ausgabe = _text(r)
    assert r.returncode == 2, f"cd-Umlenkung haette blockieren muessen, nicht durchlassen: {ausgabe}"
    assert UNSICHER_MARKER in ausgabe
    assert "enthaelt 'cd' vor dem Commit" in ausgabe, f"Grund nicht genannt: {ausgabe}"
    assert "-C <pfad> commit" in ausgabe, f"Erlaubter Weg nicht genannt: {ausgabe}"


def test_gate_blocks_git_dir_env_assignment(tmp_path):
    """(4/5 Umlenkungswege) `GIT_DIR=... GIT_WORK_TREE=... git commit` als
    Umgebungszuweisung -> Zeile 2: BLOCKIERT."""
    haupt = _wegwerf_repo(tmp_path, mit_env=False)
    ziel = _zweitrepo(tmp_path, "ziel_repo")
    kommando = f"GIT_DIR={ziel}/.git GIT_WORK_TREE={ziel} git commit -m 'x'"
    r = _hook(haupt, kommando=kommando, cwd=haupt)
    ausgabe = _text(r)
    assert r.returncode == 2, f"GIT_DIR=/GIT_WORK_TREE= haette blockieren muessen: {ausgabe}"
    assert UNSICHER_MARKER in ausgabe
    assert "GIT_DIR/GIT_WORK_TREE als Umgebungszuweisung" in ausgabe, f"Grund nicht genannt: {ausgabe}"


def test_gate_blocks_cd_redirect_in_subshell(tmp_path):
    """(5/5 Umlenkungswege) `(cd <ziel> && git commit)` in einer Subshell ->
    Zeile 2: BLOCKIERT (Klammern sind fuer die Zerlegung Trenner wie `&&`)."""
    haupt = _wegwerf_repo(tmp_path, mit_env=False)
    ziel = _zweitrepo(tmp_path, "ziel_repo")
    r = _hook(haupt, kommando=f"(cd {ziel} && git commit -m 'x')", cwd=haupt)
    ausgabe = _text(r)
    assert r.returncode == 2, f"cd-Umlenkung in Subshell haette blockieren muessen: {ausgabe}"
    assert UNSICHER_MARKER in ausgabe
    assert "enthaelt 'cd' vor dem Commit" in ausgabe, f"Grund nicht genannt: {ausgabe}"


@pytest.mark.parametrize("wrapper", [
    "timeout 5",
    "flock /tmp/irgendeine.lock",
    "xargs -I{}",
    "nice -n 10",
])
def test_gate_blocks_commit_behind_unrecognized_wrapper(tmp_path, wrapper):
    """Unbekanntes Hilfsprogramm vor `git commit` -> Zeile 2: BLOCKIERT.

    `nice` steht absichtlich mit einem eigenen Argument (`-n 10`) in der Liste:
    `nice` ALLEIN ist ein bekannter transparenter Praefix (sicher), `nice -n 10`
    ist es nicht (das Token direkt vor `git` ist dann `10`, kein bekannter
    Praefix mehr) — die Unterscheidung ist beabsichtigt scharf.
    """
    repo = _wegwerf_repo(tmp_path)
    _stage(repo, "config/leaked.txt", f"token = {GEHEIM_WERT}\n")
    r = _hook(repo, kommando=f"{wrapper} git commit -m 'x'")
    ausgabe = _text(r)
    assert r.returncode == 2, f"'{wrapper} git commit' haette blockieren muessen: {ausgabe}"
    assert UNSICHER_MARKER in ausgabe
    assert "nicht erkannten Hilfsprogramm" in ausgabe, f"Grund nicht genannt: {ausgabe}"


def test_gate_blocks_commit_behind_loop(tmp_path):
    """Schleife vor `git commit` -> Zeile 2: BLOCKIERT."""
    repo = _wegwerf_repo(tmp_path)
    _stage(repo, "config/leaked.txt", f"token = {GEHEIM_WERT}\n")
    r = _hook(repo, kommando="for i in 1; do git commit -m 'x'; done")
    ausgabe = _text(r)
    assert r.returncode == 2, f"Commit in einer Schleife haette blockieren muessen: {ausgabe}"
    assert UNSICHER_MARKER in ausgabe


def test_gate_blocks_commit_inside_sh_dash_c(tmp_path):
    """`sh -c "git commit -m x"` -> Zeile 2: BLOCKIERT (verschachtelte Shell)."""
    repo = _wegwerf_repo(tmp_path)
    _stage(repo, "config/leaked.txt", f"token = {GEHEIM_WERT}\n")
    r = _hook(repo, kommando='sh -c "git commit -m x"')
    ausgabe = _text(r)
    assert r.returncode == 2, f"'sh -c \"git commit\"' haette blockieren muessen: {ausgabe}"
    assert UNSICHER_MARKER in ausgabe
    assert "verschachtelten Shell" in ausgabe, f"Grund nicht genannt: {ausgabe}"


def test_gate_blocks_commit_inside_eval(tmp_path):
    """`eval "git commit -m x"` -> Zeile 2: BLOCKIERT (verschachtelter Aufruf)."""
    repo = _wegwerf_repo(tmp_path)
    _stage(repo, "config/leaked.txt", f"token = {GEHEIM_WERT}\n")
    r = _hook(repo, kommando='eval "git commit -m x"')
    ausgabe = _text(r)
    assert r.returncode == 2, f"'eval \"git commit\"' haette blockieren muessen: {ausgabe}"
    assert UNSICHER_MARKER in ausgabe
    assert "eval" in ausgabe, f"Grund nicht genannt: {ausgabe}"


def test_gate_blocks_unresolvable_dash_c_target(tmp_path):
    """`-C` auf einen nicht existierenden Pfad loest NICHT sauber auf -> Zeile 2:
    BLOCKIERT (nicht Zeile 3 'eigene Stoerung', da `git rev-parse` selbst
    laeuft und lediglich einen Fehler meldet)."""
    haupt = _wegwerf_repo(tmp_path, mit_env=False)
    r = _hook(haupt, kommando="git -C /pfad/der/garantiert/nicht/existiert commit -m 'x'", cwd=haupt)
    ausgabe = _text(r)
    assert r.returncode == 2, f"Nicht aufloesbares -C haette blockieren muessen, nicht durchlassen: {ausgabe}"
    assert UNSICHER_MARKER in ausgabe
    assert "loest nicht sauber auf" in ausgabe, f"Grund nicht genannt: {ausgabe}"


def test_gate_does_not_block_mere_mention_of_commit(tmp_path):
    """Gegenfall: die Woerter "git commit" kommen nur als Text vor (z.B. in
    einem `--grep`-Suchbegriff) — das ist KEIN Commit-Aufruf und darf nicht
    blockieren, obwohl eine vorgemerkte Datei das Geheimnis enthaelt. Ein
    naiver Teilstring-Vergleich wuerde hier faelschlich blockieren.
    """
    repo = _wegwerf_repo(tmp_path)
    _stage(repo, "config/leaked.txt", f"token = {GEHEIM_WERT}\n")
    r = _hook(repo, kommando='git log --grep="git commit" -1')
    ausgabe = _text(r)
    assert r.returncode == 0, f"Blosse Erwaehnung haette nicht blockieren duerfen: {ausgabe}"
    assert SECRET_MARKER not in ausgabe and UNSICHER_MARKER not in ausgabe


# --------------------------------------------------------- F002: Aufrufform-Netz


def test_gate_detects_commit_via_dash_capital_c_flag_same_repo(tmp_path):
    """(F002) `git -C <repo> commit` muss erkannt werden — ein reiner
    Teilstring-Vergleich auf "git commit" findet diese Form NICHT (dazwischen
    steht `-C <repo>`)."""
    repo = _wegwerf_repo(tmp_path)
    _stage(repo, "config/leaked.txt", f"token = {GEHEIM_WERT}\n")
    r = _hook(repo, kommando=f"git -C {repo} commit -m 'x'")
    ausgabe = _text(r)
    assert r.returncode == 2, f"'git -C <repo> commit' wurde nicht erkannt: {ausgabe}"
    assert SECRET_MARKER in ausgabe and GEHEIM_SCHLUESSEL in ausgabe


def test_gate_detects_commit_via_dash_c_option(tmp_path):
    """(F002) `git -c user.name=x commit` — Teilstring "git commit" fehlt
    (dazwischen steht `-c user.name=x`)."""
    repo = _wegwerf_repo(tmp_path)
    _stage(repo, "config/leaked.txt", f"token = {GEHEIM_WERT}\n")
    r = _hook(repo, kommando="git -c user.name=x commit -m 'x'")
    ausgabe = _text(r)
    assert r.returncode == 2, f"'git -c k=v commit' wurde nicht erkannt: {ausgabe}"
    assert SECRET_MARKER in ausgabe and GEHEIM_SCHLUESSEL in ausgabe


def test_gate_detects_commit_via_no_pager_flag(tmp_path):
    """(F002) `git --no-pager commit` — Teilstring "git commit" fehlt
    (dazwischen steht `--no-pager`)."""
    repo = _wegwerf_repo(tmp_path)
    _stage(repo, "config/leaked.txt", f"token = {GEHEIM_WERT}\n")
    r = _hook(repo, kommando="git --no-pager commit -m 'x'")
    ausgabe = _text(r)
    assert r.returncode == 2, f"'git --no-pager commit' wurde nicht erkannt: {ausgabe}"
    assert SECRET_MARKER in ausgabe and GEHEIM_SCHLUESSEL in ausgabe
