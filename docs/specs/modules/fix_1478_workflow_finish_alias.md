---
entity_id: fix_1478_workflow_finish_alias
type: module
created: 2026-08-09
updated: 2026-08-09
status: draft
version: "1.0"
tags: [workflow-engine, harness-fehlalarm, plugin]
---

# workflow.py: Alias `finish` für `complete`

## Approval

- [ ] Approved

## Purpose

`workflow.py complete` — der letzte Buchungsschritt eines Workflows — ist aus jeder
worktree-isolierten Session heraus nicht ausführbar: der Worktree-Wächter des
Claude-Code-Harness liest das Wort `complete` als bash-Builtin (programmierbare
Vervollständigung) und blockiert die gesamte Kommandozeile, unabhängig vom
vorangestellten Pfad. Ein zusätzlicher, gleichwertiger Unterbefehlsname räumt den
Fehlalarm ab, ohne den Wächter anzufassen. Issue #1478 (Teil 2 von 2 — Teil 1, das
RED-Artefakt-Suchpfadproblem, ist nicht Gegenstand dieser Spec).

## Source

**Schicht-Hinweis (abweichend vom Standardfall):** Diese Änderung betrifft nicht
Frontend/Go-API/Python-Core von `gregor_zwanzig`, sondern das externe Framework-Repo
`henemm/agent-os-openspec` (Marketplace `henemm-private`, Directory-Quelle
`/home/hem/agent-os-openspec`), das von allen sechs Claude-Instanzen des Servers
gemeinsam genutzt wird. `gregor_zwanzig` selbst besitzt kein eigenes
`.claude/hooks/workflow.py` — nur zwei Doku-Zeilen verweisen auf den Unterbefehl.

- **File:** `agent-os-openspec/core/hooks/workflow.py` (Repo:
  `/home/hem/agent-os-openspec`, nicht Teil dieses Projekt-Checkouts)
- **Identifier:** `COMMANDS`-Dict, Zeile ~1185

## Estimated Scope

- **LoC:** ~40 (überwiegend Test; Doku zählt nicht gegen das Projekt-LoC-Limit und
  betrifft ohnehin ein anderes Repo)
- **Files:** ~13 (1 Code, 1 Test, ~11 Doku-/Aufrufzeilen über zwei Repos)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `cmd_complete` (workflow.py) | upstream, unverändert | Zielfunktion, auf die der neue Name zeigt |
| Plugin-Marketplace-Sync (`directory`-Quelle) | Infrastruktur | überträgt Source-Repo-Änderungen automatisch in `~/.claude/plugins/cache/henemm-private/agent-os-openspec/3.10.2` — empirisch bestätigt (Cache-Kopie zeitlich neuer, inhaltlich identisch zum Source) |
| `gregor_zwanzig/.claude/commands/70-deploy.md`, `CLAUDE.md` | downstream | zwei Aufrufstellen im Projekt-Repo, eigener Folge-PR |

## Implementation Details

```python
# agent-os-openspec/core/hooks/workflow.py — COMMANDS-Dict
COMMANDS = {
    "start": cmd_start,
    ...
    "complete": cmd_complete,
    "finish": cmd_complete,   # NEU — Alias, siehe Issue #1478
    "abandon": cmd_abandon,
    ...
}
```

Kein Logikcode ändert sich — `cmd_complete` bleibt unverändert und wird unter zwei
Namen erreichbar. `complete` bleibt dauerhaft gültig (Rückwärtskompatibilität für
laufende Sitzungen und fremde Projekt-Dokus, die den alten Namen noch verwenden).

Aufrufstellen, die auf den neuen Namen umgestellt werden (alle im Plugin-Repo, plus
zwei im Projekt-Repo):

- `agent-os-openspec/core/commands/80-workflow.md:96`
- `agent-os-openspec/core/commands/00-bug.md:111`
- `agent-os-openspec/core/commands/99-reset.md:21`
- `agent-os-openspec/setup.py:566,602`
- `agent-os-openspec/README.md`, `CLAUDE.md`, `docs/WORKFLOW_GUIDE.md`,
  `docs/specs/bug-fix-fast-track.md`
- `agent-os-openspec/.claude-plugin/plugin.json` (Version 3.10.2 → 3.11.0)
- `agent-os-openspec/CHANGELOG.md` (neuer Eintrag)
- `gregor_zwanzig/.claude/commands/70-deploy.md:91`
- `gregor_zwanzig/CLAUDE.md:41`

## Expected Behavior

- **Input:** `python3 <pfad>/workflow.py finish` (aus einer worktree-isolierten Sitzung
  heraus, mit vorher gesetztem `phase8_complete` und geschriebenem Execution-Log)
- **Output:** identischer End-State wie bisher `complete` — Workflow-JSON wandert nach
  `_archive/`, Statusmeldung wie beim Altnamen
- **Side effects:** keine neuen. `complete` bleibt unverändert nutzbar (getestet, nicht
  nur behauptet — siehe AC-2)

## Acceptance Criteria

- **AC-1:** Given ein Workflow in `phase8_complete` mit geschriebenem Execution-Log,
  When `workflow.py finish` aufgerufen wird, Then ist der End-State (archiviertes
  JSON, Statusausgabe) inhaltlich identisch zu einem Referenzlauf mit
  `workflow.py complete` auf demselben Ausgangszustand.
  - Test: Subprozess-Test (Muster `tests/test_workflow_abandon_82.py`, hermetisch via
    `CLAUDE_PROJECT_DIR=tmp_path`) — zwei identisch präparierte Workflow-Fixtures, einer
    mit `complete` beendet, einer mit `finish`; beide resultierenden `_archive/`-JSONs
    werden bis auf Zeitstempelfelder verglichen.

- **AC-2:** Given derselbe Zustand, When `workflow.py complete` weiterhin aufgerufen
  wird, Then funktioniert der Altname unverändert (keine Regression durch die
  Alias-Einführung).
  - Test: derselbe Subprozess-Test ruft explizit auch `complete` auf und prüft Exit 0 +
    unveränderten Output gegenüber einem vor der Änderung aufgezeichneten Referenzlauf.

- **AC-3:** Given eine worktree-isolierte Claude-Code-Sitzung (echter Wächter aktiv,
  kein Unit-Test-Mock), When `finish` als Bash-Kommando ausgeführt wird (mit
  vorangestelltem Pfad, wie es die Skills tatsächlich tun), Then blockiert der
  Worktree-Wächter NICHT — im Unterschied zu `complete`, das nachweislich blockiert.
  - Test: **Kein automatisierter Test möglich** (der Wächter ist Harness-Infrastruktur,
    nicht Teil der Codebasis). Manueller Nachweis während Implementierung/Adversary:
    realer `echo finish` und realer `workflow.py finish`-Aufruf aus dieser Sitzung,
    Ergebnis im Adversary-Protokoll festgehalten. Das ist der eigentliche Beweis der
    Spec — AC-1/AC-2 allein würden einen funktionslosen Alias nicht von diesem
    unterscheiden.

- **AC-4:** Given der Marketplace `henemm-private` ist vom Typ `directory`, When das
  Source-Repo verändert und diese Sitzung eine Skill-Instruktion neu lädt, Then
  spiegelt die aufgelöste Cache-Kopie (`~/.claude/plugins/cache/henemm-private/
  agent-os-openspec/<version>`) den neuen Stand — ohne manuellen Cache-Eingriff.
  - Test: nach der Code-Änderung `diff` zwischen Source- und Cache-Kopie von
    `workflow.py`; muss nach einer neuen Skill-Ladung identisch sein (Fortsetzung der
    bereits in der Analysephase gemessenen Beobachtung, dass beide Kopien synchron
    bleiben).

## Known Limitations

- Löst **nur** Teil 2 von #1478. Teil 1 (RED-Artefakt-Suche im Hauptrepo statt
  Worktree, `tdd_enforcement.py`) bleibt offen, eigene Scheibe.
- Der Wächter selbst (Harness) bleibt unverändert — künftige, noch unentdeckte
  Bash-Builtin-Kollisionen (`test`, `type`, `read` u.ä. als Unterbefehlsnamen) sind mit
  diesem Fix nicht pauschal ausgeschlossen, nur der konkret gemeldete Fall.
- Rückwärtskompatibilität ist Pflicht, aber nicht ewig geplant: `complete` wird nicht
  aktiv abgekündigt; ein künftiges Aufräumen wäre ein separates Ticket mit eigener
  Migrationsfrist über alle sechs Instanzen hinweg.
- **AC-4 nachträglich als Harness-Grenze eingestuft (PO-Entscheidung 2026-08-09,
  gemessen im Adversary-Lauf):** Der Fix ist gemergt auf `origin/main` von
  `agent-os-openspec` (PR #91, Commit `e07e01d`) und der gemeinsam genutzte Checkout
  `/home/hem/agent-os-openspec` ist per Fast-Forward aktuell. Der **versionierte
  Plugin-Cache** (`~/.claude/plugins/cache/henemm-private/agent-os-openspec/3.10.2`,
  von `installed_plugins.json` referenziert) zieht das **nicht automatisch** nach —
  bestätigt: `CLAUDE_PLUGIN_ROOT` ist in dieser Sitzung nicht gesetzt, die
  Skill-eigene Pfadauflösung fällt auf den stehengebliebenen Cache-Eintrag zurück.
  Das ist ein bereits dokumentiertes Merkmal der Plugin-Cache-Architektur
  (`~/.claude/plugins/cache/.../` hinkt der `directory`-Quelle nach Fremd-Releases
  grundsätzlich hinterher), keine neue Lücke dieses Fixes. Ob/wann ein Session-Neustart
  oder ein Plugin-Update den Cache auffrischt, liegt außerhalb dessen, was aus einer
  laufenden Sitzung heraus ohne Hand-Eingriff in Harness-Zustand geprüft oder erzwungen
  werden kann — bewusst nicht versucht.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** additiver Alias auf Werkzeug-Ebene (nicht Produktarchitektur von
  `gregor_zwanzig`), betrifft kein Entscheidungsfeld aus `docs/adr/`. Präzedenz für
  „Harness-Fehlalarm im Framework mildern" bereits etabliert: CHANGELOG 3.10.2, Issue #87.

## Changelog

- 2026-08-09: Initial spec created
