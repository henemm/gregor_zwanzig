---
entity_id: fix_1327_1228_selftest_gates
type: module
created: 2026-07-20
updated: 2026-07-20
status: draft
version: "1.0"
tags: [deploy-gate, staging_gate, prod_selftest, e2e-attestation, hooks]
---

# Fix #1327 + #1228 — Deploy-Gate-Robustheit (staging_gate.py + prod_selftest.py)

## Approval

- [ ] Approved

## Purpose

Die Deploy-Gates (`staging_gate.py`, `prod_selftest.py`) erzeugen PARTIAL-/FAIL-Falschbefunde und einen Findings-Datenverlust bei parallelen Workflows: Freitext-Findings werden fälschlich als HTTP-Probe interpretiert, POST-only-Endpoints werden per GET geprüft und als FAIL gewertet, Attestation-Findings zweier gleichzeitig laufender Workflows auf demselben Commit vermischen sich unentwirrbar, Platzhalter-Verdicts wie `"TEST"` werden unbemerkt geschrieben und sprengen den späteren Lese-Check, und der Selftest-Bericht kann unter dem falschen Workflow-Verzeichnis landen. Diese Spec fixiert fünf konservative Korrekturen — neue SKIP-Klassen und Schreibvalidierung statt Gate-Aufweichung.

## Source

- **File:** `.claude/hooks/prod_selftest.py`
- **File:** `.claude/hooks/staging_gate.py`
- **Identifier:** `_probe_ac`, `_staging_to_prod_url`, `_is_probeable_url` (prod_selftest.py); `write_verdict` (staging_gate.py)

> **Schicht-Hinweis:** Beide Dateien sind Deploy-Gate-Hooks unter `.claude/hooks/` (kein Frontend, keine Go-API, kein Python-Core-Domain-Code) — Edits daran lösen den Hook-Selbstschutz aus und benötigen User-Override ([[reference_infra_hooks_edit_needs_user_override]]).

## Estimated Scope

- **LoC:** ~150 (über 2 Hook-Dateien + 3 Bestands-Testsuiten)
- **Files:** 5 (`prod_selftest.py`, `staging_gate.py`, `tests/tdd/test_prod_selftest_564.py`, `tests/tdd/test_staging_gate.py`, `tests/tdd/test_staging_gate_verdict_merge.py`)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `.claude/hooks/_e2e_paths.py` | Modul | Pfad-Helper (Singleton vs. commit-getaggte Attestation) — unverändert |
| `/home/hem/henemm-infra/scripts/deploy-gregor-prod.sh:90-135` | Konsument | Ruft `staging_gate.py --check [--expected-commit]` auf — Exit-Code-Vertrag darf nicht brechen |
| `staging-validator` Agent | Schreiber | Ruft `staging_gate.py --write-verdict` mit Findings-JSON auf — muss weiterhin mit Exit 0/1 arbeiten können |
| `OPENSPEC_ACTIVE_WORKFLOW` (Env) | Konvention | Primäre Workflow-Namensquelle für Findings-Tagging (Fix 3) und Berichtspfad (Fix 5) |
| `GZ_ACTIVE_WORKFLOW` (Env) | Legacy-Fallback | Zweite Fallback-Stufe im Berichtspfad (Fix 5), analog `prod_send_gate.py` |
| `tests/tdd/test_prod_selftest_564.py` | Testsuite | Bestands-Suite (live/staging-marked) — RED-Tests für Fix 1/2/5 andocken |
| `tests/tdd/test_staging_gate.py` | Testsuite | Bestands-Suite Mode A/B — RED-Test für Fix 4 (Whitelist) andocken |
| `tests/tdd/test_staging_gate_verdict_merge.py` | Testsuite | Bestands-Merge-Suite (#1197) — Semantikänderung (Fix 3) muss hier respektiert/angepasst werden |

## Implementation Details

### Fix 1 — Freitext-URL-Erkennung (`prod_selftest.py`, in `_probe_ac`, vor Zeile 240)

Vor dem Aufruf von `_staging_to_prod_url(raw_url)` eine neue Prüfung einfügen: `raw_url` (nach den bestehenden Sentinel-/Test-Trip-/Internal-Checks) muss — getrimmt — entweder mit `http://`, `https://` oder `/` beginnen. Andernfalls sofort `SKIPPED_NO_URL` zurückgeben, **ohne** `_staging_to_prod_url` aufzurufen:

```
# NEU, vor: prod_url = _staging_to_prod_url(raw_url)
trimmed = raw_url.strip()
if not (trimmed.startswith("/") or trimmed.startswith("http://") or trimmed.startswith("https://")):
    return {**finding, "prod_url": "", "prod_http": "—", "prod_status": "SKIPPED_NO_URL"}
```

Begründung: `_staging_to_prod_url` (Z. 140-146) baut `f"{PROD_BASE}{path}{query}"` aus `urlparse(clean).path`. Bei Freitext ohne führenden `/` (z.B. `"compareMetricDefs.ts/ALL_METRICS"`) liefert `urlparse` `path="compareMetricDefs.ts/ALL_METRICS"`, `scheme=""` — die Konkatenation ergibt einen syntaktisch validen, aber falschen Host (`https://gregor20.henemm.comcompareMetricDefs.ts/...`), der `_is_probeable_url` (Z. 183-196) passiert und erst per DNS-Fehler in FAIL läuft. Die neue Prüfung fängt das strukturell ab, bevor die Pfad-Konkatenation überhaupt läuft.

### Fix 2 — 405-Bewertung (`prod_selftest.py`, in `_probe_ac`, Zeilen 252-260)

Neuer Status `SKIPPED_METHOD_NOT_PROBEABLE`, wenn die GET-Probe `status == 405` liefert:

```
status, _ = _http_get(prod_url, follow_redirects=False)
if status == 405:
    return {**finding, "prod_url": prod_url, "prod_http": status,
            "prod_status": "SKIPPED_METHOD_NOT_PROBEABLE"}
ok = status in (200, 302)
return {**finding, "prod_url": prod_url, "prod_http": status,
        "prod_status": "PASS" if ok else "FAIL"}
```

`_derive_verdict` (Z. 415-429) behandelt `SKIPPED_*`-Status bereits korrekt als nicht-blockierend (nur `pass_probes` mit `prod_status == "FAIL"` erzeugen PARTIAL) — **kein Änderungsbedarf** dort, sofern die Probe-Funktion den Finding-`status` (Input, `PASS`/`SKIPPED`) nicht mit `prod_status` (Output) verwechselt. Kein neues Schema-Feld `method` in dieser Scheibe (Scope-Grenze, siehe Known Limitations).

### Fix 3 — Workflow-getrennte Findings (`staging_gate.py`, `write_verdict`, Zeilen 229-289)

Jedes Finding bekommt beim Schreiben ein `workflow`-Feld:

```
current_workflow = os.environ.get("OPENSPEC_ACTIVE_WORKFLOW", "unknown")
findings = [{**f, "workflow": f.get("workflow", current_workflow)} for f in findings]
```

Merge-Logik (ersetzt Zeilen 264-278, dedup-by-serialisierung entfällt):

```
if e2e_path.exists():
    try:
        existing = json.loads(e2e_path.read_text())
    except (json.JSONDecodeError, OSError):
        existing = None
    if existing is not None and existing.get("verified_commit") == sha:
        existing_findings = existing.get("findings") or []
        # Fremde Findings (workflow != current_workflow, inkl. Altbestand ohne
        # 'workflow'-Feld -> gilt als fremd) bleiben unangetastet.
        foreign = [f for f in existing_findings if f.get("workflow") != current_workflow]
        payload["findings"] = foreign + findings
```

Semantik: Eigene Findings (gleicher `workflow`-Wert) werden bei Re-Write komplett ersetzt (alte raus, neue rein) — kein additiver Dedup mehr für den eigenen Workflow. Fremde Findings (anderer `workflow`-Wert ODER kein `workflow`-Feld = Altbestand) bleiben unverändert erhalten (#1197-Schutz gegen Evidenz-Verlust des Erstschreibers). `staging_verdict` wird weiterhin vom aktuellen Schreiber gesetzt (unverändert ggü. Bestand) — Absicherung gegen kaputte Verdicts kommt aus Fix 4, nicht aus der Merge-Logik.

### Fix 4 — Verdict-Schreibvalidierung (`staging_gate.py`, `write_verdict`, Zeilen 235-239)

Bestehende Negativ-Prüfung (`BROKEN*` blockt) wird um eine Positiv-Whitelist ergänzt:

```
verdict_upper = verdict.strip().upper()
if verdict_upper.startswith("BROKEN"):
    _log(f"BROKEN-Verdict erhalten: {verdict}")
    _log("Kein VERIFIED-Artefakt geschrieben — /e2e-verify erneut ausführen.", stream=sys.stderr)
    return 1
if not (verdict_upper.startswith("VERIFIED") or verdict_upper.startswith("AMBIGUOUS")):
    _log(f"FEHLER: Verdict {verdict!r} beginnt weder mit VERIFIED noch AMBIGUOUS (noch BROKEN) — abgelehnt.", stream=sys.stderr)
    return 1
```

Kein Schreiben (auch kein Merge-Versuch, keine Datei-Berührung) bei Ablehnung — Funktion kehrt vor jedem Dateizugriff zurück. Der Lese-Check in `gate_check` (Zeile 452: `verdict.startswith("VERIFIED")`) bleibt unverändert; ein per `--write-verdict "AMBIGUOUS: ..."` geschriebenes Verdict lässt den Lese-Check weiterhin fehlschlagen (bestehendes Verhalten, kein Regress) — die Whitelist verhindert nur, dass beliebiger Freitext (`"TEST"`) durchrutscht und die Datei unbemerkt korrumpiert.

### Fix 5 — Berichtspfad-Workflow-Quelle (`prod_selftest.py`, `main`, Zeilen 668-677)

Ist-Zustand: `workflow = args.workflow or os.environ.get("OPENSPEC_ACTIVE_WORKFLOW")`, Fallback `"unknown"` — **kein** `GZ_ACTIVE_WORKFLOW`-Fallback trotz irreführender Logzeile (Z. 672-674 spricht von `GZ_ACTIVE_WORKFLOW`, prüft aber nur `OPENSPEC_ACTIVE_WORKFLOW`). Ziel-Kette:

```
workflow = args.workflow \
    or os.environ.get("OPENSPEC_ACTIVE_WORKFLOW") \
    or os.environ.get("GZ_ACTIVE_WORKFLOW")
if not workflow:
    _log(
        "WARN: weder OPENSPEC_ACTIVE_WORKFLOW noch GZ_ACTIVE_WORKFLOW gesetzt — "
        "Bericht wird unter docs/artifacts/unknown/prod-selftest.md abgelegt.",
        stream=sys.stderr,
    )
    workflow = "unknown"
```

**Entwickler-Pflicht:** Der reale Vorfall vom 2026-07-20 (Bericht landete unter `docs/artifacts/epic-1273-s3-redirect/` statt dem tatsächlich aktiven Workflow) muss in der Implementierungsphase per Reproduktion verifiziert werden — die o.g. Env-Kette allein erklärt den Vorfall nicht zwingend (möglicher Kandidat: Aufrufer übergibt einen stale `--workflow`-Wert, oder eine Shell/Deploy-Skript-Injektion setzt `OPENSPEC_ACTIVE_WORKFLOW` fälschlich weiter). Die tatsächliche stale Quelle ist zu identifizieren und zu schließen, nicht nur die Fallback-Kette zu vervollständigen.

## Expected Behavior

- **Input:** Findings-Listen mit Freitext-URLs, POST-only-Prod-Routen, parallele `--write-verdict`-Aufrufe verschiedener Workflows auf demselben Commit, Platzhalter-Verdict-Strings, `prod_selftest.py`-Aufruf ohne `--workflow`-Arg.
- **Output:** Neue SKIP-Klassen (`SKIPPED_NO_URL` für Freitext, `SKIPPED_METHOD_NOT_PROBEABLE` für 405) statt FAIL/PARTIAL; workflow-partitionierte, verlustfreie Findings in der Attestation; Exit ≠ 0 und unveränderte Datei bei ungültigem Verdict-String; korrekter Berichtspfad gemäß Env-Fallback-Kette.
- **Side effects:** Keine neuen Dateien/Schemas außer dem additiven `workflow`-Feld pro Finding-Eintrag. Bestehende SKIP-Klassen, 24h-Staleness, Ancestor-Relaxierung (#1197) und Scope-Detection bleiben unverändert.

## Acceptance Criteria

- **AC-1:** Given ein Finding trägt eine Freitext-`url` ohne führendes `http(s)://` oder `/` (z.B. `"compareMetricDefs.ts/ALL_METRICS"`) / When `prod_selftest.py` dieses Finding probet / Then das Ergebnis hat `prod_status == "SKIPPED_NO_URL"`, und es wird nachweislich kein Netzwerk-Request an einen aus der Konkatenation entstandenen Fantasie-Host ausgelöst.
  - Test: `_probe_ac` (bzw. der laufende Prozess) direkt mit dem Freitext-Finding aufrufen — keine Netzwerkabhängigkeit nötig, da der Kurzschluss vor jedem `_http_get` greift; Assertion auf `prod_status`.

- **AC-2:** Given ein PASS-Finding zeigt auf eine Prod-Route, die auf GET mit HTTP 405 antwortet (POST-only-Endpoint) / When `prod_selftest.py` diese Route probet / Then das Ergebnis hat `prod_status == "SKIPPED_METHOD_NOT_PROBEABLE"` (nicht `FAIL`, nicht `PASS`), und der Gesamt-Verdict wird durch dieses Finding allein nicht auf `PARTIAL`/`FAIL` gezogen.
  - Test: echter lokaler `ThreadingHTTPServer` (Vorbild `tests/tdd/test_issue_1142_geosphere_direct_fallback.py`) liefert 405 auf GET; `PROD_BASE`/Ziel-URL wird testseitig auf den lokalen Server umgebogen (Modul-Import statt Subprocess, damit der Modul-Konstantenwert überschreibbar ist); Assertion auf `prod_status` und Gesamt-Verdict.

- **AC-3:** Given Workflow W1 hat bereits eine commit-getaggte Attestation mit Finding F1 (workflow=W1) geschrieben / When Workflow W2 auf demselben Commit `--write-verdict` mit Finding F2 aufruft / Then die resultierende Datei enthält sowohl F1 (workflow=W1) als auch F2 (workflow=W2) — kein Datenverlust, keine Vermischung.
  - Test: `write_verdict` zweimal direkt aufrufen (Muster `test_staging_gate_verdict_merge.py`) mit unterschiedlichem `OPENSPEC_ACTIVE_WORKFLOW`-Monkeypatch je Aufruf; `json.loads` der Ergebnisdatei prüft beide Findings inkl. `workflow`-Tag.

- **AC-4:** Given Workflow W1 hat bereits Finding F1 (workflow=W1) geschrieben / When W1 erneut auf demselben Commit mit korrigiertem Finding F1' schreibt / Then F1 ist aus dem Ergebnis verschwunden, F1' ist vorhanden, und Findings anderer Workflows (inkl. Alt-Findings ohne `workflow`-Feld) bleiben unverändert erhalten.
  - Test: drei `write_verdict`-Aufrufe (W1 initial, W2 dazwischen, W1 Korrektur) auf demselben Commit; Ergebnis geprüft auf: F1 fehlt, F1' vorhanden, W2-Finding weiterhin vorhanden.

- **AC-5:** Given `--write-verdict "TEST"` (Platzhalter, beginnt weder mit `VERIFIED` noch `AMBIGUOUS` noch `BROKEN`) wird aufgerufen, während bereits eine gültige Attestation für denselben Commit existiert / When `write_verdict` läuft / Then der Prozess beendet mit Exit ≠ 0, und die bestehende Attestations-Datei ist byteidentisch unverändert (kein Schreibversuch).
  - Test: Datei-Inhalt (mtime oder Byte-Vergleich) vor/nach dem Aufruf vergleichen; Exit-Code prüfen.

- **AC-6:** Given `OPENSPEC_ACTIVE_WORKFLOW` ist NICHT gesetzt, `GZ_ACTIVE_WORKFLOW=issue-1327-legacy-fallback` IST gesetzt, kein `--workflow`-Arg wird übergeben / When `prod_selftest.py` läuft / Then der Bericht erscheint unter `docs/artifacts/issue-1327-legacy-fallback/prod-selftest.md` (nicht unter `docs/artifacts/unknown/`).
  - Test: Subprocess-Aufruf mit kontrolliertem `env` (analog `_run_selftest`-Helper in `test_prod_selftest_564.py`, dort wird aktuell `GZ_ACTIVE_WORKFLOW` sogar aktiv entfernt — für diesen Test gezielt setzen); Bericht-Pfad-Existenz prüfen.

## Known Limitations

- Kein neues Findings-Schema-Feld `method` in dieser Scheibe — 405 wird ausschließlich über `prod_status` sichtbar, nicht als eigenes strukturiertes Feld (#1228 nannte das zusätzlich, bewusst außerhalb des Scopes; eigener Vorschlag bei Bedarf).
- Alt-Findings ohne `workflow`-Feld gelten dauerhaft als "fremd" — sie werden von KEINEM Schreiber je ersetzt (auch nicht vom ursprünglichen Autor, dessen Workflow-Zugehörigkeit nicht mehr rekonstruierbar ist). Das ist beabsichtigt (kein Datenverlust) und kein Bug; sie akkumulieren bis zur nächsten Staleness-Bereinigung (24h) oder manuellen Aufräumung.
- Fix 5 beschreibt die Ziel-Fallback-Kette; die tatsächliche Root-Cause des historischen Fehlbefunds (Bericht unter `epic-1273-s3-redirect`) muss der Entwickler in der Implementierungsphase reproduzieren und bestätigen — die Spec macht keine abschließende Aussage über die exakte stale Quelle.
- `staging_verdict` bleibt Single-Value pro Attestation (nicht workflow-partitioniert) — bei zwei Workflows auf demselben Commit gewinnt weiterhin der letzte Schreiber für das Verdict-Feld selbst (nur die `findings`-Liste wird partitioniert). Das ist unverändertes Bestandsverhalten, keine Regression dieser Scheibe.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0031
- **Rationale:** Gate-Falschbefunde werden als SKIP-Klassen behandelt, nie als PASS; Attestation-Findings sind workflow-partitioniert. Begründung: Ein Gate, das bei Unsicherheit (Freitext-URL, nicht-probebare Methode) PASS vergibt, verliert seine Beweiskraft (Gate-Erosion, vgl. Regel-Budget-Prinzip). Ein Gate, das bei Unsicherheit blockiert, obwohl das reale Feature funktioniert, erzeugt Beweis-Theater in die andere Richtung. Die einzige Option, die beide Fehlrichtungen vermeidet, ist eine explizite dritte Kategorie (SKIPPED_*), die weder Erfolg noch Misserfolg behauptet. Analog: Findings-Vermischung paralleler Workflows ist kein Bug, der durch strengeres Locking gelöst wird (verhindert legitime Parallelarbeit, siehe „Parallele Sessions"-Konvention), sondern durch Partitionierung — jeder Workflow besitzt und verantwortet nur seine eigenen Findings, fremde bleiben unangetastet.

## Changelog

- 2026-07-20: Initial spec created (Issues #1327, #1228)
