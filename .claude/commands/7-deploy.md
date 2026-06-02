# Deploy to Production

Deploy current main to production via henemm-infra deploy script.

## Schritt 0: E2E-Verifikation (ZWINGEND ZUERST — vor Brief, vor allem)

**Der Tech-Lead-Brief darf erst ausgegeben werden, wenn E2E VERIFIED ist.**
Das ist der einzige echte Nachweis, dass der Code auf Staging funktioniert.

### 0a. Prüfen ob E2E bereits für diesen Commit läuft

```bash
HEAD=$(git rev-parse HEAD)
python3 -c "
import json, sys
try:
    d = json.load(open('.claude/e2e_verified.json'))
    if d.get('verified_commit') == '$HEAD' and d.get('staging_verdict','').startswith('VERIFIED'):
        print('E2E bereits VERIFIED für', '$HEAD'[:7])
    else:
        print('E2E FEHLT oder veraltet — muss jetzt laufen')
        sys.exit(1)
except FileNotFoundError:
    print('e2e_verified.json nicht vorhanden — muss jetzt laufen')
    sys.exit(1)
"
```

### 0b. Falls E2E fehlt oder veraltet: JETZT ausführen

Rufe das Skill `/e2e-verify` auf. **Nicht weitergehen bis Verdict = VERIFIED.**

Staging-Auto-Deploy läuft alle 5 Minuten. Falls noch nicht durch:
```bash
# Warten bis Staging den neuen Commit hat
EXPECTED=$(git rev-parse HEAD)
curl -s https://staging.gregor20.henemm.com/api/health | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('commit','?'))"
```
Wenn der Commit noch nicht übereinstimmt: 2 Minuten warten, nochmal prüfen.

**STOP bei BROKEN oder wenn E2E nicht durchführbar.** Fehlerbehebung zuerst.

### 0c. E2E-Ergebnis für den Brief notieren

Aus `.claude/e2e_verified.json` auslesen:
- `staging_verdict` → für "Staging validiert"-Zeile im Brief
- `verified_at` → Zeitstempel

---

## Tech-Lead-Brief für den PO (erst nach E2E VERIFIED ausgeben)

**Was wurde gebaut:** [1-2 Sätze aus Nutzerperspektive — was kann der Nutzer jetzt tun, was vorher nicht ging?]

**Staging validiert:** [staging_verdict aus e2e_verified.json] — [verified_at]

**Tests:** [N] bestanden, 0 fehlgeschlagen

**Offene Punkte:** [keine] ODER [Issue #N wurde erstellt für: X]

**Risiko:** niedrig / mittel / hoch — [1 Satz Begründung, z.B. "nur Frontend, kein Daten-Schema berührt"]

**Empfehlung:** Deploy auf Production.

Sage **'go'** um zu deployen.

**Erst nach Bestätigung durch den PO die Pre-Flight Checks starten!**

## Pre-Flight Checks

```bash
git branch --show-current        # muss "main" sein
git status --porcelain           # muss leer sein
git fetch origin main
git log HEAD..origin/main --oneline  # zeigt was deployt wird
```

**STOP wenn:**
- Branch != main → erst checkout main
- Uncommitted Changes → erst committen oder stashen
- Tests rot → erst fixen

## Production-Deploy

```bash
bash /home/hem/henemm-infra/scripts/deploy-gregor-prod.sh
```

Was das Skript macht:
1. Pre-Flight (Branch, Uncommitted Changes)
2. `git pull origin main`
3. `go build -o gregor-api ./cmd/server`
4. `npm install && npm run build` im Frontend
5. `systemctl restart gregor-python` → `gregor-api` → `gregor-frontend` (in dieser Reihenfolge mit Sleeps)
6. Smoke-Test gegen `https://gregor20.henemm.com/`
7. Live-Commit-Hash ausgeben

## Post-Deployment Verification

1. **Healthcheck:**
   ```bash
   curl https://gregor20.henemm.com/api/health
   bash /home/hem/henemm-infra/scripts/check-gregor20.sh  # alert bei Code-Drift
   ```

2. **Browser-Test:** Geänderte Funktionalität öffnen und prüfen.

3. **Logs überwachen:**
   ```bash
   journalctl -u gregor-api -u gregor-python -u gregor-frontend -f --since "5 minutes ago"
   ```

## Abschluss: Issue schließen + "Fertig und live"

**Erst hier** — nach bestätigtem Prod-Deploy — das GitHub Issue schließen und dem User Bescheid geben:

```bash
gh issue close <ISSUE_NR> --comment "Fertig und live — $(git rev-parse --short HEAD) auf Production."
```

Danach dem User mitteilen:

> **Fertig und live.** Issue #N — [Titel] ist abgeschlossen.
> Was geliefert wurde: [1-2 Sätze Nutzerperspektive]

**NICHT früher "Fertig und live" sagen — nicht nach /6-validate, nicht nach Push, nicht wenn Staging noch nicht deployt hat.**

## Rollback

```bash
cd /home/hem/gregor_zwanzig
git revert HEAD
git push origin main
bash /home/hem/henemm-infra/scripts/deploy-gregor-prod.sh
```

## Drift-Detection

`check-gregor20.sh` (cron alle 5min) vergleicht Binary-mtime mit `origin/main`-Commit-Zeit. Bei Drift > 1h → BetterStack-Alert via Telegram. Selbst wenn der Deploy vergessen wird, fängt das Monitoring es.

## Konvention

**Nach jedem Feature/Bug der live gehen soll:** Dieses Skill ausführen. Sonst rennt Production hinter Staging her.
