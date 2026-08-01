"""Compare-Metrik-Katalog (Backend-Datenquelle fuer #1350 Teil 1).

Liefert die 26 Ortsvergleich-Metriken als explizite, angereicherte Struktur
(Label/Unit/Decimals/`higherIsBetter`/`kind`/Wertebereich bzw. Enum-/Ordinal-
Werte). Migriert 1:1 aus den heutigen Frontend-Quellen
`compareMetricDefs.ts::ALL_METRICS` und `corridorEditorState.ts` (Thunder-
Ordinal-Sonderbehandlung, PO-Entscheidung 2026-07-12) — siehe
docs/specs/modules/compare_metric_catalog_endpoint.md.

Teil 1 (Strangler-Migration, Issue #1350): Der Katalog wird NUR bereitgestellt,
noch nicht vom Frontend konsumiert. Keine Aenderung an compareMetricDefs.ts,
corridorEditorState.ts oder der `active_metrics`/`corridors`-Persistenz.

Teil 3 (docs/specs/modules/compare_metric_ssot_final.md, D1 Hybrid): jeder
Eintrag traegt zusaetzlich `alarmCapable: bool` -- `True` fuer genau die 10
Keys aus `compare_alert.py::_SUMMARY_KEY_TO_CATALOG_ID` (semantisches
Alarm-Engine-Wissen gehoert ins Backend), sonst `False`.

#1435 E1a (docs/specs/modules/feat_1435_e1a_alarmfaehigkeit_register.md): jeder
Eintrag traegt zusaetzlich `alertMetric` -- die Alarm-Identitaet des Paares
(Groesse, Auswertung) aus dem zentralen Register, `None` wenn die Zeile keinen
Alarm ausloesen kann. `alarmCapable` wird ab jetzt daraus abgeleitet
(`is not None`) statt aus `_SUMMARY_KEY_TO_CATALOG_ID.keys()`; die Menge bleibt
dieselben 10 Keys (verhaltensneutral, nachgewiesen in
`tests/unit/test_alert_metric_identity_delivery.py`).

#1373 (S2 Scheibe A, docs/specs/modules/feat_1373_s2_ein_katalog.md): jeder
Eintrag traegt zusaetzlich `metric_id` (Kennung der zentralen Katalog-Groesse
in `src/app/metric_catalog.py`) und `aggregation` (die Auswertung, die dieser
Eintrag zeigt). Die Tabelle bleibt kuratiert -- sie wird NICHT erzeugt (Labels,
Wertebereiche und Bedienstruktur sind redaktionell und im zentralen Katalog
nicht vorhanden). Die beiden Felder stellen die Beziehung zum zentralen Katalog
nachweisbar her; `tests/unit/test_compare_catalog_derives_from_central_catalog.py`
schlaegt kuenftig an, wenn eine waehlbare zentrale Groesse den Vergleich nicht
erreicht. `key` bleibt unveraendert erhalten (Rueckwaertskompatibilitaet).

#1401 Scheibe A1 (docs/specs/modules/fix_1401_a1_namensregister.md): der
Anzeigename wird NICHT mehr getippt, sondern zur Aufrufzeit aus dem zentralen
Register abgeleitet (`get_metric(metric_id).label_de`); die Auswertung steht
als eigenes Feld `aggregation_label` daneben (Maximum/Minimum/Mittel/Summe)
statt im Namen ("Temperatur max"). Wertebereiche, `kind` und `ordinalLabels`
bleiben kuratiert -- abgeleitet wird ausschliesslich der Name.

Keys sind identisch zu `compare_metric_ids.py::FRONTEND_TO_RENDERER_METRIC_ID`
(keine sechste Kopie der Keyliste) -- der Modul-Import-Assert unten macht eine
kuenftige Drift wie #1324 strukturell unmoeglich: fehlt ein Key im Katalog oder
im Resolver, schlaegt der Import fehl.
"""
from __future__ import annotations

from app.metric_catalog import aggregation_label_de, alert_metric_for, get_metric
from output.renderers.compare_hourly_metric_ids import (
    HOURLY_DEFAULT_METRIC_IDS, HOURLY_EXCLUDED_METRIC_IDS, HOURLY_EXCLUSION_REASON,
    HOURLY_LEGACY_KEYS_BY_METRIC_ID, HOURLY_MERGE_ONLY_METRIC_IDS,
)
from output.renderers.compare_metric_ids import FRONTEND_TO_RENDERER_METRIC_ID
from services.compare_alert import _SUMMARY_KEY_TO_CATALOG_ID

# #1401 A1: deutsche Beschriftung der Auswertung -- eigenes Anzeige-Element
# neben dem Namen, nicht Teil des Namens.
# #1357: die Tabelle selbst liegt jetzt im zentralen Katalog
# (``metric_catalog.aggregation_label_de``) -- EINE Quelle fuer beide Seiten.

# Reihenfolge = ALL_METRICS-Reihenfolge im Frontend (compareMetricDefs.ts),
# erleichtert visuellen Diff in Teil 2 (Spec "Expected Behavior").
#
# `metric_id`/`aggregation` (#1373): gemessen am zentralen Katalog
# (`metric_catalog.MetricDefinition.summary_fields`), nicht geraten. Fuer 24 der
# 26 Keys ist der Compare-Key woertlich der Summary-Feldname der zentralen
# Groesse. Die zwei verbleibenden Abweichungen sind hier einzeln vermerkt:
#   sunny_hours_h      -> sunshine/sum       (zentral "sunny_hours", ohne _h)
#   wind_direction_deg -> wind_direction/avg (zentral "wind_direction_avg_deg")
# Seit #1391/#1392 tragen auch snowfall_limit_m (MIN -- kanonische Trip-Regel,
# weather_metrics.py:_compute_snowfall_limit) und cloud_low/mid/high (AVG,
# gerundet) `summary_fields` und sind damit keine Abweichung mehr.
COMPARE_METRIC_CATALOG: list[dict] = [
    {"key": "snow_depth_cm", "unit": "cm", "decimals": 0,
     "higherIsBetter": True, "kind": "range", "rangeMin": 0, "rangeMax": 200, "step": 5,
     "metric_id": "snow_depth", "aggregation": "max"},
    {"key": "snow_new_sum_cm", "unit": "cm", "decimals": 0,
     "higherIsBetter": True, "kind": "range", "rangeMin": 0, "rangeMax": 50, "step": 1,
     "metric_id": "fresh_snow", "aggregation": "sum"},
    {"key": "sunny_hours_h", "unit": "h", "decimals": 1,
     "higherIsBetter": True, "kind": "range", "rangeMin": 0, "rangeMax": 12, "step": 0.5,
     "metric_id": "sunshine", "aggregation": "sum"},
    {"key": "wind_max_kmh", "unit": "km/h", "decimals": 0,
     "higherIsBetter": False, "kind": "range", "rangeMin": 0, "rangeMax": 100, "step": 5,
     "metric_id": "wind", "aggregation": "max"},
    {"key": "cloud_avg_pct", "unit": "%", "decimals": 0,
     "higherIsBetter": False, "kind": "range", "rangeMin": 0, "rangeMax": 100, "step": 5,
     "metric_id": "cloud_total", "aggregation": "avg"},
    {"key": "visibility_min_m", "unit": "m", "decimals": 0,
     "higherIsBetter": True, "kind": "range", "rangeMin": 0, "rangeMax": 10000, "step": 500,
     "metric_id": "visibility", "aggregation": "min"},
    {"key": "precip_sum_mm", "unit": "mm", "decimals": 1,
     "higherIsBetter": False, "kind": "range", "rangeMin": 0, "rangeMax": 30, "step": 0.5,
     "metric_id": "precipitation", "aggregation": "sum"},
    {"key": "uv_index_max", "unit": "", "decimals": 0,
     "higherIsBetter": False, "kind": "range", "rangeMin": 0, "rangeMax": 12, "step": 1,
     "metric_id": "uv_index", "aggregation": "max"},
    {"key": "temp_max_c", "unit": "°C", "decimals": 0,
     "higherIsBetter": True, "kind": "range", "rangeMin": -20, "rangeMax": 45, "step": 1,
     "metric_id": "temperature", "aggregation": "max"},
    {"key": "thunder_level_max", "unit": "", "decimals": 0,
     "higherIsBetter": False, "kind": "ordinal",
     "ordinalLabels": ["kein", "mittel", "hoch"],
     "metric_id": "thunder", "aggregation": "max"},
    {"key": "temp_min_c", "unit": "°C", "decimals": 0,
     "higherIsBetter": True, "kind": "range", "rangeMin": -30, "rangeMax": 30, "step": 1,
     "metric_id": "temperature", "aggregation": "min"},
    {"key": "gust_max_kmh", "unit": "km/h", "decimals": 0,
     "higherIsBetter": False, "kind": "range", "rangeMin": 0, "rangeMax": 150, "step": 5,
     "metric_id": "gust", "aggregation": "max"},
    {"key": "cape_max_jkg", "unit": "J/kg", "decimals": 0,
     "higherIsBetter": False, "kind": "range", "rangeMin": 0, "rangeMax": 3000, "step": 100,
     "metric_id": "cape", "aggregation": "max"},
    {"key": "freezing_level_m", "unit": "m", "decimals": 0,
     "higherIsBetter": True, "kind": "range", "rangeMin": 0, "rangeMax": 5000, "step": 100,
     "metric_id": "freezing_level", "aggregation": "min"},
    {"key": "pop_max_pct", "unit": "%", "decimals": 0,
     "higherIsBetter": False, "kind": "range", "rangeMin": 0, "rangeMax": 100, "step": 5,
     "metric_id": "rain_probability", "aggregation": "max"},
    {"key": "wind_direction_deg", "unit": "°", "decimals": 0,
     "higherIsBetter": False, "kind": "range", "rangeMin": 0, "rangeMax": 360, "step": 10,
     "metric_id": "wind_direction", "aggregation": "avg"},
    {"key": "wind_chill_min_c", "unit": "°C", "decimals": 0,
     "higherIsBetter": True, "kind": "range", "rangeMin": -30, "rangeMax": 30, "step": 1,
     "metric_id": "wind_chill", "aggregation": "min"},
    {"key": "wind_chill_max_c", "unit": "°C", "decimals": 0,
     "higherIsBetter": True, "kind": "range", "rangeMin": -20, "rangeMax": 45, "step": 1,
     "metric_id": "wind_chill", "aggregation": "max"},
    {"key": "humidity_avg_pct", "unit": "%", "decimals": 0,
     "higherIsBetter": False, "kind": "range", "rangeMin": 0, "rangeMax": 100, "step": 5,
     "metric_id": "humidity", "aggregation": "avg"},
    {"key": "dewpoint_avg_c", "unit": "°C", "decimals": 0,
     "higherIsBetter": False, "kind": "range", "rangeMin": -20, "rangeMax": 30, "step": 1,
     "metric_id": "dewpoint", "aggregation": "avg"},
    {"key": "snowfall_limit_m", "unit": "m", "decimals": 0,
     "higherIsBetter": True, "kind": "range", "rangeMin": 0, "rangeMax": 5000, "step": 100,
     "metric_id": "snowfall_limit", "aggregation": "min"},
    {"key": "precip_type_dominant", "unit": "", "decimals": 0,
     "higherIsBetter": False, "kind": "enum",
     "enumValues": ["RAIN", "SNOW", "MIXED", "FREEZING_RAIN"],
     "metric_id": "precip_type", "aggregation": "max"},
    {"key": "cloud_low_avg_pct", "unit": "%", "decimals": 0,
     "higherIsBetter": False, "kind": "range", "rangeMin": 0, "rangeMax": 100, "step": 5,
     "metric_id": "cloud_low", "aggregation": "avg"},
    {"key": "cloud_mid_avg_pct", "unit": "%", "decimals": 0,
     "higherIsBetter": False, "kind": "range", "rangeMin": 0, "rangeMax": 100, "step": 5,
     "metric_id": "cloud_mid", "aggregation": "avg"},
    {"key": "cloud_high_avg_pct", "unit": "%", "decimals": 0,
     "higherIsBetter": False, "kind": "range", "rangeMin": 0, "rangeMax": 100, "step": 5,
     "metric_id": "cloud_high", "aggregation": "avg"},
    {"key": "pressure_avg_hpa", "unit": "hPa", "decimals": 0,
     "higherIsBetter": True, "kind": "range", "rangeMin": 950, "rangeMax": 1050, "step": 5,
     "metric_id": "pressure", "aggregation": "avg"},
]

# Drift-Wächter (Spec Punkt 3): Katalog-Keys MÜSSEN mit der autoritativen
# Key-Liste aus compare_metric_ids.py identisch sein -- fehlt ein Key auf
# einer der beiden Seiten, schlägt der Import fehl (statt still zu driften,
# vgl. #1324).
_catalog_keys = {entry["key"] for entry in COMPARE_METRIC_CATALOG}
_resolver_keys = set(FRONTEND_TO_RENDERER_METRIC_ID.keys())
assert _catalog_keys == _resolver_keys, (
    "compare_metric_catalog.py Keys weichen von "
    "compare_metric_ids.FRONTEND_TO_RENDERER_METRIC_ID ab: "
    f"nur im Katalog: {_catalog_keys - _resolver_keys}, "
    f"nur im Resolver: {_resolver_keys - _catalog_keys}"
)

# Drift-Waechter (Teil 3, defensiv): alarmfaehige Keys muessen eine Teilmenge
# der Katalog-Keys sein -- kein neuer Datenverlust-Pfad, falls
# _SUMMARY_KEY_TO_CATALOG_ID jemals einen Key nennt, den es im Katalog nicht
# (mehr) gibt.
_alarm_keys = set(_SUMMARY_KEY_TO_CATALOG_ID.keys())
assert _alarm_keys <= _catalog_keys, (
    "compare_alert._SUMMARY_KEY_TO_CATALOG_ID nennt Keys, die nicht im "
    f"Compare-Metrik-Katalog existieren: {_alarm_keys - _catalog_keys}"
)


def duplicate_metric_aggregation_pairs(
    entries: list[dict] | None = None,
) -> list[tuple[str, str]]:
    """Liefert jedes (metric_id, aggregation)-Paar, das in `entries` mehr als
    einmal vorkommt (jedes Paar hoechstens einmal, in Fundreihenfolge). Leere
    Liste = in Ordnung.

    #1373 Scheibe B (AC-10): das Paar ist im neuen Speicherformat der
    Metrik-Auswahl (`display_config.active_metrics`) der EINZIGE Schluessel --
    zwei paargleiche Katalog-Zeilen wuerden unbemerkt auf denselben
    Auswahl-Eintrag kollidieren und eine der beiden Metriken unspeicherbar
    machen. `entries=None` prueft den echten Katalog; der Modul-Import-Assert
    unten und der Wirkungsnachweis im Test rufen DIESELBE Funktion auf
    (Adversary-Befund F002 aus Scheibe A: eine im Test nachgebaute Kopie der
    Pruflogik beweist nichts)."""
    source = COMPARE_METRIC_CATALOG if entries is None else entries
    seen: set[tuple[str, str]] = set()
    duplicates: list[tuple[str, str]] = []
    for entry in source:
        if not isinstance(entry, dict):
            continue
        pair = (entry.get("metric_id"), entry.get("aggregation"))
        if pair in seen:
            if pair not in duplicates:
                duplicates.append(pair)  # type: ignore[arg-type]
        else:
            seen.add(pair)  # type: ignore[arg-type]
    return duplicates


# Drift-Waechter (#1373 Scheibe B, AC-10): schlaegt beim Modul-Import an, wenn
# eine kuenftige Katalog-Zeile ein bereits belegtes Groesse-Auswertung-Paar
# traegt -- ueber genau die Funktion oben, nicht ueber eine zweite Kopie der
# Logik.
_duplicate_pairs = duplicate_metric_aggregation_pairs()
assert not _duplicate_pairs, (
    "compare_metric_catalog.py fuehrt mehrfach dasselbe "
    f"(metric_id, aggregation)-Paar: {_duplicate_pairs} -- im neuen "
    "Speicherformat von display_config.active_metrics nicht unterscheidbar."
)

# Umkehr-Index (#1373 Scheibe B, Spec Punkt 1): (metric_id, aggregation) -> key.
# KEINE fuenfte Uebersetzungstabelle, sondern ein reiner Index ueber die in
# Scheibe A kuratierten Herkunftsfelder -- Eindeutigkeit garantiert der Assert
# darueber.
_KEY_BY_METRIC_AGGREGATION: dict[tuple[str, str], str] = {
    (entry["metric_id"], entry["aggregation"]): entry["key"]
    for entry in COMPARE_METRIC_CATALOG
}


def key_for(metric_id: object, aggregation: object) -> str | None:
    """Loest ein Groesse-Auswertung-Paar (neues Speicherformat der
    Metrik-Auswahl) auf den Compare-Auswahl-Schluessel zurueck.

    Unbekannte, unvollstaendige oder falsch typisierte Paare ergeben `None`
    (Signal "nicht aufloesbar") -- kein KeyError, keine Ausnahme; darauf beruht
    der Verwerfungspfad in `compare_metric_ids.resolve_enabled_metrics()`."""
    if not isinstance(metric_id, str) or not isinstance(aggregation, str):
        return None
    return _KEY_BY_METRIC_AGGREGATION.get((metric_id, aggregation))


def get_compare_metric_catalog(entries: list[dict] | None = None) -> list[dict]:
    """Liefert die 26 Ortsvergleich-Metriken (read-only Kopie der Katalog-Liste),
    angereichert um `alarmCapable` (Teil 3, D1 Hybrid), `label` und
    `aggregation_label` (#1401 A1). `metric_id`/`aggregation` (#1373) stehen
    bereits an den Eintraegen selbst.

    `label` kommt aus dem zentralen Register (`metric_catalog.label_de`) und
    wird HIER, zur Aufrufzeit, aufgeloest -- nicht beim Modul-Import: ein
    kuenftiger Registerfehler laesst dann den Endpoint-Aufruf sichtbar
    scheitern statt den Serverstart. Eine `metric_id`, die das Register nicht
    kennt, wirft `KeyError` MIT der fehlenden Kennung im Text (kein Auffangen,
    kein Ersatzname -- #1401 AC-4).

    `entries` injiziert eine Testkopie der Katalogzeilen (Vorbild:
    `duplicate_metric_aggregation_pairs(entries=...)`), damit dieser
    Scheiter-Pfad ohne Monkeypatch des echten Katalogs pruefbar ist."""
    source = COMPARE_METRIC_CATALOG if entries is None else entries
    result: list[dict] = []
    for entry in source:
        metric_id = entry["metric_id"]
        try:
            label = get_metric(metric_id).label_de
        except KeyError as exc:
            raise KeyError(
                f"Compare-Katalogzeile {entry.get('key')!r} nennt die zentral "
                f"unbekannte Groesse {metric_id!r} -- der Anzeigename ist nicht "
                "ableitbar (src/app/metric_catalog.py)"
            ) from exc
        aggregation = entry["aggregation"]
        # #1435 E1a: die Alarm-Identitaet kommt aus dem zentralen Register
        # (Paar Groesse+Auswertung); `alarmCapable` ist ab jetzt nur noch ihre
        # Boolean-Sicht statt einer zweiten, handgepflegten Liste. Die Menge ist
        # verhaltensneutral identisch zu _SUMMARY_KEY_TO_CATALOG_ID (10 Keys),
        # bewiesen in tests/unit/test_alert_metric_identity_delivery.py.
        alert_metric = alert_metric_for(metric_id, aggregation)
        # #1406 Scheibe B: der Stundenverlauf speist seine Grundauswahl aus
        # DIESER Antwort. Damit die Bedienflaeche keine eigene Alias-Tabelle,
        # keine eigene Vorgabemenge und kein eigenes Wissen ueber Ausnahmen
        # braucht (das waere der fuenfte Vokabular-Ort, AC-10), reist alles
        # Noetige hier mit -- abgeleitet aus compare_hourly_metric_ids.py,
        # nicht zweitgepflegt.
        result.append({
            **entry,
            "label": label,
            "aggregation_label": aggregation_label_de(aggregation),
            "alertMetric": alert_metric,
            "alarmCapable": alert_metric is not None,
            "hourlySelectable": metric_id not in HOURLY_EXCLUDED_METRIC_IDS,
            "hourlyNotSelectableReason": HOURLY_EXCLUSION_REASON.get(metric_id, ""),
            "hourlyDefault": metric_id in HOURLY_DEFAULT_METRIC_IDS,
            "hourlyMergeOnly": metric_id in HOURLY_MERGE_ONLY_METRIC_IDS,
            "hourly_legacy_keys": list(
                HOURLY_LEGACY_KEYS_BY_METRIC_ID.get(metric_id, [])
            ),
        })
    return result
