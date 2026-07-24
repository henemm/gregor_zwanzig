---
entity_id: fix_1353_selftest_auth_redirect
type: module
created: 2026-07-24
updated: 2026-07-24
status: draft
version: "1.0"
tags: [gate, deploy, selftest, honesty]
---

# Fix #1353 — Post-Deploy-Selbsttest: 302-auf-Login nicht mehr blind als PASS

## Approval

- [ ] Approved

## Purpose

Der Post-Deploy-Selbsttest (`prod_selftest.py`) wertet aktuell **jeden** HTTP-302-Redirect als „PASS". Da geschützte Endpoints unauthentifiziert mit `302 → /login` antworten, besteht ein Endpoint den Test, ohne dass sein Akzeptanzkriterium je geprüft wurde. Weil der Issue-Close an „Selftest Exit 0" hängt, kann ein Issue geschlossen werden, obwohl in Prod nur die Anmelde-Schranke gesehen wurde. Dieser Fix macht den Selbsttest ehrlich: Ein Redirect auf die Anmeldeseite wird als „strukturell nicht prüfbar" ausgewiesen statt als bestanden.

## Source

- **File:** `.claude/hooks/prod_selftest.py`
- **Identifier:** `_http_get` (Location durchreichen), `_probe_ac` (Statusklassifikation, Zeile 283)

## Estimated Scope

- **LoC:** ~+40 / -3 (Kern-Datei), Test separat
- **Files:** 1 Quelldatei + 1 Testdatei
- **Effort:** low–medium (kleiner Diff, aber Deploy-Gate = kritischer Pfad)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `e2e_verified.json` → `findings[].url` | Datenquelle | Liefert die pro-AC geprüften URLs |
| `frontend/src/hooks.server.ts:21` | Referenz | Auth-Guard leitet unauth mit `redirect(302, '/login')` um — definiert das Redirect-Ziel `/login` |
| `_derive_verdict` (`prod_selftest.py:444-458`) | unverändert | Zählt nur `prod_status == "FAIL"` als PARTIAL; `SKIPPED_*` blockiert PASS nicht |
| Deploy-Schritt 4b (`CLAUDE.md:230`) | Konsument | Exit 0 = einzige Freigabe für `gh issue close` |

## Implementation Details

```
1. _http_get: Rückgabe um das Redirect-Ziel erweitern → (status, body, location).
   - Erfolgsfall (2xx): location = "" (kein Redirect).
   - Abgefangener HTTPError (3xx/4xx/5xx): location = exc.headers.get("Location", "").
   - Alle Aufrufer anpassen: _check_health (follow_redirects=True) + _probe_ac.

2. Login-Redirect-Erkennung (Hilfsfunktion): Ein Redirect zeigt auf die Anmeldeseite,
   wenn der Location-Pfad == "/login" ist oder mit "/login" beginnt (robust gegen
   absolute URL, relative URL und Query-String — via urlparse den Pfad extrahieren).

3. _probe_ac (ersetzt `ok = status in (200, 302)`):
   - status == 200                              → prod_status = "PASS"
   - status ∈ {301,302,303,307,308} UND Ziel == Anmeldeseite → "SKIPPED_AUTH_REDIRECT"
   - status ∈ {301,302,303,307,308} UND Ziel != Anmeldeseite → "PASS" (echter Redirect)
   - sonst (401/403/404/5xx …)                   → "FAIL" (bestehende Semantik)

4. _derive_verdict: EINE zusätzliche Fallunterscheidung (Korrektur v1.1, s. Changelog).
   - Bestehende Logik bleibt: SKIPPED_* löst kein FAIL/PARTIAL aus.
   - NEU: Ergaben ALLE geprobten Findings `prod_status == "SKIPPED_AUTH_REDIRECT"`
     (also kein einziger echter inhaltlicher Nachweis), lautet der Gesamt-Verdict
     NICHT "PASS", sondern "SKIPPED_AUTH_REDIRECT".
   - run_selftest: dieser Verdict gehört in die Exit-0-Menge (kein Deploy-Block),
     analog zu "SKIPPED_ALL".
   Begründung: _derive_verdict bildet `pass_probes` über das STAGING-Feld `status`,
   nicht über `prod_status`. Ohne diesen Zweig bliebe die Gesamt-Note "PASS", obwohl
   in Prod ausschliesslich die Anmelde-Schranke gesehen wurde — exakt der Kern des Bugs
   (AC-5). Der Zeilen-Status allein (Punkt 3) genügt dafür nicht.

5. Rückwärtskompatibilität der _http_get-Signatur: Bestehende Tests monkeypatchen
   `_http_get` mit einem Zwei-Tupel `(status, body)` (z. B.
   tests/tdd/test_prod_selftest_internal_url_skip.py). Die Aufrufstellen müssen
   Zwei- UND Drei-Tupel akzeptieren (Normalisierung an der Aufrufstelle), damit
   bestehende grüne Tests nicht brechen — ohne diese Testdateien zu ändern.
```

## Expected Behavior

- **Input:** Ein AC-Finding mit einer Prod-URL; die HTTP-Antwort dieser URL (Status + Location-Header).
- **Output:** `prod_status` ∈ {PASS, FAIL, SKIPPED_AUTH_REDIRECT, bestehende SKIPPED_*}.
- **Side effects:** keine (reiner Lese-Probe-Pfad; kein State, keine Netz-Schreibvorgänge).

## Acceptance Criteria

- **AC-1:** Given ein AC-Finding, dessen Prod-URL unauthentifiziert mit `302 → /login` antwortet / When der Selbsttest dieses Finding probt / Then ist das Ergebnis `prod_status = "SKIPPED_AUTH_REDIRECT"` und **nicht** `PASS`.
  - Test: Lokaler HTTP-Server antwortet auf die Probe mit `302` und `Location: /login`; die Probe-Funktion liefert `SKIPPED_AUTH_REDIRECT`.

- **AC-2:** Given ein AC-Finding, dessen URL mit `302` auf ein Ziel **ungleich** der Anmeldeseite umleitet (echter inhaltlicher Redirect) / When der Selbsttest es probt / Then bleibt das Ergebnis `PASS`.
  - Test: Lokaler Server liefert `302` mit `Location: /app`; die Probe liefert `PASS`.

- **AC-3:** Given ein AC-Finding, dessen URL mit `200` antwortet / When geprobt / Then ist das Ergebnis `PASS` (unveränderter Regressions-Anker).
  - Test: Lokaler Server liefert `200`; Probe liefert `PASS`.

- **AC-4:** Given ein AC-Finding auf einer öffentlichen URL, die mit `401` antwortet / When geprobt / Then bleibt das Ergebnis `FAIL` (bestehender Anker aus #1197 — Auth-Wall ohne Redirect ist weiterhin ein Fehler).
  - Test: Lokaler Server liefert `401`; Probe liefert `FAIL`.

- **AC-5:** Given alle geprüften Findings ergeben `SKIPPED_AUTH_REDIRECT` / When `run_selftest` den Gesamt-Verdict bildet / Then ist der Exit-Code `0` (kein Deploy-Block), aber der Verdict lautet **nicht** `PASS`, sondern spiegelt den Skip wider, und der Report zeigt `SKIPPED_AUTH_REDIRECT` je Zeile (keine vorgetäuschte Prüfung).
  - Test: Findings-Satz mit ausschließlich Login-Redirects → Exit 0, Verdict ≠ „PASS", Report enthält `SKIPPED_AUTH_REDIRECT`.

## Known Limitations

- Der Selbsttest läuft unauthentifiziert; er kann den *inhaltlichen* AC-Beweis für geschützte Endpoints grundsätzlich nicht erbringen. Nach dem Fix weist er das ehrlich als `SKIPPED_AUTH_REDIRECT` aus, statt es vorzutäuschen. Der echte AC-Beweis bleibt Aufgabe der vorgelagerten Staging-E2E-Verifikation; das „lebt Prod?"-Signal liefert der separate Health-Check (`/api/health`).
- Die Login-Erkennung ist an den Pfad `/login` gebunden (aktueller App-Auth-Guard, `hooks.server.ts:21`). Ändert sich die Login-Route, muss die Konstante nachgezogen werden.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Keine neue Grundsatzentscheidung — der Fix folgt exakt dem bestehenden Muster „strukturell nicht prüfbare Antwort → eigener `SKIPPED_*`-Status" (Präzedenz: `SKIPPED_METHOD_NOT_PROBEABLE` für 405, `prod_selftest.py:276-282`). Die gewählte Modellierung (SKIPPED statt FAIL für Auth-Redirects) ist Tech-Lead-Entscheidung unter PO-Mandat und in „Known Limitations" begründet.

## Changelog

- 2026-07-24: Initial spec created (#1353)
- 2026-07-24 (v1.1, PO-bestätigt): Korrektur der Implementation Details. Punkt 4 sagte
  faelschlich „_derive_verdict: unveraendert" — in der RED-Phase aufgedeckt: die
  Gesamt-Note wird aus dem Staging-Feld `status` gebildet und bliebe „PASS", obwohl in
  Prod nur die Anmelde-Schranke gesehen wurde (AC-5 waere unerfuellbar). Punkt 4 praezisiert
  auf EINEN zusaetzlichen Zweig (alle Probes SKIPPED_AUTH_REDIRECT → Verdict
  SKIPPED_AUTH_REDIRECT, Exit 0). Punkt 5 ergaenzt: _http_get-Signaturwechsel muss
  Zwei-Tupel-Monkeypatches bestehender Tests weiter tragen. ACs unveraendert.
