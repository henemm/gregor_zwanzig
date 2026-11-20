"""#3047 Runde 7, Paket p9 -- Ausblick-Zeilen im Telegram brechen nur ZWISCHEN
Werten um (geteilter Zeilenbau ``narrow._outlook_lines``, Orte und Trip).

Befund: lange Tageszeilen des 3-Tages-Ausblicks wurden an Wortgrenzen auf 56
Zeichen umbrochen -- mitten in einer Zelle (``Wind: 28`` / ``km/h``, ``Gust:`` /
``30 km/h``). Soll: jede Zelle ``{Label}: {Wert}`` und der Tageskopf bleiben
ganz; der Umbruch faellt nur zwischen zwei Zellen.

Echte Wege bis zur Transport-Mitschrift:

* Orte: gespeichertes Preset (JSON) -> Loader -> Resolver ->
  ``send_one_compare_preset`` -> Telegram-Mitschrift, zwei Nutzer, DE und EN.
* Trip: ``send_test_report_outcome`` (derselbe Weg wie On-Demand/Slot) auf den
  aufgezeichneten Open-Meteo-Fixture-Daten (Golden-Trip aus #2439), zwei Nutzer.

SPEC: docs/specs/modules/feat_3047_einstellung_gleich_mail_pruefkatalog.md
(Nachtrag Runde 7, AC-24: Ausblick in Trip-Telegram-Form; ADR-0095 Kanal-Paritaet).
"""
from __future__ import annotations

import re

import pytest

# ruff: noqa: F811  (mit = geteilte Fixture als Testparameter)
from tests.tdd.test_3047_runde7_orte_kanaele import (  # noqa: F401 (Fixture `mit`)
    mit, ortsbloecke, preset, text, zwei_nutzer,
)

#: Tageskopf einer Ausblick-Zeile: ``Fr``/``Fri`` (Orte), ``Fr 30.10.`` (de) /
#: ``Fri 30 Oct`` (en) bzw. normalisiert ``<WT> <TT.MM.>`` (Golden-Normalisierung
#: des Trip-Wegs); danach folgen zwei Leerzeichen oder das Zeilenende.
_TAGESKOPF = re.compile(
    r"^(?:<WT>(?: <TT\.MM\.>)?|[A-Z][a-z]{1,2}(?: \d{1,2}(?:\.\d{2}\.| [A-Z][a-z]{2}))?)(?=  |$)")
#: Eine ganze Zelle: Label, Doppelpunkt, nicht-leerer Wert.
_ZELLE = re.compile(r"^[^:]+: \S")


def _zerbrochene_zellen(zeilen: list[str]) -> list[str]:
    """Liefert jede Ausblick-Zeile, die eine Zelle oder den Tageskopf zerteilt.

    Eine Zeile ist ganz, wenn ihre Teile (Trenner zwei Leerzeichen) aus einem
    Tageskopf (nur am Zeilenanfang) und sonst nur ganzen Zellen bestehen."""
    kaputt = []
    for zeile in zeilen:
        roh = zeile.strip()
        if not roh or roh.startswith("↳"):
            continue
        teile = roh.split("  ")
        if _TAGESKOPF.match(teile[0]):
            teile = teile[1:]
        if not teile or not all(_ZELLE.match(t) for t in teile) or roh.endswith(":"):
            kaputt.append(zeile)
    return kaputt


def _unnoetig_umbrochen(zeilen: list[str]) -> list[str]:
    """Folgezeilen, deren erste Zelle noch in die Vorzeile gepasst haette
    (Umbruch nur, wenn noetig -- sonst wuerde jede Zelle eine eigene Zeile)."""
    zu_frueh = []
    for vor, zeile in zip(zeilen, zeilen[1:]):
        roh = zeile.strip()
        if not roh or roh.startswith("↳") or _TAGESKOPF.match(roh):
            continue
        erste = roh.split("  ")[0]
        if len(vor.rstrip()) + 2 + len(erste) <= 56:
            zu_frueh.append(zeile)
    return zu_frueh


def _tageskoepfe(zeilen: list[str]) -> int:
    return sum(1 for z in zeilen if _TAGESKOPF.match(z.strip()))


# ---------------------------------------------------------------------------
# Orte: echter Versandweg
# ---------------------------------------------------------------------------

#: Bewusst viele Groessen in Roh (lange Zeilen > 56 Zeichen); Folge != Katalogfolge.
_LANG = ["wind", "gust", "temperature", "precipitation", "rain_probability", "cloud_total"]


def _lang_preset() -> dict:
    p = preset()
    p["display_config"]["outlook_metrics"] = list(_LANG)
    p["display_config"]["outlook_metric_formats"] = {m: False for m in _LANG}
    return p


def _ausblick_block(block: list[str], lang: str) -> list[str]:
    kopf = {"de": "3-Tages-Ausblick", "en": "3-day outlook"}[lang]
    assert kopf in block, f"Vorbedingung: Ausblick fehlt im Ortsblock: {block}"
    return block[block.index(kopf) + 1:]


@pytest.mark.parametrize("lang", ["de", "en"])
def test_p9_orte_telegram_ausblick_bricht_nur_zwischen_werten_um(mit, lang):
    """GIVEN ein Ortsvergleich mit sechs Ausblick-Groessen in Roh (Tageszeile > 56 Zeichen)
    WHEN  das Briefing ueber ``send_one_compare_preset`` an Telegram geht (zwei Nutzer)
    THEN  ist jede Ausblick-Zeile aus ganzen Zellen gebaut -- kein ``Wind: 28`` / ``km/h``."""
    for uid, snap in zwei_nutzer(mit, _lang_preset(), lang=lang):
        tg = text(snap, "telegram")
        bloecke = ortsbloecke(tg)
        assert bloecke, f"Vorbedingung: keine Ortsbloecke ({uid}):\n{tg}"
        for name, block in bloecke.items():
            zeilen = _ausblick_block(block, lang)
            assert _tageskoepfe(zeilen) == 3, f"{uid}/{name}: drei Ausblick-Tage erwartet:\n{tg}"
            assert len(zeilen) > 3, f"Vorbedingung: Zeilen muessen umbrechen ({name}):\n{tg}"
            kaputt = _zerbrochene_zellen(zeilen)
            assert not kaputt, f"{uid}/{name}: Umbruch mitten im Wert: {kaputt}\n{tg}"
            assert not _unnoetig_umbrochen(zeilen), f"{uid}/{name}: Umbruch ohne Not:\n{tg}"
            assert all(len(z) <= 56 for z in zeilen), f"{name}: Zeile > 56 Zeichen:\n{tg}"


# ---------------------------------------------------------------------------
# Trip: echter Versandweg (Golden-Trip, aufgezeichnete Fixture-Daten)
# ---------------------------------------------------------------------------


def test_p9_trip_telegram_ausblick_bricht_nur_zwischen_werten_um(monkeypatch):
    """GIVEN der Golden-Trip (Ausblick-Standardauswahl, Tageszeile > 56 Zeichen)
    WHEN  der Abend-Bericht ueber ``send_test_report_outcome`` versendet wird (zwei Nutzer)
    THEN  bricht die Ausblick-Zeile im Telegram nur zwischen ganzen Zellen um
          (vorher ``Gust:`` / ``30 km/h``) und ihr Inhalt bleibt vollstaendig."""
    from tests import test_befehl_antwortzeit as ba

    monkeypatch.setenv("GZ_PUBLIC_HOST", "https://gregor20.henemm.com")
    for name, wert in ba._TRANSPORT_ENV.items():
        monkeypatch.setenv(name, wert)
    from tests.helpers.transport_mitschrift import aufzeichner_installieren

    mitschrift = aufzeichner_installieren(monkeypatch)
    ba.dwd._RASTER_CACHE.clear()
    ba.parallel_fetch._reset_for_tests()
    ergebnisse = []
    with ba._dwd_server(monkeypatch, verzoegerung_s=0.0):
        for uid in ("ausblickumbruch-a", "ausblickumbruch-b"):
            ergebnisse.append(ba._bericht_aufnehmen(mitschrift, uid, *ba.REYKJAVIK))
    for erg in ergebnisse:
        assert erg["ausgang"] == "sent", f"Vorbedingung: Bericht versendet: {erg['ausgang']}"
        bubbles = [s["body"] for s in erg["telegram"]]
        ausblick = [b for b in bubbles if b.splitlines()[0] in ("3-Tages-Ausblick", "3-day outlook")]
        assert len(ausblick) == 1, f"Vorbedingung: genau eine Ausblick-Bubble: {bubbles}"
        zeilen = ausblick[0].splitlines()[1:]
        assert _tageskoepfe(zeilen) >= 1, f"Vorbedingung: Ausblick-Tag fehlt: {zeilen}"
        assert len(zeilen) > _tageskoepfe(zeilen), f"Vorbedingung: Zeile bricht um: {zeilen}"
        kaputt = _zerbrochene_zellen(zeilen)
        assert not kaputt, f"Trip: Umbruch mitten im Wert: {kaputt}\n{ausblick[0]}"
        assert not _unnoetig_umbrochen(zeilen), f"Trip: Umbruch ohne Not: {zeilen}"
        assert all(len(z) <= 56 for z in zeilen), f"Trip: Zeile > 56 Zeichen: {zeilen}"
        # Inhalt vollstaendig: die Zellen des Golden-Altstands stehen alle da.
        flach = "  ".join(z.strip() for z in zeilen)
        for zelle in ("Temp: -5/-5", "Wind: 20 km/h", "Gust: 30 km/h", "Rain: 3.6 mm",
                      "Cloud: 60 %", "Visib: 7000 m", "Sun: 12.0 h", "SnowH: 45 cm"):
            assert zelle in flach, f"Trip: Zelle {zelle!r} fehlt/zerteilt: {zeilen}"


# ---------------------------------------------------------------------------
# Rueckfall: eine einzelne Zelle breiter als die Zeile
# ---------------------------------------------------------------------------


def test_p9_ueberbreite_einzelzelle_faellt_auf_wortumbruch_zurueck():
    """GIVEN eine Ausblick-Zelle, die allein breiter als 56 Zeichen ist
    WHEN  die Tageszeile gepackt wird
    THEN  bleibt jede Zeile <= 56 Zeichen (Wort-Umbruch nur IN dieser Zelle),
          die Nachbarzellen bleiben ganz und der Text geht nicht verloren."""
    from output.renderers.narrow import _TG_PROSE_WIDTH, _wrap_cells

    lang_zelle = "Gewitter: " + " ".join(["moeglich"] * 9)
    assert len(lang_zelle) > _TG_PROSE_WIDTH, "Vorbedingung: Zelle ueberbreit"
    zeilen = _wrap_cells(["Fr", "Wind: 20 km/h", lang_zelle, "Rain: 3.6 mm"], _TG_PROSE_WIDTH)
    assert all(len(z) <= _TG_PROSE_WIDTH for z in zeilen), zeilen
    assert " ".join(" ".join(zeilen).split()) == " ".join(
        f"Fr  Wind: 20 km/h  {lang_zelle}  Rain: 3.6 mm".split()), zeilen
    assert zeilen[0] == "Fr  Wind: 20 km/h", zeilen
    assert zeilen[-1].endswith("Rain: 3.6 mm"), zeilen
