# Deploy to Production

Deploy current main to production via henemm-infra deploy script.

## Ablauf (alles in dieser Session, kein Warten auf Cron)

```
1. Staging-Deploy sofort triggern
2. ~90 Sekunden warten bis Build durch
3. E2E gegen Staging ausführen (/e2e-verify)
4. Tech-Lead-Brief ausgeben (erst nach E2E VERIFIED)
5. Auf 'go' warten
6. Prod-Deploy
7. Issue schließen
```

---

## Schritt 1: Staging-Deploy sofort triggern

Nicht auf den 5-Minuten-Cron warten — Deploy jetzt starten:

```bash
bash /home/hem/henemm-infra/scripts/auto-deploy-gregor-staging.sh
```

Das Script prüft selbst ob etwas zu deployen ist. Falls Staging schon aktuell ist,
kommt sofort Exit 0 — dann direkt zu Schritt 2.

## Schritt 2: Auf Staging-Deploy warten

```bash
# Commit auf Staging prüfen
EXPECTED=$(git rev-parse HEAD)
for i in 1 2 3 4 5; do
  STAGING=$(curl -s https://staging.gregor20.henemm.com/api/health | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('commit','?'))" 2>/dev/null)
  echo "Staging: $STAGING | Erwartet: ${EXPECTED:0:7}"
  [ "${STAGING:0:7}" = "${EXPECTED:0:7}" ] && echo "✓ Staging aktuell" && break
  echo "Warte 30s..."
  sleep 30
done
```

Falls nach 5 Versuchen (2,5 Min) noch nicht aktuell: Staging-Logs prüfen.

## Schritt 3: E2E gegen Staging ausführen

Rufe das Skill `/e2e-verify` auf. **Kein Weitergehen bis Verdict = VERIFIED.**

- Bei VERIFIED → Schritt 4
- Bei BROKEN → Fehler beheben, neu pushen, Schritt 1 wiederholen
- Bei AMBIGUOUS → Findings prüfen, ggf. trotzdem weitermachen mit Begründung

## Schritt 4: Tech-Lead-Brief ausgeben

**Erst nach E2E VERIFIED:**

---

**Was wurde gebaut:** [1-2 Sätze aus Nutzerperspektive — was kann der Nutzer jetzt tun, was vorher nicht ging?]

**Staging validiert:** [staging_verdict aus e2e_verified.json] — [verified_at]

**Tests:** [N] bestanden, 0 fehlgeschlagen

**Offene Punkte:** [keine] ODER [Issue #N wurde erstellt für: X]

**Risiko:** niedrig / mittel / hoch — [1 Satz Begründung]

**Empfehlung:** Deploy auf Production.

Sage **'go'** um zu deployen.

---

## Schritt 5: Pre-Flight + Prod-Deploy (nach 'go')

```bash
git branch --show-current      # muss "main" sein
git status --porcelain         # muss leer sein
```

```bash
bash /home/hem/henemm-infra/scripts/deploy-gregor-prod.sh
```

## Schritt 6: Post-Deploy-Smoke

```bash
curl https://gregor20.henemm.com/api/health
```

## Schritt 7: Issue schließen

```bash
gh issue close <ISSUE_NR> --comment "Fertig und live — $(git rev-parse --short HEAD) auf Production."
```

Danach dem User mitteilen:

**Fertig und live.** Issue #N — [Titel] ist abgeschlossen.
Was geliefert wurde: [1-2 Sätze Nutzerperspektive]

**NICHT früher "Fertig und live" sagen.**

---

## Rollback

```bash
git revert HEAD && git push origin main
bash /home/hem/henemm-infra/scripts/deploy-gregor-prod.sh
```

## Drift-Detection

`check-gregor20.sh` (cron alle 5min) vergleicht Binary-mtime mit `origin/main`-Commit-Zeit.
Bei Drift > 1h → BetterStack-Alert via Telegram.
