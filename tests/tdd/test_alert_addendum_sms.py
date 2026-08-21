"""TDD RED — Issue #2018 Teil B: die Nachtragsmeldung erreicht die Kanaele.

SPEC: docs/specs/modules/alert_nachtragsmeldung.md, Abschnitt "Teil B",
AC-B1/AC-B3/AC-B4/AC-B6/AC-B7/AC-B8/AC-B9/AC-B11/AC-B12.

Fachlicher Kern: eine Nowcast-Meldung, die das Ereignis-Identitaets-Gate als
NACHTRAG zu einer bereits zugestellten amtlichen Warnung einstuft, wird
weiterhin zugestellt — aber gekennzeichnet. Die Kennzeichnung sitzt im
SMS-Text (Spec B1), weil der Kurzstil-Telegram-Zweig und Premium-SMS
(Garmin inReach) genau diesen Text senden; E-Mail und Voll-Telegram
bekommen zusaetzlich die ausformulierte Bezugszeile.

Vertrag, den die GREEN-Phase uebernehmen MUSS (Spec B2/B4/B6 — heute
existiert nichts davon, das ist der RED-Grund):

* ``AlertMessage.addendum_reference: str | None = None`` — additiv,
  optional, traegt die AUSFORMULIERTE Bezugszeile
  ("Ergaenzung zur amtlichen Warnung von 16:15").
* ``RadarAlertRequest.addendum_reference: str | None = None`` — additiv,
  optional, Muster ``briefing_context``; ``send_radar_alert()`` reicht den
  Wert unveraendert auf die ``AlertMessage`` durch. Das ist der Traeger,
  ueber den der Trip-Nowcast-Pfad (``trip_alert.py:1437-1445``) die vom
  Gate gelieferte Bezugszeile an den Versand gibt.
* ``render.py::_ADDENDUM_SMS_PREFIX = "Erg "`` — das gemeinsame Kompakt-
  Token fuer SMS/Kurzstil-Telegram/Premium-SMS.
* ``GateResult.is_addendum``/``addendum_reported_at`` (Teil A).

Mock-frei: echte Dataclass-Konstruktion, echte Renderer-Aufrufe, echte
lokale HTTP-Aufzeichnungs-Server fuer seven.io (SMS und Premium-SMS),
echte ``NotificationService``-/``TripAlertService``-Laeufe ueber die
vorhandenen DI-Naehte (``radar_service=``, ``mail_sink=``). Kein
``Mock()``/``patch()``/``MagicMock``, kein Netz, kein echter Versand.
"""
from __future__ import annotations

import http.server
import socket
import threading
import urllib.parse
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from app.config import Settings
from output.renderers.alert.model import AlertEvent, AlertMessage, OnsetEvent
from output.renderers.alert.render import (
    render_email, render_sms, render_subject, render_telegram,
)
from services.notification_service import NotificationService, RadarAlertRequest
from utils.timezone import local_fmt

from tests.helpers.nowcast_gate_fixtures import (
    TRIP_ZONE, clean_uid, fresh_uid, make_trip,
    quiet_window_elsewhere, radar_service, read_log, save_trip,
    settings_email_only, write_user_tier,
)

# Die Bezugszeile, wie sie der Trip-Nowcast-Pfad aus dem Gate-Ergebnis baut
# (Spec B2). Sie steht hier als Literal, weil sie NUTZERTEXT ist — der Test
# prueft den Satz, den der Wanderer liest, nicht eine Konstante des
# Prueflings.
ADDENDUM_LINE = "Ergänzung zur amtlichen Warnung von 16:15"

_UNSET = object()  # Sentinel: `addendum_reference` gar nicht erst uebergeben.


# ---------------------------------------------------------------------------
# Bausteine (mock-frei)
# ---------------------------------------------------------------------------


def _onset_msg(
    *,
    addendum_reference: object = _UNSET,
    onset_minutes: int = 25,
    onset_time: str = "16:45",
    onset_day_offset: int = 0,
    is_convective: bool = True,
    intensity_label: str = "kräftiger Regen",
    source_label: str = "Radar (DWD)",
    segment_id: str | None = "Ziel",
    location_label: str | None = None,
    briefing_context: str | None = "nicht angekündigt",
    trip_short: str = "KHW 403",
    km_from: float = 0.0,
    km_to: float = 6.0,
) -> AlertMessage:
    """Eine Nowcast-Onset-``AlertMessage`` (Trip-Pfad, ``source`` gesetzt).

    ``addendum_reference`` wird NUR uebergeben, wenn ein Aufrufer es
    ausdruecklich setzt (Muster ``briefing_context`` in
    ``test_952_onset_alert_fidelity.py``): so bleiben die Regressions-
    Waechter (AC-B8/AC-B9) unabhaengig vom Modell-Erweiterungsstand gruen,
    waehrend die Nachtrags-Faelle heute am ``TypeError`` scheitern.
    """
    event = OnsetEvent(
        onset_minutes=onset_minutes, onset_time=onset_time,
        onset_day_offset=onset_day_offset, km_from=km_from, km_to=km_to,
        is_convective=is_convective, intensity_label=intensity_label,
        source_label=source_label, briefing_context=briefing_context,
        segment_id=segment_id, location_label=location_label,
    )
    kwargs = dict(
        trip_short=trip_short, stand_at="16:20", events=(event,),
        source=source_label, cooldown_display="2 Stunden",
    )
    if addendum_reference is not _UNSET:
        kwargs["addendum_reference"] = addendum_reference
    return AlertMessage(**kwargs)


def _bundle_onset_msg(*, addendum_reference: object = _UNSET) -> AlertMessage:
    """Gebuendelter Mehr-Orte-Onset (``_render_email_onset_multi``-Zweig)."""
    first = OnsetEvent(
        onset_minutes=20, onset_time="16:40", km_from=0.0, km_to=0.0,
        is_convective=True, intensity_label="kräftiger Regen",
        source_label="Radar (DWD)", location_label="Innsbruck",
    )
    second = OnsetEvent(
        onset_minutes=35, onset_time="16:55", km_from=0.0, km_to=0.0,
        is_convective=False, intensity_label="leichter Regen",
        source_label="AROME-FR", location_label="Bozen",
    )
    kwargs = dict(
        trip_short="Alpen", stand_at="16:20", events=(first, second),
        source="Radar (DWD)", cooldown_display="2 Stunden",
    )
    if addendum_reference is not _UNSET:
        kwargs["addendum_reference"] = addendum_reference
    return AlertMessage(**kwargs)


def _thunder_deviation_msg(
    *, value_from: float = 2.0, value_to: float = 4.0,
    addendum_reference: object = _UNSET,
) -> AlertMessage:
    """Aenderungsalarm (``source=None``) mit Stufen-Metrik.

    ``value_to=4.0`` liegt AUSSERHALB der Stufenleiter 0-3 und erzwingt
    damit den ``LEVELS.get(..., "-")``-Rueckfall — der zweite bestehende
    Bindestrich-Gebrauch neben dem ``"->"``-Pfeil (AC-B11).
    """
    event = AlertEvent(
        metric_id="thunder", value_from=value_from, value_to=value_to,
        threshold=1.0, cmp="über", occurred_at="15:00",
        km_from=0.0, km_to=4.0,
    )
    kwargs = dict(
        trip_short="KHW 403", stand_at="09:30", events=(event,), source=None,
    )
    if addendum_reference is not _UNSET:
        kwargs["addendum_reference"] = addendum_reference
    return AlertMessage(**kwargs)


class _SevenIoStub:
    """Lokaler HTTP-Server, der die seven.io-POSTs von SMS UND Premium-SMS
    entgegennimmt (Vorbild ``test_channel_origin_guard_parity.py``). Kein
    Mock: der echte Transport laeuft, die Nutzlast wird am Draht gemessen."""

    def __init__(self) -> None:
        self.received: list[dict] = []
        received = self.received

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length", 0))
                data = urllib.parse.parse_qs(self.rfile.read(length).decode())
                received.append({k: v[0] for k, v in data.items()})
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"100")

            def log_message(self, *args):  # noqa: D401
                pass

        probe = socket.socket()
        probe.bind(("", 0))
        self.port = probe.getsockname()[1]
        probe.close()
        self._server = http.server.HTTPServer(("127.0.0.1", self.port), Handler)
        threading.Thread(target=self._server.serve_forever, daemon=True).start()

    def stop(self) -> None:
        self._server.shutdown()


@pytest.fixture()
def seven_io_stub():
    stub = _SevenIoStub()
    yield stub
    stub.stop()


SMS_TO = "+49000000000"
PREMIUM_REPLY_TO = "+4915799912345"


def _sms_and_premium_settings(port: int) -> Settings:
    """seven.io auf den lokalen Stub, Rueckadresse fuer Premium-SMS frisch.

    ``seven_api_key == seven_sandbox_key`` haelt beide Sicherheitssperren
    (Test-Modus-Zwang und Herkunftssperre, ``seven_io_base.py``) zufrieden,
    ohne dass der Test von der Herkunfts-Erkennung abhaengt.
    """
    return Settings(
        sms_gateway_url=f"http://127.0.0.1:{port}/api/sms",
        seven_api_key="sandbox-key-2018",
        seven_sandbox_key="sandbox-key-2018",
        sms_to=SMS_TO,
        sms_from=None,
        premium_sms_reply_to=PREMIUM_REPLY_TO,
        premium_sms_reply_at=datetime.now(timezone.utc),
        telegram_bot_token="", telegram_chat_id="",
    )


def _radar_request(*, addendum_reference: object = _UNSET) -> RadarAlertRequest:
    kwargs = dict(
        onset_minutes=25, onset_time="16:45", km_from=0.0, km_to=6.0,
        is_convective=True, intensity_label="kräftiger Regen",
        source_label="Radar (DWD)", tz=ZoneInfo("Europe/Paris"),
        briefing_context="nicht angekündigt", segment_id="Ziel",
    )
    if addendum_reference is not _UNSET:
        kwargs["addendum_reference"] = addendum_reference
    return RadarAlertRequest(**kwargs)


class _RecordingNotificationService(NotificationService):
    """Echte Unterklasse (kein Mock): merkt sich die kanonische
    ``AlertMessage``, laesst danach den unveraenderten echten Versand
    weiterlaufen. Die Naht sitzt an der Stelle, an der die Nachricht
    fertig gebaut ist und die Kanaele sie bekommen."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.dispatched: list[AlertMessage] = []

    def _dispatch_alert_message(self, alert_msg, effective_channels, **kwargs):
        self.dispatched.append(alert_msg)
        return super()._dispatch_alert_message(
            alert_msg, effective_channels, **kwargs,
        )


class _ConvectiveFrameSource:
    """Echter aufrufbarer ``frame_source`` (kein Mock): garantiert ein
    konvektives — also ``HIGH``-dringliches — Nowcast-Ergebnis."""

    def __init__(self, onset_minutes: int = 20) -> None:
        self._onset = onset_minutes

    def __call__(self, lat: float, lon: float) -> list:
        from providers.brightsky import RadarFrame

        ts = datetime.now(timezone.utc) + timedelta(minutes=self._onset)
        return [
            RadarFrame(timestamp=ts, precip_mm_h=9.0, is_convective=True),
            RadarFrame(
                timestamp=ts + timedelta(minutes=10), precip_mm_h=12.0,
                is_convective=True,
            ),
        ]


# ===========================================================================
# AC-B1 — der Trip-Nowcast-Pfad stellt den Nachtrag ZU
# ===========================================================================


def test_ac_b1_nachtrag_wird_zugestellt_und_traegt_die_bezugszeile():
    """AC-B1 GIVEN eine bereits zugestellte amtliche Warnung (Register-
    Eintrag der Klasse ``wet``, Dringlichkeit ``MODERATE``) und einen
    danach auflaufenden konvektiven Nowcast (``HIGH``) fuer dieselbe Etappe
    WHEN ``check_radar_alerts()`` laeuft
    THEN wird die Meldung ZUGESTELLT (keine Unterdrueckung, kein
    ``not_delivered``-Eintrag mit ``REASON_EVENT_DUPLICATE``) und die
    kanonische ``AlertMessage`` traegt ``addendum_reference`` mit der
    Uhrzeit der amtlichen Warnung.

    RED heute: das Gate kennt keinen dritten Ausgang — die Meldung geht
    als UNMARKIERTER Voll-Alarm raus, ``AlertMessage`` hat das Feld nicht.
    """
    from services.alert_gate import record_event_identity
    from services.alert_log import REASON_EVENT_DUPLICATE
    from services.trip_alert import TripAlertService

    uid, trip_id = fresh_uid("2018-b1"), "trip-2018-b1"
    clean_uid(uid)
    try:
        write_user_tier(uid, "premium")
        now = datetime.now(timezone.utc)
        reported_at = now - timedelta(minutes=25)
        # Bereits zugestellte AMTLICHE Warnung: nur `window_*`, kein
        # `point_at` -- daraus leitet das Register die Quelle "official" ab
        # (Spec A2). Segment "1" ist die Einzeletappe von `make_trip()`.
        record_event_identity(
            user_id=uid, entity_id=trip_id, hazard_class="wet",
            segment_ids=["1"], severity="MODERATE",
            window_start=now - timedelta(minutes=30),
            window_end=now + timedelta(hours=3), now=reported_at,
        )
        quiet_from, quiet_to = quiet_window_elsewhere(zone=TRIP_ZONE)
        save_trip(make_trip(trip_id, quiet_from=quiet_from, quiet_to=quiet_to), uid)

        mails: list[tuple[str, str]] = []
        svc = TripAlertService(
            settings=settings_email_only(), throttle_hours=0, user_id=uid,
            radar_service=radar_service(_ConvectiveFrameSource()),
            mail_sink=lambda subject, body: mails.append((subject, body)),
        )
        recorder = _RecordingNotificationService(settings_email_only(), uid)
        svc._notification_service = recorder

        sent = svc.check_radar_alerts()

        assert sent == 1, (
            "RED: der Nachtrag muss ZUGESTELLT werden (Variante c) — "
            f"check_radar_alerts() lieferte {sent}."
        )
        assert mails, "RED: es ging keine Nachricht raus."
        unterdrueckt = [
            e for e in read_log(uid).get("not_delivered", [])
            if e.get("entity_id") == trip_id
            and any(
                item.get("reason") == REASON_EVENT_DUPLICATE
                for item in e.get("channels_not_sent", [])
                if isinstance(item, dict)
            )
        ]
        assert unterdrueckt == [], (
            "RED: der Nachtrag darf NICHT als Ereignis-Duplikat unterdrueckt "
            f"protokolliert werden: {unterdrueckt!r}"
        )
        assert len(recorder.dispatched) == 1, (
            f"Erwartet genau EINE versandte AlertMessage: {recorder.dispatched!r}"
        )
        alert_msg = recorder.dispatched[0]
        erwartet = (
            "Ergänzung zur amtlichen Warnung von "
            f"{local_fmt(reported_at, TRIP_ZONE)}"
        )
        assert getattr(alert_msg, "addendum_reference", None) == erwartet, (
            "RED: AlertMessage.addendum_reference fehlt oder zitiert die "
            f"falsche Uhrzeit: {getattr(alert_msg, 'addendum_reference', None)!r} "
            f"(erwartet {erwartet!r})"
        )
    finally:
        clean_uid(uid)


# ===========================================================================
# AC-B3 — Voll-Telegram traegt die ausformulierte Zeile
# ===========================================================================


def test_ac_b3_voll_telegram_traegt_bezugszeile_vor_dem_detailtext():
    """AC-B3 GIVEN eine Nowcast-Onset-Meldung mit gesetztem
    ``addendum_reference``
    WHEN der reiche Telegram-Renderer laeuft
    THEN steht die ausformulierte Bezugszeile als EIGENE Zeile zwischen
    Kopfzeile und dem bestehenden Detailtext — und der Detailtext bleibt
    unveraendert.

    RED heute: ``AlertMessage`` kennt das Feld nicht (``TypeError``)."""
    ohne = render_telegram(_onset_msg())
    mit = render_telegram(_onset_msg(addendum_reference=ADDENDUM_LINE))

    zeilen_ohne = ohne.split("\n")
    zeilen_mit = mit.split("\n")
    assert len(zeilen_mit) == len(zeilen_ohne) + 1, (
        f"Erwartet genau EINE zusaetzliche Zeile: {zeilen_mit!r}"
    )
    assert zeilen_mit[0] == zeilen_ohne[0], (
        f"Die Kopfzeile hat sich veraendert: {zeilen_mit[0]!r}"
    )
    assert zeilen_mit[1] == ADDENDUM_LINE, (
        "RED: die Bezugszeile muss als eigene Zeile VOR dem Detailtext "
        f"stehen: {zeilen_mit!r}"
    )
    assert zeilen_mit[2] == zeilen_ohne[1], (
        f"Der bestehende Detailtext hat sich veraendert: {zeilen_mit[2]!r}"
    )


def test_ac_b3_voll_telegram_ohne_nachtrag_bleibt_unveraendert():
    """AC-B3 (Gegenprobe) GIVEN dieselbe Meldung mit
    ``addendum_reference=None`` WHEN Telegram gerendert wird THEN ist der
    Text byte-identisch zu dem OHNE das Feld — keine Leerzeile."""
    assert render_telegram(_onset_msg(addendum_reference=None)) == render_telegram(
        _onset_msg()
    ), "Ein ungesetzter Nachtrag darf den Telegram-Text nicht anfassen."


# ===========================================================================
# AC-B4 — die Kurznachricht traegt das Kompakt-Token
# ===========================================================================


def test_ac_b4_sms_beginnt_mit_nachtrags_praefix_und_bleibt_sonst_gleich():
    """AC-B4 GIVEN eine Nowcast-Onset-Meldung mit gesetztem
    ``addendum_reference``
    WHEN ``render_sms`` laeuft
    THEN beginnt der Text mit ``"Erg "`` und der Rest hinter dem Praefix
    ist IDENTISCH zum Text ohne Nachtrag.

    RED heute: ``AlertMessage`` kennt das Feld nicht (``TypeError``)."""
    ohne = render_sms(_onset_msg())
    mit = render_sms(_onset_msg(addendum_reference=ADDENDUM_LINE))

    assert mit.startswith("Erg "), (
        f"RED: die Kurznachricht traegt kein Nachtrags-Token: {mit!r}"
    )
    assert mit[len("Erg "):] == ohne, (
        "RED: hinter dem Praefix muss der unveraenderte Kern-Text stehen.\n"
        f"  mit  = {mit!r}\n  ohne = {ohne!r}"
    )


def test_ac_b4_sms_ohne_nachtrag_traegt_kein_praefix():
    """AC-B4 (Gegenprobe) GIVEN dieselbe Meldung mit
    ``addendum_reference=None`` WHEN die SMS gerendert wird THEN ist sie
    byte-identisch zur Fassung ohne das Feld."""
    assert render_sms(_onset_msg(addendum_reference=None)) == render_sms(
        _onset_msg()
    ), "Ein ungesetzter Nachtrag darf die Kurznachricht nicht anfassen."


# ===========================================================================
# AC-B6 — Premium-SMS (Garmin inReach) bekommt denselben Text
# ===========================================================================


def test_ac_b6_premium_sms_traegt_dasselbe_praefix_wie_die_sms(seven_io_stub):
    """AC-B6 GIVEN eine Nowcast-Meldung mit gesetztem
    ``addendum_reference`` und aktiviertem Premium-SMS-Kanal
    WHEN ``NotificationService.send_radar_alert()`` laeuft
    THEN traegt der an ``PremiumSmsOutput`` uebergebene Text dasselbe
    ``"Erg "``-Praefix und ist identisch zum SMS-Text DESSELBEN Laufs —
    ein eigener Premium-Renderer entstuende sonst unbemerkt.

    Premium-SMS ist auf der Huette am Karnischen Hoehenweg der EINZIGE
    ankommende Kanal (CLAUDE.md) — eine Kennzeichnung, die ihn nicht
    erreicht, erreicht dort niemanden.

    RED heute: ``RadarAlertRequest`` kennt ``addendum_reference`` nicht
    (``TypeError``)."""
    settings = _sms_and_premium_settings(seven_io_stub.port)
    svc = NotificationService(settings, fresh_uid("2018-b6"))
    trip = make_trip("trip-2018-b6")

    svc.send_radar_alert(
        trip=trip,
        request=_radar_request(addendum_reference=ADDENDUM_LINE),
        source="Radar (DWD)",
        cooldown_display="2 Stunden",
        effective_channels={"sms", "premium_sms"},
    )

    nach_ziel = {p.get("to"): p.get("text") for p in seven_io_stub.received}
    assert set(nach_ziel) == {SMS_TO, PREMIUM_REPLY_TO}, (
        "Erwartet je EINEN seven.io-POST fuer SMS und Premium-SMS, "
        f"empfangen: {seven_io_stub.received!r}"
    )
    premium_text = nach_ziel[PREMIUM_REPLY_TO]
    sms_text = nach_ziel[SMS_TO]
    assert premium_text.startswith("Erg "), (
        f"RED: Premium-SMS traegt kein Nachtrags-Token: {premium_text!r}"
    )
    assert premium_text == sms_text, (
        "RED: Premium-SMS und SMS muessen denselben Renderer-Ausgang tragen.\n"
        f"  premium = {premium_text!r}\n  sms     = {sms_text!r}"
    )


# ===========================================================================
# AC-B7 — die Kurznachricht bleibt im laengsten Fall im Budget
# ===========================================================================


def test_ac_b7_laengster_realistischer_nachtragsfall_bleibt_im_zeichenbudget():
    """AC-B7 GIVEN den laengsten realistischen Nachtragsfall — maximale
    Ortsbezeichnung, voller Zeitstempel mit Tagesbezug, Nachtrags-Praefix
    WHEN ``render_sms`` mit dem Default-Limit laeuft
    THEN ist das Ergebnis <= 160 Zeichen (hartes Produktlimit) UND
    <= ``limit`` (140) — gemessen an der TATSAECHLICHEN Laenge des
    Strings, nicht an einer Rechnung darueber.

    RED heute: ``AlertMessage`` kennt ``addendum_reference`` nicht."""
    msg = _onset_msg(
        addendum_reference=ADDENDUM_LINE,
        onset_time="00:23", onset_day_offset=1,
        location_label="Ödensteinalm am Karnischen Höhenweg " * 8,
        segment_id=None,
    )
    sms = render_sms(msg)

    assert len(sms) <= 140, (
        f"RED: {len(sms)} Zeichen ueberschreiten das Render-Limit: {sms!r}"
    )
    assert len(sms) <= 160, (
        f"RED: {len(sms)} Zeichen ueberschreiten das Produktlimit: {sms!r}"
    )


def test_ac_b7_nachtrag_haelt_auch_ein_kleines_uebergebenes_limit_ein():
    """AC-B7 (zweite Haelfte) GIVEN denselben Fall mit einem KLEINEN
    uebergebenen ``limit`` WHEN gerendert wird THEN haelt das Ergebnis
    dieses Limit ein — das Praefix darf das Budget nicht sprengen, sondern
    muss es dem Kern-Text abziehen (Spec B4)."""
    msg = _onset_msg(
        addendum_reference=ADDENDUM_LINE,
        location_label="Ödensteinalm am Karnischen Höhenweg " * 8,
        segment_id=None,
    )
    sms = render_sms(msg, limit=40)

    assert len(sms) <= 40, (
        f"RED: {len(sms)} Zeichen bei limit=40: {sms!r}"
    )
    assert sms.startswith("Erg "), (
        f"Das Praefix darf der Kuerzung nicht zum Opfer fallen: {sms!r}"
    )


# ===========================================================================
# AC-B8 — der Normalfall bleibt byte-identisch (Regressionswaechter, GRUEN)
# ===========================================================================

# Ist-Stand vor dieser Scheibe, aufgezeichnet am 2026-08-21 aus echten
# Renderer-Aufrufen (nicht aus der Spec abgeschrieben).
GOLDEN_SMS = "Ziel: TH@16:45"
GOLDEN_SUBJECT = "[KHW 403] 🏁 Ziel · Gewitter in 25 Min"
GOLDEN_TELEGRAM = (
    "<b>KHW 403 · 🏁 Ziel · Gewitter in 25 Min</b>\n"
    "16:45 · kräftiger Regen · Radar (DWD)"
)
GOLDEN_EMAIL_PLAIN = (
    "Gewitter in 25 Min\n"
    "\n"
    "Radar-Nowcast\n"
    "\n"
    "Wo & wann: 🏁 Ziel · ab 16:45\n"
    "Intensität: kräftiger Regen\n"
    "Quelle: Radar (DWD)\n"
    "Briefing: nicht angekündigt\n"
    "\n"
    "Stand: heute 16:20\n"
    "Cooldown: Du erhältst diese Warnung höchstens einmal in 2 Stunden.\n"
    "\n"
    "Regen-/Gewitter-Alarm · Radar (DWD)"
)
GOLDEN_EMAIL_PLAIN_BUNDLE = (
    "Regen-Alarm: 2 Orte\n"
    "\n"
    "Radar-Nowcast\n"
    "\n"
    "Innsbruck · Gewitter/Hagel in 20 Min: ab 16:40 · kräftiger Regen\n"
    "Bozen · Regen in 35 Min: ab 16:55 · leichter Regen\n"
    "\n"
    "Stand: heute 16:20 · Quelle: Radar (DWD), AROME-FR\n"
    "Cooldown: Du erhältst diese Warnung höchstens einmal in 2 Stunden.\n"
    "\n"
    "Regen-/Gewitter-Alarm · Radar (DWD)"
)


def test_ac_b8_gewoehnliche_nowcast_meldung_bleibt_auf_allen_kanaelen_gleich():
    """AC-B8 GIVEN eine gewoehnliche Nowcast-Meldung OHNE Registertreffer
    WHEN irgendein Kanal gerendert wird
    THEN ist die Ausgabe byte-identisch zum Stand vor dieser Scheibe —
    keine neue Zeile, kein Praefix, keine Leerzeile.

    Heute GRUEN; wird dieser Test durch die Implementierung rot, leckt die
    Kennzeichnung in einen Fall ohne Treffer."""
    msg = _onset_msg()

    assert render_sms(msg) == GOLDEN_SMS
    assert render_subject(msg) == GOLDEN_SUBJECT
    assert render_telegram(msg) == GOLDEN_TELEGRAM
    _, plain = render_email(msg)
    assert plain == GOLDEN_EMAIL_PLAIN


def test_ac_b8_gebuendelte_nowcast_mail_bleibt_gleich():
    """AC-B8 (Buendel-Zweig) GIVEN einen gebuendelten Mehr-Orte-Onset OHNE
    Nachtrag WHEN die E-Mail gerendert wird THEN bleibt der Plain-Text
    byte-identisch zum Stand vor dieser Scheibe."""
    _, plain = render_email(_bundle_onset_msg())
    assert plain == GOLDEN_EMAIL_PLAIN_BUNDLE


# ===========================================================================
# AC-B9 — ein gewoehnlicher Alarm traegt das Token NICHT
# ===========================================================================


def test_ac_b9_gewoehnlicher_alarm_traegt_kein_nachtrags_token():
    """AC-B9 GIVEN einen gewoehnlichen Alarm OHNE vorherige Meldung —
    einmal als Aenderungsalarm (Stufenwort-Waechter-Fall), einmal als
    Nowcast
    WHEN der SMS-Text erzeugt wird (den der Kurzstil-Telegram-Zweig
    unveraendert weiterreicht)
    THEN enthaelt er das Nachtrags-Token ``"Erg "`` NICHT und bleibt
    zeichengleich zum heutigen Stand.

    Heute GRUEN. Die beiden benannten Bestandswaechter
    (``test_alert_stufenwort.py::test_ac14_sms_bleibt_unveraendert_
    regressionswaechter`` und die Byte-Identitaet in
    ``test_telegram_kurzstil_trip_alert.py``) bleiben UNANGETASTET und
    laufen im selben Lauf mit; wird einer von ihnen rot, ist das ein
    Befund an der Implementierung, nicht am Test (Spec AC-B9)."""
    aenderung = render_sms(_thunder_deviation_msg(value_from=2.0, value_to=3.0))
    assert aenderung == "km 0-4: TH:M->H@15", (
        f"Der Aenderungsalarm hat sich veraendert: {aenderung!r}"
    )
    assert not aenderung.startswith("Erg "), (
        f"Nachtrags-Token in einem Fall OHNE Treffer: {aenderung!r}"
    )

    nowcast = render_sms(_onset_msg())
    assert nowcast == GOLDEN_SMS, f"Der Nowcast hat sich veraendert: {nowcast!r}"
    assert not nowcast.startswith("Erg "), (
        f"Nachtrags-Token in einem Fall OHNE Treffer: {nowcast!r}"
    )


# ===========================================================================
# AC-B11 — kein dritter Bindestrich-Gebrauch
# ===========================================================================


def test_ac_b11_praefix_literal_enthaelt_keinen_bindestrich():
    """AC-B11 GIVEN das SMS-Praefix-Literal ``_ADDENDUM_SMS_PREFIX``
    WHEN man seinen Zeichenbestand inspiziert
    THEN enthaelt es KEIN ``"-"`` — der Bindestrich bleibt ausschliesslich
    Stufen-Rueckfall (``LEVELS.get(..., "-")``) und Pfeilbestandteil
    (``"->"``), ohne dritte Bedeutung.

    Bewusste Literal-Inspektion des importierten Symbols (nicht der Datei
    als Text), weil die Aussage sich auf den ZEICHENBESTAND bezieht.

    RED heute: das Symbol existiert nicht (``ImportError``)."""
    from output.renderers.alert.render import _ADDENDUM_SMS_PREFIX

    assert "-" not in _ADDENDUM_SMS_PREFIX, (
        f"Dritte Bedeutung des Bindestrichs: {_ADDENDUM_SMS_PREFIX!r}"
    )
    assert _ADDENDUM_SMS_PREFIX == "Erg ", (
        f"Erwartet das Kompakt-Token 'Erg ': {_ADDENDUM_SMS_PREFIX!r}"
    )


def test_ac_b11_nachtrag_und_stufen_rueckfall_bleiben_gleichzeitig_lesbar():
    """AC-B11 (zweite Haelfte) GIVEN einen Alarm, dessen Stufe AUSSERHALB
    der Leiter 0-3 liegt (``LEVELS.get(..., "-")``-Rueckfall) UND der als
    Nachtrag gekennzeichnet ist
    WHEN die SMS gerendert wird
    THEN stehen Nachtrags-Token und Stufen-Rueckfall im selben Text, ohne
    einander zu ueberladen: das Praefix bleibt vorn und zeichenrein, das
    Stufen-Token unveraendert.

    RED heute: ``AlertMessage`` kennt ``addendum_reference`` nicht."""
    ohne = render_sms(_thunder_deviation_msg())
    mit = render_sms(_thunder_deviation_msg(addendum_reference=ADDENDUM_LINE))

    assert ohne == "km 0-4: TH:M->-@15", (
        f"Voraussetzung: der Stufen-Rueckfall muss auftreten: {ohne!r}"
    )
    assert mit == "Erg " + ohne, (
        "RED: Nachtrags-Token und Stufen-Rueckfall muessen nebeneinander "
        f"unveraendert lesbar bleiben: {mit!r}"
    )
    assert mit.count("-") == ohne.count("-"), (
        f"Das Praefix hat einen weiteren Bindestrich eingebracht: {mit!r}"
    )


# ===========================================================================
# AC-B12 — der amtliche Trip-Pfad bleibt unangetastet
# ===========================================================================


def test_ac_b12_official_alert_notice_traegt_kein_nachtrags_feld():
    """AC-B12 GIVEN das amtliche Melde-DTO ``OfficialAlertNotice``
    WHEN man seine Felder betrachtet
    THEN traegt es KEIN ``addendum_reference`` — amtliche Meldungen koennen
    durch diese Scheibe strukturell nie zum Nachtrag werden (Spec A4/B2),
    das Feld waere auf diesem DTO tot.

    Heute GRUEN; der Test haelt die Abwesenheit fest, damit sie nicht
    beilaeufig gekippt wird."""
    import dataclasses

    from output.renderers.alert.official_alerts import OfficialAlertNotice

    felder = {f.name for f in dataclasses.fields(OfficialAlertNotice)}
    assert "addendum_reference" not in felder, (
        f"Nachtrags-Feld auf dem amtlichen DTO: {sorted(felder)!r}"
    )


def test_ac_b12_amtliche_warnung_nach_nowcast_bleibt_unmarkierter_vollalarm():
    """AC-B12 GIVEN einen bereits registrierten Nowcast (``MODERATE``) und
    eine danach auflaufende amtliche Warnung hoeherer Stufe (``HIGH``) fuer
    dieselbe Etappe
    WHEN der amtliche Trip-Pfad laeuft
    THEN wird die Warnung als VOLLER, unmarkierter Alarm zugestellt — der
    Filter-Loop verwirft weiterhin ausschliesslich bei ``allowed=False``,
    und keine Nachtrags-Kennzeichnung erscheint im Text.

    Heute GRUEN (Kernfall aus S4b-1, PO-freigegeben); wird er durch diese
    Scheibe rot, ist die Richtungs-Bedingung falsch herum gebaut."""
    from services.alert_gate import record_event_identity
    from services.official_alerts import (
        OfficialAlert, register_official_alert_source,
    )
    import services.official_alerts.base as official_base
    from services.trip_alert import TripAlertService
    from services.weather_snapshot import WeatherSnapshotService

    from tests.helpers.alert_log_fixtures import gust_alert_trip, weather

    class _FakeOfficialSource:
        """Echte Quelle im Sinne des Quell-Protokolls (strukturelles
        Subtyping, Vorbild ``test_nowcast_suppression_logging.py``)."""

        def __init__(self, alerts) -> None:
            self._alerts = alerts

        @property
        def name(self) -> str:
            return "tdd-2018-b12-source"

        def covers(self, lat, lon) -> bool:
            return True

        def fetch(self, lat, lon, **kwargs):
            return list(self._alerts)

    uid = fresh_uid("2018-b12")
    clean_uid(uid)
    quellen = list(official_base._REGISTERED_SOURCES)
    official_base._REGISTERED_SOURCES.clear()
    try:
        now = datetime.now(timezone.utc)
        # Bereits zugestellter NOWCAST (nur `point_at` -> Quelle "nowcast").
        record_event_identity(
            user_id=uid, entity_id="trip-2018-b12", hazard_class="wet",
            segment_ids=["1"], severity="MODERATE", point_at=now, now=now,
        )
        trip = gust_alert_trip("trip-2018-b12")
        trip.official_alert_triggers_enabled = None
        WeatherSnapshotService(user_id=uid).save_dated(
            trip.id, date.today(), [weather(1, precip_sum_mm=2.0)],
        )
        # Stufe 4 (`LEVEL_LETTERS[4] == "H"` -> `HIGH`) uebertrifft den
        # registrierten Nowcast (`MODERATE`) -- die V2-Eskalation traegt die
        # Warnung durch das Gate, genau wie vor dieser Scheibe.
        register_official_alert_source(_FakeOfficialSource([
            OfficialAlert(
                source="tdd-2018-b12", hazard="thunderstorm", level=4,
                label="AC-B12-Warnung", valid_from=now - timedelta(minutes=5),
                valid_to=now + timedelta(minutes=45), region_label="B12-Region",
            ),
        ]))

        mails: list[tuple[str, str]] = []
        svc = TripAlertService(
            settings=settings_email_only(), user_id=uid,
            mail_sink=lambda subject, body: mails.append((subject, body)),
        )
        notices = svc.check_official_alert_triggers(trip)
        assert len(notices) == 1, (
            f"Voraussetzung: die Warnung muss als neu erkannt werden: {notices!r}"
        )
        gesendet = svc._send_official_alert_only(trip, notices)

        assert gesendet is True, (
            "Voraussetzung: die eskalierende amtliche Warnung muss durchkommen "
            "(V2, unveraendert)."
        )
        assert mails, "Voraussetzung: es muss eine Nachricht rausgegangen sein."
        betreff, koerper = mails[-1]
        assert "Ergänzung zur amtlichen Warnung" not in koerper, (
            f"Amtliche Warnung als Nachtrag gekennzeichnet: {koerper!r}"
        )
        assert not betreff.startswith("Erg "), (
            f"Nachtrags-Token auf der amtlichen Warnung: {betreff!r}"
        )
    finally:
        official_base._REGISTERED_SOURCES.clear()
        official_base._REGISTERED_SOURCES.extend(quellen)
        clean_uid(uid)
