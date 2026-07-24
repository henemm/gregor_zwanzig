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
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app


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
EXPECTED_METRICS: list[dict] = [
    {"key": "snow_depth_cm", "label": "Schneehöhe", "higherIsBetter": True,
     "kind": "range", "rangeMin": 0, "rangeMax": 200},
    {"key": "snow_new_sum_cm", "label": "Neuschnee", "higherIsBetter": True,
     "kind": "range", "rangeMin": 0, "rangeMax": 50},
    {"key": "sunny_hours_h", "label": "Sonnenstunden", "higherIsBetter": True,
     "kind": "range", "rangeMin": 0, "rangeMax": 12},
    {"key": "wind_max_kmh", "label": "Windspitzen", "higherIsBetter": False,
     "kind": "range", "rangeMin": 0, "rangeMax": 100},
    {"key": "cloud_avg_pct", "label": "Bewölkung Ø", "higherIsBetter": False,
     "kind": "range", "rangeMin": 0, "rangeMax": 100},
    {"key": "visibility_min_m", "label": "Sichtweite min", "higherIsBetter": True,
     "kind": "range", "rangeMin": 0, "rangeMax": 10000},
    {"key": "precip_sum_mm", "label": "Niederschlag", "higherIsBetter": False,
     "kind": "range", "rangeMin": 0, "rangeMax": 30},
    {"key": "uv_index_max", "label": "UV-Index max", "higherIsBetter": False,
     "kind": "range", "rangeMin": 0, "rangeMax": 12},
    {"key": "temp_max_c", "label": "Temperatur max", "higherIsBetter": True,
     "kind": "range", "rangeMin": -20, "rangeMax": 45},
    {"key": "thunder_level_max", "label": "Gewitter", "higherIsBetter": False,
     "kind": "ordinal", "rangeMin": None, "rangeMax": None},
    {"key": "temp_min_c", "label": "Temperatur min", "higherIsBetter": True,
     "kind": "range", "rangeMin": -30, "rangeMax": 30},
    {"key": "gust_max_kmh", "label": "Böen", "higherIsBetter": False,
     "kind": "range", "rangeMin": 0, "rangeMax": 150},
    {"key": "cape_max_jkg", "label": "Gewitter-Energie (CAPE)", "higherIsBetter": False,
     "kind": "range", "rangeMin": 0, "rangeMax": 3000},
    {"key": "freezing_level_m", "label": "Nullgradgrenze", "higherIsBetter": True,
     "kind": "range", "rangeMin": 0, "rangeMax": 5000},
    {"key": "pop_max_pct", "label": "Regenwahrscheinlichkeit", "higherIsBetter": False,
     "kind": "range", "rangeMin": 0, "rangeMax": 100},
    {"key": "wind_direction_deg", "label": "Windrichtung", "higherIsBetter": False,
     "kind": "range", "rangeMin": 0, "rangeMax": 360},
    {"key": "wind_chill_min_c", "label": "Gefühlte Temp. min", "higherIsBetter": True,
     "kind": "range", "rangeMin": -30, "rangeMax": 30},
    # Issue #1351 Teil 1: 26. Eintrag, analog temp_max_c (Wertebereich).
    {"key": "wind_chill_max_c", "label": "Gefühlte Temp. max", "higherIsBetter": True,
     "kind": "range", "rangeMin": -20, "rangeMax": 45},
    {"key": "humidity_avg_pct", "label": "Luftfeuchtigkeit Ø", "higherIsBetter": False,
     "kind": "range", "rangeMin": 0, "rangeMax": 100},
    {"key": "dewpoint_avg_c", "label": "Taupunkt Ø", "higherIsBetter": False,
     "kind": "range", "rangeMin": -20, "rangeMax": 30},
    {"key": "snowfall_limit_m", "label": "Schneefallgrenze", "higherIsBetter": True,
     "kind": "range", "rangeMin": 0, "rangeMax": 5000},
    {"key": "precip_type_dominant", "label": "Niederschlagsart", "higherIsBetter": False,
     "kind": "enum", "rangeMin": None, "rangeMax": None},
    {"key": "cloud_low_avg_pct", "label": "Wolken tief", "higherIsBetter": False,
     "kind": "range", "rangeMin": 0, "rangeMax": 100},
    {"key": "cloud_mid_avg_pct", "label": "Wolken mittel", "higherIsBetter": False,
     "kind": "range", "rangeMin": 0, "rangeMax": 100},
    {"key": "cloud_high_avg_pct", "label": "Wolken hoch", "higherIsBetter": False,
     "kind": "range", "rangeMin": 0, "rangeMax": 100},
    {"key": "pressure_avg_hpa", "label": "Luftdruck Ø", "higherIsBetter": True,
     "kind": "range", "rangeMin": 950, "rangeMax": 1050},
]

assert len(EXPECTED_METRICS) == 26, "Paritaets-Fixture muss exakt 26 Eintraege haben (#1351: +wind_chill_max_c)"


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
        assert len(data["metrics"]) == 26

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

    def test_thunder_level_max_is_ordinal_with_three_labels(self, client: TestClient) -> None:
        """AC-2 (Sonderfall): thunder_level_max ist 'ordinal' mit den drei sichtbaren
        Editor-Labels (PO-Entscheidung 2026-07-12, nicht 'enum' wie im rohen
        ALL_METRICS-Eintrag)."""
        response = client.get("/api/compare/metrics")
        metrics = {m["key"]: m for m in response.json()["metrics"]}
        thunder = metrics["thunder_level_max"]
        assert thunder["kind"] == "ordinal"
        assert thunder["ordinalLabels"] == ["kein", "mittel", "hoch"]

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

    def test_alarm_capable_true_for_exactly_the_ten_alarm_keys(self, client: TestClient) -> None:
        """AC-3 (Teil 3, KERN): `alarmCapable=True` fuer genau die 10 Keys aus
        compare_alert.py::_SUMMARY_KEY_TO_CATALOG_ID, sonst False."""
        expected_alarm_keys = {
            "temp_max_c", "temp_min_c", "wind_max_kmh", "gust_max_kmh",
            "precip_sum_mm", "thunder_level_max", "visibility_min_m",
            "snow_new_sum_cm", "cape_max_jkg", "freezing_level_m",
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
