"""Geteilte Korridor-mark-Markierung — EIN Baustein fuer Trip- UND
Vergleichs-Mail (Issue #1425 Schritt 1; vorher Compare-only, Issue #1231
Slice 7). ``corridor_inside()`` (``src/services/corridor_match.py``) bleibt
die einzige Match-Quelle — diese Datei buendelt nur die Anzeige-Logik
(Lookup/Ordinal-Uebersetzung/Zell-Stil) an EINER Stelle, damit kein zweiter
Nachbau im Trip-Renderer entsteht (Trip/Compare-Teilungs-Invariante,
CLAUDE.md; Anti-Pattern-Referenz #1170).

SPEC: docs/specs/modules/fix_1425_trip_wertebereiche_wirkung.md
"""
from __future__ import annotations

from typing import Optional

from app.models import Corridor, ThunderLevel
from output.metric_format import thunder_ordinal
from output.renderers.email.design_tokens import G_SUCCESS, tone_css
from services.corridor_match import corridor_inside


def mark_lookup(corridors: list[Corridor] | None, id_map: dict[str, str]) -> dict[str, Corridor]:
    """`corridors` (nur mark=True) ueber `id_map` (Quell-Namensraum ->
    Renderer-Zeilen-Key) aufgeloest. notify-only-Corridors (mark=False) und
    nicht mappbare Metriken fallen raus. Kollidieren zwei Quell-Metriken auf
    demselben Key, gewinnt die letzte -- im Compare-Namensraum folgenlos
    (1:1), s. `mark_lookup_multi` fuer den kollisionssicheren Trip-Fall
    (#1425: temperature_min/temperature_max teilen sich die "temp"-Spalte)."""
    if not corridors:
        return {}
    return {id_map[c.metric]: c for c in corridors if c.mark and c.metric in id_map}


def mark_lookup_multi(
    corridors: list[Corridor] | None, id_map: dict[str, str],
) -> dict[str, list[Corridor]]:
    """Wie `mark_lookup`, sammelt aber ALLE Corridors je Ziel-Key statt nur
    den letzten (Issue #1425): der Trip-Namensraum bildet `temperature_min`
    UND `temperature_max` auf denselben Stunden-Key "temp" ab (zwei
    Alarm-Metriken, eine Spalte) -- eine 1:1-dict-Aufloesung wuerde eine der
    beiden Marken kommentarlos verschlucken."""
    out: dict[str, list[Corridor]] = {}
    for c in corridors or []:
        if not c.mark or c.metric not in id_map:
            continue
        out.setdefault(id_map[c.metric], []).append(c)
    return out


def is_marked(corridor: Optional[Corridor], value) -> bool:
    """corridor_inside() (C5) ist die einzige Match-Quelle. Gewitter-Werte
    (ThunderLevel-Enum) werden vorab per thunder_ordinal() in ihr Ordinal
    uebersetzt -- Corridor.range traegt fuer diese Metrik Ordinalwerte,
    keine Enum-Instanzen."""
    if corridor is None:
        return False
    v = thunder_ordinal(value) if isinstance(value, ThunderLevel) else value
    return bool(corridor_inside(v, corridor.range[0], corridor.range[1]))


def is_marked_any(corridors: Optional[list[Corridor]], value) -> bool:
    """Trip-Variante (#1425) fuer `mark_lookup_multi`: markiert, sobald
    IRGENDEINER der auf denselben Key gemappten Corridors den Wert
    einschliesst -- `temperature_min` deckt die Kaelte-, `temperature_max`
    die Hitze-Grenze derselben "temp"-Spalte ab."""
    return any(is_marked(c, value) for c in (corridors or []))


# Adversary F001 (Fix-Loop, urspruenglich Compare #1231 Slice 7): class=
# "corridor-mark" allein ist unsichtbar (keine <style>-Regel referenziert
# sie) -- die eigentliche Sichtbarkeits-Signatur ist ein additiver gruener
# Border-Balken (Inline-Style, E-Mail-tauglich). Der gruene Hintergrund-Tint
# (tone_css("green")) wird NUR gesetzt, wenn die Zelle noch keinen eigenen
# Severity-Hintergrund traegt -- sonst wuerde er die Severity-Farbe
# verdecken (Design-Prinzip Lesbarkeit, CLAUDE.md).
MARK_BORDER = f"border-left:3px solid {G_SUCCESS};"


def mark_cell_style(bg: str, marked: bool) -> tuple[str, str]:
    """(bg, extra_style) fuer eine Zelle -- `extra_style` wird VOR
    `background:` in den style-String eingefuegt, `bg` ist ggf. auf den
    gruenen Tint umgeschrieben (nur wenn zuvor transparent, s.o.)."""
    if not marked:
        return bg, ""
    mark_bg = tone_css("green")[0] if bg == "transparent" else bg
    return mark_bg, MARK_BORDER
