# Deploy to Production (Gregor Zwanzig)

Ablauf: Push → Staging warten (echt) → E2E-Validierung → Prod-Deploy → Selftest → Issue schließen.

## Schritt 1: Pre-Flight

```bash
git branch --show-current          # muss main sein
git status --porcelain             # muss leer sein
git fetch origin main
git log HEAD..origin/main --oneline  # muss leer sein
```

**STOP wenn:** uncommittete Änderungen, main hinter origin, oder Tests rot.

## Schritt 2: Push

```bash
git push origin main
DEPLOY_COMMIT=$(git rev-parse HEAD)
echo "Deploy-Commit: $DEPLOY_COMMIT"
```

## Schritt 3: Auf Staging-Deploy warten (ECHT — kein Fake-Wait)

Staging-Cron läuft alle 5 Minuten. Statt „ich warte 5 Minuten" zu behaupten,
dieses Script im Hintergrund starten und mit Monitor beobachten:

```bash
# Im Hintergrund starten (run_in_background=True):
EXPECTED="$DEPLOY_COMMIT"
STAGING_CLONE=/home/hem/gregor_zwanzig_staging
MAX=20  # 20 × 30s = 10 Minuten Timeout

for i in $(seq 1 $MAX); do
    CURRENT=$(cd "$STAGING_CLONE" && git log -1 --format=%H 2>/dev/null || echo "unknown")
    if [ "$CURRENT" = "$EXPECTED" ]; then
        echo "STAGING_READY: ${EXPECTED:0:8} ist live auf Staging"
        exit 0
    fi
    echo "Warte ($i/$MAX) — Staging: ${CURRENT:0:8}, Erwartet: ${EXPECTED:0:8}"
    sleep 30
done

echo "STAGING_TIMEOUT: Staging hat nach 10 Minuten nicht deployed"
exit 1
```

**Anweisung an Claude:** Dieses Script mit `Bash(run_in_background=True)` starten,
dann `Monitor` aufrufen und auf "STAGING_READY" oder "STAGING_TIMEOUT" warten.
Erst wenn Monitor "STAGING_READY" meldet, weiter mit Schritt 4.
Bei "STAGING_TIMEOUT": Staging-Cron und Logs prüfen, nicht blind weiter.

## Schritt 4: Smoke-Check Staging

```bash
curl -sf https://staging.gregor20.henemm.com/ -o /dev/null -w "%{http_code}"
curl -sf https://staging.gregor20.henemm.com/api/health
```

Beide müssen 200 zurückgeben. Dann `/e2e-verify` ausführen.

## Schritt 5: Prod-Deploy

Nur wenn Staging-Verdict mit "VERIFIED" beginnt (Gate in `e2e_verified.json`):

```bash
bash /home/hem/henemm-infra/scripts/deploy-gregor-prod.sh
```

## Schritt 6: Post-Deploy-Selftest

```bash
python3 .claude/hooks/prod_selftest.py
```

Nur bei Exit 0 weiter. Bei PARTIAL/FAIL: Bericht in `docs/artifacts/` prüfen,
ggf. Rollback einleiten.

## Schritt 7: Issue schließen

```bash
gh issue close <N>
```

Nur wenn Selftest Exit 0.
