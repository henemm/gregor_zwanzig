# Context: epic-191-ac-format-pflicht

## Request Summary

Specs müssen `## Acceptance Criteria` mit `AC-N` Given/When/Then-Format enthalten. Validierung in zwei Stufen: `spec-validator`-Agent meldet INVALID, `workflow_gate.py` blockiert phase6-Edits. Stichtag-basiert: nur **neue** Specs (`created >= Stichtag`) sind betroffen, 164 Bestands-Specs bleiben grandfathered.

## Realitäts-Check

| Metrik | Wert |
|--------|------|
| Specs total | 167 |
| Mit `## Acceptance Criteria` Section | 40 |
| Mit `AC-N` Pattern | **3** (epic_191_state_migration, epic_191_logbuch_audit, trip_edit_view) |

Heißt: 164 Specs müssen **NICHT** migriert werden — Stichtagsregel ist Pflicht, sonst bricht jeder Code-Edit auf alten Specs.

## Related Files

| File | Relevanz |
|------|----------|
| `.claude/hooks/workflow_gate.py` | Hauptort der Hard-Enforcement (phase6_implement Edit-Block) |
| `.claude/hooks/spec_enforcement.py` | Bestehender Spec-Existenz-/TODO-Check — eventuell erweitern |
| `.claude/agents/spec-validator.md` | Soft-Check vor User-Approval (Phase 3) |
| `.claude/agents/spec-writer.md` | Muss neue Specs automatisch mit AC-N-Template ausstatten |
| `docs/specs/_template.md` | Spec-Template — soll AC-N-Beispiel enthalten |
| `openspec.yaml` | Konfigurations-Stichtag `ac_format_required_since: "2026-05-11"` |
| `.claude/hooks/config_loader.py` | Liest openspec.yaml — Helper für Stichtag-Datum nötig |

## Existing Patterns

### Soft-Check via spec-validator
`spec-validator` prüft schon: Frontmatter, Pflichtsektionen, `[TODO]`-Placeholder, Approval-Checkbox. **Erweitern um AC-N-Check** mit Stichtagslogik.

### Hard-Block via workflow_gate
`workflow_gate.py` blockt schon phase6-Edits auf "protected paths" wenn der Workflow nicht in `spec_approved/implemented/validated/phase4_approved` ist. **Erweitern um AC-N-Check der referenzierten spec_file**.

### Spec-Frontmatter
Alle neuen Specs haben `created: YYYY-MM-DD` im Frontmatter. Das ist unser Stichtag-Marker.

## Dependencies

- **Upstream:** `re` (regex), `pathlib.Path`, `yaml` (PyYAML für Frontmatter-Parsing), `config_loader.load_config()`
- **Downstream:** Alle 6 Slash-Commands (Phase 3 erzeugt Spec), 9 Hooks die State lesen

## Existing Specs

- `docs/specs/modules/epic_191_state_migration.md` — Vorbild AC-N Format (9 Kriterien)
- `docs/specs/modules/epic_191_logbuch_audit.md` — Vorbild AC-N Format (9 Kriterien)
- `docs/specs/_template.md` — soll mit Beispiel-AC-N erweitert werden

## Risks & Considerations

| Risiko | Mitigation |
|--------|-----------|
| **Hart-Block bricht alle Edits auf alte Specs** | Stichtags-Regel: `created < ac_format_required_since` → Legacy, kein Block |
| **`created` fehlt im Frontmatter** | Default-Verhalten: kein Block, aber Warnung. Konservativ: kein Frontmatter = Legacy. |
| **Spec wird verschoben oder Frontmatter editiert** | `created`-Feld sollte stabil sein. Wenn jemand es ändert, ist das bewusste Migration → AC-N erforderlich. |
| **Stichtag muss konfigurierbar sein** | `openspec.yaml` → `ac_format_required_since: "2026-05-11"` |
| **AC-N-Regex matcht zu strikt** | Regex sollte tolerant sein: `AC-\d+` reicht, Given/When/Then-Match optional als "WARNING" statt "BLOCK" |
| **Edge-Case: leere `## Acceptance Criteria` Section** | Counter-Check: mindestens 1 `AC-N` Eintrag mit min. 30 Zeichen Inhalt |
| **Bestehende `## Acceptance Criteria` mit alter Form** | Stichtagslogik schützt sie, aber sie bleiben "schlechter Stil" — Akzeptiert. |

## Out of Scope

- Migration der 37 bestehenden `## Acceptance Criteria`-Specs auf AC-N (separates Issue bei Bedarf)
- Auto-Refactoring von Specs
- Dashboards/Reports über AC-Format-Adoption-Rate
