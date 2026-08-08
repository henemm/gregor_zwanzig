# Context: feat-1558-frontend-browser-gate

Issue: #1558 — „Frontend-Änderungen erzwingen einen echten Browserlauf — Gate statt Einzelentscheidung"
Erhoben: 2026-08-07 · Track: Full Process

## Request Summary

Berührt ein ausgelieferter Änderungssatz `frontend/**`, soll ein **Browser-Nachweis** Pflicht
werden: die betroffene(n) Seite(n) wurden in einem echten Browser **geladen** und dabei auf
**Konsolenfehler** geprüft. Fehlt der Nachweis, verweigert das Gate das Staging-Verdict — womit
auch der Produktions-Rollout blockiert bleibt. Anlass: #1552, Kernseite unbedienbar bei 5837
grünen Tests.

## Related Files

| Datei | Relevanz |
|---|---|
| `.claude/hooks/staging_gate.py` (591 Z.) | Trägt das Gate. `write_verdict()` (251–363) schreibt die Attestation; `gate_check()` (366–559) liest sie beim Deploy. |
| `.claude/hooks/staging_gate.py:215–248` | `_telegram_live_gate()` — **das Vorbild** (#686 AC-5). Aufgerufen in `write_verdict()` bei 275–276, **nicht** in `gate_check()`. |
| `.claude/hooks/e2e_telegram_live.py:16–74` | Detektor + Verweigerung des Vorbilds. `_scope_touches_telegram()` (47–74) ist Substring-Match über Dateinamen. |
| `.claude/hooks/_e2e_paths.py:181–233` | **Einzige** Scope-Klassifikation. Erzeugt genau vier Werte. |
| `.claude/hooks/_e2e_paths.py:249–289` | Pfad-Auflösung: Attestation im *shared* Repo-Dir, Commit/Diff aus dem *Worktree*. |
| `.claude/hooks/e2e_browser_test.py` (284 Z.) | Einziges Hook-seitiges Playwright-Werkzeug. Chromium headless, Screenshot nach `/tmp/`. **Erfasst keine Konsolenfehler** (0 Treffer für `page.on`). |
| `.claude/agents/staging-validator.md` | Der empfohlene Nachweis-Erzeuger. Schreibt das Verdict selbst (Step 7). Verlangt DOM-/Sichtbarkeits-/Style-Assertions — **Konsolenfehler kommen nicht vor**. |
| `.claude/commands/e2e-verify.md:69–78` | Schritt 3a: `staging-validator` empfohlen, `e2e_browser_test.py` als manueller Fallback. |
| `.claude/hooks/ui_screenshot_gate.py` | Bestehendes UI-Gate (Vorher/Nachher-Screenshots). Kandidat für die Regel-Budget-Frage „Ersatz statt Zusatz". |
| `frontend/playwright.config.ts` | Root-Config: `baseURL localhost:4173`, `webServer` startet Preview, `storageState playwright/.auth/admin.json`. |
| `frontend/e2e/*.staging.config.ts` (10 Stück) | Ad-hoc-Configs gegen Staging: `GZ_SVELTE_BASE`, `httpCredentials`, eigenes `storageState` je Thema. |
| `frontend/e2e/issue-1093-compare-layout-crash.spec.ts:54–67` | Vorhandenes Konsolenfehler-Muster, ad hoc. |
| `.github/workflows/ci.yml` | 6 Jobs. **Keine** Playwright-TS-Ausführung, keine laufende App. |

## Existing Patterns

**Scope-Klassifikation (`_e2e_paths.py:198–233`)** — genau vier Werte:
`docs-only` · `frontend-only` · `backend` · `full-stack`.
`frontend/`-Präfix setzt `has_frontend`; `src/`, `api/`, `internal/`, `cmd/` setzen `has_backend`;
neutral sind `docs/`, `.claude/`, `*.md`, `README*`, `.gitignore`, `tests/`, `openspec.yaml`;
**unbekannte Pfade zählen konservativ als Backend**. Git-Fehler → `backend` (fail-closed).
⇒ Ein Frontend-Gate muss auf `frontend-only` **und** `full-stack` greifen.

**Verweigerungs-Muster (#686 AC-5)** — der Detektor sitzt in `write_verdict()`, *vor* dem Schreiben.
Verweigert er, entsteht **kein Artefakt**; ohne Artefakt blockt `gate_check()` später den Deploy.
Ein zweiter Prüfpunkt ist unnötig.

**Attestations-Schema** (`.claude/e2e_verified/<sha>.json`), reale Felder:
`verified_commit` · `staging_verdict` · `findings[]` (`{ac, status, url, evidence, workflow}`) ·
`verified_at` · `scope` · `environment`. Findings werden über das `workflow`-Feld verlustfrei
gemerged (310–352); Retention 20.

**Staging-Playwright** — Login per API statt UI (Token-Bucket 30/h, #703), `storageState` mit
`chmod 0600`, zwei Credential-Ebenen: nginx-Basic (`GZ_VALIDATOR_*`) und App-Login (`GZ_AUTH_*`).

**Screenshot-Konvention:** `docs/artifacts/<workflow>/`. `e2e_browser_test.py:54` weicht ab (`/tmp/`).

## Dependencies

- **Upstream:** `_e2e_paths` (Scope, Pfade, Diff), git-Zustand des Worktrees, Playwright + Chromium,
  Staging-Erreichbarkeit, beide Credential-Sätze.
- **Downstream:** `deploy-gregor-prod.sh:174,210` (zwei `--check`-Aufrufe, blocken bei Exit≠0),
  `prod_selftest.py:691–695` (verlangt `VERIFIED`-Präfix), `staging-validator` (Step 7),
  `.claude/commands/e2e-verify.md`. **Jede Session dieses Repos** liefert über diesen Pfad aus.

## Existing Specs

- `docs/specs/_archive/modules/issue_686_telegram_functional_live_tests.md:150–154` — AC-5, das Vorbild.
- Tests des Vorbilds: `tests/tdd/test_issue_686_telegram_functional_live.py`,
  `test_issue_728_telegram_scope_neutral.py`, `test_issue_1121_git_diff_returncode.py`,
  `test_staging_gate_verdict_merge.py` (neutralisiert `_telegram_live_gate` per monkeypatch —
  dasselbe Seam wird ein Browser-Gate brauchen).

## Risks & Considerations

1. **Das Vorbild trägt einen Fehler.** `_telegram_live_gate()` diffft fest `HEAD~1..HEAD`
   (`staging_gate.py:237`), während die reguläre Scope-Erkennung die Marker-Kette seit dem letzten
   Gate-Lauf nutzt (`_scope_diff_base`, 112–153). Bei mehreren Commits seit dem letzten Lauf sieht
   der Zweig **nur den letzten** — eine Frontend-Änderung zwei Commits zurück wäre unsichtbar.
   Baugleiches Kopieren erbt einen blinden Wächter (Muster #1431).

2. **Das Gate kann Echtheit nicht prüfen — nur Anwesenheit.** `--write-verdict` validiert heute
   ausschließlich das Verdict-Präfix; ob Screenshots existieren oder Evidence echt ist, prüft es
   nicht. Ein Nachweisfeld, das der Aufrufer selbst befüllt, ist eine Selbstauskunft.
   ⇒ Der Nachweis muss **maschinell erzeugt** und vom Gate **nachgemessen** werden.

3. **Login-Screenshot-Falle (#1307).** `page.fill`/`page.click` werfen nicht, wenn die Anmeldung
   scheitert; der Lauf schreibt trotzdem einen Erfolgsbericht. „Keine Konsolenfehler" auf dem
   Login-Screen ist wertlos. ⇒ Zwei unabhängige Merkmale, dass die Zielseite **angemeldet** erreicht
   wurde, sonst Abbruch ohne Nachweis.

4. **Anti-Stale.** Ein Glob nach „irgendeinem bestandenen Bericht" besteht mit einer Leiche.
   Nachweis vor dem Lauf entfernen: erst weg, dann neu belegen.

5. **Blast Radius.** Zu streng ⇒ die Auslieferung steht repo-weit, für alle Sessions.
   Fail-soft bei **eigener** Störung (Import-/Playwright-Fehler) ist Hauskonvention — aber
   fail-soft bei fehlendem Nachweis wäre genau das Sicherheits-Theater, das #1558 abschafft.
   Die Grenze zwischen beidem gehört in die ACs.

6. **Arbeitsverzeichnis.** `--write-verdict` nimmt den Commit aus `git rev-parse HEAD` des **cwd**.
   Aufruf aus dem Hauptordner statt dem Worktree attestiert einen fremden Stand (#1447 S1).
   `--e2e-path` ist praktisch unbenutzbar: `bash_gate.py` erkennt den Pfad als Freigabe-Marker.

7. **Login-Rate-Limit 30/h.** Ein Smoke über vier Kernseiten darf nicht viermal einloggen —
   einmal per API anmelden, `storageState` wiederverwenden.

8. **CI-Variante ist teurer als sie aussieht.** Playwright läuft heute **nirgends** in der CI:
   kein npm-Script, keine laufende App, kein Browser-Setup im `frontend-test`-Job. Der Smoke
   bräuchte Build + Preview-Server + Chromium-Install im CI-Lauf. Der Staging-Weg nutzt dagegen
   vorhandene Infrastruktur vollständig. ⇒ Getrennte Scheiben, Gate zuerst.

9. **Regel-Budget.** Prüfdatum 2026-11-05, Fang-Beleg #1552 liegt vor. Zu prüfen, ob
   `ui_screenshot_gate.py` ganz oder teilweise **ersetzt** werden kann statt danebenzustehen.

## Analysis

### Type
Feature (neues Gate) — kein Bug.

### Die Weichenstellung: Gate LIEST vs. Gate FÜHRT AUS

Zwei Bauarten standen zur Wahl:

- **A — Gate liest einen Nachweis.** Ein Agent führt den Browserlauf aus, legt einen Nachweis ab,
  `write_verdict()` prüft dessen Anwesenheit und Frische.
- **B — Gate führt den Browserlauf selbst aus.** `write_verdict()` startet bei Frontend-Scope
  selbst einen Playwright-Lauf gegen Staging und verweigert das Verdict bei Konsolenfehlern.

**Entschieden: B.** Bei A sind Nachweis-Erzeuger und Gate-Aufrufer dieselbe Instanz — wer den
Nachweis schreiben kann, kann ihn erfinden. Das ist kein theoretisches Risiko:

- `pre_issue_close_design_gate.py:64–72` ist ein Attestations-Leser im Betrieb. Er globt
  `design-diff-*.json` und akzeptiert alles mit `passed: true` — ohne zu prüfen, ob die
  referenzierten Bilder existieren. **Eine handgeschriebene JSON-Datei besteht dieses Gate.**
- `write_verdict()` prüft `findings_path` heute nur auf JSON-Validität (278–282), nie darauf, ob
  die genannten `evidence`-Pfade existieren.

A wäre nur durch eine unabhängige Instanz zu retten (CI-Job) — das ist dann faktisch B an anderer
Stelle. **Die tragende Eigenschaft ist: die Prüf-Logik läuft im Gate-Code, nicht im Agenten-Code.**

**Preis von B, ehrlich benannt:** Staging-Erreichbarkeit wird Voraussetzung für jeden
Frontend-Deploy. Der Agent entscheidet weiterhin, *ob* er `--write-verdict` aufruft — das ist
unvermeidbar. Aber wenn er es aufruft, kann er das Ergebnis nicht mehr durch Behauptung erkaufen.

### Machbarkeit — gemessen

| Frage | Befund |
|---|---|
| Playwright verfügbar? | Ja. `pyproject.toml:87` (`>=1.57.0`), Chromium unter `~/.cache/ms-playwright/chromium-1200/` mit `INSTALLATION_COMPLETE`. |
| Credentials? | `load_validator_env()` (`design_fidelity_diff.py:145–164`) lädt beide Ebenen: `.claude/validator.env` (`GZ_VALIDATOR_*`) und `.env` (`GZ_AUTH_*`). Direkt wiederverwendbar. |
| Login-Screenshot-Falle gelöst? | **Ja, bereits.** `unauthenticated_reason()` (`design_fidelity_diff.py:167–194`) prüft zwei unabhängige Merkmale (Redirect auf `/login`, sichtbares Passwortfeld) und schreibt bei Misserfolg **kein** Artefakt. Genau die Anforderung aus Risk 3 — importierbar statt nachzubauen. |
| Laufzeit? | **Gemessen: 1,0 s** für Browser-Start + eine Staging-Seite mit Basic-Auth (HTTP 200). Die kursierende „>30 s"-Zahl betrifft den vollen Fidelity-Diff-Lauf inkl. Screenshots, nicht das Laden. Sechs Seiten + einmal Formular-Login bleiben deutlich im Sekundenbereich. |
| Import-Weg? | `.claude/hooks/` ist kein Package. `staging_gate.py:45–53` löst das bereits per `importlib.util.spec_from_file_location` für `_e2e_paths.py` — dasselbe Muster ist 1:1 übertragbar. |

**Einschränkung:** Der Login-Code selbst steckt inline in `take_screenshot()` (239–248), ist also
keine isolierte Funktion. `load_validator_env()` und `unauthenticated_reason()` sind dagegen sauber
wiederverwendbar. Nicht geprüft: ob der Hook-Kontext dieselben Netzwerkrechte hat wie eine
interaktive Sitzung.

### Affected Files

| Datei | Typ | Beschreibung |
|---|---|---|
| `.claude/hooks/e2e_frontend_browser_gate.py` | CREATE | Detektor + Browserlauf + Konsolenfehler-Auswertung. Vorbild `e2e_telegram_live.py`. |
| `.claude/hooks/staging_gate.py` | MODIFY | `_frontend_browser_gate()` analog `_telegram_live_gate()`; Aufruf **nach** Zeile 296. |
| `tests/tdd/test_frontend_browser_gate.py` | CREATE | Gate-Logik ohne Netz (Scope-Zweige, Fail-Grenzen). |
| `tests/tdd/test_staging_gate_verdict_merge.py` | MODIFY | Neuen Seam neutralisieren, analog Z. 70–73 für Telegram. |

### Entscheidungen

1. **Einbauort:** nach der Scope-Berechnung (`staging_gate.py:296`), nicht bei 275 wie Telegram.
   Gemessen: dort ist `scope` noch nicht berechnet. Das Gate **konsumiert** `scope in
   ("frontend-only", "full-stack")` statt einen eigenen Diff zu ziehen — damit kann der
   `HEAD~1`-Erbfehler strukturell nicht entstehen, weil keine zweite Diff-Logik existiert.
2. **Seiten:** fester Kernseiten-Satz. Eine Zuordnung „geänderte Komponente → betroffene Route"
   ist bei 235 `lib`-Komponenten gegen 27 Routen ohne Dependency-Graph eine Rate-Funktion mit hoher
   Fehlerquote. `design_fidelity_diff.py:21–70` löst dasselbe Problem bereits mit einer festen Karte.
3. **Fail-Grenze:**
   - *Durchlassen + WARN* nur bei **eigener** Störung: Modul-Import-/Syntaxfehler des Gates.
   - *Blockieren* bei: Playwright fehlt, Staging nicht erreichbar, Login scheitert, Credentials
     fehlen, Konsolenfehler vorhanden. Das sind Fälle von „Nachweis nicht erbringbar" —
     als Freifahrtschein wären sie genau das Sicherheits-Theater, das #1558 abschafft.
   - Kein zweiter stiller Notausgang: `GZ_SKIP_E2E_GATE=1` (`staging_gate.py:383–385`) existiert
     bereits, laut und geloggt.
4. **Anti-Stale** entfällt als eigenes Problem: Es gibt keinen zwischengelagerten Nachweis, der
   veralten könnte — der Lauf passiert im selben Aufruf, der das Verdict schreibt.

### Scope Assessment

- Dateien: 4 (2 neu, 2 geändert)
- Geschätzt: **~190–220 LoC** — unter dem 250er-Limit, aber knapp. Konsolenfehler-Erfassung
  bewusst einfach halten (`page.on('console')` + `page.on('pageerror')`, Filter auf `type=='error'`,
  keine Retry-Heuristik).
- **Risiko: MITTEL–HOCH.** Der Eingriff sitzt im gemeinsamen `write_verdict()`-Pfad, den *jede*
  Session durchläuft. Greift die Scope-Prüfung falsch, blockiert das auch Backend-Deploys.
  Mitigation: Test-Seam wie beim Telegram-Gate.

### Scheiben-Schnitt

- **Scheibe 1 (dieses Issue):** Variante B in `write_verdict()`, fester Kernseiten-Satz,
  Scope-Wiederverwendung, Fail-Grenze wie oben.
- **Scheibe 2 (eigenes Issue, NICHT hier):** CI-Playwright-Smoke. Braucht Build + Preview-Server +
  Chromium im Runner und einen eigenen Login-/Fixture-Mechanismus — kein Copy-Paste aus Scheibe 1.
  Das Issue markiert diesen Teil selbst als „alternativ oder ergänzend zu prüfen".

### Offene Fragen

- [ ] Blockieren Konsolen-**Warnungen** auch, oder nur `error`? (Vorschlag: nur `error`, sonst
      erstickt das Gate an Rauschen aus Drittbibliotheken.)
- [ ] Welcher Trip für `/trips/[id]`? Auf Staging existiert ein geseedeter Test-Trip
      (`global.setup.ts:66–118` legt `e2e-cockpit-test` an) — zu prüfen, ob er dort vorhanden ist.
- [ ] Greift das Gate auch bei `AMBIGUOUS`-Verdicts? (Vorschlag: ja — auch ein AMBIGUOUS-Verdict
      wird abgelegt und kann später als Vorgänger dienen.)
