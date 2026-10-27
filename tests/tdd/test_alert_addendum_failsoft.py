"""Fail-soft-Waechter der Nachtrags-Bezugszeile am WIRKORT (Issue #2018).

SPEC: docs/specs/modules/alert_nachtragsmeldung.md — Teil B, B2:

    "Fehlt ``addendum_reported_at`` (fail-soft-Fall aus A3), entfaellt die
    Uhrzeit ersatzlos aus dem Satz ('Ergaenzung zur amtlichen Warnung')
    statt eines erfundenen Platzhalters."

Warum diese Datei existiert (Adversary-Finding F002, 2026-08-21): die
Zusicherung wird im Trip-Nowcast-Pfad (`services/trip_alert.py`) gebaut,
nicht im Renderer. Entfernt man dort die Wachzeile
``if _identity_gate.addendum_reported_at is not None:``, wirft
``local_fmt(None, tz)`` einen ``AttributeError`` — und zwar an einer Stelle
OHNE Try/Except pro Trip. Der Fehler reisst damit ``check_radar_alerts()``
fuer ALLE Trips ab: "Alarm bleibt aus" ist die gefaehrlichste
Fehlerrichtung dieses Projekts. Vor dieser Datei blieb genau diese
Verfaelschung von keinem Test bemerkt (nachgemessen: 101 Tests gruen).

Gemessen wird deshalb ueber den ECHTEN Trip-Pfad (`check_radar_alerts()`),
nicht ueber einen isolierten Renderer-Aufruf: nur dort entsteht die
Bezugszeile, und nur dort ist der Abbruch beobachtbar.

Mock-frei (CLAUDE.md): echte Register-Eintraege, echter
``TripAlertService``-Lauf ueber die vorhandenen DI-Naehte (``radar_service=``,
``mail_sink=``), echte gerenderte Mailkoerper. Kein ``Mock()``/``patch()``/
``MagicMock``, kein Netz, kein echter Versand.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from output.renderers.alert.model import AlertMessage
from services.notification_service import NotificationService

from tests.helpers.nowcast_gate_fixtures import (
    TRIP_ZONE, clean_uid, fresh_uid, make_trip, quiet_window_elsewhere,
    radar_service, save_trip, settings_email_only, write_user_tier,
)
from tests.tdd.test_alert_addendum_sms import _ConvectiveFrameSource

#: Der Satz, den der Wanderer liest, wenn der Meldezeitpunkt der amtlichen
#: Warnung im Register fehlt oder unlesbar ist — OHNE Uhrzeit, ohne
#: Platzhalter. Nutzertext, deshalb Literal statt Prueflings-Konstante.
BEZUG_OHNE_UHRZEIT = "Ergänzung zur amtlichen Warnung"

#: Zeichenfolgen, die einen erfundenen Platzhalter verraten wuerden.
PLATZHALTER = ("None", "??", "--", "n/a", "N/A", "{", "}")


class _Recorder(NotificationService):
    """Echte Unterklasse (kein Mock): merkt sich die kanonische
    ``AlertMessage`` und laesst den unveraenderten echten Versand
    weiterlaufen."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.dispatched: list[AlertMessage] = []

    def _dispatch_alert_message(self, alert_msg, effective_channels, **kwargs):
        self.dispatched.append(alert_msg)
        return super()._dispatch_alert_message(alert_msg, effective_channels, **kwargs)


def _amtlichen_eintrag_beschaedigen(uid: str, trip_id: str, *, roh: object) -> None:
    """Registriert eine amtliche Warnung und setzt danach ihr
    ``reported_at`` auf den uebergebenen Rohwert (``_UNSET`` -> Feld ganz
    entfernt). Genau so sehen Alt-/Fremdeintraege aus, die A3 fail-soft auf
    ``addendum_reported_at=None`` abbildet."""
    from services.alert_gate import record_event_identity
    from services.alert_state import AlertStateService

    now = datetime.now(timezone.utc)
    record_event_identity(
        user_id=uid, entity_id=trip_id, hazard_class="wet",
        segment_ids=["1"], severity="MODERATE",
        window_start=now - timedelta(minutes=30),
        window_end=now + timedelta(hours=3),
        now=now - timedelta(minutes=25),
    )
    service = AlertStateService(user_id=uid)
    state = service.load(trip_id)
    schluessel = [k for k in state if str(k).startswith("event_identity:wet:")]
    assert len(schluessel) == 1, f"Erwartet genau EINEN Registereintrag: {state!r}"
    if roh is None:
        state[schluessel[0]].pop("reported_at", None)
    else:
        state[schluessel[0]]["reported_at"] = roh
    service.save(trip_id, state)


def _bezugszeile(text: str) -> str:
    zeilen = [z.strip() for z in text.splitlines() if BEZUG_OHNE_UHRZEIT in z]
    assert len(zeilen) == 1, (
        f"Erwartet genau EINE Bezugszeile in:\n{text}"
    )
    return zeilen[0]


@pytest.mark.parametrize(
    "roh, fall",
    [
        (None, "reported_at fehlt ganz"),
        ("16:15 Uhr", "reported_at unparsbar (keine ISO-Zeit)"),
    ],
)
def test_nachtrag_ohne_meldezeitpunkt_bleibt_zustellbar_und_reisst_den_lauf_nicht_ab(
    roh, fall,
):
    """Spec B2 / Adversary-F002.

    GIVEN einen amtlichen Registereintrag, dessen ``reported_at`` FEHLT
          bzw. UNPARSBAR ist, und einen danach auflaufenden eskalierenden
          Nowcast fuer denselben Trip — sowie einen ZWEITEN, voellig
          unbeteiligten Trip desselben Nutzers
    WHEN  ``check_radar_alerts()`` laeuft
    THEN  wird der Nachtrag ZUGESTELLT, seine Bezugszeile lautet
          "Ergaenzung zur amtlichen Warnung" OHNE Uhrzeit und ohne
          Platzhalter, es gibt keinen Absturz, und der zweite Trip bekommt
          seinen gewoehnlichen (unmarkierten) Alarm.

    Gegenprobe (Pflicht, Protokoll im Adversary-Dialog): wird die Wachzeile
    ``if _identity_gate.addendum_reported_at is not None:`` in
    ``trip_alert.py`` entfernt, wirft ``local_fmt(None, tz)`` und dieser
    Test wird rot — inklusive des ZWEITEN Trips, der dann gar nicht mehr
    geprueft wird.
    """
    from services.trip_alert import TripAlertService

    uid = fresh_uid("2018-f002")
    nachtrag_trip, normal_trip = "trip-2018-f002-a", "trip-2018-f002-b"
    clean_uid(uid)
    try:
        write_user_tier(uid, "premium")
        _amtlichen_eintrag_beschaedigen(uid, nachtrag_trip, roh=roh)
        quiet_from, quiet_to = quiet_window_elsewhere(zone=TRIP_ZONE)
        for trip_id in (nachtrag_trip, normal_trip):
            save_trip(
                make_trip(trip_id, quiet_from=quiet_from, quiet_to=quiet_to), uid,
            )

        mails: list[tuple[str, str]] = []
        svc = TripAlertService(
            settings=settings_email_only(), throttle_hours=0, user_id=uid,
            radar_service=radar_service(_ConvectiveFrameSource()),
            mail_sink=lambda subject, body: mails.append((subject, body)),
        )
        recorder = _Recorder(settings_email_only(), uid)
        svc._notification_service = recorder

        sent = svc.check_radar_alerts()

        assert sent == 2, (
            f"{fall}: beide Trips muessen ihren Alarm bekommen — der Nachtrag "
            "darf weder ausfallen noch den Lauf der uebrigen Trips abreissen "
            f"(check_radar_alerts() lieferte {sent})."
        )
        markiert = [m for m in recorder.dispatched if m.addendum_reference]
        assert len(markiert) == 1, (
            f"{fall}: erwartet GENAU EINE als Nachtrag markierte Meldung, "
            f"erfasst: {[m.addendum_reference for m in recorder.dispatched]!r}"
        )
        assert len(recorder.dispatched) == 2, (
            f"{fall}: der zweite Trip muss seinen gewoehnlichen Alarm "
            f"bekommen: {recorder.dispatched!r}"
        )
        assert markiert[0].addendum_reference == BEZUG_OHNE_UHRZEIT, (
            f"{fall}: ohne lesbaren Meldezeitpunkt muss die Uhrzeit ERSATZLOS "
            "entfallen — kein Platzhalter, kein angehaengtes 'von': "
            f"{markiert[0].addendum_reference!r}"
        )

        nachtrags_mails = [b for _s, b in mails if BEZUG_OHNE_UHRZEIT in b]
        assert len(nachtrags_mails) == 1, (
            f"{fall}: die Bezugszeile muss in genau EINER zugestellten Mail "
            f"stehen ({len(mails)} Mails erfasst)."
        )
        zeile = _bezugszeile(nachtrags_mails[0])
        assert zeile == BEZUG_OHNE_UHRZEIT, (
            f"{fall}: die gerenderte Bezugszeile traegt einen Zusatz, obwohl "
            f"kein Meldezeitpunkt lesbar war: {zeile!r}"
        )
        for muster in PLATZHALTER:
            assert muster not in zeile, (
                f"{fall}: Platzhalter {muster!r} in der Bezugszeile: {zeile!r}"
            )
    finally:
        clean_uid(uid)
