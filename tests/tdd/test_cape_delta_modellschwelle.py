"""TDD RED — #1592 Scheibe C3: CAPE-Änderungsalarme rechnen die bestehende
Empfindlichkeitsleiter (1200/600/200) in die jeweilige Modellwelt um.

Spec: docs/specs/modules/fix_1592_c3_cape_delta_alarme.md
Context: docs/context/fix-1592-c3-cape-delta-alarme.md

Regel:
    wirksame Δ-Schwelle = nominale Preset-Zahl × cape_threshold_jkg(modell, gebiet) / 1000

Andockpunkt (noch nicht implementiert): `WeatherChangeDetectionService.detect_changes()`
(`src/services/weather_change_detection.py:598-658`), Sonderpfad je Metrik analog
`_ordinal_levels` (#1460).

Mock-frei: alle Aufrufe laufen durch die echte `WeatherChangeDetectionService`
(bzw. für AC-7 durch die echte `DeviationAlertEngine`) mit echten DTOs
(`SegmentWeatherData`/`SegmentWeatherSummary`/`PointWeatherData`) — kein
`Mock()`/`patch()`/`MagicMock`.

Gemessene Fakten (nicht neu hergeleitet, s. Team-Lead-Briefing):
    cape_threshold_jkg('meteofrance_arome', 'FR') == 300.0  →  Faktor 0.30
    thunder_region_for(42.22, 9.05) == 'FR'                 (Korsika)
    Preset "standard" für CAPE (Δ) == 600  →  wirksame Schwelle 600*0.30 == 180.0
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.model_registry import cape_threshold_jkg
from app.models import (
    ChangeSeverity,
    GPXPoint,
    SegmentWeatherData,
    SegmentWeatherSummary,
    TripSegment,
)
from providers.thunder_routing import thunder_region_for
from services.weather_change_detection import WeatherChangeDetectionService

# ─────────────────────────────────────────────────────────────────────────
# Sanity-Checks der in dieser Datei benutzten geografischen/Eich-Annahmen —
# laufen bei jedem Testlauf mit, damit ein künftiger Registry-/Routing-Umbau
# diese Testdatei nicht lautlos auf falschen Annahmen sitzen lässt.
# ─────────────────────────────────────────────────────────────────────────

CORSICA_LAT, CORSICA_LON = 42.22, 9.05
assert thunder_region_for(CORSICA_LAT, CORSICA_LON) == "FR", (
    "Testannahme verletzt: Korsika-Koordinaten müssen ins Gebiet FR routen "
    "(sonst prüfen AC-1/2/3/5/6 den falschen Fall)."
)
assert cape_threshold_jkg("meteofrance_arome", "FR") == 300.0, (
    "Testannahme verletzt: die B0-Eichung für meteofrance_arome×FR hat sich "
    "geändert (erwartet 300.0) — die hartcodierten Erwartungswerte 180.0 in "
    "AC-1/2/5/6 dieser Datei sind davon abgeleitet und müssen nachgezogen werden."
)

# EU_REST-Koordinaten, die NICHT in FR (lat 41.3-51.1 / lon -5.2-9.7) und
# NICHT in DE_ALPEN (lat 43.17-58.09 / lon -3.95-20.35) fallen — Ostsee-Raum.
EU_REST_LAT, EU_REST_LON = 60.0, 25.0
assert thunder_region_for(EU_REST_LAT, EU_REST_LON) == "EU_REST"
# icon_d2×EU_REST ist nachweislich NICHT in der Eichtabelle enthalten (nur
# icon_d2×FR und icon_d2×DE_ALPEN sind geeicht, s. model_registry.py:120-132)
# — die Kombination steht daher für AC-4 ("Kein Gebiet, keine Aussage").
assert cape_threshold_jkg("icon_d2", "EU_REST") is None, (
    "Testannahme verletzt: icon_d2×EU_REST müsste unbelegt sein (AC-4 braucht "
    "genau eine nachweislich fehlende Kombination)."
)


# ─────────────────────────────────────────────────────────────────────────
# Helfer (mock-frei) — bauen echte SegmentWeatherData-Paare.
# ─────────────────────────────────────────────────────────────────────────

def _segment(lat: float, lon: float) -> TripSegment:
    now = datetime(2026, 8, 8, 10, 0, tzinfo=timezone.utc)
    return TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=lat, lon=lon, elevation_m=800, distance_from_start_km=0.0),
        end_point=GPXPoint(lat=lat + 0.05, lon=lon + 0.05, elevation_m=1200, distance_from_start_km=5.0),
        start_time=now,
        end_time=now,
        duration_hours=2.0,
        distance_km=5.0,
        ascent_m=400,
        descent_m=0,
    )


def _cape_pair(
    *, old_cape: float, new_cape: float, cape_model_id, lat: float, lon: float
) -> tuple[SegmentWeatherData, SegmentWeatherData]:
    """Baut ein (old_data, new_data)-Paar mit ausschließlich CAPE + Herkunft
    belegt — alle anderen Felder bleiben None (werden vom Detektor übersprungen,
    s. `detect_changes()`: `old_value is None or new_value is None` → `continue`)."""
    segment = _segment(lat, lon)
    fetched_at = datetime(2026, 8, 8, 6, 0, tzinfo=timezone.utc)
    old_data = SegmentWeatherData(
        segment=segment,
        timeseries=None,
        aggregated=SegmentWeatherSummary(cape_max_jkg=old_cape, cape_model_id=cape_model_id),
        fetched_at=fetched_at,
        provider="test-scripted",
    )
    new_data = SegmentWeatherData(
        segment=segment,
        timeseries=None,
        aggregated=SegmentWeatherSummary(cape_max_jkg=new_cape, cape_model_id=cape_model_id),
        fetched_at=fetched_at,
        provider="test-scripted",
    )
    return old_data, new_data


def _cape_changes(changes) -> list:
    return [c for c in changes if c.metric == "cape_max_jkg"]


# ─────────────────────────────────────────────────────────────────────────
# AC-1: Der Kernfall — CAPE-Alarme erreichen Frankreich.
# ─────────────────────────────────────────────────────────────────────────

def test_ac1_arome_fr_standard_250_jump_triggers_alarm():
    """
    GIVEN Korsika (FR), Herkunft meteofrance_arome, Stufe "standard"
          (nominale Δ-Schwelle 600, umgerechnet 600*0.30 = 180)
    WHEN  CAPE-Tagesmaximum springt um 250 J/kg (500 -> 750)
    THEN  entsteht ein WeatherChange für cape_max_jkg.

    RED heute: der Detektor kennt noch keine Modell-/Gebiets-Umrechnung und
    vergleicht stur gegen die nominale 600 -> 250 < 600 -> KEIN Ereignis.
    """
    old_data, new_data = _cape_pair(
        old_cape=500.0, new_cape=750.0,
        cape_model_id="meteofrance_arome", lat=CORSICA_LAT, lon=CORSICA_LON,
    )
    service = WeatherChangeDetectionService(thresholds={"cape_max_jkg": 600.0})
    changes = service.detect_changes(old_data, new_data)

    cape_changes = _cape_changes(changes)
    assert cape_changes, (
        "AC-1: erwartetes CAPE-Ereignis fehlt. Heute vergleicht der Detektor "
        "gegen die nominale Schwelle 600 (250 < 600 -> kein Alarm); nach C3 "
        "muss er gegen die umgerechnete Schwelle 180 vergleichen (250 > 180 "
        "-> Alarm)."
    )


# ─────────────────────────────────────────────────────────────────────────
# AC-2: Gegenprobe — die Schwelle verschwindet nicht (darf JETZT schon grün
# sein: 150 < 600 (nominal, heute) UND 150 < 180 (umgerechnet, nach C3) —
# in BEIDEN Welten kein Ereignis).
# ─────────────────────────────────────────────────────────────────────────

def test_ac2_arome_fr_standard_150_jump_stays_silent():
    """
    GIVEN dieselbe Etappe/Stufe wie AC-1
    WHEN  CAPE-Maximum springt nur um 150 J/kg (500 -> 650)
    THEN  entsteht KEIN CAPE-Ereignis (150 < 180).

    Dieser Test ist die Gegenprobe zu AC-1 und darf schon HEUTE grün sein
    (150 liegt sowohl unter der nominalen 600 als auch unter der künftigen
    umgerechneten 180) — ohne ihn wäre AC-1 auch von einer Implementierung
    erfüllt, die immer auslöst.
    """
    old_data, new_data = _cape_pair(
        old_cape=500.0, new_cape=650.0,
        cape_model_id="meteofrance_arome", lat=CORSICA_LAT, lon=CORSICA_LON,
    )
    service = WeatherChangeDetectionService(thresholds={"cape_max_jkg": 600.0})
    changes = service.detect_changes(old_data, new_data)

    assert _cape_changes(changes) == []


# ─────────────────────────────────────────────────────────────────────────
# AC-3: Unbekannte Herkunft schweigt, statt zu behaupten.
# ─────────────────────────────────────────────────────────────────────────

def test_ac3_unknown_model_id_abstains_even_on_huge_jump():
    """
    GIVEN Etappe mit cape_model_id=None (unbekanntes Modell)
    WHEN  CAPE-Maximum springt um 5000 J/kg
    THEN  entsteht KEIN CAPE-Ereignis ("keine Aussage", nicht "unauffällig").

    RED heute: der Detektor kennt cape_model_id noch gar nicht und feuert
    stur bei abs(delta) > 600 -> 5000 > 600 -> Ereignis entsteht (fälschlich).
    """
    old_data, new_data = _cape_pair(
        old_cape=100.0, new_cape=5100.0,
        cape_model_id=None, lat=CORSICA_LAT, lon=CORSICA_LON,
    )
    service = WeatherChangeDetectionService(thresholds={"cape_max_jkg": 600.0})
    changes = service.detect_changes(old_data, new_data)

    assert _cape_changes(changes) == [], (
        "AC-3: unbekannte Modell-Herkunft (cape_model_id=None) darf auch bei "
        "einem riesigen Sprung KEIN CAPE-Ereignis erzeugen — Abstain, nicht "
        "Alarm."
    )


def test_ac3_gegenprobe_known_model_id_fires_on_same_jump():
    """Gegenprobe zu AC-3: dieselbe Konstellation, aber mit gesetzter
    Herkunft, liefert sehr wohl ein Ereignis — das Abstain-Verhalten aus
    AC-3 hängt wirklich an `cape_model_id`, nicht an sonst etwas."""
    old_data, new_data = _cape_pair(
        old_cape=100.0, new_cape=5100.0,
        cape_model_id="meteofrance_arome", lat=CORSICA_LAT, lon=CORSICA_LON,
    )
    service = WeatherChangeDetectionService(thresholds={"cape_max_jkg": 600.0})
    changes = service.detect_changes(old_data, new_data)

    assert _cape_changes(changes), (
        "Gegenprobe zu AC-3: mit bekannter Herkunft muss derselbe Sprung ein "
        "CAPE-Ereignis erzeugen (heute schon der Fall, da 5000 > 600 ohnehin "
        "auslöst — bleibt nach C3 mit umgerechneter Schwelle 180 ebenso "
        "wahr)."
    )


# ─────────────────────────────────────────────────────────────────────────
# AC-4: Kein Gebiet / keine Eichung, keine Aussage.
# ─────────────────────────────────────────────────────────────────────────

def test_ac4_known_model_but_uncalibrated_region_abstains():
    """
    GIVEN Etappe mit bekannter Herkunft (icon_d2), aber Koordinaten im
          Gebiet EU_REST — für icon_d2×EU_REST existiert KEIN Eichwert
          (nur icon_d2×FR und icon_d2×DE_ALPEN sind in CAPE_THRESHOLDS_JKG,
          s. model_registry.py:120-132)
    WHEN  CAPE-Maximum springt um 5000 J/kg
    THEN  entsteht KEIN CAPE-Ereignis.

    RED heute: der Detektor prüft die Kombination noch nicht gegen die
    Eichtabelle und feuert stur bei abs(delta) > 600.
    """
    old_data, new_data = _cape_pair(
        old_cape=100.0, new_cape=5100.0,
        cape_model_id="icon_d2", lat=EU_REST_LAT, lon=EU_REST_LON,
    )
    service = WeatherChangeDetectionService(thresholds={"cape_max_jkg": 600.0})
    changes = service.detect_changes(old_data, new_data)

    assert _cape_changes(changes) == [], (
        "AC-4: icon_d2xEU_REST hat keinen Eichwert -> auch ein riesiger "
        "Sprung darf KEIN CAPE-Ereignis erzeugen."
    )


# ─────────────────────────────────────────────────────────────────────────
# AC-5: Der Alarmtext nennt die Schwelle, die wirklich galt — Prüfort ist
# der RENDERER (over_thr()), nicht nur das WeatherChange-Objekt.
# ─────────────────────────────────────────────────────────────────────────

def test_ac5_event_carries_effective_threshold_and_renderer_sees_over_thr():
    """
    GIVEN der Alarm aus AC-1 (250-J/kg-Sprung, meteofrance_arome, FR)
    WHEN  die Alarmzeile über den echten Konverter `to_alert_message()`
          gerendert wird
    THEN  WeatherChange.threshold == 180.0 UND das daraus gebaute
          AlertEvent liefert `over_thr(event) is True` — nicht 600 und
          nicht "unter Schwelle".

    Baut das AlertEvent über den echten Projektions-Weg
    (`output.renderers.alert.project.to_alert_message`), nicht von Hand
    zusammengestückelt.

    RED heute: AC-1 liefert noch KEIN Ereignis (250 < nominale 600) — diese
    Kette bricht deshalb bereits an der ersten Assertion.
    """
    from output.renderers.alert.model import over_thr
    from output.renderers.alert.project import to_alert_message

    old_data, new_data = _cape_pair(
        old_cape=500.0, new_cape=750.0,
        cape_model_id="meteofrance_arome", lat=CORSICA_LAT, lon=CORSICA_LON,
    )
    service = WeatherChangeDetectionService(thresholds={"cape_max_jkg": 600.0})
    changes = service.detect_changes(old_data, new_data)
    cape_changes = _cape_changes(changes)
    assert cape_changes, "AC-5 setzt das AC-1-Ereignis voraus — s. AC-1 für die Begründung."

    change = cape_changes[0]
    assert change.threshold == 180.0, (
        f"AC-5: WeatherChange.threshold muss die umgerechnete Schwelle 180.0 "
        f"tragen, nicht die nominale 600 — war {change.threshold!r}."
    )

    message = to_alert_message(
        [change], [new_data], "GR20-Test", tz=timezone.utc, stand_at="12:00",
    )
    assert len(message.events) == 1
    event = message.events[0]
    assert over_thr(event) is True, (
        "AC-5: der Renderer muss das Ereignis als 'über Schwelle' einstufen "
        "(over_thr() aus output.renderers.alert.model) — sonst stünde im "
        "Alarmtext 'unter Schwelle', obwohl er ausgelöst hat."
    )


# ─────────────────────────────────────────────────────────────────────────
# AC-6: Die Dringlichkeit folgt der umgerechneten Schwelle.
# ─────────────────────────────────────────────────────────────────────────

def test_ac6_400_jump_is_major_under_converted_threshold():
    """
    GIVEN Etappe aus AC-1 (meteofrance_arome, FR, Stufe "standard")
    WHEN  CAPE-Maximum springt um 400 J/kg
    THEN  ChangeSeverity.MAJOR (400 / 180 = 2.22 >= 2.0), während heute
          ÜBERHAUPT KEIN Alarm entstünde (400 < nominale 600).

    RED heute: kein Ereignis (400 < 600) -> die Severity-Prüfung kann gar
    nicht erst stattfinden.
    """
    old_data, new_data = _cape_pair(
        old_cape=500.0, new_cape=900.0,
        cape_model_id="meteofrance_arome", lat=CORSICA_LAT, lon=CORSICA_LON,
    )
    service = WeatherChangeDetectionService(thresholds={"cape_max_jkg": 600.0})
    changes = service.detect_changes(old_data, new_data)
    cape_changes = _cape_changes(changes)
    assert cape_changes, (
        "AC-6 setzt voraus, dass ein CAPE-Ereignis entsteht (heute: 400 < "
        "600 -> kein Alarm; nach C3: 400 > 180 -> Alarm mit MAJOR)."
    )
    assert cape_changes[0].severity is ChangeSeverity.MAJOR, (
        f"AC-6: Severity muss MAJOR sein (400/180=2.22>=2.0) — war "
        f"{cape_changes[0].severity!r}."
    )


# ─────────────────────────────────────────────────────────────────────────
# AC-7: Der Ortsvergleich erbt die Wirkung, ohne eigenen Code — geprüft über
# den echten Compare-Auswertungskern `DeviationAlertEngine`, NICHT über eine
# Trip-Attrappe. `DeviationAlertEngine` ist location-generisch (kennt kein
# `Trip`) und ist exakt der Kern, den `CompareAlertService` UND
# `TripAlertService` gemeinsam nutzen (services/deviation_alert_engine.py) —
# das ist die tiefste Ebene, die noch echter (geteilter) Compare-Code ist,
# ohne dass ein voller `CompareAlertService`-Lauf Netz/Dateisystem-Fixtures
# braucht.
# ─────────────────────────────────────────────────────────────────────────

def test_ac7_compare_path_via_deviation_alert_engine_inherits_conversion():
    """
    GIVEN ein Ortsvergleichs-Punkt in Frankreich, Herkunft meteofrance_arome,
          Stufe "standard" (per `metric_alert_levels={"cape": "standard"}`,
          exakt der Weg, über den `CompareAlertService` seine Regeln baut,
          s. `expand_per_metric_levels()` in `services/alert_preset.py`)
    WHEN  CAPE-Maximum dieses Ortes um 250 J/kg steigt
    THEN  entsteht eine Abweichungsmeldung (EvaluationResult.triggered=True)
          mit einem cape_max_jkg-Change bei Schwelle 180.0.

    RED heute: die Engine baut die Regel mit der nominalen Schwelle 600 ->
    250 < 600 -> `triggered=False` ("no_significant_changes").
    """
    from services.deviation_alert_engine import DeviationAlertEngine
    from services.point_weather import AlertEvaluationConfig, PointWeatherData

    fetched_at = datetime(2026, 8, 8, 6, 0, tzinfo=timezone.utc)
    old_point = PointWeatherData(
        id="corse-test", name="Korsika-Testort", lat=CORSICA_LAT, lon=CORSICA_LON,
        timeseries=None,
        aggregated=SegmentWeatherSummary(cape_max_jkg=500.0, cape_model_id="meteofrance_arome"),
        fetched_at=fetched_at, provider="test-scripted",
    )
    fresh_point = PointWeatherData(
        id="corse-test", name="Korsika-Testort", lat=CORSICA_LAT, lon=CORSICA_LON,
        timeseries=None,
        aggregated=SegmentWeatherSummary(cape_max_jkg=750.0, cape_model_id="meteofrance_arome"),
        fetched_at=fetched_at, provider="test-scripted",
    )
    config = AlertEvaluationConfig(
        cooldown_minutes=0, quiet_from=None, quiet_to=None,
        metric_alert_levels={"cape": "standard"}, channels={"email"},
    )
    engine = DeviationAlertEngine()
    result = engine.evaluate(
        [old_point], [fresh_point], config, alert_state={},
        now=datetime(2026, 8, 8, 10, 0, tzinfo=timezone.utc),
    )

    assert result.triggered is True, (
        f"AC-7: der Ortsvergleichs-Auswertungskern muss bei 250 J/kg Sprung "
        f"gegen FR/meteofrance_arome auslösen (umgerechnete Schwelle 180) — "
        f"war triggered={result.triggered!r} suppressed_reason="
        f"{result.suppressed_reason!r}."
    )
    cape_changes = _cape_changes(result.changes)
    assert cape_changes, "AC-7: erwartetes cape_max_jkg-Ereignis fehlt im Compare-Pfad."
    assert cape_changes[0].threshold == 180.0


# ─────────────────────────────────────────────────────────────────────────
# AC-8: Regressionsschutz — vier NICHT betroffene Metriken bleiben
# byte-identisch (Auslösung, Schwelle, Severity) zu den heutigen
# `_PRESET_TABLE`-Werten (Stufe "standard": WIND_GUST 20, PRECIPITATION_SUM
# 10, FRESH_SNOW 8, FREEZING_LEVEL 400). Alle vier Deltas sind bewusst exakt
# das 2.5-fache ihrer Schwelle -> eindeutig MAJOR (>=2.0), keine
# Rundungs-/Grenzfall-Ambiguität.
# ─────────────────────────────────────────────────────────────────────────

def test_ac8_untouched_metrics_stay_byte_identical():
    """
    GIVEN identische Eingaben für gust_max_kmh, precip_sum_mm,
          snow_new_sum_cm, freezing_level_m (Stufe "standard"-Schwellen aus
          `_PRESET_TABLE`, unverändert von dieser Scheibe)
    WHEN  detect_changes() läuft
    THEN  Auslösung, Schwelle und Severity dieser vier Metriken bleiben exakt
          wie heute (2.5x Schwelle -> MAJOR).

    Darf JETZT schon grün sein — dient als Regressionsschutz gegen die
    CAPE-Änderung dieser Scheibe (die vier Felder sind vom neuen
    CAPE-Sonderpfad nicht berührt).
    """
    segment = _segment(47.0, 11.0)
    fetched_at = datetime(2026, 8, 8, 6, 0, tzinfo=timezone.utc)
    old_summary = SegmentWeatherSummary(
        gust_max_kmh=20.0, precip_sum_mm=10.0, snow_new_sum_cm=5.0, freezing_level_m=2000,
    )
    new_summary = SegmentWeatherSummary(
        gust_max_kmh=70.0,   # +50 (Schwelle 20 -> 2.5x)
        precip_sum_mm=35.0,  # +25 (Schwelle 10 -> 2.5x)
        snow_new_sum_cm=25.0,  # +20 (Schwelle 8 -> 2.5x)
        freezing_level_m=3000,  # +1000 (Schwelle 400 -> 2.5x)
    )
    old_data = SegmentWeatherData(
        segment=segment, timeseries=None, aggregated=old_summary,
        fetched_at=fetched_at, provider="test-scripted",
    )
    new_data = SegmentWeatherData(
        segment=segment, timeseries=None, aggregated=new_summary,
        fetched_at=fetched_at, provider="test-scripted",
    )
    service = WeatherChangeDetectionService(thresholds={
        "gust_max_kmh": 20.0,
        "precip_sum_mm": 10.0,
        "snow_new_sum_cm": 8.0,
        "freezing_level_m": 400.0,
    })
    changes = service.detect_changes(old_data, new_data)
    by_field = {c.metric: c for c in changes}

    assert set(by_field) == {"gust_max_kmh", "precip_sum_mm", "snow_new_sum_cm", "freezing_level_m"}
    expected_thresholds = {
        "gust_max_kmh": 20.0,
        "precip_sum_mm": 10.0,
        "snow_new_sum_cm": 8.0,
        "freezing_level_m": 400.0,
    }
    for field, expected_threshold in expected_thresholds.items():
        change = by_field[field]
        assert change.threshold == expected_threshold, (
            f"AC-8 Regression: {field}.threshold muss unverändert "
            f"{expected_threshold} bleiben — war {change.threshold!r}."
        )
        assert change.severity is ChangeSeverity.MAJOR, (
            f"AC-8 Regression: {field}.severity muss unverändert MAJOR "
            f"bleiben (2.5x Schwelle) — war {change.severity!r}."
        )
