---
issue_id: 101
title: "Auto-Rebuild Go-Binary nach Code-Änderungen"
created: 2026-04-29
status: analyzed
---

# Context: Issue #101 — Deploy-Pipeline

## Ist-Zustand

| Environment | Pfad | Auto-Deploy? |
|-------------|------|--------------|
| **Staging** | `/home/hem/gregor_zwanzig_staging` | ✅ `auto-deploy-gregor-staging.sh` alle 5min via cron |
| **Production** | `/home/hem/gregor_zwanzig` | ❌ KEIN Auto-Deploy. Manuell. |

**Cron (`crontab -l`):**
```
*/5 * * * * /home/hem/henemm-infra/scripts/auto-deploy-gregor-staging.sh
```

Das **fehlende Production-Pendant** ist die direkte Ursache von Bug #95: Wenn niemand manuell `go build && systemctl restart gregor-api` ausführt, läuft alter Code weiter.

## Wie das Staging-Skript es richtig macht

`auto-deploy-gregor-staging.sh` (Referenz):
1. `git fetch origin` + Diff-Check (kein unnötiger Restart)
2. `git pull origin main`
3. `go build -o gregor-api ./cmd/server`
4. `cd frontend && npm install && npm run build`
5. `sudo systemctl restart gregor-python-staging` (3s sleep)
6. `sudo systemctl restart gregor-api-staging` (2s sleep)
7. `sudo systemctl restart gregor-frontend-staging` (3s sleep)
8. Smoke-Test gegen `https://staging.gregor20.henemm.com/`
9. Heartbeat ping bei Erfolg

## Optionen für Production

### Option A: Auto-Deploy für Prod (analog Staging)
- Pro: Kein Forgetting möglich, Code aus main ist immer live
- Contra: Bricht Prinzip "main → Staging → Promote → Prod". Untestet code geht direkt live.

### Option B: Manuelles Promote-Skript
- Skript `deploy-gregor-prod.sh`, manuell aufrufen wenn Staging validiert ist
- Macht denselben Build + Restart wie Staging-Skript
- Pro: Explizite Promotion, kein versehentlicher Live-Push
- Contra: Manueller Schritt → kann vergessen werden (siehe Bug #95)

### Option C: Promote nach Branch (z.B. `production`)
- Prod-Auto-Deploy zieht nur von Branch `production`, nicht `main`
- Manueller Merge `main → production` ist die Promote-Aktion
- Pro: Atomarer Promote-Akt, klar dokumentiert via Git
- Contra: Mehr Branching-Komplexität

### Option D: Tag-basiert
- Prod-Auto-Deploy zieht nur Tags (z.B. `v*.*.*` oder `prod-*`)
- Tag = Promote
- Pro: Versionierung gleich mit drin
- Contra: Discipline-abhängig

## Cross-Repo-Audit (TODO)

Gleicher Bug-Typ möglich in:
- `henemm-n8n` — wie wird n8n-Config nach Pull aktualisiert?
- `oebb-nightjet-monitor` — Go-Binary, gleiches Pattern?

## Empfehlung (zur Diskussion)

**Option B** für sofortigen Fix, danach **Option C** evaluieren.

Konkret:
1. **Sofort:** `auto-deploy-gregor-staging.sh` zu `deploy-gregor-prod.sh` adaptieren (Pfade, Service-Namen ohne `-staging`-Suffix). NICHT in cron, sondern manuell.
2. **CLAUDE.md update:** Nach jedem Production-Deploy MUSS dieses Skript laufen. Hook im 7-deploy-Skill?
3. **Mittelfristig:** Branch-Strategie evaluieren (Option C) für saubere Promote-Semantik.

## Files to Change

| # | File | Action | Repo |
|---|------|--------|------|
| 1 | `scripts/deploy-gregor-prod.sh` | CREATE | henemm-infra |
| 2 | `CLAUDE.md` (Deploy-Sektion) | MODIFY | gregor_zwanzig |
| 3 | `.claude/skills/7-deploy.md` | MODIFY | gregor_zwanzig (falls existiert) |

## Risiken

| Risk | Mitigation |
|------|------------|
| Skript bricht Production beim ersten Run | Smoke-Test eingebaut, sudo-Restart-Reihenfolge wie Staging |
| User vergisst Skript zu laufen (gleicher Bug wie #95) | Doku in CLAUDE.md, Reminder im Deploy-Skill, ggf. Telegram-Alert wenn Prod-Code-Hash != Live-Hash |
| Concurrent Pull während Build | Lock-File analog Staging? |
