---
entity_id: issue_608_sms_seven_io
type: module
created: 2026-06-05
updated: 2026-06-05
status: draft
version: "1.0"
tags: [sms, output, seven-io, channel]
---

# SMSOutput — seven.io HTTP Versand

## Approval

- [ ] Approved

## Purpose

Implementiert den fehlenden SMS-Versandweg via seven.io REST-API als `SMSOutput`-Klasse im Python-Backend. Ohne diese Klasse bricht jeder `channel="sms"`-Aufruf mit `ModuleNotFoundError` ab, obwohl SMS-Text-Formatter und Config-Felder bereits vollständig vorhanden sind.

## Source

- **File:** `src/outputs/sms.py` (NEU)
- **Identifier:** `SMSOutput`

## Estimated Scope

- **LoC:** ~65
- **Files:** 4 (neu: `sms.py`; geändert: `config.py`, `outputs/__init__.py`, `.env.example`)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `app.config.Settings` | intern | Liefert `sms_gateway_url`, `sms_api_key`, `sms_from`, `sms_to`, `can_send_sms()` |
| `httpx` | extern | HTTP POST an seven.io REST-API (bereits im Projekt via `telegram.py`) |
| `outputs.base.OutputError` | intern | Fehlertyp bei HTTP-Fehlern |
| `outputs.base.OutputConfigError` | intern | Fehlertyp bei unvollständiger Konfiguration |
| `src/output/renderers/sms.render_sms()` | intern | Liefert den fertig formatierten SMS-Text (≤160 Zeichen, bereits implementiert) |
| `outputs.base.get_channel()` | intern | Importiert `SMSOutput` wenn `channel="sms"` gewählt wird |

## Implementation Details

### Klassen-Struktur (analog zu `src/outputs/telegram.py`)

```python
class SMSOutput:
    def __init__(self, settings: Settings) -> None:
        if not settings.can_send_sms():
            raise OutputConfigError(
                "SMS nicht konfiguriert: sms_api_key und sms_to sind Pflichtfelder"
            )
        self._settings = settings

    def send(self, subject: str, body: str) -> None:
        """Sendet body als SMS via seven.io. subject wird ignoriert (SMS hat keinen Betreff)."""
        payload: dict[str, str] = {
            "to": self._settings.sms_to,
            "text": body,
        }
        if self._settings.sms_from:
            payload["from"] = self._settings.sms_from

        response = httpx.post(
            self._settings.sms_gateway_url,
            headers={"X-Api-Key": self._settings.sms_api_key},
            data=payload,
            timeout=10,
        )
        if response.status_code != 200:
            raise OutputError(
                f"seven.io HTTP {response.status_code}: {response.text[:200]}"
            )
        # seven.io liefert "100" bei Erfolg als Plain-Text
        status_code = response.text.strip()
        if status_code != "100":
            raise OutputError(f"seven.io Fehler-Code: {status_code!r}")
```

### Config-Default in `src/app/config.py`

```python
sms_gateway_url: str = "https://gateway.seven.io/api/sms"
```

Der Default erspart eine manuelle Konfigurationseintrag für Standard-seven.io-Nutzer.

### Export in `src/outputs/__init__.py`

```python
from outputs.sms import SMSOutput

__all__ = [..., "SMSOutput"]
```

### `.env.example`-Ergänzung

```ini
# seven.io SMS-Versand
SMS_API_KEY=your_seven_io_api_key
SMS_TO=+49XXXXXXXXXX
SMS_FROM=Gregor          # optional, max 11 Zeichen (alphanumerisch) oder Rufnummer
# SMS_GATEWAY_URL=https://gateway.seven.io/api/sms  # Default, nur bei Abweichung setzen
```

### Verarbeitungsablauf bei `channel="sms"`

```
cli.py
  -> get_channel("sms", settings)      # outputs/base.py
  -> SMSOutput(settings)               # __init__: can_send_sms() prüfen
  -> render_sms(token_line)            # ≤160 Zeichen
  -> channel.send(subject=body, body=body)  # subject wird ignoriert
  -> httpx.post(gateway_url, headers, data)
  -> Antwort "100" prüfen
```

### Fehlerbehandlung

| Situation | Verhalten |
|-----------|-----------|
| `can_send_sms()` False | `OutputConfigError` in `__init__`, kein HTTP-Call |
| HTTP-Status != 200 | `OutputError` mit Status-Code + Body-Excerpt |
| seven.io Body != "100" | `OutputError` mit dem erhaltenen Status-Code |
| `sms_from` leer | Payload ohne `from`-Feld (seven.io-Default greift) |
| Netzwerk-Timeout (10s) | `httpx.TimeoutException` propagiert (kein Wrapping) |

## Expected Behavior

- **Input:** `body` = fertig formatierter SMS-Text (≤160 Zeichen, produziert von `render_sms()`); `subject` wird ignoriert
- **Output:** Keine Rückgabe; side-effect ist der HTTP-POST an seven.io
- **Side effects:** Eine SMS wird an `settings.sms_to` gesendet; bei Fehler wird eine Exception geworfen, die im CLI geloggt wird

## Acceptance Criteria

- **AC-1:** Given eine vollständige seven.io-Konfiguration (`sms_api_key`, `sms_to` gesetzt) / When `SMSOutput(settings).send(body, body)` mit einem ≤160-Zeichen-Text aufgerufen wird / Then liefert seven.io HTTP 200 + Body "100" und die SMS kommt auf der Zielrufnummer an — verifiziert durch echten HTTP-Call und Empfang (kein Mock)

- **AC-2:** Given `sms_api_key` oder `sms_to` fehlt in der Konfiguration / When `SMSOutput(settings)` instanziiert wird / Then wird `OutputConfigError` geworfen, bevor ein HTTP-Request abgeschickt wird

- **AC-3:** Given eine gültige Konfiguration / When `get_channel("sms", settings)` in `outputs/base.py` aufgerufen wird / Then gibt es keinen `ModuleNotFoundError` mehr und das zurückgegebene Objekt ist eine `SMSOutput`-Instanz, die das Output-Protocol erfüllt

- **AC-4:** Given `sms_from` ist in der Config leer / When `send()` aufgerufen wird / Then enthält der HTTP-POST an seven.io kein `from`-Feld und die SMS wird trotzdem erfolgreich zugestellt

- **AC-5:** Given seven.io antwortet mit einem Fehler-Code (nicht "100") / When `send()` aufgerufen wird / Then wird `OutputError` mit dem empfangenen Status-Code geworfen und keine stille Fehlerignorierung tritt auf

## Known Limitations

- Garmin/Satellit-Versand (Issue #18) ist kein Teil dieser Spec — das ist ein separater Channel-Typ und hat keinen Overlap mit seven.io
- `httpx.TimeoutException` bei Netzwerkproblemen wird nicht in `OutputError` gewrapped — der Aufrufer (CLI) fängt alle Exceptions
- Die seven.io-API unterstützt Bulk-SMS; diese Implementierung sendet genau eine SMS pro Aufruf (kein Batching, da der Use Case Einzel-Briefings sind)
- SMS-Text-Länge wird in `render_sms()` garantiert (≤160 Zeichen); `SMSOutput.send()` vertraut darauf und prüft nicht selbst

## Changelog

- 2026-06-05: Initial spec erstellt — Issue #608, seven.io SMS-Versandweg
