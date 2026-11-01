"""Deterministische Inbound-Fixture fuer P10 (Issue #2673, Epic #2644).

SPEC: docs/specs/modules/i18n_p10_inbound_2673.md Abschnitt 7.

Feste Zeit 2026-10-29T04:00Z (= 06:00+02:00, Donnerstag), ein Trip mit drei
Etappen (28.10., 29.10., 31.10. -- der 30.10. ist bewusst etappenlos, damit
MORGEN ohne Netz in "keine Etappe" endet) samt echtem Stunden-Snapshot und ein
Ortsvergleich mit drei Orten. Die Sprache steht wie im Betrieb in
``user.json`` (``language``); ``None`` = Bestandsnutzer ohne Feld.

Erzeugt wird ueber den ECHTEN Prozessor (``TripCommandProcessor.process``)
bzw. die echten Zielauswahl-Funktionen; Netzraender (Telegram, seven.io,
SMTP, Lern-Endpunkt) faengt der Recorder aus ``_befehl_e2e_fixtures``.
Kein ``Mock()``/``patch()``. Format je Fall: ``[Betreff]\\n\\nText`` -- genau
die Form, die Telegram zustellt.
"""
from __future__ import annotations

import json
import shutil
from datetime import date, datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GOLDEN_DIR = REPO / "tests" / "golden" / "inbound"
JETZT = datetime(2026, 10, 29, 4, 0, tzinfo=timezone.utc)
FEST = "2026-10-29T04:00:00+00:00"
TRIP_NAME = "Golden Trip"
VERGLEICH_NAME = "Golden Vergleich"

#: Faelle mit eigener Golden-Datei (Spec Abschnitt 7.1); alles Weitere steht
#: abschnittsweise in ``weitere.<lang>.txt`` bzw. ``kurz_weitere.en.txt``.
LANGFORM_FAELLE = (
    "hilfe_trip", "hilfe_vergleich", "kuerzel", "status", "ruhetag_bestaetigung",
    "ruhetag_bereits", "trip_beendet", "unbekannt_trip", "trip_nicht_gefunden",
    "rueckfrage_mehrdeutig",
)
KURZ_FAELLE = ("kurz_hilfe", "kurz_codes", "kurz_status", "kurz_unbekannt")


def golden_pfad(fall: str, lang: str) -> Path:
    return GOLDEN_DIR / f"{fall}.{lang}.txt"


# ----------------------------------------------------------------- Daten


def nutzer_anlegen(user_id: str, lang: str | None, *, chat_id: str = "") -> None:
    """``user.json`` frisch; ``language`` nur wenn ``lang`` gesetzt ist."""
    from app.loader import get_data_dir

    shutil.rmtree(get_data_dir(user_id), ignore_errors=True)
    ordner = get_data_dir(user_id)
    ordner.mkdir(parents=True, exist_ok=True)
    profil = {
        "id": user_id, "tier": "premium",
        "mail_to": f"{user_id}@henemm.com",
        "email_verified_at": "2026-01-01T00:00:00Z",
        "telegram_chat_id": chat_id or f"7{abs(hash(user_id)) % 10**8:08d}",
        "premium_sms_reply_to": f"+49170{abs(hash(user_id)) % 10**7:07d}",
        "premium_sms_reply_at": FEST,
        "sms_to": "+490000000000", "sms_verified_number": "+490000000000",
    }
    if lang is not None:
        profil["language"] = lang
    (ordner / "user.json").write_text(json.dumps(profil), encoding="utf-8")


def trip_anlegen(user_id: str, name: str = TRIP_NAME):
    """Trip mit drei Etappen und Stunden-Snapshot (fester Tag 29.10.2026)."""
    from app.loader import load_all_trips, save_trip
    from app.models import TripReportConfig
    from app.trip import Stage, Trip, Waypoint
    from services.weather_snapshot import WeatherSnapshotService
    from tests.tdd._befehl_e2e_fixtures import INNSBRUCK_LAT as LAT
    from tests.tdd._befehl_e2e_fixtures import INNSBRUCK_LON as LON
    from tests.tdd._befehl_e2e_fixtures import _segment_fuer_stage

    trip_id = f"{user_id}-trip"
    tage = ((date(2026, 10, 28), "Innsbruck - Stubai"),
            (date(2026, 10, 29), "Stubai - Neustift"),
            (date(2026, 10, 31), "Neustift - Elfer"))
    stages = [
        Stage(id=f"T{i}", name=n, date=d, waypoints=[
            Waypoint(id=f"G{i}a", name="Start", lat=LAT, lon=LON, elevation_m=600),
            Waypoint(id=f"G{i}b", name="Ziel", lat=LAT + 0.02, lon=LON + 0.02,
                     elevation_m=900),
        ])
        for i, (d, n) in enumerate(tage, start=1)
    ]
    save_trip(Trip(
        id=trip_id, name=name, stages=stages, official_alerts_enabled=False,
        report_config=TripReportConfig(
            trip_id=trip_id, send_email=True, send_sms=False,
            send_premium_sms=True, send_telegram=True,
            day_window_start_hour=0, day_window_end_hour=23,
        ),
    ), user_id)
    trip = next(t for t in load_all_trips(user_id) if t.id == trip_id)
    WeatherSnapshotService(user_id).save(
        trip.id, [_segment_fuer_stage(s) for s in trip.stages], JETZT.date())
    return trip


def vergleich_anlegen(user_id: str, name: str = VERGLEICH_NAME, nr: int = 1) -> dict:
    from app.loader import get_briefings_dir

    eintrag = {
        "id": f"{user_id}-cmp{nr}", "name": name, "kind": "vergleich",
        "user_id": user_id, "location_ids": ["loc-a", "loc-b", "loc-c"],
        "schedule": "daily", "previous_schedule": "",
        "created_at": "2026-09-01T08:00:00Z",
    }
    ordner = get_briefings_dir(user_id)
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / f"{eintrag['id']}.json").write_text(json.dumps(eintrag), encoding="utf-8")
    return eintrag


# ----------------------------------------------------------------- Abruf


def antwort(user_id: str, body: str, *, channel: str = "email",
            trip_name: str = TRIP_NAME, preset: dict | None = None,
            englisch: bool = False) -> str:
    """Eine Nachricht durch ``TripCommandProcessor.process``."""
    from services.trip_command_processor import InboundMessage, TripCommandProcessor

    msg = InboundMessage(
        trip_name=preset["name"] if preset else trip_name, body=body,
        sender="golden", channel=channel, received_at=JETZT, user_id=user_id,
        resolved_kind="vergleich" if preset else None,
        resolved_preset_id=preset["id"] if preset else None, englisch=englisch,
    )
    erg = TripCommandProcessor().process(msg)
    return f"[{erg.confirmation_subject}]\n\n{erg.confirmation_body}"


def _ziel(key, trips, presets, channel: str, lang: str | None) -> str:
    from services.trip_selection import resolve_command_target

    kw = {} if lang is None else {"lang": lang}
    return resolve_command_target(key, trips, presets, JETZT, channel=channel, **kw).text


def _abschnitte(faelle: dict[str, str]) -> str:
    return "".join(f"----- {k} -----\n{v}\n" for k, v in faelle.items())


def langform_texte(user_id: str, lang: str | None) -> dict[str, str]:
    """Alle Langform-Faelle (E-Mail-Kanal) des Nutzers in fester Reihenfolge.

    Lesende Faelle zuerst, Mutationen (Ruhetag, Startdatum, Stop) zuletzt."""
    from app.loader import load_all_trips

    trip = trip_anlegen(user_id)
    preset = vergleich_anlegen(user_id)
    a = lambda body, **kw: antwort(user_id, body, **kw)  # noqa: E731
    f: dict[str, str] = {}
    f["status"] = a("STATUS")
    f["hilfe_trip"] = a("HILFE", trip_name="")
    f["kuerzel"] = a("KUERZEL", trip_name="")
    f["unbekannt_trip"] = a("Hilfen")
    f["trip_nicht_gefunden"] = a("STATUS", trip_name="Gibtsnicht")
    f["hilfe_vergleich"] = a("HILFE", preset=preset)
    w: dict[str, str] = {}
    w["unbekannt_schluessel"] = a("### foo")
    w["glance"] = a("### query: glance", channel="telegram")
    w["timeline_heute"] = a("### query: timeline_heute", channel="telegram")
    w["timeline_morgen"] = a("### query: timeline_morgen", channel="telegram")
    w["gewitter_heute"] = a("GEWITTER", channel="telegram")
    w["stunden_heute"] = a("### dd_hours_today", channel="telegram")
    w["drilldown_gewitter"] = a("### dd_thunder_today", channel="telegram")
    w["metrik_temp"] = a("temp", channel="telegram")
    w["metrik_uv"] = a("uv", channel="telegram")
    w["morgen_keine_etappe"] = a("MORGEN", channel="telegram")
    w["report_typ"] = a("REPORT abends")
    w["kuerzel_vergleich"] = a("KUERZEL", preset=preset)
    w["vergleich_status"] = a("STATUS", preset=preset)
    w["vergleich_pause"] = a("PAUSE 2d", preset=preset)
    w["vergleich_weiter"] = a("WEITER", preset=preset)
    w["vergleich_weiter_nicht_pausiert"] = a("WEITER", preset=preset)
    w["pause_ohne_dauer"] = a("PAUSE")
    w["pause_ungueltig"] = a("PAUSE xx")
    w["pause_null"] = a("PAUSE 0")
    w["pause"] = a("PAUSE 2d")
    w["skip"] = a("SKIP")
    w["weiter"] = a("WEITER")
    w["spalten"] = a("### columns", trip_name="")
    f["ruhetag_bestaetigung"] = a("RUHETAG 2")
    f["ruhetag_bereits"] = a("RUHETAG")
    w["startdatum_fehlt"] = a("STARTDATUM")
    w["startdatum_ungueltig"] = a("STARTDATUM 2026-13-01")
    w["startdatum"] = a("STARTDATUM 2026-11-02")
    f["trip_beendet"] = a("STOP")
    trips = load_all_trips(user_id)
    zweiter = vergleich_anlegen(user_id, "Zweiter Vergleich", nr=2)
    f["rueckfrage_mehrdeutig"] = _ziel("pause", trips, [preset, zweiter], "telegram", lang)
    w["ziel_kein_kandidat"] = _ziel("status", [], [], "telegram", lang)
    w["ziel_kein_aktives"] = _ziel("status", [], [preset], "email", lang)
    w.update(_funktions_texte(lang))
    f["weitere"] = _abschnitte(w)
    return f


def _funktions_texte(lang: str | None) -> dict[str, str]:
    """Geteilte Bausteine, die der Mail-Befehlsblock und der Telegram-Reader
    nutzen (``command_rows``, ``unknown_command_body``)."""
    from services.trip_command_processor import command_rows, unknown_command_body

    kw = {} if lang is None else {"lang": lang}
    zeilen = lambda kind: "\n".join(  # noqa: E731
        f"{c} | {b}" for c, b in command_rows(kind, **kw))
    return {
        "command_rows_route": zeilen("route"),
        "command_rows_vergleich": zeilen("vergleich"),
        "unknown_command_body": unknown_command_body("Prefix.", **kw),
    }


def kurz_texte(user_id: str, lang: str | None = None) -> dict[str, str]:
    """Kurzform (Premium-SMS und Telegram-Kurzstil) -- fuer jede Kontosprache
    byte-gleich (PO-Vorgabe, AC-3/AC-4)."""
    from app.loader import load_all_trips

    trip_anlegen(user_id)
    preset = vergleich_anlegen(user_id)
    p = lambda body, **kw: antwort(user_id, body, channel="premium_sms", **kw)  # noqa: E731
    tg = lambda body, **kw: antwort(user_id, body, channel="telegram",  # noqa: E731
                                    englisch=True, **kw)
    f: dict[str, str] = {}
    f["kurz_hilfe"] = p("HELP", trip_name="")
    f["kurz_codes"] = p("CODES", trip_name="")
    f["kurz_status"] = p("STATUS")
    f["kurz_unbekannt"] = p("Hilfen")
    w: dict[str, str] = {}
    w["unbekannt_schluessel"] = p("### foo")
    w["morgen"] = p("TOMORROW")
    w["glance"] = p("glance")
    w["gewitter"] = p("STORMS")
    w["metrik_temp"] = p("T")
    w["metrik_uv"] = p("UV")
    w["stunden"] = p("### dd_hours_today")
    w["report_typ"] = p("REPORT abends")
    w["hilfe_vergleich"] = p("HELP", preset=preset)
    w["vergleich_status"] = p("STATUS", preset=preset)
    w["vergleich_pause"] = p("PAUSE 2d", preset=preset)
    w["vergleich_weiter"] = p("WEITER", preset=preset)
    w["pause_ungueltig"] = p("PAUSE xx")
    w["pause_null"] = p("PAUSE 0")
    w["skip"] = p("SKIP")
    w["tg_hilfe"] = tg("HELP", trip_name="")
    w["tg_status"] = tg("STATUS")
    w["tg_timeline"] = tg("### query: timeline_heute")
    w["tg_stunden"] = tg("### dd_hours_today")
    w["tg_drilldown"] = tg("### dd_thunder_today")
    w["tg_unbekannt"] = tg("Hilfen")
    w["ruhetag"] = p("RESTDAY")
    w["startdatum_fehlt"] = p("STARTDATE")
    w["stop"] = p("STOP")
    trips = load_all_trips(user_id)
    zweiter = vergleich_anlegen(user_id, "Zweiter Vergleich", nr=2)
    w["mehrdeutig"] = _ziel("pause", trips, [preset, zweiter], "premium_sms", lang)
    w["kein_kandidat"] = _ziel("status", [], [], "premium_sms", lang)
    w["kein_aktives"] = _ziel("status", [], [preset], "premium_sms", lang)
    f["kurz_weitere"] = _abschnitte(w)
    return f


# ----------------------------------------------------- echte Eingaenge


def _nutzer(user_id: str):
    from app.loader import get_data_dir
    from tests.tdd._befehl_e2e_fixtures import BefehlNutzer

    profil = json.loads((get_data_dir(user_id) / "user.json").read_text(encoding="utf-8"))
    return BefehlNutzer(
        user_id=user_id, mail_to=profil["mail_to"],
        telegram_chat_id=profil["telegram_chat_id"],
        premium_sms_reply_to=profil["premium_sms_reply_to"],
    )


def mail_text(raw: str) -> str:
    """``[Betreff]\\n\\nText`` einer aufgezeichneten Antwortmail."""
    import email
    from email.header import decode_header, make_header

    msg = email.message_from_string(raw)
    teil = next(p for p in msg.walk() if p.get_content_type() == "text/plain")
    text = teil.get_payload(decode=True).decode(teil.get_content_charset() or "utf-8")
    return f"[{make_header(decode_header(msg['Subject']))}]\n\n{text.rstrip()}"


def telegram_texte(recorder, settings, user_id: str, text: str) -> list[str]:
    """Alle sichtbaren Telegram-Inhalte auf EINE getippte Nachricht."""
    from tests.tdd._befehl_e2e_fixtures import sende_telegram_text

    vorher = len(recorder.telegram_inhalte())
    sende_telegram_text(settings, _nutzer(user_id), text)
    return [e["payload"]["text"] for e in recorder.telegram_inhalte()[vorher:]]


def email_texte(recorder, settings, user_id: str, body: str,
                trip_name: str = TRIP_NAME) -> list[str]:
    """Alle Antwortmails auf EINE Befehlsmail (echter ``_process_single``)."""
    from tests.tdd._befehl_e2e_fixtures import sende_email

    vorher = len(recorder.emails)
    sende_email(settings, _nutzer(user_id), body, trip_name=trip_name)
    return [mail_text(e["raw"]) for e in recorder.emails[vorher:]]


def reader_texte(recorder, settings, user_id: str) -> str:
    """Eigene Texte der Reader (Telegram, E-Mail) durch den echten Eingang."""
    trip_anlegen(user_id)

    def tg(text: str) -> str:
        return "\n=====\n".join(telegram_texte(recorder, settings, user_id, text))

    w = {
        "telegram_unbekannt": tg("Hilfen"),
        "telegram_unbekannt_nach_name": tg(f"{TRIP_NAME} Hilfen"),
        "telegram_laden": tg("/th"),
        "email_trip_nicht_gefunden": "\n".join(
            email_texte(recorder, settings, user_id, "STATUS", trip_name="Gibtsnicht")),
    }
    vergleich_anlegen(user_id)
    w["telegram_mehrdeutig"] = tg("PAUSE")
    return _abschnitte(w)
