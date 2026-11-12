"""Verhaltensnachweis fuer das Commit-Gate „Tests der beruehrten Dateien" (#1481 A).

Spec: docs/specs/modules/feat_1481a_touched_tests_gate.md

Kern-Schicht, deterministisch: jeder Fall baut ein **Wegwerf-Repository** mit echten
Dateien und ruft den Hook als echten Unterprozess auf — kein Mock, kein patch(), kein
Netz. Geprueft wird der Exit-Code (2 = blockiert, 0 = durchgelassen) und die Meldung.

Pfadregel #1409: Der Prueflig wird relativ zu DIESER Datei aufgeloest, damit der Test aus
einem Worktree den Worktree-Stand prueft und nicht die Hauptrepo-Kopie.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
GATE = REPO / ".claude" / "hooks" / "touched_tests_gate.py"


# ---------------------------------------------------------------------------
# Wegwerf-Repository
# ---------------------------------------------------------------------------

def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True,
                   capture_output=True, text=True)


HEIL = "def verdopple(x):\n    return x * 2\n"
KAPUTT = "def verdopple(x):\n    return x * 3\n"


def _wegwerf_repo(tmp_path: Path, quelle: str, test: str, basis: str = HEIL) -> Path:
    """Repo mit committetem Ausgangsstand (`basis`) und gestagter Aenderung (`quelle`).

    Der Ausgangsstand ist nicht Beiwerk: Das Gate misst den Vorzustand an einem
    Wegwerf-Abzug des letzten Commits (statt einer pflegbaren — und damit faelschbaren —
    Liste bekannter Fehlschlaege). Ohne echten Commit gaebe es nichts zu messen.

    Die Testdatei liegt unter `tests/unit/` — das bildet die echte Struktur ab: Das Gate
    prueft ausschliesslich die versandfreie Kern-Schicht, nicht `tests/tdd/` (dort kann ein
    Testlauf echte Nachrichten verschicken, #1477).
    """
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "tests" / "unit").mkdir(parents=True)
    (repo / "src" / "rechner.py").write_text(basis)
    (repo / "tests" / "unit" / "test_rechner.py").write_text(test)
    _git(repo.parent, "init", "-q", str(repo))
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "Ausgangsstand")
    (repo / "src" / "rechner.py").write_text(quelle)
    _git(repo, "add", "-A")
    return repo


GRUENER_TEST = (
    "import sys, pathlib\n"
    "sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / 'src'))\n"
    "from rechner import verdopple\n"
    "def test_verdopple():\n"
    "    assert verdopple(2) == 4\n"
)


def _hook(repo: Path, kommando: str = "git commit -m 'x'") -> subprocess.CompletedProcess:
    """Ruft das Gate wie die Hook-Schicht auf: stdin-JSON, cwd = Wegwerf-Repo."""
    eingabe = json.dumps({"tool_input": {"command": kommando}})
    umgebung = {**os.environ, "GIT_DIR": "", "GIT_WORK_TREE": ""}
    umgebung.pop("GIT_DIR", None)
    umgebung.pop("GIT_WORK_TREE", None)
    # #2503: Die Phase des aktiven Workflows entscheidet mit. Sie darf nur aus dem
    # Wegwerf-Repo kommen — nie aus der Sitzung, die diesen Test gerade ausfuehrt.
    umgebung.pop("CLAUDE_PROJECT_DIR", None)
    umgebung.pop("OPENSPEC_ACTIVE_WORKFLOW", None)
    return subprocess.run(
        [sys.executable, str(GATE)], input=eingabe, cwd=str(repo),
        capture_output=True, text=True, timeout=180, env=umgebung,
    )


# ---------------------------------------------------------------------------
# AC-1 / AC-2: die Grundzusicherung
# ---------------------------------------------------------------------------

def test_ac1_roter_test_blockiert_den_commit(tmp_path):
    """Die Aenderung macht den zugehoerigen Test rot -> Commit wird abgebrochen."""
    repo = _wegwerf_repo(tmp_path, "def verdopple(x):\n    return x * 3\n", GRUENER_TEST)
    r = _hook(repo)
    assert r.returncode == 2, f"Gate haette blockieren muessen (Exit {r.returncode})\n{r.stderr}"
    assert "test_verdopple" in r.stderr, (
        "Die Meldung muss den fehlgeschlagenen Test namentlich nennen (AC-1):\n" + r.stderr
    )


def test_ac2_gruene_tests_lassen_durch(tmp_path):
    """Alles gruen -> der Commit laeuft ohne Zutun durch."""
    repo = _wegwerf_repo(tmp_path, HEIL + "# echte Aenderung\n", GRUENER_TEST)
    r = _hook(repo)
    assert r.returncode == 0, f"Gate haette durchlassen muessen (Exit {r.returncode})\n{r.stderr}"


# ---------------------------------------------------------------------------
# AC-3 / AC-4: Ratsche gegen den Rot-Bestand
# ---------------------------------------------------------------------------

def test_ac3_vorbestehend_roter_test_blockiert_nicht(tmp_path):
    """War der Test schon VOR der Aenderung rot, blockiert er nicht — er wird gemeldet.

    Gemessen, nicht geglaubt: Das Gate legt einen Wegwerf-Abzug des letzten Commits an
    und laesst dieselben Tests dort laufen. Es gibt keine pflegbare Liste, die jemand
    faelschen koennte (Adversary F001/F001b).
    """
    # Ausgangsstand ist bereits kaputt, die Aenderung macht ihn nicht schlimmer
    repo = _wegwerf_repo(tmp_path, KAPUTT + "# harmlose Zeile\n", GRUENER_TEST, basis=KAPUTT)
    r = _hook(repo)
    assert r.returncode == 0, (
        f"Vorbestehend roter Test darf nicht blockieren (Exit {r.returncode})\n{r.stderr}"
    )
    assert "vorbesteh" in (r.stderr + r.stdout).lower(), (
        "Der vorbestehende Fehlschlag muss trotzdem sichtbar gemeldet werden (AC-3)"
    )


def test_ac4_aus_gruen_wird_rot_blockiert(tmp_path):
    """Die Gegenprobe zu AC-3: derselbe Test, aber im Ausgangsstand gruen -> blockiert.

    ⚠️ Beide Faelle zusammen sind die eigentliche Zusicherung. Ohne diesen hier waere
    „blockiert nicht" trivial erfuellbar, indem das Gate NIE blockiert.
    """
    repo = _wegwerf_repo(tmp_path, KAPUTT, GRUENER_TEST, basis=HEIL)
    r = _hook(repo)
    assert r.returncode == 2 and "test_verdopple" in r.stderr, (
        "Ein Test, der im Ausgangsstand gruen war und es jetzt nicht mehr ist, MUSS "
        f"blockieren (Exit {r.returncode})\n{r.stderr}"
    )


# ---------------------------------------------------------------------------
# AC-7 / AC-8: Arbeitsfaehigkeit
# ---------------------------------------------------------------------------

def test_ac7_gescheiterte_vorzustandsmessung_blockiert_nicht(tmp_path):
    """Adversary-Fund F007 (CRITICAL): Kann das Gate den Vorzustand nicht messen,
    laesst es durch und sagt es — es blockiert NICHT.

    ⚠️ Der Fall war in beiden Richtungen ungetestet, und der erste Entwurf entschied
    genau falsch herum: Eine gescheiterte MESSUNG liess einen harmlosen Commit auflaufen,
    obwohl der Test schon vorher rot war. Dieselbe blinde Stelle wie bei den beiden Funden
    davor — der Erfolgspfad war gebaut und geprueft, der Stoerungspfad nicht.
    """
    repo = _wegwerf_repo(tmp_path, KAPUTT + "# harmlose Zeile\n", GRUENER_TEST, basis=KAPUTT)
    gitdir = repo / ".git"
    urspruenglich = gitdir.stat().st_mode
    gitdir.chmod(0o500)  # Messung braucht Schreibrecht in .git/worktrees -> scheitert
    try:
        r = _hook(repo)
    finally:
        gitdir.chmod(urspruenglich)
    text = (r.stderr + r.stdout).lower()
    assert r.returncode == 0, (
        "Eine gescheiterte Vorzustandsmessung ist eine Stoerung des Gates — sie darf den "
        f"Commit nicht blockieren (AC-7, Exit {r.returncode})\n{r.stderr}"
    )
    assert "unbekannt" in text or "nicht messbar" in text, (
        "Das Gate muss sagen, dass es den Vorzustand nicht kennt — sonst sieht "
        f"durchgelassen wie geprueft aus (AC-12). Ausgabe: {text!r}"
    )


def test_ac7b_alte_messreste_werden_aufgeraeumt(tmp_path):
    """Adversary-Fund F008: Ein harter Abbruch laesst einen Mess-Abzug zurueck.

    Gegen SIGKILL hilft kein `finally` — deshalb raeumt das Gate zu Beginn jeder Messung
    die Reste frueherer Laeufe weg. Ohne dieses Netz sammeln sich Registrierungen im
    echten Repo an.
    """
    repo = _wegwerf_repo(tmp_path, KAPUTT, GRUENER_TEST, basis=HEIL)
    leiche = tmp_path / "leiche"
    _git(repo, "worktree", "add", "--detach", "-q", str(leiche), "HEAD")
    shutil.rmtree(leiche)  # Verzeichnis weg, Registrierung bleibt — wie nach einem Kill
    vorher = subprocess.run(["git", "-C", str(repo), "worktree", "list"],
                            capture_output=True, text=True).stdout
    assert "leiche" in vorher, "Vorbedingung: die Leiche muss registriert sein"

    _hook(repo)

    nachher = subprocess.run(["git", "-C", str(repo), "worktree", "list"],
                             capture_output=True, text=True).stdout
    assert "leiche" not in nachher, (
        "Das Gate muss Reste frueherer Messungen entfernen — sonst waechst die Liste der "
        f"registrierten Arbeitsverzeichnisse endlos:\n{nachher}"
    )


def test_ac8_kein_commit_kein_aufwand(tmp_path):
    """Ein anderer Bash-Aufruf laeuft ohne Testlauf durch."""
    repo = _wegwerf_repo(tmp_path, "def verdopple(x):\n    return x * 3\n", GRUENER_TEST)
    r = _hook(repo, kommando="ls -la")
    assert r.returncode == 0
    assert "test_verdopple" not in r.stderr, "Ohne git commit darf gar nichts laufen (AC-8)"


# ---------------------------------------------------------------------------
# AC-5: das Gate darf NIE etwas verschicken
#
# ⚠️ Diese beiden Faelle kamen erst durch die Mutations-Gegenprobe dazu: die
# Verfaelschungen „Live-Marker entfernt" und „tests/tdd wieder mitgeprueft" liefen
# durch ALLE bisherigen Tests hindurch. Beide bedeuten dasselbe in echt: jeder Commit
# koennte dann Nachrichten verschicken — genau der Vorfall vom 2026-08-03 (#1477).
# Der Versand wird durch eine Datei vertreten: laeuft der markierte Test, entsteht sie.
# ---------------------------------------------------------------------------

VERSAND_TEST = (
    "import pytest, pathlib, sys\n"
    "sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / 'src'))\n"
    "import rechner  # nennt das geaenderte Modul — sonst waehlt das Gate die Datei nie\n"
    "@pytest.mark.email\n"
    "def test_wuerde_verschicken():\n"
    "    pathlib.Path('VERSAND_PASSIERT').write_text(rechner.__name__)\n"
)


def test_ac5_markierte_versand_tests_laufen_nicht(tmp_path):
    """Ein Test mit Versand-Marker darf vom Gate nicht ausgefuehrt werden."""
    repo = _wegwerf_repo(tmp_path, HEIL + "# echte Aenderung\n", GRUENER_TEST)
    (repo / "tests" / "unit" / "test_rechner_versand.py").write_text(VERSAND_TEST)
    _git(repo, "add", "-A")
    _hook(repo)
    assert not (repo / "VERSAND_PASSIERT").exists(), (
        "Das Gate hat einen mit `email` markierten Test ausgefuehrt — so loest jeder "
        "Commit echten Versand aus (AC-5, Vorfall #1477)"
    )


@pytest.mark.parametrize("marker", ["live", "staging"])
def test_ac5_alle_drei_marker_bleiben_draussen(tmp_path, marker):
    """Adversary-Fund F002: Der Nachweis deckte nur `email` ab.

    `tests/unit/` enthaelt real Tests mit `@pytest.mark.live`, die echte Wetterdienste
    anrufen. Faellt einer der drei Marker aus dem Ausschluss, telefoniert kuenftig jeder
    Commit — und kein Test haette es bemerkt.
    """
    repo = _wegwerf_repo(tmp_path, HEIL + "# echte Aenderung\n", GRUENER_TEST)
    (repo / "tests" / "unit" / f"test_rechner_{marker}.py").write_text(
        "import pytest, pathlib, sys\n"
        "sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / 'src'))\n"
        "import rechner\n"
        f"@pytest.mark.{marker}\n"
        "def test_geht_raus():\n"
        f"    pathlib.Path('KONTAKT_{marker.upper()}').write_text(rechner.__name__)\n"
    )
    _git(repo, "add", "-A")
    _hook(repo)
    assert not (repo / f"KONTAKT_{marker.upper()}").exists(), (
        f"Das Gate hat einen mit `{marker}` markierten Test ausgefuehrt — so nimmt jeder "
        "Commit echten Aussenkontakt auf (AC-5)"
    )


def test_ac5_tdd_schicht_wird_nicht_angefasst(tmp_path):
    """`tests/tdd/` bleibt aussen vor — dort liegen die Tests, die wirklich senden."""
    repo = _wegwerf_repo(tmp_path, HEIL + "# echte Aenderung\n", GRUENER_TEST)
    (repo / "tests" / "tdd").mkdir(parents=True)
    (repo / "tests" / "tdd" / "test_rechner_sendet.py").write_text(
        "import pathlib, sys\n"
        "sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / 'src'))\n"
        "import rechner  # nennt das Modul — sonst waehlt das Gate die Datei nie aus\n"
        "def test_sendet():\n"
        "    pathlib.Path('TDD_LIEF').write_text(rechner.__name__)\n"
        "    assert False\n"
    )
    _git(repo, "add", "-A")
    r = _hook(repo)
    assert not (repo / "TDD_LIEF").exists(), (
        "Das Gate hat einen Test aus tests/tdd/ ausgefuehrt — diese Schicht ist bewusst "
        "ausgeschlossen (Versandrisiko #1477)"
    )
    assert r.returncode == 0, (
        "Ein roter Test in tests/tdd/ darf den Commit nicht blockieren, weil das Gate "
        f"diese Schicht gar nicht prueft (Exit {r.returncode})\n{r.stderr}"
    )


def test_ac7_unerwartete_stoerung_blockiert_nie(tmp_path):
    """Selbst wenn dem Gate das Werkzeug unter den Haenden wegbricht: kein Blockieren.

    ⚠️ Auch dieser Fall stammt aus der Mutations-Gegenprobe: Der bisherige AC-7-Test traf
    nur den INNEREN Abfangweg (defekter Bestand). Der aeussere Notausgang — die letzte
    Absicherung gegen jeden unvorhergesehenen Fehler — war ungetestet.
    """
    repo = _wegwerf_repo(tmp_path, "def verdopple(x):\n    return x * 2\n", GRUENER_TEST)
    eingabe = json.dumps({"tool_input": {"command": "git commit -m 'x'"}})
    r = subprocess.run(
        [sys.executable, str(GATE)], input=eingabe, cwd=str(repo),
        capture_output=True, text=True, timeout=180,
        env={"PATH": "", "HOME": os.environ.get("HOME", "/tmp")},
    )
    assert r.returncode == 0, (
        "Ohne auffindbare Werkzeuge muss das Gate durchlassen, nicht blockieren "
        f"(Exit {r.returncode})\n{r.stderr}"
    )


def test_ac1c_umbenanntes_modul_wird_trotzdem_geprueft(tmp_path):
    """Adversary-Fund F003: Umbenennen + kaputt machen im selben Commit.

    Die Testdatei nennt weiterhin den ALTEN Modulnamen. Sucht das Gate nur nach dem
    neuen, findet es nichts und meldet beruhigend „keine Tests gefunden" — waehrend der
    Testlauf in Wahrheit gar nicht mehr startet (Importfehler).
    """
    repo = _wegwerf_repo(tmp_path, HEIL, GRUENER_TEST)
    _git(repo, "mv", "src/rechner.py", "src/rechenwerk.py")
    (repo / "src" / "rechenwerk.py").write_text("def verdopple(x):\n    return x * 3\n")
    _git(repo, "add", "-A")
    r = _hook(repo)
    assert r.returncode == 2, (
        "Nach einer Umbenennung muss das Gate die zugehoerige Testdatei ueber den ALTEN "
        f"Namen finden und blockieren (Exit {r.returncode})\n{r.stderr}{r.stdout}"
    )
    assert "test_rechner" in r.stderr, (
        "Die betroffene Testdatei muss genannt werden:\n" + r.stderr
    )


def test_ac1d_reparaturbefehl_ist_wirklich_lauffaehig(tmp_path):
    """Adversary-Fund F005b: Der vorgeschlagene Befehl wird AUSGEFUEHRT, nicht nur gelesen.

    ⚠️ Die Vorgaenger-Fassung nannte bei einem Go-Fehlschlag `go test <Testname>` — das
    sucht ein PAKET dieses Namens und bricht mit „is not in std" ab. Kein Test hat es
    bemerkt, weil alle nur den Text der Meldung durchsucht haben. Deshalb fuehrt dieser
    Fall den Befehl aus und verlangt, dass er den gemeldeten Test tatsaechlich erreicht.
    """
    go = shutil.which("go") or "/usr/local/go/bin/go"
    if not Path(go).exists():
        pytest.skip("Go-Werkzeug nicht vorhanden")

    repo = tmp_path / "repo"
    (repo / "internal" / "rechner").mkdir(parents=True)
    (repo / "go.mod").write_text("module beispiel\n\ngo 1.21\n")
    (repo / "internal" / "rechner" / "rechner.go").write_text(
        "package rechner\n\nfunc Verdopple(x int) int { return x * 2 }\n"
    )
    (repo / "internal" / "rechner" / "rechner_test.go").write_text(
        "package rechner\n\nimport \"testing\"\n\n"
        "func TestVerdopple(t *testing.T) {\n"
        "\tif Verdopple(2) != 4 { t.Fatal(\"falsch\") }\n}\n"
    )
    _git(repo.parent, "init", "-q", str(repo))
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "Ausgangsstand")
    (repo / "internal" / "rechner" / "rechner.go").write_text(
        "package rechner\n\nfunc Verdopple(x int) int { return x * 3 }\n"
    )
    _git(repo, "add", "-A")

    r = _hook(repo)
    assert r.returncode == 2, f"Go-Fehlschlag muss blockieren (Exit {r.returncode})\n{r.stderr}"

    zeile = next((z.strip() for z in r.stderr.splitlines() if z.strip().startswith("go test")), None)
    assert zeile, "Kein Go-Reparaturbefehl in der Meldung:\n" + r.stderr

    lauf = subprocess.run(zeile, shell=True, cwd=str(repo), capture_output=True,
                          text=True, timeout=300, env={**os.environ,
                                                       "PATH": f"{Path(go).parent}:{os.environ.get('PATH','')}"})
    ausgabe = lauf.stdout + lauf.stderr
    assert "is not in std" not in ausgabe and "no packages" not in ausgabe, (
        f"Der vorgeschlagene Befehl ist nicht lauffaehig:\n   {zeile}\n{ausgabe}"
    )
    assert "TestVerdopple" in ausgabe and lauf.returncode != 0, (
        f"Der Befehl muss den gemeldeten Test wirklich erreichen und ihn rot zeigen:\n"
        f"   {zeile}\n{ausgabe}"
    )


# ---------------------------------------------------------------------------
# AC-6 / AC-12: Ehrlichkeit ueber den eigenen Umfang
# ---------------------------------------------------------------------------

def test_ac6_keine_zugehoerigen_tests_wird_gesagt(tmp_path):
    """Findet das Gate keine Tests, sagt es das — Schweigen ist nicht zulaessig."""
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "einsam.py").write_text("WERT = 1\n")
    _git(repo.parent, "init", "-q", str(repo))
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "add", "-A")
    r = _hook(repo)
    assert r.returncode == 0
    text = (r.stderr + r.stdout).lower()
    assert "kein" in text and "test" in text, (
        "Das Gate muss ausdruecklich sagen, dass es keine zugehoerigen Tests gefunden hat "
        f"(AC-6). Ausgabe war: {text!r}"
    )


def test_ac12_ungepruefte_schicht_wird_benannt(tmp_path):
    """Go-Datei ohne verfuegbares Go-Werkzeug: der Commit laeuft, die Luecke wird genannt."""
    repo = tmp_path / "repo"
    (repo / "internal" / "handler").mkdir(parents=True)
    (repo / "internal" / "handler" / "x.go").write_text("package handler\n")
    _git(repo.parent, "init", "-q", str(repo))
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "add", "-A")
    r = _hook(repo)
    assert r.returncode == 0
    text = (r.stderr + r.stdout).lower()
    assert "go" in text, (
        "Bei einer nicht pruefbaren Schicht muss die Meldung sie benennen (AC-12) — sonst "
        f"sieht 'Commit ging durch' wie 'geprueft' aus. Ausgabe: {text!r}"
    )


# ===========================================================================
# #2503: neu angelegte RED-Tests in Phase TDD-RED durchlassen
#
# Spec: docs/specs/modules/fix_2503_red_tests_gate.md
#
# Die Phase kommt aus einer echten Workflow-State-Datei IM Wegwerf-Repo
# (`.claude/active_workflow` + `.claude/workflows/<name>.json`) — genau so, wie das
# Gate sie in einer echten Sitzung liest. Kein Mock der Phasenabfrage.
# ===========================================================================

WF_NAME = "wf-2503-probe"
NUR_RED = "nur in phase tdd-red erlaubt"
NEU_ANGELEGT = "neu angelegt rot"


def _phase_setzen(repo: Path, phase: str | None, defekt: bool = False) -> None:
    """Workflow-State im Wegwerf-Repo: Phase setzen, weglassen (None) oder zerstoeren."""
    if phase is None and not defekt:
        return
    wf = repo / ".claude" / "workflows"
    wf.mkdir(parents=True, exist_ok=True)
    (repo / ".claude" / "active_workflow").write_text(WF_NAME + "\n")
    datei = wf / f"{WF_NAME}.json"
    if defekt:
        datei.write_text("{ das ist kein JSON")
    else:
        datei.write_text(json.dumps({"name": WF_NAME, "current_phase": phase}))


def _repo_init(repo: Path) -> None:
    _git(repo.parent, "init", "-q", str(repo))
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "Ausgangsstand")


# --- Python ----------------------------------------------------------------

NEUER_ROTER_PY_TEST = GRUENER_TEST + (
    "def test_neu_angelegt_rot():\n"
    "    assert verdopple(2) == 5\n"
)


def _python_repo_mit_neuem_rotem_test(tmp_path: Path) -> Path:
    """Gruene Testdatei committet; im Arbeitsstand kommt eine neue, rote Funktion dazu."""
    repo = _wegwerf_repo(tmp_path, HEIL + "# echte Aenderung\n", GRUENER_TEST)
    (repo / "tests" / "unit" / "test_rechner.py").write_text(NEUER_ROTER_PY_TEST)
    _git(repo, "add", "-A")
    return repo


def test_2503_ac2_neuer_roter_python_test_in_phase_red_laesst_durch(tmp_path):
    """AC-2: Neue rote Funktion in bestehender Datei, Phase RED -> Exit 0, Name genannt."""
    repo = _python_repo_mit_neuem_rotem_test(tmp_path)
    _phase_setzen(repo, "phase5_tdd_red")
    r = _hook(repo)
    assert r.returncode == 0, (
        "Ein neu angelegter, erwartungsgemaess roter Test darf in Phase TDD-RED nicht "
        f"blockieren (AC-2, Exit {r.returncode})\n{r.stderr}"
    )
    assert "test_neu_angelegt_rot" in r.stderr and NEU_ANGELEGT in r.stderr.lower(), (
        "Der durchgelassene Test muss namentlich als 'neu angelegt rot' gemeldet werden:\n"
        + r.stderr
    )


@pytest.mark.parametrize("zustand", ["phase6_implement", "kein_workflow", "defekt"])
def test_2503_ac4_neuer_roter_test_ausserhalb_red_blockiert(tmp_path, zustand):
    """AC-4: Derselbe neue rote Test, aber nicht in Phase RED -> Exit 2 mit eigener Meldung.

    ⚠️ Ohne diesen Fall waere die Ausnahme phasenlos — jede Sitzung koennte rote Tests
    committen. Ein unlesbarer State ist fehlende Erlaubnis, keine Stoerung des Gates.
    """
    repo = _python_repo_mit_neuem_rotem_test(tmp_path)
    if zustand == "phase6_implement":
        _phase_setzen(repo, "phase6_implement")
    elif zustand == "defekt":
        _phase_setzen(repo, None, defekt=True)
    r = _hook(repo)
    assert r.returncode == 2, (
        f"Ausserhalb der Phase TDD-RED ({zustand}) muss ein neuer roter Test blockieren "
        f"(AC-4, Exit {r.returncode})\n{r.stderr}"
    )
    assert NUR_RED in r.stderr.lower() and "test_neu_angelegt_rot" in r.stderr, (
        "Die Meldung muss sagen, dass ein neu angelegter roter Test 'nur in Phase TDD-RED "
        f"erlaubt' ist, und den Test nennen ({zustand}):\n{r.stderr}"
    )


def test_2503_ac5_aus_gruen_wird_rot_blockiert_auch_in_phase_red(tmp_path):
    """AC-5 (Gegenprobe): Bestehender gruener Test wird rot -> in Phase RED weiter Exit 2.

    Faengt die Mutation „Existenzmessung durch 'immer neu' ersetzt".
    """
    repo = _wegwerf_repo(tmp_path, KAPUTT, GRUENER_TEST, basis=HEIL)
    _phase_setzen(repo, "phase5_tdd_red")
    r = _hook(repo)
    assert r.returncode == 2 and "test_verdopple" in r.stderr, (
        "Ein im letzten Commit gruener Test, der jetzt rot ist, MUSS auch in Phase RED "
        f"blockieren (AC-5, Exit {r.returncode})\n{r.stderr}"
    )
    assert "macht tests rot" in r.stderr.lower(), r.stderr


@pytest.mark.parametrize("phase", ["phase5_tdd_red", None])
def test_2503_ac6_vorbestehend_rot_unabhaengig_von_der_phase(tmp_path, phase):
    """AC-6: Vorbestehend roter Test laeuft in jeder Phase durch und wird gemeldet."""
    repo = _wegwerf_repo(tmp_path, KAPUTT + "# harmlose Zeile\n", GRUENER_TEST, basis=KAPUTT)
    _phase_setzen(repo, phase)
    r = _hook(repo)
    assert r.returncode == 0, f"Vorbestehend rot darf nicht blockieren ({phase})\n{r.stderr}"
    assert "vorbesteh" in r.stderr.lower(), r.stderr


# --- Go --------------------------------------------------------------------

def _go_oder_skip() -> str:
    go = shutil.which("go") or "/usr/local/go/bin/go"
    if not Path(go).exists():
        pytest.skip("Go-Werkzeug nicht vorhanden — Go-Faelle von #2503 UNGEPRUEFT")
    return go


GO_QUELLE = "package rechner\n\nfunc Verdopple(x int) int { return x * 2 }\n"


def _go_repo(tmp_path: Path, test_basis: str, test_neu: str,
             quelle_neu: str | None = None) -> Path:
    """Go-Paket mit committetem Test (`test_basis`), Arbeitsstand `test_neu` gestagt."""
    repo = tmp_path / "repo"
    paket = repo / "internal" / "rechner"
    paket.mkdir(parents=True)
    (repo / "go.mod").write_text("module beispiel\n\ngo 1.21\n")
    (paket / "rechner.go").write_text(GO_QUELLE)
    (paket / "rechner_test.go").write_text(test_basis)
    _repo_init(repo)
    (paket / "rechner_test.go").write_text(test_neu)
    if quelle_neu is not None:
        (paket / "rechner.go").write_text(quelle_neu)
    _git(repo, "add", "-A")
    return repo


GO_TEST_KOPF = 'package rechner\n\nimport "testing"\n\n'
GO_TEST_ALT = (
    "func TestVerdopple(t *testing.T) {\n"
    '\tif Verdopple(2) != 4 { t.Fatal("falsch") }\n}\n'
)
GO_TEST_NEU_ROT = (
    "\nfunc TestNeu(t *testing.T) {\n"
    '\tif Verdopple(2) != 5 { t.Fatal("erwartet rot") }\n}\n'
)


def test_2503_ac1_neue_go_testfunktion_in_phase_red_laesst_durch(tmp_path):
    """AC-1: Neue Go-Testfunktion per Assertion rot, Phase RED -> Exit 0, `TestNeu` genannt.

    Genau der Fall aus #2261 A-2 S2, an dem das Gate den RED-Commit verweigerte.
    """
    _go_oder_skip()
    repo = _go_repo(tmp_path, GO_TEST_KOPF + GO_TEST_ALT,
                    GO_TEST_KOPF + GO_TEST_ALT + GO_TEST_NEU_ROT)
    _phase_setzen(repo, "phase5_tdd_red")
    r = _hook(repo)
    assert r.returncode == 0, (
        f"Neue rote Go-Testfunktion in Phase RED muss durch (AC-1, Exit {r.returncode})\n"
        + r.stderr
    )
    assert "TestNeu" in r.stderr and NEU_ANGELEGT in r.stderr.lower(), (
        "Hinweis muss `TestNeu` als 'neu angelegt rot (TDD-RED, blockiert nicht)' nennen:\n"
        + r.stderr
    )


def test_2503_ac1b_neue_go_testfunktion_ausserhalb_red_blockiert(tmp_path):
    """AC-1/AC-4 fuer Go: derselbe Fall in Phase 6 -> Exit 2 mit 'nur in Phase TDD-RED'."""
    _go_oder_skip()
    repo = _go_repo(tmp_path, GO_TEST_KOPF + GO_TEST_ALT,
                    GO_TEST_KOPF + GO_TEST_ALT + GO_TEST_NEU_ROT)
    _phase_setzen(repo, "phase6_implement")
    r = _hook(repo)
    assert r.returncode == 2 and NUR_RED in r.stderr.lower(), (
        f"Ausserhalb Phase RED muss blockiert werden, mit eigener Meldung (Exit "
        f"{r.returncode})\n{r.stderr}"
    )


GO_SUBTEST_BASIS = GO_TEST_KOPF + (
    "func TestA(t *testing.T) {\n"
    '\tt.Run("alt", func(t *testing.T) { if Verdopple(2) != 4 { t.Fatal("alt") } })\n'
    "}\n"
)
GO_SUBTEST_NEU = GO_TEST_KOPF + (
    "func TestA(t *testing.T) {\n"
    '\tt.Run("alt", func(t *testing.T) { if Verdopple(2) != 4 { t.Fatal("alt") } })\n'
    '\tt.Run("neu", func(t *testing.T) { if Verdopple(2) != 5 { t.Fatal("neu") } })\n'
    "}\n"
)


def test_2503_ac3_neuer_go_subtest_in_phase_red_laesst_durch(tmp_path):
    """AC-3 (erster Teil): Neuer roter Subtest in bestehender Funktion -> Exit 0.

    Die Elternfunktion `TestA` existierte schon und ist jetzt rot — entschuldigt nur,
    weil ALLE ihre roten Subtests neu angelegt sind.
    """
    _go_oder_skip()
    repo = _go_repo(tmp_path, GO_SUBTEST_BASIS, GO_SUBTEST_NEU)
    _phase_setzen(repo, "phase5_tdd_red")
    r = _hook(repo)
    assert r.returncode == 0, (
        f"Neuer roter Subtest in Phase RED muss durch (AC-3, Exit {r.returncode})\n"
        + r.stderr
    )
    assert "TestA/neu" in r.stderr, "Der neue Subtest muss genannt werden:\n" + r.stderr


def test_2503_ac3b_vorbestehender_subtest_rot_blockiert_die_elternfunktion(tmp_path):
    """AC-3 (zweiter Teil): Zusaetzlich wird ein vorher gruener Subtest rot -> Exit 2.

    Faengt die Mutationen „Subtest-Elternregel gelockert" und „eingeruecktes
    `--- FAIL:` uebersehen": `go test` rueckt Subtest-Zeilen ein; wer nur `^--- FAIL:`
    sucht, sieht `TestA/alt` nie.
    """
    _go_oder_skip()
    repo = _go_repo(tmp_path, GO_SUBTEST_BASIS, GO_SUBTEST_NEU,
                    quelle_neu="package rechner\n\nfunc Verdopple(x int) int { return x * 3 }\n")
    _phase_setzen(repo, "phase5_tdd_red")
    r = _hook(repo)
    assert r.returncode == 2, (
        "Ist ein vorbestehender Subtest rot, darf die Elternfunktion nicht als 'neu "
        f"angelegt' entschuldigt werden (AC-3, Exit {r.returncode})\n{r.stderr}"
    )
    assert "TestA/alt" in r.stderr, (
        "Der vorbestehende, jetzt rote Subtest muss erkannt und genannt werden "
        "(eingeruecktes `--- FAIL:`):\n" + r.stderr
    )


@pytest.mark.parametrize("phase", ["phase5_tdd_red", "phase6_implement"])
def test_2503_ac8_go_uebersetzungsfehler_bleibt_stoerung(tmp_path, phase):
    """AC-8: Nicht kompilierender Go-Test ist Stoerung -> Exit 0 mit Hinweis, jede Phase."""
    _go_oder_skip()
    repo = _go_repo(tmp_path, GO_TEST_KOPF + GO_TEST_ALT,
                    GO_TEST_KOPF + GO_TEST_ALT
                    + "\nfunc TestKaputt(t *testing.T) { GibtEsNicht() }\n")
    _phase_setzen(repo, phase)
    r = _hook(repo)
    assert r.returncode == 0, (
        f"Uebersetzungsfehler ist eine Stoerung des Laufs, kein Block ({phase}, Exit "
        f"{r.returncode})\n{r.stderr}"
    )
    assert "ungeprueft" in r.stderr.lower(), "Stoerung muss sichtbar sein:\n" + r.stderr


# --- Frontend --------------------------------------------------------------

FE_TEST_ALT = (
    "import { test } from 'node:test';\n"
    "import assert from 'node:assert/strict';\n"
    "import { verdopple } from './rechner.ts';\n"
    "test('verdopple alt', () => { assert.equal(verdopple(2), 4); });\n"
)
FE_TEST_NEU = FE_TEST_ALT + (
    "test('verdopple neu rot', () => { assert.equal(verdopple(2), 5); });\n"
)


def _frontend_repo(tmp_path: Path) -> Path:
    if not shutil.which("node"):
        pytest.skip("node nicht vorhanden — Frontend-Faelle von #2503 UNGEPRUEFT")
    repo = tmp_path / "repo"
    lib = repo / "frontend" / "src" / "lib"
    lib.mkdir(parents=True)
    (repo / "frontend" / "package.json").write_text('{"type":"module"}\n')
    (repo / "frontend" / "test-lib-loader.mjs").write_text("// leer: kein $lib-Resolver noetig\n")
    # Wie im echten Repo: node_modules ist NICHT eingecheckt (.gitignore). Damit fehlt es
    # im Wegwerf-Abzug der Vorzustandsmessung — das Gate muss trotzdem messen koennen,
    # sonst gilt jeder Frontend-Fehlschlag als „Vorzustand unbekannt" und nichts blockiert.
    (repo / ".gitignore").write_text("node_modules/\n")
    (repo / "frontend" / "node_modules").mkdir()
    (repo / "frontend" / "node_modules" / ".platzhalter").write_text("x\n")
    (lib / "rechner.ts").write_text(
        "export function verdopple(x: number): number { return x * 2; }\n")
    (lib / "rechner.test.ts").write_text(FE_TEST_ALT)
    _repo_init(repo)
    (lib / "rechner.ts").write_text(
        "export function verdopple(x: number): number { return x * 2; }\n// Aenderung\n")
    (lib / "rechner.test.ts").write_text(FE_TEST_NEU)
    _git(repo, "add", "-A")
    return repo


def test_2503_ac7_neuer_roter_frontend_test_in_phase_red_laesst_durch(tmp_path):
    """AC-7: Neuer roter `node --test`-Fall in Phase RED -> Exit 0, Name genannt."""
    repo = _frontend_repo(tmp_path)
    _phase_setzen(repo, "phase5_tdd_red")
    r = _hook(repo)
    assert r.returncode == 0, (
        f"Neuer roter Frontend-Test in Phase RED muss durch (AC-7, Exit {r.returncode})\n"
        + r.stderr
    )
    assert "verdopple neu rot" in r.stderr and NEU_ANGELEGT in r.stderr.lower(), r.stderr


def test_2503_ac7b_neuer_roter_frontend_test_ausserhalb_red_blockiert(tmp_path):
    """AC-7 Gegenprobe: derselbe Fall in Phase 6 -> Exit 2 mit 'nur in Phase TDD-RED'."""
    repo = _frontend_repo(tmp_path)
    _phase_setzen(repo, "phase6_implement")
    r = _hook(repo)
    assert r.returncode == 2 and NUR_RED in r.stderr.lower(), (
        f"Ausserhalb Phase RED muss blockiert werden (Exit {r.returncode})\n{r.stderr}"
    )


# --- Adversary-Runde 1 (#2503) ---------------------------------------------

FE_KOPF = (
    "import { test, describe } from 'node:test';\n"
    "import assert from 'node:assert/strict';\n"
    "import { verdopple } from './rechner.ts';\n"
)
FE_QUELLE_HEIL = "export function verdopple(x: number): number { return x * 2; }\n"
FE_QUELLE_KAPUTT = "export function verdopple(x: number): number { return x * 3; }\n"
FE_DESCRIBE_ALT = FE_KOPF + (
    "describe('rechner', () => {\n"
    "  test('verdopple alt', () => { assert.equal(verdopple(2), 4); });\n"
    "});\n"
)
FE_DESCRIBE_NEU = FE_KOPF + (
    "describe('rechner', () => {\n"
    "  test('verdopple alt', () => { assert.equal(verdopple(2), 4); });\n"
    "  test('verdopple neu im describe', () => { assert.equal(verdopple(2), 5); });\n"
    "});\n"
)


def _frontend_repo_mit(tmp_path: Path, test_alt: str, test_neu: str,
                       quelle_neu: str) -> Path:
    """Frontend-Wegwerf-Repo mit frei waehlbarem Test- und Quell-Stand (gestagt)."""
    if not shutil.which("node"):
        pytest.skip("node nicht vorhanden — Frontend-Faelle von #2503 UNGEPRUEFT")
    repo = tmp_path / "repo"
    lib = repo / "frontend" / "src" / "lib"
    lib.mkdir(parents=True)
    (repo / "frontend" / "package.json").write_text('{"type":"module"}\n')
    (repo / "frontend" / "test-lib-loader.mjs").write_text("// leer\n")
    (repo / ".gitignore").write_text("node_modules/\n")
    (repo / "frontend" / "node_modules").mkdir()
    (repo / "frontend" / "node_modules" / ".platzhalter").write_text("x\n")
    (lib / "rechner.ts").write_text(FE_QUELLE_HEIL)
    (lib / "rechner.test.ts").write_text(test_alt)
    _repo_init(repo)
    (lib / "rechner.ts").write_text(quelle_neu)
    (lib / "rechner.test.ts").write_text(test_neu)
    _git(repo, "add", "-A")
    return repo


def test_2503_f001_neuer_roter_test_im_describe_in_phase_red_laesst_durch(tmp_path):
    """F001: Neuer roter test() in BESTEHENDEM describe -> Exit 0 in Phase RED.

    Die Eltern-Suite (`not ok 1 - rechner`) lief schon im Vorzustand und ist jetzt rot —
    entschuldigt nur, weil ihr einziger roter Kind-Test neu angelegt ist (Elternregel).
    """
    repo = _frontend_repo_mit(tmp_path, FE_DESCRIBE_ALT, FE_DESCRIBE_NEU,
                              FE_QUELLE_HEIL + "// Aenderung\n")
    _phase_setzen(repo, "phase5_tdd_red")
    r = _hook(repo)
    assert r.returncode == 0, (
        f"Neuer roter Test im bestehenden describe muss in Phase RED durch (Exit "
        f"{r.returncode})\n{r.stderr}"
    )
    assert "verdopple neu im describe" in r.stderr and NEU_ANGELEGT in r.stderr.lower(), r.stderr


def test_2503_f001b_bestehender_test_im_describe_wird_rot_blockiert(tmp_path):
    """F001 Gegenprobe: vorher gruener test() im describe wird rot -> Exit 2, auch in RED."""
    repo = _frontend_repo_mit(tmp_path, FE_DESCRIBE_ALT, FE_DESCRIBE_NEU, FE_QUELLE_KAPUTT)
    _phase_setzen(repo, "phase5_tdd_red")
    r = _hook(repo)
    assert r.returncode == 2 and "verdopple alt" in r.stderr, (
        "Ein vorher gruener Test im describe, der jetzt rot ist, MUSS blockieren "
        f"(Exit {r.returncode})\n{r.stderr}"
    )
    assert "macht tests rot" in r.stderr.lower(), r.stderr


def test_2503_f003_flacher_frontend_test_aus_gruen_wird_rot_blockiert(tmp_path):
    """F003: flacher, vorher gruener Frontend-Test wird rot, Phase RED -> Exit 2.

    Bewacht die Mutation „Frontend-gelaufen-Menge leer" (dann gaelte alles als neu).
    """
    repo = _frontend_repo_mit(tmp_path, FE_TEST_ALT, FE_TEST_ALT, FE_QUELLE_KAPUTT)
    _phase_setzen(repo, "phase5_tdd_red")
    r = _hook(repo)
    assert r.returncode == 2 and "verdopple alt" in r.stderr, (
        f"Aus gruen wird rot muss auch im Frontend blockieren (Exit {r.returncode})\n"
        + r.stderr
    )


def test_2503_f004_node_modules_bleibt_und_kein_abzug_bleibt_zurueck(tmp_path):
    """F004: Der Verweis im Abzug darf das echte node_modules nicht anfassen."""
    repo = _frontend_repo_mit(tmp_path, FE_DESCRIBE_ALT, FE_DESCRIBE_NEU, FE_QUELLE_KAPUTT)
    _phase_setzen(repo, "phase5_tdd_red")
    _hook(repo)
    assert (repo / "frontend" / "node_modules" / ".platzhalter").exists(), (
        "node_modules des Arbeitsstands wurde beim Aufraeumen beschaedigt")
    liste = subprocess.run(["git", "-C", str(repo), "worktree", "list"],
                           capture_output=True, text=True).stdout.strip().splitlines()
    assert len(liste) == 1, f"Mess-Abzug blieb registriert:\n{liste}"


def test_2503_f002_elternfunktion_mit_altem_rotem_subtest_wird_genannt(tmp_path):
    """F002: Elternregel bewacht — alter Subtest rot + neuer roter Subtest, Phase RED.

    Die Elternfunktion `TestA` darf NICHT entschuldigt werden: Sie muss selbst als
    blockierender Fehlschlag in der Meldung stehen (faengt „Eltern immer entschuldigt").
    """
    _go_oder_skip()
    repo = _go_repo(tmp_path, GO_SUBTEST_BASIS, GO_SUBTEST_NEU,
                    quelle_neu="package rechner\n\nfunc Verdopple(x int) int { return x * 3 }\n")
    _phase_setzen(repo, "phase5_tdd_red")
    r = _hook(repo)
    blockiert = [z.strip() for z in r.stderr.split("Einzeln nachstellen")[0].splitlines()]
    assert r.returncode == 2 and "TestA" in blockiert, (
        "Die Elternfunktion mit vorbestehendem, jetzt rotem Subtest muss als blockierender "
        f"Fehlschlag genannt werden (Exit {r.returncode})\n{r.stderr}"
    )


def test_2503_python_sammelfehler_bestehender_datei_blockiert_auch_in_red(tmp_path):
    """Ein Importfehler einer BESTEHENDEN Testdatei (`ERROR <datei>`) ist keine neu
    angelegte Kennung — die Datei lief im Vorzustand. Auch in Phase RED -> Exit 2.
    """
    repo = _wegwerf_repo(tmp_path, HEIL, GRUENER_TEST)
    _git(repo, "mv", "src/rechner.py", "src/rechenwerk.py")
    (repo / "src" / "rechenwerk.py").write_text(KAPUTT)
    _git(repo, "add", "-A")
    _phase_setzen(repo, "phase5_tdd_red")
    r = _hook(repo)
    assert r.returncode == 2 and "test_rechner" in r.stderr, (
        "Ein Sammelfehler einer bestehenden Testdatei darf in Phase RED nicht als 'neu "
        f"angelegt' durchgehen (Exit {r.returncode})\n{r.stderr}"
    )


# --- Adversary-Runde 2 (#2503) ---------------------------------------------

FE_ZWEI_EBENEN_ALT = FE_KOPF + (
    "describe('aussen', () => {\n"
    "  describe('innen', () => {\n"
    "    test('verdopple alt', () => { assert.equal(verdopple(2), 4); });\n"
    "  });\n"
    "});\n"
)
FE_ZWEI_EBENEN_NEU = FE_KOPF + (
    "describe('aussen', () => {\n"
    "  describe('innen', () => {\n"
    "    test('verdopple alt', () => { assert.equal(verdopple(2), 4); });\n"
    "    test('verdopple neu tief', () => { assert.equal(verdopple(2), 5); });\n"
    "  });\n"
    "});\n"
)


def test_2503_f006_neuer_roter_test_zwei_ebenen_tief_in_phase_red_laesst_durch(tmp_path):
    """F006: `aussen > innen > neu` neu und rot, `aussen > innen` bestand schon.

    Die Zwischenebene ist alt — darf die Wurzel aber nicht zu neu_rot machen: Fuer die
    Elternregel zaehlen nur die roten BLAETTER.
    """
    repo = _frontend_repo_mit(tmp_path, FE_ZWEI_EBENEN_ALT, FE_ZWEI_EBENEN_NEU,
                              FE_QUELLE_HEIL + "// Aenderung\n")
    _phase_setzen(repo, "phase5_tdd_red")
    r = _hook(repo)
    assert r.returncode == 0, (
        f"Neuer roter Test zwei Ebenen tief muss in Phase RED durch (Exit "
        f"{r.returncode})\n{r.stderr}"
    )
    assert "verdopple neu tief" in r.stderr and NEU_ANGELEGT in r.stderr.lower(), r.stderr


def test_2503_f006b_altes_blatt_zwei_ebenen_tief_wird_rot_blockiert(tmp_path):
    """F006 Gegenprobe: das alte Blatt zwei Ebenen tief wird rot -> Exit 2, Wurzel genannt."""
    repo = _frontend_repo_mit(tmp_path, FE_ZWEI_EBENEN_ALT, FE_ZWEI_EBENEN_NEU,
                              FE_QUELLE_KAPUTT)
    _phase_setzen(repo, "phase5_tdd_red")
    r = _hook(repo)
    blockiert = [z.strip() for z in r.stderr.split("Einzeln nachstellen")[0].splitlines()]
    assert r.returncode == 2 and "aussen" in blockiert, (
        f"Altes, jetzt rotes Blatt muss blockieren und die Wurzel nennen (Exit "
        f"{r.returncode})\n{r.stderr}"
    )


GO_ZWEI_EBENEN_BASIS = GO_TEST_KOPF + (
    "func TestA(t *testing.T) {\n"
    '\tt.Run("sub", func(t *testing.T) {\n'
    '\t\tt.Run("alt", func(t *testing.T) { if Verdopple(2) != 4 { t.Fatal("alt") } })\n'
    "\t})\n}\n"
)
GO_ZWEI_EBENEN_NEU = GO_TEST_KOPF + (
    "func TestA(t *testing.T) {\n"
    '\tt.Run("sub", func(t *testing.T) {\n'
    '\t\tt.Run("alt", func(t *testing.T) { if Verdopple(2) != 4 { t.Fatal("alt") } })\n'
    '\t\tt.Run("neu", func(t *testing.T) { if Verdopple(2) != 5 { t.Fatal("neu") } })\n'
    "\t})\n}\n"
)


def test_2503_f006_go_neuer_subtest_zwei_ebenen_tief_in_phase_red_laesst_durch(tmp_path):
    """F006 (Go): `TestA/sub/neu` neu und rot, `TestA/sub` bestand schon -> Exit 0."""
    _go_oder_skip()
    repo = _go_repo(tmp_path, GO_ZWEI_EBENEN_BASIS, GO_ZWEI_EBENEN_NEU)
    _phase_setzen(repo, "phase5_tdd_red")
    r = _hook(repo)
    assert r.returncode == 0 and "TestA/sub/neu" in r.stderr, (
        f"Neuer Subtest zwei Ebenen tief muss in Phase RED durch (Exit {r.returncode})\n"
        + r.stderr
    )


def test_2503_f007_bestehende_frontend_datei_bricht_beim_import_blockiert(tmp_path):
    """F007-Umfeld: Eine BESTEHENDE Testdatei wirft beim Laden.

    node meldet dann `not ok 1 - <dateipfad>` — dieser Name lief im Vorzustand nie als
    Einzeltest. Ohne Gegenmassnahme gaelte die kaputte Datei in Phase RED als „neu
    angelegt" und ginge durch.
    """
    repo = _frontend_repo_mit(tmp_path, FE_TEST_ALT,
                              "throw new Error('kaputt beim Laden');\n" + FE_TEST_ALT,
                              FE_QUELLE_HEIL + "// Aenderung\n")
    _phase_setzen(repo, "phase5_tdd_red")
    r = _hook(repo)
    assert r.returncode == 2, (
        "Eine bestehende Testdatei, die nicht mehr laedt, darf in Phase RED nicht als "
        f"'neu angelegt' durchgehen (Exit {r.returncode})\n{r.stderr}"
    )
