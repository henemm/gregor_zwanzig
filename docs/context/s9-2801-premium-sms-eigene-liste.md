# Kontext: S9 #2801 — Premium-SMS mit eigener Auswahl und Alarm-Dringlichkeit je Kanal

Workflow `s9-2801-premium-sms-eigene-liste` · Epic #2791 (Einstellungen neu, Scheibe S9, 10 von 10) · Stand `origin/main` @ `55107732d` (2026-11-28)

## Request Summary

PO-Entscheidung N2 („rein, eigene Liste“, `docs/context/einstellungen_neu.md:141`): Die Premium-SMS (inReach, Satellit, kostet je Nachricht) bekommt eine eigene Inhaltsauswahl statt der SMS-Auswahl. Bei Alarmen soll es einen Unterschied geben: SMS bekommt mehr (billig), Premium-SMS weniger. Umsetzung des Alarm-Unterschieds über die Dringlichkeits-Schwelle je Kanal (ADR-0046) mit Vorbelegung E-Mail/Telegram „gering“, SMS „mittel“, Premium-SMS „hoch“. Bestehende gesetzte Werte bleiben erhalten (ADR-0101, Read-Modify-Write).

Seit ADR-0124 (#3122, PO 2026-11-17) gibt es keinen Reiter „Inhalt je Kanal und Fläche“ mehr, sondern die Tabelle „Was steht wo“. Offene Produktfrage (Issue-Kommentar 2026-11-17): **Form der eigenen Premium-Auswahl** (z. B. eigene Spalte der Tabelle) und **ob sie eine eigene Reihenfolge behält**. ADR-0124 Nr. 3: eine Reihenfolge für alle Stellen; Nr. 5: SMS/Premium-SMS nur Kürzel, kein Roh/Einfach. PO-Entscheidung 2026-11-16: Kürzung vom Listenende, amtliche Warnungen zuletzt, gilt auch für die Premium-Liste.

## Related Files

### Datenmodell „Was steht wo“ (Briefing-Inhalt)
- `src/services/placements.py:4-10` Format `display_config.placements = {version, rows:[{metric_id, places:{stelle:bool}, formats}], outlook_reports}`; `STELLEN` :39 (`email, telegram, sms, hourly, outlook`), `STELLEN_TRIP` :40, `FORMAT_STELLEN` :41 (ohne sms); unbekannte Stelle (`premium_sms`) wird beim Lesen verworfen :84; `placements_aus_grundauswahl` :273-294.
- `src/services/placements_view_service.py` Unterzeile `sms: und_premium_sms` :33-38, Warnungen-Position `sms: last` :31-32, `sms_example` mit `max_length` :277, :308-316.
- Go: `internal/store/briefing_placements.go:22` (`SaveBriefingPlacements` ersetzt `display_config.placements` als Ganzes, RMW auf Rohbytes), `internal/handler/placements.go:84/169/237` (GET/PUT/Vorschau, Inhalt aus Python).
- Frontend: `frontend/src/lib/components/shared/wetter-tab/wasStehtWoStand.ts:13,16`, `wasStehtWoAnsicht.ts:21-35,71-72,99` (Spalten-Map, unbekannte Stelle wird nicht gezeigt), `wasStehtWoSpeicherung.ts:40`, `frontend/src/lib/components/organisms/wetter-tab/WasStehtWoKarte.svelte:324` (Hinweis Premium unter der Tabelle), i18n `i18n/messages/{de,en}/wetter.json:150,217-218` („Bekommt vorerst denselben Text wie die SMS. Eine eigene Auswahl kommt später.“).

### Resolver (wer bekommt welche Metriken)
- `src/services/channel_list_resolver.py:16` `KANAELE` (4), :46-50 `MailViewModel.premium_sms` („ist sms“), **:163-170 Premium fällt auf SMS** (`premium_sms=kanaele["sms"]`).
- Orte: `src/services/report_config_resolver.py:287-302` `enabled_metrics_by_channel`/`channel_rows_by_channel` nur email/telegram/sms.

### Renderer Briefing
- Trip: `src/output/renderers/trip_report.py:151` (resolve_trip_view), :388-390 (nur `_channel_view.sms`), **:482-494 `premium_sms_text` = SMS-Text bzw. SMS-Formatter mit 153 Zeichen** (Kommentar „Bewusst KEINE eigene Premium-Auswahl (#2801)“), :460-465 SMS-Schwelle der Warnungen gilt für Premium. Limit `CHANNEL_LIMITS["premium_sms"]` in `channel_layout.py:57`.
- Orte: `src/services/compare_briefing_aufbau.py:148-164` (`compare_premium_sms_rendern` über `enabled_metrics_by_channel["sms"]`), Kürzung `comparison.py:1102-1130` (`_sms_fit_locations`).
- Versand: `src/services/notification_service.py:977-994` (Trip), :1749-1756 (Orte, `premium_sms_text or sms_text`).

### Renderer Alarme
- Premium bekommt dasselbe `sms_body` wie SMS: `notification_service.py:2256-2268` (`_dispatch_alert_message`), amtlich :1588-1604, Orte amtlich `_dispatch_compare_official_premium_sms` :1964-1990.
- Text aus `src/services/alert_channel_texts.py:95-113` (`SMS_LIMIT=140` :32) und `src/output/renderers/alert/render.py:1883` (`render_sms`); Kürzung nach Schwere, nicht nach Metrikliste. ADR-0124 Nr. 11: Tabelle steuert nur Briefings, nicht Alarme.

### Alarm-Dringlichkeit je Kanal
- Feld `alert_channel_thresholds {email, telegram, sms, premium_sms}` existiert bereits für alle vier Kanäle: Go `internal/model/trip.go:172,236-248`, `internal/model/compare_preset.go:117`; Merge `internal/handler/trip.go:583-597`, Compare generisch `compare_preset.go:319`; Python `src/app/trip.py:235`, `src/app/loader.py:751,802,1863`.
- **Default heute überall `LOW`:** `src/services/alert_channel_threshold.py:17,28-30`; Frontend `shared/alarme-tab/alertChannelState.ts:127-145` (`resolveAlertChannelThresholds`, PO-Entscheidung #638), `shared/zustellung-tab/zustellungModell.ts:230-243,334`; Neuanlage `trip-new/tripNewLogic.ts:189`, `compare/alarmePropsAus.ts:102-104,127`. Go setzt keinen Default (nil).
- Filter `split_by_threshold`: `trip_alert.py:2786,3154,3485`, `compare_alert.py:403,442`, `compare_official_alert.py:353`, `compare_radar_alert.py:409`; Berichte `narrow.py:487` (telegram), `trip_report.py:461` (sms; SMS-Schwelle steuert auch amtliche Warnungen im SMS-/Telegram-Bericht, ADR-0046 :64-77).
- UI: `organisms/zustellung-tab/KanalTabelle.svelte:42-43,74,121-129,140`; Speichern `shared/zustellung-tab/zustellungSpeicherung.ts:31,64-66` (alle vier Kanäle); i18n `zustellung.json:35,60`, Stufen `alarme.json:27-29`.
- **Widerspruch heute:** Die Fußzeile (`zustellung.json:60`) behauptet schon „SMS ab mittel, Premium-SMS nur bei hoch“, der Code belegt alles mit LOW vor.

## Existing Patterns
- Neue Stelle in placements: wie `hourly` (nur Orte) / `outlook` — Stellen-Tupel, Lesefilter, View-Service-Spalte, Frontend-Spalten-Map.
- Kanal-Text-Kürzung SMS: `sms_format.md` §6 (Listenende zuerst, amtliche Bausteine zuletzt), Premium-Grenze 153 Zeichen.
- RMW für Schema-Reworks: ADR-0101, Pre-Snapshot-Hook `data_schema_backup.py`.
- Trip/Orte teilen den Code (ADR-0097), Pendant-Sperre.

## Dependencies / Dependents
- Python Core (Resolver, Renderer, Alarm-Versand), Go (Store/Handler placements, Modelle — Felder existieren), Frontend (Tabelle „Was steht wo“, Zustellung, Neuanlage), i18n DE/EN, Glossar.
- Docs: `docs/reference/premium_sms_format.md`, `sms_format.md` (Changelog v2.45 Premium = SMS-Text), `api_contract.md`, ADR-0124 Nr. 2/8 (müsste per neuem ADR abgelöst/ergänzt werden), Specs feat_3122 (AC-1, AC-22, :92, :329), feat_3057 AC-5, feat_3100.

## Existing Specs
`feat_3122_was_steht_wo.md`, `feat_3304_was_steht_wo_vorschau.md`, `feat_3057_kanal_liste_resolver.md`, `feat_3100_premium_sms_fallliste.md`, `feat_1461_s3b2a_kanal_schwelle.md`, `feat_1461_s3b2b_compare_kanal_schwelle.md`, `rework_2279_s1_alert_kanal_aufloesung.md`, `feat_1701_alarm_premium_sms.md`, `fix_2275_compare_premium_sms_versand.md`.

## Bestehende Tests (werden sich ändern)
- `tests/tdd/test_placements_aufloesung.py:115,129,405,446` (`premium_sms == sms`), `test_3100_premium_sms_fallliste.py` (ac1/ac2 premium gleich sms, ac4 Kürzung), `test_3237_golden_vier_kanaele.py`, `test_3172_orte_premium_versandweg.py`, `test_compare_premium_sms_versand.py`, `test_3099_sms_resolver.py`, `test_3237_placements_aus_grundauswahl.py`.
- Schwelle: `test_alert_channel_threshold.py:645,687` („ohne gesetzte Schwelle erreicht alle Kanäle“ — kollidiert mit neuer Vorbelegung), `test_compare_alert_channel_threshold.py:280,316`, `test_official_alert_channel_threshold.py`.
- Go: `internal/handler/trip_alert_channel_thresholds_test.go`, `compare_preset_alert_channel_thresholds_test.go`.
- Frontend: `alertChannelThresholds.test.ts:45,50` („ohne Bestand alle vier LOW“), `zustellungModell.test.ts`, `zustellungSpeicherung.test.ts`, `rework_3020_defaults_gleich_auslieferung.test.ts`, tripNewLogic-Tests, `was_steht_wo_karte*.test.ts`, `wetter_tab_i18n.test.ts:138-139`.

## Risks
1. **Vorbelegung ≠ Bestand:** „nicht gesetzt“ heißt heute LOW. Wird der Default für SMS/Premium angehoben, ändert sich das Verhalten für **Bestandsnutzer ohne gesetzten Wert** (sie bekämen plötzlich weniger SMS/Premium-Alarme). Issue: „Vorbelegung gilt für neue Abos und nicht gesetzte Werte“ — das bedeutet bewusst auch Bestand ohne Wert. Rote Linie #638 (Opt-in-Protokoll `below_channel_threshold`) muss erhalten bleiben. Sicherheitsrelevant: ein Alarm „mittel“ erreicht Premium-SMS nicht mehr — das ist gewollt, aber nur wenn E-Mail/Telegram/SMS ihn weiter bekommen.
2. **Offene Produktfrage zur Form** (eigene Spalte, eigene Reihenfolge?) — vor der Spec per AskUserQuestion klären bzw. in der Analyse mit begründeter Empfehlung vorlegen; ADR-0124 Nr. 3 spricht gegen eigene Reihenfolge.
3. **Alarme haben keine Metrikliste:** Die eigene Premium-Auswahl wirkt laut ADR-0124 Nr. 11 nur auf Briefings; der Alarm-Unterschied kommt allein über die Schwelle. Issue-Umfang 2 nennt „Briefing und Alarme“ — in der Spec klarstellen.
4. **Altdaten:** placements ohne `premium_sms` ⇒ Vorbelegung aus der SMS-Spalte (Issue: „z. B. die ersten 4 Zeilen der SMS-Liste“, kürzer als die SMS). Muss lesend abgeleitet werden, ohne Bestand zu überschreiben; `SaveBriefingPlacements` ersetzt das Feld als Ganzes (Frontend muss die Premium-Spalte mitschicken).
5. **Viele Tests und Docs sichern heute „Premium = SMS“ ab** (bewusste Umkehr, ADR-0124 Nr. 8 ⇒ neues ADR „Abgelöst/ergänzt durch“).
6. **E2E auf dem Server:** Premium-SMS-Empfang über die zweite seven.io-Nummer prüfen (Memory), Trip und Orte.
7. Kanal-Parität (ADR-0095): Premium-SMS beantwortet weiter dieselbe Frage — nur kürzer; Kürzung muss amtliche Warnungen zuletzt opfern.

## Analysis

**Type:** Feature (Scheibe S9 von Epic #2791), Daten-Schema-Rework (additiv).

### Teil A — eigene Premium-Spalte in „Was steht wo“
| Datei | Change | Grund |
|---|---|---|
| `src/services/placements.py` (:39-41, :84, :273-294) | MODIFY | Stelle `premium_sms` in `STELLEN`/`STELLEN_TRIP`; Lesefilter lässt sie durch; lesende Ableitung bei Altdaten (keine Zeile hat `premium_sms` ⇒ die ersten 4 SMS-Zeilen in gemeinsamer Reihenfolge); kein Roh/Einfach (nicht in `FORMAT_STELLEN`) |
| `api/routers/validator.py` (:579-584) | MODIFY | `premium_sms` als gültige Stelle |
| `src/services/channel_list_resolver.py` (:46-50, :163-170) | MODIFY | `premium_sms` aus eigener Spalte statt `kanaele["sms"]` |
| `src/services/report_config_resolver.py` (:287-302) | MODIFY | Orte: `enabled_metrics_by_channel`/`channel_rows_by_channel["premium_sms"]` |
| `src/output/renderers/trip_report.py` (:388-390, :482-494) | MODIFY | Premium-Text aus eigener Liste, 153 Zeichen, Kürzung Listenende zuerst, amtliche Warnungen zuletzt |
| `src/services/compare_briefing_aufbau.py` (:148-164), `src/services/comparison.py` (:1102-1130) | MODIFY | Orte-Premium aus eigener Liste |
| `src/services/notification_service.py` (:977-994, :1749-1756) | PRÜFEN | Versand nimmt `premium_sms_text`; Alarme unverändert (ADR-0124 Nr. 11) |
| `src/services/placements_view_service.py` (:31-38, :277, :308-316) | MODIFY | Spalte Premium-SMS (Warnungen „last“), Unterzeile „und Premium-SMS“ entfällt, `premium_sms_example` mit 153 vom echten Renderer (Budgetzeile) |
| Go `internal/store/briefing_placements.go`, `internal/handler/placements.go` | PRÜFEN | Rohbytes, keine Stellen-Whitelist erwartet |
| Frontend `shared/wetter-tab/wasStehtWoStand.ts`, `wasStehtWoAnsicht.ts`, `wasStehtWoSpeicherung.ts`, `organisms/wetter-tab/WasStehtWoKarte.svelte` | MODIFY | Spalte anzeigen/umschalten, beim Speichern mitschicken (Go ersetzt Feld), Hinweis „vorerst wie SMS“ ersetzen |
| i18n `frontend/src/lib/i18n/messages/{de,en}/wetter.json` (+ Glossar) | MODIFY | Spaltenkopf/Erklärsatz DE/EN |

### Teil B — Vorbelegung der Alarm-Dringlichkeit je Kanal
| Datei | Change | Grund |
|---|---|---|
| `frontend/src/lib/components/trip-new/tripNewLogic.ts` (:189) | MODIFY | Neuanlage schreibt explizit email/telegram LOW, sms MODERATE, premium_sms HIGH |
| `frontend/src/lib/components/compare/alarmePropsAus.ts` (:102-104,127) + Compare-Anlegen | MODIFY | dasselbe für Orts-Vergleich (geteilter Helfer, kein Pendant) |
| `frontend/src/lib/i18n/messages/{de,en}/zustellung.json` (:60) | MODIFY | Fußzeile ehrlich (gilt für neue Abos) |
| Python `alert_channel_threshold.py`, `trip_report.py:464`, `narrow.py:488` | UNVERÄNDERT (bei B2) | Laufzeit-Default LOW bleibt ⇒ Bestand unverändert |

### Docs / Specs / Tests
- CREATE neues ADR (ergänzt ADR-0124 Nr. 2/5/8, ergänzt ADR-0046 Vorbelegung bei Neuanlage); MODIFY `premium_sms_format.md`, `sms_format.md` (Changelog v2.45), `api_contract.md`; Specs feat_3122 (AC-1, AC-22, :92, :329), feat_3100 (AC-1/2/8), feat_1461_s3b2a (Vermerk).
- Tests umkehren: `test_placements_aufloesung.py`, `test_3100_premium_sms_fallliste.py`, `test_3237_golden_vier_kanaele.py`, `test_3172_*`, `test_compare_premium_sms_versand.py`, Golden-Fixtures; Frontend `alertChannelThresholds.test.ts`, tripNewLogic-, Zustellungs-, was_steht_wo-Tests. Neu: `tests/tdd/test_2801_*` + Frontend-Gegenstück, zwei Nutzer.

### Scope / Risk
- A: ca. 25 Dateien, 500–700 LoC + ~10 umgekehrte Tests. B2: ca. 4 Dateien, ~40 LoC + 4 Tests. **Ein Workflow, Spec mit AC-Gruppen A und B**; B ist abtrennbar, falls zu groß.
- Risiko **mittel**: zentrale Ausgabe (Premium-Briefing Trip+Orte), aber additiv; Alarmtexte unverändert.

### Technical Approach (Empfehlung Plan-Agent, übernommen)
1. ADR, Glossar, Spec. 2. Teil B2. 3. Teil A: Datenmodell/Lesefilter → Resolver/Renderer Trip → Orte → Vorschau-Service → Frontend-Spalte → Tests/Docs. 4. E2E Staging: Premium-SMS über zweite seven.io-Nummer (Trip und Orte), Neuanlage zeigt Vorbelegung, Alarm „mittel“ erreicht SMS, nicht Premium.

### Befunde gegen den Plan
1. **B1 (Laufzeit-Default ändern) bricht PO-Bindung** ADR-0046 Z.47/72-77, feat_1461_s3b2a AC-13 + PO 2026-08-05 („ohne gesetzte Schwelle Alarme wie vorher“), ADR-0095 Z.63; schaltet Bestand still SMS-/Premium-Alarme ab.
2. **SMS-Schwelle steuert auch amtliche Warnungen im SMS-Briefing** (`trip_report.py:461-464`, ADR-0046 :64-77, bestehende PO-Entscheidung): Neue Abos mit SMS „mittel“ sehen im SMS-/Premium-Briefing keine amtlichen Warnungen der Stufe gering mehr. Folgt aus bestehender Entscheidung; in der Spec offenlegen.
3. SMS und Premium-SMS sind bei Neuanlage per Opt-in AUS (`alert_channel_new_default.md` AC-3) — die Vorbelegung wirkt erst, wenn der Nutzer den Kanal einschaltet.
4. Issue-Satz „Renderer … Alarme liest die eigene Liste“ ist hinfällig: Alarme haben keine Metrikliste (ADR-0124 Nr. 11); Alarm-Unterschied nur über Schwelle.
5. Premium-Grenze ist 153 Zeichen (`channel_layout.py:57`), nicht 160 (Issue/Mockup).
6. Erstes Speichern schreibt die lesend abgeleitete Premium-Spalte fest (Go ersetzt das Feld) — deterministische Ableitung nötig.
7. Mockup-Fassung 3 ist durch Fassung 4 ersetzt; Fassung 4 :385/:765 zeigt die Vorbelegung, :625 noch „vorerst wie SMS“.

### Open Questions (PO)
1. Gilt die neue Vorbelegung auch für Bestand ohne gesetzten Wert? Empfehlung: Nein (B2).
2. Form der Premium-Auswahl: eigene Spalte in „Was steht wo“, gleiche Reihenfolge, Startwert = erste 4 Zeilen der SMS-Auswahl? Empfehlung: Ja.

## PO-Entscheidungen 2026-11-28 (AskUserQuestion, ersetzen die Open Questions)
1. **Bestand umstellen (B1):** Auch bestehende Trips/Orts-Vergleiche ohne gewählte Stufe melden ab sofort per SMS erst ab „mittel“ (MODERATE) und per Premium-SMS erst ab „hoch“ (HIGH); E-Mail/Telegram bleiben „gering“ (LOW). Hebt die PO-Entscheidung 2026-08-05 / feat_1461_s3b2a AC-13 / ADR-0046 Z.47 „Startwert LOW für alle“ auf ⇒ neues ADR (löst ADR-0046 teilweise ab, ADR-0095 Z.63). Gesetzte Werte bleiben unverändert. Rote Linie #638 (rohes Opt-in im Protokoll, Grund `below_channel_threshold`) bleibt.
2. **Keine eigene Premium-Auswahl:** Die Premium-SMS bekommt immer dieselben Werte wie die SMS (gekürzt von hinten auf 153 Zeichen, amtliche Warnungen zuletzt). Keine eigene Spalte in „Was steht wo“. Hinweis unter der Tabelle: „Die Premium-SMS bekommt denselben Inhalt wie die SMS.“ (statt „vorerst … eigene Auswahl kommt später“). Löst Konzept-Entscheidung N2 („eigene Liste“) ab; ADR-0124 Nr. 8 „vorerst“ wird endgültig.

**Folge für den Scope:** Teil A (eigene Spalte) entfällt komplett. Verbleibt: Laufzeit-Vorbelegung je Kanal an ALLEN Default-Stellen (Python `alert_channel_threshold.py:17`, `trip_report.py:464`, `narrow.py:488`; Frontend `alertChannelState.ts`, `zustellungModell.ts`, `tripNewLogic.ts`, `alarmePropsAus.ts`) über EINE Quelle je Sprache; Texte (Hinweis Premium, Fußzeile Zustellung) DE/EN; neues ADR; Docs/Specs (feat_3122 :92/:329, feat_3057 AC-5, feat_1461 AC-13 Vermerk, premium_sms_format.md, einstellungen_neu.md N2); Tests umstellen („ohne Bestand alle LOW“).
**Offenzulegende Folge (Spec):** Die SMS-Schwelle steuert laut ADR-0046 :64-77 auch, welche amtlichen Warnungen im SMS-Briefing (und damit Premium-SMS) stehen; mit Vorbelegung „mittel“ fallen dort amtliche Warnungen der Stufe gering weg, für alle Nutzer ohne gesetzten Wert.
