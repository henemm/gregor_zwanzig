# Mini-Spec: Playwright-Staging-Tests ohne Basic-Auth-Helper (#1045)

## Was ändert sich

In den folgenden 3 Testdateien wird der bereits etablierte Staging-Basic-Auth-Helper
(`tests.helpers.staging_auth.playwright_http_credentials`, eingeführt mit #908/#973/#987)
nachgerüstet, analog zum bestehenden Muster in `tests/tdd/test_issue_727_trips_null_safety.py`
und `tests/tdd/test_issue_846_alert_preset_e2e.py`:

- `tests/tdd/test_794_mobile_metric_label.py`
- `tests/tdd/test_702_alerts_mobile_parity.py`
- `tests/tdd/test_bundle_d_785_yesterday_toggle.py`

Konkret pro Datei:
1. Import ergänzen: `from tests.helpers.staging_auth import playwright_http_credentials`
2. Jeder bestehende `browser.new_context(...)`-Aufruf, der gegen Staging fährt, bekommt
   zusätzlich `http_credentials=playwright_http_credentials()` als Argument (bestehende
   Argumente wie `viewport=`, `storage_state=` bleiben erhalten).

### Scope-Erweiterung (während Implementierung entdeckt, PO-freigegeben)

`tests/tdd/test_bundle_d_785_yesterday_toggle.py` enthält zusätzlich 4 direkte
`httpx.put`/`httpx.get`-Aufrufe zur Testdaten-Vorbereitung, die über einen anderen Transport
als Playwright laufen und daher weiterhin an derselben nginx-Basic-Auth scheitern würden.
Nach PO-Freigabe wird hier zusätzlich, analog zu `test_issue_727_trips_null_safety.py`,
`httpx_auth` importiert und `auth=httpx_auth()` an jedem der 4 Calls ergänzt (bestehende
Argumente wie `cookies=`, `json=` bleiben erhalten). Dies ist reine Auth-Injection, keine
Änderung an Assertions oder Testablauf.

## Was darf sich nicht ändern

- Keine Änderung an Testlogik, Assertions oder Ablaufreihenfolge
- Keine Änderung an Produktivcode (`src/`, `api/`, `internal/`, `frontend/`)
- Der #1020-Fix (identischer Patch in allen 5 Dateien) bleibt unangetastet

## Manuelle Test-Schritte

1. `uv run pytest tests/tdd/test_794_mobile_metric_label.py -v` gegen Staging laufen lassen
   → kein nginx-`401 Authorization Required` mehr, Test erreicht App-Login
2. `uv run pytest tests/tdd/test_702_alerts_mobile_parity.py -v` — dito
3. `uv run pytest tests/tdd/test_bundle_d_785_yesterday_toggle.py -v` — dito

## Inline-Test (wird während Implementierung geschrieben)

- [ ] Alle 3 Dateien laufen End-to-End gegen Staging durch (kein 401 vor App-Login),
      d.h. sie erreichen mindestens den App-Login-Schritt statt an der nginx-Basic-Auth
      zu scheitern
