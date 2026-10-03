"""TDD RED — Issue #2261 Teil A, A-1: jenseits des Horizonts / ohne Frames
kein Alarm (AC-12).

SPEC: docs/specs/modules/feat_2261_a1_radar_vorlauf.md (AC-12)

Mit Schwelle = Horizont (180) ist „Beginn > Schwelle -> kein Alarm" ueber die
echte Quelle nicht mehr konstruierbar. Diese Datei ersetzt die zwei bisherigen
Tests dieser Art (`test_feature_656_radar_nowcast.py::
test_ac4_radar_alert_due_pure_logic`, Fall `later`, und
`test_radar_cooldown_overtake.py::test_f001_...`) durch die zwei Grenzen, die
bleiben: nasse Frames erst JENSEITS der Reichweite der Quelle, und eine Quelle
ganz ohne Frames.

RED-Grund:
* `test_beginn_jenseits_des_horizonts_kein_alarm` — RED ueber die
  Positivkontrolle (nass ab 165 Min loest heute nicht aus, Schwelle 55). Die
  Negativ-Haelfte (nass erst ab 195 Min) faengt einen Ausloese-Guard, der
  ueber die Reichweite der Quelle hinaus zaehlt.
* `test_ohne_frames_kein_alarm_aber_protokoll` — HEUTE GRUEN
  (Regressionswaechter, Spec-Mutation 12): faengt einen Umbau, bei dem der
  Quellenausfall-Waechter vor dem nun weiten Ausloese-Guard verloren geht
  und der Lauf als „ruhig" endet.

Mock-frei: echte `RadarNowcastService`-Ableitung ueber den `frame_source`-Seam
(echte `RadarFrame`-Objekte im 15-Minuten-Raster) bzw. die nachgestellte
Abrufkette (`_AusfallRadar`, #2050 S4a) — `onset_minutes`/`data_unavailable`
bildet der echte Dienst SELBST. Echte `check_radar_alerts()`-Laeufe ueber die
`AlarmPruefstrecke`, gelesen wird ueber `alert_log.read_undelivered()`.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from freezegun import freeze_time

from services import alert_log
from services.radar_cache import reset_shared_radar_cache_for_tests
from services.radar_service import RadarNowcastService

from tests.helpers import radar_vorlauf_strecke as strecke
from tests.helpers.nowcast_gate_fixtures import TRIP_LAT, TRIP_LON, clean_uid

_ETAPPE = strecke.ETAPPE_GANZTAGS  # Nutzer ist ueber Stunden an Punkt 0


def _quelle(nass_ab_min: int, *, frames: int = 17, rate: float = 2.0):
    """Frames ab JETZT im 15-Min-Raster (0..240 Min); nass ab `nass_ab_min`."""
    def _frames(lat: float, lon: float) -> list:
        from providers.brightsky import RadarFrame

        jetzt = datetime.now(timezone.utc)
        return [
            RadarFrame(
                timestamp=jetzt + timedelta(minutes=15 * k),
                precip_mm_h=rate if 15 * k >= nass_ab_min else 0.0,
            )
            for k in range(frames)
        ]
    return _frames


def _onset(quelle) -> object:
    """Testvoraussetzung direkt an der Quelle (Muster F001): was leitet der
    echte Dienst aus diesen Frames ab?"""
    with freeze_time(strecke.AT):
        reset_shared_radar_cache_for_tests()
        ergebnis = RadarNowcastService(frame_source=quelle).get_nowcast(TRIP_LAT, TRIP_LON)
        reset_shared_radar_cache_for_tests()
    return ergebnis


def _lauf(tag: str, radar) -> tuple[int, int, set]:
    """Ein Lauf auf frischem Nutzer; liefert (Alarme, Mails, protokollierte
    Nicht-Zustellungs-Gruende)."""
    u = strecke.uid(tag)
    clean_uid(u)
    try:
        trip = strecke.baue_trip(u, _ETAPPE)
        lauf = strecke.lauf(u, trip, radar)
        vorfaelle = alert_log.read_undelivered(
            u, entity_id=trip.id, entity_type="trip",
            since=strecke.AT - timedelta(minutes=1),
        )
        return lauf.triggered_count, len(lauf.mail), {g for v in vorfaelle for g in v.reasons}
    finally:
        clean_uid(u)


def test_beginn_jenseits_des_horizonts_kein_alarm():
    """AC-12 GIVEN die Quelle liefert bis 180 Min nur trockene Frames, nasse
    erst ab 195 Min / WHEN der Prueflauf laeuft / THEN kein Alarm.

    Positivkontrolle im selben Test (Pflicht): dieselbe Quelle mit nassen
    Frames ab 165 Min (innerhalb der Reichweite, Nutzer noch an Punkt 0) loest
    aus — sonst bewiese die Stille nur, dass die Schwelle noch bei 55 steht.
    """
    jenseits, innerhalb = _quelle(195), _quelle(165)
    vor_jenseits, vor_innerhalb = _onset(jenseits), _onset(innerhalb)
    assert vor_jenseits.onset_minutes is None and not vor_jenseits.data_unavailable, (
        f"Testvoraussetzung: nasse Frames erst ab 195 Min liegen jenseits der "
        f"Reichweite (180) — erwartet kein Beginn, abgeleitet "
        f"{vor_jenseits.onset_minutes!r} (data_unavailable="
        f"{vor_jenseits.data_unavailable})"
    )
    assert vor_innerhalb.onset_minutes == 165, (
        f"Testvoraussetzung: Positivkontrolle muss Beginn 165 ableiten, "
        f"abgeleitet {vor_innerhalb.onset_minutes!r}"
    )
    fenster0 = _ETAPPE.fenster_ende_min()[0]
    assert fenster0 is not None and fenster0 > 180, (
        f"Testvoraussetzung: Nutzer bei 165 Min noch an Punkt 0 ({fenster0})"
    )

    for nutzer in ("a", "b"):
        alarme, mails, _ = _lauf(f"ac12-kontrolle-{nutzer}", RadarNowcastService(frame_source=innerhalb))
        assert (alarme, mails) == (1, 1), (
            f"AC-12 Positivkontrolle ({nutzer}): Beginn in 165 Min liegt in der "
            f"Reichweite der Quelle und muss melden, erhalten Alarme={alarme}, "
            f"Mails={mails}"
        )
        alarme, mails, _ = _lauf(f"ac12-jenseits-{nutzer}", RadarNowcastService(frame_source=jenseits))
        assert (alarme, mails) == (0, 0), (
            f"AC-12 ({nutzer}): nasse Frames erst jenseits der 180 Min duerfen "
            f"keinen Alarm ausloesen, erhalten Alarme={alarme}, Mails={mails}"
        )


def test_ohne_frames_kein_alarm_aber_protokoll():
    """AC-12 GIVEN die Quelle liefert keine Frames (Fremdausfall,
    `data_unavailable`) / WHEN der Prueflauf laeuft / THEN kein Alarm, und
    der Lauf steht als Quellenausfall im Alarmprotokoll — nie als „ruhig".

    Heute gruen (Regressionswaechter)."""
    from tests.tdd.test_radar_data_unavailable_reason import _AusfallRadar

    for nutzer in ("a", "b"):
        alarme, mails, gruende = _lauf(f"ac12-ohne-frames-{nutzer}", _AusfallRadar())
        assert (alarme, mails) == (0, 0), (
            f"AC-12 ({nutzer}): ohne Frames kein Alarm, erhalten Alarme={alarme}, "
            f"Mails={mails}"
        )
        assert alert_log.REASON_DATA_UNAVAILABLE in gruende, (
            f"AC-12 ({nutzer}): der Quellenausfall muss mit "
            f"`{alert_log.REASON_DATA_UNAVAILABLE}` protokolliert sein, nicht als "
            f"ruhige Viertelstunde: {gruende!r}"
        )
