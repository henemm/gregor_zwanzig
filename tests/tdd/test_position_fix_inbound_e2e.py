"""TDD RED -- GPS-Fix Ende-zu-Ende durch den echten Premium-SMS-Eingang
(Issue #2327, AC-10/AC-11, Eingangsteil von AC-2/AC-4/AC-9; ADR-0102).

SPEC: docs/specs/modules/feat_2327_gps_etappenfortschritt.md

Weg: ``InboundSmsReader.poll_and_process()`` -> ``_poll_journal`` ->
Go-Lernantwort (liefert ``user_id``) -> ``_verarbeite_befehl`` -- NICHT der
direkte Funktionsaufruf (Vorbild ``tests/tdd/_befehl_e2e_fixtures.py``,
``sende_premium_sms``). Gedoubelt ist ausschliesslich die Aussengrenze:
seven.io-Journalabruf (``httpx.get``), Go-Lern-Endpunkt (``httpx.post``,
antwortet mit ``user_id`` bzw. 409) und die Versandkanaele (``httpx.post``
an seven.io/Telegram, ``smtplib.SMTP``) als Zaehler -- alles ueber den
geteilten ``Recorder``. Zielfunktionen (``extract_position``,
``record_position_fix``, Positionsquelle, Befehlsverarbeitung) laufen echt.

Eingang: aufgezeichnete Journal-Eintraege
``tests/fixtures/position_fix/seven_journal_2026-10-26_*.json`` (die zwei
echten PO-Texte woertlich + abgeleitete Varianten). Die anonymisierten
Nummern werden beim Einspielen auf ``SERVICE_NUMBER`` bzw. die
Rueckadresse des Testnutzers gesetzt (``+49000SERVICE`` liesse das Gate
#2323 still verwerfen). Der Journal-Zeitstempel (Europe/Berlin ohne Zone,
belegt in ``tests/test_befehl_antwortzeit_auswertung.py``) bleibt
unveraendert; die Uhr steht auf 26.10.2026 09:00 Ortszeit, die Heute-Etappe
des Trips liegt auf diesem Tag (08:00-16:00), die Route laeuft durch die
erste echte Koordinate (46.6370, 12.7678); die zweite (46.6124, 12.8676)
liegt ~7,6 km daneben.

VERTRAG: wie ``tests/unit/test_position_fix_snapping.py`` (Kopf) --
``position_at_time(..., user_id=...)``; der Fix wird in
``_verarbeite_befehl`` NACH der Zuordnung und VOR der Befehlsantwort
aufgenommen (sonst misst ``jetzt`` nicht am Fix).

RED-GRUND: kein Fix wird gespeichert (``position_fix.json`` fehlt), eine
reine Positions-SMS wird heute als unbekannter Befehl BEANTWORTET, und
``jetzt`` misst an der Planposition.

BESTANDSSCHUTZ (heute schon gruen und so gewollt):
``test_ac2_unsinn_klammer_wird_normal_beantwortet`` (Antwort identisch zur
Antwort ohne Klammer, kein Fix) und
``test_ac9_unbekannte_nummer_schreibt_keine_datei`` (409 vom Lern-Endpunkt
-> nichts gespeichert; die positive Kontrolle im selben Test ist RED).
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from freezegun import freeze_time

from app.loader import get_data_root
from services.inbound_sms_reader import SERVICE_NUMBER
from services.trip_segments import position_at_time, resolve_current_segment
from tests.helpers.nowcast_gate_fixtures import CountingFrameSource
from tests.helpers.position_fix_fixtures import (
    ECHT_HEUTE_KOORD,
    ZONE,
    abstand_m,
    alle_fix_dateien,
    fix_datei,
    gpx_schreiben,
    heute_track_punkte,
    lade_trip,
    ortszeit,
    trip_schreiben,
)
from tests.tdd._befehl_e2e_fixtures import (
    _schreibe_user_json,
    basis_settings,
    install_transport_fakes,
    user_ids,
)

__all__ = ["user_ids"]  # pytest muss die importierte Fixture im Modul finden

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "position_fix"
_JETZT = ortszeit(9, 0)
_SNAP_TOL_M = 5.0


def _journal_eintrag(datei: str, eintrag_id: str) -> dict:
    daten = json.loads((_FIXTURES / datei).read_text(encoding="utf-8"))
    return copy.deepcopy(next(e for e in daten["inbound"] if e["id"] == eintrag_id))


_ECHT = "seven_journal_2026-10-26_echt.json"
_VARIANTEN = "seven_journal_2026-10-26_varianten.json"


class _Nutzer:
    def __init__(self, uid: str) -> None:
        self.user_id = uid
        self.reply_to = f"+49170{abs(hash(uid)) % 10_000_000:07d}"
        self.trip_id = f"trip-2327-e2e-{uid[-6:]}"
        # Rueckadresse VOR der gestellten Uhr gelernt -- sonst blockt der
        # Kanal sie als "Zeitstempel in der Zukunft" (gemessen 26.10.).
        with freeze_time(ortszeit(8, 0)):
            _schreibe_user_json(
                uid, mail_to=f"{uid}@henemm.com", telegram_chat_id="",
                premium_sms_reply_to=self.reply_to,
            )
        gpx_schreiben(uid, "heute", heute_track_punkte())
        trip_schreiben(uid, self.trip_id, name="GPS-Fix-Trip")


def _einspielen(recorder, nutzer: _Nutzer, eintrag: dict, *, registrieren: bool = True) -> None:
    if registrieren:
        recorder.registriere_premium_sms_absender(nutzer.reply_to, nutzer.user_id)
    eintrag = dict(eintrag, to=SERVICE_NUMBER, **{"from": nutzer.reply_to})
    recorder._journal.append(eintrag)


def _poll(recorder, settings) -> None:
    from services.inbound_sms_reader import InboundSmsReader

    with freeze_time(_JETZT):
        InboundSmsReader().poll_and_process(settings)
    recorder.pruefe_keine_unbekannten_aufrufe()


def _gelernt(recorder, nutzer: _Nutzer) -> None:
    aufrufe = getattr(recorder, "premium_sms_learn_aufrufe", [])
    assert any(a.get("from") == nutzer.reply_to for a in aufrufe), (
        f"Testaufbau: der Lern-Endpunkt wurde fuer {nutzer.reply_to} nie gefragt "
        f"(Gate/Dedup?) -- Aufrufe: {aufrufe}"
    )


def _position(nutzer: _Nutzer):
    trip = lade_trip(nutzer.user_id, nutzer.trip_id)
    with freeze_time(_JETZT):
        active, seg_date = resolve_current_segment(trip, _JETZT, _JETZT.astimezone(ZONE).date())
        return position_at_time(trip, active, seg_date, _JETZT, user_id=nutzer.user_id)


@pytest.fixture
def lauf(monkeypatch):
    return install_transport_fakes(monkeypatch), basis_settings()


# ══════════════════════════════════ AC-10 ═════════════════════════════════


def test_ac10_reine_positions_sms_nimmt_fix_auf_ohne_antwort(lauf, user_ids):
    recorder, settings = lauf
    nutzer = _Nutzer(user_ids())

    _einspielen(recorder, nutzer, _journal_eintrag(_VARIANTEN, "5600201"))
    _poll(recorder, settings)

    _gelernt(recorder, nutzer)
    assert recorder.premium_sms_out == [], (
        f"AC-10: auf eine reine Positions-SMS wurde eine (bezahlte) Antwort "
        f"gesendet: {recorder.premium_sms_out}"
    )
    assert recorder.telegram_inhalte() == [] and recorder.emails == []
    assert fix_datei(nutzer.user_id).exists(), "AC-10: der Fix wurde nicht aufgenommen"


# ══════════════════════════════════ AC-11 ═════════════════════════════════


def test_ac11_heute_mit_koordinaten_wird_beantwortet_und_fix_gespeichert(lauf, user_ids):
    recorder, settings = lauf
    nutzer = _Nutzer(user_ids())

    _einspielen(recorder, nutzer, _journal_eintrag(_ECHT, "5600101"))
    _poll(recorder, settings)

    _gelernt(recorder, nutzer)
    assert recorder.premium_sms_out, "AC-11: die Heute-Antwort wurde nicht gesendet"
    assert all(s["to"] == nutzer.reply_to for s in recorder.premium_sms_out)
    assert fix_datei(nutzer.user_id).exists(), "AC-11: der Fix wurde nicht gespeichert"
    assert abstand_m(_position(nutzer), ECHT_HEUTE_KOORD) <= _SNAP_TOL_M


def test_ac11_koordinaten_ausserhalb_100m_beantwortet_aber_nicht_gespeichert(lauf, user_ids):
    recorder, settings = lauf
    nutzer = _Nutzer(user_ids())

    _einspielen(recorder, nutzer, _journal_eintrag(_ECHT, "5600102"))  # so morgen, ~7,6 km daneben
    _poll(recorder, settings)

    _gelernt(recorder, nutzer)
    assert recorder.premium_sms_out, "AC-11: der Befehl mit Koordinaten daneben blieb unbeantwortet"
    assert not fix_datei(nutzer.user_id).exists(), "AC-11: Fix > 100 m neben der Route gespeichert"

    # Positive Kontrolle: eine Positions-SMS auf der Route wird aufgenommen.
    _einspielen(recorder, nutzer, _journal_eintrag(_VARIANTEN, "5600201"))
    _poll(recorder, settings)
    assert fix_datei(nutzer.user_id).exists()


# ══════════════════════════════════ AC-2 (Eingang) ════════════════════════


def test_ac2_unsinn_klammer_wird_normal_beantwortet(monkeypatch, user_ids):
    """Bestandsschutz: dieselbe Antwort wie ohne Klammer, kein Fix."""
    recorder = install_transport_fakes(monkeypatch)
    settings = basis_settings()
    mit = _Nutzer(user_ids())
    ohne = _Nutzer(user_ids())

    _einspielen(recorder, mit, _journal_eintrag(_VARIANTEN, "5600202"))
    _poll(recorder, settings)
    antwort_mit = [s["text"] for s in recorder.premium_sms_out if s["to"] == mit.reply_to]

    kontrolle = _journal_eintrag(_VARIANTEN, "5600202")
    kontrolle.update(id="5600302", text="Heute inreachlink.com/gS5ySf-2sYCWmJQksXnjeHw")
    _einspielen(recorder, ohne, kontrolle)
    _poll(recorder, settings)
    antwort_ohne = [s["text"] for s in recorder.premium_sms_out if s["to"] == ohne.reply_to]

    assert antwort_mit, "AC-2: Befehl mit Unsinn-Klammer blieb unbeantwortet"
    assert antwort_mit == antwort_ohne, "AC-2: Unsinn-Klammer veraendert die Antwort"
    assert alle_fix_dateien(get_data_root()) == []


# ══════════════════════════════════ AC-9 (Eingang) ════════════════════════


def test_ac9_unbekannte_nummer_schreibt_keine_datei(lauf, user_ids):
    """Go kennt die Nummer nicht (409) -> kein Fix, nirgends (nie
    ``default``). Positive Kontrolle: nach der Zuordnung wird gespeichert."""
    recorder, settings = lauf
    nutzer = _Nutzer(user_ids())

    _einspielen(recorder, nutzer, _journal_eintrag(_ECHT, "5600101"), registrieren=False)
    _poll(recorder, settings)

    assert recorder.premium_sms_out == []
    assert alle_fix_dateien(get_data_root()) == [], "AC-9: Fix ohne Zuordnung gespeichert"

    zugeordnet = _journal_eintrag(_ECHT, "5600101")
    zugeordnet["id"] = "5600301"
    _einspielen(recorder, nutzer, zugeordnet)
    _poll(recorder, settings)
    assert alle_fix_dateien(get_data_root()) == [fix_datei(nutzer.user_id)]


# ══════════════════════════════════ AC-4 (Befehl) ═════════════════════════


def _aufzeichnender_radar_typ(calls: list):
    """Echte ``RadarNowcastService``-Unterklasse (Vorbild
    ``test_jetzt_misst_am_aufenthaltsort.py``): schreibt die Abfrage mit und
    laesst die echte Ableitung ueber den ``frame_source``-Seam laufen."""
    from services.radar_cache import RadarNowcastCacheService
    from services.radar_service import RadarNowcastService

    class _Aufzeichnend(RadarNowcastService):
        def __init__(self, *_a, **_kw) -> None:
            super().__init__(
                frame_source=CountingFrameSource(8), cache=RadarNowcastCacheService(),
            )

        def get_nowcast(self, lat, lon, elevation_m=None, priority="user_briefing",
                        user_id=None, deadline_at=None):
            calls.append({"lat": lat, "lon": lon})
            return super().get_nowcast(lat, lon, elevation_m=elevation_m, priority=priority)

    return _Aufzeichnend


def test_ac4_jetzt_mit_koordinaten_misst_am_fix(lauf, user_ids, monkeypatch):
    """Befehlspfad: ``Jetzt`` + Koordinaten in EINER Nachricht -- der Fix wird
    vor der Antwort aufgenommen, der Nowcast laeuft am gesnappten Fix statt an
    der Planposition (~2,7 km weiter suedlich)."""
    recorder, settings = lauf
    nutzer = _Nutzer(user_ids())
    plan = position_at_time(
        *_aktiv(nutzer), _JETZT,
    )
    assert abstand_m(plan, ECHT_HEUTE_KOORD) > 1000.0, "Testaufbau: Plan muss deutlich daneben liegen"
    calls: list = []
    monkeypatch.setattr("services.radar_service.RadarNowcastService", _aufzeichnender_radar_typ(calls))

    _einspielen(recorder, nutzer, _journal_eintrag(_VARIANTEN, "5600203"))
    _poll(recorder, settings)

    _gelernt(recorder, nutzer)
    assert recorder.premium_sms_out, "Testaufbau: Jetzt-Antwort fehlt"
    assert calls, "Testaufbau: Jetzt hat keinen Nowcast abgerufen"
    assert abstand_m((calls[0]["lat"], calls[0]["lon"]), ECHT_HEUTE_KOORD) <= _SNAP_TOL_M, (
        f"AC-4: Jetzt misst an {calls[0]} statt am Fix {ECHT_HEUTE_KOORD} (Plan: {plan})"
    )


def test_ac4_strecke_mit_koordinaten_misst_ab_dem_fix(lauf, user_ids, monkeypatch):
    """Befehlspfad ``strecke`` (``points_along_remaining_route``): der erste
    Messpunkt liegt am gesnappten Fix, alle Folgepunkte noerdlich davon
    (Richtung Ziel) -- keiner mehr an der Planposition."""
    recorder, settings = lauf
    nutzer = _Nutzer(user_ids())
    plan = position_at_time(*_aktiv(nutzer), _JETZT)
    assert abstand_m(plan, ECHT_HEUTE_KOORD) > 1000.0, "Testaufbau: Plan muss deutlich daneben liegen"
    calls: list = []
    monkeypatch.setattr("services.radar_service.RadarNowcastService", _aufzeichnender_radar_typ(calls))

    _einspielen(recorder, nutzer, _journal_eintrag(_VARIANTEN, "5600204"))
    _poll(recorder, settings)

    _gelernt(recorder, nutzer)
    assert recorder.premium_sms_out, "Testaufbau: Strecke-Antwort fehlt"
    assert calls, "Testaufbau: Strecke hat keinen Nowcast abgerufen"
    assert abstand_m((calls[0]["lat"], calls[0]["lon"]), ECHT_HEUTE_KOORD) <= _SNAP_TOL_M, (
        f"AC-4: Strecke misst zuerst an {calls[0]} statt am Fix {ECHT_HEUTE_KOORD} (Plan: {plan})"
    )
    assert all(c["lat"] >= ECHT_HEUTE_KOORD[0] - 1e-6 for c in calls), (
        f"AC-4: Strecke misst hinter dem Fix: {calls}"
    )


def test_ac4_heute_briefing_starkregen_hinweis_misst_am_fix(lauf, user_ids, monkeypatch):
    """Briefingpfad: das per ``Heute`` ausgeloeste Briefing ruft fuer den
    Starkregen-Kurzfristhinweis (``trip_report_scheduler._build_starkregen_hint``,
    ``position_at_time`` zur Fenstermitte) EINEN Nowcast ab -- gemessen 26.10.
    an der Planposition (46.63125). Mit Fix muss er am Fix liegen."""
    from datetime import timedelta

    from services import radar_service as radar_service_mod

    recorder, settings = lauf
    nutzer = _Nutzer(user_ids())
    plan = position_at_time(
        *_aktiv(nutzer), _JETZT + timedelta(minutes=radar_service_mod.NOWCAST_HORIZON_MIN // 2),
    )
    assert abstand_m(plan, ECHT_HEUTE_KOORD) > 300.0, "Testaufbau: Plan muss messbar daneben liegen"
    calls: list = []
    monkeypatch.setattr("services.radar_service.RadarNowcastService", _aufzeichnender_radar_typ(calls))

    _einspielen(recorder, nutzer, _journal_eintrag(_ECHT, "5600101"))
    _poll(recorder, settings)

    _gelernt(recorder, nutzer)
    assert calls, "Testaufbau: das Heute-Briefing hat keinen Nowcast abgerufen"
    assert abstand_m((calls[0]["lat"], calls[0]["lon"]), ECHT_HEUTE_KOORD) <= _SNAP_TOL_M, (
        f"AC-4: Briefing-Hinweis misst an {calls[0]} statt am Fix {ECHT_HEUTE_KOORD} (Plan: {plan})"
    )


def _aktiv(nutzer: _Nutzer):
    trip = lade_trip(nutzer.user_id, nutzer.trip_id)
    with freeze_time(_JETZT):
        active, seg_date = resolve_current_segment(trip, _JETZT, _JETZT.astimezone(ZONE).date())
    return trip, active, seg_date
