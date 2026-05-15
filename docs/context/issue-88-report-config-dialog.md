# Context: Issue #88 — Dialog "Report Konfiguration" optimieren

## Request Summary

Der Trip-Edit-Dialog "Report Konfiguration" soll in 3 logische Reports (Morgen / Abend / Änderungen) umstrukturiert werden, mit Gruppierung von Uhrzeit + Schwellwert pro Report, Disabled-Logik bei nicht ausgewählten Reports, Kanal-Verfügbarkeit aus User-Profil, und mobile-tauglichen Time-Pickern.

## Related Files

| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/edit/EditReportConfigSection.svelte` | **Haupt-Datei** — der Dialog, der umstrukturiert werden muss. ~190 LoC, alle Felder + Checkboxen. |
| `frontend/src/lib/components/edit/TripEditView.svelte` | Hostet `<EditReportConfigSection bind:reportConfig>`. |
| `frontend/src/routes/trips/[id]/edit/+page.svelte` | Route, lädt `Trip.report_config`. |
| `frontend/src/lib/types.ts:75` | `Trip.report_config?: Record<string, unknown>` — nicht eng typisiert. |
| `frontend/src/lib/components/AlertRulesEditor.svelte` | Wiederverwendbarer Editor für Alert-Regeln (aus Issue #224). Aktuell nur im Wizard genutzt. |
| `frontend/src/lib/wizard/wizardState.svelte.ts:15-31, 325-350` | `BriefingConfig` (Wizard-Daten) → `report_config`-Mapping. Vorbild für Edit-Konvergenz. |
| `frontend/src/lib/wizard/steps/Step4Briefings.svelte` | Wizard-Variante des Report-Dialogs (Vorbild für die 3-Report-Struktur). |
| `frontend/src/lib/wizard/components/ReportRow.svelte` | Bestehende Time-Picker-Reihe (`<input type="time">` + disabled-Logik) — bereits gute UX-Vorlage. |
| `frontend/src/routes/account/+page.svelte:8-17` | Wo die Kanal-Credentials liegen: `profile.mail_to`, `profile.signal_phone`, `profile.telegram_chat_id`. Link-Ziel `/account` für "nicht konfiguriert"-Hinweis. |
| `docs/specs/modules/epic_136_step4_briefings.md` | Wizard-Spec (Issue #164) — hat dieselbe 3-Report-Struktur, Edit soll konvergieren. |
| `docs/specs/modules/issue_224_wizard_alert_rules_editor.md` | AlertRules-Migration im Wizard — Vorlage für Edit-Migration. |

## Existing Patterns

- **3-Report-Struktur ist im Wizard bereits umgesetzt** (`Step4Briefings.svelte` + `wizardState.BriefingConfig.morning`/`.evening` + top-level `WizardState.alertRules`). Edit ist die "Insel" mit dem alten Modell.
- **AlertRulesEditor.svelte** ist die etablierte Komponente für Alert-Regeln (Schwellwerte). Im Wizard läuft sie als eigenständige Sektion. Im Edit gibt es stattdessen noch `change_threshold_temp_c`, `change_threshold_wind_kmh`, `change_threshold_precip_mm` als Einzelfelder.
- **Time-Picker:** Frontend verwendet native HTML `<input type="time">` — auf iOS/Android öffnet sich der native Picker (touch-friendly, accessible). Keine Custom-Komponente bisher.
- **Kanal-Conditional-Logic** im Frontend bereits präsent: Account-Seite zeigt Status pro Kanal. Im Edit-Dialog noch nicht angewandt — alle 4 Checkboxen werden immer angezeigt.

## Dependencies

**Upstream (was Edit-Dialog konsumiert):**
- `Trip.report_config` (Server-Daten, JSON-Blob)
- `user.profile.{mail_to,signal_phone,telegram_chat_id}` für Kanal-Verfügbarkeit
- `Trip.alert_rules` (falls AlertRules-Migration im Edit)

**Downstream (was den Edit-Dialog konsumiert):**
- `toTripPayload()` im Wizard, PUT/POST gegen Go-API `/api/trips/[id]`
- Go-API Handler in `internal/handlers/trips.go` (vermutlich) — muss neue Felder akzeptieren
- Report-Renderer in `src/services/` (Backend) — liest `report_config.{morning_time,evening_time,alert_on_changes,...}`

## Existing Specs

- `docs/specs/modules/epic_136_step4_briefings.md` — Wizard Step 4 (Issue #164). Definiert `BriefingConfig`-Struktur.
- `docs/specs/modules/issue_224_wizard_alert_rules_editor.md` — AlertRules-Editor (Issue #224). Migration `change_threshold_*` → `AlertRule[]`.

## Risks & Considerations

1. **Code-Drift Wizard ↔ Edit:** Der Edit-Dialog hat noch das alte `change_threshold_*`-Modell, Wizard hat AlertRules. Issue #88 muss klären: Edit auch auf AlertRules migrieren (empfohlen, Konsistenz)?
2. **Backend-Akzeptanz für AlertRules im Edit:** Wenn Edit-Dialog AlertRules speichert, muss die Go-API das im `Trip`-Modell akzeptieren — vermutlich schon der Fall, weil Wizard das auch tut. Trotzdem verifizieren.
3. **Bestehende Trips:** User haben bestehende Trips mit `change_threshold_temp_c` etc. im JSON. Wenn der Edit-Dialog die Felder nicht mehr anzeigt, gehen die Daten beim Speichern verloren (User-Side-Pattern: Read-Modify-Write). → Migration: beim Laden alte Felder → AlertRule-Einträge konvertieren, beim Speichern nur AlertRules schreiben (oder beide Felder).
4. **"Vernünftiger Time-Picker mobile-tauglich":** Native `<input type="time">` ist bereits state-of-the-art mobile. Issue-Text ist unklar — möglicherweise meint der User Quick-Picks ("07:00 / 18:00") oder bessere Touch-Targets. Vor Spec-Schreiben klären.
5. **Multi-Day-Trend-Reports:** Die Felder `multi_day_trend_morning`, `multi_day_trend_evening` im aktuellen Edit — gehören die zur jeweiligen Morgen/Abend-Sektion oder bleiben sie in "Erweitert"?
6. **Backwards-Compatibility:** Trips ohne `report_config` müssen weiterhin laden (Default: alle Reports aus).

## Open Questions for User (vor Spec)

1. **AlertRules-Migration im Edit:** Soll der Edit-Dialog vollständig auf `AlertRulesEditor` umstellen (wie Wizard), oder die alten `change_threshold_*`-Felder behalten?
2. **Time-Picker:** Reicht `<input type="time">` (native, mobile-tauglich) plus optionale Quick-Picks ("Morgens 07:00 / Abends 18:00")? Oder hast du eine konkrete Bibliothek/Optik im Kopf?
3. **Multi-Day-Trend:** Soll der Multi-Day-Trend-Schalter pro Report mit gruppiert werden (innerhalb Morgen-/Abend-Sektion) oder in "Erweitert" bleiben?
