---
entity_id: telegram_output
type: module
created: 2026-04-15
updated: 2026-04-15
status: draft
version: "1.0"
tags: [telegram, channel, notification, bot-api, output]
---

# Telegram Output

## Approval

- [x] Approved

## Purpose

Adds Telegram as a new output channel for weather reports and alerts, using the native Telegram Bot API. Unlike the Signal/Callmebot integration, Telegram provides a first-party REST API that is more reliable, supports HTML formatting, and requires no third-party proxy service. The module follows the existing `OutputChannel` protocol so it integrates transparently with the channel factory and all scheduler/alert components.

## Source

- **File:** `src/outputs/telegram.py` (NEW)
- **Identifier:** `TelegramOutput`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `httpx` | third-party | HTTP POST to Telegram Bot API |
| `src/app/config.Settings` | module | Reads GZ_TELEGRAM_BOT_TOKEN, GZ_TELEGRAM_CHAT_ID |
| `src/outputs/base.OutputChannel` | protocol | Interface that TelegramOutput implements |
| `src/outputs/base.get_channel()` | function | Factory extended to instantiate TelegramOutput |
| `src/app/models.TripReportConfig` | dataclass | Gains `send_telegram: bool = False` field |
| `src/app/user.CompareSubscription` | dataclass | Gains `send_telegram: bool = False` field |
| `src/app/loader` | module | Serializes/deserializes `send_telegram` in 4 places |
| `src/services/trip_report_scheduler` | module | Dispatches to TelegramOutput when `send_telegram` flag is set |
| `src/services/trip_alert` | module | Dispatches to TelegramOutput; bugfix: per-trip flags now respected |
| `src/web/scheduler` | module | Dispatches to TelegramOutput for subscriptions |
| `api/routers/scheduler` | module | Dispatches to TelegramOutput in API scheduler |
| `src/web/pages/settings` | module | Telegram credentials card + test button |
| `src/web/pages/subscriptions` | module | Telegram checkbox in subscription dialog |
| `src/web/pages/report_config` | module | Telegram checkbox in trip report config dialog |
| `src/web/pages/compare` | module | Telegram option in manual send button |

## Architecture

```
TelegramOutput
    |
    +-- send(subject: str, body: str) -> None
    |       |
    |       +-- 1. Compose: "[{subject}]\n\n{body}" (max 4096 chars)
    |       +-- 2. POST https://api.telegram.org/bot{TOKEN}/sendMessage
    |       |       JSON: {"chat_id": CHAT_ID, "text": message}
    |       +-- 3. Log: INFO on 200 OK, ERROR on non-200 / timeout
    |
    +-- name: str = "telegram"
    +-- _settings: Settings
    +-- _timeout: int = 10  # seconds
```

## Implementation Details

### Phase 1 — Core (telegram.py + config + factory + model flags)

#### 1. TelegramOutput Class (`src/outputs/telegram.py`, NEW, ~55 LoC)

```python
"""Telegram output channel via Bot API."""
import logging

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org"
MAX_MESSAGE_LENGTH = 4096


class TelegramOutput:
    """Sends messages via the Telegram Bot API.

    Implements the OutputChannel protocol: send(subject, body).
    Uses fire-and-forget semantics — one attempt with a 10s timeout.
    On failure, logs the error; the next scheduled run is the implicit retry.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings if settings else Settings()
        self._timeout = 10

    @property
    def name(self) -> str:
        return "telegram"

    def send(self, subject: str, body: str) -> None:
        token = self._settings.telegram_bot_token
        chat_id = self._settings.telegram_chat_id
        url = f"{TELEGRAM_API_BASE}/bot{token}/sendMessage"

        message = f"[{subject}]\n\n{body}"
        if len(message) > MAX_MESSAGE_LENGTH:
            message = message[:MAX_MESSAGE_LENGTH]
            logger.warning("Telegram message truncated to %d chars", MAX_MESSAGE_LENGTH)

        payload = {"chat_id": chat_id, "text": message}

        try:
            response = httpx.post(url, json=payload, timeout=self._timeout)
            if response.status_code == 200:
                logger.info("Telegram message sent (subject=%r)", subject)
            else:
                logger.error(
                    "Telegram API returned status %d: %s",
                    response.status_code,
                    response.text[:200],
                )
        except httpx.TimeoutException:
            logger.error("Telegram send timed out after %ds (subject=%r)", self._timeout, subject)
        except httpx.HTTPError as exc:
            logger.error("Telegram send failed: %s", exc)
```

#### 2. Config Extension (`src/app/config.py`, +8 LoC)

Add to `Settings`:

```python
telegram_bot_token: str = ""   # GZ_TELEGRAM_BOT_TOKEN
telegram_chat_id: str = ""     # GZ_TELEGRAM_CHAT_ID

def can_send_telegram(self) -> bool:
    """True when bot token and chat_id are both configured."""
    return bool(self.telegram_bot_token and self.telegram_chat_id)
```

#### 3. Factory Extension (`src/outputs/base.py`, +2 LoC)

In `get_channel()`:

```python
elif channel == "telegram":
    from outputs.telegram import TelegramOutput
    return TelegramOutput(settings)
```

#### 4. Model Flags

**`src/app/models.py`** — add to `TripReportConfig` dataclass:

```python
send_telegram: bool = False
```

**`src/app/user.py`** — add to `CompareSubscription` dataclass:

```python
send_telegram: bool = False
```

### Phase 2 — Persistence (`src/app/loader.py`, ~12 LoC)

Four sites in loader.py must be updated:

**`load_compare_subscriptions()`** — add to `CompareSubscription()` constructor:

```python
send_telegram=sub_data.get("send_telegram", False),
```

**`save_compare_subscriptions()`** — add to serialized dict:

```python
"send_telegram": sub.send_telegram,
```

**`deserialize_trip_report_config()`** — add:

```python
send_telegram=data.get("send_telegram", False),
```

**`serialize_trip_report_config()`** — add:

```python
config_dict["send_telegram"] = config.send_telegram
```

Backward compatibility: all four sites use `.get(..., False)` so existing JSON without the field loads cleanly with the default.

### Phase 3 — Services (`src/services/trip_report_scheduler.py` + `src/services/trip_alert.py`)

**`trip_report_scheduler.py`** (+13 LoC, includes bugfix):

The existing code sends email unconditionally when SMTP is configured, ignoring `trip.report_config.send_email`. Fix that while adding Telegram:

```python
# Email — BUGFIX: gate on send_email flag
if trip.report_config.send_email and self._settings.can_send_email():
    EmailOutput(self._settings).send(subject, html_body, plain_text_body=plain_body)

# Signal
if trip.report_config.send_signal and self._settings.can_send_signal():
    SignalOutput(self._settings).send(subject, plain_body)

# Telegram (NEW)
if trip.report_config.send_telegram and self._settings.can_send_telegram():
    TelegramOutput(self._settings).send(subject, plain_body)
```

**`trip_alert.py`** (+12 LoC, includes bugfix):

The existing code ignores per-trip channel flags for alerts. Fix that while adding Telegram:

```python
# Email — BUGFIX: gate on trip's send_email flag
if trip.report_config.send_email and self._settings.can_send_email():
    EmailOutput(self._settings).send(subject, html_body, plain_text_body=plain_body)

# Signal — BUGFIX: gate on trip's send_signal flag
if trip.report_config.send_signal and self._settings.can_send_signal():
    SignalOutput(self._settings).send(subject, plain_body)

# Telegram (NEW)
if trip.report_config.send_telegram and self._settings.can_send_telegram():
    TelegramOutput(self._settings).send(subject, plain_body)
```

### Phase 4 — API/Scheduler (`src/web/scheduler.py` + `api/routers/scheduler.py`)

**`src/web/scheduler.py`** — extend `_execute_subscription()` with Telegram dispatch (~9 LoC):

```python
if sub.send_telegram and settings.can_send_telegram():
    TelegramOutput(settings).send(subject, text_body)
```

**`api/routers/scheduler.py`** — extend trip scheduler endpoint with Telegram dispatch (~7 LoC):

```python
if trip.report_config.send_telegram and settings.can_send_telegram():
    TelegramOutput(settings).send(subject, plain_body)
```

### Phase 5 — UI

**`src/web/pages/settings.py`** — add Telegram settings card after Signal card (~45 LoC):

```python
with ui.card():
    ui.label("Telegram Notifications").classes("text-h6")
    ui.input("Bot Token", placeholder="123456:ABC-DEF...").bind_value(settings, "telegram_bot_token")
    ui.input("Chat ID", placeholder="987654321").bind_value(settings, "telegram_chat_id")
    ui.button("Test", on_click=make_test_telegram_handler()).classes("mt-2")
```

Test handler sends `TelegramOutput(settings).send("Test", "gregor_zwanzig Telegram-Test.")` and shows a UI notification with success/failure.

**`src/web/pages/subscriptions.py`** — add Telegram checkbox in `show_subscription_dialog()` alongside existing Email/Signal checkboxes (~12 LoC):

```python
send_telegram_cb = ui.checkbox(
    "Telegram",
    value=False if is_new else sub.send_telegram,
)
```

Pass `send_telegram=send_telegram_cb.value` in the save handler and `send_telegram=subscription.send_telegram` in the toggle handler.

**`src/web/pages/report_config.py`** — add Telegram checkbox in the trip config dialog after Signal checkbox (~8 LoC):

```python
ui.checkbox("Telegram", value=trip.report_config.send_telegram).bind_value(
    trip.report_config, "send_telegram"
)
```

**`src/web/pages/compare.py`** — add Telegram to the manual send logic (~12 LoC):

```python
if subscription.send_telegram and settings.can_send_telegram():
    TelegramOutput(settings).send(subject, text_body)
```

All UI handlers must use the Safari-safe Factory Pattern: `make_<action>_handler()` returning `do_<action>()`.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `GZ_TELEGRAM_BOT_TOKEN` | — | Bot token from @BotFather (format: `123456:ABC-DEF...`) |
| `GZ_TELEGRAM_CHAT_ID` | — | Numeric chat ID of the recipient (obtained by messaging the bot and calling `getUpdates`) |

When either field is empty, `can_send_telegram()` returns False and no send is attempted.

**User setup steps:**
1. Message @BotFather on Telegram, create a new bot, copy the token
2. Start a chat with the bot (send any message)
3. Call `https://api.telegram.org/bot{TOKEN}/getUpdates` to retrieve the `chat.id`
4. Set both env vars in `.env` / config.ini

## Expected Behavior

- **Input:** `subject` (str), `body` (str, plain text from `TripReport.email_plain`)
- **Output:** None (fire-and-forget)
- **Side effects:**
  - HTTP POST to `https://api.telegram.org/bot{TOKEN}/sendMessage`
  - Log INFO on success (HTTP 200), ERROR on non-200 or network failure
  - Messages over 4096 chars are silently truncated with a WARNING log entry

### Example message

```
[GR20 Korsika — Morgenbericht 15.04.2026]

Seg 1 (Calenzana→Ortu di u Piobbu): T 18°C, Wind 20 km/h NW, Regen 0.0 mm
Seg 2 (Ortu di u Piobbu→Carozzu): T 15°C, Wind 30 km/h N, Regen 2.4 mm
Risiko: MITTEL
```

### Bugfix behavior (trip_report_scheduler + trip_alert)

Before: Email was sent whenever SMTP was configured, regardless of `send_email` flag.
After: Email (and all channels) are only sent when the corresponding per-trip flag is True AND the channel's `can_send_X()` predicate is True.

## Testing Strategy

### TDD Tests (`tests/tdd/test_telegram_output.py`, NEW, ~55 LoC)

Tests use real HTTP calls — no mocks (per project rules).

```python
# tests/tdd/test_telegram_output.py

@pytest.mark.telegram
def test_send_real_telegram_message():
    """
    Sends a real Telegram message using credentials from ENV.
    Requires GZ_TELEGRAM_BOT_TOKEN and GZ_TELEGRAM_CHAT_ID.
    Asserts HTTP 200 from Bot API.
    """
    settings = Settings()
    if not settings.can_send_telegram():
        pytest.skip("Telegram credentials not configured")

    output = TelegramOutput(settings)
    output.send(
        subject="[Test] gregor_zwanzig E2E",
        plain_text_body="Automatischer E2E-Test. Bitte ignorieren.",
    )
    # No assert needed — exception means failure


@pytest.mark.telegram
def test_message_truncated_at_limit():
    """
    Verifies that messages exceeding 4096 chars are truncated before sending.
    Checks that no exception is raised and the log contains a WARNING.
    """
    settings = Settings()
    if not settings.can_send_telegram():
        pytest.skip("Telegram credentials not configured")

    long_body = "X" * 5000
    output = TelegramOutput(settings)
    output.send(subject="Truncation test", plain_text_body=long_body)


def test_can_send_telegram_false_without_credentials():
    """
    Verifies can_send_telegram() returns False when token or chat_id is empty.
    Does not require a live Telegram bot.
    """
    settings = Settings()
    settings.telegram_bot_token = ""
    settings.telegram_chat_id = "12345"
    assert not settings.can_send_telegram()

    settings.telegram_bot_token = "valid-token"
    settings.telegram_chat_id = ""
    assert not settings.can_send_telegram()

    settings.telegram_bot_token = "valid-token"
    settings.telegram_chat_id = "12345"
    assert settings.can_send_telegram()
```

Run:

```bash
uv run pytest -m telegram tests/tdd/test_telegram_output.py -v
```

## Files to Create/Modify

| # | File | Action | Est. LoC |
|---|------|--------|---------|
| 1 | `src/outputs/telegram.py` | NEW | ~55 |
| 2 | `src/outputs/base.py` | MODIFY: +1 branch in `get_channel()` | ~2 |
| 3 | `src/app/config.py` | MODIFY: +2 fields + `can_send_telegram()` | ~8 |
| 4 | `src/app/models.py` | MODIFY: +1 field on `TripReportConfig` | ~1 |
| 5 | `src/app/user.py` | MODIFY: +1 field on `CompareSubscription` | ~1 |
| 6 | `src/app/loader.py` | MODIFY: 4 serialization sites | ~12 |
| 7 | `src/services/trip_report_scheduler.py` | MODIFY: +Telegram block + send_email bugfix | ~13 |
| 8 | `src/services/trip_alert.py` | MODIFY: +Telegram block + per-trip flags bugfix | ~12 |
| 9 | `src/web/scheduler.py` | MODIFY: +Telegram dispatch in `_execute_subscription()` | ~9 |
| 10 | `api/routers/scheduler.py` | MODIFY: +Telegram dispatch in API endpoint | ~7 |
| 11 | `src/web/pages/settings.py` | MODIFY: Telegram credentials card + test button | ~45 |
| 12 | `src/web/pages/subscriptions.py` | MODIFY: Telegram checkbox + save/toggle handlers | ~12 |
| 13 | `src/web/pages/report_config.py` | MODIFY: Telegram checkbox in trip dialog | ~8 |
| 14 | `src/web/pages/compare.py` | MODIFY: Telegram in manual send | ~12 |
| 15 | `tests/tdd/test_telegram_output.py` | NEW | ~55 |

**Total: ~252 LoC across 15 files (+ 1 new test file)**

## Known Limitations

- Plain text only (no HTML `parse_mode`) — keeps parity with Signal and avoids formatting edge cases in weather reports
- No per-alert Telegram opt-out: alerts are sent via Telegram if the trip's `send_telegram` flag is True and credentials are configured
- No retry logic: single attempt with 10s timeout; the next scheduled run is the implicit retry
- Messages over 4096 chars are truncated without notifying the recipient
- User must perform manual bot setup via @BotFather and `getUpdates` to obtain `chat_id` — this cannot be automated from within the app

## Error Handling

All exceptions are caught and logged; errors never propagate to callers (fire-and-forget):

```python
try:
    response = httpx.post(url, json=payload, timeout=self._timeout)
    ...
except httpx.TimeoutException:
    logger.error(...)
except httpx.HTTPError as exc:
    logger.error(...)
```

## Changelog

- 2026-04-15: v1.0 — Initial spec created (GitHub Issue #11, F12: Versandweg-Auswahl / Channel-Switch)
