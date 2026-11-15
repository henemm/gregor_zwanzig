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
    ist_zahl,
    katalogfolge,
    kennungen,
    klartext_ausblick,
    klartext_stundenverlauf,
    klartext_vergleichstabelle,
    kopf_von,
    preset_dict,
    sende_orte_mail,
    soll_ausblick,
    soll_einfach,
    soll_stundenverlauf,
    soll_vergleichstabelle,
)

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
    """Backend-Standardliste "nie eingestellt" (Register-Konstante). Ob sie
    der Editor-Vorgabe gleicht, prueft Paket D (AC-13, ``editor_standard.json``)."""
    from output.renderers.compare_hourly_metric_ids import HOURLY_DEFAULT_METRIC_IDS

    return HOURLY_DEFAULT_METRIC_IDS


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
        return
    folge, zeilen = klartext_vergleichstabelle(mail.plain)
    assert folge == orte, f"Klartext Orts-Bloecke {folge}, eingestellt {orte}"
    for ort in orte:
        assert zeilen[ort] == soll, f"Klartext {ort}: Zeilen {zeilen[ort]}, eingestellt {soll}"


def pruefe_stundenverlauf(mail, fmt: str) -> None:
    soll = soll_stundenverlauf(mail.roh, _standard_stunden())
    ist = html_stundenverlauf(mail.html) if fmt == "html" else klartext_stundenverlauf(mail.plain)
    if soll is None:
        assert ist == {}, f"{fmt}: Stundenverlauf muss entfallen, gefunden {ist}"
        return
    assert list(ist) == _orte(mail.roh), f"{fmt}: Orte im Stundenverlauf {list(ist)}"
    for ort, koepfe in ist.items():
        assert koepfe == soll, f"{fmt} {ort}: Spalten {koepfe}, eingestellt {soll}"


def pruefe_ausblick(mail, fmt: str, *, darstellung: bool = True) -> None:
    soll = soll_ausblick(mail.roh)
    ist = html_ausblick(mail.html) if fmt == "html" else klartext_ausblick(mail.plain)
    if soll is None:
        assert ist == {}, f"{fmt}: Ausblick muss entfallen, gefunden {list(ist)}"
        assert "3-Tages-Ausblick" not in mail.plain.splitlines() or fmt == "html"
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
    Backend-Standardliste. Ob diese der Editor-Vorgabe gleicht, prueft Paket D."""
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
