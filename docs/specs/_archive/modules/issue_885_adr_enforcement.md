---
entity_id: issue_885_adr_enforcement
type: module
created: 2026-06-25
updated: 2026-06-25
status: draft
version: "1.0"
tags: [tooling, gate, adr, workflow]
---

# ADR-Enforcement: Commit-Gate + Spec-Pflichtfeld

## Approval

- [ ] Approved

## Purpose

Die ADR-Konvention (`docs/adr/`) wird mechanisch erzwungen statt nur dokumentiert. Zwei Gates
sorgen dafür, dass entscheidungs-tragende Änderungen nicht ohne ein Architecture Decision Record (oder
eine bewusste Verneinung) in den Code gelangen — analog zur bestehenden Gate-Kultur des Projekts
(`renderer_mail_gate.py`, `bash_gate.py`).

## Source

- **File:** `.claude/hooks/adr_guard.py` (neu) — reine, testbare Prüflogik
- **File:** `.claude/hooks/bash_gate.py` — Integration als Commit-Gate-Schritt 5d (`main()`, nach Zeile 262)
- **File:** `.claude/hooks/workflow.py` — Spec-Freigabe-Check in `_validate_transition` (Zeile 363–367)
- **File:** `docs/specs/_template.md` — neue Sektion `## Architektur-Entscheidung (ADR)`
- **File:** `.claude/config.yaml` (bzw. vom `config_loader` gelesene Config) — Schlüssel `adr_guard`
- **Identifier:** `adr_guard.check(staged_files, commit_message, config) -> str | None`

> Schicht: Reines Workflow-/Tooling-Hook-Werk unter `.claude/hooks/`. Kein `src/`-, Go- oder
> SvelteKit-Code betroffen. Daher kein Staging-/Prod-Deploy-Pfad (docs/tooling-only).

## Estimated Scope

- **LoC:** ~120 (adr_guard.py ~70, bash_gate-Integration ~15, workflow.py-Check ~20, Template ~8)
- **Files:** 4 Code/Config + 1 Template + Tests
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `bash_gate.py` Schritt 5 | hook | Commit-Gate-Einhängepunkt (`git commit` erkannt, staged files gelesen) |
| `config_loader.load_config` | hook util | Liefert `adr_guard`-Konfiguration (Entscheidungsflächen-Patterns) |
| `workflow.py` `_validate_transition` | hook | Phasen-Gating der Spec-Freigabe |
| `docs/adr/` | docs | Ziel-Ablage der ADRs (Existenz/Struktur aus Vorarbeit) |

## Implementation Details

```
# Ebene 1 — Commit-Gate (adr_guard.py + bash_gate.py Schritt 5d)
DECISION_SURFACE_PATTERNS (config-overridebar via config.yaml → adr_guard.decision_surface_patterns):
  - ^src/outputs/            (Kanäle)
  - ^src/output/renderers/   (Render-/Ausgabe-Entscheidungen)
  - ^docs/reference/decision_matrix\.md$   (Quellenwahl)
  - ^src/providers/          (Provider-Entscheidungen)
  - selectable / MetricDefinition  (Metrik-Sichtbarkeit — Pfad src/.*metric.*)
  - ^\.claude/hooks/.*_gate\.py$   (Gate-Logik selbst)

def check(staged_files, commit_message, config) -> str | None:
    surfaces = [f for f in staged_files if matches_decision_surface(f, config)]
    if not surfaces:
        return None                      # No-Op → AC-4
    if "[no-adr]" in commit_message:
        return None                      # bewusste Verneinung → AC-3
    if any(f.startswith("docs/adr/") and f.endswith(".md") for f in staged_files):
        return None                      # ADR mitgestaged → AC-2
    return ("BLOCKED: Entscheidungs-tragende Datei(en) ohne ADR: <surfaces>.\n"
            "Lege ein docs/adr/NNNN-*.md an ODER schreibe [no-adr] in die Commit-Message.")

# bash_gate.py Schritt 5d (nach 5a, innerhalb `if "git commit" in command`):
#   msg = _extract_commit_message(command)   # aus -m "..." / -F
#   err = adr_guard.check(staged_list, msg, config)
#   if err: block(err)

# Ebene 2 — Spec-Freigabe (workflow.py _validate_transition, bei tgt_idx >= phase4_approved):
#   spec_text = Path(data["spec_file"]).read_text()
#   prüfe Sektion "## Architektur-Entscheidung (ADR)" existiert UND enthält
#   entweder "ADR-<n>" ODER das Wort "keine"/"none". Sonst:
#   return "Spec ohne ausgefülltes ADR-Feld — '## Architektur-Entscheidung (ADR)' (ADR-Nr. oder 'keine')"
```

## Expected Behavior

- **Input:** Ein `git commit`-Kommando (Commit-Gate) bzw. eine Phasen-Transition nach `phase4_approved` (Spec-Gate).
- **Output:** Exit 0 (erlaubt) oder Exit 2 / Fehlermeldung (blockiert).
- **Side effects:** Keine — beide Gates sind rein lesend (git diff --cached, Spec-Datei lesen).

## Acceptance Criteria

- **AC-1:** Given ein echtes Git-Repo mit installiertem `adr_guard`, in dem eine Änderung an einer
  Entscheidungsfläche (z. B. `src/outputs/telegram.py`) gestaged ist, kein `docs/adr/`-File mitliegt
  und die Commit-Message keinen `[no-adr]`-Marker enthält / When ein `git commit` durch `bash_gate.py`
  geprüft wird / Then wird der Commit mit Exit 2 blockiert und die Meldung nennt die betroffene Datei
  sowie die zwei Auswege (ADR anlegen oder `[no-adr]`).
  - Test: Echtes tmp-Repo, `git add src/outputs/x.py`, Gate via Subprocess → Exit 2 + Meldungstext.

- **AC-2:** Given dieselbe Entscheidungsflächen-Änderung, aber zusätzlich ist ein neues
  `docs/adr/0010-foo.md` mitgestaged / When der Commit durch das Gate läuft / Then wird der Commit
  durchgelassen (Exit 0).
  - Test: tmp-Repo, beide Dateien gestaged, Gate → Exit 0.

- **AC-3:** Given die Entscheidungsflächen-Änderung ohne ADR, aber die Commit-Message enthält den
  Marker `[no-adr]` / When der Commit durch das Gate läuft / Then wird der Commit durchgelassen
  (Exit 0), weil die Entscheidung bewusst verneint wurde.
  - Test: tmp-Repo, `git commit -m "... [no-adr]"`, Gate → Exit 0.

- **AC-4:** Given ein Commit, der ausschließlich Nicht-Entscheidungs-Dateien ändert (z. B.
  `src/services/foo.py`) und kein ADR enthält / When der Commit durch das Gate läuft / Then verhält
  sich das Gate als No-Op und lässt durch (Exit 0).
  - Test: tmp-Repo, nur `src/services/foo.py` gestaged, Gate → Exit 0.

- **AC-5:** Given ein aktiver Workflow mit `spec_file`, dessen Spec-Datei **keine** ausgefüllte
  Sektion `## Architektur-Entscheidung (ADR)` enthält / When eine Transition nach `phase4_approved`
  versucht wird / Then blockt `_validate_transition` mit einer Meldung, die das fehlende ADR-Feld
  benennt; enthält die Spec dagegen `ADR-<n>` oder `keine`, ist die Transition erlaubt.
  - Test: Zwei Spec-Fixtures (leer vs. ausgefüllt) durch `workflow.py phase phase4_approved` → blockt bzw. erlaubt.

## Known Limitations

- Die Entscheidungsflächen-Heuristik (Pfad-Patterns) erzeugt anfangs ggf. Fehlalarme bei rein
  mechanischen Änderungen an diesen Pfaden; Abhilfe ist der bewusste `[no-adr]`-Marker. Patterns sind
  über `config.yaml` nachschärfbar, ohne Code-Änderung.
- Ebene 2 greift nur für Arbeit, die durch den 8-Phasen-Workflow läuft; reine Ad-hoc-Hotfixes deckt
  nur Ebene 1 ab.
- Kein ENV-/globaler Bypass (bewusst, analog `renderer_mail_gate.py`); der einzige Ausweg ist der
  pro-Commit explizite `[no-adr]`-Marker.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine — dieses Vorhaben *implementiert* das ADR-Enforcement selbst und trifft keine
  neue, eigenständige Architekturentscheidung, die ein eigenes Record bräuchte. (Die Felddefinition
  dient zugleich als erstes Beispiel für die neue Template-Sektion.)
- **Rationale:** Tooling-Gate ohne produktfachliche Richtungsentscheidung.

## Changelog

- 2026-06-25: Initial spec created (Issue #885)
