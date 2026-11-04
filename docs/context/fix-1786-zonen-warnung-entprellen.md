# Context: fix-1786-zonen-warnung-entprellen

## Request Summary
Die Warnung "Keine aufloesbare Zeitzone ... es gilt Weltzeit (UTC)" aus `utils.timezone.first_resolvable_tz()` feuert je Aufruf und Cron-Takt (bis 312x/Tag/Preset). Sie soll sichtbar bleiben (AC-15 aus #1726), aber entprellt werden: einmal je (Preset, Ortstag). Zusaetzlich pruefen, ob der Dispatch-Pfad die Zone erst NACH den Guards aufloesen kann.

## Related Files
| File | Relevance |
|------|-----------|
| src/utils/timezone.py:86 | `first_resolvable_tz` - die EINE Stelle mit `logger.warning` (Entprellung gehoert hierher) |
| src/services/compare_slot_scheduler.py:128 | `_preset_ortszeit` -> Briefing-Dispatch (stuendlich); Aufloesung steht VOR End-Date-/Wochentag-Guard in `presets_due_for_hour` |
| src/services/compare_alert.py:879 | Compare-Alarm (*/15), `_build_eval_config` |
| src/services/compare_radar_alert.py:250 | Radar-Alarm (7,22,37,52) |
| src/services/compare_official_alert.py:202 | Amtliche Alarme (*/15) |
| src/services/compare_preview_service.py:241, api/routers/compare.py:67 | Weitere Aufrufer (Vorschau, Sofort-Vergleich) mit `context_label` |
| src/services/alert_daily_limit.py | Vorbild fuer neustartfesten Zustand (verworfen/teurer) |

Hinweis: Zeilennummern im Issue sind veraltet (alte Stellen: 138/490/135/121); aktuelle siehe oben.

## Existing Patterns
- Warnung ist Zustandsmeldung -> prozesslokales Set/Dict `(context_label, Ortstag)` ist billig und ausreichend (Verlust beim Neustart = hoechstens 1 Zeile mehr).
- Tests nutzen Naht `css.first_resolvable_tz` per monkeypatch (tests/tdd/test_briefing_sammellauf_einheit_abschottung.py:628, test_alarmlauf_einheit_abschottung.py:869) - Signatur/Name muss stabil bleiben.
- Bestehende Tests rufen `first_resolvable_tz(..., context_label=...)` direkt (u.a. tests/tdd/test_alert_suppression_reason.py) - Rueckgabe UTC darf sich nicht aendern.

## Dependencies
- Upstream: `resolve_location_tz`, `logger`, UTC.
- Downstream: alle oben genannten Aufrufer; Rueckgabewert (UTC) bleibt unveraendert, nur das Logging aendert sich.

## Existing Specs
- #1726 / AC-15 (Zeitzonen-Epic #1722): Fall darf nicht still geschehen. Passende Spec unter docs/specs/ in Phase 2 zu suchen.

## Risks & Considerations
- AC-15 nicht aushoehlen: mindestens EINE Zeile je (Preset, Ortstag) muss bleiben.
- Leeres `context_label` (Sofort-Vergleich) -> Schluessel sinnvoll behandeln (nicht alle Aufrufer ohne Label zusammenwerfen, oder Label-lose Aufrufe unentprellt lassen).
- "Ortstag" bei unaufloesbarer Zone = UTC-Tag (es gibt ja keine Ortszone).
- Test-Isolation: modulglobaler Zustand muss in Tests rücksetzbar sein (Fixture/Reset-Funktion), sonst Reihenfolge-Abhaengigkeit.
- Guard-Reihenfolge im Dispatch: Aufloesung nach Guards verschieben ist optional; Entprellung allein behebt das Hauptproblem. Verschieben kann Verhalten (Faelligkeit) beruehren - in Phase 2 abwaegen.
- Issue ist als `status:deferred`/`priority:low` gelabelt, aber `go-live-pflicht` - PO hat den Workflow gestartet.

## Analysis

### Type
Bug (Betriebs-Sichtbarkeit / Log-Rauschen; Rueckgabewert und Fachverhalten unveraendert)

### Befund: Guard-Verschiebung ist NICHT moeglich (Issue-Vorschlag widerlegt)
Im Dispatch-Pfad (`presets_due_for_hour`) werten `end_date`-Guard und Wochentag-Guard gegen den **Ortstag** (`today = vor_ort.date()`, #1727 S5b/ADR-0044). Der Ortstag braucht die Zone, also muss `first_resolvable_tz` VOR diesen Guards laufen. Nur `is_silenced` steht schon davor (und greift korrekt). Verschieben wuerde Faelligkeit/Wochentag falsch rechnen. -> Nur Entprellung; kein Eingriff in die Guard-Reihenfolge.
Weitere Aufrufer (Stand `origin/main`): `compare_slot_scheduler._preset_ortszeit`, `scheduler_dispatch_service` (Auto-Pause :131, :913), `compare_alert:879`, `compare_radar_alert:250`, `compare_official_alert:202`, `compare_preview_service:241`, `api/routers/compare.py:67`.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| src/utils/timezone.py | MODIFY | Entprellung im `logger.warning`-Zweig von `first_resolvable_tz`; Reset-Helfer fuer Tests |
| tests/tdd/test_zonen_warnung_entprellt.py | CREATE | Verhaltenstests (caplog, echte Aufrufe) |
| docs/specs/modules/fix_1786_zonen_warnung_entprellen.md | CREATE | Spec (Phase 3) |

### Scope Assessment
- Files: 2 Code/Test + Spec
- Estimated LoC: +25 Produktiv, +60 Test
- Risk Level: LOW (nur Logging; Rueckgabe UTC bleibt)

### Technical Approach
Modulglobales `set[(context_label, utc_tag)]` in `utils/timezone.py`. Beim unaufloesbaren Fall: Schluessel `(context_label, now_utc.date())`; steht er im Set -> kein Log (aber weiterhin UTC zurueck), sonst loggen und eintragen. Tagwechsel = neuer Schluessel -> je Tag eine Zeile je Preset (AC-15 bleibt: nie still). Alte Tage beim Eintragen verwerfen (Set bleibt klein). Thread-Sicherheit: Lock oder atomare Set-Operation (Scheduler/FastAPI-Threads). Leeres `context_label` (kein Preset-Bezug): NICHT entprellen, damit unterschiedliche Aufrufer nicht verschluckt werden. Signatur `first_resolvable_tz(locations, context_label="")` unveraendert (Naht-Monkeypatch in bestehenden Tests). Neustartfeste Variante (alert_daily_limit-Muster) verworfen: Zustandsmeldung, Verlust beim Neustart = max. 1 Zeile mehr. Test-Isolation: autouse-Reset-Fixture in conftest bzw. Reset-Funktion im neuen Test.
Tag-Basis: UTC-Tag (bei unaufloesbarer Zone gibt es keinen Ortstag; kein Zugriff auf `now` im Helfer -> `datetime.now(UTC).date()`; Test per monkeypatch der Uhr im Modul, nicht per Mock der Logik).
Folge: je Preset max. 1 Zeile/Tag statt bis 312; Cron-Takt-uebergreifend, da Schluessel nur Label+Tag.

### Dependencies
Upstream: `resolve_location_tz`, `logger`, `UTC`. Downstream: die 7 Aufrufer oben, Rueckgabe unveraendert.

### Open Questions
- [ ] Keine fuer den PO. (Tag = UTC-Tag, leeres Label unentprellt: technische Entscheidung, in Spec festgehalten.)
