"""TDD RED — der neu protokollierte Unterdrueckungsgrund kommt im Briefing an
(Issue #2050 Scheibe S3b, AC-11 und AC-12).

SPEC: docs/specs/modules/feat_2050_s3b_budget_und_unterdrueckungsgrund.md

Die neun neuen Protokoll-Stellen aus Szenario 10 brauchen keinen eigenen
Lesepfad: ``alert_briefing_anchor.undelivered_since_last_briefing()`` liest sie
automatisch mit, und der Briefing-Renderer zeigt sie im Block
"ZURUECKGEHALTEN". Genau diese Kette wird hier END-ZU-ENDE gemessen —
ECHTE Unterdrueckung ⇒ echtes ``alert_log.json`` ⇒ produktive Leseseite ⇒
gerenderte Briefing-Mail. Eine handgeschriebene Protokoll-Fixture bewiese
davon nur die zweite Haelfte (das tut bereits
``tests/tdd/test_alert_undelivered_hint.py`` fuer #1461).

AC-12 ist die Gegenrichtung: SMS und Telegram bleiben unberuehrt. Geprueft
wird das als DIFFERENZ zweier echter Briefing-Laeufe (mit/ohne Vorfall), nicht
als Quelltext-Suche nach dem Wort ``undelivered`` — ein Dateiinhalt-Check
belegte nur, wo Code steht, nicht was er tut.

RED heute: der Aenderungsalarm protokolliert seine Ruhezeit-Unterdrueckung
gar nicht (Luecke O3), es gibt also nichts zu lesen und nichts anzuzeigen.
AC-12 ist heute gruen — der Vergleich hat mangels Vorfall keine Grundlage;
seine Vorbedingung ("der Lauf MIT Vorfall zeigt den Abschnitt wirklich")
scheitert deshalb heute mit derselben Ursache wie AC-11.

Mock-frei: echte Trips, echte Dienste, echte Zustandsdateien. Der
Briefing-Report wird an einem DELEGIERENDEN Beobachter auf
``TripReportFormatter.format_email`` abgegriffen — die echte Methode laeuft
unveraendert (Muster aus ``test_alert_undelivered_hint.py::_ReportRecorder``).

Pfadregel #1409: alles ueber ``app.loader`` bzw. relativ zu dieser Datei.
"""
from __future__ import annotations

import sys
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from app.config import Settings  # noqa: E402
from app.trip import Waypoint  # noqa: E402
from services.trip_day import anchor_tz  # noqa: E402

from tests.helpers.alert_log_fixtures import (  # noqa: E402
    LAT, LON, gust_alert_trip, weather,
)
from tests.helpers.nowcast_gate_fixtures import (  # noqa: E402
    CountingFrameSource, clean_uid, fresh_uid, quiet_window_now,
    settings_email_only, trip_alert_service, write_user_tier,
)

# Alle Transport-Felder ausdruecklich unbrauchbar: ein weggelassenes Feld
# faellt bei pydantic still auf die Prod-`.env` zurueck — genau so gingen am
# 2026-08-03 echte Telegram-Nachrichten an den Produktiv-Chat des PO (#1477).
_OHNE_TRANSPORT: dict = {
    "smtp_host": "", "smtp_user": "", "smtp_pass": "", "mail_to": "",
    "telegram_bot_token": "", "telegram_chat_id": "",
    "telegram_test_bot_token": "", "telegram_test_chat_id": "",
    "sms_gateway_url": "", "seven_api_key": "", "sms_to": "",
}

_TRIP_ID = "trip-2050s3b-briefing"


def _jetzt() -> datetime:
    return datetime.now(timezone.utc)


def _briefingfaehiger_alarm_trip():
    """Tour, die BEIDES kann: einen Boeen-Aenderungsalarm ausloesen (scharfe
    Regel aus ``gust_alert_trip``) UND ein Briefing rendern (zweiter Wegpunkt
    mit festen Ankunftszeiten, sonst haengt die Etappe am Naismith-Self-Heal).

    Beides MUSS derselbe Trip sein: der Protokoll-Eintrag traegt ``trip.id``
    als Kennung, und genau unter dieser Kennung sucht das Briefing seinen
    Hinweis. Zwei getrennte Trips wuerden aneinander vorbeilaufen.
    """
    trip = gust_alert_trip(_TRIP_ID)
    # `Stage` und `Waypoint` sind eingefroren — die Etappe wird deshalb per
    # `dataclasses.replace` ersetzt, nicht nachtraeglich beschrieben. Die
    # Koordinaten bleiben identisch, damit Ortszone und die von
    # `gust_alert_trip()` bereits gesetzten Briefing-Zeiten weiter passen.
    trip.stages = [replace(trip.stages[0], waypoints=[
        Waypoint(id="G1", name="Start", lat=LAT, lon=LON, elevation_m=1000.0,
                 arrival_calculated="08:00"),
        Waypoint(id="G2", name="Ziel", lat=LAT + 0.1, lon=LON + 0.1,
                 elevation_m=1500.0, arrival_calculated="12:00"),
    ])]
    trip.alert_quiet_from, trip.alert_quiet_to = quiet_window_now(
        zone=anchor_tz(trip, _jetzt())
    )
    return trip


def _anker_setzen(uid: str, entity_id: str, *, vor_stunden: float) -> None:
    """Briefing-Anker ueber den ECHTEN Schreiber — ohne ihn beginnt der
    Rueckblick "ab jetzt" und die Ergebnisliste bliebe leer (AC-7 aus #1461)."""
    from services.alert_briefing_anchor import record_briefing_sent

    record_briefing_sent(
        user_id=uid, entity_id=entity_id, entity_type="trip",
        at=_jetzt() - timedelta(hours=vor_stunden),
    )


def _ruhezeit_unterdrueckung_ausloesen(uid: str, trip) -> None:
    """EIN echter Aenderungsalarm-Lauf, den die Ruhezeit haelt — der Vorgang,
    der nach dieser Scheibe den Protokoll-Eintrag erzeugt."""
    mails: list = []
    unterdrueckt = trip_alert_service(
        uid, settings_email_only(), CountingFrameSource(),
        lambda subject, body: mails.append((subject, body)),
    ).check_and_send_alerts(
        trip,
        [weather(1, gust_max_kmh=20.0)],
        fresh_weather=[weather(1, gust_max_kmh=60.0)],
    )
    assert unterdrueckt is False, (
        "Vorbedingung: die Ruhezeit muss den Aenderungsalarm unterdruecken"
    )
    assert mails == [], "Waehrend der Ruhezeit darf nichts rausgehen"


class _ReportBeobachter:
    """DELEGIERENDER Beobachter auf ``TripReportFormatter.format_email``: die
    echte Methode laeuft unveraendert, festgehalten wird nur ihr Ergebnis."""

    def __init__(self) -> None:
        self.reports: list = []

    def install(self, monkeypatch) -> None:
        from output.renderers.trip_report import TripReportFormatter

        original = TripReportFormatter.format_email
        beobachter = self

        def _mitschreibend(self, *args, **kwargs):
            report = original(self, *args, **kwargs)
            beobachter.reports.append(report)
            return report

        monkeypatch.setattr(TripReportFormatter, "format_email", _mitschreibend)


def _briefing_bauen(monkeypatch, uid: str, trip):
    """ECHTER Briefing-Pfad; liefert den erzeugten Report.

    Kein Kanal scharf (``_OHNE_TRANSPORT`` + abgeschaltete Versandflags): der
    Pfad laeuft vollstaendig durch und rendert die Mail, versendet wird nichts.
    """
    from services.trip_report_scheduler import TripReportSchedulerService

    trip.report_config.send_email = False
    trip.report_config.send_telegram = False
    trip.report_config.send_sms = False

    class _FixtureScheduler(TripReportSchedulerService):
        def _fetch_weather(self, segments, provider=None):
            return [weather(s.segment_id, gust_max_kmh=25.0) for s in segments]

    beobachter = _ReportBeobachter()
    beobachter.install(monkeypatch)
    outcome = _FixtureScheduler(
        settings=Settings(**_OHNE_TRANSPORT), user_id=uid,
    )._send_trip_report_outcome(trip, "morning")
    assert outcome in ("sent", "no_channels"), (
        f"Vorbedingung: der Briefing-Lauf muss durchlaufen, erhalten {outcome!r}"
    )
    assert beobachter.reports, "Vorbedingung: es wurde keine Briefing-Mail gebaut"
    return beobachter.reports[-1]


def _hinweis_zeilen(text: str) -> list[str]:
    """Vorfall-Zeilen beider #1750-Bloecke — ohne Ueberschriften, ohne den
    Rest-Hinweis."""
    from output.renderers.email.undelivered_hint import (
        HEADING_FAILED, HEADING_WITHHELD,
    )

    zeilen = text.splitlines()
    grenzen = {HEADING_FAILED, HEADING_WITHHELD}
    ergebnis: list[str] = []
    for heading in (HEADING_FAILED, HEADING_WITHHELD):
        if heading not in zeilen:
            continue
        for line in zeilen[zeilen.index(heading) + 1:]:
            gestrippt = line.strip()
            if gestrippt == "" or gestrippt in grenzen:
                break
            ergebnis.append(gestrippt)
    return ergebnis


# ═════════════════════════════════ AC-11 ════════════════════════════════════


def test_ac11_neuer_unterdrueckungsgrund_erscheint_im_briefing(monkeypatch):
    """AC-11.

    GIVEN seit dem letzten Briefing-Anker eines Trips wurde ein NEUER
          Unterdrueckungsgrund protokolliert (Ruhezeit am Aenderungsalarm) —
          entstanden aus einem ECHTEN Lauf, nicht aus einer Fixture.
    WHEN  ``undelivered_since_last_briefing(...)`` fuer diese Entitaet
          aufgerufen und daraus das Briefing gerendert wird.
    THEN  enthaelt die Ergebnisliste GENAU diesen Eintrag mit
          ``gate_reason == quiet_hours`` UND ``trigger == forecast_change``,
          und die Mail zeigt ihn im Block "ZURUECKGEHALTEN" unter der
          vorhandenen deutschen Beschriftung — nicht als rohen Code.

    ROT heute: der Aenderungsalarm protokolliert nichts (Luecke O3), die
    Ergebnisliste ist leer.
    """
    from services.alert_briefing_anchor import undelivered_since_last_briefing
    from services.alert_log import REASON_FORECAST_CHANGE, REASON_QUIET_HOURS
    from output.renderers.email.undelivered_hint import (
        HEADING_FAILED, HEADING_WITHHELD, _REASON_LABELS,
    )

    uid = fresh_uid("s3b-ac11")
    clean_uid(uid)
    try:
        write_user_tier(uid, "premium")
        trip = _briefingfaehiger_alarm_trip()
        _anker_setzen(uid, trip.id, vor_stunden=6)
        _ruhezeit_unterdrueckung_ausloesen(uid, trip)

        vorfaelle = undelivered_since_last_briefing(
            user_id=uid, entity_id=trip.id, entity_type="trip",
        )
        assert len(vorfaelle) == 1, (
            f"Erwartet GENAU EINEN Vorfall seit dem Briefing-Anker, gefunden "
            f"{len(vorfaelle)}: {vorfaelle!r}"
        )
        assert set(vorfaelle[0].reasons) == {REASON_QUIET_HOURS}, (
            f"Der Vorfall muss GENAU den Grund {REASON_QUIET_HOURS!r} tragen, "
            f"gefunden {sorted(vorfaelle[0].reasons)!r}"
        )
        assert vorfaelle[0].trigger == REASON_FORECAST_CHANGE, (
            f"Der Ausloeser muss {REASON_FORECAST_CHANGE!r} bleiben, gefunden "
            f"{vorfaelle[0].trigger!r}"
        )

        report = _briefing_bauen(monkeypatch, uid, trip)
        assert len(_hinweis_zeilen(report.email_plain)) == 1, (
            "Die Briefing-Mail muss GENAU EINE Vorfall-Zeile zeigen:\n"
            f"{report.email_plain}"
        )
        assert HEADING_WITHHELD in report.email_plain, (
            "Eine Ruhezeit-Unterdrueckung ist Nutzer-Absicht und gehoert in "
            f"den Block {HEADING_WITHHELD!r}:\n{report.email_plain}"
        )
        assert HEADING_FAILED not in report.email_plain, (
            "Sie ist KEIN Zustellfehler:\n" + report.email_plain
        )
        # Das erwartete Wort kommt aus der SSoT des Renderers, nicht als
        # Literal in den Test — so schreibt der Test die Beschriftung nicht
        # fest, sondern nur, DASS sie statt des rohen Codes erscheint.
        assert _REASON_LABELS[REASON_QUIET_HOURS] in report.email_plain, (
            f"Die deutsche Beschriftung {_REASON_LABELS[REASON_QUIET_HOURS]!r} "
            f"fehlt:\n{report.email_plain}"
        )
        assert REASON_QUIET_HOURS not in report.email_plain, (
            f"Der rohe Code {REASON_QUIET_HOURS!r} darf im Briefing nicht "
            f"erscheinen:\n{report.email_plain}"
        )
    finally:
        clean_uid(uid)


# ═════════════════════════════════ AC-12 ════════════════════════════════════


def test_ac12_sms_und_telegram_bleiben_zeichengleich(monkeypatch):
    """AC-12.

    GIVEN derselbe neu protokollierte Unterdrueckungsgrund liegt vor.
    WHEN  SMS- und Telegram-Kurznachricht fuer denselben Trip im selben
          Zeitraum gerendert werden.
    THEN  sind sie Zeichen fuer Zeichen identisch mit denen eines Laufs OHNE
          Vorfall — kein ``undelivered``-Bezug in den Kurzkanaelen.

    Der Test ist bewusst nicht leerlaufend: er stellt zuerst fest, dass der
    Abschnitt in der MAIL desselben Laufs tatsaechlich erscheint und im
    Kontroll-Lauf tatsaechlich fehlt. Ohne diese Haelfte verglichen wir
    zweimal dasselbe Nichts — genau das ist heute der Fall, weshalb der Test
    an der Vorbedingung scheitert und nicht am Vergleich.
    """
    uid_mit = fresh_uid("s3b-ac12-mit")
    uid_ohne = fresh_uid("s3b-ac12-ohne")
    clean_uid(uid_mit)
    clean_uid(uid_ohne)
    try:
        write_user_tier(uid_mit, "premium")
        write_user_tier(uid_ohne, "premium")

        trip_mit = _briefingfaehiger_alarm_trip()
        _anker_setzen(uid_mit, trip_mit.id, vor_stunden=6)
        _ruhezeit_unterdrueckung_ausloesen(uid_mit, trip_mit)
        mit = _briefing_bauen(monkeypatch, uid_mit, trip_mit)

        # Identischer Trip (gleiche Kennung, gleiche Etappe, gleiche
        # Ruhezeit-Felder) — nur ohne den Alarm-Lauf, der den Vorfall erzeugt.
        trip_ohne = _briefingfaehiger_alarm_trip()
        _anker_setzen(uid_ohne, trip_ohne.id, vor_stunden=6)
        ohne = _briefing_bauen(monkeypatch, uid_ohne, trip_ohne)

        assert len(_hinweis_zeilen(mit.email_plain)) == 1, (
            "Vorbedingung: der Lauf MIT Vorfall muss den Abschnitt in der "
            f"Mail zeigen, sonst prueft der Vergleich nichts.\n{mit.email_plain}"
        )
        assert _hinweis_zeilen(ohne.email_plain) == [], (
            "Vorbedingung: der Kontroll-Lauf darf keinen Abschnitt zeigen."
        )

        assert mit.sms_text == ohne.sms_text, (
            "AC-12: Der SMS-Text muss Zeichen fuer Zeichen identisch bleiben.\n"
            f"mit:  {mit.sms_text!r}\nohne: {ohne.sms_text!r}"
        )
        assert len(mit.sms_text or "") == len(ohne.sms_text or ""), (
            "AC-12: auch die Zeichenlaenge der SMS bleibt unveraendert"
        )
        assert mit.telegram_bubbles == ohne.telegram_bubbles, (
            "AC-12: Die Telegram-Kurzform muss Zeichen fuer Zeichen identisch "
            f"bleiben.\nmit:  {mit.telegram_bubbles!r}\n"
            f"ohne: {ohne.telegram_bubbles!r}"
        )
    finally:
        clean_uid(uid_mit)
        clean_uid(uid_ohne)
