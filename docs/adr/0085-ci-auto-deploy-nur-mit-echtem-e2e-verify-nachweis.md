# ADR-0085: CI-Auto-Deploy nur mit echtem `/e2e-verify`-Nachweis

- **Status:** Akzeptiert
- **Datum:** 2026-10-06
- **Bezug:** GitHub-Issue #2047 Scheibe 2 (PR #2516 und Ergänzung S2b), Spec
  `docs/specs/modules/fix_2047_s2_ci_prod_gate.md`; ergänzt ADR-0006 (keine Mock-Tests,
  E2E gegen Staging)

## Kontext

ADR-0006 legt fest, dass Verhalten gegen Staging nachgewiesen wird, bevor Produktion es bekommt.
Der CI-Job `deploy` hat diesen Nachweis früher selbst geschrieben und den Haupt-Checkout per
`git reset --hard` umgestellt. Damit hat er sich selbst attestiert. Nach #2516 liest die CI nur
noch. Offen blieb: Liefern CI und Session (`/70-deploy`) denselben Stand aus, starten die Dienste
doppelt neu; zwei Merges konnten gleichzeitig ausliefern; im CI-Pfad lief kein
Post-Deploy-Selbsttest.

## Entscheidung

- **Die CI schreibt nie einen Nachweis.** Erzeugt wird `.claude/e2e_verified/<sha>.json` allein
  durch `/e2e-verify` gegen Staging.
- **Einmal prüfen, nicht warten:** Schritt `gate` (`scripts/ci_prod_gate.sh`) entscheidet einmalig
  `open`/`closed`. Bei `closed` gibt es eine Notice und eine Step-Summary, keinen Deploy und keine
  Telegram-Meldung. Der Normalfall bleibt `/70-deploy` aus der Session.
- **Idempotente Auslieferung:** `deploy-gregor-prod.sh` (henemm-infra) vergleicht innerhalb des
  `flock`, nach `git fetch origin`, `deployed_commit` aus `.claude/last_prod_deploy.json` mit
  `origin/main`. Bei Gleichheit gibt es die Meldung „bereits ausgeliefert" und Exit 0, ohne
  Dienstaktion. Notausgang `GZ_FORCE_REDEPLOY=1` (protokolliert in `.claude/deploy-overrides.log`).
- **Serialisierung:** `concurrency: {group: prod-deploy, cancel-in-progress: false}`.
- **Selbsttest:** Nach jeder CI-Auslieferung läuft `prod_selftest.py` per ssh im Hauptordner.
  Exit ≠ 0 macht den Job rot.
- **Telegram:** genau eine von drei Meldungen („deployed", „bereits ausgeliefert",
  „FEHLGESCHLAGEN").

## Verworfene Alternativen

- **CI wartet bis zu 60 Minuten auf den Nachweis** (`ci_wait_for_verdict.sh`, Spec-Fassung 1.0):
  belegt Runner-Zeit und verschiebt das Problem nur. Mit #2516 überholt.
- **Idempotenz über `LOCAL == origin/main`:** Der Ordner kann auf dem Zielstand stehen, ohne dass
  die Dienste neu gestartet wurden. Deshalb ist der Deploy-Marker die Quelle.

## Folgen

- Kein doppelter Dienst-Neustart für denselben Stand.
- Ein manuell verändertes `last_prod_deploy.json` würde den Kurzschluss täuschen. Dafür gibt es
  den Notausgang.
- Das Kopplungs-Literal „bereits ausgeliefert" verbindet Skript und `ci.yml`. Beide Testdateien
  bewachen es.
