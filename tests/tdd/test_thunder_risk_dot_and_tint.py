"""TDD RED — Issue #1418 (Fehler 1) / Scheibe S1 von Epic #1419.

Der Gewitterwert einer Stundenzeile ist ein Stufenwort (`ThunderLevel`-Enum),
wird im Trip-HTML-Renderer aber an zwei Stellen als Zahl gelesen
(`float("HIGH")` wirft und faellt still auf 0 bzw. None zurueck). Folge: Der
Risiko-Punkt am Zeilenende bleibt bei Gewitter immer gruen und die
Gewitterspalte bleibt immer ungefaerbt — obwohl das Symbol ⚡⚡ korrekt
erscheint.

Diese Tests messen bewusst am **gerenderten HTML** (`_render_html_table`),
nicht an der Hilfsfunktion `_row_risk`: Ein isolierter Aufruf von `_row_risk`
mit einer *Zahl* existiert bereits
(`test_renderer_katalog_schwellen.py::test_ac7_thunder_row_risk_unchanged`)
und hat den Fehler gerade deshalb nicht bemerkt — die Datenform stimmte nicht.
Hier wird ausschliesslich die Datenform des Produktivpfads gefuettert
(`helpers.py:112` setzt `getattr(dp, "thunder_level")` → `ThunderLevel`/None).

Kern-Schicht, deterministisch: keine Mocks/patch()/MagicMock, kein Netz, kein
Mailversand. Echter Renderer-Aufruf mit echten Datenstrukturen.

SPEC: docs/specs/modules/fix_1418_gewitter_risikopunkt.md AC-1 bis AC-4
KONTEXT: docs/context/fix-1418-gewitter-risikopunkt.md
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from app.models import ThunderLevel
from src.output.renderers.email.html import _RISK_DOT_COLORS, _render_html_table

# Punktfarben kommen aus der Quelle im Renderer (keine Hex-Duplikate im Test).
DOT_OK = _RISK_DOT_COLORS["ok"][0]        # gruen  — unauffaellig
DOT_WATCH = _RISK_DOT_COLORS["watch"][0]  # orange — Achtung
DOT_RISK = _RISK_DOT_COLORS["risk"][0]    # rot    — Risiko

# Zell-Toenungsfarben stehen als Literale im Renderer (html.py:633-637 /
# :650-654 — "orange"/"red" der Zell-Toenung); es gibt dafuer keine
# exportierte Konstante, daher hier bewusst als Literal mit Herkunftsangabe.
CELL_RED = "#f6c5bf"
CELL_ORANGE = "#fad6b8"

_BG_HEX = re.compile(r"background:\s*(#[0-9a-fA-F]{6})")

# Spaltenkopf der Gewitterspalte (metric_catalog.py:252 col_label="Thdr").
_THUNDER_LABEL = "Thdr"


def _render_one(row: dict) -> str:
    """Rendert GENAU EINE Stundenzeile — dadurch ist jede gefundene Farbe
    eindeutig dieser Zeile zugeordnet (keine Zeilenverwechslung moeglich)."""
    return _render_html_table([row], friendly_keys=set(), indicator_keys=set())


def _single_row(html: str):
    soup = BeautifulSoup(html, "html.parser")
    trs = soup.find("tbody").find_all("tr")
    assert len(trs) == 1, f"Erwartet genau eine Datenzeile, gefunden {len(trs)}"
    return trs[0]


def _risk_dot_color(html: str) -> str:
    """Farbe des Risiko-Punkts der (einzigen) Zeile — aus der LETZTEN Zelle,
    nicht per Textsuche im ganzen HTML."""
    tds = _single_row(html).find_all("td")
    dot_td = tds[-1]
    span = dot_td.find("span")
    assert span is not None, f"Keine Risk-Dot-Span in der letzten Zelle: {dot_td}"
    match = _BG_HEX.search(span.get("style", ""))
    assert match is not None, f"Risk-Dot ohne background-Farbe: {span}"
    return match.group(1).lower()


def _thunder_cell_bg(html: str):
    """Hintergrundfarbe der Gewitterzelle der (einzigen) Zeile.

    `None` = ungefaerbt. Fehlt die Gewitterspalte ganz (Zeile ohne
    "thunder"-Schluessel), ist das ebenfalls "ungefaerbt" → `None`.
    """
    td = _single_row(html).find("td", attrs={"data-label": _THUNDER_LABEL})
    if td is None:
        return None
    match = _BG_HEX.search(td.get("style", ""))
    return match.group(1).lower() if match else None


def _row(**overrides) -> dict:
    """Stundenzeile mit durchweg unauffaelligen Werten (alle unterhalb jeder
    Katalog-Warnschwelle) — auffaellig ist nur, was der Test setzt."""
    base = {
        "time": "14:00",
        "temp": 18.0,
        "wind": 10.0,
        "gust": 15.0,
        "precip": 0.0,
        "pop": 5.0,
    }
    base.update(overrides)
    return base


# ===========================================================================
# AC-1: Risikopunkt bei hoher Gewittergefahr
# ===========================================================================

def test_ac1_thunder_high_makes_risk_dot_red():
    """AC-1: GIVEN eine Stundenzeile mit Gewitterstufe HIGH und sonst
    unauffaelligen Werten / WHEN die Briefing-Stundentabelle gerendert wird /
    THEN zeigt der Risiko-Punkt am Zeilenende Rot — heute bleibt er gruen,
    obwohl das Gewittersymbol ⚡⚡ bereits korrekt in der Zelle erscheint."""
    html = _render_one(_row(thunder=ThunderLevel.HIGH))

    assert "⚡⚡" in html, (
        "Erwartungs-Grundlage: Der Zelltext zeigt bei HIGH bereits korrekt ⚡⚡ "
        "— genau diese Diskrepanz zum gruenen Punkt ist der Fehler."
    )

    color = _risk_dot_color(html)
    assert color == DOT_RISK.lower(), (
        f"Risiko-Punkt bei Gewitterstufe HIGH ist {color!r}, erwartet "
        f"{DOT_RISK!r} (rot). Heute liest `_row_risk` den Enum-Wert ueber "
        f"`_safe_float` als Zahl, faellt still auf 0.0 zurueck und liefert "
        f"'ok' → gruen ({DOT_OK})."
    )


# ===========================================================================
# AC-2: Gewitterzelle bei hoher Gewittergefahr
# ===========================================================================

def test_ac2_thunder_high_tints_cell_red():
    """AC-2: GIVEN dieselbe Stundenzeile mit Gewitterstufe HIGH / WHEN die
    Briefing-Stundentabelle gerendert wird / THEN ist die Gewitterspalte
    dieser Zeile rot hinterlegt (#f6c5bf) — heute bleibt sie in jedem Fall
    ungefaerbt, unabhaengig vom Wert."""
    html = _render_one(_row(thunder=ThunderLevel.HIGH))

    bg = _thunder_cell_bg(html)
    assert bg == CELL_RED, (
        f"Gewitterzelle bei Stufe HIGH hat Hintergrund {bg!r}, erwartet "
        f"{CELL_RED!r} (rot). Heute erzeugt `float(ThunderLevel.HIGH)` eine "
        f"gefangene Ausnahme → `numeric is None` → der Toenungs-Zweig "
        f"`key == 'thunder'` ist strukturell nie erfuellt."
    )


# ===========================================================================
# AC-3: Mittlere Gewittergefahr faerbt orange, nicht rot
# ===========================================================================

def test_ac3_thunder_med_is_watch_and_orange():
    """AC-3: GIVEN eine Stundenzeile mit Gewitterstufe MED / WHEN die
    Briefing-Stundentabelle gerendert wird / THEN zeigt der Risiko-Punkt
    'Achtung' (orange) und die Gewitterzelle ist orange hinterlegt
    (#fad6b8) — nicht rot, nicht gruen."""
    html = _render_one(_row(thunder=ThunderLevel.MED))

    color = _risk_dot_color(html)
    assert color == DOT_WATCH.lower(), (
        f"Risiko-Punkt bei Gewitterstufe MED ist {color!r}, erwartet "
        f"{DOT_WATCH!r} (orange/watch). Heute liefert `_row_risk` 'ok' → "
        f"gruen ({DOT_OK}), weil der Enum-Wert als Zahl gelesen wird."
    )

    bg = _thunder_cell_bg(html)
    assert bg == CELL_ORANGE, (
        f"Gewitterzelle bei Stufe MED hat Hintergrund {bg!r}, erwartet "
        f"{CELL_ORANGE!r} (orange). Heute bleibt sie ungefaerbt (None)."
    )


# ===========================================================================
# AC-4: Keine Gewittergefahr bleibt unauffaellig (Regressionsschutz)
# ===========================================================================

def test_ac4_thunder_none_and_missing_stay_unauffaellig():
    """AC-4: GIVEN eine Stundenzeile mit Gewitterstufe NONE bzw. ganz ohne
    Gewitterwert und sonst unauffaelligen Werten / WHEN die Briefing-
    Stundentabelle gerendert wird / THEN bleibt der Risiko-Punkt gruen und
    die Gewitterzelle ungefaerbt — damit die Behebung von AC-1/AC-2 keine
    falschen Positiv-Meldungen erzeugt.

    Die beiden Erhalt-Zusicherungen (gruen/ungefaerbt) treffen bereits heute
    zu — sie sind Regressionsschutz. Rot ist dieser Test heute wegen der
    dritten Zusicherung: Entwarnung (NONE) und hohe Gefahr (HIGH) duerfen
    nicht identisch aussehen. Genau das ist heute der Fall (beide gruen,
    beide ungefaerbt) und ist der nutzersichtbare Kern von #1418. Ohne diese
    Unterscheidungs-Pruefung waere AC-4 auch von einem Schein-Fix erfuellt,
    der einfach nichts faerbt.
    """
    html_none = _render_one(_row(thunder=ThunderLevel.NONE))
    color_none = _risk_dot_color(html_none)
    bg_none = _thunder_cell_bg(html_none)

    html_missing = _render_one(_row())  # kein "thunder"-Schluessel
    color_missing = _risk_dot_color(html_missing)
    bg_missing = _thunder_cell_bg(html_missing)

    assert color_none == DOT_OK.lower(), (
        f"Risiko-Punkt bei Gewitterstufe NONE ist {color_none!r}, erwartet "
        f"{DOT_OK!r} (gruen) — NONE darf nie zum Risiko beitragen."
    )
    assert bg_none is None, (
        f"Gewitterzelle bei Stufe NONE ist mit {bg_none!r} hinterlegt, "
        f"erwartet ungefaerbt (None)."
    )
    assert color_missing == DOT_OK.lower(), (
        f"Risiko-Punkt ohne Gewitterwert ist {color_missing!r}, erwartet "
        f"{DOT_OK!r} (gruen)."
    )
    assert bg_missing is None, (
        f"Gewitterzelle ohne Gewitterwert ist mit {bg_missing!r} hinterlegt, "
        f"erwartet ungefaerbt (None)."
    )

    # Unterscheidbarkeit: Entwarnung darf nicht aussehen wie hohe Gefahr.
    html_high = _render_one(_row(thunder=ThunderLevel.HIGH))
    color_high = _risk_dot_color(html_high)
    bg_high = _thunder_cell_bg(html_high)
    assert (color_high, bg_high) != (color_none, bg_none), (
        f"Gewitterstufe HIGH rendert exakt wie NONE — Punkt {color_high!r}, "
        f"Zelle {bg_high!r} in beiden Faellen. Der Nutzer kann Entwarnung und "
        f"hohe Gewittergefahr an Punkt und Zellfarbe nicht unterscheiden "
        f"(#1418): der Enum-Wert wird an beiden Stellen als Zahl gelesen."
    )
