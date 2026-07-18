"""
TDD RED — Issue #608: SMS-Kanal via seven.io

SPEC: docs/specs/modules/issue_608_sms_seven_io.md

Alle Tests schlagen fehl, solange src/outputs/sms.py nicht existiert.
Nach Implementierung:
  - AC-2/AC-3: bestehen ohne Credentials
  - AC-1/AC-4: benötigen SMS_API_KEY + SMS_TO in .env
  - AC-5: sendet mit absichtlich falschem Key → echter 401 von seven.io
"""
import pytest

from app.config import Settings
from output.channels.base import OutputChannel, OutputConfigError, OutputError, get_channel


def _settings_with_sms(**overrides) -> Settings:
    """Erstellt Settings mit minimalem SMS-Konfiguration."""
    defaults = {
        "sms_gateway_url": "https://gateway.seven.io/api/sms",
        "seven_api_key": "test-key",
        "sms_to": "+49000000000",
    }
    defaults.update(overrides)
    return Settings(**defaults, _env_file=None)


def _settings_from_env() -> Settings:
    """Lädt echte Credentials aus .env für Live-Tests."""
    return Settings()


# ---------------------------------------------------------------------------
# AC-3: get_channel("sms") darf keinen ModuleNotFoundError werfen
# ---------------------------------------------------------------------------

class TestGetChannelSms:

    def test_get_channel_sms_no_import_error(self):
        """
        GIVEN: channel="sms" und vollständige Config
        WHEN: get_channel("sms", settings) aufgerufen wird
        THEN: Kein ModuleNotFoundError — SMSOutput wird erfolgreich importiert
        """
        settings = _settings_with_sms()
        channel = get_channel("sms", settings)
        assert channel is not None

    def test_get_channel_sms_implements_protocol(self):
        """
        GIVEN: channel="sms" und vollständige Config
        WHEN: get_channel("sms", settings) aufgerufen wird
        THEN: Das Objekt implementiert das OutputChannel-Protocol (name + send)
        """
        settings = _settings_with_sms()
        channel = get_channel("sms", settings)
        assert isinstance(channel, OutputChannel)

    def test_sms_channel_name(self):
        """SMSOutput.name gibt 'sms' zurück."""
        from output.channels.sms import SMSOutput
        output = SMSOutput(_settings_with_sms())
        assert output.name == "sms"


# ---------------------------------------------------------------------------
# AC-2: Fehlende Config → OutputConfigError vor HTTP-Call
# ---------------------------------------------------------------------------

class TestSmsConfigValidation:

    def test_missing_api_key_raises_config_error(self):
        """
        GIVEN: seven_api_key fehlt
        WHEN: SMSOutput(settings) instanziiert wird
        THEN: OutputConfigError geworfen, kein HTTP-Request
        """
        from output.channels.sms import SMSOutput
        settings = _settings_with_sms(seven_api_key=None)
        with pytest.raises(OutputConfigError):
            SMSOutput(settings)

    def test_missing_sms_to_raises_config_error(self):
        """
        GIVEN: sms_to fehlt
        WHEN: SMSOutput(settings) instanziiert wird
        THEN: OutputConfigError geworfen, kein HTTP-Request
        """
        from output.channels.sms import SMSOutput
        settings = _settings_with_sms(sms_to=None)
        with pytest.raises(OutputConfigError):
            SMSOutput(settings)


# ---------------------------------------------------------------------------
# AC-5: Fehler-Antwort von seven.io → OutputError (echter HTTP-Call mit Fake-Key)
# ---------------------------------------------------------------------------

class TestSmsErrorHandling:

    # Dialt real (seven.io) -- #1211 Scheibe 2b Batch 3, nur via Marker ausfuehren.
    @pytest.mark.live
    def test_invalid_api_key_raises_output_error(self):
        """
        GIVEN: Ungültiger API-Key (echter HTTP-Call, echter 401 von seven.io)
        WHEN: send() aufgerufen wird
        THEN: OutputError geworfen — kein stilles Ignorieren des Fehlers

        Kein Mock — seven.io liefert echten Fehler bei ungültigem Key.
        """
        from output.channels.sms import SMSOutput
        settings = _settings_with_sms(seven_api_key="invalid-fake-key-for-test")
        output = SMSOutput(settings)
        with pytest.raises(OutputError):
            output.send("test", "Gregor Zwanzig Test")


# ---------------------------------------------------------------------------
# AC-4: Fehlendes sms_from → SMS trotzdem erfolgreich
# AC-1: Echter Versand mit echten Credentials → SMS kommt an
#
# Diese Tests benötigen SMS_API_KEY + SMS_TO in .env.
# Ohne Credentials: pytest.fail mit klarer Meldung (kein Mock-Fallback).
# ---------------------------------------------------------------------------

class TestSmsLiveDelivery:

    def _require_live_credentials(self):
        """Bricht Test ab wenn keine echten Credentials vorhanden."""
        settings = _settings_from_env()
        if not settings.can_send_sms():
            pytest.skip(
                "Live-Test benötigt SMS_API_KEY + SMS_TO in .env "
                "(seven.io Credentials). Eintragen und Test erneut ausführen."
            )
        return settings

    def test_ac1_real_sms_delivery(self):
        """
        AC-1: Echter Versand — SMS kommt auf Zielrufnummer an.

        GIVEN: Vollständige seven.io-Konfiguration in .env
        WHEN: send() mit gültigem ≤160-Zeichen-Text aufgerufen wird
        THEN: seven.io antwortet HTTP 200 + Body "100" (kein Exception)
        """
        from output.channels.sms import SMSOutput
        settings = self._require_live_credentials()
        output = SMSOutput(settings)
        # Kein Exception = Erfolg (seven.io hat "100" zurückgegeben)
        output.send("GZ Test", "Gregor Zwanzig SMS-Test #608 — bitte ignorieren")

    def test_ac4_send_without_sms_from(self):
        """
        AC-4: Versand ohne Absender-Name — SMS trotzdem zugestellt.

        GIVEN: sms_from ist leer, aber seven_api_key + sms_to vorhanden
        WHEN: send() aufgerufen wird
        THEN: Kein Exception — seven.io wählt Standard-Absender
        """
        from output.channels.sms import SMSOutput
        settings = self._require_live_credentials()
        settings_no_from = settings.model_copy(update={"sms_from": None})
        output = SMSOutput(settings_no_from)
        output.send("GZ Test", "Gregor Zwanzig Test ohne Absender #608")
