"""Ortsvergleich ``channel_layouts`` -- Fix-Loop 1 (Issue #3039, Adversary F001-F005).

SPEC: docs/specs/modules/feat_3039_vergleich_kanal_layouts.md (AC-1, AC-6, AC-8,
AC-13, Implementation Details 4/6/7).

Schliesst die Luecken, die die Mutations-Gegenprobe gefunden hat
(``docs/artifacts/feat-3039-vergleich-kanal-layouts/adversary-dialog.md``):

* F001 -- Telegram mit Einfach (Versand UND Vorschau), M5/M7a/M20.
* F002 -- Einfach bei Metrik mit nur einem ``format_mode``, die anderswo eine
  Wortform kennt (``rain_probability``), M2.
* F003 -- Kennung mit ZWEI abgeleiteten Zeilen (Temperatur max + min), M26;
  ``channel_layouts`` ohne Grundauswahl (kein Schnitt), M22.
* F004 -- Luecken-Zaehler liest ``channel_active_metrics`` nicht, sobald der
  Kanal eine ``channel_layouts``-Liste hat, M17.
* F005 -- Gewitter-Einfach in der HTML-Mail (M25); doppelte Kennung: der
  ERSTE Eintrag gilt (M11).

Einstieg und Naehte wie ``test_compare_channel_layouts_3039.py`` (echter
Loader, ``send_one_compare_preset``, ``ComparePreviewService``; nur Wetter und
Transport als Naht, kein ``Mock()``/``patch()``). Jeder Versand-Test laeuft mit
zwei Nutzern. Tageswerte: Innsbruck Boeen 19 km/h, Regenwahrsch. 10 %,
Temperatur 22/12; Bozen Boeen 23 km/h, Regenwahrsch. 20 %, Temperatur 27/15.
"""
from __future__ import annotations

import re

from tests.tdd._compare_kette_fixtures import ORTSNAMEN, TARGET_DATE
from tests.tdd.test_compare_channel_layouts_3039 import (
    GRUNDAUSWAHL,
    _AMPEL_PUNKT,
    _eintrag,
    _html_zeile,
    _keys,
    _plain_wert,
    _telegram_zelle,
    _vorlage,
    _voll,
    _zwei,
)
import pytest

from tests.tdd.test_compare_einstellung_auslieferung_kette import (  # noqa: F401 (Fixture)
    _text,
)
# Fixture ``mit`` unter Alias einbinden (siehe test_compare_channel_layouts_3039).
from tests.tdd.test_compare_einstellung_auslieferung_kette import (  # noqa: F401 (Fixture)
    mit as _fixture_mit,
)


@pytest.fixture
def mit(_fixture_mit):  # noqa: F811 (Fixture-Parameter, Alias-Import oben)
    """Kanalmitschrift der Auslieferungskette (Fixture aus test_compare_einstellung_auslieferung_kette)."""
    return _fixture_mit

_AGG = {"temperature": "max", "wind": "max", "gust": "max", "cloud_total": "avg",
        "sunshine": "sum", "rain_probability": "max", "thunder": "max"}


def _zeilenfolge(vorlage: dict, vorne: list[str]) -> dict:
    """#3237: Zeilen der Tabelle in dieser Folge, die uebrigen dahinter."""
    zeilen = vorlage["display_config"]["placements"]["rows"]
    zeilen.sort(key=lambda z: vorne.index(z["metric_id"]) if z["metric_id"] in vorne else len(vorne))
    return vorlage


def _grundauswahl(vorlage: dict, paare: list[tuple[str, str]]) -> dict:
    vorlage["display_config"]["active_metrics"] = [
        {"metric_id": m, "aggregation": a} for m, a in paare
    ]
    # #3237: die Tabelle "Was steht wo" folgt der geaenderten Grundauswahl
    # (die Kanal-Einstellung des Falls steht weiter in ``channel_layouts``
    # als Beschreibung und wird erneut als Tabelle ausgedrueckt).
    from tests.helpers.tabelle_aus_wunsch import orte_wunsch_als_tabelle

    vorlage["display_config"].pop("placements", None)
    return orte_wunsch_als_tabelle(vorlage)


# ---------------------------------------------------------------------------
# F001 -- Telegram Einfach: Versand und Vorschau zeigen die Einfachform
# ---------------------------------------------------------------------------


def test_f001_telegram_einfach_in_versand_und_vorschau_mail_roh_bleibt_zahl(mit):
    from services.compare_preview_service import ComparePreviewService

    layouts = {
        "email": _voll(GRUNDAUSWAHL, gust={"einfach": False}),
        "telegram": _voll(GRUNDAUSWAHL, gust={"einfach": True}),
        "sms": _voll(GRUNDAUSWAHL),
    }
    for lauf in _zwei(mit, _vorlage(layouts)):
        tg = _text(lauf.snap, "telegram")
        for ort in ORTSNAMEN:
            zelle = _telegram_zelle(tg, ort, "Böen")
            assert zelle and not re.search(r"\d", zelle), (
                f"Versand-Telegram {ort}: Böen bei Einfach muss ein Wort sein, war {zelle!r}\n{tg}")
        vorschau = ComparePreviewService().render_all_channels(
            lauf.roh["id"], user_id=lauf.uid, target_date=TARGET_DATE,
        )
        assert vorschau["telegram"] == tg, "Vorschau-Telegram muss dem Versand gleichen"
        assert _plain_wert(_text(lauf.snap, "email"), "Innsbruck", "Böen") == "19 km/h"
        assert _AMPEL_PUNKT not in _html_zeile(lauf.snap.sendungen("email")[-1]["body"], "Böen")


# ---------------------------------------------------------------------------
# F002 -- Regenwahrscheinlichkeit: bis #3156 wurde Einfach verworfen (nur EIN
# format_mode). Seit dem Renderer-Nachzug (#3156, ADR-0124 Nr. 5) entscheidet
# ``zwei_formen_stellen``: Einfach wirkt in Telegram, Klartext und HTML; die
# SMS bleibt unveraendert (AC-8).
# ---------------------------------------------------------------------------


def test_f002_einfach_bei_regenwahrscheinlichkeit_wirkt_sms_bleibt(mit):
    kennungen = GRUNDAUSWAHL + ["rain_probability"]
    paare = [(k, _AGG[k]) for k in kennungen]
    roh = _grundauswahl(_vorlage({k: _voll(kennungen) for k in ("email", "telegram", "sms")}), paare)
    einf = _grundauswahl(_vorlage({
        k: _voll(kennungen, rain_probability={"einfach": True})
        for k in ("email", "telegram", "sms")
    }), paare)
    a_roh, _ = _zwei(mit, roh)
    assert _telegram_zelle(_text(a_roh.snap, "telegram"), "Innsbruck", "Regenwahrscheinlichkeit") == "10%"
    for lauf in _zwei(mit, einf):
        # 10 % / 20 % -> Wortstufe "unwahrscheinlich" (Skala 25/50/75).
        tg = _text(lauf.snap, "telegram")
        assert _telegram_zelle(tg, "Innsbruck", "Regenwahrscheinlichkeit") == "unwahrscheinlich", tg
        for ort in ("Innsbruck", "Bozen"):
            assert _plain_wert(_text(lauf.snap, "email"), ort, "Regenwahrscheinlichkeit") == "unwahrscheinlich"
        html = lauf.snap.sendungen("email")[-1]["body"]
        assert _AMPEL_PUNKT in _html_zeile(html, "Regenwahrscheinlichkeit")
        assert _text(lauf.snap, "sms") == _text(a_roh.snap, "sms")


# ---------------------------------------------------------------------------
# F003 -- Expansion mit zwei Zeilen; ohne Grundauswahl kein Schnitt
# ---------------------------------------------------------------------------


def test_f003_temperatur_wirkt_auf_hoechst_und_tiefstwert(mit):
    """Grundauswahl Temperatur max UND min: ``an`` zeigt beide Zeilen, ``aus``
    blendet beide aus (keine kommt als „neu“ am Ende zurueck)."""
    paare = [("temperature", "max"), ("temperature", "min"), ("gust", "max")]
    layouts = {
        "telegram": [_eintrag("temperature", einfach=False), _eintrag("gust", einfach=False)],
        "email": [_eintrag("temperature", an=False, einfach=False), _eintrag("gust", einfach=False)],
    }
    vorlage = _grundauswahl(_vorlage(layouts), paare)
    # #3237: EINE Zeilenfolge fuer alle Stellen (Spec #3122 Teil A Nr. 8) --
    # die Folge der Telegram-Liste (Temperatur vor Boeen) gilt als Zeilenfolge.
    _zeilenfolge(vorlage, ["temperature", "gust"])
    for lauf in _zwei(mit, vorlage):
        for ort in ORTSNAMEN:
            assert _keys(lauf, "telegram")[ort] == ["temp_max_c", "temp_min_c", "gust_max_kmh"], (
                _text(lauf.snap, "telegram"))
            assert _keys(lauf, "email")[ort] == ["gust_max_kmh"], _text(lauf.snap, "email")


def test_f003_channel_layouts_ohne_grundauswahl_wirkt_ungeschnitten(mit):
    """Ohne Grundauswahl (nie eingestellt) zeigt Telegram genau die dort
    angehakten Zeilen in Tabellenfolge. #3237: die Einstellung steht in der
    Tabelle (Grundauswahl = Standardsatz), nicht mehr in ``channel_layouts``."""
    from tests.helpers.tabelle_aus_wunsch import tabelle

    vorlage = _vorlage({"telegram": [_eintrag("gust", einfach=False), _eintrag("wind", einfach=False)]})
    dc = vorlage["display_config"]
    dc.pop("active_metrics")
    dc["placements"] = tabelle(dc, "compare", listen={"telegram": [("gust", False), ("wind", False)]},
                               outlook_reports=dc["placements"].get("outlook_reports"))
    for lauf in _zwei(mit, vorlage):
        for ort in ORTSNAMEN:
            assert _keys(lauf, "telegram")[ort] == ["gust_max_kmh", "wind_max_kmh"], (
                _text(lauf.snap, "telegram"))


# ---------------------------------------------------------------------------
# F004 -- Luecken-Zaehler mit channel_layouts: nur die Grundauswahl zaehlt
# ---------------------------------------------------------------------------


def test_f004_luecken_zaehler_ignoriert_channel_active_metrics_bei_channel_layouts(mit):
    """Eine unaufloesbare Kennung in ``channel_active_metrics["sms"]`` zaehlt
    nicht -- die SMS traegt kein ``?N``. #3237: das Altfeld wirkt gar nicht
    mehr (mit und ohne Kanal-Einstellung, AC-3/AC-6); entfallen ist der
    Altpfad-Fall "ohne ``channel_layouts`` zaehlt die Altliste" (== 1)."""
    from services.report_config_resolver import resolve_compare_render_options

    vorlage = _vorlage({"sms": _voll(GRUNDAUSWAHL)})
    vorlage["display_config"]["channel_active_metrics"] = {"sms": ["gibt_es_nicht"]}
    ohne_layouts = _vorlage(None)
    ohne_layouts["display_config"]["channel_active_metrics"] = {"sms": ["gibt_es_nicht"]}
    assert resolve_compare_render_options(ohne_layouts).unresolved_by_channel["sms"] == 0
    assert resolve_compare_render_options(vorlage).unresolved_by_channel["sms"] == 0
    for lauf in _zwei(mit, vorlage):
        sms = _text(lauf.snap, "sms")
        assert not re.search(r"\?\d", sms), sms
        assert _keys(lauf, "sms")["Innsbruck"], sms


# ---------------------------------------------------------------------------
# F005 -- Gewitter-Einfach in der HTML-Mail; doppelte Kennung
# ---------------------------------------------------------------------------


def test_f005_gewitter_einfach_zeigt_in_der_html_mail_den_ampelpunkt(mit):
    paare = [("temperature", "max"), ("thunder", "max")]
    roh = _grundauswahl(_vorlage({"email": _voll(["temperature", "thunder"])}), paare)
    einf = _grundauswahl(_vorlage({"email": _voll(["temperature", "thunder"], thunder={"einfach": True})}), paare)
    a_roh, _ = _zwei(mit, roh)
    assert _AMPEL_PUNKT not in _html_zeile(a_roh.snap.sendungen("email")[-1]["body"], "Gewitter")
    for lauf in _zwei(mit, einf):
        zeile = _html_zeile(lauf.snap.sendungen("email")[-1]["body"], "Gewitter")
        assert _AMPEL_PUNKT in zeile, zeile


def test_f005_doppelte_kennung_der_erste_eintrag_gilt(mit):
    """Steht dieselbe Kennung zweimal in der Liste, bestimmt der ERSTE
    Eintrag Position und Format (heutiges Verhalten festgelegt). #3237: die
    Liste ist die Tabelle -- eine erste Boeen-Zeile (Roh) ganz vorn, die
    spaetere doppelte Zeile (Einfach) hat keine Wirkung."""
    import copy

    vorlage = _vorlage({"email": _voll(GRUNDAUSWAHL, gust={"einfach": True})})
    zeilen = vorlage["display_config"]["placements"]["rows"]
    boeen = copy.deepcopy(next(z for z in zeilen if z["metric_id"] == "gust"))
    assert boeen["formats"]["email"] == "simplified", "Vorbedingung: spaetere Zeile Einfach"
    boeen["formats"]["email"] = "raw"
    zeilen.insert(0, boeen)
    for lauf in _zwei(mit, vorlage):
        assert _plain_wert(_text(lauf.snap, "email"), "Innsbruck", "Böen") == "19 km/h"
        assert _AMPEL_PUNKT not in _html_zeile(lauf.snap.sendungen("email")[-1]["body"], "Böen")
        assert _keys(lauf, "email")["Innsbruck"][0] == "gust_max_kmh"
