"""TDD RED — Issue #2050 Scheibe S4b: Messluecken der Radar-Ausdehnung landen
im Alarmprotokoll (Anforderung E-1).

SPEC: docs/specs/modules/feat_2050_s4b_messluecken_protokoll.md — AC-1..AC-11
(AC-12 ist ein reiner Regressionslauf der beiden #2051-S2a-Dateien und braucht
keinen eigenen Test).

RED-Grund: das Protokollfeld `measurement_gaps` existiert nicht. Faellt einer
der bis zu sechs Messpunkte aus, verschwindet er in `derive_rain_zones`
kommentarlos — eine Ausdehnung aus vier von sechs Punkten ist nachtraeglich
nicht von einer vollstaendig vermessenen zu unterscheiden.

Mock-frei: jeder Lauf geht ueber die ECHTE Ausloeseentscheidung
(`TripAlertService.check_radar_alerts()`) mit einer echten
`RadarNowcastService`-Unterklasse am DI-Seam (Muster `_ZonenRadar`,
`test_regen_ausdehnung_textstellen.py`) und einer echten `alert_log.json`
unter `get_data_dir(user_id)`. Gesteuert wird ausschliesslich, WELCHES
`NowcastResult` ein Punkt bekommt.

Die erwarteten km-Werte werden aus den TATSAECHLICH abgefragten Koordinaten
abgeleitet (Geometrie, `haversine_km` ab WP0), nicht als Literal gesetzt —
sonst bliebe die Bildungsstelle der km-Lage unbewacht.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import NamedTuple

from freezegun import freeze_time

from app.config import Settings
from app.loader import get_briefings_dir, get_data_dir
from app.models import (
    ForecastMeta, NormalizedTimeseries, Provider, SegmentWeatherData,
    SegmentWeatherSummary,
)
from services.radar_service import NowcastResult
from services.trip_alert import TripAlertService
from utils.geo import haversine_km

from tests.helpers.arrival_window_fixtures import stage_date
from tests.tdd.test_issue_1070_daily_alert_limit import _segment
from tests.tdd.test_regen_ausdehnung_textstellen import (
    _UHR_TIROL,
    _ZONEN_LAT0,
    _ZONEN_LAT1,
    _ZONEN_LON0,
    _ZONEN_LON1,
    _ZonenRadar,
    _nass_spannen,
)

# Nord-Strecke wie in `test_regen_ausdehnung_textstellen.py`: bei Zeitanteil
# 87/360 (`_at` = jetzt + RADAR_ONSET_THRESHOLD_MIN//2) bleiben von den ~24 km
# gut 18 km Reststrecke und damit die vollen sechs Messpunkte (Deckel).
# Der Umrechnungsfaktor wird aus DIESER Strecke abgeleitet, nicht geraten —
# so laesst sich eine kuerzere Etappe (AC-1: drei Punkte) davon ableiten.
_GRAD_PRO_KM = (_ZONEN_LAT1 - _ZONEN_LAT0) / haversine_km(
    _ZONEN_LAT0, _ZONEN_LON0, _ZONEN_LAT1, _ZONEN_LON1,
)

# Etappenlaenge fuer den Drei-Punkte-Aufbau (AC-1): Reststrecke ist 0,7583 der
# Laenge, drei Punkte entstehen bei Reststrecke in [4, 6) km — 6,6 km liegt
# mittig in diesem Fenster. Die Punktzahl wird trotzdem in jedem Test als
# Testvoraussetzung geprueft.
_DREI_PUNKTE_KM = 6.6

# Die BESTEHENDEN E-1-Groessen des Radar-Zweigs (#2050 S6), die ein
# Fehlschlag der neuen Luecken-Ableitung nicht mitreissen darf (AC-9).
# Bewusst namentlich aufgezaehlt und NICHT aus `alert_log._E1_FIELD_TYPES`
# abgeleitet: eine aus dem Pruefling gezogene Liste hoerte still auf, eine
# Groesse zu bewachen, sobald sie dort verschwindet.
# `reference_at` ist dabei: der AC-9-Aufbau legt eigens einen
# Briefing-Schnappschuss an, damit die Groesse ueberhaupt entsteht (ohne ihn
# bliebe sie `None` und die Zusicherung waere fuer sie leer).
_E1_GROESSEN = (
    "lead_time_minutes", "event_at", "event_end_at", "measurement_point",
    "reference_at", "source",
)

# Erhebungszeitpunkt der Vergleichsbasis im AC-9-Aufbau: eine Stunde vor der
# gestellten Uhr. EINE Variable — sie speist den geschriebenen Schnappschuss
# und (ueber den Referenzlauf) die Erwartung, damit `reference_at` am WERT
# haengt und nicht nur an der Anwesenheit des Schluessels.
_VERGLEICHSBASIS_AT = datetime.fromisoformat(_UHR_TIROL).astimezone(
    timezone.utc
) - timedelta(hours=1)


class _LueckenRadar(_ZonenRadar):
    """Dieselbe Steuerungsidee wie `_ZonenRadar` — echte
    `RadarNowcastService`-Unterklasse am DI-Seam von `TripAlertService`, echte
    `NowcastResult`-Objekte, kein Mock —, nur mit MEHREREN gleichzeitigen
    Luecken (AC-2 braucht alle fuenf Folgepunkte auf einmal).

    `luecken` bildet Index -> Felder des Leerergebnisses
    (`{"throttled": True}` / `{"data_unavailable": True}`), `ausnahmen` sind
    die Indizes, deren Abruf wirft, `trockene` die ECHT trockenen Punkte
    (Ergebnis vorhanden, nur kein Regen).
    """

    def __init__(
        self,
        *,
        luecken: dict[int, dict] | None = None,
        ausnahmen: tuple[int, ...] = (),
        trockene: tuple[int, ...] = (),
    ) -> None:
        super().__init__()
        self._luecken = dict(luecken or {})
        self._ausnahmen = set(ausnahmen)
        self._trockene = set(trockene)

    @property
    def ausgefallene_indizes(self) -> list[int]:
        """Die Indizes, an denen dieser Aufbau eine LUECKE erzeugt — aus der
        Konfiguration abgeleitet, damit kein Test dieselbe Zahl zweimal
        hinschreibt."""
        return sorted(set(self._luecken) | self._ausnahmen)

    def get_nowcast(self, lat, lon, elevation_m=None, priority="user_briefing"):
        i = len(self.aufrufe)
        self.aufrufe.append((lat, lon))
        if i in self._ausnahmen:
            raise RuntimeError(
                f"Nowcast-Abruf fuer Zonenpunkt {i} absichtlich fehlgeschlagen"
            )
        if i in self._luecken:
            return NowcastResult(
                onset_minutes=None, intensity_label="Kein Regen", source="radar",
                **self._luecken[i],
            )
        if i in self._trockene:
            return NowcastResult(
                onset_minutes=None, intensity_label="Kein Regen", source="radar",
            )
        return NowcastResult(
            onset_minutes=10, intensity_label="Mäßiger Regen", source="radar",
            window_precip_mm=3.0, event_end_minutes=40,
        )


class _Lauf(NamedTuple):
    sent: int
    body: str
    spannen: list[str]
    entries: list[dict]
    not_delivered: list[dict]
    km: list[float]
    uid: str
    trip_id: str


def _uid(tag: str) -> str:
    return f"tdd-2050-s4b-{tag}-{uuid.uuid4().hex[:8]}"


def _endpunkt(strecke_km: float | None) -> tuple[float, float]:
    if strecke_km is None:
        return _ZONEN_LAT1, _ZONEN_LON1
    return _ZONEN_LAT0 + strecke_km * _GRAD_PRO_KM, _ZONEN_LON0


def _protokoll(uid: str) -> dict:
    pfad = get_data_dir(uid) / "alert_log.json"
    return json.loads(pfad.read_text()) if pfad.exists() else {}


def _schreibe_vergleichsbasis(uid: str, trip_id: str, tag_datum, fetched_at) -> None:
    """Einen Briefing-Schnappschuss fuer den Tag anlegen, damit
    `reference_at` ueberhaupt entstehen kann (AC-9).

    Die Zeitreihe bleibt LEER: `_briefing_precip_for_onset()` liefert dann
    `None`, die Briefing-Unterdrueckung greift nicht und der Alarm laeuft
    durch — `reference_at` haengt allein am Vorhandensein des Schnappschusses
    (`snapshot[0].fetched_at`), nicht an einer angekuendigten Menge.
    """
    from services.weather_snapshot import WeatherSnapshotService

    WeatherSnapshotService(uid).save_dated(trip_id, tag_datum, [
        SegmentWeatherData(
            segment=_segment(1),
            timeseries=NormalizedTimeseries(
                meta=ForecastMeta(
                    provider=Provider.OPENMETEO, model="test", grid_res_km=1.0,
                ),
                data=[],
            ),
            aggregated=SegmentWeatherSummary(precip_sum_mm=0.0),
            fetched_at=fetched_at,
            provider="openmeteo",
        ),
    ])


def _lauf(
    radar: _ZonenRadar, *, tag: str = "lauf", uid: str | None = None,
    strecke_km: float | None = None, vergleichsbasis_at=None,
) -> _Lauf:
    """Ein echter `check_radar_alerts()`-Lauf (Muster `_zonen_lauf`,
    `test_regen_ausdehnung_textstellen.py`), zusaetzlich mit dem geschriebenen
    Alarmprotokoll des Nutzers.

    Der Trip wird als Datei geschrieben und vom Pruefling selbst geladen —
    dieselbe Strecke wie in Produktion. `km` haelt die Kilometrierung der
    TATSAECHLICH abgefragten Punkte, unabhaengig vom Pruefling ueber die
    Geometrie gerechnet (gerade Nord-Strecke, `distance_from_start_km` 0 am
    Startwegpunkt): ein Sollwert, den der Pruefling selbst liefert, prueft
    nichts.

    `vergleichsbasis_at` legt zusaetzlich einen Briefing-Schnappschuss mit
    diesem Erhebungszeitpunkt an (nur AC-9 braucht ihn, s.
    `_schreibe_vergleichsbasis`).
    """
    uid = uid or _uid(tag)
    lat1, lon1 = _endpunkt(strecke_km)
    with freeze_time(_UHR_TIROL):
        luftlinie = haversine_km(_ZONEN_LAT0, _ZONEN_LON0, lat1, lon1)
        trip_id = f"tdd-2050-s4b-trip-{uuid.uuid4().hex[:6]}"
        tag_datum = stage_date(_ZONEN_LAT0, _ZONEN_LON0)
        trips_dir = get_briefings_dir(uid)
        trips_dir.mkdir(parents=True, exist_ok=True)
        (trips_dir / f"{trip_id}.json").write_text(json.dumps({
            "id": trip_id, "name": "Messluecken Draht Trip",
            "stages": [{
                "id": "S1", "name": "Tag 1",
                "date": tag_datum.isoformat(),
                "waypoints": [
                    {
                        "id": "WP0", "name": "WP0",
                        "lat": _ZONEN_LAT0, "lon": _ZONEN_LON0,
                        "elevation_m": 1000.0, "arrival_calculated": "11:00",
                        "distance_from_start_km": 0.0,
                    },
                    {
                        "id": "WP1", "name": "WP1",
                        "lat": lat1, "lon": lon1,
                        "elevation_m": 1000.0, "arrival_calculated": "17:00",
                        "distance_from_start_km": round(luftlinie, 3),
                    },
                ],
            }],
            "report_config": {
                "trip_id": trip_id, "send_email": True, "send_telegram": False,
            },
        }))
        if vergleichsbasis_at is not None:
            _schreibe_vergleichsbasis(uid, trip_id, tag_datum, vergleichsbasis_at)

        captured: list[dict] = []
        svc = TripAlertService(
            throttle_hours=2, user_id=uid, radar_service=radar,
            settings=Settings(
                smtp_host="test.invalid", smtp_user="u", smtp_pass="p",
                mail_to="x@example.com",
            ),
            mail_sink=lambda subject, body: captured.append(
                {"subject": subject, "body": body}
            ),
        )
        svc.clear_radar_throttle(trip_id)
        sent = svc.check_radar_alerts()

    body = captured[0]["body"] if captured else ""
    protokoll = _protokoll(uid)
    return _Lauf(
        sent=sent, body=body, spannen=_nass_spannen(body),
        entries=protokoll.get("entries", []),
        not_delivered=protokoll.get("not_delivered", []),
        km=[
            haversine_km(_ZONEN_LAT0, _ZONEN_LON0, lat, lon)
            for lat, lon in radar.aufrufe
        ],
        uid=uid, trip_id=trip_id,
    )


def _versand_eintrag(lauf: _Lauf) -> dict:
    """Der Protokoll-Eintrag des ZUGESTELLTEN Alarms dieses Laufs."""
    treffer = [e for e in lauf.entries if e.get("entity_id") == lauf.trip_id]
    assert lauf.sent >= 1 and len(treffer) == 1, (
        f"Testvoraussetzung: der Lauf muss GENAU EINEN zugestellten "
        f"Protokoll-Eintrag erzeugt haben (sent={lauf.sent}, "
        f"entries={lauf.entries!r}, not_delivered={lauf.not_delivered!r})"
    )
    return treffer[0]


def _messluecken(lauf: _Lauf) -> dict:
    eintrag = _versand_eintrag(lauf)
    assert "measurement_gaps" in eintrag, (
        f"Der Protokoll-Eintrag muss `measurement_gaps` fuehren — sonst ist "
        f"nachtraeglich nicht erkennbar, aus wie vielen Messpunkten die "
        f"Ausdehnung stammt. Eintrag: {eintrag!r}"
    )
    return eintrag["measurement_gaps"]


def _erwartete_gap_km(lauf: _Lauf, indizes: list[int]) -> list[float]:
    """km-Lage der ausgefallenen Punkte, aus den Abruf-Koordinaten abgeleitet
    und auf eine Nachkommastelle gerundet (Spec: dieselbe Nachkommastelle wie
    die gemessene km-Spanne)."""
    werte = []
    for i in indizes:
        roh = lauf.km[i]
        # Die Rundung kippt bei einer halben Nachkommastelle (x,x5) — nur DORT
        # waere der Sollwert mehrdeutig. Die Geometrie des Tests wird ueber
        # diesen Abstand geprueft, nicht ueber die Naehe zum Zehntel selbst.
        assert abs((roh * 10) % 1 - 0.5) > 0.02, (
            f"Testvoraussetzung: {roh:.4f} km liegt zu dicht an der "
            f"Rundungsgrenze (x,x5) — der Sollwert waere nicht eindeutig."
        )
        werte.append(round(roh, 1))
    return werte


def _pruefe_luecken(
    lauf: _Lauf, radar: _LueckenRadar, *, punkte_erwartet: int,
) -> dict:
    """Die drei Zahlen gegen den Aufbau pruefen — alle drei ABGELEITET:
    `points_total` aus der Zahl der tatsaechlichen Abrufe, `points_measured`
    aus der Differenz zu den ausgefallenen Indizes, `gap_km` aus deren
    Koordinaten."""
    assert len(lauf.km) == punkte_erwartet, (
        f"Testvoraussetzung: {punkte_erwartet} Messpunkte erwartet (der "
        f"Aufbau haengt daran), gesehen {len(lauf.km)}"
    )
    # Sollwerte ZUERST (sie tragen eigene Testvoraussetzungen), erst danach
    # der Blick ins Protokoll — sonst bliebe eine untaugliche Geometrie hinter
    # dem fehlenden Feld verborgen.
    ausgefallen = radar.ausgefallene_indizes
    erwartete_km = _erwartete_gap_km(lauf, ausgefallen)
    luecken = _messluecken(lauf)

    assert luecken.get("points_total") == len(lauf.km), (
        f"`points_total` muss die Zahl der Messpunkte nennen "
        f"({len(lauf.km)}), war {luecken.get('points_total')!r}: {luecken!r}"
    )
    assert luecken.get("points_measured") == len(lauf.km) - len(ausgefallen), (
        f"`points_measured` muss die Punkte MIT verwertbarem Ergebnis nennen "
        f"({len(lauf.km)} - {len(ausgefallen)} = "
        f"{len(lauf.km) - len(ausgefallen)}), war "
        f"{luecken.get('points_measured')!r}: {luecken!r}"
    )
    assert luecken.get("gap_km") == erwartete_km, (
        f"`gap_km` muss die km-Lage JEDES ausgefallenen Punkts nennen "
        f"(Indizes {ausgefallen}, abgeleitet aus den Abruf-Koordinaten: "
        f"{[round(k, 3) for k in lauf.km]}), war {luecken.get('gap_km')!r}"
    )
    return luecken


# ---------------------------------------------------------------------------
# AC-1: nass — Luecke — nass, drei Zonenpunkte.
# ---------------------------------------------------------------------------

def test_luecke_in_der_mitte_haelt_zahl_und_km_lage_fest():
    """AC-1 GIVEN drei Zonenpunkte, der mittlere ausgefallen / WHEN der Alarm
    protokolliert wird / THEN nennt `measurement_gaps` Zahl UND km-Lage genau
    dieses Punkts.

    Geprueft werden die WERTE, nicht die Form: ein `gap_km` mit der km-Lage
    eines FALSCHEN Punkts (z.B. des ersten statt des mittleren) faellt hier
    durch, weil der Sollwert aus den Abruf-Koordinaten abgeleitet wird.
    """
    radar = _LueckenRadar(luecken={1: {"data_unavailable": True}})
    lauf = _lauf(radar, tag="ac1", strecke_km=_DREI_PUNKTE_KM)

    luecken = _pruefe_luecken(lauf, radar, punkte_erwartet=3)

    # Die Luecke liegt WEDER am ersten NOCH am letzten Punkt — sonst koennte
    # ein Pruefling, der schlicht den Streckenanfang oder das Streckenende
    # meldet, hier zufaellig richtig liegen.
    assert lauf.km[0] < luecken["gap_km"][0] < lauf.km[-1], (
        f"Testvoraussetzung: die gemeldete Luecke muss ZWISCHEN erstem und "
        f"letztem Messpunkt liegen ({[round(k, 3) for k in lauf.km]}), war "
        f"{luecken['gap_km']!r}"
    )


# ---------------------------------------------------------------------------
# AC-2 / AC-3: der Extremfall und sein echter Zwilling — nebeneinander, sonst
#              belegt AC-2 nichts.
# ---------------------------------------------------------------------------

def test_alle_folgepunkte_ausgefallen_ist_der_extremfall():
    """AC-2 GIVEN der ausloesende erste Messpunkt meldet Regen, alle fuenf
    Folgepunkte fallen aus / WHEN der Alarm protokolliert wird / THEN weist
    `measurement_gaps` `points_measured=1` und alle fuenf Folgepunkte als
    `gap_km` aus."""
    radar = _LueckenRadar(luecken={i: {"data_unavailable": True} for i in range(1, 6)})
    lauf = _lauf(radar, tag="ac2")

    luecken = _pruefe_luecken(lauf, radar, punkte_erwartet=6)

    assert luecken["points_measured"] == 1 and len(luecken["gap_km"]) == 5, (
        f"AC-2: genau EIN gemessener Punkt und FUENF Luecken erwartet, war "
        f"{luecken!r}"
    )


def test_echter_befund_ein_kilometer_ist_vom_extremfall_unterscheidbar():
    """AC-3 (Gegenprobe zu AC-2) GIVEN dieselbe Strecke, aber alle sechs
    Punkte liefern ein Ergebnis und nur der erste ist nass / WHEN der Alarm
    protokolliert wird / THEN zeigt `measurement_gaps`
    `points_total == points_measured` und eine LEERE `gap_km`-Liste.

    Beide Laeufe stehen hier NEBENEINANDER: die Zusicherung ist nicht "leere
    Liste", sondern "an den Zahlen unterscheidbar, obwohl der TEXT beide Male
    dieselbe Ausdehnungsangabe traegt". Ohne den Extremfall im selben Test
    waere die leere Liste ein Wert ohne Aussage.
    """
    echt = _LueckenRadar(trockene=(1, 2, 3, 4, 5))
    lauf_echt = _lauf(echt, tag="ac3-echt")
    extrem = _LueckenRadar(luecken={i: {"data_unavailable": True} for i in range(1, 6)})
    lauf_extrem = _lauf(extrem, tag="ac3-extrem")

    assert lauf_echt.spannen and lauf_echt.spannen == lauf_extrem.spannen, (
        f"Testvoraussetzung: beide Laeufe muessen DIESELBE Ausdehnungsangabe "
        f"im Text erzeugen — genau darum muss der Unterschied an den Zahlen "
        f"haengen. Echt: {lauf_echt.spannen!r}, Extremfall: "
        f"{lauf_extrem.spannen!r}"
    )

    luecken_echt = _pruefe_luecken(lauf_echt, echt, punkte_erwartet=6)
    luecken_extrem = _messluecken(lauf_extrem)

    assert luecken_echt["gap_km"] == [], (
        f"AC-3: eine vollstaendig vermessene Strecke hat keine Luecken, war "
        f"{luecken_echt!r}"
    )
    assert luecken_echt["points_total"] == luecken_echt["points_measured"], (
        f"AC-3: vollstaendig vermessen heisst points_total == points_measured, "
        f"war {luecken_echt!r}"
    )
    assert luecken_echt != luecken_extrem, (
        f"AC-3: der echte Ein-Kilometer-Befund und der Extremfall aus AC-2 "
        f"muessen sich im Protokoll UNTERSCHEIDEN — beide Male "
        f"{luecken_echt!r} bei identischem Text {lauf_echt.spannen!r} waere "
        f"genau die Ununterscheidbarkeit, die diese Scheibe beseitigt."
    )


# ---------------------------------------------------------------------------
# AC-4: das Feld entsteht IMMER, sobald die Mehrpunkt-Abfrage lief.
# ---------------------------------------------------------------------------

def test_luecken_feld_ist_auch_ohne_luecke_vorhanden():
    """AC-4 GIVEN ein Lauf ohne jeden Ausfall / WHEN der Alarm protokolliert
    wird / THEN ist `measurement_gaps` trotzdem vorhanden, mit leerer
    `gap_km`-Liste.

    Positivkontrolle im zweiten Lauf: derselbe Aufbau MIT einer Luecke muss
    eine gefuellte `gap_km`-Liste liefern — sonst waere die leere Liste oben
    trivial wahr (ein Pruefling, der die Liste nie fuellt, kaeme durch).
    """
    ohne = _LueckenRadar()
    lauf_ohne = _lauf(ohne, tag="ac4-ohne")
    luecken_ohne = _pruefe_luecken(lauf_ohne, ohne, punkte_erwartet=6)

    assert luecken_ohne["gap_km"] == [] and (
        luecken_ohne["points_total"] == luecken_ohne["points_measured"] == len(lauf_ohne.km)
    ), (
        f"AC-4: ohne Ausfall muessen alle Punkte als gemessen gelten und "
        f"`gap_km` leer sein, war {luecken_ohne!r}"
    )

    mit = _LueckenRadar(luecken={3: {"throttled": True}})
    lauf_mit = _lauf(mit, tag="ac4-mit")
    luecken_mit = _pruefe_luecken(lauf_mit, mit, punkte_erwartet=6)
    assert luecken_mit["gap_km"], (
        f"Positivkontrolle: derselbe Aufbau MIT Luecke muss eine gefuellte "
        f"`gap_km`-Liste liefern — sonst prueft die leere Liste oben nichts. "
        f"War {luecken_mit!r}"
    )


# ---------------------------------------------------------------------------
# AC-5 / AC-6 / AC-7: die drei Lueckenwege, getrennt geprueft.
# ---------------------------------------------------------------------------

def test_geworfene_ausnahme_erscheint_als_luecke():
    """AC-5 GIVEN der Abruf eines Folgepunkts wirft / WHEN der Alarm
    protokolliert wird / THEN erscheint dieser Punkt in `gap_km`."""
    radar = _LueckenRadar(ausnahmen=(2,))
    lauf = _lauf(radar, tag="ac5")
    _pruefe_luecken(lauf, radar, punkte_erwartet=6)


def test_throttled_erscheint_als_luecke():
    """AC-6 GIVEN der Abruf eines Folgepunkts liefert `throttled=True` /
    WHEN der Alarm protokolliert wird / THEN erscheint dieser Punkt in
    `gap_km` — die Budget-Drosselung ist kein belegtes "trocken"."""
    radar = _LueckenRadar(luecken={2: {"throttled": True}})
    lauf = _lauf(radar, tag="ac6")
    _pruefe_luecken(lauf, radar, punkte_erwartet=6)


def test_data_unavailable_erscheint_als_luecke():
    """AC-7 GIVEN der Abruf eines Folgepunkts liefert `data_unavailable=True` /
    WHEN der Alarm protokolliert wird / THEN erscheint dieser Punkt in
    `gap_km` — der Quellenausfall ist kein belegtes "trocken"."""
    radar = _LueckenRadar(luecken={2: {"data_unavailable": True}})
    lauf = _lauf(radar, tag="ac7")
    _pruefe_luecken(lauf, radar, punkte_erwartet=6)


# ---------------------------------------------------------------------------
# AC-8 (Positivkontrolle): am ERSTEN Punkt entsteht gar keine Zeile mit
#       Ausdehnung — nur deshalb misst AC-2 einen Index-1..N-1-Fall.
# ---------------------------------------------------------------------------

def test_ausfall_am_ersten_punkt_erzeugt_keine_ausdehnungszeile():
    """AC-8 GIVEN der Ausfall trifft den ersten, ausloesenden Messpunkt /
    WHEN der Pruflauf durchlaeuft / THEN entsteht dazu KEINE Protokollzeile
    mit einer Ausdehnungsangabe — der Lauf steigt vorher aus.

    Positivkontrolle je Ausfallweg: DERSELBE Ausfall an Index 1 muss sehr wohl
    eine Zeile mit `measurement_gaps` erzeugen. Ohne sie waere die
    Abwesenheits-Pruefung oben trivial wahr — sie wuerde auch bestehen, wenn
    das Feld ueberhaupt nie geschrieben wird, und damit gar nichts belegen.
    """
    for name, bau_erster, bau_zweiter in (
        (
            "Ausnahme",
            lambda: _LueckenRadar(ausnahmen=(0,)),
            lambda: _LueckenRadar(ausnahmen=(1,)),
        ),
        (
            "data_unavailable",
            lambda: _LueckenRadar(luecken={0: {"data_unavailable": True}}),
            lambda: _LueckenRadar(luecken={1: {"data_unavailable": True}}),
        ),
    ):
        lauf = _lauf(bau_erster(), tag="ac8-erster")
        alle = lauf.entries + lauf.not_delivered
        assert lauf.sent == 0, (
            f"AC-8/{name}: der Ausfall am ersten Punkt darf keinen Alarm "
            f"ausloesen, sent={lauf.sent}\nBody:\n{lauf.body}"
        )
        mit_ausdehnung = [e for e in alle if "measurement_gaps" in e]
        assert not mit_ausdehnung, (
            f"AC-8/{name}: kein Protokoll-Eintrag dieses Laufs darf eine "
            f"Ausdehnungsangabe tragen — der Lauf hat die Mehrpunkt-Abfrage "
            f"nie ausgewertet. Gefunden: {mit_ausdehnung!r}"
        )

        radar_zweiter = bau_zweiter()
        lauf_zweiter = _lauf(radar_zweiter, tag="ac8-zweiter")
        luecken = _pruefe_luecken(lauf_zweiter, radar_zweiter, punkte_erwartet=6)
        assert luecken["gap_km"], (
            f"Positivkontrolle/{name}: derselbe Ausfall an Index 1 MUSS eine "
            f"Zeile mit gefuelltem `gap_km` erzeugen — sonst belegt die "
            f"Abwesenheit oben nichts. War {luecken!r}"
        )


# ---------------------------------------------------------------------------
# AC-9: Fail-soft — Protokollieren darf den Alarm nie kosten.
# ---------------------------------------------------------------------------

def test_scheiternde_luecken_ableitung_kostet_den_alarm_nicht(monkeypatch):
    """AC-9 GIVEN die Ableitung von `measurement_gaps` scheitert / WHEN der
    Radar-Alarmpfad laeuft / THEN wird der Alarm trotzdem versendet und
    protokolliert — NUR ohne dieses eine Feld.

    Der Fehler wird an der ABLEITUNG selbst ausgeloest (`_messluecken_felder`),
    nicht an `_radar_e1_fields` als Ganzem — sonst pruefte der Test die
    bestehende Absicherung der E-1-Groessen aus #2050 S6 statt der neuen
    Ableitung.

    Kern der Zusicherung ist die zweite Haelfte: die BESTEHENDEN E-1-Groessen
    muessen den Fehlschlag ueberleben. Liegt die neue Ableitung im gemeinsamen
    `try` von `_radar_e1_fields()`, gibt die Funktion `{}` zurueck und reisst
    alle fuenf mit — ein Fehler in der nachrangigen Luecken-Buchfuehrung
    loeschte dann Messpunkt, Ereigniszeit und Quelle aus dem Eintrag. Das waere
    eine Regression gegen #2050 S6, also schlechter als der Stand vor dieser
    Scheibe. Geprueft wird deshalb namentlich und am WERT (gegen einen
    Referenzlauf mit identischem Aufbau), nicht als Sammelaussage: eine reine
    Praesenz-Pruefung fiele auf einen Eintrag herein, der die Groessen zwar
    fuehrt, aber mit anderen Zahlen.

    Beide Laeufe legen eigens einen Briefing-Schnappschuss an: ohne ihn bliebe
    `reference_at` unbestimmbar (`None` -> Absenz, `_apply_e1_fields` schreibt
    sie dann gar nicht) und die Zusicherung waere fuer die sechste Groesse
    leer. Die Zeitreihe des Schnappschusses bleibt leer, damit die
    Briefing-Unterdrueckung nicht greift und der Alarm durchlaeuft. Die
    Testvoraussetzung unten haelt fest, dass der Referenzlauf wirklich ALLE
    gepruefen Groessen fuehrt — sonst liefe der Vergleich still leer.
    """
    from services import trip_alert as trip_alert_mod

    # Referenzlauf ZUERST, mit identischem Aufbau und noch UNBERUEHRTER
    # Ableitung: er liefert die Sollwerte der bestehenden E-1-Groessen. Ein
    # Literal waere hier wertlos — die Werte haengen an Geometrie und Uhr.
    referenz = _versand_eintrag(_lauf(
        _LueckenRadar(luecken={2: {"data_unavailable": True}}), tag="ac9-ref",
        vergleichsbasis_at=_VERGLEICHSBASIS_AT,
    ))
    fehlend = [n for n in _E1_GROESSEN if n not in referenz]
    assert not fehlend, (
        f"Testvoraussetzung: der Referenzlauf muss alle gepruefen "
        f"E-1-Groessen fuehren, es fehlen {fehlend} — sonst prueft der "
        f"Vergleich unten nichts. Eintrag: {referenz!r}"
    )
    assert datetime.fromisoformat(referenz["reference_at"]) == _VERGLEICHSBASIS_AT, (
        f"Testvoraussetzung: `reference_at` muss der Erhebungszeitpunkt des "
        f"geschriebenen Schnappschusses sein ({_VERGLEICHSBASIS_AT.isoformat()}), "
        f"war {referenz['reference_at']!r} — sonst misst der Vergleich unten "
        f"einen Wert, den dieser Test gar nicht gesetzt hat."
    )

    def _explodiert(*args, **kwargs):
        raise ValueError("absichtlich unerwartete Datenform")

    monkeypatch.setattr(trip_alert_mod, "_messluecken_felder", _explodiert)

    lauf = _lauf(
        _LueckenRadar(luecken={2: {"data_unavailable": True}}), tag="ac9",
        vergleichsbasis_at=_VERGLEICHSBASIS_AT,
    )

    assert lauf.sent >= 1 and lauf.body, (
        f"AC-9: eine gescheiterte Protokoll-Ableitung darf den Alarm nicht "
        f"kosten — sent={lauf.sent}\nBody:\n{lauf.body}"
    )
    eintrag = _versand_eintrag(lauf)
    assert "measurement_gaps" not in eintrag, (
        f"AC-9: die gescheiterte Ableitung darf kein halbes/erfundenes Feld "
        f"hinterlassen, Eintrag: {eintrag!r}"
    )
    for name in _E1_GROESSEN:
        assert name in eintrag, (
            f"AC-9: die gescheiterte Luecken-Ableitung darf die bestehende "
            f"E-1-Groesse `{name}` nicht mitreissen (#2050 S6) — sie fehlt im "
            f"Eintrag. Ein gemeinsamer `try`-Block mit `_radar_e1_fields()` "
            f"tut genau das. Eintrag: {eintrag!r}"
        )
        assert eintrag[name] == referenz[name], (
            f"AC-9: `{name}` muss den Fehlschlag UNVERAENDERT ueberstehen — "
            f"erwartet {referenz[name]!r} (Referenzlauf mit identischem "
            f"Aufbau), war {eintrag[name]!r}"
        )


# ---------------------------------------------------------------------------
# AC-10: Mandantentrennung — zwei verschiedene Nutzer, echte user_id.
# ---------------------------------------------------------------------------

def test_zwei_nutzer_teilen_sich_keinen_luecken_eintrag():
    """AC-10 GIVEN zwei verschiedene Nutzer erleiden je eine Messluecke /
    WHEN beide Alarmpfade laufen / THEN landet jeder `measurement_gaps`-
    Eintrag ausschliesslich im Protokoll des betroffenen Nutzers.

    Die beiden Luecken liegen an VERSCHIEDENEN Punkten (Index 1 vs. 4): eine
    Vermischung waere sonst nur an der Zahl der Eintraege erkennbar, nicht am
    Inhalt — ein gemeinsamer Schreibort mit gleichem Wert kaeme durch.
    """
    radar_a = _LueckenRadar(luecken={1: {"data_unavailable": True}})
    lauf_a = _lauf(radar_a, tag="ac10-a")
    radar_b = _LueckenRadar(luecken={4: {"throttled": True}})
    lauf_b = _lauf(radar_b, tag="ac10-b")

    assert lauf_a.uid != lauf_b.uid, "Testvoraussetzung: zwei VERSCHIEDENE Nutzer"

    luecken_a = _pruefe_luecken(lauf_a, radar_a, punkte_erwartet=6)
    luecken_b = _pruefe_luecken(lauf_b, radar_b, punkte_erwartet=6)

    assert luecken_a["gap_km"] != luecken_b["gap_km"], (
        f"Testvoraussetzung: die beiden Laeufe muessen unterscheidbare "
        f"Luecken erzeugen, waren {luecken_a!r} / {luecken_b!r}"
    )
    for lauf, fremd in ((lauf_a, lauf_b), (lauf_b, lauf_a)):
        fremde = [
            e for e in lauf.entries + lauf.not_delivered
            if e.get("entity_id") == fremd.trip_id
        ]
        assert not fremde, (
            f"AC-10: im Protokoll von {lauf.uid} darf kein Eintrag des "
            f"anderen Nutzers stehen — gefunden {fremde!r}"
        )


# ---------------------------------------------------------------------------
# AC-11: Bestandsdaten — Alteintraege ohne das Feld bleiben unveraendert.
# ---------------------------------------------------------------------------

def test_alteintrag_ohne_messluecken_feld_bleibt_unveraendert():
    """AC-11 GIVEN ein Alarmprotokoll mit einem Alt-Eintrag ohne
    `measurement_gaps` / WHEN ein neuer Eintrag dazukommt / THEN bleibt der
    Alt-Eintrag unveraendert lesbar und wird nicht umgeschrieben
    (Read-Modify-Write)."""
    uid = _uid("ac11")
    alt = {
        "entity_id": "trip-alt-2050-s4b", "entity_type": "trip",
        "sent_at": "2026-01-05T06:00:00+00:00", "changes_count": 1,
        "severity": "warn", "metrics": [], "hazards": [], "reason": "nowcast",
        "channels_sent": ["email"], "channels_not_sent": [],
    }
    pfad = get_data_dir(uid) / "alert_log.json"
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps({"entries": [dict(alt)]}))

    radar = _LueckenRadar(luecken={2: {"data_unavailable": True}})
    lauf = _lauf(radar, tag="ac11", uid=uid)

    bestand = [e for e in lauf.entries if e.get("entity_id") == alt["entity_id"]]
    assert bestand == [alt], (
        f"AC-11: der Alt-Eintrag muss unveraendert erhalten bleiben (auch "
        f"OHNE nachtraeglich angebautes `measurement_gaps`), war {bestand!r}"
    )
    assert lauf.entries[0] == alt, (
        f"AC-11: der Alt-Eintrag muss an seiner Stelle stehen bleiben, "
        f"entries={lauf.entries!r}"
    )
    _pruefe_luecken(lauf, radar, punkte_erwartet=6)
