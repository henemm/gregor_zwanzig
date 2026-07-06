# Context: fix-970-971-1011-e2e-ui-drift

## Request Summary
Nach dem v2-Redesign der Wetter-Metriken-Ansicht (#848, #587) erwarten mehrere
Frontend-E2E-Tests und 2 Unit-Tests Test-IDs/Interaktionspfade, die im aktuellen DOM
nicht mehr existieren (Bündel I: #970, #971, #1011). PO-Entscheidung zu #970: Die
Horizon-Chip-Toggle-UI + TablePreview werden **nicht** wiederhergestellt — betroffene
Tests werden offiziell zurückgezogen (permanent geskippt/entfernt), kein neues Feature.

## Related Files

| File | Relevance |
|------|-----------|
| `docs/specs/modules/fix_964_e2e_drift.md` | Vorlage-Spec des Vorgänger-Fixes (#964) — enthält Migrationstabelle alt→neu Test-IDs, aber **teilweise veraltet** (behauptet fälschlich, `table-preview-day-*`/`weather-metrics-tab-checkbox-*` seien noch gültig — das ist genau der #970-Befund, der das revidiert) |
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` (845 Zeilen) | Aktuelle v2-Struktur; importiert `WeatherV2PresetBar`, `WeatherV2Grundauswahl`, `WeatherV2Reihenfolge`, `WeatherV2MailPreview`, `ThresholdMetricRow`, `SavePresetDialog` — **NICHT** `MetricCheckbox`, `TablePreview`, `MetricGroup` |
| `frontend/src/lib/components/trip-detail/MetricCheckbox.svelte`, `TablePreview.svelte`, `MetricGroup.svelte`, `BucketSection.svelte`, `BucketSectionOff.svelte`, `PresetRow.svelte` | **Bestätigt tote Dateien** — nur noch via Barrel-Re-Export (`trip-detail/index.ts:13-15`) geführt, nirgendwo instanziiert. `MetricGroup.svelte` ist ein **zusätzlicher, in keinem der 3 Issues genannter Dead-Code-Fund**, direkt relevant für `epic-138-block-b.spec.ts` |
| `frontend/src/lib/components/trip-detail/WeatherV2Grundauswahl.svelte:25`, `WeatherV2Reihenfolge.svelte:32,45,56,90-96`, `WeatherV2PresetBar.svelte:35,38,49,58` | Aktuelle Test-IDs (`wm2-grundauswahl`, `wm2-reihenfolge-row`, `weather-preset-pill-{id}`, Roh/Einfach über sichtbaren Text statt Testid) |
| `frontend/e2e/issue-343-horizon-chips.spec.ts` (220 Z., 7 Tests) | 5 Tests (AC-1/2/3/5/6) bereits `test.skip()` mit Befund-Kommentar. 2 aktive Tests (AC-4, AC-7) nutzen reale, aktuelle Selektoren — laufen vermutlich bereits grün |
| `frontend/e2e/issue-690-custom-metrics-persist.spec.ts` (225 Z., 4 Tests) | **Identisch in #970 UND #971 gezählt — EINE Behebung, nicht zwei.** `makeDirty()`-Helper (Z.71-75) nutzt totes `weather-metrics-tab-checkbox-*` — alle 4 Tests scheitern schon am ersten Schritt. Rest der Selektoren aktuell gültig |
| `frontend/e2e/epic-138-block-b.spec.ts` (362 Z., 14 Tests) | 4 Sub-Gruppen: #178 dirty-state (gleicher toter Helper wie issue-690), #174 MetricGroup (tot, `metric-group-*`), #175 ModeBtn/INDICATOR_MAP (tot, nur in `MetricCheckbox.svelte:95,105`), #176 TablePreview (tot), #177 SavePresetDialog (teils grün [API-only ACs], teils Testid-Migration nötig: `weather-metrics-preset-row-*` → `weather-preset-pill-{id}`) |
| `frontend/e2e/issue-774-metrics-summary-persist.spec.ts` (175 Z., 3 Tests) | **Korrigiert nach Live-Verifikation (Screenshots + Code):** Die "Metriken-Überblick"-Checkbox (`report-show-metrics-summary`) existiert im Bearbeiten-Modus (weder "Inhalt"- noch "Versand"-Tab) NICHT mehr — bestätigt durch echten Playwright-Lauf gegen Staging (0 Treffer) und zwei Screenshots. Ursache: #942 hat `EditReportConfigSection` aus `WeatherMetricsTab.svelte` entfernt; `BriefingScheduleTab.svelte:105` bindet sie zwar noch ein, aber mit `showMailContent={false}` (blendet genau diesen Block aus). **Tieferer Fund:** `show_metrics_summary` ist im Renderer seit Issue #790 (2026-06-12, PO-Vision "Weg ist weg") ein kompletter No-Op — `src/output/renderers/email/html.py:759,764` und `plain.py:98` nehmen den Parameter nur noch über `**_ignored` entgegen; `build_metrics_summary_pills()` (html.py:1287) wird IMMER unconditional gerufen. Der Metriken-Überblick-Block erscheint in JEDER Mail, unabhängig von der (nicht mehr existenten) Checkbox |
| `frontend/e2e/issue-776-metrics-toggle.spec.ts` (79 Z., 1 Test) | Klickt `report-content-modules-toggle` (Z.43) — Element wurde durch #774s eigenen (bereits gemergten) Fix entfernt. Gleicher Root-Cause-Komplex wie `issue-774` (beide testen ein durch #790/#942 bereits bewusst abgeschafftes Verhalten) |
| `frontend/src/lib/utils/alertMetricLabels.test.ts`, `alertMetricLabels.ts:67-70` | **#1011 selbst verifiziert: 15/15 Tests grün, 0 Fails** (eigener Lauf `npm run test -- src/lib/utils/alertMetricLabels.test.ts`). Die Alert-Katalog-Fixes aus Commit `b65f22a0` (2026-07-03, vor #1011s Meldung am 2026-07-04) haben die beschriebene Drift bereits behoben. Latente, aber nicht testauffällige Inkonsistenz bleibt: `snow_line` ist sowohl in `ALERT_METRIC_LABELS` (aktiv) als auch tot in `LEGACY_ALERT_METRIC_MAP` (Z.61-62) |

## Existing Patterns
- **Migrations-Methodik aus #964:** alte Test-ID durch Lesen der jeweiligen v2-Sub-Komponente identifizieren, auf neuen Selektor/Text-Selektor ummünzen, `test.skip()` nur für endgültig nicht wiederherstellbare Interaktionspfade mit Befund-Kommentar (siehe `issue-343-horizon-chips.spec.ts:60-92` als Vorbild für sauberen Skip-Kommentar).
- **Reale Klickpfade statt toter Test-IDs:** `issue-343-horizon-chips.spec.ts:148-151` zeigt, wie ein "etwas ändern"-Klick gegen `wm2-grundauswahl` aussieht — Vorbild für den `makeDirty()`-Fix in `issue-690`/`epic-138-block-b`#178.
- **Text-/Rollen-Selektoren statt fehlender Test-IDs:** `WeatherV2PresetBar.svelte:58` hat keinen Trigger-Testid, nur Text "als eigenes Profil speichern" — Vorbild für den `save-preset-dialog-trigger`-Fix in `epic-138-block-b`#177.

## Dependencies
- Upstream: v2-Redesign-Komponenten (`WeatherV2*.svelte`) sind die "Wahrheit" (Memory-Regel: JSX/Svelte-Quelle gewinnt bei Konflikt) — Tests müssen sich anpassen, nicht umgekehrt.
- Downstream: Keine — reine Testdatei-Änderungen, kein Produktivcode betroffen (außer ggf. `issue-776`, das je nach Fund evtl. eine winzige Test-Anpassung statt Produktivcode-Fix braucht, da das Feature selbst laut #774 bereits korrekt entfernt wurde).

## Existing Specs
- `docs/specs/modules/fix_964_e2e_drift.md` — Vorlage/Methodik, aber teilweise veraltet (s.o.).

## PO-Entscheidungen (2026-07-06)
- **epic-138-block-b #174 (MetricGroup) + #175 (ModeBtn/INDICATOR_MAP):** Analog zu #970 zurückziehen — gleiche Ursache (totes v2-Redesign-Dead-Code), keine Wiederherstellung. Kein funktionaler Ersatz wird gesucht.
- **#1011 (alertMetricLabels.test.ts):** Als bereits erledigt behandeln — kein Code-Fix nötig, nur Verifikation + Issue mit Begründung schließen. Kein Spec-Aufwand für diesen Teil.
- **`issue-774`/`issue-776` (Metriken-Überblick-Checkbox):** Nach Live-Verifikation (Screenshots + Renderer-Code-Analyse) bestätigt: Die Checkbox ist eine wirkungslose Karteileiche — der Metriken-Überblick-Block wird seit Issue #790 (PO-Vision "Weg ist weg") IMMER gerendert, unabhängig vom Flag. PO-Entscheidung: Checkbox überall entfernen (inkl. Neuanlegen-Formular, `TripNewEditor.svelte:765,990`) + Tests auf das neue, korrekte Verhalten umstellen (Block erscheint immer, keine Checkbox-Interaktion mehr nötig). **Das ist die einzige Stelle in diesem Bündel, die Produktivcode (Svelte-Formular) berührt, nicht nur Testdateien** — kleiner, gut belegter Cleanup, kein neues Feature.

## Risks & Considerations
- **issue-690-Doppelzählung:** #970 und #971 nennen dieselben 4 Tests — im Spec-/Implementierungsschritt als EIN Arbeitspaket behandeln, nicht doppelt.
- **epic-138-block-b braucht Fall-Entscheidungen:** #174 (MetricGroup) und #175 (ModeBtn/INDICATOR_MAP) referenzieren ebenfalls totes v2-Redesign-Dead-Code — analog zur #970-PO-Entscheidung (retire statt restore), vom PO bestätigt (s.o.). #176 (TablePreview) überschneidet sich mit #970s TablePreview-Fund.
- **Dead-Code-Löschung außerhalb Scope:** `MetricCheckbox.svelte`, `TablePreview.svelte`, `MetricGroup.svelte`, `BucketSection*.svelte`, `PresetRow.svelte` sind bestätigt tot — ob sie als Cleanup gelöscht werden, ist eine separate Entscheidung (nicht zwingend Teil dieses Test-Fix-Bündels); ggf. als Folge-Issue vermerken statt hier mit zu erledigen (Scope-Disziplin). Das Backend-Feld `show_metrics_summary` (Model, Loader) kann ebenfalls als totes Feld bestehen bleiben — Entfernen wäre zusätzlicher, nicht angeforderter Cleanup.
- **Produktivcode-Änderung in `TripNewEditor.svelte`:** Einziger Fall in diesem Bündel, der über reine Testdatei-Änderungen hinausgeht (Checkbox-Entfernung im Neuanlegen-Formular) — klein und gut belegt (PO-Entscheidung + Code-Beweis #790), aber im Spec explizit als Produktivcode-Change kennzeichnen, nicht als Testfix tarnen.

## Analysis

### Type
Bug (Test-/UI-Drift-Bereinigung nach zwei unabhängigen, bereits gemergten Vorgänger-Änderungen: v2-Redesign #848/#587 und Mail-Vereinfachung #790/#942).

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|--------------|
| `frontend/e2e/issue-343-horizon-chips.spec.ts` | MODIFY | 5 `test.skip()`-Blöcke (AC-1/2/3/5/6) entfernen, Skip-Kommentar zu "PO-Entscheidung final, zurückgezogen" umformulieren. 2 aktive Tests (AC-4, AC-7) bleiben unverändert |
| `frontend/e2e/issue-690-custom-metrics-persist.spec.ts` | MODIFY | `makeDirty()`-Helper (Z.71-75): totes `weather-metrics-tab-checkbox-*` durch echten Klick gegen `wm2-grundauswahl` ersetzen (Vorbild `issue-343-horizon-chips.spec.ts:148-151`) |
| `frontend/e2e/epic-138-block-b.spec.ts` | MODIFY | #178 (dirty-state): gleicher Helper-Fix wie issue-690. #174 (MetricGroup) + #175 (ModeBtn) + #176 (TablePreview): zurückziehen (PO-Entscheidung). #177 (SavePresetDialog): `save-preset-dialog-trigger` → Text-/Rollen-Selektor "als eigenes Profil speichern"; `weather-metrics-preset-row-*` → `weather-preset-pill-{id}` |
| `frontend/e2e/issue-774-metrics-summary-persist.spec.ts` | MODIFY | Tests auf neues Verhalten umstellen: Metriken-Überblick-Block erscheint immer (kein Checkbox-Toggle mehr nötig/vorhanden) — AC-1 (Persistenz) entfällt, AC-2 (Einklapp-Element weg) bleibt sinngemäß gültig, AC-3 ggf. anpassen |
| `frontend/e2e/issue-776-metrics-toggle.spec.ts` | MODIFY | Klick auf `report-content-modules-toggle` entfernen/ersetzen — Test auf "Block erscheint immer" umstellen |
| `frontend/src/lib/components/trip-new/TripNewEditor.svelte` | MODIFY | Zwei Vorkommen der `EditReportConfigSection`-Checkbox-Karteileiche entfernen (Z.765, 990) — einzige Produktivcode-Änderung in diesem Bündel |
| Issue #1011 | KEINE CODE-ÄNDERUNG | Nur Verifikation (bereits erledigt) + Issue-Schluss mit Begründung |

### Scope Assessment
- Files: 6 (5 Testdateien + 1 Svelte-Formular-Datei)
- Estimated LoC: ~80-130 (überwiegend Löschungen/Selektor-Austausch, kein neuer Produktivcode außer der Checkbox-Entfernung ~4-6 Zeilen)
- Risk Level: LOW (reine Testbereinigung + eine kleine, durch Renderer-Code zweifelsfrei belegte Dead-Code-Entfernung; keine Business-Logik betroffen)

### Technical Approach
Reihenfolge: (1) `issue-690`/`epic-138-block-b`#178 Helper-Fix (kleinster, risikofreiester Schritt, Vorbild vorhanden), (2) `epic-138-block-b` #177-Migration + Retire von #174/#175/#176, (3) `issue-343-horizon-chips.spec.ts` Skip-Bereinigung (#970), (4) `issue-774`/`issue-776` auf "Block erscheint immer"-Verhalten umstellen + `TripNewEditor.svelte`-Checkbox entfernen, (5) `#1011` Verifikation + Issue-Schluss (unabhängig, jederzeit parallelisierbar).

### Dependencies
- Upstream: v2-Redesign-Komponenten (`WeatherV2*.svelte`) und der Mail-Renderer (`build_metrics_summary_pills`) sind die "Wahrheit" — Tests passen sich an.
- Downstream: Keine harten Abhängigkeiten; `docs/specs/modules/fix_964_e2e_drift.md` sollte NICHT als weiterhin gültige Quelle für `table-preview-day-*`/`weather-metrics-tab-checkbox-*` zitiert werden (durch diesen Fix implizit korrigiert).

### Open Questions
- [x] epic-138-block-b #174/#175 zurückziehen? → Ja (PO-Entscheidung)
- [x] #1011 bereits erledigt? → Ja (PO-Entscheidung, nur verifizieren+schließen)
- [x] Metriken-Überblick-Checkbox überall entfernen? → Ja (PO-Entscheidung)
- [ ] Keine weiteren offenen Fragen — bereit für Spec-Phase.
