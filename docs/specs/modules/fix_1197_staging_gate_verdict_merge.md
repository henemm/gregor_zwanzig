# Spec: staging_gate --write-verdict per-Workflow-Findings-Merge

- **Issue:** #1197 (Sammel-Gate-Audit), Scheibe „staging_gate --write-verdict Blind-Overwrite"
- **Created:** 2026-07-16
- **Typ:** Gate-Fix (Datenverlust-/Korrektheits-Risiko im Deploy-Gate)
- **ADR-Nr.:** keine
- **Datei:** `.claude/hooks/staging_gate.py` (`write_verdict`, ~Z. 229)
- **Prüfdatum (Regel-Budget):** 2026-10-14

## Problem

`write_verdict` überschreibt die commit-getaggte Attestation
`.claude/e2e_verified/<sha>.json` blind. Zwei Workflows auf demselben HEAD →
die Verifikations-Evidenz (`findings`) des Erstschreibers geht verloren.

## Lösung

Existiert die Zieldatei bereits mit `verified_commit == aktueller SHA`, werden
die `findings` verlustfrei vereinigt (dedup) statt überschrieben. Bei
abweichendem `verified_commit` (stale/Singleton) bleibt das Überschreiben.

## Acceptance Criteria

**AC-1:** Given eine bestehende Attestation für SHA X mit `findings` [A], When
`write_verdict` mit einem VERIFIED-Verdict und `findings` [B] für denselben SHA X
läuft, Then enthält die geschriebene Datei die Vereinigung von [A] und [B] und
kein Finding aus [A] geht verloren.

**AC-2:** Given bestehende und neue Findings mit mindestens einem inhaltlich
identischen Finding, When gemergt wird, Then erscheint dieses Finding in der
Ergebnisdatei genau einmal (Deduplizierung über stabile Serialisierung).

**AC-3:** Given es existiert noch KEINE Attestation für den SHA, When
`write_verdict` schreibt, Then ist das Ergebnis unverändert zum bisherigen
Verhalten (nur die neuen Findings, kein Merge-Artefakt).

**AC-4:** Given eine bestehende Datei am Zielpfad trägt einen ANDEREN
`verified_commit` als den aktuellen SHA (stale/Singleton via `--e2e-path`), When
`write_verdict` für den aktuellen SHA schreibt, Then wird NICHT gemergt, sondern
überschrieben (keine Vermischung fremder Commit-Findings).

**AC-5:** Given ein Merge zweier VERIFIED-Schreibvorgänge auf SHA X, When die
Datei geschrieben ist, Then beginnt `staging_verdict` weiterhin mit "VERIFIED"
und `verified_commit` ist X (das Deploy-Gate `gate_check` bleibt bestehbar).

**AC-6:** Given `write_verdict` erhält ein BROKEN-Verdict, When es aufgerufen
wird während für den SHA bereits eine Attestation existiert, Then wird die
bestehende Datei NICHT verändert und der Rückgabewert ist 1 (kein Merge, kein
Überschreiben durch BROKEN).

## Known Limitations

- Findings werden NICHT pro Workflow getaggt (keine Schema-Erweiterung). Der
  Merge ist eine reine verlustfreie Vereinigung der `findings`-Arrays.
- `verified_at` und `staging_verdict` übernimmt der zuletzt schreibende Lauf
  (beide sind VERIFIED); die Evidenz (`findings`) bleibt vollständig erhalten.

## Test-Politik

Kern-Schicht, deterministisch: `write_verdict` wird mit echten Findings-JSON-
Dateien in einem `tmp_path` gegen einen kontrollierten Attestationspfad
ausgeführt (kein Netz, kein Mock). Das Telegram-Live-Gate wird über einen echten
Seam (Umgebungs-/Scope-Bedingung) auf No-Op gehalten, nicht gemockt. Neue Datei
`tests/tdd/test_staging_gate_verdict_merge.py`.
