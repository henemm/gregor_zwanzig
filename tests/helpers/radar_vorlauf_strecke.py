"""Gemeinsamer Aufbau der Vorlauf-Tests (Issue #2261 Teil A, A-1).

SPEC: docs/specs/modules/feat_2261_a1_radar_vorlauf.md (AC-1..AC-4, AC-12)

Was hier gebaut wird, ist ein ECHTER `check_radar_alerts()`-Lauf ueber die
`AlarmPruefstrecke` (#2050 S1). Gestellt ist nur die Radar-Quelle: eine echte
`RadarNowcastService`-Unterklasse, die je MESSPUNKT-INDEX ein Ergebnis liefert
(kein `Mock()`, kein `patch()`).

Geometrie (analytisch nachrechenbar, unabhaengig vom Pruefling):

* Reykjavik (`TRIP_LAT`/`TRIP_LON`, ganzjaehrig UTC+0): Ortszeit == UTC, die
  HH:MM-Angaben der Etappe sind direkt gegen die gestellte Uhr lesbar.
* Die Etappe laeuft exakt NACH NORDEN (Meridian = Grosskreis): Streckenanteil
  und Breitengrad sind streng linear, `haversine_km` vom Startpunkt ist exakt
  die Streckenkilometrierung.
* Gespeichert wird ueber den VERKUERZTEN `nowcast_gate_fixtures.save_trip()`
  (kein Compute-on-Save, #802) — die Ankunftszeiten bleiben die gestellten.

Daraus folgen ohne Pruefling-Code (Spec, Implementation Details 3):

* Messzeitpunkt `at = jetzt + 27` (`RADAR_MEASURE_OFFSET_MIN`).
* Erster Messpunkt beim Zeitanteil `f = (at - start) / (ende - start)`
  (geklemmt auf [0, 1]); Reststrecke `rest = (1 - f) * km`.
* Punkte im Abstand 2 km, hoechstens 6, unter 2 km Reststrecke genau einer.
* Durchgangszeit `p_k = t0 + (2k / rest) * (ende - t0)`, `t0 = max(at, start)`.
* Aufenthaltsfenster-Ende `E_k = p_{k+1} + 30`, am letzten Punkt offen.

Pfadregel #1409: keine Pfadaufloesung — dieser Helfer liest nichts aus dem
Repo, nur die isolierte Datenwurzel der Testsitzung.
"""
from __future__ import annotations

import dataclasses
import math
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from freezegun import freeze_time

from services.radar_service import (
    INTENSITY_DRY, INTENSITY_MODERATE, NowcastResult, RadarNowcastService,
)
from utils.geo import haversine_km

from tests.helpers.alarm_pruefstrecke import AlarmPruefstrecke
from tests.helpers.nowcast_gate_fixtures import (
    TRIP_LAT, TRIP_LON, clean_uid, make_trip, save_trip, settings_email_only,
    write_user_tier,
)

# Mittags, Reykjavik (UTC+0): weit weg von jeder Tagesgrenze.
AT = datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc)

# Spec-Werte als LITERALE des Tests (nicht aus dem Pruefling gelesen):
MESS_OFFSET_MIN = 27       # RADAR_MEASURE_OFFSET_MIN
TOLERANZ_MIN = 30          # RADAR_PASSAGE_TOLERANCE_MIN
PUNKTABSTAND_KM = 2.0      # RADAR_ZONE_POINT_SPACING_KM
MAX_PUNKTE = 6             # RADAR_ZONE_MAX_POINTS

_EARTH_KM = 6371.0088      # == utils.geo._EARTH_KM (gegengeprueft per haversine_km)
_KM_PRO_GRAD = math.pi / 180.0 * _EARTH_KM


def _hhmm(s: str) -> datetime:
    h, m = (int(x) for x in s.split(":"))
    return AT.replace(hour=h, minute=m)


@dataclass(frozen=True)
class Etappe:
    """Ein-Segment-Etappe nach Norden; `start`/`ende` in Ortszeit (== UTC)."""

    start: str
    ende: str
    km: float

    @property
    def start_dt(self) -> datetime:
        return _hhmm(self.start)

    @property
    def ende_dt(self) -> datetime:
        return _hhmm(self.ende)

    def _mess_at(self, jetzt: datetime) -> datetime:
        return jetzt + timedelta(minutes=MESS_OFFSET_MIN)

    def _anteil(self, jetzt: datetime) -> float:
        span = (self.ende_dt - self.start_dt).total_seconds()
        f = (self._mess_at(jetzt) - self.start_dt).total_seconds() / span
        return max(0.0, min(1.0, f))

    def rest_km(self, jetzt: datetime = AT) -> float:
        return (1.0 - self._anteil(jetzt)) * self.km

    def punkte_km(self, jetzt: datetime = AT) -> list[float]:
        """Soll-Kilometrierung der Messpunkte ab Etappenstart."""
        d0 = self._anteil(jetzt) * self.km
        rest = self.rest_km(jetzt)
        if rest < PUNKTABSTAND_KM:
            return [d0]
        n = min(MAX_PUNKTE, int(rest // PUNKTABSTAND_KM) + 1)
        return [d0 + k * PUNKTABSTAND_KM for k in range(n)]

    def durchgang(self, jetzt: datetime = AT) -> list[datetime]:
        """Soll-Durchgangszeit p_k je Messpunkt (lineare Interpolation)."""
        t0 = max(self._mess_at(jetzt), self.start_dt)
        rest = self.rest_km(jetzt)
        punkte = self.punkte_km(jetzt)
        if len(punkte) == 1:
            return [t0]
        return [
            t0 + (k * PUNKTABSTAND_KM / rest) * (self.ende_dt - t0)
            for k in range(len(punkte))
        ]

    def fenster_ende_min(self, jetzt: datetime = AT) -> list[Optional[float]]:
        """E_k in Minuten ab `jetzt`; `None` = offen (letzter Punkt)."""
        p = self.durchgang(jetzt)
        out: list[Optional[float]] = []
        for k in range(len(p)):
            if k + 1 < len(p):
                out.append((p[k + 1] - jetzt).total_seconds() / 60 + TOLERANZ_MIN)
            else:
                out.append(None)
        return out


# Etappe 11:00-14:00, 24 km: sechs Punkte, Durchgang jetzt+27+15k,
# Fenster-Enden 72/87/102/117/132/offen.
ETAPPE_MITTEL = Etappe("11:00", "14:00", 24.0)
# Ganztags-Etappe, 12 km: drei Punkte, Durchgang alle ~4 h — jeder Beginn im
# Horizont liegt an Punkt 0 im Aufenthaltsfenster.
ETAPPE_GANZTAGS = Etappe("00:00", "23:59", 12.0)
# Kurz vor dem Ziel: 11:50-12:40, 60 km (schnell) -> sechs Punkte im Abstand
# von ~1,7 Min (kleines p_1 - p_0, AC-4).
ETAPPE_SCHNELL = Etappe("11:50", "12:40", 60.0)
# Reststrecke < 2 km: genau EIN Messpunkt (Einzelpunkt-Fall).
ETAPPE_KURZ = Etappe("11:00", "14:00", 3.0)


def uid(tag: str) -> str:
    return f"tdd-2261-a1-{tag}-{uuid.uuid4().hex[:6]}"


def baue_trip(user_id: str, etappe: Etappe, *, at: datetime = AT):
    """Nutzer (Tier premium, kein Tageslimit) + Trip mit der Etappe auf der
    Datenwurzel von `user_id` — unter der gestellten Uhr."""
    with freeze_time(at):
        write_user_tier(user_id, "premium")
        trip = make_trip(
            f"trip-{user_id}", arrival_start=etappe.start, arrival_end=etappe.ende,
        )
        wps = trip.stages[0].waypoints
        wps[0] = dataclasses.replace(wps[0], lat=TRIP_LAT, lon=TRIP_LON)
        wps[1] = dataclasses.replace(
            wps[1], lat=TRIP_LAT + etappe.km / _KM_PRO_GRAD, lon=TRIP_LON,
        )
        gemessen = haversine_km(wps[0].lat, wps[0].lon, wps[1].lat, wps[1].lon)
        assert abs(gemessen - etappe.km) < 0.01, (
            f"Testvoraussetzung: Etappe muss {etappe.km} km messen, misst {gemessen:.4f}"
        )
        save_trip(trip, user_id)
    return trip


def km_ab_start(lat: float, lon: float) -> float:
    return haversine_km(TRIP_LAT, TRIP_LON, lat, lon)


def nass(
    onset: Optional[int], *, laufend: bool = False, konvektiv: bool = False,
    menge: Optional[float] = None,
) -> NowcastResult:
    """Echtes nasses `NowcastResult`. Menge realistisch: das 60-Min-Fenster ab
    jetzt ist bei spaetem Beginn (>= 60) trocken (0,0)."""
    if menge is None:
        menge = 0.0 if (onset is not None and onset >= 60) else 3.0
    return NowcastResult(
        onset_minutes=onset, intensity_label=INTENSITY_MODERATE, source="radar",
        window_precip_mm=menge,
        event_end_minutes=(onset + 45) if onset is not None else 40,
        is_convective=konvektiv, already_running=laufend,
    )


def trocken() -> NowcastResult:
    return NowcastResult(onset_minutes=None, intensity_label=INTENSITY_DRY, source="radar")


class PunktRadar(RadarNowcastService):
    """Echte `RadarNowcastService`-Unterklasse am DI-Seam von
    `TripAlertService`. Ergebnis je Messpunkt-INDEX; der Index wird aus der
    KOORDINATE bestimmt (naechster Soll-Punkt, < 0,3 km), nicht aus der
    Aufrufreihenfolge — die Implementierung darf Abrufe umordnen. Ohne
    Soll-Punkte (`soll_km=None`) wird nur mitgeschrieben."""

    def __init__(self, soll_km: Optional[list[float]], script: Optional[dict] = None) -> None:
        super().__init__()
        self._soll = soll_km
        self.script = dict(script or {})
        self.aufrufe: list[dict] = []

    def get_nowcast(self, lat, lon, elevation_m=None, priority="user_briefing", user_id=None):
        km = km_ab_start(lat, lon)
        idx = None
        if self._soll is not None:
            abst = [abs(km - s) for s in self._soll]
            naechster = min(range(len(abst)), key=abst.__getitem__)
            # Kein `assert` HIER: `check_radar_alerts()` faengt Ausnahmen des
            # Abrufs fail-soft ab, ein Assert ginge still unter. Ein Abruf
            # neben jedem Soll-Punkt wird mit `idx=None` mitgeschrieben und
            # von `szenario_lauf()` laut als Testvoraussetzung gemeldet.
            idx = naechster if abst[naechster] < 0.3 else None
        self.aufrufe.append({"idx": idx, "lat": lat, "lon": lon, "km": km})
        ergebnis = self.script.get(idx, trocken()) if idx is not None else trocken()
        if isinstance(ergebnis, Exception):
            raise ergebnis
        return ergebnis

    @property
    def abgerufen(self) -> list:
        return [a["idx"] for a in self.aufrufe]


def lauf(user_id: str, trip, radar, *, at: datetime = AT):
    """Ein echter Radar-Prueflauf ueber die `AlarmPruefstrecke`."""
    strecke = AlarmPruefstrecke(user_id=user_id, settings=settings_email_only())
    return strecke.lauf(at=at, zweig="radar", trip=trip, radar_service=radar)


def szenario_lauf(tag: str, etappe: Etappe, script: dict, *, at: datetime = AT):
    """Nutzer anlegen, Trip bauen, einen Lauf fahren, aufraeumen.

    Liefert `(lauf, radar, user_id)`. Prueft als laute Testvoraussetzung, dass
    genau die analytisch erwartete Zahl Messpunkte abgerufen wurde — sonst
    stimmte die Zuordnung Index -> Ort nicht und jedes Ergebnis waere
    zufaellig."""
    u = uid(tag)
    clean_uid(u)
    try:
        trip = baue_trip(u, etappe, at=at)
        soll = etappe.punkte_km(at)
        radar = PunktRadar(soll, script)
        ergebnis = lauf(u, trip, radar, at=at)
        assert sorted(radar.abgerufen, key=lambda i: -1 if i is None else i) == list(range(len(soll))), (
            f"Testvoraussetzung: erwartet Abrufe an den Punkten "
            f"{list(range(len(soll)))} (Soll-km {[round(s, 2) for s in soll]}), "
            f"abgerufen {radar.abgerufen} bei km "
            f"{[round(a['km'], 2) for a in radar.aufrufe]}"
        )
        return ergebnis, radar, u
    finally:
        clean_uid(u)
