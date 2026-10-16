"""Gemeinsamer Aufbau fuer die Entwarnungs-Tests amtlicher Warnungen
(Issue #1441 Scheibe S2).

SPEC: docs/specs/modules/feat_1441_s2_entwarnung.md

Kein Test-Modul (fuehrender Unterstrich). Geteilt von
``test_official_alert_allclear.py``, ``test_official_alert_allclear_channels.py``
und ``tests/test_avalanche_report_escalation.py``.

Grundsaetze (Projekt-Testpolitik, kein Mock-Theater):

* **Quellen** sind echte Klassen in der ECHTEN Registry
  (``services.official_alerts.base._REGISTERED_SOURCES``) -- nicht der
  Modul-Patch ``stelle_amtliche_quelle``. Nur so laufen die vier Ausfallarten
  (Exception, ``fetch_failed``, ``not_covered``, ``fetch_incomplete``) durch den
  echten ``observe_fetch_failure``-Rahmen in ``base.py``, und nur so sieht auch
  eine kuenftige ``get_official_alerts_with_sources(...)`` dieselben Quellen.
  Registry-``name`` und ``OfficialAlert.source`` sind bewusst GLEICH, damit der
  Test nicht davon abhaengt, welches der beiden Felder die Implementierung als
  ``source`` im Gedaechtnis ablegt.
* **Versand** laeuft durch den echten ``TripAlertService.check_all_trips()``
  bzw. ``CompareOfficialAlertService.check_all_compare_presets()``; abgegriffen
  wird an den vier Ausgangs-Klassen (``tests/helpers/transport_mitschrift.py``).
* **Gedaechtnis** schreibt das Produkt selbst (Lauf 1 meldet eine echte
  Warnung). Gelesen wird ueber den Identitaets-Praefix, nicht ueber den vollen
  Schluessel (der Zeitraum steckt im Schluessel).
* **Uhr:** ``check_official_alert_triggers`` ueberschreibt ``now_utc`` mit der
  Wanduhr -- ``freeze_time`` ist die einzige Uhr-Steuerung. Basis ist die
  ECHTE Jetzt-Minute (``basis_jetzt()``), damit Briefing-Vorlauf (#1594) und
  Profil-Zeitstempel zur Laufzeit passen.
* Nutzerkennungen ohne "test"/"tdd" (Herkunftssperre #2406) ueber
  ``frisches_profil`` -- je Aufruf ein eigener Datenordner.
"""
from __future__ import annotations

import copy
import dataclasses
import re
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta, timezone
from typing import Iterable, Optional

from freezegun import freeze_time

from app.models import (
    ForecastMeta, GPXPoint, NormalizedTimeseries, Provider,
    SegmentWeatherData, SegmentWeatherSummary, TripReportConfig, TripSegment,
)
from app.trip import Stage, Trip, Waypoint
from services.official_alerts import warn_egress
from services.official_alerts.models import OfficialAlert
from tests.helpers.transport_mitschrift import ALLE_KANAELE, Kanalmitschrift

#: Innsbruck -- Punkt A; Punkt B liegt weit genug weg (Rundung auf 3 Stellen).
LAT, LON = 47.2692, 11.4041
LAT_B, LON_B = 47.5000, 12.0000
REGION = "Innsbruck-Land"
GEFAHR = "extreme_heat"  # bewusst KEINE `wet`-Gefahr: kein Ereignis-Identitaets-Register
ALLE = {"email": True, "telegram": True, "sms": True, "premium_sms": True}
OFFICIAL_PREFIX = "official_alert:"

#: Kein Wort einer Handlungsempfehlung (AC-16, nur Daten).
EMPFEHLUNGS_WOERTER = ("sicher", "kannst", "empfehlen", "gefahrlos", "aufbrechen", "losgehen")


def basis_jetzt() -> datetime:
    """Echte Jetzt-Minute (UTC), Sekunden abgeschnitten."""
    return datetime.now(timezone.utc).replace(second=0, microsecond=0)


# ---------------------------------------------------------------------------
# Quellen (echte Registry)
# ---------------------------------------------------------------------------

AUSFALLARTEN = ("exception", "fetch_failed", "not_covered", "fetch_incomplete")


class Warnquelle:
    """Echte amtliche Quelle (Protocol-Subtyping, kein Mock).

    ``alerts``: aktuell gelieferte Warnungen. ``nur_bei``: optional
    ``(lat, lon)`` -- dann liefert ``fetch`` nur an diesem Punkt etwas (an
    anderen, ebenfalls abgedeckten Punkten antwortet sie erfolgreich LEER).
    ``ausfall``: eine der ``AUSFALLARTEN`` oder ``None`` (gesund)."""

    def __init__(self, name: str, alerts: Optional[list] = None, *,
                 nur_bei: Optional[tuple] = None) -> None:
        self.name = name
        self.alerts: list = list(alerts or [])
        self.nur_bei = (round(nur_bei[0], 3), round(nur_bei[1], 3)) if nur_bei else None
        self.ausfall: Optional[str] = None
        self.fetch_calls = 0

    def covers(self, lat: float, lon: float) -> bool:
        return True

    def fetch(self, lat: float, lon: float) -> list:
        self.fetch_calls += 1
        if self.ausfall == "exception":
            raise RuntimeError(f"{self.name}: HTTP 503 (Test-Ausfall)")
        if self.ausfall == "fetch_failed":
            # Genau das, was `cached_fetch()` bei Egress-Block/429/HTTP>=400 tut.
            warn_egress._record_fetch_failure()
            return []
        if self.ausfall == "not_covered":
            warn_egress.mark_not_covered()
            return []
        if self.ausfall == "fetch_incomplete":
            warn_egress.mark_fetch_incomplete()
            return []
        if self.nur_bei is not None and (round(lat, 3), round(lon, 3)) != self.nur_bei:
            return []
        return list(self.alerts)


@contextmanager
def quellen(*qs: Warnquelle):
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


def warnung(level: int, *, quelle: Warnquelle, von: datetime, bis: datetime,
            hazard: str = GEFAHR, region: str = REGION, **extra) -> OfficialAlert:
    labels = {"extreme_heat": "Hitzewarnung", "thunderstorm": "Gewitterwarnung",
              "wind_gust": "Sturmwarnung"}
    return OfficialAlert(
        source=quelle.name, hazard=hazard, level=level,
        label=extra.pop("label", labels.get(hazard, "Warnung")), region_label=region,
        valid_from=von, valid_to=bis, **extra,
    )


# ---------------------------------------------------------------------------
# Gedaechtnis
# ---------------------------------------------------------------------------


def gedaechtnis(uid: str, entity_id: str) -> dict:
    from services.alert_state import AlertStateService

    return AlertStateService(user_id=uid).load(entity_id)


def amtliche_eintraege(uid: str, entity_id: str, *, hazard: str = GEFAHR,
                       region: str = REGION) -> dict:
    """Alle Gedaechtnis-Eintraege derselben Identitaet+Gefahr (Praefix ohne
    Zeitraum, wie `_identity_hazard_prefix`)."""
    praefix = f"{OFFICIAL_PREFIX}region:{region}:{hazard}:"
    return {k: v for k, v in gedaechtnis(uid, entity_id).items() if k.startswith(praefix)}


def einziger_eintrag(uid: str, entity_id: str, **kw) -> dict:
    eintraege = amtliche_eintraege(uid, entity_id, **kw)
    assert len(eintraege) == 1, (
        f"Vorbedingung: genau EIN Gedaechtnis-Eintrag dieser Identitaet erwartet, "
        f"vorhanden: {eintraege!r}")
    return next(iter(eintraege.values()))


# ---------------------------------------------------------------------------
# Inhalte der Mitschrift
# ---------------------------------------------------------------------------


def _texte(sendung: dict) -> str:
    return " ".join(str(sendung.get(f) or "") for f in ("subject", "body", "plain_text_body"))


def entwarnungs_sendungen(mit: Kanalmitschrift, kanal: str) -> list[dict]:
    """Sendungen eines Kanals, die eine Entwarnung tragen: Wort "Entwarnung"
    (Mail/Telegram-Vollform) ODER der `+`-Block der Kurzform (SMS/Premium-SMS/
    Telegram-Kurzform, Spec Abschnitt 7: `+TH:H>L`, `+AV4>2`, `+TH:H>0`)."""
    return [s for s in mit.sendungen(kanal)
            if "Entwarnung" in _texte(s) or re.search(r"(^|\s)\+[A-Z]{2}", _texte(s))]


def entwarnungen_gesamt(mit: Kanalmitschrift) -> int:
    return sum(len(entwarnungs_sendungen(mit, k)) for k in ALLE_KANAELE)


def schnappschuss(mit: Kanalmitschrift) -> Kanalmitschrift:
    snap = copy.deepcopy(mit)
    mit.leeren()
    return snap


# ---------------------------------------------------------------------------
# Trip-Flaeche
# ---------------------------------------------------------------------------


def _segment(seg_id: int, lat: float, lon: float, start: datetime, ende: datetime) -> SegmentWeatherData:
    seg = TripSegment(
        segment_id=seg_id,
        start_point=GPXPoint(lat=lat, lon=lon, elevation_m=600, distance_from_start_km=0.0),
        end_point=GPXPoint(lat=lat + 0.01, lon=lon + 0.01, elevation_m=900, distance_from_start_km=8.0),
        start_time=start, end_time=ende,
        duration_hours=(ende - start).total_seconds() / 3600, distance_km=8.0,
        ascent_m=300, descent_m=0,
    )
    return SegmentWeatherData(
        segment=seg,
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=1.0), data=[],
        ),
        aggregated=SegmentWeatherSummary(), fetched_at=start, provider="openmeteo",
    )


def geometrie_ein_segment(basis: datetime, *, stunden_davor: float = 2, stunden_danach: float = 10):
    return [_segment(1, LAT, LON, basis - timedelta(hours=stunden_davor),
                     basis + timedelta(hours=stunden_danach))]


def geometrie_zwei_segmente(basis: datetime):
    """Segment 1 am Punkt A endet `basis+10 min`; Segment 2 am Punkt B laeuft bis
    `basis+10h`. (Kurz statt 1 h: Laeufe nach `basis+60 min` fielen sonst in den
    Briefing-Vorlauf der Morgen-Zeit `jetzt+3h` und wuerden gesperrt, #1594.)"""
    return [
        _segment(1, LAT, LON, basis - timedelta(hours=2), basis + timedelta(minutes=10)),
        _segment(2, LAT_B, LON_B, basis + timedelta(minutes=10), basis + timedelta(hours=10)),
    ]


def routen_geometrie_setzen(monkeypatch, geometrie: list) -> None:
    """Wetter-Snapshot-Naht (Klassen-Ebene, wie `_alarm_amtlich_fixtures`):
    kein tagesgleicher Δ-Anker (Δ-Zweig schweigt), volle Routen-Geometrie fuer
    den amtlichen Zweig."""
    from services.trip_alert import TripAlertService

    def _fake(self, trip, *, tagesgleicher_anker_noetig, now_utc=None):
        return [] if tagesgleicher_anker_noetig else list(geometrie)

    monkeypatch.setattr(TripAlertService, "_get_cached_weather", _fake)


def trip_nutzer(monkeypatch, *, kanaele: Optional[dict] = None,
                schwellen: Optional[dict] = None, telegram_stil: Optional[str] = None,
                tier: str = "premium", mit_morgen: bool = True) -> tuple[str, Trip]:
    """Frischer Nutzer + gespeicherter Trip (Etappe heute + morgen, alle
    Alarmkanaele, Briefing-Zeiten ausserhalb des Vorlaufs). Die Etappe morgen
    verhindert, dass ein Lauf ueber Ortsmitternacht den Trip als abgelaufen
    ueberspringt, und ist das Ziel des Abend-Briefings.

    Achtung Zeitbudget: die Morgen-Briefingzeit liegt bei Ortsstunde+3 (#1594).
    Alarmlaeufe spaeter als ``t0+60 min`` koennen in deren Vorlauf fallen."""
    from app.loader import save_trip
    from services.trip_day import trip_local_today
    from tests.helpers.briefing_zeiten import briefing_zeiten_fuer_trip
    from tests.tdd._einstellung_auslieferung_fixtures import TRANSPORT_ENV, frisches_profil

    for k, v in TRANSPORT_ENV.items():
        monkeypatch.setenv(k, v)
    uid = frisches_profil(tier=tier)
    trip_id = f"hoehenweg-{uid[-6:]}"
    stage = Stage(
        id="T1", name="Etappe 1", date=date.today(),
        waypoints=[
            Waypoint(id="G1", name="Start", lat=LAT, lon=LON, elevation_m=600.0,
                     arrival_calculated="08:00"),
            Waypoint(id="G2", name="Ziel", lat=LAT_B, lon=LON_B, elevation_m=900.0,
                     arrival_calculated="16:00"),
        ],
    )
    trip = Trip(id=trip_id, name="Hoehenweg-Trip", stages=[stage],
                official_warnings={"enabled": True},
                alert_channels=dict(kanaele or ALLE),
                alert_channel_thresholds=schwellen)
    heute = trip_local_today(trip, datetime.now(timezone.utc))
    trip.stages = [dataclasses.replace(stage, date=heute)]
    if mit_morgen:
        # Etappe MORGEN: Ziel des Abend-Briefings (Muster #1656 -- liegt zu
        # jeder Tageszeit vollstaendig in der Zukunft).
        trip.stages.append(dataclasses.replace(stage, id="T2", name="Etappe 2",
                                               date=heute + timedelta(days=1)))
    morgen, abend = briefing_zeiten_fuer_trip(trip)
    trip.report_config = TripReportConfig(
        trip_id=trip_id, enabled=True, send_email=True, send_telegram=True,
        alert_on_changes=False, morning_time=morgen, evening_time=abend,
    )
    if telegram_stil is not None:
        trip.report_config.telegram_style = telegram_stil
    save_trip(trip, user_id=uid)
    return uid, trip


def trip_lauf(uid: str, zeitpunkt: datetime) -> object:
    """EIN regulaerer Sammellauf des Nutzers zum Zeitpunkt ``zeitpunkt``."""
    from services.trip_alert import TripAlertService
    from tests.tdd._compare_kette_fixtures import settings_fuer

    with freeze_time(zeitpunkt):
        return TripAlertService(settings=settings_fuer(uid), user_id=uid).check_all_trips()


def trip_vorbedingung_alle_kanaele(mit: Kanalmitschrift, kanaele: Iterable[str] = ALLE_KANAELE) -> None:
    """Lauf 1 muss die Warnung WIRKLICH ueber jeden erwarteten Kanal zugestellt
    haben -- sonst ist jede spaetere "nichts kam"-Erwartung wertlos."""
    fehlend = [k for k in kanaele if not mit.sendungen(k)]
    assert not fehlend, f"Vorbedingung: Erstwarnung fehlt auf {fehlend} -- {mit!r}"


# ---------------------------------------------------------------------------
# Ortsvergleich-Flaeche
# ---------------------------------------------------------------------------


def compare_nutzer(monkeypatch, *, kanaele: Optional[dict] = None,
                   schwellen: Optional[dict] = None, tier: str = "premium",
                   **aenderungen) -> tuple[str, dict]:
    """Frischer Nutzer + Orte + Preset-Datei (rohes JSON der Kette-Fixture),
    Slot-Zeiten ausserhalb des Briefing-Vorlaufs. Gibt (uid, preset) zurueck."""
    from zoneinfo import ZoneInfo

    from tests.helpers.briefing_zeiten import briefing_zeiten_iso
    from tests.tdd._compare_kette_fixtures import (
        fixture_dict, nutzer_anlegen, orte_anlegen, preset_ablegen, transport_einrichten,
    )

    transport_einrichten(monkeypatch)
    uid = nutzer_anlegen(tier)
    orte_anlegen(uid)
    p = fixture_dict("alarm_kanaele")
    p["morning_time"], p["evening_time"] = briefing_zeiten_iso(ZoneInfo("Europe/Vienna"))
    p["id"] = f"vergleich-{uid[-6:]}"
    p["alert_channels"] = dict(kanaele or ALLE)
    p["alert_channel_thresholds"] = dict(schwellen or {})
    p.update(aenderungen)
    preset_ablegen(uid, p)
    return uid, p


#: Innsbruck aus der Kette-Fixture (`ORTE["loc-ibk"]`).
IBK_LOC = "loc-ibk"
IBK = (47.27, 11.39)


def compare_lauf(uid: str, zeitpunkt: datetime) -> int:
    from services.compare_official_alert import CompareOfficialAlertService
    from tests.tdd._compare_kette_fixtures import settings_fuer

    with freeze_time(zeitpunkt):
        return CompareOfficialAlertService(
            settings=settings_fuer(uid), user_id=uid,
        ).check_all_compare_presets()


def compare_entity(preset: dict, loc_id: str = IBK_LOC) -> str:
    return f"{preset['id']}:{loc_id}"


def briefing_zeit(stunde: int) -> time:
    return time(stunde % 24, 0)


# ---------------------------------------------------------------------------
# Szenario: EIN Nutzer, EINE Flaeche, EINE meldende Quelle X
# ---------------------------------------------------------------------------

FLAECHEN = ("trip", "vergleich")


class Szenario:
    """Ein Nutzer auf einer Flaeche (``"trip"`` | ``"vergleich"``) mit der
    meldenden Quelle ``x``. ``lauf(minuten)`` fuehrt EINEN regulaeren Alarmlauf
    zum Zeitpunkt ``t0 + minuten`` aus und liefert die Mitschrift genau dieses
    Laufs (danach ist der Aufzeichner leer).

    Die Quelle(n) muessen vom Test per ``with quellen(...)`` registriert sein."""

    def __init__(self, flaeche: str, monkeypatch, mit: Kanalmitschrift, t0: datetime, *,
                 level: int = 4, hazard: str = GEFAHR, quelle: str = "quelle-x",
                 bis_stunden: float = 20, kanaele: Optional[dict] = None,
                 schwellen: Optional[dict] = None, telegram_stil: Optional[str] = None,
                 mit_morgen: bool = True, geometrie: Optional[list] = None,
                 **warn_extra) -> None:
        self.flaeche, self.mit, self.t0, self.hazard = flaeche, mit, t0, hazard
        if flaeche == "trip":
            self.uid, self.trip = trip_nutzer(
                monkeypatch, kanaele=kanaele, schwellen=schwellen,
                telegram_stil=telegram_stil, mit_morgen=mit_morgen,
            )
            routen_geometrie_setzen(monkeypatch, geometrie or geometrie_ein_segment(t0))
            self.entity = self.trip.id
            nur_bei = None
        else:
            self.uid, self.preset = compare_nutzer(monkeypatch, kanaele=kanaele, schwellen=schwellen)
            self.entity = compare_entity(self.preset)
            nur_bei = IBK
        self.x = Warnquelle(quelle, nur_bei=nur_bei)
        self.von = t0 - timedelta(hours=1)
        self.bis = t0 + timedelta(hours=bis_stunden)
        self._warn_extra = warn_extra
        self.x.alerts = [self.warnung(level)]

    def warnung(self, level: int, **kw) -> OfficialAlert:
        extra = {**self._warn_extra, **kw}
        return warnung(level, quelle=self.x, von=extra.pop("von", self.von),
                       bis=extra.pop("bis", self.bis), hazard=extra.pop("hazard", self.hazard),
                       **extra)

    def zeit(self, minuten: float) -> datetime:
        return self.t0 + timedelta(minutes=minuten)

    def lauf(self, minuten: float = 0) -> Kanalmitschrift:
        if self.flaeche == "trip":
            trip_lauf(self.uid, self.zeit(minuten))
        else:
            compare_lauf(self.uid, self.zeit(minuten))
        return schnappschuss(self.mit)

    def eintraege(self, **kw) -> dict:
        kw.setdefault("hazard", self.hazard)
        return amtliche_eintraege(self.uid, self.entity, **kw)

    def eintrag(self, **kw) -> dict:
        kw.setdefault("hazard", self.hazard)
        return einziger_eintrag(self.uid, self.entity, **kw)


def lauf_erstwarnung(sz: Szenario, kanaele: Iterable[str] = ALLE_KANAELE) -> Kanalmitschrift:
    """Lauf 1: die Erstwarnung -- schreibt das Gedaechtnis durch das Produkt.
    Vorbedingung: sie kam wirklich auf jedem erwarteten Kanal an."""
    erst = sz.lauf(0)
    trip_vorbedingung_alle_kanaele(erst, kanaele)
    assert entwarnungen_gesamt(erst) == 0, f"Vorbedingung: Lauf 1 ist eine Warnung, keine Entwarnung: {erst!r}"
    return erst


# ---------------------------------------------------------------------------
# Transport, der auf ALLEN Kanaelen scheitert (AC-11)
# ---------------------------------------------------------------------------


def fehlschlag_installieren(monkeypatch) -> dict:
    """Wie ``aufzeichner_installieren``, nur dass jedes ``send()`` mit einem
    Transportfehler endet (SMTP 554 / Telegram 502 / seven.io 500). Zaehlt
    die Versuche je Kanal -- ein Test kann so belegen, dass der Versand
    ueberhaupt VERSUCHT wurde."""
    from services import notification_service as ns
    import output.channels.email as email_mod

    versuche = {k: 0 for k in ALLE_KANAELE}

    def _fehler(kanal):
        versuche[kanal] += 1
        raise RuntimeError(f"{kanal}: Transportfehler (Test)")

    class _Email:
        def __init__(self, settings) -> None: ...
        def send(self, *a, **k): _fehler("email")

    class _Sms:
        def __init__(self, settings) -> None: ...
        def send(self, *a, **k): _fehler("sms")

    class _Premium:
        def __init__(self, settings) -> None: ...
        def send(self, *a, **k): _fehler("premium_sms")

    class _Telegram:
        def __init__(self, settings, recipient=None) -> None: ...
        def send(self, *a, **k): _fehler("telegram")

    monkeypatch.setattr(ns, "EmailOutput", _Email)
    monkeypatch.setattr(email_mod, "EmailOutput", _Email)
    monkeypatch.setattr(ns, "SMSOutput", _Sms)
    monkeypatch.setattr(ns, "PremiumSmsOutput", _Premium)
    monkeypatch.setattr(ns, "TelegramOutput", _Telegram)
    return versuche


# ---------------------------------------------------------------------------
# Briefing (echter Trip-Briefing-Versand, #1614-Unterbau)
# ---------------------------------------------------------------------------


def trip_briefing(sz: Szenario, minuten: float) -> str:
    """Echtes Abend-Briefing (Ziel: Etappe MORGEN) ueber
    ``TripReportSchedulerService._send_trip_report_outcome`` -- nur der
    Wetter-Abruf ist die Fixture-Unterklasse aus #1614/#1656. Der Briefing-
    Lauf holt die amtlichen Warnungen SELBST aus der Registry (Quellen-
    Gesundheit inklusive) und schreibt das Melde-Gedaechtnis selbst."""
    from tests.tdd._compare_kette_fixtures import settings_fuer
    from tests.tdd.test_alert_state_briefing_reset import _fixture_scheduler_class_1614

    assert sz.flaeche == "trip", "Briefing-Helfer nur fuer die Trip-Flaeche"
    with freeze_time(sz.zeit(minuten)):
        try:
            return _fixture_scheduler_class_1614()(
                settings=settings_fuer(sz.uid), user_id=sz.uid,
            )._send_trip_report_outcome(sz.trip, "evening", on_demand=False)
        except RuntimeError as exc:
            # Ein Transportfehler der E-Mail wird vom Versandpfad weitergereicht
            # (Briefing NICHT zugestellt) -- fuer die Tests ein Ergebnis, kein Absturz.
            return f"nicht_zugestellt: {exc}"


def compare_briefing(monkeypatch, sz: Szenario, minuten: float):
    """Echtes Ortsvergleich-Briefing ueber ``send_one_compare_preset``
    (``scheduler_dispatch_service.py``, Record-Aufruf ~:690). Ersetzt ist nur
    das WETTER der Vergleichs-Engine (``engine_naht`` der Kette); die amtlichen
    Warnungen holt die Engine-Naht ueber DENSELBEN Produkt-Baustein wie
    ``ComparisonEngine`` selbst (``fetch_location_official_alerts``) aus der
    ECHTEN Registry -- Quellen-Gesundheit inklusive ("nicht abrufbar" bei
    Ausfall) und mit dem Pro-Quelle-Mitschnitt desselben Abrufs."""
    import services.comparison_engine as ce_mod
    from tests.tdd._compare_kette_fixtures import briefing_senden, engine_naht, settings_fuer

    assert sz.flaeche == "vergleich", "Briefing-Helfer nur fuer die Ortsvergleich-Flaeche"
    engine_naht(monkeypatch)
    basis = ce_mod.ComparisonEngine

    class _MitAmtlichenWarnungen(basis):  # echte Subklasse, kein Mock
        @staticmethod
        def run(*args, **kwargs):
            ergebnis = basis.run(*args, **kwargs)
            for lr in ergebnis.locations:
                (lr.official_alerts, lr.official_alerts_unavailable,
                 lr.official_alert_query) = ce_mod.fetch_location_official_alerts(
                    lr.location.lat, lr.location.lon)
            return ergebnis

    monkeypatch.setattr(ce_mod, "ComparisonEngine", _MitAmtlichenWarnungen)
    with freeze_time(sz.zeit(minuten)):
        return briefing_senden(sz.uid, sz.preset["id"], settings_fuer(sz.uid))
