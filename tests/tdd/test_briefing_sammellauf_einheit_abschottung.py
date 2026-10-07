"""TDD RED — #2217: Briefing-Sammellauf je Einheit abschotten.

SPEC: docs/specs/modules/fix_2217_stapellauf_abschotten.md
      (Abschnitt „BRIEFING-SAMMELLAUF", AC-10 Ortsvergleich-Variante, AC-11..AC-14)

Fehlerbild heute: eine Ausnahme in der FAELLIGKEITSPRUEFUNG einer einzelnen
Einheit (Trip bzw. Ortsvergleich-Preset) bricht den GANZEN stuendlichen
Sammellauf ab. Sie kommt nie bis `dispatch_one`, wird also auch nie in
`failed` gezaehlt — der Router antwortet mit HTTP 500, und alle uebrigen
Einheiten desselben Nutzers bekommen in diesem Lauf nichts.

Ausloeser (echte, aber fehlerhafte Daten — INNERHALB der Schleife je Einheit,
nicht schon im Loader):

* Trip, Faelligkeitspruefung (AC-11, AC-13): ein Eintrag in
  ``briefing_log.json`` fuer Trip 1 mit ``sent_at`` am Rand des
  Datumsbereichs (``0001-01-01T00:00:00+14:00``). Die Rueckwaerts-Ableitung
  ``BriefingSlotStore.is_recorded_or_claimed`` -> ``_log_traegt_versand`` ->
  ``local_dt`` wirft ``OverflowError`` — nur fuer Trip 1, weil die Ableitung
  vor dem Parsen auf ``trip_id`` filtert. Die Stelle liegt im Rumpf von
  ``_collect_due_trips`` VOR ``_skip_next_verbrauchen``.
* Ortsvergleich, Faelligkeitspruefung (AC-14): ein Preset, dessen
  ``location_ids`` einen unhashbaren Eintrag traegt. Die Zonenbestimmung in
  ``presets_due_for_hour`` (``all_locations.get(lid)``) wirft — sie liegt
  AUSSERHALB des bestehenden engen ``except (ValueError, TypeError)``, das nur
  den Datumsblock schuetzt.
* Ortsvergleich, Auto-Pause (AC-14): ein abgelaufenes Preset, dessen ``id``
  eine Zahl ist. ``save_compare_preset_pause`` -> ``VALID_ENTITY_ID_RE.match``
  wirft ``TypeError`` — ausserhalb des engen Schutzes, der dort nur den
  Datumsvergleich umschliesst. Faelligkeit und Zonenbestimmung laufen mit
  dieser Kennung fehlerfrei.

Hinweis Fehlerklasse: fuer Zonenbestimmung und Auto-Pause gibt es KEINEN
Datenweg zu einer Nicht-ValueError/TypeError-Ausnahme (``tz_for_coords``/
``ZoneInfo`` schlucken alles; ``_rmw_compare_preset`` faengt eine
Nicht-Objekt-Datei als ValueError ab und liefert still ``False`` — gemessen).
Beide Ausloeser sind TypeError, entstehen aber AUSSERHALB des bestehenden
engen ``except`` und brechen heute den ganzen Lauf ab.

Begruendete Testnaehte (Kern-Schicht, kein Mock-Theater):

1. Netz-Naht ``_send_trip_report_outcome`` (Hausmuster aus
   ``test_briefing_slot_idempotenz.py``/``test_briefing_slot_verwaister_claim.py``):
   eine ECHTE Unterklasse gibt den dokumentierten Ausgang ``"sent"`` zurueck
   und schreibt den Versandversuch mit. Sie wird per ``monkeypatch.setattr``
   am MODUL installiert, weil Router UND ``TripDispatchStrategy`` die Klasse
   je Lauf selbst instanziieren. Vermerk, Fenster, Filter, Zaehler und Router
   laufen unveraendert echt. Kein echter Versand, kein Netz.
2. AC-12 (Filterpruefung in ``_get_active_trips``): fuer diese Stelle gibt es
   KEINEN Datenweg, der heute wirft — ``tz_for_coords``/``ZoneInfo`` schlucken
   jeden Fehler, Daten und ``paused_until`` parst der Loader vor der Schleife,
   ein Vergleich zonenbehafteter Zeitpunkte laeuft nicht ueber. Deshalb
   minimale Fehler-Injektion nach dem Hausmuster ``_ScriptedRadar(raise_on=...)``:
   die Unterklasse ueberschreibt ``_get_target_date`` (erster Schritt der
   Filterpruefung je Trip) und wirft NUR fuer die Kennung des kaputten Trips;
   fuer alle anderen ruft sie die echte Implementierung. Es wird keine
   Annahme gespiegelt — gemessen wird, ob die UEBRIGEN Trips bedient werden
   und ob der Ausfall gezaehlt/geloggt wird.
3. Endpunkt ohne HTTP-Schicht: ``trigger_trip_reports`` wird als echte
   (synchrone) Router-Funktion direkt aufgerufen. Ueber ``TestClient`` liefert
   der Endpunkt unter ``--disable-socket`` IMMER HTTP 500 (die
   Ereignisschleife bekommt ihr Socketpaar nicht) — auch ohne jeden Defekt,
   gemessen. Ein Abbruch der Funktion entspricht in Produktion HTTP 500.
4. Ortsvergleich auf Strategie-Ebene (``CompareDispatchStrategy.collect_due``
   + ``pre_pass`` + ``result``), ohne ``dispatch_one``: so kann ``failed``
   ausschliesslich aus der Faelligkeits-/Auto-Pause-Pruefung stammen, und der
   Zaehlweg, den die Spec dort verortet, ist direkt bewacht.

Bewusst NICHT geprueft: der Go-Job-Status ``error`` (liegt in Go,
``triggerResponseBody``: ``failed>0`` => error). Der Python-Router bleibt laut
Spec bei der Briefing-Altsemantik ``status="partial"`` bei ``failed>0`` (#766)
— geprueft wird deshalb ``failed >= 1`` in der Antwort, nicht ``status``.

Zeit ist durchgehend PARAMETER (fester UTC-Zeitpunkt); Ortszone ist
``Atlantic/Reykjavik`` (ganzjaehrig UTC+0), Ortsstunde = UTC-Stunde.
Pfadregel #1409: Prueflinge relativ zu DIESER Datei bzw. ueber ``app.loader``.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from app.loader import (  # noqa: E402
    get_briefings_dir,
    get_data_dir,
    get_data_root,
    get_locations_dir,
)

REYKJAVIK = (64.13, -21.90)  # Atlantic/Reykjavik, ganzjaehrig UTC+0
TAG = date(2026, 8, 20)
SLOT_STUNDE = 7
JETZT = datetime(TAG.year, TAG.month, TAG.day, SLOT_STUNDE, 0, tzinfo=timezone.utc)

KAPUTT = "a-kaputt"
GESUND = "b-gesund"

#: ``sent_at`` am Rand des Datumsbereichs: parst sauber, die Umrechnung in die
#: Ortszone (``local_dt``) laeuft aber ueber (``OverflowError``).
KAPUTTES_SENT_AT = "0001-01-01T00:00:00+14:00"

#: Preset-Kennung als Zahl statt Zeichenkette (AC-14 Auto-Pause).
KAPUTTE_ZAHL_ID = 271828182

#: Transportfelder vollstaendig belegt, aber unbrauchbar — damit der
#: SMTP-Vorab-Guard des Trip-Laufs (``smtp_guard``) NICHT frueh mit (0, 0)
#: zurueckkehrt. Gesendet wird ohnehin nie (Netz-Naht oben).
TRANSPORT_ENV = {
    "GZ_ENV": "development",
    "GZ_SMTP_HOST": "smtp.invalid", "GZ_SMTP_USER": "unbrauchbar",
    "GZ_SMTP_PASS": "unbrauchbar", "GZ_MAIL_FROM": "gregor@example.invalid",
    "GZ_MAIL_TO": "globaler-rueckfall@example.invalid",
}


# ---------------------------------------------------------------------------
# Trip-Seite: Aufbau
# ---------------------------------------------------------------------------

def _profil(uid: str) -> None:
    ordner = get_data_dir(uid)
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / "user.json").write_text(json.dumps({
        "id": uid, "mail_to": f"{uid}@example.invalid",
    }), encoding="utf-8")


def _trip(uid: str, trip_id: str, *, skip_next: bool = False) -> None:
    """Echter Trip in ``briefings/`` mit Etappen gestern/heute/morgen."""
    lat, lon = REYKJAVIK
    stages = [
        {
            "id": f"{trip_id}-s{i}", "name": f"Etappe {i}",
            "date": (TAG + timedelta(days=i - 1)).isoformat(),
            "waypoints": [
                {"id": f"{trip_id}-wp{i}a", "name": "Start",
                 "lat": lat, "lon": lon, "elevation_m": 300},
                {"id": f"{trip_id}-wp{i}b", "name": "Ziel",
                 "lat": lat + 0.05, "lon": lon + 0.05, "elevation_m": 700},
            ],
        }
        for i in range(3)
    ]
    rc = {
        "trip_id": trip_id, "enabled": True,
        "morning_time": f"{SLOT_STUNDE:02d}:00:00",
        "evening_time": "18:00:00",
        "send_email": True,
    }
    if skip_next:
        rc["skip_next"] = True
    ordner = get_briefings_dir(uid)
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / f"{trip_id}.json").write_text(json.dumps({
        "id": trip_id, "name": f"Trip {trip_id}", "kind": "route",
        "stages": stages, "report_config": rc,
    }), encoding="utf-8")


def _kaputter_logeintrag(uid: str, trip_id: str) -> Path:
    """Regulaerer (nicht angeforderter) Protokoll-Eintrag mit kaputtem ``sent_at``."""
    pfad = get_data_dir(uid) / "briefing_log.json"
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps({"entries": [{
        "trip_id": trip_id, "kind": "morning", "sent_at": KAPUTTES_SENT_AT,
        "channels": ["email"],
    }]}), encoding="utf-8")
    return pfad


def _vermerke(uid: str) -> list[dict]:
    pfad = get_data_dir(uid) / "briefing_slots.json"
    if not pfad.exists():
        return []
    return json.loads(pfad.read_text(encoding="utf-8")).get("entries", [])


def _vermerk(uid: str, trip_id: str, slot: str = "morning", tag: date = TAG):
    for e in _vermerke(uid):
        if (e.get("trip_id"), e.get("slot"), e.get("local_day")) == (
            trip_id, slot, tag.isoformat()
        ):
            return e
    return None


def _trip_datei(uid: str, trip_id: str) -> dict:
    return json.loads((get_briefings_dir(uid) / f"{trip_id}.json").read_text())


def _klasse_installieren(monkeypatch, *, wirft_bei_zieltag: str | None = None):
    """Echte Unterklasse, am MODUL installiert (Router und Strategie bauen
    ihre Instanz selbst). Ersetzt die Netz-Naht; optional Fehler-Injektion
    in ``_get_target_date`` fuer GENAU eine Trip-Kennung (AC-12)."""
    from services import trip_report_scheduler as trs

    basis = trs.TripReportSchedulerService

    class _Protokollierend(basis):
        versandversuche: list = []

        def _send_trip_report_outcome(self, trip, report_type, **kwargs):
            type(self).versandversuche.append((trip.id, report_type))
            return "sent"

        def _get_target_date(self, report_type, trip, now_utc):
            if wirft_bei_zieltag is not None and trip.id == wirft_bei_zieltag:
                # Meldung bewusst OHNE Trip-ID: AC-12 prueft, dass der
                # Produktivcode die ID selbst ins Log schreibt.
                raise RuntimeError("Zieltag nicht bestimmbar (Fehler-Injektion)")
            return super()._get_target_date(report_type, trip, now_utc)

    _Protokollierend.versandversuche = []
    monkeypatch.setattr(trs, "TripReportSchedulerService", _Protokollierend)
    return _Protokollierend


class _Antwort:
    """Ergebnis eines Endpunkt-Aufrufs: Antwort-Dict ODER die Ausnahme, mit
    der der Endpunkt abbrach (in Produktion: HTTP 500 an Go)."""

    def __init__(self, body: dict | None, fehler: BaseException | None) -> None:
        self.body = body or {}
        self.fehler = fehler

    @property
    def ok(self) -> bool:
        return self.fehler is None

    def __str__(self) -> str:
        if self.fehler is not None:
            return (
                f"Endpunkt brach ab (HTTP 500): "
                f"{type(self.fehler).__name__}: {self.fehler}"
            )
        return f"Antwort {self.body!r}"


def _router_lauf(uid: str, jetzt: datetime = JETZT) -> _Antwort:
    """Die ECHTE Endpunkt-Funktion ``api.routers.scheduler.trigger_trip_reports``.

    Direkt aufgerufen statt ueber ``TestClient``: unter ``--disable-socket``
    kann die Ereignisschleife des TestClient ihr Selbst-Pipe-Socketpaar nicht
    anlegen und liefert IMMER HTTP 500 — auch ohne jeden Defekt (gemessen).
    Die Funktion selbst ist synchron und ohne HTTP-Schicht identisch.
    """
    from api.routers.scheduler import trigger_trip_reports

    try:
        return _Antwort(trigger_trip_reports(at=jetzt.isoformat(), user_id=uid), None)
    except Exception as exc:  # noqa: BLE001 — Abbruch ist der gemeldete Defekt
        return _Antwort(None, exc)


def _antwort(resp: _Antwort) -> str:
    return str(resp)


def _json_oder_leer(resp: _Antwort) -> dict:
    return resp.body


@pytest.fixture
def trip_env(monkeypatch):
    for name, wert in TRANSPORT_ENV.items():
        monkeypatch.setenv(name, wert)
    yield


# ---------------------------------------------------------------------------
# AC-11 — Faelligkeitspruefung von Trip 1 wirft, Trip 2 bekommt sein Briefing
# ---------------------------------------------------------------------------

def test_ac11_kaputte_faelligkeitspruefung_haelt_folgetrip_nicht_auf(trip_env, monkeypatch):
    """AC-11: Given zwei Trips mit faelligem Morgen-Briefing, die
    Faelligkeitspruefung des ersten wirft (kaputter Protokoll-Eintrag) / When
    der stuendliche Briefing-Lauf ueber den echten Trip-Report-Endpunkt laeuft
    / Then bekommt der zweite Trip sein Briefing (Vermerk ``sent``), die
    Antwort enthaelt ``failed >= 1``, und fuer den ersten Trip entsteht KEIN
    Vermerk (er bleibt im Nachhol-Fenster).

    RED heute: die Ausnahme verlaesst ``_collect_due_trips`` -> HTTP 500, kein
    Trip wird bedient.
    """
    uid = "abschottung-ac11"
    _profil(uid)
    _trip(uid, KAPUTT)
    _trip(uid, GESUND)
    _kaputter_logeintrag(uid, KAPUTT)
    klasse = _klasse_installieren(monkeypatch)

    resp = _router_lauf(uid)

    gesund = _vermerk(uid, GESUND)
    assert gesund is not None and gesund.get("outcome") == "sent", (
        f"AC-11: der gesunde Trip {GESUND!r} muss im selben Lauf sein Briefing "
        f"bekommen (Vermerk 'sent'), gefunden {gesund!r}; Versandversuche "
        f"{klasse.versandversuche}; Antwort {_antwort(resp)}"
    )
    assert (GESUND, "morning") in klasse.versandversuche, (
        f"AC-11: kein Versandversuch fuer {GESUND!r}: {klasse.versandversuche}"
    )
    assert resp.ok, f"AC-11: Endpunkt bricht ab: {_antwort(resp)}"
    assert _json_oder_leer(resp).get("failed", 0) >= 1, (
        f"AC-11: der Ausfall von {KAPUTT!r} muss in 'failed' zaehlen, "
        f"sonst meldet der Lauf faelschlich Erfolg: {_antwort(resp)}"
    )
    assert _vermerk(uid, KAPUTT) is None, (
        f"AC-11: fuer den kaputten Trip darf KEIN Vermerk entstehen (er muss im "
        f"Nachhol-Fenster erneut versucht werden), gefunden {_vermerk(uid, KAPUTT)!r}"
    )
    assert (KAPUTT, "morning") not in klasse.versandversuche, (
        f"AC-11: der kaputte Trip darf nicht versendet werden: {klasse.versandversuche}"
    )


# ---------------------------------------------------------------------------
# AC-12 — Filterpruefung in _get_active_trips wirft
# ---------------------------------------------------------------------------

def test_ac12_kaputte_filterpruefung_wird_gezaehlt_geloggt_und_folgetrip_bedient(
    trip_env, monkeypatch, caplog,
):
    """AC-12: Given ein Trip, dessen Filterpruefung in ``_get_active_trips``
    (Zieltag) eine Ausnahme wirft, und ein zweiter gesunder Trip / When der
    Briefing-Lauf ueber den echten Endpunkt laeuft / Then wird der zweite Trip
    bedient, die Antwort zaehlt den Ausfall in ``failed``, und im Log steht ein
    ERROR mit der Trip-ID und Stacktrace.

    Testnaht (begruendet im Modul-Docstring): Fehler-Injektion in
    ``_get_target_date`` NUR fuer die Kennung des kaputten Trips.

    RED heute: die Ausnahme verlaesst ``_get_active_trips`` -> HTTP 500.
    """
    uid = "abschottung-ac12"
    _profil(uid)
    _trip(uid, KAPUTT)
    _trip(uid, GESUND)
    klasse = _klasse_installieren(monkeypatch, wirft_bei_zieltag=KAPUTT)
    caplog.set_level(logging.ERROR)

    resp = _router_lauf(uid)

    gesund = _vermerk(uid, GESUND)
    assert gesund is not None and gesund.get("outcome") == "sent", (
        f"AC-12: der gesunde Trip {GESUND!r} muss trotz kaputter Filterpruefung "
        f"des anderen bedient werden, Vermerk {gesund!r}; Versandversuche "
        f"{klasse.versandversuche}; Antwort {_antwort(resp)}"
    )
    assert resp.ok, f"AC-12: Endpunkt bricht ab: {_antwort(resp)}"
    assert _json_oder_leer(resp).get("failed", 0) >= 1, (
        f"AC-12: der Ausfall in der Filterpruefung muss in 'failed' zaehlen: "
        f"{_antwort(resp)}"
    )
    treffer = [
        r for r in caplog.records
        if r.levelno >= logging.ERROR and KAPUTT in r.getMessage()
    ]
    assert treffer, (
        f"AC-12: kein ERROR-Eintrag mit der Trip-ID {KAPUTT!r}; ERROR-Eintraege: "
        f"{[r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR]}"
    )
    assert any(r.exc_info for r in treffer), (
        "AC-12: der ERROR-Eintrag muss den Stacktrace tragen (exc_info), "
        f"gefunden {[(r.getMessage(), bool(r.exc_info)) for r in treffer]}"
    )
    assert _vermerk(uid, KAPUTT) is None, (
        f"AC-12: kein Vermerk fuer den kaputten Trip, gefunden {_vermerk(uid, KAPUTT)!r}"
    )


# ---------------------------------------------------------------------------
# AC-13 — skip_next bleibt bei Ausnahme in der Faelligkeitspruefung unverbraucht
# ---------------------------------------------------------------------------

def test_ac13_skip_next_bleibt_bei_ausnahme_unverbraucht_und_wirkt_danach_einmal(
    trip_env, monkeypatch,
):
    """AC-13: Given ein Trip mit ``skip_next``, dessen Faelligkeitspruefung
    wirft, und ein zweiter gesunder Trip / When der Lauf stattfindet / Then
    wird der gesunde Trip bedient und der Ausfall gezaehlt, ``skip_next`` des
    kaputten Trips bleibt unverbraucht, kein Vermerk; beim naechsten
    fehlerfreien Lauf wirkt ``skip_next`` genau einmal (Slot uebersprungen),
    danach geht das Briefing wieder hinaus.

    RED heute: der ganze Lauf bricht mit HTTP 500 ab (der gesunde Trip bekommt
    nichts). Mutations-Waechter: ``_skip_next_verbrauchen`` vor die
    abgesicherte Pruefung ziehen => ``skip_next`` verbraucht => rot.
    """
    uid = "abschottung-ac13"
    _profil(uid)
    _trip(uid, KAPUTT, skip_next=True)
    _trip(uid, GESUND)
    log = _kaputter_logeintrag(uid, KAPUTT)
    klasse = _klasse_installieren(monkeypatch)

    resp = _router_lauf(uid)

    gesund = _vermerk(uid, GESUND)
    assert gesund is not None and gesund.get("outcome") == "sent", (
        f"AC-13: der gesunde Trip muss im selben Lauf bedient werden, Vermerk "
        f"{gesund!r}; Antwort {_antwort(resp)}"
    )
    assert resp.ok, f"AC-13: Endpunkt bricht ab: {_antwort(resp)}"
    assert _json_oder_leer(resp).get("failed", 0) >= 1, (
        f"AC-13: der Ausfall muss in 'failed' zaehlen: {_antwort(resp)}"
    )
    assert _trip_datei(uid, KAPUTT)["report_config"].get("skip_next") is True, (
        "AC-13: skip_next darf bei einer Ausnahme in der Faelligkeitspruefung "
        f"NICHT verbraucht werden: {_trip_datei(uid, KAPUTT)['report_config']}"
    )
    assert _vermerk(uid, KAPUTT) is None, (
        f"AC-13: kein Vermerk fuer den kaputten Trip, gefunden {_vermerk(uid, KAPUTT)!r}"
    )

    # Naechster fehlerfreier Lauf: Protokoll repariert -> skip_next wirkt einmal.
    log.write_text(json.dumps({"entries": []}), encoding="utf-8")
    klasse.versandversuche.clear()
    resp2 = _router_lauf(uid)
    assert resp2.ok, f"AC-13: Folge-Lauf: {_antwort(resp2)}"
    assert (KAPUTT, "morning") not in klasse.versandversuche, (
        "AC-13: im naechsten fehlerfreien Lauf muss skip_next das Briefing "
        f"ueberspringen: {klasse.versandversuche}"
    )
    vermerk = _vermerk(uid, KAPUTT)
    assert vermerk is not None and vermerk.get("outcome") == "skipped", (
        f"AC-13: der uebersprungene Slot muss als 'skipped' vermerkt sein: {vermerk!r}"
    )
    assert _trip_datei(uid, KAPUTT)["report_config"].get("skip_next") is False, (
        "AC-13: nach dem fehlerfreien Lauf ist skip_next verbraucht"
    )

    # Genau einmal: am Folgetag geht das Briefing wieder hinaus.
    klasse.versandversuche.clear()
    resp3 = _router_lauf(uid, JETZT + timedelta(days=1))
    assert resp3.ok, f"AC-13: Folgetag: {_antwort(resp3)}"
    assert (KAPUTT, "morning") in klasse.versandversuche, (
        "AC-13: skip_next wirkt genau EINMAL — am Folgetag muss das Briefing "
        f"wieder hinausgehen: {klasse.versandversuche}"
    )


# ---------------------------------------------------------------------------
# Ortsvergleich-Seite (AC-14, AC-10): Aufbau
# ---------------------------------------------------------------------------

def _ort(uid: str, loc_id: str) -> None:
    lat, lon = REYKJAVIK
    ordner = get_locations_dir(uid)
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / f"{loc_id}.json").write_text(json.dumps({
        "id": loc_id, "name": f"Ort {loc_id}", "lat": lat, "lon": lon,
        "elevation_m": 100,
    }), encoding="utf-8")


def _preset(uid: str, datei_id: str, **felder) -> Path:
    preset = {
        "id": datei_id, "name": f"Vergleich {datei_id}", "kind": "vergleich",
        "location_ids": ["ort-1"], "schedule": "daily", "profil": "ALLGEMEIN",
        "empfaenger": [f"{uid}@example.invalid"],
        "created_at": "2026-07-01T00:00:00Z",
        "morning_enabled": True, "morning_time": f"{SLOT_STUNDE:02d}:00:00",
        "evening_enabled": False, "evening_time": "18:00:00",
    }
    preset.update(felder)
    ordner = get_briefings_dir(uid)
    ordner.mkdir(parents=True, exist_ok=True)
    pfad = ordner / f"{datei_id}.json"
    pfad.write_text(json.dumps(preset), encoding="utf-8")
    return pfad


def _strategie(uid: str):
    from app.config import Settings
    from services.dispatch_orchestrator import CompareDispatchStrategy

    return CompareDispatchStrategy(Settings(), uid, str(get_data_root()))


def _collect_und_pre_pass(strategie, jetzt: datetime = JETZT) -> list:
    """``collect_due`` + ``pre_pass`` wie in ``run_briefing_dispatch`` — ohne
    ``dispatch_one``, damit ``failed`` ausschliesslich aus der Faelligkeits-/
    Auto-Pause-Pruefung stammen kann. Eine Ausnahme ist hier der gemeldete
    Defekt (ganzer Lauf bricht ab) und wird als Befund gemeldet."""
    try:
        due = strategie.collect_due(jetzt)
        strategie.pre_pass(jetzt, due)
    except Exception as exc:  # noqa: BLE001 — genau das ist der Befund
        pytest.fail(
            "Faelligkeits-/Auto-Pause-Pruefung bricht den ganzen Lauf ab: "
            f"{type(exc).__name__}: {exc}"
        )
    return due


# ---------------------------------------------------------------------------
# AC-14 — Ortsvergleich: Faelligkeitspruefung (Zonenbestimmung) wirft
# ---------------------------------------------------------------------------

def test_ac14_kaputte_zonenbestimmung_haelt_folgepreset_nicht_auf(caplog):
    """AC-14: Given zwei Presets, die Zonenbestimmung des ersten wirft
    (unhashbarer ``location_ids``-Eintrag, ausserhalb des engen
    ValueError/TypeError-Schutzes des Datumsblocks) / When der stuendliche
    Lauf faellig sammelt / Then wird das zweite Preset weiter faellig
    gemeldet, ``failed >= 1``, und das erste bleibt unangetastet (kein Vermerk).

    RED heute: ``presets_due_for_hour`` wirft fuer Preset 1 -> ganzer Lauf weg.
    """
    uid = "abschottung-ac14-faellig"
    _ort(uid, "ort-1")
    kaputt = _preset(uid, KAPUTT, location_ids=[["ort-1"]])
    _preset(uid, GESUND)
    vorher = kaputt.read_bytes()
    caplog.set_level(logging.ERROR)

    strategie = _strategie(uid)
    due = _collect_und_pre_pass(strategie)

    faellig = [p.get("id") for p, _, _ in due]
    assert faellig == [GESUND], (
        f"AC-14: nur das gesunde Preset {GESUND!r} ist faellig, gemeldet {faellig}"
    )
    assert strategie.result()[1] >= 1, (
        f"AC-14: der Ausfall von {KAPUTT!r} muss in 'failed' zaehlen, "
        f"result={strategie.result()}"
    )
    assert kaputt.read_bytes() == vorher, (
        "AC-14: fuer das kaputte Preset darf nichts geschrieben werden"
    )
    assert any(
        r.levelno >= logging.ERROR and KAPUTT in r.getMessage() and r.exc_info
        for r in caplog.records
    ), (
        f"AC-14/AC-6: ERROR mit Preset-ID {KAPUTT!r} und Stacktrace fehlt: "
        f"{[r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR]}"
    )


# ---------------------------------------------------------------------------
# AC-14 — Ortsvergleich: Auto-Pause des ersten Presets wirft
# ---------------------------------------------------------------------------

def test_ac14_kaputte_auto_pause_haelt_folgepreset_nicht_auf(caplog):
    """AC-14: Given zwei abgelaufene Presets, die Auto-Pause des ersten wirft
    in ``save_compare_preset_pause`` (seine ``id`` ist eine Zahl statt einer
    Zeichenkette -> die Kennungs-Pruefung ``VALID_ENTITY_ID_RE.match`` wirft;
    Zonenbestimmung und Faelligkeit laufen mit dieser Kennung fehlerfrei) /
    When der stuendliche Lauf laeuft / Then wird das zweite Preset trotzdem
    auto-pausiert, ``failed >= 1``, das erste bleibt unangetastet, und der
    Fehler steht mit Preset-ID und Stacktrace im Log.

    RED heute: ``_auto_pause_expired_presets`` wirft fuer Preset 1 (der enge
    ``except (ValueError, TypeError)`` umschliesst dort nur den
    Datumsvergleich, nicht ``save_compare_preset_pause``) -> Preset 2 bleibt
    aktiv.
    """
    uid = "abschottung-ac14-pause"
    _ort(uid, "ort-1")
    abgelaufen = (TAG - timedelta(days=3)).isoformat()
    kaputt = _preset(uid, KAPUTT, id=KAPUTTE_ZAHL_ID, end_date=abgelaufen)
    gesund = _preset(uid, GESUND, end_date=abgelaufen)
    vorher_kaputt = kaputt.read_bytes()
    caplog.set_level(logging.ERROR)

    strategie = _strategie(uid)
    _collect_und_pre_pass(strategie)

    daten = json.loads(gesund.read_text(encoding="utf-8"))
    assert daten.get("paused_at") and daten.get("schedule") == "manual", (
        f"AC-14: das gesunde abgelaufene Preset muss auto-pausiert sein: "
        f"paused_at={daten.get('paused_at')!r}, schedule={daten.get('schedule')!r}"
    )
    assert strategie.result()[1] >= 1, (
        f"AC-14: der Auto-Pause-Ausfall muss in 'failed' zaehlen, "
        f"result={strategie.result()}"
    )
    assert kaputt.read_bytes() == vorher_kaputt, (
        "AC-14: fuer das kaputte Preset darf nichts geschrieben werden"
    )
    assert any(
        r.levelno >= logging.ERROR and str(KAPUTTE_ZAHL_ID) in r.getMessage()
        and r.exc_info
        for r in caplog.records
    ), (
        f"AC-14/AC-6: ERROR mit Preset-ID {KAPUTTE_ZAHL_ID} und Stacktrace fehlt: "
        f"{[r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR]}"
    )


# ---------------------------------------------------------------------------
# AC-14 — Fehler-Injektion mit NICHT-ValueError/TypeError (breiter Schutz)
# ---------------------------------------------------------------------------
#
# Warum zusaetzlich zu den Datentests oben: beide Datenwege enden in einem
# TypeError. Eine Implementierung, die nur den bestehenden engen
# ``except (ValueError, TypeError)`` ueber den Schleifenrumpf zieht, machte die
# Datentests gruen, liesse aber jede andere Ausnahmeklasse den Lauf weiter
# abreissen. Einen Datenweg zu einer anderen Klasse gibt es an diesen Stellen
# nicht (gemessen, s. Modul-Docstring). Deshalb minimale Fehler-Injektion nach
# dem Hausmuster ``_ScriptedRadar(raise_on=...)``: die echte Funktion wird
# umhuellt, wirft ``RuntimeError`` NUR fuer Preset 1 und delegiert sonst an
# das Original. Injektionsmeldungen tragen bewusst KEINE Preset-ID.


def test_ac14_zonenbestimmung_wirft_andere_ausnahmeklasse_folgepreset_bleibt_faellig(
    monkeypatch, caplog,
):
    """AC-14: Given zwei Presets, die Zonenbestimmung des ersten wirft eine
    ``RuntimeError`` (keine ValueError/TypeError) / When der Lauf faellig
    sammelt / Then ist das zweite Preset faellig, ``failed >= 1``, ERROR mit
    Preset-ID und Stacktrace.

    RED heute: ``presets_due_for_hour`` laesst die Ausnahme durch.
    """
    from services import compare_slot_scheduler as css

    original = css.first_resolvable_tz

    def _zone(locations, context_label=""):
        if context_label == KAPUTT:
            raise RuntimeError("Zone nicht bestimmbar (Fehler-Injektion)")
        return original(locations, context_label=context_label)

    monkeypatch.setattr(css, "first_resolvable_tz", _zone)
    uid = "abschottung-ac14-zone-injektion"
    _ort(uid, "ort-1")
    kaputt = _preset(uid, KAPUTT)
    _preset(uid, GESUND)
    vorher = kaputt.read_bytes()
    caplog.set_level(logging.ERROR)

    strategie = _strategie(uid)
    due = _collect_und_pre_pass(strategie)

    assert [p.get("id") for p, _, _ in due] == [GESUND], (
        f"AC-14: nur {GESUND!r} ist faellig, gemeldet {[p.get('id') for p, _, _ in due]}"
    )
    assert strategie.result()[1] >= 1, (
        f"AC-14: Ausfall in 'failed' zaehlen, result={strategie.result()}"
    )
    assert kaputt.read_bytes() == vorher, "AC-14: kaputtes Preset unangetastet"
    assert any(
        r.levelno >= logging.ERROR and KAPUTT in r.getMessage() and r.exc_info
        for r in caplog.records
    ), (
        f"AC-14/AC-6: ERROR mit Preset-ID {KAPUTT!r} und Stacktrace fehlt: "
        f"{[r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR]}"
    )


def test_ac14_pause_schreiben_wirft_andere_ausnahmeklasse_folgepreset_wird_pausiert(
    monkeypatch, caplog,
):
    """AC-14: Given zwei abgelaufene Presets, ``save_compare_preset_pause``
    wirft fuer das erste eine ``RuntimeError`` / When der Lauf laeuft / Then
    wird das zweite trotzdem auto-pausiert, ``failed >= 1``, ERROR mit
    Preset-ID und Stacktrace.

    RED heute: ``_auto_pause_expired_presets`` laesst die Ausnahme durch.
    """
    from services import scheduler_dispatch_service as sds

    original = sds.save_compare_preset_pause

    def _pause(user_id, preset_id, *args, **kwargs):
        if preset_id == KAPUTT:
            raise RuntimeError("Pause nicht schreibbar (Fehler-Injektion)")
        return original(user_id, preset_id, *args, **kwargs)

    monkeypatch.setattr(sds, "save_compare_preset_pause", _pause)
    uid = "abschottung-ac14-pause-injektion"
    _ort(uid, "ort-1")
    abgelaufen = (TAG - timedelta(days=3)).isoformat()
    kaputt = _preset(uid, KAPUTT, end_date=abgelaufen)
    gesund = _preset(uid, GESUND, end_date=abgelaufen)
    vorher = kaputt.read_bytes()
    caplog.set_level(logging.ERROR)

    strategie = _strategie(uid)
    _collect_und_pre_pass(strategie)

    daten = json.loads(gesund.read_text(encoding="utf-8"))
    assert daten.get("paused_at") and daten.get("schedule") == "manual", (
        f"AC-14: das gesunde abgelaufene Preset muss auto-pausiert sein: "
        f"paused_at={daten.get('paused_at')!r}, schedule={daten.get('schedule')!r}"
    )
    assert strategie.result()[1] >= 1, (
        f"AC-14: Ausfall in 'failed' zaehlen, result={strategie.result()}"
    )
    assert kaputt.read_bytes() == vorher, "AC-14: kaputtes Preset unangetastet"
    assert any(
        r.levelno >= logging.ERROR and KAPUTT in r.getMessage() and r.exc_info
        for r in caplog.records
    ), (
        f"AC-14/AC-6: ERROR mit Preset-ID {KAPUTT!r} und Stacktrace fehlt: "
        f"{[r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR]}"
    )


# ---------------------------------------------------------------------------
# AC-10 (Ortsvergleich-Briefing) — zwei Nutzer, Fehler nur Nutzer A zugeordnet
# ---------------------------------------------------------------------------

def test_ac10_zwei_nutzer_kaputtes_preset_bei_a_nutzer_b_voll_bedient(caplog):
    """AC-10: Given Nutzer A mit kaputtem Preset (Zonenbestimmung wirft) und
    gesundem Preset, Nutzer B mit gesundem Preset / When fuer beide der
    Ortsvergleich-Briefing-Lauf sammelt / Then ist bei A das gesunde Preset
    weiter faellig und ``failed >= 1``, B ist voll bedient mit ``failed == 0``,
    der ERROR traegt nur A's Preset-ID, und es entsteht kein ``default``-Nutzer.

    RED heute: der Lauf von Nutzer A bricht vollstaendig ab.
    """
    a, b = "abschottung-nutzer-a", "abschottung-nutzer-b"
    for uid in (a, b):
        _ort(uid, "ort-1")
    _preset(a, KAPUTT, location_ids=[["ort-1"]])
    _preset(a, GESUND)
    _preset(b, "c-nutzer-b")
    caplog.set_level(logging.ERROR)

    strategie_a = _strategie(a)
    due_a = _collect_und_pre_pass(strategie_a)
    strategie_b = _strategie(b)
    due_b = _collect_und_pre_pass(strategie_b)

    assert [p.get("id") for p, _, _ in due_a] == [GESUND], (
        f"AC-10: bei Nutzer A bleibt das gesunde Preset faellig: "
        f"{[p.get('id') for p, _, _ in due_a]}"
    )
    assert strategie_a.result()[1] >= 1, (
        f"AC-10: der Ausfall gehoert Nutzer A: result A={strategie_a.result()}"
    )
    assert [p.get("id") for p, _, _ in due_b] == ["c-nutzer-b"], (
        f"AC-10: Nutzer B voll bedient: {[p.get('id') for p, _, _ in due_b]}"
    )
    assert strategie_b.result()[1] == 0, (
        f"AC-10: Nutzer B hat keinen Ausfall: result B={strategie_b.result()}"
    )
    fehler = [r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR]
    assert any(KAPUTT in m for m in fehler), (
        f"AC-10: ERROR mit A's Preset-ID {KAPUTT!r} fehlt: {fehler}"
    )
    assert not any("c-nutzer-b" in m for m in fehler), (
        f"AC-10: B's Preset darf in keinem ERROR auftauchen: {fehler}"
    )
    assert not (Path(get_data_root()) / "users" / "default").exists(), (
        "AC-10: kein Rueckfall auf den Nutzer 'default'"
    )
