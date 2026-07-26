"""AC-11 der Spec `docs/specs/modules/feat_1373_s2b_metrik_speicherformat.md`
(#1373, S2 Scheibe B): der Alarm-Pfad des Ortsvergleichs ist ein ZWEITER,
unabhaengiger Leser von `display_config.active_metrics` (#1191). Nach dem
Formatwechsel muss er genau dieselben Groessen ueberwachen wie vorher -- egal
ob die Auswahl als Zeichenketten (Altformat) oder als Groesse+Auswertung
(Neuformat) gespeichert ist.

Kern-Schicht, deterministisch: kein Netz, kein Mock, kein `patch()`, kein
Datei-I/O. Geprueft wird die ECHTE Produktionsfunktion
`CompareAlertService._display_config_from_active_metrics` -- unbound
aufgerufen, weil sie `self` nicht benutzt und ein echter Dienst-Aufbau
(Settings/Store/Throttle) Datei-I/O und Nutzerverzeichnisse anlegen wuerde,
ohne am Pruefgegenstand etwas zu aendern.

Erwartungswerte werden aus dem ECHTEN Vergleichs-Katalog abgeleitet (Key ->
(metric_id, aggregation)), nicht aus `key_for()` -- sonst pruefte der Test die
Umkehrfunktion gegen sich selbst.
"""
from __future__ import annotations

from typing import Any

from output.renderers.compare_metric_catalog import COMPARE_METRIC_CATALOG
from services.compare_alert import CompareAlertService

# Drei alarmfaehige Auswahl-Schluessel, davon zwei mit DERSELBEN `metric_id`
# ("temperature") und unterschiedlicher Auswertung -- genau die
# Verschmelzungsfalle der Lieferung. Beide fuehren im Alarm-Namensraum auf
# VERSCHIEDENE Katalog-IDs ("temperature" vs. "temperature_cold").
_ALARM_KEYS = ["temp_max_c", "temp_min_c", "wind_max_kmh"]


def _pair_for_key(key: str) -> dict:
    matches = [e for e in COMPARE_METRIC_CATALOG if e["key"] == key]
    assert len(matches) == 1, f"Vorbedingung verletzt: {key!r} kommt {len(matches)}x vor"
    return {
        "metric_id": matches[0]["metric_id"],
        "aggregation": matches[0]["aggregation"],
    }


def _preset(active_metrics: Any) -> dict:
    return {
        "id": "cp-alarm",
        "kind": "vergleich",
        "location_ids": ["loc-a", "loc-b", "loc-c"],
        "display_config": {"active_metrics": active_metrics},
    }


def _monitored(active_metrics: Any) -> list[tuple[str, bool]]:
    """Ueberwachte Groessen als (Katalog-ID, aktiv)-Liste -- der echte Bauplan,
    den die Alarm-Engine spaeter auswertet."""
    config = CompareAlertService._display_config_from_active_metrics(
        None,  # type: ignore[arg-type]  # self wird von der Methode nicht benutzt
        _preset(active_metrics),
    )
    assert config is not None, "Vorbedingung: vorhandene Auswahl => kein None-Fallback"
    return [(m.metric_id, m.enabled) for m in config.metrics]


def test_new_format_monitors_exactly_the_same_metrics_as_the_legacy_format():
    """AC-11: dieselbe Auswahl, einmal alt und einmal neu gespeichert, ergibt
    identisch ueberwachte Groessen -- keine faellt aus der Ueberwachung."""
    legacy = _monitored(list(_ALARM_KEYS))
    modern = _monitored([_pair_for_key(k) for k in _ALARM_KEYS])

    assert modern == legacy, (
        "AC-11: der Alarm-Pfad ueberwacht nach dem Formatwechsel andere "
        f"Groessen.\nalt: {legacy}\nneu: {modern}"
    )
    enabled = {cid for cid, on in modern if on}
    assert enabled == {"temperature", "temperature_cold", "wind"}, (
        "AC-11: Hoechst- UND Tiefsttemperatur muessen getrennt ueberwacht "
        f"bleiben (temperature/temperature_cold), tatsaechlich: {sorted(enabled)}"
    )


def test_every_alarm_capable_key_survives_the_format_switch():
    """AC-11, Vollabdeckung: JEDER alarmfaehige Auswahl-Schluessel muss im
    Neuformat dieselbe Katalog-ID aktivieren wie im Altformat."""
    from services.compare_alert import _SUMMARY_KEY_TO_CATALOG_ID

    for key in _SUMMARY_KEY_TO_CATALOG_ID:
        legacy = _monitored([key])
        modern = _monitored([_pair_for_key(key)])
        assert modern == legacy, (
            f"AC-11: Auswahl {key!r} ueberwacht im Neuformat andere Groessen.\n"
            f"alt: {legacy}\nneu: {modern}"
        )


def test_mixed_format_selection_monitors_all_chosen_metrics():
    """AC-5/AC-11: eine Mischliste (stehengebliebene Browser-Sitzung, R1) darf
    im Alarm-Pfad keine Groesse verlieren und nicht abbrechen."""
    mixed = _monitored(["temp_max_c", _pair_for_key("wind_max_kmh")])

    enabled = {cid for cid, on in mixed if on}
    assert enabled == {"temperature", "wind"}, (
        f"AC-11: Mischliste verliert Groessen: {sorted(enabled)}"
    )


def test_empty_selection_stays_all_quiet_in_both_formats():
    """AC-3/#1191: die bewusst leere Auswahl bleibt "alles stumm" -- und darf
    durch den Formatwechsel nicht zum Legacy-None-Fallback ("alles feuert")
    werden."""
    empty = _monitored([])

    assert empty, "Vorbedingung: die metrics-Liste ist nie leer (#1191 F001)"
    assert not any(on for _cid, on in empty), (
        f"AC-3: bei leerer Auswahl darf keine Groesse aktiv sein: {empty}"
    )


def test_unresolvable_entries_are_ignored_without_breaking_the_alarm_path():
    """Haerte: ein unbekanntes Paar, ein Objekt ohne Auswertung und ein
    fremder Typ zwischen gueltigen Eintraegen -- die gueltigen ueberleben, der
    Alarm-Pfad bricht nicht ab (heutiges Verhalten fuer nicht mappbare
    Zeichenketten, jetzt auch fuer Objekte)."""
    monitored = _monitored(
        [
            "temp_max_c",
            {"metric_id": "gibtsnicht", "aggregation": "max"},
            {"metric_id": "temperature"},
            None,
            42,
            _pair_for_key("gust_max_kmh"),
        ]
    )

    enabled = {cid for cid, on in monitored if on}
    assert enabled == {"temperature", "gust"}, (
        f"Gueltige Eintraege muessen ueberleben: {sorted(enabled)}"
    )
