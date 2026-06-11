---
entity_id: issue_564_post_deploy_selftest
type: module
created: 2026-06-02
updated: 2026-06-02
status: draft
version: "1.0"
tags: [workflow, hooks, deployment-pipeline, post-deploy, selftest, qa, gate, issue-564]
---

<!-- Issue #564 — Post-Deploy-Selbsttest: automatische Verifikation nach jedem Prod-Deploy -->

# Issue #564 — Post-Deploy-Selbsttest

## Approval

- [ ] Approved

## Purpose

`prod_selftest.py` ist eine neue Verifikationsschicht, die unmittelbar nach dem Prod-Deploy läuft und die kritischen User-Flows gegen die laufende Produktion prüft — ohne Playwright (kein Risiko für echte Sessions), stattdessen über Commit-Attestation, Health-Check und HTTP-AC-Attestation. Damit schließt das Script die Lücke zwischen Staging-Verifikation (Playwright auf Staging) und tatsächlichem Prod-Deploy: erst wenn alle PASS-ACs aus der Staging-Verifikation auch in Produktion erreichbar sind, darf das GitHub Issue geschlossen werden. Das verhindert, dass Issues geschlossen werden obwohl der Deploy still fehlschlug oder der falsche Code-Stand deployed wurde.

## Source

- **File:** `.claude/hooks/prod_selftest.py` (NEU — ~190 LoC)
- **File:** `.claude/commands/7-deploy.md` (UPDATE — neuer Step 6b zwischen Smoke und Issue-Close)
- **File:** `tests/tdd/test_prod_selftest_564.py` (NEU — ~200 LoC, keine Mocks)

> **Schicht-Hinweis:** Primär Workflow-/Tooling-Schicht (`.claude/hooks/`). Kein Code in `src/`, `api/`, `internal/` oder `frontend/` — ausschließlich Deploy-Pipeline-Tooling.

## Estimated Scope

- **LoC:** ~190 (prod_selftest.py) + ~15 (7-deploy.md Patch) + ~200 (test_prod_selftest_564.py)
- **Files:** 3 (2 neu, 1 geändert)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `.claude/e2e_verified.json` | Artefakt (Input) | Enthält `verified_commit`, `staging_verdict`, `findings[]` aus Staging-Verifikation — Pflicht-Input für Commit-Attestation und AC-Attestation |
| `subprocess.check_output(["git", "rev-parse", "HEAD"])` | stdlib | Liest aktuellen HEAD-SHA für Commit-Attestation; Pfad relativ zu `REPO_DIR=/home/hem/gregor_zwanzig` |
| `concurrent.futures.ThreadPoolExecutor` | stdlib | Parallele HTTP-Probes für AC-Attestation, max 5 Workers |
| `urllib.request` / `requests` | stdlib/lib | HTTP GET gegen `https://gregor20.henemm.com/api/health` und AC-URLs |
| `docs/artifacts/<workflow>/prod-selftest.md` | Artefakt (Output) | Markdown-Bericht mit per-AC-Tabelle; Workflow-Name aus `GZ_ACTIVE_WORKFLOW` |
| `.claude/commands/7-deploy.md` | Workflow-Command | Neuer Step 6b ruft `prod_selftest.py` auf; `gh issue close` gates auf Exit 0 |
| `GZ_ACTIVE_WORKFLOW` (ENV) | Konfiguration | Bestimmt den Ausgabe-Pfad `docs/artifacts/<workflow>/prod-selftest.md` |
| `https://gregor20.henemm.com/api/health` | extern | Produktion Health-Check-Endpoint, muss HTTP 200 + `status=ok` zurückgeben |

## Implementation Details

### Architektur-Überblick

```
.claude/commands/7-deploy.md
    Step 6b: python3 .claude/hooks/prod_selftest.py
        ↓ liest
    .claude/e2e_verified.json  (findings[] mit {ac, status, url, evidence})
        ↓ prüft
    https://gregor20.henemm.com/api/health  +  AC-URLs (parallel)
        ↓ schreibt
    docs/artifacts/<workflow>/prod-selftest.md
        ↓ Exit 0 → weiter, Exit 1 → abbrechen
    gh issue close  (nur bei Exit 0)
```

### prod_selftest.py — Ablauf (3 Phasen)

**Phase 1: Commit-Attestation**

```python
REPO_DIR = "/home/hem/gregor_zwanzig"
head_sha = subprocess.check_output(
    ["git", "rev-parse", "HEAD"], cwd=REPO_DIR
).decode().strip()

with open(os.path.join(REPO_DIR, ".claude/e2e_verified.json")) as f:
    verified = json.load(f)

if head_sha != verified["verified_commit"]:
    # Verdict: FAIL — Commit-Mismatch
    # Exit 1
```

**Phase 2: Health-Check**

```python
resp = requests.get("https://gregor20.henemm.com/api/health", timeout=8)
if resp.status_code != 200 or resp.json().get("status") != "ok":
    # Verdict: FAIL — Health unreachable
    # Exit 1
```

**Phase 3: AC-Attestation (concurrent)**

```python
def probe_ac(finding):
    """Extrahiert Pfad aus Staging-URL, baut Prod-URL, prüft HTTP-Status."""
    if finding["status"] == "SKIPPED":
        return {**finding, "prod_status": "ATTESTED_SKIPPED"}

    staging_url = finding["url"]
    path = urllib.parse.urlparse(staging_url).path
    prod_url = f"https://gregor20.henemm.com{path}"

    try:
        resp = requests.get(prod_url, timeout=8, allow_redirects=False)
        ok = resp.status_code in (200, 302)
        return {
            **finding,
            "prod_url": prod_url,
            "prod_http": resp.status_code,
            "prod_status": "PASS" if ok else "FAIL",
        }
    except requests.exceptions.RequestException as e:
        return {**finding, "prod_url": prod_url, "prod_status": "FAIL", "error": str(e)}

with ThreadPoolExecutor(max_workers=5) as pool:
    results = list(pool.map(probe_ac, verified["findings"]))
```

**Verdict-Ableitung:**

```
PASS:    alle Findings mit status=PASS liefern prod_status=PASS
         (ATTESTED_SKIPPED und SKIPPED_NO_URL zählen nicht gegen PASS)
PARTIAL: mind. ein PASS-Finding liefert prod_status=FAIL
FAIL:    Health unreachable ODER Commit-Mismatch
```

prod_status-Werte:
- **PASS:** HTTP 200 oder 302 für probeable Finding
- **FAIL:** HTTP-Status ≠ 200/302, oder URLError/Netzwerkfehler
- **ATTESTED_SKIPPED:** Finding hatte staging_status=SKIPPED (nicht geprobt)
- **SKIPPED_NO_URL:** Prod-URL trägt Leerzeichen/Steuerzeichen → nicht probebar (Bug #730 fix)

Exit-Codes: 0 = PASS (oder alle SKIPPED/SKIPPED_NO_URL), 1 = FAIL oder PARTIAL

**Edge-Case: Kein e2e_verified.json / docs-only Scope**

```python
e2e_path = os.path.join(REPO_DIR, ".claude/e2e_verified.json")
if not os.path.exists(e2e_path):
    print("INFO: e2e_verified.json nicht vorhanden — Selftest übersprungen (docs-only oder erster Deploy).")
    sys.exit(0)
```

Wenn `e2e_verified.json` nicht existiert, terminiert das Script mit Exit 0 (kein Block). Das ist der docs-only-Pfad, der keinen Selftest benötigt.

### Report-Format: docs/artifacts/<workflow>/prod-selftest.md

```markdown
# Prod-Selftest — <workflow-name>

**Datum:** 2026-06-02T10:34:56Z
**Commit:** abc1234
**Staging-Commit:** abc1234
**Health:** OK (HTTP 200, status=ok)
**Verdict: PASS**

## AC-Ergebnisse

| AC | Staging-Status | Prod-URL | Prod-HTTP | Prod-Status |
|----|---------------|---------|-----------|-------------|
| AC-1 | PASS | https://gregor20.../... | 200 | PASS |
| AC-2 | PASS | https://gregor20.../... | 302 | PASS |
| AC-3 | SKIPPED | — | — | ATTESTED_SKIPPED |

## Fazit

Alle verifizierten ACs in Produktion erreichbar. Issue-Close freigegeben.
```

### 7-deploy.md — neuer Step 6b

Einzufügen zwischen bestehendem Step 6 (Smoke-Test) und Step 7 (gh issue close):

```markdown
### Step 6b: Post-Deploy-Selbsttest

python3 .claude/hooks/prod_selftest.py

Bei Exit 0 (PASS): weiter mit Step 7.
Bei Exit 1 (FAIL/PARTIAL): Deploy gilt als fehlgeschlagen.
  - Bericht in docs/artifacts/<workflow>/prod-selftest.md prüfen
  - Bei Commit-Mismatch: /e2e-verify erneut ausführen, dann deploy-gregor-prod.sh
  - Bei Partial/Health-Fail: Infrastruktur prüfen, Rollback entscheiden
  - Issue NICHT schließen
```

## Expected Behavior

- **Input:** `.claude/e2e_verified.json` (mit `verified_commit`, `staging_verdict: "VERIFIED*"`, `findings[]`), `GZ_ACTIVE_WORKFLOW` ENV, erreichbare Produktion auf `https://gregor20.henemm.com`
- **Output:** `docs/artifacts/<workflow>/prod-selftest.md` (Markdown-Tabelle pro AC), Exit 0 bei PASS, Exit 1 bei FAIL/PARTIAL
- **Side effects:** `7-deploy.md` ruft das Script auf und gibt `gh issue close` nur bei Exit 0 frei; kein Playwright gegen Produktion, keine Auth-Sessions, keine Schreiboperationen auf dem Server

## Acceptance Criteria

**AC-1:** Given `e2e_verified.json` existiert mit `verified_commit=HEAD`, `staging_verdict="VERIFIED"` und alle `findings[].status=PASS`, und die Produktion antwortet auf alle AC-Pfade mit HTTP 200 oder 302, When `prod_selftest.py` aufgerufen wird, Then ist der Exit-Code 0, der Bericht in `docs/artifacts/<workflow>/prod-selftest.md` zeigt alle ACs mit `prod_status=PASS`, und `7-deploy.md` fährt mit `gh issue close` fort.
- Test: (populated after /tdd-red)

**AC-2:** Given `e2e_verified.json` existiert, aber `verified_commit` stimmt nicht mit dem aktuellen HEAD-SHA überein (veraltete Staging-Verifikation), When `prod_selftest.py` aufgerufen wird, Then ist der Exit-Code 1, der Bericht enthält `Verdict: FAIL` mit Hinweis auf Commit-Mismatch, und `gh issue close` wird nicht ausgeführt.
- Test: (populated after /tdd-red)

**AC-3:** Given `e2e_verified.json` zeigt Commit-Match und Health-OK, aber mindestens ein PASS-Finding liefert bei der Prod-URL einen HTTP-Status der weder 200 noch 302 ist (z.B. 404 oder 503), When `prod_selftest.py` aufgerufen wird, Then ist der Exit-Code 1, der Bericht enthält `Verdict: PARTIAL` mit der fehlschlagenden AC-Zeile und dem tatsächlichen HTTP-Status, und das Issue bleibt offen.
- Test: (populated after /tdd-red)

**AC-4:** Given `e2e_verified.json` enthält Findings mit `status=SKIPPED` (Backend- oder E-Mail-ACs), When `prod_selftest.py` aufgerufen wird, Then werden diese Findings im Bericht als `ATTESTED_SKIPPED` geführt, zählen nicht gegen das PASS-Verdict, und blockieren den Issue-Close nicht — sofern alle anderen ACs PASS sind.
- Test: (populated after /tdd-red)

**AC-5:** Given `e2e_verified.json` existiert nicht (docs-only Deploy oder allererster Deploy ohne vorherige Staging-Verifikation), When `prod_selftest.py` aufgerufen wird, Then ist der Exit-Code 0, es wird eine INFO-Meldung ausgegeben ("e2e_verified.json nicht vorhanden — Selftest übersprungen"), und kein Bericht wird geschrieben.
- Test: (populated after /tdd-red)

**AC-6:** Given ein gültiges `e2e_verified.json` mit mindestens 3 PASS-Findings, When `prod_selftest.py` aufgerufen wird, Then enthält `docs/artifacts/<workflow>/prod-selftest.md` eine Markdown-Tabelle mit den Spalten `AC`, `Staging-Status`, `Prod-URL`, `Prod-HTTP`, `Prod-Status` sowie einen Fazit-Absatz mit dem Gesamtverdikt, und das Dokument ist in weniger als 60 Sekunden fertig (parallele HTTP-Probes via ThreadPoolExecutor, max 5 Workers).
- Test: (populated after /tdd-red)

## Known Limitations

- `prod_selftest.py` prüft keine Auth-geschützten Seiten gegen Produktion (kein Login, kein Playwright gegen Prod). ACs, die nur nach Login sichtbar sind, werden über den Staging-Validator (Issue #521) abgedeckt, nicht hier.
- Die AC-Attestation prüft nur die HTTP-Erreichbarkeit eines Pfades (200/302), nicht den DOM-Inhalt. Inhaltliche Regressions auf Produktionsseiten können damit nicht erkannt werden — das ist bewusste Abgrenzung gegenüber dem Staging Validator.
- Wenn `GZ_ACTIVE_WORKFLOW` nicht gesetzt ist, schreibt das Script den Bericht nach `docs/artifacts/unknown/prod-selftest.md` und gibt eine WARN-Zeile aus (kein Block, kein Absturz).
- Der Timeout von 8 Sekunden pro Probe gilt pro HTTP-Request. Bei sehr langsamen oder Rate-limitierten Produktions-Endpoints kann das zum PARTIAL-Verdict führen, auch wenn die Route technisch korrekt ist.
- Wenn `e2e_verified.json.findings[]` leer ist (kein AC wurde von der Staging-Verifikation erfasst), wertet `prod_selftest.py` das als PASS (keine ACs zu prüfen) und gibt Exit 0 zurück — dieser Fall sollte durch die staging_gate.py bereits blockiert sein.

## Changelog

- 2026-06-02: Initial spec (Issue #564) — Post-Deploy-Selbsttest als dritte Verifikationsschicht nach Staging Validator (Issue #521); kein Playwright gegen Prod; Commit-Attestation + Health-Check + concurrent AC-Attestation; Bericht in docs/artifacts/<workflow>/prod-selftest.md; 7-deploy.md Step 6b gates gh issue close
