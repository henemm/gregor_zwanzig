"""
TDD RED tests for Issue #645 — OutputError in telegram.py mit korrekter Arität.

Vor dem Fix konstruiert telegram.py OutputError mit nur einem Argument →
TypeError statt sauberem OutputError. Diese Tests beweisen das Verhalten aus
Aufrufer-Perspektive: ein fehlschlagender Send muss einen OutputError
(channel="telegram", Präfix "[telegram]") werfen — niemals einen TypeError.

MOCK-FREI: echter HTTP-Call gegen die Telegram-API mit ungültigem Bot-Token.
Die API antwortet real mit HTTP 404 (Status != 200) → realer Fehlerpfad.

Spec: docs/specs/modules/bug_645_telegram_outputerror_arity.md
Test-Spec: docs/specs/tests/issue_645_telegram_outputerror_arity_tests.md
GitHub Issue: #645
"""
import re

import pytest

from app.config import Settings
from output.channels.base import OutputError
from output.channels.telegram import TelegramOutput

_INVALID = Settings(
    telegram_bot_token="000000:INVALID-TOKEN-issue-645",
    telegram_chat_id="12345",
)


# =============================================================================
# AC-1: HTTP-Status != 200 → sauberer OutputError, kein TypeError
# =============================================================================


# Dialt real (Telegram-API) -- #1211 Scheibe 2b Batch 3, nur via Marker ausfuehren.
@pytest.mark.live
def test_non_200_raises_outputerror_not_typeerror():
    """
    GIVEN: ausgehender Telegram-Send mit ungültigem Bot-Token
    WHEN: send() aufgerufen wird (echter API-Call → HTTP 404)
    THEN: ein OutputError (KEIN TypeError) wird geworfen
    """
    output = TelegramOutput(_INVALID)

    # pytest.raises(OutputError) fängt einen TypeError NICHT ab →
    # vor dem Fix schlägt der Test mit dem rohen TypeError fehl (RED).
    with pytest.raises(OutputError) as exc_info:
        output.send("Test #645", "Body")

    assert exc_info.value.channel == "telegram"
    assert str(exc_info.value).startswith("[telegram]")


# Dialt real (Telegram-API) -- #1211 Scheibe 2b Batch 3, nur via Marker ausfuehren.
@pytest.mark.live
def test_non_200_message_contains_status_code():
    """
    GIVEN: ungültiger Bot-Token → reale Fehler-Antwort (HTTP 4xx)
    WHEN: send() fehlschlägt
    THEN: die OutputError-Meldung enthält den realen HTTP-Statuscode.

    Statuscode-agnostisch: die reale Telegram-API antwortet bei ungültigem
    Token mit 401 (Unauthorized); andere Token-/Chat-Fehler liefern 4xx.
    Geprüft wird, dass der tatsächliche Code in der Meldung steht — nicht ein
    hart kodierter Wert.
    """
    output = TelegramOutput(_INVALID)

    with pytest.raises(OutputError) as exc_info:
        output.send("Test #645", "Body")

    msg = str(exc_info.value)
    assert "status" in msg
    assert re.search(r"\b\d{3}\b", msg), f"kein HTTP-Statuscode in Meldung: {msg!r}"


# =============================================================================
# AC-2: httpx.HTTPError-Pfad → sauberer OutputError, kein TypeError
# =============================================================================


def test_http_error_path_raises_clean_outputerror(monkeypatch):
    """
    GIVEN: ein ausgehender Send, dessen HTTP-Verbindung real fehlschlägt
    WHEN: send() den Telegram-Endpoint kontaktiert
    THEN: ein OutputError (KEIN TypeError) mit channel="telegram" wird geworfen.

    MOCK-FREI: Die API-Basis wird auf eine garantiert nicht erreichbare Adresse
    (127.0.0.1:1 → Connection refused) umgelenkt. httpx führt einen ECHTEN
    Verbindungsversuch durch und wirft eine reale httpx.ConnectError (Subklasse
    von httpx.HTTPError) — kein Mock, kein patch der Sende-Logik. Deckt den
    dritten raise-Pfad (Z. 60) ab (AC-2/AC-3).
    """
    import output.channels.telegram as telegram_mod

    monkeypatch.setattr(telegram_mod, "TELEGRAM_API_BASE", "http://127.0.0.1:1")
    output = TelegramOutput(_INVALID)

    with pytest.raises(OutputError) as exc_info:
        output.send("Test #645", "Body")

    assert exc_info.value.channel == "telegram"
    assert str(exc_info.value).startswith("[telegram]")
