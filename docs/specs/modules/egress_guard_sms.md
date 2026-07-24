---
entity_id: egress_guard_sms
type: module
created: 2026-07-24
updated: 2026-07-24
status: draft
version: "1.0"
tags: [egress, isolation, sms, staging]
workflow: fix-1336-sms-egress
---

<!-- Issue #1336 — Scheibe B von #1337: SMS-Egress-Isolation via seven.io Sandbox-Key -->

# Egress Guard SMS — seven.io Sandbox-Isolation (Scheibe B von #1337)

## Approval

- [x] Approved

## Purpose

SMS ist der einzige ausgehende Kanal ohne Test-/Staging-Isolation: `SMSOutput.send()`
feuert bedingungslos an `gateway.seven.io`, `for_testing()` fasst SMS gar nicht an, und
der zentrale Egress-Wächter (`docs/specs/modules/egress_guard.md`) hält `gateway.seven.io`
deshalb bislang hart auf `BLOCKED` — Staging kann aktuell gar keine SMS senden (Kanal von
der PO am 2026-07-21 präventiv über `GZ_SEVEN_API_KEY` stillgelegt). Diese Spec baut den
fehlenden dedizierten Test-Zugang nach exaktem Telegram-Vorbild (`_guard_test_mode_chat_id`,
#1288): ein separater seven.io-Sandbox-API-Key, der laut Anbieter-Design **nie** eine echte
Nachricht sendet und **nie** kostet, wird per `for_testing()` eingespielt und per
Channel-Guard fail-closed erzwungen. Danach kann der Wächter `gateway.seven.io` von
`BLOCKED` auf `TEST_ACCESS` heben, ohne ein Kostenrisiko zu öffnen.

## Source

- **File:** `src/output/channels/sms.py`
- **Identifier:** `class SMSOutput`, neue Methode `_guard_test_mode_sandbox_key()`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/app/config.py` (`Settings`) | module | Trägt das neue Feld `seven_sandbox_key`; `for_testing()` swappt `seven_api_key` darauf |
| `src/output/channels/telegram.py::_guard_test_mode_chat_id` | function | Exaktes Guard-Vorbild (Issue #1288) — Struktur, Fail-closed-Logik und Fehlertext werden 1:1 auf SMS übertragen |
| `src/app/egress_guard.py` (`INVENTORY`) | module | Python-Hälfte des zentralen Egress-Wächters (#1337, Scheibe A) — `gateway.seven.io` wechselt von `BLOCKED` auf `TEST_ACCESS` |
| `internal/egress/inventory.go` (`Inventory`) | module | Go-Zwillingsliste — muss deckungsgleich mit `egress_guard.py::INVENTORY` bleiben |
| `tests/test_egress_inventory_drift.py` | test | Erzwingt Python==Go Deckungsgleichheit; MUSS nach beiden Änderungen weiterhin grün sein |
| `src/output/channels/base.py::OutputConfigError` | class | Exception-Typ des Guards, identisch zum Telegram-Vorbild |

## Scope

### Affected Files
| File | Change Type | Description |
|------|-------------|--------------|
| `src/app/config.py` | MODIFY | Neues Feld `seven_sandbox_key: Optional[str]` (env `GZ_SEVEN_SANDBOX_KEY`); in `for_testing()` `seven_api_key` → `seven_sandbox_key` umgelenkt (beide `model_copy(update=...)`-Zweige) |
| `src/output/channels/sms.py` | MODIFY | Neue Methode `_guard_test_mode_sandbox_key()` (Vorbild `telegram.py`), aufgerufen als erste Zeile in `send()` vor jedem `httpx.post` |
| `src/app/egress_guard.py` | MODIFY | `INVENTORY["gateway.seven.io"]`: `BLOCKED` → `TEST_ACCESS` |
| `internal/egress/inventory.go` | MODIFY | `Inventory["gateway.seven.io"]`: `Blocked` → `TestAccess` |
| `tests/tdd/test_sms_test_isolation.py` | CREATE | Kern-Tests (Verhaltens-Name, nicht issue-nummeriert) |

### Estimated Changes
- Files: 4 geändert, 1 neu
- LoC: +55/-2

## Test Plan

Kern-Schicht (deterministisch, kein Netz, kein Mock-Theater) in
`tests/tdd/test_sms_test_isolation.py`. Strategie identisch zum zentralen
Egress-Wächter: der HTTP-Transport wird durch einen Sentinel/kaputte
Gateway-URL ersetzt, die niemals erreicht werden darf — das beweist, dass der
Guard *vor* jedem Netzwerk-Touch entscheidet, ohne dass ein Mock die eigene
Annahme zurückspiegelt.

### Automated Tests (TDD RED)

- [ ] Test 1 — Guard blockt Fehlkonfiguration: GIVEN `is_test_mode=True` und
  `seven_api_key` ist ungleich `seven_sandbox_key`, WHEN `SMSOutput(settings).send()`
  aufgerufen wird, THEN wirft `SMSOutput.send()` `OutputConfigError`, bevor der
  HTTP-Sentinel/die kaputte Gateway-URL überhaupt erreicht wird.
- [ ] Test 2 — Fail-closed ohne Sandbox-Key: GIVEN `is_test_mode=True` und
  `seven_sandbox_key=None` (nicht provisioniert), WHEN `send()` aufgerufen wird,
  THEN wirft der Guard ebenfalls `OutputConfigError` statt den unveränderten
  Prod-Key durchzulassen (schließt exakt die Fallback-Lücke des Telegram-Vorbilds).
- [ ] Test 3 — Sandbox lässt durch: GIVEN `is_test_mode=True` und der aktive
  `seven_api_key` ist gleich `seven_sandbox_key`, WHEN `send()` aufgerufen wird,
  THEN wirft der Guard nichts und der Transport-Sentinel wird erreicht (Beweis
  „durchgelassen" ohne echten Netzwerk-Touch/ohne echte Kosten).
- [ ] Test 4 — `for_testing()` swappt den Key: GIVEN `seven_api_key="prod-key"`
  und `seven_sandbox_key="sb-key"`, WHEN `settings.for_testing()` aufgerufen
  wird, THEN ist `for_testing().seven_api_key == "sb-key"` — geprüft in BEIDEN
  Rückgabezweigen (mit und ohne `test_smtp_user`/`test_smtp_pass` gesetzt).
- [ ] Test 5 — Prod unberührt: GIVEN `is_test_mode=False`, WHEN
  `SMSOutput(settings).send()` mit unverändertem Prod-`seven_api_key`
  aufgerufen wird, THEN ist der Guard ein No-Op (kein `OutputConfigError`) und
  der Prod-Key bleibt exakt der konfigurierte Wert.
- [ ] Test 6 — Inventar-Flip + Drift-Wächter: GIVEN das aktualisierte
  `egress_guard.INVENTORY`, WHEN `INVENTORY["gateway.seven.io"]` gelesen wird,
  THEN ist der Wert `IsolationKind.TEST_ACCESS`; UND der bestehende
  `tests/test_egress_inventory_drift.py` bleibt grün (Python-Wert deckt sich
  weiterhin mit `internal/egress/inventory.go`).

**Live-E2E (Marker `live`, nur bei `/e2e-verify`):** auf Staging den echten SMS-Sendepfad
mit dem provisionierten Sandbox-Key auslösen; Nachweis über die zurückgespiegelte
seven.io-Response (`messages[]` mit `recipient`+`text`+`price`+`success`) bzw.
`GET /api/journal/outbound`. Per Sandbox-Design entstehen dabei keine echten Kosten
und keine echte Zustellung. Nicht Teil der Kern-Schicht.

## Implementation Details

### Config-Feld + `for_testing()`-Swap (`src/app/config.py`)
Neues Feld analog `telegram_test_chat_id`:
```
seven_sandbox_key: Optional[str] = Field(
    default=None,
    description="seven.io Sandbox-API-Key (env: GZ_SEVEN_SANDBOX_KEY) — sendet nie, kostet nie",
)
```
In `for_testing()` wird in **beiden** `model_copy(update={...})`-Aufrufen (Zweig ohne
Test-SMTP-Creds und Zweig mit Test-SMTP-Creds) zusätzlich zu `telegram_chat_id` auch
`"seven_api_key": self.seven_sandbox_key or self.seven_api_key` gesetzt — exakt das
Muster, das `telegram_chat_id` dort bereits für Telegram anwendet. Fehlt der
Sandbox-Key, bleibt der Prod-Key unverändert stehen; das ist die Fallback-Lücke, die
der Channel-Guard (nicht `for_testing()`) fail-closed abfängt.

### Channel-Guard (`src/output/channels/sms.py`)
`_guard_test_mode_sandbox_key()` — Struktur 1:1 aus `telegram.py::_guard_test_mode_chat_id`
übernommen, auf SMS übertragen:
- No-Op, wenn `self._settings.is_test_mode` False ist.
- Sonst: `sandbox_key = self._settings.seven_sandbox_key`, `active_key = self._settings.seven_api_key`.
- Wenn `not sandbox_key or active_key != sandbox_key`: `OutputConfigError("sms", "Test-Modus
  aktiv, aber es ist nicht der Sandbox-Key (GZ_SEVEN_SANDBOX_KEY) — Versand blockiert (#1336).")`.
- Aufruf als **erste Zeile** in `SMSOutput.send()`, vor dem `httpx.post(...)`-Aufruf.

Fail-closed heißt hier: fehlt `seven_sandbox_key` in der Umgebung (noch nicht
provisioniert), blockiert der Guard den Versand komplett, statt den unveränderten
Prod-Key durchzulassen. Das ist bewusst restriktiver als ein reiner „egal, Hauptsache
kein Prod-Key"-Vergleich — es gibt in `is_test_mode` keinen Zustand, in dem SMS
ungeschützt versendet werden kann.

### Egress-Inventar-Flip (Andock an Scheibe A)
Nach beiden obigen Änderungen ist `gateway.seven.io` durch den Channel-Guard +
Sandbox-Key-Swap genauso abgesichert wie `mail.henemm.com` (dessen Sicherheit ebenfalls
am `for_testing()`-Credential-Swap statt an einer eigenen Egress-Guard-Sonderregel
hängt). Damit kann der zentrale Wächter den Host von einer harten Blockade auf einen
deklarierten Test-Zugang heben:
- `src/app/egress_guard.py:46`: `"gateway.seven.io": IsolationKind.BLOCKED` →
  `"gateway.seven.io": IsolationKind.TEST_ACCESS`
- `internal/egress/inventory.go:34`: `"gateway.seven.io": Blocked` → `"gateway.seven.io": TestAccess`

Beide Zeilen MÜSSEN deckungsgleich bleiben — erzwungen von
`tests/test_egress_inventory_drift.py`, das die Zeilenform `"host": Kind,` per Regex
aus beiden Dateien parst und vergleicht.

## Expected Behavior

- **Input:** `Settings`-Objekt mit `is_test_mode`, `seven_api_key`, `seven_sandbox_key`;
  `SMSOutput.send(subject, body)`-Aufruf
- **Output:** Im Test-/Staging-Modus entweder durchgelassener SMS-Versand (aktiver Key ==
  Sandbox-Key) oder `OutputConfigError` (Key fehlt/weicht ab); in Prod (`is_test_mode=False`)
  unverändertes Original-Verhalten mit dem echten Prod-Key
- **Side effects:** Keine — reine Config-Feld-Ergänzung und ein zusätzlicher Guard-Check
  vor dem bestehenden `httpx.post`; keine neue Persistenz, kein neuer Netzwerkaufruf

## Acceptance Criteria

- **AC-1:** Given `is_test_mode=True` und `seven_api_key` ist ungleich dem konfigurierten
  `seven_sandbox_key` / When `SMSOutput(settings).send(subject, body)` aufgerufen wird /
  Then wirft der Guard `OutputConfigError`, bevor der HTTP-Sentinel/die kaputte
  Gateway-URL erreicht wird — kein Netzwerk-Touch vor dem Raise
  - Test: `tests/tdd/test_sms_test_isolation.py::test_guard_blocks_mismatched_key_before_transport`

- **AC-2:** Given `is_test_mode=True` und `seven_sandbox_key=None` (nicht provisioniert) /
  When `send()` aufgerufen wird / Then wirft der Guard ebenfalls `OutputConfigError` statt
  stillschweigend den Prod-Key zu verwenden (Fail-closed gegen die Fallback-Lücke)
  - Test: `tests/tdd/test_sms_test_isolation.py::test_guard_fails_closed_without_sandbox_key`

- **AC-3:** Given `is_test_mode=True` und der aktive `seven_api_key` ist identisch mit
  `seven_sandbox_key` / When `send()` aufgerufen wird / Then lässt der Guard durch und der
  Transport-Sentinel wird erreicht (Beweis „durchgelassen" ohne echten Netzwerk-Touch)
  - Test: `tests/tdd/test_sms_test_isolation.py::test_guard_passes_through_matching_sandbox_key`

- **AC-4:** Given `seven_api_key="prod-key"` und `seven_sandbox_key="sb-key"` / When
  `settings.for_testing()` aufgerufen wird / Then ist `for_testing().seven_api_key ==
  "sb-key"` in beiden Rückgabezweigen (mit und ohne gesetzte Test-SMTP-Creds)
  - Test: `tests/tdd/test_sms_test_isolation.py::test_for_testing_swaps_seven_api_key_both_branches`

- **AC-5:** Given `is_test_mode=False` (Prod) / When `SMSOutput(settings).send()` mit dem
  unveränderten Prod-`seven_api_key` aufgerufen wird / Then ist der Guard ein No-Op — kein
  `OutputConfigError`, der Prod-Key bleibt unverändert der konfigurierte Wert
  - Test: `tests/tdd/test_sms_test_isolation.py::test_guard_is_noop_in_production_mode`

- **AC-6:** Given das aktualisierte `egress_guard.INVENTORY` und die Go-Zwillingsliste /
  When `INVENTORY["gateway.seven.io"]` gelesen wird / Then ist der Wert
  `IsolationKind.TEST_ACCESS`, UND `tests/test_egress_inventory_drift.py` bleibt grün
  (Python und Go bleiben deckungsgleich)
  - Test: `tests/tdd/test_sms_test_isolation.py::test_inventory_flip_to_test_access` und der
    bestehende `tests/test_egress_inventory_drift.py`

## Known Limitations

- Die Provisionierung des seven.io-Sandbox-Keys selbst (Anlegen in der seven.io-Webapp,
  Setzen von `GZ_SEVEN_SANDBOX_KEY` auf Staging) ist ein operativer Deploy-Schritt, kein
  Code-Änderungsteil dieser Spec. Ohne provisionierten Key bleibt der Kanal auf Staging
  dank Fail-closed-Guard (AC-2) weiterhin sicher blockiert — kein Sicherheitsrisiko, nur
  eine funktionale Einschränkung bis zur Provisionierung.
- `with_user_profile()` (`config.py:279`) übernimmt `sms_to` aus dem Nutzerprofil auch im
  `force_test`-Fall ungebremst. Das bleibt in dieser Spec bewusst unverändert, da der
  Channel-Guard bereits den kompletten Versand blockiert, wenn kein Sandbox-Key aktiv ist
  — die Empfängernummer ist im Sandbox-Fall ohnehin folgenlos (seven.io sendet mit einem
  Sandbox-Key laut Anbieter-Design an keine echte Nummer). Eine eigene Empfänger-Guard-
  Ausnahme analog Telegram wäre zusätzlicher Schutz ohne akutes Risiko — kein Teil dieser
  Spec, ggf. Sammel-Eintrag #1199 bei Bedarf.
- Der `debug`-Request-Parameter von seven.io ist bewusst NICHT Teil dieser Lösung (laut
  Anbieter deprecated) — Isolation läuft ausschließlich über den separaten Sandbox-Key.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Übernimmt die bereits in `egress_guard.md` getroffene Grundsatzentscheidung
  (zentraler Wächter + Andock-Fläche für Scheiben B–E per Inventar-Zeile). Diese Spec ist
  reine Feinjustierung eines einzelnen Hosts nach demselben, bereits etablierten Muster
  (`mail.henemm.com`: Credential-Swap via `for_testing()` + Guard trägt die Sicherheit,
  Wächter deklariert `TEST_ACCESS`) — kein neuer Architektur-Entscheid nötig.

## Regel-Budget

Kein neues Gate und keine neue Pflicht-Regel — diese Spec fügt ausschließlich eine
Inventar-Zeile und einen Channel-Guard (Vorbild bereits etabliert durch Telegram #1288)
hinzu und dockt an den bestehenden zentralen Egress-Wächter an. Sie erbt dessen
Prüfdatum **2026-10-19** (siehe `docs/specs/modules/egress_guard.md`) — kein eigenes,
neues Prüfdatum nötig.

## Changelog

- 2026-07-24: Initial spec erstellt — Issue #1336, Scheibe B von #1337
