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
