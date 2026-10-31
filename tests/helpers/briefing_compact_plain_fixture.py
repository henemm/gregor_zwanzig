"""Reiche Trip-Briefings ``compact``/``plain`` fuer die Sprachtests (Issue #2665).

SPEC: docs/specs/modules/i18n_p3_briefing_compact_plain_2665.md

Ein Aufruf des ECHTEN ``TripReportFormatter.format_email`` mit allen
Bausteinen, die ``email/compact.py`` und ``email/plain.py`` beschriften --
Metriken-Ueberblick, Stabilitaet, Verlaesslichkeit, Ausblick, Nacht am Ziel,
Hinweise (Warnungen nicht abrufbar, Starkregen, nicht zugestellt),
Ersatzquelle, Antwort-Kommandos, Legenden, Fusszeile. Zwei Varianten:

* ``"ausblick"``: 3-Tages-Ausblick plus Stabilitaets-Satz.
* ``"zustand"``: kein Ausblick, dafuer Ausblick-Zustand (n = 1 Tag),
  Gewitter-Vorschau, ein Segment mit Abruffehler und das Ziel-Segment.

Kein Mock; Daten fest. ``ohne_spaetere_pakete`` schneidet nur, was laut
Spec spaetere Pakete umstellen (Befehlszeilen P10, Amtliche-Warnung-Zeilen P6,
Wochentage/Vorschau-Text aus dem Zeitplaner P9b).
"""
from __future__ import annotations

import dataclasses
import re
from datetime import datetime, timezone

from app.metric_catalog import build_default_display_config
from app.models import OutlookState, StabilityResult, ThunderLevel
from output.renderers.trip_report import TripReportFormatter
from services.alert_log import UndeliveredIncident
from services.report_config_resolver import resolve_report_render_options
from tests.helpers.briefing_html_sprache_fixture import TZ, _nacht, _segment, _trend

UTC = timezone.utc

# Sieben zurueckgehaltene, verschiedene Vorfaelle -> Rest-Zeile "und 2 weitere".
_WITHHELD = [
    ("quiet_hours", "nowcast", (("gust", "max"),)),
    ("cooldown", "forecast_change", ()),
    ("daily_limit", "official_alert", ()),
    ("below_channel_threshold", "nowcast", ()),
    ("double_alert_guard", "forecast_change", (("precipitation", "sum"),)),
    ("event_duplicate", "nowcast", (("wind", "max"),)),
    ("quiet_hours", "official_alert", (("thunder", "max"),)),
]


def vorfaelle() -> list[UndeliveredIncident]:
    """Ein fehlgeschlagener plus sieben zurueckgehaltene Vorfaelle."""
    incs = [UndeliveredIncident(
        at=datetime(2026, 10, 28, 9, 0, tzinfo=UTC), channels=("email", "premium_sms"),
        reasons=("delivery_failed",), metrics=(), hazards=(), trigger="nowcast",
    )]
    for i, (grund, trigger, metriken) in enumerate(_WITHHELD):
        incs.append(UndeliveredIncident(
            at=datetime(2026, 10, 28, 10, i, tzinfo=UTC), channels=("telegram",),
            reasons=(grund,), metrics=metriken, hazards=(), trigger=trigger,
        ))
    return incs


def _segmente(variante: str) -> list:
    seg = _segment()
    seg.official_alerts_unavailable = True
    seg.timeseries.meta.fallback_model = "icon_eu"
    seg.timeseries.meta.fallback_metrics = ["wind_gusts_10m", "lightning_density_per_km2_3h"]
    if variante != "zustand":
        return [seg]
    fehler = dataclasses.replace(_segment(), has_error=True)
    fehler.segment = dataclasses.replace(fehler.segment, segment_id=2)
    ziel = _segment()
    ziel.segment = dataclasses.replace(ziel.segment, segment_id="Ziel")
    return [seg, fehler, ziel]


def render_briefing(lang: str | None = None, *, email_format: str = "compact",
                    variante: str = "ausblick", trip_name: str = "Corsica North"):
    """Rendert das reiche Szenario; ``lang=None`` = Aufruf ohne ``lang``."""
    from output.renderers.email.starkregen_hint import format_starkregen_hint

    kw = {} if lang is None else {"lang": lang}
    hint_kw = {} if lang is None else {"lang": lang}
    label = "Heavy rain" if lang == "en" else "Starker Regen"  # kommt fertig (P5/P9b)
    starkregen = format_starkregen_hint(
        label, 30, tz=TZ, event_end_minutes=90, source_reach_minutes=150, **hint_kw,
    )
    dc = build_default_display_config()
    optionen = dataclasses.replace(
        resolve_report_render_options(None, dc, "evening"), email_format=email_format,
    )
    if variante == "zustand":
        extra = dict(
            multi_day_trend=None, outlook_state=OutlookState.BEYOND_HORIZON,
            outlook_horizon_days=1,
            thunder_forecast={"+1": {"date": "30.10.", "level": ThunderLevel.MED,
                                     "text": "TH:M@14"}},
        )
    else:
        extra = dict(multi_day_trend=_trend(),
                     stability_result=StabilityResult(label="WECHSELHAFT", confidence_pct=60))
    return TripReportFormatter().format_email(
        _segmente(variante), trip_name, "evening", display_config=dc,
        night_weather=_nacht(), stage_name="Vizzavona → Capannelle", tz=TZ,
        stage_stats={"distance_km": 11.0, "ascent_m": 900, "descent_m": 200},
        undelivered=vorfaelle(), starkregen_hint_text=starkregen,
        render_options=optionen, **extra, **kw,
    )


def ohne_spaetere_pakete(text: str) -> str:
    """Entfernt Befehlszeilen (P10), Amtliche-Warnung-Zeilen (P6) und die
    Wochentags-Kuerzel des Zeitplaners (P9b) -- nichts sonst."""
    zeilen = text.split("\n")
    raus: list[str] = []
    in_befehlen = False
    for z in zeilen:
        if z.startswith("── ") and z.endswith(" ──"):
            in_befehlen = True
            raus.append(z)
            continue
        if in_befehlen and z.startswith("  "):
            continue
        in_befehlen = False
        if "Amtliche Warnung:" in z:
            continue
        raus.append(re.sub(r"^(Fr|Sa)\s", "", z))
    return "\n".join(raus)
