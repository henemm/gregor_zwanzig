"""Abweichungs-Alarm nach Stufenwechsel der Profil-Ampel (Issue #2793 S2b).

Spec ``docs/specs/modules/feat_2793_s2_alarm_stufenwechsel.md`` §1-§3,
ADR-0106 P4 (D1-D4). EIN Kern fuer Trip und Orts-Vergleich (ADR-0021): die
``DeviationAlertEngine`` ruft ``ampel_changes`` mit den Punkten beider Seiten.

Je Metrik entscheidet die Farbe (Abo-Ampel, ``ampel_stufe``/``thunder_color``)
von Bezugs- und Neuwert gegen ``ampel.metrics.<id>.alarm_ab``:
Verschaerfung (Farbe steigt auf/ueber „Alarm ab"), Sprung (gleiche Farbe im
Alarmbereich, Aenderung zum Schlechteren >= Sprung-Schwelle = Spalte
„standard" der ``_PRESET_TABLE``, D1), Entwarnung (Farbe faellt unter
„Alarm ab", D2). Dringlichkeit aus der Farbe (D3).

Bezugswert ist der zuletzt gemeldete Wert dieses ``metric:segment``
(Melde-Gedaechtnis, wird beim Briefing-Versand geleert), sonst der Anker.
Damit meldet derselbe Stufenwechsel nie zweimal (§2 Dedup), und ein weiterer
Wechsel nennt die zuletzt gemeldete Farbe als „von" (AC-20).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from app.models import AlertMetric, ChangeSeverity, ThunderLevel, WeatherChange

RANG = {"green": 0, "yellow": 1, "orange": 2, "red": 3}
_ALARM_AB_RANG = {"yellow": 1, "orange": 2, "red": 3}  # "never" -> kein Rang
_FARBE_ZU_SCHWERE = {
    "yellow": ChangeSeverity.MINOR,
    "orange": ChangeSeverity.MODERATE,
    "red": ChangeSeverity.MAJOR,
}
_SEITEN_SCHLUESSEL = {
    "oben": ("yellow", "orange", "red"),
    "unten": ("yellow_lt", "orange_lt", "red_lt"),
}


def _sprung(metric: AlertMetric) -> float:
    """Sprung-Schwelle = Spalte „standard" der ``_PRESET_TABLE`` (D1)."""
    from services.alert_preset import _COL, _PRESET_TABLE

    row = next(r for r in _PRESET_TABLE if r[0] == metric)
    return float(row[_COL["standard"]])


@dataclass(frozen=True)
class AmpelFeld:
    """Eine alarmfaehige Ampel-Groesse (§1-Tabelle)."""

    catalog_id: str
    field: str
    seite: str                      # "oben" | "unten" | "stufe"
    aktivierung: Optional[AlertMetric]
    sprung: Optional[float]


AMPEL_FELDER: tuple[AmpelFeld, ...] = (
    AmpelFeld("temperature", "temp_max_c", "oben", AlertMetric.TEMPERATURE_MAX,
              _sprung(AlertMetric.TEMPERATURE_MAX)),
    AmpelFeld("temperature", "temp_min_c", "unten", AlertMetric.TEMPERATURE_MIN,
              _sprung(AlertMetric.TEMPERATURE_MIN)),
    AmpelFeld("wind", "wind_max_kmh", "oben", AlertMetric.WIND_CHANGE,
              _sprung(AlertMetric.WIND_CHANGE)),
    AmpelFeld("gust", "gust_max_kmh", "oben", AlertMetric.WIND_GUST,
              _sprung(AlertMetric.WIND_GUST)),
    AmpelFeld("precipitation", "precip_sum_mm", "oben", AlertMetric.PRECIPITATION_SUM,
              _sprung(AlertMetric.PRECIPITATION_SUM)),
    AmpelFeld("fresh_snow", "snow_new_sum_cm", "oben", AlertMetric.FRESH_SNOW,
              _sprung(AlertMetric.FRESH_SNOW)),
    AmpelFeld("visibility", "visibility_min_m", "unten", AlertMetric.VISIBILITY, None),
    AmpelFeld("uv_index", "uv_index_max", "oben", None, None),
    AmpelFeld("thunder", "thunder_level_max", "stufe", AlertMetric.THUNDER_LEVEL, None),
)


def _aktiv(feld: AmpelFeld, display_config, ergaenzen: bool, abgewaehlt: set) -> bool:
    """Aktivierung wie heute (``is_alert_metric_active``). Ohne Wetter-Reiter
    (``display_config is None``) gilt die Vergleichs-Ergaenzung (#1971)."""
    from services.weather_change_detection import is_alert_metric_active

    if display_config is None:
        return ergaenzen
    if feld.field in abgewaehlt:
        return False
    if feld.aktivierung is None:
        return not display_config.metrics or display_config.is_metric_enabled(feld.catalog_id)
    return is_alert_metric_active(feld.aktivierung, display_config)


def _ordinal(wert) -> float:
    from app.thunder_scale import thunder_ordinal

    return float(thunder_ordinal(wert)) if isinstance(wert, Enum) else float(wert)


def _farbe(ampel: dict, feld: AmpelFeld, wert) -> Optional[str]:
    """Farbe eines Werts auf der Seite des Felds (beidseitige Metriken bekommen
    die Farbe ihrer Seite); ``None`` = keine Aussage."""
    from app.ampel import schwellen_aus_ampel, thunder_color
    from output.metric_format import _THUNDER_JE_ORDINAL, severity_from_thresholds

    if wert is None:
        return None
    if feld.seite == "stufe":
        stufe = wert if isinstance(wert, Enum) else _THUNDER_JE_ORDINAL.get(int(round(wert)))
        return thunder_color(ThunderLevel(stufe), ampel) if stufe is not None else None
    schwellen = schwellen_aus_ampel(ampel, feld.catalog_id)
    seite = {k: v for k, v in schwellen.items() if k in _SEITEN_SCHLUESSEL[feld.seite]}
    return severity_from_thresholds(seite, float(wert))


def _art(feld: AmpelFeld, ab: int, ref: tuple, neu: tuple) -> Optional[str]:
    (wert_ref, rang_ref), (wert_neu, rang_neu) = ref, neu
    if rang_neu > rang_ref and rang_neu >= ab:
        return "verschaerfung"
    if rang_ref >= ab and rang_neu < ab:
        return "entwarnung"
    if rang_neu == rang_ref >= ab and feld.sprung is not None:
        schlechter = wert_neu - wert_ref if feld.seite == "oben" else wert_ref - wert_neu
        if schlechter >= feld.sprung:
            return "sprung"
    return None


def _bezug(feld: AmpelFeld, alter_wert, segment_id: str, alert_state: dict):
    """Zuletzt gemeldeter Wert dieses Felds/Abschnitts, sonst der Anker."""
    zuletzt = (alert_state.get(f"{feld.field}:{segment_id}") or {}).get("last_reported_value")
    return zuletzt if zuletzt is not None else alter_wert


def _ereignis(feld, ampel, ab, alter_wert, neuer_wert, segment_id) -> Optional[WeatherChange]:
    farbe_ref, farbe_neu = _farbe(ampel, feld, alter_wert), _farbe(ampel, feld, neuer_wert)
    if farbe_ref is None or farbe_neu is None:
        return None
    ref, neu = _ordinal(alter_wert), _ordinal(neuer_wert)
    art = _art(feld, ab, (ref, RANG[farbe_ref]), (neu, RANG[farbe_neu]))
    if art is None:
        return None
    schwere_farbe = farbe_ref if art == "entwarnung" else farbe_neu
    return WeatherChange(
        metric=feld.field, old_value=ref, new_value=neu, delta=neu - ref,
        threshold=feld.sprung or 0.0, severity=_FARBE_ZU_SCHWERE[schwere_farbe],
        direction="increase" if neu >= ref else "decrease", segment_id=segment_id,
        stufe_von=farbe_ref, stufe_bis=farbe_neu, art=art,
    )


def ampel_changes(cached, fresh, config, alert_state: dict, ampel: dict) -> list[WeatherChange]:
    """Ampel-Ereignisse aller Punkte (Trip-Segmente bzw. Vergleichs-Orte)."""
    from services.alert_preset import explicitly_disabled_fields
    from services.weather_change_detection import _peak_occurred_at

    dc = config.display_config
    abgewaehlt = explicitly_disabled_fields(dc)
    felder = []
    for feld in AMPEL_FELDER:
        ab = _ALARM_AB_RANG.get((ampel["metrics"].get(feld.catalog_id) or {}).get("alarm_ab"))
        if ab is not None and _aktiv(feld, dc, config.supplement_missing_levels, abgewaehlt):
            felder.append((feld, ab))
    fresh_by_id = {p.id: p for p in fresh}
    changes: list[WeatherChange] = []
    for alt in cached:
        neu = fresh_by_id.get(alt.id)
        if neu is None:
            continue
        sid = str(alt.id)
        for feld, ab in felder:
            neuer_wert = getattr(neu.aggregated, feld.field, None)
            alter_wert = getattr(alt.aggregated, feld.field, None)
            if neuer_wert is None or alter_wert is None:
                continue
            ch = _ereignis(feld, ampel, ab, _bezug(feld, alter_wert, sid, alert_state),
                           neuer_wert, sid)
            if ch is not None:
                ch.occurred_at = _peak_occurred_at(feld.field, _occurred_shim(neu))
                changes.append(ch)
    return changes


def _occurred_shim(point):
    from services.deviation_alert_engine import _PointShim

    return _PointShim(point)
