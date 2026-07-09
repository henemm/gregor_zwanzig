# Context: fix-1165-adr-index-cleanup

## Request Summary
Issue #1165: `docs/adr/README.md` (Index aller ADRs) ist inkonsistent mit `docs/adr/`. ADR-0018 fehlt im Index. Die Nummer 0014 ist doppelt vergeben (zwei verschiedene Entscheidungen) — aktuell im Index nur mit einer erklärenden Notiz "notdürftig" abgefangen, nicht aufgelöst. Ziel: Index korrigieren, Nummern-Kollision durch Umnummerierung sauber auflösen, alle Referenzen anpassen.

## Related Files

| File | Relevance |
|------|-----------|
| `docs/adr/README.md` | Der Index selbst — Zeile 78/79 listet 0014 doppelt mit Kollisions-Hinweis, kein Eintrag für 0018 |
| `docs/adr/0014-nullgradgrenze-eine-alert-metrik.md` | Chronologisch die echte 0014 (erstellt 2026-07-03 06:11 UTC, Commit b65f22a0) — wird umnummeriert |
| `docs/adr/0014-telegram-multi-bubble-format.md` | Kollidierende zweite 0014 (erstellt 2026-07-03 10:53 UTC, Commit 6b27798f) — behält 0014, da mehr Referenzen darauf zeigen |
| `docs/adr/0018-provider-fallback-ohne-kaschieren.md` | Existiert bereits als Datei, fehlt aber im Index |
| `docs/specs/modules/fix_alert_bundle_958ff.md` (Zeile 494) | Referenziert "Vorschlag ADR-0014" im Kontext Nullgradgrenze — muss auf neue Nummer angepasst werden |
| `docs/features/architecture.md` (Zeile 178) | Referenziert "Issue #959/ADR-0014" im Kontext Nullgradgrenze/freezing_level — anpassen |
| `docs/features/issue-816-alert-deviation-core.md` (Zeile 95) | Referenziert "Issue #959/ADR-0014" im Kontext Nullgradgrenze — anpassen |
| `docs/reference/api_contract.md` (Zeilen 2223, 2371, 2480) | Referenziert ADR-0014 im Kontext Telegram Multi-Bubble UND SNOW_LINE-Enum (Nullgradgrenze) — **gemischt**, beide Fälle vorhanden, sorgfältig einzeln prüfen |
| `docs/specs/modules/feat_1001_telegram_redesign.md` (Zeile 324, 331) | Referenziert ADR-0014 im Kontext Telegram Multi-Bubble — bleibt unverändert (0014 bleibt Telegram) |
| `docs/analysis/architektur-drift-2026-07-05.md` (Zeilen 59, 295) | Erwähnt ADR-0014 als Telegram-Format sowie eine ADR-Nummernspanne "0001…0014" — prüfen ob Anpassung nötig |

## Existing Patterns
- ADR-Dateinamen-Konvention: `NNNN-kurzer-titel.md`, vierstellig, fortlaufend (siehe `docs/adr/_template.md`)
- Frühere Index-Nachträge liefen bereits informell (z.B. Commit `10e33490`: "Index: 0016 nachgetragen [no-adr]") — kein etabliertes Tooling, nur manuelle README-Pflege
- `.claude/hooks/adr_guard.py` prüft nur Pfad-Muster beim Commit, keine inhaltliche ADR-Prüfung — diese Änderung berührt den Guard nicht (reine Doku, keine der `DEFAULT_DECISION_SURFACE_PATTERNS` matched `docs/adr/*.md` selbst als Scope-Trigger, aber `docs/adr/*.md` mitzustagen ist ohnehin der Standard-Ausweg)

## Dependencies
- Upstream: keine — reine Markdown-Pflege
- Downstream: keine Code-Abhängigkeiten. Nur Dokumentations-Querverweise (oben gelistet)

## Existing Specs
- Keine spezifische Spec für ADR-Index-Pflege vorhanden. `docs/specs/modules/issue_885_adr_enforcement.md` beschreibt das ADR-Enforcement-Konzept, aber nicht die Index-Pflege selbst.

## Analysis

### Type
Feature (Doku-Pflege, kein Bug)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `docs/adr/0014-nullgradgrenze-eine-alert-metrik.md` | RENAME → `docs/adr/0019-nullgradgrenze-eine-alert-metrik.md` (git mv) | Kollidierende Nummer auflösen; Titelzeile `# ADR-0014: ...` → `# ADR-0019: ...` anpassen |
| `docs/specs/modules/fix_alert_bundle_958ff.md` | MODIFY (Z.494) | Referenz "ADR-0014" → "ADR-0019" |
| `docs/features/architecture.md` | MODIFY (Z.178) | Referenz "ADR-0014" → "ADR-0019" |
| `docs/features/issue-816-alert-deviation-core.md` | MODIFY (Z.95) | Referenz "ADR-0014" → "ADR-0019" |
| `docs/reference/api_contract.md` | MODIFY (nur Z.2371) | Nackte Kurzform "ADR-0014" (Nullgradgrenze-Kontext) → "ADR-0019". Z.2223/2480 referenzieren bereits den vollen Dateinamen `0014-telegram-multi-bubble-format.md` (Telegram) — **unverändert lassen** |
| `docs/adr/README.md` | MODIFY (Z.78/79 + neue Zeilen) | 0014 nur noch Telegram; neue Zeile 0018 (Provider-Fallback, fehlte komplett); neue Zeile 0019 (Nullgradgrenze) |

Bestätigt durch Explore-Verifikation: keine weiteren 0014-Fundstellen im Repo, keine Code-Referenzen (nur Dokumentation). `docs/analysis/architektur-drift-2026-07-05.md` referenziert 0014 nur im Telegram-Kontext (Z.59) bzw. als beschreibende Nummernspanne "0001…0014" (Z.295) — beides bleibt unverändert, da 0014 ja weiterhin Telegram bleibt.

### Scope Assessment
- Files: 6
- Estimated LoC: ~10 Zeilenänderungen (1 Rename + Titelzeile, 4 Cross-Referenzen, README mit 3 Zeilenänderungen/-ergänzungen)
- Risk Level: LOW — reine Dokumentation, keine Code-Referenzen auf ADR-Nummern gefunden (bestätigt durch Plan-Agent-Suche über `src/`, `internal/`, `frontend/src/`)

### Technical Approach
Umnummerierung (nicht Sub-Nummer wie "0014a") — Konvention verlangt strikt `NNNN-titel.md`. Reihenfolge: (1) `git mv` + Titelzeile in der Datei selbst anpassen, (2) die 4 Cross-Referenzen anpassen, (3) README.md zuletzt (muss den Endzustand widerspiegeln). Commit mit `[no-adr]` — reine Index-Pflege, keine neue Architekturentscheidung.

### Dependencies
Keine. Reine Markdown-Änderungen, kein Code betroffen.

### Open Questions
Keine offenen Fragen — Scope ist vollständig verifiziert.

## Risks & Considerations
- **Vermischte Referenzen in `api_contract.md`:** Enthält sowohl Telegram- als auch Nullgradgrenze-Bezüge unter "ADR-0014" — jede der 3 Fundstellen einzeln prüfen, welche gemeint ist, bevor ersetzt wird.
- **Neue Nummer für Nullgradgrenze:** 0018 ist bereits vergeben → nächste freie Nummer ist 0019.
- **Kein automatisiertes Tooling** für Index-Konsistenz vorhanden — Risiko, dass diese Inkonsistenz wieder auftritt. Das strukturelle Gegenstück (Plugin-seitige Reflexionsprüfung) ist bereits als separates Issue `henemm/agent-os-openspec#63` gemeldet, hier nicht im Scope.
- Reine Dokumentationsänderung → laut CLAUDE.md-Konvention entfällt Staging-Validierung (Schritt 3) und Prod-Deploy-Schritt 4 kann direkt erfolgen, solange kein Code in `src/`/`api/`/`internal/`/`frontend/`/`cmd/` betroffen ist.
