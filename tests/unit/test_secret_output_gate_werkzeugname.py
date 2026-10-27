"""Werkzeugname in der Notfallmeldung des Ausgabe-Waechters wird maskiert (#1617).

Fehlerbild: `secret_output_gate._melde_abbruch` schrieb den Werkzeugnamen
(`tool_name` aus der Nutzlast) UNGEFILTERT in die Meldung. Steht darin der
Wert eines Geheimnisses, tritt er ueber genau die Meldung aus, die vor
ungeprueften Ergebnissen warnen soll.

Plugin-UNABHAENGIG: Ohne agent-os-openspec-Plugin ist die Plugin-Erkennung
nicht verfuegbar — die Notfallmeldung muss dann trotzdem maskieren
(konservativ ueber die Werte der lokalen `.env`). Die Subprozess-Faelle mit
Plugin stehen in `test_secret_output_gate.py`.

Synthetische `.env` in `tmp_path` (nie die echte). Pfadregel #1409: Pruefling
relativ zu DIESER Datei aufgeloest.
"""
from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

_GATE = Path(__file__).resolve().parents[2] / ".claude" / "hooks" / "secret_output_gate.py"
WERT = "Zk8mQr2vLp9wXt4nBs6y"  # frei erfunden


def _gate():
    spec = importlib.util.spec_from_file_location("secret_output_gate_name", str(_GATE))
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_abbruchmeldung_gibt_geheimnis_im_werkzeugnamen_nicht_aus(tmp_path, monkeypatch, capsys):
    """Given eine .env mit Geheimnis und ein Werkzeugname, der den Wert enthaelt /
    When die Pruefung abbricht und die Notfallmeldung geschrieben wird / Then
    steht der rohe Wert NICHT in der Meldung, das Werkzeug ist aber erkennbar."""
    (tmp_path / ".env").write_text(f"GZ_FAKE_TEST_PASS={WERT}\nKURZ=ab12\n")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    g = _gate()
    g._WERKZEUG = f"mcp__dienst__{WERT}"
    g._melde_abbruch(ValueError("egal"))
    meldung = capsys.readouterr().err
    assert "NICHT abgeschlossen" in meldung
    assert WERT not in meldung, meldung
    assert "mcp__dienst__" in meldung, meldung


def test_abbruchmeldung_nennt_harmlosen_werkzeugnamen_weiter(tmp_path, monkeypatch, capsys):
    """Ohne Geheimnis im Namen bleibt der Werkzeugname unveraendert lesbar."""
    (tmp_path / ".env").write_text(f"GZ_FAKE_TEST_PASS={WERT}\n")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    g = _gate()
    g._WERKZEUG = "Bash"
    g._melde_abbruch(ValueError("egal"))
    assert "Ergebnisses von Bash" in capsys.readouterr().err


def _env_paare(cfg, wurzel):
    """Echte, minimale Ersatz-Erkennung fuer das fehlende Plugin: KEY=WERT
    aus der `.env` der Projektwurzel."""
    paare = []
    for zeile in (Path(wurzel) / ".env").read_text().splitlines():
        schluessel, _, wert = zeile.partition("=")
        paare.append((schluessel, wert))
    return paare


def test_fundmeldung_gibt_geheimnis_im_werkzeugnamen_nicht_aus(
        tmp_path, monkeypatch, capsys):
    """(Adversary F2) Given eine .env mit Geheimnis, ein Ergebnis mit dem Wert
    und ein Werkzeugname, der den Wert ebenfalls enthaelt / When main() den
    Fund maskiert und meldet / Then steht der rohe Wert weder in der Meldung
    noch im Ersatz-Ergebnis."""
    (tmp_path / ".env").write_text(f"GZ_FAKE_TEST_PASS={WERT}\n")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    g = _gate()
    g.collect_secrets = _env_paare
    g._is_secret_value = lambda wert, cfg: len(wert) >= 8
    g._is_secret_key = lambda schluessel, cfg: schluessel.endswith("_PASS")
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({
        "tool_name": f"mcp__dienst__{WERT}",
        "tool_response": {"stdout": f"login {WERT}"},
    })))
    assert g.main() == 0
    aus = capsys.readouterr()
    assert "maskiert" in aus.err, aus.err
    assert "***GZ_FAKE_TEST_PASS***" in aus.out, aus.out
    assert WERT not in aus.err + aus.out, aus.err + aus.out


def test_abbruchmeldung_zeigt_fragezeichen_wenn_keine_maskierung_moeglich(
        tmp_path, monkeypatch, capsys):
    """(Adversary F3) Given beide Geheimnis-Quellen scheitern (Plugin fehlt,
    .env-Notbehelf wirft) / Then nennt die Notfallmeldung den Werkzeugnamen
    NICHT, sondern '?'."""
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    g = _gate()

    def env_unlesbar():
        raise OSError("env unlesbar")

    g._env_rohwerte = env_unlesbar
    g._WERKZEUG = f"mcp__dienst__{WERT}"
    g._melde_abbruch(ValueError("egal"))
    meldung = capsys.readouterr().err
    assert "Ergebnisses von ? NICHT abgeschlossen" in meldung, meldung
    assert "mcp__dienst__" not in meldung
