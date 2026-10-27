"""Merker "Erstes Briefing erhalten" (Onboarding S2, AC-12/AC-13).

Spec: docs/specs/modules/onboarding_willkommen_checkliste.md (AC-12, AC-13)

Zwei Teile:

1. ``services.first_briefing.mark_first_briefing(user_id)`` -- schreibt
   ``data/users/<id>/first_briefing.json`` (``{"first_briefing_at": ISO}``)
   genau einmal, fail-soft, nie ``user.json``.
2. Die beiden Aufrufstellen: nur ein PLANMAESSIG zugestellter Trip- bzw.
   Ortsvergleich-Versand hakt ab; Test-Versand, "report", SMS heute/morgen
   (``angefordert=True``), manueller Ortsvergleich-Versand (``on_demand=True``)
   und fehlgeschlagener Versand nicht.

Mock-frei: echte Dateien auf der isolierten Datenwurzel (autouse-Fixture,
#1133), echter Scheduler bzw. echter ``send_one_compare_preset``, Wetter ueber
die etablierte Fixture-Naht (Trip: ``GZ_TEST_FIXTURE_DIR``, Vergleich:
``engine_naht``), Transport ueber den geteilten Aufzeichner
(``tests/helpers/transport_mitschrift.py``).

Gegen die Mutation "falsches Signal": in jeder Fixture existieren
``briefing_log.json`` bzw. der Vergleichs-Status (``letzter_versand``) bereits
VOR dem Lauf und werden vom Lauf auch in den Negativfaellen fortgeschrieben,
``first_briefing.json`` fehlt. Wer den Merker aus diesen Quellen ableitet oder
neben ``_append_briefing_log``/``save_compare_preset_status`` ohne die
Bedingung setzt, wird in den Negativfaellen rot. Die Negativfaelle sind heute
gruen; sie zaehlen nur zusammen mit der ROTEN Positivkontrolle derselben
Fixture.

Der Import von ``services.first_briefing`` steht in jeder Testfunktion, damit
die Datei sammelbar bleibt, solange das Modul fehlt.
"""
from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from app.loader import get_data_dir, load_all_trips, save_trip  # noqa: E402
from app.models import TripReportConfig  # noqa: E402
from app.trip import Stage, Trip, Waypoint  # noqa: E402
from services.trip_report_scheduler import TripReportSchedulerService  # noqa: E402
from tests.helpers.transport_mitschrift import (  # noqa: E402
    Kanalmitschrift,
    aufzeichner_installieren,
)
from tests.tdd._compare_kette_fixtures import (  # noqa: E402
    briefing_senden,
    engine_naht,
    fixture_dict,
    nutzer_anlegen,
    orte_anlegen,
    preset_ablegen,
    settings_fuer,
    transport_einrichten,
)
from utils.timezone import tz_for_coords  # noqa: E402

MERKER = "first_briefing.json"

#: Exakter Standort aus ``providers/fixture.py::_FIXTURE_LOCATIONS``.
INNSBRUCK = (47.2692, 11.4041)


def _merker_pfad(user_id: str) -> Path:
    return get_data_dir(user_id) / MERKER


def _merker_zeit(user_id: str) -> datetime:
    roh = json.loads(_merker_pfad(user_id).read_text(encoding="utf-8"))
    assert set(roh) == {"first_briefing_at"}, f"Form von {MERKER}: {roh!r}"
    zeit = datetime.fromisoformat(roh["first_briefing_at"])
    assert zeit.tzinfo is not None, f"first_briefing_at braucht eine Zeitzone: {roh!r}"
    return zeit


def _kennung(praefix: str) -> str:
    """Ohne "tdd"/"test" (Herkunftssperre, ``is_test_user_id``)."""
    return f"erstbriefing-{praefix}-{uuid.uuid4().hex[:6]}"


# ═══════════════════ AC-12: mark_first_briefing ══════════════════════════════


def test_erster_aufruf_legt_den_merker_mit_aktuellem_zeitpunkt_an():
    """AC-12.

    GIVEN ein Nutzer ohne Merker.
    WHEN  ``mark_first_briefing(uid)``.
    THEN  ``first_briefing.json`` existiert mit genau ``first_briefing_at``
          (ISO, zeitzonenbehaftet, jetzt).

    RED heute: ``services.first_briefing`` existiert nicht.
    """
    from services.first_briefing import mark_first_briefing

    uid = _kennung("einmal")
    get_data_dir(uid).mkdir(parents=True, exist_ok=True)

    vorher = datetime.now(timezone.utc)
    mark_first_briefing(uid)
    nachher = datetime.now(timezone.utc)

    zeit = _merker_zeit(uid)
    assert vorher - timedelta(seconds=1) <= zeit <= nachher + timedelta(seconds=1), (
        f"first_briefing_at {zeit.isoformat()} liegt nicht im Aufrufzeitraum"
    )


def test_zweiter_aufruf_aendert_das_datum_nicht():
    """AC-12: ein zweites Briefing aendert das Datum von A nicht."""
    from services.first_briefing import mark_first_briefing

    uid = _kennung("zweimal")
    ordner = get_data_dir(uid)
    ordner.mkdir(parents=True, exist_ok=True)
    frueher = {"first_briefing_at": "2026-09-01T06:00:00+00:00"}
    (ordner / MERKER).write_text(json.dumps(frueher), encoding="utf-8")

    mark_first_briefing(uid)

    assert json.loads((ordner / MERKER).read_text(encoding="utf-8")) == frueher


def test_merker_gilt_nur_fuer_den_aufrufenden_nutzer():
    """AC-12 (Zwei-Nutzer): A wird markiert, B bleibt ohne Merker."""
    from services.first_briefing import mark_first_briefing

    a, b = _kennung("a"), _kennung("b")
    for uid in (a, b):
        get_data_dir(uid).mkdir(parents=True, exist_ok=True)

    mark_first_briefing(a)

    assert _merker_pfad(a).exists(), "AC-12: A muss den Merker tragen"
    assert not _merker_pfad(b).exists(), "AC-12: B darf keinen Merker bekommen"
    assert not _merker_pfad("default").exists(), "AC-12: nie unter 'default'"


def test_merker_schreibt_nie_in_user_json():
    """AC-12: Python schreibt ``user.json`` nicht (kein zweiter Schreiber)."""
    from services.first_briefing import mark_first_briefing

    uid = _kennung("profil")
    ordner = get_data_dir(uid)
    ordner.mkdir(parents=True, exist_ok=True)
    profil = ordner / "user.json"
    profil.write_text(
        json.dumps({"id": uid, "mail_to": "x@henemm.com", "fremdfeld": {"k": 1}}),
        encoding="utf-8",
    )
    vorher = profil.read_bytes()

    mark_first_briefing(uid)

    assert profil.read_bytes() == vorher, "AC-12: user.json wurde veraendert"
    assert _merker_pfad(uid).exists(), "AC-12: der Merker gehoert in eine eigene Datei"


def test_schreibfehler_wird_geschluckt():
    """AC-12 (fail-soft).

    GIVEN an der Stelle des Nutzerverzeichnisses liegt eine DATEI -- jeder
          Schreibversuch scheitert (``NotADirectoryError``/``FileExistsError``).
    WHEN  ``mark_first_briefing(uid)``.
    THEN  keine Ausnahme nach aussen.
    """
    from services.first_briefing import mark_first_briefing

    uid = _kennung("kaputt")
    blockade = get_data_dir(uid)
    blockade.parent.mkdir(parents=True, exist_ok=True)
    blockade.write_text("kein Verzeichnis", encoding="utf-8")

    mark_first_briefing(uid)  # darf nicht werfen

    assert blockade.read_text(encoding="utf-8") == "kein Verzeichnis"


# ═══════════════════ AC-13: Aufrufstelle Trip ════════════════════════════════


@pytest.fixture
def mitschrift(monkeypatch) -> Kanalmitschrift:
    transport_einrichten(monkeypatch)
    return aufzeichner_installieren(monkeypatch)


def _trip_nutzer(praefix: str) -> str:
    uid = _kennung(praefix)
    ordner = get_data_dir(uid)
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / "user.json").write_text(json.dumps({
        "id": uid, "tier": "premium", "mail_to": f"{uid}@example.invalid",
        "email_verified_at": "2026-10-01T08:00:00Z",
    }))
    # Bestehender Versand-Verlauf (frueheres, angefordertes Briefing): die
    # Mutation "briefing_log.json als Signal" saehe hier schon einen Eintrag.
    (ordner / "briefing_log.json").write_text(json.dumps({"entries": [{
        "trip_id": "frueherer-trip", "kind": "morning", "channels": ["email"],
        "sent_at": "2026-10-01T06:00:00+00:00", "on_demand": True,
    }]}))
    return uid


def _trip_anlegen(user_id: str) -> Trip:
    """Drei Etappen (gestern/heute/morgen) am Fixture-Standort, nur E-Mail."""
    zone = tz_for_coords(*INNSBRUCK)
    heute = datetime.now(timezone.utc).astimezone(zone).date()
    trip_id = f"erstbriefing-{uuid.uuid4().hex[:8]}"
    stages = [
        Stage(
            id=f"T{i}", name=f"Etappe {i}", date=heute + timedelta(days=i - 1),
            waypoints=[
                Waypoint(id=f"G{i}a", name="Start",
                         lat=INNSBRUCK[0], lon=INNSBRUCK[1], elevation_m=600),
                Waypoint(id=f"G{i}b", name="Ziel",
                         lat=INNSBRUCK[0] + 0.02, lon=INNSBRUCK[1] + 0.02,
                         elevation_m=900),
            ],
        )
        for i in range(3)
    ]
    trip = Trip(
        id=trip_id, name=f"Erstes Briefing {trip_id[-4:]}", stages=stages,
        official_alerts_enabled=False,
        report_config=TripReportConfig(
            trip_id=trip_id, send_email=True, send_sms=False,
            send_premium_sms=False, send_telegram=False,
        ),
    )
    save_trip(trip, user_id)
    return next(t for t in load_all_trips(user_id) if t.id == trip_id)


def _log_eintraege(user_id: str) -> int:
    pfad = get_data_dir(user_id) / "briefing_log.json"
    return len(json.loads(pfad.read_text()).get("entries", []))


def test_planmaessiges_trip_briefing_setzt_den_merker(mitschrift):
    """AC-13 Positivkontrolle (Trip).

    GIVEN Nutzer mit Trip (nur E-Mail), bestehendem ``briefing_log.json``,
          ohne Merker.
    WHEN  der planmaessige Morgen-Versand (``on_demand=False``,
          ``angefordert=False``) zustellt.
    THEN  ``first_briefing.json`` existiert.

    RED heute: niemand schreibt den Merker.
    """
    uid = _trip_nutzer("trip-plan")
    trip = _trip_anlegen(uid)

    ausgang = TripReportSchedulerService(user_id=uid)._send_trip_report_outcome(
        trip, "morning", on_demand=False, angefordert=False,
    )

    assert ausgang == "sent", f"Vorbedingung: zugestellt, Ausgang {ausgang!r} ({mitschrift!r})"
    assert mitschrift.kanaele == ["email"], f"Vorbedingung: {mitschrift!r}"
    assert _merker_pfad(uid).exists(), "AC-13: planmaessiger Trip-Versand muss abhaken"
    _merker_zeit(uid)


def test_angefordertes_trip_briefing_setzt_keinen_merker(mitschrift):
    """AC-13 (SMS heute/morgen, "report": ``on_demand=True, angefordert=True``).

    Waechter, heute gruen. Vorbedingung: zugestellt UND ``briefing_log.json``
    fortgeschrieben -- der Log allein ist also kein Signal.
    """
    uid = _trip_nutzer("trip-angefordert")
    trip = _trip_anlegen(uid)
    vorher = _log_eintraege(uid)

    ausgang = TripReportSchedulerService(user_id=uid)._send_trip_report_outcome(
        trip, "morning", on_demand=True, angefordert=True,
    )

    assert ausgang == "sent", f"Vorbedingung: zugestellt, Ausgang {ausgang!r}"
    assert _log_eintraege(uid) == vorher + 1, "Vorbedingung: Log fortgeschrieben"
    assert not _merker_pfad(uid).exists(), "AC-13: angefordertes Briefing darf nicht abhaken"


def test_test_versand_knopf_setzt_keinen_merker(mitschrift):
    """AC-13 (Test-Versand ueber den oeffentlichen Einstieg) -- Waechter."""
    uid = _trip_nutzer("trip-testversand")
    trip = _trip_anlegen(uid)

    ausgang = TripReportSchedulerService(user_id=uid).send_test_report_outcome(trip, "morning")

    assert mitschrift.kanaele == ["email"], f"Vorbedingung: zugestellt, {ausgang!r} {mitschrift!r}"
    assert not _merker_pfad(uid).exists(), "AC-13: Test-Versand darf nicht abhaken"


def test_fehlgeschlagenes_trip_briefing_setzt_keinen_merker(mitschrift, monkeypatch):
    """AC-13 (fehlgeschlagen): der einzige Kanal scheitert am Transport.

    Waechter, heute gruen. Die Ausnahme darf propagieren (Ausnahmeweg) oder als
    ``sent=False`` enden -- in beiden Faellen kein Merker.
    """
    from output.channels.base import OutputError
    from services import notification_service as ns

    class _ScheiterndeMail:
        def __init__(self, settings) -> None:
            pass

        def send(self, *args, **kwargs):
            raise OutputError("email", "Postausgang nicht erreichbar (Pruefung)")

    monkeypatch.setattr(ns, "EmailOutput", _ScheiterndeMail)
    uid = _trip_nutzer("trip-fehler")
    trip = _trip_anlegen(uid)

    try:
        ausgang = TripReportSchedulerService(user_id=uid)._send_trip_report_outcome(
            trip, "morning", on_demand=False, angefordert=False,
        )
    except Exception:  # noqa: BLE001 -- Ausnahmeweg ist ein legitimer Fehlschlag
        ausgang = "raised"

    assert ausgang != "sent", f"Vorbedingung: Versand muss scheitern, Ausgang {ausgang!r}"
    assert not _merker_pfad(uid).exists(), "AC-13: fehlgeschlagener Versand darf nicht abhaken"


def test_konfigurierter_aber_nicht_zugestellter_trip_versand_setzt_keinen_merker(
    mitschrift, monkeypatch
):
    """AC-13 (konfiguriert, nicht zugestellt, KEINE Ausnahme) -- Waechter.

    GIVEN ein Trip, der nur Telegram verlangt, der Bot aber nicht verbunden ist
          (kein Token/Chat): der Kanal ist konfiguriert, der Versand liefert
          still nichts aus (``sent=False``, keine Ausnahme, kein
          ``no_channel_configured``).
    WHEN  der planmaessige Versand laeuft.
    THEN  kein Merker -- der Aufruf muss im Zustell-Zweig stehen, nicht davor.
    """
    monkeypatch.setenv("GZ_TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setenv("GZ_TELEGRAM_CHAT_ID", "")
    uid = _trip_nutzer("trip-unzugestellt")
    trip = _trip_anlegen(uid)
    trip.report_config.send_email = False
    trip.report_config.send_telegram = True
    save_trip(trip, uid)
    trip = next(t for t in load_all_trips(uid) if t.id == trip.id)
    assert trip.report_config.send_telegram and not trip.report_config.send_email

    ausgang = TripReportSchedulerService(user_id=uid)._send_trip_report_outcome(
        trip, "morning", on_demand=False, angefordert=False,
    )

    assert ausgang != "sent", f"Vorbedingung: nichts zugestellt, Ausgang {ausgang!r}"
    assert mitschrift.kanaele == [], f"Vorbedingung: {mitschrift!r}"
    assert not _merker_pfad(uid).exists(), "AC-13: nicht zugestellt darf nicht abhaken"


# ═══════════════════ AC-13: Aufrufstelle Ortsvergleich ═══════════════════════


@pytest.fixture
def vergleich(monkeypatch) -> Kanalmitschrift:
    transport_einrichten(monkeypatch)
    engine_naht(monkeypatch)
    return aufzeichner_installieren(monkeypatch)


def _vergleich_nutzer() -> tuple[str, str]:
    uid = nutzer_anlegen("premium")
    orte_anlegen(uid)
    preset = fixture_dict("basis")
    preset_ablegen(uid, preset)
    # Bestehender Vergleichs-Status (frueherer Versand): die Mutation
    # "letzter_versand als Signal" saehe hier schon einen Wert.
    from services.scheduler_dispatch_service import save_compare_preset_status

    save_compare_preset_status(uid, preset["id"], "Innsbruck")
    return uid, preset["id"]


def test_planmaessiger_vergleich_setzt_den_merker(vergleich):
    """AC-13 Positivkontrolle (Ortsvergleich, ``on_demand=False``).

    RED heute: niemand schreibt den Merker.
    """
    uid, preset_id = _vergleich_nutzer()

    briefing_senden(uid, preset_id, settings_fuer(uid))

    assert vergleich.kanaele, f"Vorbedingung: zugestellt ({vergleich!r})"
    assert _merker_pfad(uid).exists(), "AC-13: planmaessiger Vergleich muss abhaken"
    _merker_zeit(uid)


def test_manueller_vergleich_versand_setzt_keinen_merker(vergleich):
    """AC-13 (manueller Versand ``on_demand=True``) -- Waechter.

    Vorbedingung: zugestellt; ``save_compare_preset_status`` laeuft auch hier.
    """
    uid, preset_id = _vergleich_nutzer()

    briefing_senden(uid, preset_id, settings_fuer(uid), on_demand=True)

    assert vergleich.kanaele, f"Vorbedingung: zugestellt ({vergleich!r})"
    assert not _merker_pfad(uid).exists(), "AC-13: manueller Versand darf nicht abhaken"


def test_fehlgeschlagener_vergleich_setzt_keinen_merker(vergleich, monkeypatch):
    """AC-13 (fehlgeschlagen) -- Waechter.

    Im Vergleich ist E-Mail immer aktiv und wirft bei Transportfehler
    (``send_compare_report``); ``send_result.sent=False`` ohne Ausnahme ist im
    Briefing-Pfad nicht herstellbar. Belegt wird daher der Ausnahmeweg.
    """
    import output.channels.email as email_mod
    from output.channels.base import OutputError

    class _ScheiterndeMail:
        def __init__(self, settings) -> None:
            pass

        def send(self, *args, **kwargs):
            raise OutputError("email", "Postausgang nicht erreichbar (Pruefung)")

    monkeypatch.setattr(email_mod, "EmailOutput", _ScheiterndeMail)
    uid, preset_id = _vergleich_nutzer()

    with pytest.raises(Exception):
        briefing_senden(uid, preset_id, settings_fuer(uid))

    assert not _merker_pfad(uid).exists(), "AC-13: fehlgeschlagener Versand darf nicht abhaken"


# ═══════════════ Fix-Loop 1: sent=False OHNE Ausnahme (F002) ═════════════════


def test_nicht_zustellbares_trip_briefing_ohne_ausnahme_setzt_keinen_merker(mitschrift):
    """AC-13 (F002, Trip): planmaessiger Lauf, aber KEIN Kanal stellt zu.

    Der Versandaufruf wirft nicht, ``result.sent`` ist False (kein Kanal
    aktiv). Der Merker darf trotz ``angefordert=False`` nicht entstehen --
    die Bedingung wirkt am ``else`` der Zustell-Verzweigung, nicht davor.
    """
    uid = _trip_nutzer("trip-unzustellbar")
    trip = _trip_anlegen(uid)
    trip.report_config = TripReportConfig(
        trip_id=trip.id, send_email=False, send_sms=False,
        send_premium_sms=False, send_telegram=False,
    )

    ausgang = TripReportSchedulerService(user_id=uid)._send_trip_report_outcome(
        trip, "morning", on_demand=False, angefordert=False,
    )

    assert ausgang != "sent", f"Vorbedingung: nichts zugestellt, Ausgang {ausgang!r}"
    assert mitschrift.kanaele == [], f"Vorbedingung: nichts hinausgegangen ({mitschrift!r})"
    assert not _merker_pfad(uid).exists(), "AC-13: nicht zugestelltes Briefing darf nicht abhaken"


def test_vergleich_ohne_wirksamen_kanal_meldet_no_channels_und_setzt_keinen_merker(
    vergleich, monkeypatch,
):
    """AC-13 (F002, Ortsvergleich): planmaessig, kein wirksamer Kanal.

    Die Kanalaufloesung wird im VERBRAUCHENDEN Modul auf "keiner" gesetzt
    (vorgesehene Naht, s. Docstring von ``_effective_compare_briefing_channels``).
    Seit #2280 (AC-8) bricht ``send_one_compare_preset`` dann schon VOR
    ``send_compare_report`` mit ``SendOutcomeError('no_channels')`` ab — nichts
    geht hinaus, und der Erst-Briefing-Merker darf nicht gesetzt werden.
    """
    from services import scheduler_dispatch_service as sds
    from services.send_outcomes import SendOutcomeError

    uid, preset_id = _vergleich_nutzer()
    monkeypatch.setattr(sds, "_effective_compare_briefing_channels", lambda *a, **k: set())

    with pytest.raises(SendOutcomeError) as info:
        briefing_senden(uid, preset_id, settings_fuer(uid))
    assert info.value.code == "no_channels", info.value.code

    assert vergleich.kanaele == [], f"Vorbedingung: nichts zugestellt ({vergleich!r})"
    assert not _merker_pfad(uid).exists(), "AC-13: nicht zugestellter Vergleich darf nicht abhaken"


# ═══════════════ Fix-Loop 1: F003 -- "default" schreibt nichts ═══════════════


def test_default_kennung_schreibt_keinen_merker():
    """AC-12 (F003): ohne echte Kennung (``"default"``/leer) kein Merker."""
    from services.first_briefing import mark_first_briefing

    ordner = get_data_dir("default")
    ordner.mkdir(parents=True, exist_ok=True)
    mark_first_briefing("default")
    mark_first_briefing("")

    assert not (ordner / MERKER).exists(), "AC-12: 'default' darf keinen Merker tragen"


# ═══════ Fix-Loop 3: oeffentliche Einstiege "report" und SMS heute/morgen ═══════


def test_report_kommando_setzt_keinen_merker(mitschrift):
    """AC-13 (F010): Inbound-Kommando "report" ueber ``send_test_report``.

    Der oeffentliche Einstieg muss ``angefordert=True`` setzen; der Test
    ruft ihn selbst, nicht ``_send_trip_report_outcome``.
    """
    uid = _trip_nutzer("trip-report-kommando")
    trip = _trip_anlegen(uid)
    vorher = _log_eintraege(uid)

    gesendet = TripReportSchedulerService(user_id=uid).send_test_report(trip, "morning")

    assert gesendet is True and mitschrift.kanaele == ["email"], (
        f"Vorbedingung: zugestellt ({gesendet!r}, {mitschrift!r})"
    )
    assert _log_eintraege(uid) == vorher + 1, "Vorbedingung: Log fortgeschrieben"
    assert not _merker_pfad(uid).exists(), "AC-13: Kommando 'report' darf nicht abhaken"


def test_sms_heute_morgen_setzt_keinen_merker(mitschrift):
    """AC-13 (F010b): SMS "heute"/"morgen" ueber ``send_on_demand_report``."""
    uid = _trip_nutzer("trip-sms-heute")
    trip = _trip_anlegen(uid)
    vorher = _log_eintraege(uid)

    ergebnis = TripReportSchedulerService(user_id=uid).send_on_demand_report(trip, "morning")

    assert ergebnis.outcome == "sent" and mitschrift.kanaele == ["email"], (
        f"Vorbedingung: zugestellt ({ergebnis!r}, {mitschrift!r})"
    )
    assert _log_eintraege(uid) == vorher + 1, "Vorbedingung: Log fortgeschrieben"
    assert not _merker_pfad(uid).exists(), "AC-13: SMS heute/morgen darf nicht abhaken"
