"""#3097 (Phase 3b von #3047, Epic #3058): Roh/Einfach je Zeile im Orte-Stundenverlauf (W11).

SPEC: docs/specs/modules/feat_3097_orte_stundenverlauf_darstellung.md (AC-1 bis AC-7, AC-9, AC-11)

Kette wie im Betrieb (``sende_orte_mail``: rohes Preset-JSON -> echter Loader ->
``send_one_compare_preset``); Naht nur an Wetter-Engine und Transport. Soll von
Hand (Wortskalen aus der Spec), nie aus ``resolve_*``. Kein ``Mock()``/``patch()``.

ROT vor der Umsetzung: ``display_config.hourly_metric_formats`` wird von
Resolver, Render-Optionen und Renderern ignoriert; die Stundentabelle zeigt
immer Zahlen.
"""
from __future__ import annotations

import dataclasses
import html as html_mod
import importlib.util
import re
from pathlib import Path

import pytest

from tests.helpers.einstellung_gleich_mail_orte import (
    _abschnitte, _zelltoken, html_vergleichszellen, kennungen,
    klartext_vergleichswerte, preset_dict, sende_orte_mail,
)

PUNKT = "border-radius:50%"
WIND_WORTE = {"schwach", "mäßig", "stark", "sehr stark"}
REGEN_WORTE = {"unwahrscheinlich", "möglich", "wahrscheinlich", "sehr wahrscheinlich"}
#: Stunden-Skala (Spec AC-6, ``format_precip_intensity``), von Hand.
STUNDEN_SKALA = {0.0: "trocken", 0.4: "leicht", 3.0: "mäßig", 12.0: "stark"}
#: Tagessummen-Skala (#2049) derselben Werte -- darf NICHT erscheinen.
TAGES_SKALA = {3.0: "leicht", 12.0: "mäßig"}

_TABLE_RE = re.compile(r"<table[^>]*>(.*?)</table>", re.DOTALL)


def _text(fragment: str) -> str:
    return html_mod.unescape(re.sub(r"<[^>]+>", "", fragment)).strip()


def _preset(stunden, formate=None, extra_aktiv=()):
    p = preset_dict("basis")
    dc = p["display_config"]
    dc["active_metrics"] += [{"metric_id": m, "aggregation": "avg"} for m in extra_aktiv]
    dc["hourly_metrics"] = list(stunden)
    if formate is not None:
        dc["hourly_metric_formats"] = dict(formate)
    return p


def html_stunden(html: str) -> list[dict[str, list[tuple[str, str]]]]:
    """Je Stundentabelle (Kopf "Zeit"): {Kennung: [(Text, rohes Zell-HTML) je Stunde]}."""
    tabellen = []
    for m in _TABLE_RE.finditer(html):
        trs = re.findall(r"<tr[^>]*>(.*?)</tr>", m.group(1), re.DOTALL)
        zeilen = [re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", tr, re.DOTALL) for tr in trs]
        if not (zeilen and zeilen[0] and _text(zeilen[0][0]) == "Zeit"):
            continue
        ids = kennungen([_text(k) for k in zeilen[0][1:]])
        spalten: dict[str, list[tuple[str, str]]] = {i: [] for i in ids}
        for z in zeilen[1:]:
            for mid, frag in zip(ids, z[1:]):
                spalten[mid].append((_text(frag), frag))
        tabellen.append(spalten)
    assert tabellen, "keine Stundentabelle im HTML"
    return tabellen


def klartext_stunden(plain: str) -> list[dict[str, list[str]]]:
    """Je Ortsabschnitt: {Kennung: [Zelle je Stunde]} der Stundenzeilen."""
    aus = []
    for zeilen in _abschnitte(plain)[1].values():
        spalten: dict[str, list[str]] = {}
        for z in zeilen:
            if re.match(r"^\s+\d\d:\d\d\s", z):
                for kopf, zelle in _zelltoken(z.split(None, 1)[1]):
                    spalten.setdefault(kennungen([kopf])[0], []).append(zelle)
        if spalten:
            aus.append(spalten)
    assert aus, "kein Klartext-Stundenverlauf"
    return aus


def _zahl(z: str) -> bool:
    return bool(re.search(r"\d", z))


def _wind_einfach(html: str) -> bool:
    return all(PUNKT in f and not _zahl(t) for tab in html_stunden(html) for t, f in tab["wind"])


# ---------------------------------------------------------------------------
# AC-1 / AC-2: Wind Einfach in HTML und Klartext, uebrige Zeilen Zahl
# ---------------------------------------------------------------------------

def test_ac1_html_wind_einfach_ampelpunkt_uebrige_zahl():
    mail = sende_orte_mail(_preset(["wind", "temperature", "gust"], {"wind": True}))
    for tab in html_stunden(mail.html):
        assert tab["wind"] and all(PUNKT in f and not _zahl(t) for t, f in tab["wind"]), (
            f"Wind auf Einfach, HTML-Stundentabelle zeigt {[t for t, _ in tab['wind']]}")
        assert all(_zahl(t) for t, _ in tab["temperature"]), tab["temperature"]
        assert all(_zahl(t) for t, _ in tab["gust"]), "Boeen ohne Einstellung muessen Zahl bleiben"


def test_ac2_klartext_wind_einfach_wort_gegenprobe_roh_zahl():
    einfach = sende_orte_mail(_preset(["wind", "temperature"], {"wind": True}))
    roh = sende_orte_mail(_preset(["wind", "temperature"], {"wind": False}))
    for tab in klartext_stunden(einfach.plain):
        assert tab["wind"] and all(z in WIND_WORTE for z in tab["wind"]), (
            f"Klartext-Wind auf Einfach zeigt {tab['wind']}")
        assert all(_zahl(z) for z in tab["temperature"])
    for tab in klartext_stunden(roh.plain):
        assert all(_zahl(z) for z in tab["wind"]), tab["wind"]


# ---------------------------------------------------------------------------
# AC-4: ohne Einstellung byte-gleich, explizit Roh == fehlend
# ---------------------------------------------------------------------------

def test_ac4_roh_false_gleich_fehlend_einfach_nicht():
    stunden = ["wind", "temperature", "precipitation"]
    ohne = sende_orte_mail(_preset(stunden))
    roh = sende_orte_mail(_preset(stunden, {"wind": False, "precipitation": False}))
    einfach = sende_orte_mail(_preset(stunden, {"wind": True}))
    assert (roh.html, roh.plain) == (ohne.html, ohne.plain), "explizit Roh weicht von fehlend ab"
    assert einfach.html != ohne.html and einfach.plain != ohne.plain, (
        "Einfach fuer Wind aendert die Mail nicht (Feld wird ignoriert)")


# ---------------------------------------------------------------------------
# AC-5: Vergleichstabelle und Stundenverlauf sind getrennte Schalter
# ---------------------------------------------------------------------------

def test_ac5_vergleichstabelle_einfach_laesst_stundenverlauf_roh():
    """Regressionswache (heute schon gruen): ``channel_layouts.email`` wirkt nicht
    in den Stundenverlauf."""
    p = _preset(["wind", "temperature"])
    p["display_config"]["channel_layouts"] = {"email": [
        {"metric_id": m, "enabled": True, "use_friendly_format": m == "wind"}
        for m in ("temperature", "wind", "gust", "precipitation", "rain_probability")]}
    mail = sende_orte_mail(p)
    for tab in html_stunden(mail.html):
        assert all(_zahl(t) and PUNKT not in f for t, f in tab["wind"]), tab["wind"]
    for tab in klartext_stunden(mail.plain):
        assert all(_zahl(z) for z in tab["wind"]), tab["wind"]


def test_ac5_stundenverlauf_einfach_laesst_vergleichstabelle_unveraendert():
    ohne = sende_orte_mail(_preset(["wind", "temperature"]))
    mit = sende_orte_mail(_preset(["wind", "temperature"], {"wind": True}))
    assert html_vergleichszellen(mit.html) == html_vergleichszellen(ohne.html)
    assert klartext_vergleichswerte(mit.plain) == klartext_vergleichswerte(ohne.plain)
    assert _wind_einfach(mit.html), "Vorbedingung: Stundenverlauf-Wind muss Einfach zeigen"


# ---------------------------------------------------------------------------
# Einfachformen weiterer Groessen
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("metrik,form", [
    ("gust", "punkt"), ("cloud_total", "symbol"), ("rain_probability", "wort"),
])
def test_einfachformen_je_groesse(metrik, form):
    mail = sende_orte_mail(_preset([metrik, "temperature"], {metrik: True},
                                   extra_aktiv=("cloud_total",) if metrik == "cloud_total" else ()))
    for tab in html_stunden(mail.html):
        zellen = tab[metrik]
        assert zellen and not any(_zahl(t) for t, _ in zellen), f"{metrik}: {zellen}"
        if form == "punkt":
            assert all(PUNKT in f for _t, f in zellen)
        elif form == "wort":
            assert all(t in REGEN_WORTE for t, _ in zellen), zellen
    for tab in klartext_stunden(mail.plain):
        assert not any(_zahl(z) for z in tab[metrik]), f"Klartext {metrik}: {tab[metrik]}"


# ---------------------------------------------------------------------------
# AC-6: Niederschlag nach Stunden-Skala, nicht Tagessummen-Skala
# ---------------------------------------------------------------------------

def test_ac6_niederschlag_stundenskala(monkeypatch):
    """Naht an der Testdaten-Quelle (Wetterwerte je Stunde), nicht am Produkt."""
    import tests.helpers.einstellung_gleich_mail_orte as helfer

    werte = list(STUNDEN_SKALA)
    original = helfer._ergebnis_je_ort

    def mit_niederschlag():
        aus = {}
        for lid, loc in original().items():
            daten = [dataclasses.replace(dp, precip_1h_mm=werte[i % len(werte)])
                     for i, dp in enumerate(loc.hourly_data)]
            aus[lid] = dataclasses.replace(loc, hourly_data=daten)
        return aus

    monkeypatch.setattr(helfer, "_ergebnis_je_ort", mit_niederschlag)
    mail = sende_orte_mail(_preset(["precipitation", "temperature"], {"precipitation": True}))
    soll = [STUNDEN_SKALA[werte[i % len(werte)]] for i in range(9)]
    for tab in html_stunden(mail.html):
        ist = [t for t, _ in tab["precipitation"]]
        assert ist == soll[:len(ist)], f"HTML Niederschlag Stundenskala: {ist} != {soll}"
    for tab in klartext_stunden(mail.plain):
        ist = tab["precipitation"]
        assert ist == soll[:len(ist)], f"Klartext Niederschlag Stundenskala: {ist} != {soll}"
    # Gegenprobe: 3 mm und 12 mm/h tragen NICHT die Tagessummen-Stufe.
    assert all(TAGES_SKALA[v] != STUNDEN_SKALA[v] for v in TAGES_SKALA)


# ---------------------------------------------------------------------------
# AC-7: Temperatur/Gewitter ohne Einfachform bleiben Zahl/Text
# ---------------------------------------------------------------------------

def test_ac7_temperatur_und_gewitter_ignorieren_einfach():
    stunden = ["temperature", "thunder", "wind"]
    nur_wind = sende_orte_mail(_preset(stunden, {"wind": True}))
    alle = sende_orte_mail(_preset(stunden, {"wind": True, "temperature": True, "thunder": True}))
    assert (alle.html, alle.plain) == (nur_wind.html, nur_wind.plain), (
        "Einfach fuer Temperatur/Gewitter darf die Mail nicht veraendern")
    for tab in html_stunden(alle.html):
        assert all(_zahl(t) for t, _ in tab["temperature"])
    assert _wind_einfach(alle.html), "Vorbedingung: Wind Einfach wirkt"


# ---------------------------------------------------------------------------
# AC-3: Vorschau == Versand; Resolver; Vertrag Validator-Vorschau
# ---------------------------------------------------------------------------

def test_ac3_vorschau_zeigt_dieselbe_stundentabelle_wie_versand():
    from freezegun import freeze_time

    from services.compare_preview_service import ComparePreviewService
    from tests.helpers.einstellung_gleich_mail_orte import JETZT_UTC, ZIELTAG, wetter_naht

    p = _preset(["wind", "temperature", "precipitation"], {"wind": True})
    mail = sende_orte_mail(p)
    with wetter_naht(), freeze_time(JETZT_UTC):
        vorschau = ComparePreviewService().render_all_channels(
            p["id"], user_id=mail.uid, target_date=ZIELTAG)["email_html"]
    assert html_stunden(vorschau) == html_stunden(mail.html)
    assert _wind_einfach(vorschau), "Vorschau zeigt Wind nicht als Einfach"


def test_resolver_liefert_hourly_format():
    from services.channel_list_resolver import resolve_channel_lists

    dc = _preset(["wind", "temperature", "precipitation"],
                 {"wind": True, "temperature": False})["display_config"]
    formate = {z.metric_id: z.format for z in resolve_channel_lists(dc, "compare").hourly}
    assert formate == {"wind": "simplified", "temperature": "raw", "precipitation": None}, formate


def test_validator_vorschau_vertrag_traegt_hourly_metric_formats():
    from api.routers.validator import CompareEmailPreviewBody

    body = CompareEmailPreviewBody(profile="wandern", time_window=[6, 20], target_date="2026-07-08",
                                   hourly_metrics=["wind10m_kmh"], hourly_metric_formats={"wind": True})
    assert getattr(body, "hourly_metric_formats", None) == {"wind": True}


# ---------------------------------------------------------------------------
# AC-9: zwei Nutzer, beide Reihenfolgen
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("reihenfolge", ["a_zuerst", "b_zuerst"])
def test_ac9_zwei_nutzer_getrennt(reihenfolge):
    from tests.helpers.einstellung_gleich_mail_orte import profil_anlegen

    uid_a, uid_b = profil_anlegen(), profil_anlegen()
    assert uid_a != uid_b and "default" not in (uid_a, uid_b)
    stunden = ["wind", "temperature"]
    auftraege = [(uid_a, {"wind": True}), (uid_b, None)]
    if reihenfolge == "b_zuerst":
        auftraege.reverse()
    mails = {uid: sende_orte_mail(_preset(stunden, f), uid=uid) for uid, f in auftraege}
    assert _wind_einfach(mails[uid_a].html), "Nutzer A: Wind auf Einfach wirkt nicht"
    assert not any(PUNKT in f for tab in html_stunden(mails[uid_b].html) for _t, f in tab["wind"])
    assert all(_zahl(z) for tab in klartext_stunden(mails[uid_b].plain) for z in tab["wind"])


# ---------------------------------------------------------------------------
# AC-11: Mail-Validator akzeptiert Einfach-Zellen
# ---------------------------------------------------------------------------

def _validator():
    pfad = Path(__file__).resolve().parents[2] / ".claude" / "hooks" / "email_spec_validator.py"
    spec = importlib.util.spec_from_file_location("email_spec_validator_3097", pfad)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_ac11_validator_akzeptiert_einfach_zellen():
    mod = _validator()
    formate = {"wind": True, "gust": True, "precipitation": True,
               "rain_probability": True, "cloud_total": True}
    p = _preset(["wind", "gust", "precipitation", "rain_probability", "cloud_total", "temperature"],
                formate, extra_aktiv=("cloud_total",))
    mail = sende_orte_mail(p)
    assert _wind_einfach(mail.html), "Vorbedingung: Mail traegt Einfach-Zellen"
    assert mod.validate_structure(mail.html) == []
    assert mod.validate_hourly_table(mail.html, 8, 16) == []
