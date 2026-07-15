# Spec: prod_selftest — interne/auth-geschützte URLs überspringen statt FAIL

- **Issue:** #1197 (Sammel-Gate-Audit), Scheibe „prod_selftest interne/send-URLs"
- **Created:** 2026-07-15
- **Typ:** Gate-Fix (Kategorie c — fälschlich blockierendes Gate)
- **ADR-Nr.:** keine
- **Datei:** `.claude/hooks/prod_selftest.py`
- **Prüfdatum (Regel-Budget):** 2026-10-13

## Problem

`prod_selftest.py` schreibt für Findings, deren `url` per Konstruktion nicht
öffentlich per GET probebar ist, fälschlich `prod_status: FAIL` → Verdict PARTIAL
→ Exit 1 → blockiert Issue-Close, obwohl die Produktion gesund ist. Zwei Klassen:

1. **Interner Host/Port:** `localhost` / `127.0.0.1` / `::1` bzw. interne Ports
   `8000` / `8001` / `8090` in der Roh-URL des Findings.
2. **Auth-geschützter Sende-Endpoint:** Pfad `^/api/scheduler/.+/send$`
   (Trip- und Compare-Preset-Versand) — darf öffentlich nie getriggert werden.

Sechs identische Vorfälle in #1197 belegt (Kategorie c).

## Lösung

Neue Klassifikationsfunktion `_is_internal_or_send_url(raw_url)`, ausgewertet in
`_probe_ac()` **vor** `_staging_to_prod_url()`, analog zum bestehenden
`_is_staging_test_trip_preview`-Muster. Treffer → neuer Skip-Status
`SKIPPED_NOT_MAPPABLE` (kein HTTP-GET). Das Finding zählt in `_derive_verdict`
nicht als PASS-mit-FAIL, blockiert also nicht.

## Acceptance Criteria

**AC-1:** Given ein Finding mit `status: PASS` und einer Roh-URL, deren Host
`localhost`, `127.0.0.1` oder `::1` ist, When `_probe_ac` es verarbeitet, Then
liefert es `prod_status: SKIPPED_NOT_MAPPABLE` und führt keinen HTTP-GET aus.

**AC-2:** Given ein Finding mit `status: PASS` und einer Roh-URL mit internem Port
`8000`, `8001` oder `8090` (auch auf öffentlichem Hostnamen), When `_probe_ac` es
verarbeitet, Then liefert es `prod_status: SKIPPED_NOT_MAPPABLE` ohne HTTP-GET.

**AC-3:** Given ein Finding mit `status: PASS`, dessen URL-Pfad auf das Muster
`/api/scheduler/<beliebig>/send` passt (unabhängig vom Host, inkl. öffentlicher
Staging-URL), When `_probe_ac` es verarbeitet, Then liefert es `prod_status:
SKIPPED_NOT_MAPPABLE` ohne HTTP-GET.

**AC-4:** Given eine Findings-Liste, in der jedes PASS-Finding entweder intern
oder ein Sende-Endpoint ist (alle also übersprungen werden), When der Verdict
abgeleitet wird, Then ist das Ergebnis nicht PARTIAL und der Exit-Code ist 0.

**AC-5:** Given ein Finding mit `status: PASS` und einer normalen öffentlichen
Prod-URL (z.B. `/api/health`, kein interner Host/Port, kein Sende-Pfad), das in
Produktion 401 liefert, When `_probe_ac` es verarbeitet, Then bleibt
`prod_status: FAIL` erhalten und der Gesamt-Verdict wird PARTIAL (Nicht-Aufweichen
der echten Fang-Wirkung).

**AC-6:** Given der `:AC-N`-Suffix an der Finding-URL (Staging-Marker), When die
interne/send-Klassifikation läuft, Then wird der Suffix vor der Host-/Pfad-Prüfung
entfernt, sodass die Erkennung trotz Suffix greift.

## Known Limitations

- Der Findings-Bleed beim **Schreiben** der Attestation (fremder Workflow auf
  gleichem HEAD) ist NICHT Teil dieser Spec — separater #1197-Eintrag für
  `staging_gate.py --write-verdict` (per-Workflow-Merge).
- Method-bewusstes Proben (GET vs. POST, 405-Sonderfall) wird NICHT eingeführt;
  der Skip löst das Symptom vollständig ohne Zusatzkomplexität.

## Test-Politik

Kern-Schicht, deterministisch: echte Findings-Dicts werden durch `_probe_ac`
bzw. `_derive_verdict` geschickt (kein Mock, kein Netz). Neue Datei
`tests/tdd/test_prod_selftest_internal_url_skip.py` (Verhaltens-Name, keine
Issue-Nummer).
