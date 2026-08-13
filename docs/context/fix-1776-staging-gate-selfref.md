# Bug-Analyse #1776: staging_gate.py Selbstreferenz bei preflight_base

**Status:** Analyse abgeschlossen  
**Datum:** 2026-08-13  
**Workflow:** `fix-1776-staging-gate-selfref`  
**Live-Vorfälle:** 6 dokumentiert (zuletzt 2026-08-13, Deploy #1533 S4/PR #1803)

## Symptom

`staging_gate.py --check` klassifiziert manche Commits mit Produktivcode fälschlich als `docs-only` ("nur Dokumentation, kein Code"). Bei dieser Klassifikation springt das Gate mit `return 0` direkt durch — **ohne jede Staging-Attestations-Prüfung**. Die Folge: Code landet in Produktion ohne Nachweis eines bestandenen Staging-Tests.

**Beispiel aus #1725 (2026-08-12, Merge-Commit `414b0b87`):**
- `git diff --name-only HEAD~1..HEAD` zeigt: `src/services/briefing_slots.py`, `src/services/dispatch_orchestrator.py`, `src/services/trip_report_scheduler.py`
- `staging_gate.py --detect-scope` meldet: `docs-only`
- `gate_check()` Zeile 559: `if scope == "docs-only": return 0` (Early Exit, keine Attestations-Prüfung)

## Root Cause

Zwei verschiedene Fehler-Pfade führen zum gleichen Fehler; beide sind dokumentiert und verifiziert.

### RC 1: Fehlende Selbstreferenz-Prüfung im `preflight_base`-Zweig (Hauptbefund #1776)

**Datei:** `.claude/hooks/staging_gate.py`, Funktion `_scope_diff_base()`, Zeilen 158–161

```python
# Fehler-Code (aktuell):
preflight_base = _e2e_paths.read_preflight_base(_shared_repo_dir(), head)
if preflight_base is not None:
    if _e2e_paths.commit_exists(preflight_base, _verified_repo_dir()):
        return preflight_base                             # ← FEHLER: keine Prüfung auf preflight_base == head
```

**Vergleich mit `marker_sha`-Zweig (Zeile 163–166), der die Prüfung HAT:**

```python
marker_sha = _e2e_paths.read_last_gate_scope(_shared_repo_dir())
if marker_sha and marker_sha != head:                   # ← Korrekt: Selbstreferenz-Schutz
    if _e2e_paths.commit_exists(marker_sha, _verified_repo_dir()):
        return marker_sha
return "HEAD~1"
```

**Mechanismus:**

1. `write_preflight_base()` (`.claude/hooks/_e2e_paths.py`, Zeile 135–152) speichert `{"target_sha": <head>, "base_sha": <basis>}` ab
2. Bei einem Merge kurz nach dem Preflight kann `base_sha == target_sha` werden (Selbstreferenz)
3. `_scope_diff_base()` liest diese Basis, prüft sie NICHT auf Selbstreferenz
4. `_detect_committed_scope()` führt `git diff HEAD..HEAD` aus → leer → `docs-only` fälschlich
5. `gate_check()` Zeile 559 springt durch: `if scope == "docs-only": return 0`

### RC 2: Marker wird mit `docs-only` auf HEAD geschrieben (Sekundär-Pfad, Issue #1640)

**Datei:** `.claude/hooks/staging_gate.py`, Zeile 568–569

```python
# Nach einem fehlerhaften docs-only-Durchlauf:
existing = _e2e_paths.cached_scope_for_sha(_shared_repo_dir(), _head_sha())
if existing is None or existing == "docs-only":
    _e2e_paths.write_last_gate_scope(_shared_repo_dir(), _head_sha(), scope)  # ← Marker auf HEAD mit scope=docs-only
```

**Problem:**
- Der Marker wird mit `gate_scope_sha == head` geschrieben (normalerweise nur bei Erfolgsfall), hier aber mit `scope=docs-only`
- Ein zweiter `staging_gate.py`-Lauf (z.B. bei Nachträgen oder Wiederholungen, #1592 C3 gemessen) liest diesen Marker
- `_scope_diff_base()` Zeile 164 prüft `marker_sha != head` — der Marker zeigt aber auf HEAD
- Fallback zu `HEAD~1` würde greifen, ABER: Zeile 668–670 in `prod_selftest.py` nutzt den gecachten Scope direkt — ein zweiter Lauf auf `prod_selftest` kann hier keine neuen Tests fahren

## Betroffene Dateien & Aufrufer

| Datei | Funktion | Zeile | Kontext |
|-------|----------|-------|---------|
| `.claude/hooks/staging_gate.py` | `_scope_diff_base()` | 158–161 | Liest `preflight_base` ohne Selbstreferenz-Schutz |
| `.claude/hooks/staging_gate.py` | `_detect_committed_scope()` | 198 | Ruft `_scope_diff_base(head)` auf (Benutzer von RC 1) |
| `.claude/hooks/staging_gate.py` | `gate_check()` | 559–569 | Springt durch bei `docs-only`, schreibt Marker mit `docs-only` (RC 2) |
| `.claude/hooks/_e2e_paths.py` | `read_preflight_base()` | 155–169 | Keine Selbstreferenz-Prüfung; gibt `base_sha` auch wenn `== target_sha` |
| `.claude/hooks/_e2e_paths.py` | `write_preflight_base()` | 135–152 | Speichert ab, auch wenn `base_sha == target_sha` |
| `.claude/hooks/prod_selftest.py` | `_scope_diff_base()` | 648 | **HAT** die `marker_sha != head`-Prüfung (korrekt) |
| `.claude/hooks/prod_selftest.py` | `_detect_committed_scope()` | 668–670 | Nutzt gecachten Scope direkt (RC 2 relevant) |

## Tests & Aufrufer-Aufzählung

**Tests, die `_scope_diff_base()` oder Preflight-Basis testen (vorhandene Test-Abdeckung):**

```
tests/tdd/test_fix_1428_preflight_scope_base.py:118  # test_scope_diff_base_prefers_preflight_hint_over_marker
tests/tdd/test_fix_1428_preflight_scope_base.py:140  # test_scope_diff_base_ignores_hint_for_wrong_target
tests/tdd/test_e2e_path_helper.py:301–319           # (Mehrere Aufrufe auf _scope_diff_base())
tests/tdd/test_prod_selftest_scope_diff_base.py     # Prod-Selftest-Variante (hat den Selbstreferenz-Schutz)
tests/tdd/test_issue_1109_prod_deploy_marker.py     # Prod-Deploy-Marker-Tests
tests/tdd/test_issue_668_head_sha_dedup.py          # Subprozess-Deduplizierung
```

## Geschätzter Aufwand

| Komponente | LoC/Änderung | Aufwand |
|-----------|---|---|
| **Fix RC 1** | `staging_gate.py:160` Bedingung `preflight_base != head` hinzufügen | +1 Zeile |
| **Fix RC 2** | `staging_gate.py:568` – Marker-Herabstufung verhindern | +3–5 Zeilen |
| **Tests (neu)** | 2 neue Testfunktionen, Fixtures | ~50–80 LoC |
| **Regression-Tests** | Bestehende Tests in `test_fix_1428_preflight_scope_base.py` | 0 (bereits vorhanden) |
| **Dokumentation** | Docstring-Aktualisierung | +5 Zeilen |

**Gesamt:** Klein (Hauptdatei: `.claude/hooks/staging_gate.py`)  
**Risiko:** Niedrig (isolierte Bedingungen-Prüfung)

## Unterschied zu Issue #1640

| Aspekt | #1776 | #1640 |
|--------|-------|-------|
| **Hauptursache** | Fehlende Prüfung im preflight-Zweig | Marker wird mit `docs-only` auf HEAD geschrieben |
| **Betroffen ist** | `_scope_diff_base()` Zeile 158–161 | `gate_check()` Zeile 568–569 |
| **Symptom** | Erste Runde gibt `docs-only` zurück | Zweite Runde stellt fest, dass Marker auf HEAD zeigt |
| **Gemeinsam** | Beide führen zu fälschlichem `docs-only` und Durchlassung |
| **Reparatur** | Getrennte Fixes, aber interdependent |

## Nächste Schritte (Implementierungs-Phase)

1. **Spec schreiben** (`/30-write-spec`): ACs für RC1
2. **TDD RED** (`/40-tdd-red`): Tests schreiben, rot laufen
3. **Implementierung** (`/50-implement`): RC1-Fix
4. **Adversary Verification** (automatisch): Mutation-Test aller geänderten Zeilen

## Analysis

### Type
Bug

### Scope-Entscheidung (PO-relevant, vor Spec zu bestätigen)

Der Bug-Intake-Report oben nennt zwei Root Causes (RC1, RC2). **Nur RC1 ist Gegenstand dieses
Fixes.** RC2 (Marker wird nach einem `docs-only`-Lauf mit `docs-only` auf HEAD geschrieben, ein
zweiter Lauf nutzt den gecachten Wert weiter) überschneidet sich mit dem separat offenen Issue
#1640 und wird dort behandelt, nicht hier — Vermischung würde denselben kritischen Code
zweimal aus unterschiedlichen Blickwinkeln anfassen und den engen, klar belegten Zuschnitt von
#1776 aufweichen. Offene Frage laut Plan-Bewertung: RC1s Fallback-Kette (`marker_sha`) würde
einen durch RC2 fälschlich gesetzten Marker weiterhin konsumieren — das ist eine Abgrenzungsfrage
für die Spec-Phase, keine Entscheidung, die hier vorweggenommen wird.

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|--------------|
| `.claude/hooks/staging_gate.py` | MODIFY | `_scope_diff_base()` Zeile 158–161: Selbstreferenz-Guard `preflight_base != head` ergänzen (analog `marker_sha`-Zweig Zeile 164) |
| `tests/tdd/test_fix_1428_preflight_scope_base.py` | MODIFY | 1–2 neue Testfunktionen: Selbstreferenz-Szenario (`base_sha == target_sha`) erzeugen, Fallback auf Marker/`HEAD~1` erwarten statt Selbstreferenz-Rückgabe |

### Scope Assessment
- Files: 2
- Estimated LoC: +1 (Fix) / +30–40 (Tests) — 0 Löschungen
- Risk Level: LOW (isolierte, symmetrische Bedingungsergänzung; kein legitimer Fall gefunden, in dem die Selbstreferenz gewollt ist)

### Technical Approach
Guard beim Konsum ergänzen, nicht bei der Schreib-/Lesehilfsfunktion:
`if preflight_base is not None and preflight_base != head:` in `_scope_diff_base()`. Spiegelt
exakt das bestehende Muster des direkt folgenden `marker_sha`-Zweigs. `prod_selftest.py` ist
unbetroffen (konsumiert `preflight_base` nicht, sein eigener `marker_sha`-Schutz ist bereits
korrekt).

Pflicht-Test für die Mutations-Gegenprobe (dieses Projekt verlangt das): ein Test, der
`write_preflight_base(repo, target, base=target)` (Selbstreferenz) setzt, `_scope_diff_base()`
mit `head=target` aufruft und ein Ergebnis `!= target` erwartet. Entfernt man die Bedingung
wieder, liefert die Funktion `target` zurück → Test wird rot. Zusätzlich bestehenden Test
`test_regular_check_after_reset_agrees_with_preflight_docs_only` als Regressionscheck laufen
lassen.

### Dependencies
Keine. Unabhängig von `prod_selftest.py` und von #1640 (RC2, bewusst nicht mitgezogen, siehe
Scope-Entscheidung oben).

### Open Questions
- [ ] Deckt der neue Test die drei real beobachteten Vorfälle (#1725, #1803, und der ursprüngliche
      #1776-Befund) strukturell ab, oder braucht es zusätzlich einen Test je Vorfall? (Vermutlich
      genügt der eine strukturelle Test — die drei Vorfälle sind dieselbe Ursache.)
- [ ] Soll die Spec RC1s Wechselwirkung mit dem (separat zu fixenden) RC2 aus #1640 als
      Nicht-Ziel explizit ausschließen, damit der Adversary später nicht versehentlich RC2 mit
      hineinzieht?
