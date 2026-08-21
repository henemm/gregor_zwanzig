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


# ---------------------------------------------------------------------------
# Gewitter-Zellentext des Ausblicks -- Issue #1848 A3
#
# Bis A3 stand der ganze Zellenbau (Tages-Onset, Nachtanteil, Herkunft,
# Hagel-Zusatz) INNERHALB des festen Sieben-Spalten-Zweigs der vier Ausblick-
# Renderer. Der konfigurierbare Zweig setzte nur ``stage["cells"]`` zusammen
# und zeigte deshalb bloss das Stufenwort. Solange der feste Zweig der
# Normalfall war, fiel das nicht auf; seit A3 geht JEDE Tour ueber den
# konfigurierbaren Zweig -- ohne diese Extraktion verloeren alle Touren
# Uhrzeit, Nachtanteil, Herkunft und Hagel auf einen Schlag.
#
# 🔴 Vier Funktionen, nicht eine mit Schaltern: die vier Ausgabeorte haben
# BEWUSST verschiedene Schreibweisen (HTML "mittel @14", Klartext
# "⚡mittel@14", Kompakt dasselbe ohne Herkunft/Hagel, Telegram den rohen
# Token). Ein gemeinsamer Formatierer mit drei Flags haette diese Unterschiede
# nur verschoben. Entscheidend ist, dass es je Ausgabeort GENAU EINE
# Umsetzung gibt, die fester UND konfigurierbarer Zweig aufrufen -- kein
# zweiter Zellenbau daneben.
# ---------------------------------------------------------------------------

# 🔴 KEIN NACHTANTEIL -- DREIFACH BESTAETIGTER PO-ENTSCHEID. Die
# 3-Tages-Vorschau zeigt ausschliesslich das TAGESFENSTER:
#   1. 2026-08-14 urspruenglich (fix_1841_vorschau_metrik_tagesfenster.md
#      AC-3), damals nur fuer den Metrik-Zweig;
#   2. 2026-08-21 bestaetigt und auf ALLE Touren ausgedehnt -- vorgelegt MIT
#      der Verwechslungsluecke (s. u.) und MIT dem vollen Testumfang;
#   3. 2026-08-21 ein Mittelweg ("Nachtanteil nur zeigen, wenn im Tagesfenster
#      nichts liegt") ausdruecklich ABGELEHNT -- keine Sonderfaelle.
# Bis #1848 A3 fuehrte der feste Zweig den Nachtanteil (seit #1653). Mit A3
# entfaellt der feste Zweig als Normalfall -- damit gilt der Entscheid
# ueberall, und die #1653-Nachtangabe entfaellt aus allen VIER
# Ausblick-Darstellungen. DIES ist die zentrale Fundstelle des Entscheids;
# die umgedrehten Tests verweisen auf "#1848 A3" hierher.
#
# 🔴 Bewusst getragene Folge: ein rein naechtliches Gewitter ist in der
# Vorschau nicht von "gar kein Gewitter" zu unterscheiden -- beide zeigen das
# NONE-Zeichen. Vor Punkt 2 und 3 oben ausdruecklich vorgelegt.
#
# ⚠️ Der Entscheid gilt AUSSCHLIESSLICH fuer die 3-Tages-Vorschau. Tages-
# Briefing, Stundenverlauf und Alarme fuehren den Tag/Nacht-Split von
# #1653/#1671 unveraendert weiter -- wer hier eine Verallgemeinerung
# hineinliest, nimmt dort eine fremde Entscheidung zurueck.

def _tagesteil(tok: dict, stage: dict, *, praefix: str, mit_uhrzeit: bool,
               mit_herkunft: bool) -> str:
    """Der Tagesteil der Gewitter-Zelle -- EINE Zweigwahl fuer alle vier
    Ausgabeorte, nur die Schreibweise unterscheidet sich.

    ``praefix``: "" (HTML) oder "⚡" (Klartext/Kompakt/Telegram).
    ``mit_uhrzeit``: HTML setzt ein Leerzeichen vor das ``@`` ("mittel @14"),
    Klartext und Kompakt nicht ("⚡mittel@14"); Telegram nimmt den ROHEN Token
    (``mittel@14(hoch@18)``) und setzt deshalb ``mit_uhrzeit=False``.
    """
    from output.renderers.email.compare_html import _fmt_thunder
    from output.renderers.email.helpers import _THUNDER_MAP

    branch = resolve_thunder_day_branch(tok, stage)
    # Der Zweig-Helfer entscheidet nur ueber ``thunder_day_token != "-"``; ob
    # der Token zerlegbar ist, bleibt Sache des Formatierers -- ein gesetzter,
    # aber unzerlegbarer Token faellt wie im Altcode auf "kein Gewitter"
    # zurueck statt abzustuerzen.
    parts = _thunder_token_parts(tok.get("thunder_day_token", "-")) if branch == "day" else None
    if parts:
        trenn = " " if mit_uhrzeit else ""
        teil = f"{praefix}{parts[0]}{trenn}@{parts[1]}{parts[2]}"
        origin = tok.get("thunder_day_origin") if mit_herkunft else None
        if origin:
            teil += f" · {origin}"
        return teil
    if branch in ("day", "none"):
        # Stundenreihe da, im Tagesfenster aber kein Gewitter: AUSDRUECKLICH
        # "kein Gewitter" (fix_1841 AC-2) -- nicht die Nachtstufe, nicht eine
        # leere Zelle. Das Zeichen dafuer ist bestandsgemaess der Strich
        # (#1488 B: "NONE zeigt bewusst kein Wort, sondern einen
        # Gedankenstrich"), im HTML der lange aus ``_fmt_thunder``.
        return _THUNDER_MAP["NONE"]["plain"] if praefix else _fmt_thunder(None)
    # Ohne jede Stundenreihe (Alt-Aufrufer/Compare) kann der Split nichts
    # sagen -- dann das ungefilterte Aggregat.
    if praefix:
        return tok["thunder_plain"]
    from app.models import ThunderLevel

    level = (stage.get("thunder", "NONE") or "NONE").upper()
    return _fmt_thunder(getattr(ThunderLevel, level, ThunderLevel.NONE))


def thunder_cell_html(tok: dict, stage: dict) -> str:
    """Gewitter-Zelle der HTML-Ausblick-Tabelle (extrahiert aus
    ``render_outlook_table``) -- ``mittel @14 (hoch @18) · CAPE`` plus
    Hagel-Zusatz (#1475). Ohne Gewitter im Tagesfenster der Strich."""
    from output.metric_format import format_hail_note

    zelle = _tagesteil(tok, stage, praefix="", mit_uhrzeit=True, mit_herkunft=True)
    note = format_hail_note(stage.get("hail"))
    return f"{zelle} · {note}" if note else zelle


def thunder_cell_plain(tok: dict, stage: dict) -> str:
    """Gewitterfeld der Klartext-Ausblick-Zeile (extrahiert aus
    ``render_outlook_plain``) -- ``⚡mittel@14 (hoch @18) · CAPE`` plus
    Hagel-Zusatz."""
    from output.metric_format import format_hail_note

    feld = _tagesteil(tok, stage, praefix="⚡", mit_uhrzeit=False, mit_herkunft=True)
    note = format_hail_note(stage.get("hail"))
    return f"{feld} · {note}" if note else feld


def thunder_cell_compact(tok: dict, stage: dict) -> str:
    """Gewitterspalte der Kompakt-Ausblick-Zeile (#1671).

    Wie ``thunder_cell_plain``, aber ohne Herkunfts- und ohne Hagel-Zusatz:
    die Kompakt-Mail traegt beide bestandsgemaess nicht (#1680 S5a AC-13,
    PO-Entscheidung 1 der #1493-Spec). Deshalb eine eigene Funktion statt
    eines Flags -- die Auslassung ist eine Produktentscheidung, keine
    Formatvariante.
    """
    return _tagesteil(tok, stage, praefix="⚡", mit_uhrzeit=False, mit_herkunft=False)


def thunder_cell_telegram(tok: dict, stage: dict) -> str:
    """Gewitterteil der Telegram-Ausblick-Zeile (extrahiert aus
    ``narrow._outlook_lines``) -- der ROHE Token (``⚡mittel@14(hoch@18)``),
    ohne ausgeschriebene Uhrzeit, plus Herkunft."""
    branch = resolve_thunder_day_branch(tok, stage)
    if branch != "day":
        return _tagesteil(tok, stage, praefix="⚡", mit_uhrzeit=False,
                          mit_herkunft=False)
    teil = f"⚡{tok.get('thunder_day_token', '-')}"
    origin = tok.get("thunder_day_origin")
    if origin:
        teil += f" · {origin}"
    return teil


def thunder_column_index(columns: list[dict]) -> Optional[int]:
    """Position der Gewitter-Spalte in einer ``outlook_columns()``-Liste.

    #1848 A3: der konfigurierbare Zweig aller vier Ausblick-Renderer ersetzt
    genau diese eine Zelle durch den ausgabeort-eigenen Zellenbau oben --
    ``stage["cells"]`` traegt dort nur das Stufenwort. Gesucht wird ueber die
    KENNUNG, nicht ueber ``kind == "ordinal"``: waechst der Katalog um eine
    zweite ordinale Groesse, bekaeme die sonst faelschlich den
    Gewitter-Zellenbau.
    """
    for i, column in enumerate(columns):
        if column.get("metric_id") == "thunder":
            return i
    return None
