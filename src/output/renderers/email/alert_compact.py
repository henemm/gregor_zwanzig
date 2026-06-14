"""Knapper Abweichungs-Alert-Renderer (Issue #816, Epic #813 Slice 1).

Rendert die mobil-first Alert-Mail/Telegram-Nachricht: NUR Kopfzeile,
Vorher→Jetzt-Zeilen (sortiert nach Stärke der Abweichung) und eine
Orientierungs-Fußzeile. KEINE Stundentabelle, KEIN Ausblick, KEINE
Gewitter-Vorschau, KEINE Nacht-Sektion, KEIN Vortags-Vergleich, KEINE
Etappen-Statistik (PO-bestätigt 2026-06-14).

SPEC: docs/specs/modules/issue_816_alert_deviation_core.md Abschnitt D
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.metric_catalog import format_metric_value, get_label_for_field
from output.renderers.email.helpers import build_segment_label
from utils.timezone import local_fmt

_HEADER = "Wetter ändert sich seit dem Briefing"


def _strength(change) -> float:
    """Stärke der Abweichung = |delta| / threshold (größer = wichtiger)."""
    threshold = abs(change.threshold) or 1.0
    return abs(change.delta) / threshold


def _line(change, segments, *, tz) -> str:
    """Eine Vorher→Jetzt-Zeile: 'Metrik  Vorher → Jetzt Einheit  (Segment-Label)'."""
    label_info = get_label_for_field(change.metric)
    if label_info:
        name, _agg, unit = label_info
        old_fmt = format_metric_value(unit, change.old_value)
        new_fmt = format_metric_value(unit, change.new_value)
    else:
        name = change.metric
        old_fmt = f"{change.old_value:.1f}"
        new_fmt = f"{change.new_value:.1f}"
    seg_label = build_segment_label(change, segments, tz=tz)
    return f"{name}  {old_fmt} → {new_fmt}  ({seg_label})"


def render_deviation_alert(
    changes,
    segments,
    trip_name: str,
    *,
    tz: ZoneInfo = ZoneInfo("UTC"),
    stage_label: str | None = None,
    sent_at: datetime | None = None,
) -> tuple[str, str]:
    """Render die knappe Abweichungs-Alert-Mail.

    Returns (html, plain). Zeilen sind nach Stärke (|delta|/threshold)
    absteigend sortiert.
    """
    ordered = sorted(changes, key=_strength, reverse=True)
    now = sent_at or datetime.now(timezone.utc)
    stamp = local_fmt(now, tz)
    footer = f"Stand: heute {stamp} · verglichen mit dem letzten Briefing"

    plain_lines = [_HEADER, ""]
    for c in ordered:
        plain_lines.append(_line(c, segments, tz=tz))
    plain_lines.extend(["", footer])
    plain = "\n".join(plain_lines)

    html_rows = "".join(
        f"<tr><td style=\"padding:4px 0;\">{_html_escape(_line(c, segments, tz=tz))}</td></tr>"
        for c in ordered
    )
    html = (
        "<html><body style=\"font-family:sans-serif;\">"
        f"<h2 style=\"margin:0 0 12px;\">{_html_escape(_HEADER)}</h2>"
        f"<table style=\"border-collapse:collapse;\">{html_rows}</table>"
        f"<p style=\"color:#555;margin-top:16px;\">{_html_escape(footer)}</p>"
        "</body></html>"
    )
    return html, plain


def _html_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
