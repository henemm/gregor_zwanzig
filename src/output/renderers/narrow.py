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
    from output.renderers.email.outlook_state_hint import OutlookState
    from services.day_comparison import DayComparison

from app.metric_catalog import get_metric
from app.models import SegmentWeatherData, StabilityResult, ThunderLevel, UnifiedWeatherDisplayConfig
from utils.timezone import local_fmt, local_hour

from output.renderers.alert.render import _esc
from output.renderers.fallback_notice import build_fallback_lines, select_fallback_meta
from output.renderers.channel_layout import (
    VISIBILITY_GATE_IDS, render_for_channel, telegram_metric_notice,
)
from output.renderers.day_window import (
    DAY_WINDOW_END_HOUR, DAY_WINDOW_START_HOUR, collect_hiking_window_points,
    hiking_field_min_max, night_temp_min_c, night_wind_chill_min_c,
)
from output.metric_format import THUNDER_LABEL_DE
from output.renderers.compare_outlook_metric_ids import outlook_columns
from output.renderers.email.helpers import _THUNDER_MAP, fmt_val, format_trend_tokens
from output.renderers.email.thunder_branch import resolve_thunder_day_branch
from output.renderers.email.unavailable_hint import (
    any_official_alerts_unavailable,
    render_official_alerts_unavailable_plain,
)
from output.renderers.email.starkregen_hint import render_starkregen_hint_plain
from output.renderers.email.outlook_state_hint import (
    OutlookState as _OutlookState, render_outlook_state_plain,
)
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


# Issue #1474 (F003-Nachbesserung): Inverse der kanonischen Ordinalskala
# (thunder_ordinal() -> {NONE:0, LOW:1, MED:2, HIGH:3}), NUR fuer die
# Ruecklookup-Stelle in _tg_day_footer -- Index == thunder_ordinal(Level).
# gz-thunder-scale: geduldete Inverse der kanonischen Ordinalskala, reine
# Rueck-Lookup-Stelle ohne eigene Stufen-Wahrheit (#1480 Duldungsliste)
_SEV_TO_THUNDER_LEVEL: tuple[ThunderLevel, ...] = (
    ThunderLevel.NONE, ThunderLevel.LOW, ThunderLevel.MED, ThunderLevel.HIGH,
)


def _day_window_thunder_severity(
    segments: list[SegmentWeatherData],
    night_weather: Optional["NormalizedTimeseries"],
    tz: ZoneInfo,
    *,
    start_hour: int = DAY_WINDOW_START_HOUR,
    end_hour: int = DAY_WINDOW_END_HOUR,
) -> int:
    """Schlimmstes Gewitter-Ordinal über das geteilte Tagesfenster (#1498).

    EINE Quelle für JEDE Gewitter-Aussage derselben Bubble: Fußzeile
    (``_tg_day_footer``) und Kurzübersicht (``_overview_line``) lesen beide
    dieses Ergebnis — vorher las die Kurzübersicht nur die Gehzeit-Reihen,
    und ein Gewitter nach der Ankunft (#1317) machte die zwei Zeilen
    widersprüchlich (``⚡ ?`` gegen ``⚡ leicht``, Issue #1498).
    """
    from output.renderers.day_window import build_day_window_points

    worst = 0
    for dp in build_day_window_points(
        segments, night_weather, tz, start_hour=start_hour, end_hour=end_hour,
    ):
        sev = _thunder_severity(dp.thunder_level)
        if sev > worst:
            worst = sev
    return worst


def _tg_day_footer(
    segments: list[SegmentWeatherData],
    enabled_metric_ids: set[str] | list[str],
    *,
    night_weather: Optional["NormalizedTimeseries"] = None,
    tz: ZoneInfo,
    has_gap: bool = False,
    day_window_start_hour: int = DAY_WINDOW_START_HOUR,
    day_window_end_hour: int = DAY_WINDOW_END_HOUR,
) -> Optional[str]:
    """Fußzeile mit Tageswerten (AC-6): ⚡ kein|leicht|mittel|hoch · Sicht gut|… · 0°C-Grenze N m.

    Issue #954: jeder Teil erscheint nur, wenn die zugehörige Metrik in
    ``enabled_metric_ids`` aktiviert ist.

    Gewitter (Issue #1317 / Epic #1319 Scheibe A): schlimmstes Ordinal aus dem
    geteilten Tagesfenster 04-19 (``day_window.build_day_window_points``) —
    dieselbe Quelle und dasselbe Fenster wie SMS/Kurzzusammenfassung/Pillen
    (ADR-0025-Konsistenz), statt nur der Wanderzeit je Segment (#1275).

    ``has_gap`` (Issue #1331/#1334 F002): vom Aufrufer (``render_telegram_
    bubbles``, dem echten Bubble-Einstiegspunkt mit ``night_weather``) bereits
    ermittelte Ziel-Datenluecke — KEINE eigene Berechnung mehr hier.
    """
    from output.renderers.day_window import build_day_window_points

    enabled = set(enabled_metric_ids)
    max_thunder_sev = 0
    min_vis: Optional[int] = None
    rep_freeze: Optional[int] = None

    if "thunder" in enabled:
        max_thunder_sev = _day_window_thunder_severity(
            segments, night_weather, tz,
            start_hour=day_window_start_hour, end_hour=day_window_end_hour,
        )

    for sd in segments:
        agg = sd.aggregated
        if agg.visibility_min_m is not None:
            if min_vis is None or agg.visibility_min_m < min_vis:
                min_vis = agg.visibility_min_m
        if rep_freeze is None and agg.freezing_level_m is not None:
            rep_freeze = agg.freezing_level_m

    parts: list[str] = []

    # Gewitter
    # Issue #1474 (F002/F003, Adversary-Nachbesserung): geteilte Quelle
    # THUNDER_LABEL_DE (metric_format.py) statt einer vierten eigenen
    # Wortliste -- vorher stand hier "MED"/"HIGH" (Englisch), waehrend
    # outlook.py und helpers.py bereits "mittel"/"hoch" (Deutsch) zeigten:
    # derselbe Sprachwechsel in derselben Nachricht, je nach Ausgabeteil.
    # Ordinal->ThunderLevel ueber die kanonische Ordnung (thunder_ordinal()),
    # NONE bewusst mit eigenem Zweig (Datenluecke "?" statt Fehl-Entwarnung,
    # Issue #1331).
    if "thunder" in enabled:
        if max_thunder_sev == 0:
            # Issue #1331: Ziel-Datenluecke darf keine positive Entwarnung
            # "kein" vortaeuschen -- Unsicherheitsmarker statt Fehl-Entwarnung.
            thunder_word = "?" if has_gap else THUNDER_LABEL_DE[ThunderLevel.NONE]
        else:
            thunder_word = THUNDER_LABEL_DE[_SEV_TO_THUNDER_LEVEL[max_thunder_sev]]
        parts.append(f"⚡ {thunder_word}")
        # Issue #1475 S5a: Hagel-Kennzeichen rein deskriptiv NEBEN der
        # Gewitterstufe -- derselbe geteilte Textbaustein wie Mail und
        # `GEWITTER`-Kommando (#1481 DRY, call-time Import). Bei
        # "unbekannt"/"nein" bleibt die Zeile zeichengleich (Spec AC-6).
        from output.metric_format import format_hail_note, hail_priority
        _hail_note = format_hail_note(hail_priority([
            getattr(dp, "hail_flag", None) for dp in build_day_window_points(
                segments, night_weather, tz,
                start_hour=day_window_start_hour, end_hour=day_window_end_hour,
            )
        ]))
        if _hail_note:
            parts.append(_hail_note)

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


def _tg_vortag_line(
    day_comparison: Optional["DayComparison"], report_type: str = "evening",
) -> Optional[str]:
    """F6 (#752): Kompakte Vortag-Zeile für Telegram.

    Sammelt alle abweichenden Metrik-Deltas über alle Segmente, sortiert
    absteigend nach |delta| und nimmt die Top-3. Gibt None zurück wenn keine
    abweichenden Metriken vorliegen (oder day_comparison None/leer).

    ``report_type`` (Issue #1319 Scheibe D): morgens entfaellt der
    "Temp min"-Delta aus der Kandidatenliste (DEC-2 -- N ist morgens gar
    nicht sichtbar, ein Delta darauf wuerde verwirren, Epic-Punkt 6).
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
    if report_type == "morning":
        _LABELS = [entry for entry in _LABELS if entry[0] != "temp_min"]

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
    Gefiltert wird ueber dieselbe Schwelle wie die Trip-SMS: beide Kanaele
    zeigen dieselbe Teilmenge, nur unterschiedlich lang ausformuliert
    (ADR-0025). Ohne Warnung >= Filter -> `None` -> Bubble-Liste bleibt
    bit-identisch zum Stand vor #1318.

    Issue #1461 S3b-2a: die Schwelle ist die per Telegram-Kanal eingestellte
    Trip-Kanal-Schwelle (Startwert 'gering' == Stufe 2) statt des aelteren
    festen `MIN_SMS_LEVEL` (Stufe 3, Ist-Verhalten bis hierhin).

    `trip` ist optional: fehlt es, faellt nur die "gesamte Route"-Verdichtung
    des Umfangs UND die Trip-Kanal-Schwelle (-> Startwert 'gering') weg — die
    Warnung selbst haengt an den Segmenten und darf nie an einem fehlenden
    Kontext-Parameter scheitern.
    """
    import services.alert_urgency as alert_urgency
    from output.renderers.alert.official_alerts import (
        build_official_alert_notices, official_alert_source_label,
        render_official_alert_telegram,
    )

    _threshold = (trip.alert_channel_thresholds or {}).get("telegram") if trip else None
    _min_level = alert_urgency.min_official_level_for_threshold(_threshold or "LOW")

    tagged = [
        (alert, [str(sd.segment.segment_id)])
        for sd in segments
        for alert in (getattr(sd, "official_alerts", None) or [])
        if alert.level >= _min_level
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


def _overview_line(
    metric_id: str, seg_tables: list[list[dict]], fkeys: set[str],
    *, report_type: str = "evening", night_min_c: Optional[float] = None,
    night_wind_chill_min_c: Optional[float] = None,
    hiking_temp_extrema: Optional[tuple[float, float, str]] = None,
    hiking_felt_extrema: Optional[tuple[float, float, str]] = None,
    has_gap: bool = False,
    day_thunder_sev: Optional[int] = None,
) -> str:
    """Eine Kurzübersicht-Zeile ``{Kürzel} {Min}-{Max}@{Peak-Stunde}`` (oder
    Einzelwert/kategorisch).

    Sammelt alle Rohwerte der Metrik ueber alle Segmente/Stunden hinweg und
    formatiert Minimum/Maximum ueber die bestehende ``fmt_val``-Formatierung.
    Bei unterschiedlichem Min/Max wird zusaetzlich die Uhrzeit des Maximums
    angehaengt (``@{Stunde}``, gleiche Konvention wie die Peak-Token in
    ``format_trend_tokens()``/``render_threshold_peak_value()``) — die fuer
    Entscheidungen relevantere Spitze (z.B. Windboeen-Spitze). Fuer die
    Gewitter-Metrik (``thunder``) gilt seit #1498 DIESELBE Quelle wie fuer
    die Fusszeile: ``day_thunder_sev`` traegt das vom Aufrufer ueber
    ``_day_window_thunder_severity()`` (Tagesfenster 04-19 inkl.
    ``night_weather``) ermittelte Schlimmst-Ordinal — vorher las dieser
    Zweig nur die Gehzeit-Reihen (``seg_tables``) und ein Gewitter nach der
    Ankunft (#1317) machte Kurzuebersicht und Fusszeile derselben Bubble
    widerspruechlich (``⚡ ?`` gegen ``⚡ leicht``). Bewusste
    Scheiben-Entscheidung (#1498): NUR Gewitter wechselt auf das
    Tagesfenster; alle uebrigen Metriken behalten die Gehzeit als
    Bezugsrahmen. Fehlt ``day_thunder_sev`` (None, z.B. Direktaufrufe ohne
    Tagesfenster-Kontext), bleibt fail-soft der bisherige Gehzeit-Pfad.
    Andere nicht-numerische Metriken zeigen weiterhin den zuletzt
    beobachteten Wert ohne Uhrzeit.

    ``report_type``/``night_min_c``/``night_wind_chill_min_c``: abends steht
    fuer ``temperature``/``wind_chill`` der echte Nachtwert am Ziel als
    Untergrenze statt des Gehzeit-Minimums aus ``seg_tables`` -- fail-soft auf
    Letzteres, wenn er fehlt. Issue #1410 (F1) hat den frueheren
    Morgen-Sonderzweig (nur Max-Wert, DEC-2 aus night_temp_evening_only.md)
    ersatzlos entfernt: morgens laeuft die Funktion in ihren generischen Pfad
    und zeigt die Spanne ueber die Gehzeit-Stunden -- ohne neue Datenquelle.

    ``hiking_temp_extrema``/``hiking_felt_extrema`` (Issue #1417):
    ``(min, max, Spitzenstunde)`` aus der geteilten Gehzeit-Quelle
    ``day_window.collect_hiking_window_points()``, NUR fuer ``temperature``/
    ``wind_chill``. Sie ersetzen fuer diese zwei Groessen die bisherige
    Ableitung aus ``seg_tables`` -- die ist je Segment beidseitig inklusiv und
    damit ein DRITTER, eigener Rechenweg fuer dieselbe Aussage. Fehlen sie
    (keine verwertbare Zeitreihe), bleibt es fail-soft beim
    ``seg_tables``-Weg. Alle uebrigen Metriken sind unberuehrt.

    ``has_gap`` (Issue #1491 Adversary-Nachbesserung F001): dieselbe vom
    Aufrufer ermittelte Ziel-Datenluecke wie ``_tg_day_footer`` (Zeile
    ~242-248) -- NUR fuer die Gewitter-Metrik relevant. Ist der ueber alle
    ``hits`` schlimmste beobachtete Wert ``NONE`` UND liegt eine Luecke vor,
    darf diese Zeile keine positive Entwarnung "kein" zeigen (das waere eine
    Aussage ueber ein unbeobachtetes Zeitfenster) -- sie zeigt stattdessen
    den Unsicherheitsmarker "?", identisch zur Fusszeile derselben Bubble.
    """
    label = _compact_label(metric_id)
    key = _col_key(metric_id)
    if key is None:
        return f"{label} –"

    hiking = None
    if metric_id == "temperature":
        hiking = hiking_temp_extrema
    elif metric_id == "wind_chill":
        hiking = hiking_felt_extrema

    hits = [r for rows in seg_tables for r in rows if r.get(key) is not None]
    if not hits and hiking is None:
        return f"{label} –"

    try:
        if hiking is not None:
            lo = fmt_val(key, hiking[0], friendly_keys=fkeys)
            hi = fmt_val(key, hiking[1], friendly_keys=fkeys)
            peak_hour = hiking[2]
        else:
            nums = [float(h[key]) for h in hits]
            lo_row = hits[nums.index(min(nums))]
            hi_row = hits[nums.index(max(nums))]
            lo = _cell(metric_id, lo_row, fkeys)
            hi = _cell(metric_id, hi_row, fkeys)
            peak_hour = hi_row.get("time", "")
        if metric_id in ("temperature", "wind_chill") and report_type == "evening":
            _night_val = (night_min_c if metric_id == "temperature"
                          else night_wind_chill_min_c)
            if _night_val is not None:
                lo = f"{_night_val:.1f}"
        if lo == hi:
            value = lo
        else:
            value = f"{lo}-{hi}@{peak_hour}" if peak_hour else f"{lo}-{hi}"
    except (TypeError, ValueError):
        if metric_id == "thunder":
            if day_thunder_sev is not None:
                # #1498: identische Quelle UND identisches Wort wie die
                # Fusszeile (THUNDER_LABEL_DE ueber die kanonische Ordnung,
                # #1474) — die Bubble traegt genau EINE Gewitter-Aussage.
                if day_thunder_sev == 0:
                    value = ("?" if has_gap
                             else THUNDER_LABEL_DE[ThunderLevel.NONE])
                else:
                    value = THUNDER_LABEL_DE[
                        _SEV_TO_THUNDER_LEVEL[day_thunder_sev]
                    ]
            else:
                worst_row = max(
                    hits, key=lambda h: _thunder_severity(h.get(key))
                )
                # Issue #1491 F001: schlimmster BEOBACHTETER Wert ist NONE,
                # aber das Zielfenster ist (teilweise) unbeobachtet --
                # "kein" waere hier eine Fehl-Entwarnung ueber die Luecke
                # hinweg (analog _tg_day_footer).
                if _thunder_severity(worst_row.get(key)) == 0 and has_gap:
                    value = "?"
                else:
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


def _outlook_lines(
    multi_day_trend: list[dict],
    outlook_metrics: Optional[list[dict]] = None,
) -> list[str]:
    """3-Tage-Trend-Zeilen (Issue #623/#640-Rechenlogik, jetzt Ausblick-Bubble).

    ``outlook_metrics`` (#1720 S2): gesetzte Auswahl ersetzt die fuenf festen
    Felder durch die gewaehlten Groessen -- MIT Katalog-Label je Zelle, weil
    die Positionsgarantie der festen Reihenfolge dann entfaellt. ``None``
    (Altbestand) laesst die Zeile byte-identisch.
    """
    lines: list[str] = ["Ausblick"]
    if outlook_metrics is not None:
        columns = outlook_columns(outlook_metrics)
        for stage in multi_day_trend:
            weekday = stage.get("weekday", "")
            cells = stage.get("cells") or []
            values = "  ".join(
                f"{c['label']}: {cells[i] if i < len(cells) else '–'}"
                for i, c in enumerate(columns)
            )
            lines.extend(_wrap(f"{weekday}  {values}", _TG_PROSE_WIDTH))
            note = stage.get("note")
            if note:
                lines.extend(_wrap(f"    ↳ {note}", _TG_PROSE_WIDTH))
        return lines
    for stage in multi_day_trend:
        tok = format_trend_tokens(stage)
        weekday = stage.get("weekday", "")
        pt, wt = tok["precip_token"], tok["wind_token"]
        precip_part = f"R{pt}" if pt != "-" else (tok["precip_str"] if tok["precip_str"] != "–" else "R–")
        wind_part = f"W{wt}" if wt != "-" else tok["wind_str"]
        # Issue #1653: Tag/Nacht getrennt statt 24h-Peak -- Fall B zeigte
        # bisher nur das staerkere Nachtgewitter, das Tagesgewitter kam nie
        # durch.
        # F004: dasselbe Tageswort-Kriterium wie in HTML- und Klartext-Mail --
        # liegt eine Stundenreihe vor, entscheidet ausschliesslich das
        # Tagesfenster. Vorher fiel dieser Zweig auf `thunder_plain` (das auf
        # die Gehzeit geklemmte Aggregat) zurueck und schrieb "⚡HIGH · nachts
        # hoch@0" -- ein Tagesgewitter, das es im Tagesfenster nicht gab.
        dt = tok.get("thunder_day_token", "-")
        nt = tok.get("thunder_night_token", "-")
        # Issue #1671: Zweigwahl aus dem geteilten Helfer (identisch zu
        # compact.py/outlook.py) -- die Formatierung bleibt hier unveraendert.
        branch = resolve_thunder_day_branch(tok, stage)
        if branch == "day":
            thunder_part = f"⚡{dt}"
            # Issue #1680 S5a: die tragende Zutat hinter der Tagesstufe --
            # derselbe Token wie in HTML- und Klartext-Mail (AC-3). Ein
            # Zeilenumbruch auf _TG_PROSE_WIDTH ist hinnehmbar (Wort-Umbruch).
            _origin = tok.get("thunder_day_origin")
            if _origin:
                thunder_part += f" · {_origin}"
        elif branch == "none":
            thunder_part = _THUNDER_MAP["NONE"]["plain"]
        else:
            thunder_part = tok["thunder_plain"]
        if nt != "-":
            thunder_part += f" · nachts {nt}"
        trend_line = f"{weekday}  {tok['temp_str']}  {precip_part}  {wind_part}  {thunder_part}"
        lines.extend(_wrap(trend_line, _TG_PROSE_WIDTH))
        note = stage.get("note")
        if note:
            lines.extend(_wrap(f"    ↳ {note}", _TG_PROSE_WIDTH))
    return lines


def render_telegram_incomplete_hint(missing_count: int) -> str:
    """Hinweis „Briefing unvollstaendig" (Issue #1370). Pure function.

    Bauart nach dem Vorbild des Nicht-abrufbar-Hinweises (#1348,
    ``email/unavailable_hint.py``): kurz, hochkontrastig eingeleitet, in
    Klartext-Deutsch fuer einen Wanderer ohne technisches Vorwissen — kein
    Fachbegriff, keine Statuscodes. Nennt die Anzahl der fehlenden Teile,
    damit der Nutzer weiss, wie viel ihm entgeht.
    """
    count = max(1, int(missing_count))
    teile = "Teil" if count == 1 else "Teile"
    ist_sind = "ist" if count == 1 else "sind"
    return (
        f"⚠️ Briefing unvollständig — {count} {teile} des Briefings "
        f"{ist_sind} nicht angekommen. Bitte fordere das Briefing gleich "
        "noch einmal an."
    )


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
    # #1720 S2: fertig aufgeloeste Ausblick-Spalten (trip_report.py, aus dem
    # UNGEKOLLABIERTEN dc) -- None = Altbestand, [] = bewusst geleerte Auswahl.
    outlook_metrics: Optional[list[dict]] = None,
    outlook_state: Optional["OutlookState"] = None,
    outlook_horizon_days: Optional[int] = None,
    day_comparison: Optional["DayComparison"] = None,
    night_weather: Optional["NormalizedTimeseries"] = None,
    trip: Optional["Trip"] = None,
    has_gap: bool = False,
    day_window_start_hour: int = DAY_WINDOW_START_HOUR,
    day_window_end_hour: int = DAY_WINDOW_END_HOUR,
    starkregen_hint_text: Optional[str] = None,
) -> list[TelegramBubble]:
    """Render die Telegram-Briefing-Bubble-Liste (Issue #1001). Pure function.

    Reihenfolge: Kopf, Kurzuebersicht (alle konfigurierten Metriken,
    ``telegram_kurzform`` wirkungslos — AC-10), je Segment/Ziel eine Tabellen-
    Bubble, optionaler Ausblick (nur wenn ``multi_day_trend`` gesetzt),
    Aktionen (Inline-Keyboard).

    ``has_gap`` (Issue #1331/#1334 F008): vom echten Versandpfad bereits per
    ``notification_service.compute_has_gap()`` (aus
    ``day_window.build_day_window_points()``) ermittelte Ziel-Datenluecke —
    einziger Berechnungspunkt, wird 1:1 durchgereicht (Default False fuer
    Vorschau/Tests ohne echten Versandpfad). Dieser Renderer rechnet die
    Luecke nicht selbst nach.
    """
    fkeys = friendly_keys if friendly_keys is not None else set()
    layout = render_for_channel("telegram", dc, report_type)
    bubbles: list[TelegramBubble] = []
    # Issue #1319 Scheibe D: EINE Berechnung, an die Kurzuebersicht-
    # Temperatur-Zeile durchgereicht (fail-soft None bei fehlendem
    # night_weather/leerem Nachtfenster).
    _night_min_c = night_temp_min_c(night_weather, segments, tz)
    # Issue #1410 (F4): dieselbe Berechnung fuer die gefuehlte Temperatur.
    _night_felt_min_c = night_wind_chill_min_c(night_weather, segments, tz)

    # Issue #1417: EINE Gehzeit-Berechnung, an die Kurzuebersicht-Zeilen fuer
    # Temperatur/gefuehlte Temperatur durchgereicht -- dieselbe Quelle wie
    # Mail-Kachelzeile, SMS und Kurzzusammenfassung. `max_ts` derselben
    # Ableitung liefert die Spitzenstunde (Format wie `_dp_to_row`: `%02d`).
    _hiking_points = collect_hiking_window_points(segments)

    def _extrema(field: str) -> Optional[tuple[float, float, str]]:
        found = hiking_field_min_max(_hiking_points, field)
        if found is None:
            return None
        return found[0], found[1], f"{local_hour(found[2], tz):02d}"

    _hiking_temp = _extrema("t2m_c")
    _hiking_felt = _extrema("wind_chill_c")

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

    # 1a. Amtliche Warnungen nicht abrufbar (#1349 Scheibe 2) — geteilter
    # Baustein, direkt nach dem Kopf, weil sicherheitsrelevant.
    if any_official_alerts_unavailable(segments):
        bubbles.append(TelegramBubble(
            text=_esc(render_official_alerts_unavailable_plain(ascii_safe=False))
        ))

    # Issue #1439: Starkregen-Kurzfristhinweis (planmaessiger Pfad) — direkt
    # nach dem Kopf, weil zeitkritisch.
    if starkregen_hint_text:
        bubbles.append(TelegramBubble(
            text=_esc(render_starkregen_hint_plain(starkregen_hint_text))
        ))

    # 1b. Amtliche Warnungen (#1318 AC-8) — direkt nach dem Kopf, weil
    # sicherheitsrelevant. Ohne Warnung >= MIN_SMS_LEVEL entfaellt sie ganz.
    warn_bubble = _official_alert_bubble(segments, tz, trip)
    if warn_bubble is not None:
        bubbles.append(warn_bubble)

    # 2. Kurzuebersicht-Bubble — ALLE konfigurierten Metriken (AC-3), immer
    # vorhanden, unabhaengig von telegram_kurzform (AC-10).
    # #1498: EINE Tagesfenster-Berechnung fuer die Gewitter-Aussage, an die
    # Kurzuebersicht durchgereicht — dieselbe Quelle (und Segment-Auswahl),
    # aus der die Fusszeile unten liest. Kurzuebersicht und Fusszeile
    # derselben Bubble koennen sich damit strukturell nicht mehr
    # widersprechen (vorher: Gehzeit-Reihen vs. Tagesfenster).
    _day_thunder_sev = _day_window_thunder_severity(
        [sd for sd in segments if not sd.has_error], night_weather, tz,
        start_hour=day_window_start_hour, end_hour=day_window_end_hour,
    )
    overview_lines: list[str] = ["Kurzübersicht"]
    # Issue #1484: die Nacht-Untergrenze der T-Zeile folgt der EIGENEN
    # Groesse "temperature_night". Ohne aktive "temperature" bekommt sie
    # abends eine eigene Zeile mit dem Register-Kuerzel (TN).
    _enabled_ids = set(dc.get_enabled_metric_ids())
    _night_selected = "temperature_night" in _enabled_ids
    # Issue #1660 Scheibe A: dieselbe Abspaltung jetzt auch fuer die
    # gefuehlte Nacht-Untergrenze -- "wind_chill_night" statt unbedingt
    # "wind_chill".
    _felt_night_selected = "wind_chill_night" in _enabled_ids
    for mid in dc.get_enabled_metric_ids():
        if mid == "temperature_night":
            if ("temperature" in _enabled_ids or report_type != "evening"
                    or _night_min_c is None):
                continue
            from app.metric_catalog import get_metric
            overview_lines.extend(_wrap(_esc(
                f"{get_metric('temperature_night').compact_label} "
                f"{_night_min_c:.1f}"), _TG_PROSE_WIDTH))
            continue
        if mid == "wind_chill_night":
            if ("wind_chill" in _enabled_ids or report_type != "evening"
                    or _night_felt_min_c is None):
                continue
            from app.metric_catalog import get_metric
            overview_lines.extend(_wrap(_esc(
                f"{get_metric('wind_chill_night').compact_label} "
                f"{_night_felt_min_c:.1f}"), _TG_PROSE_WIDTH))
            continue
        # Issue #1728 Scheibe 1: die vier Tagesrichtungen sind reine
        # Sichtbarkeits-Gates der Kurzform (SMS-Token K/D/FK/FD) und tragen
        # in der Telegram-Kurzuebersicht keinen eigenen Wert -- die T-/TF-
        # Zeile zeigt die Spanne dort bereits unbedingt. Ohne diese Ausnahme
        # entstuenden vier leere Zeilen ("K –", "D –", "FK –", "FD –").
        # Die beiden Nachtfenster-Skalare sind oben eigens behandelt.
        if mid in VISIBILITY_GATE_IDS:
            continue
        overview_lines.extend(_wrap(_esc(_overview_line(
            mid, seg_tables, fkeys, report_type=report_type,
            night_min_c=_night_min_c if _night_selected else None,
            night_wind_chill_min_c=(
                _night_felt_min_c if _felt_night_selected else None
            ),
            hiking_temp_extrema=_hiking_temp,
            hiking_felt_extrema=_hiking_felt,
            has_gap=has_gap,
            day_thunder_sev=_day_thunder_sev,
        )), _TG_PROSE_WIDTH))
    # Issue #1331/#1334 F008: has_gap kommt als expliziter Parameter vom
    # echten Versandpfad (notification_service.compute_has_gap() aus
    # day_window.build_day_window_points(), einziger Berechnungspunkt) —
    # dieser Renderer rechnet die Luecke nicht selbst nach.
    footer = _tg_day_footer(
        [sd for sd in segments if not sd.has_error], dc.get_enabled_metric_ids(),
        night_weather=night_weather, tz=tz,
        has_gap=has_gap,
        day_window_start_hour=day_window_start_hour,
        day_window_end_hour=day_window_end_hour,
    )
    if footer:
        overview_lines.append("")
        overview_lines.extend(_wrap(_esc(footer), _TG_PROSE_WIDTH))
    # Issue #1492 S2b AC-3: Herkunfts-Vertretung als eigene Zeile(n) UNTER der
    # Tagesfußzeile, in derselben Kurzübersicht-Bubble. Wortlaut aus dem
    # geteilten Modul (R6) — identisch zu Voll- und Kompakt-Mail (AC-10). Die
    # Telegram-KURZFORM erreicht diesen Renderer nicht (sie sendet
    # `report.sms_text`), deshalb bleibt das SMS-Budget unberührt (AC-7).
    # Segmentauswahl GETEILT mit den drei Mail-Renderern
    # (`select_fallback_meta`) — keine kanal-eigene Auswahlregel mehr.
    for _fb_line in build_fallback_lines(select_fallback_meta(segments)):
        overview_lines.extend(_wrap(_esc(_fb_line), _TG_PROSE_WIDTH))
    vortag_line = _tg_vortag_line(day_comparison, report_type)
    if vortag_line:
        overview_lines.append("")
        overview_lines.extend(_wrap(_esc(vortag_line), _TG_PROSE_WIDTH))
    # Issue #1741: Kappungshinweis (>7 primary-Metriken verlieren ihre
    # stuendliche Aufloesung in der Segment-Tabelle) -- ans Ende der
    # Kurzuebersicht, EINMAL fuer den ganzen Trip (dieselbe `layout`-
    # Berechnung wie die Segment-Tabellen oben, nicht je Segment neu).
    notice = telegram_metric_notice(layout.demoted_count, context="route")
    if notice:
        overview_lines.append("")
        overview_lines.extend(_wrap(_esc(notice), _TG_PROSE_WIDTH))
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
    # #1720 S2: eine bewusst geleerte Auswahl ([]) laesst die Bubble GANZ
    # entfallen -- auch den Zustands-Fallback (identisch zu compact.py).
    if outlook_metrics != []:
        if multi_day_trend:
            outlook = [_esc(ln) for ln in
                       _outlook_lines(multi_day_trend, outlook_metrics)]
            bubbles.append(TelegramBubble(text="\n".join(outlook)))
        elif outlook_state is not None and outlook_state != _OutlookState.FOUND:
            # Fix #1486: der vierte, gern vergessene Ausgabeweg — Telegram liess
            # die Bubble bisher kommentarlos weg. Reiner Text, kein HTML-Kasten.
            state_line = _esc(render_outlook_state_plain(
                outlook_state, outlook_horizon_days,
            ))
            bubbles.append(TelegramBubble(text="Ausblick\n" + state_line))

    # 6. Aktionen-Bubble — einzige Bubble mit reply_markup.
    bubbles.append(TelegramBubble(text="Aktionen", reply_markup=ACTIONS_BUBBLE_BUTTONS))

    return bubbles
