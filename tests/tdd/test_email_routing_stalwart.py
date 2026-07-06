"""
TDD RED — test-email-routing-stalwart
Spec: docs/specs/modules/test_email_routing_stalwart.md

AC-1: for_testing() mit gesetzten GZ_TEST_SMTP_*-Vars → smtp_user + imap_user = "gregor-test"
AC-2: Settings-Objekt hat test_smtp_user-Feld (kein AttributeError)
AC-3: for_testing()-Fallback ohne Creds → nur is_test_mode=True, kein Absturz
"""


class TestForTestingStalwartRouting:

    def test_settings_has_test_smtp_user_field(self):
        """
        AC-2: Settings muss test_smtp_user-Feld haben (ersetzt google_smtp_user).
        GIVEN: frisches Settings-Objekt
        WHEN:  Attribut test_smtp_user abgerufen
        THEN:  kein AttributeError, Wert ist None wenn nicht gesetzt
        """
        from app.config import Settings
        s = Settings()
        # Field must exist — currently it doesn't → AttributeError → RED
        assert hasattr(s, "test_smtp_user"), "Settings fehlt Feld test_smtp_user"
        assert hasattr(s, "test_smtp_pass"), "Settings fehlt Feld test_smtp_pass"
        assert hasattr(s, "test_mail_from"), "Settings fehlt Feld test_mail_from"
        assert hasattr(s, "test_imap_user"), "Settings fehlt Feld test_imap_user"
        assert hasattr(s, "test_imap_pass"), "Settings fehlt Feld test_imap_pass"

    def test_for_testing_sets_smtp_user_from_test_creds(self, monkeypatch):
        """
        AC-1: for_testing() liest GZ_TEST_SMTP_USER und setzt smtp_user.
        GIVEN: GZ_TEST_SMTP_USER=gregor-test, GZ_TEST_SMTP_PASS=testpass gesetzt
        WHEN:  Settings().for_testing() aufgerufen
        THEN:  result.smtp_user == "gregor-test", result.is_test_mode == True
        """
        monkeypatch.setenv("GZ_TEST_SMTP_USER", "gregor-test")
        monkeypatch.setenv("GZ_TEST_SMTP_PASS", "testpass")

        from app.config import Settings
        result = Settings().for_testing()

        assert result.smtp_user == "gregor-test", (
            f"smtp_user sollte 'gregor-test' sein, ist '{result.smtp_user}'"
        )
        assert result.is_test_mode is True

    def test_for_testing_overrides_imap_credentials(self, monkeypatch):
        """
        AC-1: for_testing() setzt auch imap_user + imap_pass auf Test-Credentials.
        GIVEN: GZ_TEST_IMAP_USER=gregor-test, GZ_TEST_IMAP_PASS=testpass gesetzt
        WHEN:  Settings().for_testing() aufgerufen
        THEN:  result.imap_user == "gregor-test", result.imap_pass == "testpass"
        """
        monkeypatch.setenv("GZ_TEST_SMTP_USER", "gregor-test")
        monkeypatch.setenv("GZ_TEST_SMTP_PASS", "testpass")
        monkeypatch.setenv("GZ_TEST_IMAP_USER", "gregor-test")
        monkeypatch.setenv("GZ_TEST_IMAP_PASS", "testpass")

        from app.config import Settings
        result = Settings().for_testing()

        assert result.imap_user == "gregor-test", (
            f"imap_user sollte 'gregor-test' sein, ist '{result.imap_user}'"
        )
        assert result.imap_pass == "testpass"

    def test_for_testing_fallback_without_test_creds(self, monkeypatch):
        """
        AC-3: for_testing() ohne GZ_TEST_SMTP_*-Vars → Fallback, nur is_test_mode=True.
        GIVEN: keine GZ_TEST_SMTP_USER-Env-Var
        WHEN:  Settings().for_testing() aufgerufen
        THEN:  result.is_test_mode == True, kein Absturz
        """
        # Leerer String überschreibt den .env-File-Wert (Env-Var hat Vorrang bei Pydantic)
        monkeypatch.setenv("GZ_TEST_SMTP_USER", "")
        monkeypatch.setenv("GZ_TEST_SMTP_PASS", "")

        from app.config import Settings
        result = Settings().for_testing()

        assert result.is_test_mode is True
        # smtp_user bleibt unverändert (production value)
        assert result.smtp_user == Settings().smtp_user

    def test_google_smtp_fields_removed(self):
        """
        Regression: Die alten google_smtp_*-Felder dürfen nicht mehr existieren.
        GIVEN: frisches Settings-Objekt
        WHEN:  Attribut google_smtp_host abgerufen
        THEN:  AttributeError (Feld entfernt)
        """
        from app.config import Settings
        s = Settings()
        assert not hasattr(s, "google_smtp_host"), (
            "google_smtp_host sollte entfernt sein (durch test_smtp_user ersetzt)"
        )
        assert not hasattr(s, "google_smtp_user"), (
            "google_smtp_user sollte entfernt sein"
        )
