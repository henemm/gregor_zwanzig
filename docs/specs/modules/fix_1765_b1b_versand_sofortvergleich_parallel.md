---
entity_id: fix_1765_b1b_versand_sofortvergleich_parallel
type: module
created: 2026-08-16
updated: 2026-08-16
status: approved
version: "1.0"
tags: [issue-1765, ortsvergleich, nebenlaeufigkeit, versand]
---

# #1765 B1b — Versand + Sofortvergleich verarbeiten Orte gleichzeitig

## Approval

- [x] Approved — PO, 2026-08-16 (ACs + LoC-Override auf 500)

## Purpose

Die beiden verbliebenen Aufrufwege des Ortsvergleichs — **Versand** (auch per Cron) und
**Sofortvergleich** — verarbeiten ihre Orte nacheinander und reissen dadurch die
60-Sekunden-Grenze von nginx (gemeldet: 504 bei vier Orten). Beide werden auf den in
Scheibe B1 gelieferten, bereits live laufenden Baustein `run_comparison_parallel()`
umgestellt. Damit ist #1765 vollstaendig behoben.

## Source

- **File:** `src/services/scheduler_dispatch_service.py`
- **Identifier:** `send_one_compare_preset()` (Z.451)
- **File:** `api/routers/compare.py`
- **Identifier:** `run_comparison()` (Z.71)

Schicht: **Python-Core** (`src/services/`, `api/routers/`). Kein Go-, kein Frontend-Anteil.

## Estimated Scope

- **LoC:** ~12 produktiv, ~350-450 Test (Erfahrungswert B1: Testanteil ×3-4)
- **Files:** 2 geaendert, 2 neu (Tests)
- **Effort:** medium

**Das LoC-Limit von 250 wird gerissen** — Override auf 500 noetig. Grund ist nicht der
Mechanismus (12 Zeilen), sondern der Nachweis: bei Nebenlaeufigkeit braucht jedes Kriterium
einen eigenen Aufbau (Treffpunkt-Sperre, gedrehte Fertigstellung, echter Aufrufweg), der
sich zwischen den Kriterien nicht teilen laesst.

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `src/services/comparison_parallel.py` | nutzt | Der Baustein. Signaturgleich, seit `098226ae` live |
| `src/services/comparison_engine.py` | unberuehrt | Wird vom Baustein je Ort aufgerufen |
| `src/providers/call_log.py` | nutzt | `call_source` muss explizit gesetzt werden |
| `src/services/dispatch_orchestrator.py` | unberuehrt | Presets bleiben sequentiell (Z.229) |

## Implementation Details

Beide Stellen sind ein reiner Aufrufweg-Tausch, kein neuer Mechanismus:

```python
# src/services/scheduler_dispatch_service.py — statt ComparisonEngine.run(...)
from services.comparison_parallel import run_comparison_parallel

result = run_comparison_parallel(
    locations=locations,
    time_window=resolve_compare_time_window(preset),
    target_date=target_date,
    forecast_hours=COMPARE_FORECAST_HOURS,
    profile=profile,
    official_alerts_enabled=preset.get("official_alerts_enabled", True),
    call_source="vergleich",
)
```

```python
# api/routers/compare.py — analog, ohne official_alerts_enabled (Default True)
result = run_comparison_parallel(
    locations=selected,
    time_window=(time_window_start, time_window_end),
    target_date=td,
    forecast_hours=forecast_hours,
    profile=profile,
    call_source="vergleich",
)
```

`call_source` MUSS explizit gesetzt werden: ein `ThreadPoolExecutor` vererbt den
`ContextVar`-Kontext nicht an seine Worker, und die Stack-Marker-Liste
(`call_log.py:43-55`) liefe im Worker-Thread ins Leere.

## Expected Behavior

- **Input:** unveraendert — ein Preset (Versand) bzw. `location_ids` (Sofortvergleich)
- **Output:** unveraendert — dasselbe `ComparisonResult`, dieselbe Mail, dieselbe JSON-Antwort
- **Side effects:** unveraendert — `letzter_versand`/`top_ort_letzter_versand` nur im
  Erfolgsfall, Δ-Anker je Ort, Alarm-Schnappschuesse. Neu ist allein, dass die
  Wetterabrufe der Orte gleichzeitig laufen (hoechstens 4).

## Acceptance Criteria

- **AC-1:** Given ein Preset mit drei Orten / When der Versand laeuft / Then werden die drei
  Orte gleichzeitig verarbeitet, nicht nacheinander
  - Test: Die Fake-Engine laesst jeden Ort an einer `threading.Barrier` (Parteien = 3,
    Zeitschranke) warten. Seriell erreicht der zweite Ort den Treffpunkt nie ⇒ Zeitschranke
    ⇒ rot. Pflichtmutation: `MAX_PARALLEL_LOCATIONS = 1` muss den Test rot machen.

- **AC-2:** Given ein Preset mit drei Orten, deren Verarbeitung in umgekehrter Reihenfolge
  fertig wird / When die Vergleichsmail erzeugt wird / Then stehen die Orte darin in der
  **konfigurierten** Reihenfolge, nicht in der Fertigstellungsreihenfolge
  - Test: Fake-Engine mit gestaffelten Wartezeiten (letzter Ort zuerst fertig); geprueft
    wird die Ortsreihenfolge im **gerenderten Mailtext**, nicht im Zwischenobjekt.

- **AC-3:** Given ein Preset mit drei Orten, deren Verarbeitung in umgekehrter Reihenfolge
  fertig wird / When der Versand abgeschlossen ist / Then ist der persistierte `top_ort` der
  **erste konfigurierte** Ort
  - Test: `top_ort_letzter_versand` aus `briefings/<preset_id>.json` nach dem Lauf lesen und
    gegen den ersten konfigurierten Ort pruefen. Deckt die Luecke, dass `top_ort` aus
    `result.locations[0]` stammt (`scheduler_dispatch_service.py:460`).

- **AC-4:** Given ein Preset mit drei Orten mit unterschiedlichen Wetterwerten / When die
  Vergleichsmail erzeugt wird / Then traegt **jeder** Ort seine eigenen Werte, nicht die
  eines anderen Orts
  - Test: Fake-Engine liefert je Ort einen ortsabhaengigen Wert (nachgeschlagen ueber
    `loc.id`, **nicht** ueber den Aufrufindex); geprueft wird die Zuordnung Ort→Wert im
    gerenderten Mailtext. Schliesst die gemessene Luecke, dass **kein** Bestands-Test die
    Orts-Staffelung bewacht.

- **AC-5:** Given ein Preset mit drei Orten, bei dem genau einer scheitert / When der
  Versand laeuft / Then wird die Mail trotzdem versandt und traegt den Fehler an der
  Position des gescheiterten Orts
  - Test: Fake-Engine wirft nur fuer einen bestimmten Ort; geprueft wird, dass die Mail
    zugestellt wurde und die beiden anderen Orte ihre Werte tragen.

- **AC-6:** Given ein Preset, bei dem **alle** Orte mit einer Ausnahme scheitern / When der
  Versand laeuft / Then schlaegt der Versand mit derselben Fehlerform fehl wie vor der
  Umstellung, und `letzter_versand` wird **nicht** geschrieben
  - Test: Fake-Engine wirft fuer jeden Ort; geprueft wird, dass die Ausnahme den Aufrufer
    erreicht und `briefings/<preset_id>.json` keinen neuen `letzter_versand` traegt.

- **AC-7:** Given ein Sofortvergleich ueber drei Orte / When `GET /api/compare` aufgerufen
  wird / Then werden die Orte gleichzeitig verarbeitet und die Antwort listet sie in der
  angeforderten Reihenfolge
  - Test: `threading.Barrier` wie AC-1, ueber den echten Router (`TestClient`); geprueft
    wird die Ortsreihenfolge im JSON-Antwortkoerper.

- **AC-8:** Given ein Versand mit mehreren Orten / When die Wetterabrufe laufen / Then
  traegt jeder Abruf im Aufruf-Journal die Quelle `vergleich`, auch aus dem Worker-Thread
  - Test: `resolve_call_source()` innerhalb der Fake-Engine auslesen und je Ort pruefen.
    Pflichtmutation: `call_source` weglassen muss den Test rot machen.

- **AC-9:** Given die Bestands-Testsuite des Versandpfads / When die Umstellung erfolgt ist
  / Then bleiben alle 14 Testdateien mit Engine-Stub unveraendert gruen
  - Test: Die betroffenen Dateien werden benannt ausgefuehrt; keine Datei wird angepasst.

## Known Limitations

- **Thundering Herd** bei Warnquellen mit gemeinsamem Schluessel (AT/IT ueber
  `meteoalarm_feed._cache`, FR ueber `vigilance`/`dpc`): bei zeitgleichem Cache-Miss
  entstehen redundante Abrufe. Kein Datenverlust, keine falsche Anzeige. Gebucht in #1199
  (Herkunft #1890, dort widerlegt und geschlossen).
- **Cron-Ueberlagerung ueber Nutzer hinweg** ist gemessen unkritisch: 2 Nutzer in der
  Produktions-Datenwurzel, Presets sequentiell, 4 Orte je Preset ⇒ hoechstens 8 gleichzeitige
  Ortsverarbeitungen gegen 100 Anfragen/Minute (Meteo-France).
- Bei **zwei zeitgleichen, verschiedenen** systemischen Stoerungen entscheidet der erste
  konfigurierte Ort ueber die Fehlerart (Einreichungs-, nicht Fertigstellungsreihenfolge) —
  uebernommen aus B1, unveraendert.
- `GET /api/compare` ignoriert weiterhin den `user_id` (#1891) und kennt keine Obergrenze
  fuer die Ortsanzahl. **Nicht** Teil dieser Scheibe.
- Der Vergleichspfad hat weiterhin keinen Grundvorhersage-Cache (Zurueckstellung aus #1329).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Die Entscheidung fuer parallele Ortsverarbeitung im Vergleichspfad wurde in
  Scheibe B1 getroffen und ist dort dokumentiert. B1b haengt lediglich zwei weitere
  Aufrufstellen an denselben Baustein — keine neue Entscheidungsflaeche.

## Changelog

- 2026-08-16: Initial spec created
