"""Issue #3284: Kuerzel-Legende "Was steht wo" nennt beim Temperatur-Bereich kein ``L``.

SPEC: docs/specs/modules/fix_3284_legende_bereich_ohne_l.md (AC-1 bis AC-7).

Sind Tiefst- UND Hoechstwert eines Paares gewaehlt, verschmilzt der Token-Builder
beide zu EINEM Bereichs-Token unter dem Hoechstwert-Kuerzel (``D13/27``,
``FD10/14``; #1824). Ein eigenes ``L``/``FL`` sendet die SMS dann nicht -- die
Legende darf es nicht nennen (sonst steht ``L`` doppelt neben ``L`` = Stufe gelb).
Das Bereichs-Kuerzel traegt die zusammengesetzte Bedeutung aus dem Katalog.

Kern-Schicht: echter Endpunkt (TestClient), echte Renderer, kein Mock. Orakel ist
das SMS-Beispiel der Antwort (= Versand-SMS, in den Nachbartests belegt), roh
gelesen: ein Bereichs-Token zaehlt NUR als sein eigenes Kuerzel.

    uv run pytest tests/tdd/test_3284_legende_bereich_ohne_l.py -q
"""
from __future__ import annotations

import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.tdd.test_placements_tabelle_endpoint import NUTZER_A, _ok, _orte, _sprache, _trip

BEREICH = {
    "de": {"D": "Tagestiefstwert/Tageshöchstwert", "FD": "L gefühlt/D gefühlt"},
    "en": {"D": "day min/day max", "FD": "L feels like/D feels like"},
}

#: Feste Eintraege der Legende (Spec feat_3122 Nr. 12), unveraendert (AC-7).
FEST = [
    ("@14", "zeit_ab_gelb"), ("!TS:H@14", "amtliche_warnung"), ("L", "stufe_gelb"),
    ("M", "stufe_orange"), ("H", "stufe_rot"), ("WG", "warnung_wind"),
    ("RA", "warnung_starkregen"), ("AV4", "lawinenstufe"),
    ("X?", "warnquelle_nicht_erreichbar"),
]


@pytest.fixture
def client():
    from api.routers import placements

    app = FastAPI()
    app.include_router(placements.router)
    return TestClient(app)


@pytest.fixture(autouse=True)
def _deutsch_danach():
    yield
    _sprache(NUTZER_A, "de")


def _symbole() -> set[str]:
    from output.renderers.sms_trip import SMS_MULTI_SYMBOLS_BY_METRIC, SMS_SYMBOL_BY_METRIC

    return set(SMS_SYMBOL_BY_METRIC.values()) | {
        s for syms in SMS_MULTI_SYMBOLS_BY_METRIC.values() for s in syms}


def _roh_gesendet(sms: str) -> set[str]:
    """Kuerzel, die als eigenes Token in der SMS stehen (laengstes Symbol, ohne
    Doppelpunkt, Warnblock ausgenommen). ``D13/27`` zaehlt nur als ``D``."""
    alle = _symbole()
    out = set()
    for tok in sms.split(" "):
        treffer = [s for s in alle if tok.startswith(s)]
        if treffer and not tok.startswith("!"):
            out.add(max(treffer, key=len).rstrip(":"))
    return out


def _legende(antwort) -> dict[str, str]:
    eintraege = antwort["legend"]["metrics"]
    kuerzel = [e["kuerzel"] for e in eintraege]
    assert len(kuerzel) == len(set(kuerzel)), f"Kuerzel doppelt in legend.metrics: {kuerzel}"
    return {e["kuerzel"]: e["meaning"] for e in eintraege}


def _hat_bereich(sms: str, symbol: str) -> bool:
    return re.search(rf"(?:^| ){symbol}-?\d+/-?\d+(?: |$)", sms) is not None


def _trip_antwort(client, kennung, grund, lang):
    _sprache(NUTZER_A, lang)
    _trip(NUTZER_A, kennung, grund=grund)
    return _ok(client, kennung, "route")


# ---------------------------------------------------------------------------
# AC-1/AC-2: Orte, Tiefst + Hoechst -> nur D (Bereich), kein L
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("lang", ["de", "en"])
def test_orte_bereich_ohne_l(client, lang):
    _sprache(NUTZER_A, lang)
    _orte(NUTZER_A, f"o-3284-{lang}", anzahl=1)  # ORTE_GRUND: Temperatur max UND min
    antwort = _ok(client, f"o-3284-{lang}", "vergleich")
    sms = antwort["sms_example"]["text"]

    assert _hat_bereich(sms, "D"), sms
    assert "L" not in _roh_gesendet(sms), sms
    legende = _legende(antwort)
    assert "L" not in legende, legende
    assert legende.get("D") == BEREICH[lang]["D"], legende


# ---------------------------------------------------------------------------
# AC-3: Trip, Tages-Tief + Tages-Hoch -> dito
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("lang", ["de", "en"])
def test_trip_bereich_ohne_l(client, lang):
    antwort = _trip_antwort(client, f"t-3284-{lang}",
                            ["temperature_day_low", "temperature_day_high", "wind"], lang)
    sms = antwort["sms_example"]["text"]

    assert _hat_bereich(sms, "D"), sms
    legende = _legende(antwort)
    assert "L" not in legende, legende
    assert legende.get("D") == BEREICH[lang]["D"], legende


# ---------------------------------------------------------------------------
# AC-4: gefuehlte Werte -> nur FD (Bereich), kein FL
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("lang", ["de", "en"])
def test_trip_gefuehlt_bereich_ohne_fl(client, lang):
    antwort = _trip_antwort(client, f"t-3284-f-{lang}",
                            ["wind_chill_day_low", "wind_chill_day_high", "wind"], lang)
    sms = antwort["sms_example"]["text"]

    assert _hat_bereich(sms, "FD"), sms
    legende = _legende(antwort)
    assert "FL" not in legende, legende
    assert legende.get("FD") == BEREICH[lang]["FD"], legende


# ---------------------------------------------------------------------------
# AC-5: jedes Legenden-Kuerzel wird wirklich gesendet, keines doppelt
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("lang", ["de", "en"])
@pytest.mark.parametrize("fall", ["orte", "trip", "trip_gefuehlt", "trip_nur_tief"])
def test_legende_nennt_nur_gesendete_kuerzel(client, fall, lang):
    if fall == "orte":
        _sprache(NUTZER_A, lang)
        _orte(NUTZER_A, f"o-3284-g-{lang}", anzahl=1)
        antwort = _ok(client, f"o-3284-g-{lang}", "vergleich")
    else:
        grund = {
            "trip": ["temperature_day_low", "temperature_day_high", "wind", "gust"],
            "trip_gefuehlt": ["wind_chill_day_low", "wind_chill_day_high", "wind"],
            "trip_nur_tief": ["temperature_day_low", "wind"],
        }[fall]
        antwort = _trip_antwort(client, f"t-3284-g-{fall}-{lang}", grund, lang)
    sms = antwort["sms_example"]["text"]
    legende = _legende(antwort)
    assert set(legende) <= _roh_gesendet(sms), (set(legende) - _roh_gesendet(sms), sms)


# ---------------------------------------------------------------------------
# AC-6: nur Tiefstwert -> L wird gesendet und bleibt (PO 2026-11-23)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("lang", ["de", "en"])
def test_nur_tiefstwert_behaelt_l(client, lang):
    antwort = _trip_antwort(client, f"t-3284-t-{lang}", ["temperature_day_low", "wind"], lang)
    sms = antwort["sms_example"]["text"]

    assert "L" in _roh_gesendet(sms), sms
    assert not _hat_bereich(sms, "D"), sms
    legende = _legende(antwort)
    assert legende.get("L") == {"de": "Tagestiefstwert", "en": "day min"}[lang], legende
    assert "D" not in legende, legende


# ---------------------------------------------------------------------------
# AC-7: feste Eintraege unveraendert
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("kind", ["route", "vergleich"])
def test_feste_eintraege_unveraendert(client, kind):
    if kind == "route":
        antwort = _trip_antwort(client, "t-3284-fix",
                                ["temperature_day_low", "temperature_day_high", "wind"], "de")
    else:
        _orte(NUTZER_A, "o-3284-fix", anzahl=1)
        antwort = _ok(client, "o-3284-fix", "vergleich")
    fest = [(e["token"], e["key"]) for e in antwort["legend"]["fixed"]]
    assert fest[:len(FEST)] == FEST, fest
