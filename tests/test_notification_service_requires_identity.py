"""Kern-Schicht: ``NotificationService`` scheitert fail-closed, wenn ihm beim
Konstruieren weder ``settings`` noch ``user_id`` mitgegeben werden -- statt
still intern ``Settings().with_user_profile("default")`` aufzurufen (#2151
Scheibe C, Vorbild Scheibe B ``requireUser()``).

Spec: docs/specs/modules/fix_2151_default_fallbacks_scheibe_c.md (Test 7/8,
AC-5)

Heute (RED):
  * ``NotificationService()`` (kein Argument) baut klaglos
    ``Settings().with_user_profile("default")`` -- kein ``ValueError``.
  * Wird mit ``settings`` aber ohne ``user_id`` konstruiert, greift eine
    Operation, die ``self._user_id`` braucht (``send_official_alert`` ->
    ``WeatherSnapshotService(user_id=self._user_id)``), klaglos mit dem
    impliziten Wert ``"default"`` zu -- statt vorher fail-closed mit einem
    eindeutigen Fehler zu scheitern.

Nachweisform (kein Mock-Theater): ein echter Zaehl-Wrapper um
``Settings.with_user_profile`` (ruft die Originalmethode unveraendert auf)
sowie eine echte Aufzeichner-Klasse an der ``WeatherSnapshotService``-
Konstruktionsnaht (ersetzt den Netz-/Dateizugriff nicht, sie WIRFT nur
sofort, um den Erreichungspunkt zu belegen -- kein ``Mock()``/``patch()``
auf ``NotificationService`` selbst). Echte ``Trip``/``Stage``/``Waypoint``-
Objekte, isolierte Datenwurzel (autouse ``tests/conftest.py::_isolate_data_root``).
"""
from __future__ import annotations

from datetime import date, time

import pytest

from app.config import Settings
from app.trip import Stage, TimeWindow, Trip, Waypoint
from services.notification_service import NotificationService

LAT, LON = 47.2692, 11.4041


def _minimaler_trip(trip_id: str = "t-identitaet") -> Trip:
    wps = [
        Waypoint(
            id="G1", name="Start", lat=LAT, lon=LON, elevation_m=600,
            time_window=TimeWindow(start=time(0, 0), end=time(0, 0)),
        ),
    ]
    stage = Stage(id="T1", name="Etappe", date=date.today(), start_time=time(8, 0), waypoints=wps)
    return Trip(id=trip_id, name="Identitaets-Trip", stages=[stage])


def _with_user_profile_zaehler(monkeypatch) -> list[str]:
    """Echter Zaehl-Wrapper um ``Settings.with_user_profile`` -- ruft die
    Originalmethode unveraendert auf, zeichnet nur die angefragten
    ``user_id``-Werte auf. Kein ``Mock()``/``patch()``."""
    aufrufe: list[str] = []
    original = Settings.with_user_profile

    def _gezaehlt(self: Settings, user_id: str) -> Settings:
        aufrufe.append(user_id)
        return original(self, user_id)

    monkeypatch.setattr(Settings, "with_user_profile", _gezaehlt)
    return aufrufe


# ═══════════════════════════ AC-5 (Test 7) ═══════════════════════════════════


def test_ac5_konstruktor_ohne_settings_und_ohne_user_id_wirft_valueerror(monkeypatch):
    """AC-5 / Test 7: ``NotificationService()`` ohne ``settings`` und ohne
    ``user_id`` wirft ``ValueError`` und liest zu keinem Zeitpunkt
    ``users/default/user.json`` (kein ``with_user_profile``-Aufruf ueberhaupt).

    RED heute: der Konstruktor laeuft klaglos durch und ruft intern
    ``Settings().with_user_profile("default")`` auf.
    """
    aufrufe = _with_user_profile_zaehler(monkeypatch)

    with pytest.raises(ValueError):
        NotificationService()  # type: ignore[call-arg]  -- Identitaet bewusst weggelassen

    assert aufrufe == [], (
        "AC-5: NotificationService() ohne Identitaet hat trotz (erwartetem) "
        f"ValueError Settings.with_user_profile aufgerufen: {aufrufe}"
    )


# ═══════════════════════════ AC-5 (Test 8) ═══════════════════════════════════


class _ErreichtWeatherSnapshotService(Exception):
    """Belegt, dass ``send_official_alert`` bis zur ``WeatherSnapshotService``-
    Konstruktion mit ``self._user_id`` gelaufen ist -- OHNE die echte Klasse
    zu ersetzen (nur die Konstruktion wirft sofort, kein Netz-/Dateizugriff)."""

    def __init__(self, user_id: object) -> None:
        super().__init__(f"WeatherSnapshotService(user_id={user_id!r}) erreicht")
        self.user_id = user_id


class _WeatherSnapshotServiceFalle:
    def __init__(self, user_id: str = "default") -> None:
        raise _ErreichtWeatherSnapshotService(user_id)


def test_ac5_operation_ohne_gesetzte_user_id_scheitert_fail_closed(monkeypatch):
    """AC-5 / Test 8: ``NotificationService(settings=...)`` OHNE ``user_id``
    konstruiert -- eine Operation, die ``self._user_id`` braucht
    (``send_official_alert``), muss VOR dem Zugriff mit einem eindeutigen
    Fehler scheitern, statt den impliziten Wert ``"default"`` an
    ``WeatherSnapshotService`` durchzureichen.

    RED heute: ``self._user_id`` ist implizit ``"default"`` (Konstruktor-
    Default) -- die Falle wird MIT ``user_id="default"`` erreicht, was genau
    den stillen Rueckfall belegt, den AC-5 verbietet.
    """
    import services.weather_snapshot as weather_snapshot_mod

    monkeypatch.setattr(weather_snapshot_mod, "WeatherSnapshotService", _WeatherSnapshotServiceFalle)

    service = NotificationService(settings=Settings())  # type: ignore[call-arg]  -- user_id bewusst weggelassen
    trip = _minimaler_trip()

    with pytest.raises(Exception) as exc_info:
        service.send_official_alert(trip, notices=[], effective_channels=set())

    fund = exc_info.value
    assert not isinstance(fund, _ErreichtWeatherSnapshotService), (
        "AC-5: send_official_alert griff mit implizitem "
        f"user_id={getattr(fund, 'user_id', '?')!r} auf WeatherSnapshotService "
        "zu, statt vorher fail-closed mit einem eindeutigen Identitaetsfehler "
        "zu scheitern"
    )
