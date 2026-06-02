# Context: bug-554-556-test-fixes

## Request Summary
Zwei fehlerhafte Tests beheben: #554 (playwright-Env-Check bricht immer ab) und #556 (Sidebar-Test prüft Literal statt Config). #556 ist laut Commit-Message bereits behoben; #554 braucht einen `pytest.skip`.

## Related Files
| File | Relevance |
|------|-----------|
| `tests/tdd/test_epic_404_phase2_ist_screenshots.py:84` | Enthält `test_env_playwright_vorhanden` — hard assert statt skip |
| `tests/tdd/test_trips_naming.py:34` | Enthält `test_sidebar_uses_trips_label` — bereits grün |
| `frontend/src/lib/components/ui/sidebar/Sidebar.svelte:27-29` | Config-Array mit `'Meine Touren'`-Literal — erklärt warum #556 bereits besteht |

## Befund #556

Test **besteht bereits** (grün). Commit `a871fd6` (2026-06-02) hat die Sidebar-Migration inklusive dieses Tests fix erledigt — die Commit-Message nennt explizit "#556 (Sidebar-Test-Drift, mit Fix erledigt)". Issue muss nur geschlossen werden.

## Befund #554

Test schlägt **dauerhaft fehl**, weil `frontend/.env.playwright` nicht im Repo liegt (enthält Credentials). Fix: `pytest.skip(...)` wenn Datei fehlt — identische Lösung wie bei anderen optionalen E2E-Voraussetzungstests.

## Existing Patterns
- `pytest.skip` für optionale/umgebungsabhängige Tests: bereits im Projekt-Standard (pyproject.toml: `markers: live`)
- Muster: früher Check am Funktionsanfang `if not file.exists(): pytest.skip("...")`

## Dependencies
- `tests/tdd/test_epic_404_phase2_ist_screenshots.py` hängt von keinem anderen Code ab — pure Dateisystem-Prüfung

## Risks & Considerations
- Kein Risiko: nur Test-Code, kein Produktions-Code betroffen
- #556 ist bereits behoben — kein Code-Edit nötig, nur Issue schließen
