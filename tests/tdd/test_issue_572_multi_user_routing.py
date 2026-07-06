"""
TDD RED Tests — Issue #572: Multi-User Inbound-Routing.

Testet:
  - list_all_user_ids()        → alle echten User auflisten
  - lookup_user_by_email()     → User per mail_to finden
  - lookup_user_by_telegram_chat_id() → User per chat_id finden
  - InboundEmailReader: User-scoped Settings bei bekanntem Absender
  - InboundTelegramReader: User-scoped Settings bei bekannter Chat-ID

Diese Tests MÜSSEN fehlschlagen bis die Implementierung vorhanden ist.
Spec: docs/specs/modules/issue_572_multi_user_inbound_routing.md
"""
from __future__ import annotations

import json
from pathlib import Path



# ---------------------------------------------------------------------------
# Hilfs-Fixture: temporäre data/users/-Struktur
# ---------------------------------------------------------------------------

def _write_user_profile(users_root: Path, user_id: str, profile: dict) -> None:
    user_dir = users_root / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    (user_dir / "user.json").write_text(json.dumps(profile), encoding="utf-8")


# ===========================================================================
# AC-5: list_all_user_ids() schließt Test-User aus
# ===========================================================================

class TestListAllUserIds:
    def test_returns_real_users_only(self, tmp_path: Path):
        """
        GIVEN: data/users/ mit echten Usern, test_-Usern und _-Usern
        WHEN: list_all_user_ids() aufgerufen wird
        THEN: Nur echte User (default, henning) werden zurückgegeben
        """
        from app.loader import list_all_user_ids  # ImportError erwartet → RED

        users_root = tmp_path / "users"
        _write_user_profile(users_root, "default", {"mail_to": "a@example.com"})
        _write_user_profile(users_root, "henning", {"mail_to": "h@example.com"})
        _write_user_profile(users_root, "test_abc123", {"mail_to": "t@example.com"})
        _write_user_profile(users_root, "__internal__", {"mail_to": "i@example.com"})

        result = list_all_user_ids(data_dir=str(tmp_path))

        assert "default" in result
        assert "henning" in result
        assert "test_abc123" not in result
        assert "__internal__" not in result

    def test_empty_data_dir_returns_empty_list(self, tmp_path: Path):
        """
        GIVEN: data/users/ existiert nicht
        WHEN: list_all_user_ids() aufgerufen wird
        THEN: Leere Liste zurückgegeben, kein Fehler
        """
        from app.loader import list_all_user_ids  # ImportError erwartet → RED

        result = list_all_user_ids(data_dir=str(tmp_path))
        assert result == []

    def test_returns_list_not_generator(self, tmp_path: Path):
        """
        GIVEN: data/users/ mit einem User
        WHEN: list_all_user_ids() aufgerufen wird
        THEN: Ergebnis ist eine Liste (nicht Generator)
        """
        from app.loader import list_all_user_ids  # ImportError erwartet → RED

        users_root = tmp_path / "users"
        _write_user_profile(users_root, "default", {})

        result = list_all_user_ids(data_dir=str(tmp_path))
        assert isinstance(result, list)


# ===========================================================================
# AC-1 + AC-6: lookup_user_by_email()
# ===========================================================================

class TestLookupUserByEmail:
    def test_finds_user_by_exact_email(self, tmp_path: Path):
        """
        GIVEN: Zwei User-Profile, henning hat mail_to=henning@example.com
        WHEN: lookup_user_by_email("henning@example.com") aufgerufen wird
        THEN: Gibt "henning" zurück
        """
        from app.loader import lookup_user_by_email  # ImportError erwartet → RED

        users_root = tmp_path / "users"
        _write_user_profile(users_root, "default", {"mail_to": "other@example.com"})
        _write_user_profile(users_root, "henning", {"mail_to": "henning@example.com"})

        result = lookup_user_by_email("henning@example.com", data_dir=str(tmp_path))
        assert result == "henning"

    def test_case_insensitive_match(self, tmp_path: Path):
        """
        GIVEN: User-Profil mit mail_to=Henning@Example.COM
        WHEN: lookup_user_by_email("henning@example.com") aufgerufen wird (Kleinschreibung)
        THEN: User wird gefunden (case-insensitiv)
        """
        from app.loader import lookup_user_by_email  # ImportError erwartet → RED

        users_root = tmp_path / "users"
        _write_user_profile(users_root, "henning", {"mail_to": "Henning@Example.COM"})

        result = lookup_user_by_email("henning@example.com", data_dir=str(tmp_path))
        assert result == "henning"

    def test_returns_none_when_no_match(self, tmp_path: Path):
        """
        GIVEN: Kein User-Profil mit passender E-Mail
        WHEN: lookup_user_by_email("unknown@example.com") aufgerufen wird
        THEN: Gibt None zurück (kein Fehler)
        """
        from app.loader import lookup_user_by_email  # ImportError erwartet → RED

        users_root = tmp_path / "users"
        _write_user_profile(users_root, "default", {"mail_to": "someone@example.com"})

        result = lookup_user_by_email("unknown@example.com", data_dir=str(tmp_path))
        assert result is None

    def test_ignores_users_without_mail_to(self, tmp_path: Path):
        """
        GIVEN: User-Profil ohne mail_to-Feld
        WHEN: lookup_user_by_email() aufgerufen wird
        THEN: Kein Absturz, gibt None zurück
        """
        from app.loader import lookup_user_by_email  # ImportError erwartet → RED

        users_root = tmp_path / "users"
        _write_user_profile(users_root, "default", {})  # kein mail_to

        result = lookup_user_by_email("any@example.com", data_dir=str(tmp_path))
        assert result is None


# ===========================================================================
# AC-2 + AC-4: lookup_user_by_telegram_chat_id()
# ===========================================================================

class TestLookupUserByTelegramChatId:
    def test_finds_user_by_chat_id(self, tmp_path: Path):
        """
        GIVEN: User-Profil mit telegram_chat_id=12345
        WHEN: lookup_user_by_telegram_chat_id("12345") aufgerufen wird
        THEN: Gibt die korrekte user_id zurück
        """
        from app.loader import lookup_user_by_telegram_chat_id  # ImportError erwartet → RED

        users_root = tmp_path / "users"
        _write_user_profile(users_root, "default", {"telegram_chat_id": "99999"})
        _write_user_profile(users_root, "henning", {"telegram_chat_id": "12345"})

        result = lookup_user_by_telegram_chat_id("12345", data_dir=str(tmp_path))
        assert result == "henning"

    def test_integer_chat_id_matches_string(self, tmp_path: Path):
        """
        GIVEN: User-Profil mit telegram_chat_id als Integer 12345
        WHEN: lookup_user_by_telegram_chat_id("12345") mit String aufgerufen wird
        THEN: User wird trotzdem gefunden (int/str-tolerant)
        """
        from app.loader import lookup_user_by_telegram_chat_id  # ImportError erwartet → RED

        users_root = tmp_path / "users"
        _write_user_profile(users_root, "henning", {"telegram_chat_id": 12345})

        result = lookup_user_by_telegram_chat_id("12345", data_dir=str(tmp_path))
        assert result == "henning"

    def test_returns_none_when_no_match(self, tmp_path: Path):
        """
        GIVEN: Kein User-Profil mit passender Chat-ID
        WHEN: lookup_user_by_telegram_chat_id("99999") aufgerufen wird
        THEN: Gibt None zurück (kein Fehler)
        """
        from app.loader import lookup_user_by_telegram_chat_id  # ImportError erwartet → RED

        users_root = tmp_path / "users"
        _write_user_profile(users_root, "default", {"telegram_chat_id": "11111"})

        result = lookup_user_by_telegram_chat_id("99999", data_dir=str(tmp_path))
        assert result is None


# ===========================================================================
# AC-1: InboundEmailReader — User-Routing via Absender-Email
# ===========================================================================

class TestInboundEmailReaderUserRouting:
    def test_resolve_settings_returns_user_scoped_settings(self, tmp_path: Path):
        """
        GIVEN: InboundEmailReader und User "henning" mit mail_to=henning@example.com
        WHEN: _resolve_settings_for_sender("henning@example.com", base_settings) aufgerufen wird
        THEN: Gibt (user_id="henning", settings_mit_hennings_profil) zurück
        """
        from app.config import Settings
        from services.inbound_email_reader import InboundEmailReader

        users_root = tmp_path / "users"
        _write_user_profile(users_root, "henning", {"mail_to": "henning@example.com"})

        reader = InboundEmailReader()
        base = Settings()
        user_id, scoped = reader._resolve_settings_for_sender(
            "henning@example.com", base, data_dir=str(tmp_path)
        )
        assert user_id == "henning"

    def test_resolve_settings_fallback_to_default(self):
        """
        GIVEN: InboundEmailReader und keine User-Profil-Datei für Absender
        WHEN: _resolve_settings_for_sender("unknown@example.com", base_settings) aufgerufen wird
        THEN: Gibt (user_id="default", base_settings) zurück — kein Fehler
        """
        from app.config import Settings
        from services.inbound_email_reader import InboundEmailReader

        reader = InboundEmailReader()
        # Methode existiert noch nicht → AttributeError erwartet → RED
        base = Settings()
        user_id, scoped = reader._resolve_settings_for_sender(
            "nobody@example.com", base
        )
        assert user_id == "default"


# ===========================================================================
# AC-2: InboundTelegramReader — User-Routing via Chat-ID
# ===========================================================================

class TestInboundTelegramReaderUserRouting:
    def test_resolve_user_for_known_chat_id(self, tmp_path: Path):
        """
        GIVEN: InboundTelegramReader und User "henning" mit telegram_chat_id=12345
        WHEN: _resolve_user_for_chat("12345", base_settings) aufgerufen wird
        THEN: Gibt (user_id="henning", henning_scoped_settings) zurück
        """
        from app.config import Settings
        from services.inbound_telegram_reader import InboundTelegramReader

        users_root = tmp_path / "users"
        _write_user_profile(users_root, "henning", {"telegram_chat_id": 12345})

        reader = InboundTelegramReader()
        base = Settings()
        user_id, scoped = reader._resolve_user_for_chat("12345", base, data_dir=str(tmp_path))
        assert user_id == "henning"

    def test_resolve_user_fallback_to_default_for_unknown_chat(self):
        """
        GIVEN: InboundTelegramReader, keine User mit dieser Chat-ID
        WHEN: _resolve_user_for_chat("99999", base_settings) aufgerufen wird
        THEN: Gibt (user_id="default", base_settings) zurück — kein Fehler
        """
        from app.config import Settings
        from services.inbound_telegram_reader import InboundTelegramReader

        reader = InboundTelegramReader()
        # Methode existiert noch nicht → AttributeError erwartet → RED
        base = Settings()
        user_id, scoped = reader._resolve_user_for_chat("99999", base)
        assert user_id == "default"


# ===========================================================================
# AC-3 (production path): _process_update ruft _find_active_trip mit user_id
# ===========================================================================

class TestProductionPathUserIdPropagation:
    def test_process_update_passes_resolved_user_id_to_find_active_trip(
        self, monkeypatch
    ):
        """
        GIVEN: A Telegram update for chat_id 12345, resolved to user_id "henning"
        WHEN: _process_update() is called
        THEN: load_all_trips is called with user_id="henning" (not "default")
        """
        from datetime import date, datetime, timezone
        from app.config import Settings
        from app.trip import Trip, Stage, Waypoint
        from services.inbound_telegram_reader import InboundTelegramReader

        today = date.today()
        stage = Stage(
            id="s1", name="Tag 1", date=today,
            waypoints=[
                Waypoint(id="w1", name="Start", lat=39.0, lon=2.0, elevation_m=100),
            ],
        )
        trip = Trip(id="gr20", name="GR20", stages=[stage])

        calls = []

        def fake_load_all_trips(user_id="default"):
            calls.append(user_id)
            return [trip]

        monkeypatch.setattr(
            "services.inbound_telegram_reader.load_all_trips",
            fake_load_all_trips,
        )
        monkeypatch.setattr(
            "services.trip_command_processor.TripCommandProcessor.process",
            lambda self, msg: __import__("services.trip_command_processor", fromlist=["CommandResult"]).CommandResult(
                success=True, command="ruhetag", confirmation_subject="OK",
                confirmation_body="OK", trip_name="GR20",
            ),
        )
        monkeypatch.setattr(
            "services.inbound_telegram_reader.TelegramOutput.send",
            lambda self, subject, body, reply_markup=None: None,
        )
        # Patch resolver to return user_id "henning" for chat 12345
        monkeypatch.setattr(
            InboundTelegramReader,
            "_resolve_user_for_chat",
            lambda self, chat_id, settings, data_dir="data": (
                "henning", settings
            ),
        )

        reader = InboundTelegramReader()
        settings = Settings(telegram_bot_token="fake:token", telegram_chat_id="12345")
        update = {
            "update_id": 1,
            "message": {
                "chat": {"id": 12345},
                "text": "ruhetag",
                "date": int(datetime.now(tz=timezone.utc).timestamp()),
            },
        }
        reader._process_update(update, settings)

        assert calls == ["henning"], (
            f"Expected load_all_trips called with 'henning', got: {calls}"
        )

    def test_process_update_uses_default_user_for_unknown_chat(self, monkeypatch):
        """
        GIVEN: A Telegram update for chat_id 99999, unknown user → default
        WHEN: _process_update() is called
        THEN: load_all_trips is called with user_id="default"
        """
        from datetime import date, datetime, timezone
        from app.config import Settings
        from app.trip import Trip, Stage, Waypoint
        from services.inbound_telegram_reader import InboundTelegramReader

        today = date.today()
        stage = Stage(
            id="s1", name="Tag 1", date=today,
            waypoints=[
                Waypoint(id="w1", name="Start", lat=39.0, lon=2.0, elevation_m=100),
            ],
        )
        trip = Trip(id="gr20", name="GR20", stages=[stage])

        calls = []

        def fake_load_all_trips(user_id="default"):
            calls.append(user_id)
            return [trip]

        monkeypatch.setattr(
            "services.inbound_telegram_reader.load_all_trips",
            fake_load_all_trips,
        )
        monkeypatch.setattr(
            "services.trip_command_processor.TripCommandProcessor.process",
            lambda self, msg: __import__("services.trip_command_processor", fromlist=["CommandResult"]).CommandResult(
                success=True, command="ruhetag", confirmation_subject="OK",
                confirmation_body="OK", trip_name="GR20",
            ),
        )
        monkeypatch.setattr(
            "services.inbound_telegram_reader.TelegramOutput.send",
            lambda self, subject, body, reply_markup=None: None,
        )
        # Resolver returns "default" for unknown chat
        monkeypatch.setattr(
            InboundTelegramReader,
            "_resolve_user_for_chat",
            lambda self, chat_id, settings, data_dir="data": (
                "default", settings
            ),
        )

        reader = InboundTelegramReader()
        settings = Settings(telegram_bot_token="fake:token", telegram_chat_id="99999")
        update = {
            "update_id": 2,
            "message": {
                "chat": {"id": 99999},
                "text": "ruhetag",
                "date": int(datetime.now(tz=timezone.utc).timestamp()),
            },
        }
        reader._process_update(update, settings)

        assert calls == ["default"], (
            f"Expected load_all_trips called with 'default', got: {calls}"
        )

    def test_find_trip_id_passes_user_id_to_load_all_trips(self, monkeypatch):
        """
        GIVEN: InboundEmailReader with _find_trip_id("GR20", user_id="henning")
        WHEN: _find_trip_id is called with user_id="henning"
        THEN: load_all_trips is called with user_id="henning"
        """
        from app.trip import Trip, Stage, Waypoint
        from datetime import date
        from services.inbound_email_reader import InboundEmailReader

        stage = Stage(
            id="s1", name="Tag 1", date=date.today(),
            waypoints=[Waypoint(id="w1", name="A", lat=0.0, lon=0.0, elevation_m=0)],
        )
        trip = Trip(id="gr20", name="GR20", stages=[stage])
        calls = []

        def fake_load(user_id="default"):
            calls.append(user_id)
            return [trip]

        monkeypatch.setattr("services.inbound_email_reader.load_all_trips", fake_load)

        reader = InboundEmailReader()
        result = reader._find_trip_id("GR20", user_id="henning")

        assert result == "gr20"
        assert calls == ["henning"], f"Expected call with 'henning', got: {calls}"
