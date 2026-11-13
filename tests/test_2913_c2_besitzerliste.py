# doc-compliance-test
"""TDD RED — Issue #2913 Scheibe c2 (Seitenkopf), AC-12: Besitzerliste des Ganzseiten-Abgleichs.

Spec: docs/specs/modules/feat_2913_c2_seitenkopf.md (AC-12, Scope Punkt 6).
Daten: docs/context/einstellungen_neu/elementliste_besitzer.json (gelesen von
frontend/e2e/elementliste_abgleich_logik.ts: leseBesitzer, leseAusnahmen).

Doku-Daten-Test (Marker oben): die Besitzerliste IST Daten, die der Abgleich-Lauf
liest; geprüft wird ihr Inhalt, nicht Quelltext.

Vertrag für den Developer:
  - kein Eintrag mit verweis "#2913-c2" mehr;
  - Tempo-Karte (art=abschnitt, ctx=trip, reiter=etappen, abschnitt=tempo) und die
    20 Profil-Options-Texte (Trip-Aktivitäten DE/EN, Orte-Profile DE/EN) sind auf
    verweis "#2796" umgehängt, grund enthält „Scheibe S4, Datenmodell+Migration“;
  - die 8 #2797-Einträge („Test schicken“-Menü, Kebab) bleiben unverändert;
  - Einträge anderer Scheiben (#2967, #2966, #2913-d, #2913-e, #2795) bleiben
    unverändert (Anzahl je Verweis gleich);
  - Ausnahmen: die bisherigen zwei bleiben; neu je Kontext (trip, orte) eine
    Ausnahme für die Bearbeiten-Texte von Name/Region („Name bearbeiten“,
    „Region bearbeiten“, „Edit name“, „Edit region“) mit
    spec = docs/specs/modules/feat_2913_c2_seitenkopf.md.

Ausführen: uv run pytest tests/test_2913_c2_besitzerliste.py -v
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BESITZER = ROOT / "docs" / "context" / "einstellungen_neu" / "elementliste_besitzer.json"
C2_SPEC = "docs/specs/modules/feat_2913_c2_seitenkopf.md"
S4_GRUND = "Scheibe S4, Datenmodell+Migration"


@pytest.fixture(scope="module")
def daten() -> dict:
    return json.loads(BESITZER.read_text(encoding="utf-8"))


def _verweise(daten: dict) -> Counter:
    return Counter(b["verweis"] for b in daten["besitzer"])


def test_ac12_kein_eintrag_mehr_mit_verweis_2913_c2(daten):
    rest = [b for b in daten["besitzer"] if b["verweis"] == "#2913-c2"]
    assert rest == [], f"{len(rest)} Besitzer-Einträge tragen noch #2913-c2"


def test_ac12_tempo_karte_haengt_an_2796(daten):
    treffer = [
        b
        for b in daten["besitzer"]
        if b["art"] == "abschnitt"
        and b.get("ctx") == "trip"
        and b.get("reiter") == "etappen"
        and b.get("abschnitt") == "tempo"
    ]
    assert len(treffer) == 1, f"Tempo-Abschnitt {len(treffer)}× in der Besitzerliste (erwartet 1, nicht gelöscht)"
    assert treffer[0]["verweis"] == "#2796", f"Tempo verweist auf {treffer[0]['verweis']}"
    assert S4_GRUND in treffer[0]["grund"], f"Grund ohne „{S4_GRUND}“: {treffer[0]['grund']}"


PROFIL_TEXTE = {
    "trip": [
        "Trekking", "Skitour", "Hochtour", "Klettersteig", "Fahrrad ({zahl} km/h)", "MTB",
        "Ski touring", "Mountaineering", "Via ferrata", "Bike ({zahl} km/h)",
    ],
    "orte": [
        "Allgemein", "Wandern", "Wintersport", "Sommer-Trekking", "· Wandern",
        "General", "Hiking", "Winter sports", "Summer trekking", "· Hiking",
    ],
}


@pytest.mark.parametrize(
    "ctx,text", [(c, t) for c, liste in PROFIL_TEXTE.items() for t in liste]
)
def test_ac12_profil_texte_haengen_an_2796(daten, ctx, text):
    treffer = [
        b
        for b in daten["besitzer"]
        if b["art"] == "zusaetzlich"
        and b.get("ctx") == ctx
        and b.get("reiter") is None
        and (b.get("text") == text or b.get("muster") == text)
    ]
    assert treffer, f"Profil-Text „{text}“ ({ctx}) fehlt in der Besitzerliste — umhängen, nicht löschen (AC-12)"
    for b in treffer:
        assert b["verweis"] == "#2796", f"„{text}“ ({ctx}) verweist auf {b['verweis']}, erwartet #2796"
        assert S4_GRUND in b["grund"], f"„{text}“ ({ctx}): Grund ohne „{S4_GRUND}“"


MENUE_2797 = {
    (ctx, "wetter", a)
    for ctx in ("trip", "orte")
    for a in ("kebab-bestaetigung-archivieren", "kebab-bestaetigung-loeschen", "kebab-menue", "test-menue")
}


def test_ac12_acht_menue_eintraege_bleiben_bei_2797(daten):
    eintraege = [b for b in daten["besitzer"] if b["verweis"] == "#2797"]
    assert len(eintraege) == 8, f"#2797: {len(eintraege)} Einträge (erwartet 8)"
    assert {(b["ctx"], b["reiter"], b["abschnitt"]) for b in eintraege} == MENUE_2797
    for b in eintraege:
        assert b["art"] == "abschnitt"


def test_ac12_eintraege_anderer_scheiben_unveraendert(daten):
    soll = {"#2967": 47, "#2966": 35, "#2913-d": 12, "#2913-e": 6, "#2795": 2, "#2797": 8}
    ist = _verweise(daten)
    assert {k: ist.get(k, 0) for k in soll} == soll


def test_ac12_umgehaengte_eintraege_mindestens_profil_plus_tempo(daten):
    anzahl = _verweise(daten).get("#2796", 0)
    mindest = sum(len(v) for v in PROFIL_TEXTE.values()) + 1
    assert anzahl >= mindest, f"#2796: {anzahl} Einträge, erwartet mindestens {mindest} (20 Profil-Texte + Tempo)"


def test_ac12_jeder_eintrag_hat_grund_und_gueltigen_verweis(daten):
    for i, b in enumerate(daten["besitzer"]):
        assert b.get("grund", "").strip(), f"Eintrag {i} ohne Grund"
        assert re.fullmatch(r"#\d+|#2913-[a-z]\d?", b.get("verweis", "")), f"Eintrag {i}: Verweis {b.get('verweis')!r}"


def _trifft(ausnahme: dict, ctx: str, text: str) -> bool:
    if ausnahme.get("ctx") not in (None, ctx):
        return False
    if ausnahme.get("text") == text:
        return True
    muster = ausnahme.get("muster")
    if not muster:
        return False
    teile = re.split(r"\{[^}]+\}", muster)
    return re.fullmatch(".+".join(re.escape(t) for t in teile), text) is not None


BEARBEITEN_TEXTE = ["Name bearbeiten", "Region bearbeiten", "Edit name", "Edit region"]


@pytest.mark.parametrize("ctx,text", [(c, t) for c in ("trip", "orte") for t in BEARBEITEN_TEXTE])
def test_ac12_ausnahme_name_region_bearbeiten_mit_spec_verweis(daten, ctx, text):
    passend = [
        a for a in daten["ausnahmen"]
        if a.get("spec") == C2_SPEC and a.get("reiter") is None and _trifft(a, ctx, text)
    ]
    assert passend, f"keine Ausnahme mit spec={C2_SPEC} für „{text}“ ({ctx})"
    for a in passend:
        assert a.get("grund", "").strip(), "Ausnahme ohne Grund"


def test_ac12_bisherige_ausnahmen_bleiben(daten):
    alt = [a for a in daten["ausnahmen"] if a.get("spec") == "docs/specs/modules/feat_2913_abgleich_ganzseite.md"]
    assert {(a["ctx"], a["reiter"], a["muster"]) for a in alt} == {
        ("trip", "uebersicht", "{text}"),
        ("orte", "uebersicht", "{text}"),
    }
