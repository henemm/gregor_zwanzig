"""Issue #2144: ``Settings.with_user_profile()`` darf bei fehlendem Profilfeld
NICHT still auf den globalen ``.env``-Wert (Betreiber-Adresse) zurueckfallen.

Spec: docs/specs/bugfix/user_recipient_fallback.md, AC-2 und AC-3.

Kernursache (Kontext-Datei fix-2144-mail-to-fallback.md): ``with_user_profile()``
ueberschreibt ``mail_to``/``telegram_chat_id``/``sms_to`` in ``overrides`` NUR,
wenn das Profil den Wert traegt (``if profile.get("mail_to"): ...``) -- fehlt er,
bleibt der globale ``.env``-Wert aus ``base``/``self`` unveraendert stehen. Das
ist die Cross-Tenant-Zustellung: ein Nutzer ohne eigenes ``mail_to`` bekaeme sein
Briefing an die Betreiber-Adresse zugestellt.

Muss FEHLSCHLAGEN bis implementiert: aktuell liefert ``with_user_profile()`` bei
fehlendem Profilfeld weiterhin ``self.mail_to``/``self.sms_to``/
``self.telegram_chat_id`` (den globalen Wert), nicht ``None``.
"""
from __future__ import annotations

import json

from app.config import Settings
from app.loader import get_data_dir

OPERATOR_MAIL = "betreiber@henemm.com"
OPERATOR_SMS = "+491700000000"
OPERATOR_TELEGRAM_CHAT = "operator-chat-id"


def _write_profile(user_id: str, profile: dict) -> None:
    path = get_data_dir(user_id)
    path.mkdir(parents=True, exist_ok=True)
    (path / "user.json").write_text(json.dumps(profile), encoding="utf-8")


# ---------------------------------------------------------------------------
# AC-2: mail_to/sms_to duerfen NIE auf den globalen Wert zurueckfallen
# ---------------------------------------------------------------------------


def test_with_user_profile_returns_none_not_global_mail_to(monkeypatch):
    """AC-2 GIVEN ein Profil ohne ``mail_to``, ``GZ_MAIL_TO`` zeigt auf die
    Betreiber-Adresse / WHEN ``with_user_profile()`` laeuft / THEN ist
    ``mail_to`` am Ergebnis ``None`` -- nicht die Betreiber-Adresse."""
    monkeypatch.setenv("GZ_MAIL_TO", OPERATOR_MAIL)
    user_id = "no-mail-to-profile"
    _write_profile(user_id, {"id": user_id})

    settings = Settings().with_user_profile(user_id)

    assert settings.mail_to is None, (
        f"BUG #2144: mail_to ist {settings.mail_to!r} -- ein Nutzer ohne "
        "eigenes mail_to darf NICHT an die Betreiber-Adresse zugestellt "
        "werden (Cross-Tenant-Leck)."
    )


def test_with_user_profile_returns_none_not_global_sms_to(monkeypatch):
    """AC-2 (SMS-Analogon) GIVEN ein Profil ohne ``sms_to``, ``GZ_SMS_TO``
    zeigt auf die Betreiber-Nummer / WHEN ``with_user_profile()`` laeuft /
    THEN ist ``sms_to`` am Ergebnis ``None``."""
    monkeypatch.setenv("GZ_SMS_TO", OPERATOR_SMS)
    user_id = "no-sms-to-profile"
    _write_profile(user_id, {"id": user_id})

    settings = Settings().with_user_profile(user_id)

    assert settings.sms_to is None, (
        f"BUG #2144: sms_to ist {settings.sms_to!r} -- Fallback auf die "
        "Betreiber-Nummer statt eines sauberen Abbruchs."
    )


def test_with_user_profile_still_takes_over_present_mail_to(monkeypatch):
    """Gegenprobe zu AC-2: ein GESETZTES Profil-``mail_to`` muss weiterhin
    ankommen -- sonst waere die vorige Assertion nur ein generell
    zerstoertes Feld, kein korrigierter Fallback."""
    monkeypatch.setenv("GZ_MAIL_TO", OPERATOR_MAIL)
    user_id = "with-mail-to-profile"
    own_mail = "eigene-adresse@example.com"
    _write_profile(user_id, {"id": user_id, "mail_to": own_mail})

    settings = Settings().with_user_profile(user_id)

    assert settings.mail_to == own_mail, (
        f"Gegenprobe fehlgeschlagen: erwartet {own_mail!r}, bekommen "
        f"{settings.mail_to!r} -- with_user_profile() darf ein vorhandenes "
        "Profil-mail_to nicht verlieren."
    )


# ---------------------------------------------------------------------------
# AC-3: telegram_chat_id -- Normal-Nutzer vs. Test-/Staging-Nutzer
# ---------------------------------------------------------------------------


def test_with_user_profile_returns_none_telegram_chat_id_for_normal_user(monkeypatch):
    """AC-3 (Fall 1) GIVEN ein Profil ohne ``telegram_chat_id``, ``force_test``
    ist INAKTIV (Normal-Nutzer-ID, kein Test-/Staging-Kontext), ``GZ_TELEGRAM_
    CHAT_ID`` zeigt auf den Betreiber-Chat / WHEN ``with_user_profile()``
    laeuft / THEN ist ``telegram_chat_id`` am Ergebnis ``None``."""
    monkeypatch.setenv("GZ_TELEGRAM_CHAT_ID", OPERATOR_TELEGRAM_CHAT)
    user_id = "normal-user-no-telegram"
    assert "test" not in user_id and "tdd" not in user_id, (
        "Testaufbau defekt: user_id darf force_test nicht ueber die "
        "Namens-Heuristik ausloesen."
    )
    _write_profile(user_id, {"id": user_id})

    settings = Settings().with_user_profile(user_id)

    assert settings.telegram_chat_id in (None, ""), (
        f"BUG #2144: telegram_chat_id ist {settings.telegram_chat_id!r} -- "
        "ein Normal-Nutzer ohne eigene Chat-ID darf nicht an den "
        "Betreiber-Chat zugestellt werden."
    )


def test_with_user_profile_keeps_force_test_chat_id_for_test_user(monkeypatch):
    """AC-3 (Fall 2) GIVEN dieselbe Lage, aber der Nutzer ist ein
    Test-/Staging-Nutzer (``force_test`` aktiv ueber die Namens-Heuristik
    ``is_test_user_id``) / WHEN ``with_user_profile()`` laeuft / THEN bleibt
    der bestehende force_test-Sonderfall UNVERAENDERT: die Chat-ID kommt
    ausschliesslich aus ``for_testing()`` (``GZ_TELEGRAM_TEST_CHAT_ID``),
    unabhaengig vom (hier fehlenden) Profilinhalt."""
    test_chat_id = "test-chat-id-4711"
    monkeypatch.setenv("GZ_TELEGRAM_CHAT_ID", OPERATOR_TELEGRAM_CHAT)
    monkeypatch.setenv("GZ_TELEGRAM_TEST_CHAT_ID", test_chat_id)
    user_id = "tdd-2144-force-test-user"
    _write_profile(user_id, {"id": user_id})

    settings = Settings().with_user_profile(user_id)

    assert settings.telegram_chat_id == test_chat_id, (
        f"Regression: force_test-Sonderfall veraendert -- erwartet die "
        f"Test-Chat-ID {test_chat_id!r}, bekommen "
        f"{settings.telegram_chat_id!r}."
    )
