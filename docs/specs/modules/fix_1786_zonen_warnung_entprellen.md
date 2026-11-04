---
entity_id: fix_1786_zonen_warnung_entprellen
type: module
created: 2026-11-04
updated: 2026-11-04
status: draft
version: "1.0"
tags: [zeitzone, logging, scheduler, bugfix]
---

# Zonen-Warnung entprellen (#1786)

## Approval

- [ ] Approved

## Purpose

Die Warnung „Keine aufloesbare Zeitzone … es gilt Weltzeit (UTC)" aus `first_resolvable_tz()` feuert bei jedem Aufruf und Cron-Takt (bis 312× pro Tag und Preset) und überdeckt andere Meldungen im Protokoll. Sie soll sichtbar bleiben (#1726 AC-15: der Fall darf nie still geschehen), aber höchstens einmal je (Preset, Tag) erscheinen. Rückgabewert (UTC) und Fachverhalten bleiben unverändert.

## Source

- **File:** `src/utils/timezone.py`
- **Identifier:** `first_resolvable_tz` (Schicht: Python-Core, `src/utils/`)

> **Schicht/Querschnitt:** reine Python-Core-Logging-Änderung. Kein Frontend, keine Go-API, kein Trip/Compare-Pendant (gemeinsame Helferfunktion beider Seiten). Keine Nutzerdaten bewegt (kein Mandanten-Test nötig; der Schlüssel enthält nur das Preset-/Kontext-Label). Kein Briefing-/Alarm-Inhalt betroffen → Kanäle (E-Mail · Telegram · SMS · Premium-SMS) unberührt.

## Befund Guard-Reihenfolge (Issue-Vorschlag abgelehnt)

Das Issue regte an, die Zone erst nach den Guards aufzulösen. Das geht nicht: `end_date`- und Wochentag-Guard in `presets_due_for_hour` rechnen gegen den **Ortstag** (#1727 S5b, ADR-0044), der die Zone braucht. Verschieben würde Fälligkeit und Wochentag falsch berechnen. Es bleibt bei reiner Entprellung; die Guard-Reihenfolge wird nicht angefasst.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue. Die Änderung berührt keine Entscheidungsfläche (Kanäle, Provider, Datenmodell, Auth); sie hält #1726 AC-15 ein und stützt sich auf ADR-0044 (Ortstag-Guards bleiben unverändert).
- **Rationale:** prozesslokale Entprellung statt persistentem Zustand (Zustandsmeldung, Neustartverlust = höchstens eine Zeile mehr).

## Estimated Scope

- **LoC:** ~25 Produktiv, ~60 Test
- **Files:** 2 (`src/utils/timezone.py`, `tests/tdd/test_zonen_warnung_entprellt.py`)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `resolve_location_tz` | Funktion | unverändert |
| `logger`, `UTC` | Modul | Warnung / Rückfallwert |
| Aufrufer (`compare_slot_scheduler._preset_ortszeit`, `scheduler_dispatch_service`, `compare_alert`, `compare_radar_alert`, `compare_official_alert`, `compare_preview_service`, `api/routers/compare.py`) | Downstream | Signatur und Rückgabe unverändert |

## Implementation Details

```
_WARNED: set[tuple[str, date]]   # modulglobal, prozesslokal
_WARNED_LOCK: threading.Lock

def _utc_today() -> date:        # Naht für Tests (Uhr)
    return datetime.now(UTC).date()

def reset_zonen_warnung() -> None:   # Reset für Tests
    mit Lock: _WARNED.clear()

first_resolvable_tz(locations, context_label=""):
    ... Auflösung wie bisher ...
    unaufloesbar:
        if context_label == "":           # kein Preset-Bezug -> nicht entprellen
            logger.warning(...)           # wie bisher
        else:
            tag = _utc_today()
            mit Lock:
                alte Einträge mit Tag != heute verwerfen
                neu = (context_label, tag) not in _WARNED
                _WARNED.add((context_label, tag))
            if neu: logger.warning(...)
    return UTC
```

Entscheidungen:
- **Schlüssel `(context_label, UTC-Tag)`**: bei unauflösbarer Zone gibt es keinen Ortstag, daher UTC-Tag. Tageswechsel ⇒ neuer Schlüssel ⇒ je Tag und Preset eine Zeile (AC-15 bleibt erfüllt).
- **Leeres `context_label`** (z. B. Sofort-Vergleich ohne Preset): nicht entprellen, damit unterschiedliche Aufrufer nicht verschluckt werden.
- **Prozesslokal, nicht neustartfest**: es ist eine Zustandsmeldung; ein Neustart kostet höchstens eine Zeile mehr. Das Muster von `alert_daily_limit` (persistiert) wurde als überdimensioniert verworfen.
- **Thread-Sicherheit** über `threading.Lock` (Scheduler- und FastAPI-Threads).
- **Signatur und Name** `first_resolvable_tz(locations, context_label="")` bleiben stabil (bestehende Tests patchen die Naht `css.first_resolvable_tz`).

## Acceptance Criteria

- **AC-1:** Given ein Preset-Label und Orte ohne auflösbare Zone/When `first_resolvable_tz` an demselben UTC-Tag 312-mal mit diesem Label aufgerufen wird/Then erscheint genau eine Warnzeile im Protokoll und jeder Aufruf liefert UTC zurück.
- **AC-2:** Given zwei verschiedene Preset-Labels mit unauflösbarer Zone am selben Tag/When beide aufgerufen werden/Then erscheint je Label genau eine Warnzeile (A verschluckt B nicht).
- **AC-3:** Given ein Label wurde heute bereits gewarnt/When die Uhr auf den nächsten UTC-Tag springt und derselbe Fall erneut auftritt/Then erscheint erneut genau eine Warnzeile (die Warnung ist nie dauerhaft still).
- **AC-4:** Given ein leeres `context_label` und unauflösbare Zone/When die Funktion mehrfach aufgerufen wird/Then erscheint bei jedem Aufruf eine Warnzeile (keine Entprellung ohne Preset-Bezug).
- **AC-5:** Given Orte mit auflösbarer Zone (auch erst beim späteren Ort)/When die Funktion aufgerufen wird/Then liefert sie dieselbe Zone wie bisher und schreibt keine Warnung (Rückgabe und Überspringen von `None`/unauflösbaren Orten unverändert).
- **AC-6:** Given parallele Aufrufe aus mehreren Threads mit demselben Label und Tag/When alle fertig sind/Then erscheint insgesamt genau eine Warnzeile.
- **AC-7:** Given der Zustand wurde per `reset_zonen_warnung()` zurückgesetzt/When der Fall erneut auftritt/Then erscheint wieder eine Warnzeile (Tests bleiben reihenfolgeunabhängig).

## Expected Behavior

- **Input:** `first_resolvable_tz(locations, context_label)` wie bisher.
- **Output:** unverändert (Zone oder UTC).
- **Side effects:** Warnzeile höchstens einmal je (Label, UTC-Tag) bei nichtleerem Label; Set wird beim Eintragen auf den heutigen Tag begrenzt (bleibt klein).

## Tests

`tests/tdd/test_zonen_warnung_entprellt.py` — echte Aufrufe mit `caplog`, Uhr per Monkeypatch der Naht `_utc_today` (keine Mock-Logik), Reset per Fixture. Mutations-Gegenprobe: Entprellung entfernen ⇒ AC-1/6 rot; Label aus dem Schlüssel entfernen ⇒ AC-2 rot; Tag aus dem Schlüssel entfernen ⇒ AC-3 rot; Leer-Label-Sonderfall entfernen ⇒ AC-4 rot.

## Changelog

- 2026-11-04: Initiale Fassung (#1786).
