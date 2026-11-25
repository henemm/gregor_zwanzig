"""#2988 S2: Der Server loest die Ampel fuer einen Entwurf auf.

SPEC: docs/specs/modules/rework_2988_ampel_ableitung.md, AC-4 bis AC-7 (Kern-
Teil) und AC-19 (Aufloesung der Renderer unveraendert).

``POST /api/ampel/aufloesung?user_id=...`` mit ``{"eintraege": [...]}`` antwortet
``{"ergebnisse": [{"vorlage_id", "ampel"}, ...]}``.

Orakel: ``tests/fixtures/ampel_aufloesung_2988.json``, einmalig aus dem
Frontend-Code VOR dem Umbau erzeugt, und ``GET /api/templates``. Kern-Schicht:
echter Router (FastAPI TestClient), isolierte Datenwurzel, zwei Nutzer, kein Mock.
"""
from __future__ import annotations

import copy
import json
import logging
import os
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.ampel import resolve_ampel, validate_ampel

PFAD = "/api/ampel/aufloesung"
NUTZER_A, NUTZER_B = "p2988-a", "p2988-b"
MAX_EINTRAEGE = 32

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "ampel_aufloesung_2988.json"
REF = json.loads(_FIXTURE.read_text(encoding="utf-8"))
ABO = [f for f in REF["faelle"] if f["form"] == "abo"]
ALTBESTAND = [f for f in REF["faelle"] if f["form"] == "altbestand"]


def _name(fall: dict) -> str:
    return fall["name"]


def _soll(fall: dict) -> dict:
    ampel = copy.deepcopy(REF["vorlagen"][fall["vorlage_id"]])
    ampel["metrics"].update(copy.deepcopy(fall["zeilen"]))
    ampel["thunder"] = copy.deepcopy(fall["thunder"])
    return ampel


@pytest.fixture
def client():
    from api.routers import ampel_aufloesung

    app = FastAPI()
    app.include_router(ampel_aufloesung.router)
    return TestClient(app, raise_server_exceptions=False)


def _post(client, rumpf, user=NUTZER_A):
    return client.post(PFAD, params={"user_id": user}, json=rumpf)


def _post_roh(client, inhalt: str, user=NUTZER_A):
    return client.post(PFAD, params={"user_id": user}, content=inhalt.encode("utf-8"),
                       headers={"Content-Type": "application/json"})


def _loese(client, eintraege: list) -> list:
    antwort = _post(client, {"eintraege": eintraege})
    assert antwort.status_code == 200, antwort.text
    rumpf = antwort.json()
    assert set(rumpf) == {"ergebnisse"}
    assert len(rumpf["ergebnisse"]) == len(eintraege)
    return rumpf["ergebnisse"]


def _eins(client, eintrag: dict) -> dict:
    ergebnis = _loese(client, [eintrag])[0]
    assert set(ergebnis) == {"vorlage_id", "ampel"}
    assert ergebnis["ampel"]["template"] == ergebnis["vorlage_id"]
    return ergebnis


def _baum() -> dict[str, bytes]:
    from app.loader import get_data_root

    wurzel = Path(get_data_root())
    return {str((Path(o) / n).relative_to(wurzel)): (Path(o) / n).read_bytes()
            for o, _d, dateien in os.walk(wurzel) for n in dateien}


# --- AC-4: sieben Vorlagen und Abweichungen ----------------------------------


def test_ac4_jede_vorlage_gleich_get_templates(client):
    """AC-4: je Systemvorlage ist die Antwort die Vorlagen-Ampel aus
    ``GET /api/templates``."""
    from api.routers.config import get_templates

    vorlagen = {t["id"]: t["ampel"] for t in get_templates()}
    assert len(vorlagen) == 7
    for tid, ampel in vorlagen.items():
        e = _eins(client, {"ampel": {"template": tid}})
        assert e["vorlage_id"] == tid
        assert e["ampel"] == ampel


@pytest.mark.parametrize("fall", ABO, ids=_name)
def test_ac4_ac5_abo_sicht_gleich_referenz(client, fall):
    """AC-4/AC-5: Vorlage + Abweichungen, Rangfolge, ungueltige Ampel und
    unbekannte Vorlage wie im Code vor dem Umbau."""
    e = _eins(client, fall["eintrag"])
    assert e["vorlage_id"] == fall["vorlage_id"]
    assert e["ampel"] == _soll(fall)


def test_ac4_reihenfolge_und_laenge_bleiben_und_eintraege_mischen_sich_nicht(client):
    """Antwort in Reihenfolge der Eintraege, Abo-Sicht und Altbestand gemischt;
    ein Eintrag faerbt nie auf den naechsten oder den naechsten Aufruf ab."""
    misch = [*ALTBESTAND, *ABO][:MAX_EINTRAEGE]
    assert len(misch) == MAX_EINTRAEGE
    for reihe in (misch, list(reversed(misch))):
        ergebnisse = _loese(client, [f["eintrag"] for f in reihe])
        assert [e["vorlage_id"] for e in ergebnisse] == [f["vorlage_id"] for f in reihe]
        assert [e["ampel"] for e in ergebnisse] == [_soll(f) for f in reihe]


def test_leere_liste_ergibt_leere_ergebnisse(client):
    assert _loese(client, []) == []


# --- AC-5: nie ein Fehler je Eintrag -----------------------------------------


def test_ac5_ungueltige_ampel_verliert_auch_ihre_vorlage(client):
    """Known Limitation: ist die Ampel ungueltig, zaehlt auch ihr ``template``
    nicht; es gilt ``preset_name`` bzw. ``profil``."""
    kaputt = {"template": "skitouren", "metrics": {
        "gust": {"upper": {"yellow": 90, "orange": 60, "red": 30}}}}
    e = _eins(client, {"ampel": kaputt, "preset_name": "wandern"})
    assert e["vorlage_id"] == "wandern"
    assert e["ampel"] == REF["vorlagen"]["wandern"]


@pytest.mark.parametrize("ampel", [
    "text", 7, True, [], ["x"],
    {"template": ["wandern"]},
    {"metrics": {"gust": {"alarm_ab": []}}},
    {"metrics": {"gust": {"alarm_ab": {"a": 1}}}},
    {"metrics": {"thunder": {"alarm_ab": []}}},
    {"metrics": {"gust": {"upper": [1, 2]}}},
    {"metrics": {"gust": None}},
    {"thunder": {"mittel": []}},
    {"thunder": {"hoch": {"a": 1}}},
    {"thunder": "rot"},
    {"metrics": {"wind_direction": {"modus": [], "sektoren": []}}},
    {"metrics": {"wind_direction": {"modus": "sektoren", "sektoren": [["N"]]}}},
], ids=repr)
def test_ac5_jede_ungueltige_ampel_faellt_auf_die_vorlage(client, ampel):
    """AC-5: eine ungueltige Ampel jeder Form ist kein Fehler; die Vorlage greift,
    und der zweite Eintrag wird normal beantwortet."""
    erster, zweiter = _loese(client, [
        {"ampel": ampel, "preset_name": "wandern"},
        {"ampel": {"template": "skitouren"}},
    ])
    assert erster == {"vorlage_id": "wandern", "ampel": REF["vorlagen"]["wandern"]}
    assert zweiter == {"vorlage_id": "skitouren", "ampel": REF["vorlagen"]["skitouren"]}


def test_ac5_unendliche_grenze_ist_ungueltig(client):
    """``1e999`` ist gueltiges JSON, aber keine Grenze (Frontend vor dem Umbau:
    ungueltig): Vorlage greift, kein Serverfehler."""
    antwort = _post_roh(client, '{"eintraege": [{"preset_name": "wandern", "ampel": '
                                '{"metrics": {"gust": {"upper": {"red": 1e999}}}}}]}')
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["ergebnisse"] == [
        {"vorlage_id": "wandern", "ampel": REF["vorlagen"]["wandern"]}]


# --- AC-6: Altbestand eigener Vorlagen ---------------------------------------


@pytest.mark.parametrize("fall", ALTBESTAND, ids=_name)
def test_ac6_altbestand_gleich_referenz(client, fall):
    """AC-6: nur ``metrics``-Liste -> „allgemein", nur die aktiven Metriken an."""
    e = _eins(client, fall["eintrag"])
    assert e["vorlage_id"] == "allgemein" == fall["vorlage_id"]
    assert e["ampel"] == _soll(fall)


def test_ac6_unlesbare_listenzeilen_werden_uebergangen(client):
    """Kein Eintrag erzeugt einen Fehler: unlesbare Zeilen zaehlen nicht."""
    muell = [None, 7, "gust", [], {}, {"enabled": True}, {"metric_id": None, "enabled": True},
             {"metric_id": ["gust"], "enabled": True}, {"metric_id": "wind", "enabled": True}]
    sauber = _eins(client, {"metrics": [{"metric_id": "wind", "enabled": True}]})
    assert _eins(client, {"metrics": muell}) == sauber
    an = [m for m, z in sauber["ampel"]["metrics"].items() if z["enabled"]]
    assert an == ["wind"]


def test_ac6_leere_metric_id_wird_uebergangen(client):
    """Eine Zeile ohne Namen ist unlesbar: keine Ampelzeile mit leerem Schluessel."""
    e = _eins(client, {"metrics": [{"metric_id": "", "enabled": True},
                                   {"metric_id": "wind", "enabled": True}]})
    assert set(e["ampel"]["metrics"]) == set(REF["vorlagen"]["allgemein"]["metrics"])
    assert [m for m, z in e["ampel"]["metrics"].items() if z["enabled"]] == ["wind"]


def test_ac6_leere_ampel_ist_abo_sicht(client):
    """Altbestand nur, wenn ``ampel`` fehlt oder null ist (nicht bei ``{}``)."""
    e = _eins(client, {"ampel": {}, "metrics": [{"metric_id": "gust", "enabled": True}]})
    assert e["ampel"] == REF["vorlagen"]["allgemein"]


# --- AC-7: Form, Fehler, Mandantentrennung -----------------------------------

FORMFEHLER = [
    "[]", "null", "42", '"x"', "{}", "", "{kaputt", '{"eintraege": NaN}',
    '{"eintraege": null}', '{"eintraege": {}}', '{"eintraege": "x"}',
    '{"eintraege": [null]}', '{"eintraege": ["x"]}', '{"eintraege": [[]]}',
    '{"eintraege": [{"preset_name": 7}]}', '{"eintraege": [{"preset_name": []}]}',
    '{"eintraege": [{"profil": true}]}', '{"eintraege": [{"profil": {}}]}',
    '{"eintraege": [{"metrics": {}}]}', '{"eintraege": [{"metrics": "gust"}]}',
    '{"eintraege": [{"ampel": {}, "metrics": 1}]}',
    '{"eintraege": [{"ampel": {"template": "wandern"}}, 5]}',
]


@pytest.mark.parametrize("rumpf", FORMFEHLER)
def test_ac7_formfehler_ist_400_ohne_teilantwort(client, rumpf):
    """AC-7: Formfehler -> 400 ``bad_request``, nichts teilweise beantwortet."""
    antwort = _post_roh(client, rumpf)
    assert antwort.status_code == 400, f"{rumpf}: {antwort.status_code} {antwort.text}"
    koerper = antwort.json()
    assert koerper["code"] == "bad_request"
    assert koerper["detail"]
    assert "ergebnisse" not in koerper


def test_ac7_hoechstens_32_eintraege(client):
    eintrag = {"ampel": {"template": "wandern"}}
    assert len(_loese(client, [eintrag] * MAX_EINTRAEGE)) == MAX_EINTRAEGE
    antwort = _post(client, {"eintraege": [eintrag] * (MAX_EINTRAEGE + 1)})
    assert antwort.status_code == 400
    assert antwort.json()["code"] == "bad_request"


def test_ac7_zwei_nutzer_gleiche_antwort_und_kein_dateizugriff_sichtbar(client):
    """AC-7: A (mit eigenem, abweichendem Bestand) und B (ohne) erhalten dieselbe
    Antwort; unter der Datenwurzel entsteht und aendert sich nichts."""
    from app.loader import get_data_root

    ordner = Path(get_data_root()) / "users" / NUTZER_A
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / "user.json").write_text(json.dumps({"id": NUTZER_A, "language": "en"}))
    (ordner / "metric_presets.json").write_text(json.dumps(
        [{"id": "x", "ampel": {"template": "skitouren"}}]))
    vorher = _baum()
    rumpf = {"eintraege": [f["eintrag"] for f in [*ALTBESTAND, *ABO][:MAX_EINTRAEGE]]}
    a, b = _post(client, rumpf, NUTZER_A), _post(client, rumpf, NUTZER_B)
    assert a.status_code == b.status_code == 200
    assert a.json() == b.json()
    assert "etag" not in a.headers
    assert _baum() == vorher
    assert not (Path(get_data_root()) / "users" / NUTZER_B).exists()


def test_ac7_fehlertext_in_der_sprache_des_nutzers(client):
    from app.loader import get_data_root

    ordner = Path(get_data_root()) / "users" / NUTZER_A
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / "user.json").write_text(json.dumps({"id": NUTZER_A, "language": "en"}))
    en, de = _post(client, [], NUTZER_A), _post(client, [], NUTZER_B)
    assert en.status_code == de.status_code == 400
    assert en.json()["detail"] != de.json()["detail"]


def test_ac7_ohne_user_id_kein_rueckfall(client):
    """Ohne ``user_id`` wird nicht still fuer einen Standardnutzer geantwortet."""
    antwort = client.post(PFAD, json={"eintraege": []})
    assert antwort.status_code in (400, 422), antwort.text


def test_endpunkt_ist_in_der_anwendung_registriert():
    """Der Router haengt an der echten Anwendung (``api/main.py``)."""
    from api.main import app

    assert any(getattr(r, "path", None) == PFAD and "POST" in getattr(r, "methods", ())
               for r in app.routes)


# --- Waechter: Inhalte, die sich nicht lesen, kopieren oder ausgeben lassen ---


def _post_bytes(client, inhalt: bytes):
    return client.post(PFAD, params={"user_id": NUTZER_A}, content=inhalt,
                       headers={"Content-Type": "application/json"})


def _roh_ergebnisse(client, *eintraege: str) -> list:
    antwort = _post_roh(client, '{"eintraege": [' + ", ".join(eintraege) + "]}")
    assert antwort.status_code == 200, antwort.text
    ergebnisse = antwort.json()["ergebnisse"]
    assert len(ergebnisse) == len(eintraege)
    return ergebnisse


def _vorlage(tid: str) -> dict:
    return {"vorlage_id": tid, "ampel": REF["vorlagen"][tid]}


_NICHT_AUSGEBBAR = {
    "1e999 neben den Grenzen": r'"metrics": {"gust": {"upper": {"red": 80, "x": 1e999}}}',
    "-1e999 neben den Grenzen": r'"metrics": {"gust": {"lower": {"x": -1e999}}}',
    "1e999 in der Metrik": r'"metrics": {"gust": {"enabled": true, "x": 1e999}}',
    "1e999 in modus": r'"metrics": {"wind_direction": {"modus": 1e999}}',
    "1e999 in thunder": r'"thunder": {"x": 1e999}',
    "1e999 als thunder.mittel": r'"thunder": {"mittel": 1e999}',
    "Surrogat im Metrik-Schluessel": r'"metrics": {"gu\ud800": {"enabled": true}}',
    "Surrogat im Textwert der Metrik": r'"metrics": {"gust": {"x": "\ud800"}}',
    "Surrogat im Textwert von thunder": r'"thunder": {"x": "a\udfffb"}',
}


@pytest.mark.parametrize("inhalt", _NICHT_AUSGEBBAR.values(), ids=_NICHT_AUSGEBBAR.keys())
def test_ac5_nicht_ausgebbare_ampel_faellt_auf_die_vorlage(client, inhalt):
    """Gueltiges JSON, das sich nicht wieder als JSON ausgeben laesst: 200, die
    ganze Ampel (samt ``template``) zaehlt nicht, der Nachbar ist normal."""
    erster, zweiter = _roh_ergebnisse(
        client, '{"preset_name": "wandern", "ampel": {"template": "skitouren", ' + inhalt + "}}",
        '{"ampel": {"template": "skitouren"}}')
    assert erster == _vorlage("wandern")
    assert zweiter == _vorlage("skitouren")


def test_ac5_surrogat_in_der_vorlagenkennung(client):
    erster, zweiter = _roh_ergebnisse(
        client, r'{"preset_name": "wandern", "ampel": {"template": "\ud800"}}',
        '{"ampel": {"template": "skitouren"}}')
    assert erster == _vorlage("wandern")
    assert zweiter == _vorlage("skitouren")


@pytest.mark.parametrize("feld", ["preset_name", "profil"])
def test_ac5_surrogat_in_preset_name_und_profil_ist_allgemein(client, feld):
    assert _roh_ergebnisse(client, '{"%s": "wand\\ud800"}' % feld) == [_vorlage("allgemein")]


def test_ac6_surrogat_im_altbestand_wird_uebergangen(client):
    wind = '{"metric_id": "wind", "enabled": true}'
    mit, ohne = _roh_ergebnisse(
        client, r'{"metrics": [{"metric_id": "gu\ud800", "enabled": true}, ' + wind + "]}",
        '{"metrics": [' + wind + "]}")
    assert mit == ohne
    assert [m for m, z in mit["ampel"]["metrics"].items() if z["enabled"]] == ["wind"]


def _tief(n: int) -> str:
    return ('{"eintraege": [{"preset_name": "wandern", "ampel": {"template": "skitouren", "thunder": {"x": '
            + "[" * n + "]" * n + '}}}, {"ampel": {"template": "skitouren"}}]}')


@pytest.mark.parametrize("tiefe", [500, 2000])
def test_ac5_tief_verschachtelte_ampel_ist_kein_serverfehler(client, tiefe):
    """Ob der Leser diese Tiefe noch annimmt, haengt an der Laufzeit; nimmt er
    sie an, greift die Vorlage, sonst ist es ein Formfehler."""
    antwort = _post_roh(client, _tief(tiefe))
    assert antwort.status_code in (200, 400), antwort.text
    if antwort.status_code == 400:
        assert antwort.json()["code"] == "bad_request"
        return
    assert antwort.json()["ergebnisse"] == [_vorlage("wandern"), _vorlage("skitouren")]


_UNLESBAR = {
    "100000 tief": _tief(100_000).encode(),
    "5000 Ziffern": b'{"eintraege": [{"ampel": {"x": ' + b"9" * 5000 + b"}}]}",
    "NaN": b'{"eintraege": [{"ampel": {"x": NaN}}]}',
    "Infinity": b'{"eintraege": [{"ampel": {"x": Infinity}}]}',
    "-Infinity": b'{"eintraege": [{"ampel": {"x": -Infinity}}]}',
    "kaputtes UTF-8": b'{"eintraege": [{"preset_name": "\xff"}]}',
    "Surrogat als UTF-8-Bytes": b'{"eintraege": [{"preset_name": "\xed\xa0\x80"}]}',
    "UTF-16": '{"eintraege": []}'.encode("utf-16"),
}


@pytest.mark.parametrize("inhalt", _UNLESBAR.values(), ids=_UNLESBAR.keys())
def test_ac7_unlesbarer_rumpf_ist_400(client, inhalt):
    antwort = _post_bytes(client, inhalt)
    assert antwort.status_code == 400, antwort.text[:300]
    assert antwort.json()["code"] == "bad_request"
    assert "ergebnisse" not in antwort.json()


@pytest.mark.parametrize("eintrag, vorlage", [
    ({"preset_name": "wandern"}, "wandern"),
    ({"ampel": {"template": "wandern"}}, "wandern"),
    ({"profil": "wandern"}, "wandern"),
    ({}, "allgemein"),
], ids=repr)
def test_display_config_im_eintrag_wirkt_nicht(client, eintrag, vorlage):
    """Nur die vier Felder des Entwurfs zaehlen, nie ein eingebettetes Abo."""
    fremd = {"preset_name": "skitouren", "ampel": {
        "template": "skitouren", "metrics": {"gust": {"upper": {"red": 7}}}}}
    assert _eins(client, {**eintrag, "display_config": fremd}) == _vorlage(vorlage)


def test_ac7_leere_user_id_wird_abgewiesen(client):
    antwort = _post(client, {"eintraege": []}, user="")
    assert antwort.status_code in (400, 422), antwort.text
    assert "ergebnisse" not in antwort.json()


@pytest.mark.parametrize("ampel, fehler", [
    ({"metrics": {"gust": {"alarm_ab": []}}}, ["gust.alarm_ab: unbekannt"]),
    ({"metrics": {"gust": {"alarm_ab": {}}}}, ["gust.alarm_ab: unbekannt"]),
    ({"metrics": {"thunder": {"alarm_ab": ["red"]}}}, ["thunder.alarm_ab: unbekannt"]),
    ({"thunder": {"mittel": []}}, ["thunder.mittel: unbekannt"]),
    ({"thunder": {"mittel": "red", "hoch": {}}}, ["thunder.hoch: nie gelb"]),
    ({"thunder": {"mittel": [], "hoch": []}}, ["thunder.mittel: unbekannt", "thunder.hoch: nie gelb"]),
], ids=repr)
def test_validate_ampel_nicht_hashbare_werte(ampel, fehler):
    assert validate_ampel(ampel) == fehler


@pytest.mark.parametrize("umbruch", ["\n", "\r", " ", "\x1b"], ids=ascii)
def test_warnzeile_zu_ungueltiger_ampel_einzeilig_und_begrenzt(client, caplog, umbruch):
    """Client-Schluessel stehen nie roh und nie unbegrenzt im Protokoll."""
    kurz = "gu" + umbruch + "WARNING gefaelscht"
    for schluessel in (kurz, kurz + "x" * 100_000):
        caplog.clear()
        with caplog.at_level(logging.WARNING, logger="app.ampel"):
            ergebnis = _eins(client, {"ampel": {"metrics": {schluessel: None}}, "preset_name": "wandern"})
        assert ergebnis == _vorlage("wandern")
        zeilen = [r.getMessage() for r in caplog.records if r.name == "app.ampel"]
        assert len(zeilen) == 1 and "ungueltig" in zeilen[0] and "gefaelscht" in zeilen[0]
        assert umbruch not in zeilen[0]
        assert len(zeilen[0]) <= 600


@pytest.mark.parametrize("wert", ["1e999", r'"\ud800"'])
def test_warnzeile_zu_nicht_ausgebbarer_ampel(client, caplog, wert):
    """Genau eine Zeile je betroffenem Eintrag, ohne Inhalt des Clients."""
    with caplog.at_level(logging.WARNING, logger="app.ampel"):
        _roh_ergebnisse(client, '{"preset_name": "wandern", "ampel": {"template": "skitouren", '
                        '"metrics": {"gust": {"geheim": %s}}}}' % wert, '{"preset_name": "wandern"}')
    zeilen = [r.getMessage() for r in caplog.records if r.name == "app.ampel"]
    assert zeilen == ["Profil-Ampel nicht als JSON ausgebbar, Vorlage greift"]


@pytest.mark.parametrize("feld", ["ampel.template", "preset_name", "profil"])
@pytest.mark.parametrize("schwanz", ["", "x" * 100_000], ids=["kurz", "lang"])
def test_warnzeile_zu_unbekannter_vorlage_einzeilig_und_begrenzt(client, caplog, feld, schwanz):
    wert = "fremd\nWARNING gefaelscht" + schwanz
    eintrag = {"ampel": {"template": wert}} if feld == "ampel.template" else {feld: wert}
    with caplog.at_level(logging.WARNING, logger="app.ampel"):
        assert _eins(client, eintrag) == _vorlage("allgemein")
    zeilen = [r.getMessage() for r in caplog.records if r.name == "app.ampel"]
    assert len(zeilen) == 1 and "nutze allgemein" in zeilen[0]
    assert r"fremd\nWARNING gefaelscht" in zeilen[0] and "\n" not in zeilen[0]
    assert len(zeilen[0]) <= 600


# --- AC-19: Aufloesung der Renderer unveraendert (Waechter, von Anfang an gruen) ---


@pytest.mark.parametrize("fall", ABO, ids=_name)
def test_ac19_resolve_ampel_unveraendert(fall):
    """AC-19: die Quelle der vier Kanaele liefert die eingefrorene Referenz und
    veraendert weder Eingabe noch Vorlagen."""
    eintrag = copy.deepcopy(fall["eintrag"])
    assert resolve_ampel(eintrag) == _soll(fall)
    assert eintrag == fall["eintrag"]


# Orakel sind die Vorlagenfarben: wandern orange/red, wassersport red/red.
_GEWITTER_NULL = [
    ("wandern", {"mittel": None, "hoch": "orange"}, {"mittel": "orange", "hoch": "orange"}),
    ("wandern", {"mittel": "red", "hoch": None}, {"mittel": "red", "hoch": "red"}),
    ("wandern", {"mittel": None, "hoch": None}, {"mittel": "orange", "hoch": "red"}),
    ("wassersport", {"mittel": None, "hoch": "orange"}, {"mittel": "red", "hoch": "orange"}),
    ("wassersport", {"mittel": "yellow", "hoch": None}, {"mittel": "yellow", "hoch": "red"}),
    ("wassersport", {"mittel": None, "hoch": None}, {"mittel": "red", "hoch": "red"}),
]


@pytest.mark.parametrize("vorlage, thunder, soll", _GEWITTER_NULL)
def test_ac19_gewitter_null_ist_vorlagenfarbe(vorlage, thunder, soll):
    """AC-19: null je Gewitter-Schluessel ist keine Abweichung, sondern Vorlage."""
    erwartet = {**REF["vorlagen"][vorlage], "thunder": soll}
    for abo in ({"ampel": {"template": vorlage, "thunder": thunder}},
                {"ampel": {"thunder": thunder}, "preset_name": vorlage}):
        assert resolve_ampel(abo) == erwartet
        assert resolve_ampel({"display_config": abo}) == erwartet


@pytest.mark.parametrize("vorlage, thunder, soll", _GEWITTER_NULL)
def test_ac4_gewitter_null_ist_vorlagenfarbe_am_endpunkt(client, vorlage, thunder, soll):
    e = _eins(client, {"ampel": {"template": vorlage, "thunder": thunder}})
    assert e == {"vorlage_id": vorlage, "ampel": {**REF["vorlagen"][vorlage], "thunder": soll}}
