"""TDD RED — Issue #1460 Teil 1, Paket P1b: die Empfindlichkeitsstufe wirkt bei
Gefahrenstufen-Groessen ueber das erreichte NIVEAU, nicht ueber die Sprunggroesse.

SPEC: docs/specs/modules/rework_1460_t1_relevanzfilter.md v1.2 (AC-4 .. AC-19)

Zielsemantik (Ordinalwerte NONE=0 / LOW=1 / MED=2 / HIGH=3) — beide Richtungen melden,
symmetrisch je Stufe (PO-go 2026-08-03):

    sensibel   -> Verschaerfung: `neu > alt`               Entwarnung: `neu < alt`
    standard   -> Verschaerfung: `neu > alt AND neu==HIGH` Entwarnung: `neu < alt AND alt==HIGH`
    entspannt  -> Verschaerfung: `alt==NONE AND neu==HIGH` Entwarnung: `alt==HIGH AND neu==NONE`
    jede Stufe -> meldet NIE bei `neu == alt`

RED-Ursache (heute, vor der Implementierung):
- `_PRESET_TABLE` (alert_preset.py:42) traegt fuer THUNDER_LEVEL in allen drei
  Stufen denselben Delta-Wert 1, und `detect_changes()`
  (weather_change_detection.py:602) vergleicht fuer JEDES Feld strikt
  `abs(delta) > threshold`. Es meldet deshalb heute genau dann, wenn sich der
  Wert um ZWEI Stufen aendert (HIGH<->NONE) — und zwar in allen drei Stufen
  gleich. Jeder Wechsel um GENAU eine Stufe bleibt stumm, aufwaerts wie
  abwaerts: rot sind AC-4, AC-5, AC-7 (aufwaerts) und AC-11, AC-12, AC-13
  (abwaerts) sowie die Gesamttabelle in AC-19.

Keine Mocks: echte `SegmentWeatherSummary`-Fixturen mit direkt konstruierten
`ThunderLevel`-Werten (AC-13 — `_parse_thunder_level()` liefert MED nie, deshalb
darf kein Provider-Pfad beteiligt sein), echte `expand_per_metric_levels()`- und
`WeatherChangeDetectionService`-Aufrufe, kein Netz, kein Versand.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.models import (
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripSegment,
)

LAT, LON = 47.0, 11.0

NONE, MED, HIGH = ThunderLevel.NONE, ThunderLevel.MED, ThunderLevel.HIGH

ALL_LEVELS = ("entspannt", "standard", "sensibel")


def _segment(segment_id: str = "seg-1") -> TripSegment:
    now = datetime.now(timezone.utc)
    return TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=LAT, lon=LON, elevation_m=1000, distance_from_start_km=0.0),
        end_point=GPXPoint(lat=LAT + 0.1, lon=LON + 0.1, elevation_m=1500,
                           distance_from_start_km=8.0),
        start_time=now - timedelta(hours=1),
        end_time=now + timedelta(hours=3),
        duration_hours=4.0,
        distance_km=8.0,
        ascent_m=500,
        descent_m=0,
    )


def _data(**summary_kwargs) -> SegmentWeatherData:
    """Aufgezeichnete Fixture (AC-13): der Gewitter-Wert wird DIREKT gesetzt,
    nie ueber einen Provider-Parser erzeugt."""
    return SegmentWeatherData(
        segment=_segment(),
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=1.0),
            data=[],
        ),
        aggregated=SegmentWeatherSummary(**summary_kwargs),
        fetched_at=datetime.now(timezone.utc),
        provider="openmeteo",
    )


def _thunder_changes(old: ThunderLevel, new: ThunderLevel, level: str) -> list:
    """Der echte Auswertungsweg des Alarm-Pfads: Empfindlichkeitsstufe ->
    Regeln -> Detektor -> `detect_changes(include_absolute=False)`."""
    from services.alert_preset import expand_per_metric_levels
    from services.weather_change_detection import WeatherChangeDetectionService

    rules = expand_per_metric_levels({"thunder_level": level})
    detector = WeatherChangeDetectionService.from_alert_rules(rules)
    changes = detector.detect_changes(
        _data(thunder_level_max=old),
        _data(thunder_level_max=new),
        include_absolute=False,
    )
    return [c for c in changes if c.metric == "thunder_level_max"]


# ───────────────────────────── AC-4 / AC-5 — sensibel ────────────────────────

def test_ac4_sensibel_meldet_anstieg_auf_die_mittelstufe():
    """AC-4.

    GIVEN Empfindlichkeit "sensibel" fuer Gewitter und ein Briefing-Stand ohne
          Gewitter (ThunderLevel.NONE)
    WHEN  die aktuelle Vorhersage auf die Mittelstufe (ThunderLevel.MED) steigt
    THEN  wird eine Meldung ausgeloest.
    """
    changes = _thunder_changes(NONE, MED, "sensibel")
    assert len(changes) == 1, (
        "sensibel muss bereits den Anstieg auf die Mittelstufe melden, "
        f"erhalten: {changes!r}"
    )
    assert changes[0].direction == "increase"


def test_ac5_sensibel_meldet_anstieg_von_mittel_auf_hoechststufe():
    """AC-5.

    GIVEN Empfindlichkeit "sensibel", Briefing-Stand ThunderLevel.MED
    WHEN  die Vorhersage auf ThunderLevel.HIGH steigt
    THEN  wird eine Meldung ausgeloest.
    """
    changes = _thunder_changes(MED, HIGH, "sensibel")
    assert len(changes) == 1, (
        "sensibel muss den Anstieg von der Mittel- auf die Hoechststufe melden, "
        f"erhalten: {changes!r}"
    )


# ─────────────────────── AC-6 / AC-7 / AC-8 — standard ───────────────────────

def test_ac6_standard_meldet_die_mittelstufe_nicht():
    """AC-6.

    GIVEN Empfindlichkeit "standard", Briefing-Stand ThunderLevel.NONE
    WHEN  die Vorhersage auf die Mittelstufe (ThunderLevel.MED) steigt
    THEN  wird KEINE Meldung ausgeloest (die Mittelstufe ist nicht die hoechste).
    """
    changes = _thunder_changes(NONE, MED, "standard")
    assert changes == [], (
        "standard darf die blosse Mittelstufe nicht melden, erhalten: "
        f"{changes!r}"
    )


def test_ac7_standard_meldet_das_erreichen_der_hoechststufe():
    """AC-7.

    GIVEN Empfindlichkeit "standard", Briefing-Stand ThunderLevel.MED
    WHEN  die Vorhersage auf ThunderLevel.HIGH steigt
    THEN  WIRD eine Meldung ausgeloest (die hoechste Stufe wird erreicht).
    """
    changes = _thunder_changes(MED, HIGH, "standard")
    assert len(changes) == 1, (
        "standard muss melden, sobald die hoechste Stufe erreicht wird, "
        f"erhalten: {changes!r}"
    )


def test_ac8_standard_meldet_den_vollen_sprung_auf_die_hoechststufe():
    """AC-8.

    GIVEN Empfindlichkeit "standard", Briefing-Stand ThunderLevel.NONE
    WHEN  die Vorhersage direkt auf ThunderLevel.HIGH springt
    THEN  WIRD eine Meldung ausgeloest.
    """
    changes = _thunder_changes(NONE, HIGH, "standard")
    assert len(changes) == 1, (
        f"standard muss den vollen Sprung melden, erhalten: {changes!r}"
    )


# ───────────────────────── AC-9 / AC-10 — entspannt ──────────────────────────

def test_ac9_entspannt_meldet_den_teilsprung_nicht():
    """AC-9.

    GIVEN Empfindlichkeit "entspannt", Briefing-Stand ThunderLevel.MED
    WHEN  die Vorhersage auf ThunderLevel.HIGH steigt
    THEN  wird KEINE Meldung ausgeloest (kein voller Sprung von "kein Gewitter").
    """
    changes = _thunder_changes(MED, HIGH, "entspannt")
    assert changes == [], (
        "entspannt darf nur den vollen Sprung von 'kein Gewitter' melden, "
        f"erhalten: {changes!r}"
    )


def test_ac10_entspannt_meldet_den_vollen_sprung():
    """AC-10.

    GIVEN Empfindlichkeit "entspannt", Briefing-Stand ThunderLevel.NONE
    WHEN  die Vorhersage direkt auf ThunderLevel.HIGH springt
    THEN  WIRD eine Meldung ausgeloest.
    """
    changes = _thunder_changes(NONE, HIGH, "entspannt")
    assert len(changes) == 1, (
        f"entspannt muss den vollen Sprung melden, erhalten: {changes!r}"
    )


# ───────────────────── AC-11 / AC-12 — Entwarnung, sensibel ─────────────────

def test_ac11_sensibel_meldet_die_senkung_von_der_hoechststufe():
    """AC-11.

    GIVEN Empfindlichkeit "sensibel", Briefing-Stand ThunderLevel.HIGH
    WHEN  die Vorhersage auf ThunderLevel.MED sinkt
    THEN  WIRD eine Meldung ausgeloest — die Entwarnung wird symmetrisch zur
          Verschaerfung gemeldet.
    """
    changes = _thunder_changes(HIGH, MED, "sensibel")
    assert len(changes) == 1, (
        "sensibel muss auch die Senkung von der Hoechststufe melden, "
        f"erhalten: {changes!r}"
    )
    assert changes[0].direction == "decrease", (
        f"Die Entwarnung muss als Rueckgang ausgewiesen sein: {changes[0]!r}"
    )


def test_ac12_sensibel_meldet_die_senkung_von_der_mittelstufe():
    """AC-12.

    GIVEN Empfindlichkeit "sensibel", Briefing-Stand ThunderLevel.MED
    WHEN  die Vorhersage auf ThunderLevel.NONE sinkt
    THEN  WIRD eine Meldung ausgeloest.
    """
    changes = _thunder_changes(MED, NONE, "sensibel")
    assert len(changes) == 1, (
        "sensibel muss auch die Senkung von der Mittelstufe melden, "
        f"erhalten: {changes!r}"
    )


# ───────────────── AC-13 / AC-14 / AC-15 — Entwarnung, standard ──────────────

def test_ac13_standard_meldet_das_verlassen_der_hoechststufe():
    """AC-13.

    GIVEN Empfindlichkeit "standard", Briefing-Stand ThunderLevel.HIGH
    WHEN  die Vorhersage auf ThunderLevel.MED sinkt
    THEN  WIRD eine Meldung ausgeloest — die hoechste Stufe wird verlassen
          (Spiegelbild von AC-7).
    """
    changes = _thunder_changes(HIGH, MED, "standard")
    assert len(changes) == 1, (
        "standard muss das Verlassen der Hoechststufe melden, "
        f"erhalten: {changes!r}"
    )


def test_ac14_standard_meldet_den_vollen_rueckgang():
    """AC-14.

    GIVEN Empfindlichkeit "standard", Briefing-Stand ThunderLevel.HIGH
    WHEN  die Vorhersage direkt auf ThunderLevel.NONE zurueckgeht
    THEN  WIRD eine Meldung ausgeloest.
    """
    changes = _thunder_changes(HIGH, NONE, "standard")
    assert len(changes) == 1, (
        f"standard muss den vollen Rueckgang melden, erhalten: {changes!r}"
    )


def test_ac15_standard_meldet_das_verlassen_der_mittelstufe_nicht():
    """AC-15.

    GIVEN Empfindlichkeit "standard", Briefing-Stand ThunderLevel.MED
    WHEN  die Vorhersage auf ThunderLevel.NONE sinkt
    THEN  wird KEINE Meldung ausgeloest — die hoechste Stufe war nicht
          beteiligt (Spiegelbild von AC-6).
    """
    changes = _thunder_changes(MED, NONE, "standard")
    assert changes == [], (
        "standard darf das blosse Verlassen der Mittelstufe nicht melden, "
        f"erhalten: {changes!r}"
    )


# ──────────────────── AC-16 / AC-17 — Entwarnung, entspannt ──────────────────

def test_ac16_entspannt_meldet_den_vollen_rueckgang():
    """AC-16.

    GIVEN Empfindlichkeit "entspannt", Briefing-Stand ThunderLevel.HIGH
    WHEN  die Vorhersage direkt auf ThunderLevel.NONE zurueckgeht
    THEN  WIRD eine Meldung ausgeloest (Spiegelbild von AC-10).
    """
    changes = _thunder_changes(HIGH, NONE, "entspannt")
    assert len(changes) == 1, (
        f"entspannt muss den vollen Rueckgang melden, erhalten: {changes!r}"
    )


def test_ac17_entspannt_meldet_den_teilrueckgang_nicht():
    """AC-17.

    GIVEN Empfindlichkeit "entspannt", Briefing-Stand ThunderLevel.HIGH
    WHEN  die Vorhersage auf ThunderLevel.MED sinkt
    THEN  wird KEINE Meldung ausgeloest — kein voller Rueckgang auf "kein
          Gewitter" (Spiegelbild von AC-9).
    """
    changes = _thunder_changes(HIGH, MED, "entspannt")
    assert changes == [], (
        "entspannt darf nur den vollen Rueckgang melden, "
        f"erhalten: {changes!r}"
    )


@pytest.mark.parametrize("level", ALL_LEVELS)
def test_ac11_bis_ac17_unveraenderter_wert_meldet_nie(level: str):
    """AC-11 .. AC-17 (gemeinsame Randbedingung).

    GIVEN irgendeine der drei Empfindlichkeitsstufen
    WHEN  sich die Gewitterneigung gegenueber dem Briefing-Stand NICHT
          veraendert
    THEN  wird bei KEINER Stufe eine Meldung ausgeloest — nur ein
          Stufenwechsel ist ein Ereignis, kein Bestandswert.
    """
    for level_value in (NONE, MED, HIGH):
        changes = _thunder_changes(level_value, level_value, level)
        assert changes == [], (
            f"Stufe {level!r} darf den unveraenderten Wert {level_value.name} "
            f"nicht melden, erhalten: {changes!r}"
        )


# ──────────────── AC-18 — Regressionsschutz fuer stetige Groessen ────────────

def test_ac18_stetige_groesse_meldet_bei_genau_der_schwelle_nicht():
    """AC-18 (Regressionsschutz).

    GIVEN die stetige Groesse Boeen mit Empfindlichkeit "standard" (Schwelle 20)
    WHEN  sich der Wert seit dem Briefing-Stand um exakt 20 km/h aendert
    THEN  bleibt das heutige Verhalten unveraendert: striktes `>` — KEINE
          Meldung bei genau 20 km/h.
    """
    from services.alert_preset import expand_per_metric_levels
    from services.weather_change_detection import WeatherChangeDetectionService

    detector = WeatherChangeDetectionService.from_alert_rules(
        expand_per_metric_levels({"wind_gust": "standard"})
    )
    changes = detector.detect_changes(
        _data(gust_max_kmh=30.0), _data(gust_max_kmh=50.0), include_absolute=False,
    )
    assert changes == [], (
        "Genau die Schwelle darf bei stetigen Groessen weiterhin nicht melden "
        f"(striktes >), erhalten: {changes!r}"
    )


def test_ac18b_stetige_groesse_meldet_knapp_ueber_der_schwelle():
    """AC-18 (Grenzfall-Nachweis).

    GIVEN dieselbe Boeen-Konfiguration ("standard", Schwelle 20)
    WHEN  sich der Wert um 20.01 km/h aendert
    THEN  WIRD gemeldet — die generische Delta-Logik fuer stetige Groessen
          bleibt von der Niveau-Semantik unangetastet.
    """
    from services.alert_preset import expand_per_metric_levels
    from services.weather_change_detection import WeatherChangeDetectionService

    detector = WeatherChangeDetectionService.from_alert_rules(
        expand_per_metric_levels({"wind_gust": "standard"})
    )
    changes = detector.detect_changes(
        _data(gust_max_kmh=30.0), _data(gust_max_kmh=50.01), include_absolute=False,
    )
    assert len(changes) == 1, (
        f"Knapp ueber der Schwelle muss weiterhin gemeldet werden, erhalten: {changes!r}"
    )
    assert changes[0].metric == "gust_max_kmh"


def test_ac18c_gewitter_semantik_beeinflusst_die_boeen_schwelle_nicht():
    """AC-18 (Nicht-Ansteckung).

    GIVEN eine Tour-Konfiguration mit Gewitter UND Boeen auf "standard"
    WHEN  die Boeen um exakt 20 km/h steigen und das Gewitter unveraendert
          bleibt
    THEN  bleibt die Boeen-Auswertung stumm — die Niveau-Semantik fuer Gewitter
          darf die Schwelle stetiger Groessen nicht veraendern.
    """
    from services.alert_preset import expand_per_metric_levels
    from services.weather_change_detection import WeatherChangeDetectionService

    detector = WeatherChangeDetectionService.from_alert_rules(
        expand_per_metric_levels({"wind_gust": "standard", "thunder_level": "standard"})
    )
    changes = detector.detect_changes(
        _data(gust_max_kmh=30.0, thunder_level_max=NONE),
        _data(gust_max_kmh=50.0, thunder_level_max=NONE),
        include_absolute=False,
    )
    assert changes == [], (
        f"Weder Boeen noch Gewitter duerfen hier melden, erhalten: {changes!r}"
    )


# ─────────────── AC-19 — Mittelstufe kommt aus der Fixture, nie live ─────────

def test_ac19_mittelstufe_stammt_aus_der_fixture_nicht_vom_provider():
    """AC-19.

    GIVEN eine aufgezeichnete Fixture, die ThunderLevel.MED direkt als Wert
          traegt (der Live-Parser `_parse_thunder_level()` liefert MED nie)
    WHEN  AC-4 bis AC-17 gegen diese Fixture laufen
    THEN  gilt exakt die Niveau-Tabelle — in BEIDEN Richtungen und unabhaengig
          davon, ob je eine Quelle die Mittelstufe liefert.
    """
    fixture = _data(thunder_level_max=MED)
    assert fixture.aggregated.thunder_level_max is MED, (
        "Vorbedingung: die Fixture traegt die Mittelstufe direkt"
    )
    from providers.openmeteo import OpenMeteoProvider

    parse = OpenMeteoProvider()._parse_thunder_level
    live_values = {parse(code) for code in range(0, 100)}
    assert MED not in live_values, (
        "Vorbedingung von AC-19 verletzt: der Live-Parser liefert die "
        "Mittelstufe inzwischen doch — dann muss #1419 S3 die Niveau-Tabelle "
        "mitgepruefte Quelle sein"
    )

    # Die vollstaendige Niveau-Tabelle, beide Richtungen, je Stufe.
    matrix = {
        # aufwaerts (AC-4 .. AC-10)
        ("sensibel", NONE, MED): 1,
        ("sensibel", MED, HIGH): 1,
        ("standard", NONE, MED): 0,
        ("standard", MED, HIGH): 1,
        ("standard", NONE, HIGH): 1,
        ("entspannt", MED, HIGH): 0,
        ("entspannt", NONE, HIGH): 1,
        # abwaerts (AC-11 .. AC-17)
        ("sensibel", HIGH, MED): 1,
        ("sensibel", MED, NONE): 1,
        ("standard", HIGH, MED): 1,
        ("standard", HIGH, NONE): 1,
        ("standard", MED, NONE): 0,
        ("entspannt", HIGH, NONE): 1,
        ("entspannt", HIGH, MED): 0,
    }
    abweichungen = []
    for (level, old, new), expected in matrix.items():
        changes = _thunder_changes(old, new, level)
        if len(changes) != expected:
            abweichungen.append(
                f"{level} {old.name}->{new.name}: erwartet {expected}, erhalten {len(changes)}"
            )
    assert not abweichungen, (
        "Die Niveau-Tabelle wird nicht eingehalten:\n  " + "\n  ".join(abweichungen)
    )
