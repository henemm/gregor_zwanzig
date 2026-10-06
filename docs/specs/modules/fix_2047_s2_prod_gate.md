---
entity_id: fix_2047_s2_prod_gate
type: module
created: 2026-10-06
updated: 2026-10-06
status: draft
version: "1.0"
tags: [ci, deploy, gate, staging]
---

# #2047 Scheibe 2 — Prod-Gate wirksam machen

## Approval

- [ ] Approved

## Purpose

Der CI-Job `deploy` schreibt sich heute seinen Staging-Nachweis selbst
(`--write-verdict 'VERIFIED: CI smoke test (ROOT+HEALTH) passed'`) und liefert eine Zeile
später damit nach Produktion aus. Das Hard Gate prüft sich damit selbst ab. Nach dieser Scheibe
schreibt die CI **keinen** Nachweis mehr. Sie liefert nur aus, wenn für den Zielstand bereits ein
echter `/e2e-verify`-Nachweis vorliegt. Fehlt er, überspringt sie den Prod-Deploy sichtbar, und
die Auslieferung läuft über `/70-deploy` Schritt 4. Dazu kommt C4-71: Der Deploy hängt an
**allen sechs** Ampel-Checks statt nur an `test` und `lint`.

PO-Entscheide: 2026-08-21 („Weg A mit Automatisierung“) und 2026-10-05 (Rest-Scope: „Die CI darf
keinen eigenen Verdict mehr schreiben, sie verlangt einen echten `/e2e-verify`-Nachweis für den
SHA“ + C4-71).

## Source

- **File:** `.github/workflows/ci.yml` — Job `deploy`
- **File (neu):** `scripts/ci_prod_gate.sh` — Gate-Entscheidung, auf dem Server im
  Haupt-Checkout ausgeführt
- **Identifier:** `staging_gate.py --check --expected-commit` (unverändert, wird nur aufgerufen)

## Estimated Scope

- **LoC:** ~60 Code (Skript + ci.yml) + ~150 Tests
- **Files:** 3 Code/Test + Doku (CLAUDE.md, `.claude/commands/70-deploy.md`,
  `docs/reference/operations_playbook.md`, `docs/reference/gates_und_ratschen.md`)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `.claude/hooks/staging_gate.py` | Hook | `--check --expected-commit <ziel>` — dieselbe Prüfung, die `deploy-gregor-prod.sh` im Preflight fährt |
| `henemm-infra/scripts/deploy-gregor-prod.sh` | Infra | unverändert; prüft den Nachweis zusätzlich selbst |
| `scripts/wip_safety.sh` | Skript (Scheibe 1) | entfällt im CI-Pfad, weil der `reset --hard` dort entfällt; bleibt im Repo |

## Implementation Details

### Was entfällt

Der Schritt `Staging-Verdict schreiben (CI smoke)` fällt **ersatzlos** weg, mit ihm:

- das Schreiben der Findings-JSON und der Aufruf `staging_gate.py --write-verdict`,
- der `git reset --hard origin/main` im Haupt-Checkout (der einzige Grund dafür war, dass
  `write_verdict` den SHA aus dem cwd zieht),
- der `wip_safety.sh`-Aufruf aus Scheibe 1, der nur diesen Reset absicherte,
- das Sourcen der Staging-`.env` mit `GZ_TELEGRAM_LIVE=1` (#1031-Umweg).

Damit ist auch der Zusatzbefund aus Scheibe 1 erledigt: Die CI tauscht den Code-Stand nicht
mehr unter laufenden Produktions-Diensten aus. Das macht nur noch `deploy-gregor-prod.sh` mit
Dienst-Stopp.

### Was neu ist — `scripts/ci_prod_gate.sh <repo>`

Aufruf per SSH im Haupt-Checkout (`/home/hem/gregor_zwanzig`). Das Skript wird wie in Scheibe 1
aus `origin/main` bezogen (`git show origin/main:scripts/ci_prod_gate.sh`):

```
git -C <repo> fetch origin                       # Ziel auflösbar machen, KEIN reset
python3 .claude/hooks/staging_gate.py --check --expected-commit origin/main
  rc 0  → stdout "PROD_GATE=open"   , exit 0
  rc ≠0 → stdout "PROD_GATE=closed" , exit 0   (Gate-Meldung wird durchgereicht)
fetch scheitert / Skriptfehler → kein PROD_GATE-Satz, exit ≠ 0
```

- Zielstand ist `origin/main`, nicht `github.sha`. Ausgeliefert wird von
  `deploy-gregor-prod.sh` immer `origin/main`. Geprüft wird also genau der Stand, der
  tatsächlich live geht. Ist zwischendurch ein neuerer Merge gelandet, braucht **dieser**
  einen Nachweis.
- Das Skript schreibt **nie** in `.claude/e2e_verified/`. Es ändert weder Arbeitsbaum noch
  HEAD.
- `docs-only`-Scope: `staging_gate` gibt dafür rc 0 → `open`. Reine Doku-Merges liefert die
  CI also weiter automatisch aus. Das entspricht der bestehenden Doku-Ausnahme.
- Notfall-Override `GZ_SKIP_E2E_GATE` wird vom Skript **nicht** gesetzt.

### Verdrahtung in `ci.yml`

```
deploy:
  needs: [test, lint, go-test, frontend-test, svelte-check, e2e]     # C4-71
  steps:
    Warten bis Staging aktuellen Commit hat   (unverändert)
    Smoke-Test Staging                        (unverändert, nur noch Erreichbarkeit)
    Prod-Gate prüfen (id: gate)               → ssh … ci_prod_gate.sh → outputs.open=true|false
                                                fehlt PROD_GATE-Satz → Schritt rot
    Prod-Deploy übersprungen (if open!=true)  → ::notice + Job-Summary:
                                                "Kein /e2e-verify-Nachweis für <sha> —
                                                 Prod-Deploy über /70-deploy Schritt 4"
    Deploy zu Produktion via SSH (if open==true)        (unverändert)
    Telegram erfolgreich (if success() && open==true)   — kein "deployed" ohne Deploy
    Telegram fehlgeschlagen (if failure())              (unverändert)
```

**Bewusste Entscheidung: einmal prüfen, nicht warten.** `/e2e-verify` läuft nach dem Merge und
braucht in der Regel länger als der CI-Job. Ein Warte-Poll im Runner würde Minuten verbrennen
und trotzdem oft leer ausgehen. Real liefert deshalb fast immer `/70-deploy` Schritt 4 aus. Die
CI fängt nur den Fall, dass der Nachweis schon vorliegt, zum Beispiel bei einem Re-Run des Jobs
oder bei reinen Doku-Merges. Den Ablauf, der tatsächlich läuft, beschreibt danach die Doku.

### Doku auf den wirksamen Ablauf ziehen

- **CLAUDE.md** (E2E-Verifikation & Deploy): Ein Merge ist **kein** Prod-Deploy mehr. Die CI
  liefert nur bei vorliegendem Nachweis aus, sonst Schritt 4 aus `/70-deploy`.
- **`/70-deploy`**: Schritt 1 nennt 6 statt 5 Checks. Schritt 4 nennt die CI-Abkürzung
  (übersprungener CI-Deploy ist der Normalfall, kein Fehler).
- **`operations_playbook.md` / `gates_und_ratschen.md`**: CI-Verdict-Schritt streichen,
  `ci_prod_gate.sh` eintragen.

## Expected Behavior

- **Input:** Push auf `main` nach grüner Ampel
- **Output:** Prod-Deploy genau dann, wenn `staging_gate --check` für `origin/main` besteht,
  sonst sichtbar übersprungener Deploy bei grünem Lauf
- **Side effects:** keine Schreibzugriffe der CI auf `.claude/e2e_verified/`, kein Reset im
  Haupt-Checkout

## Acceptance Criteria

- **AC-1:** Given ein Haupt-Checkout, in dem für den Zielstand `origin/main` (Code-Scope) **kein**
  Nachweis unter `.claude/e2e_verified/` liegt / When die CI-Gate-Prüfung `ci_prod_gate.sh` läuft /
  Then meldet sie `PROD_GATE=closed`, und `.claude/e2e_verified/` ist danach **unverändert leer**.
  Die CI erzeugt also keinen Nachweis mehr.
  - Test: echtes Wegwerf-Repo mit Bare-Remote, Code-Commit auf `origin/main`, Skript-Aufruf per
    `subprocess`, Assertion auf Ausgabe und Verzeichnisinhalt
- **AC-2:** Given für den Zielstand `origin/main` liegt ein gültiger, von `staging_gate
  --write-verdict` erzeugter VERIFIED-Nachweis / When `ci_prod_gate.sh` läuft / Then meldet es
  `PROD_GATE=open`.
  - Test: Nachweis über den echten Erzeuger (`staging_gate.py --write-verdict`) im Wegwerf-Repo
    anlegen, dann Skript aufrufen
- **AC-3:** Given der Nachweis liegt nur für einen **älteren** Commit vor, und auf `origin/main`
  ist danach ein neuer Code-Commit gelandet / When `ci_prod_gate.sh` läuft / Then meldet es
  `PROD_GATE=closed`. Geprüft wird der tatsächlich auszuliefernde Stand, nicht der Stand des
  CI-Laufs.
  - Test: Nachweis für Commit A, dann Commit B nach `origin/main` pushen, Skript → `closed`
- **AC-4:** Given im Haupt-Checkout liegen uncommittete getrackte Änderungen und HEAD steht auf
  einem älteren Commit als `origin/main` / When `ci_prod_gate.sh` läuft / Then sind danach HEAD,
  Arbeitsbaum-Inhalt und `git status` **unverändert**. Kein Reset, kein Stash.
  - Test: Wegwerf-Repo mit WIP-Datei und zurückliegendem HEAD, Vorher/Nachher-Vergleich
- **AC-5:** Given der Fetch im Haupt-Checkout scheitert, etwa weil das Remote nicht erreichbar
  ist / When `ci_prod_gate.sh` läuft / Then endet es mit Exit ≠ 0 **ohne** `PROD_GATE=`-Zeile.
  Der CI-Schritt wird rot, statt den Deploy still zu überspringen oder freizugeben.
  - Test: Remote-URL auf nicht existenten Pfad setzen, Exit-Code und Ausgabe prüfen
- **AC-6:** Given der Zielstand ändert gegenüber dem live laufenden Stand nur `docs/`/`*.md` /
  When `ci_prod_gate.sh` läuft / Then meldet es `PROD_GATE=open`. Die Doku-Ausnahme bleibt
  erhalten.
  - Test: Wegwerf-Repo, reiner `.md`-Commit auf `origin/main`, Skript → `open`
- **AC-7:** Given die CI-Definition `.github/workflows/ci.yml` / When man den Job `deploy` als
  YAML auswertet / Then gilt: (a) `needs` umfasst genau die sechs Ampel-Jobs `test`, `lint`,
  `go-test`, `frontend-test`, `svelte-check`, `e2e`. (b) Kein Schritt des Jobs ruft
  `--write-verdict` oder `git reset` auf. (c) Der Schritt `Deploy zu Produktion via SSH` und die
  Erfolgs-Telegram-Meldung laufen nur unter der Bedingung, dass das Gate `open` gemeldet hat.
  - Test: `yaml.safe_load` der Workflow-Datei, Assertions auf die geparste Struktur
    (`# doc-compliance-test` — Konfiguration ist hier der Prüfling)
- **AC-8:** Given der Merge-Lauf auf `main` nach Auslieferung dieser Scheibe / When der CI-Job
  `deploy` ohne vorliegenden Nachweis durchläuft / Then ist der Lauf **grün**, der Prod-Deploy-
  Schritt steht als *skipped*, die Job-Summary nennt den SHA und `/70-deploy` Schritt 4, und es
  geht **keine** Telegram-Meldung „deployed“ raus.
  - Test: Live-Beobachtung des ersten Merge-Laufs (Run-Log), dokumentiert im Issue

## Known Limitations

- Eine Session kann `staging_gate --write-verdict` weiterhin ohne echte Messung aufrufen. Das
  verhindert diese Scheibe nicht, und das ist auch nicht ihr Ziel. Sie schließt nur den
  **automatisierten** Selbst-Nachweis der CI.
- Das Skript fährt die `staging_gate.py`-Version des Haupt-Checkouts, nicht die aus
  `origin/main`. Das ist dasselbe Verhalten wie bei `deploy-gregor-prod.sh`.
- `wip_safety.sh` bleibt mit seinen Verhaltenstests im Repo, hat im CI-Pfad aber keinen
  Aufrufer mehr. Der Verdrahtungstest
  `test_ci_ruft_die_sicherung_vor_dem_harten_reset_aus_origin_main_auf` prüft veraltetes
  Verhalten und wird **gelöscht**. Der Rückbau des Skripts selbst ist eine Sammel-Zeile in
  #1197, nicht Teil dieser Scheibe.

## Changelog

- 2026-10-06: Erstfassung (Scheibe 2, nach Entparkung 2026-10-05)
