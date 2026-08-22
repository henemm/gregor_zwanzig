"""TDD RED — Issue #2051 S3: Reichweite der Quelle (`source_reach_minutes`).

SPEC: docs/specs/modules/feat_2051_s3_reichweite_und_guete.md — AC-1, AC-2.

Fachlicher Kern: `_derive_result` kennt seit S1 Beginn und Ende eines nassen
Blocks, aber nicht, WIE WEIT die Quelle selbst geliefert hat. Das neue Feld
`source_reach_minutes` beantwortet das unabhaengig vom Regen-Zustand -- ein
durchgehend TROCKENES Fenster hat trotzdem eine Reichweite.

Zwei Zusicherungen dieser Datei:
  * AC-1 -- eine luecklose Deckung ueber das gesamte 180-Minuten-Fenster
    liefert `source_reach_minutes == 180`, gedeckelt am Horizont.
  * AC-2 -- eine nach Minute 40 abbrechende, komplett TROCKENE Zeitreihe
    liefert eine deutlich kleinere Reichweite (nahe 40 + `_MAX_FRAME_COVERAGE`
    = 55), waehrend `onset_minutes`/`event_end_minutes` unveraendert `None`
    bleiben -- die Reichweite bewegt sich unabhaengig vom Regen-Zustand, kein
    gemeinsamer Waechter verschiebt beide zugleich.

RED heute: `NowcastResult` kennt das additive Feld `source_reach_minutes`
noch nicht -> `AttributeError` beim Zugriff auf das Ergebnis (Dataclass ohne
dieses Feld).

Mock-frei: echte `RadarFrame`-Objekte durch das echte `_derive_result`, die
Uhr ist ueber `now=` FEST injiziert (keine Wanduhr). Eigener Cache je Service
(`cache=RadarNowcastCacheService()`), damit kein prozessweit geteilter
Zustand zwischen den Faellen wirkt.
"""
from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone
from pathlib import Path

from providers.brightsky import RadarFrame
from services.radar_cache import RadarNowcastCacheService
from services.radar_service import RadarNowcastService

# Fester Bezugszeitpunkt aller Faelle -- keine Wanduhr.
_NOW = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)


def _frames(raster: dict[int, float]) -> list[RadarFrame]:
    """`{Minutenversatz ab _NOW: Rate mm/h}` -> echte `RadarFrame`-Liste."""
    return [
        RadarFrame(timestamp=_NOW + timedelta(minutes=minute), precip_mm_h=rate)
        for minute, rate in sorted(raster.items())
    ]


def _result(raster: dict[int, float]):
    """Echtes `_derive_result` mit fest injizierter Uhr."""
    svc = RadarNowcastService(cache=RadarNowcastCacheService())
    return svc._derive_result(_frames(raster), "radar", now=_NOW)


def test_prueling_stammt_aus_diesem_arbeitsbaum():
    """Vorbedingung (kein AC): der gepruefte Nowcast-Dienst wird RELATIV ZU
    DIESER Testdatei aufgeloest -- sonst pruefte ein Worktree-Lauf still die
    Datei des Hauptrepos und lieferte falsches Gruen."""
    from services import radar_service as radar_module

    modul_pfad = Path(inspect.getfile(radar_module)).resolve()
    arbeitsbaum = Path(__file__).resolve().parents[2]
    assert modul_pfad.is_relative_to(arbeitsbaum), (
        f"Prueling stammt nicht aus diesem Arbeitsbaum: {modul_pfad}"
    )


# ---------------------------------------------------------------------------
# AC-1 -- luecklose Deckung ueber das gesamte Fenster -> voller Horizont
# ---------------------------------------------------------------------------


def _volle_deckung_nass() -> dict[int, float]:
    """15-Minuten-Raster, durchgehend nass (1.0 mm/h), von Minute 15 bis
    Minute 180 -- keine Luecke, kein Trockenuebergang."""
    return {m: 1.0 for m in range(15, 181, 15)}


def test_ac1_luecklose_deckung_liefert_den_vollen_horizont():
    """AC-1 GIVEN eine Frame-Zeitreihe, die das gesamte 180-Minuten-Fenster
    durchgehend abdeckt (Raster 15 Min, kein Trockenuebergang, keine Luecke)
    WHEN `_derive_result` `source_reach_minutes` ableitet
    THEN entspricht `source_reach_minutes` dem vollen Horizont (180),
    gedeckelt und nicht darueber hinaus.

    RED heute: `NowcastResult` kennt `source_reach_minutes` nicht
    (`AttributeError`)."""
    result = _result(_volle_deckung_nass())

    assert result.source_reach_minutes == 180, (
        f"RED: bei lueckloser Deckung ueber das gesamte Fenster muss die "
        f"Reichweite dem vollen Horizont (180) entsprechen, bekam "
        f"{result.source_reach_minutes!r}"
    )


def test_ac1_reichweite_uebersteigt_niemals_den_horizont():
    """AC-1 (Deckelung) GIVEN dieselbe luecklose Zeitreihe, deren letzter
    Frame GENAU auf dem Horizont liegt (Minute 180)
    WHEN die Reichweite abgeleitet wird
    THEN bleibt sie exakt auf 180 gedeckelt -- ein Frame am Horizont darf die
    Reichweite nicht ueber den Pruefhorizont hinaustragen (die Formel
    `min(next_ts_full, ts + _MAX_FRAME_COVERAGE, horizon)` deckelt hart auf
    `horizon`).

    RED heute: `NowcastResult` kennt `source_reach_minutes` nicht."""
    result = _result(_volle_deckung_nass())

    assert result.source_reach_minutes <= 180, (
        f"Die Reichweite darf den 180-Minuten-Horizont nicht ueberschreiten: "
        f"{result.source_reach_minutes!r}"
    )


# ---------------------------------------------------------------------------
# AC-2 -- abbrechende, komplett trockene Zeitreihe: Reichweite unabhaengig
# vom Regen-Zustand
# ---------------------------------------------------------------------------


def _abbrechende_trockene_reihe() -> dict[int, float]:
    """10-Minuten-Raster, komplett TROCKEN (0.0 mm/h), bricht nach Minute 40
    ab -- keine weiteren Frames bis zum Horizont."""
    return {m: 0.0 for m in range(0, 41, 10)}


def test_ac2_abbruch_nach_minute_40_liefert_reichweite_nahe_55():
    """AC-2 GIVEN eine Frame-Zeitreihe, die nach Minute 40 abbricht (keine
    weiteren Frames bis zum Horizont), waehrend zugleich KEIN nasser Block
    vorliegt (komplett trocken)
    WHEN `_derive_result` `source_reach_minutes` ableitet
    THEN ist `source_reach_minutes` deutlich kleiner als der Horizont (nahe
    Minute 40 + `_MAX_FRAME_COVERAGE` = 55) -- der letzte Frame (Minute 40)
    hat keinen Nachbarn mehr, seine Deckung reicht bis 40 + 15 = 55, gedeckelt
    am Horizont (hier irrelevant, 55 < 180).

    RED heute: `NowcastResult` kennt `source_reach_minutes` nicht."""
    result = _result(_abbrechende_trockene_reihe())

    assert result.source_reach_minutes == 55, (
        f"RED: nach Abbruch bei Minute 40 muss die Reichweite bei "
        f"40 + _MAX_FRAME_COVERAGE (15) = 55 liegen, bekam "
        f"{result.source_reach_minutes!r}"
    )
    assert result.source_reach_minutes < 180, (
        "Die abgebrochene Reichweite darf nicht auf den vollen Horizont "
        f"zurueckfallen: {result.source_reach_minutes!r}"
    )


def test_ac2_reichweite_bewegt_sich_unabhaengig_vom_regen_zustand():
    """AC-2 (Kernaussage) GIVEN dieselbe abbrechende, komplett trockene
    Zeitreihe
    WHEN `_derive_result` gleichzeitig `source_reach_minutes` UND
    `onset_minutes`/`event_end_minutes` ableitet
    THEN bleiben `onset_minutes` und `event_end_minutes` unveraendert `None`
    (kein nasser Frame im Fenster), waehrend `source_reach_minutes` einen
    konkreten, von 180 verschiedenen Wert traegt -- ein durchgehend
    trockenes Fenster hat trotzdem eine Reichweite, kein gemeinsamer
    Waechter verschiebt beide Groessen zugleich.

    RED heute: `NowcastResult` kennt `source_reach_minutes` nicht."""
    result = _result(_abbrechende_trockene_reihe())

    assert result.onset_minutes is None, (
        f"Vorbedingung verletzt: kein Beginn erwartet, bekam "
        f"{result.onset_minutes!r}"
    )
    assert result.event_end_minutes is None, (
        f"Vorbedingung verletzt: kein Ende erwartet, bekam "
        f"{result.event_end_minutes!r}"
    )
    assert result.source_reach_minutes is not None, (
        "RED: ein durchgehend trockenes Fenster muss trotzdem eine "
        "Reichweite tragen -- 'kein Regen' darf nicht mit 'keine "
        "Beobachtung' verwechselt werden."
    )
    assert result.source_reach_minutes == 55, (
        f"Die Reichweite muss unabhaengig vom fehlenden Regen bei 55 liegen: "
        f"{result.source_reach_minutes!r}"
    )
