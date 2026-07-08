# Context: fix-1084-stale-gate-marker

## Request Summary

Issue #1084: `prod_selftest.py` überspringt die Post-Deploy-Prod-Verifikation still
(Exit 0), wenn ein echter Frontend-/Backend-Deploy unmittelbar nach einem
erfolgreichen `staging_gate.py --check` läuft — weil beide Skripte ihre
Scope-Erkennung über denselben Marker (`.claude/last_gate_scope.json`) spiegeln
und der Marker vom vorausgehenden `--check`-Lauf bereits auf HEAD gesetzt wurde.
Zusätzlich ignoriert `write_verdict()` (Mode A) einen übergebenen `--scope`-Override.

## Related Files

| File | Relevance |
|------|-----------|
| `.claude/hooks/staging_gate.py` | `_scope_diff_base()`/`_detect_committed_scope()` (Marker-Lese-Logik), `gate_check()` (schreibt Marker bei JEDEM Exit-0-Pfad, Zeilen 285 + 343), `write_verdict()` (Zeile 254 ruft `_detect_committed_scope()` OHNE den `--scope`-Override zu berücksichtigen — `main()` reicht `args.scope` nur an `gate_check()` durch, nicht an `write_verdict()`) |
| `.claude/hooks/prod_selftest.py` | Gespiegelte, READ-ONLY-Kopie von `_scope_diff_base()`/`_detect_committed_scope()` (Zeilen 393-459); `run_selftest()` (Zeile 462) akzeptiert bereits einen `scope`-Parameter, der `_detect_committed_scope()` umgeht — aber `main()`/CLI hat **keinen** `--scope`-Flag, ruft `run_selftest(e2e_path, workflow)` immer ohne Override auf (Zeile 621) |
| `.claude/hooks/_e2e_paths.py` | Pure-Function-Helper: `last_gate_scope_path`, `read_last_gate_scope`, `write_last_gate_scope` — Marker-Format aktuell nur `{"gate_scope_sha": sha}` |
| `docs/specs/modules/issue_916_988_gate_scope_robustness.md` | HEUTE (2026-07-07) erstellte Spec, status `draft`/nicht approved — führt den Marker-Mechanismus selbst ein (Fix für #916: Multi-Commit-Scope-Erkennung). "Known Limitations" beschreibt NUR den Fall "Marker zu ALT" (prod_selftest läuft isoliert, Marker zeigt auf älteren Commit → breiterer, aber korrekter Diff-Scan). Der in #1084 beobachtete Fall — Marker frisch auf HEAD durch einen VORAUSGEHENDEN Schritt IN DERSELBEN Deploy-Pipeline — ist dort NICHT abgedeckt. |
| `tests/tdd/test_issue_916_gate_scope_marker.py` | AC-1..AC-4 für den Marker-Mechanismus (MUSS unverändert grün bleiben) |
| `tests/tdd/test_staging_gate.py` | Bestehende `write_verdict`/`gate_check`-Tests; **keine** Abdeckung für `--scope`-Override bei `write_verdict()` — echte Lücke |
| `tests/tdd/test_bundle_e_gate_tooling.py` | AC-3/AC-4 (#786): `run_selftest(scope=...)` überspringt/überspringt-nicht korrekt bei explizitem Scope-Parameter — bestätigt, dass der Parameter bereits existiert und getestet ist, nur nicht per CLI erreichbar |
| `docs/reference/operations_playbook.md` | Dokumentiert Post-Push-Workflow: Schritt 4 = `deploy-gregor-prod.sh` (ruft intern `staging_gate.py --check` auf), Schritt 4b = `python3 .claude/hooks/prod_selftest.py` (SEPARATER manueller Folgeschritt, nicht automatisch aus dem Deploy-Script heraus) |
| `/home/hem/henemm-infra/scripts/deploy-gregor-prod.sh` (Zeile 104) | Ruft `staging_gate.py --check` unmittelbar nach `git reset --hard origin/main` auf — bestätigt: Marker wird HIER (Schritt 4) auf HEAD gesetzt, BEVOR Schritt 4b (`prod_selftest.py`) läuft. Kein `--scope`-Durchreichen zwischen den beiden Schritten vorgesehen; die beiden Aufrufe sind unabhängige Prozesse ohne gemeinsamen State außer der Marker-Datei. |

## Root Cause (bereits verifiziert, keine offene Frage mehr)

1. `deploy-gregor-prod.sh` synct HEAD via `git reset --hard origin/main`, ruft dann
   `staging_gate.py --check`. Bei Erfolg (docs-only-Skip ODER volle Prüfung
   bestanden) schreibt `gate_check()` den Marker auf den AKTUELLEN HEAD
   (`_e2e_paths.write_last_gate_scope`). Das ist **beabsichtigtes, getestetes**
   Verhalten (AC-4, #916) — die nächste Gate-Prüfung soll ab hier neu zählen.
2. Direkt danach (gleiche Pipeline, kein neuer Commit) läuft `prod_selftest.py`
   als eigener Prozess. Seine eigene, gespiegelte `_detect_committed_scope()`
   liest DENSELBEN Marker — der jetzt zufällig == HEAD ist — als Diff-Basis.
   `git diff HEAD..HEAD` ist leer → Scope wird fälschlich `docs-only` →
   Post-Deploy-Selftest überspringt sich selbst, obwohl echter Code deployt wurde.
3. **Wichtige Erkenntnis aus der Analyse:** Ein naiver Fix "wenn Marker-SHA ==
   HEAD, dann Fallback auf `HEAD~1`" wäre FALSCH — er würde den ursprünglichen
   #916-Bug (Multi-Commit-Push, mehrere Commits seit dem LETZTEN Deploy, nur der
   letzte ist docs-only) für `prod_selftest.py` in genau dem Standardfall (Schritt
   4 direkt gefolgt von 4b) wieder einschleppen, weil `HEAD~1` nur den letzten
   Commit sieht, nicht alle seit dem VORHERIGEN (Vor-Update-)Marker.

## Existing Patterns

- `run_selftest(e2e_path, workflow, scope: str | None = None)` unterstützt
  bereits einen expliziten Scope-Parameter, der `_detect_committed_scope()`
  komplett umgeht (genutzt/getestet in Bundle #786, AC-3/AC-4). Nur der CLI-Layer
  (`main()`) reicht keinen `--scope`-Flag durch.
- `gate_check(e2e_path, scope_override)` honoriert einen Override bereits korrekt
  — das ist das Vorbild, dem `write_verdict()` fehlt.
- `_e2e_paths.py` ist bewusst ein "dünner, pure-function Shim-Layer" (Docstring),
  auf den beide Hook-Dateien zugreifen — Erweiterungen dort (neues Marker-Feld)
  sind der bereits etablierte Ort für geteilte Marker-Logik.

## Dependencies

- **Upstream:** `git` (Subprocess-Aufrufe für `diff`, `cat-file`, `rev-parse`),
  `.claude/e2e_verified.json` bzw. `.claude/e2e_verified/<sha>.json` (Attestation).
- **Downstream:** `deploy-gregor-prod.sh` (henemm-infra, ruft nur `--check` auf,
  KEIN Scope-Durchreichen geplant/gewünscht — Fix muss sich allein in
  gregor_zwanzig lösen lassen, ohne henemm-infra anzufassen); der Claude-Session-
  Bediener, der Schritt 4b manuell ausführt.

## Existing Specs

- `docs/specs/modules/issue_916_988_gate_scope_robustness.md` — Vorgänger-Spec,
  führt den Marker-Mechanismus ein. #1084 ist ein Folgefehler dieser (heute
  implementierten) Lösung. Diese neue Spec muss die "Known Limitations" dort
  ergänzen/korrigieren, ohne AC-1 bis AC-6 der Vorgänger-Spec zu brechen.

## Risks & Considerations

- **Kritischer Pfad:** Fix betrifft das Produktions-Deploy-Sicherheitsnetz. Ein
  Fehlgriff kann entweder (a) die Verifikation weiterhin still überspringen
  (Status quo, Gate-Erosion) oder (b) durch Überkorrektur den ursprünglichen
  #916-Multi-Commit-Bug für `prod_selftest.py` wieder einführen.
- **Nicht anfassen:** `.claude/last_gate_scope.json` nicht von Hand editieren
  (Permission-Layer blockt es ohnehin); `deploy-gregor-prod.sh`
  (henemm-infra-Repo) sollte nicht verändert werden müssen — Fix soll
  eigenständig in gregor_zwanzig funktionieren.
- **Bestehende Tests dürfen nicht regressieren:** AC-1..AC-4 in
  `test_issue_916_gate_scope_marker.py`, alle `write_verdict`/`gate_check`-Tests
  in `test_staging_gate.py`, AC-3/AC-4 in `test_bundle_e_gate_tooling.py`.
- **Kein Mock:** Fixes müssen wie bisher gegen echte Temp-Git-Repos + echte
  Subprozess-Aufrufe getestet werden (Projektregel, kein Mock in Tests).

## Analysis

### Type

Bug (Deploy-Gate-Tooling, kritischer Pfad).

### Gegenprüfung (bug-intake, unabhängig)

Root Cause bestätigt, exakte Code-Referenzen: `staging_gate.py:285,343`
(Marker-Schreiben nach Erfolg), `prod_selftest.py:621,465-466,400,420,422,427`
(Marker-Lesen → `git diff HEAD..HEAD` leer → `docs-only`). Bestätigt zusätzlich
per grep: `scope` im `e2e_verified.json` wird von KEINER Gate-Logik
zurückgelesen (rein informativ) — der `write_verdict`-Fix ist daher risikoarm.

**Verwandte offene Issues gefunden** (gleiche Fehlerklasse, andere Ursache):
- **#1072** — beschreibt das genaue Szenario, für das der Marker-Mechanismus
  (#916) eingeführt wurde (Fremd-Commit landet zwischen Push und Deploy,
  `HEAD~1` allein übersieht ihn). Bereits durch die bestehende, getestete
  Marker-Logik (AC-1 in `test_issue_916_gate_scope_marker.py`) abgedeckt,
  SOFERN der `marker==HEAD`-Sonderfall aus #1084 korrekt behandelt wird. Kein
  zusätzlicher Code in diesem Workflow nötig — nach Deploy verifizieren und
  als Duplikat/durch-#1084-gelöst schließen.
- **#1078** — drittes, unabhängiges Skript (`e2e_commit_gate.py`), eigene
  Root Cause (`git diff --cached` ist nach einem Commit immer leer). Bewusst
  NICHT in diesen Workflow aufgenommen (anderer Code, würde Scope/Risiko
  unnötig vergrößern) — bleibt eigenständiges Issue.

### Strategische Bewertung (Plan/Sonnet, unabhängig)

Bestätigt den Ansatz als "einzig praktikable Lösung unter den Randbedingungen"
(kein Zugriff auf henemm-infra, `prod_selftest.py` läuft als eigener Prozess).
Wichtigste Konkretisierung: **nichts wird neu berechnet** — `gate_check()` hat
den `scope`-Wert zum Zeitpunkt beider `write_last_gate_scope()`-Aufrufe
(docs-only-Skip, full-check-pass) bereits vorliegen, er muss nur mitgeschrieben
werden. Verworfene Alternative (Scope in eigener commit-getaggter Datei analog
`e2e_verified/<sha>.json`) als unnötig komplexer eingestuft.

Bestätigt Backward-Kompatibilität: alte Marker-Dateien ohne neues Feld →
`.get()` liefert `None` → Fallback auf unveränderte, bestehende Diff-Logik
(kein neues Risiko). Bestätigt: der Fix-Commit selbst ändert nur
`.claude/hooks/*.py` + `tests/tdd/*.py` (beides bereits als "ignoriert" in der
Scope-Klassifikation gelistet) → wird selbst als `docs-only` erkannt, kein
Henne-Ei-Problem beim eigenen Deploy.

**API-Konkretisierung:** `write_last_gate_scope(repo_dir, sha, scope=None)`
um optionales Scope-Argument erweitern (statt neuer Funktion); zusätzlich neue
Lesefunktion `read_last_gate_scope_entry(repo_dir) -> dict | None` für den
vollen Eintrag (SHA + Scope), während die bestehende `read_last_gate_scope()`
(nur SHA) für alle unveränderten Aufrufer identisch bleibt.

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|-------------|
| `.claude/hooks/_e2e_paths.py` | MODIFY | `write_last_gate_scope()` um optionales `scope`-Arg erweitern; neue `read_last_gate_scope_entry()` für vollen Marker-Eintrag |
| `.claude/hooks/staging_gate.py` | MODIFY | `gate_check()`: beide Erfolgspfade (Zeile 285, 343) schreiben den bereits berechneten `scope` mit; `write_verdict()`: neuer `scope_override`-Parameter (analog `gate_check`); `main()`: `args.scope` an `write_verdict()` durchreichen |
| `.claude/hooks/prod_selftest.py` | MODIFY | `_detect_committed_scope()`/`run_selftest()`: Kurzschluss — wenn Marker-SHA == aktueller HEAD UND Scope-Feld vorhanden → direkt verwenden statt Diff-Herleitung; sonst unverändertes Fallback |
| `tests/tdd/test_issue_1084_gate_scope_same_pipeline.py` | CREATE | Bug-Reproduktion (gate_check → prod_selftest im selben Repo-Zustand darf NICHT docs-only liefern), Cache-Hit, Backward-Kompat ohne neues Feld, `write_verdict --scope`-Override |

### Scope Assessment

- Files: 3 MODIFY + 1 CREATE
- Estimated LoC: ~55–70 Produktivcode, ~150–220 Testcode
- Risk Level: MEDIUM (kritischer Pfad, aber Backward-kompatibel + bestehende
  AC-1..AC-4/write_verdict/gate_check-Tests bleiben als Regressionsschutz
  unverändert grün)

### Technical Approach

Marker-Datei `.claude/last_gate_scope.json` von `{"gate_scope_sha": sha}` auf
`{"gate_scope_sha": sha, "gate_last_scope": scope}` erweitern. `gate_check()`
schreibt beide Felder bei Erfolg (Wert bereits berechnet, keine Zusatzarbeit).
`prod_selftest.py` nutzt den gecachten Scope NUR, wenn der Marker exakt auf dem
aktuellen HEAD steht (== "der Gate-Check ist gerade erst für genau diesen
Commit gelaufen") — in jedem anderen Fall (isolierter Lauf, spätere Commits,
altes Marker-Format) bleibt die bestehende, getestete Diff-Basis-Logik
unverändert. `write_verdict()` erhält separat einen `scope_override`-Parameter
(risikoarmer, unabhängiger Nebenfix, da rein informatives Attestations-Feld).

### Dependencies

Implementierungsreihenfolge: (1) `_e2e_paths.py` (gemeinsame Basis) → (2)
`staging_gate.py`/`gate_check()` (Schreiber) → (3) `prod_selftest.py` (Leser,
hängt von 1+2 ab) → (4) `write_verdict()`-Scope-Override (unabhängig, eigener
Test/Commit-Gedanke, keine Abhängigkeit zu 1–3).

### Open Questions

- [x] Ist der HEAD~1-Fallback-Ansatz sicher? — Nein, verworfen (würde #916 für
  prod_selftest.py reintroduzieren). Ersetzt durch Cache-Ansatz.
- [x] Muss henemm-infra (`deploy-gregor-prod.sh`) angefasst werden? — Nein,
  Fix ist vollständig in `gregor_zwanzig`/`.claude/hooks/` lösbar.
- Keine offenen Blocker — bereit für `/30-write-spec`.
