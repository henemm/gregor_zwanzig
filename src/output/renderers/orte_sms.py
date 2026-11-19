"""Orte-SMS in der Token-Zeile der Trip-SMS (Issue #3172, ADR-0125).

SPEC: docs/specs/modules/feat_3172_orte_sms_token_zeile.md (Implementation
Details 1-4)

Je Ort entsteht dieselbe Token-Zeile wie in der Trip-SMS (``W21@13``,
``G26@10(31@13)``, ``R-``, ``PR53%@13``, ``TH:-``), gebaut ueber den EINEN
Token-Baukasten ``output.tokens.builder.build_token_line`` -- keine zweite
Formatierung fuer Orte. Dieses Modul bildet nur die Eingaben:

* ``NormalizedForecast`` je Ort aus ``LocationResult.hourly_data`` (Ortszeit),
  Feld fuer Feld wie ``sms_trip._segments_to_normalized_forecast``;
  Tageswerte, die die Orte-Mail als Zahl zeigt, aus ``_metric_value``
  (dieselbe Quelle wie die Mail).
* ``MetricSpec``-Liste aus der SMS-Spalte (Auswahl, Reihenfolge, Roh/Einfach).
* ``?`` statt ``-`` fuer gewaehlte Groessen ohne Wert an diesem Ort;
  Wintersport (``SD``/``NS24+``/``SL``) ohne Wert entfaellt wie im Trip
  (``builder._wintersport``).

Die Kuerzung (Formen von "alle Listenzeilen" bis "keine") nutzt
``tokens.render._drop_last_list_row``; die Verteilung des Platzes auf die Orte
trifft ``comparison._sms_fit_locations``.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Optional

from app.metric_catalog import (
    SMS_FORMAT_MODE_METRIC_IDS, SMS_MULTI_SYMBOLS_BY_METRIC, SMS_SYMBOL_BY_METRIC, get_metric,
)
from app.user import LocationResult
from output.metric_format import thunder_label_value
from output.renderers.alert.official_alerts import official_alerts_to_sms_entries
from output.renderers.email.compare_html import _daily_summary, _metric_value, loc_hail_flag
from output.renderers.sms_trip import (
    _dominant_precip_type_code, _dominant_wind_sector, sms_format_fields,
)
from output.tokens.builder import build_token_line
from output.tokens.dto import DailyForecast, HourlyValue, MetricSpec, NormalizedForecast, Token
from output.tokens.render import _drop_last_list_row, _fuse
from utils.timezone import local_hour, location_tz, resolve_location_tz
import services.alert_urgency as alert_urgency

#: ADR-0125 Nr. 5: Nacht (N/FN) und Folgetag (TH+:) gibt es bei Orten nicht;
#: ``TF`` (Stundenwert der gefuehlten Temperatur) hat keine Orte-Zeile.
_IMMER_AUS = frozenset({"N", "FN", "TH+:", "TF"})

#: Tageswert-Kuerzel -> Renderer-Kennung der Orte-Mail (Wert ueber
#: ``_metric_value``, Paritaet SMS <-> Mail).
_TAGESWERT_RID: dict[str, str] = {
    "L": "temp_min", "D": "temp_max", "FL": "wind_chill_min", "FD": "wind_chill_max",
    "SU": "sunny_hours", "HP": "pressure_avg", "SD": "snow_depth_cm",
    "NS24+": "snow_new_cm", "SL": "snowfall_limit",
}

#: Stundenproben nur ``> 0``, je Stunde der Hoechstwert (Trip: Klasse (a)).
_PROBEN_POSITIV: tuple[tuple[str, str, str], ...] = (
    ("R", "precip_1h_mm", "rain_hourly"), ("PR", "pop_pct", "pop_hourly"),
    ("W", "wind10m_kmh", "wind_hourly"), ("G", "gust_kmh", "gust_hourly"),
    ("HU", "humidity_pct", "humidity_hourly"), ("DP", "dewpoint_c", "dewpoint_hourly"),
    ("CP", "cape_jkg", "cape_hourly"), ("UV", "uv_index", "uv_hourly"),
    ("CT", "cloud_total_pct", "cloud_total_hourly"), ("CL", "cloud_low_pct", "cloud_low_hourly"),
    ("CM", "cloud_mid_pct", "cloud_mid_hourly"), ("CH", "cloud_high_pct", "cloud_high_hourly"),
)
#: Tiefstwert-Proben ohne Filter, je Stunde der Tiefstwert (Trip: Klasse (b)).
_PROBEN_TIEFST: tuple[tuple[str, str, str], ...] = (
    ("VS", "visibility_m", "visibility_hourly"),
    ("FZ", "freezing_level_m", "freezing_level_hourly"),
    ("TF", "wind_chill_c", "wind_chill_hourly"),
)
#: Kuerzel mit Stundenquelle -> Feld (fuer "kein Wert" = alle Stunden ``None``).
_STUNDENFELD: dict[str, str] = {
    **{sym: feld for sym, feld, _ziel in _PROBEN_POSITIV + _PROBEN_TIEFST},
    "TH:": "thunder_level", "WD:": "wind_direction_deg",
}
_LISTEN_KATEGORIEN = ("forecast", "wintersport")
#: Bereichs-Token (``D-5/0``): Hoechstwert-Kuerzel -> Tiefstwert-Kuerzel.
_BEREICH = {"D": "L", "FD": "FL"}


# ---------------------------------------------------------------------------
# MetricSpecs aus der SMS-Spalte
# ---------------------------------------------------------------------------

def _einfach_modus(metric_id: str) -> str:
    """Einfach-Modus des Trips fuer eine Groesse mit SMS-Einfachform."""
    m = get_metric(metric_id)
    if m.default_format_mode != "raw":
        return m.default_format_mode
    return next((x for x in m.format_modes if x != "raw"), "raw")


def orte_metric_specs(
    enabled_metrics: Optional[list[str]], metric_formats: Optional[dict[str, bool]],
) -> list[MetricSpec]:
    """Eine ``MetricSpec`` je Kurzform-Kuerzel des Katalogs (Muster
    ``trip_report``): ``enabled`` = in der SMS-Liste, ``position`` = Listenplatz,
    Roh/Einfach ueber ``sms_format_fields``. ``None`` ("nie eingestellt") =
    ``_NIE_EINGESTELLT_IDS`` in dieser Folge. ``N``/``FN``/``TH+:``/``TF`` sind
    fuer Orte immer aus (ADR-0125 Nr. 5)."""
    from output.renderers.comparison import _NIE_EINGESTELLT_IDS, _RENDERER_TO_CATALOG_METRIC_ID

    rids = list(dict.fromkeys(_NIE_EINGESTELLT_IDS if enabled_metrics is None else enabled_metrics))
    position: dict[str, int] = {}
    modus: dict[str, str] = {}
    for i, rid in enumerate(rids):
        cid = _RENDERER_TO_CATALOG_METRIC_ID.get(rid)
        if cid is None or cid in position:
            continue
        position[cid] = i
        if cid in SMS_FORMAT_MODE_METRIC_IDS:
            modus[cid] = _einfach_modus(cid) if (metric_formats or {}).get(rid) is True else "raw"
    paare = [(cid, sym) for cid, sym in SMS_SYMBOL_BY_METRIC.items()
             if cid not in SMS_MULTI_SYMBOLS_BY_METRIC]
    paare += [(cid, sym) for cid, syms in SMS_MULTI_SYMBOLS_BY_METRIC.items() for sym in syms]
    return [
        MetricSpec(symbol=sym, enabled=cid in position and sym not in _IMMER_AUS,
                   position=position.get(cid), **sms_format_fields(cid, modus))
        for cid, sym in paare
    ]


# ---------------------------------------------------------------------------
# Forecast je Ort
# ---------------------------------------------------------------------------

def _je_stunde(paare, *, nur_positiv: bool, tiefst: bool) -> tuple[HourlyValue, ...]:
    """Stundenproben, je Ortszeit-Stunde der Hoechst- bzw. Tiefstwert."""
    best: dict[int, float] = {}
    for stunde, wert in paare:
        if wert is None or (nur_positiv and wert <= 0):
            continue
        wert = float(wert)
        if stunde not in best or (wert < best[stunde] if tiefst else wert > best[stunde]):
            best[stunde] = wert
    return tuple(HourlyValue(h, best[h]) for h in sorted(best))


def _extrem_stunden(punkte: list, feld: str) -> tuple[Optional[int], Optional[int]]:
    """Ortszeit-Stunde von Tiefst- und Hoechstwert eines Feldes (fuer ``@h``)."""
    werte = [(h, getattr(p, feld)) for h, p in punkte if getattr(p, feld, None) is not None]
    if not werte:
        return None, None
    return min(werte, key=lambda hv: hv[1])[0], max(werte, key=lambda hv: hv[1])[0]


def _stundenreihen(punkte: list) -> dict:
    """Stundenfelder der ``DailyForecast`` (Trip: ``_segments_to_normalized_forecast``)."""
    reihen = {ziel: _je_stunde([(h, getattr(p, feld, None)) for h, p in punkte],
                               nur_positiv=True, tiefst=False)
              for _sym, feld, ziel in _PROBEN_POSITIV}
    reihen.update({ziel: _je_stunde([(h, getattr(p, feld, None)) for h, p in punkte],
                                    nur_positiv=False, tiefst=True)
                   for _sym, feld, ziel in _PROBEN_TIEFST})
    reihen["thunder_hourly"] = _je_stunde(
        [(h, float(thunder_label_value(p.thunder_level))) for h, p in punkte
         if p.thunder_level is not None], nur_positiv=True, tiefst=False)
    reihen["wind_direction_sector"] = _dominant_wind_sector([
        (h, float(p.wind_direction_deg), float(p.wind10m_kmh or 0.0))
        for h, p in punkte if p.wind_direction_deg is not None])
    reihen["precip_type_dominant"] = _dominant_precip_type_code(
        [p.precip_type for _h, p in punkte if p.precip_type is not None])
    reihen["pop_all_missing"] = bool(punkte) and all(p.pop_pct is None for _h, p in punkte)
    return reihen


def _tageswerte(werte: dict, punkte: list) -> dict:
    """Tageswerte der Mail (``_metric_value``) und die Stunde ihres Extrems."""
    t_tief, t_hoch = _extrem_stunden(punkte, "t2m_c")
    f_tief, f_hoch = _extrem_stunden(punkte, "wind_chill_c")
    return dict(
        temp_min_c=werte["L"], temp_max_c=werte["D"],
        wind_chill_min_c=werte["FL"], wind_chill_max_c=werte["FD"],
        temp_min_hour=t_tief, temp_max_hour=t_hoch,
        wind_chill_min_hour=f_tief, wind_chill_max_hour=f_hoch,
        sunshine_hours=werte["SU"], pressure_avg_hpa=werte["HP"],
        snow_depth_cm=werte["SD"], snow_new_24h_cm=werte["NS24+"],
        snowfall_limit_m=werte["SL"],
    )


def orte_forecast(loc: LocationResult, werte: dict, summary) -> NormalizedForecast:
    """``NormalizedForecast(days=(heute,))`` eines Ortes. ``official_alerts_
    unavailable`` bleibt aus: Orte fuehren ``X?`` einmal am Nachrichtenende."""
    tz = location_tz(loc.location)
    punkte = [(local_hour(p.ts, tz), p) for p in loc.hourly_data]
    heute = DailyForecast(**_tageswerte(werte, punkte), **_stundenreihen(punkte),
                          hail_flag=loc_hail_flag(loc, summary))
    return NormalizedForecast(days=(heute,), official_alerts=orte_warn_eintraege(loc))


def orte_warn_eintraege(loc: LocationResult) -> tuple:
    """Amtliche Warnungen des Ortes ab der Startschwelle "gering" (#1461 S3b-2b)."""
    if loc.error is not None:
        return ()
    return official_alerts_to_sms_entries(
        loc.official_alerts, resolve_location_tz(loc.location),
        min_level=alert_urgency.min_official_level_for_threshold("LOW"),
    )


# ---------------------------------------------------------------------------
# "?" fuer fehlende Werte
# ---------------------------------------------------------------------------

def _fehlende_kuerzel(loc: LocationResult, werte: dict) -> set[str]:
    """Kuerzel, fuer die an diesem Ort kein Wert vorliegt: Tageswert ``None``
    bzw. alle Stundenwerte ``None`` (auch: keine Stundenwerte). ``PT:`` nur
    ohne Stundenwerte -- eine fehlende Niederschlagsart heisst "trocken"."""
    fehlend = {sym for sym, wert in werte.items() if wert is None}
    fehlend |= {sym for sym, feld in _STUNDENFELD.items()
                if all(getattr(p, feld, None) is None for p in loc.hourly_data)}
    if not loc.hourly_data:
        fehlend.add("PT:")
    return fehlend


def _fragezeichen(token: Token, fehlend: set[str]) -> Token:
    if token.symbol in _BEREICH and "/" in token.value:
        tief, hoch = token.value.split("/", 1)
        tief = "?" if tief == "-" and _BEREICH[token.symbol] in fehlend else tief
        hoch = "?" if hoch == "-" and token.symbol in fehlend else hoch
        return replace(token, value=f"{tief}/{hoch}")
    if token.value == "-" and token.symbol in fehlend:
        return replace(token, value="?")
    return token


def _mit_fragezeichen(tokens: list[Token], fehlend: set[str]) -> list[Token]:
    """``-`` -> ``?`` fuer gewaehlte Groessen ohne Wert. Wintersport-Werte ohne
    Wert (``SD``/``NS24+``/``SL``) laesst der Baukasten ganz weg -- wie im Trip
    bleiben sie weg, auch bei "nie eingestellt" (kein ``SD?``)."""
    return [_fragezeichen(t, fehlend) if t.category in _LISTEN_KATEGORIEN else t for t in tokens]


# ---------------------------------------------------------------------------
# Formen je Ort
# ---------------------------------------------------------------------------

def orte_token_reihen(
    loc: LocationResult, enabled_metrics: Optional[list[str]],
    metric_formats: Optional[dict[str, bool]], *, ampel: dict,
) -> list[list[Token]]:
    """Token des Ortes je Form, Index d = d Listenzeilen vom Listenende
    entfernt (``_drop_last_list_row``; letzte Form: keine Listenzeile, nur
    Warnblock). Fehler-Ort: ``[[]]``."""
    if loc.error is not None:
        return [[]]
    specs = orte_metric_specs(enabled_metrics, metric_formats)
    summary = _daily_summary(loc) if loc.hourly_data else None
    werte = {sym: _metric_value(loc, rid, summary) for sym, rid in _TAGESWERT_RID.items()}
    zeile = build_token_line(orte_forecast(loc, werte, summary), specs, report_type="morning",
                             stage_name="Ort", ampel=ampel)
    tokens = _mit_fragezeichen(list(zeile.tokens), _fehlende_kuerzel(loc, werte))
    reihen = [list(tokens)]
    while _drop_last_list_row(tokens):
        reihen.append(list(tokens))
    return reihen


def orte_kennung(nummer: int) -> str:
    """Ortsnummer der Orte-SMS (PO 2026-11-19, #3172): ``O{n}`` wie das
    Etappen-Praefix ``E{n}`` der Trip-SMS; ``n`` = 1-basierte Stelle in der
    Reihenfolge des Abos, ueber ALLE Orte gezaehlt (auch Orte ohne Daten).
    Ortsnamen stehen nie in der SMS."""
    return f"O{nummer}"


def orte_ortsteil(kennung: str, tokens: list[Token]) -> str:
    """Ortsteil ``"O{n} {Token}"`` -- ohne Doppelpunkt (PO 2026-11-19: jedes
    Zeichen zaehlt); Warnblock ``!`` wie im Trip (``render._fuse``). Ohne
    Token (leere SMS-Liste) steht nur ``O{n}``."""
    return " ".join([kennung, *_fuse(tokens)])


def orte_token_formen(
    loc: LocationResult, enabled_metrics: Optional[list[str]],
    metric_formats: Optional[dict[str, bool]], *, nummer: int, ampel: dict,
) -> list[str]:
    """Formen des Ortsteils ``O{n} {Token}`` zu ``orte_token_reihen``.
    Ort ohne Daten: ``O{n} n/a``."""
    kennung = orte_kennung(nummer)
    if loc.error is not None:
        return [f"{kennung} n/a"]
    reihen = orte_token_reihen(loc, enabled_metrics, metric_formats, ampel=ampel)
    return [orte_ortsteil(kennung, tokens) for tokens in reihen]


def orte_kuerzel_je_metrik() -> dict[str, str]:
    """Kurzform-Kuerzel -> Katalog-ID, wie die Orte-SMS sie sendet (ohne die
    fuer Orte abgeschalteten ``N``/``FN``/``TH+:``/``TF``)."""
    out = {sym: cid for cid, sym in SMS_SYMBOL_BY_METRIC.items()
           if cid not in SMS_MULTI_SYMBOLS_BY_METRIC}
    out.update({sym: cid for cid, syms in SMS_MULTI_SYMBOLS_BY_METRIC.items() for sym in syms})
    return {sym: cid for sym, cid in out.items() if sym not in _IMMER_AUS}


def token_metriken(token: Token) -> set[str]:
    """Katalog-IDs, die ein Listen-Token zeigt; der Bereich ``D-5/0`` zeigt
    Tiefst- UND Hoechstwert."""
    je_kuerzel = orte_kuerzel_je_metrik()
    out = {je_kuerzel[token.symbol]} if token.symbol in je_kuerzel else set()
    if token.symbol in _BEREICH and "/" in token.value:
        out.add(je_kuerzel[_BEREICH[token.symbol]])
    return out
