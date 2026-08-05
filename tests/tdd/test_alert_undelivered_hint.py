"""TDD RED — Issue #1461 Scheibe S3b-1: das Briefing weist aus, welche
Alarm-Meldungen seit dem letzten Briefing einen Kanal NICHT erreicht haben.

SPEC: docs/specs/modules/feat_1461_s3b1_briefing_sichtbarkeit.md (AC-1 … AC-16)

RED-Grund heute (gemessen): das Alarm-Protokoll aus #1459 hat sechs
Schreibstellen und NULL Leser auf der Python-Seite. Konkret fehlen:

* ``services.alert_log.read_undelivered()``  — die Lesefunktion
* ``services.alert_briefing_anchor.record_briefing_sent()`` /
  ``last_briefing_at()`` — der Zeitraum "seit dem letzten Briefing"
* ``output.renderers.email.undelivered_hint`` — der Anzeige-Baustein
* die Durchreichung als kwarg durch ``notification_service`` →
  ``TripReportFormatter.format_email()`` → ``render_email()`` bzw.
  ``scheduler_dispatch_service`` → ``render_compare_email()``

Testpolitik (CLAUDE.md "Test-Politik: Zwei Schichten"):

* **Kein Mock-Theater.** Es gibt kein ``Mock()``/``patch()``/``MagicMock``.
  Die Protokolldateien sind ECHTE ``alert_log.json``-Dateien im echten Schema
  unter der pytest-isolierten ``app.loader.get_data_dir()``-Basis (#1133).
  Das Schema der Fixture wird von
  ``test_fixtur_schema_deckt_sich_mit_der_echten_schreibfunktion`` gegen die
  echte Schreibfunktion ``alert_log.append_entry()`` gehalten — die Fixture
  kann also nicht von der Wirklichkeit wegdriften.
* **Wirkung statt Fähigkeit.** Geprueft wird der TEXT der erzeugten Mail, nicht
  der Rueckgabewert einer Hilfsfunktion. Das Briefing entsteht ueber den echten
  Versandpfad (``TripReportSchedulerService._send_trip_report_outcome`` bzw.
  ``scheduler_dispatch_service.send_one_compare_preset``); der Report wird an
  einem DELEGIERENDEN Beobachter auf ``TripReportFormatter.format_email``
  abgegriffen — die echte Methode laeuft unveraendert, es wird nur
  mitgeschrieben, was sie zurueckgibt (Muster aus
  ``tests/tdd/test_trip_briefing_anchor_unchanged.py::_ResetRecorder``).
* **Kein Netz, kein Versand.** Trip: alle Transport-Felder leer (``Settings()``
  faellt bei fehlenden Feldern still auf die Prod-``.env`` zurueck, #1477).
  Ortsvergleich: ``mail_sink``-Naht. Wetter ueber den autouse
  Offline-Fixture-Provider.

Pfadregel #1409: ``REPO_ROOT`` wird relativ zu DIESER Datei aufgeloest.

────────────────────────────────────────────────────────────────────────────
Der Anzeige-Vertrag, den diese Tests festschreiben (Spec "Beispiel-Ausgabe"):

    NICHT BEI DIR ANGEKOMMEN

      05.08. 18:42 · Gewitter · SMS nicht zugestellt
      … und 3 weitere

* Ueberschrift: ``UNDELIVERED_HEADING``
* je Vorfall EINE Zeile, erkennbar am Marker ``"nicht zugestellt"``
  (im ganzen Repo sonst nirgends im Ausgabetext, gemessen)
* die Zeile nennt Zeitpunkt (Briefing-Zeitzone), Anlass, Kanaele, Grund
* Deckelung bei ``MAX_UNDELIVERED_LINES`` = 5, darunter "und N weitere"

Die STRUKTUR je Zeile wird am Klartext-Teil geprueft (dort gibt die Spec ein
woertliches Beispiel vor); fuer HTML wird die Anwesenheit aller vier Angaben
und die Zeilen-ANZAHL geprueft, nicht das Markup — sonst schriebe der Test das
HTML-Geruest fest statt der Zusicherung.
────────────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

import json
import os
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.config import Settings
from app.loader import get_data_dir, save_location
from app.models import TripReportConfig
from app.trip import Stage, Trip, Waypoint

from tests.helpers.alert_log_fixtures import (
    LAT,
    LON,
    gust_alert_trip,
    settings_email_only,
    weather,
)

# Pfadregel #1409: Pruefling relativ zur Testdatei — nie ueber einen festen
# Hauptrepo-Pfad, sonst pruefte dieser Test aus dem Worktree die unveraenderte
# Hauptrepo-Kopie und meldete falsches Gruen.
REPO_ROOT = Path(__file__).resolve().parents[2]

# Zeilen-Marker des Hinweis-Abschnitts (s. Modul-Docstring).
LINE_MARKER = "nicht zugestellt"

ALL_CHANNELS = ("email", "telegram", "sms")

# Alle Transport-Felder ausdruecklich unbrauchbar (#1477).
_NO_TRANSPORT_FIELDS: dict = {
    "smtp_host": "", "smtp_user": "", "smtp_pass": "", "mail_to": "",
    "telegram_bot_token": "", "telegram_chat_id": "",
    "telegram_test_bot_token": "", "telegram_test_chat_id": "",
    "sms_gateway_url": "", "seven_api_key": "", "sms_to": "",
}


def _uid(prefix: str) -> str:
    return f"tdd-1461-s3b1-{prefix}-{uuid.uuid4().hex[:6]}"


def _settings_no_transport() -> Settings:
    return Settings(**_NO_TRANSPORT_FIELDS)


def _jetzt() -> datetime:
    return datetime.now(timezone.utc).replace(second=0, microsecond=0)


# ═══════════════════════════ Protokoll-Fixtures ═══════════════════════════
#
# Echtes ``alert_log.json`` im Schema von ``alert_log.append_entry()``.
# Direkt geschrieben (statt ueber ``append_entry``), weil ``append_entry`` den
# Zeitstempel immer auf "jetzt" setzt — und dieser Test genau die Zeitachse
# pruefen muss. Das Schema haelt der Drift-Waechter unten fest.


def _entry(
    *,
    entity_id: str,
    entity_type: str = "trip",
    sent_at: datetime,
    metrics: tuple = (),
    hazards: tuple = (),
    reason: str = "forecast_change",
    channels_sent: tuple = (),
    not_sent: tuple = (),
    severity: str = "MODERATE",
    changes_count: int = 1,
) -> dict:
    """Ein Protokoll-Eintrag. ``not_sent`` ist eine Folge von
    ``(kanal, grund)``-Paaren — genau die Traegerform, die
    ``alert_log._channels_not_sent()`` erzeugt."""
    return {
        "entity_id": entity_id,
        "entity_type": entity_type,
        "sent_at": sent_at.astimezone(timezone.utc).isoformat(),
        "changes_count": changes_count,
        "severity": severity,
        "metrics": [{"metric_id": m, "aggregation": a} for m, a in metrics],
        "hazards": sorted(hazards),
        "reason": reason,
        "channels_sent": sorted(channels_sent),
        "channels_not_sent": [{"channel": c, "reason": r} for c, r in not_sent],
    }


def _write_log(user_id: str, *, entries=(), not_delivered=()) -> Path:
    path = get_data_dir(user_id) / "alert_log.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(
        {"entries": list(entries), "not_delivered": list(not_delivered)},
        indent=2,
    ))
    return path


def _read_log(user_id: str) -> dict:
    path = get_data_dir(user_id) / "alert_log.json"
    data = json.loads(path.read_text())
    data.setdefault("entries", [])
    data.setdefault("not_delivered", [])
    return data


def _seed(
    user_id: str,
    *,
    entity_id: str,
    entity_type: str = "trip",
    entries=(),
    not_delivered=(),
    letztes_briefing: datetime | None = None,
) -> None:
    """Protokoll UND Briefing-Zeitstempel setzen — in DIESER Reihenfolge.

    Umgekehrt waere der Test still wertlos, falls der Zeitstempel (eine
    naheliegende Umsetzung) als weiterer Top-Level-Schluessel IN
    ``alert_log.json`` landet: das nachtraegliche Schreiben der Protokolldatei
    wuerde ihn wieder wegwerfen.
    """
    _write_log(user_id, entries=entries, not_delivered=not_delivered)
    if letztes_briefing is not None:
        from services.alert_briefing_anchor import record_briefing_sent

        record_briefing_sent(
            user_id=user_id, entity_id=entity_id, entity_type=entity_type,
            at=letztes_briefing,
        )


# ═══════════════════════════ Briefing-Fixtures ════════════════════════════


def _trip(trip_id: str, *, email_format: str = "full") -> Trip:
    """Tour ohne scharfen Kanal: der Briefing-Pfad laeuft VOLLSTAENDIG durch
    (Ergebnis ``no_channels``) und rendert die Mail — versendet wird nichts.
    Muster aus ``test_trip_briefing_anchor_unchanged.py::_trip``."""
    stage = Stage(
        id="T1", name="Tag 1", date=date.today(),
        waypoints=[
            Waypoint(id="G1", name="Start", lat=LAT, lon=LON, elevation_m=1000.0),
            Waypoint(id="G2", name="Ziel", lat=LAT + 0.1, lon=LON + 0.1, elevation_m=1500.0),
        ],
    )
    trip = Trip(id=trip_id, name="Hinweis-Trip", stages=[stage], official_warnings=None)
    trip.report_config = TripReportConfig(
        trip_id=trip_id, send_email=False, send_telegram=False, send_sms=False,
        email_format=email_format,
    )
    trip.alert_cooldown_minutes = 0
    return trip


def _scheduler_class(gust: float):
    """Echte Unterklasse des Schedulers (kein Mock): Wetter aus der Fixture."""
    from services.trip_report_scheduler import TripReportSchedulerService

    class _FixtureScheduler(TripReportSchedulerService):
        def _fetch_weather(self, segments, provider=None):
            return [weather(s.segment_id, gust_max_kmh=gust) for s in segments]

    return _FixtureScheduler


class _ReportRecorder:
    """DELEGIERENDER Beobachter auf ``TripReportFormatter.format_email``.

    Kein Mock: die echte Methode laeuft unveraendert (die Mail wird also
    wirklich gebaut), es wird nur festgehalten, WAS sie zurueckgegeben hat.
    Anders als ein Direktaufruf des Renderers laeuft damit der komplette
    Versandpfad inklusive echter ``user_id`` — genau der Ort, an dem die
    Mandantentrennung entschieden wird.
    """

    def __init__(self) -> None:
        self.reports: list = []

    def install(self, monkeypatch) -> None:
        from output.renderers.trip_report import TripReportFormatter

        original = TripReportFormatter.format_email
        recorder = self

        def _recording_format_email(self, *args, **kwargs):
            report = original(self, *args, **kwargs)
            recorder.reports.append(report)
            return report

        monkeypatch.setattr(TripReportFormatter, "format_email", _recording_format_email)


def _run_trip_briefing(recorder, uid: str, trip: Trip, *, on_demand: bool = False,
                       gust: float = 25.0):
    """Fuehrt den ECHTEN Briefing-Pfad aus und liefert den erzeugten Report."""
    scheduler = _scheduler_class(gust)(settings=_settings_no_transport(), user_id=uid)
    outcome = scheduler._send_trip_report_outcome(trip, "morning", on_demand=on_demand)
    assert outcome in ("sent", "no_channels"), (
        f"Voraussetzung: der Briefing-Lauf muss durchlaufen, erhalten {outcome!r}"
    )
    assert recorder.reports, "Voraussetzung: es wurde keine Briefing-Mail gebaut"
    return recorder.reports[-1]


def _trip_tz():
    from utils.timezone import tz_for_coords
    return tz_for_coords(LAT, LON)


# ═══════════════════════════ Text-Auswertung ══════════════════════════════


def _heading() -> str:
    from output.renderers.email.undelivered_hint import UNDELIVERED_HEADING
    return UNDELIVERED_HEADING


def _hint_lines(text: str) -> list[str]:
    """Die Vorfall-Zeilen des Hinweis-Abschnitts (Marker s. Modul-Docstring)."""
    return [line.strip() for line in text.splitlines() if LINE_MARKER in line]


def _html_as_text(html: str) -> str:
    """HTML auf Text reduzieren — jedes Element auf eine eigene Zeile."""
    return re.sub(r"<[^>]+>", "\n", html)


def _local_hhmm(moment: datetime) -> str:
    return moment.astimezone(_trip_tz()).strftime("%H:%M")


def _ohne_uhrzeiten(text: str) -> str:
    """Uhrzeiten entfernen — fuer Gleichheits-Vergleiche zweier Laeufe.

    Die Mail traegt einen Erzeugungs-Zeitstempel auf die Minute genau; zwei
    Laeufe koennten sonst allein wegen eines Minutenwechsels auseinanderfallen.
    Die Wetterwerte beider Laeufe sind identisch, es geht also nichts
    Pruefbares verloren.
    """
    return re.sub(r"\d{1,2}:\d{2}(:\d{2})?", "", text)


# ═══════════════════ Schema-Waechter fuer die Fixture ═════════════════════


def test_fixtur_schema_deckt_sich_mit_der_echten_schreibfunktion():
    """Die Protokoll-Fixture dieses Tests muss dasselbe Schema haben wie das,
    was die echte Schreibfunktion erzeugt — sonst pruefen alle folgenden Tests
    an der Wirklichkeit vorbei (CLAUDE.md: "Fixtures gegen Wirklichkeit").

    Kein Verhaltens-Test des Features, sondern der Waechter ueber der Fixture.
    """
    from services import alert_log

    uid = _uid("schema")
    alert_log.append_entry(
        uid, entity_id="trip-schema", entity_type="trip", changes_count=1,
        severity="MODERATE", metrics=[("gust", "max")], hazards=[],
        reason="forecast_change",
        effective_channels={"email", "sms"}, sent_channels=["email"],
    )
    echt = _read_log(uid)["entries"][0]
    fixtur = _entry(
        entity_id="trip-schema", sent_at=datetime.now(timezone.utc),
        metrics=(("gust", "max"),), reason="forecast_change",
        channels_sent=("email",), not_sent=(("sms", "delivery_failed"),),
    )
    assert set(fixtur) == set(echt), (
        "Die Fixture-Schluessel weichen von der echten Schreibfunktion ab: "
        f"nur Fixture {set(fixtur) - set(echt)!r}, nur echt {set(echt) - set(fixtur)!r}"
    )
    assert fixtur["channels_not_sent"][0].keys() == echt["channels_not_sent"][0].keys(), (
        "Die Kanal-Traegerform der Fixture weicht ab: "
        f"{fixtur['channels_not_sent'][0]!r} vs. {echt['channels_not_sent'][0]!r}"
    )


# ══════════════════════════════════ AC-1 ══════════════════════════════════


def test_ac1_teilausfall_zeile_nennt_zeit_groesse_kanal_und_grund(monkeypatch):
    """AC-1.

    GIVEN ein Alarm wurde per E-Mail zugestellt, erreichte aber die SMS nicht
          (``entries[*].channels_not_sent = [{sms, delivery_failed}]``).
    WHEN  das naechste Briefing des Trips erzeugt wird.
    THEN  enthaelt die Briefing-Mail EINE Zeile, die den Zeitpunkt in der
          Zeitzone des Briefings, die betroffene Wettergroesse, den Kanal
          'SMS' und den Grund nennt.

    Die Zeitzone ist der Kern: der Protokoll-Zeitstempel steht in UTC. Steht
    in der Zeile die UTC-Uhrzeit, ist AC-1 verletzt — auch wenn 'eine Zeile'
    da ist.
    """
    uid = _uid("ac1")
    trip = _trip(f"trip-ac1-{uuid.uuid4().hex[:6]}")

    jetzt = _jetzt()
    vorfall = jetzt - timedelta(hours=3)
    _seed(uid, entity_id=trip.id, letztes_briefing=jetzt - timedelta(hours=6),
          entries=[_entry(
              entity_id=trip.id, sent_at=vorfall, metrics=(("gust", "max"),),
              reason="forecast_change", channels_sent=("email",),
              not_sent=(("sms", "delivery_failed"),),
          )])

    recorder = _ReportRecorder()
    recorder.install(monkeypatch)
    report = _run_trip_briefing(recorder, uid, trip)

    zeilen = _hint_lines(report.email_plain)
    assert len(zeilen) == 1, (
        "AC-1: Genau EINE Vorfall-Zeile erwartet, gefunden "
        f"{len(zeilen)}: {zeilen!r}\n--- Klartext-Mail ---\n{report.email_plain}"
    )
    zeile = zeilen[0]
    lokal = _local_hhmm(vorfall)
    utc = vorfall.strftime("%H:%M")
    assert lokal in zeile, (
        f"AC-1: Der Zeitpunkt muss in der Briefing-Zeitzone stehen ({lokal}), "
        f"Zeile: {zeile!r}"
    )
    if utc != lokal:
        assert utc not in zeile, (
            f"AC-1: In der Zeile steht die UTC-Uhrzeit {utc} statt der "
            f"Ortszeit {lokal}: {zeile!r}"
        )
    assert "Böen" in zeile, (
        f"AC-1: Die betroffene Wettergroesse (Katalog-Name 'Böen') fehlt: {zeile!r}"
    )
    assert "SMS" in zeile, f"AC-1: Der betroffene Kanal 'SMS' fehlt: {zeile!r}"
    assert "Telegram" not in zeile and "E-Mail" not in zeile, (
        f"AC-1: Nur der SMS-Kanal war betroffen — die Zeile nennt weitere: {zeile!r}"
    )

    # Dieselbe Zusicherung im HTML-Teil derselben Mail.
    html_text = _html_as_text(report.email_html)
    assert _heading() in html_text, "AC-1: Die HTML-Mail traegt keine Ueberschrift."
    assert len(_hint_lines(html_text)) == 1, (
        f"AC-1: Die HTML-Mail muss genau eine Vorfall-Zeile tragen, gefunden "
        f"{_hint_lines(html_text)!r}"
    )
    for angabe in (lokal, "Böen", "SMS"):
        assert angabe in html_text, (
            f"AC-1: {angabe!r} fehlt im HTML-Teil der Briefing-Mail."
        )


# ══════════════════════════════════ AC-2 ══════════════════════════════════


def test_ac2_totalausfall_nennt_alle_betroffenen_kanaele(monkeypatch):
    """AC-2.

    GIVEN eine Alarm-Meldung erreichte KEINEN einzigen Kanal (Eintrag unter
          ``not_delivered``, alle drei Kanaele ``delivery_failed``).
    WHEN  das naechste Briefing erzeugt wird.
    THEN  erscheint sie ebenfalls als Zeile — mit ALLEN betroffenen Kanaelen.
    """
    uid = _uid("ac2")
    trip = _trip(f"trip-ac2-{uuid.uuid4().hex[:6]}")

    jetzt = _jetzt()
    vorfall = jetzt - timedelta(hours=2)
    _seed(uid, entity_id=trip.id, letztes_briefing=jetzt - timedelta(hours=6),
          not_delivered=[_entry(
              entity_id=trip.id, sent_at=vorfall, hazards=("thunderstorm",),
              reason="official_alert", channels_sent=(),
              not_sent=tuple((c, "delivery_failed") for c in ALL_CHANNELS),
          )])

    recorder = _ReportRecorder()
    recorder.install(monkeypatch)
    report = _run_trip_briefing(recorder, uid, trip)

    zeilen = _hint_lines(report.email_plain)
    assert len(zeilen) == 1, (
        f"AC-2: Der Totalausfall muss als genau eine Zeile erscheinen, gefunden "
        f"{zeilen!r}\n--- Klartext-Mail ---\n{report.email_plain}"
    )
    zeile = zeilen[0]
    for kanal in ("E-Mail", "Telegram", "SMS"):
        assert kanal in zeile, (
            f"AC-2: Bei einem Totalausfall muessen ALLE betroffenen Kanaele in "
            f"der Zeile stehen — {kanal!r} fehlt: {zeile!r}"
        )
    assert "Amtliche Warnung" in zeile, (
        f"AC-2: Der Anlass (amtliche Warnung) fehlt in der Zeile: {zeile!r}"
    )


# ══════════════════════════════════ AC-3 ══════════════════════════════════


def test_ac3_alles_zugestellt_erzeugt_keinen_abschnitt(monkeypatch):
    """AC-3.

    GIVEN seit dem letzten Briefing wurde jede Meldung auf jedem
          EINGESCHALTETEN Kanal zugestellt.
    WHEN  das Briefing erzeugt wird.
    THEN  enthaelt es KEINERLEI Hinweis-Abschnitt — auch keine Ueberschrift
          und keine Null-Zeile.
    """
    uid = _uid("ac3")
    trip = _trip(f"trip-ac3-{uuid.uuid4().hex[:6]}")

    jetzt = _jetzt()
    _seed(uid, entity_id=trip.id, letztes_briefing=jetzt - timedelta(hours=6),
          entries=[_entry(
              entity_id=trip.id, sent_at=jetzt - timedelta(hours=2),
              metrics=(("gust", "max"),), reason="forecast_change",
              channels_sent=("email", "sms", "telegram"), not_sent=(),
          )])

    recorder = _ReportRecorder()
    recorder.install(monkeypatch)
    report = _run_trip_briefing(recorder, uid, trip)

    for teil, name in ((report.email_plain, "Klartext"),
                       (_html_as_text(report.email_html), "HTML")):
        assert _heading() not in teil, (
            f"AC-3: Ohne fehlende Zustellung darf im {name}-Teil keine "
            f"Ueberschrift stehen."
        )
        assert _hint_lines(teil) == [], (
            f"AC-3: Ohne fehlende Zustellung darf im {name}-Teil keine Zeile "
            f"stehen, gefunden {_hint_lines(teil)!r}"
        )


def test_ac3_abgeschalteter_kanal_ist_kein_vorfall(monkeypatch):
    """AC-3 (die entscheidende Haelfte — Wortlaut 'auf jedem EINGESCHALTETEN
    Kanal').

    GIVEN ein Nutzer hat nur E-Mail eingeschaltet; die Meldung ging per E-Mail
          raus, und ``channels_not_sent`` fuehrt Telegram und SMS mit dem Grund
          ``channel_disabled`` (genau das schreibt
          ``alert_log._channels_not_sent()`` fuer JEDEN erfolgreichen Alarm
          eines Ein-Kanal-Nutzers).
    WHEN  das Briefing erzeugt wird.
    THEN  erscheint KEIN Hinweis-Abschnitt.

    Ohne diese Abgrenzung stuende der Abschnitt bei jedem Ein-Kanal-Nutzer in
    JEDEM Briefing und meldete abgeschaltete Kanaele als 'nicht angekommen' —
    AC-3 waere strukturell nie erfuellbar.
    """
    uid = _uid("ac3b")
    trip = _trip(f"trip-ac3b-{uuid.uuid4().hex[:6]}")

    jetzt = _jetzt()
    _seed(uid, entity_id=trip.id, letztes_briefing=jetzt - timedelta(hours=6),
          entries=[_entry(
              entity_id=trip.id, sent_at=jetzt - timedelta(hours=2),
              metrics=(("gust", "max"),), reason="forecast_change",
              channels_sent=("email",),
              not_sent=(("telegram", "channel_disabled"), ("sms", "channel_disabled")),
          )])

    recorder = _ReportRecorder()
    recorder.install(monkeypatch)
    report = _run_trip_briefing(recorder, uid, trip)

    assert _heading() not in report.email_plain, (
        "AC-3: Ein vom Nutzer ABGESCHALTETER Kanal ist keine fehlgeschlagene "
        "Zustellung — es darf kein Abschnitt erscheinen.\n"
        f"--- Klartext-Mail ---\n{report.email_plain}"
    )
    assert _hint_lines(report.email_plain) == [], (
        f"AC-3: unerwartete Zeilen: {_hint_lines(report.email_plain)!r}"
    )


# ══════════════════════════════════ AC-4 ══════════════════════════════════


def test_ac4_bereits_ausgewiesener_vorfall_erscheint_nicht_erneut(monkeypatch):
    """AC-4.

    GIVEN eine nicht zugestellte Meldung wurde in einem frueheren Briefing
          bereits ausgewiesen.
    WHEN  das darauffolgende Briefing erzeugt wird.
    THEN  erscheint sie NICHT erneut.

    Zwei ECHTE Briefing-Laeufe hintereinander: der erste schreibt beim
    Anker-Baustein den Briefing-Zeitstempel fort, der zweite liest ihn.
    """
    uid = _uid("ac4")
    trip = _trip(f"trip-ac4-{uuid.uuid4().hex[:6]}")

    jetzt = _jetzt()
    _seed(uid, entity_id=trip.id, letztes_briefing=jetzt - timedelta(hours=6),
          not_delivered=[_entry(
              entity_id=trip.id, sent_at=jetzt - timedelta(hours=2),
              metrics=(("thunder", "max"),), reason="forecast_change",
              channels_sent=(), not_sent=(("sms", "delivery_failed"),),
          )])

    recorder = _ReportRecorder()
    recorder.install(monkeypatch)

    erstes = _run_trip_briefing(recorder, uid, trip)
    assert len(_hint_lines(erstes.email_plain)) == 1, (
        "AC-4 Voraussetzung: das ERSTE Briefing muss den Vorfall ausweisen, "
        f"gefunden {_hint_lines(erstes.email_plain)!r}"
    )

    zweites = _run_trip_briefing(recorder, uid, trip)
    assert _hint_lines(zweites.email_plain) == [], (
        "AC-4: Ein bereits ausgewiesener Vorfall darf im darauffolgenden "
        f"Briefing nicht erneut erscheinen: {_hint_lines(zweites.email_plain)!r}"
    )
    assert _heading() not in zweites.email_plain, (
        "AC-4: Im zweiten Briefing darf auch die Ueberschrift nicht mehr stehen."
    )


# ══════════════════════════════════ AC-5 ══════════════════════════════════


def test_ac5_ein_lauf_mit_zwei_eintraegen_ergibt_eine_zeile(monkeypatch):
    """AC-5 — Entdoppelung (Risiko 1 des Kontexts).

    GIVEN ein einziger Alarm-Lauf hat wegen gleichzeitiger Vorhersage-Aenderung
          und amtlicher Warnung MEHRERE Protokolleintraege erzeugt (drei
          getrennte ``append_entry``-Aufrufe: ``trip_alert.py:278``, ``:877``,
          ``:1150``), die alle niemanden erreichten.
    WHEN  das Briefing erzeugt wird.
    THEN  steht dafuer EINE Zeile, nicht mehrere, und die betroffenen Kanaele
          sind darin zusammengefasst.
    """
    uid = _uid("ac5")
    trip = _trip(f"trip-ac5-{uuid.uuid4().hex[:6]}")

    jetzt = _jetzt()
    lauf = jetzt - timedelta(hours=2)
    _seed(uid, entity_id=trip.id, letztes_briefing=jetzt - timedelta(hours=6),
          not_delivered=[
              _entry(entity_id=trip.id, sent_at=lauf, metrics=(("thunder", "max"),),
                     reason="forecast_change", channels_sent=(),
                     not_sent=(("sms", "delivery_failed"),)),
              _entry(entity_id=trip.id, sent_at=lauf, hazards=("thunderstorm",),
                     reason="official_alert", channels_sent=(),
                     not_sent=(("telegram", "delivery_failed"),)),
          ])

    recorder = _ReportRecorder()
    recorder.install(monkeypatch)
    report = _run_trip_briefing(recorder, uid, trip)

    zeilen = _hint_lines(report.email_plain)
    assert len(zeilen) == 1, (
        "AC-5: Mehrere Protokolleintraege desselben Laufs sind fuer den Nutzer "
        f"EIN Vorfall — erwartet 1 Zeile, gefunden {len(zeilen)}: "
        f"{zeilen!r}\n--- Klartext-Mail ---\n{report.email_plain}"
    )
    zeile = zeilen[0]
    assert "SMS" in zeile and "Telegram" in zeile, (
        "AC-5: Die betroffenen Kanaele beider Eintraege muessen in der EINEN "
        f"Zeile zusammengefasst sein: {zeile!r}"
    )


# ══════════════════════════════════ AC-6 ══════════════════════════════════


def test_ac6_deckelung_fuenf_zeilen_plus_und_drei_weitere(monkeypatch):
    """AC-6.

    GIVEN mehr als fuenf Meldungen haben seit dem letzten Briefing einen Kanal
          nicht erreicht (hier acht, je eine volle Stunde auseinander — also
          ausserhalb jedes Entdoppelungs-Fensters).
    WHEN  das Briefing erzeugt wird.
    THEN  stehen die FUENF JUENGSTEN als Zeilen da, gefolgt von einem Hinweis,
          wie viele weitere es sind.
    """
    from output.renderers.email.undelivered_hint import MAX_UNDELIVERED_LINES

    uid = _uid("ac6")
    trip = _trip(f"trip-ac6-{uuid.uuid4().hex[:6]}")

    jetzt = _jetzt()
    zeitpunkte = [jetzt - timedelta(hours=n) for n in range(1, 9)]
    _seed(uid, entity_id=trip.id, letztes_briefing=jetzt - timedelta(hours=24),
          not_delivered=[
              _entry(entity_id=trip.id, sent_at=t, metrics=(("thunder", "max"),),
                     reason="forecast_change", channels_sent=(),
                     not_sent=(("sms", "delivery_failed"),))
              for t in zeitpunkte
          ])

    recorder = _ReportRecorder()
    recorder.install(monkeypatch)
    report = _run_trip_briefing(recorder, uid, trip)

    zeilen = _hint_lines(report.email_plain)
    assert MAX_UNDELIVERED_LINES == 5, (
        f"Die Deckelung ist auf 5 Zeilen freigegeben, ist {MAX_UNDELIVERED_LINES}"
    )
    assert len(zeilen) == 5, (
        f"AC-6: Bei acht Vorfaellen erwartet 5 Zeilen, gefunden {len(zeilen)}: "
        f"{zeilen!r}\n--- Klartext-Mail ---\n{report.email_plain}"
    )
    gezeigt = "\n".join(zeilen)
    for t in zeitpunkte[:5]:
        assert _local_hhmm(t) in gezeigt, (
            f"AC-6: Der Vorfall von {_local_hhmm(t)} gehoert zu den fuenf "
            f"juengsten und fehlt: {zeilen!r}"
        )
    for t in zeitpunkte[5:]:
        assert _local_hhmm(t) not in gezeigt, (
            f"AC-6: Der Vorfall von {_local_hhmm(t)} ist aelter als die fuenf "
            f"juengsten und darf keine eigene Zeile haben: {zeilen!r}"
        )
    assert re.search(r"und\s+3\s+weitere", report.email_plain), (
        "AC-6: Der Hinweis 'und 3 weitere' fehlt.\n"
        f"--- Klartext-Mail ---\n{report.email_plain}"
    )


# ══════════════════════════════════ AC-7 ══════════════════════════════════


def test_ac7_erstes_briefing_ohne_anker_zeigt_keine_altlasten(monkeypatch):
    """AC-7.

    GIVEN ein Nutzer bekommt zum ersten Mal ein Briefing, nachdem diese
          Funktion ausgeliefert wurde; sein Protokoll enthaelt alte nicht
          zugestellte Meldungen und es gibt KEINEN gespeicherten
          Briefing-Zeitpunkt.
    WHEN  das Briefing erzeugt wird.
    THEN  wird KEINE dieser Alt-Meldungen ausgewiesen (Rueckblick beginnt ab
          jetzt, nicht ueber die unbestimmte Vergangenheit).
    """
    from services.alert_briefing_anchor import last_briefing_at

    uid = _uid("ac7")
    trip = _trip(f"trip-ac7-{uuid.uuid4().hex[:6]}")

    jetzt = _jetzt()
    _seed(uid, entity_id=trip.id, not_delivered=[
        _entry(entity_id=trip.id, sent_at=jetzt - timedelta(days=n),
               metrics=(("thunder", "max"),), reason="forecast_change",
               channels_sent=(), not_sent=(("sms", "delivery_failed"),))
        for n in (2, 3, 5)
    ])
    assert last_briefing_at(user_id=uid, entity_id=trip.id, entity_type="trip") is None, (
        "AC-7 Voraussetzung: es darf noch kein Briefing-Zeitstempel existieren"
    )

    recorder = _ReportRecorder()
    recorder.install(monkeypatch)
    report = _run_trip_briefing(recorder, uid, trip)

    assert _hint_lines(report.email_plain) == [], (
        "AC-7: Beim ersten Briefing nach der Auslieferung darf keine "
        f"Alt-Meldung erscheinen: {_hint_lines(report.email_plain)!r}"
    )
    assert _heading() not in report.email_plain, (
        "AC-7: Auch die Ueberschrift darf nicht erscheinen."
    )
    assert last_briefing_at(user_id=uid, entity_id=trip.id, entity_type="trip") is not None, (
        "AC-7: Nach dem Briefing muss der Zeitstempel gesetzt sein — sonst "
        "faengt der Rueckblick nie an zu laufen."
    )


# ══════════════════════════════════ AC-8 ══════════════════════════════════


def test_ac8_selbstabruf_schneidet_den_zeitraum_nicht_ab(monkeypatch):
    """AC-8.

    GIVEN ein Nutzer ruft ein Briefing selbst ab (``on_demand=True``, kein
          geplanter Versand).
    WHEN  er danach das naechste GEPLANTE Briefing bekommt.
    THEN  sind die nicht zugestellten Meldungen dort IMMER NOCH ausgewiesen —
          der Selbstabruf hat den Zeitraum nicht abgeschnitten. Im Selbstabruf
          selbst stehen sie ebenfalls.
    """
    uid = _uid("ac8")
    trip = _trip(f"trip-ac8-{uuid.uuid4().hex[:6]}")

    jetzt = _jetzt()
    _seed(uid, entity_id=trip.id, letztes_briefing=jetzt - timedelta(hours=6),
          not_delivered=[_entry(
              entity_id=trip.id, sent_at=jetzt - timedelta(hours=2),
              metrics=(("thunder", "max"),), reason="forecast_change",
              channels_sent=(), not_sent=(("sms", "delivery_failed"),),
          )])

    recorder = _ReportRecorder()
    recorder.install(monkeypatch)

    abruf = _run_trip_briefing(recorder, uid, trip, on_demand=True)
    assert len(_hint_lines(abruf.email_plain)) == 1, (
        "AC-8: Auch der Selbstabruf weist den Vorfall aus, gefunden "
        f"{_hint_lines(abruf.email_plain)!r}"
    )

    geplant = _run_trip_briefing(recorder, uid, trip, on_demand=False)
    assert len(_hint_lines(geplant.email_plain)) == 1, (
        "AC-8: Der Selbstabruf darf den Zeitraum NICHT abschneiden — im "
        "darauffolgenden geplanten Briefing muss der Vorfall immer noch "
        f"stehen, gefunden {_hint_lines(geplant.email_plain)!r}"
    )


# ══════════════════════════════════ AC-9 ══════════════════════════════════


def test_ac9_abschnitt_erscheint_in_full_und_compact(monkeypatch):
    """AC-9.

    GIVEN es liegen nicht zugestellte Meldungen vor.
    WHEN  ein Briefing im Format ``full`` UND eines im Format ``compact``
          erzeugt wird.
    THEN  enthalten BEIDE den Abschnitt.
    """
    jetzt = _jetzt()
    ergebnis = {}
    for fmt in ("full", "compact"):
        uid = _uid(f"ac9-{fmt}")
        trip = _trip(f"trip-ac9-{fmt}-{uuid.uuid4().hex[:6]}", email_format=fmt)
        _seed(uid, entity_id=trip.id, letztes_briefing=jetzt - timedelta(hours=6),
              not_delivered=[_entry(
                  entity_id=trip.id, sent_at=jetzt - timedelta(hours=2),
                  metrics=(("thunder", "max"),), reason="forecast_change",
                  channels_sent=(), not_sent=(("sms", "delivery_failed"),),
              )])
        recorder = _ReportRecorder()
        recorder.install(monkeypatch)
        ergebnis[fmt] = _run_trip_briefing(recorder, uid, trip)

    voll = ergebnis["full"]
    kompakt = ergebnis["compact"]

    assert len(_hint_lines(voll.email_plain)) == 1, (
        f"AC-9 (full): Abschnitt fehlt.\n{voll.email_plain}"
    )
    assert len(_hint_lines(_html_as_text(voll.email_html))) == 1, (
        "AC-9 (full/HTML): Abschnitt fehlt im HTML-Teil."
    )
    assert kompakt.email_html == "", (
        "Voraussetzung: das compact-Format erzeugt kein HTML"
    )
    assert len(_hint_lines(kompakt.email_plain)) == 1, (
        "AC-9 (compact): Der Abschnitt MUSS auch im Kurzformat der Mail "
        f"stehen.\n--- compact ---\n{kompakt.email_plain}"
    )
    assert _heading() in kompakt.email_plain, (
        "AC-9 (compact): Die Ueberschrift fehlt."
    )
    assert kompakt.email_plain.isascii(), (
        "AC-9 (compact): Das Kurzformat muss reines ASCII bleiben — der neue "
        "Abschnitt bricht das."
    )


# ══════════════════════════════════ AC-10 ═════════════════════════════════


def test_ac10_kurznachricht_zeichengleich_mit_und_ohne_vorfaelle(monkeypatch):
    """AC-10.

    GIVEN es liegen nicht zugestellte Meldungen vor.
    WHEN  die Kurznachrichten fuer Telegram und SMS erzeugt werden.
    THEN  sind diese Zeichen fuer Zeichen identisch mit denen ohne solche
          Meldungen (PO: die Kurznachricht bleibt unberuehrt).

    Der Test ist bewusst NICHT leer-laufend: er stellt zuerst fest, dass der
    Abschnitt in der MAIL desselben Laufs tatsaechlich erscheint — sonst
    verglichen wir zwei Male dasselbe Nichts.
    """
    jetzt = _jetzt()

    uid_mit = _uid("ac10-mit")
    trip_mit = _trip(f"trip-ac10-{uuid.uuid4().hex[:6]}")
    _seed(uid_mit, entity_id=trip_mit.id, letztes_briefing=jetzt - timedelta(hours=6),
          not_delivered=[_entry(
              entity_id=trip_mit.id, sent_at=jetzt - timedelta(hours=2),
              metrics=(("thunder", "max"),), reason="forecast_change",
              channels_sent=(), not_sent=(("sms", "delivery_failed"),),
          )])
    rec_mit = _ReportRecorder()
    rec_mit.install(monkeypatch)
    mit = _run_trip_briefing(rec_mit, uid_mit, trip_mit)

    uid_ohne = _uid("ac10-ohne")
    trip_ohne = _trip(f"trip-ac10-{uuid.uuid4().hex[:6]}")
    _write_log(uid_ohne)
    rec_ohne = _ReportRecorder()
    rec_ohne.install(monkeypatch)
    ohne = _run_trip_briefing(rec_ohne, uid_ohne, trip_ohne)

    assert len(_hint_lines(mit.email_plain)) == 1, (
        "AC-10 Voraussetzung: der Lauf MIT Vorfaellen muss den Abschnitt in "
        f"der Mail zeigen, sonst prueft der Vergleich nichts.\n{mit.email_plain}"
    )
    assert _hint_lines(ohne.email_plain) == [], (
        "AC-10 Voraussetzung: der Lauf OHNE Vorfaelle darf keinen Abschnitt zeigen."
    )

    assert mit.sms_text == ohne.sms_text, (
        "AC-10: Der SMS-Text muss Zeichen fuer Zeichen identisch bleiben.\n"
        f"mit:  {mit.sms_text!r}\nohne: {ohne.sms_text!r}"
    )
    assert mit.telegram_bubbles == ohne.telegram_bubbles, (
        "AC-10: Die Telegram-Kurzform muss Zeichen fuer Zeichen identisch "
        f"bleiben.\nmit:  {mit.telegram_bubbles!r}\nohne: {ohne.telegram_bubbles!r}"
    )


# ══════════════════════════════════ AC-11 ═════════════════════════════════


def _compare_preset(uid: str, preset_id: str) -> dict:
    return {
        "id": preset_id, "name": "Vergleich S3b-1", "user_id": uid,
        "location_ids": ["loc-a", "loc-b"], "schedule": "daily", "weekday": 4,
        "profil": "ALLGEMEIN", "hour_from": 9, "hour_to": 16,
        "empfaenger": ["dummy@example.com"], "created_at": "2026-08-01T00:00:00Z",
    }


def _setup_compare_locations(uid: str) -> None:
    from app.user import SavedLocation

    save_location(SavedLocation(id="loc-a", name="Vergleichsort", lat=LAT, lon=LON,
                                elevation_m=1000), user_id=uid)
    save_location(SavedLocation(id="loc-b", name="Zweitort", lat=LAT + 0.2, lon=LON + 0.2,
                                elevation_m=900), user_id=uid)


def _run_compare_briefing(uid: str, preset: dict, data_root, *, on_demand: bool = False) -> str:
    """ECHTER Ortsvergleichs-Versandpfad; liefert den HTML-Body der Mail."""
    from services.scheduler_dispatch_service import send_one_compare_preset

    mails: list = []
    send_one_compare_preset(
        preset, settings_email_only(), uid, data_root=str(data_root),
        mail_sink=lambda subject, body: mails.append((subject, body)),
        on_demand=on_demand,
    )
    assert mails, "Voraussetzung: die Vergleichs-Mail wurde nicht erzeugt"
    return mails[-1][1]


def test_ac11_ortsvergleich_zeigt_vorfall_unter_der_preset_kennung(tmp_path):
    """AC-11 — deckt den gemessenen KENNUNGS-FALLSTRICK ab.

    GIVEN ein Ortsvergleich hat eine Meldung, die einen Kanal nicht erreicht
          hat. Das Protokoll schreibt sie unter ``entity_id = preset_id``
          (``compare_alert.py:193``, ``compare_official_alert.py:151``) —
          NICHT unter ``f"{preset_id}:{loc.id}"``, das nur der Anker-Baustein
          bekommt (``scheduler_dispatch_service.py:413``).
    WHEN  das Ortsvergleichs-Briefing erzeugt wird.
    THEN  erscheint der Abschnitt dort mit derselben Zeilenform wie beim Trip
          — und ist NICHT leer.

    Wer den Briefing-Zeitstempel unter den Anker-Kennungen ablegt, findet beim
    Lesen nie einen Treffer: ``last_briefing_at(preset_id)`` bliebe ``None``,
    der Rueckblick begaenne 'ab jetzt' und der Vorfall verschwaende. Genau das
    macht dieser Test rot.
    """
    uid = _uid("ac11")
    preset_id = f"cp-ac11-{uuid.uuid4().hex[:6]}"
    _setup_compare_locations(uid)

    jetzt = _jetzt()
    _seed(uid, entity_id=preset_id, entity_type="compare",
          letztes_briefing=jetzt - timedelta(hours=6),
          not_delivered=[_entry(
              entity_id=preset_id, entity_type="compare",
              sent_at=jetzt - timedelta(hours=2), metrics=(("thunder", "max"),),
              reason="forecast_change", channels_sent=(),
              not_sent=(("sms", "delivery_failed"),),
          )])

    html = _run_compare_briefing(uid, _compare_preset(uid, preset_id), tmp_path)
    text = _html_as_text(html)

    assert _heading() in text, (
        "AC-11: Die Ortsvergleichs-Mail traegt keine Hinweis-Ueberschrift."
    )
    zeilen = _hint_lines(text)
    assert len(zeilen) == 1, (
        "AC-11: Der Abschnitt muss im Ortsvergleich mit derselben Zeilenform "
        f"erscheinen und darf NICHT leer sein, gefunden {zeilen!r}"
    )
    assert "Gewitter" in zeilen[0] and "SMS" in zeilen[0], (
        f"AC-11: Anlass und Kanal fehlen in der Zeile: {zeilen[0]!r}"
    )


def test_ac11_ortsvergleich_schreibt_zeitstempel_unter_die_protokoll_kennung(tmp_path):
    """AC-11 (die andere Haelfte des Fallstricks — die SCHREIBSEITE).

    GIVEN ein Ortsvergleichs-Briefing laeuft regulaer durch.
    WHEN  danach der Briefing-Zeitstempel gesucht wird.
    THEN  steht er unter der PROTOKOLL-Kennung (``preset_id`` / ``compare``),
          nicht unter den Anker-Kennungen ``f"{preset_id}:{loc.id}"``.

    Ohne diesen Test bliebe die Verwechslung unbemerkt: der Hinweis waere beim
    Ortsvergleich dauerhaft leer, und kein Test wuerde rot.
    """
    from services.alert_briefing_anchor import last_briefing_at

    uid = _uid("ac11b")
    preset_id = f"cp-ac11b-{uuid.uuid4().hex[:6]}"
    _setup_compare_locations(uid)
    _write_log(uid)

    assert last_briefing_at(user_id=uid, entity_id=preset_id, entity_type="compare") is None, (
        "Voraussetzung: noch kein Briefing-Zeitstempel"
    )
    _run_compare_briefing(uid, _compare_preset(uid, preset_id), tmp_path)

    unter_protokoll = last_briefing_at(user_id=uid, entity_id=preset_id, entity_type="compare")
    assert unter_protokoll is not None, (
        "AC-11: Nach dem Ortsvergleichs-Briefing MUSS ein Zeitstempel unter der "
        f"Protokoll-Kennung {preset_id!r} stehen. Liegt er unter den "
        f"Anker-Kennungen '{preset_id}:loc-a'/'{preset_id}:loc-b', findet die "
        "Lesefunktion nie einen Treffer und der Hinweis bleibt dauerhaft leer."
    )
    for loc_id in ("loc-a", "loc-b"):
        assert last_briefing_at(
            user_id=uid, entity_id=f"{preset_id}:{loc_id}", entity_type="compare",
        ) is None, (
            f"AC-11: Unter der Anker-Kennung '{preset_id}:{loc_id}' darf KEIN "
            "Briefing-Zeitstempel liegen — das ist genau die Verwechslung."
        )


# ══════════════════════════════════ AC-17 ═════════════════════════════════


class _CompareMailRecorder:
    """DELEGIERENDER Beobachter auf ``render_compare_email``.

    Kein Mock: die echte Funktion laeuft unveraendert, es wird nur
    festgehalten, WAS sie zurueckgegeben hat (Muster ``_ReportRecorder``).

    Noetig, weil der ``mail_sink`` ausschliesslich den HTML-Body bekommt
    (``notification_service.send_compare_report``); der Klartext-Teil geht als
    ``plain_text_body`` an den echten Transport und waere aus dem Test sonst
    gar nicht sichtbar. Genau dieser blinde Fleck liess in #1366 den Schalter
    ``hourly_enabled`` im Klartext monatelang wirkungslos — der
    Pflicht-Validator ``email_spec_validator`` liest nur HTML.
    """

    def __init__(self) -> None:
        self.bodies: list[tuple[str, str]] = []

    def install(self, monkeypatch) -> None:
        import output.renderers.comparison as _cmp

        original = _cmp.render_compare_email
        recorder = self

        def _recording_render_compare_email(*args, **kwargs):
            html_body, text_body = original(*args, **kwargs)
            recorder.bodies.append((html_body, text_body))
            return html_body, text_body

        # `scheduler_dispatch_service` importiert die Funktion erst IM Aufruf
        # (`from output.renderers.comparison import render_compare_email`),
        # deshalb wirkt das Setzen am Ursprungsmodul.
        monkeypatch.setattr(_cmp, "render_compare_email", _recording_render_compare_email)


def _run_compare_briefing_texts(recorder, uid, preset, data_root) -> tuple[str, str]:
    _run_compare_briefing(uid, preset, data_root)
    assert recorder.bodies, "Voraussetzung: die Vergleichs-Mail wurde nicht gebaut"
    return recorder.bodies[-1]


def test_ac17_ortsvergleich_klartext_zeigt_den_abschnitt_ebenfalls(tmp_path, monkeypatch):
    """AC-17 (Spec v1.2).

    GIVEN ein Ortsvergleich hat eine Meldung, die einen Kanal nicht erreicht
          hat.
    WHEN  das Ortsvergleichs-Briefing erzeugt wird.
    THEN  traegt auch der KLARTEXT-Teil der Mail den Abschnitt — dieselbe
          Zeilenform wie HTML und Trip.

    Beide Fassungen werden zugestellt (`send_compare_report(..., html_body,
    plain_text_body=text_body)`); "nur E-Mail" meint die Mail, nicht ihre
    HTML-Haelfte. Ohne diesen Test bliebe der Klartext-Teil des Ortsvergleichs
    schlechter gestellt als der des Trips (`email/plain.py`) — und kein
    Pflicht-Validator wuerde es merken (#1366).
    """
    uid = _uid("ac17")
    preset_id = f"cp-ac17-{uuid.uuid4().hex[:6]}"
    _setup_compare_locations(uid)

    jetzt = _jetzt()
    _seed(uid, entity_id=preset_id, entity_type="compare",
          letztes_briefing=jetzt - timedelta(hours=6),
          not_delivered=[_entry(
              entity_id=preset_id, entity_type="compare",
              sent_at=jetzt - timedelta(hours=2), metrics=(("thunder", "max"),),
              reason="forecast_change", channels_sent=(),
              not_sent=(("sms", "delivery_failed"),),
          )])

    recorder = _CompareMailRecorder()
    recorder.install(monkeypatch)
    html, text = _run_compare_briefing_texts(
        recorder, uid, _compare_preset(uid, preset_id), tmp_path,
    )

    assert _heading() in text, (
        "AC-17: Der Klartext-Teil der Vergleichs-Mail traegt keine "
        f"Hinweis-Ueberschrift.\n--- Klartext ---\n{text}"
    )
    zeilen = _hint_lines(text)
    assert len(zeilen) == 1, (
        "AC-17: Der Klartext-Teil muss genau eine Vorfall-Zeile tragen, "
        f"gefunden {zeilen!r}\n--- Klartext ---\n{text}"
    )
    assert "Gewitter" in zeilen[0] and "SMS" in zeilen[0], (
        f"AC-17: Anlass und Kanal fehlen in der Klartext-Zeile: {zeilen[0]!r}"
    )
    # Nicht-Leerlauf: derselbe Lauf zeigt den Abschnitt auch im HTML-Teil —
    # die beiden Fassungen laufen nicht auseinander.
    assert len(_hint_lines(_html_as_text(html))) == 1, (
        "AC-17: HTML- und Klartext-Teil derselben Mail muessen dieselbe "
        "Anzahl Vorfall-Zeilen tragen."
    )


def test_ac17_ortsvergleich_klartext_ohne_vorfaelle_ohne_abschnitt(tmp_path, monkeypatch):
    """AC-17 (Leerfall, wie AC-3).

    GIVEN dem Ortsvergleich fehlt nichts.
    WHEN  das Briefing erzeugt wird.
    THEN  steht im Klartext-Teil KEIN Abschnitt — auch keine Ueberschrift.
    """
    uid = _uid("ac17b")
    preset_id = f"cp-ac17b-{uuid.uuid4().hex[:6]}"
    _setup_compare_locations(uid)
    _write_log(uid)

    recorder = _CompareMailRecorder()
    recorder.install(monkeypatch)
    _html_body, text = _run_compare_briefing_texts(
        recorder, uid, _compare_preset(uid, preset_id), tmp_path,
    )

    assert _heading() not in text, (
        "AC-17: Ohne fehlende Zustellung darf im Klartext-Teil keine "
        f"Ueberschrift stehen.\n--- Klartext ---\n{text}"
    )
    assert _hint_lines(text) == [], (
        f"AC-17: unerwartete Zeilen im Klartext-Teil: {_hint_lines(text)!r}"
    )


# ══════════════════════════════════ AC-12 ═════════════════════════════════


def test_ac12_zwei_nutzer_sehen_nur_die_eigenen_vorfaelle(monkeypatch):
    """AC-12 — Mandantentrennung, Kreuzpruefung in BEIDE Richtungen.

    GIVEN zwei verschiedene Nutzer haben je eigene nicht zugestellte Meldungen
          (unterscheidbar an der Wettergroesse), unter derselben Trip-Kennung —
          nur die ``user_id`` trennt sie.
    WHEN  das Briefing des einen erzeugt wird.
    THEN  enthaelt es ausschliesslich dessen eigene Meldungen.
    """
    jetzt = _jetzt()
    alice, bob = _uid("alice"), _uid("bob")
    trip_id = "trip-ac12-geteilte-kennung"
    marker = {alice: (("thunder", "max"), "Gewitter", "Böen"),
              bob: (("gust", "max"), "Böen", "Gewitter")}

    for uid, (metrik, _eigen, _fremd) in marker.items():
        _seed(uid, entity_id=trip_id, letztes_briefing=jetzt - timedelta(hours=6),
              not_delivered=[_entry(
                  entity_id=trip_id, sent_at=jetzt - timedelta(hours=2),
                  metrics=(metrik,), reason="forecast_change", channels_sent=(),
                  not_sent=(("sms", "delivery_failed"),),
              )])

    for uid, (_metrik, eigen, fremd) in marker.items():
        trip = _trip(trip_id)
        recorder = _ReportRecorder()
        recorder.install(monkeypatch)
        report = _run_trip_briefing(recorder, uid, trip)
        zeilen = _hint_lines(report.email_plain)
        assert len(zeilen) == 1, (
            f"AC-12: {uid} muss genau seinen eigenen Vorfall sehen, gefunden "
            f"{zeilen!r}"
        )
        assert eigen in zeilen[0], (
            f"AC-12: Der eigene Vorfall ({eigen}) fehlt bei {uid}: {zeilen[0]!r}"
        )
        assert fremd not in zeilen[0], (
            f"AC-12: Der Vorfall des ANDEREN Nutzers ({fremd}) steht im Briefing "
            f"von {uid} — Cross-User-Datenleck: {zeilen[0]!r}"
        )


# ══════════════════════════════════ AC-13 ═════════════════════════════════


def test_ac13_briefing_veraendert_das_protokoll_um_keine_zahl(monkeypatch):
    """AC-13 — Zusicherung D4 aus #1459.

    GIVEN ein Protokoll enthaelt nicht zugestellte Meldungen.
    WHEN  ein Briefing erzeugt wird (Cockpit-Kachel und Archiv-Statistik lesen
          ueber ``internal/store/log.go`` GENAU den Schluessel ``entries``).
    THEN  stehen ``entries`` UND ``not_delivered`` danach Feld fuer Feld
          unveraendert da — und die Datei wurde ueberhaupt NICHT angefasst.

    Der Test ist nicht leer-laufend: er stellt zuerst fest, dass der Abschnitt
    tatsaechlich erscheint (sonst bewiese die Unveraendertheit nichts).

    Warum zusaetzlich die Datei-Metadaten (Adversary-Befund F002): reine
    Wertgleichheit uebersieht einen INHALTSGLEICHEN Rueckschreibvorgang. "Lesen
    schreibt nicht" ist aber die staerkere und die eigentlich gemeinte
    Zusicherung — ein Rueckschreiben waere eine echte Kollisionsgefahr, wenn
    parallel ein Alarm-Lauf schreibt (`append_entry()` macht Read-Modify-Write
    ueber die VOLLE Datei; ein gleichzeitiger Rueckschreiber verloere dessen
    frischen Eintrag).

    Die Aenderungszeit wird vorher bewusst weit in die Vergangenheit gesetzt:
    damit haengt der Nachweis nicht an der Zeitaufloesung des Dateisystems —
    jeder Schreibvorgang, auch ein inhaltsgleicher, zieht sie auf "jetzt".
    """
    uid = _uid("ac13")
    trip = _trip(f"trip-ac13-{uuid.uuid4().hex[:6]}")
    jetzt = _jetzt()
    _seed(
        uid, entity_id=trip.id, letztes_briefing=jetzt - timedelta(hours=6),
        entries=[_entry(entity_id=trip.id, sent_at=jetzt - timedelta(hours=3),
                        metrics=(("gust", "max"),), reason="forecast_change",
                        channels_sent=("email",),
                        not_sent=(("sms", "delivery_failed"),))],
        not_delivered=[_entry(entity_id=trip.id, sent_at=jetzt - timedelta(hours=2),
                              metrics=(("thunder", "max"),), reason="forecast_change",
                              channels_sent=(),
                              not_sent=(("sms", "delivery_failed"),))],
    )
    vorher = _read_log(uid)
    log_path = get_data_dir(uid) / "alert_log.json"
    rohbytes_vorher = log_path.read_bytes()
    alt_ns = int((jetzt - timedelta(days=1)).timestamp()) * 1_000_000_000
    os.utime(log_path, ns=(alt_ns, alt_ns))

    recorder = _ReportRecorder()
    recorder.install(monkeypatch)
    report = _run_trip_briefing(recorder, uid, trip)
    assert _hint_lines(report.email_plain), (
        "AC-13 Voraussetzung: der Abschnitt muss erscheinen, sonst prueft die "
        "Unveraendertheit nichts."
    )

    assert log_path.stat().st_mtime_ns == alt_ns, (
        "AC-13/D4: Die Protokolldatei wurde beim Briefing GESCHRIEBEN — die "
        "Aenderungszeit hat sich bewegt. Auch ein inhaltsgleicher "
        "Rueckschreibvorgang ist verboten: `append_entry()` arbeitet per "
        "Read-Modify-Write ueber die volle Datei, ein gleichzeitiger Alarm-Lauf "
        "verloere seinen frischen Eintrag."
    )
    assert log_path.read_bytes() == rohbytes_vorher, (
        "AC-13/D4: Die Protokolldatei ist Byte fuer Byte nicht mehr dieselbe."
    )

    nachher = _read_log(uid)
    assert nachher["entries"] == vorher["entries"], (
        "AC-13/D4: Der Schluessel `entries` (Cockpit-Kachel und Archiv-"
        "Statistik) darf sich durch das Briefing um KEINE Zahl aendern.\n"
        f"vorher:  {vorher['entries']!r}\nnachher: {nachher['entries']!r}"
    )
    assert nachher["not_delivered"] == vorher["not_delivered"], (
        "AC-13/D4: Auch `not_delivered` wird nur gelesen, nie umgeschrieben.\n"
        f"vorher:  {vorher['not_delivered']!r}\nnachher: {nachher['not_delivered']!r}"
    )


# ══════════════════════════════════ AC-14 ═════════════════════════════════


def test_ac14_kaputte_protokolldatei_laesst_das_briefing_vollstaendig(monkeypatch):
    """AC-14 — Fail-soft wie die Schreibseite.

    GIVEN die Protokolldatei ist beschaedigt (kein gueltiges JSON).
    WHEN  ein Briefing erzeugt wird.
    THEN  geht das Briefing vollstaendig und ohne Fehler raus, nur ohne den
          Abschnitt.

    Die Vergleichsgroesse ist ein Lauf mit INTAKTER, leerer Protokolldatei:
    beide Mails muessen dieselben uebrigen Abschnitte tragen (Uhrzeiten
    herausgerechnet, s. ``_ohne_uhrzeiten``).
    """
    uid_kaputt = _uid("ac14-kaputt")
    trip_kaputt = _trip("trip-ac14-vergleichbar")
    path = get_data_dir(uid_kaputt) / "alert_log.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{ das ist kein JSON ][")

    rec_kaputt = _ReportRecorder()
    rec_kaputt.install(monkeypatch)
    kaputt = _run_trip_briefing(rec_kaputt, uid_kaputt, trip_kaputt)

    uid_heil = _uid("ac14-heil")
    trip_heil = _trip("trip-ac14-vergleichbar")
    _write_log(uid_heil)
    rec_heil = _ReportRecorder()
    rec_heil.install(monkeypatch)
    heil = _run_trip_briefing(rec_heil, uid_heil, trip_heil)

    assert _hint_lines(kaputt.email_plain) == [], (
        "AC-14: Bei kaputter Protokolldatei darf kein Abschnitt erscheinen."
    )
    assert _heading() not in kaputt.email_plain
    assert _ohne_uhrzeiten(kaputt.email_plain) == _ohne_uhrzeiten(heil.email_plain), (
        "AC-14: Das Briefing muss bei kaputter Protokolldatei VOLLSTAENDIG "
        "rausgehen — der Klartext-Teil unterscheidet sich vom Lauf mit "
        "intakter Datei."
    )
    assert _ohne_uhrzeiten(kaputt.email_html) == _ohne_uhrzeiten(heil.email_html), (
        "AC-14: Auch der HTML-Teil muss vollstaendig bleiben."
    )


def test_ac14_fehlende_protokolldatei_laesst_das_briefing_vollstaendig(monkeypatch):
    """AC-14 (zweite Haelfte): die Protokolldatei FEHLT ganz (Neu-Nutzer).

    Zugleich der Nicht-Leerlauf-Nachweis fuer den Test darueber: derselbe
    Aufbau MIT einem Vorfall zeigt den Abschnitt sehr wohl.
    """
    uid = _uid("ac14b")
    trip = _trip(f"trip-ac14b-{uuid.uuid4().hex[:6]}")
    assert not (get_data_dir(uid) / "alert_log.json").exists(), (
        "Voraussetzung: die Protokolldatei darf nicht existieren"
    )
    rec = _ReportRecorder()
    rec.install(monkeypatch)
    ohne_datei = _run_trip_briefing(rec, uid, trip)
    assert _heading() not in ohne_datei.email_plain, (
        "AC-14: Ohne Protokolldatei darf kein Abschnitt erscheinen."
    )

    uid2 = _uid("ac14c")
    trip2 = _trip(f"trip-ac14c-{uuid.uuid4().hex[:6]}")
    jetzt = _jetzt()
    _seed(uid2, entity_id=trip2.id, letztes_briefing=jetzt - timedelta(hours=6),
          not_delivered=[_entry(
              entity_id=trip2.id, sent_at=jetzt - timedelta(hours=2),
              metrics=(("thunder", "max"),), reason="forecast_change",
              channels_sent=(), not_sent=(("sms", "delivery_failed"),),
          )])
    rec2 = _ReportRecorder()
    rec2.install(monkeypatch)
    mit_vorfall = _run_trip_briefing(rec2, uid2, trip2)
    assert _heading() in mit_vorfall.email_plain, (
        "AC-14 (Nicht-Leerlauf): derselbe Aufbau MIT Vorfall muss den Abschnitt "
        "sehr wohl zeigen — sonst prueft die Abwesenheits-Zusicherung nichts."
    )


# ══════════════════════════════════ AC-15 ═════════════════════════════════


def test_ac15_ordinale_groesse_erscheint_als_wort_ohne_zahl(monkeypatch):
    """AC-15 — ordinale Groessen nie roh (#1503/#1474).

    GIVEN eine nicht zugestellte Meldung betraf das Gewitter-Niveau
          (Register-Paar ``("thunder", "max")``, Einstufung ``severity="MAJOR"``,
          ``changes_count=3``).
    WHEN  die Zeile erzeugt wird.
    THEN  steht dort die Bezeichnung in WORTEN, nie eine nackte Zahl.

    Bei ordinalen Groessen ist eine Zahl bedeutungslos bis irrefuehrend — die
    Zeile darf ausser dem Zeitstempel keine Ziffer tragen.
    """
    uid = _uid("ac15")
    trip = _trip(f"trip-ac15-{uuid.uuid4().hex[:6]}")
    jetzt = _jetzt()
    vorfall = jetzt - timedelta(hours=2)
    _seed(uid, entity_id=trip.id, letztes_briefing=jetzt - timedelta(hours=6),
          not_delivered=[_entry(
              entity_id=trip.id, sent_at=vorfall, metrics=(("thunder", "max"),),
              reason="forecast_change", severity="MAJOR", changes_count=3,
              channels_sent=(), not_sent=(("sms", "delivery_failed"),),
          )])

    recorder = _ReportRecorder()
    recorder.install(monkeypatch)
    report = _run_trip_briefing(recorder, uid, trip)

    zeilen = _hint_lines(report.email_plain)
    assert len(zeilen) == 1, f"AC-15: erwartet 1 Zeile, gefunden {zeilen!r}"
    zeile = zeilen[0]
    assert "Gewitter" in zeile, (
        f"AC-15: Die Bezeichnung in Worten ('Gewitter') fehlt: {zeile!r}"
    )
    # Zeitstempel-Ziffern herausnehmen, dann darf keine Ziffer uebrig bleiben.
    ohne_zeit = re.sub(r"\d{1,2}[.:]\d{2}\.?|\d{1,2}\.\d{1,2}\.", "", zeile)
    assert not re.search(r"\d", ohne_zeit), (
        "AC-15: Ausser dem Zeitstempel darf in der Zeile keine nackte Zahl "
        f"stehen (ordinale Groesse) — uebrig: {ohne_zeit!r}, Zeile: {zeile!r}"
    )


# ══════════════════════════════════ AC-16 ═════════════════════════════════


def test_ac16_alarmversand_bleibt_kanal_und_zahlgleich(monkeypatch):
    """AC-16.

    GIVEN beliebige Alarm-Lagen.
    WHEN  ein kompletter Alarm- und Briefing-Lauf durchlaeuft.
    THEN  wird KEIN Alarm anders verschickt als vor dieser Aenderung — gleiche
          Kanaele, gleiche Anzahl.

    Umgesetzt als A/B im selben Lauf: derselbe Alarm fuer zwei Nutzer, einer
    mit vorbelastetem Protokoll (dessen Briefing den Abschnitt nachweislich
    zeigt), einer mit leerem. Versandzahl, Kanaele und Mail-Inhalt des ALARMS
    muessen identisch sein — der Briefing-Hinweis darf in den Alarm-Pfad nicht
    hineinlecken.
    """
    from services.trip_alert import TripAlertService

    jetzt = _jetzt()
    trip_id = "trip-ac16-geteilte-kennung"

    uid_vorbelastet = _uid("ac16-mit")
    _seed(uid_vorbelastet, entity_id=trip_id,
          letztes_briefing=jetzt - timedelta(hours=6),
          not_delivered=[_entry(
              entity_id=trip_id, sent_at=jetzt - timedelta(hours=2),
              metrics=(("thunder", "max"),), reason="forecast_change",
              channels_sent=(), not_sent=(("sms", "delivery_failed"),),
          )])

    uid_leer = _uid("ac16-ohne")
    _write_log(uid_leer)

    # Nicht-Leerlauf-Nachweis: das Briefing des vorbelasteten Nutzers zeigt
    # den Abschnitt tatsaechlich.
    recorder = _ReportRecorder()
    recorder.install(monkeypatch)
    briefing = _run_trip_briefing(recorder, uid_vorbelastet, _trip(trip_id))
    assert _hint_lines(briefing.email_plain), (
        "AC-16 Voraussetzung: der Abschnitt muss erscheinen, sonst vergleicht "
        "der Test zwei unveraenderte Bestandslaeufe."
    )

    ergebnis = {}
    for uid in (uid_vorbelastet, uid_leer):
        mails: list = []
        gesendet = TripAlertService(
            settings=settings_email_only(), user_id=uid, throttle_hours=0,
            mail_sink=lambda subject, body: mails.append((subject, body)),
        ).check_and_send_alerts(
            gust_alert_trip(trip_id), [weather(1, gust_max_kmh=20.0)],
            fresh_weather=[weather(1, gust_max_kmh=60.0)],
        )
        ergebnis[uid] = (gesendet, mails)

    gesendet_mit, mails_mit = ergebnis[uid_vorbelastet]
    gesendet_ohne, mails_ohne = ergebnis[uid_leer]

    assert gesendet_mit is gesendet_ohne is True, (
        f"AC-16: Beide Alarm-Laeufe muessen rausgehen: {gesendet_mit!r} / "
        f"{gesendet_ohne!r}"
    )
    assert len(mails_mit) == len(mails_ohne) == 1, (
        "AC-16: Die Zahl der Alarm-Mails je Kanal darf sich nicht aendern: "
        f"{len(mails_mit)} vs. {len(mails_ohne)}"
    )
    assert mails_mit[0][0] == mails_ohne[0][0], (
        f"AC-16: Der Alarm-Betreff hat sich geaendert: {mails_mit[0][0]!r} vs. "
        f"{mails_ohne[0][0]!r}"
    )
    assert _heading() not in mails_mit[0][1], (
        "AC-16: Der Briefing-Hinweis darf NICHT in der Alarm-Mail auftauchen."
    )
    assert _ohne_uhrzeiten(mails_mit[0][1]) == _ohne_uhrzeiten(mails_ohne[0][1]), (
        "AC-16: Der Inhalt der Alarm-Mail haengt jetzt vom Protokoll ab — der "
        "Briefing-Hinweis leckt in den Alarm-Pfad."
    )


# ════════════ Vertrag des Anker-Bausteins (Reihenfolge, F001) ═════════════


def test_zeitstempel_ueberlebt_einen_fehlschlagenden_ankerschreibvorgang():
    """Der Briefing-Zeitstempel wird VOR dem Δ-Anker fortgeschrieben.

    GIVEN das Briefing ist raus, der Δ-Anker-Schreibvorgang scheitert aber.
    WHEN  der geteilte Baustein durchlaeuft.
    THEN  ist der Briefing-Zeitstempel TROTZDEM gesetzt.

    Ohne diese Reihenfolge zeigte das naechste Briefing dieselben Vorfaelle
    erneut, sobald der Anker einmal klemmt. Heute werfen beide Produktiv-
    Lambdas nicht (sie sind selbst fail-soft) — die Zusicherung waere also
    strukturell unbewacht und die Reihenfolge koennte beim naechsten Umbau
    still zurueckkippen (Adversary-Befund F001).

    Kein Mock: ``write_anchor`` IST ein Callable-Parameter des Bausteins; hier
    wird schlicht eines uebergeben, das scheitert — der echte Fehlerpfad.
    """
    from services.alert_briefing_anchor import (
        last_briefing_at, write_anchor_and_reset_memory,
    )

    uid = _uid("anker")
    trip_id = "trip-anker-fehlschlag"
    zurueckgesetzt: list[str] = []

    def _scheiternder_anker() -> None:
        raise RuntimeError("Snapshot-Write gescheitert")

    with pytest.raises(RuntimeError):
        write_anchor_and_reset_memory(
            user_id=uid,
            entity_ids=[trip_id],
            write_anchor=_scheiternder_anker,
            reset_memory=zurueckgesetzt.append,
            briefing_entity_id=trip_id,
            briefing_entity_type="trip",
        )

    assert last_briefing_at(
        user_id=uid, entity_id=trip_id, entity_type="trip",
    ) is not None, (
        "Der Briefing-Zeitstempel muss VOR dem Δ-Anker geschrieben werden — "
        "sonst verschluckt ein fehlschlagender Anker-Schreibvorgang den "
        "Zeitpunkt, und das naechste Briefing weist dieselben Vorfaelle "
        "erneut aus."
    )
    assert zurueckgesetzt == [], (
        "Voraussetzung dieses Tests: der Anker scheitert VOR dem "
        "Gedaechtnis-Reset — sonst prueft er eine andere Reihenfolge als die "
        "gemeinte."
    )


def test_ohne_kennung_wird_kein_zeitstempel_geschrieben():
    """Bestandsaufrufer ohne die neuen Parameter bleiben unveraendert: der
    Baustein schreibt dann KEINEN Zeitstempel (Rueckwaertskompatibilitaet)."""
    from services.alert_briefing_anchor import (
        last_briefing_at, write_anchor_and_reset_memory,
    )

    uid = _uid("anker-alt")
    trip_id = "trip-anker-altbestand"
    write_anchor_and_reset_memory(
        user_id=uid, entity_ids=[trip_id], write_anchor=lambda: None,
        reset_memory=lambda _e: None,
    )
    assert last_briefing_at(
        user_id=uid, entity_id=trip_id, entity_type="trip",
    ) is None, (
        "Ohne `briefing_entity_id`/`briefing_entity_type` darf der Baustein "
        "keinen Zeitstempel anlegen."
    )


# ═════════════════ Vertrag der Lesefunktion (Entdoppelung) ════════════════


def test_lesefunktion_entdoppelt_und_vereinigt_kanaele():
    """Vertrag zu AC-5 direkt an der Lesefunktion — die Wirkung im Briefing
    prueft ``test_ac5_...``; dieser Test macht sichtbar, WO die Entdoppelung
    passiert (beim LESEN, nie im Protokoll — sonst kippt D4).
    """
    from services.alert_log import read_undelivered

    uid = _uid("read")
    entity_id = "trip-read"
    jetzt = _jetzt()
    lauf = jetzt - timedelta(hours=1)
    _write_log(uid, not_delivered=[
        _entry(entity_id=entity_id, sent_at=lauf, metrics=(("thunder", "max"),),
               reason="forecast_change", channels_sent=(),
               not_sent=(("sms", "delivery_failed"),)),
        _entry(entity_id=entity_id, sent_at=lauf, hazards=("thunderstorm",),
               reason="official_alert", channels_sent=(),
               not_sent=(("telegram", "delivery_failed"),)),
    ], entries=[
        _entry(entity_id="trip-fremd", sent_at=lauf, metrics=(("gust", "max"),),
               reason="forecast_change", channels_sent=("email",),
               not_sent=(("sms", "delivery_failed"),)),
    ])

    vorfaelle = read_undelivered(
        uid, entity_id=entity_id, entity_type="trip", since=jetzt - timedelta(hours=6),
    )
    assert len(vorfaelle) == 1, (
        f"Zwei Eintraege desselben Laufs sind EIN Vorfall: {vorfaelle!r}"
    )
    kanaele = set(vorfaelle[0].channels)
    assert kanaele == {"sms", "telegram"}, (
        f"Die Kanaele beider Eintraege muessen vereinigt werden: {kanaele!r}"
    )

    ohne_fenster = read_undelivered(
        uid, entity_id=entity_id, entity_type="trip", since=jetzt + timedelta(minutes=1),
    )
    assert ohne_fenster == [], (
        f"Vorfaelle vor `since` duerfen nicht geliefert werden: {ohne_fenster!r}"
    )


@pytest.mark.parametrize("entity_type", ["trip", "compare"])
def test_lesefunktion_liest_nur_die_eigene_kennung(entity_type):
    """Kennung UND Typ trennen (seit #1467 S1 die EINZIGE Kennung)."""
    from services.alert_log import read_undelivered

    uid = _uid(f"kennung-{entity_type}")
    jetzt = _jetzt()
    _write_log(uid, not_delivered=[
        _entry(entity_id="x-1", entity_type="trip", sent_at=jetzt - timedelta(hours=1),
               metrics=(("gust", "max"),), reason="forecast_change",
               channels_sent=(), not_sent=(("sms", "delivery_failed"),)),
        _entry(entity_id="x-1", entity_type="compare", sent_at=jetzt - timedelta(hours=1),
               metrics=(("thunder", "max"),), reason="forecast_change",
               channels_sent=(), not_sent=(("sms", "delivery_failed"),)),
    ])
    vorfaelle = read_undelivered(
        uid, entity_id="x-1", entity_type=entity_type, since=jetzt - timedelta(hours=6),
    )
    assert len(vorfaelle) == 1, (
        f"Gleiche Kennung, anderer Typ darf nicht mitgelesen werden: {vorfaelle!r}"
    )
