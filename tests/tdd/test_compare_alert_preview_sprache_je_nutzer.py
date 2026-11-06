"""TDD RED — Issue #2721 (Epic #2644, ADR-0104): Alarm-Vorschau des
Ortsvergleichs in der Sprache des Kontos.

Nutzersicht: ein Konto mit ``language=en`` oeffnet im Ortsvergleich die
Alarm-Vorschau (``POST /api/briefings/{id}/alert-preview?kind=vergleich``)
und bekommt bisher eine deutsche Vorschau, obwohl der echte Alarm-Versand
fuer dasselbe Konto englisch ist. Die Vorschau muss DIESELBE Nachricht zeigen
wie der Versand (ADR-0011) -- je Konto in dessen Sprache.

Gemessen am Wirkort:
- Vorschau ueber den echten FastAPI-Endpunkt (``validator.router``), zwei
  echte Konten (``en`` und ``de``) im isolierten Datenordner, verschraenkt.
- Referenz = der ECHTE Versandweg desselben Kontos (Draht-Mitschnitt ueber
  lokale Telegram-/SMS-Stubs bzw. Aufzeichnungs-Senken), Haus-Muster aus
  ``test_alert_preview_compare_paritaet.py``. Kein Mock.
- SMS bleibt sprachneutral (ADR-0104 Pkt 5): die SMS beider Konten ist gleich.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.helpers.telegram_empfaenger import profil_chat
from tests.helpers.vorschau_umgebung import env  # noqa: F401  (Fixture)
from tests.tdd.test_alert_preview_compare_paritaet import (  # noqa: F401  (wire = Fixture)
    _CHANNELS,
    COOLDOWN_MIN,
    PRESET_ID,
    _assert_channels_equal,
    _change_dicts,
    _deviation_reference,
    _loc,
    _official_dicts,
    _official_reference,
    _onset_dicts,
    _seed,
    _stable,
    wire,
)

ORTE = ["loc-ibk", "loc-bz", "loc-mer"]


@pytest.fixture
def client():
    from api.routers import validator

    app = FastAPI()
    app.include_router(validator.router)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def konten(env):  # noqa: F811
    """Zwei echte Konten: ``<env>-en`` (language=en) und ``<env>-de`` (ohne Angabe)."""
    en, de = f"{env}-en", f"{env}-de"
    presets = {}
    for uid in (en, de):
        presets[uid] = _seed(uid)
    profil_chat(en, "99999", language="en")
    profil_chat(de, "99999")
    return {"en": (en, presets[en]), "de": (de, presets[de])}


def _vorschau(client, uid: str, body: dict) -> dict:
    resp = client.post(
        f"/api/briefings/{PRESET_ID}/alert-preview",
        params={"user_id": uid, "kind": "vergleich"}, json=body,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _onset_reference_wie_versand(preset: dict, body: dict, user_id: str, wire) -> dict:  # noqa: F811
    """Echter Versand `send_multi_location_radar_alert`, aufgerufen wie
    `compare_radar_alert.py` (Cooldown-Hinweis in der Sprache DIESES Kontos)."""
    from i18n import resolve_user_lang
    from services.compare_alert_channels import effective_compare_telegram_style
    from services.compare_radar_alert import _format_cooldown_display
    from services.notification_service import NotificationService
    from services.radar_service import NowcastResult

    by_loc = {o["location_id"]: o for o in body["onsets"]}
    entities = [
        (_loc(lid).name, _loc(lid), NowcastResult(
            onset_minutes=by_loc[lid]["onset_minutes"],
            intensity_label=by_loc[lid]["intensity_label"],
            source=by_loc[lid]["source"], is_convective=by_loc[lid]["is_convective"],
        ))
        for lid in preset["location_ids"] if lid in by_loc
    ]
    service = NotificationService(wire.settings(user_id), user_id)
    lang = resolve_user_lang(user_id)
    return wire.capture(lambda mail_sink: service.send_multi_location_radar_alert(
        entities, _CHANNELS, mail_sink=mail_sink,
        cooldown_display=_format_cooldown_display(COOLDOWN_MIN, lang=lang),
        telegram_style=effective_compare_telegram_style(preset), preset=preset,
    ))


def _referenz(art: str, preset: dict, body: dict, uid: str, wire) -> dict:  # noqa: F811
    if art == "changes":
        return _deviation_reference(preset, body, uid, wire)
    if art == "onsets":
        return _onset_reference_wie_versand(preset, body, uid, wire)
    return _official_reference(preset, body, uid)


def _waldbrand_ein_ort() -> dict:
    """Ein Ort ("nur X"/"only X") und eine Quelle mit sprachabhaengigem
    Anzeigenamen (Météo-France Waldbrand/wildfire) -- beide Stellen tragen
    Sprache nur in diesem Fall."""
    (eintrag,) = _official_dicts(["loc-bz"])
    return {"official": [{**eintrag, "source": "meteo_forets", "hazard": "wildfire_risk",
                          "label": "Waldbrandgefahr", "region_label": "Bozen"}]}


_BODIES = {
    "changes": lambda: {"changes": _change_dicts(ORTE)},
    "onsets": lambda: {"onsets": _onset_dicts(ORTE)},
    "official": lambda: {"official": _official_dicts(ORTE)},
    "official-ein-ort": _waldbrand_ein_ort,
}


@pytest.mark.parametrize(
    "art", list(_BODIES), ids=["abweichung", "radar", "amtlich", "amtlich-ein-ort-waldbrand"],
)
def test_vorschau_spricht_die_sprache_des_kontos(client, konten, wire, art):  # noqa: F811
    """AC (#2721): GIVEN zwei Konten, eines mit language=en, eines deutsch,
    mit demselben Ortsvergleich
    WHEN beide (verschraenkt en, de, en) die Alarm-Vorschau abrufen
    THEN zeigt jede Vorschau je Kanal genau die Nachricht, die der echte
    Versand an DIESES Konto schickt -- en englisch, de deutsch -- und die SMS
    ist fuer beide Konten gleich (sprachneutral, ADR-0104 Pkt 5).

    RED: die Vorschau rendert ohne Sprache -> das en-Konto bekommt deutschen
    Betreff/Klartext/Telegram, der Versand an dasselbe Konto ist englisch."""
    body = _BODIES[art]()
    ergebnisse = {}
    for sprache in ("en", "de", "en"):
        uid, preset = konten[sprache]
        got, ref = _stable(
            lambda: _referenz(art, preset, body, uid, wire),
            lambda: _vorschau(client, uid, body),
        )
        _assert_channels_equal(got, ref, f"{art}/{sprache}")
        ergebnisse[sprache] = got

    en, de = ergebnisse["en"], ergebnisse["de"]
    assert en["subject"] != de["subject"], f"{art}: en-Betreff ist der deutsche: {en['subject']!r}"
    assert en["telegram"] != de["telegram"], f"{art}: en-Telegram ist das deutsche"
    if art != "onsets":  # Onset-SMS traegt Uhrzeiten -> nur gleich innerhalb einer Minute
        assert en["sms"] == de["sms"], f"{art}: SMS muss sprachneutral bleiben"
