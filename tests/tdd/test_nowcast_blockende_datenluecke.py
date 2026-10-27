"""TDD RED — Issue #2051 S1: Datenluecken beim Ableiten des Blockendes.

SPEC: docs/specs/modules/feat_2051_s1_dauer_und_ende.md — AC-3, AC-4.

Fachlicher Kern: ein FEHLENDER Frame ist keine Quellenaussage "hier hat es
aufgehoert", sondern schlicht keine Beobachtung. Die Ende-Bestimmung benutzt
deshalb DIESELBE Deckungsmechanik wie `_accumulate_precip_mm` (Rechenkern aus
#2046/#2020) und KEINE neue Toleranzzahl:

  * Luecke <= `_MAX_FRAME_COVERAGE` (15 Min) -> die Deckung des letzten
    Frames reicht ueber die Luecke; der Block laeuft weiter (AC-3).
  * Luecke > 15 Min -> das Ende wird an der Deckungsgrenze gesetzt
    (`letzter Frame vor der Luecke + 15 Min`), NICHT am nach der Luecke
    wieder nassen Frame (AC-4).

RED heute: `NowcastResult` kennt das additive Feld `event_end_minutes` noch
nicht -> `AttributeError` beim Zugriff auf das Ergebnis.

Mock-frei: echte `RadarFrame`-Objekte durch das echte `_derive_result`, Uhr
ueber `now=` FEST injiziert (keine Wanduhr), eigener Cache je Service.
"""
from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone
from pathlib import Path

from providers.brightsky import RadarFrame
from services.radar_cache import RadarNowcastCacheService
from services.radar_service import _MAX_FRAME_COVERAGE, RadarNowcastService

_NOW = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)

# Deckung EINES Frames in Minuten — bewusst aus der Produktivkonstante
# gelesen, nicht als zweite 15 danebengeschrieben (sonst waere die Zusicherung
# gegen eine Kopie der Zahl gestellt statt gegen die gueltige).
_DECKUNG_MIN = int(_MAX_FRAME_COVERAGE.total_seconds() // 60)


def _frames(raster: dict[int, float]) -> list[RadarFrame]:
    """`{Minutenversatz ab _NOW: Rate mm/h}` -> echte `RadarFrame`-Liste.

    Ein Minutenversatz, der NICHT im Wörterbuch steht, ist eine echte
    Datenluecke — es entsteht kein Frame dafuer."""
    return [
        RadarFrame(timestamp=_NOW + timedelta(minutes=minute), precip_mm_h=rate)
        for minute, rate in sorted(raster.items())
    ]


def _result(raster: dict[int, float]):
    svc = RadarNowcastService(cache=RadarNowcastCacheService())
    return svc._derive_result(_frames(raster), "radar", now=_NOW)


def test_prueling_stammt_aus_diesem_arbeitsbaum():
    """Vorbedingung (kein AC): der gepruefte Nowcast-Dienst wird RELATIV ZU
    DIESER Testdatei aufgeloest — sonst pruefte ein Worktree-Lauf still die
    Datei des Hauptrepos."""
    from services import radar_service as radar_module

    modul_pfad = Path(inspect.getfile(radar_module)).resolve()
    arbeitsbaum = Path(__file__).resolve().parents[2]
    assert modul_pfad.is_relative_to(arbeitsbaum), (
        f"Prueling stammt nicht aus diesem Arbeitsbaum: {modul_pfad}"
    )


def test_deckungskonstante_ist_fuenfzehn_minuten():
    """Vorbedingung (kein AC): die beiden Faelle unten sind nur dann
    aussagekraeftig, wenn die Deckung eines Frames 15 Minuten betraegt — die
    10-Minuten-Luecke liegt darunter, die 25-Minuten-Luecke darueber."""
    assert _DECKUNG_MIN == 15, (
        f"Testaufbau haengt an _MAX_FRAME_COVERAGE == 15 Min, ist aber "
        f"{_DECKUNG_MIN} Min — die Luecken-Faelle muessen nachgezogen werden."
    )


# ---------------------------------------------------------------------------
# AC-3 — Luecke INNERHALB der Deckung beendet den Block nicht
# ---------------------------------------------------------------------------


def _luecke_innerhalb_der_deckung() -> dict[int, float]:
    """5-Minuten-Raster, nass ab Minute 20; der Frame bei Minute 35 FEHLT
    (10 Minuten Abstand zwischen den vorhandenen Frames 30 und 40), danach
    weiter nass bis Minute 50, ab Minute 55 trocken."""
    raster = {m: 0.0 for m in range(0, 121, 5)}
    for m in (20, 25, 30, 40, 45, 50):
        raster[m] = 1.0
    del raster[35]
    return raster


def test_ac3_zehn_minuten_luecke_beendet_den_block_nicht():
    """AC-3 GIVEN einen nassen Block, in dem ein einzelner Frame mitten drin
    fehlt (5-Minuten-Raster, dadurch 10 Minuten Abstand zwischen den
    vorhandenen Frames bei Minute 30 und 40 — innerhalb der
    `_MAX_FRAME_COVERAGE`-Deckung von 15 Minuten)
    WHEN das Ende abgeleitet wird
    THEN wird der Block durch die Luecke NICHT faelschlich beendet: das Ende
    liegt beim letzten tatsaechlich nassen Frame NACH der Luecke (Minute 50),
    nicht bei der Luecke selbst (Minute 30).

    Ein fehlender Frame ist keine Beobachtung — ihn wie einen Trockenframe zu
    behandeln wuerde die Dauer systematisch zu kurz melden.

    RED heute: `NowcastResult` kennt `event_end_minutes` nicht."""
    result = _result(_luecke_innerhalb_der_deckung())

    assert result.onset_minutes == 20, (
        f"Vorbedingung: Beginn bei Minute 20 erwartet, bekam "
        f"{result.onset_minutes}"
    )
    assert result.event_end_minutes == 50, (
        f"RED: eine 10-Minuten-Luecke liegt innerhalb der Deckung und darf den "
        f"Block nicht beenden — erwartet Minute 50, bekam "
        f"{result.event_end_minutes!r}"
    )
    assert result.event_end_minutes != 30, (
        "Der Block wurde an der Datenluecke beendet — eine fehlende "
        "Beobachtung ist keine Trockenmeldung."
    )
    assert result.event_ongoing_beyond_horizon is False, (
        "Der Block endet an einem Trockenframe im Fenster — der "
        "Horizont-Waechter darf nicht anschlagen."
    )


# ---------------------------------------------------------------------------
# AC-4 — Luecke GROESSER als die Deckung setzt das Ende an der Deckungsgrenze
# ---------------------------------------------------------------------------


def _luecke_groesser_als_deckung() -> dict[int, float]:
    """Nass bei 20/25/30, dann 25 Minuten ohne jeden Frame, ab Minute 55
    wieder nass (55/60), ab Minute 65 trocken."""
    raster = {m: 0.0 for m in range(0, 121, 5)}
    for m in range(35, 55, 5):
        del raster[m]
    for m in (20, 25, 30, 55, 60):
        raster[m] = 1.0
    return raster


def test_ac4_luecke_groesser_als_die_deckung_endet_an_der_deckungsgrenze():
    """AC-4 GIVEN einen nassen Block mit einer Datenluecke von 25 Minuten
    (groesser als `_MAX_FRAME_COVERAGE` = 15 Minuten) zwischen dem letzten
    nassen Frame bei Minute 30 und dem naechsten Frame bei Minute 55, der
    wieder nass ist
    WHEN das Ende abgeleitet wird
    THEN wird das Ende an der Deckungsgrenze des letzten Frames vor der
    Luecke gesetzt (Minute 30 + 15 = Minute 45) — NICHT am nach der Luecke
    wieder nassen Frame (Minute 55) und nicht am Frame selbst (Minute 30).

    Dieselbe Deckungsmechanik wie `_accumulate_precip_mm`, keine neue
    Toleranzzahl: ein einzelner Frame darf nie fuer mehr Zeit einstehen, als
    das groebste Produktivraster hergibt.

    RED heute: `NowcastResult` kennt `event_end_minutes` nicht."""
    result = _result(_luecke_groesser_als_deckung())

    assert result.onset_minutes == 20, (
        f"Vorbedingung: Beginn bei Minute 20 erwartet, bekam "
        f"{result.onset_minutes}"
    )
    assert result.event_end_minutes == 30 + _DECKUNG_MIN, (
        f"RED: das Ende muss an der Deckungsgrenze liegen "
        f"(Minute 30 + {_DECKUNG_MIN} = {30 + _DECKUNG_MIN}), bekam "
        f"{result.event_end_minutes!r}"
    )
    assert result.event_end_minutes != 55, (
        "Der Block wurde ueber die Luecke hinweg bis zum naechsten nassen "
        "Frame gestreckt — 25 Minuten ohne Beobachtung sind kein Regen."
    )
    assert result.event_end_minutes != 30, (
        "Das Ende wurde auf den letzten Frame gesetzt statt auf dessen "
        "Deckungsgrenze — die Deckung eines Frames reicht 15 Minuten weit."
    )
    assert result.event_ongoing_beyond_horizon is False, (
        "Eine Deckungsgrenze ist ein bekanntes Ende innerhalb des Fensters — "
        "der Horizont-Waechter gilt nur fuer Bloecke, die den Horizont "
        "erreichen."
    )
