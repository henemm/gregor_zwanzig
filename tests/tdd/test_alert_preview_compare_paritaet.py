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

Referenzen (= Versandweg, Zeilen gemessen auf origin/main @500734951):
- Abweichung (AC-17): `NotificationService.send_multi_location_deviation_alert`
  (notification_service.py:1040) → `to_multi_point_alert_message`
  → `_dispatch_alert_message` (:1807): Betreff/E-Mail aus der Bündel-
  Nachricht, SMS `render_sms(limit=140, location_positions=…)` mit den
  Positionen aus `CompareAlertService._location_positions`, Telegram je Ort
  `to_multi_point_alert_message([gruppe])` (:2019) bzw. Kurzstil = SMS-Text.
- Radar/Onset (AC-18): `send_multi_location_radar_alert` (:1104) →
  `to_multi_location_onset_alert_message(…, cooldown_display=…)` mit dem
  Cooldown-Text aus `compare_radar_alert._format_cooldown_display`.
- Amtlich (AC-19): der ECHTE Versand `send_multi_location_official_alert`
  (:1491) mit Aufzeichnungs-Senken (mail_sink/telegram_sink/sms_sink) —
  keine Nachbildung.

Zeit: Stand-Zeile und Onset-Uhrzeiten haengen an `now()`. Jeder Vergleich
laeuft Referenz → Vorschau → Referenz; nur wenn beide Referenzen gleich sind
(kein Minutenwechsel), wird verglichen — sonst Wiederholung.

RED-Grund: `services.compare_alert_preview_service` existiert nicht →
ModuleNotFoundError in jedem Test (Import bewusst IN der Testfunktion).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.loader import get_data_dir, save_location
from app.user import SavedLocation

from tests.helpers.compare_briefings import write_compare_briefings
from tests.integration.test_briefing_preview_bundle import env  # noqa: F401  (Fixture)

PRESET_ID = "cp-2283-alarm"
PRESET_NAME = "Alarm-Vergleich 2283"
COOLDOWN_MIN = 90

LOCATIONS = [
    SavedLocation(id="loc-ibk", name="Innsbruck", lat=47.27, lon=11.39, elevation_m=574),
    SavedLocation(id="loc-bz", name="Bozen", lat=46.50, lon=11.35, elevation_m=262),
    SavedLocation(id="loc-mer", name="Meran", lat=46.67, lon=11.16, elevation_m=325),
]

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
# AC-17 — Abweichung (to_multi_point_alert_message)
# ---------------------------------------------------------------------------


def _change_dicts(loc_ids: list[str]) -> list[dict]:
    out = []
    for i, loc_id in enumerate(loc_ids):
        out.append({
            "location_id": loc_id, "metric": "gust_max_kmh",
            "old_value": 25.0 + i, "new_value": 72.0 + i, "delta": 47.0,
            "threshold": 60.0, "severity": "major", "direction": "increase",
        })
    return out


def _deviation_reference(preset: dict, body: dict) -> dict:
    """Nachbau-frei: genau die Aufrufe des Versandwegs (s. Modul-Docstring)."""
    from app.models import ChangeSeverity, WeatherChange
    from output.renderers.alert.project import to_multi_point_alert_message
    from output.renderers.alert.render import (
        render_email, render_sms, render_subject, render_telegram,
    )
    from services.compare_alert import CompareAlertService
    from services.compare_alert_channels import effective_compare_telegram_style
    from utils.timezone import local_fmt, tz_for_coords

    by_loc: dict[str, list] = {}
    for c in body["changes"]:
        by_loc.setdefault(c["location_id"], []).append(WeatherChange(
            metric=c["metric"], old_value=c["old_value"], new_value=c["new_value"],
            delta=c["delta"], threshold=c["threshold"],
            severity=ChangeSeverity(c["severity"]), direction=c["direction"],
        ))
    ordered = [lid for lid in preset["location_ids"] if lid in by_loc]
    groups = [(_loc(lid).name, by_loc[lid], _loc(lid)) for lid in ordered]
    first = _loc(ordered[0])
    tz = tz_for_coords(first.lat, first.lon)
    stand_at = local_fmt(datetime.now(timezone.utc), tz)
    msg = to_multi_point_alert_message(groups, tz=tz, stand_at=stand_at)
    html, plain = render_email(msg)
    positions = CompareAlertService._location_positions(
        preset["location_ids"], {loc.id: loc for loc in LOCATIONS},
    )
    sms = render_sms(msg, limit=140, location_positions=positions)
    if effective_compare_telegram_style(preset) == "kurzform":
        bubbles = [sms]
    else:
        bubbles = [
            render_telegram(to_multi_point_alert_message([g], tz=tz, stand_at=stand_at))
            for g in groups
        ]
    return {
        "subject": render_subject(msg), "email_html": html, "email_plain": plain,
        "sms": sms, "telegram_bubbles": bubbles,
    }


@pytest.mark.parametrize(
    "loc_ids,telegram_style",
    [
        (["loc-bz"], None),
        (["loc-ibk", "loc-mer"], None),
        (["loc-ibk", "loc-bz", "loc-mer"], None),
        (["loc-ibk", "loc-mer"], "kurzform"),
    ],
    ids=["ein-ort", "zwei-orte", "drei-orte", "zwei-orte-kurzform"],
)
def test_compare_deviation_alert_preview_equals_dispatch_projection(env, loc_ids, telegram_style):  # noqa: F811
    """AC-17: GIVEN ein Ortsvergleich mit Abweichung an einem/mehreren Orten
    WHEN die Alarm-Vorschau (Art Abweichung) abgerufen wird
    THEN ist jeder Kanal identisch zur Nachricht, die der Versand ueber
    `to_multi_point_alert_message` fuer dieselbe Eingabe erzeugt — inklusive
    Ortsnummern in der SMS und einer Telegram-Blase je Ort (Kurzstil: SMS-Text).

    RED: services.compare_alert_preview_service fehlt (ModuleNotFoundError)."""
    from services.compare_alert_preview_service import render_compare_alert_preview

    user_id = env
    preset = _seed(user_id, telegram_style=telegram_style)
    body = {"changes": _change_dicts(loc_ids)}

    got, ref = _stable(
        lambda: _deviation_reference(preset, body),
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


def _onset_reference(preset: dict, body: dict) -> dict:
    from output.renderers.alert.project import to_multi_location_onset_alert_message
    from output.renderers.alert.render import (
        render_email, render_sms, render_subject, render_telegram,
    )
    from services.compare_alert_channels import effective_compare_telegram_style
    from services.compare_radar_alert import _format_cooldown_display
    from services.radar_service import NowcastResult
    from utils.timezone import local_fmt, resolve_location_tz

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
    tz = resolve_location_tz(entities[0][1])
    stand_at = local_fmt(datetime.now(timezone.utc), tz)
    msg = to_multi_location_onset_alert_message(
        entities, tz=tz, stand_at=stand_at,
        cooldown_display=_format_cooldown_display(COOLDOWN_MIN),
    )
    html, plain = render_email(msg)
    sms = render_sms(msg, limit=140, location_positions=None)
    bubbles = [sms] if effective_compare_telegram_style(preset) == "kurzform" else [
        render_telegram(msg)
    ]
    return {
        "subject": render_subject(msg), "email_html": html, "email_plain": plain,
        "sms": sms, "telegram_bubbles": bubbles,
    }


@pytest.mark.parametrize(
    "loc_ids", [["loc-ibk"], ["loc-ibk", "loc-bz", "loc-mer"]], ids=["ein-ort", "drei-orte"],
)
def test_compare_onset_alert_preview_equals_dispatch_projection(env, loc_ids):  # noqa: F811
    """AC-18: GIVEN ein Ortsvergleich und ein Regen-/Radar-Ereignis an einem
    oder mehreren Orten
    WHEN die Alarm-Vorschau (Art Radar/Onset) abgerufen wird
    THEN ist jeder Kanal identisch zur Nachricht aus
    `to_multi_location_onset_alert_message` (mit dem Cooldown-Hinweis des
    Presets, wie im Versand).

    RED: services.compare_alert_preview_service fehlt (ModuleNotFoundError)."""
    from services.compare_alert_preview_service import render_compare_alert_preview

    user_id = env
    preset = _seed(user_id)
    body = {"onsets": _onset_dicts(loc_ids)}

    got, ref = _stable(
        lambda: _onset_reference(preset, body),
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


def test_dispatch_references_are_buildable_for_all_three_kinds(env):  # noqa: F811
    """Fixture-Probe (heute GRUEN): die drei Versand-Referenzen lassen sich
    fuer die Testeingaben bauen, liefern nichtleere Kanaele, und die amtliche
    Versand-Nachricht selbst enthaelt keine Handlungsempfehlung — die roten
    Tests oben scheitern also allein am fehlenden Vorschau-Modul."""
    user_id = env
    preset = _seed(user_id)
    refs = {
        "abweichung": _deviation_reference(
            preset, {"changes": _change_dicts(["loc-ibk", "loc-bz"])},
        ),
        "onset": _onset_reference(preset, {"onsets": _onset_dicts(["loc-ibk", "loc-bz"])}),
        "amtlich": _official_reference(
            preset, {"official": _official_dicts(["loc-ibk"])}, user_id,
        ),
    }
    for kind, ref in refs.items():
        for key in ("subject", "email_html", "sms"):
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
