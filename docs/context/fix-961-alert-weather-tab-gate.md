# Context: fix-961-alert-weather-tab-gate

## Request Summary

Issue #961: Alarm-Regeln aus `metric_alert_levels` werden unabhängig davon
ausgewertet, ob die zugehörige Metrik auf dem Weather-Tab (`display_config.metrics`)
aktiv ist. Vollständiger Vertrag, der wiederhergestellt werden muss:

```
should_fire = weather_tab_enabled AND level != 'off'
```

Zwei symmetrische Lücken, beide bereits per TDD-RED bewiesen und doppelt unabhängig
adversary-verifiziert (CONFIRMED):
1. **Deaktivieren-Lücke:** verwaister `metric_alert_levels`-Eintrag feuert weiter,
   obwohl die Metrik auf dem Weather-Tab deaktiviert wurde.
2. **Aktivieren-Lücke:** neu aktivierte Weather-Tab-Metrik feuert nie, solange der
   Nutzer den Alerts-Tab nicht manuell anfasst — obwohl die UI "Standard" (aktiv)
   suggeriert.

Offene Design-Frage: `snow_line` hängt an ZWEI Weather-Tab-Metriken
(`snowfall_limit`, `freezing_level`) — Policy bei gemischtem Zustand muss die Spec
explizit festlegen.

## Related Files

| File | Relevance |
|------|-----------|
| `src/services/trip_alert.py:238-253` (`_select_change_detector`) | Liest ausschließlich `metric_alert_levels`, prüft nie `display_config.metrics[].enabled`. Zentrale Fix-Stelle. |
| `src/services/alert_preset.py:91-121` (`expand_per_metric_levels`) | Wandelt `metric_alert_levels`-Dict in `AlertRule`-Liste um, iteriert nur vorhandene Keys — kein Backfill für neu aktivierte Metriken. |
| `src/app/models.py:578` (`UnifiedWeatherDisplayConfig.is_metric_enabled`) | Bereits vorhandener, aber toter Baustein (0 Aufrufer in `src/`) — genau das, was im Fix gebraucht wird. |
| `src/services/weather_change_detection.py:300-315` (`from_display_config`) | Schwester-Factory, die `enabled=False`-Metriken bereits korrekt überspringt — Vorbild-Pattern für den Fix. |
| `src/services/weather_change_detection.py:41-77` (`_ALERT_METRIC_TO_SUMMARY_FIELD`, `_ALERT_METRIC_TO_CATALOG_ID`) | Bestehende AlertMetric→Feld/Katalog-Zuordnung; Fix braucht analog eine Catalog-ID→AlertMetric-Rückrichtung. |
| `frontend/src/lib/components/alerts-tab/alertMetricTable.ts:279-323` (`CATALOG_TO_ALERT_METRICS`, `activeAlertableMetrics`) | Bereits existierende Frontend-Zuordnung Catalog-ID→AlertMetric (inkl. Mehrfach-Mapping für `snow_line`) — Vorlage für ein Backend-Äquivalent, damit Frontend-Anzeige und Backend-Auswertung denselben Vertrag nutzen. |
| `frontend/src/lib/components/alerts-tab/AlertMetricLevelTable.svelte:97` | Zeigt `level={levels[metric] ?? 'standard'}` — rein visueller Default ohne Persistenz; Ursache der Aktivieren-Lücke auf UI-Seite. |
| `frontend/src/lib/components/alerts-tab/AlertsTab.svelte:32-69` | Lädt/speichert `currentLevels` 1:1 aus/nach `metric_alert_levels`, ohne Abgleich mit `activeAlertableMetrics()` beim Speichern. |
| `src/app/loader.py:578,1069-1074` | Persistiert `metric_alert_levels` unverändert (Read-Modify-Write ohne Filterung) — beim Fix zu beachten (keine Datenverluste, siehe CLAUDE.md Daten-Schema-Reworks). |
| `tests/tdd/test_bug_alert_ignores_weather_tab_disable.py` | RED-Test Deaktivieren-Lücke (5 failed / 4 passed), adversary CONFIRMED. |
| `tests/tdd/test_bug_alert_metric_lifecycle_matrix.py` | RED-Test volle Matrix, 12 Metriken × 6 Zustände (24 failed / 49 passed), adversary CONFIRMED inkl. dokumentierter offener Frage zu `snow_line`. |
| `data/users/henning/trips/74de939c.json` | Realer Produktions-Beleg (Trip "Lottis Abschiedfahrradtour") für die Deaktivieren-Lücke. |

## Existing Patterns

- **Catalog-ID → AlertMetric Mapping existiert bereits, aber nur im Frontend**
  (`CATALOG_TO_ALERT_METRICS` in `alertMetricTable.ts`). Der Fix sollte dieses
  Mapping NICHT duplizieren, sondern eine äquivalente, backend-seitige Quelle
  nutzen oder das Frontend-Mapping als Referenz 1:1 spiegeln (Einzelquelle
  anstreben, siehe CLAUDE.md "Code-Duplikate konsolidieren").
- **`from_display_config()` filtert bereits korrekt nach `enabled`** — zeigt,
  dass das Codebase-Pattern für "nur aktive Metriken berücksichtigen" bekannt
  und etabliert ist, nur eben nicht auf den `metric_alert_levels`-Pfad
  angewendet wurde.
- **Issue #946 Prinzip "Single Source of Truth"**: `metric_alert_levels` bleibt
  die einzige *Konfigurationsquelle* — der Fix darf das nicht aufweichen
  (kein Rückfall auf `from_display_config()`/`alert_preset`), sondern muss
  `metric_alert_levels` nur noch gegen den aktuellen Weather-Tab-Status filtern/
  ergänzen.

## Dependencies

- **Upstream (wird von `_select_change_detector` genutzt):** `expand_per_metric_levels()`,
  `UnifiedWeatherDisplayConfig.metrics`/`metric_alert_levels`/`is_metric_enabled()`.
- **Downstream (nutzt `_select_change_detector`):** `TripAlertService.check_and_send_alerts()`
  (Zeile 108) — der reale Scheduler-Pfad (`check_all_trips()`), der Alarme tatsächlich
  versendet. Jede Änderung wirkt sich direkt auf den Live-Alarmversand aus.
- **Frontend-Konsument:** `AlertsTab.svelte` (Anzeige + Save), `AlertMetricLevelTable.svelte`
  (Zeilen-Rendering) — falls der Fix auch eine Persistenz-Bereinigung
  (verwaiste Einträge entfernen) vorsieht, ist dieser Pfad mitbetroffen.

## Existing Specs

- `docs/specs/modules/fix_946_alert_architecture.md` — führte `metric_alert_levels`
  als einzige Alert-Quelle ein; AC-6/AC-8 betreffen `freezing_level`-Wiring
  (separates, bereits als Issue #959 verfolgtes Problem).
- `docs/specs/modules/feat_864_859_alert_presets.md` — AC-1 (Zeile 302, Projektions-
  Prinzip: "zeigt der Tab exakt die im Wetter-Metriken-Tab aktiv gewählten ...
  Metriken") ist die spezifikatorische Grundlage für den hier geforderten Vertrag.
  AC-7 (Zeile 320) bedeutet dort ausdrücklich NUR Auto-Save-bei-Klick, NICHT
  Auto-Sync bei Weather-Tab-Aktivierung (Korrektur einer ursprünglichen
  Fehlzuschreibung, siehe Issue-#961-Kommentare).

## Risks & Considerations

- **Scope-Grenze:** Issue #959 (freezing_level komplett unverdrahtet) ist ein
  separates, bereits eigenständig gemeldetes Problem — sollte nicht in diesem
  Fix mit-gelöst werden, außer die gewählte Lösung (Catalog-ID→AlertMetric-Mapping
  im Backend) deckt es als Nebeneffekt ab. Falls ja: explizit in der Spec vermerken,
  nicht stillschweigend.
- **snow_line Mehrfach-Mapping:** Muss die Spec explizit entscheiden (siehe
  `test_documents_open_question_mixed_snow_line_catalog_state` in der Matrix-Testdatei).
- **Keine Datenverluste:** Bestehende `metric_alert_levels`-Einträge für aktuell
  deaktivierte Metriken dürfen nicht ungefragt aus der Trip-JSON gelöscht werden
  (Reaktivierung soll die alte Stufe wiederherstellen können) — Fix sollte eher
  beim AUSWERTEN filtern als beim Speichern löschen, sofern die Spec nicht
  bewusst Cleanup vorsieht (siehe CLAUDE.md "Daten-Schema-Reworks").
- **Live-Wirkung:** Der Scheduler läuft alle 30 Minuten (`check_all_trips`) —
  jede Trip-JSON mit ähnlichem Muster (Metrik deaktiviert, aber alter Alert-Level
  vorhanden) ist von der Deaktivieren-Lücke potenziell schon jetzt betroffen.

## Analysis

### Type
Bug (zwei symmetrische Lücken in einem bestehenden Vertrag, kein neues Feature).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/weather_change_detection.py` | MODIFY | `_ALERT_METRIC_TO_CATALOG_ID` von `dict[AlertMetric, str]` auf `dict[AlertMetric, tuple[str, ...]]` erweitern, 5 fehlende Metriken ergänzen (`visibility`, `precipitation_change`, `wind_change`, `temperature_change`, `freezing_level`), neue Helper-Funktion `is_alert_metric_active()`. |
| `src/services/alert_preset.py` | MODIFY | `expand_per_metric_levels()` bekommt zusätzlichen `display_config`-Parameter; filtert deaktivierte Metriken heraus UND synthetisiert `'standard'`-Default für aktive, aber unkonfigurierte Metriken. |
| `src/services/trip_alert.py` | MODIFY | `_select_change_detector()` reicht `trip.display_config` an `expand_per_metric_levels()` durch. |
| `tests/tdd/test_bug_alert_ignores_weather_tab_disable.py` | bereits vorhanden (RED) | Muss nach Fix grün werden. |
| `tests/tdd/test_bug_alert_metric_lifecycle_matrix.py` | bereits vorhanden (RED) | Muss nach Fix grün werden (inkl. dokumentierter Beobachtung zu `snow_line`-Mehrfach-Mapping). |

Kein Frontend-Scope nötig — die Anzeige (`activeAlertableMetrics()`) ist bereits korrekt.

### Scope Assessment
- Files: 3 Backend-Dateien (MODIFY), 2 Testdateien bereits vorhanden
- Estimated LoC: +45 bis +65 (Backend, produktiv)
- Risk Level: LOW — der Fix engt einen bereits laut Spec (#864 AC-1) gebrochenen Vertrag ein, kein bewusst gewolltes Verhalten wird entfernt. Verhaltensänderung in beide Richtungen (weniger Fehlalarme, mehr korrekte Alarme) ist beabsichtigt und sollte im Release-Kommentar erwähnt werden.

### Technical Approach
`_ALERT_METRIC_TO_CATALOG_ID` (bereits als "Single Source" dokumentiert, aktuell nur für Vergleichsrichtung genutzt) wird zur kanonischen Backend-Zuordnung Catalog-ID→AlertMetric ausgebaut (Werte als Tupel für Mehrfach-Mappings wie `snow_line`). Eine neue Helper-Funktion `is_alert_metric_active(alert_metric, display_config)` prüft `any(display_config.is_metric_enabled(cid) for cid in ...)` — nutzt damit den bisher toten Baustein `is_metric_enabled()`. Diese eine Prüfung, aufgerufen in `expand_per_metric_levels()`, schließt symmetrisch BEIDE Lücken: filtert verwaiste Einträge heraus (Deaktivieren-Lücke) UND synthetisiert fehlende Standard-Einträge für aktive, aber unkonfigurierte Metriken (Aktivieren-Lücke). Kein Duplikat zum Frontend-Mapping nötig (Python/TS nicht ohne Build-Schritt teilbar; beide Seiten unabhängig durch Tests abgesichert).

**snow_line-Mehrfach-Mapping-Policy:** "Mindestens eine Weather-Tab-Metrik aktiv" (OR), nicht "beide". Begründung: konservativ im Sinne von "keine Alarme verlieren"; als Übergangslösung mit Verweis auf Issue #959 (dortige Konsolidierung wird `snow_line` vermutlich ohnehin auflösen) zu kommentieren.

**Keine aktive Bereinigung von `metric_alert_levels`:** Nur Filterung zur Auswertungszeit — Reaktivierung einer Metrik muss die alte Stufe automatisch wiederherstellen (keine Datenverluste, CLAUDE.md-Konvention).

### Dependencies
Siehe oben (Upstream/Downstream) — zusätzlich bestätigt: keine weiteren Aufrufer von `expand_per_metric_levels()` oder `_select_change_detector()` außerhalb von `trip_alert.py`, die von der Signaturänderung betroffen wären.

### Open Questions
- [x] snow_line-Mehrfach-Mapping → OR-Policy, als Übergangslösung dokumentiert (siehe oben)
- [ ] Soll die Spec-Phase Issue #959 (freezing_level-Wiring) explizit mit abdecken oder strikt draußen halten? → Empfehlung: draußen halten, separates Issue, nur als Kommentar/Verweis erwähnen.
