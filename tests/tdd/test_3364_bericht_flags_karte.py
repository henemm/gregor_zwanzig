"""Karte "Was steht wo": Bericht-Flags je Zeile und Ausblick-Haken (#3364, Epic #3122).

SPEC: docs/specs/modules/fix_3364_nur_morgens_abends.md, Test Plan 6 und 7,
AC-5 und AC-7; Kontext docs/context/fix-3364-nur-morgens-abends.md,
Entscheidungen 6 und 7.

Test 6: Die Karten-Antwort (GET ``/api/briefings/{id}/placements``) traegt je
Zeile das Feld ``briefing_only``: ``"morning"`` (nur das Morgen-Briefing fuehrt
die Groesse), ``"evening"`` (nur das Abend-Briefing) oder ``None`` (beide oder
keins). Regel je Metrik nach Flags wie der Mail-Filter
``_filter_metrics_by_report_type``: Flag wenn gesetzt, sonst ``enabled``. Nur
Trip; im Ortsvergleich fehlt das Feld.

Test 7: Der Ausblick-Haken einer Zeile steht nur, wenn mindestens ein Briefing
aus ``outlook_reports`` die Groesse fuehrt. ``cloud_low`` nur morgens bei
``outlook_reports == ["evening"]``: kein Haken -- in der Anzeige (GET und
Vorschau) und in der Erstanlage gleich. Fuehrt ein Ausblick-Briefing die
Groesse, ist der Haken gesetzt.

Kern-Schicht: echte Dateien in der isolierten Datenwurzel, echter Router und
echte Service-Funktionen, kein Mock. Zwei Nutzer mit verschiedenen Flags.
"""
from __future__ import annotations

import copy

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.tdd.test_placements_tabelle_endpoint import _ok, _orte, _schreibe

NUTZER_A, NUTZER_B = "p3364-flags-a", "p3364-flags-b"

#: Nutzer A: cloud_mid nur morgens (enabled aus, Morgen-Flag an), gust nur abends
#: (enabled an, Morgen-Flag aus), wind mit beiden Flags, thunder ohne Flags.
METRIKEN_A = [
    {"metric_id": "cloud_mid", "enabled": False, "bucket": "primary", "order": 0, "morning_enabled": True},
    {"metric_id": "gust", "enabled": True, "bucket": "primary", "order": 1, "morning_enabled": False},
    {"metric_id": "wind", "enabled": True, "bucket": "primary", "order": 2,
     "morning_enabled": True, "evening_enabled": True},
    {"metric_id": "thunder", "enabled": True, "bucket": "primary", "order": 3},
]
ERWARTET_A = {"cloud_mid": "morning", "gust": "evening", "wind": None, "thunder": None}

#: Nutzer B, gleiche Kennung: umgekehrt -- cloud_mid nur abends, gust ohne Flags.
METRIKEN_B = [
    {"metric_id": "cloud_mid", "enabled": True, "bucket": "primary", "order": 0, "morning_enabled": False},
    {"metric_id": "gust", "enabled": True, "bucket": "primary", "order": 1},
    {"metric_id": "wind", "enabled": False, "bucket": "primary", "order": 2, "evening_enabled": True},
    {"metric_id": "thunder", "enabled": True, "bucket": "primary", "order": 3},
]
ERWARTET_B = {"cloud_mid": "evening", "gust": None, "wind": "evening", "thunder": None}

#: cloud_low nur morgens (wie Golden C), wind in beiden Briefings als Gegenprobe.
METRIKEN_AUSBLICK = [
    {"metric_id": "cloud_low", "enabled": True, "bucket": "primary", "order": 0, "evening_enabled": False},
    {"metric_id": "wind", "enabled": True, "bucket": "primary", "order": 1},
]


@pytest.fixture
def client():
    from api.routers import placements

    app = FastAPI()
    app.include_router(placements.router)
    return TestClient(app)


def _trip_daten(kennung: str, metriken: list, outlook_reports=None) -> dict:
    dc: dict = {"trip_id": kennung, "metrics": copy.deepcopy(metriken)}
    if outlook_reports is not None:
        # Marke ohne rows (#3155): die Tabelle kommt aus der Grundauswahl.
        dc["placements"] = {"outlook_reports": list(outlook_reports)}
    return {
        "id": kennung, "name": "Trip " + kennung, "kind": "route",
        "stages": [{"id": "T1", "name": "Etappe 1", "date": "2026-07-14", "waypoints": [
            {"id": "W1", "name": "Start", "lat": 47.27, "lon": 11.40, "elevation_m": 600},
            {"id": "W2", "name": "Ziel", "lat": 47.29, "lon": 11.42, "elevation_m": 900}]}],
        "official_alerts_enabled": True, "display_config": dc,
    }


def _trip(user: str, kennung: str, metriken: list, outlook_reports=None):
    return _schreibe(user, "briefings", kennung, _trip_daten(kennung, metriken, outlook_reports))


def _zeilen(antwort: dict) -> dict:
    return {z["metric_id"]: z for z in antwort["rows"]}


# ---------------------------------------------------------------------------
# Test 6: Zeilenfeld briefing_only
# ---------------------------------------------------------------------------

def test_trip_zeilenfeld_briefing_only_je_flags_zwei_nutzer(client):
    """AC-5: je Zeile "morning"/"evening"/None nach Flags; Nutzer A und B
    unter derselben Kennung sehen jeweils ihre eigenen Flags."""
    kennung = "flags-3364"
    _trip(NUTZER_A, kennung, METRIKEN_A)
    _trip(NUTZER_B, kennung, METRIKEN_B)
    for user, erwartet in ((NUTZER_A, ERWARTET_A), (NUTZER_B, ERWARTET_B)):
        zeilen = _zeilen(_ok(client, kennung, "route", user))
        assert set(erwartet) <= set(zeilen), f"{user}: Zeilen {sorted(zeilen)}"
        for mid, soll in erwartet.items():
            assert "briefing_only" in zeilen[mid], f"{user}/{mid}: Feld briefing_only fehlt"
            assert zeilen[mid]["briefing_only"] == soll, f"{user}/{mid}"


def test_trip_vorschau_traegt_briefing_only(client):
    """Die Vorschau (Anlage, #3304) baut dieselbe Antwort: gleiches Feld."""
    from services.placements_view_service import build_placements_preview

    antwort = build_placements_preview("route", _trip_daten("", METRIKEN_A), NUTZER_A)
    zeilen = _zeilen(antwort)
    for mid, soll in ERWARTET_A.items():
        assert "briefing_only" in zeilen[mid], f"{mid}: Feld briefing_only fehlt"
        assert zeilen[mid]["briefing_only"] == soll, mid


def test_vergleich_hat_kein_zeilenfeld_briefing_only(client):
    """Der Ortsvergleich kennt keine Bericht-Flags: das Feld fehlt ganz."""
    _orte(NUTZER_A, "orte-3364")
    antwort = _ok(client, "orte-3364", "vergleich", NUTZER_A)
    assert antwort["rows"], "Messaufbau: der Vergleich hat Zeilen"
    for z in antwort["rows"]:
        assert "briefing_only" not in z, z["metric_id"]


# ---------------------------------------------------------------------------
# Test 7: Ausblick-Haken nur bei Fuehrung durch ein Ausblick-Briefing
# ---------------------------------------------------------------------------

def _ausblick_karte(antwort: dict, mid: str) -> str:
    return _zeilen(antwort)[mid]["cells"]["outlook"]["state"]


def _ausblick_anlage(placements: dict, mid: str):
    zeile = next(r for r in placements["rows"] if r["metric_id"] == mid)
    return zeile.get("places", {}).get("outlook")


def _ausblick_fall() -> str:
    """Nutzer A: cloud_low nur morgens; Nutzer B (gleiche Kennung): ohne
    Einschraenkung. Beide: nur das Abend-Briefing fuehrt den Ausblick."""
    kennung = "ausblick-3364"
    _trip(NUTZER_A, kennung, METRIKEN_AUSBLICK, outlook_reports=["evening"])
    ohne_flag = [{k: v for k, v in m.items() if k != "evening_enabled"} for m in METRIKEN_AUSBLICK]
    _trip(NUTZER_B, kennung, ohne_flag, outlook_reports=["evening"])
    return kennung


def test_cloud_low_nur_morgens_ausblick_nur_abends_kein_haken_in_der_karte(client):
    """AC-7 (Fehlerfall, Anzeige GET): kein Haken; wind (beide) als Gegenprobe."""
    kennung = _ausblick_fall()
    karte = _ok(client, kennung, "route", NUTZER_A)
    assert karte["outlook_reports"] == ["evening"], "Messaufbau: nur das Abend-Briefing fuehrt den Ausblick"
    assert _ausblick_karte(karte, "wind") == "on", "Messaufbau: wind im Ausblick"
    assert _ausblick_karte(karte, "cloud_low") != "on", "Karte: cloud_low im Ausblick angehakt"


def test_cloud_low_nur_morgens_ausblick_nur_abends_kein_haken_in_der_vorschau(client):
    """AC-7 (Fehlerfall, Anzeige Vorschau der Anlage)."""
    from services.placements_view_service import build_placements_preview

    vorschau = build_placements_preview("route", _trip_daten("", METRIKEN_AUSBLICK, ["evening"]), NUTZER_A)
    assert vorschau["outlook_reports"] == ["evening"]
    assert _ausblick_karte(vorschau, "wind") == "on", "Messaufbau: wind im Ausblick"
    assert _ausblick_karte(vorschau, "cloud_low") != "on", "Vorschau: cloud_low im Ausblick angehakt"


def test_cloud_low_nur_morgens_ausblick_nur_abends_kein_haken_in_der_erstanlage(client):
    """AC-7 (Fehlerfall, Erstanlage): gleiche Regel wie die Anzeige."""
    from services.placements_view_service import erstanlage_placements

    kennung = _ausblick_fall()
    anlage = erstanlage_placements("route", kennung, NUTZER_A)["placements"]
    assert anlage["outlook_reports"] == ["evening"]
    assert _ausblick_anlage(anlage, "wind") is True, "Messaufbau: wind in der Erstanlage im Ausblick"
    assert _ausblick_anlage(anlage, "cloud_low") is False, "Erstanlage: cloud_low im Ausblick angehakt"


def test_ausblick_haken_zweiter_nutzer_ohne_einschraenkung_bleibt_gesetzt(client):
    """Mandantentrennung: Nutzer B fuehrt cloud_low in beiden Briefings -> Haken."""
    from services.placements_view_service import erstanlage_placements

    kennung = _ausblick_fall()
    assert _ausblick_karte(_ok(client, kennung, "route", NUTZER_B), "cloud_low") == "on"
    assert _ausblick_anlage(erstanlage_placements("route", kennung, NUTZER_B)["placements"], "cloud_low") is True


@pytest.mark.parametrize("berichte", [["morning"], ["morning", "evening"]])
def test_cloud_low_nur_morgens_mit_fuehrendem_ausblick_briefing_haken_gesetzt(client, berichte):
    """AC-7 (Gegenprobe): fuehrt ein Briefing aus outlook_reports die Groesse,
    steht der Haken -- in Karte und Erstanlage gleich."""
    from services.placements_view_service import erstanlage_placements

    kennung = "ausblick-3364-" + "-".join(berichte)
    _trip(NUTZER_A, kennung, METRIKEN_AUSBLICK, outlook_reports=berichte)
    karte = _ok(client, kennung, "route", NUTZER_A)
    assert karte["outlook_reports"] == berichte
    assert _ausblick_karte(karte, "cloud_low") == "on"
    assert _ausblick_anlage(erstanlage_placements("route", kennung, NUTZER_A)["placements"], "cloud_low") is True
