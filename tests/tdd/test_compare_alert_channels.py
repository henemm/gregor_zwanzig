"""TDD RED — Issue #1467 Scheibe S2, Arbeitsgang AG1: Kanal-Ermittlung fuer
Ortsvergleich-Aenderungsalarme wird auf EINEN gemeinsamen Resolver gezogen.

Ist-Stand (vor dieser Aenderung): Der Compare-Kanal-Resolver existiert
funktional identisch an zwei Stellen —
`compare_official_alert.py::CompareOfficialAlertService._effective_channels`
und `scheduler_dispatch_service.py::_effective_compare_channels`. AG1 zieht
beides in ein neues Modul `src/services/compare_alert_channels.py`
(`effective_compare_channels(preset, settings, user_id)`); beide
Bestandsstellen delegieren dorthin, Verhalten bleibt exakt gleich.

Regel (unveraendert): E-Mail immer aktiv; Telegram nur bei
`preset.get("send_telegram")` UND `settings.can_send_telegram()`; SMS nur
bei `preset.get("send_sms")` UND `settings.can_send_sms()` UND
`sms_allowed(user_id)`. Gelesen wird aus dem Preset-Rohdict, ein fehlender
Schluessel darf NIE als "an" gelten (Risiko R4 der Spec).

RED-Ursache:
- `services.compare_alert_channels` existiert noch nicht -> ImportError
  (AC-1, AC-2 der beiden reinen Wirkungstests).
- `compare_official_alert.py` und `scheduler_dispatch_service.py` haben noch
  KEINE delegierende Kopplung an ein importiertes Resolver-Symbol namens
  `effective_compare_channels` -- die Verdrahtungsnachweis-Tests (AC-3a/AC-3b)
  patchen genau dieses (noch nicht vorhandene) Symbol im VERBRAUCHENDEN Modul
  und beweisen damit ueber eine Verhaltensaenderung, dass echte Delegation
  fehlt, solange die Inline-Kopie stehen bleibt.

Testpolitik (CLAUDE.md): kein Mock-Theater. `monkeypatch` wird ausschliesslich
fuer den Verdrahtungsnachweis (AC-3a/AC-3b) eingesetzt und setzt am
VERBRAUCHENDEN Modul an (`compare_official_alert`/`scheduler_dispatch_service`),
nicht am (noch nicht existierenden) Definitionsort -- sonst waere der Patch
wirkungslos als Beweis. Alle anderen Tests laufen gegen echte Funktionen und
echte Dict-/Settings-Fixturen, keine echten Versaende (kein SMTP, kein
Telegram-Netz, kein IMAP). Reine Kern-Schicht, offline, ohne Marker
`email`/`live`/`staging`.

SPEC: docs/specs/modules/rework_1467_s2_aenderungsalarm.md (AG1: AC-1..AC-3)

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
    -> der gemeinsame Resolver liefert `{"email", "telegram"}` (E-Mail bleibt
    immer aktiv, Telegram kommt bei erfuelltem Opt-in UND globaler Faehigkeit
    hinzu). Direkter Aufruf des neuen Bausteins."""
    from services.compare_alert_channels import effective_compare_channels

    settings = _telegram_capable_settings()
    user_id = f"tdd-ag1-ac1-{uuid.uuid4().hex[:8]}"
    preset = {"id": "p-ac1", "send_telegram": True}

    result = effective_compare_channels(preset, settings, user_id)

    assert result == {"email", "telegram"}, (
        "AC-1: E-Mail muss immer aktiv sein, send_telegram=True + "
        f"telegramfaehige Settings muessen 'telegram' ergaenzen. "
        f"Ergebnis: {result!r}."
    )


# ───────────────────────── AC-2 — Wirkung, negative Seite (R4) ──────────────

def test_ac2_missing_send_telegram_key_never_activates_telegram():
    """AC-2/R4: Fehlt der Schluessel `send_telegram` GANZ im Preset-Dict
    (nicht `False`, sondern gar nicht vorhanden), darf der Resolver Telegram
    NIE aktivieren -- selbst wenn die Konto-Settings telegramfaehig sind."""
    from services.compare_alert_channels import effective_compare_channels

    settings = _telegram_capable_settings()
    user_id = f"tdd-ag1-ac2-tg-{uuid.uuid4().hex[:8]}"
    preset = {"id": "p-ac2-tg"}  # send_telegram fehlt komplett

    result = effective_compare_channels(preset, settings, user_id)

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
    from services.compare_alert_channels import effective_compare_channels

    user_id = clean_user_dir(f"tdd-ag1-ac2-sms-{uuid.uuid4().hex[:8]}")
    _write_standard_tier_user(user_id)
    settings = _sms_capable_settings()
    preset = {"id": "p-ac2-sms"}  # send_sms fehlt komplett

    result = effective_compare_channels(preset, settings, user_id)

    assert "sms" not in result, (
        "AC-2/R4: ein FEHLENDER send_sms-Schluessel darf niemals als Opt-in "
        f"gelten, auch nicht bei SMS-faehigem Tier. Ergebnis: {result!r}."
    )
    assert result == {"email"}


# ───────────────── AC-3a — Verdrahtungsnachweis compare_official_alert ──────

def test_ac3a_compare_official_alert_delegates_to_shared_resolver(monkeypatch):
    """AC-3a: `CompareOfficialAlertService._effective_channels` muss ueber
    das im Modul `compare_official_alert` importierte Resolver-Symbol
    `effective_compare_channels` laufen -- nicht ueber eine eigene Inline-
    Kopie. Beweis: Wir ersetzen genau dieses Symbol im VERBRAUCHENDEN Modul
    durch eine Fassung mit einem erkennbar abweichenden Kanalsatz. Ein Preset
    OHNE jedes Opt-in wuerde inline `{"email"}` ergeben -- liefert der Aufruf
    stattdessen den gepatchten Satz, ist die Delegation bewiesen. Laeuft die
    Methode noch ueber ihre eigene Inline-Kopie, bleibt das Ergebnis bei
    `{"email"}` haengen und der Test faellt durch (RED = fehlende
    Delegation, kein Sammel-Fehler)."""
    import services.compare_official_alert as coa

    def _fake_resolver(preset, settings, user_id):
        return {"telegram"}  # bewusst NICHT das Inline-Ergebnis {"email"}

    monkeypatch.setattr(coa, "effective_compare_channels", _fake_resolver, raising=False)

    settings = _telegram_capable_settings()
    user_id = f"tdd-ag1-coa-{uuid.uuid4().hex[:8]}"
    svc = coa.CompareOfficialAlertService(settings=settings, user_id=user_id)
    preset = {"id": "p-delegation-coa"}  # kein send_telegram/send_sms

    result = svc._effective_channels(preset)

    assert result == {"telegram"}, (
        "AC-3a: _effective_channels muss ueber das importierte Resolver-"
        "Symbol delegieren. Solange compare_official_alert.py noch die "
        "Inline-Kopie benutzt, bleibt die Wirkung unveraendert bei "
        f"{{'email'}} statt beim gepatchten Ergebnis. Gemessen: {result!r}."
    )


# ─────────────── AC-3b — Verdrahtungsnachweis scheduler_dispatch_service ────

def test_ac3b_scheduler_dispatch_delegates_to_shared_resolver(monkeypatch):
    """AC-3b: Dasselbe Muster fuer `scheduler_dispatch_service._effective_compare_channels`
    -- Patch am VERBRAUCHENDEN Modul, nicht am Definitionsort. Solange die
    Funktion noch ihre eigene Inline-Logik ausfuehrt, bleibt die Wirkung
    unveraendert und der Test faellt durch."""
    import services.scheduler_dispatch_service as sds

    def _fake_resolver(preset, settings, user_id):
        return {"sms"}  # bewusst NICHT das Inline-Ergebnis {"email"}

    monkeypatch.setattr(sds, "effective_compare_channels", _fake_resolver, raising=False)

    settings = _sms_capable_settings()
    user_id = f"tdd-ag1-sds-{uuid.uuid4().hex[:8]}"
    preset = {"id": "p-delegation-sds"}  # kein send_telegram/send_sms

    result = sds._effective_compare_channels(preset, settings, user_id)

    assert result == {"sms"}, (
        "AC-3b: _effective_compare_channels muss ueber das importierte "
        "Resolver-Symbol delegieren. Solange scheduler_dispatch_service.py "
        "noch die Inline-Kopie benutzt, bleibt die Wirkung unveraendert bei "
        f"{{'email'}} statt beim gepatchten Ergebnis. Gemessen: {result!r}."
    )


# ───────────────────── Mandantentrennung (AC-1/AC-2, R4) ────────────────────

def test_sms_gate_is_per_user_never_default(clean_user_dir):
    """Mandantentrennung: `send_sms: true` bei EINEM Nutzer ohne SMS-Tier
    (`sms_allowed()` == False) darf keine SMS ergeben; derselbe Preset-Inhalt
    bei einem ANDEREN, echten Nutzer mit SMS-Tier muss SMS ergeben. Zwei
    verschiedene, echte `user_id`-Werte -- niemals ein stiller Ruecksprung
    auf `"default"`, der beide Nutzer verwaschen wuerde."""
    from services.compare_alert_channels import effective_compare_channels

    user_free = clean_user_dir(f"tdd-ag1-tier-free-{uuid.uuid4().hex[:8]}")
    user_std = clean_user_dir(f"tdd-ag1-tier-std-{uuid.uuid4().hex[:8]}")
    # user_free bekommt bewusst KEIN user.json -> Default-Tier "free".
    _write_standard_tier_user(user_std)

    settings = _sms_capable_settings()
    preset = {"id": "p-mandant", "send_sms": True}

    result_free = effective_compare_channels(preset, settings, user_free)
    result_std = effective_compare_channels(preset, settings, user_std)

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
