"""Issue #1670 (TDD RED) AC-3/AC-4: ein einziger "kein Wert"-Platzhalter.

Spec: docs/specs/modules/fix_1670_mail_formatdetails.md
Heute: Compare-Mail mischt EM DASH "—" (Uebersicht, Tabellen, Warn-Zelle)
mit EN DASH "–" (Ausblick). Echte DTOs, echter Renderer, kein Mock.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

import pytest

from app.user import ComparisonResult, LocationResult, SavedLocation

ROOT = Path(__file__).resolve().parent.parent
EM = "—"
EN = "–"


def _loc(i, name):
    return SavedLocation(id=i, name=name, lat=47.0, lon=11.0, elevation_m=1500)


def _result():
    ok = [
        LocationResult(location=_loc(f"o{n}", f"Ort{n}"), score=50,
                       wind_max=20.0, gust_max=30.0, cloud_avg=40, temp_max=5.0,
                       sunny_hours=3, snow_depth_cm=50.0, snow_new_cm=2.0)
        for n in (1, 2)
    ]
    leer = LocationResult(location=_loc("o3", "Ort3"), score=0, error="Timeout")
    return ComparisonResult(locations=ok + [leer], time_window=(9, 16),
                            target_date=date.today(), created_at=datetime.now())


@pytest.mark.parametrize("lang", ["de", "en"])
def test_keine_zelle_oder_span_besteht_nur_aus_em_dash(lang):
    from output.renderers.email.compare_html import render_compare_html

    html = render_compare_html(_result(), outlook_enabled=True, lang=lang)
    nur_em = re.findall(rf"<(?:td|span|th)[^>]*>\s*{EM}\s*</(?:td|span|th)>", html)
    assert nur_em == [], f"{len(nur_em)} Platzhalter-Zellen mit EM DASH"
    assert re.search(rf">\s*{EN}\s*<", html), "EN-DASH-Platzhalter fehlt ganz"


def test_platzhalter_kommt_aus_einer_konstante():
    from output.metric_format import NO_VALUE

    assert NO_VALUE == EN
    for rel in ("src/output/renderers/email/compare_html.py",
                "src/output/renderers/compare_outlook_metric_ids.py",
                "src/output/renderers/narrow.py"):
        src = (ROOT / rel).read_text(encoding="utf-8")  # doc-compliance-test
        assert f'"{EM}"' not in src, rel
        assert f'"{EN}"' not in src, rel
        # Adversary F002: auch Teilstrings in Literalen/f-Strings (z. B.
        # f"{label} –", "R–") zaehlen; Kommentare und Docstrings nicht.
        treffer = _strich_literale(src, rel)
        assert treffer == [], f"{rel}: Strich-Literal statt NO_VALUE: {treffer}"


# Einzige dokumentierte Ausnahme: der Bereichsstrich "km A–B" der
# Etappen-Kopfzeile in narrow.py ist ein Bis-Strich, kein Platzhalter.
_BEREICHSSTRICH = ("src/output/renderers/narrow.py",
                   'f"–{seg.end_point.distance_from_start_km:.1f} km"')


def _docstring_ids(baum) -> set[int]:
    import ast

    ids = set()
    for node in ast.walk(baum):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            erstes = node.body[0] if node.body else None
            if isinstance(erstes, ast.Expr) and isinstance(erstes.value, ast.Constant):
                ids.add(id(erstes.value))
    return ids


# Gedankenstrich im Fliesstext (Log-/Fehlermeldung, "Wort — Wort") ist kein
# Platzhalter: Text, Leerzeichen, Strich, Leerzeichen, Text im selben Literal.
_PROSA_STRICH = re.compile(rf"\S\s[{EM}{EN}]\s\S")


def _hat_platzhalter_strich(text: str) -> bool:
    return bool(re.search(f"[{EM}{EN}]", _PROSA_STRICH.sub("", text)))


def _strich_literale(src: str, rel: str) -> list[str]:
    """Alle String-Konstanten im Code (ohne Docstrings und ohne Gedankenstrich
    im Fliesstext), die EM/EN DASH enthalten -- je Fundstelle die Quellzeile."""
    import ast

    baum = ast.parse(src)
    doc = _docstring_ids(baum)
    zeilen = src.splitlines()
    funde = []
    for node in ast.walk(baum):
        if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                and id(node) not in doc and _hat_platzhalter_strich(node.value)):
            zeile = zeilen[node.lineno - 1].strip()
            if (rel, zeile) != _BEREICHSSTRICH:
                funde.append(f"Z.{node.lineno}: {zeile}")
    return funde


def test_strich_finder_erkennt_teilstring_literale():
    """Gegenprobe zum Finder: ein Teilstring-Literal wird gefunden, Kommentar,
    Docstring und die dokumentierte Ausnahme nicht."""
    probe = (
        f'"""Doc {EN} {EM}."""\n'
        f'# Kommentar {EN}\n'
        'def f(label):\n'
        f'    return f"{{label}} {EN}"\n'
        f'x = "R{EN}"\n'
        f'y = "{EM}"\n'
        f'log = "Eintrag fehlt {EM} Rueckfall"\n'
    )
    funde = _strich_literale(probe, "probe.py")
    assert len(funde) == 3, funde
    ausnahme = f'x = {_BEREICHSSTRICH[1]}\n'.replace("seg.end_point.distance_from_start_km:.1f", "1")
    assert _strich_literale(ausnahme, "probe.py") != []  # nur in narrow.py erlaubt


def test_validator_akzeptiert_en_dash_als_fehlwert():
    src = (ROOT / ".claude/hooks/email_spec_validator.py").read_text(encoding="utf-8")  # doc-compliance-test
    assert f'val == "{EN}"' in src
    assert f'val == "{EM}"' not in src
