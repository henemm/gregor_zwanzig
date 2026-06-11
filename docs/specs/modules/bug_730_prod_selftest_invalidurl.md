---
entity_id: bug_730_prod_selftest_invalidurl
type: module
created: 2026-06-11
updated: 2026-06-11
status: draft
version: "1.0"
tags: [bug, infra, tooling, prod-selftest, deploy]
---

# Bug #730 — prod_selftest.py crasht (InvalidURL) bei Findings ohne echte URL

## Approval

- [ ] Approved

## Purpose

Der Post-Deploy-Selbsttest (`prod_selftest.py`) darf nicht abstürzen, wenn ein
Attestation-Finding eine `url` trägt, die kein gefahrlos abrufbarer HTTP-Pfad ist
(Freitext mit Leerzeichen/Steuerzeichen, z.B. eine Backend-AC-Beschreibung
`/api/trips/{id} PUT/GET`). Solche Findings werden **übersprungen** statt das
ganze Script — und damit den legitimen Issue-Close — mit Exit 1 zu blockieren.

## Source

- **File:** `.claude/hooks/prod_selftest.py`
- **Identifier:** `_probe_ac` (Z. 114-141); neuer Helper `_is_probeable_url`

(Python-Tooling-Schicht: `.claude/hooks/` — kein Frontend, keine Go-API, kein
produktiver `src/`-Backend-Code. Deploy-Gate-Hook, läuft unter System-`python3`.)

## Estimated Scope

- **LoC:** ~25
- **Files:** 2 (`.claude/hooks/prod_selftest.py`, `tests/tdd/test_prod_selftest_730.py`)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `urllib` / `http.client` | stdlib | wirft `InvalidURL` (MRO: `HTTPException → Exception`, **nicht** `URLError`/`OSError`) bei Disallowed-Chars `[\x00-\x20\x7f]` |
| `_staging_to_prod_url` | intern | baut die zu probende Prod-URL aus der Finding-URL |
| `_derive_verdict` | intern | klassifiziert nach `finding["status"]`; Block nur bei `prod_status=="FAIL"` |

## Implementation Details

Root Cause: `_http_get` löst bei Leer-/Steuerzeichen in der URL `http.client.InvalidURL`
aus. Der `except (urllib.error.URLError, OSError)` in `_probe_ac` greift nicht (kein
Subtyp) → Exception propagiert → `list(pool.map(_probe_ac, findings))` re-raised sie →
Script-Exit 1, obwohl der Deploy erfolgreich war.

Fix — Validitäts-Gate vor dem HTTP-Probe:

```python
import re
# Mirror von http.client: Steuerzeichen 0x00-0x20 (inkl. Space) und 0x7f (DEL)
_DISALLOWED_URL_CHARS = re.compile(r"[\x00-\x20\x7f]")

def _is_probeable_url(url: str) -> bool:
    """True nur wenn die URL gefahrlos per HTTP-GET probebar ist.
    Findings tragen teils Freitext (z.B. '/api/trips/{id} PUT/GET') statt echter
    Pfade — urllib würde dann InvalidURL werfen. Solche URLs sind nicht probebar."""
    if not url or _DISALLOWED_URL_CHARS.search(url):
        return False
    parsed = urlparse(url)
    return bool(parsed.scheme in ("http", "https") and parsed.netloc
                and parsed.path.startswith("/"))

# in _probe_ac, nach prod_url = _staging_to_prod_url(...):
if not _is_probeable_url(prod_url):
    return {**finding, "prod_url": prod_url, "prod_http": "—",
            "prod_status": "SKIPPED_NO_URL"}
```

Defense-in-depth: `http.client.InvalidURL` (bzw. `ValueError`) zusätzlich in den
`except` von `_probe_ac` aufnehmen, falls eine URL die Prüfung passiert, urllib aber
dennoch ablehnt → dann `prod_status="FAIL"` mit Fehlertext (kein Crash).

Verdict-Semantik: `SKIPPED_NO_URL` ist **kein** `FAIL` → `_derive_verdict` blockt nicht.
Eine PASS-Finding ohne probebare URL führt damit weder zu PARTIAL noch FAIL.

## Expected Behavior

- **Input:** `e2e_verified/<HEAD>.json` mit Findings, von denen mind. eines eine
  nicht-probebare `url` trägt (Leerzeichen/Steuerzeichen, kein `http(s)://…/<pfad>`).
- **Output:** Exit 0 (sofern Commit/Health ok und keine echte AC-Regression); Bericht
  listet die nicht-probebare Finding mit `prod_status=SKIPPED_NO_URL`.
- **Side effects:** keine (best-effort Report-Schreibung wie bisher).

## Acceptance Criteria

- **AC-1:** Given eine Attestation für HEAD mit einer `status=PASS`-Finding, deren `url`
  ein Leerzeichen enthält (z.B. `/api/trips/{id} PUT/GET`) / When `prod_selftest.py`
  läuft (Commit==HEAD, Health ok) / Then das Script crasht **nicht**, endet mit Exit 0,
  und kein `InvalidURL`-Traceback erscheint auf stderr.
  - Test: Subprozess-Lauf des echten Scripts (mock-frei) gegen echtes Prod mit
    `verified_commit=$(git rev-parse HEAD)`; Assertion `rc == 0` und `"InvalidURL"`
    bzw. `"Traceback"` **nicht** in stderr.

- **AC-2:** Given eine Attestation mit zwei `status=PASS`-Findings — eine echte erreichbare
  Prod-URL (`https://staging…/:AC-1`) und eine nicht-probebare Freitext-URL / When der
  Selftest läuft / Then das Verdict ist **PASS** (Exit 0); die nicht-probebare Finding
  erzeugt weder PARTIAL noch FAIL.
  - Test: Subprozess-Lauf, Assertion `rc == 0` und Report enthält **kein** `Verdict: PARTIAL`
    und **kein** `Verdict: FAIL`.

- **AC-3:** Given eine nicht-probebare PASS-Finding / When der Selftest den Bericht schreibt
  / Then die Finding erscheint in der AC-Tabelle des Berichts mit einem erkennbaren
  Skip-Marker (`SKIPPED_NO_URL`) — sie wird nicht still verworfen.
  - Test: Subprozess-Lauf, Bericht `docs/artifacts/<workflow>/prod-selftest.md` einlesen,
    Assertion `"SKIPPED_NO_URL"` in der Tabelle.

- **AC-4:** Given eine valide, probebare `status=PASS`-Finding, deren Prod-URL 404 liefert
  (bestehendes Regressions-Szenario) / When der Selftest läuft / Then bleibt das bisherige
  Verhalten unverändert: Verdict **PARTIAL**, Exit 1.
  - Test: Subprozess-Lauf mit einer 404-Route, Assertion `rc == 1` und `"PARTIAL"` im
    Bericht (schützt vor Über-Generalisierung des SKIP-Pfads).

## Changelog

- 2026-06-11: Initial-Spec für Bug #730 (prod_selftest InvalidURL-Crash → SKIP statt Crash).
