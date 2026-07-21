---
entity_id: test-936-sms-stub-server
type: test
version: "1.1"
created: 2026-06-30
updated: 2026-07-01
status: implemented
workflow: test-936-sms-stub-server
---

# SMS-Format-Verifikation via lokalem HTTP-Stub (Issue #936)

## Approval

- [x] Approved

## Purpose

Verifiziert die vollständige Send-Kette `render_sms()` → `SMSOutput.send()` gegen einen
lokalen HTTP-Stub-Server und prüft, was tatsächlich als `text`-Feld im POST-Body ankam.
Hintergrund: Drei Format-Bugs am 2026-06-30 wurden erst durch echten Versand entdeckt.
Der lokale Stub empfängt den echten HTTP-POST von `SMSOutput.send()` und gibt die
gesendeten Daten zurück — ohne externe API-Abhängigkeit und ohne Credentials.

## Source

- **File:** `tests/tdd/test_issue_936_sms_stub.py`
- **Identifier:** Testfunktionen (kein eigenes Modul, reine Test-Datei)

## Estimated Scope

- **LoC:** ~240
- **Files:** 1 (CREATE) + 1 (MODIFY: `src/output/tokens/builder.py`)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `outputs.sms.SMSOutput` | Uses | Produktionskette die unter Test steht |
| `output.renderers.sms.render_sms` | Uses | Erzeugt den SMS-String aus Token-Daten |
| `output.tokens.builder.build_token_line` | Uses | Baut synthetische Testdaten |
| `output.tokens.dto.DailyForecast` | Uses | DTO für Tagesprognose-Testdaten |
| `output.tokens.dto.NormalizedForecast` | Uses | DTO als Input für render_sms() |
| `output.tokens.dto.HourlyValue` | Uses | DTO für stündliche Messwerte |
| `app.config.Settings` | Uses | SMS-Config mit lokaler Stub-URL |
| `http.server.HTTPServer` | Internal | Lokaler HTTP-Stub-Server (Port random) |

## Implementation Details

**Kein Credential-Handling nötig:** Der Stub läuft lokal auf einem zufälligen Port —
keine externen Keys, kein `pytest.skip()`. Tests laufen überall (lokal + CI).

**Settings-Vorbereitung:**
```python
def _stub_settings(port: int) -> Settings:
    return Settings().model_copy(update={
        "sms_gateway_url": f"http://127.0.0.1:{port}/api/sms",
        "seven_api_key": "test-stub-key",
        "sms_to": "+49000000000",
        "sms_from": None,
    })
```

**Testdaten:** Synthetic `NormalizedForecast` mit `stage_name="GR221 Mallorca km0-11"`
via `build_token_line()`. Deterministischer Output — eindeutig im Stub identifizierbar.

**Ablauf:**
1. `_SMSStub().start()` — lokaler HTTP-Server auf Random-Port
2. `expected = render_sms(token_line)` — String der durch die Kette gehen soll
3. `SMSOutput(_stub_settings(stub.port)).send("", expected)` — echter HTTP-POST an Stub
4. `stub.last_text()` — letzten empfangenen POST-Body auslesen
5. Format-ACs auf `text` prüfen

**Stub-Implementierung:** `_SMSStub` nutzt `http.server.HTTPServer` in einem Daemon-Thread.
`do_POST` liest `Content-Length`, dekodiert URL-encoded Body (`urllib.parse.parse_qs`),
antwortet mit HTTP 200 + Body `100` (seven.io-Format). `last_text()` gibt `text`-Parameter zurück.

## Test Plan

Alle Tests in `tests/tdd/test_issue_936_sms_stub.py`, markiert mit `@pytest.mark.live`.

| Testfunktion | ACs | Beschreibung |
|---|---|---|
| `test_sms_send_appears_in_stub` | AC-1, AC-2 | SMS landet im Stub — Roundtrip bewiesen |
| `test_sms_text_length` | AC-3 | text-Feld im Stub <= 140 Zeichen |
| `test_sms_stage_name_no_parens` | AC-4 | Kein `(` im Stage-Name-Anteil vor `km` |
| `test_sms_km_format` | AC-5 | `km0-11:` im Stub-Text |
| `test_sms_send_does_not_transform_text` | AC-6 | Stub-Text == render_sms()-Output |

## Acceptance Criteria

- **AC-1:** Given ein laufender lokaler HTTP-Stub-Server / When `SMSOutput(settings).send()` aufgerufen wird / Then empfängt der Stub einen POST mit dem erwarteten text-Feld (echter HTTP-Roundtrip, kein patch()/Mock())
  - Test: `assert text is not None` — beweist, dass der POST die komplette Kette bis zum Stub-Gateway durchlaufen hat

- **AC-2:** Given der im Stub empfangene text-Parameter / When er ausgelesen wird / Then ist er nicht leer und identisch mit dem Wert den `render_sms()` zurückgegeben hat
  - Test: `assert text is not None` und `assert text == expected` — beweist den unverfälschten Durchlauf durch `SMSOutput.send()`

- **AC-3:** Given der aus dem Stub extrahierte `text`-Wert / When die Länge gemessen wird / Then ist `len(text) <= 140` für den verwendeten Testdatensatz
  - Test: `assert len(text) <= 140` — beweist, dass render_sms() für diesen Datensatz unter der SMS-Zeichengrenze bleibt

- **AC-4:** Given der Stub-`text`-Wert mit stage_name `"GR221 Mallorca km0-11"` / When der Anteil vor dem ersten `km`-Vorkommen isoliert wird / Then enthält er kein `(`-Zeichen
  - Test: `assert "(" not in text.split("km")[0].rstrip()` — beweist, dass kein geklammerte Stage-Name-Artefakt vor dem km-Marker erscheint

- **AC-5:** Given der Stub-`text`-Wert / When nach dem km-Bereichsformat gesucht wird / Then enthält er `"km0-11:"` (Bindestrich, kein Leerzeichen, Doppelpunkt direkt dahinter)
  - Test: `assert "km0-11:" in text` — beweist die korrekte km-Bereichsdarstellung ohne Leerzeichen-Mangling

- **AC-6:** Given der via `render_sms(token_line)` erzeugte String / When `SMSOutput.send()` ihn an den Stub schickt / Then ist der Stub-Text byte-identisch mit dem `render_sms()`-Rückgabewert
  - Test: `assert text == expected` — beweist, dass `SMSOutput.send()` den Text nicht modifiziert oder re-enkodiert

## Known Limitations

- `@pytest.mark.live`-Markierung bleibt, da Tests echten HTTP-POST abfeuern (kein Mock/patch).
- Bei sehr kurzen generischen Texten theoretisch Überschneidung möglich wenn mehrere Tests parallel laufen — in der Praxis durch deterministischen Stage-Name eindeutig.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Lokaler HTTP-Stub statt Sandbox-API, weil: (1) keine externen Credentials nötig → CI-freundlich, (2) deterministisch und schnell, (3) testet dennoch den echten HTTP-POST-Pfad inkl. URL-Encoding in `SMSOutput.send()` — was genug ist um die drei Format-Bugs aus #936 zu fangen. Sandbox-API würde zusätzlich die API-Authentifizierung testen, ist dafür aber credential-abhängig und langsamer.

## Changelog

- 2026-06-30: Spec erstellt — definiert `_SevenStub`-Pattern (lokaler HTTP-Stub)
- 2026-07-01: Zwischenzeitlich auf seven.io Sandbox-API umgestellt (lokaler Stub galt als zu künstlich)
- 2026-07-01: Zurück zu lokalem HTTP-Stub — Implementierung verifiziert (Adversary VERIFIED, 5/5 Tests grün). Sandbox-Ansatz wäre credential-abhängig ohne zusätzlichen Mehrwert für die Format-Bug-Erkennung.
