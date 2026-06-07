# Context: #586 — Design-Fidelity Alert-Config, Close-Gate

## Request Summary
Issue #586 verlangt die 1:1-Übernahme der Alert-Config nach `screen-alert-config.jsx` **und** das
Pixel-Diff-Close-Gate (`<10 %` gegen `K-alert-config-list.png`, Tool aus #603). Die Implementierung
ist bereits seit 2026-06-04 live; offen ist ausschließlich das nie gefahrene Diff-Gate.

## Ist-Zustand (entscheidend)
- **Code ist live:** Commit `75aed1f0 feat(#586): Alert-Config Design-Fidelity 1:1 …` liegt auf
  `origin/main` (seit 2026-06-04) und wurde **seitdem nicht mehr angefasst** → auf Prod aktiv.
  9 Dateien, Spec `docs/specs/modules/issue_586_alert_config_design.md`, Test
  `frontend/src/lib/components/alerts-tab/issue_586_design_fidelity.test.ts` (1098 Insertions).
  Adversary-Verdict damals VERIFIED.
- **Issue blieb offen**, weil es am 2026-06-04 als Teil der Epic-#575-Drift-Korrektur **wieder
  geöffnet** wurde: gefordert ist das Diff-Gate `python3 .claude/hooks/design_fidelity_diff.py
  --screen K-alert-config-list` mit `diff_pct < 10 %` + PASS-Artefakt
  (`pre_issue_close_design_gate.py` blockt Close ohne Artefakt).
- **Root-Cause „nie geschlossen":** `K-alert-config-list` ist im Diff-Tool nur auf `screen_url`
  `/trips` (die Trip-Liste) gemappt — **ohne `SCREEN_PRE_ACTIONS`**, die in einen Trip + den
  Alarme-Tab navigieren. Das Tool erreicht den Alert-Config-Screen also gar nicht; das Gate war
  technisch nie lauffähig.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/alerts-tab/AlertsTab.svelte` | Alert-Config-Screen (1:1 nach JSX), Tab im Trip-Detail |
| `frontend/src/lib/components/alerts-tab/AlertMetricTable.svelte` u.a. | übrige 1:1-Komponenten |
| `.claude/hooks/design_fidelity_diff.py` | Diff-Gate-Tool; braucht Navigation zum Alarme-Tab (`SCREEN_PRE_ACTIONS`) |
| `claude-code-handoff/current/jsx/screen-alert-config.jsx` | bindende JSX-Vorlage |
| `claude-code-handoff/current/soll/K-alert-config-list.png` | SOLL-Screenshot @ 1440px |
| `.claude/hooks/pre_issue_close_design_gate.py` | blockt Close ohne PASS-Artefakt |

## Existing Patterns (Schwester-Screens)
Die Screens D-home / E-trips-list / G-compare sind alle als **30 %-Override** in
`SCREEN_THRESHOLD_MAP` dokumentiert: Layout 1:1 (staging-validator bestätigt), aber Daten-/SOLL-
Divergenz macht `<10 %` strukturell unmöglich (dünnes Test-Konto vs. datenreiches SOLL; veraltete
SOLL-PNGs). Gleiche Situation hier zu erwarten — die Alarm-Daten des Staging-Test-Trips
unterscheiden sich von den SOLL-Demo-Daten.

## Risks & Considerations
- Reine **Verifikations-/Close-Aufgabe**, kein Neubau (Code 1:1 & VERIFIED seit 06-04).
- Nur Tooling-Edits an `.claude/hooks/design_fidelity_diff.py` zu erwarten (Navigation), evtl.
  dokumentierter Threshold-Override — **kein src/-Code**, sofern der Diff kein echtes Layout-Drift zeigt.
- **Memory-Regel:** Diff-Bild ansehen, bevor Threshold angefasst wird. Eigener Drift → fixen;
  SOLL≠JSX / Daten-Divergenz → dokumentierter Override + Design-Request (kein Maskieren).
- SOLL-Stale-Check: JSX enthält **keinen** Signal-Bezug → durch #610 nicht veraltet.
