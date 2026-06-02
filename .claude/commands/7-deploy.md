# Deploy to Production

Deploy current main to production via henemm-infra deploy script.

## Tech-Lead-Brief für den PO (PFLICHT — vor allem anderen ausgeben)

Bevor du irgendeinen Deploy-Schritt ausführst, gib diesen Brief aus:

**Was wurde gebaut:** [1-2 Sätze aus Nutzerperspektive — was kann der Nutzer jetzt tun, was vorher nicht ging?]

**Staging validiert:** ja — [Datum/Uhrzeit des letzten Staging-Checks]

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

## Staging-Validierung (Pflicht!)

Staging deployt automatisch (Cron alle 5min, `auto-deploy-gregor-staging.sh`).

```bash
# Staging-Status prüfen
curl -s https://staging.gregor20.henemm.com/api/health
# Manuell im Browser: https://staging.gregor20.henemm.com
```

**Erst weitermachen wenn Staging die geänderte Funktionalität korrekt zeigt.**

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
