"""TDD RED — Issue #2279 Scheibe S1: EINE Alarm-Kanal-Auflösung für Trip UND
Ortsvergleich (`effective_alert_channels`/`resolve_alert_channels`).

SPEC: docs/specs/modules/rework_2279_s1_alert_kanal_aufloesung.md
      (Implementation Details, AC-1, AC-3, AC-4, AC-5)
KONTEXT: docs/context/rework-2279-alert-kanal-aufloesung.md

RED-Ursache: `src/services/alert_channels.py` existiert noch nicht --
`from services.alert_channels import effective_alert_channels,
resolve_alert_channels` schlägt mit `ModuleNotFoundError` fehl. Jede
Testfunktion importiert den Prüfling lokal (Projektkonvention, s.
`tests/tdd/test_compare_alert_channels.py`), damit jeder Fall EINZELN als
ImportError sichtbar wird statt in einem einzigen Kollektionsfehler zu
verschwinden.

Testpolitik (CLAUDE.md): kein Mock-Theater. Alle Tests laufen gegen echte
`app.trip.Trip`-Objekte, echte Compare-Preset-Rohdicts und echte
`data/users/<id>/user.json`-Tier-Dateien -- keine `Mock()`/`patch()`, nur
`monkeypatch` für Verdrahtungsnachweise (die stehen in
`test_compare_alert_channels.py`, AC-6, nicht hier). Kein Netz, keine
tatsächlichen Versände -- diese Datei prüft ausschließlich die REINE
Kanal-Auflösung (Kern-Schicht, offline, ohne Marker).

Pfadregel #1409: Nutzerverzeichnisse ausschließlich über
`app.loader.get_data_dir()`, kein fester Hauptrepo-Pfad.
"""
from __future__ import annotations

import copy
import itertools
import json
import shutil
import uuid
from datetime import date, timedelta

import pytest


# ───────────────────────────── Fixtures & Helfer ────────────────────────────

@pytest.fixture()
def clean_user_dir():
    """Registriert echte `data/users/<user_id>`-Verzeichnisse und räumt sie
    zuverlässig auf (Vorbild `test_compare_alert_channels.py::clean_user_dir`,
    `test_issue_1069_tier_channel_gating.py::clean_user_dirs`)."""
    from app.loader import get_data_dir

    created: list[str] = []

    def _register(user_id: str) -> str:
        created.append(user_id)
        path = get_data_dir(user_id)
        if path.exists():
            shutil.rmtree(path)
        return user_id

    yield _register

    for uid in created:
        path = get_data_dir(uid)
        if path.exists():
            shutil.rmtree(path)


def _fresh_uid(prefix: str) -> str:
    return f"tdd-2279-s1-{prefix}-{uuid.uuid4().hex[:8]}"


def _write_tier(user_id: str, tier: str) -> None:
    """Legt ein echtes `user.json` mit dem gegebenen Tier an -- Vorbild
    `test_compare_alert_channels.py::_write_standard_tier_user`."""
    from app.loader import get_data_dir

    path = get_data_dir(user_id)
    path.mkdir(parents=True, exist_ok=True)
    (path / "user.json").write_text(json.dumps({"id": user_id, "tier": tier}))


def _settings_all_capable():
    """Settings mit vollständig erreichbaren Kanälen (E-Mail/Telegram/SMS),
    ohne Netzzugriff -- kein Sink wird hier tatsächlich angesteuert. Dient
    ausschließlich dem Tripwire AC-5: die Auflösung darf sich davon NICHT
    beeinflussen lassen."""
    from app.config import Settings

    return Settings(
        smtp_host="dummy.invalid", smtp_user="dummy", smtp_pass="dummy",
        mail_to="dummy@example.invalid",
        telegram_bot_token="dummy-token", telegram_chat_id="123456",
        sms_gateway_url="https://sms.invalid/api/sms",
        seven_api_key="dummy-key", sms_to="+491700000000",
    )


def _settings_none_capable():
    """Settings ohne EINEN erreichbaren Kanal -- Gegenprobe zu
    `_settings_all_capable()` für den AC-5-Tripwire."""
    from app.config import Settings

    return Settings(
        smtp_host="", smtp_user="", smtp_pass="", mail_to="",
        telegram_bot_token="", telegram_chat_id="",
        seven_api_key="", sms_to="",
    )


def _stage():
    """Minimale, gültige Etappe -- die effektive Kanal-Berechnung liest nur
    `report_config`/`alert_channels`/`alert_rules`, nie die Etappen-Geometrie
    (Vorbild `test_trip_alert_channel_precedence.py::_stage`)."""
    from app.trip import Stage, Waypoint

    return Stage(
        id="S1", name="Etappe 1", date=date.today() + timedelta(days=1),
        waypoints=[
            Waypoint(id="W1", name="Start", lat=42.2, lon=9.05, elevation_m=400,
                     arrival_calculated="08:00"),
            Waypoint(id="W2", name="Ziel", lat=42.25, lon=9.09, elevation_m=1200,
                     arrival_calculated="12:00"),
        ],
    )


def _trip(trip_id: str, alert_channels: dict | None) -> "object":
    from app.trip import Trip

    return Trip(
        id=trip_id, name=f"Parity {trip_id}", stages=[_stage()],
        alert_channels=alert_channels,
    )


def _compare_preset(preset_id: str, **extra) -> dict:
    """Compare-Preset-Rohdict -- `**extra` setzt NUR ausdrücklich übergebene
    Schlüssel (Vorbild `test_compare_alert_channel_delivery.py::_compare_preset`):
    fehlt ein Feld, fehlt der Schlüssel im Dict GANZ, nicht `False`."""
    preset: dict = {
        "id": preset_id, "name": preset_id, "user_id": "unused",
        "location_ids": ["loc-1"], "schedule": "daily", "weekday": 4,
        "profil": "ALLGEMEIN", "hour_from": 9, "hour_to": 16,
        "empfaenger": [], "created_at": "2026-09-09T00:00:00Z",
    }
    preset.update(extra)
    return preset


_ALL_CHANNELS = ("email", "telegram", "sms", "premium_sms")


def _all_channel_combinations() -> list[dict]:
    """Alle 16 Kombinationen von True/False über die vier Kanäle, als
    vollständige Dicts (jeder Schlüssel IMMER gesetzt) -- passend zur
    `alert_channels`-Override-Form, die beide Adapter lesen."""
    combos = []
    for values in itertools.product([False, True], repeat=len(_ALL_CHANNELS)):
        combos.append(dict(zip(_ALL_CHANNELS, values)))
    return combos


# ═══════════════════════ Kern — `resolve_alert_channels` ════════════════════
# Direkter Nachweis des reinen Kern-Algorithmus (primitive Eingaben, Muster
# `app/day_window.py:26`), damit der geforderte Import von
# `resolve_alert_channels` (Aufgabenstellung) nicht nur behauptet, sondern
# tatsächlich geprüft wird -- unabhängig von den beiden Adaptern.

def test_core_override_replaces_inherited_even_when_result_is_empty():
    """Implementation Details Punkt 1: ein gesetztes `override` ersetzt
    `inherited` VOLLSTÄNDIG -- auch wenn ALLE Kanäle im Override aus sind.
    Kein `{"email"}`-Default bei explizitem, leerem Override."""
    from services.alert_channels import resolve_alert_channels

    result = resolve_alert_channels(
        override={"email": False, "telegram": False, "sms": False, "premium_sms": False},
        inherited={"email", "telegram"},
        rule_channel_sets=[],
        user_id=_fresh_uid("core-empty-override"),
    )

    assert result == set(), (
        f"Ein explizit leeres Override darf NICHT auf {{'email'}} zurückfallen, "
        f"gemessen: {result!r}"
    )


def test_core_no_override_uses_inherited_unchanged():
    """`override=None` ⇒ Ergebnis ist exakt `inherited` (keine aktiven
    Regeln). Bewusst `{"email", "telegram"}` statt eines SMS-Kanals: dieser
    Test prueft die reine Vererbung, nicht das Tier-Gate (das deckt AC-4
    separat mit einem gezielt konfigurierten Nutzer ab) -- ein frischer,
    ungeschriebener `user_id` faellt bei `sms`/`premium_sms` sonst
    fail-closed auf `free` zurueck (`services.user_tier`)."""
    from services.alert_channels import resolve_alert_channels

    result = resolve_alert_channels(
        override=None, inherited={"email", "telegram"}, rule_channel_sets=[],
        user_id=_fresh_uid("core-no-override"),
    )

    assert result == {"email", "telegram"}


def test_core_active_rules_union_with_fallback_to_inherited():
    """Implementation Details Punkt 3: pro Regel gewinnt ein nicht-leeres
    `rule.channels`, sonst fällt die Regel auf `inherited` zurück; das
    Gesamtergebnis ist die UNION über alle aktiven Regeln."""
    from services.alert_channels import resolve_alert_channels

    result = resolve_alert_channels(
        override=None, inherited={"email"},
        rule_channel_sets=[{"telegram"}, set()],
        user_id=_fresh_uid("core-union"),
    )

    assert result == {"telegram", "email"}, (
        f"Erwartet Union aus Regel-Override {{'telegram'}} und Fallback auf "
        f"inherited {{'email'}} der leeren Regel, gemessen: {result!r}"
    )


# ══════════════════════ AC-1 — Parität über beide `kind`-Werte ══════════════

@pytest.mark.parametrize("combo", _all_channel_combinations(), ids=lambda c: "-".join(
    ch for ch in _ALL_CHANNELS if c[ch]
) or "none")
def test_ac1_trip_and_compare_yield_identical_channel_set(combo, clean_user_dir):
    """AC-1: identische `alert_channels`-Konfiguration (alle 16 Kombinationen)
    liefert für Trip UND Ortsvergleich dieselbe Kanalmenge -- ein Nutzer mit
    Premium-Tier, damit weder SMS noch Premium-SMS durch das Tier-Gate
    verfälscht werden."""
    from services.alert_channels import effective_alert_channels

    user_id = clean_user_dir(_fresh_uid("ac1"))
    _write_tier(user_id, "premium")
    settings = _settings_all_capable()
    expected = {ch for ch in _ALL_CHANNELS if combo[ch]}

    trip = _trip("t-ac1", alert_channels=combo)
    preset = _compare_preset("p-ac1", alert_channels=dict(combo))

    trip_result = effective_alert_channels(trip, settings, user_id)
    compare_result = effective_alert_channels(preset, settings, user_id)

    assert trip_result == expected, (
        f"Trip-Auflösung fuer {combo!r} erwartet {expected!r}, "
        f"gemessen {trip_result!r}"
    )
    assert compare_result == expected, (
        f"Compare-Auflösung fuer {combo!r} erwartet {expected!r}, "
        f"gemessen {compare_result!r}"
    )
    assert trip_result == compare_result, (
        f"AC-1: Trip und Ortsvergleich muessen bei identischer Konfiguration "
        f"{combo!r} dieselbe Kanalmenge liefern -- Trip: {trip_result!r}, "
        f"Compare: {compare_result!r}"
    )


# ═════════════════ AC-3 — Bestand ohne `alert_channels` identisch ═══════════

def _flat_send_combinations() -> list[dict]:
    """Alle 8 Kombinationen der drei flachen Opt-in-Felder, JEDES Feld
    ausdrücklich gesetzt (True/False) -- kein fehlender Schlüssel (das prüft
    R4/AC-2 andernorts, hier geht es um die Bestands-IDENTITÄT)."""
    fields = ("send_telegram", "send_sms", "send_premium_sms")
    combos = []
    for values in itertools.product([False, True], repeat=len(fields)):
        combos.append(dict(zip(fields, values)))
    return combos


@pytest.mark.parametrize(
    "flat", _flat_send_combinations(),
    ids=lambda f: "-".join(k.replace("send_", "") for k, v in f.items() if v) or "none",
)
def test_ac3_legacy_preset_without_alert_channels_matches_today(flat, clean_user_dir):
    """AC-3: ein Bestands-Preset OHNE `alert_channels` (nur die flachen
    `send_*`-Felder) liefert exakt das heutige Verhalten -- E-Mail immer an,
    Opt-in-Kanäle nach Tier-Gate (hier Premium, also ungefiltert) -- UND das
    Preset-Dict bleibt nach dem Lauf bytegleich (keine Mutation durch die
    reine Auflösung)."""
    from services.alert_channels import effective_alert_channels

    user_id = clean_user_dir(_fresh_uid("ac3"))
    _write_tier(user_id, "premium")
    settings = _settings_all_capable()
    preset = _compare_preset("p-ac3", **flat)
    preset_before = copy.deepcopy(preset)

    expected = {"email"}
    if flat["send_telegram"]:
        expected.add("telegram")
    if flat["send_sms"]:
        expected.add("sms")
    if flat["send_premium_sms"]:
        expected.add("premium_sms")

    result = effective_alert_channels(preset, settings, user_id)

    assert result == expected, (
        f"AC-3: Bestandsverhalten fuer flat={flat!r} erwartet {expected!r}, "
        f"gemessen {result!r}"
    )
    assert preset == preset_before, (
        "AC-3: die reine Auflösung darf das Preset-Dict NICHT verändern, "
        f"vorher {preset_before!r}, nachher {preset!r}"
    )
    assert "alert_channels" not in preset, (
        "Setup-Kontrolle: dieses Preset darf kein alert_channels tragen."
    )


# ════════════════════ AC-4 — Tier-Gates genau einmal im Kern ════════════════

def test_ac4_non_premium_user_loses_sms_and_premium_sms_in_both_kinds(clean_user_dir):
    """AC-4: ein Nutzer OHNE SMS-/Premium-SMS-Tier verliert beide Kanäle
    sowohl beim Trip ALS AUCH beim Ortsvergleich -- das Gate sitzt nur einmal
    im gemeinsamen Kern.

    Mutations-Gegenprobe (Spec, PFLICHT): wird das Tier-Gate aus
    `resolve_alert_channels` entfernt, wird DIESER Test in BEIDEN Zweigen rot
    (sms/premium_sms tauchen dann im Ergebnis auf)."""
    from services.alert_channels import effective_alert_channels

    user_id = clean_user_dir(_fresh_uid("ac4"))
    _write_tier(user_id, "free")
    settings = _settings_all_capable()
    combo = {"email": False, "telegram": False, "sms": True, "premium_sms": True}

    trip = _trip("t-ac4", alert_channels=combo)
    preset = _compare_preset("p-ac4", alert_channels=dict(combo))

    trip_result = effective_alert_channels(trip, settings, user_id)
    compare_result = effective_alert_channels(preset, settings, user_id)

    for label, result in (("trip", trip_result), ("compare", compare_result)):
        assert "sms" not in result, (
            f"AC-4: free-Tier-Nutzer darf im {label}-Kanal-Set kein 'sms' "
            f"haben, gemessen: {result!r}"
        )
        assert "premium_sms" not in result, (
            f"AC-4: free-Tier-Nutzer darf im {label}-Kanal-Set kein "
            f"'premium_sms' haben, gemessen: {result!r}"
        )
    assert trip_result == compare_result == set(), (
        "AC-4: bei email/telegram=False und gesperrtem sms/premium_sms muss "
        f"in BEIDEN kinds ein leeres Set uebrig bleiben, gemessen trip="
        f"{trip_result!r}, compare={compare_result!r}"
    )


# ═══════════════════ AC-5 — `settings` bleibt inert (Tripwire) ══════════════

def test_ac5_settings_readiness_does_not_change_the_resolved_set_for_trip(clean_user_dir):
    """AC-5: identische Trip-Kanal-Konfiguration liefert mit voll
    sendebereiten UND mit vollständig leeren `Settings` dasselbe Ergebnis --
    Sendebereitschaft entscheidet ausschließlich die Zustellung
    (`notification_service.py`), NICHT die Auflösung.

    Mutations-Gegenprobe (Spec, PFLICHT): schmuggelt eine Implementierung
    eine `settings.can_send_*()`-Prüfung in den Kern, wird DIESER Test rot."""
    from services.alert_channels import effective_alert_channels

    user_id = clean_user_dir(_fresh_uid("ac5-trip"))
    _write_tier(user_id, "premium")
    combo = {"email": True, "telegram": True, "sms": True, "premium_sms": False}
    trip = _trip("t-ac5", alert_channels=combo)

    result_capable = effective_alert_channels(trip, _settings_all_capable(), user_id)
    result_empty = effective_alert_channels(trip, _settings_none_capable(), user_id)

    assert result_capable == result_empty, (
        "AC-5: das Ergebnis darf NICHT von der Sendebereitschaft der "
        f"Settings abhaengen -- capable={result_capable!r}, "
        f"empty={result_empty!r}"
    )
    assert result_capable == {"email", "telegram", "sms"}


def test_ac5_settings_readiness_does_not_change_the_resolved_set_for_compare(clean_user_dir):
    """AC-5, Ortsvergleich-Seite desselben Tripwires -- über den flachen
    Bestandspfad (kein `alert_channels`), damit auch der Erbe-Zweig des
    Compare-Adapters vom Settings-Objekt unbeeinflusst bleibt."""
    from services.alert_channels import effective_alert_channels

    user_id = clean_user_dir(_fresh_uid("ac5-compare"))
    _write_tier(user_id, "premium")
    preset = _compare_preset("p-ac5", send_telegram=True, send_sms=True)

    result_capable = effective_alert_channels(preset, _settings_all_capable(), user_id)
    result_empty = effective_alert_channels(preset, _settings_none_capable(), user_id)

    assert result_capable == result_empty, (
        "AC-5: das Ergebnis darf NICHT von der Sendebereitschaft der "
        f"Settings abhaengen -- capable={result_capable!r}, "
        f"empty={result_empty!r}"
    )
    assert result_capable == {"email", "telegram", "sms"}
