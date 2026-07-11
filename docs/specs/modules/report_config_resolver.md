---
entity_id: report_config_resolver
type: module
created: 2026-07-10
updated: 2026-07-10
status: draft
version: "1.1"
tags: [reporting, email, config, resolver, rework]
---

<!-- Issue #1208 -- Scheibe A von #1203; erledigt Bug #1102 mit -->

# Report-Config-Resolver (Scheibe A)

## Approval

- [x] Approved (PO 'go' 2026-07-10)

## Purpose

Ein zentraler Resolver loest `TripReportConfig` (und `UnifiedWeatherDisplayConfig`)
eines Trips VOLLSTAENDIG und an EINER Stelle in ein explizites
`ReportRenderOptions`-Objekt auf. Der E-Mail-Versandpfad (Scheduler ->
`notification_service` -> `TripReportFormatter.format_email`) konsumiert nur noch
dieses Objekt statt einzelner Hand-Durchreichungen. Das schliesst die Luecke, die
Bug #1102 verursacht hat (`email_format`/`show_outlook` wurden im gesamten
Versandpfad nie aus `report_config` gelesen, Defaults griffen immer), und
verhindert strukturell, dass ein neues Config-Feld kuenftig stillschweigend
wirkungslos bleibt.

## Source

- **File:** `src/services/report_config_resolver.py` (NEU)
- **Identifier:** `class ReportRenderOptions`, `def resolve_report_render_options()`, `RENDER_NEUTRAL`

Betroffene Schicht: Python-Core / Domain-Backend (`src/services/`,
`src/output/renderers/`) -- kein Frontend-, kein Go-API-Anteil.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `TripReportConfig` (`src/app/models.py:701-764`) | Datenklasse | Quelle der 27 Config-Felder, die der Resolver klassifiziert (7 render-wirksam, 20 RENDER_NEUTRAL) |
| `UnifiedWeatherDisplayConfig` (`src/app/models.py:552-650`) | Datenklasse | Wird opak in `ReportRenderOptions.display_config` eingebettet, nicht in Einzelfelder zerlegt |
| `report_type` (str "morning"/"evening") | Parameter | Steuert die Ableitung von `show_multi_day_trend`/`show_daylight` aus `multi_day_trend_reports` |
| `TripReportFormatter.format_email()` (`src/output/renderers/trip_report.py:56-171`) | Funktion | Bekommt optionalen `render_options`-Parameter; Resolver-Fallback bei `render_options=None` erhaelt Bestandsverhalten |
| `trip_report_scheduler.py:637-921` | Modul | Ersetzt 5 Direktzugriffe auf `report_config.*` durch einen Resolver-Aufruf; Patch-Hack (Zeile 779) entfaellt |
| `TripReportRequest` (`src/services/notification_service.py:53-92`) | DTO | Bekommt neues Feld `render_options: Optional[ReportRenderOptions]` |
| `resolve_enabled_metrics()` (`compare_metric_ids.py:23`) | Vorbild | Resolve-zu-Options-Muster fuer Namensgebung/Struktur |
| `StabilityResult` (`src/app/models.py:832`) | Vorbild | Frozen-Dataclass-Stil fuer `ReportRenderOptions` |

## Scope

### Affected Files
| File | Change Type | Description |
|------|-------------|--------------|
| `src/services/report_config_resolver.py` | CREATE | `ReportRenderOptions` (frozen dataclass, 7 render-wirksame Felder + `show_daylight` als Pre-Render-Gate + opakes `display_config`), `RENDER_NEUTRAL` (20 Felder, begruendet), `resolve_report_render_options(report_config, display_config, report_type) -> ReportRenderOptions` |
| `src/output/renderers/trip_report.py` | MODIFY | `format_email()` bekommt optionalen `render_options`-Parameter mit internem Resolver-Fallback (`resolve_report_render_options(...)` wenn `render_options is None`); Hand-Ableitungen (Zeilen 129-139) durch `render_options.*` ersetzt; `email_format`/`show_outlook` erstmals an `render_email()` durchgereicht -- **Mailgate-Trigger** |
| `src/services/trip_report_scheduler.py` | MODIFY | Ein Resolver-Aufruf ersetzt 5 Direktzugriffe (Zeilen 637, 744-756, 779-780 Patch-Hack entfernt, 784, DTO-Bau 863-921); DTO wird mit `render_options=` statt Einzelfeldern befuellt |
| `src/services/notification_service.py` | MODIFY | `TripReportRequest`-DTO bekommt Feld `render_options: Optional[ReportRenderOptions] = None`, Durchreichen an `format_email()` |
| `tests/tdd/test_report_config_render_contract.py` | CREATE | Vertragstest: ueber `dataclasses.fields(TripReportConfig)` parametrisiert, Ebene `format_email()`-Ausgabe (nicht Renderer direkt), Vorbild `test_issue_811_mode_matrix.py` |
| `tests/tdd/test_report_config_scheduler_structure.py` | CREATE | AST-Struktur-Test (AC-3): Scheduler-Pfad enthaelt keinen `report_config.<feld>`-Direktzugriff mehr, Vorbild `test_765_backend_hygiene_compliance.py` |

### Estimated Changes
- Files: 4 src (CREATE/MODIFY) + 2 Test (CREATE)
- LoC: ~150-175 src-Delta (unter Limit 250; Aufschluesselung: Resolver ~90-110, `trip_report.py` ~20, Scheduler ~30-35, `notification_service.py` ~8)

## Implementation Details

`ReportRenderOptions` ist eine `@dataclass(frozen=True)` mit 7
render-wirksamen Feldern plus einem opak eingebetteten `display_config`:

```
email_format: str                 # "full" | "compact"
show_outlook: bool
show_stage_stats: bool
show_stability: bool
show_compact_summary: bool
show_daylight: bool               # NUR Pre-Render-Gate im Scheduler; render-neutral seit #790 (s.u.)
show_multi_day_trend: bool        # aus multi_day_trend_reports + report_type aufgeloest
show_yesterday_comparison: bool
display_config: UnifiedWeatherDisplayConfig
```

`resolve_report_render_options(report_config, display_config, report_type)`
ist der EINZIGE Ableitungspfad zwischen `TripReportConfig` und den
render-wirksamen Optionen. Sie kapselt insbesondere den heutigen
Scheduler-Gate-Einzeiler fuer `show_multi_day_trend` (`report_type in
trip.report_config.multi_day_trend_reports`) und fuer `show_daylight`
(Bestandslogik aus `trip_report_scheduler.py:754`).

Wiring:
- `format_email(..., render_options: Optional[ReportRenderOptions] = None)` --
  bei `None` loest die Funktion intern via `resolve_report_render_options(...)`
  aus dem uebergebenen `report_config`/`display_config` auf. Dadurch bleibt
  `preview_service.py` (Scheibe B, unangetastet) weiterhin kompatibel, weil sich
  ihr Bestandsverhalten durch den Fallback nicht aendert.
- Scheduler ruft den Resolver genau einmal auf und befuellt `TripReportRequest.render_options`
  statt einzelner Felder; die 5 Direktzugriffe sowie der Patch-Hack
  `trip.display_config.show_compact_summary = trip.report_config.show_compact_summary`
  (`trip_report_scheduler.py:779`) entfallen ersatzlos.
- `notification_service._send_email` braucht KEINE Aenderung: `mail_format` folgt
  bereits `bool(report.email_html)` -- sobald `email_format="compact"`
  durchgereicht wird, setzt der bestehende Mechanismus automatisch
  `X-GZ-Format: compact`.

### RENDER_NEUTRAL -- 20 Felder, kategorisiert und begruendet

| Kategorie | Felder | Begruendung |
|-----------|--------|-------------|
| Metadaten | `trip_id`, `updated_at` | Keine Render-Wirkung, reine Identifikation/Zeitstempel |
| Pre-Render-Gate | `enabled`, `paused_until`, `skip_next` | Entscheiden VOR dem Rendern, ob ueberhaupt versendet wird -- kein Render-Toggle |
| Zeitplanung | `morning_time`, `evening_time` | Steuern WANN der Scheduler laeuft, nicht WAS gerendert wird |
| Kanalwahl | `send_email`, `send_sms`, `send_telegram` | Steuern WELCHER Kanal versendet wird, nicht den Mail-Inhalt selbst |
| Alert-Pfad | `alert_on_changes`, `change_threshold_temp_c`, `change_threshold_wind_kmh`, `change_threshold_precip_mm` | Gehoeren zum separaten Alert-/Deviation-Pfad (`TripAlertService`), nicht zum Briefing-Rendering |
| Pre-Renderer-Service | `wind_exposition_min_elevation_m` | Wird von einem vorgelagerten Exposition-Service konsumiert, bevor `format_email()` aufgerufen wird -- kein direktes Render-Flag |
| Tote #790-Toggles | `show_quick_take_tags`, `show_highlights`, `daily_summary_metrics`, `show_metrics_summary`, `show_daylight` | Werden zwar an `render_email()` uebergeben, aber dort in `**_ignored` bewusst absorbiert (`email/__init__.py`, `html.py:776`, `plain.py:99`; fuer `show_daylight` wurde der Tageslicht-Block in #790 aus den Renderern entfernt, bestaetigt `test_issue_790_briefing_simplify.py`) -- strukturell wirkungslos. Reaktivierung ist ausdruecklich NICHT Scope dieses Issues (PO-Entscheidung 2026-07-10 im GREEN-Review; Folge-Issue zum Entfernen/Reaktivieren des Toggles angelegt). `show_daylight` bleibt als Pre-Render-Gate in `ReportRenderOptions`, weil der Scheduler damit die Tageslicht-BERECHNUNG gated |

Der Vertragstest (AC-2) verifiziert diese Liste aktiv: jedes Feld von
`TripReportConfig`, das NICHT in den 7 render-wirksamen Feldern von
`ReportRenderOptions` muendet, MUSS namentlich in `RENDER_NEUTRAL` stehen --
sonst schlaegt der Test mit dem Feldnamen rot.

## Expected Behavior

- **Input:** `TripReportConfig`, `UnifiedWeatherDisplayConfig`, `report_type` ("morning"/"evening")
- **Output:** `ReportRenderOptions` (frozen dataclass) mit den 7 render-wirksamen Feldern korrekt aufgeloest; `format_email()`-Aufrufer erhalten identisches Rendering wie zuvor, ausser bei `email_format`/`show_outlook` (Bugfix #1102 -- diese wirken jetzt erstmals)
- **Side effects:** Keine -- reine Aufloesungsfunktion ohne I/O. Der Patch-Hack, der bisher `trip.display_config` mutiert hat, entfaellt (weniger Seiteneffekte als vorher)

## Acceptance Criteria

- **AC-1:** Given ein Trip mit persistiertem `report_config.email_format = "compact"` auf Staging / When der Scheduler-/Send-Pfad eine Briefing-Mail ausloest (z. B. via `POST /api/trips/{id}/send`) / Then traegt die tatsaechlich zugestellte Mail im Postfach `gregor-test@henemm.com` den Header `X-GZ-Format: compact` (IMAP-Nachweis wie bei #1102 dokumentiert) -- dieses AC erledigt Bug #1102 final.
  - Test: Live-Schicht (Staging), kein Kern-Test -- IMAP-Verifikation der real zugestellten Mail, kein Mock.

- **AC-2:** Given ein ueber `dataclasses.fields(TripReportConfig)` parametrisierter Vertragstest auf Ebene der `format_email()`-Ausgabe / When jedes einzelne Feld einzeln von seinem Default abweichend gesetzt wird / Then aendert sich entweder das gerenderte Output (HTML/Plain), oder das Feld ist mit Begruendung in `RENDER_NEUTRAL` deklariert -- ein Feld, das weder Output-Wirkung zeigt noch deklariert ist, laesst den Test mit dem exakten Feldnamen rot fehlschlagen; auch ein neu hinzugefuegtes, nicht deklariertes Feld schlaegt automatisch rot an.
  - Test: `tests/tdd/test_report_config_render_contract.py`, mock-frei, Segment-Fabrik nach Vorbild `test_issue_811_mode_matrix.py`.

- **AC-3:** Given `trip_report_scheduler.py` nach dem Umbau / When der Quellcode per `ast.parse`/`ast.walk` auf direkte Attributzugriffe der Form `report_config.<feld>` untersucht wird / Then finden sich ausserhalb einer Whitelist (Resolver-Modul selbst, Loader, Modell-Definitionen) KEINE solchen Direktzugriffe mehr -- der gesamte Scheduler-Pfad liest render-relevante Werte ausschliesslich ueber `ReportRenderOptions`.
  - Test: `tests/tdd/test_report_config_scheduler_structure.py`, AST-Assertion nach Vorbild `test_765_backend_hygiene_compliance.py`.

- **AC-4:** Given ein Default-Trip ohne explizit gesetzte `report_config`-Abweichungen (alle Felder auf Standardwert) / When die Briefing-Mail nach dem Umbau gerendert wird / Then ist das Ergebnis (HTML + Plain, alle Sektionen und Header) identisch zum Rendering vor dem Umbau -- der interne Resolver-Fallback in `format_email()` reproduziert exakt das heutige Verhalten, es entsteht kein ungewollter Regressions-Nebeneffekt.
  - Test: Teil von `tests/tdd/test_report_config_render_contract.py`, Vergleich Default-Konfiguration vor/nach Umbau, mock-frei.

## Known Limitations

- **preview_service/Compare/CLI bleiben unangetastet** (Scheibe B, Issue #1209). Praezisierung nach Adversary-Befund F002 (2026-07-11): Weil `preview_service.py:157-166` `format_email()` ohne `render_options` aufruft, wirkt der interne Resolver-Fallback fuer `email_format`/`show_outlook` bereits auch im Preview-Pfad (empirisch belegt: Preview-compact vorher 29 KB HTML, nachher 0). Der Preview-Pfad bleibt fuer diese Felder jedoch UNTESTET; `show_compact_summary` laeuft dort weiter ueber den bestehenden Patch-Hack (`preview_service.py:120-121`). Explizite Umstellung + Testabdeckung = Scheibe B.
- **`display_config` wird NICHT in Einzelfelder zerlegt** -- es bleibt als Ganzes opak in `ReportRenderOptions.display_config` eingebettet, so wie es heute bereits als Ganzes durchgereicht wird. Die von #1102/#1208 geschlossene Luecke betrifft ausschliesslich `report_config`-Felder.
- **Tote #790-Toggles werden NICHT reaktiviert.** `show_quick_take_tags`, `show_highlights`, `daily_summary_metrics`, `show_metrics_summary` UND `show_daylight` (Befund aus dem Vertragstest, PO-Entscheidung 2026-07-10) bleiben strukturell wirkungslos und werden als render-neutral deklariert. Eine Reaktivierung waere eine eigenstaendige Verhaltensaenderung ausserhalb dieses Issues (Folge-Issue angelegt).
- **`_send_service_error_email`** (`notification_service.py:802-804`) liest `report_config.send_sms`/`send_email` direkt fuer das Routing von Fehler-Mails. Dies bleibt bewusst ausserhalb des Scopes -- es handelt sich um Kanalwahl-Routing im Fehlerfall, kein Render-Feld, daher nicht Teil der AC-3-Struktur-Pruefung.
- **Gewollte Verhaltensaenderung:** Ab Deploy erhalten Trips mit persistiertem `email_format = "compact"` erstmals tatsaechlich Compact-Mails statt (wie bisher faelschlich) immer Full-Mails. Dies ist der beabsichtigte Bugfix von #1102, kein Nebeneffekt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Rein internes Refactoring/Struktur-Fix eines bestehenden Datenflusses (Resolve-Pattern), keine neue Systemgrenze, kein neuer externer Vertrag, kein Technologiewechsel -- daher kein eigenstaendiger ADR-Eintrag noetig.

## Test Coverage

- `tests/tdd/test_report_config_render_contract.py`:
  - Vertragstest ueber alle `TripReportConfig`-Felder (AC-2)
  - Default-Regressionstest (AC-4)
  - KEINE Mocks -- echte `format_email()`-Aufrufe mit Segment-Fabrik nach Vorbild `test_issue_811_mode_matrix.py`
- `tests/tdd/test_report_config_scheduler_structure.py`:
  - AST-Struktur-Assertion gegen `trip_report_scheduler.py` (AC-3), Vorbild `test_765_backend_hygiene_compliance.py`
- AC-1 wird NICHT im Kern getestet (Live-Schicht/Staging), sondern im Rahmen der Post-Push-Staging-Verifikation per IMAP nachgewiesen -- siehe `docs/reference/operations_playbook.md`.

## Changelog

- 2026-07-10: Initial spec erstellt -- Issue #1208 (Scheibe A von #1203), erledigt Bug #1102 mit
- 2026-07-10: v1.1 -- `show_daylight` von render-wirksam nach RENDER_NEUTRAL umklassifiziert (Befund des Vertragstests: Tageslicht-Block seit #790 aus den Renderern entfernt, Toggle wirkungslos; PO-Entscheidung im GREEN-Review). 7 render-wirksame / 20 neutrale Felder.
- 2026-07-11: Scheibe B implementiert (Issue #1209) -- Preview-/Compare-Pfad auf `CompareRenderOptions`-Resolver umgestellt, Struktur-Gate gegen Direktzugriffe auf render-wirksame Felder. Spezifikation: `docs/specs/modules/report_config_resolver_slice_b.md`.
