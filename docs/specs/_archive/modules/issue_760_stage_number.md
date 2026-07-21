---
entity_id: issue_760_stage_number
type: module
created: 2026-06-11
updated: 2026-06-11
status: draft
version: "1.0"
tags: [email, trip-briefing, stage, formatter]
---

<!-- Issue #760 — E-Mail: Etappen-Nummer muss zwingend Bestandteil sein -->

# Issue 760 — Etappen-Nummer zwingend in der Briefing-E-Mail

## Approval

- [x] Approved

## Purpose

Die Trip-Briefing-E-Mail (Betreff **und** Body-Header) zeigt aktuell nur den frei
eingegebenen Etappennamen (`stage.name`). Bei mehrtägigen Touren fehlt damit jeder
Hinweis, **welche** Etappe der Tour gemeint ist — der Wanderer kann das Briefing
nicht zuverlässig seiner Planung zuordnen. Diese Spec stellt der Etappen-Bezeichnung
**zwingend** die fortlaufende Etappen-Nummer voran (`Etappe N: <Name>`), abgeleitet
aus der chronologischen Position der Etappe innerhalb der Tour.

## Source

- **File:** `src/app/trip.py` — NEUE Methode `Trip.numbered_stage_label(stage: Stage) -> str` (~25 LoC): berechnet die 1-basierte chronologische Position (nach Datum sortiert) und erzeugt die deduplizierte Bezeichnung.
- **File:** `src/services/trip_report_scheduler.py:419` — `stage_name = stage.name if stage else None` → `stage_name = trip.numbered_stage_label(stage) if stage else None`
- **File:** `src/services/preview_service.py:117` — analog
- **File:** `src/services/trip_alert.py:654` — analog (`matched_stage`)

> **Schicht:** Python-Backend (`src/app/`, `src/services/`). Betreff (`output.subject`),
> HTML-Header (`html.py:329`) und Plain-Header (`plain.py:144`) konsumieren `stage_name`
> bereits unverändert — kein Eingriff in die Renderer nötig.

## Estimated Scope

- **LoC:** ~30
- **Files:** 4 (1 neue Methode + 3 Call-Site-Änderungen)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `re` | stdlib | Dedup-Erkennung vorhandener `Etappe N`/`Tag N`-Präfixe |
| `Trip.stages` | intern | chronologische Reihenfolge (nach `stage.date` sortiert) für die Positionsberechnung |

## Implementation Details

```python
# src/app/trip.py — Methode auf Trip
_STAGE_PREFIX_RE = re.compile(
    r"^\s*(?:Etappe|Tag)\s*\d+\s*[:.\-–—]?\s*(?P<rest>.*)$",
    re.IGNORECASE,
)

def numbered_stage_label(self, stage: Stage) -> str:
    """Etappen-Bezeichnung mit zwingender, dedupliziert vorangestellter Nummer.

    Die Nummer ist die 1-basierte chronologische Position der Etappe innerhalb
    der Tour (Etappen nach Datum sortiert). Trägt der Name bereits ein
    'Etappe N'/'Tag N'-Präfix, wird dieses durch die korrekte 'Etappe N:'-Form
    ersetzt (keine doppelte Nummer).
    """
    ordered = sorted(self.stages, key=lambda s: s.date)
    try:
        number = ordered.index(stage) + 1
    except ValueError:
        number = self.stages.index(stage) + 1  # Fallback: Listenposition
    name = (stage.name or "").strip()
    m = _STAGE_PREFIX_RE.match(name)
    rest = m.group("rest").strip() if m else name
    return f"Etappe {number}: {rest}" if rest else f"Etappe {number}"
```

**Dedup-Regel (PO-bestätigt, Format „Präfix, dedupliziert"):**

| `stage.name` | chronolog. Position | Ergebnis |
|--------------|---------------------|----------|
| `von Sóller nach Tossals Verds` | 3 | `Etappe 3: von Sóller nach Tossals Verds` |
| `Tag 1: von Valldemossa nach Deià` | 1 | `Etappe 1: von Valldemossa nach Deià` |
| `Etappe 4` | 4 | `Etappe 4` |
| `Etappe 2: Gipfeltour` | 2 | `Etappe 2: Gipfeltour` |
| `` (leer) | 5 | `Etappe 5` |

## Expected Behavior

- **Input:** ein `Trip` mit ≥1 `Stage`, plus die für das Datum aufgelöste `Stage`.
- **Output:** `stage_name`-String mit zwingend vorangestellter `Etappe N`-Nummer.
- **Side effects:** keine. Reine Funktion; `stage.name` in der Persistenz bleibt unverändert.

## Acceptance Criteria

- **AC-1:** Given ein Trip mit ≥2 Etappen, deren für heute aufgelöste Etappe einen Namen
  OHNE Nummer trägt (z. B. „von Sóller nach Tossals Verds", chronologisch Position 3) /
  When das Briefing als E-Mail versendet wird / Then enthält die zugestellte Mail im
  **Body-Header** den Text `Etappe 3: von Sóller nach Tossals Verds`.
  - Test: Echter Backend-Mail-E2E gegen Staging (Test-Trip, Empfänger `gregor-test@henemm.com`), IMAP-Abruf, Header-Zeile geprüft.

- **AC-2:** Given derselbe Versand / When die Mail zugestellt ist / Then enthält der
  **Betreff** ebenfalls die Etappen-Nummer im Format `Etappe 3: …`.
  - Test: IMAP-Abruf, Subject-Header geprüft (nicht bloß Substring-Presence, sondern korrekte Nummer für die aufgelöste Etappe).

- **AC-3:** Given ein Etappenname, der bereits ein Präfix `Tag 1: …` oder `Etappe 1`
  trägt / When `Trip.numbered_stage_label(stage)` aufgerufen wird / Then erscheint die
  Nummer GENAU EINMAL (`Etappe 1: …`), keine Verdopplung wie `Etappe 1: Tag 1: …`.
  - Test: Unit-Test über die Helper-Methode mit allen Fällen der Dedup-Tabelle.

- **AC-4:** Given ein Trip mit Etappen in nicht-chronologischer Listenreihenfolge
  (Persistenz-Reihenfolge ≠ Datums-Reihenfolge) / When `numbered_stage_label` für eine
  Etappe aufgerufen wird / Then entspricht die Nummer der chronologischen Position
  (nach `stage.date`), nicht der Listenposition.
  - Test: Unit-Test mit absichtlich umsortierter `stages`-Liste; erwartete Nummer = Datums-Rang.

## Changelog

- v1.0 (2026-06-11): Initiale Spec für Issue #760.
