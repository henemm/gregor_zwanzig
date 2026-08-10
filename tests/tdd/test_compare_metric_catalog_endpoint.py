"""RED-Tests fuer #1350 Teil 1: GET /api/compare/metrics (Backend-Metrik-Katalog).

Spec: docs/specs/modules/compare_metric_catalog_endpoint.md (AC-1..AC-3, Kern-Schicht)

Keine Mocks: echter FastAPI ``TestClient`` gegen die reale ``api.main.app`` (Muster
uebernommen von tests/tdd/test_weather_templates.py::TestTemplatesEndpoint). Der
Endpoint existiert zum Zeitpunkt dieses Commits noch nicht -> alle Tests sind ROT
(404, weil die Route fehlt).

Paritaets-Fixture (AC-3): eingefroren aus
frontend/src/lib/components/compare/compareMetricDefs.ts::ALL_METRICS (urspruenglich
25 Eintraege, Stand 2026-07-23), angereichert um die ``kind``-Sonderbehandlung aus
frontend/src/lib/components/shared/corridor-editor/corridorEditorState.ts:273-289
(thunder_level_max -> 'ordinal' statt 'enum', PO-Entscheidung 2026-07-12).

Issue #1351 Teil 1: ``wind_chill_max_c`` (Gefuehlte Temp. max, analog
``temp_max_c``) kommt als 26. Eintrag hinzu -- Katalog ist seit #1350 die
SSoT, das Frontend-Fixture ist nur noch die eingefrorene Ausgangsbasis.

#1373 (S2 Scheibe A, AC-6): jeder der 26 Eintraege traegt zusaetzlich
``metric_id`` (zentrale Katalog-ID) und ``aggregation`` (Auswertung) --
``key`` bleibt unveraendert erhalten (Rueckwaertskompatibilitaet).
SPEC: docs/specs/modules/feat_1373_s2_ein_katalog.md
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app
from app.metric_catalog import get_all_metrics, get_metric
from output.renderers.compare_metric_catalog import (
    COMPARE_METRIC_CATALOG,
    get_compare_metric_catalog,
)


@pytest.fixture()
def client() -> TestClient:
    """FastAPI TestClient gegen die reale App (kein Mock, kein Netz)."""
    return TestClient(app)


# ---------------------------------------------------------------------------
# Paritaets-Fixture: 25 Eintraege, eingefroren aus compareMetricDefs.ts::ALL_METRICS
# Reihenfolge = ALL_METRICS-Reihenfolge (Spec "Expected Behavior").
# Felder: key, label, higherIsBetter, kind, rangeMin, rangeMax (None bei enum/ordinal,
# da dort kein numerischer Wertebereich in ALL_METRICS existiert).
# ---------------------------------------------------------------------------
#
# #1401 Scheibe A1 (RED): die `label`-Spalte dieses Fixtures beschreibt ab hier
# den ZIELZUSTAND -- den Namen, wie ihn das zentrale Register
# (`metric_catalog.MetricDefinition.label_de`) fuehrt. Die Auswertung
# (Maximum/Minimum/Mittel/Summe) ist nicht mehr Teil des Namens, sie steht ab
# #1401 im eigenen Feld `aggregation_label`. Gemessen 2026-07-27: 16 der 26
# Labels weichen heute vom Register ab (8 redaktionell -- s. Namensentscheidungen
# der Spec --, 8 weitere nur durch die angehaengte Auswertung "max"/"min"/"Ø").
# SPEC: docs/specs/modules/fix_1401_a1_namensregister.md
EXPECTED_METRICS: list[dict] = [
    {"key": "snow_depth_cm", "label": "Schneehöhe", "higherIsBetter": True,
     "kind": "range", "rangeMin": 0, "rangeMax": 200},
    {"key": "snow_new_sum_cm", "label": "Neuschnee", "higherIsBetter": True,
     "kind": "range", "rangeMin": 0, "rangeMax": 50},
    {"key": "sunny_hours_h", "label": "Sonnenstunden", "higherIsBetter": True,
     "kind": "range", "rangeMin": 0, "rangeMax": 12},
    {"key": "wind_max_kmh", "label": "Wind", "higherIsBetter": False,
     "kind": "range", "rangeMin": 0, "rangeMax": 100},
    {"key": "cloud_avg_pct", "label": "Bewölkung", "higherIsBetter": False,
     "kind": "range", "rangeMin": 0, "rangeMax": 100},
    {"key": "visibility_min_m", "label": "Sichtweite", "higherIsBetter": True,
     "kind": "range", "rangeMin": 0, "rangeMax": 10000},
    {"key": "precip_sum_mm", "label": "Niederschlag", "higherIsBetter": False,
     "kind": "range", "rangeMin": 0, "rangeMax": 30},
    {"key": "uv_index_max", "label": "UV-Index", "higherIsBetter": False,
     "kind": "range", "rangeMin": 0, "rangeMax": 12},
    {"key": "temp_max_c", "label": "Temperatur", "higherIsBetter": True,
     "kind": "range", "rangeMin": -20, "rangeMax": 45},
    {"key": "thunder_level_max", "label": "Gewitter", "higherIsBetter": False,
     "kind": "ordinal", "rangeMin": None, "rangeMax": None},
    {"key": "temp_min_c", "label": "Temperatur", "higherIsBetter": True,
     "kind": "range", "rangeMin": -30, "rangeMax": 30},
    {"key": "gust_max_kmh", "label": "Böen", "higherIsBetter": False,
     "kind": "range", "rangeMin": 0, "rangeMax": 150},
    # Issue #1585: cape_max_jkg entfallen -- CAPE ist zentral nicht mehr
    # waehlbar, get_compare_metric_catalog() liefert die Zeile nicht mehr aus.
    {"key": "freezing_level_m", "label": "Nullgradgrenze", "higherIsBetter": True,
     "kind": "range", "rangeMin": 0, "rangeMax": 5000},
    {"key": "pop_max_pct", "label": "Regenwahrscheinlichkeit", "higherIsBetter": False,
     "kind": "range", "rangeMin": 0, "rangeMax": 100},
    {"key": "wind_direction_deg", "label": "Windrichtung", "higherIsBetter": False,
     "kind": "range", "rangeMin": 0, "rangeMax": 360},
    {"key": "wind_chill_min_c", "label": "Gefühlte Temperatur", "higherIsBetter": True,
     "kind": "range", "rangeMin": -30, "rangeMax": 30},
    # Issue #1351 Teil 1: 26. Eintrag, analog temp_max_c (Wertebereich).
    {"key": "wind_chill_max_c", "label": "Gefühlte Temperatur", "higherIsBetter": True,
     "kind": "range", "rangeMin": -20, "rangeMax": 45},
    {"key": "humidity_avg_pct", "label": "Luftfeuchtigkeit", "higherIsBetter": False,
     "kind": "range", "rangeMin": 0, "rangeMax": 100},
    {"key": "dewpoint_avg_c", "label": "Taupunkt", "higherIsBetter": False,
     "kind": "range", "rangeMin": -20, "rangeMax": 30},
    {"key": "snowfall_limit_m", "label": "Schneefallgrenze", "higherIsBetter": True,
     "kind": "range", "rangeMin": 0, "rangeMax": 5000},
    {"key": "precip_type_dominant", "label": "Niederschlagsart", "higherIsBetter": False,
     "kind": "enum", "rangeMin": None, "rangeMax": None},
    {"key": "cloud_low_avg_pct", "label": "Tiefe Wolken", "higherIsBetter": False,
     "kind": "range", "rangeMin": 0, "rangeMax": 100},
    {"key": "cloud_mid_avg_pct", "label": "Mittelhohe Wolken", "higherIsBetter": False,
     "kind": "range", "rangeMin": 0, "rangeMax": 100},
    {"key": "cloud_high_avg_pct", "label": "Hohe Wolken", "higherIsBetter": False,
     "kind": "range", "rangeMin": 0, "rangeMax": 100},
    {"key": "pressure_avg_hpa", "label": "Luftdruck", "higherIsBetter": True,
     "kind": "range", "rangeMin": 950, "rangeMax": 1050},
]

assert len(EXPECTED_METRICS) == 25, (
    "Paritaets-Fixture muss exakt 25 Eintraege haben "
    "(#1351: +wind_chill_max_c; #1585: -cape_max_jkg)"
)


# ---------------------------------------------------------------------------
# #1373 AC-6: Herkunfts-Fixture -- welche zentrale Groesse (metric_id) und
# welche Auswertung (aggregation) steht hinter jedem Compare-Key.
#
# Abgeleitet aus `metric_catalog.MetricDefinition.summary_fields` (gemessen
# 2026-07-26): fuer 22 der 26 Keys ist der Compare-Key woertlich der
# Summary-Feldname der zentralen Groesse (z. B. temperature/max ->
# "temp_max_c").
#
# Zwei weitere Keys weichen NAMENTLICH ab, die zentrale Groesse traegt ihr
# summary_fields aber sehr wohl -- sie sind daher KEINE Ausnahme von der
# Auswertungs-Pruefung (Messkorrektur 2026-07-26, metric_catalog.py:368
# bzw. :177):
#   sunny_hours_h      -> sunshine/sum       (zentral: "sunny_hours", ohne _h)
#   wind_direction_deg -> wind_direction/avg (zentral: "wind_direction_avg_deg")
#
# Nur fuer 4 Keys fehlt `summary_fields` strukturell -- ihre Herkunft ist hier
# explizit festgehalten (eigene Tickets, s. Ausnahmeliste in
# tests/unit/test_compare_catalog_derives_from_central_catalog.py):
#   cloud_low/mid/high -> cloud_low|mid|high/avg (summary_fields leer, #1392)
#   snowfall_limit_m   -> snowfall_limit/?   (summary_fields leer UND zwei
#                                             default_aggregations min/max,
#                                             #1391)
# Der Wert None bedeutet: Auswertung nicht eindeutig aus den Katalogdaten
# ableitbar -> unten wird nur auf Plausibilitaet geprueft
# (aggregation in default_aggregations), nicht auf einen festen Wert.
# ---------------------------------------------------------------------------
EXPECTED_METRIC_ORIGIN: dict[str, tuple[str, str | None]] = {
    "snow_depth_cm": ("snow_depth", "max"),
    "snow_new_sum_cm": ("fresh_snow", "sum"),
    "sunny_hours_h": ("sunshine", "sum"),
    "wind_max_kmh": ("wind", "max"),
    "cloud_avg_pct": ("cloud_total", "avg"),
    "visibility_min_m": ("visibility", "min"),
    "precip_sum_mm": ("precipitation", "sum"),
    "uv_index_max": ("uv_index", "max"),
    "temp_max_c": ("temperature", "max"),
    "thunder_level_max": ("thunder", "max"),
    "temp_min_c": ("temperature", "min"),
    "gust_max_kmh": ("gust", "max"),
    "freezing_level_m": ("freezing_level", "min"),
    "pop_max_pct": ("rain_probability", "max"),
    "wind_direction_deg": ("wind_direction", "avg"),
    "wind_chill_min_c": ("wind_chill", "min"),
    "wind_chill_max_c": ("wind_chill", "max"),
    "humidity_avg_pct": ("humidity", "avg"),
    "dewpoint_avg_c": ("dewpoint", "avg"),
    "snowfall_limit_m": ("snowfall_limit", None),
    "precip_type_dominant": ("precip_type", "max"),
    "cloud_low_avg_pct": ("cloud_low", "avg"),
    "cloud_mid_avg_pct": ("cloud_mid", "avg"),
    "cloud_high_avg_pct": ("cloud_high", "avg"),
    "pressure_avg_hpa": ("pressure", "avg"),
}

assert set(EXPECTED_METRIC_ORIGIN) == {m["key"] for m in EXPECTED_METRICS}, (
    "Herkunfts-Fixture (#1373 AC-6) und Paritaets-Fixture beschreiben nicht "
    "dieselben 25 Keys"
)


class TestCompareMetricCatalogEndpoint:
    """AC-1/AC-2/AC-3: GET /api/compare/metrics liefert 26 Eintraege mit Editor-Feldern,
    bitgleich zu compareMetricDefs.ts::ALL_METRICS + #1351-Ergaenzung."""

    def test_endpoint_returns_200(self, client: TestClient) -> None:
        """AC-1: Given der Python-Core / When GET /api/compare/metrics / Then HTTP 200
        (heute ROT: Route fehlt -> 404)."""
        response = client.get("/api/compare/metrics")
        assert response.status_code == 200

    def test_endpoint_returns_exactly_26_metrics(self, client: TestClient) -> None:
        """AC-1 (#1351: +wind_chill_max_c): genau 26 Eintraege unter dem Schluessel 'metrics'."""
        response = client.get("/api/compare/metrics")
        data = response.json()
        assert "metrics" in data
        assert len(data["metrics"]) == 25

    def test_each_entry_has_fields_matching_its_kind(self, client: TestClient) -> None:
        """AC-2: jeder Eintrag traegt key/label/unit/decimals/higherIsBetter/kind plus
        die kind-spezifischen Felder (range -> rangeMin/rangeMax/step, enum ->
        enumValues, ordinal -> ordinalLabels)."""
        response = client.get("/api/compare/metrics")
        data = response.json()
        metrics = data["metrics"]

        required_base = {"key", "label", "unit", "decimals", "higherIsBetter", "kind"}
        for entry in metrics:
            missing = required_base - entry.keys()
            assert not missing, f"{entry.get('key')}: fehlende Basisfelder {missing}"

            if entry["kind"] == "range":
                for field in ("rangeMin", "rangeMax", "step"):
                    assert field in entry, f"{entry['key']}: fehlt {field} (kind=range)"
            elif entry["kind"] == "enum":
                assert "enumValues" in entry, f"{entry['key']}: fehlt enumValues"
            elif entry["kind"] == "ordinal":
                assert "ordinalLabels" in entry, f"{entry['key']}: fehlt ordinalLabels"
            else:
                pytest.fail(f"{entry['key']}: unbekannter kind {entry['kind']!r}")

    def test_thunder_level_max_is_ordinal_with_four_labels(self, client: TestClient) -> None:
        """AC-2 (Sonderfall): thunder_level_max ist 'ordinal' mit den vier sichtbaren
        Editor-Labels. Urspruenglich drei Labels (PO-Entscheidung 2026-07-12);
        seit Issue #1474 (S3 zu #1419) vier Stufen — LOW 'leicht' besetzt den
        vorher unerreichbaren Render-Platz L, und der Frontend-Schieberegler
        leitet seinen Bereich aus len(ordinalLabels) ab."""
        response = client.get("/api/compare/metrics")
        metrics = {m["key"]: m for m in response.json()["metrics"]}
        thunder = metrics["thunder_level_max"]
        assert thunder["kind"] == "ordinal"
        assert thunder["ordinalLabels"] == ["kein", "leicht", "mittel", "hoch"]

    def test_precip_type_dominant_stays_enum(self, client: TestClient) -> None:
        """AC-2 (Sonderfall): precip_type_dominant bleibt 'enum' mit den vier
        Enum-Werten (keine abweichende Editor-Darstellung wie bei Gewitter)."""
        response = client.get("/api/compare/metrics")
        metrics = {m["key"]: m for m in response.json()["metrics"]}
        precip_type = metrics["precip_type_dominant"]
        assert precip_type["kind"] == "enum"
        assert precip_type["enumValues"] == ["RAIN", "SNOW", "MIXED", "FREEZING_RAIN"]

    def test_matches_frozen_frontend_parity_fixture(self, client: TestClient) -> None:
        """AC-3 (KERN): die 25 Eintraege stimmen bitgleich (Key, Label,
        higherIsBetter, kind, rangeMin/rangeMax) mit dem eingefrorenen
        compareMetricDefs.ts::ALL_METRICS-Fixture ueberein."""
        response = client.get("/api/compare/metrics")
        metrics = response.json()["metrics"]

        actual_keys = [m["key"] for m in metrics]
        expected_keys = [m["key"] for m in EXPECTED_METRICS]
        assert actual_keys == expected_keys, (
            "Key-Menge/Reihenfolge weicht vom Frontend-Fixture ab"
        )

        by_key = {m["key"]: m for m in metrics}
        for expected in EXPECTED_METRICS:
            actual = by_key[expected["key"]]
            for field in ("label", "higherIsBetter", "kind", "rangeMin", "rangeMax"):
                assert actual.get(field) == expected[field], (
                    f"{expected['key']}.{field}: erwartet {expected[field]!r}, "
                    f"erhalten {actual.get(field)!r}"
                )

    def test_each_entry_has_alarm_capable_flag(self, client: TestClient) -> None:
        """AC-3 (Teil 3, #1350): jeder Eintrag traegt `alarmCapable: bool` -- heute
        ROT, das Feld fehlt noch (D1 Hybrid, compare_metric_ssot_final.md).
        RED-Erwartung: Zugriff via `entry["alarmCapable"]` (nicht `.get()`) macht den
        Fehlschlag explizit als KeyError statt eines stillen `assert None == ...`."""
        response = client.get("/api/compare/metrics")
        metrics = response.json()["metrics"]
        for entry in metrics:
            assert "alarmCapable" in entry, f"{entry['key']}: fehlt alarmCapable"
            assert isinstance(entry["alarmCapable"], bool), (
                f"{entry['key']}: alarmCapable muss bool sein, ist {entry['alarmCapable']!r}"
            )

    def test_alarm_capable_true_for_exactly_the_nine_alarm_keys(self, client: TestClient) -> None:
        """AC-3 (Teil 3, KERN): `alarmCapable=True` fuer genau die Keys aus
        compare_alert.py::_SUMMARY_KEY_TO_CATALOG_ID, sonst False.

        Issue #1585: `cape_max_jkg` faellt heraus -- die Zeile wird nicht mehr
        ausgeliefert, also kann sie hier auch keine Alarmfaehigkeit tragen.
        Der CAPE-Delta-Alarm (#1592) ist davon unberuehrt, er ist ein eigener
        Alarmtyp und haengt nicht am Compare-Katalog."""
        expected_alarm_keys = {
            "temp_max_c", "temp_min_c", "wind_max_kmh", "gust_max_kmh",
            "precip_sum_mm", "thunder_level_max", "visibility_min_m",
            "snow_new_sum_cm", "freezing_level_m",
        }
        response = client.get("/api/compare/metrics")
        metrics = response.json()["metrics"]

        actual_alarm_keys = {m["key"] for m in metrics if m.get("alarmCapable") is True}
        assert actual_alarm_keys == expected_alarm_keys, (
            "alarmCapable=True weicht von den 10 Alarm-Keys ab: "
            f"fehlend {expected_alarm_keys - actual_alarm_keys}, "
            f"zusaetzlich {actual_alarm_keys - expected_alarm_keys}"
        )

        for m in metrics:
            expected = m["key"] in expected_alarm_keys
            assert m.get("alarmCapable") is expected, (
                f"{m['key']}: alarmCapable erwartet {expected}, erhalten {m.get('alarmCapable')!r}"
            )


class TestCompareMetricOrigin:
    """#1373 AC-6: jeder Eintrag nennt neben dem bisherigen Kurznamen (`key`)
    auch die zugehoerige zentrale Wettergroesse (`metric_id`) und die
    Auswertung (`aggregation`) als eigene, auslesbare Angaben.

    Heute ROT -- beide Felder gibt es noch nicht.
    """

    def test_each_entry_has_metric_id_and_aggregation(self, client: TestClient) -> None:
        """AC-6: alle 26 Eintraege tragen `metric_id` und `aggregation` als
        nicht-leere Strings. `key` bleibt zusaetzlich erhalten
        (Rueckwaertskompatibilitaet -- das Frontend waehlt weiterhin ueber
        `key` aus, Scheibe B)."""
        response = client.get("/api/compare/metrics")
        metrics = response.json()["metrics"]
        assert len(metrics) == 25

        for entry in metrics:
            assert "key" in entry and entry["key"], "Eintrag ohne `key`"
            for field in ("metric_id", "aggregation"):
                assert field in entry, f"{entry['key']}: fehlt {field}"
                assert isinstance(entry[field], str) and entry[field], (
                    f"{entry['key']}.{field} muss ein nicht-leerer String sein, "
                    f"ist {entry[field]!r}"
                )

    def test_metric_id_exists_in_central_catalog(self, client: TestClient) -> None:
        """AC-6: `metric_id` verweist auf eine tatsaechlich waehlbare Groesse
        des zentralen Wetterkatalogs -- keine frei erfundene Kennung."""
        response = client.get("/api/compare/metrics")
        metrics = response.json()["metrics"]
        central_ids = {m.id for m in get_all_metrics()}

        unknown = sorted(
            (e["key"], e.get("metric_id"))
            for e in metrics
            if e.get("metric_id") not in central_ids
        )
        assert not unknown, (
            f"Eintraege mit unbekannter/fehlender zentraler Groesse: {unknown} "
            f"(bekannt: {sorted(central_ids)})"
        )

    def test_metric_id_and_aggregation_are_plausible(self, client: TestClient) -> None:
        """AC-6 (KERN): Herkunft je Eintrag stimmt mit dem zentralen Katalog
        ueberein -- z. B. `temp_max_c` -> metric_id="temperature",
        aggregation="max"; `temp_min_c` -> "temperature"/"min".

        Fuer `snowfall_limit_m` ist die Auswertung aus den Katalogdaten nicht
        eindeutig ableitbar (leeres `summary_fields`, zwei
        `default_aggregations`) -- dort wird nur geprueft, dass die gewaehlte
        Auswertung eine der zentral definierten ist.
        """
        response = client.get("/api/compare/metrics")
        metrics = response.json()["metrics"]
        central = {m.id: m for m in get_all_metrics()}

        for entry in metrics:
            key = entry["key"]
            expected_metric_id, expected_aggregation = EXPECTED_METRIC_ORIGIN[key]
            assert entry.get("metric_id") == expected_metric_id, (
                f"{key}.metric_id: erwartet {expected_metric_id!r}, "
                f"erhalten {entry.get('metric_id')!r}"
            )
            if expected_aggregation is not None:
                assert entry.get("aggregation") == expected_aggregation, (
                    f"{key}.aggregation: erwartet {expected_aggregation!r}, "
                    f"erhalten {entry.get('aggregation')!r}"
                )
            else:
                allowed = central[expected_metric_id].default_aggregations
                assert entry.get("aggregation") in allowed, (
                    f"{key}.aggregation: {entry.get('aggregation')!r} ist keine "
                    f"der zentral definierten Auswertungen {allowed}"
                )

    def test_split_metrics_share_metric_id_but_differ_in_aggregation(
        self, client: TestClient
    ) -> None:
        """AC-6 + AC-2 zusammen: die beiden Aufspaltungen (Temperatur,
        Gefuehlte Temperatur) bleiben getrennte Eintraege, teilen sich aber
        dieselbe zentrale Groesse und unterscheiden sich genau in der
        Auswertung. Das ist der Nachweis, dass `metric_id`/`aggregation` die
        Aufspaltung korrekt beschreiben -- Voraussetzung fuer Scheibe B."""
        response = client.get("/api/compare/metrics")
        by_key = {m["key"]: m for m in response.json()["metrics"]}

        for max_key, min_key, metric_id in (
            ("temp_max_c", "temp_min_c", "temperature"),
            ("wind_chill_max_c", "wind_chill_min_c", "wind_chill"),
        ):
            hi, lo = by_key[max_key], by_key[min_key]
            assert hi.get("metric_id") == metric_id, (
                f"{max_key}.metric_id: erwartet {metric_id!r}, erhalten {hi.get('metric_id')!r}"
            )
            assert lo.get("metric_id") == metric_id, (
                f"{min_key}.metric_id: erwartet {metric_id!r}, erhalten {lo.get('metric_id')!r}"
            )
            assert hi.get("aggregation") == "max"
            assert lo.get("aggregation") == "min"
            assert hi["key"] != lo["key"], (
                f"{max_key}/{min_key} sind zu einem Eintrag zusammengefallen"
            )


# ---------------------------------------------------------------------------
# TDD RED -- #1401 Scheibe A1 (AC-2, AC-4): der Anzeigename kommt aus dem
# zentralen Register (`metric_catalog.label_de`) statt getippt im Compare-
# Katalog zu stehen; die Auswertung wird ein eigenes Feld `aggregation_label`.
# SPEC: docs/specs/modules/fix_1401_a1_namensregister.md
# ---------------------------------------------------------------------------

EXPECTED_AGGREGATION_LABELS = {"max": "Maximum", "min": "Minimum",
                               "avg": "Mittel", "sum": "Summe"}


class TestCompareMetricLabelsComeFromCentralRegister:
    """#1401 AC-2: derselbe Name wie im Trip-Editor, Auswertung daneben."""

    def test_label_equals_central_register_label_de(self, client: TestClient) -> None:
        """AC-2 (KERN): `label` ist fuer jeden der 26 Eintraege exakt der Name
        der zentralen Wettergroesse -- heute ROT, der Compare-Katalog tippt
        seine Namen selbst ("Temperatur max", "Windspitzen", "Wolken tief")."""
        metrics = client.get("/api/compare/metrics").json()["metrics"]
        assert len(metrics) == 25
        abweichungen = [
            (e["key"], e.get("label"), get_metric(e["metric_id"]).label_de)
            for e in metrics
            if e.get("label") != get_metric(e["metric_id"]).label_de
        ]
        assert not abweichungen, (
            "Name nicht aus dem zentralen Register abgeleitet "
            f"(key, geliefert, Register): {abweichungen}"
        )

    def test_label_carries_no_aggregation_marker(self, client: TestClient) -> None:
        """AC-2: der Name enthaelt die Auswertung nicht mehr -- weder als
        Suffix ("Sichtweite min") noch als Mittelwert-Zeichen ("Bewölkung Ø")
        noch als deutsches Auswertungswort."""
        marker = (" max", " min", " Ø", " avg", " sum",
                  " Maximum", " Minimum", " Mittel", " Summe")
        metrics = client.get("/api/compare/metrics").json()["metrics"]
        treffer = [(e["key"], e["label"]) for e in metrics
                   if str(e.get("label", "")).endswith(marker)]
        assert not treffer, f"Auswertung steckt noch im Namen: {treffer}"

    def test_each_entry_has_aggregation_label(self, client: TestClient) -> None:
        """AC-2b (KERN): jeder der 26 Eintraege traegt `aggregation_label` und
        bildet die Auswertung korrekt ab (max->Maximum, min->Minimum,
        avg->Mittel, sum->Summe)."""
        metrics = client.get("/api/compare/metrics").json()["metrics"]
        assert len(metrics) == 25
        fehlend = [e["key"] for e in metrics if "aggregation_label" not in e]
        assert not fehlend, (
            f"Eintraege ohne `aggregation_label`: {fehlend} -- die Auswertung "
            "ist in der Auswahlliste nicht als eigenes Element anzeigbar"
        )
        falsch = [(e["key"], e["aggregation"], e["aggregation_label"]) for e in metrics
                  if e["aggregation_label"] != EXPECTED_AGGREGATION_LABELS.get(e["aggregation"])]
        assert not falsch, f"aggregation_label falsch (key, aggregation, ist): {falsch}"

    def test_split_metrics_share_label_but_stay_distinguishable(
        self, client: TestClient
    ) -> None:
        """AC-2 (KERN, Nutzersicht): die beiden Aufspaltungen tragen denselben
        Namen, bleiben aber einzeln waehl- und unterscheidbar -- verschiedene
        Auswahl-Schluessel UND verschiedenes, sichtbares `aggregation_label`."""
        by_key = {m["key"]: m for m in client.get("/api/compare/metrics").json()["metrics"]}
        for max_key, min_key in (("temp_max_c", "temp_min_c"),
                                 ("wind_chill_max_c", "wind_chill_min_c")):
            hi, lo = by_key[max_key], by_key[min_key]
            assert hi["label"] == lo["label"], (
                f"{max_key}/{min_key} tragen verschiedene Namen: "
                f"{hi['label']!r} vs. {lo['label']!r}"
            )
            assert hi["key"] != lo["key"], f"{max_key}/{min_key} sind zusammengefallen"
            assert (hi.get("aggregation_label"), lo.get("aggregation_label")) == (
                "Maximum", "Minimum"), (
                f"{max_key}/{min_key} waeren in der Liste ununterscheidbar: "
                f"{hi.get('aggregation_label')!r} / {lo.get('aggregation_label')!r}"
            )


class TestUnknownMetricIdFailsVisibly:
    """#1401 AC-4: kein stilles Verwerfen, wenn die Verbindung ins zentrale
    Register bricht."""

    def test_unknown_metric_id_fails_visibly(self) -> None:
        """AC-4 (KERN): eine Katalogzeile mit zentral unbekannter `metric_id`
        laesst den Katalogaufruf sichtbar scheitern -- mit der fehlenden
        Kennung im Fehlertext -- statt eine leere oder erfundene Bezeichnung zu
        liefern. Injizierte Testkopie (Vorbild:
        `duplicate_metric_aggregation_pairs(entries=...)`), KEIN Monkeypatch
        des echten Katalogs, kein Mock."""
        kaputte_kopie = [
            dict(COMPARE_METRIC_CATALOG[0]),
            {**dict(COMPARE_METRIC_CATALOG[1]), "key": "erfundene_groesse_x",
             "metric_id": "gibt_es_zentral_nicht"},
        ]
        with pytest.raises(Exception) as exc_info:
            get_compare_metric_catalog(entries=kaputte_kopie)
        assert not isinstance(exc_info.value, TypeError), (
            "get_compare_metric_catalog() nimmt noch keinen `entries`-Parameter -- der "
            f"Pfad 'unbekannte metric_id' ist nur per Monkeypatch pruefbar ({exc_info.value})"
        )
        assert "gibt_es_zentral_nicht" in str(exc_info.value), (
            f"Der Fehler nennt die fehlende Kennung nicht: {exc_info.value!r}"
        )

    def test_real_catalog_resolves_completely(self) -> None:
        """AC-4 (Gegenprobe): der echte Katalog laeuft ohne Ausnahme durch."""
        assert len(get_compare_metric_catalog()) == 25


def test_the_eight_approved_names() -> None:
    """#1401: die mit der Spec freigegebenen Namensentscheidungen, gegen das
    echte zentrale Register (acht Spec-Zeilen = sieben Groessen, `wind_chill`
    steht dort zweimal). Heute ROT bei `sunshine` ("Sonnenschein"); die
    uebrigen sind hier festgehalten, damit sie nicht still zurueckdriften."""
    freigegeben = {
        "wind": "Wind", "sunshine": "Sonnenstunden",
        "cape": "Gewitterenergie (CAPE)", "wind_chill": "Gefühlte Temperatur",
        "cloud_low": "Tiefe Wolken", "cloud_mid": "Mittelhohe Wolken",
        "cloud_high": "Hohe Wolken",
    }
    abweichungen = {mid: (get_metric(mid).label_de, soll)
                    for mid, soll in freigegeben.items()
                    if get_metric(mid).label_de != soll}
    assert not abweichungen, (
        f"Register weicht von den freigegebenen Namen ab (id: (ist, soll)): {abweichungen}"
    )
