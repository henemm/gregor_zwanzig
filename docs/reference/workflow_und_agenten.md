# Workflow & Agenten — Detailmechanik

> Ausgelagert aus `CLAUDE.md` (#2640, 2026-10-30). In `CLAUDE.md` bleibt nur der Kern:
> Spec-Freigabe ist das einzig Freigabepflichtige, Rückfragen nur per `AskUserQuestion`,
> Deploy läuft ohne Halt, Mutations-Gegenprobe ist Pflicht. Hier steht der Rest wörtlich.

## Befehle

OpenSpec-Workflow mit Adversary Verification (Einstiege: `/00-intake` — auch Bugs starten dort, `/00-bug` gibt es nicht mehr — und `/01-feature`):

| Command | Purpose | PO-Eingriff |
|---------|---------|-------------|
| `/10-context` | Kontext sammeln | — |
| `/20-analyse` | Request verstehen, Codebase recherchieren | Optional: 3-Satz-Zusammenfassung korrigieren |
| `/30-write-spec` | Spezifikation erstellen | **Pflicht: ACs auf Deutsch freigeben** (`approved`/`freigabe`) |
| `/40-tdd-red` | Fehlschlagende Tests schreiben (RED) | Optional: AC-Test-Mapping lesen |
| `/50-implement` | Implementieren (GREEN) + Adversary | — |
| `/60-validate` | Validieren vor Commit | — |
| `/70-deploy` | Staging-Verifikation + Prod-Deploy | — (läuft autonom, **kein** Freigabe-Halt) |

**Freigabepflichtig ist allein die Spec.** Deploy läuft ohne Halt durch: nach dem Merge zieht die Kette Staging-Poll → `/e2e-verify` → `deploy-gregor-prod.sh` → `prod_selftest.py` → Issue-Close **am Stück**. Der PO liest das Ergebnis danach, nicht vorher als Freigabe. Ein selbst formulierter „Tech-Lead-Brief" mit anschließender Bitte um 'go' ist dieselbe verbotene Prozessfrage in Freitextform. Einzige erlaubte Unterbrechung: ein echtes Hard Gate scheitert (Staging-Verdict BROKEN, Selftest-Exit ≠ 0) — dann eskalieren mit konkretem Befund.

**Herkunft der Befehle:** `/00-…` bis `/60-…` kommen aus dem Plugin agent-os-openspec; projekteigen in `.claude/commands/` sind nur `/70-deploy` (ersetzt das Plugin-Template), `/e2e-verify`, `/next-ticket`, `/radar`.

**Rückfragen an den PO IMMER über das `AskUserQuestion`-Tool** — nie als Freitext-Frage am Ende einer Antwort (PO-Vorgabe 2026-10-08). Gilt auch für Spec-Freigaben.

## Adversary Verification

Nach der Implementation führt ein unabhängiger `implementation-validator` (Sonnet) einen strukturierten Dialog, um die Implementierung aktiv zu brechen. Tri-State Verdict: VERIFIED / BROKEN / AMBIGUOUS. Details: `docs/features/openspec_workflow.md`. Bei Findings ist `Code reference: file:line` Pflicht.

**Mutations-Gegenprobe ist PFLICHT, keine Kür.** Der Adversary muss die Implementierung gezielt verfälschen und melden, **welche Verfälschung KEIN Test fängt** — wird kein Test rot, ist das ein Finding. Ein grüner Testlauf beweist nur, dass die Tests durchlaufen, nicht dass sie etwas bewachen. Leitfrage: **Ist die Zusicherung an der Stelle geprüft, an der sie WIRKT — oder nur dort, wo der Code steht?** Ablauf und Mutations-Familien: `.claude/agents/implementation-validator.md`, Sektion „Step 3b". **Mutationen nur per String-Ersetzung mit externer Sicherungskopie — nie `git checkout/stash/reset`** (hat einmal die gesamte unkommittete Arbeit gelöscht).

**Fresh Eyes:** Bei UI-Änderungen prüft zusätzlich ein `fresh-eyes-inspector` Screenshots OHNE Bug-Kontext.

## Oberflächen-Scheiben: Scheibe → Staging-Abgleich → Prüf-Agent (ADR-0112, #2913)

Seiten nach einem Mockup (zuerst „Einstellungen neu“, Mockup Fassung 3) entstehen in Scheiben, je eine
mit eigener Spec. „Fertig“ heißt „Elementliste lückenlos und Prüf-Agent ohne Befund“, nicht „Tests grün“.
Ablauf am Ende jeder Scheibe: **Scheibe → Staging-Abgleich → Prüf-Agent**.

1. **Scheibe:** nur aus Bausteinen (`atoms/molecules/organisms`); fehlende Bausteine zuerst in einem eigenen
   Bausteine-Workflow. Neue Seiten-/Reiter-Dateien in `SEITEN_SCOPE` von `bausteine_waechter` eintragen,
   Abschnitte mit `data-abschnitt="<name>"` aus der Elementliste markieren, neue Texte nur über den Katalog.
2. **Staging-Abgleich:** `npm run elementliste:abgleich -- --scope <reiter[/zustand]>` (im Ordner
   `frontend`, nach dem Push gegen Staging) mit der Teilmenge der Scheibe; Bericht JSON + Markdown.
   Abschluss der Scheibe erst mit `--strict` grün für ihre Teilmenge (DE, danach `--sprache en`).
   Ganze Seite: `--abnahme` (Exit ≠ 0, solange `abweichend`/`nicht_pruefbar`/`zusaetzlich` ohne Besitzer in
   `docs/context/einstellungen_neu/elementliste_besitzer.json`); Details in `gates_und_ratschen.md`.
   Vor dem Abgleich läuft der Generator-Spec (`npx playwright test --config
   playwright.elementliste.mockup.config.ts`), falls Mockup oder Katalog geändert wurden.
3. **Prüf-Agent `mockup-bildpruefer`:** bekommt nur Mockup-Bild, Staging-Bild (gleicher Viewport, gleicher
   Zustand) und den Elementlisten-Auszug, keinen Quellcode. Je Scheibe **höchstens zwei Runden**; er ergänzt
   die Elementliste um die Optik und ersetzt sie nicht. Befunde der zweiten Runde, die offen bleiben, gehen
   als Issue an die nächste Scheibe.

## Product Owner Pattern

Main Context (Opus) ist reiner Orchestrierer und schreibt KEINEN Code. Implementierung geht an den Developer Agent (Opus, Worktree-Isolation). >10 Min ohne grüne Tests → `TaskStop` + Neustart mit präziserem Briefing; max 2 Versuche, danach Eskalation.

## Agenten-Modelle

`developer` (Plugin-Pendant `developer-agent`)/`user-story-planner` Opus · `bug-intake`/`bug-investigator`/`analysis-challenger`/`feature-planner`/`spec-writer`/`implementation-validator`/`staging-validator`/`external-validator`/`fresh-eyes-inspector` Sonnet · `docs-updater`/`spec-validator`/`test-runner`/Explore Haiku · Katalog-Migrationspakete (i18n) → `developer` mit Haiku (scheitern zwei Läufe, Wechsel auf Sonnet; Konventionen Epic #2644, Abschnitt 7).

## Workflow-State

| Was | Regel |
|-----|-------|
| **OPENSPEC_ACTIVE_WORKFLOW** | `export OPENSPEC_ACTIVE_WORKFLOW=<name>` ist die Variable, die das Plugin agent-os-openspec (ab 4.4.2) setzt und liest. **Symlink-Fallback ist deaktiviert** — `workflow.py` bricht FATAL ab ohne die Variable. Niemals `state['active_workflow']` lesen. Beim Agent-Spawn immer im Prompt übergeben. **Korrektur 2026-10-30 (#2640):** Bis dahin nannte `CLAUDE.md` hier `GZ_ACTIVE_WORKFLOW` als EINZIGE erlaubte Methode; das ist veraltet. `GZ_ACTIVE_WORKFLOW` wird nur noch als Fallback von `design_fidelity_diff.py`, `pre_issue_close_design_gate.py` und `prod_selftest.py` gelesen. |
| **Execution-Log vor `finish`** | `workflow.py write-log success`, dann `workflow.py finish`. Ohne Log blockt der Hook. `workflow.py`/`qa_gate.py`/`adversary_dialog.py` liegen im Plugin agent-os-openspec, **nicht** in `.claude/hooks/` (Plugin-Modus seit 465380c1e). |
| **LoC-Limit 250/Workflow** | `workflow.py status` zeigt `LoC-Delta: +N/250`. Überschritten → `workflow.py set-field loc_limit_override 500`. `docs/`/`*.md`/`.gitignore` und generierte Dateien zählen nicht. |
| **Adversary-Verdict Gating** | `AMBIGUOUS` → `workflow.py override-ambiguous "<Grund>"` (TTL 1h); `None`/`BROKEN` → `qa_gate.py`. Commit blockt ohne Verdict. |
| **State-Ablage** | `.claude/workflows/<name>.json` (laufend) / `_archive/<name>.json` (abgeschlossen) |

**Hooks erzwingen diesen Workflow** — Edit/Write auf geschützte Dateien ist blockiert. Blockiert ein Gate und die Meldung reicht nicht: `docs/reference/gates_und_ratschen.md`.

## Backlog & Nebenbefunde

**GitHub Issues ist die Single Source of Truth für offene Arbeit.** Neue Features → Label `enhancement`; Bugs → Label `bug`; fertig → Issue schließen. **NICHT in Markdown-Dateien planen.** Root-Cause-Analysen → `docs/project/known_issues.md`; strategische Entscheidungen → `docs/project/strategic-directions.md`.

**Nebenbefund-Triage:** Nebenbefunde werden NICHT automatisch eigene Issues. **Eigenes Issue nur bei:** (a) nutzersichtbarem Fehlverhalten, (b) Datenverlust-/Sicherheitsrisiko, (c) fälschlich blockierendem Gate. **Alles andere** → Checkbox-Zeile im rollierenden Sammel-Issue **#1199**; Test-/Gate-Befunde in #1196/#1197. Einträge ohne PO-Bestätigung verfallen nach 30 Tagen. Adversary-Findings der Stufe LOW/kosmetisch sind per Default Sammel-Einträge.

## Regel-Budget

Jede neue Pflicht-Regel, jedes neue Gate, jeder neue Pflicht-Validator muss beim Einführen entweder **eine bestehende Regel ersetzen** oder ein **Prüfdatum (+90 Tage)** tragen. Am Prüfdatum: kein nachweisbarer Fang → Rückbau. Prüfdaten-Tabelle: `docs/reference/gates_und_ratschen.md`. Wirkmodell: `docs/analysis/backlog-spirale-2026-07.md`.

## Messaging

Diese Instanz heißt `gregor`. Siehe `~/.claude/CLAUDE.md` → „Inter-Instance Messaging".

**VERBOTEN: MQ-Nachrichten `gregor` → `gregor`.** Alle Parallelsitzungen dieses Projekts
teilen sich dieselbe MQ-Adresse `gregor` — eine Nachricht an `gregor` landet also bei einem
selbst, benachrichtigt aber den PO per Telegram. Das ist Lärm, kein Kanal (PO-Ansage
2026-08-16).

| Empfänger | Weg |
|---|---|
| **Andere Sitzung im selben Projekt** (paralleler Worktree/Tab) | `ListAgents` → `SendMessage({to: "<Name aus der Liste>", message: "…"})` — direkt, sofort, ohne PO-Benachrichtigung |
| **Andere Instanz** (`infra`, `n8n`, `website`, `nightjet`, `security`) | `/home/hem/claude-mq/send.sh gregor <empfaenger> …` |

MQ ist ausschließlich der **Instanz-übergreifende** Weg. Innerhalb von `gregor` gilt immer
`SendMessage`.
