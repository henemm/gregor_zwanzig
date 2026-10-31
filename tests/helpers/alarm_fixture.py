"""Deterministische Alarm-Fixture fuer P5 (Issue #2667, Epic #2644).

Sechs Faelle (Abweichung Wind einzeln, Abweichung Mehrfach mit
Beginn-Verschiebung, Regen-Alarm einzeln, Regen-Alarm spaet am Folgetag,
Regen-Alarm Buendel, Nachtrag) aus dem echten Alarm-Renderer, je Kanal
Betreff, E-Mail (HTML + Klartext), Telegram und SMS. Feste Zeit
2026-10-29T06:00+02:00 (Donnerstag), Nutzer ``golden-de``.

Die ``*.de.*``-Golden-Dateien entstanden mit dem Code VOR der Sprach-
umstellung; deshalb ruft der Builder bei ``lang="de"`` die Funktionen OHNE
``lang`` auf (Bestandsaufruf). Erzeugen:
``uv run python -m tests.helpers.alarm_fixture``.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

GOLDEN_DIR = Path(__file__).resolve().parents[1] / "golden" / "abweichungs_radar_alarm"
TRENNER = "\n----- %s -----\n"
KANAELE = ("betreff", "klartext", "telegram", "sms")
FAELLE = (
    "abweichung_wind", "abweichung_mehrfach", "regen_einzel",
    "regen_spaet", "regen_buendel", "nachtrag",
)
TZ = ZoneInfo("Europe/Berlin")
JETZT = datetime(2026, 10, 29, 4, 0, tzinfo=timezone.utc)  # 06:00 Ortszeit (CEST)


def _kw(lang: str | None) -> dict:
    """``lang=None`` = Bestandsaufruf ohne Parameter (Golden vor #2667)."""
    return {} if lang is None else {"lang": lang}


def _referenz(lang):
    from utils.timezone import format_reference_at

    gestern = datetime(2026, 10, 28, 16, 3, tzinfo=timezone.utc)
    return format_reference_at(gestern, TZ, now=JETZT, **_kw(lang))


def _cooldown_trip(minuten: int, lang):
    from services.radar_alert_service import _cooldown_display

    return _cooldown_display(SimpleNamespace(alert_cooldown_minutes=minuten), **_kw(lang))


def _cooldown_vergleich(minuten: int, lang):
    from services.compare_radar_alert import _format_cooldown_display

    return _format_cooldown_display(minuten, **_kw(lang))


def _gust(**extra):
    from output.renderers.alert.model import AlertEvent, AlertHourRow

    basis = dict(
        metric_id="gust", value_from=45.0, value_to=72.0, threshold=20.0, cmp="über",
        occurred_at="15:00", km_from=8.0, km_to=14.0, segment_id="3",
        occurred_day_offset=1, occurred_weekday="Do", stage_number=3,
        hours=(AlertHourRow("14:00", 40.0, 66.0), AlertHourRow("15:00", 45.0, 72.0)),
        hours_range=("13:00", "18:00"), hours_capped=True,
    )
    basis.update(extra)
    return AlertEvent(**basis)


def _abweichung_wind(lang):
    from output.renderers.alert.model import AlertMessage

    return AlertMessage(
        trip_short="GR20 Golden", stand_at="06:00", events=(_gust(),),
        reference_at=_referenz(lang),
    )


def _verschiebung():
    from output.renderers.alert.project import _to_onset_shift_event

    alt = datetime(2026, 10, 29, 13, 0, tzinfo=timezone.utc).timestamp()
    neu = datetime(2026, 10, 29, 10, 30, tzinfo=timezone.utc).timestamp()
    ch = SimpleNamespace(metric="precip_heavy_onset_utc", old_value=alt, new_value=neu,
                         delta=neu - alt)
    return _to_onset_shift_event(ch, tz=TZ, km_from=8.0, km_to=14.0, segment_id="3",
                                 now_utc=JETZT, stage_number=3)


def _abweichung_mehrfach(lang):
    from output.renderers.alert.model import AlertEvent, AlertMessage

    regen = AlertEvent(
        metric_id="precipitation", value_from=4.0, value_to=12.5, threshold=5.0,
        cmp="über", occurred_at="16:00", km_from=8.0, km_to=14.0, segment_id="3",
        occurred_day_offset=-1, occurred_is_past=True, occurred_weekday="Mi",
        remaining_mm=6.5, remaining_until_time="20:00", remaining_until_day_offset=1,
        remaining_until_weekday="Fr", stage_number=3,
    )
    schnee = AlertEvent(
        metric_id="freezing_level", value_from=2400.0, value_to=1850.0, threshold=300.0,
        cmp="unter", occurred_at="09:00", km_from=8.0, km_to=14.0, segment_id="4",
        occurred_day_offset=2, occurred_weekday="Sa", stage_number=4,
    )
    temp = AlertEvent(
        metric_id="temperature", value_from=11.5, value_to=10.2, threshold=3.0,
        cmp="unter", occurred_at="12:00", km_from=8.0, km_to=14.0, segment_id="Ziel",
        occurred_day_offset=-3, occurred_is_past=True, occurred_weekday="Mo",
        stage_number=4,
    )
    gewitter = AlertEvent(
        metric_id="thunder", value_from=1.0, value_to=3.0, threshold=1.0, cmp="über",
        occurred_at="17:00", km_from=8.0, km_to=14.0, segment_id="3", stage_number=3,
        hail_flag=True,
    )
    return AlertMessage(
        trip_short="GR20 Golden", stand_at="06:00",
        events=(_gust(), regen, schnee, temp, gewitter),
        onset_shift_events=(_verschiebung(),),
    )


def _zonen():
    from services.rain_extent import RainZone

    return (RainZone(km_from=2.0, km_to=4.0, onset_minutes=25, event_end_minutes=90),
            RainZone(km_from=9.0, km_to=11.0, onset_minutes=30, event_end_minutes=None))


def _onset(**extra):
    from output.renderers.alert.model import OnsetEvent

    basis = dict(
        onset_minutes=25, onset_time="06:25", km_from=0.0, km_to=12.0, is_convective=False,
        intensity_label="Starker Regen", source_label="Radar (DWD)",
        briefing_context=None, segment_id="Ziel", onset_precip_mm=2.5,
    )
    basis.update(extra)
    return OnsetEvent(**basis)


def _regen_einzel(lang):
    from output.renderers.alert.model import AlertMessage

    e = _onset(
        km_measured=True, event_end_time="00:40", event_end_day_offset=1,
        event_end_weekday="Fr", event_ongoing_beyond_horizon=True,
        source_reach_time="08:55", location_sharpness_limit_time="07:30",
        rain_zones=_zonen(), gap_km=(6.0,), convective_checked=False, stage_number=5,
    )
    return AlertMessage(
        trip_short="GR20 Golden", stand_at="06:00", events=(e,),
        source="Radar (DWD)", cooldown_display=_cooldown_trip(120, lang),
    )


def _regen_spaet(lang):
    from output.renderers.alert.model import AlertMessage

    e = _onset(
        onset_minutes=170, onset_time="15:40", onset_day_offset=1, onset_weekday="Fr",
        is_convective=True, intensity_label="Starker Hagel/Gewitter", segment_id="2",
        event_end_time="17:10", event_end_day_offset=1, event_end_weekday="Fr",
        source_reach_time="09:00", source_reach_day_offset=0,
    )
    return AlertMessage(
        trip_short="GR20 Golden", stand_at="06:00", events=(e,),
        source="Radar (DWD)", cooldown_display=_cooldown_trip(60, lang),
    )


def _regen_buendel(lang):
    from output.renderers.alert.model import AlertMessage
    from output.renderers.alert.project import COMPARE_RADAR_SOURCE

    a = _onset(location_label="Innsbruck", segment_id=None, source_label="INCA",
               intensity_label="Mäßiger Regen", event_end_time="07:40")
    b = _onset(location_label="Lienz", segment_id=None, already_running=True,
               intensity_label="Gewitter", is_convective=True, onset_minutes=0,
               event_end_time="08:10", event_ongoing_beyond_horizon=True)
    return AlertMessage(
        trip_short="Innsbruck, Lienz", stand_at="06:00", events=(a, b),
        source=COMPARE_RADAR_SOURCE, cooldown_display=_cooldown_vergleich(90, lang),
    )


def _nachtrag(lang):
    from output.renderers.alert.model import AlertMessage

    if lang is None:  # Text baut der Orchestrierer (P9b); Bestand: deutsch
        bezug = "Ergänzung zur amtlichen Warnung"
    else:
        from i18n import t

        bezug = t("alarm.nachtrag.amtlich", lang)
    return AlertMessage(
        trip_short="GR20 Golden", stand_at="06:00", events=(_onset(),),
        source="Radar (DWD)", cooldown_display=_cooldown_trip(150, lang),
        addendum_reference=bezug,
    )


_BAUPLAN = {
    "abweichung_wind": _abweichung_wind, "abweichung_mehrfach": _abweichung_mehrfach,
    "regen_einzel": _regen_einzel, "regen_spaet": _regen_spaet,
    "regen_buendel": _regen_buendel, "nachtrag": _nachtrag,
}


def nachricht(fall: str, lang: str | None = None):
    """``AlertMessage`` des Falls; ``lang`` wirkt auf die Dienst-Texte
    (Cooldown, Referenzzeit), die das Modell fertig traegt."""
    return _BAUPLAN[fall](lang)


def render_fall(fall: str, lang: str | None = None) -> dict[str, str]:
    """Alle Kanaele eines Falls; die SMS ohne ``lang`` (PO-Korrektur 2026-10-31)."""
    from output.renderers.alert.render import (
        render_email, render_sms, render_subject, render_telegram,
    )

    msg = nachricht(fall, lang)
    html, plain = render_email(msg, **_kw(lang))
    return {
        "betreff": render_subject(msg, **_kw(lang)), "html": html, "klartext": plain,
        "telegram": render_telegram(msg, **_kw(lang)), "sms": render_sms(msg),
    }


def als_text(kanaele: dict[str, str]) -> str:
    return "".join(TRENNER % k + kanaele[k] for k in KANAELE)


def golden_pfad(fall: str, lang: str, endung: str) -> Path:
    return GOLDEN_DIR / f"{fall}.{lang}.{endung}"


def schreibe(lang: str) -> list[Path]:
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    pfade = []
    for fall in FAELLE:
        k = render_fall(fall, None if lang == "de" else lang)
        for endung, inhalt in (("html", k["html"]), ("txt", als_text(k))):
            p = golden_pfad(fall, lang, endung)
            p.write_text(inhalt, encoding="utf-8")
            pfade.append(p)
    return pfade


if __name__ == "__main__":
    import sys

    for p in schreibe(sys.argv[1] if len(sys.argv) > 1 else "de"):
        print(p)
