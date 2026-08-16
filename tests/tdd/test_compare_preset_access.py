"""TDD RED — Der geteilte Preset-/Notification-Helfer der drei
Ortsvergleich-Alarmpfade (Issue #1467 S4a, AC-13, AC-14) und der ADR-Nachtrag
(AC-19).

SPEC:    docs/specs/modules/rework_1467_s4a_amtlich.md
KONTEXT: docs/context/rework-1467-s4a-amtlich.md

Zwei Helfer liegen heute dreifach im Baum: ``_load_presets()``
(``compare_alert.py:592``, ``compare_radar_alert.py:294``,
``compare_official_alert.py:336`` — byte-identisch) und
``_notification_service_for()`` (``:576``/``:274``/``:322`` — strukturgleich).
``services/compare_preset_access.py`` fuehrt beide zusammen; ``log_label``
traegt den einzigen echten Unterschied.

Zu AC-14 ausdruecklich: die Spec spricht von „drei unterscheidbaren Texten mit
diesen Praefixen". Gemessen an der Fundstelle sind diese Praefixe die
LOG-Warnung bei fehlender Empfaengeradresse, nicht der Nutzertext der Alarmmail
(die Alarmtexte unterscheiden sich ohnehin ueber ganz andere Renderer). Geprueft
wird deshalb genau das Beobachtbare, das die Zusammenlegung einebnen wuerde.

Mock-frei: echte Dienste, echte Presets auf Platte, echte Log-Aufzeichnung ueber
``caplog``; der Aufrufzaehler ruft die ECHTE Fassung auf. Pfadregel #1409.
"""
from __future__ import annotations

import logging
import re
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from tests.helpers.briefing_imminent_fixtures import (  # noqa: E402
    LOCATION_ZONE, clean_uid, compare_preset, fresh_uid, ruhezeit_woanders,
    settings_email_only, stunde_versetzt, write_location, write_presets,
    write_user_tier,
)
from tests.helpers.official_alert_gate_fixtures import gate_spion  # noqa: E402

HELFER_MODUL = "services.compare_preset_access"
LADEN = "load_compare_alert_presets"
DIENST = "notification_service_for_preset"

PRESET = "cp-1467s4a-helfer"
ORT = "loc-1467s4a-helfer"

#: Die drei Alarmtyp-Praefixe, an denen der Nutzer im Protokoll erkennt, WELCHER
#: seiner drei Ortsvergleich-Alarme keine Empfaengeradresse hat.
PRAEFIXE = {
    "aenderung": "Compare-Alert:",
    "radar": "Compare-Alert (Radar):",
    "amtlich": "Compare-Alert (amtlich):",
}


@pytest.fixture
def nutzer():
    vergeben: list[str] = []

    def _neu(kennung: str, tier: str = "premium") -> str:
        user_id = fresh_uid(f"s4a-helfer-{kennung}")
        clean_uid(user_id)
        write_user_tier(user_id, tier)
        write_location(user_id, ORT)
        write_presets(user_id, [compare_preset(
            PRESET, morgen_stunde=stunde_versetzt(5, zone=LOCATION_ZONE),
            quiet=ruhezeit_woanders(), location_ids=[ORT])])
        vergeben.append(user_id)
        return user_id

    yield _neu
    for user_id in vergeben:
        clean_uid(user_id)


def _die_drei_dienste(user_id: str, settings) -> dict:
    from services.compare_alert import CompareAlertService
    from services.compare_official_alert import CompareOfficialAlertService
    from services.compare_radar_alert import CompareRadarAlertService

    return {
        "aenderung": CompareAlertService(settings=settings, user_id=user_id),
        "radar": CompareRadarAlertService(settings=settings, user_id=user_id),
        "amtlich": CompareOfficialAlertService(settings=settings, user_id=user_id),
    }


def _settings_ohne_empfaenger():
    """Vollstaendig konstruierte ``Settings`` OHNE ``mail_to``.

    Bewusst jedes Feld gesetzt (auch die leeren): ein weggelassenes Feld faellt
    bei pydantic still auf die Prod-``.env`` zurueck — genau so gingen am
    2026-08-03 echte Telegram-Nachrichten an den Produktiv-Chat des PO (#1477).
    """
    from app.config import Settings

    return Settings(
        smtp_host="dummy.invalid", smtp_user="dummy", smtp_pass="dummy", mail_to="",
        telegram_bot_token="", telegram_chat_id="", seven_api_key="", sms_to="")


# ══════════ AC-13: alle drei Pfade rufen denselben geteilten Helfer ═════════


def test_ac13_alle_drei_compare_pfade_rufen_denselben_helfer(nutzer):
    """AC-13: Die drei Bestandsmethoden ``_load_presets()`` und
    ``_notification_service_for()`` sind Ein-Zeiler-Wrapper geworden — jeder
    Pfad laeuft je Aufruf genau einmal durch den geteilten Helfer.

    Gezaehlt wird an der geteilten Fassung, nicht an den Wrappern: nur so faellt
    auf, wenn EINER der drei seine eigene Implementierung behaelt. Der
    Aufbau-Nachweis belegt, dass die Wrapper Brauchbares liefern — ein Helfer,
    der immer ``[]`` zurueckgibt, wuerde die Zaehler ebenso befriedigen.

    ROT HEUTE: ``ModuleNotFoundError`` — ``services/compare_preset_access.py``
    gibt es nicht.
    """
    from services.compare_preset_access import (  # noqa: F401
        load_compare_alert_presets, notification_service_for_preset,
    )

    uid = nutzer("ac13")
    dienste = _die_drei_dienste(uid, settings_email_only())

    with gate_spion(namen=(LADEN, DIENST), modulname=HELFER_MODUL) as spion:
        geladen = {name: d._load_presets() for name, d in dienste.items()}
        gebaut = {name: d._notification_service_for(geladen[name][0])
                  for name, d in dienste.items()}

    for name, presets in geladen.items():
        assert [p.get("id") for p in presets] == [PRESET], (
            f"Aufbau-Nachweis: {name} muss {PRESET!r} laden, geladen: {presets!r}")
        assert gebaut[name] is not None, (
            f"Aufbau-Nachweis: {name} muss einen Notification-Service liefern")

    assert spion.zaehle(LADEN) == 3, (
        f"Alle drei Pfade muessen ueber ``{LADEN}`` laden — gezaehlt: "
        f"{spion.zaehle(LADEN)} ({spion.reihenfolge()!r})")
    assert spion.zaehle(DIENST) == 3, (
        f"Alle drei Pfade muessen ueber ``{DIENST}`` bauen — gezaehlt: "
        f"{spion.zaehle(DIENST)} ({spion.reihenfolge()!r})")


# ═══ AC-14: die drei Alarmtypen bleiben in der Meldung unterscheidbar ═══════


def test_ac14_die_drei_alarmtypen_melden_weiterhin_unterscheidbar(nutzer, caplog):
    """AC-14: Fehlt die Empfaengeradresse, meldet jeder der drei Pfade das mit
    SEINEM Alarmtyp-Praefix — die Zusammenlegung aendert die Struktur, nicht den
    Text.

    Ohne diese Zusicherung waere die naheliegende Vereinfachung („ein Label fuer
    alle") eine stille Verschlechterung: der Nutzer saehe drei gleichlautende
    Meldungen und wuesste nicht mehr, welcher seiner drei Ortsvergleich-Alarme
    keine Adresse hat.

    ROT HEUTE: ``ModuleNotFoundError`` beim Helfer-Import — die Zusicherung
    gehoert zu dem Umbau, der sie gefaehrdet.
    """
    from services.compare_preset_access import (  # noqa: F401
        notification_service_for_preset,
    )

    uid = nutzer("ac14")
    dienste = _die_drei_dienste(uid, _settings_ohne_empfaenger())
    preset = dienste["amtlich"]._load_presets()[0]

    meldungen: dict[str, list[str]] = {}
    for name, dienst in dienste.items():
        caplog.clear()
        with caplog.at_level(logging.WARNING):
            dienst._notification_service_for(preset)
        meldungen[name] = [r.getMessage() for r in caplog.records]

    for name, praefix in PRAEFIXE.items():
        passend = [m for m in meldungen[name] if m.startswith(praefix)]
        assert passend, (
            f"Der {name}-Pfad muss seine Meldung mit {praefix!r} kennzeichnen, "
            f"protokolliert: {meldungen[name]!r}")
        assert uid in passend[0] and PRESET in passend[0], (
            f"Die Meldung muss Nutzer und Preset benennen: {passend[0]!r}")

    erste = {name: msgs[0] for name, msgs in meldungen.items() if msgs}
    assert len(set(erste.values())) == 3, (
        f"Die drei Meldungen muessen unterscheidbar bleiben: {erste!r}")


# ══════════════════════ AC-19: der ADR-0021-Nachtrag ═══════════════════════

#: Der Satz aus dem #1467-S3-Nachtrag, der laut E3 unveraendert richtig bleibt.
S3_SATZ = "Änderungs- und amtlicher Alarm bewusst weiterhin nicht"


def test_ac19_adr_0021_traegt_einen_nachtrag_zu_s4a():
    """AC-19: ADR-0021 traegt nach dieser Scheibe einen datierten Nachtrag mit
    Bezug auf #1467 S4a — und der bestehende Satz zur
    Unterdrueckungs-Protokollierung bleibt darin unangetastet.

    Nachtrag 2 impliziert heute, dass der amtliche Pfad KEINEN geteilten
    Ablauf-Baustein nutzt; diese Scheibe macht das sachlich falsch. Eine
    dokumentierte Entscheidung wird nie still ueberholt (ADR-Regel, CLAUDE.md).

    # doc-compliance-test — hier ist der Dokumententext ausdruecklich der
    Pruefgegenstand, nicht ein Ersatz fuer einen Verhaltensnachweis.

    ROT HEUTE: es gibt keinen S4a-Nachtrag.
    """
    adr = ROOT / "docs" / "adr" / "0021-shared-deviation-alert-engine.md"
    assert adr.exists(), f"ADR-0021 nicht gefunden unter {adr}"
    text = adr.read_text(encoding="utf-8")

    nachtraege = [z for z in text.splitlines()
                  if "Nachtrag" in z and "#1467" in z and "S4a" in z]
    assert nachtraege, (
        "ADR-0021 braucht einen Nachtrag mit Bezug auf '#1467' und 'S4a', der "
        "festhaelt, dass BEIDE amtlichen Pfade seit dieser Scheibe ueber "
        "denselben geteilten Ablauf-Baustein laufen.")

    datumsangaben = [date.fromisoformat(t) for z in nachtraege
                     for t in re.findall(r"\d{4}-\d{2}-\d{2}", z)]
    assert any(d >= date(2026, 8, 16) for d in datumsangaben), (
        f"Der S4a-Nachtrag muss auf den 2026-08-16 oder spaeter datiert sein, "
        f"gefunden: {datumsangaben!r} in {nachtraege!r}")
    assert S3_SATZ in text, (
        f"Der Satz zur Unterdrueckungs-Protokollierung aus dem S3-Nachtrag "
        f"bleibt laut E3 richtig und darf nicht entfernt werden: {S3_SATZ!r}")
