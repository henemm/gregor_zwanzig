"""TDD RED — Issue #1927: Risk-Dot-Farbpalette in Trip-E-Mail vereinheitlichen.

`_RISK_DOT_COLORS` (`src/output/renderers/email/html.py`) ist eine eigene,
veraltete Farbpalette fuer den Risk-Punkt am Zeilenende der Stundentabelle.
Fix #1801 (PO-Entscheid 2026-08-14) hat den Orange<->Rot-Abstand der uebrigen
Ampel-Spalten (`_AMPEL_DOT_COLORS`, `helpers.py`) bewusst auf ΔE76 54,4
vergroessert, `_RISK_DOT_COLORS` dabei aber ausdruecklich ausgenommen — dort
bleibt der Abstand bei ΔE76 16,4 (Watch #c2410c vs. Risk #b91c1c), demselben
Wert, den #1801 fuer die anderen Spalten gerade als "nicht unterscheidbar"
korrigiert hat. Ergebnis (Issue #1927): der Risk-Punkt wirkt bei mittlerer
Warnstufe optisch wie "rot" statt "mittel/orange".

Gemessen wird ausschliesslich am GERENDERTEN HTML (`_render_html_table`),
nicht an einer internen Konstante — die Spec laesst den Namen/die Form der
Farbzuordnung im Produktivcode bewusst offen (Implementierungsdetail).

Kern-Schicht, deterministisch: keine Mocks/patch()/MagicMock, kein Netz.
Echter Renderer-Aufruf mit echten Zeilen-Dicts.

SPEC: docs/specs/modules/fix_1927_risk_dot_farbpalette.md AC-1
KONTEXT: docs/context/fix-1927-risk-farbe-mismatch.md
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from app.models import ThunderLevel
from src.output.renderers.email.html import _render_html_table

# Zielwerte laut Spec: identisch zu _AMPEL_DOT_COLORS (helpers.py:588-593).
_EXPECTED_OK = "#15803d"     # unveraendert (green)
_EXPECTED_WATCH = "#d4530a"  # neu (bisher #c2410c)
_EXPECTED_RISK = "#a8104a"   # neu (bisher #b91c1c)

# Alte, zu eng beieinanderliegende Farben (ΔE76 16,4) — duerfen nach dem Fix
# nirgends mehr im gerenderten Output auftauchen.
_OLD_WATCH = "#c2410c"
_OLD_RISK = "#b91c1c"

_BG_HEX = re.compile(r"background:\s*(#[0-9a-fA-F]{6})")

_HARMLESS = {"wind": 5, "gust": 10, "precip": 0.0, "pop": 5, "visibility": 20000.0}


def _render_one(row: dict) -> str:
    """Rendert GENAU EINE Stundenzeile — jede gefundene Farbe ist dadurch
    eindeutig dieser Zeile zugeordnet (keine Zeilenverwechslung moeglich)."""
    return _render_html_table([row], friendly_keys=set(), indicator_keys=set())


def _risk_dot_color(html: str) -> str:
    """Fuellfarbe des Risk-Punkts der (einzigen) Zeile — aus der LETZTEN
    Zelle, nicht per Textsuche im ganzen HTML."""
    soup = BeautifulSoup(html, "html.parser")
    trs = soup.find("tbody").find_all("tr")
    assert len(trs) == 1, f"Erwartet genau eine Datenzeile, gefunden {len(trs)}"
    tds = trs[0].find_all("td")
    dot_td = tds[-1]
    span = dot_td.find("span")
    assert span is not None, f"Keine Risk-Dot-Span in der letzten Zelle: {dot_td}"
    match = _BG_HEX.search(span.get("style", ""))
    assert match is not None, f"Risk-Dot ohne background-Farbe: {span}"
    return match.group(1).lower()


def test_ok_risk_level_stays_green():
    """Given eine Zeile ohne jede Warnung (Gewitter NONE, alle Einzelwerte
    harmlos) / When gerendert wird / Then bleibt der Risk-Punkt gruen
    (#15803d) — Regressionsschutz, unveraendert durch diesen Fix."""
    row = {**_HARMLESS, "time": "11", "thunder": ThunderLevel.NONE}
    color = _risk_dot_color(_render_one(row))
    assert color == _EXPECTED_OK, (
        f"Risk-Dot bei Gewitter NONE ist {color!r}, erwartet {_EXPECTED_OK!r} (gruen)."
    )


def test_watch_risk_level_uses_new_ampel_orange():
    """Given eine Zeile mit Gewitter MED und sonst harmlosen Werten (löst
    laut `_row_risk` genau 'watch' aus) / When gerendert wird / Then traegt
    der Risk-Punkt die NEUE Ampel-Orange-Farbe (#d4530a, identisch zu
    `_AMPEL_DOT_COLORS['orange']`) — heute liefert der Renderer stattdessen
    die alte, zu rot wirkende Farbe #c2410c (Issue #1927)."""
    row = {**_HARMLESS, "time": "12", "thunder": ThunderLevel.MED}
    color = _risk_dot_color(_render_one(row))
    assert color != _OLD_WATCH, (
        f"Risk-Dot bei 'watch' traegt noch die alte Farbe {_OLD_WATCH!r} — "
        f"dieselbe Palette, die #1801 fuer die anderen Ampel-Spalten bereits "
        f"als zu eng an 'risk' (ΔE76 16,4) korrigiert hat."
    )
    assert color == _EXPECTED_WATCH, (
        f"Risk-Dot bei 'watch' ist {color!r}, erwartet {_EXPECTED_WATCH!r} "
        f"(dieselbe Orange-Farbe wie die uebrigen Ampel-Spalten)."
    )


def test_risk_risk_level_uses_new_ampel_red():
    """Given eine Zeile mit Gewitter HIGH ('risk') / When gerendert wird /
    Then traegt der Risk-Punkt die NEUE Ampel-Rot-Farbe (#a8104a, identisch
    zu `_AMPEL_DOT_COLORS['red']`) — heute liefert der Renderer die alte
    Farbe #b91c1c."""
    row = {**_HARMLESS, "time": "13", "thunder": ThunderLevel.HIGH}
    color = _risk_dot_color(_render_one(row))
    assert color != _OLD_RISK, (
        f"Risk-Dot bei 'risk' traegt noch die alte Farbe {_OLD_RISK!r}."
    )
    assert color == _EXPECTED_RISK, (
        f"Risk-Dot bei 'risk' ist {color!r}, erwartet {_EXPECTED_RISK!r} "
        f"(dieselbe Rot-Farbe wie die uebrigen Ampel-Spalten)."
    )


def test_old_watch_and_risk_colors_vanish_from_full_table():
    """Given alle drei Risk-Level in einer Tabelle / When gerendert wird /
    Then kommen die alten, zu eng beieinanderliegenden Farben (#c2410c,
    #b91c1c) NIRGENDS mehr im HTML-Output vor — Regressionsschutz gegen ein
    stillschweigendes erneutes Auseinanderlaufen der Paletten."""
    rows = [
        {**_HARMLESS, "time": "11", "thunder": ThunderLevel.NONE},
        {**_HARMLESS, "time": "12", "thunder": ThunderLevel.MED},
        {**_HARMLESS, "time": "13", "thunder": ThunderLevel.HIGH},
    ]
    html = _render_html_table(rows, friendly_keys=set(), indicator_keys=set())
    assert _OLD_WATCH not in html.lower(), (
        f"Alte Watch-Farbe {_OLD_WATCH!r} taucht noch im gerenderten HTML auf."
    )
    assert _OLD_RISK not in html.lower(), (
        f"Alte Risk-Farbe {_OLD_RISK!r} taucht noch im gerenderten HTML auf."
    )
