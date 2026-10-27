"""Starkregen-Kurzfristhinweis im planmaessigen Trip-Briefing (Issue #1439).

Nutzt den bereits produktiven `RadarNowcastService` (#656) fuer eine kurze
Hinweiszeile im planmaessigen Briefing — Nowcast-Fenster
(`NOWCAST_HORIZON_MIN`, seit #1945 180 Minuten; der Docstring nannte bis
Issue #2051 S1 faelschlich 60), keine Tage-vorher-Vorhersage (s. Spec
"Known Limitations").

Bewusst im Briefing-/E-Mail-Renderer-Bereich (nicht unter `renderers/alert/`):
ein Briefing-Baustein, kein amtliche-Warnung-Renderer — Muster
`unavailable_hint.py` (Issue #1348).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


def format_starkregen_hint(
    intensity_label: str, onset_minutes: int | None, *, tz: ZoneInfo,
    event_end_minutes: int | None = None,
    event_ongoing_beyond_horizon: bool = False,
    already_running: bool = False,
    source_reach_minutes: int | None = None,
) -> str:
    """"Starker Regen ab ca. HH:MM (in ~N Min), letzter Regen gegen HH:MM." —
    identisches Format wie `RadarNowcastService.format_now_text()` fuer den
    Starkregen-Zweig, damit E-Mail und Telegram wortgleich sind (beide Zeiten
    in Trip-Ortszeit).

    Issue #2051 S1: die beiden Ende-Argumente sind additiv und defaultet — ein
    Aufrufer, der sie nicht uebergibt, bekommt byte-identisch den bisherigen
    Text. Der R4-Waechter `event_ongoing_beyond_horizon` unterdrueckt die
    Ende-Angabe seit Spec v1.1 (PO-Entscheid 2026-08-22) NICHT mehr, sondern
    waehlt ihre Form: gesetzt heisst "die Zeitreihe ist ausgegangen, waehrend
    es noch regnete" — die Zahl ist eine belegte Untergrenze
    (`Regen mindestens bis HH:MM`) statt eines bekannten Endes
    (`letzter Regen gegen HH:MM`). Beide Formen entstehen an dieser einen
    Stelle mit genau einer Weiche, damit sie nicht ineinander rutschen
    (AC-20).

    Issue #2051 S3: `source_reach_minutes` ist additiv und defaultet (Muster
    o.). Reichweite und Guete werden HIER selbst aus `onset_minutes`/
    `event_end_minutes` abgeleitet (kein Aufruf der `project.py`-Fassungen
    -- dieser Baustein liegt in einem anderen Modul und bekommt schon heute
    nur Rohwerte, kein `OnsetEvent`). Die Guete-Grenze wird ueber die
    MODUL-Referenz auf `radar_service` gelesen, nie per Import gebunden
    (AC-16, Laufzeit-Drift-Schutz)."""
    import services.radar_service as radar_service_mod
    from utils.timezone import local_dt

    now = datetime.now(timezone.utc)
    if already_running:
        # Issue #2050 S2b: laeuft das Ereignis zur Briefing-Erstellung
        # bereits, ist die Beginn-Angabe eine Falschaussage -- und
        # `onset_minutes` darf hier `None` sein (kein kuenftiger Beginn
        # bestimmbar). Die Ende-Angabe unten bleibt unveraendert.
        satz = f"{intensity_label} läuft bereits"
    else:
        onset_time = now + timedelta(minutes=onset_minutes)
        time_str = local_dt(onset_time, tz).strftime("%H:%M")
        satz = f"{intensity_label} ab ca. {time_str} (in ~{onset_minutes} Min)"
    if event_end_minutes is not None:
        end_str = local_dt(
            now + timedelta(minutes=event_end_minutes), tz,
        ).strftime("%H:%M")
        if event_ongoing_beyond_horizon:
            satz += f", Regen mindestens bis {end_str}"
        else:
            satz += f", letzter Regen gegen {end_str}"
    # Issue #2051 S3 (E5): Reichweite additiv, aber NICHT bei gesetztem
    # R4-Waechter -- die Untergrenzenform traegt die Reichweiten-Aussage
    # bereits implizit.
    if source_reach_minutes is not None and not event_ongoing_beyond_horizon:
        reach_str = local_dt(
            now + timedelta(minutes=source_reach_minutes), tz,
        ).strftime("%H:%M")
        satz += f" · Radar reicht bis {reach_str}"
    # Issue #2051 S3 (E4): Guete-Grenze -- ausgeloest, wenn Beginn ODER Ende
    # jenseits der Grenze liegen. Genannt wird die GRENZZEIT selbst.
    limit = radar_service_mod.LOCATION_SHARPNESS_LIMIT_MIN
    jenseits_guete = (
        (onset_minutes is not None and onset_minutes > limit)
        or (event_end_minutes is not None and event_end_minutes > limit)
    )
    if jenseits_guete:
        guete_str = local_dt(now + timedelta(minutes=limit), tz).strftime("%H:%M")
        satz += f" · Ortsangabe ab {guete_str} unscharf"
    return satz + "."


def render_starkregen_hint_html(hint_text: str) -> str:
    """Hochkontrastiger Danger-Box-Baustein, analog
    `unavailable_hint.render_official_alerts_unavailable_html()`."""
    from output.renderers.email.design_tokens import (
        FONT_UI, G_BOX_DANGER_BG, G_DANGER,
    )

    return (
        f'<div style="background:{G_BOX_DANGER_BG};'
        f'border-left:4px solid {G_DANGER};padding:12px;margin:8px 20px;'
        f'border-radius:4px;font-family:{FONT_UI};">'
        f'<strong style="color:{G_DANGER};font-size:14px;">{hint_text}</strong>'
        f'</div>'
    )


def render_starkregen_hint_plain(hint_text: str) -> str:
    """Einzeilige Text-Fassung, analog
    `unavailable_hint.render_official_alerts_unavailable_plain()`."""
    return f"⚠️ {hint_text}"
