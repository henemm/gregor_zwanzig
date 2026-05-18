---
workflow: issue-245-sms-prefix-separator
date: 2026-05-17
validator: external
isolation: spec + running app only (no src/, no git, no implementer artifacts)
---

# External Validator Report — Issue #245 SMS Prefix Separator

**Spec:** `docs/specs/modules/issue_245_sms_prefix_separator.md`
**Datum:** 2026-05-17
**Server:** https://staging.gregor20.henemm.com
**Auth:** Session-Cookie für User `validator-issue110`

## Setup

Drei Test-Trips via `POST /api/trips` angelegt:

| Trip-ID | Stage-Name | Zweck |
|---|---|---|
| `val-issue245` | `"Tag 1: von Valldemossa nach Deià"` | AC-1 (Original-Bug-Reproduktion aus Spec) |
| `val-issue245-ac2` | `"Normalname"` (kein `:`) | AC-2 (Regressions-Check) |
| `val-issue245-adv` | `"AB CDEFGH: ABC"` (14 Zeichen, `:` an Pos 9) | Adversary: trailing Space entsteht **erst nach** 10-Char-Truncation |

Vorschau jeweils über das Trip-Detail-View `→ Vorschau`-Tab ausgelöst (kein direkter API-Endpunkt vorhanden), Phone-Frame mit Playwright headless gelesen + byte-exakt via `od -c` verifiziert.

## Checklist

| # | Expected Behavior (Spec) | Beweis | Verdict |
|---|---|---|---|
| AC-1 | Stage `"Tag 1: von Valldemossa nach Deià"` → token_line enthält **kein** `" :"` (kein Space direkt vor Separator-Doppelpunkt) | Phone-Screen: `"Tag 1 von: N- D- R- PR- W- G- TH:-"` — byte-exakt `n,:,SP,N` (kein Space vor `:`). Screenshot `preview-tab.png`, hex-Dump `sms-text.txt` | **PASS** |
| AC-2 | Stage `"Normalname"` (ohne Doppelpunkt) → kein Regressions-Effekt | Phone-Screen: `"Normalname: N- D- R- PR- W- G- TH:-"` — Prefix `Normalname:` korrekt, identisches Subject/Sektions-Schema wie AC-1. Screenshot `preview-ac2.png`, `sms-text-ac2.txt` | **PASS** |
| Adv | Stage `"AB CDEFGH: ABC"` — trailing Space entstünde nur **nach** `[:10]`-Truncation. Beweist, dass der Fix nicht nur outer-strip macht, sondern bis ins fertige Token greift. | Phone-Screen: `"AB CDEFGH: N- D- R- PR- W- G- TH:-"` — `H,:,SP,N` byte-exakt, kein Space vor `:`. Screenshot `preview-adv.png`, `sms-text-adv.txt` | **PASS** |

### Konsistenz-Check (zusätzlich)

| Aspekt | Beobachtung |
|---|---|
| Report-Type-Switch | Morning + Evening liefern identisches Prefix-Verhalten (`sms-text-morning.txt`) |
| Reihenfolge Subject·Nacht·Tag·Regen·Druck·Wind·Gust·Gewitter·Stirnlampe·Risiko | Im UI-Hint sichtbar, Token-Reihenfolge in Vorschau entspricht (`N- D- R- PR- W- G- TH:-`) |
| Zeichenzähler | `34/160` (AC-1), `35/160` (AC-2) — plausibel |

## Findings

Keine. Bug aus Issue #245 ist reproduzierbar gefixt; auch der Edge-Case, bei dem der trailing Space erst nach Truncation entsteht, wird abgefangen.

## Verdict: VERIFIED

### Begründung

- **AC-1 erfüllt** (Original-Spec-Beispiel byte-exakt korrekt: `"Tag 1 von:"` statt `"Tag 1 von :"`).
- **AC-2 erfüllt** (keine Regression bei Stage-Namen ohne Doppelpunkt).
- **Adversary-Vector entschärft** (trailing Space nach Truncation greift ebenfalls — der Fix wirkt entweder mehrfach oder post-truncation und ist damit robuster als ein reines outer-strip).
- Phone-Frame-Screenshots + Byte-exakte `od -c`-Dumps liegen als Beweis vor.
