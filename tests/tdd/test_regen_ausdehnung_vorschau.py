"""TDD RED — Issue #2051 Scheibe S2b: die Alarm-Vorschau zeigt die
raeumliche Ausdehnung in allen vier Kanaltexten.

SPEC: docs/specs/modules/feat_2051_s2b_ausdehnung_kanaele.md — AC-12, AC-13.

Warum das zaehlt (R4): `render_alert_preview` baut sein `OnsetEvent` heute
OHNE `rain_zones`/`km_measured` (`validator_render_service.py:117-172`) und
`OnsetPayload` kennt die Felder nicht (`api/routers/validator.py:226-268`).
Solange diese Luecke offen ist, ist KEIN AC dieser Scheibe ueber
`POST /api/trips/{id}/alert-preview` auf Staging messbar — genau das hat die
S2a-Lieferung als „nicht gemessen" gebucht.

Pydantic verwirft unbekannte Felder STILL (Muster #2046 Finding F002): ohne
diesen Test liesse sich die Payload-Erweiterung ersatzlos streichen, und die
Ausdehnung verschwaende lautlos aus der Vorschau.

Mock-frei: echte Pydantic-Payloads (`AlertPreviewBody`/`OnsetPayload`),
echter `Trip`, echte Renderer. Gestellte Uhr (`freeze_time`) statt Wanduhr —
die Vorschau setzt ihre Stand-Zeile aus `datetime.now()`.
"""
from __future__ import annotations

import inspect
from pathlib import Path

from freezegun import freeze_time

from api.routers.validator import AlertPreviewBody
from app.trip import Trip
from services.rain_extent import RainZone
from services.validator_render_service import render_alert_preview

# Feste Uhr: die Stand-Zeile der Vorschau ("Stand: heute 12:00") entsteht aus
# `datetime.now()`. Ohne gestellte Uhr waere der Volltextvergleich in AC-13
# wanduhrabhaengig.
_UHR = "2026-08-23T12:00:00+00:00"

_ZONE = RainZone(km_from=8.0, km_to=12.0, onset_minutes=20, event_end_minutes=40)

_KANAL_FELDER = ("subject", "email_plain", "telegram", "sms")


def _trip() -> Trip:
    return Trip(id="trip-2051-s2b", name="Vorschau-Trip", stages=[])


def _payload(**onset_overrides) -> AlertPreviewBody:
    """Der Vorschau-Payload als ECHTES Pydantic-Objekt (kein Mock, kein
    `SimpleNamespace`) — nur so laeuft der Test durch denselben
    Validierungsweg wie der HTTP-Endpunkt."""
    onset = {
        "onset_minutes": 25,
        "onset_time": "15:00",
        "km_from": 0.0,
        "km_to": 6.0,
        "is_convective": False,
        "intensity_label": "Mäßiger Regen",
        "source_label": "Radar (DWD)",
        "segment_id": "Ziel",
        "onset_precip_mm": 2.5,
        "event_end_time": "16:30",
    }
    onset.update(onset_overrides)
    return AlertPreviewBody(onset=onset)


def test_prueling_stammt_aus_diesem_arbeitsbaum():
    """Vorbedingung (kein AC): Prueffläche und Payload-Schema werden RELATIV
    ZU DIESER Testdatei aufgeloest — sonst pruefte ein Worktree-Lauf still
    die Dateien des Hauptrepos und lieferte falsches Gruen."""
    from api.routers import validator as validator_modul
    from services import validator_render_service as service_modul

    arbeitsbaum = Path(__file__).resolve().parents[2]
    for modul in (validator_modul, service_modul):
        pfad = Path(inspect.getfile(modul)).resolve()
        assert pfad.is_relative_to(arbeitsbaum), (
            f"Prueling stammt nicht aus diesem Arbeitsbaum: {pfad}"
        )


# --------------------------------------------------------------------------
# AC-12 — mit gesetzten Feldern traegt JEDER der vier Vorschau-Texte die
#         Ausdehnungsangabe.
# --------------------------------------------------------------------------

def test_ac12_vorschau_zeigt_die_ausdehnung_in_allen_vier_kanaelen():
    """AC-12 GIVEN einen `OnsetPayload` mit gesetzten `rain_zones` und
    `km_measured=True`
    WHEN `render_alert_preview(trip_obj, body)` laeuft
    THEN traegt JEDER der vier betroffenen Preview-Texte (`subject`,
    `email_plain`, `telegram`, `sms`) die Ausdehnungsangabe.

    Die Vorbedingung prueft zuerst das PAYLOAD-SCHEMA selbst: verwirft
    pydantic die neuen Schluessel still, waere der Rest des Tests eine
    Aussage ueber einen Payload, der die Angabe gar nicht enthaelt.

    Zugleich die Positivkontrolle zu AC-13 unten: dort wird Byte-Gleichheit
    OHNE die Felder zugesichert — ohne diesen Test waere sie trivial wahr.

    RED heute: `OnsetPayload` kennt `rain_zones`/`km_measured` nicht
    (`AttributeError` an der Vorbedingung)."""
    body = _payload(
        km_measured=True,
        rain_zones=[{
            "km_from": _ZONE.km_from, "km_to": _ZONE.km_to,
            "onset_minutes": _ZONE.onset_minutes,
            "event_end_minutes": _ZONE.event_end_minutes,
        }],
    )

    assert body.onset.km_measured is True, (
        "Vorbedingung: `OnsetPayload` muss `km_measured` fuehren — pydantic "
        "verwirft ein unbekanntes Feld sonst still."
    )
    assert len(body.onset.rain_zones) == 1, (
        f"Vorbedingung: `OnsetPayload.rain_zones` muss die Zone fuehren, "
        f"erhalten {body.onset.rain_zones!r}"
    )
    assert (
        body.onset.rain_zones[0].km_from == _ZONE.km_from
        and body.onset.rain_zones[0].km_to == _ZONE.km_to
    ), (
        f"Vorbedingung: die Zonenwerte muessen unveraendert ankommen, "
        f"erhalten {body.onset.rain_zones[0]!r}"
    )

    with freeze_time(_UHR):
        out = render_alert_preview(_trip(), body)

    langform = f"Nass km {int(round(_ZONE.km_from))}-{int(round(_ZONE.km_to))}"
    kurzform = f"km{int(round(_ZONE.km_from))}-{int(round(_ZONE.km_to))}"

    for feld in _KANAL_FELDER:
        erwartet = kurzform if feld == "sms" else langform
        assert erwartet in (out[feld] or ""), (
            f"AC-12: das Vorschau-Feld {feld!r} traegt die Ausdehnungsangabe "
            f"{erwartet!r} nicht: {out[feld]!r}"
        )


# --------------------------------------------------------------------------
# AC-13 — ohne die neuen Felder bleibt jeder Vorschau-Text byte-identisch
#         (Rueckwaertskompatibilitaets-Vertrag, Muster #2046 F002).
# --------------------------------------------------------------------------

# Aufgenommener Ist-Stand der vier Vorschau-Texte VOR dieser Spec (Stand
# `c8334159`, aufgenommen 2026-08-23 bei gestellter Uhr `_UHR`).
_AC13_GOLD = {
    "subject": "[Vorschau-Trip] 🏁 Ziel · Regen in 25 Min · letzter Regen gegen 16:30",
    "email_plain": (
        "Regen in 25 Min\n"
        "\n"
        "Radar-Nowcast\n"
        "\n"
        "Wo & wann: 🏁 Ziel · ab 15:00 · letzter Regen gegen 16:30\n"
        "Intensität: Mäßiger Regen\n"
        "Quelle: Radar (DWD)\n"
        "\n"
        "Stand: heute 12:00\n"
        "\n"
        "Regen-/Gewitter-Alarm · Radar (DWD)"
    ),
    "telegram": (
        "<b>Vorschau-Trip · 🏁 Ziel · Regen in 25 Min</b>\n"
        "15:00 · letzter Regen gegen 16:30 · Mäßiger Regen · Radar (DWD)"
    ),
    "sms": "Ziel: R2.5@15:00@16:30",
}


def test_ac13_alt_client_payload_bleibt_byte_identisch():
    """AC-13 GIVEN einen `OnsetPayload` OHNE die neuen Felder (Alt-Client)
    WHEN `render_alert_preview` laeuft
    THEN bleibt jeder der vier Preview-Texte byte-identisch zum Stand vor
    dieser Spec — die neuen Felder sind additiv und defaulten auf „keine
    Ausdehnung".

    Regressionstest: laeuft heute (RED-Zustand) GRUEN und muss nach der
    Implementierung gruen BLEIBEN. Seine Positivkontrolle ist AC-12 oben —
    derselbe Aufbau MIT den Feldern erzeugt einen anderen Text; ohne sie
    waere diese Byte-Gleichheit trivial erfuellbar.

    RED heute: gruen (Regressions-Absicherung)."""
    with freeze_time(_UHR):
        out = render_alert_preview(_trip(), _payload())

    for feld in _KANAL_FELDER:
        assert out[feld] == _AC13_GOLD[feld], (
            f"AC-13: das Vorschau-Feld {feld!r} hat sich gegenueber dem Stand "
            f"vor dieser Spec veraendert.\n"
            f"Erhalten:\n{out[feld]!r}\nErwartet:\n{_AC13_GOLD[feld]!r}"
        )
        assert "Nass km" not in (out[feld] or ""), (
            f"AC-13: ohne die neuen Felder darf keine Ausdehnungsangabe "
            f"erscheinen ({feld}): {out[feld]!r}"
        )
