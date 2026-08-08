"""TDD RED — Issue #1467 Scheibe S2, Arbeitsgang AG4: Telegram und SMS fuer
Ortsvergleich-Aenderungsalarme scharf schalten.

SPEC: docs/specs/modules/rework_1467_s2_aenderungsalarm.md — AC-10, AC-11,
AC-12, AC-13, Abschnitt "AG4 — Telegram und SMS fuer Ortsvergleich-
Aenderungsalarme scharf schalten".
Kontext: docs/context/rework-1467-s2-ag3b-ag4.md

GEMESSENER IST-STAND (HEAD 6b6ad80d): `compare_alert.py:272` verdrahtet
`channels={"email"}` FEST — ein Nutzer kann Telegram/SMS fuer
Ortsvergleich-Alarme im Alarme-Tab einschalten (`AlertChannelPicker`,
`AlarmeTab.svelte:295`) und bekommt trotzdem nur E-Mail. AG4 ersetzt die feste
Liste durch den bereits vorhandenen Resolver
`services/compare_alert_channels.py::effective_compare_channels()` (AG1),
den heute nur `compare_official_alert.py:257` und
`scheduler_dispatch_service.py:288` benutzen.

ROT/GRUEN-Aufteilung: alle vier Tests sind ROT. Drei davon enthalten
ausdruecklich BEIDE Seiten (Nutzer ohne Opt-in -> Kanal bleibt stumm; Nutzer
mit Opt-in -> Kanal liefert). Die stumme Seite ist heute schon gruen — sie
allein waere ein Test, der die Nicht-Aenderung feiert; erst zusammen mit der
liefernden Seite beweist er, dass genau das Preset-Feld (und nicht der fest
verdrahtete Kanalsatz) ueber die Zustellung entscheidet. Beide Seiten laufen
ueber ZWEI verschiedene, echte `user_id`-Werte — nie ein Rueckfall auf
`"default"` (Mandantentrennung, CLAUDE.md).

TESTPOLITIK (CLAUDE.md, Kern-Schicht): kein `Mock()`/`patch()`/`MagicMock`.
Nachweise erfolgen AN DER SENKE, nicht am Rueckgabewert: echter lokaler
HTTP-Stub fuer die Telegram-Bot-API (via `monkeypatch` auf
`output.channels.telegram.TELEGRAM_API_BASE`, Muster aus
`test_compare_alert_telegram_per_location.py`), echter lokaler HTTP-Stub fuer
die seven.io-SMS-API, echte Preset-/Orts-/Snapshot-Dateien, echtes
`alert_log.json`.

Signaturfalle (Vorwoche): `mail_sink` wird mit SCHLUESSELWOERTERN aufgerufen
(`mail_sink(subject=..., body=...)`, `notification_service.py:1131`), die
Telegram-/SMS-Transporte dagegen ueber echte HTTP-POSTs. Eine Senke mit
falscher Signatur schluckt den Aufruf still und der Dienst meldet trotzdem
Erfolg — deshalb prueft jeder Test, WAS an der Senke ankam, nicht nur DASS
etwas passierte.

KEIN ECHTER VERSAND (Issue #1477): `Settings(...)` faellt bei NICHT gesetzten
Feldern still auf die Prod-`.env` des Worktrees zurueck (gemessen:
`Settings().telegram_chat_id` ist der Produktiv-Chat des PO,
`Settings().sms_gateway_url == 'https://gateway.seven.io/api/sms'`). Deshalb
setzt JEDE Settings-Fabrik hier JEDES versandrelevante Feld ausdruecklich,
und JEDER Test lenkt BEIDE Netz-Transporte auf seine lokalen Loopback-Stubs
um — auch dort, wo der Kanal stumm bleiben SOLL. Faellt die Implementierung
falsch aus, landet die Nachricht am Stub und der Test schlaegt fehl; sie kann
den Rechner nicht verlassen.

KORREKTUR-RUNDE 2026-08-04 (Kriterien K-5/K-6, unterer Abschnitt): der
Kurzstil-Schalter `display_config.telegram_style` (#1260) wirkt auf dem
Ortsvergleich-AENDERUNGSalarm bisher gar nicht — genau auf dem Weg, den AG4
oben gerade freigeschaltet hat. Die gemessene Kette und der ROT-Grund stehen
im Abschnitts-Kommentar vor `test_k5_*`.

Pfadregel #1409: der Prueflings-Datenpfad wird relativ zur Testdatei
aufgeloest, nie ueber einen festen Hauptrepo-Pfad.
"""
from __future__ import annotations

import http.server
import json
import shutil
import socket
import threading
import urllib.parse
import uuid
from datetime import datetime, timezone
from pathlib import Path

import output.channels.telegram as tg_module
from app.config import Settings
from app.models import SegmentWeatherSummary
from app.user import SavedLocation

from tests.helpers.compare_briefings import write_compare_briefings
import pytest


# Live-Schicht (Test-Politik, CLAUDE.md): braucht echtes Netz/echte Dienste --
# lief im Kern nie gruen (CI-Vermessung 2026-08-04, #1196) und gehoert per
# Marker in den /e2e-verify-Lauf, nicht auf eine Ausnahmeliste.
pytestmark = pytest.mark.live

# Pfadregel #1409: relativ zur Testdatei. `load_compare_presets()` liest
# ComparePresets ueber `data_root="data"` RELATIV zum Arbeitsverzeichnis
# (`src/app/loader.py:318`) und laeuft damit an der data-root-Isolation der
# conftest vorbei — die Preset-Dateien muessen deshalb genau hier liegen und
# werden im `finally` restlos wieder entfernt.
def _data_root_users() -> Path:
    """Nutzer-Wurzel der Compare-Preset-Ablage — Funktion statt Konstante
    (#1595): ``get_data_root()`` liefert erst zur Laufzeit die von der
    #1133-Fixture gesetzte Basis, eine Konstante waere beim Import gebunden."""
    from app.loader import get_data_root

    return get_data_root() / "users"


# ---------------------------------------------------------------------------
# Echte lokale Aufzeichnungs-Senken (kein Mock, kein Netz)
# ---------------------------------------------------------------------------

def _free_port() -> int:
    s = socket.socket()
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class _TelegramStub:
    """Lokaler HTTP-Stub fuer die Telegram-Bot-API. Zeichnet jede
    `sendMessage`-Nutzlast auf. 1:1 das Muster aus
    `test_compare_alert_telegram_per_location.py::_TelegramStub`."""

    def __init__(self) -> None:
        self.sent: list[dict] = []
        sent = self.sent
        counter = {"mid": 7000}

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

            def log_message(self, *args):  # noqa: D401 - silence
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
    """Lokaler HTTP-Stub fuer die seven.io-API — empfaengt den echten POST von
    `SMSOutput.send()`."""

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

            def log_message(self, *args):  # noqa: D401 - silence
                pass

        self.port = _free_port()
        self._server = http.server.HTTPServer(("127.0.0.1", self.port), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def texts(self) -> list[str]:
        return [r.get("text", "") for r in self.received]

    def stop(self) -> None:
        self._server.shutdown()


# ---------------------------------------------------------------------------
# Settings — JEDES versandrelevante Feld ausdruecklich gesetzt (#1477)
# ---------------------------------------------------------------------------

def _settings_all_channels(sms_port: int) -> Settings:
    """E-Mail (ueber `mail_sink`, kein SMTP-Socket), Telegram (lokaler Stub via
    `TELEGRAM_API_BASE`) und SMS (lokaler Stub) sind ALLE technisch faehig.
    So entscheidet ausschliesslich das Preset-Opt-in bzw. das Tarif-Gate
    darueber, was zugestellt wird — und nicht ein zufaellig fehlendes
    Konto-Feld."""
    return Settings(
        smtp_host="dummy.invalid", smtp_user="dummy", smtp_pass="dummy",
        mail_to="dummy@example.invalid",
        telegram_bot_token="tdd-stub-bot-token", telegram_chat_id="99999",
        sms_gateway_url=f"http://127.0.0.1:{sms_port}/api/sms",
        seven_api_key="tdd-stub-key", sms_to="+49000000000", sms_from=None,
    )


# ---------------------------------------------------------------------------
# Fixture-Daten (echte DTOs / echte Dateien)
# ---------------------------------------------------------------------------

def _pwd(point_id: str, name: str, lat: float, lon: float, precip_sum_mm: float):
    from services.point_weather import PointWeatherData

    return PointWeatherData(
        id=point_id, name=name, lat=lat, lon=lon, timeseries=None,
        aggregated=SegmentWeatherSummary(precip_sum_mm=precip_sum_mm),
        fetched_at=datetime.now(timezone.utc), provider="test-scripted",
    )


class _ScriptedWeatherSource:
    """Deterministische `LocationWeatherSource`-Implementierung (kein Mock):
    liefert echte `PointWeatherData` mit vorab festgelegten Werten, ohne Netz."""

    def __init__(self, values: dict[str, float]) -> None:
        self._values = dict(values)

    def fetch(
        self, point_id: str, lat: float, lon: float,
        start_hour: int | None = None, end_hour: int | None = None,
    ):
        return _pwd(point_id, point_id, lat, lon, self._values.get(point_id, 0.0))


def _compare_preset(preset_id: str, location_ids: list[str], **extra) -> dict:
    """Compare-Preset-Rohdict. `**extra` setzt NUR die ausdruecklich
    uebergebenen Schluessel — fehlt `send_telegram`, fehlt der Schluessel im
    Dict GANZ (nicht `False`), genau wie es AC-11/R4 verlangt."""
    preset = {
        "id": preset_id,
        "name": preset_id,
        "user_id": "unused",
        "location_ids": list(location_ids),
        "schedule": "daily",
        "weekday": 4,
        "profil": "ALLGEMEIN",
        "hour_from": 9,
        "hour_to": 16,
        "empfaenger": [],
        "letzter_versand": None,
        "top_ort_letzter_versand": None,
        "created_at": "2026-08-04T00:00:00Z",
    }
    preset.update(extra)
    return preset


def _clean_user(user_id: str) -> None:
    d = _data_root_users() / user_id
    if d.exists():
        shutil.rmtree(d)


def _write_tier(user_id: str, tier: str) -> None:
    """Echtes `user.json` — `sms_allowed()` (`services/user_tier.py:6-14`)
    liest es aus dem `get_data_dir()`-Baum. Ohne Datei gilt der Free-Tarif."""
    from app.loader import get_data_dir

    path = get_data_dir(user_id)
    path.mkdir(parents=True, exist_ok=True)
    (path / "user.json").write_text(json.dumps({"id": user_id, "tier": tier}))


def _setup_single_location_preset(
    user_id: str, preset_id: str, location_name: str, **preset_extra
) -> None:
    """Legt einen vollstaendigen, ausloesenden Ortsvergleich an: EIN Ort, ein
    Delta-Anker von 2 mm Niederschlag; die Wetterquelle liefert spaeter 30 mm
    (Delta 28, weit ueber jeder Empfindlichkeitsstufe)."""
    from app.loader import save_location
    from services.compare_weather_snapshot import CompareWeatherSnapshotService

    loc_id = "loc-1"
    save_location(
        SavedLocation(id=loc_id, name=location_name, lat=47.07, lon=15.44, elevation_m=353),
        user_id=user_id,
    )
    write_compare_briefings(
        _data_root_users() / user_id, [_compare_preset(preset_id, [loc_id], **preset_extra)]
    )
    CompareWeatherSnapshotService(user_id=user_id).save(
        preset_id, loc_id, _pwd(loc_id, location_name, 47.07, 15.44, 2.0)
    )


def _setup_two_location_preset(
    user_id: str, preset_id: str, **preset_extra
) -> None:
    """Zwei Orte ("Graz" auf Position 1, "Wien" auf Position 2), beide mit
    einem Delta-Anker von 2 mm Niederschlag. Die Wetterquelle liefert spaeter
    UNTERSCHIEDLICHE Werte (Graz 30, Wien 45) — damit sind die Kurznachricht
    (`'2:+R45 1:+R30'`, Korrektur-Kriterium K-1) und die reichen Sprechblasen
    je Ort eindeutig auseinanderzuhalten."""
    from app.loader import save_location
    from services.compare_weather_snapshot import CompareWeatherSnapshotService

    orte = [("loc-graz", "Graz", 47.07, 15.44), ("loc-wien", "Wien", 48.21, 16.37)]
    for loc_id, name, lat, lon in orte:
        save_location(
            SavedLocation(id=loc_id, name=name, lat=lat, lon=lon, elevation_m=300),
            user_id=user_id,
        )
    write_compare_briefings(
        _data_root_users() / user_id,
        [_compare_preset(preset_id, [o[0] for o in orte], **preset_extra)],
    )
    snapshots = CompareWeatherSnapshotService(user_id=user_id)
    for loc_id, name, lat, lon in orte:
        snapshots.save(preset_id, loc_id, _pwd(loc_id, name, lat, lon, 2.0))


def _run_compare_alerts(
    user_id: str, settings: Settings, mails: list,
    values: dict[str, float] | None = None,
) -> int:
    from services.compare_alert import CompareAlertService

    service = CompareAlertService(
        settings=settings, user_id=user_id,
        weather_source=_ScriptedWeatherSource(
            values if values is not None else {"loc-1": 30.0}
        ),
        mail_sink=lambda subject, body: mails.append((subject, body)),
    )
    return service.check_all_compare_presets()


_ZWEI_ORTE_WETTER = {"loc-graz": 30.0, "loc-wien": 45.0}
# Gemessener Kurznachrichten-Text fuer diese Fixture nach der Korrektur
# (Kriterium K-1: nur die Werte mit ihrer Ortsnummer, kein Kopf). Wien traegt
# den groesseren Messwert und steht durch die severity-Sortierung vorne — die
# Zahlen laufen absteigend.
_KURZ_TEXT_ZWEI_ORTE = "2:+R45 1:+R30"


def _load_alert_log(user_id: str) -> dict:
    from app.loader import get_data_dir

    path = get_data_dir(user_id) / "alert_log.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text())


# ═══════════════════════════════ AC-10 ═══════════════════════════════════════

def test_ac10_preset_with_send_telegram_delivers_exactly_one_telegram(monkeypatch):
    """AC-10 (ROT) GIVEN ein Ortsvergleich mit `send_telegram: true` und
    telegramfaehigen Konto-Settings, dessen einziger Ort ("Graz") eine
    Aenderung weit ueber der Schwelle hat.

    WHEN `CompareAlertService.check_all_compare_presets()` laeuft.

    THEN kommt an der Telegram-Senke GENAU EINE Zustellung an, und ihr Inhalt
    traegt den Ortsnamen "Graz". Die E-Mail wird zusaetzlich zugestellt
    (E-Mail bleibt immer aktiv, Spec AG1).

    ROT-Grund (gemessen): `compare_alert.py:272` setzt `channels={"email"}`
    fest — die Telegram-Senke bleibt bei 0 Zustellungen. Der Nachweis laeuft
    ausdruecklich AN DER SENKE (empfangene HTTP-Nutzlast), nicht ueber den
    Rueckgabewert von `check_all_compare_presets()`: der zaehlt gebuendelte
    Laeufe und stuende auch heute schon auf 1.
    """
    uid = f"tdd-ag4-ac10-{uuid.uuid4().hex[:6]}"
    preset_id = f"cp-ag4-ac10-{uuid.uuid4().hex[:6]}"
    tg_stub = _TelegramStub()
    sms_stub = _SMSStub()
    _clean_user(uid)
    try:
        monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", tg_stub.base_url)
        _write_tier(uid, "standard")
        _setup_single_location_preset(uid, preset_id, "Graz", send_telegram=True)

        mails: list[tuple[str, str]] = []
        _run_compare_alerts(uid, _settings_all_channels(sms_stub.port), mails)

        texts = tg_stub.texts()
        assert len(texts) == 1, (
            "AC-10: erwartet GENAU EINE Telegram-Zustellung an der Senke, "
            f"erhalten: {len(texts)} -- {texts!r}. Solange compare_alert.py "
            "`channels={'email'}` fest verdrahtet, bleibt der eingeschaltete "
            "Telegram-Schalter des Nutzers wirkungslos."
        )
        assert "Graz" in texts[0], (
            "AC-10: die Telegram-Nachricht muss den Ortsnamen tragen, "
            f"erhalten: {texts[0]!r}"
        )
        assert len(mails) == 1, (
            "AC-10: die E-Mail muss weiterhin zugestellt werden (E-Mail ist "
            f"immer aktiv), erhalten: {len(mails)} Sends"
        )
        assert sms_stub.texts() == [], (
            "AC-10: ohne `send_sms` darf keine SMS rausgehen, erhalten: "
            f"{sms_stub.texts()!r}"
        )
    finally:
        tg_stub.stop()
        sms_stub.stop()
        _clean_user(uid)


# ═══════════════════════════════ AC-11 ═══════════════════════════════════════

def test_ac11_missing_send_telegram_key_stays_email_only_while_optin_user_gets_telegram(
    monkeypatch,
):
    """AC-11 (ROT) GIVEN ZWEI verschiedene, echte Nutzer mit identisch
    ausloesendem Ortsvergleich und identisch telegramfaehigen Konto-Settings:
    bei Nutzer A fehlt der Schluessel `send_telegram` GANZ im Preset-Dict
    (nicht `false` — gar nicht vorhanden), bei Nutzer B steht er auf `true`.

    WHEN fuer beide `check_all_compare_presets()` laeuft.

    THEN bleibt Nutzer As Telegram-Senke unberuehrt (0 Zustellungen), seine
    E-Mail wird trotzdem zugestellt; Nutzer Bs Telegram-Senke bekommt genau
    eine Zustellung.

    Warum beide Seiten in EINEM Test stehen: die stumme Seite allein ist heute
    schon gruen (es geht ja gar nichts raus) und wuerde die Nicht-Aenderung
    feiern. Erst die liefernde Seite daneben beweist, dass GENAU der fehlende
    Preset-Schluessel blockiert — und nicht der fest verdrahtete Kanalsatz
    aus `compare_alert.py:272` (Risiko R4 der Spec).

    ROT-Grund (gemessen): Nutzer B bekommt heute 0 statt 1 Telegram-Zustellung.

    Mandantentrennung: zwei getrennte `user_id`-Werte, zwei getrennte Senken —
    kein Rueckfall auf `"default"`.
    """
    uid_a = f"tdd-ag4-ac11-nokey-{uuid.uuid4().hex[:6]}"
    uid_b = f"tdd-ag4-ac11-optin-{uuid.uuid4().hex[:6]}"
    preset_a = f"cp-ac11-a-{uuid.uuid4().hex[:6]}"
    preset_b = f"cp-ac11-b-{uuid.uuid4().hex[:6]}"
    tg_a, tg_b = _TelegramStub(), _TelegramStub()
    sms_stub = _SMSStub()
    _clean_user(uid_a)
    _clean_user(uid_b)
    try:
        assert uid_a != "default" and uid_b != "default"

        # ── Nutzer A: Schluessel `send_telegram` fehlt komplett ─────────────
        monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", tg_a.base_url)
        _write_tier(uid_a, "standard")
        _setup_single_location_preset(uid_a, preset_a, "Graz")
        # Gegenprobe am geschriebenen Rohdict: der Schluessel darf wirklich
        # nicht existieren (sonst prueft der Test einen anderen Fall).
        raw_a = json.loads(
            (_data_root_users() / uid_a / "briefings" / f"{preset_a}.json").read_text()
        )
        assert "send_telegram" not in raw_a, (
            "Setup-Kontrolle: das Preset von Nutzer A darf den Schluessel "
            f"`send_telegram` GAR NICHT enthalten, gefunden: {sorted(raw_a)}"
        )

        mails_a: list[tuple[str, str]] = []
        _run_compare_alerts(uid_a, _settings_all_channels(sms_stub.port), mails_a)

        assert tg_a.texts() == [], (
            "AC-11: ein FEHLENDER `send_telegram`-Schluessel darf nie als "
            f"Opt-in gelten, erhalten: {tg_a.texts()!r}"
        )
        assert len(mails_a) == 1, (
            "AC-11: E-Mail bleibt einziger Kanal und muss zugestellt werden, "
            f"erhalten: {len(mails_a)} Sends"
        )

        # ── Nutzer B: derselbe Fall MIT Opt-in ──────────────────────────────
        monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", tg_b.base_url)
        _write_tier(uid_b, "standard")
        _setup_single_location_preset(uid_b, preset_b, "Wien", send_telegram=True)

        mails_b: list[tuple[str, str]] = []
        _run_compare_alerts(uid_b, _settings_all_channels(sms_stub.port), mails_b)

        assert len(tg_b.texts()) == 1, (
            "AC-11 (Gegenprobe): mit `send_telegram: true` MUSS genau eine "
            f"Telegram-Zustellung ankommen, erhalten: {tg_b.texts()!r}. "
            "Bleibt sie aus, entscheidet nicht das Preset-Feld, sondern die "
            "fest verdrahtete Kanalliste."
        )
        assert "Wien" in tg_b.texts()[0]
        assert tg_a.texts() == [], (
            "Mandantentrennung: Nutzer Bs Opt-in darf keine Zustellung an "
            f"Nutzer As Senke ausloesen, erhalten: {tg_a.texts()!r}"
        )
    finally:
        tg_a.stop()
        tg_b.stop()
        sms_stub.stop()
        _clean_user(uid_a)
        _clean_user(uid_b)


# ═══════════════════════════════ AC-12 ═══════════════════════════════════════

def test_ac12_free_tier_user_gets_no_sms_while_standard_tier_user_does(monkeypatch):
    """AC-12 (ROT) GIVEN ZWEI verschiedene, echte Nutzer mit identischem
    Ortsvergleich (`send_sms: true`) und identisch SMS-faehigen Konto-Settings:
    Nutzer A hat den Free-Tarif (`user.json` mit `tier: "free"`), Nutzer B den
    Standard-Tarif.

    WHEN fuer beide `check_all_compare_presets()` laeuft.

    THEN bleibt Nutzer As SMS-Senke unberuehrt (0 Zustellungen) — das
    Tarif-Gate `sms_allowed()` sitzt im Resolver, nicht im Renderer —, waehrend
    Nutzer B genau eine SMS bekommt. Beide bekommen ihre E-Mail.

    Warum beide Seiten in EINEM Test stehen: die Free-Tarif-Seite ist heute
    schon gruen (es geht ueberhaupt keine SMS raus). Erst die Standard-Tarif-
    Seite beweist, dass wirklich der Tarif blockiert und nicht der fest
    verdrahtete `channels={"email"}`-Satz.

    ROT-Grund (gemessen): Nutzer B bekommt heute 0 statt 1 SMS.
    """
    uid_free = f"tdd-ag4-ac12-free-{uuid.uuid4().hex[:6]}"
    uid_std = f"tdd-ag4-ac12-std-{uuid.uuid4().hex[:6]}"
    preset_free = f"cp-ac12-free-{uuid.uuid4().hex[:6]}"
    preset_std = f"cp-ac12-std-{uuid.uuid4().hex[:6]}"
    tg_stub = _TelegramStub()
    sms_free, sms_std = _SMSStub(), _SMSStub()
    _clean_user(uid_free)
    _clean_user(uid_std)
    try:
        monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", tg_stub.base_url)
        assert uid_free != "default" and uid_std != "default"

        # ── Nutzer A: Free-Tarif ────────────────────────────────────────────
        _write_tier(uid_free, "free")
        _setup_single_location_preset(uid_free, preset_free, "Graz", send_sms=True)
        mails_free: list[tuple[str, str]] = []
        _run_compare_alerts(uid_free, _settings_all_channels(sms_free.port), mails_free)

        assert sms_free.texts() == [], (
            "AC-12: ein Free-Tarif-Nutzer darf trotz `send_sms: true` KEINE "
            f"SMS bekommen (Tarif-Gate `sms_allowed`), erhalten: "
            f"{sms_free.texts()!r}"
        )
        assert len(mails_free) == 1, (
            "AC-12: die E-Mail muss trotz gesperrter SMS zugestellt werden, "
            f"erhalten: {len(mails_free)} Sends"
        )

        # ── Nutzer B: Standard-Tarif ────────────────────────────────────────
        _write_tier(uid_std, "standard")
        _setup_single_location_preset(uid_std, preset_std, "Wien", send_sms=True)
        mails_std: list[tuple[str, str]] = []
        _run_compare_alerts(uid_std, _settings_all_channels(sms_std.port), mails_std)

        assert len(sms_std.texts()) == 1, (
            "AC-12 (Gegenprobe): ein Nutzer mit SMS-Tarif und `send_sms: true` "
            f"MUSS genau eine SMS bekommen, erhalten: {sms_std.texts()!r}"
        )
        assert sms_free.texts() == [], (
            "Mandantentrennung: die SMS von Nutzer B darf nicht an der Senke "
            f"von Nutzer A auftauchen, erhalten: {sms_free.texts()!r}"
        )
        assert tg_stub.texts() == [], (
            "AC-12: ohne `send_telegram` darf kein Telegram rausgehen, "
            f"erhalten: {tg_stub.texts()!r}"
        )
    finally:
        tg_stub.stop()
        sms_free.stop()
        sms_std.stop()
        _clean_user(uid_free)
        _clean_user(uid_std)


# ═══════════════════════════════ AC-13 ═══════════════════════════════════════

def test_ac13_alert_log_entry_reflects_email_and_telegram_delivery(monkeypatch):
    """AC-13 (ROT) GIVEN einen Ortsvergleich-Alarm, der ueber E-Mail UND
    Telegram zugestellt wird (`send_telegram: true`, beide Kanaele faehig, kein
    `send_sms`).

    WHEN der Lauf beendet ist.

    THEN fuehrt der Eintrag im Alarm-Protokoll (`alert_log.json`) BEIDE
    Kanaele als tatsaechlich zugestellt und weist SMS als nicht eingeschaltet
    aus.

    Feld-Zuordnung (`services/alert_log.py:182-199`): die Spec spricht von
    `effective_channels`/`sent_channels`/`reachable_channels` — das sind die
    PARAMETER von `append_entry()`. In der Datei stehen sie als
    `channels_sent` (die Schnittmenge aus tatsaechlicher Zustellung und
    eingeschalteten Kanaelen) und `channels_not_sent` (je nicht zugestelltem
    Kanal ein Grund: `delivery_failed` = war eingeschaltet und scheiterte,
    `channel_disabled` = war gar nicht eingeschaltet). Aus beiden zusammen
    ist `effective_channels` eindeutig ablesbar — deshalb prueft dieser Test
    die Datei, nicht die Aufrufargumente.

    ROT-Grund (gemessen): heute ist `effective_channels` fest `{"email"}` —
    der Eintrag fuehrt `channels_sent == ["email"]` und meldet Telegram
    faelschlich als `channel_disabled`, obwohl der Nutzer ihn eingeschaltet hat.
    """
    uid = f"tdd-ag4-ac13-{uuid.uuid4().hex[:6]}"
    preset_id = f"cp-ag4-ac13-{uuid.uuid4().hex[:6]}"
    tg_stub = _TelegramStub()
    sms_stub = _SMSStub()
    _clean_user(uid)
    try:
        monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", tg_stub.base_url)
        _write_tier(uid, "standard")
        _setup_single_location_preset(uid, preset_id, "Graz", send_telegram=True)

        mails: list[tuple[str, str]] = []
        _run_compare_alerts(uid, _settings_all_channels(sms_stub.port), mails)

        log = _load_alert_log(uid)
        entries = log.get("entries", [])
        assert len(entries) == 1, (
            f"AC-13: erwartet GENAU EINEN Protokolleintrag, erhalten: "
            f"{len(entries)} -- {log!r}"
        )
        entry = entries[0]
        assert entry["entity_id"] == preset_id
        assert entry["entity_type"] == "compare"

        assert entry["channels_sent"] == ["email", "telegram"], (
            "AC-13: `channels_sent` muss die tatsaechliche Zustellung ueber "
            "BEIDE Kanaele widerspiegeln (E-Mail und Telegram kamen an der "
            f"jeweiligen Senke an), gemessen: {entry['channels_sent']!r}"
        )
        assert entry["channels_not_sent"] == [
            {"channel": "sms", "reason": "channel_disabled"}
        ], (
            "AC-13: nur SMS darf als nicht zugestellt gefuehrt werden, und "
            "zwar mit dem Grund 'channel_disabled' (der Nutzer hat den Kanal "
            "nicht eingeschaltet). Steht Telegram hier, war es gar nicht Teil "
            f"von `effective_channels`. Gemessen: {entry['channels_not_sent']!r}"
        )

        # Gegenprobe an den Senken: das Protokoll behauptet nichts, was nicht
        # wirklich zugestellt wurde.
        assert len(mails) == 1 and len(tg_stub.texts()) == 1, (
            "AC-13: das Protokoll darf nur spiegeln, was tatsaechlich "
            f"zugestellt wurde -- Mails: {len(mails)}, Telegram: "
            f"{tg_stub.texts()!r}"
        )
        assert log.get("not_delivered", []) == [], (
            "AC-13: bei erreichbaren Kanaelen darf nichts in `not_delivered` "
            f"landen, gemessen: {log.get('not_delivered')!r}"
        )
    finally:
        tg_stub.stop()
        sms_stub.stop()
        _clean_user(uid)


# ═══════════════════ K-5 / K-6 — Kurzstil-Schalter (Korrektur) ═══════════════
# Es gibt seit #1260 den Schalter `display_config.telegram_style` mit den
# Werten "rich"/"kurzform"; bei "kurzform" geht der SMS-Text ueber Telegram
# raus. Trip-Alarme (`trip_alert.py:990,1135`) und der amtliche
# Ortsvergleich-Pfad (`compare_official_alert.py:43,135`) lesen ihn.
#
# GEMESSENE KETTE am funktionierenden Pfad (amtliche Warnung):
#   preset["display_config"]["telegram_style"]
#     -> `_effective_telegram_style(preset)`      compare_official_alert.py:43-51
#     -> `send_multi_location_official_alert(..., telegram_style)`
#                                                 notification_service.py:838
#     -> `_dispatch_compare_official_telegram(..., telegram_style=...)`   :907
#     -> `if telegram_style == "kurzform": TelegramOutput(...).send(
#            body=<SMS-Text>, parse_mode=None, suppress_subject_line=True)` :953
#
# Der Ortsvergleich-AENDERUNGSalarm haengt an dieser Kette NICHT dran:
# `compare_alert.py` erwaehnt `telegram_style` nirgends, und
# `send_multi_location_deviation_alert()` (`notification_service.py:517-523`)
# nimmt den Wert gar nicht entgegen — er kommt an
# `_dispatch_alert_message()` (`:1051`) immer als Default "rich" an. Der
# Schalter ist auf genau dem Weg wirkungslos, den AG4 gerade freigeschaltet
# hat.
#
# Beide Tests pruefen AN DER TELEGRAM-SENKE (empfangene HTTP-Nutzlast), nicht
# am Parameter: die Zusicherung wirkt dort, wo die Nachricht rausgeht.

def test_k5_telegram_style_kurzform_delivers_the_short_message(monkeypatch):
    """K-5 (ROT) GIVEN einen Ortsvergleich mit ZWEI Orten, `send_telegram:
    true` und `display_config: {"telegram_style": "kurzform"}` — derselbe
    Schalter, den der Nutzer im Editor umlegt und den der amtliche
    Ortsvergleich-Pfad bereits befolgt.

    WHEN `CompareAlertService.check_all_compare_presets()` laeuft.

    THEN kommt an der Telegram-Senke GENAU EINE Nachricht an, und zwar die
    Kurznachricht (`'2:+R45 1:+R30'`) als reiner Text — ohne `parse_mode`,
    ohne HTML-Auszeichnung, ohne Ortsnamen.

    Warum genau EINE: der Kurzstil ersetzt die ausfuehrliche Fassung, und die
    ausfuehrliche Fassung ist seit AG3a die Auffaecherung in eine Sprechblase
    JE ORT. Die Kurznachricht ist ihrem Wesen nach gebuendelt — sie fuehrt
    alle Orte als Zahl in EINEM Text; sie je Ort aufzuteilen wuerde die
    Ortsnummern sinnlos machen und dem Zweck des Kurzstils (ein knapper Blick
    aufs Telefon) zuwiderlaufen. Der Kurzstil des Trip-Alarms und der des
    amtlichen Ortsvergleich-Alarms senden ebenfalls genau eine Nachricht.

    ROT-Grund (gemessen an Commit 97ec3deb): heute kommen ZWEI reiche
    HTML-Sprechblasen an ("Graz ..." und "Wien ...", je `parse_mode="HTML"`),
    weil der Fan-out-Zweig in `_dispatch_alert_message()` (`:1180`) vor dem
    Kurzstil-Zweig (`:1211`) greift und `telegram_style` diesen Aufrufer
    ueberhaupt nie erreicht.
    """
    uid = f"tdd-k5-kurz-{uuid.uuid4().hex[:6]}"
    preset_id = f"cp-k5-kurz-{uuid.uuid4().hex[:6]}"
    tg_stub = _TelegramStub()
    sms_stub = _SMSStub()
    _clean_user(uid)
    try:
        monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", tg_stub.base_url)
        _write_tier(uid, "standard")
        _setup_two_location_preset(
            uid, preset_id, send_telegram=True,
            display_config={"telegram_style": "kurzform"},
        )

        mails: list[tuple[str, str]] = []
        _run_compare_alerts(
            uid, _settings_all_channels(sms_stub.port), mails, _ZWEI_ORTE_WETTER,
        )

        texts = tg_stub.texts()
        assert len(texts) == 1, (
            "K-5: im Kurzstil ersetzt EINE Kurznachricht die ausfuehrliche "
            f"Fassung, erhalten: {len(texts)} Nachrichten -- {texts!r}. Zwei "
            "Nachrichten bedeuten, dass der Fan-out je Ort weiterlaeuft und "
            "der Kurzstil-Schalter diesen Versandweg nicht erreicht."
        )
        assert texts[0] == _KURZ_TEXT_ZWEI_ORTE, (
            "K-5: zugestellt werden muss der Kurznachrichten-Text (dieselbe "
            f"Fassung wie per SMS), erwartet {_KURZ_TEXT_ZWEI_ORTE!r}, "
            f"gemessen {texts[0]!r}"
        )
        assert tg_stub.sent[0].get("parse_mode") is None, (
            "K-5: der Kurzstil ist Plaintext -- `parse_mode` darf gar nicht "
            f"gesetzt sein, gemessen: {tg_stub.sent[0].get('parse_mode')!r} "
            "(so macht es der amtliche Ortsvergleich-Pfad, "
            "notification_service.py:953)"
        )
        assert "<" not in texts[0] and "Graz" not in texts[0], (
            "K-5: keine HTML-Auszeichnung, kein Ortsname -- sonst ist es die "
            f"reiche Fassung: {texts[0]!r}"
        )
        assert len(mails) == 1, (
            "K-5: die E-Mail bleibt unberuehrt und wird zugestellt (der "
            f"Schalter betrifft nur Telegram), erhalten: {len(mails)} Sends"
        )
        assert sms_stub.texts() == [], (
            "K-5: ohne `send_sms` darf trotz Kurzstil keine SMS rausgehen, "
            f"erhalten: {sms_stub.texts()!r}"
        )
    finally:
        tg_stub.stop()
        sms_stub.stop()
        _clean_user(uid)


def test_k6_telegram_style_rich_or_absent_keeps_one_bubble_per_location(monkeypatch):
    """K-6 (GRUEN vor UND nach) GIVEN ZWEI verschiedene, echte Nutzer mit
    identisch ausloesendem Zwei-Orte-Vergleich und `send_telegram: true`:
    Nutzer A hat `display_config: {"telegram_style": "rich"}` ausdruecklich
    gesetzt, bei Nutzer B fehlt `display_config` GANZ.

    WHEN fuer beide `check_all_compare_presets()` laeuft.

    THEN bekommen BEIDE das unveraenderte Verhalten: je Ort eine eigene
    reiche Sprechblase (zwei Nachrichten, `parse_mode="HTML"`, Ortsname im
    Text) — das AG3a-Verhalten aus Commit 97ec3deb.

    Dieser Test ist heute schon gruen. Er steht neben K-5, weil erst das Paar
    beweist, dass der SCHALTER entscheidet: ohne ihn koennte eine
    Implementierung den Kurzstil einfach immer senden und K-5 bestehen. Die
    Zusicherung "ein fehlender/`rich`-Schalter aendert nichts" ist ausserdem
    die Gegenprobe zum haeufigsten Fehlermuster dieses Projekts (stiller
    Parameter-Rueckfall: ein nicht gesetzter Wert darf nie das neue Verhalten
    ausloesen).

    Mandantentrennung: zwei getrennte `user_id`-Werte, zwei getrennte Senken —
    kein Rueckfall auf `"default"`.
    """
    uid_rich = f"tdd-k6-rich-{uuid.uuid4().hex[:6]}"
    uid_absent = f"tdd-k6-absent-{uuid.uuid4().hex[:6]}"
    preset_rich = f"cp-k6-rich-{uuid.uuid4().hex[:6]}"
    preset_absent = f"cp-k6-absent-{uuid.uuid4().hex[:6]}"
    tg_rich, tg_absent = _TelegramStub(), _TelegramStub()
    sms_stub = _SMSStub()
    _clean_user(uid_rich)
    _clean_user(uid_absent)
    try:
        assert uid_rich != "default" and uid_absent != "default"

        # ── Nutzer A: telegram_style ausdruecklich "rich" ────────────────────
        monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", tg_rich.base_url)
        _write_tier(uid_rich, "standard")
        _setup_two_location_preset(
            uid_rich, preset_rich, send_telegram=True,
            display_config={"telegram_style": "rich"},
        )
        mails_rich: list[tuple[str, str]] = []
        _run_compare_alerts(
            uid_rich, _settings_all_channels(sms_stub.port), mails_rich,
            _ZWEI_ORTE_WETTER,
        )

        texts_rich = tg_rich.texts()
        assert len(texts_rich) == 2, (
            "K-6: bei `rich` bleibt es bei EINER Sprechblase je Ort (AG3a), "
            f"erwartet 2 Nachrichten, erhalten {len(texts_rich)}: {texts_rich!r}"
        )
        assert any("Graz" in t for t in texts_rich), (
            f"K-6: eine Sprechblase muss Graz nennen: {texts_rich!r}"
        )
        assert any("Wien" in t for t in texts_rich), (
            f"K-6: eine Sprechblase muss Wien nennen: {texts_rich!r}"
        )
        assert all(p.get("parse_mode") == "HTML" for p in tg_rich.sent), (
            "K-6: die reiche Fassung geht als HTML raus, gemessen: "
            f"{[p.get('parse_mode') for p in tg_rich.sent]!r}"
        )
        assert all(t != _KURZ_TEXT_ZWEI_ORTE for t in texts_rich), (
            "K-6: bei `rich` darf NIE die Kurznachricht rausgehen, gemessen: "
            f"{texts_rich!r}"
        )

        # ── Nutzer B: `display_config` fehlt GANZ ────────────────────────────
        monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", tg_absent.base_url)
        _write_tier(uid_absent, "standard")
        _setup_two_location_preset(uid_absent, preset_absent, send_telegram=True)
        raw = json.loads(
            (_data_root_users() / uid_absent / "briefings" / f"{preset_absent}.json").read_text()
        )
        assert "display_config" not in raw, (
            "Setup-Kontrolle: das Preset von Nutzer B darf gar kein "
            f"`display_config` haben, gefunden: {sorted(raw)}"
        )

        mails_absent: list[tuple[str, str]] = []
        _run_compare_alerts(
            uid_absent, _settings_all_channels(sms_stub.port), mails_absent,
            _ZWEI_ORTE_WETTER,
        )

        texts_absent = tg_absent.texts()
        assert len(texts_absent) == 2, (
            "K-6: ein FEHLENDER Schalter darf nie den Kurzstil ausloesen -- "
            f"erwartet 2 reiche Sprechblasen, erhalten {len(texts_absent)}: "
            f"{texts_absent!r}"
        )
        assert all(p.get("parse_mode") == "HTML" for p in tg_absent.sent), (
            "K-6: ohne Schalter bleibt es bei HTML, gemessen: "
            f"{[p.get('parse_mode') for p in tg_absent.sent]!r}"
        )
        assert len(tg_rich.texts()) == 2, (
            "Mandantentrennung: der Lauf von Nutzer B darf an der Senke von "
            f"Nutzer A nichts hinzufuegen, gemessen: {tg_rich.texts()!r}"
        )
    finally:
        tg_rich.stop()
        tg_absent.stop()
        sms_stub.stop()
        _clean_user(uid_rich)
        _clean_user(uid_absent)
