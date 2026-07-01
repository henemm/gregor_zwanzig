# Context: test-936-sms-stub-server

## Request Summary

Einen echten lokalen HTTP-Stub-Server als pytest-Fixture einrichten, der die
seven.io-API nachbildet — damit die vollständige Send-Kette
`render_sms()` → `SMSOutput.send()` getestet werden kann, ohne echte
SMS-Kosten oder Geräteverifikation. Hintergrund: 3 Format-Bugs am
2026-06-30 wurden nur durch echten Versand entdeckt (Issue #936).

## Related Files

| Datei | Relevanz |
|-------|----------|
| `src/outputs/sms.py` | `SMSOutput.send()` — hier landet das `text`-Feld im HTTP-POST |
| `src/output/renderers/sms/__init__.py` | `render_sms()` — pure Delegation an `render_line()` |
| `src/formatters/sms_trip.py` | `SMSTripFormatter.format_sms()` — erzeugt den SMS-String aus Trip-Segmenten |
| `src/app/config.py` | `Settings.sms_gateway_url`, `.seven_api_key`, `.sms_to`, `.sms_from`, `can_send_sms()` |
| `tests/tdd/test_914_slice4_alert_sms_dispatch.py` | **Referenz-Implementierung** des `_SevenStub`-Patterns (alert-Pfad) |
| `tests/golden/test_sms_golden.py` | Golden-Tests für `render_sms()` — Fixture-Daten wiederverwendbar |
| `tests/unit/test_renderers_sms.py` | Unit-Tests für `render_sms()` direkt |
| `tests/tdd/test_issue_608_sms_seven_io.py` | Bestehende SMS-Channel-Tests (Config-Validierung + Live-Delivery) |

## Existing Patterns

### `_SevenStub` (aus #914 Slice 4)

`tests/tdd/test_914_slice4_alert_sms_dispatch.py` enthält bereits eine
vollständige Referenz-Implementierung eines echten lokalen HTTP-Servers:

```python
class _SevenStub:
    def __init__(self, body="100", status=200):
        self.received: list[bytes] = []
        # Handler fängt POST-Body in self.received
        self._httpd = HTTPServer(("127.0.0.1", 0), _Handler)
        self.url = f"http://127.0.0.1:{self._httpd.server_port}/api/sms"
        threading.Thread(target=self._httpd.serve_forever, daemon=True).start()
    def close(self): self._httpd.shutdown()
```

#936 soll dieses Muster als **pytest-Fixture** (`seven_stub`) bereitstellen
und für den Briefing-Pfad (`render_sms` → `SMSOutput.send`) verwenden.

### HTTP-POST-Format von `SMSOutput.send()`

```python
payload = {"to": settings.sms_to, "text": body}
if settings.sms_from: payload["from"] = settings.sms_from
httpx.post(url, headers={"X-Api-Key": key}, data=payload, timeout=10)
```

`data=payload` bedeutet: `application/x-www-form-urlencoded` — der
empfangene Body muss mit `parse_qs()` dekodiert werden um `text` zu
extrahieren.

### `render_sms()` Output-Format (v2.0)

Beispiel: `"GR20 E3: N12 D24 W28@15 G40@15 TH:H@16 TH+:H@14"` — Stage-Prefix
gefolgt von Metrik-Tokens mit `@Stunde`. Max 160 Zeichen.

## Dependencies

- **Upstream:** `render_sms()` → `render_line()` → Token-Builder; kein
  echtes Wetter nötig — Synthetic-Forecasts wie in Golden-Tests.
- **Downstream:** `SMSOutput.send()` → `httpx.post()` → sieben.io.
  Im Test: `httpx.post()` gegen `127.0.0.1:{port}` des Stubs.

## Existing Specs

- `docs/specs/modules/issue_608_sms_seven_io.md` — SMS-Kanal via seven.io
- `docs/reference/sms_format.md` — v2.0 Wire-Format (N, D, R@h, W@h, ...)

## Gap-Analyse

| Pfad | Was getestet wird | Lücke |
|------|------------------|-------|
| `test_renderers_sms.py` | `render_sms()` direkt | Kein HTTP-Roundtrip |
| `test_golden_sms.py` | Format-Korrektheit des Outputs | Kein HTTP-Roundtrip |
| `test_914_slice4_alert_sms_dispatch.py` | Alert-Pfad: `TripAlertService → SMSOutput` | Prüft nur `"text=" in payload`, kein dekodiertes Feld-Check |
| `test_issue_608_sms_seven_io.py` | Config-Validierung + Live-Delivery | Kein Stub; AC-5 braucht echte Credentials |

**Fehlt:** Ein Test der `render_sms()` + `SMSOutput.send()` verbindet und
prüft, was **tatsächlich im `text`-Feld ankommt** — nach URL-Decoding.

## Analysis

### Type
Feature — neues Test-Modul (kein Produktionscode geändert)

### Affected Files (with changes)

| Datei | Typ | Beschreibung |
|-------|-----|-------------|
| `tests/tdd/test_issue_936_sms_stub.py` | CREATE | Einzige neue Datei: `_SevenStub`-Klasse + `seven_stub`-Fixture + 4-5 Testfunktionen |

> Kein Refactoring von `test_914_slice4_alert_sms_dispatch.py` — CLAUDE.md-Regel
> "Don't add abstractions beyond what the task requires" gilt hier.

### Scope Assessment
- Dateien: 1 (CREATE)
- Geschätzte LoC: +85 bis +110
- Risiko: LOW — kein Produktionscode betroffen, bewährtes HTTPServer-Port-0-Pattern

### Technical Approach

**Fixture inline (nicht in conftest.py):**
- `_SevenStub`-Klasse (32 LoC, analog test_914) direkt in der Datei
- `@pytest.fixture seven_stub` startet den Stub, gibt `(stub_url, settings)` oder `(stub_url, received)` zurück
- `finally: stub.close()` im Fixture-Teardown

**Testdaten:** Synthetic `NormalizedForecast` (wie in golden tests), stage_name enthält "km" (z.B. `"GR221 Mallorca km0-11"`) um AC-4/AC-5 zu testen.

**AC-Interpretation:**
- **AC-3 (≤140 Zeichen):** Schärferer Test; eigentliche Spec-Grenze ist 160. Mit Testdaten, die einen kurzen Output erzeugen, bleibt ≤140 realistisch.
- **AC-4 (kein `(` vor km):** `assert "(" not in text.split("km")[0].rstrip()` — prüft, dass stage_name-Teil keine einschließenden Klammern bekommt (Regressions-Guard gegen Formatierungs-Bugs wie am 2026-06-30).
- **AC-5 (km-Format):** stage_name = `"GR221 Mallorca km0-11"` → `"km0-11:"` muss im Output erscheinen, nicht `"km 0 km-11:"` oder andere mangled Form. Prüft Pipeline-Durchgängigkeit.
- **AC-6 (kein Transformation):** `render_sms()` erzeugt String S; `SMSOutput.send("", S)` schickt ihn; Stub captured `text` = S. `assert text == render_sms(token_line)`.

### Dependencies
- Import-Pfade (sys.path enthält `src/`):
  - `from outputs.sms import SMSOutput`
  - `from app.config import Settings`
  - `from output.renderers.sms import render_sms`
  - `from output.tokens.dto import DailyForecast, NormalizedForecast, HourlyValue`
  - `from output.tokens.builder import build_token_line`
  - stdlib: `http.server`, `threading`, `urllib.parse`

### Open Questions
- [x] Fixture in conftest.py oder inline? → **Inline** (kein Refactoring benötigt)
- [x] AC-5 Alert- oder Briefing-Pfad? → **Briefing** (stage_name mit km-String)
- [x] AC-3 Warum 140 statt 160? → Schärferer Test mit kurzem Testdatensatz; Kommentar dokumentieren

## Risks & Considerations

1. **Port-Kollision:** `HTTPServer(("127.0.0.1", 0), ...)` wählt freien
   Port automatisch — kein `unused_tcp_port`-Plugin nötig.
2. **Thread-Safety:** Server läuft als `daemon=True`-Thread, `shutdown()`
   in `finally`-Block oder Fixture-Teardown.
3. **Fixture vs. Klasse:** Issue schlägt `@pytest.fixture` vor; der `_SevenStub`
   aus #914 ist eine Klasse. Fixture-Wrapper ist bevorzugt für Wiederverwendbarkeit.
4. **Kein `parse_qs` nötig für AC-2:** Der Stub captured `bytes`; für
   AC-3–AC-6 muss `urllib.parse.parse_qs(body.decode())` verwendet werden.
5. **km-Format im Issue-Beispiel** (`km0-11:`) taucht im aktuellen
   `render_sms()`-Output **nicht auf** — das ist Pseudocode im Issue.
   Die echten ACs beziehen sich auf das tatsächliche v2.0-Format.
