"""Geteilter Baustein "Antwort-Kommandos" fuer Trip- UND Ortsvergleichs-Mail.

SPEC: docs/specs/modules/feat_2420_befehle_anzeigen.md AC-8, AC-10..12.

EIN Baustein, Parameter ``kind`` ("route" | "vergleich"): die Zeilen kommen
aus ``command_rows(kind)`` (Einzelquelle ``_COMMAND_SPECS``). Kein Nachbau in
Trip- oder Compare-Renderer (Pendant-Regel).
"""
from __future__ import annotations

from i18n import Lang, t
from output.renderers.email.design_tokens import FONT_DATA, G_HEADER_BG
from services.trip_command_processor import command_rows


def render_commands_plain(kind: str = "route", *, lang: Lang = "de") -> str:
    """Klartext-Block: Kopfzeile plus eine Zeile je Befehl.

    ``lang`` (Issue #2665) betrifft Kopfzeile, Eyebrow und Hinweis; die
    Befehlszeilen aus ``command_rows`` stellt P10 (#2673) um."""
    zeilen = [f"── {t('mail.befehle.titel', lang)} ──"]
    for label, beschreibung in command_rows(kind):
        zeilen.append(f"  {label:<20} – {beschreibung}")
    return "\n".join(zeilen)


def render_commands_html(kind: str = "route", *, lang: Lang = "de") -> str:
    """HTML-Block (JSX EmailPreview L185-200): Befehlsgrid + Hinweis."""
    cmds = command_rows(kind)
    rows = []
    for i in range(0, len(cmds), 3):
        tds = ""
        for cmd, desc in cmds[i:i + 3]:
            tds += (
                f'<td style="padding:6px 16px 6px 0;vertical-align:top;">'
                f'<span style="font-family:{FONT_DATA};font-size:11px;font-weight:700;'
                f'color:#1d1c1a;min-width:70px;display:inline-block;">{cmd}</span>'
                f'<span style="font-family:{FONT_DATA};font-size:10px;color:#9a978d;'
                f'display:block;margin-top:1px;">{desc}</span>'
                f'</td>'
            )
        rows.append(f'<tr>{tds}</tr>')
    grid = (
        '<table cellpadding="0" cellspacing="0" style="border-collapse:collapse;margin-top:10px;">'
        + "".join(rows)
        + "</table>"
    )
    hint = (
        f'<div style="font-family:{FONT_DATA};font-size:10px;color:#b8b4a8;margin-top:10px;">'
        f'{t("mail.befehle.hinweis", lang)}</div>'
    )
    eyebrow = (
        f'<span style="font-family:{FONT_DATA};font-size:10px;'
        f'letter-spacing:0.12em;color:#9a978d;font-weight:600;'
        f'text-transform:uppercase;">{t("mail.befehle.titel", lang)}</span>'
    )
    return (
        f'<div style="background:{G_HEADER_BG};border-bottom:1px solid #e6e1d3;'
        f'padding:16px 28px 18px;">' + eyebrow + grid + hint + "</div>"
    )
