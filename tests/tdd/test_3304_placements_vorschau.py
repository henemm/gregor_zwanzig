"""#3304 (Teil A von #3041): Vorschau der Tabelle "Was steht wo" fuer einen
noch nicht angelegten Trip bzw. Orts-Vergleich.

SPEC: docs/specs/modules/feat_3304_was_steht_wo_vorschau.md, AC-1 bis AC-5,
AC-7, AC-8 (Kern-Teil), AC-9 (Regression), AC-10 (Kern-Teil).

``POST /api/briefings/placements/vorschau?kind=route|vergleich&user_id=...``
nimmt den Entwurf im Koerper und antwortet mit DERSELBEN Ansicht wie
``GET /api/briefings/{id}/placements`` eines gleich konfigurierten
gespeicherten Abos -- nur ``stored`` ist immer ``false``. Es wird nichts
geschrieben.

Orakel: der bestehende GET-Weg (gespeichertes Abo gleicher Konfiguration)
und ``erstanlage_placements`` (Tabelle, die die Anlage schreiben wuerde).
Kern-Schicht: echte Dateien in der isolierten Datenwurzel, echter Router
(FastAPI TestClient), zwei Nutzer, kein Mock.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.tdd.test_placements_tabelle_endpoint import _orte, _trip

NUTZER_A, NUTZER_B = "p3304-a", "p3304-b"
VORSCHAU = "/api/briefings/placements/vorschau"
SCHLUESSEL = {"kind", "lang", "stored", "placements", "location_count", "columns",
              "fixed_rows", "rows", "sms_example", "outlook_reports", "blocks",
              "legend", "example_version"}
NAMEN_B = ("Bregenz", "Feldkirch")


@pytest.fixture
def client():
    from api.routers import placements

    app = FastAPI()
    app.include_router(placements.router)
    return TestClient(app)


def _root() -> Path:
    from app.loader import get_data_root

    return Path(get_data_root())


def _entwurf(datei: Path) -> dict:
    """Der Entwurf ist die Konfiguration des gespeicherten Abos -- als
    Koerper geschickt, nicht als Datei gelesen."""
    return json.loads(datei.read_text(encoding="utf-8"))


def _vorschau(client, kind, entwurf, user=NUTZER_A, **params):
    return client.post(VORSCHAU, params={"kind": kind, "user_id": user, **params},
                       json=entwurf)


def _vorschau_ok(client, kind, entwurf, user=NUTZER_A) -> dict:
    antwort = _vorschau(client, kind, entwurf, user)
    assert antwort.status_code == 200, antwort.text
    return antwort.json()


def _get_ok(client, kennung, kind, user=NUTZER_A) -> dict:
    antwort = client.get(f"/api/briefings/{kennung}/placements",
                         params={"kind": kind, "user_id": user})
    assert antwort.status_code == 200, antwort.text
    return antwort.json()


def _ohne_stored(antwort: dict) -> dict:
    return {k: v for k, v in antwort.items() if k != "stored"}


def _baum() -> dict[str, bytes]:
    """Alle Dateien der Datenwurzel mit Inhalt (relativer Pfad -> Bytes)."""
    wurzel = _root()
    stand = {}
    for ordner, _dirs, dateien in os.walk(wurzel):
        for name in dateien:
            pfad = Path(ordner) / name
            stand[str(pfad.relative_to(wurzel))] = pfad.read_bytes()
    return stand


def _rc_beide() -> dict:
    return {"morning_enabled": True, "evening_enabled": True, "send_email": True}


# ---------------------------------------------------------------------------
# AC-1 / AC-2: Vorschau == GET-Ansicht eines gleich konfigurierten Abos
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("rc", [None, _rc_beide()], ids=["standard", "beide_briefings"])
def test_ac1_trip_vorschau_gleich_get_ansicht_nur_stored_false(client, rc):
    """AC-1: GIVEN gespeicherter Trip und derselbe Trip als Entwurf WHEN
    Vorschau (kind=route) und GET THEN gleiche Schluessel und gleiche Werte
    (Spalten, Zeilen, SMS-Beispiel, Legende, Ausblick), nur ``stored`` ist
    bei der Vorschau ``false``."""
    datei = _trip(NUTZER_A, "v3304-trip", rc=rc)
    gespeichert = _get_ok(client, "v3304-trip", "route")
    vorschau = _vorschau_ok(client, "route", _entwurf(datei))

    assert set(vorschau) == set(gespeichert) == SCHLUESSEL
    assert vorschau["stored"] is False
    assert _ohne_stored(vorschau) == _ohne_stored(gespeichert)


def test_ac1_trip_mit_tabelle_vorschau_gleich_get_aber_stored_false(client):
    """AC-1: auch ein Trip MIT gespeicherter Tabelle (GET: ``stored=true``)
    ergibt als Entwurf dieselbe Ansicht -- die Vorschau meldet trotzdem
    ``stored=false``."""
    tabelle = {"version": 1, "rows": [
        {"metric_id": "gust", "places": {"sms": False}},
        {"metric_id": "wind", "formats": {"telegram": "simplified"}}],
        "outlook_reports": ["morning"]}
    datei = _trip(NUTZER_A, "v3304-tab", placements=tabelle, grund=["wind", "gust"])
    gespeichert = _get_ok(client, "v3304-tab", "route")
    assert gespeichert["stored"] is True
    vorschau = _vorschau_ok(client, "route", _entwurf(datei))

    assert vorschau["stored"] is False
    assert _ohne_stored(vorschau) == _ohne_stored(gespeichert)


def test_ac2_orte_vorschau_gleich_get_ansicht_inklusive_ortsanzahl(client):
    """AC-2: GIVEN gespeicherter Orts-Vergleich mit eigenen Orten und derselbe
    Vergleich als Entwurf WHEN Vorschau (kind=vergleich) und GET THEN gleiche
    Form und gleicher Inhalt inklusive ``location_count`` und Beispielwerten
    der Orte, nur ``stored`` ist ``false``."""
    datei = _orte(NUTZER_A, "v3304-orte", anzahl=2)
    gespeichert = _get_ok(client, "v3304-orte", "vergleich")
    vorschau = _vorschau_ok(client, "vergleich", _entwurf(datei))

    assert set(vorschau) == set(gespeichert) == SCHLUESSEL
    assert vorschau["stored"] is False
    assert vorschau["location_count"] == gespeichert["location_count"] == 2
    assert _ohne_stored(vorschau) == _ohne_stored(gespeichert)


# ---------------------------------------------------------------------------
# AC-3: Zeilen aus der Grundauswahl bzw. genau die mitgeschickten
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("kind", ["route", "vergleich"])
def test_ac3_entwurf_ohne_rows_traegt_erstanlage_tabelle(client, kind):
    """AC-3: GIVEN Entwurf ohne ``placements.rows`` WHEN Vorschau THEN traegt
    die Antwort exakt die Tabelle, die die Erstanlage fuer denselben Entwurf
    schreiben wuerde (Orakel: ``erstanlage_placements`` eines Referenz-Abos
    gleicher Konfiguration); ``stored`` bleibt ``false``."""
    from services.placements_view_service import erstanlage_placements

    if kind == "route":
        datei = _trip(NUTZER_A, "ref3304", rc=_rc_beide())
    else:
        datei = _orte(NUTZER_A, "ref3304", anzahl=2)
    soll = erstanlage_placements(kind, "ref3304", NUTZER_A)["placements"]
    entwurf = _entwurf(datei)
    entwurf["id"] = "entwurf-ohne-datei"
    assert "placements" not in entwurf["display_config"]

    vorschau = _vorschau_ok(client, kind, entwurf)
    assert vorschau["stored"] is False
    assert vorschau["placements"] == soll
    assert vorschau["placements"]["rows"], "Grundauswahl-Tabelle darf nicht leer sein"


@pytest.mark.parametrize("kind", ["route", "vergleich"])
def test_ac3_entwurf_mit_rows_behaelt_genau_diese_zeilen(client, kind):
    """AC-3: GIVEN Entwurf mit eigenen Zeilen (Teilmenge, umgekehrte
    Reihenfolge, eigene Form) WHEN Vorschau THEN stehen in ``placements.rows``
    genau die mitgeschickten Zeilen in dieser Reihenfolge, ``stored`` bleibt
    ``false``."""
    from services.placements_view_service import erstanlage_placements

    if kind == "route":
        datei = _trip(NUTZER_A, "rows3304", rc=_rc_beide())
    else:
        datei = _orte(NUTZER_A, "rows3304", anzahl=2)
    grund = erstanlage_placements(kind, "rows3304", NUTZER_A)["placements"]
    eigene = copy.deepcopy(list(reversed(grund["rows"][:3])))
    eigene[0]["places"] = {**(eigene[0].get("places") or {}), "sms": False}
    entwurf = _entwurf(datei)
    entwurf["id"] = "entwurf-mit-zeilen"
    entwurf["display_config"]["placements"] = {
        "version": grund["version"], "rows": eigene,
        "outlook_reports": grund["outlook_reports"]}

    vorschau = _vorschau_ok(client, kind, entwurf)
    assert vorschau["stored"] is False
    assert vorschau["placements"]["rows"] == eigene


# ---------------------------------------------------------------------------
# AC-4: nichts wird geschrieben
# ---------------------------------------------------------------------------

def test_ac4_vorschau_schreibt_nichts_kein_etag_keine_kennung(client):
    """AC-4: GIVEN Nutzer mit bekanntem Datenbaum WHEN er die Vorschau fuer
    Trip und Orts-Vergleich mehrfach abruft (auch mit Kennungen, die es noch
    nicht gibt) THEN bleibt der Datenbaum byte-gleich (keine neue, keine
    geaenderte Datei), die Antwort traegt keinen ETag und keine Kennung eines
    angelegten Abos."""
    from app.loader import get_data_root, load_all_trips, load_compare_presets

    trip = _entwurf(_trip(NUTZER_A, "baum3304-trip"))
    orte = _entwurf(_orte(NUTZER_A, "baum3304-orte", anzahl=2))
    neu_trip = {**trip, "id": "neu3304-trip"}
    neu_orte = {**orte, "id": "neu3304-orte"}
    vorher = _baum()
    trips_vorher = len(load_all_trips(user_id=NUTZER_A))
    orte_vorher = len(load_compare_presets(user_id=NUTZER_A, data_root=get_data_root()))

    for _ in range(3):
        for kind, entwurf in (("route", trip), ("route", neu_trip),
                              ("vergleich", orte), ("vergleich", neu_orte)):
            antwort = _vorschau(client, kind, entwurf)
            assert antwort.status_code == 200, antwort.text
            assert "etag" not in {h.lower() for h in antwort.headers}
            body = antwort.json()
            assert not {"id", "entity_id", "briefing_id"} & set(body), body.keys()
            assert body["stored"] is False

    assert _baum() == vorher, "Vorschau darf den Datenbaum nicht veraendern"
    assert len(load_all_trips(user_id=NUTZER_A)) == trips_vorher
    assert len(load_compare_presets(user_id=NUTZER_A, data_root=get_data_root())) == orte_vorher


# ---------------------------------------------------------------------------
# AC-5: Mandantentrennung mit zwei Nutzern
# ---------------------------------------------------------------------------

def test_ac5_nur_eigene_orte_fremde_id_und_fremde_user_id_ohne_wirkung(client):
    """AC-5: GIVEN Nutzer A und B mit je eigenen Orten; der Entwurf von A nennt
    eine Orts-ID von B und eine unbekannte ID, im Koerper steht ``user_id`` von
    B WHEN A die Vorschau abruft THEN erscheinen nur die Orte von A
    (``location_count`` zaehlt nur sie, keine Namen von B); derselbe Aufruf
    als B liefert dessen eigene Orte."""
    entwurf_a = _entwurf(_orte(NUTZER_A, "iso3304-a", anzahl=2))
    entwurf_b = _entwurf(_orte(NUTZER_B, "iso3304-b", anzahl=2, namen=NAMEN_B))
    ids_a, ids_b = entwurf_a["location_ids"], entwurf_b["location_ids"]
    vorschau_a = {**entwurf_a, "id": "iso3304-neu", "user_id": NUTZER_B,
                  "location_ids": [ids_b[0], "gibt-es-nicht", *ids_a]}

    antwort_a = _vorschau_ok(client, "vergleich", vorschau_a, user=NUTZER_A)
    text_a = json.dumps(antwort_a, ensure_ascii=False)
    assert antwort_a["location_count"] == len(ids_a) == 2
    for name in NAMEN_B:
        assert name not in text_a, f"Ort von B ({name}) in der Vorschau von A"

    vergleich_a = _get_ok(client, "iso3304-a", "vergleich", user=NUTZER_A)
    assert _ohne_stored(antwort_a) == _ohne_stored(vergleich_a), \
        "fremde und unbekannte IDs muessen still entfallen"

    vorschau_b = {**vorschau_a, "user_id": NUTZER_A,
                  "location_ids": [ids_a[0], "gibt-es-nicht", *ids_b]}
    antwort_b = _vorschau_ok(client, "vergleich", vorschau_b, user=NUTZER_B)
    assert antwort_b["location_count"] == len(ids_b) == 2
    # Ortsnamen stehen in keiner Antwort (auch nicht im GET des eigenen Abos);
    # Nachweis "B sieht seine eigenen Orte" daher ueber die GET-Ansicht von B.
    vergleich_b = _get_ok(client, "iso3304-b", "vergleich", user=NUTZER_B)
    assert _ohne_stored(antwort_b) == _ohne_stored(vergleich_b), "B sieht seine eigenen Orte"


def test_ac5_body_user_id_waehlt_keinen_fremden_bestand(client):
    """AC-5: GIVEN Entwurf von A, der nur Orts-IDs von B nennt und im Koerper
    ``user_id`` von B traegt WHEN A die Vorschau abruft THEN zaehlt sie null
    Orte -- der Koerper waehlt nie den Bestand eines anderen Nutzers."""
    _orte(NUTZER_A, "leer3304-a", anzahl=1)
    entwurf_b = _entwurf(_orte(NUTZER_B, "leer3304-b", anzahl=2, namen=NAMEN_B))
    entwurf = {**entwurf_b, "id": "leer3304-neu", "user_id": NUTZER_B}

    antwort = _vorschau_ok(client, "vergleich", entwurf, user=NUTZER_A)
    assert antwort["location_count"] == 0
    text = json.dumps(antwort, ensure_ascii=False)
    for name in NAMEN_B:
        assert name not in text


# ---------------------------------------------------------------------------
# AC-7 / AC-8: Fehler am Kern
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("params", [{}, {"kind": "foo"}, {"kind": "trip"}])
def test_ac7_kern_ohne_gueltige_art_ist_400_kind_required(client, params):
    """AC-7: GIVEN Vorschau direkt am Kern WHEN ``kind`` fehlt oder unbekannt
    ist THEN 400 mit Code ``kind_required`` und Katalogtext (kein Freitext)."""
    entwurf = _entwurf(_trip(NUTZER_A, "k3304"))
    antwort = client.post(VORSCHAU, params={"user_id": NUTZER_A, **params}, json=entwurf)
    assert antwort.status_code == 400, antwort.text
    body = antwort.json()
    assert body["code"] == "kind_required"
    from services.send_outcomes import error_body

    assert body == error_body("kind_required", lang="de")[1]


@pytest.mark.parametrize("kind,entwurf", [
    ("route", []),
    ("vergleich", []),
    ("route", {"id": "kaputt3304", "name": "Kaputt", "stages": "keine-liste"}),
    ("vergleich", "kein-objekt"),
], ids=["route-liste", "vergleich-liste", "route-unlesbar", "vergleich-text"])
def test_ac8_kern_unlesbarer_entwurf_ist_422_invalid_preset(client, kind, entwurf):
    """AC-8 (Kern-Teil): GIVEN ein Entwurf, der kein Objekt ist oder den der
    Kern nicht lesen kann WHEN Vorschau THEN 422 mit Code ``invalid_preset``
    aus dem Katalog (nicht FastAPIs eigene Validierungsantwort); es entsteht
    keine Datei."""
    vorher = _baum()
    antwort = _vorschau(client, kind, entwurf)
    assert antwort.status_code == 422, antwort.text
    assert antwort.json().get("code") == "invalid_preset", antwort.text
    assert _baum() == vorher


@pytest.mark.parametrize("lang", ["de", "en"])
@pytest.mark.parametrize("kind", ["route", "vergleich"])
def test_ac8_unlesbarer_entwurf_text_ohne_platzhalter_und_ohne_orte_abo(client, kind, lang):
    """Adversary F001: GIVEN ein deutsch- bzw. englischsprachiger Nutzer und
    ein unlesbarer Entwurf WHEN Vorschau THEN der Fehlertext steht in seiner
    Sprache, enthaelt keinen offenen Platzhalter und nennt bei Trips kein
    Orte-Abo (Code bleibt ``invalid_preset``)."""
    from i18n import t
    from tests.helpers.versand_fixture import nutzer_anlegen

    nutzer = f"p3304-{lang}"
    nutzer_anlegen(nutzer, lang)
    antwort = _vorschau(client, kind, [], user=nutzer)
    assert antwort.status_code == 422, antwort.text
    body = antwort.json()
    assert body["code"] == "invalid_preset"
    text = body["detail"]
    assert text == t("versand.vorschau.entwurf_unlesbar", lang)
    assert "{" not in text and "}" not in text, text
    if kind == "route":
        assert "orte-abo" not in text.lower(), text
        assert "locations subscription" not in text.lower(), text
    if lang == "en":
        assert text != t("versand.vorschau.entwurf_unlesbar", "de")


# ---------------------------------------------------------------------------
# AC-9: bestehender Lese- und Erstanlage-Weg unveraendert (Regression)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("kind", ["route", "vergleich"])
def test_ac9_regression_get_und_erstanlage_unveraendert(client, kind):
    """AC-9 (Regression, darf in RED gruen sein): GIVEN gespeichertes Abo
    WHEN GET und Erstanlage am Kern THEN liefern sie weiter ``stored=false``
    ohne Tabelle, die Grundauswahl-Tabelle und 404 fuer fremde Nutzer."""
    if kind == "route":
        _trip(NUTZER_A, "reg3304")
    else:
        _orte(NUTZER_A, "reg3304", anzahl=2)
    gelesen = _get_ok(client, "reg3304", kind)
    assert set(gelesen) == SCHLUESSEL and gelesen["stored"] is False
    erst = client.get("/api/briefings/reg3304/placements/erstanlage",
                      params={"kind": kind, "user_id": NUTZER_A})
    assert erst.status_code == 200 and erst.json()["placements"] == gelesen["placements"]
    fremd = client.get("/api/briefings/reg3304/placements",
                       params={"kind": kind, "user_id": NUTZER_B})
    assert fremd.status_code == 404


# ---------------------------------------------------------------------------
# AC-10: Pfad ist die Vorschau, nicht ein Abo mit der Kennung "placements"
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("kind", ["route", "vergleich"])
def test_ac10_pfad_ist_vorschau_auch_bei_abo_namens_placements(client, kind):
    """AC-10: GIVEN ein gespeichertes Abo mit der Kennung ``placements`` WHEN
    ``POST /api/briefings/placements/vorschau`` mit einem anderen Entwurf
    THEN antwortet die Vorschau mit der Ansicht DES ENTWURFS (``stored=false``,
    Zeilen des Entwurfs), nicht mit dem Abo ``placements``; der GET-Weg des
    Abos ``placements`` funktioniert weiter."""
    if kind == "route":
        _trip(NUTZER_A, "placements", grund=["wind", "gust"],
              placements={"version": 1, "rows": [{"metric_id": "gust"}, {"metric_id": "wind"}],
                          "outlook_reports": ["evening"]})
        entwurf = _entwurf(_trip(NUTZER_A, "anders3304", grund=["precipitation", "thunder"]))
    else:
        _orte(NUTZER_A, "placements", anzahl=1)
        entwurf = _entwurf(_orte(NUTZER_A, "anders3304", anzahl=2,
                                 grund=[{"metric_id": "wind", "aggregation": "max"}]))

    abo = _get_ok(client, "placements", kind)
    vorschau = _vorschau_ok(client, kind, entwurf)
    assert vorschau["stored"] is False
    assert vorschau != abo
    assert _ohne_stored(vorschau) == _ohne_stored(_get_ok(client, "anders3304", kind))


# ---------------------------------------------------------------------------
# Fix 1 (Staging-Befund): Entwurf in Anlage-Form OHNE Kennung
# ---------------------------------------------------------------------------

def _ohne_kennung(entwurf: dict) -> dict:
    """Entwurf so, wie die Anlage ihn vor dem Speichern traegt: ohne ``id``
    und ohne die daraus abgeleitete ``display_config.trip_id`` (die Kennung
    vergibt erst die Anlage). Etappen und Wegpunkte behalten ihre Kennungen,
    wie ``buildCreateTripPayload`` sie mitschickt."""
    entwurf = copy.deepcopy(entwurf)
    entwurf.pop("id", None)
    entwurf.get("display_config", {}).pop("trip_id", None)
    return entwurf


@pytest.mark.parametrize("leer", [None, ""], ids=["fehlt", "leer"])
@pytest.mark.parametrize("rc", [None, _rc_beide()], ids=["standard", "beide_briefings"])
def test_fix1_trip_entwurf_ohne_kennung_gleich_get_ansicht(client, rc, leer):
    """AC-1 (Staging-Befund): GIVEN ein Trip-Entwurf in Anlage-Form ohne
    Kennung (Etappen mit Wegpunkten, ``display_config.metrics``) WHEN Vorschau
    (kind=route) THEN 200, ``stored=false`` und dieselbe Ansicht wie das GET
    eines gleich konfigurierten gespeicherten Trips. Keine Ausnahme noetig:
    die Antwort traegt kein kennungsabhaengiges Feld (AC-4 -- weder ``id``
    noch ``entity_id``/``briefing_id``), daher Vergleich aller Felder ausser
    ``stored``."""
    datei = _trip(NUTZER_A, "ohne3304-trip", rc=rc)
    gespeichert = _get_ok(client, "ohne3304-trip", "route")
    entwurf = _ohne_kennung(_entwurf(datei))
    if leer is not None:
        entwurf["id"] = leer
    unveraendert = copy.deepcopy(entwurf)
    vorher = _baum()

    vorschau = _vorschau_ok(client, "route", entwurf)

    assert set(vorschau) == SCHLUESSEL
    assert vorschau["stored"] is False
    assert _ohne_stored(vorschau) == _ohne_stored(gespeichert)
    assert not {"id", "entity_id", "briefing_id"} & set(vorschau)
    assert entwurf == unveraendert, "Entwurf des Aufrufers darf nicht veraendert werden"
    assert _baum() == vorher


def test_fix1_trip_entwurf_ohne_kennung_direkt_am_dienst_unveraendert():
    """Kopie statt Veraenderung: der Dienst ergaenzt die Platzhalter-Kennung
    nur intern; das uebergebene Woerterbuch bleibt ohne ``id``."""
    from services.placements_view_service import build_placements_preview

    entwurf = _ohne_kennung(_entwurf(_trip(NUTZER_A, "dienst3304")))
    unveraendert = copy.deepcopy(entwurf)
    antwort = build_placements_preview("route", entwurf, NUTZER_A)
    assert antwort["stored"] is False
    assert entwurf == unveraendert


@pytest.mark.parametrize("leer", [None, ""], ids=["fehlt", "leer"])
def test_fix1_orte_entwurf_ohne_kennung_gleich_get_ansicht(client, leer):
    """AC-2 (Absicherung): GIVEN ein Orts-Vergleich-Entwurf ohne Kennung WHEN
    Vorschau (kind=vergleich) THEN 200, ``stored=false``, gleiche Ansicht
    wie das GET des gleich konfigurierten gespeicherten Vergleichs."""
    datei = _orte(NUTZER_A, "ohne3304-orte", anzahl=2)
    gespeichert = _get_ok(client, "ohne3304-orte", "vergleich")
    entwurf = _ohne_kennung(_entwurf(datei))
    if leer is not None:
        entwurf["id"] = leer
    unveraendert = copy.deepcopy(entwurf)

    vorschau = _vorschau_ok(client, "vergleich", entwurf)

    assert vorschau["stored"] is False
    assert vorschau["location_count"] == 2
    assert _ohne_stored(vorschau) == _ohne_stored(gespeichert)
    assert entwurf == unveraendert
