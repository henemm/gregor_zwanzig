"""TDD RED — Issue #1474 (S3 zu #1419), AC-2.

SPEC: docs/specs/modules/feat_1474_gewitter_befund_stufen.md v2.3 Abschnitt 2

AC-2 ist die Pflicht-Zusicherung der ganzen Scheibe: die Alarm-Auswertung
("standard"/"entspannt"/"sensibel") muss fuer die BESTEHENDEN drei Stufen
{NONE, MED, HIGH} exakt dieselben Faelle melden wie vor der Erweiterung um
`ThunderLevel.LOW` — obwohl sich die Ordinalskala real verschiebt (MED
wandert von Ordinal 1 auf 2, HIGH von 2 auf 3).

Regressions-Anker: tests/tdd/test_alert_sensitivity_levels.py (21 Tests,
#1460 T1, AC-4..AC-19) MUSS nach dieser Scheibe unveraendert gruen bleiben.
Dieser Test hier ist ZUSAETZLICH: er spielt alle drei Empfindlichkeitsstufen
gegen alle VIER Stufen durch (die alte Suite kennt LOW noch gar nicht) und
prueft dieselbe Zusicherung aus Abschnitt 2 der Spec woertlich:
`ORDINAL_LEVEL_BOUNDS` wird auf benannte `ThunderLevel`-Tupel umgestellt
(entspannt=(HIGH,NONE), standard=(HIGH,HIGH), sensibel=(MED,HIGH)) —
"dieselbe Bedeutung wie heute, jetzt namentlich". Das bedeutet: LOW selbst
ist an keiner der drei Bounds explizit als reach_min/from_max beteiligt,
folgt aber sehr wohl den bestehenden Ordinal-Vergleichsregeln, sobald ein
Sprung ueber MED/HIGH hinweg fuehrt.

RED-Ursache (heute): `ThunderLevel.LOW` existiert nicht -> AttributeError.
Der Zugriff liegt bewusst INNERHALB der Testfunktion (nicht auf Modulebene),
damit ein fehlendes Attribut den einzelnen Test individuell rot macht statt
den Collect der ganzen Datei/Suite abzubrechen. Die scharfe Gegenprobe aus
Abschnitt 2 der Spec ("bleiben die Rohzahlen unveraendert, loest 'standard'
faelschlich schon bei MED aus") ist NICHT hier dupliziert, sondern bewusst
identisch mit dem bestehenden Regressions-Anker
`tests/tdd/test_alert_sensitivity_levels.py::test_ac6_standard_meldet_die_
mittelstufe_nicht` -- dieser Test bleibt schon heute (vor LOW) gruen und ist
deshalb kein neuer RED-Test, sondern die geforderte "unveraendert gruen
bleibende" Regressionspruefung selbst (s. AC-2, zweiter Satz).

Keine Mocks: echte SegmentWeatherSummary-Fixturen mit direkt konstruierten
ThunderLevel-Werten (Muster test_alert_sensitivity_levels.py), echte
expand_per_metric_levels()- und WeatherChangeDetectionService-Aufrufe, kein
Netz, kein Versand.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

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

# NUR die drei heute existierenden Werte auf Modulebene binden. `LOW` wird
# bewusst NICHT hier (und nicht per `getattr(..., None)`-Sentinel) aufgeloest
# -- ein Zugriff auf Modulebene wuerde die Collection der Datei/Suite mit
# einer AttributeError abbrechen, ein stiller `None`-Fallback wuerde die
# Matrix mit einem semantisch falschen Platzhalter statt der echten Stufe
# fuellen. Die Testfunktion loest `ThunderLevel.LOW` selbst auf (s.u.).
NONE, MED, HIGH = ThunderLevel.NONE, ThunderLevel.MED, ThunderLevel.HIGH


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


def test_ac2_vier_stufen_matrix_je_empfindlichkeit():
    """AC-2: die volle Vier-Stufen-Matrix je Empfindlichkeit — LOW eingerechnet,
    aber die Bounds fuer die drei Bestandsstufen bleiben IDENTISCH zu vorher
    (Abschnitt 2: dieselben Grenzen, jetzt namentlich statt numerisch)."""
    # Bewusst hier (innerhalb der Testfunktion) aufgeloest, nicht auf
    # Modulebene: fehlt die Stufe noch, faellt NUR dieser eine Test mit einer
    # klaren AttributeError, die Collection der Datei bleibt unberuehrt.
    LOW = ThunderLevel.LOW
    matrix = {
        # sensibel: reach_min=MED, from_max=HIGH (unveraendert ggue. #1460 T1,
        # jetzt als Namen statt Rohzahl 1/2) -> LOW selbst loest NICHT aus,
        # solange kein Sprung MINDESTENS bis MED reicht.
        ("sensibel", NONE, LOW): 0,
        ("sensibel", LOW, MED): 1,
        ("sensibel", MED, HIGH): 1,
        ("sensibel", HIGH, MED): 1,
        ("sensibel", MED, LOW): 1,
        ("sensibel", LOW, NONE): 0,
        # standard: reach_min=HIGH, from_max=HIGH (unveraendert) -> nur das
        # ERREICHEN/VERLASSEN der Hoechststufe loest aus, unabhaengig davon,
        # ob der Ausgangswert LOW statt NONE war.
        ("standard", NONE, LOW): 0,
        ("standard", LOW, MED): 0,
        ("standard", MED, HIGH): 1,
        ("standard", LOW, HIGH): 1,
        ("standard", HIGH, MED): 1,
        ("standard", HIGH, LOW): 1,
        ("standard", MED, LOW): 0,
        # entspannt: reach_min=HIGH, from_max=NONE (unveraendert) -> NUR der
        # volle Sprung "kein Gewitter" <-> Hoechststufe. Ein Sprung, der bei
        # LOW beginnt oder endet, ist explizit KEIN voller Sprung.
        ("entspannt", NONE, LOW): 0,
        ("entspannt", LOW, HIGH): 0,
        ("entspannt", NONE, HIGH): 1,
        ("entspannt", HIGH, NONE): 1,
        ("entspannt", HIGH, LOW): 0,
    }
    abweichungen = []
    for (level, old, new), expected in matrix.items():
        changes = _thunder_changes(old, new, level)
        if len(changes) != expected:
            abweichungen.append(
                f"{level} {old.name}->{new.name}: erwartet {expected}, "
                f"erhalten {len(changes)}"
            )
    assert not abweichungen, (
        "Die Vier-Stufen-Alarm-Matrix stimmt nicht mit Abschnitt 2 der Spec "
        "ueberein:\n  " + "\n  ".join(abweichungen)
    )
