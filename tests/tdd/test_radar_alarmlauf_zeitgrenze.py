"""TDD RED — Epic #2261, Scheibe A-2 S2: Zeitgrenze im Radar-Alarmlauf.

SPEC: docs/specs/modules/feat_2261_a2s2_radar_takt.md (AC-3 Python-Seite, AC-4)

ACHTUNG Namen: Die Spec spricht von ``RadarService``; die echte Klasse heisst
``services.radar_service.RadarNowcastService`` (``get_nowcast`` und
``_fetch_frames_with_fallback`` liegen dort).

Vertrag, den diese Tests der Implementierung vorgeben:
- ``RadarNowcastService.get_nowcast(..., deadline_at: Optional[float] = None)``
  — absolute ``time.monotonic()``-Marke. Default ``None`` = Verhalten
  unveraendert.
- ``services.radar_service.RadarDeadlineExceeded`` (Exception). Wird vor JEDER
  Quelle der Kette geprueft (auch vor der ersten), ``monotonic() >= deadline_at``.
  Eine laufende Quelle wird nicht abgebrochen. Nach Abbruch: nichts im Cache.
- ``services.trip_alert.RADAR_RUN_DEADLINE_SECONDS`` (45.0).

Kein Mock-Theater: echte ``RadarNowcastService``-Instanz mit echtem
``RadarNowcastCacheService``; die Quellenschritte (``_fetch_*``, die
NETZ-Grenze) werden auf der Instanz durch echte Funktionen ersetzt, die
wirklich Zeit verbrauchen (``time.sleep``) und Aufrufe zaehlen. Das
Konvektions-Sidecar (Open-Meteo) liegt innerhalb dieser Schritte und wird
damit mit ersetzt — kein Netz (``--disable-socket``).
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import pytest

from providers import geosphere
from services import radar_service as radar_service_mod
from services import trip_alert
from services.radar_cache import (
    RadarNowcastCacheService,
    get_shared_radar_cache,
    reset_shared_radar_cache_for_tests,
)
from services.radar_service import RadarNowcastService

# Tirol: liegt zugleich in RADOLAN- und INCA-Bereich → mehrere Quellen.
LAT, LON = 47.3, 11.4

# Go-Wartebudget der Radar-Jobs (internal/scheduler/scheduler.go, budgetsFor).
GO_RADAR_WAIT_BUDGET_S = 240
GO_RADAR_TAKT_S = 300

SOURCE_METHODS = (
    "_fetch_brightsky",
    "_fetch_geosphere_inca",
    "_fetch_corsica_arome_fr",
    "_fetch_italy_arpae",
    "_fetch_arome_france_hd",
    "_fetch_icon_d2",
    "_fetch_openmeteo_minutely15",
)

_WITHIN = {
    "_fetch_brightsky": radar_service_mod._within_radolan,
    "_fetch_geosphere_inca": radar_service_mod._within_inca,
    "_fetch_corsica_arome_fr": radar_service_mod._within_corsica,
    "_fetch_italy_arpae": radar_service_mod._within_italy_radar,
    "_fetch_arome_france_hd": radar_service_mod._within_arome_france,
    "_fetch_icon_d2": radar_service_mod._within_icon_d2,
}


def _service_mit_zeitverbrauchenden_quellen(
    monkeypatch: pytest.MonkeyPatch, *, sleep_s: float,
):
    """Echte Instanz; jeder Quellenschritt schlaeft ``sleep_s`` real, zaehlt
    seine Aufrufe (Reihenfolge in ``calls``) und liefert keine Frames."""
    cache = RadarNowcastCacheService()
    svc = RadarNowcastService(cache=cache)
    calls: list[str] = []

    def _make(name: str):
        def _step(lat, lon, elevation_m=None):
            calls.append(name)
            time.sleep(sleep_s)
            return []
        return _step

    for name in SOURCE_METHODS:
        monkeypatch.setattr(svc, name, _make(name))
    return svc, cache, calls


def _erwartete_kettenfolge(lat: float, lon: float) -> list[str]:
    """Quellenfolge der Standardkette, AUS DEN ``_within_*``-Pruefungen
    abgeleitet (nicht hartkodiert): alle zustaendigen Quellen, dann der
    Open-Meteo-Abschluss ``_fetch_openmeteo_minutely15``."""
    folge = [n for n in SOURCE_METHODS[:-1] if _WITHIN[n](lat, lon)]
    return folge + ["_fetch_openmeteo_minutely15"]


# ---------------------------------------------------------------------------
# AC-3 (Python-Seite) — Ungleichungskette aus den ECHTEN Konstanten.
# ---------------------------------------------------------------------------

def test_radar_zeitgrenze_unter_go_wartebudget():
    """AC-3: Zeitgrenze + laengster Einzelschritt (INCA 180 s + Sidecar 8 s)
    < Go-Wartebudget 240 s; Cache-TTL <= Takt - Zeitgrenze.

    RED heute: ``RADAR_RUN_DEADLINE_SECONDS`` existiert nicht; TTL ist 300.
    Zweiseitig verankert: das Go-Gegenstueck prueft Wait <= Run,
    Run + 10 s < Cron-Abstand, Cap = 2 x Abstand
    (``radar_budget_per_alarmart_test.go``)."""
    deadline = getattr(trip_alert, "RADAR_RUN_DEADLINE_SECONDS", None)
    assert deadline is not None, "trip_alert.RADAR_RUN_DEADLINE_SECONDS fehlt"
    laengster_schritt = geosphere.FETCH_DEADLINE_SECONDS + radar_service_mod.HTTPX_TIMEOUT
    assert deadline + laengster_schritt < GO_RADAR_WAIT_BUDGET_S, (
        f"{deadline} + {laengster_schritt} muss < {GO_RADAR_WAIT_BUDGET_S} sein "
        f"(ADR-0038: Python-Grenze strikt unter Go-Wartezeit, kein Null-Puffer)"
    )



def test_radar_cache_ttl_hoechstens_takt_minus_zeitgrenze():
    """AC-3 (TTL-Teil, eigener Test, damit er aus eigenem Grund rot wird):
    TTL <= Takt - Zeitgrenze, damit ein im Lauf N geholter Eintrag im Lauf N+1
    nicht aelter als TTL ausgeliefert wird. Zeitgrenze = 45 s laut Spec
    (Fallback, falls die Konstante noch fehlt). RED heute: TTL 300."""
    deadline = getattr(trip_alert, "RADAR_RUN_DEADLINE_SECONDS", 45.0)
    # VERHALTENSBASIERT: ein Eintrag, der aelter ist
    # als (Takt - Zeitgrenze), darf nicht mehr ausgeliefert werden.
    reset_shared_radar_cache_for_tests()
    try:
        cache = get_shared_radar_cache()
        t0 = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)
        from providers.brightsky import RadarFrame

        frame = RadarFrame(timestamp=t0, precip_mm_h=1.0)
        cache.put(LAT, LON, "r", [frame], "radar", now=t0)
        grenzalter = GO_RADAR_TAKT_S - deadline
        spaeter = t0 + timedelta(seconds=grenzalter + 0.5)
        assert cache.get(LAT, LON, "r", now=spaeter) is None, (
            f"Eintrag mit Alter {grenzalter + 0.5} s darf nicht mehr bedient werden "
            f"(TTL muss <= Takt - Zeitgrenze = {grenzalter} s sein)"
        )
    finally:
        reset_shared_radar_cache_for_tests()


# ---------------------------------------------------------------------------
# AC-4 — Grenze wird VOR JEDER QUELLE geprueft.
# ---------------------------------------------------------------------------

def test_radar_kette_prueft_grenze_vor_jeder_quelle(monkeypatch):
    """AC-4: Given eine echte Instanz, deren Schritte real Zeit verbrauchen,
    Koordinate in mehreren Quellenbereichen, erste Quelle liefert nichts /
    When ``get_nowcast`` mit ``deadline_at`` laeuft und die Grenze nach der
    ersten Quelle abgelaufen ist / Then beginnt KEINE weitere Quelle
    (Zaehler Folgequellen == 0), ``RadarDeadlineExceeded`` wird ausgeloest,
    der Cache bleibt leer.

    Mutation „Pruefung nur vor get_nowcast" laesst INCA laufen ⇒ rot.
    RED heute: ``get_nowcast`` kennt kein ``deadline_at`` (TypeError),
    ``RadarDeadlineExceeded`` existiert nicht.
    """
    # Import am Testanfang: ein ImportError hier ist der RED-Grund dieses
    # Tests, nicht ein stilles Verschlucken in der Kette.
    from services.radar_service import RadarDeadlineExceeded

    svc, cache, calls = _service_mit_zeitverbrauchenden_quellen(monkeypatch, sleep_s=0.3)
    reset_shared_radar_cache_for_tests()
    deadline_at = time.monotonic() + 0.15  # läuft WAEHREND der ersten Quelle ab

    with pytest.raises(RadarDeadlineExceeded):
        svc.get_nowcast(LAT, LON, deadline_at=deadline_at)

    assert calls == ["_fetch_brightsky"], (
        f"Nach Ablauf der Grenze darf keine Folgequelle beginnen; Aufrufe: {calls!r}"
    )
    region = radar_service_mod._region_bucket(LAT, LON)
    assert cache.get(LAT, LON, region, now=datetime.now(timezone.utc)) is None, (
        "Eine abgebrochene Kette darf nichts in den Cache schreiben"
    )


def test_radar_kette_prueft_grenze_auch_vor_der_ersten_quelle(monkeypatch):
    """AC-4 („auch vor der ersten"): ist die Grenze beim Eintritt schon
    abgelaufen, beginnt gar keine Quelle."""
    from services.radar_service import RadarDeadlineExceeded

    svc, _cache, calls = _service_mit_zeitverbrauchenden_quellen(monkeypatch, sleep_s=0.05)

    with pytest.raises(RadarDeadlineExceeded):
        svc.get_nowcast(LAT, LON, deadline_at=time.monotonic() - 1.0)

    assert calls == [], f"Keine Quelle darf beginnen, Aufrufe: {calls!r}"


def test_radar_kette_ohne_deadline_unveraendert_gegenprobe(monkeypatch):
    """AC-4 Default-Gegenprobe (Waechter, GRUEN erwartet): ohne ``deadline_at``
    werden dieselben Quellen wie bisher der Reihe nach versucht (Briefing,
    ``/jetzt`` & Co. bleiben unveraendert). Die erwartete Folge wird aus den
    ``_within_*``-Pruefungen abgeleitet."""
    svc, _cache, calls = _service_mit_zeitverbrauchenden_quellen(monkeypatch, sleep_s=0.05)
    reset_shared_radar_cache_for_tests()

    result = svc.get_nowcast(LAT, LON)

    assert calls == _erwartete_kettenfolge(LAT, LON), calls
    assert result.data_unavailable is True or result.onset_minutes is None
