# Context: fix-2125-override-prod-send

## Request Summary
Der Notausgang des Prod-Send-Gates (#1148) — der PO tippt `override` — wirkt nicht: das
Gate bleibt zu. Ziel: eine bewusst gewollte Prod-Versand-Freigabe muss aus jeder Session
(auch Worktree) wirksam und sichtbar sein, und sie darf nur das Prod-Send-Gate öffnen
(Kreuzbindung aus #2227 nicht wieder scharf machen).

## Befund (Stand 2026-11-12, Plugin 4.10.0/4.11.0)

| # | Defekt aus Issue | Stand heute | Beleg |
|---|---|---|---|
| 1 | Pfad-Divergenz Schreiber/Leser | **besteht** | Schreiber `override_token._get_token_file()` → `find_project_root()` (`hook_utils.py:1632`) löst Worktree → Haupt-Repo auf. Leser `prod_send_gate.py:289 _project_root()` nimmt `CLAUDE_PROJECT_DIR` roh bzw. `git rev-parse --show-toplevel` → Worktree. Token liegt real in `/home/hem/gregor_zwanzig/.claude/user_override_token.json` (heute 20:00 aus einer Worktree-Session geschrieben). |
| 2 | Namens-Divergenz | **besteht, schärfer als beschrieben** | Schreiber schlüsselt unter dem vom Plugin aufgelösten Workflow-Namen (`phase_listener.py:505`, `__global__` ohne Workflow). Leser nimmt nur `GZ_ACTIVE_WORKFLOW`/`OPENSPEC_ACTIVE_WORKFLOW` aus der Hook-Umgebung (`prod_send_gate.py:305`); diese Variablen erreichen Hook-Prozesse normalerweise gar nicht (Shell-`export` überlebt keinen Tool-Aufruf) → `_has_valid_override("")` liefert immer False (`:336`). |
| 3 | Schreiber feuert nicht | **heute nicht reproduzierbar** | Token-Datei im Haupt-Repo trägt Eintrag `fix-2227-override-zwei-gates` von heute 20:00; seit #425 meldet `phase_listener` auch einen Schreibfehler sichtbar (`_create_override_token`, `:382-411`). |

Zusätzlich (#2227-Kommentar): Das Plugin-Stichwort `override` ist an den Workflow gebunden,
nicht an eine Sperre. Ein gemeinsamer Token-Eintrag gibt also gleichzeitig LoC-/Plugin-Gates
(`edit_gate`, `bash_gate`, `evidence_gate`, … lesen `has_valid_token`) und den Prod-Versand frei.
Der Fix muss den Prod-Send-Notausgang an das Prod-Send-Gate binden.

Nebenbefund: Plugin schreibt `created` naiv lokal (`datetime.now()`), Leser deutet naiv als UTC.
Server-Zeitzone ist UTC → heute folgenlos, aber fragil.

## Related Files
| File | Relevance |
|------|-----------|
| `.claude/hooks/prod_send_gate.py` | Leser: `_project_root` (:289), `_active_workflow_name` (:305), `_consume_token`, `_has_valid_override` (:330), `_block`-Text (:363) |
| `.claude/settings.json` | Hook-Registrierung PreToolUse Bash (:45); UserPromptSubmit hat heute nur `context_budget_guard.py` (:136) |
| Plugin `core/hooks/phase_listener.py` | Schreiber des allgemeinen Override-Tokens (nicht in diesem Repo, nicht änderbar hier) |
| Plugin `core/hooks/override_token.py` | v2-Format, TTL 1 h, Pfad via `find_project_root` |
| Plugin `core/hooks/hook_utils.py:1632` | `find_project_root` (Worktree → Haupt-Repo) — Vorbild für die Wurzel-Auflösung |
| `tests/tdd/test_issue_1148_prod_send_gate.py` | Bestehende Gate-Tests; Override-Test (:117) baut Token unter Workflow-Namen + setzt Env-Vars — bildet die reale Lage nicht ab |
| `tests/tdd/test_broad_test_run_gate_ignores_override.py` | #2227: Testlauf-Gate hat keinen Override mehr; dort nichts mehr zu tun |
| `docs/specs/modules/gate_1148_prod_send_deny.md` | Spec des Gates, Abschnitt „Override-Mechanik“ (:113), AC-3 (:157) — muss nachgezogen werden |
| `docs/reference/gates_und_ratschen.md:699` | Gate-Tabelle, nennt den Override-Weg |

## Existing Patterns
- Projekt-eigene Hooks in `.claude/hooks/` mit eigenem kleinem Reader statt Plugin-Import (Spec #1148 „kein Import aus dem Plugin“).
- Atomares Schreiben per `tempfile.mkstemp` + `os.rename` (`_consume_token`).
- Gate-Tests laufen als Subprozess mit isoliertem `CLAUDE_PROJECT_DIR` auf `tmp_path`.
- Worktree-Erkennung: `.git` ist Datei → `gitdir:` zeigt auf `<main>/.git/worktrees/<n>` (Plugin `find_main_repo_from_worktree`).

## Dependencies
- Upstream: Claude-Code-Hook-Umgebung (`CLAUDE_PROJECT_DIR`, stdin-JSON), Plugin-Schreiber `phase_listener` (nur falls weiter genutzt).
- Downstream: jede Claude-Session, die bewusst gegen Prod sendet (Abendbriefing-Nachversand, Störungsbehebung).

## Lösungsrichtung (für /20-analyse zu prüfen)
- Eigenes, sperrenspezifisches Freigabe-Stichwort mit eigenem projekt-lokalen UserPromptSubmit-Hook
  und eigener Token-Datei, die nur das Prod-Send-Gate liest. Behebt 1 (eine gemeinsame Wurzel-Funktion
  für Schreiber und Leser im selben Repo), 2 (keine Workflow-Bindung) und die #2227-Kreuzbindung, ohne
  Repo-übergreifende Änderung. Sichtbare Bestätigung bzw. Fehlermeldung beim Tippen (AC-4).
- Allgemeines `override` öffnet das Prod-Send-Gate danach nicht mehr; Block-Text nennt das neue Stichwort.

## Risks & Considerations
- Sicherheitsfläche: Ein zu lockeres Stichwort-Matching könnte einen Versand aus beiläufigem Text freigeben → Phrase muss allein stehen (wie Plugin `OVERRIDE_EXTRA_WORDS = 0`), harness-injizierte Turns ignorieren.
- Token-Datei darf nicht über Symlink/Hardlink umgelenkt werden (Plugin #416/#422-Muster).
- Prod-Versand selbst wird im Test nie ausgelöst; Nachweis ausschließlich über Hook-Subprozesse.
- Spec #1148 und Gate-Doku müssen den neuen Weg beschreiben; Stichwort ist eine PO-sichtbare Festlegung → Teil der Spec-Freigabe.

## Analysis

### Type
Bug (Notausgang eines Sicherheits-Gates wirkungslos) — mit sicherheitsrelevanter Neubindung.

### Ursachen (am Code bestätigt, 2026-11-12)
1. Leser `_project_root()` (`prod_send_gate.py:289`) löst Worktree nicht auf Haupt-Repo auf → liest eine Datei, die nie geschrieben wird.
2. Leser schlüsselt nach `GZ_ACTIVE_WORKFLOW`/`OPENSPEC_ACTIVE_WORKFLOW` (`:305`); diese Variablen fehlen in Hook-Prozessen praktisch immer → `_has_valid_override("")` ist strukturell immer False (`:336`). Das allein macht den Notausgang auch im Haupt-Repo tot.
3. Schreiber-Ausfall vom 30.08. heute nicht reproduzierbar; wird durch eigenen Schreiber gegenstandslos.
4. Kreuzbindung (#2227): Plugin-`override` ist an den Workflow gebunden und öffnet auch LoC-/Plugin-Gates — darf das Prod-Send-Gate nicht mehr öffnen.

### Technical Approach (Empfehlung)
Eigener, projekt-lokaler Freigabe-Weg nur für den Prod-Versand, ohne Plugin-Abhängigkeit:

- **Neuer UserPromptSubmit-Hook** `.claude/hooks/prod_send_release.py`: erkennt eine eigene, allein stehende Freigabe-Phrase (Vorschlag: `prod-versand freigeben`; exakter Vergleich nach Trim/Kleinschreibung, keine Zusatzwörter → beiläufiger Text und harness-injizierte Turns öffnen nichts). Schreibt einen Einmal-Eintrag in eine **eigene** Datei `.claude/prod_send_release.json` im **Haupt-Repo** (Worktree aufgelöst).
- **Bindung an die Sitzung statt an den Workflow:** Schlüssel ist die `session_id`, die Claude Code beiden Hook-Arten (UserPromptSubmit und PreToolUse) im stdin-JSON mitgibt. Die Freigabe wirkt genau in der Sitzung, in der der PO sie getippt hat — parallele Sitzungen können sie nicht verbrauchen, Workflow-Variablen spielen keine Rolle.
- **Eine gemeinsame Wurzel-Funktion** (Worktree → Haupt-Repo über `.git`-Datei/`gitdir:`) in der projekt-lokalen `hook_utils.py`, genutzt von Schreiber UND Leser → Defekt 1 strukturell ausgeschlossen.
- **Gate** `prod_send_gate.py`: `_has_valid_override` liest nur noch die neue Datei unter `session_id`, verbraucht atomar (einmalig), TTL 1 h (wie bisher), Zeitstempel UTC mit Zeitzone. `user_override_token.json` wird nicht mehr gelesen → Plugin-`override` öffnet den Prod-Versand nicht mehr.
- **Sichtbarkeit (AC-4 aus Issue):** Hook bestätigt beim Tippen sichtbar (`systemMessage`) bzw. meldet sichtbar, wenn das Schreiben scheitert. Block-Text des Gates nennt die neue Phrase.
- **Härtung:** kein Schreiben/Lesen über Symlink (`O_NOFOLLOW`/`is_symlink`), Rechte 0600, Datei in `.gitignore` (heute ist auch `user_override_token.json` nicht ignoriert).
- **Registrierung** in `.claude/settings.json` unter UserPromptSubmit (neben `context_budget_guard.py`).

Verworfen: (a) nur Leser reparieren (Wurzel + Workflow-Name aus Plugin-State) — Kreuzbindung #2227 bliebe scharf, Kopplung an Plugin-Interna; (b) Plugin ändern — fremdes Repo, betrifft alle Projekte, löst Sperrenbindung nicht.

### Affected Files
| File | Change Type | Description |
|------|-------------|-------------|
| `.claude/hooks/prod_send_release.py` | CREATE | UserPromptSubmit: Phrase erkennen, Eintrag je session_id schreiben, sichtbare Rückmeldung |
| `.claude/hooks/hook_utils.py` | MODIFY | gemeinsame Haupt-Repo-Wurzel + Release-Dateipfad |
| `.claude/hooks/prod_send_gate.py` | MODIFY | Override-Leser auf neue Datei/session_id, alter Workflow-Reader entfällt, Block-Text |
| `.claude/settings.json` | MODIFY | Hook-Registrierung UserPromptSubmit |
| `.gitignore` | MODIFY | Release-Datei ignorieren |
| `tests/tdd/test_issue_2125_prod_send_release.py` | CREATE | Subprozess-Tests: Worktree-Lage, fremde Sitzung, Plugin-Token öffnet nicht, Einmaligkeit, Ablauf, beiläufiger Text, Symlink |
| `tests/tdd/test_issue_1148_prod_send_gate.py` | MODIFY | Override-Test (:117) auf neuen Weg |
| `docs/specs/modules/gate_1148_prod_send_deny.md` | MODIFY | Override-Mechanik, AC-3, Side effects |
| `docs/reference/gates_und_ratschen.md` | MODIFY | Gate-Tabelle (:699) |

### Scope Assessment
- Dateien: 9 (3 Code, 2 Tests, 4 Konfig/Doku)
- Geschätzte LoC: +220 / −50
- Risiko: MITTEL — Sicherheits-Gate; Fehler Richtung „zu offen“ wäre schwerwiegend, Richtung „zu“ ist der heutige Zustand. Keine Auswirkung auf Nutzerfunktionen.

### Dependencies
- Hook-Eingabe: `session_id` + `prompt` (UserPromptSubmit), `session_id` (PreToolUse).
- Kein Plugin-Import (Regel aus Spec #1148 bleibt).

### Open Questions
- [ ] Wortlaut der Freigabe-Phrase ist PO-sichtbar → mit der Spec freigeben (Vorschlag `prod-versand freigeben`).
- [ ] Spec hält fest: Freigabe gilt für genau einen Versand-Aufruf, 1 h gültig, nur in der tippenden Sitzung.
