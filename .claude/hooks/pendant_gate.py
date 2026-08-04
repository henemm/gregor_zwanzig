#!/usr/bin/env python3
"""Commit-Gate „Pendant-Sperre" — Issue #1481 Scheibe B.

Blockiert `git commit`, wenn eine NEU angelegte Datei in einem einseitigen Bereich liegt
(nur Vergleich **oder** nur Trip) und keine Begruendungszeile `gz-eigenstaendig: <Grund>`
im Kopf traegt. Der geteilte Bereich (`shared/**`, Renderer ohne `compare_`/`trip_`-Praefix)
loest die Sperre nie aus.

Warum es das gibt: CLAUDE.md verlangt seit langem „moeglichst viel Code zwischen Trip und
Ortsvergleich teilen" — bisher eine reine Textregel. Vier Paare existieren heute doppelt,
zwoelf Paritaets-Tests bewachen Paare, die bereits doppelt entstanden sind. Der Ausweg
verhindert nichts, er macht die Entscheidung im Aenderungssatz zitierbar.

Exit-Codes (Hook-Vertrag):
  0  durchlassen
  2  blockieren (stderr wird Claude gezeigt)

Nicht verhandelbar (AC-13): Eigene Stoerungen blockieren NIE.

Spec: docs/specs/modules/feat_1481b_pendant_gate.md
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

# Regel-Budget: ohne belegten Fang bis hierhin -> Rueckbau (Gate-Audit #1197).
PRUEFDATUM = date(2026, 11, 3)

MARKER = "gz-eigenstaendig:"
KOPF_ZEILEN = 20
MIN_ZEICHEN = 15
# Ab welcher von git gemeldeten Aehnlichkeit gilt eine Umbenennung als ECHT?
#
# 🔴 Adversary-Fund F007 (HIGH) + PO-Entscheidung 2026-08-04: Der Waechter setzte
# „aehnlicher Inhalt" mit „dasselbe Bauteil" gleich. Wird im selben Commit irgendeine
# Datei derselben Seite geloescht und eine neue angelegt, die zufaellig ein paar Zeilen
# teilt (jedes Svelte-Bauteil beginnt gleich), meldet git eine Umbenennung — und die
# gleichseitige Ausnahme liess die echte Neuanlage voellig UNGEPRUEFT durch.
#
# Beabsichtigtes Umbenennen-mit-Umschreiben und zufaellige Aehnlichkeit sind maschinell
# nicht unterscheidbar. PO-Entscheidung: Fehlalarm in Kauf nehmen, Umgehung schliessen.
# Die Ausnahme greift deshalb nur noch, wenn der Inhalt praktisch unveraendert ist.
# Messreihe zur Wahl der Grenze: docs/specs/modules/feat_1481b_pendant_gate.md.
ECHTE_UMBENENNUNG = 95

FE = "frontend/src/lib/components"
RENDERER = "src/output/renderers"
# Bereich -> (Seite, Praefix im Dateinamen)
FE_BEREICHE = {
    f"{FE}/compare/": ("compare", "compare"),
    f"{FE}/compare-new/": ("compare", "compare"),
    f"{FE}/trip-detail/": ("trip", "trip"),
    f"{FE}/trip-new/": ("trip", "trip"),
}
GEGENSEITE = {"compare": "trip", "trip": "compare"}
TEST_ENDUNGEN = (".test.ts", ".spec.ts", ".test.js", ".spec.js")

# Issue #1431: Commit-Erkennung ueber die Aufrufform, nicht ueber den Wortlaut.
#
# 🔴 Adversary-Fund F001 (CRITICAL): Der Import stand hier ungeschuetzt auf Modulebene.
# Faellt die Plugin-Aufloesung aus, stuerzt das Skript ab, BEVOR das Sicherheitsnetz in
# __main__ ueberhaupt existiert — Rueckgabewert 1, und der Commit ist blockiert. Genau
# das verbietet AC-13 („nicht verhandelbar").
#
# Und es wird NICHT geraten: Ein Rueckfall auf `f"git {sub}" in command` (wie in
# e2e_commit_gate.py) waere eine stille Zweitfassung genau des Defekts, den #1431
# beseitigt hat — fuer dessen Rueckbau bereits ein Auftrag laeuft
# (docs/context/fix-1431b-rueckfall-entfernen.md). Ohne das Werkzeug wird durchgelassen
# und gesagt, wie in Scheibe A.
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from hook_utils import is_git_subcommand  # noqa: E402
    WERKZEUG_FEHLT: str | None = None
except Exception as _fehler:  # noqa: BLE001
    is_git_subcommand = None  # type: ignore[assignment]
    WERKZEUG_FEHLT = f"{type(_fehler).__name__}: {_fehler}"

# Die GEPRUEFTE Kommandozerlegung aus hook_utils — bewusst KEIN Eigenbau: genau das
# Nachbauen einer Zerlegung hat in #1431 zweimal zu einem BROKEN gefuehrt. Der Name ist
# mit Unterstrich als hausintern markiert; fehlt er, wird nicht geraten, sondern der
# Commit ungeprueft durchgelassen und das gesagt (AC-13).
try:
    from hook_utils import _git_segments  # noqa: E402
except Exception:  # noqa: BLE001
    _git_segments = None  # type: ignore[assignment]


def _lauf(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=str(cwd), capture_output=True, text=True, timeout=60)


# Anzeichen dafuer, dass der Commit einen ANDEREN Ordner meint. Ein abgeschlossener,
# dokumentierter Satz — keine Liste von Hilfsprogrammen, keine Pfad-Aufloesung.
ANDERER_ORDNER = ("--git-dir", "--work-tree", "GIT_DIR=", "GIT_WORK_TREE=")


def _zielt_woanders_hin(befehl: str) -> tuple[bool, str | None]:
    """(zielt der Commit auf einen anderen Ordner?, Stoerung)

    🔴 Adversary-Funde F002 -> F006 -> F008 -> F010, vier Runden an DERSELBEN Stelle.
    Hier stand zuletzt eine Aufloesung, die aus dem Kommando herauslesen wollte, WO
    committet wird. Sie kannte genau einen der fuenf gemessenen Wege dorthin:

        git -C B commit                              erkannt
        cd B && git commit                           NICHT erkannt (der haeufigste!)
        git --git-dir=B/.git --work-tree=B commit    NICHT erkannt
        GIT_DIR=B/.git GIT_WORK_TREE=B git commit    NICHT erkannt
        (cd B && git commit)                         NICHT erkannt

    Die Frage „wo wird committet?" ist nicht zuverlaessig zu beantworten — es kommen
    immer neue Wege dazu (Aliase, Skripte, Schleifen). Die Frage, die der Waechter
    beantworten KANN, ist: „bin ich hier zustaendig?" Also prueft er immer sein eigenes
    Verzeichnis und laesst durch, sobald ein Anzeichen auf einen anderen Ordner deutet —
    durchlassen UND sagen, statt still den falschen Ordner zu messen.

    Warum die Anzeichen abschnittsweise geprueft werden und nicht im Rohtext: `grep -C 3
    muster datei && git commit` committet hier, das `-C` gehoert zu grep (F011). Deshalb
    zaehlen `-C` und die git-Optionen nur in einem Abschnitt, der auch wirklich `git`
    aufruft. Was VOR `git` steht, ist dabei egal — ob `sudo`, `timeout` oder `xargs`
    interessiert nicht mehr, und damit endet die Liste, die kein Ende hatte.
    """
    if _git_segments is None:
        return False, "Kommando-Zerleger aus hook_utils fehlt"
    segmente = _git_segments(befehl)
    if segmente is None:
        return False, "Kommando nicht verlaesslich zerlegbar"
    for tokens in segmente:
        # `cd` als Befehlswort — der haeufigste Weg in einen anderen Ordner (F010).
        if tokens and tokens[0] == "cd":
            return True, None
        if not any(t == "git" or t.endswith("/git") for t in tokens):
            continue
        for t in tokens:
            # `-C` nur als eigenes Token: in einer Commit-Nachricht steht es im Text und
            # bleibt damit Teil EINES Tokens. Eine geklebte Form gibt es nicht — `git
            # -C/pfad` lehnt git mit „unknown option" ab.
            if t == "-C" or t.startswith(ANDERER_ORDNER):
                return True, None
    return False, None

# --------------------------------------------------------------------------- Zuschnitt

def _bereich(pfad: str) -> tuple[str, str, str] | None:
    """(Seite, Bereichspfad, Namens-Praefix) — oder None fuer geteilt/unbeteiligt."""
    if pfad.endswith(TEST_ENDUNGEN):
        return None  # AC-6: die Ausnahme haengt an der ENDUNG, nicht am Ordner
    teile = pfad.split("/")
    if "tests" in teile or "__tests__" in teile:
        return None
    for bereich, (seite, praefix) in FE_BEREICHE.items():
        if pfad.startswith(bereich):
            return seite, bereich, praefix
    if pfad.startswith(RENDERER + "/") and pfad.endswith(".py"):
        name = pfad.rsplit("/", 1)[-1]
        for seite in ("compare", "trip"):
            if name.startswith(seite + "_"):  # rekursiv: email/compare_html.py zaehlt mit
                return seite, RENDERER + "/", seite + "_"
    return None


def _begruendet(wurzel: Path, pfad: str) -> bool:
    """Traegt der Dateikopf eine Begruendungszeile mit genug Substanz?

    Gelesen wird der VORGEMERKTE Stand — der kommt in den Commit, nicht der Arbeitsstand.
    Erkannt werden alle drei Formen (`#`, `//`, blosse Zeile im Modul-Docstring): der
    Marker wird ueberall in der Zeile gesucht. Die Python-Renderer haben gemessen gar keine
    `#`-Koepfe, nur Docstrings — ein reiner `#`-Ausdruck waere dort wirkungslos.
    """
    r = _lauf(["git", "show", f":{pfad}"], wurzel)
    inhalt = r.stdout if r.returncode == 0 else (wurzel / pfad).read_text(errors="replace")
    for zeile in inhalt.splitlines()[:KOPF_ZEILEN]:
        stelle = zeile.lower().find(MARKER)
        if stelle < 0:
            continue
        grund = zeile[stelle + len(MARKER):]
        if len(re.sub(r"[\W_]+", "", grund, flags=re.UNICODE)) >= MIN_ZEICHEN:
            return True
    return False


def _gegenstueck(wurzel: Path, pfad: str, seite: str, praefix: str) -> str | None:
    """Namensaehnliche Datei der Gegenseite — oder None. Nie geraten (AC-15)."""
    name = pfad.rsplit("/", 1)[-1]
    stamm, punkt, endung = name.partition(".")
    rest = stamm[len(praefix):] if stamm.lower().startswith(praefix) else stamm
    if not rest:
        return None
    gegen = GEGENSEITE[seite]
    orte = [b for b, (s, _) in FE_BEREICHE.items() if s == gegen] or [RENDERER + "/"]
    r = _lauf(["git", "ls-files", "--", *orte], wurzel)
    for kandidat in r.stdout.splitlines():
        k_name = kandidat.rsplit("/", 1)[-1]
        k_stamm, _, k_endung = k_name.partition(".")
        if k_endung != endung or not punkt:
            continue
        for k_praefix in (gegen, gegen + "_"):
            if k_stamm.lower().startswith(k_praefix):
                if k_stamm[len(k_praefix):].lower() == rest.lower():
                    return kandidat
    return None


# --------------------------------------------------------------------------- Hauptlauf

def main() -> int:
    try:
        eingabe = json.loads(sys.stdin.read() or "{}")
    except Exception:  # noqa: BLE001
        return 0
    befehl = (eingabe.get("tool_input") or {}).get("command", "")
    if WERKZEUG_FEHLT:  # F001: ohne Werkzeug wird nicht geraten, sondern gesagt
        print(f"[pendant_gate] gestoert: Werkzeug-Paket hook_utils nicht verfuegbar "
              f"({WERKZEUG_FEHLT}) — Commit UNGEPRUEFT durchgelassen. Es wird bewusst "
              "NICHT auf eine Wortlaut-Pruefung zurueckgefallen (#1431).", file=sys.stderr)
        return 0
    if not is_git_subcommand(befehl, "commit"):
        return 0

    if date.today() > PRUEFDATUM:
        print(f"[pendant_gate] Pruefdatum {PRUEFDATUM.isoformat()} abgelaufen — Gate "
              f"abgeschaltet, Commit ungeprueft (Rueckbau: Gate-Audit #1197).", file=sys.stderr)
        return 0

    if not shutil.which("git"):
        print("[pendant_gate] gestoert: kein `git` auffindbar — Commit ungeprueft "
              "durchgelassen.", file=sys.stderr)
        return 0

    woanders, zerlegungs_stoerung = _zielt_woanders_hin(befehl)
    if zerlegungs_stoerung:
        print(f"[pendant_gate] gestoert: {zerlegungs_stoerung} — Commit UNGEPRUEFT "
              "durchgelassen.", file=sys.stderr)
        return 0
    if woanders:
        print("[pendant_gate] Der Commit zielt auf einen anderen Ordner — hier wurde "
              "nicht geprueft. Der Waechter prueft immer das Verzeichnis, in dem er "
              "laeuft; wo ein Commit wirklich landet, ist ihm nicht zuverlaessig "
              "zugaenglich (siehe Spec, Abschnitt Nicht in dieser Scheibe).",
              file=sys.stderr)
        return 0
    wurzel = Path(os.getcwd())

    # F007: git-Voreinstellung. Die zwischenzeitlich abgesenkte Schwelle (25 %) brachte
    # nur MEHR zufaellige Umbenennungs-Meldungen — und die gleichseitige Ausnahme haengt
    # jetzt ohnehin an der gemeldeten Aehnlichkeit statt am blossen Vorliegen einer
    # Umbenennung. Gemessen: unverwandte Paare erreichen 25-61 %, echte Umbenennungen 95 %+.
    r = _lauf(["git", "diff", "--cached", "--name-status", "-M"], wurzel)
    if r.returncode != 0:
        print(f"[pendant_gate] gestoert: Vormerk-Stand nicht lesbar "
              f"({r.stderr.strip()[:120]}) — Commit ungeprueft.", file=sys.stderr)
        return 0

    neuzugaenge: list[str] = []
    for zeile in r.stdout.splitlines():
        teile = zeile.split("\t")
        if len(teile) < 2 or not teile[0]:
            continue
        if teile[0].startswith("R") and len(teile) >= 3:
            alt, neu = teile[1], teile[2]
            alte_seite = _bereich(alt)
            neue_seite = _bereich(neu)
            # AC-8: reines Umbenennen auf derselben Seite ist keine Neuanlage. AC-9: aus
            # der Gegenseite oder aus dem geteilten Bereich herein sehr wohl.
            #
            # 🔴 F007: „gleiche Seite" allein genuegt NICHT. Git meldet auch dann eine
            # Umbenennung, wenn eine unverwandte Datei geloescht und eine neue angelegt
            # wurde, die zufaellig ein paar Zeilen teilt — jedes Svelte-Bauteil beginnt
            # gleich. Die Ausnahme greift deshalb nur bei praktisch unveraendertem Inhalt.
            ziffern = teile[0][1:]
            aehnlichkeit = int(ziffern) if ziffern.isdigit() else 0
            if (neue_seite and alte_seite and alte_seite[0] == neue_seite[0]
                    and aehnlichkeit >= ECHTE_UMBENENNUNG):
                continue
            neuzugaenge.append(neu)
        elif teile[0].startswith("A"):
            neuzugaenge.append(teile[1])

    befunde: list[tuple[str, str, str | None]] = []
    for pfad in neuzugaenge:
        zuschnitt = _bereich(pfad)
        if not zuschnitt:
            continue
        seite, bereich, praefix = zuschnitt
        if _begruendet(wurzel, pfad):
            continue
        befunde.append((pfad, bereich, _gegenstueck(wurzel, pfad, seite, praefix)))

    if not befunde:
        return 0

    meldung = ["PENDANT-SPERRE (#1481 B) — neue Datei im einseitigen Bereich:"]
    for pfad, bereich, gegen in befunde:
        meldung.append(f"   {pfad}   [Bereich: {bereich}]")
        if gegen:
            meldung.append(f"      vermutetes Gegenstueck: {gegen}")
    meldung += [
        "",
        "Zwei Wege durch:",
        f"   1. In den geteilten Bereich legen: {FE}/shared/ bzw. Renderer ohne "
        "compare_/trip_-Praefix.",
        f"   2. Begruendungszeile in die ersten {KOPF_ZEILEN} Zeilen setzen "
        f"(#, // oder blosse Docstring-Zeile):",
        "      gz-eigenstaendig: <fachlicher Grund, mindestens 15 sinnvolle Zeichen>",
        "",
        f"CLAUDE.md -> Trip/Ortsvergleich-Code-Teilung. Pruefdatum dieses Gates: "
        f"{PRUEFDATUM.isoformat()}.",
    ]
    print("\n".join(meldung), file=sys.stderr)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001 — AC-13: eine eigene Stoerung blockiert NIE
        print(f"[pendant_gate] gestoert, Commit nicht blockiert: {e}", file=sys.stderr)
        sys.exit(0)
