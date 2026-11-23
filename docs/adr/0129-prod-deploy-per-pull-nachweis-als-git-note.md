# ADR-0129: Prod-Deploy per Pull, Nachweis als Git-Note

- **Status:** Akzeptiert (Spec freigegeben vom PO 2026-11-23)
- **Datum:** 2026-11-23
- **Bezug:** Issue #3289, Spec `docs/specs/modules/prod_pull_deploy.md`, Kontext `docs/context/feat-3289-pull-deploy.md`. Schreibt fort: [ADR-0085](0085-ci-auto-deploy-nur-mit-echtem-e2e-verify-nachweis.md) (CI-Deploy nur mit echtem Nachweis), [ADR-0098](0098-liefer-workflow-pr-statt-direkt-push.md) (Liefer-Workflow), [ADR-0099](0099-autonomer-deploy-ohne-freigabe-halt.md) (autonomer Deploy). Löst keines davon ab.

## Kontext

Der Staging-Nachweis (`/e2e-verify`) lag nur als Datei `.claude/e2e_verified/<sha>.json` im Haupt-Checkout des Servers. Eine Sitzung außerhalb des Servers (iMac, Cloud) konnte ihn weder dort ablegen noch Prod ausliefern; der Prod-Deploy war ein manueller Schritt (`/70-deploy`). Der CI-Job `deploy` sieht beim Merge meist noch keinen Nachweis, weil der erst nach dem Staging-Deploy entsteht. Gate (`staging_gate.py --check`, Vorfahren-Regel #1382) und Selbsttest (`prod_selftest.py`) brauchen das volle Nachweis-JSON (`verdicts`, `langs`, `findings`).

## Entscheidung

1. **Transport als Git-Note.** `staging_gate.py --write-verdict` hängt den Nachweis nach dem lokalen Schreiben byte-gleich als Note unter `refs/notes/e2e-verified` an den verifizierten Commit und pusht die Notes-Ref nach `origin` (ohne Force, bei abgelehntem Push bis zu drei Versuche mit frischem Fetch; fremde Notes bleiben erhalten). Scheitert die Veröffentlichung, endet der Befehl mit Exit ≠ 0. `GZ_E2E_PUBLISH=0` schaltet nur das Veröffentlichen ab und ist für Tests bestimmt.
2. **Ablage auf dem Server unverändert.** `scripts/e2e_nachweis_holen.py <repo>` holt die Notes-Ref und legt für `origin/main` und seine letzten 40 Vorfahren die Note als die gewohnte Datei ab, nur wenn `verified_commit` der Note dem Commit entspricht (fail-closed). `scripts/ci_prod_gate.sh` ruft es vor dem Gate auf; CI-Job und Timer sehen denselben Nachweis. Gate, Vorfahren-Regel und Selbsttest bleiben unverändert. Präzisierung zu ADR-0085: der CI-Pfad erzeugt weiterhin nie einen Nachweis, er legt nur einen auf `origin` veröffentlichten ab.
3. **Pull-Auslöser auf dem Server.** `henemm-infra/scripts/pull-deploy-gregor-prod.sh` läuft alle 5 Minuten (Cron, eigenes flock): gleicher Stand wie zuletzt ausgeliefert → nur Heartbeat; Gate zu → Logzeile „wartet auf Nachweis für <sha>“ und Heartbeat (Normalfall); Gate offen → `deploy-gregor-prod.sh`, danach `prod_selftest.py`. Ohne Nachweis wird nie ausgeliefert.
4. **Rückmeldung per Commit-Status.** Der Timer setzt am Ziel-Commit den Status `deploy/prod` (`success` mit Live-SHA, sonst `failure`). Bei Fehlschlag geht genau ein Alarm der Stufe `high` je SHA per Claude MQ raus, kein Heartbeat, kein erneuter Versuch für dieselbe SHA, bis ein neuer Stand auf `main` liegt oder `GZ_FORCE_REDEPLOY=1` gesetzt ist.
5. **Sitzungen außerhalb des Servers** deployen nicht selbst: `/70-deploy` wartet auf `deploy/prod` am Ziel-Commit und schließt das Issue erst bei `success`. `/e2e-verify` läuft dort per `ssh henemm` im Staging-Checkout; die Sitzung misst weiterhin selbst. Auf dem Server bleibt der direkte Weg (`deploy-gregor-prod.sh` + Selbsttest) erlaubt.

## Verworfene Alternativen

- **Commit-Status als Nachweis-Transport** — trägt nur 140 Zeichen Beschreibung; Gate und Selbsttest brauchen das volle JSON. Ein zweiter, gekürzter Nachweis wäre eine zweite Wahrheit.
- **Push-Deploy per SSH aus der Sitzung** — verlangte einen Zugang zum Prod-Server auf iMac und Cloud.
- **Manueller Auslöser wie bisher** — eine Sitzung außerhalb des Servers käme nie bis live.

## Konsequenzen

- **Positiv:** Ein Ticket läuft von jedem Rechner bis live; der Nachweis ist an die SHA gebunden, versioniert und löst keinen CI-Lauf aus. Hard Gates (Nachweis je Stand, Selbsttest) und Autonomie (ADR-0099) bleiben.
- **Negativ / Preis:** Vertrauensstufe der Notes = Schreibrecht im Repo (wie bisher: wer pushen darf, darf attestieren). Bis zu 5 Minuten Verzug zwischen Nachweis und Auslieferung. Nach einem Fehlschlag gibt es bewusst keinen automatischen Wiederholversuch.
- **Folgepflichten:** Der Timer braucht einen BetterStack-Heartbeat (Ping nur bei fachlich sauberem Lauf). Doppel-Deploy von CI-Job und Timer bleibt unschädlich, solange beide über `deploy-gregor-prod.sh` (flock, idempotent über `last_prod_deploy.json`) laufen.
