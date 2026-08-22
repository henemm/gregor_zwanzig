"""TDD RED — Issue #2051 S1: Ende des zusammenhaengenden nassen Blocks.

SPEC: docs/specs/modules/feat_2051_s1_dauer_und_ende.md — AC-1, AC-2.

Fachlicher Kern: die Onset-Schleife (`_derive_result`) bricht heute beim
ERSTEN nassen Frame ab; der Rest der bereits abgerufenen Zeitreihe wird
verworfen. Neu wird aus DENSELBEN Frames zusaetzlich das Ende des
zusammenhaengenden nassen Blocks abgeleitet (`event_end_minutes`) — ohne
neuen Quellenabruf.

Zwei Zusicherungen dieser Datei:
  * AC-1 — ein durchgehend nasser Block endet beim LETZTEN nassen Frame vor
    dem Trockenuebergang, nicht am Horizont und nicht am Beginn.
  * AC-2 — ein zweiter, spaeterer Regenblock in derselben Zeitreihe wird
    NICHT eingerechnet: zwei getrennte Ereignisse duerfen nicht zu einer
    ueberlangen Dauer verschmelzen.

RED heute: `NowcastResult` kennt das additive Feld `event_end_minutes` noch
nicht -> `AttributeError` beim Zugriff auf das Ergebnis; der in der Spec
vorgeschriebene Helfer `_derive_wet_block_end` existiert nicht ->
`ImportError`.

Mock-frei: echte `RadarFrame`-Objekte durch das echte `_derive_result`, die
Uhr ist ueber `now=` FEST injiziert (keine Wanduhr). Eigener Cache je
Service (`cache=RadarNowcastCacheService()`), damit kein prozessweit
geteilter Zustand zwischen den Faellen wirkt.
"""
from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone
from pathlib import Path

from providers.brightsky import RadarFrame
from services.radar_cache import RadarNowcastCacheService
from services.radar_service import RadarNowcastService

# Fester Bezugszeitpunkt aller Faelle — keine Wanduhr.
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


def _fuenf_minuten_raster(nass_von: int, nass_bis: int, ende: int = 120) -> dict[int, float]:
    """Durchgehendes 5-Minuten-Raster; nass (1.0 mm/h) im angegebenen
    Minutenfenster, sonst trocken (0.0 mm/h)."""
    return {
        m: (1.0 if nass_von <= m <= nass_bis else 0.0)
        for m in range(0, ende + 1, 5)
    }


def test_prueling_stammt_aus_diesem_arbeitsbaum():
    """Vorbedingung (kein AC): der gepruefte Nowcast-Dienst wird RELATIV ZU
    DIESER Testdatei aufgeloest — sonst pruefte ein Worktree-Lauf still die
    Datei des Hauptrepos und lieferte falsches Gruen."""
    from services import radar_service as radar_module

    modul_pfad = Path(inspect.getfile(radar_module)).resolve()
    arbeitsbaum = Path(__file__).resolve().parents[2]
    assert modul_pfad.is_relative_to(arbeitsbaum), (
        f"Prueling stammt nicht aus diesem Arbeitsbaum: {modul_pfad}"
    )


# ---------------------------------------------------------------------------
# AC-1 — durchgehender Block: Ende am letzten nassen Frame
# ---------------------------------------------------------------------------


def test_ac1_durchgehender_block_endet_am_letzten_nassen_frame():
    """AC-1 GIVEN eine Frame-Zeitreihe im 5-Minuten-Raster mit einem
    durchgaengig nassen Block (`precip_mm_h >= 0.1`) von Minute 20 bis
    Minute 80, danach trocken
    WHEN `_derive_result` daraus `event_end_minutes` ableitet
    THEN entspricht `event_end_minutes` dem Zeitpunkt des LETZTEN nassen
    Frames vor dem Trockenuebergang (Minute 80) — nicht dem Horizontende
    (180) und nicht dem Beginn (20).

    RED heute: `NowcastResult` kennt `event_end_minutes` nicht."""
    result = _result(_fuenf_minuten_raster(20, 80))

    assert result.onset_minutes == 20, (
        f"Vorbedingung verletzt: Beginn nicht bei Minute 20, sondern "
        f"{result.onset_minutes}"
    )
    assert result.event_end_minutes == 80, (
        f"RED: Blockende muss am letzten nassen Frame (Minute 80) liegen, "
        f"bekam {result.event_end_minutes!r}"
    )
    assert result.event_end_minutes != 180, (
        "Das Ende darf nicht auf das Horizontende gesetzt werden, solange ein "
        "Trockenframe im Fenster liegt."
    )
    assert result.event_end_minutes != result.onset_minutes, (
        "Das Ende darf nicht auf den Beginn zurueckfallen — dann waere die "
        "Dauer strukturell immer null."
    )


def test_ac1_ende_ohne_beginn_bleibt_leer():
    """AC-1 (Kehrseite) GIVEN eine durchgehend trockene Frame-Zeitreihe
    (kein Beginn erkannt, `onset_minutes is None`)
    WHEN `_derive_result` das Ergebnis baut
    THEN bleibt `event_end_minutes` `None` und der Horizont-Waechter `False`
    — ohne Beginn gibt es kein Ende, das behauptet werden koennte.

    RED heute: `NowcastResult` kennt die beiden Felder nicht."""
    result = _result({m: 0.0 for m in range(0, 121, 5)})

    assert result.onset_minutes is None, "Vorbedingung: kein Beginn erwartet"
    assert result.event_end_minutes is None, (
        f"Ohne Beginn darf kein Ende entstehen: {result.event_end_minutes!r}"
    )
    assert result.event_ongoing_beyond_horizon is False, (
        "Ohne Beginn darf der Horizont-Waechter nicht anschlagen: "
        f"{result.event_ongoing_beyond_horizon!r}"
    )


def test_ac1_helfer_derive_wet_block_end_liefert_ende_und_waechter():
    """AC-1 (Bauform) GIVEN denselben durchgehenden Block
    WHEN der in der Spec vorgeschriebene Helfer `_derive_wet_block_end(
    frames, all_ts_sorted, onset_ts, horizon)` direkt aufgerufen wird
    THEN liefert er das Tupel `(end_ts, ongoing_beyond_horizon)` mit dem
    Zeitstempel des letzten nassen Frames und `False`.

    Der Helfer ist bewusst ein GESCHWISTER von `_accumulate_precip_mm`
    (Summieren in bekanntem Fenster) und nicht dessen Erweiterung —
    Grenzenfinden ist eine andere Aufgabe.

    RED heute: der Helfer existiert nicht (`ImportError`)."""
    from services.radar_service import _derive_wet_block_end

    frames = _frames(_fuenf_minuten_raster(20, 80))
    all_ts_sorted = sorted({f.timestamp for f in frames})
    onset_ts = _NOW + timedelta(minutes=20)
    horizon = _NOW + timedelta(minutes=180)

    end_ts, ongoing = _derive_wet_block_end(frames, all_ts_sorted, onset_ts, horizon)

    assert end_ts == _NOW + timedelta(minutes=80), (
        f"Helfer liefert das falsche Blockende: {end_ts!r}"
    )
    assert ongoing is False, (
        f"Ein im Fenster beendeter Block darf den Waechter nicht setzen: "
        f"{ongoing!r}"
    )


# ---------------------------------------------------------------------------
# AC-2 — zwei getrennte Bloecke verschmelzen nicht
# ---------------------------------------------------------------------------


def _zwei_bloecke() -> dict[int, float]:
    """Nass 10-30, trocken 35-50, wieder nass 55-70 (5-Minuten-Raster)."""
    raster = {m: 0.0 for m in range(0, 121, 5)}
    for m in range(10, 31, 5):
        raster[m] = 1.0
    for m in range(55, 71, 5):
        raster[m] = 1.0
    return raster


def test_ac2_zwei_getrennte_bloecke_verschmelzen_nicht():
    """AC-2 GIVEN zwei getrennte nasse Bloecke in DERSELBEN Zeitreihe
    (nass Minute 10-30, trocken Minute 35-50, wieder nass Minute 55-70)
    WHEN `_derive_result` Beginn und Ende ableitet
    THEN endet der Block beim ersten Trockenuebergang nach Minute 30 — das
    zweite, spaetere Ereignis wird NICHT eingerechnet.

    Ein Zusammenziehen wuerde die Dauer ueberschaetzen (60 statt 20 Minuten)
    und dem Nutzer durchgehenden Regen behaupten, wo die Quelle eine
    Trockenphase zeigt.

    RED heute: `NowcastResult` kennt `event_end_minutes` nicht."""
    result = _result(_zwei_bloecke())

    assert result.onset_minutes == 10, (
        f"Vorbedingung: Beginn bei Minute 10 erwartet, bekam "
        f"{result.onset_minutes}"
    )
    assert result.event_end_minutes == 30, (
        f"RED: das Ende des ERSTEN Blocks muss bei Minute 30 liegen, bekam "
        f"{result.event_end_minutes!r}"
    )
    assert result.event_end_minutes < 55, (
        f"Das Ende reicht in den zweiten, unabhaengigen Block hinein "
        f"({result.event_end_minutes!r}) — die beiden Ereignisse sind "
        f"verschmolzen."
    )
    assert result.event_ongoing_beyond_horizon is False, (
        "Ein durch einen Trockenframe beendeter Block ist ein BEKANNTES Ende "
        "— der Horizont-Waechter darf nicht anschlagen."
    )


def test_ac2_dauer_ergibt_sich_aus_beginn_und_ende():
    """AC-2 (abgeleitete Dauer) GIVEN denselben Aufbau
    WHEN die Dauer als `event_end_minutes - onset_minutes` gebildet wird
    THEN ergibt sie 20 Minuten (nicht 60) — und es gibt KEIN gespeichertes
    `event_duration_minutes`-Feld, das als zweite Quelle der Wahrheit
    auseinanderlaufen koennte (Spec, Implementation Details).

    RED heute: `NowcastResult` kennt `event_end_minutes` nicht."""
    result = _result(_zwei_bloecke())

    assert result.event_end_minutes - result.onset_minutes == 20, (
        f"Dauer falsch: {result.onset_minutes} -> {result.event_end_minutes!r}"
    )
    assert not hasattr(result, "event_duration_minutes"), (
        "Kein gespeichertes Dauer-Feld: die Dauer ist stets die Differenz "
        "aus Beginn und Ende (Spec: keine zweite Quelle der Wahrheit)."
    )
