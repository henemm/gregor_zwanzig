# E2E-Verifikation (Post-Push auf Staging)

Sichere Acceptance-Stage-Verifikation, dass der neue Code auf der **Staging**-Umgebung
tatsaechlich funktioniert. Sie ersetzt die fruehere lokale Prod-Verifikation
(Issue #339): kein Eingriff in den Live-Server, keine Mails an echte Nutzer.

## Wann ausfuehren

NACH `git push origin main`, sobald der Staging-Auto-Deploy (~5 Min via Cron)
durch ist — und VOR `deploy-gregor-prod.sh`.

Ablauf:
1. `git push origin main`
2. ~5 Min warten (Auto-Deploy auf Staging)
3. Diese Prozedur (`/e2e-verify`) gegen Staging
4. `deploy-gregor-prod.sh`

## Ziel-Umgebung

- **Basis-URL:** `https://staging.gregor20.henemm.com`
- **Override:** `GZ_SVELTE_BASE` bzw. `GZ_VALIDATION_URL` (z. B. fuer einen anderen
  Staging-Host). Niemals auf die Live-Produktions-URL umstellen.

## Schritt 1: Smoke gegen Staging

```bash
BASE="${GZ_SVELTE_BASE:-https://staging.gregor20.henemm.com}"
curl -s -o /dev/null -w "ROOT %{http_code}\n" "$BASE/"
curl -s -o /dev/null -w "HEALTH %{http_code}\n" "$BASE/api/health"
```

**STOP wenn:** ROOT nicht `200`/`302` oder HEALTH nicht `200`. Auto-Deploy noch
nicht durch oder fehlgeschlagen — warten bzw. Staging-Logs pruefen.

## Schritt 2: Scope bestimmen

Die zu pruefende Tiefe haengt vom Aenderungs-Scope ab (Logik aus `e2e_commit_gate.py::detect_scope`,
Issue #86):

- **frontend-only** → nur visuelle Pruefung auf Staging, KEIN Mailversand.
- **backend** / **full-stack** → Test-Trip auf Staging anlegen + Briefing
  ausschliesslich an diesen Test-Trip senden, danach IMAP-Pruefung.

```bash
python3 .claude/hooks/e2e_commit_gate.py <<< '{"tool_input":{"command":"git commit"}}' 2>&1 || true
```

(Der Aufruf gibt nur den erkannten Scope als Hinweis aus — er blockt nichts.)

## Schritt 3a: frontend-only — visuelle Pruefung

Playwright/Screenshot gegen Staging. Die Basis-URL kommt aus `GZ_SVELTE_BASE`:

```bash
GZ_SVELTE_BASE="${GZ_SVELTE_BASE:-https://staging.gregor20.henemm.com}" \
  uv run python3 .claude/hooks/e2e_browser_test.py browser --check "Feature" --url "/"
```

Screenshot visuell pruefen: ist die Aenderung auf Staging sichtbar und korrekt?
KEINE Mail in diesem Scope.

## Schritt 3b: backend / full-stack — Test-Trip + Test-Mail

1. **Test-Trip auf Staging anlegen** (via Staging-API), niemals einen Produktiv-Trip
   (GR221 etc.) verwenden. Der Trip bekommt als einzigen Empfaenger die Test-Adresse
   `gregor-test@henemm.com`.
2. **Briefing ausschliesslich an diesen einen Test-Trip** ausloesen — niemals einen
   Sammel-Versand ueber alle aktiven Touren. Nur dieser eine Test-Trip darf eine Mail
   erhalten.
3. **IMAP-Pruefung gegen Stalwart:** Posteingang von `gregor-test@henemm.com` auf
   `mail.henemm.com` abrufen (Credentials aus den Settings, nicht im Klartext hier).
   Pruefen: Subject mit Trip-Name + Report-Typ, HTML-Body nicht leer, Wetter-Tabelle
   vorhanden, Werte plausibel, Timestamp NACH dem Versand.

Inhaltliche Tiefe via Spec-Validator (liest dieselbe Test-Mail):

```bash
uv run python3 .claude/hooks/email_spec_validator.py
```

**STOP wenn:** Validator nicht Exit 0.

## Schritt 4: Test-Trip aufraeumen

Den auf Staging angelegten Test-Trip wieder loeschen, damit Staging sauber bleibt.

## Schritt 5: Nachweis schreiben

NUR wenn alle relevanten Schritte erfolgreich waren — als Nachweis fuer den
Pre-Prod-Schritt:

```bash
python3 -c "
import json, datetime
data = {
    'verified_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'environment': 'staging',
    'scope': 'frontend-only',  # oder 'backend' / 'full-stack'
    'checks': ['staging_smoke', 'visual'],  # backend zusaetzlich: 'test_trip', 'test_mail', 'imap'
    'feature_checks': ['HIER BESCHREIBEN WAS GEPRUEFT WURDE']
}
with open('.claude/e2e_verified.json', 'w') as f:
    json.dump(data, f, indent=2)
print('e2e_verified.json geschrieben')
"
```

## VERBOTEN

- Den lokalen Produktiv-API-Port (8090) beenden oder beschiessen.
- Die Go-API lokal als eigenen Prozess hochfahren, um gegen `localhost` zu testen.
- Einen Sammel-Versand ueber alle aktiven Touren ausloesen — nur der eine Test-Trip
  darf eine Mail erhalten, Empfaenger ausschliesslich `gregor-test@henemm.com`.
- IMAP gegen ein Gmail-Postfach pruefen — Stalwart (`mail.henemm.com`) ist die Quelle.
- In einen laufenden Systemd-Prozess von Live oder Staging eingreifen
  (stoppen/starten/neu starten).
- Produktiv-Trips fuer den Test verwenden.
- Den Nachweis schreiben, ohne die relevanten Schritte tatsaechlich durchlaufen zu haben.
