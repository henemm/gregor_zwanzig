"""Render TokenLine to wire format with HR/TH fusion + §6 truncation."""
from __future__ import annotations

from output.tokens.dto import Token, TokenLine

# §6 Kuerzung (#3047 Runde 7, AC-23, PO-Entscheidung 2026-11-16): bei
# Ueberlaenge faellt die SMS-Liste von HINTEN weg -- ganze Zeilen, Trip und
# Orte gleich. Die fruehere feste Prioritaetsfolge (DROP_ORDER, #1677 AC-6)
# ist abgeloest; sicherheitsrelevante Groessen stehen ueber die Vorbelegung
# der Liste vorn. Amtliche Bausteine (Warnblock, Vigilance, Brandzonen)
# fallen zuletzt, nach Prioritaet; 'X?' (Warndaten nicht abrufbar) nie.
_LIST_CATEGORIES = ("forecast", "wintersport")
_LAST_RESORT = ("fire", "vigilance", "official_alert")


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
        # Issue #2417 AC-27: Meteo-France-Paar VR:/VT: (builder.VIGI_HR/VIGI_TH).
        if (t.symbol == "VR:" and t.category == "vigilance"
                and i + 1 < len(tokens)
                and tokens[i + 1].symbol == "VT:"
                and tokens[i + 1].category == "vigilance"):
            parts.append(f"{t.render()}{tokens[i + 1].render()}")
            i += 2
        else:
            parts.append(t.render())
            i += 1
    return parts


def _draw(stage: str, tokens: list[Token]) -> str:
    return f"{stage}: " + " ".join(_fuse(tokens))


def _drop_last_list_row(tokens: list[Token]) -> bool:
    """Entfernt die hinterste Listenzeile: alle Token mit dem Listenplatz des
    letzten Listen-Tokens (Token ohne Platz zaehlen je fuer sich)."""
    idx = [i for i, t in enumerate(tokens) if t.category in _LIST_CATEGORIES]
    if not idx:
        return False
    last = tokens[idx[-1]]
    if last.list_position is None:
        del tokens[idx[-1]]
        return True
    tokens[:] = [t for t in tokens if not (
        t.category in _LIST_CATEGORIES and t.list_position == last.list_position)]
    return True


def _truncate(tokens: list[Token], stage: str, mx: int) -> tuple[list[Token], bool]:
    if len(_draw(stage, tokens)) <= mx:
        return tokens, False
    truncated = False
    for t in [t for t in tokens if t.category == "debug"]:
        tokens.remove(t)
        truncated = True
    if len(_draw(stage, tokens)) <= mx:
        return tokens, truncated
    while _drop_last_list_row(tokens):
        truncated = True
        if len(_draw(stage, tokens)) <= mx:
            return tokens, True
    # Amtliche Bausteine zuletzt, nach aufsteigender Prioritaet (#1318: der
    # Warnblock traegt die hoechste). Entfernt wird das GEWAEHLTE Token
    # (Identitaet); einer bleibt immer stehen.
    while len([t for t in tokens if t.category in _LAST_RESORT]) > 1:
        cand = sorted(
            [t for t in tokens if t.category in _LAST_RESORT],
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
