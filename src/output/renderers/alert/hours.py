"""Stundenzeilen des Abweichungsalarms (Issue #1737).

EINE Logik fuer Trip UND Ortsvergleich (ADR-0021): welche Stunden betroffen
sind (`affected_hours`), wie viele gezeigt werden (Kappung) und wie eine Zelle
aussieht (`format_cell`, dasselbe `fmt_val` wie das Briefing des Kanals).
Nur Daten -- keine Empfehlung, keine berechnete Prozentangabe.
"""
from __future__ import annotations

from app.metric_catalog import get_metric
from utils.timezone import _as_utc, local_fmt

from .model import AlertHourRow

MAX_ROWS = 6
# Metriken mit Stufe: ampelfaehig (helpers._AMPEL_CAPABLE_METRIC_IDS) + Gewitter.
_LEVEL_METRICS = frozenset(
    {"thunder", "wind", "gust", "precipitation", "rain_probability", "cape"}
)
# fmt_val kennt nur "temp" als Temperatur-Spalte; die Varianten teilen ihr Format.
_CELL_KEY_ALIAS = {
    "temp_cold": "temp", "temp_night": "temp",
    "temp_day_low": "temp", "temp_day_high": "temp",
}


def _numeric(metric_id: str, raw) -> float | None:
    """Anzeige-/Rechenwert einer Stunde (Gewitter: Ordinale 0..3)."""
    if raw is None:
        return None
    if metric_id == "thunder":
        from output.metric_format import thunder_ordinal
        return float(thunder_ordinal(raw))
    return raw


def _stage(metric_id: str, value) -> int | None:
    """Stufe einer Stunde (Gewitter: Ordinale, sonst Ampelband-Index)."""
    if metric_id == "thunder":
        return int(round(value))
    from output.renderers.email.helpers import _AMPEL_STAGE_ORDER, ampel_level
    level = ampel_level(metric_id, value)
    return _AMPEL_STAGE_ORDER.index(level) if level in _AMPEL_STAGE_ORDER else None


def _series(ts, dp_field: str, metric_id: str, window) -> dict:
    """{UTC-Zeitstempel: Wert} der Reihe, optional auf das Segmentfenster
    (beide Grenzen inklusive, wie `_peak_occurred_at`) begrenzt."""
    out: dict = {}
    for p in getattr(ts, "data", None) or []:
        if p.ts is None:
            continue
        t = _as_utc(p.ts)
        if window is not None and not (window[0] <= t <= window[1]):
            continue
        val = _numeric(metric_id, getattr(p, dp_field, None))
        if val is not None:
            out[t] = val
    return out


def _is_affected(metric_id, old, new, threshold, level_metric) -> bool:
    if level_metric:
        return _stage(metric_id, old) != _stage(metric_id, new)
    return abs(new - old) >= threshold


def _strength(metric_id, old, new, level_metric) -> tuple:
    step = 0
    if level_metric and old is not None:
        a, b = _stage(metric_id, old), _stage(metric_id, new)
        step = abs((a or 0) - (b or 0))
    return (step, abs(new - old) if old is not None else float(new))


def _affected_range(metric_id, series, old, threshold, value_from, level_metric):
    """Zusammenhaengender Bereich [(ts, alt|None, neu)] von der ersten bis zur
    letzten betroffenen Stunde (AC-6/AC-10)."""
    if old:
        hours = [(t, old[t], series[t]) for t in sorted(series) if t in old]
        hit = [
            i for i, (_t, o, n) in enumerate(hours)
            if _is_affected(metric_id, o, n, threshold, level_metric)
        ]
        if not hit:  # verteilte Summe: jede abweichende Stunde zaehlt
            hit = [i for i, (_t, o, n) in enumerate(hours) if n != o]
    else:
        hours = [(t, None, series[t]) for t in sorted(series)]
        if level_metric:
            hit = [i for i, (_t, _o, n) in enumerate(hours) if (_stage(metric_id, n) or 0) > 0]
        else:
            hit = [
                i for i, (_t, _o, n) in enumerate(hours)
                if value_from is not None and abs(n - value_from) >= threshold
            ]
    return hours[hit[0]:hit[-1] + 1] if hit else []


def affected_hours(
    metric_id: str, fresh_ts, anchor_ts, *, threshold: float, value_from, tz,
    window=None,
) -> dict:
    """Stundenzeilen EINES Ereignisses: `{hours, hours_range, hours_capped}`
    (leeres dict = keine Stundenreihe / keine betroffene Stunde).

    `fresh_ts`/`anchor_ts`: `NormalizedTimeseries` der frischen bzw. ALTEN
    Reihe (`anchor_ts` darf fehlen -> nur neuer Wert). Paarung per
    UTC-Zeitstempel, nie per Index. `window`: (start, end) UTC des Segments."""
    if fresh_ts is None:
        return {}
    dp_field = get_metric(metric_id).dp_field
    series = _series(fresh_ts, dp_field, metric_id, window)
    old = _series(anchor_ts, dp_field, metric_id, None) if anchor_ts is not None else {}
    level_metric = metric_id in _LEVEL_METRICS
    rng = _affected_range(metric_id, series, old, threshold, value_from, level_metric)
    if not rng:
        return {}
    shown = rng
    if len(rng) > MAX_ROWS:
        ranked = sorted(
            rng, key=lambda h: _strength(metric_id, h[1], h[2], level_metric), reverse=True,
        )[:MAX_ROWS]
        shown = sorted(ranked, key=lambda h: h[0])
    rows = tuple(AlertHourRow(local_fmt(t, tz), o, n) for t, o, n in shown)
    return {
        "hours": rows,
        "hours_range": (local_fmt(rng[0][0], tz), local_fmt(rng[-1][0], tz)),
        "hours_capped": len(rng) > MAX_ROWS,
    }


def format_cell(
    metric_id: str, value, mode: str, *, html: bool, indicators: frozenset = frozenset(),
) -> str:
    """Zelle genau wie das Briefing (`fmt_val`): ROH = Wort/Zahl, sonst (HTML)
    CSS-Punkt aus derselben Quelle."""
    from output.metric_format import _THUNDER_JE_ORDINAL
    from output.renderers.email.helpers import fmt_val

    col = get_metric(metric_id).col_key
    key = _CELL_KEY_ALIAS.get(col, col)
    if col == "thunder":
        value = _THUNDER_JE_ORDINAL.get(int(round(value)))
    if html:
        return fmt_val(
            key, value, format_modes={key: mode},
            indicator_keys=({key} if mode != "raw" or col in indicators else set()),
            html=True,
        )
    return fmt_val(key, value, format_modes={key: mode})


def mode_for(metric_id: str, modes: dict | None) -> str:
    """Anzeigemodus dieser Metrik in der Kanal-Zuordnung (fehlend = raw)."""
    return (modes or {}).get(get_metric(metric_id).col_key, "raw")


def row_parts(
    e, row: AlertHourRow, modes: dict | None, *, html: bool,
    indicators: frozenset = frozenset(),
) -> list[str]:
    """`[alt, neu]` bzw. `[neu]` (ohne Anker) als Zellen (HTML: Markup)."""
    mode = mode_for(e.metric_id, modes)
    parts = [format_cell(e.metric_id, row.value_to, mode, html=html, indicators=indicators)]
    if row.value_from is not None:
        parts.insert(0, format_cell(
            e.metric_id, row.value_from, mode, html=html, indicators=indicators,
        ))
    return parts
