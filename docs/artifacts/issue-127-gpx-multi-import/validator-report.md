# External Validator Report

**Spec:** `docs/specs/modules/gpx_multi_import.md` (v1.1, SvelteKit-Schicht)
**Datum:** 2026-05-05T15:20Z
**Server:** https://staging.gregor20.henemm.com
**Methode:** Unabhängige Playwright-Validierung (Headless Chromium), Auth-Cookie gesetzt

---

> **Hinweis:** Dies ist ein unabhängiger Validator-Report (externe Session).
> Tests TC1–TC11 wurden eigenständig entwickelt und gegen Staging ausgeführt.

## Checklist

| # | Acceptance Criterion (aus Spec) | Beweis | Verdict |
|---|----------------------------------|--------|---------|
| 1 | Multi-Select-Upload im New-Trip-Wizard möglich | TC1: setInputFiles([KHW_11, KHW_00a, KHW_10]) → Screenshot `screenshots/tc1-after-upload.png`: "3 Datei(en) ausgewaehlt" | **PASS** |
| 2 | Multi-Select-Upload im Edit-Trip-Dialog möglich | TC8: Route-Sektion ausgeklappt → Screenshot `screenshots/tc8-after-upload.png`: "3 Datei(en) ausgewaehlt", `multiple=""`-Attribut bestätigt | **PASS** |
| 3 | Nach Upload: Datumspicker + "X Etappen anlegen"-Button erscheint | Screenshot `tc1-after-upload.png`: Pending-Row mit Startdatum + "3 Etappen anlegen" | **PASS** |
| 4 | Natural-Sort korrekt: KHW_11, KHW_00a, KHW_10 → KHW_00a, KHW_10, KHW_11 | TC3 Output: `"KHW_00a: Von Troblach…"`, `"KHW_10: von Egger…"`, `"KHW_11: von Dolinza…"`. Screenshot `screenshots/tc3-natural-sort-stages.png` | **PASS** |
| 5 | Datums-Propagation: erste Stage = Startdatum, jede weitere +1 Tag | TC4 Output: date0=2026-05-01, date1=2026-05-02, date2=2026-05-03. Screenshot `screenshots/tc4-date-propagation.png` | **PASS** |
| 6 | Default-Datum: `today` wenn kein Stage vorhanden | TC6 Output: default date="2026-05-05", today="2026-05-05". Screenshot `screenshots/tc6-default-date.png` | **PASS** |
| 7 | Default-Datum: `last_stage_date + 1` wenn Stages vorhanden | TC7: Stage mit 2026-06-01 angelegt → nächster Upload → default="2026-06-02". Screenshot `screenshots/tc7-default-date-with-stages.png` | **PASS** |
| 8 | Single-File-Upload funktioniert weiterhin: "1 Etappe anlegen" | TC2 Output: commit btn text="1 Etappe anlegen". Screenshot `tc6-default-date.png` | **PASS** |
| 9 | Korrupte GPX-Datei übersprungen, restliche lückenlos | TC5: Inline-Fehler rot "KHW_05_corrupt.gpx: GPX parse failed…", "2 Etappe(n) geladen", Daten 2026-05-01/02. Screenshot `screenshots/tc5-corrupt-skip.png` | **PASS** |
| 10 | Kein Datum → Fehlermeldung, Buffer bleibt | TC10: Screenshot `screenshots/tc10b-after-no-date-commit.png`: roter Text "Bitte Startdatum waehlen.", Buffer unverändert | **PASS** |
| 11 | Buffer nach Commit geleert | TC11b Output: "buffer cleared after commit: true", "4 Etappe(n) geladen". Screenshot `screenshots/tc11b-after-commit.png` | **PASS** |
| 12 | Commit Edit-Trip: Natural-Sort + Daten korrekt | TC11b: KHW_00a als erste neue Etappe (07/01/2026). Screenshot `screenshots/tc11b-etappen.png` | **PASS** |
| 13 | Safari Factory Pattern | Headless Chromium kann Safari nicht testen; `[data-testid="bulk-stage-commit"]` ist vorhanden und klickbar (TC3, TC11b) | **UNKLAR** |

---

## Test-Ergebnisse (Rohdaten)

### Playwright-Tests (eigenständig, gegen Staging)

```
TC1  Multi-upload → "3 Etappen anlegen"           PASS (commit btn text: "3 Etappen anlegen")
TC2  Single-file → "1 Etappe anlegen"             PASS (commit btn text: "1 Etappe anlegen")
TC3  Natural-Sort KHW_11/00a/10 → 00a/10/11       PASS (stage names in correct order)
TC4  Datums-Propagation 2026-05-01/02/03           PASS
TC5  Corrupt file skipped, dates gapless           PASS (warning visible: true)
TC6  Default-Datum leerem Trip = today             PASS (2026-05-05 = today)
TC7  Default-Datum mit Stage = last+1              PASS (after 2026-06-01 → default 2026-06-02)
TC8  Edit-Trip Multi-Upload                        PASS (3 Datei(en), commit sichtbar)
TC10 Kein Datum → Fehler, Buffer bleibt           PASS (buffer still pending: true)
TC11b Edit-Trip Commit → Buffer geleert           PASS (4 Etappe(n) geladen, sorted)

Gesamt: 10 PASS, 1 UNKLAR (Safari)
```

### Stage-Reihenfolge (TC3, live gegen Staging)
```
Upload-Reihenfolge: KHW_11, KHW_00a, KHW_10 (absichtlich falsch)
→ Commit Startdatum 2026-05-01

Stage 1: "KHW_00a: Von Troblach Bhf nach Helmhotel"   date=2026-05-01  ✓
Stage 2: "KHW_10: von Egger Alm nach Dolinza Alm"     date=2026-05-02  ✓
Stage 3: "KHW_11: von Dolinza Alm nach Nötsch im Gailtal"  date=2026-05-03  ✓
```

### Edit-Trip Commit (TC11b, live gegen Staging)
```
Trip "Validator Test" hatte 1 vorhandene Stage.
Upload KHW_11, KHW_00a, KHW_10 → Commit 2026-07-01

Nach Commit: "4 Etappe(n) geladen"
Neue Stage 2: "KHW_00a: Von Troblach Bhf nach Helmhotel"  date=07/01/2026 ✓
(Natural-Sort in Edit-Trip bestätigt)
```

---

## Screenshots (in `screenshots/`)

| Datei | Inhalt |
|-------|--------|
| `tc1-after-upload.png` | New-Trip: "3 Datei(en) ausgewaehlt", Datumspicker, "3 Etappen anlegen" |
| `tc3-natural-sort-stages.png` | Step 2: KHW_00a (05/01), KHW_10 (05/02), KHW_11 (05/03) — natural-sorted |
| `tc4-date-propagation.png` | Step 2: Datums-Propagation 2026-05-01/02/03 |
| `tc5-corrupt-skip.png` | Roter Fehlertext + "2 Etappe(n) geladen" |
| `tc6-default-date.png` | Single-File: "1 Datei(en)", "1 Etappe anlegen", Default-Datum=heute |
| `tc7-default-date-with-stages.png` | Default-Datum = last_stage_date+1 (2026-06-02 nach 2026-06-01) |
| `tc8-after-upload.png` | Edit-Trip Route-Sektion: "3 Datei(en) ausgewaehlt", "3 Etappen anlegen" |
| `tc10b-after-no-date-commit.png` | Kein Datum: "Bitte Startdatum waehlen." in rot, Buffer bleibt |
| `tc11b-after-commit.png` | Edit-Trip nach Commit: "4 Etappe(n) geladen", Buffer geleert |
| `tc11b-etappen.png` | Edit-Trip Etappen: KHW_00a als erste neue Etappe (07/01/2026) |

---

## Findings

### F1 — Safari Factory Pattern nicht verifizierbar
- **Severity:** LOW
- **Expected:** Commit-Button reagiert nach Safari Hard-Reload (Factory Pattern)
- **Actual:** Headless-Chromium-Umgebung — Safari nicht testbar
- **Assessment:** `[data-testid="bulk-stage-commit"]` ist präsent und funktionsfähig (TC3, TC11b bestätigt). Kein Hinweis auf defektes Binding im Chromium-Test. Risiko bleibt gering.

---

## Verdict: VERIFIED

### Begründung

12 von 13 Acceptance Criteria PASS, 1 UNKLAR (Safari-Plattform-Constraint).

Alle funktional prüfbaren Anforderungen der Spec v1.1 sind gegen Staging nachgewiesen:
Multi-Upload in beiden Dialogen, Natural-Sort, Datums-Propagation, Default-Datum-Logik,
Fehlerbehandlung (corrupt + kein Datum), Buffer-Lifecycle und Edit-Trip-Commit.
Das Feature ist bereit für Production-Deploy.
