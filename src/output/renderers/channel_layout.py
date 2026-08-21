"""Kanal-bewusste Layout-Berechnung (Issue #360, Teil 1 von Epic #331).

SPEC: docs/specs/modules/issue_360_signal_channel_renderer.md §2–§4.

Pure functions: aus einer ``UnifiedWeatherDisplayConfig`` und einem Kanal
wird berechnet, welche Metriken als eigene Tabellen-Spalte erscheinen und
wie viele wegen der Kanal-Grenze verdraengt werden (``demoted_count``).
Keine I/O, keine Mocks.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - nur fuer Typannotation
    from app.models import MetricConfig, UnifiedWeatherDisplayConfig


# Kanal-Constraints. ``max_table_cols`` zaehlt die GESAMT-Spalten inkl. der
# impliziten Zeit-Spalte (Telegram 8 = Zeit + 7 Metriken).
#
# Issue #1362 S5b, Adversary-Fund Runde 4/5 (PO-Entscheidung 2026-07-30): SMS
# ``max_chars`` stand bislang bei 140 -- das ist die BYTE-Grenze einer
# SMS-PDU (3GPP TS 23.038/23.040), KEINE Zeichengrenze. Beides faellt nur bei
# 8-Bit-Kodierung zusammen; GSM-7 packt 7 Bit je Zeichen in ein Byte.
#
# Herleitung des verkettungssicheren Werts (gilt sobald 2+ SMS-Teile noetig
# werden, nicht nur beim Einzel-Teil):
#   SMS_PDU_PAYLOAD_BYTES   = 140  (3GPP TS 23.038/23.040)
#   CONCAT_UDH_HEADER_BYTES = 6    (User-Data-Header je Teil bei Verkettung)
#   GSM7_BITS_PER_CHAR      = 7
#   nutzbare Zeichen/Teil   = floor((140 - 6) * 8 / 7) = 153
#
# Gilt NUR unter der Bedingung, dass der Text GSM-7-kodierbar bleibt (sonst
# UCS-2: 140/2=70 Einzel-/(140-6)/2=67 Teil-Zeichen, ein Vielfaches
# schlechter). Der Compare-SMS-Zellbau (comparison.py:_sms_metric_cell/
# _sms_gsm7_safe) und sein Waechter (tests/tdd/test_compare_sms_gsm7_
# charset.py) garantieren GSM-7-Reinheit fuer den GESAMTEN renderer-erzeugten
# Text; Ortsnamen (Freitext-Nutzerdaten, SavedLocation.name) bleiben eine
# bewusst nicht geschlossene Ausnahme (s. dortiger Moduldocstring). 153 statt
# der optimistischeren Einzel-SMS-Grenze (160) traegt genau diesem Restrisiko
# Rechnung: bleibt korrekt, selbst wenn eine Nachricht durch einen
# untypischen Ortsnamen doch verkettet wird. Test gegen diese Herleitung
# (nicht gegen sich selbst): test_compare_sms_gsm7_charset.py::
# test_sms_char_budget_matches_gsm7_concatenated_derivation.
CHANNEL_LIMITS = {
    "email":    {"max_table_cols": None, "max_chars": None},   # unbegrenzt
    "telegram": {"max_table_cols": 8,    "max_chars": 4096},
    "sms":      {"max_table_cols": 0,    "max_chars": 153},
    # Issue #1676 S2a (ADR-0049): Vorsorge, kein Bestandteil des
    # Briefing-Pfads — der uebergibt `max_length=160` fest (trip_report.py).
    # Ohne diesen Eintrag fiele ein kuenftiger Aufrufer (S3, Vergleichspfad)
    # unten still auf die TELEGRAM-Grenzen zurueck: 4096 Zeichen und eine
    # Tabelle in einer Satelliten-SMS.
    "premium_sms": {"max_table_cols": 0, "max_chars": 153},
}


# Heuristik-Prioritaet fuer die Auto-Verteilung (Katalog-IDs, nicht #331-JS-IDs).
# Hoeher = wichtiger. Die 5 wichtigsten landen im ``primary``-Bucket.
METRIC_PRIORITY = {
    "temperature": 95, "wind": 90, "gust": 88, "rain_probability": 85,
    "precipitation": 78, "wind_chill": 70, "cloud_total": 65, "thunder": 60,
    "fresh_snow": 55, "visibility": 55, "freezing_level": 50, "uv_index": 45,
    "wind_direction": 40, "snow_depth": 35, "precip_type": 35, "snowfall_limit": 35,
    "cloud_low": 30, "humidity": 25, "sunshine": 25, "dewpoint": 20,
    "pressure": 18, "cape": 15, "cloud_mid": 12, "cloud_high": 10, "confidence": 8,
}

# Anzahl Metriken, die die Auto-Verteilung als ``primary`` markiert.
_PRIMARY_SLOTS = 5

# #1484/#1660 A/#1728 S1: reine Sichtbarkeits-Gates ohne eigenen Stundenwert
# (Nachtfenster-Skalare + Tagesrichtungen). Sie tragen ihren Wert ueber
# SMS-Token bzw. Abend-Untergrenzen und duerfen nie in einem Bucket landen.
VISIBILITY_GATE_IDS: frozenset[str] = frozenset({
    "temperature_night", "wind_chill_night",
    "temperature_day_low", "temperature_day_high",
    "wind_chill_day_low", "wind_chill_day_high",
})


@dataclass(frozen=True)
class ChannelLayout:
    """Ergebnis der Layout-Berechnung fuer einen Kanal."""
    table_columns: list[str]   # metric_ids in Spalten-Reihenfolge (ohne Zeit)
    demoted_count: int         # aus primary verdraengt (Logging/Badge/Hinweis)


def telegram_metric_notice(demoted_count: int, *, context: str) -> str:
    """context='vergleich' -> Ortsvergleich-Wortlaut (#1362, unveraendert).
    context='route' -> Trip-Wortlaut (#1741, neu). Leer, wenn nichts verdraengt wurde.

    Die beiden Wortlaute sind BEWUSST nicht ueber einen gemeinsamen Satzbau
    gebildet: im Ortsvergleich fehlen die verdraengten Groessen in der
    Telegram-Nachricht GANZ, im Trip stehen sie unmittelbar darueber in der
    Kurzuebersicht als Tageswert. Ein gemeinsamer Text waere fuer eine der
    beiden Flaechen sachlich falsch."""
    if demoted_count <= 0:
        return ""
    if context == "vergleich":
        return (
            f"… +{demoted_count} weitere Wettergrößen je Ort (Telegram-Limit) "
            "— vollständig per E-Mail"
        )
    return (
        f"… +{demoted_count} weitere Wettergrößen nur als Tageswert "
        "(Telegram-Limit)"
    )


def render_for_channel(
    channel: str, dc: "UnifiedWeatherDisplayConfig", report_type: str,
) -> ChannelLayout:
    """Berechne das Spalten-/Detail-Layout fuer ``channel``.

    Respektiert die per-Report-Typ-Flags ueber ``get_metrics_for_channel``,
    das wiederum kanal-spezifische Listen (Issue #429) oder die globale
    Liste (Fallback) liefert.
    """
    enabled = dc.get_metrics_for_channel(channel, report_type)
    # #1484/#1660 Scheibe A: Nachtfenster-Skalare — nie eine Tabellenspalte/
    # Detail-Zeile; den Wert tragen SMS-Token bzw. die Abend-Untergrenzen der
    # Kurzzusammenfassung/Telegram-Kurzuebersicht.
    # #1728 Scheibe 1: dieselbe Lage fuer die vier Tagesrichtungen — reine
    # Sichtbarkeits-Gates ohne eigenen Stundenwert. Kein Eintrag in
    # METRIC_PRIORITY noetig: die Auto-Verteilungs-Heuristik sieht sie dank
    # dieses Filters gar nicht erst.
    enabled = [m for m in enabled if m.metric_id not in VISIBILITY_GATE_IDS]
    primary = sorted(
        [m for m in enabled if m.bucket == "primary"], key=lambda m: m.order,
    )

    channel_cfg = CHANNEL_LIMITS.get(channel, CHANNEL_LIMITS["telegram"])
    limit = channel_cfg["max_table_cols"]
    if limit is None:                       # Email: kein Limit
        table, overflow = primary, []
    elif limit == 0:                        # SMS: keine Tabelle
        table, overflow = [], primary
    else:                                   # Telegram (und unbekannte Kanaele): Slot 0 = Zeit
        metric_slots = limit - 1
        table, overflow = primary[:metric_slots], primary[metric_slots:]

    return ChannelLayout(
        table_columns=[m.metric_id for m in table],
        demoted_count=len(overflow),
    )


def auto_distribute(enabled_ids: list[str]) -> list["MetricConfig"]:
    """Verteile aktive Metrik-IDs auf primary/secondary (Signal-safe Heuristik).

    Die 5 wichtigsten (nach ``METRIC_PRIORITY``) -> ``primary`` mit order 0..4,
    der Rest -> ``secondary`` mit order 0..n. Reihenfolge stabil: bei gleicher
    Prioritaet bleibt die Eingabe-Reihenfolge erhalten.
    """
    from app.models import MetricConfig

    ranked = sorted(
        enumerate(enabled_ids),
        key=lambda pair: (-METRIC_PRIORITY.get(pair[1], 0), pair[0]),
    )
    ordered_ids = [mid for _, mid in ranked]

    result: list[MetricConfig] = []
    for idx, metric_id in enumerate(ordered_ids):
        if idx < _PRIMARY_SLOTS:
            result.append(MetricConfig(
                metric_id=metric_id, bucket="primary", order=idx,
            ))
        else:
            result.append(MetricConfig(
                metric_id=metric_id, bucket="secondary", order=idx - _PRIMARY_SLOTS,
            ))
    return result
