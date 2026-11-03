"""Begruendung „stuendlich nicht waehlbar" im Ortsvergleich folgt der Sprache (#2751).

SPEC: docs/specs/modules/i18n_p12_python_ratsche_rest_2751.md AC-1, AC-2, AC-3.

Kern-Schicht: echter Katalog, echter FastAPI-Router per TestClient, kein Netz,
keine Mocks. Der deutsche Referenztext ist der bisherige Wortlaut (byte-gleich).
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from output.renderers.compare_hourly_metric_ids import (
    HOURLY_EXCLUDED_METRIC_IDS, HOURLY_EXCLUSION_REASON, hourly_exclusion_reason,
)
from output.renderers.compare_metric_catalog import get_compare_metric_catalog

_SONNE_DE = (
    "Stuendlich nur als Einstrahlung (W/m²) verfuegbar, nicht als "
    "Sonnenstunden — die Bewölkung und der UV-Index beantworten dieselbe "
    "Frage stundengenau."
)
_TAG_TIEF_DE = (
    "Tagesrichtung der Gehzeit-Spanne (#1728), kein Stundenwert — "
    "stuendlich beantwortet die gefuehlte Temperatur dieselbe Frage."
)
_UMLAUTE = set("äöüÄÖÜß")


@pytest.fixture
def client() -> TestClient:
    from api.routers import compare

    app = FastAPI()
    app.include_router(compare.router)
    return TestClient(app)


def _gruende(eintraege: list[dict]) -> dict[str, str]:
    return {e["metric_id"]: e["hourlyNotSelectableReason"] for e in eintraege
            if e["metric_id"] in HOURLY_EXCLUDED_METRIC_IDS}


def test_ac1_deutsch_byte_gleich_ohne_und_mit_lang():
    ohne = get_compare_metric_catalog()
    assert ohne == get_compare_metric_catalog(lang="de")
    assert _gruende(ohne)["sunshine"] == _SONNE_DE
    assert HOURLY_EXCLUSION_REASON["sunshine"] == _SONNE_DE
    assert HOURLY_EXCLUSION_REASON["wind_chill_day_low"] == _TAG_TIEF_DE
    assert "die Temperatur dieselbe" in HOURLY_EXCLUSION_REASON["temperature_day_high"]
    for metric_id, text in HOURLY_EXCLUSION_REASON.items():
        assert hourly_exclusion_reason(metric_id) == text, metric_id
        assert hourly_exclusion_reason(metric_id, "de") == text, metric_id
    assert hourly_exclusion_reason("temperature") == ""


def test_ac2_englisch_je_ausgeschlossener_groesse():
    assert set(HOURLY_EXCLUSION_REASON) == set(HOURLY_EXCLUDED_METRIC_IDS)
    for metric_id, text_de in HOURLY_EXCLUSION_REASON.items():
        text = hourly_exclusion_reason(metric_id, "en")
        assert text and text != text_de, metric_id
        assert not _UMLAUTE & set(text), (metric_id, text)
    assert "feels-like temperature" in hourly_exclusion_reason("wind_chill_day_low", "en")
    assert "feels-like" not in hourly_exclusion_reason("temperature_day_low", "en")
    assert hourly_exclusion_reason("temperature", "en") == ""


def test_ac2_katalog_englisch_und_sonst_identisch():
    de = get_compare_metric_catalog(lang="de")
    en = get_compare_metric_catalog(lang="en")
    gruende_de, gruende_en = _gruende(de), _gruende(en)
    assert gruende_en, "keine stuendlich ausgeschlossene Groesse im Katalog"
    for metric_id, text in gruende_en.items():
        assert text == hourly_exclusion_reason(metric_id, "en") != gruende_de[metric_id]
    ohne_grund = [{k: v for k, v in e.items() if k != "hourlyNotSelectableReason"}
                  for e in de]
    assert ohne_grund == [{k: v for k, v in e.items() if k != "hourlyNotSelectableReason"}
                          for e in en]


def test_ac2_endpunkt_liefert_englisch(client):
    antwort = client.get("/api/compare/metrics", params={"lang": "en"})
    assert antwort.status_code == 200
    assert antwort.json() == {"metrics": get_compare_metric_catalog(lang="en")}
    assert _gruende(antwort.json()["metrics"])["sunshine"].startswith("Hourly")


@pytest.mark.parametrize("params", [{}, {"lang": "fr"}, {"lang": ""}, {"lang": "de"}])
def test_ac3_endpunkt_ohne_oder_mit_unbekannter_sprache_deutsch(client, params):
    antwort = client.get("/api/compare/metrics", params=params)
    assert antwort.status_code == 200
    assert antwort.json() == {"metrics": get_compare_metric_catalog()}
    assert _gruende(antwort.json()["metrics"])["sunshine"] == _SONNE_DE
