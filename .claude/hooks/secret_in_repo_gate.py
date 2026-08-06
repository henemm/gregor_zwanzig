#!/usr/bin/env python3
"""Commit-Gate „Secret-in-Repo-Sperre" — Issue #1537 Scheibe 1 (Stufe C).

Blockiert `git commit`, wenn eine der zum Commit vorgemerkten Dateien den
AUSGESCHRIEBENEN Wert eines Geheimnisses aus der lokalen `.env` enthaelt
(Schluessel endet auf `_PASS`, `_TOKEN`, `_KEY` oder `_SECRET`, Wert mind.
10 Zeichen lang).

Anlass: `secret_egress_guard.py` (Plugin, #1380) prueft nur, ob ein Geheimnis
als Literal IM BEFEHL steht. Ein Wert, der zur Laufzeit aus einer Datei
gelesen und in eine andere geschrieben wird (z.B. per Edit/Write-Tool, nicht
per Bash-Kommando), laeuft daran vorbei — genau so ist #1537 entstanden
(`GZ_AUTH_PASS` im Klartext in `frontend/.env.test` und einem Archiv-Dokument).
Dieses Gate schliesst die Luecke NICHT beim Schreiben, sondern an der letzten
moeglichen Stelle davor: dem Commit selbst.

Exit-Codes (Hook-Vertrag):
  0  durchlassen
  2  blockieren (stderr wird Claude gezeigt)

Drei Ausgaenge (Tech-Lead-Entscheid #1537 Runde 3):

  1. Commit erkannt, KEIN Umlenkungs-Anzeichen (oder -C/--git-dir/--work-tree
     loest sauber auf)                                 -> dort pruefen (0/2
                                                            je nach Fund)
  2. Commit erkannt, ein Anzeichen fuer ein moeglicherweise ANDERES Ziel
     (cd-Umlenkung, GIT_DIR=/GIT_WORK_TREE= als Env-Zuweisung, unbekanntes
     Hilfsprogramm davor, verschachtelte Shell/eval, nicht sauber aufloesbares
     -C/--git-dir/--work-tree)                          -> BLOCKIEREN (Exit 2)
  3. Eigene Stoerung (git fehlt, .env unlesbar, Zerlegungs-Werkzeug fehlt)
                                                          -> durchlassen, sagen

Warum Zeile 2 blockiert statt durchzulassen: bei einem Struktur-Waechter wie
`pendant_gate.py` (#1481 Scheibe B) kostet ein verpasster Fall Doppelarbeit —
"durchlassen und sagen" ist dort vertretbar (und dort auch die etablierte
Loesung, nach vier Adversary-Runden F002->F006->F008->F010, die alle an
derselben Frage "wo wird committet?" scheiterten). Bei DIESEM Gate stellt ein
verpasster Fall ein gueltiges Passwort ins oeffentliche Internet — "durchlassen
und sagen" waere hier ein stilles Sicherheitsloch. Zeile 2 ist deshalb KEIN
Defekt des Waechters, sondern ein Fall, den er nachweislich nicht pruefen
kann; das ist zumutbar, weil immer ein erlaubter Weg offensteht (einfacher
`git commit` im eigenen Ordner oder `git -C <pfad> commit`) — die
Blockade-Meldung nennt diesen Weg ausdruecklich.

Vorgeschichte: Runde 1 dieses Gates nahm das Ziel per `os.getcwd()` (F001:
bei `git -C <anderswo> commit` falsch). Runde 2 versuchte, die #1481-Loesung
("Anzeichen? -> trotzdem eigenes Verzeichnis pruefen und sagen") 1:1 zu
uebernehmen — fuer ein Sicherheits-Gate falsch, siehe oben.

Nicht verhandelbar: Eigene Stoerungen (Zeile 3) blockieren NIE — ein
defektes Gate darf nicht die Ursache sein, dass nicht mehr gearbeitet werden
kann. Ein GEFUNDENES Geheimnis UND ein nicht sicher bestimmbares Ziel
blockieren dagegen hart.

Strikte Auflage: Geheimniswerte werden AUSSCHLIESSLICH im Arbeitsspeicher
dieses einen Prozesses gehalten — nie in eine Datei geschrieben, nie in
Log-/Fehlermeldungen ausgegeben. Meldungen nennen nur Dateiname + Schluessel.

Regel-Budget: dieses Gate schliesst eine akut ausgenutzte Sicherheitsluecke
(oeffentliches Repo, gueltige Zugangsdaten im Klartext) — anders als die
prozessualen Commit-Gates schaltet es sich deshalb NICHT nach einem
Pruefdatum automatisch ab. Wirksamkeits-Pruefung (Regel-Budget-Ledger):
2026-11-04.

Verdrahtung: `.claude/settings.json`, geschuetzte Form
`if [ -f … ]; then python3 … ; fi` (Vorbild: `pendant_gate.py`, #1481 B) —
ohne diese Form legt ein noch nicht nachgezogener Hauptordner jede Sitzung
lahm (#1307 A).
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

# Schluessel-Endungen, deren Wert als Geheimnis gilt. Bewusst eng (keine
# breite Regex wie im Egress-Guard) — sonst traefe z.B. der Projektname
# "gregor_zwanzig" ueberall.
_SECRET_KEY_SUFFIXES = ("_PASS", "_TOKEN", "_KEY", "_SECRET")
# Unterhalb dieser Laenge sind es fast immer Benutzernamen oder kurze
# Konfigwerte, keine echten Geheimnisse.
_MIN_WERT_LAENGE = 10
# Zu grosse Dateien werden nicht gescannt (Notbremse, kein Fehler) — echte
# Geheimnisse in mehrstelligen-MB-Dateien sind unrealistisch, das Einlesen
# waere aber teuer.
_MAX_DATEI_BYTES = 2 * 1024 * 1024

# Issue #1431: Commit-Erkennung ueber die Aufrufform, nicht ueber den
# Wortlaut. Ohne das Werkzeug wird NICHT auf `"git commit" in befehl`
# zurueckgefallen (das waere die stille Zweitfassung genau des Defekts, den
# #1431 beseitigt hat) — sondern durchgelassen und gesagt (siehe main()).
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from hook_utils import is_git_subcommand  # noqa: E402
    WERKZEUG_FEHLT: str | None = None
except Exception as _fehler:  # noqa: BLE001
    is_git_subcommand = None  # type: ignore[assignment]
    WERKZEUG_FEHLT = f"{type(_fehler).__name__}: {_fehler}"

# Fuer die Sicherheitslage-Einstufung (F001) werden dieselben GEPRUEFTEN
# Zerlegungs-Bausteine wie oben nachgeladen — bewusst KEIN eigener Tokenizer
# (#1431: zweimal BROKEN durch nachgebaute Zerlegung). Eigener Import, weil
# diese (mit Unterstrich als hausintern markierten) Namen in einer aelteren
# Plugin-Version fehlen koennten, waehrend is_git_subcommand schon vorhanden
# ist.
try:
    from hook_utils import (  # noqa: E402
        _ENV_ASSIGN_RE,
        _GIT_COMMAND_PREFIXES,
        _GIT_OPTS_WITH_VALUE,
        _GIT_SHELL_BINARY_RE,
        _git_segments,
        _git_subcommand_of_segment,
        _git_subcommands_in_segment,
        git_subcommands,
    )
    ZIEL_WERKZEUG_FEHLT: str | None = None
except Exception as _fehler2:  # noqa: BLE001
    _git_segments = None  # type: ignore[assignment]
    ZIEL_WERKZEUG_FEHLT = f"{type(_fehler2).__name__}: {_fehler2}"


def _lauf(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=str(cwd), capture_output=True, text=True, timeout=60)


# ------------------------------------------------------------- Sicherheitslage


def _commit_sicherheitslage(befehl: str) -> tuple[str, list[Path], str | None]:
    """Bestimmt, WO der commit-Aufruf sicher geprueft werden kann.

    Rueckgabe (lage, wurzeln, grund):
      "sicher"    -> wurzeln enthaelt >=1 Pfad, dort wird geprueft
      "unsicher"  -> wurzeln ist leer, BLOCKIEREN (grund nennt die Ursache)
      "gestoert"  -> wurzeln ist leer, DURCHLASSEN (grund nennt die eigene
                     Stoerung — z.B. fehlendes Zerlegungs-Werkzeug)

    Nur Segmente, die tatsaechlich `git` aufrufen, werden auf Ziel-Anzeichen
    durchsucht — sonst waere `grep -C 3 muster datei && git commit` ein
    Fehlalarm (`-C` gehoert dort zu `grep`, nicht zu `git`).
    """
    if _git_segments is None:
        return "gestoert", [], (
            f"Zerlegungs-Baustein fuer die Ziel-Erkennung fehlt ({ZIEL_WERKZEUG_FEHLT})"
        )
    segmente = _git_segments(befehl)
    if segmente is None:
        return "unsicher", [], "Kommando nicht verlaesslich zerlegbar (kaputte/unklare Quotes)"

    if any(tokens and tokens[0] == "cd" for tokens in segmente):
        return "unsicher", [], "Kommando enthaelt 'cd' vor dem Commit — Ziel nicht sicher bestimmbar"

    wurzeln: list[Path] = []
    fand_commit_segment = False

    for tokens in segmente:
        # Verschachtelte Shell (`sh -c "..."`, `eval ...`): IMMER unsicher, wenn
        # darin ein commit steckt — unabhaengig davon, was sonst noch drinsteht.
        for i, tok in enumerate(tokens):
            basis = tok.rsplit("/", 1)[-1]
            if _GIT_SHELL_BINARY_RE.match(basis) and i + 2 < len(tokens) and tokens[i + 1] == "-c":
                if "commit" in git_subcommands(tokens[i + 2]):
                    return "unsicher", [], "Commit steckt in einer verschachtelten Shell (sh -c/bash -c)"
            elif basis == "eval":
                for rest in tokens[i + 1:]:
                    if "commit" in git_subcommands(rest):
                        return "unsicher", [], "Commit steckt in einem `eval`-Aufruf"

        if not any(t == "git" or t.endswith("/git") for t in tokens):
            continue  # dieses Segment ruft gar kein git auf
        if "commit" not in _git_subcommands_in_segment(tokens):
            continue  # dieses Segment betrifft keinen commit

        fand_commit_segment = True

        if _git_subcommand_of_segment(tokens) != "commit":
            # `git` steht nicht kopf-gebunden (ggf. nach bekannten transparenten
            # Praefixen/Env-Zuweisungen) vor `commit` — ein NICHT erkanntes
            # Hilfsprogramm (timeout/flock/xargs/Schleife/...) steht davor.
            return "unsicher", [], "Commit-Aufruf steht hinter einem nicht erkannten Hilfsprogramm"

        i = 0
        while i < len(tokens) and (
            _ENV_ASSIGN_RE.match(tokens[i]) or tokens[i] in _GIT_COMMAND_PREFIXES
        ):
            if tokens[i].startswith(("GIT_DIR=", "GIT_WORK_TREE=")):
                return "unsicher", [], "GIT_DIR/GIT_WORK_TREE als Umgebungszuweisung vor dem Commit"
            i += 1
        # tokens[i] ist an dieser Stelle 'git' (durch den kopf-gebundenen Treffer oben).
        j = i + 1
        praefix: list[str] = []
        while j < len(tokens):
            tok = tokens[j]
            if tok in _GIT_OPTS_WITH_VALUE:
                if j + 1 >= len(tokens):
                    j += 1
                    break
                praefix.extend([tok, tokens[j + 1]])
                j += 2
                continue
            if tok.startswith("-"):
                praefix.append(tok)
                j += 1
                continue
            break

        ziel_flags = [t for t in praefix if t == "-C" or t.startswith(("--git-dir", "--work-tree"))]
        if not ziel_flags:
            wurzeln.append(Path.cwd())
            continue

        r = _lauf(["git", *praefix, "rev-parse", "--show-toplevel"], Path.cwd())
        if r.returncode != 0 or not r.stdout.strip():
            return "unsicher", [], (
                "-C/--git-dir/--work-tree loest nicht sauber auf "
                f"({r.stderr.strip()[:120] or 'kein Pfad zurueckgegeben'})"
            )
        wurzeln.append(Path(r.stdout.strip()))

    if not fand_commit_segment:
        # Defensiv: sollte wegen der vorherigen is_git_subcommand-Pruefung in
        # main() nicht vorkommen. Im Zweifel unsicher, nicht raten.
        return "unsicher", [], "Kein commit-Segment in der Zerlegung gefunden, obwohl einer erkannt wurde"

    eindeutig: list[Path] = []
    gesehen_pfade: set[str] = set()
    for w in wurzeln:
        schluessel = str(w)
        if schluessel not in gesehen_pfade:
            gesehen_pfade.add(schluessel)
            eindeutig.append(w)
    return "sicher", eindeutig, None


# --------------------------------------------------------------------- .env


def _parse_env_zeilen(text: str) -> list[tuple[str, str]]:
    """Minimal-Parser: KEY=WERT je Zeile, Anfuehrungszeichen und `export `
    werden entfernt, Kommentare und Leerzeilen uebersprungen."""
    paare: list[tuple[str, str]] = []
    for zeile in text.splitlines():
        zeile = zeile.strip()
        if not zeile or zeile.startswith("#") or "=" not in zeile:
            continue
        if zeile.startswith("export "):
            zeile = zeile[len("export "):].lstrip()
        schluessel, _, wert = zeile.partition("=")
        schluessel = schluessel.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", schluessel):
            continue
        wert = wert.strip()
        if len(wert) >= 2 and wert[0] == wert[-1] and wert[0] in ("'", '"'):
            wert = wert[1:-1]
        else:
            wert = re.split(r"\s+#", wert, maxsplit=1)[0].strip()
        paare.append((schluessel, wert))
    return paare


def _lade_geheimnisse(env_pfad: Path) -> tuple[list[tuple[str, str]], str | None]:
    """(Schluessel, Wert)-Paare aus der lokalen `.env`, deren Schluessel auf
    einen der gesuchten Suffixe endet und deren Wert lang genug ist. Wird bei
    jedem Lauf frisch gelesen (kein Cache) — sonst greift das Gate nach einer
    Rotation ins Leere."""
    try:
        text = env_pfad.read_text(errors="ignore")
    except OSError as fehler:
        return [], f".env nicht lesbar ({fehler})"
    geheimnisse: list[tuple[str, str]] = []
    for schluessel, wert in _parse_env_zeilen(text):
        if not wert or len(wert) < _MIN_WERT_LAENGE:
            continue
        if not schluessel.upper().endswith(_SECRET_KEY_SUFFIXES):
            continue
        geheimnisse.append((schluessel, wert))
    return geheimnisse, None


# --------------------------------------------------------------- Vormerk-Stand


def _vorgemerkte_dateien(wurzel: Path) -> tuple[list[str], str | None]:
    """Pfade der zum Commit vorgemerkten Dateien — Binaerdateien werden
    anhand der numstat-Markierung `-` ausgeschlossen (dort steht kein Text,
    der ein Geheimnis im Klartext tragen koennte)."""
    r = _lauf(["git", "diff", "--cached", "--numstat"], wurzel)
    if r.returncode != 0:
        return [], f"Vormerk-Stand nicht lesbar ({r.stderr.strip()[:120]})"
    dateien: list[str] = []
    for zeile in r.stdout.splitlines():
        teile = zeile.split("\t")
        if len(teile) != 3:
            continue
        hinzugefuegt, entfernt, pfad = teile
        if hinzugefuegt == "-" and entfernt == "-":
            continue  # Binaerdatei laut git
        dateien.append(pfad)
    return dateien, None


def _vorgemerkter_inhalt(wurzel: Path, pfad: str) -> str | None:
    """Inhalt der Datei im INDEX (Vormerk-Stand, das was in den Commit
    ginge) — nicht der Arbeitsstand. `None` bei geloeschten Dateien (die
    koennen kein Geheimnis neu einbringen) oder wenn die Datei die
    Groessengrenze ueberschreitet."""
    groesse_r = _lauf(["git", "cat-file", "-s", f":{pfad}"], wurzel)
    if groesse_r.returncode == 0:
        try:
            if int(groesse_r.stdout.strip()) > _MAX_DATEI_BYTES:
                return None
        except ValueError:
            pass
    inhalt_r = _lauf(["git", "show", f":{pfad}"], wurzel)
    if inhalt_r.returncode != 0:
        return None
    return inhalt_r.stdout


# ------------------------------------------------------------------- Hauptlauf


def main() -> int:
    try:
        eingabe = json.loads(sys.stdin.read() or "{}")
    except Exception:  # noqa: BLE001
        return 0
    befehl = (eingabe.get("tool_input") or {}).get("command", "")

    if WERKZEUG_FEHLT:  # ohne Werkzeug wird nicht geraten, sondern gesagt
        print(f"[secret_in_repo_gate] gestoert: Werkzeug-Paket hook_utils nicht "
              f"verfuegbar ({WERKZEUG_FEHLT}) — Commit UNGEPRUEFT durchgelassen. "
              "Es wird bewusst NICHT auf eine Wortlaut-Pruefung zurueckgefallen "
              "(#1431).", file=sys.stderr)
        return 0
    if not is_git_subcommand(befehl, "commit"):
        return 0

    if not shutil.which("git"):
        print("[secret_in_repo_gate] gestoert: kein `git` auffindbar — Commit "
              "ungeprueft durchgelassen.", file=sys.stderr)
        return 0

    lage, wurzeln, grund = _commit_sicherheitslage(befehl)
    if lage == "gestoert":
        print(f"[secret_in_repo_gate] gestoert: {grund} — Commit ungeprueft "
              "durchgelassen.", file=sys.stderr)
        return 0
    if lage == "unsicher":
        print(
            f"ZIEL-NICHT-SICHER-BESTIMMBAR (#1537) — {grund}.\n"
            "Hier wird NICHT geraten, sondern blockiert (ein stilles "
            "Sicherheitsloch waere schlimmer als ein Fehlalarm).\n"
            "Erlaubter Weg: ein einfacher 'git commit' im eigenen Ordner ODER "
            "'git -C <pfad> commit' (wird dann an diesem Pfad geprueft).",
            file=sys.stderr,
        )
        return 2

    treffer: list[tuple[str, str]] = []
    gesehen: set[tuple[str, str, str]] = set()
    stoerungen: list[str] = []
    for wurzel in wurzeln:
        geheimnisse, env_stoerung = _lade_geheimnisse(wurzel / ".env")
        if env_stoerung:
            stoerungen.append(f"{wurzel}: {env_stoerung}")
            continue
        if not geheimnisse:
            continue  # keine passenden Schluessel in dieser .env -> nichts zu pruefen

        dateien, diff_stoerung = _vorgemerkte_dateien(wurzel)
        if diff_stoerung:
            stoerungen.append(f"{wurzel}: {diff_stoerung}")
            continue

        for pfad in dateien:
            inhalt = _vorgemerkter_inhalt(wurzel, pfad)
            if inhalt is None:
                continue
            for schluessel, wert in geheimnisse:
                marke = (str(wurzel), pfad, schluessel)
                if wert in inhalt and marke not in gesehen:
                    gesehen.add(marke)
                    treffer.append((pfad, schluessel))

    if treffer:
        meldung = [
            "SECRET-IN-REPO-SPERRE (#1537) — vorgemerkte Datei(en) enthalten den "
            "gueltigen Wert eines Zugangsdatums aus der lokalen .env:",
        ]
        for pfad, schluessel in treffer:
            meldung.append(f"   {pfad}   [Schluessel: {schluessel}]")
        meldung += [
            "",
            "Der Wert selbst wird hier bewusst nicht angezeigt.",
            "Abhilfe: Wert aus der Datei entfernen, zur Laufzeit aus der Umgebung "
            "lesen (Python: os.environ[\"<SCHLUESSEL>\"] / Bash: \"$<SCHLUESSEL>\") "
            "und die Datei neu vormerken. Bereits vorgemerkte Datei aus dem Commit "
            "nehmen: git restore --staged <datei>",
        ]
        print("\n".join(meldung), file=sys.stderr)
        return 2

    if stoerungen:
        print(f"[secret_in_repo_gate] gestoert: {'; '.join(stoerungen)} — Commit "
              "ungeprueft durchgelassen.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001 — eine eigene Stoerung blockiert NIE
        print(f"[secret_in_repo_gate] gestoert, Commit nicht blockiert: {e}",
              file=sys.stderr)
        sys.exit(0)
