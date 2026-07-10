# Context: fix-1134-compare-mail-format (Issue #1134)

## Request Summary
E-Mail "Orts-Vergleich" hat 3 Bugs: (1) Farbe der Waldbrand-Warn-Chips ist je Ort
inkonsistent, (2) "Extreme Hitze" wird pro Ort im Stundenverlauf-Abschnitt
doppelt gerendert, (3) das im Wizard (Step 5) gewählte Zeitfenster wird beim
Bearbeiten eines bestehenden Orts-Vergleichs nicht gespeichert — die Mail zeigt
weiterhin das alte Zeitfenster.

## Related Files

| File | Relevance |
|------|-----------|
| `src/output/renderers/email/compare_html.py` | Übersichtstabelle (`_warn_short`/`_RISK_CELL`, Zeile 160-239), Pro-Ort-Sektion (`_render_location_section`, Zeile 403-427), Header/Zeitfenster-Ausgabe (`_render_header`, Zeile 458-470) |
| `src/output/renderers/alert/official_alerts.py` | Geteilter Alert-Renderer (`render_official_alerts_html`, Zeile 24-65) — eigene Farbschwellen nach `alert.level` (Zeile 47-52), gilt pauschal für alle hazard-Typen. `collect_trip_alert_entries` (Zeile 79-96) dedupliziert nach `region_label` — **nur für den Trip-Pfad**, nicht für Compare |
| `src/services/official_alerts/vigilance.py` | `extreme_heat`: `level` = `phenomenon_max_color_id` (Vigilance-Farbskala), Zeile 130 |
| `src/services/official_alerts/meteo_forets.py` | `wildfire_risk`: `level` = `niveau_j1`, Label `"Waldbrand-Gefahr — Stufe {level}"`, Zeile 100-121 |
| `frontend/src/lib/components/compare/compareWizardState.svelte.ts` | Wizard-State; `timeWindowStart`/`timeWindowEnd` (Zeile 36-37); `saveComparePreset()` (Zeile 200-227) übergibt **kein** Zeitfenster an `buildComparePresetSavePayload` |
| `frontend/src/lib/components/compare/compareEditorSave.ts` | `buildComparePresetSavePayload` (Zeile 40-99) — Round-Trip-Spread-Pattern; `hour_from`/`hour_to` fehlen komplett in `CompareEditorEdits`, werden daher nie überschrieben |
| `frontend/src/lib/components/compare/steps/Step5Versand.svelte` | UI-Eingabefelder für Zeitfenster existieren (Zeile 189, 198) und funktionieren im Create-Pfad (`saveNewPreset`, Zeile 167-168) |
| `frontend/src/routes/compare/[id]/edit/+page.svelte` | Lädt beim Öffnen korrekt `hour_from`/`hour_to` in den State (Zeile 33-34) — Load-Pfad ist NICHT betroffen |
| `frontend/src/lib/types.ts` | `ComparePreset.hour_from`/`hour_to` (Zeile 488-489) |

## Root-Cause je Teilproblem

**1) Farb-Inkonsistenz Waldbrand-Stufe:** Zwei unabhängige Farblogiken für dieselbe
Warnung: Übersichtstabelle nutzt `_RISK_CELL` mit hazard-spezifischer Stufen-Zuordnung
(`compare_html.py:160-169`), der Pro-Ort-Streifen nutzt `official_alerts.py`s eigene,
hazard-**unabhängige** Schwellen (`level<=2` grün, `==3` orange, `>=4` rot) — angewendet
gleichermaßen auf `wildfire_risk` (Skala `niveau_j1`) und `extreme_heat`
(Skala `phenomenon_max_color_id`), obwohl beide Skalen unterschiedliche Semantik haben.

**2) "Extreme Hitze" doppelt:** `_render_location_section` (`compare_html.py:403-427`)
ruft `render_official_alerts_html([("", loc.official_alerts)])` **ohne Dedup** auf.
Der Dedup aus #1172 (`collect_trip_alert_entries`) ist laut eigenem Docstring
explizit nur für den Trip-Briefing-Pfad gebaut — der Compare-Pfad wurde nie
angebunden.

**3) Zeitfenster nicht gespeichert:** Bug ausschließlich im **Edit-Pfad**. Laden
funktioniert (`+page.svelte:33-34`). Die UI-Felder in `Step5Versand.svelte`
ändern reaktiv `state.timeWindowStart`/`timeWindowEnd`. Aber `saveComparePreset()`
(`compareWizardState.svelte.ts:200-216`) übergibt diese Werte **nicht** an
`buildComparePresetSavePayload` — dort gibt es kein `hour_from`/`hour_to`-Feld in
`CompareEditorEdits` (`compareEditorSave.ts:13-32`), daher bleibt beim PUT-Request
immer der `...original`-Spread-Wert erhalten (Zeile 81-96). Der Create-Pfad
(`saveNewPreset`, `compareWizardState.svelte.ts:167-168`) ist NICHT betroffen —
dort werden die Werte korrekt gesendet.

## Existing Patterns
- **Round-Trip-Spread + explizites Edit-Override-Feld** ist das etablierte Muster
  für "editierbares Feld im Compare-Preset-Edit-Pfad" — siehe `forecastHours`
  (#764), `officialAlertsEnabled` (#1040), `hourlyEnabled` (#1107) in
  `compareEditorSave.ts:87-95`. Der Fix für Punkt 3 folgt exakt diesem Muster:
  `hourFrom`/`hourTo` als optionale Felder in `CompareEditorEdits` ergänzen, im
  Body-Spread analog `...(edits.hourFrom !== undefined ? { hour_from: edits.hourFrom } : {})`.
- **Hazard-spezifische Farbzuordnung** existiert bereits in `_RISK_CELL`/`_warn_short`
  (Übersichtstabelle) — für Punkt 1 bietet es sich an, diese als Single Source of
  Truth zu nutzen und `official_alerts.py`s Farblogik darauf umzustellen (oder
  eine gemeinsame hazard-aware Mapping-Funktion zu extrahieren).
- **Dedup nach `(region_label, hazard)`** existiert bereits (#1172,
  `collect_trip_alert_entries`) — für Punkt 2 kann dasselbe Prinzip auf
  `_render_location_section` angewendet werden (dort reicht Dedup pro Ort, da
  bereits pro-Ort iteriert wird — ggf. reicht simple Dedup nach `(hazard, level, label)`
  innerhalb `loc.official_alerts`).

## Dependencies
- Upstream: `services/official_alerts/*` (Datenquellen: vigilance.py, meteo_forets.py,
  massif_closure.py) liefern `OfficialAlert`-Objekte mit `hazard`/`level`/`label`.
- Downstream: `render_official_alerts_html` wird auch vom Trip-Briefing-Pfad
  (`html.py`, `plain.py`, `compact.py`) genutzt — **Änderungen an der Farblogik
  dürfen den Trip-Pfad nicht brechen** (geteilter Renderer, ADR-0011/#1087).
  `buildComparePresetSavePayload` wird nur von `saveComparePreset` genutzt (Edit-Pfad).

## Existing Specs
- `docs/specs/modules/issue_1110_compare_mail_v2.md` — aktuelles Compare-Mail-Layout
- `docs/specs/modules/alert_render_foundation.md` — geteilter Alert-Renderer (#1087)
- `docs/specs/modules/issue_1172_official_alert_dedup_info_done.md` (falls vorhanden) bzw. Memory `project_issue_1172_official_alert_dedup_info_done.md` — Dedup-Vorarbeit für Trip-Pfad
- `docs/specs/modules/issue_679_compare_editor_edit.md` — Round-Trip-Spread-Prinzip für Compare-Preset-Edit (§ AC-3)
- `docs/specs/modules/issue_764_compare_forecast_hours.md` — Referenz-Pattern für optionales Edit-Feld

## Risks & Considerations
- Trip-Briefing-Pfad nutzt denselben `render_official_alerts_html` — Farblogik-Änderung
  muss für BEIDE Pfade (Compare + Trip) korrekt/konsistent bleiben, nicht nur für Compare.
  Byte-Gleichheits-Anspruch aus #1087 beachten, wo (noch) sinnvoll.
- Dedup in `_render_location_section` darf keine echten Doppel-Warnungen (z. B. zwei
  unterschiedliche `region_label` mit gleichem hazard) unterdrücken — nur exakte
  Duplikate.
- Zeitfenster-Fix betrifft nur den ComparePreset-Edit-Pfad (`/api/compare/presets/{id}`).
  **Geklärt:** Der Go-`Subscription`-Pfad (`internal/model/subscription.go`,
  `/api/subscriptions/{id}`) ist für die Compare-Edit-Route Legacy — laut Kommentar
  in `frontend/src/routes/compare/[id]/edit/+page.server.ts:6-7` wurde diese Route
  in #582 explizit von Subscription auf ComparePreset umgestellt. Kein Handlungsbedarf
  am Go-Code.
- Mail-Renderer-Commit-Gate (`renderer_mail_gate.py`) greift bei Änderungen an
  `compare_html.py`/`official_alerts.py` — vor Commit `test_issue_811_mode_matrix.py`
  + `briefing_mail_validator.py` grün bekommen (siehe CLAUDE.md).
