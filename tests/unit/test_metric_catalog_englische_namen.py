"""Englische Anzeigenamen im Metrik-Register (Issue #2662 AC-4).

Soll-Werte: Namenstabelle der Spec ``i18n_p1_python_kern_metrik_2662.md``.
Deutsche Werte: vor der Aenderung aus dem Register festgehalten (byte-gleich).
"""
from __future__ import annotations

from app.metric_catalog import (
    _METRICS, aggregation_label, aggregation_label_de, get_alert_label,
)

# id -> (label_en, alert_label_en); "" = kein eigenes alert_label_en
ENGLISCH = {
    "temperature": ("Temperature", "Temp"),
    "temperature_cold": ("Low temperature alert", "Temp"),
    "temperature_night": ("Night low", ""),
    "temperature_day_low": ("Daytime low (walking hours)", ""),
    "temperature_day_high": ("Daytime high (walking hours)", ""),
    "wind_chill": ("Feels-like temperature", ""),
    "wind_chill_night": ("Feels-like night low", ""),
    "wind_chill_day_low": ("Feels-like daytime low (walking hours)", ""),
    "wind_chill_day_high": ("Feels-like daytime high (walking hours)", ""),
    "humidity": ("Humidity", "Humidity"),
    "dewpoint": ("Dew point", ""),
    "wind": ("Wind", "Wind"),
    "gust": ("Wind gusts", "Gusts"),
    "wind_direction": ("Wind direction", ""),
    "precipitation": ("Precipitation", "Precip"),
    "rain_probability": ("Rain probability", "Rain%"),
    "confidence": ("Confidence", ""),
    "thunder": ("Thunderstorm", "Thunder"),
    "cape": ("Thunderstorm energy (CAPE)", "CAPE"),
    "snowfall_limit": ("Snow line", "0° line"),
    "precip_type": ("Precipitation type", ""),
    "cloud_total": ("Cloud cover", ""),
    "cloud_low": ("Low clouds", ""),
    "cloud_mid": ("Mid-level clouds", ""),
    "cloud_high": ("High clouds", ""),
    "visibility": ("Visibility", "Visib"),
    "sunshine": ("Sunshine hours", ""),
    "uv_index": ("UV index", "UV index"),
    "pressure": ("Air pressure", ""),
    "freezing_level": ("Freezing level", "Freezing lvl"),
    "snow_depth": ("Snow depth", "Snow depth"),
    "fresh_snow": ("Fresh snow", "Fresh snow"),
}

# id -> (label_de, get_alert_label(id)) vor #2662
DEUTSCH = {
    "temperature": ("Temperatur", "Temp"),
    "temperature_cold": ("Tiefsttemperatur-Alarm", "Temp"),
    "temperature_night": ("Nacht-Tiefsttemperatur", "Nacht-Tiefsttemperatur"),
    "temperature_day_low": ("Tages-Tiefsttemperatur (Gehzeit)", "Tages-Tiefsttemperatur (Gehzeit)"),
    "temperature_day_high": ("Tages-Höchsttemperatur (Gehzeit)", "Tages-Höchsttemperatur (Gehzeit)"),
    "wind_chill": ("Gefühlte Temperatur", "Gefühlte Temperatur"),
    "wind_chill_night": ("Gefühlte Nacht-Tiefsttemperatur", "Gefühlte Nacht-Tiefsttemperatur"),
    "wind_chill_day_low": ("Gefühlte Tages-Tiefsttemperatur (Gehzeit)",
                           "Gefühlte Tages-Tiefsttemperatur (Gehzeit)"),
    "wind_chill_day_high": ("Gefühlte Tages-Höchsttemperatur (Gehzeit)",
                            "Gefühlte Tages-Höchsttemperatur (Gehzeit)"),
    "humidity": ("Luftfeuchtigkeit", "Feuchte"),
    "dewpoint": ("Taupunkt", "Taupunkt"),
    "wind": ("Wind", "Wind"),
    "gust": ("Böen", "Böen"),
    "wind_direction": ("Windrichtung", "Windrichtung"),
    "precipitation": ("Niederschlag", "Niedersch"),
    "rain_probability": ("Regenwahrscheinlichkeit", "Regen%"),
    "confidence": ("Sicherheit", "Sicherheit"),
    "thunder": ("Gewitter", "Gewitter"),
    "cape": ("Gewitterenergie (CAPE)", "CAPE"),
    "snowfall_limit": ("Schneefallgrenze", "0°-Grenze"),
    "precip_type": ("Niederschlagsart", "Niederschlagsart"),
    "cloud_total": ("Bewölkung", "Bewölkung"),
    "cloud_low": ("Tiefe Wolken", "Tiefe Wolken"),
    "cloud_mid": ("Mittelhohe Wolken", "Mittelhohe Wolken"),
    "cloud_high": ("Hohe Wolken", "Hohe Wolken"),
    "visibility": ("Sichtweite", "Sicht"),
    "sunshine": ("Sonnenstunden", "Sonnenstunden"),
    "uv_index": ("UV-Index", "UV-Index"),
    "pressure": ("Luftdruck", "Luftdruck"),
    "freezing_level": ("Nullgradgrenze", "Nullgradgrenze"),
    "snow_depth": ("Schneehöhe", "Schneehöhe"),
    "fresh_snow": ("Neuschnee", "Neuschnee"),
}


def _by_id():
    return {m.id: m for m in _METRICS}


def test_alle_32_eintraege_abgedeckt():
    assert len(_METRICS) == 32
    assert set(_by_id()) == set(ENGLISCH) == set(DEUTSCH)


def test_label_en_laut_tabelle():
    for mid, m in _by_id().items():
        label_en, alert_en = ENGLISCH[mid]
        assert m.label_en == label_en, mid
        assert m.label("en") == label_en, mid
        assert m.alert_label_en == alert_en, mid
        assert m.alert_label_for("en") == (alert_en or label_en), mid
        assert get_alert_label(mid, "en") == (alert_en or label_en), mid


def test_beispiele():
    m = _by_id()
    assert m["gust"].label("en") == "Wind gusts"
    assert m["snowfall_limit"].label("en") == "Snow line"


def test_alert_label_en_hoechstens_12_zeichen():
    for m in _METRICS:
        assert len(m.alert_label_en) <= 12, (m.id, m.alert_label_en)


def test_deutsch_byte_gleich():
    for mid, m in _by_id().items():
        label_de, alert_de = DEUTSCH[mid]
        assert m.label_de == label_de, mid
        assert m.label() == label_de and m.label("de") == label_de, mid
        assert m.alert_label_for() == alert_de and m.alert_label_for("de") == alert_de, mid
        assert get_alert_label(mid) == alert_de, mid
        assert get_alert_label(mid, "de") == alert_de, mid
        assert m.label("fr") == label_de, mid


def test_unbekannte_kennung_bleibt_kennung():
    assert get_alert_label("gibt_es_nicht") == "gibt_es_nicht"
    assert get_alert_label("gibt_es_nicht", "en") == "gibt_es_nicht"


def test_friendly_label_sprachneutral():
    for m in _METRICS:
        assert m.friendly_label_en == ""
        assert m.friendly_label_for("en") == m.friendly_label
        assert m.friendly_label_for("de") == m.friendly_label


def test_aggregation_labels():
    assert aggregation_label("avg", "en") == "Average"
    soll_en = {"min": "Minimum", "max": "Maximum", "avg": "Average", "sum": "Total"}
    soll_de = {"min": "Minimum", "max": "Maximum", "avg": "Mittel", "sum": "Summe"}
    for a in soll_en:
        assert aggregation_label(a, "en") == soll_en[a]
        assert aggregation_label(a, "de") == soll_de[a] == aggregation_label_de(a)
    assert aggregation_label("onset", "en") == ""
    assert aggregation_label(None, "en") == ""
