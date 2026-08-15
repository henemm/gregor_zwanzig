# Context: fix-1872-deploy-branch-checkout

## Request Summary
`deploy-gregor-prod.sh` verweigert den Prod-Deploy, wenn `/home/hem/gregor_zwanzig`
(REPO_DIR) nicht auf `main` steht — obwohl der Zielstand (`origin/main`) vollständig
verifiziert, gemergt und attestiert ist. Eine worktree-isolierte Sitzung kann die
Vorbedingung strukturell nicht selbst herstellen (Isolations-Wächter verweigert jeden
Zugriff auf den geteilten Ordner). Am 2026-08-15 zweimal aufgetreten (#1750, laut
Memory auch #1856 E7) — kein Einzelfall.

## Related Files

| Datei | Relevanz |
|---|---|
| `henemm-infra/scripts/deploy-gregor-prod.sh:37,130-198` | `REPO_DIR="/home/hem/gregor_zwanzig"`, Branch-Check (130-135) bricht ab statt herzustellen; Stash-Safety-Netz (152-159) existiert bereits, aber NACH dem Branch-Check |
| `henemm-infra/scripts/auto-deploy-gregor-staging.sh:6` | **Vorbild:** `REPO_DIR="/home/hem/gregor_zwanzig_staging"` — bereits dedizierter Checkout, nie von Sessions berührt → Staging hat dieses Problem strukturell nie |
| `henemm-infra/systemd/gregor-{python,api,frontend}.service` | `WorkingDirectory=/home/hem/gregor_zwanzig[/frontend]`, `gregor-api` zusätzlich `ExecStart=/home/hem/gregor_zwanzig/gregor-api` — bestätigt: REPO_DIR ist real der Live-Serving-Root, kein bloßer Checkout |
| `henemm-infra/systemd/*.service.d/hardening.conf:18` | `ReadWritePaths=/home/hem/gregor_zwanzig/data …` — evtl. bereits veraltet seit der Datenwurzel-Migration nach `/var/lib` (#1595), separat zu prüfen |
| `henemm-infra/scripts/check-gregor20.sh:93` | Drift-Check nutzt REPO_DIR für Commit-Vergleich — misst aktuell nur zufällig richtig, wenn der Session-Ordner gerade auf `main` steht |
| `.claude/hooks/staging_gate.py:54` (`_DEFAULT_REPO_DIR`) | Hardcoded, genutzt für HEAD-Ermittlung/Attestation-Pfadauflösung — Test-Override existiert (Monkeypatch), aber KEIN Env-Override für echten Betrieb |
| `.claude/hooks/prod_selftest.py:56` (`REPO_DIR`) | Hardcoded, kein Override-Mechanismus — genutzt für Scope-Diff, `docs/artifacts/`-Reportpfad, `.env`-Lesen, Telegram-Codecheck |
| `henemm-infra/scripts/sync-staging-validator-creds.sh:25` | Schreibt `validator.env` — müsste einen neuen Prod-Checkout mitversorgen, falls der die Gates selbst aufruft |
| `CLAUDE.md:227` | Behauptet bereits „diese Pattsituation existiert nicht mehr" — genau diese Aussage widerlegt das Issue; muss nach dem Fix entweder wahr gemacht oder korrigiert werden |

## Existing Patterns

- **Staging löst das Problem bereits strukturell**, nicht durch Disziplin: dedizierter
  Checkout (`gregor_zwanzig_staging`), den keine interaktive Session je betritt. Die vom
  PO im Issue empfohlene Option 1 (dedizierter Deploy-Checkout) ist damit kein Neuland,
  sondern die Übertragung eines bereits produktiv bewährten Musters von Staging auf Prod.
- Das Skript hat bereits ein Sicherungsnetz für uncommittete Arbeit (`git stash create`
  + Tag `deploy-safety/<zeit>`, Zeile 152-159) — dieses Muster ließe sich (Option 2)
  auch auf den Branch-Wechsel selbst ausdehnen (`git switch main` vor dem Reset), analog
  zur bestehenden Begründung im Kopfkommentar der Datei.
- Persistenz ist bereits vom REPO_DIR entkoppelt: Prod-Daten liegen seit #1595 unter
  `/var/lib/gregor/users`, nicht mehr unter `REPO_DIR/data`. Das senkt das Risiko einer
  Checkout-Migration erheblich — kein Datenumzug nötig, nur Code/Build-Artefakte.

## Dependencies

- **Upstream (was REPO_DIR voraussetzt):** 3 systemd-Units, `hardening.conf`
  (`ReadWritePaths`), `deploy-gregor-prod.sh` selbst, `check-gregor20.sh` (Drift-Messung),
  zwei `.claude/hooks/*.py`-Module mit hardcodiertem Pfad, `sync-staging-validator-creds.sh`.
- **Downstream/verwandt (nicht zwingend im Scope, gleiche Fehlerklasse):** Ein Cronjob
  (`15 4 * * *`) `cd`t ebenfalls in `/home/hem/gregor_zwanzig`, um
  `setup_staging_validator_trip.py` auszuführen — hängt damit vom selben
  Session-Branch-Zustand ab. Nicht Teil der gemeldeten Beschwerde (betrifft Staging-Setup,
  nicht den Prod-Deploy-Abbruch), aber dieselbe Fehlerklasse. Kandidat für #1199
  (Nebenbefund-Sammlung), kein eigenes Issue.
- `check-gregor20.sh:530,586` liest `.env` aus REPO_DIR — ob diese bei einer Checkout-
  Trennung mitwandert oder geteilt bleibt, ist ungeklärt (kein Blocker, aber Klärungspunkt
  für die Spec).

## Existing Specs
Keine — reines Infra-Skript (`henemm-infra`), kein `docs/specs/modules/`-Eintrag in
`gregor_zwanzig`. Kein ADR zu Deploy-Strategie vorhanden (`docs/adr/README.md` nennt
„Test-/Deploy-Strategie" nur als Kriterium, keine existierende Entscheidung).

## Entscheidung (PO, 2026-08-15)

Hybrid: **Option 2 jetzt** als Scope dieses Workflows (Selbstheilung: `git switch main`
im bestehenden Sicherheitsnetz von `deploy-gregor-prod.sh`, vor dem `git reset --hard
origin/main`). **Option 1** (dedizierter Prod-Checkout) als eigenes Folge-Issue
[henemm-infra#193](https://github.com/henemm/henemm-infra/issues/193) — Begründung dort:
9+ Fundstellen, einmaliger Dienst-Cutover, ADR-pflichtige Deploy-Strategie-Entscheidung.

## Risks & Considerations

1. **Scope-Frage Option 1 vs. 2 vs. 3** (aus dem Issue „nicht entschieden", PO empfiehlt
   Option 1): Option 1 (dedizierter Checkout) ist die robustere, strukturelle Lösung mit
   Staging-Präzedenz, aber berührt 9 Fundstellen in `henemm-infra` + 2 Hooks in
   `gregor_zwanzig` — eine echte, wenn auch kleine Infra-Migration mit einmaligem Cutover
   (neuer Checkout anlegen, Dienste umhängen), nicht ein Ein-Zeilen-Fix. Option 2
   (`git switch main` im bestehenden Sicherheitsnetz) ist eine ~10-Zeilen-Änderung in
   EINER Datei, behebt das gemeldete Symptom vollständig, lässt aber die Kopplung
   „Prod-Deploy hängt am Zustand des Session-Ordners" strukturell bestehen — künftige neue
   Abhängigkeiten könnten dieselbe Fehlerklasse erneut einführen.
2. **Kein Downtime-Risiko bei Option 2** (reine Skript-Logik-Änderung, kein Dienst-Umzug).
   **Reales, aber beherrschbares Cutover-Risiko bei Option 1** (Dienste müssen einmalig auf
   neuen Pfad umgehängt werden — analog zum bereits gelösten Frontend-Release-Symlink-
   Muster, aber diesmal für den gesamten Checkout).
3. Falls Option 1: `hardening.conf` `ReadWritePaths` und `check-gregor20.sh` `.env`-Lesen
   brauchen vor dem Cutover Klärung, sonst bricht entweder systemd-Sandboxing oder das
   Monitoring still.
4. CLAUDE.md Zeile 227 muss nach dem Fix aktualisiert werden — sonst bleibt die (aktuell
   falsche) Behauptung „Pattsituation existiert nicht mehr" stehen.
