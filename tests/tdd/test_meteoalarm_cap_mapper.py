"""Kern-Tests fuer den geteilten MeteoAlarm-CAP-Mapper (Issue #2266, Epic #2258).

SPEC: docs/specs/modules/refactor_2266_meteoalarm_edr_rueckbau.md (AC-3)

Herkunft: umgezogen aus ``tests/tdd/test_meteoalarm_source.py`` (modulweit
``live``-markiert, wird mit der EDR-Klasse geloescht). Kopiert wurden die dort
netzfreien Tests um :206, :238, :313, :395, :540, :697, :786, :2346, :2380; die
gemischten Tests um :2251 und :2306 sind auf ihren bleibenden Anteil entmischt
(die Haelfte ueber ``MeteoAlarmSource`` entfaellt, der AT-Weg ist seit #1445 S3
``MeteoAlarmFeedSource("AT")``). Ergaenzt (AC-3 verlangt sie in DIESER Datei):
Lawine Typ 9 ueber den XML- und den Feed-Sammelweg, verworfene Typen und der
XML-Sammler ``_collect_cap_info_entries``.

Bewusst NICHT uebernommen: die Autouse-Fixture der Altdatei (sie leert
EDR-Index-/Geometrie-Caches, die mit dem Rueckbau verschwinden) und jeder Bezug
auf ``MeteoAlarmSource``, Budget, Index, Geometrie oder EDR-only-Fixtures.

Der Mapper (``_group_and_map_info_entries``) traegt die amtlichen Warnungen fuer
AT/IT/DE ueber den Feed-Weg -- ein versehentliches Loeschen oder Verfaelschen
muss hier einen Kern-Test rot machen.

Kern-Schicht: OHNE ``live``-Marker, ohne Netz, nur versionierte Fixtures unter
``tests/fixtures/meteoalarm/`` (aufgezeichnet bzw. dort dokumentiert abgeleitet).
Testquellen fuer den Registry-Pfad sind reale Objekte, die das
``OfficialAlertSource``-Protocol strukturell erfuellen -- kein Mock.
"""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

from services.official_alerts.models import OfficialAlert

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "meteoalarm"

VILLACH = (46.61, 13.85)
HAUTE_CORSE = (42.3, 9.15)


def _read_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# CAP-XML -> OfficialAlert (_extract_alerts_from_cap / _collect_cap_info_entries)
# ---------------------------------------------------------------------------

def test_gruene_stufe_level1_wird_gefiltert():
    """(aus :313) GIVEN eine CAP-Fixture mit awareness_level='1; green; Minor',
    WHEN die Mapping-Funktion sie verarbeitet, THEN entsteht KEIN OfficialAlert."""
    from services.official_alerts.meteoalarm import _extract_alerts_from_cap

    alerts = _extract_alerts_from_cap(_read_fixture("cap_green_level1.xml"))

    assert alerts == [], f"Level-1 (gruen) muss gefiltert werden, erhalten: {alerts}"


def test_kaputtes_cap_xml_wird_uebersprungen_kein_crash():
    """(aus :395) GIVEN eine strukturell kaputte CAP-XML-Fixture, WHEN die
    Mapping-Funktion sie verarbeitet, THEN wirft sie nicht und liefert []."""
    from services.official_alerts.meteoalarm import _collect_cap_info_entries, _extract_alerts_from_cap

    cap_text = _read_fixture("cap_broken.xml")

    assert _collect_cap_info_entries(cap_text) == []
    assert _extract_alerts_from_cap(cap_text) == []


def test_xml_sammler_liefert_jeden_info_block_normalisiert():
    """GIVEN die aufgezeichnete CAP-Datei mit Lawine + Hitze in je zwei Sprachen
    (4 ``<info>``-Bloecke), WHEN ``_collect_cap_info_entries`` sie sammelt, THEN
    entstehen 4 normalisierte Eintraege mit Sprache, Rohstufe und Rohtyp."""
    from services.official_alerts.meteoalarm import _collect_cap_info_entries

    entries = _collect_cap_info_entries(_read_fixture("cap_avalanche_plus_heat.xml"))

    assert [(e["lang"], e["type_raw"], e["level_raw"]) for e in entries] == [
        ("de-DE", "9; avalanche", "3; orange; Severe"),
        ("en-GB", "9; avalanche", "3; orange; Severe"),
        ("de-DE", "5; high-temperature", "2; yellow; Moderate"),
        ("en-GB", "5; high-temperature", "2; yellow; Moderate"),
    ]
    assert {e["area_desc"] for e in entries} == {"Villach (Stadt)"}


def test_lawine_typ9_und_hitze_werden_gruppiert_gemappt_deutsch_bevorzugt():
    """GIVEN dieselbe CAP-Datei, WHEN sie ueber den CAP-Weg gemappt wird, THEN
    entstehen genau ZWEI Warnungen (Sprachbloecke gruppiert): ``avalanche``
    Stufe 3 und ``extreme_heat`` Stufe 2, Label aus dem deutschen Block,
    Region und Gueltigkeit aus der CAP-Datei."""
    from services.official_alerts.meteoalarm import _extract_alerts_from_cap, _parse_iso

    alerts = _extract_alerts_from_cap(_read_fixture("cap_avalanche_plus_heat.xml"))

    assert [(a.hazard, a.level, a.label) for a in alerts] == [
        ("avalanche", 3, "Lawinenwarnung"),
        ("extreme_heat", 2, "Hitzewarnung"),
    ], f"erhalten: {alerts}"
    for a in alerts:
        assert a.source == "meteoalarm"
        assert a.region_label == "Villach (Stadt)"
        assert a.valid_from == _parse_iso("2026-07-15T00:00:00+02:00")
        assert a.valid_to == _parse_iso("2026-07-15T23:59:59+02:00")


def test_lawine_typ9_ueber_den_feed_sammelweg_je_land():
    """GIVEN die (dokumentiert abgeleitete) Feed-Fixture mit je einem Typ-9-Eintrag
    fuer IT/AT/DE, WHEN der Feed-Sammler ``_info_entries_from_alert`` und danach
    der geteilte Mapper laufen (der Produktivweg des Feeds), THEN wird jeder
    Eintrag genau EINE ``avalanche``-Warnung der Stufe 3 mit seiner Region."""
    from services.official_alerts.meteoalarm import _group_and_map_info_entries
    from services.official_alerts.meteoalarm_feed import _info_entries_from_alert

    feed = json.loads(_read_fixture("feed_avalanche_type9.json"))
    erwartete_region = {"IT": "Lazio", "AT": "Lienz", "DE": "Kreis Garmisch-Partenkirchen"}

    for land, region in erwartete_region.items():
        warnungen = feed[land]["warnings"]
        assert len(warnungen) == 1, f"Aufbaupruefung {land}: genau ein Eintrag erwartet"
        alerts = _group_and_map_info_entries(_info_entries_from_alert(warnungen[0]["alert"]))
        assert [(a.hazard, a.level, a.region_label) for a in alerts] == [("avalanche", 3, region)], (
            f"{land}: Typ 9 muss genau eine Lawinenwarnung Stufe 3 ergeben, erhalten: {alerts}"
        )


def test_verworfene_und_unbekannte_typen_fallen_weg_typ9_bleibt():
    """GIVEN Eintraege der Typen 4 (Nebel), 7 (Kueste), 99 (unbekannt) neben
    einer Typ-9-Warnung, WHEN sie durch den geteilten Mapper laufen, THEN bleibt
    genau die Typ-9-Warnung uebrig -- auch hohe Stufen verworfener Typen."""
    from services.official_alerts.meteoalarm import _group_and_map_info_entries

    def _entry(type_raw: str, level_raw: str) -> dict:
        return {
            "type_raw": type_raw, "level_raw": level_raw,
            "onset": "2026-07-15T00:00:00+02:00", "expires": "2026-07-15T23:59:59+02:00",
            "area_desc": "Villach (Stadt)", "lang": "de-DE",
            "event": f"Typ {type_raw}", "headline": f"Typ {type_raw}",
        }

    alerts = _group_and_map_info_entries([
        _entry("4; fog", "3; orange; Severe"),
        _entry("7; coastal-event", "2; yellow; Moderate"),
        _entry("99; unbekannt", "4; red; Extreme"),
        _entry("9; avalanche", "3; orange; Severe"),
    ])

    assert [(a.hazard, a.level) for a in alerts] == [("avalanche", 3)], f"erhalten: {alerts}"


def test_awareness_type_12_flooding_mappt_auf_flood_nicht_rain():
    """(aus :2346) GIVEN die echte, aufgezeichnete Warnung vom awareness_type 12
    ('flooding', RO/Alba, 2026-07-31), WHEN die Gefahren-Zuordnung des Moduls
    auf den aus der CAP-XML gelesenen Rohwert angewendet wird, THEN 'flood'."""
    from services.official_alerts.meteoalarm import (
        _TYPE_HAZARD_MAP,
        _find_parameter,
        _leading_int,
        _local_tag,
    )

    root = ET.fromstring(_read_fixture("cap_flooding_type12_ro.xml"))
    info = next(child for child in root if _local_tag(child) == "info")
    type_raw = _find_parameter(info, "awareness_type")

    assert type_raw == "12; flooding", f"Fixture-Rohwert gelesen: {type_raw!r}"
    assert _TYPE_HAZARD_MAP.get(_leading_int(type_raw)) == "flood"


def test_awareness_type_13_rainflood_mappt_auf_flood_nicht_unabgebildet():
    """(aus :2380) GIVEN die echte, aufgezeichnete Warnung vom awareness_type 13
    ('rain-flood', RO/Alba, 2026-07-31), WHEN dieselbe Zuordnung angewendet wird,
    THEN 'flood' (frueher unabgebildet, die Warnung fiel weg)."""
    from services.official_alerts.meteoalarm import (
        _TYPE_HAZARD_MAP,
        _find_parameter,
        _leading_int,
        _local_tag,
    )

    root = ET.fromstring(_read_fixture("cap_rainflood_type13_ro.xml"))
    info = next(child for child in root if _local_tag(child) == "info")
    type_raw = _find_parameter(info, "awareness_type")

    assert type_raw == "13; rain-flood", f"Fixture-Rohwert gelesen: {type_raw!r}"
    assert _TYPE_HAZARD_MAP.get(_leading_int(type_raw)) == "flood"


# ---------------------------------------------------------------------------
# Punkt-Kollaps in get_official_alerts_for_location() (aus :206, :238, :697)
# ---------------------------------------------------------------------------

class _FixedGeoSphereLikeSource:
    """Reale Test-Quelle (kein Mock): fester Hitze-Alert, GeoSphere-typisches Label."""

    name = "fixed_geosphere_like_test_source"

    def __init__(self, level: int = 2) -> None:
        self._level = level

    def covers(self, lat: float, lon: float) -> bool:
        return True

    def fetch(self, lat: float, lon: float) -> list[OfficialAlert]:
        return [OfficialAlert(source="geosphere_warn", hazard="extreme_heat", level=self._level,
                              label="Hitze", region_label="Villach")]


class _FixedMeteoAlarmLikeSource:
    """Reale Test-Quelle (kein Mock): fester Hitze-Alert, MeteoAlarm-typisches Label."""

    name = "fixed_meteoalarm_like_test_source"

    def __init__(self, level: int = 2) -> None:
        self._level = level

    def covers(self, lat: float, lon: float) -> bool:
        return True

    def fetch(self, lat: float, lon: float) -> list[OfficialAlert]:
        return [OfficialAlert(source="meteoalarm", hazard="extreme_heat", level=self._level,
                              label="Hitzewarnung", region_label="Villach (Stadt)")]


class _FixedFrSource:
    """Reale Test-Quelle (kein Mock): liefert genau einen festen FR-artigen Alert."""

    def __init__(self, name: str, alert: OfficialAlert) -> None:
        self.name = name
        self._alert = alert

    def covers(self, lat: float, lon: float) -> bool:
        return True

    def fetch(self, lat: float, lon: float) -> list[OfficialAlert]:
        return [self._alert]


_VIGILANCE_GEWITTER = OfficialAlert(source="meteofrance_vigilance", hazard="thunderstorm", level=3,
                                    label="Gewitter Haute-Corse", region_label="Haute-Corse")
_VIGILANCE_GEWITTER_SCHWACH = OfficialAlert(source="meteofrance_vigilance", hazard="thunderstorm", level=1,
                                            label="Gewitter (schwach) Haute-Corse", region_label="Haute-Corse")
_METEO_FORETS = OfficialAlert(source="meteo_forets", hazard="wildfire_risk", level=2,
                              label="Waldbrandgefahr Haute-Corse", region_label="Haute-Corse")
_MASSIF_CLOSURE = OfficialAlert(source="massif_closure", hazard="access_ban", level=3,
                                label="Zugang eingeschraenkt — Massif de l'Esterel", region_label=None,
                                dedup_id="ESTEREL-MASSIF-ID")


def _mit_quellen(quellen, lat, lon):
    import services.official_alerts.base as oa_base
    from services.official_alerts import get_official_alerts_for_location, register_official_alert_source

    backup = list(oa_base._REGISTERED_SOURCES)
    oa_base._REGISTERED_SOURCES.clear()
    try:
        for quelle in quellen:
            register_official_alert_source(quelle)
        return get_official_alerts_for_location(lat, lon)
    finally:
        oa_base._REGISTERED_SOURCES.clear()
        oa_base._REGISTERED_SOURCES.extend(backup)


def test_punkt_kollaps_gleiche_stufe_erste_quelle_bleibt():
    """(aus :206) GIVEN zwei Quellen melden fuer denselben Punkt ``extreme_heat``
    Stufe 2, WHEN ``get_official_alerts_for_location`` laeuft, THEN genau EIN
    Alert, Repraesentant ist die zuerst registrierte Quelle."""
    alerts = _mit_quellen([_FixedGeoSphereLikeSource(2), _FixedMeteoAlarmLikeSource(2)], *VILLACH)

    heat = [a for a in alerts if a.hazard == "extreme_heat"]
    assert len(heat) == 1, f"zu EINEM Alert kollabieren, erhalten {len(heat)}"
    assert heat[0].region_label == "Villach"


def test_punkt_kollaps_hoehere_stufe_gewinnt():
    """(aus :238) GIVEN dieselbe Konstellation, die zweite Quelle meldet Stufe 3,
    WHEN der Punkt-Kollaps laeuft, THEN gewinnt die hoehere Stufe samt Label."""
    alerts = _mit_quellen([_FixedGeoSphereLikeSource(2), _FixedMeteoAlarmLikeSource(3)], *VILLACH)

    heat = [a for a in alerts if a.hazard == "extreme_heat"]
    assert len(heat) == 1
    assert heat[0].level == 3
    assert heat[0].region_label == "Villach (Stadt)"


def test_registry_pfad_fr_quellen_kein_kollaps_bei_verschiedenen_gefahren():
    """(aus :697) GIVEN drei FR-artige Quellen mit drei verschiedenen Gefahren am
    selben Punkt, WHEN der echte Registry-Pfad laeuft, THEN bleiben alle drei in
    Registrierungsreihenfolge erhalten; bei GLEICHER Gefahr kollabiert es
    generisch auf die hoechste Stufe der zuerst registrierten Quelle."""
    alerts = _mit_quellen([
        _FixedFrSource("vig", _VIGILANCE_GEWITTER),
        _FixedFrSource("forets", _METEO_FORETS),
        _FixedFrSource("massif", _MASSIF_CLOSURE),
    ], *HAUTE_CORSE)

    assert [(a.hazard, a.level, a.label) for a in alerts] == [
        ("thunderstorm", 3, "Gewitter Haute-Corse"),
        ("wildfire_risk", 2, "Waldbrandgefahr Haute-Corse"),
        ("access_ban", 3, "Zugang eingeschraenkt — Massif de l'Esterel"),
    ]

    alerts = _mit_quellen([
        _FixedFrSource("vig", _VIGILANCE_GEWITTER),
        _FixedFrSource("vig_low", _VIGILANCE_GEWITTER_SCHWACH),
    ], *HAUTE_CORSE)
    thunder = [a for a in alerts if a.hazard == "thunderstorm"]
    assert [(a.level, a.label) for a in thunder] == [(3, "Gewitter Haute-Corse")]


# ---------------------------------------------------------------------------
# dedupe_official_alerts (aus :540, :786)
# ---------------------------------------------------------------------------

def test_fr_dedup_regression_unveraendert():
    """(aus :540) GIVEN die FR-Faelle aus #1035/#1036/#1037, WHEN
    ``dedupe_official_alerts`` laeuft, THEN 4 Gruppen, hoechste Stufe gewinnt,
    Segment-Union, keine falsche Kollision."""
    from output.renderers.alert.official_alerts import dedupe_official_alerts

    heat_low = OfficialAlert(source="meteofrance_vigilance", hazard="extreme_heat", level=2,
                             label="Hitzewarnung Haute-Corse", region_label="Haute-Corse")
    heat_high = OfficialAlert(source="meteofrance_vigilance", hazard="extreme_heat", level=4,
                              label="Hitzewarnung Haute-Corse", region_label="Haute-Corse")
    massif_low = OfficialAlert(source="massif_closure", hazard="access_ban", level=3,
                               label="Zugang eingeschraenkt — Massif de l'Esterel", region_label=None,
                               dedup_id="ESTEREL-MASSIF-ID")
    massif_high = OfficialAlert(source="massif_closure", hazard="access_ban", level=4,
                                label="Zugang gesperrt — Massif de l'Esterel", region_label=None,
                                dedup_id="ESTEREL-MASSIF-ID")
    thunder = OfficialAlert(source="meteofrance_vigilance", hazard="thunderstorm", level=3,
                            label="Gewitter Haute-Corse", region_label="Haute-Corse")
    heat_other_region = OfficialAlert(source="meteofrance_vigilance", hazard="extreme_heat", level=3,
                                      label="Hitzewarnung Corse-du-Sud", region_label="Corse-du-Sud")

    deduped = dedupe_official_alerts([
        (heat_low, ["1"]), (heat_high, ["2"]),
        (massif_low, ["1"]), (massif_high, ["2"]),
        (thunder, ["1"]), (heat_other_region, ["1"]),
    ])

    assert len(deduped) == 4, f"{[(a.hazard, a.region_label, a.dedup_id) for a, _ in deduped]}"
    by_key = {(a.hazard, a.region_label or a.dedup_id): (a, segs) for a, segs in deduped}
    heat_repr, heat_segs = by_key[("extreme_heat", "Haute-Corse")]
    assert heat_repr.level == 4
    assert sorted(heat_segs) == ["1", "2"]
    massif_repr, _ = by_key[("access_ban", "ESTEREL-MASSIF-ID")]
    assert massif_repr.level == 4
    assert massif_repr.label == "Zugang gesperrt — Massif de l'Esterel"
    assert ("thunderstorm", "Haute-Corse") in by_key
    assert ("extreme_heat", "Corse-du-Sud") in by_key


def test_zwei_verschiedene_orte_aehnlicher_name_kollabieren_nicht():
    """(aus :786) GIVEN zwei Alerts mit unterschiedlichem region_label fuer zwei
    Orte, WHEN ``dedupe_official_alerts`` auf die Mehr-Orte-Liste laeuft, THEN
    zwei Eintraege mit je eigener Stufe und loc_id."""
    from output.renderers.alert.official_alerts import dedupe_official_alerts

    ort_a = OfficialAlert(source="geosphere_warn", hazard="extreme_heat", level=2,
                          label="Hitze", region_label="Villach (Stadt)")
    ort_b = OfficialAlert(source="geosphere_warn", hazard="extreme_heat", level=4,
                          label="Hitze", region_label="Villach Land")
    assert ort_a.dedup_id is None and ort_b.dedup_id is None

    deduped = dedupe_official_alerts([(ort_a, ["loc-a"]), (ort_b, ["loc-b"])])

    assert len(deduped) == 2, f"{[(a.region_label, a.level) for a, _ in deduped]}"
    by_region = {a.region_label: (a, segs) for a, segs in deduped}
    assert (by_region["Villach (Stadt)"][0].level, by_region["Villach (Stadt)"][1]) == (2, ["loc-a"])
    assert (by_region["Villach Land"][0].level, by_region["Villach Land"][1]) == (4, ["loc-b"])
    key_a = f"official_alert:{by_region['Villach (Stadt)'][0].region_label}:extreme_heat"
    key_b = f"official_alert:{by_region['Villach Land'][0].region_label}:extreme_heat"
    assert key_a != key_b


# ---------------------------------------------------------------------------
# Zustaendigkeit der Feed-Quellen (entmischt aus :2251 und :2306)
# ---------------------------------------------------------------------------

def test_feed_quellen_decken_oesterreich_und_italien_ab_frankreich_nicht():
    """(entmischt aus :2251) GIVEN reale AT- und IT-Orte, WHEN ``covers()`` der
    Feed-Quellen AT und IT geprueft wird, THEN deckt mindestens eine jeden Ort
    ab; Fréjus (FR) deckt keine ab (#1397 S2b darf AT/IT nicht mit-treffen)."""
    from services.official_alerts.meteoalarm_feed import MeteoAlarmFeedSource

    at_source = MeteoAlarmFeedSource("AT")
    it_source = MeteoAlarmFeedSource("IT")
    for lat, lon, ort in (
        (46.7333, 12.2167, "Toblach"),
        (46.4983, 11.3548, "Bozen"),
        (47.2333, 11.8500, "Zillertal"),
        (47.2692, 11.4041, "Innsbruck"),
        (45.4642, 9.1900, "Mailand"),
    ):
        assert at_source.covers(lat, lon) or it_source.covers(lat, lon), (
            f"{ort} MUSS von mindestens einer Feed-Quelle (AT oder IT) abgedeckt sein"
        )

    frejus = (43.4330, 6.7370)
    assert at_source.covers(*frejus) is False
    assert it_source.covers(*frejus) is False


def test_nachbarlaender_ausserhalb_italiens_sind_nicht_it_abgedeckt():
    """(entmischt aus :2306) GIVEN Ljubljana und Zuerich liegen in der groben
    DPC-Bbox, aber in keiner italienischen Warnzone, WHEN ``covers()`` der
    IT-Feed-Quelle geprueft wird, THEN False; Bayern bleibt ueber den AT-Weg
    (``MeteoAlarmFeedSource("AT")``, INCA-Bbox) abgedeckt."""
    from services.official_alerts.meteoalarm_feed import MeteoAlarmFeedSource

    assert MeteoAlarmFeedSource("AT").covers(48.1351, 11.5820) is True, (
        "Bayern (Muenchen) bleibt ueber den AT-Weg (INCA-Bbox) abgedeckt"
    )
    it_source = MeteoAlarmFeedSource("IT")
    for lat, lon, ort in ((46.0569, 14.5058, "Ljubljana"), (47.3769, 8.5417, "Zuerich")):
        assert it_source.covers(lat, lon) is False, f"{ort} liegt ausserhalb Italiens"
