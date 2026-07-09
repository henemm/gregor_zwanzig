---
entity_id: issue_1165_adr_index_cleanup
type: module
created: 2026-07-09
updated: 2026-07-09
status: draft
version: "1.0"
tags: [docs, adr, index-cleanup]
---

# Issue #1165: ADR-Index-Cleanup

## Approval

- [ ] Approved

## Purpose

`docs/adr/README.md` (Index aller ADRs) ist inkonsistent mit den tatsächlich vorhandenen Dateien in `docs/adr/`: ADR-0018 fehlt komplett im Index, und es gibt **zwei** Nummern-Kollisionen (0013 und 0014 sind je doppelt vergeben). Diese Spec beschreibt die Auflösung beider Kollisionen durch Umnummerierung sowie die Anpassung aller betroffenen Cross-Referenzen und des Index selbst, sodass der Index wieder eine echte 1:1-Abbildung der ADR-Dateien ist.

## Source

- **File:** `docs/adr/README.md` (primäre Quelle — kein einzelnes Code-Modul betroffen)
- **Identifier:** ADR-Index-Tabelle (`## Index`)

> **Schicht-Hinweis:** Reine Dokumentationsänderung. Eine Fundstelle liegt in Python-Domain-Code (`src/output/renderers/alert/model.py:66`, Kommentar) — dort ändert sich **nichts**, da ADR-0013 (Alert-Threshold) seine Nummer behält.

## Estimated Scope

- **LoC:** ~16 Zeilenänderungen
- **Files:** 8
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/adr/_template.md` | Konvention | Dateinamens-Schema `NNNN-kurzer-titel.md`, vierstellig fortlaufend |
| `.claude/hooks/adr_guard.py` | Guard | Prüft nur Pfad-Muster beim Commit, keine inhaltliche Prüfung — von dieser Änderung nicht berührt |

## Implementation Details

```
Zwei unabhängige Nummern-Kollisionen werden durch Umnummerierung aufgelöst
(nicht durch Sub-Nummern wie "0014a" — Konvention verlangt strikt NNNN).
Kriterium für "wer behält die Nummer": die Datei mit den meisten
Referenzen bleibt, die andere wird auf die nächste freie Nummer nach der
höchsten bestehenden ADR-Nummer (0018) umnummeriert.

Kollision 1 — 0013:
  - docs/adr/0013-alert-threshold-ist-delta-sensitivitaet.md  → bleibt 0013
    (4 Referenzen, davon 1 Code-Kommentar in
    src/output/renderers/alert/model.py:66 — bleibt unverändert, da Nummer
    gleich bleibt)
  - docs/adr/0013-node-test-frontend-unit-runner.md            → wird 0020
    (2 Referenzen: docs/adr/README.md:77,
    docs/specs/modules/fix_972_974_975_tooling.md:250)

Kollision 2 — 0014:
  - docs/adr/0014-telegram-multi-bubble-format.md              → bleibt 0014
    (mehr Referenzen, u.a. docs/reference/api_contract.md:2223/2480,
    docs/specs/modules/feat_1001_telegram_redesign.md:324/331)
  - docs/adr/0014-nullgradgrenze-eine-alert-metrik.md          → wird 0019
    (Referenzen: docs/specs/modules/fix_alert_bundle_958ff.md:494,
    docs/features/architecture.md:178,
    docs/features/issue-816-alert-deviation-core.md:95,
    docs/reference/api_contract.md:2371)

Reihenfolge der Änderungen (pro Kollision):
  1. `git mv` der umzunummerierenden Datei
  2. Titelzeile in der umbenannten Datei selbst anpassen
     ("# ADR-0013: ..." → "# ADR-0020: ...", "# ADR-0014: ..." → "# ADR-0019: ...")
  3. Alle Cross-Referenzen in den betroffenen Dateien anpassen
  4. docs/adr/README.md zuletzt aktualisieren (muss Endzustand widerspiegeln)

Betroffene Dateien im Detail:

| Datei | Änderung |
|-------|----------|
| docs/adr/0013-node-test-frontend-unit-runner.md | RENAME → docs/adr/0020-node-test-frontend-unit-runner.md (git mv) + Titelzeile |
| docs/specs/modules/fix_972_974_975_tooling.md (Z.250) | Referenz auf Dateinamen "0013-node-test-frontend-unit-runner.md" → "0020-node-test-frontend-unit-runner.md" |
| docs/adr/0014-nullgradgrenze-eine-alert-metrik.md | RENAME → docs/adr/0019-nullgradgrenze-eine-alert-metrik.md (git mv) + Titelzeile |
| docs/specs/modules/fix_alert_bundle_958ff.md (Z.494) | Referenz "ADR-0014" → "ADR-0019" |
| docs/features/architecture.md (Z.178) | Referenz "ADR-0014" → "ADR-0019" |
| docs/features/issue-816-alert-deviation-core.md (Z.95) | Referenz "ADR-0014" → "ADR-0019" |
| docs/reference/api_contract.md (nur Z.2371) | Nackte Kurzform "ADR-0014" (Nullgradgrenze-/SNOW_LINE-Kontext) → "ADR-0019". Z.2223 und Z.2480 referenzieren bereits den vollen Dateinamen "0014-telegram-multi-bubble-format.md" (Telegram) — unverändert lassen |
| docs/adr/README.md (Z.77-79 + neue Zeilen) | Z.77: 0013 nur noch Alert-Threshold-Titel; Z.78: 0014 nur noch Telegram (Zeile mit Nullgradgrenze/Kollisions-Hinweis entfernen); neue Zeile für 0018 (Provider-Fallback, fehlte komplett); neue Zeile für 0019 (Nullgradgrenze); neue Zeile für 0020 (node:test) |

Unverändert (bewusst NICHT anfassen):
  - src/output/renderers/alert/model.py:66 — referenziert ADR-0013 (Alert-Threshold), Nummer bleibt gleich
  - docs/specs/modules/feat_1001_telegram_redesign.md:324/331 — referenziert ADR-0014 (Telegram), Nummer bleibt gleich
  - docs/reference/api_contract.md:2223/2480 — referenzieren vollen Dateinamen "0014-telegram-multi-bubble-format.md" (Telegram)
  - docs/analysis/architektur-drift-2026-07-05.md:59 (Telegram-Kontext) und :295 (beschreibende Nummernspanne "0001…0014") — beide bleiben unverändert, da 0014 weiterhin Telegram bleibt
```

## Expected Behavior

- **Input:** Bestehende ADR-Dateien in `docs/adr/` (18 Dateien, davon 2 mit doppelt vergebener Nummer) und der inkonsistente Index in `docs/adr/README.md`.
- **Output:** Jede ADR-Datei hat eine eindeutige, vierstellige Nummer; `docs/adr/README.md` listet jede Datei genau einmal mit korrektem Titel und Link; alle Cross-Referenzen im Repo zeigen auf die jeweils korrekte (ggf. neue) Nummer.
- **Side effects:** Zwei Dateien werden umbenannt (`git mv`), was ihre Git-Historie als Rename erhält, aber ihren Pfad ändert — Links von außerhalb des Repos (z.B. gespeicherte URLs) auf die alten Dateinamen würden brechen. Kein Code-Verhalten betroffen (reine Doku, `[no-adr]`-Commit).

## Acceptance Criteria

- **AC-1:** Given der Zustand von `docs/adr/` nach der Umnummerierung / When man alle `docs/adr/*.md`-Dateien (außer `README.md` und `_template.md`) mit den Zeilen der Index-Tabelle in `docs/adr/README.md` abgleicht / Then besteht eine Bijektion: jede Datei ist genau einmal im Index gelistet, keine Nummer taucht doppelt auf, keine Datei fehlt und keine Index-Zeile verweist auf eine nicht existierende Datei.
  - Test: `# doc-compliance-test`. Parst die Dateinamen in `docs/adr/*.md` (Regex `^\d{4}-.*\.md$`, `README.md`/`_template.md` ausgeschlossen) und extrahiert parallel alle `[NNNN](dateiname.md)`-Zeilen aus der Index-Tabelle in `docs/adr/README.md`. Assert: beide Mengen sind identisch (Set-Vergleich Dateiname), jede Nummer NNNN kommt in der extrahierten Zeilenliste genau einmal vor, und jede Index-Zeile referenziert eine tatsächlich existierende Datei.

- **AC-2:** Given den Nullgradgrenze-Kontext (ehemals ADR-0014, jetzt ADR-0019) / When man alle Markdown-Dateien im Repo (`docs/**/*.md`) nach der Zeichenkette "ADR-0014" durchsucht / Then referenziert keine verbleibende Fundstelle mehr die Nullgradgrenze-Entscheidung unter der alten Nummer — alle bekannten Nullgradgrenze-Cross-Referenzen (`docs/specs/modules/fix_alert_bundle_958ff.md`, `docs/features/architecture.md`, `docs/features/issue-816-alert-deviation-core.md`, `docs/reference/api_contract.md`) zeigen auf "ADR-0019"; verbleibende Treffer für "ADR-0014" existieren ausschließlich im Telegram-Kontext (Dateiname `0014-telegram-multi-bubble-format.md` oder Beschreibungstext "Telegram"/"Multi-Bubble").
  - Test: `# doc-compliance-test`. Grep über `docs/**/*.md` nach `ADR-0014`. Für jede Fundstelle: assert, dass die umgebende Zeile (bzw. Datei-Kontext) sich eindeutig auf Telegram/Multi-Bubble bezieht (z.B. via Nachbarschafts-Check auf "Telegram" oder "Bubble" im gleichen Absatz/Datei), nicht auf Nullgradgrenze/`freezing_level`/`snow_line`.

- **AC-3:** Given den node:test-Kontext (ehemals ADR-0013, jetzt ADR-0020) / When man alle Markdown-Dateien im Repo nach der Zeichenkette "ADR-0013" bzw. dem Dateinamen "0013-node-test-frontend-unit-runner.md" durchsucht / Then referenziert keine verbleibende Fundstelle mehr die node:test-Entscheidung unter der alten Nummer — `docs/specs/modules/fix_972_974_975_tooling.md` und `docs/adr/README.md` verweisen auf "0020-node-test-frontend-unit-runner.md"/"ADR-0020"; verbleibende Treffer für "ADR-0013" existieren ausschließlich im Alert-Threshold-Kontext (Δ-Sensitivitätsschwelle, inkl. Code-Kommentar `src/output/renderers/alert/model.py:66`).
  - Test: `# doc-compliance-test`. Grep über `docs/**/*.md` und `src/**/*.py` nach `ADR-0013` sowie nach dem alten Dateinamen `0013-node-test-frontend-unit-runner.md`. Assert: der alte Dateiname taucht nirgends mehr auf; jede verbleibende "ADR-0013"-Fundstelle bezieht sich nachweislich auf Alert-Threshold/Δ-Sensitivität (Nachbarschafts-Check auf "threshold"/"Δ"/"Sensitivität" im gleichen Kontext), nicht auf node:test/vitest.

## Known Limitations

- Kein automatisiertes Tooling verhindert künftige Index-Drift (z.B. bei Anlage einer neuen ADR-Datei ohne README-Nachtrag) — das strukturelle Gegenstück (Plugin-seitige Reflexionsprüfung bei Spec-Freigabe) ist separat als `henemm/agent-os-openspec#63` gemeldet und **nicht** Teil dieses Scopes.
- Die Doku-Compliance-Tests (AC-1 bis AC-3) laufen nur bei explizitem Aufruf, nicht als CI-Gate bei jeder ADR-Änderung — sie beweisen den Zustand zum Zeitpunkt der Implementierung, nicht dauerhaft.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Index-/Nummerierungs-Pflege bestehender ADRs, keine neue Architekturentscheidung. Commit trägt `[no-adr]`.

## Changelog

- 2026-07-09: Initial spec created (Issue #1165), erweitert um zweite Kollision (ADR-0013) nach Team-Lead-Rückmeldung
- 2026-07-09: Implementiert und validiert (3/3 Tests grün, Adversary VERIFIED) — 8 Dateien aktualisiert, 2 ADR-Dateien umbenannt, Index + Cross-Referenzen konsistent
