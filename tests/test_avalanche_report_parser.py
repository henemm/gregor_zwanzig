"""CAAML-v6-Parser `parse_region_alert` auf aufgezeichneten Bulletins (AC-2, AC-3).

SPEC: docs/specs/modules/avalanche_report_bulletin.md -- AC-2, AC-3
VERTRAG: docs/artifacts/feat-1441-s1-lawinenlagebericht/red-contract.md Abschnitt 2

Eingaben sind die aufgezeichneten Dateien unter tests/fixtures/avalanche_report/ (Herkunft und die
drei abgeleiteten Dateien: README.md dort). Der Parser ist rein (keine Gueltigkeitspruefung).
"""
from __future__ import annotations

import copy
import json
from datetime import datetime, timezone

import pytest

from tests.helpers.avalanche_report_support import BULLETINS, DERIVED, doc, parse_alert

UTC = timezone.utc


def test_ac2_zahl_bleibt_zahl_oberhalb_2200():
    a = parse_alert("2026-01-30_AT-07_de_CAAMLv6.json", "AT-07-28")

    assert a is not None
    assert (a.native_level, a.elevation_value, a.elevation_direction) == (3, "2200", "above")
    assert a.time_of_day is None


def test_ac2_treeline_erscheint_woertlich_als_waldgrenze_ohne_erfundene_zahl():
    a = parse_alert("2026-03-01_AT-07_de_CAAMLv6.json", "AT-07-05")

    assert (a.native_level, a.elevation_value, a.elevation_direction) == (3, "Waldgrenze", "above")
    assert not any(ch.isdigit() for ch in a.elevation_value)


def test_ac2_nachmittags_split_hoechste_stufe_traegt_ihre_eigene_hoehenangabe():
    """2026-04-06, AT-07-20: vormittags Stufe 2 ohne Hoehe; nachmittags Stufe 3 UNTERHALB
    2200 m und Stufe 2 oberhalb. Die Hoechststufe (3) ist nachmittags und gilt unterhalb 2200 m."""
    a = parse_alert("2026-04-06_AT-07_de_CAAMLv6.json", "AT-07-20")

    assert a.native_level == 3 and a.level == 3
    assert (a.elevation_value, a.elevation_direction) == ("2200", "below")
    assert a.time_of_day == "later"


def test_ac2_gleichstand_der_hoechststufe_nimmt_das_rating_ohne_hoehenbegrenzung():
    """2026-02-26, AT-07-05: Stufe 3 steht vormittags ab Waldgrenze UND nachmittags ohne Hoehe.
    Gemeldet wird die breitere Aussage (keine Hoehe) -- "ab Waldgrenze" wuerde sie verkuerzen.
    Die Maxima beider Tageshaelften sind gleich -> keine Tageszeit."""
    a = parse_alert("2026-02-26_AT-07_de_CAAMLv6.json", "AT-07-05")

    assert a.native_level == 3
    assert a.elevation_value is None and a.elevation_direction is None
    assert a.time_of_day is None


def test_ac2_ganztags_bulletin_hat_keine_tageszeit():
    a = parse_alert("2026-02-20_AT-07_de_CAAMLv6.json", "AT-07-25")

    assert a.time_of_day is None


def test_ac2_bulletin_ohne_hoehenbegrenzung_liefert_keine_hoehenangabe():
    a = parse_alert("2026-03-01_AT-02_de_CAAMLv6.json", "AT-02-05-02")

    assert (a.elevation_value, a.elevation_direction) == (None, None)


def _alle_bulletin_dateien():
    return sorted(BULLETINS.glob("20*_de_CAAMLv6.json")) + sorted(DERIVED.glob("*.json"))


@pytest.mark.parametrize("path", _alle_bulletin_dateien(), ids=lambda p: p.name)
def test_ac2_kein_erfundener_zahlenwert_in_keiner_aufgezeichneten_datei(path):
    """Eigenschaft ueber ALLE Regionen ALLER Fixtures: jede Hoehenangabe des Parsers ist
    entweder `Waldgrenze` oder genau ein im Bulletin vorkommender Zahlenwert."""
    from services.official_alerts.avalanche_report import parse_region_alert

    document = json.loads(path.read_text(encoding="utf-8"))
    pruefungen = 0
    for bulletin in document["bulletins"]:
        erlaubt = set()
        for rating in bulletin["dangerRatings"]:
            for bound in (rating.get("elevation") or {}).values():
                erlaubt.add("Waldgrenze" if bound == "treeline" else str(bound))
        for region in bulletin["regions"]:
            alert = parse_region_alert(document, region["regionID"])
            assert alert is not None, f"{path.name}: {region['regionID']} nicht geparst"
            if alert.elevation_value is not None:
                assert alert.elevation_value in erlaubt, (
                    f"{path.name} {region['regionID']}: {alert.elevation_value!r} nicht im Bulletin ({erlaubt})"
                )
                assert alert.elevation_direction in ("above", "below")
            pruefungen += 1
    assert pruefungen > 0


@pytest.mark.parametrize(
    "datei, region, native, level",
    [
        ("2026-03-01_AT-02_de_CAAMLv6.json", "AT-02-05-02", 1, 1),     # low
        ("2026-03-01_AT-07_de_CAAMLv6.json", "AT-07-29-02", 2, 2),     # moderate
        ("2026-01-30_AT-07_de_CAAMLv6.json", "AT-07-28", 3, 3),        # considerable
        ("2026-02-20_AT-07_de_CAAMLv6.json", "AT-07-25", 4, 4),        # high
        ("derived/2026-02-20_AT-07_de_CAAMLv6_DERIVED_very_high.json", "AT-07-25", 5, 4),  # very_high (abgeleitet)
    ],
)
def test_ac3_originalstufen_1_bis_5_und_abgeleitetes_farblevel(datei, region, native, level):
    a = parse_alert(datei, region)

    assert a.native_level == native
    assert a.level == level, "5 wird nur fuer die Farbe auf 4 abgebildet, native_level bleibt 5"
    assert a.scale == "eaws"


def test_ac3_stufe_5_wird_nie_auf_4_gequetscht():
    vier = parse_alert("2026-02-20_AT-07_de_CAAMLv6.json", "AT-07-25")
    fuenf = parse_alert("derived/2026-02-20_AT-07_de_CAAMLv6_DERIVED_very_high.json", "AT-07-25")

    assert (vier.native_level, fuenf.native_level) == (4, 5)
    assert vier.level == fuenf.level == 4


@pytest.mark.parametrize("native, wort", [(1, "gering"), (2, "mäßig"), (3, "erheblich"), (4, "groß"), (5, "sehr groß")])
def test_ac3_label_traegt_stufe_und_eaws_wort(native, wort):
    src = {1: ("2026-03-01_AT-02_de_CAAMLv6.json", "AT-02-05-02"),
           2: ("2026-03-01_AT-07_de_CAAMLv6.json", "AT-07-29-02"),
           3: ("2026-01-30_AT-07_de_CAAMLv6.json", "AT-07-28"),
           4: ("2026-02-20_AT-07_de_CAAMLv6.json", "AT-07-25"),
           5: ("derived/2026-02-20_AT-07_de_CAAMLv6_DERIVED_very_high.json", "AT-07-25")}[native]

    a = parse_alert(*src)

    assert a.label == f"Lawinenstufe {native} ({wort})"


def test_ac1_felder_url_zeitraum_region_und_dedup_id():
    a = parse_alert("2026-02-20_AT-07_de_CAAMLv6.json", "AT-07-25")

    assert a.url == "https://avalanche.report/bulletin/2026-02-20?region=AT-07-25"
    assert a.valid_from == datetime(2026, 2, 19, 16, 0, tzinfo=UTC)
    assert a.valid_to == datetime(2026, 2, 20, 16, 0, tzinfo=UTC)
    assert a.region_label == "Lasörlinggruppe"
    assert a.dedup_id == "avalanche_bulletin:AT-07-25", "stabil je Mikroregion, nicht die bulletinID"
    assert a.problems == ("persistent_weak_layers", "wind_slab", "new_snow")


def test_ac1_url_datum_ist_ortsdatum_des_gueltigkeitsendes_auch_in_der_sommerzeit():
    """Mai: endTime 2026-05-02T15:00Z = 17:00 Ortszeit (MESZ) am 02.05."""
    a = parse_alert("2026-05-02_AT-07_de_CAAMLv6.json", "AT-07-05")

    assert a.url == "https://avalanche.report/bulletin/2026-05-02?region=AT-07-05"
    assert a.native_level == 1


def test_ac1_probleme_ohne_dubletten_in_bulletin_reihenfolge():
    """Das Bulletin 2026-04-06 nennt jedes Problem zweimal (vormittags/nachmittags)."""
    a = parse_alert("2026-04-06_AT-07_de_CAAMLv6.json", "AT-07-20")

    assert a.problems == ("persistent_weak_layers", "wet_snow")


def test_ac2_alle_caaml_problemcodes_bleiben_erhalten():
    """Synthetisch (CAAML-Schema, NICHT aufgezeichnet): ein echtes Bulletin, dessen Problemliste
    durch drei im Schema erlaubte, in den ~100 gescannten Winterdateien nie vorkommende Codes
    ersetzt ist."""
    from services.official_alerts.avalanche_report import parse_region_alert

    d = copy.deepcopy(doc("2026-03-01_AT-07_de_CAAMLv6.json"))
    bulletin = next(b for b in d["bulletins"] if any(r["regionID"] == "AT-07-05" for r in b["regions"]))
    bulletin["avalancheProblems"] = [
        {"problemType": "no_distinct_avalanche_problem", "validTimePeriod": "all_day"},
        {"problemType": "favourable_situation", "validTimePeriod": "all_day"},
        {"problemType": "cornices", "validTimePeriod": "all_day"},
    ]

    a = parse_region_alert(d, "AT-07-05")

    assert a.problems == ("no_distinct_avalanche_problem", "favourable_situation", "cornices")


def test_ac1_region_die_in_keinem_bulletin_steht_liefert_none():
    from services.official_alerts.avalanche_report import parse_region_alert

    assert parse_region_alert(doc("2026-03-01_AT-07_de_CAAMLv6.json"), "AT-99-99") is None


def test_ac3_parser_ist_deterministisch_und_veraendert_die_eingabe_nicht():
    from services.official_alerts.avalanche_report import parse_region_alert

    d = doc("2026-04-06_AT-07_de_CAAMLv6.json")
    vorher = copy.deepcopy(d)

    ergebnisse = [parse_region_alert(d, "AT-07-20") for _ in range(3)]

    assert ergebnisse[0] == ergebnisse[1] == ergebnisse[2]
    assert d == vorher
