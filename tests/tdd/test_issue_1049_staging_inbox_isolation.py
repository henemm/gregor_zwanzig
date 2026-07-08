"""
TDD RED für Issue #1049: Prod und Staging teilen sich die Inbound-Mail-Inbox.

KEINE Mocks — liest die echten, live auf dem Server liegenden .env-Dateien von
Prod und Staging (beide Instanzen laufen auf demselben Hetzner-Host) und prüft
den tatsächlichen, aktuellen Konfigurationszustand. Vor dem Fix sind
GZ_INBOUND_ADDRESS/GZ_IMAP_USER auf beiden Seiten identisch (der eigentliche
Bug) — dieser Test muss deshalb JETZT fehlschlagen (RED) und erst nach der
Stalwart-Postfach-Trennung + Staging-.env-Umstellung grün werden.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

PROD_ENV_PATH = Path("/home/hem/gregor_zwanzig/.env")
STAGING_ENV_PATH = Path("/home/hem/gregor_zwanzig_staging/.env")

# Opt-in wie bei allen Live-/Infra-Tests (Muster: GZ_TELEGRAM_LIVE, Issue #1014):
# ohne explizites Opt-in wird übersprungen, damit normale `pytest`-Läufe auf
# diesem Host nicht rot werden, solange die #1049-Postfach-Trennung (externe
# Stalwart-Aktion) noch nicht abgeschlossen ist.
_LIVE_OPT_IN = os.environ.get("GZ_STAGING_INFRA_LIVE") == "1"


def _read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"')
    return values


@pytest.mark.skipif(
    not (_LIVE_OPT_IN and PROD_ENV_PATH.exists() and STAGING_ENV_PATH.exists()),
    reason="GZ_STAGING_INFRA_LIVE=1 nicht gesetzt oder Prod-/Staging-.env nicht auf diesem Host vorhanden",
)
def test_staging_inbound_address_isolated_from_prod():
    """Given Prod und Staging .env / When GZ_INBOUND_ADDRESS verglichen wird / Then unterschiedlich."""
    prod = _read_env(PROD_ENV_PATH)
    staging = _read_env(STAGING_ENV_PATH)

    prod_address = prod.get("GZ_INBOUND_ADDRESS")
    staging_address = staging.get("GZ_INBOUND_ADDRESS")

    assert prod_address, "Prod GZ_INBOUND_ADDRESS ist leer/fehlt"
    assert staging_address, "Staging GZ_INBOUND_ADDRESS ist leer/fehlt"
    assert staging_address != prod_address, (
        f"Staging und Prod teilen sich dieselbe Inbound-Adresse ({staging_address}) — "
        "genau der in #1049 gemeldete Bug. Nach dem Fix muss Staging ein eigenes "
        "Postfach (gregor-staging@henemm.com) verwenden."
    )


@pytest.mark.skipif(
    not (_LIVE_OPT_IN and PROD_ENV_PATH.exists() and STAGING_ENV_PATH.exists()),
    reason="GZ_STAGING_INFRA_LIVE=1 nicht gesetzt oder Prod-/Staging-.env nicht auf diesem Host vorhanden",
)
def test_staging_imap_user_isolated_from_prod():
    """Given Prod und Staging .env / When GZ_IMAP_USER verglichen wird / Then unterschiedlich."""
    prod = _read_env(PROD_ENV_PATH)
    staging = _read_env(STAGING_ENV_PATH)

    prod_user = prod.get("GZ_IMAP_USER")
    staging_user = staging.get("GZ_IMAP_USER")

    assert prod_user, "Prod GZ_IMAP_USER ist leer/fehlt"
    assert staging_user, "Staging GZ_IMAP_USER ist leer/fehlt"
    assert staging_user != prod_user, (
        f"Staging und Prod nutzen denselben IMAP-User ({staging_user}) — beide Cron-Jobs "
        "(inbound_command_poll, */5min) lesen dieselbe Mailbox und konkurrieren um dieselben "
        "UNSEEN-Mails. Nach dem Fix muss Staging einen eigenen IMAP-User (gregor-staging) haben."
    )
