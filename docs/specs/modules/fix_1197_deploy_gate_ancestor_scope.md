# Spec: Deploy-Gate Ancestor+docs-only-Relaxierung (staging_gate.gate_check)

- **Issue:** #1197 (Sammel-Gate-Audit), Scheibe „strikte-Gleichheits-Gate blockt gestapelten Tooling-Commit"
- **Created:** 2026-07-16
- **Typ:** Gate-Fix (Kategorie c — fälschlich blockierender Prod-Hard-Gate)
- **ADR-Nr.:** keine
- **Datei:** `.claude/hooks/staging_gate.py` (`gate_check`, ~Z.272-380)
- **Prüfdatum (Regel-Budget):** 2026-10-14

## Problem

`gate_check` blockt strikt bei `verified_commit != HEAD`. Ein docs-/tooling-only-
Commit über einem verifizierten Produktcommit ändert HEAD → Block, obwohl der
Code-Inhalt unverändert-verifiziert ist. Zusätzlich findet die Attestations-
Auflösung den nächsten verifizierten Ancestor nicht (nur exakt-HEAD oder Singleton).

## Lösung

(A) Fehlt `<HEAD>.json`, den nächsten VERIFIED, nicht-stalen Ancestor mit
commit-getaggter Attestation als Basis auflösen. (B) Ist die Basis ≠ HEAD, nur
durchlassen, wenn HEAD Nachfahre der Basis ist UND der Zuwachs Basis..HEAD
`docs-only` ist. Sonst Block (fail-closed).

## Acceptance Criteria

**AC-1:** Given `<HEAD>.json` existiert und ist VERIFIED mit `verified_commit ==
HEAD`, When `gate_check` läuft, Then Exit 0 (unverändertes Verhalten, exakte
Übereinstimmung).

**AC-2:** Given es existiert KEINE `<HEAD>.json`, aber ein Ancestor C von HEAD hat
`<C>.json` (VERIFIED, nicht stale), und der Zuwachs C..HEAD enthält ausschließlich
Doku/Tooling/Tests (Scope docs-only), When `gate_check` läuft, Then Exit 0 und ein
Log weist die Ancestor-Relaxierung aus.

**AC-3:** Given dieselbe Ancestor-Konstellation, aber der Zuwachs C..HEAD enthält
mindestens eine Datei unter `frontend/`, When `gate_check` läuft, Then Exit 1
(keine Relaxierung bei echtem Frontend-Code).

**AC-4:** Given dieselbe Ancestor-Konstellation, aber der Zuwachs C..HEAD enthält
mindestens eine Datei unter `src/`, `api/`, `internal/` oder `cmd/`, When
`gate_check` läuft, Then Exit 1 (keine Relaxierung bei echtem Backend-Code).

**AC-5:** Given HEAD ist KEIN Nachfahre irgendeiner verifizierten Attestation
(divergenter/unverwandter Commit), When `gate_check` läuft, Then Exit 1.

**AC-6:** Given der nächste Ancestor mit Attestation trägt ein Verdict, das NICHT
mit "VERIFIED" beginnt (z.B. leer/BROKEN), When `gate_check` läuft, Then wird diese
Attestation NICHT als Basis akzeptiert und der Gate blockt (Exit 1), sofern keine
andere gültige Basis == HEAD existiert.

**AC-7:** Given die als Basis aufgelöste Ancestor-Attestation ist älter als die
Staleness-Grenze, When `gate_check` läuft, Then Exit 1 (Staleness gilt auch für die
Ancestor-Basis).

**AC-8:** Given die Scope-Ermittlung des Zuwachses scheitert (git-Fehler,
nicht auflösbar), When `gate_check` läuft, Then wird NICHT relaxiert → Exit 1
(fail-closed; `_detect_scope_from_git_diff` liefert bei Fehler "backend").

**AC-9:** Given `GZ_SKIP_E2E_GATE=1`, When `gate_check` läuft, Then Exit 0 wie
bisher (Notfall-Override unverändert, keine Interaktion mit der neuen Logik).

## Known Limitations

- Die Ancestor-Auflösung lebt lokal in `staging_gate`; `prod_selftest` erhält
  keine analoge Findings-Ancestor-Auflösung (separater Bedarf).
- Der Ancestor-Walk ist auf eine feste Obergrenze an Commits begrenzt; ein
  verifizierter Ancestor jenseits dieser Grenze führt zu Block (fail-closed, kein
  Fehlverhalten).

## Test-Politik

Kern-Schicht, deterministisch: ein echtes temporäres Git-Repo (`git init`,
`git commit`) mit echten commit-getaggten Attestations-Dateien; `gate_check` wird
gegen dieses Repo ausgeführt (kein Netz, kein Mock der Git-Logik). Scope wird über
echte Dateipfade in echten Commits erzeugt. Neue Datei
`tests/tdd/test_staging_gate_ancestor_scope.py`.
