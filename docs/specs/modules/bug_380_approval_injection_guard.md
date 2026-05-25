---
entity_id: bug_380_approval_injection_guard
type: module
created: 2026-05-25
updated: 2026-05-25
status: draft
version: "1.0"
tags: [bug, workflow, hook, security]
---

# Bug #380 — Approval-Hook gegen injizierte Inhalte härten

## Approval

- [x] Approved

## Purpose

Der UserPromptSubmit-Hook `workflow_state_updater.py` darf Phasen-Übergänge
(Spec-Freigabe, GREEN-Freigabe, Abschluss) **ausschließlich** aus echtem
User-Text auslösen — niemals aus harness-injizierten Inhalten (Task-Notifications
abgeschlossener Hintergrund-Agenten, System-Reminder, Tool-Ergebnisse), die
zufällig Freigabe-Wörter enthalten. Behebt False-Positive-Freigaben (#380).

## Source

- **File:** `.claude/hooks/workflow_state_updater.py`
- **Identifier:** `main()` (Eingangs-Guard), neue Helfer `_is_injected_content()`, `_looks_like_user_turn()`
- **Schicht:** Workflow-Hook-Infrastruktur (Python), keine App-Schicht. Test in `tests/tdd/`.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `is_approval_message` / `is_green_approval` / `is_completion_message` | Funktion | Substring-Scan, der NUR auf gefilterten User-Text laufen darf |
| Session-Registry (#325/#332) | Mechanismus | Workflow-Auflösung — unverändert |

## Implementation Details

Ursache: `main()` (`workflow_state_updater.py:100`) liest `user_prompt` und scannt
ihn ungefiltert per Wortgrenzen-Regex nach Freigabe-/GREEN-/Abschluss-Phrasen.
Harness-injizierte Inhalte kommen als UserPromptSubmit-Event an und werden nicht
von echtem User-Text unterschieden → enthält ein Agent-Ergebnis ein Trigger-Wort
(bei einem Spec-Validator quasi garantiert „approved"), entsteht ein Phantom-Übergang.

Fix: **ein** Guard am Eingang von `main()`, VOR allen drei Prüfungen (deckt also
Spec-, GREEN- und Abschluss-Erkennung gleichermaßen ab):

```python
_INJECTED_MARKERS = (
    "<task-notification", "<system-reminder", "<function_results",
    "<function_calls", "tool_use_id", "spec validation:", "verdict:",
    "approval status",
)

def _is_injected_content(message: str) -> bool:
    low = message.lower()
    return any(m in low for m in _INJECTED_MARKERS)

def _looks_like_user_turn(message: str) -> bool:
    # Echte Freigaben sind kurze, eigenständige Turns.
    s = message.strip()
    return 0 < len(s) <= 120 and len(s.split()) <= 20

# in main(), nach dem user_message-Aufbau, vor is_approval/is_green/is_complete:
if _is_injected_content(user_message) or not _looks_like_user_turn(user_message):
    sys.exit(0)
```

Begründung der Doppel-Absicherung: Marker-Guard ist zielgenau; Längen-Guard greift
auch bei unbekanntem Marker-Format. Falsch-Negativ (User tippt erneut „approved")
ist harmlos; Falsch-Positiv (Phantom-Freigabe) verletzt das Kernprinzip.

**Verschärfung nach Adversary-Befund F001:** Marker- + Längen-Guard allein
genügen NICHT — kurze Klartext-Agent-Zusammenfassungen ohne XML-Marker
(„Task done. approved.", „Tests pass. Go.", „Job done!") rutschen sonst durch.
Daher wird die Phrasen-Erkennung zusätzlich **am Satzanfang verankert**: eine
Trigger-Phrase zählt nur, wenn die Nachricht mit ihr BEGINNT (nicht, wenn sie
sie irgendwo enthält). Negativer Lookahead `(?![a-z0-9])` verhindert
Wort-Präfix-Treffer („go" ≠ „going"):

```python
def _starts_with_command(message: str, phrases) -> bool:
    s = message.strip().lower()
    # Phrase nur gültig, wenn ihr Satzende, Leerzeichen oder Satzzeichen folgt.
    return any(re.match(re.escape(p.lower()) + r"(?=$|\s|[.,!?])", s) for p in phrases)

# is_approval_message / is_green_approval / is_completion_message nutzen dies
# statt der bisherigen \b<phrase>\b-Suche irgendwo im Text.
```

**Verschärfung 2 nach Adversary-Befund F003:** Die erste Anchoring-Fassung
nutzte `(?![a-z0-9])` und ließ damit header-artige Ausgaben mit Trenner durch
(„approved: spec validation passed", „go: all checks passed"). Die positive
Erlaubnisliste `(?=$|\s|[.,!?])` lässt nur natürliche Freigabe-Fortsetzungen zu
(Satzende / Leerzeichen / `. , ! ?`) und blockiert Trenner wie `:` `-` `;` `=`.

So bleiben legitime Freigaben am Anfang erhalten („approved", „go ahead",
„looks good", „approved, sieht gut aus"), während nachgestellte Trigger-Wörter
hinter einem Status-Satz blockiert werden.

## Expected Behavior

- **Input:** UserPromptSubmit-Payload mit `user_prompt`.
- **Output:** Phasen-Übergang nur bei echtem, kurzem User-Turn mit Freigabe-Phrase.
- **Side effects:** Bei injiziertem/langem Inhalt: `sys.exit(0)`, kein State-Write.

## Acceptance Criteria

- **AC-1:** Given Workflow in `phase3_spec` / When eine UserPromptSubmit-Payload mit einem `<task-notification>`-Block eintrifft, der „approved" und „SPEC VALIDATION: VALID" enthält / Then bleibt `current_phase == phase3_spec`, `spec_approved == False`, und es wird KEIN `phase_transitions`-Eintrag geschrieben
  - Test: (populated after /tdd-red)

- **AC-2:** Given Workflow in `phase3_spec` / When der echte, kurze User-Turn „approved" eintrifft / Then transitioniert der Workflow nach `phase4_approved` mit `spec_approved == True` (echte Freigabe funktioniert weiterhin)
  - Test: (populated after /tdd-red)

- **AC-3:** Given Workflow in `phase3_spec` / When eine lange Nachricht (> 120 Zeichen) eintrifft, die „approved" nur als eingebetteten Substring enthält / Then erfolgt KEIN Übergang (Längen-Guard)
  - Test: (populated after /tdd-red)

- **AC-4:** Given Workflow in `phase6_implement` / When eine Payload mit `<system-reminder>` oder Tool-Ergebnis-Marker eintrifft, die GREEN-/Abschluss-Wörter („go", „done", „complete") enthält / Then erfolgt WEDER eine GREEN-Freigabe NOCH ein Abschluss (Guard schützt alle drei Erkennungspfade)
  - Test: (populated after /tdd-red)

- **AC-5:** Given Workflow in `phase6_implement` / When der echte, kurze User-Turn „go" eintrifft / Then wird `green_approved == True` gesetzt (echte GREEN-Freigabe funktioniert weiterhin)
  - Test: (populated after /tdd-red)

- **AC-6:** Given eine kurze Klartext-Zusammenfassung OHNE XML-Marker, bei der das Trigger-Wort hinter einem Status-Satz steht („Task done. approved.", „Tests pass. Go.", „Deployment complete. Done.") / When der Hook sie verarbeitet / Then erfolgt KEIN Übergang (Anchoring am Satzanfang — Adversary-Befund F001)
  - Test: (populated after /tdd-red)

- **AC-7:** Given mehrwortige, mit der Phrase BEGINNENDE echte Freigaben („looks good", „go ahead", „approved, sieht gut aus") / When sie eintreffen / Then wirken sie weiterhin (Anchoring blockiert keine legitimen Freigaben — No-Regression)
  - Test: (populated after /tdd-red)

- **AC-8:** Given header-artige Ausgaben, bei denen die Phrase am Anfang steht, aber von einem Trenner gefolgt wird („approved: spec validation passed", „go: all checks passed", „done: deployment succeeded") / When sie eintreffen / Then erfolgt KEIN Übergang (positive Erlaubnisliste `(?=$|\s|[.,!?])` — Adversary-Befund F003)
  - Test: (populated after /tdd-red)

## Known Limitations

- Eine echte Freigabe muss als kurzer, eigenständiger Turn (≤ 120 Zeichen, ≤ 20 Wörter) kommen, der MIT der Phrase BEGINNT. Eingebettete oder header-artige Treffer („…: approved", „approved: …") werden bewusst nicht erkannt — der User tippt dann erneut knapp „approved". Falsch-Negativ ist harmlos, Falsch-Positiv gefährlich.
- Die drei Guards (Marker / Länge / Anchoring+Erlaubnisliste) sind Verteidigung in der Tiefe. Die real beobachteten Harness-Injektionsformate (XML-umschlossen `<task-notification>`/`<system-reminder>`, Validator-Ausgaben mit Präfix `SPEC VALIDATION:`/`VERDICT:`) werden bereits vom Marker-Guard gefangen; Anchoring + Erlaubnisliste schließen zusätzlich marker-lose Klartext-Zusammenfassungen.

## Out of Scope

- Keine Änderung an der Phrasen-Liste selbst (`get_approval_phrases`, `GREEN_APPROVAL_PHRASES`, `COMPLETION_PHRASES`).
- Keine Änderung am Session-Registry-Routing (#325/#332).

## Changelog

- 2026-05-25: Initial spec created (#380)
- 2026-05-25: Adversary F001 → Anchoring am Satzanfang ergänzt (AC-6/AC-7)
- 2026-05-25: Adversary F003 → positive Erlaubnisliste `(?=$|\s|[.,!?])` statt `(?![a-z0-9])` (AC-8)
