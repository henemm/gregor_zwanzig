# agent-os-openspec Improvement Bundle
# Quelle: gregor_zwanzig Workflow-Erfahrungen

Erstellt: 2026-06-19
Basis: gregor_zwanzig `.claude/` (43 Hooks, 11.882 LOC) vs. agent-os v3.1.0 (11 Hooks)

---

## Übersicht

Das gregor_zwanzig-Projekt hat den agent-os-Workflow über viele Monate in Produktion
betrieben und zahlreiche Lücken geschlossen. Dieses Dokument klassifiziert alle
Verbesserungen und bereitet sie für die Aufnahme in agent-os-openspec vor.

**Klassifikation:**
- ✅ **Vollständig generalisierbar** — kann direkt in agent-os übernommen werden
- ⚙️ **Teilweise generalisierbar** — Konzept ist allgemein, Implementierung braucht Anpassung
- ❌ **Projekt-spezifisch** — nur für gregor_zwanzig sinnvoll

---

## 1. State-Management: Workflow v3

**Status:** ✅ Vollständig generalisierbar  
**Priorität:** HOCH — betrifft Kern des Frameworks

### Problem in agent-os (aktuell)
Single flat state (`workflow_state.json`) — nur ein aktiver Workflow gleichzeitig möglich.

### Verbesserung in gregor_zwanzig
**Per-Feature JSON-State:** `.claude/workflows/<name>.json` pro Workflow, Archiv in `_archive/`.

**Neu hinzugekommen:**
- `GZ_ACTIVE_WORKFLOW` Env-Var als einzige erlaubte Aktivierungsmethode (kein Symlink-Fallback)
- `workflow.py phase <ziel> --trigger=command|advance|user_keyword|manual` — Trigger-Typen
- `phase_transitions[]` — vollständiger Phasen-Audit-Trail mit `from/to/at/trigger`
- Fix-Loop-Counter: automatisches Zählen von `phase6b → phase6` Iterationen
- `loc_limit_override` — per-Workflow konfigurierbar (nicht global)
- `workflow.py write-log success` — YAML-Execution-Log vor `complete` (Pflicht)
- Token-Akkumulation über mehrere Sessions (kumulativ in Workflow-State)

**Kritische Regel:** `workflow.py` bricht mit FATAL-Fehler ab wenn `GZ_ACTIVE_WORKFLOW` nicht gesetzt ist. Niemals aus `load_state()` lesen — immer `os.environ['GZ_ACTIVE_WORKFLOW']` direkt.

**Dateien:** `hooks/workflow.py`, `hooks/workflow_state_multi.py`, `hooks/migrate_v2_to_v3.py`

---

## 2. Session Singleton Guard

**Status:** ✅ Vollständig generalisierbar  
**Priorität:** HOCH — verhindert Datenverlust durch parallele Sessions

### Problem
Zwei Claude-Sessions im selben Working-Tree kollidieren: gemeinsame uncommittete Dateien,
gemeinsame Workflow-Buchführung, `git add -A` erfasst Fremd-Arbeit.

### Verbesserung
`session_singleton_guard.py` (PreToolUse SessionStart-Hook):
- Erkennt zweite Session im selben Ordner via Lock-Datei in `.session-locks/`
- Ruft automatisch `EnterWorktree` auf — User muss nichts tun
- Lock wird bei Session-Ende (Stop-Hook) aufgeräumt

**Aus CLAUDE.md (wichtige Konvention für Nutzer):**
> Ein Projektordner = höchstens eine Claude-Session gleichzeitig.
> Für Parallelarbeit: isolierte Arbeitskopie via Workspace-Tool.

---

## 3. Worktree Write Guard

**Status:** ✅ Vollständig generalisierbar  
**Priorität:** HOCH — erzwingt Developer-Agent-Isolation

### Problem
Developer Agent schreibt direkt in den Haupt-Working-Tree statt in Worktree-Isolation.
Uncommittete Arbeit anderer Sessions wird korrumpiert.

### Verbesserung
`worktree_write_guard.py` (PreToolUse Edit/Write-Hook):
- Erzwingt dass Edit/Write nur in `phase6_implement`, `phase7_validate`, `phase8_complete` erlaubt
- Außerhalb dieser Phasen: Block mit klarem Hinweis auf aktuell erlaubte Phase
- Developer Agent bekommt im Briefing immer `export GZ_ACTIVE_WORKFLOW=<name>`

---

## 4. LOC Scope Guard

**Status:** ✅ Vollständig generalisierbar  
**Priorität:** MITTEL

### Problem
Kein Limit für Code-Umfang pro Workflow. Agent "schleicht" Scope-Creep ein.

### Verbesserung
`scope_guard.py` (PreToolUse Edit-Hook):
- Zählt LoC-Delta aller geänderten Dateien seit Workflow-Start
- Default-Limit: **250 LoC**
- Ausnahmen (zählen NICHT): `docs/`, `*.md`, `.gitignore`, generierte Dateien (`.po`, `uv.lock`, `package-lock.json`)
- Override pro Workflow: `workflow.py set-field loc_limit_override 500`
- `workflow.py status` zeigt `LoC-Delta: +N/250`

**Wichtig:** Override braucht User-Permission — nie selbst setzen ohne Rückfrage.

---

## 5. Token-Tracking

**Status:** ✅ Vollständig generalisierbar  
**Priorität:** NIEDRIG — nice-to-have für Transparenz

### Verbesserung
`track_token_usage.py` (Stop-Hook):
- Liest Session-Transcript
- Summiert `input_tokens`, `output_tokens`, `cache_read_tokens` etc.
- Schreibt kumulativ in Workflow-State (`token_usage.*`)
- `workflow.py write-log` schreibt akkumulierte Token ins YAML-Log

---

## 6. Adversary Verdict Gating (verschärft)

**Status:** ✅ Vollständig generalisierbar  
**Priorität:** HOCH — schließt kritische QA-Lücke

### Problem in agent-os (aktuell)
`post_bash.py` setzt `adversary_verdict` aus Test-Output. Aber: kein Gate das Commits
blockiert solange kein Verdict vorhanden. `AMBIGUOUS` führt zu undefiniertem Verhalten.

### Verbesserung
`pre_commit_gate.py` + `qa_gate.py`:
- Commit blockiert bis Verdict gesetzt (nicht None)
- `AMBIGUOUS` → expliziter Override nötig: `workflow.py override-ambiguous "<Grund>"` (TTL 1h)
- `BROKEN` → `qa_gate.py` aufrufen, setzt Verdict aus Test-Output neu
- Nur `VERIFIED` → Commit erlaubt ohne manuelle Intervention

**Aus CLAUDE.md:**
> Nach phase6b muss Verdict gesetzt sein.
> `None`/`BROKEN` → `qa_gate.py` aufrufen.
> Commits blockt pre_commit_gate bis Verdict vorhanden ist.

---

## 7. E2E Scope Detection & Commit Gate

**Status:** ✅ Vollständig generalisierbar  
**Priorität:** MITTEL

### Verbesserung
`e2e_commit_gate.py` (PreToolUse Bash git-commit Hook):
- Erkennt Scope des Commits: `docs-only` / `frontend-only` / `backend` / `full-stack`
- Anhand geänderter Dateipfade (Regex-Patterns konfigurierbar)
- Schreibt `e2e_scope` in Workflow-State → bestimmt E2E-Pfad in `/e2e-verify`
- `docs-only`: Staging-Validierung entfällt

**Pattern-Logik (generalisierbar):**
```python
DOCS_PATTERNS = [r'^docs/', r'^\.md$', r'\.claude/']
FRONTEND_PATTERNS = [r'^frontend/', r'^src/.*\.svelte', r'^src/.*\.css']
BACKEND_PATTERNS = [r'^src/', r'^api/', r'^internal/', r'^cmd/']
```

---

## 8. Secrets Guard

**Status:** ✅ Vollständig generalisierbar  
**Priorität:** HOCH — Sicherheit

### Verbesserung
`secrets_guard.py` (PreToolUse Bash + Edit/Write):
- Scannt Bash-Befehle und Dateiinhalte auf Credential-Pattern
- Patterns: API-Keys, Tokens, Passwörter in Klartext, `.env`-Includes
- Block mit klarem Hinweis: "Nutze Env-Variablen oder secrets.env"

---

## 9. Workflow Execution Log (Pflicht vor `complete`)

**Status:** ✅ Vollständig generalisierbar  
**Priorität:** MITTEL — Audit-Trail

### Verbesserung
`workflow.py write-log success` schreibt YAML in `.claude/workflows/_log/`:
```yaml
workflow: issue-838-fix-time-format
issue: 838
phases: [phase1_context, phase2_analyse, ..., phase7_validate]
phase_transitions:
  - {from: phase5_tdd_red, to: phase6_implement, at: "2026-06-15T14:23:00Z", trigger: command}
fix_loop_count: 1
loc_delta: 87
token_usage:
  input: 145230
  output: 23410
  cache_read: 89200
duration_minutes: 47
verdict: VERIFIED
```

Ohne vorherigen `write-log`-Aufruf blockiert der Hook `workflow.py complete`.

---

## 10. Per-Commit E2E Attestation

**Status:** ✅ Vollständig generalisierbar  
**Priorität:** MITTEL

### Problem
Einzelne `e2e_verified.json` — bei schnellen Commits überschrieben, Race-Condition.

### Verbesserung
`staging_gate.py` schreibt in `.claude/e2e_verified/<sha>.json` (SHA = HEAD-Commit):
- Eine Attestation pro Commit, nie überschrieben
- `deploy-script` liest sha-spezifische Datei: nur gültiger Stand wird deployed
- Retention: max 20 Attestationen (älteste wird gelöscht)
- `verified_commit` + `staging_verdict` + strukturierte Findings pro AC

**Kritische Lektion (Issue #662):**
> Singleton-`e2e_verified.json` führte zu Race-Condition wenn zwei Sessions
> gleichzeitig validieren. SHA-basierte Dateien sind das Fix.

---

## 11. External Validator Agent

**Status:** ✅ Vollständig generalisierbar  
**Priorität:** HOCH — 4-Layer QA

### Was fehlt in agent-os
agent-os hat `implementation-validator` (Code-Analyse). Aber: kein Agent der die App
von außen als echter User testet, ohne Code zu sehen.

### Verbesserung: `external-validator.md`
- Läuft als isolierte Claude-Session (`claude --print`)
- Kennt NUR: Spec (ACs) + laufende App (URL + Credentials)
- Liest keinen Source-Code
- Testet jeden AC manuell durch
- Schreibt Verdict: `VERIFIED` / `BROKEN` / `AMBIGUOUS` mit `Code reference: file:line`

**Wichtig:** Findings-Format ist Pflicht: `Code reference: file:line` (nicht nur Beschreibung).

---

## 12. Staging Validator Agent (UI Adversary)

**Status:** ⚙️ Teilweise generalisierbar  
**Priorität:** MITTEL — nur relevant für Web-UIs

### Verbesserung: `staging-validator.md`
- Playwright gegen Staging-URL
- Prüft jeden AC aus der Spec als DOM-Assertion
- Schreibt Screenshots als Evidenz
- Tri-State Verdict: `VERIFIED` / `BROKEN` / `AMBIGUOUS`
- Wird nach `/5-implement` Phase 9 aufgerufen (parallel zu implementation-validator)

**Anpassung nötig:** Staging-URL ist projekt-spezifisch → als `GZ_STAGING_URL` ENV-Var.

---

## 13. /e2e-verify Skill

**Status:** ⚙️ Teilweise generalisierbar  
**Priorität:** MITTEL

### Verbesserung
Neuer Skill `/e2e-verify` für Post-Push-Verifikation gegen Staging:

1. Smoke gegen Staging (`/` + `/api/health`)
2. Scope bestimmen (aus `e2e_scope` in Workflow-State)
3. `frontend-only` → staging-validator (Playwright)
4. `backend/full-stack` → Test-Ressourcen triggern + Ergebnis prüfen
5. Schreibt `e2e_verified/<sha>.json`

**Anpassung nötig:** Health-Endpunkt und Staging-URL als Konfiguration.

---

## 14. /7-deploy Skill (vollständige Deploy-Pipeline)

**Status:** ⚙️ Teilweise generalisierbar  
**Priorität:** MITTEL

### Verbesserung
Neuer Skill `/7-deploy` mit integriertem Post-Deploy-Selftest:

| Schritt | Was |
|---|---|
| 1 | `git push origin main` |
| 2 | Auto-Deploy auf Staging abwarten |
| 3 | `/e2e-verify` (Staging-Verifikation) |
| 4 | Prod-Deploy via Deploy-Script |
| 4b | Post-Deploy-Selftest (Commit/Health/AC-Attestation) |
| 5 | Issue schließen — nur bei Exit 0 |

**Anpassung nötig:** Deploy-Script-Pfade sind projekt-spezifisch.

---

## 15. Wichtige Konventionen (CLAUDE.md-Regeln)

**Status:** ✅ Vollständig generalisierbar — als Framework-Defaults in agent-os README

### Heartbeat-Readiness-Prinzip
> Monitoring-Pings NUR bei tatsächlichem fachlichen Erfolg.
> Reine "Prozess läuft"-Pings sind verboten.

### Keine Mocked Tests
> Mocked Tests beweisen NICHTS.
> Tests müssen echtes Verhalten beweisen.
> Dateiinhalt-Checks sind ebenfalls verboten (`assert 'xyz' in file.read_text()`).

### Adversary-Findings-Format (Pflicht)
> Bei Findings immer `Code reference: file:line` — nie nur Beschreibung.

### Workflow-Gates: "go" als universelles Keyword
> PO tippt "go" um Phase freizugeben (Spec, Deploy).
> Kein Output an PO = auto-proceed.

### Kein LoC-Override ohne User-Permission
> `workflow.py set-field loc_limit_override` ist Workflow-Bypass.
> Bei >250 LoC: User fragen oder Issue splitten.

### Nie Workflow-State-JSON editieren
> `.claude/workflows/*.json` NIEMALS per Edit/Write.
> State nur via `workflow.py` CLI oder Skills.

### Keine technischen Fragen an den PO
> PO ist nicht-technisch. Technische Entscheidungen selbst treffen.
> AskUserQuestion nur für fachlich-inhaltliche Entscheidungen.

---

## Zusammenfassung: Prioritätsliste für agent-os

| Prio | Verbesserung | Aufwand | Impact |
|------|---|---|---|
| 1 | Multi-Workflow State v3 (per-feature JSON) | HOCH | Kern |
| 2 | Adversary Verdict Gating (verschärft) | MITTEL | QA-Lücke |
| 3 | Session Singleton Guard | NIEDRIG | Stabilität |
| 4 | Worktree Write Guard | NIEDRIG | Isolation |
| 5 | External Validator Agent | NIEDRIG | QA-Layer |
| 6 | LOC Scope Guard | NIEDRIG | Scope-Creep |
| 7 | Secrets Guard | NIEDRIG | Sicherheit |
| 8 | E2E Scope Detection | MITTEL | E2E-Pfad |
| 9 | Per-Commit E2E Attestation | MITTEL | Race-Fix |
| 10 | Workflow Execution Log | NIEDRIG | Audit |
| 11 | Token-Tracking | NIEDRIG | Transparenz |
| 12 | Staging Validator Agent | MITTEL | UI-QA |
| 13 | /e2e-verify Skill | MITTEL | E2E-Workflow |
| 14 | /7-deploy Skill | MITTEL | Deploy-Pipeline |

---

## Was NICHT in agent-os gehört (gregor-spezifisch)

- `renderer_mail_gate.py` — Mail-Template-Gate
- `data_schema_backup.py` — Datenschema-Backup
- `email_spec_validator.py`, `briefing_mail_validator.py` — Mail-Validatoren
- `auto_restart_server.py` — Server-Restart
- `e2e_telegram_live.py` — Telegram-spezifische E2E-Tests
- `validate.py` / `validate-external.sh` — gregor-spezifische Startup-Checks
- `gz-workspace` — Workspace-Tool (Konzept generalisierbar, aber Pfade hardcoded)

---

## Empfohlener Ansatz für agent-os

**Wichtig:** agent-os nutzt 4 konsolidierte Hooks (nicht 43 granulare).
Die Verbesserungen sollten IN die bestehenden Hooks integriert werden — nicht als neue Dateien.

| agent-os Hook | Neue Logik integrieren |
|---|---|
| `edit_gate.py` | + Worktree Write Guard + LOC Scope Guard |
| `bash_gate.py` | + Secrets Guard + Adversary Verdict Gate + E2E Scope Detection |
| `post_bash.py` | + Token-Tracking (Stop-Kontext) |
| `phase_listener.py` | + Fix-Loop Counter + Audit-Trail |
| `workflow.py` | State v3 — größtes Rewrite |

Neue Dateien nur für: `session_singleton_guard.py` (SessionStart-Hook), `external-validator.md`.
