"""Issue #2989: Standardfolge der Ortsvergleich-Groessen aus dem Backend-Katalog.

Spec: docs/specs/modules/refactor_2989_compare_default_order_ssot.md (Tests 1-4,
AC-1 bis AC-3). Echter Katalog, echte ``CV2_ZEILEN``, echter Router ueber den
FastAPI-TestClient -- kein Mock, kein Netz. Die Abweichungsfaelle (Test 4)
werden ueber Parameter der Ableitungsfunktion injiziert, nicht per Patch.

Erwartete Produktions-Schnittstelle:
    output.renderers.compare_metric_catalog.default_order(zeilen=None, katalog=None) -> list[str]
      zeilen  -- Ersatz fuer CV2_ZEILEN (Default: die echten Zeilen)
      katalog -- Ersatz fuer die waehlbaren Katalog-Eintraege (Default:
                 get_compare_metric_catalog()); Eintraege tragen mindestens "key"
      wirft ValueError, wenn die abgeleitete Schluesselmenge von der Menge der
      waehlbaren Katalog-Schluessel abweicht (fail-fast wie _sort_by_cv2_order).
    GET /api/compare/metrics -> {"metrics": [...unveraendert...], "default_order": [...]}

RED heute: ``default_order`` existiert nicht, der Endpoint liefert kein
``default_order``.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from output.renderers.compare_metric_catalog import get_compare_metric_catalog, key_for
from output.renderers.email.compare_html import CV2_ZEILEN

# Regressions-Anker: Wert der bis #2989 handgepflegten Frontend-Liste
# COMPARE_METRIC_KEYS (corridorEditorState.ts). Nicht das alleinige Orakel --
# die Erwartung wird zusaetzlich aus CV2_ZEILEN + key_for abgeleitet.
BISHERIGE_FRONTEND_FOLGE = [
    "temp_max_c", "wind_max_kmh", "precip_sum_mm", "pop_max_pct", "thunder_level_max",
    "sunny_hours_h", "cloud_avg_pct", "uv_index_max", "visibility_min_m", "snow_depth_cm",
    "snow_new_sum_cm", "temp_min_c", "gust_max_kmh", "freezing_level_m",
    "wind_direction_deg", "wind_chill_min_c", "wind_chill_max_c", "cloud_low_avg_pct",
    "cloud_mid_avg_pct", "cloud_high_avg_pct", "humidity_avg_pct", "dewpoint_avg_c",
    "pressure_avg_hpa", "precip_type_dominant", "snowfall_limit_m",
]


def _default_order(**kwargs):
    from output.renderers.compare_metric_catalog import default_order

    return default_order(**kwargs)


def _erwartet_aus_cv2() -> list[str]:
    return [
        key_for(z.get("metric_id"), z.get("aggregation"))
        for z in CV2_ZEILEN
        if z["key"] != "warn"
    ]


# ── Test 1 (AC-1): Folge = CV2_ZEILEN ohne warn, in Katalog-Schluesseln ──────
def test_default_order_folgt_cv2_zeilen_ohne_warn():
    erwartet = _erwartet_aus_cv2()
    assert None not in erwartet, f"CV2-Zeile ohne Katalog-Schluessel: {erwartet}"
    folge = _default_order()
    assert folge == erwartet
    assert folge == BISHERIGE_FRONTEND_FOLGE, "Mail-Standardfolge hat sich verschoben"
    assert "warn" not in folge


# ── Test 2 (AC-1): Menge = waehlbare Katalog-Schluessel, ohne Duplikate ──────
def test_default_order_menge_gleich_waehlbarem_katalog_ohne_duplikate():
    folge = _default_order()
    katalog_keys = [e["key"] for e in get_compare_metric_catalog()]
    assert len(folge) == len(set(folge)), f"Duplikate in default_order: {folge}"
    assert set(folge) == set(katalog_keys)
    # #1585: nicht waehlbares CAPE darf nicht in der Standardfolge stehen.
    assert "cape_max_jkg" not in folge


# ── Test 3 (AC-1, AC-3): Endpoint liefert default_order, metrics unveraendert ─
@pytest.mark.parametrize("lang", ["de", "en"])
def test_endpoint_liefert_default_order_und_unveraenderte_metrics(lang):
    from api.routers import compare

    app = FastAPI()
    app.include_router(compare.router)
    antwort = TestClient(app).get(f"/api/compare/metrics?lang={lang}")
    assert antwort.status_code == 200
    daten = antwort.json()
    assert "default_order" in daten, f"Antwort ohne default_order: {sorted(daten)}"
    assert daten["default_order"] == _erwartet_aus_cv2()
    assert daten["default_order"] == BISHERIGE_FRONTEND_FOLGE
    # AC-3: metrics in Inhalt und Reihenfolge wie bisher (Katalogfolge, nicht CV2).
    assert daten["metrics"] == get_compare_metric_catalog(lang=lang)
    assert [m["key"] for m in daten["metrics"]] != daten["default_order"], (
        "metrics darf nicht in die Standardfolge umsortiert werden (Variante C verworfen)"
    )


# ── Test 4 (AC-2): fail-fast bei abweichender Menge, ueber Parameter injiziert ─
def test_default_order_bricht_ab_bei_cv2_zeile_ohne_katalog_schluessel():
    zeilen = [*CV2_ZEILEN, {"key": "fake_zeile", "metric_id": "nope", "aggregation": "max"}]
    with pytest.raises(ValueError) as exc:
        _default_order(zeilen=zeilen)
    text = str(exc.value)
    assert "fake_zeile" in text or "nope" in text, text


def test_default_order_bricht_ab_wenn_katalog_schluessel_in_cv2_fehlt():
    zeilen = [z for z in CV2_ZEILEN if z["key"] != "temp_max"]
    with pytest.raises(ValueError) as exc:
        _default_order(zeilen=zeilen)
    assert "temp_max_c" in str(exc.value)


def test_default_order_bricht_ab_bei_zusaetzlichem_katalog_schluessel():
    katalog = [*get_compare_metric_catalog(),
               {"key": "zusatz_x", "metric_id": "zusatz", "aggregation": "max"}]
    with pytest.raises(ValueError) as exc:
        _default_order(katalog=katalog)
    assert "zusatz_x" in str(exc.value)


def test_default_order_mit_injizierten_echten_quellen_gleich_default():
    """Gegenprobe zu Test 4: die Parameter selbst veraendern nichts."""
    assert _default_order(zeilen=CV2_ZEILEN, katalog=get_compare_metric_catalog()) == _default_order()
