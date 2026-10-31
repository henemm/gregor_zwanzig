# doc-compliance-test
"""Ratsche gegen hartkodierte Nutzertexte im Telegram-Renderer (Issue #2669, AC-11).

SPEC: docs/specs/modules/i18n_p7_telegram_2669.md AC-11. Die Python-Ratsche P11
und ihre Allowlist ``tests/fixtures/i18n_python_allowlist.json`` existieren noch
nicht; laut Spec prueft dieser Test die Treffer-Freiheit von ``narrow.py``
direkt. Treffer: ein String-Literal (ohne Docstrings) mit Umlaut/ß oder mit
einem deutschen Fragment des Katalogs ``telegram.*``. Zeilen mit
``# i18n-token`` tragen Protokoll-Kennungen (z. B. Segment-ID ``Ziel``).
Selbsttest: ein eingeschmuggelter Nutzertext wird gefunden.
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
NARROW = REPO / "src" / "output" / "renderers" / "narrow.py"
ALLOWLIST = REPO / "tests" / "fixtures" / "i18n_python_allowlist.json"
KATALOG = REPO / "src" / "i18n" / "messages"


def _fragmente() -> set[str]:
    de = json.loads((KATALOG / "de" / "telegram.json").read_text(encoding="utf-8"))
    en = json.loads((KATALOG / "en" / "telegram.json").read_text(encoding="utf-8"))
    out: set[str] = set()
    for key, wert in de.items():
        for teil in re.split(r"\{[a-z_]+\}", wert):
            teil = teil.strip(" :—⚠️.")
            if len(teil) >= 3 and teil not in en.get(key, ""):
                out.add(teil)
    return out


def _docstring_ids(tree: ast.AST) -> set[int]:
    ids = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(body, list) and body and isinstance(body[0], ast.Expr) \
                and isinstance(body[0].value, ast.Constant):
            ids.add(id(body[0].value))
    return ids


def treffer(quelle: str) -> list[tuple[int, str]]:
    tree = ast.parse(quelle)
    zeilen = quelle.splitlines()
    docs, frags = _docstring_ids(tree), _fragmente()
    found = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
            continue
        if id(node) in docs or "# i18n-token" in zeilen[node.lineno - 1]:
            continue
        s = node.value
        if re.fullmatch(r"telegram(\.[a-z0-9_]+){1,3}", s):
            continue  # Katalog-Schluessel, kein Text
        if re.search(r"[äöüÄÖÜß]", s) or any(f in s for f in frags):
            found.append((node.lineno, s))
    return found


def test_narrow_py_ohne_hartkodierte_nutzertexte():
    assert treffer(NARROW.read_text(encoding="utf-8")) == []


def test_kein_allowlist_eintrag_fuer_narrow_py():
    if not ALLOWLIST.exists():
        return  # P11 legt die Allowlist an; Treffer-Freiheit prueft der Test oben
    eintraege = json.loads(ALLOWLIST.read_text(encoding="utf-8"))
    assert not any("src/output/renderers/narrow.py" in str(e) for e in eintraege)


def test_selbsttest_eingeschmuggelter_text_wird_gefunden():
    quelle = 'def f():\n    """Doku mit Ümlaut."""\n    return "Kurzübersicht"\n'
    assert treffer(quelle) == [(3, "Kurzübersicht")]
    assert treffer('X = "Ziel"  # i18n-token\n') == []
