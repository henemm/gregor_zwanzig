"""TDD RED -- Fix #3085: Radar-Fristablauf in der Parallelphase bricht die Einheit ab.

SPEC: docs/specs/modules/fix_3085_radar_grenzabbruch.md (AC-1 .. AC-7)

Laeuft die Radar-Frist mitten in der Parallelphase ab, wurde die Einheit bisher
mit Luecken ausgewertet (Trip) bzw. der Ort als Ausfall protokolliert
(Ortsvergleich, ``skipped="timeout"``). ADR-0082 Punkt 5: ein Grenzabbruch ist
keine Entwarnung -- keine Auswertung, kein Protokolleintrag, kein Stempel.

Kein Mock-Theater: echte ``RadarNowcastService``-Unterklasse am DI-Seam (wie
``test_radar_alarmlauf_fairness.py``), echte Threads im echten
``parallel_fetch``-Baustein, echte Schlafzeit, echte Trips/Ortsvergleiche,
echte Stempel- und Protokolldateien. Der Baustein ``wirf_radar_grenze`` wird
zusaetzlich direkt mit echten ``FetchOutcome``-Objekten geprueft (Grund
``deadline`` vs. ``timeout`` deterministisch, ohne Zeitwettlauf).
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest

from api.routers.scheduler import _radar_run_response
from services import parallel_fetch
from services import radar_service as radar_service_mod
from services.parallel_fetch import FetchOutcome
from services.radar_service import RadarDeadlineExceeded

from tests.tdd.test_radar_alarmlauf_fairness import (  # noqa: F401 (autouse-Fixture)
    COMPARE_STATE,
    TRIP_STATE,
    _alert_log_has_entries,
    _alert_log_text,
    _compare_service,
    _gestellte_uhr,
    _loc_idx,
    _make_multi_preset,
    _make_trips,
    _patch_deadline,
    _read_state,
    _ScriptedRadar,
    _trip_idx,
    _trip_service,
    _uid,
    _write_state,
)

# Frist und Haengezeit: der haengende Worker laeuft deutlich ueber die Frist
# hinaus (keine Mikrosekunden-Wettlaeufe), alle anderen Abrufe sind sofort fertig.
FRIST_S = 0.8
HAENGEN_S = 2.0


@pytest.fixture(autouse=True)
def _frischer_baustein():
    """Eigener Executor je Test; verwaiste (haengende) Worker vor dem
    Abraeumen abwarten, damit sie keine Dateien eines Folgetests beschreiben."""
    parallel_fetch._reset_for_tests()
    yield
    if parallel_fetch._executor is not None:
        parallel_fetch._executor.shutdown(wait=True)
    parallel_fetch._reset_for_tests()


class _HaengenderRadar(_ScriptedRadar):
    """Echte Unterklasse: der ``haenge_nr``-te Aufruf der Einheit ``haenge_einheit``
    schlaeft ``HAENGEN_S`` (laeuft also beim Fristablauf noch). Zaehlung unter
    Lock, weil die Zonenpunkte/Orte parallel in Workern ankommen."""

    def __init__(self, idx_fn, *, haenge_einheit: int, haenge_nr: int, **kw) -> None:
        super().__init__(idx_fn, **kw)
        self._lock = threading.Lock()
        self._haenge = (haenge_einheit, haenge_nr)
        self._zaehler: dict[int, int] = {}
        self.gehangen = 0

    def get_nowcast(self, lat, lon, *a, **kw):
        idx = self._idx_fn(lat)
        with self._lock:
            n = self._zaehler.get(idx, 0) + 1
            self._zaehler[idx] = n
        if (idx, n) == self._haenge:
            with self._lock:
                self.gehangen += 1
            time.sleep(HAENGEN_S)
        return super().get_nowcast(lat, lon, *a, **kw)


def _warnungen(caplog, *woerter: str) -> list[str]:
    return [
        r.getMessage() for r in caplog.records
        if r.levelno >= logging.WARNING
        and all(w.lower() in r.getMessage().lower() for w in woerter)
    ]


# ===========================================================================
# Baustein: wirf_radar_grenze (AC-1/AC-2/AC-3/AC-4/AC-6)
# ===========================================================================

def _outcomes(*arten) -> list[FetchOutcome]:
    """Je Art ein Outcome: "ok", "fehler", "deadline", "timeout"."""
    outs = []
    for i, art in enumerate(arten):
        out = FetchOutcome(index=i, item=(47.0 + 0.1 * i, 11.0, 1000))
        if art == "ok":
            out.value = object()
        elif art == "fehler":
            out.error = RuntimeError("503 Quelle")
        else:
            out.skipped = art
        outs.append(out)
    return outs


def test_baustein_timeout_ist_grenzabbruch():
    """AC-1/AC-2: ein beim Fristablauf noch laufender Worker (``timeout``) ist
    ein Grenzabbruch. Mutationen 1 und 2 (skipped-Zweig weg / nur deadline)."""
    with pytest.raises(RadarDeadlineExceeded):
        radar_service_mod.wirf_radar_grenze(_outcomes("ok", "timeout", "ok"))


def test_baustein_nie_gestartet_ist_grenzabbruch():
    """AC-3: ein wegen der Frist nie gestarteter Punkt/Ort (``deadline``) ist ein
    Grenzabbruch -- ohne dass irgendein Worker noch laeuft. Mutation 3."""
    with pytest.raises(RadarDeadlineExceeded):
        radar_service_mod.wirf_radar_grenze(_outcomes("ok", "ok", "deadline"))


def test_baustein_ohne_uebersprungene_kein_grenzabbruch():
    """AC-6: vollstaendige Ergebnisse und echte Quellenfehler (ohne Frist) sind
    KEIN Grenzabbruch -- auch wenn die Frist inzwischen abgelaufen waere.
    Mutation 7 (zu breit werfen)."""
    radar_service_mod.wirf_radar_grenze(_outcomes("ok", "fehler", "ok"))
    radar_service_mod.wirf_radar_grenze(_outcomes())


def test_baustein_worker_grenze_bleibt_grenzabbruch():
    """Bestand (#1539 S4): ein im Worker geworfener ``RadarDeadlineExceeded``
    geht weiterhin hoch -- unveraendert."""
    outs = _outcomes("ok", "ok")
    outs[1].error = RadarDeadlineExceeded("im Worker")
    with pytest.raises(RadarDeadlineExceeded):
        radar_service_mod.wirf_radar_grenze(outs)


def test_baustein_log_zeile_je_uebersprungenem_punkt(caplog):
    """AC-4: vor dem Abbruch steht fuer JEDEN uebersprungenen Punkt eine
    WARNING-Zeile mit Grund (nichts still weggelassen). Mutation 4."""
    caplog.set_level(logging.DEBUG)
    with pytest.raises(RadarDeadlineExceeded):
        radar_service_mod.wirf_radar_grenze(
            _outcomes("ok", "timeout", "deadline", "deadline", "ok")
        )
    assert len(_warnungen(caplog, "timeout")) >= 1, (
        f"Fuer den laufenden Punkt fehlt die Zeile mit Grund: {caplog.messages!r}"
    )
    assert len(_warnungen(caplog, "deadline")) >= 2, (
        f"Fuer beide nie gestarteten Punkte muss je eine Zeile stehen: {caplog.messages!r}"
    )


# ===========================================================================
# AC-1: Trip -- Zonenpunkt-Worker laeuft beim Fristablauf noch
# ===========================================================================

def test_ac1_trip_haengender_zonenpunkt_bricht_die_einheit_ab(monkeypatch, caplog):
    """Given ein (nasser) Trip, dessen erster Zonenpunkt-Worker beim Fristablauf
    noch laeuft / Then: kein Alarm, kein Protokoll, kein Stempel, keine
    Sperrzeit, ``hit_deadline``, Trip in ``skipped_ids``, Endpunkt ``partial``.
    Heute: Luecke, Auswertung laeuft weiter, der Trip alarmiert und wird gestempelt."""
    from services.throttle_store import ThrottleStore

    uid = _uid("3085t")
    ids = _make_trips(uid, ["trip-3085"])
    mails: list = []
    radar = _HaengenderRadar(_trip_idx, haenge_einheit=0, haenge_nr=2, wet=True)
    _patch_deadline(monkeypatch, FRIST_S)
    caplog.set_level(logging.DEBUG)

    result = _trip_service(uid, radar, mails).check_radar_alerts_run()

    assert radar.gehangen == 1, "Testaufbau: der Zonenpunkt-Worker muss gehangen haben"
    assert result.hit_deadline is True, f"Einheit muss abgebrochen sein: {result!r}"
    assert result.alerts_sent == 0 and not mails, (
        f"Teildaten duerfen keinen Alarm ausloesen: {result!r}, {len(mails)} Mails"
    )
    assert result.skipped_ids == ids and result.checked == 0, result
    assert not _alert_log_has_entries(uid), (
        f"Grenzabbruch darf nichts protokollieren: {_alert_log_text(uid)!r}"
    )
    assert ids[0] not in _read_state(uid, TRIP_STATE), "Abgebrochener Trip gestempelt"
    assert ThrottleStore(uid).last_sent("radar", ids[0]) is None, "Sperrzeit gebucht"
    body = _radar_run_response(result, "radar_alert", uid)
    assert body["status"] == "partial" and body.get("reason") == "deadline", body
    assert _warnungen(caplog, "timeout"), (
        f"Der laufende Zonenpunkt muss mit Grund im Log stehen: {caplog.messages!r}"
    )


def test_ac6_trip_ohne_haengen_alarmiert_normal(monkeypatch):
    """AC-6 (Gegenprobe zu AC-1): derselbe Aufbau, alle Abrufe innerhalb der
    Frist fertig ⇒ normale Auswertung: genau ein Alarm, Stempel, Status ok."""
    uid = _uid("3085tok")
    ids = _make_trips(uid, ["trip-3085"])
    mails: list = []
    _patch_deadline(monkeypatch, 600.0)

    result = _trip_service(uid, _ScriptedRadar(_trip_idx, wet=True), mails).check_radar_alerts_run()

    assert result.hit_deadline is False and result.alerts_sent == 1 and len(mails) == 1, result
    assert ids[0] in _read_state(uid, TRIP_STATE)
    assert _radar_run_response(result, "radar_alert", uid)["status"] == "ok"


# ===========================================================================
# AC-2: Ortsvergleich -- Orts-Worker laeuft beim Fristablauf noch
# ===========================================================================

def test_ac2_compare_haengender_ort_bricht_ab_ohne_ausfall_eintrag(monkeypatch, caplog):
    """Given ein Ortsvergleich mit 2 Orten (nass), Ort 2 haengt ueber die Frist /
    Then: kein Alarm, KEIN Ausfall-Protokolleintrag, kein Stempel,
    ``hit_deadline``, Endpunkt ``partial``. Heute: Ort 2 zaehlt als Ausfall
    (protokolliert), Ort 1 alarmiert, Preset gestempelt. Mutation 5."""
    uid = _uid("3085c")
    preset = _make_multi_preset(uid, "mp", 2)
    mails: list = []
    radar = _HaengenderRadar(_loc_idx, haenge_einheit=1, haenge_nr=1, wet=True)
    _patch_deadline(monkeypatch, FRIST_S)
    caplog.set_level(logging.DEBUG)

    result = _compare_service(uid, radar, mails).check_all_compare_presets_run()

    assert radar.gehangen == 1, "Testaufbau: der Orts-Worker muss gehangen haben"
    assert result.hit_deadline is True, f"Preset muss abgebrochen sein: {result!r}"
    assert result.alerts_sent == 0 and not mails, (result, len(mails))
    assert result.skipped_ids == [preset] and result.checked == 0, result
    assert not _alert_log_has_entries(uid), (
        f"Zeitueberschreitung ist kein Ausfall: {_alert_log_text(uid)!r}"
    )
    assert preset not in _read_state(uid, COMPARE_STATE), "Abgebrochenes Preset gestempelt"
    body = _radar_run_response(result, "compare_radar_alert", uid)
    assert body["status"] == "partial" and body.get("reason") == "deadline", body
    assert _warnungen(caplog, "loc-mp-1", "timeout"), (
        f"Der laufende Ort muss mit Grund im Log stehen: {caplog.messages!r}"
    )


def test_ac6_compare_quellenausfall_ohne_frist_bleibt_protokolliert(monkeypatch):
    """AC-6: echter Quellenausfall (Fehler, keine Frist) bleibt wie bisher ein
    protokollierter Ausfall, der andere Ort alarmiert -- kein Grenzabbruch."""
    uid = _uid("3085cf")
    _make_multi_preset(uid, "mp", 2)
    mails: list = []
    radar = _ScriptedRadar(_loc_idx, wet=True, raise_on=(0, 1, RuntimeError("503 Quelle")))
    _patch_deadline(monkeypatch, 600.0)

    result = _compare_service(uid, radar, mails).check_all_compare_presets_run()

    assert result.hit_deadline is False and result.alerts_sent == 1, result
    assert "data_unavailable" in _alert_log_text(uid), _alert_log_text(uid)


# ===========================================================================
# AC-5: Fairness -- abgebrochene Einheit kommt im Folgelauf zuerst
# ===========================================================================

def test_ac5_trip_abgebrochen_steht_im_folgelauf_vorn(monkeypatch):
    """Trip A (Stempel aelter als B) ist im ersten Lauf zuerst dran und bricht
    an der Frist ab. Wuerde A trotzdem gestempelt, stuende im Folgelauf B vorn
    (B-Stempel aelter als ``jetzt``). Erwartet: A bleibt vorn. Mutation 6."""
    uid = _uid("3085f")
    ids = _make_trips(uid, ["t-a", "t-b"])
    jetzt = datetime.now(timezone.utc)
    _write_state(uid, TRIP_STATE, {ids[0]: jetzt - timedelta(hours=2),
                                   ids[1]: jetzt - timedelta(hours=1)})
    _patch_deadline(monkeypatch, FRIST_S)
    lauf1 = _trip_service(
        uid, _HaengenderRadar(_trip_idx, haenge_einheit=0, haenge_nr=2),
    ).check_radar_alerts_run()
    assert lauf1.hit_deadline is True and ids[0] in lauf1.skipped_ids, lauf1

    parallel_fetch._executor.shutdown(wait=True)
    parallel_fetch._reset_for_tests()
    _patch_deadline(monkeypatch, 600.0)
    radar2 = _ScriptedRadar(_trip_idx)
    _trip_service(uid, radar2).check_radar_alerts_run()

    assert radar2.first_seen[:1] == [0], (
        f"Abgebrochener Trip A muss im Folgelauf zuerst dran sein, Reihenfolge {radar2.first_seen!r}"
    )


# ===========================================================================
# Mandantentrennung: Abbruch bei Nutzer A beruehrt Nutzer B nicht
# ===========================================================================

def test_zwei_nutzer_abbruch_bei_a_beruehrt_b_nicht(monkeypatch):
    """Gleiche Trip-ID bei A und B. A bricht ab (haengender Zonenpunkt), B laeuft
    normal: A ohne Stempel/Protokoll, B gestempelt mit genau einem Alarm."""
    uid_a, uid_b = _uid("3085a"), _uid("3085b")
    ids_a = _make_trips(uid_a, ["gleich"])
    ids_b = _make_trips(uid_b, ["gleich"])
    _patch_deadline(monkeypatch, FRIST_S)

    res_a = _trip_service(
        uid_a, _HaengenderRadar(_trip_idx, haenge_einheit=0, haenge_nr=2, wet=True),
    ).check_radar_alerts_run()
    assert res_a.hit_deadline is True and res_a.alerts_sent == 0, res_a
    assert _read_state(uid_b, TRIP_STATE) == {}, "Lauf von A hat B gestempelt"
    assert not _alert_log_has_entries(uid_b), "Lauf von A hat bei B protokolliert"

    parallel_fetch._executor.shutdown(wait=True)
    parallel_fetch._reset_for_tests()
    _patch_deadline(monkeypatch, 600.0)
    mails_b: list = []
    res_b = _trip_service(uid_b, _ScriptedRadar(_trip_idx, wet=True), mails_b).check_radar_alerts_run()

    assert res_b.alerts_sent == 1 and len(mails_b) == 1, res_b
    assert ids_b[0] in _read_state(uid_b, TRIP_STATE)
    assert ids_a[0] not in _read_state(uid_a, TRIP_STATE), "A darf weiterhin keinen Stempel tragen"
    assert not _alert_log_has_entries(uid_a), _alert_log_text(uid_a)
