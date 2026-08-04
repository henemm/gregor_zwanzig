#!/usr/bin/env python3
"""Commit-Gate „Tests der beruehrten Dateien" — Issue #1481 Scheibe A.

Blockiert `git commit`, wenn eine Aenderung einen Test rot macht, der zu einer der
geaenderten Dateien gehoert. Verallgemeinert das seit #811 bewaehrte
`renderer_mail_gate.py` auf alle drei Schichten, statt ein zweites Werkzeug danebenzustellen.

Warum es das gibt: Bei #1453 stand der passende Waechter ZWEI TAGE rot und meldete den
Fehler korrekt — gelesen hat den Lauf niemand. Die Information war da, sie hat nur nichts
blockiert.

Exit-Codes (Hook-Vertrag):
  0  durchlassen
  2  blockieren (stderr wird Claude gezeigt)

Nicht verhandelbar (AC-7): Eigene Stoerungen blockieren NIE. Ein defektes Gate darf nicht
die Ursache sein, dass nicht mehr gearbeitet werden kann.

Spec: docs/specs/modules/feat_1481a_touched_tests_gate.md
"""
from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import sys
from pathlib import Path

ZEITGRENZE = 300          # Sekunden je Schicht
MAX_TESTDATEIEN = 40      # Notbremse gegen Ausreisser-Aenderungen

QUELL_SCHICHTEN = {
    "python": (("src/", "api/"), ".py"),
    "go": (("internal/", "cmd/"), ".go"),
    "frontend": (("frontend/src/",), (".svelte", ".ts")),
}


# ---------------------------------------------------------------------------
# Grundlagen
# ---------------------------------------------------------------------------

def _lauf(args: list[str], cwd: Path, zeitgrenze: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=str(cwd), capture_output=True, text=True,
                          timeout=zeitgrenze)


def _gestagte_dateien(wurzel: Path) -> tuple[list[str], list[str]]:
    """(geaenderte Dateien, alte Namen umbenannter Dateien).

    Adversary-Fund F003: Wird ein Modul umbenannt und dabei kaputt gemacht, sucht die
    Zuordnung nur nach dem NEUEN Namen — die zugehoerige Testdatei nennt aber noch den
    alten und wird nie gefunden. Das Gate meldete dann „keine Tests gefunden" und liess
    durch, obwohl der Testlauf an einem Importfehler zerbricht. Deshalb reisen die alten
    Namen mit.
    """
    r = _lauf(["git", "diff", "--cached", "--name-status", "-M"], wurzel)
    dateien: list[str] = []
    alte: list[str] = []
    for zeile in r.stdout.splitlines():
        teile = zeile.split("\t")
        if not teile or not teile[0]:
            continue
        if teile[0].startswith("R") and len(teile) >= 3:
            alte.append(teile[1])
            dateien.append(teile[2])
        elif len(teile) >= 2:
            dateien.append(teile[1])
    return dateien, alte


def _schicht(pfad: str) -> str | None:
    for name, (praefixe, endungen) in QUELL_SCHICHTEN.items():
        if pfad.startswith(praefixe) and pfad.endswith(endungen):
            return name
    return None


def _vorzustand_messen(wurzel: Path, schicht: str, ziele: list[str],
                       laeufer) -> tuple[set[str], str | None]:
    """Welche dieser Tests waren schon VOR der Aenderung rot? (gemessen, nicht geglaubt)

    🔴 **Warum es hier keine gepflegte Liste gibt** (Adversary F001/F001b, beide CRITICAL):
    Der erste Entwurf hielt bekannte Fehlschlaege in einer Datei. Die liess sich mit einem
    einzigen Schreibzugriff faelschen. Die Bindung an den committeten Stand verschob das
    Problem nur: Ein Commit, der NUR diese Liste aendert, beruehrt keine Quelldatei und
    laeuft am Gate vorbei — in zwei Schritten blieb die Ratsche wertlos.

    **Eine Liste, die gepflegt werden muss, ist immer faelschbar.** Also wird nichts
    gepflegt: Der Vorzustand wird an einem Wegwerf-Abzug des letzten Commits GEMESSEN.

    Kosten: ein zweiter Testlauf, und zwar nur dann, wenn ueberhaupt etwas rot ist.
    """
    # Adversary-Fund F008: Ein harter Abbruch (SIGKILL, aeusseres Zeitlimit) laesst den
    # `finally`-Block nie laufen — die Registrierung bliebe dauerhaft im echten Repo
    # stehen. Zwei Netze: hier vorab die Leichen frueherer Laeufe entfernen, und unten
    # ein Handler fuer den abfangbaren Abbruch (SIGTERM). Gegen SIGKILL hilft nur das
    # Aufraeumen beim naechsten Lauf.
    _lauf(["git", "worktree", "prune"], wurzel, 30)

    tmp = Path(tempfile.mkdtemp(prefix="gz-vorzustand-"))
    abzug = tmp / "stand"
    try:
        r = _lauf(["git", "worktree", "add", "--detach", "-q", str(abzug), "HEAD"], wurzel, 120)
        if r.returncode != 0:
            return set(), f"Vorzustand nicht messbar ({r.stderr.strip()[:80]})"
        vorher, stoerung = laeufer(abzug, ziele)
        if stoerung:
            return set(), f"Vorzustand nicht messbar ({stoerung})"
        return vorher, None
    except Exception as e:
        return set(), f"Vorzustand nicht messbar ({e})"
    finally:
        _lauf(["git", "worktree", "remove", "--force", str(abzug)], wurzel, 60)
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Zuordnung Quelldatei -> Tests
# ---------------------------------------------------------------------------

def _python_tests(wurzel: Path, dateien: list[str]) -> list[str]:
    """Testdateien, die das geaenderte Modul beim Namen nennen.

    ⚠️ **Bewusst nur `tests/unit/`** — zwei Gruende, beide gemessen:
    1. **Sicherheit.** `tests/tdd/` enthaelt Tests, die echten Versand ausloesen. Der
       Marker-Ausschluss allein reicht nicht: am 2026-08-03 genuegte EINE ungemarkerte
       Datei fuer echte Telegram-Nachrichten an den Produktiv-Chat (#1477). Ein Gate, das
       bei JEDEM Commit laeuft, darf dieses Risiko nicht tragen.
    2. **Wirksamkeit.** Ueber ganz `tests/` fand die Zuordnung fuer `compare_html.py`
       **72** Dateien und lief in die Notbremse — ausgerechnet bei der Datei, deren Fehler
       (#1451, #1453) den Anstoss gaben. Auf `tests/unit/` sind es 20 Dateien in 8
       Sekunden, und der Waechter, der #1453 zwei Tage lang ungelesen meldete, ist dabei.

    `tests/tdd/` bleibt damit ungeprueft — das MUSS die Meldung sagen (AC-12), sonst sieht
    „Commit ging durch" nach mehr aus, als es ist.
    """
    treffer: set[str] = set()
    for d in dateien:
        modul = Path(d).stem
        if not modul or modul == "__init__":
            continue
        r = _lauf(["git", "grep", "-l", "-w", modul, "--", "tests/unit/"], wurzel)
        treffer.update(z for z in r.stdout.splitlines()
                       if z.endswith(".py") and Path(z).name.startswith("test_"))
    return sorted(treffer)


def _go_pakete(dateien: list[str]) -> list[str]:
    """In Go liegt der Test im selben Paket — die Zuordnung ist das Verzeichnis."""
    return sorted({"./" + str(Path(d).parent) + "/" for d in dateien})


def _frontend_tests(wurzel: Path, dateien: list[str]) -> list[str]:
    treffer: set[str] = set()
    for d in dateien:
        stamm = Path(d).stem
        if not stamm:
            continue
        r = _lauf(["git", "grep", "-l", "-w", stamm, "--", "frontend/src/"], wurzel)
        treffer.update(z for z in r.stdout.splitlines() if ".test." in z)
    return sorted(treffer)


# ---------------------------------------------------------------------------
# Testlaeufe je Schicht
# ---------------------------------------------------------------------------

def _pytest_befehl(wurzel: Path) -> list[str]:
    if shutil.which("uv") and (wurzel / "pyproject.toml").exists():
        return ["uv", "run", "pytest"]
    return [sys.executable, "-m", "pytest"]


def _lauf_python(wurzel: Path, tests: list[str]) -> tuple[set[str], str | None]:
    """(fehlgeschlagene Test-Kennungen, Stoermeldung)."""
    befehl = _pytest_befehl(wurzel) + [
        "-q", "-p", "no:randomly", "--no-header",
        # AC-5: die Live-Schicht bleibt draussen, sonst loest ein Commit echten Versand aus
        "-m", "not live and not email and not staging",
        *tests,
    ]
    try:
        r = _lauf(befehl, wurzel, ZEITGRENZE)
    except Exception as e:
        return set(), f"Python-Tests nicht ausfuehrbar ({e})"
    # pytest-Rueckgabewerte: 0 gruen · 1 Tests rot · 2 Abbruch/Sammelfehler · 3 interner
    # Fehler · 4 Aufruffehler · 5 nichts gesammelt.
    # ⚠️ Die 2 gehoert auf die Fehlschlag-Seite, nicht auf die Stoerungs-Seite: Ein
    # Importfehler (z.B. nach einer Modul-Umbenennung, Adversary-Fund F003) bricht die
    # Sammlung ab — der Testlauf hat dann NICHT stattgefunden, und genau das darf nicht
    # als „alles in Ordnung" durchgehen. Der erste Entwurf hat hier durchgelassen.
    if r.returncode == 5:
        return set(), "keine Tests gesammelt"
    if r.returncode not in (0, 1, 2):
        return set(), f"Python-Testlauf gestoert (Exit {r.returncode})"
    # Auch Sammel-Fehler zaehlen: Ein Importfehler meldet `ERROR <datei>`, nicht `FAILED`.
    # Genau so sieht eine Modul-Umbenennung aus (Adversary-Fund F003) — wer nur nach
    # FAILED sucht, laesst eine Testdatei durch, die gar nicht mehr startet.
    return (set(re.findall(r"^FAILED (\S+)", r.stdout, re.M))
            | set(re.findall(r"^ERROR (\S+)", r.stdout, re.M))), None


def _lauf_go(wurzel: Path, pakete: list[str]) -> tuple[set[str], str | None]:
    go = shutil.which("go") or "/usr/local/go/bin/go"
    if not Path(go).exists():
        return set(), "Go-Werkzeug nicht gefunden — Go-Dateien UNGEPRUEFT"
    try:
        r = _lauf([go, "test", *pakete], wurzel, ZEITGRENZE)
    except Exception as e:
        return set(), f"Go-Tests nicht ausfuehrbar ({e}) — Go-Dateien UNGEPRUEFT"
    if r.returncode == 0:
        return set(), None
    fehl = set(re.findall(r"^--- FAIL: (\S+)", r.stdout, re.M))
    if fehl:
        return fehl, None
    # ⚠️ Der Unterschied, der beim ersten Anlauf gefehlt hat: Ein Lauf, der gar nicht
    # STATTFINDEN konnte (kein go.mod, Uebersetzungsfehler, fehlende Abhaengigkeit),
    # meldet ebenfalls Exit != 0 — er ist aber eine Stoerung, kein roter Test. Wer beides
    # gleichsetzt, blockiert Arbeit wegen eines Werkzeugproblems (AC-7/AC-12).
    grund = (r.stderr or r.stdout).strip().splitlines()
    return set(), ("Go-Lauf nicht moeglich — Go-Dateien UNGEPRUEFT"
                   + (f": {grund[0][:120]}" if grund else ""))


def _lauf_frontend(wurzel: Path, tests: list[str]) -> tuple[set[str], str | None]:
    fe = wurzel / "frontend"
    lader = fe / "test-lib-loader.mjs"
    if not (fe / "node_modules").exists() or not lader.exists():
        return set(), "Frontend-Abhaengigkeiten fehlen — Frontend-Dateien UNGEPRUEFT"
    rel = [str(Path(t).relative_to("frontend")) for t in tests]
    try:
        r = _lauf(["node", "--import", "./test-lib-loader.mjs",
                   "--experimental-strip-types", "--test", *rel], fe, ZEITGRENZE)
    except Exception as e:
        return set(), f"Frontend-Tests nicht ausfuehrbar ({e}) — UNGEPRUEFT"
    if r.returncode == 0:
        return set(), None
    return set(re.findall(r"^not ok \d+ - (.+)$", r.stdout, re.M)) or {"frontend: rot"}, None


# ---------------------------------------------------------------------------
# Hauptlauf
# ---------------------------------------------------------------------------

def main() -> int:
    try:
        eingabe = json.loads(sys.stdin.read() or "{}")
    except Exception:
        return 0
    befehl = (eingabe.get("tool_input") or {}).get("command", "")
    if "git commit" not in befehl:
        return 0  # AC-8

    wurzel = Path(os.getcwd())
    dateien, alte_namen = _gestagte_dateien(wurzel)
    nach_schicht: dict[str, list[str]] = {}
    for d in dateien + alte_namen:  # F003: alte Namen umbenannter Module zaehlen mit
        s = _schicht(d)
        if s:
            nach_schicht.setdefault(s, []).append(d)
    if not nach_schicht:
        return 0  # AC-8

    hinweise: list[str] = []
    neu_rot: list[tuple[str, str]] = []
    vorbestehend: list[str] = []
    geprueft: list[str] = []
    ziele_je_schicht: dict[str, list[str]] = {}

    laeufe = {
        "python": lambda ds: (_python_tests(wurzel, ds), _lauf_python),
        "go": lambda ds: (_go_pakete(ds), _lauf_go),
        "frontend": lambda ds: (_frontend_tests(wurzel, ds), _lauf_frontend),
    }

    for schicht, ds in nach_schicht.items():
        ziele, laeufer = laeufe[schicht](ds)
        if not ziele:
            hinweise.append(f"{schicht}: keine zugehoerigen Tests gefunden — UNGEPRUEFT")
            continue
        if len(ziele) > MAX_TESTDATEIEN:
            hinweise.append(
                f"{schicht}: {len(ziele)} Testdateien — zu breit, UNGEPRUEFT "
                f"(Notbremse bei {MAX_TESTDATEIEN})"
            )
            continue
        fehlschlaege, stoerung = laeufer(wurzel, ziele)
        if stoerung:
            hinweise.append(f"{schicht}: {stoerung}")
            continue
        geprueft.append(f"{schicht} ({len(ziele)})")
        ziele_je_schicht[schicht] = ziele
        if schicht == "python":
            hinweise.append("python: tests/tdd/ bleibt UNGEPRUEFT (Versandrisiko, s. #1477)")
        if not fehlschlaege:
            continue
        # Erst jetzt — und nur jetzt — kostet es einen zweiten Lauf: War das schon vorher rot?
        vorher, vorher_stoerung = _vorzustand_messen(wurzel, schicht, ziele, laeufer)
        if vorher_stoerung:
            # 🔴 Adversary-Fund F007 (CRITICAL): Hier stand vorher „alle Fehlschlaege
            # gelten als NEU" — und damit blockierte eine gescheiterte MESSUNG den Commit,
            # obwohl der Test nachweislich schon vorher rot war. Genau das verbietet AC-7,
            # und an sieben anderen Stellen dieser Datei wird es auch eingehalten: eine
            # Stoerung des Gates fuehrt zu „durchlassen und sagen", nie zu „blockieren".
            # Der Erfolgspfad war sorgfaeltig gebaut, der Stoerungspfad nicht — dieselbe
            # blinde Stelle wie bei den beiden Funden davor.
            hinweise.append(
                f"{schicht}: {vorher_stoerung} — Vorzustand UNBEKANNT, deshalb nicht "
                f"blockiert; {len(fehlschlaege)} Fehlschlag/Fehlschlaege ungeprueft"
            )
            for f in sorted(fehlschlaege):
                vorbestehend.append(f"{f} (Vorzustand unbekannt)")
            continue
        for f in sorted(fehlschlaege):
            if f in vorher:
                vorbestehend.append(f)
            else:
                neu_rot.append((schicht, f))

    meldung: list[str] = []
    if geprueft:
        meldung.append("Geprueft: " + ", ".join(geprueft))
    for h in hinweise:
        meldung.append("HINWEIS  " + h)
    for v in vorbestehend:
        meldung.append(f"vorbestehend rot (blockiert nicht): {v}")

    if neu_rot:
        meldung.insert(0, "BLOCKIERT — diese Aenderung macht Tests rot:")
        for _, n in neu_rot:
            meldung.insert(1, f"   {n}")
        meldung.append("")
        meldung.append("Einzeln nachstellen:")
        # Adversary-Fund F005: Der Reparaturbefehl haing fest an pytest — bei einem
        # Go-Fehlschlag stand dort „uv run pytest TestVerdopple", was schlicht nicht
        # laeuft. Der Befehl gehoert zur Schicht, aus der der Fehlschlag stammt.
        # 🔴 Adversary-Fund F005b: Die erste Fassung nannte fuer Go `go test <Testname>`
        # (sucht ein PAKET dieses Namens) und fuers Frontend `npm test -- <TAP-Text>`
        # (erwartet einen DATEIPFAD — meldete „Could not find" und trotzdem Erfolg).
        # Beide Befehle waren nicht lauffähig, weil ich sie nie ausgefuehrt habe.
        # Deshalb: Paket bzw. Dateipfad kommen aus `ziele_je_schicht`, nicht aus dem
        # Testnamen — und ein Test fuehrt die Zeilen jetzt wirklich aus.
        for schicht in dict.fromkeys(s for s, _ in neu_rot):
            namen = [n for s, n in neu_rot if s == schicht][:5]
            ziele = ziele_je_schicht.get(schicht, [])
            if schicht == "go":
                muster = "|".join(n.split("/")[-1] for n in namen)
                meldung.append(f"   go test -run '{muster}' " + " ".join(ziele))
            elif schicht == "frontend":
                meldung.append("   cd frontend && node --import ./test-lib-loader.mjs "
                               "--experimental-strip-types --test "
                               + " ".join(z[len("frontend/"):] for z in ziele[:5]))
            else:
                meldung.append("   uv run pytest "
                               + " ".join(sorted({n.split("::")[0] for n in namen})))
        meldung.append("Reparieren oder loeschen — nicht drumherum arbeiten.")
        print("\n".join(meldung), file=sys.stderr)
        return 2

    if meldung:
        print("\n".join(meldung), file=sys.stderr)
    return 0


def _bei_abbruch(signalnummer, rahmen):  # noqa: ARG001 — Signatur ist vorgegeben
    """SIGTERM: aufraeumen und durchlassen (F008). SIGKILL kann niemand abfangen —
    dagegen wirkt das `git worktree prune` zu Beginn der naechsten Messung."""
    try:
        _lauf(["git", "worktree", "prune"], Path(os.getcwd()), 30)
    except Exception:
        pass
    sys.exit(0)


if __name__ == "__main__":
    try:
        signal.signal(signal.SIGTERM, _bei_abbruch)
    except Exception:
        pass  # Signalbehandlung ist ein Sicherheitsnetz, kein Muss
    try:
        sys.exit(main())
    except Exception as e:  # AC-7: eine eigene Stoerung blockiert NIE
        print(f"[touched_tests_gate] gestoert, Commit nicht blockiert: {e}", file=sys.stderr)
        sys.exit(0)
