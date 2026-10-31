"""Ratsche gegen hartkodierte deutsche Nutzertexte im Telegram-Briefing (Issue #2669, AC-11).

SPEC: docs/specs/modules/i18n_p7_telegram_2669.md AC-11. Die Python-Ratsche P11
und ihre Allowlist ``tests/fixtures/i18n_python_allowlist.json`` existieren noch
nicht; laut Spec wird die Treffer-Freiheit von ``narrow.py`` direkt geprueft --
hier als VERHALTEN: alle Ausgabewege des Renderers werden mit ``lang="en"``
gerendert, und kein Umlaut/ß und kein deutsches Bruchstueck des Katalogs
``telegram.*`` darf in der Ausgabe stehen.

Ausgenommen sind nur Texte, die geteilte Bausteine anderer Pakete liefern und
die mit diesen Paketen englisch werden (dann die Ausnahme hier streichen):
die Warnungs-Bubble (Rahmen P6 #2668) und der Ausblick-Zustandssatz
(``render_outlook_state_plain``, P3 #2665). Echter Renderer, kein Mock.
"""
from __future__ import annotations

import json
import re
from dataclasses import replace
from pathlib import Path

import pytest

from app.models import OutlookState
from output.renderers.narrow import _tg_day_footer, render_telegram_incomplete_hint
from tests.helpers.telegram_briefing_fixture import TZ, _segment, build_texts

REPO = Path(__file__).resolve().parents[1]
ALLOWLIST = REPO / "tests" / "fixtures" / "i18n_python_allowlist.json"
KATALOG = REPO / "src" / "i18n" / "messages"
_FOOTER_IDS = ["thunder", "visibility", "freezing_level"]


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


def treffer(texte: list[str]) -> list[str]:
    frags = _fragmente()
    return [s for s in texte
            if re.search(r"[äöüÄÖÜß]", s) or any(f in s for f in frags)]


def _ohne_fremde_bausteine(texts: list[str]) -> list[str]:
    out = []
    for b in texts:
        if b.startswith("<b>"):
            continue  # Warnungs-Bubble: Rahmen P6
        if b.startswith("Outlook\n⚠️"):
            b = "Outlook"  # Zustandssatz: P3
        out.append(b)
    return out


def _footer(vis_m: int) -> str:
    seg = _segment(1, (0.0, 8.4), (7, 12), [])
    seg = replace(seg, aggregated=replace(seg.aggregated, visibility_min_m=vis_m))
    return _tg_day_footer([seg], _FOOTER_IDS, tz=TZ, lang="en") or ""


def _alle_englischen_ausgaben() -> list[str]:
    texte = _ohne_fremde_bausteine(build_texts(lang="en"))
    texte += _ohne_fremde_bausteine(build_texts(lang="en", error_segment=True))
    texte += _ohne_fremde_bausteine(build_texts(
        lang="en", multi_day_trend=None, outlook_state=OutlookState.UNAVAILABLE))
    texte += [render_telegram_incomplete_hint(n, lang="en") for n in (1, 3)]
    texte += [_footer(v) for v in (15000, 5000, 1000)]
    return texte


def test_englische_ausgabe_ohne_deutsche_nutzertexte():
    assert treffer(_alle_englischen_ausgaben()) == []


def test_deutsche_gegenprobe_wird_erkannt():
    """Selbsttest: dieselben Wege auf Deutsch MUESSEN Treffer liefern."""
    de = build_texts(lang="de", error_segment=True) + [
        render_telegram_incomplete_hint(3, lang="de")]
    gefunden = treffer(de)
    assert any("Kurzübersicht" in s for s in gefunden)
    assert any("keine Daten" in s for s in gefunden)
    assert any("unvollständig" in s for s in gefunden)


@pytest.mark.parametrize("vis_m, wort", [(5000, "fair"), (1000, "poor")])
def test_sicht_stufen_englisch(vis_m, wort):
    assert f"Visibility {wort}" in _footer(vis_m)


def test_kein_allowlist_eintrag_fuer_narrow_py():
    if not ALLOWLIST.exists():
        return  # P11 legt die Allowlist an; Treffer-Freiheit prueft der Test oben
    eintraege = json.loads(ALLOWLIST.read_text(encoding="utf-8"))
    assert not any("src/output/renderers/narrow.py" in str(e) for e in eintraege)
