"""Amtliche Warnung mit zwei gleichzeitig gueltigen Nachbarperioden wird nicht
mehrfach gemeldet (Issue #3470).

SPEC:    docs/specs/modules/fix_3470_amtlich_nachbarperioden.md (AC-1..AC-10)
KONTEXT: docs/context/fix-3470-amtlich-pingpong.md

Prod 27.11.2026: Meteoalarm liefert dieselbe Kaeltewarnung als zwei
aneinandergrenzende, gleichzeitig gueltige Perioden A (12-16 Uhr) und B
(16-12 Uhr Folgetag). ``official_alert_revision_verdict`` sucht auch bei
exaktem Schluesseltreffer Kandidaten, die Aufrufer loeschen den Kandidaten
(``del state[stale_key]``) -- A und B verdraengen sich im Melde-Gedaechtnis
gegenseitig, und A wird als "Vorverlegung >= 2 h" gegen B immer wieder neu
gemeldet (Ping-Pong). Zweitbefund: ``build_official_allclear_notices``
entdoppelt Entwarnungen nicht -- liegen A und B im Gedaechtnis, kommen zwei
Entwarnungen fuer eine Warnung.

Mehrlauf-Simulation aus Nutzersicht: je Lauf laeuft der ECHTE Aufrufer
(Trip: ``TripAlertService.check_official_alert_triggers``; Vergleich:
``CompareOfficialAlertService._detect``). Die "Zustellung" schreibt das
Gedaechtnis ueber den ECHTEN Schreibweg (Trip:
``_record_official_alert_state`` -> ``alert_briefing_anchor.
record_official_alerts_reported``; Vergleich: ``_record_state``; Entwarnung:
``_apply_official_allclears`` bzw. ``_apply_allclears``). Gezaehlt werden die
gemeldeten Warnungen je Lauf bzw. die erzeugten Entwarnungs-Notices.

Mock-frei: echte ``OfficialAlert``-DTOs, echte Quellen in der echten Registry
(Protocol-Subtyping), echtes Dateigedaechtnis ``AlertStateService(user_id=...)``
(die Datenwurzel liegt per ``tests/conftest.py`` in einem tmp-Verzeichnis).

Uhr: ``check_official_alert_triggers`` ueberschreibt ``now_utc`` intern mit der
Wanduhr -- die Trip-Perioden liegen deshalb relativ zur echten Jetzt-Minute.
``_detect`` hat keine injizierbare Zeit; der Vergleich friert wie die
Bestandstests (``test_official_alert_revision_dedup._freeze_compare_now``) das
Modul-``datetime`` ein.
"""
from __future__ import annotations

import json
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone

import pytest

from app.models import (
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    TripReportConfig,
    TripSegment,
)
from app.trip import Stage, Trip, Waypoint
from app.user import SavedLocation
from output.renderers.alert.official_alerts import (
    build_official_allclear_notices,
    official_alert_state_key,
)
from services.alert_state import AlertStateService
from services.official_alerts.models import OfficialAlert
from tests.helpers.ortstag import ortstag

LAT, LON = 47.0, 11.0
LAT_Y, LON_Y = 49.0, 13.0
REGION = "Stadt-Muenster-3470"
GEFAHR = "extreme_cold"  # wie der Prod-Fall; keine `wet`-Gefahr (kein Ereignis-Register)
PRAEFIX = f"official_alert:region:{REGION}:{GEFAHR}:"
REIHENFOLGEN = [pytest.param("AB", id="feed-A-B"), pytest.param("BA", id="feed-B-A")]
LAEUFE = 4


# ---------------------------------------------------------------------------
# Bausteine
# ---------------------------------------------------------------------------


def _fresh_user(prefix: str) -> str:
    return f"fix3470-{prefix}-{uuid.uuid4().hex[:6]}"


def _warnung(vf: datetime | None, vt: datetime | None, level: int = 2, *,
             region: str = REGION) -> OfficialAlert:
    return OfficialAlert(source="test-3470", hazard=GEFAHR, level=level,
                         label="Kaeltewarnung (#3470)", region_label=region,
                         valid_from=vf, valid_to=vt)


class _FeedQuelle:
    """Echte amtliche Quelle (Protocol-Subtyping, kein Mock) mit frei
    belegbarer Feed-Liste ``alerts`` -- die Reihenfolge der Liste ist die
    Feed-Reihenfolge."""

    def __init__(self, name: str, lat: float, lon: float, alerts=()) -> None:
        self.name = name
        self._lat, self._lon = lat, lon
        self.alerts: list = list(alerts)

    def covers(self, lat: float, lon: float) -> bool:
        return abs(lat - self._lat) < 0.5 and abs(lon - self._lon) < 0.5

    def fetch(self, lat: float, lon: float, **_kw) -> list:
        return list(self.alerts)


@contextmanager
def _nur_quellen(*qs):
    """Registry leeren, nur ``qs`` registrieren, danach Bestand zurueck."""
    import services.official_alerts.base as base
    from services.official_alerts import register_official_alert_source

    sicherung = list(base._REGISTERED_SOURCES)
    base._REGISTERED_SOURCES.clear()
    for q in qs:
        register_official_alert_source(q)
    try:
        yield qs
    finally:
        base._REGISTERED_SOURCES.clear()
        base._REGISTERED_SOURCES.extend(sicherung)


def _eintraege(user_id: str, entity_id: str) -> dict:
    state = AlertStateService(user_id=user_id).load(entity_id)
    return {k: v for k, v in state.items() if k.startswith(PRAEFIX)}


def _feed(order: str, a: OfficialAlert, b: OfficialAlert) -> list:
    return [a, b] if order == "AB" else [b, a]


# ---- Trip ------------------------------------------------------------------


def _jetzt_minute() -> datetime:
    return datetime.now(timezone.utc).replace(second=0, microsecond=0)


def _perioden(t: datetime) -> tuple[tuple[datetime, datetime], tuple[datetime, datetime]]:
    """A = 12-16 Uhr, B = 16-12 Uhr Folgetag (Prod-Form), relativ zu ``t``:
    A laeuft gerade, B schliesst nahtlos an (Ende A == Beginn B)."""
    return (t - timedelta(hours=1), t + timedelta(hours=3)), (t + timedelta(hours=3), t + timedelta(hours=23))


def _minimal_trip(trip_id: str) -> Trip:
    stage = Stage(
        id="T1", name="Tag 1", date=date(2026, 11, 27),
        waypoints=[Waypoint(id="G1", name="Start", lat=LAT, lon=LON, elevation_m=1000.0)],
    )
    trip = Trip(id=trip_id, name="Nachbarperioden-Trip", stages=[stage], official_warnings=None)
    trip.report_config = TripReportConfig(trip_id=trip_id, send_email=True)
    return trip


def _save_cached(user_id: str, trip_id: str) -> None:
    """Routen-Geometrie (Segment jetzt-2h..jetzt+48h) -- ohne Schnappschuss
    erreicht ``check_official_alert_triggers`` keine Warnquelle."""
    from services.weather_snapshot import WeatherSnapshotService

    now = datetime.now(timezone.utc)
    segment = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=LAT, lon=LON, elevation_m=1000, distance_from_start_km=0.0),
        end_point=GPXPoint(lat=LAT + 0.1, lon=LON + 0.1, elevation_m=1500, distance_from_start_km=8.0),
        start_time=now - timedelta(hours=2), end_time=now + timedelta(hours=48),
        duration_hours=4.0, distance_km=8.0, ascent_m=500, descent_m=0,
    )
    data = SegmentWeatherData(
        segment=segment,
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=1.0), data=[],
        ),
        aggregated=SegmentWeatherSummary(precip_sum_mm=2.0),
        fetched_at=now, provider="openmeteo",
    )
    WeatherSnapshotService(user_id=user_id).save_dated(trip_id, ortstag(LAT, LON), [data])


class _TripNutzer:
    """Ein Nutzer mit einem Trip; ``lauf()`` = ein regulaerer Alarm-Lauf mit
    anschliessender Zustellung (echte Schreibwege)."""

    def __init__(self, prefix: str, trip_id: str | None = None) -> None:
        from services.trip_alert import TripAlertService

        self.user_id = _fresh_user(prefix)
        self.trip = _minimal_trip(trip_id or f"trip-3470-{prefix}")
        _save_cached(self.user_id, self.trip.id)
        self.svc = TripAlertService(user_id=self.user_id)

    def lauf(self) -> tuple[list, list]:
        """Liefert ``(gemeldete Warnungen, Entwarnungs-Notices)`` dieses Laufs."""
        gemeldet = self.svc.check_official_alert_triggers(self.trip)
        allclears = list(self.svc._pending_official_allclears)
        notices = build_official_allclear_notices(allclears)
        if gemeldet:
            # Zustellung: DER Schreibweg des echten Versands
            # (record_official_alerts_reported, alert_briefing_anchor.py).
            self.svc._record_official_alert_state(self.trip.id, gemeldet)
        if allclears:
            self.svc._apply_official_allclears(self.trip.id, allclears)
        return [a for a, _seg in gemeldet], notices

    def eintraege(self) -> dict:
        return _eintraege(self.user_id, self.trip.id)

    def rohtext(self) -> str:
        return AlertStateService(user_id=self.user_id)._path(self.trip.id).read_text()


def _melde_folge(nutzer: _TripNutzer, laeufe: int = LAEUFE) -> list[list]:
    return [nutzer.lauf()[0] for _ in range(laeufe)]


def _trip_erstmeldung(nutzer: _TripNutzer, quelle: _FeedQuelle, a: OfficialAlert) -> str:
    """Lauf 0: nur A im Feed, A wird gemeldet und zugestellt. Liefert den
    ``reported_at`` von A."""
    quelle.alerts = [a]
    gemeldet, _ = nutzer.lauf()
    assert len(gemeldet) == 1, f"Vorbedingung: Erstmeldung von A muss neu sein: {gemeldet!r}"
    eintraege = nutzer.eintraege()
    assert set(eintraege) == {official_alert_state_key(a)}, f"Vorbedingung Gedaechtnis {{A}}: {eintraege!r}"
    return eintraege[official_alert_state_key(a)]["reported_at"]


# ---- Ortsvergleich -----------------------------------------------------------

COMPARE_FROZEN = datetime(2026, 8, 11, 6, 0, tzinfo=timezone.utc)


def _freeze_compare_now(monkeypatch, frozen: datetime) -> None:
    # Muster test_official_alert_revision_dedup.py / test_compare_official_alert.py.
    import services.compare_official_alert as coa_mod

    class _Frozen(datetime):
        @classmethod
        def now(cls, tz=None):
            return frozen.astimezone(tz) if tz else frozen.replace(tzinfo=None)

    monkeypatch.setattr(coa_mod, "datetime", _Frozen)


class _VergleichsUhr:
    """Eingefrorene Uhr des Vergleichs-Moduls, die je Lauf um 15 Minuten
    weiterlaeuft (Takt des Alarm-Crons). Ohne Fortschritt traegen alle
    Gedaechtnis-Eintraege denselben ``reported_at`` und der Tie-Break der
    Kandidatenwahl verliefe anders als im Betrieb."""

    def __init__(self, monkeypatch, start: datetime) -> None:
        self._mp, self.jetzt = monkeypatch, start
        _freeze_compare_now(self._mp, self.jetzt)

    def weiter(self, minuten: int = 15) -> None:
        self.jetzt += timedelta(minutes=minuten)
        _freeze_compare_now(self._mp, self.jetzt)


def _compare_service(user_id: str):
    from app.config import Settings
    from services.compare_official_alert import CompareOfficialAlertService

    settings = Settings(smtp_host="dummy.invalid", smtp_user="dummy", smtp_pass="dummy",
                        mail_to="dummy@example.com")
    return CompareOfficialAlertService(settings=settings, user_id=user_id, mail_sink=lambda *a: None)


def _vergleich_lauf(svc, preset_id: str, locs: list, uhr: _VergleichsUhr) -> tuple[list, list]:
    """Ein Ortsvergleich-Lauf (15 Minuten nach dem vorigen) mit Zustellung
    (echte Schreibwege ``_record_state``/``_apply_allclears``)."""
    uhr.weiter()
    neu, per_loc = svc._detect(preset_id, locs)
    pending = list(svc._pending_allclears)
    notices = build_official_allclear_notices(
        [ac for ac, _l in pending], {loc.id: loc.name for loc in locs},
    )
    if neu:
        svc._record_state(preset_id, per_loc)
    if pending:
        svc._apply_allclears(preset_id, pending)
    return [a for a, _l in neu], notices


# ===========================================================================
# AC-1 -- Kernfall: kein Ping-Pong, beide Perioden bleiben im Gedaechtnis
# ===========================================================================


@pytest.mark.parametrize("order", REIHENFOLGEN)
def test_ac1_nachbarperioden_melden_nach_der_ersten_meldung_nie_wieder(order):
    """AC-1 (Kernfall, RED): Gedaechtnis {A}, Feed liefert A und B
    gleichzeitig. In vier Laeufen darf keine erneute Meldung kommen, und beide
    Perioden stehen danach im Gedaechtnis. Heute: A wird gegen B als
    Vorverlegung neu gemeldet (A,B: jeder zweite Lauf; B,A: jeder Lauf)."""
    t = _jetzt_minute()
    (a_vf, a_vt), (b_vf, b_vt) = _perioden(t)
    a, b = _warnung(a_vf, a_vt), _warnung(b_vf, b_vt)
    quelle = _FeedQuelle("quelle-3470-ac1", LAT, LON)
    with _nur_quellen(quelle):
        nutzer = _TripNutzer(f"ac1-{order}")
        _trip_erstmeldung(nutzer, quelle, a)

        quelle.alerts = _feed(order, a, b)
        folge = _melde_folge(nutzer)

    anzahl = [len(r) for r in folge]
    assert anzahl == [0] * LAEUFE, (
        f"Feed {order}: erwartet keine erneute Meldung in Lauf 1-{LAEUFE}, gemeldet je Lauf: {anzahl}"
    )
    assert set(nutzer.eintraege()) == {official_alert_state_key(a), official_alert_state_key(b)}, (
        f"Beide Perioden muessen im Gedaechtnis bleiben: {sorted(nutzer.eintraege())}"
    )


# ===========================================================================
# AC-2 -- Bestandsgedaechtnis aus der Zeit vor dem Fix: {B mit reported_at von A}
# ===========================================================================


@pytest.mark.parametrize("order", REIHENFOLGEN)
def test_ac2_bestandsgedaechtnis_nur_b_loest_keinen_letzten_doppelalarm_aus(order):
    """AC-2 (Kernfall, RED): das Gedaechtnis enthaelt -- wie es der heutige
    Code nach einer stillen Revision A->B hinterlaesst -- nur B mit dem
    ``reported_at`` von A. Liefert der Feed danach A und B, darf die Warnung
    nicht noch einmal gemeldet werden. Der Bestandszustand wird ueber die
    echten Laeufe hergestellt (Feed {A}, dann Feed {B}), nicht von Hand."""
    t = _jetzt_minute()
    (a_vf, a_vt), (b_vf, b_vt) = _perioden(t)
    a, b = _warnung(a_vf, a_vt), _warnung(b_vf, b_vt)
    quelle = _FeedQuelle("quelle-3470-ac2", LAT, LON)
    with _nur_quellen(quelle):
        nutzer = _TripNutzer(f"ac2-{order}")
        reported_a = _trip_erstmeldung(nutzer, quelle, a)
        quelle.alerts = [b]
        still, _ = nutzer.lauf()
        assert still == [], f"Vorbedingung: B allein ist eine stille Revision: {still!r}"
        bestand = nutzer.eintraege()
        assert set(bestand) == {official_alert_state_key(b)}, f"Vorbedingung Gedaechtnis {{B}}: {bestand!r}"
        assert bestand[official_alert_state_key(b)]["reported_at"] == reported_a

        quelle.alerts = _feed(order, a, b)
        folge = _melde_folge(nutzer)

    anzahl = [len(r) for r in folge]
    assert anzahl == [0] * LAEUFE, (
        f"Feed {order} gegen Bestand {{B*}}: erwartet 0 Meldungen in Lauf 1-{LAEUFE}, gemeldet je Lauf: {anzahl}"
    )


# ===========================================================================
# AC-3 -- echte Neuausgabe bleibt stille Revision (Regressionsschutz #1685/#1657)
# ===========================================================================


@pytest.mark.parametrize("art", ["beruehrt", "ueberlappt"])
def test_ac3_echte_neuausgabe_ersetzt_alte_periode_still(art):
    """AC-3 (Regressionsschutz, heute gruen): A wurde gemeldet und
    verschwindet aus dem Feed; die neue Periode beruehrt bzw. ueberlappt A.
    Stille Revision -- keine Meldung, A wird im Gedaechtnis durch die neue
    Periode ersetzt (mit dem ``reported_at`` von A)."""
    t = _jetzt_minute()
    (a_vf, a_vt), (b_vf, b_vt) = _perioden(t)
    a = _warnung(a_vf, a_vt)
    neu = _warnung(b_vf, b_vt) if art == "beruehrt" else _warnung(t + timedelta(hours=1), b_vt)
    quelle = _FeedQuelle(f"quelle-3470-ac3-{art}", LAT, LON)
    with _nur_quellen(quelle):
        nutzer = _TripNutzer(f"ac3-{art}")
        reported_a = _trip_erstmeldung(nutzer, quelle, a)
        quelle.alerts = [neu]
        folge = _melde_folge(nutzer, 3)

    assert [len(r) for r in folge] == [0, 0, 0], f"Neuausgabe ({art}) muss still bleiben: {folge!r}"
    eintraege = nutzer.eintraege()
    assert set(eintraege) == {official_alert_state_key(neu)}, (
        f"Alte Periode muss durch die neue ersetzt sein: {sorted(eintraege)}"
    )
    assert eintraege[official_alert_state_key(neu)]["reported_at"] == reported_a


# ===========================================================================
# AC-4 -- echte Vorverlegung meldet genau einmal, auch wenn die alte noch im Feed steht
# ===========================================================================


@pytest.mark.parametrize("order", REIHENFOLGEN)
def test_ac4_echte_vorverlegung_meldet_genau_einmal(order):
    """AC-4 (RED ueber die Folgelaeufe): die neue Periode beginnt 3 h frueher
    und ueberlappt die gemeldete im Inneren (keine Randberuehrung, kein
    Umschliessen); die alte steht weiter im Feed. Erwartet: genau EINE
    Meldung (die Vorverlegung) ueber alle Laeufe. Lauf 1 meldet heute schon
    richtig; danach verdraengen sich alte und neue Periode im Gedaechtnis
    wie bei AC-1 und die Vorverlegung wird erneut gemeldet."""
    t = _jetzt_minute()
    alt = _warnung(t + timedelta(hours=1), t + timedelta(hours=9))
    vorverlegt = _warnung(t - timedelta(hours=2), t + timedelta(hours=5))
    quelle = _FeedQuelle("quelle-3470-ac4", LAT, LON)
    with _nur_quellen(quelle):
        nutzer = _TripNutzer(f"ac4-{order}")
        _trip_erstmeldung(nutzer, quelle, alt)
        quelle.alerts = _feed(order, alt, vorverlegt)
        folge = _melde_folge(nutzer)

    anzahl = [len(r) for r in folge]
    assert anzahl[0] == 1 and official_alert_state_key(folge[0][0]) == official_alert_state_key(vorverlegt), (
        f"Lauf 1 muss die Vorverlegung melden: {folge[0]!r}"
    )
    assert anzahl == [1] + [0] * (LAEUFE - 1), (
        f"Feed {order}: erwartet genau eine Meldung (Lauf 1), gemeldet je Lauf: {anzahl}"
    )


# ===========================================================================
# AC-5 -- Eskalation der Nachbarperiode meldet (einmal)
# ===========================================================================


@pytest.mark.parametrize("order", REIHENFOLGEN)
def test_ac5_eskalation_der_nachbarperiode_meldet_genau_einmal(order):
    """AC-5: A (Stufe 2) gemeldet, Feed liefert A (2) und B (3). Lauf 1 meldet
    genau die Eskalation B mit Stufe 3 -- Regressionsschutz, heute gruen.
    Die Folgelaeufe duerfen nichts mehr melden (RED heute: A wird danach gegen
    das gemeldete B als Vorverlegung neu gemeldet -- derselbe Ping-Pong)."""
    t = _jetzt_minute()
    (a_vf, a_vt), (b_vf, b_vt) = _perioden(t)
    a2, b3 = _warnung(a_vf, a_vt, 2), _warnung(b_vf, b_vt, 3)
    quelle = _FeedQuelle("quelle-3470-ac5", LAT, LON)
    with _nur_quellen(quelle):
        nutzer = _TripNutzer(f"ac5-{order}")
        _trip_erstmeldung(nutzer, quelle, a2)
        quelle.alerts = _feed(order, a2, b3)
        folge = _melde_folge(nutzer)

    assert len(folge[0]) == 1 and folge[0][0].level == 3, (
        f"Lauf 1 muss genau die Eskalation (Stufe 3) melden: {folge[0]!r}"
    )
    anzahl = [len(r) for r in folge]
    assert anzahl == [1] + [0] * (LAEUFE - 1), (
        f"Feed {order}: nach der Eskalation keine weitere Meldung erwartet, gemeldet je Lauf: {anzahl}"
    )


# ===========================================================================
# AC-6 -- exakter Schluesseltreffer: Eintrag unveraendert, nur Eskalation meldet
# ===========================================================================


@pytest.mark.parametrize("order", REIHENFOLGEN)
def test_ac6_exakter_treffer_laesst_eintrag_byte_gleich_trotz_nachbarperiode(order):
    """AC-6 (Kernfall, RED): A steht exakt im Gedaechtnis, der Feed liefert A
    (gleiche Stufe) und die Nachbarperiode B. Keine Meldung, und der Eintrag
    von A bleibt byte-gleich (gleicher JSON-Text). Heute verbraucht B den
    Eintrag A (``del state[stale_key]``)."""
    t = _jetzt_minute()
    (a_vf, a_vt), (b_vf, b_vt) = _perioden(t)
    a, b = _warnung(a_vf, a_vt), _warnung(b_vf, b_vt)
    key_a = official_alert_state_key(a)
    quelle = _FeedQuelle("quelle-3470-ac6", LAT, LON)
    with _nur_quellen(quelle):
        nutzer = _TripNutzer(f"ac6-{order}")
        _trip_erstmeldung(nutzer, quelle, a)
        vorher = json.dumps(json.loads(nutzer.rohtext())[key_a])

        quelle.alerts = _feed(order, a, b)
        gemeldet = nutzer.svc.check_official_alert_triggers(nutzer.trip)  # ohne Zustellung

    nachher_state = json.loads(nutzer.rohtext())
    assert gemeldet == [], f"Feed {order}: gleiche Stufe darf nicht melden: {gemeldet!r}"
    assert key_a in nachher_state, (
        f"Feed {order}: Eintrag von A wurde entfernt, Gedaechtnis: {sorted(nachher_state)}"
    )
    assert json.dumps(nachher_state[key_a]) == vorher, (
        f"Feed {order}: Eintrag von A veraendert:\n vorher {vorher}\n nachher {json.dumps(nachher_state[key_a])}"
    )


@pytest.mark.parametrize("mit_nachbar", [False, True], ids=["allein", "mit-nachbar"])
def test_ac6_exakter_treffer_mit_hoeherer_stufe_meldet(mit_nachbar):
    """AC-6 Eskalationszweig (Regressionsschutz, heute gruen): A (2) gemeldet,
    Feed liefert A mit Stufe 3 (gleicher Schluessel) -- genau eine Meldung."""
    t = _jetzt_minute()
    (a_vf, a_vt), (b_vf, b_vt) = _perioden(t)
    a2, a3, b2 = _warnung(a_vf, a_vt, 2), _warnung(a_vf, a_vt, 3), _warnung(b_vf, b_vt, 2)
    quelle = _FeedQuelle(f"quelle-3470-ac6b-{mit_nachbar}", LAT, LON)
    with _nur_quellen(quelle):
        nutzer = _TripNutzer(f"ac6b-{int(mit_nachbar)}")
        _trip_erstmeldung(nutzer, quelle, a2)
        quelle.alerts = [a3, b2] if mit_nachbar else [a3]
        gemeldet, _ = nutzer.lauf()

    assert [(official_alert_state_key(x), x.level) for x in gemeldet] == [(official_alert_state_key(a3), 3)], (
        f"Eskalation auf exaktem Schluessel muss genau einmal melden: {gemeldet!r}"
    )


# ===========================================================================
# AC-7 -- Ortsvergleich verhaelt sich wie der Trip; Ort X schuetzt Ort Y nicht
# ===========================================================================


@pytest.mark.parametrize("order", REIHENFOLGEN)
def test_ac7_ortsvergleich_kein_pingpong_und_orte_getrennt(monkeypatch, order):
    """AC-7 (Kernfall, RED): Ortsvergleich mit zwei Orten. Beide haben A
    gemeldet. Danach fuehrt nur Ort X die Nachbarperioden A und B im Feed;
    an Ort Y ist A verschwunden und B ist da (echte Neuausgabe).
    Erwartet: keine Meldung in vier Laeufen (Trip-Verhalten, AC-1);
    Gedaechtnis X = {A, B}; Gedaechtnis Y = {B} -- das A im Feed von X darf
    den Eintrag A von Y NICHT schuetzen. Heute: Ping-Pong an Ort X."""
    uhr = _VergleichsUhr(monkeypatch, COMPARE_FROZEN)
    (a_vf, a_vt), (b_vf, b_vt) = _perioden(COMPARE_FROZEN)
    a, b = _warnung(a_vf, a_vt), _warnung(b_vf, b_vt)
    loc_x = SavedLocation(id="loc-x-3470", name="Ort X", lat=LAT, lon=LON, elevation_m=60)
    loc_y = SavedLocation(id="loc-y-3470", name="Ort Y", lat=LAT_Y, lon=LON_Y, elevation_m=60)
    quelle_x = _FeedQuelle("quelle-3470-x", LAT, LON, [a])
    quelle_y = _FeedQuelle("quelle-3470-y", LAT_Y, LON_Y, [a])
    user_id = _fresh_user(f"ac7-{order}")
    preset_id = f"preset-3470-{order}"
    with _nur_quellen(quelle_x, quelle_y):
        svc = _compare_service(user_id)
        erst, _ = _vergleich_lauf(svc, preset_id, [loc_x, loc_y], uhr)
        assert len(erst) == 1, f"Vorbedingung: A an beiden Orten neu (eine gebuendelte Meldung): {erst!r}"
        for loc in (loc_x, loc_y):
            assert set(_eintraege(user_id, f"{preset_id}:{loc.id}")) == {official_alert_state_key(a)}

        quelle_x.alerts = _feed(order, a, b)
        quelle_y.alerts = [b]
        folge = [_vergleich_lauf(svc, preset_id, [loc_x, loc_y], uhr)[0] for _ in range(LAEUFE)]

    anzahl = [len(r) for r in folge]
    gedaechtnis_x = set(_eintraege(user_id, f"{preset_id}:{loc_x.id}"))
    gedaechtnis_y = set(_eintraege(user_id, f"{preset_id}:{loc_y.id}"))
    assert anzahl == [0] * LAEUFE, (
        f"Ortsvergleich Feed X {order}: erwartet 0 Meldungen in Lauf 1-{LAEUFE}, gemeldet je Lauf: {anzahl}"
    )
    assert gedaechtnis_x == {official_alert_state_key(a), official_alert_state_key(b)}, (
        f"Ort X muss beide Perioden behalten: {sorted(gedaechtnis_x)}"
    )
    assert gedaechtnis_y == {official_alert_state_key(b)}, (
        f"Ort Y: A ist dort verschwunden -> stille Revision, A darf nicht durch den Feed von X "
        f"geschuetzt werden: {sorted(gedaechtnis_y)}"
    )


# ===========================================================================
# AC-8 -- genau eine Entwarnung je Warnung, nicht eine je Periode
# ===========================================================================


def test_ac8_beide_perioden_verschwinden_genau_eine_entwarnung_trip():
    """AC-8 (Kernfall, RED): A und B wurden gemeldet und stehen beide im
    Gedaechtnis; dann verschwinden beide aus dem Feed (Quelle gesund, liefert
    leer). Ueber alle Laeufe (Zwei-Lauf-Bestaetigung + Zustellung) entsteht
    genau EINE Entwarnungs-Notice. Heute: zwei (eine je Periode)."""
    t = _jetzt_minute()
    (a_vf, a_vt), (b_vf, b_vt) = _perioden(t)
    a, b = _warnung(a_vf, a_vt), _warnung(b_vf, b_vt)
    quelle = _FeedQuelle("quelle-3470-ac8", LAT, LON, [a, b])
    with _nur_quellen(quelle):
        nutzer = _TripNutzer("ac8-ende")
        erst, _ = nutzer.lauf()
        assert len(erst) == 2, f"Vorbedingung: Erstauftritt meldet beide Perioden: {erst!r}"
        assert set(nutzer.eintraege()) == {official_alert_state_key(a), official_alert_state_key(b)}

        quelle.alerts = []
        notices = [n for _ in range(LAEUFE) for n in nutzer.lauf()[1]]

    assert len(notices) == 1, (
        f"Erwartet genau eine Entwarnung, erzeugt {len(notices)}: "
        f"{[(n.kind, n.region, n.old_rank, n.new_rank) for n in notices]}"
    )
    assert notices[0].kind == "ended" and notices[0].hazard == GEFAHR


@pytest.mark.parametrize("order", REIHENFOLGEN)
def test_ac8_herabstufung_beider_perioden_genau_eine_entwarnung_trip(order):
    """AC-8 Herabstufung: A und B (Stufe 3) gemeldet, dann liefert der Feed
    beide mit Stufe 2. Genau eine Entwarnung "3 -> 2". Heute ggf. zufaellig
    gruen, weil der Ping-Pong eine der beiden Perioden aus dem Gedaechtnis
    loescht -- nach dem Fix (beide bleiben stehen) bewacht der Test die
    Entdopplung im Notice-Builder."""
    t = _jetzt_minute()
    (a_vf, a_vt), (b_vf, b_vt) = _perioden(t)
    quelle = _FeedQuelle(f"quelle-3470-ac8b-{order}", LAT, LON,
                         [_warnung(a_vf, a_vt, 3), _warnung(b_vf, b_vt, 3)])
    with _nur_quellen(quelle):
        nutzer = _TripNutzer(f"ac8b-{order}")
        erst, _ = nutzer.lauf()
        assert len(erst) == 2, f"Vorbedingung: Erstauftritt meldet beide Perioden: {erst!r}"

        quelle.alerts = _feed(order, _warnung(a_vf, a_vt, 2), _warnung(b_vf, b_vt, 2))
        notices = [n for _ in range(LAEUFE) for n in nutzer.lauf()[1]]

    assert [(n.kind, n.old_rank, n.new_rank) for n in notices] == [("lowered", 3, 2)], (
        f"Feed {order}: erwartet genau eine Entwarnung 3->2, erzeugt: "
        f"{[(n.kind, n.old_rank, n.new_rank) for n in notices]}"
    )


def test_ac8_beide_perioden_verschwinden_genau_eine_entwarnung_vergleich(monkeypatch):
    """AC-8 Ortsvergleich (Kernfall, RED): derselbe Fall ueber ``_detect`` --
    genau eine Entwarnungs-Notice fuer Ort X."""
    uhr = _VergleichsUhr(monkeypatch, COMPARE_FROZEN)
    (a_vf, a_vt), (b_vf, b_vt) = _perioden(COMPARE_FROZEN)
    a, b = _warnung(a_vf, a_vt), _warnung(b_vf, b_vt)
    loc_x = SavedLocation(id="loc-x-3470", name="Ort X", lat=LAT, lon=LON, elevation_m=60)
    quelle = _FeedQuelle("quelle-3470-ac8c", LAT, LON, [a, b])
    user_id = _fresh_user("ac8c")
    preset_id = "preset-3470-ac8"
    with _nur_quellen(quelle):
        svc = _compare_service(user_id)
        erst, _ = _vergleich_lauf(svc, preset_id, [loc_x], uhr)
        assert len(erst) == 2, f"Vorbedingung: Erstauftritt meldet beide Perioden: {erst!r}"
        quelle.alerts = []
        notices = [n for _ in range(LAEUFE) for n in _vergleich_lauf(svc, preset_id, [loc_x], uhr)[1]]

    assert len(notices) == 1, (
        f"Erwartet genau eine Entwarnung, erzeugt {len(notices)}: "
        f"{[(n.kind, n.scope_label, n.old_rank, n.new_rank) for n in notices]}"
    )


@pytest.mark.parametrize("order", REIHENFOLGEN)
def test_ac8_herabstufung_beider_perioden_genau_eine_entwarnung_vergleich(monkeypatch, order):
    """AC-8 Herabstufung im Ortsvergleich: A und B (Stufe 3) gemeldet, dann
    liefert der Feed beide mit Stufe 2. Ueber ``_detect`` mit echtem
    Dateigedaechtnis: genau eine Entwarnung 3 -> 2 fuer Ort X."""
    uhr = _VergleichsUhr(monkeypatch, COMPARE_FROZEN)
    (a_vf, a_vt), (b_vf, b_vt) = _perioden(COMPARE_FROZEN)
    loc_x = SavedLocation(id="loc-x-3470", name="Ort X", lat=LAT, lon=LON, elevation_m=60)
    quelle = _FeedQuelle(f"quelle-3470-ac8d-{order}", LAT, LON,
                         [_warnung(a_vf, a_vt, 3), _warnung(b_vf, b_vt, 3)])
    user_id = _fresh_user(f"ac8d-{order}")
    preset_id = "preset-3470-ac8d"
    with _nur_quellen(quelle):
        svc = _compare_service(user_id)
        erst, _ = _vergleich_lauf(svc, preset_id, [loc_x], uhr)
        assert len(erst) == 2, f"Vorbedingung: Erstauftritt meldet beide Perioden: {erst!r}"

        quelle.alerts = _feed(order, _warnung(a_vf, a_vt, 2), _warnung(b_vf, b_vt, 2))
        notices = [n for _ in range(LAEUFE) for n in _vergleich_lauf(svc, preset_id, [loc_x], uhr)[1]]

    assert [(n.kind, n.old_rank, n.new_rank) for n in notices] == [("lowered", 3, 2)], (
        f"Feed {order}: erwartet genau eine Entwarnung 3->2, erzeugt: "
        f"{[(n.kind, n.scope_label, n.old_rank, n.new_rank) for n in notices]}"
    )


# ===========================================================================
# AC-9 -- zwei Nutzer: Gedaechtnis und Meldungen getrennt (Regressionsschutz)
# ===========================================================================


def test_ac9_zwei_nutzer_beeinflussen_sich_nicht():
    """AC-9 (Regressionsschutz, heute gruen): Nutzer 1 hat A gemeldet, Nutzer
    2 (gleiche Trip-Kennung) noch nichts. Der Lauf von Nutzer 2 meldet ihm
    A und B neu und laesst das Gedaechtnis von Nutzer 1 byte-gleich; der Lauf
    von Nutzer 1 laesst das Gedaechtnis von Nutzer 2 byte-gleich."""
    t = _jetzt_minute()
    (a_vf, a_vt), (b_vf, b_vt) = _perioden(t)
    a, b = _warnung(a_vf, a_vt), _warnung(b_vf, b_vt)
    quelle = _FeedQuelle("quelle-3470-ac9", LAT, LON)
    with _nur_quellen(quelle):
        eins = _TripNutzer("ac9-eins", trip_id="trip-3470-geteilt")
        zwei = _TripNutzer("ac9-zwei", trip_id="trip-3470-geteilt")
        assert eins.user_id != zwei.user_id
        _trip_erstmeldung(eins, quelle, a)

        quelle.alerts = [a, b]
        roh_eins = eins.rohtext()
        gemeldet_zwei, _ = zwei.lauf()
        assert eins.rohtext() == roh_eins, "Lauf von Nutzer 2 hat das Gedaechtnis von Nutzer 1 veraendert"
        roh_zwei = zwei.rohtext()
        eins.lauf()
        assert zwei.rohtext() == roh_zwei, "Lauf von Nutzer 1 hat das Gedaechtnis von Nutzer 2 veraendert"

    assert {official_alert_state_key(x) for x in gemeldet_zwei} == {
        official_alert_state_key(a), official_alert_state_key(b)}, (
        f"Nutzer 2 muss die Warnung trotz Gedaechtnis von Nutzer 1 gemeldet bekommen: {gemeldet_zwei!r}"
    )
    assert set(zwei.eintraege()) == {official_alert_state_key(a), official_alert_state_key(b)}


# ===========================================================================
# AC-10 -- Fail-soft: fehlende Fenster, naive Zeitstempel
# ===========================================================================


def test_ac10_warnung_ohne_fenster_meldet_einmal_und_stuerzt_nicht():
    """AC-10 (Regressionsschutz, heute gruen): eine Warnung ohne
    ``valid_from``/``valid_to`` entscheidet nur ueber den exakten Schluessel --
    erste Meldung, danach still, kein Absturz."""
    quelle = _FeedQuelle("quelle-3470-ac10a", LAT, LON, [_warnung(None, None)])
    with _nur_quellen(quelle):
        nutzer = _TripNutzer("ac10a")
        folge = _melde_folge(nutzer)

    assert [len(r) for r in folge] == [1] + [0] * (LAEUFE - 1), (
        f"Zeitlose Warnung: genau eine Meldung erwartet, gemeldet je Lauf: {[len(r) for r in folge]}"
    )


@pytest.mark.parametrize("order", REIHENFOLGEN)
def test_ac10_naive_zeitstempel_nachbarperioden_ohne_absturz_und_ohne_pingpong(order):
    """AC-10 naive Zeitstempel (Meteoalarm liefert sie real, F001 #1685): A
    und B ohne Zeitzone. Kein Absturz in keinem Lauf. RED heute nur wegen des
    Kernfehlers (Ping-Pong wie AC-1) -- die Zusicherung bewacht, dass der Fix
    die Randberuehrung auch mit naiven Zeitstempeln (normalisiert,
    geschuetzter Block) erkennt."""
    t = _jetzt_minute().replace(tzinfo=None)
    (a_vf, a_vt), (b_vf, b_vt) = _perioden(t)
    a, b = _warnung(a_vf, a_vt), _warnung(b_vf, b_vt)
    quelle = _FeedQuelle("quelle-3470-ac10b", LAT, LON)
    with _nur_quellen(quelle):
        nutzer = _TripNutzer(f"ac10b-{order}")
        _trip_erstmeldung(nutzer, quelle, a)
        quelle.alerts = _feed(order, a, b)
        folge = _melde_folge(nutzer)  # darf nicht werfen

    anzahl = [len(r) for r in folge]
    assert anzahl == [0] * LAEUFE, (
        f"Naive Zeitstempel, Feed {order}: erwartet 0 Meldungen in Lauf 1-{LAEUFE}, gemeldet je Lauf: {anzahl}"
    )


# ===========================================================================
# AC-8 Fix-Loop 1 (Adversary F001/F002) -- Entdopplung der Entwarnungen
# ===========================================================================


def _save_segmente(user_id: str, trip_id: str, segmente: list) -> None:
    """Routen-Geometrie mit mehreren Segmenten: je Eintrag ``(id, lat, lon,
    start, ende)`` -- jedes Segment bekommt sein eigenes Warnfenster."""
    from services.weather_snapshot import WeatherSnapshotService

    now = datetime.now(timezone.utc)
    daten = []
    for seg_id, lat, lon, start, ende in segmente:
        segment = TripSegment(
            segment_id=seg_id,
            start_point=GPXPoint(lat=lat, lon=lon, elevation_m=1000, distance_from_start_km=0.0),
            end_point=GPXPoint(lat=lat + 0.01, lon=lon + 0.01, elevation_m=1100, distance_from_start_km=4.0),
            start_time=start, end_time=ende, duration_hours=2.0, distance_km=4.0,
            ascent_m=100, descent_m=0,
        )
        daten.append(SegmentWeatherData(
            segment=segment,
            timeseries=NormalizedTimeseries(
                meta=ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=1.0), data=[],
            ),
            aggregated=SegmentWeatherSummary(precip_sum_mm=2.0),
            fetched_at=now, provider="openmeteo",
        ))
    WeatherSnapshotService(user_id=user_id).save_dated(trip_id, ortstag(LAT, LON), daten)


def _warnung_von(quelle: str, vf: datetime, vt: datetime, level: int) -> OfficialAlert:
    return OfficialAlert(source=quelle, hazard=GEFAHR, level=level,
                         label="Kaeltewarnung (#3470)", region_label=REGION,
                         valid_from=vf, valid_to=vt)


def _getrennte_perioden(t: datetime) -> tuple[tuple[datetime, datetime], tuple[datetime, datetime]]:
    """A und B derselben Warnung mit einer Luecke dazwischen -- jede Periode
    sieht beim Herabstufen nur ihre eigene neue Stufe."""
    return (t - timedelta(hours=1), t + timedelta(hours=3)), (t + timedelta(hours=5), t + timedelta(hours=23))


def _notice_bild(notices: list) -> list:
    return [(n.kind, n.source, n.scope_label, n.old_rank, n.new_rank, n.old_level, n.new_level)
            for n in notices]


def test_ac8_perioden_auf_verschiedenen_segmenten_genau_eine_entwarnung_fuer_beide():
    """AC-8 (Adversary F001): A beruehrt nur Segment 1, B nur Segment 2; beide
    enden. Genau EINE Entwarnung, die beide Segmente nennt -- die Segmente
    sind nur die Fundstellen derselben Warnung auf der Route."""
    from output.renderers.alert.segments import format_segment_reference

    t = _jetzt_minute()
    (a_vf, a_vt), (b_vf, b_vt) = _perioden(t)
    a, b = _warnung(a_vf, a_vt), _warnung(b_vf, b_vt)
    quelle = _FeedQuelle("quelle-3470-ac8seg", LAT, LON, [a, b])
    with _nur_quellen(quelle):
        nutzer = _TripNutzer("ac8seg")
        _save_segmente(nutzer.user_id, nutzer.trip.id, [
            (1, LAT, LON, t - timedelta(hours=2), t + timedelta(hours=2)),
            (2, LAT + 0.1, LON + 0.1, t + timedelta(hours=4), t + timedelta(hours=48)),
        ])
        erst, _ = nutzer.lauf()
        assert len(erst) == 2, f"Vorbedingung: Erstauftritt meldet beide Perioden: {erst!r}"
        scopes = {k: tuple(v.get("scope") or ()) for k, v in nutzer.eintraege().items()}
        assert len(scopes) == 2, f"Vorbedingung: beide Perioden im Gedaechtnis: {scopes!r}"

        quelle.alerts = []
        notices = [n for _ in range(LAEUFE) for n in nutzer.lauf()[1]]

    assert len(notices) == 1, f"Erwartet genau eine Entwarnung, erzeugt: {_notice_bild(notices)}"
    assert notices[0].kind == "ended"
    assert notices[0].scope_label == format_segment_reference(["1", "2"]), (
        f"Entwarnung muss beide Segmente nennen: {notices[0].scope_label!r}"
    )


def test_ac8_herabstufung_mit_verschiedenen_alten_stufen_hoechste_alte_niedrigste_neue():
    """AC-8 (Adversary F002): A war Stufe 3, B Stufe 4; der Feed senkt A auf 2
    und B auf 3. Genau eine Entwarnung "4 -> 2" -- hoechste alte und
    niedrigste neue Stufe, fuer Rang UND Stufe."""
    t = _jetzt_minute()
    (a_vf, a_vt), (b_vf, b_vt) = _getrennte_perioden(t)
    quelle = _FeedQuelle("quelle-3470-ac8lv", LAT, LON,
                         [_warnung(a_vf, a_vt, 3), _warnung(b_vf, b_vt, 4)])
    with _nur_quellen(quelle):
        nutzer = _TripNutzer("ac8lv")
        erst, _ = nutzer.lauf()
        assert len(erst) == 2, f"Vorbedingung: Erstauftritt meldet beide Perioden: {erst!r}"

        quelle.alerts = [_warnung(a_vf, a_vt, 2), _warnung(b_vf, b_vt, 3)]
        notices = [n for _ in range(LAEUFE) for n in nutzer.lauf()[1]]

    assert [(n.kind, n.old_rank, n.new_rank, n.old_level, n.new_level) for n in notices] == [
        ("lowered", 4, 2, 4, 2)
    ], f"Erwartet genau eine Entwarnung 4->2, erzeugt: {_notice_bild(notices)}"


def test_ac8_verschiedene_quellen_bleiben_getrennte_entwarnungen():
    """AC-8 Gegenprobe: dieselbe Gefahr mit derselben Regionsbezeichnung,
    aber von zwei verschiedenen Quellen (je eine zustaendig fuer ein Segment
    der Route) gemeldet -- beide enden. Zwei Entwarnungen, je Quelle eine
    (verschiedene Warnungen, nicht zwei Perioden einer)."""
    t = _jetzt_minute()
    (a_vf, a_vt), (b_vf, b_vt) = _getrennte_perioden(t)
    q1 = _FeedQuelle("quelle-3470-ac8q1", LAT, LON, [_warnung_von("quelle-3470-ac8q1", a_vf, a_vt, 3)])
    q2 = _FeedQuelle("quelle-3470-ac8q2", LAT_Y, LON_Y, [_warnung_von("quelle-3470-ac8q2", b_vf, b_vt, 3)])
    with _nur_quellen(q1, q2):
        nutzer = _TripNutzer("ac8q")
        _save_segmente(nutzer.user_id, nutzer.trip.id, [
            (1, LAT, LON, t - timedelta(hours=2), t + timedelta(hours=48)),
            (2, LAT_Y, LON_Y, t - timedelta(hours=2), t + timedelta(hours=48)),
        ])
        erst, _ = nutzer.lauf()
        assert len(erst) == 2, f"Vorbedingung: Erstauftritt meldet beide Warnungen: {erst!r}"
        q1.alerts, q2.alerts = [], []
        notices = [n for _ in range(LAEUFE) for n in nutzer.lauf()[1]]

    assert sorted((n.kind, n.source) for n in notices) == [
        ("ended", "quelle-3470-ac8q1"), ("ended", "quelle-3470-ac8q2"),
    ], f"Je Quelle eine Entwarnung erwartet, erzeugt: {_notice_bild(notices)}"


def test_ac8_beendet_und_gesenkt_im_selben_lauf_bleiben_getrennt():
    """AC-8 Gegenprobe: A wird gesenkt, B ist beendet -- im selben Lauf. Zwei
    Entwarnungen verschiedener Art, keine verschmilzt zur anderen."""
    t = _jetzt_minute()
    (a_vf, a_vt), (b_vf, b_vt) = _getrennte_perioden(t)
    quelle = _FeedQuelle("quelle-3470-ac8art", LAT, LON,
                         [_warnung(a_vf, a_vt, 3), _warnung(b_vf, b_vt, 3)])
    with _nur_quellen(quelle):
        nutzer = _TripNutzer("ac8art")
        erst, _ = nutzer.lauf()
        assert len(erst) == 2, f"Vorbedingung: Erstauftritt meldet beide Perioden: {erst!r}"
        quelle.alerts = [_warnung(a_vf, a_vt, 3)]
        _, vorlauf = nutzer.lauf()  # B fehlt zum ersten Mal: erst vermerkt
        assert vorlauf == [], f"Vorbedingung: Zwei-Lauf-Bestaetigung: {_notice_bild(vorlauf)}"
        quelle.alerts = [_warnung(a_vf, a_vt, 2)]
        _, notices = nutzer.lauf()

    assert sorted(n.kind for n in notices) == ["ended", "lowered"], (
        f"Gesenkt und beendet im selben Lauf getrennt erwartet: {_notice_bild(notices)}"
    )


def test_ac8_vergleich_verschiedene_orte_bleiben_getrennte_entwarnungen(monkeypatch):
    """AC-8 Gegenprobe Ortsvergleich: dieselbe Warnung an Ort X und Ort Y
    endet. Jeder Ort hat ein eigenes Melde-Gedaechtnis (eigene alte Stufe) --
    die Entdopplung fasst nur Perioden EINES Ortes zusammen, je Ort bleibt
    eine eigene, benannte Entwarnung (Verhalten vor #3470)."""
    uhr = _VergleichsUhr(monkeypatch, COMPARE_FROZEN)
    (a_vf, a_vt), _b = _perioden(COMPARE_FROZEN)
    loc_x = SavedLocation(id="loc-x-3470o", name="Ort X", lat=LAT, lon=LON, elevation_m=60)
    loc_y = SavedLocation(id="loc-y-3470o", name="Ort Y", lat=LAT + 0.1, lon=LON + 0.1, elevation_m=60)
    quelle = _FeedQuelle("quelle-3470-ac8orte", LAT, LON, [_warnung(a_vf, a_vt)])
    with _nur_quellen(quelle):
        svc = _compare_service(_fresh_user("ac8orte"))
        erst, _ = _vergleich_lauf(svc, "preset-3470-ac8orte", [loc_x, loc_y], uhr)
        assert len(erst) == 1, f"Vorbedingung: Erstauftritt meldet die Warnung: {erst!r}"
        quelle.alerts = []
        notices = [n for _ in range(LAEUFE)
                   for n in _vergleich_lauf(svc, "preset-3470-ac8orte", [loc_x, loc_y], uhr)[1]]

    assert sorted((n.kind, n.scope_label) for n in notices) == [("ended", "Ort X"), ("ended", "Ort Y")], (
        f"Je Ort eine Entwarnung erwartet, erzeugt: {_notice_bild(notices)}"
    )


# ===========================================================================
# AC-8 Fix-Loop 2 (Adversary F004) -- verschiedene Gefahren derselben Quelle
# ===========================================================================


def _warnung_gefahr(gefahr: str, vf: datetime, vt: datetime, level: int = 2) -> OfficialAlert:
    return OfficialAlert(source="test-3470", hazard=gefahr, level=level,
                         label=f"{gefahr}-Warnung (#3470)", region_label=REGION,
                         valid_from=vf, valid_to=vt)


def test_ac8_verschiedene_gefahren_derselben_quelle_bleiben_getrennte_entwarnungen_trip():
    """AC-8 Gegenprobe (Adversary F004): Wind und Kaelte derselben Quelle und
    Region wurden gemeldet und enden im selben Lauf. Zwei Entwarnungen, je
    Gefahr eine -- verschiedene Warnungen verschmelzen nicht."""
    t = _jetzt_minute()
    (a_vf, a_vt), _b = _perioden(t)
    quelle = _FeedQuelle("quelle-3470-ac8gef", LAT, LON,
                         [_warnung_gefahr("wind", a_vf, a_vt), _warnung_gefahr(GEFAHR, a_vf, a_vt)])
    with _nur_quellen(quelle):
        nutzer = _TripNutzer("ac8gef")
        erst, _ = nutzer.lauf()
        assert sorted(a.hazard for a in erst) == sorted(["wind", GEFAHR]), (
            f"Vorbedingung: Erstauftritt meldet beide Gefahren: {erst!r}"
        )
        quelle.alerts = []
        notices = [n for _ in range(LAEUFE) for n in nutzer.lauf()[1]]

    assert sorted((n.kind, n.hazard) for n in notices) == sorted([("ended", "wind"), ("ended", GEFAHR)]), (
        f"Je Gefahr eine Entwarnung erwartet, erzeugt: "
        f"{[(n.kind, n.hazard, n.source, n.scope_label) for n in notices]}"
    )


def test_ac8_vergleich_verschiedene_gefahren_an_einem_ort_bleiben_getrennte_entwarnungen(monkeypatch):
    """AC-8 Gegenprobe Ortsvergleich (Adversary F004): Wind und Kaelte
    derselben Quelle an Ort X enden im selben Lauf -- zwei Entwarnungen, je
    Gefahr eine."""
    uhr = _VergleichsUhr(monkeypatch, COMPARE_FROZEN)
    (a_vf, a_vt), _b = _perioden(COMPARE_FROZEN)
    loc_x = SavedLocation(id="loc-x-3470g", name="Ort X", lat=LAT, lon=LON, elevation_m=60)
    quelle = _FeedQuelle("quelle-3470-ac8vgef", LAT, LON,
                         [_warnung_gefahr("wind", a_vf, a_vt), _warnung_gefahr(GEFAHR, a_vf, a_vt)])
    with _nur_quellen(quelle):
        svc = _compare_service(_fresh_user("ac8vgef"))
        erst, _ = _vergleich_lauf(svc, "preset-3470-ac8vgef", [loc_x], uhr)
        assert sorted(a.hazard for a in erst) == sorted(["wind", GEFAHR]), (
            f"Vorbedingung: Erstauftritt meldet beide Gefahren: {erst!r}"
        )
        quelle.alerts = []
        notices = [n for _ in range(LAEUFE)
                   for n in _vergleich_lauf(svc, "preset-3470-ac8vgef", [loc_x], uhr)[1]]

    assert sorted((n.kind, n.hazard, n.scope_label) for n in notices) == sorted(
        [("ended", "wind", "Ort X"), ("ended", GEFAHR, "Ort X")]
    ), f"Je Gefahr eine Entwarnung erwartet, erzeugt: {[(n.kind, n.hazard, n.scope_label) for n in notices]}"
