"""Die eine Regel der wirksamen Bewölkung (Issue #3106, ADR-0122).

SPEC: docs/specs/modules/feat_3106_wirksame_bewoelkung.md (AC-1 bis AC-6)

Kern-Schicht, rein, ohne Netz und ohne Mocks: geprüft wird die Domänenregel
``app.cloud_cover.wirksame_bewoelkung`` mit den Zahlen der Spec und die
Normalisierung ``normalisiere_bewoelkung`` je Datenpunkt (Modellwert bleibt in
``cloud_total_model_pct``, ``cloud_total_pct`` trägt die wirksame Bewölkung,
ein zweiter Lauf ändert nichts).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.models import ForecastDataPoint, ForecastMeta, NormalizedTimeseries, Provider

TAL_M = 800
HOCHLAGE_M = 3000


def _regel(gesamt, tief, mittel, hoch, hoehe_m=TAL_M):
    from app.cloud_cover import wirksame_bewoelkung

    return wirksame_bewoelkung(gesamt, tief, mittel, hoch, hoehe_m)


# ── AC-1 bis AC-6: Zahlen der Spec ────────────────────────────────────────────

def test_ac1_nur_schleierwolken_zaehlen_halb():
    assert _regel(100, 0, 0, 100) == 50


def test_ac2_dichte_mittelhohe_schicht_bleibt_voll():
    assert _regel(100, 0, 100, 100) == 100


def test_ac3_gemischte_stunde_tief_voll_rest_halb():
    # 20 + (84 - 20) * 0,5 = 52
    assert _regel(84, 20, 0, 80) == 52


def test_ac4_hochlage_tiefe_wolken_unter_dem_standort_zaehlen_nicht():
    assert _regel(100, 100, 0, 0, HOCHLAGE_M) == 0


def test_ac4_schwelle_genau_2500_m_ist_hochlage():
    assert _regel(100, 100, 0, 0, 2500) == 0
    assert _regel(100, 100, 0, 0, 2499) == 100


def test_ac5_hochlage_dichte_mittelhohe_schicht_voll_statt_halb():
    assert _regel(100, 0, 100, 0, HOCHLAGE_M) == 100


def test_hochlage_hohe_wolken_zaehlen_halb_ueber_der_mittelhohen_schicht():
    # dicht = mittel 40, bezug = max(40, 80) = 80 -> 40 + 40 * 0,5 = 60
    assert _regel(90, 70, 40, 80, HOCHLAGE_M) == 60


@pytest.mark.parametrize("mittel, hoch", [(None, 50), (50, None), (None, None)])
def test_ac6_ohne_schichten_bleibt_der_gesamtwert(mittel, hoch):
    assert _regel(77, 10, mittel, hoch) == 77
    assert _regel(77, 10, mittel, hoch, HOCHLAGE_M) == 77


def test_fehlt_tief_und_tief_zaehlt_bleibt_der_gesamtwert():
    assert _regel(77, None, 0, 100) == 77


def test_fehlt_tief_in_der_hochlage_ist_egal():
    assert _regel(77, None, 0, 100, HOCHLAGE_M) == 50


def test_unbekannte_hoehe_zaehlt_tiefe_wolken():
    assert _regel(100, 100, 0, 0, None) == 100


def test_gesamtwert_unbekannt_bezug_aus_den_schichten():
    # tief zählt, gesamt fehlt -> bezug = max(mittel, hoch) = 100, dicht = 0
    assert _regel(None, 0, 0, 100) == 50


def test_alles_unbekannt_bleibt_unbekannt():
    assert _regel(None, None, None, None) is None


def test_rundung_halb_auf():
    # dicht 0, bezug 1 -> 0,5 -> 1 (nicht Banker's Rounding auf 0)
    assert _regel(1, 0, 0, 1) == 1
    # dicht 0, bezug 3 -> 1,5 -> 2
    assert _regel(3, 0, 0, 3) == 2


def test_gesamt_unter_der_dichten_schicht_ergibt_die_dichte_schicht():
    # Inkonsistente Modellwerte (gesamt < tief): nie unter die dichte Schicht.
    assert _regel(30, 60, 0, 0) == 60


def test_ergebnis_ist_auf_0_bis_100_begrenzt():
    assert _regel(250, 180, 0, 0) == 100
    assert _regel(-5, -10, -10, -10) == 0


def test_konstanten_der_regel():
    from app.cloud_cover import HOCHLAGE_SCHWELLE_M, HOHE_WOLKEN_GEWICHT

    assert HOHE_WOLKEN_GEWICHT == 0.5
    assert HOCHLAGE_SCHWELLE_M == 2500


# ── Normalisierung je Datenpunkt ──────────────────────────────────────────────

def _reihe(*punkte: dict) -> NormalizedTimeseries:
    t0 = datetime(2026, 11, 17, 6, 0, tzinfo=timezone.utc)
    data = [ForecastDataPoint(ts=t0 + timedelta(hours=i), **p) for i, p in enumerate(punkte)]
    meta = ForecastMeta(provider=Provider.OPENMETEO, model="icon_d2", grid_res_km=2.2)
    return NormalizedTimeseries(meta=meta, data=data)


SCHLEIER = dict(cloud_total_pct=100, cloud_low_pct=0, cloud_mid_pct=0, cloud_high_pct=100)
GEMISCHT = dict(cloud_total_pct=84, cloud_low_pct=20, cloud_mid_pct=0, cloud_high_pct=80)
OHNE_SCHICHTEN = dict(cloud_total_pct=64)


def test_normalisierung_setzt_wirksam_und_bewahrt_modellwert():
    from app.cloud_cover import normalisiere_bewoelkung

    ts = _reihe(SCHLEIER, GEMISCHT, OHNE_SCHICHTEN)
    normalisiere_bewoelkung(ts, TAL_M)
    assert [dp.cloud_total_pct for dp in ts.data] == [50, 52, 64]
    assert [dp.cloud_total_model_pct for dp in ts.data] == [100, 84, 64]
    # Schichten bleiben unverändert (eigene Metriken CL/CM/CH).
    assert [dp.cloud_high_pct for dp in ts.data] == [100, 80, None]


def test_normalisierung_nutzt_die_standorthoehe():
    from app.cloud_cover import normalisiere_bewoelkung

    tief_unten = dict(cloud_total_pct=100, cloud_low_pct=100, cloud_mid_pct=0, cloud_high_pct=0)
    ts_tal, ts_berg = _reihe(tief_unten), _reihe(tief_unten)
    normalisiere_bewoelkung(ts_tal, TAL_M)
    normalisiere_bewoelkung(ts_berg, HOCHLAGE_M)
    assert ts_tal.data[0].cloud_total_pct == 100
    assert ts_berg.data[0].cloud_total_pct == 0


def test_normalisierung_ist_idempotent():
    from app.cloud_cover import normalisiere_bewoelkung

    ts = _reihe(SCHLEIER, GEMISCHT, OHNE_SCHICHTEN)
    normalisiere_bewoelkung(ts, TAL_M)
    normalisiere_bewoelkung(ts, TAL_M)
    assert [dp.cloud_total_pct for dp in ts.data] == [50, 52, 64]
    assert [dp.cloud_total_model_pct for dp in ts.data] == [100, 84, 64]


def test_normalisierung_ohne_modell_gesamtwert_bleibt_stabil():
    """Ohne Modell-Gesamtwert liesse sich ein zweiter Lauf nicht vom ersten
    unterscheiden; die Normalisierung laesst solche Punkte deshalb unberuehrt."""
    from app.cloud_cover import normalisiere_bewoelkung

    ts = _reihe(dict(cloud_low_pct=0, cloud_mid_pct=0, cloud_high_pct=100))
    normalisiere_bewoelkung(ts, TAL_M)
    normalisiere_bewoelkung(ts, TAL_M)
    assert ts.data[0].cloud_total_pct is None
    assert ts.data[0].cloud_total_model_pct is None
