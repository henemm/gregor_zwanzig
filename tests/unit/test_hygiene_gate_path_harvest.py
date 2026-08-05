# doc-compliance-test
"""Regressionstests fuer die Pfadlisten-Heuristik des Hygiene-Gates (#1469).

Das Gate (tests/tdd/test_765_backend_hygiene_compliance.py) erntet Pfade aus
Listen-/Tupel-Literalen nur, wenn das Literal eine HOMOGENE Produktpfad-Liste
ist — jedes Element loest zu einem existierenden Produkt-``.py``/``.go`` auf.
Vorher wurde jedes Literal der Datei geerntet, sobald irgendwo ein nicht
aufloesbares ``read_text()``-Ziel existierte; dadurch galten reine Namensdaten
(parametrize-Faelle wie in test_validator_log_unique_filenames.py) als
Quelltext-Lektuere und die Datei musste per Ausnahmeeintrag stillgelegt
werden (#1466 AP4 — das Loch, das dieses Ticket schliesst).

Prueft die Gate-FUNKTIONEN (Werkzeug-Compliance), kein Produkt-Verhalten —
daher ``# doc-compliance-test``. Die synthetischen Prueflinge entstehen unter
``tmp_path``; Produktpfade kommen in dieser Datei bewusst NIE als homogenes
Listen-Literal vor, damit das Gate diese Datei nicht selbst erntet.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_HERE = Path(__file__).resolve()
_REPO = _HERE.parents[2]
_GATE_FILE = _REPO / "tests" / "tdd" / "test_765_backend_hygiene_compliance.py"
_NAMESDATA_FILE = (
    _REPO / "tests" / "tdd" / "test_validator_log_unique_filenames.py"
)


def _load_gate():
    spec = importlib.util.spec_from_file_location("hygiene_gate_765", _GATE_FILE)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_namensdaten_literal_wird_nicht_geerntet(tmp_path):
    """Given eine Testdatei mit gemischtem parametrize-Literal (Namensdaten,
    darunter ein echter Produktpfad) und einem read_text() ueber eine
    Comprehension-Variable auf tmp-Protokolle / When das Gate sie prueft /
    Then meldet es KEINE Produkt-Quelltext-Lektuere (#1469-Fehlalarm)."""
    gate = _load_gate()
    offender = tmp_path / "test_namensdaten.py"
    offender.write_text(
        "_CASES = [\n"
        '    ("briefing_mail_validator.py", "src/app/models.py", {}),\n'
        '    ("email_spec_validator.py", "src/app/trip.py", {"n": 3}),\n'
        "]\n"
        "def test_x(tmp_path):\n"
        '    logs = [p for p in tmp_path.glob("*.yaml")]\n'
        "    data = [p.read_text() for p in logs]\n",
        encoding="utf-8",
    )
    assert gate._find_product_reads(offender) == []


def test_homogene_produktpfadliste_wird_weiter_gefangen(tmp_path):
    """Given eine Testdatei, die eine homogene Liste echter Produktpfade per
    Schleifen-read_text() liest / When das Gate sie prueft / Then bleibt der
    Verstoss gefangen (die Praezisierung reisst kein Loch)."""
    gate = _load_gate()
    offender = tmp_path / "test_quelltextleser.py"
    offender.write_text(
        "from pathlib import Path\n"
        "_R = Path(__file__).resolve().parents[2]\n"
        "FILES = [\n"
        '    _R / "src" / "app" / "models.py",\n'
        '    _R / "src" / "app" / "trip.py",\n'
        "]\n"
        "def test_y():\n"
        "    for f in FILES:\n"
        '        assert "class" in f.read_text(encoding="utf-8")\n',
        encoding="utf-8",
    )
    expected = sorted("src/app/" + name for name in ("models.py", "trip.py"))
    assert gate._find_product_reads(offender) == expected


def test_namensdaten_datei_ist_ohne_ausnahmeeintrag_konform():
    """Given die reale Namensdaten-Datei aus #1408/#1466 / When das Gate sie
    direkt prueft / Then ist sie konform UND steht nicht mehr in _SELF_EXEMPT
    (das Loch aus #1466 AP4 ist geschlossen)."""
    gate = _load_gate()
    assert gate._find_product_reads(_NAMESDATA_FILE) == []
    assert _NAMESDATA_FILE.name not in gate._SELF_EXEMPT


def test_echter_quelltextzugriff_wird_wieder_gefangen(tmp_path):
    """Given dieselbe Namensdaten-Datei, ergaenzt um einen ECHTEN
    Quelltext-Zugriff im Schleifen-Muster / When das Gate sie prueft / Then
    schlaegt es an — die Gegenprobe aus #1469 Schritt 3."""
    gate = _load_gate()
    original = _NAMESDATA_FILE.read_text(encoding="utf-8")
    mutated = tmp_path / _NAMESDATA_FILE.name
    mutated.write_text(
        original
        + "\n\nfrom pathlib import Path as _P\n"
        '_MUT = [_P(__file__).resolve().parents[3] / "src" / "app" / "models.py"]\n'
        "def test_mutationsprobe():\n"
        "    for f in _MUT:\n"
        '        assert "class" in f.read_text(encoding="utf-8")\n',
        encoding="utf-8",
    )
    hits = gate._find_product_reads(mutated)
    assert hits == ["src/app/" + "models.py"]
