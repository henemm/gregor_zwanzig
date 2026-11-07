"""Per-metric value calculation (Threshold + Peak) per sms_format.md §5.

Renderings:
    '{symbol}{thr}@{thr_h}({max}@{max_h})'   threshold + peak (default)
    '{symbol}{thr}@{thr_h}'                  Threshold == Max optimisation
    '{symbol}-'                              Null form
"""
from __future__ import annotations

from typing import Callable, Optional

from output.tokens.dto import HourlyValue

LEVELS = {0: "-", 1: "L", 2: "M", 3: "H"}

# Issue #2422 S6 (B2): GSM-7-Einfach-Stufen. Die Klassifikation kommt aus der
# E-Mail (``metric_format.cloud_emoji``), nur die
# Darstellung ist ASCII -- die Baender werden ueber Band-Mittelpunkte auf die
# Stufenwoerter abgebildet, nie als zweite Grenzliste gepflegt.
_CLOUD_STUFEN = ((5.0, "CLR"), (20.0, "FEW"), (50.0, "SCT"), (80.0, "BKN"), (95.0, "OVC"))


def cloud_stufe(pct: float) -> str:
    """Wolken-Stufe CLR/FEW/SCT/BKN/OVC aus den Baendern von ``cloud_emoji``."""
    from output.metric_format import cloud_emoji
    emoji = cloud_emoji(float(pct))
    return next(w for mitte, w in _CLOUD_STUFEN if cloud_emoji(mitte) == emoji)


#: Kuerzel -> Stufen-Abbildung der Groessen mit SMS-Einfachform
#: (Spiegel von ``metric_catalog.SMS_FORMAT_MODE_METRIC_IDS``; Drift-Test).
STUFEN_FN: dict[str, Callable[[float], str]] = {
    "CT": cloud_stufe, "CL": cloud_stufe, "CM": cloud_stufe, "CH": cloud_stufe,
}


def _fmt_num(symbol: str, value: float) -> str:
    if symbol == "R":
        return f"{value:.1f}"
    if symbol == "PR":
        return f"{int(round(value))}%"
    return f"{int(round(value))}"


def _level(value: float) -> str:
    return LEVELS.get(int(round(value)), "-")


_STUFEN_RANG = {"yellow": 1, "orange": 2, "red": 3}


def _peak_per_ampel_stufe(
    symbol: str, samples: tuple[HourlyValue, ...],
    ampel_stufe: Callable[[float], Optional[str]],
    ampel_schaerfe: Callable[[float], tuple],
) -> str:
    """Hervorhebung nach Ampelstufe (Issue #2792, E1/AC-7): beidseitig ab
    Gelb, erste Stunde ab Gelb. Ein Wert 0 wird nicht verschluckt (Windstille
    kann bei Wassersport orange sein).

    Fix-Loop 2 (F003, Koordinator-Entscheid): die Klammer nennt den
    SCHLIMMSTEN Wert unter den hervorgehobenen Stunden mit Stunde
    (``app.ampel.schlimmster_index``: hoechste Stufe, dann weiter vom gruenen
    Bereich, dann die frueheste Stunde), wenn er vom ersten Wert verschieden
    ist. Obere Grenze = Maximum (``G70@8(110@13)``), untere = Minimum
    (Wassersport-Wind ``7@9(3@12)``)."""
    from app.ampel import schlimmster_index
    ordnung = sorted(samples, key=lambda s: s.hour)
    getroffen = [s for s in ordnung if _STUFEN_RANG.get(ampel_stufe(s.value), 0) > 0]
    if not getroffen:
        return "-"
    first = getroffen[0]
    peak = getroffen[schlimmster_index([s.value for s in getroffen], ampel_schaerfe)]
    f_str, p_str = _fmt_num(symbol, first.value), _fmt_num(symbol, peak.value)
    if peak is first or f_str == p_str:
        return f"{f_str}@{first.hour}"
    return f"{f_str}@{first.hour}({p_str}@{peak.hour})"


def render_threshold_peak_value(
    symbol: str, samples: tuple[HourlyValue, ...],
    threshold: Optional[float], *, is_level: bool = False,
    level_labels: Optional[dict] = None,
    stufe_fn: Optional[Callable[[float], str]] = None,
    ampel_stufe: Optional[Callable[[float], Optional[str]]] = None,
    ampel_schaerfe: Optional[Callable[[float], tuple]] = None,
) -> str:
    """Render value-tail per §5. '-' for null form.

    ``ampel_stufe`` (Issue #2792, verdrahtet in S1c-4b ueber
    ``builder._mk_metric``): Wert -> Ampelstufe. Gesetzt ersetzt es
    ``threshold`` (siehe ``_peak_per_ampel_stufe``). Dann ist auch
    ``ampel_schaerfe`` (Wert -> ``app.ampel.ampel_schaerfe``) Pflicht: sie
    waehlt die Klammer je Seite (Fix-Loop 2, F003); ohne sie scheitert der
    Aufruf laut statt still das Maximum zu nehmen.

    Args:
        symbol:       Metric symbol (e.g. 'R', 'W', 'TH').
        samples:      Hourly samples (HourlyValue tuples).
        threshold:    Minimum value to trigger first-crossing detection.
                      None → use peak as first (no threshold filter).
        is_level:     True → format values as level labels rather than numbers.
                      Default label map: LEVELS = {0:'-', 1:'L', 2:'M', 3:'H'}.
        level_labels: Optional override map int→str for is_level=True rendering.
                      Pass e.g. {1: 'MED', 2: 'HIGH'} to get trend-style labels.
                      Does NOT affect callers that omit this param (bit-identical).
        stufe_fn:     Issue #2422 S6 (B2): Einfachform -- ersetzt die Zahl durch
                      ihre Stufe; der Wert beginnt dann mit ':' (Konvention
                      #1824 B). Schwellen-/Fensterlogik bleibt auf den Zahlen.
    """
    if not samples:
        return "-"
    if ampel_stufe is not None:
        if ampel_schaerfe is None:
            raise ValueError("ampel_stufe ohne ampel_schaerfe: Klammer je Seite nicht bestimmbar")  # i18n-log
        return _peak_per_ampel_stufe(symbol, samples, ampel_stufe, ampel_schaerfe)
    peak = max(samples, key=lambda s: (s.value, -s.hour))
    if peak.value <= 0:
        return "-"
    if threshold is None:
        first = peak
    else:
        first = next((s for s in sorted(samples, key=lambda s: s.hour)
                      if s.value >= threshold), None)
        if first is None:
            return "-"
    if stufe_fn is not None:
        f_str, p_str = stufe_fn(first.value), stufe_fn(peak.value)
        if f_str == p_str and first.hour == peak.hour:
            return f":{f_str}@{first.hour}"
        return f":{f_str}@{first.hour}({p_str}@{peak.hour})"
    if is_level:
        _lmap = level_labels if level_labels is not None else LEVELS
        f_str = _lmap.get(int(round(first.value)), "-")
        p_str = _lmap.get(int(round(peak.value)), "-")
    else:
        f_str, p_str = _fmt_num(symbol, first.value), _fmt_num(symbol, peak.value)
    if f_str == p_str and first.hour == peak.hour:
        return f"{f_str}@{first.hour}"
    return f"{f_str}@{first.hour}({p_str}@{peak.hour})"


def render_temperature(value: Optional[float]) -> str:
    return "-" if value is None else f"{int(round(value))}"


render_int = render_temperature


def render_inverse_min_value(
    symbol: str, samples: tuple[HourlyValue, ...],
    threshold: Optional[float], *, unit_factor: float = 1.0, decimals: int = 0,
) -> str:
    """Klasse (b) — Invers-Min: Tages-Tiefstwert im Fenster mit Stunde, kein
    Peak-Klammer-Zusatz (`{min}@{h}`). Issue #1660 Scheibe B, DEC-2b.

    '-' bei fehlenden Samples ODER wenn eine konfigurierte Schwelle NICHT
    unterschritten wird (Invers-Gate: nur `min <= threshold` zeigt einen
    Wert). Ohne Schwelle immer sichtbar. `unit_factor`/`decimals` erlauben
    eine Anzeige-Einheit ungleich dem DTO-Feld (VS: Meter -> km, §7 Known
    Limitations 7).
    """
    if not samples:
        return "-"
    lowest = min(samples, key=lambda s: (s.value, s.hour))
    converted = lowest.value * unit_factor
    if threshold is not None and converted > threshold:
        return "-"
    val_str = f"{converted:.{decimals}f}" if decimals else f"{int(round(converted))}"
    return f"{val_str}@{lowest.hour}"
