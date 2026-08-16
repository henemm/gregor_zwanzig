"""Gemeinsame Bausteine der amtlichen Freigabe-Tests (Issue #1467 S4a).

SPEC: docs/specs/modules/rework_1467_s4a_amtlich.md

Baut auf den Bestands-Helfern auf: ``briefing_imminent_fixtures`` liefert
Trips/Presets/Orte auf Platte, die echte Warnquellen-Registry und die
Zustands-Schnappschuesse; ``nowcast_gate_fixtures`` liefert Tageszaehler und
Sperrzeit. Neu ist nur, was dort fehlt.

Mock-frei: kein ``Mock()``/``patch()``/``MagicMock``. Die Aufzeichner rufen die
ECHTE Fassung auf; die Warnquelle ist ein echtes strukturelles Subtyp-Objekt der
Quellen-Registry. Pfadregel #1409: alles ueber ``app.loader``.
"""
from __future__ import annotations

import sys
from datetime import date as date_type
from datetime import datetime, timedelta, timezone

from tests.helpers.briefing_imminent_fixtures import (  # noqa: F401  (Re-Export)
    TRIP_LAT, TRIP_LON, TRIP_ZONE, load_trip_obj, nur_diese_warnquelle,
    settings_email_only,
)


class gate_spion:
    """Zeichnet die LAUFZEIT-Reihenfolge benannter Funktionsaufrufe auf.

    🔴 Warum der Name an MEHREREN Stellen getauscht wird:
    ``from services.alert_gate import f`` bindet ``f`` im VERBRAUCHENDEN Modul
    zur Import-Zeit — ein Tausch allein im Ursprungsmodul bliebe dann wirkungslos
    und der Test still blind. Ein Tausch NUR im Verbraucher waere umgekehrt
    blind, wenn dieser erst im Methodenrumpf importiert (so macht es
    ``trip_alert.py`` heute mit ``check_briefing_imminent``). Deshalb: Ursprung
    UND jede bestehende Bindung desselben Objekts in ``sys.modules``. Wer erst
    WAEHREND der Aufzeichnung importiert, zieht ohnehin die getauschte Fassung.

    Jeder zaehlende Test fuehrt zusaetzlich einen Kontroll-Lauf, in dem der
    Zaehler beweisbar hochgeht — sonst waere „0" auch die Antwort einer toten Naht.
    """

    NAMEN = ("check_official_alert_gate", "check_briefing_imminent")
    MODUL = "services.alert_gate"

    def __init__(self, namen=None, *, modulname: str | None = None) -> None:
        self._namen = tuple(namen) if namen else self.NAMEN
        self._modulname = modulname or self.MODUL
        self.aufrufe: list[str] = []

    def _stellen(self, name: str, wert) -> list:
        """Alle Namensraeume, in denen ``name`` an ``wert`` gebunden ist."""
        treffer = [self._ursprung]
        for modul in list(sys.modules.values()):
            if modul is None or modul is self._ursprung:
                continue
            try:
                if getattr(modul, name, None) is wert:
                    treffer.append(modul)
            except Exception:  # pragma: no cover - lazy __getattr__ o.ae.
                continue
        return treffer

    def __enter__(self) -> "gate_spion":
        import importlib

        self._ursprung = importlib.import_module(self._modulname)
        self._originale: dict = {}
        self._wrapper: dict = {}
        for name in self._namen:
            original = getattr(self._ursprung, name)  # fehlt -> AttributeError
            self._originale[name] = original

            def _bauen(name=name, original=original):
                def _aufzeichnend(*args, **kwargs):
                    self.aufrufe.append(name)
                    return original(*args, **kwargs)
                _aufzeichnend.__name__ = name
                return _aufzeichnend

            self._wrapper[name] = _bauen()
            for modul in self._stellen(name, original):
                setattr(modul, name, self._wrapper[name])
        return self

    def __exit__(self, *exc) -> bool:
        for name, original in self._originale.items():
            for modul in self._stellen(name, self._wrapper[name]):
                setattr(modul, name, original)
        return False

    def zaehle(self, name: str) -> int:
        return self.aufrufe.count(name)

    def reihenfolge(self) -> list[str]:
        return list(self.aufrufe)


class zaehlende_tagesgrenze:
    """Zaehlt Aufrufe der Tages-Obergrenze — echte Fassung, echtes Ergebnis.

    ``alert_gate.py`` ruft ``alert_daily_limit.is_allowed(...)`` ueber das
    MODUL-Objekt auf (``from services import alert_daily_limit``); der Tausch des
    Modulattributs wirkt deshalb an der Aufrufstelle.
    """

    def __init__(self) -> None:
        self.aufrufe = 0

    def __enter__(self) -> "zaehlende_tagesgrenze":
        from services import alert_daily_limit

        self._modul = alert_daily_limit
        self._original = alert_daily_limit.is_allowed

        def _aufzeichnend(*args, **kwargs):
            self.aufrufe += 1
            return self._original(*args, **kwargs)

        alert_daily_limit.is_allowed = _aufzeichnend
        return self

    def __exit__(self, *exc) -> bool:
        self._modul.is_allowed = self._original
        return False


class StufenWarnquelle:
    """Echte Warnquelle (strukturelles Subtyping) mit steuerbarer Warnstufe —
    dasselbe Ereignis einmal GELB (2), einmal ORANGE (3).

    Identitaet (``source``/``hazard``/``region_label``) bleibt ueber beide Stufen
    gleich; nur so wertet ``official_alert_revision_verdict()`` den zweiten
    Abruf als ESKALATION statt als neue Warnung.
    """

    def __init__(self, lat: float = TRIP_LAT, lon: float = TRIP_LON, *,
                 hazard: str = "wind", region_label: str = "Testregion-S4a") -> None:
        self._lat, self._lon = lat, lon
        self._hazard, self._region_label = hazard, region_label
        self.level = 2
        self.fetch_calls = 0

    @property
    def name(self) -> str:
        return "test-1467s4a-stufenquelle"

    def covers(self, lat: float, lon: float) -> bool:
        return abs(lat - self._lat) < 0.15 and abs(lon - self._lon) < 0.15

    def fetch(self, lat: float, lon: float, **kwargs) -> list:
        from services.official_alerts.models import OfficialAlert

        self.fetch_calls += 1
        jetzt = datetime.now(timezone.utc)
        return [OfficialAlert(
            source="test-1467s4a", hazard=self._hazard, level=self.level,
            label=f"Sturmwarnung Stufe {self.level}", region_label=self._region_label,
            valid_from=jetzt - timedelta(hours=1), valid_to=jetzt + timedelta(hours=12))]


def schnappschuss_speichern(user_id: str, trip_id: str, *,
                            lat: float = TRIP_LAT, lon: float = TRIP_LON) -> None:
    """Wetter-Schnappschuss des Trips auf Platte.

    ``check_official_alert_triggers()`` liest die Segment-Koordinaten
    AUSSCHLIESSLICH aus dem Schnappschuss (``_get_cached_weather``) — ohne ihn
    bleibt jede Warnquelle unerreichbar und der Test gruen aus falschem Grund.
    """
    from app.models import (
        ForecastMeta, GPXPoint, NormalizedTimeseries, Provider, SegmentWeatherData,
        SegmentWeatherSummary, TripSegment,
    )
    from services.weather_snapshot import WeatherSnapshotService

    jetzt = datetime.now(timezone.utc)
    segment = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=lat, lon=lon, elevation_m=1000, distance_from_start_km=0.0),
        end_point=GPXPoint(lat=lat + 0.1, lon=lon + 0.1, elevation_m=1200,
                           distance_from_start_km=6.0),
        start_time=jetzt - timedelta(hours=1), end_time=jetzt + timedelta(hours=3),
        duration_hours=4.0, distance_km=6.0, ascent_m=200, descent_m=0)
    daten = SegmentWeatherData(
        segment=segment,
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=1.0),
            data=[]),
        aggregated=SegmentWeatherSummary(precip_sum_mm=2.0),
        fetched_at=jetzt, provider="openmeteo")
    WeatherSnapshotService(user_id=user_id).save_dated(trip_id, date_type.today(), [daten])


def gelb_ins_melde_gedaechtnis(user_id: str, trip_id: str, quelle: StufenWarnquelle) -> int:
    """Runde 1 der Eskalation: GELB wird erkannt und ins Melde-Gedaechtnis
    geschrieben — ohne Versand, ueber die echten Produktivfassungen.
    Returns die Anzahl erkannter Warnungen (Aufbau-Nachweis)."""
    from services.trip_alert import TripAlertService

    quelle.level = 2
    with nur_diese_warnquelle(quelle):
        dienst = TripAlertService(settings=settings_email_only(), throttle_hours=2,
                                  user_id=user_id)
        gelb = dienst.check_official_alert_triggers(load_trip_obj(user_id, trip_id))
        if gelb:
            dienst._record_official_alert_state(trip_id, gelb)
    return len(gelb)


def trip_amtlicher_lauf(user_id: str, *, quelle, settings=None) -> tuple[int, list]:
    """Echter ``check_all_trips()``-Lauf mit lokaler Warnquelle — bewusst der
    oeffentliche Sammel-Einstieg, damit der amtliche Versand durch dieselbe Kette
    laeuft wie im Betrieb. Returns ``(versendete Alarme, mail_sink-Rufe)``."""
    from services.trip_alert import TripAlertService

    mails: list = []
    with nur_diese_warnquelle(quelle):
        ergebnis = TripAlertService(
            settings=settings or settings_email_only(), throttle_hours=2, user_id=user_id,
            mail_sink=lambda subject, body: mails.append((subject, body)),
        ).check_all_trips()
    return ergebnis.alerts_sent, mails


def trip_amtlicher_direktlauf(user_id: str, trip_id: str, *,
                              settings=None, level: int = 3) -> tuple[bool, list]:
    """Echter ``_send_official_alert_only()``-Lauf — DIE Aufrufstelle, an der der
    geteilte Baustein einsortiert wird.

    Fuer Reihenfolge-Nachweise (AC-12) bewusst der Direktaufruf: der
    Sammel-Einstieg wuerde die Briefing-Sperre zusaetzlich aus dem Aenderungspfad
    rufen und die aufgezeichnete Reihenfolge verrauschen.
    """
    from services.official_alerts.models import OfficialAlert
    from services.trip_alert import TripAlertService

    mails: list = []
    dienst = TripAlertService(
        settings=settings or settings_email_only(), throttle_hours=2, user_id=user_id,
        mail_sink=lambda subject, body: mails.append((subject, body)))
    jetzt = datetime.now(timezone.utc)
    warnung = OfficialAlert(
        source="test-1467s4a", hazard="wind", level=level, label="Sturmwarnung",
        region_label="Testregion-S4a",
        valid_from=jetzt - timedelta(hours=1), valid_to=jetzt + timedelta(hours=12))
    return bool(dienst._send_official_alert_only(
        load_trip_obj(user_id, trip_id), [(warnung, ["1"])])), mails
