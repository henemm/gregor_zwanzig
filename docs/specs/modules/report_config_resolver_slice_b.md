---
entity_id: report_config_resolver_slice_b
type: refactor
created: 2026-07-11
updated: 2026-07-11
status: draft
version: "1.0"
tags: [reporting, email, compare, config, resolver, rework]
---

<!-- Issue #1209 — Scheibe B von #1203; erweitert Scheibe A (#1208, docs/specs/modules/report_config_resolver.md) -->

# Report-Config-Resolver — Scheibe B (Vorschau + Compare)

## Approval

- [x] Approved (PO 'go' 2026-07-11)

## Purpose

Scheibe A (#1208) hat den `ReportRenderOptions`-Resolver fuer den
E-Mail-Versandpfad des Scheduler gebaut. Scheibe B schliesst die beiden
verbliebenen Luecken: der Vorschau-Pfad (`preview_service.py`) mutiert
weiterhin ein Bestandsobjekt statt den Resolver zu benutzen (Patch-Hack,
Adversary-Befund F002), und der Compare-Versandpfad
(`scheduler_dispatch_service.py`) loest seine Render-Optionen weiterhin
inline aus einem rohen Preset-Dict auf, statt eine explizite,
resolverfoermige Struktur zu konsumieren. Zusaetzlich erzwingt ein
src-weiter Struktur-Test kuenftig, dass render-wirksame
`report_config`-Felder ausschliesslich ueber den Resolver gelesen werden —
nicht nur im Scheduler-Pfad (Scheibe A), sondern in ganz `src/services/`
und `src/output/`.

## Source

- **File:** `src/services/preview_service.py`, `src/services/scheduler_dispatch_service.py`, `src/services/report_config_resolver.py` (Erweiterung)
- **Identifier:** `PreviewService._build_report`/`_render_email`, `send_one_compare_preset`, `resolve_compare_render_options()` (NEU)

Betroffene Schicht: Python-Core / Domain-Backend (`src/services/`,
`src/output/renderers/`) — kein Frontend-, kein Go-API-Anteil.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `ReportRenderOptions`/`resolve_report_render_options()` (`src/services/report_config_resolver.py`, Scheibe A) | Funktion/DTO | Wird im Vorschau-Pfad genauso verdrahtet wie bereits im Scheduler-Pfad |
| `TripReportFormatter.format_email(..., render_options=)` (`src/output/renderers/trip_report.py:56-90`) | Funktion | Nimmt bereits den Parameter entgegen; Preview reicht ihn kuenftig explizit durch statt den internen Fallback zu nutzen |
| `resolve_enabled_metrics()` (`src/output/renderers/compare_metric_ids.py`) | Funktion | Baustein der neuen `resolve_compare_render_options()` |
| `resolve_hourly_metrics()` (`src/output/renderers/compare_hourly_metric_ids.py`) | Funktion | Baustein der neuen `resolve_compare_render_options()` |
| `render_compare_email()` (`src/output/renderers/comparison.py`) | Funktion | Konsument der neuen Compare-Optionen (unveraendert, nur Aufrufstelle aendert sich) |
| `tests/tdd/test_report_config_scheduler_structure.py` (Scheibe A) | Test | Vorbild fuer AST-Alias-Erkennung, das der neue src-weite Gate wiederverwendet |
| `RENDER_EFFECTIVE_FIELDS`/`RENDER_NEUTRAL` (`src/services/report_config_resolver.py`) | Konstanten | Feld-Whitelist/-Blacklist, auf der der neue Struktur-Gate basiert |

## Scope

### Affected Files
| File | Change Type | Description |
|------|-------------|--------------|
| `src/services/preview_service.py` | MODIFY | `_build_report` resolved einmal via `resolve_report_render_options(...)`, reicht `render_options=` explizit an `_render_email`/`format_email()` durch; Patch-Hack Z. 120-121 (`trip.display_config.show_compact_summary = trip.report_config.show_compact_summary`) entfaellt ersatzlos |
| `src/services/report_config_resolver.py` | MODIFY | NEU: `@dataclass(frozen=True) class CompareRenderOptions` (`top_n_details: int`, `enabled_metrics`, `hourly_metrics`, `hourly_enabled: bool`) + `resolve_compare_render_options(preset: dict) -> CompareRenderOptions` — reine Funktion, buendelt Default/Clamp/Log-Logik aus `scheduler_dispatch_service.py:252-276` |
| `src/services/scheduler_dispatch_service.py` | MODIFY | `send_one_compare_preset` ersetzt die inline Extraktion (Z. 252-276) durch einen einzigen Aufruf `resolve_compare_render_options(preset)`; `render_compare_email(...)`/`EmailOutput.send(...)` konsumieren die aufgeloesten Felder |
| `tests/tdd/test_render_effective_fields_access_gate.py` | CREATE | Src-weiter AST-Struktur-Test (AC-3): scannt alle `.py`-Dateien unter `src/services/` + `src/output/` (ausser Whitelist: Resolver-Modul selbst, `src/app/loader.py`, `src/app/models.py`) auf Direktzugriffe der 7 `RENDER_EFFECTIVE_FIELDS`; RENDER_NEUTRAL-Felder werden NICHT geprueft |
| `tests/tdd/test_preview_render_options_parity.py` | CREATE | Bug-Nachweis AC-1: Vorschau und Versand liefern fuer denselben Trip dieselbe Format-Entscheidung; `trip.display_config.show_compact_summary` bleibt nach einem Preview-Aufruf unveraendert (rot vor Fix, gruen danach) |
| `tests/tdd/test_compare_render_options_resolver.py` | CREATE | AC-2: Compare-Preset mit deaktivierter Metrik/Sektion fehlt in der gerenderten Mail; Default `top_n=3` + Clamp 1..10 + Log-Warnung bleiben erhalten |

### Estimated Changes
- Files: 3 src (MODIFY) + 3 Test (CREATE)
- LoC: ~120-150 src-Delta (unter Limit 250; Aufschluesselung: `preview_service.py` ~10-15, `report_config_resolver.py` Compare-Erweiterung ~50-70, `scheduler_dispatch_service.py` ~15-25 netto). Test-Dateien kommen zusaetzlich hinzu (~150-200 LoC), zaehlen nach dem Praezedenzfall der Scheibe-A-Spec nicht in dasselbe Budget wie der Src-Delta, werden aber im Blick behalten.
- #954 (Telegram/SMS-Fussleisten-Gating): opportunistisch ~40-60 LoC zusaetzlich — passt rechnerisch noch unter 250, wird aber NUR mitgenommen wenn waehrend der Implementierung tatsaechlich Kapazitaet bleibt. Sonst Known-Limitation-Ruecklauf an #954.

## Implementation Details

**1. Vorschau-Pfad (`preview_service.py`).** `_build_report` ruft nach dem
Ermitteln von `stage`/`stage_stats` einmal
`resolve_report_render_options(trip.report_config, trip.display_config, report_type)`
auf (Vorbild: `trip_report_scheduler.py:634-639`). Das Ergebnis wird als
zusaetzliches Argument an `_render_email(...)` gereicht, das es
unveraendert an `format_email(..., render_options=render_options)`
weiterreicht. Die Zeilen 120-121 (Patch-Hack-Mutation von
`trip.display_config.show_compact_summary`) werden ersatzlos entfernt —
`ReportRenderOptions.show_compact_summary` traegt den Wert bereits.

**2. Compare-Pfad (`report_config_resolver.py` + `scheduler_dispatch_service.py`).**
Analog zu `ReportRenderOptions` entsteht eine zweite, unabhaengige frozen
Dataclass `CompareRenderOptions` im selben Modul (kein neues Modul —
selbe Verantwortung: Config-Dict -> explizite Optionen):

```
top_n_details: int          # Default 3, geclampt auf 1..10
enabled_metrics: ...        # resolve_enabled_metrics(dc.get("active_metrics"))
hourly_metrics: ...         # resolve_hourly_metrics(dc.get("hourly_metrics"))
hourly_enabled: bool        # preset.get("hourly_enabled", True) — TOP-LEVEL Feld
```

`resolve_compare_render_options(preset: dict) -> CompareRenderOptions` ist
eine reine Funktion (kein I/O, keine Mutation von `preset`), die exakt das
heutige Verhalten aus `scheduler_dispatch_service.py:252-276` reproduziert
(inkl. `try/except (TypeError, ValueError)` fuer ungueltiges `top_n`,
`logger.warning` bei Clamp/Fehlwert). `send_one_compare_preset` ruft die
Funktion einmal auf und liest die 4 Felder aus dem Rueckgabeobjekt statt
aus dem rohen `preset["display_config"]`-Dict.

**3. Struktur-Gate.** Der neue Test in `tests/tdd/test_render_effective_fields_access_gate.py`
uebernimmt das Alias-Erkennungsmuster aus
`test_report_config_scheduler_structure.py` (`_collect_aliases`), erweitert
den Scan aber von einer festen Dateiliste auf `glob("src/services/**/*.py")`
+ `glob("src/output/**/*.py")`. Whitelist (keine Verstoss-Pruefung):
`src/services/report_config_resolver.py` selbst, `src/app/loader.py`,
`src/app/models.py`. Geprueft werden AUSSCHLIESSLICH die 7
`RENDER_EFFECTIVE_FIELDS` aus dem Resolver-Modul (importiert, keine
Kopie) — RENDER_NEUTRAL-Felder (`morning_time`, `evening_time`,
`wind_exposition_min_elevation_m`, `alert_on_changes`, `alert_preset`,
`send_email`/`send_sms`/`send_telegram` etc.) werden NICHT gescannt und
duerfen bei bestehenden Direktzugriffen (z. B. `stage_weather.py`,
`trip_alert.py`) gruen bleiben.

**4. #954 (opportunistisch).** Falls Budget reicht: Telegram-/SMS-Renderer
gaten ihre Fusszeilen ueber `ReportRenderOptions`-Flags statt eigener
Direktabfrage. Kein eigenstaendiger Abschnitt hier — wird als
Zusatzaenderung an den bereits gelisteten Dateien vorgenommen, falls sie
sauber hineinpasst; sonst entfaellt sie ersatzlos und #954 bleibt offen.

## Expected Behavior

- **Input:** Vorschau-Pfad: `Trip` (mit `report_config`/`display_config`), `report_type`. Compare-Pfad: rohes `preset: dict` (Compare-Preset-JSON).
- **Output:** Vorschau liefert dieselbe `TripReport` (HTML/Plain) wie ein aequivalenter Versand fuer denselben Trip — keine Divergenz zwischen `email_format`/`show_compact_summary` in Preview vs. Versand mehr moeglich. Compare-Versand liest `top_n_details`/`enabled_metrics`/`hourly_metrics`/`hourly_enabled` ausschliesslich aus `CompareRenderOptions`.
- **Side effects:** Keine neuen. Der bestehende Patch-Hack-Seiteneffekt (Mutation von `trip.display_config`) entfaellt — Nettoreduktion an Seiteneffekten.

## Acceptance Criteria

- **AC-1:** Given ein Trip mit `report_config.email_format = "compact"` und `report_config.show_compact_summary = False` / When zuerst die Vorschau (`render_email_preview`) und danach der regulaere Versandpfad fuer denselben Trip/Report-Typ aufgerufen werden / Then treffen beide Pfade dieselbe Format-Entscheidung (beide compact, beide ohne Compact-Summary-Sektion), UND `trip.display_config.show_compact_summary` ist nach dem Preview-Aufruf nachweislich unveraendert (der Patch-Hack mutiert das Bestandsobjekt nicht mehr).
  - Test: `tests/tdd/test_preview_render_options_parity.py` — ruft beide Pfade mit derselben In-Memory-Trip-Fixture auf und vergleicht die tatsaechlich gerenderte Ausgabe sowie den Zustand von `trip.display_config` vor/nach dem Preview-Aufruf; kein Dateiinhalt-Check, sondern beobachtbares Objektverhalten.

- **AC-2:** Given ein Compare-Preset mit `display_config.active_metrics` ohne eine bestimmte Metrik (z. B. `wind_gust` deaktiviert) / When `send_one_compare_preset` ueber `resolve_compare_render_options(preset)` versendet / Then fehlt die deaktivierte Metrik in der gerenderten Compare-Mail (HTML + Plain), UND ein Preset ohne `top_n` liefert weiterhin den Default 3, ein Preset mit `top_n=15` wird weiterhin auf 10 geclampt (mit Log-Warnung) — exakt das Bestandsverhalten von `scheduler_dispatch_service.py:252-276`.
  - Test: `tests/tdd/test_compare_render_options_resolver.py` — ruft `resolve_compare_render_options()` mit mehreren Preset-Varianten (fehlend/gueltig/ungueltig/out-of-range) auf und prueft das resultierende `CompareRenderOptions`-Objekt sowie (mind. ein Fall) die tatsaechlich gerenderte Mail auf Ab-/Anwesenheit der Metrik.

- **AC-3:** Given der komplette Quellbaum unter `src/services/` und `src/output/` nach dem Umbau / When der neue Struktur-Test per `ast.parse`/`ast.walk` alle Dateien ausserhalb der Whitelist auf Direktzugriffe der 7 `RENDER_EFFECTIVE_FIELDS` untersucht / Then schlaegt der Test bei jedem gefundenen Direktzugriff mit exaktem Datei:Zeile-Fund fehl, UND bestehende RENDER_NEUTRAL-Zugriffe (`morning_time` in `trip_report_scheduler.py`, `wind_exposition_min_elevation_m` in `stage_weather.py`, `alert_on_changes`/`alert_preset` in `trip_alert.py`) bleiben unveraendert gruen.
  - Test: `tests/tdd/test_render_effective_fields_access_gate.py` — provoziert vor dem Fix (Preview-Patch-Hack) einen roten Fund mit Datei+Zeile, ist nach dem Umbau vollstaendig gruen; enthaelt einen Gegenprobe-Fall (RENDER_NEUTRAL-Zugriff bleibt unbeanstandet).

## Known Limitations

- **F001 (geerbt aus Scheibe A, #1199):** Der AST-Gate ist weiterhin blind fuer `getattr(rc, "feld")`-Zugriffe — nicht Teil dieser Scheibe, dokumentiert und getriaged.
- **#954 (Telegram/SMS-Fusszeilen-Gating):** wird nur mitgenommen, wenn das LoC-Budget (250) nach den drei Kernteilen noch Spielraum laesst. Falls nicht: Issue #954 bleibt offen, kein Teil-Fix wird als "erledigt" markiert.
- **Legacy-CLI-Pfad** wird NICHT auf den Resolver umgestellt — #1131 entfernt ihn ohnehin; Portierung waere verschwendete Arbeit.
- **Compare-Preset-Persistenzformat** (rohes `dict`, kein typisiertes Modell) bleibt unveraendert — `resolve_compare_render_options()` liest defensiv mit `.get()`, aendert aber nichts an der Speicherstruktur von `compare_presets.json`.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Erweiterung des in Scheibe A (#1208) bereits etablierten Resolve-Patterns um eine zweite, strukturell gleichartige Variante (`CompareRenderOptions`) im selben Modul, sowie Ausweitung des dort eingefuehrten Struktur-Gates von einer festen Dateiliste auf den vollen `src/services/`+`src/output/`-Baum. Keine neue Systemgrenze, kein neuer externer Vertrag, kein Technologiewechsel — daher wie Scheibe A kein eigenstaendiger ADR-Eintrag noetig.

## Test Coverage

- `tests/tdd/test_preview_render_options_parity.py`: AC-1, mock-frei, In-Memory-Trip-Fixture, Vorbild `test_issue_811_mode_matrix.py`.
- `tests/tdd/test_compare_render_options_resolver.py`: AC-2, mock-frei, Preset-Fixtures aus Bestandswerten von `scheduler_dispatch_service.py`.
- `tests/tdd/test_render_effective_fields_access_gate.py`: AC-3, AST-Assertion nach Vorbild `test_report_config_scheduler_structure.py`, jedoch src-weiter Scan statt fester Dateiliste.

## Changelog

- 2026-07-11: Initial spec erstellt — Issue #1209 (Scheibe B von #1203), erweitert Scheibe A (#1208)
