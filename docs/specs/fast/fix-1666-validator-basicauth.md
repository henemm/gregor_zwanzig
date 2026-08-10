# Mini-Spec: fix-1666-validator-basicauth

## Was ändert sich
- `scripts/setup-validator-user.sh`: Beiden `curl`-Aufrufen (Register Zeile 20-22, Login-Verifikation Zeile 30-33) wird `-u "$USER:$PASS"` hinzugefügt, damit die nginx-Basicauth vor Staging (`GZ_VALIDATOR_USER`/`GZ_VALIDATOR_PASS` aus `.claude/validator.env`) passiert wird.

## Was darf sich nicht ändern
- Die bestehende HTTP-Status-Logik (201/409/429/Fehlerfall) und die JSON-Payloads der beiden Requests bleiben unverändert — nur der zusätzliche Basicauth-Header wird ergänzt.
- Kein Verhalten für lokale/nicht-Staging-Ziele ändert sich (Basicauth-Header ist idempotent, falls nicht erforderlich).

## Manuelle Test-Schritte
1. `bash scripts/setup-validator-user.sh` gegen Staging ausführen.
2. Erwartung: kein HTTP 401 (nginx-Basicauth-Seite) mehr — stattdessen reguläre App-Antwort (201, 409 oder 429 je nach Vorzustand).
3. Bei 409/429: Login-Verifikationszweig durchläuft ebenfalls ohne 401.

## Inline-Test (wird während Implementierung geschrieben)
- [ ] Kein automatisierter Test möglich ohne Live-Staging-Zugriff (reines Shell-Script, keine Unit-Test-Infrastruktur vorhanden) — Verifikation erfolgt manuell gegen Staging gemäß obigen Schritten.
