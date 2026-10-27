"""TDD RED — Issue #2046: die angezeigte Menge ist am BEGINN ausgerichtet,
nicht an "jetzt".

SPEC: docs/specs/modules/fix_2046_onset_menge.md — AC-3 (Messgrundlage,
durchgerechnetes Gegenbeispiel) und AC-12 (ein Aufruf, vier Felder, kein
zweiter Abruf).

Fachlicher Kern (das Risiko, das dieses Ticket ueberhaupt erst hat): das
bestehende Feld `window_precip_mm` misst die Menge der 60 Minuten AB JETZT,
der Onset-Alarm feuert aber bis 55 Minuten vor dem Beginn
(`RADAR_ONSET_THRESHOLD_MIN`). Bei spaetem Beginn deckt dieses Fenster fast
nur noch trockene Zeit ab — die Zahl waere systematisch zu klein und wuerde
den Alarm durch Untertreibung entwerten. Das neue Feld `onset_precip_mm`
misst deshalb die 60 Minuten AB DEM BEGINN.

Der Wächter unten schlaegt rot, sobald jemand `onset_precip_mm` (wieder) ab
"jetzt" rechnet, ODER es als blosse Rate mal eine Stunde hochrechnet statt
ueber die Frames zu akkumulieren.

Mock-frei: echte `RadarFrame`-Objekte mit echten Zeitstempeln, echter
`RadarNowcastService`, injizierte Zeit (`now=`/`now_fn=`) statt Wanduhr,
echter zaehlender `frame_source` (DI-Naht des Services) statt `patch`.
"""
from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from providers.brightsky import RadarFrame
from services.radar_service import RadarNowcastService

# Fester Bezugszeitpunkt — keine Wanduhr im Test.
NOW = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)
# 5-Minuten-Raster (RADOLAN-Kadenz), 180 Minuten weit — deckt sowohl das
# 60-Min-Fenster ab jetzt als auch das 60-Min-Fenster ab Minute 50 voll ab.
RASTER_MIN = 5
DAUER_MIN = 180
REGEN_RATE = 12.0  # mm/h


def _frames(*, regen_ab_min: int, regen_bis_min: int = DAUER_MIN + 1,
            rate: float = REGEN_RATE) -> list[RadarFrame]:
    """Frames im 5-Minuten-Raster ab `NOW`: trocken, ausser im Abschnitt
    [`regen_ab_min`, `regen_bis_min`) — dort `rate` mm/h."""
    frames = []
    for offset in range(0, DAUER_MIN + RASTER_MIN, RASTER_MIN):
        nass = regen_ab_min <= offset < regen_bis_min
        frames.append(RadarFrame(
            timestamp=NOW + timedelta(minutes=offset),
            precip_mm_h=rate if nass else 0.0,
            is_convective=False,
        ))
    return frames


def _service() -> RadarNowcastService:
    """Eigener Service MIT EIGENEM Cache — der geteilte Prozess-Cache wuerde
    Abruf-Zaehlungen zwischen Tests verfaelschen."""
    from services.radar_cache import RadarNowcastCacheService

    return RadarNowcastService(cache=RadarNowcastCacheService(), now_fn=lambda: NOW)


def test_prueling_stammt_aus_diesem_arbeitsbaum():
    """Vorbedingung (kein AC): der gepruefte Dienst wird RELATIV ZU DIESER
    Testdatei aufgeloest — sonst pruefte ein Worktree-Lauf still die Datei des
    Hauptrepos und lieferte falsches Gruen."""
    import services.radar_service as radar_module

    modul_pfad = Path(inspect.getfile(radar_module)).resolve()
    arbeitsbaum = Path(__file__).resolve().parents[2]
    assert modul_pfad.is_relative_to(arbeitsbaum), (
        f"Prueling stammt nicht aus diesem Arbeitsbaum: {modul_pfad}"
    )


# ---------------------------------------------------------------------------
# AC-3 — spaeter Beginn: "ab jetzt" untertreibt, "ab Beginn" trifft
# ---------------------------------------------------------------------------


def test_ac3_spaeter_beginn_menge_ab_beginn_statt_ab_jetzt():
    """AC-3 GIVEN ein `NowcastResult`, dessen Beginn 50 Minuten voraus liegt
    (unter der 55-Minuten-Ausloeseschwelle), dessen Frames VOR dem Beginn
    durchgaengig trocken sind (0 mm/h) und AB dem Beginn 12 mm/h liefern
    WHEN `_derive_result` sowohl `window_precip_mm` (60 Min ab jetzt) als
    auch `onset_precip_mm` (60 Min ab Beginn) berechnet
    THEN weist `window_precip_mm` nur rund 2 mm aus (das Fenster ab jetzt
    erfasst nur die letzten 10 Minuten vor dem Fensterende), waehrend
    `onset_precip_mm` rund 12 mm ausweist (volle Stunde bei 12 mm/h) — die
    neue Zahl entwertet den Alarm nicht durch Untertreibung.

    DURCHGERECHNET (5-Min-Raster, Regen ab Minute 50):
      * Fenster ab jetzt  [0, 60):   Frames 50 und 55 nass -> 2 x 5 Min x
        12 mm/h = 2.0 mm
      * Fenster ab Beginn [50, 110): 12 nasse Frames x 5 Min x 12 mm/h =
        12.0 mm

    Beide Erwartungen stehen mit ENGER Toleranz da: wer `onset_precip_mm`
    versehentlich wieder ab "jetzt" rechnet, landet bei 2.0 mm und faellt hier
    hart durch.

    RED heute: `NowcastResult` kennt `onset_precip_mm` nicht
    (`AttributeError`)."""
    result = _service()._derive_result(_frames(regen_ab_min=50), "radar", now=NOW)

    assert result.onset_minutes == 50, (
        f"Voraussetzung: der Beginn muss bei Minute 50 liegen, "
        f"war {result.onset_minutes!r}"
    )
    assert result.window_precip_mm == pytest.approx(2.0, abs=0.25), (
        "Voraussetzung: das Fenster AB JETZT muss den Regen fast verpassen "
        f"(rund 2 mm), war {result.window_precip_mm!r}"
    )

    onset_menge = result.onset_precip_mm
    assert onset_menge == pytest.approx(12.0, abs=0.6), (
        "RED: die angezeigte Menge muss die volle Stunde AB DEM BEGINN "
        f"messen (rund 12 mm), war {onset_menge!r} — bei rund 2 mm ist sie "
        "faelschlich ab 'jetzt' gerechnet."
    )
    assert onset_menge > 4 * result.window_precip_mm, (
        "RED: bei spaetem Beginn MUSS die Menge ab Beginn die Menge ab jetzt "
        f"deutlich uebersteigen: {onset_menge!r} vs "
        f"{result.window_precip_mm!r}"
    )


def test_ac3_kurzer_schauer_wird_akkumuliert_nicht_hochgerechnet():
    """AC-3 (Gegenprobe zur Rechenart) GIVEN denselben spaeten Beginn, aber
    einen Regen, der nach 10 Minuten wieder aufhoert (Minute 50 bis 60)
    WHEN `onset_precip_mm` berechnet wird
    THEN weist es rund 2 mm aus (10 Minuten bei 12 mm/h) — NICHT 12 mm.

    Nagelt fest, dass ueber die Frames AKKUMULIERT und nicht die Spitzenrate
    mit einer Stunde multipliziert wird. Der Hauptfall oben allein koennte
    beide Rechenarten nicht unterscheiden.

    RED heute: `NowcastResult` kennt `onset_precip_mm` nicht."""
    result = _service()._derive_result(
        _frames(regen_ab_min=50, regen_bis_min=60), "radar", now=NOW,
    )

    assert result.onset_minutes == 50
    assert result.onset_precip_mm == pytest.approx(2.0, abs=0.25), (
        "RED: ein 10-Minuten-Schauer bei 12 mm/h ergibt rund 2 mm — "
        f"bekam {result.onset_precip_mm!r} (12 mm hiesse: Rate mal Stunde "
        "hochgerechnet statt akkumuliert)."
    )


def test_ac3_sofortiger_beginn_laesst_beide_fenster_zusammenfallen():
    """AC-3 (zweite Gegenprobe) GIVEN Regen, der SOFORT beginnt (Minute 0)
    WHEN beide Mengen berechnet werden
    THEN fallen sie zusammen — die beiden Fenster sind dann deckungsgleich.

    Waechter gegen einen konstanten Versatz: eine Implementierung, die die
    Menge pauschal streckt oder ein anderes Fenster als 60 Minuten benutzt,
    faellt hier auf, obwohl der Hauptfall oben gruen bliebe.

    RED heute: `NowcastResult` kennt `onset_precip_mm` nicht."""
    result = _service()._derive_result(_frames(regen_ab_min=0), "radar", now=NOW)

    assert result.onset_minutes == 0
    assert result.window_precip_mm == pytest.approx(12.0, abs=0.6), (
        f"Voraussetzung: Dauerregen ab jetzt ergibt rund 12 mm, "
        f"war {result.window_precip_mm!r}"
    )
    assert result.onset_precip_mm == pytest.approx(result.window_precip_mm, abs=0.1), (
        "RED: bei sofortigem Beginn muessen beide Fenster dieselbe Menge "
        f"liefern: {result.onset_precip_mm!r} vs {result.window_precip_mm!r}"
    )


def test_ac3_ohne_beginn_gibt_es_keine_menge():
    """AC-3 (Rand) GIVEN durchgaengig trockene Frames (kein Beginn)
    WHEN `_derive_result` laeuft
    THEN bleibt `onset_precip_mm` `None` — es gibt kein Fenster, auf das es
    sich beziehen koennte (Grundlage der zahlenlosen Ausweichform, AC-4).

    RED heute: `NowcastResult` kennt `onset_precip_mm` nicht."""
    result = _service()._derive_result(
        _frames(regen_ab_min=DAUER_MIN + 99), "radar", now=NOW,
    )

    assert result.onset_minutes is None, "Voraussetzung: kein Beginn im Fenster"
    assert result.onset_precip_mm is None, (
        "RED: ohne Beginn darf keine Menge entstehen (schon gar keine 0.0, die "
        f"als Zahl in die SMS liefe): {result.onset_precip_mm!r}"
    )


# ---------------------------------------------------------------------------
# AC-12 — EIN Abruf, EIN Ergebnisobjekt, vier Felder
# ---------------------------------------------------------------------------


class _ZaehlenderFrameSource:
    """Echter aufrufbarer `frame_source` (DI-Naht des Services, kein Mock):
    liefert dieselbe Frame-Liste und zaehlt, wie oft er befragt wurde."""

    def __init__(self, frames: list[RadarFrame]) -> None:
        self._frames = frames
        self.calls = 0

    def __call__(self, lat: float, lon: float) -> list[RadarFrame]:
        self.calls += 1
        return list(self._frames)


def test_ac12_ein_abruf_liefert_alle_vier_felder_aus_derselben_frameliste():
    """AC-12 GIVEN die Frame-Liste, aus der `_derive_result` `onset_minutes`
    und `window_precip_mm` ableitet
    WHEN `onset_precip_mm` berechnet wird
    THEN verwendet die Rechnung DIESELBE Frame-Liste — genau EIN Abruf der
    Quelle — und alle vier Felder (`onset_minutes`, `window_precip_mm`,
    `max_rate_mm_h`, `onset_precip_mm`) stammen aus DEMSELBEN Ergebnisobjekt.
    Weder `onset_minutes` noch `window_precip_mm` noch `max_rate_mm_h`
    veraendern sich durch die neue Rechnung.

    Der Abruf-Zaehler ist ein echtes aufrufbares Objekt an der vorhandenen
    `frame_source`-Naht — kein `patch`, das einen zweiten Produktiv-Abruf
    verschleiern koennte.

    RED heute: `NowcastResult` kennt `onset_precip_mm` nicht
    (`AttributeError`)."""
    from services.radar_cache import RadarNowcastCacheService

    quelle = _ZaehlenderFrameSource(_frames(regen_ab_min=50))
    service = RadarNowcastService(
        frame_source=quelle, cache=RadarNowcastCacheService(),
        now_fn=lambda: NOW,
    )

    result = service.get_nowcast(51.0, 10.0)

    assert quelle.calls == 1, (
        f"Die neue Zahl darf keinen zweiten Quellen-Abruf ausloesen — "
        f"{quelle.calls} Abrufe gezaehlt."
    )
    assert result.onset_minutes == 50, (
        f"onset_minutes hat sich veraendert: {result.onset_minutes!r}"
    )
    assert result.window_precip_mm == pytest.approx(2.0, abs=0.25), (
        f"window_precip_mm hat sich veraendert: {result.window_precip_mm!r}"
    )
    assert result.max_rate_mm_h == pytest.approx(12.0, abs=0.01), (
        f"max_rate_mm_h hat sich veraendert: {result.max_rate_mm_h!r}"
    )
    assert result.onset_precip_mm == pytest.approx(12.0, abs=0.6), (
        f"RED: onset_precip_mm fehlt oder misst das falsche Fenster: "
        f"{result.onset_precip_mm!r}"
    )
