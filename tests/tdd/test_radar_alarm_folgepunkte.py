"""TDD RED — Issue #2480: der Trip-Radar-Alarm loest an ALLEN Messpunkten aus.

SPEC: docs/specs/modules/fix_2480_radar_alle_messpunkte.md (AC-1 bis AC-11)

Ausgangslage (Stand `e140b3955`): `check_radar_alerts()` misst an bis zu sechs
Punkten der Reststrecke (Abstand 2 km), entscheidet aber NUR am ersten
(`_punkte[0]`, `radar_alert_due(result, 55)`). Regen, der nur ueber Punkt 2..6
liegt, loest nichts aus; faellt Punkt 0 aus, bricht der Lauf mit `continue`
ab, bevor die Folgepunkte ueberhaupt abgerufen werden.

RED-GRUND (je Test an einer ZUSICHERUNG, nicht am Aufbau):
  * AC-1/AC-3/AC-5/AC-8/AC-9/AC-10/AC-11: der Alarm durch einen FOLGEPUNKT
    (`sent == 1`, Werte des gewaehlten Punkts, `trigger_point_km`) existiert
    heute nicht.
  * Baustein-Test (AC-3): `waehle_massgeblichen_punkt` existiert nicht — der
    Import steht INNERHALB des Tests, damit jeder Test aus eigenem Grund rot
    wird und nicht die ganze Datei an einem Collection-Fehler haengt.
  * Regressionsschutz, HEUTE SCHON GRUEN und so gewollt: AC-2 (Punkt 0
    loest aus — bitgleich zur Referenz), AC-4 (nichts in Reichweite),
    AC-6 (Ausfall ohne Regen bleibt protokolliert), AC-7 (throttled),
    AC-10 zweiter Test (Altzeile ohne das neue Feld).

Mock-frei: echte `RadarNowcastService`-Unterklasse am DI-Seam von
`TripAlertService`, echte `NowcastResult`-Objekte, echter
`check_radar_alerts()`-Lauf ueber die `AlarmPruefstrecke` (#2050 S1) mit
Abgriff aller vier Kanaele. Gesteuert wird nur, WELCHER Punkt welches Ergebnis
bekommt.

STEUERUNG NACH KOORDINATE, nicht nach Aufrufreihenfolge: der Fix aendert
Reihenfolge und Anzahl der Abrufe (Folgepunkte auch nach einer Ausnahme an
Punkt 0). Die Soll-Punkte werden deshalb je gestellter Uhrzeit mit einem
trockenen Probelauf EINMAL aufgenommen (Punkt 0 haengt am Zeitanteil, 30 Min
verschieben ihn um rund einen Punktabstand) und jede Anfrage dem naechsten
Soll-Punkt zugeordnet; liegt keiner naeher als 0,3 km, schlaegt der Test laut
fehl statt still falsch zu indizieren.

Pfadregel #1409: Prueflinge werden relativ zu DIESER Datei aufgeloest.
"""
from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from app.loader import get_briefings_dir, get_data_dir, load_trip  # noqa: E402
from services import alert_log, alert_input_capture  # noqa: E402
from services.radar_service import (  # noqa: E402
    INTENSITY_DRY, INTENSITY_HEAVY, INTENSITY_LIGHT, INTENSITY_MODERATE,
    NowcastResult, RadarNowcastService, _nowcast_source_key,
)
from utils.geo import haversine_km  # noqa: E402

from tests.helpers.alarm_pruefstrecke import AlarmPruefstrecke  # noqa: E402
from tests.helpers.arrival_window_fixtures import stage_date  # noqa: E402
from tests.tdd.test_952_onset_alert_fidelity import _clean_user  # noqa: E402
from tests.tdd.test_alarm_pruefstrecke_selbstschutz import (  # noqa: E402
    _settings_all_channels, _write_premium_profile, _write_tier,
)
from tests.tdd.test_regen_ausdehnung_textstellen import (  # noqa: E402
    _UHR_TIROL, _ZONEN_LAT0, _ZONEN_LAT1, _ZONEN_LON0, _ZONEN_LON1,
)

_UHR = datetime.fromisoformat(_UHR_TIROL)
_ORTSZEIT = ZoneInfo("Europe/Vienna")  # Etappe liegt in Tirol (tz_for_coords)
_REFERENZ = ROOT / "tests" / "fixtures" / "radar_folgepunkte" / "punkt0_referenz.json"

# RADAR_ONSET_THRESHOLD_MIN — bewusst als Literal des Tests. #2261 A-1: die
# Schwelle ist die Reichweite der Quelle (NOWCAST_HORIZON_MIN), vorher 55.
_SCHWELLE_MIN = 180


# ---------------------------------------------------------------------------
# Aufbau: Nutzer + Trip, Radar-Fake nach Koordinate, Ergebnis-Bausteine
# ---------------------------------------------------------------------------

def _uid(tag: str) -> str:
    return f"tdd-2480-{tag}-{uuid.uuid4().hex[:6]}"


def _lege_trip_an(uid: str, *, tier: str = "premium", trip_id: str | None = None):
    """Nutzer (alle vier Kanaele) + Nord-Strecke (~24 km, sechs Messpunkte,
    Muster `_vier_kanal_lauf`). Das Premium-Profil entsteht VOR der
    `AlarmPruefstrecke` (deren Konstruktor liest es ein)."""
    _clean_user(uid)
    if tier == "premium":
        _write_premium_profile(uid, _UHR)
    else:
        _write_tier(uid, tier)
    trip_id = trip_id or f"tdd-2480-trip-{uuid.uuid4().hex[:6]}"
    luftlinie = haversine_km(_ZONEN_LAT0, _ZONEN_LON0, _ZONEN_LAT1, _ZONEN_LON1)
    verzeichnis = get_briefings_dir(uid)
    verzeichnis.mkdir(parents=True, exist_ok=True)
    pfad = verzeichnis / f"{trip_id}.json"
    from freezegun import freeze_time

    with freeze_time(_UHR):
        pfad.write_text(json.dumps({
            "id": trip_id, "name": "Folgepunkte Trip",
            "stages": [{
                "id": "S1", "name": "Tag 1",
                "date": stage_date(_ZONEN_LAT0, _ZONEN_LON0).isoformat(),
                "waypoints": [
                    {
                        "id": "WP0", "name": "WP0",
                        "lat": _ZONEN_LAT0, "lon": _ZONEN_LON0,
                        "elevation_m": 1000.0, "arrival_calculated": "11:00",
                        "distance_from_start_km": 0.0,
                    },
                    {
                        "id": "WP1", "name": "WP1",
                        "lat": _ZONEN_LAT1, "lon": _ZONEN_LON1,
                        "elevation_m": 1000.0, "arrival_calculated": "17:00",
                        "distance_from_start_km": round(luftlinie, 3),
                    },
                ],
            }],
            "report_config": {
                "trip_id": trip_id, "send_email": True, "send_telegram": True,
                "send_sms": True, "send_premium_sms": True,
                "alert_on_changes": True,
            },
        }))
        return load_trip(pfad, user_id="default")


def nass(
    onset: int | None, *, menge: float = 3.0, ende: int | None = 40,
    label: str = INTENSITY_MODERATE, quelle: str = "radar",
    konvektiv: bool = False, laufend: bool = False,
) -> NowcastResult:
    """Ein ECHTES nasses `NowcastResult` MIT Menge (`strecke_fixtures.nass()`
    kennt kein `window_precip_mm`)."""
    return NowcastResult(
        onset_minutes=onset, intensity_label=label, source=quelle,
        window_precip_mm=menge, event_end_minutes=ende,
        is_convective=konvektiv, already_running=laufend,
    )


def trocken() -> NowcastResult:
    return NowcastResult(onset_minutes=None, intensity_label=INTENSITY_DRY, source="radar")


class _PunktRadar(RadarNowcastService):
    """Echte `RadarNowcastService`-Unterklasse am DI-Seam. Ergebnis je
    PUNKTINDEX (`script`: Index -> `NowcastResult` | `Exception`; nicht
    gelistete Punkte sind trocken). Der Index wird aus der Koordinate
    bestimmt, nicht aus der Aufrufnummer. Mitgeschrieben werden Aufrufe und
    — wie der echte `get_nowcast` es tut — der Roh-Mitschnitt je Punkt
    (`alert_input_capture.capture_system`), damit die Capture-ID eines Alarms
    einem Punkt zuordenbar ist."""

    def __init__(self, soll, script: dict | None = None) -> None:
        super().__init__()
        self._soll = soll  # None: Probe-Modus, Index = Aufrufnummer
        self.script = dict(script or {})
        self.aufrufe: list[dict] = []
        self.capture_ids: dict[int, str | None] = {}

    def neuer_lauf(self, script: dict | None = None) -> None:
        self.aufrufe.clear()
        self.capture_ids.clear()
        if script is not None:
            self.script = dict(script)

    def _index(self, lat: float, lon: float) -> int:
        if self._soll is None:
            return len(self.aufrufe)
        abstaende = [haversine_km(lat, lon, s[0], s[1]) for s in self._soll]
        i = min(range(len(abstaende)), key=abstaende.__getitem__)
        assert abstaende[i] < 0.3, (
            f"Testaufbau: Anfrage ({lat}, {lon}) liegt {abstaende[i]:.2f} km "
            f"neben dem naechsten Soll-Punkt — die Soll-Punkte der gestellten "
            f"Uhr passen nicht."
        )
        return i

    def get_nowcast(self, lat, lon, elevation_m=None, priority="user_briefing", user_id=None):
        i = self._index(lat, lon)
        self.aufrufe.append({
            "idx": i, "lat": lat, "lon": lon, "priority": priority,
        })
        self.capture_ids[i] = alert_input_capture.capture_system(
            branch="nowcast", source_key=_nowcast_source_key(lat, lon),
            payload={"source": "radar", "punkt": i, "frames": []},
        )
        ergebnis = self.script.get(i, trocken())
        if isinstance(ergebnis, Exception):
            raise ergebnis
        return ergebnis

    @property
    def abgerufen(self) -> list[int]:
        return [a["idx"] for a in self.aufrufe]


@lru_cache(maxsize=None)
def _soll_punkte(at: datetime) -> tuple[tuple[float, float], ...]:
    """Die sechs Messpunkte (nach Breitengrad = Index sortiert, Nord-Strecke)
    fuer die gestellte Uhr `at`, aufgenommen mit einem trockenen Probelauf."""
    uid = _uid("soll")
    try:
        trip = _lege_trip_an(uid)
        probe = _PunktRadar(None)
        strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())
        strecke.lauf(at=at, zweig="radar", trip=trip, radar_service=probe)
    finally:
        _clean_user(uid)
    punkte = sorted((a["lat"], a["lon"]) for a in probe.aufrufe)
    assert len(punkte) >= 4, (
        f"Testvoraussetzung: die Nord-Strecke muss bei {at} mindestens vier "
        f"Messpunkte liefern (die Tests nutzen Index 0..3), lieferte "
        f"{len(punkte)}."
    )
    return tuple(punkte)


class _Szenario:
    """Ein Nutzer + Trip + Pruefstrecke ueber MEHRERE Laeufe (Zustand liegt auf
    dem Datentraeger unter `get_data_dir(uid)`, wie in Produktion)."""

    def __init__(
        self, tag: str, *, tier: str = "premium", trip_id: str | None = None,
    ) -> None:
        self.uid = _uid(tag)
        self.trip = _lege_trip_an(self.uid, tier=tier, trip_id=trip_id)
        self.strecke = AlarmPruefstrecke(
            user_id=self.uid, settings=_settings_all_channels(),
        )
        self.radar: _PunktRadar | None = None

    def lauf(self, script: dict, *, at: datetime = _UHR):
        if self.radar is None:
            self.radar = _PunktRadar(_soll_punkte(at), script)
        else:
            self.radar._soll = _soll_punkte(at)
            self.radar.neuer_lauf(script)
        return self.strecke.lauf(
            at=at, zweig="radar", trip=self.trip, radar_service=self.radar,
        )

    def soll(self, at: datetime = _UHR):
        return _soll_punkte(at)

    def km(self, idx: int, at: datetime = _UHR) -> float:
        """Streckenkilometer des Soll-Punkts: gerade Nord-Strecke mit
        `distance_from_start_km == 0` am Startwegpunkt — Entfernung von WP0,
        unabhaengig vom Pruefling gerechnet."""
        lat, lon = self.soll(at)[idx]
        return haversine_km(_ZONEN_LAT0, _ZONEN_LON0, lat, lon)

    def protokoll(self) -> dict:
        pfad = get_data_dir(self.uid) / "alert_log.json"
        return json.loads(pfad.read_text()) if pfad.exists() else {}

    def entries(self) -> list[dict]:
        return [
            e for e in self.protokoll().get("entries", [])
            if e.get("entity_id") == self.trip.id
        ]

    def nicht_zugestellt(self) -> list[dict]:
        return [
            e for e in self.protokoll().get("not_delivered", [])
            if e.get("entity_id") == self.trip.id
        ]

    def vergleichsbasis_mm(self):
        """Zuletzt GEBUCHTE Menge (Vergleichsbasis #2065) ueber den
        produktiven Lesepfad des Sperrzeit-Vergleichs."""
        from services.alert_gate import last_nowcast_precip_mm

        return last_nowcast_precip_mm(
            user_id=self.uid, throttle_scope="radar", throttle_key=self.trip.id,
        )

    def gruende(self, seit: datetime) -> set:
        """Alle Nicht-Zustellungs-Gruende, die der PRUEFLING selbst
        protokolliert hat (`alert_log.read_undelivered`)."""
        vorfaelle = alert_log.read_undelivered(
            self.uid, entity_id=self.trip.id, entity_type="trip", since=seit,
        )
        return {g for v in vorfaelle for g in v.reasons}

    def aufraeumen(self) -> None:
        _clean_user(self.uid)


@pytest.fixture
def szenario():
    erzeugt: list[_Szenario] = []

    def _bau(tag: str, **kw) -> _Szenario:
        s = _Szenario(tag, **kw)
        erzeugt.append(s)
        return s

    yield _bau
    for s in erzeugt:
        s.aufraeumen()


def _ab_uhrzeit(at: datetime, onset_min: int) -> str:
    """Erwartete „HH:MM“ des Beginns in Ortszeit — aus gestellter Uhr + Beginn
    gerechnet, kein Literal."""
    return (at + timedelta(minutes=onset_min)).astimezone(_ORTSZEIT).strftime("%H:%M")


def _kanaele(lauf) -> dict[str, str]:
    return {
        "mail": "\n".join(f"{betreff}\n{koerper}" for betreff, koerper in lauf.mail),
        "telegram": "\n".join(lauf.telegram),
        "sms": "\n".join(lauf.sms),
        "premium_sms": "\n".join(lauf.premium_sms),
    }


# ---------------------------------------------------------------------------
# AC-2: Referenz-Aufnahme „Punkt 0 loest aus“ (vor #2480 aufgezeichnet)
# ---------------------------------------------------------------------------

_REFERENZ_TRIP_ID = "tdd-2480-referenz-trip"


def _punkt0_skript() -> dict:
    """Punkt 0 loest aus (Beginn 20 Min). Die Folgepunkte sind nass, aber alle
    SPAETER als Punkt 0 — einer davon mit hoeherer Dringlichkeit (Punkt 1,
    starker Regen) und groesserer Menge. Damit entscheidet bei Punkt 0 allein
    der fruehere Beginn; eine Auswahl, die Dringlichkeit/Menge ueber den
    Beginn stellt, ginge hier fehl. Punkt 3 ist trocken und trennt die
    Nass-Zone."""
    return {
        0: nass(20, menge=3.0, ende=50),
        1: nass(30, menge=6.0, ende=70, label=INTENSITY_HEAVY),
        2: nass(45, menge=2.0, ende=60),
        4: nass(35, menge=4.0, ende=65, label=INTENSITY_LIGHT),
    }


def _normalisiert(wert, ersetze: dict):
    """Fluechtiges (Trip-ID, Capture-ID) durch stabile Platzhalter ersetzen."""
    text = json.dumps(wert, sort_keys=True, ensure_ascii=False)
    for roh, platzhalter in ersetze.items():
        if roh:
            text = text.replace(roh, platzhalter)
    return json.loads(text)


def _aufnahme_punkt0() -> dict:
    """Der Lauf „Punkt 0 loest aus“ mit fester Uhr, aufgenommen als
    vergleichbare Struktur: alle vier Kanaltexte, die Alarmprotokoll-Eintraege
    (Trip-/Capture-ID normalisiert), die gebuchte Vergleichsbasis, die
    registrierten Ereignis-Identitaeten und die Zahl der Abrufe."""
    s = _Szenario("referenz", trip_id=_REFERENZ_TRIP_ID)
    try:
        lauf = s.lauf(_punkt0_skript())
        ersetze = {
            cid: f"<capture:{idx}>" for idx, cid in s.radar.capture_ids.items()
        }
        from services.alert_state import AlertStateService

        register = AlertStateService(s.uid).load(s.trip.id)
        identitaeten = sorted(
            (
                {k: v for k, v in eintrag.items()}
                for schluessel, eintrag in register.items()
                if schluessel.startswith("event_identity:")
                and isinstance(eintrag, dict)
            ),
            key=lambda e: json.dumps(e, sort_keys=True, default=str),
        )
        return _normalisiert({
            "triggered_count": lauf.triggered_count,
            "kanaele": _kanaele(lauf),
            "entries": s.entries(),
            "nicht_zugestellt": s.nicht_zugestellt(),
            "vergleichsbasis_mm": s.vergleichsbasis_mm(),
            "ereignis_identitaeten": identitaeten,
            "abrufe": len(s.radar.aufrufe),
        }, ersetze)
    finally:
        s.aufraeumen()


# ---------------------------------------------------------------------------
# AC-3: der reine Auswahl-Baustein
# ---------------------------------------------------------------------------

def test_massgeblicher_punkt_fruehester_beginn_dann_dringlichkeit_dann_index():
    """AC-3 (Baustein) GIVEN mehrere Punkte erfuellen die Ausloeseregel /
    WHEN der maßgebliche gewaehlt wird / THEN gewinnt der FRUEHESTE Beginn
    (laufender Regen = 0 Min), bei Gleichstand die hoehere Dringlichkeit,
    dann der kleinere Index; nicht verwertbare Punkte (None, throttled,
    data_unavailable) und Beginn jenseits der Schwelle sind keine Kandidaten.

    RED heute: `services.trip_alert.waehle_massgeblichen_punkt` existiert
    nicht (Import im Test, damit jeder Test aus eigenem Grund rot wird)."""
    from services.trip_alert import waehle_massgeblichen_punkt as waehle

    # Stufe 1 — frueheste Beginn gewinnt, auch gegen hoehere Dringlichkeit und
    # kleineren Index (faengt „spaetester statt frueherer Beginn“).
    liste = [
        nass(50, label=INTENSITY_HEAVY), None, nass(10), nass(30),
        nass(40, konvektiv=True),
    ]
    gewaehlt = waehle(liste)
    assert gewaehlt is not None and gewaehlt[0] == 2 and gewaehlt[1] is liste[2], (
        f"Stufe 1: frueheste Beginn (Index 2, 10 Min) muss gewinnen, gewaehlt: {gewaehlt!r}"
    )

    # Laufender Regen zaehlt als Beginn 0 und schlaegt jeden Beginn in der Zukunft.
    liste = [nass(5), nass(20), nass(None, laufend=True, ende=30)]
    gewaehlt = waehle(liste)
    assert gewaehlt is not None and gewaehlt[0] == 2, (
        f"Stufe 1: laufender Regen (Beginn 0) muss gegen Beginn 5/20 gewinnen: {gewaehlt!r}"
    )

    # Stufe 2 — gleicher Beginn: hoehere Dringlichkeit (Rangfolge LOW < MODERATE
    # < HIGH wie `highest_urgency`); Gewitter ist immer HIGH.
    liste = [
        nass(20, label=INTENSITY_LIGHT), nass(20, label=INTENSITY_MODERATE),
        nass(20, label=INTENSITY_HEAVY), nass(20, label=INTENSITY_MODERATE),
    ]
    gewaehlt = waehle(liste)
    assert gewaehlt is not None and gewaehlt[0] == 2, (
        f"Stufe 2: bei Gleichstand gewinnt die hoechste Dringlichkeit (Index 2): {gewaehlt!r}"
    )
    liste = [nass(20, label=INTENSITY_HEAVY), nass(20, label=INTENSITY_MODERATE, konvektiv=True)]
    gewaehlt = waehle(liste)
    assert gewaehlt is not None and gewaehlt[0] == 0, (
        f"Stufe 2: Gewitter (HIGH) und starker Regen (HIGH) sind gleich dringlich "
        f"— dann entscheidet der Index: {gewaehlt!r}"
    )
    liste = [nass(20, label=INTENSITY_MODERATE), nass(20, label=INTENSITY_MODERATE, konvektiv=True)]
    gewaehlt = waehle(liste)
    assert gewaehlt is not None and gewaehlt[0] == 1, (
        f"Stufe 2: Gewitter (HIGH) schlaegt maessigen Regen bei gleichem Beginn: {gewaehlt!r}"
    )

    # Stufe 3 — alles gleich: der kleinere Index (nahe am Wanderer).
    liste = [None, nass(20), nass(20), nass(20)]
    gewaehlt = waehle(liste)
    assert gewaehlt is not None and gewaehlt[0] == 1, (
        f"Stufe 3: bei vollem Gleichstand gewinnt der kleinere Index (1): {gewaehlt!r}"
    )

    # Keine Kandidaten -> „keiner“.
    keine = [
        None, trocken(), nass(_SCHWELLE_MIN + 1), nass(_SCHWELLE_MIN + 60),
        NowcastResult(onset_minutes=5, intensity_label=INTENSITY_MODERATE,
                      source="radar", throttled=True),
        NowcastResult(onset_minutes=5, intensity_label=INTENSITY_MODERATE,
                      source="radar", data_unavailable=True),
    ]
    assert waehle(keine) is None, (
        "Keine Kandidaten (None/trocken/Beginn > Schwelle/throttled/data_unavailable) "
        "muessen „keiner“ ergeben"
    )
    # Grenze: genau an der Schwelle ist noch auslösend (`radar_alert_due`).
    gewaehlt = waehle([trocken(), nass(_SCHWELLE_MIN)])
    assert gewaehlt is not None and gewaehlt[0] == 1, (
        f"Beginn genau {_SCHWELLE_MIN} Min ist auslösend: {gewaehlt!r}"
    )
    assert waehle([]) is None, "leere Liste ergibt „keiner“"


# ---------------------------------------------------------------------------
# AC-1: Regen weiter vorn loest Alarm aus
# ---------------------------------------------------------------------------

def test_folgepunkt_nass_loest_alarm_aus(szenario):
    """AC-1 GIVEN der erste Messpunkt ist trocken, ueber Punkt 2 (rund 4 km
    weiter) beginnt Regen in 25 Min / WHEN der Radar-Pruflauf laeuft / THEN
    wird ein Alarm versendet; die Uhrzeit im Text ist der Beginn AN PUNKT 2
    (ab jetzt gerechnet) und der Ort steht im Nass-Zonen-Suffix.

    RED heute: `triggered_count == 0` — nur Punkt 0 entscheidet."""
    s = szenario("ac1")
    lauf = s.lauf({2: nass(25, menge=3.0, ende=55), 3: nass(40, menge=3.0, ende=70)})
    assert lauf.triggered_count == 1, (
        f"AC-1: Regen mit Beginn in 25 Min ueber Punkt 2 muss einen Alarm "
        f"ausloesen (war {lauf.triggered_count}); abgerufen: {s.radar.abgerufen}"
    )
    kanaele = _kanaele(lauf)
    hhmm = _ab_uhrzeit(_UHR, 25)
    assert f"ab {hhmm}" in kanaele["mail"], (
        f"AC-1: die Mail nennt den Beginn AN PUNKT 2 (`ab {hhmm}`):\n{kanaele['mail']}"
    )
    import re

    spannen = re.search(r"· Nass (km [^·\n]*)", kanaele["mail"])
    erwartet = f"km {round(s.km(2))}-{round(s.km(3))}"
    assert spannen and spannen.group(1).strip() == erwartet, (
        f"AC-1: der Ort steht im Nass-Zonen-Suffix (`{erwartet}` = Punkt 2 und 3, "
        f"Punkt 0/1 sind trocken): {spannen.group(1) if spannen else None!r}"
    )


def test_beginn_genau_an_der_schwelle_am_folgepunkt_loest_aus(szenario):
    """Randfall zu AC-1: genau an der Schwelle (#2261 A-1: 180 Min) ist
    `radar_alert_due` noch erfuellt — auch an einem Folgepunkt (faengt eine
    Auswahl mit `<`). Punkt 4 ist der vorletzte: der Nutzer passiert Punkt 5
    laut Zeitplan erst ~jetzt+177, Fenster-Ende 207 >= 180."""
    s = szenario("ac1-grenze")
    lauf = s.lauf({4: nass(_SCHWELLE_MIN, menge=0.0, ende=None)})
    assert lauf.triggered_count == 1, (
        f"Beginn genau {_SCHWELLE_MIN} Min ueber Punkt 4 muss ausloesen "
        f"(war {lauf.triggered_count})"
    )


# ---------------------------------------------------------------------------
# AC-2: Punkt 0 loest aus — bitgleich zum Stand vor #2480
# ---------------------------------------------------------------------------

def test_punkt0_ausloesend_bleibt_bitgleich():
    """AC-2 GIVEN der erste Messpunkt erfuellt die Ausloeseregel und kein
    Folgepunkt beginnt frueher / WHEN der Pruflauf laeuft / THEN sind Versand,
    alle vier Kanaltexte, Dringlichkeit, Vergleichsbasis, Ereignis-Identitaet
    und Alarmprotokoll BITGLEICH zur Aufnahme des Stands vor #2480.

    REFERENZ: `tests/fixtures/radar_folgepunkte/punkt0_referenz.json` wurde
    am 2026-10-02 auf dem UNVERAENDERTEN Code (Basis `e140b3955`, kein Diff
    unter src/) mit fester Uhr (`_UHR_TIROL`) und fester Trip-ID
    aufgenommen — vor jeder Implementierung von #2480. Fluechtiges (Trip-,
    Capture-ID) ist durch Platzhalter ersetzt. Dass bei Ausloesung durch
    Punkt 0 KEIN `trigger_point_km` im Protokoll steht, ist damit
    mitbewacht (die Referenz kennt das Feld nicht).

    Die Folgepunkte sind nass, aber alle SPAETER; einer (Punkt 1) mit hoeherer
    Dringlichkeit und Menge — bei Punkt 0 entscheidet allein der fruehere
    Beginn. HEUTE GRUEN (Regressionsschutz)."""
    referenz = json.loads(_REFERENZ.read_text(encoding="utf-8"))
    aufnahme = _aufnahme_punkt0()
    assert aufnahme["triggered_count"] == 1, (
        f"Testvoraussetzung: Punkt 0 muss genau einen Alarm ausloesen: {aufnahme['triggered_count']}"
    )
    assert aufnahme == referenz, (
        "AC-2: der Lauf `Punkt 0 loest aus` weicht von der Aufnahme des "
        "Stands vor #2480 ab.\n"
        + "\n".join(
            f"  {k}: war {referenz.get(k)!r}, jetzt {aufnahme.get(k)!r}"
            for k in sorted(set(referenz) | set(aufnahme))
            if referenz.get(k) != aufnahme.get(k)
        )
    )


# ---------------------------------------------------------------------------
# AC-3: alle Groessen stammen aus EINEM Abruf
# ---------------------------------------------------------------------------

def test_alle_groessen_stammen_aus_einem_abruf(szenario):
    """AC-3 GIVEN mehrere Punkte erfuellen die Ausloeseregel, jeder mit
    BEWUSST anderer Menge/Dringlichkeit/Ende/Quelle / WHEN der Alarm
    versendet wird / THEN stammen Beginn, Menge (Vergleichsbasis),
    Dringlichkeit, Gewitter-Kennzeichen, Ende, Quelle und die
    Mitschnitt-Capture-ID alle aus dem Abruf des EINEN massgeblichen Punkts
    (frueheste Beginn = Punkt 2) — nicht aus Punkt 0, nicht aus Max/Min.

    Aufbau (alle Werte paarweise verschieden, damit jede Mischung auffaellt):
      Punkt 0  nass, aber AUSSER REICHWEITE (80 Min): 9,0 mm, starker Regen,
               Gewitter, Ende +150, Quelle INCA — jeder Leser von Punkt 0
               faellt auf.
      Punkt 2  Beginn 20: 3,0 mm, maessig, kein Gewitter, Ende +50, radar
               <- massgeblich (frueheste Beginn)
      Punkt 3  Beginn 35: 6,0 mm, starker Regen, Ende +90, AROME-FR
      Punkt 4  Beginn 50: 8,0 mm, Gewitter, Ende +100, ICON-D2
               (spaetester Beginn UND hoechste Dringlichkeit).

    RED heute: `triggered_count == 0`, weil Punkt 0 ausser Reichweite ist."""
    s = szenario("ac3")
    skript = {
        0: nass(80, menge=9.0, ende=150, label=INTENSITY_HEAVY, quelle="INCA", konvektiv=True),
        2: nass(20, menge=3.0, ende=50, label=INTENSITY_MODERATE, quelle="radar"),
        3: nass(35, menge=6.0, ende=90, label=INTENSITY_HEAVY, quelle="AROME-FR"),
        4: nass(50, menge=8.0, ende=100, label=INTENSITY_MODERATE, quelle="ICON-D2", konvektiv=True),
    }
    lauf = s.lauf(skript)
    assert lauf.triggered_count == 1, (
        f"AC-3: Folgepunkte in Reichweite muessen den Alarm tragen "
        f"(war {lauf.triggered_count})"
    )
    eintraege = s.entries()
    assert len(eintraege) == 1, f"AC-3: genau ein Protokolleintrag erwartet: {eintraege!r}"
    e = eintraege[0]
    assert e["severity"] == "MODERATE", (
        f"AC-3: Dringlichkeit stammt aus Punkt 2 (MODERATE), nicht aus "
        f"Punkt 0/3/4 (HIGH): {e['severity']!r}"
    )
    assert e["lead_time_minutes"] == 20, f"AC-3: Vorwarnzeit aus Punkt 2 (20): {e!r}"
    assert e["source"] == "radar", f"AC-3: Quelle aus Punkt 2 (radar): {e['source']!r}"
    ende = (_UHR + timedelta(minutes=50)).isoformat()
    assert e["event_end_at"] == ende, (
        f"AC-3: Regenende aus Punkt 2 (+50 Min = {ende}): {e['event_end_at']!r}"
    )
    assert e["event_at"] == (_UHR + timedelta(minutes=20)).isoformat(), (
        f"AC-3: Beginn aus Punkt 2 (+20 Min): {e['event_at']!r}"
    )
    # Menge: die Vergleichsbasis der naechsten Runde (#2065) ist die Menge
    # dieses EINEN Abrufs.
    assert s.vergleichsbasis_mm() == pytest.approx(3.0), (
        f"AC-3: Vergleichsbasis = Menge von Punkt 2 (3,0 mm), nicht 9,0 (Punkt 0) "
        f"und nicht 8,0 (Max): {s.vergleichsbasis_mm()!r}"
    )
    # Capture-ID: gehoert zur Koordinate des gewaehlten Punkts.
    ids = s.radar.capture_ids
    assert ids.get(2) and ids.get(0) and ids[2] != ids[0], (
        f"Testvoraussetzung: der Radar-Fake hat je Punkt einen eigenen Mitschnitt "
        f"geschrieben: {ids!r}"
    )
    assert e.get("capture_id") == ids[2], (
        f"AC-3: die Mitschnitt-Capture-ID gehoert zur Koordinate des "
        f"massgeblichen Punkts 2 ({ids[2]!r}), nicht zu Punkt 0 ({ids[0]!r}): "
        f"{e.get('capture_id')!r}"
    )
    # Gewitter-Kennzeichen und Label in den Texten: Punkt 2 ist KEIN Gewitter.
    kanaele = _kanaele(lauf)
    # (Der Fuss „Regen-/Gewitter-Alarm“ steht in JEDER Radar-Mail und zaehlt
    # nicht — gemessen wird Kopfzeile und Intensitaetszeile.)
    assert "Regen in 20 Min" in kanaele["mail"] and "Gewitter in" not in kanaele["mail"] \
        and "Hagel" not in kanaele["mail"], (
        f"AC-3: Punkt 2 ist kein Gewitter — die Mail meldet `Regen in 20 Min`:\n{kanaele['mail']}"
    )
    assert "mäßiger Regen" in kanaele["mail"], (
        f"AC-3: Intensitaet aus Punkt 2 (maessig):\n{kanaele['mail']}"
    )
    assert "Radar (DWD)" in kanaele["mail"] and "INCA" not in kanaele["mail"], (
        f"AC-3: Quellen-Label aus Punkt 2 (radar):\n{kanaele['mail']}"
    )
    assert f"letzter Regen gegen {_ab_uhrzeit(_UHR, 50)}" in kanaele["mail"], (
        f"AC-3: Regenende aus Punkt 2:\n{kanaele['mail']}"
    )


# ---------------------------------------------------------------------------
# AC-4: nichts in Reichweite -> kein Alarm (Regressionsschutz, heute gruen)
# ---------------------------------------------------------------------------

def test_alle_trocken_kein_alarm(szenario):
    """AC-4 GIVEN alle Messpunkte sind trocken / WHEN der Pruflauf laeuft /
    THEN wird kein Alarm versendet und nichts protokolliert."""
    s = szenario("ac4-trocken")
    lauf = s.lauf({})
    assert lauf.triggered_count == 0, f"AC-4: trocken ⇒ kein Alarm: {lauf.triggered_count}"
    assert not s.entries(), f"AC-4: kein Versandeintrag: {s.entries()!r}"
    assert len(s.radar.abgerufen) >= 4, (
        f"Testvoraussetzung: die Folgepunkte wurden gemessen: {s.radar.abgerufen}"
    )


def test_beginn_jenseits_der_schwelle_an_allen_punkten_kein_alarm(szenario):
    """AC-4 GIVEN an ALLEN Punkten beginnt der Regen erst jenseits der
    Schwelle (#2261 A-1: 180 Min; vorher 55) / WHEN der Pruflauf laeuft /
    THEN kein Alarm. Auch nicht, wenn ein Punkt knapp daneben liegt (+1 Min).
    Die Ergebnisse sind gestellt — ueber die echte Quelle ist ein Beginn
    jenseits von 180 nicht konstruierbar (Gegenstueck mit echten Frames:
    `test_vorlauf_horizont.py`)."""
    s = szenario("ac4-spaet")
    lauf = s.lauf({
        0: nass(_SCHWELLE_MIN + 25), 1: nass(_SCHWELLE_MIN + 1),
        2: nass(_SCHWELLE_MIN + 5), 3: nass(_SCHWELLE_MIN + 65),
        4: nass(_SCHWELLE_MIN + 15),
    })
    assert lauf.triggered_count == 0, (
        f"AC-4: Beginn > {_SCHWELLE_MIN} Min an allen Punkten ⇒ kein Alarm: "
        f"{lauf.triggered_count}"
    )
    assert not s.entries(), f"AC-4: kein Versandeintrag: {s.entries()!r}"


# ---------------------------------------------------------------------------
# AC-5 / AC-6: Ausfall des ersten Messpunkts (PO-Entscheid b)
# ---------------------------------------------------------------------------

def _ausfall(art: str):
    if art == "ausnahme":
        return RuntimeError("Nowcast-Abruf fuer Punkt 0 absichtlich fehlgeschlagen")
    return NowcastResult(
        onset_minutes=None, intensity_label=INTENSITY_DRY, source="radar",
        data_unavailable=True,
    )


@pytest.mark.parametrize("art", ["ausnahme", "data_unavailable"])
def test_punkt0_ausfall_folgepunkt_nass_loest_alarm_aus(szenario, art):
    """AC-5 GIVEN der erste Messpunkt liefert keine Daten (Ausnahme bzw.
    `data_unavailable`) und Punkt 2 belegt Regen in 25 Min / WHEN der
    Pruflauf laeuft / THEN wird ein Alarm versendet; bei einer Ausnahme an
    Punkt 0 werden die Folgepunkte dafuer trotzdem abgerufen.

    Loest den Waechter von #2050 S4b AC-8 (`sent == 0`) in genau diesem
    Teil ab (PO-Entscheid b, 2026-10-02). RED heute: kein Alarm (Ausnahme:
    `continue` vor der Zonenschleife; `data_unavailable`: Ausstieg am
    ersten Punkt)."""
    s = szenario(f"ac5-{art}")
    lauf = s.lauf({0: _ausfall(art), 2: nass(25, menge=3.0, ende=55)})
    assert lauf.triggered_count == 1, (
        f"AC-5/{art}: ausgefallener Punkt 0 + belegt nasser Punkt 2 ⇒ Alarm "
        f"(war {lauf.triggered_count}); abgerufen: {s.radar.abgerufen}"
    )
    assert {1, 2, 3, 4}.issubset(set(s.radar.abgerufen)), (
        f"AC-5/{art}: die Folgepunkte muessen auch nach dem Ausfall an Punkt 0 "
        f"abgerufen werden: {s.radar.abgerufen}"
    )
    assert f"ab {_ab_uhrzeit(_UHR, 25)}" in _kanaele(lauf)["mail"], (
        f"AC-5/{art}: der Text nennt den Beginn AN PUNKT 2:\n{_kanaele(lauf)['mail']}"
    )


@pytest.mark.parametrize("art", ["ausnahme", "data_unavailable"])
def test_punkt0_ausfall_folgepunkte_trocken_kein_alarm_aber_protokoll(szenario, art):
    """AC-6 GIVEN der erste Messpunkt ist ausgefallen und alle Folgepunkte
    sind trocken oder ebenfalls ausgefallen (throttled/Ausnahme) / WHEN der
    Pruflauf laeuft / THEN kein Alarm UND der Lauf steht mit dem Grund
    `data_unavailable` im Alarmprotokoll (nie als „ruhig“ gewertet).

    Heute schon gruen (beide Ausfallwege protokollieren den Grund) —
    Regressionsschutz gegen einen Fix, der den Ausfall beim Folgepunkt-Abruf
    verschluckt."""
    s = szenario(f"ac6-{art}")
    lauf = s.lauf({
        0: _ausfall(art),
        2: NowcastResult(onset_minutes=None, intensity_label=INTENSITY_DRY,
                         source="radar", throttled=True),
        3: RuntimeError("Folgepunkt 3 ausgefallen"),
    })
    assert lauf.triggered_count == 0, (
        f"AC-6/{art}: ohne belegten Regen kein Alarm: {lauf.triggered_count}"
    )
    gruende = s.gruende(_UHR - timedelta(minutes=1))
    assert alert_log.REASON_DATA_UNAVAILABLE in gruende, (
        f"AC-6/{art}: der Ausfall muss mit `{alert_log.REASON_DATA_UNAVAILABLE}` "
        f"protokolliert sein, nicht als ruhige Viertelstunde: {gruende!r}"
    )


# ---------------------------------------------------------------------------
# AC-7: Budget-Druck unveraendert (Regressionsschutz, heute gruen)
# ---------------------------------------------------------------------------

def test_punkt0_throttled_kein_zusatzabruf_kein_alarm(szenario):
    """AC-7 GIVEN der erste Messpunkt ist `throttled` (Budget-Druck, #1329) —
    und die Folgepunkte waeren nass / WHEN der Pruflauf laeuft / THEN wird
    kein Alarm versendet und es entstehen keine ZUSAETZLICHEN Abrufe: jeder
    Punkt wird hoechstens einmal abgerufen, mit Prioritaet `polling`.

    „Wie vor dieser Aenderung“ heisst hier: der Lauf ruft heute alle Punkte
    EINMAL ab (Punkt 0, dann die Zonenschleife). Der Test pinnt das als
    Obergrenze (`<=` Punktzahl, kein Index doppelt), nicht als exakte Zahl.
    Die nassen Folgepunkte machen den Test scharf: eine Auswahl, die
    `throttled` an Punkt 0 uebergeht, wuerde hier ausloesen.
    HEUTE GRUEN."""
    s = szenario("ac7")
    lauf = s.lauf({
        0: NowcastResult(onset_minutes=None, intensity_label=INTENSITY_DRY,
                         source="radar", throttled=True),
        1: nass(10), 2: nass(20), 3: nass(30),
    })
    assert lauf.triggered_count == 0, (
        f"AC-7: Budget-Druck an Punkt 0 ⇒ kein Alarm, auch bei nassen "
        f"Folgepunkten: {lauf.triggered_count}"
    )
    abgerufen = s.radar.abgerufen
    assert len(abgerufen) == len(set(abgerufen)) <= len(s.soll()), (
        f"AC-7: kein Punkt darf mehrfach abgerufen werden (Zusatzabruf): {abgerufen}"
    )
    assert abgerufen.count(0) == 1, f"AC-7: Punkt 0 genau einmal: {abgerufen}"
    assert all(a["priority"] == "polling" for a in s.radar.aufrufe), (
        f"AC-7: alle Scheduler-Abrufe laufen mit Prioritaet `polling` (drosselbar): "
        f"{[a['priority'] for a in s.radar.aufrufe]}"
    )


# ---------------------------------------------------------------------------
# AC-8: Sperren bleiben wirksam; Verschaerfung am Folgepunkt durchbricht
# ---------------------------------------------------------------------------

def _identitaets_stufen(s: "_Szenario") -> list[dict]:
    from services.alert_state import AlertStateService

    register = AlertStateService(s.uid).load(s.trip.id)
    return [
        eintrag for schluessel, eintrag in register.items()
        if schluessel.startswith("event_identity:") and isinstance(eintrag, dict)
    ]


def test_sperrzeit_tageslimit_identitaet_wirken_mit_folgepunkt(szenario):
    """AC-8 GIVEN ein Folgepunkt hat einen Alarm ausgeloest / WHEN im naechsten
    Lauf wieder derselbe Folgepunkt ausloest / THEN greifen Sperrzeit,
    Tageslimit und Ereignis-Identitaet unveraendert — kein zweiter Alarm.

    Teil A (Sperrzeit): Lauf 1 alarmiert wegen Punkt 2, Lauf 2 (+30 Min,
    gleiche Lage) schweigt mit Grund `cooldown`.
    Teil B (Identitaet): das Ereignis-Register von Lauf 1 traegt die Stufe des
    MASSGEBLICHEN Punkts (MODERATE), nicht die des ausser Reichweite nassen
    Punkts 0 (HIGH) — die Identitaet haengt am Abruf, der den Alarm trug.
    Teil C (Tageslimit): ein Nutzer mit erschoepftem Tagesbudget bekommt auch
    bei einem Folgepunkt keinen Alarm; Grund `daily_limit`.

    RED heute: schon die Vorbedingung — ein Folgepunkt-Alarm — fehlt."""
    s = szenario("ac8-sperre")
    punkt0 = nass(80, menge=0.5, ende=150, label=INTENSITY_HEAVY)
    lauf1 = s.lauf({0: punkt0, 2: nass(25, menge=3.0, ende=55)})
    assert lauf1.triggered_count == 1, (
        "AC-8 Vorbedingung (#2480-Verhalten fehlt): Lauf 1 muss durch den "
        f"Folgepunkt alarmieren (war {lauf1.triggered_count})"
    )
    stufen = [e.get("severity") for e in _identitaets_stufen(s)]
    assert stufen == ["MODERATE"], (
        f"AC-8/B: die Ereignis-Identitaet traegt die Stufe des massgeblichen "
        f"Punkts 2 (MODERATE), nicht die von Punkt 0 (HIGH): {stufen!r}"
    )

    at2 = _UHR + timedelta(minutes=30)
    lauf2 = s.lauf({0: punkt0, 2: nass(25, menge=3.0, ende=55)}, at=at2)
    assert lauf2.triggered_count == 0, (
        f"AC-8/A: im Sperrfenster kein zweiter Alarm fuer dasselbe Ereignis "
        f"(war {lauf2.triggered_count})"
    )
    assert alert_log.REASON_COOLDOWN in s.gruende(at2 - timedelta(minutes=1)), (
        f"AC-8/A: Grund `cooldown` erwartet: {s.gruende(at2 - timedelta(minutes=1))!r}"
    )

    # Teil C: Tageslimit (Tier `standard`, Limit 4), Budget erschoepft.
    from services.trip_day import anchor_tz
    from tests.tdd.test_daily_budget_escalation import (
        TIER_MIT_BUDGET, _budget_ausschoepfen,
    )

    # Ohne Vorlauf wuerde ein NICHT erschoepfter Tag mit „noch nichts
    # zugestellt“ (= LOW) jede Stufe als Eskalation durchlassen (#2050 S3b) —
    # deshalb erst ein echter Folgepunkt-Alarm (bucht die zugestellte Stufe
    # MODERATE), dann das Budget leeren, dann eine mengenmaessige
    # Verschaerfung OHNE Stufenwechsel (MODERATE bleibt MODERATE).
    limit = szenario("ac8-limit", tier=TIER_MIT_BUDGET)
    lauf_l1 = limit.lauf({2: nass(25, menge=3.0, ende=55)})
    assert lauf_l1.triggered_count == 1, (
        f"AC-8/C Vorbedingung: Lauf 1 (Tier standard) alarmiert durch Punkt 2 "
        f"(war {lauf_l1.triggered_count})"
    )
    at_l = _UHR + timedelta(minutes=60)
    _budget_ausschoepfen(limit.uid, at_l, anchor_tz(limit.trip, at_l))
    lauf_l2 = limit.lauf({2: nass(25, menge=7.0, ende=55)}, at=at_l)
    assert lauf_l2.triggered_count == 0, (
        f"AC-8/C: erschoepftes Tagesbudget haelt auch bei einem Folgepunkt, "
        f"wenn die Verschaerfung keine Eskalation der Stufe ist "
        f"(war {lauf_l2.triggered_count})"
    )
    gruende = limit.gruende(at_l - timedelta(minutes=1))
    assert alert_log.REASON_DAILY_LIMIT in gruende, (
        f"AC-8/C: Grund `daily_limit` erwartet: {gruende!r}"
    )


def test_verschaerfung_am_folgepunkt_durchbricht_sperrzeit(szenario):
    """AC-8 GIVEN Lauf 1 hat wegen Punkt 2 (3,0 mm) alarmiert / WHEN Lauf 2
    (+60 Min, innerhalb der Sperrzeit) an Punkt 2 eine echte Verschaerfung
    (7,0 mm >= 2 x 3,0 und >= 2 mm, #2065) misst / THEN durchbricht sie die
    Sperrzeit — gemessen mit der Menge des MASSGEBLICHEN Punkts.

    Punkt 0 bleibt ueber beide Laeufe klein (0,5 mm) und ausser Reichweite:
    liest die Ueberholungs-Entscheidung die Menge von Punkt 0, bleibt die
    Sperrzeit bestehen (Mutation „Menge weiter aus Punkt 0“). Nach Lauf 1
    ist die Vergleichsbasis die Menge von Punkt 2, nicht die von Punkt 0.

    RED heute: Lauf 1 alarmiert gar nicht (Vorbedingung)."""
    s = szenario("ac8-verschaerfung")
    punkt0 = nass(80, menge=0.5, ende=150)
    lauf1 = s.lauf({0: punkt0, 2: nass(25, menge=3.0, ende=55)})
    assert lauf1.triggered_count == 1, (
        "AC-8 Vorbedingung (#2480-Verhalten fehlt): Lauf 1 muss durch den "
        f"Folgepunkt alarmieren (war {lauf1.triggered_count})"
    )
    assert s.vergleichsbasis_mm() == pytest.approx(3.0), (
        f"AC-8: nach Lauf 1 ist die Vergleichsbasis die Menge des "
        f"massgeblichen Punkts (3,0 mm): {s.vergleichsbasis_mm()!r}"
    )

    at2 = _UHR + timedelta(minutes=60)
    lauf2 = s.lauf({0: punkt0, 2: nass(25, menge=7.0, ende=55)}, at=at2)
    assert lauf2.triggered_count == 1, (
        f"AC-8: 7,0 mm gegen eine Basis von 3,0 mm (Faktor 2,33, ueber 2 mm) "
        f"muessen die Sperrzeit durchbrechen, gemessen am Folgepunkt "
        f"(war {lauf2.triggered_count}); Gruende: "
        f"{s.gruende(at2 - timedelta(minutes=1))!r}"
    )
    assert lauf2.mail and lauf2.telegram and lauf2.sms and lauf2.premium_sms, (
        f"AC-8: der Durchbruch erreicht alle vier Kanaele: mail={lauf2.mail!r} "
        f"telegram={lauf2.telegram!r} sms={lauf2.sms!r} premium={lauf2.premium_sms!r}"
    )
    assert s.vergleichsbasis_mm() == pytest.approx(7.0), (
        f"AC-8: nach dem Durchbruch ist die neue Basis die Menge des "
        f"massgeblichen Punkts (7,0 mm): {s.vergleichsbasis_mm()!r}"
    )


# ---------------------------------------------------------------------------
# AC-9: Punktwechsel ohne Verschaerfung (Pflicht-Test, nicht aufweichen)
# ---------------------------------------------------------------------------

def test_punktwechsel_ohne_verschaerfung_kein_zweiter_alarm(szenario):
    """AC-9 GIVEN der erste Lauf hat wegen Punkt 2 alarmiert / WHEN im zweiten
    Lauf (+30 Min, Sperrzeit, gleiches Ereignis) wegen Messwert-Schwankung
    Punkt 3 statt Punkt 2 massgeblich wird — Menge 4,0 mm (groesser als die
    3,0 mm von Lauf 1, aber unter dem Doppelten), gleiche Dringlichkeit —
    THEN wird KEIN zweiter Alarm versendet, Grund `cooldown`.

    FAELLT DIESER TEST NACH DEM FIX ROT, IST DAS EIN SPEC-BEFUND (Stickiness
    wird dann in der Spec nachgezogen) — kein Grund, ihn aufzuweichen.
    RED heute: Lauf 1 alarmiert gar nicht (Vorbedingung)."""
    s = szenario("ac9")
    lauf1 = s.lauf({2: nass(25, menge=3.0, ende=55)})
    assert lauf1.triggered_count == 1, (
        "AC-9 Vorbedingung (#2480-Verhalten fehlt): Lauf 1 muss durch Punkt 2 "
        f"alarmieren (war {lauf1.triggered_count})"
    )
    at2 = _UHR + timedelta(minutes=30)
    lauf2 = s.lauf({3: nass(30, menge=4.0, ende=60)}, at=at2)
    assert lauf2.triggered_count == 0, (
        f"AC-9: Wechsel des massgeblichen Punkts (2 -> 3) OHNE Verschaerfung "
        f"darf keinen zweiten Alarm ausloesen (war {lauf2.triggered_count}); "
        f"abgerufen: {s.radar.abgerufen}"
    )
    gruende = s.gruende(at2 - timedelta(minutes=1))
    assert alert_log.REASON_COOLDOWN in gruende, (
        f"AC-9: die Stille kommt von der Sperrzeit (`cooldown`), nicht von "
        f"einem anderen Grund: {gruende!r}"
    )


# ---------------------------------------------------------------------------
# AC-10: Alarmprotokoll nennt den ausloesenden Punkt
# ---------------------------------------------------------------------------

def test_e1_protokoll_nennt_km_des_ausloesenden_punkts(szenario):
    """AC-10 GIVEN ein Alarm wurde durch Punkt 3 ausgeloest / WHEN der
    Alarmprotokolleintrag geschrieben wird / THEN enthaelt er zusaetzlich
    `trigger_point_km` = Streckenkilometer dieses Punkts (Entfernung von WP0
    auf der geraden Nord-Strecke, unabhaengig vom Pruefling gerechnet; die
    Rundung legt die Spec nicht fest, daher +-0,06 km) — alle bisherigen
    Felder bleiben unveraendert (`measurement_point` ist weiter das
    SEGMENT-km).

    RED heute: kein Alarm (Punkt 0 trocken) bzw. kein Feld."""
    s = szenario("ac10")
    lauf = s.lauf({3: nass(25, menge=3.0, ende=55)})
    assert lauf.triggered_count == 1, (
        f"AC-10 Vorbedingung (#2480-Verhalten fehlt): Alarm durch Punkt 3 "
        f"(war {lauf.triggered_count})"
    )
    e = s.entries()[0]
    assert "trigger_point_km" in e, (
        f"AC-10: Eintrag muss `trigger_point_km` tragen: {sorted(e)!r}"
    )
    assert e["trigger_point_km"] == pytest.approx(s.km(3), abs=0.06), (
        f"AC-10: `trigger_point_km` = km des Punkts 3 ({s.km(3):.2f}), nicht "
        f"der von Punkt 0 ({s.km(0):.2f}): {e['trigger_point_km']!r}"
    )
    assert e["measurement_point"] == {"segment_id": "1", "km_from": 0.0, "km_to": 23.996}, (
        f"AC-10: `measurement_point` bleibt das SEGMENT-km: {e['measurement_point']!r}"
    )
    assert e["lead_time_minutes"] == 25 and e["source"] == "radar", (
        f"AC-10: die bisherigen E-1-Felder bleiben unveraendert: {e!r}"
    )


def test_e1_felder_rueckwaertskompatibel():
    """AC-10 GIVEN ein Alteintrag OHNE `trigger_point_km` (Altbestand bzw.
    Alarm durch Punkt 0) / WHEN ein neuer Eintrag MIT dem Feld angehaengt
    wird / THEN bleibt der alte Eintrag unveraendert und lesbar, der neue
    traegt das Feld; ein falsch geformter Wert (kein float) laesst nur das
    Feld weg (additiv-defensiv, wirft nie).

    Der Schreibweg ist `alert_log.append_entry` (dieselbe Funktion wie im
    Produktivlauf), der Leseweg die Datei, die auch die Go-Seite liest; zusaetzlich
    `read_undelivered` als Python-Leseweg des Nicht-Zustellungs-Teils."""
    uid = _uid("ac10-alt")
    _clean_user(uid)
    try:
        gemeinsam = dict(
            entity_id="trip-ac10", entity_type="trip", changes_count=1,
            severity="MODERATE", metrics=alert_log.register_pairs_for_nowcast(False),
            reason=alert_log.REASON_NOWCAST, effective_channels=["email"],
            sent_channels=["email"], lead_time_minutes=20,
            event_at="2026-08-18T10:20:00+00:00", source="radar",
            measurement_point={"segment_id": "1", "km_from": 0.0, "km_to": 3.0},
        )
        alert_log.append_entry(uid, **gemeinsam)
        try:
            alert_log.append_entry(uid, trigger_point_km=4.2, **gemeinsam)
        except TypeError as fehler:
            pytest.fail(
                f"AC-10: `append_entry` kennt `trigger_point_km` nicht: {fehler}"
            )
        alert_log.append_entry(uid, trigger_point_km="vier", **gemeinsam)

        pfad = get_data_dir(uid) / "alert_log.json"
        eintraege = json.loads(pfad.read_text())["entries"]
        assert len(eintraege) == 3, f"drei Eintraege erwartet: {eintraege!r}"
        alt, neu, kaputt = eintraege
        assert "trigger_point_km" not in alt and alt["lead_time_minutes"] == 20, (
            f"AC-10: der Alteintrag bleibt ohne das Feld und lesbar: {alt!r}"
        )
        assert neu.get("trigger_point_km") == pytest.approx(4.2) and neu["source"] == "radar", (
            f"AC-10: der neue Eintrag traegt das Feld UND alle alten: {neu!r}"
        )
        assert "trigger_point_km" not in kaputt and kaputt["source"] == "radar", (
            f"AC-10: ein falsch geformter Wert laesst nur das Feld weg: {kaputt!r}"
        )
    finally:
        _clean_user(uid)


# ---------------------------------------------------------------------------
# AC-11: alle vier Kanaele, derselbe Pfad
# ---------------------------------------------------------------------------

def test_folgepunkt_alarm_erreicht_alle_vier_kanaele(szenario):
    """AC-11 GIVEN ein Alarm wird durch Punkt 2 ausgeloest (Beginn 25 Min,
    Ende 55 Min; Punkt 0 und 1 trocken) und der Nutzer hat Mail, Telegram,
    SMS und Premium-SMS / WHEN der Alarm versendet wird / THEN tragen ALLE
    vier Kanaele denselben Beginn (Ortszeit, aus gestellter Uhr + Beginn
    gerechnet: `ab HH:MM` bzw. `@HH:MM`) und denselben Zonen-Ort — und KEIN
    Kanal behauptet den Beginn am Standort: Der Ort ist ausschliesslich die
    Nass-Zone von Punkt 2 (`km 10-10`), die Standort-Position (Punkt 0,
    km 6) kommt nicht als nasse Stelle vor.

    RED heute: kein Alarm."""
    import re

    s = szenario("ac11")
    lauf = s.lauf({2: nass(25, menge=3.0, ende=55)})
    assert lauf.triggered_count == 1, (
        f"AC-11: Alarm durch Punkt 2 erwartet (war {lauf.triggered_count})"
    )
    kanaele = _kanaele(lauf)
    assert all(kanaele.values()), f"AC-11: jeder der vier Kanaele traegt Inhalt: {kanaele!r}"

    beginn = _ab_uhrzeit(_UHR, 25)
    ende = _ab_uhrzeit(_UHR, 55)
    standort_km = round(s.km(0))
    zone_km = round(s.km(2))
    assert standort_km != zone_km, "Testvoraussetzung: Standort und Zone liegen auseinander"

    assert f"ab {beginn}" in kanaele["mail"], f"Mail: `ab {beginn}`:\n{kanaele['mail']}"
    assert beginn in kanaele["telegram"], f"Telegram: `{beginn}`:\n{kanaele['telegram']}"
    for name in ("sms", "premium_sms"):
        assert f"@{beginn}" in kanaele[name], f"{name}: `@{beginn}`: {kanaele[name]!r}"
    # Der Beginn steht NICHT in einer Form, die einen Standort-Beginn zu
    # frueherer Uhrzeit behauptet: keine andere Beginn-Uhrzeit als die von Punkt 2.
    for name in ("mail", "telegram", "sms", "premium_sms"):
        zeiten = set(re.findall(r"\b(\d{2}:\d{2})\b", kanaele[name])) - {ende}
        assert zeiten <= {beginn, "12:00"}, (
            f"AC-11/{name}: ausser Beginn ({beginn}), Ende ({ende}) und dem "
            f"Stand (12:00) darf keine Uhrzeit vorkommen: {sorted(zeiten)}"
        )
    # Zonen-Ort in allen vier Kanaelen — und nur der von Punkt 2.
    for name, muster in (
        ("mail", rf"Nass km {zone_km}-{zone_km}(?!\d)"),
        ("telegram", rf"Nass km {zone_km}-{zone_km}(?!\d)"),
        ("sms", rf"km{zone_km}-{zone_km}(?!\d)"),
        ("premium_sms", rf"km{zone_km}-{zone_km}(?!\d)"),
    ):
        assert re.search(muster, kanaele[name]), (
            f"AC-11/{name}: Zonen-Ort `{muster}` fehlt: {kanaele[name]!r}"
        )
        assert not re.search(rf"km ?{standort_km}-{standort_km}(?!\d)", kanaele[name]), (
            f"AC-11/{name}: der Standort (km {standort_km}) darf nicht als "
            f"nasse Stelle erscheinen: {kanaele[name]!r}"
        )
    assert kanaele["sms"] == kanaele["premium_sms"], (
        f"AC-11: SMS und Premium-SMS tragen dieselbe Aussage:\n"
        f"{kanaele['sms']!r}\n{kanaele['premium_sms']!r}"
    )


