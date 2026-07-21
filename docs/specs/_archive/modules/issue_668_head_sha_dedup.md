---
entity_id: issue_668_head_sha_dedup
type: module
created: 2026-06-08
updated: 2026-06-08
status: draft
version: "1.0"
tags: [tooling, e2e, staging-gate, refactor]
---

# Issue #668 — staging_gate.write_verdict: _head_sha() einmal erfassen

## Approval

- [ ] Approved

## Purpose

`write_verdict()` in `.claude/hooks/staging_gate.py` ruft `_head_sha()` (intern
`git rev-parse HEAD`) zweimal auf: einmal indirekt via `_commit_e2e_path()`,
einmal direkt für `payload["verified_commit"]`. Beide liefern denselben SHA. Der
Fix erfasst den SHA einmal und reicht ihn weiter — ein Subprozess weniger pro Aufruf,
ohne Verhaltensänderung am geschriebenen Artefakt.

## Source

- **File:** `.claude/hooks/staging_gate.py`
- **Identifier:** `write_verdict()`

## Estimated Scope

- **LoC:** ~5
- **Files:** 1 (Source) + 1 (Test)
- **Effort:** low

## Dependencies

- Upstream: `_e2e_paths.head_sha(REPO_DIR)` (#665) — echtes `git rev-parse HEAD`.
- Downstream: `/e2e-verify`-Skill + `staging-validator` rufen `write_verdict` auf;
  Output-Format und SHA-Wert bleiben unverändert.

## Acceptance Criteria

**AC-1:** Given ein `write_verdict`-Aufruf ohne `--e2e-path`-Override in einem
echten Git-Repo, When das Verdict geschrieben wird, Then wird `git rev-parse HEAD`
**genau einmal** als Subprozess ausgeführt (vor dem Fix: zweimal).

**AC-2:** Given ein VERIFIED-Verdict, When `write_verdict` die Attestation schreibt,
Then enthält `payload["verified_commit"]` weiterhin exakt den aktuellen HEAD-SHA
(bit-identisch zum Vor-Fix-Verhalten, kein Format- oder Wertunterschied).

**AC-3:** Given ein expliziter `--e2e-path`-Override, When `write_verdict` aufgerufen
wird, Then wird die Attestation an genau diesen Pfad geschrieben und `verified_commit`
entspricht dem HEAD-SHA — der Override-Pfad bleibt unverändert funktionsfähig.

## Out of Scope

- `gate_check()` (ruft `_head_sha()` bereits nur einmal auf) — nicht angefasst.
- Signatur-Änderungen an `_commit_e2e_path` / `_head_sha` — der vorhandene optionale
  SHA-Parameter von `_commit_e2e_path(sha)` reicht aus.

## Implementation Details

In `write_verdict()` wird der HEAD-SHA zu Funktionsbeginn einmal erfasst und an beide
Verwendungsstellen weitergereicht:

```python
def write_verdict(verdict, findings_path, e2e_path=None):
    sha = _head_sha()                       # einmalig
    if e2e_path is None:
        e2e_path = _commit_e2e_path(sha)    # statt _commit_e2e_path() (kein 2. rev-parse)
    ...
    payload = {
        "verified_commit": sha,             # statt _head_sha()
        ...
    }
```

`_commit_e2e_path(sha)` akzeptiert den SHA bereits als optionalen Parameter (#665) —
keine Signaturänderung nötig. Reine Reihenfolge-/Variablen-Umstellung innerhalb der
Funktion.

## Expected Behavior

| Input | Output |
|-------|--------|
| `write_verdict("VERIFIED ...", findings)` ohne Override | Attestation unter `.claude/e2e_verified/<HEAD-SHA>.json`, `verified_commit == HEAD-SHA`, **1×** `git rev-parse HEAD` |
| `write_verdict("VERIFIED ...", findings, e2e_path=X)` | Attestation unter `X`, `verified_commit == HEAD-SHA`, **1×** `git rev-parse HEAD` |
| `write_verdict("BROKEN ...", findings)` | Exit 1, kein Artefakt (unverändert) |

Der geschriebene Datei-Inhalt ist bit-identisch zum Vor-Fix-Verhalten.

## Changelog

- **2026-06-08 (v1.0):** Initiale Spec. `_head_sha()`-Doppelaufruf in `write_verdict`
  zu einmaliger Erfassung konsolidiert (Issue #668, Nebenbefund aus #665 F002).
