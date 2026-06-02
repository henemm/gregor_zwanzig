---
entity_id: bug_548_workflow_output_readability
type: bugfix
created: 2026-06-02
updated: 2026-06-02
status: draft
version: "1.0"
tags: [workflow, infra, formatting]
---

# Bug #548: Workflow-Ausgabe Lesbarkeit

## Approval

- [ ] Approved

## Purpose

Behebt die unlesbare Darstellung der PO-Zusammenfassungen in Claude Code's UI: Das `>` Blockquote-Format erzeugt weißen Text auf schwarzem Hintergrund, wobei die Leerzeichen zwischen den Wörtern weiß bleiben — das macht die Ausgabe kaum lesbar.

## Source

- **Files:**
  - `.claude/commands/2-analyse.md` (Zeile 86–93)
  - `.claude/commands/3-write-spec.md` (Zeile 82–93)
  - `.claude/commands/4-tdd-red.md` (Zeile 91–103)
  - `.claude/commands/7-deploy.md` (Zeile 7–21)

## Estimated Scope

- **LoC:** ~40 (reine Format-Änderung, kein Logik-Code)
- **Files:** 4
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| Claude Code Markdown-Renderer | extern | Verarbeitet das Format der Command-Files |

## Implementation Details

In allen 4 Command-Files: `>` Blockquote-Prefix entfernen.

**Vorher (erzeugt Lesbarkeits-Bug):**
```markdown
> **Das Problem:** [text]
> **Warum das wichtig ist:** [text]
> **Was ich vorhabe:** [text]
>
> Sage **'go'** um fortzufahren — oder korrigiere mich.
```

**Nachher (lesbar, plain text mit bold):**
```markdown
**Das Problem:** [text]
**Warum das wichtig ist:** [text]
**Was ich vorhabe:** [text]

Sage **'go'** um fortzufahren — oder korrigiere mich.
```

Gleiches Muster für alle PO-Zusammenfassungen in den 4 Dateien.

## Expected Behavior

- **Input:** Claude liest Command-Files und folgt den Formatierungsanweisungen
- **Output:** PO-Zusammenfassungen werden als normaler fetter Text gerendert, ohne schwarzen Hintergrund
- **Side effects:** Keine — inhaltlich ändert sich nichts

## Acceptance Criteria

**AC-1:** Given die 4 Command-Files enthalten PO-Zusammenfassungen / When Claude eine Workflow-Phase abschließt und die Zusammenfassung ausgibt / Then enthält der Output-Text kein `>` Blockquote-Zeichen am Zeilenanfang der Zusammenfassungs-Sätze.

**AC-2:** Given `.claude/commands/2-analyse.md` / When der Abschnitt "PO-Zusammenfassung" gelesen wird / Then beginnen die Sätze "Das Problem:", "Warum das wichtig ist:" und "Was ich vorhabe:" direkt mit `**` (bold), ohne vorangestelltes `>`.

**AC-3:** Given `.claude/commands/3-write-spec.md` / When der Abschnitt "Akzeptanzkriterien für PO präsentieren" gelesen wird / Then beginnen die Ausgabe-Zeilen des Beispiel-Outputs ohne `>` Prefix.

**AC-4:** Given `.claude/commands/4-tdd-red.md` / When der Abschnitt "PO-Zusammenfassung ausgeben" gelesen wird / Then ist die Tabellen-Ausgabe und der abschließende Satz ohne `>` Blockquote-Format dargestellt.

**AC-5:** Given `.claude/commands/7-deploy.md` / When der Abschnitt "Tech-Lead-Brief" gelesen wird / Then sind alle Brief-Zeilen ("Was wurde gebaut:", "Staging validiert:", "Tests:", "Offene Punkte:", "Risiko:", "Empfehlung:") ohne `>` Prefix.

## Known Limitations

- Keine — reine Formatkorrektur ohne funktionale Auswirkungen.

## Changelog

- 2026-06-02: Initial spec created (Issue #548)
