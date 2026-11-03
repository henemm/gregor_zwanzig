"""TDD RED — Issue #1895 Scheibe S3a: die EINE Quelle fuer „welche Alarm-Zeile
landet auf welchem Speicherschluessel von `alert_metric_channels`".

SPEC: docs/specs/modules/alert_metric_channels.md — Implementation Details (S3a)
      §3/§4, AC-30 bis AC-34.

Gemessen wird der Endpunkt `GET /alert-metric-channel-keys` des Python-Cores
ueber einen FastAPI-`TestClient` (kein Mock, kein Netz) und, fuer AC-32, gegen
den ECHTEN Detektor (`WeatherChangeDetectionService`) und die ECHTE Leser-
Primitive (`alert_channels._metric_id_for_summary_key`). Die Testapp bindet nur
`api.routers.config.router` ein — derselbe Router, den `api/main.py` montiert —
damit weder Lifespan noch Core-Auth den Endpunkt verdecken.

RED heute: der Endpunkt existiert nicht (404).

Warum AC-32 auf MENGENGLEICHHEIT je Zeile prueft (Nachfreigabe 2026-11-03):
`wind_change` beobachtet `wind_max_kmh` UND `gust_max_kmh`; der Leser liest das
Boeen-Feld als `gust`. Eine Pruefung „erster Schluessel" oder „⊆" verschwiege
genau diese Kopplung. Deshalb werden je Zeile ALLE beobachteten Werte bewegt und
ALLE gemeldeten Aenderungen aufgeloest.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone


# ═══════════════════════════ Helfer ═════════════════════════════════════════

def _client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from api.routers import config

    app = FastAPI()
    app.include_router(config.router)
    return TestClient(app)


def _schluessel_antwort() -> dict:
    antwort = _client().get("/alert-metric-channel-keys")
    assert antwort.status_code == 200, (
        "Der Endpunkt GET /alert-metric-channel-keys muss existieren und 200 "
        f"liefern, bekam {antwort.status_code}: {antwort.text[:200]}"
    )
    daten = antwort.json()
    assert set(daten) == {"keys", "accepted"}, (
        f"Antwortform `{{keys, accepted}}` erwartet, bekam Schluessel {sorted(daten)}"
    )
    return daten


def _segment():
    from app.models import GPXPoint, TripSegment

    jetzt = datetime.now(timezone.utc)
    return TripSegment(
        segment_id="seg-1",
        start_point=GPXPoint(lat=47.0, lon=11.0, elevation_m=1000, distance_from_start_km=0.0),
        end_point=GPXPoint(lat=47.1, lon=11.1, elevation_m=1500, distance_from_start_km=8.0),
        start_time=jetzt - timedelta(hours=1), end_time=jetzt + timedelta(hours=3),
        duration_hours=4.0, distance_km=8.0, ascent_m=500, descent_m=0,
    )


def _daten(**werte):
    from app.models import (
        ForecastMeta, NormalizedTimeseries, Provider, SegmentWeatherData,
        SegmentWeatherSummary,
    )

    return SegmentWeatherData(
        segment=_segment(),
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=1.0),
            data=[],
        ),
        aggregated=SegmentWeatherSummary(**werte),
        fetched_at=datetime.now(timezone.utc),
        provider="openmeteo",
    )


def _alt_und_neu():
    """Jeder Wert, den irgendeine Alarm-Zeile beobachtet, springt kraeftig.
    `cape_model_id` ist auf beiden Seiten ein geeichtes Modell, sonst
    enthaelt sich der CAPE-Zweig (#1592/#1601)."""
    from app.models import ThunderLevel

    jetzt = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    alt = dict(
        gust_max_kmh=10, wind_max_kmh=5, precip_sum_mm=0.0, temp_min_c=10,
        temp_max_c=15, thunder_level_max=ThunderLevel.NONE, freezing_level_m=3500,
        snow_new_sum_cm=0, cape_max_jkg=0, cape_model_id="meteofrance_arome",
        visibility_min_m=20000, thunder_onset_utc=jetzt + timedelta(hours=8),
        precip_heavy_onset_utc=jetzt + timedelta(hours=8),
    )
    neu = dict(
        gust_max_kmh=120, wind_max_kmh=90, precip_sum_mm=60.0, temp_min_c=-15,
        temp_max_c=38, thunder_level_max=ThunderLevel.HIGH, freezing_level_m=800,
        snow_new_sum_cm=60, cape_max_jkg=3500, cape_model_id="meteofrance_arome",
        visibility_min_m=50, thunder_onset_utc=jetzt + timedelta(hours=1),
        precip_heavy_onset_utc=jetzt + timedelta(hours=1),
    )
    return _daten(**alt), _daten(**neu)


def _gelesene_schluessel_fuer_zeile(zeile: str) -> set[str]:
    """Echter Weg: Empfindlichkeitsstufe → Regeln → Detektor → Leser."""
    from services.alert_channels import _metric_id_for_summary_key
    from services.alert_preset import expand_per_metric_levels
    from services.weather_change_detection import WeatherChangeDetectionService

    regeln = expand_per_metric_levels({zeile: "sensibel"})
    detektor = WeatherChangeDetectionService.from_alert_rules(regeln)
    alt, neu = _alt_und_neu()
    aenderungen = detektor.detect_changes(alt, neu, include_absolute=True)
    return {_metric_id_for_summary_key(a.metric) for a in aenderungen}


# ═══ AC-30 — Endpunkt liefert je Zeile die Schluesselliste ═══════════════════

def test_ac30_endpunkt_bildet_alarm_zeilen_auf_schluessellisten_ab():
    """AC-30 (ROT: Endpunkt fehlt)."""
    daten = _schluessel_antwort()
    keys = daten["keys"]

    mindestens = {
        "wind_gust": ["gust"],
        "wind_change": ["gust", "wind"],
        "temperature_min": ["temperature"],
        "temperature_max": ["temperature"],
        "temperature_change": ["temperature"],
        "thunder_onset": ["thunder"],
        "precipitation_heavy_onset": ["precipitation"],
        "snow_line": ["freezing_level"],
        "cape": ["cape"],
        "fresh_snow": ["fresh_snow"],
        "visibility": ["visibility"],
    }
    for zeile, erwartet in mindestens.items():
        assert keys.get(zeile) == erwartet, (
            f"AC-30: `{zeile}` muss auf {erwartet} abbilden, bekam {keys.get(zeile)!r}"
        )
    for zeile, liste in keys.items():
        assert liste == sorted(set(liste)) and liste, (
            f"AC-30: Schluesselliste von `{zeile}` muss nicht leer, sortiert und "
            f"doppelfrei sein, bekam {liste!r}"
        )

    bild = sorted({s for liste in keys.values() for s in liste} | {"snowfall_limit"})
    assert daten["accepted"] == bild, (
        "AC-30: `accepted` ist die sortierte Liste aller Schluessel aus `keys` "
        f"zuzueglich `snowfall_limit` — erwartet {bild}, bekam {daten['accepted']}"
    )


def test_ac30_funktion_und_endpunkt_sind_dieselbe_quelle():
    """AC-30 (ROT: Funktion fehlt): der Endpunkt liefert genau, was
    `alert_metric_channel_keys()` liefert — keine zweite Liste im Router."""
    from services.weather_change_detection import alert_metric_channel_keys

    assert _schluessel_antwort() == alert_metric_channel_keys(), (
        "AC-30: Endpunkt und `alert_metric_channel_keys()` muessen identisch sein"
    )


# ═══ AC-31 — humidity fehlt, snowfall_limit nie Ziel ═════════════════════════

def test_ac31_humidity_fehlt_und_snowfall_limit_ist_nie_ziel():
    """AC-31 (ROT: Endpunkt fehlt)."""
    daten = _schluessel_antwort()
    keys = daten["keys"]

    assert "humidity" not in keys, (
        f"AC-31: `humidity` hat keine Alarm-Identitaet und darf nicht in `keys` stehen: {keys}"
    )
    ziele = {s for liste in keys.values() for s in liste}
    assert "snowfall_limit" not in ziele, (
        f"AC-31: `snowfall_limit` darf nie Ziel in `keys` sein, Ziele: {sorted(ziele)}"
    )
    assert "snowfall_limit" in daten["accepted"], (
        "AC-31: `snowfall_limit` bleibt akzeptiert, weil die Legacy-Migration ihn "
        f"schreibt: {daten['accepted']}"
    )


# ═══ AC-32 — zeilenweise Mengengleichheit gegen Detektor + Leser ═════════════

def test_ac32_jede_zeile_entspricht_exakt_dem_was_der_leser_liest():
    """AC-32 (ROT: Endpunkt fehlt). Fuer JEDE Zeile in `keys`: alle von ihr
    beobachteten Werte bewegen, alle gemeldeten Aenderungen ueber die Leser-
    Primitive aufloesen, Menge == Endpunkt-Liste. Keine ⊆-Kette."""
    keys = _schluessel_antwort()["keys"]
    assert keys, "AC-32: `keys` darf nicht leer sein"

    abweichungen = {}
    for zeile, liste in sorted(keys.items()):
        gelesen = _gelesene_schluessel_fuer_zeile(zeile)
        if gelesen != set(liste):
            abweichungen[zeile] = {"endpunkt": liste, "leser": sorted(map(str, gelesen))}

    assert not abweichungen, (
        "AC-32: Endpunkt und Leser muessen je Zeile exakt uebereinstimmen, "
        f"Abweichungen: {abweichungen}"
    )


def test_ac32_jede_alarmfaehige_zeile_steht_im_endpunkt():
    """AC-32 Gegenrichtung (ROT: Endpunkt fehlt): jede `AlertMetric`, fuer die
    der Detektor ueberhaupt etwas meldet, MUSS im Endpunkt stehen — sonst
    fiele eine wirksame Zeile still aus der Oberflaeche."""
    from app.models import AlertMetric

    keys = _schluessel_antwort()["keys"]
    fehlend = [m.value for m in AlertMetric
               if _gelesene_schluessel_fuer_zeile(m.value) and m.value not in keys]
    assert not fehlend, f"AC-32: wirksame Zeilen fehlen im Endpunkt: {fehlend}"


# ═══ AC-33 — Migration schreibt nur akzeptierte Schluessel ═══════════════════

def test_ac33_migration_schreibt_nur_akzeptierte_schluessel():
    """AC-33 (ROT: Endpunkt fehlt). Regeln ALLER `AlertMetric`-Werte mit
    gesetzten Kanaelen laufen durch die echte Legacy-Migration; jeder
    geschriebene Schluessel muss in `accepted` liegen."""
    from app.loader import _migrate_rule_channels_to_metric_channels
    from app.models import AlertMetric, AlertRule, AlertRuleKind, AlertSeverity

    akzeptiert = set(_schluessel_antwort()["accepted"])
    regeln = [
        AlertRule(id=f"r-{m.value}", kind=AlertRuleKind.DELTA, metric=m,
                  threshold=1.0, severity=AlertSeverity.WARNING, enabled=True,
                  channels=["telegram"])
        for m in AlertMetric
    ]

    migriert = _migrate_rule_channels_to_metric_channels(regeln, None) or {}

    assert {"snowfall_limit", "freezing_level"} <= set(migriert), (
        "Vorbedingung AC-33: `snow_line`-Regeln schreiben `snowfall_limit` und "
        f"`freezing_level`, migriert: {sorted(migriert)}"
    )
    fremd = sorted(set(migriert) - akzeptiert)
    assert not fremd, (
        f"AC-33: die Migration schreibt Schluessel ausserhalb von `accepted`: {fremd}"
    )


# ═══ AC-34 — /metrics bleibt unveraendert ═══════════════════════════════════

def test_ac34_metrics_endpunkt_bleibt_unveraendert():
    """AC-34 (🟢 HEUTE GRUEN, Mutations-Fixture gegen „aggregations[]
    erweitern"): `cape` fehlt weiterhin (selectable=False), `aggregations[]`
    traegt nur Katalog-Auswertungen, keine Onset-/Alarm-Zeilen und kein
    Schluessel-Feld."""
    from app.metric_catalog import available_aggregations, get_all_metrics

    antwort = _client().get("/metrics")
    assert antwort.status_code == 200, antwort.text[:200]
    eintraege = [e for liste in antwort.json().values() for e in liste]
    nach_id = {e["id"]: e for e in eintraege}

    assert "cape" not in nach_id, "AC-34: `cape` (selectable=False) bleibt aus /metrics"
    assert set(nach_id) <= {m.id for m in get_all_metrics()}
    for metric_id, eintrag in nach_id.items():
        aggs = eintrag.get("aggregations") or []
        assert [a["id"] for a in aggs] == list(available_aggregations(metric_id)), (
            f"AC-34: `{metric_id}`: aggregations[] muss genau die Katalog-"
            f"Auswertungen tragen, bekam {aggs}"
        )
        for agg in aggs:
            assert set(agg) == {"id", "label", "label_en", "alert_metric"}, (
                f"AC-34: aggregations[] darf kein neues Feld (z. B. Schluessel-"
                f"Zuordnung) tragen: {agg}"
            )
            assert "onset" not in str(agg["id"]).lower(), (
                f"AC-34: keine Onset-Zeile in aggregations[]: {agg}"
            )
