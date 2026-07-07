"""
TDD RED tests for Telegram Output channel.

These tests MUST FAIL until TelegramOutput is implemented.
Spec: docs/specs/modules/telegram_output.md
GitHub Issue: #11
"""
import json



# =============================================================================
# Test 1: TelegramOutput class exists and follows protocol
# =============================================================================


def test_telegram_output_import():
    """GIVEN outputs package WHEN importing TelegramOutput THEN class exists."""
    from output.channels.telegram import TelegramOutput
    assert TelegramOutput is not None


def test_telegram_output_implements_protocol():
    """GIVEN TelegramOutput WHEN checking protocol THEN satisfies OutputChannel."""
    from output.channels.base import OutputChannel
    from output.channels.telegram import TelegramOutput
    from app.config import Settings
    settings = Settings(telegram_bot_token="fake:token", telegram_chat_id="12345")
    output = TelegramOutput(settings)
    assert isinstance(output, OutputChannel)


def test_telegram_output_name():
    """GIVEN TelegramOutput WHEN accessing .name THEN returns telegram."""
    from output.channels.telegram import TelegramOutput
    from app.config import Settings
    settings = Settings(telegram_bot_token="fake:token", telegram_chat_id="12345")
    output = TelegramOutput(settings)
    assert output.name == "telegram"


# =============================================================================
# Test 2: Settings fields and can_send_telegram()
# =============================================================================


def test_telegram_config_fields():
    """GIVEN Settings WHEN creating with telegram fields THEN accessible."""
    from app.config import Settings
    settings = Settings(
        telegram_bot_token="123456:ABC-DEF",
        telegram_chat_id="987654321",
    )
    assert settings.telegram_bot_token == "123456:ABC-DEF"
    assert settings.telegram_chat_id == "987654321"


def test_telegram_can_send_true():
    """GIVEN Settings with token and chat_id WHEN can_send_telegram THEN True."""
    from app.config import Settings
    settings = Settings(telegram_bot_token="123:ABC", telegram_chat_id="12345")
    assert settings.can_send_telegram() is True


def test_telegram_can_send_false_no_token():
    """GIVEN Settings without token WHEN can_send_telegram THEN False."""
    from app.config import Settings
    settings = Settings(telegram_bot_token="", telegram_chat_id="12345")
    assert settings.can_send_telegram() is False


def test_telegram_can_send_false_no_chat_id():
    """GIVEN Settings without chat_id WHEN can_send_telegram THEN False."""
    from app.config import Settings
    settings = Settings(telegram_bot_token="123:ABC", telegram_chat_id="")
    assert settings.can_send_telegram() is False


# =============================================================================
# Test 3: Factory integration
# =============================================================================


def test_telegram_output_factory():
    """GIVEN get_channel WHEN requesting telegram THEN returns TelegramOutput."""
    from output.channels.base import get_channel
    from app.config import Settings
    settings = Settings(telegram_bot_token="123:ABC", telegram_chat_id="12345")
    channel = get_channel("telegram", settings)
    assert channel.name == "telegram"


# =============================================================================
# Test 4: Model flags
# =============================================================================


def test_telegram_trip_config_default():
    """GIVEN TripReportConfig WHEN created without send_telegram THEN False."""
    from app.models import TripReportConfig
    config = TripReportConfig(trip_id="test")
    assert config.send_telegram is False


def test_telegram_trip_config_explicit():
    """GIVEN TripReportConfig WHEN send_telegram=True THEN True."""
    from app.models import TripReportConfig
    config = TripReportConfig(trip_id="test", send_telegram=True)
    assert config.send_telegram is True


def test_telegram_subscription_default():
    """GIVEN CompareSubscription WHEN created without send_telegram THEN False."""
    from app.user import CompareSubscription
    sub = CompareSubscription(id="test", name="Test")
    assert sub.send_telegram is False


def test_telegram_subscription_explicit():
    """GIVEN CompareSubscription WHEN send_telegram=True THEN True."""
    from app.user import CompareSubscription
    sub = CompareSubscription(id="test", name="Test", send_telegram=True)
    assert sub.send_telegram is True


# =============================================================================
# Test 5: Loader round-trip for send_telegram
# =============================================================================


class TestLoaderTelegramRoundTrip:
    """Loader serializes and deserializes send_telegram flag."""

    def test_subscription_save_load_telegram(self):
        """
        GIVEN: CompareSubscription with send_telegram=True
        WHEN: saved and loaded back
        THEN: send_telegram round-trips correctly
        """
        from app.user import CompareSubscription
        from app.loader import save_compare_subscription, load_compare_subscriptions

        sub = CompareSubscription(
            id="telegram-test", name="Telegram Test",
            send_email=True, send_telegram=True,
        )
        save_compare_subscription(sub, user_id="__test_telegram__")
        loaded = load_compare_subscriptions(user_id="__test_telegram__")

        found = [s for s in loaded if s.id == "telegram-test"]
        assert len(found) == 1
        assert found[0].send_telegram is True
        assert found[0].send_email is True

    def test_subscription_json_contains_send_telegram(self):
        """
        GIVEN: CompareSubscription with send_telegram=True
        WHEN: saved to JSON
        THEN: JSON contains send_telegram key
        """
        from app.user import CompareSubscription
        from app.loader import save_compare_subscription, get_compare_subscriptions_file

        sub = CompareSubscription(
            id="tg-json-check", name="TG JSON Check",
            send_telegram=True,
        )
        save_compare_subscription(sub, user_id="__test_json_tg__")

        path = get_compare_subscriptions_file("__test_json_tg__")
        with open(path) as f:
            data = json.load(f)

        subs = data["subscriptions"]
        found = [s for s in subs if s["id"] == "tg-json-check"]
        assert len(found) == 1
        assert found[0]["send_telegram"] is True

    def test_backward_compat_no_telegram_field(self):
        """
        GIVEN: Legacy JSON without send_telegram field
        WHEN: loaded via load_compare_subscriptions
        THEN: defaults to send_telegram=False
        """
        from app.loader import load_compare_subscriptions, get_compare_subscriptions_file

        path = get_compare_subscriptions_file("__test_legacy_tg__")
        path.parent.mkdir(parents=True, exist_ok=True)
        legacy = {
            "subscriptions": [{
                "id": "legacy-tg",
                "name": "Legacy No Telegram",
                "enabled": True,
                "locations": ["*"],
                "forecast_hours": 48,
                "time_window_start": 9,
                "time_window_end": 16,
                "schedule": "weekly",
                "weekday": 4,
                "send_email": True,
                "send_signal": False,
            }]
        }
        with open(path, "w") as f:
            json.dump(legacy, f)

        loaded = load_compare_subscriptions(user_id="__test_legacy_tg__")
        assert len(loaded) == 1
        assert loaded[0].send_telegram is False


# =============================================================================
# Issue #976 — HTML-Truncation darf Tags nicht mittig abschneiden.
# =============================================================================


class TestTelegramHTMLTruncation:
    """Issue #976: MAX_MESSAGE_LENGTH-Truncation muss HTML-Tag-Balance bewahren."""

    def test_truncate_html_closes_open_tags(self):
        """GIVEN: HTML-Nachricht > MAX_MESSAGE_LENGTH mit offenem <b>
        WHEN: _truncate_html angewendet wird
        THEN: resultierender Text enthält kein ungeschlossenes <b>.
        """
        from output.channels.telegram import _truncate_html, MAX_MESSAGE_LENGTH

        # Ein sehr langer Text mit führendem <b>, der definitiv abgeschnitten wird.
        body = "<b>" + "word " * 3000 + "</b>"
        assert len(body) > MAX_MESSAGE_LENGTH

        truncated = _truncate_html(body, MAX_MESSAGE_LENGTH)
        assert len(truncated) <= MAX_MESSAGE_LENGTH
        # Es darf kein öffnendes <b> ohne schließendes </b> geben.
        open_count = truncated.count("<b>")
        close_count = truncated.count("</b>")
        assert open_count == close_count, (
            f"RED: unbalanced HTML tags after truncation (<b>={open_count}, "
            f"</b>={close_count}): {truncated[-100:]!r}"
        )

    def test_truncate_html_does_not_break_non_html(self):
        """GIVEN: Plaintext-Nachricht > MAX_MESSAGE_LENGTH
        WHEN: _truncate_html angewendet wird
        THEN: es wird wie bisher hart auf die Länge gekürzt.
        """
        from output.channels.telegram import _truncate_html, MAX_MESSAGE_LENGTH

        body = "word " * 3000
        truncated = _truncate_html(body, MAX_MESSAGE_LENGTH)
        assert len(truncated) == MAX_MESSAGE_LENGTH

    def test_truncate_html_preserves_small_html_message(self):
        """GIVEN: Kurze HTML-Nachricht < MAX_MESSAGE_LENGTH
        WHEN: _truncate_html angewendet wird
        THEN: Nachricht bleibt unverändert.
        """
        from output.channels.telegram import _truncate_html, MAX_MESSAGE_LENGTH

        body = "<b>short</b>"
        assert len(body) < MAX_MESSAGE_LENGTH
        assert _truncate_html(body, MAX_MESSAGE_LENGTH) == body

    def test_truncate_html_never_exceeds_max_len_dense_tags(self):
        """GIVEN: HTML-Nachrichten mit vielen kleinen, dicht gepackten Tags nahe der Grenze
        WHEN: _truncate_html über eine Reihe von Fuellzeichen-Laengen angewendet wird
        THEN: len(ergebnis) <= max_len gilt IMMER (AC-1) UND alle <b>-Tags bleiben
              balanciert (AC-2) — unabhaengig davon, wie dicht die Tags liegen.
        """
        from output.channels.telegram import _truncate_html, MAX_MESSAGE_LENGTH

        for filler in range(1, 41):
            body = ("x" * filler + "<b>y</b>") * 2000
            out = _truncate_html(body, MAX_MESSAGE_LENGTH)
            assert len(out) <= MAX_MESSAGE_LENGTH, (
                f"RED: filler={filler} produced len={len(out)} > {MAX_MESSAGE_LENGTH}"
            )
            assert out.count("<b>") == out.count("</b>"), (
                f"RED: filler={filler} unbalanced <b> tags in {out[-100:]!r}"
            )

    def test_truncate_html_padded_closing_tag_respects_max_len(self):
        """GIVEN: schließendes Tag mit Zusatz-Whitespace/Rauschen (</b  >), gefolgt
        von weiterem Text, an einer Stelle die nahe an max_len liegt
        WHEN: _truncate_html angewendet wird
        THEN: len(ergebnis) <= max_len gilt IMMER (AC-1) — auch wenn der reale
              schließende Tag laenger ist als das synthetische "</b>", mit dem
              das Budget reserviert wurde (Adversary-Finding F001).
        """
        from output.channels.telegram import _truncate_html, MAX_MESSAGE_LENGTH

        for fill_len in range(4000, 4096, 5):
            for pad in range(0, 51, 5):
                body = "<b>" + "A" * fill_len + "</b" + " " * pad + ">" + "Z" * 20
                out = _truncate_html(body, MAX_MESSAGE_LENGTH)
                assert len(out) <= MAX_MESSAGE_LENGTH, (
                    f"RED: fill_len={fill_len} pad={pad} produced len={len(out)} "
                    f"> {MAX_MESSAGE_LENGTH}"
                )

    def test_truncate_html_case_mismatched_closing_tag_balanced(self):
        """GIVEN: öffnendes <b> und ein case-abweichendes schließendes </B>
        WHEN: _truncate_html angewendet wird
        THEN: die Tags bleiben case-insensitiv balanciert (AC-2) — kein
              unbalanciertes </B></b>-Waisenpaar (Adversary-Finding F002).
        """
        from output.channels.telegram import _truncate_html, MAX_MESSAGE_LENGTH

        body = "<b>" + "A" * 4085 + "</B>" + "Z" * 20
        assert len(body) > MAX_MESSAGE_LENGTH

        out = _truncate_html(body, MAX_MESSAGE_LENGTH)
        assert len(out) <= MAX_MESSAGE_LENGTH
        open_count = out.lower().count("<b>")
        close_count = out.lower().count("</b>")
        assert open_count == close_count, (
            f"RED: case-insensitive unbalanced <b> tags "
            f"(<b>={open_count}, </b>={close_count}): {out[-100:]!r}"
        )
        assert "</B></b>" not in out, (
            f"RED: orphaned unbalanced </B></b> pair found: {out[-100:]!r}"
        )
