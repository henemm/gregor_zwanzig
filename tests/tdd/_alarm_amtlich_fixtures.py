"""Gemeinsame Fixtures für Issue #2422 S4 — amtliche-Warnungen-Kette.

Kein Test-Modul (führender Unterstrich → pytest sammelt es nicht ein), nur
echte Datenmodell-Objekte und zwei Test-Nähte:

1. `services.official_alerts.get_official_alerts_for_location` (Modul-Ebene)
   — ersetzt den HTTP-Abruf einer amtlichen Quelle durch eine feste Liste.
   `check_official_alert_triggers()` importiert die Funktion LOKAL bei jedem
   Aufruf (`from services.official_alerts import get_official_alerts_for_location`,
   trip_alert.py:2582) — ein Patch auf dem Quellmodul wirkt deshalb bei jedem
   Aufruf neu, unabhängig davon, wie oft/wann `TripAlertService` gebaut wird.
2. `TripAlertService._get_cached_weather` (Klassen-Ebene) — ersetzt den
   Snapshot-Datei-Zugriff durch synthetische Routen-Geometrie. Die Methode
   wird von ZWEI Stellen mit unterschiedlichem `tagesgleicher_anker_noetig`
   aufgerufen: `check_all_trips()` (True, Zeile 922) und
   `check_official_alert_triggers()` selbst (False, Zeile 2571) — der Fake
   unterscheidet beide Fälle, weil AC-5 (Sammellauf) exakt auf der
   Kombination "kein tagesgleicher Wetter-Anker, aber volle Routen-
   Geometrie" aufbaut (sonst würde der Δ-Zweig fälschlich mitprüfen bzw. der
   amtliche Zweig faende gar keine Route).

Kein `Mock()`/`patch()`/`MagicMock` — beide Nähte sind echte, deterministische
Ersatzfunktionen an klar benannten DI-Seams (Vorbild `radar_service=` in
`alarm_pruefstrecke.py`).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from app.loader import load_trip
from app.models import (
    ForecastMeta, GPXPoint, NormalizedTimeseries, Provider,
    SegmentWeatherData, SegmentWeatherSummary, TripSegment,
)
from services import official_alerts as official_alerts_mod
from services.official_alerts.models import OfficialAlert
from services.trip_alert import TripAlertService

GOLDEN_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "alarm_kette"

#: Route-Startpunkt aller amtlichen Golden-Fixtures (Innsbruck, wie die
#: Abweichungs-/Radar-Fixtures — ein gemeinsamer Ort hält die Tests klein).
LAT, LON = 47.2692, 11.4041


def amtlich_dict(name: str, *, heute: Optional[datetime] = None) -> dict:
    """Rohes JSON-Dict einer `golden_amtlich_fall*`-Fixture. `heute` (falls
    gesetzt) überschreibt `stages[0].date` — nötig für AC-5, wo der reguläre
    Sammellauf abgelaufene Trips überspringt (trip_alert.py:917), unabhängig
    vom hier geprüften Vorab-Filter."""
    data = json.loads((GOLDEN_DIR / f"{name}.json").read_text())
    if heute is not None:
        data["stages"][0]["date"] = heute.date().isoformat()
    return data


def amtlich_trip(name: str, uid: str, *, heute: Optional[datetime] = None, **overrides):
    """Golden-Amtlich-Fixture ECHT über `app.loader.load_trip()` geladen,
    danach werden nur die je Test variablen Felder gesetzt (reale
    Dataclass-Attribute)."""
    d = amtlich_dict(name, heute=heute)
    d["id"] = f"trip-{uid}"
    trip = load_trip(d, user_id=uid)
    for feld, wert in overrides.items():
        setattr(trip, feld, wert)
    return trip


def amtliche_warnung(level: int, *, von: datetime, bis: datetime, source: str = "tdd-2422s4") -> OfficialAlert:
    return OfficialAlert(
        source=source, hazard="thunderstorm", level=level,
        label="Gewitterwarnung", valid_from=von, valid_to=bis,
    )


def segmentgeometrie(at: datetime) -> list[SegmentWeatherData]:
    """EIN Segment, dessen Zeitfenster `at` umschließt — die "Routen-
    Geometrie", die `check_official_alert_triggers()` für die Segment-/
    Zeitfenster-Zuordnung braucht (trip_alert.py:2600-2618). Der
    Wetter-Inhalt selbst (`aggregated`) bleibt leer — er wird auf diesem Pfad
    nicht gelesen."""
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=LAT, lon=LON, elevation_m=600, distance_from_start_km=0.0),
        end_point=GPXPoint(lat=LAT + 0.05, lon=LON + 0.05, elevation_m=900, distance_from_start_km=8.0),
        start_time=at - timedelta(hours=2), end_time=at + timedelta(hours=6),
        duration_hours=8.0, distance_km=8.0, ascent_m=300, descent_m=0,
    )
    return [SegmentWeatherData(
        segment=seg,
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=1.0), data=[],
        ),
        aggregated=SegmentWeatherSummary(),
        fetched_at=at, provider="openmeteo",
    )]


def stelle_amtliche_quelle(monkeypatch, alerts: list[OfficialAlert]) -> None:
    """Ersetzt den Provider-Abruf durch eine feste Liste — kein Netz."""
    def _fake(lat, lon, *, window_start, window_end, now):
        return list(alerts)
    monkeypatch.setattr(official_alerts_mod, "get_official_alerts_for_location", _fake)


def stelle_cache_fuer_amtliche_kette(monkeypatch, *, route_geometrie: list) -> None:
    """Klassen-Ebene (wirkt auf JEDE `TripAlertService`-Instanz, auch die
    von `check_all_trips()`/`alarm_pruefstrecke.lauf()` intern frisch
    gebaute): `tagesgleicher_anker_noetig=True` (Sammellauf-Δ-Zweig) liefert
    bewusst KEINEN Anker (`[]`) — der Bug-Fall (AC-5) hat keine aktive
    Wetter-Delta-Regel, der Δ-Zweig darf gar nicht erst greifen. Der amtliche
    Zweig selbst ruft mit `tagesgleicher_anker_noetig=False` auf und bekommt
    die echte Routen-Geometrie."""
    def _fake(self, trip, *, tagesgleicher_anker_noetig, now_utc=None):
        if tagesgleicher_anker_noetig:
            return []
        return list(route_geometrie)
    monkeypatch.setattr(TripAlertService, "_get_cached_weather", _fake)
