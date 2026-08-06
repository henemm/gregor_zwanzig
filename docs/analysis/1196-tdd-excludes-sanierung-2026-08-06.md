# #1196 TDD-Exclude-Sanierung — Nachvermessung 2026-08-06 und Restplan

**Stand:** 2026-08-06 · **Datenbasis:** Offline-Vollvermessung aller 48 Exclude-Dateien
unter exakten CI-Bedingungen (`--disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,::1,localhost`,
Marker-Filter `not email and not live and not staging` aus `pyproject.toml`)

## Warum es dieses Dokument gibt

`.github/ci_tdd_excludes.txt` ist die Ratschen-Liste offline-roter `tests/tdd/`-Dateien
(#1196, PR #1497): Sie darf nur schrumpfen, jeder Eintrag ist eine Sanierungsbaustelle.
Die Liste stammte aus der Vermessung 2026-08-04 (469 rote Tests). Diese Nachvermessung
zeigt: **Der Bestand hat sich seither stark verbessert — die Liste war zu 75 % überholt.**
Dieses Dokument belegt die Entfernung der 36 überholten Einträge und legt für die
verbleibenden 12 Dateien Ursache und Sanierungsweg fest.

## Ergebnis vorweg

- **48 → 14 Dateien.** 34 Einträge laufen offline grün (oder werden per Marker
  `live`/`email` ohnehin deselektiert) und wurden aus der Liste entfernt. Der CI-Lauf
  des zugehörigen PRs ist der verbindliche Beleg — läuft eine entfernte Datei auf dem
  Runner doch rot (Host-Abhängigkeit), ist das ein Ein-Zeilen-Revert.
- **38 rote Tests in 14 Dateien** sind der reale Restbestand (Vermessung 2026-08-04: 469).
- **24 der 38 Fehler** sitzen in einer einzigen Datei (`test_epic_140_preview_endpoints.py`)
  und haben eine einzige, mechanisch behebbare Ursache (fehlende Daten-Isolation, #1133).
- **Messumgebung entscheidet:** Die 12 „fachlich roten" Dateien sind in beiden Umgebungen
  rot. `test_622`/`test_952` sind nur im frischen Checkout **ohne `.env`** rot (CI-ähnlich),
  im Haupt-Checkout mit `.env` grün → host-abhängig, bleiben vorerst excludiert.
- **Test-Pollution beobachtet:** `test_issue_1014_live_optin` (nie excludiert) fällt nur
  im Volllauf um, wenn bestimmte re-aktivierte Dateien mitlaufen (Env-Mutation ohne
  Aufräumen) — isoliert grün. Das ist die in `fix_1196_s1_testnetz_entrauschen.md`
  beschriebene Baustelle und grenzt ein, welche Re-Aktivierungen sofort ungefährlich sind.

## Die 14 verbleibenden Dateien nach Ursache

| Datei | Fehler | Grundursache (Beleg) | Sanierungsweg |
|---|---|---|---|
| `test_622_fidelity_pre_actions.py` | 2 | Rot nur ohne `.env`/im frischen Checkout (Trio-Lauf im Worktree rot, im Haupt-Checkout grün) — host-/umgebungsabhängig | Test von Host-Umgebung entkoppeln (Pfade/Env über Fixtures statt Implizitem). |
| `test_952_onset_alert_fidelity.py` | 2–3 | Wie 622: umgebungsabhängig rot ohne `.env`; zusätzlich Verdacht, Env zu mutieren (Pollution von `test_issue_1014_live_optin` im Volllauf) | Env-Zugriffe über `monkeypatch` kapseln + Host-Entkopplung. |
| `test_epic_140_preview_endpoints.py` | 24 | Schreibt in echten `data/users/`-Baum → `PermissionError` durch #1133-Isolation | Fixtures auf tmp-data-root umstellen (Muster: andere tdd-Dateien mit Isolation). **Größter Hebel, mechanisch.** |
| `test_compare_metric_catalog_endpoint.py` | 1 | Katalog liefert 4 Thunder-Labels `['kein','lei..','mittel','hoch']`, Test erwartet 3 ordinale | Fachliche Entscheidung (3 vs. 4 Stufen), dann Test **oder** Katalog angleichen. Siehe `test_day_comparison_service`. |
| `test_day_comparison_service.py` | 2 | Thunder-Ordinal-Scoring driftet (`assert 2.0 == 1`, `assert -3.0 == -2`) | Gleiche Entscheidung wie Katalog-Datei — **als ein Batch bearbeiten.** |
| `test_trip_report_test_send_past_stage_clamp.py` | 2 | Erwartet ehrliches `no_weather`/HTTP 422, Code liefert `sent`/200 | **Priorität: möglicher echter Produkt-Bug** (unehrlicher Versand-Status), kein reines Testproblem. Zuerst fachlich klären. |
| `test_feature_656_radar_nowcast.py` | 1 | Throttle-Test `assert 0 == 1` (Alert wird nicht wie erwartet gedrosselt) | Diagnose: Throttle-Persistenz/State im Test-Setup. |
| `test_feature_660_convective_stage.py` | 1 | Wie 656 (`assert 0 == 1`, Throttle) | Gleiche Diagnose — **als ein Batch mit 656.** |
| `test_bundle_e_gate_tooling.py` | 1 | Test verbindet auf externe IP `178.104.143.19` → Socket-Block (per Bauart) | Gate-Aufruf mocken oder Test als `staging`-markiert aus dem Kern nehmen. |
| `test_issue_586_alert_config_fidelity.py` | 3 | Braucht Live-Screenshots von Staging + Gate-Artefakte unter `docs/artifacts/` | Artefakt-Test, kein Kern-Test: dauerhaft excludiert lassen **oder** nach `tests/` außerhalb des CI-Pfads verschieben (mit Begründung hier dokumentieren). |
| `test_issue_603_design_fidelity_gate.py` | 1 | Host-/artefakt-abhängig (Diff-Tool-Exit vs. `passed`-Feld), lokal nicht reproduzierbar grün | Wie 586: Artefakt-/Staging-Test, kein Kern-Kandidat. |
| `test_issue_833_gate.py` | 1 Error | Fehler im Test-Setup (parametrisierter Defekt-Fall `_defect_sonne`), kein Assertion-Failure | Setup reparieren (Diagnose beim Abarbeiten, vermutlich klein). |
| `test_issue_1165_adr_index_cleanup.py` | 1 | Wächter schlägt an, weil `docs/specs/modules/fix_1196_s1_testnetz_entrauschen.md` den alten ADR-Dateinamen `0013-...` referenziert | Trivial: Verweis in der Spec-Datei korrigieren. **Quick Win.** |
| `test_pytest_collection_and_timeout_safety.py` | 1 | Meta-Wächter: `test_issue_684_alert_email_guard.py` habe „0 Rest-Tests im Standardlauf" | Wächter-Regel gegen Ist-Stand von test_issue_684 prüfen und angleichen. |

## Sanierungsreihenfolge (Batches)

1. **Batch 1 — Quick Wins (1/2 Tag):** `test_issue_1165` (Doku-Verweis), `test_issue_833_gate` (Setup-Error).
2. **Batch 2 — Thunder-Ordinal (fachliche Entscheidung nötig):** `test_compare_metric_catalog_endpoint` + `test_day_comparison_service`.
3. **Batch 3 — Epic 140 (größter Hebel):** Daten-Isolation in `test_epic_140_preview_endpoints.py` → 24 Fehler auf einmal weg.
4. **Batch 4 — Radar-Throttle:** `test_feature_656` + `test_feature_660`.
5. **Batch 5 — Produkt-Bug-Klärung:** `test_trip_report_test_send_past_stage_clamp` (PO-Entscheid: ist `sent` bei fehlendem Wetter ein Bug?).
6. **Batch 6 — Host-Entkopplung & Pollution:** `test_622`, `test_952` (Env-Kapselung; gehört zur Spec `fix_1196_s1_testnetz_entrauschen.md`).
7. **Batch 7 — Endgültig ausmisten:** `test_issue_586`, `test_issue_603`, `test_bundle_e_gate_tooling`, `test_pytest_collection_and_timeout_safety` — Artefakt-/Meta-Tests entweder sauber aus dem Kern-Pfad verschieben oder mit Begründung in der Liste belassen. Zielbild: Die Exclude-Liste enthält am Ende nur noch begründete Nicht-Kern-Tests.

## Verifikationsprotokoll dieser Nachvermessung

- Lauf 1 (alle 48 Dateien, Haupt-Checkout): 32 FAILED + 1 ERROR in 11 Dateien.
- Lauf 2 (37 grüne Kandidaten einzeln, Haupt-Checkout): 1 unerwarteter FAILED in
  `test_issue_603_design_fidelity_gate.py` (host-/artefakt-abhängig) → bleibt in der Liste.
- Lauf 3 (12 rote Dateien, `--tb=line`): Grundursachen der Tabelle oben.
- Lauf 4 (Volllauf, frischer Worktree-Checkout ohne `.env`): 6 FAILED —
  `test_622` (2) und `test_952` (2) umgebungsabhängig rot → zurück in die Liste;
  `test_issue_1014_live_optin` (2) nur im Volllauf rot → Pollution (isoliert grün).
- Lauf 5 (Volllauf mit 14er-Liste): nur `test_issue_1014_live_optin` (2) rot.
- Lauf 6 (Subset der alphabetischen Vorgänger von 1014 im Worktree): dort zeigen
  re-aktivierte Dateien (`test_alert_run_deadline`, `test_alert_tenancy_two_users`,
  `test_bundle_791_847_844_alerts`) Alert-Versand-Assertions rot, die im Volllauf
  grün waren — d.h. das Testnetz ist **in beide Richtungen instabil**
  (reihenfolge-, datums- und hostabhängig). Lokale Läufe können die CI-Wirkung
  einer Listen-Entfernung daher nicht abschließend beweisen.
- Konsequenz: Der **PR-Lauf auf dem CI-Runner ist der einzige verbindliche
  Beleg** (Workflow läuft auf `pull_request`, main ist geschützt). Fällt eine
  re-aktivierte Datei dort auf: Ein-Zeilen-Revert (Eintrag zurück in die Liste)
  und die Datei wandert in Batch 6/7 dieser Liste. Die mittelfristige Lösung
  ist die Spec `fix_1196_s1_testnetz_entrauschen.md`, nicht weitere lokale
  Mehrfachvermessung.
