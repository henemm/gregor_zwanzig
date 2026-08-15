"""Gewitter-Tagesfenster-Zweigwahl -- Issue #1671.

Vor dieser Scheibe entschied jeder der drei betroffenen Kanaele (Klartext-
Mail-Ausblick, Telegram-Trendblock, Kompaktformat-Mail) dieselbe if/elif-
Kette fast identisch selbst: zeigt das Tagesfenster einen Gewitter-Token
(``thunder_day_token``), das Tageswort daraus -- sonst, wenn ueberhaupt eine
Stundenreihe vorliegt, ein explizites "kein Gewitter" -- sonst (Alt-
Aufrufer/Compare ohne Stundenreihe) das ungefilterte 24h-Aggregat
(``thunder_plain``). Zwei der drei Kopien wurden bereits mit #1653
geschrieben, die Kompaktformat-Mail blieb bei #1653 aussen vor (die
eigentliche Ursache dieses Issues) und baute nie eine dritte Kopie.

``resolve_thunder_day_branch()`` ist die EINE Zweigwahl fuer alle drei
Aufrufer (``compact.py``, ``outlook.py`` Klartext, ``narrow.py``); jeder
formatiert das Ergebnis weiterhin selbst (mit/ohne Uhrzeit, mit/ohne
Herkunft, mit/ohne Emoji-Praefix). ``_thunder_token_parts()`` zerlegt einen
Gewitter-Token in seine Bestandteile und wanderte aus ``outlook.py`` hierher
(dritter Verbraucher).

Eigenstaendiges Modul statt Ablage in ``helpers.py`` (#1671-Nachtrag): kein
Import von ``helpers`` hier -- reine Zweig-/Zerlegungs-Logik ohne
Abhaengigkeit auf das dortige Sammelmodul, keine Zirkelimport-Gefahr.
"""
from __future__ import annotations

import re
from typing import Optional


_THUNDER_TOKEN_RE = re.compile(
    r"^([a-zA-Zäöü]+)@(\d+)(?:\(([a-zA-Zäöü]+)@(\d+)\))?"
)


def _thunder_token_parts(token: Optional[str]):
    """Zerlegt einen Gewitter-Token in (Erst-Wort, Erst-Stunde, Peak-Zusatz).

    Issue #1653 (F005): ``render_threshold_peak_value`` haengt den
    Spitzenwert als ``leicht@5(hoch@15)`` an, wenn Erst-Ueberschreitung und
    Spitze im selben Fenster auseinanderfallen -- der meteorologische
    Normalfall eines ueber den Nachmittag eskalierenden Gewitters. Wer nur
    die erste Gruppe liest, unterschlaegt genau die Stufe, vor der der
    Report warnen soll. Der Peak-Zusatz ist "" (leer), wenn Erst == Peak.
    """
    if not token or token == "-":
        return None
    m = _THUNDER_TOKEN_RE.match(token)
    if not m:
        return None
    peak_suffix = f" ({m.group(3)} @{m.group(4)})" if m.group(3) else ""
    return m.group(1), m.group(2), peak_suffix


def resolve_thunder_day_branch(tok: dict, stage: dict) -> str:
    """Waehlt die Datenquelle fuer das Tages-Gewitterwort (#1671).

    Reine Zweigwahl, KEINE Formatierung -- die drei Aufrufer (compact.py,
    outlook.py Klartext, narrow.py) stellen das Ergebnis unterschiedlich
    dar, entscheiden aber identisch. Ersetzt die bis #1671 dreifach fast
    identisch kopierte if/elif-Kette. Ob der Tages-Token tatsaechlich
    zerlegbar ist (``_THUNDER_TOKEN_RE``), prueft dieser Helfer NICHT --
    das bleibt Aufrufer-Sache (siehe render_outlook_plain()/
    _compact_thunder_field()), damit ein gesetzter, aber unzerlegbarer
    Token nicht hier verschluckt wird, sondern beim Aufrufer denselben
    Rueckfall auf "kein Gewitter" durchlaeuft wie im Altcode.

    Returns:
        "day"   -- tok["thunder_day_token"] traegt einen Wert (!= "-"):
                   Wort+Uhrzeit aus dem Tagesfenster verwenden.
        "none"  -- Stundenreihe vorhanden, im Tagesfenster aber leer:
                   explizites "kein Gewitter" zeigen (_THUNDER_MAP["NONE"]).
        "plain" -- keine Stundenreihe (Alt-Aufrufer/Compare): auf das
                   ungefilterte 24h-Aggregat (tok["thunder_plain"]) zurueckfallen.
    """
    if tok.get("thunder_day_token", "-") != "-":
        return "day"
    if stage.get("hourly_thunder"):
        return "none"
    return "plain"
