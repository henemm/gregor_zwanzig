"""TDD RED — Issue #2051 Scheibe S4: Eingang des neuen Kommandos `/strecke`
ueber beide Inbound-Kanaele (Telegram-Freitext/-Slash, E-Mail) plus Hilfe.

SPEC: docs/specs/modules/feat_2051_s4_strecke_kommando.md — AC-1, AC-2, AC-3.

RED-Ursache: `"strecke"` steht weder in
`inbound_telegram_reader._SHORTCUT_MAP` noch in
`trip_command_processor._BARE_KEYWORD_MAP`/`_VALID_COMMANDS`, und
`_show_help()` kennt keine STRECKE-Zeile.

Mock-frei: echte `InboundTelegramReader`/`TripCommandProcessor`/
`InboundMessage`-Objekte, kein `Mock()`/`patch()`.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from services.inbound_telegram_reader import InboundTelegramReader
from services.trip_command_processor import InboundMessage, TripCommandProcessor
from tests.helpers.strecke_fixtures import fresh_trip_id, future_two_point_trip


# --------------------------------------------------------------------------
# AC-1: Freitext "strecke" und Slash "/strecke" loesen denselben Schluessel.
# --------------------------------------------------------------------------

def test_ac1_freitext_und_slash_liefern_denselben_schluessel():
    """AC-1 GIVEN zwei Telegram-Nachrichten -- (a) 'strecke' (Freitext), (b)
    '/strecke' (Slash) -- WHEN beide durch `_parse_command` laufen THEN
    lösen BEIDE denselben internen Schlüssel `('strecke', None)` auf."""
    reader = InboundTelegramReader()

    schluessel_freitext = reader._parse_command("strecke")
    schluessel_slash = reader._parse_command("/strecke")

    assert schluessel_freitext == ("strecke", None), (
        f"AC-1: Freitext 'strecke' muss ('strecke', None) liefern, erhalten "
        f"{schluessel_freitext!r}"
    )
    assert schluessel_slash == ("strecke", None), (
        f"AC-1: Slash '/strecke' muss ('strecke', None) liefern, erhalten "
        f"{schluessel_slash!r}"
    )
    assert schluessel_freitext == schluessel_slash, (
        f"AC-1: Freitext- und Slash-Eingabe muessen IDENTISCH aufgeloest "
        f"werden, erhalten {schluessel_freitext!r} vs. {schluessel_slash!r}"
    )
    # Gegenprobe "Form statt Wert": ein Schluessel, der zwar wahr, aber ein
    # ANDERER String ist (z.B. 'Strecke' mit Grossschreibung oder ein Tippfehler),
    # faellt hier durch die Gleichheitspruefung, nicht nur durch Wahrheitswert.
    assert schluessel_freitext[0] == "strecke" and schluessel_slash[0] == "strecke"


def test_ac1_grossschreibung_und_restliche_zeile_bleiben_unveraendert():
    """AC-1 (Formvarianten): case-insensitive wie alle Bare-Keywords, und
    eine fuehrende Grossschreibung darf das Ergebnis nicht veraendern --
    dasselbe Muster wie 'HEUTE'/'heute'."""
    reader = InboundTelegramReader()

    assert reader._parse_command("STRECKE") == ("strecke", None), (
        "AC-1: Grossschreibung 'STRECKE' muss wie 'strecke' aufgeloest werden"
    )
    assert reader._parse_command("Strecke") == ("strecke", None)


# --------------------------------------------------------------------------
# AC-2: E-Mail-Inbound (channel="email") loest ueber denselben Prozessor-
#       Kern denselben Handler aus -- kein "Unbekannter Befehl".
# --------------------------------------------------------------------------

def test_ac2_email_body_strecke_loest_den_handler_aus():
    """AC-2 GIVEN eine E-Mail mit Body 'STRECKE' als erste Zeile WHEN
    `TripCommandProcessor().process()` mit channel='email' laeuft THEN wird
    `_show_strecke` aufgerufen (`result.command == 'strecke'`, kein
    'Unbekannter Befehl')."""
    trip_id = fresh_trip_id("ac2")
    trip = future_two_point_trip(trip_id, 8.0)

    # Trip muss ueber den Prozessor-Lookup ("Trip nicht gefunden" sonst)
    # auffindbar sein -- dafuer persistiert der Test ihn ueber die echte
    # save_trip()-Schreibkette (Muster S2a AC-9-Draht-Test).
    import json

    from app.loader import get_briefings_dir

    uid = f"tdd-2051-s4-ac2-{uuid.uuid4().hex[:6]}"
    trips_dir = get_briefings_dir(uid)
    trips_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "id": trip.id, "name": trip.name,
        "stages": [{
            "id": trip.stages[0].id, "name": trip.stages[0].name,
            "date": trip.stages[0].date.isoformat(),
            "waypoints": [
                {
                    "id": w.id, "name": w.name, "lat": w.lat, "lon": w.lon,
                    "elevation_m": w.elevation_m,
                    "arrival_calculated": w.arrival_calculated,
                    "distance_from_start_km": w.distance_from_start_km,
                }
                for w in trip.stages[0].waypoints
            ],
        }],
        "report_config": {
            "trip_id": trip.report_config.trip_id,
            "send_email": True, "send_telegram": False,
        },
    }
    (trips_dir / f"{trip.id}.json").write_text(json.dumps(data))

    msg = InboundMessage(
        trip_name=trip.name, body="STRECKE", sender="tester@example.invalid",
        channel="email", received_at=datetime.now(timezone.utc), user_id=uid,
    )

    result = TripCommandProcessor().process(msg)

    assert result.command == "strecke", (
        f"AC-2: erwartet result.command == 'strecke', erhalten "
        f"{result.command!r} (subject={result.confirmation_subject!r}, "
        f"body={result.confirmation_body!r})"
    )
    assert "Unbekannter Befehl" not in result.confirmation_subject, (
        f"AC-2: 'STRECKE' darf nicht als unbekannter Befehl gelten -- "
        f"subject={result.confirmation_subject!r}"
    )


# --------------------------------------------------------------------------
# F003 (Adversary-Befund team-lead): der Telegram-Eingangsdraht war end-to-
# end unverifiziert -- AC-1 prueft nur `_parse_command()` isoliert, AC-2 nur
# `channel="email"` durch `process()`. Diese Luecke faengt die Mutation
# 'elif key == "strecke" and msg.channel == "email":' im Dispatch, die
# Telegram-Nachrichten in "Interner Fehler." laufen liesse -- Telegram ist
# der haeufiger genutzte Eingangskanal (E4).
# --------------------------------------------------------------------------

def test_f003_telegram_body_strecke_loest_den_handler_aus_end_to_end():
    """F003 GIVEN eine Telegram-Nachricht mit Body 'STRECKE' als erste Zeile
    WHEN `TripCommandProcessor().process()` mit channel='telegram' laeuft
    THEN wird `_show_strecke` real aufgerufen (`result.command == 'strecke'`,
    kein 'Interner Fehler.') -- derselbe Draht-Nachweis wie AC-2, nur ueber
    den anderen Eingangskanal."""
    import json

    from app.loader import get_briefings_dir

    trip_id = fresh_trip_id("f003")
    trip = future_two_point_trip(trip_id, 8.0)

    uid = f"tdd-2051-s4-f003-{uuid.uuid4().hex[:6]}"
    trips_dir = get_briefings_dir(uid)
    trips_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "id": trip.id, "name": trip.name,
        "stages": [{
            "id": trip.stages[0].id, "name": trip.stages[0].name,
            "date": trip.stages[0].date.isoformat(),
            "waypoints": [
                {
                    "id": w.id, "name": w.name, "lat": w.lat, "lon": w.lon,
                    "elevation_m": w.elevation_m,
                    "arrival_calculated": w.arrival_calculated,
                    "distance_from_start_km": w.distance_from_start_km,
                }
                for w in trip.stages[0].waypoints
            ],
        }],
        "report_config": {
            "trip_id": trip.report_config.trip_id,
            "send_email": True, "send_telegram": False,
        },
    }
    (trips_dir / f"{trip.id}.json").write_text(json.dumps(data))

    msg = InboundMessage(
        trip_name=trip.name, body="STRECKE", sender="123456789",
        channel="telegram", received_at=datetime.now(timezone.utc), user_id=uid,
    )

    result = TripCommandProcessor().process(msg)

    assert result.command == "strecke", (
        f"F003: erwartet result.command == 'strecke' ueber channel="
        f"'telegram', erhalten {result.command!r} (subject="
        f"{result.confirmation_subject!r}, body={result.confirmation_body!r})"
    )
    assert "Interner Fehler" not in result.confirmation_body, (
        f"F003: der Telegram-Draht darf nicht im 'Should not reach here'-"
        f"Zweig landen -- body={result.confirmation_body!r}"
    )


# --------------------------------------------------------------------------
# AC-3: die Hilfe kennt eine STRECKE-Zeile.
# --------------------------------------------------------------------------

def test_ac3_hilfe_nennt_strecke_kommando():
    """AC-3 GIVEN den Befehl HILFE WHEN `_show_help()` laeuft THEN enthaelt
    der Text eine Zeile, die mit '  STRECKE' beginnt, mit einer
    Kurzbeschreibung der Regen-Ereignisflaechen entlang der Reststrecke."""
    result = TripCommandProcessor()._show_help()

    zeilen = result.confirmation_body.splitlines()
    strecke_zeilen = [z for z in zeilen if z.startswith("  STRECKE")]

    assert strecke_zeilen, (
        f"AC-3: keine Zeile beginnt mit '  STRECKE' im Hilfe-Text:\n"
        f"{result.confirmation_body}"
    )
    # Positivkontrolle: die Zeile muss auch inhaltlich etwas ueber die
    # Reststrecke/Ereignisflaechen sagen, nicht nur das Wort STRECKE tragen
    # (Formpruefung waere sonst schon mit einer leeren Ueberschrift wahr).
    assert any(
        "Reststrecke" in z or "Regen" in z for z in strecke_zeilen
    ), (
        f"AC-3: die STRECKE-Zeile muss die Reststrecke/Regen-Ereignisflaechen "
        f"benennen, erhalten: {strecke_zeilen!r}"
    )
