---
entity_id: signal_output
type: module
created: 2026-04-03
updated: 2026-04-03
status: draft
version: "1.0"
tags: [signal, channel, notification, callmebot, output]
---

# Signal Output

## Approval

- [x] Approved

## Purpose

Sendet Wetterreports und Alerts als Signal-Nachricht via Callmebot API.
Ergaenzt den E-Mail-Channel als zweiten Benachrichtigungskanal fuer Wanderer
mit eingeschraenkter Konnektivitaet, bei denen Signal-Nachrichten zuverlaessiger
zugestellt werden als E-Mails.

## Source

- **File:** `src/outputs/signal.py` (NEW)
- **Identifier:** `SignalOutput`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `httpx` | third-party | HTTP GET-Request an Callmebot API |
| `urllib.parse.quote` | stdlib | URL-Encoding des Nachrichtentexts |
| `src/app/config.Settings` | module | Liest GZ_SIGNAL_PHONE, GZ_SIGNAL_API_KEY, GZ_SIGNAL_API_URL |
| `src/outputs/base.OutputChannel` | protocol | Interface, das SignalOutput implementiert |
| `src/app/models.TripReport` | dataclass | Liefert email_plain als Message-Body |

## Architecture

```
SignalOutput
    |
    +-- send(subject: str, plain_text_body: str) -> None
    |       |
    |       +-- 1. Compose: "[subject]\n\n{plain_text_body}" (max 4000 Zeichen)
    |       +-- 2. URL-encode message
    |       +-- 3. HTTP GET: {api_url}?phone={phone}&apikey={apikey}&text={msg}
    |       +-- 4. Log: success (status 200) oder error (non-200 / timeout)
    |
    +-- _settings: Settings
    +-- _timeout: int = 10  # Sekunden
```

## Implementation Details

### 1. SignalOutput Class

```python
# src/outputs/signal.py

import logging
import urllib.parse

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)

DEFAULT_API_URL = "https://signal.callmebot.com/signal/send.php"
MAX_MESSAGE_LENGTH = 4000


class SignalOutput:
    """
    Sends messages via Signal using the Callmebot API.

    Implements the OutputChannel protocol: send(subject, plain_text_body).
    Uses fire-and-forget semantics — a single attempt with a 10s timeout.
    On failure, logs the error; the next scheduled run acts as the implicit retry.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings if settings else Settings()
        self._timeout = 10

    def send(self, subject: str, plain_text_body: str) -> None:
        """
        Send a Signal message via Callmebot.

        Args:
            subject: Report/alert subject line (prepended to body)
            plain_text_body: Plain-text report body (from TripReport.email_plain)
        """
        phone = self._settings.signal_phone
        apikey = self._settings.signal_api_key
        api_url = self._settings.signal_api_url or DEFAULT_API_URL

        message = f"[{subject}]\n\n{plain_text_body}"
        if len(message) > MAX_MESSAGE_LENGTH:
            message = message[:MAX_MESSAGE_LENGTH]
            logger.warning("Signal message truncated to %d chars", MAX_MESSAGE_LENGTH)

        encoded = urllib.parse.quote(message)
        url = f"{api_url}?phone={phone}&apikey={apikey}&text={encoded}"

        try:
            response = httpx.get(url, timeout=self._timeout)
            if response.status_code == 200:
                logger.info("Signal message sent (subject=%r)", subject)
            else:
                logger.error(
                    "Callmebot returned status %d: %s",
                    response.status_code,
                    response.text[:200],
                )
        except httpx.TimeoutException:
            logger.error("Signal send timed out after %ds (subject=%r)", self._timeout, subject)
        except httpx.HTTPError as exc:
            logger.error("Signal send failed: %s", exc)
```

### 2. Config Erweiterung (src/app/config.py)

Neue Felder in der `Settings`-Klasse (gelesen aus ENV, dann config.ini):

```python
# Environment variables (prefixed GZ_)
signal_phone: str = ""          # GZ_SIGNAL_PHONE
signal_api_key: str = ""        # GZ_SIGNAL_API_KEY
signal_api_url: str = ""        # GZ_SIGNAL_API_URL (default: Callmebot URL)

def can_send_signal(self) -> bool:
    """True when phone and apikey are both configured."""
    return bool(self.signal_phone and self.signal_api_key)
```

### 3. OutputChannel Factory Erweiterung (src/outputs/base.py)

```python
# In get_channel() factory function
elif channel == "signal":
    from outputs.signal import SignalOutput
    return SignalOutput(settings)
```

### 4. TripReportConfig Erweiterung (src/app/models.py)

```python
@dataclass
class TripReportConfig:
    ...
    send_signal: bool = False   # Neues Feld
```

### 5. CLI Erweiterung (src/app/cli.py)

```python
parser.add_argument(
    "--channel",
    choices=["email", "signal", "none"],  # "signal" hinzugefuegt
    default="email",
)
```

### 6. Loader Erweiterung (src/app/loader.py)

In `serialize_trip_report_config()` und `deserialize_trip_report_config()`:

```python
# Serialize
config_dict["send_signal"] = config.send_signal

# Deserialize
send_signal = data.get("send_signal", False)
```

### 7. Scheduler Erweiterung (src/services/trip_report_scheduler.py)

Nach dem bestehenden E-Mail-Versand:

```python
if trip.report_config.send_signal and self._settings.can_send_signal():
    signal_out = SignalOutput(self._settings)
    signal_out.send(subject=report.email_subject, plain_text_body=report.email_plain)
```

### 8. Alert Erweiterung (src/services/trip_alert.py)

In `_send_alert()`, nach dem bestehenden E-Mail-Versand:

```python
if self._settings.can_send_signal():
    signal_out = SignalOutput(self._settings)
    signal_out.send(subject=alert_subject, plain_text_body=report.email_plain)
```

Hinweis: Signal-Alerts werden immer gesendet wenn `can_send_signal()` True ist;
eine separate `send_signal`-Flag am Trip ist nicht noetig (Alerts sind immer opt-in
durch die Konfiguration des API-Keys).

### 9. Web UI Erweiterungen

**settings.py** — neues Settings-Card:

```python
# Signal Settings Card (nach Email Settings)
with ui.card():
    ui.label("Signal Notifications").classes("text-h6")
    ui.input("Phone", placeholder="+43...").bind_value(settings, "signal_phone")
    ui.input("API Key", placeholder="Callmebot API Key").bind_value(settings, "signal_api_key")
    ui.input("API URL (optional)").bind_value(settings, "signal_api_url")
    ui.button("Test", on_click=make_test_signal_handler()).classes("mt-2")
```

**report_config.py** — Checkbox pro Trip:

```python
ui.checkbox("Signal", value=trip.report_config.send_signal).bind_value(
    trip.report_config, "send_signal"
)
```

Alle UI-Handler verwenden Safari-sicheres Factory Pattern (`make_<action>_handler()`).

## Configuration

| Variable | Default | Beschreibung |
|----------|---------|--------------|
| `GZ_SIGNAL_PHONE` | — | Empfaenger-Telefonnummer mit Laendervorwahl (z.B. +43...) |
| `GZ_SIGNAL_API_KEY` | — | Callmebot API Key (einmalig per Signal-Nachricht aktiviert) |
| `GZ_SIGNAL_API_URL` | Callmebot URL | Ueberschreibbar fuer Tests |

Wenn `GZ_SIGNAL_PHONE` oder `GZ_SIGNAL_API_KEY` leer sind, gibt `can_send_signal()` False
zurueck und kein Send-Versuch wird unternommen.

## Expected Behavior

- **Input:** subject (str), plain_text_body (str aus `TripReport.email_plain`)
- **Output:** None (fire-and-forget)
- **Side effects:**
  - HTTP GET-Request an Callmebot API
  - Log-Eintrag (INFO bei Erfolg, ERROR bei Fehler)
  - Nachrichten ueber 4000 Zeichen werden still gekuerzt (mit WARNING-Log)

### Beispiel Nachricht:

```
[GR221 Mallorca — Morgenbericht 03.04.2026]

Seg 1 (Valldemossa→Deià): T 14°C, Wind 25 km/h SW, Regen 1.2 mm
Seg 2 (Deià→Sóller): T 16°C, Wind 18 km/h W, Regen 0.0 mm
Risiko: NIEDRIG
```

## Testing Strategy

### E2E Test (pytest marker: `signal`)

```python
# tests/e2e/test_signal_output.py
@pytest.mark.signal
def test_send_real_signal_message():
    """
    Sends a real Signal message via Callmebot using credentials from ENV.
    Requires GZ_SIGNAL_PHONE and GZ_SIGNAL_API_KEY to be set.
    Prueft: HTTP 200 von Callmebot API.
    """
    settings = Settings()
    if not settings.can_send_signal():
        pytest.skip("Signal credentials not configured")

    output = SignalOutput(settings)
    output.send(
        subject="[Test] gregor_zwanzig E2E",
        plain_text_body="Automatischer E2E-Test. Bitte ignorieren.",
    )
    # Kein assert noetig — Exception waere Fehlschlag
```

Ausfuehren:

```bash
uv run pytest -m signal tests/e2e/test_signal_output.py -v
```

## Files to Create/Modify

| File | Action | LoC |
|------|--------|-----|
| `src/outputs/signal.py` | NEW | ~55 |
| `src/outputs/base.py` | MODIFY | +3 |
| `src/app/config.py` | MODIFY | +10 |
| `src/app/models.py` | MODIFY | +2 |
| `src/app/cli.py` | MODIFY | +1 |
| `src/app/loader.py` | MODIFY | +4 |
| `src/services/trip_report_scheduler.py` | MODIFY | +5 |
| `src/services/trip_alert.py` | MODIFY | +5 |
| `src/web/pages/settings.py` | MODIFY | +15 |
| `src/web/pages/report_config.py` | MODIFY | +5 |
| `tests/e2e/test_signal_output.py` | NEW | ~30 |

**Total: ~135 LoC** (unter 250 Limit)

## Known Limitations

- Signal-Alerts (`trip_alert.py`) werden bei jedem Wetter-Alert gesendet, solange
  `can_send_signal()` True ist — kein separates Per-Trip-Opt-in fuer Alerts im MVP.
- Keine Retry-Logik: einzelner Versuch mit 10s Timeout; der naechste geplante Report-Lauf
  ist der implizite Retry.
- Nachrichten ueber 4000 Zeichen werden ohne Benutzerhinweis gekuerzt.
- Callmebot erfordert einmalige manuelle Aktivierung via Signal-Nachricht an +34 631 19 61 60.

## Error Handling

```python
# Alle Fehler werden geloggt, nie propagiert — fire-and-forget
try:
    response = httpx.get(url, timeout=self._timeout)
    ...
except httpx.TimeoutException:
    logger.error(...)
except httpx.HTTPError as exc:
    logger.error(...)
```

## Changelog

- 2026-04-03: v1.0 Initial spec created (GitHub Issue #4)
