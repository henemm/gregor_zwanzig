"""TDD RED — #1703 Scheibe 8: kanalweise Metrik-Aufloesung im Ortsvergleich.

Spec: docs/specs/modules/feat_1703_s8_compare_kanal_tabs.md
  Abschnitt 1 ("Backend — kanalweise Aufloesung"), AC-S8-1, AC-S8-2, AC-S8-15.
Kontext: docs/context/feat-1703-s8-compare-kanal-tabs.md

Heutiger Stand (nachgemessen): `report_config_resolver.py:280` reicht EINE
flache Liste (`resolve_enabled_metrics(display_config["active_metrics"])`) an
alle drei Compare-Renderer. `resolve_channel_enabled_metrics()` existiert
NICHT -- jeder Test dieser Datei scheitert deshalb an der Zusicherung in
`_resolve()` (RED). Muster: tests/unit/test_compare_active_metrics_dual_format.py
(getattr IN der Funktion statt Modul-Import, damit jeder Test einzeln und mit
lesbarer Begruendung rot wird statt die Collection der Datei zu sprengen).

Kern-Schicht, deterministisch: kein Netz, kein Mock, kein patch().
Erwartungswerte sind echte Renderer-IDs aus FRONTEND_TO_RENDERER_METRIC_ID.
"""
from __future__ import annotations

from output.renderers import compare_metric_ids
from output.renderers.compare_metric_ids import resolve_enabled_metrics

# Grundauswahl der Uebersichtstabelle, aufgeloest wie im Resolver:
# ['temp_max', 'wind_max'] -- die Renderer-IDs zu temp_max_c / wind_max_kmh.
GLOBAL = resolve_enabled_metrics(["temp_max_c", "wind_max_kmh"])


def _resolve(global_metrics, channel_active_metrics, channel):
    fn = getattr(compare_metric_ids, "resolve_channel_enabled_metrics", None)
    assert fn is not None, (
        "RED: resolve_channel_enabled_metrics() fehlt in "
        "src/output/renderers/compare_metric_ids.py -- ohne sie liest der "
        "Compare-Resolver fuer alle drei Kanaele dieselbe flache Liste "
        "(genau die Attrappe, die #1287/#1291 zum Rueckbau gefuehrt hat)."
    )
    return fn(global_metrics, channel_active_metrics, channel)


def test_ac1_kanal_kann_global_abgewaehlte_metrik_nicht_zurueckholen():
    """AC-S8-1 (ADR-0050 Regel 1/2): Grundauswahl ist das MAXIMUM."""
    result = _resolve(GLOBAL, {"sms": ["temp_max_c", "precip_sum_mm"]}, "sms")
    assert result == ["temp_max"], (
        "AC-S8-1 FAIL: precip_sum steht im SMS-Override, aber NICHT in der "
        "Grundauswahl -- ein Kanal darf nur abwaehlen, nie zurueckholen "
        f"(M1: Schnitt gegen global_metrics entfernt). Ergebnis: {result}"
    )


def test_ac2_neuformat_eintrag_ausserhalb_der_grundauswahl_faellt_raus():
    """AC-S8-2: derselbe Schnitt greift auch beim {metric_id, aggregation}-Format."""
    channel_raw = {
        "sms": [
            {"metric_id": "precipitation", "aggregation": "sum"},
            {"metric_id": "temperature", "aggregation": "max"},
        ]
    }
    result = _resolve(GLOBAL, channel_raw, "sms")
    assert result == ["temp_max"], (
        "AC-S8-2 FAIL: ein Neuformat-Eintrag ausserhalb der Grundauswahl "
        f"erreicht den gerenderten SMS-Text. Ergebnis: {result}"
    )


def test_ac15_fehlendes_channel_feld_liefert_die_globale_liste():
    """AC-S8-15: Altbestand -- `channel_active_metrics` fehlt komplett."""
    assert _resolve(GLOBAL, None, "sms") == GLOBAL, (
        "AC-S8-15 FAIL: ein heute gespeichertes Preset (ohne "
        "channel_active_metrics) muss unveraendert die globale Auswahl "
        "liefern -- M8 (stattdessen []) wuerde alle Bestandsvergleiche leeren."
    )


def test_ac15_leeres_channel_objekt_liefert_die_globale_liste():
    """AC-S8-15, zweite Form: `channel_active_metrics == {}`."""
    assert _resolve(GLOBAL, {}, "sms") == GLOBAL, (
        "AC-S8-15 FAIL: ein leeres channel_active_metrics-Objekt ist KEIN "
        "Override -- alle drei Kanaele folgen der Grundauswahl."
    )


def test_kanal_ohne_eigenen_eintrag_folgt_der_grundauswahl():
    """Nur E-Mail wurde editiert -- SMS folgt weiter der Grundauswahl."""
    assert _resolve(GLOBAL, {"email": ["temp_max_c"]}, "sms") == GLOBAL


def test_global_none_ist_kein_maximum_und_schneidet_nicht():
    """`active_metrics` fehlt (=> None): kein Maximum definiert, kein Schnitt.

    Vorbild: models.py:913-914 (`_clip_to_global_maximum` bei leerem
    self.metrics). Bewusst NICHT mit dem []-Fall zusammengelegt -- die beiden
    Faelle haben gegensaetzliches Sollverhalten.
    """
    result = _resolve(None, {"sms": ["temp_max_c"]}, "sms")
    assert result == ["temp_max"], (
        "FAIL: bei fehlender Grundauswahl (None) gibt es kein Maximum -- die "
        f"Kanal-Liste darf dann nicht leergeschnitten werden. Ergebnis: {result}"
    )


def test_global_leere_liste_ist_ein_maximum_und_schneidet_den_kanal_leer():
    """`active_metrics == []` (bewusste Leerauswahl) IST ein Maximum: die leere Menge."""
    result = _resolve([], {"sms": ["temp_max_c"]}, "sms")
    assert result == [], (
        "FAIL: eine bewusst geleerte Grundauswahl ([]) muss jeden Kanal auf [] "
        "schneiden ('leer heisst leer', #1366) -- eine Verwechslung mit dem "
        f"None-Fall holt abgewaehlte Metriken zurueck. Ergebnis: {result}"
    )


def test_bewusst_geleerter_kanal_bleibt_leer():
    """Kanal-Key vorhanden, Liste leer -> kein Rueckfall auf die Grundauswahl."""
    result = _resolve(GLOBAL, {"sms": []}, "sms")
    assert result == [], (
        "FAIL: eine bewusste Leerauswahl im SMS-Reiter darf nicht auf die "
        f"globale Liste zurueckfallen (Backend-Haelfte von AC-S8-11). Ergebnis: {result}"
    )


def test_reihenfolge_folgt_der_kanalliste_nicht_der_globalen():
    """Die Kanal-Reihenfolge erreicht den Renderer (compare_metric_ids.py:172)."""
    global_metrics = resolve_enabled_metrics(
        ["temp_max_c", "wind_max_kmh", "precip_sum_mm"]
    )
    result = _resolve(global_metrics, {"sms": ["precip_sum_mm", "temp_max_c"]}, "sms")
    assert result == ["precip_sum", "temp_max"], (
        "FAIL: das Ergebnis muss der Reihenfolge der KANAL-Liste folgen, nicht "
        f"der der Grundauswahl (['temp_max', ...] waere falsch). Ergebnis: {result}"
    )


def test_unaufloesbarer_kanaleintrag_faellt_auf_die_grundauswahl_zurueck():
    """Defensiv (Fremddaten): kein Absturz, kein leerer Kanal."""
    assert _resolve(GLOBAL, {"sms": None}, "sms") == GLOBAL, (
        "FAIL: ein null-Kanaleintrag muss auf die Grundauswahl zurueckfallen"
    )
    assert _resolve(GLOBAL, {"sms": "temp_max_c"}, "sms") == GLOBAL, (
        "FAIL: ein Nicht-Listen-Kanaleintrag muss auf die Grundauswahl "
        "zurueckfallen (resolve_enabled_metrics liefert dafuer None)"
    )
