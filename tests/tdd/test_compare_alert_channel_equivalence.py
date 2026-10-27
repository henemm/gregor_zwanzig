"""AC-3, AC-12 — Issue #2293 Scheibe S2 (Epic #1374/#2345).

Spec: docs/specs/modules/feat_2293_s2_compare_alarm_kanaele.md AC-3, AC-12.

AC-3 ersetzt das im Ticket vorgesehene Migrationsskript (Abweichungen vom
Ticket, Punkt 1): statt eines Migrationslaufs materialisiert Go beim Laden
deterministisch ``alert_channels`` aus den flachen Feldern
(``{email:true, telegram:<flach>, sms:<flach>, premium_sms:<flach>}``,
Implementation Details Abschnitt 1/7). Dieser Test belegt die Absicht dahinter
auf der PYTHON-Seite: die geteilte Alarm-Kanal-Auflösung
(``services.alert_channels.effective_alert_channels`` ->
``_compare_channel_inputs``, unveraendert seit #2279 S1) liefert fuer ein
flaches Legacy-Preset (ohne ``alert_channels``-Schluessel) und das
aequivalente, materialisierte Preset (mit ``alert_channels``-Objekt) exakt
dieselbe Kanalmenge — die Materialisierung aendert kein beobachtbares
Alarmverhalten.

Erwartungsgemaess GRUEN heute (Waechter-Test, kein RED-Treiber): weder
``_compare_channel_inputs`` (``src/services/alert_channels.py:123-137``)
noch ``resolve_alert_channels`` werden von #2293 S2 veraendert — diese Datei
belegt/bewacht eine bereits bestehende Eigenschaft, auf der die Go-seitige
Materialisierung aufbaut (ohne diesen Nachweis waere die Ersetzung des
Migrationsskripts durch reine Materialisierung unbelegt).

AC-12: ein Preset mit ``alert_channels`` = alle vier Kanaele aus liefert die
LEERE Kanalmenge (kein ``{"email"}``-Default bei explizitem, leerem
Override) — identisches Verhalten zum Trip mit derselben Konfiguration.
Ebenfalls heute bereits GRUEN (``resolve_alert_channels`` Zeile 66-67:
"kein `{"email"}`-Default bei explizitem, leerem Override").

TESTPOLITIK (CLAUDE.md "Test-Politik: Zwei Schichten", Kern-Schicht): kein
Mock-Theater. Tarif-Gates (``sms_allowed``/``premium_sms_allowed``) werden
ueber ECHTE ``user.json``-Profile unter der pytest-isolierten Datenwurzel
geprueft (Vorbild ``tests/unit/test_compare_alert_premium_sms.py::_write_profile``),
kein ``patch``/``Mock``.
"""
from __future__ import annotations

import itertools
import json
import uuid

from app.config import Settings
from services.alert_channels import effective_alert_channels


def _write_profile(user_id: str, tier: str) -> None:
    from app.loader import get_data_dir

    path = get_data_dir(user_id)
    path.mkdir(parents=True, exist_ok=True)
    (path / "user.json").write_text(
        json.dumps({"id": user_id, "tier": tier}), encoding="utf-8"
    )


def _uid(prefix: str) -> str:
    return f"tdd-2293-eq-{prefix}-{uuid.uuid4().hex[:6]}"


def _flat_preset(telegram: bool, sms: bool, premium_sms: bool) -> dict:
    """Bestands-Preset OHNE alert_channels — nur die drei flachen
    Kanal-Opt-ins (vor #2293 S2 der einzige Zustand fuer den Alarm-Pfad,
    solange kein Go-Schreibzugriff stattgefunden hat)."""
    return {
        "id": "cp-eq-flat", "name": "eq-flat",
        "send_telegram": telegram, "send_sms": sms, "send_premium_sms": premium_sms,
    }


def _materialized_preset(telegram: bool, sms: bool, premium_sms: bool) -> dict:
    """Dasselbe Preset NACH der Go-Materialisierung (Implementation Details
    Abschnitt 1): alert_channels.email ist immer true, die drei anderen
    Kanaele uebernehmen 1:1 den vorherigen flachen Wert."""
    return {
        "id": "cp-eq-mat", "name": "eq-mat",
        "send_telegram": telegram, "send_sms": sms, "send_premium_sms": premium_sms,
        "alert_channels": {
            "email": True, "telegram": telegram, "sms": sms, "premium_sms": premium_sms,
        },
    }


def test_materialized_alert_channels_yield_same_set_as_flat_legacy_preset_for_all_combinations():
    """AC-3: alle 8 Kombinationen der drei flachen Kanal-Felder, je einmal
    fuer einen Nutzer OHNE (free) und MIT (premium) Premium-Tarif — die
    Materialisierung darf die resultierende Kanalmenge in KEINER
    Kombination veraendern."""
    settings = Settings()
    for tier in ("free", "standard", "premium"):
        uid = _uid(tier)
        _write_profile(uid, tier)
        for telegram, sms, premium_sms in itertools.product([False, True], repeat=3):
            flat = _flat_preset(telegram, sms, premium_sms)
            materialized = _materialized_preset(telegram, sms, premium_sms)

            flat_channels = effective_alert_channels(flat, settings, uid)
            materialized_channels = effective_alert_channels(materialized, settings, uid)

            assert flat_channels == materialized_channels, (
                f"AC-3: tier={tier} telegram={telegram} sms={sms} premium_sms={premium_sms}: "
                f"flat={flat_channels!r} != materialized={materialized_channels!r} — "
                "die Materialisierung veraendert die Alarm-Kanalmenge"
            )


def test_all_four_alert_channels_false_yields_empty_channel_set():
    """AC-12: ein Ortsvergleich mit alert_channels = alle vier Kanaele aus
    liefert die leere Menge — ein ausgeloester Alarm wird ueber KEINEN
    Kanal zugestellt (kein Fehler, keine Sperre, kein {"email"}-Default)."""
    settings = Settings()
    uid = _uid("ac12")
    _write_profile(uid, "premium")

    preset = {
        "id": "cp-ac12", "name": "ac12",
        "alert_channels": {
            "email": False, "telegram": False, "sms": False, "premium_sms": False,
        },
    }
    channels = effective_alert_channels(preset, settings, uid)
    assert channels == set(), (
        f"AC-12: erwartet leere Kanalmenge bei allen vier Kanaelen aus, erhalten: {channels!r}"
    )
