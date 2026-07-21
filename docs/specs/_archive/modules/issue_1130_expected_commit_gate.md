# Spec: staging_gate.py `--expected-commit`-Preflight (Issue #1130)

- **created:** 2026-07-08
- **status:** draft
- **issue:** henemm/gregor_zwanzig#1130 (Gegenstück: henemm-infra#107)

## Problem

`gate_check()` vergleicht `verified_commit == _head_sha()`. Deshalb muss `deploy-gregor-prod.sh` erst `git reset --hard origin/main` machen (damit `HEAD == Deploy-Commit`), bevor es das Gate aufrufen kann. Diese Reihenfolge erzwingt, dass der Dienst-Stop (`systemctl stop gregor-python`) und der Reset **vor** der Freigabe-Prüfung laufen → blockt eine Parallel-Session-Merge das Gate, ist der Dienst schon unten und Prod driftet (Vorfall 2026-07-08).

## Lösung

Ein optionaler Modus `--expected-commit <sha>`, mit dem der Gate-Check gegen einen **übergebenen Ziel-Commit** statt gegen `HEAD` prüft. Damit kann das Deploy-Script das Gate als **Preflight** aufrufen — vor jedem Stop/Reset. Bestehendes Verhalten (ohne Flag) bleibt byte-gleich.

Referenz-Commit `EXP` wird im Preflight konsistent verwendet:
- **Attestation:** `verified_commit == EXP`.
- **Scope-Skip:** Deploy-Änderungsumfang = Diff `HEAD..EXP` (was dieser Deploy ausrollt); `docs-only` → Exit 0 auch ohne Attestation.
- **Scope-Cache:** im Preflight-Modus **nicht** schreiben (HEAD≠EXP → falscher Key; der reguläre `--check` nach dem Reset schreibt korrekt).
- **Verdict-VERIFIED-Prüfung + Staleness (24h):** unverändert.

## Acceptance Criteria

**AC-1:** Given ein tmp-git-Repo, dessen `origin/main` auf Commit `EXP` zeigt und ein `e2e_verified.json` mit `verified_commit == EXP`, gültigem `VERIFIED`-Verdict und frischem `verified_at`, während der Arbeits-`HEAD` auf einem **älteren** Commit steht (Deploy noch nicht resettet) / When `staging_gate.py --check --expected-commit EXP` aufgerufen wird / Then ist der Exit-Code `0` (Gate bestanden), obwohl `HEAD != EXP`.

**AC-2:** Given dasselbe Repo, aber `e2e_verified.json` mit `verified_commit` = altem `HEAD` (also `!= EXP`) / When `staging_gate.py --check --expected-commit EXP` aufgerufen wird / Then ist der Exit-Code `1` und die Meldung nennt die Diskrepanz zwischen attestiertem Commit und `EXP` (nicht `HEAD`).

**AC-3:** Given ein Repo, in dem der Diff `HEAD..EXP` ausschließlich `docs/`-/`.md`-/`.claude/`-Dateien umfasst (docs-only) und **kein** passendes `e2e_verified.json` existiert / When `staging_gate.py --check --expected-commit EXP` aufgerufen wird / Then ist der Exit-Code `0` (docs-only-Skip greift gegen den Ziel-Commit, nicht gegen `HEAD`).

**AC-4:** Given einen bestehenden Aufruf ohne das neue Flag (`staging_gate.py --check`) in einem Repo, in dem `verified_commit == HEAD` und Verdict `VERIFIED` frisch ist / When der Check läuft / Then verhält er sich exakt wie vor der Änderung (Exit `0`, `write_last_gate_scope` wird mit `HEAD` geschrieben) — Rückwärtskompatibilität bewiesen durch weiterhin grüne Bestands-Tests in `tests/tdd/test_staging_gate.py`.

**AC-5:** Given ein `--check --expected-commit EXP`-Lauf mit `HEAD != EXP` / When der Check (egal ob Exit 0 oder 1) durchläuft / Then wird **kein** `last_gate_scope`-Markereintrag mit `HEAD` als Key geschrieben (kein Cache-Poisoning des noch nicht ausgerollten Zustands).

## Out of Scope
- Änderung an `deploy-gregor-prod.sh` (→ henemm-infra#107, separat).
- Änderung an `--write-verdict`, `--detect-scope`, `/e2e-verify`.
- Keine neue Staleness-/Scope-Semantik jenseits der Referenz-Commit-Umlenkung.

## Known Limitations
- Das Flag ändert **nur** die Referenz-Commit-Quelle. Ob das Deploy-Script es korrekt VOR Stop/Reset aufruft, ist Sache von henemm-infra#107 — diese Spec macht den Preflight nur *möglich*, nicht *verpflichtend*.
