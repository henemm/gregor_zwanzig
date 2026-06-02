# Context: bug-548-workflow-output-readability

## Request Summary
Die PO-Zusammenfassungen in den Workflow-Phasen-Command-Dateien werden in Claude Code's UI mit weißem Text auf schwarzem Hintergrund gerendert, wobei die Leerzeichen zwischen den Wörtern weiß (Standard-Hintergrund) bleiben — das macht den Text kaum lesbar.

## Root Cause (klar identifiziert)
Das `>` Blockquote-Format in den Command-Dateien (`2-analyse.md`, `3-write-spec.md`, `4-tdd-red.md`, `7-deploy.md`) erzeugt in Claude Code's Markdown-Renderer eine Darstellung, bei der Text-Tokens jeweils einzeln mit dunklem Hintergrund hervorgehoben werden, während die Leerzeichen den Standard-Hintergrund (weiß/hell) behalten.

## Related Files

| File | Relevance |
|------|-----------|
| `.claude/commands/2-analyse.md` | PO-Zusammenfassung (Zeilen 84-94) mit `>` Blockquotes |
| `.claude/commands/3-write-spec.md` | Akzeptanzkriterien-Ausgabe (Zeilen 80-93) mit `>` Blockquotes |
| `.claude/commands/4-tdd-red.md` | Tests-Übersicht (Zeilen 90-103) mit `>` Blockquotes + Tabelle |
| `.claude/commands/7-deploy.md` | Tech-Lead-Brief (Zeilen 5-22) mit `>` Blockquotes |

## Existing Patterns
- Alle 4 Dateien wurden durch Commit `b3a2ef1` (feat #535) hinzugefügt/geändert
- Die `>` Blockquote-Syntax ist das einzige Format-Element, das das visuelle Problem erzeugt
- Vor #535 gab es keine PO-Zusammenfassungen in diesen Command-Dateien

## Fix-Ansatz

**Option A (empfohlen):** `>` Blockquote-Prefix entfernen, plain text mit **bold** und evtl. `---` Trennzeichen:
```
---
**Das Problem:** [text]
**Warum das wichtig ist:** [text]
**Was ich vorhabe:** [text]

Sage **'go'** um fortzufahren — oder korrigiere mich.
```

**Option B:** Kein Sonderformat — einfach normaler Text mit bold-Überschriften, kein Blockquote.

## Dependencies
- Upstream: Claude liest Command-Files als Skill-Instruktionen
- Downstream: Kein Code betroffen — nur Instruktions-Dateien für Claude's Output-Format

## Existing Specs
- Keine zugehörige Spec notwendig für reine Instruktionsdatei-Änderungen

## Risks & Considerations
- Sehr niedrig — nur `.claude/commands/` Instruktionsdateien
- Kein Python/Go/Frontend-Code betroffen
- Kein Daten-Schema berührt
- Sofort wirksam nach Commit (Claude liest die Dateien frisch pro Session)
