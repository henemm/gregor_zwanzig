"""TDD RED -- Issue #3174: Trip-SMS ohne Doppelpunkt nach dem Etappen-Praefix.

SPEC: docs/specs/modules/feat_3174_trip_sms_ohne_doppelpunkt.md

PO-Auswahl 2026-11-19 ("Beide ohne", "Jedes Zeichen ist kostbar!!!"): wie die
Orte-SMS (``O1 D-5/0 ...``, #3172) schreibt die Trip-SMS ``E3 N12 D17 ...``.

AC -> Test:
  AC-1  test_ac1_trip_sms_beginnt_mit_praefix_ohne_doppelpunkt
        (+ Goldens ``tests/golden/trip_briefing_aufbau/*.sms.txt`` ueber den
        echten Versandweg, ``test_trip_briefing_aufbau.py`` AC-1/AC-2)
  AC-2  Goldens ``*.premium_sms.txt`` / ``*kurzform.telegram.txt`` desselben
        Versandwegs (zwei Nutzer, Transport-Mitschrift)
  AC-3  test_ac3_name_mit_km_bereich_und_freier_name
  AC-4  test_ac4_gespartes_zeichen_steht_fuer_werte_bereit,
        test_ac4_zeile_ohne_token_ist_nur_das_praefix
  AC-5  test_ac5_karte_ordnet_werte_trotz_tokenartigem_etappennamen
  AC-6  test_ac6_kuerzel_doppelpunkte_bleiben

Kern-Schicht: echte Renderer (``TripReportFormatter.format_email`` bzw.
``SMSTripFormatter.format_sms``, ``render_line``), echte Placements-Ansicht.
Kein Mock(), kein patch(), kein Netz.
"""
from __future__ import annotations

import re

import pytest

from output.renderers.sms_trip import SMSTripFormatter
from output.tokens.dto import Token, TokenLine
from output.tokens.render import render_line
from tests.helpers.ampel_allgemein import AMPEL_ALLGEMEIN
from tests.tdd import _sms_token_format_fixtures as F


def _format_sms(stage_name: str, max_length: int = 160) -> str:
    return SMSTripFormatter().format_sms(
        [F.segment()], stage_name=stage_name, report_type="evening", tz=F.TZ,
        night_weather=F.night_weather(), max_length=max_length, ampel=AMPEL_ALLGEMEIN,
    )


def test_ac1_trip_sms_beginnt_mit_praefix_ohne_doppelpunkt():
    sms = F.sms("temperature", "temperature_day_low", "temperature_day_high", "wind")
    assert sms.startswith(f"{F.STAGE_NAME} "), sms
    assert not sms.startswith(f"{F.STAGE_NAME}:"), sms
    # Das zweite Wort ist schon ein Token (kein leeres Wort, kein Doppelpunkt).
    zweites = sms.split(" ")[1]
    assert re.match(r"^[A-Z!]", zweites), sms


def test_ac1_etappe_n_wird_e_n_ohne_doppelpunkt():
    sms = _format_sms("Etappe 3: Kamm")
    assert sms.startswith("E3 "), sms
    assert "E3:" not in sms, sms


@pytest.mark.parametrize("name, kopf", [
    ("GR221 Mallorca km0-11", "GR221 km0-11 "),
    ("Ballone", "Ballone "),
    ("Ballone:", "Ballone "),
])
def test_ac3_name_mit_km_bereich_und_freier_name(name, kopf):
    sms = _format_sms(name)
    assert sms.startswith(kopf), sms
    assert f"{kopf.rstrip()}:" not in sms, sms


def _wort_token(n: int) -> Token:
    return Token(symbol="W", value=str(n), category="forecast", priority=1)


def test_ac4_gespartes_zeichen_steht_fuer_werte_bereit():
    # "E3" + 31 x " W123" = 2 + 31*5 = 157; dazu " W1" (+3) -> 160 ohne,
    # 161 mit Doppelpunkt. Ohne Doppelpunkt passt die Zeile ungekuerzt.
    tokens = tuple([_wort_token(123)] * 31 + [_wort_token(1)])
    zeile = TokenLine(stage_name="E3", report_type="evening", tokens=tokens)
    text = render_line(zeile, 160)
    assert len(text) == 160, (len(text), text)
    assert text.startswith("E3 W123 "), text
    assert text.endswith(" W1"), text
    assert zeile.truncated is False


def test_ac4_zeile_ohne_token_ist_nur_das_praefix():
    zeile = TokenLine(stage_name="E3", report_type="evening", tokens=())
    assert render_line(zeile, 160) == "E3"


def test_ac6_kuerzel_doppelpunkte_bleiben():
    sms = F.sms("thunder", "wind_direction")
    worte = sms.split(" ")
    assert any(w.startswith("TH:") for w in worte), sms
    assert any(w.startswith("WD:") for w in worte), sms
    assert worte[0] == F.STAGE_NAME, sms


# ---------------------------------------------------------------------------
# AC-5: Karte "Was steht wo" -- SMS-Beispiel und Werte je Metrik
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from api.routers import placements

    app = FastAPI()
    app.include_router(placements.router)
    return TestClient(app)


def test_ac5_karte_ordnet_werte_trotz_tokenartigem_etappennamen(client):
    from tests.tdd.test_placements_tabelle_endpoint import (
        NUTZER_A, _ok, _trip, _trip_versand_sms,
    )

    # Ein Etappenname, der wie ein Wind-Token aussieht: das Praefix darf nie
    # als Wert der Metrik "Wind" in die Karte geraten.
    _trip(NUTZER_A, "t-3174", etappe="W99")
    antwort = _ok(client, "t-3174", "route")
    versand = _trip_versand_sms(NUTZER_A, "t-3174")

    assert versand.startswith("W99 "), versand
    assert antwort["sms_example"]["text"] == versand
    token_teil = versand.split(" ")[1:]
    zeilen = {z["metric_id"]: z["cells"]["sms"] for z in antwort["rows"]}
    wind = zeilen["wind"]
    assert wind["state"] == "on"
    assert wind["example"] and wind["example"] != "W99", wind
    assert wind["example"] in token_teil, (wind["example"], versand)
    for mid, zelle in zeilen.items():
        if zelle["state"] == "on" and zelle.get("example"):
            for wort in zelle["example"].split(" "):
                assert wort in token_teil, (mid, zelle["example"], versand)
