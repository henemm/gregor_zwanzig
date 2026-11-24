"""#3306 (Teil C von #3041, Epic #3122): Vorschau der Tabelle "Was steht wo"
fuer einen FRUEHEN Ortsvergleich-Entwurf beim Anlegen.

SPEC: docs/specs/modules/feat_3306_tabelle_orte_anlegen.md, Test Plan Nr. 5
(AC-8) und Nr. 6 (AC-7, Kern-Teil).

Die Seite /compare/new schickt im Schritt Wetter den Entwurf ``wetterAbo`` des
Editors an ``POST /api/briefings/placements/vorschau?kind=vergleich``. Dieser
Entwurf hat weder ``id`` noch ``name`` noch ``schedule``; ``location_ids`` ist
die Auswahl des Schritts Orte (leer, solange nichts gewaehlt ist), dazu
``hourly_enabled`` und ``display_config.telegram_style`` aus dem Feldsatz. Die
Entwuerfe unten bilden genau diese Form nach (CompareNewEditor.svelte,
``wetterAbo`` nach #3306).

Ein unvollstaendiger, aber wohlgeformter Entwurf ist waehrend des Anlegens ein
legitimer Zustand: die Vorschau antwortet mit einer Ansicht, schreibt nichts
und rechnet nur mit Orten aus dem Bestand des angemeldeten Nutzers.

Kern-Schicht: echter Router (FastAPI TestClient), echter Service, isolierte
Datenwurzel mit echten Dateien, zwei Nutzer, kein Mock.
"""
from __future__ import annotations

import copy
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.tdd.test_3304_placements_vorschau import SCHLUESSEL, VORSCHAU, _baum
from tests.tdd.test_placements_tabelle_endpoint import ORTE_GRUND, _orte

NUTZER_A, NUTZER_B = "p3306-a", "p3306-b"
NAMEN_A = ("Innsbruck", "Lienz")
NAMEN_B = ("Bregenz", "Feldkirch")


def _wetter_abo(location_ids, *, auswahl=True, hourly=True, stil="rich") -> dict:
    """Entwurf ``wetterAbo`` des Anlege-Editors im Schritt Wetter: ohne
    ``id``, ``name`` und ``schedule``."""
    dc: dict = {"ampel": {"template": "allgemein"}, "telegram_style": stil}
    if auswahl:
        dc["active_metrics"] = copy.deepcopy(ORTE_GRUND)
    return {
        "display_config": dc,
        "official_alerts_enabled": True,
        "official_warnings": {"enabled": True},
        "radar_alert_enabled": False,
        "day_window_start_hour": 4,
        "day_window_end_hour": 19,
        "location_ids": list(location_ids),
        "hourly_enabled": hourly,
    }


@pytest.fixture
def client():
    from api.routers import placements

    app = FastAPI()
    app.include_router(placements.router)
    return TestClient(app)


def _ids(user, kennung, namen) -> list[str]:
    """Orte des Nutzers als echte Dateien (der Vergleich daneben ist nur
    Traeger der Orte; die Vorschau liest ihn nicht)."""
    datei = _orte(user, kennung, anzahl=len(namen), namen=namen)
    return json.loads(datei.read_text(encoding="utf-8"))["location_ids"]


def _vorschau(client, entwurf, user=NUTZER_A):
    return client.post(VORSCHAU, params={"kind": "vergleich", "user_id": user}, json=entwurf)


def _ok(client, entwurf, user=NUTZER_A) -> dict:
    antwort = _vorschau(client, entwurf, user)
    assert antwort.status_code == 200, antwort.text
    return antwort.json()


# ---------------------------------------------------------------------------
# Test 5 (AC-8): frueher Entwurf -> 200 mit Ansicht
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("entwurf", [
    {},
    _wetter_abo([], auswahl=False),
    _wetter_abo([]),
    _wetter_abo([], hourly=False, stil="kurzform"),
], ids=["leer", "ohne-auswahl-ohne-orte", "auswahl-ohne-orte", "schalter-gesetzt-ohne-orte"])
def test_ac8_frueher_entwurf_ohne_orte_liefert_ansicht(client, entwurf):
    """GIVEN ein frueher Entwurf ohne ``id``/``name``/``schedule`` und ohne
    gewaehlte Orte WHEN Vorschau ``kind=vergleich`` THEN 200 mit der vollen
    Ansicht (alle Schluessel, Zeilen, Stellen), ``stored=false``, null Orte;
    es entsteht keine Datei und der Entwurf des Aufrufers bleibt unveraendert."""
    vorher = _baum()
    original = copy.deepcopy(entwurf)
    body = _ok(client, entwurf)
    assert set(body) == SCHLUESSEL
    assert body["stored"] is False
    assert body["location_count"] == 0
    assert body["rows"], "Ansicht ohne Zeilen"
    assert [c["stelle"] for c in body["columns"]]
    assert _baum() == vorher, "Vorschau darf den Datenbaum nicht veraendern"
    assert entwurf == original


def test_ac8_frueher_entwurf_mit_eigenen_orten_liefert_beispielwerte(client):
    """GIVEN ein frueher Entwurf (ohne ``name``/``schedule``) mit zwei eigenen
    Orten WHEN Vorschau THEN 200, ``location_count`` = 2 und ein SMS-Beispiel
    aus den Orten (Beispielwerte statt leerer Ansicht)."""
    ids_a = _ids(NUTZER_A, "frueh3306-a", NAMEN_A)
    body = _ok(client, _wetter_abo(ids_a))
    assert body["stored"] is False
    assert body["location_count"] == 2
    assert (body.get("sms_example") or {}).get("text"), "keine Beispielwerte trotz gewaehlter Orte"


def test_ac8_schalter_des_entwurfs_stehen_in_den_bloecken(client):
    """GIVEN ein frueher Entwurf mit ``hourly_enabled=false`` und
    ``telegram_style=kurzform`` WHEN Vorschau THEN starten die Schalter der
    Karte mit diesem Stand (``blocks``), nicht mit dem Standard."""
    ids_a = _ids(NUTZER_A, "schalter3306-a", NAMEN_A)
    standard = _ok(client, _wetter_abo(ids_a))
    gesetzt = _ok(client, _wetter_abo(ids_a, hourly=False, stil="kurzform"))
    assert standard["blocks"].get("hourly") is True
    assert standard["blocks"].get("telegram_style") == "rich"
    assert gesetzt["blocks"].get("hourly") is False
    assert gesetzt["blocks"].get("telegram_style") == "kurzform"


# ---------------------------------------------------------------------------
# Test 6 (AC-7): Orte nur aus dem eigenen Bestand -- zwei Nutzer
# ---------------------------------------------------------------------------

def test_ac7_fremde_orts_kennung_faellt_weg(client):
    """GIVEN Nutzer A und B mit je eigenen Orten; der fruehe Entwurf von A
    nennt eine Orts-Kennung von B, eine unbekannte und die eigenen WHEN A die
    Vorschau abruft THEN rechnet sie nur mit den Orten von A: gleiche Ansicht
    wie ohne die fremde Kennung, kein Name von B in der Antwort."""
    ids_a = _ids(NUTZER_A, "iso3306-a", NAMEN_A)
    ids_b = _ids(NUTZER_B, "iso3306-b", NAMEN_B)

    nur_eigene = _ok(client, _wetter_abo(ids_a))
    mit_fremder = _ok(client, _wetter_abo([ids_b[0], "gibt-es-nicht", *ids_a]))
    assert mit_fremder["location_count"] == 2
    assert mit_fremder == nur_eigene, "fremde und unbekannte Kennungen muessen still entfallen"
    text = json.dumps(mit_fremder, ensure_ascii=False)
    for name in NAMEN_B:
        assert name not in text, f"Ort von B ({name}) in der Vorschau von A"


def test_ac7_nur_fremde_orte_ergeben_keine_beispielwerte(client):
    """GIVEN der Entwurf von A nennt nur Orte von B (auch mit ``user_id`` von
    B im Koerper) WHEN A die Vorschau abruft THEN null Orte und keine Werte
    von B; derselbe Entwurf als B rechnet mit dessen zwei Orten."""
    _ids(NUTZER_A, "fremd3306-a", NAMEN_A)
    ids_b = _ids(NUTZER_B, "fremd3306-b", NAMEN_B)
    entwurf = {**_wetter_abo(ids_b), "user_id": NUTZER_B}

    als_a = _ok(client, entwurf, user=NUTZER_A)
    assert als_a["location_count"] == 0
    leer = _ok(client, _wetter_abo([]), user=NUTZER_A)
    assert als_a["sms_example"] == leer["sms_example"], "Beispielwerte aus Orten von B"
    text = json.dumps(als_a, ensure_ascii=False)
    for name in NAMEN_B:
        assert name not in text

    als_b = _ok(client, entwurf, user=NUTZER_B)
    assert als_b["location_count"] == 2
