# Context: feat-2277-s5-reportconfig-rueckbau

## Request Summary
#2277 Scheibe S5: Ticket-AC-5 verlangt, dass es keinen produktiven Importeur von `EditReportConfigSection` (und `reportConfigWrite`, `BriefingsTab`) mehr gibt. S1–S4 sind live (zuletzt S4 `e346b60e`, 02.10.).

## Kernbefund
`EditReportConfigSection.svelte` (574 Zeilen) ist **nicht tot**: Sie ist die einzige Implementierung der Karte „E-Mail-Inhalt" (Format full/compact, `show_*`-Schalter, `data-testid="report-mail-content"`). `VersandTab` hat kein Pendant. Reines Löschen entfernt das Feature. S5 ist daher ein **Umzug** der Karte in einen geteilten Baustein plus Löschung des Rests — kein Rückbau.

## Related Files
| Datei | Relevanz |
|-------|----------|
| `frontend/src/lib/components/edit/EditReportConfigSection.svelte` | Zu ersetzen; Props `showMailContent/showChannels/showSchedule/weatherChannels/onChannelChange/profileOverride/mode` |
| `frontend/src/lib/components/edit/reportConfigWrite.ts` (156) | Einziger produktiver Aufrufer ist die Section selbst |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte:87,1986` | Mountet die Section (Hub, Trip-Anlegen, Compare-Pfade); Kommentare zu Mount-Kanonisierung (#1269), Touch-Scope (#1234) — eng gekoppelt, Spec #1234: Section „darf nicht geändert werden" |
| `frontend/src/lib/components/trip-new/TripNewEditor.svelte:17,880,1163` | Mountet die Section 2× (Desktop/Mobil, XOR per `isMobileViewport`) mit `showChannels=false showSchedule=false` |
| `frontend/src/lib/components/briefings-tab/BriefingsTab.svelte` (98) | Mountet die Section mit `mode="edit"`; in `trip-detail/TripTabs.svelte:14` nur **importiert**, nicht gerendert (Import tot) |
| `frontend/src/lib/components/shared/VersandTab.svelte` | Geteilter Versand-Baustein; Kommentare verweisen auf die Section; kein Mail-Inhalt |
| `frontend/src/lib/components/trip-detail/weatherSaveGate.ts`, `shared/reportConfigDirty.ts`, `shared/versand-tab/{mergeReportConfig,reportConfigPayload,channelContactLabel,premiumSmsChannelState}.ts`, `utils/reportSlotAktiv.ts` | Nur Erwähnungen (Kommentare/Verweise) — vor Löschung prüfen, ob Code oder Text |

## Betroffene Tests (referenzieren die Section oder reportConfigWrite)
`edit/issue_619_report_config_write.test.ts`, `edit/issue_693_email_config_cleanup.test.ts`, `edit/issue_723_email_tab_eindampfen.test.ts`, `edit/__tests__/report_config_uses_shared_schedule.test.ts`, `edit/__tests__/sms_unbestaetigt_trip_editor.test.ts`, `shared/__tests__/reportConfigDirty.test.ts`, `shared/versand-tab/__tests__/*` (6 Dateien), `trip-detail/issue_617_briefing_channel_gating.test.ts`, `trip-detail/__tests__/weatherSaveGate.test.ts`, `trip-new/__tests__/trip_new_{versandkanaele_unabhaengig_von_metriken,zeitplan_tab_nutzt_geteilten_versand_baustein}.test.ts`, `utils/__tests__/report_slot_aktiv.test.ts`.

## Existing Patterns
- Geteilte Bausteine unter `shared/` mit `context="route"|"vergleich"` (VersandTab, WeatherMetricsTab, CorridorEditor, AlarmeTab).
- Vorgehen S1–S4: Test-RED an der Wirkstelle, dann Umhängen, dann Altbestand samt Alt-Tests löschen.
- Doppelter Mount per `isMobileViewport` (XOR), weil zwei Instanzen je einen Schnappschuss von `report_config` halten (Last-Write-Wins, Fix-Loop 4 in #1738).

## Dependencies / Dependents
- Upstream der Section: `reportConfigWrite.ts`, Profil-/Kanal-Fetch (doppelt zu `VersandTab`, C4-22 in #1986).
- Downstream: Hub-Speichern (`WeatherMetricsTab` + `saveController`), Trip-Anlegen (`TripNewEditor`), E-Mail-Rendering (Schalter bestimmen Mail-Inhalt, Validator `briefing_mail_validator.py`).

## Existing Specs
`docs/specs/modules/email_toggles_621.md`, `briefing_mail_inhalt.md`, `bundle_d_mail_ui_schalter.md`; archiviert: `issue_619_mail_elements_ui.md`, `issue_693_email_config_cleanup.md`.

## Risks & Considerations
1. **Funktionsverlust:** Mail-Inhalt-Karte darf nicht verschwinden; Daten (`show_*`, Format) müssen bei Umzug per Read-Modify-Write erhalten bleiben (CLAUDE.md „Daten-Schema-Reworks").
2. **Kopplung WeatherMetricsTab:** Mount-Kanonisierung (#1269), Touch-Scope (#1234), `weatherSaveGate` hängen an dem Verhalten der Section beim Mounten. Ein Umzug verändert Mount-Zeitpunkt/Normalisierung → Datenverlust-/Dirty-Risiko.
3. **Mail-Pfad:** Änderung an der Mail-Inhalt-Steuerung berührt das Renderer-Commit-Gate nur, wenn Renderer-Dateien angefasst werden; Validator-Lauf gegen Staging-Mail ist bei Inhalts-Schaltern dennoch sinnvoll.
4. **Ortsvergleich:** Compare hat ein eigenes Mail-Template; ob die Karte dort gebraucht wird, ist in der Analyse zu klären (Teilungsregel Trip/Ortsvergleich).
5. **Scope höher als im Intake geschätzt** (Umzug eines 574-Zeilen-Bausteins mit Mount-Kopplung statt Löschung): LoC-Limit 250 wird voraussichtlich `loc_limit_override` brauchen; ggf. Aufteilung in S5a (toter `BriefingsTab` + Import) und S5b (Karte umziehen).
6. **Nebenbefund:** `TripTabs.svelte` importiert `BriefingsTab` ohne Nutzung.

## Analysis

### Type
Feature/Rework (Umzug + Rückbau), Scheibe S5 von #2277 — Ticket-AC-5 (kein produktiver Importeur von `EditReportConfigSection`, `reportConfigWrite`, `BriefingsTab`).

### Befund (nachgemessen)
- Die Section wird nur noch im **Mail-Inhalt-Modus** genutzt (`showChannels=false showSchedule=false`): Hub-Mount `WeatherMetricsTab.svelte:1986` (`context="route"`, innerhalb `report-config-touch-scope`) und `TripNewEditor.svelte:880` (Desktop) / `:1163` (Mobil, XOR per `isMobileViewport`). Zeitplan-/Kanal-/Profil-Fetch-Zweige sind damit für Produktivpfade tot. `BriefingsTab` ist der einzige Mount mit Defaults, aber selbst tot (Import in `TripTabs.svelte:14` ohne Verwendung).
- Der Ortsvergleich mountet die Section nie (eigenes Mail-Template, 3-Tages-Vorschau über `CompareOutlookLayoutControls`) → Karte bleibt **route-eigen**, kein `context="vergleich"` nötig (Begründung für die Teilungsregel in die Spec).
- Section-Write-Back (`$effect`) schreibt per Read-Modify-Write (`baueReportConfigPayload`, Basis = lebender Blob) neben den Mail-Schaltern auch `show_compact_summary`, `wind_exposition_min_elevation_m`, `daily_summary_metrics`.

### Affected Files (with changes)
| Datei | Change | Beschreibung |
|---|---|---|
| `shared/MailInhaltCard.svelte` | CREATE | Karte „E-Mail-Inhalt" (Format full/compact, `show_*`, `data-testid` unverändert), nur Mail-Felder, gleiche Lade-/Merge-Logik, `$bindable reportConfig` |
| `shared/WeatherMetricsTab.svelte` | MODIFY | Mount `:1986` + Kommentare (#1234/#1269) umhängen |
| `trip-new/TripNewEditor.svelte` | MODIFY | 2 Mounts + Import |
| `edit/EditReportConfigSection.svelte` (574) | DELETE | |
| `edit/reportConfigWrite.ts` (156) | DELETE | nur Section ist Aufrufer |
| `briefings-tab/BriefingsTab.svelte` (98) | DELETE | tot |
| `trip-detail/TripTabs.svelte` | MODIFY | toter Import entfällt |
| Tests (Liste oben) | MODIFY/DELETE | Mail-Inhalt-Tests (`issue_619/693/723`, `sms_unbestaetigt_trip_editor`, `report_config_uses_shared_schedule`) auf neuen Baustein umhängen; reine Section-/Write-Tests löschen; Kommentar-Verweise in `VersandTab`, `weatherSaveGate`, `reportConfigDirty`, `versand-tab/*`, `reportSlotAktiv` nachziehen |

### Scope Assessment
- ~6 Produktiv- + ~12 Testdateien; netto produktiv eher negativ, brutto voraussichtlich >250 → `loc_limit_override 500`. Keine Aufteilung (S5a/S5b würde den Mount-Umzug nur verdoppeln).
- Risk Level: MEDIUM — Verhalten identisch halten; `show_*`/`email_format` per Read-Modify-Write erhalten.

### Technical Approach
1. RED an der Wirkstelle: Hub und Trip-Anlegen rendern `report-mail-content` über den neuen Baustein und schreiben Format/Schalter, ohne Fremdfelder (Zeitplan/Kanäle/`telegram_style`) anzufassen.
2. Baustein aus dem Mail-Zweig der Section extrahieren, Mounts umhängen; `report-config-touch-scope`, XOR-Mount und Mount-Kanonisierung (#1269) bleiben.
3. Section + `reportConfigWrite` + `BriefingsTab` samt Alt-Tests löschen, Kommentare bereinigen.
4. Mutations-Gegenprobe: Mount-Umhängung, Fremdfeld-Schutz, Karte nur in Route.

### Dependencies
Upstream: `reportConfigPayload.ts`, `mergeReportConfig.ts`, Lader `ladeReportZustand`. Downstream: Hub-Speichern (`weatherSaveGate`, `reportConfigDirty`), Trip-Anlegen, Mail-Rendering (Validator `briefing_mail_validator.py` gegen Staging-Mail, Wegwerf-Nutzer `gregor-test+…`).

### Open Questions
- [ ] Mount-Kanonisierung der Zeiten (`toHHMMSS`) entfällt im Mail-only-Baustein (keine Zeitfelder) — Empfehlung: ja; Hub-Dirty-Verhalten per Test absichern (Spec #1234).
- [ ] Pendant-Sperre: Neuanlage `shared/MailInhaltCard.svelte` ohne Compare-Pendant → Begründung in die Spec.
