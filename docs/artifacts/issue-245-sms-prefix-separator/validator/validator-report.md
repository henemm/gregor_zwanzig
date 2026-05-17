# External Validator Report

**Spec:** docs/specs/modules/issue_245_sms_prefix_separator.md
**Datum:** 2026-05-17T14:54:00+02:00
**Server:** https://staging.gregor20.henemm.com

## Test-Setup

Trips angelegt via `POST /api/trips`:

| Trip-ID | Stage-Name | Zweck |
|---------|------------|-------|
| `val245-colon` | `"Tag 1: von Valldemossa nach Deià"` | AC-1: Doppelpunkt im Stage-Namen |
| `val245-normal` | `"Normalname"` | AC-2: Regression-Test ohne Doppelpunkt |
| `val245-leading` | `": Start"` | Zusatz: führender Doppelpunkt |
| `val245-trailing` | `"Tag1:"` | Zusatz: abschließender Doppelpunkt |

SMS-Preview gerufen über `GET /api/preview/{trip_id}/sms?type=evening` (auch type=morning gegengeprüft, identisches Ergebnis).

## Checklist

| # | Expected Behavior (aus Spec) | Beweis | Verdict |
|---|------------------------------|--------|---------|
| AC-1 | Stage `"Tag 1: von Valldemossa nach Deià"` → `token_line` enthält **keinen** Space direkt vor dem Separator-Doppelpunkt (`" :"` ist verboten). | `ac1_evidence_colon_stage.json`: `"token_line":"Tag 1 von : N- D- R- PR- W- G- TH:-"` — enthält `" :"` an Position 9–10. | **FAIL** |
| AC-2 | Stage `"Normalname"` (ohne Doppelpunkt) → kein Regressions-Effekt. | `ac2_evidence_normal_stage.json`: `"token_line":"Normalname: N- D- R- PR- W- G- TH:-"` — kein Space vor `:`, plausibel. | **PASS** |
| Spec-Output | `clean_stage = "Tag 1 von"` (no trailing space), SMS-Prefix `"Tag 1 von: N- ..."`. | Tatsächlich: `"Tag 1 von : N-..."` — der trailing Space von `clean_stage` ist sichtbar. | **FAIL** |

## Findings

### AC-1 fehlgeschlagen — `.strip()` ist auf Staging nicht aktiv

- **Severity:** HIGH
- **Expected:** `token_line` startet mit `"Tag 1 von: N-"` (kein Space vor Separator-Doppelpunkt).
- **Actual:** `token_line` startet mit `"Tag 1 von : N-"` — der durch `.replace(":", "")` entstandene Space steht weiterhin vor dem von der Token-Pipeline angehängten Separator-Doppelpunkt. Spec-Anforderung "`" :"` ist verboten" ist verletzt.
- **Evidence:**
  - `ac1_evidence_colon_stage.json`
  - 3× hintereinander identisch reproduziert (deterministisch, kein Timing/Cache-Artefakt)
  - Request: `GET /api/preview/val245-colon/sms?type=evening`
  - Response: `{"subject":"[Validator 245 Colon] Tag 1: von Valldemossa nach Deià — Abend","token_line":"Tag 1 von : N- D- R- PR- W- G- TH:-","char_count":35}`

### Zusatz-Beobachtung — Leading Colon ebenfalls betroffen

- **Severity:** LOW (nicht von AC abgedeckt, aber im Implementation-Detail-Block durch `.strip()` impliziert mitgeschützt)
- **Stage:** `": Start"`
- **Actual token_line:** `" Start: N- D- R- PR- W- G- TH:-"` — führendes Leerzeichen, das `.strip()` ebenfalls entfernen müsste.
- **Folge:** Bestätigt unabhängig, dass der `.strip()`-Fix aus dem Implementation-Details-Block der Spec auf Staging nicht wirkt — sonst wäre auch dieser Leading-Space weg.

### AC-2 in Ordnung — kein Regressions-Effekt

- **Severity:** —
- Normaler Stage-Name `"Normalname"` → `token_line` `"Normalname: N- D- R- PR- W- G- TH:-"` — exakt wie erwartet, sauberer Prefix-Separator ohne Whitespace-Drift.

## Verdict: BROKEN

### Begründung

Die Spec macht in Acceptance Criterion AC-1 unmissverständlich klar: bei Stage-Namen mit Doppelpunkt darf `token_line` keinen Space direkt vor dem Separator-Doppelpunkt enthalten (`" :"` ist verboten). Die laufende App auf Staging liefert reproduzierbar (3× identisch) genau diese verbotene Sequenz: `"Tag 1 von : N-..."`.

Damit ist der im Implementation-Details-Block der Spec dokumentierte Fix (`.replace(":", "").strip()`) auf https://staging.gregor20.henemm.com nicht aktiv — der Bug aus Issue #245 ist nicht behoben. AC-2 ist zwar erfüllt (keine Regression bei normalen Stage-Namen), aber das ist trivial, weil ohne `:` der Code-Pfad `replace(":", "")` wirkungslos bleibt.

AC-1 ist die zentrale Forderung des Tickets — sie schlägt fehl. Verdict: **BROKEN**.

### Hinweis an Implementierer

Falls der Fix lokal committed, aber das Staging-Deploy noch nicht erfolgt ist: Auto-Deploy auf Staging läuft ~5 Min nach Push. Erneute Validierung erst sinnvoll, wenn `/api/preview/val245-colon/sms?type=evening` ein `token_line` ohne `" :"` liefert.
