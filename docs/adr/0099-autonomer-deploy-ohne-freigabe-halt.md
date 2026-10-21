# ADR-0099: Autonomer Deploy ohne Freigabe-Halt — freigabepflichtig ist allein die Spec

- **Status:** Akzeptiert (rückwirkend dokumentiert 2026-10-21 — PO-Vorgabe 2026-08-03, in CLAUDE.md verankert mit Commit `22e219d88`, 2026-08-05)
- **Datum:** 2026-10-21
- **Bezug:** CLAUDE.md §„Workflow" (Tabellenzeile `/70-deploy`, Absatz „Freigabepflichtig ist allein die Spec"), Issue #1511, Commits `22e219d88` (Widerspruch aufgelöst) und `c79980add` (`/70-deploy` angeglichen), `.claude/commands/70-deploy.md`; ADR-0085 (CI-Deploy nur mit Nachweis), ADR-0098 (Liefer-Workflow)

## Kontext

Die Workflow-Tabelle in CLAUDE.md verlangte für `/70-deploy` „Pflicht: Tech-Lead-Brief lesen +
'go' sagen". Die PO-Vorgabe vom 2026-08-03 sagte das Gegenteil: die Pipeline läuft nach dem Merge
am Stück durch, der PO liest das Ergebnis danach. Zwei sich widersprechende Pflichtregeln machten
beide unverbindlich (Commit-Text `22e219d88`). Zusätzlich überdeckte eine globale
`~/.claude/commands/70-deploy.md` die Projektdatei (#1511 Punkt a, entfernt).

## Entscheidung

1. **Die einzige PO-Freigabe ist die Spec** (ACs auf Deutsch, `/30-write-spec`).
2. **Deploy läuft autonom am Stück:** nach dem Merge Staging-Poll → `/e2e-verify` →
   `deploy-gregor-prod.sh` → `prod_selftest.py` → Issue-Close.
3. **Ein selbst formulierter „Tech-Lead-Brief" mit Bitte um 'go'** ist dieselbe verbotene
   Prozessfrage in Freitextform.
4. **Einzige erlaubte Unterbrechung:** ein echtes Hard Gate scheitert (Staging-Verdict BROKEN,
   Selftest-Exit ≠ 0). Dann wird mit konkretem Befund eskaliert.

## Verworfene Alternativen

- **Freigabe-Halt vor dem Prod-Deploy:** verworfen (PO 2026-08-03) — die Hard Gates (E2E-Nachweis
  je Stand, Selftest) tragen die Sicherheit; ein menschliches „go" ohne neuen Befund fügt nur
  Wartezeit hinzu.

## Konsequenzen

- **Positiv:** Lieferungen bleiben nicht halbfertig zwischen Merge und Prod liegen.
- **Negativ / Preis:** Die Sicherheit hängt vollständig an der Qualität der Hard Gates (ADR-0085,
  `.claude/e2e_verified/<sha>.json`, `prod_selftest.py`).
- **Folgepflichten:** Issue-Close nur bei Selftest-Exit 0. Neue Prozess-Halte vor dem Deploy
  brauchen ein neues ADR.
