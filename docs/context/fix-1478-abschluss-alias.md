# Context: fix-1478-abschluss-alias

## Request Summary

Der letzte Buchungsschritt eines Workflows (`workflow.py complete`) ist aus einer
worktree-isolierten Sitzung heraus nicht ausführbar — und praktisch jede Sitzung ist
worktree-isoliert. Ziel: ein zweiter, gleichwertiger Name für denselben Unterbefehl,
der den Fehlalarm nicht auslöst. Teil 2 von Issue #1478.

## Befund (gemessen 2026-08-08, Worktree `pw-forensik`)

```
echo complete
  → BLOCKIERT: "runs a string through complete, which can't be verified
    to stay inside the worktree"
```

**Es ist ausschließlich das Wort, nicht `workflow.py`.** Schon ein nacktes `echo` mit
diesem Argument wird abgewiesen. `complete` ist ein bash-Builtin (programmierbare
Vervollständigung, nimmt ein Kommando als Argument); der Worktree-Wächter des
Claude-Code-Harness liest es als eval-artiges Konstrukt und hält den Rest der Zeile für
ein durchgereichtes, unprüfbares Kommando.

Das erklärt lückenlos die frühere Beobachtung, dass **alle anderen Unterbefehle** über
denselben absoluten Pfad problemlos laufen: `start`, `switch`, `status`, `phase`,
`set-field`, `add-artifact`, `write-log`. In dieser Sitzung erneut bestätigt — `start`
lief, `complete` nicht.

Gegenprobe für Kandidatennamen: `echo finish`, `echo close`, `echo wrapup` laufen alle
durch. `done` scheidet aus (Shell-Keyword in `for`/`while`-Schleifen).

## Zuständigkeit — Korrektur der bisherigen Lagebeurteilung

Im Issue-Kommentar vom 2026-08-08 12:29 steht „in diesem Repo ist er nicht behebbar".
Das ist richtig für `gregor_zwanzig` und für den *Wächter* — aber der **Name des
Unterbefehls** gehört uns: er steht in `henemm/agent-os-openspec`, einem eigenen Repo
des PO. Der Fehlalarm ist damit abräumbar, ohne den Wächter anzufassen.

**Präzedenz im selben Repo:** CHANGELOG 3.10.2 (Issue #87) behandelt exakt dieselbe
Konstellation — „Root Cause liegt im Claude-Code-Harness und ist nicht im Framework
korrigierbar. Mitigation innerhalb des Frameworks: …". Das ist das etablierte Muster.

## Related Files

| Datei | Relevanz |
|---|---|
| `agent-os-openspec/core/hooks/workflow.py:1172-1191` | `COMMANDS`-Dict — hier entsteht der Alias (1 Zeile) |
| `agent-os-openspec/core/commands/80-workflow.md:96` | Aufrufzeile |
| `agent-os-openspec/core/commands/00-bug.md:111` | Aufrufzeile |
| `agent-os-openspec/core/commands/99-reset.md:21` | Aufrufzeile |
| `agent-os-openspec/setup.py:566, 602` | erzeugt die Aufrufzeile in **neu generierten** Projekt-CLAUDE.md |
| `agent-os-openspec/.claude-plugin/plugin.json` | Version (aktuell 3.10.2) — Release-Konvention |
| `agent-os-openspec/CHANGELOG.md` | Pflicht-Eintrag je Release |
| `gregor_zwanzig/.claude/commands/70-deploy.md:91` | Aufrufzeile Schritt 5 — der real blockierte Pfad |
| `gregor_zwanzig/CLAUDE.md:41` | Tabellenzeile „Execution-Log vor `complete`" |
| `gregor_zwanzig/docs/project/agent-os-improvement-bundle.md:200` | nur Beschreibung, kein Aufruf (Archiv) |

Reine Doku im Plugin-Repo, nachzuziehen: `README.md`, `CLAUDE.md`,
`docs/WORKFLOW_GUIDE.md`, `docs/specs/bug-fix-fast-track.md`.

## Existing Patterns

- **Unterbefehl mit Tests:** `tests/test_workflow_abandon_82.py` ist das Vorbild —
  hermetischer Subprozess-Test (`CLAUDE_PROJECT_DIR=tmp_path`, `cwd=tmp_path`), ruft
  `workflow.py` mit Argumentliste auf. Das Wort im Python-Quelltext ist unkritisch;
  nur Bash-Zeilen lösen den Wächter aus.
- **Harness-Fehler mildern statt beheben:** CHANGELOG 3.10.2 / Issue #87.
- **Release:** Version-Bump in `plugin.json` + CHANGELOG-Eintrag, SemVer. Ein neuer
  Unterbefehlsname ist additiv → MINOR (3.11.0).

## Dependencies

- **Upstream:** `cmd_complete` bleibt unverändert; der Alias zeigt auf dieselbe Funktion.
- **Downstream:** Jede Claude-Instanz auf diesem Server (`infra`, `n8n`, `website`,
  `gregor`, `nightjet`, `security`) nutzt dasselbe Plugin. Deshalb ist
  **Rückwärtskompatibilität Pflicht**: der alte Name muss gültig bleiben, sonst brechen
  laufende Sitzungen und fremde Projekt-Dokus.

## Risks & Considerations

1. **Wirkort ≠ Quellort.** Das aktive Plugin wird über
   `~/.claude/plugins/installed_plugins.json` auf
   `~/.claude/plugins/cache/henemm-private/agent-os-openspec/3.10.2` aufgelöst — eine
   **echte Kopie**, kein Symlink (inhaltlich derzeit identisch mit dem Repo, nur `.pyc`
   weichen ab). Der Marketplace `henemm-private` ist vom Typ `directory` mit
   `installLocation = /home/hem/agent-os-openspec`, weshalb Skills aus dem Repo geladen
   werden. Welcher Pfad im Ernstfall gewinnt, ist **nicht abgeleitet, sondern zu
   messen** — sonst ändern wir eine Datei, die niemand ausführt.
2. **Gemeinsam genutzter Checkout.** `/home/hem/agent-os-openspec` steht auf `main` und
   wird von allen Instanzen live gelesen. Dort einen Branch auszuchecken verändert das
   Verhalten **jeder laufenden Sitzung**. Arbeit gehört in einen isolierten Klon; im
   gemeinsamen Checkout liegen zudem fremde uncommittete Dateien
   (`.claude/pending_validation_*.json`), die unangetastet bleiben.
3. **Der Beweis muss aus einer worktree-isolierten Sitzung kommen.** Ein grüner
   Unit-Test im Plugin zeigt nur, dass der Alias denselben State schreibt — er zeigt
   **nicht**, dass der Wächter die neue Aufrufzeile durchlässt. Das ist genau der
   Prüfort-≠-Wirkort-Fehler, der in diesem Projekt mehrfach zu falschem Grün geführt hat.
   Abnahmekriterium ist der reale Aufruf, nicht die Testsuite.
4. **Keine Gate-Aufweichung.** Der Wächter soll verhindern, dass eine isolierte Sitzung
   außerhalb ihres Worktrees schreibt. `workflow.py finish` ist für ihn genauso prüfbar
   wie das erlaubte `workflow.py status` — es gibt kein Schutzziel, das der neue Name
   aushebelt. Abzugrenzen von der verbotenen Alternative: Aufrufformen durchprobieren,
   bis eine durchrutscht.
5. **Zwei Repos, zwei PRs.** Plugin-Fix und Projekt-Doku hängen zusammen, laufen aber
   über getrennte Liefer-Wege.
6. **Teil 1 von #1478** (RED-Artefakt wird im Hauptrepo statt im Worktree gesucht) ist
   nicht Gegenstand dieses Workflows und bleibt offen.

## Existing Specs

Keine Spec im Projekt betroffen. Im Plugin-Repo ist `docs/specs/bug-fix-fast-track.md`
nur als Doku-Fundstelle berührt.

## Analysis

### Type
Bug (Harness-Fehlalarm) mit additivem Fix im eigenen Framework-Repo — kein Feature.

### Affected Files (with changes)

| File | Change Type | Description |
|---|---|---|
| `agent-os-openspec/core/hooks/workflow.py` | MODIFY | `"finish": cmd_complete` zusätzlich in `COMMANDS`-Dict (~1 Zeile) |
| `agent-os-openspec/tests/test_workflow_finish_alias.py` | CREATE | Subprozess-Test nach Vorbild `test_workflow_abandon_82.py`: `finish` schreibt identischen End-State wie `complete`; Altname bleibt funktionsfähig |
| `agent-os-openspec/core/commands/80-workflow.md` | MODIFY | Aufrufzeile auf `finish` |
| `agent-os-openspec/core/commands/00-bug.md` | MODIFY | Aufrufzeile auf `finish` |
| `agent-os-openspec/core/commands/99-reset.md` | MODIFY | Aufrufzeile auf `finish` |
| `agent-os-openspec/setup.py` | MODIFY | zwei Stellen (Tabelle Zeile 566, generierte Aufrufzeile 602) — wirkt in künftig neu generierte Projekt-CLAUDE.md |
| `agent-os-openspec/README.md`, `CLAUDE.md`, `docs/WORKFLOW_GUIDE.md`, `docs/specs/bug-fix-fast-track.md` | MODIFY | Doku-Erwähnungen von `workflow.py complete` |
| `agent-os-openspec/.claude-plugin/plugin.json` | MODIFY | Version 3.10.2 → 3.11.0 (additiv, SemVer MINOR) |
| `agent-os-openspec/CHANGELOG.md` | MODIFY | neuer Eintrag, Muster CHANGELOG 3.10.2 (#87) |
| `gregor_zwanzig/.claude/commands/70-deploy.md:91` | MODIFY | `workflow.py complete` → `workflow.py finish` |
| `gregor_zwanzig/CLAUDE.md:41` | MODIFY | Tabellenzeile auf `finish` |

`gregor_zwanzig/docs/project/agent-os-improvement-bundle.md:200` bleibt unverändert
(Archiv-Doku, beschreibt nur das historische Verhalten).

### Scope Assessment
- Dateien: ~13 (1 Code, 1 Test, 11 Doku/Aufrufzeilen in 2 Repos)
- Geschätztes LoC: +~40/-~10 (überwiegend Test + Dict-Eintrag; Doku zählt laut Projekt-Konvention nicht gegen das LoC-Limit)
- Risk Level: **LOW** — additiv, alter Name bleibt gültig, keine bestehende Funktion wird verändert

### Technical Approach
1. `COMMANDS["finish"] = cmd_complete` in `workflow.py` — reiner Alias, keine Logikänderung.
2. Test nach Vorbild `test_workflow_abandon_82.py`: hermetischer Subprozess-Aufruf mit
   `finish`, Vergleich des resultierenden State-JSON gegen einen Referenzlauf mit
   `complete`.
3. **Abnahme zusätzlich zum Unit-Test:** realer Aufruf `echo finish` und
   `python3 .../workflow.py finish` aus dieser worktree-isolierten Sitzung heraus —
   das ist der eigentliche Beweis, der Unit-Test allein reicht nicht (Risiko 3 im
   Context-Dokument).
4. Alle Aufrufstellen in Skills/Doku auf `finish` umstellen; `complete` nirgends
   entfernen.
5. Release: Version-Bump + CHANGELOG-Eintrag im Plugin-Repo, danach PR.
6. Im Projekt-Repo (`gregor_zwanzig`) zweiter, kleiner PR für die zwei Doku-Stellen —
   erst nachdem der Plugin-PR gemerged UND der Cache-Sync (automatisch, s.o.) bestätigt ist.

### Dependencies
- Upstream: keine — `cmd_complete` unverändert.
- Downstream: alle sechs Claude-Instanzen des Servers nutzen dasselbe Plugin
  (`infra`, `n8n`, `website`, `gregor`, `nightjet`, `security`) — Rückwärtskompatibilität
  ist deshalb Pflicht, nicht optional.

### Open Questions
Keine blockierenden. Einzig zu beobachten: ob der automatische Cache-Sync (Marketplace
`directory`-Quelle) den neuen Namen ohne manuellen Eingriff in
`~/.claude/plugins/cache/henemm-private/agent-os-openspec/3.10.2` verfügbar macht —
wird in der Implementierungs-/Adversary-Phase empirisch geprüft (siehe Technical Approach
Punkt 3), nicht vorab angenommen.
