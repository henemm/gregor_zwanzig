"""cd-Erkennung des Secret-in-Repo-Gates ignoriert Heredoc-Inhalte (#1636 F008).

Fehlerbild: `git commit -F - <<EOF` mit einer Nachrichtenzeile, die mit `cd`
beginnt, wurde als „Kommando enthaelt 'cd' vor dem Commit" BLOCKIERT, obwohl
die Zeile reiner Heredoc-Text ist und nie ausgefuehrt wird.

Diese Datei prueft die plugin-UNABHAENGIGE Vorstufe der cd-Erkennung
(`_ohne_heredoc_inhalt`) mit echten Kommandostrings — sie laeuft daher auch auf
CI-Runnern ohne agent-os-openspec-Plugin. Der End-zu-End-Nachweis ueber den
Waechter-Unterprozess steht in `test_secret_in_repo_gate.py` (braucht das
Plugin, sonst Modul-Skip).

Pfadregel #1409: Pruefling relativ zu DIESER Datei aufgeloest.
"""
from __future__ import annotations

import importlib.util
import re
import shlex
from pathlib import Path

_GATE = Path(__file__).resolve().parents[2] / ".claude" / "hooks" / "secret_in_repo_gate.py"


def _gate():
    spec = importlib.util.spec_from_file_location("secret_gate_heredoc", str(_GATE))
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _zeilen_beginnen_mit_cd(befehl: str) -> bool:
    return any(z.strip().startswith("cd ") for z in befehl.split("\n"))


def test_cd_zeile_im_unquotierten_heredoc_verschwindet():
    """Given `git commit -F - <<EOF` mit Nachrichtenzeile 'cd foo' / When die
    cd-Vorstufe laeuft / Then bleibt keine ausfuehrbare cd-Zeile uebrig."""
    befehl = "git commit -F - <<EOF\nfix: Pfad korrigiert\ncd foo ist jetzt weg\nEOF"
    rest = _gate()._ohne_heredoc_inhalt(befehl)
    assert not _zeilen_beginnen_mit_cd(rest), rest
    assert rest.startswith("git commit -F - <<EOF")


def test_cd_im_heredoc_mit_bindestrich_und_tabs():
    """`<<-EOF` erlaubt Tab-eingerueckten Terminator — auch dann verschwindet
    der Inhalt samt Terminator."""
    befehl = "cat <<-EOF > f\n\tcd foo\n\tEOF\ngit commit -m x"
    rest = _gate()._ohne_heredoc_inhalt(befehl)
    assert not _zeilen_beginnen_mit_cd(rest), rest
    assert rest.endswith("git commit -m x")


def test_echtes_cd_nach_heredoc_bleibt_sichtbar():
    """Given ein Heredoc, DANACH ein echtes `cd /x && git commit` / Then bleibt
    das echte cd erhalten (kein Durchrutschen)."""
    befehl = "cat <<'EOF' > f\ninhalt\nEOF\ncd /x && git commit -m y"
    rest = _gate()._ohne_heredoc_inhalt(befehl)
    assert "cd /x && git commit -m y" in rest


def test_heredoc_operator_in_anfuehrungszeichen_zaehlt_nicht():
    """Given `<<X` nur INNERHALB von Anfuehrungszeichen (kein Heredoc) und
    danach ein echtes cd / Then bleibt das cd sichtbar."""
    befehl = 'echo "<<X"\ncd /evil\nX\ngit commit -m z'
    rest = _gate()._ohne_heredoc_inhalt(befehl)
    assert "cd /evil" in rest


def test_heredoc_ohne_terminator_bleibt_unveraendert():
    """Unklare Lage (Terminator fehlt) -> Kommando unveraendert, damit die
    cd-Pruefung fail-closed weiterlaeuft."""
    befehl = "git commit -F - <<EOF\ncd foo"
    assert _gate()._ohne_heredoc_inhalt(befehl) == befehl


def test_here_string_und_kommentar_sind_kein_heredoc():
    """`<<<` (Here-String) und `<<` in einem Kommentar oeffnen keinen Heredoc."""
    g = _gate()
    befehl = "grep a <<<EOF\ncd /x\nEOF\ngit commit -m q"
    assert "cd /x" in g._ohne_heredoc_inhalt(befehl)
    befehl2 = "ls # <<EOF\ncd /x\nEOF\ngit commit -m q"
    assert "cd /x" in g._ohne_heredoc_inhalt(befehl2)


def test_arithmetik_shift_ist_kein_heredoc():
    """`$((1<<2))` ist eine Bit-Verschiebung, kein Heredoc mit Endwort `2` —
    das nachfolgende echte cd muss sichtbar bleiben (Adversary F4)."""
    befehl = "echo $((1<<2))\ncd /evil\n2\ngit commit -m x"
    assert "cd /evil" in _gate()._ohne_heredoc_inhalt(befehl)


def test_heredoc_endwort_mit_ziffer_am_anfang_nur_gequotet():
    """Unquotiertes Endwort muss mit Buchstabe/Unterstrich beginnen; `<<1`
    oeffnet keinen Heredoc, das cd bleibt sichtbar."""
    befehl = "cat <<1\ncd /evil\n1\ngit commit -m x"
    assert "cd /evil" in _gate()._ohne_heredoc_inhalt(befehl)


def test_arithmetik_shift_mit_variablen_ist_kein_heredoc():
    """`$((a<<b))` und `((a<<b))`: auch mit Buchstaben-Operand kein Heredoc."""
    g = _gate()
    for arith in ("echo $((a<<b))", "((a<<b))"):
        befehl = f"{arith}\ncd /evil\nb\ngit commit -m x"
        assert "cd /evil" in g._ohne_heredoc_inhalt(befehl), arith


# ------------------------------------------------------------------------------
# Entscheidungsfunktion `_commit_sicherheitslage` ohne Plugin (Adversary F1).
# Die Zerlegungs-Bausteine stammen sonst aus dem Plugin; hier ersetzt sie eine
# echte, minimale Zerlegung (shlex je Zeile, Trenner && || ; | & ( )). Geprueft
# wird der AUSGANG der Gate-Entscheidung, nicht die Ersatz-Zerlegung.

_TRENNER = {"&&", "||", ";", "|", "&", "(", ")"}
_CD_GRUND = "enthaelt 'cd' vor dem Commit"


def _zerlege(befehl: str):
    segmente: list[list[str]] = []
    for zeile in befehl.split("\n"):
        lex = shlex.shlex(zeile, posix=True, punctuation_chars=";&|()")
        lex.whitespace_split = True
        aktuell: list[str] = []
        try:
            for tok in lex:
                if tok in _TRENNER:
                    if aktuell:
                        segmente.append(aktuell)
                    aktuell = []
                else:
                    aktuell.append(tok)
        except ValueError:
            return None
        if aktuell:
            segmente.append(aktuell)
    return segmente


def _gate_mit_zerlegung(zerleger=_zerlege):
    g = _gate()
    g._git_segments = zerleger
    g._GIT_SHELL_BINARY_RE = re.compile(r"^(ba|z|da)?sh$")
    g.git_subcommands = lambda s: ["commit"] if "git commit" in s else []
    g._git_subcommands_in_segment = lambda t: ["commit"] if "commit" in t else []
    g._git_subcommand_of_segment = (
        lambda t: t[1] if len(t) > 1 and t[0] == "git" else None
    )
    g._ENV_ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
    g._GIT_COMMAND_PREFIXES = frozenset()
    g._GIT_OPTS_WITH_VALUE = frozenset({"-C", "-c", "--git-dir", "--work-tree"})
    return g


def test_gate_entscheidung_cd_zeile_im_heredoc_blockt_nicht():
    """Given `git commit -F - <<EOF` mit Nachrichtenzeile 'cd foo' / When die
    Gate-Entscheidung faellt / Then 'sicher' (kein cd-Alarm)."""
    lage, _wurzeln, grund = _gate_mit_zerlegung()._commit_sicherheitslage(
        "git commit -F - <<EOF\nfix\ncd foo entfaellt\nEOF"
    )
    assert lage == "sicher", grund


def test_gate_entscheidung_cd_nach_heredoc_blockt():
    """Given ein echtes `cd /x && git commit` nach einem Heredoc / Then
    'unsicher' mit cd-Grund."""
    lage, _wurzeln, grund = _gate_mit_zerlegung()._commit_sicherheitslage(
        "cat <<EOF > f\ninhalt\nEOF\ncd /x && git commit -m y"
    )
    assert lage == "unsicher" and _CD_GRUND in (grund or ""), (lage, grund)


def test_gate_entscheidung_faellt_auf_ungekuerzte_zerlegung_zurueck():
    """Given ein strenger Zerleger, der einen Heredoc-Operator OHNE Inhalt
    (also das gekuerzte Kommando) nicht versteht / Then entscheidet das Gate
    konservativ auf der UNGEKUERZTEN Zerlegung — die cd-Zeile zaehlt, Lage
    'unsicher' statt Absturz oder Durchlass."""
    def streng(befehl: str):
        if re.search(r"<<\w+\s*$", befehl):
            return None  # Heredoc ohne Inhalt/Endwort: nicht zerlegbar
        return _zerlege(befehl)

    lage, _wurzeln, grund = _gate_mit_zerlegung(streng)._commit_sicherheitslage(
        "git commit -F - <<EOF\ncd foo\nEOF"
    )
    assert lage == "unsicher" and _CD_GRUND in (grund or ""), (lage, grund)
