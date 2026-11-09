"""TDD RED — Issue #1767 (inkl. B2-51): Nowcast-/Radar-Onset-Alarm im
Ortsvergleich nennt ALLE ausloesenden Orte in JEDER Kurzform.

SPEC: docs/specs/modules/fix_1767_nowcast_mehrort_kurzform.md (AC-1 bis AC-10)
Kontext: docs/context/fix-1767-nowcast-mehrort-kurzform.md

PO-Entscheid 2026-11-09 (Variante A', loest Entscheid 3b aus #1948 S4 ab,
ADR-0095 Kanal-Paritaet): SMS, Premium-SMS und Telegram-Kurzstil fuehren je
Ort ein Token mit Ortsnummer (`1:R@14:05 3:R@14:40`), ohne Namenskopf und ohne
`km0-0`; die Telegram-Langform ist EINE Nachricht mit einer Zeile je Ort.

Heute (RED) wertet die Kurzform nur den fuehrenden Ort aus
(`Zermatt: R@14:05`) und die Telegram-Langform zeigt alle Ortsnamen im Kopf,
aber Wert und Zeit nur des ersten Ortes, dazu `km 0–0`.

Wege, ueber die gemessen wird (Wirkort, kein Baustein-Nachweis allein):
  * Versand: `CompareRadarAlertService.check_all_compare_presets()` — der
    einzige produktive Aufrufer von `send_multi_location_radar_alert` — mit
    echten Orts-/Preset-Dateien im isolierten tmp-Datenordner, echtem
    `RadarNowcastService` ueber den `frame_source`-Seam und lokalen
    HTTP-Aufzeichnungs-Servern fuer seven.io (SMS + Premium-SMS) und die
    Telegram-Bot-API. Die gerenderten Texte werden am Draht gemessen.
  * Vorschau: `render_compare_alert_preview` (derselbe Positionsweg wie der
    Versand, AC-7/AC-10).
  * Direktversand `send_multi_location_radar_alert` OHNE den kuenftigen
    Parameter `location_positions` nur dort, wo die Zusicherung von den
    Ortsnummern nicht abhaengt (Telegram-Langform, E-Mail).

Uhr: gestellt auf 2026-11-09 13:00 UTC = 14:00 MEZ (Zermatt, Verbier,
Chamonix). Ein Beginn in 5 bzw. 40 Minuten ergibt damit 14:05 bzw. 14:40.

Kein Mock-Theater: kein `Mock()`/`patch()`/`MagicMock`; `monkeypatch` biegt
nur die Telegram-API-Basis und den Datenordner auf lokale Ziele um.
Nutzerkennungen sind echte, je Test frische Kennungen — nie "default".
"""
from __future__ import annotations

import http.server
import json
import re
import socket
import threading
import urllib.parse
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from freezegun import freeze_time

import output.channels.telegram as tg_module
from app.config import Settings
from app.loader import get_data_dir, save_location
from app.user import SavedLocation
from i18n import t

from tests.helpers.compare_briefings import write_compare_briefings
from tests.helpers.nutzer_tier import nutzer_mit_tier
from tests.helpers.sms_empfaenger import mit_profil_kanaele

GEFRORENE_UHR = "2026-11-09 13:00:00+00:00"  # = 14:00 MEZ an allen drei Orten

SMS_TO = "+49000000000"
PREMIUM_TO = "+4915799917670"

ZERMATT = SavedLocation(id="loc-zermatt", name="Zermatt", lat=46.0207, lon=7.7491, elevation_m=1608)
CHAMONIX = SavedLocation(id="loc-chamonix", name="Chamonix", lat=45.9237, lon=6.8694, elevation_m=1035)
VERBIER = SavedLocation(id="loc-verbier", name="Verbier", lat=46.0967, lon=7.2286, elevation_m=1500)
DREI_ORTE = [ZERMATT, CHAMONIX, VERBIER]

# Ein Kurzform-Token mit Ortsnummer: `<pos>:<Kuerzel>[Menge][...]@H:MM[...]`
# bzw. laufend `<pos>:R now`. Nur fuer die Struktur-/Reihenfolgepruefung.
_POS_TOKEN_RE = re.compile(r"^(\d+):(TH|R)\S*$")


# ---------------------------------------------------------------------------
# Lokale Aufzeichnungs-Server (Vorbild test_alert_preview_compare_paritaet.py)
# ---------------------------------------------------------------------------


def _free_port() -> int:
    s = socket.socket()
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class _RecordingServer:
    """Lokaler HTTP-Server auf 127.0.0.1; `parse` macht aus dem POST-Koerper
    einen Eintrag, `reply` ist die Antwort. Kein Mock: der echte Transport
    laeuft, die Nutzlast wird am Draht gemessen."""

    def __init__(self, parse, reply: bytes) -> None:
        self.received: list[dict] = []
        received = self.received

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length", 0))
                received.append(parse(self.rfile.read(length).decode()))
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(reply)

            def log_message(self, *args):  # noqa: D401
                pass

        self.port = _free_port()
        self._server = http.server.HTTPServer(("127.0.0.1", self.port), Handler)
        threading.Thread(target=self._server.serve_forever, daemon=True).start()

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def stop(self) -> None:
        self._server.shutdown()


def _parse_json(raw: str) -> dict:
    try:
        return json.loads(raw)
    except ValueError:
        return {}


def _parse_form(raw: str) -> dict:
    return {k: v[0] for k, v in urllib.parse.parse_qs(raw).items()}


class _Wire:
    def __init__(self, telegram: _RecordingServer, seven: _RecordingServer) -> None:
        self.telegram = telegram
        self.seven = seven

    def settings(self, *, mit_mail: bool) -> Settings:
        """Jedes versandrelevante Feld ausdruecklich gesetzt (#1477: sonst
        faellt pydantic still auf die `.env` des Arbeitsverzeichnisses
        zurueck). E-Mail nur mit `mit_mail` und dann ausschliesslich ueber
        `mail_sink` (Direktversand) — der Ortsvergleich-Lauf hat keine Senke,
        dort bleibt E-Mail aus."""
        smtp = (
            dict(smtp_host="smtp.test.invalid", smtp_user="t@test.invalid",
                 smtp_pass="x", mail_to="to@test.invalid")
            if mit_mail else
            dict(smtp_host=None, smtp_user=None, smtp_pass=None, mail_to=None)
        )
        return Settings(
            sms_gateway_url=f"{self.seven.base_url}/api/sms",
            seven_api_key="sandbox-key-1767", seven_sandbox_key="sandbox-key-1767",
            sms_to=SMS_TO, sms_from=None,
            premium_sms_reply_to=PREMIUM_TO,
            premium_sms_reply_at=datetime.now(timezone.utc),
            telegram_bot_token="test-token-1767",
            telegram_chat_id="99999", telegram_test_chat_id="99999",
            telegram_rate_limit_max_per_window=10_000,
            **smtp,
        )

    def sms(self) -> list[str]:
        return [p.get("text", "") for p in self.seven.received if p.get("to") == SMS_TO]

    def premium(self) -> list[str]:
        return [p.get("text", "") for p in self.seven.received if p.get("to") == PREMIUM_TO]

    def telegram_texts(self) -> list[str]:
        return [p.get("text", "") for p in self.telegram.received]


@pytest.fixture
def wire(monkeypatch):
    telegram = _RecordingServer(_parse_json, b'{"ok": true, "result": {"message_id": 1}}')
    seven = _RecordingServer(_parse_form, b"100")
    monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", telegram.base_url)
    assert tg_module.TELEGRAM_API_BASE.startswith("http://127.0.0.1:")
    yield _Wire(telegram, seven)
    telegram.stop()
    seven.stop()


@pytest.fixture
def data_root(tmp_path, monkeypatch):
    """Isolierter Datenordner ueber beide Loader-Zugriffsformen (Muster
    `tests/helpers/vorschau_umgebung.py::env`)."""
    from app import loader as app_loader

    root = tmp_path / "data"
    root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(app_loader, "_DATA_ROOT", str(root))
    try:
        from src.app import loader as src_loader

        monkeypatch.setattr(src_loader, "_DATA_ROOT", str(root))
    except ImportError:  # pragma: no cover
        pass
    return root


def _uid(marke: str) -> str:
    uid = f"tdd-1767-{marke}-{uuid.uuid4().hex[:6]}"
    assert uid != "default"
    return uid


def _setze_sprache(user_id: str, lang: str) -> None:
    """Read-Modify-Write auf `user.json` (bestehende Felder bleiben)."""
    datei = get_data_dir(user_id) / "user.json"
    datei.parent.mkdir(parents=True, exist_ok=True)
    try:
        profil = json.loads(datei.read_text())
    except (OSError, ValueError):
        profil = {"id": user_id}
    profil["language"] = lang
    datei.write_text(json.dumps(profil))


# ---------------------------------------------------------------------------
# Ortsvergleich anlegen und den ECHTEN Alarmlauf fahren
# ---------------------------------------------------------------------------


def _preset(user_id: str, preset_id: str, orte: list[SavedLocation], *,
            style: str = "kurzform", kanaele=("sms", "premium_sms", "telegram")) -> dict:
    preset = {
        "id": preset_id,
        "name": preset_id,
        "user_id": user_id,
        "location_ids": [o.id for o in orte],
        # Aktiver Zeitplan noetig (#1467 S2 AG6), sonst gilt das Preset als
        # pausiert und schweigt in allen Alarm-Pfaden.
        "schedule": "daily",
        "weekday": 4,
        "profil": "ALLGEMEIN",
        "hour_from": 9,
        "hour_to": 16,
        "empfaenger": ["gregor-test@henemm.com"],
        "letzter_versand": None,
        "top_ort_letzter_versand": None,
        "created_at": "2026-11-01T00:00:00Z",
        "radar_alert_enabled": True,
        "alert_cooldown_minutes": 0,
        "display_config": {"telegram_style": style},
    }
    for ch in kanaele:
        preset[f"send_{ch}"] = True
    return preset


def _anlegen(user_id: str, preset: dict, orte: list[SavedLocation]) -> None:
    for o in orte:
        save_location(o, user_id=user_id)
    write_compare_briefings(get_data_dir(user_id), [preset])


class _FrameQuelle:
    """Echter, aufrufbarer `frame_source` (kein Mock): je Koordinate zwei
    nasse Frames bei `+m` und `+m+10` Minuten nach der gestellten Uhr, danach
    ein trockener bei `+m+20`. Von Hand hergeleitet:
      * Beginn = `+m` (z. B. 14:05), letzter nasser Frame `+m+10` = Ende
        (14:15) -> Ende-Token `@14:15` direkt am Beginn (#2051 S1);
      * Menge 0.2 mm/h x 20 Min = 0.07 mm < 0.1 mm -> KEINE Mengenangabe
        (`_SMS_ONSET_MENGE_MIN_MM`), das Token bleibt `R@14:05@14:15`.
    Koordinaten ohne Eintrag bleiben trocken (loesen nicht aus)."""

    def __init__(self, minuten_je_ort: dict[str, int], orte: list[SavedLocation]) -> None:
        self._by_coord = {
            (round(o.lat, 4), round(o.lon, 4)): minuten_je_ort[o.name]
            for o in orte if o.name in minuten_je_ort
        }
        self.calls: list[tuple[float, float]] = []

    def __call__(self, lat: float, lon: float) -> list:
        from providers.brightsky import RadarFrame

        self.calls.append((lat, lon))
        m = self._by_coord.get((round(lat, 4), round(lon, 4)))
        if m is None:
            return []
        start = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        return [
            RadarFrame(timestamp=start + timedelta(minutes=m + d), precip_mm_h=rate,
                       is_convective=False)
            for d, rate in ((0, 0.2), (10, 0.2), (20, 0.0))
        ]


def _ortsvergleich_lauf(wire: _Wire, user_id: str, orte: list[SavedLocation],
                        minuten_je_ort: dict[str, int], *, style: str = "kurzform") -> None:
    """Faehrt `CompareRadarAlertService.check_all_compare_presets()` fuer
    einen frisch angelegten Ortsvergleich dieses Nutzers."""
    from services.compare_radar_alert import CompareRadarAlertService
    from services.radar_cache import reset_shared_radar_cache_for_tests
    from services.radar_service import RadarNowcastService

    reset_shared_radar_cache_for_tests()
    settings = wire.settings(mit_mail=False)
    mit_profil_kanaele(nutzer_mit_tier(user_id, "premium"), settings)
    _anlegen(user_id, _preset(user_id, f"cp-1767-{uuid.uuid4().hex[:4]}", orte, style=style), orte)
    frames = _FrameQuelle(minuten_je_ort, orte)
    svc = CompareRadarAlertService(
        settings=settings, user_id=user_id,
        radar_service=RadarNowcastService(frame_source=frames),
    )
    sent = svc.check_all_compare_presets()
    assert sent == 1, (
        f"Voraussetzung: genau EIN Ortsvergleich-Radar-Alarm erwartet, war {sent}. "
        f"Nowcast-Abrufe: {frames.calls!r}"
    )


def _direktversand(wire: _Wire, user_id: str, onsets: list[tuple], *,
                   channels: set[str], style: str = "rich"):
    """`send_multi_location_radar_alert` mit echten `NowcastResult`s (ohne
    Ende/Menge, also goldstring-fest) — nur fuer Zusicherungen, die von den
    Ortsnummern NICHT abhaengen (Telegram-Langform, E-Mail).

    `onsets`: `(SavedLocation, onset_minutes, intensity_label, is_convective)`.
    Liefert die am Mail-Sink abgegebenen `(subject, body)`-Paare."""
    from services.notification_service import NotificationService
    from services.radar_service import NowcastResult

    settings = wire.settings(mit_mail=True)
    mit_profil_kanaele(nutzer_mit_tier(user_id, "premium"), settings)
    entities = [
        (loc.name, loc, NowcastResult(
            onset_minutes=m, intensity_label=label, source="radar",
            is_convective=conv,
        ))
        for loc, m, label, conv in onsets
    ]
    mails: list[tuple[str, str]] = []
    NotificationService(settings, user_id).send_multi_location_radar_alert(
        entities, channels, mail_sink=lambda subject, body: mails.append((subject, body)),
        telegram_style=style, preset=None,
    )
    return mails


def _vorschau(user_id: str, preset_id: str, onsets: list[tuple]) -> dict:
    """Alarm-Vorschau (Art Radar/Onset) dieses Nutzers.
    `onsets`: `(location_id, onset_minutes, intensity_label, is_convective)`."""
    from services.compare_alert_preview_service import render_compare_alert_preview

    body = {"onsets": [
        {"location_id": lid, "onset_minutes": m, "intensity_label": label,
         "source": "radar", "is_convective": conv}
        for lid, m, label, conv in onsets
    ]}
    return render_compare_alert_preview(preset_id, user_id=user_id, body=body)


def _positionen_der_tokens(sms: str) -> list[int]:
    """Ortsnummern der Kurzform in Lesereihenfolge (ohne `+k`-Marker)."""
    out = []
    for tok in sms.split(" "):
        m = _POS_TOKEN_RE.match(tok)
        if m:
            out.append(int(m.group(1)))
    return out


# ---------------------------------------------------------------------------
# AC-1 — SMS nennt jeden ausloesenden Ort mit seiner Ortsnummer
# ---------------------------------------------------------------------------


# AC-1 woertlich (Nowcast OHNE Ende-Angabe, z. B. Vorschau-Eingabe):
AC1_OHNE_ENDE = "1:R@14:05 3:R@14:40"
# Derselbe Alarm aus echten Radar-Frames: die Frames tragen ein Ende (s.
# `_FrameQuelle`), die Spec behaelt die bestehende Token-Form „inklusive
# Ende-/Guete-/Pruefmarker" — jedes Orts-Token traegt sein eigenes Ende.
AC1_AUS_FRAMES = "1:R@14:05@14:15 3:R@14:40@14:50"


@freeze_time(GEFRORENE_UHR)
def test_ac1_sms_nennt_jeden_ausloesenden_ort_mit_ortsnummer(data_root, wire):
    """AC-1 GIVEN ein Ortsvergleich Zermatt, Chamonix, Verbier (Positionen
    1-3), Zermatt beginnt 14:05, Verbier 14:40, Chamonix bleibt trocken
    WHEN der echte Alarmlauf (`CompareRadarAlertService`) die SMS versendet
    THEN nennt der Text jeden ausloesenden Ort mit seiner Ortsnummer:
    `1:R@14:05@14:15 3:R@14:40@14:50` (= AC-1 `1:R@14:05 3:R@14:40` plus das
    aus den Frames bekannte Ende je Ort) — ohne Ortsnamen-Kopf, ohne `km0-0`.
    Die woertliche Form ohne Ende pruefen AC-7/AC-10 ueber die Vorschau.

    Der Test laeuft ueber den Aufrufer: er wird nur gruen, wenn
    `compare_radar_alert.py` die Positionen aus `preset["location_ids"]`
    berechnet UND bis ins SMS-Rendering reicht.

    RED heute: `Zermatt: R@14:05@14:15` (nur der fuehrende Ort)."""
    uid = _uid("ac1")
    _ortsvergleich_lauf(wire, uid, DREI_ORTE, {"Zermatt": 5, "Verbier": 40})

    sms = wire.sms()
    assert len(sms) == 1, f"Erwartet genau EINE SMS am Draht: {sms!r}"
    assert sms[0] == AC1_AUS_FRAMES, (
        f"Die SMS muss jeden ausloesenden Ort mit Ortsnummer nennen: {sms[0]!r}"
    )
    assert "Zermatt" not in sms[0] and "km0" not in sms[0]


# ---------------------------------------------------------------------------
# AC-2 — Premium-SMS und Telegram-Kurzstil tragen denselben Text
# ---------------------------------------------------------------------------


@freeze_time(GEFRORENE_UHR)
def test_ac2_premium_sms_und_telegram_kurzstil_identisch_zur_sms(data_root, wire):
    """AC-2 GIVEN dieselbe Lage, Kanaele SMS + Premium-SMS + Telegram-Kurzstil
    WHEN der echte Alarmlauf versendet
    THEN tragen Premium-SMS und Telegram-Kurzstil exakt denselben Text wie
    die SMS (`1:R@14:05@14:15 3:R@14:40@14:50`), jeweils hoechstens 140
    Zeichen.

    RED heute: alle drei tragen `Zermatt: R@14:05@14:15`."""
    uid = _uid("ac2")
    _ortsvergleich_lauf(wire, uid, DREI_ORTE, {"Zermatt": 5, "Verbier": 40})

    sms, premium, tg = wire.sms(), wire.premium(), wire.telegram_texts()
    assert len(sms) == 1 and len(premium) == 1 and len(tg) == 1, (
        f"Je EINE Nachricht pro Kanal erwartet: sms={sms!r} premium={premium!r} tg={tg!r}"
    )
    erwartet = AC1_AUS_FRAMES
    for kanal, text in (("SMS", sms[0]), ("Premium-SMS", premium[0]), ("Telegram-Kurzstil", tg[0])):
        assert text == erwartet, f"{kanal} muss {erwartet!r} tragen, war {text!r}"
        assert len(text) <= 140, f"{kanal} sprengt 140 Zeichen: {len(text)}"


# ---------------------------------------------------------------------------
# AC-3 — Telegram-Langform: EINE Nachricht, eine Zeile je Ort
# ---------------------------------------------------------------------------


def _zeile_mit(text: str, needle: str) -> list[str]:
    return [z for z in text.splitlines() if needle in z]


@freeze_time(GEFRORENE_UHR)
def test_ac3_telegram_langform_eine_nachricht_mit_zeile_je_ort(data_root, wire):
    """AC-3 GIVEN dieselbe Lage, Zermatt mit leichtem, Verbier mit maessigem
    Regen, Telegram im ausfuehrlichen Stil
    WHEN der Alarm gesendet wird
    THEN kommt genau EINE Nachricht mit Kopf „Regen-Alarm: 2 Orte“
    (Katalog `alarm.regen.buendel`), je einer Zeile fuer Zermatt (14:05,
    leichter Regen) und Verbier (14:40, maessiger Regen), ohne Namens-Join im
    Kopf und ohne `km 0–0`.

    RED heute: Kopf `Zermatt, Verbier · km 0–0 · …`, Zeit/Intensitaet nur
    von Zermatt."""
    uid = _uid("ac3")
    _direktversand(wire, uid, [
        (ZERMATT, 5, "leichter Regen", False),
        (VERBIER, 40, "mäßiger Regen", False),
    ], channels={"telegram"}, style="rich")

    tg = wire.telegram_texts()
    assert len(tg) == 1, f"Erwartet genau EINE Telegram-Nachricht: {tg!r}"
    text = tg[0]
    kopf = t("alarm.regen.buendel", "de", n=2)
    assert kopf == "Regen-Alarm: 2 Orte"
    assert text.splitlines()[0] == f"<b>{kopf}</b>", (
        f"Kopf muss der Buendel-Kopf aus dem Katalog sein: {text!r}"
    )
    assert "km 0" not in text and "km0" not in text, f"km 0–0 im Text: {text!r}"
    assert "Zermatt, Verbier" not in text, f"Namens-Join im Text: {text!r}"
    z_zermatt, z_verbier = _zeile_mit(text, "Zermatt"), _zeile_mit(text, "Verbier")
    assert len(z_zermatt) == 1 and len(z_verbier) == 1, (
        f"Je genau EINE Zeile fuer Zermatt und Verbier erwartet: {text!r}"
    )
    assert "14:05" in z_zermatt[0] and "leichter Regen" in z_zermatt[0], z_zermatt[0]
    assert "14:40" in z_verbier[0] and "mäßiger Regen" in z_verbier[0], z_verbier[0]
    assert "14:40" not in z_zermatt[0] and "14:05" not in z_verbier[0]


# ---------------------------------------------------------------------------
# AC-4 — Englisch: Telegram aus dem EN-Katalog, SMS-Tokens unuebersetzt
# ---------------------------------------------------------------------------


@freeze_time(GEFRORENE_UHR)
def test_ac4_englischer_nutzer_telegram_englisch(data_root, wire):
    """AC-4 (Telegram) GIVEN ein Nutzer mit Sprache Englisch und dieselbe Lage
    WHEN der Alarm per Telegram ausfuehrlich kommt
    THEN sind Kopf (`Rain alert: 2 locations`) und Zeilentexte englisch,
    kein deutsches Wort aus dem Katalog.

    RED heute: Kopf `Zermatt, Verbier · km 0–0 · Rain …` (Namens-Join)."""
    uid = _uid("ac4tg")
    _setze_sprache(uid, "en")
    _direktversand(wire, uid, [
        (ZERMATT, 5, "leichter Regen", False),
        (VERBIER, 40, "mäßiger Regen", False),
    ], channels={"telegram"}, style="rich")

    tg = wire.telegram_texts()
    assert len(tg) == 1, f"Erwartet genau EINE Telegram-Nachricht: {tg!r}"
    text = tg[0]
    kopf = t("alarm.regen.buendel", "en", n=2)
    assert kopf == "Rain alert: 2 locations"
    assert text.splitlines()[0] == f"<b>{kopf}</b>", f"EN-Kopf fehlt: {text!r}"
    z_zermatt, z_verbier = _zeile_mit(text, "Zermatt"), _zeile_mit(text, "Verbier")
    assert len(z_zermatt) == 1 and "light rain" in z_zermatt[0], text
    assert len(z_verbier) == 1 and "moderate rain" in z_verbier[0], text
    for deutsch in ("Regen-Alarm", "leichter Regen", "mäßiger Regen", " Orte"):
        assert deutsch not in text, f"Deutscher Text {deutsch!r} in EN-Nachricht: {text!r}"


@freeze_time(GEFRORENE_UHR)
def test_ac4_englischer_nutzer_sms_identisch_zum_deutschen(data_root, wire):
    """AC-4 (SMS) GIVEN ein Nutzer mit Sprache Englisch und dieselbe Lage
    WHEN der echte Alarmlauf die SMS versendet
    THEN ist sie zeichengleich zu AC-1 (`1:R@14:05@14:15 3:R@14:40@14:50`):
    Protokoll-Token (`R`, `@`, Ortsnummer) werden nie uebersetzt.

    RED heute: `Zermatt: R@14:05@14:15`."""
    uid = _uid("ac4sms")
    _setze_sprache(uid, "en")
    _ortsvergleich_lauf(wire, uid, DREI_ORTE, {"Zermatt": 5, "Verbier": 40})

    sms = wire.sms()
    assert sms == [AC1_AUS_FRAMES], f"EN-SMS weicht ab: {sms!r}"


# ---------------------------------------------------------------------------
# AC-5 — 20 Orte: Budget, ganze Tokens, `+k`, frueheste zuerst
# ---------------------------------------------------------------------------


ZWANZIG_ORTE = [
    SavedLocation(
        id=f"loc-a{i:02d}", name=f"Alpenort {i:02d}",
        lat=round(46.00 + 0.03 * i, 4), lon=round(7.00 + 0.03 * i, 4), elevation_m=1200,
    )
    for i in range(1, 21)
]


@freeze_time(GEFRORENE_UHR)
def test_ac5_zwanzig_orte_budget_und_ueberlaufzaehler(data_root, wire):
    """AC-5 GIVEN 20 gleichzeitig ausloesende Orte, deren Beginn GEGEN die
    Preset-Reihenfolge laeuft (Ort 20 zuerst: 14:01, Ort 1 zuletzt: 14:39)
    WHEN der echte Alarmlauf SMS, Premium-SMS und Telegram-Kurzstil versendet
    THEN ist jeder Text <= 140 Zeichen, besteht nur aus ganzen Tokens
    `<pos>:R@H:MM@H:MM` (Beginn + Ende aus den Frames), nennt die Orte mit
    fruehestem Beginn zuerst (20, 19, …) und endet auf ` +k` mit
    k == 20 - Anzahl genannter Orte; alle drei Texte sind identisch.

    RED heute: `Alpenort 01: R@14:38@14:48` — ein Ort (Preset-Erster statt
    Fruehester), kein `+k`."""
    uid = _uid("ac5")
    minuten = {o.name: 40 - 2 * i for i, o in enumerate(ZWANZIG_ORTE, start=1)}
    _ortsvergleich_lauf(wire, uid, ZWANZIG_ORTE, minuten)

    sms, premium, tg = wire.sms(), wire.premium(), wire.telegram_texts()
    assert len(sms) == 1, f"Erwartet genau EINE SMS: {sms!r}"
    text = sms[0]
    assert premium == [text] and tg == [text], (
        f"Premium-SMS/Telegram-Kurzstil weichen ab: sms={text!r} premium={premium!r} tg={tg!r}"
    )
    assert len(text) <= 140, f"{len(text)} Zeichen > 140: {text!r}"
    m = re.search(r" \+(\d+)$", text)
    assert m, f"Text endet nicht auf ' +k': {text!r}"
    k = int(m.group(1))
    tokens = text[: m.start()].split(" ")
    for tok in tokens:
        assert re.fullmatch(r"\d+:R@\d{1,2}:\d{2}@\d{1,2}:\d{2}", tok), (
            f"Token {tok!r} ist kein ganzes `<pos>:R@H:MM@H:MM`-Token: {text!r}"
        )
    positionen = [int(tok.split(":", 1)[0]) for tok in tokens]
    assert len(positionen) + k == 20, f"genannt {len(positionen)} + k={k} != 20: {text!r}"
    assert positionen == list(range(20, 20 - len(positionen), -1)), (
        f"Frueheste Orte (Ort 20 = 14:01) muessen zuerst stehen: {positionen!r}"
    )


# ---------------------------------------------------------------------------
# AC-6 — Reihenfolge nach Beginn, Gleichstand kleinere Ortsnummer, in ALLEN
#        Kanaelen gleich
# ---------------------------------------------------------------------------


@freeze_time(GEFRORENE_UHR)
def test_ac6_reihenfolge_nach_beginn_in_kurzform(data_root, wire):
    """AC-6 (Kurzform) GIVEN Zermatt (Pos 1) 14:40, Chamonix (Pos 2) 14:10,
    Verbier (Pos 3) 14:10 — Beginn gegen die Preset-Reihenfolge, Chamonix und
    Verbier gleichauf
    WHEN der echte Alarmlauf SMS, Premium-SMS und Telegram-Kurzstil versendet
    THEN lautet jede Kurzform `2:R@14:10@14:20 3:R@14:10@14:20 1:R@14:40@14:50`
    (Ortsnummern-Folge 2, 3, 1).

    RED heute: `Zermatt: R@14:40@14:50` — nur der Preset-Erste, obwohl er
    als Letzter beginnt."""
    uid = _uid("ac6k")
    _ortsvergleich_lauf(wire, uid, DREI_ORTE, {"Zermatt": 40, "Chamonix": 10, "Verbier": 10})

    erwartet = "2:R@14:10@14:20 3:R@14:10@14:20 1:R@14:40@14:50"
    for kanal, texte in (("SMS", wire.sms()), ("Premium-SMS", wire.premium()),
                         ("Telegram-Kurzstil", wire.telegram_texts())):
        assert texte == [erwartet], f"{kanal}: erwartet {erwartet!r}, war {texte!r}"
        assert _positionen_der_tokens(texte[0]) == [2, 3, 1]


@freeze_time(GEFRORENE_UHR)
def test_ac6_reihenfolge_nach_beginn_in_telegram_und_email(data_root, wire):
    """AC-6 (Langform) GIVEN dieselbe Lage (Zermatt 14:40, Chamonix 14:10,
    Verbier 14:10, Preset-Reihenfolge Zermatt, Chamonix, Verbier)
    WHEN der Alarm per Telegram-Langform und E-Mail gesendet wird
    THEN fuehren beide die Orte als Chamonix, Verbier, Zermatt — dieselbe
    Reihenfolge wie die Kurzform (`2: 3: 1:`).

    RED heute: die E-Mail steht in Preset-Reihenfolge (Zermatt zuerst), die
    Telegram-Langform nennt nur einen Join-Kopf."""
    uid = _uid("ac6l")
    mails = _direktversand(wire, uid, [
        (ZERMATT, 40, "leichter Regen", False),
        (CHAMONIX, 10, "leichter Regen", False),
        (VERBIER, 10, "leichter Regen", False),
    ], channels={"telegram", "email"}, style="rich")

    namen = ["Zermatt", "Chamonix", "Verbier"]
    erwartet = ["Chamonix", "Verbier", "Zermatt"]
    assert len(mails) == 1, f"Erwartet genau EINE Mail: {mails!r}"
    _subject, body = mails[0]
    daten = [z for z in body.splitlines() if any(n in z for n in namen)]
    assert [next(n for n in namen if n in z) for z in daten] == erwartet, (
        f"E-Mail-Zeilen nicht nach Beginn sortiert: {daten!r}"
    )
    tg = wire.telegram_texts()
    assert len(tg) == 1, f"Erwartet genau EINE Telegram-Nachricht: {tg!r}"
    zeilen = [z for z in tg[0].splitlines()[1:] if any(n in z for n in namen)]
    assert [next(n for n in namen if n in z) for z in zeilen] == erwartet, (
        f"Telegram-Zeilen nicht nach Beginn sortiert: {tg[0]!r}"
    )


# ---------------------------------------------------------------------------
# AC-7 — Vorschau == Versand (Mehrort-Fall)
# ---------------------------------------------------------------------------


@freeze_time(GEFRORENE_UHR)
def test_ac7_vorschau_sms_gleich_versand_sms(data_root, wire):
    """AC-7 GIVEN derselbe Ortsvergleich und dieselbe Lage (Zermatt 14:05,
    Verbier 14:40)
    WHEN erst die Alarm-Vorschau gerendert und dann der echte Alarm versendet
    wird
    THEN nennt die Vorschau-SMS alle ausloesenden Orte (`1:R@14:05 3:R@14:40`)
    und ist zeichengleich zur versendeten.

    Referenz ist der Versand so, wie `compare_radar_alert.py` ihn aufruft:
    `send_multi_location_radar_alert` mit denselben Nowcast-Eingaben (ohne
    Ende, wie die Vorschau-Eingabe) und den Ortsnummern aus derselben
    Positionsfunktion (`CompareAlertService._location_positions` ueber
    `preset["location_ids"]`). Ein Lauf ueber Radar-Frames waere hier kein
    Vergleich: Frames tragen ein Ende, die Vorschau-Eingabe nicht.

    RED heute: Vorschau `Zermatt: R@14:05` (inhaltlich); danach kennt
    `send_multi_location_radar_alert` den Parameter `location_positions`
    noch nicht."""
    from services.compare_alert import CompareAlertService
    from services.notification_service import NotificationService
    from services.radar_service import NowcastResult

    uid = _uid("ac7")
    preset = _preset(uid, "cp-1767-ac7", DREI_ORTE)
    _anlegen(uid, preset, DREI_ORTE)

    vorschau = _vorschau(uid, "cp-1767-ac7", [
        (ZERMATT.id, 5, "leichter Regen", False),
        (VERBIER.id, 40, "leichter Regen", False),
    ])
    assert vorschau["sms"] == AC1_OHNE_ENDE, (
        f"Vorschau nennt nicht alle Orte mit Ortsnummer: {vorschau['sms']!r}"
    )

    settings = wire.settings(mit_mail=False)
    mit_profil_kanaele(nutzer_mit_tier(uid, "premium"), settings)
    positionen = CompareAlertService._location_positions(
        preset["location_ids"], {o.id: o for o in DREI_ORTE},
    )
    NotificationService(settings, uid).send_multi_location_radar_alert(
        [(o.name, o, NowcastResult(onset_minutes=m, intensity_label="leichter Regen",
                                   source="radar", is_convective=False))
         for o, m in ((ZERMATT, 5), (VERBIER, 40))],
        {"sms"}, telegram_style="kurzform", preset=preset,
        location_positions=positionen,
    )
    versand = wire.sms()
    assert versand == [vorschau["sms"]], (
        f"Vorschau-SMS {vorschau['sms']!r} != Versand-SMS {versand!r}"
    )


# ---------------------------------------------------------------------------
# AC-8 — Regressionsschutz Ein-Ort (darf heute GRUEN sein)
# ---------------------------------------------------------------------------


@freeze_time(GEFRORENE_UHR)
def test_ac8_ein_ort_ortsvergleich_und_trip_byte_identisch(data_root, wire):
    """AC-8 (REGRESSIONSSCHUTZ — darf heute GRUEN sein) GIVEN ein Ortsvergleich
    mit genau EINEM ausloesenden Ort (Zermatt 14:05, Chamonix/Verbier trocken)
    und ein Trip-Radar-Alarm (immer ein Ort)
    WHEN gerendert/versendet
    THEN bleibt die Kurzform byte-identisch zur bisherigen: `Zermatt: R@14:05`
    (Vorschau-Eingabe ohne Ende), `Zermatt: R@14:05@14:15` (echter Lauf aus
    Frames, gemessen vor dem Umbau) bzw. `km 5-18: R@14:35` (Trip) — ohne
    Ortsnummer, ohne `+k`, auch wenn Positionen vorliegen."""
    from output.renderers.alert.model import AlertMessage, OnsetEvent
    from output.renderers.alert.render import render_sms
    from app.ampel import resolve_ampel

    uid = _uid("ac8")
    _ortsvergleich_lauf(wire, uid, DREI_ORTE, {"Zermatt": 5})
    ein_ort = "Zermatt: R@14:05@14:15"
    assert wire.sms() == [ein_ort], f"Ein-Ort-Compare veraendert: {wire.sms()!r}"
    assert wire.premium() == [ein_ort]
    assert wire.telegram_texts() == [ein_ort]

    preset_id = next(p.stem for p in (get_data_dir(uid) / "briefings").glob("*.json"))
    vorschau = _vorschau(uid, preset_id, [(ZERMATT.id, 5, "leichter Regen", False)])
    assert vorschau["sms"] == "Zermatt: R@14:05", f"Ein-Ort-Vorschau: {vorschau['sms']!r}"

    trip_event = OnsetEvent(
        onset_minutes=12, onset_time="14:35", km_from=5.0, km_to=18.0,
        is_convective=False, intensity_label="leichter Regen",
        source_label="Radar (DWD)", location_label=None,
    )
    trip_msg = AlertMessage(
        trip_short="GR20-Test", stand_at="14:23", events=(trip_event,),
        source="Radar (DWD)", cooldown_display="2 Stunden", ampel=resolve_ampel(None),
    )
    assert render_sms(trip_msg, limit=140) == "km 5-18: R@14:35"
    assert render_sms(trip_msg, limit=140, location_positions={"GR20-Test": 1}) == "km 5-18: R@14:35"


# ---------------------------------------------------------------------------
# AC-9 — B2-51: jede Datenzeile traegt ihren eigenen Ortsnamen (Beleg, darf
#        heute GRUEN sein)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("namen", [
    ["Zermatt", "Chamonix"],
    ["Zermatt", "Chamonix", "Verbier"],
], ids=["zwei-gruppen", "drei-gruppen"])
def test_ac9_b2_51_mehrgruppen_email_traegt_eigenen_ortsnamen(namen):
    """AC-9 (B2-51-BELEG, kein Codefix — darf heute GRUEN sein) GIVEN eine
    Mehr-Gruppen-Projektion (`to_multi_point_alert_message`) mit 2 bzw. 3
    Orten, je Ort ein anderer Wert
    WHEN `render_email` rendert
    THEN steht jeder Wert in einer Zeile mit dem Namen SEINES Ortes; der
    Rueckfall `msg.location_label` setzt nie einen fremden Ortsnamen. Der
    Ein-Gruppen-Fall nennt denselben (einzigen) Ort."""
    from app.ampel import resolve_ampel
    from app.models import ChangeSeverity, WeatherChange
    from output.renderers.alert.project import to_multi_point_alert_message
    from output.renderers.alert.render import render_email

    def _change(neu: float) -> WeatherChange:
        return WeatherChange(
            metric="gust_max_kmh", old_value=20.0, new_value=neu, delta=neu - 20.0,
            threshold=50.0, severity=ChangeSeverity("major"), direction="increase",
        )

    orte = {o.name: o for o in DREI_ORTE}
    # Werte so gewaehlt, dass kein Neuwert als Delta eines anderen Ortes
    # auftaucht (63/77/92 -> Deltas 43/57/72).
    werte = {name: w for name, w in zip(namen, (63.0, 77.0, 92.0))}
    groups = [(name, [_change(werte[name])], orte[name]) for name in namen]
    msg = to_multi_point_alert_message(
        groups, tz=timezone.utc, stand_at="14:00", ampel=resolve_ampel(None),
    )
    assert all(e.location_label for e in msg.events), (
        f"B2-51: jedes Event muss seinen Ortsnamen tragen: {msg.events!r}"
    )
    assert {e.location_label for e in msg.events} == set(namen)
    _html, plain = render_email(msg)
    for name in namen:
        wert = f"{int(werte[name])}"
        zeilen = [z for z in plain.splitlines() if f" {wert} km/h" in z]
        assert zeilen, f"Wert {wert} von {name} fehlt in der E-Mail: {plain!r}"
        fremd = [n for n in namen if n != name]
        for z in zeilen:
            assert not any(f in z for f in fremd), (
                f"B2-51: Wert von {name} steht unter fremdem Ortsnamen: {z!r}"
            )
    # Ein-Gruppen-Fall: derselbe Ort, kein fremder Name.
    einzeln = to_multi_point_alert_message(
        [groups[0]], tz=timezone.utc, stand_at="14:00", ampel=resolve_ampel(None),
    )
    _h, plain1 = render_email(einzeln)
    assert namen[0] in plain1
    assert not any(n in plain1 for n in namen[1:]), plain1


# ---------------------------------------------------------------------------
# AC-10 — zwei Nutzer, gleichnamige Orte, eigene Preset-Reihenfolge
# ---------------------------------------------------------------------------


@freeze_time(GEFRORENE_UHR)
def test_ac10_zwei_nutzer_vorschau_traegt_eigene_ortsnummern(data_root):
    """AC-10 GIVEN zwei Nutzer mit gleichnamigen Orten (Zermatt, Chamonix,
    Verbier), Nutzer A in der Reihenfolge Zermatt, Chamonix, Verbier, Nutzer B
    in der Reihenfolge Verbier, Chamonix, Zermatt; Zermatt beginnt 14:05,
    Verbier 14:40
    WHEN fuer jeden Nutzer die Vorschau mit SEINER `user_id` gerendert wird
    THEN traegt A `1:R@14:05 3:R@14:40` und B `3:R@14:05 1:R@14:40` — je die
    Ortsnummern des EIGENEN Presets, nie die des anderen.

    RED heute: beide tragen `Zermatt: R@14:05`."""
    uid_a, uid_b = _uid("ac10a"), _uid("ac10b")
    assert uid_a != uid_b
    _anlegen(uid_a, _preset(uid_a, "cp-1767-ac10", DREI_ORTE), DREI_ORTE)
    _anlegen(uid_b, _preset(uid_b, "cp-1767-ac10", list(reversed(DREI_ORTE))), DREI_ORTE)

    onsets = [(ZERMATT.id, 5, "leichter Regen", False), (VERBIER.id, 40, "leichter Regen", False)]
    sms_a = _vorschau(uid_a, "cp-1767-ac10", onsets)["sms"]
    sms_b = _vorschau(uid_b, "cp-1767-ac10", onsets)["sms"]

    assert sms_a == "1:R@14:05 3:R@14:40", f"Nutzer A: {sms_a!r}"
    assert sms_b == "3:R@14:05 1:R@14:40", f"Nutzer B: {sms_b!r}"
    with pytest.raises(LookupError):
        _vorschau("default", "cp-1767-ac10", onsets)
