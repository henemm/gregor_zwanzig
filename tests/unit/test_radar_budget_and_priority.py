"""Issue #1329, Scheibe C2: Budget-Anbindung + Prioritaet im Radar-Pfad
(AC-5..AC-8, Root-Cause-3-Doppelverbrauch-Fix).

SPEC: docs/specs/modules/fix_1329_c2_radar_nowcast_cache.md
Ausfuehrung:
    uv run pytest tests/unit/test_radar_budget_and_priority.py -v

Kern-Schicht, netzfrei -- Test-Politik CLAUDE.md. Ein autouse-Fixture
ersetzt `httpx.Client` fuer die gesamte Datei durch eine Tripwire (kein
Mock/patch von Rueckgabewerten, sondern eine Abwesenheits-Beweisfuehrung):
`radar_service._fetch_openmeteo_15` faengt JEDE Exception breit ab
(Fail-soft-Fetch) -- ein `raise` in `httpx.Client()` selbst wuerde dort
lautlos geschluckt. Die Tripwire zeichnet deshalb jeden `.get()`-Versuch in
einer modulweiten Liste auf, BEVOR sie einen (im try/except der
Produktion abgefangenen) Fehler wirft -- so bleibt die Abwesenheit eines
echten Netzzugriffs *und* die Anwesenheit eines Versuchs pruefbar, ohne dass
je ein echtes Socket geoeffnet wird.

Aufrufer-Prioritaet (Scheduler = "polling", `/jetzt` = "user_briefing")
wird ueber echte, duck-typed Fake-Services (kein Mock/patch) bzw. echten
Klassenaustausch per `monkeypatch` (ersetzt NUR, welche Klasse referenziert
wird -- Vererbung, kein Verhalten vorgetaeuscht) bewiesen.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

import httpx
import pytest

from app.loader import get_data_root
from providers.brightsky import RadarFrame
from services.forecast_budget import ForecastBudgetGate
from services.radar_service import NowcastResult, RadarNowcastService

# Reale Koordinate ausserhalb aller RADOLAN/INCA/DPC/AROME/ICON-D2-Boxen
# (identisch zu test_feature_734_arome_france_nowcast.py) -> reiner
# open-meteo-minutely_15-Fallback.
_ATLANTIC_LAT, _ATLANTIC_LON = 35.0, -40.0

# Koordinate innerhalb AROME-FR UND ICON-D2, ausserhalb RADOLAN/INCA/DPC
# (Doppelverbrauch-Szenario Root Cause 3).
_DOUBLE_BRANCH_LAT, _DOUBLE_BRANCH_LON = 45.0, 4.0


# ---------------------------------------------------------------------------
# Netz-Tripwire (kein Mock-Theater -- beweist Abwesenheit eines Netzzugriffs)
# ---------------------------------------------------------------------------

_NETWORK_ATTEMPTS: list = []


class _TripwireClient:
    """Ersetzt `httpx.Client` fuer die Testdauer. `__init__`/`__enter__`
    loesen bewusst NICHTS aus (ein Konstruktor-Aufruf allein ist noch kein
    Netzzugriff) -- erst `.get()` waere der eigentliche Request und wird
    hier stattdessen aufgezeichnet und mit einem Fehler beantwortet, den
    die Produktionslogik ohnehin abfaengt (Fail-soft-Fetch)."""

    def __init__(self, *a, **kw) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a) -> bool:
        return False

    def get(self, url, *a, **kw):
        _NETWORK_ATTEMPTS.append(url)
        raise AssertionError(
            "Netzcall-Tripwire (Issue #1329 C2): .get() haette einen "
            "echten HTTP-Request an open-meteo ausgeloest -- Kern-Tests "
            "duerfen niemals echtes Netz erreichen (CLAUDE.md)."
        )


@pytest.fixture(autouse=True)
def _block_real_network(monkeypatch):
    """Diese Datei testet die Budget-/Prioritaets-Gate-Logik des ECHTEN
    open-meteo-Funnels -- dafuer muss der Offline-Fixture-Kurzschluss
    (Abschnitt 8 der Spec, greift ansonsten VOR dem Budget-Gate) fuer diese
    Tests deaktiviert werden (`tests/conftest.py` setzt GZ_TEST_FIXTURE_DIR
    sonst automatisch fuer jeden nicht-live-Test). Die httpx-Tripwire bleibt
    als Sicherheitsnetz aktiv, falls die Budget-/Guard-Logik den Aufruf
    trotzdem bis zum echten Request durchlaesst."""
    _NETWORK_ATTEMPTS.clear()
    monkeypatch.delenv("GZ_TEST_FIXTURE_DIR", raising=False)
    monkeypatch.setattr(httpx, "Client", _TripwireClient)
    yield
    _NETWORK_ATTEMPTS.clear()


def _budget_path():
    return get_data_root() / "diagnostics" / "forecast_budget.json"


def _write_budget(calls_openmeteo: int) -> None:
    import json
    path = _budget_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "date": date.today().isoformat(),
        "calls": {"openmeteo": calls_openmeteo},
        "cache_hits": 0,
        "cache_misses": 0,
    }
    path.write_text(json.dumps(payload))


# ---------------------------------------------------------------------------
# AC-6: Scheduler-Radar (`priority="polling"`) wird bei Budget-Druck
# abgewiesen -- KEIN Fetch; `/jetzt` (`priority="user_briefing"`) laeuft
# im selben Budget-Zustand weiterhin durch.
# ---------------------------------------------------------------------------

def test_polling_priority_rejected_without_network_at_80_percent_budget():
    """AC-6: `get_nowcast(priority=...)` existiert heute noch nicht --
    RED-Aussage ist der `TypeError` bei der unbekannten Keyword. Nach der
    Implementierung MUSS diese Zeile stattdessen `onset_minutes=None,
    throttled=True` liefern, ohne dass `_NETWORK_ATTEMPTS` waechst."""
    _write_budget(calls_openmeteo=7200)  # 7200/9000 = 80%
    svc = RadarNowcastService()

    result = svc.get_nowcast(_ATLANTIC_LAT, _ATLANTIC_LON, priority="polling")

    assert _NETWORK_ATTEMPTS == [], (
        "AC-6: ein bei >=80% Budget gedrosselter polling-Aufruf darf "
        f"KEINEN HTTP-Versuch ausloesen, tatsaechlich: {_NETWORK_ATTEMPTS}"
    )
    assert result.onset_minutes is None
    assert getattr(result, "throttled", False) is True, (
        "AC-6: das Ergebnis muss throttled=True tragen (Beobachtbarkeits-"
        "Signal, kein Alarm-Fehlverhalten)"
    )


def test_user_briefing_priority_never_throttled_at_same_budget_state():
    """AC-6 Gegenprobe: `/jetzt` (`priority='user_briefing'`) darf im selben
    Budget-Zustand NIE gedrosselt werden -- es MUSS versuchen, echte Daten
    zu holen (die Tripwire faengt den eigentlichen Request danach sicher
    ab, ohne echtes Netz zu beruehren)."""
    _write_budget(calls_openmeteo=8999)  # praktisch voll ausgeschoepft
    svc = RadarNowcastService()

    svc.get_nowcast(_ATLANTIC_LAT, _ATLANTIC_LON, priority="user_briefing")

    assert _NETWORK_ATTEMPTS, (
        "AC-6: user_briefing darf NIE gedrosselt werden -- auch bei fast "
        "vollem Budget muss ein echter Fetch-Versuch unternommen werden "
        "(hier durch die Netz-Tripwire sicher abgefangen), tatsaechlich "
        f"aufgezeichnete Versuche: {_NETWORK_ATTEMPTS}"
    )


# ---------------------------------------------------------------------------
# AC-6 (Aufrufer-Seite): Scheduler-Pfade uebergeben priority="polling"
# ---------------------------------------------------------------------------

class _CapturingRadarService:
    """Reiner Fake (KEIN Mock/patch) -- erfuellt nur den Teil des
    `RadarNowcastService`-Interfaces, den `trip_alert.py`/
    `compare_radar_alert.py` tatsaechlich aufrufen, und zeichnet die
    tatsaechlich uebergebene `priority` auf."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def get_nowcast(self, lat: float, lon: float, priority: str = "user_briefing") -> NowcastResult:
        self.calls.append({"lat": lat, "lon": lon, "priority": priority})
        return NowcastResult(
            onset_minutes=None, intensity_label="Kein Niederschlag",
            source="radar", frames=[],
        )


def test_trip_alert_scheduler_radar_check_uses_polling_priority():
    """AC-6: `TripAlertService.check_radar_alerts()` (Scheduler-Pfad) muss
    `priority='polling'` uebergeben -- heute uebergibt der Aufruf gar keine
    `priority` (`trip_alert.py:677`), der Fake-Default ist
    'user_briefing' -> RED."""
    from app.loader import save_trip
    from app.trip import Stage, Trip, Waypoint
    from services.trip_alert import TripAlertService

    today = date.today()
    trip = Trip(
        id="budget-ac6-trip",
        name="AC6 Budget Trip",
        stages=[
            Stage(
                id="T1", name="Heute", date=today, start_time=time(0, 0),
                waypoints=[
                    Waypoint(
                        id="W1", name="Start", lat=48.0, lon=9.0, elevation_m=500,
                        arrival_override="00:00",
                    ),
                    Waypoint(
                        id="W2", name="Ziel", lat=48.02, lon=9.02, elevation_m=520,
                        arrival_override="23:59",
                    ),
                ],
            )
        ],
    )
    save_trip(trip)

    fake = _CapturingRadarService()
    svc = TripAlertService(user_id="default", radar_service=fake)
    svc.clear_radar_throttle(trip.id)
    svc.check_radar_alerts()

    assert fake.calls, "Radar-Check haette get_nowcast aufrufen muessen"
    assert fake.calls[0]["priority"] == "polling", (
        "AC-6: Scheduler-Radar (TripAlertService.check_radar_alerts) muss "
        f"priority='polling' uebergeben, tatsaechlich: "
        f"{fake.calls[0]['priority']!r}"
    )


def test_compare_radar_scheduler_check_uses_polling_priority():
    """AC-6: `CompareRadarAlertService._detect_triggered_locations()`
    (Scheduler-Pfad) muss `priority='polling'` uebergeben -- heute
    uebergibt der Aufruf gar keine `priority` (`compare_radar_alert.py:140`)
    -> RED."""
    from app.user import SavedLocation
    from services.compare_radar_alert import CompareRadarAlertService

    fake = _CapturingRadarService()
    svc = CompareRadarAlertService(user_id="default", radar_service=fake)
    loc = SavedLocation(id="loc-ac6", name="Testort", lat=47.05, lon=11.15, elevation_m=1200)

    svc._detect_triggered_locations("preset-ac6", ["loc-ac6"], {"loc-ac6": loc})

    assert fake.calls, "Compare-Radar-Check haette get_nowcast aufrufen muessen"
    assert fake.calls[0]["priority"] == "polling", (
        "AC-6: Compare-Radar-Scheduler-Check muss priority='polling' "
        f"uebergeben, tatsaechlich: {fake.calls[0]['priority']!r}"
    )


def test_jetzt_command_uses_user_briefing_priority_explicitly(monkeypatch):
    """AC-6: `/jetzt`-Befehl (`trip_command_processor._show_now`) hat keinen
    DI-Seam fuer `radar_service` -- monkeypatch ersetzt daher NUR, welche
    Klasse `RadarNowcastService()` referenziert (echter Klassenaustausch,
    kein Mock von Verhalten), um die tatsaechlich uebergebene `priority`
    aufzuzeichnen."""
    from app.loader import save_trip
    from app.trip import Stage, Trip, Waypoint
    from services.trip_command_processor import InboundMessage, TripCommandProcessor

    class _CapturingRadarServiceClass:
        last_instance = None

        def __init__(self, *a, **kw) -> None:
            self.calls: list[str] = []
            _CapturingRadarServiceClass.last_instance = self

        def get_nowcast(self, lat, lon, priority: str = "user_briefing") -> NowcastResult:
            self.calls.append(priority)
            return NowcastResult(
                onset_minutes=None, intensity_label="Kein Niederschlag",
                source="radar", frames=[],
            )

        def format_now_text(self, result) -> str:
            return "Kein Niederschlag."

    import services.radar_service as radar_service_module
    monkeypatch.setattr(radar_service_module, "RadarNowcastService", _CapturingRadarServiceClass)

    today = date.today()
    trip = Trip(
        id="ac6-jetzt-trip",
        name="AC6 Jetzt Trip",
        stages=[
            Stage(
                id="T1", name="Heute", date=today, start_time=time(0, 0),
                waypoints=[
                    Waypoint(
                        id="W1", name="Start", lat=48.0, lon=9.0, elevation_m=500,
                        arrival_override="00:00",
                    ),
                    Waypoint(
                        id="W2", name="Ziel", lat=48.02, lon=9.02, elevation_m=520,
                        arrival_override="23:59",
                    ),
                ],
            )
        ],
    )
    save_trip(trip)

    msg = InboundMessage(
        trip_name=trip.name, body="### now", sender="gregor-test@henemm.com",
        channel="email", received_at=datetime.now(tz=timezone.utc),
    )
    result = TripCommandProcessor().process(msg)

    assert result.command == "now"
    instance = _CapturingRadarServiceClass.last_instance
    assert instance is not None and instance.calls, (
        "Der /jetzt-Befehl haette get_nowcast aufrufen muessen"
    )
    assert instance.calls[0] == "user_briefing", (
        "AC-6: /jetzt muss priority='user_briefing' explizit uebergeben "
        f"(Nutzeraktion, nie gedrosselt), tatsaechlich: {instance.calls[0]!r}"
    )


# ---------------------------------------------------------------------------
# AC-7: Doppelverbrauch-Fix (Root Cause 3) -- kein zweiter open-meteo-
# Versuch nach einem Fehlschlag im ersten Zweig, INNERHALB desselben
# get_nowcast()-Aufrufs.
# ---------------------------------------------------------------------------

def test_no_second_openmeteo_branch_attempted_after_first_failure_in_same_call():
    """AC-7: `_DOUBLE_BRANCH_LAT/_LON` liegt sowohl in der AROME-FR- als
    auch in der ICON-D2-Box (ausserhalb RADOLAN/INCA/DPC) -- die
    Quellenkette wuerde ohne Guard AROME-FR -> ICON-D2 -> minutely_15
    (bis zu drei open-meteo-Versuche) durchlaufen. Nach dem Fix darf nach
    dem ERSTEN echten Fehlschlag (hier: die Netz-Tripwire, die einen echten
    429-artigen Fehlschlag simuliert, OHNE echtes Netz zu beruehren) kein
    weiterer Versuch in demselben Aufruf erfolgen -- geprueft am ECHTEN
    Funnel (`_fetch_openmeteo_15`), nicht an einer ihn ersetzenden
    Test-Stub-Methode (die den Guard selbst umgehen wuerde). Bewusst KEIN
    Test des All-None-Guard-Uebergangs (der bleibt Aufgabe des Bestands
    `test_feature_734_arome_france_nowcast.py`)."""
    _write_budget(calls_openmeteo=0)  # kein Budget-Druck -- reiner Guard-Test
    svc = RadarNowcastService()

    result = svc.get_nowcast(_DOUBLE_BRANCH_LAT, _DOUBLE_BRANCH_LON)

    assert len(_NETWORK_ATTEMPTS) == 1, (
        "AC-7 (Doppelverbrauch-Fix, Root Cause 3): nach einem Fehlschlag im "
        "ersten open-meteo-Zweig (AROME-FR) darf die Kette (ICON-D2, dann "
        "der finale minutely_15-Fallback) KEINEN zweiten open-meteo-Versuch "
        f"unternehmen, tatsaechliche Versuche: {_NETWORK_ATTEMPTS}"
    )
    assert result.frames == []


# ---------------------------------------------------------------------------
# AC-8: Sidecar-/Zusatz-open-meteo-Calls zaehlen ueber denselben Funnel
# gegen das geteilte Tagesbudget.
# ---------------------------------------------------------------------------

def test_openmeteo_funnel_records_against_shared_budget_counter():
    """AC-8 (kombiniert mit Implementation-Details-Abschnitt 4 der Spec):
    `_fetch_openmeteo_15` ist der EINZIGE Funnel, durch den JEDER
    open-meteo-Zweig laeuft -- Haupt-Zweige (AROME/ICON/minutely_15) UND
    beide Sidecar-Aufrufe (INCA/DPC-Konvektions-Check). Ein direkter Test
    auf Funnel-Ebene beweist daher den einheitlichen Budget-Einbau
    unabhaengig von der jeweils aufrufenden Quellenkette."""
    _write_budget(calls_openmeteo=0)
    svc = RadarNowcastService()

    svc.get_nowcast(_ATLANTIC_LAT, _ATLANTIC_LON)  # reiner minutely_15-Pfad

    snapshot = ForecastBudgetGate().snapshot()
    assert snapshot["calls_today"] >= 1, (
        "AC-8: ein tatsaechlicher open-meteo-Fetch-Versuch (ueber den "
        "gemeinsamen Funnel _fetch_openmeteo_15, der auch beide Sidecar-"
        f"Zweige bedient) muss gegen den geteilten Budget-Zaehler zaehlen, "
        f"tatsaechlicher Snapshot: {snapshot}"
    )
