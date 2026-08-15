"""Nutzerlevel-Gates (``src/services/user_tier.py``) — dateibasiert, ohne Netz.

Bestand: ``sms_allowed()`` laesst ``standard`` UND ``premium`` durch (Epic
#1067/#1069). Neu mit #1676 S2a: ``premium_sms_allowed()`` fuer den vierten
Kanal — ausschliesslich ``premium``.

Spec: docs/specs/modules/feat_1676_s2a_premium_sms_versand.md (AC-8, D7)

``premium_sms_allowed`` wird ABSICHTLICH erst in der Testfunktion importiert:
ein Import auf Modulebene wuerde die Datei beim Fehlen der Funktion komplett
abbrechen und damit auch den Bestandsnachweis unten mitreissen.
"""
from __future__ import annotations

import json
import logging

from app.loader import get_data_dir
from services.user_tier import daily_alert_limit, sms_allowed


def _profile(user_id: str, tier: str | None) -> str:
    """Legt ``user.json`` in der (per conftest isolierten) Datenwurzel an."""
    path = get_data_dir(user_id)
    path.mkdir(parents=True, exist_ok=True)
    data: dict = {"id": user_id}
    if tier is not None:
        data["tier"] = tier
    (path / "user.json").write_text(json.dumps(data), encoding="utf-8")
    return user_id


def _corrupt_profile(user_id: str) -> str:
    """Legt eine VORHANDENE, aber inhaltlich kaputte ``user.json`` an (kein
    valides JSON) -- der Fall aus #1596, zu unterscheiden von einer
    tatsaechlich fehlenden Datei."""
    path = get_data_dir(user_id)
    path.mkdir(parents=True, exist_ok=True)
    (path / "user.json").write_text("{not valid json", encoding="utf-8")
    return user_id


def test_sms_allowed_matches_tier_table() -> None:
    """Bestandsverhalten (Regressionsschutz): free nein, standard/premium ja,
    fehlende Datei nein."""
    assert sms_allowed(_profile("tdd-1676-tier-free", "free")) is False
    assert sms_allowed(_profile("tdd-1676-tier-std", "standard")) is True
    assert sms_allowed(_profile("tdd-1676-tier-prem", "premium")) is True
    assert sms_allowed("tdd-1676-tier-nofile") is False


def test_premium_sms_allowed_excludes_standard_tier() -> None:
    """AC-8/D7: Given Tier ``standard`` / When die Premium-SMS-Berechtigung
    geprueft wird / Then False — obwohl derselbe Nutzer fuer den normalen
    SMS-Kanal berechtigt ist. Eine Delegation an ``sms_allowed()`` waere eine
    stille Rechte-Ausweitung."""
    from services.user_tier import premium_sms_allowed

    std = _profile("tdd-1676-psms-std", "standard")
    free = _profile("tdd-1676-psms-free", "free")
    prem = _profile("tdd-1676-psms-prem", "premium")
    no_tier = _profile("tdd-1676-psms-notier", None)

    assert sms_allowed(std) is True, (
        "Voraussetzung: standard darf normale SMS — sonst zeigt der Vergleich unten nichts."
    )
    assert premium_sms_allowed(std) is False, (
        "standard-Tier darf KEINE Premium-SMS ausloesen (Premium-Merkmal, D7)."
    )
    assert premium_sms_allowed(free) is False
    assert premium_sms_allowed(no_tier) is False, (
        "Bestandsnutzer ohne tier-Feld verhaelt sich wie free — kein impliziter "
        "Premium-Zugriff durch ein fehlendes Feld."
    )
    assert premium_sms_allowed("tdd-1676-psms-nofile") is False, (
        "Fehlende user.json darf Premium-SMS nicht versehentlich erlauben."
    )
    assert premium_sms_allowed(prem) is True, (
        "premium-Tier muss Premium-SMS erlauben — sonst ist der Kanal generell tot."
    )


def test_corrupt_user_json_logs_warning_but_missing_file_stays_quiet(caplog) -> None:
    """AC-2 + AC-4-Abgrenzung (#1596): eine VORHANDENE, aber kaputte
    ``user.json`` muss fuer alle drei Tier-Funktionen eine Warnung loggen
    (Pfad/Ursache), OHNE den Rueckgabewert zu aendern -- insbesondere bleibt
    ``premium_sms_allowed`` fail-closed (#1676 S2a AC-8/D7). Eine
    tatsaechlich FEHLENDE ``user.json`` (legitimer Normalfall) bleibt
    weiterhin still."""
    from services.user_tier import premium_sms_allowed

    corrupt_id = _corrupt_profile("tdd-1596-tier-corrupt")

    with caplog.at_level(logging.WARNING):
        caplog.clear()
        assert sms_allowed(corrupt_id) is False, "Rueckgabewert darf sich durch das Logging nicht aendern"
        assert premium_sms_allowed(corrupt_id) is False, (
            "premium_sms_allowed muss bei kaputter Datei fail-closed bleiben (#1676)"
        )
        assert daily_alert_limit(corrupt_id) == 2, "free-Default-Limit darf sich nicht aendern"

    assert corrupt_id in caplog.text, (
        f"AC-2: kaputte user.json muss eine Warnung mit der User-ID loggen, "
        f"Log-Ausgabe war: {caplog.text!r}"
    )

    missing_id = "tdd-1596-tier-missing"
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        assert sms_allowed(missing_id) is False
        assert premium_sms_allowed(missing_id) is False
        assert daily_alert_limit(missing_id) == 2

    assert missing_id not in caplog.text, (
        f"AC-4: eine tatsaechlich fehlende user.json ist der legitime Normalfall "
        f"und darf NICHT geloggt werden, Log-Ausgabe war: {caplog.text!r}"
    )
