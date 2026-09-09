"""TDD — Issue #1467 Scheibe S2, Arbeitsgang AG1 (Compare-BRIEFING-Resolver)
+ Issue #2279 Scheibe S1 (geteilte Compare-ALARM-Auflösung, AC-6-Block unten).

Historie (AG1, #1467): der Compare-BRIEFING-Kanal-Resolver existierte
funktional identisch an zwei Stellen —
`compare_official_alert.py::CompareOfficialAlertService._effective_channels`
und `scheduler_dispatch_service.py`s interner Wrapper. AG1 zog beides in ein
neues Modul `src/services/compare_alert_channels.py`; beide Bestandsstellen
delegierten dorthin.

Stand (#2279 S1): der Compare-BRIEFING-Resolver aus AG1 heisst jetzt
`effective_compare_briefing_channels` (umbenannt, Spec-Abschnitt
"Umbenennung des Briefing-Resolvers") -- die drei Compare-ALARM-Pfade nutzen
seither die geteilte Auflösung `services.alert_channels.effective_alert_channels`
(AC-6-Block unten). Der frühere, jetzt abgeloeste Name ist vollstaendig aus
dem Repository entfernt (Watchdog-Test am Dateiende).

Regel (unveraendert, gilt fuer den BRIEFING-Resolver): E-Mail immer aktiv;
Telegram nur bei `preset.get("send_telegram")` UND `settings.can_send_telegram()`;
SMS nur bei `preset.get("send_sms")` UND `settings.can_send_sms()` UND
`sms_allowed(user_id)`. Gelesen wird aus dem Preset-Rohdict, ein fehlender
Schluessel darf NIE als "an" gelten (Risiko R4 der Spec).

Testpolitik (CLAUDE.md): kein Mock-Theater. `monkeypatch` wird ausschliesslich
fuer die Verdrahtungsnachweise (AC-6-Block) eingesetzt und setzt am
VERBRAUCHENDEN Modul an (`trip_alert`/`compare_alert`/`compare_official_alert`/
`compare_radar_alert`/`scheduler_dispatch_service`), nicht am
Definitionsort -- sonst waere der Patch wirkungslos als Beweis. Alle anderen
Tests laufen gegen echte Funktionen und echte Dict-/Settings-Fixturen, keine
echten Versaende (kein SMTP, kein Telegram-Netz, kein IMAP). Reine
Kern-Schicht, offline, ohne Marker `email`/`live`/`staging`.

SPEC: docs/specs/modules/rework_1467_s2_aenderungsalarm.md (AG1: AC-1..AC-3),
docs/specs/modules/rework_2279_s1_alert_kanal_aufloesung.md (AC-6)

Diese Datei fasst KEINE Pfade fest -- sie nutzt ausschliesslich
`app.loader.get_data_dir()` fuer Nutzer-Testverzeichnisse, kein Hauptrepo-
Pfad-Literal (Issue #1409).
"""
from __future__ import annotations

import json
import shutil
import uuid

import pytest


# ───────────────────────────── Fixtures & Helfer ────────────────────────────

def _telegram_capable_settings():
    """Settings mit vollstaendiger Telegram-Konfiguration (`can_send_telegram()`
    == True), ohne Netzzugriff -- kein Sink wird hier tatsaechlich angesteuert."""
    from app.config import Settings

    return Settings(telegram_bot_token="dummy-token", telegram_chat_id="123456")


def _sms_capable_settings():
    """Settings mit vollstaendiger SMS-Konfiguration (`can_send_sms()` ==
    True), ohne Netzzugriff."""
    from app.config import Settings

    return Settings(
        sms_gateway_url="https://sms.invalid/api/sms",
        seven_api_key="dummy-key",
        sms_to="+491700000000",
    )


def _write_standard_tier_user(user_id: str) -> None:
    """Legt ein echtes `user.json` mit `tier="standard"` an, damit
    `sms_allowed(user_id)` fuer diesen Nutzer True liefert (Voraussetzung fuer
    R4-Nachweise, die zeigen sollen, dass NUR der fehlende Preset-Schluessel
    blockiert -- nicht ein zufaellig fehlendes Tier)."""
    from app.loader import get_data_dir

    path = get_data_dir(user_id)
    path.mkdir(parents=True, exist_ok=True)
    (path / "user.json").write_text(json.dumps({"id": user_id, "tier": "standard"}))


@pytest.fixture()
def clean_user_dir():
    """Registriert echte `data/users/<user_id>`-Verzeichnisse fuer Test-Setup
    und raeumt sie zuverlaessig auf (Vorbild `test_issue_1069_tier_channel_gating.py`)."""
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


# ───────────────────────── AC-1 — Wirkung, Bestandsverhalten ────────────────

def test_ac1_telegram_optin_and_capable_settings_yield_email_and_telegram():
    """AC-1: Preset mit `send_telegram: true` + telegramfaehige Konto-Settings
    -> der gemeinsame BRIEFING-Resolver liefert `{"email", "telegram"}`
    (E-Mail bleibt immer aktiv, Telegram kommt bei erfuelltem Opt-in UND
    globaler Faehigkeit hinzu). Direkter Aufruf des Bausteins (seit #2279 S1
    `effective_compare_briefing_channels`)."""
    from services.compare_alert_channels import effective_compare_briefing_channels

    settings = _telegram_capable_settings()
    user_id = f"tdd-ag1-ac1-{uuid.uuid4().hex[:8]}"
    preset = {"id": "p-ac1", "send_telegram": True}

    result = effective_compare_briefing_channels(preset, settings, user_id)

    assert result == {"email", "telegram"}, (
        "AC-1: E-Mail muss immer aktiv sein, send_telegram=True + "
        f"telegramfaehige Settings muessen 'telegram' ergaenzen. "
        f"Ergebnis: {result!r}."
    )


# ───────────────────────── AC-2 — Wirkung, negative Seite (R4) ──────────────

def test_ac2_missing_send_telegram_key_never_activates_telegram():
    """AC-2/R4: Fehlt der Schluessel `send_telegram` GANZ im Preset-Dict
    (nicht `False`, sondern gar nicht vorhanden), darf der BRIEFING-Resolver
    Telegram NIE aktivieren -- selbst wenn die Konto-Settings telegramfaehig
    sind."""
    from services.compare_alert_channels import effective_compare_briefing_channels

    settings = _telegram_capable_settings()
    user_id = f"tdd-ag1-ac2-tg-{uuid.uuid4().hex[:8]}"
    preset = {"id": "p-ac2-tg"}  # send_telegram fehlt komplett

    result = effective_compare_briefing_channels(preset, settings, user_id)

    assert "telegram" not in result, (
        "AC-2/R4: ein FEHLENDER send_telegram-Schluessel darf niemals als "
        f"Opt-in gelten. Ergebnis: {result!r}."
    )
    assert result == {"email"}


def test_ac2_missing_send_sms_key_never_activates_sms(clean_user_dir):
    """AC-2/R4: Derselbe Fall fuer SMS -- fehlt `send_sms` im Preset-Dict,
    bleibt SMS aus, selbst bei sms-faehigen Settings UND einem Nutzer, dessen
    Tier SMS grundsaetzlich erlauben wuerde (`sms_allowed()` == True). Der
    fehlende Schluessel allein muss blockieren."""
    from services.compare_alert_channels import effective_compare_briefing_channels

    user_id = clean_user_dir(f"tdd-ag1-ac2-sms-{uuid.uuid4().hex[:8]}")
    _write_standard_tier_user(user_id)
    settings = _sms_capable_settings()
    preset = {"id": "p-ac2-sms"}  # send_sms fehlt komplett

    result = effective_compare_briefing_channels(preset, settings, user_id)

    assert "sms" not in result, (
        "AC-2/R4: ein FEHLENDER send_sms-Schluessel darf niemals als Opt-in "
        f"gelten, auch nicht bei SMS-faehigem Tier. Ergebnis: {result!r}."
    )
    assert result == {"email"}


# ══════════ AC-6 (Issue #2279 S1) — Verdrahtung auf die geteilte Alarm- ══════
# ══════════ Auflösung `effective_alert_channels` + umbenannter Briefing- ════
# ══════════ Resolver `effective_compare_briefing_channels` ═════════════════
#
# Ersetzt die vormaligen AC-3a/AC-3b dieser Datei (#1467 S2 AG1): der
# Verdrahtungsnachweis läuft jetzt gegen die EINE Alarm-Auflösung aus
# `services/alert_channels.py` (Trip UND alle drei Compare-Alarmpfade),
# der Compare-BRIEFING-Pfad bleibt bewusst auf dem umbenannten
# `effective_compare_briefing_channels` (nicht auf der Alarm-Auflösung —
# Briefing- und Alarm-Kanäle müssen getrennt bleiben, Spec Abschnitt
# "Umbenennung des Briefing-Resolvers").
#
# Patch-Muster unverändert (AG1): `monkeypatch` setzt am VERBRAUCHENDEN
# Modul an, nie am Definitionsort — sonst wäre der Patch als Delegations-
# Beweis wirkungslos.

def test_ac6_trip_alert_delegates_to_shared_resolver(monkeypatch):
    """AC-6: `TripAlertService._effective_alert_channels` muss ueber das im
    Modul `trip_alert` importierte Symbol `effective_alert_channels` laufen
    -- nicht ueber eine eigene Inline-Kopie des Kern-Algorithmus (Issue
    #2279 S1 hebt den Trip-Algorithmus in den geteilten Kern). Ein Trip OHNE
    jede Kanal-Konfiguration wuerde inline `{"email"}` ergeben (Legacy-
    Default); liefert der Aufruf stattdessen den gepatchten Satz, ist die
    Delegation bewiesen."""
    from datetime import date, timedelta
    from app.config import Settings
    from app.trip import Stage, Trip, Waypoint
    import services.trip_alert as ta

    def _fake_resolver(trip, settings, user_id):
        return {"premium_sms"}  # bewusst NICHT das Inline-Ergebnis {"email"}

    monkeypatch.setattr(ta, "effective_alert_channels", _fake_resolver, raising=False)

    stage = Stage(
        id="S1", name="Etappe 1", date=date.today() + timedelta(days=1),
        waypoints=[
            Waypoint(id="W1", name="Start", lat=42.2, lon=9.05, elevation_m=400,
                     arrival_calculated="08:00"),
            Waypoint(id="W2", name="Ziel", lat=42.25, lon=9.09, elevation_m=1200,
                     arrival_calculated="12:00"),
        ],
    )
    trip = Trip(id="t-delegation-trip", name="Delegation", stages=[stage])
    user_id = f"tdd-ag1-ta-{uuid.uuid4().hex[:8]}"
    svc = ta.TripAlertService(settings=Settings().with_user_profile(user_id), user_id=user_id)

    result = svc._effective_alert_channels(trip)

    assert result == {"premium_sms"}, (
        "AC-6: _effective_alert_channels muss ueber das importierte "
        "Resolver-Symbol effective_alert_channels delegieren. Solange "
        "trip_alert.py die Inline-Kopie behaelt, bleibt das Ergebnis beim "
        f"Legacy-Default {{'email'}} haengen. Gemessen: {result!r}."
    )


def test_ac6_compare_alert_delegates_to_shared_resolver(monkeypatch):
    """AC-6: `CompareAlertService` muss den Kanalsatz fuer den Vorhersage-
    Aenderungsalarm ueber das im Modul `compare_alert` importierte Symbol
    `effective_alert_channels` beziehen (`compare_alert.py:603`) -- nicht
    ueber die alte, jetzt entfernte `compare_alert_channels`-Funktion.
    Beweis am `AlertEvaluationConfig.channels`-Feld, das direkt aus diesem
    Aufruf stammt."""
    import services.compare_alert as ca

    def _fake_resolver(preset, settings, user_id):
        return {"telegram"}  # bewusst NICHT das Inline-Ergebnis {"email"}

    monkeypatch.setattr(ca, "effective_alert_channels", _fake_resolver, raising=False)

    settings = _telegram_capable_settings()
    user_id = f"tdd-ag1-ca-{uuid.uuid4().hex[:8]}"
    svc = ca.CompareAlertService(settings=settings, user_id=user_id)
    preset = {"id": "p-delegation-ca", "location_ids": []}

    config = svc._build_eval_config(preset, cooldown_minutes=60, all_locations={})

    assert config.channels == {"telegram"}, (
        "AC-6: _build_eval_config muss die Kanaele ueber das importierte "
        "Resolver-Symbol effective_alert_channels beziehen. Solange "
        "compare_alert.py noch die alte compare_alert_channels-Funktion "
        f"benutzt, bleibt die Wirkung unveraendert. Gemessen: {config.channels!r}."
    )


def test_ac6_compare_official_alert_delegates_to_shared_resolver(monkeypatch):
    """AC-6 (vormals AC-3a): `CompareOfficialAlertService._effective_channels`
    muss ueber das im Modul `compare_official_alert` importierte Symbol
    `effective_alert_channels` laufen -- nicht ueber eine eigene Inline-Kopie
    oder die alte, jetzt entfernte `compare_alert_channels`-Funktion. Ein
    Preset OHNE jedes Opt-in wuerde inline `{"email"}` ergeben -- liefert der
    Aufruf stattdessen den gepatchten Satz, ist die Delegation bewiesen."""
    import services.compare_official_alert as coa

    def _fake_resolver(preset, settings, user_id):
        return {"telegram"}  # bewusst NICHT das Inline-Ergebnis {"email"}

    monkeypatch.setattr(coa, "effective_alert_channels", _fake_resolver, raising=False)

    settings = _telegram_capable_settings()
    user_id = f"tdd-ag1-coa-{uuid.uuid4().hex[:8]}"
    svc = coa.CompareOfficialAlertService(settings=settings, user_id=user_id)
    preset = {"id": "p-delegation-coa"}  # kein send_telegram/send_sms

    result = svc._effective_channels(preset)

    assert result == {"telegram"}, (
        "AC-6: _effective_channels muss ueber das importierte Resolver-"
        "Symbol effective_alert_channels delegieren. Solange "
        "compare_official_alert.py noch die alte compare_alert_channels-"
        "Funktion oder eine Inline-Kopie benutzt, bleibt die Wirkung "
        f"unveraendert bei {{'email'}}. Gemessen: {result!r}."
    )


def test_ac6_compare_radar_alert_delegates_to_shared_resolver(monkeypatch):
    """AC-6: `CompareRadarAlertService` muss den Kanalsatz fuer den Nowcast-
    Alarm ueber das im Modul `compare_radar_alert` importierte Symbol
    `effective_alert_channels` beziehen (`compare_radar_alert.py:169`).
    Beweis OHNE echten Nowcast-Abruf: eine Ruhezeit, die den JETZIGEN
    Zeitpunkt umschliesst, blockt VOR jedem Radar-Abruf und protokolliert
    trotzdem den (patchbaren) Kanalsatz im Unterdrueckungs-Eintrag
    (`alert_log.append_suppressed_entry`, Parameter `effective_channels`)."""
    import services.compare_radar_alert as cra
    from app.loader import save_location
    from services import alert_log
    from tests.helpers.nowcast_gate_fixtures import (
        clean_uid, fresh_uid, location, quiet_window_now, radar_preset,
        read_log, write_presets,
    )

    def _fake_resolver(preset, settings, user_id):
        return {"premium_sms"}  # bewusst NICHT das Inline-Ergebnis {"email"}

    monkeypatch.setattr(cra, "effective_alert_channels", _fake_resolver, raising=False)

    uid, preset_id = fresh_uid("ac6-cra"), "cp-ac6-cra"
    clean_uid(uid)
    try:
        quiet_from, quiet_to = quiet_window_now()
        save_location(location("loc-cra", "Verdrahtungsdorf"), user_id=uid)
        write_presets(uid, [radar_preset(
            preset_id, ["loc-cra"], user_id=uid,
            quiet_from=quiet_from, quiet_to=quiet_to,
        )])

        sent = cra.CompareRadarAlertService(
            settings=_telegram_capable_settings(), user_id=uid,
        ).check_all_compare_presets()

        assert sent == 0, "Vorbedingung: die Ruhezeit muss den Alarm blocken"
        entries = [
            e for e in read_log(uid).get("not_delivered", [])
            if e.get("entity_id") == preset_id
        ]
        assert len(entries) == 1, (
            f"Erwartet genau einen Unterdrueckungs-Eintrag: {entries!r}"
        )
        assert entries[0]["channels_not_sent"] == [
            {"channel": "premium_sms", "reason": alert_log.REASON_QUIET_HOURS}
        ], (
            "AC-6: der Unterdrueckungs-Eintrag muss den GEPATCHTEN Kanalsatz "
            "widerspiegeln -- solange compare_radar_alert.py noch die alte "
            "compare_alert_channels-Funktion benutzt, bleibt es bei "
            f"'email'. Gemessen: {entries[0]['channels_not_sent']!r}"
        )
    finally:
        clean_uid(uid)


def test_ac6_scheduler_dispatch_delegates_to_briefing_resolver(monkeypatch):
    """AC-6 (vormals AC-3b): der interne Wrapper
    `_effective_compare_briefing_channels` in `scheduler_dispatch_service.py`
    muss ueber das importierte Symbol `effective_compare_briefing_channels`
    laufen -- der Compare-BRIEFING-Pfad bleibt bewusst auf dem umbenannten
    Briefing-Resolver, NICHT auf der neuen Alarm-Auflösung
    `effective_alert_channels` (Briefing- und Alarm-Kanäle müssen getrennt
    bleiben, Spec-Abschnitt "Umbenennung des Briefing-Resolvers")."""
    import services.scheduler_dispatch_service as sds

    def _fake_resolver(preset, settings, user_id):
        return {"sms"}  # bewusst NICHT das Inline-Ergebnis {"email"}

    monkeypatch.setattr(
        sds, "effective_compare_briefing_channels", _fake_resolver, raising=False,
    )

    settings = _sms_capable_settings()
    user_id = f"tdd-ag1-sds-{uuid.uuid4().hex[:8]}"
    preset = {"id": "p-delegation-sds"}  # kein send_telegram/send_sms

    result = sds._effective_compare_briefing_channels(preset, settings, user_id)

    assert result == {"sms"}, (
        "AC-6: der interne Wrapper muss ueber das importierte "
        "Resolver-Symbol effective_compare_briefing_channels delegieren. "
        "Solange scheduler_dispatch_service.py den Aufruf noch inline "
        "kopiert statt zu delegieren, bleibt die Wirkung unveraendert bei "
        f"{{'email'}}. Gemessen: {result!r}."
    )


# ───────────────────── Mandantentrennung (AC-1/AC-2, R4) ────────────────────

def test_sms_gate_is_per_user_never_default(clean_user_dir):
    """Mandantentrennung: `send_sms: true` bei EINEM Nutzer ohne SMS-Tier
    (`sms_allowed()` == False) darf keine SMS ergeben; derselbe Preset-Inhalt
    bei einem ANDEREN, echten Nutzer mit SMS-Tier muss SMS ergeben. Zwei
    verschiedene, echte `user_id`-Werte -- niemals ein stiller Ruecksprung
    auf `"default"`, der beide Nutzer verwaschen wuerde."""
    from services.compare_alert_channels import effective_compare_briefing_channels

    user_free = clean_user_dir(f"tdd-ag1-tier-free-{uuid.uuid4().hex[:8]}")
    user_std = clean_user_dir(f"tdd-ag1-tier-std-{uuid.uuid4().hex[:8]}")
    # user_free bekommt bewusst KEIN user.json -> Default-Tier "free".
    _write_standard_tier_user(user_std)

    settings = _sms_capable_settings()
    preset = {"id": "p-mandant", "send_sms": True}

    result_free = effective_compare_briefing_channels(preset, settings, user_free)
    result_std = effective_compare_briefing_channels(preset, settings, user_std)

    assert user_free != "default" and user_std != "default"
    assert "sms" not in result_free, (
        f"Free-Tier-Nutzer {user_free} darf trotz send_sms=True keine SMS "
        f"bekommen (sms_allowed() muss False liefern). Ergebnis: {result_free!r}."
    )
    assert "sms" in result_std, (
        f"Standard-Tier-Nutzer {user_std} muss bei send_sms=True SMS "
        "bekommen -- Beweis, dass die user_id ECHT durchgereicht wird, "
        f"statt auf 'default' zurueckzufallen. Ergebnis: {result_std!r}."
    )


# ═══════════ AC-6 Waechter — alter Name vollstaendig aus dem Repo ═══════════

def test_retired_briefing_resolver_name_is_fully_gone():  # doc-compliance-test
    """AC-6: der VOR #2279 S1 gueltige Name des Briefing-Resolvers (Praefix
    ``effective_compare_`` + Suffix ``_channels``, OHNE das seither
    eingefuegte ``briefing``) darf nach Abschluss dieser Scheibe an KEINER
    Stelle in `src/` oder `tests/` mehr vorkommen (Spec-Abschnitt
    "Umbenennung des Briefing-Resolvers": er heisst jetzt
    `effective_compare_briefing_channels`). Reiner Repo-Grep -- kein
    Verhaltensnachweis, deshalb ausdruecklich als Doku-Compliance-Test
    markiert (CLAUDE.md-Ausnahme). Pfadregel #1409: die Repo-Wurzel wird
    relativ zu DIESER Testdatei aufgeloest, nie ueber einen festen
    Hauptrepo-Pfad.

    Der gesuchte Name wird bewusst aus zwei Teilen zusammengesetzt (statt als
    ein zusammenhaengendes Literal im Quelltext zu stehen) -- sonst wuerde
    DIESE Testdatei sich selbst als Fund melden, weil ihr eigener Quelltext
    den gesuchten Namen sonst woertlich enthielte."""
    import subprocess
    from pathlib import Path

    retired_name = "effective_compare" + "_channels"
    repo_root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        ["git", "grep", "-n", retired_name, "--", "src", "tests"],
        cwd=repo_root, capture_output=True, text=True,
    )

    assert result.stdout == "", (
        f"AC-6: der abgeloeste Name {retired_name!r} muss vollstaendig "
        "verschwunden sein (umbenannt zu effective_compare_briefing_channels), "
        f"aber noch gefunden:\n{result.stdout}"
    )
