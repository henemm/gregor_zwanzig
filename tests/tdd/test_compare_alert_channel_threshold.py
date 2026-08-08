"""TDD RED — Issue #1461 Scheibe S3b-2b: einstellbare Dringlichkeits-Schwelle
je Alarm-Kanal (Ortsvergleiche).

SPEC: docs/specs/modules/feat_1461_s3b2b_compare_kanal_schwelle.md (v1.3,
18 ACs). Diese Datei deckt die Python-seitigen ACs ab: AC-1 bis AC-8, AC-11,
AC-12, AC-16, AC-17, AC-18. AC-9/AC-10 (Go-Persistenz/-Merge) und AC-13/AC-14
(Anlege-/Hub-Speicherweg) sind NICHT Teil dieser Datei — Go braucht einen
Overlay-Test (siehe Team-Lead-Auftrag), AC-13/AC-14/AC-15 sind Svelte-
Oberfläche und in dieser Phase nicht mountbar (ADR-0020), sie gehören in die
Staging-/Playwright-Verifikation.

RED-Grund heute (gemessen, docs/context/feat-1461-s3b2b-compare-kanal-schwelle.md):
``split_by_threshold()`` (aus S3b-2a, bereits fertig) wird an KEINER der drei
Compare-Alarm-Nahtstellen aufgerufen:

* ``compare_alert.py`` (Δ-Änderungsalarm, `:334` Kanal-Set, `:177-187` Versand)
  — UND das Kanal-Set entsteht heute je PRESET, nicht je Ort: AC-3 deckt
  genau diese Schleifen-Falle ab.
* ``compare_official_alert.py`` (amtliche Warnung, `:271`).
* ``compare_radar_alert.py`` (Regenradar, `:131`/`:150`) — dort zusätzlich
  heute hart auf ``{"email"}`` verdrahtet, unabhängig vom Kanal-Opt-in
  (AC-5 deckt diese zweite, unabhängige Verhaltensänderung ab).

``AlertChannelThresholds`` existiert auf ``ComparePreset`` noch nicht (Go) —
Python liest die Schwelle deshalb heute nirgends aus dem Preset-Rohdict.
``comparison.py`` filtert amtliche Warnungen im Kurznachrichten-Bericht hart
auf ``MIN_SMS_LEVEL`` (Stufe 3) statt auf die (fehlende) Kanal-Schwelle
(AC-17/AC-18, zwei verschiedene Codestellen: ``:735`` Inline-Filter,
``:900`` fehlender ``min_level``-Parameter).

Testpolitik (CLAUDE.md „Test-Politik: Zwei Schichten"): kein Mock-Theater —
kein ``Mock()``/``patch()``/``MagicMock``. Telegram/SMS laufen über ECHTE
lokale HTTP-Stubs (127.0.0.1), E-Mail über den bestehenden ``mail_sink``-DI-
Seam. Reale Persistenz unter der pytest-isolierten
``app.loader.get_data_dir()``-Basis (#1133); Compare-Presets zusätzlich unter
dem cwd-relativen ``data/users/...``-Pfad, den ``load_compare_presets()``
selbst verwendet (dieselbe bewusste Ausnahme wie in
``tests/helpers/alert_log_fixtures.py`` dokumentiert).

KEIN ECHTER VERSAND (#1477): jede ``Settings(...)``-Fabrik hier setzt JEDES
versandrelevante Feld ausdrücklich mit Dummy-/Test-Werten; Telegram/SMS
werden zusätzlich per Herkunftssperre (#1476, ``running_origin`` gepinnt)
und lokalem HTTP-Stub auf 127.0.0.1 umgelenkt — Muster 1:1 aus
``tests/tdd/test_alert_channel_threshold.py`` (Trip-Vorlage, S3b-2a).

Pfadregel #1409: keine Datei dieses Moduls referenziert einen festen
Hauptrepo-Pfad für den Prüfling. Die früher hier dokumentierte Ausnahme
``DATA_ROOT`` (cwd-relative Compare-Preset-Ablage) ist mit #1595 entfallen —
der Compare-Loader löst die Datenwurzel jetzt über ``get_data_root()`` auf,
also über dieselbe Basis wie die #1133-Testisolation.

Fallen, die die Tests unten gezielt bewachen (Team-Lead-Auftrag):
  1. AC-3 — Schleifen-Falle: das Kanal-Set entsteht je PRESET, der Split muss
     je ORT (mit dessen EIGENER Dringlichkeit) laufen.
  2. AC-2/AC-4/AC-6/AC-7 — die rohe Kanalliste geht unverändert ans
     Protokoll, nur der Versand wird gefiltert; volle Unterdrückung darf
     nicht spurlos verschwinden (``alert_log.py:173-175``).
  3. AC-9 (Lese-Hälfte) — jeder Test hier lädt Presets über den ECHTEN
     Produktionspfad (``write_compare_briefings`` → ``load_compare_presets``
     → ``compare_preset_to_dict``), NIE über ein von Hand konstruiertes
     Python-Objekt mit direkt gesetztem Attribut. Der Trip-spezifische
     F002-Fallstrick (Attribut am Objekt statt am JSON-Schlüssel) kann sich
     hier strukturell nicht wiederholen — Compare-Presets sind im ganzen
     Testbestand immer Rohdicts, nie ein von Hand gebautes Domänenobjekt.
"""
from __future__ import annotations

import http.server
import json
import socket
import threading
import urllib.parse
import uuid
from datetime import date, datetime, timedelta, timezone

from app.config import Settings
from app.loader import save_location
from app.user import SavedLocation

from tests.helpers.alert_log_fixtures import gust_alert_trip, read_log, weather
from tests.tdd.test_alert_undelivered_hint import (
    _compare_preset as _briefing_preset,
    _entry,
    _hint_lines,
    _html_as_text,
    _run_compare_briefing,
    _seed,
    _setup_compare_locations,
)
from tests.tdd.test_compare_alert_channel_delivery import (
    _clean_user,
    _compare_preset as _dev_preset,
    _run_compare_alerts,
    _setup_single_location_preset,
    _setup_two_location_preset,
    _settings_all_channels as _settings_sms_capable,
    _write_tier,
)
from tests.tdd.test_compare_official_alert import (
    LAT_A,
    LON_A,
    _alert as _official_alert,
    _FakeOfficialAlertSource,
    _location as _official_location,
    _preset as _official_preset,
    _settings_all_channels as _official_settings_all_channels,
    _sources_backup,
    _write_presets,
    _write_user_tier,
)
from tests.tdd.test_compare_radar_alert import (
    _CoordFrameSource,
    _location as _radar_location,
    _radar_preset,
    _wet_frame,
    _write_preset_file,
)

# (#1595) Die frühere Konstante DATA_ROOT ist entfallen — die Presets legt
# ``_write_preset_file`` aus test_compare_radar_alert.py ab, das die Wurzel
# über ``get_data_root()`` auflöst.


# ═══════════════════════════ Transport-Stubs (echtes 127.0.0.1) ═══════════
#
# 1:1 Muster aus tests/tdd/test_alert_channel_threshold.py::_TelegramStub —
# derselbe Alarm-Dispatch-Pfad, dieselbe Beobachtungstechnik. Zusätzlich hier
# ein SMS-Stub (seven.io-API), weil AC-5/AC-6 (Regenradar) den Kanal
# erstmals scharf schalten.


def _free_port() -> int:
    s = socket.socket()
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class _TelegramStub:
    def __init__(self) -> None:
        self.sent: list[dict] = []
        sent = self.sent
        counter = {"mid": 6000}

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                try:
                    payload = json.loads(body.decode())
                except ValueError:
                    payload = {}
                sent.append(payload)
                counter["mid"] += 1
                resp = json.dumps(
                    {"ok": True, "result": {"message_id": counter["mid"]}}
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(resp)

            def log_message(self, *args):  # noqa: D401
                pass

        self.port = _free_port()
        self._server = http.server.HTTPServer(("127.0.0.1", self.port), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def texts(self) -> list[str]:
        return [p.get("text", "") for p in self.sent]

    def stop(self) -> None:
        self._server.shutdown()


class _SMSStub:
    def __init__(self) -> None:
        self.received: list[dict] = []
        received = self.received

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                data = urllib.parse.parse_qs(body.decode())
                received.append({k: v[0] for k, v in data.items()})
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"100")

            def log_message(self, *args):  # noqa: D401
                pass

        self.port = _free_port()
        self._server = http.server.HTTPServer(("127.0.0.1", self.port), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def texts(self) -> list[str]:
        return [r.get("text", "") for r in self.received]

    def stop(self) -> None:
        self._server.shutdown()


def _pin_transport_stubs(monkeypatch, telegram_stub: "_TelegramStub") -> None:
    """Herkunftssperre (#1476) auf 'production' pinnen (Muster
    test_alert_channel_threshold.py) — gemessen wird die Kanal-Schwelle,
    nicht die Herkunftsschicht. Betrifft Telegram UND SMS: beide Transporte
    haben denselben Guard (``output.channels.{telegram,sms}._guard_code_origin``)."""
    import output.channels.sms as sms_module
    import output.channels.telegram as tg_module

    monkeypatch.setattr(tg_module, "running_origin", lambda module_file: "production")
    monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", telegram_stub.base_url)
    monkeypatch.setattr(sms_module, "running_origin", lambda module_file: "production")


def _uid(prefix: str) -> str:
    return f"tdd-1461-s3b2b-{prefix}-{uuid.uuid4().hex[:6]}"


def _settings_email_and_telegram() -> Settings:
    """``can_send_email()`` UND ``can_send_telegram()`` == True. Telegram
    läuft über den lokalen Stub (kein echtes Bot-API-Konto nötig)."""
    return Settings(
        smtp_host="dummy.invalid", smtp_user="dummy", smtp_pass="dummy",
        mail_to="dummy@example.com",
        telegram_bot_token="tdd-1461-s3b2b-bot", telegram_chat_id="4711",
    )


# ═══════════════════════════════════ AC-1 ══════════════════════════════════
# Invariante — war bereits vor der Implementierung grün (keine Filterung
# existiert heute überhaupt), hier ergänzt, weil die Spec sie als eigenes
# Pflicht-AC führt und sie bislang von keinem Test bewacht wurde. Bewacht ab
# jetzt: die Implementierung darf einen unveränderten Ortsvergleich nicht
# stiller machen.


def test_ac1_ohne_gesetzte_schwelle_erreicht_die_meldung_alle_konfigurierten_kanaele(
    monkeypatch,
):
    """AC-1.

    GIVEN ein Ortsvergleich hat für keinen Kanal eine Schwelle eingestellt.
    WHEN  ein Änderungsalarm mit geringer Dringlichkeit (MINOR-Delta)
          ausgelöst wird.
    THEN  erreicht die Meldung genau die Kanäle, die auch vor dieser Änderung
          erreicht worden wären — E-Mail UND Telegram.
    """
    uid = _uid("ac1")
    preset_id = f"cp-ac1-{uuid.uuid4().hex[:6]}"
    tg_stub = _TelegramStub()
    _clean_user(uid)
    try:
        _pin_transport_stubs(monkeypatch, tg_stub)
        _setup_single_location_preset(uid, preset_id, "Ort-AC1", send_telegram=True)

        mails: list[tuple[str, str]] = []
        # anchor 2.0mm, Wert 14.0 -> Delta 12 -> Ratio 1.2 (Standard-Schwelle
        # 10mm) -> MINOR -> Dringlichkeit LOW.
        _run_compare_alerts(
            uid, _settings_email_and_telegram(), mails, {"loc-1": 14.0},
        )

        assert mails, "AC-1 Voraussetzung: E-Mail muss unverändert ankommen"
        assert tg_stub.texts(), (
            "AC-1: ohne gesetzte Schwelle muss eine gering-dringliche Meldung "
            f"Telegram unverändert erreichen, gesendet: {tg_stub.sent!r}"
        )
    finally:
        tg_stub.stop()
        _clean_user(uid)


def test_ac1_zwei_orte_unterschiedlicher_dringlichkeit_ohne_schwelle_bleibt_ein_versand(
    monkeypatch,
):
    """AC-1 (Team-Lead-Nachtrag — Regress-Waechter gegen die Schleifenfalle-
    Korrektur).

    GIVEN ein Ortsvergleich mit ZWEI Orten hat FUER KEINEN Kanal eine Schwelle
          eingestellt (derselbe Zwei-Orte-Aufbau wie AC-3, aber OHNE
          `alert_channel_thresholds`).
    WHEN  bei einem Alarm-Lauf ein Ort ('Graz') eine Meldung HOHER Dringlichkeit
          ausloest (MAJOR-Delta) und der ANDERE Ort ('Wien') eine Meldung
          GERINGER Dringlichkeit (MINOR-Delta).
    THEN  bleibt es bei GENAU EINEM Versand je Kanal (E-Mail UND Telegram) —
          nicht zwei. Beide Orte stehen in DERSELBEN Nachricht.

    Der Fang: eine Schleifen-Falle-Korrektur, die nach der DRINGLICHKEIT jedes
    Ortes gruppiert (statt nach der je Kanal ERLAUBTEN Ortsliste), erzeugt
    hier zwei Versand-Gruppen -- auch wenn der Nutzer gar keine Schwelle
    gesetzt hat. Das waere ein Regress auf AC-1: aus einer Mail werden zwei,
    ohne dass der Nutzer irgendetwas eingestellt hat (Kosten-Verdopplung,
    Widerspruch zum Epic-Ziel "eine Satelliten-SMS kostet Geld und Akku").

    Telegram laeuft hier bewusst im KURZSTIL (`telegram_style: "kurzform"`):
    im reichen Stil faechert JEDER Versand-Aufruf ohnehin eine Sprechblase je
    Ort auf (Issue #1467 S2 AG3a) -- ein Aufruf mit zwei Orten und zwei
    Aufrufe mit je einem Ort erzeugen dort ununterscheidbar zwei Bubbles. Der
    Kurzstil fasst dagegen ALLE Orte EINES Aufrufs zu GENAU EINER Nachricht
    zusammen (K-5) -- nur er macht "ein Aufruf" vs. "zwei Aufrufe" an der
    Telegram-Senke sichtbar.
    """
    uid = _uid("ac1b")
    preset_id = f"cp-ac1b-{uuid.uuid4().hex[:6]}"
    tg_stub = _TelegramStub()
    _clean_user(uid)
    try:
        _pin_transport_stubs(monkeypatch, tg_stub)
        _setup_two_location_preset(
            uid, preset_id, send_telegram=True,
            display_config={"telegram_style": "kurzform"},
        )
        # anchor beider Orte: 2.0mm (Fixture). "loc-graz" -> 30.0 (Delta 28,
        # Ratio 2.8 -> MAJOR -> HIGH). "loc-wien" -> 14.0 (Delta 12, Ratio
        # 1.2 -> MINOR -> LOW). KEINE Schwelle gesetzt -- Startwert "gering"
        # ueberall, beide Dringlichkeiten erreichen jeden Kanal.
        mails: list[tuple[str, str]] = []
        _run_compare_alerts(
            uid, _settings_email_and_telegram(), mails,
            {"loc-graz": 30.0, "loc-wien": 14.0},
        )

        assert len(mails) == 1, (
            "AC-1: ohne gesetzte Schwelle darf aus unterschiedlicher "
            f"Dringlichkeit der Orte KEIN zweiter E-Mail-Versand entstehen, "
            f"erhalten: {len(mails)} -- {mails!r}"
        )
        assert len(tg_stub.texts()) == 1, (
            "AC-1: ohne gesetzte Schwelle darf aus unterschiedlicher "
            f"Dringlichkeit der Orte KEIN zweiter Telegram-Versand entstehen "
            f"(Kurzstil fasst je Aufruf IMMER zu einer Nachricht zusammen — "
            f"zwei Nachrichten bedeuten zwei Aufrufe), erhalten: "
            f"{len(tg_stub.texts())} -- {tg_stub.texts()!r}"
        )

        mail_text = " ".join(body for _subject, body in mails)
        assert "Graz" in mail_text and "Wien" in mail_text, (
            f"AC-1: die eine E-Mail muss BEIDE Orte enthalten: {mail_text!r}"
        )
        # Kurzstil nennt keine Ortsnamen (K-5) -- die Ortszahl-Kodierung
        # bezeugt trotzdem, dass BEIDE Orte in DERSELBEN Nachricht stehen:
        # "1:"/"2:" fuer Graz (Position 1) und Wien (Position 2).
        tg_text = tg_stub.texts()[0]
        assert "1:" in tg_text and "2:" in tg_text, (
            "AC-1: die eine Kurzstil-Nachricht muss BEIDE Orte (Positionen 1 "
            f"und 2) enthalten: {tg_text!r}"
        )
    finally:
        tg_stub.stop()
        _clean_user(uid)


# ═══════════════════════════════════ AC-2 ══════════════════════════════════


def test_ac2_erhoehte_schwelle_blockt_nur_diesen_kanal_und_protokolliert_den_grund(
    monkeypatch,
):
    """AC-2.

    GIVEN ein Nutzer hat für Telegram eine erhöhte Schwelle ('HIGH')
          eingestellt, E-Mail bleibt beim Startwert.
    WHEN  ein Δ-Änderungsalarm mit geringer Dringlichkeit ausgelöst wird.
    THEN  erreicht die Meldung Telegram NICHT, E-Mail weiterhin — UND der
          Protokoll-Eintrag trägt für Telegram den Grund
          'below_channel_threshold' (NICHT 'delivery_failed'; genau die
          Verwechslung, die S3b-2a Adversary-Befund F001 beim Trip fing).

    Heute (RED): 'alert_channel_thresholds' wird an keiner Compare-
    Nahtstelle ausgewertet — Telegram bekommt die Meldung trotzdem.

    🔴 Adversary-Befund F004 (LOW): dieser Test beweist NICHT die separat
    behauptete Zusicherung „die rohe Kanalliste geht ans Protokoll" (nur der
    Versand wird gefiltert) — er prüft nur den Protokoll-GRUND bei
    TEILunterdrückung (E-Mail bleibt zugestellt). Der eigentliche Beleg für
    „roh ans Protokoll, auch bei vollständiger Unterdrückung" steht in AC-7
    (`test_ac7_alle_kanaele_unter_schwelle_landet_im_protokoll_und_briefing`)
    — dort verschwindet die Meldung trotz Unterdrückung ALLER Kanäle nicht
    spurlos aus dem Protokoll.
    """
    uid = _uid("ac2")
    preset_id = f"cp-ac2-{uuid.uuid4().hex[:6]}"
    tg_stub = _TelegramStub()
    _clean_user(uid)
    try:
        _pin_transport_stubs(monkeypatch, tg_stub)
        _setup_single_location_preset(
            uid, preset_id, "Ort-AC2", send_telegram=True,
            alert_channel_thresholds={"telegram": "HIGH"},
        )

        mails: list[tuple[str, str]] = []
        _run_compare_alerts(
            uid, _settings_email_and_telegram(), mails, {"loc-1": 14.0},
        )

        assert mails, "AC-2 Voraussetzung: E-Mail (unveränderter Kanal) muss ankommen"
        assert not tg_stub.sent, (
            "AC-2: Telegram hat eine erhöhte Schwelle (HIGH), die Meldung ist "
            f"nur gering-dringlich — sie darf Telegram NICHT erreichen. "
            f"Tatsächlich gesendet: {tg_stub.sent!r}"
        )

        log = read_log(uid)
        entries = [e for e in log["entries"] if e["entity_id"] == preset_id]
        assert len(entries) == 1, (
            "AC-2: eine TEILunterdrückte Meldung (E-Mail erreichbar) muss "
            f"unter 'entries' stehen, gefunden: {log['entries']!r}"
        )
        not_sent = {
            item["channel"]: item["reason"]
            for item in entries[0]["channels_not_sent"]
        }
        assert not_sent.get("telegram") == "below_channel_threshold", (
            "AC-2: telegram muss im Protokoll den Grund "
            "'below_channel_threshold' tragen — NICHT 'delivery_failed' (das "
            "wäre die Verwechslung aus Falle 2). Gefunden: "
            f"{not_sent!r}"
        )
        assert "email" in entries[0]["channels_sent"]
    finally:
        tg_stub.stop()
        _clean_user(uid)


# ═══════════════════════════════════ AC-3 ══════════════════════════════════


def test_ac3_zwei_orte_unterschiedlicher_dringlichkeit_werden_getrennt_gemessen(
    monkeypatch,
):
    """AC-3 — die Schleifen-Falle (Team-Lead-Pflichtfall).

    GIVEN ein Ortsvergleich mit ZWEI Orten hat für Telegram eine erhöhte
          Schwelle ('HIGH') eingestellt.
    WHEN  bei einem Alarm-Lauf EIN Ort ('Sturm') eine Meldung HOHER
          Dringlichkeit auslöst (MAJOR-Delta) und der ANDERE Ort ('Sanft')
          eine Meldung GERINGER Dringlichkeit (MINOR-Delta).
    THEN  erreicht Telegram die dringende Meldung ('Sturm'), aber NICHT die
          geringe ('Sanft') — jede Meldung wird an ihrer EIGENEN
          Dringlichkeit gemessen, nicht an der eines anderen Ortes desselben
          Vergleichs. E-Mail (unveränderte Schwelle) bekommt BEIDE Orte.

    Heute (RED): das Kanal-Set entsteht einmal je PRESET
    (``compare_alert.py:334``, ``_build_eval_config``), der Bündel-Versand
    läuft mit GENAU diesem einen Set für alle Orte — Telegram würde (sobald
    die Schwelle überhaupt ausgewertet wird) entweder BEIDE Orte bekommen
    oder KEINEN, nie „nur den dringenden". Ein Test mit nur einem Ort fängt
    diesen Fehler nicht (Spec-Auflage AC-3).
    """
    uid = _uid("ac3")
    preset_id = f"cp-ac3-{uuid.uuid4().hex[:6]}"
    tg_stub = _TelegramStub()
    _clean_user(uid)
    try:
        _pin_transport_stubs(monkeypatch, tg_stub)
        _setup_two_location_preset(
            uid, preset_id, send_telegram=True,
            alert_channel_thresholds={"telegram": "HIGH"},
        )
        # anchor beider Orte: 2.0mm (Fixture). "loc-graz" -> 30.0 (Delta 28,
        # Ratio 2.8 -> MAJOR -> HIGH). "loc-wien" -> 14.0 (Delta 12, Ratio
        # 1.2 -> MINOR -> LOW).
        mails: list[tuple[str, str]] = []
        _run_compare_alerts(
            uid, _settings_email_and_telegram(), mails,
            {"loc-graz": 30.0, "loc-wien": 14.0},
        )

        tg_texts = " ".join(tg_stub.texts())
        assert "Graz" in tg_texts, (
            "AC-3 Voraussetzung: die HOCH-dringliche Meldung (Graz, MAJOR) "
            f"muss Telegram trotz erhöhter Schwelle erreichen: {tg_stub.texts()!r}"
        )
        assert "Wien" not in tg_texts, (
            "AC-3: die GERING-dringliche Meldung (Wien, MINOR) darf Telegram "
            "NICHT erreichen, obwohl sie im selben Preset-Lauf steckt wie die "
            f"dringende Meldung von Graz. Tatsächlich gesendet: {tg_stub.texts()!r}"
        )

        mail_text = " ".join(body for _subject, body in mails)
        assert "Graz" in mail_text and "Wien" in mail_text, (
            "AC-3: E-Mail hat KEINE erhöhte Schwelle — beide Orte müssen dort "
            f"weiterhin erscheinen: {mail_text!r}"
        )
    finally:
        tg_stub.stop()
        _clean_user(uid)


# ═══════════════════════════════════ AC-4 ══════════════════════════════════


def test_ac4_erhoehte_schwelle_blockt_amtliche_warnung_geringer_dringlichkeit(
    monkeypatch,
):
    """AC-4.

    GIVEN ein Nutzer hat für Telegram eine erhöhte Schwelle ('HIGH')
          eingestellt.
    WHEN  eine amtliche Warnung geringerer Dringlichkeit (Stufe 2, gelb ->
          LOW) einen eigenständigen Ortsvergleich-Alarm auslöst.
    THEN  bleibt Telegram ebenso stumm wie beim Δ-Änderungsalarm (AC-2),
          E-Mail bleibt zugestellt, und das Protokoll trägt den Grund
          'below_channel_threshold' für Telegram.

    Heute (RED): ``compare_official_alert.py:271`` wertet
    ``alert_channel_thresholds`` nicht aus.
    """
    from services.compare_official_alert import CompareOfficialAlertService
    from services.official_alerts import register_official_alert_source

    uid = _uid("ac4")
    preset_id = f"cp-ac4-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    b, backup = _sources_backup()
    b._REGISTERED_SOURCES.clear()
    try:
        _write_user_tier(uid, "premium")
        save_location(_official_location("loc-a", "Ort-AC4", LAT_A, LON_A), user_id=uid)
        preset = _official_preset(
            preset_id, ["loc-a"], ["dummy@example.com"], send_telegram=True,
        )
        preset["alert_channel_thresholds"] = {"telegram": "HIGH"}
        _write_presets(uid, [preset])
        register_official_alert_source(
            # Default-Level 2 (gelb) -> urgency_from_official_level(2) == 'LOW'.
            _FakeOfficialAlertSource(LAT_A, LON_A, [_official_alert(level=2)])
        )

        mail_calls: list[str] = []
        tg_calls: list[str] = []
        svc = CompareOfficialAlertService(
            settings=_official_settings_all_channels(), user_id=uid,
            mail_sink=lambda subject, body: mail_calls.append(body),
            telegram_sink=lambda text: tg_calls.append(text),
        )
        svc.check_all_compare_presets()

        assert len(mail_calls) == 1, (
            f"AC-4 Voraussetzung: E-Mail muss zugestellt werden, erhalten "
            f"{len(mail_calls)}"
        )
        assert tg_calls == [], (
            "AC-4: Telegram hat eine erhöhte Schwelle (HIGH), die amtliche "
            f"Warnung ist nur LOW-dringlich — sie darf Telegram NICHT "
            f"erreichen. Tatsächlich gesendet: {tg_calls!r}"
        )

        log = read_log(uid)
        entries = [e for e in log["entries"] if e["entity_id"] == preset_id]
        assert len(entries) == 1, f"AC-4: Protokoll-Eintrag fehlt: {log!r}"
        not_sent = {
            item["channel"]: item["reason"]
            for item in entries[0]["channels_not_sent"]
        }
        assert not_sent.get("telegram") == "below_channel_threshold", (
            f"AC-4: falscher/fehlender Protokoll-Grund für telegram: {not_sent!r}"
        )
    finally:
        b._REGISTERED_SOURCES.clear()
        b._REGISTERED_SOURCES.extend(backup)
        _clean_user(uid)


# ═══════════════════════════════════ AC-5 ══════════════════════════════════


def test_ac5_regenradar_erreicht_jetzt_auch_telegram_und_sms(monkeypatch):
    """AC-5 — die zweite, unabhängige Verhaltensänderung dieser Scheibe.

    GIVEN ein Ortsvergleich hat Telegram UND SMS als Alarm-Kanal
          eingeschaltet (keine Schwelle über 'gering' gesetzt).
    WHEN  ein durch Regenradar ausgelöster Alarm eintritt.
    THEN  erreicht die Meldung Telegram UND SMS ebenso wie E-Mail.

    Heute (RED): ``compare_radar_alert.py:131``/``:150`` verdrahtet die
    Kanalliste hart auf ``{"email"}`` — unabhängig vom Kanal-Opt-in des
    Nutzers (verfallene Begründung, s. Spec „Implementation Details" Punkt 3
    / Context-Dokument Risiko 3).
    """
    from services.compare_radar_alert import CompareRadarAlertService
    from services.radar_service import RadarNowcastService

    uid = _uid("ac5")
    preset_id = f"cp-ac5-{uuid.uuid4().hex[:6]}"
    tg_stub = _TelegramStub()
    sms_stub = _SMSStub()
    _clean_user(uid)
    try:
        _pin_transport_stubs(monkeypatch, tg_stub)
        _write_tier(uid, "premium")
        loc = _radar_location("loc-a", "Ort-AC5", 46.0207, 7.7491)
        save_location(loc, user_id=uid)
        preset = _radar_preset(
            preset_id, ["loc-a"], ["dummy@example.com"], radar_alert_enabled=True,
        )
        preset["send_telegram"] = True
        preset["send_sms"] = True
        _write_preset_file(uid, [preset])

        # Leichter, nicht-konvektiver Regen (0.6 mm/h) -> urgency_from_radar
        # == 'LOW' (Startschwelle 'gering' reicht dafür unverändert aus).
        frame_source = _CoordFrameSource({(46.0207, 7.7491): _wet_frame(8, rate=0.6)})
        radar_service = RadarNowcastService(frame_source=frame_source)

        mails: list[tuple[str, str]] = []
        svc = CompareRadarAlertService(
            settings=_settings_sms_capable(sms_stub.port), user_id=uid,
            radar_service=radar_service,
            mail_sink=lambda subject, body: mails.append((subject, body)),
        )
        sent = svc.check_all_compare_presets()

        assert sent == 1, f"AC-5 Voraussetzung: Radar-Alarm muss ausgelöst worden sein: {sent}"
        assert mails, "AC-5 Voraussetzung: E-Mail muss zugestellt werden"
        assert tg_stub.sent, (
            "AC-5: Telegram ist eingeschaltet und trägt keine Schwelle über "
            f"'gering' — der Regenradar-Alarm muss ihn erreichen (vor dem Fix "
            f"ausschließlich E-Mail). Gesendet: {tg_stub.sent!r}"
        )
        assert sms_stub.received, (
            "AC-5: SMS ist eingeschaltet und muss den Regenradar-Alarm "
            f"ebenfalls erreichen. Empfangen: {sms_stub.received!r}"
        )
    finally:
        tg_stub.stop()
        sms_stub.stop()
        _clean_user(uid)


# ═══════════════════════════════════ AC-6 ══════════════════════════════════


def test_ac6_erhoehte_schwelle_blockt_regenradar_alarm_auf_diesem_kanal(monkeypatch):
    """AC-6.

    GIVEN ein Nutzer hat für Telegram UND SMS eine erhöhte Schwelle ('HIGH')
          eingestellt.
    WHEN  ein durch Regenradar ausgelöster Alarm geringerer Dringlichkeit
          auftritt (derselbe leichte, nicht-konvektive Regen wie AC-5).
    THEN  bleiben Telegram UND SMS ebenso stumm wie bei den beiden anderen
          Alarmarten (AC-2/AC-4) — E-Mail bleibt zugestellt.
    """
    from services.compare_radar_alert import CompareRadarAlertService
    from services.radar_service import RadarNowcastService

    uid = _uid("ac6")
    preset_id = f"cp-ac6-{uuid.uuid4().hex[:6]}"
    tg_stub = _TelegramStub()
    sms_stub = _SMSStub()
    _clean_user(uid)
    try:
        _pin_transport_stubs(monkeypatch, tg_stub)
        _write_tier(uid, "premium")
        loc = _radar_location("loc-a", "Ort-AC6", 46.0207, 7.7491)
        save_location(loc, user_id=uid)
        preset = _radar_preset(
            preset_id, ["loc-a"], ["dummy@example.com"], radar_alert_enabled=True,
        )
        preset["send_telegram"] = True
        preset["send_sms"] = True
        preset["alert_channel_thresholds"] = {"telegram": "HIGH", "sms": "HIGH"}
        _write_preset_file(uid, [preset])

        frame_source = _CoordFrameSource({(46.0207, 7.7491): _wet_frame(8, rate=0.6)})
        radar_service = RadarNowcastService(frame_source=frame_source)

        mails: list[tuple[str, str]] = []
        svc = CompareRadarAlertService(
            settings=_settings_sms_capable(sms_stub.port), user_id=uid,
            radar_service=radar_service,
            mail_sink=lambda subject, body: mails.append((subject, body)),
        )
        svc.check_all_compare_presets()

        assert mails, "AC-6 Voraussetzung: E-Mail (unveränderter Kanal) muss ankommen"
        assert not tg_stub.sent, (
            f"AC-6: Telegram muss bei HIGH-Schwelle stumm bleiben: {tg_stub.sent!r}"
        )
        assert not sms_stub.received, (
            f"AC-6: SMS muss bei HIGH-Schwelle stumm bleiben: {sms_stub.received!r}"
        )

        log = read_log(uid)
        entries = [e for e in log["entries"] if e["entity_id"] == preset_id]
        assert len(entries) == 1, f"AC-6: Protokoll-Eintrag fehlt: {log!r}"
        not_sent = {
            item["channel"]: item["reason"]
            for item in entries[0]["channels_not_sent"]
        }
        assert not_sent.get("telegram") == "below_channel_threshold"
        assert not_sent.get("sms") == "below_channel_threshold"
    finally:
        tg_stub.stop()
        sms_stub.stop()
        _clean_user(uid)


# ═══════════════════════════════════ AC-7 ══════════════════════════════════


def test_ac7_alle_kanaele_unter_schwelle_landet_im_protokoll_und_briefing(
    monkeypatch, tmp_path,
):
    """AC-7.

    GIVEN E-Mail UND Telegram haben beide eine hohe Schwelle ('HIGH') —
          E-Mail ist beim Ortsvergleich IMMER aktiv (ADR-0021/AG1), eine
          vollständige Unterdrückung erfordert deshalb, BEIDE tatsächlich
          aktiven Kanäle über die Schwelle zu heben.
    WHEN  ein Δ-Änderungsalarm mit geringer Dringlichkeit ausgelöst wird.
    THEN  erreicht die Meldung KEINEN Kanal, das Protokoll erhält GENAU
          EINEN Eintrag unter 'not_delivered' (NICHT 'entries' — für Go
          unsichtbar, D4 aus #1459), und das nächste Vergleichs-Briefing
          weist die Meldung als nicht zugestellt aus (S3b-1-Sichtbarkeit,
          bereits entitätsblind — hier zum ersten Mal wirklich AUSGELÖST
          über den echten Compare-Alarmpfad statt von Hand konstruiert).
    """
    uid = _uid("ac7")
    preset_id = f"cp-ac7-{uuid.uuid4().hex[:6]}"
    tg_stub = _TelegramStub()
    _clean_user(uid)
    try:
        from services.alert_briefing_anchor import record_briefing_sent

        _pin_transport_stubs(monkeypatch, tg_stub)
        _setup_single_location_preset(
            uid, preset_id, "Ort-AC7", send_telegram=True,
            empfaenger=["dummy@example.com"],
            alert_channel_thresholds={"email": "HIGH", "telegram": "HIGH"},
        )
        anchor_zeit = datetime.now(timezone.utc) - timedelta(hours=6)
        record_briefing_sent(
            user_id=uid, entity_id=preset_id, entity_type="compare", at=anchor_zeit,
        )

        mails: list[tuple[str, str]] = []
        _run_compare_alerts(
            uid, _settings_email_and_telegram(), mails, {"loc-1": 14.0},
        )

        assert not mails and not tg_stub.sent, (
            "AC-7 Voraussetzung: BEIDE aktiven Kanäle haben eine hohe "
            f"Schwelle — weder E-Mail ({mails!r}) noch Telegram "
            f"({tg_stub.sent!r}) dürfen ankommen"
        )

        log = read_log(uid)
        entries = [e for e in log["entries"] if e["entity_id"] == preset_id]
        not_delivered = [e for e in log["not_delivered"] if e["entity_id"] == preset_id]
        assert entries == [], (
            "AC-7: bei Totalausfall darf KEIN Eintrag unter 'entries' stehen "
            f"(für Go sichtbar, D4) — gefunden: {entries!r}"
        )
        assert len(not_delivered) == 1, (
            "AC-7: die vollständig unterdrückte Meldung muss GENAU EINEN "
            f"Eintrag unter 'not_delivered' erzeugen, gefunden: {not_delivered!r}"
        )

        preset_for_briefing = _dev_preset(
            preset_id, ["loc-1"], empfaenger=["dummy@example.com"],
        )
        html = _run_compare_briefing(uid, preset_for_briefing, tmp_path)
        zeilen = _hint_lines(_html_as_text(html))
        assert len(zeilen) == 1, (
            "AC-7: das nächste Vergleichs-Briefing muss die unterdrückte "
            f"Meldung als nicht zugestellt ausweisen, gefunden {zeilen!r}"
        )
    finally:
        tg_stub.stop()
        _clean_user(uid)


# ═══════════════════════════ AC-7b/AC-7c (Adversary F004) ══════════════════
# Befund F004 (MEDIUM, Fix-Loop 2): die rote Linie #638 ("das Protokoll
# bekommt die ROHE Kanalliste, nur der Versand wird gefiltert") war fuer den
# amtlichen Warnung-Pfad (compare_official_alert.py) und den Regenradar-Pfad
# (compare_radar_alert.py) UNGEDECKT -- nur AC-7 (Δ-Änderungspfad) bewachte
# sie. Beide folgenden Tests sind das AC-7-Äquivalent fuer die beiden
# uebrigen Alarmwege: alle aktiven Kanaele ueber der Schwelle, Meldung
# geringer Dringlichkeit -> Totalausfall, Protokoll-Eintrag in
# 'not_delivered' (NICHT 'entries'), und dessen 'channels_not_sent' MUSS
# beide Kanaele nennen (Beweis, dass 'effective_channels' roh -- nicht
# gefiltert auf leer -- an append_entry ging: eine leere/gefilterte Liste
# haette hier gar keine channels_not_sent-Eintraege erzeugt).


def test_ac7b_official_alle_kanaele_unter_schwelle_landet_im_protokoll_und_briefing(
    monkeypatch, tmp_path,
):
    """AC-7-Äquivalent fuer den amtlichen Warnung-Pfad (Adversary F004).

    GIVEN E-Mail UND Telegram haben beide eine hohe Schwelle ('HIGH').
    WHEN  eine amtliche Warnung geringer Dringlichkeit (Stufe 2, gelb -> LOW)
          einen eigenständigen Ortsvergleich-Alarm auslöst.
    THEN  erreicht die Meldung KEINEN Kanal, das Protokoll erhält GENAU EINEN
          Eintrag unter 'not_delivered' — dessen 'channels_not_sent' nennt
          BEIDE Kanäle (E-Mail und Telegram, roh, nicht gefiltert auf leer) —
          und das nächste Vergleichs-Briefing weist die Meldung als nicht
          zugestellt aus.
    """
    from services.compare_official_alert import CompareOfficialAlertService
    from services.official_alerts import register_official_alert_source

    uid = _uid("ac7b")
    preset_id = f"cp-ac7b-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    b, backup = _sources_backup()
    b._REGISTERED_SOURCES.clear()
    try:
        from services.alert_briefing_anchor import record_briefing_sent

        _write_user_tier(uid, "premium")
        save_location(_official_location("loc-a", "Ort-AC7b", LAT_A, LON_A), user_id=uid)
        preset = _official_preset(
            preset_id, ["loc-a"], ["dummy@example.com"], send_telegram=True,
        )
        preset["alert_channel_thresholds"] = {"email": "HIGH", "telegram": "HIGH"}
        _write_presets(uid, [preset])
        register_official_alert_source(
            # Default-Level 2 (gelb) -> urgency_from_official_level(2) == 'LOW'.
            _FakeOfficialAlertSource(LAT_A, LON_A, [_official_alert(level=2)])
        )
        anchor_zeit = datetime.now(timezone.utc) - timedelta(hours=6)
        record_briefing_sent(
            user_id=uid, entity_id=preset_id, entity_type="compare", at=anchor_zeit,
        )

        mail_calls: list[str] = []
        tg_calls: list[str] = []
        svc = CompareOfficialAlertService(
            settings=_official_settings_all_channels(), user_id=uid,
            mail_sink=lambda subject, body: mail_calls.append(body),
            telegram_sink=lambda text: tg_calls.append(text),
        )
        svc.check_all_compare_presets()

        assert not mail_calls and not tg_calls, (
            "AC-7b Voraussetzung: BEIDE aktiven Kanäle haben eine hohe "
            f"Schwelle — weder E-Mail ({mail_calls!r}) noch Telegram "
            f"({tg_calls!r}) dürfen ankommen"
        )

        log = read_log(uid)
        entries = [e for e in log["entries"] if e["entity_id"] == preset_id]
        not_delivered = [e for e in log["not_delivered"] if e["entity_id"] == preset_id]
        assert entries == [], (
            "AC-7b: bei Totalausfall darf KEIN Eintrag unter 'entries' stehen "
            f"(für Go sichtbar, D4) — gefunden: {entries!r}"
        )
        assert len(not_delivered) == 1, (
            "AC-7b: die vollständig unterdrückte Meldung muss GENAU EINEN "
            f"Eintrag unter 'not_delivered' erzeugen, gefunden: {not_delivered!r}"
        )
        channels_not_sent = {
            item["channel"] for item in not_delivered[0]["channels_not_sent"]
        }
        assert {"email", "telegram"} <= channels_not_sent, (
            "AC-7b (F004): 'channels_not_sent' muss BEIDE Kanäle nennen — das "
            "beweist, dass die ROHE Kanalliste ans Protokoll ging (eine "
            "bereits gefilterte/leere Liste hätte hier KEINE Einträge "
            f"erzeugt). Gefunden: {channels_not_sent!r}"
        )

        preset_for_briefing = _dev_preset(
            preset_id, ["loc-a"], empfaenger=["dummy@example.com"],
        )
        html = _run_compare_briefing(uid, preset_for_briefing, tmp_path)
        zeilen = _hint_lines(_html_as_text(html))
        assert len(zeilen) == 1, (
            "AC-7b: das nächste Vergleichs-Briefing muss die unterdrückte "
            f"Meldung als nicht zugestellt ausweisen, gefunden {zeilen!r}"
        )
    finally:
        b._REGISTERED_SOURCES.clear()
        b._REGISTERED_SOURCES.extend(backup)
        _clean_user(uid)


def test_ac7c_radar_alle_kanaele_unter_schwelle_landet_im_protokoll_und_briefing(
    monkeypatch, tmp_path,
):
    """AC-7-Äquivalent fuer den Regenradar-Pfad (Adversary F004).

    GIVEN E-Mail UND Telegram haben beide eine hohe Schwelle ('HIGH').
    WHEN  ein durch Regenradar ausgelöster Alarm geringer Dringlichkeit
          eintritt.
    THEN  erreicht die Meldung KEINEN Kanal, das Protokoll erhält GENAU EINEN
          Eintrag unter 'not_delivered' — dessen 'channels_not_sent' nennt
          BEIDE Kanäle (E-Mail und Telegram, roh) — und das nächste
          Vergleichs-Briefing weist die Meldung als nicht zugestellt aus.
    """
    from services.compare_radar_alert import CompareRadarAlertService
    from services.radar_service import RadarNowcastService

    uid = _uid("ac7c")
    preset_id = f"cp-ac7c-{uuid.uuid4().hex[:6]}"
    tg_stub = _TelegramStub()
    _clean_user(uid)
    try:
        from services.alert_briefing_anchor import record_briefing_sent

        _pin_transport_stubs(monkeypatch, tg_stub)
        _write_tier(uid, "premium")
        loc = _radar_location("loc-a", "Ort-AC7c", 46.0207, 7.7491)
        save_location(loc, user_id=uid)
        preset = _radar_preset(
            preset_id, ["loc-a"], ["dummy@example.com"], radar_alert_enabled=True,
        )
        preset["send_telegram"] = True
        preset["alert_channel_thresholds"] = {"email": "HIGH", "telegram": "HIGH"}
        _write_preset_file(uid, [preset])
        anchor_zeit = datetime.now(timezone.utc) - timedelta(hours=6)
        record_briefing_sent(
            user_id=uid, entity_id=preset_id, entity_type="compare", at=anchor_zeit,
        )

        # Leichter, nicht-konvektiver Regen (0.6 mm/h) -> urgency_from_radar
        # == 'LOW' (dieselbe Dringlichkeit wie AC-5/AC-6).
        frame_source = _CoordFrameSource({(46.0207, 7.7491): _wet_frame(8, rate=0.6)})
        radar_service = RadarNowcastService(frame_source=frame_source)

        mails: list[tuple[str, str]] = []
        svc = CompareRadarAlertService(
            settings=_settings_email_and_telegram(), user_id=uid,
            radar_service=radar_service,
            mail_sink=lambda subject, body: mails.append((subject, body)),
        )
        svc.check_all_compare_presets()

        assert not mails and not tg_stub.sent, (
            "AC-7c Voraussetzung: BEIDE aktiven Kanäle haben eine hohe "
            f"Schwelle — weder E-Mail ({mails!r}) noch Telegram "
            f"({tg_stub.sent!r}) dürfen ankommen"
        )

        log = read_log(uid)
        entries = [e for e in log["entries"] if e["entity_id"] == preset_id]
        not_delivered = [e for e in log["not_delivered"] if e["entity_id"] == preset_id]
        assert entries == [], (
            "AC-7c: bei Totalausfall darf KEIN Eintrag unter 'entries' stehen "
            f"(für Go sichtbar, D4) — gefunden: {entries!r}"
        )
        assert len(not_delivered) == 1, (
            "AC-7c: die vollständig unterdrückte Meldung muss GENAU EINEN "
            f"Eintrag unter 'not_delivered' erzeugen, gefunden: {not_delivered!r}"
        )
        channels_not_sent = {
            item["channel"] for item in not_delivered[0]["channels_not_sent"]
        }
        assert {"email", "telegram"} <= channels_not_sent, (
            "AC-7c (F004): 'channels_not_sent' muss BEIDE Kanäle nennen — das "
            "beweist, dass die ROHE Kanalliste ans Protokoll ging (eine "
            "bereits gefilterte/leere Liste hätte hier KEINE Einträge "
            f"erzeugt). Gefunden: {channels_not_sent!r}"
        )

        preset_for_briefing = _dev_preset(
            preset_id, ["loc-a"], empfaenger=["dummy@example.com"],
        )
        html = _run_compare_briefing(uid, preset_for_briefing, tmp_path)
        zeilen = _hint_lines(_html_as_text(html))
        assert len(zeilen) == 1, (
            "AC-7c: das nächste Vergleichs-Briefing muss die unterdrückte "
            f"Meldung als nicht zugestellt ausweisen, gefunden {zeilen!r}"
        )
    finally:
        tg_stub.stop()
        _clean_user(uid)


# ═══════════════════════════════════ AC-8 ══════════════════════════════════


def test_ac8_grund_ist_deutscher_klartext_kein_interner_bezeichner(tmp_path):
    """AC-8.

    GIVEN eine Meldung eines Ortsvergleichs wurde wegen der Kanal-Schwelle
          unterdrückt — das Protokoll trägt den Grund
          'below_channel_threshold' für einen sonst eingeschalteten Kanal
          (dieselbe, bereits geteilte Bezeichnung wie beim Trip, S3b-2a).
    WHEN  das nächste Vergleichs-Briefing erzeugt wird.
    THEN  nennt die Vorfall-Zeile einen deutschen, lesbaren Grund — NICHT
          den rohen internen Bezeichner.

    🔴 Scope-Grenze (Team-Lead-Rückfrage, damit der Adversary weiß, wohin er
    sehen muss): dieser Test schreibt den Protokoll-Eintrag PER ``_seed()``
    von Hand — er läuft NICHT über einen echten Compare-Alarmpfad und prüft
    deshalb NUR, dass die (entitätsblinde, seit S3b-1 fertige) Anzeige-Kette
    ``below_channel_threshold`` für Ortsvergleiche korrekt ins Deutsche
    übersetzt, sobald der Grund im Protokoll STEHT. Er beweist NICHT, dass
    ``compare_alert.py``/``compare_official_alert.py``/
    ``compare_radar_alert.py`` diesen Grund beim echten Filtern auch
    tatsächlich SCHREIBEN — bliebe diese Weitergabe unimplementiert, bliebe
    dieser Test unverändert grün (er würde die Lücke NICHT fangen). Die
    Weitergabe selbst (roher Grund im echten Dispatch) wird durch die
    Log-Assertions in AC-2/AC-4/AC-6/AC-7 bewacht — dort läuft der ECHTE
    Alarm-Dispatch und `entries[0]["channels_not_sent"]` wird gegen
    `"below_channel_threshold"` geprüft.
    """
    uid = _uid("ac8")
    preset_id = f"cp-ac8-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    try:
        _setup_compare_locations(uid)
        jetzt = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        vorfall = jetzt - timedelta(hours=2)
        _seed(
            uid, entity_id=preset_id, entity_type="compare",
            letztes_briefing=jetzt - timedelta(hours=6),
            not_delivered=[_entry(
                entity_id=preset_id, entity_type="compare",
                sent_at=vorfall, metrics=(("gust", "max"),),
                reason="forecast_change", channels_sent=("email",),
                not_sent=(("telegram", "below_channel_threshold"),),
            )],
        )

        html = _run_compare_briefing(
            uid, _briefing_preset(uid, preset_id), tmp_path,
        )
        text = _html_as_text(html)
        zeilen = _hint_lines(text)
        assert len(zeilen) == 1, (
            f"AC-8 Voraussetzung: genau eine Vorfall-Zeile erwartet, "
            f"gefunden {zeilen!r}"
        )
        zeile = zeilen[0]
        assert "below_channel_threshold" not in zeile, (
            "AC-8: der interne Bezeichner darf NICHT im Text stehen: "
            f"{zeile!r}"
        )
        assert "Schwelle" in zeile, (
            f"AC-8: die Zeile muss einen deutschen, lesbaren Grund nennen "
            f"(z.B. 'Schwelle'), gefunden: {zeile!r}"
        )
    finally:
        _clean_user(uid)


# ═══════════════════════════════════ AC-11 ═════════════════════════════════


def test_ac11_zwei_nutzer_je_eigene_schwelle_ohne_vermischung(monkeypatch):
    """AC-11.

    GIVEN zwei verschiedene Nutzer mit je eigenem Ortsvergleich: Nutzer A hat
          Telegram auf 'HIGH' gesetzt, Nutzer B hat Telegram unverändert bei
          'LOW' (Startwert) belassen.
    WHEN  bei BEIDEN im selben Testlauf ein Alarm mit geringer Dringlichkeit
          ausgelöst wird.
    THEN  wirkt bei jedem Nutzer NUR seine eigene Einstellung — Mandanten-
          trennung in BEIDE Richtungen geprüft.
    """
    uid_hoch = _uid("ac11-hoch")
    uid_gering = _uid("ac11-gering")
    preset_hoch = f"cp-ac11-hoch-{uuid.uuid4().hex[:6]}"
    preset_gering = f"cp-ac11-gering-{uuid.uuid4().hex[:6]}"
    tg_hoch, tg_gering = _TelegramStub(), _TelegramStub()
    _clean_user(uid_hoch)
    _clean_user(uid_gering)
    try:
        assert uid_hoch != "default" and uid_gering != "default"

        _pin_transport_stubs(monkeypatch, tg_hoch)
        _setup_single_location_preset(
            uid_hoch, preset_hoch, "Ort-Hoch", send_telegram=True,
            alert_channel_thresholds={"telegram": "HIGH"},
        )
        mails_hoch: list[tuple[str, str]] = []
        _run_compare_alerts(
            uid_hoch, _settings_email_and_telegram(), mails_hoch, {"loc-1": 14.0},
        )

        _pin_transport_stubs(monkeypatch, tg_gering)
        _setup_single_location_preset(
            uid_gering, preset_gering, "Ort-Gering", send_telegram=True,
        )
        mails_gering: list[tuple[str, str]] = []
        _run_compare_alerts(
            uid_gering, _settings_email_and_telegram(), mails_gering, {"loc-1": 14.0},
        )

        assert not tg_hoch.sent, (
            "AC-11: Nutzer mit HOHER Telegram-Schwelle darf bei geringer "
            f"Dringlichkeit keinen Telegram-Alarm bekommen: {tg_hoch.sent!r}"
        )
        assert tg_gering.sent, (
            "AC-11: Nutzer mit GERINGER (Startwert-)Telegram-Schwelle muss "
            "denselben Alarm weiterhin auf Telegram bekommen — seine "
            f"Einstellung darf durch Nutzer A NICHT beeinflusst werden: "
            f"{tg_gering.sent!r}"
        )
    finally:
        tg_hoch.stop()
        tg_gering.stop()
        _clean_user(uid_hoch)
        _clean_user(uid_gering)


# ═══════════════════════════════════ AC-12 ═════════════════════════════════


def test_ac12_kachel_und_archiv_quelle_entries_unveraendert_bei_normalem_alarm(
    monkeypatch,
):
    """AC-12.

    GIVEN ein Alarm-Lauf eines Ortsvergleichs, bei dem KEINE Kanal-Schwelle
          etwas unterdrückt (Startwert 'gering' <= Dringlichkeit der
          Meldung).
    WHEN  die für Cockpit-Kachel und Archiv-Statistik maßgebliche
          Protokoll-Quelle ('entries', D4 aus #1459) danach gelesen wird.
    THEN  zeigt sie exakt EINEN Eintrag — dieselbe Zahl wie vor dieser
          Änderung. 'not_delivered' bleibt leer (kein Vorfall).
    """
    uid = _uid("ac12")
    preset_id = f"cp-ac12-{uuid.uuid4().hex[:6]}"
    tg_stub = _TelegramStub()
    _clean_user(uid)
    try:
        _pin_transport_stubs(monkeypatch, tg_stub)
        _setup_single_location_preset(uid, preset_id, "Ort-AC12", send_telegram=True)
        # Keine Schwelle gesetzt -- Startwert 'gering' überall.

        mails: list[tuple[str, str]] = []
        sent = _run_compare_alerts(
            uid, _settings_email_and_telegram(), mails, {"loc-1": 14.0},
        )

        assert sent == 1, f"AC-12 Voraussetzung: der Alarm muss auslösen: {sent}"
        log = read_log(uid)
        entries = [e for e in log["entries"] if e["entity_id"] == preset_id]
        not_delivered = [e for e in log["not_delivered"] if e["entity_id"] == preset_id]
        assert len(entries) == 1, (
            "AC-12: ein normaler, nicht durch die Schwelle betroffener Alarm "
            f"muss GENAU EINEN Eintrag unter 'entries' erzeugen, gefunden "
            f"{len(entries)}: {entries!r}"
        )
        assert not_delivered == [], (
            f"AC-12: kein Vorfall erwartet, gefunden: {not_delivered!r}"
        )
    finally:
        tg_stub.stop()
        _clean_user(uid)


def test_ac12b_gemischter_lauf_erzeugt_dieselbe_kachel_relevante_zahl_wie_vorher(
    monkeypatch,
):
    """AC-12 (Vollstaendigkeitspruefung Fix-Loop 3, Punkt 3) — der eigentlich
    verlangte Fall.

    Der bestehende Test oben (test_ac12_...) laesst einen Alarm OHNE jede
    Unterdrueckung laufen — das AC selbst verlangt aber einen Lauf, der
    ZUGESTELLTE UND unterdrueckte Meldungen GLEICHZEITIG erzeugt, und dass
    die fuer Kachel/Statistik massgebliche Quelle ('entries', D4 aus #1459)
    danach DIESELBE Zahl zeigt wie vor dieser Aenderung.

    GIVEN zwei identische Alarm-Laeufe desselben Ortsvergleichs-Setups: einer
          OHNE gesetzte Schwelle (Baseline "vorher"), einer MIT einer
          Telegram-Schwelle, die E-Mail zustellt UND Telegram unterdrueckt
          (der "gemischte" Lauf — zugestellt UND unterdrueckt im selben
          Preset-Lauf, wie AC-2).
    WHEN  bei beiden Laeufen die fuer Kachel/Statistik massgebliche
          Protokoll-Quelle ('entries') gelesen wird.
    THEN  zeigt der gemischte Lauf EXAKT dieselbe Zahl ('entries'-Eintraege
          fuer diesen Preset) wie die Baseline OHNE Schwelle — die
          Kanal-Schwelle aendert NUR, welcher Kanal die Meldung erreicht,
          nie die Zaehllogik fuer Kachel/Statistik (D4).
    """
    uid_baseline = _uid("ac12b-baseline")
    uid_gemischt = _uid("ac12b-gemischt")
    preset_baseline = f"cp-ac12b-baseline-{uuid.uuid4().hex[:6]}"
    preset_gemischt = f"cp-ac12b-gemischt-{uuid.uuid4().hex[:6]}"
    tg_baseline = _TelegramStub()
    tg_gemischt = _TelegramStub()
    _clean_user(uid_baseline)
    _clean_user(uid_gemischt)
    try:
        # ── Baseline: identischer Alarm, KEINE Schwelle gesetzt ──────────────
        _pin_transport_stubs(monkeypatch, tg_baseline)
        _setup_single_location_preset(
            uid_baseline, preset_baseline, "Ort-AC12b-Baseline", send_telegram=True,
        )
        mails_baseline: list[tuple[str, str]] = []
        sent_baseline = _run_compare_alerts(
            uid_baseline, _settings_email_and_telegram(), mails_baseline, {"loc-1": 14.0},
        )
        assert sent_baseline == 1, "AC-12b Voraussetzung (Baseline): der Alarm muss auslösen"
        assert mails_baseline and tg_baseline.sent, (
            "AC-12b Voraussetzung (Baseline): OHNE Schwelle müssen BEIDE "
            "Kanäle die Meldung erreichen"
        )
        log_baseline = read_log(uid_baseline)
        entries_baseline = [
            e for e in log_baseline["entries"] if e["entity_id"] == preset_baseline
        ]

        # ── Gemischter Lauf: derselbe Alarm, Telegram-Schwelle blockt NUR ────
        # Telegram — E-Mail bleibt zugestellt (zugestellt UND unterdrückt im
        # selben Preset-Lauf, exakt das AC-12-Szenario).
        _pin_transport_stubs(monkeypatch, tg_gemischt)
        _setup_single_location_preset(
            uid_gemischt, preset_gemischt, "Ort-AC12b-Gemischt", send_telegram=True,
            alert_channel_thresholds={"telegram": "HIGH"},
        )
        mails_gemischt: list[tuple[str, str]] = []
        sent_gemischt = _run_compare_alerts(
            uid_gemischt, _settings_email_and_telegram(), mails_gemischt, {"loc-1": 14.0},
        )
        assert sent_gemischt == 1, "AC-12b Voraussetzung (gemischt): der Alarm muss auslösen"
        assert mails_gemischt and not tg_gemischt.sent, (
            "AC-12b Voraussetzung (gemischt): E-Mail zugestellt, Telegram "
            f"unterdrückt — erhalten mails={mails_gemischt!r}, "
            f"telegram={tg_gemischt.sent!r}"
        )
        log_gemischt = read_log(uid_gemischt)
        entries_gemischt = [
            e for e in log_gemischt["entries"] if e["entity_id"] == preset_gemischt
        ]
        not_delivered_gemischt = [
            e for e in log_gemischt["not_delivered"] if e["entity_id"] == preset_gemischt
        ]

        assert len(entries_gemischt) == len(entries_baseline) == 1, (
            "AC-12b: die für Kachel/Statistik maßgebliche Zahl ('entries') "
            "muss im gemischten Lauf (zugestellt UND unterdrückt) IDENTISCH "
            f"zur Baseline ohne Schwelle sein — Baseline: "
            f"{len(entries_baseline)}, gemischt: {len(entries_gemischt)}"
        )
        assert not_delivered_gemischt == [], (
            "AC-12b: bei TEILunterdrückung (E-Mail kam an) darf NICHTS unter "
            f"'not_delivered' landen, gefunden: {not_delivered_gemischt!r}"
        )
    finally:
        tg_baseline.stop()
        tg_gemischt.stop()
        _clean_user(uid_baseline)
        _clean_user(uid_gemischt)


# ═══════════════════════════════════ AC-16 ═════════════════════════════════


def test_ac16_ortsvergleich_schwellen_beeinflussen_trip_alarmpfad_nicht(monkeypatch):
    """AC-16.

    GIVEN derselbe Nutzer hat EINEN Ortsvergleich mit erhöhter Telegram-
          Schwelle UND EINEN Trip OHNE eigene Schwelle
          (``trip.alert_channel_thresholds`` bleibt ``None``).
    WHEN  im Trip ein Alarm mit geringer Dringlichkeit ausgelöst wird.
    THEN  verhält sich der Trip-Versand exakt wie vor dieser Änderung —
          unabhängig davon, welche Kanal-Schwellen bei Ortsvergleichen
          desselben Nutzers gesetzt sind. Nur der Python-Kernpfad wird hier
          geprüft; die Trip-Oberfläche selbst ist in dieser Phase nicht
          mountbar (ADR-0020) und gehört in die Staging-Verifikation.
    """
    from app.models import ChangeSeverity, TripReportConfig, WeatherChange
    from services.trip_alert import TripAlertService

    uid = _uid("ac16")
    preset_id = f"cp-ac16-{uuid.uuid4().hex[:6]}"
    tg_stub = _TelegramStub()
    _clean_user(uid)
    try:
        _pin_transport_stubs(monkeypatch, tg_stub)
        # Ortsvergleich desselben Nutzers MIT erhöhter Schwelle -- er wird
        # hier bewusst NICHT ausgelöst; ihre bloße Existenz im Datenbestand
        # des Nutzers darf den unabhängigen Trip-Alarmpfad nicht berühren.
        _setup_single_location_preset(
            uid, preset_id, "Ort-AC16", send_telegram=True,
            alert_channel_thresholds={"telegram": "HIGH"},
        )

        trip = gust_alert_trip(f"trip-ac16-{uuid.uuid4().hex[:6]}")
        trip.report_config = TripReportConfig(
            trip_id=trip.id, send_email=True, send_telegram=True, send_sms=False,
            alert_on_changes=True,
        )
        trip.alert_cooldown_minutes = 0
        assert trip.alert_channel_thresholds is None, (
            "AC-16 Voraussetzung: der Trip selbst trägt keine eigene Schwelle"
        )

        change = WeatherChange(
            metric="gust_max_kmh", old_value=20.0, new_value=45.0, delta=25.0,
            threshold=20.0, severity=ChangeSeverity.MINOR, direction="increase",
            segment_id="1",
        )
        mails: list[tuple[str, str]] = []
        svc = TripAlertService(
            settings=_settings_email_and_telegram(), user_id=uid, throttle_hours=0,
            mail_sink=lambda subject, body: mails.append((subject, body)),
        )
        result = svc._send_alert(trip, [weather(1)], [change])

        assert mails, "AC-16 Voraussetzung: E-Mail muss unverändert ankommen"
        assert tg_stub.sent, (
            "AC-16: der Trip-Alarm (keine eigene Schwelle gesetzt) darf durch "
            "die Ortsvergleichs-Schwelle DESSELBEN Nutzers nicht beeinflusst "
            f"werden — tatsächlich gesendet: {tg_stub.sent!r}"
        )
        assert set(result.delivered_channels) == {"email", "telegram"}, (
            f"AC-16: beide Trip-Kanäle müssen zugestellt sein wie vor dieser "
            f"Änderung, gefunden: {result.delivered_channels!r}"
        )
    finally:
        tg_stub.stop()
        _clean_user(uid)


# ═══════════════════════════════════ AC-17 ═════════════════════════════════


def test_ac17_gelbe_amtliche_warnung_erscheint_jetzt_in_sms_und_telegram():
    """AC-17.

    GIVEN ein Ortsvergleich hat die Startschwelle ('gering') für den SMS-/
          Telegram-Kanal unverändert gelassen.
    WHEN  der reguläre Kurznachrichten-Bericht (SMS UND Telegram) dieses
          Vergleichs eine gelbe amtliche Warnung (Stufe 2) enthält.
    THEN  erscheint diese Warnung jetzt in BEIDEN Berichtsformaten — vorher
          waren beide leer (harter Filter auf ``MIN_SMS_LEVEL`` = Stufe 3).

    Zwei unterschiedliche Codestellen (Spec „Implementation Details"):
    ``comparison.py:735`` (eigener Inline-Filtervergleich) für Telegram,
    ``comparison.py:900`` (fehlender ``min_level``-Parameter an
    ``official_alerts_to_sms_entries``) für SMS.

    ``tests/tdd/test_compare_sms_official_alerts.py:84`` und
    ``test_compare_telegram_official_alerts.py:111`` prüfen noch das ALTE
    Soll (gelbe Warnung darf NICHT erscheinen) — sie werden durch diese
    Scheibe sicher rot und sind in Phase 6 auf das neue Soll umzuschreiben
    (Team-Lead-Auftrag: in dieser Phase nicht anfassen).
    """
    from app.user import ComparisonResult, LocationResult
    from output.renderers.comparison import render_compare_sms, render_compare_telegram
    from services.official_alerts.models import OfficialAlert

    alert = OfficialAlert(
        source="test-vigilance", hazard="wind_gust", level=2,
        label="Windwarnung Stufe Gelb",
    )
    loc = LocationResult(
        location=SavedLocation(
            id="ort-ac17", name="Ort-AC17", lat=45.9, lon=6.87, elevation_m=1035,
        ),
        temp_max=18.0, wind_max=8.0, official_alerts=[alert],
    )
    result = ComparisonResult(
        locations=[loc], time_window=(0, 23), target_date=date(2026, 7, 23),
        created_at=datetime(2026, 7, 23, 6, 0),
    )

    sms = render_compare_sms(result)
    telegram = render_compare_telegram(result)

    assert "!W:L" in sms, (
        "AC-17: bei Startschwelle 'gering' muss die gelbe amtliche Warnung "
        f"(Stufe 2, Kürzel 'W:L') jetzt im Compare-SMS-Kürzel-Marker "
        f"erscheinen, gefunden: {sms!r}"
    )
    assert "Warnstufe GELB" in telegram, (
        "AC-17: dieselbe gelbe Warnung muss im Compare-Telegram als "
        f"ausgeschriebener Warn-Block erscheinen, gefunden: {telegram!r}"
    )


# ═══════════════════════════════════ AC-18 ═════════════════════════════════


def test_ac18_alarmversand_bei_gelber_warnung_unveraendert_von_ac17():
    """AC-18.

    GIVEN ein Ortsvergleich hat für einen Kanal keine Schwelle über 'gering'
          gesetzt.
    WHEN  eine gelbe amtliche Warnung (Stufe 2) einen ALARM auslöst (nicht
          den Bericht aus AC-17 — zwei getrennte Module,
          ``compare_official_alert.py`` vs. ``comparison.py``).
    THEN  wird die Alarm-Meldung genauso verschickt wie vor dieser Änderung
          — E-Mail UND Telegram werden erreicht. Das Aufgehen der
          Berichtsschwelle (AC-17) verändert den Alarm-Versand nicht.
    """
    from services.compare_official_alert import CompareOfficialAlertService
    from services.official_alerts import register_official_alert_source

    uid = _uid("ac18")
    preset_id = f"cp-ac18-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    b, backup = _sources_backup()
    b._REGISTERED_SOURCES.clear()
    try:
        _write_user_tier(uid, "premium")
        save_location(_official_location("loc-a", "Ort-AC18", LAT_A, LON_A), user_id=uid)
        preset = _official_preset(
            preset_id, ["loc-a"], ["dummy@example.com"], send_telegram=True,
        )
        # Keine 'alert_channel_thresholds' gesetzt -- Startwert 'gering' auf
        # jedem Kanal, unabhängig vom Bericht (AC-17).
        _write_presets(uid, [preset])
        register_official_alert_source(
            _FakeOfficialAlertSource(LAT_A, LON_A, [_official_alert(level=2)])
        )

        mail_calls: list[str] = []
        tg_calls: list[str] = []
        svc = CompareOfficialAlertService(
            settings=_official_settings_all_channels(), user_id=uid,
            mail_sink=lambda subject, body: mail_calls.append(body),
            telegram_sink=lambda text: tg_calls.append(text),
        )
        svc.check_all_compare_presets()

        assert len(mail_calls) == 1, (
            f"AC-18: E-Mail muss unverändert zugestellt werden, erhalten "
            f"{len(mail_calls)}"
        )
        assert len(tg_calls) == 1, (
            "AC-18: Telegram muss die gelbe Warnung bei Startschwelle "
            f"'gering' unverändert erreichen, erhalten: {tg_calls!r}"
        )
    finally:
        b._REGISTERED_SOURCES.clear()
        b._REGISTERED_SOURCES.extend(backup)
        _clean_user(uid)
