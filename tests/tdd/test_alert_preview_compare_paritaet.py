"""TDD RED — Issue #2283 Scheibe S4, AC-17 / AC-18 / AC-19 (Python-Kern).

Spec: docs/specs/modules/shared_preview_tab.md

Die Alarm-Vorschau des Ortsvergleichs muss je Kanal DIESELBE Nachricht
zeigen, die der Versand fuer dieselbe Eingabe erzeugt (ADR-0011: ein
Alarm-Renderer). Keine zweite Rendervariante, keine Projektion gemockt.

Vertrag des neuen Moduls (von diesen Tests festgelegt):

    from services.compare_alert_preview_service import render_compare_alert_preview

    render_compare_alert_preview(preset_id: str, *, user_id: str, body: dict) -> dict
        -> {"subject": str, "email_html": str, "email_plain": str,
            "telegram": str, "telegram_bubbles": list[str], "sms": str}

    `telegram_bubbles` = genau die Telegram-Nachrichten, die der Versand
    schickt (Aenderungsalarm: eine Sprechblase JE ORT, #1467 AG3a; Kurzstil:
    EINE Nachricht = SMS-Text; Radar/amtlich: eine Nachricht). `telegram`
    enthaelt jede dieser Blasen (bei genau einer: identisch).

    `body` — orts- statt segmentbezogen, GENAU EINES von:
      {"changes":  [{"location_id", "metric", "old_value", "new_value",
                     "delta", "threshold", "severity", "direction"}, ...]}
      {"onsets":   [{"location_id", "onset_minutes", "intensity_label",
                     "source", "is_convective"}, ...]}
      {"official": [{"source", "hazard", "level", "label", "valid_from",
                     "valid_to", "region_label", "location_ids": [...]}, ...]}

Referenzen = der ECHTE Versandweg, keine Nachbildung im Test (Zusicherung
am Wirkort gemessen, #2283 Adversary-Vorgabe):
- Abweichung (AC-17): `NotificationService.send_multi_location_deviation_alert`
  → `_dispatch_alert_message`, mit denselben Aufruf-Parametern wie
  `compare_alert.py` (Positionen aus `CompareAlertService._location_positions`,
  `effective_compare_telegram_style`).
- Radar/Onset (AC-18): `send_multi_location_radar_alert` mit dem
  Cooldown-Text aus `compare_radar_alert._format_cooldown_display` (wie
  `compare_radar_alert.py`).
  Mitschnitt fuer AC-17/18 am Draht: Betreff + Klartext ueber `mail_sink`,
  Telegram ueber einen lokalen Bot-API-Stub (`TELEGRAM_API_BASE` →
  127.0.0.1), SMS ueber einen lokalen seven.io-Stub (`sms_gateway_url` →
  127.0.0.1, Sandbox-Key) — Haus-Muster `test_radar_alert_telegram_style.py`
  / `test_alert_addendum_sms.py`. Nichts geht an echte Empfaenger; das
  SMS-Tageskontingent wird nur im isolierten tmp-Datenordner reserviert.
  Bekannte Grenze: das E-Mail-HTML gibt der Versand nur an den echten
  `EmailOutput` — es wird hier nicht am Draht verglichen (Ableitung aus
  derselben Nachricht wie der verglichene Klartext).
- Amtlich (AC-19): der ECHTE Versand `send_multi_location_official_alert`
  mit Aufzeichnungs-Senken (mail_sink/telegram_sink/sms_sink).

Zeit: Stand-Zeile und Onset-Uhrzeiten haengen an `now()`. Jeder Vergleich
laeuft Referenz → Vorschau → Referenz; nur wenn beide Referenzen gleich sind
(kein Minutenwechsel), wird verglichen — sonst Wiederholung.

RED-Grund: `services.compare_alert_preview_service` existiert nicht →
ModuleNotFoundError in jedem Test (Import bewusst IN der Testfunktion).
"""
from __future__ import annotations

import http.server
import json
import socket
import threading
import urllib.parse
from datetime import datetime, timedelta, timezone

import pytest

import output.channels.telegram as tg_module
from app.config import Settings
from app.loader import get_data_dir, save_location
from app.user import SavedLocation

from tests.helpers.compare_briefings import write_compare_briefings
from tests.helpers.nutzer_tier import nutzer_mit_tier
from tests.helpers.telegram_empfaenger import profil_chat
from tests.helpers.vorschau_umgebung import env  # noqa: F401  (Fixture)

PRESET_ID = "cp-2283-alarm"
PRESET_NAME = "Alarm-Vergleich 2283"
COOLDOWN_MIN = 90

LOCATIONS = [
    SavedLocation(id="loc-ibk", name="Innsbruck", lat=47.27, lon=11.39, elevation_m=574),
    SavedLocation(id="loc-bz", name="Bozen", lat=46.50, lon=11.35, elevation_m=262),
    SavedLocation(id="loc-mer", name="Meran", lat=46.67, lon=11.16, elevation_m=325),
    # Weitere Orte nur fuer den Langfall (SMS-Kuerzung greift erst ab ~8 Orten
    # mit mehreren Metriken — sonst bliebe das 140er-Limit unbeobachtbar).
    SavedLocation(id="loc-sz", name="Schwaz", lat=47.35, lon=11.71, elevation_m=545),
    SavedLocation(id="loc-hall", name="Hall", lat=47.28, lon=11.51, elevation_m=574),
    SavedLocation(id="loc-imst", name="Imst", lat=47.24, lon=10.74, elevation_m=828),
    SavedLocation(id="loc-lz", name="Lienz", lat=46.83, lon=12.77, elevation_m=673),
    SavedLocation(id="loc-kuf", name="Kufstein", lat=47.58, lon=12.17, elevation_m=499),
]
ALL_IDS = [loc.id for loc in LOCATIONS]

# Woerter, die eine Handlungsempfehlung anzeigen (CLAUDE.md/PO: nur Daten).
EMPFEHLUNGS_PHRASEN = ("empfohlen", "empfehl", "sollten", "meiden", "bitte", "verhalten")


def _seed(user_id: str, *, telegram_style: str | None = None) -> dict:
    for loc in LOCATIONS:
        save_location(loc, user_id=user_id)
    preset = {
        "id": PRESET_ID,
        "name": PRESET_NAME,
        "user_id": user_id,
        "location_ids": [loc.id for loc in LOCATIONS],
        "schedule": "daily",
        "profil": "ALLGEMEIN",
        "hour_from": 9,
        "hour_to": 16,
        "forecast_hours": 48,
        "alert_cooldown_minutes": COOLDOWN_MIN,
        "empfaenger": ["a@example.invalid"],
        "created_at": "2026-07-01T00:00:00Z",
    }
    if telegram_style:
        preset["display_config"] = {"telegram_style": telegram_style}
    write_compare_briefings(get_data_dir(user_id), [preset])
    return preset


def _visible_text(html: str) -> str:
    from bs4 import BeautifulSoup

    return BeautifulSoup(html, "html.parser").get_text(" ")


def _loc(loc_id: str) -> SavedLocation:
    return next(loc for loc in LOCATIONS if loc.id == loc_id)


def _stable(reference, preview, attempts: int = 3):
    """Referenz → Vorschau → Referenz; liefert (vorschau, referenz), sobald
    beide Referenzen gleich sind (kein Minutenwechsel dazwischen)."""
    for _ in range(attempts):
        before = reference()
        got = preview()
        after = reference()
        if before == after:
            return got, before
    pytest.fail("Referenz war in drei Laeufen nicht stabil (Uhr springt?)")


def _assert_channels_equal(got: dict, ref: dict, label: str) -> None:
    for key in ("subject", "email_html", "email_plain", "sms", "telegram_bubbles"):
        if key not in ref:
            continue
        assert key in got, f"{label}: Feld '{key}' fehlt in der Vorschau: {sorted(got)}"
        assert got[key] == ref[key], (
            f"{label}: Kanal '{key}' weicht vom Versand ab.\n"
            f"Vorschau: {got[key]!r}\nVersand:  {ref[key]!r}"
        )
    for bubble in ref["telegram_bubbles"]:
        assert bubble in got["telegram"], f"{label}: Telegram-Feld enthaelt Blase nicht"
    if len(ref["telegram_bubbles"]) == 1:
        assert got["telegram"] == ref["telegram_bubbles"][0], f"{label}: telegram != Blase"


# ---------------------------------------------------------------------------
# Draht-Mitschnitt des echten Versands (AC-17/18) — lokale HTTP-Stubs, kein Mock
# ---------------------------------------------------------------------------


def _free_port() -> int:
    s = socket.socket()
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class _RecordingServer:
    """Lokaler HTTP-Server auf 127.0.0.1; `parse` macht aus dem POST-Koerper
    einen Eintrag, `reply` ist die Antwort (Vorbild _TelegramStub/_SevenIoStub)."""

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
    """Beide Stubs + Settings, die AUSSCHLIESSLICH auf 127.0.0.1 zeigen."""

    def __init__(self, telegram: _RecordingServer, sms: _RecordingServer) -> None:
        self.telegram = telegram
        self.sms = sms

    def settings(self, user_id: str) -> Settings:
        chat = "99999"
        profil_chat(user_id, chat)  # TelegramRecipient.for_user liest user.json
        # SMS-Tageslimit (#2412): ohne Tarif gilt "free" (Cap 0) -> gesperrt.
        nutzer_mit_tier(user_id, "premium")
        # #1412 S4b: SMS nur an die bestaetigte Profilnummer.
        from tests.helpers.sms_empfaenger import profil_sms

        profil_sms(user_id, "+49000000000")
        return Settings().model_copy(update={
            "smtp_host": "smtp.test.invalid", "smtp_user": "t@test.invalid",
            "smtp_pass": "x", "mail_to": "to@test.invalid",
            "telegram_bot_token": "test-token-2283", "telegram_chat_id": chat,
            "telegram_test_chat_id": chat,
            "sms_gateway_url": f"{self.sms.base_url}/api/sms",
            "seven_api_key": "sandbox-key-2283", "seven_sandbox_key": "sandbox-key-2283",
            "sms_to": "+49000000000", "sms_from": None,
        })

    def capture(self, send) -> dict:
        """Fuehrt `send(mail_sink)` aus und liefert, was am Draht ankam."""
        tg0, sms0 = len(self.telegram.received), len(self.sms.received)
        mails: list[tuple[str, str]] = []
        send(lambda subject, body: mails.append((subject, body)))
        tgs = [p.get("text", "") for p in self.telegram.received[tg0:]]
        smss = [p.get("text", "") for p in self.sms.received[sms0:]]
        assert len(mails) == 1, f"Versand: {len(mails)} Mails an der Senke statt 1"
        assert tgs, "Versand: keine Telegram-Nachricht am Stub angekommen"
        assert len(smss) == 1, f"Versand: {len(smss)} SMS am Stub statt 1"
        return {
            "subject": mails[0][0], "email_plain": mails[0][1],
            "sms": smss[0], "telegram_bubbles": tgs,
        }


@pytest.fixture
def wire(monkeypatch):
    telegram = _RecordingServer(_parse_json, b'{"ok": true, "result": {"message_id": 1}}')
    sms = _RecordingServer(_parse_form, b"100")
    monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", telegram.base_url)
    assert tg_module.TELEGRAM_API_BASE.startswith("http://127.0.0.1:")
    yield _Wire(telegram, sms)
    telegram.stop()
    sms.stop()


# ---------------------------------------------------------------------------
# AC-17 — Abweichung (to_multi_point_alert_message)
# ---------------------------------------------------------------------------


_METRICS = [  # (metric, alt, neu, schwelle)
    ("gust_max_kmh", 25.0, 72.0, 60.0), ("wind_max_kmh", 15.0, 55.0, 40.0),
    ("precip_sum_mm", 1.0, 30.0, 20.0), ("temp_max_c", 20.0, 33.0, 30.0),
]


def _change_dicts(loc_ids: list[str], n_metrics: int = 1) -> list[dict]:
    out = []
    for i, loc_id in enumerate(loc_ids):
        for metric, old, new, threshold in _METRICS[:n_metrics]:
            out.append({
                "location_id": loc_id, "metric": metric,
                "old_value": old + i, "new_value": new + i, "delta": new - old,
                "threshold": threshold, "severity": "major", "direction": "increase",
            })
    return out


_CHANNELS = {"email", "telegram", "sms"}


def _deviation_reference(preset: dict, body: dict, user_id: str, wire: "_Wire") -> dict:
    """Der ECHTE Versand `send_multi_location_deviation_alert`, aufgerufen wie
    `compare_alert.py` es tut; gemessen wird, was am Draht ankommt."""
    from app.models import ChangeSeverity, WeatherChange
    from services.compare_alert import CompareAlertService
    from services.compare_alert_channels import effective_compare_telegram_style
    from services.notification_service import NotificationService

    by_loc: dict[str, list] = {}
    for c in body["changes"]:
        by_loc.setdefault(c["location_id"], []).append(WeatherChange(
            metric=c["metric"], old_value=c["old_value"], new_value=c["new_value"],
            delta=c["delta"], threshold=c["threshold"],
            severity=ChangeSeverity(c["severity"]), direction=c["direction"],
        ))
    ordered = [lid for lid in preset["location_ids"] if lid in by_loc]
    entities = [(_loc(lid).name, [_loc(lid)], by_loc[lid]) for lid in ordered]
    positions = CompareAlertService._location_positions(
        preset["location_ids"], {loc.id: loc for loc in LOCATIONS},
    )
    service = NotificationService(wire.settings(user_id), user_id)
    return wire.capture(lambda mail_sink: service.send_multi_location_deviation_alert(
        entities, _CHANNELS, mail_sink=mail_sink, location_positions=positions,
        telegram_style=effective_compare_telegram_style(preset),
    ))


@pytest.mark.parametrize(
    "loc_ids,telegram_style,n_metrics",
    [
        (["loc-bz"], None, 1),
        (["loc-ibk", "loc-mer"], None, 1),
        (["loc-ibk", "loc-bz", "loc-mer"], None, 1),
        (["loc-ibk", "loc-mer"], "kurzform", 1),
        (ALL_IDS, None, 4),
    ],
    ids=["ein-ort", "zwei-orte", "drei-orte", "zwei-orte-kurzform", "acht-orte-sms-gekuerzt"],
)
def test_compare_deviation_alert_preview_equals_dispatch_projection(
    env, wire, loc_ids, telegram_style, n_metrics,  # noqa: F811
):
    """AC-17: GIVEN ein Ortsvergleich mit Abweichung an einem/mehreren Orten
    WHEN die Alarm-Vorschau (Art Abweichung) abgerufen wird
    THEN ist jeder Kanal identisch zur Nachricht, die der Versand ueber
    `to_multi_point_alert_message` fuer dieselbe Eingabe erzeugt — inklusive
    Ortsnummern in der SMS und einer Telegram-Blase je Ort (Kurzstil: SMS-Text).

    RED: services.compare_alert_preview_service fehlt (ModuleNotFoundError)."""
    from services.compare_alert_preview_service import render_compare_alert_preview

    user_id = env
    preset = _seed(user_id, telegram_style=telegram_style)
    body = {"changes": _change_dicts(loc_ids, n_metrics)}

    got, ref = _stable(
        lambda: _deviation_reference(preset, body, user_id, wire),
        lambda: render_compare_alert_preview(PRESET_ID, user_id=user_id, body=body),
    )
    _assert_channels_equal(got, ref, f"Abweichung {loc_ids}")
    if len(loc_ids) > 1 and telegram_style is None:
        assert len(got["telegram_bubbles"]) == len(loc_ids), "eine Telegram-Blase je Ort"


# ---------------------------------------------------------------------------
# AC-18 — Radar/Onset (to_multi_location_onset_alert_message)
# ---------------------------------------------------------------------------


def _onset_dicts(loc_ids: list[str]) -> list[dict]:
    return [
        {"location_id": lid, "onset_minutes": 20 + 10 * i,
         "intensity_label": "mäßiger Regen", "source": "radar", "is_convective": i == 1}
        for i, lid in enumerate(loc_ids)
    ]


def _onset_reference(preset: dict, body: dict, user_id: str, wire: "_Wire") -> dict:
    """Der ECHTE Versand `send_multi_location_radar_alert`, aufgerufen wie
    `compare_radar_alert.py` es tut; gemessen wird, was am Draht ankommt."""
    from services.compare_alert_channels import effective_compare_telegram_style
    from services.compare_radar_alert import _format_cooldown_display
    from services.notification_service import NotificationService
    from services.radar_service import NowcastResult

    by_loc = {o["location_id"]: o for o in body["onsets"]}
    ordered = [lid for lid in preset["location_ids"] if lid in by_loc]
    entities = [
        (_loc(lid).name, _loc(lid), NowcastResult(
            onset_minutes=by_loc[lid]["onset_minutes"],
            intensity_label=by_loc[lid]["intensity_label"],
            source=by_loc[lid]["source"],
            is_convective=by_loc[lid]["is_convective"],
        ))
        for lid in ordered
    ]
    service = NotificationService(wire.settings(user_id), user_id)
    return wire.capture(lambda mail_sink: service.send_multi_location_radar_alert(
        entities, _CHANNELS, mail_sink=mail_sink,
        cooldown_display=_format_cooldown_display(COOLDOWN_MIN),
        telegram_style=effective_compare_telegram_style(preset),
    ))


@pytest.mark.parametrize(
    "loc_ids,telegram_style",
    [
        (["loc-ibk"], None),
        (["loc-ibk", "loc-bz", "loc-mer"], None),
        (["loc-ibk", "loc-bz", "loc-mer"], "kurzform"),
    ],
    ids=["ein-ort", "drei-orte", "drei-orte-kurzform"],
)
def test_compare_onset_alert_preview_equals_dispatch_projection(env, wire, loc_ids, telegram_style):  # noqa: F811
    """AC-18: GIVEN ein Ortsvergleich und ein Regen-/Radar-Ereignis an einem
    oder mehreren Orten
    WHEN die Alarm-Vorschau (Art Radar/Onset) abgerufen wird
    THEN ist jeder Kanal identisch zur Nachricht, die der Versand
    `send_multi_location_radar_alert` (mit dem Cooldown-Hinweis des Presets)
    am Draht abliefert — auch im Telegram-Kurzstil."""
    from services.compare_alert_preview_service import render_compare_alert_preview

    user_id = env
    preset = _seed(user_id, telegram_style=telegram_style)
    body = {"onsets": _onset_dicts(loc_ids)}

    got, ref = _stable(
        lambda: _onset_reference(preset, body, user_id, wire),
        lambda: render_compare_alert_preview(PRESET_ID, user_id=user_id, body=body),
    )
    _assert_channels_equal(got, ref, f"Onset {loc_ids}")


# ---------------------------------------------------------------------------
# AC-19 — amtliche Warnung (echter Versandweg mit Aufzeichnungs-Senken)
# ---------------------------------------------------------------------------


def _official_dicts(loc_ids: list[str]) -> list[dict]:
    start = (datetime.now(timezone.utc) + timedelta(hours=3)).replace(
        minute=0, second=0, microsecond=0,
    )
    return [{
        "source": "geosphere_warn", "hazard": "thunderstorm", "level": 3,
        "label": "Gewitter", "valid_from": start.isoformat(),
        "valid_to": (start + timedelta(hours=6)).isoformat(),
        "region_label": "Innsbruck-Land", "location_ids": loc_ids,
    }]


def _official_reference(preset: dict, body: dict, user_id: str) -> dict:
    """Der ECHTE Versand `send_multi_location_official_alert` mit Senken."""
    from app.config import Settings
    from output.renderers.alert.official_alerts import (
        build_compare_official_alert_notices, render_official_alert_sms_with_allclears,
    )
    from services.compare_alert_channels import effective_compare_telegram_style
    from services.notification_service import NotificationService
    from services.official_alerts.models import OfficialAlert
    from utils.timezone import resolve_location_tz

    tagged = [
        (OfficialAlert(
            source=o["source"], hazard=o["hazard"], level=o["level"], label=o["label"],
            valid_from=datetime.fromisoformat(o["valid_from"]),
            valid_to=datetime.fromisoformat(o["valid_to"]),
            region_label=o["region_label"],
        ), list(o["location_ids"]))
        for o in body["official"]
    ]
    settings = Settings(
        smtp_host="smtp.test.invalid", smtp_user="t@test.invalid", smtp_pass="x",
        mail_to="to@test.invalid", telegram_bot_token="tok", telegram_chat_id="1",
        sms_gateway_url="http://sms.test.invalid", seven_api_key="k", sms_to="+491700000000",
    )
    mails, tgs, smss = [], [], []
    NotificationService(settings, user_id).send_multi_location_official_alert(
        preset["name"], list(LOCATIONS), tagged, {"email", "telegram", "sms"},
        effective_compare_telegram_style(preset),
        mail_sink=lambda subject, body: mails.append((subject, body)),
        telegram_sink=lambda text: tgs.append(text),
        sms_sink=lambda text: smss.append(text),
    )
    assert len(mails) == 1, "Referenz: der Versand hat keine Mail an die Senke gegeben"
    assert len(tgs) == 1, "Referenz: der Versand hat kein Telegram an die Senke gegeben"
    if smss:
        sms = smss[0]
    else:
        # SMS-Tageslimit kann die Senke sperren — dann genau der Renderer-
        # Aufruf, den `_dispatch_compare_official_sms` macht (:1684).
        notices = build_compare_official_alert_notices(
            [loc.id for loc in LOCATIONS], {loc.id: loc.name for loc in LOCATIONS}, tagged,
        )
        sms, _ = render_official_alert_sms_with_allclears(
            notices, [], tz=resolve_location_tz(LOCATIONS[0]),
        )
    return {
        "subject": mails[0][0], "email_html": mails[0][1], "sms": sms,
        "telegram_bubbles": [tgs[0]],
    }


@pytest.mark.parametrize(
    "loc_ids", [["loc-bz"], ["loc-ibk", "loc-bz", "loc-mer"]], ids=["ein-ort", "alle-orte"],
)
def test_compare_official_alert_preview_equals_official_dispatch(env, loc_ids):  # noqa: F811
    """AC-19: GIVEN ein Ortsvergleich und eine amtliche Warnung
    WHEN die Alarm-Vorschau (Art amtlich) abgerufen wird
    THEN ist jeder Kanal identisch zur Nachricht, die der Versandpfad
    `send_multi_location_official_alert` fuer dieselbe Warnung erzeugt
    (Betreff, E-Mail-HTML, Telegram, SMS).

    RED: services.compare_alert_preview_service fehlt (ModuleNotFoundError)."""
    from services.compare_alert_preview_service import render_compare_alert_preview

    user_id = env
    preset = _seed(user_id)
    body = {"official": _official_dicts(loc_ids)}

    got, ref = _stable(
        lambda: _official_reference(preset, body, user_id),
        lambda: render_compare_alert_preview(PRESET_ID, user_id=user_id, body=body),
    )
    _assert_channels_equal(got, ref, f"amtlich {loc_ids}")


def test_compare_official_alert_preview_reports_unresolvable_location(env, caplog):  # noqa: F811
    """Adversary #2283 F001: GIVEN ein Ortsvergleich, der neben echten Orten
    eine Ort-ID fuehrt, die der Nutzer nicht (mehr) gespeichert hat
    WHEN die Alarm-Vorschau (Art amtlich) abgerufen wird
    THEN wird der nicht aufloesbare Ort per Warnung mit seiner ID gemeldet,
    und die Vorschau fuer die uebrigen Orte ist identisch zu der eines
    Vergleichs ohne diesen Ort (kein stilles Verwerfen, Ausgabe unveraendert)."""
    import logging

    from services.compare_alert_preview_service import render_compare_alert_preview

    user_id = env
    preset = _seed(user_id)
    ghost = "loc-2283-geloescht"
    with_ghost = {**preset, "id": PRESET_ID + "-geist",
                  "location_ids": [ghost, *preset["location_ids"]]}
    write_compare_briefings(get_data_dir(user_id), [preset, with_ghost])
    body = {"official": _official_dicts(["loc-ibk"])}
    logger_name = "services.compare_alert_preview_service"

    def ref():
        return render_compare_alert_preview(PRESET_ID, user_id=user_id, body=body)

    with caplog.at_level(logging.WARNING, logger=logger_name):
        got, clean = _stable(
            ref,
            lambda: render_compare_alert_preview(with_ghost["id"], user_id=user_id, body=body),
        )
    warnungen = [r for r in caplog.records
                 if r.name == logger_name and r.levelno >= logging.WARNING]
    assert any(ghost in r.getMessage() for r in warnungen), (
        f"nicht aufloesbarer Ort {ghost} wurde nicht gemeldet: "
        f"{[r.getMessage() for r in warnungen]}"
    )
    assert not any(lid in r.getMessage() for r in warnungen for lid in ALL_IDS), (
        "aufloesbare Orte duerfen nicht als verworfen gemeldet werden"
    )
    _assert_channels_equal(got, clean, "amtlich mit nicht aufloesbarem Ort")


def test_compare_official_alert_preview_contains_no_recommendation(env):  # noqa: F811
    """AC-19 (nur Daten): GIVEN eine amtliche Warnung ohne Verhaltenstext
    WHEN die Alarm-Vorschau (Art amtlich) abgerufen wird
    THEN enthaelt kein Kanal eine Handlungsempfehlung — nur Daten.

    RED: services.compare_alert_preview_service fehlt (ModuleNotFoundError)."""
    from services.compare_alert_preview_service import render_compare_alert_preview

    user_id = env
    _seed(user_id)
    got = render_compare_alert_preview(
        PRESET_ID, user_id=user_id, body={"official": _official_dicts(["loc-ibk"])},
    )
    for key in ("subject", "email_html", "telegram", "sms"):
        raw = got.get(key) or ""
        text = (_visible_text(raw) if key == "email_html" else raw).lower()
        assert text, f"Kanal '{key}' ist leer"
        hits = [p for p in EMPFEHLUNGS_PHRASEN if p in text]
        assert not hits, f"AC-19: Kanal '{key}' enthaelt Handlungsempfehlung {hits}: {text[:300]!r}"


def test_dispatch_references_are_buildable_for_all_three_kinds(env, wire):  # noqa: F811
    """Fixture-Probe: die drei Versand-Referenzen lassen sich fuer die
    Testeingaben bauen (Abweichung/Onset am Draht der lokalen Stubs), liefern
    nichtleere Kanaele, und die amtliche Versand-Nachricht selbst enthaelt
    keine Handlungsempfehlung."""
    user_id = env
    preset = _seed(user_id)
    refs = {
        "abweichung": _deviation_reference(
            preset, {"changes": _change_dicts(["loc-ibk", "loc-bz"])}, user_id, wire,
        ),
        "onset": _onset_reference(
            preset, {"onsets": _onset_dicts(["loc-ibk", "loc-bz"])}, user_id, wire,
        ),
        "amtlich": _official_reference(
            preset, {"official": _official_dicts(["loc-ibk"])}, user_id,
        ),
    }
    for kind, ref in refs.items():
        mail_key = "email_html" if kind == "amtlich" else "email_plain"
        for key in ("subject", mail_key, "sms"):
            assert ref[key], f"Referenz {kind}: Kanal '{key}' leer"
        assert ref["telegram_bubbles"] and all(ref["telegram_bubbles"]), (
            f"Referenz {kind}: Telegram leer"
        )
    assert len(refs["abweichung"]["telegram_bubbles"]) == 2, "Versand: eine Blase je Ort"
    amtlich = refs["amtlich"]
    for text in (amtlich["subject"], amtlich["sms"], amtlich["telegram_bubbles"][0],
                 _visible_text(amtlich["email_html"])):
        hits = [p for p in EMPFEHLUNGS_PHRASEN if p in text.lower()]
        assert not hits, f"Fixture: amtliche Versand-Nachricht enthaelt {hits}: {text[:200]!r}"
