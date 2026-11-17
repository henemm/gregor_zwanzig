"""TDD RED — Issue #2986 (Paar P05 aus #1986): EIN Baustein fuer Nachrichtenbau
und Kanaltexte, den Alarm-Vorschau (Ortsvergleich) und Versand gemeinsam nutzen.

Spec: docs/specs/modules/alert_channel_texts.md (AC-2, AC-3, AC-4, AC-6, AC-8;
AC-1/AC-5 bewacht der Bestand, AC-7 die Ratsche in test_profil_ampel_kette.py).

Vertrag des neuen Moduls ``services.alert_channel_texts`` (von diesen Tests
festgelegt; weitere keyword-Parameter MIT Default sind erlaubt):

    SMS_LIMIT = 140   # die EINZIGE Stelle des Alarm-SMS-Limits

    build_deviation_message(groups, *, preset, reference_at=None,
                            anchor_points=None) -> (AlertMessage, ZoneInfo)
        groups = [(ortsname, changes, punkt)]; tz = tz_for_coords(punkt von
        groups[0]); stand_at = local_fmt(jetzt, tz); Ampel = resolve_ampel(preset)

    build_onset_message(entities, *, preset, cooldown_display=None, tz=None,
                        stand_at=None) -> (AlertMessage, ZoneInfo)
        entities = [(ortsname, ort, NowcastResult)];
        tz = tz or resolve_location_tz(erster ort) or UTC

    render_channel_texts(msg, *, lang, location_positions=None) -> AlertChannelTexts
        AlertChannelTexts(subject, html, plain, telegram_body, sms_body);
        sms_body mit Limit SMS_LIMIT und Ortsnummern

    plan_telegram(msg, texts, *, style, groups=None, tz, anchor_points=None,
                  lang) -> TelegramPlan(fan_out: bool, bubbles: list[TelegramBubble])
        TelegramBubble(label, parse_mode, render: () -> str); Kurzform hat
        VORRANG vor der Auffaecherung je Ort (#1467 K-6); render() je Blase
        lazy (Fehlerhaertung je Ort bleibt im Dispatcher moeglich).

    official_header_texts(dto_notices, ac_notices, *, prefix, tz, lang)
        -> OfficialHeaderTexts(source_label, subject, html, plain, sms)
    official_telegram_text(dto_notices, ac_notices, *, style, prefix,
                           source_label, tz, lang) -> str

Mutationsgegenprobe (AC-3): die "Pin"-Tests unten messen Vorschau UND Versand
gegen eine unabhaengige Referenz aus den Renderern mit festen Konstanten
(Limit 140, Ortsnummern, Kurzform = EINE Blase, Betreff). Eine Verfaelschung
im geteilten Baustein trifft beide Seiten gleich — der Paritaetstest allein
saehe sie nicht; diese Pins sehen sie je Seite. Die Pins sind heute schon
gruen (sie belegen das Verhalten VOR dem Umbau, AC-1) und muessen es bleiben.

Kein Mock: echte Renderer, echte Dateien, Versand am Draht ueber lokale
Telegram-/seven.io-Stubs (Infrastruktur aus test_alert_preview_compare_paritaet).

RED-Grund: ``services.alert_channel_texts`` existiert nicht
(ModuleNotFoundError), Vorschau und Dispatcher rufen den Baustein noch nicht
(AST-Strukturtests).
"""
from __future__ import annotations

import ast
import http.server
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

import output.channels.telegram as tg_module
from app.user import SavedLocation

from tests.helpers.vorschau_umgebung import env  # noqa: F401  (Fixture)
from tests.tdd.test_alert_preview_compare_paritaet import (  # noqa: F401
    LOCATIONS, PRESET_ID, _deviation_reference, _free_port,
    _loc, _onset_dicts, _onset_reference, _seed, _stable, wire,
)

_SRC = Path(__file__).resolve().parents[2] / "src" / "services"
_VORSCHAU = _SRC / "compare_alert_preview_service.py"
_VERSAND = _SRC / "notification_service.py"
_BAUSTEIN = _SRC / "alert_channel_texts.py"


# ---------------------------------------------------------------------------
# AST-Hilfen (Aufrufgraph, kein Textinhalt)
# ---------------------------------------------------------------------------


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _func(tree: ast.AST, name: str) -> ast.AST:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError(f"Funktion {name} nicht gefunden")


def _call_name(node: ast.Call) -> str | None:
    fn = node.func
    if isinstance(fn, ast.Name):
        return fn.id
    if isinstance(fn, ast.Attribute):
        return fn.attr
    return None


def _calls(node: ast.AST) -> list[ast.Call]:
    return [n for n in ast.walk(node) if isinstance(n, ast.Call)]


def _called(node: ast.AST) -> set[str]:
    return {_call_name(c) for c in _calls(node)} - {None}


def _int_constants(node: ast.AST, value: int) -> list[ast.Constant]:
    return [
        n for n in ast.walk(node)
        if isinstance(n, ast.Constant) and type(n.value) is int and n.value == value
    ]


def _names(node: ast.AST) -> set[str]:
    out = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Name):
            out.add(n.id)
        elif isinstance(n, ast.Attribute):
            out.add(n.attr)
        elif isinstance(n, ast.alias):
            out.add(n.asname or n.name.rsplit(".", 1)[-1])
    return out


# Renderer/Projektionen, die NUR noch der Baustein aufrufen darf.
_KANAL_BAU = {
    "render_sms", "render_telegram", "render_email", "render_subject",
    "render_alert_sms", "render_alert_telegram", "render_alert_email",
    "render_alert_subject",
    "to_multi_point_alert_message", "to_multi_location_onset_alert_message",
}
_AMTLICH_BAU = {
    "render_official_alert_sms_with_allclears", "_official_subject",
    "_official_mail_bodies", "_official_telegram_rich",
    "_official_allclear_source_label",
}


# ---------------------------------------------------------------------------
# AC-2 — Struktur: Kanalbau liegt nur im Baustein
# ---------------------------------------------------------------------------


def test_baustein_modul_existiert_und_fuehrt_das_sms_limit():
    """AC-2: GIVEN der geteilte Baustein WHEN er importiert wird THEN fuehrt
    er das Alarm-SMS-Limit 140 als einzige Stelle (genau ein Literal 140)."""
    from services import alert_channel_texts as act

    assert act.SMS_LIMIT == 140
    assert len(_int_constants(_tree(_BAUSTEIN), 140)) == 1, (
        "das Literal 140 darf im Baustein genau einmal stehen (SMS_LIMIT)"
    )
    for name in (
        "build_deviation_message", "build_onset_message", "render_channel_texts",
        "plan_telegram", "official_header_texts", "official_telegram_text",
    ):
        assert callable(getattr(act, name, None)), f"Baustein ohne {name}"


def test_vorschau_baut_keinen_kanal_selbst():
    """AC-2: GIVEN das Vorschau-Modul WHEN sein Aufrufgraph geprueft wird THEN
    ruft es weder Renderer noch Projektion noch amtliche Komposition direkt
    auf, fuehrt kein eigenes SMS-Limit und keinen Versandweg."""
    tree = _tree(_VORSCHAU)
    direkt = _called(tree) & (_KANAL_BAU | _AMTLICH_BAU)
    assert not direkt, f"Vorschau ruft Kanalbau direkt: {sorted(direkt)}"
    assert "_SMS_LIMIT" not in _names(tree), "Vorschau fuehrt noch _SMS_LIMIT"
    assert not _int_constants(tree, 140), "Vorschau fuehrt noch ein Literal 140"
    # AC-6 strukturell: kein Versandweg, keine Kontingent-Reservierung.
    verboten = _names(tree) & {
        "NotificationService", "check_and_reserve", "reserve_daily_slot",
        "_dispatch_alert_message",
    }
    assert not verboten, f"Vorschau beruehrt den Versandweg: {sorted(verboten)}"


@pytest.mark.parametrize(
    "funktion,pflicht",
    [
        ("_deviation", {"build_deviation_message", "render_channel_texts", "plan_telegram"}),
        ("_onset", {"build_onset_message", "render_channel_texts", "plan_telegram"}),
        ("_official", {"official_header_texts", "official_telegram_text"}),
    ],
)
def test_vorschau_ruft_den_geteilten_baustein(funktion, pflicht):
    """AC-2: die Vorschau-Wrapper (Namen bleiben, Tests rufen sie direkt)
    holen Nachricht und Kanaltexte aus dem Baustein."""
    fehlt = pflicht - _called(_func(_tree(_VORSCHAU), funktion))
    assert not fehlt, f"Vorschau {funktion} ruft nicht {sorted(fehlt)}"


@pytest.mark.parametrize(
    "funktion,pflicht,verboten",
    [
        ("_dispatch_alert_message", {"render_channel_texts", "plan_telegram"},
         _KANAL_BAU),
        ("send_multi_location_deviation_alert", {"build_deviation_message"},
         {"to_multi_point_alert_message", "resolve_ampel", "tz_for_coords"}),
        ("send_multi_location_radar_alert", {"build_onset_message"},
         {"to_multi_location_onset_alert_message", "resolve_ampel"}),
        ("send_multi_location_official_alert", {"official_header_texts"},
         _AMTLICH_BAU),
        ("_dispatch_compare_official_telegram", {"official_telegram_text"},
         _AMTLICH_BAU),
    ],
)
def test_versand_ruft_den_geteilten_baustein(funktion, pflicht, verboten):
    """AC-2: GIVEN der Versandpfad WHEN sein Aufrufgraph geprueft wird THEN
    ruft er den Baustein und baut Nachricht/Kanaltexte nicht selbst."""
    node = _func(_tree(_VERSAND), funktion)
    called = _called(node)
    assert not (pflicht - called), f"{funktion} ruft nicht {sorted(pflicht - called)}"
    assert not (called & verboten), f"{funktion} baut selbst: {sorted(called & verboten)}"
    assert not _int_constants(node, 140), f"{funktion} fuehrt noch ein Literal 140"


def test_reference_at_bleibt_nur_im_versand():
    """AC-8: die Vorschau setzt ``reference_at`` nicht, der Versand reicht es
    an ``build_deviation_message`` weiter."""
    for call in _calls(_func(_tree(_VORSCHAU), "_deviation")):
        if _call_name(call) == "build_deviation_message":
            assert "reference_at" not in {k.arg for k in call.keywords}
    versand = [
        c for c in _calls(_func(_tree(_VERSAND), "send_multi_location_deviation_alert"))
        if _call_name(c) == "build_deviation_message"
    ]
    assert versand and all("reference_at" in {k.arg for k in c.keywords} for c in versand)


# ---------------------------------------------------------------------------
# Baustein direkt: Telegram-Plan und Nachrichtenbau
# ---------------------------------------------------------------------------


def _weather_changes(dicts: list[dict]) -> dict[str, list]:
    from app.models import ChangeSeverity, WeatherChange

    by_loc: dict[str, list] = {}
    for c in dicts:
        by_loc.setdefault(c["location_id"], []).append(WeatherChange(
            metric=c["metric"], old_value=c["old_value"], new_value=c["new_value"],
            delta=c["delta"], threshold=c["threshold"],
            severity=ChangeSeverity(c["severity"]), direction=c["direction"],
        ))
    return by_loc


_METRICS = [  # (metric, alt, neu, schwelle) wie im Paritaetstest
    ("gust_max_kmh", 25.0, 72.0, 60.0), ("wind_max_kmh", 15.0, 55.0, 40.0),
    ("precip_sum_mm", 1.0, 30.0, 20.0), ("temp_max_c", 20.0, 33.0, 30.0),
]


def _changes(loc_ids: list[str], n_metrics: int = 1, offset: float = 0.0) -> list[dict]:
    out = []
    for i, loc_id in enumerate(loc_ids):
        for metric, old, new, threshold in _METRICS[:n_metrics]:
            out.append({
                "location_id": loc_id, "metric": metric,
                "old_value": old + i, "new_value": new + i + offset,
                "delta": new + offset - old, "threshold": threshold,
                "severity": "major", "direction": "increase",
            })
    return out


# 7 Orte x 3 Metriken, Versatz 28: die SMS mit Ortsnummern trifft GENAU 140
# Zeichen (vermessen) -- bei Limit 139 faellt ein Token weg. Nur so ist eine
# Verfaelschung des Limits beobachtbar.
_LIMIT_IDS = [loc.id for loc in LOCATIONS[:7]]
_LIMIT_BODY = {"changes": _changes(_LIMIT_IDS, n_metrics=3, offset=28.0)}


def _groups(body: dict) -> list[tuple]:
    by_loc = _weather_changes(body["changes"])
    ordered = [loc.id for loc in LOCATIONS if loc.id in by_loc]
    return [(_loc(lid).name, by_loc[lid], _loc(lid)) for lid in ordered]


def _positions() -> dict[str, int]:
    return {loc.name: i + 1 for i, loc in enumerate(LOCATIONS)}


def _referenz(preset: dict, body: dict, *, style: str | None) -> dict:
    """Unabhaengige Referenz aus den Renderern mit festen Konstanten (Stand
    vor dem Umbau): Limit 140, Ortsnummern, Kurzform = EINE Blase = SMS,
    sonst eine Blase je Ort."""
    from app.ampel import resolve_ampel
    from output.renderers.alert.project import to_multi_point_alert_message
    from output.renderers.alert.render import render_sms, render_subject, render_telegram
    from utils.timezone import local_fmt, tz_for_coords

    groups = _groups(body)
    first = groups[0][2]
    tz = tz_for_coords(first.lat, first.lon)
    stand_at = local_fmt(datetime.now(timezone.utc), tz)
    ampel = resolve_ampel(preset)
    msg = to_multi_point_alert_message(groups, tz=tz, stand_at=stand_at, ampel=ampel)
    sms = render_sms(msg, limit=140, location_positions=_positions())
    if style == "kurzform":
        bubbles = [sms]
    else:
        bubbles = [
            render_telegram(to_multi_point_alert_message(
                [g], tz=tz, stand_at=stand_at, ampel=ampel,
            ), lang="de")
            for g in groups
        ]
    return {"subject": render_subject(msg, lang="de"), "sms": sms, "telegram_bubbles": bubbles}


def test_plan_telegram_kurzform_hat_vorrang_vor_auffaecherung(env):  # noqa: F811
    """AC-2/AC-3 (#1467 K-6): GIVEN Gruppen je Ort und Stil Kurzform WHEN der
    Telegram-Plan gebaut wird THEN gibt es GENAU EINE Blase ohne parse_mode,
    deren Text der SMS-Text ist; ohne Kurzform eine HTML-Blase je Ort."""
    from services.alert_channel_texts import (
        build_deviation_message, plan_telegram, render_channel_texts,
    )

    preset = _seed(env)
    groups = _groups({"changes": _changes(["loc-ibk", "loc-mer"])})
    msg, tz = build_deviation_message(groups, preset=preset)
    texts = render_channel_texts(msg, lang="de", location_positions=_positions())

    kurz = plan_telegram(msg, texts, style="kurzform", groups=groups, tz=tz, lang="de")
    assert kurz.fan_out is False
    assert len(kurz.bubbles) == 1
    assert kurz.bubbles[0].parse_mode is None
    assert kurz.bubbles[0].render() == texts.sms_body

    reich = plan_telegram(msg, texts, style="rich", groups=groups, tz=tz, lang="de")
    assert reich.fan_out is True
    assert [b.label for b in reich.bubbles] == ["Innsbruck", "Meran"]
    assert all(b.parse_mode == "HTML" for b in reich.bubbles)

    eine = plan_telegram(msg, texts, style="rich", groups=None, tz=tz, lang="de")
    assert eine.fan_out is False
    assert [b.render() for b in eine.bubbles] == [texts.telegram_body]
    assert eine.bubbles[0].parse_mode == "HTML"


def test_plan_telegram_rendert_je_blase_einzeln(env):  # noqa: F811
    """AC-4: GIVEN ein Ort mit echter kaputter Eingabe (Aenderung ``None``)
    WHEN der Telegram-Plan gebaut wird THEN scheitert erst das Rendern GENAU
    dieser Blase; Plan-Bau und die uebrigen Blasen bleiben heil (sonst kann
    der Dispatcher die uebrigen Orte nicht mehr zustellen, #1467 F002)."""
    from services.alert_channel_texts import (
        build_deviation_message, plan_telegram, render_channel_texts,
    )

    preset = _seed(env)
    gut = _groups({"changes": _changes(["loc-ibk", "loc-mer"])})
    kaputt = ("Kaputt", [None], _loc("loc-bz"))
    msg, tz = build_deviation_message(gut, preset=preset)
    texts = render_channel_texts(msg, lang="de")
    plan = plan_telegram(
        msg, texts, style="rich", groups=[gut[0], kaputt, gut[1]], tz=tz, lang="de",
    )
    assert len(plan.bubbles) == 3
    assert "Innsbruck" in plan.bubbles[0].render()
    with pytest.raises(Exception):
        plan.bubbles[1].render()
    assert "Meran" in plan.bubbles[2].render()


def test_render_channel_texts_haelt_limit_und_ortsnummern(env):  # noqa: F811
    """AC-3: GIVEN eine Nachricht, deren SMS genau an der Grenze liegt WHEN
    die Kanaltexte gerendert werden THEN ist die SMS identisch zur Referenz
    mit Limit 140 und Ortsnummern; Betreff identisch zur Referenz."""
    from output.renderers.alert.render import render_email, render_sms, render_subject, render_telegram
    from services.alert_channel_texts import build_deviation_message, render_channel_texts

    preset = _seed(env)
    msg, _tz = build_deviation_message(_groups(_LIMIT_BODY), preset=preset)
    texts = render_channel_texts(msg, lang="de", location_positions=_positions())
    assert len(texts.sms_body) == 140
    assert texts.sms_body == render_sms(msg, limit=140, location_positions=_positions())
    assert texts.subject == render_subject(msg, lang="de")
    assert (texts.html, texts.plain) == render_email(msg, lang="de")
    assert texts.telegram_body == render_telegram(msg, lang="de")


def test_build_deviation_message_tz_aus_koordinaten_und_reference_at(env):  # noqa: F811
    """AC-8: GIVEN ein Ort mit gespeicherter, abweichender Orts-Zeitzone WHEN
    die Abweichungs-Nachricht gebaut wird THEN gilt wie heute die Zeitzone
    aus den Koordinaten (``tz_for_coords``), nicht das gespeicherte Feld;
    ``reference_at`` wird durchgereicht."""
    from services.alert_channel_texts import build_deviation_message
    from utils.timezone import local_fmt, tz_for_coords

    preset = _seed(env)
    fremd = SavedLocation(
        id="loc-ibk", name="Innsbruck", lat=47.27, lon=11.39, elevation_m=574,
        timezone="America/New_York",
    )
    changes = _weather_changes(_changes(["loc-ibk"]))["loc-ibk"]
    erwartet = tz_for_coords(47.27, 11.39)

    def bau():
        return build_deviation_message(
            [("Innsbruck", changes, fremd)], preset=preset, reference_at="gestern 18:03",
        )

    (msg, tz), _ = _stable(lambda: local_fmt(datetime.now(timezone.utc), erwartet), bau)
    assert str(tz) == str(erwartet) != "America/New_York"
    assert msg.stand_at == local_fmt(datetime.now(timezone.utc), erwartet)
    assert msg.reference_at == "gestern 18:03"


def test_build_onset_message_tz_aus_ort_mit_override(env):  # noqa: F811
    """AC-8: Radar bleibt bei ``resolve_location_tz`` (gespeichertes Feld vor
    Koordinaten); ein ``tz``-Override des Versands gewinnt."""
    from services.alert_channel_texts import build_onset_message
    from services.radar_service import NowcastResult

    preset = _seed(env)
    fremd = SavedLocation(
        id="loc-ibk", name="Innsbruck", lat=47.27, lon=11.39, elevation_m=574,
        timezone="America/New_York",
    )
    nc = NowcastResult(onset_minutes=20, intensity_label="mäßiger Regen",
                       source="radar", is_convective=False)
    _msg, tz = build_onset_message([("Innsbruck", fremd, nc)], preset=preset)
    assert str(tz) == "America/New_York"
    _msg, tz = build_onset_message(
        [("Innsbruck", fremd, nc)], preset=preset, tz=ZoneInfo("Europe/Paris"),
    )
    assert str(tz) == "Europe/Paris"


def test_official_telegram_text_kurzform_ist_sms(env):  # noqa: F811
    """AC-2: amtlich, Kurzform-Telegram = amtlicher SMS-Text (wie heute);
    reich = eigene Warnvorlage mit Vergleichsname."""
    from datetime import timedelta

    from output.renderers.alert.official_alerts import build_compare_official_alert_notices
    from services.alert_channel_texts import official_header_texts, official_telegram_text
    from services.official_alerts.models import OfficialAlert

    start = (datetime.now(timezone.utc) + timedelta(hours=3)).replace(
        minute=0, second=0, microsecond=0)
    alert = OfficialAlert(
        source="geosphere_warn", hazard="thunderstorm", level=3, label="Gewitter",
        valid_from=start, valid_to=start + timedelta(hours=6), region_label="Innsbruck-Land",
    )
    notices = build_compare_official_alert_notices(
        ["loc-ibk"], {"loc-ibk": "Innsbruck"}, [(alert, ["loc-ibk"])], lang="de",
    )
    tz = ZoneInfo("Europe/Vienna")
    head = official_header_texts(notices, [], prefix="Vergleich X", tz=tz, lang="de")
    for feld in ("source_label", "subject", "html", "plain", "sms"):
        assert getattr(head, feld), f"amtlicher Kopf ohne {feld}"
    kurz = official_telegram_text(
        notices, [], style="kurzform", prefix="Vergleich X",
        source_label=head.source_label, tz=tz, lang="de",
    )
    assert kurz == head.sms
    reich = official_telegram_text(
        notices, [], style="rich", prefix="Vergleich X",
        source_label=head.source_label, tz=tz, lang="de",
    )
    assert reich != head.sms and "Vergleich X" in reich


# ---------------------------------------------------------------------------
# AC-3 — Pins je Seite (Vorschau / Versand am Draht) gegen feste Referenz
# ---------------------------------------------------------------------------


def _assert_pin(got: dict, ref: dict, label: str) -> None:
    for key in ("subject", "sms", "telegram_bubbles"):
        assert got[key] == ref[key], (
            f"{label}: '{key}' weicht von der Referenz ab.\n"
            f"Ist:      {got[key]!r}\nReferenz: {ref[key]!r}"
        )


@pytest.mark.parametrize(
    "body,style",
    [
        (_LIMIT_BODY, None),
        ({"changes": _changes(["loc-ibk", "loc-mer"])}, "kurzform"),
        ({"changes": _changes(["loc-ibk", "loc-bz", "loc-mer"])}, None),
    ],
    ids=["sms-an-der-grenze", "zwei-orte-kurzform", "drei-orte-je-ort"],
)
def test_pin_vorschau_gegen_referenz(env, body, style):  # noqa: F811
    """AC-3 (Vorschau-Seite): GIVEN ein Ortsvergleich-Abweichungsalarm WHEN
    die Vorschau gerendert wird THEN stimmen Betreff, SMS (Limit 140,
    Ortsnummern) und Telegram-Blasen (Kurzform = eine Blase) mit der festen
    Referenz ueberein."""
    from services.compare_alert_preview_service import render_compare_alert_preview

    preset = _seed(env, telegram_style=style)
    got, ref = _stable(
        lambda: _referenz(preset, body, style=style),
        lambda: render_compare_alert_preview(PRESET_ID, user_id=env, body=body),
    )
    _assert_pin(got, ref, f"Vorschau {style or 'rich'}")
    if body is _LIMIT_BODY:
        assert len(got["sms"]) == 140


@pytest.mark.parametrize(
    "body,style",
    [
        (_LIMIT_BODY, None),
        ({"changes": _changes(["loc-ibk", "loc-mer"])}, "kurzform"),
        ({"changes": _changes(["loc-ibk", "loc-bz", "loc-mer"])}, None),
    ],
    ids=["sms-an-der-grenze", "zwei-orte-kurzform", "drei-orte-je-ort"],
)
def test_pin_versand_am_draht_gegen_referenz(env, wire, body, style):  # noqa: F811
    """AC-3 (Versand-Seite): GIVEN derselbe Alarm WHEN er echt versendet wird
    (lokale Stubs) THEN kommen Betreff, SMS und Telegram-Blasen exakt wie in
    der festen Referenz am Draht an."""
    preset = _seed(env, telegram_style=style)
    got, ref = _stable(
        lambda: _referenz(preset, body, style=style),
        lambda: _deviation_reference(preset, body, env, wire),
    )
    _assert_pin(got, ref, f"Versand {style or 'rich'}")
    if body is _LIMIT_BODY:
        assert len(got["sms"]) == 140


# ---------------------------------------------------------------------------
# AC-4 — Teil- und Gesamtausfall der Telegram-Auffaecherung am Draht
# ---------------------------------------------------------------------------


class _FailingTelegram:
    """Lokaler Bot-API-Stub; Aufrufnummern in ``fail_at`` antworten HTTP 500."""

    def __init__(self, fail_at) -> None:
        self.ok_texts: list[str] = []
        ok_texts = self.ok_texts
        state = {"n": 0}

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                state["n"] += 1
                if fail_at(state["n"]):
                    self.send_response(500)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"ok": false, "description": "stub 500"}')
                    return
                try:
                    ok_texts.append(json.loads(raw.decode()).get("text", ""))
                except ValueError:
                    ok_texts.append("")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"ok": true, "result": {"message_id": 7}}')

            def log_message(self, *args):  # noqa: D401
                pass

        self.port = _free_port()
        self._server = http.server.HTTPServer(("127.0.0.1", self.port), Handler)
        threading.Thread(target=self._server.serve_forever, daemon=True).start()

    def stop(self) -> None:
        self._server.shutdown()


def _send_three(env_user: str, monkeypatch, fail_at):
    from app.config import Settings
    from services.notification_service import NotificationService

    from tests.helpers.telegram_empfaenger import profil_chat

    stub = _FailingTelegram(fail_at)
    monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", f"http://127.0.0.1:{stub.port}")
    profil_chat(env_user, "99999")
    settings = Settings().model_copy(update={
        "telegram_bot_token": "test-token-2986", "telegram_chat_id": "99999",
        "telegram_test_chat_id": "99999", "telegram_rate_limit_max_per_window": 10_000,
    })
    preset = _seed(env_user)
    by_loc = _weather_changes(_changes(["loc-ibk", "loc-bz", "loc-mer"]))
    entities = [(_loc(lid).name, [_loc(lid)], by_loc[lid]) for lid in ("loc-ibk", "loc-bz", "loc-mer")]
    try:
        result = NotificationService(settings, env_user).send_multi_location_deviation_alert(
            entities, {"telegram"}, preset=preset,
        )
    finally:
        stub.stop()
    return result, stub.ok_texts


def test_teilausfall_telegram_uebrige_blasen_und_hinweis(env, monkeypatch):  # noqa: F811
    """AC-4: GIVEN die zweite Blase scheitert am Draht WHEN der Versand laeuft
    THEN kommen Ort 1 und 3 an, ein Teilzustellungs-Hinweis folgt,
    ``telegram_fully_sent`` ist False und Telegram gilt als zugestellt."""
    result, texts = _send_three(env, monkeypatch, lambda n: n == 2)
    assert any("Innsbruck" in t for t in texts) and any("Meran" in t for t in texts)
    assert not any("Bozen" in t for t in texts[:2])
    assert len(texts) == 3, f"zwei Blasen + Hinweis erwartet: {texts!r}"
    assert result.telegram_fully_sent is False
    assert "telegram" in result.sent_channels


def test_gesamtausfall_telegram_endet_mit_fehler(env, monkeypatch):  # noqa: F811
    """AC-4: GIVEN alle Blasen scheitern am Draht WHEN der Versand laeuft THEN
    ist Telegram ein Transportfehler (nicht zugestellt, ``failed_channels``)."""
    result, _texts = _send_three(env, monkeypatch, lambda n: True)
    assert "telegram" not in result.sent_channels
    assert "telegram" in result.failed_channels
    assert result.telegram_fully_sent is False


# ---------------------------------------------------------------------------
# AC-6 — Vorschau sendet nichts und reserviert kein SMS-Kontingent
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("art", ["changes", "onsets"])
def test_vorschau_sendet_nichts_und_reserviert_kein_kontingent(env, wire, art):  # noqa: F811
    """AC-6: GIVEN ein sendebereiter Nutzer (Telegram, SMS, Premium-Tarif)
    WHEN die Alarm-Vorschau aufgerufen wird THEN bleibt der SMS-Tageszaehler
    unveraendert und an den lokalen Stubs kommt nichts an."""
    from services import sms_daily_limit
    from services.compare_alert_preview_service import render_compare_alert_preview

    wire.settings(env)  # Profil-Chat, Tarif, SMS-Nummer wie beim Versand
    _seed(env)
    body = (
        {"changes": _changes(["loc-ibk", "loc-mer"])} if art == "changes"
        else {"onsets": _onset_dicts(["loc-ibk", "loc-mer"])}
    )
    now = datetime.now(timezone.utc)
    vorher = sms_daily_limit.get_daily_usage(env, now)
    tg0, sms0 = len(wire.telegram.received), len(wire.sms.received)
    got = render_compare_alert_preview(PRESET_ID, user_id=env, body=body)
    assert got["sms"] and got["telegram_bubbles"]
    assert sms_daily_limit.get_daily_usage(env, now) == vorher
    assert len(wire.telegram.received) == tg0 and len(wire.sms.received) == sms0


def test_onset_versand_am_draht_ist_unveraendert(env, wire):  # noqa: F811
    """AC-1/AC-5 (Schutznetz Radar): der Onset-Versand am Draht liefert eine
    Blase und eine SMS mit Ortsnummern wie die Vorschau."""
    from services.compare_alert_preview_service import render_compare_alert_preview

    preset = _seed(env)
    body = {"onsets": _onset_dicts(["loc-ibk", "loc-mer"])}
    got, ref = _stable(
        lambda: _onset_reference(preset, body, env, wire),
        lambda: render_compare_alert_preview(PRESET_ID, user_id=env, body=body),
    )
    assert len(ref["telegram_bubbles"]) == 1
    assert got["sms"] == ref["sms"] and got["telegram_bubbles"] == ref["telegram_bubbles"]
    assert "1:" in ref["sms"] and "3:" in ref["sms"], "Ortsnummern fehlen in der SMS"

