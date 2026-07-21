---
entity_id: issue_603_design_fidelity_gate
type: module
created: 2026-06-04
updated: 2026-06-04
status: draft
version: "1.0"
tags: [tooling, design, gate, playwright]
---

# Design-Fidelity Gate (Issue #603)

## Approval

- [ ] Approved

## Purpose

Automatisches Pixel-Diff-Tool das die visuelle Übereinstimmung zwischen Staging-Screenshot
und Claude-Design-Vorgabe (Soll-PNG) misst und bei mehr als 10% Abweichung das Schließen
eines `design-compliance`-Issues blockiert.

## Source

- **Neue Datei:** `.claude/hooks/design_fidelity_diff.py` (Pixel-Diff-Tool)
- **Neue Datei:** `.claude/hooks/pre_issue_close_design_gate.py` (Gate-Hook)
- **Geändert:** `pyproject.toml` (Pillow-Dependency ergänzen)
- **Geändert:** `.claude/settings.json` (neuer PreToolUse:Bash Hook)

## Estimated Scope

- **LoC:** ~170 (120 diff-tool + 50 gate-hook)
- **Files:** 4
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| Playwright | runtime | Screenshot von Staging (Login + Navigate) |
| Pillow (PIL) | runtime | PNG-Laden und Pixel-Diff-Visualisierung |
| numpy | runtime | Pixel-Vergleich per Array-Diff |
| `.claude/validator.env` | config | Login-Credentials (GZ_VALIDATOR_USER, GZ_VALIDATOR_PASS) |
| `claude-code-handoff/current/soll/` | data | 29 Soll-PNGs als Referenz |
| `docs/artifacts/<workflow>/` | output | JSON-Report + Diff-Bild |

## Implementation Details

### design_fidelity_diff.py

CLI-Tool mit Argument `--screen <screen-id>` (= Dateiname ohne `.png`):

1. Source `.claude/validator.env` (graceful fail wenn nicht vorhanden)
2. Playwright: Chromium headless, Viewport 1400×900
3. Login: `/login` → `input[name="username"]` → `input[name="password"]` → `button[type="submit"]`
4. Navigate zu Screen-URL (via `SCREEN_URL_MAP`)
5. Warte auf Seitenladung (`networkidle`)
6. Screenshot: `page.screenshot(full_page=False)` → `/tmp/ist-<screen>.png`
7. Lade Soll-PNG aus `claude-code-handoff/current/soll/<screen>.png`
8. Skaliere Soll auf Viewport-Größe (1400×900) falls abweichend
9. Pixel-Diff via numpy: `diff = np.abs(ist_arr.astype(int) - soll_arr.astype(int))`
10. Diff-Prozent: `changed_pixels / total_pixels * 100`
11. Diff-Bild: rote Pixel wo Diff > Threshold (via Pillow)
12. Schreibe `docs/artifacts/<workflow>/design-diff-<screen>.json`
13. Exit 0 wenn diff_pct < threshold (default 10.0), sonst Exit 1

**SCREEN_URL_MAP** (initial, erweiterbar):
```python
SCREEN_URL_MAP = {
    "G-compare-uebersicht-kacheln": "/compare",
    "D-home-trip": "/",
    "D-home-compare": "/",
    "D-home-planning": "/",
    "E-trips-list-variant": "/trips",
    "F-trip-detail-overview": "/trips/{first_trip_id}",
    "G-compare-wizard-step1": "/compare/new",
    "H-archive": "/archive",
    "I-wizard-step1-route": "/trips/new",
}
```

### JSON-Artefakt-Format
```json
{
  "screen": "G-compare-uebersicht-kacheln",
  "diff_pct": 7.3,
  "threshold": 10.0,
  "passed": true,
  "ist_path": "docs/artifacts/<workflow>/design-diff-G-compare-uebersicht-kacheln-ist.png",
  "soll_path": "claude-code-handoff/current/soll/G-compare-uebersicht-kacheln.png",
  "diff_path": "docs/artifacts/<workflow>/design-diff-G-compare-uebersicht-kacheln-diff.png",
  "checked_at": "2026-06-04T10:00:00+00:00",
  "workflow": "issue-603-design-fidelity-gate"
}
```

### pre_issue_close_design_gate.py

PreToolUse:Bash Hook, greift wenn `gh issue close` ausgeführt wird:

1. Parse `CLAUDE_TOOL_INPUT` → extrahiere Issue-Nummer
2. `gh issue view <N> --json labels` → prüfe ob `design-compliance` in Labels
3. Wenn kein `design-compliance` Label → Exit 0 (nicht betroffen)
4. Lade aktiven Workflow via `GZ_ACTIVE_WORKFLOW` env
5. Suche `docs/artifacts/<workflow>/design-diff-*.json` mit `passed: true`
6. Wenn kein Pass-Artefakt → Exit 2 (blockiert) mit Hinweis auf `design_fidelity_diff.py`
7. Wenn Pass-Artefakt vorhanden → Exit 0 (erlaubt)

### settings.json Ergänzung
Neuer Eintrag in `hooks.PreToolUse[]`:
```json
{
  "matcher": "Bash",
  "hooks": [{
    "type": "command",
    "command": "if [ -f \"${CLAUDE_PROJECT_DIR}/.claude/hooks/pre_issue_close_design_gate.py\" ]; then python3 \"${CLAUDE_PROJECT_DIR}/.claude/hooks/pre_issue_close_design_gate.py\"; fi"
  }]
}
```

## Acceptance Criteria

**AC-1:** Gegeben ein Screen-ID mit passendem Soll-PNG in `claude-code-handoff/current/soll/`, wenn `python3 .claude/hooks/design_fidelity_diff.py --screen <screen-id>` läuft, dann erzeugt es einen JSON-Report unter `docs/artifacts/<workflow>/design-diff-<screen-id>.json` + ein Diff-PNG, und gibt Exit 0 zurück wenn der Pixel-Diff unter 10% liegt oder Exit 1 wenn er darüber liegt.

**AC-2:** Gegeben ein offenes Issue mit Label `design-compliance` und kein `design-diff-*.json`-Artefakt mit `"passed": true` im aktiven Workflow, wenn `gh issue close <N>` ausgeführt wird, dann blockt der Hook mit einer erklärenden Fehlermeldung die auf `design_fidelity_diff.py` verweist.

**AC-3:** Gegeben der Compare-Liste-Screen (`G-compare-uebersicht-kacheln`), wenn `design_fidelity_diff.py --screen G-compare-uebersicht-kacheln` nach der aktuellen Implementierung aus Issue #582 läuft, dann ist der Diff-Wert messbar (Report wird erzeugt) — dieser Pilot-Lauf beweist dass das Tool auf einem echten Screen funktioniert.

**AC-4:** Gegeben Pillow nicht in den Abhängigkeiten war, wenn `uv sync` nach dem Commit läuft, dann ist Pillow erfolgreich installiert und `import PIL` schlägt nicht fehl.
