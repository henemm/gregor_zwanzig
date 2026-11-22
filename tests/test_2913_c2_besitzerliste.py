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
    # #2795 (Scheibe d, Reiter Zustellung) hat am 15.11. die 12 Sammel-Einträge #2913-d durch Element-
    # und Text-Besitzer ersetzt (#2795 Übergangsblock/a11y, #2967 Kontodaten, #2968 EN-Lücke, #3022 Orte-Ladezustand).
    # #2966 (Haken im Reiter Wetter) hat am 17.11. seine 35 Einträge abgeräumt; Restabweichungen werden nach
    # dem Staging-Abnahmelauf neu zugeordnet (AC-10 der Spec feat_2966_abgleich_haken): Dialog-Abweichungen im
    # Reiter Wetter → #3111 (156), Mockup-Beispieldaten → #2967 (+80), EN-Lücke → #2968 (+276), Orte-Ladezustand → #3022 (+3).
    # #3122 (ADR-0124, Mockup Fassung 4, 17.11.): die zwei Abschnitts-Besitzer kanal-inhalt (#2795) heißen jetzt was-steht-wo und hängen an #3122.
    # #3007 (Listen Etappen/Orte) räumt #2913-e ab; den Rest (nur Köpfe) prüft tests/test_3007_besitzerliste.py.
    # #2968 (EN-Zuordner, 19.11.) räumt alle 446 Verweise #2968 ab: 442 entfallen (Lücke geschlossen, EN
    # eindeutig bzw. als Alternativen geführt, Grenzen-Beschriftung „gelb >“ über Regel e, zusaetzlich jetzt
    # erklärt), vier englische Live-Texte der bewussten Abweichung → #2795.
    # #3192 (20.11.): 156 #3111-Einträge abgeräumt, DE-Abgleich auf Mockup-Lage hat alle gefunden. 52 entfallen
    # (EN nach Neuerzeugung der Elementliste aus dem Katalog), 100 EN-Lücken → #3194 (EN-Sollwert nicht automatisch
    # zuordenbar), 4 EN-Lücken „eigene · aus GR221 gespeichert“ → #3151 (Mockup-Beispieldaten).
    # #3151 (20.11.): 247 #2967 nach Seed mit Kanalauswahl und Abgleich DE+EN neu klassifiziert: 181 aufgelöst
    # (179 entfallen, 2 EN-Lücken „Mallorca Frühling“ brauchen einen Besitzer ≠ #2968 → #3194), 66 umgehängt:
    # Kanalzeile → #3202 (23), Grünbereich/Metriken/Kein-Alarm/„:00“ → #3203 (19), Anzeige-Metriken Trip → #3204
    # (10), Vorlagen-Auswahl Orte/Zurücksetzen → #3205 (4), gesperrt → #3122 (+4), nur-EN-Zusatztexte → #3194 (+6).
    # #3194 (20.11., Regel g „zusammengesetzt“ im EN-Zuordner): 100 Dialogtext-Lücken (Grenzen-Titel 54,
    # Grünhinweis/Gewitter-Hinweis + abweichend 42, Bestätigungs-Rumpf 4) aus Katalog-Schlüsselfolgen zugeordnet
    # und abgeräumt; Rest 8: „Mallorca Frühling“ (2, Kontodaten) und 6 nur-EN-Zusatztexte (Metrik-Register, Einheit+Hinweis).
    # #3202 (21.11., Spec feat_3202_kanalzeile_mockup.md): Kanalzeile gekürzt wie Mockup Fassung 4, alle 23 Einträge
    # abgeräumt; Mockup angeglichen (Telegram „verbunden“ ohne @name, E-Mail ohne „+1 Empfänger“, PO 20./21.11.)
    # und Elementliste neu erzeugt — keine Ausnahme, keine Umhängung.
    # #3203 (21.11., Spec feat_3203_metrikzeilen_mockup.md): alle 19 Einträge abgeräumt. Abgleich zählt sichtbaren
    # Text unter aria-hidden (Skala, Gewitter-Stufen, „· grün: …“, Reihenfolge), Mockup-Vorbotensatz an Live
    # angeglichen und Elementliste neu erzeugt (PO 21.11.); „:00“ ist Ausnahme (Stundenraster, feat_2913_scheibe_c_wetter_rest).
    # Die zwei Abschnitt-Einträge metriken deckten nebenbei 16 EN-Lücken (Metriknamen aus dem Register, Einheit+
    # Hinweis, Grünbereich ohne Einheit) ab; sie bekommen je einen Element-Besitzer #3194 (gleiche Klasse wie dessen
    # nur-EN-Zusatztexte): #3194 8 → 24. Fix-Loop 1 (EN-Staging-Abgleich 21.11.): weitere 6 EN-Einträge „mm · Summe“/
    # „m · Minimum“ (EN-Live-Text ohne EN-Listeneintrag) und der Zusatztext „· green: up to {zahl}“ → #3194 (24 → 31);
    # 32 EN-Chips „+ {metrik}“ (EN-Abgleich prüft nur das Muster) → neues Issue #3241.
    # Fix-Loop 1b: Besitzer zeigen nie auf geschlossene Issues. #3194 ist geschlossen: alle nur-EN-Restfälle
    # (29) → #3241 (erweitert, 32 + 29 = 61); „Mallorca Frühling“ (2, Kontoname im Prüfkonto, kein
    # Übersetzungsfall) → #3009 (Abnahme, offen). #3194 damit 0.
    # #3204 (21.11., Spec feat_3204_anzeige_metriken_mockup.md): alle 10 Einträge abgeräumt. Mockup Fassung 4
    # zeigt Tages-Tief/-Hoch (Gehzeit) als Nur-Anzeige-Zeilen wie die App, App-Erklärsatz folgt dem Mockup
    # („unter „Was steht wo““); Elementliste neu erzeugt — keine Ausnahme, keine Umhängung.
    # #3205 (21.11., Spec feat_3205_vorlagen_mockup.md): alle 4 Einträge abgeräumt. Mockup Fassung 4 führt eigene
    # Vorlagen je Art wie die App (PO 08.11./21.11.); die zwei Orte-Auswahl-Einträge „Mallorca Frühling“ entfallen
    # mit dem Soll-Eintrag, ebenso die zwei #3151-Unterzeilen „eigene · aus GR221 gespeichert“ der Orte-Auswahl
    # (Besitzer auf entfallene IDs wären ein Fehler, F004): #3151 4 → 2. Die Zurücksetzen-Zeile (DE/EN) ist ein
    # Zustandsunterschied (Mockup Z. 511 `devs>0` = live `abweichungen > 0`, Prüfkonto-Trip mit Abweichung) und
    # stand als begründete Ausnahme (Weg B) mit spec feat_3205_vorlagen_mockup.md, nicht mehr als Besitzer.
    # #3251 (21.11., Spec feat_3251_abweichungszustand_vorlage.md): diese Ausnahme ist gestrichen. Die Elementliste
    # führt den Abweichungszustand als Script-Abschnitt vorlage-abweichung („▾ 1 Abweichung“, Zurücksetzen-Zeile),
    # der Abgleich prüft ihn auf dem Prüf-Datensatz mit Abweichung. Zählwerte unverändert (keine Besitzer betroffen).
    # #3258 (22.11., Spec feat_3258_sms_kuerzel_legende.md): Legende „Kürzel erklärt“ im Mockup, Elementliste führt
    # Kürzel (sprachneutral) und Bedeutungen (EN aus wetter.wsw.legende.* bzw. Server-Katalog-Schnappschuss
    # daten/kuerzel_bedeutung.json). Besitzer nur für die datensatzabhängigen SMS-Beispielwerte des Trips als
    # {zahl}-Muster: FN, FD/…, „TF- FN FD“ und die ganze SMS-Zeile → #3258 (4).
    soll = {
        "#2967": 0, "#2966": 0, "#2913-d": 0, "#2795": 318, "#2797": 8, "#2968": 0, "#3022": 62,
        "#3111": 0, "#3194": 0, "#3241": 61, "#3009": 2, "#3151": 2, "#3122": 14, "#3202": 0, "#3203": 0, "#3204": 0,
        "#3205": 0, "#3145": 0, "#3258": 4,
    }
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
    # #2969: Die Pauschal-Ausnahmen der Übersicht (Muster „{text}“) sind durch Einzel-Ausnahmen ersetzt
    # (Spec feat_2969_elementliste_uebersicht.md, Test elementliste_uebersicht_2969.test.ts); keine andere
    # Ausnahme der Vorgänger-Spec darf entstehen.
    alt = [a for a in daten["ausnahmen"] if a.get("spec") == "docs/specs/modules/feat_2913_abgleich_ganzseite.md"]
    assert alt == []
