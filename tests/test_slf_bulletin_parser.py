"""SLF-Lawinen-Lagebericht: Parser und Modell (Issue #1441 Scheibe S3, AC-1 bis AC-7).

SPEC: docs/specs/modules/feat_1441_s3_slf.md -- AC-1 bis AC-7
HELPER: tests/helpers/slf_support.py (Fixtures tests/fixtures/slf/, README dort)

Die echte ``SlfSource`` laeuft ueber die echte Abrufschicht (``warn_egress.cached_fetch``); nur
der HTTP-Transport liefert die AUFGEZEICHNETEN SLF-Antworten. Punkte bestimmt ``interior_point``
aus dem Umriss der Fixture-Datei. Abgeleitete Varianten (nur ``dangerRatingValue`` geaendert)
tragen "abgeleitet" im Testnamen. Kein Netz, keine Mocks. Alle Importe der Prueflinge
(``services.official_alerts.slf``/``caaml``, Feld ``level_modifier``) stehen IN den Tests.
"""
from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tests.helpers import avalanche_report_support as s1
from tests.helpers.slf_support import (
    APRIL,
    JANUAR,
    SLF_URL,
    WINTER_ABEND,
    WINTER_MORGEN,
    FakeClock,
    SlfFixtureTransport,
    derive,
    interior_point,
    make_slf_source,
    slf_doc,
)

UTC = timezone.utc
_REPO = Path(__file__).resolve().parents[1]

# Abrufzeitpunkte innerhalb der jeweiligen Gueltigkeit (README der Fixtures)
_NOW = {
    WINTER_MORGEN: datetime(2026, 3, 1, 8, 0, tzinfo=UTC),    # 07:00Z-16:00Z
    WINTER_ABEND: datetime(2026, 3, 1, 17, 30, tzinfo=UTC),   # 03-01 16:00Z - 03-02 16:00Z
    JANUAR: datetime(2026, 1, 15, 8, 0, tzinfo=UTC),          # 07:00Z-16:00Z
    APRIL: datetime(2026, 4, 10, 8, 0, tzinfo=UTC),           # 06:00Z-15:00Z
}

# Laut Spec (Tabelle "Estimated Scope") aus avalanche_report.py nach caaml.py verschoben.
_VERSCHOBEN = ("_parse_time", "_elevation", "_time_of_day", "_carrier", "_problems",
               "_rated", "_find_region", "parse_region_alert")


def _slf_alerts(fixture, region_id: str, *, now: datetime | None = None):
    """Echte SlfSource, Fixture-Transport (Dateiname ODER abgeleitetes Dokument), Punkt in der
    Region. Liefert die Alert-Liste des Punkts."""
    from services.official_alerts import slf

    assert Path(slf.__file__).resolve().is_relative_to(_REPO), (
        f"Pruefling {slf.__file__} liegt ausserhalb von {_REPO}"
    )
    when = now or _NOW[fixture if isinstance(fixture, str) else WINTER_ABEND]
    transport = SlfFixtureTransport(fixture)
    source = make_slf_source(transport, FakeClock(when))
    return source.fetch(*interior_point(region_id))


def _one(fixture, region_id: str, **kw):
    alerts = _slf_alerts(fixture, region_id, **kw)
    assert len(alerts) == 1, f"{region_id}: genau eine Warnung erwartet, bekommen {alerts!r}"
    return alerts[0]


# ------------------------------------------------------------------ AC-1 Grundfall
def test_ac1_muenstertal_morgen_liefert_genau_eine_slf_warnung_mit_allen_feldern():
    """AC-1: Given at_2026-03-01T08:00Z, Punkt in CH-7231 (erheblich/minus, Altschnee ab 2000 m)
    When die Warnungen abgerufen werden
    Then genau eine avalanche_bulletin-Warnung mit Quelle, Dedup-ID, EAWS-Skala, Stufe 3,
    Hoehe oberhalb 2000, Problem persistent_weak_layers und konstanter SLF-Link-URL."""
    a = _one(WINTER_MORGEN, "CH-7231")

    assert a.hazard == "avalanche_bulletin"
    assert a.source == "slf_bulletin:CH-7231"
    assert a.dedup_id == "avalanche_bulletin:CH-7231"
    assert a.scale == "eaws"
    assert (a.native_level, a.level) == (3, 3)
    assert (a.elevation_value, a.elevation_direction) == ("2000", "above")
    assert a.problems == ("persistent_weak_layers",)
    assert a.url == SLF_URL


# ------------------------------------------------------------------ AC-2 Hoehe eindeutig
def test_ac2_muenstertal_abend_maessiges_nassschnee_problem_zaehlt_nicht_hoehe_oberhalb_2000():
    """AC-2: Given at_2026-03-01T17:30Z, CH-7231 (Altschnee ab 2000 = erheblich, Nassschnee
    bis 2200 = maessig) When abgerufen Then Hoehe woertlich "oberhalb 2000" -- das maessige
    Problem traegt das Rating nicht und zaehlt nicht mit."""
    a = _one(WINTER_ABEND, "CH-7231")

    assert a.native_level == 3
    assert (a.elevation_value, a.elevation_direction) == ("2000", "above")


def test_ac2_vouvry_januar_zwei_erhebliche_probleme_mit_gleicher_grenze_oberhalb_2000():
    """AC-2: Given at_2026-01-15T08:00Z, CH-1311 (zwei erhebliche Probleme, beide ab 2000 m)
    When abgerufen Then Hoehe "oberhalb 2000"."""
    a = _one(JANUAR, "CH-1311")

    assert a.native_level == 3
    assert (a.elevation_value, a.elevation_direction) == ("2000", "above")


def test_ac2_gegenprobe_abgeleitet_nassschnee_auf_erheblich_ergibt_keine_hoehe():
    """AC-2 Gegenprobe (abgeleitet, AC-4-Regel): Given dasselbe Abend-Bulletin, Nassschnee-
    Problem (bis 2200) auf "erheblich" gesetzt -- zwei tragende Probleme mit verschiedenen
    Grenzen When abgerufen Then keine Hoehe (nichts erfinden), Stufe bleibt 3."""
    abgeleitet = derive(slf_doc(WINTER_ABEND), "CH-7231",
                        problem_values={"wet_snow": "considerable"})

    a = _one(abgeleitet, "CH-7231", now=_NOW[WINTER_ABEND])

    assert a.native_level == 3
    assert a.elevation_value is None and a.elevation_direction is None


# ------------------------------------------------------------------ AC-3 Hoehe nur nach unten
def test_ac3_gadmertal_april_nassschnee_bis_2400_ergibt_unterhalb_2400():
    """AC-3: Given at_2026-04-10T08:00Z, CH-1246 (erheblich; Nassschnee bis 2400; geringes
    Zweitproblem ab 2000 traegt nicht) When abgerufen Then Hoehe "unterhalb 2400"."""
    a = _one(APRIL, "CH-1246")

    assert a.native_level == 3
    assert (a.elevation_value, a.elevation_direction) == ("2400", "below")


# ------------------------------------------------------------------ AC-4 mehrdeutig
def test_ac4_suedliches_praettigau_abend_zwei_verschiedene_grenzen_keine_hoehe():
    """AC-4: Given at_2026-03-01T17:30Z, CH-5112 (maessig; Altschnee ab 2000 UND Nassschnee
    bis 2200, beide maessig) When abgerufen Then Stufe 2 ohne jede Hoehenangabe."""
    a = _one(WINTER_ABEND, "CH-5112")

    assert a.native_level == 2
    assert a.elevation_value is None and a.elevation_direction is None


# ------------------------------------------------------------------ AC-5 keine Grenze
def test_ac5a_vallee_de_joux_stufe_1_lowerbound_0_ist_keine_hoehe():
    """AC-5 (a): Given at_2026-03-01T08:00Z, CH-8112 (Stufe 1, Gleitschnee mit lowerBound 0)
    When abgerufen Then keine Hoehe -- 0 heisst "keine Begrenzung", nie "oberhalb 0"."""
    a = _one(WINTER_MORGEN, "CH-8112")

    assert a.native_level == 1
    assert a.elevation_value is None and a.elevation_direction is None


def test_ac5b_vouvry_april_nachmittags_traegendes_problem_ohne_elevation_keine_hoehe():
    """AC-5 (b): Given at_2026-04-10T08:00Z, CH-1311 (Traeger erheblich "nachmittags", das
    tragende Nassschnee-Problem ohne elevation; geringes Problem ab 2000 traegt nicht)
    When abgerufen Then keine Hoehe und Tageszeit "later"."""
    a = _one(APRIL, "CH-1311")

    assert a.native_level == 3
    assert a.elevation_value is None and a.elevation_direction is None
    assert a.time_of_day == "later"


# ------------------------------------------------------------------ AC-6 Feinstufe
@pytest.mark.parametrize(
    "fixture, region, native, modifier",
    [
        (WINTER_MORGEN, "CH-7231", 3, "-"),     # subdivision minus
        (JANUAR, "CH-5112", 3, "+"),            # subdivision plus
        (WINTER_MORGEN, "CH-1246", 2, None),    # subdivision neutral
        (WINTER_MORGEN, "CH-8112", 1, None),    # Stufe 1, subdivision None
    ],
    ids=["minus", "plus", "neutral", "ohne"],
)
def test_ac6_feinstufe_im_modell_ziffer_bleibt_unveraendert(fixture, region, native, modifier):
    """AC-6: Given Ratings mit subdivision minus/plus/neutral/ohne When abgerufen
    Then level_modifier "-"/"+"/None/None und native_level 3/3/2/1."""
    a = _one(fixture, region)

    assert a.native_level == native
    assert a.level_modifier == modifier


def test_ac6_feinstufe_kommt_vom_traeger_rating_nicht_vom_ersten_rating():
    """AC-6 (Spec Abschnitt 6, Adversary F001): Given at_2026-04-10T08:00Z, CH-4242 -- erstes
    Rating maessig/ganztags mit subdivision minus, Traeger-Rating erheblich/nachmittags ohne
    Feinstufe When abgerufen Then native_level 3 und level_modifier None (Feinstufe des
    Traegers, nicht des ersten Ratings)."""
    a = _one(APRIL, "CH-4242")

    assert (a.native_level, a.time_of_day) == (3, "later")
    assert a.level_modifier is None


def test_ac6_level_modifier_ist_optionales_modellfeld_mit_default_none():
    """AC-6: Given das Modell OfficialAlert When ohne Feinstufe angelegt Then level_modifier
    ist None (Bestand bit-identisch)."""
    from services.official_alerts.models import OfficialAlert

    a = OfficialAlert(source="x", hazard="avalanche_bulletin", level=3, label="L")

    assert a.level_modifier is None


# ------------------------------------------------------------------ AC-7 S1 unveraendert
_S1_DATEI = "2026-01-30_AT-07_de_CAAMLv6.json"
_S1_REGION = "AT-07-28"
_S1_NOW = datetime(2026, 1, 30, 8, 0, tzinfo=UTC)


def _s1_source_alert(document: dict):
    transport = s1.FixtureTransport(
        {"AT-07": s1.Reply(200, json.dumps(document).encode("utf-8"))}
    )
    source = s1.make_source(transport, s1.FakeClock(_S1_NOW))
    alerts = source.fetch(*s1.P_TIROL_AT_07_28)
    assert len(alerts) == 1, f"S1-Quelle: genau ein Alert erwartet: {alerts!r}"
    return alerts[0]


def test_ac7_caaml_parser_liefert_auf_s1_fixture_dasselbe_wie_avalanche_report_source():
    """AC-7: Given das S1-Bulletin 2026-01-30 (AT-07-28) When es durch
    caaml.parse_region_alert und durch AvalancheReportSource laeuft Then sind beide Ergebnisse
    gleich (Stufe 3, oberhalb 2200 aus der Rating-elevation, keine Feinstufe)."""
    from services.official_alerts import caaml

    document = s1.doc(_S1_DATEI)
    aus_caaml = caaml.parse_region_alert(document, _S1_REGION, source="avalanche_report:AT-07")
    aus_quelle = _s1_source_alert(document)

    assert aus_caaml == aus_quelle
    assert (aus_caaml.native_level, aus_caaml.elevation_value,
            aus_caaml.elevation_direction) == (3, "2200", "above")
    assert aus_caaml.level_modifier is None


def test_ac7_abgeleitet_rating_mit_eigener_elevation_schlaegt_abweichende_problem_grenze():
    """AC-7 (abgeleitet): Given das S1-Bulletin, dessen tragendes Problem zusaetzlich die
    Rating-Stufe "erheblich" und eine ABWEICHENDE Grenze (unterhalb 1800) traegt
    When caaml.parse_region_alert und AvalancheReportSource es lesen
    Then bleibt die Hoehe die des Ratings (oberhalb 2200) -- die Hoehe-aus-Problem-Regel
    greift nur ohne Rating-elevation."""
    from services.official_alerts import caaml

    document = copy.deepcopy(s1.doc(_S1_DATEI))
    bulletin = next(b for b in document["bulletins"]
                    if any(r.get("regionID") == _S1_REGION for r in b["regions"]))
    for problem in bulletin["avalancheProblems"]:
        problem["dangerRatingValue"] = "considerable"
        problem["elevation"] = {"upperBound": "1800"}

    aus_caaml = caaml.parse_region_alert(document, _S1_REGION, source="avalanche_report:AT-07")
    aus_quelle = _s1_source_alert(document)

    assert (aus_caaml.elevation_value, aus_caaml.elevation_direction) == ("2200", "above")
    assert aus_caaml == aus_quelle


def test_ac7_avalanche_report_enthaelt_keine_eigene_kopie_der_verschobenen_funktionen():
    """AC-7: Given die Ausloesung nach caaml.py When avalanche_report die Funktionen nutzt
    Then stehen sie in caaml, und was avalanche_report davon fuehrt, ist DASSELBE Objekt
    (``is``); parse_region_alert bleibt fuer den S1-Bestand ueber avalanche_report erreichbar."""
    from services.official_alerts import avalanche_report, caaml

    fehlend = [n for n in _VERSCHOBEN if not hasattr(caaml, n)]
    assert not fehlend, f"caaml.py fehlt: {fehlend}"
    assert avalanche_report.parse_region_alert is caaml.parse_region_alert
    kopien = [n for n in _VERSCHOBEN
              if hasattr(avalanche_report, n) and getattr(avalanche_report, n) is not getattr(caaml, n)]
    assert not kopien, f"eigene Kopien in avalanche_report.py: {kopien}"
