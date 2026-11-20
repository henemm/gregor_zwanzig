"""Pruefkatalog "Einstellung = Mail", Kontext Orte (Issue #3047, Paket B).

SPEC: docs/specs/modules/feat_3047_einstellung_gleich_mail_pruefkatalog.md
(§1-§4, §7; AC-5, AC-6, AC-7, AC-8 Orte, AC-10 Orte, AC-11 Orte, AC-12 Orte,
AC-21).

Kette wie im Betrieb: rohes Preset-JSON (Persistenzformat des Editors) im
Nutzerverzeichnis einer isolierten Datenwurzel -> echter Loader ->
``send_one_compare_preset(..., mail_sink=...)``; der Sink nimmt ``plain_body``
an, HTML und Klartext stammen also aus DERSELBEN Mail. Wetter offline aus
``tests/helpers/vergleichs_mail_fixture.build_result``. Kein ``Mock()``,
kein ``patch()``; Naht nur am Transport und an der Wetter-Engine (echte
Subklasse), siehe ``tests/helpers/einstellung_gleich_mail_orte.py``.

Das Soll kommt aus dem rohen JSON, das nach dem Ablegen von der Platte
zurueckgelesen wird, und aus den statischen Beschriftungen des Registers --
nie aus ``resolve_*``. Reihenfolgen werden nie sortiert verglichen; jede
eingestellte Folge ist ungleich der Katalogfolge (Vorbedingung im Test).

Fallliste: ``tests/fixtures/einstellung_gleich_mail/fallliste_orte.json``.
Die paarweisen Faelle (Spec §3) tragen ``werte``; die Tests unten bauen aus
genau diesen Werten das rohe Preset (eine Quelle, kein Abschreiben).

RED (``xfail(strict=True)``, Status ``rot_erwartet``):
* O5 / AC-10: der Stundenverlauf nimmt eine aus der Grundauswahl
  abgewaehlte Metrik weiter auf (``resolve_hourly_metrics`` ohne Schnitt,
  ``src/services/report_config_resolver.py:291``).
* WV6: im Klartext steht die amtliche Warnung hinter statt vor den
  Metrik-Zeilen (``src/output/renderers/comparison.py:310-313``).

Behoben (F4): O3 / AC-21 -- der feste Klartext-Ausblick zeigt dieselben
sieben Spalten wie das HTML (``src/output/renderers/email/outlook.py``).

F8 (#3039 auf main): Roh/Einfach der Vergleichstabelle aus
``channel_layouts.email`` ist kein ``offen_feature`` mehr (W11-Faelle gruen,
paarweise mit Darstellung). Offen (``rot_erwartet``): Totalschnitt einer nicht
leeren ``channel_active_metrics.email``-Liste -> leere Tabelle statt Rueckfall
(AC-10, ``resolve_channel_enabled_metrics``).

Golden (AC-11): ``orte_altbestand*.golden.{html,txt}`` frieren den Ist-Stand
byte-genau ein (feste Kennung, feste Uhr, feste Wetterdaten). Die Golden
``orte_altbestand_ohne_grundauswahl.golden.txt`` traegt seit F4 EINZELN die
AC-21-Korrektur (nur die Ausblick-Zeilen, nie pauschal neu eingefroren).
Bewusstes Neuschreiben: ``EINSTELLUNG_GLEICH_MAIL_GOLDEN_SCHREIBEN=1``.
"""
from __future__ import annotations

import json
import os
import re

import pytest

from tests.helpers.einstellung_gleich_mail_orte import (
    FIXTURE_DIR,
    ORTE,
    grundauswahl,
    html_ausblick,
    html_stundenverlauf,
    html_vergleichstabelle,
    html_vergleichszellen,
    ist_zahl,
    katalogfolge,
    katalogtext,
    kennungen,
    klartext_ausblick,
    klartext_stundenverlauf,
    klartext_vergleichstabelle,
    klartext_vergleichswerte,
    kopf_von,
    preset_dict,
    sende_orte_mail,
    soll_ausblick,
    soll_einfach,
    soll_stundenverlauf,
    soll_vergleichsformen,
    soll_vergleichstabelle,
)
from tests.helpers.einstellung_gleich_mail_trip import zellform

FALLLISTE = FIXTURE_DIR / "fallliste_orte.json"
NAME_JE_ID = {lid: v[0] for lid, v in ORTE.items()}
AGG = {"temperature": "max", "wind": "max", "gust": "max", "precipitation": "sum",
       "rain_probability": "max", "uv_index": "max", "visibility": "min"}
POOL = ("temperature", "wind", "gust", "precipitation", "rain_probability")
TEILMENGE = ("temperature", "wind", "precipitation")
GEMISCHT_RANG = ("wind", "temperature", "precipitation", "rain_probability", "gust")
#: Spec §2.3 / #814 AC-5 / #2049: Groessen mit Einfach-Form im Ausblick (Auszug
#: fuer die Katalog-Metriken dieses Pakets) -- von Hand gesetztes Orakel.
AUSBLICK_EINFACH_FAEHIG = frozenset({"wind", "gust", "precipitation", "rain_probability"})


def _am(ids) -> list[dict]:
    return [{"metric_id": i, "aggregation": AGG[i]} for i in ids]


def _orte(roh: dict) -> list[str]:
    return [NAME_JE_ID[lid] for lid in roh["location_ids"]]


def _standard_stunden() -> tuple[str, ...]:
    """Standardliste "nie eingestellt" von Hand (Soll, kein Spiegel der
    Register-Konstante; #3096: die Vorgabe loest allein
    ``compare_hourly_metric_ids`` auf, der Renderer fuehrt keine eigene).
    Ob sie der Editor-Vorgabe gleicht, prueft Paket D (AC-13,
    ``editor_standard.json``)."""
    return (
        "temperature", "wind_chill", "wind", "gust", "precipitation",
        "uv_index", "thunder", "rain_probability", "visibility",
    )


# ---------------------------------------------------------------------------
# Pruefbausteine je Liste (Soll aus dem rohen JSON)
# ---------------------------------------------------------------------------


def pruefe_vergleichstabelle(mail, fmt: str) -> None:
    soll = soll_vergleichstabelle(mail.roh)
    orte = _orte(mail.roh)
    if fmt == "html":
        ist_orte, ist = html_vergleichstabelle(mail.html)
        assert ist_orte == orte, f"HTML Orte-Spalten {ist_orte}, eingestellt {orte}"
        assert ist == soll, f"HTML Zeilen {ist}, eingestellt {soll} (Nutzer {mail.uid})"
    else:
        folge, zeilen = klartext_vergleichstabelle(mail.plain)
        assert folge == orte, f"Klartext Orts-Bloecke {folge}, eingestellt {orte}"
        for ort in orte:
            assert zeilen[ort] == soll, f"Klartext {ort}: Zeilen {zeilen[ort]}, eingestellt {soll}"
    pruefe_vergleichsformen(mail, fmt)


def pruefe_vergleichsformen(mail, fmt: str) -> None:
    """#3039 / Konzept W11: Roh-Zeile zeigt eine Zahl, Einfach-Zeile Ampelpunkt,
    Wort oder Symbol (ohne Ziffer) -- in jeder Ortsspalte bzw. jedem Ortsblock."""
    soll = soll_vergleichsformen(mail.roh)
    if fmt == "html":
        zellen = html_vergleichszellen(mail.html)
        ist = {mid: [zellform(text, frag) for text, frag in zellen[mid]] for mid in soll}
    else:
        werte = klartext_vergleichswerte(mail.plain)
        ist = {mid: [zellform(werte[ort][mid]) for ort in _orte(mail.roh)] for mid in soll}
    for mid, formen in ist.items():
        assert formen == [soll[mid]] * len(formen), (
            f"{fmt}: Zeile {mid} steht auf {soll[mid]}, Zellen {formen} (Nutzer {mail.uid})")


def pruefe_stundenverlauf(mail, fmt: str, lang: str = "de") -> None:
    soll = soll_stundenverlauf(mail.roh, _standard_stunden())
    ist = (html_stundenverlauf(mail.html, lang) if fmt == "html"
           else klartext_stundenverlauf(mail.plain, lang))
    if soll is None:
        assert ist == {}, f"{fmt}: Stundenverlauf muss entfallen, gefunden {ist}"
        return
    assert list(ist) == _orte(mail.roh), f"{fmt}: Orte im Stundenverlauf {list(ist)}"
    for ort, koepfe in ist.items():
        assert koepfe == soll, f"{fmt} {ort}: Spalten {koepfe}, eingestellt {soll}"


def pruefe_ausblick(mail, fmt: str, *, darstellung: bool = True, lang: str = "de") -> None:
    soll = soll_ausblick(mail.roh)
    ist = (html_ausblick(mail.html, lang) if fmt == "html"
           else klartext_ausblick(mail.plain, lang))
    if soll is None:
        assert ist == {}, f"{fmt}: Ausblick muss entfallen, gefunden {list(ist)}"
        titel = katalogtext("vergleich.ausblick.titel", lang)
        assert titel not in mail.plain.splitlines() or fmt == "html"
        return
    assert list(ist) == _orte(mail.roh), f"{fmt}: Orte im Ausblick {list(ist)}"
    einfach = soll_einfach(mail.roh)
    for ort, zellen in ist.items():
        assert kennungen(zellen) == soll, (
            f"{fmt} {ort}: Ausblick-Spalten {[k for k, _ in zellen]}, eingestellt {soll}")
        for kopf, zelle in zellen:
            mid = kennungen([kopf])[0]
            if mid == "temperature":
                assert re.match(r"^-?\d+°?/-?\d+", zelle), f"{fmt} {ort}: Temp keine Spanne Tief/Hoch: {zelle!r}"
            elif darstellung and einfach.get(mid) and mid in AUSBLICK_EINFACH_FAEHIG:
                assert not ist_zahl(zelle), f"{fmt} {ort}: {kopf} steht auf Einfach, zeigt {zelle!r}"
            elif darstellung:
                assert ist_zahl(zelle), f"{fmt} {ort}: {kopf} steht auf Roh, zeigt {zelle!r}"


PRUEFE = {
    "orte_vergleichstabelle": pruefe_vergleichstabelle,
    "orte_stundenverlauf": pruefe_stundenverlauf,
    "orte_ausblick": pruefe_ausblick,
}


# ---------------------------------------------------------------------------
# Paarweise Faelle (Spec §3) -- Preset aus den ``werte`` der Fallliste
# ---------------------------------------------------------------------------


def _folge(ids, reihenfolge: str) -> list[str]:
    katalog = katalogfolge(ids)
    if reihenfolge == "katalog":
        return katalog
    if reihenfolge == "umkehrung":
        return katalog[::-1]
    gemischt = [m for m in GEMISCHT_RANG if m in ids]
    assert gemischt not in (katalog, katalog[::-1]), "gemischt muss von Katalog und Umkehrung abweichen"
    return gemischt


def _formate(ids, darstellung: str) -> dict[str, bool]:
    faehig = [m for m in ids if m in AUSBLICK_EINFACH_FAEHIG]
    if darstellung == "roh":
        return {m: False for m in faehig}
    if darstellung == "einfach":
        return {m: True for m in faehig}
    gemischt = {m: i % 2 == 0 for i, m in enumerate(faehig)}
    assert set(gemischt.values()) == {True, False}, "gemischt braucht Roh UND Einfach"
    return gemischt


#: Register-Groessen mit mehr als einer Darstellung (``format_modes``) aus
#: POOL -- von Hand gesetztes Orakel fuer die Vergleichstabelle (#3039).
VERGLEICH_EINFACH_FAEHIG = ("wind", "gust", "precipitation")


def _layout(folge, darstellung: str) -> list[dict]:
    """``channel_layouts.email`` (#3039) in der Fall-Folge. Einfach: jede Zeile
    ``true`` (auch die ohne Einfachform -> bleibt Zahl, #3039 AC-8). Gemischt:
    die einfach-faehigen Zeilen abwechselnd ``true`` / ohne Angabe (= Roh,
    #3039 AC-7), die uebrigen ausdruecklich ``false``. POOL-Groessen ausserhalb
    der Folge stehen als ``enabled: false`` (sonst kaemen sie als "neu" hinten)."""
    faehig = [m for m in folge if m in VERGLEICH_EINFACH_FAEHIG]
    eintraege = []
    for m in folge:
        e = {"metric_id": m, "enabled": True}
        if darstellung == "einfach":
            e["use_friendly_format"] = True
        elif m in faehig:
            if faehig.index(m) % 2 == 0:
                e["use_friendly_format"] = True
        else:
            e["use_friendly_format"] = False
        eintraege.append(e)
    if darstellung == "gemischt":
        assert len(faehig) >= 2, "gemischt braucht Roh UND Einfach"
    return eintraege + [{"metric_id": m, "enabled": False, "use_friendly_format": True}
                        for m in POOL if m not in folge]


def preset_aus_werten(liste: str, werte: dict) -> dict:
    """Rohes Preset aus ``orte_basis.json`` plus den Dimensionswerten eines Falls."""
    p = preset_dict("basis")
    p["id"] = "orte-paarweise"
    dc = p["display_config"]
    muster, reihenfolge = werte["auswahl_muster"], werte["reihenfolge"]
    folge = _folge(TEILMENGE if muster == "teilmenge" else POOL, reihenfolge)
    feld = {"orte_stundenverlauf": "hourly_metrics", "orte_ausblick": "outlook_metrics"}.get(liste)
    if muster == "nie_eingestellt":
        if liste != "orte_stundenverlauf":
            dc["active_metrics"] = _am(folge)  # Grundauswahl in der Fall-Folge, Liste ohne Eintrag
    elif liste == "orte_vergleichstabelle" and werte["darstellung"] != "roh":
        dc["channel_layouts"] = {"email": _layout(folge, werte["darstellung"])}
    elif liste == "orte_vergleichstabelle":
        dc["channel_active_metrics"] = {"email": [] if muster == "bewusst_leer" else _am(folge)}
    else:
        dc[feld] = [] if muster == "bewusst_leer" else list(folge)
    if liste == "orte_ausblick":
        dc["outlook_metric_formats"] = _formate(folge, werte["darstellung"])
    return p


def _paarweise(liste: str) -> list:
    faelle = json.loads(FALLLISTE.read_text(encoding="utf-8"))["faelle"]
    return [pytest.param(f, id=f["id"]) for f in faelle if f["liste"] == liste and "werte" in f]


def _paarweise_pruefen(fall: dict) -> None:
    werte = fall["werte"]
    assert werte["format"] == fall["format"]
    mail = sende_orte_mail(preset_aus_werten(fall["liste"], werte))
    PRUEFE[fall["liste"]](mail, fall["format"])


@pytest.mark.parametrize("fall", _paarweise("orte_vergleichstabelle"))
def test_vergleichstabelle_paarweise(fall):
    """Spec §3 / AC-5: Auswahl-Muster x Reihenfolge x Format paarweise."""
    _paarweise_pruefen(fall)


@pytest.mark.parametrize("fall", _paarweise("orte_stundenverlauf"))
def test_stundenverlauf_paarweise(fall):
    """Spec §3 / AC-6: Auswahl-Muster x Reihenfolge x Format paarweise."""
    _paarweise_pruefen(fall)


@pytest.mark.parametrize("fall", _paarweise("orte_ausblick"))
def test_ausblick_paarweise(fall):
    """Spec §3 / AC-7 / AC-8: Auswahl-Muster x Reihenfolge x Darstellung x Format."""
    _paarweise_pruefen(fall)


# ---------------------------------------------------------------------------
# AC-5 Vergleichstabelle und Ortsreihenfolge
# ---------------------------------------------------------------------------


def test_ac5_vergleichstabelle_zeilen_und_orte():
    """AC-5: Zeilen Wind, Temperatur, Niederschlag; Orte Kronplatz, Sulden,
    Ahrntal; abgewaehlte Boeen/Regenwahrscheinlichkeit erscheinen nicht."""
    mail = sende_orte_mail(preset_dict("ac5_vergleichstabelle"))
    soll = soll_vergleichstabelle(mail.roh)
    assert soll == ["wind", "temperature", "precipitation"] != katalogfolge(soll)
    assert _orte(mail.roh) == ["Kronplatz", "Sulden", "Ahrntal"]
    for fmt in ("html", "klartext"):
        pruefe_vergleichstabelle(mail, fmt)
    _orte_html, zeilen = html_vergleichstabelle(mail.html)
    assert "gust" not in zeilen and "rain_probability" not in zeilen


@pytest.mark.parametrize("location_ids", [
    ["loc-ahrntal", "loc-kronplatz", "loc-sulden"],
    ["loc-sulden", "loc-ahrntal", "loc-kronplatz"],
])
def test_ac5_ortsreihenfolge_vertauscht(location_ids):
    """AC-5 (Variante), Spec §2.4: Spalten der Vergleichstabelle UND die
    Abschnitte Stundenverlauf/Ausblick folgen ``location_ids``."""
    p = preset_dict("ac5_vergleichstabelle")
    p["location_ids"] = location_ids
    mail = sende_orte_mail(p)
    erwartet = [NAME_JE_ID[i] for i in location_ids]
    for fmt in ("html", "klartext"):
        pruefe_vergleichstabelle(mail, fmt)
        pruefe_stundenverlauf(mail, fmt)
        pruefe_ausblick(mail, fmt)
    assert list(html_ausblick(mail.html)) == erwartet
    assert list(klartext_ausblick(mail.plain)) == erwartet


def _faelle(testname: str) -> list:
    """Faelle der Fallliste zu ``testname``; ``rot_erwartet`` -> ``xfail(strict)``."""
    faelle = json.loads(FALLLISTE.read_text(encoding="utf-8"))["faelle"]
    return [pytest.param(f, id=f["id"], marks=[pytest.mark.xfail(
                strict=True, reason=f"#3047 RED {f['befund']}")] if f["status"] == "rot_erwartet" else [])
            for f in faelle if f["test"] == testname]


@pytest.mark.parametrize("fall", _faelle("test_w11_vergleichstabelle_roh_einfach"))
def test_w11_vergleichstabelle_roh_einfach(fall):
    """Konzept W11 / #3039 (AC-1, AC-7, AC-8): ``channel_layouts.email`` legt
    Folge, Aus und Roh/Einfach der Vergleichstabelle fest und hat Vorrang vor
    ``channel_active_metrics``. Gemischt, ungleich Katalogfolge: Niederschlag
    Einfach (Ampelpunkt/Wort), Bewoelkung Einfach (Symbol), Wind ohne Angabe
    (= Roh), Boeen ausdruecklich Roh, Temperatur Einfach ohne Einfachform
    (bleibt Zahl); Regenwahrscheinlichkeit ``enabled: false`` fehlt."""
    p = preset_dict("basis")
    dc = p["display_config"]
    dc["active_metrics"] += [{"metric_id": "cloud_total", "aggregation": "avg"}]
    dc["channel_active_metrics"] = {"email": _am(["temperature", "wind"])}  # tritt zurueck
    dc["channel_layouts"] = {"email": [
        {"metric_id": "precipitation", "enabled": True, "use_friendly_format": True},
        {"metric_id": "cloud_total", "enabled": True, "use_friendly_format": True},
        {"metric_id": "wind", "enabled": True},
        {"metric_id": "gust", "enabled": True, "use_friendly_format": False},
        {"metric_id": "temperature", "enabled": True, "use_friendly_format": True},
        {"metric_id": "rain_probability", "enabled": False, "use_friendly_format": False},
    ]}
    mail = sende_orte_mail(p)
    soll = soll_vergleichstabelle(mail.roh)
    assert soll == ["precipitation", "cloud_total", "wind", "gust", "temperature"] != katalogfolge(soll)
    # Hand-Orakel (Register: Wind/Boeen/Niederschlag/Bewoelkung mit Einfachform).
    assert soll_vergleichsformen(mail.roh) == {
        "precipitation": "einfach", "cloud_total": "einfach", "wind": "zahl",
        "gust": "zahl", "temperature": "zahl"}
    pruefe_vergleichstabelle(mail, fall["format"])
    if fall["format"] == "html":
        zellen = html_vergleichszellen(mail.html)
        assert "rain_probability" not in zellen
        assert all("border-radius:50%" in frag for _t, frag in zellen["precipitation"]), zellen["precipitation"]
        assert all(t == "⛅" for t, _f in zellen["cloud_total"]), zellen["cloud_total"]
    else:
        for ort, werte in klartext_vergleichswerte(mail.plain).items():
            assert "rain_probability" not in werte, ort
            assert werte["precipitation"] in ("leicht", "mäßig", "stark"), werte


@pytest.mark.parametrize("fall", _faelle("test_ac10_vergleichstabelle_totalschnitt"))
def test_ac10_vergleichstabelle_totalschnitt(fall):
    """#3047 AC-10 (an #3039 uebergeben): Grundauswahl Wind, Temperatur; die
    gespeicherte E-Mail-Liste ist NICHT leer, liegt aber ganz ausserhalb
    (Boeen, Regenwahrscheinlichkeit) -> dokumentierter Rueckfall auf die volle
    Grundauswahl statt einer Tabelle ohne Metrik-Zeile.
    Variante ``channel_layouts``: Wind/Temperatur ohne Eintrag folgen hinten
    (#3039 AC-14). Variante ``channel_active_metrics``: Rueckfall in
    ``resolve_channel_enabled_metrics`` (F9)."""
    p = preset_dict("basis")
    dc = p["display_config"]
    dc["active_metrics"] = _am(["wind", "temperature"])
    if fall["variante"] == "channel_layouts":
        dc["channel_layouts"] = {"email": [
            {"metric_id": m, "enabled": True, "use_friendly_format": False}
            for m in ("gust", "rain_probability")]}
    else:
        dc["channel_active_metrics"] = {"email": _am(["gust", "rain_probability"])}
    mail = sende_orte_mail(p)
    assert not {"gust", "rain_probability"} & set(grundauswahl(mail.roh)), "Vorbedingung: Totalschnitt"
    assert soll_vergleichstabelle(mail.roh) == ["wind", "temperature"]
    pruefe_vergleichstabelle(mail, fall["format"])


@pytest.mark.parametrize("fall", _faelle("test_ac10_vergleichstabelle_alles_aus_bleibt_leer"))
def test_ac10_vergleichstabelle_alles_aus_bleibt_leer(fall):
    """Grenze des Rueckfalls (#3039 AC-6): ``channel_layouts.email`` schaltet
    ALLE Eintraege der Grundauswahl (Wind, Temperatur) ausdruecklich aus, nur
    Boeen ausserhalb ist an -> "alles aus" ist Nutzerwunsch, keine
    Metrik-Zeile, KEIN Rueckfall auf die Grundauswahl."""
    p = preset_dict("basis")
    dc = p["display_config"]
    dc["active_metrics"] = _am(["wind", "temperature"])
    dc["channel_layouts"] = {"email": [
        {"metric_id": "wind", "enabled": False, "use_friendly_format": False},
        {"metric_id": "gust", "enabled": True, "use_friendly_format": False},
        {"metric_id": "temperature", "enabled": False, "use_friendly_format": False},
    ]}
    mail = sende_orte_mail(p)
    assert soll_vergleichstabelle(mail.roh) == []
    pruefe_vergleichstabelle(mail, fall["format"])


def test_vergleichstabelle_bewusst_leer_ohne_rueckfall():
    """Spec §2.5: bewusst leere E-Mail-Liste -> keine Metrik-Zeile (kein stiller
    Rueckfall auf die Grundauswahl). Die feste Zeile "Amtliche Warnungen" ist
    keine Metrik und bleibt (sie ist nicht Teil der Liste)."""
    p = preset_dict("basis")
    p["display_config"]["channel_active_metrics"] = {"email": []}
    mail = sende_orte_mail(p)
    assert html_vergleichstabelle(mail.html)[1] == []
    folge, zeilen = klartext_vergleichstabelle(mail.plain)
    assert folge == _orte(mail.roh) and all(z == [] for z in zeilen.values()), zeilen


#: #3047 N2: gespeicherte Listen, die bei bewusst leerer Grundauswahl trotzdem
#: leer bleiben muessen (Konzept §5.8 "Jede Liste nimmt nur aus den Metriken oben").
_N2_GESPEICHERT = {
    "hourly_metrics": ["gust", "temperature"],
    "outlook_metrics": ["wind", "temperature"],
    "channel_active_metrics": {"email": [{"metric_id": "wind", "aggregation": "max"},
                                         {"metric_id": "temperature", "aggregation": "max"}]},
}


@pytest.mark.parametrize("fall", _faelle("test_n2_grundauswahl_bewusst_leer"))
def test_n2_grundauswahl_bewusst_leer(fall):
    """#3047 N2 (Repro OI/OJ, Konzept §5.8, Trip = Orte): ``active_metrics: []``
    ist eine BEWUSST leere Grundauswahl -- keine Liste hat Zeilen: die
    Vergleichstabelle zeigt keine Metrikzeile, Stundenverlauf und Ausblick
    entfallen ganz, in HTML und Klartext, DE und EN; auch dann, wenn darunter
    eigene Listen gespeichert sind (Variante ``gespeichert``). Frueher galt im
    Ausblick "leer = kein Maximum" (ADR-0050 D4) -> sieben feste Spalten, und
    der nie eingestellte Stundenverlauf fiel auf die feste Vorgabemenge."""
    p = preset_dict("basis")
    dc = p["display_config"]
    dc["active_metrics"] = []
    if fall["variante"] == "gespeichert":
        dc.update(json.loads(json.dumps(_N2_GESPEICHERT)))
    lang, fmt, liste = fall.get("sprache", "de"), fall["format"], fall["liste"]
    mail = sende_orte_mail(p, language=lang)
    assert grundauswahl(mail.roh) == [], "Vorbedingung: Grundauswahl bewusst leer"
    if liste == "orte_vergleichstabelle":
        assert soll_vergleichstabelle(mail.roh) == []
        if fmt == "html":
            assert html_vergleichstabelle(mail.html)[1] == [], fall["id"]
        else:
            folge, zeilen = klartext_vergleichstabelle(mail.plain)
            assert folge == _orte(mail.roh) and all(z == [] for z in zeilen.values()), zeilen
        return
    if liste == "orte_stundenverlauf":
        assert soll_stundenverlauf(mail.roh, _standard_stunden()) is None
        ist = (html_stundenverlauf(mail.html, lang) if fmt == "html"
               else klartext_stundenverlauf(mail.plain, lang))
        titel = katalogtext("vergleich.stunden.klartext_titel", lang)
    else:
        assert soll_ausblick(mail.roh) is None
        ist = (html_ausblick(mail.html, lang) if fmt == "html"
               else klartext_ausblick(mail.plain, lang))
        titel = katalogtext("vergleich.ausblick.titel", lang)
    assert ist == {}, f"{fall['id']}: Block trotz leerer Grundauswahl: {ist}"
    text = mail.plain if fmt == "klartext" else re.sub(r"<[^>]+>", "\n", mail.html)
    assert titel not in text, f"{fall['id']}: Ueberschrift {titel!r} ohne Inhalt"


# ---------------------------------------------------------------------------
# AC-6 Stundenverlauf
# ---------------------------------------------------------------------------


def test_ac6_stundenverlauf_spalten():
    """AC-6: je Ort Zeit, Boeen, Temp, Niederschlag in genau dieser Folge."""
    mail = sende_orte_mail(preset_dict("ac6_stundenverlauf"))
    gespeichert = mail.roh["display_config"]["hourly_metrics"]
    assert gespeichert != katalogfolge(gespeichert)
    assert soll_stundenverlauf(mail.roh, _standard_stunden()) == [kopf_von(m) for m in gespeichert]
    for fmt in ("html", "klartext"):
        pruefe_stundenverlauf(mail, fmt)


@pytest.mark.parametrize("aenderung", ["hourly_enabled_aus", "auswahl_leer"])
def test_ac6_stundenverlauf_aus_und_leer(aenderung):
    """AC-6: ausgeschaltet oder bewusst leer -> der Block entfaellt in HTML und Klartext."""
    p = preset_dict("ac6_stundenverlauf")
    if aenderung == "hourly_enabled_aus":
        p["hourly_enabled"] = False
    else:
        p["display_config"]["hourly_metrics"] = []
    mail = sende_orte_mail(p)
    assert soll_stundenverlauf(mail.roh, _standard_stunden()) is None
    assert html_stundenverlauf(mail.html) == {}
    assert "STUNDENVERLAUF" not in mail.plain.splitlines()
    assert klartext_stundenverlauf(mail.plain) == {}


def test_ac6_stundenverlauf_nie_eingestellt_standard():
    """AC-6 / AC-13 (Befund O2): nie eingestellt -> der Block erscheint mit der
    Standardliste. Seit #3047 H1 (Konzept §5.8) ist das bei vorhandener
    Grundauswahl (``basis``) deren stuendliche Groessen in deren Folge, nicht
    mehr die feste Vorgabemenge (Orakel ``soll_stundenverlauf`` bewusst
    umgestellt). Ob sie der Editor-Vorgabe gleicht, prueft Paket D."""
    mail = sende_orte_mail(preset_dict("basis"))
    assert "hourly_metrics" not in mail.roh["display_config"]
    soll = soll_stundenverlauf(mail.roh, _standard_stunden())
    assert soll and len(soll) >= 2
    for fmt in ("html", "klartext"):
        pruefe_stundenverlauf(mail, fmt)


def test_ac10_stundenverlauf_nimmt_nur_aus_grundauswahl():
    """AC-10 / Konzept §5.8 ("Jede Liste nimmt nur aus den Metriken oben"):
    Boeen stehen gespeichert im Stundenverlauf, sind aber aus der Grundauswahl
    abgewaehlt -> keine Boeen-Spalte. Ist: die Spalte erscheint, weil
    ``resolve_compare_render_options`` ``hourly_metrics`` ohne Schnitt nimmt
    (``src/services/report_config_resolver.py:291``)."""
    mail = sende_orte_mail(preset_dict("ac10_grundauswahl"))
    assert "gust" not in grundauswahl(mail.roh)
    assert "gust" in mail.roh["display_config"]["hourly_metrics"]
    for fmt in ("html", "klartext"):
        pruefe_stundenverlauf(mail, fmt)


@pytest.mark.parametrize("variante,grund,stunden,erwartet", [
    # Rueckfall 1: Vorgabemenge geschnitten mit der Grundauswahl, Folge der
    # Vorgabemenge (Temperatur vor Wind vor Niederschlag).
    ("vorgabemenge", ["wind", "temperature", "precipitation"], ["gust", "uv_index"],
     ["Temp", "Wind", "Rain"]),
    # Rueckfall 2: Grundauswahl ohne jede Groesse der Vorgabemenge -> die
    # stuendlich waehlbaren Groessen der Grundauswahl in deren Folge.
    ("waehlbare_groessen", ["humidity", "cloud_total"], ["temperature", "gust"],
     ["Humid", "Cloud"]),
], ids=["vorgabemenge", "waehlbare_groessen"])
def test_ac10_stundenverlauf_totalschnitt_rueckfall(variante, grund, stunden, erwartet):
    """AC-10 / #3047 O5: liegt die gespeicherte Stundenliste vollstaendig
    ausserhalb der Grundauswahl, verschwindet der Block nicht still, sondern
    zeigt den dokumentierten Rueckfall -- in HTML und Klartext (F7/F002)."""
    p = preset_dict("ac10_grundauswahl")
    dc = p["display_config"]
    dc["active_metrics"] = [{"metric_id": m, "aggregation": AGG.get(m, "avg")} for m in grund]
    dc.pop("channel_active_metrics")
    dc["hourly_metrics"] = list(stunden)
    mail = sende_orte_mail(p)
    assert not set(stunden) & set(grundauswahl(mail.roh)), "Vorbedingung: Totalschnitt"
    assert soll_stundenverlauf(mail.roh, _standard_stunden()) == erwartet, variante
    for fmt in ("html", "klartext"):
        pruefe_stundenverlauf(mail, fmt)


def _stunden_koepfe(mail, fmt: str) -> dict[str, list[str]]:
    return (html_stundenverlauf(mail.html) if fmt == "html"
            else klartext_stundenverlauf(mail.plain))


@pytest.mark.parametrize("fmt", ["html", "klartext"])
def test_h1_stundenverlauf_gespeichert_ausserhalb_grundauswahl(fmt):
    """#3047 H1 (Nachpruefung Punkt 1, AC-10/AC-13): Sicht steht gespeichert
    im Stundenverlauf, aber nicht in der Grundauswahl -> die Mail zeigt Boeen,
    Temp, Niederschlag (Soll von Hand, Konzept §5.8). Der Editor zeigt dieselbe
    Liste (``editor_standard.json`` Zustand ``gespeichert_ausserhalb_grundauswahl``)."""
    p = preset_dict("basis")
    p["display_config"]["hourly_metrics"] = ["visibility", "gust", "temperature", "precipitation"]
    mail = sende_orte_mail(p)
    assert "visibility" not in grundauswahl(mail.roh), "Vorbedingung"
    ist = _stunden_koepfe(mail, fmt)
    assert list(ist) == _orte(mail.roh)
    for ort, koepfe in ist.items():
        assert koepfe == ["Gust", "Temp", "Rain"], f"{fmt} {ort}: {koepfe}"


@pytest.mark.parametrize("fmt", ["html", "klartext"])
def test_h1_stundenverlauf_nie_eingestellt_aus_grundauswahl(fmt):
    """#3047 H1 (Nachpruefung Punkt 3, AC-6/AC-10/AC-13, Konzept §5.8 "Jede
    Liste nimmt nur aus den Metriken oben"): Stundenverlauf nie eingestellt,
    Grundauswahl Wind, Niederschlag, Temperatur, Boeen (ohne UV, Sicht,
    Gewitter, ...) -> genau diese Spalten in der Folge der Grundauswahl, nicht
    die feste Vorgabe ``HOURLY_DEFAULT_METRIC_IDS``. Soll von Hand."""
    p = preset_dict("basis")
    p["display_config"]["active_metrics"] = _am(("wind", "precipitation", "temperature", "gust"))
    mail = sende_orte_mail(p)
    assert "hourly_metrics" not in mail.roh["display_config"], "Vorbedingung"
    ist = _stunden_koepfe(mail, fmt)
    assert list(ist) == _orte(mail.roh)
    for ort, koepfe in ist.items():
        assert koepfe == ["Wind", "Rain", "Temp", "Gust"], f"{fmt} {ort}: {koepfe}"


def test_j1_grundauswahl_gleich_vorgabe_kette():
    """#3047 J1 (AC-13/AC-10, Konzept §5.8): die Grundauswahl ist gespeichert und
    gleicht zufaellig der Vorgabe (alle Zeilen, Standardfolge, Speicherformat des
    Editors); Stundenverlauf und Ausblick sind nie eingestellt. Gespeichert ist
    gespeichert: die Mail nimmt die Grundauswahl-Regel, in HTML und Klartext --
    dieselbe Folge, die der Editor laut ``editor_standard.json`` (Zustand
    ``grundauswahl_gleich_vorgabe``) zeigt. Soll von Hand dort."""
    daten = json.loads((FIXTURE_DIR / "editor_standard.json").read_text(encoding="utf-8"))
    zustand = {liste: next(z for z in daten["listen"][liste]["zustaende"]
                           if z["id"] == "grundauswahl_gleich_vorgabe")
               for liste in ("orte_stundenverlauf", "orte_ausblick")}
    p = preset_dict("basis")
    p["display_config"]["active_metrics"] = zustand["orte_ausblick"]["eingabe"]["display_config"]["active_metrics"]
    mail = sende_orte_mail(p)
    dc = mail.roh["display_config"]
    assert "hourly_metrics" not in dc and "outlook_metrics" not in dc, "Vorbedingung"
    stunden = [kopf_von(m) for m in zustand["orte_stundenverlauf"]["erwartet"]]
    ausblick = zustand["orte_ausblick"]["erwartet"]
    for fmt in ("html", "klartext"):
        ist_stunden = _stunden_koepfe(mail, fmt)
        assert list(ist_stunden) == _orte(mail.roh), fmt
        for ort, koepfe in ist_stunden.items():
            assert koepfe == stunden, f"{fmt} {ort}: Stundenverlauf {koepfe}"
        ist_ausblick = (html_ausblick(mail.html) if fmt == "html" else klartext_ausblick(mail.plain))
        assert list(ist_ausblick) == _orte(mail.roh), fmt
        for ort, zellen in ist_ausblick.items():
            assert kennungen(zellen) == ausblick, f"{fmt} {ort}: Ausblick {[k for k, _ in zellen]}"


@pytest.mark.parametrize("fmt", ["html", "klartext"])
def test_orte_koepfe_in_nutzersprache_en(fmt):
    """ADR-0104 / #3047 F7 (F003): ein englischer Nutzer bekommt Stundenverlauf
    und Ausblick mit englischen Festtexten -- HTML-Kopfzellen ("Time", "Day")
    und Klartext-Ueberschriften ("HOURLY VIEW", "3-day outlook") laut Katalog
    ``src/i18n/messages/en/``; Spalten und Folge wie eingestellt."""
    mail = sende_orte_mail(preset_dict("ac6_stundenverlauf"), language="en")
    assert soll_stundenverlauf(mail.roh, _standard_stunden()), "Vorbedingung: Stundenverlauf an"
    assert soll_ausblick(mail.roh), "Vorbedingung: Ausblick an"
    pruefe_stundenverlauf(mail, fmt, "en")
    pruefe_ausblick(mail, fmt, lang="en")


# ---------------------------------------------------------------------------
# AC-7 / AC-8 Ausblick
# ---------------------------------------------------------------------------


def test_ac7_ausblick_folge_mit_temperaturspanne():
    """AC-7: Ausblick je Ort Niederschlag, Wind, Temperatur (Spanne Tief/Hoch in
    EINER Spalte), in HTML und Klartext; Boeen/Regenwahrscheinlichkeit der
    Grundauswahl erscheinen nicht."""
    mail = sende_orte_mail(preset_dict("ac7_ausblick"))
    soll = soll_ausblick(mail.roh)
    assert soll == ["precipitation", "wind", "temperature"] != katalogfolge(soll)
    for fmt in ("html", "klartext"):
        pruefe_ausblick(mail, fmt)
    for zellen in html_ausblick(mail.html).values():
        assert [k for k, _ in zellen] == ["Rain", "Wind", "Temp"]


@pytest.mark.parametrize("aenderung", ["outlook_enabled_aus", "auswahl_leer"])
def test_ac7_ausblick_aus_und_leer(aenderung):
    """AC-7 / Spec §2.5: ``outlook_enabled`` aus oder bewusst leer -> kein Ausblick."""
    p = preset_dict("ac7_ausblick")
    if aenderung == "outlook_enabled_aus":
        p["outlook_enabled"] = False
    else:
        p["display_config"]["outlook_metrics"] = []
    mail = sende_orte_mail(p)
    assert soll_ausblick(mail.roh) is None
    assert html_ausblick(mail.html) == {}
    assert klartext_ausblick(mail.plain) == {}
    assert "3-Tages-Ausblick" not in mail.plain


def test_ac7_ausblick_ausserhalb_grundauswahl():
    """AC-7 (dritte Variante): eine gespeicherte, aber nicht in der Grundauswahl
    stehende Metrik (UV-Index) taucht im Ausblick nicht auf."""
    p = preset_dict("ac7_ausblick")
    p["display_config"]["outlook_metrics"] = ["precipitation", "uv_index", "wind", "temperature"]
    mail = sende_orte_mail(p)
    assert "uv_index" not in grundauswahl(mail.roh)
    assert soll_ausblick(mail.roh) == ["precipitation", "wind", "temperature"]
    for fmt in ("html", "klartext"):
        pruefe_ausblick(mail, fmt)


def test_ac10_grundauswahl_ausblick():
    """AC-10 Ausblick: (a) neu in die Grundauswahl aufgenommener UV-Index
    erscheint im nie eingestellten Ausblick; (b) abgewaehlte Boeen erscheinen
    nicht; (c) Totalschnitt -> dokumentierter Rueckfall auf die volle Grundauswahl."""
    a = preset_dict("basis")
    a["display_config"]["active_metrics"] += _am(["uv_index"])
    b = preset_dict("ac10_grundauswahl")
    c = preset_dict("ac10_grundauswahl")
    c["display_config"]["outlook_metrics"] = ["gust"]
    erwartet = [list(POOL) + ["uv_index"], ["wind", "temperature"], ["wind", "temperature", "precipitation"]]
    for p, soll in zip((a, b, c), erwartet):
        mail = sende_orte_mail(p)
        assert soll_ausblick(mail.roh) == soll
        for fmt in ("html", "klartext"):
            pruefe_ausblick(mail, fmt, darstellung=False)


def test_ac10_grundauswahl_vergleichstabelle():
    """AC-10 Vergleichstabelle: (a) UV-Index neu in der Grundauswahl -> erscheint
    in der nie eingestellten E-Mail-Liste (hinten); (b) gespeicherte, aber aus
    der Grundauswahl abgewaehlte Boeen erscheinen nicht."""
    a = preset_dict("basis")
    a["display_config"]["active_metrics"] += _am(["uv_index"])
    mail = sende_orte_mail(a)
    assert soll_vergleichstabelle(mail.roh) == list(POOL) + ["uv_index"]
    for fmt in ("html", "klartext"):
        pruefe_vergleichstabelle(mail, fmt)
    mail = sende_orte_mail(preset_dict("ac10_grundauswahl"))
    assert soll_vergleichstabelle(mail.roh) == ["wind", "temperature"]
    for fmt in ("html", "klartext"):
        pruefe_vergleichstabelle(mail, fmt)


def _offen(testname: str, grund: str) -> list:
    """Faelle ``offen_feature`` zu ``testname`` -- rot belegt per
    ``xfail(strict=True)``, damit die Umsetzung laut wird (#3047 J2)."""
    faelle = json.loads(FALLLISTE.read_text(encoding="utf-8"))["faelle"]
    params = [pytest.param(f, id=f["id"], marks=[pytest.mark.xfail(strict=True, reason=grund)])
              for f in faelle if f["test"] == testname]
    assert params, f"Fallliste ohne Faelle fuer {testname}"
    return params


@pytest.mark.parametrize("fall", _offen("test_p7_global_nachtraeglich_in_gespeicherter_liste",
                                        "#3065 Phase 2: Abwahl nicht persistiert"))
def test_p7_global_nachtraeglich_in_gespeicherter_liste(fall):
    """Konzept §5 Punkt 6 / Nachpruefung Punkt 7: eine Metrik, die NACH dem
    Speichern einer eigenen Liste in die Grundauswahl aufgenommen wird
    (UV-Index), steht in allen Listen -- Vergleichstabelle
    (``channel_active_metrics.email``), Stundenverlauf (``hourly_metrics``) und
    Ausblick (``outlook_metrics``), die sie noch nicht kennen."""
    p = preset_dict("basis")
    dc = p["display_config"]
    dc["active_metrics"] += _am(["uv_index"])
    liste = fall["liste"]
    if liste == "orte_vergleichstabelle":
        dc["channel_active_metrics"] = {"email": _am(["temperature", "wind", "gust"])}
    elif liste == "orte_stundenverlauf":
        dc["hourly_metrics"] = ["gust", "temperature"]
    else:
        dc["outlook_metrics"] = ["wind", "temperature"]
    mail = sende_orte_mail(p)
    if liste == "orte_vergleichstabelle":
        spalten = [html_vergleichstabelle(mail.html)[1]]
    elif liste == "orte_stundenverlauf":
        spalten = [kennungen(k) for k in html_stundenverlauf(mail.html).values()]
    else:
        spalten = [kennungen(z) for z in html_ausblick(mail.html).values()]
    assert spalten and all("uv_index" in s for s in spalten), (
        f"{fall['id']}: global nachtraeglich aufgenommen, fehlt in {spalten}")


@pytest.mark.parametrize("fall", _faelle("test_w11_darstellung_je_zeile"))
def test_w11_darstellung_je_zeile(fall):
    """Konzept W11 ("Darstellung Roh oder Einfach je Metrik, in jeder Liste"):
    Bewoelkung steht in der E-Mail-Liste auf Einfach (Symbol), Temperatur auf
    Roh -- auch der Stundenverlauf zeigt Bewoelkung als Symbol ohne Ziffer,
    Temperatur als Zahl. Speicherort (#3097, ADR-0121 Nachtrag 3b):
    ``display_config.hourly_metric_formats``. Gegenprobe: die Vergleichstabelle
    (``channel_layouts.email``) steht fuer Bewoelkung auf Roh und aendert den
    Stundenverlauf nicht (eigener Schalter je Liste)."""
    from tests.helpers.einstellung_gleich_mail_orte import _abschnitte, _tabellen_je_ort, _zelltoken

    p = preset_dict("basis")
    dc = p["display_config"]
    dc["active_metrics"] += [{"metric_id": "cloud_total", "aggregation": "avg"}]
    dc["hourly_metrics"] = ["cloud_total", "temperature"]
    dc["hourly_metric_formats"] = {"cloud_total": True, "temperature": False}
    dc["channel_layouts"] = {"email": [
        {"metric_id": m, "enabled": True, "use_friendly_format": False}
        for m in ("cloud_total", "temperature", "wind", "gust", "precipitation", "rain_probability")]}
    mail = sende_orte_mail(p)
    werte: dict[str, list[str]] = {"cloud_total": [], "temperature": []}
    if fall["format"] == "html":
        for zeilen in _tabellen_je_ort(mail.html, katalogtext("vergleich.stunden.zeit")).values():
            koepfe = kennungen(zeilen[0][1:])
            for zeile in zeilen[1:]:
                for mid, zelle in zip(koepfe, zeile[1:]):
                    werte.setdefault(mid, []).append(zelle)
    else:
        for zeilen in _abschnitte(mail.plain)[1].values():
            for z in zeilen:
                if re.match(r"^\s+\d\d:\d\d\s", z):
                    for kopf, zelle in _zelltoken(z.split(None, 1)[1]):
                        werte.setdefault(kennungen([kopf])[0], []).append(zelle)
    assert werte["cloud_total"] and werte["temperature"], f"Vorbedingung: Spalten fehlen {werte}"
    assert all(ist_zahl(z) for z in werte["temperature"]), werte["temperature"]
    assert not any(ist_zahl(z) for z in werte["cloud_total"]), (
        f"{fall['format']}: Bewoelkung auf Einfach, Stundenverlauf zeigt {werte['cloud_total']}")


def test_ac8_ausblick_roh_einfach():
    """AC-8 Orte: im Ausblick zeigt die Einfach-Zeile (Boeen) ein Wort, die
    Roh-Zeilen (Wind, Niederschlag) eine Zahl -- in HTML und Klartext gleich."""
    mail = sende_orte_mail(preset_dict("ac8_darstellung"))
    einfach = soll_einfach(mail.roh)
    assert einfach["gust"] is True and einfach["wind"] is False and einfach["precipitation"] is False
    for fmt in ("html", "klartext"):
        pruefe_ausblick(mail, fmt)
    for quelle in (html_ausblick(mail.html), klartext_ausblick(mail.plain)):
        for zellen in quelle.values():
            form = {kennungen([k])[0]: ist_zahl(z) for k, z in zellen}
            assert (form["gust"], form["wind"], form["precipitation"]) == (False, True, True), zellen


def test_ac8_ausblick_ohne_einfach_form_bleibt_zahl():
    """AC-8 Ausnahme (Spec §2.3, #814 AC-5, #2049): Temperatur und Sichtweite
    stehen auf Einfach, haben im Ausblick aber keine Einfach-Form -> Zahl."""
    mail = sende_orte_mail(preset_dict("ac8_darstellung"))
    einfach = soll_einfach(mail.roh)
    assert einfach["temperature"] is True and einfach["visibility"] is True
    for quelle in (html_ausblick(mail.html), klartext_ausblick(mail.plain)):
        assert quelle
        for zellen in quelle.values():
            form = {kennungen([k])[0]: ist_zahl(z) for k, z in zellen}
            assert form["temperature"] and form["visibility"], zellen


# ---------------------------------------------------------------------------
# AC-11 Altbestand (Golden), AC-21 (O3)
# ---------------------------------------------------------------------------

GOLDEN_UID = "orte-golden-altbestand"


def _golden(name: str, endung: str) -> "os.PathLike":
    return FIXTURE_DIR / f"orte_{name}.golden.{endung}"


@pytest.mark.parametrize("name", ["altbestand", "altbestand_ohne_grundauswahl"])
def test_ac11_altbestand_golden(name):
    """AC-11: Preset ohne ``outlook_metric_formats``, ``channel_layouts``,
    ``hourly_metrics``, ``outlook_metrics`` -> HTML und Klartext byte-gleich zum
    eingefrorenen Ist-Stand. Feste Kennung (kein ``"default"``), feste Uhr,
    feste Wetterdaten -- keine Normalisierung noetig. AC-21 aendert die
    Klartext-Golden ``altbestand_ohne_grundauswahl`` spaeter einzeln."""
    roh = preset_dict(name)
    neue_felder = {"outlook_metric_formats", "channel_layouts", "hourly_metrics", "outlook_metrics"}
    assert not neue_felder & set(roh["display_config"]), "Vorbedingung: Altbestand ohne neue Felder"
    mail = sende_orte_mail(roh, uid=GOLDEN_UID)
    if os.environ.get("EINSTELLUNG_GLEICH_MAIL_GOLDEN_SCHREIBEN") == "1":
        _golden(name, "html").write_text(mail.html, encoding="utf-8")
        _golden(name, "txt").write_text(mail.plain, encoding="utf-8")
    assert mail.html == _golden(name, "html").read_text(encoding="utf-8"), f"HTML {name} weicht vom Golden ab"
    assert mail.plain == _golden(name, "txt").read_text(encoding="utf-8"), f"Klartext {name} weicht vom Golden ab"


def test_ac21_altbestand_ausblick_klartext_gleich_html():
    """AC-21 (Befund O3): Altbestand ohne ``active_metrics`` und ohne
    ``outlook_metrics`` -> der Ausblick zeigt im Klartext dieselben Spalten in
    derselben Folge wie im HTML derselben Mail. Ist: HTML 7 Spalten, Klartext
    4 (fester Zweig ``src/output/renderers/email/outlook.py:395-402``)."""
    mail = sende_orte_mail(preset_dict("altbestand_ohne_grundauswahl"))
    assert "active_metrics" not in mail.roh["display_config"]
    html, plain = html_ausblick(mail.html), klartext_ausblick(mail.plain)
    assert list(html) == list(plain) == _orte(mail.roh)
    for ort in html:
        assert kennungen(plain[ort]) == kennungen(html[ort]), (
            f"{ort}: Klartext {[k for k, _ in plain[ort]]} != HTML {[k for k, _ in html[ort]]}")


def _vollauswahl_ohne_ausblick() -> dict:
    """#3061 (Befund F4): ``active_metrics`` bewusst gespeichert mit ALLEN
    Katalog-Groessen, ``outlook_metrics`` fehlt. Diese Kombination war fuer die
    paarweisen Faelle nicht darstellbar (``nie_eingestellt`` nutzt den kleinen
    POOL), deshalb blieb der Editor-Fehler unentdeckt."""
    from output.renderers.compare_metric_catalog import get_compare_metric_catalog

    roh = preset_dict("basis")
    roh["id"] = "orte-3061-vollauswahl"
    dc = roh["display_config"]
    for feld in ("outlook_metrics", "outlook_metric_formats"):
        dc.pop(feld, None)
    dc["active_metrics"] = [{"metric_id": e["metric_id"], "aggregation": e["aggregation"]}
                            for e in get_compare_metric_catalog()]
    return roh


@pytest.mark.parametrize("fmt", ["html", "klartext"])
def test_3061_vollauswahl_gespeichert_ausblick_fehlt(fmt):
    """#3061 AC-6 / #3047 AC-13, AC-21: Vollauswahl gespeichert, Ausblick nie
    eingestellt -> die Mail zeigt ALLE darstellbaren Groessen der Grundauswahl
    in deren Folge, nicht nur die sieben festen Vorgabe-Spalten des
    Altbestands. Der Editor muss genau das zeigen (editor_standard.json,
    Zustand ``gespeichert_vollauswahl_ohne_ausblick``)."""
    mail = sende_orte_mail(_vollauswahl_ohne_ausblick())
    assert "outlook_metrics" not in mail.roh["display_config"]
    pruefe_ausblick(mail, fmt, darstellung=False)
    ist = (html_ausblick(mail.html) if fmt == "html" else klartext_ausblick(mail.plain))
    for ort, zellen in ist.items():
        spalten = kennungen(zellen)
        assert len(spalten) > 6 and "sunshine" in spalten and "humidity" in spalten, (
            f"{fmt} {ort}: Vollauswahl zeigt nur {spalten} -- erwartet alle darstellbaren Groessen")


# ---------------------------------------------------------------------------
# WV6 Amtliche Warnungen zuerst (Konzept einstellungen_neu.md §5 Punkt 8)
# ---------------------------------------------------------------------------


def _hitzewarnung():
    from tests.helpers.amtliche_warnungen_fixture import hitze

    return hitze()


def _wv6_mail():
    """Vergleich mit gespeicherter Folge Wind, Temperatur, Niederschlag;
    Kronplatz hat eine aktive amtliche Warnung (Hitze)."""
    roh = preset_dict("ac5_vergleichstabelle")
    assert roh.get("official_alerts_enabled", True) is True
    mail = sende_orte_mail(roh, warnungen={"loc-kronplatz": [_hitzewarnung()]})
    assert soll_vergleichstabelle(mail.roh) == ["wind", "temperature", "precipitation"]
    return mail


def test_wv6_amtliche_warnung_zuerst_html():
    """Konzept WV6 (einstellungen_neu.md §5 Punkt 8): in der E-Mail steht die
    Zeile "Amtliche Warnungen" immer ZUERST in der Vergleichstabelle,
    unabhaengig von der gespeicherten Metrik-Folge."""
    from tests.helpers.einstellung_gleich_mail_orte import _tabellen

    mail = _wv6_mail()
    tabelle = next(z for _p, z in _tabellen(mail.html) if z and z[0] and z[0][0] == "Metrik")
    assert tabelle[1][0] == "Amtliche Warnungen", [z[0] for z in tabelle[1:]]
    assert "Hitze" in " ".join(tabelle[1][1:]), tabelle[1]
    assert html_vergleichstabelle(mail.html)[1] == ["wind", "temperature", "precipitation"]


def test_wv6_amtliche_warnung_zuerst_klartext():
    """Konzept WV6, Klartext derselben Mail: im Ortsblock steht die Warnung als
    ERSTE Zeile vor den Metrik-Zeilen. Ist: ``render_comparison_text`` haengt
    die Warnzeilen erst NACH der Metrik-Schleife an
    (``src/output/renderers/comparison.py:310-313``)."""
    from tests.helpers.einstellung_gleich_mail_orte import _abschnitte

    mail = _wv6_mail()
    uebersicht, _ = _abschnitte(mail.plain)
    block = []
    for z in uebersicht[uebersicht.index("Kronplatz") + 1:]:
        if not z.strip():
            break
        block.append(z)
    assert klartext_vergleichstabelle(mail.plain)[1]["Kronplatz"] == ["wind", "temperature", "precipitation"]
    assert block and "⚠️" in block[0] and "Hitze" in block[0], block


# ---------------------------------------------------------------------------
# AC-12 zwei Nutzer
# ---------------------------------------------------------------------------


def test_ac12_zwei_nutzer():
    """AC-12: Nutzer 1 Wind, Temperatur; Nutzer 2 Temperatur, Wind (alle drei
    Listen). Jede Mail traegt die Folge ihres Nutzers an dessen Adresse."""
    l1 = sende_orte_mail(preset_dict("ac12_nutzer1"))
    l2 = sende_orte_mail(preset_dict("ac12_nutzer2"))
    assert l1.uid != l2.uid and "default" not in (l1.uid, l2.uid)
    for lauf, folge in ((l1, ["wind", "temperature"]), (l2, ["temperature", "wind"])):
        assert lauf.empfaenger == [f"{lauf.uid}@example.invalid"], lauf.empfaenger
        assert soll_vergleichstabelle(lauf.roh) == soll_ausblick(lauf.roh) == folge
        for fmt in ("html", "klartext"):
            for pruefe in PRUEFE.values():
                pruefe(lauf, fmt)
        assert html_vergleichstabelle(lauf.html)[1] == folge
        for koepfe in klartext_stundenverlauf(lauf.plain).values():
            assert koepfe == [kopf_von(m) for m in folge]
    assert html_vergleichstabelle(l1.html)[1] != html_vergleichstabelle(l2.html)[1]
    assert l1.roh["display_config"] != l2.roh["display_config"]


def test_baue_orte_eml_liefert_vollstaendige_mail():
    """Werkzeug fuer Paket C (``--eml``): multipart/alternative mit Klartext und
    HTML derselben Kette, ``To`` = Adresse des Nutzers (nie ``"default"``)."""
    from email import message_from_bytes, policy

    from tests.helpers.einstellung_gleich_mail_orte import baue_orte_eml

    msg = message_from_bytes(baue_orte_eml(preset_dict("ac5_vergleichstabelle")), policy=policy.default)
    assert msg.get_content_type() == "multipart/alternative"
    assert msg["To"].endswith("@example.invalid") and not msg["To"].startswith("default@")
    plain = msg.get_body(preferencelist=("plain",)).get_content()
    html = msg.get_body(preferencelist=("html",)).get_content()
    assert html_vergleichstabelle(html)[1] == ["wind", "temperature", "precipitation"]
    assert klartext_vergleichstabelle(plain)[1]["Kronplatz"] == ["wind", "temperature", "precipitation"]


# ---------------------------------------------------------------------------
# #3155 (B4 von #3122): eine steuernde Stelle, ein Name -- Orte, je Briefing,
# Ausgabe (HTML, Nur-Text, Telegram; Orte kennt keine Kompakt-Mail) und
# Sprache. SPEC: docs/specs/modules/feat_3155_ein_name_ausblick.md (AC-2,
# AC-3, AC-4, AC-8, AC-10, AC-11, AC-13).
#
# Fallfelder: ``konfig`` (Schluessel in ``_B4_KONFIG``), ``briefing``,
# ``sprache``, ``format``, ``soll`` (an/aus). Die "Anlage-Marke" ist die
# Vorbelegung, die die Orte-Anlage kuenftig schreibt (Spec Entscheidung 5):
# ``display_config.placements`` OHNE ``rows``, nur ``outlook_reports`` -- das
# Abo bleibt im Altpfad (Auswahl, Formate), nur der Ausblick wird gesteuert.
# ---------------------------------------------------------------------------

from tests.helpers.ausblick_name import (  # noqa: E402
    NAME, alte_namen_in, html_textknoten, name_steht, orte_telegram_koepfe, textzeilen,
)

_B4_AUSBLICK = ["precipitation", "wind", "temperature"]


def _b4_preset(*, placements=None, **top) -> dict:
    """Orte-Abo (Morgen- und Abend-Briefing, Telegram an) mit eingestellter
    Ausblick-Auswahl und -Form (Anlege-Assistent): Folge ungleich Katalog,
    Wind auf Einfach."""
    p = preset_dict("ac7_ausblick")
    p.update(id="orte-b4", send_telegram=True, morning_enabled=True, evening_enabled=True)
    dc = p["display_config"]
    dc["outlook_metrics"] = list(_B4_AUSBLICK)
    dc["outlook_metric_formats"] = {"wind": True}
    if placements is not None:
        dc["placements"] = placements
    p.update(top)
    return p


def _b4_marke(reports) -> dict:
    return {"version": 1, "outlook_reports": list(reports)}


def _b4_tabelle(reports) -> dict:
    return {"version": 1, "rows": [{"metric_id": m} for m in _B4_AUSBLICK],
            "outlook_reports": list(reports)}


_B4_KONFIG = {
    # AC-8: Anlage-Marke (ohne ``rows``) -- nur Abend / nur Morgen / beide aus.
    "marke_abend": lambda: _b4_preset(placements=_b4_marke(["evening"])),
    "marke_morgen": lambda: _b4_preset(placements=_b4_marke(["morning"])),
    "marke_leer": lambda: _b4_preset(placements=_b4_marke([])),
    # AC-2/AC-3: mit Tabelle -- nur Abend / beide Schalter aus.
    "tabelle_abend": lambda: _b4_preset(placements=_b4_tabelle(["evening"])),
    "tabelle_aus": lambda: _b4_preset(placements=_b4_tabelle([])),
    # AC-4: Bestand ``outlook_enabled: false`` -> nirgends.
    "alt_aus": lambda: _b4_preset(outlook_enabled=False),
    # AC-13: Bestand ohne Tabelle und ohne Marke bleibt: Ausblick in jedem
    # eingeschalteten Briefing (Spec Nr. 8, heutiges Verhalten).
    "alt_an": lambda: _b4_preset(outlook_enabled=True),
}


def _b4_senden(fall: dict):
    return sende_orte_mail(_B4_KONFIG[fall["konfig"]](), language=fall.get("sprache"),
                           briefing=fall.get("briefing"))


def _b4_ausblick_da(fall: dict, mail) -> bool:
    lang = fall.get("sprache") or "de"
    fmt = fall["format"]
    if fmt == "html":
        return html_ausblick(mail.html, lang) != {}
    if fmt == "telegram":
        assert mail.telegram is not None, f"{fall['id']}: Vorbedingung Telegram-Sendung"
        return orte_telegram_koepfe(mail.telegram) != []
    return klartext_ausblick(mail.plain, lang) != {}


@pytest.mark.parametrize("fall", _faelle("test_b4_orte_ausblick_je_briefing"))
def test_b4_orte_ausblick_je_briefing(fall):
    """AC-2/AC-3/AC-4/AC-8 (#3155): der Orte-Ausblick steht in einem Briefing
    genau dann, wenn die eine Stelle ihn dort einschaltet (Tabelle oder
    Anlage-Marke), in HTML-Mail, Nur-Text-Mail und Telegram gleich. Wo er
    steht, zeigt er die im Anlege-Assistenten gewaehlte Auswahl, Folge und
    Form (Altpfad bleibt, AC-8)."""
    mail = _b4_senden(fall)
    ist = _b4_ausblick_da(fall, mail)
    soll = fall["soll"] == "an"
    assert ist is soll, (
        f"{fall['id']}: Ausblick {'fehlt' if soll else 'steht trotzdem'} "
        f"({fall['konfig']}, {fall['briefing']}, {fall['format']}, {fall['sprache']})")
    if soll and fall["format"] in ("html", "klartext") and fall["konfig"].startswith("marke"):
        pruefe_ausblick(mail, fall["format"], lang=fall["sprache"])


def _b4_texte(fall: dict, mail) -> list[str]:
    if fall["format"] == "html":
        return html_textknoten(mail.html)
    if fall["format"] == "telegram":
        return textzeilen(mail.telegram or "")
    return textzeilen(mail.plain)


@pytest.mark.parametrize("fall", _faelle("test_b4_orte_ausblick_heisst_ueberall_gleich"))
def test_b4_orte_ausblick_heisst_ueberall_gleich(fall):
    """AC-10 (#3155): der Orte-Ausblick heisst in HTML-Mail, Nur-Text-Mail und
    Telegram "3-Tages-Ausblick" bzw. "3-day outlook" -- im Telegram traegt
    JEDER Ortsblock diesen Kopf."""
    mail = _b4_senden(fall)
    lang = fall["sprache"]
    assert _b4_ausblick_da(fall, mail), f"{fall['id']}: Vorbedingung Ausblick"
    if fall["format"] == "telegram":
        koepfe = orte_telegram_koepfe(mail.telegram)
        assert koepfe and set(koepfe) == {NAME[lang]}, (
            f"{fall['id']}: Telegram-Koepfe {koepfe} != {NAME[lang]!r}")
        return
    assert name_steht(_b4_texte(fall, mail), lang), f"{fall['id']}: Blocktitel {NAME[lang]!r} fehlt"


@pytest.mark.parametrize("fall", _faelle("test_b4_orte_keine_alten_ausblick_namen"))
def test_b4_orte_keine_alten_ausblick_namen(fall):
    """AC-11 (#3155): keine Orte-Ausgabe nennt den Ausblick "Ausblick"/
    "Outlook" (auch nicht als Eyebrow), "Mehrtages-Trend" oder
    "3-Tages-Vorschau"."""
    mail = _b4_senden(fall)
    assert _b4_ausblick_da(fall, mail), f"{fall['id']}: Vorbedingung Ausblick"
    funde = alte_namen_in(_b4_texte(fall, mail))
    assert not funde, f"{fall['id']}: alte Namen in der Ausgabe: {funde}"
