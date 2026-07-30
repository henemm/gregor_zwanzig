"""Der tote, ungeschuetzte Sendeweg `src/app/core.py` ist ersatzlos entfernt
(#1412 Scheibe S3a, AC-4).

Spec: docs/specs/modules/fix_1412_s3a_transport_kapselung_mail.md

`core.send_mail` baut eine SMTP-Verbindung an allen Empfaenger-Guards vorbei
auf und zieht den Empfaenger aus `MAIL_TO`. Nachweislich tot: einziger
Aufrufer im gesamten Repo war `tests/test_core.py` (Analyse, Befund 4).

RED-Erwartung: das Modul ist heute importierbar -- der erste Test schlaegt
fehl, bis die Datei geloescht ist.
"""
from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCAN_UNTERORDNER = ("src", "api")
TOTES_MODUL = "app.core"


def test_ac4_toter_sendeweg_ist_nicht_mehr_importierbar(monkeypatch):
    """AC-4: `import app.core` gibt es nicht mehr."""
    monkeypatch.delitem(sys.modules, TOTES_MODUL, raising=False)
    importlib.invalidate_caches()
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(TOTES_MODUL)


def test_ac4_datei_existiert_nicht_mehr():
    """Gegenprobe zum Import-Nachweis: die Datei selbst ist weg, nicht bloss
    unauffindbar gemacht."""
    assert not (REPO_ROOT / "src" / "app" / "core.py").exists()


def _importiert_totes_modul(quelltext: str, datei: str) -> list[tuple[int, str]]:
    """Alle Stellen in `quelltext`, die `app.core` einbinden -- per AST, nicht
    per Textsuche: `import app.core`, `from app.core import ...`,
    `from app import core` und `importlib.import_module("app.core")`."""
    treffer: list[tuple[int, str]] = []
    baum = ast.parse(quelltext, filename=datei)
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.Import):
            for name in knoten.names:
                if name.name == TOTES_MODUL or name.name.startswith(TOTES_MODUL + "."):
                    treffer.append((knoten.lineno, f"import {name.name}"))
        elif isinstance(knoten, ast.ImportFrom) and not knoten.level:
            modul = knoten.module or ""
            if modul == TOTES_MODUL or modul.startswith(TOTES_MODUL + "."):
                treffer.append((knoten.lineno, f"from {modul} import ..."))
            elif modul == "app" and any(n.name == "core" for n in knoten.names):
                treffer.append((knoten.lineno, "from app import core"))
        elif isinstance(knoten, ast.Call):
            funktion = knoten.func
            if isinstance(funktion, ast.Attribute) and funktion.attr == "import_module":
                for argument in knoten.args:
                    if (
                        isinstance(argument, ast.Constant)
                        and argument.value == TOTES_MODUL
                    ):
                        treffer.append((knoten.lineno, "importlib.import_module"))
    return treffer


def test_ac4_kein_modul_unter_src_und_api_bindet_den_toten_weg_ein():
    """AC-4: kein Restaufrufer -- weder statisch noch ueber `import_module`."""
    befunde: list[str] = []
    for unterordner in SCAN_UNTERORDNER:
        wurzel = REPO_ROOT / unterordner
        if not wurzel.is_dir():
            continue
        for pfad in sorted(wurzel.rglob("*.py")):
            relativ = pfad.relative_to(REPO_ROOT).as_posix()
            if relativ == "src/app/core.py":
                continue
            for zeile, form in _importiert_totes_modul(
                pfad.read_text(encoding="utf-8"), relativ
            ):
                befunde.append(f"{relativ}:{zeile} ({form})")
    assert not befunde, "Restaufrufer des toten Sendewegs:\n" + "\n".join(befunde)
