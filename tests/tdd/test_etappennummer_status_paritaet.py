"""#2441 -- STATUS und Verschiebe-Bestaetigungen nennen dieselbe Etappennummer
wie Briefing/`heute`.

SPEC: docs/specs/modules/fix_2441_etappennummer_status.md
Epic #2506, Refs #2417 AC-27.

Alle Befehle laufen durch den ECHTEN Kanal-Eingang (``_befehl_e2e_fixtures``),
Zusicherung ausschliesslich auf den am Netzrand aufgezeichneten Antworten
(``Recorder``) bzw. auf dem Plattenzustand. Kein Mock.

AC-5 (Regression) deckt die bestehende Suite (#760/#762/Alarm-S{N}/Vorschau);
AC-10 (Mutations-Gegenprobe) ist Aufgabe des Adversary-Schritts.
"""
from __future__ import annotations

import dataclasses
import re
import uuid
from datetime import timedelta

import pytest

from app.loader import load_all_trips, save_trip
from app.trip import Stage, Trip, Waypoint

from app.models import TripReportConfig

from tests.tdd._befehl_e2e_fixtures import (
    INNSBRUCK_LAT,
    INNSBRUCK_LON,
    BefehlNutzer,
    _ortstag_jetzt,
    _schreibe_user_json,
    basis_settings,
    install_transport_fakes,
    sende_email,
    sende_premium_sms,
    sende_telegram_text,
    user_ids,
)
from tests.tdd._gsm7_charset import _first_non_gsm7_char

__all__ = ["user_ids"]  # pytest muss die importierte Fixture im Modul finden

_ETAPPE_ZEILE = re.compile(r"(?:Etappe|Stage) (\d+)(?:: ?(.*))?$")


# ---------------------------------------------------------------------------
# Aufbau: Trip mit frei benannten Etappen, gezaehlt nach Datum
# ---------------------------------------------------------------------------

def _nutzer(new_user_id) -> BefehlNutzer:
    user_id = new_user_id()
    chat_id = f"chat-{user_id}"
    mail_to = f"{user_id}@henemm.com"
    reply_to = f"+49170{abs(hash(user_id)) % 10_000_000:07d}"
    _schreibe_user_json(
        user_id, mail_to=mail_to, telegram_chat_id=chat_id,
        premium_sms_reply_to=reply_to,
    )
    return BefehlNutzer(
        user_id=user_id, mail_to=mail_to, telegram_chat_id=chat_id,
        premium_sms_reply_to=reply_to,
    )


def _trip_mit_etappen(nutzer: BefehlNutzer, eintraege: list[tuple[int, str]],
                      *, name: str = "Etappennummer-Trip") -> Trip:
    """``eintraege`` = (Tagesversatz zu heute in Ortszeit, Name) in LISTEN-
    Reihenfolge -- die Zaehlung erfolgt nach Datum, nicht nach Liste (AC-9)."""
    heute = _ortstag_jetzt()
    trip_id = f"gz2441-{uuid.uuid4().hex[:8]}"
    stages = [
        Stage(
            id=f"S{i}", name=stage_name, date=heute + timedelta(days=versatz),
            waypoints=[
                Waypoint(id=f"W{i}a", name="Start", lat=INNSBRUCK_LAT,
                         lon=INNSBRUCK_LON, elevation_m=600),
                Waypoint(id=f"W{i}b", name="Ziel", lat=INNSBRUCK_LAT + 0.02,
                         lon=INNSBRUCK_LON + 0.02, elevation_m=900),
            ],
        )
        for i, (versatz, stage_name) in enumerate(eintraege)
    ]
    trip = Trip(
        id=trip_id, name=name, stages=stages, official_alerts_enabled=False,
        report_config=TripReportConfig(
            trip_id=trip_id, send_email=True, send_sms=True,
            send_premium_sms=True, send_telegram=True,
            day_window_start_hour=0, day_window_end_hour=23,
        ),
    )
    save_trip(trip, nutzer.user_id)
    nutzer.trip = next(t for t in load_all_trips(nutzer.user_id) if t.id == trip_id)
    return nutzer.trip


def _vier_etappen(vierter_name: str) -> list[tuple[int, str]]:
    """Drei vergangene Etappen, die vierte ist HEUTE (sichtbar in status/heute)."""
    return [(-3, "Anreise"), (-2, "Aufstieg"), (-1, "Grat"), (0, vierter_name)]


def _erwartete_nummer(trip: Trip, stage: Stage) -> int:
    """Aus der Trip-Position abgeleitet (Spec #760), kein Literal im Aufbau."""
    return sorted(trip.stages, key=lambda s: s.date).index(stage) + 1


# ---------------------------------------------------------------------------
# Antworten lesen
# ---------------------------------------------------------------------------

def _status_zeilen(text: str) -> list[tuple[int, str]]:
    """(Nummer, Rest) je Etappenzeile der Status-Antwort. Eine Zeile ohne
    ``Etappe N`` am Zeilenende-Muster zaehlt NICHT (Rohname -> kein Treffer)."""
    ergebnis = []
    for zeile in text.splitlines():
        m = re.search(r"\d{2}\.\d{2}\.\d{4} [–-] (.+)$", zeile)
        if not m:
            continue
        em = _ETAPPE_ZEILE.match(m.group(1).strip())
        if em:
            ergebnis.append((int(em.group(1)), (em.group(2) or "").strip()))
    return ergebnis


def _telegram_text(recorder, nutzer) -> str:
    inhalte = recorder.telegram_inhalte(nutzer.telegram_chat_id)
    assert inhalte, f"Kein Telegram-Inhalt gesendet: {recorder.telegram!r}"
    return "\n".join(e["payload"].get("text", "") for e in inhalte)


def _status_telegram(settings, recorder, nutzer) -> str:
    sende_telegram_text(settings, nutzer, "status")
    return _telegram_text(recorder, nutzer)


def _mail_text(gesendet: dict) -> str:
    import email as email_lib

    msg = email_lib.message_from_string(gesendet["raw"])
    teile = []
    for teil in (msg.walk() if msg.is_multipart() else [msg]):
        if teil.get_content_maintype() == "text":
            payload = teil.get_payload(decode=True)
            if payload:
                teile.append(payload.decode(teil.get_content_charset() or "utf-8",
                                            errors="replace"))
    return "\n".join(teile)


@pytest.fixture
def aufbau(monkeypatch):
    recorder = install_transport_fakes(monkeypatch)
    return recorder, basis_settings()


# ---------------------------------------------------------------------------
# AC-1 -- status und heute nennen dieselbe Zahl
# ---------------------------------------------------------------------------

def test_status_und_heute_nennen_dieselbe_etappennummer(aufbau, user_ids):
    recorder, settings = aufbau
    nutzer = _nutzer(user_ids)
    trip = _trip_mit_etappen(nutzer, _vier_etappen("02: Obstansersee-Hütte nach Porzehütte"))
    erwartet = _erwartete_nummer(trip, trip.stages[3])

    status = _status_zeilen(_status_telegram(settings, recorder, nutzer))
    assert status, "status listet keine 'Etappe N'-Zeile (Rohname statt gezaehlter Nummer)"
    assert status[0][0] == erwartet

    sende_premium_sms(settings, recorder, nutzer, "heute")
    heute = " ".join(e["text"] for e in recorder.premium_sms_out
                     if e["to"] == nutzer.premium_sms_reply_to)
    m = re.search(r"\bE(\d+)\b", heute)
    assert m, f"heute nennt keine 'E<N>'-Kennung: {heute!r}"
    assert int(m.group(1)) == erwartet == status[0][0]


# ---------------------------------------------------------------------------
# AC-2 -- vergebenes Zahlenpraefix wird ersetzt, nicht addiert
# ---------------------------------------------------------------------------

def test_zahlenpraefix_wird_ersetzt_nicht_addiert(aufbau, user_ids):
    recorder, settings = aufbau
    nutzer = _nutzer(user_ids)
    _trip_mit_etappen(nutzer, _vier_etappen("02: X") + [(1, "02 – X"), (2, "2 - X")])

    zeilen = _status_zeilen(_status_telegram(settings, recorder, nutzer))
    assert zeilen == [(4, "X"), (5, "X"), (6, "X")], zeilen


# ---------------------------------------------------------------------------
# AC-3 -- Randfaelle: kein Praefix bleibt erhalten, leerer Rest ohne Doppelpunkt
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name,erwartet_rest", [
    ("2 Seen Runde", "2 Seen Runde"),
    ("1.5 km Runde", "1.5 km Runde"),
    ("1. Pass", "1. Pass"),
    ("2. X", "2. X"),
    ("03:", ""),
    ("02:X", "02:X"),
    ("12:30 Start", "12:30 Start"),
    ("100: X", "100: X"),
])
def test_praefix_randfaelle(aufbau, user_ids, name, erwartet_rest):
    recorder, settings = aufbau
    nutzer = _nutzer(user_ids)
    trip = _trip_mit_etappen(nutzer, _vier_etappen(name))

    zeilen = _status_zeilen(_status_telegram(settings, recorder, nutzer))
    assert zeilen == [(_erwartete_nummer(trip, trip.stages[3]), erwartet_rest)], zeilen


# ---------------------------------------------------------------------------
# AC-4 -- Verschiebe-Bestaetigungen (ruhetag + startdatum) nennen die Nummer
# ---------------------------------------------------------------------------

def _bestaetigung_zeilen(text: str) -> list[tuple[int, str]]:
    ergebnis = []
    for zeile in text.splitlines():
        m = re.match(r"\s*Etappe (\d+)(?:: ?(.*?))?(?::| ->| –| -)? ?\d{2}\.\d{2}\.\d{4}", zeile)
        if m:
            ergebnis.append((int(m.group(1)), (m.group(2) or "").strip()))
    return ergebnis


def test_ruhetag_bestaetigung_nennt_gezaehlte_nummer(aufbau, user_ids):
    recorder, settings = aufbau
    nutzer = _nutzer(user_ids)
    trip = _trip_mit_etappen(nutzer, _vier_etappen("02: Obstansersee") + [(1, "03 – Porzehuette")])

    sende_telegram_text(settings, nutzer, "ruhetag")
    text = _telegram_text(recorder, nutzer)
    zeilen = _bestaetigung_zeilen(text)
    assert zeilen == [(5, "Porzehuette")], f"Ruhetag-Bestaetigung ohne gezaehlte Nummer: {text!r}"
    assert "03" not in text.replace("03.", "").split("Verschobene")[-1].split("->")[0]


def test_startdatum_bestaetigung_nennt_gleiche_nummern_wie_status(aufbau, user_ids):
    recorder, settings = aufbau
    nutzer = _nutzer(user_ids)
    eintraege = [(1, "01: Anreise"), (2, "02 – Aufstieg"), (3, "03: Gipfel")]
    trip = _trip_mit_etappen(nutzer, eintraege)
    neuer_start = min(s.date for s in trip.stages) + timedelta(days=2)

    sende_email(settings, nutzer, f"### startdatum: {neuer_start:%Y-%m-%d}")
    text = _mail_text(recorder.emails[-1])
    zeilen = _bestaetigung_zeilen(text)
    assert zeilen == [(1, "Anreise"), (2, "Aufstieg"), (3, "Gipfel")], (
        f"Startdatum-Bestaetigung ohne gezaehlte Nummern: {text!r}"
    )


def test_startdatum_auf_telegram_kurzform_nennt_stage_n_mit_gezaehlter_nummer(aufbau, user_ids):
    """Premium-SMS kennt kein ``startdatum`` (Befehlsliste ohne das Wort);
    englisch erreichbar ist es ueber Telegram mit ``telegram_style=kurzform``
    (#2417 AC-5): je Etappe "Stage N: Rest", N aus der Trip-Position."""
    recorder, settings = aufbau
    nutzer = _nutzer(user_ids)
    eintraege = [(1, "01: Anreise"), (2, "02 – Aufstieg"), (3, "03: Gipfel")]
    trip = _trip_mit_etappen(nutzer, eintraege)
    rc = dataclasses.replace(trip.report_config, telegram_style="kurzform")
    save_trip(dataclasses.replace(trip, report_config=rc), nutzer.user_id)
    trip = nutzer.trip = next(t for t in load_all_trips(nutzer.user_id) if t.id == trip.id)
    assert trip.report_config.telegram_style == "kurzform"
    neuer_start = min(s.date for s in trip.stages) + timedelta(days=2)
    erwartet = [
        (_erwartete_nummer(trip, s), rest)
        for s, rest in zip(trip.stages, ("Anreise", "Aufstieg", "Gipfel"))
    ]

    sende_telegram_text(settings, nutzer, f"startdatum {neuer_start:%Y-%m-%d}")
    text = _telegram_text(recorder, nutzer)
    assert not re.search(r"Etappe \d", text), text
    zeilen = [
        (int(m.group(1)), m.group(2).strip())
        for m in re.finditer(r"Stage (\d+): ?(\w+)", text)
    ]
    assert zeilen == erwartet, text


# ---------------------------------------------------------------------------
# AC-6 -- Kurzform-Kanal: GSM-7, ASCII-Strich; Mail: Strich bleibt
# ---------------------------------------------------------------------------

def test_status_auf_premium_sms_ist_gsm7_und_traegt_gezaehlte_nummer(aufbau, user_ids):
    recorder, settings = aufbau
    nutzer = _nutzer(user_ids)
    trip = _trip_mit_etappen(nutzer, _vier_etappen("02: Obstansersee-Hütte"))

    sende_premium_sms(settings, recorder, nutzer, "status")
    antworten = [e["text"] for e in recorder.premium_sms_out
                 if e["to"] == nutzer.premium_sms_reply_to]
    assert antworten, "Keine Premium-SMS-Antwort auf status"
    text = antworten[-1]
    # Premium-SMS ist immer englisch (#2417 AC-4): "Stage N".
    assert f"Stage {_erwartete_nummer(trip, trip.stages[3])}" in text, text
    assert "02:" not in text, text
    assert _first_non_gsm7_char(text.replace("ü", "u")) is None, text
    assert "–" not in text, text


# ---------------------------------------------------------------------------
# AC-7 -- alle vier Kanaele nennen dieselbe Zahl und denselben Rest
# ---------------------------------------------------------------------------

def test_status_gleiche_nummer_auf_allen_vier_kanaelen(aufbau, user_ids):
    recorder, settings = aufbau
    nutzer = _nutzer(user_ids)
    trip = _trip_mit_etappen(nutzer, _vier_etappen("02: Obstansersee"))
    erwartet = [(_erwartete_nummer(trip, trip.stages[3]), "Obstansersee")]

    telegram = _status_zeilen(_status_telegram(settings, recorder, nutzer))

    sende_email(settings, nutzer, "status")
    mail = _status_zeilen(_mail_text(recorder.emails[-1]))

    sende_premium_sms(settings, recorder, nutzer, "status")
    sms = _status_zeilen("\n".join(
        e["text"] for e in recorder.premium_sms_out
        if e["to"] == nutzer.premium_sms_reply_to))

    assert telegram == erwartet, telegram
    assert mail == erwartet, mail
    assert sms == erwartet, sms


# ---------------------------------------------------------------------------
# AC-8 -- gespeicherte Namen bleiben unveraendert (reine Anzeige)
# ---------------------------------------------------------------------------

def test_status_und_verschiebung_aendern_gespeicherte_namen_nicht(aufbau, user_ids):
    recorder, settings = aufbau
    nutzer = _nutzer(user_ids)
    trip = _trip_mit_etappen(
        nutzer, _vier_etappen("02: Obstansersee") + [(1, "03 – Porze"), (2, "04:")])
    vorher = [s.name for s in trip.stages]

    _status_telegram(settings, recorder, nutzer)
    sende_telegram_text(settings, nutzer, "ruhetag")

    nachher = [s.name for s in next(
        t for t in load_all_trips(nutzer.user_id) if t.id == trip.id).stages]
    assert nachher == vorher


# ---------------------------------------------------------------------------
# AC-9 -- Zaehlung chronologisch, nicht nach Liste und nicht nach Namenszahl
# ---------------------------------------------------------------------------

def test_nummer_folgt_datum_nicht_listenposition_oder_namenszahl(aufbau, user_ids):
    recorder, settings = aufbau
    nutzer = _nutzer(user_ids)
    # Liste vertauscht; irrefuehrende Namenszahlen
    trip = _trip_mit_etappen(nutzer, [
        (2, "01: Spaet"), (0, "09: Frueh"), (-1, "Gestern"), (1, "03: Mitte"),
    ])
    sortiert = sorted(trip.stages, key=lambda s: s.date)
    erwartet = [(sortiert.index(s) + 1, s.name.split(": ")[-1])
                for s in sortiert if s.date >= _ortstag_jetzt()]

    zeilen = _status_zeilen(_status_telegram(settings, recorder, nutzer))
    assert sorted(zeilen) == sorted(erwartet), zeilen
    assert erwartet == [(2, "Frueh"), (3, "Mitte"), (4, "Spaet")]
