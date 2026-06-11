# Spec: Issue #762 — Etappen-Nummer-Dedup erhält Sub-Etappen-Suffix

- **Issue:** #762 (Nebenbefund aus #760, Adversary-Finding F004, LOW)
- **Created:** 2026-06-11
- **Type:** Bug
- **Scope:** Backend (Python), eine Regex-Änderung in `src/app/trip.py`

## Problem

Die in #760 eingeführte Dedup-Regex

```python
_STAGE_PREFIX_RE = re.compile(
    r"^\s*(?:Etappe|Tag)\s*\d+\s*[:.\-–—]?\s*(?P<rest>.*)$",
    re.IGNORECASE,
)
```

greift bei Sub-Etappen-Namen wie `Etappe 3a` zu gierig: `\d+` matcht nur die Ziffer
`3`, das Suffix-Zeichen `a` wird zum `rest`. Bei chronologischer Position 2 entsteht
dann `Etappe 2: a` — das ursprüngliche `3a` geht verloren (kosmetischer
Inhaltsverlust in Mail-Header und Betreff).

## Lösung

Wortgrenze `\b` direkt nach `\d+`:

```python
_STAGE_PREFIX_RE = re.compile(
    r"^\s*(?:Etappe|Tag)\s*\d+\b\s*[:.\-–—]?\s*(?P<rest>.*)$",
    re.IGNORECASE,
)
```

Bei `Etappe 3a` folgt auf die Ziffer `3` ein Wortzeichen `a` → keine Wortgrenze →
der gesamte Präfix-Match scheitert → der Originalname bleibt erhalten. Ergebnis:
`Etappe 2: Etappe 3a` (Original-Erhalt, eine der beiden im Issue genannten
akzeptablen Erwartungen).

Alle bisherigen Dedup-Fälle bleiben unverändert, weil nach der Ziffernfolge dort
stets eine Wortgrenze existiert (Space, Separator `:`/`-`/`.` oder Stringende).

## Änderungen

- **File:** `src/app/trip.py:33` — `_STAGE_PREFIX_RE`: `\d+` → `\d+\b` (1 Zeichen).
- Keine Änderung an `numbered_stage_label()` oder den 3 Call-Sites
  (`trip_alert.py`, `trip_report_scheduler.py`, `preview_service.py`) — sie
  konsumieren nur das Ergebnis und profitieren automatisch.

## Acceptance Criteria

**AC-1:** Given eine Etappe mit Sub-Etappen-Namen `Etappe 3a` an chronologischer
Position 2 / When `Trip.numbered_stage_label(stage)` aufgerufen wird / Then enthält
das Ergebnis weiterhin `3a` (konkret `Etappe 2: Etappe 3a`) und NICHT das
verstümmelte `Etappe 2: a`.

**AC-2:** Given eine Etappe mit Sub-Etappen-Namen `Etappe 3b` an chronologischer
Position 3 / When `numbered_stage_label(stage)` aufgerufen wird / Then bleibt das
Suffix `b` erhalten (`Etappe 3: Etappe 3b`) und geht nicht verloren.

**AC-3:** Given alle bestehenden #760-Dedup-Fälle (`von Sóller …`, `Tag 1: …`,
`Etappe 4`, `Etappe 2: Gipfeltour`, `tag 1: Foo`, `Etappe 3 - Hochalm`,
`Tag 2: Gipfeltour`, leerer Name) / When `numbered_stage_label` aufgerufen wird /
Then ist das Ergebnis byte-identisch zum bisherigen Verhalten (keine Regression der
korrekten Deduplizierung).
