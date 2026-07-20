"""Telegram Multi-Bubble-Renderer (Issue #1001).

SPEC: docs/specs/modules/feat_1001_telegram_redesign.md.

Baut die Liste der Telegram-Bubbles (Kopf, Kurzuebersicht, Segment-/Ziel-
Tabellen, optionaler Ausblick, Aktionen) via ``render_telegram_bubbles()``.
Ersetzt die fruehere Prosa-Ausgabe ``render_narrow()`` (Issue #360/#635/
#614/#887 — siehe Spec "Source"-Abschnitt) vollstaendig fuer Telegram.

Pure function (keine I/O). Werte werden ueber das bestehende ``fmt_val`` und
die Katalog-``compact_label`` gemappt.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from app.models import NormalizedTimeseries
    from app.trip import Trip
    from services.day_comparison import DayComparison

from app.metric_catalog import get_metric
from app.models import SegmentWeatherData, StabilityResult, ThunderLevel, UnifiedWeatherDisplayConfig
from utils.timezone import local_fmt

from output.renderers.alert.render import _esc
from output.renderers.channel_layout import render_for_channel
from output.renderers.email.helpers import fmt_val, format_trend_tokens
from services.trip_command_processor import ACTIONS_BUBBLE_BUTTONS

# Großzügige Wrap-Breite für Telegram-Prosa-Zeilen (Kopf-/Kurzuebersicht-
# /Mini-Header-Bubbles, #635-Erbe). Telegram sendet Klartext (proportional)
# und reflowt selbst — normale Alpendaten (~46 Zeichen) sollen auf einer
# Zeile bleiben. Pathologisch lange Zeilen werden bei 56 Zeichen als
# Sicherheitsnetz umbrochen.
_TG_PROSE_WIDTH = 56

# AC-9: harte Obergrenze fuer jede Segment-/Ziel-/Ausblick-Tabellenzeile
# (<pre>-Block), damit auf einem iPhone-Standardbildschirm kein Umbruch
# entsteht. Verifiziert gegen eine 8-Spalten-Tabelle (Zeit + 7 Metriken) mit
# den breitest moeglichen Zellwerten — siehe
# tests/tdd/test_issue_1001_telegram_bubbles.py::TestAC9TableWidthLimitStructural.
_TG_TABLE_WIDTH = 32


def _col_key(metric_id: str) -> Optional[str]:
    try:
        return get_metric(metric_id).col_key
    except KeyError:
        return None


def _compact_label(metric_id: str) -> str:
    try:
        return get_metric(metric_id).compact_label
    except KeyError:
        return metric_id[:2].upper()


def _cell(metric_id: str, row: dict, friendly_keys: set[str]) -> str:
    """Formatiere den Wert einer Metrik aus einem Tabellen-Row-Dict."""
    key = _col_key(metric_id)
    if key is None:
        return "–"
    return fmt_val(key, row.get(key), friendly_keys=friendly_keys, row=row)


def _wrap(text: str, width: int) -> list[str]:
    """Bricht ``text`` an Wortgrenzen auf <=``width``-breite Zeilen um."""
    if len(text) <= width:
        return [text]
    words = text.split(" ")
    lines: list[str] = []
    cur = ""
    for w in words:
        candidate = w if not cur else f"{cur} {w}"
        if len(candidate) <= width:
            cur = candidate
            continue
        if cur:
            lines.append(cur)
        # Einzelnes Wort laenger als width -> hart zerteilen.
        while len(w) > width:
            lines.append(w[:width])
            w = w[width:]
        cur = w
    if cur:
        lines.append(cur)
    return lines


def _detail_lines(
    metric_ids: list[str], row: dict, friendly_keys: set[str], width: int,
) -> list[str]:
    """Baue die ``·``-getrennte Detail-Zeile(n) fuer ``detail_metrics``.

    Wird auf ``width`` umgebrochen, sodass auch Signal jede Zeile <=26 haelt.
    """
    parts: list[str] = []
    for mid in metric_ids:
        val = _cell(mid, row, friendly_keys)
        parts.append(f"{_compact_label(mid)} {val}")

    lines: list[str] = []
    cur = ""
    for part in parts:
        candidate = part if not cur else f"{cur} · {part}"
        if len(candidate) <= width:
            cur = candidate
            continue
        if cur:
            lines.append(cur)
        # Ein Einzel-Part koennte breiter als width sein -> hart umbrechen.
        for sub in _wrap(part, width):
            lines.append(sub)
        cur = ""
    if cur:
        lines.append(cur)
    return lines


def _narrow_table(
    table_columns: list[str], rows: list[dict], friendly_keys: set[str],
    width: int,
) -> list[str]:
    """Schmale Monospace-Tabelle: Zeit + gekappte Metrik-Spalten.

    Spaltenbreiten werden an den breitesten Zellinhalt angepasst; zu breite
    Zeilen werden anschliessend hart umgebrochen (width-Constraint).
    """
    headers = ["Zt"] + [_compact_label(m) for m in table_columns]
    matrix: list[list[str]] = []
    for r in rows:
        cells = [str(r.get("time", ""))]
        for mid in table_columns:
            cells.append(_cell(mid, r, friendly_keys))
        matrix.append(cells)

    widths = [len(h) for h in headers]
    for cells in matrix:
        for i, c in enumerate(cells):
            widths[i] = max(widths[i], len(c))

    def _join(cells: list[str]) -> str:
        return " ".join(c.ljust(widths[i]) for i, c in enumerate(cells)).rstrip()

    lines = [_join(headers)]
    for cells in matrix:
        lines.append(_join(cells))

    # Bubble-Constraint hart durchsetzen: zu breite Zeilen zerteilen.
    out: list[str] = []
    for ln in lines:
        out.extend(_wrap(ln, width) if len(ln) > width else [ln])
    return out


def _thunder_severity(level: Optional[ThunderLevel]) -> int:
    """Issue #1214 Scheibe 6: Wrapper, delegiert an die kanonische Ordinal-Quelle."""
    from output.metric_format import thunder_ordinal
    return thunder_ordinal(level)


def _tg_day_footer(
    segments: list[SegmentWeatherData],
    enabled_metric_ids: set[str] | list[str],
    *,
    night_weather: Optional["NormalizedTimeseries"] = None,
    tz: ZoneInfo = ZoneInfo("UTC"),
) -> Optional[str]:
    """Fußzeile mit Tageswerten (AC-6): ⚡ kein|MED|HIGH · Sicht gut|… · 0°C-Grenze N m.

    Issue #954: jeder Teil erscheint nur, wenn die zugehörige Metrik in
    ``enabled_metric_ids`` aktiviert ist.

    Gewitter (Issue #1317 / Epic #1319 Scheibe A): schlimmstes Ordinal aus dem
    geteilten Tagesfenster 04-19 (``day_window.build_day_window_points``) —
    dieselbe Quelle und dasselbe Fenster wie SMS/Kurzzusammenfassung/Pillen
    (ADR-0025-Konsistenz), statt nur der Wanderzeit je Segment (#1275).
    """
    from output.renderers.day_window import build_day_window_points

    enabled = set(enabled_metric_ids)
    max_thunder_sev = 0
    min_vis: Optional[int] = None
    rep_freeze: Optional[int] = None

    if "thunder" in enabled:
        for dp in build_day_window_points(segments, night_weather, tz):
            sev = _thunder_severity(dp.thunder_level)
            if sev > max_thunder_sev:
                max_thunder_sev = sev

    for sd in segments:
        agg = sd.aggregated
        if agg.visibility_min_m is not None:
            if min_vis is None or agg.visibility_min_m < min_vis:
                min_vis = agg.visibility_min_m
        if rep_freeze is None and agg.freezing_level_m is not None:
            rep_freeze = agg.freezing_level_m

    parts: list[str] = []

    # Gewitter
    if "thunder" in enabled:
        if max_thunder_sev == 0:
            thunder_word = "kein"
        elif max_thunder_sev == 1:
            thunder_word = "MED"
        else:
            thunder_word = "HIGH"
        parts.append(f"⚡ {thunder_word}")

    # Sicht
    if "visibility" in enabled and min_vis is not None:
        if min_vis >= 10000:
            vis_word = "gut"
        elif min_vis >= 4000:
            vis_word = "mäßig"
        else:
            vis_word = "schlecht"
        parts.append(f"Sicht {vis_word}")

    # 0°C-Grenze
    if "freezing_level" in enabled and rep_freeze is not None:
        parts.append(f"0°C-Grenze {rep_freeze} m")

    if not parts:
        return None
    return " · ".join(parts)


def _tg_vortag_line(day_comparison: Optional["DayComparison"]) -> Optional[str]:
    """F6 (#752): Kompakte Vortag-Zeile für Telegram.

    Sammelt alle abweichenden Metrik-Deltas über alle Segmente, sortiert
    absteigend nach |delta| und nimmt die Top-3. Gibt None zurück wenn keine
    abweichenden Metriken vorliegen (oder day_comparison None/leer).
    """
    from services.day_comparison import ComparisonDirection

    if day_comparison is None or not day_comparison.entries:
        return None

    # Klassifikation Issue #1214 Scheibe 5, Kategorie b: KEINE Migration auf
    # metric_format.format_value. _LABELS ist ein bewusst kurzes Telegram-
    # Delta-Vokabular fuer die "Ggue. Vortag"-Zeile — Labels weichen echt vom
    # Katalog ab ("Regen" != "Niederschlag", "Temp max"/"Temp min" teilen
    # sich einen Katalog-Eintrag "Temperatur"). Zudem werden Delta-Werte roh
    # und ungerundet ausgegeben (f"{delta}{unit}", Einheit ohne Leerzeichen);
    # format_value wuerde runden und ein Leerzeichen einfuegen.
    # (Label, MetricDelta) pro Metrik je Segment einsammeln.
    _LABELS = [
        ("precip_sum", "Regen", "mm"),
        ("wind_max", "Wind", "km/h"),
        ("gust_max", "Böen", "km/h"),
        ("temp_max", "Temp max", "°C"),
        ("temp_min", "Temp min", "°C"),
        ("thunder", "Gewitter", ""),
    ]

    collected: list[tuple[float, str, str, float]] = []  # (|delta|, label, unit, delta)
    for entry in day_comparison.entries:
        for attr, label, unit in _LABELS:
            md = getattr(entry, attr)
            if md.direction == ComparisonDirection.MISSING or md.delta is None:
                continue
            if abs(md.delta) <= 0:
                continue
            collected.append((abs(md.delta), label, unit, md.delta))

    if not collected:
        return None

    collected.sort(key=lambda t: t[0], reverse=True)
    top = collected[:3]

    parts = []
    for _absd, label, unit, delta in top:
        sign = "+" if delta > 0 else ""
        if unit:
            parts.append(f"{label} {sign}{delta}{unit}")
        else:
            parts.append(f"{label} {sign}{delta}")
    return "Ggü. Vortag: " + ", ".join(parts)


@dataclass(frozen=True)
class TelegramBubble:
    """Eine einzelne Telegram-``sendMessage``-Nachricht (Issue #1001).

    ``reply_markup`` ist nur bei der letzten (Aktionen-)Bubble gesetzt.
    """
    text: str
    reply_markup: Optional[dict] = None


def _official_alert_bubble(
    segments: list[SegmentWeatherData], tz: ZoneInfo, trip: Optional["Trip"] = None,
) -> Optional[TelegramBubble]:
    """Amtliche Warnungen als eigene Bubble (Issue #1318 Scheibe B, AC-8).

    Nutzt den GETEILTEN `render_official_alert_telegram` — kein zweiter
    Renderer, keine SMS-Kuerzel, keine Kappung (Telegram ist ausgeschrieben).
    Gefiltert wird ueber dasselbe `MIN_SMS_LEVEL` wie die SMS: beide Kanaele
    zeigen dieselbe Teilmenge, nur unterschiedlich lang ausformuliert
    (ADR-0025). Ohne Warnung >= Filter -> `None` -> Bubble-Liste bleibt
    bit-identisch zum Stand vor #1318.

    `trip` ist optional: fehlt es, faellt nur die "gesamte Route"-Verdichtung
    des Umfangs weg — die Warnung selbst haengt an den Segmenten und darf nie
    an einem fehlenden Kontext-Parameter scheitern.
    """
    from output.renderers.alert.official_alerts import (
        build_official_alert_notices, official_alert_source_label,
        render_official_alert_telegram,
    )
    from output.tokens.hazard_symbols import MIN_SMS_LEVEL

    tagged = [
        (alert, [str(sd.segment.segment_id)])
        for sd in segments
        for alert in (getattr(sd, "official_alerts", None) or [])
        if alert.level >= MIN_SMS_LEVEL
    ]
    if not tagged:
        return None
    notices = build_official_alert_notices(trip, tagged)
    if not notices:
        return None
    sources = list(dict.fromkeys(
        official_alert_source_label(alert.source) for alert, _ in tagged
    ))
    return TelegramBubble(text=render_official_alert_telegram(
        notices, prefix="Amtliche Warnung", source_label=" · ".join(sources), tz=tz,
    ))


def _overview_line(metric_id: str, seg_tables: list[list[dict]], fkeys: set[str]) -> str:
    """Eine Kurzübersicht-Zeile ``{Kürzel} {Min}-{Max}@{Peak-Stunde}`` (oder
    Einzelwert/kategorisch).

    Sammelt alle Rohwerte der Metrik ueber alle Segmente/Stunden hinweg und
    formatiert Minimum/Maximum ueber die bestehende ``fmt_val``-Formatierung.
    Bei unterschiedlichem Min/Max wird zusaetzlich die Uhrzeit des Maximums
    angehaengt (``@{Stunde}``, gleiche Konvention wie die Peak-Token in
    ``format_trend_tokens()``/``render_threshold_peak_value()``) — die fuer
    Entscheidungen relevantere Spitze (z.B. Windboeen-Spitze). Fuer die
    Gewitter-Metrik (``thunder``) wird analog zu ``_tg_day_footer()`` der
    Tages-Schlimmstwert ueber ``_thunder_severity()`` ermittelt (Issue #1001
    Adversary-Finding F001: sonst widerspricht sich diese Zeile mit der
    Fusszeile derselben Bubble). Andere nicht-numerische Metriken zeigen
    weiterhin den zuletzt beobachteten Wert ohne Uhrzeit.
    """
    label = _compact_label(metric_id)
    key = _col_key(metric_id)
    if key is None:
        return f"{label} –"

    hits = [r for rows in seg_tables for r in rows if r.get(key) is not None]
    if not hits:
        return f"{label} –"

    try:
        nums = [float(h[key]) for h in hits]
        lo_row = hits[nums.index(min(nums))]
        hi_row = hits[nums.index(max(nums))]
        lo = _cell(metric_id, lo_row, fkeys)
        hi = _cell(metric_id, hi_row, fkeys)
        if lo == hi:
            value = lo
        else:
            peak_hour = hi_row.get("time", "")
            value = f"{lo}-{hi}@{peak_hour}" if peak_hour else f"{lo}-{hi}"
    except (TypeError, ValueError):
        if metric_id == "thunder":
            worst_row = max(hits, key=lambda h: _thunder_severity(h.get(key)))
            value = _cell(metric_id, worst_row, fkeys)
        else:
            value = _cell(metric_id, hits[-1], fkeys)
    return f"{label} {value}"


def _segment_mini_header(seg_data: SegmentWeatherData) -> str:
    """``"{Bezeichnung} · {km-Range} · {Höhen-Range}"`` (Spec Implementation Details)."""
    seg = seg_data.segment
    km_range = (
        f"{seg.start_point.distance_from_start_km:.1f}"
        f"–{seg.end_point.distance_from_start_km:.1f} km"
    )
    height_range = f"↑{seg.ascent_m:.0f} m ↓{seg.descent_m:.0f} m"
    label = "Ziel" if str(seg.segment_id) == "Ziel" else f"Segment {seg.segment_id}"
    return f"{label} · {km_range} · {height_range}"


def _outlook_lines(multi_day_trend: list[dict]) -> list[str]:
    """3-Tage-Trend-Zeilen (Issue #623/#640-Rechenlogik, jetzt Ausblick-Bubble)."""
    lines: list[str] = ["Ausblick"]
    for stage in multi_day_trend:
        tok = format_trend_tokens(stage)
        weekday = stage.get("weekday", "")
        pt, wt, tt = tok["precip_token"], tok["wind_token"], tok["thunder_token"]
        precip_part = f"R{pt}" if pt != "-" else (tok["precip_str"] if tok["precip_str"] != "–" else "R–")
        wind_part = f"W{wt}" if wt != "-" else tok["wind_str"]
        thunder_part = f"⚡{tt}" if tt != "-" else tok["thunder_plain"]
        trend_line = f"{weekday}  {tok['temp_str']}  {precip_part}  {wind_part}  {thunder_part}"
        lines.extend(_wrap(trend_line, _TG_PROSE_WIDTH))
        note = stage.get("note")
        if note:
            lines.extend(_wrap(f"    ↳ {note}", _TG_PROSE_WIDTH))
    return lines


def render_telegram_bubbles(
    *,
    segments: list[SegmentWeatherData],
    seg_tables: list[list[dict]],
    dc: UnifiedWeatherDisplayConfig,
    report_type: str,
    tz: ZoneInfo,
    trip_name: str = "",
    friendly_keys: Optional[set[str]] = None,
    stability_result: Optional[StabilityResult] = None,
    multi_day_trend: Optional[list[dict]] = None,
    day_comparison: Optional["DayComparison"] = None,
    night_weather: Optional["NormalizedTimeseries"] = None,
    trip: Optional["Trip"] = None,
) -> list[TelegramBubble]:
    """Render die Telegram-Briefing-Bubble-Liste (Issue #1001). Pure function.

    Reihenfolge: Kopf, Kurzuebersicht (alle konfigurierten Metriken,
    ``telegram_kurzform`` wirkungslos — AC-10), je Segment/Ziel eine Tabellen-
    Bubble, optionaler Ausblick (nur wenn ``multi_day_trend`` gesetzt),
    Aktionen (Inline-Keyboard).
    """
    fkeys = friendly_keys if friendly_keys is not None else set()
    layout = render_for_channel("telegram", dc, report_type)
    bubbles: list[TelegramBubble] = []

    # 1. Kopf-Bubble.
    head_lines: list[str] = []
    if trip_name:
        head_lines.extend(_wrap(_esc(trip_name), _TG_PROSE_WIDTH))
    report_date = ""
    if segments:
        # Bug #397: Datums-Header in Ortszeit.
        report_date = local_fmt(segments[0].segment.start_time, tz, "%d.%m.%Y")
    head2 = f"{report_type.title()} {report_date}".strip()
    if head2:
        head_lines.extend(_wrap(_esc(head2), _TG_PROSE_WIDTH))
    if stability_result is not None:
        head_lines.extend(_wrap(_esc(f"WL: {stability_result.label}"), _TG_PROSE_WIDTH))
    bubbles.append(TelegramBubble(text="\n".join(head_lines)))

    # 1b. Amtliche Warnungen (#1318 AC-8) — direkt nach dem Kopf, weil
    # sicherheitsrelevant. Ohne Warnung >= MIN_SMS_LEVEL entfaellt sie ganz.
    warn_bubble = _official_alert_bubble(segments, tz, trip)
    if warn_bubble is not None:
        bubbles.append(warn_bubble)

    # 2. Kurzuebersicht-Bubble — ALLE konfigurierten Metriken (AC-3), immer
    # vorhanden, unabhaengig von telegram_kurzform (AC-10).
    overview_lines: list[str] = ["Kurzübersicht"]
    for mid in dc.get_enabled_metric_ids():
        overview_lines.extend(_wrap(_esc(_overview_line(mid, seg_tables, fkeys)), _TG_PROSE_WIDTH))
    footer = _tg_day_footer(
        [sd for sd in segments if not sd.has_error], dc.get_enabled_metric_ids(),
        night_weather=night_weather, tz=tz,
    )
    if footer:
        overview_lines.append("")
        overview_lines.extend(_wrap(_esc(footer), _TG_PROSE_WIDTH))
    vortag_line = _tg_vortag_line(day_comparison)
    if vortag_line:
        overview_lines.append("")
        overview_lines.extend(_wrap(_esc(vortag_line), _TG_PROSE_WIDTH))
    bubbles.append(TelegramBubble(text="\n".join(overview_lines)))

    # 3./4. Segment-/Ziel-Bubbles: Mini-Header + echte Monospace-Tabelle.
    for seg_data, rows in zip(segments, seg_tables):
        seg = seg_data.segment
        if seg_data.has_error:
            bubbles.append(TelegramBubble(text=_esc(f"Seg {seg.segment_id}: keine Daten")))
            continue

        text_lines = _wrap(_esc(_segment_mini_header(seg_data)), _TG_PROSE_WIDTH)
        if layout.table_columns and rows:
            table_lines = _narrow_table(layout.table_columns, rows, fkeys, _TG_TABLE_WIDTH)
            escaped_table = "\n".join(_esc(ln) for ln in table_lines)
            text_lines = text_lines + ["<pre>", escaped_table, "</pre>"]
        bubbles.append(TelegramBubble(text="\n".join(text_lines)))

    # 5. Ausblick-Bubble (nur wenn multi_day_trend nicht leer).
    if multi_day_trend:
        outlook = [_esc(ln) for ln in _outlook_lines(multi_day_trend)]
        bubbles.append(TelegramBubble(text="\n".join(outlook)))

    # 6. Aktionen-Bubble — einzige Bubble mit reply_markup.
    bubbles.append(TelegramBubble(text="Aktionen", reply_markup=ACTIONS_BUBBLE_BUTTONS))

    return bubbles
