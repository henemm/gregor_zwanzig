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
