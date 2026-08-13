---
entity_id: fix_1776_staging_gate_selfref
type: module
created: 2026-08-13
updated: 2026-08-13
status: draft
version: "1.0"
tags: [bugfix, staging-gate, deploy-safety]
---

# Fix #1776: staging_gate.py Selbstreferenz bei preflight_base

## Approval

- [ ] Approved

## Purpose

`_scope_diff_base()` in `staging_gate.py` liest die vom Preflight hinterlegte Diff-Basis
(`preflight_base`) ohne zu prüfen, ob diese zufällig mit dem aktuellen HEAD identisch ist. Bei
Selbstreferenz (`preflight_base == head`) entsteht ein `HEAD..HEAD`-Diff, der immer leer ist und
fälschlich als `docs-only` klassifiziert wird — das lässt `gate_check()` die komplette
Staging-Attestations-Prüfung überspringen und Produktivcode ohne Staging-Nachweis passieren.
Der Fix ergänzt denselben Selbstreferenz-Schutz, den der direkt danach folgende
`marker_sha`-Zweig bereits hat.

## Source

- **File:** `.claude/hooks/staging_gate.py`
- **Identifier:** `def _scope_diff_base(head: str | None = None) -> str` (Zeile 158–161 betroffen)

## Estimated Scope

- **LoC:** ~1 (Fix) + ~30–40 (Tests)
- **Files:** 2
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `.claude/hooks/_e2e_paths.py::read_preflight_base` | function | Liefert die vom Preflight hinterlegte Diff-Basis, die `_scope_diff_base()` konsumiert |
| `.claude/hooks/_e2e_paths.py::write_preflight_base` | function | Wird im Test verwendet, um den Selbstreferenz-Fall (`base == target`) zu erzeugen |
| `tests/tdd/test_fix_1428_preflight_scope_base.py` | test module | Bestehende Regressionstests für `_scope_diff_base()`, dürfen durch den Fix nicht brechen |

## Implementation Details

```
Vorher (.claude/hooks/staging_gate.py, _scope_diff_base(), Zeile 158-161):
    preflight_base = _e2e_paths.read_preflight_base(_shared_repo_dir(), head)
    if preflight_base is not None:
        if _e2e_paths.commit_exists(preflight_base, _verified_repo_dir()):
            return preflight_base

Nachher:
    preflight_base = _e2e_paths.read_preflight_base(_shared_repo_dir(), head)
    if preflight_base is not None and preflight_base != head:
        if _e2e_paths.commit_exists(preflight_base, _verified_repo_dir()):
            return preflight_base
```

Der Guard spiegelt exakt das bestehende Muster des direkt folgenden `marker_sha`-Zweigs
(Zeile 163–166: `if marker_sha and marker_sha != head:`). Bei Selbstreferenz fällt die Funktion
durch zur Marker-Prüfung und ggf. weiter zu `"HEAD~1"` — dieselbe Fallback-Kette, die für den
`marker_sha`-Zweig bereits gilt und getestet ist.

`prod_selftest.py` ist unbetroffen: es hat einen eigenen `_scope_diff_base()`, der
`preflight_base` nicht konsumiert und dessen `marker_sha`-Schutz bereits korrekt ist.

## Expected Behavior

- **Input:** `_scope_diff_base(head=<SHA>)`, wobei für `<SHA>` per `write_preflight_base()` eine
  Diff-Basis hinterlegt wurde, die identisch mit `<SHA>` selbst ist (Selbstreferenz).
- **Output:** Die Funktion gibt **nicht** `<SHA>` zurück, sondern fällt auf die
  Marker-Basis (falls vorhanden und auflösbar, `!= head`) oder `"HEAD~1"` zurück — dieselbe
  Fallback-Kette wie im bestehenden `marker_sha`-Zweig.
- **Side effects:** Keine. Reiner Lesepfad, keine Schreiboperation auf Marker-/Preflight-Dateien.

## Acceptance Criteria

- **AC-1:** Given eine per `write_preflight_base(repo, target, base=target)` hinterlegte
  Selbstreferenz (Preflight-Basis == Ziel-Commit) für den aktuellen HEAD, When
  `_scope_diff_base(head=target)` aufgerufen wird, Then liefert die Funktion einen Wert `!=
  target` (Fallback auf Marker-SHA falls vorhanden und auflösbar, sonst `"HEAD~1"`) statt der
  Selbstreferenz.
  - Test: Neuer Test in `tests/tdd/test_fix_1428_preflight_scope_base.py` baut ein echtes
    Temp-Git-Repo, hinterlegt `write_preflight_base(tmp_path, target, target)` (Selbstreferenz)
    und ruft `GATE._scope_diff_base(head=target)` direkt auf (in-process, kein Mock der
    Git-Logik). Assertion: Rückgabewert `!= target`. Entfernt man die Bedingung
    `preflight_base != head` wieder (Mutations-Gegenprobe), liefert die Funktion `target` zurück
    und der Test wird rot — das belegt, dass der Test die Zusicherung an der Stelle prüft, an der
    sie wirkt.

- **AC-2:** Given der bestehende Normalfall ohne Selbstreferenz (Preflight-Basis zeigt auf einen
  von HEAD verschiedenen Commit, wie im Vorfall henemm-infra#148 / #1428), When
  `gate_check()` mit Preflight (`expected_commit` gesetzt) und danach der reguläre Check nach
  `git reset --hard` auf denselben Ziel-Commit laufen, Then bleibt das Ergebnis unverändert
  `docs-only` (Exit 0) für einen tatsächlich docs-only Diff — keine Regression durch den neuen
  Guard.
  - Test: Bestehender Test `test_regular_check_after_reset_agrees_with_preflight_docs_only`
    (`tests/tdd/test_fix_1428_preflight_scope_base.py:84`) läuft nach dem Fix weiterhin grün,
    ebenso `test_scope_diff_base_prefers_preflight_hint_over_marker` und
    `test_scope_diff_base_ignores_hint_for_wrong_target` (dieselbe Datei) — alle drei ohne
    Selbstreferenz-Konstellation, daher vom neuen Guard nicht betroffen.

## Known Limitations

- **RC2 (#1640) ist explizit NICHT Teil dieses Fixes.** Issue #1640 behandelt einen separaten
  Fehlerpfad: Nach einem fälschlichen `docs-only`-Lauf schreibt `gate_check()`
  (Zeile 568–569) den Gate-Marker mit `scope=docs-only` auf HEAD. Ein zweiter Lauf liest diesen
  gecachten Wert über `cached_scope_for_sha()` in `_detect_committed_scope()` direkt, ohne
  erneut `_scope_diff_base()` zu durchlaufen — der hier eingeführte Guard wirkt dort nicht,
  weil der fehlerhafte Scope bereits vor Erreichen von `_scope_diff_base()` aus dem Cache
  zurückgegeben wird. Eine Vermischung beider Fixes würde denselben kritischen Code zweimal aus
  unterschiedlichen Blickwinkeln anfassen und den Zuschnitt aufweichen — RC2 bleibt eigenständiges
  Issue.
- Der neue Guard in `_scope_diff_base()` schützt nur den `preflight_base`-Zweig. Fällt die
  Funktion nach Selbstreferenz auf den `marker_sha`-Zweig zurück und zeigt AUCH dieser Marker
  fälschlich auf HEAD (z. B. durch RC2 aus #1640 verursacht), greift dessen bereits vorhandener
  `marker_sha != head`-Schutz und die Funktion fällt weiter auf `"HEAD~1"` zurück — das ist
  bestehendes, unverändertes Verhalten und kein Teil dieser Spec.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Isolierter Bugfix an einer bestehenden Bedingungsprüfung, spiegelt ein im selben
  Modul bereits etabliertes Muster (Selbstreferenz-Schutz im `marker_sha`-Zweig). Keine neue
  Entscheidungsfläche (Kanäle, Provider, Datenmodell, Auth, Editor-Paradigma, Test-/Deploy-Strategie)
  betroffen — die Deploy-Gate-Strategie selbst (Staging-Attestation vor Prod-Deploy) bleibt
  unverändert, es wird nur ein Klassifikationsfehler innerhalb dieser Strategie behoben.

## Changelog

- 2026-08-13: Initial spec created
