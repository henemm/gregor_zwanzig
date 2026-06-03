# Bug Analysis (Analysis-First)

Analyze a bug following the **Analysis-First** principle.

**NEVER fix directly!** First understand completely, then document, then (after approval) fix.

## Phase 1: Understand the Bug

1. **Capture symptoms:**
   - What exactly happens? (User description)
   - Where does it happen? (View, feature, context)
   - When does it happen? (Always? Sometimes? After specific action?)

2. **Define reproduction steps:**
   - Step-by-step instructions to reproduce
   - Expected behavior vs. actual behavior

## Phase 2: Find Root Cause

3. **Analyze code:**
   - Identify affected files
   - Trace data flow completely (NOT just fragments!)
   - Question: "Where does the problem ORIGINATE?"

4. **Identify root cause with certainty:**
   - Name concrete code location(s) (file:line)
   - WHY does this location cause the problem?
   - No speculation - only proven causes!

## Phase 3: Document

5. **Create entry in bug tracking:**

```markdown
## Bug: [Short Description]

- **Location:** [File(s)]
- **Problem:** [What goes wrong]
- **Expected:** [What should happen]
- **Root Cause:** [Why it happens - code location]
- **Test:** [How to verify fix]
- **Effort:** [Small/Medium/Large]
```

## Phase 4: Übergabe an Workflow

Nach der Dokumentation: PO-Zusammenfassung ausgeben und auf **'go'** warten.

**Das Problem:** [Was ist kaputt, aus Nutzersicht in 1 Satz]
**Warum das wichtig ist:** [Auswirkung auf den Nutzer in 1 Satz]
**Was ich vorhabe:** [Was ich bauen werde in 1 Satz]

Sage **'go'** um fortzufahren — oder korrigiere mich.

**STOP: Warte auf 'go'. Danach SOFORT den Workflow starten — kein Befehl vom User nötig:**
1. Kontext sammeln (Phase 1) + Analyse (Phase 2) → inline ausführen
2. Spec schreiben + ACs zeigen (Phase 3) → 'go'-Gate
3. TDD RED + Implementierung + Adversary → automatisch
4. Validierung + Deploy (Phase 7) → 'go'-Gate vor Produktion

## STOP Conditions

Stop and ask when:
- Root cause unclear (need more info)
- Bug not reproducible (need steps)
- Multiple possible causes (prioritize)
- Fix would change >5 files (split?)

## Output to User

Summarize (NO code, understandable language):

1. **What is the problem?** (1-2 sentences)
2. **Where is the cause?** (File + short explanation)
3. **How do we test the fix?** (Concrete steps)
4. **Estimated effort** (Small/Medium/Large)
