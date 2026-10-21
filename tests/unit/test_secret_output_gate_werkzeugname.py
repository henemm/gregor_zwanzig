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
