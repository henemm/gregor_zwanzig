"""Issue #2009 (Nachmessung), Fix-Loop 1: zwei Ortsvergleichs-Stellen, die
bisher kein Waechter bewachte (Adversary-Befunde F001, F002).

SPEC: docs/specs/modules/fix_2009_laufender_regen_vorlauf.md
(Implementation Details 3 und 4, AC-2)

- F002: Der Fehlversuchs-Backoff-Schluessel des Ortsvergleichs traegt bei
  laufendem Regen KEINEN (je Lauf wandernden) Zeitpunkt, sondern -- wie der
  Trip -- den Wert "laufend". Gemessen am Verhalten: scheitert der Versand
  bei "Regen kommt", gilt der spaetere Lauf mit "Regen laeuft" fuer den
  Backoff als eigenes Ereignis -- im Ortsvergleich GENAU WIE im Trip.
- F001: Der Unterdrueckungs-Eintrag (Ereignis-Entdopplung) des Ortsvergleichs
  traegt bei laufendem Regen Vorlauf 0 und als Beginn den Lauf-Zeitpunkt.

Kein Mock()/patch(): echter `check_all_compare_presets()` bzw.
`check_radar_alerts()` mit echtem `RadarNowcastService(frame_source=...)`;
Versandfehler ueber die steuerbaren Fake-Transporte des `KanalRig` (wie
`test_alarm_totalausfall_wird_wiederholt.py`), Uhr per `freeze_time`.
Jede Kennung ist ein frischer Nutzer, `user_id` immer explizit.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from freezegun import freeze_time

from app.loader import save_location

from tests.helpers.alert_log_fixtures import read_log
from tests.helpers.kanal_fake_transporte import KanalRig, wiederholungs_eintraege
from tests.helpers.nowcast_gate_fixtures import (
    clean_uid, compare_radar_service, location, radar_preset, reset_radar_cache,
    settings_email_only, write_presets, write_user_tier,
)
from tests.tdd.test_952_onset_alert_fidelity import _clean_user
from tests.tdd.test_alarm_totalausfall_wird_wiederholt import (
    _T0, _TripRadar, _VergleichBasis,
)

_SLOT = _T0                                   # 10:00 UTC, INCA-Raster
_LAUF_KOMMT = _SLOT + timedelta(minutes=3)    # 10:03, Taktminute aus `3-58/5`
_LAUF_LAEUFT = _SLOT + timedelta(minutes=18)  # 10:18, Regen seit 10:15
_ANGELEGT: list[str] = []


@pytest.fixture
def rig(monkeypatch):
    r = KanalRig(monkeypatch)
    yield r
    r.stoppen()


@pytest.fixture(autouse=True)
def _aufraeumen():
    _ANGELEGT.clear()
    yield
    for uid in _ANGELEGT:
        clean_uid(uid)
        _clean_user(uid)


def _uid(tag: str) -> str:
    uid = f"tdd-2009-cmp-bo-{tag}-{uuid.uuid4().hex[:6]}"
    _ANGELEGT.append(uid)
    return uid


def _ab_viertel_nach(lat: float, lon: float) -> list:
    """Ueberall trocken bis 10:00, nass ab 10:15 bis 11:00 (INCA-Raster).
    10:03 -> "kommt in 12"; 10:18 -> `already_running`."""
    from providers.brightsky import RadarFrame
    return [
        RadarFrame(timestamp=_SLOT + timedelta(minutes=15 * k),
                   precip_mm_h=3.0 if 1 <= k <= 4 else 0.0)
        for k in range(-1, 13)
    ]


def _laeuft_bereits(lat: float, lon: float) -> list:
    """Laufendes (10:00) und folgende Frames nass bis 10:45."""
    from providers.brightsky import RadarFrame
    return [
        RadarFrame(timestamp=_SLOT + timedelta(minutes=15 * k),
                   precip_mm_h=2.0 if k < 4 else 0.0)
        for k in range(13)
    ]


class _VergleichRadarFrames(_VergleichBasis):
    name = "compare_radar_alert"

    def _lauf(self, ereignis: str):
        from services.compare_radar_alert import CompareRadarAlertService
        from services.radar_service import RadarNowcastService

        return CompareRadarAlertService(
            settings=self.settings, user_id=self.uid,
            radar_service=RadarNowcastService(frame_source=_ab_viertel_nach),
        ).check_all_compare_presets()


class _TripRadarFrames(_TripRadar):
    def _lauf(self, ereignis: str):
        from app.loader import save_trip
        from app.models import TripReportConfig
        from services.radar_service import RadarNowcastService
        from services.trip_alert import TripAlertService
        from tests.helpers.kanal_fake_transporte import kanal_auswahl
        from tests.tdd.test_952_onset_alert_fidelity import _trip_with_active_segment

        config = TripReportConfig(trip_id=self.entity_id, alert_on_changes=True, send_email=True)
        trip = _trip_with_active_segment(self.entity_id, config)
        trip.alert_channels = kanal_auswahl(*self.kanaele)
        save_trip(trip, user_id=self.uid)
        return TripAlertService(
            settings=self.settings, throttle_hours=0, user_id=self.uid,
            radar_service=RadarNowcastService(frame_source=_ab_viertel_nach),
        ).check_radar_alerts()


def _uebergang_kommt_dann_laeuft(rig: KanalRig, pfad) -> tuple[int, int, dict]:
    """Lauf 10:03 ("kommt in 12") scheitert an E-Mail, Lauf 10:18 ("laeuft")
    mit repariertem Draht. Liefert (Versuche, angenommen, Backoff-Stand nach
    Lauf 1)."""
    rig.modus["email"] = "fehler"
    pfad.lauf(_LAUF_KOMMT)
    assert rig.anzahl_versuche("email") >= 1, f"Vorbedingung {pfad.name}: kein Versuch: {rig!r}"
    backoff = wiederholungs_eintraege(pfad.uid)
    assert backoff, f"Vorbedingung {pfad.name}: kein Backoff nach Totalausfall"
    rig.modus["email"] = "ok"
    pfad.lauf(_LAUF_LAEUFT)
    return rig.anzahl_versuche("email"), rig.anzahl_angenommen("email"), backoff


def test_f002_ortsvergleich_backoff_laufender_regen_wie_trip(rig):
    """F002 (Spec Implementation Details 4): GIVEN Ortsvergleich, Lauf 10:03
    meldet "Regen kommt", der einzige Kanal scheitert (Backoff gesetzt) /
    WHEN 15 Minuten spaeter der Regen laeuft (10:18) / THEN ist das fuer den
    Backoff ein eigenes Ereignis ("laufend" statt wanderndem Zeitpunkt): der
    Alarm wird zugestellt -- GENAU WIE im Trip bei denselben Frames.

    Mit einem wandernden Zeitpunkt im Schluessel (10:18, innerhalb der
    30-Min-Toleranz von 10:15) bliebe der Ortsvergleich im Backoff stumm,
    waehrend der Trip zustellt."""
    trip_rig_versuche, trip_angenommen, _ = _uebergang_kommt_dann_laeuft(
        rig, _TripRadarFrames(rig, _uid("trip"), ("email",)),
    )
    assert trip_angenommen == 1, (
        f"Referenz Trip: der laufende Regen muss nach dem Fehlversuch "
        f"zugestellt werden (Versuche={trip_rig_versuche}): {rig!r}"
    )

    # Derselbe Rig zaehlt weiter; der Ortsvergleich wird am Zuwachs gemessen.
    vor_angenommen = rig.anzahl_angenommen("email")
    _versuche, angenommen, _backoff = _uebergang_kommt_dann_laeuft(
        rig, _VergleichRadarFrames(rig, _uid("cmp"), ("email",), entity_id="cp-2009-bo"),
    )
    assert angenommen - vor_angenommen == trip_angenommen, (
        f"F002: im Ortsvergleich muss der laufende Regen nach dem Fehlversuch "
        f"bei 'kommt' zugestellt werden wie im Trip -- ein wandernder Zeitpunkt "
        f"im Backoff-Schluessel haelt ihn faelschlich zurueck. Rig={rig!r}"
    )


def _zeit(raw) -> datetime | None:
    if raw is None:
        return None
    ts = datetime.fromisoformat(str(raw))
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def test_f001_ortsvergleich_unterdrueckungseintrag_laufender_regen_vorlauf_null():
    """F001 (AC-2, Unterdrueckungs-Stelle): GIVEN Ortsvergleich mit laufendem
    Regen, Lauf 10:08 stellt zu (Sperrzeit aus) / WHEN Lauf 10:13 dasselbe
    laufende Ereignis sieht und die Ereignis-Entdopplung ihn unterdrueckt /
    THEN traegt der Unterdrueckungs-Eintrag Vorlauf 0 und Beginn 10:13."""
    uid = _uid("f001")
    preset_id = "cp-2009-f001"
    with freeze_time(_SLOT):
        write_user_tier(uid, "premium")
        save_location(location("loc-2009", "Laufend-Ort"), user_id=uid)
        write_presets(uid, [radar_preset(preset_id, ["loc-2009"], user_id=uid,
                                         cooldown_minutes=0)])
    gesendet = []
    for minute in (8, 13):
        with freeze_time(_SLOT + timedelta(minutes=minute)):
            reset_radar_cache()
            mails: list = []
            gesendet.append(compare_radar_service(
                uid, settings_email_only(), _laeuft_bereits,
                lambda subject, body: mails.append((subject, body)),
            ).check_all_compare_presets())
    reset_radar_cache()
    assert gesendet == [1, 0], f"Vorbedingung: erst Versand, dann Entdopplung ({gesendet})"

    log = read_log(uid)
    unterdrueckt = [
        e for e in log["not_delivered"]
        if e.get("entity_id") == preset_id
        and any(c.get("reason") == "event_duplicate" for c in e.get("channels_not_sent", []))
    ]
    assert len(unterdrueckt) == 1, f"Vorbedingung: ein Unterdrueckungs-Eintrag erwartet: {log!r}"
    eintrag = unterdrueckt[0]
    assert eintrag["lead_time_minutes"] == 0, (
        f"F001: bei laufendem Regen muss der Unterdrueckungs-Eintrag Vorlauf 0 "
        f"tragen, protokolliert ist {eintrag['lead_time_minutes']!r}."
    )
    assert _zeit(eintrag.get("event_at")) == _SLOT + timedelta(minutes=13), (
        f"F001: Beginn muss der Lauf-Zeitpunkt 10:13 sein, ist {eintrag.get('event_at')!r}."
    )
