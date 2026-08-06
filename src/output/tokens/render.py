"""Render TokenLine to wire format with HR/TH fusion + §6 truncation."""
from __future__ import annotations

import re
from dataclasses import replace

from output.tokens.dto import Token, TokenLine

# §6 removal order (one symbol at a time, repeated until budget met).
# Issue #1435 E3b: Schnee-Kuerzel folgen dem Wetter-Register (SL/NS24+/SD);
# die Rangfolge selbst ist unveraendert.
DROP_ORDER = ["DBG", "WC", "AV", "SL", "NS24+", "SD", "Z:", "MAX", "M:"]


def _fuse(tokens: list[Token]) -> list[str]:
    parts: list[str] = []
    i = 0
    warn_marker_pending = True
    while i < len(tokens):
        t = tokens[i]
        # Issue #1318: der `!`-Marker leitet den Warn-Block genau einmal ein.
        if t.category == "official_alert":
            prefix = "!" if warn_marker_pending else ""
            warn_marker_pending = False
            parts.append(f"{prefix}{t.render()}")
            i += 1
            continue
        if (t.symbol == "HR:" and t.category == "vigilance"
                and i + 1 < len(tokens)
                and tokens[i + 1].symbol == "TH:"
                and tokens[i + 1].category == "vigilance"):
            parts.append(f"{t.render()}{tokens[i + 1].render()}")
            i += 2
        else:
            parts.append(t.render())
            i += 1
    return parts


def _draw(stage: str, tokens: list[Token]) -> str:
    return f"{stage}: " + " ".join(_fuse(tokens))


def _drop_first(tokens: list[Token], symbol: str) -> bool:
    for i, t in enumerate(tokens):
        if t.symbol == symbol:
            del tokens[i]
            return True
    return False


def _strip_peaks(tokens: list[Token]) -> bool:
    changed = False
    for i, t in enumerate(tokens):
        if t.category == "forecast" and "(" in t.value:
            tokens[i] = replace(t, value=re.sub(r"\([^)]*\)", "", t.value))
            changed = True
    return changed


def _truncate(tokens: list[Token], stage: str, mx: int) -> tuple[list[Token], bool]:
    if len(_draw(stage, tokens)) <= mx:
        return tokens, False
    truncated = False
    for sym in DROP_ORDER:
        while _drop_first(tokens, sym):
            truncated = True
            if len(_draw(stage, tokens)) <= mx:
                return tokens, True
    if _strip_peaks(tokens):
        truncated = True
        if len(_draw(stage, tokens)) <= mx:
            return tokens, True
    # Issue #1410 §3b: die gefuehlte Temperatur ist eine Komfort-Zusatzangabe
    # und faellt deshalb noch VOR PR -- die sicherheitsrelevanten
    # Planungsgroessen (R/PR/W/G/TH) bleiben laenger stehen.
    for sym in ("FN", "FK", "FD"):
        if _drop_first(tokens, sym):
            truncated = True
            if len(_draw(stage, tokens)) <= mx:
                return tokens, True
    while _drop_first(tokens, "PR"):
        truncated = True
        if len(_draw(stage, tokens)) <= mx:
            return tokens, True
    # Innerhalb des gemessenen Trios faellt K zuerst (neuester Wert), dann D,
    # dann N zuletzt (bestehende Reihenfolge unveraendert).
    for sym in ("K", "D", "N"):
        if _drop_first(tokens, sym):
            truncated = True
            if len(_draw(stage, tokens)) <= mx:
                return tokens, True
    # Last resort: drop forecast/vigilance/official_alert tokens by ascending
    # priority. Issue #1318: die amtliche Warnung traegt die hoechste Prioritaet
    # und faellt damit als allerletzte. Entfernt wird das GEWAEHLTE Token
    # (Identitaet), nicht das erste mit gleichem Symbol — 'TH:' tragen
    # Vorhersage, Vigilance und Warn-Block gemeinsam.
    _last_resort = ("forecast", "vigilance", "official_alert")
    while len([t for t in tokens if t.category in _last_resort]) > 1:
        cand = sorted(
            [t for t in tokens if t.category in _last_resort],
            key=lambda t: t.priority,
        )[0]
        tokens.remove(cand)
        truncated = True
        if len(_draw(stage, tokens)) <= mx:
            return tokens, True
    if len(_draw(stage, tokens)) > mx:
        raise ValueError(
            f"Cannot truncate token line below {mx} characters; "
            f"current length {len(_draw(stage, tokens))}"
        )
    return tokens, truncated


def render_line(line: TokenLine, max_length: int) -> str:
    """Render with §6 truncation if needed. Mutates frozen DTO via setattr."""
    tokens = list(line.tokens)
    full = _draw(line.stage_name, tokens)
    object.__setattr__(line, "full_length", len(full))
    if len(full) <= max_length:
        return full
    truncated_tokens, was = _truncate(tokens, line.stage_name, max_length)
    object.__setattr__(line, "truncated", was)
    return _draw(line.stage_name, truncated_tokens)


def render_line_with_survivors(line: TokenLine, max_length: int) -> tuple[str, set[str]]:
    """Issue #923: wie render_line(), liefert zusaetzlich die nach der
    §6-Kuerzung ueberlebenden Token-Symbole (fuer die SMS-Fidelity-Vorschau,
    die daraus auf survivende metric_ids zurueckschliesst). Reine Nachbar-
    funktion -- render_line() selbst bleibt unveraendert, kein Produktivpfad
    (E-Mail/Telegram/SMS-Versand) importiert diese Funktion."""
    tokens = list(line.tokens)
    full = _draw(line.stage_name, tokens)
    if len(full) <= max_length:
        return full, {t.symbol for t in tokens}
    truncated_tokens, _was = _truncate(tokens, line.stage_name, max_length)
    return _draw(line.stage_name, truncated_tokens), {t.symbol for t in truncated_tokens}
