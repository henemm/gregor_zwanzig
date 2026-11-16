"""TDD RED — Issue #2955 (gebündelt mit #3012): Reiter Wetter, Metrik-Inhalte an Mockup Fassung 3.

Spec: docs/specs/modules/wetter_metrik_inhalte.md (AC-1, AC-1b, AC-3, AC-3b, AC-4, AC-7).

Kern-Schicht, deterministisch, ohne Netz, ohne Mock: echter Router ``api.routers.config`` in
einer FastAPI-App über den TestClient (so reicht die Go-API ``/api/metrics`` an den Python-Kern
weiter), echte Katalogdaten aus ``app.metric_catalog``, echte Alarm-Fabriken aus
``services.weather_change_detection`` und echter Mail-Beschrifter ``derive_row_labels``.

RED heute:
  * wind_chill, cloud_total, dewpoint, pressure tragen ``is_precursor=False`` (AC-1).
  * ``/api/metrics`` liefert kein Feld ``rang`` (AC-3, AC-7).
  * ``label_de`` lautet noch „Nacht-Tiefsttemperatur“, „Gefühlte Nacht-Tiefsttemperatur“,
    „Luftfeuchtigkeit“ (AC-4).
Regressionsschutz (heute grün, muss grün bleiben): Alarm-Erzeugung (AC-1b), Mail-/SMS-Spalten-
reihenfolge ``_METRICS`` und Vorlagen-Zeilen ``ampel_templates._ZEILEN`` (AC-3), EN-Namen,
SMS-Codes, Alarm-Kurzlabel (AC-4).

    uv run pytest tests/tdd/test_2955_wetter_metrik_inhalte.py -v
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers import config
from app.metric_catalog import _METRICS, get_change_detection_map, get_metric

# ── Soll aus Mockup Fassung 3 (docs/context/einstellungen_neu/seiten/mockup-hub-fassung3.html,
#    TRIP_METRICS Z. 279ff „Alpen-Trekking“, ORTE_METRICS „Allgemein“) ──────────────────────────
MOCKUP_TRIP = [
    "temperature", "temperature_night", "wind_chill",
    "wind", "gust", "wind_direction",
    "precipitation", "thunder", "rain_probability",
    "visibility", "cloud_low", "uv_index",
    "freezing_level", "snowfall_limit",
]
MOCKUP_ORTE = [
    "temperature",
    "wind", "gust", "wind_direction",
    "precipitation", "thunder", "rain_probability",
    "cloud_total", "sunshine",
]

# ADR-0010: Vorboten.
VORBOTEN = ("humidity", "dewpoint", "rain_probability", "cloud_total", "pressure", "wind_chill")


def _metriken(headers: dict | None = None) -> dict[str, dict]:
    app = FastAPI()
    app.include_router(config.router)
    res = TestClient(app).get("/metrics", headers=headers or {})
    assert res.status_code == 200, res.text
    return {m["id"]: m for gruppe in res.json().values() for m in gruppe}


@pytest.fixture(scope="module")
def metriken() -> dict[str, dict]:
    return _metriken()


# ── AC-1: Vorbote-Kennzeichnung aus EINER Quelle (Katalog) ───────────────────────────────────

@pytest.mark.parametrize("mid", VORBOTEN)
def test_ac1_alle_adr0010_vorboten_sind_im_reiter_vorbote(metriken, mid):
    m = metriken[mid]
    assert m["is_precursor"] is True, f"{mid}: Reiter zeigt keinen Vorboten (is_precursor={m['is_precursor']})"
    assert m["alertable"] is False, f"{mid}: Vorbote darf nicht alarmfähig sein"
    assert get_metric(mid).is_precursor is True, f"{mid}: Katalogflag fehlt (eine Quelle, kein Reiter-Flag)"


@pytest.mark.parametrize("mid", ["cloud_low", "thunder", "temperature", "gust"])
def test_ac1_gipfel_in_wolken_und_alarmmetriken_sind_kein_vorbote(metriken, mid):
    assert metriken[mid]["is_precursor"] is False, f"{mid} darf kein Vorbote sein (Mockup)"


# ── AC-1b: Alarm-Erzeugung bleibt unverändert (Regressionsschutz) ────────────────────────────

# Stand vor #2955 (16.11.2026 abgelesen): Änderungs-Schwellen der Alarm-Erzeugung.
CHANGE_MAP_VORHER = {
    "temp_min_c": 5.0, "temp_max_c": 5.0, "temp_avg_c": 5.0, "wind_max_kmh": 20.0,
    "gust_max_kmh": 20.0, "precip_sum_mm": 10.0, "thunder_level_max": 1.0,
    "snowfall_limit_m": 200.0, "visibility_min_m": 1000, "uv_index_max": 3.0,
    "freezing_level_m": 200, "snow_depth_cm": 10.0, "snow_new_sum_cm": 5.0,
}
DISPLAY_CONFIG_VORHER = {**CHANGE_MAP_VORHER, "cape_max_jkg": 500.0}


def test_ac1b_change_detection_map_unveraendert():
    assert get_change_detection_map() == CHANGE_MAP_VORHER


def test_ac1b_alarme_aus_display_config_mit_allen_vorboten_unveraendert():
    """Nutzer hat alle Metriken (inkl. Gefühlter Temperatur, Taupunkt, Bewölkung, Luftdruck)
    eingeschaltet: die Alarm-Schwellen sind dieselben wie vor der Vorbote-Kennzeichnung."""
    from app.models import MetricConfig, UnifiedWeatherDisplayConfig
    from services.weather_change_detection import WeatherChangeDetectionService

    cfg = UnifiedWeatherDisplayConfig(metrics=[MetricConfig(metric_id=m.id) for m in _METRICS])
    svc = WeatherChangeDetectionService.from_display_config(cfg)
    assert svc._thresholds == DISPLAY_CONFIG_VORHER


# ── AC-3 / AC-3b: Reihenfolge im Reiter über `rang` aus /api/metrics ─────────────────────────

def test_ac3_jede_metrik_traegt_einen_eindeutigen_rang(metriken):
    ohne = sorted(mid for mid, m in metriken.items() if not isinstance(m.get("rang"), int))
    assert ohne == [], f"/api/metrics liefert keinen ganzzahligen rang für: {ohne}"
    raenge = [m["rang"] for m in metriken.values()]
    assert len(raenge) == len(set(raenge)), "rang ist nicht eindeutig"


def test_ac3_gewitter_steht_vor_regenwahrscheinlichkeit(metriken):
    assert metriken["thunder"].get("rang", 10**6) < metriken["rain_probability"].get("rang", -1), \
        "Gewitter muss im Reiter vor Regenwahrscheinlichkeit stehen (Mockup)"


@pytest.mark.parametrize("name, mockup", [("Trip Alpen-Trekking", MOCKUP_TRIP), ("Orte Allgemein", MOCKUP_ORTE)])
def test_ac3_rang_folgt_der_mockup_reihenfolge_je_gruppe(metriken, name, mockup):
    for gruppe in {metriken[mid]["group"] for mid in mockup}:
        soll = [mid for mid in mockup if metriken[mid]["group"] == gruppe]
        ist = sorted(soll, key=lambda mid: metriken[mid]["rang"])
        assert ist == soll, f"{name}, Gruppe {gruppe}: Rang-Folge {ist} ≠ Mockup {soll}"


# Stand vor #2955: Mail-/SMS-Spalten folgen _METRICS, Vorlagen-Zeilen folgen _ZEILEN.
METRICS_VORHER = [
    "temperature", "temperature_cold", "temperature_night", "temperature_day_low",
    "temperature_day_high", "wind_chill", "wind_chill_night", "wind_chill_day_low",
    "wind_chill_day_high", "humidity", "dewpoint", "wind", "gust", "wind_direction",
    "precipitation", "rain_probability", "confidence", "thunder", "cape", "snowfall_limit",
    "precip_type", "cloud_total", "cloud_low", "cloud_mid", "cloud_high", "visibility",
    "sunshine", "uv_index", "pressure", "freezing_level", "snow_depth", "fresh_snow",
]
ZEILEN_VORHER = [
    "temperature", "temperature_night", "wind_chill", "dewpoint", "humidity", "wind", "gust",
    "wind_direction", "precipitation", "rain_probability", "thunder", "visibility", "cloud_total",
    "cloud_low", "sunshine", "uv_index", "freezing_level", "snowfall_limit", "fresh_snow", "snow_depth",
]


def test_ac3_mail_und_sms_spaltenreihenfolge_bleibt():
    assert [m.id for m in _METRICS] == METRICS_VORHER


def test_ac3_vorlagen_zeilen_bleiben():
    from app.ampel_templates import _ZEILEN
    for tid, zeilen in _ZEILEN.items():
        assert [z[0] for z in zeilen] == ZEILEN_VORHER, f"Vorlage {tid}: Zeilenfolge geändert"


# ── AC-4: ein Name überall (Katalog → Reiter, Wertebereiche, Alarme, Mail) ───────────────────

NEUE_NAMEN = {
    "temperature_night": "Tiefsttemperatur Nacht",
    "wind_chill_night": "Gefühlte Tiefsttemperatur Nacht",
    "humidity": "Luftfeuchte",
}
# Stand vor #2955: bleibt unverändert.
UNVERAENDERT = {
    "temperature_night": ("Night low", "", ""),
    "wind_chill_night": ("Feels-like night low", "FN", ""),
    "humidity": ("Humidity", "HU", "Feuchte"),
}


@pytest.mark.parametrize("mid, soll", NEUE_NAMEN.items())
def test_ac4_deutscher_name_im_katalog_und_api(metriken, mid, soll):
    assert get_metric(mid).label_de == soll
    assert metriken[mid]["label_de"] == soll
    assert metriken[mid]["label"] == soll


@pytest.mark.parametrize("mid, alt", UNVERAENDERT.items())
def test_ac4_englischer_name_sms_code_alarm_kurzlabel_bleiben(mid, alt):
    m = get_metric(mid)
    assert (m.label_en, m.sms_code, m.alert_label) == alt


@pytest.mark.parametrize("mid, soll", NEUE_NAMEN.items())
def test_ac4_mail_uebersicht_zeigt_den_neuen_namen(mid, soll):
    from output.renderers.email.compare_html import derive_row_labels

    zeilen = [{"key": mid, "metric_id": mid}]
    assert derive_row_labels(zeilen, form="long", lang="de")[0]["label"] == soll
    assert derive_row_labels(zeilen, form="long", lang="en")[0]["label"] == UNVERAENDERT[mid][0]


# ── AC-7: /api/metrics ist nutzerunabhängig ──────────────────────────────────────────────────

def test_ac7_zwei_nutzer_erhalten_dieselben_katalogdaten_mit_rang():
    a = _metriken({"X-User-Id": "nutzer-a-2955"})
    b = _metriken({"X-User-Id": "nutzer-b-2955"})
    assert a == b
    assert all(isinstance(m.get("rang"), int) for m in a.values()), "rang fehlt in der Antwort"
    roh = repr(a)
    for fremd in ("nutzer-a-2955", "nutzer-b-2955", "user_id", "'default'"):
        assert fremd not in roh, f"Antwort enthält Nutzerbezug {fremd!r}"


# ── AC-4 (Fix-Loop F001): Namenskopien in Kanal-Katalogen an der Wirkstelle ─────────────────

def test_ac4_telegram_vergleichszeile_nennt_luftfeuchte_wie_der_katalog():
    """Telegram-Vergleich (``vergleich.zeile.humidity_avg``) zeigt den Katalognamen + „ Ø“."""
    from output.renderers.comparison import render_compare_telegram
    from tests.helpers.vergleichs_mail_fixture import build_result

    soll = f"{get_metric('humidity').label_de} Ø"
    text = render_compare_telegram(build_result(), enabled_metrics=["humidity_avg"], lang="de")
    zeilen = [z.strip() for z in text.splitlines() if z.strip().startswith(soll + " ")]
    assert zeilen, f"keine Telegram-Zeile beginnt mit „{soll}“:\n{text}"
    assert "Luftfeuchtigkeit" not in text


def test_ac4_ersatzquellen_hinweis_nennt_luftfeuchte_wie_der_katalog():
    """Mail-Hinweis zur Ersatzquelle (``mail.fallback.metrik.relative_humidity_2m``) nennt den Katalognamen."""
    from app.models import ForecastMeta, Provider
    from output.renderers.fallback_notice import build_fallback_lines

    meta = ForecastMeta(provider=Provider.OPENMETEO, model="icon_d2", grid_res_km=2.0,
                        fallback_model="icon_eu", fallback_metrics=["relative_humidity_2m"],
                        fallback_reason="metric_gap")
    zeilen = build_fallback_lines(meta, lang="de")
    assert any(z.endswith(f"({get_metric('humidity').label_de})") for z in zeilen), zeilen
